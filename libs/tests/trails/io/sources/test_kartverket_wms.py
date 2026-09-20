"""WMS rendering and snapshot accounting, with every service request mocked.

The capabilities fixture is the unmodified WMS GetCapabilities response fetched
2026-09-18 from kartverket_wms.URL, not Kartverket's separate WMTS document.
"""

import hashlib
import importlib.util
import io
import json
import math
import subprocess
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests
from PIL import Image
from trails.io.sources import kartverket_wms as wms
from trails.processing.trees import TREES
from trails.utils.tiles import tile_bounds, tile_range

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures/kartverket_wms_capabilities.xml"
SCRIPT = Path(__file__).resolve().parents[5] / "analysis/scripts/kartverket_tiles.py"


@pytest.fixture
def source():
    return wms.Source(FIXTURE.read_bytes())


@pytest.fixture
def script():
    spec = importlib.util.spec_from_file_location("kartverket_tiles", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _response(body=b"", status=200, headers=None):
    response = requests.Response()
    response.status_code = status
    response._content = body
    response._content_consumed = True
    response.headers.update(headers or {})
    return response


def _png(mode="P", size=(2560, 2560)):
    with Image.new("P", size) as picture:
        picture.putpalette([v for i in range(256) for v in ((i % 10) * 20, (i // 10 % 10) * 20, 0)])
        for row in range(10):
            for col in range(10):
                picture.paste(row * 10 + col, (col * 256, row * 256, (col + 1) * 256, (row + 1) * 256))
        data = io.BytesIO()
        picture.convert(mode).save(data, format="PNG")
        return data.getvalue()


def _box(zoom=8, x0=135, y0=63, x1=136, y1=64):
    """A box strictly inside the outside edges of the named tile rectangle."""
    n = 2**zoom

    def lat(y):
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))

    return (360 * (x0 + 0.1) / n - 180, lat(y1 + 0.9), 360 * (x1 + 0.9) / n - 180, lat(y0 + 0.1))


def test_capabilities_order_and_stand(source, monkeypatch):
    assert len(source.layers) == 189  # the 2026-09-18 WMS document; the plan recorded 188
    assert source.layers[:4] == ["n2000hoydelag", "n1000hoydelag", "n500hoydelag", "n250hoydelag"]
    assert source.layers[-3:] == ["vegnavn_eur_riks_nr", "vegnavn", "adresse"]
    assert "fjellskygge" not in source.layers
    assert "topo" not in source.layers
    expected = json.dumps([wms.URL, "1.3.0", "EPSG:3857", "image/png8", source.layers], separators=(",", ":"), ensure_ascii=False)
    assert source.stand == hashlib.sha256(expected.encode()).hexdigest()[:16]
    changed = FIXTURE.read_bytes().replace(b"<Name>adresse</Name>", b"<Name>adresse_new</Name>")
    assert wms.Source(changed).stand != source.stand
    reordered = (
        FIXTURE.read_bytes().replace(b"<Name>adresse</Name>", b"<Name>vegnavn</Name>").replace(b"<Name>vegnavn</Name>", b"<Name>adresse</Name>", 1)
    )
    assert wms.Source(reordered).stand != source.stand
    for field in ("URL", "VERSION", "CRS", "FORMAT"):
        with monkeypatch.context() as patch:
            patch.setattr(wms, field, getattr(wms, field) + "-changed")
            if field == "VERSION":
                patch.setattr(wms, "_layers", lambda _: source.layers)
            assert wms.Source(FIXTURE.read_bytes()).stand != source.stand


@pytest.mark.parametrize(
    "document",
    [
        b'<Capabilities xmlns="http://www.opengis.net/wmts/1.0" version="1.0.0"/>',
        b'<WMS_Capabilities xmlns="http://www.opengis.net/wms" version="1.3.0"/>',
        b'<WMS_Capabilities xmlns="http://www.opengis.net/wms" version="1.3.0"><Layer><Name>topo</Name></Layer></WMS_Capabilities>',
    ],
)
def test_bad_capabilities(document):
    with pytest.raises(ValueError):
        wms.Source(document)


def test_live_capabilities_request_is_mocked(source, monkeypatch):
    get = Mock(return_value=_response(FIXTURE.read_bytes()))
    monkeypatch.setattr(wms.requests, "get", get)
    assert wms.Source().stand == source.stand
    assert get.call_args.kwargs["params"] == {"SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetCapabilities"}


def test_versions_resume_latest_even_when_unfinished(source, tmp_path):
    assert wms.version_for(tmp_path, source.stand) == (1, True)
    assert wms.version_for(tmp_path, source.stand) == (1, False)
    assert not (tmp_path / "1/index.json").exists()
    assert wms.version_for(tmp_path, source.stand, new_version=True) == (2, True)
    assert wms.version_for(tmp_path, source.stand) == (2, False)
    assert wms.version_for(tmp_path, "different") == (3, True)
    assert wms.version_for(tmp_path, source.stand) == (4, True), "do not resume an older snapshot"


def test_current_version_requires_completion(source, tmp_path):
    assert wms.current_version(tmp_path) is None
    wms.version_for(tmp_path, source.stand)
    index = tmp_path / "1/index.json"
    index.write_text(json.dumps({"complete": False}))
    assert wms.current_version(tmp_path) is None
    index.write_text(json.dumps({"complete": True}))
    assert wms.current_version(tmp_path) == 1
    wms.version_for(tmp_path, source.stand, new_version=True)
    (tmp_path / "2/index.json").write_text(json.dumps({"complete": False}))
    assert wms.current_version(tmp_path) == 1
    assert wms.version_for(tmp_path, source.stand) == (2, False)


@pytest.mark.parametrize("mode", ["P", "RGB", "RGBA"])
def test_metatile_request_and_palette(source, monkeypatch, mode):
    get = Mock(return_value=_response(_png(mode)))
    monkeypatch.setattr(wms.requests, "get", get)
    with source._render(13, 4384, 2096) as picture:
        assert picture.mode == "P"
        assert picture.size == (2560, 2560)
        if mode == "P":
            assert picture.getpixel((256, 256)) == 11
    params = get.call_args.kwargs["params"]
    assert params == {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetMap",
        "CRS": "EPSG:3857",
        "FORMAT": "image/png8",
        "LAYERS": ",".join(source.layers),
        "STYLES": "",
        "WIDTH": "2560",
        "HEIGHT": "2560",
        "TRANSPARENT": "FALSE",
        "EXCEPTIONS": "XML",
        "BBOX": params["BBOX"],
    }
    west, _, _, north = tile_bounds(13, 4383, 2095)
    _, south, east, _ = tile_bounds(13, 4392, 2104)
    assert list(map(float, params["BBOX"].split(","))) == [west, south, east, north]


def test_copy_crops_margins_and_resumes_individual_tiles(source, monkeypatch, tmp_path):
    get = Mock(side_effect=lambda *args, **kwargs: _response(_png()))
    monkeypatch.setattr(wms.requests, "get", get)
    bounds = _box()
    first = source.copy_tiles(bounds, [8, 8], tmp_path)
    assert get.call_count == 4, "the four wanted tiles straddle four metatiles"
    assert first["complete"]
    assert first["source_modified"] == datetime.now(UTC).date().isoformat()
    assert first["stand"] == source.stand
    files = list(tmp_path.rglob("*.png"))
    assert len(files) == 4
    for path in files:
        x, y = int(path.parent.name), int(path.stem)
        with Image.open(path) as tile:
            assert tile.mode == "P" and tile.size == (256, 256)
            assert tile.convert("RGB").getpixel((0, 0)) == ((x % 8 + 1) * 20, (y % 8 + 1) * 20, 0)
    assert first["per_zoom"]["8"] == {"tiles": 4, "written": 4, "skipped": 0, "missing": 0, "bytes": sum(p.stat().st_size for p in files)}
    first["source_modified"] = "2026-01-02"
    (tmp_path / "index.json").write_text(json.dumps(first))
    kept = tmp_path / "8/135/63.png"
    kept.write_bytes(b"kept exactly, even if a neighbouring tile needs rendering")
    (tmp_path / "8/136/64.png").write_bytes(b"")
    (tmp_path / "8/136/64.part").write_bytes(b"interrupted write")
    get.reset_mock()
    second = source.copy_tiles(bounds, [8], tmp_path)
    assert get.call_count == 1
    assert second["source_modified"] == "2026-01-02"
    assert second["per_zoom"]["8"]["written"] == 1
    assert second["per_zoom"]["8"]["skipped"] == 3
    assert second["per_zoom"]["8"]["bytes"] == sum(p.stat().st_size for p in files)
    assert kept.read_bytes().startswith(b"kept exactly")
    get.reset_mock()
    source.copy_tiles(bounds, [8], tmp_path)
    get.assert_not_called()
    assert not list(tmp_path.rglob("*.part"))


def test_interruption_records_date_and_resumes(source, monkeypatch, tmp_path):
    def fail(*args, **kwargs):
        started = json.loads((tmp_path / "index.json").read_text())
        assert started["source_modified"] == datetime.now(UTC).date().isoformat()
        assert not started["complete"]
        raise requests.ConnectionError("interrupted")

    monkeypatch.setattr(wms.requests, "get", fail)
    monkeypatch.setattr(wms.time, "sleep", Mock())
    bounds = _box(x1=135, y1=63)
    with pytest.raises(RuntimeError, match="ConnectionError: interrupted"):
        source.copy_tiles(bounds, [8], tmp_path)
    previous = json.loads((tmp_path / "index.json").read_text())
    assert not previous["complete"]
    with pytest.raises(ValueError, match="completed"):
        wms.weights_from_index(tmp_path / "index.json")
    monkeypatch.setattr(wms.requests, "get", lambda *args, **kwargs: _response(_png()))
    final = source.copy_tiles(bounds, [8], tmp_path)
    assert final["complete"] and final["source_modified"] == previous["source_modified"]


def test_extend_preserves_existing_levels_and_rejects_mixed_tree(source, monkeypatch, tmp_path):
    monkeypatch.setattr(wms.requests, "get", lambda *args, **kwargs: _response(_png()))
    bounds = _box(zoom=9, x0=271, x1=271, y0=127, y1=127)
    source.copy_tiles(bounds, [8], tmp_path)
    index = source.copy_tiles(bounds, [9], tmp_path)
    assert index["zooms"] == [8, 9]
    assert index["per_zoom"]["8"]["skipped"] == 1
    assert set(wms.weights_from_index(tmp_path / "index.json")) == {8, 9}
    with pytest.raises(ValueError, match="bounds differ"):
        source.copy_tiles(_box(), [8], tmp_path)
    source.stand = "changed"
    with pytest.raises(ValueError, match="configuration differs"):
        source.copy_tiles(bounds, [8], tmp_path)


@pytest.mark.parametrize("zooms", [[], [7], [18], [8.5]])
def test_invalid_zooms(source, tmp_path, zooms):
    with pytest.raises(ValueError, match="zooms"):
        source.copy_tiles(_box(), zooms, tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("bounds", [(13, 65, 12, 66), (12, 66, 13, 65), (12, 65, 13, 90), (12, 65, math.nan, 66)])
def test_invalid_bounds(source, tmp_path, bounds):
    with pytest.raises(ValueError, match="bounds"):
        source.copy_tiles(bounds, [8], tmp_path)


@pytest.mark.parametrize("status", [429, 500, 503, 599])
def test_retry_backoff(monkeypatch, status):
    get = Mock(side_effect=[_response(status=status), _response(status=status), _response(b"answer")])
    sleep = Mock()
    monkeypatch.setattr(wms.requests, "get", get)
    monkeypatch.setattr(wms.time, "sleep", sleep)
    assert wms._request({"REQUEST": "GetMap"}) == b"answer"
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2]


@pytest.mark.parametrize(
    "error_type",
    [requests.exceptions.ConnectionError, requests.exceptions.SSLError, requests.exceptions.Timeout, requests.exceptions.ChunkedEncodingError],
)
@pytest.mark.parametrize("recover", [True, False])
def test_connection_failures_retry_with_bounded_backoff(monkeypatch, error_type, recover):
    errors = [error_type(f"dropped connection {attempt + 1}") for attempt in range(wms.ATTEMPTS)]
    get = Mock(side_effect=[*errors[:-1], _response(b"answer") if recover else errors[-1]])
    sleep = Mock()
    monkeypatch.setattr(wms.requests, "get", get)
    monkeypatch.setattr(wms.time, "sleep", sleep)
    if recover:
        assert wms._request({"REQUEST": "GetMap"}) == b"answer"
    else:
        with pytest.raises(RuntimeError, match=f"WMS GetMap failed: {error_type.__name__}: dropped connection {wms.ATTEMPTS}") as caught:
            wms._request({"REQUEST": "GetMap"})
        assert caught.value.__cause__ is errors[-1]
    assert get.call_count == wms.ATTEMPTS
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2, 4]


@pytest.mark.parametrize("last_is_connection_error", [True, False])
def test_connection_and_http_failures_share_retry_budget(monkeypatch, last_is_connection_error):
    error = requests.exceptions.SSLError("connection dropped")
    failure = _response(b"service unavailable", status=503, headers={"Retry-After": "3"})
    replies = [failure, error, failure, error] if last_is_connection_error else [error, failure, error, failure]
    get = Mock(side_effect=replies)
    sleep = Mock()
    monkeypatch.setattr(wms.requests, "get", get)
    monkeypatch.setattr(wms.time, "sleep", sleep)
    expected = "SSLError: connection dropped" if last_is_connection_error else "HTTP 503: service unavailable"
    with pytest.raises(RuntimeError, match=expected):
        wms._request({"REQUEST": "GetMap"})
    assert get.call_count == wms.ATTEMPTS
    assert [call.args[0] for call in sleep.call_args_list] == ([3, 2, 4] if last_is_connection_error else [1, 3, 4])


@pytest.mark.parametrize("retry_after,expected", [("12", 12), ("Fri, 18 Sep 2026 00:00:10 GMT", 10), ("bad", 1)])
def test_retry_after(monkeypatch, retry_after, expected):
    monkeypatch.setattr(wms.time, "time", lambda: datetime(2026, 9, 18, tzinfo=UTC).timestamp())
    monkeypatch.setattr(wms.requests, "get", Mock(side_effect=[_response(status=429, headers={"Retry-After": retry_after}), _response(b"ok")]))
    sleep = Mock()
    monkeypatch.setattr(wms.time, "sleep", sleep)
    assert wms._request({"REQUEST": "GetMap"}) == b"ok"
    sleep.assert_called_once_with(expected)


@pytest.mark.parametrize("status,calls", [(201, 1), (302, 1), (400, 1), (403, 1), (404, 1), (429, 4), (500, 4)])
def test_http_failures_are_clear_and_bounded(monkeypatch, status, calls):
    get = Mock(side_effect=lambda *args, **kwargs: _response(b"service says no", status=status))
    monkeypatch.setattr(wms.requests, "get", get)
    monkeypatch.setattr(wms.time, "sleep", Mock())
    with pytest.raises(RuntimeError, match=f"HTTP {status}: service says no"):
        wms._request({"REQUEST": "GetMap"})
    assert get.call_count == calls


@pytest.mark.parametrize("body", [b"<ServiceExceptionReport>bad layer</ServiceExceptionReport>", _png(size=(256, 256))])
def test_bad_map_answer_is_not_written(source, monkeypatch, tmp_path, body):
    monkeypatch.setattr(wms.requests, "get", lambda *args, **kwargs: _response(body))
    with pytest.raises(ValueError, match="WMS"):
        source.copy_tiles(_box(x1=135, y1=63), [8], tmp_path)
    assert not list(tmp_path.rglob("*.png"))
    assert not json.loads((tmp_path / "index.json").read_text())["complete"]


def test_at_most_two_requests_in_flight(source, monkeypatch, tmp_path):
    lock = threading.Lock()
    ready = threading.Event()
    active = maximum = calls = 0
    png = _png()

    def get(*args, **kwargs):
        nonlocal active, maximum, calls
        with lock:
            active += 1
            calls += 1
            maximum = max(maximum, active)
            if active == 2:
                ready.set()
        assert ready.wait(5), "two requests should be able to progress together"
        with lock:
            active -= 1
        return _response(png)

    monkeypatch.setattr(wms.requests, "get", get)
    source.copy_tiles(_box(), [8], tmp_path)
    assert maximum == 2 and calls == 4


def test_weights_count_skipped_bytes_and_reject_missing(tmp_path):
    path = tmp_path / "index.json"
    index = {"complete": True, "zooms": [8], "per_zoom": {"8": {"tiles": 3, "written": 1, "skipped": 2, "missing": 0, "bytes": 32}}}
    path.write_text(json.dumps(index))
    assert wms.weights_from_index(path) == {8: 11}
    index["per_zoom"]["8"]["missing"] = 1
    path.write_text(json.dumps(index))
    with pytest.raises(ValueError, match="incomplete"):
        wms.weights_from_index(path)


@pytest.mark.parametrize("park", ["abisko", "malingsbo-kloten"])
def test_swedish_dispatch_preserves_the_map_and_arguments(script, monkeypatch, park):
    run = Mock(return_value=subprocess.CompletedProcess([], 7))
    monkeypatch.setattr(script.subprocess, "run", run)
    assert script.main(["--park", park, "--max-zoom", "13", "--tree-root", "/tmp/a tree"]) == 7
    run.assert_called_once_with(
        [sys.executable, str(SCRIPT.with_name("lantmateriet_tiles.py")), "--park", park, "--max-zoom", "13", "--tree-root", "/tmp/a tree"],
        check=False,
    )


def test_script_uses_tree_box_and_new_version(script, source, monkeypatch, tmp_path):
    copy = Mock()
    monkeypatch.setattr(source, "copy_tiles", copy)
    monkeypatch.setattr(script.kartverket_wms, "Source", lambda: source)
    monkeypatch.setattr(script.kartverket_wms, "weights_from_index", lambda _: {8: 123})
    args = ["--park", "lomsdal-visten", "--tree-root", str(tmp_path), "--max-zoom", "8"]
    assert script.main(args) == 0
    copy.assert_called_with(TREES["lomsdal-visten"].box, range(8, 9), tmp_path / "1")
    assert script.main([*args, "--new-version"]) == 0
    copy.assert_called_with(TREES["lomsdal-visten"].box, range(8, 9), tmp_path / "2")


def test_script_weights_are_offline(script, monkeypatch, tmp_path, capsys):
    path = tmp_path / "index.json"
    path.write_text(
        json.dumps({"complete": True, "zooms": [8], "per_zoom": {"8": {"tiles": 1, "written": 1, "skipped": 0, "missing": 0, "bytes": 32}}})
    )
    get = Mock(side_effect=AssertionError("weights must not fetch the WMS"))
    monkeypatch.setattr(wms.requests, "get", get)
    assert script.main(["--weights-from", str(path)]) == 0
    assert capsys.readouterr().out.strip() == "{8: 32}"
    get.assert_not_called()


def test_make_dispatch_dry_run():
    result = subprocess.run(
        ["bash", "-c", "command make -n tiles PARK=abisko ARGS='--max-zoom 13'"], cwd=SCRIPT.parents[2], capture_output=True, text=True, check=True
    )
    assert "kartverket_tiles.py --park abisko --max-zoom 13" in result.stdout
    assert tile_range(_box(), 8) == (135, 63, 136, 64)
