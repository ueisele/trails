"""Slope-class tiles: how steep the ground is, in the classes the avalanche services publish.

**What the map is for, off the path.** The profile grades the *path* in per
cent along it and the network stays under 22° on 98.5 % of its length, because
paths were laid where the ground allows. A reader leaving them wants the other
question answered -- how steep is it *here*, in the fall line -- and that is
what these tiles colour, over the relief shadow and under everything the page
draws itself (analysis/docs/abisko-decisions.md §6.7).

**The classes are the documented ones, with one of our own at each end.** The
Swiss avalanche institute SLF recommends 30–35, 35–40, 40–45 and over 45; the
swisstopo layer built on that added a class over 50 in 2026, agreed with SLF
and the SAC. Those are winter classes, chosen where slabs release. Summer
walking is decided lower: from about 25° cross-country is laborious, from 35°
the hands come out, and from 45° a smooth face is not walked -- a stepped one
is, and the model cannot tell the two apart at four metres a post, so the
legend names the angle and not the walkability. The 25° class is ours, and so
is the one over 55°: marked trails run through ground the model reads as over
50°, and the walls no path crosses had to be told apart from the steps one
does. The legend says which are ours. Measured over the Abisko model, 101
million posts, the classes hold 5.2, 3.3, 1.9, 0.9, 0.5, 0.3 and 0.4 % of the
ground. No hiking scale we could find publishes a threshold in degrees: the
SAC scale, the DNT grades and the Alpenverein categories all describe terrain
in words.

**Coloured classes with an alpha, as a palette PNG, drawn multiplied.** Flat
colour compresses: a z15 tile is a few kilobytes against the relief's 9.4, and
the whole tree a quarter of the shadow's. The page draws the layer with
``mix-blend-mode: multiply``, as a printer overprints transparent ink: black
lettering stays black under every class, where drawn opaquely the sheet's
names fell to 3:1 against their ground and were the first thing a reader
lost. Multiplying darkens the ground by the colour, so the palette is light
-- a ramp from pale yellow through orange, coral and pink to lilac and light
blue -- and no class takes black text below 10:1 (§6.7). The alpha is in the
palette rather than the page, so a tile can be looked at on its own; the page
draws it at full strength.

The tiles are cut exactly as the relief's are -- same model, same smoothing,
same margin, same resampling per level -- through :func:`shade_tiles.plan`
and :func:`shade_tiles.cut`, so the two overlays never disagree about where a
slope is.
"""

import json
import time
from collections.abc import Iterable, Sequence
from pathlib import Path

import numpy as np
from affine import Affine
from PIL import Image
from rasterio.crs import CRS

from ..utils.tiles import Bounds, tile_count
from .shade_tiles import INDEX_FILE, SMOOTH_POSTS, cut, plan

#: Lower bounds of the classes, in degrees of slope. The first is ours; the
#: next four are the SLF's; then swisstopo's of 2026, agreed with the SLF and
#: the SAC; and the last is ours again, above where any marked trail goes.
EDGES: tuple[float, ...] = (25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0)

#: One colour per class, in the classes' order: a light ramp, because the
#: page multiplies it over the sheet and a dark colour would take the
#: lettering with it. Pale yellow to light blue, each far enough from its
#: neighbours to be told apart over the relief -- chosen on the mockup.
COLOURS: tuple[str, ...] = ("#fff176", "#ffd54f", "#ffab40", "#ff8a65", "#f48fb1", "#ce93d8", "#90caf9")

#: Where each class comes from, for the legend: who set the boundary.
SOURCES: tuple[str, ...] = ("ours", "SLF", "SLF", "SLF", "SLF", "swisstopo", "ours")

#: How opaque a class is drawn, 0 to 255. 150 is what was looked at on the
#: mockup over the relief at 0.55 and taken as it stood; under multiply it is
#: also what keeps the darkening partial, so the ground under a class is
#: ``base × (1 − α + α · colour)`` and never the colour alone.
ALPHA = 150


def rgb(colour: str) -> tuple[int, int, int]:
    """A ``#rrggbb`` string as three bytes.

    Args:
        colour: The colour, with its hash

    Returns:
        Red, green and blue
    """
    return int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16)


def slope_degrees(heights: np.ndarray, ground_m: float) -> np.ndarray:
    """How steep the ground is, in degrees from level, in the fall line.

    Args:
        heights: Metres above sea, rows from the top
        ground_m: What one cell spans on the ground, in metres

    Returns:
        ``float32`` degrees, 0 level and 90 vertical, same shape as ``heights``
    """
    dy, dx = np.gradient(np.asarray(heights, dtype=np.float32), ground_m)
    steep: np.ndarray = np.degrees(np.arctan(np.hypot(dx, dy))).astype(np.float32)
    return steep


def classify(steep: np.ndarray, edges: Sequence[float] = EDGES) -> np.ndarray:
    """Which class each cell falls in: 0 under the first edge, then 1 upwards.

    Args:
        steep: Degrees of slope, from :func:`slope_degrees`
        edges: The classes' lower bounds, ascending

    Returns:
        ``uint8`` class indices, same shape as ``steep``
    """
    classes: np.ndarray = np.digitize(np.nan_to_num(steep, nan=0.0), np.asarray(edges, dtype=np.float32)).astype(np.uint8)
    return classes


def palette(colours: Sequence[str], alpha: int) -> tuple[list[int], bytes]:
    """The PNG palette for a class image: index 0 transparent, then the classes.

    Args:
        colours: One ``#rrggbb`` per class
        alpha: How opaque every class is, 0 to 255

    Returns:
        The 768-byte palette as a list, and the transparency byte per index
    """
    flat = [0, 0, 0]
    for colour in colours:
        flat.extend(rgb(colour))
    flat.extend([0] * (768 - len(flat)))
    clear = bytes([0]) + bytes([alpha] * len(colours)) + bytes([0] * (256 - 1 - len(colours)))
    return flat, clear


def build_tiles(
    heights: np.ndarray,
    transform: Affine,
    crs: str | CRS,
    bounds: Bounds,
    zooms: Iterable[int],
    out_dir: Path,
    nodata: float | None = None,
    edges: Sequence[float] = EDGES,
    colours: Sequence[str] = COLOURS,
    alpha: int = ALPHA,
    smooth_posts: float = SMOOTH_POSTS,
) -> dict[str, object]:
    """Cut a height model into slope-class tiles, one palette PNG per ``{z}/{x}/{y}``.

    Each tile is warped out of the model with a margin round it, smoothed,
    differentiated, classed and cut back to 256 × 256 -- through the relief's
    own :func:`shade_tiles.plan` and :func:`shade_tiles.cut`. Tiles already on
    disk are skipped, so a build resumes. What was done is written to
    ``index.json``.

    Args:
        heights: The model, one band, rows from the top
        transform: Its georeferencing
        crs: Its projection
        bounds: The box to cover, WGS 84
        zooms: Zoom levels to write
        out_dir: Root of the tile tree
        nodata: The model's no-data value, if it has one
        edges: The classes' lower bounds in degrees, ascending
        colours: One colour per class
        alpha: How opaque a class is drawn, 0 to 255
        smooth_posts: How far the heights are smoothed first, in posts

    Returns:
        The index that was written: bounds, zooms, classes, per-zoom counts and bytes
    """
    if len(edges) != len(colours):
        raise ValueError(f"{len(edges)} edges but {len(colours)} colours")
    levels = sorted(set(zooms))
    out_dir.mkdir(parents=True, exist_ok=True)
    source_crs = CRS.from_user_input(crs)
    model = np.asarray(heights, dtype=np.float32)
    posts_m = abs(transform.a)
    smooth_m = smooth_posts * posts_m
    flat, clear = palette(colours, alpha)
    started = time.time()
    total = tile_count(bounds, levels)
    per_zoom: dict[str, dict[str, int]] = {}
    print(f"Building {total:,} slope-class tiles for z{levels[0]}–z{levels[-1]} from a {model.shape[1]:,} × {model.shape[0]:,} model...", flush=True)
    for zoom in levels:
        level_plan = plan(zoom, bounds, smooth_m, posts_m)
        x0, y0, x1, y1 = level_plan.span
        margin = level_plan.margin
        written = skipped = level = 0
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
                patch, empty = cut(model, transform, source_crs, nodata, level_plan, x, y)
                classes = classify(slope_degrees(patch, level_plan.ground_m), edges)[margin:-margin, margin:-margin]
                if empty:
                    classes = np.zeros_like(classes)
                    level += 1
                image = Image.fromarray(np.ascontiguousarray(classes), mode="P")
                image.putpalette(flat)
                partial = target.with_suffix(".part")
                image.save(partial, format="PNG", optimize=True, transparency=clear)
                partial.replace(target)
                written += 1
                size += target.stat().st_size
        wanted = (x1 - x0 + 1) * (y1 - y0 + 1)
        elapsed = time.time() - level_started
        print(
            f"  z{zoom}: {written:,} written, {skipped:,} already there, {level:,} without ground, of {wanted:,}"
            f" — {size / 1e6:,.1f} MB, {elapsed:,.0f} s, {level_plan.ground_m:.2f} m/px, sigma {level_plan.sigma:.2f} px, {level_plan.how.name}",
            flush=True,
        )
        per_zoom[str(zoom)] = {"tiles": wanted, "written": written, "skipped": skipped, "empty": level, "bytes": size}
    index: dict[str, object] = {
        "bounds": list(bounds),
        "zooms": levels,
        "tiles": total,
        "per_zoom": per_zoom,
        "edges": list(edges),
        "colours": list(colours),
        "alpha": alpha,
        "smooth_m": round(smooth_m, 3),
        "encoding": "palette PNG; index 0 transparent, then one index per class from the first edge up",
        "seconds": round(time.time() - started, 1),
    }
    (out_dir / INDEX_FILE).write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"Done in {index['seconds']:,} s; index written to {out_dir / INDEX_FILE}", flush=True)
    return index
