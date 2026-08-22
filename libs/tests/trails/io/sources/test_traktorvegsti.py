"""Tests for the detailed path (traktorveg_sti) WFS source."""

from unittest.mock import Mock, patch

import geopandas as gpd
import pytest
import requests
from trails.io.sources import traktorvegsti

BOUNDS = (12.4, 65.3, 13.3, 65.7)


def _feature(osm_typeveg: str, coords: list[list[float]]) -> dict:
    """Build a GeoJSON feature in the request projection."""
    return {
        "type": "Feature",
        "properties": {"objtype": "Veglenke", "typeveg": osm_typeveg, "kommunenummer": "1824"},
        "geometry": {"type": "LineString", "coordinates": coords},
    }


def _geojson_response(features: list[dict]) -> Mock:
    """Mock a WFS GeoJSON response."""
    response = Mock()
    response.json.return_value = {"type": "FeatureCollection", "features": features}
    response.raise_for_status.return_value = None
    return response


def _hits_response(count: int) -> Mock:
    """Mock a WFS resultType=hits response."""
    response = Mock()
    response.text = f'<wfs:FeatureCollection numberMatched="{count}" numberReturned="0"/>'
    response.raise_for_status.return_value = None
    return response


@pytest.fixture
def features() -> list[dict]:
    """One path, one tractor road and one ordinary road."""
    return [
        _feature("sti", [[380000.0, 7300000.0], [380100.0, 7300100.0]]),
        _feature("traktorveg", [[381000.0, 7301000.0], [381100.0, 7301100.0]]),
        _feature("enkelBilveg", [[382000.0, 7302000.0], [382100.0, 7302100.0]]),
    ]


class TestCount:
    """Tests for Source.count."""

    def test_reads_number_matched(self, tmp_path):
        source = traktorvegsti.Source(cache_dir=str(tmp_path))

        with patch("requests.get", return_value=_hits_response(6665)):
            assert source.count(BOUNDS) == 6665

    def test_missing_number_matched_raises(self, tmp_path):
        source = traktorvegsti.Source(cache_dir=str(tmp_path))
        response = Mock()
        response.text = "<ServiceException>broken</ServiceException>"
        response.raise_for_status.return_value = None

        with patch("requests.get", return_value=response), pytest.raises(ValueError, match="numberMatched"):
            source.count(BOUNDS)

    def test_http_error_propagates(self, tmp_path):
        source = traktorvegsti.Source(cache_dir=str(tmp_path))
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError("500")

        with patch("requests.get", return_value=response), pytest.raises(requests.HTTPError):
            source.count(BOUNDS)


class TestFetchPaths:
    """Tests for Source.fetch_paths."""

    def test_keeps_only_walkable_types(self, tmp_path, features):
        source = traktorvegsti.Source(cache_dir=str(tmp_path))

        with patch("requests.get", side_effect=[_hits_response(3), _geojson_response(features)]):
            gdf = source.fetch_paths(BOUNDS)

        assert isinstance(gdf, gpd.GeoDataFrame)
        assert sorted(gdf["typeveg"]) == ["sti", "traktorveg"]
        assert gdf.crs.to_epsg() == 4326

    def test_pages_until_all_features_are_read(self, tmp_path, features):
        source = traktorvegsti.Source(cache_dir=str(tmp_path), page_size=2)
        page_one, page_two = features[:2], features[2:]

        with patch("requests.get", side_effect=[_hits_response(3), _geojson_response(page_one), _geojson_response(page_two)]) as mock_get:
            source.fetch_paths(BOUNDS)

        start_indexes = [call.kwargs["params"].get("startIndex") for call in mock_get.call_args_list if "startIndex" in call.kwargs.get("params", {})]
        assert start_indexes == [0, 2]

    def test_stops_when_a_page_comes_back_empty(self, tmp_path, features):
        source = traktorvegsti.Source(cache_dir=str(tmp_path), page_size=2)

        # Service claims more than it delivers; the loop must not spin forever.
        with patch("requests.get", side_effect=[_hits_response(99), _geojson_response(features[:2]), _geojson_response([])]):
            gdf = source.fetch_paths(BOUNDS)

        assert len(gdf) == 2

    def test_empty_result_keeps_schema(self, tmp_path):
        source = traktorvegsti.Source(cache_dir=str(tmp_path))

        with patch("requests.get", side_effect=[_hits_response(0)]):
            gdf = source.fetch_paths(BOUNDS)

        assert len(gdf) == 0
        assert "typeveg" in gdf.columns
        assert gdf.crs.to_epsg() == 4326

    def test_second_call_uses_cache(self, tmp_path, features):
        source = traktorvegsti.Source(cache_dir=str(tmp_path))

        with patch("requests.get", side_effect=[_hits_response(3), _geojson_response(features)]) as mock_get:
            source.fetch_paths(BOUNDS)
            source.fetch_paths(BOUNDS)

        assert mock_get.call_count == 2

    def test_it_says_when_what_it_served_was_read(self, tmp_path, features):
        """The WFS publishes no version, so an exported file records the moment
        the answer in the cache was read instead. Both ways of serving one — a
        fresh query and a cache hit — have to answer, or a rebuilt map would
        record nothing for a source it certainly used."""
        source = traktorvegsti.Source(cache_dir=str(tmp_path))
        assert source.loaded_at is None

        with patch("requests.get", side_effect=[_hits_response(3), _geojson_response(features)]):
            source.fetch_paths(BOUNDS)
        fetched = source.loaded_at

        source.fetch_paths(BOUNDS)

        assert fetched is not None
        assert fetched.startswith("20")
        assert source.loaded_at == fetched

    def test_bbox_is_sent_in_request_projection(self, tmp_path, features):
        source = traktorvegsti.Source(cache_dir=str(tmp_path))

        with patch("requests.get", side_effect=[_hits_response(3), _geojson_response(features)]) as mock_get:
            source.fetch_paths(BOUNDS)

        bbox = mock_get.call_args_list[0].kwargs["params"]["bbox"]
        assert bbox.endswith("urn:ogc:def:crs:EPSG::25833")
        # Projected metres, not degrees.
        assert float(bbox.split(",")[0]) > 1000
