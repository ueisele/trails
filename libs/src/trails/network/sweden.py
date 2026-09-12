"""The walking network Sweden's three registers make between them.

The sibling of :mod:`trails.network.norway`, and a third of its size, because
Sweden's national map does in one product what Norway's does in four:
*Topografi 50* carries the worn paths, the marked trails, the roads, the
ferries and the fords; Naturvårdsverket's trail register carries what the
marked trails are called, how they are marked and which state trail they
belong to; OpenStreetMap carries what neither draws. Everything that is not
about which register says what — the fingerprint, the derived fields, the
build — is :mod:`trails.network.graphs`, shared with Norway.

Deliberately free of any one park, like its sibling: the extent arrives as a
clipping geometry, so a map and a graph report over the same ground hit the
same cache.

    >>> register = naturvardsregistret.Source(cache_dir=cache)
    >>> park = register.find_one("Abisko")
    >>> params = Params(cache_dir=cache)
    >>> zone = zone_around(park, params.approach_km)
    >>> loaded = load_sources(params, zone)
    >>> masks = masks_from(loaded.sources)
    >>> network, chains = build(loaded.sources, masks, zone, params, name="abisko", protected=loaded.protected)

**Winter trails are not routable** (decisions §6.5). The register separates
its trails by season and Topografi 50 by class, and both winter kinds are
kept out of the graph and handed back apart, for a legend row that is off by
default: a line over a frozen lake is nothing to walk in August.
"""

from dataclasses import dataclass
from typing import Any, NamedTuple

import geopandas as gpd
import pandas as pd

from trails.io.sources import markhojd, naturvardsregistret, overpass, topografi50
from trails.network import graphs
from trails.network.graphs import PROTECTED_SIMPLIFY_M, SURVEYED_FIELD, Masks, Rules
from trails.routing import DEFAULT_MARKED_M, DEFAULT_MIN_SHARE, DEFAULT_RECORDED_M, Network, NetworkSource, with_elevation
from trails.routing.noding import clip_lines
from trails.routing.sources import FERRY
from trails.utils.geo import attach_nearest

#: Metric CRS for Sweden: SWEREF 99 TM, which is what every register here is
#: delivered in. The routing module works in it, so every length and distance
#: below is already in metres.
METRIC_CRS = "EPSG:3006"

#: What each dataset is called, on every chain and every edge built from it, and
#: therefore also the prefix of its chain ids. A caller reading the chains back
#: has to spell them the same way.
LEDER = "Leder"
T50_TRAILS = "Topografi 50 trails"
T50_PATHS = "Topografi 50 paths"
T50_ROADS = "Topografi 50 roads"
OSM = "OSM"
FERRIES = "Ferries"

#: Every source, in the order :func:`load_sources` returns them.
SOURCE_NAMES = (LEDER, T50_TRAILS, T50_PATHS, T50_ROADS, OSM, FERRIES)

#: Cost factor per source, on the same scale as Norway's: an officially marked
#: route is a better thing to follow than a path that merely exists, and a
#: road is the last resort. Keep these close to 1.0, or a route makes real
#: detours to reach a preferred source.
COST_FACTORS = {
    LEDER: 1.02,
    # Between the register's line and Lantmäteriet's: the register describes
    # the trail, Lantmäteriet surveyed it, and the two lie within metres.
    T50_TRAILS: 1.05,
    T50_PATHS: 1.10,
    OSM: 1.20,
    T50_ROADS: 1.30,
}

#: The two classes of Topografi 50's *Övrig väg* that are marked trails —
#: ``Vandrings- och vinterled`` is Kungsleden's kind, marked with red crosses
#: for every season. **A source of their own, and not for taste.** Topografi
#: 50 draws the marked trail *and* the worn path under it as two objects on
#: one geometry: over Abisko 148 km are shared, in 6,570 collinear segments.
#: Noded as one source those cut each other at every vertex, and the identity
#: rule — every arm at such a cut carries the same trail name — ends a chain at
#: each one: 9,136 chains at 69 m instead of 470. As two sources they meet only
#: in the merged graph, exactly as Turrutebasen and FKB do in Norway.
TRAIL_CLASSES = ("Vandringsled", "Vandrings- och vinterled")

#: The classes of *Övrig väg* a walker uses that are not marked trails: the
#: worn path, and the three that are ways on foot whatever they were made for.
PATH_CLASSES = ("Gångstig", "Traktorväg", "Cykelväg", "Elljusspår")

#: The one *Övrig väg* class that is winter only, and the two of
#: *Transportled fjäll* — reindeer routes, boat drags, ski tracks — that are
#: ways on foot: a route Lantmäteriet judges suitable, and a path hard to find.
WINTER_CLASSES = ("Vinterled",)
MOUNTAIN_WALKED_CLASSES = ("Lämplig färdväg", "Svårorienterad gångstig")

#: Which path classes state that they are *not* marked: the worn path, the
#: suitable route and the hard-to-find path are what a walker finds without a
#: marking. The tractor road, the cycle path and the lit track say nothing
#: either way. The trail classes are marked by definition.
UNMARKED_CLASSES = ("Gångstig", "Lämplig färdväg", "Svårorienterad gångstig")

#: What a Topografi 50 path carries onto its chains: its class, whether it runs
#: over a bridge, whether snowmobiles may use it, whether it is brush-marked,
#: and when Lantmäteriet last wrote it.
PATH_ATTRIBUTES = (topografi50.TYPE, "vagutforande", "skoterkorning_tillaten", "ruskmarkering", SURVEYED_FIELD)

#: What a road carries: its class, its street name where it has one, and its
#: number. The number is also the identity: ``E10`` is one road across the box.
ROAD_NUMBER = "vardvagnummer"
ROAD_ATTRIBUTES = (topografi50.TYPE, "gatunamn", ROAD_NUMBER, SURVEYED_FIELD)

#: What the register's chains carry. It is the one source here that *describes*
#: its trails rather than only drawing them, so this is where a planned route's
#: reporting comes from. The state trail — ``Abisko - Abiskojaure (BD 21)`` —
#: is also the identity the chains are built on: over Abisko every segment has
#: one, where only 37 of 47 have a name.
TRAIL_ATTRIBUTES = (
    naturvardsregistret.TRAIL_NAME,
    naturvardsregistret.TRAIL_ROUTE_ID,
    naturvardsregistret.TRAIL_TYPE,
    naturvardsregistret.TRAIL_MARKING,
    naturvardsregistret.TRAIL_DESCRIPTION,
    naturvardsregistret.TRAIL_PROTECTED,
    naturvardsregistret.TRAIL_ID,
)

#: The sources whose lines are a record that something is drawn on this ground.
#: Their silence is the whole of what ``no_path_recorded`` says.
RECORDED_SOURCES = (T50_TRAILS, T50_PATHS, T50_ROADS, OSM)

#: The source that suggests a way rather than records one.
ROUTE_REGISTERS = (LEDER,)

#: The rule the two derived edge fields are read by; the same three numbers as
#: Norway's, measured there and not re-measured here.
MARKED_M, RECORDED_M, MIN_SHARE = DEFAULT_MARKED_M, DEFAULT_RECORDED_M, DEFAULT_MIN_SHARE

#: What a stored graph holds; see :data:`trails.network.norway.GRAPH_LAYOUT`.
GRAPH_LAYOUT = "elevation+coverage+protection+steepness"

#: What names a protected area, what it is called and which form it is: the
#: register's own columns.
PROTECTED_ID = naturvardsregistret.AREA_ID
PROTECTED_NAME, PROTECTED_FORM = naturvardsregistret.AREA_NAME, naturvardsregistret.AREA_FORM

#: Post spacing of the height mosaic the ground is read off, the same the
#: height tiles are built from (``make dem``), so a route's profile in the
#: build and the page's reading of the tiles describe one surface.
HEIGHT_POSTS_M = 4.0

RULES = Rules(
    metric_crs=METRIC_CRS,
    layout=GRAPH_LAYOUT,
    protected_id=PROTECTED_ID,
    protected_name=PROTECTED_NAME,
    protected_form=PROTECTED_FORM,
    form_label=naturvardsregistret.form_label,
    marked_m=MARKED_M,
    recorded_m=RECORDED_M,
    min_share=MIN_SHARE,
)


@dataclass(frozen=True, kw_only=True)
class Params(graphs.Params):
    """Everything that decides what the Swedish network comes out as.

    Nothing beyond :class:`trails.network.graphs.Params`: the registers are
    read for the whole country and cut to the zone, so there is no catalogue
    to name and no county to resolve.
    """


class Loaded(NamedTuple):
    """What one pass over the sources produced.

    Attributes:
        sources: The datasets the network is built from
        versions: What each source was read at, by name: the day the register's
            file was written, the day Lantmäteriet produced the delivery, the
            moment Overpass answered
        protected: Every protected area meeting the zone, whole rather than cut
            to it
        winter: The winter-only lines, from both registers, for a legend row
            and nothing else; with ``source``, ``kind`` and ``name``
    """

    sources: list[NetworkSource]
    versions: dict[str, str | None]
    protected: gpd.GeoDataFrame
    winter: gpd.GeoDataFrame


def zone_around(area: gpd.GeoDataFrame, distance_km: float) -> gpd.GeoDataFrame:
    """Grow an outline by a distance, keeping the interior.

    Args:
        area: Boundary in EPSG:4326
        distance_km: Width of the approach zone in kilometres

    Returns:
        The area and its approach zone as one polygon, in EPSG:4326
    """
    return graphs.zone_around(area, distance_km, METRIC_CRS)


def load_protected(params: Params, zone: gpd.GeoDataFrame, register: naturvardsregistret.Source | None = None) -> gpd.GeoDataFrame:
    """Load every protected area the ground under this network can lie in.

    One read over the zone's bounding box, then the areas that actually meet
    the zone. Every form the register draws counts, and each says which it is.

    Args:
        params: What decides the build, for the cache and the download
        zone: Park and approach zone, in EPSG:4326
        register: The register, where the caller already has it open

    Returns:
        The areas meeting the zone, whole, in EPSG:4326, ordered by
        :data:`PROTECTED_ID` so two builds of the same ground list them alike
    """
    source = register or naturvardsregistret.Source(cache_dir=params.cache_dir)
    west, south, east, north = (float(value) for value in zone.total_bounds)
    over_the_box = source.areas((west, south, east, north), force_download=params.force_download)
    if not len(over_the_box):
        return over_the_box

    # Meeting the zone, not clipped to it. A boundary cut at the edge of the
    # zone would hand a route an entry and an exit the register never drew.
    metric = over_the_box.to_crs(METRIC_CRS)
    meets = metric.intersects(zone.to_crs(METRIC_CRS).geometry.union_all())
    kept = over_the_box[meets.to_numpy()].sort_values(PROTECTED_ID).reset_index(drop=True)
    forms = kept[PROTECTED_FORM].value_counts().to_dict()
    print(f"  protected areas: {len(kept)} meeting the zone, of {len(over_the_box)} over its box")
    print(f"    {' · '.join(f'{naturvardsregistret.form_label(form)} {count}' for form, count in sorted(forms.items()))}")
    return kept


def _in_degrees(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Hand a Topografi 50 layer on the way the rest of the build expects it."""
    return gpd.GeoDataFrame(gdf, geometry="geometry", crs=topografi50.CRS).to_crs("EPSG:4326").reset_index(drop=True)


def _classes(gdf: gpd.GeoDataFrame, classes: tuple[str, ...]) -> gpd.GeoDataFrame:
    return gdf[gdf[topografi50.TYPE].isin(classes)]


def load_sources(params: Params, zone: gpd.GeoDataFrame) -> Loaded:
    """Load every dataset the network is built from.

    A source that cannot be loaded is an error rather than a smaller graph; a
    network missing its roads or its marked trails looks plausible and
    disagrees with every measured figure.

    Args:
        params: What decides the build
        zone: Area and approach zone, in EPSG:4326

    Returns:
        The sources, the version each was read at, the protected areas and the
        winter lines
    """
    min_lon, min_lat, max_lon, max_lat = (float(value) for value in zone.total_bounds)
    bounds = (min_lon, min_lat, max_lon, max_lat)
    extent = zone.union_all()
    download = params.force_download

    print("\nLoading Naturvårdsverket's trail register...")
    register = naturvardsregistret.Source(cache_dir=params.cache_dir)
    every = register.trails(bounds, force_download=download)
    season = every[naturvardsregistret.TRAIL_SEASON]
    marked = clip_lines(every[season == naturvardsregistret.SUMMER].reset_index(drop=True), extent)
    winter_register = clip_lines(every[season == naturvardsregistret.WINTER].reset_index(drop=True), extent)
    routed = marked[marked[naturvardsregistret.TRAIL_ROUTE].notna()]
    print(
        f"  {len(marked):,} summer trail segments in the zone, {len(routed):,} on a state trail; {len(winter_register):,} winter segments kept apart"
    )

    print("\nLoading Topografi 50 trails, paths, roads and ferries...")
    country = topografi50.Source(cache_dir=params.cache_dir)
    ways = country.read(topografi50.KOMMUNIKATION, topografi50.LAYER_PATHS, bounds, force_download=download)
    mountain = country.read(topografi50.KOMMUNIKATION, topografi50.LAYER_MOUNTAIN_WAYS, bounds)
    trails = clip_lines(graphs.with_capture_date(_in_degrees(_classes(ways, TRAIL_CLASSES)), topografi50.CREATED), extent)
    walked = pd.concat([_classes(ways, PATH_CLASSES), _classes(mountain, MOUNTAIN_WALKED_CLASSES)], ignore_index=True)
    paths = clip_lines(graphs.with_capture_date(_in_degrees(walked), topografi50.CREATED), extent)
    winter_t50 = clip_lines(_in_degrees(_classes(ways, WINTER_CLASSES)), extent)
    roads = clip_lines(
        graphs.with_capture_date(_in_degrees(country.read(topografi50.KOMMUNIKATION, topografi50.LAYER_ROADS, bounds)), topografi50.CREATED), extent
    )
    ferries = clip_lines(
        graphs.with_capture_date(_in_degrees(country.read(topografi50.KOMMUNIKATION, topografi50.LAYER_FERRIES, bounds)), topografi50.CREATED), extent
    )
    print(f"  delivery of {country.version}: {len(trails):,} marked trail lines, {len(paths):,} path lines, {len(roads):,} road fragments")
    print(f"  {len(ferries):,} ferry lines; {len(winter_t50):,} winter lines kept apart")

    # Topografi 50's trails carry no names, and the angle rule only has to
    # guess where nothing else can decide. The register names its state trails
    # and lies on the same lines, so this is the marked part of the network
    # getting a reliable identity instead of a guess about angles.
    before = len(trails)
    trails = attach_nearest(
        trails,
        routed,
        {naturvardsregistret.TRAIL_ROUTE: "route_name"},
        max_distance_m=params.trail_name_m,
        metric_crs=METRIC_CRS,
        # Nearness alone hands a route's name to every side path that meets it.
        min_overlap=0.5,
    )
    matched = trails["route_name"].notna()
    matched_km = trails[matched].to_crs(METRIC_CRS).length.sum() / 1000 if matched.any() else 0.0
    print(f"  {before:,} trail lines in the zone, {int(matched.sum()):,} named from the register ({matched_km:,.0f} km)")

    print("\nLoading OpenStreetMap paths...")
    osm_source = overpass.Source(cache_dir=params.cache_dir)
    osm = clip_lines(osm_source.fetch_paths(bounds, force_download=download), extent)

    sources = [
        # The official marked trails. Their published unit is the state trail,
        # which is what the identity rule keeps whole: a trail carries on
        # through every crossing of it and ends only where it genuinely
        # branches.
        NetworkSource(
            LEDER,
            marked,
            cost_factor=COST_FACTORS[LEDER],
            identity_field=naturvardsregistret.TRAIL_ROUTE,
            attributes=TRAIL_ATTRIBUTES,
            node_simplify_m=params.route_noding_m,
        ),
        NetworkSource(
            T50_TRAILS,
            trails,
            cost_factor=COST_FACTORS[T50_TRAILS],
            identity_field="route_name",
            attributes=PATH_ATTRIBUTES,
        ),
        # No identity: a worn path has no name, and under a marked trail it is
        # a second line of the same way, which the register and the trail
        # source name between them.
        NetworkSource(
            T50_PATHS,
            paths,
            cost_factor=COST_FACTORS[T50_PATHS],
            attributes=PATH_ATTRIBUTES,
        ),
        NetworkSource(
            T50_ROADS,
            roads,
            cost_factor=COST_FACTORS[T50_ROADS],
            identity_field=ROAD_NUMBER,
            attributes=ROAD_ATTRIBUTES,
        ),
        NetworkSource(
            OSM,
            osm,
            cost_factor=COST_FACTORS[OSM],
            identity_field="name",
            attributes=("highway", "surface", "sac_scale", "trail_visibility", "osm_id"),
        ),
        NetworkSource(FERRIES, ferries, kind=FERRY, attributes=(topografi50.TYPE, "destination", SURVEYED_FIELD)),
    ]
    versions = {
        LEDER: register.versions.get(naturvardsregistret.TRAILS_FILE),
        T50_TRAILS: country.version,
        T50_PATHS: country.version,
        T50_ROADS: country.version,
        FERRIES: country.version,
        OSM: osm_source.loaded_at,
    }

    print("\nLoading protected areas (Naturvårdsregistret)...")
    protected = load_protected(params, zone, register)

    winter = gpd.GeoDataFrame(
        pd.concat(
            [
                pd.DataFrame(
                    {
                        "source": LEDER,
                        "kind": winter_register[naturvardsregistret.TRAIL_TYPE].to_numpy(),
                        "name": winter_register[naturvardsregistret.TRAIL_ROUTE].to_numpy(),
                        "geometry": winter_register.geometry.to_numpy(),
                    }
                ),
                pd.DataFrame(
                    {"source": T50_PATHS, "kind": winter_t50[topografi50.TYPE].to_numpy(), "name": None, "geometry": winter_t50.geometry.to_numpy()}
                ),
            ],
            ignore_index=True,
        ),
        geometry="geometry",
        crs="EPSG:4326",
    )
    return Loaded(sources=sources, versions=versions, protected=protected, winter=winter)


def edge_costs(sources: list[NetworkSource], params: Params) -> dict[str, dict[str, float]]:
    """Say what a metre on each dataset costs a route; see :func:`graphs.edge_costs`."""
    return graphs.edge_costs(sources, params)


def protected_table(protected: gpd.GeoDataFrame, *, simplify_m: float = PROTECTED_SIMPLIFY_M) -> list[dict[str, Any]]:
    """Say what each protected area is and where its boundary runs, for a page.

    :func:`graphs.protected_table` under this register's names.

    Args:
        protected: The areas, from :func:`load_protected`, in EPSG:4326
        simplify_m: Vertex tolerance for the outlines, in metres

    Returns:
        One entry per area, in the order the edges name them
    """
    return graphs.protected_table(protected, RULES, simplify_m=simplify_m)


def masks_from(sources: list[NetworkSource]) -> Masks:
    """Build the masks the derived edge fields are tested against.

    Args:
        sources: The datasets, as loaded

    Returns:
        The three masks, in :data:`METRIC_CRS`

    Raises:
        ValueError: If Topografi 50 classifies its paths in terms this does not
            know — a class that stopped being a class would empty the unmarked
            mask and cost nothing to notice
    """
    frames = {source.name: source.gdf.to_crs(METRIC_CRS) for source in sources}
    paths = frames[T50_PATHS]
    classes = paths[topografi50.TYPE].astype("string").str.strip()

    stated = set(classes.dropna().unique())
    if stated and not stated & set(PATH_CLASSES + MOUNTAIN_WALKED_CLASSES):
        raise ValueError(f"Topografi 50 classifies its paths as {sorted(stated)}, none of which this knows")

    # Membership is the statement for both trail sources: every line in the
    # register is a marked trail, and so is every line of the two trail classes.
    marked = pd.concat([frames[LEDER].geometry, frames[T50_TRAILS].geometry], ignore_index=True)
    recorded = pd.concat([frames[name].geometry for name in RECORDED_SOURCES], ignore_index=True)
    return Masks(
        marked=gpd.GeoSeries(marked, crs=METRIC_CRS),
        unmarked=gpd.GeoSeries(paths.geometry[classes.isin(UNMARKED_CLASSES).fillna(False)].reset_index(drop=True), crs=METRIC_CRS),
        recorded=gpd.GeoSeries(recorded, crs=METRIC_CRS),
    )


def fingerprint(sources: list[NetworkSource], masks: Masks, params: Params, protected: gpd.GeoDataFrame) -> str:
    """Summarise what went into a build, so a cached one can be recognised.

    Args:
        sources: The datasets
        masks: What the derived edge fields were decided against
        params: What shaped the result
        protected: The protected areas every edge is measured against

    Returns:
        Short hash naming this build
    """
    return graphs.fingerprint(sources, masks, params, protected, RULES)


def chain_report(sources: list[NetworkSource], clip: gpd.GeoDataFrame, params: Params) -> pd.DataFrame:
    """Count each source's chains under both rules; see :func:`graphs.chain_report`."""
    return graphs.chain_report(sources, clip, params, RULES)


def build(
    sources: list[NetworkSource],
    masks: Masks,
    clip: gpd.GeoDataFrame,
    params: Params,
    *,
    name: str,
    protected: gpd.GeoDataFrame,
) -> tuple[Network, pd.DataFrame]:
    """Build the network, or read back the last build of the same inputs.

    :func:`graphs.build` under this country's rules, with the ground read off
    Lantmäteriet's height model by :func:`measure`.

    Args:
        sources: The datasets
        masks: What the derived edge fields are decided against
        clip: Extent to cut them to, in EPSG:4326; also what the height mosaic
            is read over
        params: What decides the build
        name: Area the graph is of, which names its cache entry
        protected: The protected areas every walked edge is measured against

    Returns:
        The network and the per-source chain counts
    """
    return graphs.build(sources, masks, clip, params, RULES, name=name, protected=protected, measure=lambda network: measure(network, params, clip))


def measure(network: Network, params: Params, clip: gpd.GeoDataFrame) -> Network:
    """Read the ground under the network and put it on the edges and chains.

    Off the cached mosaic of the 1 m height model rather than a point service:
    every sample of every edge is read in one pass, bilinearly, by the same
    rule the page's height tiles are resampled by. Ferries are skipped, as in
    Norway: there is no ground under a crossing.

    Args:
        network: The finished network, in :data:`METRIC_CRS`
        params: What decides the build
        clip: The extent the network was cut to, in EPSG:4326

    Returns:
        A copy carrying ``elevations`` and ``ascent`` on every edge, and
        ``ascent`` on every chain
    """
    west, south, east, north = (float(value) for value in clip.total_bounds)
    model = markhojd.Source(cache_dir=params.cache_dir)
    # The model's own CRS is the compound one with RH 2000 on top of SWEREF 99
    # TM; horizontally it is the CRS the network is built in.
    read = markhojd.heights_over(model, (west, south, east, north), posts_m=HEIGHT_POSTS_M)
    return with_elevation(network, read, step_m=params.elevation_step_m, threshold_m=params.ascent_threshold_m)


def derive(edges: gpd.GeoDataFrame, masks: Masks, protected: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Add the three fields an edge cannot read off the chain it lies on.

    :func:`graphs.derive` under this country's rules.

    Args:
        edges: The graph's edges
        masks: Raw source geometry to decide the first two against
        protected: The protected areas to measure the third against

    Returns:
        The edges carrying ``waymarked``, ``no_path_recorded`` and the
        protected-area column
    """
    return graphs.derive(edges, masks, protected, RULES)
