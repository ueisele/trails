"""Tests for the Overpass (OpenStreetMap) source."""

from unittest.mock import Mock, patch

import geopandas as gpd
import pytest
import requests
from trails.io.sources import overpass


@pytest.fixture
def ways_response() -> dict:
    """Overpass payload with two ways, one of them degenerate."""
    return {
        "elements": [
            {
                "type": "way",
                "id": 1001,
                "tags": {"highway": "path", "name": "Sjøbergmarsjen", "sac_scale": "mountain_hiking"},
                "geometry": [{"lat": 65.4, "lon": 12.8}, {"lat": 65.41, "lon": 12.81}],
            },
            {
                "type": "way",
                "id": 1002,
                "tags": {"highway": "track", "surface": "gravel"},
                "geometry": [{"lat": 65.5, "lon": 12.9}, {"lat": 65.51, "lon": 12.91}, {"lat": 65.52, "lon": 12.92}],
            },
            # Single-node way: not a usable line, must be dropped.
            {"type": "way", "id": 1003, "tags": {"highway": "path"}, "geometry": [{"lat": 65.6, "lon": 13.0}]},
        ]
    }


@pytest.fixture
def shelters_response() -> dict:
    """Overpass payload with a node hut and a way-based shelter with center."""
    return {
        "elements": [
            {"type": "node", "id": 2001, "lat": 65.45, "lon": 12.85, "tags": {"tourism": "wilderness_hut", "name": "Stavassgården"}},
            {"type": "way", "id": 2002, "center": {"lat": 65.46, "lon": 12.86}, "tags": {"amenity": "shelter", "name": "Gapahuken"}},
            # No coordinates at all: must be dropped.
            {"type": "node", "id": 2003, "tags": {"amenity": "shelter"}},
        ]
    }


@pytest.fixture
def places_response() -> dict:
    """Overpass payload with two named places and one unnamed node."""
    return {
        "elements": [
            {"type": "node", "id": 3001, "lat": 65.83, "lon": 13.19, "tags": {"place": "town", "name": "Mosjøen"}},
            {"type": "node", "id": 3002, "lat": 65.78, "lon": 13.17, "tags": {"place": "hamlet", "name": "Tverråga"}},
            # Unnamed place: no orientation value, must be dropped.
            {"type": "node", "id": 3003, "lat": 65.5, "lon": 12.9, "tags": {"place": "hamlet"}},
        ]
    }


def _mock_response(payload: dict) -> Mock:
    """Build a mock requests response returning the given payload."""
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class TestBboxConversion:
    """Tests for bounding box ordering."""

    def test_reorders_to_south_west_north_east(self):
        # GeoPandas order is (min_lon, min_lat, max_lon, max_lat).
        assert overpass._to_overpass_bbox((12.4, 65.3, 13.3, 65.7)) == "65.3,12.4,65.7,13.3"


class TestQuery:
    """Tests for mirror failover in Source.query."""

    def test_returns_payload_from_first_working_mirror(self, tmp_path, ways_response):
        source = overpass.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response(ways_response)) as mock_post:
            result = source.query("[out:json];out;")

        assert result == ways_response
        assert mock_post.call_count == 1

    def test_falls_back_to_next_mirror(self, tmp_path, ways_response):
        source = overpass.Source(cache_dir=str(tmp_path))
        failing = Mock()
        failing.raise_for_status.side_effect = requests.HTTPError("429 Too Many Requests")

        with patch("requests.post", side_effect=[failing, _mock_response(ways_response)]) as mock_post:
            result = source.query("[out:json];out;")

        assert result == ways_response
        assert mock_post.call_count == 2

    def test_retries_in_later_round_after_all_mirrors_fail(self, tmp_path, ways_response):
        source = overpass.Source(cache_dir=str(tmp_path), mirrors=("https://a", "https://b"), max_rounds=2, initial_backoff=0.0)
        failing = Mock()
        failing.raise_for_status.side_effect = requests.HTTPError("504 Gateway Timeout")

        with patch("requests.post", side_effect=[failing, failing, _mock_response(ways_response)]) as mock_post, patch("time.sleep") as mock_sleep:
            result = source.query("[out:json];out;")

        assert result == ways_response
        assert mock_post.call_count == 3
        mock_sleep.assert_called_once()

    def test_raises_when_all_rounds_exhausted(self, tmp_path):
        source = overpass.Source(cache_dir=str(tmp_path), mirrors=("https://a",), max_rounds=2, initial_backoff=0.0)
        failing = Mock()
        failing.raise_for_status.side_effect = requests.HTTPError("504 Gateway Timeout")

        with (
            patch("requests.post", return_value=failing),
            patch("time.sleep"),
            pytest.raises(overpass.OverpassError, match="All Overpass mirrors failed"),
        ):
            source.query("[out:json];out;")

    def test_payload_without_elements_is_treated_as_failure(self, tmp_path):
        source = overpass.Source(cache_dir=str(tmp_path), mirrors=("https://a",), max_rounds=1)

        with patch("requests.post", return_value=_mock_response({"version": 0.6})), pytest.raises(overpass.OverpassError):
            source.query("[out:json];out;")

    def test_sends_identifying_user_agent(self, tmp_path, ways_response):
        source = overpass.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response(ways_response)) as mock_post:
            source.query("[out:json];out;")

        assert mock_post.call_args.kwargs["headers"]["User-Agent"] == overpass.USER_AGENT


class TestFetchPaths:
    """Tests for Source.fetch_paths."""

    def test_builds_linestrings_and_drops_degenerate_ways(self, tmp_path, ways_response):
        source = overpass.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response(ways_response)):
            gdf = source.fetch_paths((12.4, 65.3, 13.3, 65.7))

        assert isinstance(gdf, gpd.GeoDataFrame)
        assert len(gdf) == 2
        assert gdf.crs.to_epsg() == 4326
        assert set(gdf["osm_id"]) == {1001, 1002}
        assert gdf.geometry.geom_type.unique().tolist() == ["LineString"]

    def test_extracts_tags(self, tmp_path, ways_response):
        source = overpass.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response(ways_response)):
            gdf = source.fetch_paths((12.4, 65.3, 13.3, 65.7))

        row = gdf[gdf["osm_id"] == 1001].iloc[0]
        assert row["name"] == "Sjøbergmarsjen"
        assert row["sac_scale"] == "mountain_hiking"
        assert row["highway"] == "path"

    def test_highway_filter_appears_in_query(self, tmp_path, ways_response):
        source = overpass.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response(ways_response)) as mock_post:
            source.fetch_paths((12.4, 65.3, 13.3, 65.7), highway_types=("path", "track"))

        sent = mock_post.call_args.kwargs["data"].decode("utf-8")
        assert "^(path|track)$" in sent
        assert "65.3,12.4,65.7,13.3" in sent

    def test_second_call_uses_cache(self, tmp_path, ways_response):
        source = overpass.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response(ways_response)) as mock_post:
            source.fetch_paths((12.4, 65.3, 13.3, 65.7))
            source.fetch_paths((12.4, 65.3, 13.3, 65.7))

        assert mock_post.call_count == 1

    def test_it_says_when_what_it_served_was_read(self, tmp_path, ways_response):
        """Overpass publishes no version of the extract it answers from, so an
        exported file records when the answer was read. A cache hit has to
        answer too, or a rebuilt map records nothing for a source it used."""
        source = overpass.Source(cache_dir=str(tmp_path))
        assert source.loaded_at is None

        with patch("requests.post", return_value=_mock_response(ways_response)):
            source.fetch_paths((12.4, 65.3, 13.3, 65.7))
            fetched = source.loaded_at
            source.fetch_paths((12.4, 65.3, 13.3, 65.7))

        assert fetched is not None
        assert fetched.startswith("20")
        assert source.loaded_at == fetched

    def test_different_bbox_is_cached_separately(self, tmp_path, ways_response):
        source = overpass.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response(ways_response)) as mock_post:
            source.fetch_paths((12.4, 65.3, 13.3, 65.7))
            source.fetch_paths((10.0, 60.0, 11.0, 61.0))

        assert mock_post.call_count == 2

    def test_empty_result_keeps_schema(self, tmp_path):
        source = overpass.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response({"elements": []})):
            gdf = source.fetch_paths((12.4, 65.3, 13.3, 65.7))

        assert len(gdf) == 0
        assert "highway" in gdf.columns
        assert gdf.crs.to_epsg() == 4326


class TestFetchShelters:
    """Tests for Source.fetch_shelters."""

    def test_reads_node_and_way_center_coordinates(self, tmp_path, shelters_response):
        source = overpass.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response(shelters_response)):
            gdf = source.fetch_shelters((12.4, 65.3, 13.3, 65.7))

        assert len(gdf) == 2
        assert set(gdf["osm_id"]) == {2001, 2002}
        assert gdf.geometry.geom_type.unique().tolist() == ["Point"]

    def test_kind_falls_back_from_tourism_to_amenity(self, tmp_path, shelters_response):
        source = overpass.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response(shelters_response)):
            gdf = source.fetch_shelters((12.4, 65.3, 13.3, 65.7))

        kinds = dict(zip(gdf["osm_id"], gdf["kind"], strict=True))
        assert kinds[2001] == "wilderness_hut"
        assert kinds[2002] == "shelter"


class TestFetchFerryTerminals:
    """Tests for Source.fetch_ferry_terminals."""

    @pytest.fixture
    def terminals_response(self) -> dict:
        """A node quay, the same quay mapped as a pier way, and an unnamed one."""
        return {
            "elements": [
                {"type": "node", "id": 4001, "lat": 65.72, "lon": 12.85, "tags": {"amenity": "ferry_terminal", "name": "Bønå hurtigbåtkai"}},
                {
                    "type": "way",
                    "id": 4002,
                    "center": {"lat": 65.7201, "lon": 12.8501},
                    "tags": {"amenity": "ferry_terminal", "name": "Bønå hurtigbåtkai"},
                },
                {"type": "node", "id": 4003, "lat": 65.60, "lon": 12.70, "tags": {"amenity": "ferry_terminal"}},
                {
                    "type": "node",
                    "id": 4004,
                    "lat": 65.50,
                    "lon": 12.60,
                    "tags": {"amenity": "ferry_terminal", "name": "Horn ferjekai", "operator": "Torghatten"},
                },
            ]
        }

    def test_drops_unnamed_quays(self, tmp_path, terminals_response):
        source = overpass.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response(terminals_response)):
            gdf = source.fetch_ferry_terminals((12.4, 65.3, 13.3, 65.8))

        assert 4003 not in set(gdf["osm_id"])

    def test_deduplicates_a_quay_mapped_twice(self, tmp_path, terminals_response):
        source = overpass.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response(terminals_response)):
            gdf = source.fetch_ferry_terminals((12.4, 65.3, 13.3, 65.8))

        # The node and the pier way describe the same quay.
        assert sorted(gdf["name"]) == ["Bønå hurtigbåtkai", "Horn ferjekai"]

    def test_records_operator(self, tmp_path, terminals_response):
        source = overpass.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response(terminals_response)):
            gdf = source.fetch_ferry_terminals((12.4, 65.3, 13.3, 65.8))

        assert gdf.set_index("name").loc["Horn ferjekai", "operator"] == "Torghatten"

    def test_second_call_uses_cache(self, tmp_path, terminals_response):
        source = overpass.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response(terminals_response)) as mock_post:
            source.fetch_ferry_terminals((12.4, 65.3, 13.3, 65.8))
            source.fetch_ferry_terminals((12.4, 65.3, 13.3, 65.8))

        assert mock_post.call_count == 1


class TestSelectorCaching:
    """Widening a selector set must not read back a narrower cached result."""

    def test_shelters_are_cached_per_selector_set(self, tmp_path, shelters_response):
        source = overpass.Source(cache_dir=str(tmp_path))
        narrow = ('node["amenity"="shelter"]',)
        wide = ('node["amenity"="shelter"]', 'way["amenity"="shelter"]')

        with patch("requests.post", return_value=_mock_response(shelters_response)) as mock_post:
            source.fetch_shelters((12.4, 65.3, 13.3, 65.7), selectors=narrow)
            source.fetch_shelters((12.4, 65.3, 13.3, 65.7), selectors=wide)
            source.fetch_shelters((12.4, 65.3, 13.3, 65.7), selectors=narrow)

        assert mock_post.call_count == 2

    def test_digest_is_stable_and_distinguishes_sets(self):
        first = ('node["amenity"="shelter"]',)
        second = ('way["amenity"="shelter"]',)

        assert overpass._selector_digest(first) == overpass._selector_digest(first)
        assert overpass._selector_digest(first) != overpass._selector_digest(second)


class TestFetchPlaces:
    """Tests for Source.fetch_places."""

    def test_returns_named_places_only(self, tmp_path, places_response):
        source = overpass.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response(places_response)):
            gdf = source.fetch_places((12.4, 65.3, 13.3, 65.7))

        assert set(gdf["osm_id"]) == {3001, 3002}
        assert gdf.geometry.geom_type.unique().tolist() == ["Point"]

    def test_records_place_kind(self, tmp_path, places_response):
        source = overpass.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response(places_response)):
            gdf = source.fetch_places((12.4, 65.3, 13.3, 65.7))

        kinds = dict(zip(gdf["name"], gdf["kind"], strict=True))
        assert kinds["Mosjøen"] == "town"
        assert kinds["Tverråga"] == "hamlet"

    def test_place_filter_appears_in_query(self, tmp_path, places_response):
        source = overpass.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response(places_response)) as mock_post:
            source.fetch_places((12.4, 65.3, 13.3, 65.7), place_types=("farm", "isolated_dwelling"))

        sent = mock_post.call_args.kwargs["data"].decode("utf-8")
        assert "^(farm|isolated_dwelling)$" in sent
        assert '["name"]' in sent

    def test_place_types_are_cached_separately(self, tmp_path, places_response):
        source = overpass.Source(cache_dir=str(tmp_path))

        with patch("requests.post", return_value=_mock_response(places_response)) as mock_post:
            source.fetch_places((12.4, 65.3, 13.3, 65.7), place_types=("town",))
            source.fetch_places((12.4, 65.3, 13.3, 65.7), place_types=("farm",))
            source.fetch_places((12.4, 65.3, 13.3, 65.7), place_types=("town",))

        assert mock_post.call_count == 2
