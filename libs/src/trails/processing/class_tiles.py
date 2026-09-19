"""One tree of palette PNGs out of a grid of classes: what the vegetation, forest and mire trees share.

A class grid -- ``uint8``, 0 where nothing is drawn, then one index per
class -- is warped tile by tile into the web-mercator grid, nearest while a
tile pixel is finer than a cell and the commonest class once it spans
several, and written as a palette PNG whose palette is no longer than its
classes, with the alpha in it, so the page draws it multiplied over the
sheet (analysis/docs/abisko-decisions.md §6.11, §6.13). The two cutters
that call this decide what the classes mean and what colour each is; this
module decides only how a tile is cut and written, and does it the same way
for both.
"""

import json
import time
from collections.abc import Iterable, Sequence
from pathlib import Path

import numpy as np
from affine import Affine
from PIL import Image
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject

from ..utils.tiles import TILE_PX, Bounds, tile_bounds, tile_count, tile_range, tile_resolution
from . import warp
from .shade_tiles import INDEX_FILE, TILE_CRS
from .slope_tiles import rgb

#: Pixels of ground carried round a tile while it is warped, against the
#: resampler reading past its edge.
MARGIN_PX = 2


def hatch_mask(hatch_px: int, side: int = TILE_PX) -> np.ndarray:
    """Where a hatched class is left transparent: diagonal lines in the tile's own pixels.

    Lines ``hatch_px`` wide with gaps as wide, running north-east, drawn in
    tile pixels rather than on the ground so they read as a texture at every
    zoom. The tile side is a multiple of twice the pitch, so the pattern
    continues across tile edges.

    Args:
        hatch_px: Width of a line and of the gap after it
        side: The tile's side in pixels

    Returns:
        ``(side, side)`` booleans, True where a pixel is dropped
    """
    rows, cols = np.indices((side, side))
    mask: np.ndarray = ((rows + cols) // hatch_px) % 2 == 1
    return mask


def palette(colours: Sequence[str], alpha: int) -> tuple[list[int], bytes]:
    """The PNG palette for a class image, no longer than its classes: index 0 transparent, then one per class.

    **Not padded to 256 entries, and that is most of a tile.** The slope
    classes' palette is written out in full, and a tile that draws nothing
    still carries the 768 bytes of it: 1,189 bytes for a blank against 163
    with only the entries it uses, and a tile of a few patches 1,296 against
    248 -- measured 2026-09-18. Over the forest tree, which is mostly blank,
    that is most of its weight; a busy tile is within a tenth either way.

    Args:
        colours: One ``#rrggbb`` per class
        alpha: How opaque every class is, 0 to 255

    Returns:
        The palette as a flat list, and the transparency byte per entry
    """
    flat = [0, 0, 0]
    for colour in colours:
        flat.extend(rgb(colour))
    return flat, bytes([0]) + bytes([alpha] * len(colours))


def cut(classes: np.ndarray, transform: Affine, source_crs: CRS, zoom: int, x: int, y: int, ground_m: float, cell_m: float) -> np.ndarray:
    """Warp one tile out of the class image.

    Nearest while a tile pixel is finer than a cell, so a class lands where
    its cell is; the commonest class once a pixel spans several cells, so
    a coarse level shows the ground's usual state rather than whichever cell
    happened to sit under the pixel's centre.

    Args:
        classes: The class image, ``uint8``, rows from the north
        transform: Its georeferencing
        source_crs: Its projection
        zoom: The tile's zoom
        x: Tile column
        y: Tile row
        ground_m: What one tile pixel spans on the ground, in metres
        cell_m: What one cell of the image spans, in metres

    Returns:
        The tile, ``TILE_PX`` × ``TILE_PX`` ``uint8``, 0 where nothing is drawn
    """
    west, south, east, north = tile_bounds(zoom, x, y)
    grown = (east - west) / TILE_PX * MARGIN_PX
    side = TILE_PX + 2 * MARGIN_PX
    wide = (west - grown, south - grown, east + grown, north + grown)
    patch = np.zeros((side, side), dtype=np.uint8)
    near = warp.window(classes, transform, source_crs, wide, side)
    if near is None:
        return patch[MARGIN_PX:-MARGIN_PX, MARGIN_PX:-MARGIN_PX]
    reproject(
        source=near[0],
        destination=patch,
        src_transform=near[1],
        src_crs=source_crs,
        src_nodata=None,
        dst_transform=from_bounds(*wide, side, side),
        dst_crs=TILE_CRS,
        dst_nodata=None,
        resampling=Resampling.mode if ground_m > 2.0 * cell_m else Resampling.nearest,
    )
    return patch[MARGIN_PX:-MARGIN_PX, MARGIN_PX:-MARGIN_PX]


def write_tree(
    classes: np.ndarray,
    transform: Affine,
    crs: str | CRS,
    bounds: Bounds,
    zooms: Iterable[int],
    out_dir: Path,
    kind: str,
    colours: Sequence[str],
    alpha: int,
    cell_m: float,
    extra: dict[str, object] | None = None,
    hatched: Sequence[int] = (),
    hatch_px: int = 2,
) -> dict[str, object]:
    """Cut a class image into one tree of palette PNGs, one per ``{z}/{x}/{y}``.

    Tiles already on disk are skipped, so a build resumes. What was done is
    written to ``index.json`` in the form the packer reads.

    Args:
        classes: The class image over the box, ``(rows, cols)`` ``uint8``
        transform: Its georeferencing
        crs: Its projection
        bounds: The box to cover, WGS 84
        zooms: Zoom levels to write
        out_dir: Root of the tile tree
        kind: What the tree is called, for the index and the log
        colours: One ``#rrggbb`` per class, in class order
        alpha: How opaque a class is drawn, 0 to 255
        cell_m: What one cell of the image spans, in metres
        extra: More keys for the index: what the classes mean
        hatched: Classes drawn as a diagonal hatch rather than a solid fill,
            so a reader tells them from a solid class of the same colour
            when the two do not lie side by side
        hatch_px: The hatch's line and gap width, in tile pixels

    Returns:
        The index that was written: bounds, zooms, classes, per-zoom counts and bytes
    """
    levels = sorted(set(zooms))
    out_dir.mkdir(parents=True, exist_ok=True)
    source_crs = CRS.from_user_input(crs)
    flat, clear = palette(colours, alpha)
    dropped = hatch_mask(hatch_px) if hatched else None
    middle = (bounds[1] + bounds[3]) / 2.0
    started = time.time()
    total = tile_count(bounds, levels)
    per_zoom: dict[str, dict[str, int]] = {}
    print(f"Building {total:,} {kind} tiles for z{levels[0]}–z{levels[-1]} from {classes.shape[1]:,} × {classes.shape[0]:,} cells...", flush=True)
    for zoom in levels:
        x0, y0, x1, y1 = tile_range(bounds, zoom)
        ground_m = tile_resolution(zoom, middle)
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
                tile = cut(classes, transform, source_crs, zoom, x, y, ground_m, cell_m)
                if dropped is not None:
                    tile[np.isin(tile, hatched) & dropped] = 0
                if not tile.any():
                    empty += 1
                image = Image.fromarray(np.ascontiguousarray(tile), mode="P")
                image.putpalette(flat)
                partial = target.with_suffix(".part")
                image.save(partial, format="PNG", optimize=True, transparency=clear)
                partial.replace(target)
                written += 1
                size += target.stat().st_size
        wanted = (x1 - x0 + 1) * (y1 - y0 + 1)
        elapsed = time.time() - level_started
        print(
            f"  z{zoom}: {written:,} written, {skipped:,} already there, {empty:,} blank, of {wanted:,}"
            f" — {size / 1e6:,.1f} MB, {elapsed:,.0f} s, {ground_m:.2f} m/px",
            flush=True,
        )
        per_zoom[str(zoom)] = {"tiles": wanted, "written": written, "skipped": skipped, "empty": empty, "bytes": size}
    index: dict[str, object] = {
        "kind": kind,
        "bounds": list(bounds),
        "zooms": levels,
        "tiles": total,
        "per_zoom": per_zoom,
        "colours": list(colours),
        "alpha": alpha,
        "cell_m": cell_m,
        "hatched": list(hatched),
        "hatch_px": hatch_px if hatched else 0,
        **(extra or {}),
        "seconds": round(time.time() - started, 1),
    }
    (out_dir / INDEX_FILE).write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"Done in {index['seconds']:,} s; index written to {out_dir / INDEX_FILE}", flush=True)
    return index
