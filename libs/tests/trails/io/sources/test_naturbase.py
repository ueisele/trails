"""Tests for the Naturbase protected area source."""

from unittest.mock import Mock, patch

import geopandas as gpd
import pytest
import requests
from trails.io.sources import naturbase


@pytest.fixture
def park_response() -> dict:
    """GeoJSON payload mimicking a single national park match."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "naturvernId": "VV00002750",
                    "navn": "Lomsdal-Visten",
                    "offisieltNavn": "Lomsdal-Visten nasjonalpark/Njaarken vaarjelimmiedajve",
                    "verneform": "Nasjonalpark",
                    "kommune": "Vefsn (1824),Grane (1825)",
                },
                "geometry": {"type": "Polygon", "coordinates": [[[12.4, 65.3], [13.3, 65.3], [13.3, 65.7], [12.4, 65.7], [12.4, 65.3]]]},
            }
        ],
    }


def _mock_response(payload: dict) -> Mock:
    """Build a mock requests response returning the given payload."""
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class TestEscaping:
    """Tests for SQL literal escaping."""

    def test_plain_value_unchanged(self):
        assert naturbase._escape_sql_literal("Lomsdal-Visten") == "Lomsdal-Visten"

    def test_single_quote_is_doubled(self):
        assert naturbase._escape_sql_literal("O'Hara") == "O''Hara"

    def test_injection_attempt_is_neutralized(self):
        escaped = naturbase._escape_sql_literal("x' OR '1'='1")
        assert escaped == "x'' OR ''1''=''1"


class TestFind:
    """Tests for Source.find."""

    def test_returns_geodataframe_in_wgs84(self, tmp_path, park_response):
        source = naturbase.Source(cache_dir=str(tmp_path))

        with patch("requests.get", return_value=_mock_response(park_response)):
            result = source.find("Lomsdal-Visten", layer=naturbase.Layer.NATIONAL_PARK)

        assert isinstance(result, gpd.GeoDataFrame)
        assert len(result) == 1
        assert result.crs.to_epsg() == 4326
        assert result["navn"].iloc[0] == "Lomsdal-Visten"

    def test_substring_search_builds_like_clause(self, tmp_path, park_response):
        source = naturbase.Source(cache_dir=str(tmp_path))

        with patch("requests.get", return_value=_mock_response(park_response)) as mock_get:
            source.find("Lomsdal", layer=naturbase.Layer.NATIONAL_PARK)

        where = mock_get.call_args.kwargs["params"]["where"]
        assert "LIKE" in where
        assert "%Lomsdal%" in where

    def test_exact_search_builds_equality_clause(self, tmp_path, park_response):
        source = naturbase.Source(cache_dir=str(tmp_path))

        with patch("requests.get", return_value=_mock_response(park_response)) as mock_get:
            source.find("Lomsdal-Visten", exact=True)

        where = mock_get.call_args.kwargs["params"]["where"]
        assert where == "navn = 'Lomsdal-Visten'"

    def test_queries_requested_layer(self, tmp_path, park_response):
        source = naturbase.Source(cache_dir=str(tmp_path))

        with patch("requests.get", return_value=_mock_response(park_response)) as mock_get:
            source.find("Lomsdal", layer=naturbase.Layer.NATURE_RESERVE)

        assert mock_get.call_args.args[0].endswith("/2/query")

    def test_second_call_uses_cache(self, tmp_path, park_response):
        source = naturbase.Source(cache_dir=str(tmp_path))

        with patch("requests.get", return_value=_mock_response(park_response)) as mock_get:
            source.find("Lomsdal-Visten")
            source.find("Lomsdal-Visten")

        assert mock_get.call_count == 1

    def test_force_download_bypasses_cache(self, tmp_path, park_response):
        source = naturbase.Source(cache_dir=str(tmp_path))

        with patch("requests.get", return_value=_mock_response(park_response)) as mock_get:
            source.find("Lomsdal-Visten")
            source.find("Lomsdal-Visten", force_download=True)

        assert mock_get.call_count == 2

    def test_arcgis_error_body_raises(self, tmp_path):
        source = naturbase.Source(cache_dir=str(tmp_path))
        payload = {"error": {"code": 400, "message": "Invalid where clause"}}

        with patch("requests.get", return_value=_mock_response(payload)), pytest.raises(ValueError, match="Naturbase query failed"):
            source.find("Lomsdal-Visten")

    def test_unexpected_payload_raises(self, tmp_path):
        source = naturbase.Source(cache_dir=str(tmp_path))

        with (
            patch("requests.get", return_value=_mock_response({"something": "else"})),
            pytest.raises(ValueError, match="Unexpected Naturbase response"),
        ):
            source.find("Lomsdal-Visten")

    def test_http_error_propagates(self, tmp_path):
        source = naturbase.Source(cache_dir=str(tmp_path))
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError("503 Service Unavailable")

        with patch("requests.get", return_value=response), pytest.raises(requests.HTTPError):
            source.find("Lomsdal-Visten")


class TestFindOne:
    """Tests for Source.find_one."""

    def test_returns_single_match(self, tmp_path, park_response):
        source = naturbase.Source(cache_dir=str(tmp_path))

        with patch("requests.get", return_value=_mock_response(park_response)):
            result = source.find_one("Lomsdal-Visten", layer=naturbase.Layer.NATIONAL_PARK)

        assert len(result) == 1

    def test_no_match_raises(self, tmp_path):
        source = naturbase.Source(cache_dir=str(tmp_path))
        empty = {"type": "FeatureCollection", "features": []}

        with patch("requests.get", return_value=_mock_response(empty)), pytest.raises(LookupError, match="No protected area"):
            source.find_one("Does Not Exist")

    def test_ambiguous_match_raises_with_names(self, tmp_path, park_response):
        source = naturbase.Source(cache_dir=str(tmp_path))
        second = dict(park_response["features"][0])
        second["properties"] = dict(second["properties"], navn="Lomsdal-Visten Sør")
        payload = {"type": "FeatureCollection", "features": [park_response["features"][0], second]}

        with patch("requests.get", return_value=_mock_response(payload)), pytest.raises(LookupError, match="ambiguous"):
            source.find_one("Lomsdal")
