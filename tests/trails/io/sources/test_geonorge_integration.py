"""Integration tests for Geonorge source with real network calls.

These tests require network access and download real data from Geonorge.
They are marked with @pytest.mark.integration and are skipped by default.

To run integration tests:
    pytest -m integration

To run all tests including integration:
    pytest

To run all tests except integration:
    pytest -m "not integration"
"""

import tempfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest

from trails.io.sources.geonorge import Source, TrailData


@pytest.mark.integration
@pytest.mark.slow
class TestGeonorgeIntegration:
    """Integration tests with real Geonorge API and data downloads."""

    def test_full_download_and_processing_workflow(self):
        """Test the complete workflow with real network calls to Geonorge.

        This test:
        1. Downloads the real ATOM feed from Geonorge
        2. Downloads the actual Turrutebasen ZIP file (>100MB)
        3. Processes the FGDB data
        4. Validates the returned TrailData

        Note: This test may take several minutes due to download size.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source with temporary cache
            source = Source(cache_dir=tmpdir)

            print("\n=== Starting Geonorge Integration Test ===")
            print("This may take several minutes to download ~150MB...")

            # Load the real data
            result = source.load_turrutebasen()

            # Validate result structure
            assert isinstance(result, TrailData)
            assert result.metadata.dataset_name == "Turrutebasen"
            assert result.metadata.provider == "Kartverket (Norwegian Mapping Authority)"

            # Validate we have spatial layers
            assert len(result.spatial_layers) > 0
            assert "fotrute_senterlinje" in result.spatial_layers

            # Validate spatial layer content
            fotrute = result.spatial_layers["fotrute_senterlinje"]
            assert isinstance(fotrute, gpd.GeoDataFrame)
            assert len(fotrute) > 1000  # Should have many trails
            assert fotrute.crs is not None

            # Validate we have attribute tables
            assert len(result.attribute_tables) > 0

            # Check for expected attribute tables
            expected_tables = ["fotruteinfo_tabell", "annenruteinfo_tabell"]
            for table_name in expected_tables:
                if table_name in result.attribute_tables:
                    table = result.attribute_tables[table_name]
                    assert isinstance(table, pd.DataFrame)
                    assert len(table) > 0

            # Validate CRS is detected
            assert result.crs.startswith("EPSG:")

            # Validate metadata
            assert result.source_url.startswith("http")
            assert result.version is not None

            print(f"✓ Downloaded and processed {result.total_features} features")
            print(f"✓ Found {len(result.spatial_layers)} spatial layers")
            print(f"✓ Found {len(result.attribute_tables)} attribute tables")
            print(f"✓ CRS: {result.crs}")

            # Validate each individual layer is independently usable
            print("\nValidating individual layers:")
            for layer_name, gdf in result.spatial_layers.items():
                # Each layer should have valid CRS
                assert gdf.crs is not None
                if len(gdf) > 0:
                    # Can perform operations on individual layers
                    bounds = gdf.total_bounds
                    assert len(bounds) == 4
                    print(f"  - {layer_name}: {len(gdf):,} features")

    def test_caching_behavior_with_real_data(self):
        """Test that caching works correctly with real downloads."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Source(cache_dir=tmpdir)

            print("\n=== Testing Cache Behavior ===")

            # First load - will download
            print("First load (downloading)...")
            result1 = source.load_turrutebasen()
            version1 = result1.version

            # Second load - should use cache
            print("Second load (from cache)...")
            result2 = source.load_turrutebasen()

            # Both should return the same data
            assert result2.version == version1
            assert len(result2.spatial_layers) == len(result1.spatial_layers)
            assert result2.total_features == result1.total_features

            # Cache files should exist
            cache_dir = Path(tmpdir)
            pkl_files = list(cache_dir.glob("**/*.pkl"))
            assert len(pkl_files) > 0, "Processed data should be cached"

            zip_files = list(cache_dir.glob("**/*.zip"))
            assert len(zip_files) > 0, "Downloaded ZIP should be cached"

            print(f"✓ Cache contains {len(pkl_files)} processed files")
            print(f"✓ Cache contains {len(zip_files)} downloaded files")

    def test_coordinate_transformation_with_real_data(self):
        """Test CRS transformation with real data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Source(cache_dir=tmpdir)

            print("\n=== Testing CRS Transformation ===")

            # Load with default CRS (EPSG:25833)
            result_default = source.load_turrutebasen()
            default_crs = result_default.crs

            # Load with WGS84
            result_wgs84 = source.load_turrutebasen(target_crs="EPSG:4326")

            # Validate transformation
            assert result_wgs84.crs == "EPSG:4326"
            assert result_wgs84.crs != default_crs

            # Check that coordinates are in expected range for WGS84
            for name, gdf in result_wgs84.spatial_layers.items():
                if len(gdf) > 0 and gdf.geometry.notna().any():
                    bounds = gdf.total_bounds
                    # Norway roughly: lon 4-31°E, lat 58-71°N
                    assert -180 <= bounds[0] <= 180, f"Invalid longitude in {name}"
                    assert -90 <= bounds[1] <= 90, f"Invalid latitude in {name}"

                    # More specific for Norway
                    if bounds[0] > -180 and bounds[2] < 180:  # Valid bounds
                        assert bounds[0] >= 4, f"Longitude too far west for Norway in {name}"
                        assert bounds[2] <= 32, f"Longitude too far east for Norway in {name}"

            print(f"✓ Default CRS: {default_crs}")
            print(f"✓ Transformed CRS: {result_wgs84.crs}")
            print("✓ Coordinates are in valid WGS84 range")

    def test_atom_feed_parsing_with_real_endpoint(self):
        """Test parsing of the real ATOM feed from Geonorge."""
        source = Source()

        print("\n=== Testing ATOM Feed Parsing ===")

        # This calls the real ATOM feed endpoint
        download_info = source._get_download_info()

        # Validate the parsed info
        assert download_info is not None
        assert download_info.url.startswith("http")
        assert "zip" in download_info.url.lower()
        assert download_info.title is not None
        assert download_info.updated is not None

        from trails.io.sources.geonorge import TURRUTEBASEN_METADATA

        print(f"✓ Feed URL: {TURRUTEBASEN_METADATA.atom_feed_url}")
        print(f"✓ Download URL: {download_info.url}")
        print(f"✓ Title: {download_info.title}")
        print(f"✓ Updated: {download_info.updated}")


@pytest.mark.integration
def test_network_error_handling():
    """Test handling of network errors (using invalid URL)."""
    from unittest.mock import patch

    from trails.io.sources.geonorge import TURRUTEBASEN_METADATA

    source = Source()

    # Create modified metadata with invalid URL
    invalid_metadata = TURRUTEBASEN_METADATA.__replace__(
        atom_feed_url="http://invalid.example.com/nonexistent.xml"
    )

    # Patch the module-level metadata constant
    with patch("trails.io.sources.geonorge.TURRUTEBASEN_METADATA", invalid_metadata):
        # Should raise network-related error (ConnectionError, URLError, etc.)
        with pytest.raises((ConnectionError, OSError, ValueError)):
            source._get_download_info()
