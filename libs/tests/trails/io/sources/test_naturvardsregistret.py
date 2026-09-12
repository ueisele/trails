"""The two Naturvårdsverket registers, read out of local stand-ins for their files."""

import zipfile

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Polygon
from trails.io.cache import DownloadResult
from trails.io.sources import naturvardsregistret as nvr

#: A box in WGS 84 around SWEREF 99 TM (650000, 7580000): Abisko.
ABISKO = (18.15, 68.17, 19.00, 68.46)


def _zipped_shapefile(tmp_path, name: str, folder: str, layer: str, frame: gpd.GeoDataFrame):
    """Write a frame as a shapefile inside a zip, laid out as the server lays it."""
    work = tmp_path / "work" / name
    work.mkdir(parents=True)
    frame.to_file(work / layer)
    archive = tmp_path / f"{name}.zip"
    with zipfile.ZipFile(archive, "w") as out:
        for part in work.iterdir():
            out.write(part, f"{folder}/{part.name}" if folder else part.name)
    return archive


def _area(identity: str, name: str, form: str, east: float) -> dict:
    square = Polygon([(east, 7580000), (east + 2000, 7580000), (east + 2000, 7582000), (east, 7582000)])
    return {
        "NVRID": identity,
        "NAMN": name,
        "SKYDDSTYP": form,
        "IUCNKAT": "II",
        "FORVALTARE": "Länsstyrelsen",
        "URSBESLDAT": "1909-05-24",
        "AREA_HA": 400.0,
        "LAN": "Norrbottens Län",
        "KOMMUN": "Kiruna",
        "geometry": square,
    }


@pytest.fixture
def source(tmp_path):
    """A source whose downloads are the local archives."""
    parks = gpd.GeoDataFrame(
        [_area("2001225", "Abisko", "Nationalpark", 650000), _area("2001230", "Vadvetjåkka", "Nationalpark", 900000)], crs=nvr.CRS
    )
    reserves = gpd.GeoDataFrame([_area("2001247", "Abisko naturvet. station", "Naturreservat", 652000)], crs=nvr.CRS)
    trails = gpd.GeoDataFrame(
        {
            "L_ID": ["1", "2"],
            "LNAMN": ["Del av Kungsleden", None],
            "LKATEGORI": [nvr.SUMMER, nvr.WINTER],
            "LTYP": ["Vandringsled", "Vinterled"],
            "STATLED": ["Abisko - Abiskojaure (BD 21)", "Abisko - Abiskojaure (BD 21)"],
            "STATLED_ID": ["BD 21", "BD 21"],
            "geometry": [LineString([(650000, 7580000), (651000, 7580000)]), LineString([(650000, 7581000), (651000, 7581000)])],
        },
        crs=nvr.CRS,
    )
    archives = {
        "NP.zip": _zipped_shapefile(tmp_path, "NP", "NP", "NP_polygon.shp", parks),
        "NR.zip": _zipped_shapefile(tmp_path, "NR", "NR", "NR_polygon.shp", reserves),
        "Leder_shp.zip": _zipped_shapefile(tmp_path, "Leder_shp", "", "Leder.shp", trails),
    }
    made = nvr.Source(cache_dir=tmp_path / "cache")
    made.downloads.download = lambda url, filename=None, version=None, force=False: DownloadResult(archives[filename], False, None)  # type: ignore[method-assign]
    return made


class TestAreas:
    def test_every_form_asked_for_is_read_and_ordered_by_id(self, source):
        areas = source.areas(ABISKO, forms=("NR", "NP"))
        assert areas[nvr.AREA_ID].tolist() == ["2001225", "2001247"]
        assert areas[nvr.AREA_FORM].tolist() == ["Nationalpark", "Naturreservat"]
        assert areas.crs.to_epsg() == 4326

    def test_an_area_outside_the_box_is_not_read(self, source):
        areas = source.areas(ABISKO, forms=("NP",))
        assert areas[nvr.AREA_NAME].tolist() == ["Abisko"]

    def test_the_file_s_date_is_its_version(self, source):
        source.areas(ABISKO, forms=("NP",))
        assert source.versions["naturvardsregistret/NP.zip"] is not None


class TestFindOne:
    def test_a_park_is_found_by_part_of_its_name(self, source):
        found = source.find_one("abisk")
        assert found[nvr.AREA_ID].tolist() == ["2001225"]
        assert found.crs.to_epsg() == 4326

    def test_nothing_matching_says_so(self, source):
        with pytest.raises(LookupError, match="no national park matches"):
            source.find_one("Sarek")

    def test_more_than_one_matching_says_which(self, source):
        with pytest.raises(LookupError, match="Abisko, Vadvetjåkka"):
            source.find_one("a")


class TestTrails:
    def test_both_seasons_come_back_with_every_column(self, source):
        trails = source.trails(ABISKO)
        assert sorted(trails[nvr.TRAIL_SEASON]) == [nvr.SUMMER, nvr.WINTER]
        assert trails[nvr.TRAIL_ROUTE_ID].tolist() == ["BD 21", "BD 21"]


class TestFormLabel:
    def test_a_known_form_reads_as_a_sign_would(self):
        assert nvr.form_label("Nationalpark") == "national park"

    def test_an_unknown_form_passes_through(self):
        assert nvr.form_label("Nytt skydd") == "Nytt skydd"
