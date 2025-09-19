"""Tests for cache implementations."""

import json
from dataclasses import dataclass
from unittest.mock import Mock, patch

import pytest

from trails.io import cache


@dataclass
class SampleDataclass:
    """Sample dataclass for testing complex object caching."""

    field1: str
    field2: int
    nested: dict = None


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Temporary directory for cache tests."""
    return tmp_path / "test_cache"


@pytest.fixture
def object_cache(temp_cache_dir):
    """Object cache instance with temp directory."""
    return cache.Object(str(temp_cache_dir / "objects"))


@pytest.fixture
def download_cache(temp_cache_dir):
    """Download cache instance with temp directory."""
    return cache.Download(str(temp_cache_dir / "downloads"))


@pytest.fixture
def sample_data():
    """Various test data types."""
    return {
        "simple_str": "test string",
        "simple_int": 42,
        "simple_list": [1, 2, 3],
        "simple_dict": {"key": "value", "number": 123},
        "complex": SampleDataclass(field1="test", field2=99, nested={"inner": "data"}),
        "nested_structure": {
            "level1": {"level2": {"level3": ["deep", "data"]}},
            "items": [{"id": i, "value": f"item_{i}"} for i in range(3)],
        },
    }


class TestObject:
    """Tests for Object cache class."""

    # Basic Operations
    def test_init_creates_directory(self, temp_cache_dir):
        """Verify cache directory is created on initialization."""
        cache_dir = temp_cache_dir / "objects"
        assert not cache_dir.exists()

        _ = cache.Object(str(cache_dir))
        assert cache_dir.exists()
        assert cache_dir.is_dir()

    def test_init_with_existing_directory(self, temp_cache_dir):
        """Ensure no error when directory exists."""
        cache_dir = temp_cache_dir / "objects"
        cache_dir.mkdir(parents=True)

        # Should not raise any exception
        obj_cache = cache.Object(str(cache_dir))
        assert obj_cache.cache_dir == cache_dir

    def test_custom_cache_directory(self, temp_cache_dir):
        """Test with non-default cache path."""
        custom_dir = temp_cache_dir / "custom" / "nested" / "cache"
        obj_cache = cache.Object(str(custom_dir))

        assert obj_cache.cache_dir == custom_dir
        assert custom_dir.exists()

    # Save/Load Cycle
    def test_save_and_load_simple_types(self, object_cache, sample_data):
        """Test with str, int, list, dict."""
        # String
        object_cache.save("test_str", sample_data["simple_str"])
        assert object_cache.load("test_str") == sample_data["simple_str"]

        # Integer
        object_cache.save("test_int", sample_data["simple_int"])
        assert object_cache.load("test_int") == sample_data["simple_int"]

        # List
        object_cache.save("test_list", sample_data["simple_list"])
        assert object_cache.load("test_list") == sample_data["simple_list"]

        # Dict
        object_cache.save("test_dict", sample_data["simple_dict"])
        assert object_cache.load("test_dict") == sample_data["simple_dict"]

    def test_save_and_load_complex_objects(self, object_cache, sample_data):
        """Test with dataclasses, custom classes, nested structures."""
        # Dataclass
        object_cache.save("test_dataclass", sample_data["complex"])
        loaded = object_cache.load("test_dataclass")
        assert loaded.field1 == sample_data["complex"].field1
        assert loaded.field2 == sample_data["complex"].field2
        assert loaded.nested == sample_data["complex"].nested

        # Nested structure
        object_cache.save("test_nested", sample_data["nested_structure"])
        loaded = object_cache.load("test_nested")
        assert loaded == sample_data["nested_structure"]

    def test_save_overwrites_existing(self, object_cache):
        """Verify overwriting existing cache entry works."""
        key = "test_overwrite"

        # Save initial value
        object_cache.save(key, "initial value")
        assert object_cache.load(key) == "initial value"

        # Overwrite with new value
        object_cache.save(key, "updated value")
        assert object_cache.load(key) == "updated value"

        # Overwrite with different type
        object_cache.save(key, {"type": "dict now"})
        assert object_cache.load(key) == {"type": "dict now"}

    def test_load_nonexistent_raises_error(self, object_cache):
        """FileNotFoundError for missing keys."""
        with pytest.raises(FileNotFoundError) as exc_info:
            object_cache.load("nonexistent_key")
        assert "nonexistent_key" in str(exc_info.value)

    # Metadata Handling
    def test_save_with_metadata(self, object_cache):
        """Verify metadata is saved correctly."""
        key = "test_metadata"
        data = {"some": "data"}
        metadata = {
            "source": "test",
            "version": "1.0",
            "count": 42,
        }

        object_cache.save(key, data, metadata=metadata)

        # Check metadata file exists
        meta_file = object_cache.cache_dir / f"{key}.meta.json"
        assert meta_file.exists()

        # Load and verify metadata
        saved_metadata = object_cache.get_metadata(key)
        assert saved_metadata["source"] == "test"
        assert saved_metadata["version"] == "1.0"
        assert saved_metadata["count"] == 42
        assert "cached_at" in saved_metadata  # Added automatically

    def test_save_without_metadata(self, object_cache):
        """Ensure works without metadata."""
        key = "test_no_metadata"
        data = {"some": "data"}

        object_cache.save(key, data)  # No metadata parameter

        # Data should be saved normally
        assert object_cache.load(key) == data

        # No metadata file should exist
        meta_file = object_cache.cache_dir / f"{key}.meta.json"
        assert not meta_file.exists()

    def test_get_metadata_existing(self, object_cache):
        """Retrieve metadata for cached object."""
        key = "test_get_metadata"
        metadata = {"field1": "value1", "field2": 123}

        object_cache.save(key, "data", metadata=metadata)

        retrieved = object_cache.get_metadata(key)
        assert retrieved["field1"] == "value1"
        assert retrieved["field2"] == 123

    def test_get_metadata_nonexistent(self, object_cache):
        """Returns None for missing metadata."""
        assert object_cache.get_metadata("nonexistent") is None

        # Even if data exists but metadata doesn't
        object_cache.save("data_only", "some data")
        assert object_cache.get_metadata("data_only") is None

    # Exists Checks
    def test_exists_for_existing_key(self, object_cache):
        """Returns True for cached data."""
        key = "test_exists"
        object_cache.save(key, "data")
        assert object_cache.exists(key) is True

    def test_exists_for_missing_key(self, object_cache):
        """Returns False for non-cached data."""
        assert object_cache.exists("missing_key") is False

    def test_exists_after_delete(self, object_cache):
        """Returns False after deletion."""
        key = "test_delete_exists"
        object_cache.save(key, "data")
        assert object_cache.exists(key) is True

        object_cache.delete(key)
        assert object_cache.exists(key) is False

    # Delete Operations
    def test_delete_existing_entry(self, object_cache):
        """Remove both .pkl and .meta.json files."""
        key = "test_delete"
        object_cache.save(key, "data", metadata={"test": "metadata"})

        # Files exist before delete
        pkl_file = object_cache.cache_dir / f"{key}.pkl"
        meta_file = object_cache.cache_dir / f"{key}.meta.json"
        assert pkl_file.exists()
        assert meta_file.exists()

        # Delete
        object_cache.delete(key)

        # Files removed after delete
        assert not pkl_file.exists()
        assert not meta_file.exists()

    def test_delete_nonexistent_entry(self, object_cache):
        """No error when deleting missing key."""
        # Should not raise any exception
        object_cache.delete("nonexistent_key")

    def test_delete_removes_files(self, object_cache):
        """Verify filesystem cleanup."""
        key = "test_cleanup"
        object_cache.save(key, {"data": "value"})

        # Verify file exists
        assert (object_cache.cache_dir / f"{key}.pkl").exists()

        # Delete and verify removed
        object_cache.delete(key)
        assert not (object_cache.cache_dir / f"{key}.pkl").exists()

        # Cannot load after delete
        with pytest.raises(FileNotFoundError):
            object_cache.load(key)

    # Clear Operations
    def test_clear_specific_key(self, object_cache):
        """Backwards compatibility with clear(key)."""
        key1 = "key1"
        key2 = "key2"
        object_cache.save(key1, "data1")
        object_cache.save(key2, "data2")

        # Clear specific key
        object_cache.clear(key1)

        # key1 removed, key2 remains
        assert not object_cache.exists(key1)
        assert object_cache.exists(key2)

    def test_clear_all_entries(self, object_cache):
        """Remove all cached files."""
        # Save multiple entries
        for i in range(5):
            object_cache.save(f"key_{i}", f"data_{i}", metadata={"index": i})

        # Verify all exist
        for i in range(5):
            assert object_cache.exists(f"key_{i}")

        # Clear all
        object_cache.clear()

        # Verify all removed
        for i in range(5):
            assert not object_cache.exists(f"key_{i}")

        # Cache directory should be empty (except the directory itself)
        files = list(object_cache.cache_dir.iterdir())
        assert len(files) == 0

    def test_clear_preserves_directory(self, object_cache):
        """Cache directory remains after clear."""
        object_cache.save("test", "data")
        cache_dir = object_cache.cache_dir

        object_cache.clear()

        # Directory still exists but is empty
        assert cache_dir.exists()
        assert cache_dir.is_dir()
        assert len(list(cache_dir.iterdir())) == 0

    # Utility Methods
    def test_get_path(self, object_cache):
        """Verify path construction for keys."""
        key = "test_key"
        expected_path = object_cache.cache_dir / key
        assert object_cache.get_path(key) == expected_path

    def test_get_path_special_characters(self, object_cache):
        """Handle keys with special chars."""
        # Test various special characters in keys
        special_keys = [
            "key_with_underscore",
            "key-with-dash",
            "key.with.dots",
            "key123numbers",
        ]

        for key in special_keys:
            path = object_cache.get_path(key)
            assert path == object_cache.cache_dir / key

            # Verify we can actually save/load with these keys
            object_cache.save(key, f"data_for_{key}")
            assert object_cache.load(key) == f"data_for_{key}"


class TestDownload:
    """Tests for Download cache class."""

    # Basic Operations
    def test_init_creates_directory(self, temp_cache_dir):
        """Verify download directory creation."""
        cache_dir = temp_cache_dir / "downloads"
        assert not cache_dir.exists()

        _ = cache.Download(str(cache_dir))
        assert cache_dir.exists()
        assert cache_dir.is_dir()

    def test_custom_download_directory(self, temp_cache_dir):
        """Test with non-default path."""
        custom_dir = temp_cache_dir / "custom_downloads"
        dl_cache = cache.Download(str(custom_dir))

        assert dl_cache.cache_dir == custom_dir
        assert custom_dir.exists()

    # Download Behavior
    @patch("trails.io.cache.requests")
    def test_download_new_file(self, mock_requests, download_cache):
        """Mock fresh download, verify was_downloaded=True."""
        mock_response = Mock()
        mock_response.headers = {"content-length": "100"}
        mock_response.iter_content.return_value = [
            b"chunk1",
            b"chunk2",
            b"chunk3",
        ]
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        result = download_cache.download("http://example.com/file.zip", "test.zip")

        assert result.was_downloaded is True
        assert result.path.exists()
        assert result.path.name == "test.zip"
        assert result.path.read_bytes() == b"chunk1chunk2chunk3"
        assert result.version is None  # No version specified

        # Verify metadata was created
        meta_path = result.path.with_suffix(".zip.meta.json")
        assert meta_path.exists()
        with open(meta_path) as f:
            metadata = json.load(f)
        assert metadata["url"] == "http://example.com/file.zip"
        assert metadata["file_size"] == 18  # len(b"chunk1chunk2chunk3")

    @patch("trails.io.cache.requests")
    def test_use_cached_file(self, mock_requests, download_cache):
        """Second call uses cache, was_downloaded=False."""
        mock_response = Mock()
        mock_response.headers = {"content-length": "100"}
        mock_response.iter_content.return_value = [b"data"]
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        # First download
        result1 = download_cache.download("http://example.com/file.zip", "cached.zip")
        assert result1.was_downloaded is True

        # Second call should use cache
        result2 = download_cache.download("http://example.com/file.zip", "cached.zip")
        assert result2.was_downloaded is False
        assert result2.path == result1.path

        # Verify requests.get was only called once
        mock_requests.get.assert_called_once()

    @patch("trails.io.cache.requests")
    def test_force_redownload(self, mock_requests, download_cache):
        """force=True triggers new download."""
        mock_response = Mock()
        mock_response.headers = {}
        mock_response.iter_content.return_value = [b"initial"]
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        # Initial download
        result1 = download_cache.download("http://example.com/file.zip", "forced.zip")
        assert result1.was_downloaded is True

        # Update mock to return different content
        mock_response.iter_content.return_value = [b"updated"]

        # Force redownload
        result2 = download_cache.download("http://example.com/file.zip", "forced.zip", force=True)
        assert result2.was_downloaded is True
        assert result2.path.read_bytes() == b"updated"

        # Verify requests.get was called twice
        assert mock_requests.get.call_count == 2

    @patch("trails.io.cache.requests")
    def test_auto_filename_from_url(self, mock_requests, download_cache):
        """No filename generates hash-based name."""
        mock_response = Mock()
        mock_response.headers = {}
        mock_response.iter_content.return_value = [b"content"]
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        # No filename provided
        result = download_cache.download("http://example.com/data.json")

        assert result.was_downloaded is True
        assert result.path.exists()
        # Should generate hash-based filename
        assert result.path.name.startswith("download_")
        assert result.path.name.endswith(".dat")

    @patch("trails.io.cache.requests")
    def test_custom_filename(self, mock_requests, download_cache):
        """Respects provided filename."""
        mock_response = Mock()
        mock_response.headers = {}
        mock_response.iter_content.return_value = [b"content"]
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        result = download_cache.download("http://example.com/data", filename="my_custom_file.txt")

        assert result.path.name == "my_custom_file.txt"

    # Version Management
    @patch("trails.io.cache.requests")
    def test_version_change_triggers_download(self, mock_requests, download_cache):
        """Different version causes re-download."""
        mock_response = Mock()
        mock_response.headers = {}
        mock_response.iter_content.return_value = [b"v1_content"]
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        # Download version 1
        result1 = download_cache.download(
            "http://example.com/file.zip", "versioned.zip", version="v1.0"
        )
        assert result1.was_downloaded is True
        assert result1.version == "v1.0"

        # Update mock for v2
        mock_response.iter_content.return_value = [b"v2_content"]

        # Download version 2 (should trigger new download)
        result2 = download_cache.download(
            "http://example.com/file.zip", "versioned.zip", version="v2.0"
        )
        assert result2.was_downloaded is True
        assert result2.version == "v2.0"
        assert result2.path.read_bytes() == b"v2_content"

        assert mock_requests.get.call_count == 2

    @patch("trails.io.cache.requests")
    def test_version_matches_uses_cache(self, mock_requests, download_cache):
        """Same version uses cached file."""
        mock_response = Mock()
        mock_response.headers = {}
        mock_response.iter_content.return_value = [b"content"]
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        # Download with version
        result1 = download_cache.download(
            "http://example.com/file.zip", "same_version.zip", version="v1.0"
        )
        assert result1.was_downloaded is True

        # Same version should use cache
        result2 = download_cache.download(
            "http://example.com/file.zip", "same_version.zip", version="v1.0"
        )
        assert result2.was_downloaded is False
        assert result2.version == "v1.0"

        # Only one actual download
        mock_requests.get.assert_called_once()

    @patch("trails.io.cache.requests")
    def test_no_version_basic_caching(self, mock_requests, download_cache):
        """Works without version parameter."""
        mock_response = Mock()
        mock_response.headers = {}
        mock_response.iter_content.return_value = [b"content"]
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        # Download without version
        result1 = download_cache.download("http://example.com/file.zip", "no_version.zip")
        assert result1.was_downloaded is True
        assert result1.version is None

        # Should still use cache on second call
        result2 = download_cache.download("http://example.com/file.zip", "no_version.zip")
        assert result2.was_downloaded is False
        assert result2.version is None

    @patch("trails.io.cache.requests")
    def test_version_in_result(self, mock_requests, download_cache):
        """DownloadResult contains correct version."""
        mock_response = Mock()
        mock_response.headers = {}
        mock_response.iter_content.return_value = [b"content"]
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        # With version
        result = download_cache.download(
            "http://example.com/file.zip", "test.zip", version="2024.1"
        )
        assert result.version == "2024.1"

        # Without version
        result = download_cache.download("http://example.com/file2.zip", "test2.zip")
        assert result.version is None

    # HTTP Handling
    @patch("trails.io.cache.requests")
    def test_download_with_progress(self, mock_requests, download_cache, capsys):
        """Content-length header shows progress."""
        mock_response = Mock()
        mock_response.headers = {"content-length": "100"}
        # 4 chunks of 25 bytes each = 100 bytes total
        mock_response.iter_content.return_value = [b"x" * 25] * 4
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        download_cache.download("http://example.com/file.zip", "progress.zip")

        captured = capsys.readouterr()
        # Should show progress
        assert "Progress:" in captured.out
        assert "100.0%" in captured.out

    @patch("trails.io.cache.requests")
    def test_download_without_content_length(self, mock_requests, download_cache, capsys):
        """Works without size info."""
        mock_response = Mock()
        mock_response.headers = {}  # No content-length
        mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        result = download_cache.download("http://example.com/file.zip", "no_size.zip")

        assert result.was_downloaded is True
        assert result.path.read_bytes() == b"chunk1chunk2"

        captured = capsys.readouterr()
        # Should not show percentage progress
        assert "100.0%" not in captured.out

    @patch("trails.io.cache.requests")
    def test_http_error_handling(self, mock_requests, download_cache):
        """404, 500 errors raise appropriately."""
        import requests as real_requests

        mock_response = Mock()
        mock_response.raise_for_status.side_effect = real_requests.HTTPError("404 Not Found")
        mock_requests.get.return_value = mock_response

        with pytest.raises(real_requests.HTTPError) as exc_info:
            download_cache.download("http://example.com/missing.zip")
        assert "404" in str(exc_info.value)

    @patch("trails.io.cache.requests")
    def test_network_error_handling(self, mock_requests, download_cache):
        """Connection errors handled gracefully."""
        import requests as real_requests

        mock_requests.get.side_effect = real_requests.ConnectionError("Connection refused")

        with pytest.raises(real_requests.ConnectionError) as exc_info:
            download_cache.download("http://example.com/file.zip")
        assert "Connection refused" in str(exc_info.value)

    @patch("trails.io.cache.requests")
    def test_chunked_download(self, mock_requests, download_cache):
        """Verify chunk-based download works."""
        mock_response = Mock()
        mock_response.headers = {"content-length": "30"}
        # Return chunks separately
        chunks = [b"chunk1-", b"chunk2-", b"chunk3"]
        mock_response.iter_content.return_value = chunks
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        result = download_cache.download("http://example.com/file.zip", "chunked.zip")

        # All chunks should be concatenated
        expected_content = b"".join(chunks)
        assert result.path.read_bytes() == expected_content

        # Verify stream=True was used
        mock_requests.get.assert_called_with("http://example.com/file.zip", stream=True)

    # Cache Management
    def test_get_cached_file_exists(self, download_cache):
        """Returns path for existing file."""
        # Create a test file
        test_file = download_cache.cache_dir / "test_file.zip"
        test_file.write_bytes(b"test content")

        result = download_cache.get_cached_file("test_file.zip")
        assert result == test_file
        assert result.exists()

    def test_get_cached_file_missing(self, download_cache):
        """Returns None for missing file."""
        result = download_cache.get_cached_file("nonexistent.zip")
        assert result is None

    @patch("trails.io.cache.requests")
    def test_clear_removes_all_files(self, mock_requests, download_cache):
        """All downloads and metadata removed."""
        mock_response = Mock()
        mock_response.headers = {}
        mock_response.iter_content.return_value = [b"content"]
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        # Download multiple files
        for i in range(3):
            download_cache.download(f"http://example.com/file{i}.zip", f"file{i}.zip")

        # Verify files exist
        assert len(list(download_cache.cache_dir.glob("*.zip"))) == 3
        assert len(list(download_cache.cache_dir.glob("*.meta.json"))) == 3

        # Clear cache
        download_cache.clear()

        # All files removed
        assert len(list(download_cache.cache_dir.iterdir())) == 0

    def test_clear_preserves_directory(self, download_cache):
        """Directory remains after clear."""
        # Add a test file
        test_file = download_cache.cache_dir / "test.txt"
        test_file.write_text("test")

        cache_dir = download_cache.cache_dir
        download_cache.clear()

        # Directory still exists but is empty
        assert cache_dir.exists()
        assert cache_dir.is_dir()
        assert len(list(cache_dir.iterdir())) == 0

    # Error Handling Edge Cases
    def test_corrupted_cache_file(self, object_cache):
        """Handle corrupted pickle files."""
        import pickle

        key = "corrupted"
        pkl_file = object_cache.cache_dir / f"{key}.pkl"

        # Write corrupted data
        pkl_file.write_bytes(b"this is not valid pickle data")

        # Should raise appropriate error
        with pytest.raises(pickle.UnpicklingError):
            object_cache.load(key)

    def test_unicode_in_metadata(self, object_cache):
        """Unicode characters in metadata."""
        key = "unicode_test"
        metadata = {
            "name": "测试数据",  # Chinese
            "emoji": "🚀🔥",
            "special": "äöü€",
        }

        object_cache.save(key, "data", metadata=metadata)

        loaded_meta = object_cache.get_metadata(key)
        assert loaded_meta["name"] == "测试数据"
        assert loaded_meta["emoji"] == "🚀🔥"
        assert loaded_meta["special"] == "äöü€"
