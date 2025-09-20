"""Tests for geo module utilities."""

import geopandas as gpd
import pandas as pd
import pytest
from pyproj import CRS
from shapely.geometry import LineString, Point

from trails.utils.geo import calculate_lengths_meters


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
