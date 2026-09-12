"""Tests for reading an SQLite database through a range reader."""

import sqlite3
from pathlib import Path

import pytest
from trails.io.remote_sqlite import BlockCache, RemoteDatabase


class LocalReader:
    """A file on disk, read by range, counting what was asked for."""

    def __init__(self, path: Path):
        self.path = path
        self.size = path.stat().st_size
        self.reads: list[tuple[int, int]] = []

    def read_range(self, offset: int, length: int) -> bytes:
        self.reads.append((offset, length))
        with self.path.open("rb") as handle:
            handle.seek(offset)
            return handle.read(length)


@pytest.fixture
def database(tmp_path) -> Path:
    """A database with a few thousand rows and a blob column, larger than one small block."""
    path = tmp_path / "tiles.gpkg"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE tiles (id INTEGER PRIMARY KEY, z INTEGER, x INTEGER, y INTEGER, data BLOB, UNIQUE (z, x, y))")
        db.executemany(
            "INSERT INTO tiles (z, x, y, data) VALUES (?, ?, ?, ?)",
            [(z, x, y, bytes([z, x, y]) * 300) for z in range(3) for x in range(2**z) for y in range(2**z)] * 1,
        )
        db.executemany("INSERT INTO tiles (z, x, y, data) VALUES (?, ?, ?, ?)", [(5, x, y, b"\x01" * 2000) for x in range(32) for y in range(32)])
    return path


class TestRemoteDatabase:
    """Rows through the VFS are the rows sqlite3 sees."""

    def test_reads_the_same_rows(self, database):
        reader = LocalReader(database)
        with sqlite3.connect(database) as direct:
            expected = direct.execute("SELECT z, x, y, length(data) FROM tiles WHERE z = 5 AND x = 7 ORDER BY y").fetchall()
        with RemoteDatabase(reader, block_size=4096, blocks=64) as remote:
            got = list(remote.execute("SELECT z, x, y, length(data) FROM tiles WHERE z = 5 AND x = 7 ORDER BY y"))
        assert got == expected
        assert len(got) == 32

    def test_blob_comes_back_whole(self, database):
        reader = LocalReader(database)
        with RemoteDatabase(reader, block_size=4096, blocks=64) as remote:
            (data,) = next(remote.execute("SELECT data FROM tiles WHERE z = 2 AND x = 3 AND y = 1"))
        assert data == bytes([2, 3, 1]) * 300

    def test_reads_only_a_fraction_of_the_file(self, database):
        reader = LocalReader(database)
        with RemoteDatabase(reader, block_size=4096, blocks=64) as remote:
            list(remote.execute("SELECT data FROM tiles WHERE z = 5 AND x = 7 AND y = 9"))
        fetched = sum(length for _, length in reader.reads)
        assert 0 < fetched < reader.size / 2

    def test_a_repeated_query_costs_no_new_reads(self, database):
        reader = LocalReader(database)
        with RemoteDatabase(reader, block_size=4096, blocks=64) as remote:
            list(remote.execute("SELECT data FROM tiles WHERE z = 5 AND x = 7 AND y = 9"))
            before = len(reader.reads)
            list(remote.execute("SELECT data FROM tiles WHERE z = 5 AND x = 7 AND y = 9"))
        assert len(reader.reads) == before

    def test_must_be_entered(self, database):
        remote = RemoteDatabase(LocalReader(database))
        with pytest.raises(RuntimeError):
            remote.execute("SELECT 1")


class TestBlockCache:
    """The block cache hands back exact ranges and evicts the oldest block."""

    def test_spans_blocks_and_stops_at_the_end(self, tmp_path):
        path = tmp_path / "bytes"
        path.write_bytes(bytes(range(256)) * 4)
        cache = BlockCache(LocalReader(path), block_size=100, blocks=2)
        assert cache.read(95, 10) == bytes(range(95, 105))
        assert cache.read(1020, 10) == bytes(range(252, 256))

    def test_evicts_the_least_recently_used(self, tmp_path):
        path = tmp_path / "bytes"
        path.write_bytes(bytes(1000))
        reader = LocalReader(path)
        cache = BlockCache(reader, block_size=100, blocks=2)
        cache.read(0, 1)
        cache.read(100, 1)
        cache.read(0, 1)  # block 0 is now the most recent
        cache.read(200, 1)  # evicts block 1
        cache.read(0, 1)  # still held
        cache.read(100, 1)  # fetched again
        assert [offset for offset, _ in reader.reads] == [0, 100, 200, 100]
