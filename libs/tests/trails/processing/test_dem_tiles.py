"""Height tiles out of a synthetic model, read back and checked."""

import json

import numpy as np
import pytest
from affine import Affine
from PIL import Image
from rasterio.crs import CRS
from rasterio.warp import transform as warp_transform
from trails.processing import dem_tiles
from trails.utils.tiles import TILE_PX, tile_bounds


class TestPacking:
    def test_round_trip_to_the_blue_step(self):
        heights = np.array([[-12.5, 0.0, 341.85], [1242.04, 8848.86, -32768.0]], dtype=np.float32)
        back = dem_tiles.unpack(dem_tiles.pack(heights))
        assert np.allclose(back, heights, atol=1 / 512)

    def test_sea_level_is_the_known_triple(self):
        assert dem_tiles.pack(np.array([0.0]))[0].tolist() == [128, 0, 0]

    def test_missing_packs_to_black_and_unpacks_to_the_floor(self):
        rgb = dem_tiles.pack(np.array([np.nan, -9999.0, 5.0]), nodata=-9999.0)
        assert rgb[0].tolist() == [0, 0, 0]
        assert rgb[1].tolist() == [0, 0, 0]
        assert rgb[2].tolist() != [0, 0, 0]
        assert dem_tiles.unpack(rgb)[0] == dem_tiles.MISSING_M


@pytest.fixture
def plane():
    """A model in SWEREF 99 TM over the Abisko box whose height is a plane in
    the projected coordinates: height = (east − 600,000) / 100 + (north − 7,560,000) / 100."""
    transform = Affine(50.0, 0.0, 600_000.0, 0.0, -50.0, 7_620_000.0)
    rows, cols = 1_200, 1_400  # 60 km × 70 km at 50 m posts
    east = 600_000.0 + (np.arange(cols) + 0.5) * 50.0
    north = 7_620_000.0 - (np.arange(rows) + 0.5) * 50.0
    heights = ((east[None, :] - 600_000.0) / 100.0 + (north[:, None] - 7_560_000.0) / 100.0).astype(np.float32)
    return heights, transform, "EPSG:3006"


class TestBuildTiles:
    def test_a_tile_carries_the_plane(self, plane, tmp_path):
        heights, transform, crs = plane
        bounds = (18.40, 68.30, 18.45, 68.33)
        index = dem_tiles.build_tiles(heights, transform, crs, bounds, zooms=[13], out_dir=tmp_path / "dem")

        assert index["per_zoom"]["13"]["written"] == index["tiles"] > 0
        assert index["per_zoom"]["13"]["empty"] == 0
        assert json.loads((tmp_path / "dem" / "index.json").read_text())["encoding"] == "terrarium"
        tile = next((tmp_path / "dem" / "13").rglob("*.png"))
        z, x, y = 13, int(tile.parent.name), int(tile.stem)
        rgb = np.asarray(Image.open(tile).convert("RGB"))
        assert rgb.shape == (TILE_PX, TILE_PX, 3)
        back = dem_tiles.unpack(rgb)
        # The tile's centre, in the model's own coordinates, and the plane there.
        min_x, min_y, max_x, max_y = tile_bounds(z, x, y)
        (east,), (north,) = warp_transform(CRS.from_epsg(3857), CRS.from_epsg(3006), [(min_x + max_x) / 2], [(min_y + max_y) / 2])
        expected = (east - 600_000.0) / 100.0 + (north - 7_560_000.0) / 100.0
        assert abs(float(back[TILE_PX // 2, TILE_PX // 2]) - expected) < 0.5, "bilinear off 50 m posts lands within half a metre on a plane"

    def test_ground_outside_the_model_is_missing_not_zero(self, plane, tmp_path):
        heights, transform, crs = plane
        bounds = (17.0, 68.30, 17.05, 68.33)  # west of the model
        index = dem_tiles.build_tiles(heights, transform, crs, bounds, zooms=[12], out_dir=tmp_path / "dem")
        assert index["per_zoom"]["12"]["empty"] == index["tiles"]
        tile = next((tmp_path / "dem" / "12").rglob("*.png"))
        rgb = np.asarray(Image.open(tile).convert("RGB"))
        assert rgb.max() == 0

    def test_a_second_run_skips_what_is_there(self, plane, tmp_path):
        heights, transform, crs = plane
        bounds = (18.40, 68.30, 18.45, 68.33)
        dem_tiles.build_tiles(heights, transform, crs, bounds, zooms=[11, 12], out_dir=tmp_path / "dem")
        again = dem_tiles.build_tiles(heights, transform, crs, bounds, zooms=[11, 12], out_dir=tmp_path / "dem")
        assert again["per_zoom"]["12"]["written"] == 0
        assert again["per_zoom"]["12"]["skipped"] == again["per_zoom"]["12"]["tiles"]
        assert not list((tmp_path / "dem").rglob("*.part"))
