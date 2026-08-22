"""Ordering per-municipality datasets from Geonorge.

Several Kartverket datasets are distributed municipality by municipality through
an order API that hands back short-lived download links. The flow is the same
for all of them, so it lives here rather than in each source::

    client = KommuneOrderClient(METADATA_UUID, "n50", download_cache)
    archives = client.fetch(["1824", "1813"])

Orders are skipped entirely when every archive is already cached, which matters
because the links expire.
"""

from dataclasses import dataclass

import requests

from ..cache import Download as DownloadCache

ORDER_URL = "https://nedlasting.geonorge.no/api/order"

#: EUREF89 UTM zone 33, the projection these datasets are ordered in for northern Norway.
PROJECTION = {
    "code": "25833",
    "name": "EUREF89 UTM sone 33, 2d",
    "codespace": "http://www.opengis.net/def/crs/EPSG/0/25833",
}


@dataclass(frozen=True)
class OrderedFile:
    """One file made available by a Geonorge order."""

    name: str
    url: str


class KommuneOrderClient:
    """Orders and downloads a Geonorge dataset per municipality."""

    def __init__(
        self,
        metadata_uuid: str,
        prefix: str,
        downloads: DownloadCache,
        timeout: int = 600,
        data_format: str = "FGDB",
    ):
        """Initialize the client.

        Args:
            metadata_uuid: Geonorge catalogue entry for the dataset
            prefix: Prefix for cached archive filenames, e.g. "n50"
            downloads: Download cache the archives are stored in
            timeout: HTTP timeout in seconds
            data_format: Distribution format to order
        """
        self.metadata_uuid = metadata_uuid
        self.prefix = prefix
        self.downloads = downloads
        self.timeout = timeout
        self.data_format = data_format

    def local_name(self, kommune_code: str) -> str:
        """Return the cache filename used for a municipality's archive.

        Args:
            kommune_code: Municipality number

        Returns:
            Filename inside the download cache
        """
        return f"{self.prefix}_{kommune_code}.zip"

    def order(self, kommune_codes: list[str]) -> list[OrderedFile]:
        """Place a Geonorge order and return the resulting download links.

        Args:
            kommune_codes: Municipality numbers to order

        Returns:
            One entry per file the order made available

        Raises:
            requests.HTTPError: If the order was rejected
            ValueError: If the response carries no downloadable files
        """
        payload = {
            "orderLines": [
                {
                    "metadataUuid": self.metadata_uuid,
                    "areas": [{"type": "kommune", "code": code, "name": code} for code in kommune_codes],
                    "projections": [PROJECTION],
                    "formats": [{"name": self.data_format}],
                }
            ]
        }

        print(f"Ordering {self.prefix} for {len(kommune_codes)} municipalities from Geonorge...")
        response = requests.post(ORDER_URL, json=payload, timeout=self.timeout)
        response.raise_for_status()

        files = [OrderedFile(name=entry["name"], url=entry["downloadUrl"]) for entry in response.json().get("files", []) if entry.get("downloadUrl")]
        if not files:
            raise ValueError(f"Geonorge order returned no downloadable files for {kommune_codes}")
        return files

    def ordered_at(self, kommune_codes: list[str]) -> str | None:
        """Say when this dataset was last ordered for these municipalities.

        The register publishes no version string, so the order date is what an
        exported file has to record instead: a plan opened months later then has
        a cause for any difference rather than a puzzle.

        Args:
            kommune_codes: Municipality numbers the answer covers

        Returns:
            ISO timestamp of the **oldest** archive in the cache, since that is
            the age of the answer as a whole — a set of files ordered on
            different days is only as current as the one that was not
            re-ordered. None where nothing is cached for any of them.
        """
        dates = [self.downloads.downloaded_at(self.local_name(code)) for code in kommune_codes]
        present = sorted(date for date in dates if date)
        return present[0] if present else None

    def fetch(self, kommune_codes: list[str], force_download: bool = False) -> dict[str, str]:
        """Ensure each municipality's archive is present in the cache.

        Args:
            kommune_codes: Municipality numbers to fetch
            force_download: Re-order and re-download even if cached

        Returns:
            Mapping of municipality number to local archive path

        Raises:
            LookupError: If the order returned no file for a requested municipality
        """
        missing = [code for code in kommune_codes if force_download or self.downloads.get_cached_file(self.local_name(code)) is None]

        if missing:
            ordered = self.order(missing)
            for code in missing:
                # Geonorge names files "Basisdata_<kommune>_<name>_...zip".
                match = next((entry for entry in ordered if f"_{code}_" in entry.name), None)
                if match is None:
                    raise LookupError(f"Geonorge order returned no file for municipality {code}")
                self.downloads.download(url=match.url, filename=self.local_name(code), version=match.name, force=force_download)

        return {code: str(self.downloads.cache_dir / self.local_name(code)) for code in kommune_codes}
