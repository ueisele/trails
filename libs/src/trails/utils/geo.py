"""Basic geometry utilities for trail data."""

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import MultiLineString
from shapely.geometry.base import BaseGeometry, BaseMultipartGeometry
from shapely.ops import linemerge, unary_union

#: The points a bearing is rounded to, clockwise from north. Eight rather than
#: four: a third of a real path network lies more than 30° from a cardinal axis,
#: where a four-point label is simply wrong, and at eight nothing is more than
#: 22.5° out.
COMPASS_POINTS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def calculate_lengths_meters(gdf: gpd.GeoDataFrame) -> pd.Series:
    """Calculate lengths for all geometries in meters (optimized for batch).

    This is much faster than calling calculate_length_meters on each geometry
    individually, as it performs CRS checks and transformations only once.

    Args:
        gdf: GeoDataFrame with line geometries

    Returns:
        Series with lengths in meters
    """
    # Handle empty GeoDataFrame
    if gdf.empty:
        return pd.Series([], dtype=float)

    # Check if already in meters
    if gdf.crs and gdf.crs.axis_info:
        units = gdf.crs.axis_info[0].unit_name
        if units == "metre":
            return gdf.geometry.length

    # Only try to estimate UTM if we have a CRS
    if gdf.crs:
        try:
            utm_crs = gdf.estimate_utm_crs()
            if utm_crs:
                gdf_utm = gdf.to_crs(utm_crs)
                return gdf_utm.geometry.length
        except ValueError, RuntimeError:
            # Can't estimate UTM (e.g., empty bounds or no CRS)
            pass

    # Fallback - return lengths in current CRS units
    return gdf.geometry.length


def thin_points(
    gdf: gpd.GeoDataFrame,
    min_spacing_m: float,
    group_by: str | None = None,
    priority: str | None = None,
    metric_crs: str = "EPSG:25833",
) -> gpd.GeoDataFrame:
    """Drop points that sit too close to one already kept.

    Repeating a label along an extended feature only works if the copies are far
    enough apart to read as separate; closer than that they collide and look like
    a rendering fault. Deduplicating identical positions is a different job — do
    that at the source, and use this for display spacing.

    Args:
        gdf: Point features
        min_spacing_m: Minimum distance to keep between retained points
        group_by: Thin within each value of this column instead of globally,
            e.g. thin each place name separately
        priority: Column to prefer by, lowest value kept first
        metric_crs: Projected CRS used for the distance test

    Returns:
        Subset of the input, in the input CRS and input column order
    """
    if gdf.empty or min_spacing_m <= 0:
        return gdf

    working = gdf.to_crs(metric_crs)
    if priority is not None:
        working = working.sort_values(priority, kind="stable")

    groups = working.groupby(group_by, sort=False) if group_by else [(None, working)]

    keep: list[int] = []
    for _, frame in groups:
        kept_geoms: list[BaseGeometry] = []
        for index, geometry in zip(frame.index, frame.geometry, strict=True):
            if geometry is None or geometry.is_empty:
                continue
            if any(geometry.distance(other) < min_spacing_m for other in kept_geoms):
                continue
            kept_geoms.append(geometry)
            keep.append(index)

    return gdf.loc[sorted(keep)]


def attach_nearest(
    gdf: gpd.GeoDataFrame,
    source: gpd.GeoDataFrame,
    fields: dict[str, str],
    max_distance_m: float,
    metric_crs: str = "EPSG:25833",
    min_overlap: float = 0.0,
) -> gpd.GeoDataFrame:
    """Copy attributes onto each feature from the closest feature of another set.

    For pairing a dataset that has the geometry with one that has the names, when
    the two share no identifier. Nothing is copied beyond ``max_distance_m``, so
    a feature with no counterpart keeps empty values rather than borrowing those
    of something unrelated further away.

    Proximity alone is a weak test for lines: at a junction the first metres of a
    side road lie well within tolerance of the main road, and would take its name.
    ``min_overlap`` demands that the line actually run *along* its counterpart
    rather than merely touch it.

    Args:
        gdf: Features to attach attributes to
        source: Features to take attributes from
        fields: Mapping of column in ``source`` to column name on the result
        max_distance_m: Furthest a counterpart may be, in metres
        metric_crs: Projected CRS the distance is measured in
        min_overlap: Least share of a line that must lie within
            ``max_distance_m`` of its counterpart, between 0 and 1. Features
            without a length, such as points, are not subject to it.

    Returns:
        Copy of ``gdf`` carrying the requested columns. Where several source
        features tie for nearest, the first wins.
    """
    attached = gdf.copy()
    if attached.empty or source.empty:
        for target in fields.values():
            attached[target] = pd.Series(dtype=object)
        return attached

    projected = attached.to_crs(metric_crs)
    right = source[[*fields, source.geometry.name]].rename(columns=fields).to_crs(metric_crs)
    joined = gpd.sjoin_nearest(
        projected,
        right,
        how="left",
        max_distance=max_distance_m,
        distance_col="_attach_distance",
    )

    # sjoin_nearest emits one row per tied match; keep the first per input feature.
    joined = joined[~joined.index.duplicated(keep="first")]

    keep = joined["index_right"].notna()
    if min_overlap > 0 and keep.any():
        # pandas-stubs for pandas 3 types to_numpy against Series[Never], which a
        # Series[BaseGeometry] does not satisfy. Stubs only; the call is unchanged.
        counterparts = right.geometry.reindex(joined.loc[keep, "index_right"]).to_numpy()  # type: ignore[misc]
        lines = projected.geometry.loc[keep.index[keep]]
        shares = [
            line.intersection(other.buffer(max_distance_m)).length / line.length if line.length else 1.0
            for line, other in zip(lines, counterparts, strict=True)
        ]
        keep.loc[keep] = pd.Series(shares, index=lines.index) >= min_overlap

    for target in fields.values():
        attached[target] = joined[target].where(keep)
    return attached


def merge_lines(gdf: gpd.GeoDataFrame, group_by: str | None = None) -> gpd.GeoDataFrame:
    """Join touching line segments into continuous lines.

    Some sources deliver a path as dozens of short pieces, which bloats maps and
    exports without adding information. Merging keeps the geometry but collapses
    the feature count. Per-feature attributes are dropped, since merged lines can
    span several originals; pass ``group_by`` to merge within one attribute and
    keep it.

    Args:
        gdf: GeoDataFrame with line geometries
        group_by: Column to merge within, retained on the result

    Returns:
        GeoDataFrame of merged LineStrings in the input CRS. Empty input returns
        an empty result with the same columns.
    """
    if gdf.empty:
        columns = [group_by] if group_by else []
        return gpd.GeoDataFrame({column: [] for column in columns}, geometry=[], crs=gdf.crs)

    groups = gdf.groupby(group_by) if group_by else [(None, gdf)]

    values: list[object] = []
    geometries = []
    for value, frame in groups:
        union = unary_union(frame.geometry.tolist())
        # linemerge only accepts collections; a lone segment comes back bare.
        merged: BaseGeometry = linemerge(union) if isinstance(union, MultiLineString) else union
        parts = list(merged.geoms) if isinstance(merged, BaseMultipartGeometry) else [merged]
        for part in parts:
            if part.is_empty or part.geom_type != "LineString":
                continue
            values.append(value)
            geometries.append(part)

    data = {group_by: values} if group_by else {}
    return gpd.GeoDataFrame(data, geometry=geometries, crs=gdf.crs)


def endpoint_bearings(gdf: gpd.GeoDataFrame, metric_crs: str = "EPSG:25833") -> pd.Series:
    """Measure which way each line runs, from its first vertex to its last.

    **In a projected CRS, and that is the whole point of the argument.** Taken
    flat from longitude and latitude the answer is a different one: at 65° N a
    degree of longitude is 0.41 of a degree of latitude, so ``atan2`` over raw
    coordinates squashes every bearing towards the meridian. Measured over this
    park's chains it puts two in five of them into a different one of
    :data:`COMPASS_POINTS` — not a rounding difference, a wrong label.

    Args:
        gdf: Features whose ends are to be measured; anything but a line has no
            direction and comes back NaN
        metric_crs: Projected CRS to measure in

    Returns:
        Degrees clockwise from north, aligned to ``gdf``. NaN where a line ends
        where it began — a ring has no bearing and needs none, since it climbs
        and falls the same whichever way round it is walked — and where a
        geometry is missing or empty.

    Raises:
        ValueError: If the features say nothing about the CRS they are in.
            Measuring them where they lie would then be measuring lon/lat flat,
            which is the one answer this function exists to avoid — and it is
            wrong silently, in a way that reads like a bearing.
    """
    if gdf.crs is None and not gdf.empty:
        raise ValueError(f"the features carry no CRS, so they cannot be measured in {metric_crs}")

    empty = pd.Series(np.nan, index=gdf.index, dtype="float64")
    if gdf.empty:
        return empty

    projected = gdf.to_crs(metric_crs)
    geometries = projected.geometry.to_numpy()
    counts = np.asarray(shapely.get_num_coordinates(geometries), dtype=np.int64)
    drawn = counts > 0
    if not drawn.any():
        return empty

    # First and last vertex of each geometry, taken off one flat array of
    # coordinates rather than per feature, so a MultiLineString is handled by
    # the same code as a LineString: its ends are the ends of its parts.
    coordinates = shapely.get_coordinates(geometries)
    ends = np.cumsum(counts)
    delta = coordinates[ends[drawn] - 1] - coordinates[(ends - counts)[drawn]]

    # Clockwise from north, which is what a compass point means: the x
    # displacement is the sine and the y the cosine, the reverse of the usual
    # atan2(y, x).
    bearing = np.degrees(np.arctan2(delta[:, 0], delta[:, 1])) % 360
    empty.loc[drawn] = np.where((delta[:, 0] == 0) & (delta[:, 1] == 0), np.nan, bearing)
    return empty


def compass_points(bearings: pd.Series) -> pd.Series:
    """Name each bearing as one of :data:`COMPASS_POINTS`.

    Args:
        bearings: Degrees clockwise from north, NaN where there is no bearing

    Returns:
        The point each bearing rounds to, aligned to ``bearings``, and None
        where there is none
    """
    # **This is the only place a bearing is named**, and it has to stay that
    # way: a rounded label is a threshold, and a second implementation of one
    # disagrees with the first exactly on the boundaries. Anything that shows a
    # direction carries what comes out of here rather than deriving it — see
    # ``FIGURE_DECIMALS`` and the panel, which is handed the point and has no
    # rule of its own.
    #
    # floor(x + 0.5) rather than numpy's rint, which rounds a half to even. Both
    # are defensible and neither is now forced by anything, so the reason to keep
    # this one is simply that it is the one in use: 241 of this park's chains lie
    # within half a degree of a boundary, and swapping the rule renames the
    # direction on some of them for no gain.
    values = bearings.to_numpy(dtype="float64")
    known = ~np.isnan(values)
    index = np.zeros(len(values), dtype=np.int64)
    index[known] = np.floor(values[known] / 45 + 0.5).astype(np.int64) % len(COMPASS_POINTS)
    return pd.Series(
        [COMPASS_POINTS[position] if is_known else None for position, is_known in zip(index.tolist(), known.tolist(), strict=True)],
        index=bearings.index,
        dtype="object",
    )
