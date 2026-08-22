"""Tests for what an edge is told by which protected areas it lies in."""

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Polygon
from trails.routing.protection import DEFAULT_TOUCHED_M, protected_metres, protected_within, touched
from trails.routing.sources import BRIDGE, FERRY, PATH

CRS = "EPSG:25833"
OTHER_CRS = "EPSG:4326"


def edges(*items: tuple[LineString, str]) -> gpd.GeoDataFrame:
    """Build an edge frame from bare lines.

    Args:
        *items: ``(geometry, kind)`` per edge

    Returns:
        The edges, carrying only what the derivation reads
    """
    return gpd.GeoDataFrame({"kind": [kind for _, kind in items]}, geometry=[geometry for geometry, _ in items], crs=CRS)


def areas(*items: tuple[str, Polygon], crs: str = CRS) -> gpd.GeoDataFrame:
    """Build an area frame from bare polygons.

    Args:
        *items: ``(id, geometry)`` per area
        crs: What they are in

    Returns:
        The areas
    """
    return gpd.GeoDataFrame({"vid": [name for name, _ in items]}, geometry=[geometry for _, geometry in items], crs=crs)


def box(west: float, south: float, east: float, north: float) -> Polygon:
    """Build a rectangle.

    Args:
        west: Left edge
        south: Bottom edge
        east: Right edge
        north: Top edge

    Returns:
        The rectangle
    """
    return Polygon([(west, south), (east, south), (east, north), (west, north)])


class TestProtectedWithin:
    """Test protected_within."""

    def test_an_edge_wholly_inside_carries_its_whole_length(self):
        """Test the ordinary case."""
        found = protected_within(edges((LineString([(10, 10), (90, 10)]), PATH)), areas(("A", box(0, 0, 100, 100))), id_field="vid")
        assert found[0] == (("A", pytest.approx(80.0)),)

    def test_an_edge_wholly_outside_carries_an_empty_answer(self):
        """Test that lying in nothing is an answer and not a gap."""
        found = protected_within(edges((LineString([(200, 10), (300, 10)]), PATH)), areas(("A", box(0, 0, 100, 100))), id_field="vid")
        assert found[0] == ()

    def test_an_edge_crossing_the_boundary_carries_only_the_part_inside(self):
        """Test that this is a length and not a share or a flag."""
        found = protected_within(edges((LineString([(50, 10), (150, 10)]), PATH)), areas(("A", box(0, 0, 100, 100))), id_field="vid")
        assert found[0] == (("A", pytest.approx(50.0)),)

    def test_an_edge_in_two_areas_names_both(self):
        """Test that overlapping areas are not collapsed to one."""
        found = protected_within(
            edges((LineString([(10, 10), (90, 10)]), PATH)),
            areas(("A", box(0, 0, 100, 100)), ("B", box(0, 0, 50, 100))),
            id_field="vid",
        )
        assert dict(found[0]) == {"A": pytest.approx(80.0), "B": pytest.approx(40.0)}

    def test_an_edge_touching_a_boundary_at_one_point_carries_nothing_for_it(self):
        """Test that a touch is not a passage.

        ``intersects`` is true where an edge meets a boundary at a single point,
        and a point is zero metres of ground. Written down it would put every
        area a route merely reaches into the route's own figure, with a pair of
        waypoints for each.
        """
        found = protected_within(edges((LineString([(50, 100), (50, 200)]), PATH)), areas(("A", box(0, 0, 100, 100))), id_field="vid")
        assert found[0] == ()

    def test_an_edge_running_along_a_boundary_is_inside(self):
        """Test that the boundary belongs to the area it bounds.

        Three of the areas here share a boundary with the national park, so a
        path laid exactly along one is inside both — which is what the register
        says and what a walker standing on it is.
        """
        found = protected_within(edges((LineString([(0, 100), (100, 100)]), PATH)), areas(("A", box(0, 0, 100, 100))), id_field="vid")
        assert found[0] == (("A", pytest.approx(100.0)),)

    def test_a_crossing_is_never_asked(self):
        """Test the distinction the column exists to keep."""
        found = protected_within(
            edges((LineString([(10, 10), (90, 10)]), FERRY), (LineString([(10, 20), (90, 20)]), PATH)),
            areas(("A", box(0, 0, 100, 100))),
            id_field="vid",
        )
        assert found[0] is None
        assert found[1] == (("A", pytest.approx(80.0)),)

    def test_a_connector_is_asked(self):
        """Test that ground nobody drew is still ground inside a boundary."""
        found = protected_within(edges((LineString([(10, 10), (90, 10)]), BRIDGE)), areas(("A", box(0, 0, 100, 100))), id_field="vid")
        assert found[0] == (("A", pytest.approx(80.0)),)

    def test_areas_in_another_crs_are_refused(self):
        """Test the mistake that would answer 'nothing anywhere' and look right."""
        with pytest.raises(ValueError, match="EPSG:4326"):
            protected_within(edges((LineString([(10, 10), (90, 10)]), PATH)), areas(("A", box(0, 0, 1, 1)), crs=OTHER_CRS), id_field="vid")

    def test_two_areas_with_one_id_are_refused(self):
        """Test that an id is what an edge names, so it has to name one area."""
        with pytest.raises(ValueError, match="more than once"):
            protected_within(
                edges((LineString([(10, 10), (90, 10)]), PATH)),
                areas(("A", box(0, 0, 100, 100)), ("A", box(0, 0, 50, 100))),
                id_field="vid",
            )

    def test_no_areas_leaves_every_walked_edge_answering_nothing(self):
        """Test that an empty register is not a missing answer."""
        found = protected_within(edges((LineString([(10, 10), (90, 10)]), PATH), (LineString([(0, 0), (1, 1)]), FERRY)), areas(), id_field="vid")
        assert list(found) == [(), None]

    def test_the_answer_is_aligned_to_the_edges(self):
        """Test that a frame with its own index is not read by position."""
        frame = edges((LineString([(10, 10), (90, 10)]), PATH), (LineString([(200, 10), (300, 10)]), PATH))
        frame.index = [7, 3]
        found = protected_within(frame, areas(("A", box(0, 0, 100, 100))), id_field="vid")
        assert list(found.index) == [7, 3]
        assert found[7] == (("A", pytest.approx(80.0)),)
        assert found[3] == ()


class TestProtectedMetres:
    """Test protected_metres."""

    def test_it_adds_each_area_up_across_the_edges(self):
        """Test the sum the report is made of."""
        assert protected_metres([(("A", 10.0),), (("A", 5.0), ("B", 2.0)), None, ()]) == {"A": 15.0, "B": 2.0}

    def test_it_lists_the_largest_first(self):
        """Test the order the report reads in."""
        assert list(protected_metres([(("A", 1.0), ("B", 9.0))])) == ["B", "A"]

    def test_an_area_nothing_touches_is_absent_rather_than_zero(self):
        """Test that this answers about the ground and is not a census."""
        assert protected_metres([()]) == {}


class TestTouched:
    """Test touched."""

    def test_it_drops_what_is_under_the_threshold(self):
        """Test the decision this phase makes."""
        assert touched({"A": 1000.0, "B": 5.0}, 100.0) == {"A": 1000.0}

    def test_the_threshold_is_inclusive(self):
        """Test that exactly the threshold counts, so the boundary is one place."""
        assert touched({"A": 100.0}, 100.0) == {"A": 100.0}

    def test_it_defaults_to_the_measured_threshold(self):
        """Test that a caller need not spell the figure to get the same answer."""
        assert touched({"A": DEFAULT_TOUCHED_M, "B": DEFAULT_TOUCHED_M - 1}) == {"A": DEFAULT_TOUCHED_M}
