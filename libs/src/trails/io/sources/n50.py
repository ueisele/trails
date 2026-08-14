"""N50 Kartdata (Kartverket's 1:50 000 base map) via the Geonorge order API.

N50 is the dataset behind Kartverket's printed and online topographic maps. Its
``Samferdsel`` (transport) theme carries the terrain paths — ``sti`` and
``traktorveg`` — that make up most of the trail network drawn on a topo map.

This matters because Turrutebasen only holds *organised* routes: waymarked and
maintained by some body. Unmarked paths visible on the topo map are absent from
it but present here::

    codes = kommuneinfo.Source().intersecting(area, fylke=("18",))
    paths = n50.Source().load_paths(codes)

N50 is distributed per municipality, so a download starts by placing an order
with Geonorge. Orders are skipped entirely when every file is already cached.
"""

from dataclasses import dataclass

import geopandas as gpd
import pandas as pd

from ..cache import Download as DownloadCache
from ..cache import Object as ObjectCache
from .geonorge_order import KommuneOrderClient, OrderedFile

#: Geonorge catalogue entry for N50 Kartdata.
METADATA_UUID = "ea192681-d039-42ec-b1bc-f3ce04c189ac"

#: Layer holding roads, tracks and paths.
TRANSPORT_LAYER = "N50_Samferdsel_senterlinje"

#: Layers holding buildings, as points and as outlines.
BUILDING_LAYERS = ("N50_BygningerOgAnlegg_posisjon", "N50_BygningerOgAnlegg_omrade")

#: Matrikkel building-type codes for huts out in the terrain, mapped to a label.
#: Wilderness huts often carry neither a name nor a service level in N50, so the
#: type code is the only thing marking them as something a hiker can shelter in.
WILDERNESS_BUILDING_TYPES = {
    171.0: "Seterhus, sel, rorbu",
    172.0: "Skogs- og utmarkskoie, gamme",
}

#: ``typeveg`` values that a walker can actually use.
WALKABLE_ROAD_TYPES = ("sti", "traktorveg", "gangOgSykkelveg", "barmarksløype")

#: ``typeveg`` values describing ferry crossings.
FERRY_ROAD_TYPES = ("bilferje", "passasjerferje")

#: ``typeveg`` values a car can drive. N50 makes no finer distinction than this
#: at 1:50 000; what separates a motorway from a forest track is ``vegkategori``.
CAR_ROAD_TYPES = ("enkelBilveg",)

#: ``vegkategori`` codes, expanded. The distinction that matters on a hiking map
#: is P against the rest: a private road is the last stretch to a trailhead,
#: everything else is a public road the topographic backdrop already draws.
ROAD_CATEGORIES = {
    "E": "Europaveg",
    "R": "Riksveg",
    "F": "Fylkesveg",
    "K": "Kommunal veg",
    "P": "Privat veg",
}

#: The ``vegkategori`` code for privately maintained roads.
PRIVATE_ROAD_CATEGORY = "P"

#: Layer holding the place-name labels drawn on the topographic map.
PLACE_NAME_LAYER = "N50_Stedsnavn_tekstplassering"

#: Columns read from the place-name layer. Reading it whole trips over
#: undecodable bytes in the cartographic styling columns.
PLACE_NAME_COLUMNS = ("fulltekst", "navneobjekttype", "navneobjektgruppe")

#: Terrain feature types worth labelling on a hiking map. Excludes the very
#: common small features (bekk, haug, ås) that would swamp the map.
TERRAIN_NAME_TYPES = ("dal", "skar", "fjell", "vann", "tjern", "seter", "gard", "grend", "isbre", "foss", "li")


@dataclass(frozen=True)
class SourceMetadata:
    """Provenance of the N50 data."""

    name: str = "N50 Kartdata"
    provider: str = "Kartverket"
    country: str = "NO"
    url: str = "https://kartkatalog.geonorge.no/metadata/ea192681-d039-42ec-b1bc-f3ce04c189ac"
    license: str = "CC BY 4.0"
    attribution: str = "© Kartverket"


METADATA = SourceMetadata()


class Source:
    """Loader for N50 Kartdata, ordered per municipality from Geonorge."""

    def __init__(self, cache_dir: str = ".cache", timeout: int = 600):
        """Initialize the N50 source.

        Args:
            cache_dir: Root directory for caching data
            timeout: HTTP timeout in seconds
        """
        self.cache = ObjectCache(f"{cache_dir}/objects")
        self.downloads = DownloadCache(f"{cache_dir}/downloads")
        self.timeout = timeout
        self.orders = KommuneOrderClient(METADATA_UUID, "n50", self.downloads, timeout=timeout)

    def order(self, kommune_codes: list[str]) -> list[OrderedFile]:
        """Place a Geonorge order and return the resulting download links.

        Args:
            kommune_codes: Municipality numbers to order, e.g. ``["1824"]``

        Returns:
            One entry per file the order made available
        """
        return self.orders.order(kommune_codes)

    def fetch(self, kommune_codes: list[str], force_download: bool = False) -> dict[str, str]:
        """Ensure each municipality's N50 archive is present in the cache.

        Args:
            kommune_codes: Municipality numbers to fetch
            force_download: Re-order and re-download even if cached

        Returns:
            Mapping of municipality number to local archive path
        """
        return self.orders.fetch(kommune_codes, force_download=force_download)

    def load_layers(self, kommune_codes: list[str], layers: tuple[str, ...], force_download: bool = False) -> gpd.GeoDataFrame:
        """Load and concatenate N50 layers across several municipalities.

        Args:
            kommune_codes: Municipality numbers to load
            layers: Layer names to read from each municipality's geodatabase
            force_download: Re-order and re-download even if cached

        Returns:
            GeoDataFrame in EPSG:4326 with ``kommune`` and ``layer`` columns added

        Raises:
            ValueError: If an archive contains no file geodatabase
        """
        codes = sorted(kommune_codes)
        cache_key = f"n50_{'+'.join(layers)}_{'-'.join(codes)}"

        if not force_download and self.cache.exists(cache_key):
            print(f"Loading N50 {', '.join(layers)} from cache...")
            cached = self.cache.load(cache_key)
            assert isinstance(cached, gpd.GeoDataFrame)
            return cached

        archives = self.fetch(codes, force_download=force_download)

        frames = []
        for code, archive in archives.items():
            layer_path = f"/vsizip/{archive}/{_find_gdb(archive)}"
            for layer in layers:
                print(f"Reading {layer} for municipality {code}...")
                frame = gpd.read_file(layer_path, layer=layer)
                frame["kommune"] = code
                frame["layer"] = layer
                frames.append(frame.to_crs("EPSG:4326"))

        merged = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")
        print(f"Loaded {len(merged):,} N50 features")

        self.cache.save(cache_key, merged, metadata={"kommune_codes": codes, "layers": list(layers), "count": len(merged)})
        return merged

    def load_place_names(
        self,
        kommune_codes: list[str],
        name_types: tuple[str, ...] | None = TERRAIN_NAME_TYPES,
        force_download: bool = False,
    ) -> gpd.GeoDataFrame:
        """Load the place-name labels the topographic map draws.

        These are the same names, in the same positions, that appear on
        Kartverket's topo base map, so labels drawn from here line up with the
        backdrop instead of floating beside it the way independently surveyed
        OpenStreetMap nodes can.

        Note that an extended feature such as a valley gets a single label
        position chosen for cartographic reasons; it marks the feature, not a
        point you can walk to.

        Args:
            kommune_codes: Municipality numbers to load
            name_types: ``navneobjekttype`` values to keep, or None for all
            force_download: Re-order and re-download even if cached

        Returns:
            GeoDataFrame in EPSG:4326 with Point geometries and the columns
            ``name``, ``kind`` and ``kommune``
        """
        codes = sorted(kommune_codes)
        cache_key = f"n50_placenames_{'-'.join(codes)}"

        if not force_download and self.cache.exists(cache_key):
            print("Loading N50 place names from cache...")
            labels = self.cache.load(cache_key)
            assert isinstance(labels, gpd.GeoDataFrame)
        else:
            archives = self.fetch(codes, force_download=force_download)

            frames = []
            for code, archive in archives.items():
                print(f"Reading {PLACE_NAME_LAYER} for municipality {code}...")
                frame = gpd.read_file(f"/vsizip/{archive}/{_find_gdb(archive)}", layer=PLACE_NAME_LAYER, columns=list(PLACE_NAME_COLUMNS))
                frame["kommune"] = code
                frames.append(frame.to_crs("EPSG:4326"))

            merged = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")
            merged["geometry"] = merged.geometry.representative_point()
            labels = gpd.GeoDataFrame(
                merged.rename(columns={"fulltekst": "name", "navneobjekttype": "kind"})[["name", "kind", "kommune", "geometry"]],
                geometry="geometry",
                crs="EPSG:4326",
            )
            print(f"Loaded {len(labels):,} N50 place names")
            self.cache.save(cache_key, labels, metadata={"kommune_codes": codes, "count": len(labels)})

        if name_types is not None:
            labels = labels[labels["kind"].isin(name_types)].reset_index(drop=True)
            print(f"  of which terrain names ({len(name_types)} types): {len(labels):,}")

        return gpd.GeoDataFrame(labels, geometry="geometry", crs="EPSG:4326")

    def load_transport(self, kommune_codes: list[str], force_download: bool = False) -> gpd.GeoDataFrame:
        """Load the N50 transport network for several municipalities.

        Args:
            kommune_codes: Municipality numbers to load
            force_download: Re-order and re-download even if cached

        Returns:
            GeoDataFrame in EPSG:4326 with a ``kommune`` column added
        """
        return self.load_layers(kommune_codes, (TRANSPORT_LAYER,), force_download=force_download)

    def load_cabins(self, kommune_codes: list[str], force_download: bool = False) -> gpd.GeoDataFrame:
        """Load cabins, rest huts and lean-tos out in the terrain.

        A building qualifies either because it carries ``betjeningsgrad`` (a
        service level, which ordinary buildings leave empty) or because its
        ``bygningstype`` is one of the wilderness hut codes. Both are needed:
        named DNT-style cabins tend to have the service level, while unlocked
        wilderness huts often have only the type code — Sæterskardhytta inside
        Lomsdal-Visten is in N50 solely as an unnamed ``172``.

        Buildings mapped as outlines are reduced to a representative point so
        cabins from both N50 building layers can share one layer.

        Args:
            kommune_codes: Municipality numbers to load
            force_download: Re-order and re-download even if cached

        Returns:
            GeoDataFrame in EPSG:4326 with Point geometries and the columns
            ``navn``, ``kind``, ``betjeningsgrad``, ``hytteeier`` and ``kommune``.
            ``kind`` falls back to the building type when no service level is set.
        """
        buildings = self.load_layers(kommune_codes, BUILDING_LAYERS, force_download=force_download)

        is_cabin = buildings["betjeningsgrad"].notna() | buildings["bygningstype"].isin(WILDERNESS_BUILDING_TYPES)
        cabins = buildings[is_cabin].copy()
        cabins["geometry"] = cabins.geometry.representative_point()
        cabins["kind"] = cabins["betjeningsgrad"].fillna(cabins["bygningstype"].map(WILDERNESS_BUILDING_TYPES))

        result = gpd.GeoDataFrame(
            cabins[["navn", "kind", "betjeningsgrad", "hytteeier", "kommune", "geometry"]].reset_index(drop=True),
            geometry="geometry",
            crs="EPSG:4326",
        )
        named = int(result["navn"].notna().sum())
        print(f"  of which cabins and wilderness huts: {len(result):,} ({named} named)")
        return result

    def load_paths(
        self,
        kommune_codes: list[str],
        road_types: tuple[str, ...] = WALKABLE_ROAD_TYPES,
        force_download: bool = False,
    ) -> gpd.GeoDataFrame:
        """Load only the walkable parts of the N50 transport network.

        Args:
            kommune_codes: Municipality numbers to load
            road_types: ``typeveg`` values to keep
            force_download: Re-order and re-download even if cached

        Returns:
            GeoDataFrame in EPSG:4326 restricted to the requested road types
        """
        return self._load_by_type(kommune_codes, road_types, "walkable", force_download=force_download)

    def load_ferries(
        self,
        kommune_codes: list[str],
        road_types: tuple[str, ...] = FERRY_ROAD_TYPES,
        force_download: bool = False,
    ) -> gpd.GeoDataFrame:
        """Load ferry connections from the N50 transport network.

        On the Norwegian coast ferries are often the only way to reach a
        trailhead, so they belong on a hiking map even though nobody walks them.

        Args:
            kommune_codes: Municipality numbers to load
            road_types: ``typeveg`` values to keep
            force_download: Re-order and re-download even if cached

        Returns:
            GeoDataFrame in EPSG:4326 restricted to the requested ferry types
        """
        return self._load_by_type(kommune_codes, road_types, "ferries", force_download=force_download)

    def load_roads(
        self,
        kommune_codes: list[str],
        road_types: tuple[str, ...] = CAR_ROAD_TYPES,
        force_download: bool = False,
    ) -> gpd.GeoDataFrame:
        """Load the drivable road network.

        A hiking map needs these for the approach: every trip starts at a road
        end. N50 carries no road names at all, so the returned frame has only
        ``vegkategori`` to tell a forest track from a trunk road — see
        :mod:`trails.io.sources.stedsnavn` for the names.

        Args:
            kommune_codes: Municipality numbers to load
            road_types: ``typeveg`` values to keep
            force_download: Re-order and re-download even if cached

        Returns:
            GeoDataFrame in EPSG:4326 with a ``road_category`` column holding the
            expanded :data:`ROAD_CATEGORIES` label
        """
        roads = self._load_by_type(kommune_codes, road_types, "car roads", force_download=force_download)
        roads["road_category"] = roads["vegkategori"].map(ROAD_CATEGORIES).fillna(roads["vegkategori"])
        return roads

    def _load_by_type(
        self,
        kommune_codes: list[str],
        road_types: tuple[str, ...],
        label: str,
        force_download: bool = False,
    ) -> gpd.GeoDataFrame:
        """Load the transport network and keep only certain ``typeveg`` values.

        Args:
            kommune_codes: Municipality numbers to load
            road_types: ``typeveg`` values to keep
            label: Word used in the progress line
            force_download: Re-order and re-download even if cached

        Returns:
            GeoDataFrame in EPSG:4326 restricted to the requested road types
        """
        transport = self.load_transport(kommune_codes, force_download=force_download)
        selected = transport[transport["typeveg"].isin(road_types)].reset_index(drop=True)
        print(f"  of which {label} ({', '.join(road_types)}): {len(selected):,}")
        return gpd.GeoDataFrame(selected, geometry="geometry", crs="EPSG:4326")


def _find_gdb(archive: str) -> str:
    """Locate the file geodatabase directory inside an N50 archive.

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
