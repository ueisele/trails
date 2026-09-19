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

**One hue, two lightness steps, and hatches for the model.** Drawn as the
vegetation is: a palette PNG with the alpha in it, ``mix-blend-mode:
multiply``, off until asked. The hue is a violet, OKLCH 285, chosen so it
stands apart from the vegetation's teal, the forest's sepia and the slope
classes' pastels; the wet mire is its dark step (lightness 0.44), the mire
its middle one (0.605), and the model's two classes are the middle one
again, hatched -- a dense hatch for wet ground, a sparse one for moist. The
first cut had the wet ground as a third, lighter step, which the validator
passed at ΔE 16 from the middle one and Uwe could not tell apart on the
phone: *"Firm mire und wet ground sind kaum auseinander zu halten, wenn sie
nicht nebeneinander liegen"* (2026-09-19). Two lightness steps of one hue
are a difference a reader sees side by side and not alone, and no second
hue was free -- every blue to pink sat within ΔE 6 of the violet under
simulated colour blindness or on top of the slope pastels. So the
difference is a texture, which is also what the mark says: a surveyed mire
is a solid fill, a modelled one is hatched.

**And the hatch is a close-up mark.** At z12 a pixel is 14 m and a mire a
few pixels wide loses half of itself to the gaps; Uwe: *"Mit Schraffur war
es bei niedrigem Zoom schon schwer zu erkennen."* So from z8 to z12 the
wet ground is a solid fill like the mires and the moist ground is not drawn
at all, and from z13 up both are hatched -- generalisation, the way a sheet
keeps its finer signatures for its finer scales.
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

#: One colour per class, in class order: wet mire darkest, the mire the
#: middle step, and the model's wet and moist ground the middle step again,
#: hatched. A violet in OKLCH at hue 285, chroma 0.13, lightness 0.44 and 0.605.
COLOURS: tuple[str, ...] = ("#4d4496", "#7b75cc", "#7b75cc", "#7b75cc")

#: The classes drawn hatched rather than solid, the model's, each with its
#: hatch as line and gap in tile pixels: dense for wet, sparse for moist.
HATCHED: dict[int, tuple[int, int]] = {mire.WET_GROUND: (2, 2), mire.MOIST_GROUND: (2, 6)}

#: The first zoom the hatches are drawn at; below it the wet ground is a solid
#: fill and the moist ground is left out.
FINE_FROM = 13

#: The classes drawn only from :data:`FINE_FROM` up.
FINE_ONLY: tuple[int, ...] = (mire.MOIST_GROUND,)

#: What each class is, for the legend, in class order.
LABELS: tuple[str, ...] = ("wet mire, hard going", "mire", "wet ground, soft", "moist ground, usually passable")

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
        hatched=HATCHED,
        fine_from=FINE_FROM,
        fine_only=FINE_ONLY,
        extra={
            "labels": list(LABELS),
            "encoding": "palette PNG of one entry per class; index 0 transparent, then wet mire, mire, and the wet and moist ground the model"
            " adds, both hatched from z13 and the moist ground left out below it",
        },
    )
