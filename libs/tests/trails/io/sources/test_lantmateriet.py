"""Tests for the Lantmäteriet tile copy."""

import json
import sqlite3
from pathlib import Path

import pytest
from trails.io.sources import lantmateriet

ABISKO = (18.15, 68.17, 19.00, 68.46)


class LocalReader:
    """A GeoPackage on disk, read by range like the FTP file is."""

    def __init__(self, path: Path):
        self.path = path
        self.size = path.stat().st_size

    def read_range(self, offset: int, length: int) -> bytes:
        with self.path.open("rb") as handle:
            handle.seek(offset)
            return handle.read(length)


def _png(z: int, x: int, y: int) -> bytes:
    """A stand-in tile: recognisable bytes, not a real image."""
    return f"tile {z}/{x}/{y}".encode() * 40


@pytest.fixture
def geopackage(tmp_path) -> Path:
    """A tile table shaped like Lantmäteriet's, holding z0 to z3 whole except one tile."""
    path = tmp_path / "topowebb.gpkg"
    with sqlite3.connect(path) as db:
        db.execute(
            f"CREATE TABLE {lantmateriet.TILE_TABLE} (id INTEGER PRIMARY KEY AUTOINCREMENT, zoom_level INTEGER NOT NULL,"
            " tile_column INTEGER NOT NULL, tile_row INTEGER NOT NULL, tile_data BLOB NOT NULL, UNIQUE (zoom_level, tile_column, tile_row))"
        )
        rows = [(z, x, y, _png(z, x, y)) for z in range(4) for x in range(2**z) for y in range(2**z) if (z, x, y) != (3, 4, 1)]
        db.executemany(f"INSERT INTO {lantmateriet.TILE_TABLE} (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?)", rows)
    return path


class TestTileRange:
    """The XYZ arithmetic, against figures computed independently for the Abisko box."""

    def test_abisko_at_z13(self):
        assert lantmateriet.tile_range(ABISKO, 13) == (4509, 1932, 4528, 1950)

    def test_abisko_at_z17(self):
        assert lantmateriet.tile_range(ABISKO, 17) == (72144, 30915, 72453, 31201)

    def test_the_world_at_z0(self):
        assert lantmateriet.tile_range((-180, -85, 180, 85), 0) == (0, 0, 1, 0)

    def test_count_over_zooms(self):
        assert lantmateriet.tile_count(ABISKO, [13]) == 380
        assert lantmateriet.tile_count(ABISKO, range(8, 18)) == 118_967


class TestCopyTiles:
    """Copying a box out of a local stand-in for the FTP file."""

    def test_writes_the_box_and_an_index(self, geopackage, tmp_path):
        out = tmp_path / "tiles"
        source = lantmateriet.Source(reader=LocalReader(geopackage))
        index = source.copy_tiles((0.0, 0.0, 90.0, 85.0), zooms=[2, 3], out_dir=out)

        assert (out / "2" / "2" / "1.png").read_bytes() == _png(2, 2, 1)
        assert (out / "3" / "5" / "2.png").read_bytes() == _png(3, 5, 2)
        assert not (out / "3" / "0").exists(), "x=0 at z3 lies west of the box"
        assert index["per_zoom"]["2"]["written"] == 6
        assert index["per_zoom"]["3"]["written"] == 14
        assert index["per_zoom"]["3"]["missing"] == 1, "3/4/1 is not in the file"
        assert json.loads((out / lantmateriet.INDEX_FILE).read_text())["tiles"] == 21

    def test_a_second_run_skips_what_is_there(self, geopackage, tmp_path):
        out = tmp_path / "tiles"
        source = lantmateriet.Source(reader=LocalReader(geopackage))
        source.copy_tiles((0.0, 0.0, 90.0, 85.0), zooms=[3], out_dir=out)
        marker = out / "3" / "5" / "2.png"
        marker.write_bytes(b"kept")

        index = source.copy_tiles((0.0, 0.0, 90.0, 85.0), zooms=[3], out_dir=out)

        assert marker.read_bytes() == b"kept"
        assert index["per_zoom"]["3"]["skipped"] == 14
        assert index["per_zoom"]["3"]["written"] == 0
        assert index["per_zoom"]["3"]["missing"] == 1
        assert index["per_zoom"]["3"]["bytes"] == 13 * len(_png(3, 4, 0)) + len(b"kept"), "the inventory counts what is on disk"

    def test_refuses_to_fill_a_tree_from_another_stand_of_the_file(self, geopackage, tmp_path):
        """The tree's index says which file it came from; a run against a
        newer file must not fill gaps under the same immutable address."""
        out = tmp_path / "tiles"
        first = LocalReader(geopackage)
        first.modified = "20260623110509"  # type: ignore[attr-defined]
        lantmateriet.Source(reader=first).copy_tiles((0.0, 0.0, 90.0, 85.0), zooms=[3], out_dir=out)
        assert json.loads((out / lantmateriet.INDEX_FILE).read_text())["source_modified"] == "20260623110509"
        (out / "3" / "5" / "2.png").unlink()

        later = LocalReader(geopackage)
        later.modified = "20261001080000"  # type: ignore[attr-defined]
        with pytest.raises(ValueError, match="new version directory"):
            lantmateriet.Source(reader=later).copy_tiles((0.0, 0.0, 90.0, 85.0), zooms=[3], out_dir=out)
        assert not (out / "3" / "5" / "2.png").exists(), "nothing was written from the newer file"

        # The same stand resumes as before, and a reader that cannot say
        # (a file on disk in a test) is not held to it.
        lantmateriet.Source(reader=first).copy_tiles((0.0, 0.0, 90.0, 85.0), zooms=[3], out_dir=out)
        lantmateriet.Source(reader=LocalReader(geopackage)).copy_tiles((0.0, 0.0, 90.0, 85.0), zooms=[3], out_dir=out)

    def test_refuses_a_zoom_the_file_lacks(self, geopackage, tmp_path):
        source = lantmateriet.Source(reader=LocalReader(geopackage))
        with pytest.raises(ValueError):
            source.copy_tiles(ABISKO, zooms=[18], out_dir=tmp_path / "tiles")
