"""Build the routing graph for Lomsdal-Visten and report what it looks like.

Nothing is drawn here. This is the foundation the route planning stands on, and
it is verifiable on its own numbers: how many chains each source falls into, how
many edges the merged graph holds, how much of the network hangs together, how
far that reach carries across the park, and whether the coast is reachable at
all without the ferries.

The graph itself is built by :mod:`trails.network.norway`, which knows nothing
about this park, on top of :mod:`trails.routing`, which knows nothing about
Kartverket either. What is left here is the park, the landmarks the result is
checked against, and the report.

Usage::

    uv run python analysis/scripts/route_graph.py
    uv run python analysis/scripts/route_graph.py --approach-km 5 --rebuild
"""

import argparse
from pathlib import Path
from typing import NamedTuple

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from trails.io.sources import hoydedata, naturbase, stedsnavn, ut
from trails.network.norway import (
    MARKED_M,
    METRIC_CRS,
    MIN_SHARE,
    RECORDED_M,
    RECORDED_SOURCES,
    ROUTE_REGISTERS,
    TURRUTEBASEN,
    Params,
    build,
    load_sources,
    masks_from,
    zone_around,
)
from trails.routing import MARKED, UNKNOWN, UNMARKED, Network, NetworkSource, label_components
from trails.routing.sources import BRIDGE, FERRY, PATH

PARK_NAME = "Lomsdal-Visten"

#: The town the graph has to contain: it is where anyone arrives from, and it
#: lies 9.8 km outside the park, which is what sets the extent.
GATEWAY_TOWN = "Mosjøen"

#: The route the elevation work is checked against. It resolves to *three*
#: chains — UT.no, Turrutebasen and FKB all draw it, all 20.48 km over the same
#: ground — and three digitisations give three ascents. A single figure against
#: a name that resolves three ways is not a check, so all three are printed.
#:
#: Matched on the stem, because the two registers do not spell it the same way:
#: UT.no publishes *Sjøbergmarsjruta* and Turrutebasen *Sjøbergmarsjen*, which
#: reaches FKB through the route-name join. Searching for either in full finds
#: one digitisation and misses two, and would have looked like a check.
CHECK_ROUTE = "Sjøbergmarsj"


class Landmarks(NamedTuple):
    """Points the finished graph is checked against.

    Attributes:
        town: The gateway town, which has to sit on the main component
        quays: Named quays from the place-name register, most of which are
            reachable only by boat
    """

    town: gpd.GeoDataFrame
    quays: gpd.GeoDataFrame


def load_landmarks(params: Params, codes: list[str], zone: gpd.GeoDataFrame) -> Landmarks:
    """Load the places the main component is measured against.

    Args:
        params: What decides the build
        codes: Municipalities the register is ordered per
        zone: Park and approach zone, in EPSG:4326

    Returns:
        The gateway town and the named quays in the zone
    """
    print("\nLoading place names (SSR)...")
    places = stedsnavn.Source(cache_dir=params.cache_dir).load_places(codes, name_types=None, force_download=params.force_download)
    quays = gpd.clip(places[places["kind"].isin(stedsnavn.QUAY_NAME_TYPES)], zone)
    towns = places[(places["kind"].isin(stedsnavn.SETTLEMENT_NAME_TYPES)) & (places["name"] == GATEWAY_TOWN)]
    print(f"  named quays in the zone: {len(quays)} | {GATEWAY_TOWN}: {len(towns)} position(s)")
    return Landmarks(town=towns, quays=quays)


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
    params: Params,
    reach_m: float,
) -> None:
    """Print everything the phase is checked against.

    Args:
        network: The finished network
        chains: Per-source chain counts
        sources: The datasets, for what each of them carries
        park: Park boundary
        landmarks: Points to check the main component against
        params: What decided the build
        reach_m: How close a component must pass a quay to count as reaching it
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
    print(f"  total, with the {params.stroke_deg:g} deg angle alone: {chains['angle only'].sum():,}")
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

        reachable = _within(landmarks.quays, main, reach_m)
        print(f"    quays reached      {reachable} of {len(landmarks.quays)} (within {reach_m:g} m)")
        if len(town):
            distance = main.distance(town.geometry.iloc[0]).min()
            print(f"    {GATEWAY_TOWN:<18} {distance:,.2f} m away{' — it sits on it' if distance < reach_m else ''}")

    print("\n  cost")
    print(f"    {'source':<12} {'factor':>7} {'edges':>9} {'km':>8}")
    for source, group in edges.groupby("source"):
        factor = "flat" if group["kind"].iloc[0] == FERRY else f"{(group['cost'] / group['length_m']).mean():.2f}"
        print(f"    {str(source):<12} {factor:>7} {len(group):>9,} {group['length_m'].sum() / 1000:>8,.0f}")

    report_attributes(network.chains, sources)
    report_derived(network)
    report_elevation(network, params)


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


def report_elevation(network: Network, params: Params) -> None:
    """Print what the ground under the network came out as.

    Args:
        network: The finished network
        params: What decided the build
    """
    edges, chains = network.edges, network.chains
    series = list(edges["elevations"])
    samples = int(sum(len(values) for values in series))
    read = int(sum(int(np.count_nonzero(~np.isnan(values))) for values in series))

    print("\n" + "=" * 78)
    print("ELEVATION")
    print("=" * 78)
    print(f"  Sampled every {params.elevation_step_m:g} m along every edge but the crossings — there is no")
    print("  ground under a ferry and the endpoint answers over water with a depth. An")
    print("  inferred connector is sampled: nobody drew it, but there is ground under it.")
    print(f"  Ascent is reported with gains under {params.ascent_threshold_m:g} m ignored.")

    walked = edges[edges["kind"] != FERRY]
    print(f"\n  samples          {samples:,} over {len(walked):,} edges")
    print(f"  read             {read:,} ({read / samples * 100 if samples else 0:.2f} %)")
    print(f"  no reading       {samples - read:,} — over water, or outside the model's coverage")
    # A figure of nothing would read as flat ground at sea level, which is what
    # the edges and chains counted here decline to say. Crossings are left out:
    # they were never asked about, so carrying no figure is not a gap.
    unread = chains[(chains["kind"] != FERRY) & chains["ascent"].isna()]
    print(f"  nothing read     {int(walked['ascent'].isna().sum()):,} walked edges and {len(unread):,} chains carry no figure at all")

    heights = np.concatenate([values for values in series if len(values)]) if samples else np.empty(0)
    if read:
        print(f"  lowest           {np.nanmin(heights):,.1f} m   <- a profile touching -276 m means datakilde is not checked")
        print(f"  highest          {np.nanmax(heights):,.1f} m")

    print("\n  per source, computed over each chain's full series")
    print(f"    {'source':<13} {'chains':>7} {'km':>8} {'ascent m':>10} {'descent m':>10} {'highest':>8} {'lowest':>8} {'nothing read':>13}")
    for source, group in chains.groupby("source"):
        climbed, fell = group["ascent"].sum(), group["descent"].sum()
        high, low = group["high_m"].max(), group["low_m"].min()
        missing = int(group["ascent"].isna().sum())
        print(
            f"    {str(source):<13} {len(group):>7,} {group['length_m'].sum() / 1000:>8,.0f} {climbed:>10,.0f} {fell:>10,.0f} "
            f"{high:>8,.0f} {low:>8,.1f} {missing:>13,}"
        )

    # Printed side by side because the two are easy to confuse and the second is
    # not an approximation of the first. The threshold restarts at every edge
    # boundary, and 42 % of the edges are shorter than the threshold is tall.
    per_chain = chains["ascent"].sum()
    per_edge = edges["ascent"].sum()
    share = per_edge / per_chain * 100 if per_chain else 0
    print(f"\n  ascent per chain, over each chain's full series   {per_chain / 1000:>8,.1f} km   <- the figure to show")
    print(f"  the same edges' own figures, summed               {per_edge / 1000:>8,.1f} km   <- {share:.0f} % of it, and no estimate of it")

    report_check_route(chains)


def report_check_route(chains: gpd.GeoDataFrame) -> None:
    """Print every chain the checked route resolves to.

    Args:
        chains: The chains of every source
    """
    named = chains[chains["identity"].astype("string").str.contains(CHECK_ROUTE, na=False)]
    print(f"\n  {CHECK_ROUTE}… — one route, three digitisations of the same ground")
    if named.empty:
        print("    nothing carries that name")
        return
    print(f"    {'chain':<38} {'source':<13} {'identity':<18} {'km':>6} {'ascent':>8} {'descent':>8} {'high':>6} {'low':>6}")
    for _, chain in named.sort_values("source").iterrows():
        print(
            f"    {chain['chain_id']:<38} {chain['source']:<13} {str(chain['identity'])[:18]:<18} {chain['length_m'] / 1000:>6,.2f} "
            f"{chain['ascent']:>8,.0f} {chain['descent']:>8,.0f} {chain['high_m']:>6,.0f} {chain['low_m']:>6,.1f}"
        )


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
    # Offered so the invariance the ascent threshold exists for can be checked
    # from the product rather than from a script beside it: the same route has
    # to read the same climb sampled every 5, 10 or 15 m.
    #
    # Coarsening it is not free, and it is worth knowing before it is run: the
    # samples are spread evenly between an edge's ends rather than laid at a
    # fixed step, so a coarser set is a subset of the finer one only where the
    # two counts divide. Measured over this network, a 10 m run asked about
    # 189,616 coordinates the 5 m run had not, and a 15 m one 127,943 — four
    # and two and a half minutes against a public endpoint. Not much beside the
    # first run's twenty thousand requests, and not nothing either.
    parser.add_argument("--elevation-step-m", type=float, default=5.0, help="How far apart the height samples are laid along an edge (m)")
    parser.add_argument("--road-name-m", type=float, default=25.0, help="How far a road fragment may look for its name in the register (m)")
    parser.add_argument("--trail-name-m", type=float, default=25.0, help="How far an FKB path may look for a Turrutebasen route name (m)")
    parser.add_argument("--reach-m", type=float, default=150.0, help="How close a component must pass a quay or town to count as reaching it")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild the graph even if a cached one matches")
    parser.add_argument("--force-download", action="store_true", help="Re-download source data instead of using the cache")
    args = parser.parse_args()

    print("=" * 78)
    print("LOMSDAL-VISTEN ROUTING GRAPH")
    print("=" * 78)

    params = Params.from_args(args)
    park = naturbase.Source(cache_dir=params.cache_dir).find_one(PARK_NAME, layer=naturbase.Layer.NATIONAL_PARK)
    zone = zone_around(park, params.approach_km)

    loaded = load_sources(params, zone)
    landmarks = load_landmarks(params, loaded.municipalities, zone)
    masks = masks_from(loaded.sources)
    network, chains = build(loaded.sources, masks, zone, params, name=PARK_NAME.lower())
    report(network, chains, loaded.sources, park, landmarks, params, args.reach_m)

    print("\n" + "=" * 78)
    print(f"Sources: Turrutebasen {loaded.versions[TURRUTEBASEN]} (CC0) | N50 Kartdata (CC BY 4.0) | Traktorveg og Skogsbilveg (CC BY 4.0)")
    # Every figure in the ELEVATION section comes out of this one, and CC BY
    # asks to be named for it.
    print(f"         Stedsnavn/SSR (CC BY 4.0) | {hoydedata.METADATA.name} ({hoydedata.METADATA.license}), all Kartverket")
    print("         Naturbase (NLOD) | OpenStreetMap (ODbL)")
    print(f"         {ut.METADATA.attribution} ({ut.METADATA.license}) — non-commercial, unlike the rest")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
