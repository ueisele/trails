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
    # Create temporary GeoDataFrame
    gdf = gpd.GeoDataFrame([1], geometry=[geometry], crs=crs)

    # If in geographic coordinates (lat/lon), project to appropriate UTM
    if gdf.crs and gdf.crs.to_epsg() == 4326:
        # Get centroid to determine UTM zone
        lon = geometry.centroid.x
        # Calculate UTM zone (Norway is mostly in zones 32-35)
        utm_zone = int((lon + 180) / 6) + 1
        utm_epsg = 32600 + utm_zone  # Northern hemisphere

        # Project to UTM
        gdf = gdf.to_crs(f"EPSG:{utm_epsg}")

    # Return length (now in meters if projected)
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
