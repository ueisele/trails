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


def _placed(rows: list[tuple[str, str, str, float, float]]) -> gpd.GeoDataFrame:
    """Names as ``Source.names`` hands them on: (name, type, language, east, north) in SWEREF."""
    frame = gpd.GeoDataFrame(
        {
            ortnamn.NAME: [row[0] for row in rows],
            ortnamn.TYPE: [row[1] for row in rows],
            ortnamn.LANGUAGE: [row[2] for row in rows],
            ortnamn.ID: [float(i) for i in range(len(rows))],
        },
        geometry=[Point(row[3], row[4]) for row in rows],
        crs=ortnamn.CRS,
    ).to_crs("EPSG:4326")
    frame["name"] = frame[ortnamn.NAME]
    frame["kind"] = frame[ortnamn.TYPE]
    frame["language"] = frame[ortnamn.LANGUAGE].map(ortnamn.language_label)
    return frame


class TestPairing:
    def test_two_languages_within_reach_are_one_place_swedish_first(self):
        """The register puts the Sámi name of the Abiskojåkka 46 m from the
        Swedish one; joined, the place reads Swedish first and Sámi in brackets,
        whichever order the file listed them in."""
        names = _placed([("Ábeskoeatnu", "VATTDRTX", "NS", 650000, 7580000), ("Abiskojåkka", "VATTDRTX", "SV", 650040, 7580020)])
        one = ortnamn.paired(names)
        assert len(one) == 1
        assert one["name"].iloc[0] == "Abiskojåkka"
        assert one["also"].iloc[0] == "Ábeskoeatnu"
        assert one["languages"].iloc[0] == "Swedish, North Sámi"
        assert ortnamn.label(one["name"].iloc[0], one["also"].iloc[0]) == "Abiskojåkka (Ábeskoeatnu)"
        # The Swedish point is the one kept, so the label stands where that name did.
        assert one.geometry.iloc[0].equals(names.geometry.iloc[1])

    def test_the_same_language_is_never_joined(self):
        """Two lakes 300 m apart, both named in Sámi only, are two lakes."""
        names = _placed([("Bajip Jávri", "VATTTX", "NS", 650000, 7580000), ("Vuolip Jávri", "VATTTX", "NS", 650300, 7580000)])
        assert list(ortnamn.paired(names)["name"]) == ["Bajip Jávri", "Vuolip Jávri"]

    def test_neither_are_two_types_nor_two_places_out_of_reach(self):
        names = _placed(
            [
                ("Abisko", "BEBTX", "SV", 650000, 7580000),
                ("Ábeskojávri", "VATTTX", "NS", 650100, 7580000),
                ("Gorsajökeln", "GLACIÄRTX", "SV", 660000, 7580000),
                ("Gorsajiekŋa", "GLACIÄRTX", "NS", 660619, 7580000),
            ]
        )
        joined = ortnamn.paired(names)
        assert list(joined["name"]) == ["Abisko", "Gorsajökeln", "Ábeskojávri", "Gorsajiekŋa"]
        assert list(joined["also"]) == ["", "", "", ""]

    def test_a_name_spelt_the_same_in_both_languages_is_one_name(self):
        names = _placed([("Eahpárusluoppal", "VATTTX", "SV", 650000, 7580000), ("Eahpárusluoppal", "VATTTX", "NS", 650090, 7580000)])
        one = ortnamn.paired(names)
        assert len(one) == 1
        assert one["also"].iloc[0] == ""
        assert one["languages"].iloc[0] == "Swedish, North Sámi"
        assert ortnamn.label(one["name"].iloc[0], one["also"].iloc[0]) == "Eahpárusluoppal"

    def test_a_third_language_joins_the_brackets(self):
        names = _placed(
            [("Kiruna", "BEBTX", "SV", 650000, 7580000), ("Giron", "BEBTX", "NS", 650100, 7580000), ("Kieruna", "BEBTX", "TF", 650200, 7580000)]
        )
        one = ortnamn.paired(names)
        assert len(one) == 1
        assert ortnamn.label(one["name"].iloc[0], one["also"].iloc[0]) == "Kiruna (Giron, Kieruna)"

    def test_nothing_in_is_nothing_out_with_the_columns(self):
        empty = ortnamn.paired(_placed([]).iloc[0:0])
        assert list(empty.columns[-2:]) == ["also", "languages"]
        assert len(empty) == 0
