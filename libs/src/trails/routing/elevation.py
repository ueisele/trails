"""The ground under the network, and the figures read off it.

Every walked edge gains a real series of heights, sampled along it at a fixed
step. Out of that come two sets of figures, and **they are not
interchangeable**:

- **per edge: ascent and descent**, which is the granularity an elevation-aware
  weight needs and the only thing it is good for
- **per chain: ascent, descent, high and low point**, computed over the chain's
  *full* series, for anything a reader is shown

A route is a chain's case again, not an edge's: lay the edges it uses end to end
as :func:`chain_series` does and read the figures off that. Summing what the
edges themselves carry gives 67 % of it over this network — a route reported
that way would quote a third less climb than the popup for the same ground.

**Descent is stored wherever ascent is.** A chain is oriented so that its id
stays stable across builds, not because a walker is obliged to take it that way,
so an ascent alone is true in one direction and silent about the other. The high
and low point carry no threshold and could disagree with nothing, but the popup
that shows them is rendered at build time, so they have to be here with the
rest.

**Never sum the per-edge figures to get the per-chain one.** The reported ascent
ignores gains under a threshold, and that threshold restarts at every edge
boundary. In this park's network 42 % of the edges are shorter than five metres
and the median is 6.9 m, so most of them report no climb at all, and a chain of
twenty such edges rising sixty metres would sum to zero. Summing does not
approximate the figure, it destroys it. :func:`chain_series` lays the chain's
own series out instead, from the same samples, by walking its edges end to end —
a walk that lives in :mod:`trails.routing.order`, because the browser has to lay
the same edges out in the same order and two walks would eventually disagree.

**A crossing is not sampled.** There is no ground under a ferry, and a height
service asked about open water answers with a depth — a coastal profile that
dives to -276 m is what that looks like. An inferred connector *is* sampled:
nobody drew it, which is what a connector is, but there is ground under it.

**A gap is carried as a gap.** Where nothing could be read the series holds NaN
rather than a number, and a climb is never counted across one: nothing is known
about the ground between the reading before it and the reading after.

This module knows nothing about where the heights come from. It is handed a
callable, and what that costs to answer, and what it remembers between builds,
is the caller's business.
"""

import math
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import replace

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from trails.routing.graph import Network
from trails.routing.order import lay_out, runs_backwards
from trails.routing.sources import FERRY

#: How far apart the samples are laid along an edge. Measured against a dense
#: reference every 2.5 m along one real route, 5 m misses at most 1.14 m between
#: its own samples where 10 m misses 2.79 m — the difference between a visible
#: ledge and a smooth line. Below 5 m the interpolation error falls under the
#: height model's own vertical uncertainty and there is nothing left to win.
DEFAULT_STEP_M = 5.0

#: A gain smaller than this is not counted as climb. Without it the figure is
#: not a property of the ground but of how finely it was measured: one route
#: here reads 1,214 m sampled every 5 m and 965 m every 100 m, a 26 % swing,
#: because finer sampling counts more noise as climbing. With it the same route
#: reads 996 / 992 / 994 m at 5, 10 and 15 m. A figure that no longer depends on
#: how you measured it is the only kind worth showing.
DEFAULT_ASCENT_THRESHOLD_M = 5.0

#: Heights for an ``(n, 2)`` array of coordinates, NaN where nothing could be
#: read. In the CRS the network was built in.
Heights = Callable[[np.ndarray], np.ndarray]

#: What a chain's series says about it beyond the series itself. Four figures
#: rather than one, and computed together because they are read together: a
#: popup and the profile panel both show all of them, and two places asking the
#: same question must not get two answers.
PROFILE_COLUMNS = ("ascent", "descent", "high_m", "low_m")

#: What separates two stretches of a chain that do not join. A single NaN is
#: enough: an ascent run breaks at it, which is the whole point.
_GAP = np.array([math.nan])


def sample_count(length_m: float, step_m: float = DEFAULT_STEP_M) -> int:
    """How many samples a line of a given length is given.

    **At least two, whatever the length.** 28,373 edges in this park's network
    are under one metre and 97,974 under five, so "every 5 m" has to mean a
    floor of two rather than a floor of none — an edge nobody sampled has no
    profile, no ascent and no ends to join its neighbours at.

    Args:
        length_m: Length of the line
        step_m: How far apart the samples are laid

    Returns:
        Number of samples, counting both ends
    """
    if step_m <= 0:
        raise ValueError(f"the sampling step has to be positive, got {step_m}")
    return max(2, int(length_m // step_m) + 1)


def sample_along(geometries: Sequence[LineString] | np.ndarray, step_m: float = DEFAULT_STEP_M) -> tuple[np.ndarray, np.ndarray]:
    """Interpolate points along each line.

    The samples are spread evenly between the two ends rather than laid from one
    of them, which is what makes an edge's last sample the same coordinate as
    its neighbour's first: most of the duplication a coordinate-keyed store
    absorbs is edge ends meeting at a node, and over this network it is 28 % of
    the work.

    Args:
        geometries: Lines to sample, in a metric CRS
        step_m: How far apart the samples are laid

    Returns:
        Every sample as ``(n, 2)`` coordinates, and how many of them each line
        got, in input order

    Raises:
        ValueError: If a line holds no coordinates at all. Interpolating along
            one yields an empty point, which is then dropped rather than
            returned — the counts and the coordinates would disagree, and every
            line after it would be given its neighbour's heights with nothing
            raised. The graph never produces one, since an edge of no length is
            discarded when it is cut; this is here because the two are public
            and a caller's geometry is not this module's to trust.
    """
    lines = np.asarray(geometries, dtype=object)
    if not len(lines):
        return np.empty((0, 2), dtype=float), np.empty(0, dtype=np.int64)

    empty = np.flatnonzero(shapely.is_empty(lines) | shapely.is_missing(lines))
    if len(empty):
        raise ValueError(f"{len(empty):,} of {len(lines):,} lines hold no coordinates, the first at position {empty[0]}")

    lengths = shapely.length(lines)
    counts = np.array([sample_count(float(length), step_m) for length in lengths], dtype=np.int64)
    positions = np.concatenate([np.linspace(0.0, float(length), count) for length, count in zip(lengths, counts, strict=True)])
    points = shapely.line_interpolate_point(np.repeat(lines, counts), positions)
    return shapely.get_coordinates(points), counts


def ascent(elevations: Sequence[float] | np.ndarray, threshold_m: float = DEFAULT_ASCENT_THRESHOLD_M) -> float:
    """Total climb along a series of heights, ignoring gains under a threshold.

    A climb counts once the series has turned away from its low point by
    ``threshold_m``; anything shallower is noise the sampling invented and is
    dropped along with the descent that follows it. The smoothing is on the
    reported figure alone — the series itself is never touched, because a
    profile is drawn from it.

    Args:
        elevations: Heights along one line, NaN where nothing was read
        threshold_m: Gains under this are not counted

    Returns:
        Metres climbed, counting only the stretches something was read along, or
        NaN where nothing was read at all. A stretch shorter than two readings
        contributes nothing rather than being guessed at.
    """
    series = np.asarray(elevations, dtype=float)
    known = ~np.isnan(series)
    if not known.any():
        return math.nan
    return sum(_climb(series[start:end], threshold_m) for start, end in _stretches(known))


def descent(elevations: Sequence[float] | np.ndarray, threshold_m: float = DEFAULT_ASCENT_THRESHOLD_M) -> float:
    """Total fall along a series of heights, ignoring losses under a threshold.

    :func:`ascent` read the other way up, and stored beside it rather than left
    to be derived: a chain is oriented so that its id stays stable across
    builds, not because a walker is obliged to take it in that direction.

    Args:
        elevations: Heights along one line, NaN where nothing was read
        threshold_m: Losses under this are not counted

    Returns:
        Metres descended, or NaN where nothing was read at all
    """
    return ascent(-np.asarray(elevations, dtype=float), threshold_m)


def profile_of(elevations: Sequence[float] | np.ndarray, threshold_m: float = DEFAULT_ASCENT_THRESHOLD_M) -> dict[str, float]:
    """Read everything a series says about the line it was taken along.

    Args:
        elevations: Heights along one line, NaN where nothing was read
        threshold_m: Gains and losses under this are not counted

    Returns:
        :data:`PROFILE_COLUMNS`, every one of them NaN where nothing was read.
        The high and low point are the readings themselves, with no threshold on
        them: a summit is where it is however it was reached.
    """
    series = np.asarray(elevations, dtype=float)
    read = bool((~np.isnan(series)).any())
    return {
        "ascent": ascent(series, threshold_m),
        "descent": descent(series, threshold_m),
        "high_m": float(np.nanmax(series)) if read else math.nan,
        "low_m": float(np.nanmin(series)) if read else math.nan,
    }


def _stretches(known: np.ndarray) -> list[tuple[int, int]]:
    """Find the runs of consecutive readings in a series.

    Args:
        known: Whether each sample was read

    Returns:
        ``(start, end)`` per run, as half-open positions
    """
    padded = np.concatenate(([False], known, [False]))
    changes = np.flatnonzero(padded[1:] != padded[:-1])
    return list(zip(changes[0::2].tolist(), changes[1::2].tolist(), strict=True))


def _climb(values: np.ndarray, threshold_m: float) -> float:
    """Sum the climbs of one uninterrupted run of readings.

    Args:
        values: Heights, none of them missing
        threshold_m: Gains under this are not counted

    Returns:
        Metres climbed
    """
    heights = values.tolist()
    total = 0.0
    # Where the run began, and how far it has reached since. A reversal only
    # ends the run once it exceeds the threshold, so a dip smaller than that
    # leaves both alone and the climb carries straight on over it.
    anchor = extreme = heights[0]
    for height in heights[1:]:
        if extreme >= anchor:
            if height > extreme:
                extreme = height
            elif extreme - height >= threshold_m:
                total += extreme - anchor
                anchor, extreme = extreme, height
        elif height < extreme:
            extreme = height
        elif height - extreme >= threshold_m:
            anchor, extreme = extreme, height
    # The run the series ends on is judged by the same threshold as any other.
    # Counting it whatever it came to is what would put a metre of noise on the
    # end of every one of the 97,974 edges here shorter than the threshold, and
    # make the per-edge figures sum to something that looks like the per-chain
    # one without being it.
    if extreme - anchor >= threshold_m:
        total += extreme - anchor
    return total


def with_elevation(
    network: Network,
    heights: Heights,
    *,
    step_m: float = DEFAULT_STEP_M,
    threshold_m: float = DEFAULT_ASCENT_THRESHOLD_M,
) -> Network:
    """Give every walked edge its heights, and every chain its ascent.

    Args:
        network: The network to measure
        heights: Called once, with every sample of every walked edge, in the
            network's own CRS
        step_m: How far apart the samples are laid along an edge
        threshold_m: Gains under this are not counted as climb

    Returns:
        A copy of the network whose edges carry ``elevations``, ``ascent`` and
        ``descent``, and whose chains carry :data:`PROFILE_COLUMNS`. A ferry
        edge carries no samples and no figures: it was never asked about.

    Raises:
        ValueError: If the heights do not answer every sample
    """
    edges = network.edges
    walked = np.asarray(edges["kind"] != FERRY, dtype=bool)
    coordinates, counts = sample_along(edges.geometry.to_numpy()[walked], step_m)

    read = np.asarray(heights(coordinates), dtype=float).reshape(-1)
    if len(read) != len(coordinates):
        raise ValueError(f"asked for {len(coordinates):,} heights and got {len(read):,}")

    # An edge nothing was read along keeps an empty series rather than none, so
    # anything laying edges end to end can concatenate without a special case.
    series: list[np.ndarray] = [np.empty(0, dtype=float) for _ in range(len(edges))]
    if len(counts):
        for position, values in zip(np.flatnonzero(walked).tolist(), np.split(read, np.cumsum(counts)[:-1]), strict=True):
            series[position] = values

    measured = edges.assign(
        elevations=pd.Series(series, index=edges.index, dtype=object),
        ascent=pd.Series([ascent(values, threshold_m) for values in series], index=edges.index, dtype="float64"),
        descent=pd.Series([descent(values, threshold_m) for values in series], index=edges.index, dtype="float64"),
    )
    profiles = chain_profiles(network.chains, measured, threshold_m=threshold_m)
    return replace(network, edges=measured, chains=network.chains.assign(**{column: profiles[column] for column in PROFILE_COLUMNS}))


def chain_profiles(chains: gpd.GeoDataFrame, edges: gpd.GeoDataFrame, *, threshold_m: float = DEFAULT_ASCENT_THRESHOLD_M) -> pd.DataFrame:
    """Read each chain's own series and everything it says.

    Args:
        chains: The chains, carrying ``chain_id`` and their geometry
        edges: The edges, carrying ``chain_id``, their nodes and ``elevations``
        threshold_m: Gains and losses under this are not counted

    Returns:
        :data:`PROFILE_COLUMNS` per chain, aligned to ``chains``, all NaN where
        nothing was read along it — which is every ferry crossing
    """
    lying_on: dict[object, list[int]] = defaultdict(list)
    for position, chain_id in enumerate(edges["chain_id"].tolist()):
        # An inferred connector names no chain: nobody drew it, so it lies on
        # nothing and belongs to no chain's profile.
        if chain_id is not None and not pd.isna(chain_id):
            lying_on[chain_id].append(position)

    pairs = list(zip(edges["from_node"].to_numpy(dtype=np.int64).tolist(), edges["to_node"].to_numpy(dtype=np.int64).tolist(), strict=True))
    values = list(edges["elevations"])
    geometries = edges.geometry.to_numpy()

    read: list[dict[str, float]] = []
    for chain_id, geometry in zip(chains["chain_id"].tolist(), chains.geometry.tolist(), strict=True):
        members = lying_on.get(chain_id, [])
        read.append(profile_of(_series_of(members, pairs, values, geometries, geometry), threshold_m))
    return pd.DataFrame(read, index=chains.index, columns=list(PROFILE_COLUMNS)).astype("float64")


def chain_series(edges: gpd.GeoDataFrame, geometry: LineString | None = None) -> np.ndarray:
    """Lay one chain's edges end to end and read the heights along it.

    A chain is linear, so its edges form a path: each shares a node with the
    next. Following that path is what turns a bag of edges into a series, and a
    series is the only thing either an ascent or a profile can be read off.

    Args:
        edges: The edges of one chain, carrying ``from_node``, ``to_node`` and
            ``elevations``
        geometry: The chain, to orient the result by. Not cosmetic: a series
            read backwards reports the chain's descent as its ascent. Without it
            the direction the walk happened to take is kept.

    Returns:
        The heights along the chain, each node it passes through counted once
    """
    pairs = list(zip(edges["from_node"].to_numpy(dtype=np.int64).tolist(), edges["to_node"].to_numpy(dtype=np.int64).tolist(), strict=True))
    return _series_of(list(range(len(edges))), pairs, list(edges["elevations"]), edges.geometry.to_numpy(), geometry)


def _series_of(
    members: Sequence[int],
    pairs: Sequence[tuple[int, int]],
    values: Sequence[np.ndarray],
    geometries: np.ndarray,
    geometry: BaseGeometry | None,
) -> np.ndarray:
    """Lay a chain's edges end to end.

    Args:
        members: Positions of the edges lying on this chain
        pairs: ``(from_node, to_node)`` per edge
        values: Heights per edge
        geometries: Geometry per edge
        geometry: The chain, to orient the result by

    Returns:
        The heights along the chain
    """
    parts: list[np.ndarray] = []
    for run in lay_out(members, pairs):
        laid = _joined([(values[position], reversed_) for position, reversed_ in run])
        if runs_backwards(run, geometries, geometry):
            laid = laid[::-1]
        # Where the walk had to start again, the two stretches do not join, so
        # they are carried apart rather than as one series: a climb counted
        # across a step nothing was measured along is invented.
        if parts:
            parts.append(_GAP)
        parts.append(laid)
    return np.concatenate(parts) if parts else np.empty(0, dtype=float)


def _joined(pieces: Sequence[tuple[np.ndarray, bool]]) -> np.ndarray:
    """Concatenate the series of a run of edges.

    Args:
        pieces: ``(heights, reversed)`` in walking order

    Returns:
        One series, with the node between two edges counted once rather than
        twice — both of them sample it, since every edge samples both its ends
    """
    laid: list[np.ndarray] = []
    for values, reversed_ in pieces:
        ordered = values[::-1] if reversed_ else values
        laid.append(ordered[1:] if laid else ordered)
    return np.concatenate(laid) if laid else np.empty(0, dtype=float)
