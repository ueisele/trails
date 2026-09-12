"""Lantmäteriet's *Ortnamn Nedladdning, vektor*: every place name in Sweden, typed.

The Stedsnavn of Sweden. One GeoPackage for the country -- 989,302 names on
2026-09-12 -- a point per name, with the name as the naming authority fixed
it, the kind of thing it names (:data:`TYPES`) and the language it is in
(:data:`LANGUAGES`): over Abisko 242 of 402 names are North Sámi. No outline
for a valley or a lake, and no importance rank; the map's own lettering
(:mod:`trails.io.sources.topografi50`, the text theme) carries the size a
name is drawn at, and a page that wants one reads it from there.

Where the file is was read off Lantmäteriet's keyless vector STAC
(``api.lantmateriet.se/stac-vektor/v1``, item ``ortnamn_se``), and the file
itself answers **403 until the product is ordered** in Geotorget -- free,
CC BY 4.0, no review, as a *Behörighet* like the height model -- and 200
with the Geotorget login after that (measured 2026-09-12, both ways). The
login arrives through the environment as it does for the height model and
the Topografi 50 delivery. Cached whole, 58 MB, and read by box over the
GeoPackage's index.
"""

import os
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pyogrio

from trails.utils.geo import project_bounds
from trails.utils.tiles import Bounds

from .topografi50 import PASSWORD_VAR, USERNAME_VAR, _auth_header, _download

#: The file, as the STAC item ``ortnamn_se`` names it. Rewritten nightly.
FILE_URL = "https://dl1.lantmateriet.se/namnsatt-plats/ortnamn_se.zip"

#: The STAC item that names the file, keyless, for anyone checking the address.
STAC_ITEM_URL = "https://api.lantmateriet.se/stac-vektor/v1/collections/ortnamn/items/ortnamn_se"

#: What the GeoPackage is delivered in.
CRS = "EPSG:3006"
LAYER = "ortnamn"

#: The name, what kind of thing it names, which language it is in, and its
#: number in the register.
NAME, TYPE, LANGUAGE, ID = "ortnamn", "detaljtyp", "sprak", "lopnummer"

#: Every ``detaljtyp`` the file carries (counted nationwide 2026-09-12), in
#: English. A terrain name is a peak, a valley, a pass or a slope alike --
#: the register does not say which; the name does (*-čohkka* a peak,
#: *-vággi* a valley).
TYPES = {
    "TERRTX": "terrain",
    "VATTTX": "lake",
    "VATTDRTX": "watercourse",
    "VATTDELTX": "part of a water",
    "GLACIÄRTX": "glacier",
    "SANKTX": "marsh",
    "BEBTX": "settlement or building",
    "BEBTÄTTX": "built-up area",
    "TRAKTTX": "tract",
    "ANLTX": "facility",
    "KULTURTX": "cultural site",
    "KYRKATX": "church",
    "NATTX": "nature conservation object",
}

#: The types a walking map draws as names on the ground, grouped as a legend
#: groups them. Tracts are regions rather than places and cultural sites,
#: churches and conservation objects are drawn by other layers.
TERRAIN_TYPES = ("TERRTX", "GLACIÄRTX", "SANKTX")
WATER_TYPES = ("VATTTX", "VATTDRTX", "VATTDELTX")
SETTLEMENT_TYPES = ("BEBTX", "BEBTÄTTX", "ANLTX")
NAME_TYPES = TERRAIN_TYPES + WATER_TYPES + SETTLEMENT_TYPES

#: Every ``sprak`` the file carries, in English.
LANGUAGES = {
    "SV": "Swedish",
    "NS": "North Sámi",
    "LS": "Lule Sámi",
    "US": "Ume Sámi",
    "SS": "South Sámi",
    "TF": "Meänkieli",
    "FI": "Finnish",
}

#: Seconds the download may take.
TIMEOUT_S = 300


@dataclass(frozen=True)
class SourceMetadata:
    """Provenance of the names."""

    name: str = "Ortnamn Nedladdning, vektor"
    provider: str = "Lantmäteriet"
    country: str = "SE"
    url: str = "https://www.lantmateriet.se/sv/geodata/vara-produkter/produktlista/ortnamn-nedladdning-vektor/"
    license: str = "CC BY 4.0"
    attribution: str = "© Lantmäteriet"
    update_frequency: str = "daily"


METADATA = SourceMetadata()


def type_label(value: object) -> str:
    """Say what a type code names, in English; the code itself where none is known."""
    return TYPES.get(str(value), str(value))


def language_label(value: object) -> str:
    """Say which language a code is, in English; the code itself where none is known."""
    return LANGUAGES.get(str(value), str(value))


def _file_date(path: Path) -> str | None:
    with zipfile.ZipFile(path) as archive:
        stamps = [datetime(*info.date_time) for info in archive.infolist()]
    return max(stamps).strftime("%Y-%m-%d") if stamps else None


class Source:
    """The country's names, one file on disk, read by box."""

    def __init__(
        self,
        cache_dir: str | Path = ".cache",
        username: str | None = None,
        password: str | None = None,
        download: Callable[[str, str, Path], None] = _download,
    ):
        """Point at the file.

        Args:
            cache_dir: Root cache directory; the file goes under ``ortnamn``
            username: Geotorget login; :data:`USERNAME_VAR` by default
            password: Geotorget password; :data:`PASSWORD_VAR` by default
            download: How the file is fetched
        """
        self.cache_dir = Path(cache_dir) / "ortnamn"
        self.username = username if username is not None else os.environ.get(USERNAME_VAR, "")
        self.password = password if password is not None else os.environ.get(PASSWORD_VAR, "")
        self.download = download
        #: The day the file on disk was written, once one has been read.
        self.version: str | None = None

    @property
    def archive(self) -> Path:
        """Where the zip is kept."""
        return self.cache_dir / FILE_URL.rsplit("/", 1)[-1]

    def fetch(self, force_download: bool = False) -> Path:
        """Have the file on disk, fetching it with the login if it is not.

        Args:
            force_download: Fetch it again even if it is there

        Returns:
            The archive

        Raises:
            RuntimeError: If the file is missing and so is the login
        """
        if self.archive.exists() and not force_download:
            self.version = _file_date(self.archive)
            return self.archive
        if not (self.username and self.password):
            raise RuntimeError(f"{METADATA.name} needs the Geotorget login; set {USERNAME_VAR} and {PASSWORD_VAR}")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        print(f"Fetching {METADATA.name} ({FILE_URL})...", flush=True)
        self.download(FILE_URL, _auth_header(self.username, self.password), self.archive)
        self.version = _file_date(self.archive)
        print(f"  {self.archive.stat().st_size / 1e6:,.0f} MB, written {self.version}", flush=True)
        return self.archive

    def geopackage(self, force_download: bool = False) -> Path:
        """The GeoPackage, unpacked beside the archive.

        Args:
            force_download: Fetch the archive again first

        Returns:
            The GeoPackage
        """
        archive = self.fetch(force_download)
        with zipfile.ZipFile(archive) as opened:
            inner = next(name for name in opened.namelist() if name.endswith(".gpkg"))
            target = self.cache_dir / inner
            if not target.exists() or force_download:
                opened.extract(inner, self.cache_dir)
        return target

    def names(self, bounds: Bounds, types: tuple[str, ...] | None = NAME_TYPES, force_download: bool = False) -> gpd.GeoDataFrame:
        """Every name over a box, of the types asked for.

        Args:
            bounds: The box, WGS 84
            types: Which :data:`TYPES` to keep; None for all of them
            force_download: Fetch the file again first

        Returns:
            Points in WGS 84 with ``name``, ``kind`` (the type code),
            ``kind_label``, ``language`` (in English) and ``name_id``, plus
            the register's own columns
        """
        path = self.geopackage(force_download)
        box = project_bounds(bounds, "EPSG:4326", CRS)
        read = pyogrio.read_dataframe(path, layer=LAYER, bbox=box)
        if types is not None:
            read = read[read[TYPE].isin(types)]
        placed: gpd.GeoDataFrame = gpd.GeoDataFrame(read, geometry="geometry", crs=CRS).to_crs("EPSG:4326").reset_index(drop=True)
        placed["name"] = placed[NAME]
        placed["kind"] = placed[TYPE]
        placed["kind_label"] = placed[TYPE].map(type_label)
        placed["language"] = placed[LANGUAGE].map(language_label)
        placed["name_id"] = placed[ID]
        return placed
