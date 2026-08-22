"""Tests for the UT.no route source."""

import json
from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
import pytest
from shapely.geometry import LineString, MultiLineString
from trails.io.sources import ut

CATALOGUE = """
name = "Lomsdal-Visten"

[[route]]
id = 1113860
name = "Sjøbergmarsjruta"
category = "core"
ut_url = "https://ut.no/turforslag/1113860"
guide_url_no = "https://lomsdalvisten.no/turbeskrivelser/sjobergmarsjruta/"
guide_url_en = "https://lomsdalvisten.no/en/hiking-descriptions/route-to-the-sjoberg-march/"

[[route]]
id = 116015
name = "Dagstur i Godvassdalen"
category = "access"
ut_url = "https://ut.no/turforslag/116015"
ut_summary = "7,2 km, 5 h, +473 m"
"""

GPX = """<?xml version="1.0" encoding="UTF-8"?>
<gpx creator="fabulator:gpx-builder" version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata><name>Sjøbergmarsjruta</name></metadata>
  <trk>
    <trkseg>
      <trkpt lat="65.645674" lon="13.143400"><ele>164</ele><time>2026-08-12T21:44:04.389Z</time></trkpt>
      <trkpt lat="65.645677" lon="13.143314"><ele>165</ele></trkpt>
      <trkpt lat="65.650000" lon="13.150000"><ele>200</ele></trkpt>
    </trkseg>
  </trk>
</gpx>
"""


@pytest.fixture
def catalogue_path(tmp_path) -> Path:
    """A two-entry catalogue on disk."""
    path = tmp_path / "routes.toml"
    path.write_text(CATALOGUE, encoding="utf-8")
    return path


@pytest.fixture
def gpx_path(tmp_path) -> Path:
    """A single-segment GPX file on disk."""
    path = tmp_path / "trip.gpx"
    path.write_text(GPX, encoding="utf-8")
    return path


class TestLoadCatalogue:
    """Tests for reading the TOML catalogue."""

    def test_reads_every_route_in_order(self, catalogue_path):
        routes = ut.load_catalogue(catalogue_path)

        assert [route.trip_id for route in routes] == [1113860, 116015]
        assert routes[0].name == "Sjøbergmarsjruta"
        assert routes[0].category == "core"

    def test_optional_fields_default_to_none(self, catalogue_path):
        routes = ut.load_catalogue(catalogue_path)

        assert routes[0].ut_summary is None
        assert routes[1].guide_url_no is None
        assert routes[1].ut_summary == "7,2 km, 5 h, +473 m"

    def test_gpx_url_is_derived_from_the_id(self, catalogue_path):
        routes = ut.load_catalogue(catalogue_path)

        assert routes[0].gpx_url == "https://ut.no/api/gpx/trip/1113860"

    def test_rejects_unknown_category(self, tmp_path):
        path = tmp_path / "bad.toml"
        path.write_text('[[route]]\nid = 1\nname = "X"\ncategory = "ski"\nut_url = "https://ut.no/1"\n', encoding="utf-8")

        with pytest.raises(ValueError, match="category must be one of"):
            ut.load_catalogue(path)

    def test_rejects_duplicate_id(self, tmp_path):
        entry = '[[route]]\nid = 1\nname = "X"\ncategory = "core"\nut_url = "https://ut.no/1"\n'
        path = tmp_path / "dup.toml"
        path.write_text(entry * 2, encoding="utf-8")

        with pytest.raises(ValueError, match="appears twice"):
            ut.load_catalogue(path)

    def test_rejects_missing_name(self, tmp_path):
        path = tmp_path / "bad.toml"
        path.write_text('[[route]]\nid = 1\ncategory = "core"\nut_url = "https://ut.no/1"\n', encoding="utf-8")

        with pytest.raises(ValueError, match="name is required"):
            ut.load_catalogue(path)

    def test_rejects_non_http_url(self, tmp_path):
        """A catalogue must not be able to put a script link into a map popup."""
        path = tmp_path / "bad.toml"
        path.write_text('[[route]]\nid = 1\nname = "X"\ncategory = "core"\nut_url = "javascript:alert(1)"\n', encoding="utf-8")

        with pytest.raises(ValueError, match="must be an http"):
            ut.load_catalogue(path)

    def test_empty_catalogue_yields_no_routes(self, tmp_path):
        path = tmp_path / "empty.toml"
        path.write_text('name = "Nowhere"\n', encoding="utf-8")

        assert ut.load_catalogue(path) == []


class TestParseGpx:
    """Tests for GPX track parsing."""

    def test_single_segment_becomes_a_linestring(self, gpx_path):
        geometry = ut.parse_gpx(gpx_path)

        assert isinstance(geometry, LineString)
        assert len(geometry.coords) == 3

    def test_coordinates_are_lon_lat_and_two_dimensional(self, gpx_path):
        """Elevation must not reach the geometry; consumers unpack (lon, lat)."""
        first = list(ut.parse_gpx(gpx_path).coords)[0]

        assert first == (13.1434, 65.645674)

    def test_several_segments_become_a_multilinestring(self, tmp_path):
        path = tmp_path / "multi.gpx"
        path.write_text(
            '<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk>'
            '<trkseg><trkpt lat="65.1" lon="13.1"/><trkpt lat="65.2" lon="13.2"/></trkseg>'
            '<trkseg><trkpt lat="65.3" lon="13.3"/><trkpt lat="65.4" lon="13.4"/></trkseg>'
            "</trk></gpx>",
            encoding="utf-8",
        )

        geometry = ut.parse_gpx(path)

        assert isinstance(geometry, MultiLineString)
        assert len(geometry.geoms) == 2

    def test_single_point_segment_is_not_a_line(self, tmp_path):
        path = tmp_path / "point.gpx"
        path.write_text(
            '<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg><trkpt lat="65.1" lon="13.1"/></trkseg></trk></gpx>', encoding="utf-8"
        )

        with pytest.raises(ValueError, match="no track segment"):
            ut.parse_gpx(path)

    def test_track_without_namespace_is_still_read(self, tmp_path):
        """GPX 1.0 uses a different namespace, so matching is wildcarded."""
        path = tmp_path / "bare.gpx"
        path.write_text('<gpx><trk><trkseg><trkpt lat="65.1" lon="13.1"/><trkpt lat="65.2" lon="13.2"/></trkseg></trk></gpx>', encoding="utf-8")

        assert isinstance(ut.parse_gpx(path), LineString)

    def test_empty_file_raises(self, tmp_path):
        path = tmp_path / "empty.gpx"
        path.write_text('<gpx xmlns="http://www.topografix.com/GPX/1/1"></gpx>', encoding="utf-8")

        with pytest.raises(ValueError, match="no track segment"):
            ut.parse_gpx(path)


class TestLoadRoutes:
    """Tests for assembling the GeoDataFrame."""

    def test_returns_one_row_per_route_with_catalogue_fields(self, tmp_path, catalogue_path, gpx_path):
        source = ut.Source(cache_dir=str(tmp_path))
        routes = ut.load_catalogue(catalogue_path)

        with patch.object(ut.Source, "fetch_gpx", return_value=gpx_path):
            gdf = source.load_routes(routes)

        assert isinstance(gdf, gpd.GeoDataFrame)
        assert len(gdf) == 2
        assert gdf.crs.to_epsg() == 4326
        assert list(gdf["trip_id"]) == [1113860, 116015]
        assert list(gdf["category"]) == ["core", "access"]
        assert gdf["gpx_url"].iloc[0] == "https://ut.no/api/gpx/trip/1113860"
        assert gdf["points"].iloc[0] == 3

    def test_measures_length_in_kilometres(self, tmp_path, catalogue_path, gpx_path):
        source = ut.Source(cache_dir=str(tmp_path))

        with patch.object(ut.Source, "fetch_gpx", return_value=gpx_path):
            gdf = source.load_routes(ut.load_catalogue(catalogue_path))

        # The fixture track spans roughly half a kilometre.
        assert 0.3 < gdf["length_km"].iloc[0] < 0.9

    def test_it_says_when_the_oldest_trip_it_served_was_downloaded(self, tmp_path, catalogue_path, gpx_path):
        """A catalogue fetched over several days is only as current as the trip
        nobody re-fetched, and an exported file has to say what it was built
        from. UT.no publishes no version of a trip at all."""
        source = ut.Source(cache_dir=str(tmp_path))
        routes = ut.load_catalogue(catalogue_path)
        for route, when in zip(routes, ["2026-08-14T09:00:00", "2026-08-12T07:30:00"], strict=True):
            sidecar = source.downloads.cache_dir / f"trip_{route.trip_id}.gpx.meta.json"
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            sidecar.write_text(json.dumps({"url": route.gpx_url, "downloaded_at": when}))

        with patch.object(ut.Source, "fetch_gpx", return_value=gpx_path):
            source.load_routes(routes)

        assert source.loaded_at == "2026-08-12T07:30:00"

    def test_a_trip_with_no_sidecar_leaves_the_date_to_the_others(self, tmp_path, catalogue_path, gpx_path):
        source = ut.Source(cache_dir=str(tmp_path))
        assert source.loaded_at is None

        with patch.object(ut.Source, "fetch_gpx", return_value=gpx_path):
            source.load_routes(ut.load_catalogue(catalogue_path))

        # Nothing was really downloaded here, so nothing is claimed.
        assert source.loaded_at is None

    def test_empty_input_yields_an_empty_frame_with_columns(self, tmp_path):
        gdf = ut.Source(cache_dir=str(tmp_path)).load_routes([])

        assert len(gdf) == 0
        assert "length_km" in gdf.columns
        assert "ut_url" in gdf.columns


class TestFetchGpx:
    """Tests for the download step."""

    def test_downloads_to_a_per_trip_filename(self, tmp_path, catalogue_path):
        source = ut.Source(cache_dir=str(tmp_path))
        route = ut.load_catalogue(catalogue_path)[0]

        with patch.object(source.downloads, "download") as mock_download:
            mock_download.return_value.path = tmp_path / "trip_1113860.gpx"
            source.fetch_gpx(route)

        assert mock_download.call_args.args[0] == "https://ut.no/api/gpx/trip/1113860"
        assert mock_download.call_args.kwargs["filename"] == "trip_1113860.gpx"
