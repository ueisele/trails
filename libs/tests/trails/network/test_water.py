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
from trails.routing.sources import PADDLE, PORTAGE, NetworkSource

CRS = "EPSG:3006"


def test_surface_dam_cuts_leave_a_portage_and_never_create_a_bank():
    polygon = box(-300, -10, 300, 10)
    dams = gpd.GeoDataFrame(geometry=[Point(0, 0)], crs=CRS)
    paddle = water.sources(gpd.GeoDataFrame(geometry=[polygon], crs=CRS), metric_crs=CRS, dams=dams)
    for source in paddle:
        assert (source.gdf.distance(dams.geometry.iloc[0]) >= water.DAM_CUT_M - 1e-9).all()
    assert paddle[0].gdf.covered_by(polygon.boundary).all()
    walking = build_network([NetworkSource("path", gpd.GeoDataFrame(geometry=[], crs=CRS))], metric_crs=CRS)
    carries, _ = water.portages(paddle, walking)
    assert len(carries.gdf) == 1
    assert carries.kind == PORTAGE
    assert carries.gdf.geometry.iloc[0].distance(dams.geometry.iloc[0]) < water.DAM_CUT_M


def test_stream_inside_surface_is_attached_without_changing_its_direction():
    surfaces = gpd.GeoDataFrame(geometry=[box(0, 0, 100, 100)], crs=CRS)
    streams = gpd.GeoDataFrame({"storleksklass": ["2"]}, geometry=[LineString([(25, 30), (26, 31)])], crs=CRS)
    paddle = water.sources(surfaces, metric_crs=CRS, streams=streams, dams=gpd.GeoDataFrame(geometry=[], crs=CRS))
    assert paddle[-1].directed
    assert paddle[-1].gdf.geometry.iloc[0].equals_exact(streams.geometry.iloc[0], 0)
    surface = shapely.union_all([*paddle[0].gdf.geometry, *paddle[1].gdf.geometry])
    assert surface.intersects(Point(25, 30)) and surface.intersects(Point(26, 31))
    assert paddle[1].gdf.covered_by(surfaces.geometry.iloc[0]).all()


def test_stream_attachment_survives_reprojection_as_a_junction():
    surfaces = gpd.GeoDataFrame(geometry=[box(500000, 6600000, 500200, 6600200)], crs=CRS).to_crs(4326)
    streams = gpd.GeoDataFrame({"storleksklass": ["2"]}, geometry=[LineString([(500050, 6600060), (500052, 6600062)])], crs=CRS).to_crs(4326)
    paddle = water.sources(surfaces, metric_crs=CRS, streams=streams, dams=gpd.GeoDataFrame(geometry=[], crs=4326))
    graph = build_network(paddle, metric_crs=CRS, bridge_m=0)
    stream_edges = graph.edges[graph.edges["source"].eq(water.STREAMS)]
    surface_edges = graph.edges[graph.edges["source"].isin((water.SHORE, water.OPEN_WATER))]
    stream_nodes = set(stream_edges["from_node"]) | set(stream_edges["to_node"])
    surface_nodes = set(surface_edges["from_node"]) | set(surface_edges["to_node"])
    assert len(stream_nodes & surface_nodes) == 2


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
    vertices = set(map(tuple, shapely.get_coordinates(shore.gdf.geometry)))
    assert set(map(tuple, shapely.get_coordinates(opened.gdf.geometry))) <= vertices


def test_dam_intervals_merge_and_cuts_keep_digitised_flow():
    streams = gpd.GeoDataFrame({"storleksklass": ["2", "1"]}, geometry=[LineString([(100, 0), (0, 0)]), LineString([(100, 100), (0, 100)])], crs=CRS)
    dams = gpd.GeoDataFrame(geometry=[Point(50, 0), Point(60, 25), Point(90, 26)], crs=CRS)
    cut = water.cut_streams(streams, dams, metric_crs=CRS)
    assert [tuple(line.coords) for line in cut.geometry] == [((100, 0), (85, 0)), ((25, 0), (0, 0))]
    assert cut.length.sum() == pytest.approx(40)
    empty = water.cut_streams(streams.iloc[:0], dams, metric_crs=CRS)
    assert empty.empty and empty.crs == streams.crs


def test_a_stream_returning_to_a_dam_cannot_reenter_its_disc():
    streams = gpd.GeoDataFrame({"storleksklass": ["2"]}, geometry=[LineString([(0, 0), (100, 0), (100, 100), (0, 100), (0, 10)])], crs=CRS)
    dams = gpd.GeoDataFrame(geometry=[Point(0, 0)], crs=CRS)
    cut = water.cut_streams(streams, dams, metric_crs=CRS)
    assert len(cut) == 1
    assert cut.geometry.iloc[0].coords[0] == (25, 0)
    assert cut.geometry.iloc[0].coords[-1] == (0, 25)
    assert cut.distance(dams.geometry.iloc[0]).min() == pytest.approx(water.DAM_CUT_M)


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
    assert chords.kind == ties.kind == PORTAGE
    joined = build_network([*paddle, chords, ties], metric_crs=CRS, bridge_m=0)
    carried = joined.edges[joined.edges["kind"] == PORTAGE]
    assert carried["chain_id"].isna().all()
    assert not carried["one_way"].any()
    assert not (joined.chains["kind"] == PORTAGE).any()


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
    lakes = shore.gdf[shore.gdf[water.SURFACE_CLASS] == "lake"]
    assert lakes[water.LAKE_BODY].nunique() == 2
    assert lakes[water.LAKE_LEVEL].tolist() == [207, 100]
    assert shore.gdf.loc[shore.gdf[water.SURFACE_CLASS] != "lake", water.LAKE_BODY].isna().all()
    for x in (100, 200, 500):
        seam = LineString([(x, 0), (x, 100)])
        assert shore.gdf.intersection(seam).length.sum() == 0
    assert set(opened.gdf[water.LAKE_BODY].dropna()) == set(shore.gdf[water.LAKE_BODY].dropna())


def test_the_pond_cutoff_applies_after_delivery_pieces_are_joined():
    surfaces = gpd.GeoDataFrame(geometry=[box(0, 0, 60, 100), box(60, 0, 120, 100), box(300, 0, 360, 100)], crs=CRS)
    shore, opened = water.sources(surfaces, metric_crs=CRS)
    assert len(shore.gdf) == 1
    assert shore.gdf.geometry.iloc[0].equals(box(0, 0, 120, 100).boundary)
    assert opened.gdf.covered_by(box(0, 0, 120, 100)).all()


def test_a_shared_mouth_is_emitted_once_with_the_lake_plane():
    surfaces = gpd.GeoDataFrame(
        {"class": ["lake", "river"], "level": [207, None]},
        geometry=[box(0, 0, 100, 100), box(100, 0, 200, 100)],
        crs=CRS,
    )
    shore, opened = water.sources(surfaces, metric_crs=CRS, class_field="class", lake_classes=("lake",), level_field="level")
    mouth = LineString([(100, 0), (100, 100)])
    crossing = opened.gdf[opened.gdf.intersection(mouth).length > 0]
    assert shore.gdf.intersection(mouth).length.sum() == 0
    assert crossing.intersection(mouth).length.sum() == pytest.approx(mouth.length)
    assert crossing[water.LAKE_BODY].notna().all()
    assert crossing[water.LAKE_LEVEL].eq(207).all()
    network = with_elevation(build_network([shore, opened], metric_crs=CRS, bridge_m=0), lambda coordinates: coordinates[:, 0])
    levelled, _ = water.level_lakes(network, threshold_m=3)
    on_mouth = levelled.edges.geometry.covered_by(mouth)
    assert on_mouth.any()
    assert all(np.all(values == 207) for values in levelled.edges.loc[on_mouth, "elevations"])
    river = levelled.chains.loc[levelled.chains[water.SURFACE_CLASS] == "river", "chain_id"]
    assert any(np.ptp(values) > 0 for values in levelled.edges.loc[levelled.edges.chain_id.isin(river), "elevations"])


def test_a_crop_boundary_is_open_water_instead_of_cheap_shore():
    surface = gpd.GeoDataFrame(geometry=[box(0, 0, 200, 100)], crs=CRS)
    extent = gpd.GeoDataFrame(geometry=[box(0, 0, 100, 100)], crs=CRS)
    shore, opened = water.sources(surface, metric_crs=CRS, extent=extent)
    seam = LineString([(100, 0), (100, 100)])
    assert shore.gdf.intersection(seam).length.sum() == 0
    assert opened.gdf.intersection(seam).length.sum() == seam.length


def test_lake_levels_use_only_their_own_shores_and_leave_other_profiles_alone():
    surfaces = gpd.GeoDataFrame(
        {"class": ["lake", "lake", "river", "sea"], "level": [207, np.nan, np.nan, np.nan]},
        geometry=[box(0, 0, 100, 100), box(200, 0, 300, 100), box(400, 0, 500, 100), box(600, 0, 700, 100)],
        crs=CRS,
    )
    items = water.sources(surfaces, metric_crs=CRS, class_field="class", lake_classes=("lake",), level_field="level")
    for name, kind, y in ((water.STREAMS, PADDLE, -100), (water.PORTAGES, PORTAGE, -200), ("path", "path", -300)):
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


def test_stream_direction_uses_the_whole_chain_and_robust_fall(capsys):
    lines = [LineString([(length, y), (0, y)]) for length, y in ((100, 0), (100, 100), (100, 200), (1000, 300), (1000, 400))]
    streams = NetworkSource(water.STREAMS, gpd.GeoDataFrame(geometry=lines, crs=CRS), kind=PADDLE, directed=True, keep_whole=True)
    path = NetworkSource("path", gpd.GeoDataFrame(geometry=[LineString([(10, -10), (10, 410)])], crs=CRS))

    def heights(coordinates):
        x, y = coordinates.T
        slope = np.select([y == 0, y == 100, y == 200, y == 300, y == 400], [0.02, 0.002, -0.02, 0.0008, 0.002])
        bump = (y == 100) & (((x > 40) & (x < 60)) | (x == 100))
        return x * slope + np.where(bump, 20, 0)

    network = with_elevation(build_network([streams, path], metric_crs=CRS, bridge_m=0), heights)
    result = water.open_level_streams(network)
    selected = result.edges[result.edges.source == water.STREAMS]
    for y, expected in ((0, True), (100, False), (200, False), (300, False), (400, True)):
        pieces = selected[selected.geometry.apply(lambda line, row=y: line.coords[0][1] == row)]
        assert len(pieces) == 2
        assert pieces.one_way.tolist() == [expected, expected]
    steep = selected[selected.geometry.apply(lambda line: line.coords[0][1] == 0)]
    assert steep.length_m.min() == pytest.approx(10)
    assert network.edges.loc[network.edges.source == water.STREAMS, "one_way"].all()
    pd.testing.assert_frame_equal(result.edges.drop(columns="one_way"), network.edges.drop(columns="one_way"))
    pd.testing.assert_series_equal(
        result.edges.loc[result.edges.source == "path", "one_way"], network.edges.loc[network.edges.source == "path", "one_way"]
    )
    assert result.chains is network.chains and result.nodes is network.nodes
    assert "Streams opened (level): 2 chains, 4 edges, 1.100 km" in capsys.readouterr().out


@pytest.mark.parametrize("values", [[], [1.0], [1.0, np.nan], 1.0])
def test_a_stream_needs_read_heights_before_its_direction_can_open(values):
    stream = NetworkSource(
        water.STREAMS, gpd.GeoDataFrame(geometry=[LineString([(100, 0), (0, 0)])], crs=CRS), kind=PADDLE, directed=True, keep_whole=True
    )
    network = with_elevation(build_network([stream], metric_crs=CRS, bridge_m=0), lambda coordinates: coordinates[:, 0])
    network.edges["elevations"] = pd.Series([np.asarray(values)], index=network.edges.index, dtype=object)
    with pytest.raises(ValueError, match="at least two finite heights"):
        water.open_level_streams(network)


def test_portages_only_join_delaunay_neighbours_and_never_cross_a_third_lake():
    surfaces = gpd.GeoDataFrame(geometry=[box(0, 0, 100, 100), box(500, 0, 600, 100), box(250, -100, 350, 1000)], crs=CRS)
    paddle = water.sources(surfaces, metric_crs=CRS)
    walking = build_network([NetworkSource("path", gpd.GeoDataFrame(geometry=[], crs=CRS))], metric_crs=CRS)
    chords, _ = water.portages(paddle, walking)
    assert not chords.gdf.empty
    for chord in chords.gdf.geometry:
        assert sum(chord.intersects(surface) for surface in surfaces.geometry) == 2
    collinear = gpd.GeoDataFrame(geometry=[box(x, 0, x + 100, 100) for x in (0, 200, 400, 600)], crs=CRS)
    chords, _ = water.portages(water.sources(collinear, metric_crs=CRS), walking)
    assert len(chords.gdf) == len(collinear) - 1
    assert not any(one.crosses(other) for one in chords.gdf.geometry for other in chords.gdf.geometry)


def test_one_water_piece_needs_no_portages():
    surfaces = gpd.GeoDataFrame(geometry=[box(0, 0, 100, 100)], crs=CRS)
    walking = build_network([NetworkSource("path", gpd.GeoDataFrame(geometry=[], crs=CRS))], metric_crs=CRS)
    assert all(source.gdf.empty for source in water.portages(water.sources(surfaces, metric_crs=CRS), walking))


def test_a_closed_stream_does_not_turn_the_land_inside_it_into_water():
    surfaces = gpd.GeoDataFrame(geometry=[box(0, 0, 100, 100), box(200, 0, 300, 100)], crs=CRS)
    paddle = water.sources(surfaces, metric_crs=CRS)
    stream = gpd.GeoDataFrame(geometry=[box(-200, -200, 800, 800).boundary], crs=CRS)
    paddle.append(NetworkSource(water.STREAMS, stream, kind=PADDLE, directed=True))
    walking = build_network([NetworkSource("path", gpd.GeoDataFrame(geometry=[], crs=CRS))], metric_crs=CRS)
    chords, _ = water.portages(paddle, walking)
    assert any(all(chord.intersects(surface) for surface in surfaces.geometry) for chord in chords.gdf.geometry)


def test_ponds_leave_no_paddle_lines_or_portages_but_do_not_change_the_input():
    surfaces = gpd.GeoDataFrame(geometry=[box(0, 0, 100, 99), box(200, 0, 300, 100)], crs=CRS)
    before = surfaces.copy()
    paddle = water.sources(surfaces, metric_crs=CRS)
    assert all(source.gdf.geometry.intersects(surfaces.geometry.iloc[1]).all() for source in paddle)
    assert not any(source.gdf.geometry.intersects(surfaces.geometry.iloc[0]).any() for source in paddle)
    walking = build_network([NetworkSource("path", gpd.GeoDataFrame(geometry=[], crs=CRS))], metric_crs=CRS)
    assert all(source.gdf.empty for source in water.portages(paddle, walking))
    assert surfaces.equals(before)
