"""The line off the bank: offset contours, their cuts and their gates."""

import geopandas as gpd
import numpy as np
import pytest
import shapely
from shapely.geometry import LineString, Point, box
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
