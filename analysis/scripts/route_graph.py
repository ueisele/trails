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
from trails.routing import ChainRule, Network, NetworkSource, build_chains, build_network, chains_of, label_components, split_source
from trails.routing.noding import clip_lines
from trails.routing.sources import BRIDGE, FERRY
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


def _join_names(values: pd.Series) -> str | None:
    """Collapse the names a Turrutebasen segment carries into one value.

    A segment can belong to several named routes. The chain rule reads several
    identities out of one value, so they are joined the way the road and trail
    layers already write them rather than one being picked.

    Args:
        values: Names of the routes a segment belongs to

    Returns:
        The names, joined, or None where the segment has none
    """
    names = sorted({str(value) for value in values.dropna().unique()})
    return " / ".join(names) if names else None


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
    merged = routes.merge(info.groupby("hiking_trail_fk")["trail_name"].apply(_join_names), left_on="local_id", right_index=True, how="left")
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
            node_simplify_m=args.route_noding_m,
        ),
        NetworkSource("FKB", fkb, cost_factor=COST_FACTORS["FKB"], identity_field="route_name", attributes=("typeveg",)),
        NetworkSource("N50 paths", paths, cost_factor=COST_FACTORS["N50 paths"], attributes=("typeveg", "rutemerking")),
        # Roads are named by the register, and the register id is what says two
        # fragments are the same road; the name repeats across the county.
        NetworkSource("N50 roads", roads, cost_factor=COST_FACTORS["N50 roads"], identity_field="road_id", attributes=("vegkategori", "road_name")),
        NetworkSource("OSM", osm, cost_factor=COST_FACTORS["OSM"], identity_field="name", attributes=("highway",)),
        # Nobody walks these, and without them the whole west of the park — where
        # the UT.no routes start — cannot be reached at all.
        NetworkSource("Ferries", ferries, kind=FERRY, attributes=("typeveg",)),
    ]
    return sources, Landmarks(town=towns, quays=quays)


def fingerprint(sources: list[NetworkSource], args: argparse.Namespace) -> str:
    """Summarise what went into a build, so a cached one can be recognised.

    Args:
        sources: The datasets
        args: Parsed command line, for the parameters that shape the result

    Returns:
        Short hash naming this build
    """
    # Every parameter that shapes the graph, including the two join distances:
    # they change no geometry, only which chains carry which identity, so a row
    # count and a total length cannot tell two of these builds apart.
    parts = [
        f"{args.approach_km}|{args.stroke_deg}|{args.probe_m}|{args.bridge_m}"
        f"|{args.ferry_cost_km}|{args.route_noding_m}|{args.road_name_m}|{args.trail_name_m}"
    ]
    for source in sources:
        length = source.gdf.to_crs(METRIC_CRS).length.sum() if len(source.gdf) else 0.0
        # And the values the chains are built from, not only the geometry they
        # are built along. The road names come from SSR and the route names from
        # Turrutebasen, so neither shows up in this source's own row count or
        # length — yet a change in either moves where a chain ends.
        parts.append(f"{source.name}:{len(source.gdf)}:{length:.0f}:{source.cost_factor}:{source.keep_whole}:{_values_digest(source)}")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]


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
        digest.update(source.gdf[column].astype(str).str.cat(sep="\x00").encode())
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


def build(sources: list[NetworkSource], clip: gpd.GeoDataFrame, args: argparse.Namespace) -> tuple[Network, pd.DataFrame]:
    """Build the network, or read back the last build of the same inputs.

    Elevation comes later and will make this expensive; the cache is here from
    the start so that a rebuild of an unchanged graph costs nothing.

    Args:
        sources: The datasets
        clip: Extent to cut them to
        args: Parsed command line

    Returns:
        The network and the per-source chain counts
    """
    store = cache_module.Object(cache_dir=str(Path(args.cache_dir) / "objects"))
    key = f"route_graph_{PARK_NAME.lower()}_{fingerprint(sources, args)}"

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
    store.save(key, {"network": network, "chains": chains}, metadata={"park": PARK_NAME, "approach_km": args.approach_km})
    return network, chains


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


def report(network: Network, chains: pd.DataFrame, park: gpd.GeoDataFrame, landmarks: Landmarks, args: argparse.Namespace) -> None:
    """Print everything the phase is checked against.

    Args:
        network: The finished network
        chains: Per-source chain counts
        park: Park boundary
        landmarks: Points to check the main component against
        args: Parsed command line
    """
    edges = network.edges
    walking = edges[edges["kind"] != FERRY]

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

    for label, subset in (("land only", walking), ("with ferries", edges)):
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
    network, chains = build(sources, zone, args)
    report(network, chains, park, landmarks, args)

    print("\n" + "=" * 78)
    print("Sources: Turrutebasen (CC0) | N50 Kartdata (CC BY 4.0) | Traktorveg og Skogsbilveg (CC BY 4.0)")
    print("         Stedsnavn/SSR (CC BY 4.0), all Kartverket | Naturbase (NLOD) | OpenStreetMap (ODbL)")
    print(f"         {ut.METADATA.attribution} ({ut.METADATA.license}) — non-commercial, unlike the rest")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
