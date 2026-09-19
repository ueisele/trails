"""What the mire sources agree on: four classes on a 10 m grid, and how outlines become cells.

**The question.** Bog and marsh are the other thing a walker off the path
wants to know about the ground, beside what stands on it (§6.11): whether the
flat green between two ridges is heath or a mire, and if a mire, whether it
carries a boot. Both countries' surveys draw the mires as outlines on their
sheets; Sweden's also says which are wet, and Sweden's forest agency has
modelled the ground's wetness at 2 m off the laser. This module is the ground
the two country sources (:mod:`.mire_sweden`, :mod:`.mire_norway`) stand on,
so the tile cutter (:mod:`trails.processing.mire_tiles`) does not know which
country it is cutting -- analysis/docs/abisko-decisions.md §6.13.

**Four classes, each a statement about the place and never about a source.**
Two are the survey's: *wet mire* is what Lantmäteriet's surveyors marked
*Sankmark, våt*, often or always under water, hard going; *mire* is a mire
the survey draws without calling it wet -- Lantmäteriet's *Sankmark, fast*,
and every N50 *Myr*, since Kartverket draws one kind of bog and says nothing
of its wetness. The same statement gets the same class in both countries,
and a class a country's data cannot support is simply absent from its tree
([[map-symbols-must-say-something]]): Uwe, 2026-09-19, *"Norwegen sollte für
das, was es sagt, dieselbe Farbe und Art bekommen wie Schweden."* Two are
the model's, where the survey drew nothing: *wet ground* is what it calls
moist-to-wet in the year's mean -- seepage lines, brook banks, the small
mires under the sheet's threshold -- and *moist ground* what it calls
fresh-to-moist, ground that gives but carries. Measured over the Abisko box
(2026-09-19): the surveyed mires are 0.63 % of the land, the model's wet
ground 3.4 % with 87 % of it outside the outlines, its moist ground 3.9 %
more. Over Norway there is no model, so the two model classes are empty
there and the legend says nothing of them.

**What is not here.** How wet a mire is *this week*. A mire is a landform; its
water table follows the snowmelt and the last fortnight's rain, and no survey
records that. The weather panel does.
"""

from collections.abc import Iterable

import numpy as np
from affine import Affine
from rasterio import features
from rasterio.warp import transform_bounds
from shapely.geometry.base import BaseGeometry

from ...utils.tiles import Bounds

#: The class of a cell inside a wet mire: *Sankmark, våt*.
WET_MIRE = 1

#: The class of a cell inside a mire the survey does not call wet: *Sankmark,
#: fast*, or N50's *Myr*.
FIRM_MIRE = 2

#: The class of a cell the model calls wet that no survey calls a mire.
WET_GROUND = 3

#: The class of a cell the model calls moist that no survey calls a mire.
MOIST_GROUND = 4

#: Every class, in palette order.
CLASSES = (WET_MIRE, FIRM_MIRE, WET_GROUND, MOIST_GROUND)

#: Cell size of every mire grid, in metres: the vegetation codes' (§6.11), so
#: the two overlays are cut over the same ground at the same grain.
CELL_M = 10.0


def grid(bounds: Bounds, crs: str, cell_m: float = CELL_M) -> tuple[tuple[int, int], Affine]:
    """The grid a box is rasterised on: cells of ``cell_m`` snapped to multiples of it, holding the box.

    Snapped, so that two sources over one box land on one grid, and so that
    a 2 m model whose origin is a round number of metres reads into it in
    whole blocks.

    Args:
        bounds: The box, WGS 84
        crs: The projected system the grid is in, metres
        cell_m: Cell size

    Returns:
        ``(rows, cols)`` and the georeferencing, rows from the north
    """
    west, south, east, north = transform_bounds("EPSG:4326", crs, *bounds)
    left = float(np.floor(west / cell_m) * cell_m)
    top = float(np.ceil(north / cell_m) * cell_m)
    cols = int(np.ceil((east - left) / cell_m))
    rows = int(np.ceil((top - south) / cell_m))
    return (rows, cols), Affine(cell_m, 0.0, left, 0.0, -cell_m, top)


def burn(classes: np.ndarray, transform: Affine, outlines: Iterable[BaseGeometry], value: int) -> None:
    """Write one class into every cell an outline covers, in place.

    A cell is covered when its centre is inside the outline, which is what
    ``rasterio`` does by default and what a 10 m cell over a mire drawn at
    1:50 000 deserves: the outline's own uncertainty is wider than the cell.
    Later calls overwrite earlier ones, so the caller burns the class that
    should win last.

    Args:
        classes: The class grid, ``uint8``, written into
        transform: Its georeferencing
        outlines: Polygons in the grid's projection
        value: The class to write
    """
    shapes = [(outline, value) for outline in outlines if outline is not None and not outline.is_empty]
    if not shapes:
        return
    features.rasterize(shapes, out=classes, transform=transform, default_value=value)
