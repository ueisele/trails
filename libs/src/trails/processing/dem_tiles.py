"""Height tiles: an elevation model cut into Web Mercator ``{z}/{x}/{y}.png``.

The heights a page needs -- for the profile of a planned route, for the ascent
of a chain -- come from the same tiles the map is drawn from, addressed the
same way and kept in the same offline store (analysis/docs/abisko-decisions.md
§6.3). Each tile is 256 × 256 metres-above-sea packed into RGB the way Terrarium
does it, ``(R · 256 + G + B / 256) − 32768``, which resolves 1/256 m and is
lossless in PNG. **It must stay PNG**: a later "optimise the images" pass with
a lossy codec would leave the tiles looking identical and the heights ruined.

A cell with no height is ``(0, 0, 0)``, which unpacks to −32768 m; nothing on
Earth is that low, so the reader treats it as missing.

The ceiling is z13: at 68° N a z13 pixel is 7 m, and the models behind this
are 1 m or 10 m posts read through their overviews -- finer tiles would be
the same numbers scaled up.
"""

import json
import time
from collections.abc import Iterable
from pathlib import Path

import numpy as np
from affine import Affine
from PIL import Image
from rasterio.crs import CRS
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject

from ..utils.tiles import TILE_PX, Bounds, tile_bounds, tile_count, tile_range

#: The tiles' projection.
TILE_CRS = "EPSG:3857"

#: What Terrarium adds before packing, so that heights below sea level pack too.
TERRARIUM_OFFSET = 32768.0

#: What the packed metre is divided into: a blue step is 1/256 m.
TERRARIUM_STEP = 256.0

#: The height a ``(0, 0, 0)`` cell unpacks to, and therefore what "missing" is.
MISSING_M = -TERRARIUM_OFFSET

#: Where a build records what it did, beside the tiles.
INDEX_FILE = "index.json"


def pack(heights: np.ndarray, nodata: float | None = None) -> np.ndarray:
    """Pack heights into Terrarium RGB.

    Args:
        heights: Metres above sea, any shape
        nodata: The value that means no height, packed as ``(0, 0, 0)``

    Returns:
        ``uint8`` array of shape ``heights.shape + (3,)``
    """
    metres = np.array(heights, dtype=np.float64)
    missing = ~np.isfinite(metres)
    if nodata is not None:
        missing |= metres == nodata
    metres[missing] = MISSING_M
    steps = np.rint((metres + TERRARIUM_OFFSET) * TERRARIUM_STEP)
    steps = np.clip(steps, 0, 256**3 - 1).astype(np.int64)
    steps[missing] = 0
    rgb = np.empty(metres.shape + (3,), dtype=np.uint8)
    rgb[..., 0] = steps // 65536
    rgb[..., 1] = (steps // 256) % 256
    rgb[..., 2] = steps % 256
    return rgb


def unpack(rgb: np.ndarray) -> np.ndarray:
    """Read heights back out of Terrarium RGB.

    Args:
        rgb: ``uint8`` array whose last axis is R, G, B

    Returns:
        Metres above sea as ``float32``; ``(0, 0, 0)`` comes back as :data:`MISSING_M`
    """
    r, g, b = (np.asarray(rgb[..., i], dtype=np.float64) for i in range(3))
    return (r * 256.0 + g + b / TERRARIUM_STEP - TERRARIUM_OFFSET).astype(np.float32)


def build_tiles(
    heights: np.ndarray,
    transform: Affine,
    crs: str | CRS,
    bounds: Bounds,
    zooms: Iterable[int],
    out_dir: Path,
    nodata: float | None = None,
) -> dict[str, object]:
    """Cut a height model into tiles, one PNG per ``{z}/{x}/{y}``.

    Each tile is warped out of the model on its own -- bilinear, since the
    model's posts are finer than or close to the tile's pixels at every level
    built -- and packed with :func:`pack`. Tiles already on disk are skipped,
    so a build resumes. What was done is written to ``index.json``.

    Args:
        heights: The model, one band, rows from the top
        transform: Its georeferencing
        crs: Its projection
        bounds: The box to cover, WGS 84
        zooms: Zoom levels to write
        out_dir: Root of the tile tree
        nodata: The model's no-data value, if it has one

    Returns:
        The index that was written: bounds, zooms, per-zoom counts and bytes
    """
    levels = sorted(set(zooms))
    out_dir.mkdir(parents=True, exist_ok=True)
    source_crs = CRS.from_user_input(crs)
    fill = MISSING_M if nodata is None else nodata
    model = np.asarray(heights, dtype=np.float32)
    started = time.time()
    total = tile_count(bounds, levels)
    per_zoom: dict[str, dict[str, int]] = {}
    print(f"Building {total:,} height tiles for z{levels[0]}–z{levels[-1]} from a {model.shape[1]:,} × {model.shape[0]:,} model...", flush=True)
    for zoom in levels:
        x0, y0, x1, y1 = tile_range(bounds, zoom)
        written = skipped = empty = 0
        size = 0
        level_started = time.time()
        for x in range(x0, x1 + 1):
            column = out_dir / str(zoom) / str(x)
            column.mkdir(parents=True, exist_ok=True)
            for y in range(y0, y1 + 1):
                target = column / f"{y}.png"
                if target.exists() and target.stat().st_size > 0:
                    skipped += 1
                    size += target.stat().st_size
                    continue
                tile = np.full((TILE_PX, TILE_PX), fill, dtype=np.float32)
                reproject(
                    source=model,
                    destination=tile,
                    src_transform=transform,
                    src_crs=source_crs,
                    src_nodata=nodata,
                    dst_transform=from_bounds(*tile_bounds(zoom, x, y), TILE_PX, TILE_PX),
                    dst_crs=TILE_CRS,
                    dst_nodata=fill,
                    resampling=Resampling.bilinear,
                )
                if np.all(tile == fill):
                    empty += 1
                partial = target.with_suffix(".part")
                Image.fromarray(pack(tile, fill), mode="RGB").save(partial, format="PNG", optimize=True)
                partial.replace(target)
                written += 1
                size += target.stat().st_size
        wanted = (x1 - x0 + 1) * (y1 - y0 + 1)
        elapsed = time.time() - level_started
        print(
            f"  z{zoom}: {written:,} written, {skipped:,} already there, {empty:,} without ground, of {wanted:,}"
            f" — {size / 1e6:,.1f} MB, {elapsed:,.0f} s",
            flush=True,
        )
        per_zoom[str(zoom)] = {"tiles": wanted, "written": written, "skipped": skipped, "empty": empty, "bytes": size}
    index: dict[str, object] = {
        "bounds": list(bounds),
        "zooms": levels,
        "tiles": total,
        "per_zoom": per_zoom,
        "encoding": "terrarium",
        "missing": "rgb(0,0,0)",
        "seconds": round(time.time() - started, 1),
    }
    (out_dir / INDEX_FILE).write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"Done in {index['seconds']:,} s; index written to {out_dir / INDEX_FILE}", flush=True)
    return index
