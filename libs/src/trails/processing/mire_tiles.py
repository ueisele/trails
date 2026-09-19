"""Mire tiles: where the ground is bog and marsh, and whether it carries a boot.

**The other question the sheet half answers.** Beside what stands on the
ground (:mod:`.vegetation_tiles`), a walker off the path wants to know
whether the flat green ahead is heath or mire, and if a mire, whether it is
the kind that carries or the kind that swallows. Both countries' sheets draw
the mires; Sweden's says which are wet; and Sweden's forest agency has
modelled the ground's wetness off the laser at 2 m, which finds four times
the wet ground the surveyors drew. This module colours the three classes
:mod:`trails.io.sources.mire` defines -- wet mire, firm mire, wet ground --
over either map, from the class grid its country's source cuts
(:mod:`trails.io.sources.mire_sweden`, :mod:`trails.io.sources.mire_norway`;
analysis/docs/abisko-decisions.md §6.13).

**One hue, three lightness steps, multiplied.** Drawn as the vegetation is:
a palette PNG with the alpha in it, ``mix-blend-mode: multiply``, off until
asked. The hue is a violet, OKLCH 285, chosen so the ramp stands apart from
the vegetation's teal, the forest's sepia and the slope classes' pastels,
and stepped in lightness 0.44, 0.605 and 0.77 with the darkest for the
wettest, since the wet mire is the one to walk round. Run through the
palette validator 2026-09-19: every adjacent pair over ΔE 16 in full colour
and over 10 under every simulated colour blindness, and the lightest step
ΔE 16.2 from the teal's lightest, so a reader with both overlays on tells a
willow thicket from a wet flat.
"""

from collections.abc import Iterable
from pathlib import Path

import numpy as np
from affine import Affine
from rasterio.crs import CRS

from ..io.sources import mire
from ..utils.tiles import Bounds
from .class_tiles import write_tree
from .vegetation_tiles import ALPHA

#: What the tree is called: its segment of every address.
KIND = "mire"

#: One colour per class, in class order: wet mire darkest, then firm mire,
#: then the model's wet ground. A violet ramp in OKLCH at hue 285, chroma
#: 0.13, lightness 0.44, 0.605 and 0.77.
COLOURS: tuple[str, ...] = ("#4d4496", "#7b75cc", "#aca8ff")

#: What each class is, for the legend, in class order.
LABELS: tuple[str, ...] = ("wet mire, hard going", "firm mire", "wet ground outside the mires")

#: Cell size of the classes, in metres.
CELL_M = mire.CELL_M


def build_tiles(
    classes: np.ndarray,
    transform: Affine,
    crs: str | CRS,
    bounds: Bounds,
    zooms: Iterable[int],
    out_dir: Path,
    alpha: int = ALPHA,
) -> dict[str, object]:
    """Cut the mire classes into one tree of palette PNGs, one per ``{z}/{x}/{y}``.

    Tiles already on disk are skipped, so a build resumes. What was done is
    written to ``index.json``.

    Args:
        classes: The class grid over the box, ``(rows, cols)``, values of :data:`~trails.io.sources.mire.CLASSES` or 0
        transform: Its georeferencing
        crs: Its projection
        bounds: The box to cover, WGS 84
        zooms: Zoom levels to write
        out_dir: Root of the tile tree
        alpha: How opaque a class is drawn, 0 to 255

    Returns:
        The index that was written: bounds, zooms, classes, per-zoom counts and bytes

    Raises:
        ValueError: If the grid carries a value that is not a class
    """
    highest = int(classes.max()) if classes.size else 0
    if highest > len(COLOURS):
        raise ValueError(f"the mire grid carries class {highest}; the palette has {len(COLOURS)}")
    return write_tree(
        classes,
        transform,
        crs,
        bounds,
        zooms,
        out_dir,
        kind=KIND,
        colours=COLOURS,
        alpha=alpha,
        cell_m=CELL_M,
        extra={
            "labels": list(LABELS),
            "encoding": "palette PNG of one entry per class; index 0 transparent, then wet mire, firm mire, and the wet ground the model adds",
        },
    )
