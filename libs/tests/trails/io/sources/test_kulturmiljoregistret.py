"""Kulturmiljöregistret: the county file on disk, read by box, one row per remain."""

import geopandas as gpd
import pytest
from shapely.geometry import Point
from trails.io.sources import kulturmiljoregistret as kmr

ABISKO = (18.15, 68.139, 19.10, 68.46)


def _remains() -> gpd.GeoDataFrame:
    """A kåta with two geometries, a fäbod, a hearth, and a house foundation with no name."""
    return gpd.GeoDataFrame(
        {
            kmr.ID: ["a", "a", "b", "c", "d"],
            kmr.TYPE: ["Kåta", "Kåta", "Fäbod", "Härd", "Husgrund, historisk tid"],
            kmr.NAME: ["Vuolip Njuorajávri", "Vuolip Njuorajávri", "Gammelvallen", None, ""],
            kmr.DESCRIPTION: ["Kåtatomt, rund", "Kåtatomt, rund", "Fäbodlämning", "Härd", "Husgrund"],
            kmr.ASSESSMENT: ["Övrig kulturhistorisk lämning"] * 5,
            kmr.URL: [f"https://pub.raa.se/visa/objekt/lamning/{i}" for i in ("a", "a", "b", "c", "d")],
            "geometrinummer": [1, 2, 1, 1, 1],
        },
        geometry=[Point(650000 + 100 * i, 7580000) for i in range(5)],
        crs=kmr.CRS,
    )


def _file_on_disk(root) -> None:
    directory = root / "kulturmiljoregistret"
    directory.mkdir(parents=True)
    _remains().to_file(directory / "lamningar_lan_norrbotten.gpkg", layer=kmr.POINT_LAYER.format(county="norrbotten"), driver="GPKG")


class TestOnDisk:
    def test_the_dwelling_types_are_read_once_each(self, tmp_path):
        """The hearth is not a dwelling; the kåta's second geometry is the same kåta."""
        _file_on_disk(tmp_path)
        source = kmr.Source("norrbotten", cache_dir=tmp_path)
        got = source.remains(ABISKO)
        assert got["kind"].tolist() == ["Kåta", "Fäbod", "Husgrund, historisk tid"]
        assert got["remain_id"].tolist() == ["a", "b", "d"]
        assert got.crs.to_epsg() == 4326
        assert source.version is not None

    def test_an_empty_name_is_none_and_the_page_link_is_kept(self, tmp_path):
        _file_on_disk(tmp_path)
        got = kmr.Source("norrbotten", cache_dir=tmp_path).remains(ABISKO)
        assert got["name"].tolist() == ["Vuolip Njuorajávri", "Gammelvallen", None]
        assert got[kmr.URL].tolist()[1] == "https://pub.raa.se/visa/objekt/lamning/b"

    def test_every_type_can_be_asked_for(self, tmp_path):
        _file_on_disk(tmp_path)
        got = kmr.Source("norrbotten", cache_dir=tmp_path).remains(ABISKO, types=None)
        assert sorted(got["kind"]) == ["Fäbod", "Husgrund, historisk tid", "Härd", "Kåta"]

    def test_the_county_names_the_file_and_the_layer(self, tmp_path):
        source = kmr.Source("Norrbotten", cache_dir=tmp_path)
        assert source.geopackage.name == "lamningar_lan_norrbotten.gpkg"
        assert kmr.FILE_URL.format(county=source.county).endswith("l%C3%A4n_norrbotten.gpkg")


class TestFetch:
    def test_a_missing_file_is_fetched_through_a_part_file(self, tmp_path, monkeypatch):
        """Nothing on disk, so it is downloaded -- and the final name appears only when the download is whole."""
        written: list[str] = []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def raise_for_status(self):
                return None

            def iter_content(self, size):
                yield b"not a geopackage, but the bytes the server sent"

        def get(url, timeout, stream, headers):
            written.append(url)
            return Response()

        monkeypatch.setattr(kmr.requests, "get", get)
        source = kmr.Source("norrbotten", cache_dir=tmp_path)
        path = source.fetch()
        assert path.exists() and not path.with_name(path.name + ".part").exists()
        assert written == [kmr.FILE_URL.format(county="norrbotten")]
        assert source.version is not None

    def test_a_file_on_disk_is_not_fetched_again(self, tmp_path, monkeypatch):
        _file_on_disk(tmp_path)
        monkeypatch.setattr(kmr.requests, "get", lambda *a, **k: pytest.fail("fetched although the file is here"))
        kmr.Source("norrbotten", cache_dir=tmp_path).fetch()
