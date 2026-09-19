"""The mire grid and how outlines are burnt into it."""

import numpy as np
from shapely.geometry import box
from trails.io.sources import mire


class TestGrid:
    def test_the_grid_snaps_to_whole_cells_and_holds_the_box(self):
        shape, transform = mire.grid((18.15, 68.139, 19.10, 68.46), "EPSG:3006")
        assert transform.a == 10.0 and transform.e == -10.0
        assert transform.c % 10 == 0 and transform.f % 10 == 0
        # The Abisko box is 41 × 38 km on the ground.
        assert shape == (3805, 4126)
        west, north = transform * (0, 0)
        east, south = transform * (shape[1], shape[0])
        assert west <= 629019.1 and east >= 670265.8 and south <= 7561701.0 and north >= 7599742.0

    def test_a_coarser_cell_gives_a_smaller_grid_on_the_same_ground(self):
        fine, _ = mire.grid((12.0, 65.15, 13.75, 65.95), "EPSG:25833")
        coarse, _ = mire.grid((12.0, 65.15, 13.75, 65.95), "EPSG:25833", cell_m=100.0)
        assert coarse[0] * 10 - 10 <= fine[0] <= coarse[0] * 10
        assert coarse[1] * 10 - 10 <= fine[1] <= coarse[1] * 10


class TestBurn:
    def test_the_class_burnt_last_wins_and_nothing_else_moves(self):
        shape, transform = (10, 10), mire.grid((18.15, 68.139, 19.10, 68.46), "EPSG:3006")[1]
        classes = np.zeros(shape, dtype=np.uint8)
        west, north = transform * (0, 0)
        firm = box(west, north - 60, west + 60, north)  # the top-left 6 × 6 cells
        wet = box(west, north - 20, west + 20, north)  # the top-left 2 × 2 of them
        mire.burn(classes, transform, [firm], mire.FIRM_MIRE)
        mire.burn(classes, transform, [wet], mire.WET_MIRE)
        assert classes[:2, :2].tolist() == [[1, 1], [1, 1]]
        assert (classes[:6, :6] != 0).sum() == 36 and (classes[:6, :6] == mire.FIRM_MIRE).sum() == 32
        assert classes[6:, :].sum() == 0 and classes[:, 6:].sum() == 0

    def test_nothing_to_burn_is_no_change(self):
        classes = np.ones((3, 3), dtype=np.uint8)
        _, transform = mire.grid((18.15, 68.139, 19.10, 68.46), "EPSG:3006")
        mire.burn(classes, transform, [], mire.WET_GROUND)
        mire.burn(classes, transform, [None, box(0, 0, 0, 0)], mire.WET_GROUND)
        assert classes.sum() == 9
