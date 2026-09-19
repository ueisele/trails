"""The Norwegian mire classes out of stand-ins for the municipality register and N50."""

import geopandas as gpd
import numpy as np
from shapely.geometry import box
from trails.io.sources import mire, mire_norway

#: A small box in the park: about 0.9 × 0.6 km.
BOX = (12.90, 65.500, 12.92, 65.505)


class Register:
    def __init__(self):
        self.asked = []

    def intersecting(self, area, fylke=None):
        self.asked.append((tuple(area.total_bounds), fylke))
        return ["1816"]


class LandCover:
    def __init__(self):
        self.asked = []

    def load_mire(self, kommune_codes, force_download=False):
        self.asked.append((kommune_codes, force_download))
        # A bog over the western third of the box, in WGS 84 as N50 is delivered.
        west, south, east, north = BOX
        bog = box(west, south, west + (east - west) / 3, north)
        return gpd.GeoDataFrame({"objtype": ["Myr"], "kommune": ["1816"]}, geometry=[bog], crs="EPSG:4326")


class TestMire:
    def test_every_bog_is_firm_mire_and_the_rest_is_nothing(self, tmp_path):
        register, cover = Register(), LandCover()
        classes, transform = mire_norway.Source(cache_dir=tmp_path, land_cover=cover, register=register).mire(BOX)
        shape, expected = mire.grid(BOX, mire_norway.CRS)
        assert classes.shape == shape and transform == expected
        assert set(np.unique(classes).tolist()) == {0, mire.FIRM_MIRE}
        share = (classes == mire.FIRM_MIRE).mean()
        assert 0.25 < share < 0.4
        assert register.asked[0][1] == mire_norway.COUNTIES
        assert cover.asked == [(["1816"], False)]

    def test_the_cut_is_cached_and_read_back(self, tmp_path):
        cover = LandCover()
        source = mire_norway.Source(cache_dir=tmp_path, land_cover=cover, register=Register())
        first, _ = source.mire(BOX)
        again, _ = source.mire(BOX)
        assert len(cover.asked) == 1 and np.array_equal(first, again)
        source.mire(BOX, force_download=True)
        assert cover.asked[-1] == (["1816"], True)
