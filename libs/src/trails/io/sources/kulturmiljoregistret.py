"""Riksantikvarieämbetet's *Kulturmiljöregistret*: every registered remain in Sweden, typed.

The register behind Fornsök. What a walking map wants from it is the places
people left -- a *Fäbod*, a *Bytomt/gårdstomt*, a *Kåta*, a *Viste*, a house
foundation from historic time (:data:`DWELLING_TYPES`) -- which is the Swedish
counterpart of the Norwegian register's ``gammelBosettingsplass``
(:mod:`trails.io.sources.stedsnavn`). Sweden's open place-name file has no
such word: thirteen coarse classes and none of them for a place left.

**One GeoPackage per county, rebuilt nightly, CC0.** Measured 2026-09-18:
the portal's DCAT entry marks the county and national downloads with
``creativecommons.org/publicdomain/zero/1.0/``, the publisher's own FAQ says
*"fria att använda men ange gärna Riksantikvarieämbetet som källa"* and asks
for the form *Riksantikvarieämbetets Kulturmiljöregister. ÅÅÅÅ-MM-DD*, and
the file for Norrbotten was 113 MB written at 03:14 that morning. The INSPIRE
feed beside it is not this file: 348,377 sites under the *Protected Sites*
schema, which carries a name and a date and no remains type at all.

**Several points per remain.** The point layer holds a geometry per
``geometrinummer``, so one house foundation can be fifteen rows -- 219 rows
for 178 remains over the Abisko box. Read once per ``uuid``.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
import requests

from trails.utils.geo import project_bounds
from trails.utils.tiles import Bounds

#: Where the county files are, as the portal's DCAT distributions name them.
#: The county goes in lower-case Swedish, as the file is named.
FILE_URL = "https://pub.raa.se/nedladdning/datauttag/lamningar_v1/lan/l%C3%A4mningar_l%C3%A4n_{county}.gpkg"

#: The portal that lists the files, for anyone checking the address.
PORTAL_URL = "https://pub.raa.se/"

#: What the GeoPackage is delivered in, and how its layers are named.
CRS = "EPSG:3006"
POINT_LAYER = "lämningar_län_{county}_point"

#: The register's own columns this reads.
ID, TYPE, NAME, DESCRIPTION, ASSESSMENT, URL = "uuid", "lamningstyp", "lamningsnamn", "beskrivning", "antikvariskbedomning", "url"

#: The remains types that are a place somebody lived at and nobody does now:
#: farmsteads, crofts and summer farms, a Sámi hut or camp, a hut's foundation
#: from historic time, a Sámi hut ring. Read off the register's 169-type
#: vocabulary on 2026-09-18 (Fornsök's ``api/lamning/domaner``). *Boplats* is
#: left out: it is a Stone Age site, which is a different question.
DWELLING_TYPES = (
    "Bytomt/gårdstomt",
    "Fäbod",
    "Lägenhetsbebyggelse",
    "Husgrund, historisk tid",
    "Kåta",
    "Viste",
    "Stalotomt",
)

#: What the register's words mean, in English. The types a walking map draws
#: and the ones it meets beside them; a type not here passes through as the
#: register spells it, visible rather than hidden.
TYPE_LABELS = {
    "Bytomt/gårdstomt": "farmstead site",
    "Fäbod": "summer farm (fäbod)",
    "Lägenhetsbebyggelse": "croft site",
    "Husgrund, historisk tid": "house foundation, historic",
    "Husgrund, förhistorisk/medeltida": "house foundation, prehistoric or medieval",
    "Kåta": "Sámi hut site (kåta)",
    "Viste": "Sámi settlement site (viste)",
    "Stalotomt": "stalo foundation",
    "Boplats": "Stone Age site",
    "Härd": "hearth",
    "Fångstgrop": "trapping pit",
    "Förvaringsanläggning": "storage structure",
    "Renvall": "reindeer pen site",
    "Samlingsplats": "gathering place",
    "Offerplats": "offering place",
    "Fyndplats": "find spot",
}

#: The register's antiquarian assessment, in English. *Fornlämning* is the
#: legally protected kind; the rest are recorded and not protected.
ASSESSMENT_LABELS = {
    "Fornlämning": "ancient monument, protected",
    "Möjlig fornlämning": "possible ancient monument",
    "Övrig kulturhistorisk lämning": "other cultural remain",
    "Ingen antikvarisk bedömning": "not assessed",
    "Ej kulturhistorisk lämning": "not a cultural remain",
    "Uppgift om lämning, ej bekräftad i fält": "reported, not confirmed in the field",
}


#: The values the tables did not know, as they passed through.
UNTRANSLATED: set[str] = set()


def type_label(value: object) -> str:
    """Say what a remains type is, in English; the register's word where none is known."""
    text = str(value)
    if text not in TYPE_LABELS:
        UNTRANSLATED.add(text)
    return TYPE_LABELS.get(text, text)


def assessment_label(value: object) -> str:
    """Say what an assessment means, in English; the register's word where none is known."""
    text = str(value)
    if text not in ASSESSMENT_LABELS:
        UNTRANSLATED.add(text)
    return ASSESSMENT_LABELS.get(text, text)


#: Seconds the download may take: a county is a hundred megabytes.
TIMEOUT_S = 600

#: How the download names itself to the far end.
USER_AGENT = "trails-analysis/0.1 (+https://github.com/ueisele/trails)"


@dataclass(frozen=True)
class SourceMetadata:
    """Provenance of the remains."""

    name: str = "Kulturmiljöregistret"
    provider: str = "Riksantikvarieämbetet"
    country: str = "SE"
    url: str = "https://www.raa.se/hitta-information/fornsok/"
    license: str = "CC0 1.0"
    attribution: str = "Riksantikvarieämbetets Kulturmiljöregister"
    update_frequency: str = "daily"


METADATA = SourceMetadata()


def _file_date(path: Path) -> str:
    """The day a file on disk was written, as the register asks to be cited by."""
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")


class Source:
    """One county's remains, one file on disk, read by box."""

    def __init__(self, county: str, cache_dir: str | Path = ".cache", timeout: int = TIMEOUT_S):
        """Point at a county's file.

        Args:
            county: The county as the file names it -- ``norrbotten``
            cache_dir: Root cache directory; the file goes under ``kulturmiljoregistret``
            timeout: Seconds the download may take
        """
        self.county = county.lower()
        self.cache_dir = Path(cache_dir) / "kulturmiljoregistret"
        self.timeout = timeout
        #: The day the file on disk was written, once one has been read.
        self.version: str | None = None

    @property
    def geopackage(self) -> Path:
        """Where the county's file is kept."""
        return self.cache_dir / f"lamningar_lan_{self.county}.gpkg"

    def fetch(self, force_download: bool = False) -> Path:
        """Have the file on disk, fetching it if it is not.

        Args:
            force_download: Fetch it again even if it is there

        Returns:
            The GeoPackage
        """
        if self.geopackage.exists() and not force_download:
            self.version = _file_date(self.geopackage)
            return self.geopackage
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        url = FILE_URL.format(county=self.county)
        print(f"Fetching {METADATA.name} for {self.county} ({url})...", flush=True)
        # Through a part file: a stop mid-download must not leave the final
        # name on a short file that the next build would read as the county.
        partial = self.geopackage.with_name(self.geopackage.name + ".part")
        with requests.get(url, timeout=self.timeout, stream=True, headers={"User-Agent": USER_AGENT}) as response:
            response.raise_for_status()
            with partial.open("wb") as sink:
                for chunk in response.iter_content(16 * 1024 * 1024):
                    sink.write(chunk)
        partial.replace(self.geopackage)
        self.version = _file_date(self.geopackage)
        print(f"  {self.geopackage.stat().st_size / 1e6:,.0f} MB, written {self.version}", flush=True)
        return self.geopackage

    def remains(self, bounds: Bounds, types: tuple[str, ...] | None = DWELLING_TYPES, force_download: bool = False) -> gpd.GeoDataFrame:
        """Every remain over a box, of the types asked for, once each.

        Args:
            bounds: The box, WGS 84
            types: Which ``lamningstyp`` values to keep; None for all of them
            force_download: Fetch the file again first

        Returns:
            Points in WGS 84 with ``remain_id``, ``name`` (None where the
            register has none), ``kind`` (the remains type as the register
            spells it) and ``kind_label`` (in English), ``description`` (the
            register's own text, Swedish), ``assessment`` and
            ``assessment_label``, and ``url`` (the remain's own page on Fornsök)
        """
        path = self.fetch(force_download)
        box = project_bounds(bounds, "EPSG:4326", CRS)
        read = pyogrio.read_dataframe(path, layer=POINT_LAYER.format(county=self.county), bbox=box)
        if types is not None:
            read = read[read[TYPE].isin(types)]
        # One row per remain: the first of its geometries is the one the
        # register lists first, which is where its own page puts the marker.
        read = read.drop_duplicates(ID)
        out = gpd.GeoDataFrame(read, geometry="geometry", crs=CRS).to_crs("EPSG:4326").reset_index(drop=True)
        out["remain_id"] = out[ID].astype(str)
        # A list and not `where`, which writes NaN for what it leaves out: a
        # remain with no name has None, the one value JSON and the page agree on.
        out["name"] = pd.Series([text if isinstance(text, str) and text.strip() else None for text in out[NAME]], index=out.index, dtype=object)
        out["kind"] = out[TYPE].astype(str)
        out["kind_label"] = out["kind"].map(type_label)
        out["description"] = out[DESCRIPTION]
        out["assessment"] = out[ASSESSMENT]
        out["assessment_label"] = out["assessment"].map(assessment_label)
        return out[["remain_id", "name", "kind", "kind_label", "description", "assessment", "assessment_label", URL, "geometry"]]
