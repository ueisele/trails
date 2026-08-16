"""Which of a chain's edges comes first, and which way round each of them runs.

A chain is linear, so its edges form a path — but **nothing in the edge frame
says so, and its own order is not that path**. Measured over this park: 2,221 of
11,290 chains have edges that do not join up in frame order, taking each edge's
last coordinate against the next one's first, and the worst of those steps is
20.2 km. Most of that is the bridging pass, which drops every edge it splits and
appends the pieces at the end of the frame, so a chain that was contiguous
acquires a hole and a tail. Sorting by ``from_node`` does not repair it either;
there is nothing in the node ids that says which way along the chain an edge
sits.

So the order is not something a consumer may assume, nor something it can
recover from the columns. It has to be **reconstructed** — by walking the edges
from one end of the chain to the other, which is what :func:`chain_order` does —
and then carried on the edge, for any consumer that has the edges but not the
chain to project them onto. A browser is exactly that consumer.

:mod:`trails.routing.elevation` has walked this path since phase 2, to lay a
chain's height series out of its edges'; the walk lives here now so that the two
cannot drift apart. A profile composed in one order and a route composed in
another would still look like a profile and like a route.

**Two things beyond the order itself**, both of which a consumer laying series
or geometry end to end needs and neither of which the sequence alone gives:

- **Which way round the edge runs.** An edge is cut out of its chain in the
  chain's own direction, but the walk can arrive at it from either end, and the
  chain's own direction is what the ascent figures were read along. 9 edges here
  run against their chain.
- **Where a stretch begins that does not join what came before.** 90 chains here
  reach a node twice — 41 rings and 49 that touch themselves somewhere — which
  leaves the walk a choice at that node; what it cannot reach in one pass starts
  again, and the two stretches must not be laid end to end as though they
  joined. A climb counted across a step nothing was measured along is invented.
  **No chain in this park actually needs it**: measured, all 11,290 come back as
  a single run, so the mark is set only at a chain's own beginning. The flag is
  carried and tested against fixtures rather than against the map, and anyone
  checking it here will find it never fires.
"""

from collections import defaultdict
from collections.abc import Sequence

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry.base import BaseGeometry

#: What :func:`chain_order` says about each edge. ``chain_seq`` counts from 0
#: along the chain and is -1 for an edge that lies on none; ``flipped`` says the
#: edge's own geometry and series run against the chain; ``run_start`` marks an
#: edge whose beginning does not join the edge before it.
CHAIN_ORDER_COLUMNS = ("chain_seq", "flipped", "run_start")


def chain_order(chains: gpd.GeoDataFrame, edges: gpd.GeoDataFrame) -> pd.DataFrame:
    """Put every chain's edges back into the order they lie in.

    Args:
        chains: The chains, carrying ``chain_id`` and their geometry
        edges: The edges, carrying ``chain_id``, ``from_node`` and ``to_node``

    Returns:
        :data:`CHAIN_ORDER_COLUMNS` per edge, aligned to ``edges``. An inferred
        connector lies on no chain and comes back at -1: nobody drew it, so
        there is no chain for it to have a position within.
    """
    lying_on: dict[object, list[int]] = defaultdict(list)
    for position, chain_id in enumerate(edges["chain_id"].tolist()):
        if chain_id is not None and not pd.isna(chain_id):
            lying_on[chain_id].append(position)

    pairs = list(zip(edges["from_node"].to_numpy(dtype=np.int64).tolist(), edges["to_node"].to_numpy(dtype=np.int64).tolist(), strict=True))
    geometries = edges.geometry.to_numpy()

    sequence = np.full(len(edges), -1, dtype=np.int64)
    flipped = np.zeros(len(edges), dtype=bool)
    run_start = np.zeros(len(edges), dtype=bool)

    for chain_id, geometry in zip(chains["chain_id"].tolist(), chains.geometry.tolist(), strict=True):
        position = 0
        for run in lay_out(lying_on.get(chain_id, []), pairs):
            # A run walked against the chain is turned round whole rather than
            # left as it is: the chain's direction is the one its ascent and
            # descent were read along, and a consumer laying the edges out has
            # no way to discover it for itself.
            backwards = runs_backwards(run, geometries, geometry)
            ordered = run[::-1] if backwards else run
            for index, (edge, reversed_) in enumerate(ordered):
                sequence[edge] = position
                flipped[edge] = reversed_ != backwards
                run_start[edge] = index == 0
                position += 1

    return pd.DataFrame({"chain_seq": sequence, "flipped": flipped, "run_start": run_start}, index=edges.index)


def lay_out(members: Sequence[int], pairs: Sequence[tuple[int, int]]) -> list[list[tuple[int, bool]]]:
    """Walk a chain's edges from one end to the other.

    One run, every time, in this park: 11,200 of its 11,290 chains walk straight
    through, 41 close on themselves and 49 touch themselves somewhere, and the
    walk gets through all of them in a single pass. Where it cannot — a node it
    arrives at with nothing left to leave by, while edges remain elsewhere — the
    rest is started again as a separate run rather than joined to what came
    before. That case does not arise here; it is written for because a run laid
    end to end across a gap is a plausible profile of a route nobody can walk.

    Args:
        members: Positions of the edges lying on this chain
        pairs: ``(from_node, to_node)`` per edge

    Returns:
        ``(position, reversed)`` in walking order, one list per run
    """
    incident: dict[int, list[tuple[int, bool]]] = defaultdict(list)
    for position in members:
        from_node, to_node = pairs[position]
        incident[from_node].append((position, False))
        incident[to_node].append((position, True))

    remaining = set(members)
    # An end of the chain first, so an open chain comes out as one run walked
    # from its beginning rather than from somewhere in its middle.
    ends = [node for node, arms in incident.items() if len(arms) == 1]
    runs: list[list[tuple[int, bool]]] = []
    for node in [*ends, *(pairs[position][0] for position in members)]:
        if not remaining:
            break
        run = walk(node, incident, remaining, pairs)
        if run:
            runs.append(run)
    return runs


def walk(node: int, incident: dict[int, list[tuple[int, bool]]], remaining: set[int], pairs: Sequence[tuple[int, int]]) -> list[tuple[int, bool]]:
    """Follow one run of edges from a node as far as it goes.

    Args:
        node: Where to start
        incident: Edges meeting at each node, and which way they leave it
        remaining: Edges not yet walked, emptied as they are
        pairs: ``(from_node, to_node)`` per edge

    Returns:
        ``(position, reversed)`` in walking order
    """
    run: list[tuple[int, bool]] = []
    while True:
        leaving = next(((position, reversed_) for position, reversed_ in incident[node] if position in remaining), None)
        if leaving is None:
            return run
        position, reversed_ = leaving
        remaining.discard(position)
        run.append(leaving)
        node = pairs[position][0] if reversed_ else pairs[position][1]


def runs_backwards(run: Sequence[tuple[int, bool]], geometries: np.ndarray, geometry: BaseGeometry | None) -> bool:
    """Say whether a walk went against the chain's own direction.

    Args:
        run: ``(position, reversed)`` in walking order
        geometries: Geometry per edge
        geometry: The chain, or None to keep the direction the walk took

    Returns:
        Whether the walk ended nearer the chain's start than it began
    """
    if geometry is None:
        return False
    first, first_reversed = run[0]
    last, last_reversed = run[-1]
    start = geometries[first].coords[-1 if first_reversed else 0]
    end = geometries[last].coords[0 if last_reversed else -1]
    return bool(geometry.project(shapely.Point(start)) > geometry.project(shapely.Point(end)))
