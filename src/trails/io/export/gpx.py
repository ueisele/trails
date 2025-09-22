"""GPX export functionality for trail data."""

from datetime import datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from lxml import etree
from shapely.geometry import LineString, MultiLineString


def create_gpx_document() -> etree.Element:
    """Create a GPX document with proper namespace and schema."""
    gpx = etree.Element(
        "gpx",
        attrib={
            "version": "1.1",
            "creator": "trails-analysis",
            "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation": (
                "http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd"
            ),
        },
        nsmap={
            None: "http://www.topografix.com/GPX/1/1",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        },
    )

    # Add metadata
    metadata = etree.SubElement(gpx, "metadata")
    etree.SubElement(metadata, "name").text = "Norwegian Trails Export"
    etree.SubElement(metadata, "desc").text = "Trail data from Geonorge"
    time_elem = etree.SubElement(metadata, "time")
    time_elem.text = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    return gpx


def linestring_to_track_segment(geometry: LineString, simplify_tolerance: float | None = None) -> etree.Element:
    """Convert a LineString to a GPX track segment.

    Args:
        geometry: LineString geometry in WGS84
        simplify_tolerance: Optional tolerance for simplification (degrees)

    Returns:
        GPX track segment element
    """
    trkseg = etree.Element("trkseg")

    # Optionally simplify geometry
    if simplify_tolerance:
        geometry = geometry.simplify(simplify_tolerance, preserve_topology=True)  # type: ignore[assignment]

    # Extract coordinates
    coords = list(geometry.coords)

    for lon, lat in coords:
        etree.SubElement(trkseg, "trkpt", attrib={"lat": str(lat), "lon": str(lon)})
        # Could add elevation here if available
        # etree.SubElement(trkpt, "ele").text = str(elevation)

    return trkseg


def trail_to_track(
    trail: pd.Series,
    name_field: str = "trail_name",
    desc_fields: list[str] | None = None,
    simplify_tolerance: float | None = None,
) -> etree.Element:
    """Convert a trail (GeoDataFrame row) to a GPX track.

    Args:
        trail: Single row from a GeoDataFrame
        name_field: Field to use for track name
        desc_fields: Fields to include in description
        simplify_tolerance: Optional tolerance for geometry simplification

    Returns:
        GPX track element
    """
    trk = etree.Element("trk")

    # Add name
    name = trail.get(name_field, f"Trail {trail.name if hasattr(trail, 'name') else 'Unknown'}")
    if pd.notna(name):
        etree.SubElement(trk, "name").text = str(name)

    # Add description
    if desc_fields:
        desc_parts = []
        for field in desc_fields:
            if field in trail and pd.notna(trail[field]):
                desc_parts.append(f"{field}: {trail[field]}")
        if desc_parts:
            etree.SubElement(trk, "desc").text = " | ".join(desc_parts)

    # Add type if available
    if "type" in trail and pd.notna(trail["type"]):
        etree.SubElement(trk, "type").text = str(trail["type"])

    # Handle geometry
    geometry = trail.geometry

    if isinstance(geometry, LineString):
        trkseg = linestring_to_track_segment(geometry, simplify_tolerance)
        trk.append(trkseg)
    elif isinstance(geometry, MultiLineString):
        for linestring in geometry.geoms:
            trkseg = linestring_to_track_segment(linestring, simplify_tolerance)
            trk.append(trkseg)

    return trk


def export_to_gpx(
    gdf: gpd.GeoDataFrame,
    output_path: Path,
    name_field: str = "trail_name",
    desc_fields: list[str] | None = None,
    simplify_tolerance: float | None = 0.00001,
    max_trails: int | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Export GeoDataFrame of trails to GPX file.

    Args:
        gdf: GeoDataFrame with trail data
        output_path: Path for output GPX file
        name_field: Field to use for track names
        desc_fields: Fields to include in track descriptions
        simplify_tolerance: Tolerance for geometry simplification (degrees)
        max_trails: Maximum number of trails to export

    Returns:
        Tuple of (output_path, statistics_dict)
    """
    # Ensure we're in WGS84
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    # Default description fields
    if desc_fields is None:
        desc_fields = ["maintenance_responsible", "difficulty", "marking"]

    # Limit trails if specified
    export_gdf = gdf.head(max_trails) if max_trails else gdf

    # Create GPX document
    gpx = create_gpx_document()

    # Statistics
    stats: dict[str, Any] = {
        "total_trails": len(export_gdf),
        "total_points": 0,
        "skipped_trails": 0,
    }

    # Add each trail as a track
    for idx, trail in export_gdf.iterrows():
        try:
            if trail.geometry is None or trail.geometry.is_empty:
                stats["skipped_trails"] += 1
                continue

            track = trail_to_track(trail, name_field=name_field, desc_fields=desc_fields, simplify_tolerance=simplify_tolerance)
            gpx.append(track)

            # Count points
            if isinstance(trail.geometry, LineString):
                stats["total_points"] += len(trail.geometry.coords)
            elif isinstance(trail.geometry, MultiLineString):
                for line in trail.geometry.geoms:
                    stats["total_points"] += len(line.coords)

        except Exception as e:
            print(f"Warning: Failed to export trail {idx}: {e}")
            stats["skipped_trails"] += 1

    # Write to file
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tree = etree.ElementTree(gpx)
    tree.write(
        str(output_path),
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8",
    )

    stats["file_size_mb"] = float(output_path.stat().st_size) / (1024 * 1024)

    return output_path, stats


def filter_trails_by_bbox(
    gdf: gpd.GeoDataFrame,
    bbox: tuple[float, float, float, float],
    buffer_m: float = 0,
) -> gpd.GeoDataFrame:
    """Filter trails that intersect with a bounding box.

    Args:
        gdf: GeoDataFrame with trail data
        bbox: Bounding box as (minx, miny, maxx, maxy) in same CRS as gdf
        buffer_m: Optional buffer in meters around bbox

    Returns:
        Filtered GeoDataFrame
    """
    from shapely.geometry import box

    # Create bounding box polygon
    bbox_geom = box(*bbox)

    # Buffer if requested (need to project to meters first)
    if buffer_m > 0 and gdf.crs and gdf.crs.to_epsg() in [4326, 4258]:
        # Project to UTM for buffering
        utm_crs = "EPSG:25833"  # UTM 33N for Norway
        bbox_gdf = gpd.GeoDataFrame([1], geometry=[bbox_geom], crs=gdf.crs)
        bbox_gdf = bbox_gdf.to_crs(utm_crs)
        bbox_geom = bbox_gdf.geometry[0].buffer(buffer_m)
        # Project back
        bbox_gdf = gpd.GeoDataFrame([1], geometry=[bbox_geom], crs=utm_crs)
        bbox_gdf = bbox_gdf.to_crs(gdf.crs)
        bbox_geom = bbox_gdf.geometry[0]  # type: ignore[assignment]

    # Use spatial index for efficient filtering
    return gdf[gdf.intersects(bbox_geom)].copy()
