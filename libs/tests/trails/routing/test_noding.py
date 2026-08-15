"""Tests for cutting lines where they meet."""

import geopandas as gpd
import pytest
from shapely.geometry import LineString, MultiLineString, Point, Polygon, box
from trails.routing.noding import clip_lines, cut_line, cut_positions, intersection_points, project_onto, working_lines

CRS = "EPSG:25833"


def frame(*lines: LineString, crs: str = CRS) -> gpd.GeoDataFrame:
    """Build a GeoDataFrame from bare lines.

    Args:
        *lines: Geometries to wrap
        crs: CRS to declare

    Returns:
        One row per line
    """
    return gpd.GeoDataFrame({"tag": [f"line{position}" for position in range(len(lines))]}, geometry=list(lines), crs=crs)


class TestClipLines:
    """Test clip_lines."""

    def test_line_outside_the_extent_is_dropped(self):
        """Test that what lies beyond the mask does not survive."""
        clipped = clip_lines(frame(LineString([(500, 500), (600, 600)])), box(0, 0, 100, 100))
        assert clipped.empty

    def test_line_crossing_the_boundary_is_cut(self):
        """Test that only the part inside the extent is kept."""
        clipped = clip_lines(frame(LineString([(50, 50), (250, 50)])), box(0, 0, 100, 100))
        assert clipped.geometry.length.sum() == pytest.approx(50.0)

    def test_a_track_doubling_back_on_itself_is_left_alone(self):
        """Test the regression that started this: an overlay nodes what it touches.

        Clipping a GPS track that walks out and back along the same ground used
        to shatter it into hundreds of pieces and lose a kilometre of it, even
        where the whole track lay well inside the extent.
        """
        track = LineString([(10, 10), (60, 10), (90, 10), (60, 10), (60, 60)])
        clipped = clip_lines(frame(track), box(0, 0, 100, 100))

        assert len(clipped) == 1
        assert clipped.geometry.iloc[0].equals(track)
        assert clipped.geometry.length.sum() == pytest.approx(track.length)

    def test_attributes_survive_the_cut(self):
        """Test that clipping keeps the columns it was given."""
        clipped = clip_lines(frame(LineString([(50, 50), (250, 50)])), box(0, 0, 100, 100))
        assert clipped["tag"].tolist() == ["line0"]


class TestWorkingLines:
    """Test working_lines."""

    def test_projects_into_the_working_crs(self):
        """Test that a source in degrees comes back in metres."""
        lines = gpd.GeoDataFrame(geometry=[LineString([(12.0, 65.0), (12.01, 65.0)])], crs="EPSG:4326")
        prepared = working_lines(lines, None, CRS)
        assert prepared.crs.to_string() == CRS
        assert prepared.geometry.length.iloc[0] > 100

    def test_multipart_geometry_is_exploded(self):
        """Test that each part becomes a row of its own."""
        lines = gpd.GeoDataFrame(geometry=[MultiLineString([[(0, 0), (1, 0)], [(5, 0), (6, 0)]])], crs=CRS)
        assert len(working_lines(lines, None, CRS)) == 2

    def test_empty_and_degenerate_geometries_are_dropped(self):
        """Test that a line with no length is not carried along."""
        lines = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (10, 0)]), LineString([(4, 4), (4, 4)])], crs=CRS)
        assert len(working_lines(lines, None, CRS)) == 1

    def test_clip_is_read_in_the_source_crs(self):
        """Test that a bare mask geometry is taken to be in the source's CRS."""
        lines = gpd.GeoDataFrame(geometry=[LineString([(12.0, 65.0), (12.1, 65.0)])], crs="EPSG:4326")
        mask = Polygon([(11.9, 64.9), (12.05, 64.9), (12.05, 65.1), (11.9, 65.1)])
        assert len(working_lines(lines, mask, CRS)) == 1


class TestIntersectionPoints:
    """Test intersection_points."""

    def test_two_lines_crossing(self):
        """Test that both lines learn where they were crossed."""
        found = intersection_points(frame(LineString([(0, 0), (100, 0)]), LineString([(50, -50), (50, 50)])).geometry)
        assert [point.coords[0] for point in found[0]] == [(50.0, 0.0)]
        assert [point.coords[0] for point in found[1]] == [(50.0, 0.0)]

    def test_lines_that_never_meet(self):
        """Test that nothing is invented."""
        found = intersection_points(frame(LineString([(0, 0), (10, 0)]), LineString([(0, 50), (10, 50)])).geometry)
        assert found == [[], []]

    def test_lines_running_along_each_other_are_cut_where_that_starts_and_ends(self):
        """Test that a shared stretch is bounded rather than ignored."""
        found = intersection_points(frame(LineString([(0, 0), (100, 0)]), LineString([(30, 0), (70, 0)])).geometry)
        assert {point.coords[0] for point in found[0]} == {(30.0, 0.0), (70.0, 0.0)}

    def test_a_line_crossing_itself_is_noticed(self):
        """Test that a junction no pair can see is still found."""
        found = intersection_points(frame(LineString([(0, 0), (100, 0), (100, 100), (50, 100), (50, -50)])).geometry)
        assert (50.0, 0.0) in {point.coords[0] for point in found[0]}

    def test_empty_input(self):
        """Test with nothing to node."""
        assert intersection_points(gpd.GeoSeries([], crs=CRS)) == []


class TestCutPositions:
    """Test cut_positions."""

    def test_always_spans_the_whole_line(self):
        """Test that the ends are cut positions by construction."""
        line = LineString([(0, 0), (100, 0)])
        assert cut_positions(line, []) == [0.0, 100.0]

    def test_positions_are_measured_along_the_line(self):
        """Test that a point becomes its distance."""
        line = LineString([(0, 0), (100, 0)])
        assert cut_positions(line, [Point(30, 0)]) == [0.0, 30.0, 100.0]

    def test_positions_at_the_ends_are_not_repeated(self):
        """Test that a cut on an endpoint does not make a zero-length piece."""
        line = LineString([(0, 0), (100, 0)])
        assert cut_positions(line, [Point(0, 0), Point(100, 0)]) == [0.0, 100.0]

    def test_positions_closer_than_the_tolerance_collapse(self):
        """Test that two cuts a millimetre apart are one cut."""
        line = LineString([(0, 0), (100, 0)])
        assert cut_positions(line, [Point(30, 0), Point(30.001, 0)]) == [0.0, 30.0, 100.0]

    def test_positions_come_back_in_order(self):
        """Test that the pieces run along the line rather than jumping about."""
        line = LineString([(0, 0), (100, 0)])
        assert cut_positions(line, [Point(70, 0), Point(30, 0)]) == [0.0, 30.0, 70.0, 100.0]


class TestCutLine:
    """Test cut_line."""

    def test_pieces_line_up_with_the_positions(self):
        """Test that there is one piece per pair of positions."""
        pieces = cut_line(LineString([(0, 0), (100, 0)]), [0.0, 30.0, 100.0])
        assert [piece.length for piece in pieces] == [30.0, 70.0]

    def test_pieces_add_up_to_the_line(self):
        """Test that cutting loses nothing."""
        line = LineString([(0, 0), (50, 50), (100, 0)])
        pieces = cut_line(line, [0.0, 20.0, 90.0, line.length])
        assert sum(piece.length for piece in pieces) == pytest.approx(line.length)

    def test_a_cut_that_leaves_nothing_is_reported_as_nothing(self):
        """Test that the caller can tell an empty piece from a real one."""
        assert cut_line(LineString([(0, 0), (100, 0)]), [0.0, 50.0, 50.0, 100.0])[1] is None


class TestProjectOnto:
    """Test project_onto."""

    def test_measures_positions_along_the_line(self):
        """Test the plain case, where the copies agree."""
        line = LineString([(0, 0), (100, 0)])
        assert project_onto(line, [Point(0, 0), Point(40, 0), Point(100, 0)]) == [0.0, 40.0, 100.0]

    def test_result_never_runs_backwards(self):
        """Test that a projection landing behind the one before it is pulled up.

        The simplified copy a position was found on wanders either side of the
        real line, so this happens, and a piece running backwards is a piece
        with a negative length.
        """
        line = LineString([(0, 0), (100, 0)])
        assert project_onto(line, [Point(0, 0), Point(60, 0), Point(55, 0), Point(100, 0)]) == [0.0, 60.0, 60.0, 100.0]

    def test_ends_are_pinned_to_the_line(self):
        """Test that the first and last positions cover the whole line."""
        line = LineString([(0, 0), (100, 0)])
        assert project_onto(line, [Point(2, 0), Point(50, 0), Point(98, 0)]) == [0.0, 50.0, 100.0]
