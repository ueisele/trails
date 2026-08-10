"""Place names from Norway's official register (SSR) via the Geonorge order API.

The register records where a name applies, not where a dot should go. Extended
features such as valleys and rivers are stored as a *MultiPoint*: several
positions along the feature. Half of them are near-coincident duplicates from
alternative spellings, so points are collapsed within a tolerance before use.

Nothing here invents geometry. The register offers no outline for a valley or a
mountain, and a hull drawn through two sampled points would be an invention, so
callers get the positions the register actually asserts::

    source = Source()
    names = source.load_places(codes, name_types=("dal", "skar", "fjell"))
"""

from dataclasses import dataclass

import geopandas as gpd
import pandas as pd

from ..cache import Download as DownloadCache
from ..cache import Object as ObjectCache
from .geonorge_order import KommuneOrderClient

#: Geonorge catalogue entry for the per-municipality Stedsnavn distribution.
METADATA_UUID = "30caed2f-454e-44be-b5cc-26bb5c0110ca"

#: Geometry layers holding named places. Lines are almost entirely street names
#: and areas exist for only a handful of features, so neither is read here.
GEOMETRY_LAYERS = ("sted_posisjon", "sted_multipunkt")

#: Tables carrying the name text, joined to the geometry via ``lokalid``.
NAME_TABLE = "stedsnavn"
SPELLING_TABLE = "skrivemate"

#: Terrain feature types worth labelling on a hiking map.
TERRAIN_NAME_TYPES = ("dal", "skar", "fjell", "fjellområde", "vann", "tjern", "seter", "isbre", "foss", "elv", "li", "myr")

#: The register's own importance ranking, most prominent first. Useful for
#: deciding label size and which names to draw at all.
IMPORTANCE_ORDER = (
    "viktighetA",
    "viktighetB",
    "viktighetC",
    "viktighetD",
    "viktighetE",
    "viktighetF",
    "viktighetG",
    "viktighetH",
    "viktighetI",
    "viktighetJ",
    "viktighetK",
)


@dataclass(frozen=True)
class SourceMetadata:
    """Provenance of the place-name data."""

    name: str = "Stedsnavn (SSR)"
    provider: str = "Kartverket"
    country: str = "NO"
    url: str = "https://kartkatalog.geonorge.no/metadata/30caed2f-454e-44be-b5cc-26bb5c0110ca"
    license: str = "CC BY 4.0"
    attribution: str = "© Kartverket"


METADATA = SourceMetadata()


def importance_rank(value: object) -> int:
    """Turn an importance code into a sortable rank.

    Args:
        value: A ``sortering`` value such as ``"viktighetC"``

    Returns:
        Zero-based rank, most prominent first; unknown values rank last
    """
    try:
        return IMPORTANCE_ORDER.index(str(value))
    except ValueError:
        return len(IMPORTANCE_ORDER)


class Source:
    """Loader for Norwegian place names, ordered per municipality."""

    def __init__(self, cache_dir: str = ".cache", timeout: int = 600):
        """Initialize the place-name source.

        Args:
            cache_dir: Root directory for caching data
            timeout: HTTP timeout in seconds
        """
        self.cache = ObjectCache(f"{cache_dir}/objects")
        self.downloads = DownloadCache(f"{cache_dir}/downloads")
        self.orders = KommuneOrderClient(METADATA_UUID, "ssr", self.downloads, timeout=timeout)

    def _read_names(self, archive: str) -> pd.Series:
        """Read the main name text for each place in an archive.

        Args:
            archive: Path to a downloaded Stedsnavn archive

        Returns:
            Series mapping place id to its approved main spelling
        """
        layer_path = f"/vsizip/{archive}/{_find_gdb(archive)}"
        names = gpd.read_file(layer_path, layer=NAME_TABLE)
        spellings = gpd.read_file(layer_path, layer=SPELLING_TABLE)

        joined = spellings.merge(names[["objid", "sted_fk", "navnestatus"]], left_on="stedsnavn_fk", right_on="objid")
        main = joined[joined["navnestatus"] == "hovednavn"]
        return main.groupby("sted_fk")["komplettskrivemate"].first()

    def load_places(
        self,
        kommune_codes: list[str],
        name_types: tuple[str, ...] | None = TERRAIN_NAME_TYPES,
        dedupe_m: float = 50.0,
        force_download: bool = False,
    ) -> gpd.GeoDataFrame:
        """Load named places as individual points.

        MultiPoint features are exploded into one row per position, after
        collapsing positions that lie within ``dedupe_m`` of each other. Around
        half of them reduce to a single point that way; what survives is the set
        of places along a feature where the name genuinely applies, which is what
        a repeated label on a topographic map represents.

        Args:
            kommune_codes: Municipality numbers to load
            name_types: ``navneobjekttype`` values to keep, or None for all
            dedupe_m: Collapse tolerance in metres
            force_download: Re-order and re-download even if cached

        Returns:
            GeoDataFrame in EPSG:4326 with Point geometries and the columns
            ``name``, ``kind``, ``importance``, ``rank``, ``positions`` (how many
            distinct positions the name has) and ``kommune``
        """
        codes = sorted(kommune_codes)
        cache_key = f"ssr_places_{'-'.join(codes)}_{dedupe_m:g}"

        if not force_download and self.cache.exists(cache_key):
            print("Loading place names from cache...")
            places = self.cache.load(cache_key)
            assert isinstance(places, gpd.GeoDataFrame)
        else:
            archives = self.orders.fetch(codes, force_download=force_download)

            frames = []
            for code, archive in archives.items():
                names = self._read_names(archive)
                for layer in GEOMETRY_LAYERS:
                    print(f"Reading {layer} for municipality {code}...")
                    frame = gpd.read_file(f"/vsizip/{archive}/{_find_gdb(archive)}", layer=layer)
                    frame["name"] = frame["lokalid"].astype("int64").map(names)
                    frame["kommune"] = code
                    frames.append(frame[["name", "navneobjekttype", "sortering", "kommune", "geometry"]])

            merged = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)
            places = _explode_positions(merged, dedupe_m)
            places = places.rename(columns={"navneobjekttype": "kind", "sortering": "importance"})
            places["rank"] = places["importance"].map(importance_rank)
            places = gpd.GeoDataFrame(places.to_crs("EPSG:4326"), geometry="geometry", crs="EPSG:4326")

            print(f"Loaded {len(places):,} place-name positions")
            self.cache.save(cache_key, places, metadata={"kommune_codes": codes, "dedupe_m": dedupe_m, "count": len(places)})

        if name_types is not None:
            places = places[places["kind"].isin(name_types)].reset_index(drop=True)
            print(f"  of which terrain names: {len(places):,}")

        return gpd.GeoDataFrame(places, geometry="geometry", crs="EPSG:4326")


def _explode_positions(gdf: gpd.GeoDataFrame, dedupe_m: float) -> gpd.GeoDataFrame:
    """Split multi-position places into one row per distinct position.

    Args:
        gdf: Named places in a metric CRS, with point or multipoint geometries
        dedupe_m: Collapse tolerance in metres

    Returns:
        GeoDataFrame with Point geometries and a ``positions`` column counting
        how many distinct positions the place kept
    """
    named = gdf[gdf["name"].notna() & gdf.geometry.notna()].reset_index(drop=True)
    if named.empty:
        return gpd.GeoDataFrame(
            {column: [] for column in ("name", "navneobjekttype", "sortering", "kommune", "positions")},
            geometry=[],
            crs=gdf.crs,
        )

    exploded = named.explode(index_parts=False)
    exploded = exploded.reset_index(names="feature_index")

    # Snap to a grid so alternative spellings sharing a position collapse.
    grid_x = (exploded.geometry.x / dedupe_m).round().astype("int64")
    grid_y = (exploded.geometry.y / dedupe_m).round().astype("int64")
    exploded["cell"] = grid_x.astype(str) + "/" + grid_y.astype(str)

    deduped = exploded.drop_duplicates(subset=["feature_index", "cell"]).copy()
    deduped["positions"] = deduped["feature_index"].map(deduped.groupby("feature_index").size())

    columns = ["name", "navneobjekttype", "sortering", "kommune", "positions", "geometry"]
    return gpd.GeoDataFrame(deduped[columns].reset_index(drop=True), geometry="geometry", crs=gdf.crs)


def _find_gdb(archive: str) -> str:
    """Locate the file geodatabase directory inside an archive.

    Args:
        archive: Path to the downloaded ZIP file

    Returns:
        Name of the ``.gdb`` directory within the archive

    Raises:
        ValueError: If the archive holds no file geodatabase
    """
    import zipfile

    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.namelist():
            top = entry.split("/")[0]
            if top.endswith(".gdb"):
                return top
    raise ValueError(f"No .gdb found in {archive}")
