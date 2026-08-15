"""Build the routing graph for Lomsdal-Visten and report what it looks like.

Nothing is drawn here. This is the foundation the route planning stands on, and
it is verifiable on its own numbers: how many chains each source falls into, how
many edges the merged graph holds, how much of the network hangs together, how
far that reach carries across the park, and whether the coast is reachable at
all without the ferries.

The graph itself is built by :mod:`trails.routing`, which knows nothing about
this park. Everything specific to it — which sources, which extent, which names
are joined onto which geometry — is here.

Usage::

    uv run python analysis/scripts/route_graph.py
    uv run python analysis/scripts/route_graph.py --approach-km 5 --rebuild
"""

import argparse
import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any, NamedTuple

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from trails.io import cache as cache_module
from trails.io.sources import kommuneinfo, n50, naturbase, overpass, stedsnavn, traktorvegsti, ut
from trails.io.sources.geonorge import Source as GeonorgeSource
from trails.io.sources.language import Language
from trails.routing import (
    DEFAULT_MARKED_M,
    DEFAULT_MIN_SHARE,
    DEFAULT_RECORDED_M,
    MARKED,
    UNKNOWN,
    UNMARKED,
    ChainRule,
    Network,
    NetworkSource,
    build_chains,
    build_network,
    chains_of,
    label_components,
    no_path_recorded,
    split_source,
    waymarked,
)
from trails.routing.noding import clip_lines
from trails.routing.sources import BRIDGE, FERRY, PATH
from trails.utils.geo import attach_nearest

PARK_NAME = "Lomsdal-Visten"

#: Metric CRS for Norway. The routing module works in it, so lengths and the
#: north-south reach below are already in metres.
METRIC_CRS = "EPSG:25833"

#: County prefix searched when resolving which municipalities the area covers.
FYLKE_PREFIXES = ("18",)

#: The town the graph has to contain: it is where anyone arrives from, and it
#: lies 9.8 km outside the park, which is what sets the extent.
GATEWAY_TOWN = "Mosjøen"

#: Cost factor per source. Priority belongs here and nowhere else — a route
#: through a valley described by three datasets should run on the best-surveyed
#: line, without any of the others being cut away. Keep these close to 1.0, or
#: a route makes real detours to reach a preferred source.
COST_FACTORS = {
    "UT.no": 1.00,
    # Between UT.no's described walks and FKB's surveyed lines: an officially
    # marked route is a better thing to follow than a path that merely exists.
    "Turrutebasen": 1.02,
    "FKB": 1.05,
    "N50 paths": 1.10,
    "OSM": 1.20,
    "N50 roads": 1.30,
}

#: What Turrutebasen's chains carry. It is the one source here that *describes*
#: its routes rather than only drawing them, so this is where a planned route's
#: reporting has to come from. Measured over this zone: ``marking`` is on all 770
#: segments and the maintaining body on all of them, ``signage`` on 88,
#: ``difficulty`` on 27 % and ``trail_significance`` on 31 %. The register's
#: other four fields — season, surface type, trail width and trail type — hold
#: nothing at all here, and a column of nulls on every chain is worse than none.
TRAIL_ATTRIBUTES = ("marking", "signage", "maintenance_responsible", "difficulty", "trail_significance")

#: What a segment takes from the info table, which holds a row per named route a
#: segment belongs to rather than a row per segment. ``trail_name`` is also the
#: identity the chains are built on.
TRAIL_INFO_FIELDS = ("trail_name", "maintenance_responsible", "difficulty", "trail_significance")

#: N50's own account of how a line was captured. It feeds nothing derived and is
#: carried for the popup, where it is worth more than any category computed from
#: it: 47 % of N50's paths in this zone are ``dig``, digitised from a map rather
#: than seen, with capture dates back to 1965 and accuracies as coarse as 50 m.
SURVEY_FIELD = "malemetode"

#: ``rutemerking`` on an N50 path: whether the register states it is waymarked.
N50_MARKED, N50_UNMARKED = "JA", "NEI"

#: The sources whose lines are a record that something is drawn on this ground.
#: Their silence is the whole of what ``no_path_recorded`` says; their lines say
#: nothing, because all four record liberally and three of them are Kartverket.
RECORDED_SOURCES = ("FKB", "N50 paths", "N50 roads", "OSM")

#: The sources that suggest a way rather than record one. Whether anything draws
#: a path is only a question for these: an FKB line *is* the record, so for it
#: the test answers itself.
ROUTE_REGISTERS = ("UT.no", "Turrutebasen")

#: The rule the two derived edge fields are read by: how close counts as running
#: along a marking mask, how close counts as recorded at all, and how much of an
#: edge has to lie that close. All three are fixed by measurement in the
#: decisions document rather than being preferences, so they are not options.
#: They live here as one value because three places need exactly the same
#: numbers — the derivation, the fingerprint that decides whether a cached graph
#: answers for them, and the report. Read from anywhere else, a change to one of
#: them would leave a graph in the cache that no longer matches its own key.
MARKED_M, RECORDED_M, MIN_SHARE = DEFAULT_MARKED_M, DEFAULT_RECORDED_M, DEFAULT_MIN_SHARE


def _join_values(values: pd.Series) -> str | None:
    """Collapse what a Turrutebasen segment carries into one value.

    A segment can belong to several named routes, so the info table holds more
    than one row for it and they need not agree. The chain rule reads several
    identities out of one value, so they are joined the way the road and trail
    layers already write them rather than one being picked — and the same holds
    for what those routes say about themselves: a segment shared by an easy
    route and a strenuous one is both, and reads so.

    Args:
        values: What the routes a segment belongs to say

    Returns:
        The values, joined, or None where the segment has none
    """
    names = sorted({str(value) for value in values.dropna().unique()})
    return " / ".join(names) if names else None


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
    paths = frames["N50 paths"]
    marking = paths["rutemerking"].astype("string").str.strip().str.upper()

    # A code that stopped being a code would empty both masks and cost nothing
    # to notice: every walked edge would come back unknown, and a report full of
    # unknown is exactly what this park looks like anyway. The sibling loader
    # already expands its codes into words, so this is not a distant prospect.
    stated = set(marking.dropna().unique())
    if stated and not stated & {N50_MARKED, N50_UNMARKED}:
        raise ValueError(f"N50 states its marking as {sorted(stated)}, not as {N50_MARKED}/{N50_UNMARKED}")

    marked = pd.concat([frames["Turrutebasen"].geometry, paths.geometry[marking == N50_MARKED]], ignore_index=True)
    recorded = pd.concat([frames[name].geometry for name in RECORDED_SOURCES], ignore_index=True)
    return Masks(
        marked=gpd.GeoSeries(marked, crs=METRIC_CRS),
        unmarked=gpd.GeoSeries(paths.geometry[marking == N50_UNMARKED].reset_index(drop=True), crs=METRIC_CRS),
        recorded=gpd.GeoSeries(recorded, crs=METRIC_CRS),
    )


class Landmarks(NamedTuple):
    """Points the finished graph is checked against.

    Attributes:
        town: The gateway town, which has to sit on the main component
        quays: Named quays from the place-name register, most of which are
            reachable only by boat
    """

    town: gpd.GeoDataFrame
    quays: gpd.GeoDataFrame


def zone_around(park: gpd.GeoDataFrame, distance_km: float) -> gpd.GeoDataFrame:
    """Grow the park outline by a distance, keeping the interior.

    Args:
        park: Park boundary in EPSG:4326
        distance_km: Width of the approach zone in kilometres

    Returns:
        The park and its approach zone as one polygon, in EPSG:4326
    """
    metric = park.to_crs(METRIC_CRS)
    return gpd.GeoDataFrame(geometry=metric.buffer(distance_km * 1000), crs=METRIC_CRS).to_crs("EPSG:4326")


def load_sources(args: argparse.Namespace, zone: gpd.GeoDataFrame) -> tuple[list[NetworkSource], Landmarks]:
    """Load every dataset the network is built from.

    Args:
        args: Parsed command line
        zone: Park and approach zone, in EPSG:4326

    Returns:
        The sources, and the landmarks the result is checked against
    """
    min_lon, min_lat, max_lon, max_lat = (float(value) for value in zone.total_bounds)
    bounds = (min_lon, min_lat, max_lon, max_lat)
    extent = zone.union_all()
    codes = kommuneinfo.Source(cache_dir=args.cache_dir).intersecting(zone, fylke=FYLKE_PREFIXES)
    download = args.force_download

    print("\nLoading UT.no routes...")
    catalogue = ut.load_catalogue(args.ut_routes)
    ut_routes = ut.Source(cache_dir=args.cache_dir).load_routes(catalogue, force_download=download)

    print("\nLoading Turrutebasen...")
    turrutebasen = GeonorgeSource(cache_dir=args.cache_dir).load_turrutebasen(target_crs="EPSG:4326", language=Language.EN, force_download=download)
    routes = turrutebasen.spatial_layers["hiking_trail_centerline"]
    info = turrutebasen.attribute_tables["hiking_trail_info_table"]
    # A segment can belong to several named routes, so the info table holds more
    # than one row per segment; the chain rule reads them all out of one value.
    described = info.groupby("hiking_trail_fk")[list(TRAIL_INFO_FIELDS)].agg(_join_values)
    merged = routes.merge(described, left_on="local_id", right_index=True, how="left")
    marked = clip_lines(gpd.GeoDataFrame(merged, geometry="geometry", crs=routes.crs), extent)
    named = marked[marked["trail_name"].notna()]
    print(f"  {len(marked):,} marked route segments in the zone, {len(named):,} of them named")

    print("\nLoading detailed FKB paths...")
    fkb = traktorvegsti.Source(cache_dir=args.cache_dir).fetch_paths(bounds, force_download=download)
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
        max_distance_m=args.trail_name_m,
        metric_crs=METRIC_CRS,
        # Nearness alone hands a route's name to every side path that meets it.
        min_overlap=0.5,
    )
    matched = fkb["route_name"].notna()
    matched_km = fkb[matched].to_crs(METRIC_CRS).length.sum() / 1000
    print(f"  {before:,} paths in the zone, {int(matched.sum()):,} named from Turrutebasen ({matched_km:,.0f} km)")

    print("\nLoading N50 paths, roads and ferries...")
    n50_source = n50.Source(cache_dir=args.cache_dir)
    paths = clip_lines(n50_source.load_paths(codes, force_download=download), extent)
    roads = clip_lines(n50_source.load_roads(codes, force_download=download), extent)
    ferries = clip_lines(n50_source.load_ferries(codes, force_download=download), extent)

    names_source = stedsnavn.Source(cache_dir=args.cache_dir)
    road_names = names_source.load_road_names(codes, force_download=download)
    roads = attach_nearest(
        roads,
        road_names,
        {"road_id": "road_id", "name": "road_name"},
        max_distance_m=args.road_name_m,
        metric_crs=METRIC_CRS,
        min_overlap=0.5,
    )
    print(f"  {int(roads['road_id'].notna().sum()):,} of {len(roads):,} road fragments named from SSR")

    print("\nLoading OpenStreetMap paths...")
    osm = clip_lines(overpass.Source(cache_dir=args.cache_dir).fetch_paths(bounds, force_download=download), extent)

    print("\nLoading place names (SSR)...")
    places = names_source.load_places(codes, name_types=None, force_download=download)
    quays = gpd.clip(places[places["kind"].isin(stedsnavn.QUAY_NAME_TYPES)], zone)
    towns = places[(places["kind"].isin(stedsnavn.SETTLEMENT_NAME_TYPES)) & (places["name"] == GATEWAY_TOWN)]
    print(f"  named quays in the zone: {len(quays)} | {GATEWAY_TOWN}: {len(towns)} position(s)")

    sources = [
        # Published as whole trips, and a trip is already linear and already the
        # unit a reader means. Noding these against each other would shatter 35
        # routes into 2,411 scraps, because they overlap each other heavily.
        NetworkSource(
            "UT.no",
            ut_routes,
            cost_factor=COST_FACTORS["UT.no"],
            identity_field="name",
            attributes=("category",),
            keep_whole=True,
            node_simplify_m=args.route_noding_m,
        ),
        # The official marked routes. Their published unit is the named route,
        # which is what the identity rule keeps whole: a route carries on through
        # every crossing of it and ends only where it genuinely branches.
        NetworkSource(
            "Turrutebasen",
            marked,
            cost_factor=COST_FACTORS["Turrutebasen"],
            identity_field="trail_name",
            attributes=TRAIL_ATTRIBUTES,
            node_simplify_m=args.route_noding_m,
        ),
        NetworkSource("FKB", fkb, cost_factor=COST_FACTORS["FKB"], identity_field="route_name", attributes=("typeveg",)),
        NetworkSource("N50 paths", paths, cost_factor=COST_FACTORS["N50 paths"], attributes=("typeveg", "rutemerking", SURVEY_FIELD)),
        # Roads are named by the register, and the register id is what says two
        # fragments are the same road; the name repeats across the county.
        NetworkSource(
            "N50 roads",
            roads,
            cost_factor=COST_FACTORS["N50 roads"],
            identity_field="road_id",
            attributes=("vegkategori", "road_name", SURVEY_FIELD),
        ),
        NetworkSource("OSM", osm, cost_factor=COST_FACTORS["OSM"], identity_field="name", attributes=("highway",)),
        # Nobody walks these, and without them the whole west of the park — where
        # the UT.no routes start — cannot be reached at all.
        NetworkSource("Ferries", ferries, kind=FERRY, attributes=("typeveg", SURVEY_FIELD)),
    ]
    return sources, Landmarks(town=towns, quays=quays)


def fingerprint(sources: list[NetworkSource], masks: Masks, args: argparse.Namespace) -> str:
    """Summarise what went into a build, so a cached one can be recognised.

    Args:
        sources: The datasets
        masks: What the derived edge fields were decided against
        args: Parsed command line, for the parameters that shape the result

    Returns:
        Short hash naming this build
    """
    # Every parameter that shapes the graph, including the two join distances:
    # they change no geometry, only which chains carry which identity, so a row
    # count and a total length cannot tell two of these builds apart.
    parts = [
        f"{args.approach_km}|{args.stroke_deg}|{args.probe_m}|{args.bridge_m}"
        f"|{args.ferry_cost_km}|{args.route_noding_m}|{args.road_name_m}|{args.trail_name_m}",
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


def chain_report(sources: list[NetworkSource], clip: gpd.GeoDataFrame, args: argparse.Namespace) -> pd.DataFrame:
    """Count each source's chains under both rules.

    Breaking at every junction is the baseline: it is what ``linemerge`` alone
    gives, and it cuts a road into a scrap at every side turning. The stroke rule
    is what makes a chain something worth clicking.

    Args:
        sources: The datasets
        clip: Extent to cut them to
        args: Parsed command line

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
        angle_only = build_chains(pieces, anonymous, rule=ChainRule.STROKE, stroke_angle_deg=args.stroke_deg, probe_m=args.probe_m)

        chains = chains_of(source, clip, rule=ChainRule.STROKE, stroke_angle_deg=args.stroke_deg, probe_m=args.probe_m, metric_crs=METRIC_CRS)
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


def build(sources: list[NetworkSource], masks: Masks, clip: gpd.GeoDataFrame, args: argparse.Namespace) -> tuple[Network, pd.DataFrame]:
    """Build the network, or read back the last build of the same inputs.

    Elevation comes later and will make this expensive; the cache is here from
    the start so that a rebuild of an unchanged graph costs nothing.

    Args:
        sources: The datasets
        masks: What the derived edge fields are decided against
        clip: Extent to cut them to
        args: Parsed command line

    Returns:
        The network and the per-source chain counts
    """
    store = cache_module.Object(cache_dir=str(Path(args.cache_dir) / "objects"))
    key = f"route_graph_{PARK_NAME.lower()}_{fingerprint(sources, masks, args)}"

    if not args.rebuild and store.exists(key):
        print(f"\nReading the graph back from the cache ({key})...")
        cached: dict[str, Any] = store.load(key)
        return cached["network"], cached["chains"]

    print("\nBuilding chains per source...")
    chains = chain_report(sources, clip, args)

    print("Noding every source against every other...")
    network = build_network(
        sources,
        clip,
        metric_crs=METRIC_CRS,
        stroke_angle_deg=args.stroke_deg,
        probe_m=args.probe_m,
        bridge_m=args.bridge_m,
        ferry_cost_m=args.ferry_cost_km * 1000,
    )

    print("Asking every edge what the ground it runs over is recorded as...")
    network = replace(network, edges=derive(network.edges, masks))

    store.save(key, {"network": network, "chains": chains}, metadata={"park": PARK_NAME, "approach_km": args.approach_km})
    return network, chains


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


def reach_across(edges: gpd.GeoDataFrame, park: gpd.GeoDataFrame) -> float:
    """Measure how far a set of edges carries across the park, north to south.

    The share of the network's *length* in one component is a misleading figure
    here — hundreds of isolated stubs recorded out in the terrain drag it down.
    What decides whether a traverse can be planned is how far the component
    reaches, and that is this.

    Args:
        edges: Edges to measure, in a metric CRS
        park: Park boundary

    Returns:
        North-south extent in metres of the part of them inside the park
    """
    inside = gpd.clip(edges, park.to_crs(METRIC_CRS))
    if inside.empty:
        return 0.0
    _, south, _, north = inside.total_bounds
    return float(north - south)


def report(
    network: Network,
    chains: pd.DataFrame,
    sources: list[NetworkSource],
    park: gpd.GeoDataFrame,
    landmarks: Landmarks,
    args: argparse.Namespace,
) -> None:
    """Print everything the phase is checked against.

    Args:
        network: The finished network
        chains: Per-source chain counts
        sources: The datasets, for what each of them carries
        park: Park boundary
        landmarks: Points to check the main component against
        args: Parsed command line
    """
    edges = network.edges
    on_land = edges[edges["kind"] != FERRY]

    print("\n" + "=" * 78)
    print("CHAINS PER SOURCE")
    print("=" * 78)
    printable = chains.copy()
    printable["km"] = printable["km"].round(0)
    printable["mean chain m"] = printable["mean chain m"].round(0)
    print(printable.to_string(index=False))
    print(f"  total, broken at every junction: {chains['at every junction'].sum():,}")
    print(f"  total, with the {args.stroke_deg:g} deg angle alone: {chains['angle only'].sum():,}")
    print(f"  total, identity first, then the angle: {chains['with identity'].sum():,}  <- what the graph is built from")

    print("\n" + "=" * 78)
    print("ROUTING GRAPH")
    print("=" * 78)
    crossed_km = edges.loc[edges["kind"] == FERRY, "length_m"].sum() / 1000
    print(f"  chains          {len(network.chains):,}")
    print(f"  edges           {len(edges):,}  ({int((edges['kind'] == BRIDGE).sum()):,} of them bridged loose ends)")
    print(f"  nodes           {len(network.nodes):,}")
    print(f"  vertices        {int(shapely.get_num_coordinates(edges.geometry).sum()):,}")
    print(f"  length          {edges['length_m'].sum() / 1000:,.0f} km, of which {crossed_km:,.0f} km by boat")
    print(f"  mean edge       {edges['length_m'].mean():.0f} m")

    park_extent = float(park.to_crs(METRIC_CRS).total_bounds[3] - park.to_crs(METRIC_CRS).total_bounds[1])
    town = landmarks.town.to_crs(METRIC_CRS)

    for label, subset in (("land only", on_land), ("with ferries", edges)):
        component = label_components(subset)
        main = subset[component == 0]
        share = main["length_m"].sum() / subset["length_m"].sum() * 100
        reach = reach_across(main, park)

        print(f"\n  {label}")
        print(f"    components         {component.nunique():,}")
        print(f"    largest            {main['length_m'].sum() / 1000:,.0f} km = {share:.0f} % of the network")
        print(f"    its reach          {reach / 1000:,.1f} km = {reach / park_extent * 100:.0f} % of the park's {park_extent / 1000:,.1f} km")

        reachable = _within(landmarks.quays, main, args.reach_m)
        print(f"    quays reached      {reachable} of {len(landmarks.quays)} (within {args.reach_m:g} m)")
        if len(town):
            distance = main.distance(town.geometry.iloc[0]).min()
            print(f"    {GATEWAY_TOWN:<18} {distance:,.2f} m away{' — it sits on it' if distance < args.reach_m else ''}")

    print("\n  cost")
    print(f"    {'source':<12} {'factor':>7} {'edges':>9} {'km':>8}")
    for source, group in edges.groupby("source"):
        factor = "flat" if group["kind"].iloc[0] == FERRY else f"{(group['cost'] / group['length_m']).mean():.2f}"
        print(f"    {str(source):<12} {factor:>7} {len(group):>9,} {group['length_m'].sum() / 1000:>8,.0f}")

    report_attributes(network.chains, sources)
    report_derived(network)


def _filled(values: pd.Series) -> float:
    """Measure how much of a column actually says something.

    ``notna`` is not the test. These registers write an empty string where they
    have nothing, and counting those once made a set of FKB's fields look fully
    populated when they are really at 3-6 %.

    Args:
        values: One column

    Returns:
        Share of its rows carrying a value, between 0 and 1
    """
    if values.empty:
        return 0.0
    said = values.notna() & (values.astype("string").str.strip() != "")
    return float(said.sum()) / len(values)


def report_attributes(chains: gpd.GeoDataFrame, sources: list[NetworkSource]) -> None:
    """Print what each source's chains carry beyond their geometry.

    An edge names its chain, so a route reads any of this through ``chain_id``
    in one lookup. Nothing here is copied onto the edges.

    Args:
        chains: The chains of every source
        sources: The datasets, for which columns each of them promised
    """
    print("\n" + "=" * 78)
    print("WHAT THE CHAINS CARRY")
    print("=" * 78)
    for source in sources:
        held = chains[chains["source"] == source.name]
        # A source's identity column arrives under the one name every chain
        # carries it as, whatever the source called it.
        carried = [("identity", source.identity_field), *((column, column) for column in source.attributes)]
        described = " · ".join(f"{label} {_filled(held[column]):.0%}" for column, label in carried if label)
        print(f"  {source.name:<13} {len(held):>6,} chains   {described or 'nothing but its geometry'}")


def report_derived(network: Network) -> None:
    """Print the two fields the edges carry about the ground they run over.

    Args:
        network: The finished network
    """
    walked = network.edges[network.edges["kind"] == PATH]
    identities = network.chains.set_index("chain_id")["identity"]

    print("\n" + "=" * 78)
    print("WHAT THE GROUND SAYS, PER EDGE")
    print("=" * 78)
    print("  Both are derived from masks over the raw sources, never from an edge's own")
    print("  attributes, and both leave out the ferries and the bridged connectors: a")
    print("  crossing is not walking, and nobody drew a connector.")

    print(f"\n  waymarked — at least {MIN_SHARE:.0%} of the edge within {MARKED_M:g} m of a mask")
    print(f"    {'source':<13} {'marked':>18} {'unmarked':>18} {'unknown':>18} {'km':>9}")
    for source, group in walked.groupby("source"):
        total = group["length_m"].sum() / 1000
        cells = ""
        for answer in (MARKED, UNMARKED, UNKNOWN):
            distance = group.loc[group["waymarked"] == answer, "length_m"].sum() / 1000
            cells += f" {distance:>9,.1f} km {distance / total * 100 if total else 0:>3.0f} %"
        print(f"    {str(source):<13}{cells} {total:>9,.0f}")

    print(f"\n  no path recorded — less than {MIN_SHARE:.0%} of the edge within {RECORDED_M:g} m of any of")
    print(f"  {', '.join(RECORDED_SOURCES)}. Their silence is evidence; their lines are not,")
    print("  so this says nothing whatever about the ground it leaves unflagged.")
    flagged = walked[walked["no_path_recorded"].fillna(False).astype(bool)]
    for source, group in walked.groupby("source"):
        found = flagged[flagged["source"] == source]
        print(f"    {str(source):<13} {found['length_m'].sum() / 1000:>8,.1f} km of {group['length_m'].sum() / 1000:>7,.0f} ({len(found):,} edges)")

    print("\n    where it falls, for the sources that suggest a way rather than record one")
    registers = walked[walked["source"].isin(ROUTE_REGISTERS)]
    whole = registers.groupby(registers["chain_id"].map(identities))["length_m"].sum().to_dict()
    on_nothing = flagged[flagged["source"].isin(ROUTE_REGISTERS)]
    if on_nothing.empty:
        print("      nothing")
        return
    per_route = on_nothing.groupby(on_nothing["chain_id"].map(identities))["length_m"].sum().sort_values(ascending=False)
    for name, distance in per_route.head(8).items():
        print(f"      {str(name)[:52]:<52} {distance / 1000:>5,.1f} of {whole[name] / 1000:>5,.1f} km")
    if len(per_route) > 8:
        print(f"      {'the other ' + str(len(per_route) - 8) + ' together':<52} {per_route.iloc[8:].sum() / 1000:>5,.1f} km")


def _within(points: gpd.GeoDataFrame, edges: gpd.GeoDataFrame, distance_m: float) -> int:
    """Count how many points a set of edges passes close to.

    Args:
        points: Points to check
        edges: Edges to measure against, in a metric CRS
        distance_m: How close counts as reached

    Returns:
        Number of points reached
    """
    if points.empty or edges.empty:
        return 0
    tree = shapely.STRtree(edges.geometry.to_numpy())
    found = tree.query(points.to_crs(METRIC_CRS).geometry.to_numpy(), predicate="dwithin", distance=float(distance_m))
    return int(np.unique(found[0]).size)


def main() -> int:
    """Build the graph and report its statistics.

    Returns:
        Process exit code
    """
    repo_root = Path(__file__).resolve().parents[2]

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache-dir", default=str(repo_root / ".cache"), help="Cache directory for downloaded data and built graphs")
    # Not a preference: Mosjøen has to be inside the graph and lies 9.8 km out.
    parser.add_argument("--approach-km", type=float, default=15.0, help="Width of the approach zone around the park (km)")
    parser.add_argument(
        "--ut-routes",
        default=str(repo_root / "analysis" / "routes" / "lomsdal-visten-ut-routes.toml"),
        help="Catalogue of UT.no routes to include",
    )
    parser.add_argument("--stroke-deg", type=float, default=45.0, help="Largest deflection accepted as a way continuing through a junction")
    parser.add_argument("--probe-m", type=float, default=5.0, help="How far either side of a junction the direction is read")
    parser.add_argument("--bridge-m", type=float, default=25.0, help="How far a loose end may reach for another node")
    parser.add_argument("--ferry-cost-km", type=float, default=5.0, help="What a ferry crossing costs, as kilometres walked")
    # Off, because it was measured and it buys nothing that is missing. The two
    # published sources are recorded at GPS density and weave across the lines
    # they run along, so noding a simplified copy of them does cut the graph
    # from 234,363 edges to 166,900. But the chains, the components, the reach
    # and the quays all come out identical, both budgets hold without it — 3.3 MB
    # against 5, two minutes against single-digit — and it costs accuracy where
    # it is least affordable: at 8 m, 4,086 nodes (4.5 %) have two edges meeting
    # on them whose geometries lie more than a metre apart, 191 more than five,
    # the worst 7.55 m. A route is stitched from edges, so those are gaps in the
    # exported track. Without it the worst is 2.2 cm.
    parser.add_argument(
        "--route-noding-m",
        type=float,
        default=0.0,
        help="Node the published route datasets by a simplified copy of themselves (m); their own geometry is kept either way",
    )
    parser.add_argument("--road-name-m", type=float, default=25.0, help="How far a road fragment may look for its name in the register (m)")
    parser.add_argument("--trail-name-m", type=float, default=25.0, help="How far an FKB path may look for a Turrutebasen route name (m)")
    parser.add_argument("--reach-m", type=float, default=150.0, help="How close a component must pass a quay or town to count as reaching it")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild the graph even if a cached one matches")
    parser.add_argument("--force-download", action="store_true", help="Re-download source data instead of using the cache")
    args = parser.parse_args()

    print("=" * 78)
    print("LOMSDAL-VISTEN ROUTING GRAPH")
    print("=" * 78)

    park = naturbase.Source(cache_dir=args.cache_dir).find_one(PARK_NAME, layer=naturbase.Layer.NATIONAL_PARK)
    zone = zone_around(park, args.approach_km)

    sources, landmarks = load_sources(args, zone)
    masks = masks_from(sources)
    network, chains = build(sources, masks, zone, args)
    report(network, chains, sources, park, landmarks, args)

    print("\n" + "=" * 78)
    print("Sources: Turrutebasen (CC0) | N50 Kartdata (CC BY 4.0) | Traktorveg og Skogsbilveg (CC BY 4.0)")
    print("         Stedsnavn/SSR (CC BY 4.0), all Kartverket | Naturbase (NLOD) | OpenStreetMap (ODbL)")
    print(f"         {ut.METADATA.attribution} ({ut.METADATA.license}) — non-commercial, unlike the rest")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
