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
        maps.finalize(fmap)

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
        maps.finalize(fmap)

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

        assert "trails-profile-panel" not in fmap.get_root().render()

    def test_without_figures_nothing_is_added(self):
        """A layer nobody measured has no profile to offer."""
        gdf = gpd.GeoDataFrame({"chain_id": ["a"], "geometry": [LineString([(12.8, 65.4), (12.81, 65.41)])]}, crs="EPSG:4326")
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        layer = maps.add_trails(fmap, gdf, name="Chains", group_field="chain_id")
        maps.add_profile_panel(fmap, [layer])

        assert "trails-profile-panel" not in fmap.get_root().render()

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

    def test_it_draws_nothing_on_the_map(self):
        """The route belongs in a pane of its own: anything drawn into the
        overlay pane is counted among the map's paths for ever after, and 11,589
        is an acceptance figure for every phase from the third."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())
        maps.finalize(fmap)

        assert not [child for child in fmap._children.values() if isinstance(child, folium.GeoJson | folium.Marker)]
        html = fmap.get_root().render()
        assert "createPane('trailsPlanRoute')" in html
        planning = html.split("var PLAN =")[-1]
        assert "pane: 'trailsPlanRoute'" in planning
        # Every layer it makes names that pane. One that did not would land in
        # the overlay pane by default, which is the whole thing being avoided.
        assert planning.count("L.polyline(") == planning.count("pane: 'trailsPlanRoute'") - planning.count("L.circleMarker(")

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
        assert planning.count("function composeRoute()") == 1
        # The shape a chain's series has, which is what the writer reads.
        for field in ("lon:", "lat:", "along:", "height:", "distance:", "stretches:"):
            assert field in planning.split("function composeRoute()")[-1], field

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
        assert "if (element && record.picked !== picked)" in planning
        # And the marker under the pointer is never written back to, or it
        # fights the hand moving it.
        assert "if (dragging && dragging.at === i) { continue; }" in planning

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
        assert "saveFile(fileNameOf(EXPORT.route.fileStem)," in html

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
        assert "offer.style.display = (selected && (!selected.composed || selected.plan)) ? '' : 'none';" in html

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


class TestLegendAndFinalize:
    """Tests for legend rendering and layer control."""

    def test_legend_renders_entries(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(fmap, "Lomsdal-Visten", {"Turrutebasen": "#1b5e20"})

        html = fmap.get_root().render()
        assert "Lomsdal-Visten" in html
        assert "#1b5e20" in html

    def test_finalize_adds_layer_control(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.finalize(fmap)

        controls = [child for child in fmap._children.values() if isinstance(child, folium.LayerControl)]
        assert len(controls) == 1


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

    def test_less_than_in_a_label_is_escaped(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(fmap, "Legend", {"Paths, approach <15 km [OSM] (1965)": "#ce93d8"})

        html = fmap.get_root().render()
        # Unescaped, the browser reads "<15 km ..." as a tag and drops the entry.
        assert "&lt;15 km" in html
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
