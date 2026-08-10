"""Basic geometry utilities for trail data."""

import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiLineString
from shapely.geometry.base import BaseGeometry, BaseMultipartGeometry
from shapely.ops import linemerge, unary_union


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
        except (ValueError, RuntimeError):
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
