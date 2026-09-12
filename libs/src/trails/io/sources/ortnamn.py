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
import shutil
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import pyogrio
from shapely.strtree import STRtree

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

#: How far apart the register puts two languages' points for one place. Measured
#: over the Abisko box on 2026-09-12: the real pairs -- Abiskojåkka / Ábeskoeatnu
#: 46 m, Torneträsk / Duortnosjávri 80–148 m, Lapporten / Čuonjávággi 87 m,
#: Trollsjön / Geargejávri 240 m (though the register calls that lake Geargejávri
#: in Swedish too, so the two stay two names -- same language, never joined),
#: Katterjåkk / Gátterjohka 249 m, Abisko / Ábeskovvu 412 m -- and the first pair
#: that is two different places at 637 m.
#: One real pair sits beyond it, Gorsajökeln / Gorsajiekŋa at 619 m, and stays
#: two names rather than risk joining two lakes.
PAIR_M = 500.0

#: Which language names a place first where the register has several: Swedish,
#: because it is what the trail signs and the sheets' larger lettering carry;
#: the Sámi languages after it, as the file lists them.
LANGUAGE_ORDER = tuple(LANGUAGES)

#: Where two names are measured against each other.
METRIC_CRS = "EPSG:3006"


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


def label(name: object, also: object) -> str:
    """One place's names as a label: the first, and the others in brackets.

    Args:
        name: The name in the first language
        also: The other languages' names, joined; empty or None for none

    Returns:
        ``Abiskojåkka (Ábeskoeatnu)``, or the name alone
    """
    return f"{name} ({also})" if isinstance(also, str) and also else str(name)


def paired(names: gpd.GeoDataFrame, within_m: float = PAIR_M, metric_crs: str = METRIC_CRS) -> gpd.GeoDataFrame:
    """One row per place, where the register has a place in several languages.

    **The register carries each language as a point of its own**, and they do
    not coincide: the Sámi name of a river sits 46 m from the Swedish one, a
    lake's names up to a few hundred metres apart. Read as they are, a map
    draws two labels a finger apart and names a river by whichever point lies
    nearer. This joins them: a point of a later language (:data:`LANGUAGE_ORDER`)
    within ``within_m`` of an earlier one **of the same type** becomes that
    place's other name. Two points in the *same* language are never joined --
    two lakes 300 m apart are two lakes -- and a name spelt the same in both
    languages is one name.

    Args:
        names: What :meth:`Source.names` returned
        within_m: How far apart one place's points may lie, see :data:`PAIR_M`
        metric_crs: The projection the distance is measured in

    Returns:
        The rows kept, in the input's CRS and column set, with ``name`` the
        first language's, ``also`` the others' joined by ``", "`` (empty for
        none) and ``languages`` every language the place has, joined
    """
    if names.empty:
        out = names.copy()
        out["also"] = pd.Series(dtype="string")
        out["languages"] = pd.Series(dtype="string")
        return out
    order = {code: rank for rank, code in enumerate(LANGUAGE_ORDER)}
    metric = names.to_crs(metric_crs)
    ranked = sorted(range(len(names)), key=lambda i: (order.get(str(names[LANGUAGE].iloc[i]), len(order)), i))
    kept: list[int] = []
    kept_geoms: list[Any] = []
    also: dict[int, list[str]] = {}
    languages: dict[int, list[str]] = {}
    trees: dict[str, tuple[STRtree, list[int]]] = {}
    for i in ranked:
        kind, code, text = str(names[TYPE].iloc[i]), str(names[LANGUAGE].iloc[i]), str(names[NAME].iloc[i])
        point = metric.geometry.iloc[i]
        joined_to = None
        if kind in trees:
            # **The nearest head, not the first the tree returns.** A query
            # answers in the tree's own order, which has nothing to do with
            # distance; a point within reach of two heads used to join
            # whichever GEOS listed first. Every candidate is measured and the
            # closest taken -- a head that already carries this language is
            # not a candidate at all.
            tree, members = trees[kind]
            nearest = None
            for hit in tree.query(point.buffer(within_m)):
                head = members[hit]
                if code in languages[head]:
                    continue
                away = kept_geoms[kept.index(head)].distance(point)
                if away <= within_m and (nearest is None or away < nearest):
                    joined_to, nearest = head, away
        if joined_to is None:
            kept.append(i)
            kept_geoms.append(point)
            also[i] = []
            languages[i] = [code]
            members = [k for k in kept if str(names[TYPE].iloc[k]) == kind]
            trees[kind] = (STRtree([kept_geoms[kept.index(k)] for k in members]), members)
            continue
        languages[joined_to].append(code)
        head_text = str(names[NAME].iloc[joined_to])
        if text.casefold() != head_text.casefold() and text not in also[joined_to]:
            also[joined_to].append(text)
    out = names.iloc[kept].copy()
    out["also"] = [", ".join(also[i]) for i in kept]
    out["languages"] = [", ".join(language_label(code) for code in languages[i]) for i in kept]
    return out.reset_index(drop=True)


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
                # Through a part file, as the delivery reader does: a stop
                # mid-extract must not leave the final name on a short file.
                target.parent.mkdir(parents=True, exist_ok=True)
                partial = target.with_name(target.name + ".part")
                with opened.open(inner) as source, partial.open("wb") as sink:
                    shutil.copyfileobj(source, sink, 16 * 1024 * 1024)
                partial.replace(target)
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
