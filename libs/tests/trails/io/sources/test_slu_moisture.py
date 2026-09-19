"""The soil-moisture mosaic, read by window out of a stand-in file."""

import numpy as np
import pytest
import rasterio
from affine import Affine
from trails.io.sources import slu_moisture


@pytest.fixture
def mosaic(tmp_path):
    """A 100 × 100 cell stand-in at 2 m on a whole-metre origin, moist-wet in its south-east quarter."""
    source = slu_moisture.Source(cache_dir=tmp_path)
    source.cache_dir.mkdir(parents=True)
    classes = np.full((100, 100), slu_moisture.DRY_FRESH, dtype=np.uint8)
    classes[50:, 50:] = slu_moisture.MOIST_WET
    transform = Affine(2.0, 0.0, 650_000.0, 0.0, -2.0, 7_580_200.0)
    with rasterio.open(
        source.mosaic, "w", driver="GTiff", height=100, width=100, count=1, dtype="uint8", crs=slu_moisture.CRS, transform=transform,
        nodata=slu_moisture.NODATA,
    ) as out:  # fmt: skip
        out.write(classes, 1)
    return source


class TestClasses:
    def test_a_window_is_read_at_the_mosaics_own_grain(self, mosaic):
        read, transform = mosaic.classes((650_100.0, 7_580_000.0, 650_200.0, 7_580_100.0))
        assert read.shape == (50, 50) and transform.c == 650_100.0 and transform.f == 7_580_100.0
        assert (read == slu_moisture.MOIST_WET).all()

    def test_past_the_mosaics_edge_is_nodata(self, mosaic):
        read, _ = mosaic.classes((649_900.0, 7_580_100.0, 650_100.0, 7_580_300.0))
        assert read.shape == (100, 100)
        assert (read[:50, :] == slu_moisture.NODATA).all() and (read[:, :50] == slu_moisture.NODATA).all()
        assert (read[50:, 50:] == slu_moisture.DRY_FRESH).all()


class TestFetch:
    def test_a_cold_cache_without_the_login_is_a_named_failure(self, tmp_path):
        source = slu_moisture.Source(cache_dir=tmp_path, username="", password="")
        with pytest.raises(RuntimeError, match="FTPS login"):
            source.fetch()

    def test_a_cached_mosaic_is_not_fetched_again(self, mosaic):
        assert mosaic.fetch() == mosaic.mosaic
