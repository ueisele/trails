"""Topografi 50: the delivery on disk, the API behind it, and reading a box."""

import json
import zipfile

import geopandas as gpd
import pytest
from shapely.geometry import LineString
from trails.io.sources import topografi50 as t50

ABISKO = (18.15, 68.17, 19.00, 68.46)
ORDER = "37ec0b88-0000-0000-0000-000000000000"


def _paths() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"objektidentitet": ["a", "b"], "objekttyp": ["Gångstig", "Vandringsled"]},
        geometry=[LineString([(650000, 7580000), (651000, 7580000)]), LineString([(900000, 7580000), (901000, 7580000)])],
        crs=t50.CRS,
    )


def _delivery_on_disk(root, day="2026-09-08", unpacked=True):
    """Lay a delivery out as the loader keeps one: zips beside a manifest, GeoPackages unpacked."""
    directory = root / "topografi50" / day
    (directory / t50.UNPACKED).mkdir(parents=True)
    gpkg = directory / t50.UNPACKED / t50.geopackage_name(t50.KOMMUNIKATION)
    _paths().to_file(gpkg, layer=t50.LAYER_PATHS, driver="GPKG")
    with zipfile.ZipFile(directory / t50.zip_name(t50.KOMMUNIKATION), "w") as out:
        out.write(gpkg, gpkg.name)
    if not unpacked:
        gpkg.unlink()
    manifest = {
        "id": "d1",
        "status": t50.READY,
        "files": [
            {"title": t50.zip_name(t50.KOMMUNIKATION), "path": "/leverans/latest/files/root/x.zip", "length": 1, "updated": f"{day}T17:29:14+02:00"}
        ],
    }
    (directory / t50.DELIVERY_FILE).write_text(json.dumps(manifest))
    return directory


class TestDeliveryFrom:
    def test_the_two_answers_become_one_delivery(self):
        latest = {"objektidentitet": "fc2b", "status": "LYCKAD", "typ": "BAS"}
        listed = [
            {
                "path": "/leverans/latest/files/root/mark_sverige.zip?q=abc",
                "title": "mark_sverige.zip",
                "type": "application/octet-stream",
                "length": 10,
                "updated": "2026-09-08T17:29:14.488+02:00",
            },
            {"path": "/leverans/latest/files/root?q=def", "title": "metadata", "type": "application/json"},
        ]
        delivery = t50.delivery_from(latest, listed)
        assert delivery.day == "2026-09-08"
        assert [file.title for file in delivery.files] == ["mark_sverige.zip"]
        assert delivery.file("mark_sverige.zip").path.endswith("?q=abc")
        with pytest.raises(KeyError):
            delivery.file("hojd_sverige.zip")


class TestOnDisk:
    def test_the_newest_delivery_is_read_and_names_the_version(self, tmp_path):
        _delivery_on_disk(tmp_path, "2026-09-01")
        _delivery_on_disk(tmp_path, "2026-09-08")
        source = t50.Source(cache_dir=tmp_path, order="", username="", password="")
        read = source.read(t50.KOMMUNIKATION, t50.LAYER_PATHS, ABISKO)
        assert read["objektidentitet"].tolist() == ["a"]
        assert read.crs.to_epsg() == 3006
        assert source.version == "2026-09-08"

    def test_an_archive_not_yet_unpacked_is_unpacked(self, tmp_path):
        _delivery_on_disk(tmp_path, unpacked=False)
        source = t50.Source(cache_dir=tmp_path, order="", username="", password="")
        assert source.geopackage(t50.KOMMUNIKATION).exists()

    def test_without_a_delivery_or_a_login_it_says_what_is_missing(self, tmp_path):
        source = t50.Source(cache_dir=tmp_path, order="", username="", password="")
        with pytest.raises(RuntimeError, match=t50.ORDER_VAR):
            source.read(t50.KOMMUNIKATION, t50.LAYER_PATHS, ABISKO)


class TestApi:
    def test_a_missing_theme_is_fetched_from_the_delivery_and_checked(self, tmp_path):
        directory = _delivery_on_disk(tmp_path)
        archive = directory / t50.zip_name(t50.KOMMUNIKATION)
        (directory / t50.UNPACKED / t50.geopackage_name(t50.KOMMUNIKATION)).unlink()
        held = archive.read_bytes()
        archive.unlink()
        answers = {
            "/leverans/latest": {"objektidentitet": "d1", "status": "LYCKAD"},
            "/leverans/latest/files": [
                {
                    "path": "/leverans/latest/files/root/kommunikation_sverige.zip?q=tok",
                    "title": "kommunikation_sverige.zip",
                    "type": "application/octet-stream",
                    "length": len(held),
                    "updated": "2026-09-08T17:29:14+02:00",
                }
            ],
        }
        asked = []

        def fetch(url, auth):
            asked.append((url, auth))
            return answers[url.removeprefix(f"{t50.API_URL}/{ORDER}")]

        def download(url, auth, target):
            asked.append((url, auth))
            target.write_bytes(held)

        source = t50.Source(cache_dir=tmp_path, order=ORDER, username="u", password="p", fetch=fetch, download=download)
        read = source.read(t50.KOMMUNIKATION, t50.LAYER_PATHS, ABISKO)
        assert read["objektidentitet"].tolist() == ["a"]
        assert asked[-1][0] == f"{t50.API_URL}/{ORDER}/leverans/latest/files/root/kommunikation_sverige.zip?q=tok"
        assert all(auth.startswith("Basic ") for _, auth in asked)

    def test_a_delivery_still_being_made_is_refused(self, tmp_path):
        source = t50.Source(
            cache_dir=tmp_path,
            order=ORDER,
            username="u",
            password="p",
            fetch=lambda url, auth: {"objektidentitet": "d1", "status": "PÅGÅENDE"} if url.endswith("latest") else [],
        )
        with pytest.raises(RuntimeError, match="PÅGÅENDE"):
            source.delivery()

    def test_the_manifest_written_carries_no_signed_path(self, tmp_path):
        answers = {
            "latest": {"objektidentitet": "d1", "status": "LYCKAD"},
            "files": [
                {
                    "path": "/leverans/latest/files/root/mark_sverige.zip?q=secret",
                    "title": "mark_sverige.zip",
                    "type": "application/octet-stream",
                    "length": 1,
                    "updated": "2026-09-08T17:29:14+02:00",
                }
            ],
        }
        source = t50.Source(cache_dir=tmp_path, order=ORDER, username="u", password="p", fetch=lambda url, auth: answers[url.rsplit("/", 1)[-1]])
        directory = source.delivery()
        assert directory.name == "2026-09-08"
        assert "secret" not in (directory / t50.DELIVERY_FILE).read_text()
