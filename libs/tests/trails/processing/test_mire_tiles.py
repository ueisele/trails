"""Mire tiles out of a synthetic class grid, read back and checked."""

import json

import numpy as np
import pytest
from PIL import Image
from trails.io.sources import mire, mire_sweden
from trails.processing import mire_tiles
from trails.utils.tiles import TILE_PX

ABISKO = (18.15, 68.139, 19.10, 68.46)


@pytest.fixture
def classes():
    """Classes over the Abisko box: wet mire in the west, firm mire in the middle, wet ground in the east."""
    shape, transform = mire.grid(ABISKO, mire_sweden.CRS, cell_m=50.0)
    grid = np.zeros(shape, dtype=np.uint8)
    third = shape[1] // 3
    grid[:, :third] = mire.WET_MIRE
    grid[:, third : 2 * third] = mire.FIRM_MIRE
    grid[:, 2 * third :] = mire.WET_GROUND
    return grid, transform, mire_sweden.CRS


class TestColours:
    def test_three_colours_three_labels_the_wettest_darkest_and_the_model_hatched_in_the_firm_colour(self):
        """Uwe, 2026-09-19: a lighter third step could not be told from the middle one alone, so the
        model's class is the middle colour hatched."""
        assert len(mire_tiles.COLOURS) == len(mire_tiles.LABELS) == len(mire.CLASSES) == 3

        def luminance(colour):
            r, g, b = (int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5))
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        assert luminance(mire_tiles.COLOURS[mire.WET_MIRE - 1]) < luminance(mire_tiles.COLOURS[mire.FIRM_MIRE - 1])
        assert mire_tiles.COLOURS[mire.WET_GROUND - 1] == mire_tiles.COLOURS[mire.FIRM_MIRE - 1]
        assert mire_tiles.HATCHED == (mire.WET_GROUND,) and mire_tiles.HATCH_PX == 2
        assert mire_tiles.LABELS[mire.WET_MIRE - 1].startswith("wet mire")


class TestBuild:
    def test_the_tree_is_cut_and_indexed(self, classes, tmp_path):
        grid, transform, crs = classes
        index = mire_tiles.build_tiles(grid, transform, crs, ABISKO, [8, 9], tmp_path / "mire")
        assert index["kind"] == "mire" and index["zooms"] == [8, 9]
        assert index["colours"] == list(mire_tiles.COLOURS) and index["labels"] == list(mire_tiles.LABELS)
        written = json.loads((tmp_path / "mire" / "index.json").read_text())
        assert written["tiles"] == index["tiles"] and written["per_zoom"]["9"]["written"] > 0
        tiles = sorted((tmp_path / "mire").glob("9/*/*.png"))
        seen = set()
        for tile in tiles:
            with Image.open(tile) as image:
                assert image.mode == "P" and image.size == (TILE_PX, TILE_PX)
                assert len(image.getpalette()) // 3 <= 4
                assert image.info["transparency"][0] == 0 and image.info["transparency"][1] == mire_tiles.ALPHA
                seen.update(np.unique(np.asarray(image)).tolist())
        assert seen == {0, mire.WET_MIRE, mire.FIRM_MIRE, mire.WET_GROUND}
        assert index["hatched"] == [mire.WET_GROUND] and index["hatch_px"] == 2

    def test_the_modelled_class_is_hatched_and_the_surveyed_ones_solid(self, classes, tmp_path):
        grid, transform, crs = classes
        mire_tiles.build_tiles(grid, transform, crs, ABISKO, [9], tmp_path / "mire")
        solid = hatched = 0
        for tile in (tmp_path / "mire").glob("9/*/*.png"):
            with Image.open(tile) as image:
                pixels = np.asarray(image)
            solid += int(np.isin(pixels, [mire.WET_MIRE, mire.FIRM_MIRE]).sum())
            hatched += int((pixels == mire.WET_GROUND).sum())
            # A hatched pixel never sits on a dropped diagonal.
            rows, cols = np.nonzero(pixels == mire.WET_GROUND)
            assert not (((rows + cols) // 2) % 2 == 1).any()
        assert solid > 0 and hatched > 0
        # The east third is wet ground, so about half of a third of the drawn pixels are hatched.
        assert 0.15 < hatched / (solid + hatched) < 0.25

    def test_a_class_the_palette_does_not_have_is_refused(self, classes, tmp_path):
        grid, transform, crs = classes
        grid[0, 0] = 4
        with pytest.raises(ValueError, match="class 4"):
            mire_tiles.build_tiles(grid, transform, crs, ABISKO, [8], tmp_path / "mire")

    def test_a_second_run_skips_what_is_there(self, classes, tmp_path):
        grid, transform, crs = classes
        first = mire_tiles.build_tiles(grid, transform, crs, ABISKO, [8], tmp_path / "mire")
        again = mire_tiles.build_tiles(grid, transform, crs, ABISKO, [8], tmp_path / "mire")
        assert again["per_zoom"]["8"]["skipped"] == first["per_zoom"]["8"]["written"]
