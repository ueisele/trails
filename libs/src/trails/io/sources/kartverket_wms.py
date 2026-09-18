"""Kartverket's topographic WMS, cut into palette XYZ tiles without hillshade.

A WMS has no data stand to read: Kartverket updates continuously, so the copy
is a snapshot and its stand identifies the rendering configuration, not the data.

The stand is the first 16 hex digits of SHA-256 over compact UTF-8 JSON of
``[URL, VERSION, CRS, FORMAT, ordered_layers]``. The leaves of ``topo`` retain
capabilities order, with ``fjellskygge`` removed. A changed configuration or
an operator's explicit new version opens a new directory; nothing detects a
change to the map's content. ``source_modified`` is the UTC date the first
copy into that directory started, retained on resume.

Each request draws eight by eight tiles with a one-tile margin (2560 px).
Only the inner tiles intersecting the box are written, atomically, as palette
PNG. Nonempty tiles already on disk are kept. At most two requests run at
once; only HTTP 429 and 5xx are retried, with exponential backoff.

The index has Lantmäteriet's inventory fields: ``per_zoom.bytes`` counts all
tiles on disk, including skipped tiles, rather than this run's writes alone.
It also records ``stand`` and ``complete``: it is written before the first
render to preserve the snapshot date, and marked complete only after success.
Readers must check ``complete`` before treating this index as a finished tree.
"""

import hashlib
import io
import json
import math
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import requests
from PIL import Image, UnidentifiedImageError

from ...utils.tiles import TILE_PX, Bounds, tile_bounds, tile_count, tile_range
from .lantmateriet import INDEX_FILE, STAND_FILE, versions

URL = "https://wms.geonorge.no/skwms1/wms.topo"
VERSION = "1.3.0"
CRS = "EPSG:3857"
FORMAT = "image/png8"
MIN_ZOOM = 8
MAX_ZOOM = 17
METATILE = 8
MARGIN = 1
REQUEST_PX = (METATILE + 2 * MARGIN) * TILE_PX
ATTEMPTS = 4
_NS = "{http://www.opengis.net/wms}"


def _request(params: dict[str, str]) -> bytes:
    """Read one WMS answer, backing off on connection, throttling and server failures."""
    for attempt in range(ATTEMPTS):
        try:
            with requests.get(URL, params={"SERVICE": "WMS", "VERSION": VERSION, **params}, timeout=(15, 120), allow_redirects=False) as response:
                if response.status_code == 200:
                    return response.content
                if (response.status_code == 429 or 500 <= response.status_code < 600) and attempt < ATTEMPTS - 1:
                    delay = float(2**attempt)
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = max(delay, float(retry_after))
                        except ValueError:
                            try:
                                delay = max(delay, parsedate_to_datetime(retry_after).timestamp() - time.time())
                            except ValueError, TypeError, OverflowError:
                                pass
                    print(f"WMS HTTP {response.status_code}; retry {attempt + 1}/{ATTEMPTS - 1} in {delay:g} s", flush=True)
                else:
                    raise RuntimeError(f"WMS {params['REQUEST']} failed: HTTP {response.status_code}: {response.text[:500]}")
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.ChunkedEncodingError) as error:
            if attempt == ATTEMPTS - 1:
                raise RuntimeError(f"WMS {params['REQUEST']} failed: {type(error).__name__}: {error}") from error
            delay = float(2**attempt)
            print(f"WMS {type(error).__name__}: {error}; retry {attempt + 1}/{ATTEMPTS - 1} in {delay:g} s", flush=True)
        time.sleep(delay)
    raise AssertionError("retry loop exhausted")  # pragma: no cover


def _layers(capabilities: bytes) -> list[str]:
    """Read the topo leaves in document order, excluding its hillshade."""
    root = ET.fromstring(capabilities)
    if root.tag != f"{_NS}WMS_Capabilities" or root.get("version") != VERSION:
        raise ValueError("expected WMS 1.3.0 capabilities")
    group = next((layer for layer in root.iter(f"{_NS}Layer") if layer.findtext(f"{_NS}Name") == "topo"), None)
    if group is None:
        raise ValueError("WMS capabilities have no topo group")
    leaves = [layer.findtext(f"{_NS}Name") for layer in group.iter(f"{_NS}Layer") if not layer.findall(f"{_NS}Layer")]
    if not leaves or any(not name for name in leaves) or "fjellskygge" not in leaves:
        raise ValueError("topo must have named leaves including fjellskygge")
    return [name for name in leaves if name and name != "fjellskygge"]


def version_for(root: Path, stand: str, *, new_version: bool = False) -> tuple[int, bool]:
    """Resume the newest directory, or open the next for a new configuration.

    Unlike Lantmäteriet's completed-version lookup, include unfinished copies:
    their stand file is enough to resume after an interruption. Never return
    to an older directory when a configuration changes back.

    Args:
        root: Tree root, normally ``tiles/kartverket/topo``.
        stand: The configuration hash from :class:`Source`.
        new_version: Open a fresh snapshot even if the configuration matches.

    Returns:
        The numeric version and whether its directory was created.
    """
    latest = (versions(root) or [0])[-1]
    marker = root / str(latest) / STAND_FILE
    if not new_version and marker.is_file() and marker.read_text(encoding="utf-8").strip() == stand:
        return latest, False
    directory = root / str(latest + 1)
    directory.mkdir(parents=True)
    (directory / STAND_FILE).write_text(stand + "\n", encoding="utf-8")
    return latest + 1, True


def current_version(root: Path) -> int | None:
    """Find the newest completed snapshot, excluding copies still under way.

    This is Lantmäteriet's completed-version lookup with an explicit completion
    check: a WMS index exists from the start to preserve the snapshot date.

    Args:
        root: Tree root, normally ``tiles/kartverket/topo``.

    Returns:
        The version, or None if no snapshot has finished.
    """
    for version in reversed(versions(root)):
        index = root / str(version) / INDEX_FILE
        if index.exists() and json.loads(index.read_text(encoding="utf-8")).get("complete"):
            return version
    return None


def weights_from_index(path: Path) -> dict[int, int]:
    """Derive mean bytes per tile, as for Lantmäteriet's provider weights.

    Args:
        path: A completed tree's ``index.json``.

    Returns:
        Zoom to mean bytes per tile, rounded to the nearest integer.

    Raises:
        ValueError: If the inventory is incomplete or has missing tiles.
    """
    index = json.loads(path.read_text(encoding="utf-8"))
    if not index.get("complete") or not index.get("zooms"):
        raise ValueError("weights require a completed tree")
    weights = {}
    for zoom in index["zooms"]:
        row = index["per_zoom"][str(zoom)]
        if row["missing"] or row["tiles"] <= 0 or row["written"] + row["skipped"] != row["tiles"] or row["bytes"] <= 0:
            raise ValueError(f"z{zoom} has an incomplete inventory")
        weights[int(zoom)] = round(row["bytes"] / row["tiles"])
    return weights


def _write_index(path: Path, index: dict[str, Any]) -> None:
    partial = path.with_suffix(".part")
    partial.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    partial.replace(path)


class Source:
    """The flat topo sheet rendered by the public WMS."""

    def __init__(self, capabilities: bytes | None = None):
        """Read the layer configuration.

        Args:
            capabilities: Saved WMS capabilities, or None to read the service.
        """
        self.layers = _layers(capabilities if capabilities is not None else _request({"REQUEST": "GetCapabilities"}))
        configuration = json.dumps([URL, VERSION, CRS, FORMAT, self.layers], ensure_ascii=False, separators=(",", ":"))
        self.stand = hashlib.sha256(configuration.encode("utf-8")).hexdigest()[:16]

    def _render(self, zoom: int, x: int, y: int) -> Image.Image:
        west, _, _, north = tile_bounds(zoom, x - MARGIN, y - MARGIN)
        _, south, east, _ = tile_bounds(zoom, x + METATILE + MARGIN - 1, y + METATILE + MARGIN - 1)
        data = _request({
            "REQUEST": "GetMap", "CRS": CRS, "FORMAT": FORMAT, "LAYERS": ",".join(self.layers),
            "STYLES": "", "BBOX": f"{west},{south},{east},{north}", "WIDTH": str(REQUEST_PX),
            "HEIGHT": str(REQUEST_PX), "TRANSPARENT": "FALSE", "EXCEPTIONS": "XML",
        })  # fmt: skip
        try:
            with Image.open(io.BytesIO(data)) as picture:
                if picture.format != "PNG" or picture.size != (REQUEST_PX, REQUEST_PX):
                    raise ValueError(f"WMS returned {picture.format} {picture.size}, expected PNG {(REQUEST_PX, REQUEST_PX)}")
                # One palette per metatile; retain the server's palette unchanged.
                return picture.copy() if picture.mode == "P" else picture.quantize(colors=256)
        except UnidentifiedImageError as error:
            raise ValueError(f"WMS GetMap returned no PNG: {data[:500]!r}") from error

    def _copy_metatile(self, job: tuple[int, int, int, tuple[int, int, int, int], Path]) -> tuple[int, int, int]:
        zoom, mx, my, limits, out_dir = job
        x0, y0, x1, y1 = limits
        missing: list[tuple[int, int, Path]] = []
        skipped = size = 0
        for x in range(max(mx, x0), min(mx + METATILE - 1, x1) + 1):
            for y in range(max(my, y0), min(my + METATILE - 1, y1) + 1):
                target = out_dir / str(zoom) / str(x) / f"{y}.png"
                held = target.stat().st_size if target.exists() else 0
                if held:
                    skipped += 1
                    size += held
                else:
                    missing.append((x, y, target))
        if missing:
            with self._render(zoom, mx, my) as picture:
                for x, y, target in missing:
                    left, top = (x - mx + MARGIN) * TILE_PX, (y - my + MARGIN) * TILE_PX
                    target.parent.mkdir(parents=True, exist_ok=True)
                    partial = target.with_suffix(".part")
                    with picture.crop((left, top, left + TILE_PX, top + TILE_PX)) as tile:
                        tile.save(partial, format="PNG", optimize=True)
                    size += partial.stat().st_size
                    partial.replace(target)
        return len(missing), skipped, size

    def copy_tiles(self, bounds: Bounds, zooms: Iterable[int], out_dir: Path) -> dict[str, Any]:
        """Render a box to a resumable XYZ tree and write its inventory.

        Args:
            bounds: WGS84 box, west, south, east, north.
            zooms: Nonempty set of levels from z8 through z17.
            out_dir: A version directory; never mix configurations or boxes.

        Returns:
            The index, including all existing levels and skipped tiles' bytes.

        Raises:
            ValueError: If bounds, zooms, or an existing tree are incompatible.
            RuntimeError: If the WMS refuses a request or exhausts retries.
        """
        levels = sorted(set(zooms))
        if not levels or any(not isinstance(z, int) or not MIN_ZOOM <= z <= MAX_ZOOM for z in levels):
            raise ValueError(f"zooms must be nonempty and within z{MIN_ZOOM}–z{MAX_ZOOM}")
        west, south, east, north = bounds
        if not all(math.isfinite(v) for v in bounds) or not (-180 <= west < east < 180 and -85.05112878 < south < north < 85.05112878):
            raise ValueError("bounds must be an ordered WGS84 box inside Web Mercator")
        out_dir.mkdir(parents=True, exist_ok=True)
        marker = out_dir / STAND_FILE
        index_path = out_dir / INDEX_FILE
        if marker.exists() and marker.read_text(encoding="utf-8").strip() != self.stand:
            raise ValueError("configuration differs: open a new version directory")
        previous = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
        if previous and (previous.get("stand") != self.stand or previous.get("bounds") != list(bounds)):
            raise ValueError("configuration or bounds differ: open a new version directory")
        levels = sorted(set(levels) | set(previous.get("zooms", [])))
        marker.write_text(self.stand + "\n", encoding="utf-8")
        index: dict[str, Any] = {
            "source": URL,
            "source_modified": previous.get("source_modified", datetime.now(UTC).date().isoformat()),
            "stand": self.stand,
            "complete": False,
            "bounds": list(bounds),
            "zooms": levels,
            "tiles": tile_count(bounds, levels),
            "per_zoom": {},
            "seconds": 0.0,
            "transfer": None,
        }
        _write_index(index_path, index)
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=2) as pool:
            for zoom in levels:
                limits = tile_range(bounds, zoom)

                def jobs(zoom: int, limits: tuple[int, int, int, int]) -> Iterator[tuple[int, int, int, tuple[int, int, int, int], Path]]:
                    x0, y0, x1, y1 = limits
                    for mx in range(x0 // METATILE * METATILE, x1 + 1, METATILE):
                        for my in range(y0 // METATILE * METATILE, y1 + 1, METATILE):
                            yield zoom, mx, my, limits, out_dir

                written = skipped = size = 0
                for count, (new, kept, held) in enumerate(pool.map(self._copy_metatile, jobs(zoom, limits), buffersize=2), 1):
                    written += new
                    skipped += kept
                    size += held
                    if count % 100 == 0:
                        print(f"  z{zoom}: {written:,} written, {skipped:,} skipped so far", flush=True)
                index["per_zoom"][str(zoom)] = {
                    "tiles": written + skipped, "written": written, "skipped": skipped, "missing": 0, "bytes": size,
                }  # fmt: skip
                print(f"  z{zoom}: {written:,} written, {skipped:,} skipped; {size / 1e6:,.1f} MB", flush=True)
                index["seconds"] = round(time.monotonic() - started, 1)
                _write_index(index_path, index)
        index["complete"] = True
        _write_index(index_path, index)
        return index
