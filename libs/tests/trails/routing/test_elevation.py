"""Tests for the heights along the network and the figures read off them."""

import math

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import LineString
from trails.routing.elevation import (
    PROFILE_COLUMNS,
    ascent,
    chain_profiles,
    chain_series,
    descent,
    profile_of,
    sample_along,
    sample_count,
    with_elevation,
)
from trails.routing.graph import Network
from trails.routing.sources import BRIDGE, FERRY, PATH

CRS = "EPSG:25833"


def edges(*items: tuple[LineString, str, object, int, int]) -> gpd.GeoDataFrame:
    """Build an edge frame from bare parts.

    Args:
        *items: ``(geometry, kind, chain_id, from_node, to_node)`` per edge

    Returns:
        The edges, carrying what the elevation work reads
    """
    return gpd.GeoDataFrame(
        {
            "kind": [kind for _, kind, _, _, _ in items],
            "chain_id": [chain for _, _, chain, _, _ in items],
            "from_node": [one for _, _, _, one, _ in items],
            "to_node": [other for _, _, _, _, other in items],
        },
        geometry=[geometry for geometry, _, _, _, _ in items],
        crs=CRS,
    )


def chains(*items: tuple[LineString, str]) -> gpd.GeoDataFrame:
    """Build a chain frame from bare parts.

    Args:
        *items: ``(geometry, chain_id)`` per chain

    Returns:
        The chains
    """
    return gpd.GeoDataFrame({"chain_id": [chain for _, chain in items]}, geometry=[geometry for geometry, _ in items], crs=CRS)


def ground(profile: dict[tuple[float, float], float]) -> object:
    """Answer heights from a lookup table, as the endpoint would.

    Args:
        profile: Height per coordinate, rounded to the metre

    Returns:
        A callable for :func:`with_elevation`, answering NaN off the table
    """

    def read(coordinates: np.ndarray) -> np.ndarray:
        return np.array([profile.get((round(east), round(north)), math.nan) for east, north in coordinates], dtype=float)

    return read


class TestSampleCount:
    """Test how many samples a line is given."""

    def test_a_long_line_is_sampled_at_the_step(self):
        """Test the ordinary case."""
        assert sample_count(100.0, 5.0) == 21

    def test_a_line_shorter_than_the_step_still_gets_both_ends(self):
        """Test the floor of two: 28,373 edges in this network are under a metre."""
        assert sample_count(0.4, 5.0) == 2

    def test_a_line_of_no_length_still_gets_two(self):
        """Test that nothing produces a line with no samples at all."""
        assert sample_count(0.0, 5.0) == 2

    def test_a_line_of_exactly_one_step_gets_both_ends_and_nothing_between(self):
        """Test the boundary, where a spurious extra sample is easy to add."""
        assert sample_count(5.0, 5.0) == 2

    def test_a_step_of_nothing_is_refused(self):
        """Test that a zero step is an error rather than an infinite series."""
        with pytest.raises(ValueError, match="positive"):
            sample_count(10.0, 0.0)


class TestSampleAlong:
    """Test where the samples fall."""

    def test_both_ends_are_sampled(self):
        """Test the property the chain series is laid out on."""
        coordinates, counts = sample_along([LineString([(0, 0), (12, 0)])], 5.0)
        assert counts.tolist() == [3]
        assert coordinates[0].tolist() == [0.0, 0.0]
        assert coordinates[-1].tolist() == [12.0, 0.0]

    def test_the_samples_are_spread_evenly(self):
        """Test that the spacing is uniform rather than laid from one end."""
        coordinates, _ = sample_along([LineString([(0, 0), (12, 0)])], 5.0)
        assert coordinates[1].tolist() == [6.0, 0.0]

    def test_two_edges_meeting_sample_the_same_point_twice(self):
        """Test what the point store's 28 % of duplicates is made of."""
        coordinates, _ = sample_along([LineString([(0, 0), (10, 0)]), LineString([(10, 0), (20, 0)])], 5.0)
        meeting = [tuple(point) for point in coordinates.tolist()].count((10.0, 0.0))
        assert meeting == 2

    def test_nothing_to_sample_is_not_an_error(self):
        """Test the empty case, which a network without a walked edge produces."""
        coordinates, counts = sample_along([], 5.0)
        assert coordinates.shape == (0, 2)
        assert counts.tolist() == []

    def test_a_line_holding_no_coordinates_is_refused(self):
        """Test the one way the counts and the coordinates could disagree.

        Interpolating along an empty line gives an empty point, which is then
        dropped rather than returned — so every line after it would silently be
        given its neighbour's heights.
        """
        with pytest.raises(ValueError, match="no coordinates"):
            sample_along([LineString(), LineString([(0, 0), (10, 0)])], 5.0)


class TestAscent:
    """Test the reported climb."""

    def test_a_steady_climb_is_its_whole_gain(self):
        """Test the ordinary case."""
        assert ascent([0.0, 20.0, 40.0, 60.0], 5.0) == pytest.approx(60.0)

    def test_a_climb_and_a_descent_count_only_the_climb(self):
        """Test that descent is not ascent."""
        assert ascent([0.0, 60.0, 0.0], 5.0) == pytest.approx(60.0)

    def test_two_climbs_are_added(self):
        """Test that the run restarts after a real descent."""
        assert ascent([0.0, 60.0, 0.0, 60.0], 5.0) == pytest.approx(120.0)

    def test_noise_under_the_threshold_is_not_climb(self):
        """Test what the threshold is for: a shallow dip is not a re-climb."""
        assert ascent([0.0, 50.0, 46.0, 100.0], 5.0) == pytest.approx(100.0)

    def test_a_dip_over_the_threshold_is_climbed_back(self):
        """Test that a real dip is counted, unlike the noise above."""
        assert ascent([0.0, 50.0, 40.0, 100.0], 5.0) == pytest.approx(110.0)

    def test_a_series_that_starts_downhill_climbs_nothing(self):
        """Test the first step, where the direction is not yet known."""
        assert ascent([100.0, 90.0, 80.0], 5.0) == pytest.approx(0.0)

    def test_wobble_around_one_height_climbs_nothing(self):
        """Test the coastline effect the threshold exists to suppress."""
        wobble = [0.0, 2.0, -2.0, 2.0, -2.0, 2.0, -2.0, 0.0]
        assert ascent(wobble, 5.0) == pytest.approx(0.0)
        assert ascent(wobble, 0.0) == pytest.approx(12.0)

    def test_a_rise_smaller_than_the_threshold_is_not_a_climb(self):
        """Test the case that keeps the two ascent figures apart.

        Most edges here are shorter than the threshold is tall, so most of them
        report nothing at all — which is why their figures cannot be summed.
        """
        assert ascent([100.0, 103.0], 5.0) == pytest.approx(0.0)

    def test_the_figure_holds_as_the_sampling_coarsens(self):
        """Test the invariance the whole threshold is there for.

        A climb of 300 m with a metre of noise on every sample: sampled twice as
        finely, twice as much noise counts as climbing, and only the threshold
        makes the two agree.
        """
        fine = [index * 0.5 + (1.0 if index % 2 else -1.0) for index in range(601)]
        coarse = fine[::2]
        assert ascent(fine, 0.0) > ascent(coarse, 0.0) + 100
        assert ascent(fine, 5.0) == pytest.approx(ascent(coarse, 5.0), abs=2.0)

    def test_a_gap_breaks_the_run_rather_than_being_stepped_over(self):
        """Test that nothing is claimed about ground nothing was read along."""
        assert ascent([0.0, 10.0, math.nan, 500.0, 510.0], 5.0) == pytest.approx(20.0)

    def test_a_series_of_nothing_but_gaps_says_nothing(self):
        """Test that unread ground reads as unknown rather than as flat."""
        assert math.isnan(ascent([math.nan, math.nan], 5.0))

    def test_a_crossing_carries_no_samples_and_no_figure(self):
        """Test the ferry case, which arrives here as an empty series."""
        assert math.isnan(ascent([], 5.0))


class TestDescentAndExtremes:
    """Test the three figures stored beside the ascent."""

    def test_a_steady_fall_is_its_whole_loss(self):
        """Test the ordinary case."""
        assert descent([60.0, 40.0, 20.0, 0.0], 5.0) == pytest.approx(60.0)

    def test_a_climb_is_not_a_descent(self):
        """Test that the two do not double-count each other."""
        assert descent([0.0, 60.0], 5.0) == pytest.approx(0.0)

    def test_noise_under_the_threshold_is_not_a_descent_either(self):
        """Test that the threshold is read the same way in both directions."""
        assert descent([100.0, 50.0, 54.0, 0.0], 5.0) == pytest.approx(100.0)

    def test_a_series_read_backwards_swaps_the_two(self):
        """Test the reason descent is stored rather than left to be derived.

        A chain is oriented so that its id stays stable, not because a walker is
        obliged to take it that way, so an ascent alone is true in one direction
        and silent about the other.
        """
        climb = [0.0, 100.0, 60.0, 200.0]
        assert ascent(climb, 5.0) == pytest.approx(descent(climb[::-1], 5.0))
        assert descent(climb, 5.0) == pytest.approx(ascent(climb[::-1], 5.0))

    def test_the_high_and_low_point_are_the_readings_themselves(self):
        """Test that no threshold is applied to them: a summit is where it is."""
        read = profile_of([100.0, 903.3, 1.4, 400.0], 5.0)
        assert read["high_m"] == pytest.approx(903.3)
        assert read["low_m"] == pytest.approx(1.4)

    def test_a_gap_is_not_a_low_point(self):
        """Test that unread ground is not read as sea level."""
        read = profile_of([100.0, math.nan, 400.0], 5.0)
        assert read["low_m"] == pytest.approx(100.0)
        assert read["high_m"] == pytest.approx(400.0)

    def test_a_series_of_nothing_says_nothing_four_times(self):
        """Test the ferry case: unknown rather than flat and at sea level."""
        read = profile_of([], 5.0)
        assert all(math.isnan(value) for value in read.values())


class TestChainSeries:
    """Test laying a chain's edges end to end."""

    def test_edges_are_laid_out_in_order(self):
        """Test the ordinary case: three edges in a row."""
        frame = edges(
            (LineString([(10, 0), (20, 0)]), PATH, "c", 1, 2),
            (LineString([(0, 0), (10, 0)]), PATH, "c", 0, 1),
            (LineString([(20, 0), (30, 0)]), PATH, "c", 2, 3),
        )
        frame["elevations"] = [np.array([10.0, 20.0]), np.array([0.0, 10.0]), np.array([20.0, 30.0])]
        assert chain_series(frame, LineString([(0, 0), (30, 0)])).tolist() == [0.0, 10.0, 20.0, 30.0]

    def test_a_node_between_two_edges_is_counted_once(self):
        """Test that the sample both edges take at their shared end is not doubled."""
        frame = edges((LineString([(0, 0), (10, 0)]), PATH, "c", 0, 1), (LineString([(10, 0), (20, 0)]), PATH, "c", 1, 2))
        frame["elevations"] = [np.array([0.0, 5.0]), np.array([5.0, 9.0])]
        assert chain_series(frame, LineString([(0, 0), (20, 0)])).tolist() == [0.0, 5.0, 9.0]

    def test_an_edge_drawn_against_the_chain_is_turned_round(self):
        """Test an edge whose own direction runs the other way."""
        frame = edges((LineString([(0, 0), (10, 0)]), PATH, "c", 0, 1), (LineString([(20, 0), (10, 0)]), PATH, "c", 2, 1))
        frame["elevations"] = [np.array([0.0, 5.0]), np.array([9.0, 5.0])]
        assert chain_series(frame, LineString([(0, 0), (20, 0)])).tolist() == [0.0, 5.0, 9.0]

    def test_the_series_follows_the_chain_rather_than_the_walk(self):
        """Test the orientation, which decides whether a climb is a climb.

        Read backwards a chain reports its descent as its ascent, and the walk
        starts at whichever end it happens to reach first.
        """
        frame = edges((LineString([(0, 0), (10, 0)]), PATH, "c", 0, 1), (LineString([(10, 0), (20, 0)]), PATH, "c", 1, 2))
        frame["elevations"] = [np.array([0.0, 50.0]), np.array([50.0, 90.0])]
        uphill = chain_series(frame, LineString([(0, 0), (20, 0)]))
        downhill = chain_series(frame, LineString([(20, 0), (0, 0)]))
        assert ascent(uphill, 5.0) == pytest.approx(90.0)
        assert ascent(downhill, 5.0) == pytest.approx(0.0)

    def test_stretches_that_do_not_join_are_kept_apart(self):
        """Test that no climb is invented across a break in the walk."""
        frame = edges((LineString([(0, 0), (10, 0)]), PATH, "c", 0, 1), (LineString([(100, 0), (110, 0)]), PATH, "c", 7, 8))
        frame["elevations"] = [np.array([0.0, 5.0]), np.array([500.0, 505.0])]
        laid = chain_series(frame, LineString([(0, 0), (110, 0)]))
        assert math.isnan(laid[2])
        assert ascent(laid, 1.0) == pytest.approx(10.0)


class TestChainProfiles:
    """Test the figures a reader is shown."""

    def test_a_chain_of_short_edges_reports_the_climb_its_edges_cannot(self):
        """Test the trap the two figures exist to keep apart.

        Twenty edges of four metres, each rising three: under a 5 m threshold
        every one of them reports nothing, so their sum is zero. The chain is
        sixty metres higher at the end than at the start and says so.
        """
        pieces = [(LineString([(index * 4, 0), (index * 4 + 4, 0)]), PATH, "c", index, index + 1) for index in range(20)]
        frame = edges(*pieces)
        frame["elevations"] = [np.array([index * 3.0, index * 3.0 + 3.0]) for index in range(20)]

        per_edge = [ascent(values, 5.0) for values in frame["elevations"]]
        assert sum(per_edge) == pytest.approx(0.0)

        measured = chain_profiles(chains((LineString([(0, 0), (80, 0)]), "c")), frame, threshold_m=5.0)
        assert measured["ascent"].iloc[0] == pytest.approx(60.0)

    def test_a_chain_nothing_lies_on_says_nothing(self):
        """Test a chain with no edges, which a ferry crossing is not far from."""
        frame = edges((LineString([(0, 0), (10, 0)]), PATH, "other", 0, 1))
        frame["elevations"] = [np.array([0.0, 5.0])]
        measured = chain_profiles(chains((LineString([(0, 0), (10, 0)]), "c")), frame, threshold_m=5.0)
        assert measured.iloc[0].isna().all()

    def test_a_connector_belongs_to_no_chain(self):
        """Test that a bridged loose end is not laid into a chain's profile."""
        frame = edges((LineString([(0, 0), (10, 0)]), PATH, "c", 0, 1), (LineString([(10, 0), (12, 0)]), BRIDGE, None, 1, 2))
        frame["elevations"] = [np.array([0.0, 20.0]), np.array([20.0, 90.0])]
        measured = chain_profiles(chains((LineString([(0, 0), (10, 0)]), "c")), frame, threshold_m=5.0)
        assert measured["ascent"].iloc[0] == pytest.approx(20.0)


class TestWithElevation:
    """Test what the network comes back carrying."""

    def network(self) -> Network:
        """Build a network of one path, one connector and one crossing.

        Returns:
            The network, with nothing measured yet
        """
        frame = edges(
            (LineString([(0, 0), (10, 0)]), PATH, "path-1", 0, 1),
            (LineString([(10, 0), (20, 0)]), BRIDGE, None, 1, 2),
            (LineString([(20, 0), (30, 0)]), FERRY, "ferry-1", 2, 3),
        )
        drawn = chains((LineString([(0, 0), (10, 0)]), "path-1"), (LineString([(20, 0), (30, 0)]), "ferry-1"))
        return Network(chains=drawn, edges=frame, nodes=gpd.GeoDataFrame(geometry=[], crs=CRS))

    def test_a_walked_edge_gains_a_series_and_a_figure(self):
        """Test the ordinary case."""
        heights = ground({(0, 0): 100.0, (5, 0): 130.0, (10, 0): 160.0})
        measured = with_elevation(self.network(), heights, step_m=5.0, threshold_m=5.0)
        assert measured.edges["elevations"].iloc[0].tolist() == [100.0, 130.0, 160.0]
        assert measured.edges["ascent"].iloc[0] == pytest.approx(60.0)

    def test_a_connector_is_sampled_because_there_is_ground_under_it(self):
        """Test that nobody having drawn a connector does not make it airborne."""
        heights = ground({(10, 0): 160.0, (15, 0): 170.0, (20, 0): 180.0})
        measured = with_elevation(self.network(), heights, step_m=5.0, threshold_m=5.0)
        assert measured.edges["ascent"].iloc[1] == pytest.approx(20.0)

    def test_a_crossing_is_never_asked_about(self):
        """Test the water case: the endpoint would answer a ferry with a depth."""
        asked: list[tuple[float, float]] = []

        def read(coordinates: np.ndarray) -> np.ndarray:
            asked.extend((east, north) for east, north in coordinates.tolist())
            return np.zeros(len(coordinates))

        measured = with_elevation(self.network(), read, step_m=5.0, threshold_m=5.0)
        assert (25.0, 0.0) not in asked
        assert len(measured.edges["elevations"].iloc[2]) == 0
        assert math.isnan(measured.edges["ascent"].iloc[2])

    def test_a_crossing_reports_no_climb_rather_than_none(self):
        """Test that a chain of crossings is unknown rather than flat."""
        measured = with_elevation(self.network(), ground({}), step_m=5.0, threshold_m=5.0)
        assert measured.chains.loc[1, list(PROFILE_COLUMNS)].isna().all()

    def test_ground_the_endpoint_cannot_answer_for_becomes_a_gap(self):
        """Test that a depth or a hole in the coverage is not read as a height."""
        heights = ground({(0, 0): 100.0, (10, 0): 160.0})
        measured = with_elevation(self.network(), heights, step_m=5.0, threshold_m=5.0)
        series = measured.edges["elevations"].iloc[0]
        assert math.isnan(series[1])
        assert measured.edges["ascent"].iloc[0] == pytest.approx(0.0)

    def test_an_answer_that_does_not_fit_the_question_is_refused(self):
        """Test that a short answer is an error rather than a silent misalignment."""
        with pytest.raises(ValueError, match="heights"):
            with_elevation(self.network(), lambda coordinates: np.zeros(len(coordinates) - 1), step_m=5.0)

    def test_a_network_of_nothing_but_crossings_is_not_an_error(self):
        """Test the degenerate case: nothing at all to sample."""
        frame = edges((LineString([(20, 0), (30, 0)]), FERRY, "ferry-1", 2, 3))
        crossings = Network(chains=chains((LineString([(20, 0), (30, 0)]), "ferry-1")), edges=frame, nodes=gpd.GeoDataFrame(geometry=[], crs=CRS))
        measured = with_elevation(crossings, ground({}), step_m=5.0, threshold_m=5.0)
        assert len(measured.edges["elevations"].iloc[0]) == 0
        assert measured.chains.loc[0, list(PROFILE_COLUMNS)].isna().all()

    def test_a_chain_carries_all_four_figures(self):
        """Test that what phase 4's panel shows exists on the chain."""
        heights = ground({(0, 0): 100.0, (5, 0): 60.0, (10, 0): 160.0})
        measured = with_elevation(self.network(), heights, step_m=5.0, threshold_m=5.0)
        chain = measured.chains.loc[0]
        assert chain["ascent"] == pytest.approx(100.0)
        assert chain["descent"] == pytest.approx(40.0)
        assert chain["high_m"] == pytest.approx(160.0)
        assert chain["low_m"] == pytest.approx(60.0)

    def test_a_walked_edge_carries_both_of_its_own(self):
        """Test that the routing figures come in both directions too."""
        heights = ground({(0, 0): 100.0, (5, 0): 60.0, (10, 0): 160.0})
        measured = with_elevation(self.network(), heights, step_m=5.0, threshold_m=5.0)
        assert measured.edges["ascent"].iloc[0] == pytest.approx(100.0)
        assert measured.edges["descent"].iloc[0] == pytest.approx(40.0)
