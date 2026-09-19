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
    grid[: shape[0] // 2, 2 * third :] = mire.MOIST_GROUND
    return grid, transform, mire_sweden.CRS


class TestColours:
    def test_four_classes_the_wettest_darkest_and_the_models_two_hatched_in_the_mires_colour(self):
        """Uwe, 2026-09-19: a lighter third step could not be told from the middle one alone, so the
        model's classes are the middle colour hatched, dense for wet and sparse for moist."""
        assert len(mire_tiles.COLOURS) == len(mire_tiles.LABELS) == len(mire.CLASSES) == 4

        def luminance(colour):
            r, g, b = (int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5))
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        assert luminance(mire_tiles.COLOURS[mire.WET_MIRE - 1]) < luminance(mire_tiles.COLOURS[mire.FIRM_MIRE - 1])
        assert mire_tiles.COLOURS[mire.WET_GROUND - 1] == mire_tiles.COLOURS[mire.MOIST_GROUND - 1] == mire_tiles.COLOURS[mire.FIRM_MIRE - 1]
        assert mire_tiles.HATCHED == {mire.WET_GROUND: (2, 2), mire.MOIST_GROUND: (2, 6)}
        assert mire_tiles.FINE_FROM == 13 and mire_tiles.FINE_ONLY == (mire.MOIST_GROUND,)
        assert mire_tiles.LABELS[mire.WET_MIRE - 1].startswith("wet mire") and mire_tiles.LABELS[mire.FIRM_MIRE - 1] == "mire"


class TestBuild:
    def test_the_tree_is_cut_and_indexed(self, classes, tmp_path):
        grid, transform, crs = classes
        index = mire_tiles.build_tiles(grid, transform, crs, ABISKO, [8, 9, 13], tmp_path / "mire")
        assert index["kind"] == "mire" and index["zooms"] == [8, 9, 13]
        assert index["colours"] == list(mire_tiles.COLOURS) and index["labels"] == list(mire_tiles.LABELS)
        written = json.loads((tmp_path / "mire" / "index.json").read_text())
        assert written["tiles"] == index["tiles"] and written["per_zoom"]["9"]["written"] > 0
        tiles = sorted((tmp_path / "mire").glob("9/*/*.png"))
        seen = set()
        for tile in tiles:
            with Image.open(tile) as image:
                assert image.mode == "P" and image.size == (TILE_PX, TILE_PX)
                assert len(image.getpalette()) // 3 <= 5
                assert image.info["transparency"][0] == 0 and image.info["transparency"][1] == mire_tiles.ALPHA
                seen.update(np.unique(np.asarray(image)).tolist())
        # Coarse: the moist ground is left out, the wet ground is solid.
        assert seen == {0, mire.WET_MIRE, mire.FIRM_MIRE, mire.WET_GROUND}
        assert index["hatched"] == {"3": [2, 2], "4": [2, 6]} and index["fine_from"] == 13 and index["fine_only"] == [4]

    def test_the_hatch_is_a_close_up_mark_and_the_moist_ground_with_it(self, classes, tmp_path):
        """z9: wet ground solid, no moist ground. z13: wet ground on a 2/2 hatch, moist ground on a 2/6 one, the mires solid."""
        grid, transform, crs = classes
        mire_tiles.build_tiles(grid, transform, crs, ABISKO, [9, 13], tmp_path / "mire")

        def pixels_of(zoom):
            counts = dict.fromkeys((0, *mire.CLASSES), 0)
            on_gap = {mire.WET_GROUND: 0, mire.MOIST_GROUND: 0}
            for tile in (tmp_path / "mire").glob(f"{zoom}/*/*.png"):
                with Image.open(tile) as image:
                    pixels = np.asarray(image)
                for index in counts:
                    counts[index] += int((pixels == index).sum())
                for index, (line, gap) in mire_tiles.HATCHED.items():
                    rows, cols = np.nonzero(pixels == index)
                    on_gap[index] += int(((rows + cols) % (line + gap) >= line).sum())
            return counts, on_gap

        coarse, _ = pixels_of(9)
        assert coarse[mire.WET_GROUND] > 0 and coarse[mire.MOIST_GROUND] == 0
        fine, on_gap = pixels_of(13)
        assert fine[mire.MOIST_GROUND] > 0 and on_gap == {mire.WET_GROUND: 0, mire.MOIST_GROUND: 0}
        # A 2/2 hatch keeps half of a class's pixels, a 2/6 one a quarter: the
        # wet band is the southern half of the east third, the moist the northern.
        assert 0.55 < fine[mire.WET_GROUND] / (fine[mire.WET_GROUND] + fine[mire.MOIST_GROUND]) < 0.75

    def test_a_class_the_palette_does_not_have_is_refused(self, classes, tmp_path):
        grid, transform, crs = classes
        grid[0, 0] = 5
        with pytest.raises(ValueError, match="class 5"):
            mire_tiles.build_tiles(grid, transform, crs, ABISKO, [8], tmp_path / "mire")

    def test_a_second_run_skips_what_is_there(self, classes, tmp_path):
        grid, transform, crs = classes
        first = mire_tiles.build_tiles(grid, transform, crs, ABISKO, [8], tmp_path / "mire")
        again = mire_tiles.build_tiles(grid, transform, crs, ABISKO, [8], tmp_path / "mire")
        assert again["per_zoom"]["8"]["skipped"] == first["per_zoom"]["8"]["written"]
