"""The routing graph: every source noded against every other.

Two units live here and confusing them wrecks both. A **chain** is what a reader
selects, and it is built within one source. An **edge** is a piece of the merged
network, cut at every crossing between every source, and it is what a route is
found over. There are an order of magnitude more edges than chains, and the link
between them is that every edge names the chain it lies on.

The union is plain: no source is cut away where a better one exists. That was
measured and it is wrong for connectivity — the redundancy is what carries the
network across the gaps in any one dataset. Priority lives in the edge cost
instead, where it decides which of two parallel lines a route follows without
ever removing one.
"""

from dataclasses import dataclass
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString, Point

from trails.routing.chains import DEFAULT_PROBE_M, DEFAULT_STROKE_ANGLE_DEG, ChainRule, chains_of
from trails.routing.noding import (
    DEFAULT_METRIC_CRS,
    NODE_TOLERANCE_M,
    ClipGeometry,
    carry_positions,
    cut_line,
    cut_positions,
    intersection_points,
    lines_of,
)
from trails.routing.sources import BRIDGE, FERRY, NetworkSource
from trails.routing.topology import UnionFind, cluster_points, dense_ids

#: Loose ends closer than this to another node are joined. Sources disagree
#: about where a path stops by a few metres, and every such disagreement is a
#: break in the network that no route can cross.
DEFAULT_BRIDGE_M = 25.0

#: What a ferry crossing costs, as the equivalent in metres walked. A crossing
#: is the same decision whether it is 2 km or 20, so its cost is not its length:
#: this is high enough that no route takes a boat to save two hundred metres,
#: low enough that it takes one where it genuinely shortens the journey.
DEFAULT_FERRY_COST_M = 5000.0

#: Cost factor on an inferred connector. No source drew it, so a route should
#: not seek it out.
DEFAULT_BRIDGE_COST_FACTOR = 1.3

#: An edge shorter than this that begins and ends at the same node carries no
#: connectivity and no direction. It is an artefact of two cuts landing together.
MIN_EDGE_M = 0.5

#: Columns of the edge frame.
EDGE_COLUMNS = ("from_node", "to_node", "cost", "source", "kind", "chain_id", "length_m")


@dataclass(frozen=True)
class Network:
    """A routable network and the chains it was built from.

    Attributes:
        chains: What a reader selects: linear, built within one source, carrying
            that source's attributes. Described by
            :data:`trails.routing.chains.CHAIN_COLUMNS`.
        edges: What a route runs over: :data:`EDGE_COLUMNS`, a geometry and the
            component it belongs to. ``chain_id`` names the chain it lies on,
            and is None only for an inferred connector.
        nodes: Where edges meet, with their degree and component.

    All three are in the working CRS the network was built in, which is metric.
    """

    chains: gpd.GeoDataFrame
    edges: gpd.GeoDataFrame
    nodes: gpd.GeoDataFrame


def build_network(
    sources: list[NetworkSource],
    clip: ClipGeometry | None = None,
    *,
    rule: ChainRule = ChainRule.STROKE,
    metric_crs: str = DEFAULT_METRIC_CRS,
    stroke_angle_deg: float = DEFAULT_STROKE_ANGLE_DEG,
    probe_m: float = DEFAULT_PROBE_M,
    bridge_m: float = DEFAULT_BRIDGE_M,
    ferry_cost_m: float = DEFAULT_FERRY_COST_M,
    bridge_cost_factor: float = DEFAULT_BRIDGE_COST_FACTOR,
    tolerance_m: float = NODE_TOLERANCE_M,
) -> Network:
    """Build chains per source and a routing graph over all of them.

    Args:
        sources: Datasets to include, all in one CRS
        clip: Extent to cut them to
        rule: How each source's pieces are joined into chains
        metric_crs: Working CRS, which every result comes back in
        stroke_angle_deg: Largest deflection accepted as a continuation
        probe_m: How far either side of a junction a direction is read
        bridge_m: How far a loose end may reach for another node
        ferry_cost_m: Cost of a whole ferry crossing, in metres walked
        bridge_cost_factor: Cost factor on an inferred connector
        tolerance_m: Distance below which two coordinates are the same point

    Returns:
        The network, in ``metric_crs``

    Raises:
        ValueError: If no source was given, or two sources share a name
    """
    if not sources:
        raise ValueError("a network needs at least one source")
    names = [source.name for source in sources]
    if len(set(names)) != len(names):
        raise ValueError(f"source names must be unique, got {names}")

    built = [
        chains_of(
            source,
            clip,
            rule=rule,
            stroke_angle_deg=stroke_angle_deg,
            probe_m=probe_m,
            metric_crs=metric_crs,
            tolerance_m=tolerance_m,
        )
        for source in sources
    ]
    chains = gpd.GeoDataFrame(pd.concat(built, ignore_index=True), geometry="geometry", crs=metric_crs)

    edges, nodes, stopped = _split_into_edges(chains, {source.name: source for source in sources}, ferry_cost_m, tolerance_m)
    edges, nodes = _with_bridges(edges, nodes, stopped, bridge_m, bridge_cost_factor, tolerance_m)

    edges["component"] = label_components(edges)
    nodes = _describe_nodes(nodes, edges)
    return Network(chains=chains, edges=edges, nodes=nodes)


def _noding_geometry(chains: gpd.GeoDataFrame, sources: dict[str, NetworkSource]) -> tuple[gpd.GeoSeries, np.ndarray]:
    """Return the geometry each chain is noded by.

    A track recorded at raw GPS density weaves across every line it runs along,
    and each weave is another crossing: noding it as recorded triples the graph.
    Simplifying what goes into the noding costs nothing, because the edge keeps
    the chain's own geometry either way.

    Args:
        chains: All chains
        sources: The datasets they came from, by name

    Returns:
        One geometry per chain, in chain order, and a mask saying which of them
        are a simplified copy rather than the chain itself
    """
    tolerances = chains["source"].map({name: source.node_simplify_m for name, source in sources.items()}).to_numpy(dtype=float)
    simplified = tolerances > 0
    if not simplified.any():
        return chains.geometry, simplified

    noding = chains.geometry.copy()
    for tolerance in sorted(set(tolerances[simplified])):
        rows = tolerances == tolerance
        noding.loc[rows] = chains.geometry.loc[rows].simplify(tolerance)
    return noding, simplified


def _split_into_edges(
    chains: gpd.GeoDataFrame,
    sources: dict[str, NetworkSource],
    ferry_cost_m: float,
    tolerance_m: float,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, np.ndarray]:
    """Cut every chain where any chain meets it, and number the cuts.

    Args:
        chains: All chains, from every source
        sources: The datasets they came from, by name
        ferry_cost_m: Cost of a whole ferry crossing, in metres walked
        tolerance_m: Distance below which two coordinates are the same point

    Returns:
        The edges, the nodes their ends fall on, and which of those nodes every
        chain reaching them stops at
    """
    noding, simplified = _noding_geometry(chains, sources)
    meetings = intersection_points(noding)

    rows: list[dict[str, object]] = []
    geometries: list[LineString] = []
    full_lines = lines_of(chains.geometry)
    chain_ids = chains["chain_id"].to_numpy()
    chain_sources = chains["source"].to_numpy()
    chain_lengths = chains["length_m"].to_numpy(dtype=float)

    # Two coordinates per edge end. The first says which node the end belongs to
    # and the second says where that end actually is: for a chain noded by a
    # simplified copy of itself the two differ, because the copy wanders a few
    # metres either side of the line the source drew.
    meets: list[tuple[float, float]] = []
    lands: list[tuple[float, float]] = []
    #: Whether the end is where its chain stops, rather than a cut along it.
    stops: list[bool] = []
    #: Whether the end lies exactly where its node was found.
    exact: list[bool] = []

    for position, node_line in enumerate(lines_of(noding)):
        full = full_lines[position]
        positions = cut_positions(node_line, meetings[position], tolerance_m)
        cuts = [node_line.interpolate(distance) for distance in positions]
        along = carry_positions(full, node_line, positions) if simplified[position] else positions

        source = sources[str(chain_sources[position])]
        pieces = cut_line(full, along)
        for index, (piece, start_cut, end_cut) in enumerate(zip(pieces, cuts[:-1], cuts[1:], strict=True)):
            if piece is None:
                continue
            meets.extend(((start_cut.x, start_cut.y), (end_cut.x, end_cut.y)))
            lands.extend(((piece.coords[0][0], piece.coords[0][1]), (piece.coords[-1][0], piece.coords[-1][1])))
            stops.extend((index == 0, index == len(pieces) - 1))
            exact.extend((not simplified[position], not simplified[position]))
            geometries.append(piece)
            rows.append(
                {
                    "from_node": -1,
                    "to_node": -1,
                    "cost": _cost(piece.length, chain_lengths[position], source, ferry_cost_m),
                    "source": source.name,
                    "kind": source.kind,
                    "chain_id": chain_ids[position],
                    "length_m": piece.length,
                }
            )

    if not rows:
        empty = gpd.GeoDataFrame(columns=list(EDGE_COLUMNS), geometry=[], crs=chains.crs)
        return empty, gpd.GeoDataFrame(geometry=[], crs=chains.crs), np.empty(0, dtype=bool)

    labels = cluster_points(np.asarray(meets, dtype=float), tolerance_m)
    lengths = np.array([float(row["length_m"]) for row in rows])  # type: ignore[arg-type]
    # An edge that begins and ends at one node carries no connectivity unless it
    # is a real loop; a short one is an artefact of two cuts landing together.
    kept = (lengths > 0) & ~((labels[0::2] == labels[1::2]) & (lengths < MIN_EDGE_M))

    surviving = np.repeat(kept, 2)
    identifiers = dense_ids(labels[surviving])
    edges = gpd.GeoDataFrame(
        [row for row, keep in zip(rows, kept, strict=True) if keep],
        columns=list(EDGE_COLUMNS),
        geometry=[geometry for geometry, keep in zip(geometries, kept, strict=True) if keep],
        crs=chains.crs,
    )
    edges["from_node"] = identifiers[0::2]
    edges["to_node"] = identifiers[1::2]

    nodes = _place_nodes(identifiers, np.asarray(lands, dtype=float)[surviving], np.asarray(exact)[surviving], chains.crs)
    stopped = np.ones(len(nodes), dtype=bool)
    np.logical_and.at(stopped, identifiers, np.asarray(stops)[surviving])
    return edges, nodes, stopped


def _place_nodes(identifiers: np.ndarray, lands: np.ndarray, exact: np.ndarray, crs: Any) -> gpd.GeoDataFrame:
    """Put every node where one of its edges actually begins.

    A node's *identity* comes from the geometry the chains were noded by, so
    that two chains cut at one crossing meet at one node even where their own
    lines run a few metres either side of it. Its *position* must not: a node
    sitting where no edge does would send anything that snaps to it off the
    network. So it takes the end of one of its own edges, preferring one whose
    chain was noded as the source drew it — for the common case of a recorded
    track crossing a surveyed path, that puts the node exactly on the path.

    Args:
        identifiers: Node each edge end belongs to
        lands: Where each edge end actually is
        exact: Whether the end lies exactly where its node was found
        crs: CRS of the result

    Returns:
        One row per node, in node order
    """
    order = np.lexsort((np.arange(len(identifiers)), ~exact, identifiers))
    _, first = np.unique(identifiers[order], return_index=True)
    chosen = lands[order[first]]
    return gpd.GeoDataFrame(geometry=shapely.points(chosen[:, 0], chosen[:, 1]), crs=crs)


def _cost(length_m: float, chain_length_m: float, source: NetworkSource, ferry_cost_m: float) -> float:
    """Cost of traversing one edge.

    Args:
        length_m: The edge's length
        chain_length_m: Length of the chain it lies on
        source: Dataset it came from
        ferry_cost_m: Cost of a whole crossing, in metres walked

    Returns:
        Cost in the same unit as a walked metre
    """
    if source.kind == FERRY:
        # Flat per crossing, and a crossing is the chain. Splitting it in
        # proportion keeps the total flat however many pieces it was cut into.
        return ferry_cost_m * (length_m / chain_length_m if chain_length_m > 0 else 1.0)
    return length_m * source.cost_factor


def _nearest_edges(edges: gpd.GeoDataFrame, nodes: gpd.GeoDataFrame, loose: np.ndarray, bridge_m: float) -> dict[int, int]:
    """Find the edge each loose end could reach, if any.

    Args:
        edges: The edges so far
        nodes: Their nodes
        loose: Node ids with only one edge on them
        bridge_m: How far a loose end may reach

    Returns:
        Nearest edge per loose end, by position in ``edges``, leaving out the
        ends that can reach nothing but what they are already on
    """
    incident: dict[int, set[int]] = {int(node): set() for node in loose.tolist()}
    for position, (one, other) in enumerate(zip(edges["from_node"], edges["to_node"], strict=True)):
        for node in (int(one), int(other)):
            if node in incident:
                incident[node].add(position)

    points = nodes.geometry.to_numpy()
    geometries = edges.geometry.to_numpy()
    found = shapely.STRtree(geometries).query(points[loose], predicate="dwithin", distance=bridge_m)

    nearest: dict[int, tuple[float, int]] = {}
    for offset, position in zip(found[0], found[1], strict=True):
        node, edge = int(loose[offset]), int(position)
        if edge in incident[node]:
            continue
        candidate = (float(shapely.distance(points[node], geometries[edge])), edge)
        if candidate < nearest.get(node, (float("inf"), 0)):
            nearest[node] = candidate
    return {node: edge for node, (_, edge) in nearest.items()}


def _with_bridges(
    edges: gpd.GeoDataFrame,
    nodes: gpd.GeoDataFrame,
    stopped: np.ndarray,
    bridge_m: float,
    cost_factor: float,
    tolerance_m: float,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Join every loose end to whatever lies close beside it.

    Sources disagree about where a way stops by a few metres, and each
    disagreement is a break no route can cross. A dangling end rarely stops at
    another line's *node*, though — it stops beside its middle. So the target is
    the nearest point on the nearest edge, and the edge is split there.

    A loose end is not the same as a node with one edge on it. Where two sources
    both draw the same dead end, their chains stop at the same point and the
    node has two edges — and counting edges would pass it over, although nothing
    continues through it. So the test is that every chain reaching the node stops
    there.

    Args:
        edges: The edges so far
        nodes: Their nodes
        stopped: Whether every chain reaching a node stops at it
        bridge_m: How far a loose end may reach
        cost_factor: Cost factor on the connectors added
        tolerance_m: Distance below which two positions are the same point

    Returns:
        The edges with the connectors added and the split edges replaced, and
        the nodes with the split positions added
    """
    if edges.empty or bridge_m <= 0:
        return edges, nodes

    loose = np.flatnonzero(stopped)
    if not len(loose):
        return edges, nodes

    nearest = _nearest_edges(edges, nodes, loose, bridge_m)
    if not nearest:
        return edges, nodes

    points = nodes.geometry.to_numpy()
    geometries = edges.geometry.to_numpy()

    # Where a loose end reaches an edge's middle rather than one of its ends,
    # that edge gains a node. Collect the positions first: two ends can arrive
    # at one edge, and it is cut once for both.
    cuts: dict[int, list[float]] = {}
    reached: dict[int, tuple[int, float]] = {}
    for node, edge in sorted(nearest.items()):
        along = float(geometries[edge].project(points[node]))
        reached[node] = (edge, along)
        if tolerance_m < along < geometries[edge].length - tolerance_m:
            cuts.setdefault(edge, []).append(along)

    boundaries, replacements, added = _split_edges(edges, cuts, len(nodes), tolerance_m)
    connectors = _connectors(edges, points, reached, boundaries, cost_factor, tolerance_m)

    kept = edges.drop(index=list(cuts))
    parts = [frame for frame in (kept, replacements, connectors) if not frame.empty]
    bridged = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry", crs=edges.crs)
    grown = gpd.GeoDataFrame(pd.concat([nodes, gpd.GeoDataFrame(geometry=added, crs=nodes.crs)], ignore_index=True), crs=nodes.crs)
    return bridged, grown


def _split_edges(
    edges: gpd.GeoDataFrame,
    cuts: dict[int, list[float]],
    next_node: int,
    tolerance_m: float,
) -> tuple[dict[int, tuple[list[float], list[int]]], gpd.GeoDataFrame, list[Point]]:
    """Cut the edges a loose end reached into, and number the new nodes.

    Args:
        edges: The edges so far
        cuts: Positions along each edge, by position in ``edges``
        next_node: First unused node id
        tolerance_m: Distance below which two positions are the same point

    Returns:
        The cut positions and their node ids per edge, the pieces replacing the
        edges that were cut, and the points the new nodes sit at
    """
    boundaries: dict[int, tuple[list[float], list[int]]] = {}
    rows: list[dict[str, object]] = []
    geometries: list[LineString] = []
    added: list[Point] = []

    lines = lines_of(edges.geometry)
    for edge in sorted(cuts):
        line = lines[edge]
        row = edges.iloc[edge]

        positions: list[float] = []
        for value in sorted(cuts[edge]):
            if not positions or value - positions[-1] > tolerance_m:
                positions.append(value)
        identifiers = list(range(next_node, next_node + len(positions)))
        next_node += len(positions)
        added.extend(line.interpolate(value) for value in positions)
        boundaries[edge] = (positions, identifiers)

        ends = [int(row.from_node), *identifiers, int(row.to_node)]
        for piece, one, other in zip(cut_line(line, [0.0, *positions, line.length]), ends[:-1], ends[1:], strict=True):
            if piece is None:
                continue
            geometries.append(piece)
            rows.append(
                {
                    "from_node": one,
                    "to_node": other,
                    "cost": row.cost * piece.length / line.length,
                    "source": row.source,
                    "kind": row.kind,
                    "chain_id": row.chain_id,
                    "length_m": piece.length,
                }
            )

    return boundaries, gpd.GeoDataFrame(rows, columns=list(EDGE_COLUMNS), geometry=geometries, crs=edges.crs), added


def _connectors(
    edges: gpd.GeoDataFrame,
    points: np.ndarray,
    reached: dict[int, tuple[int, float]],
    boundaries: dict[int, tuple[list[float], list[int]]],
    cost_factor: float,
    tolerance_m: float,
) -> gpd.GeoDataFrame:
    """Build the short edges joining each loose end to what it reached.

    Args:
        edges: The edges so far
        points: Node positions, by node id
        reached: Edge and position along it each loose end reached
        boundaries: Cut positions and their node ids per edge
        cost_factor: Cost factor on the connectors
        tolerance_m: Distance below which two positions are the same point

    Returns:
        The connectors, as edges belonging to no chain
    """
    rows: list[dict[str, object]] = []
    geometries: list[LineString] = []
    joined: set[tuple[int, int]] = set()

    lines = lines_of(edges.geometry)
    for node, (edge, along) in sorted(reached.items()):
        line = lines[edge]
        if along <= tolerance_m:
            target, landing = int(edges["from_node"].iloc[edge]), Point(line.coords[0])
        elif along >= line.length - tolerance_m:
            target, landing = int(edges["to_node"].iloc[edge]), Point(line.coords[-1])
        else:
            positions, identifiers = boundaries[edge]
            index = min(range(len(positions)), key=lambda position: abs(positions[position] - along))
            target, landing = identifiers[index], line.interpolate(positions[index])

        # Two loose ends beside each other each go looking and each find the
        # other. One connector between them is enough.
        pair = (min(node, target), max(node, target))
        if target == node or pair in joined:
            continue
        joined.add(pair)
        connector = LineString([points[node], landing])
        if connector.length <= 0:
            continue
        geometries.append(connector)
        rows.append(
            {
                "from_node": node,
                "to_node": target,
                "cost": connector.length * cost_factor,
                "source": BRIDGE,
                "kind": BRIDGE,
                "chain_id": None,
                "length_m": connector.length,
            }
        )

    return gpd.GeoDataFrame(rows, columns=list(EDGE_COLUMNS), geometry=geometries, crs=edges.crs)


def label_components(edges: gpd.GeoDataFrame, *, length_column: str = "length_m") -> pd.Series:
    """Number the connected components of a set of edges, longest first.

    Call it on a subset to ask what the network looks like without it — with the
    ferry crossings dropped, eleven of the seventeen quays here fall off the map
    entirely.

    Args:
        edges: Edges carrying ``from_node``, ``to_node`` and a length
        length_column: Column the components are ranked by

    Returns:
        Component id per edge, aligned to the input index, 0 being the longest
    """
    if edges.empty:
        return pd.Series(dtype="int64", index=edges.index)

    from_node = edges["from_node"].to_numpy()
    to_node = edges["to_node"].to_numpy()
    groups = UnionFind(int(max(from_node.max(), to_node.max())) + 1)
    for one, other in zip(from_node, to_node, strict=True):
        groups.union(int(one), int(other))

    roots = pd.Series([groups.find(int(node)) for node in from_node], index=edges.index)
    ranked = edges.groupby(roots)[length_column].sum().sort_values(ascending=False, kind="stable")
    return roots.map({root: rank for rank, root in enumerate(ranked.index)}).astype("int64")


def _describe_nodes(nodes: gpd.GeoDataFrame, edges: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Give every node its degree and its component.

    Args:
        nodes: The nodes, indexed by node id
        edges: The edges, already carrying a component

    Returns:
        Copy of the nodes with ``degree`` and ``component``
    """
    described = nodes.copy()
    if edges.empty:
        described["degree"] = 0
        described["component"] = -1
        return described

    ends = pd.concat([edges["from_node"], edges["to_node"]])
    described["degree"] = ends.value_counts().reindex(described.index).fillna(0).astype("int64")
    component = pd.concat([edges["component"], edges["component"]])
    described["component"] = component.groupby(ends.to_numpy()).first().reindex(described.index).fillna(-1).astype("int64")
    return described
