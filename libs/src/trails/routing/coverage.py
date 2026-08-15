"""What the sources say about the ground an edge runs over.

Two of the figures a route has to report cannot be read off any single field.
How much of it is waymarked is spread across two registers that record different
things, and whether anything records a path at all is a question only the
*silence* of every source can answer. Both are decided here, and both the same
way: by how much of an edge lies near a mask built out of raw source geometry.

**Masks rather than the edge's own attributes**, for a measured reason. A
marking flag reaches an edge only through the chain it lies on, and a chain
running across features that disagree about it carries both values at once — in
this park 38 chains and 158 km of N50 paths read ``JA / NEI``, which is exactly
the ground where the answer matters. A mask of the features carrying ``JA`` has
no such problem, and it treats every source alike: an edge comes out marked
because of where it lies, not because of the tag it was built from.

**The half-length guard is what makes the test mean anything.** This repository
has already paid once for taking nearness alone as a join, when 23 % of the road
names landed on the side road at a junction; an edge that merely crosses a marked
route would otherwise count along its whole length.

Both fields are derived per edge rather than per chain, because both are summed
in kilometres and a chain takes one value along its whole length. They are the
only two attributes that sit on the edge; everything else is read through
``chain_id``.
"""

from collections.abc import Sequence

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry.base import BaseGeometry

from trails.routing.sources import PATH

#: An edge running along something a source states is waymarked.
MARKED = "marked"

#: An edge running along something a source states is *not* waymarked.
UNMARKED = "unmarked"

#: No source states either way. Never to be reported as unmarked: the largest
#: source in a network like this one carries no marking information at all, and
#: calling its ground unmarked would assert what the data does not say.
UNKNOWN = "unknown"

#: How close an edge lies to a marking mask to count as running along it. Wide
#: enough for two datasets to disagree about where a path runs, narrow enough
#: that it is the same path.
DEFAULT_MARKED_M = 10.0

#: How close anything has to lie for an edge to count as having a path recorded
#: along it. Deliberately generous: the more that counts as recorded, the more
#: it means when nothing is.
DEFAULT_RECORDED_M = 25.0

#: How much of an edge has to lie near a mask before the mask decides it.
DEFAULT_MIN_SHARE = 0.5

#: Lines to test an edge against, in the working CRS of the edges.
Mask = gpd.GeoSeries | Sequence[BaseGeometry] | np.ndarray


def _geometries(mask: Mask) -> np.ndarray:
    """Read a mask as a plain array of geometries.

    Args:
        mask: Lines to test against

    Returns:
        The geometries, as an object array
    """
    if isinstance(mask, gpd.GeoSeries):
        return np.asarray(mask.to_numpy(), dtype=object)
    return np.asarray(mask, dtype=object)


def _in_one_crs(edges: gpd.GeoDataFrame, *masks: Mask) -> None:
    """Refuse a mask that is not in the same CRS as the edges.

    Everything here is a distance in metres, and a mask in degrees is not near
    anything: every query would miss, every edge would come back unknown with no
    path recorded, and the report would look plausible. A mask given as bare
    geometry carries no CRS to check and is the caller's to get right.

    Args:
        edges: Edges being classified
        *masks: What they are being tested against

    Raises:
        ValueError: If a mask states a different CRS
    """
    for mask in masks:
        if isinstance(mask, gpd.GeoSeries) and mask.crs is not None and edges.crs is not None and mask.crs != edges.crs:
            raise ValueError(f"mask is in {mask.crs}, the edges are in {edges.crs}")


def share_within(lines: Sequence[BaseGeometry] | np.ndarray, mask: Mask, distance_m: float) -> np.ndarray:
    """Measure how much of each line lies within a distance of a mask.

    Args:
        lines: Lines to measure, in a metric CRS
        mask: Lines to measure against, in the same CRS
        distance_m: How close counts as lying along the mask

    Returns:
        Share of each line's length lying within ``distance_m`` of the mask,
        between 0 and 1, in input order
    """
    geometries = np.asarray(lines, dtype=object)
    shares = np.zeros(len(geometries), dtype=float)

    targets = _geometries(mask)
    if not len(geometries) or not len(targets):
        return shares

    lengths = shapely.length(geometries)
    buffers = shapely.buffer(targets, distance_m)
    near, found = shapely.STRtree(targets).query(geometries, predicate="dwithin", distance=distance_m)
    if not len(near):
        return shares

    # The longest single overlap first, so the two cases that need no union at
    # all are the first entry of their group.
    covered = shapely.length(shapely.intersection(geometries[near], buffers[found]))
    order = np.lexsort((-covered, near))
    near, found, covered = near[order], found[order], covered[order]
    starts = np.concatenate(([0], np.flatnonzero(np.diff(near)) + 1, [len(near)]))

    for start, end in zip(starts[:-1], starts[1:], strict=True):
        line = int(near[start])
        length = float(lengths[line])
        if length <= 0:
            continue
        if covered[start] >= length or end - start == 1:
            # One mask line covering the whole edge, or only one near it at all.
            shares[line] = min(float(covered[start]) / length, 1.0)
            continue
        # Otherwise the overlaps have to be merged before they are measured, and
        # merging them as *lines* does not work: two mask lines running along
        # each other produce collinear pieces that do not dissolve, and measured
        # that way one edge here came out 3.6 times its own length. Merging the
        # buffers into one area first is what makes the measurement exact.
        whole = shapely.intersection(geometries[line], shapely.union_all(buffers[found[start:end]]))
        shares[line] = min(float(shapely.length(whole)) / length, 1.0)
    return shares


def _walked(edges: gpd.GeoDataFrame) -> np.ndarray:
    """Say which edges are walked, and so have either question to answer.

    A ferry crossing is not walking and an inferred connector was drawn by
    nobody, so neither belongs in a figure summed over the ground a walker
    covers.

    Args:
        edges: Edges carrying a ``kind``

    Returns:
        One boolean per edge
    """
    return np.asarray(edges["kind"] == PATH, dtype=bool)


def waymarked(
    edges: gpd.GeoDataFrame,
    marked: Mask,
    unmarked: Mask,
    *,
    distance_m: float = DEFAULT_MARKED_M,
    min_share: float = DEFAULT_MIN_SHARE,
) -> pd.Series:
    """Say, per edge, what the sources state about the ground being waymarked.

    An edge is :data:`MARKED` where at least ``min_share`` of its length lies
    within ``distance_m`` of the marked mask, failing that :data:`UNMARKED` on
    the same test against the unmarked mask, and failing both :data:`UNKNOWN`.
    Marked wins where an edge meets both, because a source stating a route is
    waymarked is saying something about that route, while a parallel path stating
    it is not says nothing about the route beside it.

    Args:
        edges: Edges to classify, carrying a ``kind``, in a metric CRS
        marked: Lines whose source states they are waymarked
        unmarked: Lines whose source states they are not
        distance_m: How close counts as running along a mask
        min_share: How much of an edge has to lie that close

    Returns:
        :data:`MARKED`, :data:`UNMARKED` or :data:`UNKNOWN` per edge, aligned to
        ``edges``, and NA on every edge that is not walked — a crossing is none
        of the three

    Raises:
        ValueError: If a mask states a different CRS from the edges
    """
    _in_one_crs(edges, marked, unmarked)
    walked = _walked(edges)
    geometries = edges.geometry.to_numpy()[walked]

    on_marked = share_within(geometries, marked, distance_m) >= min_share
    on_unmarked = share_within(geometries, unmarked, distance_m) >= min_share

    answers = np.full(len(edges), None, dtype=object)
    answers[walked] = np.where(on_marked, MARKED, np.where(on_unmarked, UNMARKED, UNKNOWN))
    return pd.Series(answers, index=edges.index, dtype="string")


def no_path_recorded(
    edges: gpd.GeoDataFrame,
    recorded: Mask,
    *,
    distance_m: float = DEFAULT_RECORDED_M,
    min_share: float = DEFAULT_MIN_SHARE,
) -> pd.Series:
    """Say, per edge, whether no source draws anything along it.

    True where less than ``min_share`` of an edge lies within ``distance_m`` of
    anything in ``recorded``.

    **False asserts nothing whatever.** It does not mean there is a path: the
    sources over-record, drawing a line wherever one might plausibly run and
    disclosing little about how any of it was captured, so a line beside an edge
    is no evidence of anything on the ground. Only the silence of every source
    carries information, because a liberal recorder that says nothing at all has
    said something. This field is to be read in that one direction, and any text
    that shows it has to say the same.

    Args:
        edges: Edges to test, carrying a ``kind``, in a metric CRS
        recorded: Every line from the sources that draw physical ways
        distance_m: How close a line has to lie to count as recording the ground
        min_share: How much of an edge has to lie that close

    Returns:
        One value per edge, aligned to ``edges``, and NA on every edge that is
        not walked. A crossing has nothing within reach by its nature, and
        reporting that as ground with no path recorded would put the whole of it
        into a figure about walking.

    Raises:
        ValueError: If the mask states a different CRS from the edges
    """
    _in_one_crs(edges, recorded)
    walked = _walked(edges)
    geometries = edges.geometry.to_numpy()[walked]

    answers = np.full(len(edges), None, dtype=object)
    answers[walked] = share_within(geometries, recorded, distance_m) < min_share
    return pd.Series(answers, index=edges.index, dtype="boolean")
