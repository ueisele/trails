"""The height model's squares, found and laid into a mosaic, against local stand-ins."""

import numpy as np
import pytest
import rasterio
from affine import Affine
from trails.io.sources import markhojd

ABISKO = (18.15, 68.17, 19.00, 68.46)


def _item(east: float, north: float, href: str) -> dict:
    return {
        "id": f"{int(north / 10000)}_{int(east / 10000)}_{int(east % 10000):04d}",
        "properties": {"proj:bbox": [east, north, east + 2500.0, north + 2500.0], "proj:code": "EPSG:5845"},
        "assets": {"data": {"href": href, "type": "image/tiff; application=geotiff; profile=cloud-optimized"}},
    }


class TestSearch:
    def test_it_follows_every_page_and_sorts_by_id(self):
        pages = {
            "first": {"features": [_item(660000.0, 7592500.0, "b.tif")], "links": [{"rel": "next", "href": "second"}]},
            "second": {"features": [_item(640000.0, 7580000.0, "a.tif")], "links": []},
        }
        asked = []

        def fetch(url):
            asked.append(url)
            return pages["first" if "items?" in url else url]

        squares = markhojd.search(ABISKO, fetch)
        assert [square.href for square in squares] == ["a.tif", "b.tif"]
        assert squares[0].bounds == (640000.0, 7580000.0, 642500.0, 7582500.0)
        assert asked[0].startswith(f"{markhojd.STAC_URL}/collections/{markhojd.COLLECTION}/items?bbox=18.150000,68.170000,19.000000,68.460000")


@pytest.fixture
def squares(tmp_path):
    """Two squares side by side, 1 m posts, each a constant height, with overviews."""
    made = []
    for east, height in ((640000.0, 100.0), (642500.0, 200.0)):
        path = tmp_path / f"{int(east)}.tif"
        transform = Affine(1.0, 0.0, east, 0.0, -1.0, 7582500.0)
        shape = {"driver": "GTiff", "height": 2500, "width": 2500, "count": 1, "dtype": "float32", "tiled": True}
        with rasterio.open(path, "w", crs=markhojd.CRS, transform=transform, nodata=markhojd.NODATA, **shape) as file:
            file.write(np.full((2500, 2500), height, dtype=np.float32), 1)
            file.build_overviews([2, 4, 8])
        made.append((east, str(path)))
    return made


class TestMosaic:
    def test_squares_land_where_they_belong(self, squares, tmp_path):
        page = {"features": [_item(east, 7580000.0, href) for east, href in squares], "links": []}
        source = markhojd.Source(cache_dir=tmp_path / "cache", username="u", password="p", fetch=lambda url: page)
        heights, transform = source.mosaic(ABISKO, posts_m=8.0)
        assert heights.shape == (313, 626) or heights.shape == (312, 625)
        assert transform.a == 8.0 and transform.e == -8.0
        assert transform.c == 640000.0 and transform.f == 7582500.0
        assert heights[10, 10] == 100.0
        assert heights[10, -10] == 200.0
        cached = list((tmp_path / "cache" / "elevation").glob("markhojd_*_8m.tif"))
        assert len(cached) == 1

    def test_the_second_call_reads_the_cache(self, squares, tmp_path):
        page = {"features": [_item(east, 7580000.0, href) for east, href in squares], "links": []}
        calls = []

        def fetch(url):
            calls.append(url)
            return page

        source = markhojd.Source(cache_dir=tmp_path / "cache", username="u", password="p", fetch=fetch)
        first, _ = source.mosaic(ABISKO, posts_m=8.0)
        second, _ = source.mosaic(ABISKO, posts_m=8.0)
        assert len(calls) == 1
        assert np.array_equal(first, second)

    def test_without_a_login_it_says_so(self, squares, tmp_path):
        page = {"features": [_item(east, 7580000.0, href) for east, href in squares], "links": []}
        source = markhojd.Source(cache_dir=tmp_path / "cache", username="", password="", fetch=lambda url: page)
        with pytest.raises(RuntimeError, match=markhojd.USERNAME_VAR):
            source.mosaic(ABISKO, posts_m=8.0)

    def test_a_level_the_files_lack_is_refused(self, tmp_path):
        source = markhojd.Source(cache_dir=tmp_path, username="u", password="p", fetch=lambda url: {"features": [], "links": []})
        with pytest.raises(ValueError, match="overviews"):
            source.mosaic(ABISKO, posts_m=3.0)
