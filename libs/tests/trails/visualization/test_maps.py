"""Tests for Folium map building."""

import folium
import geopandas as gpd
import pytest
from shapely.geometry import LineString, MultiLineString, Point, Polygon
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

    def test_title_is_escaped(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(fmap, "A <b>bold</b> title", {"x": "#000000"})

        assert "&lt;b&gt;bold&lt;/b&gt;" in fmap.get_root().render()

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
