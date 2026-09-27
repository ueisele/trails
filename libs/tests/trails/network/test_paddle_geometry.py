"""The line off the bank: offset contours, their cuts and their gates."""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely
from shapely.geometry import LineString, Point, Polygon, box
from trails.network import paddle_geometry as pg
from trails.network import water

CRS = "EPSG:3006"
#: Real SWEREF 99 TM coordinates, so the page's degree grid is the one a Swedish map uses.
X0, Y0 = 500_000.0, 6_600_000.0


def at(x0: float, y0: float, x1: float, y1: float):
    return box(X0 + x0, Y0 + y0, X0 + x1, Y0 + y1)


def bodies(*shapes, classes=None, levels=None) -> water.Bodies:
    frame = gpd.GeoDataFrame({"class": classes or ["lake"] * len(shapes), "level": levels or [None] * len(shapes)}, geometry=list(shapes), crs=CRS)
    return water.eligible_bodies(frame, "class", ("lake",), "level")


def assert_gates(result: pg.Contours) -> None:
    lines = result.lines
    assert lines["passes"].all()
    for clearance, deviation in zip(lines["segment_clearance_m"], lines["segment_deviation_m"], strict=True):
        assert clearance.min() >= pg.CONTOUR_CLEARANCE_M
        assert deviation.max() <= pg.CONTOUR_DEVIATION_M


def test_a_broad_lake_gets_one_closed_line_fifteen_metres_out():
    result = pg.contours(bodies(at(0, 0, 400, 200)), crs=CRS)
    assert len(result.lines) == 1
    line = result.lines.iloc[0]
    assert (line["role"], line["start"], line["end"]) == (pg.SHORE_ROLE, pg.RING, pg.RING)
    assert line.geometry.is_closed
    assert line["raw"].equals(at(15, 15, 385, 185).exterior)
    # The written line is the page's: a vertex moves by the degree grid, never more than 0.07 m here.
    assert shapely.hausdorff_distance(line.geometry, line["raw"]) < 0.07
    assert_gates(result)


def test_offsetting_the_whole_body_leaves_no_line_along_a_lake_river_interface():
    result = pg.contours(bodies(at(0, 0, 300, 300), at(300, 130, 600, 170), classes=["lake", "river"], levels=["207", None]), crs=CRS)
    lines = result.lines
    interface = LineString([(X0 + 300, Y0 + 130), (X0 + 300, Y0 + 170)])
    # The line crosses the interface where the river's two banks are offset, and never runs along it.
    crossing = shapely.union_all(lines.geometry.intersection(shapely.buffer(interface, 0.1)).to_numpy())
    assert crossing.length < 0.5
    assert set(lines[water.SURFACE_CLASS]) == {"lake", "river"}
    assert lines.loc[lines[water.SURFACE_CLASS] == "lake", water.LAKE_LEVEL].eq(207).all()
    assert lines.loc[lines[water.SURFACE_CLASS] == "river", water.LAKE_BODY].isna().all()
    # The two owners meet at pinned vertices on the interface line, not at a bank.
    assert set(lines["start"]) | set(lines["end"]) == {pg.INTERFACE}
    ends = shapely.points([c for g in lines.geometry for c in (g.coords[0], g.coords[-1])])
    assert np.allclose(shapely.get_x(ends), X0 + 300, atol=0.07)
    assert sorted({round(y - Y0) for y in shapely.get_y(ends)}) == [145, 155]
    assert_gates(result)


def test_a_closed_bay_mouth_is_a_cap_and_never_shore():
    lake_and_bay = shapely.union(at(0, 0, 400, 200), at(190, 200, 210, 350))
    result = pg.contours(bodies(lake_and_bay), crs=CRS)
    caps = result.lines[result.lines["role"] == pg.CAP_ROLE]
    assert len(caps) == 1 and len(result.caps) == 1
    assert result.caps.iloc[0]["kind"] == "terminal"
    assert result.caps.iloc[0]["reach_m"] >= pg.BAY_REACH_M
    mouth = LineString([(X0 + 190, Y0 + 200), (X0 + 210, Y0 + 200)])
    shoulders = shapely.multipoints(mouth.coords)
    # The cap is the contour the mouth's two shoulders hold 15 m off: their arcs, meeting in front of it.
    cap = caps["raw"].iloc[0]
    assert np.allclose(shapely.distance(shapely.points(shapely.get_coordinates(cap)), shoulders), 15, atol=0.02)
    assert cap.length < 25
    shore = result.lines[result.lines["role"] == pg.SHORE_ROLE]
    assert shore.geometry.distance(mouth).min() > 15
    assert set(shore["start"]) | set(shore["end"]) == {pg.CAP}
    assert_gates(result)


def test_a_small_indentation_is_smoothed_over_unless_an_anchor_is_in_it():
    notch = shapely.union(at(0, 0, 400, 200), at(190, 200, 210, 212))
    plain = pg.contours(bodies(notch), crs=CRS)
    assert set(plain.lines["role"]) == {pg.SHORE_ROLE}
    assert plain.caps.empty
    anchored = pg.contours(bodies(notch), crs=CRS, anchors=np.array([Point(X0 + 200, Y0 + 213)]))
    assert pg.CAP_ROLE in set(anchored.lines["role"])
    assert anchored.caps["anchored"].all()


def test_a_body_narrower_than_twice_the_offset_is_reported_as_vanished():
    result = pg.contours(bodies(at(0, 0, 400, 28)), crs=CRS)
    assert result.lines.empty
    assert len(result.vanished) == 1
    assert result.vanished.iloc[0]["classes"] == "lake"
    assert result.vanished.iloc[0]["area_ha"] == pytest.approx(1.12)


def test_the_map_crop_cuts_the_line_without_following_the_crop():
    extent = at(-50, -50, 200, 250)
    result = pg.contours(bodies(at(0, 0, 400, 200)), crs=CRS, extent=extent)
    assert len(result.lines) == 1
    line = result.lines.iloc[0]
    assert (line["start"], line["end"]) == (pg.CROP, pg.CROP)
    # Top and bottom from x = 15 to the crop at 200, and the west side between them.
    assert line["raw"].length == pytest.approx(2 * 185 + 170)
    assert_gates(result)


def test_a_dam_disc_cuts_the_line_and_nothing_is_drawn_inside_it():
    dam = Point(X0 + 200, Y0 + 10)
    result = pg.contours(bodies(at(0, 0, 400, 200)), crs=CRS, dams=np.array([dam]))
    assert len(result.lines) == 1
    line = result.lines.iloc[0]
    assert (line["start"], line["end"]) == (pg.DAM, pg.DAM)
    assert line["raw"].distance(dam) == pytest.approx(water.DAM_CUT_M)
    assert line.geometry.distance(dam) >= water.DAM_CUT_M - 0.07
    assert_gates(result)


def test_an_island_of_any_size_keeps_its_own_ring():
    lake = at(0, 0, 400, 400).difference(at(199.5, 199.5, 200.5, 200.5))
    result = pg.contours(bodies(lake), crs=CRS)
    assert len(result.lines) == 2
    ring = min(result.lines["raw"], key=lambda line: line.length)
    island = at(199.5, 199.5, 200.5, 200.5)
    # A 1 m² island is still an island; its ring is the offset circle, 32 chords to the quarter.
    assert ring.distance(island) >= 15 - pg.offset_error_m(15, pg.CONTOUR_QUAD_SEGS) - 1e-9
    assert ring.hausdorff_distance(island) <= 15 + 1.0
    assert_gates(result)


def test_refinement_gives_back_vertices_until_the_gates_hold():
    # A bank of 10 m teeth: at a 6 m starting tolerance the line breaks the 2.1 m gate.
    teeth = [(X0 + x, Y0 + (10 if i % 2 else 0)) for i, x in enumerate(range(0, 401, 20))]
    lake = shapely.Polygon([*teeth, (X0 + 400, Y0 + 300), (X0, Y0 + 300)])
    result = pg.contours(bodies(lake), crs=CRS, tolerance_m=6.0)
    assert result.lines["refined"].sum() > 0
    assert_gates(result)


def test_simplification_keeps_its_ends_and_never_collapses_a_ring():
    ring = np.array([(0, 0), (1, 0.1), (2, 0), (2, 1), (1, 1.1), (0, 1), (0, 0)], dtype=float)
    kept = pg.simplify_pinned(ring, 5.0)
    assert kept[0] == 0 and kept[-1] == len(ring) - 1
    assert len({tuple(ring[i]) for i in kept}) >= 3
    rng = np.random.default_rng(20260926)
    line = np.c_[np.linspace(0, 500, 400), rng.normal(0, 3, 400).cumsum()]
    kept = pg.simplify_pinned(line, 2.0)
    assert shapely.hausdorff_distance(LineString(line), LineString(line[kept]), densify=0.01) <= 2.0 + 1e-9


def test_the_offset_error_of_the_reference_contour_is_the_measured_one():
    # A square headland: its fillet is where the chords cut inside d.
    lake = at(0, 0, 400, 400).difference(at(150, 150, 250, 250))
    result = pg.contours(bodies(lake), crs=CRS)
    least = result.lines["raw_min_clearance_m"].min()
    assert 15 - pg.offset_error_m(15, pg.CONTOUR_QUAD_SEGS) - 1e-9 <= least < 15
    assert pg.offset_error_m(15, 8) == pytest.approx(0.1624, abs=1e-4)
    assert pg.offset_error_m(15, 32) == pytest.approx(0.0102, abs=1e-4)


def test_eligible_bodies_keep_the_groups_the_shore_is_built_from():
    frame = gpd.GeoDataFrame(
        {"class": ["lake", "lake", "river", "lake"], "level": ["207", "100-102", None, "5"]},
        geometry=[at(0, 0, 100, 100), at(100, 0, 200, 100), at(200, 40, 300, 60), at(1000, 0, 1060, 60)],
        crs=CRS,
    )
    found = water.eligible_bodies(frame, "class", ("lake",), "level")
    # The 0.36 ha pond is not paddle water; the two lakes and the river are one body.
    assert len(found.polygons) == 3
    assert set(found.body) == {0}
    assert [owner[water.SURFACE_CLASS] for owner in found.owners] == ["lake", "river"]
    assert found.owners[0][water.LAKE_LEVEL] == 100
    groups, boundary = water._dissolved(frame, "class", ("lake",), "level")
    assert [g[0] for g in groups] == found.owners
    for index, (_, geometry) in enumerate(groups):
        assert geometry.equals(shapely.union_all(found.polygons[found.owner == index]))
    assert boundary.equals(found.union(0).boundary)


# The centre network where the offset cannot carry the water (phase 12c).


def graph(*frames: gpd.GeoDataFrame) -> tuple[dict, dict]:
    """The written lines as a graph: nodes are exact coordinates, so lines join only where they share a vertex."""
    adjacency: dict = {}
    source: dict = {}
    for frame in frames:
        for line, role in zip(frame.geometry, frame["role"], strict=True):
            coords = [tuple(c) for c in line.coords]
            for one, other in zip(coords[:-1], coords[1:], strict=True):
                adjacency.setdefault(one, set()).add(other)
                adjacency.setdefault(other, set()).add(one)
                source[frozenset((one, other))] = role
    return adjacency, source


def reachable(adjacency: dict, start, *, avoid=None) -> set:
    seen = {start}
    stack = [start]
    for _ in range(len(adjacency) + 1):
        if not stack:
            break
        node = stack.pop()
        for other in adjacency[node]:
            if other not in seen and (avoid is None or not avoid(node, other)):
                seen.add(other)
                stack.append(other)
    return seen


def assert_centre_gates(result: pg.Contours, water) -> None:
    centre = result.centre
    assert centre["passes"].all()
    assert (centre["middle_max_m"] <= np.minimum(pg.MIDDLE_LIMIT_M, 1.0)).all()
    assert (centre["dry_m"] == 0).all()
    assert shapely.covers(water.buffer(0.07), shapely.union_all(centre.geometry.to_numpy()))


def test_a_narrow_between_two_lakes_carries_a_centre_line_from_one_contour_to_the_other():
    # Two lakes joined by a channel 24 m wide and 200 m long: the offset splits there.
    water_ = shapely.union_all([at(0, 0, 300, 300), at(300, 138, 500, 162), at(500, 0, 800, 300)])
    result = pg.contours(bodies(water_), crs=CRS)
    assert len(result.lines.loc[result.lines["role"] == pg.SHORE_ROLE]) == 2
    centre = result.centre
    assert set(centre["category"]) == {pg.PASSAGE}
    assert set(centre["source"]) == {pg.NARROW_WATER}
    # Down the middle of the channel, 12 m from both banks.
    channel = centre.geometry.intersection(at(310, 138, 490, 162)).union_all()
    assert channel.length == pytest.approx(180, abs=0.1)
    assert shapely.hausdorff_distance(channel, LineString([(X0 + 310, Y0 + 150), (X0 + 490, Y0 + 150)])) < 0.1
    # Through travel: from the west contour to the east contour on Narrow water only.
    adjacency, source = graph(result.lines, centre)
    west = tuple(result.lines.geometry.iloc[0].coords[0])
    east = next(tuple(c) for g in result.lines.geometry for c in g.coords if c[0] > X0 + 500)
    assert east in reachable(adjacency, west)
    joins = result.nodes[result.nodes["kind"] == pg.JOIN]
    assert len(joins) == 2
    for join in joins.geometry:
        # The join is a vertex of the raw contour, pinned: the middle meets it where its radius reaches d.
        assert any(join.coords[0] in set(g.coords) for g in result.lines["raw"])
        assert join.distance(water_.boundary) == pytest.approx(15, abs=0.02)
    # Once written, the centre line ends on a vertex of the written contour.
    ends = {c for g in centre.geometry for c in (g.coords[0], g.coords[-1])}
    assert sum(any(end in set(g.coords) for g in result.lines.geometry) for end in ends) == 2
    # Neither contour runs across the channel mouth as shore: those spans are caps between two shoulders.
    caps = result.lines[result.lines["role"] == pg.CAP_ROLE]
    assert set(caps["source"]) == {water.OPEN_WATER}
    assert_centre_gates(result, water_)


def test_both_ways_round_an_island_close_to_the_bank_are_kept():
    # An island 20 m off the bank: the offset closes the gap, the centre line opens it.
    lake = at(0, 0, 400, 300).difference(at(150, 20, 250, 100))
    result = pg.contours(bodies(lake), crs=CRS)
    centre = result.centre
    assert len(centre) and set(centre["category"]) == {pg.PASSAGE}
    # The gap's centre line runs 10 m from the bank and the island.
    gap = centre.geometry.intersection(at(160, 0, 240, 20)).union_all()
    assert gap.length == pytest.approx(80, abs=0.5)
    assert abs(shapely.get_coordinates(gap)[:, 1] - (Y0 + 10)).max() < 0.1
    # Each side has its way: the island lies alone in a face of the network.
    network = shapely.union_all(np.asarray([*result.lines.geometry, *centre.geometry], dtype=object))
    faces = shapely.get_parts(shapely.polygonize(shapely.get_parts(network)))
    island = at(150, 20, 250, 100)
    holding = [f for f in faces if f.contains(island.representative_point())]
    assert len(holding) == 1 and holding[0].contains(island.buffer(-0.01))
    # The arcs round the island's corners are held by one shoulder each: shore, not a crossing.
    assert set(result.lines.loc[result.lines["role"] == pg.CAP_ROLE, "source"]) == {water.SHORE}
    assert_centre_gates(result, lake)


def test_a_terminal_bay_is_kept_when_its_branch_reaches_thirty_metres_and_pruned_when_it_does_not():
    # Two bays 20 m wide off one lake. From the join, 11.18 m below the mouth, the deep bay's middle
    # runs 16.18 m to where its end and sides are 10 m away and 14.14 m on into a corner: 30.32 m.
    # The shallow one's, 5 m deep, runs 3.68 m to where its end is as near as its shoulders, 9.05 m on
    # the parabola between a shoulder and the end, and 7.07 m down a corner's bisector: 19.80 m.
    deep, shallow = at(100, 300, 120, 315), at(300, 300, 320, 305)
    lake = shapely.union_all([at(0, 0, 400, 300), deep, shallow])
    result = pg.contours(bodies(lake), crs=CRS)
    kept = result.centre[result.centre["category"] == pg.BAY]
    assert len(kept) == 1 and kept.geometry.iloc[0].distance(deep) < 1e-6
    assert kept.geometry.iloc[0].length == pytest.approx(30.32, abs=0.05)
    pruned = result.pruned[result.pruned.geometry.distance(shallow) < 1e-6]
    assert len(pruned) == 1
    assert pruned["category"].iloc[0] == pg.BAY
    assert pruned["longest_m"].iloc[0] == pytest.approx(19.80, abs=0.05)
    # The kept bay's mouth is an open-water cap; the pruned one's is smoothed over as shore.
    caps = result.caps
    assert len(caps) == 1 and caps.geometry.iloc[0].intersects(deep)
    assert set(result.lines.loc[result.lines["role"] == pg.CAP_ROLE, "source"]) == {water.OPEN_WATER}
    assert_centre_gates(result, lake)


def test_an_anchor_keeps_a_bay_branch_however_short():
    bay = at(200, 300, 220, 306)
    lake = shapely.union_all([at(0, 0, 400, 300), bay])
    plain = pg.contours(bodies(lake), crs=CRS)
    assert plain.centre.empty
    assert (plain.pruned.geometry.distance(bay) < 1e-6).any()
    anchored = pg.contours(bodies(lake), crs=CRS, anchors=np.array([Point(X0 + 210, Y0 + 306)]))
    assert set(anchored.centre["category"]) == {pg.ANCHORED}
    assert anchored.centre.geometry.length.sum() < pg.BAY_REACH_M
    assert anchored.anchors["kept"].all()
    # The anchor's branch runs from the contour to the middle its bank point faces, within the bay's half-width.
    assert anchored.anchors["node_m"].iloc[0] < 10
    assert len(anchored.caps) == 1 and anchored.caps["kept_by"].iloc[0] == pg.ANCHORED
    assert_centre_gates(anchored, lake)


def test_a_body_the_offset_removes_is_crossed_end_to_end_on_one_centre_line():
    river = at(0, 0, 600, 28)
    result = pg.contours(bodies(river), crs=CRS)
    assert result.lines.empty and len(result.vanished) == 1
    centre = result.centre
    assert set(centre["category"]) == {pg.VANISHED}
    adjacency, _ = graph(centre)
    assert len(reachable(adjacency, next(iter(adjacency)))) == len(adjacency)
    # From one end to the other: into a corner at each end, 14 m down the middle between.
    xs = shapely.get_coordinates(centre.geometry.to_numpy())[:, 0] - X0
    assert xs.min() < 1 and xs.max() > 599
    middle = centre.geometry.intersection(at(20, 0, 580, 28)).union_all()
    assert abs(shapely.get_coordinates(middle)[:, 1] - (Y0 + 14)).max() < 0.1
    assert_centre_gates(result, river)


def test_a_dam_cuts_the_centre_line_and_the_middle_does_not_reopen_it():
    # Two lakes joined by a narrow river with a dam on it: the offset splits, the middle
    # would join the halves, and the dam's disc must keep them apart as it does the contour.
    lakes_and_river = shapely.union_all([at(0, 0, 300, 300), at(300, 140, 700, 160), at(700, 0, 1000, 300)])
    dam = Point(X0 + 500, Y0 + 150)
    result = pg.contours(bodies(lakes_and_river), crs=CRS, dams=np.array([dam]))
    centre = result.centre
    assert len(centre) == 2
    assert set(centre["start"]) | set(centre["end"]) == {pg.JOIN, pg.DAM}
    assert centre.geometry.distance(dam).min() >= water.DAM_CUT_M
    adjacency, _ = graph(result.lines, centre)
    west = next(tuple(c) for g in result.lines.geometry for c in g.coords if c[0] < X0 + 300)
    east = next(tuple(c) for g in result.lines.geometry for c in g.coords if c[0] > X0 + 700)
    assert east not in reachable(adjacency, west)
    assert_centre_gates(result, lakes_and_river)


def test_the_middle_is_the_same_at_half_the_sampling_step_and_across_tile_borders():
    # A bent, uneven channel between two lakes, built in 60 m tiles so edges cross borders.
    channel = LineString([(X0 + 300, Y0 + 150), (X0 + 420, Y0 + 170), (X0 + 500, Y0 + 260), (X0 + 620, Y0 + 250)]).buffer(9, quad_segs=3)
    lake = shapely.union_all([at(0, 0, 300, 300), channel, at(620, 100, 900, 400)])
    whole = pg.contours(bodies(lake), crs=CRS)
    finer = pg.contours(bodies(lake), crs=CRS, sample_m=pg.CENTRE_SAMPLE_M / 2)
    tiled = pg.contours(bodies(lake), crs=CRS, tile_m=60.0)
    assert tiled.bodies["medial_overlap_edges"].iloc[0] > 0
    assert tiled.bodies["medial_overlap_mismatches"].iloc[0] == 0
    for other in (finer, tiled):
        for kind in (pg.JOIN, pg.JUNCTION):
            mine, theirs = whole.nodes[whole.nodes["kind"] == kind], other.nodes[other.nodes["kind"] == kind]
            assert len(mine) == len(theirs)
            for point, radius in zip(mine.geometry, mine["radius_m"], strict=True):
                assert theirs.geometry.distance(point).min() <= min(pg.MIDDLE_LIMIT_M, pg.MIDDLE_SHARE * 2 * radius)
    assert tiled.centre.geometry.length.sum() == pytest.approx(whole.centre.geometry.length.sum(), abs=1e-6)
    assert_centre_gates(whole, lake)


def test_variable_simplification_keeps_each_vertex_within_its_own_room():
    line = np.c_[np.linspace(0, 100, 101), np.sin(np.linspace(0, 6, 101)) * 3]
    room = np.where(line[:, 0] < 50, 0.05, 2.0)
    kept = pg.simplify_within(line, room)
    simplified = LineString(line[kept])
    distances = shapely.distance(shapely.points(line), simplified)
    assert (distances <= room + 1e-9).all()
    assert kept[0] == 0 and kept[-1] == len(line) - 1
    assert len(kept) < len(line)


def test_a_gap_a_hair_narrower_than_twice_the_offset_keeps_its_line_and_both_islands_their_ways():
    # Two islands 29.9 m apart: the middle runs at 14.95 m, 5 cm under d, which the samples
    # alone would put above d. The clip reads the exact distance to the bank.
    one, other = at(100, 170, 160, 230), at(189.9, 170, 249.9, 230)
    lake = at(0, 0, 400, 400).difference(shapely.union(one, other))
    result = pg.contours(bodies(lake), crs=CRS)
    gap = result.centre[result.centre.geometry.intersects(at(165, 175, 185, 225))]
    assert len(gap) and set(gap["category"]) == {pg.PASSAGE}
    assert abs(shapely.get_coordinates(gap.geometry.intersection(at(165, 180, 185, 220)).to_numpy())[:, 0] - (X0 + 174.95)).max() < 0.05
    network = shapely.union_all(np.asarray([*result.lines.geometry, *result.centre.geometry], dtype=object))
    faces = shapely.get_parts(shapely.polygonize(shapely.get_parts(network)))
    for island in (one, other):
        holding = [f for f in faces if f.contains(island.representative_point())]
        assert len(holding) == 1 and not holding[0].intersects((other if island is one else one).representative_point())
    assert not (result.failures["kind"].isin(["join", "middle", "dry", "isolated"])).any()
    assert_centre_gates(result, lake)


def test_a_river_joined_through_a_pinch_narrower_than_a_step_is_one_centre_line():
    # Two reaches of a 20 m river meet through a neck 6 cm wide: the samples there are a metre apart,
    # so their diagram crosses the bank; the middle is refined and tied through, not left in pieces.
    river = shapely.union_all([at(0, 0, 300, 20), at(300, 9.97, 300.5, 10.03), at(300.5, 0, 600, 20)])
    result = pg.contours(bodies(river), crs=CRS)
    assert len(result.vanished) == 1
    adjacency, _ = graph(result.centre)
    assert len(reachable(adjacency, next(iter(adjacency)))) == len(adjacency)
    xs = shapely.get_coordinates(result.centre.geometry.to_numpy())[:, 0] - X0
    assert xs.min() < 1 and xs.max() > 599
    assert not (result.failures["kind"].isin(["middle", "dry", "isolated"])).any()


def test_the_exact_distance_from_a_line_is_the_one_its_segment_tree_returns():
    # The validation reads a run's distance through its segments' envelopes and GEOS's own formula;
    # it must be the tree's figure bit for bit, on vertices, on segments and beside repeated vertices.
    rng = np.random.default_rng(12)
    steps = rng.normal(0, 1.5, (400, 2))
    steps[::37] = 0.0
    run = np.cumsum(steps, axis=0) + [X0, Y0]
    points = run[rng.integers(0, len(run), 2000)] + rng.normal(0, 3, (2000, 2))
    points[:50] = run[:50]
    points[50:100] = (run[:50] + run[1:51]) / 2
    (_, _), expected = shapely.STRtree(shapely.linestrings(np.stack([run[:-1], run[1:]], axis=1))).query_nearest(
        shapely.points(points), return_distance=True, all_matches=False
    )
    found = pg._SegmentIndex.of(run).distance(points, rng.integers(0, len(run) - 1, len(points)))
    assert np.array_equal(found.view(np.int64), expected.view(np.int64))


def test_the_water_of_a_cell_answers_as_the_whole_body_does():
    # A wavy lake of 20,000 vertices; short lines ending on its bank are asked of their cells,
    # long ones of the whole body; distances within a cell's margin come from the cell.
    angle = np.linspace(0, 2 * np.pi, 20_001)[:-1]
    radius = 3000 + 40 * np.sin(angle * 300)
    lake = Polygon(np.c_[X0 + radius * np.cos(angle), Y0 + radius * np.sin(angle)])
    shapely.prepare(lake)
    local = pg._local(lake)
    bank = shapely.get_coordinates(lake.exterior)[:-1]
    inward = bank + (np.c_[X0, Y0] - bank) * 0.004
    outward = bank - (np.c_[X0, Y0] - bank) * 0.004
    lines = np.asarray(
        [*shapely.linestrings(np.stack([inward, bank], axis=1))[::7], *shapely.linestrings(np.stack([outward, bank], axis=1))[::11]], dtype=object
    )
    lines = np.append(lines, LineString([bank[0], bank[5000]]))
    assert np.array_equal(local.covers(lines), shapely.covers(lake, lines))
    points = np.asarray(shapely.points(np.r_[outward[::13], inward[::17], [[X0 + 5000.0, Y0]]]), dtype=object)
    assert np.array_equal(local.distance(points), shapely.distance(points, lake))


# Phase 12d: the last metres from the bank to the line.


def contacts(*points: Point, roles: str = "launch", anchors: list[int] | None = None, surface: bool = True) -> gpd.GeoDataFrame:
    """Contacts as 12a's inventory names them; each is also the anchor of that index unless told otherwise."""
    return gpd.GeoDataFrame(
        {"roles": [roles] * len(points), "surface": [surface] * len(points), "anchor": anchors if anchors is not None else list(range(len(points)))},
        geometry=list(points),
        crs=CRS,
    )


def only_lines(*lines: LineString) -> pg.Contours:
    """A contour result holding nothing but the given lines, as if every centre branch near them were pruned."""
    frame = gpd.GeoDataFrame(
        {
            "body": [0] * len(lines),
            "start": [pg.RING] * len(lines),
            "end": [pg.RING] * len(lines),
            water.LAKE_BODY: ["lake-0"] * len(lines),
            "raw": list(lines),
        },
        geometry=list(lines),
        crs=CRS,
    )
    empty = gpd.GeoDataFrame({"body": [], "start": [], "end": [], water.LAKE_BODY: [], "raw": []}, geometry=[], crs=CRS)
    anchors = gpd.GeoDataFrame({"anchor": [], "body": [], "kept": []}, geometry=[], crs=CRS)
    blank = gpd.GeoDataFrame(geometry=[], crs=CRS)
    return pg.Contours(frame, blank, blank, pd.DataFrame(), blank, empty, blank, blank, anchors, CRS)


def assert_in_water(landed: pg.Landings, water_area) -> None:
    """No spur, mouth join or link lies over land beyond its anchor's bank step, before or after the page's grid."""
    for frame in (landed.spurs, landed.mouths, landed.links):
        drawn = frame[frame["source"].notna()]
        assert (drawn["bank_step_m"] <= pg.BANK_STEP_M).all()
        assert (drawn["stray_m"] <= pg.EXCURSION_M).all() and (drawn["decoded_stray_m"] <= pg.EXCURSION_M).all()
        for line, step in zip(drawn.geometry, drawn["bank_step_m"], strict=True):
            assert shapely.difference(line, water_area).length <= step + 0.1


def test_a_launch_25_m_from_the_bank_keeps_its_land_reach_and_gains_its_water_spur():
    from trails.network.launches import launches
    from trails.routing.graph import build_network
    from trails.routing.sources import NetworkSource

    lake = at(0, 0, 400, 200)
    surfaces = gpd.GeoDataFrame(geometry=[lake], crs=CRS)
    paddled = water.paddle(surfaces, metric_crs=CRS)
    road = NetworkSource("road", gpd.GeoDataFrame(geometry=[LineString([(X0 + 200, Y0 - 100), (X0 + 200, Y0 - 25)])], crs=CRS))
    tie = launches(paddled.bank, build_network([road], bridge_m=0, metric_crs=CRS), water.Access(surfaces, bank=paddled.bank)).gdf
    # Phase 10's reach is to the bank: 25 m, well inside 30, though the line lies 40 m from the road end.
    assert len(tie) == 1 and tie.length.iloc[0] == pytest.approx(25)
    anchor = Point(tie.geometry.iloc[0].coords[-1])
    found = bodies(lake)
    landed = pg.landings(pg.contours(found, crs=CRS, anchors=np.array([anchor])), found, contacts(anchor), crs=CRS)
    spur = landed.spurs.iloc[0]
    assert (spur["route"], spur["source"], spur["target"]) == (pg.STRAIGHT, pg.LANDING_WATER, "contour")
    assert spur["length_m"] == pytest.approx(15, abs=0.1)
    # The water spur is added; the land part is the same tie, at the same path price.
    assert tie.geometry.iloc[0].equals(LineString([(X0 + 200, Y0 - 25), (X0 + 200, Y0)]))
    assert_in_water(landed, lake)


def test_a_two_ended_carry_keeps_its_land_part_and_gains_a_spur_at_each_end():
    from trails.routing.graph import build_network
    from trails.routing.sources import NetworkSource

    # A round lake beside a square one: the carry lands mid-bank on both, not at a corner, where a
    # kept corner branch of the middle would already reach the anchor.
    lakes = [at(0, 0, 200, 200), Point(X0 + 400, Y0 + 100).buffer(100, quad_segs=64)]
    surfaces = gpd.GeoDataFrame(geometry=lakes, crs=CRS)
    paddled = water.paddle(surfaces, metric_crs=CRS)
    walking = build_network([NetworkSource("path", gpd.GeoDataFrame(geometry=[], crs=CRS))], metric_crs=CRS)
    chord = water.portages(paddled.bank, walking)[0].gdf.geometry.iloc[0]
    assert chord.length == pytest.approx(100)
    ends = [Point(chord.coords[0]), Point(chord.coords[-1])]
    found = bodies(*lakes)
    landed = pg.landings(pg.contours(found, crs=CRS, anchors=np.array(ends)), found, contacts(*ends, roles="portage"), crs=CRS)
    assert list(landed.spurs["route"]) == [pg.STRAIGHT, pg.STRAIGHT]
    # 15 m; on the round lake the 2 m contour's chord between two kept vertices lies 0.196 m farther in.
    assert landed.spurs["length_m"].to_numpy() == pytest.approx([15, 15], abs=0.25)
    assert landed.spurs["body"].nunique() == 2
    # Each spur starts at its end of the carry: the carry is not lengthened, the spurs are paddled.
    for spur, end in zip(landed.spurs.geometry, ends, strict=True):
        assert Point(spur.coords[0]).distance(end) < 0.07
    assert water.portages(paddled.bank, walking)[0].gdf.geometry.iloc[0].equals(chord)
    assert_in_water(landed, shapely.union_all(lakes))


def test_an_inlet_reaches_its_own_centre_line_or_bends_round_its_corner():
    lake = at(0, 0, 300, 300)
    inlet = shapely.union_all([at(300, 140, 380, 160), at(360, 160, 380, 260)])
    water_area = shapely.union_all([lake, inlet])
    anchor = Point(X0 + 370, Y0 + 260)
    found = bodies(water_area)
    landed = pg.landings(pg.contours(found, crs=CRS, anchors=np.array([anchor])), found, contacts(anchor), crs=CRS)
    spur = landed.spurs.iloc[0]
    # The inlet's own middle, never the lake's line across the land between them.
    assert spur["target"] in ("node", "centre") and spur["length_m"] < 15
    assert_in_water(landed, water_area)
    # With no middle in the inlet, the straight line to the lake's contour crosses land: the spur bends round the corner.
    contour = at(15, 15, 285, 285).exterior
    alone = pg.landings(only_lines(contour), found, contacts(anchor, anchors=[-1]), crs=CRS)
    bent = alone.spurs.iloc[0]
    assert bent["route"] == pg.BENT
    assert shapely.get_num_coordinates(bent.geometry) > 2
    assert shapely.shortest_line(anchor, contour).difference(water_area).length > 10
    assert_in_water(alone, water_area)


def test_an_anchor_behind_an_island_goes_round_it_and_never_across():
    island = at(150, 5, 250, 60)
    lake = Polygon(at(0, 0, 400, 300).exterior.coords, holes=[island.exterior.coords])
    anchor = Point(X0 + 200, Y0)
    target = LineString([(X0 + 100, Y0 + 80), (X0 + 300, Y0 + 80)])
    found = bodies(lake)
    landed = pg.landings(only_lines(target), found, contacts(anchor, anchors=[-1]), crs=CRS)
    spur = landed.spurs.iloc[0]
    assert shapely.shortest_line(anchor, target).intersects(island)
    assert spur["route"] == pg.BENT and not spur.geometry.crosses(island) and spur.geometry.intersection(island).length < 0.1
    assert_in_water(landed, lake)


def test_a_stream_mouth_joins_its_own_body_and_leaves_both_directions_as_phase_7_decided():
    from trails.routing.elevation import with_elevation
    from trails.routing.graph import build_network
    from trails.routing.sources import PADDLE, NetworkSource

    lakes = [at(0, 0, 300, 300), at(500, 0, 800, 300)]
    # A falling stream into the west lake that stops at its bank, and a level channel between the two lakes.
    falling = LineString([(X0 + 150, Y0 - 300), (X0 + 150, Y0)])
    channel = LineString([(X0 + 300, Y0 + 150), (X0 + 500, Y0 + 150)])
    found = bodies(*lakes)
    landed = pg.landings(
        pg.contours(found, crs=CRS), found, contacts(Point(X0 + 150, Y0), roles="mouth", anchors=[-1]), crs=CRS, streams=np.array([falling, channel])
    )
    mouths = landed.mouths
    assert sorted(mouths["kind"]) == [pg.MOUTH_KIND] * 3
    assert (mouths["source"] == pg.LANDING_WATER).all() and mouths["length_m"].to_numpy() == pytest.approx([15, 15, 15], abs=0.1)
    assert landed.spurs.iloc[0]["route"] == pg.AT_MOUTH
    joins = gpd.GeoDataFrame(geometry=list(mouths.geometry), crs=CRS)

    def decisions(extra: list[NetworkSource]) -> dict[str, bool]:
        streams = NetworkSource(water.STREAMS, gpd.GeoDataFrame(geometry=[falling, channel], crs=CRS), kind=PADDLE, directed=True, keep_whole=True)
        # The stream falls 0.1 m in every metre toward the lake; the channel is level.
        network = with_elevation(
            build_network([streams, *extra], metric_crs=CRS, bridge_m=0), lambda xy: np.where(xy[:, 1] < Y0, -(xy[:, 1] - Y0) * 0.1, 0.0)
        )
        opened = water.open_level_streams(network).edges
        own = opened[opened["source"] == water.STREAMS]
        return {
            "falling": bool(own.loc[own.geometry.bounds["maxy"] <= Y0 + 1e-6, "one_way"].all()),
            "channel": bool(own.loc[own.geometry.bounds["miny"] > Y0, "one_way"].any()),
        }

    alone = decisions([])
    joined = decisions([NetworkSource(pg.LANDING_WATER, joins, kind=PADDLE, keep_whole=True)])
    assert alone == joined == {"falling": True, "channel": False}
    assert_in_water(landed, shapely.union_all(lakes))


def test_a_lake_owned_interface_is_kept_once_at_the_lake_plane_and_met_on_both_sides():
    lake, river = at(0, 0, 300, 300), at(300, 130, 600, 170)
    found = bodies(lake, river, classes=["lake", "river"], levels=["207", None])
    landed = pg.landings(pg.contours(found, crs=CRS), found, contacts(), crs=CRS)
    interfaces = landed.interfaces
    assert len(interfaces) == 1
    row = interfaces.iloc[0]
    assert row.geometry.equals(LineString([(X0 + 300, Y0 + 130), (X0 + 300, Y0 + 170)])) or row.geometry.equals(
        LineString([(X0 + 300, Y0 + 170), (X0 + 300, Y0 + 130)])
    )
    assert row[water.LAKE_LEVEL] == 207 and row[water.LAKE_BODY] is not None
    # The contour crosses it once on each bank, from each side: four ends, no link needed, no river copy.
    assert (row["lake_side"], row["other_side"]) == (2, 2) and landed.links.empty
    assert len(shapely.get_parts(row["meets"])) == 4


def test_a_dam_blocks_every_spur_and_its_side_keeps_its_landing():
    lakes_and_river = shapely.union_all([at(0, 0, 300, 300), at(300, 120, 700, 180), at(700, 0, 1000, 300)])
    dam = Point(X0 + 500, Y0 + 150)
    # A carry's landing on each side of the disc, on its circle 8 m off the bank, as phase 9's cut leaves them.
    side = float(np.sqrt(water.DAM_CUT_M**2 - 22.0**2))
    ends = [Point(X0 + 500 - side, Y0 + 128), Point(X0 + 500 + side, Y0 + 128)]
    found = bodies(lakes_and_river)
    result = pg.contours(found, crs=CRS, dams=np.array([dam]), anchors=np.array(ends))
    landed = pg.landings(result, found, contacts(*ends, roles="portage,dam_side"), crs=CRS, dams=np.array([dam]))
    spurs = landed.spurs
    assert len(spurs) == 2 and spurs["source"].eq(pg.LANDING_WATER).all()
    assert (spurs["dam_clearance_m"] >= water.DAM_CUT_M).all()
    for spur, end in zip(spurs.geometry, ends, strict=True):
        # Its own side: the spur never passes the dam, and nothing of it enters the disc.
        assert shapely.distance(spur, dam) >= water.DAM_CUT_M - 1e-6
        assert (shapely.get_coordinates(spur)[:, 0] - dam.x).mean() * (end.x - dam.x) > 0
    assert_in_water(landed, lakes_and_river)


def test_no_spur_link_or_mouth_join_lies_over_land():
    island = at(120, 120, 180, 180)
    lake = Polygon(at(0, 0, 300, 300).exterior.coords, holes=[island.exterior.coords])
    river = at(300, 130, 600, 170)
    found = bodies(lake, river, classes=["lake", "river"], levels=["207", None])
    stream = LineString([(X0 + 450, Y0 + 400), (X0 + 450, Y0 + 170)])
    points = [Point(X0 + 150, Y0), Point(X0 + 150, Y0 + 120), Point(X0 + 450, Y0 + 130), Point(X0 + 0, Y0 + 290), Point(X0 + 450, Y0 + 170)]
    result = pg.contours(found, crs=CRS, anchors=np.array(points))
    landed = pg.landings(result, found, contacts(*points, roles="walking_bank"), crs=CRS, streams=np.array([stream]))
    assert landed.failures.empty
    assert landed.spurs["source"].eq(pg.LANDING_WATER).all() and len(landed.mouths) == 1
    assert_in_water(landed, shapely.union_all([lake, river]))


def test_a_round_lake_the_offset_carries_everywhere_needs_no_middle():
    # No corner, no closed-off water, no jump: the middle has nothing to look for, and must not fail.
    result = pg.contours(bodies(Point(X0 + 400, Y0 + 100).buffer(100, quad_segs=64)), crs=CRS)
    assert len(result.lines) == 1 and result.centre.empty
    assert_gates(result)


def test_a_contact_out_in_the_lake_reaches_the_line_across_open_water_not_landing_water():
    # A path's end on a skerry the lake does not cut out, 60 m from any bank: not the last metres from a bank.
    lake = at(0, 0, 400, 300)
    found = bodies(lake)
    near_bank, far_out = Point(X0 + 200, Y0), Point(X0 + 200, Y0 + 60)
    result = pg.contours(found, crs=CRS, anchors=np.array([near_bank, far_out]))
    landed = pg.landings(result, found, contacts(near_bank, far_out, roles="bridge_land"), crs=CRS)
    assert list(landed.spurs["source"]) == [pg.LANDING_WATER, water.OPEN_WATER]
    assert landed.spurs["length_m"].to_numpy() == pytest.approx([15, 45], abs=0.1)
