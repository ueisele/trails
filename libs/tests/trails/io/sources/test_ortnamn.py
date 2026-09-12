"""Ortnamn: the file on disk, the login when it is not, and reading a box."""

import zipfile

import geopandas as gpd
import pytest
from shapely.geometry import Point
from trails.io.sources import ortnamn

ABISKO = (18.15, 68.17, 19.00, 68.46)


def _names() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            ortnamn.NAME: ["Lapporten", "Torneträsk", "Abisko", "Kiruna kyrka"],
            ortnamn.TYPE: ["TERRTX", "VATTTX", "BEBTX", "KYRKATX"],
            ortnamn.LANGUAGE: ["SV", "SV", "SV", "SV"],
            ortnamn.ID: [1.0, 2.0, 3.0, 4.0],
        },
        geometry=[Point(650000 + 100 * i, 7580000) for i in range(4)],
        crs=ortnamn.CRS,
    )


def _file_on_disk(root, day=(2026, 9, 12)):
    directory = root / "ortnamn"
    directory.mkdir(parents=True)
    gpkg = directory / "ortnamn_se.gpkg"
    _names().to_file(gpkg, layer=ortnamn.LAYER, driver="GPKG")
    archive = directory / "ortnamn_se.zip"
    with zipfile.ZipFile(archive, "w") as out:
        info = zipfile.ZipInfo("ortnamn_se.gpkg", date_time=(*day, 3, 16, 0))
        out.writestr(info, gpkg.read_bytes())
    gpkg.unlink()
    return archive


class TestOnDisk:
    def test_the_file_is_read_by_box_and_typed(self, tmp_path):
        _file_on_disk(tmp_path)
        source = ortnamn.Source(cache_dir=tmp_path, username="", password="")
        names = source.names(ABISKO)
        assert names["name"].tolist() == ["Lapporten", "Torneträsk", "Abisko"]
        assert names["kind_label"].tolist() == ["terrain", "lake", "settlement or building"]
        assert names["language"].tolist() == ["Swedish"] * 3
        assert names.crs.to_epsg() == 4326
        assert source.version == "2026-09-12"

    def test_every_type_can_be_asked_for(self, tmp_path):
        _file_on_disk(tmp_path)
        source = ortnamn.Source(cache_dir=tmp_path, username="", password="")
        assert len(source.names(ABISKO, types=None)) == 4

    def test_without_the_file_or_the_login_it_says_what_is_missing(self, tmp_path):
        source = ortnamn.Source(cache_dir=tmp_path, username="", password="")
        with pytest.raises(RuntimeError, match=ortnamn.USERNAME_VAR):
            source.names(ABISKO)


class TestFetch:
    def test_the_file_is_fetched_once_with_the_login(self, tmp_path):
        held = _file_on_disk(tmp_path / "elsewhere").read_bytes()
        asked = []

        def download(url, auth, target):
            asked.append((url, auth))
            target.write_bytes(held)

        source = ortnamn.Source(cache_dir=tmp_path, username="u", password="p", download=download)
        assert len(source.names(ABISKO)) == 3
        assert len(source.names(ABISKO)) == 3
        assert asked == [(ortnamn.FILE_URL, ortnamn._auth_header("u", "p"))]


class TestTypes:
    def test_the_drawn_types_are_known_and_the_rest_pass_through(self):
        assert set(ortnamn.NAME_TYPES) <= set(ortnamn.TYPES)
        assert ortnamn.type_label("TRAKTTX") == "tract"
        assert ortnamn.type_label("XTX") == "XTX"
        assert ortnamn.language_label("NS") == "North Sámi"
