"""Water geometry, dam gaps and the walking choices at a portage."""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely
from shapely.geometry import LineString, Point, Polygon, box
from trails.network import water
from trails.routing.elevation import PROFILE_COLUMNS, with_elevation
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
        measure=lambda network: with_elevation(network, lambda coordinates: coordinates[:, 0]),
    )
    assert not (tmp_path / "inputs").exists()
    assert not network.edges["one_way"].any()
    assert {water.SHORE, water.OPEN_WATER, water.PORTAGES} <= set(counts["source"])
    assert "Portages:" in capsys.readouterr().out


def test_touching_lakes_share_the_lowest_register_without_trusting_ids():
    surfaces = gpd.GeoDataFrame(
        {"class": ["lake", "lake", "lake", "river", "sea"], "level": ["207", "208", "100-102", None, None]},
        geometry=[box(0, 0, 100, 100), box(100, 0, 200, 100), box(400, 0, 500, 100), box(200, 0, 300, 100), box(500, 0, 600, 100)],
        crs=CRS,
    )
    shore, opened = water.sources(surfaces, metric_crs=CRS, class_field="class", lake_classes=("lake",), level_field="level")
    assert shore.gdf[water.LAKE_BODY].iloc[0] == shore.gdf[water.LAKE_BODY].iloc[1]
    assert shore.gdf[water.LAKE_BODY].iloc[2] != shore.gdf[water.LAKE_BODY].iloc[0]
    assert shore.gdf[water.LAKE_BODY].iloc[3:].isna().all()
    assert shore.gdf[water.LAKE_LEVEL].iloc[:3].tolist() == [207, 207, 100]
    assert set(opened.gdf[water.LAKE_BODY].dropna()) == set(shore.gdf[water.LAKE_BODY].dropna())


def test_lake_levels_use_only_their_own_shores_and_leave_other_profiles_alone():
    surfaces = gpd.GeoDataFrame(
        {"class": ["lake", "lake", "river", "sea"], "level": [207, np.nan, np.nan, np.nan]},
        geometry=[box(0, 0, 100, 100), box(200, 0, 300, 100), box(400, 0, 500, 100), box(600, 0, 700, 100)],
        crs=CRS,
    )
    items = water.sources(surfaces, metric_crs=CRS, class_field="class", lake_classes=("lake",), level_field="level")
    for name, kind, y in ((water.STREAMS, PADDLE, -100), (water.PORTAGES, BRIDGE, -200), ("path", "path", -300)):
        items.append(NetworkSource(name, gpd.GeoDataFrame(geometry=[LineString([(0, y), (100, y)])], crs=CRS), kind=kind))
    network = with_elevation(build_network(items, metric_crs=CRS, bridge_m=0), lambda coordinates: coordinates[:, 0] + coordinates[:, 1])
    # Chord readings cannot influence the shore percentile.
    for index in network.edges.index[network.edges["source"] == water.OPEN_WATER]:
        network.edges.at[index, "elevations"] = np.full(len(network.edges.at[index, "elevations"]), -1000.0)
    before = [values.copy() for values in network.edges["elevations"]]
    result, levels = water.level_lakes(network, threshold_m=3)
    bodies = network.edges["chain_id"].map(network.chains.set_index("chain_id")[water.LAKE_BODY])
    assert len(levels) == 2
    for row in levels.itertuples():
        own = bodies == row.body
        shore = np.concatenate(network.edges.loc[own & (network.edges["source"] == water.SHORE), "elevations"].tolist())
        assert row.percentile == np.percentile(shore, 10)
        expected = row.registered if pd.notna(row.registered) else row.percentile
        for values in result.edges.loc[own, "elevations"]:
            assert (values == expected).all()
        assert (result.edges.loc[own, ["ascent", "descent"]] == 0).all().all()
    for index in network.edges.index[bodies.isna()]:
        np.testing.assert_array_equal(result.edges.at[index, "elevations"], network.edges.at[index, "elevations"])
        assert result.edges.loc[index, ["ascent", "descent"]].equals(network.edges.loc[index, ["ascent", "descent"]])
    unchanged = network.chains[water.LAKE_BODY].isna()
    pd.testing.assert_frame_equal(result.chains.loc[unchanged, list(PROFILE_COLUMNS)], network.chains.loc[unchanged, list(PROFILE_COLUMNS)])
    for original, values in zip(before, network.edges["elevations"], strict=True):
        np.testing.assert_array_equal(original, values)


def test_an_unread_lake_needs_a_registered_level():
    surfaces = gpd.GeoDataFrame({"level": [np.nan]}, geometry=[box(0, 0, 100, 100)], crs=CRS)
    items = water.sources(surfaces, metric_crs=CRS, level_field="level")
    network = with_elevation(build_network(items, metric_crs=CRS, bridge_m=0), lambda coordinates: np.full(len(coordinates), np.nan))
    with pytest.raises(ValueError, match="no registered level and no finite shore heights"):
        water.level_lakes(network, threshold_m=3)
    network.chains[water.LAKE_LEVEL] = "207"
    result, levels = water.level_lakes(network, threshold_m=3)
    assert levels["percentile"].isna().all()
    assert all((values == 207).all() for values in result.edges["elevations"])
