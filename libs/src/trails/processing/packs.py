"""Small, uncompressed PMTiles v3 archives of a parent and three child levels.

Source indexes use either an explicit completion flag or legacy per-zoom inventories.
Each pack has at most 85 entries, in zoom-then-Hilbert order, with run length one;
identical tiles are deliberately not deduplicated. Only one tile's bytes are held
while writing, and resume computes the exact archive size from file sizes. The
reader supports this subset only, checking the header and root without loading
any tile data. See https://github.com/protomaps/PMTiles/blob/main/spec/v3/spec.md.
"""

import json
import math
import struct
from collections.abc import Iterable
from pathlib import Path
from typing import Any

Tile = tuple[int, int, int]
PNG = b"\x89PNG\r\n\x1a\n"
MAX_ENTRIES = 85


def tile_id(z: int, x: int, y: int) -> int:
    """Return the PMTiles zoom-then-Hilbert ID for a valid XYZ address."""
    if not 0 <= z <= 26 or not 0 <= x < 1 << z or not 0 <= y < 1 << z:
        raise ValueError(f"invalid tile address: {z}/{x}/{y}")
    result = ((1 << (2 * z)) - 1) // 3
    for bit in range(z - 1, -1, -1):
        side = 1 << bit
        rx, ry = bool(x & side), bool(y & side)
        result += side * side * ((3 * rx) ^ ry)
        if not ry:
            if rx:
                x, y = side - 1 - x, side - 1 - y
            x, y = y, x
    return result


def pack_levels(zooms: Iterable[int]) -> list[int]:
    """Return ascending parent levels, grouped four at a time from the top."""
    levels = sorted(set(zooms))
    if not levels or any(type(z) is not int or not 0 <= z <= 26 for z in levels):
        raise ValueError("zooms must contain integer levels between 0 and 26")
    top = levels[-1]
    return sorted({max(0, top - 3 - 4 * ((top - z) // 4)) for z in levels})


def read_index(path: Path) -> dict[str, Any]:
    """Read a finished source inventory, naming the zoom if legacy counts fail.

    An omitted per-zoom ``missing`` means zero (terrain cutters count ``empty``
    PNGs instead). Explicit false is always refused; explicit true is accepted.
    """
    index: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    pack_levels(index.get("zooms", []))
    if "complete" in index:
        if index["complete"] is not True:
            raise ValueError(f"{path}: tree is not complete")
    else:
        for zoom in index["zooms"]:
            row = index.get("per_zoom", {}).get(str(zoom), {})
            if (
                row.get("missing", 0) != 0
                or not all(type(row.get(key)) is int and row[key] >= 0 for key in ("tiles", "written", "skipped"))
                or row["written"] + row["skipped"] != row["tiles"]
            ):
                raise ValueError(f"{path}: z{zoom} has an incomplete inventory")
    return index


def _varint(value: int) -> bytes:
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def _directory(entries: list[tuple[int, int]]) -> bytes:
    result = bytearray(_varint(len(entries)))
    previous = 0
    for ident, _ in entries:
        result.extend(_varint(ident - previous))
        previous = ident
    result.extend(b"\x01" * len(entries))  # run lengths
    for _, size in entries:
        result.extend(_varint(size))
    result.extend(b"\x01" + b"\x00" * (len(entries) - 1))  # contiguous offsets
    return bytes(result)


def _prefix(tiles: list[tuple[Tile, Path]], metadata: dict[str, str]) -> tuple[bytes, list[int]]:
    lengths = [path.stat().st_size for _, path in tiles]
    if not 1 <= len(tiles) <= MAX_ENTRIES or any(size < len(PNG) for size in lengths):
        raise ValueError("a pack needs 1–85 nonempty PNG tiles")
    directory = _directory([(tile_id(*tile), size) for (tile, _), size in zip(tiles, lengths, strict=True)])
    meta = json.dumps(metadata, separators=(",", ":")).encode()
    meta_offset = 127 + len(directory)
    data_offset = meta_offset + len(meta)
    header = bytearray(127)
    header[:8] = b"PMTiles\x03"
    struct.pack_into(
        "<11Q", header, 8, 127, len(directory), meta_offset, len(meta), data_offset, 0, data_offset, sum(lengths), len(tiles), len(tiles), len(tiles)
    )
    low, high = min(t[0][0] for t in tiles), max(t[0][0] for t in tiles)
    header[96:102] = bytes((1, 1, 1, 2, low, high))

    def position(z: int, x: int, y: int) -> tuple[float, float]:
        return x / (1 << z) * 360 - 180, math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / (1 << z)))))

    northwest = [position(z, x, y) for (z, x, y), _ in tiles]
    southeast = [position(z, x + 1, y + 1) for (z, x, y), _ in tiles]
    west, north = min(p[0] for p in northwest), max(p[1] for p in northwest)
    east, south = max(p[0] for p in southeast), min(p[1] for p in southeast)
    struct.pack_into(
        "<4iB2i", header, 102, *(round(v * 1e7) for v in (west, south, east, north)), low, round((west + east) * 5e6), round((south + north) * 5e6)
    )
    return bytes(header) + directory + meta, lengths


def write_pack(tiles: dict[Tile, Path], target: Path, *, metadata: dict[str, str] | None = None) -> bool:
    """Write one pack atomically; return false if its expected size exists.

    Args:
        tiles: Up to 85 source PNG paths, addressed by XYZ.
        target: The pack filename.
        metadata: Optional minimal JSON metadata, e.g. the DEM encoding.

    Returns:
        Whether a pack was written. Equal-sized existing files are left alone.
    """
    ordered = sorted(tiles.items(), key=lambda item: tile_id(*item[0]))
    prefix, lengths = _prefix(ordered, metadata or {})
    if target.is_file() and target.stat().st_size == len(prefix) + sum(lengths):
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".pmtiles.part")
    try:
        with partial.open("wb") as output:
            output.write(prefix)
            for (_, path), length in zip(ordered, lengths, strict=True):
                data = path.read_bytes()
                if len(data) != length or not data.startswith(PNG):
                    raise ValueError(f"{path}: changed size or invalid PNG signature")
                output.write(data)
                del data
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    return True


class PackReader:
    """Open and validate our PMTiles subset, then read individual tiles on demand."""

    def __init__(self, path: Path):
        self.path = path
        with path.open("rb") as source:
            header = source.read(127)
            if len(header) != 127 or header[:8] != b"PMTiles\x03":
                raise ValueError(f"{path}: invalid PMTiles v3 header")
            root, root_len, meta, meta_len, leaf, leaf_len, data, data_len, addressed, count, contents = struct.unpack_from("<11Q", header, 8)
            if (
                header[96:100] != bytes((1, 1, 1, 2))
                or not 0 <= header[100] <= header[101] <= 26
                or not 1 <= count <= MAX_ENTRIES
                or addressed != count
                or contents != count
                or root != 127
                or not 0 < root_len <= 16384 - 127
                or meta != root + root_len
                or not 2 <= meta_len <= 16384
                or data != meta + meta_len
                or leaf != data
                or leaf_len != 0
                or data + data_len != path.stat().st_size
            ):
                raise ValueError(f"{path}: invalid or unsupported pack header")
            directory = source.read(root_len)
            metadata = json.loads(source.read(meta_len))
            if not isinstance(metadata, dict):
                raise ValueError(f"{path}: metadata is not a JSON object")
        cursor = 0

        def varint() -> int:
            nonlocal cursor
            value = 0
            for shift in range(0, 64, 7):
                if cursor >= len(directory):
                    break
                byte = directory[cursor]
                cursor += 1
                value |= (byte & 127) << shift
                if byte < 128 and value < 1 << 64:
                    return value
            raise ValueError(f"{path}: invalid directory varint")

        if varint() != count:
            raise ValueError(f"{path}: directory count differs from header")
        ids: list[int] = []
        ident = 0
        for _ in range(count):
            delta = varint()
            if ids and delta == 0:
                raise ValueError(f"{path}: duplicate tile ID")
            ident += delta
            ids.append(ident)
        if any(varint() != 1 for _ in range(count)):
            raise ValueError(f"{path}: leaf directory or unsupported run length")
        lengths = [varint() for _ in range(count)]
        self.entries: dict[int, tuple[int, int]] = {}
        end = 0
        for i, (ident, length) in enumerate(zip(ids, lengths, strict=True)):
            encoded = varint()
            offset = end if encoded == 0 and i > 0 else encoded - 1
            if length <= 0 or offset != end or offset + length > data_len:
                raise ValueError(f"{path}: invalid tile offset or length")
            self.entries[ident] = (data + offset, length)
            end = offset + length
        if cursor != len(directory) or end != data_len:
            raise ValueError(f"{path}: directory or tile data length mismatch")
        if ids[0] < ((1 << (2 * header[100])) - 1) // 3 or ids[-1] >= ((1 << (2 * (header[101] + 1))) - 1) // 3:
            raise ValueError(f"{path}: tile IDs outside header zooms")

    def read_tile(self, z: int, x: int, y: int) -> bytes | None:
        """Return the exact PNG bytes, or None when the pack has no such tile."""
        entry = self.entries.get(tile_id(z, x, y))
        if entry is None:
            return None
        offset, length = entry
        with self.path.open("rb") as source:
            source.seek(offset)
            tile = source.read(length)
        if len(tile) != length:
            raise ValueError(f"{self.path}: truncated tile data")
        return tile


def _write_index(path: Path, index: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".json.part")
    partial.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    partial.replace(path)


def build_tree(source: Path, output: Path, *, source_index: str, parent: Tile | None = None) -> dict[str, Any]:
    """Pack one finished version, keeping only parent addresses and one pack in memory.

    Args:
        source: Source version directory, opened read-only.
        output: Destination version directory under packs/.
        source_index: Source index address relative to analysis/output, for provenance.
        parent: Optionally build only this parent; the resulting index is incomplete.

    Returns:
        The pack inventory, with per-level counts including resumed packs.
    """
    original = read_index(source / "index.json")
    zooms = sorted(set(original["zooms"]))
    levels = pack_levels(zooms)
    if parent is not None and parent[0] not in levels:
        raise ValueError(f"parent level must be one of {levels}")
    if parent is not None:
        tile_id(*parent)
    parents: set[Tile] = set()
    for zoom in zooms:
        level = max(z for z in levels if z <= zoom)
        count = 0
        for path in (source / str(zoom)).glob("*/*.png"):
            x, y = int(path.parent.name), int(path.stem)
            tile_id(zoom, x, y)
            count += 1
            address = (level, x >> (zoom - level), y >> (zoom - level))
            if parent is None or address == parent:
                parents.add(address)
        row = original.get("per_zoom", {}).get(str(zoom))
        if row is not None and count != row["tiles"]:
            raise ValueError(f"{source}: z{zoom} has {count} files, inventory says {row['tiles']}")
    if not parents:
        raise ValueError(f"{source}: no tiles for the requested packs")
    index: dict[str, Any] = {
        "bounds": original["bounds"],
        "levels": levels,
        "per_level": {str(z): {"packs": 0, "written": 0, "skipped": 0, "bytes": 0} for z in levels},
        "tiles": 0,
        "source_index": source_index,
        "complete": False,
    }
    for key in ("stand", "source_modified"):
        if key in original:
            index[key] = original[key]
    _write_index(output / "index.json", index)
    metadata = {"encoding": original["encoding"]} if "encoding" in original else {}
    for level, px, py in sorted(parents):
        tiles = {}
        for zoom in zooms:
            if not level <= zoom <= level + 3:
                continue
            scale = 1 << (zoom - level)
            for x in range(px * scale, (px + 1) * scale):
                for y in range(py * scale, (py + 1) * scale):
                    path = source / f"{zoom}/{x}/{y}.png"
                    if path.is_file():
                        tiles[zoom, x, y] = path
        target = output / f"{level}/{px}/{py}.pmtiles"
        written = write_pack(tiles, target, metadata=metadata)
        row = index["per_level"][str(level)]
        row["packs"] += 1
        row["written" if written else "skipped"] += 1
        row["bytes"] += target.stat().st_size
        index["tiles"] += len(tiles)
    index["complete"] = parent is None
    _write_index(output / "index.json", index)
    return index


def weights_from_index(path: Path) -> dict[int, int]:
    """Return rounded mean bytes per pack by level, for Phase 6b's panel.

    Like kartverket_wms.weights_from_index, refuse unfinished inventories.
    """
    index = json.loads(path.read_text(encoding="utf-8"))
    if index.get("complete") is not True or not index.get("levels"):
        raise ValueError("weights require a completed pack tree")
    result = {}
    for level in index["levels"]:
        row = index.get("per_level", {}).get(str(level), {})
        if row.get("packs", 0) <= 0 or row.get("bytes", 0) <= 0 or row.get("written", 0) + row.get("skipped", 0) != row["packs"]:
            raise ValueError(f"z{level} has an incomplete pack inventory")
        result[level] = round(row["bytes"] / row["packs"])
    return result
