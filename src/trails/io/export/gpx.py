"""GPX export functionality for trail data."""

import zipfile
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


def export_to_gpx_single_track(
    gdf: gpd.GeoDataFrame,
    output_path: Path,
    track_name: str = "Trail Network",
    name_field: str = "trail_name",
    desc_fields: list[str] | None = None,
    simplify_tolerance: float | None = 0.00001,
    max_trails: int | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Export GeoDataFrame as a single GPX track with multiple segments.

    This format is better for Outdooractive as it treats all trails as one entity
    that can be imported to "My Map" for trail planning.

    Args:
        gdf: GeoDataFrame with trail data
        output_path: Path for output GPX file
        track_name: Name for the single track containing all trails
        name_field: Field to use for segment identification
        desc_fields: Fields to include in track description
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

    # Create a single track element
    trk = etree.Element("trk")
    etree.SubElement(trk, "name").text = track_name

    # Build description with trail count and summary
    desc_parts = [f"Contains {len(export_gdf)} trail segments"]

    # Add summary of trail types if available
    if "special_hiking_trail_type" in export_gdf.columns:
        trail_types = export_gdf["special_hiking_trail_type"].value_counts().head(3)
        if not trail_types.empty:
            desc_parts.append("Types: " + ", ".join(f"{str(k)} ({v})" for k, v in trail_types.items() if k is not None))

    etree.SubElement(trk, "desc").text = " | ".join(desc_parts)

    # Statistics
    stats: dict[str, Any] = {
        "total_trails": len(export_gdf),
        "total_segments": 0,
        "total_points": 0,
        "skipped_trails": 0,
    }

    # Add each trail as a segment
    for idx, trail in export_gdf.iterrows():
        try:
            if trail.geometry is None or trail.geometry.is_empty:
                stats["skipped_trails"] += 1
                continue

            # Get trail name for comment
            trail_name = trail.get(name_field, f"Trail {idx}")

            # Handle different geometry types
            if isinstance(trail.geometry, LineString):
                # Add comment before segment (not standard but helpful)
                comment = etree.Comment(f" {trail_name} ")
                trk.append(comment)

                trkseg = linestring_to_track_segment(trail.geometry, simplify_tolerance)
                trk.append(trkseg)
                stats["total_segments"] += 1
                stats["total_points"] += len(trail.geometry.coords)

            elif isinstance(trail.geometry, MultiLineString):
                for i, linestring in enumerate(trail.geometry.geoms):
                    # Add comment for each part
                    comment = etree.Comment(f" {trail_name} (part {i + 1}) ")
                    trk.append(comment)

                    trkseg = linestring_to_track_segment(linestring, simplify_tolerance)
                    trk.append(trkseg)
                    stats["total_segments"] += 1
                    stats["total_points"] += len(linestring.coords)

        except Exception as e:
            print(f"Warning: Failed to export trail {idx}: {e}")
            stats["skipped_trails"] += 1

    # Add the single track to GPX
    gpx.append(trk)

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


def export_to_gpx_zip(
    gdf: gpd.GeoDataFrame,
    output_path: Path,
    name_field: str = "trail_name",
    desc_fields: list[str] | None = None,
    simplify_tolerance: float | None = 0.00001,
    max_trails: int | None = None,
    group_by: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Export GeoDataFrame as a ZIP file containing individual GPX files.

    This format is ideal for Outdooractive's Mass GPX Importer feature.

    Args:
        gdf: GeoDataFrame with trail data
        output_path: Path for output ZIP file
        name_field: Field to use for file names
        desc_fields: Fields to include in track descriptions
        simplify_tolerance: Tolerance for geometry simplification (degrees)
        max_trails: Maximum number of trails to export
        group_by: Optional field to group trails into folders

    Returns:
        Tuple of (output_path, statistics_dict)
    """
    import re

    # Ensure we're in WGS84
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    # Default description fields
    if desc_fields is None:
        desc_fields = ["maintenance_responsible", "difficulty", "marking"]

    # Limit trails if specified
    export_gdf = gdf.head(max_trails) if max_trails else gdf

    # Statistics
    stats: dict[str, Any] = {
        "total_files": 0,
        "total_trails": len(export_gdf),
        "skipped_trails": 0,
        "groups": [],
    }

    # Create ZIP file
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Create manifest file
        manifest_lines = ["Trail Export Manifest", "=" * 50, ""]
        manifest_lines.append(f"Export date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        manifest_lines.append(f"Total trails: {len(export_gdf)}")
        manifest_lines.append("")

        # Process each trail
        for idx, trail in export_gdf.iterrows():
            try:
                if trail.geometry is None or trail.geometry.is_empty:
                    stats["skipped_trails"] += 1
                    continue

                # Get trail name and sanitize for filename
                trail_name = str(trail.get(name_field, f"Trail_{idx}"))
                if pd.isna(trail_name) or trail_name == "nan":
                    trail_name = f"Trail_{idx}"

                # Sanitize filename
                safe_name = re.sub(r'[<>:"/\\|?*]', "_", trail_name)
                safe_name = safe_name[:100]  # Limit length

                # Determine folder if grouping
                folder = ""
                if group_by and group_by in trail and pd.notna(trail[group_by]):
                    group_value = str(trail[group_by])
                    folder = re.sub(r'[<>:"/\\|?*]', "_", group_value) + "/"
                    if folder not in stats["groups"]:
                        stats["groups"].append(folder)

                # Create individual GPX
                gpx = create_gpx_document()
                track = trail_to_track(trail, name_field=name_field, desc_fields=desc_fields, simplify_tolerance=simplify_tolerance)
                gpx.append(track)

                # Write to ZIP
                filename = f"{folder}{safe_name}.gpx"
                tree = etree.ElementTree(gpx)
                gpx_content = etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding="UTF-8")
                zipf.writestr(filename, gpx_content)

                # Add to manifest
                manifest_lines.append(f"- {filename}")
                if desc_fields:
                    for field in desc_fields:
                        if field in trail and pd.notna(trail[field]):
                            manifest_lines.append(f"  {field}: {trail[field]}")

                stats["total_files"] += 1

            except Exception as e:
                print(f"Warning: Failed to export trail {idx}: {e}")
                stats["skipped_trails"] += 1
                manifest_lines.append(f"- SKIPPED: {trail_name} (Error: {e})")

        # Add manifest to ZIP
        manifest_lines.append("")
        manifest_lines.append(f"Successfully exported: {stats['total_files']} files")
        manifest_lines.append(f"Skipped: {stats['skipped_trails']} trails")
        zipf.writestr("MANIFEST.txt", "\n".join(manifest_lines))

    stats["file_size_mb"] = float(output_path.stat().st_size) / (1024 * 1024)

    return output_path, stats


def find_connected_segments(
    segments: gpd.GeoDataFrame,
    tolerance_m: float = 50,
) -> list[list[int]]:
    """Find groups of connected trail segments.

    Args:
        segments: GeoDataFrame with LineString or MultiLineString geometries
        tolerance_m: Maximum distance in meters to consider segments connected

    Returns:
        List of lists, each containing indices of connected segments
    """
    import numpy as np
    from shapely.geometry import Point

    if len(segments) == 0:
        return []

    if len(segments) == 1:
        return [[0]]

    # Get CRS for distance calculations
    original_crs = segments.crs
    working_segments = segments.copy()

    # Convert to UTM for meter-based distance calculations if needed
    if original_crs and original_crs.to_epsg() == 4326:
        # Use UTM 33N for Norway
        working_segments = working_segments.to_crs("EPSG:25833")

    # Build connectivity matrix
    n_segments = len(working_segments)
    connected = np.zeros((n_segments, n_segments), dtype=bool)

    # Extract endpoints for each segment
    endpoints: list[tuple[Point, Point] | tuple[None, None]] = []
    for _idx, row in working_segments.iterrows():
        geom = row.geometry
        if geom and not geom.is_empty:
            # Handle both LineString and MultiLineString
            if geom.geom_type == "MultiLineString":
                # For MultiLineString, use the first and last points of the entire geometry
                first_line = geom.geoms[0]
                last_line = geom.geoms[-1]
                coords_first = list(first_line.coords)
                coords_last = list(last_line.coords)
                start_point = Point(coords_first[0])
                end_point = Point(coords_last[-1])
            else:  # LineString
                coords = list(geom.coords)
                start_point = Point(coords[0])
                end_point = Point(coords[-1])
            endpoints.append((start_point, end_point))
        else:
            endpoints.append((None, None))

    # Check connectivity between all pairs
    for i in range(n_segments):
        ep_i = endpoints[i]
        if ep_i[0] is None or ep_i[1] is None:
            continue

        for j in range(i + 1, n_segments):
            ep_j = endpoints[j]
            if ep_j[0] is None or ep_j[1] is None:
                continue

            # Check all endpoint combinations
            distances = [
                ep_i[0].distance(ep_j[0]),  # start-start
                ep_i[0].distance(ep_j[1]),  # start-end
                ep_i[1].distance(ep_j[0]),  # end-start
                ep_i[1].distance(ep_j[1]),  # end-end
            ]

            if min(distances) <= tolerance_m:
                connected[i, j] = True
                connected[j, i] = True

    # Find connected components using depth-first search
    visited = np.zeros(n_segments, dtype=bool)
    components = []

    def dfs(node: int, component: list[int]) -> None:
        visited[node] = True
        component.append(node)
        for neighbor in range(n_segments):
            if connected[node, neighbor] and not visited[neighbor]:
                dfs(neighbor, component)

    for i in range(n_segments):
        if not visited[i]:
            component: list[int] = []
            dfs(i, component)
            components.append(component)

    return components


def export_to_gpx_zip_smart(
    gdf: gpd.GeoDataFrame,
    output_path: Path,
    group_field: str = "trail_number",
    name_field: str = "trail_name",
    desc_fields: list[str] | None = None,
    simplify_tolerance: float | None = 0.00001,
    max_trails: int | None = None,
    folder_by: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Export GeoDataFrame as ZIP with smart trail grouping.

    Segments with the same trail_number (or name) are combined into single GPX files.
    Each segment is preserved as a separate track with its own metadata.

    Args:
        gdf: GeoDataFrame with trail data
        output_path: Path for output ZIP file
        group_field: Field to group trails by (default: trail_number)
        name_field: Field for trail names
        desc_fields: Fields to include in track descriptions
        simplify_tolerance: Tolerance for geometry simplification
        max_trails: Maximum number of trails to export
        folder_by: Optional field to organize into folders

    Returns:
        Tuple of (output_path, statistics_dict)
    """
    import re
    import zipfile

    # Ensure we're in WGS84
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    # Default description fields
    if desc_fields is None:
        desc_fields = ["maintenance_responsible", "difficulty", "marking", "special_hiking_trail_type"]

    # Limit trails if specified
    export_gdf = gdf.head(max_trails) if max_trails else gdf

    # Statistics
    stats: dict[str, Any] = {
        "total_files": 0,
        "total_segments": len(export_gdf),
        "merged_trails": 0,
        "split_trails": 0,
        "skipped_segments": 0,
        "groups": [],
    }

    # Create ZIP file
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Create manifest
        manifest_lines = ["Smart Trail Export Manifest", "=" * 50, ""]
        manifest_lines.append(f"Export date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        manifest_lines.append(f"Total segments: {len(export_gdf)}")
        manifest_lines.append(f"Grouping by: {group_field}")
        manifest_lines.append("")

        # Track used filenames to avoid duplicates
        used_filenames = {}

        # Group segments by trail identifier
        grouped_trails: dict[str, list] = {}

        for idx, segment in export_gdf.iterrows():
            # Skip invalid geometries
            if segment.geometry is None or segment.geometry.is_empty:
                stats["skipped_segments"] += 1
                continue

            # Determine group key - use trail_number if available, else trail_name
            group_key = None
            if group_field in segment and pd.notna(segment[group_field]):
                group_key = str(segment[group_field])
            elif name_field in segment and pd.notna(segment[name_field]):
                group_key = str(segment[name_field])
            else:
                group_key = f"Trail_{idx}"

            # Add to grouped trails
            if group_key not in grouped_trails:
                grouped_trails[group_key] = []
            grouped_trails[group_key].append((idx, segment))

        # Process each trail group
        for trail_id, segments in grouped_trails.items():
            if not segments:
                continue

            # Create GeoDataFrame for this trail's segments
            indices = [s[0] for s in segments]
            trail_segments = export_gdf.loc[indices].copy()

            # Group all segments with same trail_number into one component
            components = [list(range(len(trail_segments)))]

            # Get trail name for file naming
            first_segment = segments[0][1]
            trail_name = str(first_segment.get(name_field, trail_id))
            if pd.isna(trail_name) or trail_name == "nan":
                trail_name = trail_id

            # Sanitize base filename
            safe_name = re.sub(r'[<>:"/\\|?*]', "_", trail_name)
            safe_name = safe_name[:80]  # Leave room for part suffix

            # Add trail_number to name if available and different from trail_name
            if group_field in first_segment and pd.notna(first_segment[group_field]):
                trail_num = str(first_segment[group_field])
                # Only add number if it's not already part of the name
                if trail_num not in safe_name:
                    safe_name = f"{safe_name} ({trail_num})"

            # Determine folder
            folder = ""
            if folder_by and folder_by in first_segment and pd.notna(first_segment[folder_by]):
                folder_value = str(first_segment[folder_by])
                folder = re.sub(r'[<>:"/\\|?*]', "_", folder_value) + "/"
                if folder not in stats["groups"]:
                    stats["groups"].append(folder)

            # Export all segments as single file (no connectivity check)
            if len(components) == 1:
                # All segments in single file
                stats["merged_trails"] += 1

                # Create GPX with multiple tracks - one per segment to preserve metadata
                gpx = create_gpx_document()

                # Add each segment as a separate track to preserve individual metadata
                for seg_idx, comp_idx in enumerate(components[0], 1):
                    seg = trail_segments.iloc[comp_idx]

                    # Create a track for this segment
                    trk = etree.Element("trk")

                    # Name the track with trail name and segment number
                    segment_name = f"{trail_name} ({trail_num}) - Segment {seg_idx}/{len(components[0])}"
                    etree.SubElement(trk, "name").text = segment_name

                    # Build description with this segment's specific metadata
                    desc_parts = []
                    if group_field in seg and pd.notna(seg[group_field]):
                        desc_parts.append(f"Trail #{seg[group_field]}")
                    desc_parts.append(f"Segment {seg_idx} of {len(components[0])}")

                    # Add segment-specific metadata
                    if "local_id" in seg and pd.notna(seg["local_id"]):
                        desc_parts.append(f"local_id: {seg['local_id']}")

                    # Add all requested description fields for this specific segment
                    for field in desc_fields:
                        if field in seg and pd.notna(seg[field]):
                            value = seg[field]
                            # Format datetime fields nicely
                            if hasattr(value, "strftime"):
                                value = value.strftime("%Y-%m-%d")
                            elif "date" in field.lower() and pd.notna(value):
                                try:
                                    value = pd.to_datetime(value).strftime("%Y-%m-%d")
                                except Exception:
                                    pass
                            desc_parts.append(f"{field}: {value}")

                    # Add geometry info
                    if isinstance(seg.geometry, LineString):
                        desc_parts.append(f"Length: {seg.geometry.length * 111000:.0f}m")  # Rough conversion
                    elif isinstance(seg.geometry, MultiLineString):
                        desc_parts.append(f"Length: {seg.geometry.length * 111000:.0f}m")

                    if desc_parts:
                        etree.SubElement(trk, "desc").text = " | ".join(desc_parts)

                    # Add the geometry as track segments
                    if isinstance(seg.geometry, LineString):
                        trkseg = linestring_to_track_segment(seg.geometry, simplify_tolerance)
                        trk.append(trkseg)
                    elif isinstance(seg.geometry, MultiLineString):
                        for line in seg.geometry.geoms:
                            trkseg = linestring_to_track_segment(line, simplify_tolerance)
                            trk.append(trkseg)

                    gpx.append(trk)

                # Write to ZIP
                base_filename = f"{folder}{safe_name}"
                filename = f"{base_filename}.gpx"

                # Ensure unique filename
                if filename in used_filenames:
                    counter = 2
                    while f"{base_filename}_{counter}.gpx" in used_filenames:
                        counter += 1
                    filename = f"{base_filename}_{counter}.gpx"

                used_filenames[filename] = True

                tree = etree.ElementTree(gpx)
                gpx_content = etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding="UTF-8")
                zipf.writestr(filename, gpx_content)

                manifest_lines.append(f"✓ {filename} ({len(segments)} segments merged)")
                stats["total_files"] += 1

        # Add summary to manifest
        manifest_lines.append("")
        manifest_lines.append("=" * 50)
        manifest_lines.append("Summary:")
        manifest_lines.append(f"  Total GPX files: {stats['total_files']}")
        manifest_lines.append(f"  Merged trails: {stats['merged_trails']}")
        manifest_lines.append(f"  Split trails: {stats['split_trails']}")
        manifest_lines.append(f"  Skipped segments: {stats['skipped_segments']}")

        # Write manifest
        zipf.writestr("MANIFEST.txt", "\n".join(manifest_lines))

    stats["file_size_mb"] = float(output_path.stat().st_size) / (1024 * 1024)

    return output_path, stats
