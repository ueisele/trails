"""The mire classes over a Swedish box: the sheet's wetlands, and the model's wet ground beyond them.

Two sources laid on one 10 m grid (:mod:`.mire`): Lantmäteriet's wetland
outlines (:mod:`.marktacke`), firm or wet, burnt in first so the survey's
word is the cell's whatever the model says; then the cells the soil-moisture
model (:mod:`.slu_moisture`) calls moist-to-wet in most of their 2 m
sub-cells, where no outline has claimed them and the model does not call
them water, as *wet ground*, and those it calls fresh-to-moist in most of
them as *moist ground*. Water is nothing, as in the vegetation codes: the
sheet draws its own lakes.

**Most of the 2 m cells, not any of them.** A 10 m cell is 25 of the model's,
and the model is noisy at its own grain -- a single wet cell among 24 dry
ones is the classifier's doubt and not a puddle. Half of them wet is where
the 10 m cell's usual state is wet; measured over the Abisko box the share
moves from 4.4 % of the land at a third to 2.7 % at seven in ten, and half
gives 3.4 %, of which 87 % lies outside the surveyed wetlands (2026-09-19).
"""

from pathlib import Path

import numpy as np
import rasterio
from affine import Affine

from ...utils.tiles import Bounds
from . import marktacke, mire, slu_moisture

#: The grid's projection: SWEREF 99 TM, which both sources are in.
CRS = "EPSG:3006"

#: How many of a cell's 2 m sub-cells the model must call moist-to-wet for
#: the cell to be wet ground, or fresh-to-moist for it to be moist ground,
#: as a share.
WET_SHARE = 0.5


class Source:
    """The mire classes over a box, cut once and kept."""

    def __init__(
        self,
        cache_dir: str | Path = ".cache",
        wetlands: marktacke.Source | None = None,
        moisture: slu_moisture.Source | None = None,
    ):
        """Point at the two sources.

        Args:
            cache_dir: Where the cut is kept, and where the two sources keep theirs
            wetlands: The sheet's wetlands; read from ``cache_dir`` by default
            moisture: The soil-moisture model; likewise
        """
        self.cache_dir = Path(cache_dir) / "mire"
        self.wetlands = wetlands if wetlands is not None else marktacke.Source(cache_dir=cache_dir)
        self.moisture = moisture if moisture is not None else slu_moisture.Source(cache_dir=cache_dir)

    def _cut_file(self, bounds: Bounds) -> Path:
        stem = "_".join(f"{value:.2f}" for value in bounds).replace(".", "p").replace("-", "m")
        return self.cache_dir / f"sweden_{stem}.tif"

    def mire(self, bounds: Bounds, force_download: bool = False) -> tuple[np.ndarray, Affine]:
        """The mire classes over a box.

        Args:
            bounds: The box, WGS 84
            force_download: Cut the box again, reading the sources again, even if its cut is cached

        Returns:
            The classes (rows from the north), ``uint8``, 0 where nothing is
            drawn, and their georeferencing in :data:`CRS`
        """
        cached = self._cut_file(bounds)
        if cached.exists() and not force_download:
            with rasterio.open(cached) as kept:
                return kept.read(1), kept.transform
        shape, transform = mire.grid(bounds, CRS)
        classes = np.zeros(shape, dtype=np.uint8)
        outlines = self.wetlands.wetlands(bounds, force_download=force_download)
        mire.burn(classes, transform, outlines[~outlines["wet"]].geometry, mire.FIRM_MIRE)
        mire.burn(classes, transform, outlines[outlines["wet"]].geometry, mire.WET_MIRE)
        surveyed = int((classes != 0).sum())
        west, south, east, north = window_of(transform, shape)
        fine, fine_transform = self.moisture.classes((west, south, east, north))
        # The model's grid is 2 m on a whole-metre origin and this one is 10 m
        # snapped to tens, so a cell is exactly five by five of the model's.
        # Read over the same ground, the model's window starts where this
        # grid does; the offsets guard that rather than assume it.
        offset_col = int(round((west - fine_transform.c) / slu_moisture.CELL_M))
        offset_row = int(round((fine_transform.f - north) / slu_moisture.CELL_M))
        per_cell = int(round(mire.CELL_M / slu_moisture.CELL_M))
        rows, cols = shape[0] * per_cell, shape[1] * per_cell
        fine = fine[offset_row : offset_row + rows, offset_col : offset_col + cols]
        if fine.shape != (rows, cols):
            raise ValueError(f"the moisture model covers {fine.shape} of the {(rows, cols)} sub-cells the box needs")
        blocks = fine.reshape(shape[0], per_cell, shape[1], per_cell)
        wet_share = (blocks == slu_moisture.MOIST_WET).mean(axis=(1, 3))
        moist_share = (blocks == slu_moisture.FRESH_MOIST).mean(axis=(1, 3))
        water = (blocks == slu_moisture.WATER).mean(axis=(1, 3)) > 0.5
        classes[(wet_share >= WET_SHARE) & (classes == 0) & ~water] = mire.WET_GROUND
        classes[(moist_share >= WET_SHARE) & (classes == 0) & ~water] = mire.MOIST_GROUND
        land = int(shape[0] * shape[1] - water.sum())
        wet_ground = int((classes == mire.WET_GROUND).sum())
        moist_ground = int((classes == mire.MOIST_GROUND).sum())
        print(
            f"Mire over {bounds}: {surveyed / land * 100:.2f} % of the land is surveyed wetland,"
            f" {wet_ground / land * 100:.2f} % wet ground the model adds beyond it and {moist_ground / land * 100:.2f} % moist",
            flush=True,
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        partial = cached.with_suffix(".part.tif")
        with rasterio.open(
            partial, "w", driver="GTiff", height=shape[0], width=shape[1], count=1, dtype="uint8", crs=CRS, transform=transform,
            nodata=None, compress="deflate", tiled=True, blockxsize=512, blockysize=512,
        ) as out:  # fmt: skip
            out.write(classes, 1)
        partial.replace(cached)
        return classes, transform


def window_of(transform: Affine, shape: tuple[int, int]) -> tuple[float, float, float, float]:
    """The ground a grid covers, ``(west, south, east, north)``, off its georeferencing.

    Args:
        transform: The grid's georeferencing, north up
        shape: ``(rows, cols)``

    Returns:
        The box in the grid's own projection
    """
    west, north = transform @ (0, 0)
    east, south = transform @ (shape[1], shape[0])
    return (west, south, east, north)
