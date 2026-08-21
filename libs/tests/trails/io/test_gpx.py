"""Tests for the GPX writer.

It had none until phase 5's readiness check, which is why two faults lived in it
for as long as it existed: it thinned every export by default against a rule
saying exports carry full source precision, and it reported a point count taken
from the geometry that went in rather than from the file that came out — 305,248
for a file holding 115,655.
"""

from pathlib import Path

import geopandas as gpd
import pytest
from lxml import etree
from shapely.geometry import LineString, MultiLineString
from trails.io.export.gpx import export_to_gpx

#: A line whose vertices sit far closer together than any simplification
#: tolerance worth applying, so thinning it is visible in a count.
WIGGLE = LineString([(13.0 + i * 1e-6, 65.5 + (i % 2) * 1e-6) for i in range(200)])


def trails(*geometries: LineString | MultiLineString) -> gpd.GeoDataFrame:
    """Build a trail frame from bare geometries.

    Args:
        *geometries: The lines to export

    Returns:
        A frame carrying a name for each
    """
    return gpd.GeoDataFrame(
        {"trail_name": [f"line {index}" for index in range(len(geometries))]},
        geometry=list(geometries),
        crs="EPSG:4326",
    )


def written(path: Path) -> list[etree._Element]:
    """Read the trackpoints back out of a written file.

    Args:
        path: The file

    Returns:
        Every ``trkpt`` element in it
    """
    return etree.parse(str(path)).getroot().findall(".//{*}trkpt")


def test_every_vertex_is_written_unless_thinning_is_asked_for(tmp_path: Path) -> None:
    # The one thing that leaves this machine carries the resolution its source
    # recorded. The old default of 1e-5 degrees is under the survey accuracy of
    # the best source here and still dropped 62 % of FKB's vertices.
    path, _ = export_to_gpx(trails(WIGGLE), tmp_path / "dense.gpx")

    assert len(written(path)) == len(WIGGLE.coords)


def test_thinning_still_happens_when_a_caller_asks(tmp_path: Path) -> None:
    path, _ = export_to_gpx(trails(WIGGLE), tmp_path / "thin.gpx", simplify_tolerance=1e-5)

    assert len(written(path)) < len(WIGGLE.coords)


def test_the_point_count_is_what_the_file_holds(tmp_path: Path) -> None:
    # Counting the input instead reports what the file would have held if
    # nothing thinned it, which is a figure a reader is meant to trust.
    path, stats = export_to_gpx(trails(WIGGLE), tmp_path / "counted.gpx", simplify_tolerance=1e-5)

    assert stats["total_points"] == len(written(path))
    assert stats["total_points"] < len(WIGGLE.coords)


def test_the_point_count_covers_every_part_of_a_multipart_line(tmp_path: Path) -> None:
    parts = MultiLineString([[(13.0, 65.5), (13.001, 65.501)], [(13.01, 65.51), (13.011, 65.511), (13.012, 65.512)]])
    path, stats = export_to_gpx(trails(parts), tmp_path / "parts.gpx")

    assert stats["total_points"] == len(written(path)) == 5


def test_the_size_is_reported_in_the_megabytes_it_is_labelled_with(tmp_path: Path) -> None:
    # Dividing by 1024**2 and calling the answer MB reported 7.72 for a file of
    # 8.09 million bytes.
    path, stats = export_to_gpx(trails(WIGGLE), tmp_path / "sized.gpx")

    assert stats["file_size_mb"] == pytest.approx(path.stat().st_size / 1e6)


def test_an_empty_geometry_is_skipped_rather_than_written(tmp_path: Path) -> None:
    frame = trails(WIGGLE, LineString())
    path, stats = export_to_gpx(frame, tmp_path / "skipped.gpx")

    assert stats["skipped_trails"] == 1
    assert stats["total_points"] == len(written(path)) == len(WIGGLE.coords)
