"""Tests for Folium map building."""

import pathlib
import re

import folium
import geopandas as gpd
import pytest
from shapely.geometry import LineString, MultiLineString, Point, Polygon
from trails.routing.sources import BRIDGE, FERRY
from trails.visualization import maps


@pytest.fixture
def trails() -> gpd.GeoDataFrame:
    """Two trail segments, one of them a MultiLineString."""
    return gpd.GeoDataFrame(
        {
            "trail_name": ["Sjøbergmarsjen", None],
            "difficulty": ["Easy (Green)", None],
            "geometry": [
                LineString([(12.8, 65.4), (12.81, 65.41)]),
                MultiLineString([[(12.9, 65.5), (12.91, 65.51)], [(12.92, 65.52), (12.93, 65.53)]]),
            ],
        },
        crs="EPSG:4326",
    )


@pytest.fixture
def park() -> gpd.GeoDataFrame:
    """A square park boundary."""
    return gpd.GeoDataFrame(
        {"navn": ["Lomsdal-Visten"], "geometry": [Polygon([(12.4, 65.3), (13.3, 65.3), (13.3, 65.7), (12.4, 65.7)])]},
        crs="EPSG:4326",
    )


@pytest.fixture
def shelters() -> gpd.GeoDataFrame:
    """Two point features."""
    return gpd.GeoDataFrame(
        {"name": ["Stavassgården", None], "kind": ["wilderness_hut", "shelter"], "geometry": [Point(12.85, 65.45), Point(12.86, 65.46)]},
        crs="EPSG:4326",
    )


class TestCreateMap:
    """Tests for create_map."""

    def test_centers_on_bounds(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        assert fmap.location == [65.5, 12.9]

    def test_accepts_explicit_center(self):
        fmap = maps.create_map(center=(65.5, 12.9))
        assert fmap.location == [65.5, 12.9]

    def test_requires_bounds_or_center(self):
        with pytest.raises(ValueError, match="bounds or center"):
            maps.create_map()

    def test_uses_kartverket_tiles_by_default(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        assert "cache.kartverket.no" in fmap.get_root().render()

    def test_adds_extra_base_layers(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7), extra_bases=(maps.BaseMap.OPENSTREETMAP,))
        tile_layers = [child for child in fmap._children.values() if isinstance(child, folium.TileLayer)]
        assert len(tile_layers) == 2

    def test_base_layers_are_named_not_labelled_with_urls(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7), extra_bases=(maps.BaseMap.KARTVERKET_GRAYSCALE,))
        tile_layers = [child for child in fmap._children.values() if isinstance(child, folium.TileLayer)]

        names = sorted(layer.layer_name for layer in tile_layers)
        assert names == ["Kartverket Grayscale", "Kartverket Topo"]

    def test_only_the_primary_base_is_displayed_on_load(self):
        # Leaflet stacks every base layer it is given, so a visible extra would
        # cover the primary one entirely.
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7), extra_bases=(maps.BaseMap.OPENSTREETMAP,))
        tile_layers = [child for child in fmap._children.values() if isinstance(child, folium.TileLayer)]

        shown = [layer for layer in tile_layers if layer.show]
        assert len(shown) == 1
        assert "kartverket" in shown[0].tiles.lower()

    def test_openstreetmap_is_not_a_default_extra(self):
        # OSM tiles 403 on file:// URLs because no Referer is sent.
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        rendered = fmap.get_root().render()
        assert "tile.openstreetmap.org" not in rendered

    def test_does_not_duplicate_the_primary_base(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7), base=maps.BaseMap.OPENSTREETMAP, extra_bases=(maps.BaseMap.OPENSTREETMAP,))
        tile_layers = [child for child in fmap._children.values() if isinstance(child, folium.TileLayer)]
        assert len(tile_layers) == 1


class TestPopup:
    """Tests for popup rendering."""

    def test_skips_missing_and_empty_values(self, trails):
        html = maps._build_popup(trails.iloc[0], {"trail_name": "Route", "absent": "Absent"})
        assert "Sjøbergmarsjen" in html
        assert "Absent" not in html

    def test_returns_none_when_nothing_populated(self, trails):
        assert maps._build_popup(trails.iloc[1], {"trail_name": "Route", "difficulty": "Difficulty"}) is None

    def test_shows_the_source_as_a_footer(self, trails):
        html = maps._build_popup(trails.iloc[0], {"trail_name": "Route"}, source="Turrutebasen")

        assert "Source: Turrutebasen" in html
        assert html.index("Sjøbergmarsjen") < html.index("Source:")

    def test_a_source_alone_is_enough_for_a_popup(self, trails):
        """A feature the source says nothing else about should still name it."""
        assert maps._build_popup(trails.iloc[1], {"trail_name": "Route"}, source="N50") is not None

    def test_without_a_source_nothing_is_appended(self, trails):
        html = maps._build_popup(trails.iloc[0], {"trail_name": "Route"})

        assert "Source:" not in html

    def test_source_is_escaped(self, trails):
        html = maps._build_popup(trails.iloc[0], {"trail_name": "Route"}, source="N50 <b>x</b>")

        assert "<b>x</b>" not in html

    def test_renders_link_fields_as_anchors(self, trails):
        row = trails.iloc[0].copy()
        row["ut_url"] = "https://ut.no/turforslag/1113860"

        html = maps._build_popup(row, {"trail_name": "Route"}, {"ut_url": "Open on ut.no"})

        assert 'href="https://ut.no/turforslag/1113860"' in html
        assert "Open on ut.no</a>" in html
        assert 'rel="noopener noreferrer"' in html

    def test_a_link_alone_is_enough_for_a_popup(self, trails):
        row = trails.iloc[1].copy()
        row["ut_url"] = "https://ut.no/turforslag/1"

        assert maps._build_popup(row, {}, {"ut_url": "Route"}) is not None

    def test_link_heading_is_written_once_above_the_links(self, trails):
        row = trails.iloc[0].copy()
        row["ut_url"] = "https://ut.no/turforslag/1"
        row["gpx_url"] = "https://ut.no/api/gpx/trip/1"

        html = maps._build_popup(
            row,
            {"trail_name": "Route"},
            {"ut_url": "Route page", "gpx_url": "Their GPX"},
            link_heading="Published elsewhere",
        )

        assert html.count("Published elsewhere") == 1
        assert html.index("Published elsewhere") < html.index("Route page")

    def test_no_link_heading_where_no_link_survives(self, trails):
        """A route with no description elsewhere must not get a heading over nothing."""
        row = trails.iloc[0].copy()
        row["guide_url_en"] = None

        html = maps._build_popup(
            row,
            {"trail_name": "Route"},
            {"guide_url_en": "Description"},
            link_heading="Published elsewhere",
        )

        assert "Published elsewhere" not in html

    def test_escapes_the_link_heading(self, trails):
        row = trails.iloc[0].copy()
        row["ut_url"] = "https://ut.no/turforslag/1"

        html = maps._build_popup(row, {"trail_name": "Route"}, {"ut_url": "Route page"}, link_heading="a <b>heading</b>")

        assert "<b>heading</b>" not in html

    def test_skips_missing_link_values(self, trails):
        row = trails.iloc[0].copy()
        row["guide_url_en"] = None

        html = maps._build_popup(row, {"trail_name": "Route"}, {"guide_url_en": "Description", "absent": "Absent"})

        assert "<a " not in html

    def test_rejects_non_http_links(self, trails):
        """A URL from a data file must not be able to run script on click."""
        row = trails.iloc[0].copy()
        row["ut_url"] = "javascript:alert(1)"

        html = maps._build_popup(row, {"trail_name": "Route"}, {"ut_url": "Open"})

        assert "javascript:" not in html

    def test_link_url_is_escaped(self, trails):
        row = trails.iloc[0].copy()
        row["ut_url"] = 'https://ut.no/x?a=1"><script>alert(1)</script>'

        html = maps._build_popup(row, {"trail_name": "Route"}, {"ut_url": "Open"})

        assert "<script>" not in html
        assert "&quot;&gt;&lt;script&gt;" in html


class TestLabelledPoints:
    """Tests for add_labelled_points."""

    def test_a_click_opens_a_popup_when_fields_are_given(self, shelters):
        """Without one the dot is interactive but answers nothing, which reads as broken."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_labelled_points(fmap, shelters, name="Places [SSR]", popup_fields={"name": "Name"}, source="SSR")

        markers = [child for child in group._children.values() if isinstance(child, folium.CircleMarker)]
        popups = [c for m in markers for c in m._children.values() if isinstance(c, folium.Popup)]
        assert len(popups) == 1

    def test_the_popup_names_its_source(self, shelters):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_labelled_points(fmap, shelters, name="Places [SSR]", popup_fields={"name": "Name"}, source="SSR")

        assert "Source: SSR" in fmap.get_root().render()

    def test_without_popup_fields_only_the_tooltip_remains(self, shelters):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_labelled_points(fmap, shelters, name="Places")

        markers = [child for child in group._children.values() if isinstance(child, folium.CircleMarker)]
        popups = [c for m in markers for c in m._children.values() if isinstance(c, folium.Popup)]
        assert not popups

    def test_labels_are_recorded_for_the_search(self, shelters):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_labelled_points(fmap, shelters, name="Places")

        assert "Stavassgården" in getattr(group, maps.SEARCH_NAMES_ATTR).values()


class TestClickHighlight:
    """Tests for add_click_highlight."""

    def test_it_can_be_let_go_of_without_a_click(self, trails):
        """Both of its ways out are clicks -- on the line, or on empty ground --
        and something else can own those. Plan mode does, so the highlight needs
        a way in that is not a click or it dims the map with no way back.
        """
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="Paths", color="#1b5e20")
        maps.add_click_highlight(fmap, [group])

        html = fmap.get_root().render()

        assert "window.trailsHighlight = {" in html
        assert "clear: clear," in html
        assert "selected: function () { return selected; }" in html

    def test_renders_after_the_layers_it_drives(self, trails):
        """The snippet names the feature groups, so they must exist by then."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="UT.no", group_field="trail_name")
        maps.add_click_highlight(fmap, [group])

        html = fmap.get_root().render()
        assert html.index(f"var {group.get_name()} = L.featureGroup") < html.index(f"var groups = [{group.get_name()}]")

    def test_uses_the_given_boost_and_dimming(self, trails):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="UT.no", group_field="trail_name")
        maps.add_click_highlight(fmap, [group], weight_boost=6.0, dim_opacity=0.3)

        html = fmap.get_root().render()
        assert "var boost = 6.0;" in html
        assert "var dim = 0.3;" in html

    def test_without_groups_nothing_is_added(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_click_highlight(fmap, [])

        assert "var groups = [" not in fmap.get_root().render()


class TestAddTrails:
    """Tests for add_trails."""

    def test_adds_one_polyline_per_line_part(self, trails):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="Turrutebasen")

        polylines = [child for child in group._children.values() if isinstance(child, folium.PolyLine)]
        # One plain LineString plus two parts of the MultiLineString.
        assert len(polylines) == 3

    def test_tooltip_field_labels_each_line(self, trails):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="UT.no", tooltip_field="trail_name")

        polyline = next(child for child in group._children.values() if isinstance(child, folium.PolyLine))
        tooltip = next(child for child in polyline._children.values() if isinstance(child, folium.Tooltip))
        assert tooltip.text == "Sjøbergmarsjen"

    def test_source_reaches_every_popup(self, trails):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="Paths [N50]", popup_fields={"trail_name": "Route"}, source="N50")

        lines = [child for child in group._children.values() if isinstance(child, folium.PolyLine)]
        popups = [c for line in lines for c in line._children.values() if isinstance(c, folium.Popup)]
        # Every drawn line gets one, including the row with no populated field.
        assert len(popups) == len(lines) == 3

    def test_link_fields_reach_the_popup(self, trails):
        gdf = trails.copy()
        gdf["ut_url"] = "https://ut.no/turforslag/1113860"
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))

        maps.add_trails(fmap, gdf, name="UT.no", link_fields={"ut_url": "Open on ut.no"})

        assert "ut.no/turforslag/1113860" in fmap.get_root().render()

    def test_group_field_marks_every_part_of_one_route(self, trails):
        gdf = trails.copy()
        gdf["trip_id"] = [1113860, 116015]
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))

        group = maps.add_trails(fmap, gdf, name="UT.no", group_field="trip_id")

        classes = [child.options["className"] for child in group._children.values() if isinstance(child, folium.PolyLine)]
        # The second route is a MultiLineString: both its parts carry one class.
        assert classes == ["trail-group-1113860", "trail-group-116015", "trail-group-116015"]

    def test_group_value_is_reduced_to_a_css_token(self, trails):
        gdf = trails.copy()
        gdf["route"] = ["Tverådalen - Bønå", "x"]
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))

        group = maps.add_trails(fmap, gdf, name="UT.no", group_field="route")

        polyline = next(child for child in group._children.values() if isinstance(child, folium.PolyLine))
        assert polyline.options["className"].startswith("trail-group-Tver-dalen---B-n--")

    def test_names_that_flatten_alike_stay_distinct(self):
        """Without the digest both of these would become one selection."""
        assert maps._group_class("Bønå") != maps._group_class("Bønö")

    def test_plain_ids_are_not_given_a_digest(self):
        assert maps._group_class(1113860) == "trail-group-1113860"

    def test_a_whole_float_id_matches_the_integer(self):
        """One null in the column turns the whole thing into floats."""
        assert maps._group_class(1113860.0) == maps._group_class(1113860)

    def test_rows_without_a_group_value_get_no_class(self, trails):
        gdf = trails.copy()
        gdf["trip_id"] = [1113860, None]
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))

        group = maps.add_trails(fmap, gdf, name="UT.no", group_field="trip_id")

        classes = [child.options.get("className") for child in group._children.values() if isinstance(child, folium.PolyLine)]
        assert classes == ["trail-group-1113860", None, None]

    def test_layer_name_includes_feature_count(self, trails):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="Turrutebasen")
        assert group.layer_name == "Turrutebasen (2)"

    def test_reprojects_to_wgs84(self, trails):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        metric = trails.to_crs("EPSG:25833")
        group = maps.add_trails(fmap, metric, name="Turrutebasen")

        polyline = next(child for child in group._children.values() if isinstance(child, folium.PolyLine))
        lat, lon = polyline.locations[0]
        assert 65.0 < lat < 66.0
        assert 12.0 < lon < 14.0

    def test_dash_array_is_passed_through(self, trails):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="Ferries", dash_array="10,7")

        polyline = next(child for child in group._children.values() if isinstance(child, folium.PolyLine))
        assert polyline.options["dashArray"] == "10,7"

    def test_solid_by_default(self, trails):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="Trails")

        polyline = next(child for child in group._children.values() if isinstance(child, folium.PolyLine))
        assert polyline.options.get("dashArray") is None

    def test_skips_empty_geometries(self):
        gdf = gpd.GeoDataFrame({"geometry": [None, LineString([(12.8, 65.4), (12.81, 65.41)])]}, crs="EPSG:4326")
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, gdf, name="Trails")

        polylines = [child for child in group._children.values() if isinstance(child, folium.PolyLine)]
        assert len(polylines) == 1


class TestAddPoints:
    """Tests for add_points."""

    def test_adds_one_marker_per_point(self, shelters):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_points(fmap, shelters, name="Huts")

        markers = [child for child in group._children.values() if isinstance(child, folium.Marker)]
        assert len(markers) == 2

    def test_uses_label_field_as_tooltip(self, shelters):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_points(fmap, shelters, name="Huts")

        markers = [child for child in group._children.values() if isinstance(child, folium.Marker)]
        tooltips = [next((c for c in marker._children.values() if isinstance(c, folium.Tooltip)), None) for marker in markers]
        assert tooltips[0] is not None
        assert tooltips[0].text == "Stavassgården"
        # The second shelter has no name, so it gets no tooltip.
        assert tooltips[1] is None


class TestNamedPoints:
    """Tests for the table a waypoint takes its name from.

    The markers themselves cannot answer *what is at this position*: their names
    are inside the popup HTML they were given, which is markup and not a lookup.
    """

    @pytest.fixture
    def huts(self) -> gpd.GeoDataFrame:
        """A named hut and an unnamed one."""
        return gpd.GeoDataFrame(
            {"name": ["Lavasshytta", None], "geometry": [Point(12.98079, 65.77416), Point(12.9, 65.5)]},
            crs="EPSG:4326",
        )

    def test_a_layer_given_a_type_carries_what_it_draws(self, huts):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_points(fmap, huts, name="Huts", point_type="hut")

        assert getattr(group, maps.NAMED_POINTS_ATTR) == [{"name": "Lavasshytta", "type": "hut", "lat": 65.77416, "lon": 12.98079}]

    def test_a_layer_without_one_answers_nothing(self, huts):
        # Opt-in per layer: a place name drawn as text asserts no single
        # position — a valley has none — and a waypoint must not take one.
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_points(fmap, huts, name="Huts")

        assert getattr(group, maps.NAMED_POINTS_ATTR) == []

    def test_circles_carry_the_same_table_as_pins(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        farms = gpd.GeoDataFrame({"name": ["Strompdalen"], "geometry": [Point(13.05, 65.45)]}, crs="EPSG:4326")
        group = maps.add_labelled_points(fmap, farms, name="Farms", point_type="farm")

        assert getattr(group, maps.NAMED_POINTS_ATTR) == [{"name": "Strompdalen", "type": "farm", "lat": 65.45, "lon": 13.05}]

    def test_text_labels_never_carry_one(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        valleys = gpd.GeoDataFrame({"name": ["Lomsdalen"], "geometry": [Point(13.05, 65.45)]}, crs="EPSG:4326")
        group = maps.add_text_labels(fmap, valleys, name="Terrain names")

        assert not hasattr(group, maps.NAMED_POINTS_ATTR)


class TestAddLabelledPoints:
    """Tests for add_labelled_points."""

    @pytest.fixture
    def places(self) -> gpd.GeoDataFrame:
        """A town, a hamlet and an unnamed place."""
        return gpd.GeoDataFrame(
            {
                "name": ["Mosjøen", "Tverråga", None],
                "kind": ["town", "hamlet", "hamlet"],
                "geometry": [Point(13.19, 65.83), Point(13.17, 65.78), Point(12.9, 65.5)],
            },
            crs="EPSG:4326",
        )

    def test_skips_unlabelled_features(self, places):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_labelled_points(fmap, places, name="Places")

        circles = [child for child in group._children.values() if isinstance(child, folium.CircleMarker)]
        assert len(circles) == 2

    def test_always_label_makes_tooltip_permanent(self, places):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_labelled_points(fmap, places, name="Places", always_label=("town",))

        circles = [child for child in group._children.values() if isinstance(child, folium.CircleMarker)]
        tooltips = [next(c for c in circle._children.values() if isinstance(c, folium.Tooltip)) for circle in circles]
        assert tooltips[0].options["permanent"] is True
        assert tooltips[1].options["permanent"] is False

    def test_layer_name_includes_count(self, places):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_labelled_points(fmap, places, name="Places")
        assert group.layer_name == "Places (3)"


class TestAddTextLabels:
    """Tests for add_text_labels."""

    @pytest.fixture
    def names(self) -> gpd.GeoDataFrame:
        """Two named positions of one valley plus an unnamed row."""
        return gpd.GeoDataFrame(
            {
                "name": ["Eiterådalen", "Eiterådalen", None],
                "font_size": [12.0, 12.0, 10.0],
                "geometry": [Point(13.14, 65.67), Point(13.14, 65.60), Point(13.0, 65.5)],
            },
            crs="EPSG:4326",
        )

    def test_draws_one_label_per_position(self, names):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, names, name="Terrain names")

        markers = [child for child in group._children.values() if isinstance(child, folium.Marker)]
        # The repeated name is drawn at both of its positions; the unnamed row is skipped.
        assert len(markers) == 2

    def test_uses_a_div_icon_rather_than_a_marker_symbol(self, names):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, names, name="Terrain names")

        marker = next(child for child in group._children.values() if isinstance(child, folium.Marker))
        icon = next(child for child in marker._children.values() if isinstance(child, folium.DivIcon))
        # A zero-sized icon means no pin or circle is drawn, only the text.
        assert icon.options["icon_size"] == (0, 0)

    def test_renders_the_label_text(self, names):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, names, name="Terrain names")

        marker = next(child for child in group._children.values() if isinstance(child, folium.Marker))
        icon = next(child for child in marker._children.values() if isinstance(child, folium.DivIcon))
        assert "Eiterådalen" in icon.options["html"]

    def test_size_field_controls_the_font_size(self, names):
        gdf = names.copy()
        gdf.loc[0, "font_size"] = 17.5
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_text_labels(fmap, gdf, name="Terrain names", size_field="font_size")

        assert "font-size:17.5px" in fmap.get_root().render()

    def test_default_size_applies_without_a_size_field(self, names):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_text_labels(fmap, names, name="Terrain names", default_size=13)

        assert "font-size:13px" in fmap.get_root().render()


class TestAddBoundary:
    """Tests for add_boundary."""

    def test_adds_geojson_layer(self, park):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        layer = maps.add_boundary(fmap, park, name="Park")

        assert isinstance(layer, folium.GeoJson)
        assert layer.layer_name == "Park"


class TestAddRoutingGraph:
    """Tests for the routing graph the page carries but never draws."""

    def test_the_payload_and_its_header_reach_the_page(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_routing_graph(fmap, {"version": 1, "edges": 3}, "H4sIAAAAAAAA")

        html = fmap.get_root().render()
        assert '"edges": 3' in html
        assert '"H4sIAAAAAAAA"' in html
        assert "window.trailsGraph" in html

    def test_it_draws_nothing_and_joins_no_layer_control(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_routing_graph(fmap, {"version": 1, "edges": 0}, "")
        assert not [child for child in fmap._children.values() if isinstance(child, folium.GeoJson | folium.FeatureGroup)]

    def test_the_decoder_fetches_nothing(self):
        """A script pulled from a CDN does not load on a file:// page: it fails
        silently, the way the OpenStreetMap tiles once did."""
        bounds = (12.4, 65.3, 13.4, 65.7)
        plain = maps.create_map(bounds=bounds).get_root().render()

        fmap = maps.create_map(bounds=bounds)
        maps.add_routing_graph(fmap, {"version": 1, "edges": 0}, "")
        with_graph = fmap.get_root().render()

        assert with_graph.count("://") == plain.count("://")


class TestChainFigures:
    """Tests for the figures a line carries beside the layer it is drawn in."""

    @pytest.fixture
    def measured(self) -> gpd.GeoDataFrame:
        """Two chains, one of them with nothing read along it."""
        return gpd.GeoDataFrame(
            {
                "chain_id": ["ut-no-1-2-3", "ferries-4-5-6"],
                "ascent": [996.4, float("nan")],
                "descent": [850.2, float("nan")],
                "bearing_deg": [47.3, 12.0],
                "geometry": [
                    LineString([(12.8, 65.4), (12.81, 65.41)]),
                    LineString([(12.9, 65.5), (12.91, 65.51)]),
                ],
            },
            crs="EPSG:4326",
        )

    def fields(self) -> dict[str, str]:
        """The columns to carry, and the keys they travel under."""
        return {"ascent": "ascent", "descent": "descent", "bearing_deg": "bearing"}

    def test_figures_travel_beside_the_layer_keyed_by_the_class(self, measured):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, measured, name="Chains", group_field="chain_id", figure_fields=self.fields())

        figures = getattr(group, maps.CHAIN_FIGURES_ATTR)
        assert figures["trail-group-ut-no-1-2-3"]["ascent"] == pytest.approx(996.4)
        assert figures["trail-group-ut-no-1-2-3"]["bearing"] == pytest.approx(47.3)

    def test_a_figure_is_rounded_rather_than_carried_at_float_precision(self, measured):
        """17.339999999999996 is eleven thousand times over, for digits a tenth
        of a metre already exceeds."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        rough = measured.assign(ascent=[17.339999999999996, float("nan")])
        group = maps.add_trails(fmap, rough, name="Chains", group_field="chain_id", figure_fields=self.fields())

        assert getattr(group, maps.CHAIN_FIGURES_ATTR)["trail-group-ut-no-1-2-3"]["ascent"] == 17.3

    def test_a_label_travels_as_itself_rather_than_as_a_number(self, measured):
        """The compass point is a string and is carried, not re-derived."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        labelled = measured.assign(compass=["NE", None])
        group = maps.add_trails(fmap, labelled, name="Chains", group_field="chain_id", figure_fields={**self.fields(), "compass": "point"})

        figures = getattr(group, maps.CHAIN_FIGURES_ATTR)
        assert figures["trail-group-ut-no-1-2-3"]["point"] == "NE"
        assert figures["trail-group-ferries-4-5-6"]["point"] is None

    def test_each_entry_names_the_chain_it_is_about(self, measured):
        """A class is not an id: _group_class reshapes anything that is not a
        CSS token, so what the figures describe travels as a value."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, measured, name="Chains", group_field="chain_id", figure_fields=self.fields())

        figures = getattr(group, maps.CHAIN_FIGURES_ATTR)
        assert figures["trail-group-ut-no-1-2-3"][maps.FIGURE_ID_KEY] == "ut-no-1-2-3"

    def test_a_missing_figure_travels_as_null_rather_than_zero(self, measured):
        """A crossing has no ground under it. Zero would be a claim about it."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, measured, name="Chains", group_field="chain_id", figure_fields=self.fields())

        assert getattr(group, maps.CHAIN_FIGURES_ATTR)["trail-group-ferries-4-5-6"]["ascent"] is None

    def test_without_figure_fields_nothing_is_recorded(self, measured):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, measured, name="Chains", group_field="chain_id")

        assert getattr(group, maps.CHAIN_FIGURES_ATTR) == {}


class TestProfilePanel:
    """Tests for the profile panel."""

    def drawn(self) -> tuple[folium.Map, folium.FeatureGroup]:
        """A map with one measured chain drawn on it."""
        gdf = gpd.GeoDataFrame(
            {
                "chain_id": ["ut-no-1-2-3"],
                "ascent": [996.4],
                "geometry": [LineString([(12.8, 65.4), (12.81, 65.41)])],
            },
            crs="EPSG:4326",
        )
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        return fmap, maps.add_trails(fmap, gdf, name="Chains", group_field="chain_id", figure_fields={"ascent": "ascent"})

    @pytest.fixture
    def group(self) -> tuple[folium.Map, folium.FeatureGroup]:
        """The same map, as a fixture."""
        return self.drawn()

    def test_the_figures_and_the_sources_are_one_tap_away_on_every_screen(self, group):
        """First the licences folded on a short screen, then on a narrow one as
        well — a width rule for something that was never about width. The
        heading carries the three figures a walk is decided on and everything
        else is behind the *i*, on a phone and on a desktop alike."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "var folded = sheeted() || !licencesOpen;" in html
        assert "size.y < SHORT" not in html.split("function showLicences")[1][:400]

    def test_the_i_opens_the_sheet_rather_than_the_drawing(self, group):
        """A page whose popups all dock into one panel has somewhere to put a
        sentence this long, and unfolding eleven lines into a 390 px drawing
        gives straight back the room the fold was for. Where there is no chrome
        the fold is still the answer, because there is nowhere else."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "window.trailsChrome.detail(named, box, 'profile');" in html
        # And a second press closes it, which is what a button that opened
        # something is expected to do.
        assert "standing.detailKey === 'profile'" in html
        # Read off the element that shows it rather than composed again: one
        # sentence, in two places, from one derivation.
        assert "said.textContent = part[0];" in html
        assert "licencesOpen = !licencesOpen;" in html

    def test_the_heading_shows_three_of_the_list_the_sheet_shows_all_of(self, group):
        """Six lines of figures over a drawing that got four. The heading takes
        how far, how much climb and how steep at worst; the sheet takes the same
        list entire, in the same order — a second list for the second rendering
        is how a page comes to tell two stories about one route."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "summary.textContent = lines.slice(0, 3).join(" in html
        assert "saidLines.forEach(function (line, at) {" in html

    def test_the_panel_can_be_put_away_only_where_something_brings_it_back(self, group):
        """A control that strands a reader is worse than no control: a page built
        without the chrome has no way back to the panel once it is gone."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "hide.className = 'trails-profile-hide';" in html
        assert "window.trailsChrome.profile(false);" in html
        assert "hide.style.display = (window.trailsChrome && window.trailsChrome.profile) ? '' : 'none';" in html

    def test_the_gradient_bands_and_their_rule_reach_the_page(self, group):
        """The bands are a measurement, not a taste: 15 % sits above the worst
        gradient the height model reads on ground that is level."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        for lower, label, colour, _ in maps.GRADIENT_BANDS:
            assert label in html
            assert colour in html
            assert str(lower) in html
        assert str(maps.GRADIENT_WINDOW_M) in html
        assert str(maps.GRADIENT_MIN_RUN_M) in html

    def test_the_profile_height_is_a_reader_s_to_drag(self, group):
        """And the drag is coalesced to one draw a frame.

        A redraw per mouse move is the mistake that froze this map twice, and a
        chain of eight thousand samples is four hundred separate strokes.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "cursor:ns-resize" in html
        assert "function stretchTo(pixels)" in html
        assert "window.requestAnimationFrame(function () { awaiting = false; render(); });" in html

    def test_the_profile_height_is_bounded_at_both_ends(self, group):
        """Room for a curve at all, and never so tall that the panel is the map.

        Measured against the height the panel was **laid out** with rather than
        the one it was last asked for. A redraw is coalesced to the next frame,
        so two moves inside one frame otherwise measure a fresh chart against a
        stale box: the second reads an overhead of minus 620, a ceiling of 1,440,
        and hands out a panel taller than the map. Firefox reports clientY as -86
        the moment the pointer leaves the foot of the window, so a drag that runs
        off the bottom delivers three such moves at once.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "var least = 60;" in html
        assert "map.getSize().y - (box.offsetHeight - laidOut) - 80" in html
        assert "laidOut = chartHeight;" in html

    def test_the_profile_height_does_not_move_while_the_panel_is_folded(self, group):
        """Folded, the box is one line with no chart in it, so the overhead
        measures as minus 170 and the ceiling comes out taller than the map
        instead of shorter. A click on the map folds the panel, and a click can
        land in the middle of a drag: measured, that reopened it at 705 px.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "Folded, the box is one line with no chart in it" in html
        assert "if (!open && stretching) { stretching = null;" in html

    def test_the_height_is_held_to_a_ceiling_that_moves(self, group):
        """It was clamped only where it was asked for, so a window made shorter
        afterwards left the panel taller than the map: measured, a 725 px panel
        in a 620 px window put its own grip at -127, off the top of the map and
        out of a reader's reach for good.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "if (open) { stretchTo(chartHeight); }" in html

    def test_the_wheel_is_the_map_s_except_over_a_curve_that_can_use_it(self, group):
        """A panel that swallows a wheel and does nothing with it reads as the
        map having frozen, which is why this panel has only ever taken clicks.
        So the chart takes the wheel exactly where there is detail under the
        drawing to reach: 126 chains of 11,264, and every route worth planning.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "chart.addEventListener('wheel'" in html
        assert "if (!crosshair || !(crosshair.closest > 1.001)) { return; }" in html
        assert "}, {passive: false});" in html

    def test_the_zoom_stops_at_one_reading_per_pixel(self, group):
        """The ceiling is the data's rather than a taste. Past it the panel
        magnifies the straight lines drawn between samples, which claims a
        resolution nothing supports: 7.1x on the 42 km chain, 1 on most.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "var spacing = readable > 1 ? shape.total / (readable - 1) : shape.total;" in html
        assert "var closest = spacing > 0 ? Math.max(1, base / spacing) : 1;" in html
        assert "view.zoom = Math.min(closest, Math.max(1, view.zoom));" in html

    def test_a_zoomed_window_is_drawn_at_the_same_true_scale(self, group):
        """One metres-per-pixel for both axes, whatever the window: zooming
        changes how much of the chain is on the panel and never its angle.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "var metresPerPixel = base / view.zoom;" in html
        assert "return box.left + (value - from) / metresPerPixel;" in html
        assert "return middleY - (value - view.centre) / metresPerPixel;" in html

    def test_a_window_steeper_than_the_panel_is_clipped(self, group):
        """The panel's own shape is a gradient, 14.6 %, and it does not move with
        the zoom. Unclipped, a steeper window runs over the height labels and out
        of the panel into the map.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "createElementNS(SVG, 'clipPath')" in html
        assert "group.setAttribute('clip-path', 'url(#' + id + ')');" in html
        # And the waypoint marks get a frame of their own, wider by their own
        # radius: every route has a point at nought and one at its end, and the
        # curve's frame would draw both as half discs.
        assert "var marks = framed('trails-profile-marks-" in html
        assert "STATION_R + 1);" in html

    def test_the_profile_marks_the_points_a_route_was_planned_with(self, group):
        """ "Where is the climb" is half an answer until the profile says which
        two points it lies between. Drawn as the pin is drawn — a pale disc, a
        dark ring, the same number — because they are the same point seen from
        above and from the side.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "(shape.stations || []).forEach(function (metres, index) {" in html
        assert "var sample = nearest(shape.distance, metres);" in html
        # A point on ground nothing was read along still happened, and it rests
        # on the floor of the box: at the ceiling it read as a summit, which a
        # waypoint set on the water is the one thing it must not.
        assert "var level = read ? y(value) : box.bottom - STATION_R - 1;" in html
        assert "var ink = read ? STATION : STATION_UNREAD;" in html

    def test_the_heading_says_how_steep_the_ground_gets(self, group):
        """Absolute, over the 25 m window the curve is banded by: a signed
        maximum would call this park's steepest chain flat, since it climbs 9 m
        and drops 816.

        A chain's figure is the build's, the same number its popup carries. The
        page's own series would answer 80.87 where the build says 81 -- they
        differ by the arc length Python spaces its samples at against the chords
        this page sums -- and one page showing both would be showing two answers
        about one chain. A composed route has no build figure and no popup, so
        there the page computes it.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "function steepestOf(shape) {" in html
        assert "var slope = gradients(shape), worst = NaN;" in html
        # A route works it out; a chain is handed it.
        assert "var worst = steepestOf(shape);" in html
        assert "told.push('steepest ' + Math.round(worst) + ' %');" in html
        assert "var steepest = figure.steepest;" in html

    def test_a_window_belongs_to_the_chain_it_was_opened_on(self, group):
        """Carried over, it would open the panel somewhere in the middle of
        whatever the reader just clicked, at a scale chosen for something else.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "view.zoom = 1; view.at = 0; view.centre = null;" in html

    def test_the_crosshair_marks_its_position_on_the_map(self, group):
        """The hill under the pointer and the hill on the map are the same hill.

        In the direction arrow's pane, for the arrow's reason: the map's path
        count is what phase 3 was accepted against and nothing this panel draws
        may join it.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "standing = positionAt(shape, shape.distance[at]);" in html
        assert "function placeHere() {" in html
        assert "L.DomUtil.setPosition(here, map.latLngToLayerPoint(standing));" in html
        assert "map.on('zoomend viewreset moveend resize', placeHere);" in html

    def test_the_mark_is_drawn_above_the_route_it_reports_on(self, group):
        """It shared the direction arrow's pane at 450 and plan mode's route
        pane is 460, so the one mark whose whole job is to say where on this
        route you are was drawn underneath the route."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "map.createPane('trailsProfileHere')" in html
        assert "over.style.zIndex = 470;" in html
        assert "over.appendChild(here);" in html
        # And it takes no clicks, so plan mode's dispatcher never sees it.
        assert "over.style.pointerEvents = 'none';" in html

    def test_a_position_is_looked_up_on_the_axis_that_has_one(self, group):
        """A series has two axes and they are not the same length: heights every
        5 m, and the line through the vertices somebody surveyed. Only a distance
        is shared between them, so a sample's index cannot index a vertex.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "function positionAt(shape, metres) {" in html
        assert "if (shape.along[middle] < metres) { low = middle + 1; } else { high = middle; }" in html
        # And the arrow asks the same walk rather than keeping one of its own.
        assert "return positionAt(shape, shape.total / 2);" in html

    def test_the_mark_does_not_outlive_the_reading_that_put_it_there(self, group):
        """A dot left on the map after the pointer has gone claims a position
        nobody is pointing at. It goes when the pointer leaves the chart, when
        the curve is redrawn under it, and when a drag starts.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "function forget() {" in html
        assert "chart.addEventListener('mouseleave', forget);" in html
        assert "if (standing) { standing = null; placeHere(); }" in html

    def test_the_panel_says_which_part_of_the_chain_it_is_showing(self, group):
        """A window is a thing to be read rather than screenshotted, the same as
        the series and the figures above it.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "view: function () {" in html
        assert "metresPerPixel: crosshair ? crosshair.mpp : null," in html
        assert "closest: crosshair ? crosshair.closest : null" in html

    def test_the_lowest_band_clears_what_the_model_reads_on_level_ground(self):
        """Measured: level chains read a median of 1.0 % over a 25 m window and
        never more than 9.2 %. A boundary under that would colour the data."""
        assert maps.GRADIENT_BANDS[0][0] == 0.0
        assert maps.GRADIENT_BANDS[1][0] > 9.2

    def test_the_gradient_is_never_read_between_neighbouring_samples(self):
        """Samples are laid per edge, so two of them can be a third of a metre
        apart, where a decimetre of model noise reads as a cliff — 2,754 % at
        the worst. The window and its floor are what stop that."""
        assert maps.GRADIENT_MIN_RUN_M >= 10.0
        assert maps.GRADIENT_WINDOW_M >= 2 * maps.GRADIENT_MIN_RUN_M

    def test_the_crosshair_is_not_the_colour_of_the_steepest_band(self):
        """A red rule over a red stretch of curve reads as part of the data."""
        fmap, layer = self.drawn()
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert f"CROSS = '{maps.GRADIENT_BANDS[-1][2]}'" not in html

    def test_the_page_names_no_compass_point_of_its_own(self, group):
        """A rounded label is a threshold, so it is decided once, in Python, and
        carried. A second rule in the page would name a different direction from
        the popup on any chain lying near a boundary between two points."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "figure.point" in html
        for derived in ("octant(", "OCTANTS", "/ 45 + 0.5"):
            assert derived not in html, f"the page derives the compass point itself: {derived}"

    def test_the_figures_reach_the_page(self, group):
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "trail-group-ut-no-1-2-3" in html
        assert "996.4" in html

    def test_it_draws_nothing_on_the_map(self, group):
        """The arrow belongs in a container of its own: anything drawn into the
        overlay pane is counted among the map's paths for ever after."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])
        assert not [child for child in fmap._children.values() if isinstance(child, folium.GeoJson | folium.Marker)]
        html = fmap.get_root().render()
        assert "createPane" in html
        assert "L.polyline" not in html.split("var figures")[-1]

    def test_it_fetches_nothing(self, group):
        """A charting library from a CDN does not load on a file:// page: it
        fails silently, the way the OpenStreetMap tiles once did.

        Every URL the panel does carry is a **namespace**, and a namespace names
        a language rather than a place: the SVG one, which is what
        createElementNS takes, and GPX's own, which the panel writes into the
        file it produces. Nothing resolves either, and the schema location
        beside the second is a hint to a validator that will never see this
        page."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])
        with_panel = fmap.get_root().render()
        for namespace in ("http://www.w3.org/2000/svg", "http://www.topografix.com/GPX/1/1", "http://www.w3.org/2001/XMLSchema-instance"):
            with_panel = with_panel.replace(namespace, "")

        bare, _ = self.drawn()
        assert with_panel.count("://") == bare.get_root().render().count("://")

    def test_the_wheel_still_reaches_the_map(self, group):
        """disableClickPropagation, and deliberately not the scroll one: a panel
        that swallows the wheel reads as a map that has frozen."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "disableClickPropagation" in html
        assert "disableScrollPropagation" not in html

    def exported(self, **changed: object) -> dict[str, object]:
        """What the page has to be handed before it can write a GPX file.

        Args:
            **changed: Settings to override or, with a value of None, to drop

        Returns:
            A complete set, minus anything set to None
        """
        settings: dict[str, object] = {
            "credits": {"UT.no": [{"name": "UT.no", "licence": "CC BY-NC 4.0", "note": "non-commercial", "version": "downloaded 2026-08-12"}]},
            "heights": [{"name": "Høydedata DTM1", "licence": "CC BY 4.0", "note": ""}],
            "fields": [["id", "chain"], ["ascent", "ascent"]],
            "creditFields": ["name", "licence", "version"],
            "gapM": 5.0,
            "decimals": 1,
            "elevationDecimals": 2,
            "coordinateDecimals": 7,
            "namespace": "https://github.com/ueisele/trails/gpx/1",
            "prefix": "trails",
            "creator": "trails-analysis",
            "description": "One chain",
            "ascentMethod": "DTM1, sampled every 5 m, gains under 5 m ignored",
            "identitySeparator": " / ",
            "filePrefix": "lomsdal-visten",
            "sourceLength": "metres",
            "route": {
                "name": "Planned route in Lomsdal-Visten",
                "description": "A route planned on the Lomsdal-Visten map",
                "fileStem": "route",
                "kindField": "kind",
                "kind": "route",
                "fields": [["ascent", "ascent"], ["walked", "walked"], ["unknown", "unknown"]],
                "legs": "legs",
                "leg": "leg",
                "part": "part",
                "partKind": "kind",
                "partLength": "m",
                "areas": "protected",
                "area": "area",
                "areaId": "id",
                "areaName": "name",
                "areaForm": "form",
                "areaLength": "m",
            },
            "waypoint": {
                "name": "Point",
                "origin": "origin",
                "set": "set",
                "generated": "generated",
                "enters": "Enters",
                "leaves": "Leaves",
                "area": "area",
                "stage": "stage",
            },
            "protected": [{"name": "Naturvernområder", "licence": "NLOD", "note": ""}],
        }
        settings.update(changed)
        return {name: value for name, value in settings.items() if value is not None}

    def test_the_licences_and_the_versions_reach_the_page(self, group):
        """The browser writes the exported file, so everything in it has to be
        in the page. Measured before this: CC BY 4.0, ODbL and CC BY-NC appeared
        **zero times** in the built page, and so did any source version — they
        existed only in what the build printed to its console."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer], export=self.exported())

        html = fmap.get_root().render()
        assert "CC BY-NC 4.0" in html
        assert "downloaded 2026-08-12" in html
        assert "DTM1, sampled every 5 m, gains under 5 m ignored" in html

    def test_a_panel_given_no_export_offers_no_download(self, group):
        """Phase 4's panel, unchanged: it draws and says nothing about files."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "var EXPORT = null" in html
        # The words about licences that remain are the ones explaining why no
        # <copyright> is written; none of them is a licence the page carries.
        assert "CC BY-NC 4.0" not in html
        assert "Høydedata" not in html

    def test_an_export_missing_a_setting_is_refused(self, group):
        """A page that quietly wrote 'undefined' into a licence is worse than
        one that was never built."""
        fmap, layer = group

        with pytest.raises(ValueError, match="licence|credits|ascentMethod"):
            maps.add_profile_panel(fmap, [layer], export=self.exported(credits=None, ascentMethod=None))

    def test_every_setting_the_template_reads_is_one_it_insists_on(self, group):
        """The two lists are the same list. A setting the template reads and the
        check does not require is one a caller can leave out and find missing in
        a browser, which is the expensive place to find it."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer], export=self.exported())

        html = fmap.get_root().render()
        for setting in maps.EXPORT_SETTINGS:
            assert f"EXPORT.{setting}" in html, setting
        for setting in maps.EXPORT_ROUTE_SETTINGS:
            assert f"EXPORT.route.{setting}" in html, setting
        for setting in maps.EXPORT_WAYPOINT_SETTINGS:
            assert f"EXPORT.waypoint.{setting}" in html, setting

    def test_a_route_setting_missing_from_inside_its_own_block_is_refused(self, group):
        """Checking only the top-level key lets a `route` short of `partLength`
        build without a word, and the page then writes
        `<trails:part kind="routed" undefined="2027.0"/>`."""
        fmap, layer = group
        short = dict(self.exported())
        short["route"] = {name: value for name, value in short["route"].items() if name != "partLength"}
        short["waypoint"] = {name: value for name, value in short["waypoint"].items() if name != "origin"}

        with pytest.raises(ValueError, match="route.partLength.*waypoint.origin"):
            maps.add_profile_panel(fmap, [layer], export=short)

    def test_the_figures_a_file_is_written_from_travel_as_the_page_names_them(self, group):
        """Every field the export writes has to be a key the figures table
        actually carries; one that is not is a field the browser would write as
        'undefined' into the file that leaves the machine."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer], export=self.exported())

        html = fmap.get_root().render()
        assert '["id", "chain"]' in html or '["id","chain"]' in html

    def test_the_offer_says_nothing_where_the_panel_has_said_what_went_wrong(self, group):
        """Three things can stop a chain reaching the panel — no graph in the
        page, a graph that never arrived, a line the graph does not hold — and
        each is said once, by the line that knows which it was. A row under it
        still reading 'decoding' would contradict it, and a reader believes what
        is next to the button they were about to press."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer], export=self.exported())

        html = fmap.get_root().render()
        assert html.count("selected.missing = true") == 3
        assert "selected.missing ? '' :" in html

    def test_without_groups_nothing_is_added(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_profile_panel(fmap, [])

        # The class name alone is no longer proof: the theme's stylesheet names
        # every panel it colours, whether or not one was added. What only a real
        # panel produces is the call that makes one.
        assert "L.DomUtil.create('div', 'trails-profile-panel')" not in fmap.get_root().render()

    def test_without_figures_nothing_is_added(self):
        """A layer nobody measured has no profile to offer."""
        gdf = gpd.GeoDataFrame({"chain_id": ["a"], "geometry": [LineString([(12.8, 65.4), (12.81, 65.41)])]}, crs="EPSG:4326")
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        layer = maps.add_trails(fmap, gdf, name="Chains", group_field="chain_id")
        maps.add_profile_panel(fmap, [layer])

        # The class name alone is no longer proof: the theme's stylesheet names
        # every panel it colours, whether or not one was added. What only a real
        # panel produces is the call that makes one.
        assert "L.DomUtil.create('div', 'trails-profile-panel')" not in fmap.get_root().render()

    def test_it_starts_folded(self, group):
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        assert "var open = false;" in fmap.get_root().render()


class TestPlanMode:
    """Tests for clicking a route together over the graph in the page."""

    def planned(self, **changed: object) -> dict[str, object]:
        """What the page has to be handed before it can plan a route.

        Args:
            **changed: Settings to override or, with a value of None, to drop

        Returns:
            A complete set, minus anything set to None
        """
        settings: dict[str, object] = {
            "heightsUrl": "https://ws.geonorge.no/hoydedata/v1/punkt",
            "heightsCrs": 4326,
            "heightsBatch": 50,
            "heightsWorkers": 6,
            "terrainModel": "dtm",
            "seaTerrain": "Havflate",
            "sampleStepM": 5.0,
            "ascentThresholdM": 5.0,
            "snapM": 150.0,
            "maxStraightM": 20000.0,
            "crossingKind": "ferry",
            "connectorKind": "bridge",
            "touchedM": 100.0,
            "namedM": 50.0,
            "indexCellM": 100.0,
            "matchToleranceM": 25.0,
            "matchMinOverlap": 0.6,
            "matchMinRunM": 100.0,
            "matchMaxTurnDeg": 60.0,
            "matchAnchorM": 250.0,
            "gpx": {
                "namespace": "https://github.com/ueisele/trails/gpx/1",
                "kindField": "kind",
                "kind": "route",
                "chainField": "chain",
                "legs": "legs",
                "leg": "leg",
                "part": "part",
                "partKind": "kind",
                "partLength": "m",
                "origin": "origin",
                "set": "set",
                "generated": "generated",
                "trackKind": "track",
                "stage": "stage",
            },
        }
        settings.update(changed)
        return {name: value for name, value in settings.items() if value is not None}

    def drawn(self) -> tuple[folium.Map, folium.FeatureGroup]:
        """A map carrying a chain, the graph and the panel, ready for plan mode."""
        gdf = gpd.GeoDataFrame(
            {"chain_id": ["ut-no-1-2-3"], "ascent": [996.4], "geometry": [LineString([(12.8, 65.4), (12.81, 65.41)])]},
            crs="EPSG:4326",
        )
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        layer = maps.add_trails(fmap, gdf, name="Chains", group_field="chain_id", figure_fields={"ascent": "ascent"})
        maps.add_routing_graph(fmap, {"version": 2, "edges": 0}, "")
        maps.add_profile_panel(fmap, [layer])
        return fmap, layer

    def test_every_setting_the_template_reads_is_one_it_insists_on(self):
        """The two lists are the same list. A setting the template reads and the
        check does not require is one a caller can leave out and find missing in
        a browser, which is the expensive place to find it."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()
        for setting in maps.PLAN_SETTINGS:
            assert f"PLAN.{setting}" in html, setting

    def test_every_setting_the_template_reads_is_one_the_check_knows_about(self):
        """The converse of the test above, and the one that was missing.

        That direction — list to template — says nothing about a name the
        template reads that is not on the list, and JavaScript has no complaint
        to make about one: ``PLAN.matchAnchorM`` was left out of
        :data:`PLAN_SETTINGS` while the matcher read it, ``along[i] - since <
        undefined`` is ``false``, and every recorded point became an anchor. The
        matcher then matched **3.6 %** of a track that lies exactly on the
        network, and nothing threw, nothing logged, and the page looked right.
        """
        source = pathlib.Path(maps.__file__).read_text(encoding="utf-8")
        planning = source.split("class _PlanMode")[1].split("class _Legend")[0]
        read = set(re.findall(r"PLAN\.([A-Za-z_][A-Za-z0-9_]*)", planning)) - {"gpx"}
        assert read - set(maps.PLAN_SETTINGS) == set()
        assert set(maps.PLAN_SETTINGS) - read - {"gpx"} == set()

        inside = set(re.findall(r"PLAN\.gpx\.([A-Za-z_][A-Za-z0-9_]*)", planning))
        assert inside - set(maps.PLAN_GPX_SETTINGS) == set()
        assert set(maps.PLAN_GPX_SETTINGS) - inside == set()

    def test_every_name_the_reader_looks_for_is_one_the_check_insists_on(self):
        """Phase 8 both reads and writes this file, which nothing else here does.
        A ``gpx`` short of one name leaves the page looking for an element called
        ``undefined``, finding none, and reporting one of its own routes as a
        foreign track without a word."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()
        for setting in maps.PLAN_GPX_SETTINGS:
            assert f"PLAN.gpx.{setting}" in html, setting

    def test_a_plan_that_cannot_read_a_file_back_is_refused(self):
        """The same refusal as a missing sampling step, for the same reason: a
        page that guessed a field name would load its own routes as foreign
        tracks and nothing about it would look wrong."""
        fmap, _ = self.drawn()
        short = self.planned()
        short["gpx"] = {name: value for name, value in short["gpx"].items() if name not in ("origin", "trackKind")}

        with pytest.raises(ValueError, match="gpx.origin|gpx.trackKind"):
            maps.add_plan_mode(fmap, short)

    def test_a_plan_with_no_gpx_block_at_all_is_refused(self):
        """Checked as its own list rather than by the presence of the key above
        it, which is how :data:`EXPORT_ROUTE_SETTINGS` is checked and for the
        same reason."""
        fmap, _ = self.drawn()

        # An empty block rather than no block: dropping the key means the check
        # above this one fires first, and the branch this test is about is never
        # reached — which is what it did until a review said so.
        with pytest.raises(ValueError, match=r"read a GPX back without gpx\."):
            maps.add_plan_mode(fmap, self.planned(gpx={}))

        with pytest.raises(ValueError, match="without gpx$"):
            maps.add_plan_mode(fmap, self.planned(gpx=None))

    def test_a_plan_missing_a_setting_is_refused(self):
        """A page that quietly sampled every 50 m, or read a climb at no
        threshold at all, would look exactly like one that did neither."""
        fmap, _ = self.drawn()

        with pytest.raises(ValueError, match="sampleStepM|ascentThresholdM"):
            maps.add_plan_mode(fmap, self.planned(sampleStepM=None, ascentThresholdM=None))

    def test_the_build_s_own_step_and_threshold_reach_the_page(self):
        """Two halves of one profile read under two rules answer differently,
        and nothing about the answer looks wrong."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned(sampleStepM=7.5, ascentThresholdM=3.25))

        html = fmap.get_root().render()
        assert "7.5" in html
        assert "3.25" in html

    def test_every_mode_says_what_it_does_to_every_kind_of_file(self):
        """The mode names have to be true of a planned route and of somebody's
        GPS recording at once, and they cannot be: read as a plan, *take it as it
        is* means the route as it was planned; read as a recording it means the
        line as it was walked. So the question is asked once the file has been
        read, in terms of the file -- and the wording lives in one table keyed by
        both, because a sentence and the mode it describes are one decision.

        Checked in **both** directions. A kind missing a mode leaves the sentence
        under the selector ``undefined`` and JavaScript has nothing to say about
        it; a kind naming a mode that does not exist is a sentence no reader can
        ever reach. That asymmetry cost this page an hour once already.
        """
        source = pathlib.Path(maps.__file__).read_text(encoding="utf-8")
        planning = source.split("class _PlanMode")[1].split("class _Legend")[0]
        modes = set(re.findall(r"\{key: '([a-z]+)', label:", planning))
        assert modes

        table = planning.split("var READINGS = {")[1].split("\n            };")[0]
        kinds = re.findall(r"\n                ([a-z]+): \{(.*?)\n                \}", table, re.S)
        assert {kind for kind, _ in kinds} == {"route", "chain", "track"}

        for kind, block in kinds:
            named = set(re.findall(r"\n                    ([a-z]+):", block))
            assert named - {"first"} == modes, kind
            first = re.search(r"first: '([a-z]+)'", block)
            assert first and first.group(1) in modes, kind

    def test_the_mode_is_asked_after_the_file_has_been_read(self):
        """It stood beside the button and had to be answered before anybody knew
        what was in the file. A reader picking the first of the three lost the
        points their route was planned with -- measured, six set waypoints in the
        file and two points on the map -- while the page named the number it was
        about to discard.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        # The picker reads and describes; nothing is taken by picking a file.
        assert "offerFile(String(reader.result), file.name);" in html
        assert "loadGpx(String(reader.result)" not in html
        assert "class ='trails-plan-offer'" not in html
        assert "offerBox.className = 'trails-plan-offer';" in html

    def test_a_file_read_and_not_taken_replaces_nothing(self):
        """The question is the only moment at which the plan on the map still
        exists: taking a file replaces it and there is no way back, because undo
        takes a point off the end and a load has no history. So reading must
        touch nothing -- one place puts a file on the map, and it is the one the
        reader reaches through an answer.
        """
        source = pathlib.Path(maps.__file__).read_text(encoding="utf-8")
        planning = source.split("class _PlanMode")[1].split("class _Legend")[0]

        assert planning.count("points = pointsForLoaded(graph);") == 1
        assert planning.count("loaded = read;") == 1
        taking = planning.split("function takeGpx(read, mode) {")[1].split("\n            }")[0]
        assert "points = pointsForLoaded(graph);" in taking
        assert "loaded = read;" in taking

        # And what it costs is said before it happens, as a count rather than
        # as a warning about files in general. **It no longer says there is no
        # way back**: the history covers a load, so undo restores the plan the
        # file replaced. The sentence was true when it was written and the
        # question is still worth asking -- it says what the file turned out to
        # be and what each mode would do to it, which was never the half about
        # the way back.
        assert "' points' ) + ' on the map." not in planning
        assert "on the map. Undo brings them back." in planning

    def test_a_plan_is_restored_from_its_own_leg_list(self):
        """*Take it as it is*, read as what the file describes. The seam is
        **inside** a leg -- a matched leg is ``routed + track + routed`` -- which
        is why nothing restored one before: ``anchorRecordedLegs`` asks whether a
        leg is *wholly* recorded and so never fires on the legs that need it.
        Measured, align routed 1,038 recorded metres away and came back 353 m
        short without a word; restored, the same route comes home at 5,986.6 m
        with its three points and its four parts.

        The order in ``resolve`` is the test worth having: both ends of a
        restored leg may well sit on a node, so a routing branch reached first
        would replace a recorded stretch with whatever path lies there.
        """
        source = pathlib.Path(maps.__file__).read_text(encoding="utf-8")
        planning = source.split("class _PlanMode")[1].split("class _Legend")[0]
        deciding = planning.split("function resolve(graph, from, to, mayAsk) {")[1]

        assert deciding.index("from.restore") < deciding.index("from.track === loaded.id")
        assert deciding.index("from.restore") < deciding.index("from.node >= 0")

        # And it is offered only where there is a plan in the file to restore.
        assert "loaded.mode === 'asis' && loaded.isRoute" in planning
        assert "loaded.waypoints.length === loaded.legs.length + 1" in planning

    def test_a_restored_routed_stretch_is_held_to_the_length_the_file_states(self):
        """A routed part of a *matched* route is a run of spans between anchors
        merged into one, and the cheapest path between its two ends is not the
        concatenation of the cheapest paths between the anchors along it -- the
        same thing this project already measured about align on a matched route,
        7,266 m against 7,307. Here it read **2,899 against 3,142**, and routing
        alone would have restored a plan 243 m short while calling it exact.

        So each way of laying the stretch is checked against the length the file
        states, and they are tried in the order that keeps the most: routed,
        then matched off the very geometry the router produced, then the file's
        own line -- which is exact and costs the edges underneath, and is what
        ``drifted`` then says out loud.
        """
        source = pathlib.Path(maps.__file__).read_text(encoding="utf-8")
        planning = source.split("class _PlanMode")[1].split("class _Legend")[0]
        laying = planning.split("function restoredWalked(")[1].split("\n            function agrees")[0]

        assert laying.count("agrees(") == 2
        assert laying.index("routedParts(graph, found)") < laying.index("matchedParts(graph, first, last)")
        assert laying.index("matchedParts(graph, first, last)") < laying.rindex("trackPart(graph, first, last)")

    def test_a_waypoint_off_the_track_keeps_the_position_it_was_written_at(self):
        """A point set on open water is in the ``<wpt>`` list and in no
        ``<trkseg>`` at all -- the crossing either side of it writes no geometry,
        which is what stops a file drawing a line across a fjord. Anchoring it to
        the nearest trackpoint would put it on the shore, and the shore is where
        it went: measured, three points out and eight back with the offshore one
        gone. Restored, it comes home at the position it was set.
        """
        source = pathlib.Path(maps.__file__).read_text(encoding="utf-8")
        planning = source.split("class _PlanMode")[1].split("class _Legend")[0]
        placing = planning.split("if (restoring()) {")[1].split("if (loaded.mode === 'align')")[0]

        assert "<= 1.0" in placing
        assert "anchored(graph, at) : snapped(graph, wp.lat, wp.lon)" in placing
        # And a crossing contributes none of its length to the walking, so the
        # stations cannot be summed off the parts without saying so.
        assert "part.kind !== 'water' && part.kind !== CROSSING" in placing

    def test_a_loaded_route_is_shown_once_and_not_once_a_refresh(self):
        """The map stands wherever the reader left it and a file may describe
        ground fifty kilometres away, so a load that changes nothing on the
        screen reads as a load that did nothing. Driven: the map at zoom 9 over
        the park moves to zoom 13 over a loaded recording with all 1,233 of its
        vertices inside the window, and a map deliberately moved 50 km away
        comes back to a loaded route with every point of it in view.

        **The fit follows the settle, not the load.** A route half worked out has
        half a shape, and fitting to that leaves the reader looking at the wrong
        window. And it happens once: the map is the reader's from that moment,
        and a control that moves it twice is one that fights the hand.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        assert "fitWanted = true;" in html
        assert "if (fitWanted) { fitWanted = false; showRoute(); }" in html
        # Fitted to what is drawn *and* to the points, which are not the same
        # set: a waypoint on open water lies inside a crossing, and a crossing
        # draws nothing at all.
        showing = html.split("function showRoute() {")[1].split("\n            }")[0]
        assert "points.forEach(" in showing
        assert "maxZoom: SHOW_MAX_ZOOM" in showing
        # Measured rather than assumed: both controls are the reader's to resize.
        assert "getBoundingClientRect().height" in showing
        assert "getBoundingClientRect().width" in showing

    def test_a_stage_mark_survives_being_dragged(self):
        """A tour is planned whole and walked in pieces, and the mark lives on
        the point object so that reordering and inserting carry it along without
        a case of their own. **A drag is the exception and the trap**: phase 7's
        model replaces a dragged waypoint with a *new* object on purpose, which
        is what tells the legs beside it to rebuild — so anything the reader put
        on the old one is lost unless it is carried over by hand, and a mark lost
        by dragging a point would be lost silently.

        Driven: three stages cut, one named, then point 5 dragged and point 2
        moved to the front. All three survive both, and come back out of the file
        the same way.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        assert "var was = points[at].stage;" in html
        assert "if (was !== undefined) { points[at].stage = was; }" in html
        # And it reaches the file, which is a different list from the point.
        assert "stage: cut};" in html
        assert "if (typeof wp.stage === 'string') { here.stage = wp.stage; }" in html

    def test_a_tour_nobody_has_cut_is_offered_no_stages(self):
        """One stage is the whole route, and a heading over it would offer the
        file the button already offers under a second name -- which is the
        two-panel mistake the legend was cured of. The archive follows the same
        rule for a harder reason: with one stage it would hand over the same
        file twice.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        assert "if (stages.length > 1) {" in html
        # And only where the panel can write a file at all, and only while the
        # list is open -- each heading composes its own stage to state its
        # figures, which is a walk over the route per stage nobody is looking at.
        assert "var gathered = writes && listOpen && stagesOf().length > 1;" in html
        assert "var stages = (listOpen && points.length) ? stagesOf() : [];" in html
        # The ends are never marked: a tour ends where it ends, and a mark there
        # would make a stage of no legs.
        assert "if (at < 1 || at + 1 >= points.length) { return; }" in html

    def test_a_stage_states_what_it_was_composed_to_state(self):
        """Its ascent is not the difference of two ascents, its steepest is a
        maximum over its own window, and its crossings are its own -- a stage
        that inherited an ``Enters`` from ground it never covers would be a file
        stating something about somewhere else. So a range is a narrowing of the
        one walk and never a slice of its figures.

        Driven: three stages of a 32,175.4 m tour come to 12,351.6, 12,403.9 and
        7,419.9 m, which is the walk exactly.
        """
        source = pathlib.Path(maps.__file__).read_text(encoding="utf-8")
        planning = source.split("class _PlanMode")[1].split("class _Legend")[0]

        assert "composeRoute(stage.from, stage.to)" in planning
        assert planning.count("function composeRoute(fromLeg, toLeg)") == 1
        # And the writer works its runs and its crossings out from the shape it
        # is handed, which is what makes a stage's file its own.
        panelling = source.split("class _ProfilePanel")[1].split("class _PlanMode")[0]
        writing = panelling.split("routeFile: function")[1].split("routeName:")[0]
        assert "runsOf(shape)" in writing
        assert "crossingsOf(shape, runs)" in writing

    def test_the_archive_is_written_here_because_nothing_may_be_added(self):
        """Several files as one download, against several downloads in a row --
        which rests on an assumption about what a browser lets a page opened off
        the disk do unattended, where an archive rests on arithmetic. Measured
        before it was written: a hand-made zip downloads from this page, keeps
        its name, opens in Python with a clean ``testzip()``, and every member
        reads back byte for byte. Deflated it is 1.87 MB of GPX in 282 kB.

        **Stamped with the time it was written**, which is a correction: it went
        in at zero on the rule that no trackpoint carries a time, and that rule
        is about the *route* -- a time on a trackpoint claims somebody walked
        there at that hour. When an archive was written claims nothing about the
        walk. And zero is not absent: the DOS field counts from 1980, so every
        member showed 1980-01-01, a wrong answer stated confidently.
        """
        fmap, _ = self.drawn()

        html = fmap.get_root().render()

        assert "function crc32(bytes) {" in html
        assert "new CompressionStream('deflate-raw')" in html
        # Stored where the browser cannot deflate, and where deflating made it
        # bigger -- a zip that grew its own members advertises itself badly.
        assert "u16(deflated ? 8 : 0)" in html
        assert "small.length < member.body.length" in html
        # One stamp for the whole archive, in the local header and again in the
        # central directory entry: the members were written in one act.
        assert html.count("u16(stamp.time), u16(stamp.date), u32(sum)") == 2
        assert "var stamp = dosStamp(new Date());" in html

    def test_a_point_where_a_stage_changes_hands_says_so(self):
        """A pin already carries two things -- which number it is and whether it
        is picked -- so a third meaning has to be readable beside both rather
        than instead of one. A second ring, drawn as a shadow so the icon keeps
        its size and its anchor and nothing about where a click lands moves.

        **The ends are not marked.** A tour begins and ends whether anybody says
        so, and a ring at the finish would claim the walk carries on past it.
        Driven with cuts after points 3 and 5: exactly pins 3 and 5 carry it, the
        marker pane stays at one per point, and the two stations on the profile
        carry two circles where the others carry one.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        assert "function pinStyle(picked, ends) {" in html
        assert "box-shadow:0 0 0 2px " in html
        # Never the first or the last, in the one list all three readings of a
        # cut are taken from.
        assert "for (var i = 1; i + 1 < points.length; i += 1) {" in html
        assert "stages: cutsOf()});" in html

    def test_it_draws_nothing_on_the_map(self):
        """The route belongs in a pane of its own: anything drawn into the
        overlay pane is counted among the map's paths for ever after, and 11,589
        is an acceptance figure for every phase from the third."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())
        assert not [child for child in fmap._children.values() if isinstance(child, folium.GeoJson | folium.Marker)]
        html = fmap.get_root().render()
        assert "createPane('trailsPlanRoute')" in html
        planning = html.split("var PLAN =")[-1]
        assert "pane: 'trailsPlanRoute'" in planning
        # Every layer it makes names that pane. One that did not would land in
        # the overlay pane by default, which is the whole thing being avoided.
        assert planning.count("L.polyline(") == planning.count("pane: 'trailsPlanRoute'") - planning.count("L.circleMarker(")

    def test_a_click_in_a_popup_is_not_a_click_on_the_ground(self):
        """A popup is not in the control container -- it lives in a pane inside
        the map -- so a dispatcher that only steps around the controls walks
        over it. Measured: the close button of a chain's popup placed a waypoint
        behind it and left the popup open.

        The chrome is in the list for the same reason and was added later: it
        hangs off the map container rather than off a corner, so that a panel
        can cover the corners on a narrow screen. **The assertion names the
        members and not the string**, because a check that pins the exact list
        fails on the next thing that legitimately joins it.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        assert "function overFurniture(event) {" in html
        stepped = html.split("return !!event.target.closest('")[-1].split("')")[0]
        assert {part.strip() for part in stepped.split(",")} >= {
            ".leaflet-control-container",
            ".leaflet-popup",
            ".trails-chrome",
        }
        assert "if (!on || overFurniture(event)) { return; }" in html
        assert "if (on && !overFurniture(event)) { event.stopPropagation(); }" in html

    def test_switching_on_lets_go_of_a_highlighted_line(self):
        """The click-highlight's only two ways out are a click on the line and a
        click on empty ground, and plan mode owns both from the moment it is on.
        Left standing it dims every line on the map with no way back.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        assert "if (on && window.trailsHighlight) { window.trailsHighlight.clear(); }" in html

    def test_the_points_are_listed_in_order_behind_their_own_count(self):
        """A route is a sequence and a map cannot show a sequence: reading eleven
        numbered pins off a map to find that 7 comes before 8 is searching, not
        reading. The count was already naming what the list holds, so it is the
        handle -- a second heading saying the same number would be the two-panel
        mistake the legend was cured of.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        assert "function drawList(stations) {" in html
        assert "listOpen = !listOpen;" in html
        assert "listBox.style.display = (listable && listOpen) ? '' : 'none';" in html
        # Drawn from the walk the panel is fed, so how far along a point comes is
        # the walk's answer and not a sum of the legs'.
        assert "drawList(shape.stations || []);" in html

    def test_a_row_can_be_dragged_to_any_place_in_the_route(self):
        """A splice and not a run of swaps: a swap is a full re-route of the two
        legs it touches, so dragging a point four places would route eight legs
        to arrive at the two that changed -- and dropping a row between two
        others means taking it out and putting it back in, where a run of swaps
        would drag every point it passed one place the other way.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        assert "function moveTo(at, to) {" in html
        assert "points.splice(to, 0, points.splice(at, 1)[0]);" in html
        assert "row.draggable = true;" in html
        # Firefox starts no drag at all without something in the transfer.
        assert "event.dataTransfer.setData('text/plain', String(index));" in html
        assert "if (from !== null && from !== index) { moveTo(from, index); }" in html

    def test_the_list_is_not_rebuilt_under_a_row_in_the_air(self):
        """A leg settling mid-drag would rebuild the rows under the pointer and
        the drop would land on nothing."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        # And never under a name being typed, which is the same rule for the
        # same reason: measured, typing a stage name and letting a point settle
        # rebuilt the heading and threw the half-typed name away with it.
        assert "if (heldRow !== null || namingRow !== null) { return; }" in html

    def test_the_list_keeps_inside_the_room_the_profile_leaves_it(self):
        """The profile panel is anchored to the foot of the map, takes its full
        width and is the reader's own to drag taller. Measured, twelve points
        with the profile pulled to 725 px put 315 px of this control underneath
        it, and the two corners share a z-index so whichever is written later
        wins. So this asks what is left rather than fighting over it.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        assert "function roomAbove() {" in html
        assert "document.querySelector('.trails-profile-panel')" in html
        assert "map.on('resize', fitList);" in html
        # The panel's height is a reader's to drag and nothing announces that.
        assert "new ResizeObserver(fitList).observe(watched);" in html
        # Off the scroll height, not the offset: the box is capped below, so its
        # offset height is the cap and subtracting the list would measure the cap.
        assert "var fixed = box.scrollHeight - listBox.offsetHeight;" in html

    def test_the_list_is_named_so_it_can_be_found(self):
        """Its height is computed, so nothing can find it by the cap it carried."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        assert "listBox.className = 'trails-plan-points';" in fmap.get_root().render()

    def test_the_points_a_reader_put_down_are_recorded_as_the_walk_happens(self):
        """A crossing contributes no walking distance and a leg still being
        worked out contributes none either, so a sum over the legs' own lengths
        would put every later point too far along. Leg i runs from point i to
        point i + 1, so the distance at the head of leg i is point i's.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        assert "var stations = [];" in html
        assert "stations.push(walked);\n                    if (!leg.parts)" in html
        # One per point and never one per leg: with nothing down there is
        # nothing to mark, and the guard is what says so. A range of one leg has
        # two stations, which is the same rule counted from the other end.
        assert "if (last > first || points.length) { stations.push(walked); }" in html
        assert "stations: shape.stations," in html

    def test_a_waypoint_is_a_marker_because_a_circle_cannot_be_dragged(self):
        """198 markers and 13 plan-pane paths were both acceptance figures, and
        phase 7 moves them on purpose. Measured in the built page: a
        ``circleMarker`` added to the map has no ``dragging`` at all and
        ``draggable: true`` on one is silently ignored, while an ``L.marker``
        gets a live handler and lands in the marker pane. So a draggable
        waypoint is a marker — 198 becomes 203 — and it draws no path, so the
        plan pane's 13 becomes 8."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "L.marker(" in planning
        assert "L.circleMarker(" not in planning
        # A div rather than an image, so the number is the element's own text
        # and selecting one is a single attribute rather than a second layer.
        assert "L.divIcon({className: 'trails-plan-pin'" in planning
        assert "draggable: true" in planning

    def test_a_pin_is_dead_to_the_pointer_out_of_plan_mode(self):
        """A pin has to catch clicks to be selected and dragged, and everything
        this page draws over the trails is otherwise deliberately not a click
        target: the park boundary swallowing every click inside it cost a
        fortnight. So the pointer events go off with plan mode, and dragging
        with them."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "element.style.pointerEvents = on ? 'auto' : 'none';" in planning
        assert "record.marker.dragging.enable(); } else { record.marker.dragging.disable();" in planning

    def test_the_named_points_reach_the_page_as_a_table(self):
        """A waypoint set beside a hut can only be called after it if the page
        holds a table of what is where. 1,411 circle markers and 865 markers
        keep their names inside popup HTML, which is markup and not a lookup."""
        fmap, _ = self.drawn()
        huts = gpd.GeoDataFrame({"name": ["Lavasshytta"], "geometry": [Point(12.98079, 65.77416)]}, crs="EPSG:4326")
        layer = maps.add_points(fmap, huts, name="Huts", point_type="hut")
        maps.add_plan_mode(fmap, self.planned(), [layer])

        planning = fmap.get_root().render().split("var NAMED =")[-1]
        assert '"name": "Lavasshytta"' in planning or '"name":"Lavasshytta"' in planning
        assert '"type": "hut"' in planning or '"type":"hut"' in planning

    def test_a_name_carrying_a_script_tag_cannot_close_the_block(self):
        """Every one of these is a name out of somebody else's register, and
        json.dumps does not escape '<'."""
        fmap, _ = self.drawn()
        nasty = gpd.GeoDataFrame({"name": ["</script><script>alert(1)</script>"], "geometry": [Point(12.98, 65.77)]}, crs="EPSG:4326")
        layer = maps.add_points(fmap, nasty, name="Huts", point_type="hut")
        maps.add_plan_mode(fmap, self.planned(), [layer])

        planning = fmap.get_root().render().split("var NAMED =")[-1]
        assert "</script><script>" not in planning.split("})();")[0]

    def test_without_a_table_a_waypoint_is_numbered(self):
        """Which is what it did before this existed."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var NAMED =")[-1]
        assert planning.lstrip().startswith("[]")

    def test_the_threshold_is_applied_once_and_carried_rather_than_spelled(self):
        """A rounded label is a threshold and so is a reported one. Applied in
        two places it becomes two thresholds, and the sentence above the button
        would name areas the file's markers do not."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned(touchedM=250.0))

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert planning.count("PLAN.touchedM") == 1
        assert "250" in fmap.get_root().render()

    def test_what_protects_the_ground_is_summed_per_edge_like_the_rest(self):
        """A part keeps its geometry and its heights and nothing downstream can
        get back to the edge a metre came from."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "graph.protectedAt[edge]" in planning
        assert "graph.protectedShare[p] * metres" in planning

    def test_a_crossing_is_asked_nothing_about_what_protects_it(self):
        """There is no walking distance under a ferry, so there is no protected
        walking distance either."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "if (source.kind !== CROSSING) { addProtected(out, graph, edge, metres); }" in planning

    def test_a_connector_is_asked(self):
        """Nobody drew it, but a walker covers its ground and that ground lies
        inside a boundary or outside it — so the protected question is put
        before the connector is taken out of the other two."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        protecting = planning.index("addProtected(out, graph, edge, metres)")
        connector = planning.index("if (source.kind === CONNECTOR) { out.undrawn += metres; continue; }")
        assert protecting < connector

    def test_a_leg_drawn_straight_reads_its_areas_off_its_own_samples(self):
        """The page has one protected area of the nineteen drawn and the height
        service answers ground cover, not protection — so the boundaries have to
        be carried, and a straight leg is decided at the samples it fetched."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "graph.areasAt(laid.lon[s], laid.lat[s])" in planning

    def test_the_wheel_still_reaches_the_map(self):
        """disableClickPropagation, and deliberately not the scroll one: a
        control that swallows the wheel reads as a map that has frozen."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "disableClickPropagation" in planning
        assert "disableScrollPropagation" not in planning

    def test_the_only_address_it_carries_is_the_height_service(self):
        """A routing library from a CDN does not load on a file:// page: it
        fails silently, the way the OpenStreetMap tiles once did. The one
        address here is the service a leg drawn straight asks for its heights,
        and it is asked when a reader draws one, not when the page loads."""
        fmap, _ = self.drawn()
        bare = fmap.get_root().render().count("://")

        maps.add_plan_mode(fmap, self.planned())
        planning = fmap.get_root().render()
        # Two, since phase 8: the height service, and the namespace a file this
        # map wrote puts its extensions in. **A namespace is an identifier and
        # never fetched** — it is compared against, which is the whole reason
        # the reader addresses elements by it rather than by their prefix.
        assert planning.count("://") == bare + 2
        assert planning.count("fetch(") == 1
        assert "getElementsByTagNameNS(PLAN.gpx.namespace" in planning

    def test_the_cost_comes_out_of_the_header(self):
        """Length times the source's factor, and a crossing at the header's flat
        figure. A cost column in the payload is the thing the encoder
        deliberately left out, and a second table here would be the same
        mistake wearing a different hat."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "graph.header.sources[graph.sources[i]]" in planning
        assert "cost[i] = length[i] * source.factor" in planning
        assert "source.flatM" in planning

    def test_it_lays_its_route_out_with_the_panel_s_own_walk(self):
        """Two walks laying edges end to end would eventually disagree, and a
        route composed by the wrong one still looks like a route. The Python
        side keeps its one in trails.routing.order for the same reason."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "panel().layEdges(" in planning
        assert "function layEdges(" not in planning
        assert "panel().metresBetween" in planning

    def test_every_walk_over_the_graph_is_bounded_and_throws(self):
        """An unbounded walk that appends is what a defect here looks like from
        the outside: not an error but a page that has hung. The Python sibling
        of the back-walk, written without a bound, took 42 GB before the kernel
        stopped it."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "pops > mostPops" in planning
        assert "steps > graph.header.edges" in planning
        assert planning.count("throw new Error(") >= 3

    def test_the_sentinel_is_tested_for_and_never_indexed_with(self):
        """A typed array answers a negative index with undefined rather than
        raising, so an unset predecessor would put undefined into the geometry
        and carry on."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "if (used < 0 || before < 0)" in planning
        # Which way round an edge is walked comes off the predecessor, not off
        # the edge's own ends: fourteen edges in this graph begin and end at the
        # same node and say nothing about direction.
        assert "graph.fromNode[used] !== before" in planning

    def test_a_crossing_carries_no_profile(self):
        """Not a flat line at zero, which is a claim about ground that is not
        there. The same rule a ferry chain follows in the panel."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "kind: CROSSING" in planning
        assert "kind: 'water'" in planning
        # Both are written with no series at all rather than with an empty one.
        assert planning.count("height: null, distance: null, read: false") == 2

    def test_the_kinds_it_classifies_by_come_from_the_build(self):
        """A ferry and an inferred connector are named in
        :mod:`trails.routing.sources`, and the page tests every edge it routes
        over against both names. Spelled in the page, a rename there would leave
        it counting a crossing as walked ground and nothing would look wrong."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned(crossingKind=FERRY, connectorKind=BRIDGE))

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "var CROSSING = PLAN.crossingKind, CONNECTOR = PLAN.connectorKind;" in planning
        assert f'"crossingKind": "{FERRY}"' in fmap.get_root().render()
        assert f'"connectorKind": "{BRIDGE}"' in fmap.get_root().render()

    def test_the_route_is_laid_out_in_one_walk_and_not_two(self):
        """The profile is drawn from heights against distance and the file is
        written from vertices, and two walks over one route would eventually
        disagree while each still looked like a route."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        # One walk, which a stage narrows rather than repeats: a second walk
        # over a range would be the same failure at a smaller scale.
        assert planning.count("function composeRoute(fromLeg, toLeg)") == 1
        # The shape a chain's series has, which is what the writer reads.
        for field in ("lon:", "lat:", "along:", "height:", "distance:", "stretches:"):
            assert field in planning.split("function composeRoute(fromLeg, toLeg)")[-1], field

    def test_a_crossing_ends_a_stretch_and_an_unread_sample_does_not(self):
        """The two kinds of NaN mean opposite things: no ground under a
        crossing, against ground with no reading of it. The first has to break
        the track and the second may only drop an ``<ele>``, so the boundary is
        recorded where it happens rather than inferred from a repeated
        distance."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function breakHere()" in planning
        # A crossing closes the stretch; a NaN height inside one is only a NaN.
        assert "crossed += part.length;" in planning
        assert "breakHere();" in planning

    def test_what_a_route_is_made_of_is_summed_per_edge(self):
        """A part keeps its geometry and its heights, and nothing downstream can
        get back to which edge a metre came from."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function tallyOf(graph, list)" in planning
        assert "graph.header.waymarked[graph.waymarked[edge]]" in planning
        assert "graph.noPathRecorded[edge]" in planning

    def test_unknown_is_never_folded_into_unmarked(self):
        """Measured over the walked network without its connectors, 63.4 % of
        the length is unknown and FKB — the largest source at 33.8 % — carries
        no marking field at all. Calling that unmarked asserts what no source
        says, and a connector nobody drew was never asked at all."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "var MARKING = ['marked', 'unmarked', 'unknown'];" in planning
        assert "var TALLIED = MARKING.concat(['undrawn', 'recorded', 'unrecorded']);" in planning
        # And the fifth, which phase 8 adds beside `undrawn` and for the same
        # reason: no register was asked about ground read off a loaded file.
        assert "tally.recorded = run;" in planning
        # A state the payload names and this page has no bucket for is a defect,
        # not a fourth silent bucket created by an index into an object.
        assert "the payload names a marking state this page has no bucket for" in planning

    def test_the_four_kinds_are_all_there_from_the_first_line(self):
        """A model that knew only routed legs would have to be widened the first
        time a ferry or a strait turned up, and both turn up here."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        for kind in ("routed", "land", "water", "ferry"):
            assert f"{kind}:" in planning or f"'{kind}'" in planning, kind

    def test_a_crossing_is_priced_as_a_whole_crossing(self):
        """Noding cuts a ferry wherever something meets it: 15 of the 21 ferry
        chains here are in several pieces and the longest is in seven. Charging
        the flat figure per edge priced that one at 35 km of walking instead of
        5, and a page that does so refuses crossings the build called
        affordable. trails.routing.graph._cost splits it the same way."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "source.flatM * (whole[i] > 0 ? length[i] / whole[i] : 1)" in planning

    def test_a_leg_drawn_straight_has_a_stated_ceiling(self):
        """Sampling is fixed at the build's step, so the only way to bound what
        one misclick asks of a public service is to bound the leg — and to say
        so, because coarsening instead would make the two halves of one profile
        answer differently with nothing looking wrong."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "length > PLAN.maxStraightM" in planning
        assert "is further than a leg may be drawn straight" in planning

    def test_one_refused_batch_stops_the_rest(self):
        """Once a leg has given up there is nothing left to use, and a page that
        carries on fetching the remainder is the opposite of the restraint the
        concurrency is set for."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "if (stopped || next >= batches.length)" in planning

    def test_the_legs_follow_from_the_waypoints_rather_than_being_edited(self):
        """Four edits and one rule. A leg survives exactly when it still runs
        between the same two waypoint objects, so inserting costs the two legs
        that replace one, removing costs the one that replaces two, and moving a
        point costs the three that touch it — and nothing has to work out which
        legs an edit invalidated, which is the arithmetic all four would
        otherwise get wrong in four different ways."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function relink(graph, mayAsk)" in planning
        assert "kept[k].from === points[i] && kept[k].to === points[i + 1]" in planning
        for edit in ("function insert(at, lat, lon, trackAt)", "function remove(at)", "function moveBy(at, step)"):
            assert edit in planning, edit
        # And a waypoint that has moved is a new object, so a drag needs no
        # case of its own in the rule above.
        assert "points[dragging.at] = snapped(held, where.lat, where.lng);" in planning

    def test_a_reply_about_ground_a_waypoint_has_left_is_dropped(self):
        """The whole of the cancellation, and it has to be: a drag settles eight
        times a second and every settle replaces the legs beside the point. A
        leg drawn from an answer that is no longer wanted is a route that
        disagrees with its own waypoints."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "if (legs.indexOf(leg) < 0) { return; }" in planning

    def test_a_live_drag_asks_the_height_service_for_nothing(self):
        """The cache is keyed on ends already visited and the ground under a
        dragged waypoint is new at every position, so a free leg fetched per
        mouse move is an uncapped stream of requests to somebody else's service
        — the shape 6B's review already found once and capped at 20 km. The leg
        is carried at its own straight length instead, and counts as unsettled
        so no file is written from it."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function heightsFor(from, to, mayAsk)" in planning
        assert "if (!mayAsk) { return null; }" in planning
        assert "relink(held, false);" in planning
        assert "function waitingParts(from, to)" in planning
        assert "provisional: true" in planning
        assert "return leg.provisional || (!leg.parts && !leg.failed);" in planning

    def test_a_drag_is_throttled_and_settles_where_the_pointer_stopped(self):
        """Placing a point costs 19-76 ms with its Dijkstra, so two legs is 40
        to 160 ms; run at the rate a pointer reports, that is three of them
        queued per frame. There was no throttle anywhere in plan mode before
        this — the only setTimeout near it was the search box's."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "var DRAG_EVERY_MS = 120;" in planning
        # A trailing settle, or the position the hand came to rest at is never
        # the one the route is worked out from.
        assert "dragging.timer = setTimeout(" in planning
        assert "clearTimeout(dragging.timer)" in planning

    def test_the_free_leg_cache_is_keyed_on_the_pair_and_bounded(self):
        """Moving a point one place past its neighbour turns exactly one leg
        round, so a cache that told A-to-B from B-to-A would fetch ground the
        page is already holding. And a drag leaves one leg's samples behind
        every time the pointer is let go, which is what a cache kept for the
        life of the page could not do before."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function forwards(from, to) { return endKey(from) <= endKey(to); }" in planning
        assert "function mirrored(answered)" in planning
        assert "var ASKED_MOST = 64;" in planning
        assert "while (askedKeys.length > ASKED_MOST) { delete asked[askedKeys.shift()]; }" in planning

    def test_a_click_on_the_route_is_hit_tested_and_never_caught(self):
        """An interactive route would have to stop catching clicks the moment
        plan mode is switched off, or it would stand between a reader and the
        trail underneath it — the mistake the park boundary made for a
        fortnight. The leg a click landed on is found in the geometry the page
        already holds instead, in the one handler every click goes through."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "pane.style.pointerEvents = 'none';" in planning
        assert planning.count("interactive: false") == 1
        assert "function onRoute(lat, lon)" in planning
        assert "var ON_ROUTE_PX = 8;" in planning
        # Pin, then route, then a point on the end: a pin sits on the route.
        decided = planning.split("container.addEventListener('click'")[-1]
        assert decided.index("closest('.trails-plan-pin')") < decided.index("onRoute(where.lat")
        assert decided.index("onRoute(where.lat") < decided.index("place(where.lat")

    def test_a_click_on_a_pin_selects_it_rather_than_deleting_it(self):
        """The same click is a few pixels from one that places a point and
        there is no way back from a deletion. What a selection makes possible
        has to be visible anyway: dragging a pin says nothing about where it
        comes in the sequence, so reordering needs a gesture of its own."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "chosen = chosen === at ? -1 : at;" in planning
        assert "moveBy(chosen, -1)" in planning and "moveBy(chosen, 1)" in planning
        assert "remove(chosen)" in planning

    def test_the_pins_are_written_as_differences(self):
        """Rebuilding a layer per keystroke and writing a style already set have
        each frozen this map on their own, and a drag does it several times a
        second. What was written is kept beside the pin rather than read back:
        an element answers 'rgb(17, 17, 17)' to a '#111111' just set to it."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "if (element && record.label !== label)" in planning
        # Whether it is picked and whether it ends a stage, both compared
        # against what was last written rather than read back off the element:
        # a style set to '#111111' reads back as 'rgb(17, 17, 17)'.
        assert "if (element && (record.picked !== picked || record.ends !== ends))" in planning
        # And the marker under the pointer is never written back to, or it
        # fights the hand moving it.
        assert "if (dragging && dragging.at === i) { continue; }" in planning

    def test_a_plan_is_kept_as_the_file_the_page_already_writes(self):
        """A reload threw the plan away, which is the one thing a reader cannot
        get back by clicking again. What is kept is the GPX the download button
        offers and it comes back through the picker's own reader — a shorter
        payload of its own would be a second recording of one decision, which is
        how the file name, the mode wording and the ascent all came apart."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "var made = panel().routeFile(figuresOf(shape), shape, told(shape), plan);" in planning
        assert "window.localStorage.setItem(keptKey(), made.text);" in planning
        assert "loadGpx(text, 'asis');" in planning

    def test_the_key_outlives_a_build(self):
        """folium hashes the container's id afresh every time the page is
        written, so a plan keyed on that would be thrown away on every deploy —
        the one moment a reader would least expect to lose something."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "return 'trails.plan.' + (prefix || 'map');" in planning
        assert "var prefix = panel() ? panel().prefix() : null;" in planning

    def test_a_full_quota_is_said_and_not_swallowed(self):
        """A reader who believes their plan is being kept and finds it gone is
        worse off than one who was told it is too large to keep."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "refused.name === 'QuotaExceededError'" in planning
        assert "too large to keep in this browser" in planning
        # And a payload that cannot be read is let go of once, or the page fails
        # the same way on every load with no way for a reader to clear it.
        assert "could not be read, so it has been let go." in planning

    def test_the_plan_is_written_when_the_editing_stops_and_when_the_tab_goes(self):
        """A drag refreshes at the rate the pointer reports, and a phone closes
        tabs without asking — iOS delivers no beforeunload at all."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "keptWhen = setTimeout(writeKept, KEEP_AFTER_MS);" in planning
        assert "window.addEventListener('pagehide'" in planning

    def test_the_whole_tour_is_offered_where_the_route_is_made(self):
        """The panel over the profile writes exactly this file and has always
        offered it — but on a narrow screen that panel is not on the screen by
        default, so a reader planning on a phone had no way to the one file they
        came for. One writer asked from three places: this button, the profile's
        own, and the archive's tour member."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "oneFile.textContent = 'Whole tour (GPX)';" in planning
        assert "var made = panel().routeFile(figuresOf(shape), shape, told(shape), writable());" in planning
        # Why it is refused, where it is: 'still working out 2 legs' is the
        # difference between a button that is waiting and one that is broken.
        assert "oneFile.title = refusing ||" in planning

    def test_a_plan_that_comes_back_on_its_own_has_a_way_out(self):
        """A kept plan is restored on every load until there is nothing left to
        restore, and emptying a twenty-point route a point at a time is not a
        way out. It goes through the same edit funnel as every other change, so
        undo brings it back — which is what makes a button that clears the map
        safe to offer."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "fresh.textContent = 'Start again';" in planning
        assert "points.length = 0;" in planning
        # The recording goes with it: a waypoint anchored to a file nobody is
        # working from is a point looked up in the wrong track.
        assert "loaded = null;" in planning

    def test_the_list_is_capped_by_the_room_and_not_by_a_constant(self):
        """It was 220 px whatever the screen: a twelve-point route scrolled
        inside a panel with 350 px of room under it, and running off the end of
        that scroller is what handed the wheel to the map."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "listBox.style.maxHeight = Math.max(40, room - fixed) + 'px';" in planning

    def test_a_wheel_over_a_panel_does_not_end_in_a_zoom(self):
        """Each scroller inside takes what it can use and the outermost panel
        swallows the rest. Where the chrome holds this control the chrome is that
        boundary; where there is none, this box is."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "if (!box.closest || !box.closest('.trails-chrome')) { event.stopPropagation(); }" in planning

    def test_a_page_without_a_panel_says_so_rather_than_throwing(self):
        """Plan mode composes with the walk the panel owns, so a page carrying
        one and not the other can plan nothing — said once, loudly."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()
        assert "console.error('plan mode: there is no profile panel" in html


class TestRoutingGraphAreas:
    """Tests for the boundaries the page is handed with the graph."""

    def rendered(self, areas: list[dict[str, object]]) -> str:
        """A page carrying a graph header with these areas in it.

        Args:
            areas: What the header says is protected

        Returns:
            The rendered page
        """
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_routing_graph(fmap, {"version": 3, "edges": 0, "protected": areas}, "")
        return fmap.get_root().render()

    def test_the_test_is_bound_before_the_stream_is_inflated(self):
        """It needs nothing from the stream — the outlines are in the header —
        and a caller asking what protects a position should not wait for two
        million coordinates it is not going to look at."""
        html = self.rendered([])

        assert "graph.areasAt = areasAt.bind(null, graph.protectedAreas)" in html
        assert html.index("graph.areasAt = areasAt") < html.index("graph.ready = inflate")

    def test_an_area_carries_its_outline_and_its_box(self):
        """The box settles thirty of thirty-one areas in four comparisons, and
        only then are four thousand vertices walked."""
        area = {"id": "VV0001", "name": "Somewhere", "form": "naturreservat", "bounds": [12.0, 65.0, 13.0, 66.0], "rings": [[[12.0, 65.0]]]}
        html = self.rendered([area])

        assert "VV0001" in html
        assert "areas[a].bounds" in html
        assert "areas[a].rings" in html

    def test_a_page_without_a_protected_list_still_answers(self):
        """An older payload, or a build over ground nothing protects."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_routing_graph(fmap, {"version": 3, "edges": 0}, "")

        assert "header.protected || []" in fmap.get_root().render()


class TestComposedProfile:
    """Tests for the second way into the panel, which a planned route uses."""

    def drawn(self) -> folium.Map:
        """A map carrying one chain and the panel."""
        gdf = gpd.GeoDataFrame(
            {"chain_id": ["ut-no-1-2-3"], "ascent": [996.4], "geometry": [LineString([(12.8, 65.4), (12.81, 65.41)])]},
            crs="EPSG:4326",
        )
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        layer = maps.add_trails(fmap, gdf, name="Chains", group_field="chain_id", figure_fields={"ascent": "ascent"})
        maps.add_profile_panel(fmap, [layer])
        return fmap

    def test_the_panel_offers_a_second_way_in(self):
        """A planned route has no chain and no row in the figures table."""
        html = self.drawn().get_root().render()
        assert "window.trailsProfilePanel" in html
        assert "series: function (spec)" in html
        assert "suspend: function (taken)" in html

    def test_one_walk_and_one_metre_are_handed_out_rather_than_copied(self):
        html = self.drawn().get_root().render()
        assert "layEdges: layEdges" in html
        assert "metresBetween: metresBetween" in html

    def test_a_composed_route_is_offered_as_a_file(self):
        """Phase 6 withheld the button because writing a plan out was its own
        phase. This is that phase, and restoring it is its visible outcome."""
        html = self.drawn().get_root().render()
        assert "function routeGpxOf(figure, shape, runs, plan, extra, crossings)" in html
        assert "saveFile(fileNameOf((selected.plan.stem) || EXPORT.route.fileStem)," in html

    def test_the_name_rides_with_the_bytes_and_not_only_on_the_anchor(self):
        """iOS Safari saves a `blob:` URL under the blob's own identifier and
        ignores `a.download`, which is a reader getting a line of hex where the
        tour should be — reported from the device, on a file this page had
        already named correctly. A `File` carries the name itself."""
        html = self.drawn().get_root().render()
        assert "new File([body], name, {type: type})" in html
        assert "anchor.download = name;" in html

    def test_a_finger_is_offered_the_share_sheet_and_canshare_has_no_veto(self):
        """How a phone saves anything, and the one route that keeps the name
        whatever the browser does with the anchor. `canShare` used to gate it and
        does not any more: reported from a device, iOS Firefox still named the
        file after the blob while Chrome on the same phone — the same WebKit —
        got it right, and the cost of asking anyway is one rejected promise
        whose answer is the anchor the reader was already on."""
        html = self.drawn().get_root().render()
        assert "navigator.share({files: [file]})" in html
        # The call, not the word: the comment above the gate explains why it
        # is gone, and a test that forbids the word forbids the explanation.
        assert "canShare({files:" not in html
        # A closed sheet is not a failure, and saving the file anyway would be
        # doing something nobody asked for.
        assert "if (failure && failure.name === 'AbortError') {" in html

    def test_a_reader_is_told_when_the_name_could_not_be_carried(self):
        """They are about to find a file named after a blob. The browser would
        not take it through a sheet and does not carry a name on a download
        either; the one thing left is to say what it was meant to be called."""
        html = self.drawn().get_root().render()
        assert "This browser named the download itself" in html
        assert "saveSaid = 'anchor after '" in html

    def test_the_button_most_routes_are_downloaded_with_names_the_tour(self):
        """It named none of them. This button took the export's own stem
        outright, so every route came off it as `-route.gpx` however carefully
        the tour had been named, while the stage buttons two panels away read
        `stem` and got it right. `stem` is the file's name; the export's stem is
        what a tour nobody named falls back to."""
        html = self.drawn().get_root().render()
        assert "saveFile(fileNameOf(EXPORT.route.fileStem)," not in html

    def test_the_file_says_what_the_panel_above_the_button_says(self):
        """One sentence written once. Handed `plan` instead of what the panel was
        told, the file quietly dropped the route's crossings from its own
        description while the panel went on showing them — a file that is
        plausible and silent about the one thing it breaks its track for."""
        html = self.drawn().get_root().render()
        assert "planned(figure, shape, extra).concat([markingLine(shape.tally)])" in html
        assert "routeGpxOf(selected.figure, selected.shape, selected.runs, selected.plan, selected.told, crossings())" in html

    def test_a_series_composed_without_a_description_is_not_offered(self):
        """The file has to say what its legs are and where its waypoints went. A
        button this panel could not honour is worse than no button at all."""
        html = self.drawn().get_root().render()
        assert "offer.style.display = (selected && (!selected.composed || selected.plan)) ? 'block' : 'none';" in html

    def test_a_route_with_a_hole_in_it_is_refused_and_said(self):
        """The file states that it breaks its track only at crossings. A leg
        still being worked out, or one the height service refused, would break
        it somewhere else with nothing in the file to say so."""
        html = self.drawn().get_root().render()
        assert "download.disabled = points < 2 || !!selected.plan.why;" in html
        assert "if (!selected.plan || selected.plan.why) { return; }" in html

    def test_the_panel_stops_answering_clicks_while_something_else_owns_them(self):
        html = self.drawn().get_root().render()
        assert "if (suspended) { return; }" in html
        assert "if (!suspended) { show(null); }" in html

    def test_a_straight_stretch_is_dashed_in_the_curve(self):
        """The profile has to say the same thing the map does about the same
        ground, and a chain is never any of it."""
        html = self.drawn().get_root().render()
        assert "FREE_DASH" in html
        assert "current.free !== free" in html
        assert "drawn straight, not a path" in html

    def test_the_crossings_are_read_off_the_series_the_file_is_written_from(self):
        """The one series in this page with a point every few metres over the
        whole route. The vertices alone are a source's own corners, and a leg
        drawn straight has two of them for twenty kilometres."""
        html = self.drawn().get_root().render()
        assert "function crossingsOf(shape, runs)" in html
        assert "routeGpxOf(selected.figure, selected.shape, selected.runs, selected.plan, selected.told, crossings())" in html

    def test_the_crossings_are_asked_for_rather_than_worked_out_every_refresh(self):
        """Measured: the boundary walk is 45 ms of a 50 ms refresh over a 37 km
        route and it grows with the route, while the only thing that needs it is
        a button a reader may never press. Cached against the selection, so the
        file and a check still get one answer."""
        html = self.drawn().get_root().render()
        assert "if (!selected.crossings) { selected.crossings = crossingsOf(selected.shape, selected.runs); }" in html
        assert "crossings: crossings" in html
        # And not in the row that is rebuilt on every click.
        assert "selected.runs = runsOf(selected.shape);\n                var points = pointsIn(selected.runs);" in html

    def test_only_the_areas_the_route_reports_get_a_marker(self):
        """The threshold is applied once, where the figures are, so a boundary
        grazed for ten metres cannot bring a pair of markers in through this
        door after the sentence above declined to mention it."""
        html = self.drawn().get_root().render()
        assert "(shape.protected || []).forEach(function (area) { reported[area.id] = area; });" in html
        assert "if (reported[id] && before.indexOf(id) < 0)" in html

    def test_a_boundary_marker_says_it_was_generated(self):
        """Phase 8 loads a file back and must never read a marker the map placed
        as a station somebody chose, or a loaded route gains points nobody put
        down and starts routing through them."""
        html = self.drawn().get_root().render()
        assert "EXPORT.waypoint.generated, crossing.id" in html
        assert "EXPORT.waypoint.set, null" in html

    def test_the_areas_are_written_as_figures_and_not_as_a_sentence(self):
        """A sentence has to be parsed back, and phase 8 has to know which
        boundary was meant rather than which words were written."""
        html = self.drawn().get_root().render()
        assert "EXPORT.route.areas" in html
        assert "EXPORT.route.areaId" in html
        assert "EXPORT.route.areaLength" in html

    def test_the_register_is_credited_wherever_a_file_states_one_of_its_figures(self):
        """A file naming a source it did not draw on is exactly as wrong as one
        leaving a source out."""
        html = self.drawn().get_root().render()
        assert ".concat((shape.protected || []).length ? EXPORT.protected : []);" in html

    def test_what_protects_the_route_is_said_once_and_shown_twice(self):
        """The sentence above the button and the sentence in the file are one
        sentence, so the areas go into `planned` rather than beside it."""
        html = self.drawn().get_root().render()
        assert ".concat(extra || []).concat(protectedIn(shape));" in html
        assert "function protectedIn(shape)" in html

    def test_the_metre_is_the_ellipsoid_and_not_a_sphere(self):
        """Measured over 4,000 real edges: the sphere read 0.56 % short, which
        is 900 m on a 160 km route stating its own distance. Nothing scales a
        planned route onto a length it carries, because it carries none."""
        html = self.drawn().get_root().render()
        assert "111132.92" in html
        assert "111412.84" in html
        assert "110574" not in html


class TestLegend:
    """The legend, which is also the map's layer control."""

    @staticmethod
    def points(show=True):
        """A one-point layer to hang a legend row on."""
        return gpd.GeoDataFrame({"name": ["Hut"]}, geometry=[Point(13.0, 65.5)], crs="EPSG:4326"), show

    def test_legend_renders_entries(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(fmap, "Lomsdal-Visten", {"Turrutebasen": "#1b5e20"})

        html = fmap.get_root().render()
        assert "Lomsdal-Visten" in html
        assert "#1b5e20" in html

    def test_a_row_given_a_layer_switches_it(self):
        """The legend replaced the layer control, so this is the only thing on
        the page that can put a layer on the map or take it off."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        gdf, _ = self.points()
        layer = maps.add_points(fmap, gdf, name="Huts")
        maps.add_legend(fmap, "Legend", [maps.LegendRow("Huts (1)", "#800080", layer)])

        html = fmap.get_root().render()
        assert "tick.type = 'checkbox';" in html
        assert "if (tick.checked) { map.addLayer(layer); } else { map.removeLayer(layer); }" in html
        assert layer.get_name() in html.split("var layers = [")[1].split("]")[0]

    def test_a_row_without_a_layer_switches_nothing(self):
        """A mapping still gives a legend that only explains colours, and those
        rows keep the checkbox's width so the labels line up with the ones that
        have a box."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(fmap, "Legend", {"Turrutebasen": "#1b5e20"})

        html = fmap.get_root().render()
        assert "var layers = [null];" in html
        assert "width:13px;flex:none" in html

    def test_a_layer_that_starts_off_is_taken_off(self):
        """**Folium's layer control did this in its own template**, so with that
        control gone the legend has to: a layer added with show=False is on the
        map like any other until something removes it."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        gdf, _ = self.points()
        layer = maps.add_points(fmap, gdf, name="Huts", show=False)
        maps.add_legend(fmap, "Legend", [maps.LegendRow("Huts (1)", "#800080", layer)])

        html = fmap.get_root().render()
        assert '"shown": false' in html
        assert "if (!row.shown && map.hasLayer(layer)) { map.removeLayer(layer); }" in html

    def test_the_base_maps_become_radio_buttons(self):
        """And only the one asked for stays on the map, for the same reason:
        folium hands every base layer to the map and left the unwanted ones to
        the control's template."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(fmap, "Legend", {"x": "#000000"})

        html = fmap.get_root().render()
        assert '["Kartverket Topo", "Kartverket Grayscale"]' in html
        assert "[true, false]" in html
        assert "pick.type = 'radio';" in html
        assert "if (!baseShown[index] && map.hasLayer(layer)) { map.removeLayer(layer); }" in html

    def test_nothing_else_adds_a_layer_control(self):
        """Two controls over one list is two places to look and two to drift."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(fmap, "Legend", {"x": "#000000"})

        assert not [child for child in fmap._children.values() if isinstance(child, folium.LayerControl)]
        assert not hasattr(maps, "finalize")

    def test_a_switched_off_row_says_so(self):
        """A colour for something not on the map is still the key to that
        colour, but it is not speaking for the terrain."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(fmap, "Legend", {"x": "#000000"})

        html = fmap.get_root().render()
        assert "row.line.style.opacity = (row.layer && !map.hasLayer(row.layer)) ? '0.45' : '';" in html

    def test_the_wheel_is_the_map_s_where_the_list_cannot_scroll(self):
        """A list this long that will not scroll is as useless as a map that
        will not zoom, and only one of the two can have any one turn."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(fmap, "Legend", {"x": "#000000"})

        html = fmap.get_root().render()
        assert "var room = box.scrollHeight - box.clientHeight;" in html
        assert "if (room <= 0) { return; }" in html


class TestTextLabelColours:
    """Tests for per-label colouring in add_text_labels."""

    @pytest.fixture
    def typed_names(self) -> gpd.GeoDataFrame:
        """A river and a valley with their own colours, plus one without."""
        return gpd.GeoDataFrame(
            {
                "name": ["Vefsna", "Eiterådalen", "Namnlaus"],
                "color": ["#0288d1", "#6d4c41", None],
                "geometry": [Point(13.1, 65.7), Point(13.14, 65.6), Point(13.2, 65.5)],
            },
            crs="EPSG:4326",
        )

    def _html(self, group) -> list[str]:
        """Collect the rendered HTML of every label in a group."""
        markers = [child for child in group._children.values() if isinstance(child, folium.Marker)]
        icons = [next(c for c in m._children.values() if isinstance(c, folium.DivIcon)) for m in markers]
        return [icon.options["html"] for icon in icons]

    def test_colour_field_sets_each_label_individually(self, typed_names):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, typed_names, name="Names", color_field="color")

        html = " ".join(self._html(group))
        assert "color:#0288d1" in html
        assert "color:#6d4c41" in html

    def test_missing_colour_falls_back_to_the_default(self, typed_names):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, typed_names, name="Names", color_field="color", color="#455a64")

        assert any("color:#455a64" in html for html in self._html(group))

    def test_without_a_colour_field_all_labels_share_one_colour(self, typed_names):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, typed_names, name="Names", color="#37474f")

        assert all("color:#37474f" in html for html in self._html(group))


class TestLegendEscaping:
    """Legend text must survive characters that would otherwise start a tag."""

    def test_a_label_that_would_start_a_tag_stays_a_label(self):
        """The map's own legend reads "Paths, approach ≤15 km". Built as markup
        the browser would read "<15 km ..." as a tag and drop the whole row, so
        a label is written as text and can no longer make markup at all.
        """
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(fmap, "Legend", {"Paths, approach <15 km [OSM] (1965)": "#ce93d8"})

        html = fmap.get_root().render()
        assert "name.textContent = row.label;" in html
        # It survives whole, and as an escape rather than as a live "<".
        assert "Paths, approach \\u003c15 km [OSM] (1965)" in html
        assert "approach <15 km" not in html

    def test_boundary_does_not_intercept_clicks(self, park):
        """It is drawn last, so an interactive fill would swallow every trail click."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_boundary(fmap, park, name="National park")

        assert '"interactive": false' in fmap.get_root().render()

    def test_title_cannot_inject_markup(self):
        """The heading is written as text, so markup in it stays text."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(fmap, "A <b>bold</b> title", {"x": "#000000"})

        html = fmap.get_root().render()
        assert "<b>bold</b>" not in html
        assert "bold" in html

    def test_nothing_can_close_the_script_block(self):
        """A value carrying </script> would end the block and start markup."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(fmap, "T </script><img src=x>", {"Also </script> here": "#000000"})

        html = fmap.get_root().render()
        assert "</script><img" not in html
        assert "\\u003c/script>" in html

    def test_popup_values_are_escaped(self, trails):
        row = trails.iloc[0].copy()
        row["trail_name"] = "Sti <b>merket</b>"

        html = maps._build_popup(row, {"trail_name": "Route"})
        assert "&lt;b&gt;merket&lt;/b&gt;" in html

    def test_label_text_is_escaped(self):
        gdf = gpd.GeoDataFrame({"name": ["Dal <test>"], "geometry": [Point(13.1, 65.6)]}, crs="EPSG:4326")
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, gdf, name="Names")

        marker = next(child for child in group._children.values() if isinstance(child, folium.Marker))
        icon = next(c for c in marker._children.values() if isinstance(c, folium.DivIcon))
        assert "&lt;test&gt;" in icon.options["html"]


class TestTextLabelSymbols:
    """Tests for the glyph drawn before a label."""

    @pytest.fixture
    def typed_names(self) -> gpd.GeoDataFrame:
        """A valley and a river with glyphs, plus one without."""
        return gpd.GeoDataFrame(
            {
                "name": ["Eiterådalen", "Vefsna", "Namnlaus"],
                "symbol": ["∨", "≈", None],
                "geometry": [Point(13.14, 65.6), Point(13.1, 65.7), Point(13.2, 65.5)],
            },
            crs="EPSG:4326",
        )

    def _html(self, group) -> list[str]:
        """Collect the rendered HTML of every label in a group."""
        markers = [child for child in group._children.values() if isinstance(child, folium.Marker)]
        icons = [next(c for c in m._children.values() if isinstance(c, folium.DivIcon)) for m in markers]
        return [icon.options["html"] for icon in icons]

    def test_symbol_precedes_the_name(self, typed_names):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, typed_names, name="Names", symbol_field="symbol")

        assert any("∨ Eiterådalen" in html for html in self._html(group))
        assert any("≈ Vefsna" in html for html in self._html(group))

    def test_missing_symbol_leaves_the_name_alone(self, typed_names):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, typed_names, name="Names", symbol_field="symbol")

        assert any(">Namnlaus</div>" in html for html in self._html(group))

    def test_no_symbol_field_means_plain_names(self, typed_names):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, typed_names, name="Names")

        assert all(" " not in html for html in self._html(group))

    def test_symbols_are_escaped_like_the_name(self, typed_names):
        gdf = typed_names.copy()
        gdf.loc[0, "symbol"] = "<b>"
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, gdf, name="Names", symbol_field="symbol")

        assert any("&lt;b&gt;" in html for html in self._html(group))


class TestChrome:
    """Tests for the rail, the burger, and the one sheet under both."""

    def test_one_sheet_holds_whatever_is_read_in_it(self):
        """A popup docks here and so does anything else the page has that is to
        be read rather than glanced at. Two full-screen surfaces on a phone
        would be two things that have to agree about which is on top, which is
        the defect this chrome exists to end — so it is written once and called
        from both."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "function readInSheet(title, content, asHtml, key)" in html
        assert "readInSheet(titleFor(popup), content, true, 'popup')" in html
        assert "detail: function (title, node, key) { readInSheet(title, node, false, key); }," in html
        # A popup's content is markup and a caller's string is text, told apart
        # by the caller rather than sniffed at: the day something guesses is the
        # day a place name with an ampersand in it becomes an element.
        assert "if (asHtml) { wrap.innerHTML = content; } else { wrap.textContent = content; }" in html

    def test_the_last_one_opened_is_the_one_drawn(self):
        """On a narrow screen the dock, the menu and the detail are one
        full-screen sheet and only one may be drawn. Which one used to be fixed —
        a tool always covered the detail — so a reader pressing the panel's own
        *i* watched the plan panel go and got nothing back when they closed the
        sheet."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "function raise(what) { opening += 1; opened[what] = opening; }" in html
        assert "var top = narrow ? topmost() : null;" in html
        # And the sheet dismisses nothing: what it covers on a narrow screen it
        # gives back when it closes.
        assert "openTool = null;\n                menuOpen = false;\n                paintRail();" not in html
        assert "closeDetail: function () { closeSheet(); }," in html

    def test_one_state_decides_whether_the_profile_stands(self):
        """Three places offer the switch — the rail, the plan bar and the plan
        control — and a second flag beside this one is two switches that can
        disagree. Three values and not two: null means nobody has said, and the
        default then depends on where the reader is."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "profileAsked = (want === undefined || want === null) ? !profileOn() : !!want;" in html
        assert "return profileAsked === null ? profileDefault() : profileAsked;" in html
        # While planning on a narrow screen the map is what is being tapped.
        assert "return !(map.getSize().x < NARROW && planOn());" in html
        assert "profile: function (want) {" in html

    def test_the_rail_takes_the_corner_the_burger_already_has(self):
        """It stood at the left and pushed Leaflet's whole top-left corner 56 px
        aside to make room — which put the zoom buttons at 66, exactly where the
        dock opened, so every tool a reader opened covered the zoom. Moved to the
        right it needs room from nobody, and nothing touches a corner it did not
        make."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "rail.style.cssText = 'position:absolute;right:10px;top:10px;width:46px" in html
        assert "corner.style.marginLeft" not in html
        assert "dock.style.right = '66px';" in html


class TestTheme:
    """Tests for the two sets of colours the furniture is drawn from."""

    def test_three_blocks_and_not_two(self):
        """A web page has three theme states, not two: an explicit choice stamps
        `data-theme` on the root and the default setting stamps nothing at all,
        so `prefers-color-scheme` alone separates light from dark for most
        readers while a stamped choice has to beat it in both directions."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))

        html = fmap.get_root().render()
        assert ":root {" in html
        assert "@media (prefers-color-scheme: dark)" in html
        assert ':root:not([data-theme="light"])' in html
        assert ':root[data-theme="dark"]' in html
        # Native controls — the legend's checkboxes, the search field — are the
        # browser's to paint, and this is how it is told which set to use.
        assert "color-scheme: dark;" in html

    def test_the_data_keeps_its_own_colours(self):
        """The four gradient bands, the route's black and the sea line are
        statements about the ground, not furniture. Green meaning *gentle* in the
        morning and something else at night would be the drawing lying to keep up
        with the panels."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        gdf = gpd.GeoDataFrame(
            {
                "chain_id": ["ut-no-1-2-3"],
                "ascent": [996.4],
                "geometry": [LineString([(12.8, 65.4), (12.81, 65.41)])],
            },
            crs="EPSG:4326",
        )
        layer = maps.add_trails(fmap, gdf, name="Chains", group_field="chain_id", figure_fields={"ascent": "ascent"})
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        for _, _, colour, _ in maps.GRADIENT_BANDS:
            assert colour in html
        assert "var ROUTE = '#111111'" in html or "'#111111'" in html
        assert "var SEA = '#4fa3c7';" in html

    def test_the_panels_say_their_own_ink(self):
        """Not one of them set a `color`: they inherited the document's black,
        which is right on a white panel and 1.4:1 on a dark one — measured in a
        browser, which is the only place it could have been."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))

        html = fmap.get_root().render()
        assert ".trails-profile-panel, .trails-plan-control, .trails-legend, .trails-search," in html
        assert "color: var(--trails-ink);" in html
