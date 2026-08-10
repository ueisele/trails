"""Norwegian municipality lookup via Kartverket's Kommuneinfo API.

Several Geonorge datasets are distributed per municipality rather than as a
single national file, so working with them starts with the question "which
municipalities does my area of interest touch?"::

    source = Source()
    codes = source.intersecting(approach_zone)
"""

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import shape

from ..cache import Object as ObjectCache

SERVICE_URL = "https://api.kartverket.no/kommuneinfo/v1"

#: Kommuneinfo speaks ETRS89 geographic coordinates, equivalent to WGS84 here.
API_CRS = "EPSG:4258"


class Source:
    """Loader for Norwegian municipality names and boundaries."""

    def __init__(self, cache_dir: str = ".cache", timeout: int = 60):
        """Initialize the Kommuneinfo source.

        Args:
            cache_dir: Root directory for caching data
            timeout: HTTP timeout in seconds
        """
        self.cache = ObjectCache(f"{cache_dir}/objects")
        self.timeout = timeout

    def list_all(self, force_download: bool = False) -> pd.DataFrame:
        """List every Norwegian municipality.

        Args:
            force_download: Bypass the cache and re-query the service

        Returns:
            DataFrame with the columns ``number`` and ``name``
        """
        cache_key = "kommuneinfo_all"
        if not force_download and self.cache.exists(cache_key):
            cached = self.cache.load(cache_key)
            assert isinstance(cached, pd.DataFrame)
            return cached

        print("Fetching municipality list from Kommuneinfo...")
        response = requests.get(
            f"{SERVICE_URL}/kommuner",
            params={"filtrer": "kommunenummer,kommunenavnNorsk"},
            timeout=self.timeout,
        )
        response.raise_for_status()

        frame = pd.DataFrame(
            [{"number": row["kommunenummer"], "name": row["kommunenavnNorsk"]} for row in response.json()],
        ).sort_values("number", ignore_index=True)

        self.cache.save(cache_key, frame, metadata={"count": len(frame)})
        return frame

    def bounding_box(self, number: str, force_download: bool = False) -> gpd.GeoDataFrame:
        """Fetch a municipality's bounding box.

        Much cheaper than the full outline, so it works well as a first pass
        when testing many municipalities against an area.

        Args:
            number: Municipality number, e.g. "1824"
            force_download: Bypass the cache and re-query the service

        Returns:
            Single-row GeoDataFrame in EPSG:4326
        """
        return self._fetch_geometry(number, detailed=False, force_download=force_download)

    def geometry(self, number: str, force_download: bool = False) -> gpd.GeoDataFrame:
        """Fetch a municipality's full outline.

        Args:
            number: Municipality number, e.g. "1824"
            force_download: Bypass the cache and re-query the service

        Returns:
            Single-row GeoDataFrame in EPSG:4326
        """
        return self._fetch_geometry(number, detailed=True, force_download=force_download)

    def _fetch_geometry(self, number: str, detailed: bool, force_download: bool) -> gpd.GeoDataFrame:
        """Fetch either the outline or the bounding box of a municipality.

        Args:
            number: Municipality number
            detailed: Request the full outline instead of the bounding box
            force_download: Bypass the cache and re-query the service

        Returns:
            Single-row GeoDataFrame in EPSG:4326

        Raises:
            LookupError: If the service returns no geometry for the number
        """
        kind = "omrade" if detailed else "bbox"
        cache_key = f"kommuneinfo_{kind}_{number}"

        if not force_download and self.cache.exists(cache_key):
            cached = self.cache.load(cache_key)
            assert isinstance(cached, gpd.GeoDataFrame)
            return cached

        url = f"{SERVICE_URL}/kommuner/{number}/omrade" if detailed else f"{SERVICE_URL}/kommuner/{number}"
        response = requests.get(url, params={"utkoordsys": "4258"}, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()

        raw = payload.get("omrade") if detailed else payload.get("avgrensningsboks")
        if not raw:
            raise LookupError(f"Kommuneinfo returned no {kind} for municipality {number}")

        gdf = gpd.GeoDataFrame(
            {"number": [number], "name": [payload.get("kommunenavn")]},
            geometry=[shape(raw)],
            crs=API_CRS,
        ).to_crs("EPSG:4326")

        self.cache.save(cache_key, gdf, metadata={"number": number, "kind": kind})
        return gdf

    def intersecting(self, area: gpd.GeoDataFrame, fylke: tuple[str, ...] | None = None) -> list[str]:
        """Find the municipalities an area overlaps.

        Candidates are narrowed by bounding box first so only a handful of full
        outlines have to be fetched.

        Args:
            area: Area of interest in EPSG:4326
            fylke: County number prefixes to restrict the search to, e.g.
                ``("18",)`` for Nordland. Searching all of Norway is possible
                but costs one request per municipality.

        Returns:
            Municipality numbers whose outline intersects the area, sorted
        """
        candidates = self.list_all()
        if fylke:
            candidates = candidates[candidates["number"].str.startswith(fylke)]

        area_union = area.to_crs("EPSG:4326").union_all()

        by_bbox = []
        for number in candidates["number"]:
            if self.bounding_box(number).geometry.iloc[0].intersects(area_union):
                by_bbox.append(number)

        matches = [number for number in by_bbox if self.geometry(number).geometry.iloc[0].intersects(area_union)]
        print(f"Area touches {len(matches)} municipalities: {', '.join(matches)}")
        return sorted(matches)
