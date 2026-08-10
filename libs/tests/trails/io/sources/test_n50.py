"""Tests for the N50 Kartdata source."""

from unittest.mock import Mock, patch

import geopandas as gpd
import pytest
import requests
from shapely.geometry import LineString, Point, Polygon
from trails.io.sources import n50


def _mock_response(payload: dict) -> Mock:
    """Build a mock requests response returning the given payload."""
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


@pytest.fixture
def order_response() -> dict:
    """A Geonorge order response covering two municipalities."""
    return {
        "referenceNumber": "abc-123",
        "files": [
            {"name": "Basisdata_1824_Vefsn_25833_N50Kartdata_FGDB.zip", "downloadUrl": "https://example.test/vefsn"},
            {"name": "Basisdata_1813_Bronnoy_25833_N50Kartdata_FGDB.zip", "downloadUrl": "https://example.test/bronnoy"},
        ],
    }


@pytest.fixture
def transport() -> gpd.GeoDataFrame:
    """A transport layer holding a road, a path and a tractor road."""
    return gpd.GeoDataFrame(
        {
            "objtype": ["Veglenke"] * 3,
            "typeveg": ["enkelBilveg", "sti", "traktorveg"],
            "rutemerking": ["NEI", "JA", "NEI"],
            "geometry": [
                LineString([(12.8, 65.4), (12.81, 65.41)]),
                LineString([(12.9, 65.5), (12.91, 65.51)]),
                LineString([(13.0, 65.6), (13.01, 65.61)]),
            ],
        },
        crs="EPSG:25833",
    )


class TestOrder:
    """Tests for Source.order."""

    def test_returns_one_entry_per_file(self, tmp_path, order_response):
        source = n50.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response(order_response)):
            files = source.order(["1824", "1813"])

        assert [entry.url for entry in files] == ["https://example.test/vefsn", "https://example.test/bronnoy"]

    def test_sends_requested_municipalities(self, tmp_path, order_response):
        source = n50.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response(order_response)) as mock_post:
            source.order(["1824", "1813"])

        areas = mock_post.call_args.kwargs["json"]["orderLines"][0]["areas"]
        assert [area["code"] for area in areas] == ["1824", "1813"]
        assert all(area["type"] == "kommune" for area in areas)

    def test_empty_file_list_raises(self, tmp_path):
        source = n50.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response({"files": []})), pytest.raises(ValueError, match="no downloadable files"):
            source.order(["1824"])

    def test_http_error_propagates(self, tmp_path):
        source = n50.Source(cache_dir=str(tmp_path))
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError("503")

        with patch("requests.post", return_value=response), pytest.raises(requests.HTTPError):
            source.order(["1824"])


class TestFetch:
    """Tests for Source.fetch and its caching behaviour."""

    def test_downloads_missing_municipalities(self, tmp_path, order_response):
        source = n50.Source(cache_dir=str(tmp_path))

        with (
            patch("requests.post", return_value=_mock_response(order_response)),
            patch.object(source.downloads, "download") as mock_download,
        ):
            paths = source.fetch(["1824", "1813"])

        assert mock_download.call_count == 2
        assert set(paths) == {"1824", "1813"}

    def test_skips_ordering_when_everything_is_cached(self, tmp_path, order_response):
        source = n50.Source(cache_dir=str(tmp_path))
        for code in ("1824", "1813"):
            (source.downloads.cache_dir / f"n50_{code}.zip").write_bytes(b"cached")

        with patch("requests.post", return_value=_mock_response(order_response)) as mock_post:
            source.fetch(["1824", "1813"])

        mock_post.assert_not_called()

    def test_only_missing_municipalities_are_ordered(self, tmp_path, order_response):
        source = n50.Source(cache_dir=str(tmp_path))
        (source.downloads.cache_dir / "n50_1813.zip").write_bytes(b"cached")

        with (
            patch("requests.post", return_value=_mock_response(order_response)) as mock_post,
            patch.object(source.downloads, "download"),
        ):
            source.fetch(["1824", "1813"])

        ordered = [area["code"] for area in mock_post.call_args.kwargs["json"]["orderLines"][0]["areas"]]
        assert ordered == ["1824"]

    def test_missing_file_in_order_raises(self, tmp_path):
        source = n50.Source(cache_dir=str(tmp_path))
        response = {"files": [{"name": "Basisdata_9999_Other_25833_N50Kartdata_FGDB.zip", "downloadUrl": "https://example.test/x"}]}

        with patch("requests.post", return_value=_mock_response(response)), pytest.raises(LookupError, match="no file for municipality 1824"):
            source.fetch(["1824"])


@pytest.fixture
def transport_with_ferries() -> gpd.GeoDataFrame:
    """A transport layer holding a path, a car ferry and a passenger ferry."""
    return gpd.GeoDataFrame(
        {
            "objtype": ["Veglenke"] * 3,
            "typeveg": ["sti", "bilferje", "passasjerferje"],
            "geometry": [
                LineString([(12.8, 65.4), (12.81, 65.41)]),
                LineString([(12.9, 65.5), (12.95, 65.55)]),
                LineString([(13.0, 65.6), (13.05, 65.65)]),
            ],
        },
        crs="EPSG:4326",
    )


@pytest.fixture
def buildings() -> gpd.GeoDataFrame:
    """A named cabin, a rest hut as an outline, an unnamed wilderness hut, a house."""
    return gpd.GeoDataFrame(
        {
            "navn": ["Litjvasshytta", "Eiteråfjellet", None, None],
            "betjeningsgrad": ["Ubetjent", "Rastebu", None, None],
            "bygningstype": [161.0, 161.0, 172.0, 111.0],
            "hytteeier": [2.0, 4.0, None, None],
            "kommune": ["1824", "1824", "1824", "1824"],
            "geometry": [
                Point(13.09, 65.60),
                Polygon([(13.11, 65.63), (13.12, 65.63), (13.12, 65.64), (13.11, 65.64)]),
                Point(13.0626, 65.6196),
                Point(13.20, 65.70),
            ],
        },
        crs="EPSG:4326",
    )


class TestLoadCabins:
    """Tests for Source.load_cabins."""

    def test_keeps_buildings_with_a_service_level(self, tmp_path, buildings):
        source = n50.Source(cache_dir=str(tmp_path))

        with patch.object(source, "load_layers", return_value=buildings):
            cabins = source.load_cabins(["1824"])

        assert sorted(cabins["navn"].dropna()) == ["Eiteråfjellet", "Litjvasshytta"]

    def test_keeps_unnamed_wilderness_huts_by_building_type(self, tmp_path, buildings):
        # Sæterskardhytta is in N50 only as an unnamed type 172.
        source = n50.Source(cache_dir=str(tmp_path))

        with patch.object(source, "load_layers", return_value=buildings):
            cabins = source.load_cabins(["1824"])

        assert len(cabins) == 3
        assert "Skogs- og utmarkskoie, gamme" in set(cabins["kind"])

    def test_excludes_ordinary_buildings(self, tmp_path, buildings):
        source = n50.Source(cache_dir=str(tmp_path))

        with patch.object(source, "load_layers", return_value=buildings):
            cabins = source.load_cabins(["1824"])

        assert 111.0 not in set(cabins.get("bygningstype", []))
        assert len(cabins) < len(buildings)

    def test_kind_prefers_service_level_over_building_type(self, tmp_path, buildings):
        source = n50.Source(cache_dir=str(tmp_path))

        with patch.object(source, "load_layers", return_value=buildings):
            cabins = source.load_cabins(["1824"])

        kinds = dict(zip(cabins["navn"].fillna("unnamed"), cabins["kind"], strict=True))
        assert kinds["Litjvasshytta"] == "Ubetjent"
        assert kinds["unnamed"] == "Skogs- og utmarkskoie, gamme"

    def test_outlines_are_reduced_to_points(self, tmp_path, buildings):
        source = n50.Source(cache_dir=str(tmp_path))

        with patch.object(source, "load_layers", return_value=buildings):
            cabins = source.load_cabins(["1824"])

        assert cabins.geometry.geom_type.unique().tolist() == ["Point"]
        assert cabins.crs.to_epsg() == 4326

    def test_reads_both_building_layers(self, tmp_path, buildings):
        source = n50.Source(cache_dir=str(tmp_path))

        with patch.object(source, "load_layers", return_value=buildings) as mock_load:
            source.load_cabins(["1824"])

        assert mock_load.call_args.args[1] == n50.BUILDING_LAYERS


class TestLoadFerries:
    """Tests for Source.load_ferries."""

    def test_keeps_only_ferry_types(self, tmp_path, transport_with_ferries):
        source = n50.Source(cache_dir=str(tmp_path))

        with patch.object(source, "load_transport", return_value=transport_with_ferries):
            ferries = source.load_ferries(["1824"])

        assert sorted(ferries["typeveg"]) == ["bilferje", "passasjerferje"]
        assert ferries.crs.to_epsg() == 4326

    def test_custom_ferry_types_are_respected(self, tmp_path, transport_with_ferries):
        source = n50.Source(cache_dir=str(tmp_path))

        with patch.object(source, "load_transport", return_value=transport_with_ferries):
            ferries = source.load_ferries(["1824"], road_types=("bilferje",))

        assert ferries["typeveg"].tolist() == ["bilferje"]


class TestLoadPaths:
    """Tests for filtering the transport network down to walkable ways."""

    def test_keeps_only_walkable_road_types(self, tmp_path, transport):
        source = n50.Source(cache_dir=str(tmp_path))

        with patch.object(source, "load_transport", return_value=transport.to_crs("EPSG:4326")):
            paths = source.load_paths(["1824"])

        assert sorted(paths["typeveg"]) == ["sti", "traktorveg"]
        assert paths.crs.to_epsg() == 4326

    def test_custom_road_types_are_respected(self, tmp_path, transport):
        source = n50.Source(cache_dir=str(tmp_path))

        with patch.object(source, "load_transport", return_value=transport.to_crs("EPSG:4326")):
            paths = source.load_paths(["1824"], road_types=("sti",))

        assert paths["typeveg"].tolist() == ["sti"]

    def test_ferries_are_excluded_from_paths(self, tmp_path, transport_with_ferries):
        source = n50.Source(cache_dir=str(tmp_path))

        with patch.object(source, "load_transport", return_value=transport_with_ferries):
            paths = source.load_paths(["1824"])

        assert "bilferje" not in set(paths["typeveg"])

    def test_transport_result_is_cached_per_municipality_set(self, tmp_path, transport):
        source = n50.Source(cache_dir=str(tmp_path))
        source.cache.save(f"n50_{n50.TRANSPORT_LAYER}_1813-1824", transport.to_crs("EPSG:4326"))

        with patch.object(source, "fetch") as mock_fetch:
            # Order must not matter: the cache key is built from sorted codes.
            result = source.load_transport(["1824", "1813"])

        mock_fetch.assert_not_called()
        assert len(result) == 3
