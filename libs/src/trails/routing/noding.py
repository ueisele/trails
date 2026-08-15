"""Cutting lines wherever they meet.

Both stages of the build need this: a source is noded against itself to find its
own junctions, and every source is noded against all the others to build the
routing graph. The difference is only what goes in.
"""

import math
from bisect import bisect_right
from collections.abc import Sequence
from typing import Any, cast

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import substring, unary_union

#: Working CRS. Everything here is measured in metres, and this is Norway.
DEFAULT_METRIC_CRS = "EPSG:25833"

#: Distance below which two coordinates are treated as the same point.
NODE_TOLERANCE_M = 0.01

#: Clipping mask, in the CRS of the features it is applied to.
ClipGeometry = BaseGeometry | gpd.GeoDataFrame | gpd.GeoSeries


def lines_of(geoms: gpd.GeoSeries) -> list[LineString]:
    """Read a geometry column as the LineStrings it holds.

    Everything here runs on frames that have been through
    :func:`working_lines`, which leaves nothing else in them.

    Args:
        geoms: Geometry column

    Returns:
        Its geometries
    """
    return cast(list[LineString], list(geoms))


def clip_geometry(clip: ClipGeometry, source_crs: Any, metric_crs: str) -> BaseGeometry:
    """Bring a clipping mask into the working CRS.

    Args:
        clip: Mask as a bare geometry, which is read in ``source_crs``, or as a
            GeoDataFrame or GeoSeries, which carries its own
        source_crs: CRS a bare geometry is assumed to be in
        metric_crs: Working CRS

    Returns:
        The mask as one geometry in ``metric_crs``
    """
    if isinstance(clip, gpd.GeoDataFrame | gpd.GeoSeries):
        return clip.to_crs(metric_crs).union_all()
    return gpd.GeoSeries([clip], crs=source_crs).to_crs(metric_crs).union_all()


def clip_lines(gdf: gpd.GeoDataFrame, mask: BaseGeometry) -> gpd.GeoDataFrame:
    """Cut lines to an extent, leaving the ones already inside it alone.

    Clipping is an overlay, and an overlay nodes whatever it touches. A GPS
    track that doubles back along itself comes out of one shattered into
    hundreds of pieces and a kilometre shorter — even where it lies wholly
    inside the extent and nothing should have happened to it at all.

    Args:
        gdf: Lines to cut, in the same CRS as the mask
        mask: Extent to cut them to

    Returns:
        The lines inside the extent, in input order where nothing was cut
    """
    crosses = ~gdf.geometry.covered_by(mask)
    if not crosses.any():
        return gdf
    cut = gpd.clip(gdf[crosses], gpd.GeoSeries([mask], crs=gdf.crs))
    return gpd.GeoDataFrame(pd.concat([gdf[~crosses], cut]), geometry=gdf.geometry.name, crs=gdf.crs)


def working_lines(gdf: gpd.GeoDataFrame, clip: ClipGeometry | None, metric_crs: str) -> gpd.GeoDataFrame:
    """Project, clip and reduce a dataset to plain LineStrings.

    Args:
        gdf: Features to prepare
        clip: Extent to cut them to, or None to keep everything
        metric_crs: Working CRS

    Returns:
        Copy in ``metric_crs`` holding one LineString per row, indexed from zero.
        Empty and zero-length geometries are dropped: they have no direction, so
        nothing downstream can chain or node them.
    """
    working = gdf.to_crs(metric_crs)
    if clip is not None:
        working = clip_lines(working, clip_geometry(clip, gdf.crs, metric_crs))

    working = working.explode(index_parts=False)
    working = working[(working.geom_type == "LineString") & ~working.geometry.is_empty & (working.geometry.length > 0)]
    return gpd.GeoDataFrame(working.reset_index(drop=True), geometry="geometry", crs=metric_crs)


def _points_in(geometry: BaseGeometry) -> list[Point]:
    """Read the point positions out of an intersection result.

    Two lines that merely cross intersect in a point; two that run along each
    other for a stretch intersect in a line, and then what matters is where that
    stretch begins and ends.

    Args:
        geometry: Result of intersecting two lines

    Returns:
        Positions to cut both lines at
    """
    points: list[Point] = []
    for part in shapely.get_parts(shapely.get_parts(geometry)):
        if isinstance(part, Point):
            points.append(part)
        elif isinstance(part, LineString) and not part.is_empty:
            coords = part.coords
            points.append(Point(coords[0]))
            points.append(Point(coords[-1]))
    return points


def intersection_points(geoms: gpd.GeoSeries) -> list[list[Point]]:
    """Find every position at which each line meets another, or itself.

    Args:
        geoms: Lines to node against each other, in a projected CRS

    Returns:
        One list of positions per input line, in input order. Endpoints are not
        included: they are cut positions by construction.
    """
    frame = gpd.GeoDataFrame(geometry=geoms.reset_index(drop=True))
    found: list[list[Point]] = [[] for _ in range(len(frame))]
    if frame.empty:
        return found

    pairs = gpd.sjoin(frame, frame, predicate="intersects")
    left = pairs.index.to_numpy()
    right = pairs["index_right"].to_numpy()
    # The join reports every pair twice, plus every line against itself.
    keep = left < right
    left, right = left[keep], right[keep]

    values = frame.geometry.to_numpy()
    for one, other, meeting in zip(left, right, shapely.intersection(values[left], values[right]), strict=True):
        points = _points_in(meeting)
        found[one].extend(points)
        found[other].extend(points)

    # A line crossing itself has junctions no pairing can see. Noding it alone
    # exposes them as the ends of the pieces it falls into.
    for position, geometry in enumerate(values):
        if not geometry.is_simple:
            for part in shapely.get_parts(unary_union(geometry)):
                found[position].extend((Point(part.coords[0]), Point(part.coords[-1])))
    return found


def cut_positions(geometry: LineString, points: list[Point], tolerance_m: float = NODE_TOLERANCE_M) -> list[float]:
    """Turn cut positions into distances along a line.

    Args:
        geometry: Line being cut
        points: Positions to cut it at, as returned by :func:`intersection_points`
        tolerance_m: Positions closer together than this are one position

    Returns:
        Ascending distances, always starting at 0 and ending at the line's
        length, so consecutive pairs describe the pieces the line falls into
    """
    length = geometry.length
    inside = sorted(distance for distance in (geometry.project(point) for point in points) if tolerance_m < distance < length - tolerance_m)

    positions = [0.0]
    for distance in inside:
        if distance - positions[-1] > tolerance_m:
            positions.append(distance)
    positions.append(length)
    return positions


def cut_line(geometry: LineString, positions: list[float]) -> list[LineString | None]:
    """Cut a line at a set of distances.

    Args:
        geometry: Line to cut
        positions: Ascending distances along it, from :func:`cut_positions`

    Returns:
        One entry per consecutive pair of positions, so the result lines up with
        the positions it came from. An entry is None where the cut left nothing.
    """
    pieces: list[LineString | None] = []
    for start, end in zip(positions[:-1], positions[1:], strict=True):
        piece = substring(geometry, start, end)
        pieces.append(piece if isinstance(piece, LineString) and piece.length > 0 else None)
    return pieces


def project_onto(geometry: LineString, points: list[Point]) -> list[float]:
    """Measure where a set of positions falls along a line, in order.

    A projection can land marginally behind the one before it, so the result is
    forced to ascend rather than producing a piece that runs backwards.

    Args:
        geometry: Line to measure along
        points: Positions to measure, in the order they occur along it

    Returns:
        Ascending distances, the first 0 and the last the line's length
    """
    distances = np.maximum.accumulate([geometry.project(point) for point in points])
    distances[0] = 0.0
    distances[-1] = geometry.length
    return [float(distance) for distance in distances]


def _walked(coords: Sequence[tuple[float, ...]]) -> list[float]:
    """Distance along a line at each of its vertices.

    Args:
        coords: The line's coordinates

    Returns:
        Ascending distances, starting at 0
    """
    walked = [0.0]
    for start, end in zip(coords[:-1], coords[1:], strict=True):
        walked.append(walked[-1] + math.dist(start[:2], end[:2]))
    return walked


def carry_positions(full: LineString, noding: LineString, positions: list[float]) -> list[float]:
    """Carry distances measured on a simplified copy back onto the full line.

    Projecting the positions back would be the obvious way and it is wrong for
    exactly the lines this exists for. A track that walks out and back along the
    same ground passes twice within a metre of itself, and a projection reports
    the *first* of the two — so every cut on the return leg lands on the
    outbound one, up to ninety metres from where it belongs.

    Simplification keeps a subset of the original vertices, so the two lines
    share their vertices in order, and those shared vertices are what bound the
    search: a position is mapped to the nearest point of the full line *between*
    the two shared vertices it falls between. That is exact at every vertex, and
    within them it cannot reach the other leg the way a projection along the
    whole line does.

    Args:
        full: The line as the source drew it
        noding: The simplified copy the positions were measured on
        positions: Ascending distances along ``noding``

    Returns:
        The same positions as distances along ``full``
    """
    full_coords = list(full.coords)
    noding_coords = list(noding.coords)

    shared: list[int] = []
    cursor = 0
    for coordinate in noding_coords:
        while cursor < len(full_coords) and full_coords[cursor] != coordinate:
            cursor += 1
        if cursor >= len(full_coords):
            # Not a subset after all, so there is nothing to walk along.
            return project_onto(full, [noding.interpolate(position) for position in positions])
        shared.append(cursor)
        cursor += 1

    full_at, noding_at = _walked(full_coords), _walked(noding_coords)
    carried = []
    for position in positions:
        segment = min(max(bisect_right(noding_at, position) - 1, 0), len(noding_at) - 2)
        start, end = full_at[shared[segment]], full_at[shared[segment + 1]]

        # Between two shared vertices, take the point of the real line nearest
        # the position rather than the proportional one. The two vertices bound
        # the search, so this cannot wander onto another part of the line the
        # way a projection along the whole of it would; and within them it is
        # the difference between landing sixteen metres from the crossing and
        # landing on it.
        window = substring(full, start, end) if end > start else None
        if isinstance(window, LineString) and window.length > 0:
            carried.append(start + float(window.project(noding.interpolate(position))))
        else:
            carried.append(start)

    # A window can double back on itself, and then its nearest point runs
    # backwards; a piece with a negative length is worse than an imprecise one.
    ascending = [float(value) for value in np.maximum.accumulate(carried)]
    ascending[0] = 0.0
    ascending[-1] = full.length
    return ascending
