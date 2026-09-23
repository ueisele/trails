"""Closing belongs to the drawing, not to the protected-area calculation."""

import geopandas as gpd
import pytest
from shapely import MultiPolygon, Point, Polygon, box
from trails.visualization.boundary import close_for_display


def test_closed_and_open_seams_go_but_real_holes_and_components_stay() -> None:
    outer = box(500000, 6600000, 500100, 6600100)
    hole = box(500020, 6600020, 500030, 6600030)
    seam = box(500050, 6600020, 500050.5, 6600080)
    inlet = box(500070, 6600050, 500070.5, 6600101)
    area = outer.difference(hole.union(seam).union(inlet))
    island = box(500200, 6600000, 500210, 6600010)
    frame = gpd.GeoDataFrame({"name": ["Counties together"]}, geometry=[MultiPolygon([area, island])], crs=3006, index=[7])
    before = frame.geometry.iloc[0].wkb

    drawn = close_for_display(frame, "EPSG:3006", source_records=3)

    expected = MultiPolygon([Polygon(outer.exterior, [hole.exterior]), island])
    assert drawn.geometry.iloc[0].equals(expected)
    assert frame.geometry.iloc[0].wkb == before
    assert drawn.index.equals(frame.index)
    assert drawn["name"].equals(frame["name"])
    assert drawn.crs == frame.crs


@pytest.mark.parametrize("metric_crs", ["EPSG:3006", "EPSG:25833"])
def test_geographic_input_is_closed_in_metres_and_keeps_its_crs(metric_crs: str) -> None:
    area = box(500000, 6600000, 500100, 6600100).difference(box(500050, 6600020, 500050.5, 6600080))
    frame = gpd.GeoDataFrame(geometry=[area], crs=metric_crs).to_crs(4326)
    before = frame.geometry.iloc[0].wkb

    drawn = close_for_display(frame, metric_crs, source_records=2)

    assert drawn.crs == frame.crs
    assert len(drawn.geometry.iloc[0].interiors) == 0
    assert drawn.to_crs(metric_crs).geometry.iloc[0].hausdorff_distance(box(500000, 6600000, 500100, 6600100)) < 0.000001
    assert frame.geometry.iloc[0].wkb == before


def test_an_empty_frame_keeps_its_columns_and_crs() -> None:
    frame = gpd.GeoDataFrame({"name": []}, geometry=[], crs=4326)
    drawn = close_for_display(frame, "EPSG:3006", source_records=3)
    assert drawn.empty
    assert drawn.columns.equals(frame.columns)
    assert drawn.crs == frame.crs


@pytest.mark.parametrize("metric_crs", ["EPSG:4326", "EPSG:2263"])
def test_degrees_and_feet_are_not_a_metric_tolerance(metric_crs: str) -> None:
    frame = gpd.GeoDataFrame(geometry=[box(15, 59, 16, 60)], crs=4326)
    with pytest.raises(ValueError, match="projected in metres"):
        close_for_display(frame, metric_crs, source_records=2)


def test_an_undeclared_crs_is_not_assumed() -> None:
    with pytest.raises(ValueError, match="declare its CRS"):
        close_for_display(gpd.GeoDataFrame(geometry=[box(0, 0, 10, 10)]), "EPSG:3006", source_records=2)


def test_a_point_is_not_silently_buffered_into_a_boundary() -> None:
    with pytest.raises(ValueError, match="contain polygons"):
        close_for_display(gpd.GeoDataFrame(geometry=[Point(15, 60)], crs=4326), "EPSG:3006", source_records=2)


@pytest.mark.parametrize("crs", ["EPSG:4326", "EPSG:3006"])
def test_a_single_record_is_not_reprojected_or_closed(crs: str) -> None:
    area = box(500000, 6600000, 500100, 6600100).difference(box(500050, 6600020, 500050.5, 6600080))
    frame = gpd.GeoDataFrame({"name": ["One record"]}, geometry=[area], crs=3006).to_crs(crs)
    before = frame.geometry.iloc[0].wkb
    drawn = close_for_display(frame, "EPSG:3006", source_records=1)
    assert drawn is not frame
    assert drawn.geometry.iloc[0].wkb == before
    assert drawn.to_json() == frame.to_json()
    assert len(drawn.geometry.iloc[0].interiors) == 1


def test_a_record_count_cannot_be_empty() -> None:
    frame = gpd.GeoDataFrame(geometry=[box(15, 59, 16, 60)], crs=4326)
    with pytest.raises(ValueError, match="at least one source record"):
        close_for_display(frame, "EPSG:3006", source_records=0)
