"""Tests for geo module utilities."""

import math

import geopandas as gpd
import pandas as pd
import pytest
from pyproj import CRS
from shapely.geometry import LineString, MultiLineString, Point
from trails.utils.geo import (
    COMPASS_POINTS,
    attach_nearest,
    calculate_lengths_meters,
    compass_points,
    endpoint_bearings,
    merge_lines,
    thin_points,
)


class TestCalculateLengthsMeters:
    """Test calculate_lengths_meters function."""

    def test_empty_geodataframe(self):
        """Test with empty GeoDataFrame."""
        gdf = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        result = calculate_lengths_meters(gdf)
        assert isinstance(result, pd.Series)
        assert len(result) == 0

    def test_crs_already_in_meters_epsg25833(self):
        """Test with CRS already in meters (EPSG:25833 - Norwegian UTM)."""
        # Create sample lines in EPSG:25833 (already in meters)
        lines = [
            LineString([(500000, 7000000), (501000, 7000000)]),  # 1000m horizontal
            LineString([(500000, 7000000), (500000, 7001000)]),  # 1000m vertical
            LineString([(500000, 7000000), (500000, 7000500)]),  # 500m vertical
        ]
        gdf = gpd.GeoDataFrame(geometry=lines, crs="EPSG:25833")

        result = calculate_lengths_meters(gdf)

        assert isinstance(result, pd.Series)
        assert len(result) == 3
        assert pytest.approx(result.iloc[0], rel=1e-2) == 1000.0
        assert pytest.approx(result.iloc[1], rel=1e-2) == 1000.0
        assert pytest.approx(result.iloc[2], rel=1e-2) == 500.0

    def test_crs_already_in_meters_epsg32633(self):
        """Test with another meter-based CRS (EPSG:32633 - UTM Zone 33N)."""
        lines = [
            LineString([(600000, 5500000), (602000, 5500000)]),  # 2000m horizontal
            LineString([(600000, 5500000), (600000, 5503000)]),  # 3000m vertical
        ]
        gdf = gpd.GeoDataFrame(geometry=lines, crs="EPSG:32633")

        result = calculate_lengths_meters(gdf)

        assert len(result) == 2
        assert pytest.approx(result.iloc[0], rel=1e-2) == 2000.0
        assert pytest.approx(result.iloc[1], rel=1e-2) == 3000.0

    def test_crs_in_degrees_wgs84(self):
        """Test with WGS84 (degrees) that needs transformation."""
        # Create lines near Oslo, Norway
        lines = [
            LineString([(10.7, 59.9), (10.8, 59.9)]),  # Roughly E-W line
            LineString([(10.7, 59.9), (10.7, 60.0)]),  # Roughly N-S line
        ]
        gdf = gpd.GeoDataFrame(geometry=lines, crs="EPSG:4326")

        result = calculate_lengths_meters(gdf)

        assert isinstance(result, pd.Series)
        assert len(result) == 2
        # At 60°N, 0.1° longitude ≈ 5.5 km, 0.1° latitude ≈ 11.1 km
        assert 5000 < result.iloc[0] < 6000  # E-W line
        assert 11000 < result.iloc[1] < 12000  # N-S line

    def test_crs_in_degrees_different_location(self):
        """Test WGS84 at different latitude (affects distance calculations)."""
        # Near equator - distances should be different
        lines = [
            LineString([(0.0, 0.0), (0.1, 0.0)]),  # E-W at equator
            LineString([(0.0, 0.0), (0.0, 0.1)]),  # N-S at equator
        ]
        gdf = gpd.GeoDataFrame(geometry=lines, crs="EPSG:4326")

        result = calculate_lengths_meters(gdf)

        # At equator, 0.1° ≈ 11.1 km for both directions
        assert 11000 < result.iloc[0] < 11200  # E-W line
        assert 11000 < result.iloc[1] < 11200  # N-S line

    def test_mixed_geometry_lengths(self):
        """Test with various line lengths in meter-based CRS."""
        lines = [
            LineString([(0, 0), (100, 0)]),  # 100m
            LineString([(0, 0), (0, 250)]),  # 250m
            LineString([(0, 0), (300, 400)]),  # 500m (3-4-5 triangle)
            LineString([(0, 0), (1000, 0)]),  # 1000m
            LineString([(0, 0), (0, 0)]),  # 0m (zero-length)
        ]
        gdf = gpd.GeoDataFrame(geometry=lines, crs="EPSG:32633")

        result = calculate_lengths_meters(gdf)

        assert len(result) == 5
        assert pytest.approx(result.iloc[0], rel=1e-2) == 100.0
        assert pytest.approx(result.iloc[1], rel=1e-2) == 250.0
        assert pytest.approx(result.iloc[2], rel=1e-2) == 500.0
        assert pytest.approx(result.iloc[3], rel=1e-2) == 1000.0
        assert pytest.approx(result.iloc[4]) == 0.0

    def test_multiline_segments(self):
        """Test with multi-segment lines."""
        lines = [
            LineString([(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]),  # Square perimeter: 400m
            LineString([(0, 0), (50, 0), (100, 0)]),  # Straight line with midpoint: 100m
            LineString([(0, 0), (100, 0), (0, 0)]),  # There and back: 200m
        ]
        gdf = gpd.GeoDataFrame(geometry=lines, crs="EPSG:32633")

        result = calculate_lengths_meters(gdf)

        assert len(result) == 3
        assert pytest.approx(result.iloc[0], rel=1e-2) == 400.0
        assert pytest.approx(result.iloc[1], rel=1e-2) == 100.0
        assert pytest.approx(result.iloc[2], rel=1e-2) == 200.0

    def test_no_crs(self):
        """Test with GeoDataFrame without CRS (should return raw lengths)."""
        lines = [
            LineString([(0, 0), (100, 0)]),
            LineString([(0, 0), (0, 200)]),
        ]
        gdf = gpd.GeoDataFrame(geometry=lines)  # No CRS specified

        result = calculate_lengths_meters(gdf)

        assert isinstance(result, pd.Series)
        assert len(result) == 2
        # Should return raw geometry lengths without transformation
        assert result.iloc[0] == 100.0
        assert result.iloc[1] == 200.0

    def test_custom_crs_with_meters(self):
        """Test with custom projected CRS in meters."""
        # Custom Albers Equal Area for Norway
        custom_crs = CRS.from_proj4("+proj=aea +lat_1=60 +lat_2=68 +lat_0=64 +lon_0=14 +x_0=0 +y_0=0 +ellps=GRS80 +units=m +no_defs")

        lines = [
            LineString([(0, 0), (1000, 0)]),
            LineString([(0, 0), (0, 2000)]),
        ]
        gdf = gpd.GeoDataFrame(geometry=lines, crs=custom_crs)

        result = calculate_lengths_meters(gdf)

        # Should recognize meters and return direct lengths
        assert pytest.approx(result.iloc[0], rel=1e-2) == 1000.0
        assert pytest.approx(result.iloc[1], rel=1e-2) == 2000.0

    def test_performance_many_lines(self):
        """Test performance with many lines (should be fast)."""
        import numpy as np

        # Create 10000 random lines
        n_lines = 10000
        lines = []
        for _ in range(n_lines):
            x1, y1 = np.random.uniform(500000, 600000, 2)
            x2, y2 = np.random.uniform(7000000, 7100000, 2)
            lines.append(LineString([(x1, y1), (x2, y2)]))

        gdf = gpd.GeoDataFrame(geometry=lines, crs="EPSG:25833")

        # This should complete quickly (< 1 second)
        import time

        start = time.time()
        result = calculate_lengths_meters(gdf)
        duration = time.time() - start

        assert len(result) == n_lines
        assert duration < 1.0  # Should be much faster than individual calculations
        assert all(result > 0)  # All should have positive length

    def test_preserve_index(self):
        """Test that the function preserves the GeoDataFrame index."""
        lines = [
            LineString([(0, 0), (100, 0)]),
            LineString([(0, 0), (200, 0)]),
            LineString([(0, 0), (300, 0)]),
        ]
        # Custom index
        gdf = gpd.GeoDataFrame(geometry=lines, index=["trail_a", "trail_b", "trail_c"], crs="EPSG:32633")

        result = calculate_lengths_meters(gdf)

        assert list(result.index) == ["trail_a", "trail_b", "trail_c"]
        assert result["trail_a"] == 100.0
        assert result["trail_b"] == 200.0
        assert result["trail_c"] == 300.0

    def test_with_point_geometries_should_return_zero(self):
        """Test with point geometries (should return 0 length)."""
        points = [
            Point(100, 200),
            Point(300, 400),
        ]
        gdf = gpd.GeoDataFrame(geometry=points, crs="EPSG:32633")

        result = calculate_lengths_meters(gdf)

        # Points have no length
        assert result.iloc[0] == 0.0
        assert result.iloc[1] == 0.0

    def test_crs_without_axis_info(self):
        """Test with CRS that doesn't have axis_info (older pyproj versions)."""
        # Create a basic CRS without axis info
        lines = [
            LineString([(0, 0), (100, 0)]),
            LineString([(0, 0), (0, 200)]),
        ]

        # Use a CRS string that might not have axis_info in all pyproj versions
        gdf = gpd.GeoDataFrame(geometry=lines, crs="EPSG:2154")  # French Lambert

        result = calculate_lengths_meters(gdf)

        # Should handle gracefully and attempt UTM transformation
        assert isinstance(result, pd.Series)
        assert len(result) == 2
        assert result.iloc[0] > 0
        assert result.iloc[1] > 0

    @pytest.mark.parametrize(
        "epsg_code,expected_direct",
        [
            ("EPSG:25832", True),  # ETRS89 / UTM zone 32N (meters)
            ("EPSG:25833", True),  # ETRS89 / UTM zone 33N (meters)
            ("EPSG:32633", True),  # WGS 84 / UTM zone 33N (meters)
            ("EPSG:3857", True),  # Web Mercator (meters)
            ("EPSG:4326", False),  # WGS84 (degrees)
            ("EPSG:4258", False),  # ETRS89 (degrees)
        ],
    )
    def test_various_crs_handling(self, epsg_code, expected_direct):
        """Test that various CRS are handled correctly."""
        lines = [LineString([(0, 0), (100, 0)])]

        # For degree-based CRS, use appropriate coordinates
        if not expected_direct:
            lines = [LineString([(10, 60), (10.1, 60)])]

        gdf = gpd.GeoDataFrame(geometry=lines, crs=epsg_code)
        result = calculate_lengths_meters(gdf)

        assert isinstance(result, pd.Series)
        assert len(result) == 1
        assert result.iloc[0] > 0  # Should have positive length

    def test_single_line_consistency(self):
        """Test that a single line gives consistent results."""
        # Single line that's 1km long
        line = LineString([(500000, 7000000), (501000, 7000000)])
        gdf = gpd.GeoDataFrame(geometry=[line], crs="EPSG:25833")

        result1 = calculate_lengths_meters(gdf)
        result2 = calculate_lengths_meters(gdf)

        # Should give same result each time
        assert result1.iloc[0] == result2.iloc[0]
        assert pytest.approx(result1.iloc[0], rel=1e-6) == 1000.0


class TestAttachNearest:
    """Tests for attach_nearest."""

    @pytest.fixture
    def fragments(self) -> gpd.GeoDataFrame:
        """Three road fragments: two along one road, one far away."""
        return gpd.GeoDataFrame(
            {
                "vegkategori": ["P", "P", "K"],
                "geometry": [
                    LineString([(0, 0), (100, 0)]),
                    LineString([(100, 0), (200, 0)]),
                    LineString([(0, 5000), (100, 5000)]),
                ],
            },
            crs="EPSG:25833",
        )

    @pytest.fixture
    def named(self) -> gpd.GeoDataFrame:
        """One named road running along the first two fragments."""
        return gpd.GeoDataFrame(
            {"name": ["Tveråvegen"], "extra": ["viktighetC"], "geometry": [LineString([(0, 10), (200, 10)])]},
            crs="EPSG:25833",
        )

    def test_copies_the_name_onto_nearby_features(self, fragments, named):
        result = attach_nearest(fragments, named, {"name": "road_name"}, max_distance_m=25)

        assert result["road_name"].tolist()[:2] == ["Tveråvegen", "Tveråvegen"]

    def test_leaves_distant_features_empty(self, fragments, named):
        """A fragment with no counterpart must not borrow a far-away name."""
        result = attach_nearest(fragments, named, {"name": "road_name"}, max_distance_m=25)

        assert pd.isna(result["road_name"].iloc[2])

    def test_respects_the_distance_limit(self, fragments, named):
        result = attach_nearest(fragments, named, {"name": "road_name"}, max_distance_m=5)

        assert result["road_name"].isna().all()

    def test_keeps_the_input_columns_and_geometry(self, fragments, named):
        result = attach_nearest(fragments, named, {"name": "road_name"}, max_distance_m=25)

        assert result["vegkategori"].tolist() == ["P", "P", "K"]
        assert result.geometry.equals(fragments.geometry)
        assert result.crs == fragments.crs

    def test_renames_several_fields_at_once(self, fragments, named):
        result = attach_nearest(fragments, named, {"name": "road_name", "extra": "importance"}, max_distance_m=25)

        assert result["importance"].iloc[0] == "viktighetC"

    def test_one_row_per_input_even_when_several_tie(self, fragments):
        """sjoin_nearest emits a row per tied match; the result must not grow."""
        tied = gpd.GeoDataFrame(
            {"name": ["A", "B"], "geometry": [LineString([(0, 10), (200, 10)]), LineString([(0, -10), (200, -10)])]},
            crs="EPSG:25833",
        )
        result = attach_nearest(fragments, tied, {"name": "road_name"}, max_distance_m=25)

        assert len(result) == len(fragments)

    def test_reprojects_before_measuring(self, named):
        """Distances are metres, so a degree-based input must be projected first."""
        degrees = gpd.GeoDataFrame({"geometry": [LineString([(12.8, 65.4), (12.81, 65.4)])]}, crs="EPSG:4326")
        result = attach_nearest(degrees, named.to_crs("EPSG:4326"), {"name": "road_name"}, max_distance_m=25)

        assert len(result) == 1
        assert result.crs.to_epsg() == 4326

    def test_min_overlap_rejects_a_line_that_only_touches(self):
        """A side road at a junction is near the main road but not part of it."""
        junction = gpd.GeoDataFrame({"geometry": [LineString([(100, 0), (100, 400)])]}, crs="EPSG:25833")
        main = gpd.GeoDataFrame({"name": ["Tveråvegen"], "geometry": [LineString([(0, 10), (200, 10)])]}, crs="EPSG:25833")

        lenient = attach_nearest(junction, main, {"name": "road_name"}, max_distance_m=25)
        strict = attach_nearest(junction, main, {"name": "road_name"}, max_distance_m=25, min_overlap=0.5)

        assert lenient["road_name"].iloc[0] == "Tveråvegen"
        assert pd.isna(strict["road_name"].iloc[0])

    def test_min_overlap_keeps_a_line_that_runs_along(self, fragments, named):
        result = attach_nearest(fragments, named, {"name": "road_name"}, max_distance_m=25, min_overlap=0.5)

        assert result["road_name"].tolist()[:2] == ["Tveråvegen", "Tveråvegen"]

    def test_min_overlap_leaves_points_alone(self, named):
        """A point has no length to run along anything."""
        points = gpd.GeoDataFrame({"geometry": [Point(100, 12)]}, crs="EPSG:25833")

        result = attach_nearest(points, named, {"name": "road_name"}, max_distance_m=25, min_overlap=0.9)

        assert result["road_name"].iloc[0] == "Tveråvegen"

    def test_empty_input_gains_the_column(self, named):
        empty = gpd.GeoDataFrame({"vegkategori": []}, geometry=[], crs="EPSG:25833")
        result = attach_nearest(empty, named, {"name": "road_name"}, max_distance_m=25)

        assert "road_name" in result.columns
        assert len(result) == 0

    def test_empty_source_leaves_every_value_empty(self, fragments):
        empty = gpd.GeoDataFrame({"name": []}, geometry=[], crs="EPSG:25833")
        result = attach_nearest(fragments, empty, {"name": "road_name"}, max_distance_m=25)

        assert result["road_name"].isna().all()
        assert len(result) == len(fragments)


class TestMergeLines:
    """Tests for merge_lines."""

    def test_joins_touching_segments(self):
        gdf = gpd.GeoDataFrame(
            {"typeveg": ["sti", "sti"], "geometry": [LineString([(0, 0), (1, 1)]), LineString([(1, 1), (2, 2)])]},
            crs="EPSG:25833",
        )
        merged = merge_lines(gdf)

        assert len(merged) == 1
        assert merged.geometry.iloc[0].geom_type == "LineString"

    def test_leaves_disjoint_segments_separate(self):
        gdf = gpd.GeoDataFrame(
            {"geometry": [LineString([(0, 0), (1, 1)]), LineString([(5, 5), (6, 6)])]},
            crs="EPSG:25833",
        )
        assert len(merge_lines(gdf)) == 2

    def test_single_line_is_returned_unchanged(self):
        # unary_union of one line yields a bare LineString, which linemerge rejects.
        gdf = gpd.GeoDataFrame({"geometry": [LineString([(0, 0), (1, 1)])]}, crs="EPSG:25833")
        merged = merge_lines(gdf)

        assert len(merged) == 1
        assert merged.geometry.iloc[0].geom_type == "LineString"

    def test_group_by_keeps_the_attribute_and_merges_within_it(self):
        gdf = gpd.GeoDataFrame(
            {
                "typeveg": ["sti", "sti", "traktorveg"],
                "geometry": [LineString([(0, 0), (1, 1)]), LineString([(1, 1), (2, 2)]), LineString([(2, 2), (3, 3)])],
            },
            crs="EPSG:25833",
        )
        merged = merge_lines(gdf, group_by="typeveg")

        assert sorted(merged["typeveg"]) == ["sti", "traktorveg"]
        assert len(merged) == 2

    def test_total_length_is_preserved(self):
        gdf = gpd.GeoDataFrame(
            {"geometry": [LineString([(0, 0), (0, 10)]), LineString([(0, 10), (0, 25)])]},
            crs="EPSG:25833",
        )
        assert merge_lines(gdf).length.sum() == pytest.approx(gdf.length.sum())

    def test_empty_input_returns_empty_frame(self):
        gdf = gpd.GeoDataFrame({"typeveg": [], "geometry": []}, geometry="geometry", crs="EPSG:25833")
        merged = merge_lines(gdf, group_by="typeveg")

        assert len(merged) == 0
        assert "typeveg" in merged.columns

    def test_crs_is_preserved(self):
        gdf = gpd.GeoDataFrame({"geometry": [LineString([(0, 0), (1, 1)])]}, crs="EPSG:25833")
        assert merge_lines(gdf).crs.to_epsg() == 25833


class TestThinPoints:
    """Tests for thin_points."""

    @pytest.fixture
    def labels(self) -> gpd.GeoDataFrame:
        """Three positions of one valley plus one of another name."""
        return gpd.GeoDataFrame(
            {
                "name": ["Eiterådalen", "Eiterådalen", "Eiterådalen", "Sørvassdalen"],
                "rank": [7, 7, 7, 3],
                "geometry": [
                    Point(400000, 7280000),
                    Point(400000, 7281200),  # 1.2 km from the first
                    Point(400000, 7288400),  # 8.4 km from the first
                    Point(400000, 7280500),  # close, but a different name
                ],
            },
            crs="EPSG:25833",
        )

    def test_drops_positions_closer_than_the_spacing(self, labels):
        result = thin_points(labels, 3000.0, group_by="name")

        valley = result[result["name"] == "Eiterådalen"]
        assert len(valley) == 2

    def test_keeps_the_well_separated_extremes(self, labels):
        result = thin_points(labels, 3000.0, group_by="name")

        ys = sorted(result[result["name"] == "Eiterådalen"].geometry.y)
        assert ys == [7280000, 7288400]

    def test_grouping_keeps_different_names_independent(self, labels):
        # Sørvassdalen is 500 m from an Eiterådalen label but must survive.
        result = thin_points(labels, 3000.0, group_by="name")
        assert "Sørvassdalen" in set(result["name"])

    def test_without_grouping_nearby_names_compete(self, labels):
        result = thin_points(labels, 3000.0)
        assert len(result) < len(thin_points(labels, 3000.0, group_by="name"))

    def test_priority_decides_which_position_survives(self, labels):
        gdf = labels.copy()
        gdf.loc[1, "rank"] = 1  # the middle position becomes the important one
        result = thin_points(gdf, 3000.0, group_by="name", priority="rank")

        ys = sorted(result[result["name"] == "Eiterådalen"].geometry.y)
        assert 7281200 in ys

    def test_zero_spacing_is_a_no_op(self, labels):
        assert len(thin_points(labels, 0.0, group_by="name")) == len(labels)

    def test_empty_input_returns_empty(self):
        empty = gpd.GeoDataFrame({"name": []}, geometry=[], crs="EPSG:25833")
        assert len(thin_points(empty, 3000.0, group_by="name")) == 0

    def test_input_crs_and_columns_are_preserved(self, labels):
        result = thin_points(labels.to_crs("EPSG:4326"), 3000.0, group_by="name")

        assert result.crs.to_epsg() == 4326
        assert list(result.columns) == list(labels.columns)


class TestEndpointBearings:
    """Tests for endpoint_bearings."""

    def line(self, *coordinates: tuple[float, float]) -> gpd.GeoDataFrame:
        """One line through the given metric positions."""
        return gpd.GeoDataFrame(geometry=[LineString(coordinates)], crs="EPSG:25833")

    def test_north_is_zero(self):
        result = endpoint_bearings(self.line((400000, 7280000), (400000, 7281000)))
        assert result.iloc[0] == pytest.approx(0.0)

    def test_east_is_ninety(self):
        result = endpoint_bearings(self.line((400000, 7280000), (401000, 7280000)))
        assert result.iloc[0] == pytest.approx(90.0)

    def test_west_is_two_hundred_and_seventy(self):
        result = endpoint_bearings(self.line((400000, 7280000), (399000, 7280000)))
        assert result.iloc[0] == pytest.approx(270.0)

    def test_only_the_two_ends_count(self):
        """A chain wanders; the bearing is a simplification and stays one."""
        wandering = self.line((400000, 7280000), (390000, 7285000), (401000, 7280000))
        assert endpoint_bearings(wandering).iloc[0] == pytest.approx(90.0)

    def test_a_ring_has_no_bearing(self):
        ring = self.line((400000, 7280000), (401000, 7281000), (400000, 7280000))
        assert pd.isna(endpoint_bearings(ring).iloc[0])

    def test_a_multilinestring_is_measured_end_to_end(self):
        gdf = gpd.GeoDataFrame(
            geometry=[MultiLineString([[(400000, 7280000), (400500, 7280000)], [(400500, 7280000), (401000, 7280000)]])],
            crs="EPSG:25833",
        )
        assert endpoint_bearings(gdf).iloc[0] == pytest.approx(90.0)

    def test_measured_in_the_metric_crs_not_flat(self):
        """At 65° N a degree of longitude is 0.41 of one of latitude, so the
        same two ends give a different bearing taken flat — far enough apart to
        land in a different one of the eight points."""
        gdf = gpd.GeoDataFrame(geometry=[LineString([(13.0, 65.5), (13.5, 65.5 + 0.2)])], crs="EPSG:4326")
        flat = math.degrees(math.atan2(0.5, 0.2)) % 360

        measured = float(endpoint_bearings(gdf).iloc[0])
        assert flat == pytest.approx(68.2, abs=0.1)
        assert measured == pytest.approx(47.6, abs=0.5)
        assert compass_points(pd.Series([measured])).iloc[0] != compass_points(pd.Series([flat])).iloc[0]

    def test_an_empty_geometry_has_none(self):
        gdf = gpd.GeoDataFrame(geometry=[LineString(), LineString([(400000, 7280000), (401000, 7280000)])], crs="EPSG:25833")
        result = endpoint_bearings(gdf)

        assert pd.isna(result.iloc[0])
        assert result.iloc[1] == pytest.approx(90.0)

    def test_features_without_a_crs_are_refused(self):
        """The wrong answer here reads exactly like a right one: a lon/lat frame
        measured flat gives 68° where the ground gives 48°, which is a different
        compass point and no warning."""
        gdf = gpd.GeoDataFrame(geometry=[LineString([(13.0, 65.5), (13.5, 65.7)])])
        with pytest.raises(ValueError, match="no CRS"):
            endpoint_bearings(gdf)

    def test_empty_input_returns_empty(self):
        assert len(endpoint_bearings(gpd.GeoDataFrame(geometry=[], crs="EPSG:25833"))) == 0

    def test_the_index_is_kept(self):
        gdf = self.line((400000, 7280000), (401000, 7280000))
        gdf.index = pd.Index([7])
        assert list(endpoint_bearings(gdf).index) == [7]


class TestCompassPoints:
    """Tests for compass_points."""

    def test_names_each_octant(self):
        bearings = pd.Series([0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0])
        assert list(compass_points(bearings)) == list(COMPASS_POINTS)

    def test_rounds_to_the_nearest_point(self):
        assert list(compass_points(pd.Series([22.4, 22.6, 359.9]))) == ["N", "NE", "N"]

    def test_a_half_rounds_up_the_way_javascript_does(self):
        """floor(x + 0.5), not a rint: the panel in the page names the point
        from the same number with Math.round, and a rint rounds a half to even.
        Two of the boundaries are the ones where the two would part."""
        assert list(compass_points(pd.Series([22.5, 67.5, 112.5, 157.5]))) == ["NE", "E", "SE", "S"]

    def test_nothing_is_named_where_there_is_no_bearing(self):
        assert compass_points(pd.Series([float("nan")])).iloc[0] is None

    def test_empty_input_returns_empty(self):
        assert len(compass_points(pd.Series([], dtype="float64"))) == 0
