"""Hillshade tiles: a relief shadow cut from the same height model the profile reads.

**What the paper map has and ours had not.** A printed sheet of this ground
(Calazo 1:25 000) reads as terrain rather than as a pattern of brown lines,
and the difference is the shading laid under the contours. Neither
Lantmäteriet's *Topografisk webbkarta* nor Kartverket's *Topo* carries one --
read off the tiles, not assumed -- so the page draws its own over them
(analysis/docs/abisko-decisions.md §6.6).

**Black with an alpha channel, not a grey image to multiply.** The two were
built side by side and looked at over the same ground. A grey hillshade
multiplied over the sheet darkens flat ground too, because level ground shades
to ``sin(altitude)`` rather than to white, and the whole map goes grey with it.
Here the flat is transparent and only what is turned away from the light
darkens, so the map keeps its cream, its water and its forest::

    alpha = clip(1 - shade / sin(altitude), 0, 1)

**How strong it is, is not baked in.** The tiles carry the full range and the
page draws them at an opacity it can change; re-tuning the look costs a number
in the document rather than a rebuild of the tree.

**The ceiling is z15, and not for the reason a tile tree usually has one.**
Both a z14 and a z15 tree show the same ground: the heights are smoothed by one
post before they are differentiated, so neither resolves anything finer than
about 8 m. What the deeper tree buys is that the image is not blown up --
measured over a steep flank, z14 is visibly soft at z16 where z15 is not. Past
z15 even that stops paying, because the model has no more to give.
"""

import dataclasses
import json
import math
import time
from collections.abc import Iterable
from pathlib import Path

import numpy as np
from affine import Affine
from PIL import Image
from rasterio.crs import CRS
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject

from ..utils.tiles import TILE_PX, Bounds, tile_bounds, tile_count, tile_range, tile_resolution

#: The tiles' projection.
TILE_CRS = "EPSG:3857"

#: Where the light comes from, degrees clockwise from north. North-west is what
#: relief shading has used since it was drawn by hand: a reader takes a lit
#: south-east slope as convex, and lighting from the other side turns every
#: valley into a ridge.
AZIMUTH = 315.0

#: How high the light stands, in degrees. At 45 the modelling is strong without
#: throwing the whole of a steep flank into one flat shadow.
ALTITUDE = 45.0

#: How far the heights are smoothed before they are differentiated, in posts of
#: the model. One post is the Nyquist limit: below it a gradient is reading
#: interpolation rather than ground, and the shade turns to noise over
#: boulder field.
SMOOTH_POSTS = 1.0

#: Pixels of ground carried round a tile while it is computed and cut off
#: afterwards. Without it the gradient at the tile's border has no neighbour
#: and every seam in the tree draws as a line.
MARGIN_PX = 12

#: How many steps of transparency a tile is stored in, 0 to fully shadowed.
#:
#: **Measured, and it halves the tree.** A shadow is a smooth ramp and PNG pays
#: for every level of it: at full precision a z14 tile is 24.7 kB, at 64 steps
#: 14.4 kB. What that costs in the picture is one step of ``255/63`` in alpha,
#: which over the sheet's cream at the opacity the page draws it at is **2.2
#: levels of 255** -- under where banding is seen, and far under what the height
#: model behind it can justify. A palette PNG was tried instead and came out
#: slightly *larger*; 32 steps halves it again and puts a 4.3-level step into a
#: smooth slope, which is where banding starts to show.
STEPS = 64

#: Where a build records what it did, beside the tiles.
INDEX_FILE = "index.json"


def blurred(field: np.ndarray, sigma: float) -> np.ndarray:
    """Smooth a field with a Gaussian, separably.

    Written out rather than taken from SciPy, which this project does not
    otherwise depend on: it is fifteen weighted adds per axis and the edge is
    held rather than wrapped, which matters because a tile is computed with a
    margin and a wrapped edge would put the far side of the tile into it.

    Args:
        field: What to smooth, two-dimensional
        sigma: Standard deviation in pixels; below 0.5 the field is returned as it is

    Returns:
        The smoothed field, same shape and dtype ``float32``
    """
    work = np.asarray(field, dtype=np.float32)
    if sigma < 0.5:
        return work
    radius = int(math.ceil(3.0 * sigma))
    steps = np.arange(-radius, radius + 1, dtype=np.float64)
    weights = np.exp(-(steps**2) / (2.0 * sigma**2))
    weights /= weights.sum()
    for axis in (0, 1):
        padded = np.pad(work, [(radius, radius) if a == axis else (0, 0) for a in (0, 1)], mode="edge")
        out = np.zeros_like(work)
        for index, weight in enumerate(weights):
            piece = padded[index : index + work.shape[0], :] if axis == 0 else padded[:, index : index + work.shape[1]]
            out += np.float32(weight) * piece
        work = out
    return work


def shade(heights: np.ndarray, ground_m: float, azimuth: float = AZIMUTH, altitude: float = ALTITUDE) -> np.ndarray:
    """How much light a surface catches, 0 in full shadow and 1 face-on to the light.

    Args:
        heights: Metres above sea, rows from the top
        ground_m: What one cell spans on the ground, in metres
        azimuth: Where the light comes from, degrees clockwise from north
        altitude: How high the light stands, in degrees

    Returns:
        ``float32`` in ``[0, 1]``, same shape as ``heights``
    """
    light = math.radians(azimuth)
    high = math.radians(altitude)
    # `np.gradient` returns the derivative along each axis in order, and axis 0
    # is rows, which run north to south -- so the first is d/dy and the second
    # d/dx. Naming them the other way round is the classic way to get a map lit
    # from the wrong quarter while every number in it stays plausible.
    dy, dx = np.gradient(np.asarray(heights, dtype=np.float32), ground_m)
    slope = np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    lit = np.sin(high) * np.cos(slope) + np.cos(high) * np.sin(slope) * np.cos(light - aspect)
    caught: np.ndarray = np.clip(lit, 0.0, 1.0).astype(np.float32)
    return caught


def shadow(lit: np.ndarray, altitude: float = ALTITUDE, steps: int = STEPS) -> np.ndarray:
    """Turn light caught into how much the map is darkened, with level ground at nothing.

    Args:
        lit: What :func:`shade` returned
        altitude: The altitude it was computed at
        steps: How many steps of transparency to store it in (:data:`STEPS`);
            256 or fewer, and both ends are always reachable

    Returns:
        ``uint8`` alpha, 0 where the ground is level or lit and 255 in full shadow
    """
    flat = math.sin(math.radians(altitude))
    deep = np.clip(1.0 - lit / flat, 0.0, 1.0)
    if steps >= 256:
        return (deep * 255.0).astype(np.uint8)
    return (np.rint(deep * (steps - 1)) * (255.0 / (steps - 1))).astype(np.uint8)


@dataclasses.dataclass(frozen=True)
class Level:
    """One zoom of a tree, and how a tile of it is cut from the model."""

    #: The zoom.
    zoom: int
    #: What one tile pixel spans on the ground, in metres, at the box's middle latitude.
    ground_m: float
    #: How far the heights are smoothed, in tile pixels.
    sigma: float
    #: Pixels of ground carried round a tile while it is computed.
    margin: int
    #: How the model is resampled into a tile: averaged once a pixel is wider
    #: than a post, bilinear while it is not.
    how: Resampling
    #: The tile columns and rows the box covers: x0, y0, x1, y1, inclusive.
    span: tuple[int, int, int, int]

    @property
    def side(self) -> int:
        """Pixels a patch is cut at: the tile and its margin on both sides."""
        return TILE_PX + 2 * self.margin


def plan(zoom: int, bounds: Bounds, smooth_m: float, posts_m: float) -> Level:
    """How the tiles of one zoom are cut, for :func:`cut`.

    **The resampling changes with the zoom.** Down to about the model's own post
    spacing a tile is asking for detail the model has, and bilinear is right;
    above it a tile pixel covers many posts, and bilinear would take one of them
    and alias whatever is derived from the heights into noise, so those levels
    are averaged.

    Args:
        zoom: The zoom
        bounds: The box to cover, WGS 84
        smooth_m: How far the heights are smoothed, in metres
        posts_m: The model's post spacing, in metres

    Returns:
        The level's plan
    """
    middle = (bounds[1] + bounds[3]) / 2.0
    ground_m = tile_resolution(zoom, middle)
    sigma = smooth_m / ground_m
    margin = max(MARGIN_PX, int(math.ceil(3.0 * sigma)) + 1)
    how = Resampling.average if ground_m > posts_m else Resampling.bilinear
    return Level(zoom=zoom, ground_m=ground_m, sigma=sigma, margin=margin, how=how, span=tile_range(bounds, zoom))


def cut(
    model: np.ndarray,
    transform: Affine,
    source_crs: CRS,
    nodata: float | None,
    level: Level,
    x: int,
    y: int,
) -> tuple[np.ndarray, bool]:
    """Warp one tile's ground out of the model, with its margin, and smooth it.

    Args:
        model: The height model, one band, rows from the top
        transform: Its georeferencing
        source_crs: Its projection
        nodata: Its no-data value, if it has one
        level: The zoom's plan, from :func:`plan`
        x: Tile column
        y: Tile row

    Returns:
        The smoothed patch, ``side`` × ``side`` ``float32`` with no NaN in it,
        and whether the tile holds no ground at all -- in which case the patch
        is level zero and whatever is cut from it should draw nothing
    """
    west, south, east, north = tile_bounds(level.zoom, x, y)
    grown = (east - west) / TILE_PX * level.margin
    side = level.side
    patch = np.full((side, side), np.nan, dtype=np.float32)
    reproject(
        source=model,
        destination=patch,
        src_transform=transform,
        src_crs=source_crs,
        src_nodata=nodata,
        dst_transform=from_bounds(west - grown, south - grown, east + grown, north + grown, side, side),
        dst_crs=TILE_CRS,
        dst_nodata=np.nan,
        resampling=level.how,
    )
    blank = ~np.isfinite(patch)
    if blank.all():
        # No ground here at all: level, so the map beneath is drawn exactly
        # as it would be without the tile.
        return np.zeros((side, side), dtype=np.float32), True
    if blank.any():
        patch = np.where(blank, np.float32(np.nanmedian(patch)), patch)
    return blurred(patch, level.sigma), False


def build_tiles(
    heights: np.ndarray,
    transform: Affine,
    crs: str | CRS,
    bounds: Bounds,
    zooms: Iterable[int],
    out_dir: Path,
    nodata: float | None = None,
    azimuth: float = AZIMUTH,
    altitude: float = ALTITUDE,
    smooth_posts: float = SMOOTH_POSTS,
    steps: int = STEPS,
) -> dict[str, object]:
    """Cut a height model into hillshade tiles, one RGBA PNG per ``{z}/{x}/{y}``.

    Each tile is warped out of the model with :data:`MARGIN_PX` of ground round
    it, smoothed, shaded and cut back to 256 × 256. Tiles already on disk are
    skipped, so a build resumes. What was done is written to ``index.json``.
    How a level is resampled is :func:`plan`'s to say.

    Args:
        heights: The model, one band, rows from the top
        transform: Its georeferencing
        crs: Its projection
        bounds: The box to cover, WGS 84
        zooms: Zoom levels to write
        out_dir: Root of the tile tree
        nodata: The model's no-data value, if it has one
        azimuth: Where the light comes from, degrees clockwise from north
        altitude: How high the light stands, in degrees
        smooth_posts: How far the heights are smoothed first, in posts
        steps: How many steps of transparency a tile is stored in

    Returns:
        The index that was written: bounds, zooms, per-zoom counts and bytes
    """
    levels = sorted(set(zooms))
    out_dir.mkdir(parents=True, exist_ok=True)
    source_crs = CRS.from_user_input(crs)
    model = np.asarray(heights, dtype=np.float32)
    posts_m = abs(transform.a)
    smooth_m = smooth_posts * posts_m
    started = time.time()
    total = tile_count(bounds, levels)
    per_zoom: dict[str, dict[str, int]] = {}
    print(f"Building {total:,} hillshade tiles for z{levels[0]}–z{levels[-1]} from a {model.shape[1]:,} × {model.shape[0]:,} model...", flush=True)
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
                lit = shade(patch, level_plan.ground_m, azimuth, altitude)
                alpha = shadow(lit, altitude, steps)[margin:-margin, margin:-margin]
                if empty:
                    alpha = np.zeros_like(alpha)
                    level += 1
                rgba = np.zeros((TILE_PX, TILE_PX, 4), dtype=np.uint8)
                rgba[..., 3] = alpha
                partial = target.with_suffix(".part")
                Image.fromarray(rgba, mode="RGBA").save(partial, format="PNG", optimize=True)
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
        "azimuth": azimuth,
        "altitude": altitude,
        "smooth_m": round(smooth_m, 3),
        "steps": steps,
        "encoding": "black with alpha = 1 - shade / sin(altitude)",
        "seconds": round(time.time() - started, 1),
    }
    (out_dir / INDEX_FILE).write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"Done in {index['seconds']:,} s; index written to {out_dir / INDEX_FILE}", flush=True)
    return index
