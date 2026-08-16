"""The walking network these seven Norwegian datasets make between them.

:mod:`trails.routing` knows how to turn named GeoDataFrames into chains and
edges and nothing else; it has never heard of Kartverket. This module is the
other half: which datasets go in, what a route costs on each of them, what each
one carries onto its chains, and how the two derived edge fields are decided.

It is deliberately free of any one park — the extent arrives as a clipping
geometry — so both the map and the graph report call the same
:func:`load_sources` and the same :func:`build`, and therefore hit the same
cache. Two scripts drawing two different graphs of the same ground would be a
worse fault than either of them being wrong, because nothing would say so.

    >>> park = naturbase.Source(cache_dir=cache).find_one("Lomsdal-Visten", layer=...)
    >>> params = Params(cache_dir=cache, ut_routes=catalogue)
    >>> zone = zone_around(park, params.approach_km)
    >>> loaded = load_sources(params, zone)
    >>> network, chains = build(loaded.sources, masks_from(loaded.sources), zone, params, name="lomsdal-visten")
"""

import argparse
import hashlib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, NamedTuple

import geopandas as gpd
import pandas as pd

from trails.io import cache as cache_module
from trails.io.sources import hoydedata, kommuneinfo, n50, overpass, stedsnavn, traktorvegsti, ut
from trails.io.sources.geonorge import Source as GeonorgeSource
from trails.io.sources.language import Language
from trails.routing import (
    CHAIN_COVERAGE_COLUMNS,
    DEFAULT_ASCENT_THRESHOLD_M,
    DEFAULT_MARKED_M,
    DEFAULT_MIN_SHARE,
    DEFAULT_RECORDED_M,
    DEFAULT_STEP_M,
    IDENTITY_SEPARATOR,
    ChainRule,
    Network,
    NetworkSource,
    build_chains,
    build_network,
    chain_coverage,
    chains_of,
    no_path_recorded,
    parts_of,
    split_source,
    waymarked,
    with_elevation,
)
from trails.routing.graph import DEFAULT_BRIDGE_COST_FACTOR
from trails.routing.noding import clip_lines
from trails.routing.sources import BRIDGE, FERRY
from trails.utils.geo import attach_nearest

#: Metric CRS for Norway. The routing module works in it, so every length and
#: distance below is already in metres.
METRIC_CRS = "EPSG:25833"

#: What each dataset is called, on every chain and every edge built from it, and
#: therefore also the prefix of its chain ids. Named here rather than written out
#: where they are used, because a caller reading the chains back has to spell
#: them the same way: the map groups the chain frame by exactly these.
UT = "UT.no"
TURRUTEBASEN = "Turrutebasen"
FKB = "FKB"
N50_PATHS = "N50 paths"
N50_ROADS = "N50 roads"
OSM = "OSM"
FERRIES = "Ferries"

#: Every source, in the order :func:`load_sources` returns them.
SOURCE_NAMES = (UT, TURRUTEBASEN, FKB, N50_PATHS, N50_ROADS, OSM, FERRIES)

#: Cost factor per source. Priority belongs here and nowhere else — a route
#: through a valley described by three datasets should run on the best-surveyed
#: line, without any of the others being cut away. Keep these close to 1.0, or
#: a route makes real detours to reach a preferred source.
COST_FACTORS = {
    UT: 1.00,
    # Between UT.no's described walks and FKB's surveyed lines: an officially
    # marked route is a better thing to follow than a path that merely exists.
    TURRUTEBASEN: 1.02,
    FKB: 1.05,
    N50_PATHS: 1.10,
    OSM: 1.20,
    N50_ROADS: 1.30,
}

#: What a segment takes from Turrutebasen's info table, which holds a row per
#: named route a segment belongs to rather than a row per segment.
#: ``trail_name`` is also the identity the chains are built on.
TRAIL_INFO_FIELDS = ("trail_name", "trail_number", "maintenance_responsible", "difficulty", "trail_significance", "special_hiking_trail_type")

#: N50's own account of how a line was captured. It feeds nothing derived and is
#: carried for the popup, where it is worth more than any category computed from
#: it: 47 % of N50's paths in this zone are ``dig``, digitised from a map rather
#: than seen, with capture dates back to 1965 and accuracies as coarse as 50 m.
SURVEY_FIELD = "malemetode"

#: When a line was captured, as a date rather than the timestamp every one of
#: these registers stores. See :func:`_with_capture_date` for why the rendering
#: happens before the chains rather than after them.
SURVEYED_FIELD = "surveyed"

#: What Turrutebasen's chains carry. It is the one source here that *describes*
#: its routes rather than only drawing them, so this is where a planned route's
#: reporting has to come from, and after UT.no's it holds the richest popup on
#: the map. Measured over this zone: ``marking`` is on all 770 segments and the
#: maintaining body on all of them, ``signage`` on 88, ``difficulty`` on 27 %
#: and ``trail_significance`` on 31 %. The register's other four fields —
#: season, surface type, trail width and trail type — hold nothing at all here,
#: and a column of nulls on every chain is worse than none.
TRAIL_ATTRIBUTES = (
    "marking",
    "signage",
    "trail_follows",
    "origin",
    # This register writes its capture method out in words already, so unlike
    # N50's it needs no code table — only the date turning into one.
    "measurement_method",
    SURVEYED_FIELD,
    *(field for field in TRAIL_INFO_FIELDS if field != "trail_name"),
)

#: ``rutemerking`` on an N50 path: whether the register states it is waymarked.
N50_MARKED, N50_UNMARKED = "JA", "NEI"

#: What a register writes in a name column when it has no name. Read as an
#: identity these are worse than nothing, and in exactly the way ``pd.NA`` once
#: was: *Ukjent* means unknown, so every unnamed route becomes the same route as
#: every other unnamed route. Three Turrutebasen segments say it here, and it
#: reaches nineteen FKB paths through the route-name join.
#:
#: Excluded from the identity itself as well as from the derived figures, which
#: is what moved Turrutebasen from 245 chains to 244 and FKB from 6,202 to
#: 6,201: two chains the rule had carried through a junction on the strength of
#: the word "unknown", and which are two ways glued at a crossing rather than
#: one way. That correction waited for a change of its own, because it moves a
#: chain count several phases were accepted against and the value of such an
#: acceptance is that a moved figure has exactly one cause.
PLACEHOLDER_IDENTITIES = frozenset({"Ukjent"})

#: The sources whose lines are a record that something is drawn on this ground.
#: Their silence is the whole of what ``no_path_recorded`` says; their lines say
#: nothing, because all four record liberally and three of them are Kartverket.
RECORDED_SOURCES = (FKB, N50_PATHS, N50_ROADS, OSM)

#: The sources that suggest a way rather than record one. Whether anything draws
#: a path is only a question for these: an FKB line *is* the record, so for it
#: the test answers itself.
ROUTE_REGISTERS = (UT, TURRUTEBASEN)

#: The rule the two derived edge fields are read by: how close counts as running
#: along a marking mask, how close counts as recorded at all, and how much of an
#: edge has to lie that close. All three are fixed by measurement in the
#: decisions document rather than being preferences, so they are not options.
#: They live here as one value because three places need exactly the same
#: numbers — the derivation, the fingerprint that decides whether a cached graph
#: answers for them, and the report. Read from anywhere else, a change to one of
#: them would leave a graph in the cache that no longer matches its own key.
MARKED_M, RECORDED_M, MIN_SHARE = DEFAULT_MARKED_M, DEFAULT_RECORDED_M, DEFAULT_MIN_SHARE

#: What a stored graph holds, bumped whenever a build starts producing something
#: a cached one does not carry. The rest of the fingerprint covers what went
#: *into* a build; this covers what comes out of it. Without it, a graph cached
#: before a column existed is served to code that reads that column — the
#: parameters and the sources are unchanged, so nothing else in the key notices.
GRAPH_LAYOUT = "elevation+coverage"


@dataclass(frozen=True)
class Params:
    """Everything that decides what the network comes out as.

    Every field here except ``force_download`` and ``rebuild`` goes into the
    cache key, so two callers agreeing on these agree on the graph — which is
    the point of the class. Anything that would change the result and is *not*
    here is a cache that answers for a build it did not come from.

    Attributes:
        cache_dir: Root cache directory
        ut_routes: Catalogue of UT.no trips to include
        approach_km: Width of the approach zone around the area
        fylke_prefixes: County prefixes searched when resolving municipalities
        stroke_deg: Largest deflection accepted as a way continuing through a
            junction
        probe_m: How far either side of a junction the direction is read
        bridge_m: How far a loose end may reach for another node
        ferry_cost_km: What a crossing costs, as kilometres walked
        route_noding_m: Tolerance for the simplified copy the published route
            datasets are noded by; their own geometry is kept either way. Off,
            because it was measured and buys nothing that is missing.
        road_name_m: How far a road fragment may look for its name in the
            place-name register
        trail_name_m: How far an FKB path may look for a Turrutebasen route name
        elevation_step_m: How far apart the height samples are laid along an
            edge. A parameter only so that the invariance the ascent threshold
            exists for can be checked: the same route has to read the same
            climb at 5, 10 and 15 m.
        ascent_threshold_m: Gains under this are not counted as climb
        force_download: Re-download source data instead of using the cache
        rebuild: Rebuild the graph even if a cached one matches
    """

    cache_dir: str
    ut_routes: str
    approach_km: float = 15.0
    fylke_prefixes: tuple[str, ...] = ("18",)
    stroke_deg: float = 45.0
    probe_m: float = 5.0
    bridge_m: float = 25.0
    ferry_cost_km: float = 5.0
    route_noding_m: float = 0.0
    road_name_m: float = 25.0
    trail_name_m: float = 25.0
    elevation_step_m: float = DEFAULT_STEP_M
    ascent_threshold_m: float = DEFAULT_ASCENT_THRESHOLD_M
    force_download: bool = False
    rebuild: bool = False

    @classmethod
    def from_args(cls, args: argparse.Namespace, **overrides: Any) -> Params:
        """Read whichever of these a command line happens to offer.

        The two scripts expose different subsets — the map has no reason to
        offer a noding tolerance — and what a script leaves out has to fall to
        the default rather than to whatever that script felt like, or the two
        would build different graphs from the same ground.

        Args:
            args: Parsed command line
            **overrides: Values to use in preference to both

        Returns:
            The parameters
        """
        taken = {name: getattr(args, name) for name in cls.__dataclass_fields__ if hasattr(args, name)}
        return cls(**{**taken, **overrides})


class Masks(NamedTuple):
    """Raw source geometry the two derived edge fields are decided against.

    Built out of the sources rather than read off the edges, and that is not a
    detail. A marking flag reaches an edge only through the chain it lies on,
    where a run that changes character has already been merged into an ambiguous
    ``JA / NEI`` — 38 chains and 158 km of it, exactly where the answer matters.
    A mask has no such problem and it treats every source alike: a Turrutebasen
    edge lies on its own feature and comes out marked without a special case.

    Attributes:
        marked: Every Turrutebasen feature — membership is the statement, since
            all 770 segments in this zone read ``marking = Marked`` — together
            with every N50 path the register marks as waymarked
        unmarked: Every N50 path the register marks as not waymarked
        recorded: Every line from :data:`RECORDED_SOURCES`
    """

    marked: gpd.GeoSeries
    unmarked: gpd.GeoSeries
    recorded: gpd.GeoSeries


class Loaded(NamedTuple):
    """What one pass over the sources produced.

    Attributes:
        sources: The datasets the network is built from
        municipalities: The codes they were ordered per, which the caller needs
            for anything else it draws from the same per-municipality datasets
        turrutebasen_version: The version string the register publishes, which
            an export has to record so a route that differs months later has a
            cause rather than a puzzle
    """

    sources: list[NetworkSource]
    municipalities: list[str]
    turrutebasen_version: str


def zone_around(area: gpd.GeoDataFrame, distance_km: float) -> gpd.GeoDataFrame:
    """Grow an outline by a distance, keeping the interior.

    Args:
        area: Boundary in EPSG:4326
        distance_km: Width of the approach zone in kilometres

    Returns:
        The area and its approach zone as one polygon, in EPSG:4326
    """
    metric = area.to_crs(METRIC_CRS)
    return gpd.GeoDataFrame(geometry=metric.buffer(distance_km * 1000), crs=METRIC_CRS).to_crs("EPSG:4326")


def _join_values(values: pd.Series) -> str | None:
    """Collapse what a Turrutebasen segment carries into one value.

    A segment can belong to several named routes, so the info table holds more
    than one row for it and they need not agree. The chain rule reads several
    identities out of one value, so they are joined the way the road and trail
    layers already write them rather than one being picked — and the same holds
    for what those routes say about themselves: a segment shared by an easy
    route and a strenuous one is both, and reads so.

    Written through :func:`parts_of` rather than by hand, so that it agrees with
    the chain rule that has to read it back. Two ways it would otherwise not:
    the separator is one constant rather than two literals that can drift apart,
    and a register writing an empty string where it has nothing is not taken for
    a value — which would put ``" / Enkel"`` on the chain and into the popup.

    Args:
        values: What the routes a segment belongs to say

    Returns:
        The values, joined, or None where the segment has none
    """
    parts = sorted({part for value in values for part in parts_of(value)})
    return IDENTITY_SEPARATOR.join(parts) if parts else None


def _with_capture_date(gdf: gpd.GeoDataFrame, field: str) -> gpd.GeoDataFrame:
    """Render a capture timestamp as the date a popup shows.

    Rendered here rather than after chaining, and that is the whole reason the
    function exists: a chain spans several features and joins the values they
    disagree on, so a timestamp reaching the chain arrives as
    ``1984-03-01 00:00:00+00:00 / 2005-06-06 00:00:00+00:00`` and no parser
    reads it back. As dates the same chain reads ``1984-03-01 / 2005-06-06``,
    which is both true and legible.

    Args:
        gdf: Features carrying the source's own capture timestamp
        field: Column holding it

    Returns:
        Copy carrying :data:`SURVEYED_FIELD` as ``YYYY-MM-DD``
    """
    captured = pd.to_datetime(gdf[field], errors="coerce", utc=True).dt.strftime("%Y-%m-%d")
    return gdf.assign(**{SURVEYED_FIELD: captured})


def load_sources(params: Params, zone: gpd.GeoDataFrame) -> Loaded:
    """Load every dataset the network is built from.

    A source that cannot be loaded is an error rather than a smaller graph.
    Without the roads the largest component falls from 79 % of the network's
    length to 5 %; without the ferries eleven of seventeen quays are
    unreachable; without the place-name register the chains lose the identity
    that keeps them whole. Each of those produces a network that looks plausible
    and disagrees with every measured figure.

    Args:
        params: What decides the build
        zone: Area and approach zone, in EPSG:4326

    Returns:
        The sources, the municipalities they were ordered per, and the version
        of the one register that publishes one
    """
    min_lon, min_lat, max_lon, max_lat = (float(value) for value in zone.total_bounds)
    bounds = (min_lon, min_lat, max_lon, max_lat)
    extent = zone.union_all()
    codes = kommuneinfo.Source(cache_dir=params.cache_dir).intersecting(zone, fylke=params.fylke_prefixes)
    download = params.force_download

    print("\nLoading UT.no routes...")
    catalogue = ut.load_catalogue(params.ut_routes)
    ut_routes = ut.Source(cache_dir=params.cache_dir).load_routes(catalogue, force_download=download)

    print("\nLoading Turrutebasen...")
    turrutebasen = GeonorgeSource(cache_dir=params.cache_dir).load_turrutebasen(target_crs="EPSG:4326", language=Language.EN, force_download=download)
    routes = turrutebasen.spatial_layers["hiking_trail_centerline"]
    info = turrutebasen.attribute_tables["hiking_trail_info_table"]
    # A segment can belong to several named routes, so the info table holds more
    # than one row per segment; the chain rule reads them all out of one value.
    described = info.groupby("hiking_trail_fk")[list(TRAIL_INFO_FIELDS)].agg(_join_values)
    merged = routes.merge(described, left_on="local_id", right_index=True, how="left")
    marked = clip_lines(gpd.GeoDataFrame(merged, geometry="geometry", crs=routes.crs), extent)
    marked = _with_capture_date(marked, "data_capture_date")
    named = marked[marked["trail_name"].notna()]
    print(f"  {len(marked):,} marked route segments in the zone, {len(named):,} of them named")

    print("\nLoading detailed FKB paths...")
    fkb = traktorvegsti.Source(cache_dir=params.cache_dir).fetch_paths(bounds, force_download=download)
    fkb = clip_lines(fkb, extent)

    # FKB carries no names at all, and the angle rule only has to guess where
    # nothing else can decide. Turrutebasen names its routes and lies almost
    # entirely on FKB, so this is the waymarked part of the network getting a
    # reliable identity instead of a guess about angles.
    before = len(fkb)
    fkb = attach_nearest(
        fkb,
        named,
        {"trail_name": "route_name"},
        max_distance_m=params.trail_name_m,
        metric_crs=METRIC_CRS,
        # Nearness alone hands a route's name to every side path that meets it.
        min_overlap=0.5,
    )
    matched = fkb["route_name"].notna()
    matched_km = fkb[matched].to_crs(METRIC_CRS).length.sum() / 1000
    print(f"  {before:,} paths in the zone, {int(matched.sum()):,} named from Turrutebasen ({matched_km:,.0f} km)")

    print("\nLoading N50 paths, roads and ferries...")
    n50_source = n50.Source(cache_dir=params.cache_dir)
    paths = _with_capture_date(clip_lines(n50_source.load_paths(codes, force_download=download), extent), "datafangstdato")
    roads = _with_capture_date(clip_lines(n50_source.load_roads(codes, force_download=download), extent), "datafangstdato")
    ferries = _with_capture_date(clip_lines(n50_source.load_ferries(codes, force_download=download), extent), "datafangstdato")

    names_source = stedsnavn.Source(cache_dir=params.cache_dir)
    road_names = names_source.load_road_names(codes, force_download=download)
    roads = attach_nearest(
        roads,
        road_names,
        {"road_id": "road_id", "name": "road_name"},
        max_distance_m=params.road_name_m,
        metric_crs=METRIC_CRS,
        min_overlap=0.5,
    )
    print(f"  {int(roads['road_id'].notna().sum()):,} of {len(roads):,} road fragments named from SSR")

    print("\nLoading OpenStreetMap paths...")
    osm = clip_lines(overpass.Source(cache_dir=params.cache_dir).fetch_paths(bounds, force_download=download), extent)

    sources = [
        # Published as whole trips, and a trip is already linear and already the
        # unit a reader means. Noding these against each other would shatter 35
        # routes into 2,411 scraps, because they overlap each other heavily.
        NetworkSource(
            UT,
            ut_routes,
            cost_factor=COST_FACTORS[UT],
            identity_field="name",
            # The four links and the summary are the richest thing on the map
            # and the only content no other source has any form of.
            attributes=("category", "ut_summary", "ut_url", "guide_url_no", "guide_url_en", "gpx_url"),
            keep_whole=True,
            node_simplify_m=params.route_noding_m,
        ),
        # The official marked routes. Their published unit is the named route,
        # which is what the identity rule keeps whole: a route carries on through
        # every crossing of it and ends only where it genuinely branches.
        NetworkSource(
            TURRUTEBASEN,
            marked,
            cost_factor=COST_FACTORS[TURRUTEBASEN],
            identity_field="trail_name",
            placeholder_identities=PLACEHOLDER_IDENTITIES,
            attributes=TRAIL_ATTRIBUTES,
            node_simplify_m=params.route_noding_m,
        ),
        NetworkSource(
            FKB,
            fkb,
            cost_factor=COST_FACTORS[FKB],
            identity_field="route_name",
            attributes=("typeveg",),
            placeholder_identities=PLACEHOLDER_IDENTITIES,
        ),
        NetworkSource(
            N50_PATHS,
            paths,
            cost_factor=COST_FACTORS[N50_PATHS],
            attributes=("typeveg", "rutemerking", "vedlikeholdsansvarlig", "medium", SURVEY_FIELD, SURVEYED_FIELD),
        ),
        # Roads are named by the register, and the register id is what says two
        # fragments are the same road; the name repeats across the county.
        NetworkSource(
            N50_ROADS,
            roads,
            cost_factor=COST_FACTORS[N50_ROADS],
            identity_field="road_id",
            attributes=("vegkategori", "road_name", SURVEY_FIELD, SURVEYED_FIELD),
        ),
        NetworkSource(
            OSM,
            osm,
            cost_factor=COST_FACTORS[OSM],
            identity_field="name",
            attributes=("highway", "surface", "sac_scale", "trail_visibility", "osm_id"),
        ),
        # Nobody walks these, and without them the whole west of the park — where
        # the UT.no routes start — cannot be reached at all.
        NetworkSource(FERRIES, ferries, kind=FERRY, attributes=("typeveg", SURVEY_FIELD, SURVEYED_FIELD)),
    ]
    return Loaded(sources=sources, municipalities=codes, turrutebasen_version=turrutebasen.version)


def edge_costs(sources: list[NetworkSource], params: Params) -> dict[str, dict[str, float]]:
    """Say what a metre on each dataset costs a route.

    For a consumer that has the geometry but not the cost column, which is the
    position a browser is in. The cost of a walked edge is its length times its
    source's factor, and the length is in the geometry already — so what has to
    travel is these six numbers rather than one per edge.

    A crossing is the exception, and travels as a whole crossing's cost: it is
    the same decision whether it is 2 km or 20, so its cost is not its length
    and cannot be recovered from one.

    Args:
        sources: The datasets, as loaded
        params: What decides the build, for the crossing cost

    Returns:
        What each source costs, by source name, including the connectors that
        belong to no source at all
    """
    costs: dict[str, dict[str, float]] = {}
    for source in sources:
        costs[source.name] = {"flatM": params.ferry_cost_km * 1000} if source.kind == FERRY else {"factor": source.cost_factor}
    # Nobody drew a connector, and :func:`build` leaves its factor at the
    # default, so this is the same number the edges were weighted with.
    costs[BRIDGE] = {"factor": DEFAULT_BRIDGE_COST_FACTOR}
    return costs


def masks_from(sources: list[NetworkSource]) -> Masks:
    """Build the masks the derived edge fields are tested against.

    Args:
        sources: The datasets, as loaded

    Returns:
        The three masks, in :data:`METRIC_CRS`

    Raises:
        ValueError: If N50 states its marking in terms this does not know
    """
    frames = {source.name: source.gdf.to_crs(METRIC_CRS) for source in sources}
    paths = frames[N50_PATHS]
    marking = paths["rutemerking"].astype("string").str.strip().str.upper()

    # A code that stopped being a code would empty both masks and cost nothing
    # to notice: every walked edge would come back unknown, and a report full of
    # unknown is exactly what this park looks like anyway. The sibling loader
    # already expands its codes into words, so this is not a distant prospect.
    stated = set(marking.dropna().unique())
    if stated and not stated & {N50_MARKED, N50_UNMARKED}:
        raise ValueError(f"N50 states its marking as {sorted(stated)}, not as {N50_MARKED}/{N50_UNMARKED}")

    marked = pd.concat([frames[TURRUTEBASEN].geometry, paths.geometry[marking == N50_MARKED]], ignore_index=True)
    recorded = pd.concat([frames[name].geometry for name in RECORDED_SOURCES], ignore_index=True)
    return Masks(
        marked=gpd.GeoSeries(marked, crs=METRIC_CRS),
        unmarked=gpd.GeoSeries(paths.geometry[marking == N50_UNMARKED].reset_index(drop=True), crs=METRIC_CRS),
        recorded=gpd.GeoSeries(recorded, crs=METRIC_CRS),
    )


def fingerprint(sources: list[NetworkSource], masks: Masks, params: Params) -> str:
    """Summarise what went into a build, so a cached one can be recognised.

    Args:
        sources: The datasets
        masks: What the derived edge fields were decided against
        params: What shaped the result

    Returns:
        Short hash naming this build
    """
    # Every parameter that shapes the graph, including the two join distances:
    # they change no geometry, only which chains carry which identity, so a row
    # count and a total length cannot tell two of these builds apart.
    parts = [
        GRAPH_LAYOUT,
        f"{params.approach_km}|{params.stroke_deg}|{params.probe_m}|{params.bridge_m}"
        f"|{params.ferry_cost_km}|{params.route_noding_m}|{params.road_name_m}|{params.trail_name_m}"
        # And how the ground under the edges was read. Neither moves a line, but
        # a graph sampled every 15 m must not be served to a caller asking for
        # every 5 m — that is precisely the comparison the threshold is checked
        # by, and it would compare a cache against itself.
        f"|{params.elevation_step_m}|{params.ascent_threshold_m}",
        # And the masks with the rule they are read by. A mask is a filtered
        # subset of its sources, so a change in which features go into one shows
        # up in no source's row count or length.
        f"{_mask_digest(masks.marked)}|{_mask_digest(masks.unmarked)}|{_mask_digest(masks.recorded)}|{MARKED_M}|{RECORDED_M}|{MIN_SHARE}",
    ]
    for source in sources:
        length = source.gdf.to_crs(METRIC_CRS).length.sum() if len(source.gdf) else 0.0
        # And the values the chains are built from, not only the geometry they
        # are built along. The road names come from SSR and the route names from
        # Turrutebasen, so neither shows up in this source's own row count or
        # length — yet a change in either moves where a chain ends.
        parts.append(f"{source.name}:{len(source.gdf)}:{length:.0f}:{source.cost_factor}:{source.keep_whole}:{_values_digest(source)}")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]


def _mask_digest(mask: gpd.GeoSeries) -> str:
    """Summarise a mask, so a graph is not read back for a different one.

    Args:
        mask: Lines the derived fields are decided against

    Returns:
        Its size and total length
    """
    return f"{len(mask)}:{mask.length.sum():.0f}"


def _values_digest(source: NetworkSource) -> str:
    """Summarise the non-geometric values a source contributes to its chains.

    Args:
        source: Dataset going into the build

    Returns:
        Short digest of its identity column and attributes, or ``-`` where it
        has neither
    """
    columns = [name for name in dict.fromkeys((source.identity_field, *source.attributes)) if name]
    if not columns:
        return "-"

    digest = hashlib.sha256()
    for column in columns:
        digest.update(f"\n{column}\n".encode())
        # `na_rep` is what keeps a missing value visible here. Without it
        # `str.cat` drops one entirely rather than writing a placeholder, so a
        # road that loses its name and a road that never had one hash the same,
        # and this digest exists precisely because a name arriving from SSR
        # changes neither the row count nor the length of the source it lands
        # in. Under pandas 2 `astype(str)` wrote "None" and hid the gap; pandas
        # 3 stopped, which is what exposed it.
        digest.update(source.gdf[column].astype(str).str.cat(sep="\x00", na_rep="\x01").encode())
    return digest.hexdigest()[:12]


def chain_report(sources: list[NetworkSource], clip: gpd.GeoDataFrame, params: Params) -> pd.DataFrame:
    """Count each source's chains under both rules.

    Breaking at every junction is the baseline: it is what ``linemerge`` alone
    gives, and it cuts a road into a scrap at every side turning. The stroke rule
    is what makes a chain something worth clicking.

    Args:
        sources: The datasets
        clip: Extent to cut them to
        params: What decides the build

    Returns:
        One row per source
    """
    rows = []
    for source in sources:
        # The baseline is reported for every source, a published one included:
        # it is what noding that source against itself would have cost it.
        pieces = split_source(source, clip, metric_crs=METRIC_CRS)
        baseline = build_chains(pieces, source, rule=ChainRule.JUNCTION)

        # The angle alone, without the identity rule, is what the decisions
        # document measured. Reported next to it because the two differ by more
        # than the rounding: identity ends a chain wherever a way divides, and
        # a named road divides at most of its junctions.
        anonymous = replace(source, identity_field=None)
        angle_only = build_chains(pieces, anonymous, rule=ChainRule.STROKE, stroke_angle_deg=params.stroke_deg, probe_m=params.probe_m)

        chains = chains_of(source, clip, rule=ChainRule.STROKE, stroke_angle_deg=params.stroke_deg, probe_m=params.probe_m, metric_crs=METRIC_CRS)
        rows.append(
            {
                "source": source.name,
                "features": len(source.gdf),
                "at every junction": len(baseline),
                "angle only": len(angle_only),
                "with identity": len(chains),
                "whole": source.keep_whole,
                "km": chains["length_m"].sum() / 1000,
                "mean chain m": chains["length_m"].mean() if len(chains) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def build(
    sources: list[NetworkSource],
    masks: Masks,
    clip: gpd.GeoDataFrame,
    params: Params,
    *,
    name: str,
) -> tuple[Network, pd.DataFrame]:
    """Build the network, or read back the last build of the same inputs.

    Reading the ground height along every edge is what makes this expensive —
    twenty thousand requests against a public service, a quarter of an hour
    once. Two caches stand between that and a rebuild: this one, which serves an
    unchanged graph whole, and the point store underneath it, which means even a
    changed source only asks about the ground that actually moved.

    Args:
        sources: The datasets
        masks: What the derived edge fields are decided against
        clip: Extent to cut them to
        params: What decides the build
        name: Area the graph is of, which names its cache entry

    Returns:
        The network and the per-source chain counts

    Raises:
        ValueError: If the height endpoint does not speak the CRS the network is
            built in
    """
    store = cache_module.Object(cache_dir=str(Path(params.cache_dir) / "objects"))
    key = f"route_graph_{name}_{fingerprint(sources, masks, params)}"

    if not params.rebuild and store.exists(key):
        print(f"\nReading the graph back from the cache ({key})...")
        cached: dict[str, Any] = store.load(key)
        return cached["network"], cached["chains"]

    print("\nBuilding chains per source...")
    chains = chain_report(sources, clip, params)

    print("Noding every source against every other...")
    network = build_network(
        sources,
        clip,
        metric_crs=METRIC_CRS,
        stroke_angle_deg=params.stroke_deg,
        probe_m=params.probe_m,
        bridge_m=params.bridge_m,
        ferry_cost_m=params.ferry_cost_km * 1000,
    )

    print("Asking every edge what the ground it runs over is recorded as...")
    network = replace(network, edges=derive(network.edges, masks))

    # And summed along the chains, because a chain is what gets selected and
    # shown while an edge is only what a mask can be tested against.
    covered = chain_coverage(network.chains, network.edges)
    network = replace(network, chains=network.chains.assign(**{column: covered[column] for column in CHAIN_COVERAGE_COLUMNS}))

    print(f"Reading the ground height every {params.elevation_step_m:g} m along every edge but the crossings...")
    network = measure(network, params)

    store.save(key, {"network": network, "chains": chains}, metadata={"area": name, "approach_km": params.approach_km})
    return network, chains


def measure(network: Network, params: Params) -> Network:
    """Read the ground under the network and put it on the edges and chains.

    Ferries are skipped rather than filtered afterwards: there is no ground
    under a crossing, and asked about open water the endpoint answers with a
    depth from its depth contours — a ferry edge would come back at -276 m.
    Bridged connectors *are* sampled. Nobody drew one, which is what a connector
    is, but there is ground under it.

    Args:
        network: The finished network, in :data:`METRIC_CRS`
        params: What decides the build

    Returns:
        A copy carrying ``elevations`` and ``ascent`` on every edge, and
        ``ascent`` on every chain

    Raises:
        ValueError: If the endpoint does not speak the CRS the network is in
    """
    if METRIC_CRS != hoydedata.REQUEST_CRS:
        raise ValueError(f"the height endpoint answers in {hoydedata.REQUEST_CRS}, the network is built in {METRIC_CRS}")

    heights = hoydedata.Source(cache_dir=params.cache_dir)
    return with_elevation(network, heights.elevations, step_m=params.elevation_step_m, threshold_m=params.ascent_threshold_m)


def derive(edges: gpd.GeoDataFrame, masks: Masks) -> gpd.GeoDataFrame:
    """Add the two fields an edge cannot read off the chain it lies on.

    Both are summed in kilometres by a planned route, which is what earns them a
    place on the edge rather than on the chain: a chain takes one value along its
    whole length, and both of these change along it.

    Args:
        edges: The graph's edges
        masks: Raw source geometry to decide them against

    Returns:
        The edges carrying ``waymarked`` and ``no_path_recorded``, both of them
        empty on a crossing and on an inferred connector
    """
    return edges.assign(
        waymarked=waymarked(edges, masks.marked, masks.unmarked, distance_m=MARKED_M, min_share=MIN_SHARE),
        no_path_recorded=no_path_recorded(edges, masks.recorded, distance_m=RECORDED_M, min_share=MIN_SHARE),
    )
