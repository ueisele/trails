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

    def test_the_waypoints_are_not_markers(self):
        """198 is the other acceptance figure, and a marker joins it for ever."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "L.marker(" not in planning
        assert "L.circleMarker(" in planning

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
        assert planning.count("://") == bare + 1
        assert planning.count("fetch(") == 1

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
        assert "kind: 'ferry'" in planning
        assert "kind: 'water'" in planning
        # Both are written with no series at all rather than with an empty one.
        assert planning.count("height: null, distance: null, read: false") == 2

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

    def test_a_page_without_a_panel_says_so_rather_than_throwing(self):
        """Plan mode composes with the walk the panel owns, so a page carrying
        one and not the other can plan nothing — said once, loudly."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()
        assert "console.error('plan mode: there is no profile panel" in html


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

    def test_a_composed_route_is_not_offered_as_a_file(self):
        """Writing a plan out is its own phase, and a button this panel could
        not honour is worse than no button."""
        html = self.drawn().get_root().render()
        assert "if (!selected || selected.composed) { return; }" in html

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
