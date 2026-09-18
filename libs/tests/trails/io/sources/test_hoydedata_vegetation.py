"""Norway's vegetation codes out of two synthetic models, and the source that reads them."""

import numpy as np
import pytest
import rasterio
from affine import Affine
from rasterio.io import MemoryFile
from trails.io.sources import hoydedata_vegetation as veg
from trails.io.sources import nmd


class TestCodes:
    def test_cover_codes_are_the_upper_bound_of_the_class(self):
        share = np.array([0.0, 0.04, 0.05, 0.2, 0.21, 0.7, 1.0])
        assert veg.cover_code(share).tolist() == [0, 5, 5, 20, 30, 70, 100]

    def test_height_codes_are_the_upper_bound_too(self):
        top = np.array([0.6, 1.0, 1.1, 3.0, 4.9])
        assert veg.height_code(top, np.ones(5, dtype=bool)).tolist() == [1, 1, 3, 3, 5]
        assert veg.height_code(top, np.zeros(5, dtype=bool)).tolist() == [0] * 5

    def test_a_cell_is_classed_from_its_posts(self):
        posts = veg.PER_CELL
        terrain = np.zeros((2 * posts, 2 * posts), dtype=np.float32)
        surface = terrain.copy()
        surface[:posts, :posts] += 0.8  # knee-high on every post
        surface[:posts, posts:][:2, :] += 2.0  # 1–3 m on two rows of five: 40 %
        surface[posts:, :posts] += 12.0  # trees
        codes = veg.codes_from(surface, terrain)
        assert codes[:, 0, 0].tolist() == [1, 100, 0]
        assert codes[:, 0, 1].tolist() == [3, 40, 0]
        assert codes[:, 1, 0].tolist() == [0, 0, 100]
        assert codes[:, 1, 1].tolist() == [0, 0, 0]

    def test_a_cell_the_models_have_nothing_for_is_unknown(self):
        posts = veg.PER_CELL
        terrain = np.full((posts, 2 * posts), veg.NODATA, dtype=np.float32)
        surface = terrain.copy()
        terrain[:, posts:] = 100.0
        surface[:, posts:] = 100.0
        codes = veg.codes_from(surface, terrain)
        assert codes[:, 0, 0].tolist() == [nmd.UNKNOWN] * 3
        assert codes[:, 0, 1].tolist() == [0, 0, 0]

    def test_models_of_different_shapes_are_refused(self):
        with pytest.raises(ValueError, match="surface is"):
            veg.codes_from(np.zeros((5, 5)), np.zeros((5, 10)))


def _tiff(square, value):
    with MemoryFile() as held:
        with held.open(
            driver="GTiff", height=square.height, width=square.width, count=1, dtype="float32", crs=veg.CRS,
            transform=Affine(veg.POSTS_M, 0.0, square.bounds[0], 0.0, -veg.POSTS_M, square.bounds[3]), nodata=veg.NODATA,
        ) as out:  # fmt: skip
            out.write(np.full((square.height, square.width), value, dtype=np.float32), 1)
        return held.read()


class TestSource:
    def test_the_box_is_read_square_by_square_and_cached(self, tmp_path, monkeypatch):
        """Ten metres of surface over nought of terrain: every cell is forest, and the second read is the cache's."""
        monkeypatch.setattr(veg, "CHUNK_M", 50.0)
        asked = []

        def fetch(url):
            asked.append(url)
            # The query is percent-encoded, so the comma between west and south is `%2C`.
            square = next(s for s in squares if f"{s.bounds[0]:.3f}%2C{s.bounds[1]:.3f}" in url)
            return _tiff(square, 10.0 if "DOM" in url else 0.0)

        box = _box(400_010.0, 7_260_010.0, 400_090.0, 7_260_090.0)
        squares, _, _, _ = veg.squares_over(box, veg.POSTS_M, 50.0)
        source = veg.Source(cache_dir=tmp_path, fetch=fetch)
        codes, transform = source.structure(box)
        assert codes.shape == (3, 10, 10)
        assert transform.a == 10.0
        assert (codes[2] == 100).all() and (codes[0] == 0).all()
        assert len(asked) == 2 * len(squares)
        again, _ = source.structure(box)
        assert len(asked) == 2 * len(squares)
        assert again.tolist() == codes.tolist()
        with rasterio.open(next(tmp_path.glob("vegetation/hoydedata/codes_*.tif"))) as kept:
            assert kept.descriptions == nmd.BANDS


def _box(west, south, east, north):
    from rasterio.warp import transform_bounds

    return tuple(transform_bounds(veg.CRS, "EPSG:4326", west, south, east, north))
