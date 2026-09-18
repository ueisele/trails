"""Vegetation tiles: how much stands between knee and head height, and where the trees are.

**The question the sheet does not answer.** A map draws forest, open ground and
water, and a walker leaving the path wants to know something else: whether
the open ground is heath they can stride over or willow they will push
through at a kilometre an hour. The laser knows. Both countries' height
models carry every return off the vegetation, and Sweden's NMD 2018 has
already classed them at 10 m -- the height of what stands between 0.5 and
5 m and how much of each cell it covers -- so this module colours that, and
Norway's side is computed from the same two models to the same codes
(:mod:`trails.io.sources.nmd`, :mod:`trails.io.sources.hoydedata_vegetation`;
analysis/docs/abisko-decisions.md §6.11).

**Two trees, because they answer two questions.** *Vegetation* is the cover
of what stands between 0.5 and 5 m, in six steps from a tenth of the cell to
all of it -- knee-high dwarf birch and head-high willow alike, since the
laser's height class turned out to matter less than its cover once looked
at over the Abisko box: 26 % of the ground carries something in the band and
only 4 % carries it at more than 40 %. *Forest* is where trees over 5 m
stand on at least 30 % of a cell, a different thing drawn in a different
colour and switched separately: high forest is usually easy ground, and the
sheet draws its own idea of it, so this is the laser's word on where the
sheet is right. Measured over Abisko, 1.7 % of the box.

**One hue, six lightness steps, multiplied.** The page draws both layers the
way it draws the slope classes -- palette PNG with the alpha in it,
``mix-blend-mode: multiply`` -- so the sheet's lettering stays black under
them. The vegetation ramp is teal, chosen on the mockup against green, which
vanished into the sheet's own forest green, and violet; the forest is a
sepia. All three were stepped in OKLCH and run through the palette
validator: the ramp reads light to dark with every step at least 0.06 apart
and its light end over 2:1 on the sheet, and the sepia stands at least
ΔE 15.6 from every teal step under simulated colour blindness (2026-09-18).
"""

import json
import math
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

from ..io.sources.nmd import UNKNOWN
from ..utils.tiles import TILE_PX, Bounds, tile_bounds, tile_count, tile_range, tile_resolution
from . import warp
from .shade_tiles import INDEX_FILE, TILE_CRS
from .slope_tiles import rgb

#: The two trees this module cuts.
KINDS = ("vegetation", "forest")

#: Lower bounds of the vegetation classes, as NMD cover codes: a code is the
#: upper bound of its class in per cent, so 20 is *10–20 %* and the first class
#: starts where a tenth of the cell is covered. Below it a cell is drawn as
#: nothing: a few bushes are not an obstacle.
DENSITY_EDGES: tuple[int, ...] = (20, 30, 40, 50, 60, 80)

#: What each class spans, in per cent of the cell, for the legend.
DENSITY_SPANS: tuple[tuple[int, int], ...] = ((10, 20), (20, 30), (30, 40), (40, 50), (50, 70), (70, 100))

#: One colour per vegetation class, lightest first: a teal ramp in OKLCH at
#: hue 190, chroma 0.10, lightness 0.72 down to 0.37.
COLOURS: tuple[str, ...] = ("#4ab9b2", "#2fa29d", "#018d87", "#007873", "#00635f", "#004f4b")

#: The forest's one colour: sepia, OKLCH hue 62, chroma 0.115, lightness 0.62.
FOREST_COLOUR = "#b77534"

#: The least tall-tree cover a cell needs to be forest, as an NMD code: 40 is
#: *30–40 %*, so this is at least 30 % of the cell under crowns over 5 m.
FOREST_MIN_COVER = 40

#: How opaque a class is drawn, 0 to 255: the slope classes' figure, looked at
#: on the mockup over the relief and taken as it stood.
ALPHA = 150

#: Cell size of the codes, in metres.
CELL_M = 10.0

#: Pixels of ground carried round a tile while it is warped, against the
#: resampler reading past its edge.
MARGIN_PX = 2


def classify_vegetation(codes: np.ndarray, edges: Sequence[int] = DENSITY_EDGES) -> np.ndarray:
    """Which vegetation class each cell falls in: 0 for nothing or unknown, then 1 upwards.

    Args:
        codes: The three code bands, ``(3, rows, cols)``
        edges: The classes' lower bounds as cover codes, ascending

    Returns:
        ``uint8`` class indices, ``(rows, cols)``
    """
    cover = codes[1]
    classes: np.ndarray = np.digitize(cover, np.asarray(edges, dtype=np.uint8)).astype(np.uint8)
    classes[(cover == UNKNOWN) | (codes[0] == 0)] = 0
    return classes


def classify_forest(codes: np.ndarray, min_cover: int = FOREST_MIN_COVER) -> np.ndarray:
    """Which cells are forest: 1 where trees over 5 m cover at least ``min_cover``, else 0.

    Args:
        codes: The three code bands, ``(3, rows, cols)``
        min_cover: The least tall cover, as an NMD code

    Returns:
        ``uint8`` 0 or 1, ``(rows, cols)``
    """
    tall = codes[2]
    forest: np.ndarray = ((tall != UNKNOWN) & (tall >= min_cover)).astype(np.uint8)
    return forest


def classify(codes: np.ndarray, kind: str) -> np.ndarray:
    """The class image of one tree.

    Args:
        codes: The three code bands
        kind: ``vegetation`` or ``forest``

    Returns:
        ``uint8`` class indices

    Raises:
        ValueError: If ``kind`` is neither
    """
    if kind == "vegetation":
        return classify_vegetation(codes)
    if kind == "forest":
        return classify_forest(codes)
    raise ValueError(f"kind must be one of {KINDS}; got {kind!r}")


def colours_of(kind: str) -> tuple[str, ...]:
    """The palette of one tree, in class order.

    Args:
        kind: ``vegetation`` or ``forest``

    Returns:
        One colour per class
    """
    return COLOURS if kind == "vegetation" else (FOREST_COLOUR,)


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


def cut(classes: np.ndarray, transform: Affine, source_crs: CRS, zoom: int, x: int, y: int, ground_m: float) -> np.ndarray:
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
        resampling=Resampling.mode if ground_m > 2.0 * CELL_M else Resampling.nearest,
    )
    return patch[MARGIN_PX:-MARGIN_PX, MARGIN_PX:-MARGIN_PX]


def build_tiles(
    codes: np.ndarray,
    transform: Affine,
    crs: str | CRS,
    bounds: Bounds,
    zooms: Iterable[int],
    out_dir: Path,
    kind: str = "vegetation",
    alpha: int = ALPHA,
) -> dict[str, object]:
    """Cut the codes into one tree of palette PNGs, one per ``{z}/{x}/{y}``.

    Tiles already on disk are skipped, so a build resumes. What was done is
    written to ``index.json``.

    Args:
        codes: The three code bands over the box, ``(3, rows, cols)``
        transform: Their georeferencing
        crs: Their projection
        bounds: The box to cover, WGS 84
        zooms: Zoom levels to write
        out_dir: Root of the tile tree
        kind: ``vegetation`` or ``forest``
        alpha: How opaque a class is drawn, 0 to 255

    Returns:
        The index that was written: bounds, zooms, classes, per-zoom counts and bytes
    """
    levels = sorted(set(zooms))
    out_dir.mkdir(parents=True, exist_ok=True)
    source_crs = CRS.from_user_input(crs)
    classes = classify(codes, kind)
    colours = colours_of(kind)
    flat, clear = palette(colours, alpha)
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
                tile = cut(classes, transform, source_crs, zoom, x, y, ground_m)
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
        "edges": list(DENSITY_EDGES) if kind == "vegetation" else [FOREST_MIN_COVER],
        "colours": list(colours),
        "alpha": alpha,
        "cell_m": CELL_M,
        "encoding": "palette PNG of one entry per class; index 0 transparent, then one index per class from the first edge up",
        "seconds": round(time.time() - started, 1),
    }
    (out_dir / INDEX_FILE).write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"Done in {index['seconds']:,} s; index written to {out_dir / INDEX_FILE}", flush=True)
    return index


def weights(index: dict[str, object]) -> dict[int, int]:
    """The mean bytes of a tile per zoom, off a tree's index, for the page's estimate.

    Args:
        index: What :func:`build_tiles` wrote

    Returns:
        Zoom to bytes, whole bytes, levels with no tiles left out
    """
    per_zoom = index["per_zoom"]
    assert isinstance(per_zoom, dict)
    return {int(zoom): int(math.ceil(level["bytes"] / level["tiles"])) for zoom, level in per_zoom.items() if level["tiles"]}
