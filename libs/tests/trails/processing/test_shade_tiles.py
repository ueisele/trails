"""Hillshade tiles out of a synthetic model, read back and checked."""

import json
import math

import numpy as np
import pytest
from affine import Affine
from PIL import Image
from trails.processing import shade_tiles
from trails.utils.tiles import TILE_PX


class TestBlur:
    def test_a_field_flatter_than_half_a_pixel_is_left_alone(self):
        field = np.array([[0.0, 9.0], [3.0, 1.0]], dtype=np.float32)
        assert np.array_equal(shade_tiles.blurred(field, 0.4), field)

    def test_a_spike_spreads_and_nothing_is_lost(self):
        field = np.zeros((21, 21), dtype=np.float32)
        field[10, 10] = 100.0
        out = shade_tiles.blurred(field, 2.0)
        assert out[10, 10] < 100.0
        assert out[10, 11] > 0.0
        # The edge is held rather than wrapped, so a Gaussian over a field with
        # room around the spike keeps its whole weight.
        assert abs(float(out.sum()) - 100.0) < 0.5

    def test_the_edge_is_held_and_not_wrapped(self):
        """A tile is computed with a margin and cut back. A wrapping blur would
        fold the far side of the patch into that margin, which is how a seam
        gets into a tree that was built to have none."""
        field = np.zeros((21, 21), dtype=np.float32)
        field[0, :] = 100.0
        out = shade_tiles.blurred(field, 2.0)
        assert out[0, 0] > 50.0, "the held edge keeps the top row near its own value"
        assert out[20, 0] < 0.01, "and nothing of it reaches the bottom"


class TestShade:
    def test_level_ground_catches_the_light_at_its_altitude(self):
        for altitude in (30.0, 45.0, 60.0):
            lit = shade_tiles.shade(np.zeros((5, 5)), 1.0, altitude=altitude)
            assert abs(float(lit[2, 2]) - math.sin(math.radians(altitude))) < 1e-6

    def test_the_light_comes_from_the_north_west(self):
        """The one mistake this is worth a test for: `np.gradient` hands back
        rows first, and naming those two the other way round lights the map from
        the south-east while every number in it stays plausible — which reads as
        every valley being a ridge."""
        rows, cols = np.mgrid[0:41, 0:41].astype(float)
        dome = -((rows - 20) ** 2 + (cols - 20) ** 2) * 0.1
        lit = shade_tiles.shade(dome, 1.0)
        north_west, south_east = float(lit[10, 10]), float(lit[30, 30])
        north_east, south_west = float(lit[10, 30]), float(lit[30, 10])
        assert north_west > 0.85, "the flank turned towards the light is nearly face-on to it"
        assert south_east == 0.0, "and the one turned away is in full shadow"
        assert abs(north_east - south_west) < 1e-6, "the two flanks across the light are alike"

    def test_nothing_is_darker_than_dark_or_brighter_than_face_on(self):
        rough = np.random.default_rng(7).normal(0.0, 30.0, (32, 32))
        lit = shade_tiles.shade(rough, 4.0)
        assert lit.min() >= 0.0
        assert lit.max() <= 1.0


class TestShadow:
    def test_level_ground_darkens_nothing(self):
        assert int(shade_tiles.shadow(shade_tiles.shade(np.zeros((3, 3)), 1.0))[1, 1]) == 0

    def test_full_shadow_is_opaque(self):
        assert int(shade_tiles.shadow(np.zeros((1, 1)))[0, 0]) == 255

    def test_it_is_stored_in_the_steps_the_tree_was_sized_for(self):
        """A shadow is a smooth ramp and PNG pays for every level of it. 64 steps
        halve the tree and put a 2.2-level step of 255 into the drawn sheet,
        which is under where banding is seen; both ends stay reachable, so level
        ground is still wholly clear and full shadow still wholly opaque."""
        ramp = np.linspace(0.0, 1.0, 257).reshape(1, -1)
        alpha = shade_tiles.shadow(ramp)
        assert len(np.unique(alpha)) == shade_tiles.STEPS
        assert alpha.min() == 0 and alpha.max() == 255
        assert len(np.unique(shade_tiles.shadow(ramp, steps=256))) > shade_tiles.STEPS

    def test_ground_brighter_than_level_is_left_alone(self):
        """Only what is turned away from the light darkens. A grey hillshade
        multiplied over the sheet takes the lit side down too, and the map goes
        grey with it — which is the encoding this one was chosen over."""
        assert int(shade_tiles.shadow(np.ones((1, 1)))[0, 0]) == 0


@pytest.fixture
def ridge():
    """A model in SWEREF 99 TM over the Abisko box: a ridge running north-east,
    steep enough that its two flanks cannot shade alike."""
    transform = Affine(50.0, 0.0, 600_000.0, 0.0, -50.0, 7_620_000.0)
    rows, cols = 1_200, 1_400
    east = (np.arange(cols) + 0.5) * 50.0
    north = -(np.arange(rows) + 0.5) * 50.0
    heights = (300.0 * np.sin((east[None, :] + north[:, None]) / 900.0)).astype(np.float32)
    return heights, transform, "EPSG:3006"


class TestBuildTiles:
    def test_a_tile_is_black_with_an_alpha_that_carries_the_relief(self, ridge, tmp_path):
        heights, transform, crs = ridge
        bounds = (18.40, 68.30, 18.45, 68.33)
        index = shade_tiles.build_tiles(heights, transform, crs, bounds, zooms=[14], out_dir=tmp_path / "shade")

        assert index["per_zoom"]["14"]["written"] == index["tiles"] > 0
        written = json.loads((tmp_path / "shade" / "index.json").read_text())
        assert written["azimuth"] == shade_tiles.AZIMUTH
        assert written["altitude"] == shade_tiles.ALTITUDE
        assert written["smooth_m"] == 50.0, "one post of this model"
        assert written["steps"] == shade_tiles.STEPS

        tile = next((tmp_path / "shade" / "14").rglob("*.png"))
        rgba = np.asarray(Image.open(tile).convert("RGBA"))
        assert rgba.shape == (TILE_PX, TILE_PX, 4)
        assert rgba[..., :3].max() == 0, "the colour is black everywhere; only the alpha varies"
        assert rgba[..., 3].max() > 0, "and a ridge has a shaded side"
        assert rgba[..., 3].min() == 0, "and a lit one, which the map shows through untouched"

    def test_ground_outside_the_model_darkens_nothing(self, ridge, tmp_path):
        heights, transform, crs = ridge
        bounds = (17.0, 68.30, 17.05, 68.33)  # west of the model
        index = shade_tiles.build_tiles(heights, transform, crs, bounds, zooms=[12], out_dir=tmp_path / "shade")
        assert index["per_zoom"]["12"]["empty"] == index["tiles"]
        rgba = np.asarray(Image.open(next((tmp_path / "shade" / "12").rglob("*.png"))).convert("RGBA"))
        assert rgba.max() == 0, "wholly transparent, so the sheet beneath is drawn exactly as it would be"

    def test_neighbouring_tiles_meet_without_a_seam(self, ridge, tmp_path):
        """The margin is what this is for. Cut without one, the gradient at a
        tile's border has no neighbour and every join in the tree draws as a
        line — over a whole map, a grid."""
        heights, transform, crs = ridge
        bounds = (18.40, 68.30, 18.45, 68.33)
        shade_tiles.build_tiles(heights, transform, crs, bounds, zooms=[14], out_dir=tmp_path / "shade")
        level = tmp_path / "shade" / "14"
        columns = sorted(int(where.name) for where in level.iterdir())
        rows = sorted(int(where.stem) for where in (level / str(columns[0])).iterdir())
        assert len(columns) > 1 and len(rows) > 1, "the box has to span a join for this to say anything"
        left = np.asarray(Image.open(level / str(columns[0]) / f"{rows[0]}.png").convert("RGBA"))[..., 3].astype(int)
        right = np.asarray(Image.open(level / str(columns[1]) / f"{rows[0]}.png").convert("RGBA"))[..., 3].astype(int)
        across = abs(int(left[:, -1].mean()) - int(right[:, 0].mean()))
        within = abs(int(left[:, -1].mean()) - int(left[:, -2].mean()))
        assert across <= within + 4, "the step over the join is no bigger than a step inside a tile"

    def test_a_second_run_skips_what_is_there(self, ridge, tmp_path):
        heights, transform, crs = ridge
        bounds = (18.40, 68.30, 18.45, 68.33)
        shade_tiles.build_tiles(heights, transform, crs, bounds, zooms=[12, 13], out_dir=tmp_path / "shade")
        again = shade_tiles.build_tiles(heights, transform, crs, bounds, zooms=[12, 13], out_dir=tmp_path / "shade")
        assert again["per_zoom"]["13"]["written"] == 0
        assert again["per_zoom"]["13"]["skipped"] == again["per_zoom"]["13"]["tiles"]
        assert not list((tmp_path / "shade").rglob("*.part"))
