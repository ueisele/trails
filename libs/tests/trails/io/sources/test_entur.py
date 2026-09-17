"""Tests for the Entur timetable source."""

from unittest.mock import Mock, patch

import pandas as pd
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
    """Three stop places: a served quay, a station a bus also calls at, and a quay nothing sails to."""
    return {
        "data": {
            "stopPlacesByBbox": [
                {"id": "NSR:StopPlace:48932", "name": "Bønå hurtigbåtkai", "latitude": 65.64458, "longitude": 12.75372, "transportMode": ["water"]},
                {"id": "NSR:StopPlace:58971", "name": "Mosjøen stasjon", "latitude": 65.83, "longitude": 13.19, "transportMode": ["bus", "rail"]},
                {"id": "NSR:StopPlace:50233", "name": "Vikdal ferjekai", "latitude": 65.88782, "longitude": 13.09585, "transportMode": ["water"]},
            ]
        }
    }


@pytest.fixture
def lines() -> dict:
    """What serves those three: a boat, a train and a bus, and nothing at all."""
    return {
        "data": {
            "s0": {
                "id": "NSR:StopPlace:48932",
                "quays": [
                    {
                        "lines": [
                            {
                                "publicCode": "18-167",
                                "name": "Brønnøysund-Vega",
                                "transportMode": "water",
                                "authority": {"name": "Nordland fylkeskommune"},
                            }
                        ]
                    },
                    # The connecting bus is not a boat, and must not be listed as one.
                    {
                        "lines": [
                            {
                                "publicCode": "18-166",
                                "name": "Tjøtta-Visthus",
                                "transportMode": "bus",
                                "authority": {"name": "Nordland fylkeskommune"},
                            }
                        ]
                    },
                ],
            },
            "s1": {
                "id": "NSR:StopPlace:58971",
                "quays": [
                    {
                        "lines": [
                            {"publicCode": "F7", "name": "Nordlandsbanen", "transportMode": "rail", "authority": {"name": "SJ Nord"}},
                            {
                                "publicCode": "705",
                                "name": "Mosjøen-Sandnessjøen",
                                "transportMode": "bus",
                                "authority": {"name": "Nordland fylkeskommune"},
                            },
                        ]
                    },
                ],
            },
            "s2": {"id": "NSR:StopPlace:50233", "quays": []},
        }
    }


class TestScheduledStops:
    """Tests for Source.scheduled_stops."""

    def test_keeps_only_the_stops_a_line_calls_at(self, tmp_path, box, places, lines):
        """A stop place carrying a mode but no line of it is registered, not
        served. Measured over this box: Vikdal ferjekai and Toftsundet
        hurtigbåtkai, neither with a departure in sixty days."""
        source = entur.Source(cache_dir=str(tmp_path))
        with patch("requests.post", side_effect=[_mock_response(places), _mock_response(lines)]):
            gdf = source.scheduled_stops(box)

        assert gdf["stop_id"].tolist() == ["NSR:StopPlace:48932", "NSR:StopPlace:58971"]
        assert gdf.crs.to_epsg() == 4326

    def test_a_line_is_filed_under_its_own_mode_and_not_the_stops(self, tmp_path, box, places, lines):
        """Bønå carries a boat line and a bus line; a quay drawn from its stop's
        modes alone would call the bus a sailing."""
        source = entur.Source(cache_dir=str(tmp_path))
        with patch("requests.post", side_effect=[_mock_response(places), _mock_response(lines)]):
            gdf = source.scheduled_stops(box).set_index("name")

        assert gdf.loc["Bønå hurtigbåtkai", "water_lines"] == "18-167 Brønnøysund-Vega"
        assert gdf.loc["Bønå hurtigbåtkai", "bus_lines"] == "18-166 Tjøtta-Visthus"
        assert pd.isna(gdf.loc["Bønå hurtigbåtkai", "rail_lines"])
        assert gdf.loc["Bønå hurtigbåtkai", "modes"] == "boat / bus"

    def test_a_station_says_the_train_and_the_bus_and_who_runs_them(self, tmp_path, box, places, lines):
        source = entur.Source(cache_dir=str(tmp_path))
        with patch("requests.post", side_effect=[_mock_response(places), _mock_response(lines)]):
            gdf = source.scheduled_stops(box).set_index("name")

        assert gdf.loc["Mosjøen stasjon", "rail_lines"] == "F7 Nordlandsbanen"
        assert gdf.loc["Mosjøen stasjon", "bus_lines"] == "705 Mosjøen-Sandnessjøen"
        assert gdf.loc["Mosjøen stasjon", "modes"] == "train / bus"
        assert gdf.loc["Mosjøen stasjon", "operator"] == "SJ Nord / Nordland fylkeskommune"

    def test_the_link_is_the_form_that_renders(self, tmp_path, box, places, lines):
        """`/nearby/<id>` answers 200 and renders *Dead end*; this one renders the
        stop and its board. Measured in Firefox on 2026-09-17."""
        source = entur.Source(cache_dir=str(tmp_path))
        with patch("requests.post", side_effect=[_mock_response(places), _mock_response(lines)]):
            gdf = source.scheduled_stops(box)

        assert gdf["entur_url"].iloc[0] == "https://entur.no/nearby-stop-place-detail?id=NSR:StopPlace:48932"

    def test_is_cached_and_the_key_names_the_modes(self, tmp_path, box, places, lines):
        source = entur.Source(cache_dir=str(tmp_path))
        with patch("requests.post", side_effect=[_mock_response(places), _mock_response(lines)]) as post:
            source.scheduled_stops(box)
            source.scheduled_stops(box)
        assert post.call_count == 2
        assert any("rail-air-water-bus" in path.name for path in tmp_path.rglob("entur_stops_*"))

    def test_a_box_nothing_calls_at_is_empty_rather_than_broken(self, tmp_path, box):
        source = entur.Source(cache_dir=str(tmp_path))
        with patch("requests.post", return_value=_mock_response({"data": {"stopPlacesByBbox": []}})):
            gdf = source.scheduled_stops(box)
        assert len(gdf) == 0
        assert list(gdf.columns) == entur.COLUMNS


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
