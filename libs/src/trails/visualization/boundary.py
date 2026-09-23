"""The protected area's drawn outline, separate from its analytical geometry."""

import geopandas as gpd
from pyproj import CRS

# Malingsbo-Kloten's closed county seams measured at most 0.061 m wide;
# the closing's widest changed sliver was 0.655 m (2026-09-23).
BOUNDARY_TOLERANCE_M = 1.0


def close_for_display(boundary: gpd.GeoDataFrame, metric_crs: str, *, source_records: int = 1) -> gpd.GeoDataFrame:
    """Close seams of a dissolved area in a copy used only for drawing.

    Args:
        boundary: The analytical area, with polygon geometry and a declared CRS
        metric_crs: The source's projected CRS, whose units must be metres
        source_records: How many register records were dissolved into the area

    Returns:
        A copy in the input CRS, retaining its attributes and index. Single
        records pass through without reprojection; only dissolved areas close.

    Raises:
        ValueError: If the record count is not positive, or a dissolved area
            has an unsuitable CRS or non-polygonal geometry
    """
    if source_records < 1:
        raise ValueError("The boundary must come from at least one source record")
    # A single record has no county join. Closing its sharp tips needlessly
    # moved Lomsdal-Visten's outline by 1.132 m in the measured candidate.
    if source_records == 1:
        return boundary.copy()
    if boundary.crs is None:
        raise ValueError("The boundary must declare its CRS")
    target = CRS.from_user_input(metric_crs)
    if not target.is_projected or any(axis.unit_conversion_factor != 1 for axis in target.axis_info):
        raise ValueError("The boundary's display CRS must be projected in metres")
    if not boundary.geometry.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError("The boundary must contain polygons")
    drawn = boundary.to_crs(target)
    # Mitre joins keep real corners sharp; only the display copy loses slivers.
    drawn.geometry = drawn.geometry.buffer(BOUNDARY_TOLERANCE_M, join_style="mitre").buffer(-BOUNDARY_TOLERANCE_M, join_style="mitre")
    return drawn.to_crs(boundary.crs)
