"""GPX export functionality for trail data."""

from datetime import UTC, datetime
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
    # Timezone-aware: utcnow() returns a naive datetime that claims to be UTC
    # and is deprecated for exactly that reason, and this value is written
    # into a file with a Z on the end.
    time_elem.text = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

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
    simplify_tolerance: float | None = None,
    max_trails: int | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Export GeoDataFrame of trails to GPX file.

    **Nothing is thinned unless a caller asks for it.** An exported track is the
    one thing that leaves this machine, and it carries the resolution its source
    recorded — that is a decision, not an oversight, and it is the opposite of
    what the map does with the copy it draws. The default used to be 1e-5
    degrees, about 1.1 m, which is under the survey accuracy of the best source
    here and still dropped 62 % of FKB's vertices and 65 % of UT.no's. On a path
    that matters: the target platforms do not know these ways and cannot rebuild
    a line between points they were not given.

    Args:
        gdf: GeoDataFrame with trail data
        output_path: Path for output GPX file
        name_field: Field to use for track names
        desc_fields: Fields to include in track descriptions
        simplify_tolerance: Tolerance for geometry simplification, in degrees.
            None keeps every vertex, which is what an export is for.
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

            # Counted off the written element, not off the geometry that went
            # in. Counting the input reports what the file would have held if
            # nothing thinned it — this file said 305,248 points while holding
            # 115,655, and the figure is one a reader is meant to trust.
            stats["total_points"] += len(track.findall("trkseg/trkpt"))

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

    # Millions of bytes, which is what "MB" says and what a file manager
    # shows. Dividing by 1024**2 and calling it MB reported 7.72 for a file
    # of 8.09.
    stats["file_size_mb"] = float(output_path.stat().st_size) / 1e6

    return output_path, stats
