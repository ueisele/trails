"""Tests for the Entur timetable source."""

from unittest.mock import Mock, patch

import pytest
from trails.io.sources import entur


def _mock_response(payload: dict) -> Mock:
    """Build a mock requests response returning the given payload."""
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


@pytest.fixture
def box() -> entur.Bounds:
    """The Lomsdal-Visten box, in GeoPandas order."""
    return (12.0556, 65.1749, 13.6946, 65.9213)


@pytest.fixture
def places() -> dict:
    """Three stop places: a served quay, a bus stop, and a quay nothing sails to."""
    return {
        "data": {
            "stopPlacesByBbox": [
                {"id": "NSR:StopPlace:48932", "name": "Bønå hurtigbåtkai", "latitude": 65.64458, "longitude": 12.75372, "transportMode": ["water"]},
                {"id": "NSR:StopPlace:11111", "name": "Somewhere bussholdeplass", "latitude": 65.5, "longitude": 12.6, "transportMode": ["bus"]},
                {"id": "NSR:StopPlace:50233", "name": "Vikdal ferjekai", "latitude": 65.88782, "longitude": 13.09585, "transportMode": ["water"]},
            ]
        }
    }


@pytest.fixture
def lines() -> dict:
    """What serves those two water stops: a boat at one, nothing at the other."""
    return {
        "data": {
            "s0": {
                "id": "NSR:StopPlace:48932",
                "quays": [
                    {"lines": [{"publicCode": "18-167", "transportMode": "water", "authority": {"name": "Nordland fylkeskommune"}}]},
                    # The connecting bus is not a boat, and must not make a quay served.
                    {"lines": [{"publicCode": "18-166", "transportMode": "bus", "authority": {"name": "Nordland fylkeskommune"}}]},
                ],
            },
            "s1": {"id": "NSR:StopPlace:50233", "quays": []},
        }
    }


class TestWaterStops:
    """Tests for Source.water_stops."""

    def test_keeps_only_quays_a_boat_line_calls_at(self, tmp_path, box, places, lines):
        """A stop place carrying the water mode but no water line is registered,
        not served. Measured over this box: Vikdal ferjekai and Toftsundet
        hurtigbåtkai, neither with a departure in sixty days."""
        source = entur.Source(cache_dir=str(tmp_path))
        with patch("requests.post", side_effect=[_mock_response(places), _mock_response(lines)]):
            gdf = source.water_stops(box)

        assert gdf["stop_id"].tolist() == ["NSR:StopPlace:48932"]
        assert gdf["lines"].tolist() == ["18-167"]
        assert gdf["operator"].tolist() == ["Nordland fylkeskommune"]
        assert gdf.crs.to_epsg() == 4326

    def test_the_link_is_the_form_that_renders(self, tmp_path, box, places, lines):
        """`/nearby/<id>` answers 200 and renders *Dead end*; this one renders the
        stop and its board. Measured in Firefox on 2026-09-17."""
        source = entur.Source(cache_dir=str(tmp_path))
        with patch("requests.post", side_effect=[_mock_response(places), _mock_response(lines)]):
            gdf = source.water_stops(box)

        assert gdf["entur_url"].iloc[0] == "https://entur.no/nearby-stop-place-detail?id=NSR:StopPlace:48932"

    def test_is_cached_and_the_key_names_the_shape(self, tmp_path, box, places, lines):
        source = entur.Source(cache_dir=str(tmp_path))
        with patch("requests.post", side_effect=[_mock_response(places), _mock_response(lines)]) as post:
            source.water_stops(box)
            source.water_stops(box)
        assert post.call_count == 2
        assert any("_served" in path.name for path in tmp_path.rglob("entur_water_stops_*"))

    def test_a_box_nothing_sails_to_is_empty_rather_than_broken(self, tmp_path, box):
        source = entur.Source(cache_dir=str(tmp_path))
        with patch("requests.post", return_value=_mock_response({"data": {"stopPlacesByBbox": []}})):
            gdf = source.water_stops(box)
        assert len(gdf) == 0
        assert list(gdf.columns) == ["stop_id", "name", "lines", "operator", "entur_url", "geometry"]


class TestQuery:
    """Tests for Source.query."""

    def test_a_graphql_error_is_a_failure_and_not_a_shrug(self, tmp_path):
        """The response carries HTTP 200 and a `data` of nulls, and a build that
        read those would quietly draw every quay as unserved.

        **And it is not retried.** A rejected query is rejected again a minute
        later, so this fails at once and says what Entur said, rather than
        spending the backoff to arrive at the same answer."""
        source = entur.Source(cache_dir=str(tmp_path))
        with patch("requests.post", return_value=_mock_response({"errors": [{"message": "no"}], "data": None})) as post:
            with pytest.raises(entur.EnturError, match="answered with errors"):
                source.query("{ ping }")
        assert post.call_count == 1

    def test_it_names_itself_to_entur(self, tmp_path):
        source = entur.Source(cache_dir=str(tmp_path))
        with patch("requests.post", return_value=_mock_response({"data": {}})) as post:
            source.query("{ ping }")
        assert post.call_args.kwargs["headers"]["ET-Client-Name"] == entur.CLIENT_NAME
