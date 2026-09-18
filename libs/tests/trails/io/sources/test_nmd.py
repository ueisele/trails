"""NMD's rasters, converted and cut, without the 10 GB behind them."""

import numpy as np
import rasterio
from affine import Affine
from trails.io.sources import nmd


def _write(path, data, nodata=None, north=7_600_000.0):
    with rasterio.open(
        path, "w", driver="GTiff", height=data.shape[0], width=data.shape[1], count=1, dtype="uint8", crs=nmd.CRS,
        transform=Affine(10.0, 0.0, 600_000.0, 0.0, -10.0, north), nodata=nodata,
    ) as out:  # fmt: skip
        out.write(data, 1)


class TestConvert:
    def test_a_raster_is_rewritten_as_it_is(self, tmp_path):
        data = np.array([[1, 3, 5, 255], [255, 255, 1, 1]], dtype=np.uint8)
        _write(tmp_path / "in.tif", data, nodata=255)
        nmd.convert(tmp_path / "in.tif", tmp_path / "out.tif")
        with rasterio.open(tmp_path / "out.tif") as out:
            assert out.read(1).tolist() == data.tolist()
            assert out.nodata == 255
            assert out.compression is not None

    def test_a_mask_is_one_where_the_raster_is_anything(self, tmp_path):
        data = np.array([[0, 7, 250], [0, 0, 1]], dtype=np.uint8)
        _write(tmp_path / "in.tif", data)
        nmd.convert(tmp_path / "in.tif", tmp_path / "out.tif", as_mask=True)
        with rasterio.open(tmp_path / "out.tif") as out:
            assert out.read(1).tolist() == [[0, 1, 1], [0, 0, 1]]


class TestStructure:
    def _source(self, tmp_path):
        source = nmd.Source(cache_dir=tmp_path, fetch=lambda url, target: (_ for _ in ()).throw(AssertionError(url)))
        source.cache_dir.mkdir(parents=True)
        return source

    def test_the_two_kinds_of_nothing_are_told_apart(self, tmp_path):
        """255 where the laser flew is *nothing there*; past the flight strips it stays unknown."""
        source = self._source(tmp_path)
        height = np.full((4, 4), 255, dtype=np.uint8)
        height[0, 0], height[1, 1] = 3, 5
        cover = np.full((4, 4), 255, dtype=np.uint8)
        cover[0, 0], cover[1, 1] = 40, 90
        tall = np.full((4, 4), 255, dtype=np.uint8)
        tall[2, 2] = 60
        scanned = np.ones((4, 4), dtype=np.uint8)
        scanned[3, :] = 0
        _write(source.cache_dir / "low_height.tif", height, nodata=255)
        _write(source.cache_dir / "low_cover.tif", cover, nodata=255)
        _write(source.cache_dir / "tall_cover.tif", tall, nodata=255)
        _write(source.cache_dir / "scanned.tif", scanned)
        # A box strictly inside the 40 × 40 m raster, in WGS 84.
        codes, transform = source.structure(_box(600_005.0, 7_599_965.0, 600_035.0, 7_599_995.0))
        assert codes.shape[0] == 3 and codes.dtype == np.uint8
        assert transform.a == 10.0 and transform.e == -10.0
        # Row 3 was never flown: unknown in every band. Elsewhere 255 became 0.
        assert (codes[:, 3, :] == nmd.UNKNOWN).all()
        assert int(codes[0, 0, 0]) == 3 and int(codes[1, 0, 0]) == 40
        assert int(codes[0, 0, 1]) == 0 and int(codes[1, 0, 1]) == 0
        assert int(codes[2, 2, 2]) == 60 and int(codes[2, 0, 0]) == 0

    def test_a_raster_on_a_taller_grid_is_read_over_the_same_ground(self, tmp_path):
        """The tall-cover raster starts 65 rows further north than the others;
        a cell is matched by where it is, not by its row."""
        source = self._source(tmp_path)
        _write(source.cache_dir / "low_height.tif", np.full((4, 4), 255, dtype=np.uint8), nodata=255)
        _write(source.cache_dir / "low_cover.tif", np.full((4, 4), 255, dtype=np.uint8), nodata=255)
        tall = np.full((6, 4), 255, dtype=np.uint8)
        tall[2 + 1, 1] = 70  # two rows further down in a raster that starts two rows further north
        _write(source.cache_dir / "tall_cover.tif", tall, nodata=255, north=7_600_020.0)
        _write(source.cache_dir / "scanned.tif", np.ones((4, 4), dtype=np.uint8))
        codes, _ = source.structure(_box(600_005.0, 7_599_965.0, 600_035.0, 7_599_995.0))
        assert int(codes[2, 1, 1]) == 70
        assert int((codes[2] == 70).sum()) == 1

    def test_the_cut_is_cached_and_read_back(self, tmp_path):
        source = self._source(tmp_path)
        for name in ("low_height.tif", "low_cover.tif", "tall_cover.tif"):
            _write(source.cache_dir / name, np.full((4, 4), 255, dtype=np.uint8), nodata=255)
        _write(source.cache_dir / "scanned.tif", np.ones((4, 4), dtype=np.uint8))
        box = _box(600_005.0, 7_599_965.0, 600_035.0, 7_599_995.0)
        first, _ = source.structure(box)
        assert list(source.cache_dir.glob("structure_*.tif"))
        again, _ = source.structure(box)
        assert again.tolist() == first.tolist()


def _box(west, south, east, north):
    from rasterio.warp import transform_bounds

    return tuple(transform_bounds(nmd.CRS, "EPSG:4326", west, south, east, north))
