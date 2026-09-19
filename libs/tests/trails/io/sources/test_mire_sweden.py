"""The Swedish mire classes out of stand-ins for the sheet's wetlands and the moisture model."""

import geopandas as gpd
import numpy as np
import rasterio
from affine import Affine
from shapely.geometry import box
from trails.io.sources import mire, mire_sweden, slu_moisture

#: A small box near Abisko: about 0.9 × 0.6 km.
BOX = (18.80, 68.350, 18.82, 68.355)


class Wetlands:
    """Stands in for :class:`trails.io.sources.marktacke.Source`: a firm mire in the north-west, a wet one inside it."""

    def __init__(self):
        self.calls = 0

    def wetlands(self, bounds, force_download=False):
        self.calls += 1
        shape, transform = mire.grid(bounds, mire_sweden.CRS)
        west, north = transform * (0, 0)
        firm = box(west, north - 200, west + 300, north)
        wet = box(west, north - 50, west + 50, north)
        return gpd.GeoDataFrame({"objekttyp": ["Sankmark, fast", "Sankmark, våt"], "wet": [False, True]}, geometry=[firm, wet], crs=mire_sweden.CRS)


class Moisture:
    """Stands in for :class:`trails.io.sources.slu_moisture.Source`: wet in a band across the south, water in the south-east corner."""

    def __init__(self, wet_share=1.0):
        self.wet_share = wet_share

    def classes(self, bounds):
        west, south, east, north = bounds
        cols = int(round((east - west) / slu_moisture.CELL_M))
        rows = int(round((north - south) / slu_moisture.CELL_M))
        fine = np.full((rows, cols), slu_moisture.DRY_FRESH, dtype=np.uint8)
        band = fine[rows - 50 : rows - 25, :]
        # Every 10 m cell of the band has the same share of its 25 sub-cells wet.
        wet_rows = int(round(5 * self.wet_share))
        for block in range(0, 25, 5):
            band[block : block + wet_rows, :] = slu_moisture.MOIST_WET
        fine[rows - 25 :, cols - 25 :] = slu_moisture.WATER
        # The moisture model also calls the firm mire wet, which must not move it.
        fine[:100, :150] = slu_moisture.MOIST_WET
        return fine, Affine(slu_moisture.CELL_M, 0.0, west, 0.0, -slu_moisture.CELL_M, north)


class TestMire:
    def test_the_survey_wins_the_model_adds_and_water_is_nothing(self, tmp_path):
        source = mire_sweden.Source(cache_dir=tmp_path, wetlands=Wetlands(), moisture=Moisture())
        classes, transform = source.mire(BOX)
        shape, expected = mire.grid(BOX, mire_sweden.CRS)
        assert classes.shape == shape and transform == expected
        assert classes[:5, :5].tolist() == [[mire.WET_MIRE] * 5] * 5
        assert (classes[:20, :30] == mire.FIRM_MIRE).sum() == 20 * 30 - 25
        assert set(classes[-10:-5, : shape[1] - 5].ravel().tolist()) == {mire.WET_GROUND}
        assert classes[-5:, -5:].sum() == 0
        assert (tmp_path / "mire").glob("sweden_*.tif")

    def test_half_the_sub_cells_wet_is_wet_ground_and_fewer_is_not(self, tmp_path):
        half, _ = mire_sweden.Source(cache_dir=tmp_path / "half", wetlands=Wetlands(), moisture=Moisture(0.6)).mire(BOX)
        few, _ = mire_sweden.Source(cache_dir=tmp_path / "few", wetlands=Wetlands(), moisture=Moisture(0.4)).mire(BOX)
        assert (half == mire.WET_GROUND).any()
        assert not (few == mire.WET_GROUND).any()

    def test_the_cut_is_cached_and_read_back(self, tmp_path):
        wetlands = Wetlands()
        source = mire_sweden.Source(cache_dir=tmp_path, wetlands=wetlands, moisture=Moisture())
        first, transform = source.mire(BOX)
        again, transform_again = source.mire(BOX)
        assert wetlands.calls == 1
        assert np.array_equal(first, again) and transform == transform_again
        with rasterio.open(next((tmp_path / "mire").glob("sweden_*.tif"))) as kept:
            assert kept.crs.to_string() == mire_sweden.CRS and kept.count == 1
        source.mire(BOX, force_download=True)
        assert wetlands.calls == 2
