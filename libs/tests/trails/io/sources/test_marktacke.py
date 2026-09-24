"""Lantmäteriet's wetlands, found through a stand-in STAC page and read out of a stand-in delivery."""

import zipfile

import geopandas as gpd
import pytest
from shapely.geometry import box
from trails.io.sources import marktacke

ABISKO = (18.15, 68.139, 19.10, 68.46)


def _item(number: str, bbox: list[float]) -> dict:
    return {"id": number, "bbox": bbox, "assets": {"data": {"href": f"https://dl1.test/marktacke_kn{number}.zip", "type": "application/zip"}}}


class TestSearch:
    def test_it_follows_every_page_and_sorts_by_id(self):
        pages = {
            "first": {"features": [_item("2584", [17.8, 67.5, 23.6, 68.9])], "links": [{"rel": "next", "href": "second"}]},
            "second": {"features": [_item("2523", [16.6, 66.4, 22.6, 68.0])], "links": []},
        }
        asked = []

        def fetch(url):
            asked.append(url)
            return pages["first" if "items?" in url else url]

        found = marktacke.search(ABISKO, fetch)
        assert [m.id for m in found] == ["2523", "2584"]
        assert found[1].href.endswith("kn2584.zip") and found[1].bounds == (17.8, 67.5, 23.6, 68.9)
        assert asked[0].startswith(f"{marktacke.STAC_URL}/collections/marktacke/items?bbox=18.150000,68.139000,19.100000,68.460000")


def _delivery(target, wetlands: gpd.GeoDataFrame) -> None:
    """Write a zip holding one GeoPackage with the wetland layer, the way the product is delivered."""
    packed = target.with_suffix(".gpkg")
    wetlands.to_file(packed, layer=marktacke.WETLAND_LAYER, driver="GPKG")
    with zipfile.ZipFile(target, "w") as bundle:
        bundle.write(packed, arcname="marktacke_kn2584.gpkg")
    packed.unlink()


@pytest.fixture
def delivery():
    """Two wetlands in SWEREF 99 TM near Abisko, one firm and one wet, and a third far outside the box."""
    firm = box(650_000, 7_580_000, 650_500, 7_580_400)
    wet = box(651_000, 7_581_000, 651_100, 7_581_100)
    away = box(700_000, 7_500_000, 700_100, 7_500_100)
    return gpd.GeoDataFrame(
        {"objekttypnr": [2651, 2652, 2651], "objekttyp": [marktacke.FIRM_TYPE, marktacke.WET_TYPE, marktacke.FIRM_TYPE]},
        geometry=[firm, wet, away],
        crs=marktacke.CRS,
    )


class TestSource:
    def test_water_keeps_whole_pieces_and_levels_from_every_cached_delivery(self, tmp_path, delivery):
        root = tmp_path / "marktacke"
        root.mkdir()
        frame = delivery.copy()
        frame["objekttyp"] = ["Sjö", "Skog", "Sjö"]
        frame["hojd_over_havet"] = [207, None, 300]
        frame.to_file(root / "marktacke_kn2584.gpkg", layer="mark")
        river = frame.iloc[:1].copy()
        river["objekttyp"] = "Vattendragsyta"
        river.to_file(root / "marktacke_kn2523.gpkg", layer="mark")

        def forbidden(*args):
            pytest.fail("reading cached water must not search or download")

        source = marktacke.Source(cache_dir=tmp_path, fetch=forbidden, download=forbidden)
        found = source.water(ABISKO, ("2584", "2523"))
        assert found["objekttyp"].tolist() == ["Sjö", "Vattendragsyta"]
        assert found["hojd_over_havet"].tolist() == [207, 207]
        assert all(geometry.equals(frame.geometry.iloc[0]) for geometry in found.geometry)
        with pytest.raises(FileNotFoundError, match="2585"):
            source.water(ABISKO, ("2584", "2585"))
        with pytest.raises(ValueError, match="municipalities"):
            source.water(ABISKO, ())

    def test_the_wetlands_are_read_out_of_the_delivery_and_cut_to_the_box(self, tmp_path, delivery):
        fetched = []

        def download(url, target, username, password):
            fetched.append((url, username, password))
            _delivery(target, delivery)

        def fetch(url):
            return {"features": [_item("2584", [17.8, 67.5, 23.6, 68.9])], "links": []}

        source = marktacke.Source(cache_dir=tmp_path, username="me", password="secret", fetch=fetch, download=download)
        found = source.wetlands(ABISKO)
        assert fetched == [("https://dl1.test/marktacke_kn2584.zip", "me", "secret")]
        assert len(found) == 2 and found.crs.to_string() == marktacke.CRS
        assert sorted(found["objekttyp"]) == [marktacke.FIRM_TYPE, marktacke.WET_TYPE]
        assert found["wet"].tolist() == [False, True] or found["wet"].tolist() == [True, False]
        assert set(found["kommun"]) == {"2584"}
        assert (tmp_path / "marktacke" / "marktacke_kn2584.gpkg").exists()
        assert not (tmp_path / "marktacke" / "marktacke_kn2584.zip").exists()
        # A second read is the cached file and no download.
        source.wetlands(ABISKO)
        assert len(fetched) == 1

    def test_a_cold_cache_without_the_login_is_a_named_failure(self, tmp_path):
        def fetch(url):
            return {"features": [_item("2584", [17.8, 67.5, 23.6, 68.9])], "links": []}

        source = marktacke.Source(cache_dir=tmp_path, username="", password="", fetch=fetch)
        with pytest.raises(RuntimeError, match="Geotorget login"):
            source.wetlands(ABISKO)

    def test_a_box_no_municipality_covers_is_a_named_failure(self, tmp_path):
        source = marktacke.Source(cache_dir=tmp_path, username="me", password="secret", fetch=lambda url: {"features": [], "links": []})
        with pytest.raises(RuntimeError, match="no municipality"):
            source.wetlands(ABISKO)
