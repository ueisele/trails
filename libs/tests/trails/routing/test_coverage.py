"""Tests for the two things an edge is told by where it lies."""

import geopandas as gpd
import pandas as pd
import pytest
import shapely
from shapely.geometry import LineString
from trails.routing.coverage import MARKED, UNKNOWN, UNMARKED, chain_coverage, no_path_recorded, share_within, waymarked
from trails.routing.sources import BRIDGE, FERRY, PATH

CRS = "EPSG:25833"


def edges(*items: tuple[LineString, str]) -> gpd.GeoDataFrame:
    """Build an edge frame from bare lines.

    Args:
        *items: ``(geometry, kind)`` per edge

    Returns:
        The edges, carrying only what the derivations read
    """
    return gpd.GeoDataFrame({"kind": [kind for _, kind in items]}, geometry=[geometry for geometry, _ in items], crs=CRS)


def walking(*lines: LineString) -> gpd.GeoDataFrame:
    """Build an edge frame of walked edges.

    Args:
        *lines: Geometries

    Returns:
        The edges
    """
    return edges(*((line, PATH) for line in lines))


class TestShareWithin:
    """Test share_within."""

    def test_a_line_on_the_mask_lies_wholly_along_it(self):
        """Test the ordinary case: an edge running on a line the mask holds."""
        share = share_within([LineString([(0, 0), (100, 0)])], [LineString([(0, 0), (100, 0)])], 10.0)
        assert share[0] == pytest.approx(1.0)

    def test_a_line_far_from_the_mask_lies_nowhere_near_it(self):
        """Test that the distance is respected."""
        share = share_within([LineString([(0, 50), (100, 50)])], [LineString([(0, 0), (100, 0)])], 10.0)
        assert share[0] == pytest.approx(0.0)

    def test_a_line_half_along_the_mask_reads_a_half(self):
        """Test the measurement the half-length guard is applied to."""
        share = share_within([LineString([(0, 0), (100, 0)])], [LineString([(0, 0), (50, 0)])], 1.0)
        assert share[0] == pytest.approx(0.5, abs=0.02)

    def test_a_line_merely_crossing_the_mask_counts_only_where_it_is_near(self):
        """Test what the guard exists for: a crossing must not count whole."""
        crossing = LineString([(50, -100), (50, 100)])
        share = share_within([crossing], [LineString([(0, 0), (100, 0)])], 10.0)
        assert share[0] == pytest.approx(0.1, abs=0.01)

    def test_overlapping_mask_lines_are_not_counted_twice(self):
        """Test the failure that merging the overlaps as lines produces.

        Real coordinates and a wobbling track, because a tidy fixture at the
        origin does not have the case at all: there the two ways of measuring
        agree to the last digit, and the test would pass against either. What
        produces the failure is a line with many vertices running in and out of
        buffers that overlap, at the magnitudes a projected CRS actually uses —
        the pieces then no longer dissolve into one another, and their combined
        length runs past the truth. On this network's own data one edge came out
        at 3.6 times its own length that way.
        """
        east, north = 400_000.0, 7_300_000.0
        edge = LineString([(east + step * 2.5, north + (0.4 if step % 2 else -0.4)) for step in range(41)])
        mask = [
            LineString([(east, north + 0.3), (east + 60, north + 0.3)]),
            LineString([(east + 40, north - 0.4), (east + 80, north - 0.4)]),
            LineString([(east + 10, north - 0.2), (east + 55, north + 0.5)]),
            LineString([(east + 20, north + 0.1), (east + 70, north - 0.3)]),
        ]

        assert share_within([edge], mask, 5.0)[0] == pytest.approx(0.85, abs=0.01)

        # And the fixture has to keep being a case: measuring it the wrong way
        # has to come out materially different, or this passes against anything.
        merged = shapely.union_all([shapely.intersection(edge, shapely.buffer(line, 5.0)) for line in mask])
        assert merged.length / edge.length > 0.95

    def test_a_line_lying_along_two_mask_lines_at_once_reads_the_ground_once(self):
        """Test the same guard where the overlap is exact rather than ragged."""
        edge = LineString([(0, 0), (100, 0)])
        mask = [LineString([(0, 0), (60, 0)]), LineString([(40, 0), (80, 0)])]
        assert share_within([edge], mask, 1.0)[0] == pytest.approx(0.8, abs=0.02)

    def test_one_mask_line_repeated_covers_no_more_than_once(self):
        """Test the same failure in its simplest form."""
        edge = LineString([(0, 0), (100, 0)])
        mask = [LineString([(0, 0), (100, 0)])] * 3
        assert share_within([edge], mask, 1.0)[0] == pytest.approx(1.0)

    def test_an_empty_mask_reaches_nothing(self):
        """Test that a mask nothing went into decides nothing."""
        assert share_within([LineString([(0, 0), (100, 0)])], [], 10.0).tolist() == [0.0]

    def test_no_lines_at_all(self):
        """Test with nothing to measure."""
        assert share_within([], [LineString([(0, 0), (100, 0)])], 10.0).tolist() == []

    def test_shares_come_back_in_input_order(self):
        """Test that the result lines up with what was asked about."""
        lines = [LineString([(0, 0), (100, 0)]), LineString([(0, 500), (100, 500)]), LineString([(0, 1), (100, 1)])]
        share = share_within(lines, [LineString([(0, 0), (100, 0)])], 10.0)
        assert share[0] == pytest.approx(1.0)
        assert share[1] == pytest.approx(0.0)
        assert share[2] == pytest.approx(1.0)


class TestWaymarked:
    """Test waymarked."""

    def test_an_edge_along_a_marked_route_is_marked(self):
        """Test the case the whole field exists for."""
        answers = waymarked(walking(LineString([(0, 0), (100, 0)])), [LineString([(0, 2), (100, 2)])], [])
        assert answers.tolist() == [MARKED]

    def test_an_edge_along_an_unmarked_path_is_unmarked(self):
        """Test the source that states the negative."""
        answers = waymarked(walking(LineString([(0, 0), (100, 0)])), [], [LineString([(0, 2), (100, 2)])])
        assert answers.tolist() == [UNMARKED]

    def test_an_edge_along_neither_is_unknown_and_never_unmarked(self):
        """Test the distinction the largest source in a network depends on."""
        answers = waymarked(walking(LineString([(0, 0), (100, 0)])), [LineString([(0, 500), (100, 500)])], [LineString([(0, 900), (100, 900)])])
        assert answers.tolist() == [UNKNOWN]

    def test_marked_wins_where_an_edge_meets_both(self):
        """Test that a parallel unmarked path does not unmark a marked route."""
        edge = walking(LineString([(0, 0), (100, 0)]))
        answers = waymarked(edge, [LineString([(0, 2), (100, 2)])], [LineString([(0, -2), (100, -2)])])
        assert answers.tolist() == [MARKED]

    def test_an_edge_merely_crossing_a_marked_route_is_not_marked(self):
        """Test the half-length guard, which is what keeps the figure honest."""
        edge = walking(LineString([(50, -100), (50, 100)]))
        assert waymarked(edge, [LineString([(0, 0), (100, 0)])], []).tolist() == [UNKNOWN]

    def test_an_edge_mostly_along_a_marked_route_is_marked(self):
        """Test the other side of the guard: most of it is enough."""
        edge = walking(LineString([(0, 0), (100, 0)]))
        assert waymarked(edge, [LineString([(0, 0), (60, 0)])], [], distance_m=1.0).tolist() == [MARKED]

    def test_a_crossing_is_none_of_the_three(self):
        """Test that a ferry is excluded rather than classified."""
        frame = edges((LineString([(0, 0), (100, 0)]), FERRY), (LineString([(0, 0), (100, 0)]), PATH))
        answers = waymarked(frame, [LineString([(0, 2), (100, 2)])], [])
        assert answers.isna().tolist() == [True, False]

    def test_an_inferred_connector_is_none_of_the_three(self):
        """Test that a bridged loose end carries nothing: nobody drew it."""
        frame = edges((LineString([(0, 0), (10, 0)]), BRIDGE))
        assert waymarked(frame, [LineString([(0, 2), (100, 2)])], []).isna().tolist() == [True]

    def test_the_answer_is_aligned_to_the_edges(self):
        """Test that the result can be assigned back onto a frame."""
        frame = walking(LineString([(0, 0), (100, 0)]), LineString([(0, 500), (100, 500)]))
        frame.index = pd.Index([7, 9])
        answers = waymarked(frame, [LineString([(0, 2), (100, 2)])], [])
        assert answers.index.tolist() == [7, 9]
        assert answers.loc[7] == MARKED


class TestOneCrs:
    """Test that a mask in the wrong CRS is refused rather than missed."""

    def test_a_mask_in_another_crs_is_refused(self):
        """Test the failure that would otherwise look like an answer.

        Every distance here is metres. A mask in degrees lies nowhere near
        anything, so every query misses and every edge comes back unknown with
        no path recorded — a report that reads exactly like a park with nothing
        in it.
        """
        frame = walking(LineString([(0, 0), (100, 0)]))
        degrees = gpd.GeoSeries([LineString([(12.0, 65.0), (12.1, 65.0)])], crs="EPSG:4326")
        with pytest.raises(ValueError, match="EPSG:4326"):
            waymarked(frame, degrees, [])
        with pytest.raises(ValueError, match="EPSG:4326"):
            no_path_recorded(frame, degrees)

    def test_a_mask_in_the_same_crs_is_accepted(self):
        """Test that the guard does not stand in the way of the ordinary case."""
        frame = walking(LineString([(0, 0), (100, 0)]))
        mask = gpd.GeoSeries([LineString([(0, 2), (100, 2)])], crs=CRS)
        assert waymarked(frame, mask, []).tolist() == [MARKED]

    def test_bare_geometry_carries_no_crs_and_is_the_caller_s_to_get_right(self):
        """Test that a mask given as plain lines is not refused for lacking one."""
        frame = walking(LineString([(0, 0), (100, 0)]))
        assert waymarked(frame, [LineString([(0, 2), (100, 2)])], []).tolist() == [MARKED]


class TestNoPathRecorded:
    """Test no_path_recorded."""

    def test_an_edge_with_nothing_near_it_has_no_path_recorded(self):
        """Test the only direction this field may be read in."""
        frame = walking(LineString([(0, 0), (100, 0)]))
        assert no_path_recorded(frame, [LineString([(0, 500), (100, 500)])]).tolist() == [True]

    def test_an_edge_along_a_recorded_line_is_not_flagged(self):
        """Test the negative, which asserts nothing about there being a path."""
        frame = walking(LineString([(0, 0), (100, 0)]))
        assert no_path_recorded(frame, [LineString([(0, 5), (100, 5)])]).tolist() == [False]

    def test_an_edge_touching_a_recorded_line_at_one_end_is_still_flagged(self):
        """Test the guard: most of an edge has to be recorded, not a corner of it.

        Without it a long edge that happens to end at a road counts as recorded
        over its whole length, and the figure quietly shrinks to a third.
        """
        frame = walking(LineString([(0, 0), (500, 0)]))
        assert no_path_recorded(frame, [LineString([(0, -10), (0, 10)])]).tolist() == [True]

    def test_a_crossing_is_excluded_rather_than_flagged(self):
        """Test the trap: nothing is recorded across open water, by its nature.

        Left in, every kilometre of ferry would be reported as ground with no
        path recorded, and it would land in a route's walking figures.
        """
        frame = edges((LineString([(0, 0), (5000, 0)]), FERRY))
        assert no_path_recorded(frame, [LineString([(0, 9000), (100, 9000)])]).isna().tolist() == [True]

    def test_an_inferred_connector_is_excluded_too(self):
        """Test that a bridge carries nothing: nobody drew it, which is the point."""
        frame = edges((LineString([(0, 0), (20, 0)]), BRIDGE))
        assert no_path_recorded(frame, [LineString([(0, 9000), (100, 9000)])]).isna().tolist() == [True]

    def test_a_mask_of_nothing_leaves_every_walked_edge_flagged(self):
        """Test that no sources loaded means no evidence, not no answer."""
        frame = walking(LineString([(0, 0), (100, 0)]))
        assert no_path_recorded(frame, []).tolist() == [True]

    def test_the_answer_is_aligned_to_the_edges(self):
        """Test that the result can be assigned back onto a frame."""
        frame = walking(LineString([(0, 0), (100, 0)]), LineString([(0, 500), (100, 500)]))
        frame.index = pd.Index([3, 4])
        answers = no_path_recorded(frame, [LineString([(0, 5), (100, 5)])])
        assert answers.index.tolist() == [3, 4]
        assert bool(answers.loc[4]) is True


def summed(*items: tuple[str | None, str | None, bool | None, float]) -> gpd.GeoDataFrame:
    """Build an edge frame :func:`chain_coverage` can be asked about.

    Args:
        *items: ``(chain_id, waymarked, no_path_recorded, length_m)`` per edge

    Returns:
        The edges, with a placeholder geometry nothing here reads
    """
    return gpd.GeoDataFrame(
        {
            "chain_id": pd.array([chain for chain, _, _, _ in items], dtype="string"),
            "waymarked": pd.array([state for _, state, _, _ in items], dtype="string"),
            "no_path_recorded": pd.array([recorded for _, _, recorded, _ in items], dtype="boolean"),
            "length_m": [length for _, _, _, length in items],
        },
        geometry=[LineString([(0, 0), (1, 0)]) for _ in items],
        crs=CRS,
    )


class TestChainCoverage:
    """Test chain_coverage."""

    def test_a_chain_marked_along_part_of_its_run_says_so_rather_than_picking_one(self):
        """Test the case the whole function exists for: a chain of mixed edges."""
        frame = gpd.GeoDataFrame({"chain_id": pd.array(["a"], dtype="string")}, geometry=[LineString([(0, 0), (1, 0)])], crs=CRS)
        covered = chain_coverage(frame, summed(("a", MARKED, False, 300.0), ("a", UNKNOWN, False, 700.0)))

        assert covered["marked_m"].tolist() == [300.0]
        assert covered["unknown_m"].tolist() == [700.0]
        assert covered["unmarked_m"].tolist() == [0.0]

    def test_nothing_stated_is_never_added_to_unmarked(self):
        """Test that the two are kept apart, which is the point of three classes."""
        frame = gpd.GeoDataFrame({"chain_id": pd.array(["a"], dtype="string")}, geometry=[LineString([(0, 0), (1, 0)])], crs=CRS)
        covered = chain_coverage(frame, summed(("a", UNKNOWN, False, 500.0), ("a", UNMARKED, False, 500.0)))

        assert covered["unknown_m"].tolist() == [500.0]
        assert covered["unmarked_m"].tolist() == [500.0]

    def test_an_edge_on_no_chain_is_dropped_rather_than_gathered(self):
        """Test that a connector, which nobody drew, is evidence about nothing."""
        frame = gpd.GeoDataFrame({"chain_id": pd.array(["a"], dtype="string")}, geometry=[LineString([(0, 0), (1, 0)])], crs=CRS)
        covered = chain_coverage(frame, summed(("a", MARKED, False, 100.0), (None, None, None, 900.0)))

        assert covered["marked_m"].tolist() == [100.0]
        assert covered.to_numpy().sum() == 100.0

    def test_a_chain_of_nothing_but_crossings_comes_back_at_zero(self):
        """Test that neither question having been asked reads as zero, not as NaN."""
        frame = gpd.GeoDataFrame({"chain_id": pd.array(["f"], dtype="string")}, geometry=[LineString([(0, 0), (1, 0)])], crs=CRS)
        covered = chain_coverage(frame, summed(("f", None, None, 20_000.0)))

        assert covered.loc[covered.index[0]].tolist() == [0.0, 0.0, 0.0, 0.0]

    def test_a_chain_with_no_edges_at_all_is_not_an_error(self):
        """Test the empty case, which reindex has to fill rather than drop."""
        frame = gpd.GeoDataFrame({"chain_id": pd.array(["a", "b"], dtype="string")}, geometry=[LineString([(0, 0), (1, 0)])] * 2, crs=CRS)
        covered = chain_coverage(frame, summed(("a", MARKED, False, 100.0)))

        assert len(covered) == 2
        assert covered["marked_m"].tolist() == [100.0, 0.0]

    def test_the_ground_no_source_records_is_summed_apart_from_the_marking(self):
        """Test that an edge can be both marked and unrecorded, and counts in both."""
        frame = gpd.GeoDataFrame({"chain_id": pd.array(["a"], dtype="string")}, geometry=[LineString([(0, 0), (1, 0)])], crs=CRS)
        covered = chain_coverage(frame, summed(("a", MARKED, True, 400.0), ("a", MARKED, False, 600.0)))

        assert covered["marked_m"].tolist() == [1000.0]
        assert covered["no_path_m"].tolist() == [400.0]
