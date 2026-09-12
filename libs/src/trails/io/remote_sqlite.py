"""Read an SQLite database that lives on a remote server, by byte range.

Some of the files worth reading are far too large to download: Lantmäteriet's
whole-Sweden tile GeoPackage is 156 GB, and the map it is read for needs about
119,000 of its 38 million rows. SQLite reads a database one fixed-size page at
a time and asks for nothing it does not need, so a database can be opened over
a byte-range protocol by giving SQLite a virtual file system whose ``xRead`` is
a range request. This module is that VFS, on top of ``apsw``, which exposes the
VFS interface to Python.

**Blocks, not pages.** A range request costs about 0.19 s on an open FTP
connection whatever its size, and 1 MB arrives in 0.40 s — measured on
Lantmäteriet's server — so the file is read in 1 MB blocks held in a small LRU,
not in 4 KB pages. A B-tree walk touches the same few interior pages again and
again, and rows that are near each other on disk share a block, which is what
turns a tile copy from one request per page into one request per run of tiles::

    remote = FtpFile("download-opendata.lantmateriet.se", "path/to/file.gpkg")
    with RemoteDatabase(remote) as db:
        for row in db.execute("select name from sqlite_master"):
            print(row)
    print(remote.stats)

The database is opened read-only and declared immutable, so SQLite takes no
locks and never looks for a journal — both of which would be range requests
answered with nothing.
"""

import ftplib
import sys
import time
from collections import OrderedDict
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol

import apsw

#: Bytes fetched per request. Measured against the cost of a request: below
#: this the request dominates, above it the transfer does, and a tile is a few
#: kilobytes, so anything much larger fetches ground nobody asked for.
DEFAULT_BLOCK_SIZE = 1 << 20

#: Blocks held in memory — 256 MB at the default block size. Enough that the
#: index pages of a walk stay resident while the leaves stream past.
DEFAULT_CACHE_BLOCKS = 256

#: Attempts at one range read before giving up. A dropped FTP connection is
#: reconnected in between; the sleeps double.
MAX_ATTEMPTS = 5

#: Seconds before the second attempt.
INITIAL_BACKOFF = 1.0

#: Seconds a socket waits before a read is declared dead.
SOCKET_TIMEOUT = 120


@dataclass
class Stats:
    """What the remote file has cost so far."""

    reads: int = 0
    bytes: int = 0
    seconds: float = 0.0

    def __str__(self) -> str:
        return f"{self.reads:,} reads, {self.bytes / 1e6:,.1f} MB, {self.seconds:,.1f} s"


class RangeReader(Protocol):
    """Something a byte range can be read from."""

    @property
    def size(self) -> int:
        """Length of the file in bytes."""
        ...

    def read_range(self, offset: int, length: int) -> bytes:
        """Return up to ``length`` bytes starting at ``offset``."""
        ...


class FtpFile:
    """A file on an FTP server, read by ``REST`` and ``RETR`` over one connection.

    The control connection is opened on first use and kept; each range read
    opens one data connection, reads what it needs and closes it early, which
    the server answers with a 426 that is expected and ignored. A connection
    that has died is reopened and the read retried.
    """

    def __init__(self, host: str, path: str, timeout: int = SOCKET_TIMEOUT):
        """Describe the file; nothing is fetched yet.

        Args:
            host: FTP server, anonymous login
            path: Path of the file on the server
            timeout: Socket timeout in seconds
        """
        self.host = host
        self.path = path
        self.timeout = timeout
        self.stats = Stats()
        self._ftp: ftplib.FTP | None = None
        self._size: int | None = None
        self._modified: str | None = None

    def _connect(self) -> ftplib.FTP:
        ftp = ftplib.FTP(self.host, timeout=self.timeout)
        ftp.login()
        ftp.voidcmd("TYPE I")
        return ftp

    def _session(self) -> ftplib.FTP:
        if self._ftp is None:
            self._ftp = self._connect()
        return self._ftp

    def _drop(self) -> None:
        if self._ftp is not None:
            try:
                self._ftp.close()
            except OSError:
                pass
        self._ftp = None

    @property
    def size(self) -> int:
        """Length of the file, asked of the server once."""
        if self._size is None:
            size = self._session().size(self.path)
            if size is None:
                raise OSError(f"{self.host} does not report a size for {self.path}")
            self._size = size
        return self._size

    @property
    def modified(self) -> str:
        """When the server says the file was last modified, as ``YYYYMMDDHHMMSS``."""
        if self._modified is None:
            answer = self._session().sendcmd(f"MDTM {self.path}")
            self._modified = answer.split()[-1]
        return self._modified

    def read_range(self, offset: int, length: int) -> bytes:
        """Read ``length`` bytes at ``offset``, reconnecting and retrying on failure.

        Args:
            offset: First byte
            length: Bytes wanted; fewer come back only at the end of the file

        Returns:
            The bytes

        Raises:
            OSError: If every attempt failed
        """
        backoff = INITIAL_BACKOFF
        for attempt in range(1, MAX_ATTEMPTS + 1):
            started = time.time()
            try:
                ftp = self._session()
                data = ftp.transfercmd(f"RETR {self.path}", rest=offset)
                buffer = bytearray()
                try:
                    while len(buffer) < length:
                        chunk = data.recv(min(1 << 16, length - len(buffer)))
                        if not chunk:
                            break
                        buffer += chunk
                finally:
                    data.close()
                try:
                    ftp.voidresp()
                except ftplib.error_temp:
                    pass  # 426: the transfer was cut short, which is what closing early does
                self.stats.reads += 1
                self.stats.bytes += len(buffer)
                self.stats.seconds += time.time() - started
                return bytes(buffer)
            except (OSError, EOFError, ftplib.Error) as failure:
                self._drop()
                if attempt == MAX_ATTEMPTS:
                    raise OSError(f"range read at {offset} failed after {attempt} attempts: {failure}") from failure
                print(f"  FTP read at {offset:,} failed (try {attempt}/{MAX_ATTEMPTS}): {failure}; retrying in {backoff:.0f} s", file=sys.stderr)
                time.sleep(backoff)
                backoff *= 2
        raise AssertionError("unreachable")

    def close(self) -> None:
        """Close the control connection."""
        self._drop()


class BlockCache:
    """Fixed-size blocks of a remote file, fetched on demand and held in an LRU."""

    def __init__(self, reader: RangeReader, block_size: int = DEFAULT_BLOCK_SIZE, blocks: int = DEFAULT_CACHE_BLOCKS):
        """Wrap a reader.

        Args:
            reader: Where the bytes come from
            block_size: Bytes per request
            blocks: Blocks kept in memory
        """
        self.reader = reader
        self.block_size = block_size
        self.capacity = blocks
        self._blocks: OrderedDict[int, bytes] = OrderedDict()

    def _block(self, index: int) -> bytes:
        held = self._blocks.get(index)
        if held is not None:
            self._blocks.move_to_end(index)
            return held
        start = index * self.block_size
        length = min(self.block_size, self.reader.size - start)
        fetched = self.reader.read_range(start, length) if length > 0 else b""
        self._blocks[index] = fetched
        if len(self._blocks) > self.capacity:
            self._blocks.popitem(last=False)
        return fetched

    def read(self, offset: int, length: int) -> bytes:
        """Return the bytes at ``offset``, from as many blocks as it takes.

        Args:
            offset: First byte
            length: Bytes wanted

        Returns:
            The bytes, short only at the end of the file
        """
        out = bytearray()
        while length > 0:
            index, inside = divmod(offset, self.block_size)
            piece = self._block(index)[inside : inside + length]
            if not piece:
                break
            out += piece
            offset += len(piece)
            length -= len(piece)
        return bytes(out)


class _File(apsw.VFSFile):
    """The one file SQLite sees: read-only, immutable, never locked."""

    def __init__(self, cache: BlockCache, size: int, flags: list[int]):
        self._cache = cache
        self._size = size
        flags[1] = apsw.SQLITE_OPEN_READONLY

    def xRead(self, amount: int, offset: int) -> bytes:  # noqa: N802 - apsw's names
        data = self._cache.read(offset, amount)
        if len(data) < amount:
            data += b"\0" * (amount - len(data))
        return data

    def xFileSize(self) -> int:  # noqa: N802
        return self._size

    def xClose(self) -> None:  # noqa: N802
        pass

    def xLock(self, level: int) -> None:  # noqa: N802
        pass

    def xUnlock(self, level: int) -> None:  # noqa: N802
        pass

    def xCheckReservedLock(self) -> bool:  # noqa: N802
        return False

    def xSectorSize(self) -> int:  # noqa: N802
        return 4096

    def xDeviceCharacteristics(self) -> int:  # noqa: N802
        return apsw.SQLITE_IOCAP_IMMUTABLE

    def xFileControl(self, op: int, ptr: int) -> bool:  # noqa: N802
        return False

    def xSync(self, flags: int) -> None:  # noqa: N802
        pass

    def xTruncate(self, size: int) -> None:  # noqa: N802
        raise OSError("read-only")

    def xWrite(self, data: Any, offset: int) -> None:  # noqa: N802
        raise OSError("read-only")


class _Vfs(apsw.VFS):
    """A VFS that answers every open with the one remote file."""

    def __init__(self, name: str, cache: BlockCache, size: int):
        self._cache = cache
        self._size = size
        super().__init__(name, "", makedefault=False)

    def xOpen(self, name: Any, flags: list[int]) -> _File:  # noqa: N802
        return _File(self._cache, self._size, flags)

    def xAccess(self, pathname: str, flags: int) -> bool:  # noqa: N802
        return False

    def xFullPathname(self, name: str) -> str:  # noqa: N802
        return name

    def xDelete(self, name: str, syncdir: bool) -> None:  # noqa: N802
        pass


class RemoteDatabase:
    """An SQLite database opened over a :class:`RangeReader`.

    Use as a context manager; the connection and the VFS registration are
    released on exit.
    """

    def __init__(self, reader: RangeReader, block_size: int = DEFAULT_BLOCK_SIZE, blocks: int = DEFAULT_CACHE_BLOCKS):
        """Prepare the VFS; the database is opened on entry.

        Args:
            reader: Where the file's bytes come from
            block_size: Bytes per range request
            blocks: Blocks held in memory
        """
        self.cache = BlockCache(reader, block_size, blocks)
        self._size = reader.size
        self._name = f"remote-sqlite-{id(self)}"
        self._vfs: _Vfs | None = None
        self._connection: apsw.Connection | None = None

    def __enter__(self) -> RemoteDatabase:
        self._vfs = _Vfs(self._name, self.cache, self._size)
        self._connection = apsw.Connection("remote", flags=apsw.SQLITE_OPEN_READONLY, vfs=self._name)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        if self._vfs is not None:
            self._vfs.unregister()
            self._vfs = None

    def execute(self, sql: str, bindings: tuple[Any, ...] = ()) -> Iterator[tuple[Any, ...]]:
        """Run one statement and iterate its rows.

        Args:
            sql: The statement
            bindings: Its parameters

        Returns:
            The rows, as tuples
        """
        if self._connection is None:
            raise RuntimeError("the database is opened by entering the context")
        return iter(self._connection.execute(sql, bindings))
