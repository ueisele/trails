"""Naturvårdsverket's open files: the protected areas, and the trail register.

Both sit as plain files under ``geodata.naturvardsverket.se/nedladdning``,
rewritten every night, behind no login. The same data is also served over WFS,
and that server answered *503 ArcGIS Server Error* for a whole day
(2026-09-12); the files did not go anywhere, and a file is what a build wants
in any case — it is read once, it is cached whole, and it says the same thing
tomorrow.

Two registers, one loader:

- **naturvardsregistret** — one zipped shapefile per protection form, every one
  of them with the same columns: the register's own id, the name, the form, and
  what decided it. The forms in :data:`FORMS` are the ones with an outline.
- **friluftsliv** — the trail register, *Leder och friluftsanordningar*:
  every marked trail in the country with its season, its marking and the state
  trail it belongs to, and the facilities along them. Nationwide, not only in
  protected areas: over Abisko 34 of the 47 lines in the box lie outside one.

Everything is delivered in SWEREF 99 TM and handed on in WGS 84, which is what
the rest of the build expects a register to speak.
"""

import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pyogrio

from trails.io import cache
from trails.utils.geo import project_bounds
from trails.utils.tiles import Bounds

#: Where the files are.
BASE_URL = "https://geodata.naturvardsverket.se/nedladdning"

#: What the files are delivered in.
CRS = "EPSG:3006"

#: The register's protection forms that come as outlines, by the file each is
#: in, and the value the ``SKYDDSTYP`` column carries for it.
FORMS = {
    "NP": "Nationalpark",
    "NR": "Naturreservat",
    "NVO": "Naturvårdsområde",
    "DVO": "Djur- och växtskyddsområde",
    "KR": "Kulturreservat",
    "NM": "Naturminne",
    "LBSO": "Landskapsbildsskyddsområde",
    "OBO": "Övrigt biotopskyddsområde",
}

#: The words a sign would use for each form, for the page.
FORM_LABELS = {
    "Nationalpark": "national park",
    "Naturreservat": "nature reserve",
    "Naturvårdsområde": "nature conservation area",
    "Djur- och växtskyddsområde": "wildlife sanctuary",
    "Kulturreservat": "cultural reserve",
    "Naturminne": "natural monument",
    "Landskapsbildsskyddsområde": "landscape protection area",
    "Övrigt biotopskyddsområde": "biotope protection area",
}

NATIONAL_PARK = "Nationalpark"

#: What names an area, what it is called and which form it is.
AREA_ID, AREA_NAME, AREA_FORM = "NVRID", "NAMN", "SKYDDSTYP"

#: What the areas carry besides those three.
AREA_FIELDS = ("IUCNKAT", "FORVALTARE", "URSBESLDAT", "AREA_HA", "LAN", "KOMMUN")

#: The trail register's two files, and the layer in each.
TRAILS_FILE, TRAILS_LAYER = "friluftsliv/Leder_shp.zip", "Leder.shp"
FACILITIES_FILE, FACILITIES_LAYER = "friluftsliv/Anordningar_shp.zip", "Anordningar.shp"

#: What a trail says about itself.
TRAIL_ID = "L_ID"
TRAIL_NAME = "LNAMN"
TRAIL_SEASON = "LKATEGORI"
TRAIL_TYPE = "LTYP"
TRAIL_MARKING = "LMARKERING"
TRAIL_DESCRIPTION = "BESKRIVN"
#: The state trail a segment belongs to, as ``Abisko - Abiskojaure (BD 21)``,
#: and its number alone. The number is the key the county's brochures, the
#: signs and Naturkartan all use.
TRAIL_ROUTE, TRAIL_ROUTE_ID = "STATLED", "STATLED_ID"
TRAIL_PROTECTED, TRAIL_PROTECTED_ID = "SKOMRDE", "SKOMRDE_ID"

#: The two seasons the register separates. A winter trail runs over lakes and
#: bogs and is nothing to walk in August.
SUMMER, WINTER = "Barmarksled", "Led på snö"

#: What a facility says about itself.
FACILITY_ID, FACILITY_NAME, FACILITY_TYPE, FACILITY_SUBTYPE = "ANORD_ID", "ANORD_NAMN", "TYP", "UNDERTYP"


@dataclass(frozen=True)
class SourceMetadata:
    """Provenance of the two registers."""

    name: str = "Naturvårdsregistret and Leder och friluftsanordningar"
    provider: str = "Naturvårdsverket"
    country: str = "SE"
    url: str = BASE_URL
    license: str = "CC0 1.0"
    attribution: str = "© Naturvårdsverket"
    update_frequency: str = "daily"


METADATA = SourceMetadata()


def form_label(value: object) -> str:
    """Say what a protection form is in the words a sign uses.

    Args:
        value: What the register's ``SKYDDSTYP`` column says

    Returns:
        The English words, or the register's own value where none are known
    """
    return FORM_LABELS.get(str(value), str(value))


def _file_date(path: Path) -> str | None:
    """Read the date a zipped delivery was written, off its newest entry.

    The server rewrites the files every night and says so only in the listing,
    which the download does not keep; the entries inside carry the same date.

    Args:
        path: The archive

    Returns:
        ``YYYY-MM-DD``, or None where the archive holds nothing
    """
    with zipfile.ZipFile(path) as archive:
        stamps = [datetime(*info.date_time) for info in archive.infolist()]
    return max(stamps).strftime("%Y-%m-%d") if stamps else None


class Source:
    """The two registers, read out of their nightly files."""

    def __init__(self, cache_dir: str | Path = ".cache", timeout: int = 300):
        """Point at the files.

        Args:
            cache_dir: Root cache directory; the archives go under
                ``naturvardsregistret`` in it
            timeout: Seconds the server may go quiet for
        """
        self.downloads = cache.Download(cache_dir=str(Path(cache_dir) / "naturvardsregistret"), timeout=timeout)
        #: The date each file read so far was written, by its name in the
        #: listing. What an exported file records as the register's version.
        self.versions: dict[str, str | None] = {}

    def _archive(self, relative: str, force_download: bool = False) -> Path:
        name = relative.rsplit("/", 1)[-1]
        path = self.downloads.download(f"{BASE_URL}/{relative}", filename=name, force=force_download).path
        self.versions[relative] = _file_date(path)
        return path

    def _read(self, relative: str, layer: str, bounds: Bounds, force_download: bool = False) -> gpd.GeoDataFrame:
        archive = self._archive(relative, force_download)
        box = project_bounds(bounds, "EPSG:4326", CRS)
        # The inner name is looked up rather than assumed: the trail archives
        # carry three shapefiles side by side, the area archives one in a folder.
        with zipfile.ZipFile(archive) as opened:
            inner = next(name for name in opened.namelist() if name.endswith(layer))
        read = pyogrio.read_dataframe(f"/vsizip/{archive}/{inner}", bbox=box)
        placed: gpd.GeoDataFrame = read.set_crs(CRS, allow_override=True).to_crs("EPSG:4326")
        return placed

    def areas(self, bounds: Bounds, forms: tuple[str, ...] = tuple(FORMS), force_download: bool = False) -> gpd.GeoDataFrame:
        """Every protected area over a box, whole.

        Args:
            bounds: The box, WGS 84
            forms: Which of :data:`FORMS` to read, by file code
            force_download: Fetch the files again rather than reading the cache

        Returns:
            The areas meeting the box, in WGS 84, with :data:`AREA_ID`,
            :data:`AREA_NAME`, :data:`AREA_FORM` and :data:`AREA_FIELDS`,
            ordered by id so two reads list them alike
        """
        frames = [self._read(f"naturvardsregistret/{code}.zip", f"{code}_polygon.shp", bounds, force_download) for code in forms]
        columns = [AREA_ID, AREA_NAME, AREA_FORM, *AREA_FIELDS, "geometry"]
        kept = [frame[columns] for frame in frames if len(frame)]
        if not kept:
            return gpd.GeoDataFrame({column: [] for column in columns[:-1]}, geometry=[], crs="EPSG:4326")
        joined = gpd.GeoDataFrame(gpd.pd.concat(kept, ignore_index=True), geometry="geometry", crs="EPSG:4326")
        return joined.sort_values(AREA_ID).reset_index(drop=True)

    def find_one(self, name: str, form: str = NATIONAL_PARK, exact: bool = False, force_download: bool = False) -> gpd.GeoDataFrame:
        """Find exactly one protected area by name.

        Args:
            name: What it is called, or part of that
            form: Which form to look among, as the register spells it
            exact: Require the whole name rather than a part
            force_download: Fetch the file again rather than reading the cache

        Returns:
            One row, in WGS 84

        Raises:
            LookupError: If nothing matches, or more than one thing does
        """
        code = next(code for code, spelled in FORMS.items() if spelled == form)
        archive = self._archive(f"naturvardsregistret/{code}.zip", force_download)
        with zipfile.ZipFile(archive) as opened:
            inner = next(entry for entry in opened.namelist() if entry.endswith(f"{code}_polygon.shp"))
        every = pyogrio.read_dataframe(f"/vsizip/{archive}/{inner}").set_crs(CRS, allow_override=True)
        names = every[AREA_NAME].astype(str)
        hits = every[names.str.casefold() == name.casefold()] if exact else every[names.str.contains(name, case=False, regex=False)]
        if not len(hits):
            raise LookupError(f"no {form_label(form)} matches '{name}'")
        if len(hits) > 1:
            raise LookupError(f"'{name}' is ambiguous among the {form_label(form)}s, matched {len(hits)}: {', '.join(hits[AREA_NAME].astype(str))}")
        found: gpd.GeoDataFrame = hits.reset_index(drop=True).to_crs("EPSG:4326")
        return found

    def trails(self, bounds: Bounds, force_download: bool = False) -> gpd.GeoDataFrame:
        """Every registered trail over a box, summer and winter alike.

        Args:
            bounds: The box, WGS 84
            force_download: Fetch the file again rather than reading the cache

        Returns:
            The trails meeting the box, in WGS 84, with every column the
            register writes
        """
        return self._read(TRAILS_FILE, TRAILS_LAYER, bounds, force_download)

    def facilities(self, bounds: Bounds, force_download: bool = False) -> gpd.GeoDataFrame:
        """Every registered facility over a box: bridges, shelters, privies.

        Args:
            bounds: The box, WGS 84
            force_download: Fetch the file again rather than reading the cache

        Returns:
            The facilities in the box, in WGS 84
        """
        return self._read(FACILITIES_FILE, FACILITIES_LAYER, bounds, force_download)
