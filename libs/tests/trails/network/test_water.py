"""Water geometry, dam gaps and the walking choices at a portage."""

import geopandas as gpd
import pytest
import shapely
from shapely.geometry import LineString, Point, Polygon, box
from trails.network import water
from trails.routing.graph import build_network
from trails.routing.sources import BRIDGE, PADDLE, NetworkSource

CRS = "EPSG:3006"


def test_chords_stay_in_water_and_do_not_duplicate_the_shore():
    polygon = Polygon(
        [(0, 0), (1000, 0), (1000, 1000), (600, 1000), (600, 300), (400, 300), (400, 1000), (0, 1000)],
        holes=[[(100, 100), (200, 100), (200, 200), (100, 200)]],
    )
    shore, opened = water.sources(gpd.GeoDataFrame(geometry=[polygon], crs=CRS), metric_crs=CRS)
    assert shore.kind == opened.kind == PADDLE
    assert len(shore.gdf) == 2
    assert opened.cost_factor == water.OPEN_WATER_FACTOR
    assert len(opened.gdf) > 0
    assert opened.gdf.covered_by(polygon).all()
    assert not opened.gdf.covered_by(polygon.boundary).any()
    assert shore.gdf.length.sum() == pytest.approx(polygon.boundary.length)


def test_dam_intervals_merge_and_cuts_keep_digitised_flow():
    streams = gpd.GeoDataFrame({"storleksklass": ["2", "1"]}, geometry=[LineString([(100, 0), (0, 0)]), LineString([(100, 100), (0, 100)])], crs=CRS)
    dams = gpd.GeoDataFrame(geometry=[Point(50, 0), Point(60, 25), Point(90, 26)], crs=CRS)
    cut = water.cut_streams(streams, dams, metric_crs=CRS)
    assert [tuple(line.coords) for line in cut.geometry] == [((100, 0), (85, 0)), ((25, 0), (0, 0))]
    assert cut.length.sum() == pytest.approx(40)
    empty = water.cut_streams(streams.iloc[:0], dams, metric_crs=CRS)
    assert empty.empty and empty.crs == streams.crs


def test_portages_join_components_once_and_tie_their_feet_to_path_nodes():
    surfaces = gpd.GeoDataFrame(geometry=[box(0, 0, 100, 100), box(200, 0, 300, 100)], crs=CRS)
    paddle = water.sources(surfaces, metric_crs=CRS)
    walking = build_network(
        [NetworkSource("path", gpd.GeoDataFrame(geometry=[LineString([(100, -50), (200, -50)])], crs=CRS))], metric_crs=CRS, bridge_m=0
    )
    chords, ties = water.portages(paddle, walking)
    assert len(chords.gdf) == 1
    assert chords.gdf.length.iloc[0] == pytest.approx(100)
    assert len(ties.gdf) == 2
    assert ties.gdf.length.max() <= water.PATH_JOIN_M
    assert chords.kind == ties.kind == BRIDGE
    joined = build_network([*paddle, chords, ties], metric_crs=CRS, bridge_m=0)
    carried = joined.edges[joined.edges["kind"] == BRIDGE]
    assert carried["chain_id"].isna().all()
    assert not carried["one_way"].any()
    assert not (joined.chains["kind"] == BRIDGE).any()


def test_no_chord_reaches_beyond_the_portage_distance():
    surfaces = gpd.GeoDataFrame(geometry=[box(0, 0, 100, 100), box(1200, 0, 1300, 100)], crs=CRS)
    paddle = water.sources(surfaces, metric_crs=CRS)
    walking = build_network([NetworkSource("path", gpd.GeoDataFrame(geometry=[], crs=CRS))], metric_crs=CRS)
    assert all(source.gdf.empty for source in water.portages(paddle, walking))


def test_a_dam_gap_is_a_portage_and_streams_declare_their_direction():
    streams = gpd.GeoDataFrame({"storleksklass": ["2"]}, geometry=[LineString([(100, 0), (0, 0)])], crs=CRS)
    dams = gpd.GeoDataFrame(geometry=[Point(50, 0)], crs=CRS)
    paddle = water.sources(gpd.GeoDataFrame(geometry=[], crs=CRS), metric_crs=CRS, streams=streams, dams=dams)
    assert paddle[-1].directed
    walking = build_network([NetworkSource("path", gpd.GeoDataFrame(geometry=[], crs=CRS))], metric_crs=CRS)
    chord, ties = water.portages(paddle, walking)
    assert len(chord.gdf) == 1 and chord.gdf.length.iloc[0] == pytest.approx(50)
    assert ties.gdf.empty
    assert shapely.union_all(paddle[-1].gdf.geometry).length == pytest.approx(50)


def test_the_combined_build_reports_water_and_leaves_the_input_cache_alone(tmp_path, capsys):
    from trails.network import graphs

    surfaces = gpd.GeoDataFrame(geometry=[box(0, 0, 100, 100), box(200, 0, 300, 100)], crs=CRS)
    items = [NetworkSource("path", gpd.GeoDataFrame(geometry=[LineString([(100, -50), (200, -50)])], crs=CRS))]
    items.extend(water.sources(surfaces, metric_crs=CRS))
    empty = gpd.GeoSeries([], crs=CRS)
    masks = graphs.Masks(empty, empty, empty)
    protected = gpd.GeoDataFrame({"id": [], "name": [], "form": []}, geometry=[], crs=CRS)
    rules = graphs.Rules(metric_crs=CRS, layout="test", protected_id="id", protected_name="name", protected_form="form", form_label=str)
    network, counts = water.build(
        items,
        masks,
        gpd.GeoDataFrame(geometry=[box(-100, -100, 400, 200)], crs=CRS),
        graphs.Params(cache_dir=str(tmp_path / "inputs")),
        rules,
        protected=protected,
        measure=lambda network: network,
    )
    assert not (tmp_path / "inputs").exists()
    assert not network.edges["one_way"].any()
    assert {water.SHORE, water.OPEN_WATER, water.PORTAGES} <= set(counts["source"])
    assert "Portages:" in capsys.readouterr().out
