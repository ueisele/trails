"""Basic geometry utilities for trail data."""

import geopandas as gpd
import pandas as pd


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
