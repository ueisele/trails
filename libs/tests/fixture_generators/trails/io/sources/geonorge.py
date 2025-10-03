#!/usr/bin/env python3
"""
Fixture generator for Geonorge/Kartverket trail data.

Creates minimal test fixtures from real Turrutebasen data for testing.
"""

import tempfile
import zipfile
from collections.abc import Collection
from pathlib import Path
from typing import Any

import geopandas as gpd
import requests


def get_fixture_dir() -> Path:
    """Get the fixture directory for Geonorge data."""
    # Navigate from this file to the fixtures directory
    module_path = Path(__file__)
    tests_root = module_path.parents[4]  # Go up to tests/
    return tests_root / "fixtures" / "trails" / "io" / "sources" / "geonorge"


def download_turrutebasen() -> Path:
    """Download the real Turrutebasen dataset from Geonorge."""
    print("Downloading real Turrutebasen data from Geonorge...")
    url = "https://nedlasting.geonorge.no/geonorge/Friluftsliv/TurOgFriluftsruter/FGDB/Friluftsliv_0000_Norge_25833_TurOgFriluftsruter_FGDB.zip"

    response = requests.get(url, stream=True)
    response.raise_for_status()

    # Save to temporary file
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0

        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                tmp.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    progress = (downloaded / total_size) * 100
                    print(f"\rDownloading: {progress:.1f}%", end="", flush=True)

        print()  # New line after progress
        return Path(tmp.name)


def _find_gdb_in_zip(source_zip: Path) -> str:
    """Find the .gdb path inside a ZIP file."""
    gdb_path_in_zip = None
    with zipfile.ZipFile(source_zip, "r") as zf:
        for name in zf.namelist():
            if ".gdb/" in name:
                # Get the path up to and including .gdb
                gdb_path_in_zip = name.split(".gdb/")[0] + ".gdb"
                break

    if not gdb_path_in_zip:
        raise FileNotFoundError(f"No .gdb folder found in {source_zip}")

    return gdb_path_in_zip


def verify_fixture_completeness(gdb_path: Path, expected_layers: Collection[str], processed_info: dict[str, dict[str, Any]]) -> None:
    """Ensure all expected layers are present in the fixture."""
    print("\n  Verifying fixture completeness...")

    # List layers in the created FGDB
    created_layers_df = gpd.list_layers(gdb_path)
    created_layer_names = set(created_layers_df["name"].values)
    expected_layer_names = set(expected_layers)

    # Check for missing layers
    missing = expected_layer_names - created_layer_names
    if missing:
        raise ValueError(
            f"Fixture generation failed. Missing layers: {missing}\nExpected: {sorted(expected_layer_names)}\nCreated: {sorted(created_layer_names)}"
        )

    # Verify each layer has features
    for layer_name in expected_layers:
        # Read from FGDB using GeoPandas
        try:
            df = gpd.read_file(gdb_path, layer=layer_name)
        except Exception as e:
            raise ValueError(f"Failed to read layer '{layer_name}' from FGDB: {e}") from e

        if len(df) == 0:
            raise ValueError(f"Layer '{layer_name}' has no features!")

        expected_count = processed_info[layer_name]["features"]
        if len(df) != expected_count:
            raise ValueError(f"Layer '{layer_name}' has {len(df)} features, expected {expected_count}")

        # Check type matches
        has_geometry = "geometry" in df.columns
        expected_type = processed_info[layer_name]["type"]
        actual_type = "spatial" if has_geometry else "attribute"

        if actual_type != expected_type:
            raise ValueError(f"Layer '{layer_name}' type mismatch: expected {expected_type}, got {actual_type}")

    spatial_count = sum(1 for v in processed_info.values() if v["type"] == "spatial")
    attribute_count = sum(1 for v in processed_info.values() if v["type"] == "attribute")

    print(f"    ✓ All {len(expected_layers)} layers verified successfully")
    print(f"    ✓ Spatial layers: {spatial_count}")
    print(f"    ✓ Attribute tables: {attribute_count}")


def create_minimal_turrutebasen_gdb(source_zip: Path, output_dir: Path) -> Path:
    """Extract minimal subset from the full Turrutebasen FGDB."""
    print("\nExtracting and creating minimal dataset...")

    # Find GDB path in ZIP
    gdb_path_in_zip = _find_gdb_in_zip(source_zip)
    print(f"Found GDB in ZIP: {gdb_path_in_zip}")

    # Read using GDAL virtual filesystem with the full path to the GDB
    vsi_path = f"/vsizip/{source_zip}/{gdb_path_in_zip}"

    # List all layers
    try:
        layers_df = gpd.list_layers(vsi_path)
        print(f"Found {len(layers_df)} layers in source data")
    except Exception as e:
        # Try without the intermediate path as fallback
        print(f"Error listing layers: {e}")
        print("Trying alternative approach...")
        vsi_path = f"/vsizip/{source_zip}"
        layers_df = gpd.list_layers(vsi_path)
        print(f"Found {len(layers_df)} layers in source data")

    # Selected layers configuration
    selected_layers = {
        "fotrute_senterlinje": 15,  # Spatial: hiking trails
        "ruteinfopunkt_posisjon": 20,  # Spatial: info points
        "fotruteinfo_tabell": 15,  # Non-spatial: trail metadata
        "annenruteinfo_tabell": 10,  # Non-spatial: other metadata
    }

    # Validate all expected layers exist
    missing_layers = []
    for layer_name in selected_layers:
        if layer_name not in layers_df["name"].values:
            missing_layers.append(layer_name)

    if missing_layers:
        raise ValueError(f"Expected layers not found in source data: {missing_layers}\nAvailable layers: {layers_df['name'].tolist()}")

    # Create output FGDB path
    gdb_path = output_dir / "Turrutebasen_minimal.gdb"

    # Remove existing FGDB if it exists
    if gdb_path.exists():
        import shutil

        shutil.rmtree(gdb_path)

    # Process each layer
    processed_layers = {}

    for layer_name, max_features in selected_layers.items():
        print(f"  Processing {layer_name} (max {max_features} features)...")

        try:
            # Read layer using GeoPandas
            df = gpd.read_file(vsi_path, layer=layer_name)

            # Take subset
            subset = df.head(max_features)

            # Determine if spatial or attribute table
            is_spatial = "geometry" in subset.columns

            # Write to new FGDB using GeoPandas
            # For non-spatial tables, ensure we have a GeoDataFrame with geometry=None
            if not is_spatial:
                # Convert DataFrame to GeoDataFrame with no geometry
                subset = gpd.GeoDataFrame(subset, geometry=None)

            subset.to_file(gdb_path, layer=layer_name, driver="OpenFileGDB")

            # Track what we processed
            processed_layers[layer_name] = {
                "features": len(subset),
                "type": "spatial" if is_spatial else "attribute",
            }

            print(f"    Saved {len(subset)} features ({processed_layers[layer_name]['type']})")

        except Exception as e:
            # No fallback - if we can't write to FGDB, that's a hard failure
            # Our implementation only reads FGDB, so fixtures must be in FGDB format
            # Determine layer type for error message
            layer_type = "unknown"
            try:
                if "df" in locals() and hasattr(df, "columns"):
                    if "geometry" in df.columns:
                        layer_type = "spatial"
                    else:
                        layer_type = "non-spatial attribute table"
            except Exception:
                pass

            raise ValueError(
                f"Failed to write layer '{layer_name}' to FGDB.\n"
                f"Layer type: {layer_type}\n"
                f"This is likely a GDAL configuration issue.\n"
                f"Requirements: GDAL >= 3.6 with OpenFileGDB write support.\n"
                f"Error: {e}"
            ) from e

    # Verify all layers were created successfully
    verify_fixture_completeness(gdb_path, selected_layers.keys(), processed_layers)

    return gdb_path


def create_turrutebasen_zip_fixture(gdb_path: Path, output_path: Path) -> Path:
    """Compress the minimal Turrutebasen FGDB to a ZIP file."""
    print(f"\nCreating ZIP fixture: {output_path.name}")

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add all files from the GDB directory
        for file_path in gdb_path.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(gdb_path.parent)
                zf.write(file_path, arcname)

    # Check size
    size_kb = output_path.stat().st_size / 1024
    print(f"  Size: {size_kb:.1f} KB")

    if size_kb > 100:
        print("  ⚠️  WARNING: Fixture larger than 100KB target!")
    else:
        print("  ✓ Size is within target (<100KB)")

    return output_path


def create_turrutebasen_atom_fixture(output_path: Path) -> Path:
    """Create a minimal ATOM feed fixture for Turrutebasen."""
    print(f"\nCreating ATOM feed fixture: {output_path.name}")

    atom_content = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:georss="http://www.georss.org/georss">
    <id>test-feed-id</id>
    <title>Tur- og friluftsruter</title>
    <subtitle>Test ATOM feed for Turrutebasen</subtitle>
    <rights>Kartverket</rights>
    <updated>2025-09-18T05:31:27+02:00</updated>
    <generator version="1.0">Test Generator</generator>

    <entry>
        <author>
            <name>Kartverket</name>
        </author>
        <category term="EPSG:25833" scheme="http://www.opengis.net/def/crs/"/>
        <id>test-entry-id</id>
        <link rel="alternate"
              href="https://test.example.com/turrutebasen_minimal.zip"
              type="application/zip"
              title="FGDB-format, Landsdekkende"/>
        <published>2025-09-18T05:31:27+02:00</published>
        <rights>Kartverket</rights>
        <title>FGDB-format, Landsdekkende</title>
        <updated>2025-09-18T05:31:27</updated>
    </entry>
</feed>"""

    output_path.write_text(atom_content, encoding="utf-8")

    size_kb = output_path.stat().st_size / 1024
    print(f"  Size: {size_kb:.1f} KB")

    return output_path


def create_turrutebasen_fixtures() -> int:
    """Create all Turrutebasen test fixtures."""
    print("=" * 60)
    print("Geonorge Turrutebasen Test Fixture Generator")
    print("=" * 60)

    # Setup paths
    fixture_dir = get_fixture_dir()
    fixture_dir.mkdir(parents=True, exist_ok=True)

    # Check if fixtures already exist
    zip_fixture = fixture_dir / "turrutebasen_minimal.zip"
    atom_fixture = fixture_dir / "turrutebasen_atom_feed.xml"

    if zip_fixture.exists() or atom_fixture.exists():
        response = input("\n⚠️  Fixtures already exist. Overwrite? (y/N): ")
        if response.lower() != "y":
            print("Aborted.")
            return 1

    try:
        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as tmpdir_str:
            tmpdir = Path(tmpdir_str)

            # Step 1: Download real data
            source_zip = download_turrutebasen()

            try:
                # Step 2: Create minimal GDB
                minimal_gdb = create_minimal_turrutebasen_gdb(source_zip, tmpdir)

                # Step 3: Create ZIP fixture
                create_turrutebasen_zip_fixture(minimal_gdb, zip_fixture)

                # Step 4: Create ATOM feed fixture
                create_turrutebasen_atom_fixture(atom_fixture)

                print("\n" + "=" * 60)
                print("✓ Successfully created test fixtures:")
                print(f"  - {zip_fixture}")
                print(f"  - {atom_fixture}")
                print("=" * 60)

            finally:
                # Clean up downloaded file
                source_zip.unlink(missing_ok=True)

    except Exception as e:
        print(f"\n❌ Error creating fixtures: {e}")
        return 1

    return 0


def main() -> None:
    """Main entry point when run as a script or module."""
    import sys

    sys.exit(create_turrutebasen_fixtures())


if __name__ == "__main__":
    main()
