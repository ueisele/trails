"""The line an export writes: every vertex, filled to 5 m, with a height on each.

A chain's drawn copy, its routed copy and its **exported** copy are three
different things, and this module builds the third. It is not the geometry the
map draws — that one is thinned for the render budget — and it is not the bare
chain either: an exported track carries an ``<ele>`` on every point, and the
heights were sampled every 5 m along the edges rather than at the vertices, so
the two have to be laid against each other before either can be written down.

**Keep every vertex, lay in every sample, and only then space out what is still
further apart than 5 m.** Resampling the line every 5 m instead would drop the
source's own vertices and round off every corner between two samples, which is
the one thing the geometry was worth carrying at full precision for. Keeping the
vertices *alone* and interpolating the heights between them loses the other
half: the ascent read back off the written values came out 47 m under the figure
the same file states for the 42 km Rundtur, and 2,637 chains disagreed with
their own extensions.

Two things about the sampling that this has to account for and that its own name
hides. The samples are laid **per edge**, evenly between its two ends, so their
step is ``length / floor(length / 5)`` — between 5 and 10 m, not 5 — which is why
the spacing pass still has work to do after they are laid in. And an edge's first
and last sample sit *on* its end vertices, so most of what the two lists have in
common is already shared and the merge drops the copy.

Measured over this park: the 541,060 vertices the chains carry become 2,392,035
points, the median chain goes from 19 to 76 and the 42 km Rundtur from 1,330 to
16,421 — and every one of the 5,254 chains longer than 200 m reproduces its own
stored ascent exactly from the heights written beside those points.

**A browser writes the same file from the same graph**, out of the payload
:mod:`trails.visualization.encoding` puts in the page. The two agree on the walk
itself — the same edges in the order
:func:`~trails.routing.order.chain_order` reconstructed, the same 327 vertices
and 704 samples on the chain this was measured against — because both compose
from that order and both scale onto the length the chain carries.

**They do not agree to the last point, and the two reasons are worth knowing
rather than being rediscovered.** Measured on a 3.78 km Turrutebasen chain,
1,373 points here against 1,365 there:

- **Nine pairs of vertices lie closer together than the payload's own grid.**
  A coordinate travels to the page rounded to a millionth of a degree, about
  11 cm, so two vertices 2 mm apart are one vertex to it. This keeps both,
  because the export carries the resolution its source recorded.
- **One fill decision lands on a boundary.** The page measures a degree flat
  where this measures a projected metre, and after the scaling the two still
  differ by up to **1.28 m over 3.8 km** — three parts in ten thousand, not the
  parts per million a scaling argument suggests, because the scaling fixes the
  total and not the distribution. One sample gap therefore reads 9.98 m here and
  10.01 m there, and ``ceil(gap / 5)`` puts one point into it here and two there.

Neither is a fault, and neither is a licence to let the two drift: a point one
writer has that the other cannot account for by one of these two is.
"""

from collections import defaultdict
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

#: How far apart two points of an exported track may be before one is put
#: between them, in metres. The same 5 m the heights were sampled at: a gap
#: wider than that is ground the export could describe and does not.
DEFAULT_GAP_M = 5.0

#: What an exported track is written in. Every consumer of a GPX file speaks
#: longitude and latitude, so the reprojection happens here — while the heights
#: are still an array of their own — rather than afterwards on a geometry
#: carrying them. A missing height is NaN, and pyproj answers a NaN third
#: ordinate with a NaN *coordinate*: the point loses its position along with it.
EXPORT_CRS = "EPSG:4326"


def chain_tracks(
    chains: gpd.GeoDataFrame,
    edges: gpd.GeoDataFrame,
    order: pd.DataFrame,
    *,
    gap_m: float = DEFAULT_GAP_M,
    crs: Any = EXPORT_CRS,
) -> gpd.GeoSeries:
    """Build the dense, height-carrying line of every chain.

    Args:
        chains: The chains, carrying ``chain_id`` and ``length_m``, in a metric
            CRS
        edges: The graph's edges, carrying ``chain_id`` and ``elevations``, in
            the same CRS
        order: :data:`~trails.routing.order.CHAIN_ORDER_COLUMNS` per edge, from
            :func:`~trails.routing.order.chain_order`
        gap_m: How far apart two points may be before one is put between them
        crs: What to write the tracks in

    Returns:
        One line per chain, aligned to ``chains``, carrying a Z ordinate
        wherever the height model was read along it. A chain nothing was read
        along at all — every ferry crossing — comes back flat and **unfilled**:
        the fill exists to carry heights, and a point every 5 m across a fjord
        would add 29,414 of them to this park's crossings while saying nothing
        the two ends do not already say.

    Raises:
        ValueError: If the order does not describe these edges, or if the chains
            and the edges are in different CRSs
    """
    if len(order) != len(edges) or not order.index.equals(edges.index):
        raise ValueError(f"the order has to describe these {len(edges):,} edges, got {len(order):,} rows indexed differently")
    # The points are composed out of the edges and reprojected out of the
    # chains' CRS, so the two being the same is not a detail of the signature:
    # if they ever differ every exported track lands somewhere else on the
    # earth, and nothing about the file would say so.
    if chains.crs != edges.crs:
        raise ValueError(f"the chains are in {chains.crs} and their edges in {edges.crs}, and a track is composed from both")

    sequence = order["chain_seq"].to_numpy(dtype=np.int64)
    flipped = order["flipped"].to_numpy(dtype=bool)
    run_start = order["run_start"].to_numpy(dtype=bool)

    # Every edge's coordinates in one array, taken out once: asking shapely per
    # edge costs a quarter of a million calls for the same bytes.
    geometries = edges.geometry.to_numpy()
    coordinates = shapely.get_coordinates(geometries)
    bounds = np.concatenate([[0], np.cumsum(shapely.get_num_coordinates(geometries))])
    heights = list(edges["elevations"])

    lying_on: dict[object, list[int]] = defaultdict(list)
    for position, chain_id in enumerate(edges["chain_id"].tolist()):
        # An inferred connector lies on no chain, and an edge the order could
        # not place has no position along one either.
        if chain_id is not None and not pd.isna(chain_id) and sequence[position] >= 0:
            lying_on[chain_id].append(position)
    for members in lying_on.values():
        members.sort(key=lambda position: sequence[position])

    parts: list[np.ndarray] = []
    part_of: list[int] = []
    for chain, (chain_id, carried) in enumerate(zip(chains["chain_id"].tolist(), chains["length_m"].tolist(), strict=True)):
        runs = _compose(lying_on.get(chain_id, []), coordinates, bounds, heights, flipped, run_start)
        _scale(runs, float(carried))
        for run in runs:
            points = _fill(run, gap_m)
            # One point is not a line. Nothing here produces a stretch that
            # short — an edge holds at least two coordinates — but a geometry
            # built from one would raise from inside shapely, several thousand
            # chains into a build.
            if len(points) > 1:
                parts.append(points)
                part_of.append(chain)

    return _lines(parts, np.array(part_of, dtype=np.int64), len(chains), chains.crs, crs, chains.index)


def _compose(
    members: list[int],
    coordinates: np.ndarray,
    bounds: np.ndarray,
    heights: list[np.ndarray],
    flipped: np.ndarray,
    run_start: np.ndarray,
) -> list[dict[str, np.ndarray]]:
    """Lay one chain's edges end to end, geometry and heights side by side.

    The page composes a chain the same way and from the same order, so anything
    changed here has to change there: the two write the same file.

    Args:
        members: The chain's edges, in the order they lie in
        coordinates: Every edge's coordinates, concatenated
        bounds: Where each edge's coordinates begin and end within them
        heights: Height samples per edge
        flipped: Whether each edge's geometry and series run against its chain
        run_start: Whether each edge begins a stretch that does not join what
            came before

    Returns:
        One entry per stretch that joins up, holding the coordinates and their
        distance along the chain, and the samples and theirs. The two series
        describe the same ground and are **not** the same points: a vertex is
        where the surveyor turned, a sample is where the height model was asked.
    """
    runs: list[dict[str, list[np.ndarray]]] = []
    current: dict[str, list[np.ndarray]] | None = None
    reached, joined, laid_any = 0.0, False, False

    for position in members:
        # Whether anything has been laid down *anywhere* on this chain, not just
        # in the stretch being built: two stretches that both begin a run must
        # both begin one, and a flag reset per stretch would join the second and
        # third of them together.
        apart = bool(run_start[position]) and laid_any
        if current is None or apart:
            current = {"xy": [], "along": [], "distance": [], "height": []}
            runs.append(current)
            joined = False

        laid = coordinates[bounds[position] : bounds[position + 1]]
        values = heights[position]
        values = np.empty(0, dtype=float) if values is None else np.asarray(values, dtype=float)
        if flipped[position]:
            laid, values = laid[::-1], values[::-1]

        began = reached
        walked = reached + np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(laid[:, 0]), np.diff(laid[:, 1])))])
        # Where there is something to join onto, the edge's first coordinate is
        # the node the edge before it ended at and is already laid down. Where
        # there is not, it starts where it starts and adds no distance.
        from_here = 1 if current["xy"] else 0
        current["xy"].append(laid[from_here:])
        current["along"].append(walked[from_here:])
        reached, laid_any = float(walked[-1]), True

        # The samples are spread evenly between the edge's two ends rather than
        # laid from one of them, so this is where the sth of them lies rather
        # than s * 5. The first is dropped wherever the edge before it already
        # sampled the node the two share.
        first = 1 if joined else 0
        if len(values) > first:
            steps = np.arange(first, len(values), dtype=float)
            span = reached - began
            at = began + span * steps / (len(values) - 1) if len(values) > 1 else np.full(len(steps), began)
            # The last one sits *on* the edge's far end, which is a vertex, and
            # it has to land on that vertex's own distance rather than a hair
            # away from it: ``began + (reached - began)`` is not ``reached``,
            # and the two then merge into a pair of points at one position.
            at[-1] = reached if len(values) > 1 else began
            current["height"].append(values[first:])
            current["distance"].append(at)
        joined = len(values) > 0

    return [{key: np.concatenate(value) if value else np.empty(0, dtype=float) for key, value in run.items()} for run in runs]


def _scale(runs: list[dict[str, np.ndarray]], carried: float) -> None:
    """Stretch a composed chain onto the length the chain says it is.

    The page does the same thing for the same reason: one length, so a profile's
    axis, a popup's figure and an exported file all end on the same number. It
    also takes out the difference between measuring a metre in a projection and
    measuring it flat in degrees, which is what lets the two writers agree on
    where a 5 m gap is.

    Args:
        runs: The chain's stretches, changed in place
        carried: The length the chain carries, in metres
    """
    total = max((float(run["along"][-1]) for run in runs if len(run["along"])), default=0.0)
    if not (carried > 0 and total > 0):
        return
    factor = carried / total
    for run in runs:
        run["along"] *= factor
        run["distance"] *= factor


def _fill(run: dict[str, np.ndarray], gap_m: float) -> np.ndarray:
    """Put a point wherever two are further apart than the gap, and height them.

    **Where the model was read, that is where a point goes.** The samples are
    laid into the track before anything is spaced evenly, so every reading the
    height model gave comes out in the file as itself rather than as an
    interpolation between the two readings on either side of it. Measured with
    the points spaced evenly instead: the ascent read back off the file's own
    ``<ele>`` values came out **47 m under** the figure the same file states for
    the 42 km Rundtur, and 2,637 chains disagreed with their own extensions. A
    file whose points do not reproduce the number printed in it is a file that
    has to be believed rather than read.

    Args:
        run: One stretch, from :func:`_compose`
        gap_m: How far apart two points may be

    Returns:
        ``(n, 3)`` of x, y and height, the height NaN wherever the model was not
        read across the two samples the point falls between
    """
    xy, along, distance = run["xy"], run["along"], run["distance"]
    if len(xy) < 2 or not np.isfinite(run["height"]).any():
        # Nothing was read along this stretch, so there is nothing to fill it
        # for. A crossing keeps the two ends the ferry runs between.
        return np.column_stack([xy, np.full(len(xy), np.nan)]) if len(xy) else np.empty((0, 3), dtype=float)

    # Every vertex and every sample, each once. An edge's first and last sample
    # sit on its end vertices and are the same float here, so the union drops
    # the copy rather than writing a step of no length.
    inside = distance[(distance > along[0]) & (distance < along[-1])]
    merged = np.union1d(along, inside)

    # And the samples are not as close together as their step suggests: an edge
    # of 12 m gets three of them, 6 m apart. Whatever is still wider than the
    # gap is divided evenly — one interval more than the number of points put
    # in, so every interval comes out at or under the gap rather than anywhere
    # under twice it.
    steps = np.diff(merged)
    intervals = np.maximum(np.ceil(steps / gap_m), 1.0).astype(np.int64)
    segment = np.repeat(np.arange(len(steps)), intervals)
    rank = np.arange(len(segment)) - np.repeat(np.cumsum(intervals) - intervals, intervals) + 1
    fraction = rank / intervals[segment]
    positions = merged[segment] + fraction * steps[segment]
    # A position already in the list is written as itself rather than as a
    # fraction of the way to itself: ``a + 1.0 * (b - a)`` is not ``b``, and a
    # sample that misses its own distance by an ulp is interpolated instead of
    # read.
    landed = rank == intervals[segment]
    positions[landed] = merged[segment[landed] + 1]
    positions = np.concatenate([merged[:1], positions])

    return np.column_stack([_placed(positions, xy, along), _heights_at(positions, distance, run["height"])])


def _placed(positions: np.ndarray, xy: np.ndarray, along: np.ndarray) -> np.ndarray:
    """Put each position back on the line the vertices draw.

    Args:
        positions: Distances along the stretch
        xy: The stretch's vertices
        along: Where each of them lies

    Returns:
        ``(n, 2)``, with a vertex written as the coordinate the surveyor
        recorded rather than as a point computed between it and its neighbour
    """
    below = np.clip(np.searchsorted(along, positions, side="right") - 1, 0, len(along) - 2)
    span = along[below + 1] - along[below]
    fraction = np.clip(np.divide(positions - along[below], span, out=np.zeros(len(positions)), where=span > 0), 0.0, 1.0)
    placed = xy[below] + fraction[:, None] * (xy[below + 1] - xy[below])
    placed[fraction <= 0.0] = xy[below[fraction <= 0.0]]
    placed[fraction >= 1.0] = xy[below[fraction >= 1.0] + 1]
    return np.asarray(placed)


def _heights_at(positions: np.ndarray, distance: np.ndarray, height: np.ndarray) -> np.ndarray:
    """Read the height model at a set of distances along a stretch.

    Args:
        positions: Distances along the stretch to read at
        distance: Where each sample lies
        height: What was read at each, NaN where nothing was

    Returns:
        One height per position, NaN wherever either of the two samples it lies
        **between** says nothing. Interpolating across a gap would invent
        ground, and an invented height is worse in a file than a missing one:
        nothing downstream can tell the two apart. A position landing *on* a
        sample takes that sample and asks nothing of its neighbour — it is the
        reading, not a point between two of them, and discarding it because the
        next sample is missing would throw away a height the model gave.
    """
    if len(distance) < 2:
        return np.full(len(positions), np.nan)

    below = np.clip(np.searchsorted(distance, positions, side="right") - 1, 0, len(distance) - 2)
    span = distance[below + 1] - distance[below]
    fraction = np.clip(np.divide(positions - distance[below], span, out=np.zeros(len(positions)), where=span > 0), 0.0, 1.0)
    low, high = height[below], height[below + 1]
    return np.where(fraction <= 0.0, low, np.where(fraction >= 1.0, high, low + fraction * (high - low)))


def _lines(parts: list[np.ndarray], part_of: np.ndarray, chains: int, source: Any, target: Any, index: pd.Index) -> gpd.GeoSeries:
    """Turn the composed points into one geometry per chain, in the target CRS.

    Args:
        parts: ``(n, 3)`` of x, y and height per stretch, in chain order
        part_of: Which chain each stretch belongs to
        chains: How many chains there are
        source: CRS the points are in
        target: CRS to write them in
        index: Index of the chain frame, for the result to be aligned to

    Returns:
        One line per chain, or a multi-line for a chain whose stretches do not
        join — 90 chains here reach a node twice, none of them needs it, and a
        track drawn straight across ground nobody walked is a route that cannot
        be followed
    """
    if not parts:
        return gpd.GeoSeries(np.full(chains, None, dtype=object), index=index, crs=target)

    counts = np.array([len(part) for part in parts], dtype=np.int64)
    stacked = np.vstack(parts)
    belongs = np.repeat(np.arange(len(parts)), counts)

    # Reprojected flat and rebuilt with the heights afterwards, never carried
    # through as a Z: pyproj answers a NaN ordinate with a NaN coordinate, and
    # the point loses its position along with its height.
    flat = np.asarray(shapely.linestrings(stacked[:, :2], indices=belongs))
    if source is not None and target is not None:
        flat = gpd.GeoSeries(flat, crs=source).to_crs(target).to_numpy()
    placed = shapely.get_coordinates(flat)
    lines = np.asarray(shapely.linestrings(np.column_stack([placed, stacked[:, 2]]), indices=belongs))

    # The stretches are in chain order, so each chain's are one slice of them
    # rather than something to search for — 11,290 scans of 11,290 stretches is
    # a hundred million comparisons for an answer two lookups give.
    wanted = np.arange(chains)
    first = np.searchsorted(part_of, wanted, side="left")
    last = np.searchsorted(part_of, wanted, side="right")
    geometries: list[Any] = [None] * chains
    for chain in range(chains):
        own = lines[first[chain] : last[chain]]
        if len(own) == 1:
            geometries[chain] = own[0]
        elif len(own) > 1:
            geometries[chain] = shapely.multilinestrings(own)
    return gpd.GeoSeries(geometries, index=index, crs=target)
