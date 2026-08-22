"""Tests for the GPX writer.

It had none until phase 5's readiness check, which is why two faults lived in it
for as long as it existed: it thinned every export by default against a rule
saying exports carry full source precision, and it reported a point count taken
from the geometry that went in rather than from the file that came out — 305,248
for a file holding 115,655.

What phase 5 then added to it — a height on every point, the sources and their
licences, and what a track says it is — is tested here for the same reason.

**Nothing here tests the browser's copy of the same writer**, and nothing can:
the suite does not run JavaScript, and adding something that did would be a
dependency this project has kept out on purpose. What is testable from Python is
tested from Python — the field names, their order, the rounding rule, and the
coupling that makes two different rounding rules agree — and the two files
themselves are exported on a real chain and compared in a browser whenever the
work is accepted. :mod:`trails.io.export.gpx` says what that comparison found.
"""

from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import geopandas as gpd
import pytest
from lxml import etree
from shapely.geometry import LineString, MultiLineString
from trails.io.export.gpx import (
    EXTENSION_DECIMALS,
    SOURCE_LENGTH_FIELD,
    WAYPOINT_GENERATED,
    WAYPOINT_ORIGIN_FIELD,
    WAYPOINT_SET,
    export_to_gpx,
)

#: A line whose vertices sit far closer together than any simplification
#: tolerance worth applying, so thinning it is visible in a count.
WIGGLE = LineString([(13.0 + i * 1e-6, 65.5 + (i % 2) * 1e-6) for i in range(200)])


#: The GPX 1.1 schema, as a file. **No test may reach the network**: a suite
#: that fetches its own schema fails on a train, and the one it fetched is not
#: the one the last run passed against.
SCHEMA = Path(__file__).resolve().parents[2] / "fixtures" / "trails" / "io" / "export" / "gpx_1_1.xsd"

#: A line whose points carry a height, and one that says nothing.
HEIGHTED = LineString([(13.0, 65.5, 100.0), (13.0001, 65.5001, 104.5), (13.0002, 65.5002, 109.25)])
UNREAD = LineString([(13.1, 65.6, float("nan")), (13.1001, 65.6001, float("nan"))])

#: What a file says it draws on, in the shape both writers of one use.
CREDITS = [
    {"name": "FKB", "licence": "CC BY 4.0", "version": "read 2026-08-10", "attribution": "© Kartverket", "url": "https://example.invalid/fkb"},
    {"name": "OSM", "licence": "ODbL 1.0", "attribution": "© OpenStreetMap contributors"},
]


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


def parsed(path: Path) -> etree._Element:
    """Read a written file back.

    Args:
        path: The file

    Returns:
        Its root element
    """
    return etree.parse(str(path)).getroot()


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


def test_the_file_validates_against_the_gpx_1_1_schema(tmp_path: Path) -> None:
    frame = trails(HEIGHTED)
    frame["chain_id"], frame["source"], frame["ascent"] = ["fkb-1"], ["FKB"], [17.25]
    path, _ = export_to_gpx(
        frame,
        tmp_path / "valid.gpx",
        sources=CREDITS,
        extension_fields={"chain_id": "chain", "source": "source", "ascent": "ascent"},
        ascent_method="DTM1, sampled every 5 m, gains under 5 m ignored",
    )

    schema = etree.XMLSchema(etree.parse(str(SCHEMA)))
    schema.assertValid(etree.parse(str(path)))


def test_a_height_is_written_from_the_geometry_s_own_third_ordinate(tmp_path: Path) -> None:
    path, _ = export_to_gpx(trails(HEIGHTED), tmp_path / "ele.gpx")

    # Two places, not one: the height is what the ascent was computed from,
    # and 109.25 written as 109.2 is a file that no longer reproduces the
    # figure it states.
    assert [point.findtext("{*}ele") for point in written(path)] == ["100.00", "104.50", "109.25"]


def test_a_point_the_model_never_answered_for_is_written_without_a_height(tmp_path: Path) -> None:
    # Not a zero and not the height beside it: nothing downstream can tell an
    # invented height from a read one, and a file is where that stops being
    # recoverable.
    path, _ = export_to_gpx(trails(UNREAD), tmp_path / "unread.gpx")
    points = written(path)

    assert len(points) == 2
    assert [point.find("{*}ele") for point in points] == [None, None]


def test_no_trackpoint_carries_a_time_though_the_file_says_when_it_was_written(tmp_path: Path) -> None:
    # A track carrying timestamps reads as a recorded activity rather than a
    # plan, and the rest would be guesses dressed as data.
    path, _ = export_to_gpx(trails(HEIGHTED), tmp_path / "timeless.gpx")
    root = parsed(path)

    assert not root.findall(".//{*}trkpt/{*}time")
    assert root.findtext("{*}metadata/{*}time", "").endswith("Z")


def test_the_metadata_names_every_source_with_its_licence(tmp_path: Path) -> None:
    path, _ = export_to_gpx(trails(HEIGHTED), tmp_path / "sources.gpx", sources=CREDITS)
    root = parsed(path)
    named = root.findall("{*}metadata/{*}extensions/{*}source")

    assert [entry.get("name") for entry in named] == ["FKB", "OSM"]
    assert [entry.get("licence") for entry in named] == ["CC BY 4.0", "ODbL 1.0"]
    assert named[0].get("version") == "read 2026-08-10"
    # A field with nothing in it is left out rather than written empty: OSM's
    # version is not known here, and an empty string would read as one.
    assert named[1].get("version") is None
    # And in words too, since that is what a person opening the file sees.
    assert "CC BY 4.0" in root.findtext("{*}metadata/{*}desc", "")
    assert "ODbL 1.0" in root.findtext("{*}metadata/{*}desc", "")


def test_no_copyright_is_invented_for_a_file_that_has_no_single_one(tmp_path: Path) -> None:
    # It holds exactly one licence, and a file mixing CC0, CC BY, ODbL and
    # CC BY-NC has no one answer to put there. Listing what is present is both
    # honest and more useful than inventing an answer.
    path, _ = export_to_gpx(trails(HEIGHTED), tmp_path / "uncopyrighted.gpx", sources=CREDITS)

    assert not parsed(path).findall(".//{*}copyright")


def test_a_track_says_which_chain_it_is_and_how_its_ascent_was_reached(tmp_path: Path) -> None:
    # What phase 8 reads to recognise a file as one of this map's own, rather
    # than matching its geometry against the network.
    frame = trails(HEIGHTED)
    frame["chain_id"], frame["source"], frame["ascent"], frame["no_path_m"] = ["fkb-1"], ["FKB"], [17.25], [0.0]
    path, _ = export_to_gpx(
        frame,
        tmp_path / "extended.gpx",
        extension_fields={"chain_id": "chain", "source": "source", "ascent": "ascent", "no_path_m": "unrecorded"},
        ascent_method="DTM1, sampled every 5 m, gains under 5 m ignored",
    )
    block = parsed(path).find("{*}trk/{*}extensions")

    assert [etree.QName(child).localname for child in block] == ["chain", "source", "ascent", "unrecorded", "ascentMethod"]
    assert block.findtext("{*}chain") == "fkb-1"
    # Written to as many places as the page's own figures carry and to exactly
    # that many: '500' in one file against '500.0' in the other would be two
    # writers disagreeing about a number both of them got right. And a zero is
    # written rather than dropped — every metre of this chain is recorded by
    # some source, which is a statement and not a silence.
    assert block.findtext("{*}ascent") == "17.2"
    assert block.findtext("{*}unrecorded") == "0.0"


def test_a_file_with_nothing_to_say_about_a_track_writes_no_extensions(tmp_path: Path) -> None:
    path, _ = export_to_gpx(trails(HEIGHTED), tmp_path / "plain.gpx")

    assert not parsed(path).findall(".//{*}extensions")


def test_the_denser_line_is_written_where_a_caller_holds_one(tmp_path: Path) -> None:
    # The heights were sampled along the edges rather than at the vertices, so
    # the geometry a file is written from is the one the two were laid against
    # each other on — which is not the one the map draws or the router reads.
    frame = trails(LineString([(13.0, 65.5), (13.0002, 65.5002)]))
    frame["track"] = gpd.GeoSeries([HEIGHTED], crs="EPSG:4326")
    path, stats = export_to_gpx(frame, tmp_path / "dense.gpx", track_field="track")

    assert stats["total_points"] == len(written(path)) == 3


def test_a_track_that_breaks_is_written_as_two_segments(tmp_path: Path) -> None:
    # A ferry or a stretch nobody walked breaks the track; a line drawn straight
    # across the step between them is a route nobody can follow.
    apart = MultiLineString([[(13.0, 65.5), (13.001, 65.501)], [(13.1, 65.6), (13.101, 65.601)]])
    path, stats = export_to_gpx(trails(apart), tmp_path / "apart.gpx")
    root = parsed(path)

    assert len(root.findall("{*}trk/{*}trkseg")) == 2
    assert stats["total_points"] == 4


def test_the_sampling_rule_is_stated_only_where_a_height_was_read(tmp_path: Path) -> None:
    # On a crossing it would say how a measurement was taken that was never
    # taken — and the page, which writes it under the same condition, would not.
    frame = trails(HEIGHTED, UNREAD)
    path, _ = export_to_gpx(frame, tmp_path / "method.gpx", ascent_method="DTM1, sampled every 5 m, gains under 5 m ignored")
    tracks = parsed(path).findall("{*}trk")

    assert tracks[0].findtext("{*}extensions/{*}ascentMethod") is not None
    assert tracks[1].find("{*}extensions") is None


def test_a_track_field_naming_no_column_is_refused(tmp_path: Path) -> None:
    # Falling back to the frame's own geometry writes a file of the right size
    # holding no <ele> at all, while <metadata> goes on crediting the height
    # model — plausible, and wrong in the one way nothing downstream could see.
    with pytest.raises(KeyError, match="renamed_away"):
        export_to_gpx(trails(HEIGHTED), tmp_path / "missing.gpx", track_field="renamed_away")


def test_a_figure_is_rounded_the_way_the_page_will_format_it(tmp_path: Path) -> None:
    """The page formats with ``toFixed``, which rounds a half up, where this
    formats with Python, which rounds a half to even. They agree only because
    every figure the page carries has been through ``_figure_values`` first, so
    what ``toFixed`` sees is already on the grid. This is that coupling, held:
    the values below are exact halves, where the two rules would part company if
    the rounding here were ever taken out."""
    for raw in (17.25, 109.25, 0.05, 935.35, 500.0, 2.675):
        # What the page ends up formatting, and how toFixed formats it.
        carried = round(raw, EXTENSION_DECIMALS)
        page = str(Decimal(carried).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
        frame = trails(HEIGHTED)
        frame["ascent"] = [raw]
        path, _ = export_to_gpx(frame, tmp_path / "rounded.gpx", extension_fields={"ascent": "ascent"})

        assert parsed(path).findtext("{*}trk/{*}extensions/{*}ascent") == page


#: Two points of a route, one a reader put down and one the map did.
WAYPOINTS = [
    {"lat": 65.5, "lon": 13.0, "name": "Point 1", WAYPOINT_ORIGIN_FIELD: WAYPOINT_SET},
    {"lat": 65.6, "lon": 13.1, "name": "Enters Lomsdal-Visten", WAYPOINT_ORIGIN_FIELD: WAYPOINT_GENERATED},
]


def test_a_waypoint_is_written_before_the_track_and_not_inside_it(tmp_path: Path) -> None:
    """A waypoint is a GPX 1.1 top-level element and **not** part of the
    extensions mechanism. Written anywhere else the file parses and fails the
    schema, and neither writer could write one at all before this."""
    path, _ = export_to_gpx(trails(HEIGHTED), tmp_path / "wpt.gpx", waypoints=WAYPOINTS)

    children = [etree.QName(child).localname for child in parsed(path)]
    assert children == ["metadata", "wpt", "wpt", "trk"]


def test_a_file_carrying_waypoints_validates_against_the_schema(tmp_path: Path) -> None:
    path, _ = export_to_gpx(trails(HEIGHTED), tmp_path / "wpt-valid.gpx", sources=CREDITS, waypoints=WAYPOINTS)

    schema = etree.XMLSchema(etree.parse(str(SCHEMA)))
    schema.assertValid(etree.parse(str(path)))


def test_every_waypoint_says_whether_it_was_set_or_generated(tmp_path: Path) -> None:
    """Phase 8 must never read a marker the map placed as a station somebody
    chose: a loaded route would gain points nobody put down and start routing
    through them."""
    path, _ = export_to_gpx(trails(HEIGHTED), tmp_path / "origin.gpx", waypoints=WAYPOINTS)

    origins = [element.text for element in parsed(path).findall(f".//{{*}}wpt/{{*}}extensions/{{*}}{WAYPOINT_ORIGIN_FIELD}")]
    assert origins == [WAYPOINT_SET, WAYPOINT_GENERATED]


def test_a_waypoint_carries_no_height_of_its_own(tmp_path: Path) -> None:
    """The track carries every height that was read and the file states the rule
    they were read under. A fourth copy of one of those numbers on the waypoint
    could only ever disagree with them."""
    path, _ = export_to_gpx(trails(HEIGHTED), tmp_path / "wpt-ele.gpx", waypoints=WAYPOINTS)

    assert parsed(path).findall(".//{*}wpt/{*}ele") == []


def test_a_waypoint_with_no_position_is_refused(tmp_path: Path) -> None:
    """Writing one at 0/0 would put it in the Gulf of Guinea."""
    with pytest.raises(KeyError):
        export_to_gpx(trails(HEIGHTED), tmp_path / "nowhere.gpx", waypoints=[{"name": "nowhere"}])


def test_a_chain_export_writes_no_waypoints(tmp_path: Path) -> None:
    """A waypoint is a place somebody chose, and nobody chose anything about a
    line read out of a register."""
    path, _ = export_to_gpx(trails(HEIGHTED), tmp_path / "none.gpx")

    assert parsed(path).findall(".//{*}wpt") == []


def test_a_source_states_its_length_only_where_one_was_worked_out(tmp_path: Path) -> None:
    """A chain has one source and the length is the track's; a planned route
    runs over several and states each, so *3.20 km OSM (ODbL)* is readable
    before the file is passed on."""
    measured = [dict(CREDITS[0], **{SOURCE_LENGTH_FIELD: "3200.0"}), CREDITS[1]]
    path, _ = export_to_gpx(trails(HEIGHTED), tmp_path / "lengths.gpx", sources=measured)

    written_sources = parsed(path).findall(".//{*}metadata/{*}extensions/{*}source")
    assert [element.get(SOURCE_LENGTH_FIELD) for element in written_sources] == ["3200.0", None]


def test_the_description_records_a_source_the_way_the_extensions_do(tmp_path: Path) -> None:
    """``<metadata>`` records its sources twice, once for a person and once for
    a program. A field carried in one and left out of the other is two
    recordings of one thing that disagree — and the page writes the phrase with
    the length in it."""
    measured = [dict(CREDITS[0], **{SOURCE_LENGTH_FIELD: "3200.0"}), CREDITS[1]]
    path, _ = export_to_gpx(trails(HEIGHTED), tmp_path / "desc.gpx", sources=measured)

    described = parsed(path).find(".//{*}metadata/{*}desc").text
    assert "3.20 km FKB (CC BY 4.0" in described
    assert "3.20 km OSM" not in described
