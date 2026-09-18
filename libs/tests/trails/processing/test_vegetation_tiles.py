"""Vegetation and forest tiles out of synthetic codes, read back and checked."""

import json

import numpy as np
import pytest
from affine import Affine
from PIL import Image
from trails.io.sources import nmd
from trails.processing import vegetation_tiles
from trails.utils.tiles import TILE_PX


class TestClasses:
    def test_the_density_classes_start_at_a_tenth(self):
        cover = np.array([0, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, nmd.UNKNOWN], dtype=np.uint8)
        codes = np.stack([np.where(cover == 0, 0, 1).astype(np.uint8), cover, np.zeros_like(cover)])
        assert vegetation_tiles.classify_vegetation(codes).tolist() == [0, 0, 0, 1, 2, 3, 4, 5, 5, 6, 6, 6, 0]

    def test_a_cell_with_no_low_object_is_not_drawn_whatever_its_cover_says(self):
        codes = np.array([[[0]], [[60]], [[0]]], dtype=np.uint8)
        assert int(vegetation_tiles.classify_vegetation(codes)[0, 0]) == 0

    def test_forest_needs_a_third_of_the_cell_under_crowns(self):
        tall = np.array([0, 5, 30, 40, 100, nmd.UNKNOWN], dtype=np.uint8)
        codes = np.stack([np.zeros_like(tall), np.zeros_like(tall), tall])
        assert vegetation_tiles.classify_forest(codes).tolist() == [0, 0, 0, 1, 1, 0]

    def test_six_colours_for_six_classes_and_one_for_the_forest(self):
        assert len(vegetation_tiles.COLOURS) == len(vegetation_tiles.DENSITY_EDGES) == len(vegetation_tiles.DENSITY_SPANS) == 6
        assert vegetation_tiles.colours_of("forest") == (vegetation_tiles.FOREST_COLOUR,)
        with pytest.raises(ValueError, match="kind must be"):
            vegetation_tiles.classify(np.zeros((3, 1, 1), dtype=np.uint8), "heather")

    def test_the_palette_is_no_longer_than_its_classes(self):
        """A blank tile carries the palette and nothing else, so the palette is
        the classes and not 256 entries: measured, 163 bytes against 1,189."""
        flat, clear = vegetation_tiles.palette(("#ff0000", "#00ff00"), 150)
        assert flat == [0, 0, 0, 255, 0, 0, 0, 255, 0]
        assert clear == bytes([0, 150, 150])

    def test_the_ramp_reads_light_to_dark(self):
        """One hue, monotone lightness: what the palette validator checked on
        2026-09-18, kept here as the cheap half of it."""

        def luminance(colour):
            r, g, b = (int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5))
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        steps = [luminance(colour) for colour in vegetation_tiles.COLOURS]
        assert steps == sorted(steps, reverse=True)


@pytest.fixture
def codes():
    """Codes over the Abisko box in SWEREF 99 TM: willow in the west, forest in the east, a bare band between."""
    transform = Affine(50.0, 0.0, 600_000.0, 0.0, -50.0, 7_620_000.0)
    rows, cols = 1_200, 1_400
    low_height = np.zeros((rows, cols), dtype=np.uint8)
    low_cover = np.zeros((rows, cols), dtype=np.uint8)
    tall = np.zeros((rows, cols), dtype=np.uint8)
    low_height[:, : cols // 3] = 3
    low_cover[:, : cols // 3] = 60
    tall[:, 2 * cols // 3 :] = 70
    return np.stack([low_height, low_cover, tall]), transform, "EPSG:3006"


class TestBuild:
    def test_both_trees_are_cut_and_indexed(self, codes, tmp_path):
        bounds = (18.15, 68.139, 19.10, 68.46)
        stack, transform, crs = codes
        index = vegetation_tiles.build_tiles(stack, transform, crs, bounds, [8, 9], tmp_path / "vegetation", kind="vegetation")
        forest = vegetation_tiles.build_tiles(stack, transform, crs, bounds, [8], tmp_path / "forest", kind="forest")
        assert index["kind"] == "vegetation" and index["zooms"] == [8, 9] and index["colours"] == list(vegetation_tiles.COLOURS)
        assert forest["kind"] == "forest" and forest["colours"] == [vegetation_tiles.FOREST_COLOUR]
        written = json.loads((tmp_path / "vegetation" / "index.json").read_text())
        assert written["tiles"] == index["tiles"] and written["per_zoom"]["9"]["written"] > 0
        tiles = sorted((tmp_path / "vegetation").glob("9/*/*.png"))
        assert tiles
        with Image.open(tiles[0]) as image:
            assert image.mode == "P" and image.size == (TILE_PX, TILE_PX)
            assert image.info["transparency"][0] == 0 and image.info["transparency"][1] == vegetation_tiles.ALPHA
            assert len(image.getpalette()) // 3 <= 7
        blank = next(t for t in tiles if t.stat().st_size < 300)
        assert blank.stat().st_size < 300
        # The willow is class 5 (50–70 %) and nothing else is drawn on that side.
        classes = set()
        for tile in tiles:
            with Image.open(tile) as image:
                classes.update(np.unique(np.asarray(image)).tolist())
        assert classes <= {0, 5}
        assert 5 in classes
        assert vegetation_tiles.weights(index)[9] > 0

    def test_a_second_run_skips_what_is_there(self, codes, tmp_path):
        stack, transform, crs = codes
        bounds = (18.15, 68.139, 19.10, 68.46)
        first = vegetation_tiles.build_tiles(stack, transform, crs, bounds, [8], tmp_path / "forest", kind="forest")
        again = vegetation_tiles.build_tiles(stack, transform, crs, bounds, [8], tmp_path / "forest", kind="forest")
        assert again["per_zoom"]["8"]["skipped"] == first["per_zoom"]["8"]["written"]
