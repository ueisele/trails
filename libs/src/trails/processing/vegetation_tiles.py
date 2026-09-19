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

**And a seventh class, grey, for the ground the laser has no word on.** Uwe
asked whether a blank tile means *nothing there* or *nobody looked*, and it
could not: both were transparent. So the cells the source marks
:data:`~trails.io.sources.nmd.UNKNOWN` are drawn in a light neutral grey at
the same alpha, one more palette entry and a legend row of its own. The grey
was validated against the ramp's light step and the sepia: ΔE 16.7 in full
colour and 9.8 under simulated protanopia from the lightest teal, so a reader
who cannot tell red from green still tells *not surveyed* from *a tenth
covered*; a darker grey did not (ΔE 4.2 at ``#bdbdbd``). Water is not
unknown on either side of the border -- both sources report it as bare,
measured, since the laser gets nothing back off it -- so the grey is the
ground past a country's edge and any gap in its scanning, and nothing else.
"""

import math
from collections.abc import Iterable, Sequence
from pathlib import Path

import numpy as np
from affine import Affine
from rasterio.crs import CRS

from ..io.sources.nmd import UNKNOWN
from ..utils.tiles import Bounds
from .class_tiles import write_tree

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

#: The class of a cell the laser has not flown, after the six density classes.
UNSURVEYED = len(DENSITY_EDGES) + 1

#: Its colour: a neutral grey at OKLCH lightness 0.86, the lightest the
#: multiply still shows and far enough from the ramp's light step (ΔE 9.8
#: under simulated protanopia; ``#bdbdbd`` reached 4.2).
UNSURVEYED_COLOUR = "#cfcfcf"

#: The least tall-tree cover a cell needs to be forest, as an NMD code: 40 is
#: *30–40 %*, so this is at least 30 % of the cell under crowns over 5 m.
FOREST_MIN_COVER = 40

#: How opaque a class is drawn, 0 to 255: the slope classes' figure, looked at
#: on the mockup over the relief and taken as it stood.
ALPHA = 150

#: Cell size of the codes, in metres.
CELL_M = 10.0


def classify_vegetation(codes: np.ndarray, edges: Sequence[int] = DENSITY_EDGES) -> np.ndarray:
    """Which vegetation class each cell falls in: 0 for nothing, 1 upwards by cover, :data:`UNSURVEYED` where the laser has not been.

    Args:
        codes: The three code bands, ``(3, rows, cols)``
        edges: The classes' lower bounds as cover codes, ascending

    Returns:
        ``uint8`` class indices, ``(rows, cols)``
    """
    cover = codes[1]
    classes: np.ndarray = np.digitize(cover, np.asarray(edges, dtype=np.uint8)).astype(np.uint8)
    classes[codes[0] == 0] = 0
    classes[cover == UNKNOWN] = len(edges) + 1
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
        One colour per class: the six density steps and the grey of the
        unsurveyed ground, or the forest's one
    """
    return (*COLOURS, UNSURVEYED_COLOUR) if kind == "vegetation" else (FOREST_COLOUR,)


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
    classes = classify(codes, kind)
    colours = colours_of(kind)
    return write_tree(
        classes,
        transform,
        crs,
        bounds,
        zooms,
        out_dir,
        kind=kind,
        colours=colours,
        alpha=alpha,
        cell_m=CELL_M,
        extra={
            "edges": list(DENSITY_EDGES) if kind == "vegetation" else [FOREST_MIN_COVER],
            "encoding": "palette PNG of one entry per class; index 0 transparent, then one index per class from the first edge up"
            + (", then the grey of the ground the laser has not flown" if kind == "vegetation" else ""),
        },
    )


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
