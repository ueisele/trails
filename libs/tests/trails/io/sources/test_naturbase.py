"""Tests for the Naturbase protected area source."""

import json
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


class TestVerneformLabel:
    """Tests for the words a protection form is said in."""

    def test_the_register_s_own_spelling_becomes_the_one_a_sign_uses(self):
        # The register writes its values without the letters they are said with.
        assert naturbase.verneform_label("Landskapsvernomraade") == "landskapsvernområde"
        assert naturbase.verneform_label("Nasjonalpark") == "nasjonalpark"

    def test_it_is_the_whole_of_the_service_s_own_coded_value_domain(self):
        # Written from memory it was seven entries, three of them wrong and
        # fourteen missing — including the compound forms within a day's drive
        # of Lomsdal-Visten. This is what `{layer}?f=json` publishes.
        assert len(naturbase.VERNEFORM_LABELS) == 24
        assert naturbase.VERNEFORM_LABELS["Dyrefredningsomrade"] == "dyrefredningsområde"
        assert naturbase.VERNEFORM_LABELS["LandskapsvernomraadePlantelivsfredning"] == "landskapsvernområde med plantelivsfredning"
        # And a code that was invented rather than read is not in it.
        assert "AnnetVern" not in naturbase.VERNEFORM_LABELS

    def test_a_form_it_does_not_know_falls_through_as_it_was_written(self):
        # Renamed to the nearest one it would say something the register does
        # not: a protection type nobody here has seen is not a nature reserve.
        assert naturbase.verneform_label("Kulturmiljoefredning") == "Kulturmiljoefredning"


class TestWithin:
    """Tests for Source.within."""

    def test_it_asks_by_envelope_rather_than_by_name(self, tmp_path, park_response):
        source = naturbase.Source(cache_dir=str(tmp_path))

        with patch("requests.get", return_value=_mock_response(park_response)) as get:
            source.within((12.0, 65.1, 13.7, 65.9))

        params = get.call_args.kwargs["params"]
        assert "where" not in params
        assert params["geometryType"] == "esriGeometryEnvelope"
        assert params["spatialRel"] == "esriSpatialRelIntersects"
        # Without inSR the service reads the box in the layer's own projection
        # and answers about somewhere else.
        assert params["inSR"] == "4326"
        assert json.loads(params["geometry"]) == {"xmin": 12.0, "ymin": 65.1, "xmax": 13.7, "ymax": 65.9, "spatialReference": {"wkid": 4326}}

    def test_it_returns_what_the_box_holds_in_wgs84(self, tmp_path, park_response):
        source = naturbase.Source(cache_dir=str(tmp_path))

        with patch("requests.get", return_value=_mock_response(park_response)):
            found = source.within((12.0, 65.1, 13.7, 65.9))

        assert isinstance(found, gpd.GeoDataFrame)
        assert found.crs.to_epsg() == 4326
        assert found["navn"].tolist() == ["Lomsdal-Visten"]

    def test_a_second_call_over_the_same_box_asks_nothing(self, tmp_path, park_response):
        source = naturbase.Source(cache_dir=str(tmp_path))

        with patch("requests.get", return_value=_mock_response(park_response)) as get:
            source.within((12.0, 65.1, 13.7, 65.9))
            source.within((12.0, 65.1, 13.7, 65.9))

        assert get.call_count == 1

    def test_another_box_is_another_answer(self, tmp_path, park_response):
        source = naturbase.Source(cache_dir=str(tmp_path))

        with patch("requests.get", return_value=_mock_response(park_response)) as get:
            source.within((12.0, 65.1, 13.7, 65.9))
            source.within((12.0, 65.1, 13.7, 66.0))

        assert get.call_count == 2

    def test_a_truncated_answer_is_refused_rather_than_taken(self, tmp_path, park_response):
        # ArcGIS reports a partial answer as a successful one with a flag.
        # Taking the first page would build a network that knows about some of
        # the protected ground it runs over and not the rest.
        source = naturbase.Source(cache_dir=str(tmp_path))
        truncated = {**park_response, "exceededTransferLimit": True}

        with patch("requests.get", return_value=_mock_response(truncated)):
            with pytest.raises(ValueError, match="smaller box"):
                source.within((12.0, 65.1, 13.7, 65.9))

    def test_an_empty_box_comes_back_as_an_empty_frame(self, tmp_path):
        source = naturbase.Source(cache_dir=str(tmp_path))

        with patch("requests.get", return_value=_mock_response({"type": "FeatureCollection", "features": []})):
            found = source.within((12.0, 65.1, 13.7, 65.9))

        assert len(found) == 0
        assert "verneform" in found.columns

    def test_an_arcgis_error_body_raises(self, tmp_path):
        source = naturbase.Source(cache_dir=str(tmp_path))

        with patch("requests.get", return_value=_mock_response({"error": {"code": 400}})):
            with pytest.raises(ValueError, match="query failed"):
                source.within((12.0, 65.1, 13.7, 65.9))
