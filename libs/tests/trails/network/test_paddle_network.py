"""The line off the bank wired into a build: its sources, chords, bridges, stream directions and lake planes (phase 12e)."""

from dataclasses import replace

import geopandas as gpd
import numpy as np
import pytest
import shapely
from shapely.geometry import LineString, Point, box
from trails.network import graphs, paddle_geometry, paddle_network, water
from trails.routing.elevation import with_elevation
from trails.routing.graph import Network, build_network
from trails.routing.sources import BRIDGE, LANDING, OPEN, PADDLE, PATH, STREAM, TRAVEL, NetworkSource

CRS = "EPSG:3006"
LAKE = "Sjö"
RIVER = "Vattendragsyta"


def _map(dams: list[Point] | None = None) -> dict:
    """Two lakes joined by a 20 m river channel, a stream into one and another through the other, and ways to them.

    The channel is narrower than 2d, so its middle is Narrow water. A road ends 20 m
    below the first lake (a launch), a track 10 m below the channel (a bridge to the
    old bank), and a path joins them.
    """
    surfaces = gpd.GeoDataFrame(
        {"cls": [LAKE, RIVER, LAKE], "level": [None, None, None]},
        geometry=[box(0, 0, 200, 200), box(200, 90, 300, 110), box(300, 0, 500, 200)],
        crs=CRS,
    )
    streams = gpd.GeoDataFrame(
        {"storleksklass": ["2", "2"]},
        # Into the first lake's north bank, and through the second lake from north to south.
        geometry=[LineString([(100, 400), (100, 200)]), LineString([(400, 300), (400, -100)])],
        crs=CRS,
    )
    walking = [
        NetworkSource("path", gpd.GeoDataFrame(geometry=[LineString([(0, -100), (500, -100)])], crs=CRS)),
        NetworkSource("road", gpd.GeoDataFrame(geometry=[LineString([(100, -100), (100, -20)])], crs=CRS)),
        NetworkSource("track", gpd.GeoDataFrame(geometry=[LineString([(250, -100), (250, 80)])], crs=CRS)),
    ]
    return {"surfaces": surfaces, "streams": streams, "walking": walking, "dams": gpd.GeoDataFrame(geometry=dams or [], crs=CRS)}


def _build(parts: dict, *, offset: bool) -> tuple[Network, list[NetworkSource]]:
    zone = gpd.GeoDataFrame(geometry=[box(-100, -200, 600, 500)], crs=CRS)
    fields = {"class_field": "cls", "lake_classes": (LAKE,), "level_field": "level"}
    paddled = water.paddle(parts["surfaces"], metric_crs=CRS, streams=parts["streams"], dams=parts["dams"], extent=zone, **fields)
    halo = paddle_network.Offset(parts["surfaces"], zone.to_crs("EPSG:4326").union_all(), zone, "cls", (LAKE,), "level") if offset else None
    sources = [*parts["walking"], *paddled.sources]
    empty = gpd.GeoSeries([], crs=CRS)
    network, _ = water.build(
        sources,
        graphs.Masks(empty, empty, empty),
        zone,
        graphs.Params(cache_dir="/nonexistent"),
        graphs.Rules(metric_crs=CRS, layout="test", protected_id="id", protected_name="name", protected_form="form", form_label=str),
        protected=gpd.GeoDataFrame({"id": [], "name": [], "form": []}, geometry=[], crs=CRS),
        # Heights fall northwards to southwards by a metre in ten: the streams fall, the lakes are levelled.
        measure=lambda network: with_elevation(network, lambda coordinates: 100 + coordinates[:, 1] / 10),
        access=water.Access(parts["surfaces"], parts["dams"], paddled.bank, halo),
    )
    return network, sources


@pytest.fixture(scope="module")
def built() -> dict:
    parts = _map()
    off, off_sources = _build(parts, offset=False)
    on, on_sources = _build(parts, offset=True)
    return {"off": off, "on": on, "off_sources": off_sources, "on_sources": on_sources, "parts": parts}


def test_every_new_source_carries_its_price_role_and_lake_owner(built):
    sources = {source.name: source for source in built["on_sources"] if source.kind == PADDLE}
    expected = {
        water.SHORE: (1.0, TRAVEL),
        water.NARROW_WATER: (1.0, TRAVEL),
        water.LANDING_WATER: (1.0, LANDING),
        water.OPEN_WATER: (water.OPEN_WATER_FACTOR, OPEN),
        water.STREAMS: (1.0, STREAM),
    }
    assert {name: (source.cost_factor, source.role) for name, source in sources.items()} == expected
    edges = built["on"].edges
    for name in expected:
        assert (edges["source"] == name).any(), name
    # Walking never had these: they are paddled, and a bridge is the earlier build's.
    assert set(edges.loc[edges["kind"] == PADDLE, "source"]) == set(expected)
    assert not (built["off"].edges["source"].isin((water.NARROW_WATER, water.LANDING_WATER))).any()
    costs = graphs.edge_costs(built["on_sources"], graphs.Params(cache_dir="/nonexistent"))
    assert {name: costs[name]["role"] for name in expected} == {name: role for name, (_, role) in expected.items()}
    assert all("role" not in cost for cost in graphs.edge_costs(built["off_sources"], graphs.Params(cache_dir="/nonexistent")).values())


def test_carries_and_launches_are_the_bank_build_s_and_the_line_is_offshore(built):
    for name in (water.LAUNCHES, water.PORTAGES, water.PORTAGE_PATHS):
        off = next(s for s in built["off_sources"] if s.name == name).gdf
        on = next(s for s in built["on_sources"] if s.name == name).gdf
        assert len(on) == len(off) and on.geometry.geom_equals_exact(off.geometry, 0).all(), name
    edges = built["on"].edges
    water_area = built["parts"]["surfaces"].union_all()
    bank = water_area.boundary
    shore = edges[edges["source"] == water.SHORE]
    assert shapely.distance(shore.geometry.to_numpy(), bank).min() >= paddle_geometry.CONTOUR_CLEARANCE_M
    # The launch still ends 20 m from the road, and Landing water carries on from its bank end.
    launch = edges[edges["source"] == water.LAUNCHES]
    assert sorted(launch["length_m"].round(6)) == [10, 20]
    ends = set(launch["from_node"]) | set(launch["to_node"])
    landing = edges[edges["source"] == water.LANDING_WATER]
    assert ends & (set(landing["from_node"]) | set(landing["to_node"]))


def test_chords_follow_today_s_rule_inside_the_water_d_from_the_bank():
    # A lake with a bay and an island, and a river beside it: chords stay per owner and off the contour.
    lake = box(0, 0, 300, 200).difference(box(120, 60, 160, 100)).difference(box(200, -1, 230, 120))
    river = box(300, 80, 400, 130)
    surfaces = gpd.GeoDataFrame({"cls": [LAKE, RIVER]}, geometry=[lake, river], crs=CRS)
    bodies = water.eligible_bodies(surfaces, "cls", (LAKE,), None)
    result = paddle_geometry.contours(bodies, crs=CRS)
    landed = paddle_geometry.landings(result, bodies, gpd.GeoDataFrame({"roles": [], "surface": [], "anchor": []}, geometry=[], crs=CRS), crs=CRS)
    interfaces, _ = paddle_network._interfaces(landed, result.lines, result.centre)
    rows, counts = paddle_network._chords(result, bodies, {0: interfaces}, {})
    chords = np.array([row["geometry"] for row in rows], dtype=object)
    assert counts["chords"] == len(chords) > 20 and counts["delaunay"] > counts["chords"]
    region = result.regions.geometry.union_all().buffer(paddle_network.REGION_SLACK_M)
    assert shapely.covers(region, chords).all()
    # None crosses the island's contour, runs along the contour or crosses the lake/river interface.
    contour = shapely.union_all(result.lines.geometry.to_numpy())
    for line in chords:
        tips = shapely.multipoints(shapely.get_coordinates(line)[[0, -1]])
        assert shapely.difference(shapely.intersection(line, contour), tips).is_empty
        assert shapely.difference(shapely.intersection(line, shapely.union_all(interfaces)), tips).is_empty
    owners = {row[water.LAKE_BODY] for row in rows}
    assert None in owners and len(owners) == 2
    runs = [shapely.get_coordinates(line) for line in result.lines.geometry]
    segments = {tuple(sorted(map(tuple, pair))) for run in runs for pair in zip(run[:-1], run[1:], strict=True)}
    assert not {tuple(sorted(map(tuple, shapely.get_coordinates(line)))) for line in chords} & segments


def test_the_channel_s_middle_joins_both_lakes_and_every_interface_is_lake_owned_once(built):
    edges = built["on"].edges
    narrow = edges[edges["source"] == water.NARROW_WATER]
    assert narrow.geometry.union_all().intersects(box(220, 99, 280, 101))
    paddled = edges[edges["kind"] == PADDLE]
    assert paddled["component"].nunique() == 1
    lake_a = paddled[paddled.geometry.within(box(0, 0, 200, 200))]
    lake_b = paddled[paddled.geometry.within(box(300, 0, 500, 200))]
    assert set(lake_a["component"]) == set(lake_b["component"])
    interfaces = edges[
        (edges["source"] == water.OPEN_WATER) & edges.geometry.apply(lambda g: g.within(LineString([(200, 80), (200, 120)]).buffer(0.1)))
    ]
    assert len(interfaces) >= 1
    chains = built["on"].chains.set_index("chain_id")
    assert chains.loc[interfaces["chain_id"], water.LAKE_BODY].notna().all()


def test_a_bridge_to_the_old_bank_now_reaches_its_anchor_and_its_spur(built):
    off, on = built["off"].edges, built["on"].edges
    track_end = Point(250, 80)
    old = off[(off["kind"] == BRIDGE) & (shapely.distance(off.geometry.to_numpy(), track_end) < 0.01)]
    new = on[(on["kind"] == BRIDGE) & (shapely.distance(on.geometry.to_numpy(), track_end) < 0.01)]
    assert len(old) == len(new) == 1
    # The same line: the anchor is the old bank point it reached.
    assert new.geometry.iloc[0].equals_exact(old.geometry.iloc[0], 1e-6)
    anchor = set(new[["from_node", "to_node"]].to_numpy().ravel()) - {int(built["on"].nodes.sindex.nearest(track_end)[1][0])}
    landing = on[on["source"] == water.LANDING_WATER]
    assert anchor & (set(landing["from_node"]) | set(landing["to_node"]))
    # No bridge is inferred anew: every one is the earlier build's, and none lands on a line of the offset network.
    assert len(on[on["kind"] == BRIDGE]) <= len(off[off["kind"] == BRIDGE])


def test_stream_directions_are_the_bank_build_s_even_where_the_new_lines_cut_them_finer(built):
    off, on = built["off"].edges, built["on"].edges
    old = off[off["source"] == water.STREAMS].groupby("chain_id")
    new = on[on["source"] == water.STREAMS].groupby("chain_id")
    assert set(old.groups) == set(new.groups)

    def cuts(group: gpd.GeoDataFrame) -> set[tuple[float, float]]:
        return {tuple(np.round(xy, 3)) for line in group.geometry for xy in shapely.get_coordinates(line)[[0, -1]]}

    # The stream through the second lake is cut where the contour and the chords cross it, not where the bank did.
    assert any(cuts(new.get_group(chain)) != cuts(old.get_group(chain)) for chain in old.groups)
    for chain in old.groups:
        assert set(new.get_group(chain)["one_way"]) == set(old.get_group(chain)["one_way"]), chain


def test_lake_planes_are_read_off_the_bank_as_before(built):
    def planes(network: Network) -> dict[str, set[float]]:
        chains = network.chains.set_index("chain_id")[water.LAKE_BODY]
        lakes = network.edges[network.edges["source"].isin(water.LAKE_SOURCES)]
        out: dict[str, set[float]] = {}
        for chain, values in zip(lakes["chain_id"], lakes["elevations"], strict=True):
            body = chains.get(chain)
            if isinstance(body, str):
                out.setdefault(body, set()).update(np.round(np.asarray(values, dtype=float), 9).tolist())
        return out

    off, on = planes(built["off"]), planes(built["on"])
    assert set(off) == set(on) and all(len(values) == 1 for values in on.values())
    assert off == on


def test_phase_seven_decides_on_the_edges_it_is_given():
    """A chain falling 0.4 m in two edges stays one way; the same chain cut into five level-looking pieces does not decide it."""

    def frame(pieces: list[list[float]]) -> gpd.GeoDataFrame:
        lines = [LineString([(i * 10, 0), (i * 10 + 10, 0)]) for i in range(len(pieces))]
        return gpd.GeoDataFrame(
            {
                "source": water.STREAMS,
                "kind": PADDLE,
                "chain_id": "streams-1",
                "one_way": True,
                "from_node": range(len(pieces)),
                "to_node": range(1, len(pieces) + 1),
                "length_m": [10.0] * len(pieces),
                "elevations": [np.asarray(values) for values in pieces],
            },
            geometry=lines,
            crs=CRS,
        )

    # Each fine piece reads its own quarters: they sum to 0.25 m, under the 0.3 m gate.
    fine = frame([[1.0, 1.0, 1.0, 0.95], [0.95, 0.95, 0.95, 0.9], [0.9, 0.9, 0.9, 0.85], [0.85, 0.85, 0.85, 0.8], [0.8, 0.8, 0.8, 0.75]])
    coarse = frame([[1.0, 1.0, 0.8, 0.8], [0.8, 0.8, 0.6, 0.6]])
    network = Network(
        chains=gpd.GeoDataFrame({"chain_id": ["streams-1"]}, geometry=[LineString([(0, 0), (50, 0)])], crs=CRS),
        edges=fine,
        nodes=gpd.GeoDataFrame(geometry=[], crs=CRS),
    )
    assert not water.open_level_streams(network).edges["one_way"].any()
    assert water.open_level_streams(network, decided_by=coarse).edges["one_way"].all()
    with pytest.raises(ValueError, match="exactly the network's stream chains"):
        water.open_level_streams(network, decided_by=coarse.assign(chain_id="streams-2"))


def test_settled_lines_join_what_they_end_on_and_neither_seek_nor_receive_bridges():
    path = NetworkSource(PATH, gpd.GeoDataFrame(geometry=[LineString([(0, 0), (100, 0)]), LineString([(40, 10), (40, 30)])], crs=CRS))
    # A spur ending a hair off the path's middle, and another whose far end is loose 5 m from the second path's end.
    spur = [LineString([(50, 50), (50, 1e-9)]), LineString([(30, 50), (45, 32)])]
    settled = NetworkSource("Landing water", gpd.GeoDataFrame(geometry=spur, crs=CRS), kind=PADDLE, keep_whole=True, settled=True)
    network = build_network([path, settled], metric_crs=CRS, bridge_m=25.0)
    edges = network.edges
    landing = edges[edges["source"] == "Landing water"]
    walked = edges[edges["source"] == PATH]
    joined = (set(landing["from_node"]) | set(landing["to_node"])) & (set(walked["from_node"]) | set(walked["to_node"]))
    assert len(joined) == 1 and network.nodes.geometry.iloc[joined.pop()].distance(Point(50, 0)) < 1e-6
    # The second path's loose end at (40, 30) bridges to nothing settled, and the spur's loose end seeks nothing.
    assert not ((edges["kind"] == "bridge") & (shapely.distance(edges.geometry.to_numpy(), Point(45, 32)) < 1)).any()


def test_a_dam_on_the_bank_keeps_every_new_line_out_of_its_disc():
    parts = _map(dams=[Point(400, 0)])
    network, sources = _build(parts, offset=True)
    edges = network.edges
    new = edges[edges["source"].isin(paddle_network.PADDLED)]
    near = shapely.distance(new.geometry.to_numpy(), Point(400, 0))
    assert near.min() >= water.DAM_CUT_M - 0.07
    streams = edges[edges["source"] == water.STREAMS]
    assert shapely.distance(streams.geometry.to_numpy(), Point(400, 0)).min() >= water.DAM_CUT_M - 1e-6


def test_the_deviation_bound_proved_holds_where_every_segment_is_sampled():
    # Where the page's grid moves a vertex by at most GRID_MOVE_M: in Sweden, not at SWEREF's false origin.
    centre = Point(650_000, 7_580_000)
    shape = centre.buffer(200, quad_segs=64).difference(box(centre.x - 30, centre.y - 300, centre.x + 30, centre.y - 150))
    water_area = gpd.GeoDataFrame({"cls": [LAKE]}, geometry=[shape], crs=CRS)
    bodies = water.eligible_bodies(water_area, "cls", (LAKE,), None)
    proved = paddle_geometry.contours(bodies, crs=CRS)
    sampled = paddle_geometry.contours(bodies, crs=CRS, prove_deviation=False)
    assert proved.lines.geometry.geom_equals_exact(sampled.lines.geometry, 0).all()
    assert (sampled.lines["max_deviation_m"] <= proved.lines["deviation_bound_m"] + 1e-9).all()
    assert (proved.lines["deviation_bound_m"] <= paddle_geometry.CONTOUR_DEVIATION_M).all()
    assert (proved.lines["deviation_bound_m"] <= paddle_geometry.CONTOUR_SIMPLIFY_M + paddle_geometry.GRID_MOVE_M).all()


def test_an_offset_source_names_a_known_role():
    with pytest.raises(ValueError, match="unknown role"):
        NetworkSource("x", gpd.GeoDataFrame(geometry=[], crs=CRS), kind=PADDLE, role="bank")
    assert replace(NetworkSource("x", gpd.GeoDataFrame(geometry=[], crs=CRS)), role=TRAVEL).role == TRAVEL


def test_a_carry_ending_at_a_dam_anchor_ends_where_its_spur_was_moved_out_of_the_disc():
    carry = NetworkSource(
        water.PORTAGES, gpd.GeoDataFrame(geometry=[LineString([(0, -100), (0, -25.0)]), LineString([(50, -100), (50, -60)])], crs=CRS)
    )
    written = np.array([0.0, -25.1])
    moved = paddle_network._moved_ends(carry, {7: (np.array([0.0, -25.0]), written)}, CRS)
    ends = [shapely.get_coordinates(line)[-1] for line in moved.gdf.geometry]
    assert ends[0] == pytest.approx(written) and ends[1] == pytest.approx([50, -60])
    assert moved.gdf.crs == carry.gdf.crs
