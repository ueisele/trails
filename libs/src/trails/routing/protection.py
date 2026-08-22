"""Which protected areas an edge lies in, and for how many of its metres.

The third thing an edge carries about the ground it runs over, beside whether
the sources say it is waymarked and whether any of them records a path along it.
It is here for the same reason those two are: a planned route sums it in
kilometres, and a chain cannot hold it because it changes along a chain's length.

**Measured against the areas themselves, not sampled.** The sibling module
:mod:`trails.routing.coverage` tests nearness to a mask, where an exact answer
would be meaningless — two datasets disagreeing about where a path runs is the
whole subject. A protected area is not like that: its boundary is a legal line
with a published geometry, and the length of an edge inside it is a number, so
this takes the number. That is what makes a figure of ten metres worth writing
down rather than an artefact of a step size.

**A crossing is asked nothing.** There is no walking distance under a ferry, so
there is no protected walking distance either, and a route that reported the
water it was carried over as ground it walked in a marine protected area would
be saying something false in a figure meant to be read closely. An inferred
connector *is* asked: nobody drew it, which is what a connector is, but a walker
covers its ground and that ground is inside the boundary or outside it.

**An edge that retraces itself is measured a little short, and by how much was
measured.** Intersecting a line with a polygon nodes the line first, so where a
GPS track doubles back along ground it has already covered, the overlay counts
that ground once. Over this network it costs **67.5 m in the 647.8 km** the
walked edges spend inside Lomsdal-Visten — five edges of 60,576, the worst a
120.9 m UT.no edge with ten repeated vertices that comes out 40 m short. Every
other area of the nineteen agrees with a segment-by-segment measurement to under
a millimetre. The error only ever goes one way, so what an edge carries is a
lower bound; measuring segment by segment closes it and costs forty times the
time, which is not a trade worth making for a hundredth of a per cent.

**None and () are two different answers.** ``None`` is an edge that was never
asked — a crossing. ``()`` is an edge that was asked and lies in nothing. This
distinction has cost this repository real time three times over, with
``pd.NA``, with an empty string and with a register writing the word for
*nothing* into a name, so it is kept explicitly here rather than recovered later
from the ``kind`` column.
"""

from collections.abc import Sequence

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from trails.routing.sources import FERRY

#: What each edge carries: the areas it lies in, as ``(area id, metres)`` pairs.
PROTECTED_COLUMN = "protected"

#: How much of a route has to lie inside an area before the route says so.
#:
#: **A reported figure is a threshold like a rounded one**, and this is that
#: threshold said out loud. Without it a route brushing a corner of a boundary
#: reports an area it never entered and generates a pair of waypoints for it,
#: metres apart, in the file a reader takes into the terrain.
#:
#: A hundred metres, for three reasons that can each be checked. It is more than
#: six times the worst error the measurement can carry — a boundary the page
#: carries simplified to 5 m, plus half a sampling step at each of the two
#: crossings of a leg drawn straight. It is about a minute's walking, which is
#: the shortest passage for which *the route runs through here* describes the
#: walk rather than the geometry. And measured over this network it is not a
#: knife edge: of the nineteen areas the walked network touches, the nearest
#: below is 67 m and the nearest above 146 m, so moving it by half either way
#: changes nothing.
DEFAULT_TOUCHED_M = 100.0


def protected_within(edges: gpd.GeoDataFrame, areas: gpd.GeoDataFrame, *, id_field: str) -> pd.Series:
    """Measure how much of each edge lies inside each protected area.

    Args:
        edges: Edges to measure, carrying a ``kind``, in a metric CRS
        areas: Protected areas in the same CRS, one row each, carrying
            ``id_field``
        id_field: Column naming each area, which is what an edge records rather
            than a row number: a position in a frame is not something a cached
            graph and a later reader can be trusted to agree on

    Returns:
        One entry per edge, aligned to ``edges``: a tuple of ``(area id,
        metres)`` pairs ordered as ``areas`` is, empty where the edge lies in
        none of them, and ``None`` on every crossing, which was not asked

    Raises:
        ValueError: If the areas are in a different CRS from the edges, which
            would leave every edge outside every area and look like an answer,
            or if two of them carry the same id
    """
    if areas.crs is not None and edges.crs is not None and areas.crs != edges.crs:
        raise ValueError(f"the areas are in {areas.crs}, the edges are in {edges.crs}")

    identities = [str(value) for value in areas[id_field].tolist()]
    repeated = sorted({value for value in identities if identities.count(value) > 1})
    if repeated:
        raise ValueError(f"an area is named once and {repeated} name themselves more than once")

    walked = np.asarray(edges["kind"] != FERRY, dtype=bool)
    lines = edges.geometry.to_numpy()
    # Only the edges that have the question put to them go into the tree, so a
    # crossing cannot come back as a hit and be given an answer by accident.
    positions = np.flatnonzero(walked)
    found: list[list[tuple[str, float]]] = [[] for _ in range(len(edges))]

    if len(positions) and len(areas):
        tree = shapely.STRtree(lines[positions])
        for identity, shape in zip(identities, areas.geometry.to_numpy(), strict=True):
            hits = tree.query(shape, predicate="intersects")
            if not len(hits):
                continue
            inside = shapely.length(shapely.intersection(lines[positions[hits]], shape))
            # `intersects` is true where an edge only touches the boundary, and
            # a touch is zero metres of ground. Written down it would put every
            # area a route runs *past* into the route's own figure.
            for hit, metres in zip(hits[inside > 0], inside[inside > 0], strict=True):
                found[int(positions[int(hit)])].append((identity, float(metres)))

    answers = np.empty(len(edges), dtype=object)
    answers[:] = [tuple(entry) if inside else None for entry, inside in zip(found, walked.tolist(), strict=True)]
    return pd.Series(answers, index=edges.index, dtype=object)


#: What one edge carries: the areas it lies in, as ``(area id, metres)`` pairs,
#: or ``None`` where the question was never put to it.
Protected = tuple[tuple[str, float], ...] | None


def protected_metres(protected: Sequence[Protected] | pd.Series) -> dict[str, float]:
    """Add up how much ground lies in each area.

    Args:
        protected: What :func:`protected_within` produced, or any run of it

    Returns:
        Metres per area id, for the areas that carry any at all, largest first.
        An area nothing touches is left out rather than listed at zero: it is
        the answer to a question about *this* ground, not a census of the
        register.
    """
    summed: dict[str, float] = {}
    for entry in protected:
        if entry is None:
            continue
        for identity, metres in entry:
            summed[identity] = summed.get(identity, 0.0) + float(metres)
    return dict(sorted(summed.items(), key=lambda pair: -pair[1]))


def touched(metres: dict[str, float], threshold_m: float = DEFAULT_TOUCHED_M) -> dict[str, float]:
    """Keep the areas something spends more than a threshold inside.

    Args:
        metres: Metres per area id, from :func:`protected_metres`
        threshold_m: How much counts as being inside one

    Returns:
        The same mapping without the areas below the threshold
    """
    return {identity: value for identity, value in metres.items() if value >= threshold_m}
