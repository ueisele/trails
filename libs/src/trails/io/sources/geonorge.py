"""
Geonorge (Kartverket) data source loader.
Norwegian government's official mapping authority data.
"""

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple, TypeVar

import feedparser
import geopandas as gpd
import pandas as pd

from trails.io import cache
from trails.io.sources import geonorge_codes, geonorge_schema, geonorge_translations
from trails.io.sources.language import Language

# TypeVar for DataFrame types
T = TypeVar("T", gpd.GeoDataFrame, pd.DataFrame)


class AtomFeedEntry(NamedTuple):
    """Dataset entry from Geonorge ATOM feed."""

    url: str
    title: str
    updated: str  # ISO format string


@dataclass(frozen=True)
class Metadata:
    """Static metadata for a Geonorge dataset."""

    dataset_id: str
    dataset_name: str
    atom_feed_url: str
    base_url: str = "https://kartkatalog.geonorge.no"
    source_name: str = "Geonorge"
    provider: str = "Kartverket (Norwegian Mapping Authority)"
    license: str = "CC BY 4.0"
    attribution: str = "© Kartverket"
    description: str = ""

    @property
    def catalog_url(self) -> str:
        """URL to the dataset in Geonorge catalog."""
        return f"{self.base_url}/metadata/{self.dataset_name.lower()}/{self.dataset_id}"


@dataclass(frozen=True)
class TrailData:
    """Loaded trail data with metadata."""

    metadata: Metadata
    spatial_layers: dict[str, gpd.GeoDataFrame]  # Spatial geometry layers
    attribute_tables: dict[str, pd.DataFrame]  # Non-spatial attribute tables
    source_url: str  # The actual download URL from ATOM feed
    version: str  # Current version from ATOM feed
    language: Language  # Language used for code expansion and translation
    crs: str = field(init=False)  # Auto-detected from spatial layers

    def __post_init__(self) -> None:
        """Validate and set CRS from spatial layers."""
        # Collect all CRSs from spatial layers
        crs_set = set()
        for _name, gdf in self.spatial_layers.items():
            if hasattr(gdf, "crs") and gdf.crs is not None:
                # Use to_authority() for consistent format (e.g., "EPSG:25833")
                if hasattr(gdf.crs, "to_authority"):
                    auth = gdf.crs.to_authority()
                    if auth:
                        crs_set.add(f"{auth[0]}:{auth[1]}")
                    else:
                        # Fallback to string representation
                        crs_set.add(str(gdf.crs))
                else:
                    crs_set.add(str(gdf.crs))

        if not crs_set:
            raise ValueError("No spatial layers with CRS found in TrailData")

        if len(crs_set) > 1:
            raise ValueError(f"Inconsistent CRS across spatial layers: {crs_set}. All spatial layers must have the same CRS.")

        # Set the single CRS (frozen=True requires using object.__setattr__)
        object.__setattr__(self, "crs", crs_set.pop())

    @property
    def total_features(self) -> int:
        """Total number of features across all layers and tables."""
        spatial_count = sum(len(gdf) for gdf in self.spatial_layers.values())
        table_count = sum(len(df) for df in self.attribute_tables.values())
        return spatial_count + table_count

    @property
    def layer_names(self) -> list[str]:
        """List of all layer names (spatial and attribute)."""
        return self.spatial_layer_names + self.attribute_table_names

    @property
    def spatial_layer_names(self) -> list[str]:
        """List of spatial layer names."""
        return list(self.spatial_layers.keys())

    @property
    def attribute_table_names(self) -> list[str]:
        """List of attribute table names."""
        return list(self.attribute_tables.keys())

    def get_description(self, column: str, value: str) -> str | None:
        """Get description for a value in the data's language.

        This method performs a reverse lookup to find the code from the value,
        then returns the description for that code.

        Args:
            column: Column name (e.g., "gradering" or "difficulty")
            value: Expanded value (e.g., "Enkel (Grønn)" or "Easy (Green)")

        Returns:
            Description in the data's language, or None if not found

        Example:
            # Norwegian data
            desc = data.get_description("gradering", "Enkel (Grønn)")
            # Returns Norwegian description for difficulty level G

            # English data
            desc = data.get_description("gradering", "Easy (Green)")
            # Returns English description for difficulty level G
        """
        # Get the code from the value
        code = geonorge_codes.get_code(column, value, self.language)
        if code is None:
            return None

        # Get the description for the code
        return geonorge_codes.get_description(column, code, self.language)

    def get_full_metadata(self) -> dict:
        """Combine static and dynamic metadata."""
        return {
            # Static from metadata object
            "source_name": self.metadata.source_name,
            "provider": self.metadata.provider,
            "dataset": self.metadata.dataset_name,
            "dataset_id": self.metadata.dataset_id,
            "license": self.metadata.license,
            "attribution": self.metadata.attribution,
            "catalog_url": self.metadata.catalog_url,
            "description": self.metadata.description,
            # Dynamic instance data
            "source_url": self.source_url,
            "version": self.version,
            "language": self.language.value,
            "crs": self.crs,
            "total_features": self.total_features,
            "spatial_layers": self.spatial_layer_names,
            "attribute_tables": self.attribute_table_names,
            "spatial_layer_count": len(self.spatial_layers),
            "attribute_table_count": len(self.attribute_tables),
        }


# Metadata for Turrutebasen dataset
TURRUTEBASEN_METADATA = Metadata(
    dataset_id="d1422d17-6d95-4ef1-96ab-8af31744dd63",
    dataset_name="Turrutebasen",
    atom_feed_url="http://nedlasting.geonorge.no/geonorge/ATOM-feeds/TurOgFriluftsruter_AtomFeedFGDB.xml",
    description=(
        "Nasjonal database for turruter (National database for hiking routes). "
        "Contains foot trails, ski tracks, bicycle routes, and outdoor facilities."
    ),
)


class Source:
    """
    Loader for Norwegian trail data from Geonorge/Kartverket.

    Dataset: Turrutebasen (National database for hiking routes)
    """

    def __init__(self, cache_dir: str = ".cache"):
        """Initialize Geonorge source.

        Args:
            cache_dir: Root directory for caching data
        """
        self.cache = cache.Object(f"{cache_dir}/objects")
        self.download_cache = cache.Download(f"{cache_dir}/downloads")

    def load_turrutebasen(
        self,
        force_download: bool = False,
        target_crs: str | None = None,
        language: Language = Language.NO,
    ) -> TrailData:
        """
        Load Turrutebasen (trail database) from Geonorge with automatic code expansion.

        Always:
        - Expands codes to readable values
        - Translates layer names when language=EN
        - Translates column names when language=EN

        Args:
            force_download: Force re-download even if cached
            target_crs: Optional CRS to convert spatial layers to (e.g., "EPSG:4326")
            language: Language for values, layer names, and column names (NO or EN)

        Returns:
            TrailData object with expanded codes and translations

        Example:
            # Norwegian (default)
            data = source.load_turrutebasen()
            # Layer: "fotrute_senterlinje"
            # Column: gradering="Enkel (Grønn)"

            # English
            data = source.load_turrutebasen(language=Language.EN)
            # Layer: "hiking_trail_centerline"
            # Column: difficulty="Easy (Green)"

        Raises:
            FileNotFoundError: If automatic download fails
        """
        # Include target CRS and language in cache key
        cache_key = "geonorge_turrutebasen"
        if target_crs:
            crs_suffix = target_crs.replace(":", "_").lower()
            cache_key = f"{cache_key}_{crs_suffix}"
        if language != Language.NO:
            cache_key = f"{cache_key}_{language.value}"
        zip_filename = "turrutebasen.zip"

        try:
            # Get download info from ATOM feed
            download_info = self._get_download_info()

            # Download or get cached ZIP file
            result = self.download_cache.download(
                url=download_info.url,
                filename=zip_filename,
                version=download_info.updated,
                force=force_download,
            )

            # If we got fresh data, invalidate the processed cache
            if result.was_downloaded:
                print("Got fresh data, clearing processed cache...")
                self.cache.delete(cache_key)
            elif self.cache.exists(cache_key):
                # ZIP wasn't re-downloaded AND we have cache = versions match
                print("Loading Geonorge Turrutebasen from cache...")
                data = self.cache.load(cache_key)
                assert isinstance(data, TrailData)
                return data

            # If we get here: either fresh download OR no cache exists
            print("Processing FGDB from ZIP file...")
            spatial_layers, attribute_tables = self._load_fgdb_from_zip(result.path, target_crs=target_crs)

            # Process codes and translations
            spatial_layers = self._process_layers(spatial_layers, language)
            attribute_tables = self._process_layers(attribute_tables, language)

            # Create TrailData object (CRS will be auto-detected)
            trail_data = TrailData(
                metadata=TURRUTEBASEN_METADATA,
                spatial_layers=spatial_layers,
                attribute_tables=attribute_tables,
                source_url=download_info.url,
                version=result.version or "unknown",
                language=language,
            )

            # Cache the TrailData object with its own metadata
            print(f"Caching processed data with key: {cache_key}")
            self.cache.save(cache_key, trail_data, metadata=trail_data.get_full_metadata())

            return trail_data

        except Exception as e:
            print(f"Error: {e}")
            # If anything fails but we have cached data, use it
            if self.cache.exists(cache_key):
                print("Using cached data instead...")
                # Return cached TrailData object
                data = self.cache.load(cache_key)
                assert isinstance(data, TrailData)
                return data
            raise FileNotFoundError(f"Could not load data and no cache available.\nError: {e}") from e

    def _get_download_info(self) -> AtomFeedEntry:
        """Fetch download information from the ATOM feed.

        Returns:
            AtomFeedEntry with url, title, and updated date

        Raises:
            ValueError: If the feed cannot be parsed or URL not found
        """
        print("Fetching download URL from ATOM feed...")

        # Parse the ATOM feed
        feed = feedparser.parse(TURRUTEBASEN_METADATA.atom_feed_url)

        # Check if feed has entries even if bozo is True (encoding issues are ok)
        if not feed.entries:
            error_msg = "No entries found in ATOM feed"
            if feed.bozo:
                error_msg += f" (parse warning: {feed.bozo_exception})"
            raise ValueError(error_msg)

        # Look for nationwide dataset (Landsdekkende means nationwide in Norwegian)
        nationwide_entries = []

        for entry in feed.entries:
            title = entry.get("title", "")

            # Check if this is the nationwide FGDB dataset
            if ("Landsdekkende" in title or "_0000_" in title) and "FGDB" in title:
                # Get the download link from entry.links
                for link in entry.get("links", []):
                    href = link.get("href", "")
                    if href and href.endswith(".zip") and "FGDB" in href:
                        nationwide_entries.append(AtomFeedEntry(url=href, title=title, updated=entry.get("updated", "")))
                        break

        if not nationwide_entries:
            raise ValueError("Could not find nationwide FGDB download URL in ATOM feed")

        # If multiple entries, sort by updated date (newest first)
        if len(nationwide_entries) > 1:
            nationwide_entries.sort(key=lambda x: x.updated, reverse=True)
            print(f"Found {len(nationwide_entries)} nationwide entries, using most recent")

        selected = nationwide_entries[0]
        print(f"Found download URL: {selected.url}")
        print(f"  Dataset: {selected.title}")
        print(f"  Updated: {selected.updated}")

        return selected

    def _load_fgdb_from_zip(self, zip_path: Path, target_crs: str | None = None) -> tuple[dict[str, gpd.GeoDataFrame], dict[str, pd.DataFrame]]:
        """Load FGDB directly from ZIP file.

        This is a pure function that only transforms data from ZIP to GeoDataFrames.
        No caching or side effects.

        Args:
            zip_path: Path to the ZIP file containing FGDB
            target_crs: Optional CRS to convert ALL spatial layers to (e.g., "EPSG:4326")

        Returns:
            Tuple of (spatial_layers, attribute_tables)
        """
        print(f"Loading FGDB from {zip_path.name}")

        # Find the GDB path inside the ZIP
        gdb_path_in_zip = self._find_gdb_in_zip(zip_path)

        # Construct GDAL virtual file system path
        vsi_path = f"/vsizip/{zip_path}/{gdb_path_in_zip}"
        print(f"Using virtual path: {vsi_path}")

        # List available layers
        try:
            layers_df = gpd.list_layers(vsi_path)
            print(f"\nFound {len(layers_df)} layers in Geonorge dataset:")
            for _, row in layers_df.iterrows():
                print(f"  - {row['name']} ({row['geometry_type']})")
        except Exception as e:
            print(f"Error listing layers: {e}")
            raise

        # Load each layer and separate spatial from non-spatial
        spatial_layers = {}
        attribute_tables = {}

        for _, row in layers_df.iterrows():
            layer_name = row["name"]
            print(f"\nLoading layer: {layer_name}")
            try:
                df = gpd.read_file(vsi_path, layer=layer_name)
                print(f"  Loaded {len(df)} features")

                # Check if it's actually a spatial layer
                if isinstance(df, gpd.GeoDataFrame) and df.crs:
                    # Spatial layer with geometry
                    # Convert CRS if requested
                    if target_crs:
                        print(f"  Converting CRS from {df.crs} to {target_crs}")
                        df = df.to_crs(target_crs)
                    spatial_layers[layer_name] = df
                else:
                    # Non-spatial attribute table
                    # Convert to regular DataFrame to be explicit
                    attribute_tables[layer_name] = pd.DataFrame(df)

            except Exception as e:
                print(f"  Error loading layer {layer_name}: {e}")
                continue

        if not spatial_layers and not attribute_tables:
            raise ValueError("No layers could be loaded from FGDB")

        return spatial_layers, attribute_tables

    def _process_layers(
        self,
        layers: dict[str, T],
        language: Language,
    ) -> dict[str, T]:
        """Process layers: expand codes and translate if needed.

        Args:
            layers: Dictionary of layer_name -> DataFrame/GeoDataFrame
            language: Target language for expansion and translation

        Returns:
            Processed layers with expanded codes and translated names
        """
        processed: dict[str, T] = {}

        for layer_name, df in layers.items():
            # Process the dataframe
            # _process_dataframe preserves the type
            processed_df = self._process_dataframe(df, language)

            # Always translate - will return original if no translation exists
            translated_name = geonorge_translations.translate_layer_name(layer_name, language)

            processed[translated_name] = processed_df

        return processed

    def _process_dataframe(
        self,
        df: T,
        language: Language,
    ) -> T:
        """Process DataFrame: standardize types, expand codes, and translate columns.

        Args:
            df: DataFrame to process
            language: Target language

        Returns:
            Processed DataFrame with standardized types and expanded codes
        """
        # Make a copy to avoid modifying the original
        df = df.copy()

        # Step 1: Standardize column types (converts numeric codes to strings)
        df = geonorge_schema.standardize_types(df)

        # Step 2: Expand code columns to human-readable values
        for column in df.columns:
            col_name: str = str(column)
            # Check if this is a code column using the schema
            if geonorge_schema.get_column_type(col_name) == "code":
                # Now codes are strings, so lookup will work correctly
                df[col_name] = (
                    df[col_name]
                    .apply(lambda code, col=col_name: geonorge_codes.get_value(col, code, language) if pd.notna(code) else pd.NA)
                    .astype("string")
                )  # Ensure result is string dtype, not object

        # Step 3: Translate column names - will return original if no translation
        rename_dict = {}
        for col_name in df.columns:
            rename_dict[col_name] = geonorge_translations.translate_column_name(col_name, language)

        df = df.rename(columns=rename_dict)

        return df

    def _find_gdb_in_zip(self, zip_path: Path) -> str:
        """Find the GDB folder path inside a ZIP file.

        Args:
            zip_path: Path to the ZIP file

        Returns:
            Path to the .gdb folder inside the ZIP
        """
        with zipfile.ZipFile(zip_path, "r") as z:
            for name in z.namelist():
                if ".gdb/" in name:
                    # Return the path up to and including .gdb
                    return name.split(".gdb/")[0] + ".gdb"
        raise FileNotFoundError(f"No .gdb folder found in {zip_path}")
