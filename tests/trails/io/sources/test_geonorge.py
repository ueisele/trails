"""Tests for Geonorge/Kartverket trail data loader."""

from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import Mock, patch

import geopandas as gpd
import pandas as pd
import pytest

from trails.io import cache
from trails.io.sources.geonorge import TURRUTEBASEN_METADATA, Metadata, Source, TrailData
from trails.io.sources.language import Language

# Test data constants for error cases
ATOM_FEED_NO_NATIONWIDE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <entry>
        <title>FGDB-format, Oslo</title>
        <link href="https://example.com/Friluftsliv_0301_Oslo_25833_TurOgFriluftsruter_FGDB.zip"/>
    </entry>
</feed>"""

ATOM_FEED_MULTIPLE_NATIONWIDE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <entry>
        <title>FGDB-format, Landsdekkende</title>
        <link rel="alternate" href="https://example.com/old.zip"/>
        <updated>2025-09-17T05:31:27</updated>
    </entry>
    <entry>
        <title>FGDB-format, Landsdekkende</title>
        <link rel="alternate" href="https://example.com/new.zip"/>
        <updated>2025-09-18T05:31:27</updated>
    </entry>
</feed>"""

ATOM_FEED_MALFORMED = "not valid xml <>"


def create_test_geodataframe(num_features=10, crs="EPSG:25833"):
    """Create a simple test GeoDataFrame with line geometries."""
    from shapely.geometry import LineString

    geometries = [LineString([(0, i), (1, i), (2, i)]) for i in range(num_features)]

    # Use real columns from our schema to avoid warnings
    data = {
        "lokalid": [f"trail_{i}" for i in range(num_features)],  # string column from schema
        "rutenavn": [f"Trail_{i}" for i in range(num_features)],  # string column from schema
    }
    # Add a code column with cycling values
    gradering_values = ["G", "B", "R", "S"]
    data["gradering"] = [gradering_values[i % len(gradering_values)] for i in range(num_features)]

    return gpd.GeoDataFrame(
        data,
        geometry=geometries,
        crs=crs,
    )


def create_test_dataframe(num_rows=10):
    """Create a simple test DataFrame (non-spatial)."""
    # Use real columns from our schema to avoid warnings
    return pd.DataFrame(
        {
            "ruteinfoid": [f"info_{i}" for i in range(num_rows)],  # string column from schema
            "informasjon": [f"Description_{i}" for i in range(num_rows)],  # string column from schema
        }
    )


class TestTrailData:
    """Tests for the TrailData dataclass."""

    def test_init_with_valid_spatial_layers(self):
        """Single CRS across all layers succeeds."""
        spatial_layers = {
            "layer1": create_test_geodataframe(5, "EPSG:25833"),
            "layer2": create_test_geodataframe(3, "EPSG:25833"),
        }
        attribute_tables = {
            "table1": create_test_dataframe(5),
        }

        trail_data = TrailData(
            metadata=TURRUTEBASEN_METADATA,
            spatial_layers=spatial_layers,
            attribute_tables=attribute_tables,
            source_url="http://example.com/data.zip",
            version="2025-01-01",
            language=Language.NO,
        )

        assert trail_data.crs == "EPSG:25833"
        assert len(trail_data.spatial_layers) == 2
        assert len(trail_data.attribute_tables) == 1

    def test_init_with_multiple_crs_raises_error(self):
        """Different CRS in layers should fail with ValueError."""
        spatial_layers = {
            "layer1": create_test_geodataframe(5, "EPSG:25833"),
            "layer2": create_test_geodataframe(3, "EPSG:4326"),  # Different CRS!
        }

        with pytest.raises(ValueError, match="Inconsistent CRS"):
            TrailData(
                metadata=TURRUTEBASEN_METADATA,
                spatial_layers=spatial_layers,
                attribute_tables={},
                source_url="http://example.com/data.zip",
                version="2025-01-01",
                language=Language.NO,
            )

    def test_init_without_spatial_layers_raises_error(self):
        """No spatial layers should fail."""
        with pytest.raises(ValueError, match="No spatial layers"):
            TrailData(
                metadata=TURRUTEBASEN_METADATA,
                spatial_layers={},
                attribute_tables={"table1": create_test_dataframe()},
                source_url="http://example.com/data.zip",
                version="2025-01-01",
                language=Language.NO,
            )

    def test_init_with_empty_spatial_layers_raises_error(self):
        """Empty dict should fail."""
        with pytest.raises(ValueError, match="No spatial layers"):
            TrailData(
                metadata=TURRUTEBASEN_METADATA,
                spatial_layers={},
                attribute_tables={},
                source_url="http://example.com/data.zip",
                version="2025-01-01",
                language=Language.NO,
            )

    def test_init_with_none_crs_in_layer_raises_error(self):
        """Layer without CRS should fail."""
        # Create GeoDataFrame without CRS
        gdf = create_test_geodataframe(5, None)

        with pytest.raises(ValueError, match="No spatial layers with CRS"):
            TrailData(
                metadata=TURRUTEBASEN_METADATA,
                spatial_layers={"layer1": gdf},
                attribute_tables={},
                source_url="http://example.com/data.zip",
                version="2025-01-01",
                language=Language.NO,
            )

    def test_crs_auto_detection_epsg_format(self):
        """Verify CRS formatted as 'EPSG:25833'."""
        spatial_layers = {
            "layer1": create_test_geodataframe(5, "EPSG:25833"),
        }

        trail_data = TrailData(
            metadata=TURRUTEBASEN_METADATA,
            spatial_layers=spatial_layers,
            attribute_tables={},
            source_url="http://example.com/data.zip",
            version="2025-01-01",
            language=Language.NO,
        )

        assert trail_data.crs == "EPSG:25833"
        assert trail_data.crs.startswith("EPSG:")

    def test_frozen_dataclass_immutability(self):
        """Verify fields can't be modified after creation."""
        trail_data = TrailData(
            metadata=TURRUTEBASEN_METADATA,
            spatial_layers={"layer1": create_test_geodataframe(1)},
            attribute_tables={},
            source_url="http://example.com/data.zip",
            version="2025-01-01",
            language=Language.NO,
        )

        # Try to modify a field
        with pytest.raises(FrozenInstanceError):
            trail_data.source_url = "http://new-url.com"

    def test_total_features_count(self):
        """Sum of spatial + attribute table features."""
        spatial_layers = {
            "layer1": create_test_geodataframe(10),
            "layer2": create_test_geodataframe(5),
        }
        attribute_tables = {
            "table1": create_test_dataframe(20),
            "table2": create_test_dataframe(15),
        }

        trail_data = TrailData(
            metadata=TURRUTEBASEN_METADATA,
            spatial_layers=spatial_layers,
            attribute_tables=attribute_tables,
            source_url="http://example.com/data.zip",
            version="2025-01-01",
            language=Language.NO,
        )

        assert trail_data.total_features == 50  # 10 + 5 + 20 + 15

    def test_layer_names_complete_list(self):
        """All layer names combined correctly."""
        spatial_layers = {
            "spatial1": create_test_geodataframe(1),
            "spatial2": create_test_geodataframe(1),
        }
        attribute_tables = {
            "attr1": create_test_dataframe(1),
            "attr2": create_test_dataframe(1),
        }

        trail_data = TrailData(
            metadata=TURRUTEBASEN_METADATA,
            spatial_layers=spatial_layers,
            attribute_tables=attribute_tables,
            source_url="http://example.com/data.zip",
            version="2025-01-01",
            language=Language.NO,
        )

        assert set(trail_data.layer_names) == {"spatial1", "spatial2", "attr1", "attr2"}
        assert len(trail_data.layer_names) == 4

    def test_spatial_layer_names(self):
        """Returns only spatial layer names."""
        trail_data = TrailData(
            metadata=TURRUTEBASEN_METADATA,
            spatial_layers={
                "fotrute": create_test_geodataframe(1),
                "skiloype": create_test_geodataframe(1),
            },
            attribute_tables={
                "info": create_test_dataframe(1),
            },
            source_url="http://example.com/data.zip",
            version="2025-01-01",
            language=Language.NO,
        )

        assert trail_data.spatial_layer_names == ["fotrute", "skiloype"]

    def test_attribute_table_names(self):
        """Returns only attribute table names."""
        trail_data = TrailData(
            metadata=TURRUTEBASEN_METADATA,
            spatial_layers={
                "fotrute": create_test_geodataframe(1),
            },
            attribute_tables={
                "info1": create_test_dataframe(1),
                "info2": create_test_dataframe(1),
            },
            source_url="http://example.com/data.zip",
            version="2025-01-01",
            language=Language.NO,
        )

        assert trail_data.attribute_table_names == ["info1", "info2"]

    def test_get_full_metadata_includes_all_fields(self):
        """All expected metadata fields present."""
        trail_data = TrailData(
            metadata=TURRUTEBASEN_METADATA,
            spatial_layers={"layer1": create_test_geodataframe(1)},
            attribute_tables={"table1": create_test_dataframe(1)},
            source_url="http://example.com/data.zip",
            version="2025-01-01",
            language=Language.NO,
        )

        full_metadata = trail_data.get_full_metadata()

        # Check all expected fields are present
        expected_fields = [
            "source_name",
            "provider",
            "dataset",
            "dataset_id",
            "license",
            "attribution",
            "catalog_url",
            "description",
            "source_url",
            "version",
            "crs",
            "total_features",
            "spatial_layers",
            "attribute_tables",
            "spatial_layer_count",
            "attribute_table_count",
        ]

        for field in expected_fields:
            assert field in full_metadata

    def test_crs_fallback_to_string(self):
        """Test CRS fallback to string representation when EPSG code extraction fails."""

        # Create a GeoDataFrame with a mock CRS that doesn't have to_epsg
        gdf = create_test_geodataframe(1, "EPSG:25833")

        # Mock the CRS to make to_epsg() return None
        with patch.object(type(gdf.crs), "to_epsg", return_value=None):
            spatial_layers = {"layer1": gdf}

            trail_data = TrailData(
                metadata=TURRUTEBASEN_METADATA,
                spatial_layers=spatial_layers,
                attribute_tables={},
                source_url="http://example.com/data.zip",
                version="2025-01-01",
                language=Language.NO,
            )

            # Should fallback to string representation when EPSG code not available
            assert trail_data.crs == str(gdf.crs)  # Verify actual CRS string
            assert isinstance(trail_data.crs, str)
            # CRS string should contain coordinate system info
            assert "proj" in trail_data.crs.lower() or "epsg" in trail_data.crs.lower()

    def test_get_full_metadata_dynamic_values(self):
        """Correct counts, lists, and calculated values."""
        spatial_layers = {
            "layer1": create_test_geodataframe(10),
            "layer2": create_test_geodataframe(5),
        }
        attribute_tables = {
            "table1": create_test_dataframe(8),
        }

        trail_data = TrailData(
            metadata=TURRUTEBASEN_METADATA,
            spatial_layers=spatial_layers,
            attribute_tables=attribute_tables,
            source_url="http://example.com/data.zip",
            version="2025-01-01",
            language=Language.NO,
        )

        full_metadata = trail_data.get_full_metadata()

        assert full_metadata["total_features"] == 23  # 10 + 5 + 8
        assert full_metadata["spatial_layer_count"] == 2
        assert full_metadata["attribute_table_count"] == 1
        assert full_metadata["spatial_layers"] == ["layer1", "layer2"]
        assert full_metadata["attribute_tables"] == ["table1"]
        assert full_metadata["crs"] == "EPSG:25833"
        assert full_metadata["version"] == "2025-01-01"


class TestMetadata:
    """Tests for the Metadata dataclass."""

    def test_catalog_url_construction(self):
        """Verify URL format."""
        metadata = Metadata(
            dataset_id="test-id-123",
            dataset_name="TestDataset",
            atom_feed_url="http://example.com/feed.xml",
            description="Test dataset",
        )

        expected_url = "https://kartkatalog.geonorge.no/metadata/testdataset/test-id-123"
        assert metadata.catalog_url == expected_url


class TestSource:
    """Tests for the main Source class."""

    def test_init_creates_cache_instances(self, tmp_path):
        """Both Object and Download caches created."""
        cache_dir = tmp_path / "test_cache"
        source = Source(cache_dir=str(cache_dir))

        assert isinstance(source.cache, cache.Object)
        assert isinstance(source.download_cache, cache.Download)

        # Check directories were created
        assert (cache_dir / "objects").exists()
        assert (cache_dir / "downloads").exists()

    def test_init_with_custom_cache_dir(self, tmp_path):
        """Custom directory path propagated correctly."""
        custom_dir = tmp_path / "custom" / "cache"
        source = Source(cache_dir=str(custom_dir))

        assert source.cache.cache_dir == custom_dir / "objects"
        assert source.download_cache.cache_dir == custom_dir / "downloads"

    @patch("trails.io.sources.geonorge.feedparser.parse")
    def test_get_download_info_valid_feed(self, mock_parse):
        """Extract correct nationwide FGDB URL."""
        # Mock feedparser response
        mock_parse.return_value = Mock(
            bozo=False,
            entries=[
                {
                    "title": "FGDB-format, Landsdekkende",
                    "updated": "2025-09-18T05:31:27",
                    "links": [
                        {
                            "href": "https://example.com/Friluftsliv_0000_Norge_25833_TurOgFriluftsruter_FGDB.zip",
                            "rel": "alternate",
                        }
                    ],
                },
                {
                    "title": "FGDB-format, Oslo",
                    "updated": "2025-09-18T05:31:27",
                    "links": [{"href": "https://example.com/oslo_FGDB.zip", "rel": "alternate"}],
                },
            ],
        )

        source = Source()
        result = source._get_download_info()

        assert result.url == "https://example.com/Friluftsliv_0000_Norge_25833_TurOgFriluftsruter_FGDB.zip"
        assert result.title == "FGDB-format, Landsdekkende"
        assert result.updated == "2025-09-18T05:31:27"

    @patch("trails.io.sources.geonorge.feedparser.parse")
    def test_get_download_info_no_entries(self, mock_parse):
        """Handle empty feed gracefully."""
        mock_parse.return_value = Mock(bozo=False, entries=[])

        source = Source()
        with pytest.raises(ValueError, match="No entries found"):
            source._get_download_info()

    @patch("trails.io.sources.geonorge.feedparser.parse")
    def test_get_download_info_no_nationwide_entry(self, mock_parse):
        """Error when no Landsdekkende/0000 entry."""
        mock_parse.return_value = Mock(
            bozo=False,
            entries=[{"title": "FGDB-format, Oslo", "links": [{"href": "https://example.com/oslo.zip"}]}],
        )

        source = Source()
        with pytest.raises(ValueError, match="Could not find nationwide"):
            source._get_download_info()

    @patch("trails.io.sources.geonorge.feedparser.parse")
    def test_get_download_info_multiple_nationwide_entries(self, mock_parse):
        """Choose most recent by updated date."""
        mock_parse.return_value = Mock(
            bozo=False,
            entries=[
                {
                    "title": "FGDB-format, Landsdekkende",
                    "updated": "2025-09-17T05:31:27",  # Older
                    "links": [{"href": "https://example.com/old_FGDB.zip", "rel": "alternate"}],
                },
                {
                    "title": "FGDB-format, Landsdekkende",
                    "updated": "2025-09-18T05:31:27",  # Newer
                    "links": [{"href": "https://example.com/new_FGDB.zip", "rel": "alternate"}],
                },
            ],
        )

        source = Source()
        result = source._get_download_info()

        assert result.url == "https://example.com/new_FGDB.zip"
        assert result.updated == "2025-09-18T05:31:27"

    def test_find_gdb_in_simple_zip(self, tmp_path):
        """Find .gdb folder in root."""
        import zipfile

        # Create a test ZIP with .gdb folder
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("TestData.gdb/file1.txt", "content")
            zf.writestr("TestData.gdb/file2.txt", "content")
            zf.writestr("readme.txt", "readme")

        source = Source()
        result = source._find_gdb_in_zip(zip_path)

        assert result == "TestData.gdb"

    def test_find_gdb_in_nested_zip(self, tmp_path):
        """Find .gdb in subdirectory."""
        import zipfile

        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/TestData.gdb/file1.txt", "content")
            zf.writestr("data/TestData.gdb/file2.txt", "content")

        source = Source()
        result = source._find_gdb_in_zip(zip_path)

        assert result == "data/TestData.gdb"

    def test_no_gdb_raises_error(self, tmp_path):
        """FileNotFoundError when .gdb missing."""
        import zipfile

        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("file1.txt", "content")
            zf.writestr("file2.txt", "content")

        source = Source()
        with pytest.raises(FileNotFoundError, match="No .gdb folder"):
            source._find_gdb_in_zip(zip_path)

    @patch("trails.io.sources.geonorge.gpd.list_layers")
    @patch("trails.io.sources.geonorge.gpd.read_file")
    def test_load_fgdb_spatial_vs_attribute_separation(self, mock_read, mock_list, tmp_path):
        """Correctly separate spatial and attribute layers."""
        # Mock layer listing
        mock_list.return_value = pd.DataFrame(
            {
                "name": ["fotrute_senterlinje", "fotruteinfo_tabell"],
                "geometry_type": ["Line String", "None"],
            }
        )

        # Mock reading layers
        def read_side_effect(path, layer=None):
            if layer == "fotrute_senterlinje":
                return create_test_geodataframe(5)
            else:
                return pd.DataFrame({"ruteinfoid": ["info_1", "info_2", "info_3"]})

        mock_read.side_effect = read_side_effect

        # Create a dummy zip file
        import zipfile

        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("Test.gdb/dummy", "content")

        source = Source()
        spatial_layers, attribute_tables = source._load_fgdb_from_zip(zip_path)

        assert "fotrute_senterlinje" in spatial_layers
        assert "fotruteinfo_tabell" in attribute_tables
        assert isinstance(spatial_layers["fotrute_senterlinje"], gpd.GeoDataFrame)
        assert isinstance(attribute_tables["fotruteinfo_tabell"], pd.DataFrame)

    @patch("trails.io.sources.geonorge.gpd.list_layers")
    @patch("trails.io.sources.geonorge.gpd.read_file")
    def test_load_fgdb_crs_conversion(self, mock_read, mock_list, tmp_path):
        """Apply target_crs to all spatial layers."""
        mock_list.return_value = pd.DataFrame({"name": ["layer1", "layer2"], "geometry_type": ["Line String", "Point"]})

        # Mock GeoDataFrames with CRS conversion
        mock_gdf1 = create_test_geodataframe(5, "EPSG:25833")
        mock_gdf1_converted = create_test_geodataframe(5, "EPSG:4326")
        mock_gdf1.to_crs = Mock(return_value=mock_gdf1_converted)

        mock_gdf2 = create_test_geodataframe(3, "EPSG:25833")
        mock_gdf2_converted = create_test_geodataframe(3, "EPSG:4326")
        mock_gdf2.to_crs = Mock(return_value=mock_gdf2_converted)

        def read_side_effect(path, layer=None):
            if layer == "layer1":
                return mock_gdf1
            else:
                return mock_gdf2

        mock_read.side_effect = read_side_effect

        # Create dummy zip
        import zipfile

        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("Test.gdb/dummy", "content")

        source = Source()
        spatial_layers, _ = source._load_fgdb_from_zip(zip_path, target_crs="EPSG:4326")

        # Verify CRS conversion was called
        mock_gdf1.to_crs.assert_called_once_with("EPSG:4326")
        mock_gdf2.to_crs.assert_called_once_with("EPSG:4326")

    @patch("trails.io.cache.requests")
    @patch("trails.io.sources.geonorge.feedparser.parse")
    def test_cache_fallback_on_error(self, mock_parse, mock_requests, tmp_path):
        """Use cache if download/parse fails."""
        # Setup cache with existing data
        source = Source(cache_dir=str(tmp_path))

        # Create cached TrailData
        cached_data = TrailData(
            metadata=TURRUTEBASEN_METADATA,
            spatial_layers={"layer1": create_test_geodataframe(1)},
            attribute_tables={},
            source_url="http://cached.com/data.zip",
            version="cached-version",
            language=Language.NO,
        )
        source.cache.save("geonorge_turrutebasen", cached_data)

        # Make download fail
        mock_requests.get.side_effect = Exception("Network error")

        # Should return cached data
        result = source.load_turrutebasen()
        assert result.version == "cached-version"

    def test_load_with_target_crs(self, tmp_path):
        """Test loading with a target CRS creates different cache key."""
        source = Source(cache_dir=str(tmp_path))

        # Mock the download and FGDB loading
        with patch.object(source, "_get_download_info") as mock_info:
            mock_info.return_value = Mock(url="http://test.com/data.zip", title="Test Data", updated="2025-01-01")

            with patch.object(source.download_cache, "download") as mock_download:
                from trails.io.cache import DownloadResult

                mock_download.return_value = DownloadResult(path=Path(tmp_path / "test.zip"), was_downloaded=False, version="1.0")

                with patch.object(source, "_load_fgdb_from_zip") as mock_load:
                    mock_load.return_value = (
                        {"layer1": create_test_geodataframe(1, "EPSG:25833")},
                        {"table1": create_test_dataframe(1)},
                    )

                    # Load with target CRS
                    source.load_turrutebasen(target_crs="EPSG:4326")

                    # Verify the cache key includes CRS
                    expected_key = "geonorge_turrutebasen_epsg_4326"
                    assert source.cache.exists(expected_key)

                    # Verify target_crs was passed to load function
                    mock_load.assert_called_once()
                    call_args = mock_load.call_args
                    assert call_args[1]["target_crs"] == "EPSG:4326"

    def test_load_cached_data_when_zip_not_redownloaded(self, tmp_path):
        """Test that cached processed data is used when ZIP wasn't re-downloaded."""
        source = Source(cache_dir=str(tmp_path))

        # Create cached processed data
        cached_data = TrailData(
            metadata=TURRUTEBASEN_METADATA,
            spatial_layers={"cached": create_test_geodataframe(1)},
            attribute_tables={},
            source_url="http://cached.com/data.zip",
            version="cached-version",
            language=Language.NO,
        )
        source.cache.save("geonorge_turrutebasen", cached_data)

        with patch.object(source, "_get_download_info") as mock_info:
            mock_info.return_value = Mock(url="http://test.com/data.zip", title="Test Data", updated="2025-01-01")

            # download returns (path, False) - False means NOT re-downloaded
            with patch.object(source.download_cache, "download") as mock_download:
                from trails.io.cache import DownloadResult

                mock_download.return_value = DownloadResult(path=Path(tmp_path / "test.zip"), was_downloaded=False, version="1.0")

                # Should return cached data without processing
                with patch.object(source, "_load_fgdb_from_zip") as mock_load:
                    result = source.load_turrutebasen()

                    # Verify cached data was returned
                    assert result.version == "cached-version"
                    assert "cached" in result.spatial_layers

                    # Verify _load_fgdb_from_zip was NOT called
                    mock_load.assert_not_called()

    def test_clear_cache_on_fresh_download(self, tmp_path):
        """Test that processed cache is cleared when fresh data is downloaded."""
        source = Source(cache_dir=str(tmp_path))

        # Create old cached data
        old_cached = TrailData(
            metadata=TURRUTEBASEN_METADATA,
            spatial_layers={"old": create_test_geodataframe(1)},
            attribute_tables={},
            source_url="http://old.com/data.zip",
            version="old-version",
            language=Language.NO,
        )
        source.cache.save("geonorge_turrutebasen", old_cached)

        with patch.object(source, "_get_download_info") as mock_info:
            mock_info.return_value = Mock(url="http://test.com/data.zip", title="Test Data", updated="2025-01-01")

            # download returns DownloadResult with was_downloaded=True for fresh download
            with patch.object(source.download_cache, "download") as mock_download:
                from trails.io.cache import DownloadResult

                mock_download.return_value = DownloadResult(path=Path(tmp_path / "test.zip"), was_downloaded=True, version="new-version")

                with patch.object(source, "_load_fgdb_from_zip") as mock_load:
                    mock_load.return_value = ({"new": create_test_geodataframe(1)}, {})

                    result = source.load_turrutebasen()

                    # Verify new data was returned
                    assert "new" in result.spatial_layers
                    assert "old" not in result.spatial_layers

    def test_newer_version_triggers_redownload(self, tmp_path):
        """Test that newer version in ATOM feed triggers re-download even if file is cached."""
        source = Source(cache_dir=str(tmp_path))

        # Step 1: Initial download with version "2025-01-01"
        with patch.object(source, "_get_download_info") as mock_info:
            mock_info.return_value = Mock(
                url="http://test.com/data.zip",
                title="Test Data",
                updated="2025-01-01",  # Initial version
            )

            with patch.object(source.download_cache, "download") as mock_download:
                from trails.io.cache import DownloadResult

                # First call: Initial download
                mock_download.return_value = DownloadResult(path=Path(tmp_path / "test.zip"), was_downloaded=True, version="2025-01-01")

                with patch.object(source, "_load_fgdb_from_zip") as mock_load:
                    mock_load.return_value = ({"layer_v1": create_test_geodataframe(1)}, {})

                    result1 = source.load_turrutebasen()
                    assert "layer_v1" in result1.spatial_layers
                    assert result1.version == "2025-01-01"

        # Step 2: ATOM feed now reports newer version
        with patch.object(source, "_get_download_info") as mock_info:
            mock_info.return_value = Mock(
                url="http://test.com/data.zip",
                title="Test Data",
                updated="2025-02-01",  # NEWER version!
            )

            with patch.object(source.download_cache, "download") as mock_download:
                from trails.io.cache import DownloadResult

                # The download cache should be called with the new version
                # and should return was_downloaded=True (re-downloaded)
                mock_download.return_value = DownloadResult(
                    path=Path(tmp_path / "test.zip"),
                    was_downloaded=True,  # Should re-download due to version change
                    version="2025-02-01",
                )

                with patch.object(source, "_load_fgdb_from_zip") as mock_load:
                    mock_load.return_value = ({"layer_v2": create_test_geodataframe(2)}, {})

                    result2 = source.load_turrutebasen()

                    # Verify the download was called with the new version
                    mock_download.assert_called_once_with(
                        url="http://test.com/data.zip",
                        filename="turrutebasen.zip",  # Turrutebasen specific filename
                        version="2025-02-01",  # New version passed
                        force=False,
                    )

                    # Verify new data was loaded
                    assert "layer_v2" in result2.spatial_layers
                    assert "layer_v1" not in result2.spatial_layers
                    assert result2.version == "2025-02-01"

    @patch("trails.io.sources.geonorge.feedparser.parse")
    def test_get_download_info_with_feed_parse_error(self, mock_parse):
        """Test handling of feed parse errors."""
        # Make feedparser return a bozo feed (parse error)
        mock_parse.return_value = Mock(
            bozo=True,
            bozo_exception=Exception("XML parse error"),
            entries=[],  # Need entries for iteration
        )

        source = Source()
        with pytest.raises(ValueError, match="No entries found in ATOM feed"):
            source._get_download_info()

    def test_progress_callback_is_called(self, tmp_path):
        """Test that progress messages are printed during loading."""
        source = Source(cache_dir=str(tmp_path))

        # Since load_turrutebasen doesn't have progress_callback parameter,
        # we verify that downloading/loading messages are printed
        with patch.object(source, "_get_download_info") as mock_info:
            mock_info.return_value = Mock(url="http://test.com/data.zip", title="Test Data", updated="2025-01-01")

            with patch.object(source.download_cache, "download") as mock_download:
                from trails.io.cache import DownloadResult

                mock_download.return_value = DownloadResult(path=Path(tmp_path / "test.zip"), was_downloaded=True, version="1.0")

                with patch.object(source, "_load_fgdb_from_zip") as mock_load:
                    mock_load.return_value = ({"layer1": create_test_geodataframe(1)}, {})

                    # Capture print output to verify progress messages
                    import io
                    import sys

                    captured_output = io.StringIO()
                    sys.stdout = captured_output

                    try:
                        source.load_turrutebasen()
                        output = captured_output.getvalue()
                        # Verify some progress indication was shown
                        assert "Loading" in output or "FGDB" in output
                    finally:
                        sys.stdout = sys.__stdout__

    @patch("trails.io.sources.geonorge.gpd.list_layers")
    def test_load_fgdb_with_empty_layers_list(self, mock_list, tmp_path):
        """Test handling of FGDB with no layers."""
        import zipfile

        # Create a test ZIP with mock GDB
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("Test.gdb/dummy", "content")

        # Mock empty layers list
        mock_list.return_value = pd.DataFrame({"name": [], "geometry_type": []})

        source = Source()
        # Should raise ValueError when no layers found
        with pytest.raises(ValueError, match="No layers could be loaded from FGDB"):
            source._load_fgdb_from_zip(zip_path)


class TestIntegration:
    """End-to-end integration tests."""

    @patch("trails.io.cache.requests")
    def test_load_with_real_fixtures(self, mock_requests, geonorge_zip_fixture, geonorge_atom_fixture, tmp_path):
        """Test with real fixture files (if they exist)."""
        if not geonorge_zip_fixture.exists() or not geonorge_atom_fixture.exists():
            pytest.skip("Fixtures not found. Run 'command make fixtures' to generate them.")

        # Read real ATOM feed fixture
        with open(geonorge_atom_fixture) as f:
            atom_content = f.read()

        # Read real ZIP fixture
        with open(geonorge_zip_fixture, "rb") as f:
            zip_content = f.read()

        # Mock HTTP responses to return our fixture content
        mock_atom_response = Mock()
        mock_atom_response.text = atom_content
        mock_atom_response.raise_for_status = Mock()

        mock_zip_response = Mock()
        mock_zip_response.headers = {"content-length": str(len(zip_content))}
        mock_zip_response.iter_content = Mock(return_value=[zip_content[i : i + 8192] for i in range(0, len(zip_content), 8192)])
        mock_zip_response.raise_for_status = Mock()

        def get_side_effect(url, stream=False):
            if "ATOM" in url:
                return mock_atom_response
            else:
                return mock_zip_response

        mock_requests.get.side_effect = get_side_effect

        # Now test with real geopandas/GDAL processing
        # Capture stdout to verify progress messages
        import io
        import sys

        captured_output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured_output

        try:
            source = Source(cache_dir=str(tmp_path))
            trail_data = source.load_turrutebasen()

            # Get the captured output
            output = captured_output.getvalue()

            # Verify progress messages were shown
            assert "Fetching download URL" in output or "Loading" in output, "Should show progress about fetching/loading"
            assert "Download" in output or "Processing" in output or "FGDB" in output, "Should show progress about download/processing"

        finally:
            sys.stdout = old_stdout

        # Verify we got real data
        assert isinstance(trail_data, TrailData)
        assert trail_data.crs == "EPSG:25833"
        assert len(trail_data.spatial_layers) > 0

        # Check we have the expected layers (at minimum)
        assert "fotrute_senterlinje" in trail_data.spatial_layers or "ruteinfopunkt_posisjon" in trail_data.spatial_layers

        # Verify the data is actually loaded
        for _layer_name, gdf in trail_data.spatial_layers.items():
            assert isinstance(gdf, gpd.GeoDataFrame)
            assert len(gdf) > 0  # Should have some features

        # Verify non-spatial tables are loaded
        assert len(trail_data.attribute_tables) > 0, "Should have attribute tables"
        for table_name, df in trail_data.attribute_tables.items():
            assert isinstance(df, pd.DataFrame)
            assert len(df) > 0, f"Table {table_name} should have rows"
            assert "geometry" not in df.columns, f"Table {table_name} should not have geometry"


# Helper fixtures for tests
@pytest.fixture
def fixture_dir():
    """Path to test fixtures directory."""
    # Navigate to the fixtures directory from the test file location
    test_file = Path(__file__)  # tests/trails/io/sources/test_geonorge.py
    test_dir = test_file.parent  # tests/trails/io/sources/
    tests_root = test_dir.parent.parent.parent  # tests/
    return tests_root / "fixtures" / "trails" / "io" / "sources" / "geonorge"


@pytest.fixture
def geonorge_zip_fixture(fixture_dir):
    """Path to minimal FGDB ZIP fixture."""
    return fixture_dir / "turrutebasen_minimal.zip"


@pytest.fixture
def geonorge_atom_fixture(fixture_dir):
    """Path to ATOM feed fixture."""
    return fixture_dir / "turrutebasen_atom_feed.xml"
