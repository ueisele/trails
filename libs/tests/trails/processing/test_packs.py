"""PMTiles conformance through a separately implemented spec reader, plus pipeline tests."""

import importlib.util
import json
import struct
import zlib
from pathlib import Path

import pytest
from trails.processing import packs


def _png(value=0):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">2I5B", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes((0, value, 20, 30))))
        + chunk(b"IEND", b"")
    )


def _independent_read(path):
    """Decode spec v3 by field offsets; no calls to any production helpers.

    Convert IDs back to XYZ using the inverse Hilbert algorithm, so writer
    and test do not share their coordinate-to-ID implementation either.
    """
    data = path.read_bytes()
    assert data[:7] == b"PMTiles" and data[7] == 3

    def u64(at):
        return int.from_bytes(data[at : at + 8], "little")

    assert u64(8) == 127
    assert u64(8) + u64(16) <= 16384
    assert u64(48) == 0
    assert data[96] == 1
    assert data[97] == data[98] == 1
    assert data[99] == 2
    assert isinstance(json.loads(data[u64(24) : u64(24) + u64(32)]), dict)
    cursor = u64(8)

    def number():
        nonlocal cursor
        value = shift = 0
        for _ in range(10):
            byte = data[cursor]
            cursor += 1
            value += (byte % 128) * 2**shift
            if byte < 128:
                return value
            shift += 7
        raise AssertionError("overlong varint")

    count = number()
    assert count == u64(72) == u64(80) == u64(88)
    ids = []
    previous = 0
    for _ in range(count):
        previous += number()
        ids.append(previous)
    runs = [number() for _ in ids]
    lengths = [number() for _ in ids]
    offsets = []
    for i in range(count):
        offset = number()
        offsets.append(offsets[i - 1] + lengths[i - 1] if i and offset == 0 else offset - 1)
    assert cursor == u64(8) + u64(16)
    result = {}
    for ident, run, length, offset in zip(ids, runs, lengths, offsets, strict=True):
        assert run == 1 and length > 0 and offset >= 0
        for zoom in range(27):
            base = (4**zoom - 1) // 3
            if ident < base + 4**zoom:
                break
        distance = ident - base
        x = y = 0
        for bit in range(zoom):
            side = 2**bit
            rx = (distance // 2) % 2
            ry = (distance ^ rx) % 2
            if ry == 0:
                if rx == 1:
                    x, y = side - 1 - x, side - 1 - y
                x, y = y, x
            x += side * rx
            y += side * ry
            distance //= 4
        assert data[100] <= zoom <= data[101]
        start = u64(56) + offset
        result[zoom, x, y] = data[start : start + length]
    assert u64(56) + u64(64) == len(data)
    return result


def _source(root, addresses, *, complete="legacy", extra=None):
    per_zoom = {}
    expected = {}
    for i, address in enumerate(addresses):
        z, x, y = address
        path = root / f"{z}/{x}/{y}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = _png(i % 256)
        path.write_bytes(data)
        expected[address] = data
        row = per_zoom.setdefault(str(z), {"tiles": 0, "written": 0, "skipped": 0, "bytes": 0})
        row["tiles"] += 1
        row["written"] += 1
        row["bytes"] += len(data)
    index = {"bounds": [-180, -85, 180, 85], "zooms": sorted(int(z) for z in per_zoom), "per_zoom": per_zoom}
    if complete != "legacy":
        index["complete"] = complete
    index.update(extra or {})
    (root / "index.json").write_text(json.dumps(index))
    return expected


def _script(name):
    path = Path(__file__).resolve().parents[4] / f"analysis/scripts/{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "address,ident", [((0, 0, 0), 0), ((1, 0, 0), 1), ((1, 0, 1), 2), ((1, 1, 1), 3), ((1, 1, 0), 4), ((2, 0, 0), 5), ((12, 3423, 1763), 19078479)]
)
def test_spec_tile_ids(address, ident):
    assert packs.tile_id(*address) == ident


@pytest.mark.parametrize("address", [(-1, 0, 0), (27, 0, 0), (4, -1, 0), (4, 0, 16)])
def test_invalid_address(address):
    with pytest.raises(ValueError, match="invalid tile"):
        packs.tile_id(*address)


@pytest.mark.parametrize("top,levels", [(17, [6, 10, 14]), (15, [8, 12]), (13, [6, 10])])
def test_levels(top, levels):
    assert packs.pack_levels(range(8, top + 1)) == levels


@pytest.mark.parametrize("zooms", [[], [-1], [27], [8.5]])
def test_invalid_levels(zooms):
    with pytest.raises(ValueError):
        packs.pack_levels(zooms)


@pytest.mark.parametrize("parent", [(0, 0, 0), (6, 35, 10), (10, 562, 243), (14, 9030, 3860)])
def test_independent_reader_full_pack_and_exact_bytes(tmp_path, parent):
    z, x, y = parent
    addresses = [(z + d, x * 2**d + dx, y * 2**d + dy) for d in range(4) for dx in range(2**d) for dy in range(2**d)]
    source = tmp_path / "source"
    expected = _source(source, addresses)
    paths = {a: source / f"{a[0]}/{a[1]}/{a[2]}.png" for a in reversed(addresses)}
    target = tmp_path / "one.pmtiles"
    assert packs.write_pack(paths, target)
    assert _independent_read(target) == expected
    reader = packs.PackReader(target)
    assert len(reader.entries) == 85
    for address, data in expected.items():
        assert reader.read_tile(*address) == data
    assert reader.read_tile(26, 0, 0) is None
    # Geographic bounds and center are populated, in lon/lat e7 order.
    header = target.read_bytes()[:127]
    west, south, east, north = struct.unpack_from("<4i", header, 102)
    lon, lat = struct.unpack_from("<2i", header, 119)
    assert west < east and south < north
    assert west <= lon <= east and south <= lat <= north
    assert header[118] == z


def test_identical_tiles_are_not_deduplicated_and_resume_is_by_size(tmp_path):
    source = tmp_path / "tile.png"
    source.write_bytes(_png())
    target = tmp_path / "one.pmtiles"
    tiles = {(1, 0, 0): source, (1, 0, 1): source}
    assert packs.write_pack(tiles, target)
    assert list(_independent_read(target).values()) == [_png(), _png()]
    size = target.stat().st_size
    stamp = target.stat().st_mtime_ns
    assert not packs.write_pack(tiles, target)
    assert target.stat().st_mtime_ns == stamp
    target.write_bytes(target.read_bytes()[:-1])
    assert packs.write_pack(tiles, target)
    assert target.stat().st_size == size


@pytest.mark.parametrize("mode", ["empty", "too_many", "bad_png"])
def test_invalid_pack_input_does_not_leave_partial_file(tmp_path, mode):
    tile = tmp_path / "tile.png"
    tile.write_bytes(b"not a png" if mode == "bad_png" else _png())
    tiles = {} if mode == "empty" else {(7, x, 0): tile for x in range(86 if mode == "too_many" else 1)}
    with pytest.raises(ValueError):
        packs.write_pack(tiles, tmp_path / "one.pmtiles")
    assert not list(tmp_path.glob("*.pmtiles*"))


@pytest.mark.parametrize("complete", [True, False, "legacy"])
def test_completion_conventions(tmp_path, complete):
    _source(tmp_path, [(8, 140, 60)], complete=complete)
    if complete is False:
        with pytest.raises(ValueError, match="not complete"):
            packs.read_index(tmp_path / "index.json")
    else:
        assert packs.read_index(tmp_path / "index.json")["zooms"] == [8]


@pytest.mark.parametrize("change", ["row", "missing", "written", "skipped", "tiles"])
def test_legacy_inventory_refusal_names_zoom(tmp_path, change):
    _source(tmp_path, [(8, 140, 60)])
    path = tmp_path / "index.json"
    index = json.loads(path.read_text())
    if change == "row":
        index["per_zoom"] = {}
    else:
        index["per_zoom"]["8"][change] = 10
    path.write_text(json.dumps(index))
    with pytest.raises(ValueError, match="z8.*incomplete"):
        packs.read_index(path)
    index["complete"] = True
    path.write_text(json.dumps(index))
    assert packs.read_index(path)["complete"] is True


def test_tree_sparse_edges_coarse_levels_provenance_weights_and_resume(tmp_path):
    source, output = tmp_path / "source", tmp_path / "output"
    # z6 and z7 do not exist; even the z10 parent is absent. Only actual files go in.
    addresses = [(8, 140, 60), (9, 281, 121), (11, 1120, 480), (13, 4480, 1920), (13, 4496, 1920)]
    expected = _source(source, addresses, extra={"stand": "abc", "source_modified": "2026-09-18", "encoding": "terrarium"})
    index = packs.build_tree(source, output, source_index="dem/example/1/index.json")
    assert index["levels"] == [6, 10]
    assert index["tiles"] == 5 and index["complete"]
    assert index["stand"] == "abc" and index["source_modified"] == "2026-09-18"
    assert index["source_index"] == "dem/example/1/index.json"
    decoded = {}
    for path in output.glob("*/*/*.pmtiles"):
        contents = _independent_read(path)
        assert not decoded.keys() & contents.keys()
        decoded.update(contents)
        header = path.read_bytes()
        meta, length = struct.unpack_from("<2Q", header, 24)
        assert json.loads(header[meta : meta + length]) == {"encoding": "terrarium"}
    assert decoded == expected
    assert index["per_level"]["6"]["packs"] == 1
    assert index["per_level"]["10"]["packs"] == 2
    assert packs.weights_from_index(output / "index.json") == {int(z): round(row["bytes"] / row["packs"]) for z, row in index["per_level"].items()}
    resumed = packs.build_tree(source, output, source_index="dem/example/1/index.json")
    assert all(row["written"] == 0 and row["skipped"] == row["packs"] for row in resumed["per_level"].values())
    assert resumed["tiles"] == 5


def test_missing_source_file_is_refused_before_writing(tmp_path):
    source = tmp_path / "source"
    _source(source, [(8, 140, 60), (13, 4480, 1920)])
    (source / "13/4480/1920.png").unlink()
    with pytest.raises(ValueError, match="z13.*files"):
        packs.build_tree(source, tmp_path / "out", source_index="dem/example/1/index.json")
    assert not (tmp_path / "out").exists()


def test_single_parent_has_incomplete_inventory_and_no_weights(tmp_path):
    source, output = tmp_path / "source", tmp_path / "out"
    _source(source, [(8, 140, 60), (17, 71680, 30720)])
    index = packs.build_tree(source, output, source_index="tiles/example/sheet/1/index.json", parent=(14, 8960, 3840))
    assert not index["complete"] and index["tiles"] == 1
    with pytest.raises(ValueError, match="completed"):
        packs.weights_from_index(output / "index.json")
    with pytest.raises(ValueError, match="parent level"):
        packs.build_tree(source, output, source_index="index.json", parent=(12, 0, 0))
    with pytest.raises(ValueError, match="no tiles"):
        packs.build_tree(source, output, source_index="index.json", parent=(14, 0, 0))


@pytest.mark.parametrize("field,value", [("packs", 0), ("bytes", 0), ("skipped", 8)])
def test_bad_weights(tmp_path, field, value):
    row = {"packs": 1, "written": 1, "skipped": 0, "bytes": 300}
    row[field] = value
    path = tmp_path / "index.json"
    path.write_text(json.dumps({"complete": True, "levels": [6], "per_level": {"6": row}}))
    with pytest.raises(ValueError, match="z6"):
        packs.weights_from_index(path)


@pytest.mark.parametrize(
    "damage",
    [
        "magic",
        "version",
        "short_header",
        "root",
        "compression",
        "type",
        "leaves",
        "count",
        "truncated",
        "directory_count",
        "run",
        "length",
        "offset",
        "varint",
        "zoom",
        "metadata",
    ],
)
def test_reader_rejects_broken_packs(tmp_path, damage):
    tile = tmp_path / "tile.png"
    tile.write_bytes(_png())
    target = tmp_path / "one.pmtiles"
    packs.write_pack({(0, 0, 0): tile}, target)
    data = bytearray(target.read_bytes())
    changes = {
        "magic": (0, 0),
        "version": (7, 2),
        "root": (8, 0),
        "compression": (97, 2),
        "type": (99, 3),
        "leaves": (48, 1),
        "count": (80, 86),
        "directory_count": (127, 2),
        "run": (129, 0),
        "length": (130, 0),
        "offset": (131, 0),
        "varint": (127, 255),
        "zoom": (100, 1),
        "metadata": (132, 0),
    }
    if damage == "short_header":
        data = data[:126]
    elif damage == "truncated":
        data = data[:-1]
    else:
        at, value = changes[damage]
        data[at] = value
    target.write_bytes(data)
    with pytest.raises(ValueError):
        packs.PackReader(target)


def test_cli_builds_all_seven_trees_and_refuses_latest_incomplete_base(tmp_path):
    script = _script("pack_tiles")
    source, output = tmp_path / "in", tmp_path / "out"
    prefixes = [
        "tiles/lantmateriet/topowebb/1",
        "dem/lantmateriet/1",
        "shade/lantmateriet/1",
        "slope/lantmateriet/2",
        "vegetation/lantmateriet/2",
        "forest/lantmateriet/1",
        "mire/lantmateriet/3",
    ]
    for prefix in prefixes:
        _source(source / prefix, [(8, 140, 60), (13, 4480, 1920)])
    args = ["--park", "abisko", "--input-dir", str(source), "--output-dir", str(output)]
    assert script.main(args) == 0
    assert sorted(p.relative_to(output / "packs").as_posix() for p in (output / "packs").rglob("index.json")) == [
        f"{p}/index.json" for p in sorted(prefixes)
    ]
    _source(source / "tiles/lantmateriet/topowebb/2", [(17, 71680, 30720)], complete=False)
    with pytest.raises(SystemExit) as error:
        script.main(args)
    assert error.value.code == 1
    assert not (output / "packs/tiles/lantmateriet/topowebb/2").exists()


def test_cli_parent_requires_one_tree(tmp_path):
    script = _script("pack_tiles")
    with pytest.raises(SystemExit) as error:
        script.main(["--parent", "14", "8960", "3840"])
    assert error.value.code == 2


def test_interrupted_tree_resumes_completed_packs(tmp_path, monkeypatch):
    source, output = tmp_path / "source", tmp_path / "out"
    _source(source, [(8, 140, 60), (13, 4480, 1920)])
    writer = packs.write_pack
    calls = 0

    def interrupted(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("interrupted write")
        return writer(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(packs, "write_pack", interrupted)
        with pytest.raises(OSError, match="interrupted"):
            packs.build_tree(source, output, source_index="dem/example/1/index.json")
    assert json.loads((output / "index.json").read_text())["complete"] is False
    assert len(list(output.rglob("*.pmtiles"))) == 1
    resumed = packs.build_tree(source, output, source_index="dem/example/1/index.json")
    assert resumed["complete"] is True
    assert resumed["per_level"]["6"]["skipped"] == 1
    assert resumed["per_level"]["10"]["written"] == 1
