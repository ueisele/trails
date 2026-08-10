"""Tests for the Kommuneinfo municipality source."""

from unittest.mock import Mock, patch

import geopandas as gpd
import pandas as pd
import pytest
import requests
from shapely.geometry import Polygon
from trails.io.sources import kommuneinfo


def _mock_response(payload: object) -> Mock:
    """Build a mock requests response returning the given payload."""
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def _square(x0: float, y0: float, x1: float, y1: float) -> dict:
    """Return a GeoJSON polygon for the given extent."""
    return {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


@pytest.fixture
def kommune_list() -> list[dict]:
    """Three municipalities, two of them in county 18."""
    return [
        {"kommunenummer": "1824", "kommunenavnNorsk": "Vefsn"},
        {"kommunenummer": "1813", "kommunenavnNorsk": "Brønnøy"},
        {"kommunenummer": "5001", "kommunenavnNorsk": "Trondheim"},
    ]


class TestListAll:
    """Tests for Source.list_all."""

    def test_returns_number_and_name(self, tmp_path, kommune_list):
        source = kommuneinfo.Source(cache_dir=str(tmp_path))

        with patch("requests.get", return_value=_mock_response(kommune_list)):
            frame = source.list_all()

        assert isinstance(frame, pd.DataFrame)
        assert list(frame.columns) == ["number", "name"]
        assert set(frame["number"]) == {"1824", "1813", "5001"}

    def test_second_call_uses_cache(self, tmp_path, kommune_list):
        source = kommuneinfo.Source(cache_dir=str(tmp_path))

        with patch("requests.get", return_value=_mock_response(kommune_list)) as mock_get:
            source.list_all()
            source.list_all()

        assert mock_get.call_count == 1


class TestGeometry:
    """Tests for boundary and bounding box lookups."""

    def test_bounding_box_reads_avgrensningsboks(self, tmp_path):
        source = kommuneinfo.Source(cache_dir=str(tmp_path))
        payload = {"kommunenavn": "Vefsn", "avgrensningsboks": _square(12.5, 65.4, 13.7, 66.1)}

        with patch("requests.get", return_value=_mock_response(payload)):
            gdf = source.bounding_box("1824")

        assert isinstance(gdf, gpd.GeoDataFrame)
        assert gdf.crs.to_epsg() == 4326
        assert gdf["number"].iloc[0] == "1824"

    def test_geometry_reads_omrade(self, tmp_path):
        source = kommuneinfo.Source(cache_dir=str(tmp_path))
        payload = {"kommunenavn": "Vefsn", "omrade": _square(12.5, 65.4, 13.7, 66.1)}

        with patch("requests.get", return_value=_mock_response(payload)) as mock_get:
            gdf = source.geometry("1824")

        assert mock_get.call_args.args[0].endswith("/kommuner/1824/omrade")
        assert not gdf.geometry.iloc[0].is_empty

    def test_missing_geometry_raises(self, tmp_path):
        source = kommuneinfo.Source(cache_dir=str(tmp_path))

        with patch("requests.get", return_value=_mock_response({"kommunenavn": "Vefsn"})), pytest.raises(LookupError, match="no omrade"):
            source.geometry("1824")

    def test_http_error_propagates(self, tmp_path):
        source = kommuneinfo.Source(cache_dir=str(tmp_path))
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError("500")

        with patch("requests.get", return_value=response), pytest.raises(requests.HTTPError):
            source.geometry("1824")

    def test_bbox_and_outline_are_cached_separately(self, tmp_path):
        source = kommuneinfo.Source(cache_dir=str(tmp_path))
        payload = {"kommunenavn": "Vefsn", "avgrensningsboks": _square(12.5, 65.4, 13.7, 66.1), "omrade": _square(12.5, 65.4, 13.7, 66.1)}

        with patch("requests.get", return_value=_mock_response(payload)) as mock_get:
            source.bounding_box("1824")
            source.geometry("1824")
            source.bounding_box("1824")

        assert mock_get.call_count == 2


class TestIntersecting:
    """Tests for Source.intersecting."""

    @pytest.fixture
    def area(self) -> gpd.GeoDataFrame:
        """A small area overlapping only the first municipality."""
        return gpd.GeoDataFrame(geometry=[Polygon([(12.6, 65.5), (12.8, 65.5), (12.8, 65.7), (12.6, 65.7)])], crs="EPSG:4326")

    def test_returns_only_overlapping_municipalities(self, tmp_path, kommune_list, area):
        source = kommuneinfo.Source(cache_dir=str(tmp_path))
        shapes = {
            "1824": _square(12.5, 65.4, 13.7, 66.1),  # overlaps
            "1813": _square(11.0, 64.0, 11.5, 64.5),  # far away
        }

        def fake_get(url, **kwargs):
            if url.endswith("/kommuner"):
                return _mock_response(kommune_list)
            number = url.rstrip("/").split("/kommuner/")[1].split("/")[0]
            key = "omrade" if url.endswith("/omrade") else "avgrensningsboks"
            return _mock_response({"kommunenavn": number, key: shapes[number]})

        with patch("requests.get", side_effect=fake_get):
            matches = source.intersecting(area, fylke=("18",))

        assert matches == ["1824"]

    def test_county_filter_skips_other_counties(self, tmp_path, kommune_list, area):
        source = kommuneinfo.Source(cache_dir=str(tmp_path))
        requested = []

        def fake_get(url, **kwargs):
            if url.endswith("/kommuner"):
                return _mock_response(kommune_list)
            number = url.rstrip("/").split("/kommuner/")[1].split("/")[0]
            requested.append(number)
            return _mock_response({"kommunenavn": number, "avgrensningsboks": _square(11.0, 64.0, 11.5, 64.5)})

        with patch("requests.get", side_effect=fake_get):
            source.intersecting(area, fylke=("18",))

        assert "5001" not in requested

    def test_outline_is_only_fetched_for_bbox_matches(self, tmp_path, kommune_list, area):
        source = kommuneinfo.Source(cache_dir=str(tmp_path))
        outline_calls = []

        def fake_get(url, **kwargs):
            if url.endswith("/kommuner"):
                return _mock_response(kommune_list)
            number = url.rstrip("/").split("/kommuner/")[1].split("/")[0]
            if url.endswith("/omrade"):
                outline_calls.append(number)
                return _mock_response({"kommunenavn": number, "omrade": _square(12.5, 65.4, 13.7, 66.1)})
            box = _square(12.5, 65.4, 13.7, 66.1) if number == "1824" else _square(11.0, 64.0, 11.5, 64.5)
            return _mock_response({"kommunenavn": number, "avgrensningsboks": box})

        with patch("requests.get", side_effect=fake_get):
            source.intersecting(area, fylke=("18",))

        assert outline_calls == ["1824"]
