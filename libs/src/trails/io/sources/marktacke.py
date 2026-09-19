"""Lantmäteriet's Marktäcke: the Swedish sheet's land cover as outlines, and its wetlands apart.

The product Topografi 50 draws its ground from -- *Marktäcke Nedladdning,
vektor*, CC BY 4.0, one GeoPackage per municipality, updated weekly --
carries the wetlands as a layer of their own, ``sankmark``, in two kinds the
sheet has always drawn and the legend has always named: *Sankmark, fast*,
peat-forming ground on comparatively firm peat that usually carries a boot,
and *Sankmark, våt*, ground often or always under water that usually does
not. That distinction is the one a walker wants, and no other source over
either map makes it (analysis/docs/abisko-decisions.md §6.13).

**Through the same door as the heights.** The municipalities are items of the
``marktacke`` collection of Lantmäteriet's vector STAC API, found by box, and
each item's file answers 403 until the product has been ordered once in
Geotorget -- free, one click, and Uwe's to do -- and 200 with the Geotorget
login after that, the way :mod:`.markhojd` and :mod:`.ortnamn` are read. The
Abisko box lies in one municipality, Kiruna (``2584``, 200 MB zipped, 540 MB
as a GeoPackage of 84,000 land outlines and 41,000 wetlands, 2026-09-19).

**Measured over the Abisko box, 2026-09-19:** 357 firm wetlands of 8.3 km²
and 34 wet ones of 0.17 km² -- 0.63 % of the land. That is the survey's word
and it is kept, but it is not the whole of the wet ground: the soil-moisture
model (:mod:`.slu_moisture`) finds four times as much, most of it outside
these outlines, which is why the mire tiles carry a third class.
"""

import dataclasses
import os
import urllib.parse
import urllib.request
import zipfile
from base64 import b64encode
from collections.abc import Callable
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box as box_of

from ...utils.tiles import Bounds
from .markhojd import PASSWORD_VAR, TIMEOUT_S, USERNAME_VAR, _get_json


@dataclasses.dataclass(frozen=True)
class SourceMetadata:
    """Provenance of the wetlands."""

    name: str = "Marktäcke Nedladdning, vektor"
    provider: str = "Lantmäteriet"
    country: str = "SE"
    url: str = "https://www.lantmateriet.se/sv/geodata/vara-produkter/produktlista/marktacke-nedladdning-vektor/"
    license: str = "CC BY 4.0"
    attribution: str = "© Lantmäteriet"


METADATA = SourceMetadata()

#: The vector STAC API the municipalities are listed through.
STAC_URL = "https://api.lantmateriet.se/stac-vektor/v1"

#: The collection: one item per municipality, one zipped GeoPackage each.
COLLECTION = "marktacke"

#: Items per page asked of the API.
PAGE_SIZE = 100

#: The layer of the GeoPackage that holds the wetlands.
WETLAND_LAYER = "sankmark"

#: What the layer calls a wetland that usually carries a boot, and one that does not.
FIRM_TYPE = "Sankmark, fast"
WET_TYPE = "Sankmark, våt"

#: The files' projection: SWEREF 99 TM.
CRS = "EPSG:3006"


@dataclasses.dataclass(frozen=True)
class Municipality:
    """One item of the collection: a municipality's file and the box it covers."""

    #: The municipality's number, as the item id: Kiruna is ``2584``.
    id: str
    #: Where its zipped GeoPackage is.
    href: str
    #: What it covers, WGS 84.
    bounds: Bounds


def municipalities_from(page: dict[str, object]) -> list[Municipality]:
    """Read the municipalities out of one STAC page.

    Args:
        page: The page, as the API answers it

    Returns:
        The municipalities, in the page's order
    """
    found = []
    features = page.get("features", [])
    assert isinstance(features, list)
    for feature in features:
        bbox = feature["bbox"]
        found.append(Municipality(id=str(feature["id"]), href=feature["assets"]["data"]["href"], bounds=(bbox[0], bbox[1], bbox[2], bbox[3])))
    return found


def search(bounds: Bounds, fetch: Callable[[str], dict[str, object]] = _get_json) -> list[Municipality]:
    """Which municipalities touch a box.

    Args:
        bounds: The box, WGS 84
        fetch: How a page is read; the API by default, a stand-in in a test

    Returns:
        The municipalities, sorted by id, every page followed
    """
    query = urllib.parse.urlencode({"bbox": ",".join(f"{value:.6f}" for value in bounds), "limit": PAGE_SIZE}, safe=",")
    url: str | None = f"{STAC_URL}/collections/{COLLECTION}/items?{query}"
    found: list[Municipality] = []
    while url:
        page = fetch(url)
        found.extend(municipalities_from(page))
        links = page.get("links", [])
        assert isinstance(links, list)
        url = next((link["href"] for link in links if link.get("rel") == "next"), None)
    return sorted(found, key=lambda municipality: municipality.id)


def _download(url: str, target: Path, username: str, password: str) -> None:
    """Fetch one file with the Geotorget login, whole, into ``target``."""
    token = b64encode(f"{username}:{password}".encode()).decode("ascii")
    request = urllib.request.Request(url, headers={"Authorization": f"Basic {token}"})
    partial = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as answer, partial.open("wb") as out:
        while chunk := answer.read(1 << 20):
            out.write(chunk)
    partial.replace(target)


class Source:
    """The wetlands of the sheet, read municipality by municipality and kept as files."""

    def __init__(
        self,
        cache_dir: str | Path = ".cache",
        username: str | None = None,
        password: str | None = None,
        fetch: Callable[[str], dict[str, object]] = _get_json,
        download: Callable[[str, Path, str, str], None] = _download,
    ):
        """Point at the product.

        Args:
            cache_dir: Where the municipalities' files are kept between builds
            username: Geotorget login; :data:`~trails.io.sources.markhojd.USERNAME_VAR` by default
            password: Geotorget password; :data:`~trails.io.sources.markhojd.PASSWORD_VAR` by default
            fetch: How a STAC page is read
            download: How a file is fetched; the login goes in as its last two arguments
        """
        self.cache_dir = Path(cache_dir) / "marktacke"
        self.username = username if username is not None else os.environ.get(USERNAME_VAR, "")
        self.password = password if password is not None else os.environ.get(PASSWORD_VAR, "")
        self.fetch = fetch
        self.download = download

    def geopackage(self, municipality: Municipality, force_download: bool = False) -> Path:
        """One municipality's GeoPackage, fetched and unpacked if it is not in the cache.

        Args:
            municipality: Which one
            force_download: Fetch it again even if it is there

        Returns:
            The GeoPackage

        Raises:
            RuntimeError: If it has to be fetched and the login is missing
            ValueError: If the archive holds no GeoPackage
        """
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        kept = self.cache_dir / f"marktacke_kn{municipality.id}.gpkg"
        if kept.exists() and not force_download:
            return kept
        if not (self.username and self.password):
            raise RuntimeError(f"{METADATA.name} needs the Geotorget login; set {USERNAME_VAR} and {PASSWORD_VAR}")
        archive = self.cache_dir / f"marktacke_kn{municipality.id}.zip"
        print(f"Fetching {METADATA.name} for municipality {municipality.id}...", flush=True)
        self.download(municipality.href, archive, self.username, self.password)
        with zipfile.ZipFile(archive) as bundle:
            names = [name for name in bundle.namelist() if name.lower().endswith(".gpkg")]
            if len(names) != 1:
                raise ValueError(f"{archive.name} holds {len(names)} GeoPackages; expected one")
            with bundle.open(names[0]) as packed, kept.with_suffix(".part").open("wb") as out:
                while chunk := packed.read(1 << 20):
                    out.write(chunk)
        kept.with_suffix(".part").replace(kept)
        archive.unlink()
        return kept

    def wetlands(self, bounds: Bounds, force_download: bool = False) -> gpd.GeoDataFrame:
        """The wetlands over a box, firm and wet, cut to it.

        Args:
            bounds: The box, WGS 84
            force_download: Fetch the files again even if they are cached

        Returns:
            GeoDataFrame in :data:`CRS` with the columns ``objekttyp`` (the
            layer's own word), ``wet`` (True for *Sankmark, våt*), ``kommun``
            and ``geometry``; empty, with those columns, where the box has none

        Raises:
            RuntimeError: If no municipality covers the box
        """
        municipalities = search(bounds, self.fetch)
        if not municipalities:
            raise RuntimeError(f"no municipality of {COLLECTION} covers {bounds}")
        window = gpd.GeoSeries([box_of(*bounds)], crs="EPSG:4326").to_crs(CRS).iloc[0]
        frames = []
        for municipality in municipalities:
            layer = gpd.read_file(self.geopackage(municipality, force_download=force_download), layer=WETLAND_LAYER, bbox=window.bounds)
            if len(layer) == 0:
                continue
            layer = layer.to_crs(CRS)
            layer = layer[layer.intersects(window)].copy()
            layer["geometry"] = layer.geometry.intersection(window)
            layer["kommun"] = municipality.id
            frames.append(layer[["objekttyp", "kommun", "geometry"]])
        if not frames:
            return gpd.GeoDataFrame({"objekttyp": [], "wet": [], "kommun": []}, geometry=[], crs=CRS)
        merged = gpd.GeoDataFrame(gpd.pd.concat(frames, ignore_index=True), crs=CRS)
        merged["wet"] = merged["objekttyp"] == WET_TYPE
        return gpd.GeoDataFrame(merged[["objekttyp", "wet", "kommun", "geometry"]], crs=CRS)
