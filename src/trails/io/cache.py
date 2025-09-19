"""Caching utilities for trail data."""

import hashlib
import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

import requests


class Object:
    """Cache for Python objects using pickle serialization."""

    def __init__(self, cache_dir: str = ".cache/objects"):
        """Initialize cache with specified directory.

        Args:
            cache_dir: Directory to store cached files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def exists(self, key: str) -> bool:
        """Check if cache key exists.

        Args:
            key: Cache key to check

        Returns:
            True if cached data exists
        """
        return (self.cache_dir / f"{key}.pkl").exists()

    def save(self, key: str, data: Any, metadata: dict | None = None) -> None:
        """Save data to cache using pickle.

        Args:
            key: Cache key for the data
            data: Data to cache (must be pickleable)
            metadata: Optional metadata about the cached data
        """
        # Save data with pickle
        with open(self.cache_dir / f"{key}.pkl", "wb") as f:
            pickle.dump(data, f)

        # Save metadata if provided
        if metadata is not None:
            metadata["cached_at"] = datetime.now().isoformat()
            with open(self.cache_dir / f"{key}.meta.json", "w") as f:
                json.dump(metadata, f, indent=2)

    def load(self, key: str) -> Any:
        """Load data from cache using pickle.

        Args:
            key: Cache key to load

        Returns:
            Cached data

        Raises:
            FileNotFoundError: If cache key doesn't exist
        """
        cache_file = self.cache_dir / f"{key}.pkl"
        if not cache_file.exists():
            raise FileNotFoundError(f"Cache key '{key}' not found")

        with open(cache_file, "rb") as f:
            return pickle.load(f)

    def get_metadata(self, key: str) -> dict[str, Any] | None:
        """Get metadata for cached data.

        Args:
            key: Cache key

        Returns:
            Metadata dict if exists, None otherwise
        """
        meta_file = self.cache_dir / f"{key}.meta.json"
        if meta_file.exists():
            with open(meta_file) as f:
                return dict(json.load(f))
        return None

    def get_path(self, key: str) -> Path:
        """Get path for raw file storage.

        Args:
            key: File/directory name

        Returns:
            Path object for the file/directory
        """
        return self.cache_dir / key

    def delete(self, key: str) -> None:
        """Delete a specific cache entry.

        Args:
            key: Cache key to delete
        """
        # Delete data file
        pkl_file = self.cache_dir / f"{key}.pkl"
        if pkl_file.exists():
            pkl_file.unlink()

        # Delete metadata file
        meta_file = self.cache_dir / f"{key}.meta.json"
        if meta_file.exists():
            meta_file.unlink()

    def clear(self, key: str | None = None) -> None:
        """Clear cache.

        Args:
            key: Specific key to clear, or None to clear all
        """
        if key:
            # Clear specific key (backwards compatibility)
            self.delete(key)
        else:
            # Clear all cache files
            for file in self.cache_dir.glob("*.pkl"):
                file.unlink()
            for file in self.cache_dir.glob("*.meta.json"):
                file.unlink()


class DownloadResult(NamedTuple):
    """Result from download operation."""

    path: Path
    was_downloaded: bool  # True if fresh download, False if cached
    version: str | None  # Version that was downloaded/cached


class Download:
    """Cache for downloaded files with versioning."""

    def __init__(self, cache_dir: str = ".cache/downloads"):
        """Initialize download cache.

        Args:
            cache_dir: Directory for storing downloaded files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def download(
        self, url: str, filename: str | None = None, version: str | None = None, force: bool = False
    ) -> DownloadResult:
        """Download a file if not cached or version changed.

        Args:
            url: URL to download from
            filename: Local filename (defaults to URL hash)
            version: Version identifier for cache invalidation
            force: Force re-download even if cached

        Returns:
            DownloadResult with path, download status, and version
        """
        # Generate filename from URL if not provided
        if filename is None:
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            filename = f"download_{url_hash}.dat"

        file_path = self.cache_dir / filename
        meta_path = file_path.with_suffix(file_path.suffix + ".meta.json")

        # Check if we need to download
        needs_download = force or not file_path.exists()

        if not needs_download and meta_path.exists():
            # Check version if provided
            with open(meta_path) as f:
                metadata = json.load(f)
            if version and metadata.get("version") != version:
                print(f"Version changed: {metadata.get('version')} → {version}")
                needs_download = True

        if needs_download:
            print(f"Downloading from {url}...")
            self._download_file(url, file_path)

            # Save metadata
            metadata = {
                "url": url,
                "version": version,
                "downloaded_at": datetime.now().isoformat(),
                "file_size": file_path.stat().st_size,
            }
            with open(meta_path, "w") as f:
                json.dump(metadata, f, indent=2)

            return DownloadResult(path=file_path, was_downloaded=True, version=version)
        else:
            print(f"Using cached file: {file_path}")

            # Get version from metadata if available
            cached_version = version
            if meta_path.exists():
                with open(meta_path) as f:
                    metadata = json.load(f)
                    cached_version = metadata.get("version", version)

            return DownloadResult(path=file_path, was_downloaded=False, version=cached_version)

    def _download_file(self, url: str, target_path: Path) -> None:
        """Download file with progress indicator.

        Args:
            url: URL to download
            target_path: Where to save the file
        """
        response = requests.get(url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0

        with open(target_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\rProgress: {progress:.1f}%", end="", flush=True)

        print()  # New line after progress

    def get_cached_file(self, filename: str) -> Path | None:
        """Get path to cached file if it exists.

        Args:
            filename: Name of the cached file

        Returns:
            Path to file if exists, None otherwise
        """
        file_path = self.cache_dir / filename
        return file_path if file_path.exists() else None

    def clear(self) -> None:
        """Clear all cached downloads."""
        for file in self.cache_dir.iterdir():
            if file.is_file():
                file.unlink()
        print(f"Cleared download cache: {self.cache_dir}")
