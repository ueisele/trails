"""Tests for the Stedsnavn (SSR) place-name source."""

from unittest.mock import patch

import geopandas as gpd
import pytest
from shapely.geometry import LineString, MultiPoint, Point
from trails.io.sources import stedsnavn


@pytest.fixture
def raw_places() -> gpd.GeoDataFrame:
    """Places in a metric CRS: a valley, a lake with duplicates, a peak, an unnamed one."""
    return gpd.GeoDataFrame(
        {
            "name": ["Eiterådalen", "Storvatnet", "Snøfjelltinden", None],
            "navneobjekttype": ["dal", "vann", "fjell", "dal"],
            "sortering": ["viktighetH", "viktighetC", "viktighetB", "viktighetC"],
            "kommune": ["1824", "1824", "1816", "1824"],
            "geometry": [
                # Three positions along a valley, two of them 10 m apart.
                MultiPoint([(400000, 7280000), (400000, 7288000), (400005, 7288005)]),
                # Two spellings sharing one position.
                MultiPoint([(410000, 7290000), (410001, 7290001)]),
                Point(390000, 7270000),
                Point(395000, 7275000),
            ],
        },
        crs="EPSG:25833",
    )


class TestImportanceRank:
    """Tests for the register's importance ordering."""

    def test_ranks_most_prominent_first(self):
        assert stedsnavn.importance_rank("viktighetA") < stedsnavn.importance_rank("viktighetC")
        assert stedsnavn.importance_rank("viktighetC") < stedsnavn.importance_rank("viktighetK")

    def test_unknown_values_rank_last(self):
        assert stedsnavn.importance_rank(None) == len(stedsnavn.IMPORTANCE_ORDER)
        assert stedsnavn.importance_rank("nonsense") == len(stedsnavn.IMPORTANCE_ORDER)


class TestExplodePositions:
    """Tests for turning multi-position places into label positions."""

    def test_collapses_positions_within_the_tolerance(self, raw_places):
        result = stedsnavn._explode_positions(raw_places, dedupe_m=50.0)

        valley = result[result["name"] == "Eiterådalen"]
        # The two positions 10 m apart become one; the distant one survives.
        assert len(valley) == 2

    def test_duplicate_spellings_collapse_to_one_label(self, raw_places):
        result = stedsnavn._explode_positions(raw_places, dedupe_m=50.0)

        assert len(result[result["name"] == "Storvatnet"]) == 1

    def test_records_how_many_positions_survived(self, raw_places):
        result = stedsnavn._explode_positions(raw_places, dedupe_m=50.0)

        positions = dict(zip(result["name"], result["positions"], strict=True))
        assert positions["Eiterådalen"] == 2
        assert positions["Storvatnet"] == 1
        assert positions["Snøfjelltinden"] == 1

    def test_unnamed_places_are_dropped(self, raw_places):
        result = stedsnavn._explode_positions(raw_places, dedupe_m=50.0)
        assert result["name"].notna().all()

    def test_output_is_points_only(self, raw_places):
        result = stedsnavn._explode_positions(raw_places, dedupe_m=50.0)
        assert result.geometry.geom_type.unique().tolist() == ["Point"]

    def test_a_larger_tolerance_merges_more(self, raw_places):
        coarse = stedsnavn._explode_positions(raw_places, dedupe_m=20000.0)
        assert len(coarse[coarse["name"] == "Eiterådalen"]) == 1

    def test_empty_input_returns_empty_frame(self):
        empty = gpd.GeoDataFrame({"name": [], "navneobjekttype": [], "sortering": [], "kommune": []}, geometry=[], crs="EPSG:25833")
        result = stedsnavn._explode_positions(empty, dedupe_m=50.0)

        assert len(result) == 0
        assert "positions" in result.columns


class TestLoadPlaces:
    """Tests for filtering and enrichment in load_places."""

    @pytest.fixture
    def cached(self, tmp_path, raw_places) -> stedsnavn.Source:
        """A source with a prepared cache entry, so no network is touched."""
        source = stedsnavn.Source(cache_dir=str(tmp_path))
        places = stedsnavn._explode_positions(raw_places, dedupe_m=50.0)
        places = places.rename(columns={"navneobjekttype": "kind", "sortering": "importance"})
        places["rank"] = places["importance"].map(stedsnavn.importance_rank)
        source.cache.save("ssr_places_1816-1824_50", gpd.GeoDataFrame(places.to_crs("EPSG:4326"), geometry="geometry", crs="EPSG:4326"))
        return source

    def test_reads_from_cache_without_ordering(self, cached):
        with patch.object(cached.orders, "fetch") as mock_fetch:
            result = cached.load_places(["1824", "1816"], name_types=None)

        mock_fetch.assert_not_called()
        assert len(result) == 4
        assert result.crs.to_epsg() == 4326

    def test_filters_by_feature_type(self, cached):
        result = cached.load_places(["1824", "1816"], name_types=("dal",))
        assert set(result["kind"]) == {"dal"}

    def test_rank_is_available_for_label_sizing(self, cached):
        result = cached.load_places(["1824", "1816"], name_types=("fjell",))
        assert result["rank"].iloc[0] == stedsnavn.importance_rank("viktighetB")


class TestLoadRoadNames:
    """Tests for load_road_names."""

    @pytest.fixture
    def roads(self) -> gpd.GeoDataFrame:
        """Two named roads as whole centerlines."""
        return gpd.GeoDataFrame(
            {
                "road_id": [10001, 10002],
                "name": ["Tveråvegen", "Tosenveien"],
                "importance": ["viktighetC", "viktighetB"],
                "rank": [2, 1],
                "kommune": ["1824", "1824"],
                "geometry": [LineString([(12.8, 65.4), (12.9, 65.45)]), LineString([(13.0, 65.5), (13.1, 65.55)])],
            },
            crs="EPSG:4326",
        )

    @pytest.fixture
    def cached(self, tmp_path, roads) -> stedsnavn.Source:
        """A source with a prepared cache entry, so no network is touched."""
        source = stedsnavn.Source(cache_dir=str(tmp_path))
        source.cache.save("ssr_roads2_1824", roads)
        return source

    def test_reads_from_cache_without_ordering(self, cached):
        with patch.object(cached.orders, "fetch") as mock_fetch:
            result = cached.load_road_names(["1824"])

        mock_fetch.assert_not_called()
        assert len(result) == 2
        assert result.crs.to_epsg() == 4326

    def test_carries_the_register_id_so_same_named_roads_stay_apart(self, cached):
        """A name cannot identify a road: "Havnegata" exists three times over in this area.

        The id is not unique across the frame either — a road crossing a municipal
        boundary appears in both extracts under one id, which is what reunites it.
        """
        result = cached.load_road_names(["1824"])

        assert result.groupby("name")["road_id"].nunique().max() == 1
        assert result["road_id"].nunique() == 2

    def test_keeps_whole_roads_rather_than_fragments(self, cached):
        """One feature per road is what makes it usable as a click target."""
        result = cached.load_road_names(["1824"])

        assert sorted(result["name"]) == ["Tosenveien", "Tveråvegen"]
        assert set(result.geometry.geom_type) <= {"LineString", "MultiLineString"}

    def test_force_download_bypasses_the_cache(self, cached, roads):
        with patch.object(cached.orders, "fetch", return_value={}) as mock_fetch:
            with pytest.raises((IndexError, ValueError)):
                cached.load_road_names(["1824"], force_download=True)

        mock_fetch.assert_called_once()
