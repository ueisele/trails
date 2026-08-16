"""Tests for the height endpoint and the store that keeps it from being asked twice."""

import json
import math
from unittest.mock import Mock, patch

import numpy as np
import pytest
import requests
from trails.io.sources import hoydedata
from trails.io.sources.hoydedata import PointStore, Source


def _answer(*points: dict) -> Mock:
    """Build a response carrying one entry per point asked about.

    Args:
        *points: What each point came back as

    Returns:
        A stand-in for the endpoint's answer
    """
    response = Mock()
    response.json.return_value = {"koordsys": hoydedata.COORDINATE_SYSTEM, "punkter": list(points)}
    response.raise_for_status.return_value = None
    return response


def _ground(height: float) -> dict:
    """One point answered out of the terrain model.

    Args:
        height: Its height

    Returns:
        The entry the endpoint would send
    """
    return {"datakilde": "dtm1", "terreng": "Skog", "x": 0.0, "y": 0.0, "z": height}


def _asked(call: object) -> list[list[float]]:
    """Read the points out of one recorded request.

    Args:
        call: A recorded call to the session

    Returns:
        The coordinates it asked about
    """
    points: list[list[float]] = json.loads(call.kwargs["params"]["punkter"])
    return points


class TestReadings:
    """Test what counts as a height."""

    def test_a_terrain_model_answer_is_a_height(self):
        """Test the ordinary case."""
        assert hoydedata._reading(_ground(412.3)) == pytest.approx(412.3)

    def test_a_depth_over_water_is_not_a_height(self):
        """Test the answer that poisons a coastal profile: -276 m is a seabed."""
        depth = {"datakilde": "dybdekurver", "terreng": "Havflate", "x": 0.0, "y": 0.0, "z": -276.0}
        assert math.isnan(hoydedata._reading(depth))

    def test_nothing_at_all_outside_the_coverage_is_not_a_height(self):
        """Test the other answer that is not one."""
        assert math.isnan(hoydedata._reading({"datakilde": None, "terreng": None, "x": 0.0, "y": 0.0, "z": None}))

    def test_an_answer_from_something_unrecognised_is_not_read_as_ground(self):
        """Test the safe direction: an unknown source is a gap, not a number."""
        assert math.isnan(hoydedata._reading({"datakilde": "something-new", "z": 100.0}))

    def test_an_answer_of_the_wrong_length_is_refused(self):
        """Test that a short answer is an error rather than a silent shift."""
        with pytest.raises(ValueError, match="asked about"):
            hoydedata._readings({"punkter": [_ground(1.0)]}, 2)


class TestPointStore:
    """Test the table that keeps a second build from asking again."""

    def test_what_was_written_is_read_back(self, tmp_path):
        """Test the round trip through parquet."""
        store = PointStore(tmp_path / "points.parquet")
        store.add(hoydedata.keys_of(np.array([[398130.0, 7281098.0]])), np.array([1.77]))
        store.save()

        heights, known = PointStore(tmp_path / "points.parquet").lookup(hoydedata.keys_of(np.array([[398130.0, 7281098.0]])))
        assert known.tolist() == [True]
        assert heights.tolist() == [pytest.approx(1.77)]

    def test_a_point_with_no_height_is_still_remembered(self, tmp_path):
        """Test the reason a gap is a row.

        A store that recorded only the successes would ask again about exactly
        the points that can never answer, on every build, for as long as the
        network touches a coast.
        """
        store = PointStore(tmp_path / "points.parquet")
        store.add(hoydedata.keys_of(np.array([[100.0, 200.0]])), np.array([math.nan]))
        heights, known = store.lookup(hoydedata.keys_of(np.array([[100.0, 200.0]])))
        assert known.tolist() == [True]
        assert math.isnan(heights[0])

    def test_a_coordinate_it_has_not_seen_is_unknown(self, tmp_path):
        """Test the miss."""
        store = PointStore(tmp_path / "points.parquet")
        store.add(hoydedata.keys_of(np.array([[100.0, 200.0]])), np.array([5.0]))
        _, known = store.lookup(hoydedata.keys_of(np.array([[100.0, 201.0]])))
        assert known.tolist() == [False]

    def test_it_keys_on_the_centimetre(self, tmp_path):
        """Test the grain: finer is noise, coarser is half a metre of height."""
        store = PointStore(tmp_path / "points.parquet")
        store.add(hoydedata.keys_of(np.array([[100.0, 200.0]])), np.array([5.0]))
        _, same = store.lookup(hoydedata.keys_of(np.array([[100.001, 200.0]])))
        _, apart = store.lookup(hoydedata.keys_of(np.array([[100.02, 200.0]])))
        assert same.tolist() == [True]
        assert apart.tolist() == [False]

    def test_a_coordinate_is_kept_once(self, tmp_path):
        """Test that asking twice does not grow the table."""
        store = PointStore(tmp_path / "points.parquet")
        store.add(hoydedata.keys_of(np.array([[100.0, 200.0]])), np.array([5.0]))
        store.add(hoydedata.keys_of(np.array([[100.0, 200.0]])), np.array([5.0]))
        assert len(store) == 1

    def test_a_coordinate_off_the_grid_it_was_built_for_is_refused(self):
        """Test that a mistaken CRS fails loudly rather than colliding silently."""
        with pytest.raises(ValueError, match="EPSG:25833"):
            hoydedata.keys_of(np.array([[13.5, 65.5], [1e9, 1e9]]))


class TestSource:
    """Test the fetching."""

    def source(self, tmp_path) -> Source:
        """Build a source with an empty store.

        Args:
            tmp_path: Directory for its store

        Returns:
            The source, asking one request at a time so calls are in order
        """
        return Source(cache_dir=str(tmp_path), workers=1, initial_backoff=0.0)

    def test_the_heights_come_back_in_the_order_they_were_asked_for(self, tmp_path):
        """Test the ordinary case."""
        with patch.object(requests.Session, "get", return_value=_answer(_ground(10.0), _ground(20.0))):
            heights = self.source(tmp_path).elevations(np.array([[100.0, 200.0], [110.0, 200.0]]))
        assert heights.tolist() == [10.0, 20.0]

    def test_a_coordinate_asked_for_twice_is_asked_about_once(self, tmp_path):
        """Test the deduplication *within* one run, which is 28 % of the work."""
        with patch.object(requests.Session, "get", return_value=_answer(_ground(10.0))) as session:
            heights = self.source(tmp_path).elevations(np.array([[100.0, 200.0], [100.0, 200.0], [100.0, 200.0]]))
        assert heights.tolist() == [10.0, 10.0, 10.0]
        assert _asked(session.call_args) == [[100.0, 200.0]]

    def test_a_second_run_asks_nothing(self, tmp_path):
        """Test the acceptance: a second build must not touch the endpoint."""
        points = np.array([[100.0, 200.0], [110.0, 200.0]])
        with patch.object(requests.Session, "get", return_value=_answer(_ground(10.0), _ground(20.0))):
            self.source(tmp_path).elevations(points)

        with patch.object(requests.Session, "get", side_effect=AssertionError("asked again")) as session:
            heights = self.source(tmp_path).elevations(points)
        assert heights.tolist() == [10.0, 20.0]
        assert session.call_count == 0

    def test_a_second_run_asks_nothing_about_water_either(self, tmp_path):
        """Test that a point which cannot answer is not asked again forever."""
        points = np.array([[100.0, 200.0]])
        depth = {"datakilde": "dybdekurver", "terreng": "Havflate", "z": -276.0}
        with patch.object(requests.Session, "get", return_value=_answer(depth)):
            self.source(tmp_path).elevations(points)

        with patch.object(requests.Session, "get", side_effect=AssertionError("asked again")) as session:
            heights = self.source(tmp_path).elevations(points)
        assert math.isnan(heights[0])
        assert session.call_count == 0

    def test_it_asks_fifty_points_at_a_time(self, tmp_path):
        """Test the endpoint's own cap."""
        points = np.stack([np.arange(120.0), np.zeros(120)], axis=1)

        def answer(_url: str, params: dict, timeout: int) -> Mock:
            return _answer(*(_ground(1.0) for _ in json.loads(params["punkter"])))

        with patch.object(requests.Session, "get", side_effect=answer) as session:
            self.source(tmp_path).elevations(points)
        assert [len(_asked(call)) for call in session.call_args_list] == [50, 50, 20]

    def test_a_failed_request_is_retried(self, tmp_path):
        """Test that a busy public endpoint does not lose a quarter of an hour."""
        failing = requests.ConnectionError("busy")
        with patch.object(requests.Session, "get", side_effect=[failing, _answer(_ground(10.0))]) as session:
            heights = self.source(tmp_path).elevations(np.array([[100.0, 200.0]]))
        assert heights.tolist() == [10.0]
        assert session.call_count == 2

    def test_a_request_that_never_succeeds_stops_the_build(self, tmp_path):
        """Test that a gap is never invented out of a failure."""
        with patch.object(requests.Session, "get", side_effect=requests.ConnectionError("busy")), pytest.raises(requests.ConnectionError):
            self.source(tmp_path).elevations(np.array([[100.0, 200.0]]))

    def test_what_was_answered_before_a_failure_is_kept(self, tmp_path):
        """Test that an interrupted run resumes rather than starting again."""
        points = np.stack([np.arange(60.0), np.zeros(60)], axis=1)
        answers = [_answer(*(_ground(1.0) for _ in range(50)))] + [requests.ConnectionError("busy")] * 4
        source = Source(cache_dir=str(tmp_path), workers=1, initial_backoff=0.0, flush_seconds=0.0)
        with patch.object(requests.Session, "get", side_effect=answers), pytest.raises(requests.ConnectionError):
            source.elevations(points)

        assert len(PointStore(source.store.path)) == 50
