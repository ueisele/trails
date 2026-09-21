"""The shore, open water, streams and the ground joining separate water bodies."""

import time
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring

from trails.network import graphs
from trails.routing.coverage import CHAIN_COVERAGE_COLUMNS, chain_coverage
from trails.routing.graph import DEFAULT_BRIDGE_COST_FACTOR, Network, build_network
from trails.routing.noding import lines_of, working_lines
from trails.routing.sources import BRIDGE, PADDLE, PATH, NetworkSource

SHORE = "Shore"
OPEN_WATER = "Open water"
STREAMS = "Streams"
PORTAGES = "Portages"
PORTAGE_PATHS = "Portage paths"
WATER_SOURCES = (SHORE, OPEN_WATER, STREAMS)
SHORE_SIMPLIFY_M = 10.0
#: Starting value until phase 2 measures the price in the browser.
OPEN_WATER_FACTOR = 1.5
PORTAGE_M = 1000.0
PATH_JOIN_M = 150.0
DAM_CUT_M = 25.0
DAM_NEAR_M = 25.0


def sources(
    surfaces: gpd.GeoDataFrame,
    *,
    metric_crs: str,
    streams: gpd.GeoDataFrame | None = None,
    dams: gpd.GeoDataFrame | None = None,
) -> list[NetworkSource]:
    """Turn water outlines and classed stream lines into paddled sources.

    Args:
        surfaces: Water polygons, already clipped to the map's box
        metric_crs: Projection in which the tolerances are metres
        streams: Stream lines carrying ``storleksklass``, or None
        dams: Dam points and lock gates, or None where streams are absent

    Returns:
        Shore and open-water sources, and directed streams when supplied
    """
    if surfaces.crs is None:
        raise ValueError("water surfaces need a coordinate reference system")
    source_crs = surfaces.crs
    started = time.perf_counter()
    shore: list[LineString] = []
    chords: list[LineString] = []
    metric = surfaces.to_crs(metric_crs).geometry.simplify(SHORE_SIMPLIFY_M)
    for surface in shapely.get_parts(metric.to_numpy()):
        if not isinstance(surface, Polygon) or surface.is_empty:
            continue
        rings = [surface.exterior, *surface.interiors]
        shore.extend(LineString(ring.coords) for ring in rings)
        ring_edges = {
            tuple(sorted((one[:2], other[:2]))) for ring in rings for one, other in zip(list(ring.coords)[:-1], list(ring.coords)[1:], strict=True)
        }
        candidates = shapely.get_parts(shapely.delaunay_triangles(surface, only_edges=True))
        shapely.prepare(surface)
        for line in candidates[shapely.covers(surface, candidates)]:
            if tuple(sorted(line.coords)) not in ring_edges:
                chords.append(line)
    result = [
        NetworkSource(SHORE, gpd.GeoDataFrame(geometry=shore, crs=metric_crs).to_crs(source_crs), kind=PADDLE, keep_whole=True),
        NetworkSource(
            OPEN_WATER,
            gpd.GeoDataFrame(geometry=chords, crs=metric_crs).to_crs(source_crs),
            kind=PADDLE,
            cost_factor=OPEN_WATER_FACTOR,
            keep_whole=True,
        ),
    ]
    print(
        f"  Water outlines and triangulation: {time.perf_counter() - started:.3f} s; "
        f"{len(chords):,} open-water chords, {sum(line.length for line in chords) / 1000:.3f} km"
    )
    if streams is not None:
        if dams is None:
            raise ValueError("stream lines need the dam and lock-gate layer")
        cut = cut_streams(streams, dams, metric_crs=metric_crs)
        result.append(NetworkSource(STREAMS, cut.to_crs(source_crs), kind=PADDLE, directed=True, keep_whole=True))
    return result


def cut_streams(streams: gpd.GeoDataFrame, dams: gpd.GeoDataFrame, *, metric_crs: str) -> gpd.GeoDataFrame:
    """Cut class-2 streams around dams, retaining their digitised direction.

    Args:
        streams: Lines with Topografi 50's text ``storleksklass`` column
        dams: Dam and lock-gate points
        metric_crs: Projection in which the cuts are metres

    Returns:
        Stream pieces outside the merged dam intervals, in the metric CRS
    """
    lines = working_lines(streams[streams["storleksklass"].astype(str) == "2"], None, metric_crs)
    points = dams.to_crs(metric_crs).geometry.to_numpy()
    tree = shapely.STRtree(points)
    kept: list[LineString] = []
    for line in lines_of(lines.geometry):
        intervals = sorted(
            (max(0.0, line.project(points[i]) - DAM_CUT_M), min(line.length, line.project(points[i]) + DAM_CUT_M))
            for i in tree.query(line, predicate="dwithin", distance=DAM_NEAR_M)
        )
        previous = 0.0
        for start, end in intervals:
            if start > previous:
                piece = substring(line, previous, start)
                assert isinstance(piece, LineString)
                kept.append(piece)
            previous = max(previous, end)
        if previous < line.length:
            piece = substring(line, previous, line.length)
            assert isinstance(piece, LineString)
            kept.append(piece)
    return gpd.GeoDataFrame(geometry=kept, crs=metric_crs)


def _components(count: int, pairs: np.ndarray) -> np.ndarray:
    """Label the connected sets without an unbounded walk through parents."""
    parent = list(range(count))

    def root(item: int) -> int:
        for _ in range(count):
            if parent[item] == item:
                return item
            parent[item] = parent[parent[item]]
            item = parent[item]
        raise RuntimeError("a water component's parent chain contains a cycle")

    for one, other in pairs.T:
        left, right = root(int(one)), root(int(other))
        parent[max(left, right)] = min(left, right)
    return np.unique([root(i) for i in range(count)], return_inverse=True)[1]


def portages(water_sources: list[NetworkSource], walking: Network, *, distance_m: float = PORTAGE_M) -> list[NetworkSource]:
    """Join nearby connected water pieces and tie the feet to walking nodes.

    Args:
        water_sources: Paddled lines after dam cuts
        walking: The noded walking network, in a metric CRS
        distance_m: Largest inferred carry between connected water pieces

    Returns:
        Inferred chords and their walking-network ties, both kind BRIDGE
    """
    if walking.edges.crs is None or not walking.edges.crs.is_projected:
        raise ValueError("portages need a projected walking network")
    metric_crs = walking.edges.crs
    arrays = [source.gdf.to_crs(metric_crs).geometry.to_numpy() for source in water_sources]
    lines = np.concatenate(arrays) if arrays else np.empty(0, dtype=object)
    chords: list[LineString] = []
    ties: dict[bytes, LineString] = {}
    if len(lines):
        # These are the connected pieces before portages: adding a carry must
        # not erase another pair that the reader may prefer to carry between.
        pairs = shapely.STRtree(lines).query(lines, predicate="intersects")
        labels = _components(len(lines), pairs)
        count = int(labels.max()) + 1
        groups = [shapely.union_all(lines[labels == i]) for i in range(count)]
        left, right = shapely.STRtree(groups).query(groups, predicate="dwithin", distance=distance_m)
        paths = walking.edges[walking.edges["kind"].isin((PATH, BRIDGE))]
        ids = np.unique(paths[["from_node", "to_node"]].to_numpy(dtype=int))
        nodes = walking.nodes.geometry.to_numpy()[ids]
        node_tree = shapely.STRtree(nodes)
        for one, other in zip(left, right, strict=True):
            if one >= other:
                continue
            chord = shapely.shortest_line(groups[one], groups[other])
            if chord.length == 0:
                continue
            chords.append(chord)
            for foot in (Point(chord.coords[0]), Point(chord.coords[-1])):
                nearest = node_tree.query_nearest(foot, max_distance=PATH_JOIN_M, all_matches=False)
                if len(nearest):
                    tie = LineString([foot, nodes[int(nearest[0])]])
                    if tie.length > 0:
                        ties[shapely.normalize(tie).wkb] = tie
        print(
            f"  {count:,} connected water pieces; {len(chords):,} portage chords, "
            f"{sum(line.length for line in chords) / 1000:.3f} km; {len(ties):,} walking ties"
        )
    return [
        NetworkSource(
            name, gpd.GeoDataFrame(geometry=geometries, crs=walking.edges.crs), kind=BRIDGE, cost_factor=DEFAULT_BRIDGE_COST_FACTOR, keep_whole=True
        )
        for name, geometries in ((PORTAGES, chords), (PORTAGE_PATHS, list(ties.values())))
    ]


def build(
    sources: list[NetworkSource],
    masks: graphs.Masks,
    clip: gpd.GeoDataFrame,
    params: graphs.Params,
    rules: graphs.Rules,
    *,
    protected: gpd.GeoDataFrame,
    measure: Callable[[Network], Network],
) -> tuple[Network, pd.DataFrame]:
    """Build the combined network without writing into the shared input cache.

    Args:
        sources: Walking and paddled sources; receives the inferred portages
        masks: The walking records used to describe ground
        clip: Map extent
        params: Graph construction parameters
        rules: Country's projection and coverage rules
        protected: Protected areas
        measure: Country's height reader

    Returns:
        Measured combined network and per-source chain counts
    """

    def node(items: list[NetworkSource]) -> Network:
        return build_network(
            items,
            clip,
            metric_crs=rules.metric_crs,
            stroke_angle_deg=params.stroke_deg,
            probe_m=params.probe_m,
            bridge_m=params.bridge_m,
            ferry_cost_m=params.ferry_cost_km * 1000,
        )

    walking_sources = [source for source in sources if source.kind != PADDLE and source.name not in (PORTAGES, PORTAGE_PATHS)]
    started = time.perf_counter()
    walking = node(walking_sources)
    print(f"  Walking graph build before water: {time.perf_counter() - started:.3f} s; {len(walking.edges):,} edges")
    started = time.perf_counter()
    added = portages([source for source in sources if source.kind == PADDLE], walking)
    sources[:] = [source for source in sources if source.name not in (PORTAGES, PORTAGE_PATHS)] + added
    network = node(sources)
    print(f"  Combined graph build with portages: {time.perf_counter() - started:.3f} s; {len(network.edges):,} edges")
    report(network)
    network = replace(network, edges=graphs.derive(network.edges, masks, protected, rules))
    covered = chain_coverage(network.chains, network.edges)
    network = replace(network, chains=network.chains.assign(**{column: covered[column] for column in CHAIN_COVERAGE_COLUMNS}))
    network = measure(network)
    # Walking sources retain the existing report's comparisons. The generated
    # water geometry already defines its units; a stroke comparison adds no evidence.
    counts = graphs.chain_report(walking_sources, clip, params, rules)
    rows: list[dict[str, Any]] = []
    for source in sources:
        if source.name in {item.name for item in walking_sources}:
            continue
        chains = network.chains[network.chains["source"] == source.name]
        rows.append(
            {
                "source": source.name,
                "features": len(source.gdf),
                "at every junction": len(chains),
                "angle only": len(chains),
                "with identity": len(chains),
                "whole": source.keep_whole,
                "km": chains["length_m"].sum() / 1000,
                "mean chain m": chains["length_m"].mean() if len(chains) else 0.0,
            }
        )
    return network, pd.concat([counts, pd.DataFrame(rows)], ignore_index=True)


def report(network: Network) -> None:
    """Print water edge counts and metres separately from the walking sources.

    Args:
        network: The combined graph
    """
    print("\nWater in the routing graph:")
    for name in (*WATER_SOURCES, PORTAGES, PORTAGE_PATHS):
        edges = network.edges[network.edges["source"] == name]
        print(f"  {name}: {len(edges):,} edges, {edges['length_m'].sum() / 1000:.3f} km")
