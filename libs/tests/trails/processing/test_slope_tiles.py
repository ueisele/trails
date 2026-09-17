"""Slope-class tiles out of a synthetic model, read back and checked."""

import json

import numpy as np
import pytest
from affine import Affine
from PIL import Image
from trails.processing import shade_tiles, slope_tiles
from trails.utils.tiles import TILE_PX


class TestSlope:
    def test_level_ground_is_level(self):
        assert float(slope_tiles.slope_degrees(np.zeros((5, 5)), 1.0).max()) == 0.0

    def test_a_plane_reads_its_own_angle_whichever_way_it_faces(self):
        """The slope is the fall line's, so a 30° plane is 30° facing north,
        east or anywhere between -- the aspect is the relief's business."""
        rows, cols = np.mgrid[0:21, 0:21].astype(float)
        rise = np.tan(np.radians(30.0))
        for plane in (rows * rise, cols * rise, (rows + cols) * rise / np.sqrt(2)):
            steep = slope_tiles.slope_degrees(plane, 1.0)
            assert abs(float(steep[10, 10]) - 30.0) < 0.01

    def test_the_classes_start_at_the_first_edge(self):
        steep = np.array([[0.0, 24.9, 25.0], [34.9, 35.0, 89.0]], dtype=np.float32)
        assert slope_tiles.classify(steep).tolist() == [[0, 0, 1], [2, 3, 7]]

    def test_what_cannot_be_measured_is_not_steep(self):
        assert int(slope_tiles.classify(np.array([[np.nan]], dtype=np.float32))[0, 0]) == 0

    def test_the_documented_classes_and_ours(self):
        """The four SLF classes, swisstopo's over 50, and ours at either end:
        25 below them for summer walking, 55 above them because marked trails
        run through ground the model reads as over 50."""
        assert slope_tiles.EDGES == (25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0)
        assert len(slope_tiles.COLOURS) == len(slope_tiles.EDGES) == len(slope_tiles.SOURCES)
        assert slope_tiles.SOURCES == ("ours", "SLF", "SLF", "SLF", "SLF", "swisstopo", "ours")

    def test_every_colour_leaves_black_lettering_readable_when_multiplied(self):
        """The page multiplies the layer over the sheet, so the ground under a
        class is base × (1 − α + α · colour) and the lettering stays black. The
        palette is light enough that no class takes black text on the sheet's
        cream below 7:1 -- the WCAG bar for body text is 4.5."""

        def luminance(rgb):
            def channel(v):
                v /= 255
                return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

            r, g, b = rgb
            return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

        alpha = slope_tiles.ALPHA / 255
        cream, ink = (250, 240, 220), (20, 20, 20)

        def multiplied(base, tint):
            return tuple(b * (1 - alpha + alpha * t / 255) for b, t in zip(base, tint, strict=True))

        for colour in slope_tiles.COLOURS:
            tint = slope_tiles.rgb(colour)
            ground, text = luminance(multiplied(cream, tint)), luminance(multiplied(ink, tint))
            assert (ground + 0.05) / (text + 0.05) >= 7.0, colour

    def test_the_palette_leaves_index_zero_clear_and_colours_the_rest(self):
        flat, clear = slope_tiles.palette(("#ff0000", "#00ff00"), 150)
        assert flat[:9] == [0, 0, 0, 255, 0, 0, 0, 255, 0] and len(flat) == 768
        assert clear[:3] == bytes([0, 150, 150]) and len(clear) == 256 and clear[3:] == bytes(253)


@pytest.fixture
def ridge():
    """The relief tests' model: a ridge in SWEREF 99 TM over the Abisko box."""
    transform = Affine(50.0, 0.0, 600_000.0, 0.0, -50.0, 7_620_000.0)
    rows, cols = 1_200, 1_400
    east = (np.arange(cols) + 0.5) * 50.0
    north = -(np.arange(rows) + 0.5) * 50.0
    heights = (300.0 * np.sin((east[None, :] + north[:, None]) / 900.0)).astype(np.float32)
    return heights, transform, "EPSG:3006"


class TestBuildTiles:
    def test_a_tile_is_a_palette_with_the_classes_coloured_and_the_rest_clear(self, ridge, tmp_path):
        heights, transform, crs = ridge
        bounds = (18.40, 68.30, 18.45, 68.33)
        index = slope_tiles.build_tiles(heights, transform, crs, bounds, zooms=[14], out_dir=tmp_path / "slope")

        assert index["per_zoom"]["14"]["written"] == index["tiles"] > 0
        written = json.loads((tmp_path / "slope" / "index.json").read_text())
        assert written["edges"] == list(slope_tiles.EDGES)
        assert written["colours"] == list(slope_tiles.COLOURS)
        assert written["alpha"] == slope_tiles.ALPHA
        assert written["smooth_m"] == 50.0, "one post of this model, as the relief is"

        tile = next((tmp_path / "slope" / "14").rglob("*.png"))
        image = Image.open(tile)
        assert image.mode == "P", "a palette, not four channels: flat colour compresses"
        rgba = np.asarray(image.convert("RGBA"))
        assert rgba.shape == (TILE_PX, TILE_PX, 4)
        assert set(np.unique(rgba[..., 3]).tolist()) <= {0, slope_tiles.ALPHA}
        # The ridge is 300 m over 900 m of run, so its flanks reach the classes.
        assert rgba[..., 3].max() == slope_tiles.ALPHA, "a steep flank is coloured"
        assert rgba[..., 3].min() == 0, "and the ridge top and valley floor are left clear"
        coloured = rgba[rgba[..., 3] > 0][..., :3]
        assert {tuple(int(v) for v in row) for row in coloured} <= {slope_tiles.rgb(c) for c in slope_tiles.COLOURS}

    def test_ground_outside_the_model_colours_nothing(self, ridge, tmp_path):
        heights, transform, crs = ridge
        bounds = (17.0, 68.30, 17.05, 68.33)  # west of the model
        index = slope_tiles.build_tiles(heights, transform, crs, bounds, zooms=[12], out_dir=tmp_path / "slope")
        assert index["per_zoom"]["12"]["empty"] == index["tiles"]
        rgba = np.asarray(Image.open(next((tmp_path / "slope" / "12").rglob("*.png"))).convert("RGBA"))
        assert rgba[..., 3].max() == 0

    def test_it_is_cut_where_the_relief_is_cut(self, ridge, tmp_path):
        """The two overlays come off the same smoothed heights at every level,
        so a class boundary and a shadow's edge fall in the same place: a
        class tile is coloured exactly where the relief tile is not level."""
        heights, transform, crs = ridge
        bounds = (18.40, 68.30, 18.45, 68.33)
        slope_tiles.build_tiles(heights, transform, crs, bounds, zooms=[14], out_dir=tmp_path / "slope")
        shade_tiles.build_tiles(heights, transform, crs, bounds, zooms=[14], out_dir=tmp_path / "shade")
        tile = next((tmp_path / "slope" / "14").rglob("*.png"))
        classes = np.asarray(Image.open(tile))
        shadow = np.asarray(Image.open(tmp_path / "shade" / "14" / tile.parent.name / tile.name).convert("RGBA"))[..., 3]
        # Where the ridge's north-west flank is steep enough to be classed it
        # faces the light and is not shaded; the south-east flank is both.
        assert classes.max() > 0 and shadow.max() > 0
        assert ((classes > 0) & (shadow > 0)).any(), "the flank turned from the light is classed and shaded alike"

    def test_neighbouring_tiles_meet_without_a_seam(self, ridge, tmp_path):
        heights, transform, crs = ridge
        bounds = (18.40, 68.30, 18.45, 68.33)
        slope_tiles.build_tiles(heights, transform, crs, bounds, zooms=[14], out_dir=tmp_path / "slope")
        level = tmp_path / "slope" / "14"
        columns = sorted(int(where.name) for where in level.iterdir())
        rows = sorted(int(where.stem) for where in (level / str(columns[0])).iterdir())
        assert len(columns) > 1 and len(rows) > 1
        left = np.asarray(Image.open(level / str(columns[0]) / f"{rows[0]}.png")).astype(int)
        right = np.asarray(Image.open(level / str(columns[1]) / f"{rows[0]}.png")).astype(int)
        # A class is a step function, so the fair reading is how many rows
        # change class over the join against how many change inside a tile.
        across = int((left[:, -1] != right[:, 0]).sum())
        within = int((left[:, -1] != left[:, -2]).sum())
        assert across <= within + 4

    def test_a_second_run_skips_what_is_there(self, ridge, tmp_path):
        heights, transform, crs = ridge
        bounds = (18.40, 68.30, 18.45, 68.33)
        slope_tiles.build_tiles(heights, transform, crs, bounds, zooms=[12, 13], out_dir=tmp_path / "slope")
        again = slope_tiles.build_tiles(heights, transform, crs, bounds, zooms=[12, 13], out_dir=tmp_path / "slope")
        assert again["per_zoom"]["13"]["written"] == 0
        assert again["per_zoom"]["13"]["skipped"] == again["per_zoom"]["13"]["tiles"]
        assert not list((tmp_path / "slope").rglob("*.part"))

    def test_edges_and_colours_have_to_agree(self, ridge, tmp_path):
        heights, transform, crs = ridge
        with pytest.raises(ValueError):
            slope_tiles.build_tiles(heights, transform, crs, (18.40, 68.30, 18.45, 68.33), zooms=[12], out_dir=tmp_path / "s", colours=("#000000",))
