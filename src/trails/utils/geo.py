"""Basic geometry utilities for trail data."""

import geopandas as gpd
from shapely.geometry import LineString


def get_bounds(gdf: gpd.GeoDataFrame) -> tuple[float, float, float, float]:
    """Get bounding box of geodataframe.

    Args:
        gdf: GeoDataFrame to get bounds from

    Returns:
        Tuple of (minx, miny, maxx, maxy)
    """
    bounds = gdf.total_bounds
    return float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3])


def calculate_length_meters(geometry: LineString, crs: str | None = None) -> float:
    """Calculate length of geometry in meters.

    Args:
        geometry: LineString geometry
        crs: Coordinate reference system of the geometry

    Returns:
        Length in meters
    """
    gdf = gpd.GeoDataFrame([1], geometry=[geometry], crs=crs)

    # Check if already in meters
    if gdf.crs and gdf.crs.axis_info:
        units = gdf.crs.axis_info[0].unit_name
        if units == "metre":
            return float(gdf.geometry[0].length)

    # Only project if not in meters
    utm_crs = gdf.estimate_utm_crs()
    if utm_crs:
        gdf = gdf.to_crs(utm_crs)

    return float(gdf.geometry[0].length)


def simplify_for_visualization(gdf: gpd.GeoDataFrame, tolerance: float = 10) -> gpd.GeoDataFrame:
    """Simplify geometry for faster visualization.

    Args:
        gdf: GeoDataFrame to simplify
        tolerance: Simplification tolerance in map units

    Returns:
        GeoDataFrame with simplified geometry
    """
    # Create copy to avoid modifying original
    simplified = gdf.copy()
    simplified["geometry"] = simplified.geometry.simplify(tolerance)
    return simplified


def get_geometry_info(gdf: gpd.GeoDataFrame) -> dict:
    """Get information about geometries in GeoDataFrame.

    Args:
        gdf: GeoDataFrame to analyze

    Returns:
        Dictionary with geometry statistics
    """
    return {
        "total_features": len(gdf),
        "geometry_types": gdf.geometry.geom_type.value_counts().to_dict(),
        "crs": str(gdf.crs) if gdf.crs else None,
        "bounds": get_bounds(gdf) if not gdf.empty else None,
        "valid_geometries": gdf.geometry.is_valid.sum() if not gdf.empty else 0,
        "empty_geometries": gdf.geometry.is_empty.sum() if not gdf.empty else 0,
    }
