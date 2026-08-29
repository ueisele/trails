"""Interactive Folium maps for trail data.

Builds layered maps that combine trail geometries, area boundaries and points of
interest. Every layer is toggleable so several data sources can be compared
visually::

    fmap = create_map(bounds=park.total_bounds, base=BaseMap.KARTVERKET_TOPO)
    add_boundary(fmap, park, name="National park")
    add_trails(fmap, trails, name="Turrutebasen", color="#1b5e20")
    fmap.save("map.html")
"""

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from html import escape
from typing import Any

import folium
import geopandas as gpd
import pandas as pd
from branca.element import MacroElement
from jinja2 import Template

from trails.routing import elevation

#: Bounding box as (min_lon, min_lat, max_lon, max_lat), matching GeoPandas.
Bounds = tuple[float, float, float, float]


class BaseMap(Enum):
    """Available base layers.

    ``KARTVERKET_TOPO`` is the Norwegian national topographic map and is the
    most useful backdrop for hiking.

    ``OPENSTREETMAP`` only works when the page is served over http(s):
    OSM's tile usage policy requires a Referer header, which browsers omit for
    ``file://`` URLs, so every tile comes back as an "Access blocked" image.
    """

    KARTVERKET_TOPO = "kartverket_topo"
    KARTVERKET_GRAYSCALE = "kartverket_grayscale"
    OPENSTREETMAP = "openstreetmap"


_KARTVERKET_ATTRIBUTION = '&copy; <a href="https://www.kartverket.no/">Kartverket</a>'

_BASE_LAYERS: dict[BaseMap, dict[str, str]] = {
    BaseMap.KARTVERKET_TOPO: {
        "tiles": "https://cache.kartverket.no/v1/wmts/1.0.0/topo/default/webmercator/{z}/{y}/{x}.png",
        "attr": _KARTVERKET_ATTRIBUTION,
        "name": "Kartverket Topo",
    },
    BaseMap.KARTVERKET_GRAYSCALE: {
        "tiles": "https://cache.kartverket.no/v1/wmts/1.0.0/topograatone/default/webmercator/{z}/{y}/{x}.png",
        "attr": _KARTVERKET_ATTRIBUTION,
        "name": "Kartverket Grayscale",
    },
    BaseMap.OPENSTREETMAP: {
        "tiles": "OpenStreetMap",
        "attr": "&copy; OpenStreetMap contributors",
        "name": "OpenStreetMap",
    },
}


def create_map(
    bounds: Bounds | None = None,
    center: tuple[float, float] | None = None,
    zoom: int = 10,
    base: BaseMap = BaseMap.KARTVERKET_TOPO,
    extra_bases: tuple[BaseMap, ...] = (BaseMap.KARTVERKET_GRAYSCALE,),
) -> folium.Map:
    """Create a Folium map focused on an area.

    Args:
        bounds: (min_lon, min_lat, max_lon, max_lat) to fit the view to
        center: (lat, lon) fallback when no bounds are given
        zoom: Initial zoom level, used only when fitting to bounds is skipped
        base: Base layer shown by default
        extra_bases: Additional base layers offered in the layer control. They
            are registered but not displayed until selected, otherwise Leaflet
            stacks them all and the last one wins.

    Returns:
        Folium map with base layers attached; call :func:`add_legend` when done
        adding overlays, which is what lists and switches them.

    Raises:
        ValueError: If neither bounds nor center is given
    """
    if bounds is None and center is None:
        raise ValueError("Either bounds or center must be provided")

    if center is None:
        assert bounds is not None
        min_lon, min_lat, max_lon, max_lat = bounds
        center = ((min_lat + max_lat) / 2, (min_lon + max_lon) / 2)

    # Base layers are attached explicitly rather than via Map(tiles=...), which
    # would label the layer control with the raw tile URL instead of the name.
    fmap = folium.Map(location=list(center), zoom_start=zoom, tiles=None, control_scale=True)

    for index, source in enumerate((base, *(extra for extra in extra_bases if extra is not base))):
        layer = _BASE_LAYERS[source]
        folium.TileLayer(
            tiles=layer["tiles"],
            attr=layer["attr"],
            name=layer["name"],
            overlay=False,
            control=True,
            show=index == 0,
        ).add_to(fmap)

    if bounds is not None:
        min_lon, min_lat, max_lon, max_lat = bounds
        fmap.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]])

    return fmap


#: Schemes a popup link may use. Anything else — ``javascript:`` above all —
#: would execute in the page as soon as a reader clicks a trail.
_LINK_SCHEMES = ("http://", "https://")

#: Prefix of the CSS class identifying which route a line belongs to.
_GROUP_CLASS_PREFIX = "trail-group-"

#: Anything outside this becomes a dash, so a route name or id always yields a
#: single valid CSS class token.
_CLASS_SAFE = re.compile(r"[^A-Za-z0-9_-]+")


def _group_class(value: object) -> str:
    """Build the CSS class marking every line of one route.

    Args:
        value: Identifying value, typically a route id or name

    Returns:
        A single CSS class token, distinct for distinct values
    """
    # A single null anywhere in an id column makes pandas store it as float, and
    # 1113860.0 would otherwise yield a different class than 1113860 — the same
    # route named differently depending on an unrelated row.
    if isinstance(value, float) and value.is_integer():
        value = int(value)

    text = str(value)
    token = _CLASS_SAFE.sub("-", text)
    if token != text:
        # "Bønå" and "Bønö" both flatten to "B-n-", which would silently merge two
        # routes into one selection, so anything reshaped keeps a digest of the
        # original. Plain ids pass through untouched.
        token = f"{token}-{hashlib.md5(text.encode()).hexdigest()[:6]}"
    return f"{_GROUP_CLASS_PREFIX}{token}"


#: Attribute under which a feature group carries the text its lines can be found
#: by. Leaflet path options accept no custom keys, so the names travel beside the
#: layer rather than on it, keyed by the class each path already carries.
SEARCH_NAMES_ATTR = "search_names"


def _record_search_names(group: folium.FeatureGroup, names: dict[str, str]) -> None:
    """Attach the searchable names of a layer to its feature group.

    Args:
        group: Feature group the names belong to
        names: Mapping of CSS class to the text it can be found by
    """
    setattr(group, SEARCH_NAMES_ATTR, names)


#: Attribute under which a feature group carries the named things it draws, as
#: a table rather than as popup HTML. The same mechanism as
#: :data:`SEARCH_NAMES_ATTR` and :data:`CHAIN_FIGURES_ATTR`, and needed for the
#: same reason: a Leaflet marker's name lives in the popup it was given, which
#: is a string of markup and not a lookup. Over two thousand points are drawn
#: here — huts, quays, trailheads, farms, settlements — and until this existed
#: nothing in the page could answer *what is at this position*.
#:
#: Opt-in per layer, through the ``point_type`` a caller passes: a place name
#: drawn as text rather than as a marker asserts no single position — a valley
#: has none — and a waypoint must not be named after one.
NAMED_POINTS_ATTR = "named_points"


def _record_named_points(group: folium.FeatureGroup, points: list[dict[str, object]]) -> None:
    """Attach the named things a layer draws to its feature group.

    Args:
        group: Feature group the points belong to
        points: One entry per point, with its name, type and position
    """
    setattr(group, NAMED_POINTS_ATTR, points)


#: Attribute under which a feature group carries the figures its lines are
#: described by. The same mechanism as :data:`SEARCH_NAMES_ATTR`, for the same
#: reason: a Leaflet polyline has no ``feature.properties`` and its path options
#: drop unknown keys, so a number reaches the browser beside the layer, keyed by
#: the class every path already carries.
CHAIN_FIGURES_ATTR = "chain_figures"

#: Key under which the figures of a line name the thing they describe. The class
#: is what the table is keyed by, but a class is not an id — :func:`_group_class`
#: reshapes anything that is not a CSS token — so what the figures are *about*
#: travels as a value rather than being read back out of the key.
FIGURE_ID_KEY = "id"

#: Decimals a carried figure keeps. A tenth of a metre is ten times finer than
#: the height model resolves and a hundred times finer than anything shown, and
#: a tenth of a degree turns an arrow by less than its own stroke width. Written
#: at full float precision instead, this table costs a third of a megabyte more
#: for digits nothing can use.
FIGURE_DECIMALS = 1

#: The gradient rule, taken from :mod:`trails.routing.elevation` rather than
#: kept here as well. The panel colours by it and a chain's popup states the
#: steepest it reaches, so the page and the build have to be reading one rule:
#: two copies of a threshold drift, and this project has paid for that twice.
GRADIENT_WINDOW_M = elevation.GRADIENT_WINDOW_M
GRADIENT_MIN_RUN_M = elevation.GRADIENT_MIN_RUN_M

#: How a gradient is banded on the profile: the lower bound in per cent, the
#: name, the colour and the stroke width. The width escalates with the colour so
#: the reading survives a red-green confusion.
#:
#: **The lowest boundary was chosen against the model's own noise, not by taste.**
#: On chains that rise under three metres end to end — level ground — the height
#: model reads a median of 1.0 % over this window, a 99th percentile of 5.8 % and
#: a worst case of 9.2 %. Not one level stretch reaches 15 %. So a coloured
#: stretch is a statement about the hill and never about the data. Measured over
#: the network the bands hold 81.9 %, 11.5 %, 5.1 % and 1.5 % of the ground.
GRADIENT_BANDS = (
    (0.0, "gentle", "#33691e", 1.6),
    (15.0, "steep", "#f9a825", 2.1),
    (25.0, "very steep", "#ef6c00", 2.6),
    (40.0, "extreme", "#c62828", 3.2),
)

#: Everything the page has to be handed before it can write a GPX file. There is
#: no default for any of it and none may be missing: a licence, a version or a
#: field name the browser had to invent would be a claim nobody made, written
#: into the one file that leaves this machine. :func:`add_profile_panel` refuses
#: an ``export`` that is short of any of them rather than building a page that
#: writes ``undefined`` into a source's terms.
EXPORT_SETTINGS = (
    "credits",
    "heights",
    "protected",
    "fields",
    "creditFields",
    "sourceLength",
    "route",
    "waypoint",
    "gapM",
    "decimals",
    "elevationDecimals",
    "coordinateDecimals",
    "namespace",
    "prefix",
    "creator",
    "description",
    "ascentMethod",
    "identitySeparator",
    "filePrefix",
)


#: What ``route`` holds, which is every name a planned route's own file is
#: written with. Checked as its own list rather than by the presence of the key
#: above it: a ``route`` short of ``partLength`` builds without a word and the
#: page writes ``<trails:part kind="routed" undefined="2027.0"/>``, and one short
#: of ``kindField`` writes an element called ``undefined`` — a file that fails
#: the schema, out of a check whose whole point is that it does not happen.
EXPORT_ROUTE_SETTINGS = (
    "name",
    "description",
    "fileStem",
    "kindField",
    "kind",
    "fields",
    "legs",
    "leg",
    "part",
    "partKind",
    "partLength",
    "areas",
    "area",
    "areaId",
    "areaName",
    "areaForm",
    "areaLength",
)

#: What ``waypoint`` holds, checked for the same reason as
#: :data:`EXPORT_ROUTE_SETTINGS`.
#:
#: ``generated`` is the other value ``origin`` takes, and the three words after
#: it are what a marker the map placed says it is: a boundary crossing names the
#: area it enters or leaves, and ``area`` is the field its id travels under, so
#: a reader loading the file back can tell which boundary was meant without
#: parsing a sentence.
EXPORT_WAYPOINT_SETTINGS = ("name", "origin", "set", "generated", "enters", "leaves", "area", "stage")


#: Everything the page has to be handed before it can plan a route. As with
#: :data:`EXPORT_SETTINGS` there is no default for any of it: a sampling step,
#: an ascent threshold or the name of the answer that means *sea* are all things
#: the build already decided, and a page that quietly picked its own would draw
#: a profile that disagrees with every other figure on the map without anything
#: looking wrong. :func:`add_plan_mode` refuses a ``plan`` short of any of them.
PLAN_SETTINGS = (
    "heightsUrl",
    "heightsCrs",
    "heightsBatch",
    "heightsWorkers",
    "terrainModel",
    "seaTerrain",
    "sampleStepM",
    "ascentThresholdM",
    "snapM",
    "maxStraightM",
    "crossingKind",
    "connectorKind",
    "touchedM",
    "namedM",
    "gpx",
    "indexCellM",
    "matchToleranceM",
    "matchMinOverlap",
    "matchMinRunM",
    "matchMaxTurnDeg",
    "matchAnchorM",
)


#: What ``gpx`` holds: every name phase 8's reader needs to recognise a file
#: this map wrote and to read back what it says. Checked as its own list for the
#: reason :data:`EXPORT_ROUTE_SETTINGS` is — a missing key here is a page that
#: looks for an element called ``undefined``, finds none, and reports a route
#: export as a foreign track without a word.
#:
#: **This is the one place in the project where a reader and a writer of the
#: same file are in one phase**, and every name below is also in
#: :data:`EXPORT_ROUTE_SETTINGS` or :data:`EXPORT_WAYPOINT_SETTINGS` — handed
#: over twice, out of one Python constant each, so the two vocabularies cannot
#: drift. ``trackKind`` is the exception and travels only here: it is the fifth
#: part kind, and plan mode both writes it and reads it.
PLAN_GPX_SETTINGS = (
    "namespace",
    "kindField",
    "kind",
    "chainField",
    "legs",
    "leg",
    "part",
    "partKind",
    "partLength",
    "origin",
    "set",
    "generated",
    "trackKind",
    "stage",
)


def _record_chain_figures(group: folium.FeatureGroup, figures: dict[str, dict[str, object]]) -> None:
    """Attach the per-line figures of a layer to its feature group.

    Args:
        group: Feature group the figures belong to
        figures: Mapping of CSS class to the figures of the line carrying it
    """
    setattr(group, CHAIN_FIGURES_ATTR, figures)


def _figure_values(row: pd.Series, fields: dict[str, str]) -> dict[str, object]:
    """Read the figures of one feature, in the shape the page reads them.

    Args:
        row: Row of a GeoDataFrame
        fields: Mapping of column name to the key it travels under

    Returns:
        One entry per field. A missing value travels as None and reaches the
        page as ``null``, which is what a ferry crossing's ascent is and what a
        ring's bearing is: not zero, and not a number to be drawn. A number is
        rounded to :data:`FIGURE_DECIMALS`, which is finer than anything shown
        and ten times finer than the height model resolves — the alternative is
        writing ``17.339999999999996`` eleven thousand times.
    """
    values: dict[str, object] = {}
    for column, key in fields.items():
        value = row[column] if column in row else None
        if value is None or pd.isna(value):
            values[key] = None
        elif isinstance(value, str):
            # Anything already decided here travels as it is. A label must not
            # be re-derived in the page: that is a second implementation of a
            # rounding rule, and a rounding rule is a threshold.
            values[key] = value
        else:
            values[key] = round(float(value), FIGURE_DECIMALS)
    return values


def _build_popup(
    row: pd.Series,
    fields: dict[str, str],
    link_fields: dict[str, str] | None = None,
    source: str | None = None,
    link_heading: str | None = None,
) -> str | None:
    """Render a popup table from selected fields.

    Args:
        row: Row of a GeoDataFrame
        fields: Mapping of column name to display label
        link_fields: Mapping of a column holding a URL to the link text to show
            for it. Rendered below the table rows, one link per line. Values that
            are not http(s) URLs are dropped.
        source: Dataset the feature came from, shown as a footer. A map that
            stacks seven sources is unreadable without it, so it is worth a line
            even where nothing else about the feature is known.
        link_heading: Line set above the links, saying whose pages they are.
            Without one, a link offering a GPX reads as this map's export of the
            line rather than as the recording somebody else published.

    Returns:
        HTML table, or None if the row has nothing to show at all
    """
    rows = []
    for column, label in fields.items():
        if column not in row:
            continue
        value = row[column]
        if pd.isna(value) or value == "":
            continue
        # Values come from third-party data, so they must not be able to inject markup.
        rows.append(
            f"<tr><td style='padding:2px 8px 2px 0;color:#555'>{escape(str(label))}</td>"
            f"<td style='padding:2px 0'><b>{escape(str(value))}</b></td></tr>"
        )

    written = 0
    for column, text in (link_fields or {}).items():
        if column not in row:
            continue
        url = row[column]
        if pd.isna(url) or not str(url).startswith(_LINK_SCHEMES):
            continue
        # Above the first link that survives, not above the block: a route with
        # no description on the park's site would otherwise get a heading over
        # nothing at all.
        if link_heading and not written:
            rows.append(f"<tr><td colspan='2' style='padding:7px 0 1px;color:#777'>{escape(str(link_heading))}</td></tr>")
        written += 1
        # noopener keeps the opened page from reaching back into this one.
        rows.append(
            f"<tr><td colspan='2' style='padding:3px 0'>"
            f'<a href="{escape(str(url), quote=True)}" target="_blank" rel="noopener noreferrer">{escape(str(text))}</a>'
            f"</td></tr>"
        )

    if source:
        # Set off by a rule, so it reads as provenance rather than as another
        # attribute of the feature.
        rows.append(f"<tr><td colspan='2' style='padding:5px 0 0;border-top:1px solid #ddd;color:#777'>Source: {escape(str(source))}</td></tr>")

    if not rows:
        return None
    return f"<table style='font-family:sans-serif;font-size:12px'>{''.join(rows)}</table>"


def add_trails(
    fmap: folium.Map,
    gdf: gpd.GeoDataFrame,
    name: str,
    color: str = "#1b5e20",
    weight: float = 3.0,
    opacity: float = 0.85,
    popup_fields: dict[str, str] | None = None,
    link_fields: dict[str, str] | None = None,
    link_heading: str | None = None,
    tooltip_field: str | None = None,
    group_field: str | None = None,
    search_field: str | None = None,
    figure_fields: dict[str, str] | None = None,
    source: str | None = None,
    dash_array: str | None = None,
    show: bool = True,
) -> folium.FeatureGroup:
    """Add trail geometries as a toggleable layer.

    Args:
        fmap: Map to add the layer to
        gdf: GeoDataFrame with line geometries; reprojected to WGS84 if needed
        name: Layer name shown in the layer control
        color: Line color
        weight: Line width in pixels
        opacity: Line opacity between 0 and 1
        popup_fields: Mapping of column name to popup label
        link_fields: Mapping of a column holding a URL to its link text, for
            trails that have a description page elsewhere
        link_heading: Line set above those links, saying whose pages they are
        tooltip_field: Column shown on hover, so a line can be identified before
            it is clicked
        group_field: Column whose value ties the parts of one route together, so
            :func:`add_click_highlight` can pick out all of it at once. A route
            split into several lines shares one value.
        search_field: Column holding the text :func:`add_search` matches against
        figure_fields: Mapping of a column to the key it travels under, for what
            :func:`add_profile_panel` shows and writes. Recorded per
            ``group_field`` value, beside the layer rather than on it, alongside
            the value itself under :data:`FIGURE_ID_KEY`. A number is rounded on
            the way (see :func:`_figure_values`); a string travels as it is,
            which is what carries a chain's name and its source into a page that
            has to write both into an exported file.
        source: Dataset the lines came from, shown at the foot of every popup
        dash_array: SVG dash pattern, e.g. ``"8,6"``. Use for connections that
            are not walked, such as ferry crossings.
        show: Whether the layer starts visible

    Returns:
        The feature group that was added
    """
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    group = folium.FeatureGroup(name=f"{name} ({len(gdf)})", show=show)
    search_names: dict[str, str] = {}
    figures: dict[str, dict[str, object]] = {}

    for _, row in gdf.iterrows():
        geometry = row.geometry
        if geometry is None or geometry.is_empty:
            continue

        lines = list(geometry.geoms) if geometry.geom_type == "MultiLineString" else [geometry]
        popup_html = _build_popup(row, popup_fields or {}, link_fields, source, link_heading) if (popup_fields or link_fields or source) else None

        tooltip = None
        if tooltip_field and tooltip_field in row and pd.notna(row[tooltip_field]):
            tooltip = str(row[tooltip_field])

        # Leaflet writes className straight onto the SVG path, which makes it the
        # natural place to carry the route identity into the browser. Path options
        # drop unknown keys, so the searchable text cannot ride along the same way
        # and is handed to the browser as a lookup keyed by this class instead.
        class_name = None
        key_field = group_field or search_field
        if key_field and key_field in row and pd.notna(row[key_field]):
            class_name = _group_class(row[key_field])
        if class_name and search_field and search_field in row and pd.notna(row[search_field]):
            search_names[class_name] = str(row[search_field])
        # Keyed by the class and not by the group value, because that is what a
        # click hands back: a path knows the class it was drawn with and nothing
        # else about the feature it came from.
        if class_name and figure_fields and key_field:
            figures[class_name] = {FIGURE_ID_KEY: str(row[key_field]), **_figure_values(row, figure_fields)}

        for line in lines:
            polyline = folium.PolyLine(
                locations=[(lat, lon) for lon, lat in line.coords],
                color=color,
                weight=weight,
                opacity=opacity,
                dash_array=dash_array,
                tooltip=tooltip,
                class_name=class_name,
            )
            if popup_html:
                polyline.add_child(folium.Popup(popup_html, max_width=320))
            polyline.add_to(group)

    _record_search_names(group, search_names)
    _record_chain_figures(group, figures)
    group.add_to(fmap)
    return group


class _ClickHighlight(MacroElement):
    """Leaflet behaviour that lifts the clicked route out of the tangle.

    Rendered after the layers it operates on, so their JavaScript variables
    already exist by the time this runs.
    """

    _template = Template("""
        {% macro script(this, kwargs) %}
        (function () {
            var groups = [{{ this.group_names|join(', ') }}];
            var boost = {{ this.weight_boost }};
            var dim = {{ this.dim_opacity }};
            var selected = null;

            function eachPath(fn) {
                groups.forEach(function (group) {
                    group.eachLayer(function (layer) {
                        if (layer.setStyle && layer.options.className) { fn(layer); }
                    });
                });
            }

            // Captured before anything is restyled, so a restore is always exact.
            eachPath(function (layer) {
                layer._baseStyle = {
                    color: layer.options.color,
                    weight: layer.options.weight,
                    opacity: layer.options.opacity
                };
            });

            function step_back(layer) {
                // Width is reset alongside the fade, or a route that was selected
                // a moment ago would stay widened underneath the new one.
                layer.setStyle({weight: layer._baseStyle.weight, opacity: dim});
            }

            function clear() {
                if (selected === null) { return; }
                selected = null;
                eachPath(function (layer) { layer.setStyle(layer._baseStyle); });
            }

            function select(key) {
                // Restyling is the expensive part on a map with thousands of lines,
                // so only what actually changes is touched: the first selection
                // fades everything once, and each later one repaints just the two
                // routes involved.
                var previous = selected;
                selected = key;
                eachPath(function (layer) {
                    var mine = layer.options.className === key;
                    if (mine) {
                        layer.setStyle({weight: layer._baseStyle.weight + boost, opacity: 1});
                        layer.bringToFront();
                    } else if (previous === null || layer.options.className === previous) {
                        step_back(layer);
                    }
                });
            }

            eachPath(function (layer) {
                layer.on('click', function () {
                    if (selected === layer.options.className) { clear(); } else { select(layer.options.className); }
                });
            });

            // Leaflet only fires a map click when the click hit no layer, so this
            // clears the selection on empty terrain without fighting the handler above.
            {{ this._parent.get_name() }}.on('click', clear);

            // **And a way in that is not a click**, because both of the ways out
            // above are clicks and something else can own those. Plan mode does:
            // it takes every click on the container and stops it there, so a
            // highlight made before switching it on had no way back and left the
            // whole map faded behind the route being planned. Exposed the way the
            // graph and the panel's selection are, so a browser check reads it
            // rather than measuring opacities.
            window.trailsHighlight = {
                clear: clear,
                selected: function () { return selected; }
            };
        })();
        {% endmacro %}
    """)

    def __init__(self, groups: list[folium.FeatureGroup], weight_boost: float, dim_opacity: float) -> None:
        """Initialize the behaviour.

        Args:
            groups: Feature groups whose lines take part
            weight_boost: Pixels added to the selected route's width
            dim_opacity: Opacity the unselected routes fall back to
        """
        super().__init__()
        self._name = "ClickHighlight"
        self.group_names = [group.get_name() for group in groups]
        self.weight_boost = weight_boost
        self.dim_opacity = dim_opacity


def add_click_highlight(
    fmap: folium.Map,
    groups: list[folium.FeatureGroup],
    weight_boost: float = 4.0,
    dim_opacity: float = 0.15,
) -> None:
    """Make a clicked route stand out from the ones it overlaps.

    Where several sources map the same valley, none of their lines can be
    followed by eye. Clicking one widens it, draws it in front of everything
    else and fades every other line on the map, so a single trip reads end to
    end. Clicking it again, or clicking empty terrain, puts everything back.

    Only lines carrying a ``group_field`` take part, and all lines sharing that
    value are selected together, so a route split into several pieces — or
    across two layers — still highlights as one.

    Call after the layers have been added, and before :func:`add_legend`.

    Args:
        fmap: Map holding the layers
        groups: Feature groups returned by :func:`add_trails`
        weight_boost: Pixels added to the selected route's width
        dim_opacity: Opacity the unselected routes fall back to
    """
    if not groups:
        return
    _ClickHighlight(groups, weight_boost=weight_boost, dim_opacity=dim_opacity).add_to(fmap)


def _script_json(value: object) -> str:
    """Serialise a value for embedding inside a ``<script>`` block.

    ``json.dumps`` leaves ``<`` alone, so a string holding ``</script>`` would
    close the block and everything after it would be parsed as markup. Escaping
    the one character shuts that door; a JavaScript parser reads ``\\u003c``
    back as ``<``, so any HTML carried in the value survives intact.

    Args:
        value: Anything JSON can represent

    Returns:
        A JavaScript literal safe to paste into a script block
    """
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c")


class _NameSearch(MacroElement):
    """A box that reduces the map to whatever matches what is typed.

    Deliberately separate from :class:`_ClickHighlight`: this one decides what is
    *visible*, that one decides what is *emphasised*. Two independent properties,
    so the two can be used together without either undoing the other.
    """

    _template = Template("""
        {% macro script(this, kwargs) %}
        (function () {
            var map = {{ this._parent.get_name() }};
            var groups = [{{ this.group_names|join(', ') }}];
            var names = {{ this.names_json }};

            // A real Leaflet control rather than a box floating over the page.
            // Anchored in the map, it moves with it — and, decisively, a wheel
            // turned over it still bubbles to the map and zooms. A panel outside
            // the container swallows the wheel instead, which reads as the map
            // having frozen the moment you finish typing.
            var input = document.createElement('input');
            input.type = 'search';
            input.placeholder = {{ this.placeholder_json }};
            input.autocomplete = 'off';
            input.style.cssText = 'width:210px;font-size:12px;padding:3px 6px;border:1px solid #bbb;border-radius:3px';

            var count = document.createElement('span');
            count.style.cssText = 'margin-left:8px;color:#666';

            var control = L.control({position: 'topleft'});
            control.onAdd = function () {
                var box = L.DomUtil.create('div');
                box.style.cssText = 'background:rgba(255,255,255,0.95);padding:6px 8px;border:1px solid #999;' +
                    'border-radius:4px;font-family:sans-serif;font-size:12px';
                box.appendChild(input);
                box.appendChild(count);
                // Clicking and dragging inside the box must not reach the map;
                // scrolling must. Leaflet has a separate opt-out for each, and
                // only the click one is wanted here.
                L.DomEvent.disableClickPropagation(box);
                // Leaflet binds its own keyboard shortcuts to the container, so
                // typing a "+" would otherwise zoom the map mid-word.
                L.DomEvent.on(input, 'keydown keypress keyup', L.DomEvent.stopPropagation);
                return box;
            };
            control.addTo(map);

            // Leaflet appends to a top corner, which would leave the box below
            // the zoom buttons. It is the first thing reached for, so it belongs
            // above them.
            var corner = control.getContainer().parentNode;
            corner.insertBefore(control.getContainer(), corner.firstChild);

            // Norwegian names are unreachable from most keyboards otherwise, so
            // "tveravegen" has to find "Tveråvegen". Combining marks fall out by
            // decomposition; ø and æ are letters in their own right and do not.
            function fold(text) {
                return (text || '').toLowerCase()
                    .replace(/ø/g, 'o').replace(/æ/g, 'ae').replace(/å/g, 'a')
                    .normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
            }

            var entries = [];
            groups.forEach(function (group, index) {
                group.eachLayer(function (layer) {
                    var text = layer.options.searchName || names[layer.options.className] || null;
                    entries.push({layer: layer, group: index, text: text, folded: fold(text)});
                });
            });

            // A layer switched off holds no elements to reveal, so a match inside
            // it would be silently unfindable. Those layers are switched on for
            // the duration of the search and put back afterwards.
            var revealed = [];

            function display(layer, visible) {
                var value = visible ? '' : 'none';
                // A layer is drawn either as a path or as an icon, never both.
                var element = layer._path || layer._icon;
                // Reading the current value is cheap; writing one that is already
                // set is not, and with twelve thousand features that is the whole
                // difference between a filter that keeps up and one that stalls.
                if (!element || element.style.display === value) { return; }
                element.style.display = value;
                if (layer._shadow) { layer._shadow.style.display = value; }
            }

            var query = '';

            // Only the difference is applied. Tearing every revealed layer off the
            // map and putting it straight back would rebuild a thousand markers on
            // each keystroke, and that work blocks the thread the map zooms on:
            // the wheel piles up and only lands once typing stops.
            function set_revealed(wanted) {
                revealed = revealed.filter(function (index) {
                    if (wanted && wanted[index]) { return true; }
                    map.removeLayer(groups[index]);
                    return false;
                });
                if (!wanted) { return; }
                Object.keys(wanted).forEach(function (index) {
                    if (!map.hasLayer(groups[index])) { map.addLayer(groups[index]); revealed.push(index); }
                });
            }

            var filtering = false;

            function apply() {
                query = fold(input.value.trim());
                if (!query) {
                    if (filtering) {
                        entries.forEach(function (e) { display(e.layer, true); });
                        filtering = false;
                    }
                    set_revealed(null);
                    count.textContent = '';
                    return;
                }

                var matched = entries.map(function (e) { return !!e.text && e.folded.indexOf(query) !== -1; });

                var wanted = {};
                matched.forEach(function (hit, i) { if (hit) { wanted[entries[i].group] = true; } });
                // Reveal before restyling: an element only exists once its layer
                // is on the map.
                set_revealed(wanted);

                var hits = 0;
                entries.forEach(function (e, i) {
                    display(e.layer, matched[i]);
                    if (matched[i]) { hits += 1; }
                });
                filtering = true;
                count.textContent = hits === 1 ? '1 match' : hits + ' matches';
            }

            function fit() {
                if (!query) { return; }
                var bounds = L.latLngBounds([]);
                entries.forEach(function (e) {
                    if (!e.text || e.folded.indexOf(query) === -1) { return; }
                    if (e.layer.getBounds) { bounds.extend(e.layer.getBounds()); }
                    else if (e.layer.getLatLng) { bounds.extend(e.layer.getLatLng()); }
                });
                if (bounds.isValid()) { map.fitBounds(bounds, {maxZoom: 14, padding: [40, 40]}); }
            }

            var pending = null;
            input.addEventListener('input', function () {
                window.clearTimeout(pending);
                pending = window.setTimeout(apply, 150);
            });
            input.addEventListener('keydown', function (event) {
                if (event.key === 'Enter') { window.clearTimeout(pending); apply(); fit(); }
                if (event.key === 'Escape') { input.value = ''; window.clearTimeout(pending); apply(); }
            });

            // Toggling a layer back on rebuilds its elements at full visibility,
            // which would smuggle non-matching features past an active filter.
            map.on('overlayadd', function () { window.setTimeout(apply, 0); });
        })();
        {% endmacro %}
    """)

    def __init__(self, groups: list[folium.FeatureGroup], names: dict[str, str], placeholder: str) -> None:
        """Initialize the search box.

        Args:
            groups: Feature groups to search across
            names: Mapping of CSS class to searchable text, for path layers
            placeholder: Hint shown in the empty input
        """
        super().__init__()
        self._name = "NameSearch"
        self.group_names = [group.get_name() for group in groups]
        self.names_json = _script_json(names)
        self.placeholder_json = _script_json(placeholder)


def add_search(
    fmap: folium.Map,
    groups: list[folium.FeatureGroup],
    placeholder: str = "Search names… (Enter to zoom)",
) -> None:
    """Add a box that hides everything not matching what is typed.

    On a map carrying several thousand features from seven sources, finding the
    one place named in a brochure is otherwise hopeless. Typing reduces the map
    to the matches — across trails, roads, huts and place names alike — so what
    is left standing is the answer. Enter zooms to it, Escape restores.

    Matching ignores case and folds Norwegian letters, so ``tveravegen`` finds
    ``Tveråvegen`` from a keyboard that cannot type å.

    Only features given a searchable name take part; anything unnamed disappears
    while a search is active, which is what makes the remainder legible. A layer
    that is switched off is switched on for as long as it holds a match, so a
    name cannot hide behind an unticked box.

    Call after the layers have been added, and before :func:`add_legend`.

    Args:
        fmap: Map holding the layers
        groups: Feature groups to search across, of any layer type
        placeholder: Hint shown in the empty input
    """
    if not groups:
        return

    names: dict[str, str] = {}
    for group in groups:
        names.update(getattr(group, SEARCH_NAMES_ATTR, {}))

    _NameSearch(groups, names, placeholder).add_to(fmap)


def add_points(
    fmap: folium.Map,
    gdf: gpd.GeoDataFrame,
    name: str,
    color: str = "red",
    icon: str = "home",
    popup_fields: dict[str, str] | None = None,
    label_field: str | None = "name",
    search_field: str | None = None,
    source: str | None = None,
    point_type: str | None = None,
    show: bool = True,
) -> folium.FeatureGroup:
    """Add point features (huts, shelters, info points) as a toggleable layer.

    Args:
        fmap: Map to add the layer to
        gdf: GeoDataFrame with point geometries; reprojected to WGS84 if needed
        name: Layer name shown in the layer control
        color: Marker color; must be one of Folium's named icon colors
            (e.g. "red", "darkblue", "green"), not a CSS hex value
        icon: Glyph name from the Font Awesome set bundled with Folium
        popup_fields: Mapping of column name to popup label
        label_field: Column used for the hover tooltip
        search_field: Column holding the text :func:`add_search` matches against;
            defaults to ``label_field``
        source: Dataset the points came from, shown at the foot of every popup
        point_type: What these points are — a hut, a quay, a trailhead. Given
            one, the layer carries a table of what it draws and where, which is
            how a waypoint set beside one of them comes to be named after it.
            Left out, the layer draws itself and answers no questions.
        show: Whether the layer starts visible

    Returns:
        The feature group that was added
    """
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    group = folium.FeatureGroup(name=f"{name} ({len(gdf)})", show=show)
    named: list[dict[str, object]] = []

    for _, row in gdf.iterrows():
        geometry = row.geometry
        if geometry is None or geometry.is_empty:
            continue

        tooltip = None
        if label_field and label_field in row and pd.notna(row[label_field]):
            tooltip = str(row[label_field])

        popup_html = _build_popup(row, popup_fields or {}, source=source) if (popup_fields or source) else None
        # Unlike a path, a marker keeps whatever options it is handed, so the
        # searchable text can travel on the layer itself.
        found_by = search_field or label_field
        options: dict[str, Any] = {}
        if found_by and found_by in row and pd.notna(row[found_by]):
            options["searchName"] = str(row[found_by])

        marker = folium.Marker(
            location=(geometry.y, geometry.x),
            tooltip=tooltip,
            icon=folium.Icon(color=color, icon=icon, prefix="fa"),
            **options,
        )
        if popup_html:
            marker.add_child(folium.Popup(popup_html, max_width=320))
        marker.add_to(group)

        if point_type and tooltip:
            named.append({"name": tooltip, "type": point_type, "lat": round(geometry.y, 6), "lon": round(geometry.x, 6)})

    _record_named_points(group, named)
    group.add_to(fmap)
    return group


def add_labelled_points(
    fmap: folium.Map,
    gdf: gpd.GeoDataFrame,
    name: str,
    color: str = "#37474f",
    radius: float = 6.0,
    label_field: str = "name",
    always_label: tuple[str, ...] = (),
    kind_field: str = "kind",
    popup_fields: dict[str, str] | None = None,
    source: str | None = None,
    point_type: str | None = None,
    searchable: bool = True,
    show: bool = True,
) -> folium.FeatureGroup:
    """Add place markers as small labelled circles.

    Lighter than :func:`add_points` for orientation layers with many features:
    pin icons would dominate the map, so these render as dots. Labels for the
    most important kinds stay permanently visible, the rest appear on hover.

    Args:
        fmap: Map to add the layer to
        gdf: GeoDataFrame with point geometries; reprojected to WGS84 if needed
        name: Layer name shown in the layer control
        color: Circle fill and outline color
        radius: Circle radius in pixels. Doubles as the click target, so a dot
            small enough to look tidy is often too small to hit.
        label_field: Column holding the label text
        always_label: Values of ``kind_field`` whose labels are always shown
        kind_field: Column consulted for ``always_label``
        popup_fields: Mapping of column name to popup label. Without it a marker
            only names itself on hover, which reads as a dead click.
        source: Dataset the points came from, shown at the foot of every popup
        point_type: What these points are — a trailhead, a farm, a settlement.
            See :func:`add_points`; the same table, for the same reason.
        searchable: Whether :func:`add_search` can find these by their label
        show: Whether the layer starts visible

    Returns:
        The feature group that was added
    """
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    group = folium.FeatureGroup(name=f"{name} ({len(gdf)})", show=show)
    search_names: dict[str, str] = {}
    named: list[dict[str, object]] = []

    for _, row in gdf.iterrows():
        geometry = row.geometry
        if geometry is None or geometry.is_empty:
            continue
        if label_field not in row or pd.isna(row[label_field]):
            continue

        label = str(row[label_field])
        permanent = kind_field in row and row[kind_field] in always_label

        class_name = None
        if searchable:
            class_name = _group_class(label)
            search_names[class_name] = label

        marker = folium.CircleMarker(
            location=(geometry.y, geometry.x),
            radius=radius,
            color=color,
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            class_name=class_name,
            tooltip=folium.Tooltip(label, permanent=permanent, direction="right"),
        )

        popup_html = _build_popup(row, popup_fields or {}, source=source) if (popup_fields or source) else None
        if popup_html:
            marker.add_child(folium.Popup(popup_html, max_width=320))
        marker.add_to(group)

        if point_type:
            named.append({"name": label, "type": point_type, "lat": round(geometry.y, 6), "lon": round(geometry.x, 6)})

    _record_search_names(group, search_names)
    _record_named_points(group, named)
    group.add_to(fmap)
    return group


def add_text_labels(
    fmap: folium.Map,
    gdf: gpd.GeoDataFrame,
    name: str,
    label_field: str = "name",
    size_field: str | None = None,
    default_size: float = 11.0,
    color: str = "#37474f",
    color_field: str | None = None,
    symbol_field: str | None = None,
    halo: str = "#ffffff",
    show: bool = True,
) -> folium.FeatureGroup:
    """Add place names as plain text, without a marker symbol.

    For terrain features a dot would assert a precision the data does not have —
    a valley has no single position. Drawing only the text, repeated wherever the
    name applies, is the topographic convention and stays honest about that.

    Args:
        fmap: Map to add the layer to
        gdf: GeoDataFrame with point geometries; reprojected to WGS84 if needed
        name: Layer name shown in the layer control
        label_field: Column holding the text to draw
        size_field: Column holding a per-label font size in pixels
        default_size: Font size used when ``size_field`` is absent or empty
        color: Text colour used when no per-label colour is given
        color_field: Column holding a per-label CSS colour, e.g. to distinguish
            rivers from valleys
        symbol_field: Column holding a short glyph drawn before the label, so the
            feature type reads without relying on colour alone
        halo: Outline colour drawn around the glyphs for legibility over the map
        show: Whether the layer starts visible

    Returns:
        The feature group that was added
    """
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    group = folium.FeatureGroup(name=f"{name} ({len(gdf)})", show=show)
    shadow = f"-1px -1px 0 {halo}, 1px -1px 0 {halo}, -1px 1px 0 {halo}, 1px 1px 0 {halo}"

    for _, row in gdf.iterrows():
        geometry = row.geometry
        if geometry is None or geometry.is_empty:
            continue
        if label_field not in row or pd.isna(row[label_field]):
            continue

        size = default_size
        if size_field and size_field in row and pd.notna(row[size_field]):
            size = float(row[size_field])

        text_color = color
        if color_field and color_field in row and pd.notna(row[color_field]):
            text_color = str(row[color_field])

        text = escape(str(row[label_field]))
        if symbol_field and symbol_field in row and pd.notna(row[symbol_field]):
            text = f"{escape(str(row[symbol_field]))}\u2009{text}"

        html = (
            f'<div style="font-family:sans-serif;font-size:{size:g}px;color:{text_color};'
            f'text-shadow:{shadow};white-space:nowrap;transform:translate(-50%,-50%)">{text}</div>'
        )
        # A zero-sized icon keeps Leaflet from reserving a box around the text.
        folium.Marker(
            location=(geometry.y, geometry.x),
            icon=folium.DivIcon(icon_size=(0, 0), icon_anchor=(0, 0), html=html),
            searchName=str(row[label_field]),
        ).add_to(group)

    group.add_to(fmap)
    return group


def add_boundary(
    fmap: folium.Map,
    gdf: gpd.GeoDataFrame,
    name: str,
    color: str = "#0d47a1",
    fill_opacity: float = 0.06,
    weight: float = 2.5,
    show: bool = True,
) -> folium.GeoJson:
    """Add an area boundary as a toggleable outline.

    Args:
        fmap: Map to add the layer to
        gdf: GeoDataFrame with polygon geometries; reprojected to WGS84 if needed
        name: Layer name shown in the layer control
        color: Outline color
        fill_opacity: Fill opacity between 0 and 1
        weight: Outline width in pixels
        show: Whether the layer starts visible

    Returns:
        The GeoJson layer that was added
    """
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    def style(_: Any) -> dict[str, Any]:
        return {"color": color, "weight": weight, "fillColor": color, "fillOpacity": fill_opacity}

    # A boundary is drawn last so its outline stays legible over every trail, which
    # also puts its fill on top of them for hit-testing — and a faint fill still
    # swallows clicks. Since the outline carries no popup, it opts out of pointer
    # events entirely and lets clicks reach the trails underneath.
    layer = folium.GeoJson(gdf.to_json(), name=name, style_function=style, show=show, interactive=False)
    layer.add_to(fmap)
    return layer


class _RoutingGraph(MacroElement):
    """The routing graph, decoded in the page and never drawn.

    Hand-written, like the legend, the search and the click-highlight, and for
    the same reason: a script pulled from a CDN does not load on a ``file://``
    page and fails silently, the way the OpenStreetMap tiles once did.

    The decode runs off the load rather than during it. It is a megabyte or two
    of arithmetic, and nothing on the map waits for it — a reader who never
    plans a route never notices it happened.
    """

    _template = Template("""
        {% macro script(this, kwargs) %}
        (function () {
            var header = {{ this.header_json }};
            var encoded = {{ this.data_json }};

            // A cursor over the inflated stream. Every count it needs is either
            // in the header or in a section it has already read, so it runs
            // straight through and never seeks.
            function Cursor(bytes) { this.bytes = bytes; this.at = 0; }

            // Deliberately arithmetic rather than bitwise: JavaScript's shifts
            // truncate to 32 bits, and a value that overflowed that would come
            // back quietly wrong instead of loudly.
            Cursor.prototype.varint = function () {
                var value = 0, scale = 1, byte;
                do {
                    byte = this.bytes[this.at]; this.at += 1;
                    value += (byte & 0x7f) * scale;
                    scale *= 128;
                } while (byte & 0x80);
                return value;
            };

            Cursor.prototype.zigzag = function () {
                var value = this.varint();
                return value % 2 === 0 ? value / 2 : -(value + 1) / 2;
            };

            Cursor.prototype.take = function (count) {
                var out = this.bytes.slice(this.at, this.at + count);
                this.at += count;
                return out;
            };

            function bytesOf(text) {
                var binary = atob(text);
                var out = new Uint8Array(binary.length);
                for (var i = 0; i < binary.length; i += 1) { out[i] = binary.charCodeAt(i); }
                return out;
            }

            function inflate(bytes) {
                if (typeof DecompressionStream === 'undefined') {
                    return Promise.reject(new Error('this browser cannot inflate gzip'));
                }
                var stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
                return new Response(stream).arrayBuffer().then(function (buffer) { return new Uint8Array(buffer); });
            }

            function decode(bytes) {
                var cursor = new Cursor(bytes);
                var edges = header.edges, chains = header.chains, i;

                var lengths = new Int32Array(chains);
                for (i = 0; i < chains; i += 1) { lengths[i] = cursor.varint(); }
                var text = new TextDecoder('utf-8');
                var chainIds = new Array(chains);
                // Without a prototype, so that a lookup answers for the chain
                // ids and for nothing else. A plain object would hand back
                // Object's own members for names like "constructor".
                var chainOf = Object.create(null);
                for (i = 0; i < chains; i += 1) {
                    chainIds[i] = text.decode(cursor.take(lengths[i]));
                    chainOf[chainIds[i]] = i;
                }

                // Where each chain's edges begin. They are contiguous and in the
                // chain's own order, which is the whole reason the payload is
                // laid out this way: the frame order the graph is built in is
                // not the order the edges lie in, and one chain in five does not
                // even join up in it.
                var chainAt = new Int32Array(chains + 1);
                for (i = 0; i < chains; i += 1) { chainAt[i + 1] = chainAt[i] + cursor.varint(); }

                var flags = cursor.take(edges);
                var fromNode = new Int32Array(edges), toNode = new Int32Array(edges);
                var tail = 0;
                for (i = 0; i < edges; i += 1) {
                    // The node an edge starts at along its chain, then the one it
                    // ends at. Which of from and to holds which depends on the
                    // way round the edge runs, so the flag puts them back.
                    var head = tail + cursor.zigzag();
                    tail = head + cursor.zigzag();
                    fromNode[i] = (flags[i] & 1) ? tail : head;
                    toNode[i] = (flags[i] & 1) ? head : tail;
                }

                var sources = cursor.take(edges);

                // What a planned route sums beside its length. waymarked
                // indexes header.waymarked, whose first entry is null and means
                // the edge was never asked — a crossing, or a connector nobody
                // drew. That is not the same as 'unknown', which means it was
                // asked and no source answered, and the two must not be added
                // together. noPathRecorded says no source records a path along
                // the edge; it does NOT say there is no path, and any text
                // showing it has to say the same.
                var derived = cursor.take(edges);
                var waymarked = new Uint8Array(edges), noPathRecorded = new Uint8Array(edges);
                for (i = 0; i < edges; i += 1) {
                    waymarked[i] = derived[i] & 0x03;
                    noPathRecorded[i] = (derived[i] & header.noPathBit) ? 1 : 0;
                }

                // The third field, which is a length and not a flag: how much of
                // the edge lies inside each protected area it meets, in the
                // order header.protected lists them. Most edges say 'none' in
                // one byte. **A crossing says 'none' as well and means
                // something else** — there is no walking distance under a
                // ferry, so it was never asked — and nothing here may read this
                // for one; the kind is what tells them apart, as it does for
                // waymarked, where the payload can afford a code of its own and
                // here it cannot.
                var protectedAt = new Int32Array(edges + 1);
                var areaOf = [], areaShare = [];
                var shareStep = header.protectedShareQuantum;
                for (i = 0; i < edges; i += 1) {
                    var meets = cursor.varint();
                    for (var a = 0; a < meets; a += 1) {
                        areaOf.push(cursor.take(1)[0]);
                        // A share of the edge, not a length. Python measured
                        // these metres in the projection the graph is built in
                        // and this page measures its own from the ellipsoid;
                        // multiplied by the length measured here, a route can
                        // never state more ground inside an area than it walked.
                        areaShare.push(cursor.varint() * shareStep);
                    }
                    protectedAt[i + 1] = protectedAt[i] + meets;
                }
                var protectedArea = Uint8Array.from(areaOf), protectedShare = Float64Array.from(areaShare);

                var vertexAt = new Int32Array(edges + 1);
                for (i = 0; i < edges; i += 1) { vertexAt[i + 1] = vertexAt[i] + cursor.varint(); }
                var coordinates = new Float64Array(2 * header.vertices);
                var quantum = header.coordinateQuantum, lon = 0, lat = 0;
                for (i = 0; i < header.vertices; i += 1) {
                    lon += cursor.zigzag();
                    lat += cursor.zigzag();
                    coordinates[2 * i] = lon * quantum;
                    coordinates[2 * i + 1] = lat * quantum;
                }

                var sampleAt = new Int32Array(edges + 1);
                for (i = 0; i < edges; i += 1) { sampleAt[i + 1] = sampleAt[i] + cursor.varint(); }
                // Single precision, and the bound is worth stating because the
                // grid is a centimetre: a float32 near v is wrong by at most
                // v / 2**24, so a centimetre stays recoverable up to 83 km of
                // altitude — four orders of magnitude above this ground. That
                // halves what the series costs in memory. The coordinates get
                // double precision, where a millionth of a degree needs it.
                var heights = new Float32Array(header.samples);
                var step = header.elevationQuantum, height = 0;
                for (i = 0; i < header.samples; i += 1) {
                    var code = cursor.varint();
                    if (code === 0) {
                        // Nothing was read here, and it must not become a number:
                        // a profile that fills a gap invents ground, and a climb
                        // counted across one invents a hill.
                        heights[i] = NaN;
                        continue;
                    }
                    code -= 1;
                    height += code % 2 === 0 ? code / 2 : -(code + 1) / 2;
                    heights[i] = height * step;
                }

                // Reading past the end of the stream yields undefined, which
                // masks to zero and ends a varint quietly, so a truncated
                // payload decodes to plausible numbers rather than to an error.
                // The layout accounts for every byte, so this says the whole of
                // it was read and nothing beyond it.
                if (cursor.at !== bytes.length) {
                    throw new Error('read ' + cursor.at + ' of ' + bytes.length + ' bytes');
                }

                // Node positions come off the edge endpoints rather than a table
                // of their own, so they cannot disagree with the geometry and
                // cost nothing in the payload.
                var nodeLon = new Float64Array(header.nodes), nodeLat = new Float64Array(header.nodes);
                for (i = 0; i < edges; i += 1) {
                    var first = 2 * vertexAt[i], last = 2 * (vertexAt[i + 1] - 1);
                    nodeLon[fromNode[i]] = coordinates[first];
                    nodeLat[fromNode[i]] = coordinates[first + 1];
                    nodeLon[toNode[i]] = coordinates[last];
                    nodeLat[toNode[i]] = coordinates[last + 1];
                }

                return {
                    header: header,
                    // Composing a chain runs its edges from chainAt[c] to
                    // chainAt[c + 1], reversing the geometry and the heights of
                    // any edge whose flag bit 0 is set, dropping the first
                    // sample and vertex of every edge but the first — the node
                    // between two edges is sampled by both — and breaking rather
                    // than joining wherever bit 1 says a new stretch begins.
                    chainIds: chainIds, chainOf: chainOf, chainAt: chainAt, flags: flags,
                    fromNode: fromNode, toNode: toNode, sources: sources,
                    waymarked: waymarked, noPathRecorded: noPathRecorded,
                    protectedAt: protectedAt, protectedArea: protectedArea, protectedShare: protectedShare,
                    vertexAt: vertexAt, coordinates: coordinates,
                    sampleAt: sampleAt, heights: heights,
                    nodeLon: nodeLon, nodeLat: nodeLat,
                    nearestNode: nearestNode.bind(null, nodeLon, nodeLat)
                };
            }

            // Nothing lies in a protected area far more often than something
            // does, so the answer for that case is one shared array rather than
            // a new one per position: this is asked once per height sample
            // along a leg drawn straight, and once per point of an exported
            // track.
            var NOWHERE = [];

            // Which protected areas a position lies in, by their place in
            // header.protected. **Even-odd over every ring of an area, its
            // holes among them**: in a valid multipolygon a point inside a hole
            // is enclosed by an even number of rings and so comes out outside,
            // and a point in any of several disjoint parts comes out inside. So
            // there is no outer-and-inner structure here to keep in step with
            // itself, and a boundary that gains an island needs no new case.
            //
            // The box first, because it settles thirty of the thirty-one areas
            // in four comparisons, and only then the four thousand vertices.
            function areasAt(areas, lon, lat) {
                var found = null;
                for (var a = 0; a < areas.length; a += 1) {
                    var box = areas[a].bounds;
                    if (lon < box[0] || lon > box[2] || lat < box[1] || lat > box[3]) { continue; }
                    var rings = areas[a].rings, crossings = 0;
                    for (var r = 0; r < rings.length; r += 1) {
                        var ring = rings[r];
                        for (var i = 0, k = ring.length - 1; i < ring.length; k = i, i += 1) {
                            var yi = ring[i][1], yk = ring[k][1];
                            // The half-open rule: a vertex exactly at this
                            // latitude is counted by the segment below it and
                            // not by the one above, so a ray through a corner
                            // is counted once rather than twice or not at all.
                            if ((yi > lat) === (yk > lat)) { continue; }
                            var t = (lat - yi) / (yk - yi);
                            if (lon < ring[i][0] + t * (ring[k][0] - ring[i][0])) { crossings += 1; }
                        }
                    }
                    if (crossings % 2 === 1) { (found = found || []).push(a); }
                }
                return found || NOWHERE;
            }

            // A linear scan, and it needs no spatial index: a hundred thousand
            // nodes is a few milliseconds, once per click. Anything cleverer
            // here would be a structure to keep in step with the geometry for no
            // gain a reader could perceive.
            function nearestNode(nodeLon, nodeLat, lat, lon, withinM) {
                var scale = Math.cos(lat * Math.PI / 180);
                var limit = withinM === undefined ? Infinity : Math.pow(withinM / 111320, 2);
                var best = -1, closest = limit;
                for (var i = 0; i < nodeLon.length; i += 1) {
                    var dx = (nodeLon[i] - lon) * scale, dy = nodeLat[i] - lat;
                    var distance = dx * dx + dy * dy;
                    if (distance < closest) { closest = distance; best = i; }
                }
                return best;
            }

            var began = performance.now();
            var graph = {header: header, inflateMs: null, decodeMs: null, totalMs: null, error: null};
            // Bound to the graph before the stream is inflated rather than
            // inside the decode, because it needs nothing from the stream: the
            // outlines travel in the header, and a caller asking what protects
            // a position should not have to wait for two million coordinates
            // it is not going to look at.
            graph.protectedAreas = header.protected || [];
            graph.areasAt = areasAt.bind(null, graph.protectedAreas);
            graph.ready = inflate(bytesOf(encoded)).then(function (bytes) {
                var inflated = performance.now();
                var decoded = decode(bytes);
                graph.inflateMs = inflated - began;
                graph.decodeMs = performance.now() - inflated;
                graph.totalMs = performance.now() - began;
                Object.keys(decoded).forEach(function (key) { graph[key] = decoded[key]; });
                return graph;
            }).catch(function (error) {
                // Loudly, in the one place a reader might look: a graph that
                // silently failed to arrive looks exactly like one that was
                // never asked for.
                graph.error = String(error);
                console.error('routing graph: ' + error);
                throw error;
            });
            window.trailsGraph = graph;
        })();
        {% endmacro %}
    """)

    def __init__(self, header: dict[str, Any], data: str) -> None:
        """Initialize the payload.

        Args:
            header: Everything the decoder needs before it starts
            data: The binary stream, gzipped and base64-encoded
        """
        super().__init__()
        self._name = "RoutingGraph"
        self.header_json = _script_json(header)
        self.data_json = _script_json(data)


def add_routing_graph(fmap: folium.Map, header: dict[str, Any], data: str) -> None:
    """Put the routing graph in the page, at full source precision.

    A second representation beside the drawn one, and the two must not be
    unified: what the map draws is chains, simplified for rendering, and what a
    route is found over is the merged graph at the resolution its sources
    recorded. One copy cannot serve both without losing either the accuracy or
    the render budget.

    Nothing draws it and nothing yet reads it. It arrives as
    ``window.trailsGraph``, whose ``ready`` promise resolves once the stream has
    been inflated and decoded, and whose ``decodeMs`` says what that cost.

    Args:
        fmap: Map to attach the payload to
        header: Everything the decoder needs before it starts
        data: The binary stream, gzipped and base64-encoded
    """
    _RoutingGraph(header, data).add_to(fmap)


class _ProfilePanel(MacroElement):
    """The selected chain's profile, drawn by hand at the foot of the map.

    Hand-written SVG, like the legend, the search and the click-highlight: a
    charting library pulled from a CDN does not load on a ``file://`` page and
    fails silently, the way the OpenStreetMap tiles once did.

    **Nothing here recomputes a figure.** The ascent, the descent, the high and
    low point and the bearing are read off the table this is handed, which the
    build put beside the layers. The panel decodes the chain's series for one
    thing only — the curve, and the distance under it — because a number that
    exists in two languages ends up with two values, and a popup and a panel
    disagreeing by a few metres about the same chain is worse than either of
    them being wrong.

    A control rather than a box over the page, and with only
    ``disableClickPropagation``: a wheel turned over it still has to reach the
    map, or the map reads as frozen the moment the panel is open. The **curve**
    is the one exception, and only where it has detail to give — see the zoom
    below.

    **And the crosshair marks the ground it is reading.** Wherever the pointer
    stands on the curve, a dot stands at that position on the map, so the hill
    under the pointer and the hill on the map are visibly the same hill. It works
    for a chain and for a planned route alike, because both reach this panel as
    one series. Finding the position is not the sample's index: the heights are
    sampled every 5 m and the line is drawn through the vertices somebody
    surveyed, so the two axes are different lengths and only a distance is shared
    between them. The dot travels in the same pane as the direction arrow and for
    the same reason — the map's path count is what phase 3 was accepted against.

    **And a reader can zoom into the curve**, which is a feature of the long
    chain and of a planned route rather than of the map's lines. Measured over
    the built graph: the median chain is drawn at 0.16 metres a pixel against a
    series carrying a height every 5.12 m, so the panel already magnifies every
    reading it holds some thirty times, and only 126 chains of 11,264 are drawn
    coarser than their own samples. The wheel is therefore taken over the curve
    exactly where zooming would show something and passed to the map everywhere
    else. The ceiling is the data's — one reading per pixel, 7.1x on the 42 km
    chain — and the scale stays true in both axes at every step, so zooming
    changes how much of the chain is on the panel and never its angle. Dragging
    moves the window, double-clicking returns the whole chain, and a new
    selection starts over.

    **It also writes the chain out as GPX**, from the same composed series it
    draws the curve from — which is the reason the two live in one closure
    rather than in two controls. A second composition in the page would be a
    third implementation of the same walk, and the file would eventually
    disagree with the profile drawn above the button that produced it.

    **And it takes a second way in**, for a series composed rather than read off
    one chain. A planned route has no chain and no row in the figures table, so
    ``window.trailsProfilePanel.series`` is handed the series and the figures
    already read from it; the gradient bands, the crosshair and the reduction
    all apply unchanged, and a stretch drawn straight across unrecorded ground
    is dashed in the curve as it is dashed on the map. The same object carries
    ``suspend``, for while something else owns the map's clicks, and the two
    things a second consumer must not write again: the walk that lays a run of
    edges end to end, and the metre this page measures distance with.

    **A route composed that way is written out here too**, from the same series
    the curve was drawn from, and it is a second kind of file rather than the
    same file with different numbers in it. What is different about it:

    - Its points travel as ``<wpt>`` elements before the track, each saying
      whether a reader set it or the map generated it. A waypoint is a GPX 1.1
      top-level element and not an extension, so it goes in its own place.
    - Its legs are listed on the track, each with its parts in order. **They
      cannot go on a ``<trkseg>``**: a segment is a stretch and a stretch breaks
      only where the ground stops, so four routed legs laid end to end are one
      segment.
    - Its track breaks at every crossing and nowhere else, because a crossing
      ends the stretch it was in and a crossing's own line is never written —
      there is no way in GPX to say a segment is a boat, and every reader would
      import one as a walked line across a fjord.
    - Its sources are as many as it runs over, each with the length it
      contributed and the licence that comes with it.
    - It says how much of it is waymarked in three buckets, and how much runs
      where no source records a path.

    The series a composed route arrives with carries both kinds of nothing —
    ground with no reading of it, and no ground at all — and they must not be
    confused: the first only drops an ``<ele>``, the second breaks the track.
    They are told apart by the stretch boundaries the composer records, never by
    inference from the series.
    """

    _template = Template("""
        {% macro script(this, kwargs) %}
        (function () {
            var map = {{ this._parent.get_name() }};
            var groups = [{{ this.group_names|join(', ') }}];
            var figures = {{ this.figures_json }};
            var title = {{ this.title_json }};
            var chartHeight = {{ this.chart_height }};
            var GRADE = {{ this.gradient_json }};
            var open = {{ 'false' if this.collapsed else 'true' }};

            var SVG = 'http://www.w3.org/2000/svg';
            // Room for the axes: the left margin holds a four-digit height, the
            // bottom one a distance.
            var PAD = {left: 52, right: 16, top: 12, bottom: 22};
            // Blue, deliberately: the steepest gradient band is red, and a red rule
            // over a red stretch of curve reads as part of the data.
            var AXIS = '#9e9e9e', TEXT = '#555', CROSS = '#1565c0';
            // Sea level, which is the one height on this panel that is not a
            // choice: every other line is drawn where the data happens to be.
            var SEA = '#4fa3c7';
            // The dash a stretch nobody recorded a way along is drawn with,
            // here and on the map. One pattern, so the two read as one thing.
            var FREE_DASH = '5,4';

            // ---- what a number reads as ------------------------------------
            // Math.round is floor(x + 0.5), which is exactly what the popup's
            // formatter does. Anything else here — a toFixed, a rint — rounds a
            // half the other way, and the panel and the popup then disagree by
            // a metre on the chains that land on one.
            function metres(value) {
                return String(Math.round(value)).replace(/\\B(?=(\\d{3})+(?!\\d))/g, ',');
            }

            // There is deliberately no rule here for naming a compass point.
            // It is decided once, in Python, and carried as figure.point.
            // Deriving it in the page from figure.bearing would be a second
            // implementation of a rounding rule — and a rounded label IS a
            // threshold: measured on this network, 241 chains lie within half a
            // degree of a boundary between two points, and two rules that
            // disagree by a hair name a different direction in the panel from
            // the one in the popup.

            // The one phrase that says which way the figures run. The popup
            // renders the same words from the same numbers in Python; a ring
            // gets no direction, because it has none and needs none.
            function climb(figure) {
                var words = '+' + metres(figure.ascent) + ' / \\u2212' + metres(figure.descent) + ' m';
                return figure.point ? words + ' towards ' + figure.point : words;
            }

            // ---- the chain's own series, laid out of its edges --------------
            // Metres between two positions, from the metres-per-degree of the
            // ellipsoid at the latitude between them.
            //
            // **This used to be a sphere and it read 0.56 % short.** Measured
            // over 4,000 real edges against the projection the graph is built
            // in: 110,309 m where the projection says 110,933, because
            // 110,574 m to a degree of latitude is the figure at the *equator*
            // and this park sits at 65.6 N, where it is 111,500. That did not
            // matter while the only consumer was a chain, whose series is
            // scaled onto the length the chain carries before anything is
            // shown — a uniform factor cancels exactly. It matters the moment a
            // planned route states its own distance, because there is no
            // carried length to scale onto and nothing in the payload to read
            // one from: 0.56 % is 900 m on a 160 km traverse, against a map
            // whose every popup was measured in the projection.
            //
            // The series below is the standard one for WGS84 and reads +0.034 %
            // over the same 4,000 edges, sixteen times nearer. A degree of
            // longitude carries its own series rather than a bare cosine of the
            // equatorial radius, which is the other half of the old error.
            function metresBetween(lon1, lat1, lon2, lat2) {
                var phi = ((lat1 + lat2) / 2) * Math.PI / 180;
                var perLat = 111132.92 - 559.82 * Math.cos(2 * phi) + 1.175 * Math.cos(4 * phi) - 0.0023 * Math.cos(6 * phi);
                var perLon = 111412.84 * Math.cos(phi) - 93.5 * Math.cos(3 * phi) + 0.118 * Math.cos(5 * phi);
                var dx = (lon2 - lon1) * perLon;
                var dy = (lat2 - lat1) * perLat;
                return Math.sqrt(dx * dx + dy * dy);
            }

            // Lay a run of edges end to end, in the order and the directions
            // given. **One walk, and every consumer in the page uses it**: the
            // panel lays a chain's edges out of the payload's own order, plan
            // mode lays a route's out of what the router returned. Two walks
            // would eventually disagree, and each would still look like a
            // profile — which is the reason the Python side keeps its one in
            // trails.routing.order rather than one per caller.
            //
            // Two joined edges both sample the node between them, so the second
            // copy of it is dropped; where `breaks` says an edge does not join
            // what came before, the series is broken rather than joined.
            function layEdges(graph, list, reversed, breaks) {
                var lon = [], lat = [], along = [], height = [], distance = [];
                var reached = 0, read = false, crossing = false, joined = false;
                // Where each stretch that joins up begins, in both series. The
                // profile does not need them — it reads the NaN the break
                // leaves behind — but an export writes one track segment per
                // stretch, and a segment drawn across the step between two of
                // them is a route nobody can walk.
                var stretches = [];
                for (var index = 0; index < list.length; index += 1) {
                    var edge = list[index];
                    var flipped = reversed[index];
                    var apart = breaks[index] && lon.length > 0;
                    var v0 = graph.vertexAt[edge], v1 = graph.vertexAt[edge + 1];
                    var s0 = graph.sampleAt[edge], s1 = graph.sampleAt[edge + 1], samples = s1 - s0;
                    var began = reached;
                    crossing = crossing || graph.header.sources[graph.sources[edge]].kind === 'ferry';

                    if (apart || !lon.length) {
                        // The separator pushed below closes the stretch that
                        // ended; it is not the first sample of this one.
                        var separated = !!(samples && height.length && apart);
                        stretches.push({from: lon.length, sampleFrom: height.length + (separated ? 1 : 0), separated: separated});
                    }

                    for (var v = 0; v < v1 - v0; v += 1) {
                        var at = flipped ? v1 - 1 - v : v0 + v;
                        var x = graph.coordinates[2 * at], y = graph.coordinates[2 * at + 1];
                        if (v === 0) {
                            // The node this edge is joined on is already laid
                            // down. Where it is not joined, the step across is
                            // ground nothing was measured along, so it starts
                            // where it starts and adds no distance.
                            if (lon.length && !apart) { continue; }
                            began = reached;
                        } else {
                            reached += metresBetween(lon[lon.length - 1], lat[lat.length - 1], x, y);
                        }
                        lon.push(x); lat.push(y); along.push(reached);
                    }

                    var length = reached - began;
                    if (samples && height.length && apart) {
                        // A break rather than a join: a climb counted across a
                        // step nothing was measured along is invented.
                        height.push(NaN); distance.push(began);
                    }
                    for (var s = (joined && !apart) ? 1 : 0; s < samples; s += 1) {
                        var sample = flipped ? s1 - 1 - s : s0 + s;
                        var value = graph.heights[sample];
                        height.push(value);
                        // Every 5 m along the edge means samples spread evenly
                        // between its two ends, so this is where the sth of them
                        // lies rather than s * 5 — and the last of them sits on
                        // the edge's far end, which is a vertex, so it takes
                        // that vertex's own distance rather than one a hair
                        // away: began + (reached - began) is not reached, and
                        // an export merging the two writes a pair of points at
                        // a single position.
                        distance.push(samples < 2 ? began : (s === samples - 1 ? reached : began + (length * s) / (samples - 1)));
                        if (!isNaN(value)) { read = true; }
                    }
                    joined = samples > 0;
                }
                for (var s = 0; s < stretches.length; s += 1) {
                    var next = stretches[s + 1];
                    stretches[s].to = next ? next.from : lon.length;
                    stretches[s].sampleTo = next ? next.sampleFrom - (next.separated ? 1 : 0) : height.length;
                }
                return {lon: lon, lat: lat, along: along, height: height, distance: distance,
                        stretches: stretches, total: reached, read: read, crossing: crossing};
            }

            // The payload holds a chain's edges as one contiguous run in the
            // chain's own order; bit 0 of an edge's flag says it runs against
            // the chain, bit 1 that it begins a stretch which does not join
            // what came before.
            function compose(graph, index) {
                var list = [], reversed = [], breaks = [];
                for (var edge = graph.chainAt[index]; edge < graph.chainAt[index + 1]; edge += 1) {
                    list.push(edge);
                    reversed.push(!!(graph.flags[edge] & 1));
                    breaks.push(!!(graph.flags[edge] & 2));
                }
                return layEdges(graph, list, reversed, breaks);
            }

            // The chain's length as the chain carries it, distributed over the
            // series by the geometry. One length, so the axis, the crosshair and
            // the popup all end on the same number.
            function scale(shape, carried) {
                var factor = (carried > 0 && shape.total > 0) ? carried / shape.total : 1;
                var i;
                for (i = 0; i < shape.along.length; i += 1) { shape.along[i] *= factor; }
                for (i = 0; i < shape.distance.length; i += 1) { shape.distance[i] *= factor; }
                shape.total = carried > 0 ? carried : shape.total;
                return shape;
            }

            // Which point of the drawn line lies this far along it.
            //
            // **A series has two axes and they are not the same length.** The
            // heights are sampled every 5 m; the line is drawn through the
            // vertices somebody surveyed, which fall wherever they fall. So a
            // sample's index says nothing about a vertex's, and the only thing
            // the two share is a distance. ``along`` is the vertices' own.
            function positionAt(shape, metres) {
                if (!shape.along || !shape.along.length) { return null; }
                var low = 0, high = shape.along.length - 1;
                while (low < high) {
                    var middle = (low + high) >> 1;
                    if (shape.along[middle] < metres) { low = middle + 1; } else { high = middle; }
                }
                if (low < 1) { return L.latLng(shape.lat[0], shape.lon[0]); }
                var span = shape.along[low] - shape.along[low - 1];
                var t = span > 0 ? Math.min(1, Math.max(0, (metres - shape.along[low - 1]) / span)) : 0;
                return L.latLng(shape.lat[low - 1] + t * (shape.lat[low] - shape.lat[low - 1]),
                                shape.lon[low - 1] + t * (shape.lon[low] - shape.lon[low - 1]));
            }

            // Where to put the arrow: half way along, by distance.
            function midpoint(shape) {
                return positionAt(shape, shape.total / 2);
            }

            // ---- the file this panel writes ---------------------------------
            // Hand-written, like everything else here: a library from a CDN
            // does not load on a page opened off the disk. It writes what
            // libs/src/trails/io/export/gpx.py writes, from the same graph and
            // the same edge order. Nothing here can import that module and no
            // test can run this, so the two are exported on a real chain and
            // compared in a browser whenever the work is accepted — to a
            // tolerance the payload sets rather than to equality. What they
            // agree on exactly is the field names, and those are handed in.
            var EXPORT = {{ this.export_json }};

            function escaped(value) {
                return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;').replace(/'/g, '&apos;');
            }

            // Written to as many places as the page's own figures carry, and to
            // exactly that many: '500' in one file against '500.0' in the other
            // is two writers disagreeing about a number both of them got right.
            function fixed(value) {
                return Number(value).toFixed(EXPORT.decimals);
            }

            // A height keeps more places than a figure does: it is what the
            // figure was computed from, and a file whose <ele> values do not
            // reproduce the ascent it states has no use for stating one.
            function fixedEle(value) {
                return Number(value).toFixed(EXPORT.elevationDecimals);
            }

            // The height model read at a set of distances along one stretch.
            // Both series only ever move forward, so one pointer serves the
            // whole of it. A position *between* two samples one of which says
            // nothing gets nothing — a height interpolated across a gap is
            // invented ground, and nothing downstream can tell the two apart —
            // while a position landing on a sample takes that sample and asks
            // nothing of its neighbour.
            function heightsAt(positions, shape, from, to) {
                var out = new Array(positions.length), below = from, i;
                for (i = 0; i < positions.length; i += 1) { out[i] = NaN; }
                if (to - from < 2) { return out; }
                for (i = 0; i < positions.length; i += 1) {
                    while (below < to - 2 && shape.distance[below + 1] <= positions[i]) { below += 1; }
                    var span = shape.distance[below + 1] - shape.distance[below];
                    var t = span > 0 ? (positions[i] - shape.distance[below]) / span : 0;
                    t = t < 0 ? 0 : (t > 1 ? 1 : t);
                    var low = shape.height[below], high = shape.height[below + 1];
                    out[i] = t <= 0 ? low : (t >= 1 ? high : (isNaN(low) || isNaN(high)) ? NaN : low + t * (high - low));
                }
                return out;
            }

            // Every vertex the chain has, every sample the height model gave,
            // and a point wherever two of those are still further apart than
            // the gap. **Not** a resampling every 5 m: that drops the source's
            // own vertices and rounds off every corner between two samples, and
            // those vertices are the whole reason the geometry is carried at
            // full precision. And **not** the vertices alone with the heights
            // interpolated between them: measured that way, the ascent read
            // back off the file's own values came out 47 m under the figure the
            // same file states for the 42 km Rundtur. Where nothing was read
            // along the stretch there is nothing to fill it for either — a
            // point every 5 m across a fjord says nothing its two ends do not.
            function denseOf(shape, stretch) {
                var lon = [], lat = [], read = false, i, k;
                for (i = stretch.sampleFrom; i < stretch.sampleTo; i += 1) {
                    if (!isNaN(shape.height[i])) { read = true; break; }
                }
                var along = shape.along, first = stretch.from, last = stretch.to;
                if (!read || last - first < 2) {
                    for (i = first; i < last; i += 1) { lon.push(shape.lon[i]); lat.push(shape.lat[i]); }
                    return {lon: lon, lat: lat, ele: lon.map(function () { return NaN; })};
                }

                // The two lists merged, each distance once. An edge's first and
                // last sample sit on its end vertices and are the same number
                // here, so the merge drops the copy rather than writing a step
                // of no length.
                var merged = [], sample = stretch.sampleFrom;
                function keep(value) {
                    if (!merged.length || merged[merged.length - 1] !== value) { merged.push(value); }
                }
                while (sample < stretch.sampleTo && shape.distance[sample] <= along[first]) { sample += 1; }
                for (i = first; i < last; i += 1) {
                    while (sample < stretch.sampleTo && shape.distance[sample] < along[i]) { keep(shape.distance[sample]); sample += 1; }
                    if (sample < stretch.sampleTo && shape.distance[sample] === along[i]) { sample += 1; }
                    keep(along[i]);
                }

                // And the samples are not as close together as their step
                // suggests: an edge of 12 m gets three of them, 6 m apart.
                var positions = [merged[0]];
                for (i = 1; i < merged.length; i += 1) {
                    var step = merged[i] - merged[i - 1];
                    var intervals = Math.max(Math.ceil(step / EXPORT.gapM), 1);
                    for (k = 1; k < intervals; k += 1) { positions.push(merged[i - 1] + (k / intervals) * step); }
                    // A position already in the list is written as itself and
                    // never as a fraction of the way to itself: a + 1 * (b - a)
                    // is not b, and a sample that misses its own distance by an
                    // ulp is interpolated instead of read.
                    positions.push(merged[i]);
                }

                var below = first;
                for (i = 0; i < positions.length; i += 1) {
                    while (below < last - 2 && along[below + 1] <= positions[i]) { below += 1; }
                    var span = along[below + 1] - along[below];
                    var t = span > 0 ? (positions[i] - along[below]) / span : 0;
                    t = t < 0 ? 0 : (t > 1 ? 1 : t);
                    // A vertex is the coordinate the surveyor recorded, not a
                    // point computed between it and its neighbour.
                    var at = t >= 1 ? below + 1 : below;
                    if (t <= 0 || t >= 1) {
                        lon.push(shape.lon[at]); lat.push(shape.lat[at]);
                    } else {
                        lon.push(shape.lon[below] + t * (shape.lon[below + 1] - shape.lon[below]));
                        lat.push(shape.lat[below] + t * (shape.lat[below + 1] - shape.lat[below]));
                    }
                }
                return {lon: lon, lat: lat, ele: heightsAt(positions, shape, stretch.sampleFrom, stretch.sampleTo)};
            }

            function runsOf(shape) {
                return shape.stretches.map(function (stretch) { return denseOf(shape, stretch); });
            }

            // Where the selection crosses a protected boundary, worked out the
            // first time something asks and then kept against that selection.
            //
            // **Asked for rather than computed on every refresh, and measured.**
            // The walk below is 45 ms of a 50 ms panel refresh over a 37 km
            // route and it grows with the route, while the only thing that needs
            // it is the button — which a reader may never press. Cached, so the
            // file and any check that reads them get one answer rather than two
            // walks that could differ. The cache dies with the selection, which
            // is a fresh object on every change.
            function crossings() {
                if (!selected || !selected.composed || !selected.shape || !selected.runs) { return []; }
                if (!selected.crossings) { selected.crossings = crossingsOf(selected.shape, selected.runs); }
                return selected.crossings;
            }

            // Where the route crosses into a protected area and where it leaves
            // one again, as the markers the file carries. **Read off the runs
            // the file is written from**, which is the one series in this page
            // with a point every few metres over the whole route — the vertices
            // alone are a source's own corners and a leg drawn straight has two
            // of them for twenty kilometres.
            //
            // Two things this deliberately does not do. It puts no marker where
            // the route *begins* inside an area or ends inside one: that is not
            // a crossing and there is nothing there to see. And it looks only
            // for the areas the route already reports — the threshold is
            // applied once, where the figures are — so a boundary grazed for
            // ten metres cannot bring a pair of markers in through this door
            // after the sentence above declined to mention it.
            //
            // The boundary this walks is the page's own copy, simplified to
            // five metres, so a marker sits within that of the line the
            // register draws. The *lengths* beside it are not measured here:
            // they come from the build, which measured them against the
            // register's full precision.
            function crossingsOf(shape, runs) {
                var graph = window.trailsGraph;
                if (!graph || !graph.areasAt) { return []; }
                var reported = Object.create(null);
                (shape.protected || []).forEach(function (area) { reported[area.id] = area; });

                var out = [];
                function mark(area, entering, first, second) {
                    out.push({id: area.id, name: area.name, form: area.form, entering: entering,
                              lat: (first.lat + second.lat) / 2, lon: (first.lon + second.lon) / 2});
                }
                function named(indices) {
                    var ids = [];
                    for (var i = 0; i < indices.length; i += 1) { ids.push(graph.protectedAreas[indices[i]].id); }
                    return ids;
                }

                runs.forEach(function (run) {
                    var before = [];
                    for (var i = 0; i < run.lon.length; i += 1) {
                        var here = named(graph.areasAt(run.lon[i], run.lat[i]));
                        if (i > 0) {
                            var from = {lon: run.lon[i - 1], lat: run.lat[i - 1]};
                            var to = {lon: run.lon[i], lat: run.lat[i]};
                            here.forEach(function (id) {
                                if (reported[id] && before.indexOf(id) < 0) { mark(reported[id], true, from, to); }
                            });
                            before.forEach(function (id) {
                                if (reported[id] && here.indexOf(id) < 0) { mark(reported[id], false, from, to); }
                            });
                        }
                        before = here;
                    }
                });
                return out;
            }

            function pointsIn(runs) {
                return runs.reduce(function (total, run) { return total + run.lon.length; }, 0);
            }

            function heightsWritten(runs) {
                return runs.some(function (run) { return run.ele.some(function (value) { return !isNaN(value); }); });
            }

            // Whether the height model is behind any of the numbers in this
            // file, which is a different question from whether the file carries
            // heights at all.
            //
            // **A stretch kept as it was recorded carries the heights that came
            // with the loaded file, and this map never asked the model about
            // it.** Crediting Kartverket for a consumer GPS reading, and
            // stating it was sampled from DTM1 every 5 m, is a false claim in a
            // file somebody takes into the terrain — and it is the exact claim
            // this file was given an `ascentMethod` to avoid making by
            // accident. A chain's series is nothing but the model and says
            // nothing about itself, so an absent answer means the model.
            function modelBehind(shape) {
                return !shape || shape.modelled === undefined ? true : !!shape.modelled;
            }

            // What a chain's file draws on: the chain's own source, and the
            // height model wherever the file carries a height. Naming a source a
            // file does not draw on is exactly as wrong as leaving one out.
            function creditsOf(figure, runs) {
                return (EXPORT.credits[figure.source] || []).concat(heightsWritten(runs) ? EXPORT.heights : []);
            }

            // And a route's, each with the length it contributed. **The terms
            // are not the same for every route**: one running on FKB and
            // Turrutebasen alone is unencumbered, one that picks up a kilometre
            // of OSM is share-alike and one that picks up UT.no is
            // non-commercial, so the figure belongs beside the licence rather
            // than in a blanket warning nobody reads.
            function routeCredits(shape, runs) {
                var metres = shape.tally.sources;
                var names = Object.keys(metres).sort(function (a, b) { return metres[b] - metres[a]; });
                var out = [];
                names.forEach(function (name) {
                    (EXPORT.credits[name] || []).forEach(function (credit) {
                        // A copy. EXPORT.credits is the page's one description of
                        // each dataset, and writing a length onto it would leave
                        // this route's metres on the next route's file.
                        var carried = {};
                        Object.keys(credit).forEach(function (field) { carried[field] = credit[field]; });
                        carried[EXPORT.sourceLength] = fixed(metres[name]);
                        out.push(carried);
                    });
                });
                // And the register the protected figures come from, wherever
                // the file states one. A file naming a source it did not draw on
                // is exactly as wrong as one leaving a source out, and this
                // route's description carries a number that came from Naturbase.
                return out.concat(heightsWritten(runs) && modelBehind(shape) ? EXPORT.heights : [])
                    .concat((shape.protected || []).length ? EXPORT.protected : []);
            }

            function creditLine(credit) {
                var inside = ['licence', 'version', 'attribution'].filter(function (field) { return credit[field]; })
                    .map(function (field) { return credit[field]; });
                var named = inside.length ? credit.name + ' (' + inside.join(', ') + ')' : credit.name;
                // The height model contributes no metres of line, so it carries
                // none and is named without one rather than with a zero.
                var metres = credit[EXPORT.sourceLength];
                return metres ? (Number(metres) / 1000).toFixed(2) + ' km ' + named : named;
            }

            // The same entry as the reader sees it before pressing the button.
            function licenceLine(credit) {
                var metres = credit[EXPORT.sourceLength];
                return (metres ? (Number(metres) / 1000).toFixed(2) + ' km ' : '') +
                    credit.name + ' \\u2014 ' + credit.licence + (credit.note ? ', ' + credit.note : '');
            }

            // A length in the unit it can be read in. The three buckets below
            // are always in kilometres because they are read against one
            // another; the two beside them are not, and a connector run of a
            // quarter of a metre written as '0.00 km' reads as a figure that is
            // not there.
            function span(value) {
                return value >= 1000 ? (value / 1000).toFixed(2) + ' km' : (Math.round(value * 10) / 10) + ' m';
            }

            // How much of the route is waymarked, in length and in three
            // buckets. **Unknown is its own bucket and is never folded into
            // unmarked**: measured over the walked network without its inferred
            // connectors, 63.4 % of the length is unknown, and FKB — the largest
            // source at 33.8 % — carries no marking field at all, so calling it
            // unmarked would assert what no source says. All three are shown
            // even at zero, because which of them a route avoids is the reading.
            //
            // Two more only where there is any: ground on a connector nobody
            // drew, which was never asked rather than asked and unanswered, and
            // ground no source records a path along — **recorded, not fact**.
            // The sources over-record, so their silence is evidence and their
            // lines are not.
            function markingLine(tally) {
                var said = ['marked', 'unmarked', 'unknown'].map(function (bucket) {
                    return bucket + ' ' + (tally[bucket] / 1000).toFixed(2) + ' km';
                });
                if (tally.undrawn > 0) {
                    said.push(span(tally.undrawn) + ' on connectors nobody drew');
                }
                // The fifth bucket, and it is reported for the same reason the
                // fourth is: no register was asked about ground that came off a
                // loaded recording, and folding it into 'unmarked' would turn a
                // question nobody put into an answer.
                if (tally.recorded > 0) {
                    said.push(span(tally.recorded) + ' kept as it was recorded');
                }
                if (tally.unrecorded > 0) {
                    said.push(span(tally.unrecorded) + ' where no source records a path');
                }
                return said.join(' \\u00b7 ');
            }

            // The named ways the track follows. A chain running over several of
            // them carries them joined, and that is its own identity: 'via
            // Tveråvegen, Gamle Stavassveg' is how a person describes a route.
            function waysOf(figure) {
                if (!figure.name) { return ''; }
                return 'via ' + String(figure.name).split(EXPORT.identitySeparator).map(function (part) { return part.trim(); })
                    .filter(function (part) { return part; }).join(', ');
            }

            // The silence is the whole of the statement, and the wording has to
            // keep saying so: this is ground no register draws anything on, not
            // ground with no path. The popup's own words, off the same field.
            function unrecordedOf(figure) {
                return figure.noPath > 0 ? (figure.noPath / 1000).toFixed(2) + ' km where no source records a path' : '';
            }

            function fileNameOf(stem, extension) {
                return (EXPORT.filePrefix + '-' + (stem || 'track')).replace(/[^A-Za-z0-9._-]+/g, '-') +
                    (extension || '.gpx');
            }

            function element(name, value) {
                return '<' + EXPORT.prefix + ':' + name + '>' + escaped(value) + '</' + EXPORT.prefix + ':' + name + '>';
            }

            function openGpx(out) {
                out.push('<?xml version="1.0" encoding="UTF-8"?>');
                out.push('<gpx version="1.1" creator="' + escaped(EXPORT.creator) + '"' +
                    ' xmlns="http://www.topografix.com/GPX/1/1"' +
                    ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"' +
                    ' xmlns:' + EXPORT.prefix + '="' + escaped(EXPORT.namespace) + '"' +
                    ' xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">');
            }

            // The order GPX 1.1 fixes for what <metadata> holds, and there is
            // deliberately no <copyright>: it takes exactly one licence, and a
            // file mixing CC0, CC BY, ODbL and CC BY-NC has no single one to put
            // there. Listing what is present is the honest form.
            function metadataOf(out, name, described, credits) {
                out.push('  <metadata>');
                out.push('    <name>' + escaped(name) + '</name>');
                // The phrase goes in with the list and not before it. A route
                // made entirely of a loaded recording draws on nothing this map
                // holds — its ground came out of the reader's file and its
                // heights with it — and `Sources: ` followed by nothing reads
                // like a list that failed to be written rather than one there
                // was nothing to put in.
                out.push('    <desc>' + escaped(credits.length
                    ? described + '. Sources: ' + credits.map(creditLine).join(' \\u00b7 ')
                    : described) + '</desc>');
                out.push('    <time>' + new Date().toISOString().replace(/\\.\\d+Z$/, 'Z') + '</time>');
                out.push('    <extensions>');
                credits.forEach(function (credit) {
                    var written = EXPORT.creditFields.filter(function (field) { return credit[field]; })
                        .map(function (field) { return ' ' + field + '="' + escaped(credit[field]) + '"'; });
                    out.push('      <' + EXPORT.prefix + ':source' + written.join('') + '/>');
                });
                out.push('    </extensions>');
                out.push('  </metadata>');
            }

            // One segment per stretch that joins up. A track drawn straight
            // across the step between two of them is a route nobody can walk:
            // no chain in this park has such a step and a plan has one at every
            // crossing, and the file says which by where it breaks rather than
            // by asserting anything.
            function segmentsOf(out, runs) {
                runs.forEach(function (run) {
                    out.push('    <trkseg>');
                    for (var i = 0; i < run.lon.length; i += 1) {
                        var point = '      <trkpt lat="' + run.lat[i].toFixed(EXPORT.coordinateDecimals) +
                            '" lon="' + run.lon[i].toFixed(EXPORT.coordinateDecimals) + '">';
                        // No <time> on a trackpoint, ever: a track carrying
                        // timestamps reads as a recorded activity rather than a
                        // plan, and the rest would be guesses dressed as data.
                        //
                        // And a point the height model was never read at keeps
                        // its place and loses only its <ele>. That is the second
                        // of the two kinds of nothing this file has to tell
                        // apart: there is ground here and no reading of it,
                        // where a crossing is no ground at all and ended the
                        // segment above.
                        out.push(point + (isNaN(run.ele[i]) ? '</trkpt>' : '<ele>' + fixedEle(run.ele[i]) + '</ele></trkpt>'));
                    }
                    out.push('    </trkseg>');
                });
            }

            function gpxOf(figure, shape, runs) {
                var credits = creditsOf(figure, runs);
                var told = [waysOf(figure), shape.read ? climb(figure) : '', unrecordedOf(figure)]
                    .filter(function (part) { return part; });

                var out = [];
                openGpx(out);
                metadataOf(out, figure.name || figure.id, EXPORT.description, credits);

                out.push('  <trk>');
                out.push('    <name>' + escaped(figure.name || figure.id) + '</name>');
                if (told.length) { out.push('    <desc>' + escaped(told.join(' \\u00b7 ')) + '</desc>'); }
                out.push('    <extensions>');
                EXPORT.fields.forEach(function (pair) {
                    var value = figure[pair[0]];
                    if (value === null || value === undefined || value === '') { return; }
                    out.push('      ' + element(pair[1], typeof value === 'number' ? fixed(value) : value));
                });
                if (heightsWritten(runs) && EXPORT.ascentMethod) {
                    out.push('      ' + element('ascentMethod', EXPORT.ascentMethod));
                }
                out.push('    </extensions>');
                segmentsOf(out, runs);
                out.push('  </trk>');
                out.push('</gpx>');
                return out.join('\\n') + '\\n';
            }

            // Everything a planned route states about itself as one number.
            // Read off the composed series and the figures already read from
            // it, never recomputed here: the panel above the button and the file
            // under it have to be the same claim.
            function routeFigures(figure, shape) {
                return {
                    ascent: shape.read ? figure.ascent : null,
                    descent: shape.read ? figure.descent : null,
                    walked: shape.total,
                    crossed: shape.crossed,
                    straight: shape.straight,
                    recorded: shape.tally.recorded,
                    unrecorded: shape.tally.unrecorded,
                    marked: shape.tally.marked,
                    unmarked: shape.tally.unmarked,
                    unknown: shape.tally.unknown,
                    undrawn: shape.tally.undrawn
                };
            }

            // `extra` is what the panel was told about the route beside its own
            // series — its crossings, its stretches drawn straight — and it is
            // handed in for the same reason `planned` takes it: the sentence
            // above the button and the one in the file are one sentence.
            function routeGpxOf(figure, shape, runs, plan, extra, crossings) {
                var credits = routeCredits(shape, runs);
                var told = planned(figure, shape, extra).concat([markingLine(shape.tally)]);
                var figures = routeFigures(figure, shape);

                // **What the reader called it, where they called it anything.**
                // A tour goes into <metadata><name> and <trk><name>, which is
                // where GPX already puts a name and what every other reader
                // shows — so it needs no field of its own, and a second
                // recording of one title is a second thing to disagree.
                var titled = (plan && plan.name) ? plan.name : EXPORT.route.name;

                var out = [];
                openGpx(out);
                metadataOf(out, titled, EXPORT.route.description, credits);

                // After the metadata and before the track, which is where GPX
                // 1.1 puts a waypoint: it is a top-level element of its own and
                // **not** part of the extensions mechanism, and a file placing
                // it anywhere else parses and fails the schema.
                // The order GPX 1.1 fixes inside a <wpt> as well: name, then
                // desc, then type, then the extensions. A file that writes them
                // in the order they were thought of parses and fails the schema,
                // which is the whole reason phase 6B's file is checked against
                // one.
                function waypoint(point, name, described, kind, origin, area, stage) {
                    out.push('  <wpt lat="' + point.lat.toFixed(EXPORT.coordinateDecimals) +
                        '" lon="' + point.lon.toFixed(EXPORT.coordinateDecimals) + '">');
                    out.push('    <name>' + escaped(name) + '</name>');
                    if (described) { out.push('    <desc>' + escaped(described) + '</desc>'); }
                    if (kind) { out.push('    <type>' + escaped(kind) + '</type>'); }
                    // Set or generated, on every one: a reader loading this file
                    // back must never take a marker the map placed for a station
                    // somebody chose, or the route would gain stations nobody
                    // put down and start routing through them.
                    out.push('    <extensions>');
                    out.push('      ' + element(EXPORT.waypoint.origin, origin));
                    if (area) { out.push('      ' + element(EXPORT.waypoint.area, area)); }
                    // **Present and empty is not absent.** The element standing
                    // there is what says a stage ends at this point; its text is
                    // only the name. Written on a falsy test every unnamed cut
                    // would be dropped, and a tour would come back in one piece
                    // with nothing saying it had ever been in more.
                    if (stage !== null && stage !== undefined) {
                        out.push('      ' + element(EXPORT.waypoint.stage, stage));
                    }
                    out.push('    </extensions>');
                    out.push('  </wpt>');
                }

                plan.waypoints.forEach(function (point, index) {
                    // Named after what is there where the map draws something
                    // named within reach, and after its number otherwise. The
                    // naming is decided where the points are, not here, so that
                    // what the panel reports and what the file says are one
                    // answer.
                    waypoint(point, point.name || (EXPORT.waypoint.name + ' ' + (index + 1)),
                             null, point.kind || null, EXPORT.waypoint.set, null,
                             point.stage === undefined ? null : point.stage);
                });

                // And the boundaries, which are the only way GPX can carry one
                // at all: it holds waypoints, routes and tracks, and no
                // polygons. **After the points the reader placed rather than
                // among them.** Their order in the file says nothing — every
                // one of them names its origin — and interleaving them would
                // make the sequence of set points depend on where the route
                // happens to run, which is a decision phase 7 owns.
                (crossings || []).forEach(function (crossing) {
                    var verb = crossing.entering ? EXPORT.waypoint.enters : EXPORT.waypoint.leaves;
                    waypoint(crossing, verb + ' ' + crossing.name + ' ' + crossing.form,
                             null, crossing.form, EXPORT.waypoint.generated, crossing.id);
                });

                out.push('  <trk>');
                out.push('    <name>' + escaped(titled) + '</name>');
                out.push('    <desc>' + escaped(told.join(' \\u00b7 ')) + '</desc>');
                out.push('    <extensions>');
                out.push('      ' + element(EXPORT.route.kindField, EXPORT.route.kind));
                EXPORT.route.fields.forEach(function (pair) {
                    var value = figures[pair[0]];
                    if (value === null || value === undefined || isNaN(value)) { return; }
                    out.push('      ' + element(pair[1], fixed(value)));
                });
                if (heightsWritten(runs) && modelBehind(shape) && EXPORT.ascentMethod) {
                    out.push('      ' + element('ascentMethod', EXPORT.ascentMethod));
                }
                // The legs, in the order they were clicked, each holding its
                // parts in the order they are walked. **This cannot go on a
                // <trkseg>**: a segment is a stretch and a stretch breaks only
                // where the ground stops, so four routed legs laid end to end
                // are one segment and could carry one mode between them. Leg n
                // runs from waypoint n to waypoint n + 1, which is what makes
                // the list readable without an index on either.
                out.push('      <' + EXPORT.prefix + ':' + EXPORT.route.legs + '>');
                plan.legs.forEach(function (parts) {
                    out.push('        <' + EXPORT.prefix + ':' + EXPORT.route.leg + '>');
                    parts.forEach(function (part) {
                        out.push('          <' + EXPORT.prefix + ':' + EXPORT.route.part +
                            ' ' + EXPORT.route.partKind + '="' + escaped(part.kind) + '"' +
                            ' ' + EXPORT.route.partLength + '="' + fixed(part.length) + '"/>');
                    });
                    out.push('        </' + EXPORT.prefix + ':' + EXPORT.route.leg + '>');
                });
                out.push('      </' + EXPORT.prefix + ':' + EXPORT.route.legs + '>');
                // And what protects the ground it covers, as figures rather
                // than as a sentence to be parsed back: which areas, in which
                // form, and how much of the route lies in each. **Nothing here
                // says what may be done in one.** That is in each area's
                // verneforskrift, none has been read, and a file that guessed
                // would be read as advice.
                if ((shape.protected || []).length) {
                    out.push('      <' + EXPORT.prefix + ':' + EXPORT.route.areas + '>');
                    shape.protected.forEach(function (area) {
                        out.push('        <' + EXPORT.prefix + ':' + EXPORT.route.area +
                            ' ' + EXPORT.route.areaId + '="' + escaped(area.id) + '"' +
                            ' ' + EXPORT.route.areaName + '="' + escaped(area.name) + '"' +
                            ' ' + EXPORT.route.areaForm + '="' + escaped(area.form) + '"' +
                            ' ' + EXPORT.route.areaLength + '="' + fixed(area.metres) + '"/>');
                    });
                    out.push('      </' + EXPORT.prefix + ':' + EXPORT.route.areas + '>');
                }
                out.push('    </extensions>');
                segmentsOf(out, runs);
                out.push('  </trk>');
                out.push('</gpx>');
                return out.join('\\n') + '\\n';
            }

            function saveFile(name, body) {
                // A body already made into a blob is handed on as it is: an
                // archive is not XML and wrapping it again would label it so.
                var blob = (body instanceof Blob) ? body : new Blob([body], {type: 'application/gpx+xml'});
                var url = URL.createObjectURL(blob);
                var anchor = document.createElement('a');
                anchor.href = url;
                anchor.download = name;
                // Firefox saves a blob offered by a page opened off the disk
                // under the name given, and raises nothing — measured before
                // this was written rather than assumed. The anchor has to be in
                // the document for the click to count as one.
                document.body.appendChild(anchor);
                anchor.click();
                document.body.removeChild(anchor);
                setTimeout(function () { URL.revokeObjectURL(url); }, 0);
            }

            // ---- a zip, written here because nothing may be added to this page ----
            // **A tour cut into stages is several files and one download.** The
            // alternative was several downloads in a row, which rests on an
            // assumption about what a browser lets a page opened off the disk do
            // unattended; a zip rests on arithmetic. Measured before this was
            // written: a hand-made archive downloads from this page, keeps its
            // offered name, opens in Python with a clean `testzip()`, and every
            // member reads back byte for byte.
            //
            // Deflated where the browser can, stored where it cannot, and the
            // choice is not a guess: `CompressionStream('deflate-raw')` is the
            // twin of the `DecompressionStream` this page already inflates its
            // graph with, so anything that can read the payload can pack this.
            // Measured, 20,016 bytes to 55 and back unchanged.
            //
            // **Stamped with the time it was written, and that is a correction.**
            // Every entry went in at zero first, on the rule that no trackpoint
            // carries a time — and that rule is about the *route*: a time on a
            // trackpoint claims somebody walked there at that hour. When an
            // archive was written claims nothing about the walk, and the two are
            // different sentences about the word 'time'. Worse, zero is not
            // absent: the DOS field counts from 1980, so every member showed
            // **1980-01-01**, which is a wrong answer stated confidently rather
            // than no answer at all.
            //
            // One stamp for the whole archive, taken once: the members were
            // written in one act and dating them apart would say otherwise.
            function dosStamp(when) {
                var year = Math.max(1980, when.getFullYear());
                return {
                    // Seconds are stored halved, in the five bits that leaves.
                    time: (when.getHours() << 11) | (when.getMinutes() << 5) | (when.getSeconds() >> 1),
                    date: ((year - 1980) << 9) | ((when.getMonth() + 1) << 5) | when.getDate()
                };
            }

            function crc32(bytes) {
                var table = crc32.table, n, k, c, i;
                if (!table) {
                    table = crc32.table = new Uint32Array(256);
                    for (n = 0; n < 256; n += 1) {
                        c = n;
                        for (k = 0; k < 8; k += 1) { c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1); }
                        table[n] = c >>> 0;
                    }
                }
                c = 0xFFFFFFFF;
                for (i = 0; i < bytes.length; i += 1) { c = table[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8); }
                return (c ^ 0xFFFFFFFF) >>> 0;
            }

            function packed(bytes) {
                if (typeof CompressionStream !== 'function') { return Promise.resolve(null); }
                try {
                    var stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream('deflate-raw'));
                    return new Response(stream).arrayBuffer().then(function (buffer) {
                        return new Uint8Array(buffer);
                    }, function () { return null; });
                } catch (failure) {
                    return Promise.resolve(null);
                }
            }

            function zipOf(files) {
                var encoder = new TextEncoder();
                var members = files.map(function (file) {
                    return {name: encoder.encode(file.name), body: encoder.encode(file.text)};
                });
                var stamp = dosStamp(new Date());
                return Promise.all(members.map(function (member) { return packed(member.body); }))
                    .then(function (compressed) {
                        var chunks = [], directory = [], at = 0;
                        function u16(v) { return [v & 0xFF, (v >>> 8) & 0xFF]; }
                        function u32(v) { return [v & 0xFF, (v >>> 8) & 0xFF, (v >>> 16) & 0xFF, (v >>> 24) & 0xFF]; }
                        members.forEach(function (member, index) {
                            // Only where it is actually smaller: a short file
                            // deflates to more than it was, and a zip that grew
                            // its own members is a bad advertisement for itself.
                            var small = compressed[index];
                            var deflated = !!small && small.length < member.body.length;
                            var stored = deflated ? small : member.body;
                            var sum = crc32(member.body);
                            var header = [].concat(u32(0x04034b50), u16(20), u16(0x0800), u16(deflated ? 8 : 0),
                                                   u16(stamp.time), u16(stamp.date), u32(sum), u32(stored.length),
                                                   u32(member.body.length), u16(member.name.length), u16(0));
                            chunks.push(new Uint8Array(header), member.name, stored);
                            directory.push(new Uint8Array(
                                [].concat(u32(0x02014b50), u16(20), u16(20), u16(0x0800), u16(deflated ? 8 : 0),
                                          u16(stamp.time), u16(stamp.date), u32(sum), u32(stored.length),
                                          u32(member.body.length),
                                          u16(member.name.length), u16(0), u16(0), u16(0), u16(0), u32(0), u32(at))),
                                member.name);
                            at += header.length + member.name.length + stored.length;
                        });
                        var directoryAt = at, directoryLength = 0;
                        directory.forEach(function (piece) { chunks.push(piece); directoryLength += piece.length; });
                        chunks.push(new Uint8Array([].concat(u32(0x06054b50), u16(0), u16(0),
                                                             u16(members.length), u16(members.length),
                                                             u32(directoryLength), u32(directoryAt), u16(0))));
                        return new Blob(chunks, {type: 'application/zip'});
                    });
            }

            // ---- the panel -------------------------------------------------
            // **Two rows above the chart rather than five.** The panel is a
            // control over the map and every row it takes is map a reader
            // cannot see — and on a steep chain the rows cost more than space:
            // the scale is the coarser of length-per-width and relief-per-
            // height, so where the height binds, a row given back is resolution.
            // Measured on the 3 km chain below, 55 px of freed height take it
            // from 6.96 to 4.72 metres a pixel, which is where its readings
            // already are. Where the width binds — a long gentle route — it
            // changes nothing, and only zooming would.
            var header = document.createElement('div');
            header.style.cssText = 'font-weight:600;cursor:pointer;user-select:none;' +
                'display:flex;gap:12px;align-items:baseline;justify-content:space-between';
            var name = document.createElement('span');
            var body = document.createElement('div');
            // Right of the title, not under it. It reads as what the title is
            // about rather than as a second thing to look at, and when nothing
            // is selected the whole panel is one line.
            var summary = document.createElement('span');
            summary.style.cssText = 'font-weight:400;color:#333;text-align:right';
            header.appendChild(name);
            header.appendChild(summary);
            var chart = document.createElementNS(SVG, 'svg');
            chart.setAttribute('height', chartHeight);
            chart.style.cssText = 'display:block;width:100%;height:' + chartHeight + 'px;cursor:crosshair';
            // What the colours mean, once, beside the figures. A curve that
            // changes colour is unreadable without it.
            var key = document.createElement('div');
            key.style.cssText = 'margin:0 0 2px;color:#666;font-size:11px';
            GRADE.bands.forEach(function (band, index) {
                var swatch = document.createElement('span');
                swatch.style.cssText = 'display:inline-block;width:14px;height:0;vertical-align:middle;margin:0 4px 0 ' +
                    (index ? '12px' : '0') + ';border-top:' + band.width + 'px solid ' + band.colour;
                var caption = document.createElement('span');
                caption.textContent = band.label + (GRADE.bands[index + 1] ? ' ' + band.from + '\u2013' + GRADE.bands[index + 1].from + ' %'
                    : ' over ' + band.from + ' %');
                if (!index) { caption.textContent = band.label + ' under ' + GRADE.bands[1].from + ' %'; }
                key.appendChild(swatch);
                key.appendChild(caption);
            });
            // And what the dash means, shown only while something in the panel
            // is dashed. A chain is never drawn straight across anything, so on
            // the phase-4 panel this row never appears.
            var freeKey = document.createElement('span');
            freeKey.style.display = 'none';
            var freeSwatch = document.createElement('span');
            freeSwatch.style.cssText = 'display:inline-block;width:14px;height:0;vertical-align:middle;margin:0 4px 0 12px;' +
                'border-top:1.6px dashed ' + GRADE.bands[0].colour;
            var freeCaption = document.createElement('span');
            freeCaption.textContent = 'drawn straight, not a path';
            freeKey.appendChild(freeSwatch);
            freeKey.appendChild(freeCaption);
            key.appendChild(freeKey);
            // The download, and beside it what the file will actually contain
            // rather than a generic notice: a stretch of FKB is unproblematic, a
            // stretch of OSM is share-alike and a stretch of UT.no is
            // non-commercial, and the reader should know which before pressing
            // the button rather than afterwards.
            // **Text, not a row of boxes.** As flex items the button, the
            // count and the licences were three things that either fitted on one
            // line or did not: a route drawing on seven sources names them in
            // some 300 characters, so the whole list moved to a line of its own
            // and left the count sitting alone beside the button. Laid out as a
            // sentence it starts where the count ends and wraps mid-list, which
            // is what a chain has always looked like — the chain's list is just
            // short enough that flex never had to choose.
            var offer = document.createElement('div');
            offer.style.cssText = 'margin:4px 0 2px;display:none';
            var download = document.createElement('button');
            download.type = 'button';
            download.textContent = 'Download GPX';
            download.style.cssText = 'font:inherit;font-size:12px;padding:2px 8px;margin-right:8px;cursor:pointer';
            var carries = document.createElement('span');
            carries.style.cssText = 'color:#333;margin-right:8px';
            var licensed = document.createElement('span');
            licensed.style.cssText = 'color:#666;font-size:11px';
            // What kind of ground the file covers, which only a route states:
            // its three marking buckets, and the length no source records a path
            // along. A chain leaves this row empty. A line of its own and
            // deliberately so: the licences say who may be asked about the file,
            // this says what ground it covers, and run together the two read as
            // one longer list of sources.
            var noted = document.createElement('span');
            noted.style.cssText = 'color:#666;font-size:11px;display:block;margin-top:2px';
            offer.appendChild(download);
            offer.appendChild(carries);
            offer.appendChild(licensed);
            offer.appendChild(noted);
            // The button and what the file carries on the left, the colour key
            // on the right: one row of things about the drawing rather than
            // three stacked above it. `key` keeps its own margins, so it is
            // pushed rather than padded apart.
            var meta = document.createElement('div');
            meta.style.cssText = 'display:flex;gap:16px;align-items:baseline;justify-content:space-between;flex-wrap:wrap';
            key.style.marginLeft = 'auto';
            meta.appendChild(offer);
            meta.appendChild(key);

            body.appendChild(meta);
            body.appendChild(chart);

            // ---- the height, which a reader owns ----------------------------
            // **Dragging this taller is not decoration.** The chart's scale is
            // the coarser of length-per-width and relief-per-height, so on a
            // chain steep enough for the height to bind, every pixel given here
            // is a finer scale: 55 px took the 3 km path off Øyfjellet from
            // 6.96 to 4.72 metres a pixel. On a long gentle route the width
            // binds and dragging changes the picture's size and nothing else,
            // which is honest — there is no detail there to uncover.
            var grip = document.createElement('div');
            grip.title = 'Drag to change the height of the profile';
            grip.style.cssText = 'height:7px;margin:-4px -10px 1px;cursor:ns-resize;' +
                'display:flex;align-items:center;justify-content:center';
            var grabbed = document.createElement('div');
            grabbed.style.cssText = 'width:38px;height:3px;border-radius:2px;background:#c4c4c4';
            grip.appendChild(grabbed);
            // The chart height the panel was last **laid out** with, which
            // is not the same as the height it has been asked for: a redraw is
            // coalesced to the next frame, so between the ask and the frame the
            // box on the page still measures the old one.
            var laidOut = chartHeight;
            var stretching = null, awaiting = false;
            grip.addEventListener('mouseenter', function () { grabbed.style.background = '#8a8a8a'; });
            grip.addEventListener('mouseleave', function () { if (!stretching) { grabbed.style.background = '#c4c4c4'; } });

            function stretchTo(pixels) {
                // **Only while the panel is open**, and that is not tidiness.
                // Folded, the box is one line with no chart in it, so the
                // overhead below measures as negative — 35 px of panel against
                // a 205 px chart, an overhead of minus 170 — and the ceiling
                // comes out taller than the map instead of shorter. A click on
                // the map folds the panel, and a click can land in the middle of
                // a drag: measured, that reopened the panel at 705 px with the
                // ceiling reading 990.
                if (!open) { return; }
                // Room for a curve at all, and never so tall that the panel is
                // the map. The overhead is measured rather than assumed: the two
                // rows above the chart are a different height in every browser.
                //
                // **Against the height the panel was laid out with, not the one
                // it was last asked for.** Two moves inside one frame otherwise
                // measure a fresh chart against a stale box: the second reads an
                // overhead of minus 620, a ceiling of 1,440, and hands out a
                // panel taller than the map. It is not a corner — Firefox
                // reports clientY as -86 the moment the pointer leaves the foot
                // of the window, so a drag that runs off the bottom delivers
                // three of them at once, and the panel opens at 900 px on a
                // 900 px map.
                var least = 60;
                var most = Math.max(least, map.getSize().y - (box.offsetHeight - laidOut) - 80);
                var wanted = Math.round(Math.min(most, Math.max(least, pixels)));
                if (wanted === chartHeight) { return; }
                chartHeight = wanted;
                // Coalesced to one draw a frame. A redraw per mouse move is the
                // mistake that froze this map twice, and a chain of eight
                // thousand samples is four hundred separate strokes.
                if (!awaiting) {
                    awaiting = true;
                    window.requestAnimationFrame(function () { awaiting = false; render(); });
                }
            }

            grip.addEventListener('mousedown', function (event) {
                if (!open) { return; }
                // The panel is anchored to the bottom of the map, so it grows
                // upwards and a pointer moving up asks for more.
                stretching = {from: event.clientY, height: chartHeight};
                grabbed.style.background = '#8a8a8a';
                event.preventDefault();
            });
            document.addEventListener('mousemove', function (event) {
                if (!stretching) { return; }
                stretchTo(stretching.height + (stretching.from - event.clientY));
            });
            document.addEventListener('mouseup', function () {
                if (!stretching) { return; }
                stretching = null;
                grabbed.style.background = '#c4c4c4';
            });

            var control = L.control({position: 'bottomleft'});
            var box = null;
            control.onAdd = function () {
                box = L.DomUtil.create('div', 'trails-profile-panel');
                box.style.cssText = 'background:rgba(255,255,255,0.94);padding:6px 10px;border:1px solid #999;' +
                    'border-radius:4px;font-family:sans-serif;font-size:12px;line-height:1.4;' +
                    // Clear of the attribution, which sits in the corner opposite
                    // and would otherwise be covered by a panel this wide.
                    'margin-bottom:22px';
                box.appendChild(grip);
                box.appendChild(header);
                box.appendChild(body);
                // Clicking and dragging inside the panel must not reach the map;
                // scrolling must, or the map freezes under an open panel.
                L.DomEvent.disableClickPropagation(box);
                return box;
            };
            control.addTo(map);

            // Leaflet inserts into a *bottom* corner rather than appending, so
            // the control added last ends up highest — the opposite of the top
            // corners, and the opposite of what this one wants. It takes the
            // foot of the map; the legend and the scale keep the corner above
            // it, whichever order they were added in.
            var corner = control.getContainer().parentNode;
            corner.appendChild(control.getContainer());

            function fold() {
                // **And the height is held to a ceiling that moves.** It was
                // clamped only where it was asked for, so a window made shorter
                // afterwards left the panel taller than the map: measured, a
                // 725 px panel in a 620 px window put its own grip at −127, off
                // the top of the map and out of a reader's reach for good.
                // Asking for the height it already has is what re-clamps it.
                if (open) { stretchTo(chartHeight); }
                // A drag does not survive the panel folding under it: the grip
                // it started on is no longer above a chart, and picking the drag
                // up again on reopening would jump the height by however far the
                // pointer travelled in between.
                if (!open && stretching) { stretching = null; grabbed.style.background = '#c4c4c4'; }
                var named = open && selected && selected.label ? ' \\u00b7 ' + selected.label : '';
                name.textContent = (open ? '\\u25be ' : '\\u25b8 ') + title + named;
                body.style.display = open ? '' : 'none';
                header.style.marginBottom = open ? '4px' : '0';
                // Full width only when there is something to show in it: folded
                // away, a full-width bar would take a strip of the map with it.
                box.style.width = open ? (map.getSize().x - 20) + 'px' : '';
            }
            header.addEventListener('click', function () { open = !open; fold(); render(); });

            // ---- the arrow, in a container of its own -----------------------
            // Not a layer and not a path on the map: the count of those is what
            // phase 3 was accepted against, and anything drawn into the overlay
            // pane joins it for ever.
            var pane = map.createPane('trailsProfileDirection');
            pane.style.zIndex = 450;
            pane.style.pointerEvents = 'none';
            // Leaflet scales the panes it animates a zoom with; this one is
            // hidden for the duration and put back where it belongs afterwards.
            L.DomUtil.addClass(pane, 'leaflet-zoom-hide');
            var arrow = document.createElementNS(SVG, 'svg');
            arrow.setAttribute('width', '96');
            arrow.setAttribute('height', '96');
            arrow.style.cssText = 'position:absolute;margin:-48px 0 0 -48px;overflow:visible;display:none';
            // Drawn pointing north and turned to the bearing, so it says the
            // same thing the words do rather than following the line's local
            // wanderings. Twice: a pale wide stroke under a dark narrow one, or
            // it disappears over a dark line.
            var SHAFT = 'M48 76 L48 28 M38 41 L48 24 L58 41';
            // The gentlest band's colour: the arrow says which way, not how
            // steep, so it takes the curve's base colour rather than a band.
            ['#ffffff', GRADE.bands[0].colour].forEach(function (colour, index) {
                var stroke = document.createElementNS(SVG, 'path');
                stroke.setAttribute('d', SHAFT);
                stroke.setAttribute('fill', 'none');
                stroke.setAttribute('stroke', colour);
                stroke.setAttribute('stroke-width', index ? '3' : '6');
                stroke.setAttribute('stroke-linecap', 'round');
                stroke.setAttribute('stroke-linejoin', 'round');
                arrow.appendChild(stroke);
            });
            pane.appendChild(arrow);

            // **And where the reader's pointer is, on the ground.** The panel
            // already knows which sample the crosshair sits on and the map wants
            // that sample's position: a profile is far easier to plan against
            // when the hill under the pointer and the hill on the map are the
            // same hill. It takes the arrow's pane for the arrow's reason — the
            // map's path count is what phase 3 was accepted against, and nothing
            // this panel draws may join it — and the crosshair's colour, because
            // the two are one thing shown in two places.
            // **Above the planned route, in a pane of its own.** It shared the
            // arrow's, at z-index 450, and plan mode's route pane is 460 — so
            // the one mark whose whole job is to say *where on this route you
            // are* was drawn underneath the route. Not the arrow's pane raised
            // instead: the arrow belongs under a route it can only ever point
            // along, and the two never show together anyway. Under the markers
            // at 600, so a waypoint's pin still covers it where they coincide,
            // which is the pin saying the same place.
            var over = map.createPane('trailsProfileHere');
            over.style.zIndex = 470;
            over.style.pointerEvents = 'none';
            L.DomUtil.addClass(over, 'leaflet-zoom-hide');
            var here = document.createElementNS(SVG, 'svg');
            here.setAttribute('width', '22');
            here.setAttribute('height', '22');
            here.style.cssText = 'position:absolute;margin:-11px 0 0 -11px;overflow:visible;display:none';
            // A pale disc under a dark one, like the arrow: over a dark line, or
            // over the dark green of a forest, a bare dot disappears.
            ['#ffffff', CROSS].forEach(function (colour, index) {
                var ring = document.createElementNS(SVG, 'circle');
                ring.setAttribute('cx', '11'); ring.setAttribute('cy', '11');
                ring.setAttribute('r', index ? '4' : '6.5');
                ring.setAttribute('fill', colour);
                here.appendChild(ring);
            });
            over.appendChild(here);

            // The position under the crosshair, in ground rather than in pixels,
            // so a pan or a zoom moves the mark with the map rather than leaving
            // it where the map used to be.
            var standing = null;

            function placeHere() {
                if (!standing) { here.style.display = 'none'; return; }
                here.style.display = '';
                L.DomUtil.setPosition(here, map.latLngToLayerPoint(standing));
            }
            map.on('zoomend viewreset moveend resize', placeHere);

            function placeArrow() {
                // Nothing is drawn for a chain with no profile — a crossing has
                // no figures for an arrow to point the way of, and an arrow
                // along it would be the only mark on the map claiming otherwise.
                var showing = selected && selected.shape && selected.shape.read && selected.mid;
                var bearing = showing ? selected.figure.bearing : null;
                if (bearing === null || bearing === undefined) { arrow.style.display = 'none'; return; }
                arrow.style.display = '';
                arrow.childNodes.forEach(function (stroke) { stroke.setAttribute('transform', 'rotate(' + bearing + ' 48 48)'); });
                L.DomUtil.setPosition(arrow, map.latLngToLayerPoint(selected.mid));
            }
            map.on('zoomend viewreset moveend resize', placeArrow);

            // ---- drawing ----------------------------------------------------
            function text(x, y, value, anchor) {
                var node = document.createElementNS(SVG, 'text');
                node.setAttribute('x', x); node.setAttribute('y', y);
                node.setAttribute('font-size', '10'); node.setAttribute('fill', TEXT);
                node.setAttribute('text-anchor', anchor || 'start');
                node.textContent = value;
                return node;
            }

            function line(x1, y1, x2, y2, colour, width) {
                var node = document.createElementNS(SVG, 'line');
                node.setAttribute('x1', x1); node.setAttribute('y1', y1);
                node.setAttribute('x2', x2); node.setAttribute('y2', y2);
                node.setAttribute('stroke', colour); node.setAttribute('stroke-width', width || 1);
                return node;
            }

            // Round numbers an axis can be read off: 1, 2 or 5 times a power of
            // ten, whichever first gives about as many steps as asked for.
            function ticks(low, high, wanted) {
                if (!(high > low)) { return [low]; }
                var rough = (high - low) / wanted;
                var power = Math.pow(10, Math.floor(Math.log(rough) / Math.LN10));
                var step = 10 * power;
                [1, 2, 5].some(function (multiple) { if (multiple * power >= rough) { step = multiple * power; return true; } return false; });
                var out = [];
                for (var value = Math.ceil(low / step) * step; value <= high + step * 1e-6; value += step) { out.push(value); }
                return out;
            }

            // ---- how much of the chain is on the panel, and at what scale ---
            // **Zoom belongs to the long chain and to a planned route, and to
            // almost nothing else.** Measured over the built graph: the median
            // chain is drawn at 0.16 metres a pixel against a series carrying a
            // height every 5.12 m, so the panel already magnifies every reading
            // it holds some thirty times over. Only 126 chains of 11,264 are
            // drawn coarser than their own samples — the 42 km Rundtur is one of
            // them, at 36.28 m/px, and a route planned here is that long by
            // nature. So this is for the route, and the chain is the exception.
            //
            // The ceiling is the data's rather than a taste: **one reading per
            // pixel**. Past it the panel magnifies the straight lines drawn
            // between samples, which claims a resolution nothing supports. It
            // works out at 7.1x on that chain and 3 to 5x on the next longest.
            //
            // ``at`` is the distance at the left edge and ``centre`` the height
            // at the middle, both in metres, because pixels change under a drag
            // of the grip and metres do not. ``centre`` is null until a window
            // turns out to be steeper than the panel — see render().
            var view = {zoom: 1, at: 0, centre: null};

            // The waypoint pins' own ink. Plan mode names it ROUTE and draws
            // its pins with it; a station on this panel is the same point seen
            // from the side, and two colours for one point would be two points.
            var STATION = '#111111', STATION_R = 7;
            // And the ink for one the height model has nothing to say about.
            var STATION_UNREAD = '#9e9e9e';

            var crosshair = null;

            // How steep the ground is at each sample, read over GRADE.window
            // rather than between neighbours. Two pointers rather than a search:
            // both ends only ever move forward, so the whole series costs one
            // pass however long it is.
            function gradients(shape) {
                var n = shape.height.length, out = new Float64Array(n);
                var half = GRADE.window / 2, lo = 0, hi = 0, i;
                for (i = 0; i < n; i += 1) {
                    out[i] = NaN;
                    if (isNaN(shape.height[i])) { continue; }
                    while (lo < i && shape.distance[i] - shape.distance[lo] > half) { lo += 1; }
                    if (hi < i) { hi = i; }
                    while (hi < n - 1 && shape.distance[hi] - shape.distance[i] < half) { hi += 1; }
                    // Pull both ends in off any ground nothing was read along:
                    // a difference across a gap is a difference across invented
                    // ground.
                    var a = lo, b = hi;
                    while (a < i && isNaN(shape.height[a])) { a += 1; }
                    while (b > i && isNaN(shape.height[b])) { b -= 1; }
                    var run = shape.distance[b] - shape.distance[a];
                    if (run >= GRADE.minRun && !isNaN(shape.height[a]) && !isNaN(shape.height[b])) {
                        out[i] = 100 * (shape.height[b] - shape.height[a]) / run;
                    }
                }
                return out;
            }

            // The steepest the ground gets along a series, absolute, over the
            // same 25 m window the curve is banded by.
            //
            // **Absolute, because a signed maximum would call this park's
            // steepest chain flat**: it climbs 9 m and drops 816. The same
            // reasoning the popups were given, and the same window, so the
            // heading, the colours and the crosshair cannot come to disagree
            // about how steep the same ground is.
            //
            // Computed here only for a **composed route**, which nothing else
            // has measured. A chain's is carried from the build, where it was
            // read off the samples at arc length rather than off the chords this
            // page sums — the two differ by about one part in a thousand, and
            // one page showing both would be showing two answers.
            function steepestOf(shape) {
                var slope = gradients(shape), worst = NaN;
                for (var i = 0; i < slope.length; i += 1) {
                    if (isNaN(slope[i])) { continue; }
                    var magnitude = Math.abs(slope[i]);
                    if (isNaN(worst) || magnitude > worst) { worst = magnitude; }
                }
                return worst;
            }

            // Which band a gradient falls in. Anything unmeasurable comes back
            // as the gentlest — a stretch too short to read a slope along is not
            // thereby steep, and colouring it would be an assertion nothing
            // supports.
            function bandOf(slope) {
                if (isNaN(slope)) { return 0; }
                var magnitude = Math.abs(slope), band = 0;
                for (var i = 0; i < GRADE.bands.length; i += 1) {
                    if (magnitude >= GRADE.bands[i].from) { band = i; }
                }
                return band;
            }

            // The points the curve is drawn through, in runs that must not be
            // joined across, each carrying the sample it came from so its band
            // can be looked up in the full series. ``from`` and ``to`` are the
            // window on the chain, which is the whole of it until something
            // zooms in.
            function drawPoints(shape, columns, from, to) {
                var runs = [], run = [], i;
                var reach = to - from;
                if (!(reach > 0)) { return runs; }
                // Samples are laid in order, so a window is a slice and not a
                // filter. Held to a hair either side, or the sample sitting
                // exactly on the end of the chain falls outside its own chain.
                var lo = 0, hi = shape.distance.length - 1;
                while (lo <= hi && shape.distance[lo] < from - 1e-6) { lo += 1; }
                while (hi >= lo && shape.distance[hi] > to + 1e-6) { hi -= 1; }
                if (hi < lo) { return runs; }
                if (hi - lo + 1 <= columns) {
                    // The common case, and it has to be: the median chain here
                    // holds 36 samples and a third of them fewer than twenty.
                    // Bucketing those into 900 columns leaves 864 empty and the
                    // curve full of holes it has no business having.
                    //
                    // One sample beyond each edge as well, and only here: zoomed
                    // into a sparse stretch the nearest reading can lie a long
                    // way outside the window, and without it the curve stops
                    // short of the edge and says nothing about why. What that
                    // draws outside the box is clipped away below.
                    var a = lo > 0 ? lo - 1 : lo, b = hi < shape.distance.length - 1 ? hi + 1 : hi;
                    for (i = a; i <= b; i += 1) {
                        if (isNaN(shape.height[i])) {
                            if (run.length) { runs.push(run); run = []; }
                            continue;
                        }
                        run.push({d: shape.distance[i], h: shape.height[i], at: i});
                    }
                    if (run.length) { runs.push(run); }
                    return runs;
                }
                // One point per pixel column for the long ones, keeping that
                // column's own lowest and highest reading, in the order they
                // occur, so no spike is lost to the reduction. The crosshair
                // still reads the full series.
                var low = new Float64Array(columns), high = new Float64Array(columns);
                var lowAt = new Int32Array(columns), highAt = new Int32Array(columns), filled = new Uint8Array(columns);
                var firstAt = new Int32Array(columns), lastAt = new Int32Array(columns);
                // How many samples up to here the model had no reading for, so
                // the question "was anything missed between these two columns"
                // is one subtraction rather than a scan. Over the whole series
                // rather than the window: the indices it is asked about are the
                // series' own, and a window does not renumber them.
                var missed = new Int32Array(shape.height.length + 1);
                for (i = 0; i < shape.height.length; i += 1) {
                    missed[i + 1] = missed[i] + (isNaN(shape.height[i]) ? 1 : 0);
                }
                for (i = lo; i <= hi; i += 1) {
                    var value = shape.height[i];
                    if (isNaN(value)) { continue; }
                    var column = Math.max(0, Math.min(columns - 1, Math.floor(((shape.distance[i] - from) / reach) * columns)));
                    if (!filled[column] || value < low[column]) { low[column] = value; lowAt[column] = i; }
                    if (!filled[column] || value > high[column]) { high[column] = value; highAt[column] = i; }
                    if (!filled[column]) { firstAt[column] = i; }
                    lastAt[column] = i;
                    filled[column] = 1;
                }
                var previous = -1;
                for (var c = 0; c < columns; c += 1) {
                    // An empty column is NOT a gap. It only says no sample landed
                    // in that pixel, and the walk carries straight through it —
                    // which is routine here, because samples are laid per edge
                    // and a chain of short edges clumps them: 2,532 samples over
                    // 1,977 columns leave 285 columns empty. Lifting the pen for
                    // those drew one gapless 6.5 km chain as 222 separate
                    // strokes. Only ground nothing was read along lifts it.
                    if (!filled[c]) { continue; }
                    if (previous >= 0 && missed[firstAt[c]] > missed[lastAt[previous] + 1]) {
                        if (run.length) { runs.push(run); run = []; }
                    }
                    var at = from + ((c + 0.5) / columns) * reach;
                    var lowFirst = lowAt[c] <= highAt[c];
                    run.push({d: at, h: lowFirst ? low[c] : high[c], at: firstAt[c]});
                    if (low[c] !== high[c]) { run.push({d: at, h: lowFirst ? high[c] : low[c], at: lastAt[c]}); }
                    previous = c;
                }
                if (run.length) { runs.push(run); }
                return runs;
            }

            // Whether a sample lies on ground the route was drawn straight
            // across rather than routed over a recorded way. A chain is never
            // any of it and carries no such series at all.
            function freeAt(shape, sample) {
                return shape.free && shape.free[sample] ? 1 : 0;
            }

            function drawCurve(shape, plot, x, y, slope, from, to) {
                // One stroke per run of segments sharing a band, so the curve is
                // its own legend: where it turns amber the ground turned steep.
                // And per run sharing a *drawing*, so a stretch the plan drew
                // straight is dashed here as it is dashed on the map — the
                // profile has to say the same thing the map does about the same
                // ground.
                var strokes = [], current;
                drawPoints(shape, Math.max(1, Math.floor(plot.width)), from, to).forEach(function (points) {
                    current = null;
                    for (var i = 1; i < points.length; i += 1) {
                        var band = bandOf(slope[points[i - 1].at]), free = freeAt(shape, points[i - 1].at);
                        if (!current || current.band !== band || current.free !== free) {
                            current = {band: band, free: free, parts: ['M' + x(points[i - 1].d).toFixed(1) + ' ' + y(points[i - 1].h).toFixed(1)]};
                            strokes.push(current);
                        }
                        current.parts.push('L' + x(points[i].d).toFixed(1) + ' ' + y(points[i].h).toFixed(1));
                    }
                });
                return strokes.map(function (stroke) { return {band: stroke.band, free: stroke.free, d: stroke.parts.join(' ')}; });
            }

            function render() {
                while (chart.firstChild) { chart.removeChild(chart.firstChild); }
                crosshair = null;
                // The mark goes with the crosshair that put it there. A wheel or
                // a drag redraws the curve without the pointer moving, and a mark
                // left behind would point at whatever is now under that pixel.
                if (standing) { standing = null; placeHere(); }
                // Cleared before every early return below, so the row never
                // outlives the curve that explained it.
                freeKey.style.display = 'none';
                if (!open) { return; }

                var width = Math.max(240, body.clientWidth || (map.getSize().x - 40));
                // The height is set here and nowhere else. It is no longer a
                // constant — a reader drags it — and a viewBox that disagreed
                // with the element it is drawn in scales the whole chart by the
                // ratio between them, which reads as a wrong slope on a panel
                // whose whole point is that the slope is right.
                chart.setAttribute('height', chartHeight);
                chart.style.height = chartHeight + 'px';
                laidOut = chartHeight;
                chart.setAttribute('viewBox', '0 0 ' + width + ' ' + chartHeight);
                chart.setAttribute('width', width);
                if (!selected || !selected.shape || !selected.shape.read) { return; }

                var shape = selected.shape;
                if (!(shape.total > 0)) { return; }
                var box = {left: PAD.left, right: width - PAD.right, top: PAD.top, bottom: chartHeight - PAD.bottom};
                var wide = box.right - box.left, tall = box.bottom - box.top;
                var lowest = Infinity, highest = -Infinity, readable = 0, i;
                for (i = 0; i < shape.height.length; i += 1) {
                    if (isNaN(shape.height[i])) { continue; }
                    readable += 1;
                    if (shape.height[i] < lowest) { lowest = shape.height[i]; }
                    if (shape.height[i] > highest) { highest = shape.height[i]; }
                }
                // A stretch of flat ground is flat ground, not a mountain: give
                // it a range of its own rather than letting the height model's
                // centimetre wobble fill the panel. Under the scale below it no
                // longer changes any angle — one metres-per-pixel serves both
                // axes — but it still caps how far a metre of wobble is blown up.
                if (highest - lowest < 20) {
                    var middle = (highest + lowest) / 2;
                    lowest = middle - 10; highest = middle + 10;
                }

                // **One metres-per-pixel for both axes, so the angle drawn is
                // the angle on the ground.** Fitting each axis to its own range
                // is what an elevation profile usually does, and it is why a
                // 73 % descent read as 18 degrees here: measured on this panel,
                // the vertical was 2.2 times coarser than the horizontal on a
                // 3 km chain and 7.5 times on a 42 km one, so the shape said
                // gentle where the crosshair said extreme. Taking the coarser of
                // the two fits the whole chain in the box at a single scale. A
                // steep chain then leaves width unused — 561 px of 1,238 for the
                // 3 km one — and a long gentle chain draws as the ribbon it is,
                // 20 px tall over 42 km. Both are the truth about the ground.
                var base = Math.max(shape.total / wide, (highest - lowest) / tall);

                // **How far in the readings let anyone go.** One per pixel, and
                // the mean spacing is the honest measure of that: the series is
                // laid per edge, so a chain does not sample evenly and a median
                // per render would cost a sort. Where a chain is already drawn
                // finer than it was measured this is 1 and nothing zooms, which
                // is 99 % of them.
                var spacing = readable > 1 ? shape.total / (readable - 1) : shape.total;
                var closest = spacing > 0 ? Math.max(1, base / spacing) : 1;
                view.zoom = Math.min(closest, Math.max(1, view.zoom));
                var metresPerPixel = base / view.zoom;
                var holds = wide * metresPerPixel;
                var shown = Math.min(shape.total, holds);
                view.at = Math.min(Math.max(0, view.at), Math.max(0, shape.total - holds));
                var from = view.at, to = view.at + shown;

                // The band is the **window's** own range and not the chain's.
                // Zoomed into a col, a panel scaled to a summit ten kilometres
                // away would draw the col as a flat line along the foot of the
                // box. At zoom 1 the window is the chain and the two are one.
                var seenLow = Infinity, seenHigh = -Infinity;
                for (i = 0; i < shape.height.length; i += 1) {
                    if (isNaN(shape.height[i])) { continue; }
                    if (shape.distance[i] < from - 1e-6 || shape.distance[i] > to + 1e-6) { continue; }
                    if (shape.height[i] < seenLow) { seenLow = shape.height[i]; }
                    if (shape.height[i] > seenHigh) { seenHigh = shape.height[i]; }
                }
                if (!(seenHigh >= seenLow)) { seenLow = lowest; seenHigh = highest; }
                if (seenHigh - seenLow < 20) {
                    var centre = (seenHigh + seenLow) / 2;
                    seenLow = centre - 10; seenHigh = centre + 10;
                }

                // **The panel's own shape is a gradient** — 171 px over 1,170,
                // or 14.6 % — and it does not move with the zoom. At a true
                // scale a window fits top to bottom exactly when the ground
                // across it averages gentler than that, so zooming in far enough
                // on steep ground must eventually overflow. Measured over the
                // six longest chains: everything fits to 4x, and at 8x three of
                // them stand 108 to 163 m over, which at that scale is 24 to
                // 36 px — the grip above the chart is where those come from.
                // Where it does stand over, the reader drags the window up and
                // down as well, and this is the only case where that does
                // anything: below it the middle is pinned and a vertical drag
                // cannot take the curve off the panel.
                var carries = tall * metresPerPixel;
                if (seenHigh - seenLow > carries) {
                    if (view.centre === null) { view.centre = (seenLow + seenHigh) / 2; }
                    view.centre = Math.min(Math.max(view.centre, seenLow + carries / 2), seenHigh - carries / 2);
                } else {
                    // **Sea level on the floor wherever it fits.** At a true
                    // scale a long route leaves most of the height unused — 39 km
                    // across this panel is 30 m to the pixel, so the box carries
                    // 5,168 m of it and a route with 658 m of relief draws as a
                    // 22 px ribbon. Centred in that surplus the ribbon sat where
                    // nothing put it, and a point standing at 0 m came out just
                    // under the middle of the box, which reads as half way up
                    // something. Anchored, the floor of the box means sea level
                    // and the ribbon's height above it is the reader's own.
                    //
                    // Clamped both ways, and both bounds are real: below sea
                    // level the lowest reading has to stay in the box, and where
                    // the height binds there is no surplus to spend, so this
                    // comes out at the midpoint and nothing moves.
                    // **Sea level stands clear of the floor rather than on
                    // it.** A waypoint resting at 0 m is a disc, and a disc on
                    // the floor is half a disc; the label had the km numbers
                    // immediately under it as well. The clearance is a layout
                    // margin and not a claim about height, so it is counted in
                    // pixels — and capped against the panel's own height, or a
                    // reader who drags it short spends a quarter of what is left
                    // on empty water.
                    var spare = Math.min(18, tall / 4) * metresPerPixel;
                    // Where the floor would have to stand for that, and how low
                    // it may go at all without pushing the high point out of the
                    // box. Where sea level cannot be reached the old midpoint is
                    // the answer: pinning the floor as low as it will go instead
                    // would jam the curve against the ceiling, which is the same
                    // arbitrariness the other way up.
                    var wanted = -spare, lowest = seenHigh - carries;
                    var floorM = wanted < lowest ? (seenLow + seenHigh - carries) / 2
                                                 : Math.min(wanted, seenLow);
                    view.centre = floorM + carries / 2;
                }

                var middleY = (box.top + box.bottom) / 2;
                var x = function (value) { return box.left + (value - from) / metresPerPixel; };
                var y = function (value) { return middleY - (value - view.centre) / metresPerPixel; };
                var plot = {left: box.left, right: box.left + shown / metresPerPixel,
                            top: Math.max(box.top, y(seenHigh)), bottom: Math.min(box.bottom, y(seenLow))};
                plot.width = plot.right - plot.left;

                // As many labels as the drawn band can hold rather than a fixed
                // four: a gentle chain is twenty pixels tall at a true scale,
                // and four heights stacked in twenty pixels is one smear. Over
                // what the box shows rather than what the window holds, so a
                // window taller than the panel is not labelled off its own edge.
                var heights = Math.max(2, Math.min(4, Math.round((plot.bottom - plot.top) / 34)));
                // **And none of them closer together than they can be read.**
                // Asking for a number of labels is not the same as having room
                // for them: a 100 m relief over 39 km draws as a three-pixel
                // ribbon, and the two this asked for landed 1.7 px apart and
                // came out as one smear. The count above says how many to aim
                // for; this says which of them there is room to draw.
                var drawnHeights = [], lastY = null;
                ticks(Math.max(seenLow, view.centre - carries / 2),
                      Math.min(seenHigh, view.centre + carries / 2), heights).forEach(function (value) {
                    var at = y(value);
                    if (lastY !== null && Math.abs(at - lastY) < 12) { return; }
                    lastY = at;
                    drawnHeights.push(value);
                    chart.appendChild(line(plot.left, at, plot.right, at, '#eceff1'));
                    chart.appendChild(text(plot.left - 6, at + 3, metres(value) + ' m', 'end'));
                });
                // One number of decimals for the whole axis, decided by how far
                // the window runs: 0.00 beside 1.0 reads as two different
                // scales. The gridlines run the box's full height rather than
                // the band's, so a twenty-pixel ribbon still has something to be
                // read against.
                // **And sea level itself, wherever the box holds it.** Every
                // other line on this axis is drawn where the data happens to
                // be; this one is the only height that means the same thing on
                // every profile, and without it the floor of the box is a number
                // a reader has to look up rather than a place they know.
                if (0 >= view.centre - carries / 2 && 0 <= view.centre + carries / 2) {
                    var sea = line(plot.left, y(0), plot.right, y(0), SEA);
                    chart.appendChild(sea);
                    // Not a second time: anchored to the floor, 0 is usually a
                    // tick already, and two labels at one height read as two
                    // heights.
                    if (!drawnHeights.some(function (value) { return Math.abs(value) < 0.5; })) {
                        var label = text(plot.left - 6, y(0) + 3, '0 m', 'end');
                        label.setAttribute('fill', SEA);
                        chart.appendChild(label);
                    }
                }

                var decimals = shown < 2000 ? 2 : 1;
                var alongs = Math.max(2, Math.min(6, Math.round(plot.width / 110)));
                ticks(from, to, alongs).forEach(function (value) {
                    chart.appendChild(line(x(value), box.top, x(value), box.bottom, '#eceff1'));
                    chart.appendChild(text(x(value), box.bottom + 14, (value / 1000).toFixed(decimals), 'middle'));
                });
                chart.appendChild(text(plot.right, box.bottom + 14, 'km', 'end'));
                chart.appendChild(line(plot.left, box.top, plot.left, box.bottom, AXIS));
                chart.appendChild(line(plot.left, box.bottom, plot.right, box.bottom, AXIS));

                // Everything that can leave the box goes in here. A window
                // steeper than the panel draws past the top and the bottom, and
                // unclipped that runs over the height labels and out of the
                // panel into the map.
                var framed = function (id, spare) {
                    var frame = document.createElementNS(SVG, 'clipPath');
                    frame.setAttribute('id', id);
                    var shield = document.createElementNS(SVG, 'rect');
                    shield.setAttribute('x', box.left - spare); shield.setAttribute('y', box.top - spare);
                    shield.setAttribute('width', Math.max(0, wide + 2 * spare));
                    shield.setAttribute('height', Math.max(0, tall + 2 * spare));
                    frame.appendChild(shield);
                    chart.appendChild(frame);
                    var group = document.createElementNS(SVG, 'g');
                    group.setAttribute('clip-path', 'url(#' + id + ')');
                    chart.appendChild(group);
                    return group;
                };
                var inside = framed('trails-profile-frame-{{ this.get_name() }}', 0);
                // **A second frame, roomier by a waypoint's own radius, in
                // both directions.** The curve's has to end where the plot does —
                // zoomed in, the run it is drawn from reaches a sample beyond
                // each edge on purpose — but a waypoint sits *at* a distance and
                // *at* a height, and a disc straddles both. Every route has a
                // point at nought and one at its end, and any point at sea level
                // sits on the floor: clipped to the plot, all of them came out
                // as half discs.
                var marks = framed('trails-profile-marks-{{ this.get_name() }}', STATION_R + 1);

                var slope = gradients(shape);
                var strokes = drawCurve(shape, plot, x, y, slope, from, to);
                if (strokes.some(function (stroke) { return stroke.free; })) { freeKey.style.display = ''; }
                strokes.forEach(function (stroke) {
                    var band = GRADE.bands[stroke.band];
                    var curve = document.createElementNS(SVG, 'path');
                    curve.setAttribute('d', stroke.d);
                    curve.setAttribute('fill', 'none');
                    curve.setAttribute('stroke', band.colour);
                    // Width escalates with the colour, so which stretch is the
                    // steep one survives a red-green confusion.
                    curve.setAttribute('stroke-width', String(band.width));
                    curve.setAttribute('stroke-linejoin', 'round');
                    curve.setAttribute('stroke-linecap', 'round');
                    // Dashed where the ground was crossed rather than followed.
                    // The gradient still bands it: the hill is real even where
                    // the line across it is a straight one somebody drew.
                    if (stroke.free) { curve.setAttribute('stroke-dasharray', FREE_DASH); }
                    inside.appendChild(curve);
                });

                // **The reader's own points, on the profile.** A route is
                // planned by putting points down on the map, and "where is the
                // climb" is only half an answer until the profile says which two
                // points the climb lies between. Drawn as the pin is drawn — a
                // pale disc, a dark ring, the same number — because they are the
                // same point seen from above and from the side, and a reader
                // should not have to work that out. Clipped with the curve: at a
                // zoom most of them are off the panel.
                (shape.stations || []).forEach(function (metres, index) {
                    var here = x(metres);
                    if (here < box.left - 1 || here > box.right + 1) { return; }
                    var sample = nearest(shape.distance, metres);
                    var value = shape.height[sample];
                    var read = !isNaN(value);
                    // **One the model has no reading for rests on the floor, not
                    // the ceiling.** It was the ceiling first, which drew a
                    // waypoint set on the water at the very top of the profile —
                    // where a summit goes, and the one thing it must not be read
                    // as. The floor is no claim either, because the box's lowest
                    // line is the window's lowest reading and not sea level, so
                    // this one is greyed and given no rule up to a curve it is
                    // not on. Drawn all the same: a route with a hole in it is
                    // exactly when a reader is looking for its points.
                    var level = read ? y(value) : box.bottom - STATION_R - 1;
                    var ink = read ? STATION : STATION_UNREAD;
                    if (read) {
                        var rule = line(here, box.bottom, here, level, STATION);
                        rule.setAttribute('stroke-dasharray', '2 2');
                        marks.appendChild(rule);
                    }
                    // **A second ring where a stage changes hands**, the same
                    // mark the pin on the map carries, because they are the same
                    // point seen from above and from the side. Under the disc
                    // rather than over it, so the number stays the clearest
                    // thing on it.
                    if (selected && selected.stages && selected.stages.indexOf(index) >= 0) {
                        var ring = document.createElementNS(SVG, 'circle');
                        ring.setAttribute('cx', here); ring.setAttribute('cy', level);
                        ring.setAttribute('r', String(STATION_R + 2.5));
                        ring.setAttribute('fill', 'none');
                        ring.setAttribute('stroke', ink);
                        ring.setAttribute('stroke-width', '1');
                        marks.appendChild(ring);
                    }
                    var disc = document.createElementNS(SVG, 'circle');
                    disc.setAttribute('cx', here); disc.setAttribute('cy', level);
                    disc.setAttribute('r', String(STATION_R));
                    disc.setAttribute('fill', '#ffffff');
                    disc.setAttribute('stroke', ink);
                    disc.setAttribute('stroke-width', '1.5');
                    marks.appendChild(disc);
                    var number = text(here, level + 3, String(index + 1), 'middle');
                    number.setAttribute('font-size', '9');
                    number.setAttribute('font-weight', 'bold');
                    number.setAttribute('fill', ink);
                    marks.appendChild(number);
                });

                // What the reader is looking at, and only where that is less
                // than all of it. On the 99 % of chains already drawn finer than
                // their own readings neither line ever appears: there is nothing
                // under the drawing to reach, and offering it would be a claim
                // to detail that does not exist.
                if (view.zoom > 1.001) {
                    chart.appendChild(text(box.left, box.top + 8, (shown / 1000).toFixed(2) + ' km of '
                        + (shape.total / 1000).toFixed(2) + ' \\u00b7 drag to move, double-click for all', 'start'));
                } else if (closest > 1.05) {
                    var hint = text(box.left, box.top + 8,
                        'Scroll here: the readings hold ' + closest.toFixed(1) + '\\u00d7 more detail than this', 'start');
                    hint.setAttribute('fill', '#9e9e9e');
                    chart.appendChild(hint);
                }

                // The crosshair's own parts, made once and moved afterwards.
                // Rebuilding them per mouse move is the mistake that froze this
                // map twice already, on a layer rather than on a chart. The rule
                // and the dot are clipped with the curve — the dot sits on it,
                // and on an overflowing window that is off the panel.
                var rule = line(plot.left, box.top, plot.left, box.bottom, CROSS);
                var dot = document.createElementNS(SVG, 'circle');
                dot.setAttribute('r', '2.5'); dot.setAttribute('fill', CROSS);
                // Against the box rather than the band: the reading has to sit
                // in the same place whether the chain drew 150 pixels tall or 20.
                var reading = text(box.right, box.top + 8, '', 'end');
                reading.setAttribute('fill', CROSS);
                [rule, dot].forEach(function (node) { node.style.display = 'none'; inside.appendChild(node); });
                reading.style.display = 'none';
                chart.appendChild(reading);
                crosshair = {rule: rule, dot: dot, reading: reading, plot: plot, width: width, x: x, y: y, at: -1,
                             slope: slope, box: box, from: from, shown: shown, mpp: metresPerPixel,
                             base: base, closest: closest};
            }

            // The nearest sample to a distance, over the full series: the
            // reduction above exists so the browser draws 900 points instead of
            // eight thousand, not so a reader hovering over a spike is told the
            // column's height instead of the spike's.
            function nearest(distance, value) {
                var low = 0, high = distance.length - 1;
                while (low < high) {
                    var middle = (low + high) >> 1;
                    if (distance[middle] < value) { low = middle + 1; } else { high = middle; }
                }
                if (low > 0 && Math.abs(distance[low - 1] - value) <= Math.abs(distance[low] - value)) { return low - 1; }
                return low;
            }

            chart.addEventListener('mousemove', function (event) {
                // Not while the window is being dragged: the pointer is moving
                // the curve then, and a reading that chased it would name a
                // different place every frame without the pointer leaving the
                // ground it started on.
                if (dragging) { return; }
                if (!crosshair || !selected || !selected.shape) { return; }
                var shape = selected.shape;
                // The drawing is scaled to whatever width the panel ended up
                // with, so a pointer position has to go back through the
                // viewBox before it means anything in the chart's own units.
                var rect = chart.getBoundingClientRect();
                var px = ((event.clientX - rect.left) / rect.width) * crosshair.width;
                // At a true scale a steep chain leaves width unused — 433 px of
                // 1,238 on the 3 km one — and there is no ground out there to
                // report. Before this the curve always filled the box, so the
                // pointer could not be past its end; now it can, and clamping
                // would pin the reading to the last sample while the pointer
                // sits a third of a panel away from it.
                if (px < crosshair.plot.left - 1 || px > crosshair.plot.right + 1) {
                    forget();
                    return;
                }
                // Through the window rather than through the chain: at zoom
                // 1 the two are the same arithmetic, and past it only this one
                // is right.
                var at = nearest(shape.distance, crosshair.from + (px - crosshair.plot.left) * crosshair.mpp);
                if (at === crosshair.at) { return; }
                crosshair.at = at;
                // The mark on the map, before anything is written: a reader
                // following a climb wants to see where it is, and the sentence
                // beside it is the slower half of the answer.
                standing = positionAt(shape, shape.distance[at]);
                placeHere();
                var here = crosshair.x(shape.distance[at]);
                crosshair.rule.setAttribute('x1', here); crosshair.rule.setAttribute('x2', here);
                crosshair.rule.style.display = '';
                var value = shape.height[at];
                var read = !isNaN(value);
                crosshair.dot.style.display = read ? '' : 'none';
                if (read) {
                    crosshair.dot.setAttribute('cx', here);
                    crosshair.dot.setAttribute('cy', crosshair.y(value));
                }
                crosshair.reading.style.display = '';
                var steep = crosshair.slope[at];
                var gradient = '';
                if (!isNaN(steep)) {
                    var band = GRADE.bands[bandOf(steep)];
                    gradient = ' \\u00b7 ' + (steep < 0 ? '\\u2212' : '+') + Math.round(Math.abs(steep)) + ' %'
                        + (bandOf(steep) ? ', ' + band.label : '');
                }
                crosshair.reading.textContent = (shape.distance[at] / 1000).toFixed(2) + ' km \\u00b7 '
                    + (read ? metres(value) + ' m' : 'not read') + gradient;
            });

            // Everything the crosshair is showing, taken back: the rule, the
            // reading, and the mark on the map. In one place because they have to
            // go together — a dot left on the map after the pointer has gone
            // claims a position nobody is pointing at.
            function forget() {
                if (crosshair && crosshair.at !== -1) {
                    crosshair.at = -1;
                    [crosshair.rule, crosshair.dot, crosshair.reading].forEach(function (node) { node.style.display = 'none'; });
                }
                if (standing) { standing = null; placeHere(); }
            }

            chart.addEventListener('mouseleave', forget);

            // ---- the window on the chain, which a reader moves ---------------
            // One redraw a frame, for the reason the grip has one: a redraw per
            // event is the mistake that froze this map twice, and a long chain
            // is four hundred separate strokes.
            var settling = false;
            function redraw() {
                if (settling) { return; }
                settling = true;
                window.requestAnimationFrame(function () { settling = false; render(); });
            }

            // **The wheel stays the map's, except over a curve that can use it.**
            // A panel that swallows a wheel and does nothing with it reads as
            // the map having frozen the moment the panel opened — which is why
            // this panel has only ever taken clicks, and why the map's own
            // 9 to 11 is unchanged everywhere else on it. So the chart takes the
            // wheel exactly where there is detail under the drawing to reach,
            // and lets it through where there is not: 126 chains of 11,264, and
            // every route long enough to be worth planning.
            chart.addEventListener('wheel', function (event) {
                if (!crosshair || !(crosshair.closest > 1.001)) { return; }
                event.preventDefault();
                event.stopPropagation();
                // A wheel says its delta in pixels, lines or pages, and a line
                // is not a pixel. Four notches of a mouse double the scale.
                var step = event.deltaY * (event.deltaMode === 1 ? 20 : (event.deltaMode === 2 ? 400 : 1));
                var wanted = Math.min(crosshair.closest, Math.max(1, view.zoom * Math.pow(2, -step / 400)));
                if (wanted === view.zoom) { return; }
                var rect = chart.getBoundingClientRect();
                var px = ((event.clientX - rect.left) / rect.width) * crosshair.width;
                // The ground under the pointer stays under the pointer, which is
                // what makes a wheel read as a lens rather than as a slider.
                var under = crosshair.from + (px - crosshair.box.left) * crosshair.mpp;
                view.zoom = wanted;
                view.at = under - (px - crosshair.box.left) * (crosshair.base / wanted);
                redraw();
            }, {passive: false});

            // Dragging moves the window, in both directions: along the chain,
            // and up and down where the window is steeper than the panel and so
            // does not all fit. render() pins the second whenever it does fit,
            // so there is no way to drag the curve off its own panel.
            var dragging = null;
            chart.addEventListener('mousedown', function (event) {
                if (!crosshair || !(view.zoom > 1.001)) { return; }
                forget();
                dragging = {x: event.clientX, y: event.clientY, at: view.at, centre: view.centre, mpp: crosshair.mpp};
                chart.style.cursor = 'grabbing';
                event.preventDefault();
            });
            document.addEventListener('mousemove', function (event) {
                if (!dragging) { return; }
                view.at = dragging.at - (event.clientX - dragging.x) * dragging.mpp;
                view.centre = dragging.centre + (event.clientY - dragging.y) * dragging.mpp;
                redraw();
            });
            document.addEventListener('mouseup', function () {
                if (!dragging) { return; }
                dragging = null;
                chart.style.cursor = 'crosshair';
            });

            // Back to the whole chain. The map never sees this — the panel stops
            // clicks at its own edge — and the header's own click, which folds
            // the panel away, is a different element.
            chart.addEventListener('dblclick', function (event) {
                if (!(view.zoom > 1.001)) { return; }
                event.preventDefault();
                view.zoom = 1; view.at = 0; view.centre = null;
                redraw();
            });

            // ---- what is selected -------------------------------------------
            var selected = null;
            // Whether something else owns the map's clicks. Plan mode does
            // while it is on: a click there places a waypoint, and a panel that
            // also answered it would select a chain out from under the route.
            var suspended = false;

            // What to call the selected line in the heading: its own hover text
            // where it has one, and its chain id where it has not. A tooltip is
            // markup — folium wraps the name in a div — and this is written into
            // a heading as text, so the tags come out rather than being rendered.
            function labelOf(layer, className) {
                var tooltip = layer.getTooltip && layer.getTooltip();
                var content = tooltip && tooltip.getContent();
                if (typeof content === 'string') { return content.replace(/<[^>]*>/g, ' ').replace(/\\s+/g, ' ').trim(); }
                if (content && content.textContent) { return content.textContent.trim(); }
                return (figures[className] || {}).id;
            }

            function say(message) {
                summary.textContent = message;
            }

            // What a composed series says about itself. The distance is the
            // **walking** distance and says so: a crossing is never counted
            // into it, and whatever composed the series reports the crossings
            // beside it in `told`. A flat line at zero would be a claim about
            // ground that is not there, and so would a total that swallowed a
            // crossing.
            // `extra` is handed in rather than read off the selection: the
            // panel says this above the button and the file says it in the
            // track's <desc>, and the two must be one sentence written once.
            function planned(figure, shape, extra) {
                var told = [];
                if (shape.read) { told.push(climb(figure)); }
                told.push((shape.total / 1000).toFixed(2) + ' km on foot');
                if (shape.read) {
                    told.push('high ' + metres(figure.high) + ' m', 'low ' + metres(figure.low) + ' m');
                    var worst = steepestOf(shape);
                    if (!isNaN(worst)) { told.push('steepest ' + Math.round(worst) + ' %'); }
                }
                told = told.concat(extra || []).concat(protectedIn(shape));
                if (!shape.read) {
                    told.push(shape.total > 0 ? 'no height was read along it' : 'no ground under any of it');
                }
                return told;
            }

            // Which protected areas the route runs through and how far through
            // each. Read off the list whatever composed the route already
            // filtered, never re-filtered here: the sentence above the button,
            // the sentence in the file and the markers the file carries have to
            // name the same areas, and a second application of a threshold is a
            // second threshold.
            //
            // **It says where the route is and nothing about what may be done
            // there.** The rules inside a Norwegian protected area differ from
            // outside, but how they differ is in each area's verneforskrift and
            // not one has been read. This is a fact about the route.
            function protectedIn(shape) {
                return (shape.protected || []).map(function (area) {
                    return (area.metres / 1000).toFixed(2) + ' km in ' + area.name + ' ' + area.form;
                });
            }

            function describe() {
                if (!selected) { say(suspended ? 'Plan mode: click the map to place a point.' : 'Click a line to see its profile.'); return; }
                var figure = selected.figure, shape = selected.shape;
                if (!shape) { say(selected.saying || 'Decoding the network\\u2026'); return; }
                if (selected.composed) { say(planned(figure, shape, selected.told).join(' \\u00b7 ')); return; }
                if (!shape.read) {
                    // Two kinds of nothing, and they are not the same nothing.
                    // A flat line at zero would be a claim about ground that was
                    // never asked about.
                    say(shape.crossing
                        ? 'No profile: there is no ground under a crossing.'
                        : 'No profile: the height model has no reading along this stretch.');
                    return;
                }
                // The chain's steepest is the **build's**, the same number its
                // popup carries, and not one worked out here from the drawn
                // series: those two agree to about a part in a thousand and
                // disagree in the third decimal, which is one number too many
                // for one chain in one page.
                var steepest = figure.steepest;
                say(climb(figure) + ' \\u00b7 high ' + metres(figure.high) + ' m \\u00b7 low ' + metres(figure.low) +
                    ' m \\u00b7 ' + (shape.total / 1000).toFixed(2) + ' km' +
                    (steepest === null || steepest === undefined || isNaN(steepest)
                        ? '' : ' \\u00b7 steepest ' + Math.round(Math.abs(steepest)) + ' %') +
                    (figure.bearing === null ? ' \\u00b7 a loop, so it climbs the same either way' : ''));
            }

            // What pressing the button would get you, worked out from the same
            // series the file is written from rather than estimated beside it.
            // The points are counted here and written there, so the figure a
            // reader is shown is the one the file holds.
            function offered() {
                if (!EXPORT) { return; }
                // A series composed by something that offered no description of
                // what it composed cannot be written out: the file has to say
                // what its legs are and where its waypoints went, and a button
                // this panel could not honour is worse than no button at all.
                offer.style.display = (selected && (!selected.composed || selected.plan)) ? 'block' : 'none';
                noted.textContent = '';
                if (!selected || (selected.composed && !selected.plan)) { return; }
                if (!selected.shape) {
                    download.disabled = true;
                    // Whatever went wrong with the graph is said once, above,
                    // by the line that knows what it was. Saying 'decoding' here
                    // as well would contradict it — and a reader believes the
                    // thing next to the button they were about to press.
                    carries.textContent = selected.missing ? '' : 'Decoding the network\\u2026';
                    licensed.textContent = '';
                    return;
                }
                selected.runs = runsOf(selected.shape);
                var points = pointsIn(selected.runs);
                if (selected.composed) {
                    // **Refused while any leg is unsettled, and said.** The file
                    // states that it breaks only at crossings; a leg still being
                    // worked out, or one the height service refused, is a hole
                    // that would break it somewhere else and nothing in the file
                    // would say so.
                    download.disabled = points < 2 || !!selected.plan.why;
                    // Only what the header does not already say. It carried
                    // the climb, the crossings and the distance a second time,
                    // word for word, in the row underneath the row that said
                    // them — five rows where two will do.
                    carries.textContent = selected.plan.why ? selected.plan.why
                        : points.toLocaleString('en-GB') + ' points';
                    licensed.textContent = routeCredits(selected.shape, selected.runs).map(licenceLine).join(' \\u00b7 ');
                    noted.textContent = markingLine(selected.shape.tally);
                    return;
                }
                download.disabled = points < 2;
                // The climb and the distance are in the header. What belongs
                // here is what only the file has — how many points it holds —
                // and the one case the header cannot show, a stretch the height
                // model never read, because then the header says so instead.
                carries.textContent = points.toLocaleString('en-GB') + ' points';
                licensed.textContent = creditsOf(selected.figure, selected.runs).map(licenceLine).join(' \\u00b7 ');
            }

            if (EXPORT) {
                download.addEventListener('click', function () {
                    if (!selected || !selected.runs) { return; }
                    if (selected.composed) {
                        if (!selected.plan || selected.plan.why) { return; }
                        saveFile(fileNameOf(EXPORT.route.fileStem),
                                 routeGpxOf(selected.figure, selected.shape, selected.runs, selected.plan, selected.told, crossings()));
                        return;
                    }
                    saveFile(fileNameOf(selected.figure.id), gpxOf(selected.figure, selected.shape, selected.runs));
                });
            }

            // Everything that happens whatever is selected. Two things reach
            // the panel — a chain, whose figures are read off the table this
            // was handed, and a series composed elsewhere — and they differ
            // only in how they arrive.
            function present(given) {
                selected = given;
                // A window belongs to the chain it was opened on. Carried over,
                // it would open the panel somewhere in the middle of whatever
                // the reader just clicked, at a scale chosen for something else.
                view.zoom = 1; view.at = 0; view.centre = null;
                // Open on a selection and folded away again the moment there is
                // none: a panel this wide takes a strip of the map with it, and
                // it may only do that while it has something to show there.
                open = selected !== null;
                // What the panel is showing, the way the graph itself arrives as
                // window.trailsGraph: the series it laid out and the figures it
                // was handed, so a browser check can read them rather than a
                // screenshot.
                window.trailsProfile = selected;
                fold();
                describe();
                offered();
                render();
                placeArrow();
            }

            // The panel's second way in. A planned route has no chain and no
            // row in the figures table, so what arrives is the composed series
            // itself and the figures already read off it; the bands, the
            // crosshair and the reduction all apply unchanged.
            window.trailsProfilePanel = {
                series: function (spec) {
                    present(spec === null ? null : {
                        composed: true, label: spec.label, figure: spec.figure, shape: spec.shape,
                        told: spec.told || [], saying: spec.saying, mid: null,
                        // Which of the points below the curve are where one
                        // stage hands over to the next. The panel draws every
                        // point the same; what a point *means* belongs to
                        // whatever composed the series.
                        stages: spec.stages || null,
                        // What the panel cannot work out from a series alone and
                        // the file cannot be written without: where the reader
                        // put its points down, what each leg is made of, and
                        // whether the route has a hole in it. Absent, the series
                        // still draws and is not offered as a file.
                        plan: spec.plan || null});
                },
                suspend: function (taken) {
                    suspended = !!taken;
                    if (suspended) { present(null); }
                },
                // The two things a second consumer must not write for itself:
                // the walk that lays edges end to end, and the metre this page
                // measures distance with. A route composed by a second walk
                // would still look like a route.
                layEdges: layEdges,
                metresBetween: metresBetween,
                // And where the selection crosses a protected boundary, which
                // is a method rather than a field because asking costs 45 ms
                // over a 37 km route. The file is written from what this
                // returns, so a check reads the same list the file carries.
                crossings: crossings,
                // And which part of the chain is on the panel, at what scale,
                // and how much finer the readings would let it go. A window is
                // a thing to be read rather than screenshotted, the same as the
                // series and the figures above it; ``closest`` is 1 wherever the
                // panel is already drawn finer than the ground was measured,
                // which is 99 % of the chains here.
                view: function () {
                    return {zoom: view.zoom, at: view.at, centre: view.centre,
                            metresPerPixel: crosshair ? crosshair.mpp : null,
                            shown: crosshair ? crosshair.shown : null,
                            closest: crosshair ? crosshair.closest : null};
                },
                // **Writing a route the panel is not showing.** A stage of a
                // plan is a range of one walk, and the file it becomes has to
                // come out of the same writer as the whole tour's: a second
                // writer would eventually disagree with the first about a route
                // it was handed the same way, which is the failure this project
                // keeps finding. So composing stays with the plan, which is the
                // only thing that knows where a stage begins, and writing stays
                // here, which is the only thing that knows what a file says.
                //
                // Its runs and its crossings are worked out from the shape it is
                // given and never sliced from the whole tour's — a stage that
                // inherited an `Enters` from ground it never covers would be a
                // file stating something about somewhere else.
                routeFile: function (figure, shape, told, plan, suffix) {
                    if (!EXPORT) { throw new Error('this panel was given nothing to write a file with'); }
                    var runs = runsOf(shape);
                    // **The title and the file name come apart for a stage.**
                    // What a device shows is the track's name, so a stage has to
                    // be named as one or four files read as four copies of the
                    // tour; what goes in the file name is the tour, with the
                    // stage as its suffix, or the stage's own name lands in it
                    // twice.
                    var stem = (plan && (plan.stem || plan.name)) || EXPORT.route.fileStem;
                    return {name: fileNameOf(stem + (suffix ? '-' + suffix : '')),
                            text: routeGpxOf(figure, shape, runs, plan, told || [],
                                             crossingsOf(shape, runs))};
                },
                // What a tour is called where nobody has called it anything, so
                // the plan can offer it as a placeholder and tell a name a
                // reader chose apart from the one every file carries by default.
                routeName: function () { return EXPORT ? EXPORT.route.name : null; },
                // Whether this panel was given what a file needs at all. A page
                // may have a profile and no export — the panel hides its own
                // button for exactly that — and anything else offering files off
                // the back of it has to ask rather than assume.
                writes: function () { return !!EXPORT; },
                // Handing a name and a body to the browser, which is one place
                // and not two: the anchor has to be in the document for the
                // click to count, and that was measured rather than assumed.
                save: saveFile,
                // Several files as one download. The plan says which files,
                // because it is the only thing that knows what a stage is.
                saveZip: function (files, plan) {
                    if (!EXPORT) { throw new Error('this panel was given nothing to write a file with'); }
                    // **The title and the file name come apart for a stage.**
                    // What a device shows is the track's name, so a stage has to
                    // be named as one or four files read as four copies of the
                    // tour; what goes in the file name is the tour, with the
                    // stage as its suffix, or the stage's own name lands in it
                    // twice.
                    var stem = (plan && (plan.stem || plan.name)) || EXPORT.route.fileStem;
                    return zipOf(files).then(function (blob) { saveFile(fileNameOf(stem, '.zip'), blob); });
                }
            };

            function show(className, label) {
                var chosen = className === null ? null : {className: className, figure: figures[className], label: label, shape: null, mid: null};
                if (chosen && !chosen.figure) { chosen = null; }
                present(chosen);
                if (!selected) { return; }
                if (!window.trailsGraph) {
                    selected.missing = true;
                    say('There is no routing graph in this page, so there is no profile to draw.');
                    offered();
                    return;
                }
                var wanted = selected.className;
                window.trailsGraph.ready.then(function (graph) {
                    // The reader may well have clicked something else while a
                    // megabyte of arithmetic was going on.
                    if (!selected || selected.className !== wanted) { return; }
                    var index = graph.chainOf[selected.figure.id];
                    if (index === undefined) {
                        selected.missing = true;
                        say('This line is not in the routing graph.');
                        offered();
                        return;
                    }
                    selected.shape = scale(compose(graph, index), selected.figure.length);
                    selected.mid = midpoint(selected.shape);
                    describe();
                    offered();
                    render();
                    placeArrow();
                // Two handlers rather than a .catch: a catch would also swallow
                // anything thrown while drawing and report it as a graph that
                // never arrived, which is the wrong cause and sends the next
                // reader looking in the wrong place. A drawing fault belongs in
                // the console, loudly.
                }, function () {
                    if (selected && selected.className === wanted) { selected.missing = true; }
                    say('The routing graph did not arrive, so there is no profile to draw.');
                    offered();
                });
            }

            groups.forEach(function (group) {
                group.eachLayer(function (layer) {
                    if (!layer.setStyle || !layer.options.className) { return; }
                    layer.on('click', function () {
                        if (suspended) { return; }
                        var className = layer.options.className;
                        show(selected && selected.className === className ? null : className, labelOf(layer, className));
                    });
                });
            });
            // Leaflet only fires a map click where the click hit no layer, which
            // is what clears the selection on empty terrain — the same rule the
            // click-highlight follows, so the two cannot drift apart.
            map.on('click', function () { if (!suspended) { show(null); } });
            // A panel this wide is sized against the map, so a resized window
            // has to size it again before anything is drawn into it.
            map.on('resize', function () { fold(); render(); placeArrow(); });

            fold();
            describe();
            offered();
            render();
        })();
        {% endmacro %}
    """)

    def __init__(
        self,
        groups: list[folium.FeatureGroup],
        figures: dict[str, dict[str, object]],
        title: str,
        chart_height: int,
        collapsed: bool,
        export: dict[str, Any] | None,
    ) -> None:
        """Initialize the panel.

        Args:
            groups: Feature groups whose lines can be selected
            figures: Mapping of CSS class to the figures of the line carrying it
            title: Panel heading, doubling as the fold handle
            chart_height: Height of the drawing area in pixels
            collapsed: Whether it starts folded away
            export: What the page needs to write a GPX file, or None for a panel
                that only draws. See :func:`add_profile_panel`.
        """
        super().__init__()
        self._name = "ProfilePanel"
        self.group_names = [group.get_name() for group in groups]
        self.figures_json = _script_json(figures)
        self.title_json = _script_json(title)
        self.chart_height = int(chart_height)
        self.collapsed = collapsed
        # Through _script_json like everything else that lands inside a script
        # block: a licence or a source name carrying a '<' would otherwise close
        # it, and json.dumps leaves that character alone.
        self.export_json = _script_json(export)
        # The bands travel rather than being written into the template, so the
        # measurement that chose them and the colours that show them sit in one
        # documented place.
        self.gradient_json = _script_json(
            {
                "window": GRADIENT_WINDOW_M,
                "minRun": GRADIENT_MIN_RUN_M,
                "bands": [{"from": lower, "label": label, "colour": colour, "width": width} for lower, label, colour, width in GRADIENT_BANDS],
            }
        )


def add_profile_panel(
    fmap: folium.Map,
    groups: list[folium.FeatureGroup],
    title: str = "Elevation profile",
    #: Raised from 150 when the panel's five rows above the chart became two.
    #: Not decoration: the scale is the coarser of length-per-width and
    #: relief-per-height, so on a chain steep enough for the height to bind, a
    #: row given back is resolution. Measured on a 3 km chain dropping 807 m,
    #: these 55 px take it from 6.96 to 4.72 metres a pixel — its readings are
    #: 4.5 m apart, so that is as fine as the data goes. On a long gentle route
    #: the width binds and this changes nothing.
    chart_height: int = 205,
    collapsed: bool = True,
    export: dict[str, Any] | None = None,
) -> None:
    """Draw the selected chain's profile at the foot of the map, and offer it.

    Clicking a line opens the panel on its profile: distance against elevation,
    with the ascent, descent, high and low point the chain carries, and an arrow
    on the map pointing the way those figures were read. Clicking it again, or
    clicking empty terrain, closes it. The heading folds it away.

    **Every figure it shows is read, not computed.** They travel with the layers
    as :data:`CHAIN_FIGURES_ATTR`, put there by :func:`add_trails`; the elevation
    series is decoded from the payload :func:`add_routing_graph` put in the page,
    and only the curve and the distance under it come out of that. A chain whose
    series holds no reading at all — a ferry crossing, or a stretch outside the
    height model — says so instead of drawing a flat line at zero.

    **The crosshair marks its position on the map.** Hovering the curve puts a
    dot on the ground the reading came from, which is what makes a profile worth
    planning against: the climb in the panel and the climb on the map become one
    thing. A chain and a planned route both get it. It is taken back whenever the
    pointer leaves, the curve is redrawn or the window is dragged, so it can never
    name a place nobody is pointing at.

    **The curve can be zoomed into, where there is anything to see.** A wheel
    over it takes the window down to one height reading per pixel and no
    further; past that the panel would be magnifying the straight lines drawn
    between samples. On this map that is worth doing on 126 chains of 11,264 —
    the rest are already drawn finer than the ground under them was measured —
    and on every route long enough to be worth planning. Everywhere it is not
    worth doing the wheel goes to the map, as it always has. The scale stays
    true in both axes throughout, dragging moves the window, and a double click
    puts the whole chain back.

    **And it writes the chain out.** Given ``export``, the panel offers the
    selected chain as a GPX file — every vertex, a point wherever two are
    further apart than ``gapM``, an ``<ele>`` on each and no ``<time>`` on any —
    and says what the file will contain before the button is pressed rather than
    after: how many points, what it climbs, and which licence each source it
    draws on carries. The browser is the only thing that can write that file, so
    everything in it has to be in the page: the sources, their licences and
    their versions come through here, because nothing in a page can invent them.

    Call after the layers and after :func:`add_routing_graph`, whose payload it
    reads. It shares the bottom left with the legend and the scale bar and puts
    itself under both, so the order it is added in does not matter.

    Args:
        fmap: Map holding the layers
        groups: Feature groups returned by :func:`add_trails`
        title: Panel heading, which doubles as the fold handle
        chart_height: Height of the drawing area in pixels
        collapsed: Whether it starts folded away
        export: What the page needs to write a GPX file, or None for a panel
            that only draws one. It carries ``credits`` — the sources a chain of
            each dataset draws on, each with its licence and the version it was
            read at — ``heights``, the same for the height model every ``<ele>``
            comes from, ``fields``, the figure keys a track's ``<extensions>``
            are written from and the names they travel under,
            ``sourceLength``, the credit field a route states each source's
            contributed metres in, ``route`` and ``waypoint``, the names a
            planned route's own file is written with, and the writer's
            own settings: ``gapM``, ``decimals``, ``elevationDecimals``,
            ``coordinateDecimals``,
            ``namespace``, ``prefix``, ``creator``, ``description``,
            ``ascentMethod``, ``identitySeparator`` and ``filePrefix``. The
            names come from :mod:`trails.io.export.gpx`, which writes the same
            file from Python; that module's docstring says what the two agree
            on, how closely, and where the difference comes from.

    Raises:
        ValueError: If ``export`` leaves out something the page cannot write the
            file without. A page that quietly wrote ``undefined`` into a licence
            is worse than one that was never built.
    """
    if not groups:
        return

    figures: dict[str, dict[str, object]] = {}
    for group in groups:
        figures.update(getattr(group, CHAIN_FIGURES_ATTR, {}))
    if not figures:
        return

    if export is not None:
        missing = sorted(set(EXPORT_SETTINGS) - set(export))
        # And into the two that are dicts of names rather than single values.
        # Reported under the key they sit in, so a caller is told where to look
        # rather than that something called "partLength" is missing.
        for key, wanted in (("route", EXPORT_ROUTE_SETTINGS), ("waypoint", EXPORT_WAYPOINT_SETTINGS)):
            inside = export.get(key)
            if isinstance(inside, dict):
                missing += sorted(f"{key}.{name}" for name in set(wanted) - set(inside))
        if missing:
            raise ValueError(f"the page cannot write a GPX file without {', '.join(sorted(missing))}")

    _ProfilePanel(groups, figures, title, chart_height, collapsed, export).add_to(fmap)


class _PlanMode(MacroElement):
    """Plan mode: clicking a route together, leg by leg, and then working on it.

    Switch it on and every click appends a waypoint and works out the way from
    the one before, so a route grows as far as a reader cares to take it. Four
    edits then make it something to work on rather than to restart: **insert**
    into the middle, which splits a leg; **remove**, which merges two; **move a
    point earlier or later**, which changes which legs there are at all; and
    **drag**, which moves one where it stands.

    **The legs follow from the waypoints rather than being edited beside them.**
    Every edit rewrites the list of points and nothing else; a leg survives
    exactly when it still runs between the same two waypoints, and a waypoint
    that has moved is a new object rather than a mutated one. What each edit
    costs falls out of that, and so does the cancellation: a reply about ground
    a waypoint has since left arrives to find its leg no longer on the route.

    **One click, three meanings, decided in one place.** A click on a pin selects
    it, a click within a few pixels of the drawn route puts a point into that
    leg, and a click on anything else puts one on the end. Nothing the route
    draws is interactive — the leg a click landed on is found by hit-testing the
    geometry the page already holds — because a line that catches clicks would
    have to stop catching them the moment plan mode is switched off, which is the
    mistake the park boundary made for a fortnight.

    **A drag is throttled and asks the height service nothing until it ends.**
    Placing a point costs 19-76 ms including its Dijkstra, so the two legs a
    dragged waypoint moves are 40 to 160 ms and are settled every 120 ms rather
    than at the rate a pointer reports. A leg the network cannot carry is carried
    at its own straight length with no heights while the pointer is down: its
    ground is new at every position, the endpoint cache answers only for ends
    already visited, and asking anyway is an uncapped stream of requests to
    somebody else's service.

    **A leg has four kinds and they are parts of a leg, not legs.** That is what
    they are on the ground: a routed leg that takes a ferry is walked, then
    crossed, then walked again, and a leg drawn straight across a strait splits
    at the shoreline into the same two things. A model that knew only whole legs
    would have to be widened the first time either happened, and both happen
    here.

    ======= ==================== ==============================
    kind    distance counts as   profile
    ======= ==================== ==============================
    routed  on foot              read off the payload
    land    on foot              sampled on demand
    water   a **crossing**       none
    ferry   a **crossing**       none
    ======= ==================== ==============================

    **A crossing is never added to the walking distance and never to an ascent.**
    It is reported beside them — *42 km on foot · 2 crossings, 31 km* — and it
    contributes no curve at all, because a flat line at zero is a claim about
    ground that is not there.

    **Nothing here is drawn into the overlay pane.** The route, its waypoints and
    everything else this adds live in a pane of their own: what goes into the
    overlay pane is counted among the map's paths for ever after, and that count
    is an acceptance figure for every phase from the third.

    Hand-written, like the panel, the legend and the search: a routing library
    pulled from a CDN does not load on a ``file://`` page and fails silently, the
    way the OpenStreetMap tiles once did. So the heap, the search and the
    adjacency are all here, and they are cheap — the adjacency is derived from
    the payload's own columns rather than shipped beside them.

    **The route's series is laid out in one walk, not two.** The profile wants
    heights against distance and the exported file wants coordinates, and
    composing those separately would be two walks over one route that could
    disagree — each still looking like a route. So ``composeRoute`` produces the
    shape a chain's series has, which is what the panel's writer already knows
    how to read, and the geometry that existed per part but was never composed
    is what made this more than wiring.

    **What a route is made of is summed per edge**, where the edges are still in
    hand: which dataset drew each metre, whether anything says it is waymarked,
    and whether any source records a path along it. A part keeps its geometry
    and its heights and nothing downstream can get back to the edge a metre came
    from. Unknown is its own bucket and is never folded into unmarked, and a
    connector nobody drew was never asked rather than asked and unanswered.

    It arrives as ``window.trailsPlan``, whose ``state()`` says what the route is
    and whose ``place()`` is the entry a click uses, so a browser check can drive
    it and read it rather than screenshot it.
    """

    _template = Template("""
        {% macro script(this, kwargs) %}
        (function () {
            var map = {{ this._parent.get_name() }};
            var PLAN = {{ this.plan_json }};

            // Everything named that the map draws at a position, as a table:
            // name, what it is and where. The markers themselves cannot answer
            // this — their names are inside popup HTML — and a route's file
            // reading 'Lavasshytta -> Sæterskaret skogstue -> Bønå ferjekai'
            // rather than three coordinates is the whole of what it buys.
            var NAMED = {{ this.points_json }};

            // The route's own colours. Near-black over the pale topo backdrop,
            // which nothing else on this map uses: a plan is the reader's own
            // and should not read as another dataset. A pale wide stroke under
            // a dark narrow one, or it disappears over a dark line.
            var ROUTE = '#111111', CASING = '#ffffff', WAITING = '#9e9e9e';

            // What the payload's own header calls a crossing and an inferred
            // connector, handed in rather than spelled here: renaming either in
            // trails.routing.sources would otherwise leave this page reading
            // every ferry as walked ground, and nothing would look wrong.
            var CROSSING = PLAN.crossingKind, CONNECTOR = PLAN.connectorKind;

            // How each kind is drawn. Routed is a line; ground drawn straight
            // across is dashed exactly as the profile dashes it; a crossing is a
            // wider gap still, because it is not walked at all. A leg not yet
            // worked out is neither, and says so by being grey.
            //
            // **The crossing's key is the name that arrived, not the word
            // 'ferry'.** Spelled out, a rename in trails.routing.sources would
            // leave this table without an entry for the kind routedParts emits,
            // and an undefined dashArray draws a fjord crossing as a solid line
            // indistinguishable from walked ground — which is the one thing this
            // page must never draw, and nothing about it would look wrong.
            var DASH = {routed: null, land: '5,4', water: '2,8', waiting: '1,6'};
            DASH[CROSSING] = '2,8';

            // ---- what the panel owns and this must not write again ----------
            // Laying a run of edges end to end and the metre this page measures
            // distance with both live in the profile panel. A second walk here
            // would eventually disagree with the one the panel draws and the
            // export writes, and a route composed by the wrong walk still looks
            // like a route. Read late rather than at load, so the two scripts
            // need no order between them beyond the one the builder gives.
            var owned = null;

            function panel() {
                if (!owned) { owned = window.trailsProfilePanel || null; }
                return owned;
            }

            // ---- the router --------------------------------------------------
            // Built on the first route asked for and then kept. The payload
            // carries edges, nodes and geometry and nothing else — no cost
            // column, deliberately, because a cost is length times the source's
            // factor and the page has both. Deriving it here is a pass over the
            // geometry; shipping it would be a megabyte of numbers the browser
            // can work out for itself.
            var routing = null;

            function router(graph) {
                if (routing) { return routing; }
                var edges = graph.header.edges, nodes = graph.header.nodes, i;
                // Hoisted out of a loop that runs once per vertex, of which
                // there are 948,465.
                var between = panel().metresBetween;

                var length = new Float64Array(edges), cost = new Float64Array(edges);
                for (i = 0; i < edges; i += 1) {
                    var run = 0;
                    for (var v = graph.vertexAt[i] + 1; v < graph.vertexAt[i + 1]; v += 1) {
                        run += between(graph.coordinates[2 * v - 2], graph.coordinates[2 * v - 1],
                                       graph.coordinates[2 * v], graph.coordinates[2 * v + 1]);
                    }
                    length[i] = run;
                }

                // How long the chain each edge lies on is, which only a crossing
                // needs. The payload lays a chain's edges out as one contiguous
                // run, so this is one pass and no index.
                var whole = new Float64Array(edges);
                for (var chain = 0; chain < graph.header.chains; chain += 1) {
                    var first = graph.chainAt[chain], last = graph.chainAt[chain + 1], along = 0;
                    for (i = first; i < last; i += 1) { along += length[i]; }
                    for (i = first; i < last; i += 1) { whole[i] = along; }
                }

                for (i = 0; i < edges; i += 1) {
                    var source = graph.header.sources[graph.sources[i]];
                    if (source.flatM === undefined) { cost[i] = length[i] * source.factor; }
                    // A crossing costs the header's flat figure rather than its
                    // length: taking a ferry is the same decision whether it is
                    // 2 km or 20, so weighting it by distance means nothing and
                    // would send a route across a fjord to save two hundred
                    // metres.
                    //
                    // **And the flat figure is the whole crossing's, not each
                    // piece's.** A crossing is a chain, and noding cuts it
                    // wherever something meets it: 15 of the 21 ferry chains
                    // here are in several pieces and the longest is in seven.
                    // Charging the flat cost per edge priced that one at 35 km
                    // of walking instead of 5, and a page that does so refuses
                    // crossings the build priced as affordable — the route the
                    // reader is shown would then disagree with the network the
                    // rest of the map was measured on. Split in proportion, as
                    // trails.routing.graph._cost splits it.
                    else { cost[i] = source.flatM * (whole[i] > 0 ? length[i] / whole[i] : 1); }
                }

                // Compressed adjacency: count what meets each node, prefix-sum,
                // then fill. An array of arrays over 116,967 nodes costs more in
                // allocation alone than every search a reader will ever run.
                var at = new Int32Array(nodes + 2);
                for (i = 0; i < edges; i += 1) { at[graph.fromNode[i] + 2] += 1; at[graph.toNode[i] + 2] += 1; }
                for (i = 2; i < at.length; i += 1) { at[i] += at[i - 1]; }
                var arc = new Int32Array(2 * edges);
                for (i = 0; i < edges; i += 1) {
                    arc[at[graph.fromNode[i] + 1]] = i; at[graph.fromNode[i] + 1] += 1;
                    arc[at[graph.toNode[i] + 1]] = i; at[graph.toNode[i] + 1] += 1;
                }
                // Filling leaves at[v + 1] at the end of node v's arcs, which is
                // where node v + 1's begin, so afterwards node v owns
                // arc[at[v] .. at[v + 1]).
                routing = {length: length, cost: cost, at: at, arc: arc,
                           best: new Float64Array(nodes), viaEdge: new Int32Array(nodes), viaNode: new Int32Array(nodes)};
                return routing;
            }

            // A binary heap over two parallel arrays. Entries are never removed
            // when a node is reached more cheaply — the stale one is popped and
            // recognised by its cost, which is the usual trade and the cheaper
            // one here.
            function Heap() { this.node = []; this.cost = []; }

            Heap.prototype.swap = function (a, b) {
                var node = this.node[a], cost = this.cost[a];
                this.node[a] = this.node[b]; this.cost[a] = this.cost[b];
                this.node[b] = node; this.cost[b] = cost;
            };

            Heap.prototype.push = function (node, cost) {
                var at = this.node.length;
                this.node.push(node); this.cost.push(cost);
                while (at > 0) {
                    var parent = (at - 1) >> 1;
                    if (this.cost[parent] <= this.cost[at]) { break; }
                    this.swap(parent, at); at = parent;
                }
            };

            // Sifting down ends because the position it moves to is always a
            // child of the one it was at, so it strictly increases and the loop
            // runs at most as deep as the heap. That is a property of the array
            // and not of the graph, which is why it carries no bound.
            Heap.prototype.pop = function () {
                var top = {node: this.node[0], cost: this.cost[0]}, last = this.node.length - 1;
                this.node[0] = this.node[last]; this.cost[0] = this.cost[last];
                this.node.pop(); this.cost.pop();
                var at = 0, size = this.node.length;
                while (true) {
                    var left = 2 * at + 1, right = left + 1, least = at;
                    if (left < size && this.cost[left] < this.cost[least]) { least = left; }
                    if (right < size && this.cost[right] < this.cost[least]) { least = right; }
                    if (least === at) { break; }
                    this.swap(least, at); at = least;
                }
                return top;
            };

            // Dijkstra over the weighted graph, once per new leg. Nothing but
            // the source factors weighs an edge: elevation-aware routing is a
            // decision nobody has taken, and the per-edge ascent it would need
            // is deliberately not in the payload.
            function route(graph, from, to) {
                var work = router(graph);
                var best = work.best, viaEdge = work.viaEdge, viaNode = work.viaNode;
                if (from === to) { return {edges: [], reversed: [], cost: 0}; }
                best.fill(Infinity); viaEdge.fill(-1); viaNode.fill(-1);
                best[from] = 0;

                // Every loop over this graph is bounded and throws when it
                // reaches the bound. A settled node is never settled twice and
                // every stale entry was pushed by a relaxation, so the pops
                // cannot exceed one per node plus one per arc; anything past
                // that is a defect, and a defect that runs for ever in a page
                // is indistinguishable from a page that has hung.
                var heap = new Heap();
                var pops = 0, mostPops = graph.header.nodes + 2 * graph.header.edges + 1;
                heap.push(from, 0);
                while (heap.node.length) {
                    pops += 1;
                    if (pops > mostPops) { throw new Error('the search took more than ' + mostPops + ' steps'); }
                    var taken = heap.pop();
                    if (taken.cost > best[taken.node]) { continue; }
                    if (taken.node === to) { break; }
                    for (var a = work.at[taken.node]; a < work.at[taken.node + 1]; a += 1) {
                        var edge = work.arc[a];
                        var other = graph.fromNode[edge] === taken.node ? graph.toNode[edge] : graph.fromNode[edge];
                        var reached = taken.cost + work.cost[edge];
                        if (reached < best[other]) {
                            best[other] = reached; viaEdge[other] = edge; viaNode[other] = taken.node;
                            heap.push(other, reached);
                        }
                    }
                }
                if (!isFinite(best[to])) { return null; }

                // Walking the path back out. **Bounded, and the sentinel is
                // tested for rather than indexed with**: a typed array answers
                // a negative index with undefined rather than raising, so an
                // unset predecessor would put undefined into the geometry and
                // carry on, and a walk that never reached its start would
                // append for ever. The Python sibling of this loop, written
                // without either guard, took 42 GB and the kernel killed it.
                var edges = [], reversed = [], walk = to, steps = 0;
                while (walk !== from) {
                    steps += 1;
                    if (steps > graph.header.edges) { throw new Error('the way back is longer than the graph'); }
                    var used = viaEdge[walk], before = viaNode[walk];
                    if (used < 0 || before < 0) { throw new Error('node ' + walk + ' was reached by nothing'); }
                    edges.push(used);
                    // An edge's geometry and its heights run from its own
                    // from-node to its own to-node, and the walk can arrive at
                    // it from either end. Read off the predecessor rather than
                    // off the edge's own ends, which say nothing about
                    // direction on the fourteen edges here that begin and end
                    // at the same node.
                    reversed.push(graph.fromNode[used] !== before);
                    walk = before;
                }
                edges.reverse(); reversed.reverse();
                return {edges: edges, reversed: reversed, cost: best[to]};
            }

            // ---- what a route's metres are made of ----------------------------
            // Summed per edge while the edges are still in hand. A part keeps
            // its geometry and its heights and nothing downstream can get back
            // to which edge a metre came from, so anything to be reported by
            // length has to be counted here.
            // The three buckets an edge's own sources answer with, and then the
            // two that are not answers at all: ground on a connector nobody drew
            // and so never asked about, and ground no source records a path
            // along. Kept apart, because a bucket that quietly absorbed one of
            // the others would be a claim nothing supports.
            var MARKING = ['marked', 'unmarked', 'unknown'];
            // And the two that are not answers at all, now three: ground on a
            // connector nobody drew, ground kept exactly as some file recorded
            // it, and ground no source records a path along. `recorded` is
            // phase 8's, and it is its own bucket for the reason `undrawn` is —
            // no register was asked about it, so folding it into `unmarked`
            // would turn a question nobody put into an answer.
            var TALLIED = MARKING.concat(['undrawn', 'recorded', 'unrecorded']);

            // Two things counted by name rather than into a fixed bucket: which
            // dataset drew each metre, and which protected areas the metres lie
            // in. Both are keyed without a prototype, so a register that names
            // an area "constructor" answers about that area rather than about
            // Object's own member.
            function blankTally() {
                var out = {sources: Object.create(null), protected: Object.create(null)};
                TALLIED.forEach(function (field) { out[field] = 0; });
                return out;
            }

            function addTally(into, from) {
                if (!from) { return; }
                ['sources', 'protected'].forEach(function (kind) {
                    Object.keys(from[kind]).forEach(function (name) {
                        into[kind][name] = (into[kind][name] || 0) + from[kind][name];
                    });
                });
                TALLIED.forEach(function (field) { into[field] += from[field]; });
            }

            // What protects the ground under one edge, added to a tally. **The
            // payload carries a share and this multiplies it by the length this
            // page measured**, so a route can never state more ground inside an
            // area than it walked altogether: Python measured those metres in
            // the projection the graph is built in, and 0.03 % of a long route
            // is enough for a subtotal to overtake its own total.
            function addProtected(out, graph, edge, metres) {
                var areas = graph.header.protected;
                for (var p = graph.protectedAt[edge]; p < graph.protectedAt[edge + 1]; p += 1) {
                    var area = areas[graph.protectedArea[p]];
                    if (!area) { throw new Error('edge ' + edge + ' lies in an area the page has no entry for'); }
                    out.protected[area.id] = (out.protected[area.id] || 0) + graph.protectedShare[p] * metres;
                }
            }

            // Which dataset drew each edge, whether anything says it is
            // waymarked, and whether any source records a path along it. All
            // three are on the payload per edge since it was first put in the
            // page, put there for exactly this.
            function tallyOf(graph, list) {
                var work = router(graph), out = blankTally();
                for (var i = 0; i < list.length; i += 1) {
                    var edge = list[i], source = graph.header.sources[graph.sources[edge]];
                    var metres = work.length[edge];
                    // Before the two lines below take a connector and a crossing
                    // out, because the three questions have different answers
                    // for them. A connector was never drawn, so no register says
                    // whether it is waymarked — but a walker covers its ground,
                    // and that ground lies inside a boundary or outside it. A
                    // crossing is the other way round: there is no walking
                    // distance under a ferry, so it is asked neither.
                    if (source.kind !== CROSSING) { addProtected(out, graph, edge, metres); }
                    // An inferred connector is not a dataset — nobody drew it,
                    // which is what a connector is — so it names no source and
                    // answers nothing about marking. Its ground is walked and
                    // counted, apart, under its own name.
                    if (source.kind === CONNECTOR) { out.undrawn += metres; continue; }
                    out.sources[source.name] = (out.sources[source.name] || 0) + metres;
                    // A crossing is not walking and no register marks water, so
                    // it is credited for its metres and counted in none of the
                    // buckets. Its length is reported apart, as a crossing.
                    if (source.kind === CROSSING) { continue; }
                    // header.waymarked[0] is null and means the edge was never
                    // asked. That is not 'unknown', which means it was asked and
                    // no source answered, and the two must not be added together.
                    // Every edge left here is walked ground the build asked
                    // about, so it has an answer. One that did not would be
                    // reported as ground on a connector *and* credited to a
                    // named dataset — two contradictory claims about one edge —
                    // so it is a defect rather than a fourth bucket.
                    var state = graph.header.waymarked[graph.waymarked[edge]];
                    if (state === null || state === undefined) {
                        throw new Error('edge ' + edge + ' is walked ground on ' + source.name + ' that was never asked about');
                    }
                    if (MARKING.indexOf(state) < 0) {
                        throw new Error('the payload names a marking state this page has no bucket for: ' + state);
                    }
                    out[state] += metres;
                    // Recorded, never fact: the sources over-record, so their
                    // silence is evidence and their lines are not.
                    if (graph.noPathRecorded[edge]) { out.unrecorded += metres; }
                }
                return out;
            }

            // A leg drawn straight is unmarked by construction rather than
            // unknown — nobody marks a line you drew across open ground — and it
            // asserts nothing about whether a path is recorded there: that rule
            // is a spatial test against every source's lines, which the page
            // cannot run. Its length is reported as drawn straight instead.
            //
            // **What protects it, it can answer**, and this is the one figure
            // on a straight leg that is measured rather than asserted. The
            // boundaries are in the page and the leg has a height sample every
            // few metres, so each sample says what it is standing in and a
            // sample's own stretch runs half way to each of its neighbours —
            // the same halfway rule the shoreline split above is decided by, and
            // there is no second rule to disagree with it.
            function straightTally(graph, laid, standing, first, last, began, ended) {
                var out = blankTally();
                out.unmarked = ended - began;
                spreadProtected(out, graph, standing, laid.along, first, last, began, ended);
                return out;
            }


            // ---- the index over the edge geometry ---------------------------------
            // **The first work of this phase, and it is not the matcher.** The
            // page could already find the nearest node — a linear scan over
            // 116,967 of them, 0.135 ms — and over the *edge* geometry it had
            // nothing whatever. One pass over the 948,465 vertices costs 2 ms,
            // so a recording matched a point at a time is 2.9 s of frozen main
            // thread at the corpus median and 10 s at its largest, before a
            // single overlap test. Written the other way round the matcher
            // works, on a map that has stopped answering, and the cause is
            // looked for in the matcher.
            //
            // A uniform grid in scaled degrees, laid out the way the adjacency
            // is: count per cell, prefix-sum, fill. One entry per *segment* per
            // cell its bounding box touches, rather than one per edge: 21 of
            // this network's chains are ferries and the longest runs kilometres
            // end to end, and an edge indexed by its own box would be in every
            // cell between them.
            //
            // Measured in the built page over the network's 714,107 segments:
            // **29 ms to build**, 799,863 entries, 8.4 MB, and **0.7
            // microseconds a lookup** looking at 159 segments. Against the 2 ms
            // pass that is some 2,800 times cheaper, and it is what makes a
            // 5,147-point recording something matched between two frames.
            //
            // Built once, on the first thing that asks — a reader who never
            // loads a file never pays for it.
            var gridded = null;

            function edgeIndex(graph) {
                if (gridded) { return gridded; }
                var began = performance.now();
                var co = graph.coordinates, vertexAt = graph.vertexAt, edges = graph.header.edges, i, v, r, c;
                var minLon = Infinity, minLat = Infinity, maxLon = -Infinity, maxLat = -Infinity;
                for (i = 0; i < co.length; i += 2) {
                    if (co[i] < minLon) { minLon = co[i]; }
                    if (co[i] > maxLon) { maxLon = co[i]; }
                    if (co[i + 1] < minLat) { minLat = co[i + 1]; }
                    if (co[i + 1] > maxLat) { maxLat = co[i + 1]; }
                }
                // One cosine for the whole grid, taken at its middle. The zone
                // is 80 km of latitude and the cosine moves 1.4 % across it,
                // which is a metre in seventy on a cell edge and nothing at all
                // against a tolerance of twenty-five metres.
                var lonScale = Math.cos((minLat + maxLat) / 2 * Math.PI / 180);
                var dLat = PLAN.indexCellM / 111320, dLon = dLat / lonScale;
                var cols = Math.floor((maxLon - minLon) / dLon) + 1;
                var rows = Math.floor((maxLat - minLat) / dLat) + 1;
                var at = new Int32Array(cols * rows + 1), entries = 0;

                // Both passes walk the same segments in the same order and have
                // to agree exactly on how many cells each one touches, or the
                // fill writes past a cell's own run and the index is quietly
                // wrong wherever two cells meet. So the box is worked out in
                // one place and each pass reads it out of the same four slots
                // rather than deriving it again.
                var box = new Int32Array(4);

                function boxOf(vertex) {
                    var ax = co[2 * vertex], ay = co[2 * vertex + 1];
                    var bx = co[2 * vertex + 2], by = co[2 * vertex + 3];
                    box[0] = Math.floor(((ax < bx ? ax : bx) - minLon) / dLon);
                    box[1] = Math.floor(((ax > bx ? ax : bx) - minLon) / dLon);
                    box[2] = Math.floor(((ay < by ? ay : by) - minLat) / dLat);
                    box[3] = Math.floor(((ay > by ? ay : by) - minLat) / dLat);
                }

                for (i = 0; i < edges; i += 1) {
                    for (v = vertexAt[i]; v + 1 < vertexAt[i + 1]; v += 1) {
                        boxOf(v);
                        for (r = box[2]; r <= box[3]; r += 1) {
                            for (c = box[0]; c <= box[1]; c += 1) { at[r * cols + c + 1] += 1; entries += 1; }
                        }
                    }
                }
                for (i = 1; i < at.length; i += 1) { at[i] += at[i - 1]; }
                var cursor = new Int32Array(cols * rows);
                var item = new Int32Array(entries), vert = new Int32Array(entries);
                for (i = 0; i < edges; i += 1) {
                    for (v = vertexAt[i]; v + 1 < vertexAt[i + 1]; v += 1) {
                        boxOf(v);
                        for (r = box[2]; r <= box[3]; r += 1) {
                            for (c = box[0]; c <= box[1]; c += 1) {
                                var cell = r * cols + c, put = at[cell] + cursor[cell];
                                cursor[cell] += 1;
                                item[put] = i; vert[put] = v;
                            }
                        }
                    }
                }
                // Filling leaves cursor[cell] at that cell's own count, so
                // at[cell] + cursor[cell] is where the next cell begins — the
                // invariant the node adjacency above is filled under too.
                gridded = {at: at, item: item, vert: vert, cols: cols, rows: rows,
                           dLon: dLon, dLat: dLat, minLon: minLon, minLat: minLat, lonScale: lonScale,
                           entries: entries, cells: cols * rows, buildMs: performance.now() - began,
                           bytes: (at.length + item.length + vert.length) * 4};
                return gridded;
            }

            // The nearest edge to a position, or nothing within the tolerance.
            //
            // **The heading is tested here, and it is the cheap half of what
            // keeps a recording off the wrong line.** At a junction the first
            // metres of a side path lie well inside any tolerance of the path
            // being walked, and a test asking only how far away something is
            // takes it: that is what put 23 % of `attach_nearest`'s matches on
            // a road they followed for under half its length. Undirected,
            // because a recording may walk an edge either way round — what is
            // compared is the line's direction and not its arrow. Where the
            // recording has no heading at all, which consumer GPS produces
            // whenever somebody stands still, every candidate passes it and the
            // distance decides.
            function nearestEdge(graph, index, lon, lat, hx, hy) {
                var co = graph.coordinates, lonScale = index.lonScale;
                var reach = PLAN.matchToleranceM / 111320;
                var c0 = Math.floor((lon - reach / lonScale - index.minLon) / index.dLon);
                var c1 = Math.floor((lon + reach / lonScale - index.minLon) / index.dLon);
                var r0 = Math.floor((lat - reach - index.minLat) / index.dLat);
                var r1 = Math.floor((lat + reach - index.minLat) / index.dLat);
                if (c0 < 0) { c0 = 0; }
                if (r0 < 0) { r0 = 0; }
                if (c1 > index.cols - 1) { c1 = index.cols - 1; }
                if (r1 > index.rows - 1) { r1 = index.rows - 1; }
                var turning = Math.cos(PLAN.matchMaxTurnDeg * Math.PI / 180);
                var heading = Math.sqrt(hx * hx + hy * hy);
                var closest = reach * reach, best = -1;
                for (var r = r0; r <= r1; r += 1) {
                    for (var c = c0; c <= c1; c += 1) {
                        var cell = r * index.cols + c;
                        for (var s = index.at[cell]; s < index.at[cell + 1]; s += 1) {
                            var v = index.vert[s];
                            var ax = co[2 * v], ay = co[2 * v + 1];
                            var ex = (co[2 * v + 2] - ax) * lonScale, ey = co[2 * v + 3] - ay;
                            var span = ex * ex + ey * ey;
                            if (heading > 0 && span > 0 &&
                                Math.abs(hx * ex + hy * ey) < turning * heading * Math.sqrt(span)) { continue; }
                            var px = (lon - ax) * lonScale, py = lat - ay;
                            var t = span > 0 ? (px * ex + py * ey) / span : 0;
                            t = t < 0 ? 0 : (t > 1 ? 1 : t);
                            var qx = px - t * ex, qy = py - t * ey;
                            var away = qx * qx + qy * qy;
                            if (away < closest) { closest = away; best = index.item[s]; }
                        }
                    }
                }
                return best < 0 ? null : {edge: best, m: Math.sqrt(closest) * 111320};
            }

            // How far a position lies from a run of coordinates, in metres. It
            // stops as soon as it is inside the tolerance: the overlap test asks
            // it once per recorded point against a laid path, and all it wants
            // to know is whether that point is near the path at all.
            function awayFromRun(lon, lat, xs, ys, lonScale, withinM) {
                var reach = withinM / 111320, inside = reach * reach, closest = Infinity;
                for (var i = 0; i + 1 < xs.length; i += 1) {
                    var ax = xs[i], ay = ys[i];
                    var ex = (xs[i + 1] - ax) * lonScale, ey = ys[i + 1] - ay;
                    var px = (lon - ax) * lonScale, py = lat - ay;
                    var span = ex * ex + ey * ey;
                    var t = span > 0 ? (px * ex + py * ey) / span : 0;
                    t = t < 0 ? 0 : (t > 1 ? 1 : t);
                    var qx = px - t * ex, qy = py - t * ey, away = qx * qx + qy * qy;
                    if (away < closest) { closest = away; }
                    if (closest <= inside) { return Math.sqrt(closest) * 111320; }
                }
                return Math.sqrt(closest) * 111320;
            }

            // ---- the recording, and the parts cut out of it ------------------------
            // The one recording the page is working from, or nothing. Loading a
            // second replaces the first, and every waypoint that came out of the
            // first names it by id — so a waypoint left over from a file that is
            // no longer loaded is recognised rather than read against the wrong
            // coordinates.
            var loaded = null;

            // A file that has been read and not yet taken, and null the rest of
            // the time — which is how everything else knows whether a question
            // is on the screen. **It is deliberately not `loaded`**: nothing
            // anchored to a recording may see a file the reader has not
            // accepted, or an edit made while the question stands would look its
            // points up in the wrong track.
            var pendingFile = null;

            // Set when a file is taken and cleared by the fit itself, so the map
            // is moved once per load and not once per refresh.
            var fitWanted = false;

            // What the reader calls this tour, or empty where they have called
            // it nothing. It travels in <metadata><name> and <trk><name>, which
            // is where GPX puts a name, so it comes back out of a file this map
            // wrote without a field of its own.
            var tourName = '';
            var loadedCount = 0;

            // A waypoint anchored to a recorded point. **It keeps the
            // recording's own position and does not snap to the network**: the
            // mode that takes a track as it is has to leave it where it was
            // recorded, and a waypoint that jumped to a node 100 m away would
            // drag the first and last hundred metres of the track with it.
            function anchored(graph, at) {
                // **And it carries a node where the recording reached one**,
                // which is not the same as snapping to it. Its position stays
                // the recording's, because a mode that takes a track as it is
                // has to leave it where it was recorded; the node is what lets
                // the *other* legs beside it route. Without it a leg joining an
                // anchored waypoint to an ordinary one falls past the routing
                // test — which wants a node at both ends — and is drawn straight
                // over the terrain: extending a loaded track by clicking would
                // draw a line rather than follow a path, and a mixed route
                // reloaded would come back with every leg beside a recorded one
                // turned into a straight line.
                //
                // Within the match tolerance rather than `snapM`. A routed leg
                // is laid from the node, so whatever the two are apart is a step
                // in the track at that waypoint, and 25 m is the same seam the
                // matcher already leaves where a recorded stretch meets a
                // routed one. A hundred and fifty would be a visible jump.
                var node = graph ? graph.nearestNode(loaded.lat[at], loaded.lon[at], PLAN.matchToleranceM) : -1;
                return {lat: loaded.lat[at], lon: loaded.lon[at], node: node, track: loaded.id, at: at};
            }

            // Which protected areas a run of ground lies in, spread over it by
            // the halfway rule: a point's own stretch runs half way to each of
            // its neighbours. **One rule, in one place**, called by the leg
            // drawn straight and by the stretch kept as recorded — two spellings
            // of a halfway rule would eventually disagree about a boundary and
            // both would look right.
            function spreadProtected(out, graph, standing, along, first, last, began, ended) {
                for (var s = first; s < last; s += 1) {
                    var here = standing[s];
                    if (!here || !here.length) { continue; }
                    var low = s === first ? began : (along[s - 1] + along[s]) / 2;
                    var high = s === last - 1 ? ended : (along[s] + along[s + 1]) / 2;
                    for (var a = 0; a < here.length; a += 1) {
                        var id = graph.header.protected[here[a]].id;
                        out.protected[id] = (out.protected[id] || 0) + (high - low);
                    }
                }
            }

            // One stretch of the recording, kept as it was recorded: the fifth
            // kind, and the one this phase adds.
            //
            // **Its metres go in a bucket of their own and in none of the four.**
            // No register was asked about this ground, which rules out marked,
            // unmarked and unknown; it is not a connector, which rules out
            // undrawn. It is the same shape of answer as a connector's — never
            // asked, reported under its own name — and folding it into unmarked
            // would turn a question nobody put into an answer.
            //
            // What protects it, it can say, and by the same halfway rule as a
            // leg drawn straight: the boundaries are in the page and the
            // recording has a point every few metres.
            //
            // ``firstLon``/``firstLat`` and ``lastLon``/``lastLat`` move the two
            // ends onto whatever they join, which is a node where a matched
            // stretch begins or ends. The displacement is bounded by the match
            // tolerance and it is what keeps the route one continuous line
            // instead of a run of stretches with 20 m holes between them.
            //
            // ``kind`` is what the span is, where something knows: a restored
            // plan's own leg list says whether a stretch was recorded or drawn
            // straight, and the two are different ground. Left out it is a
            // recording, which is what every other caller has.
            function trackPart(graph, first, last, firstLon, firstLat, lastLon, lastLat, kind) {
                // **A typed array answers an index outside it with undefined
                // rather than raising**, so an anchor left over from a file that
                // is no longer loaded would put NaN coordinates into the route
                // and draw nothing, silently. The Python sibling of this rule is
                // that a numpy array is never indexed with a sentinel; here the
                // sentinel would be an index into the wrong recording.
                if (first < 0 || last < 0 || first >= loaded.n || last >= loaded.n) {
                    throw new Error('a waypoint points at ' + first + '..' + last +
                                    ' of a recording that has ' + loaded.n + ' points');
                }
                var step = last >= first ? 1 : -1, count = Math.abs(last - first) + 1;
                var lon = new Array(count), lat = new Array(count), height = new Array(count);
                var along = new Array(count), i, at;
                for (i = 0, at = first; i < count; i += 1, at += step) {
                    lon[i] = loaded.lon[at]; lat[i] = loaded.lat[at]; height[i] = loaded.ele[at];
                }
                if (firstLon !== undefined) { lon[0] = firstLon; lat[0] = firstLat; }
                if (lastLon !== undefined) { lon[count - 1] = lastLon; lat[count - 1] = lastLat; }
                var run = 0;
                along[0] = 0;
                for (i = 1; i < count; i += 1) {
                    run += panel().metresBetween(lon[i - 1], lat[i - 1], lon[i], lat[i]);
                    along[i] = run;
                }
                var tally = blankTally();
                // **A stretch the reader drew across open ground is unmarked by
                // construction and not recorded**: nobody marks a line you drew,
                // and nobody recorded it either. The decisions document settles
                // that distinction, and restoring a plan is the first thing that
                // ever had to apply it to a span of somebody's file.
                if (kind === 'land') { tally.unmarked = run; } else { tally.recorded = run; }
                var standing = new Array(count);
                for (i = 0; i < count; i += 1) { standing[i] = graph.areasAt(lon[i], lat[i]); }
                spreadProtected(tally, graph, standing, along, 0, count, 0, run);
                var read = false;
                for (i = 0; i < count; i += 1) { if (!isNaN(height[i])) { read = true; break; } }
                // The vertices and the samples are one series here, which they
                // are for no other kind: a recording's points are both what the
                // file writes and what the profile is drawn from, and there is
                // nothing to sample between them that was ever measured.
                return {kind: kind || PLAN.gpx.trackKind, lon: lon, lat: lat, along: along, length: run,
                        height: height, distance: along, read: read, tally: tally,
                        index: {from: first, step: step, count: count}};
            }

            // ---- matching a recording onto the network ----------------------------
            // **Anchor, then route, then test the result against the recording.**
            // Every point of the recording could be assigned an edge instead,
            // and the runs of like assignment chained into paths — that was the
            // first design and it spends its life on cases the graph answers for
            // free: an edge here averages 25 m, a recording wobbles between two
            // of them at every junction, and reconstructing which way round each
            // one is walked is arithmetic with four ways to be wrong. Routing
            // between two anchors cannot produce a path that is not a path, and
            // the 14 edges here whose two ends are the same node are the
            // router's problem rather than this function's.
            //
            // What it costs: one Dijkstra per anchor, and a search between two
            // nodes a few hundred metres apart settles a handful of nodes. The
            // three arrays it clears are the floor — 116,967 each — which is
            // why the anchors are spaced rather than taken at every point.
            //
            // **And the test is `attach_nearest`'s rule, with the recording as
            // the line and the routed path as its counterpart**: what share of
            // the recorded stretch actually lies along the path offered to
            // replace it. Proximity alone is a weak test for lines, and this is
            // the phase where that lesson is either applied or paid for.
            function anchorsOf(graph, index, first, last) {
                var out = [], since = -Infinity;
                for (var i = first; i <= last; i += 1) {
                    if (i > first && i < last && loaded.along[i] - since < PLAN.matchAnchorM) { continue; }
                    since = loaded.along[i];
                    var before = i > first ? i - 1 : i, after = i < last ? i + 1 : i;
                    var hx = (loaded.lon[after] - loaded.lon[before]) * index.lonScale;
                    var hy = loaded.lat[after] - loaded.lat[before];
                    var found = nearestEdge(graph, index, loaded.lon[i], loaded.lat[i], hx, hy);
                    if (!found) { continue; }
                    // The nearer of the matched edge's own two ends, **and
                    // only if the recording actually reached it**.
                    //
                    // That second half is not a refinement, it is what keeps
                    // the matcher from stating a walk nobody took. Noding cuts
                    // a line only where something meets it, so a recording out
                    // in the terrain that nothing crosses is *one edge*: the
                    // median edge here is 6.9 m and the 90th percentile 49 m,
                    // but **1,142 of the 234,358 are over 500 m and 79 over
                    // 2 km, the longest 18.5 km**. Anchoring to the far end of
                    // one of those and routing to it hands back the whole edge
                    // — measured on trip 1113935, an out-and-back that turns
                    // round 332 m short of the end of its own 4,729 m edge, and
                    // the route came back 332 m longer than the walk.
                    //
                    // A node the recording passed within the tolerance of is a
                    // place it demonstrably stood, so a routed stretch between
                    // two of them is ground that was walked. Where there is no
                    // such node the stretch is kept as it was recorded, which
                    // is the honest answer while a part is a whole edge: what
                    // it would take to say more is in the phase's write-up.
                    var a = graph.fromNode[found.edge], b = graph.toNode[found.edge];
                    var toA = panel().metresBetween(loaded.lon[i], loaded.lat[i], graph.nodeLon[a], graph.nodeLat[a]);
                    var toB = panel().metresBetween(loaded.lon[i], loaded.lat[i], graph.nodeLon[b], graph.nodeLat[b]);
                    if (toA > PLAN.matchToleranceM && toB > PLAN.matchToleranceM) { continue; }
                    var node = toA <= toB ? a : b;
                    // Never the node the last anchor already stands on. Two
                    // anchors at one node have nothing to route between, and the
                    // stretch between them would be dropped rather than tested —
                    // so the recording would keep ground the network carries
                    // perfectly well, for no reason a reader could see.
                    if (out.length && out[out.length - 1].node === node) { continue; }
                    out.push({at: i, node: node, away: found.m});
                }
                return out;
            }

            // What share of the recorded points between two anchors lies within
            // the tolerance of the path offered to replace them.
            function overlapWith(laid, first, last, lonScale) {
                var inside = 0, count = 0;
                for (var i = first; i <= last; i += 1) {
                    count += 1;
                    if (awayFromRun(loaded.lon[i], loaded.lat[i], laid.lon, laid.lat,
                                    lonScale, PLAN.matchToleranceM) <= PLAN.matchToleranceM) { inside += 1; }
                }
                return count ? inside / count : 0;
            }

            // The recording cut into stretches: the ones the network carries and
            // the ones it does not, in the order they are walked. Every stretch
            // between ``first`` and ``last`` is covered exactly once.
            function matchedSpans(graph, first, last) {
                var index = edgeIndex(graph);
                var anchors = anchorsOf(graph, index, first, last);
                var spans = [], at = first, k;
                for (k = 0; k + 1 < anchors.length; k += 1) {
                    var a = anchors[k], b = anchors[k + 1];
                    if (a.node === b.node || b.at <= a.at) { continue; }
                    var found = route(graph, a.node, b.node);
                    if (!found || !found.edges.length) { continue; }
                    var breaks = found.edges.map(function () { return false; });
                    var laid = panel().layEdges(graph, found.edges, found.reversed, breaks);
                    // **The overlap test's other half, and it is not optional.**
                    // Overlap asks what share of the *recording* lies along the
                    // path offered to replace it, which is `attach_nearest`'s
                    // rule and is one-directional: a path that runs along the
                    // whole recording and then goes somewhere else as well
                    // passes it. Measured before this line existed, the 42.44 km
                    // Rundtur came back as **48.2 km** — 5.7 km of ground the
                    // walker never covered, on a round trip whose own line
                    // crosses itself and where the router took the wrong branch
                    // at the crossing while still lying along the recording
                    // everywhere it was asked about.
                    //
                    // A route may not claim more ground than was walked. Both
                    // anchors lie within the tolerance of a recorded point, so
                    // the tolerance at each end is the whole of the slack there
                    // is: anything beyond it is a different way round.
                    var covered = loaded.along[b.at] - loaded.along[a.at];
                    if (laid.total > covered + 2 * PLAN.matchToleranceM) { continue; }
                    if (overlapWith(laid, a.at, b.at, index.lonScale) < PLAN.matchMinOverlap) { continue; }
                    if (at < a.at) { spans.push({routed: false, from: at, to: a.at}); }
                    // Two accepted stretches meeting at one anchor are one path
                    // and not two: the second begins at the node the first ended
                    // at, so their edge lists lay end to end with nothing
                    // between them.
                    var back = spans.length ? spans[spans.length - 1] : null;
                    if (back && back.routed && back.to === a.at) {
                        back.edges = back.edges.concat(found.edges);
                        back.reversed = back.reversed.concat(found.reversed);
                        back.to = b.at; back.length += laid.total;
                    } else {
                        spans.push({routed: true, from: a.at, to: b.at, node: a.node,
                                    edges: found.edges, reversed: found.reversed, length: laid.total});
                    }
                    at = b.at;
                }
                if (at < last) { spans.push({routed: false, from: at, to: last}); }
                if (!spans.length) { spans.push({routed: false, from: first, to: last}); }

                // **A floor under what counts as running along something.** A
                // matched stretch shorter than this is the junction case — a
                // recording crossing a path takes a few of its metres — and
                // below it *running along* a path and *touching* it cannot be
                // told apart. Reverted rather than dropped: the ground is still
                // walked, and what changes is only whose line says so.
                var kept = [];
                spans.forEach(function (span) {
                    var back = kept.length ? kept[kept.length - 1] : null;
                    var verbatim = !span.routed || span.length < PLAN.matchMinRunM;
                    if (verbatim && back && !back.routed) { back.to = span.to; return; }
                    kept.push(verbatim ? {routed: false, from: span.from, to: span.to} : span);
                });
                return kept;
            }

            // The stretches as parts of one leg: what the network carries laid
            // out of its own edges, and what it does not kept exactly as it was
            // recorded, with the two ends of every recorded stretch moved onto
            // the nodes it joins.
            function matchedParts(graph, first, last) {
                var spans = matchedSpans(graph, first, last), parts = [];
                spans.forEach(function (span, i) {
                    if (span.routed) {
                        parts.push.apply(parts, routedParts(graph, {edges: span.edges, reversed: span.reversed}));
                        return;
                    }
                    var before = i > 0 ? spans[i - 1] : null, after = i + 1 < spans.length ? spans[i + 1] : null;
                    var lead = before && before.routed ? endOf(parts) : null;
                    var trail = after && after.routed ? startOf(graph, after) : null;
                    parts.push(trackPart(graph, span.from, span.to,
                                         lead ? lead.lon : undefined, lead ? lead.lat : undefined,
                                         trail ? trail.lon : undefined, trail ? trail.lat : undefined));
                });
                return parts;
            }

            function endOf(parts) {
                for (var i = parts.length - 1; i >= 0; i -= 1) {
                    var part = parts[i];
                    if (part.lon && part.lon.length) {
                        return {lon: part.lon[part.lon.length - 1], lat: part.lat[part.lat.length - 1]};
                    }
                }
                return null;
            }

            function startOf(graph, span) {
                return {lon: graph.nodeLon[span.node], lat: graph.nodeLat[span.node]};
            }

            // ---- the four kinds ----------------------------------------------
            // A routed leg, cut at every change between walking and crossing, so
            // the ferry inside it is a crossing rather than 8 km of walking with
            // no ground under it.
            function routedParts(graph, found) {
                var parts = [], run = [], reversed = [], kind = null;

                function flush() {
                    if (!run.length) { return; }
                    var breaks = run.map(function () { return false; });
                    var laid = panel().layEdges(graph, run, reversed, breaks);
                    var tally = tallyOf(graph, run);
                    // `along` travels with the part because the file is written
                    // from the vertices and the profile from the samples, and
                    // the two are different series over the same ground.
                    parts.push(kind === CROSSING
                        ? {kind: CROSSING, lon: laid.lon, lat: laid.lat, along: laid.along, length: laid.total,
                           height: null, distance: null, read: false, tally: tally}
                        : {kind: 'routed', lon: laid.lon, lat: laid.lat, along: laid.along, length: laid.total,
                           height: laid.height, distance: laid.distance, read: laid.read, tally: tally});
                    run = []; reversed = [];
                }

                for (var i = 0; i < found.edges.length; i += 1) {
                    var here = graph.header.sources[graph.sources[found.edges[i]]].kind === CROSSING ? CROSSING : 'routed';
                    if (here !== kind) { flush(); kind = here; }
                    run.push(found.edges[i]); reversed.push(found.reversed[i]);
                }
                flush();
                return parts;
            }

            // ---- heights for a leg the network cannot carry -------------------
            // Sampled by the build's own rule: floor(length / step) + 1 samples,
            // never fewer than two, spread evenly between the two ends. Two
            // halves of one profile read under two rules answer differently, and
            // nothing about the answer looks wrong.
            // **Refused rather than quietly coarsened.** Sampling is fixed at
            // the build's step, so the only way to bound the work is to bound
            // the leg: at 5 m and fifty points a request, the width of this map
            // is some 180 requests to somebody else's service, from one misclick
            // out to sea. Coarsening instead would make the two halves of a
            // profile answer differently and nothing would look wrong, so the
            // leg says what it will not do.
            //
            // Asked here rather than inside the sampling, because a leg carried
            // through a drag without heights is refused for its length too — and
            // a ceiling that only applied where the samples are laid out would
            // let a drag draw across the whole map and refuse it on release.
            function refuseLong(length) {
                if (length > PLAN.maxStraightM) {
                    throw new Error((length / 1000).toFixed(1) + ' km is further than a leg may be drawn straight (' +
                                    (PLAN.maxStraightM / 1000).toFixed(1) + ' km)');
                }
            }

            function straightSamples(from, to) {
                var length = panel().metresBetween(from.lon, from.lat, to.lon, to.lat);
                refuseLong(length);
                var count = Math.max(2, Math.floor(length / PLAN.sampleStepM) + 1);
                var lon = [], lat = [], along = [];
                for (var i = 0; i < count; i += 1) {
                    var t = i / (count - 1);
                    lon.push(from.lon + t * (to.lon - from.lon));
                    lat.push(from.lat + t * (to.lat - from.lat));
                    along.push(t * length);
                }
                return {lon: lon, lat: lat, along: along, length: length};
            }

            // The same two rules the build reads an answer by, and they are two
            // rules rather than one. `datakilde` says whether the number is a
            // ground height at all: over water the service answers with a depth
            // from the depth contours — a metre offshore reads -276 m — and
            // outside its coverage with nothing. `terreng` says what the point
            // is *on*, and that is what tells a straight leg whether it is
            // walking or crossing. A lake answers with neither: a real height
            // from a lake model, which is not a terrain model, so it is walked
            // ground with nothing read along it.
            function reading(point) {
                var from = point.datakilde;
                var ground = typeof from === 'string' && from.toLowerCase().indexOf(PLAN.terrainModel) === 0;
                var height = point.z;
                return {
                    height: (ground && height !== null && height !== undefined) ? Number(height) : NaN,
                    sea: point.terreng === PLAN.seaTerrain
                };
            }

            function askOnce(points) {
                return fetch(PLAN.heightsUrl + '?punkter=' + encodeURIComponent(JSON.stringify(points)) +
                             '&koordsys=' + encodeURIComponent(PLAN.heightsCrs))
                    .then(function (response) {
                        if (!response.ok) { throw new Error('the height model answered ' + response.status); }
                        return response.json();
                    })
                    .then(function (body) {
                        var answered = body && body.punkter;
                        // The answer is read by position, so one that does not
                        // line up with the question would put each point's
                        // neighbour's height on it and raise nothing.
                        if (!answered || answered.length !== points.length) {
                            throw new Error('asked about ' + points.length + ' points and got ' +
                                            (answered ? answered.length : 'no list'));
                        }
                        return answered.map(reading);
                    });
            }

            // Retried the way the build retries: this endpoint is shared and a
            // busy server has been seen to answer moments later. After that the
            // leg says it has no heights rather than drawing flat ground.
            var ATTEMPTS = 3;

            function ask(points, attempt) {
                return askOnce(points).catch(function (failure) {
                    if (attempt >= ATTEMPTS) { throw failure; }
                    return new Promise(function (resolve) { setTimeout(resolve, 500 * attempt); })
                        .then(function () { return ask(points, attempt + 1); });
                });
            }

            // The build's concurrency, not a faster one: this is somebody else's
            // endpoint and restraint counts for more than speed.
            function inWaves(batches) {
                var out = new Array(batches.length), next = 0, stopped = false;

                function pull() {
                    // Once one batch has given up, the leg has no heights and
                    // nothing the others fetch will be used. Without this the
                    // reader is told the leg failed while the page carries on
                    // asking the service for the rest of it — the opposite of
                    // the restraint the concurrency is set for.
                    if (stopped || next >= batches.length) { return Promise.resolve(); }
                    var mine = next;
                    next += 1;
                    return ask(batches[mine], 1).then(function (answers) { out[mine] = answers; return pull(); },
                        function (failure) { stopped = true; throw failure; });
                }

                var running = [];
                for (var i = 0; i < Math.min(PLAN.heightsWorkers, batches.length); i += 1) { running.push(pull()); }
                return Promise.all(running).then(function () {
                    var flat = [];
                    out.forEach(function (part) { part.forEach(function (one) { flat.push(one); }); });
                    return flat;
                });
            }

            // Cached by the leg's two ends, so taking a point back and putting
            // it down in the same place does not ask the service twice.
            //
            // **Keyed on the pair and not on the order it was given in.** Moving
            // a waypoint one place past its neighbour turns exactly one leg
            // round — it is what a reorder always does — and a cache that
            // treated A to B and B to A as different ground would fetch a leg
            // the page is already holding. The samples run one way and are read
            // back the other by ``mirrored``, so nothing downstream knows or
            // needs to.
            var asked = Object.create(null);
            var askedKeys = [];
            // And bounded, which it did not have to be while a leg could only be
            // added and taken back: a drag leaves one leg's samples behind every
            // time the pointer is let go, and a leg is up to twenty kilometres
            // of them. Oldest out first — the ends a reader is working between
            // are the ones they come back to.
            var ASKED_MOST = 64;

            function endKey(point) { return point.lon.toFixed(7) + ',' + point.lat.toFixed(7); }

            // Which way round the pair is asked for. Any consistent order does,
            // and this one is a comparison of the very strings the key is built
            // from, so the order and the key cannot come apart.
            function forwards(from, to) { return endKey(from) <= endKey(to); }

            // The same ground read from the other end: the coordinates reversed
            // and every distance measured from the far end instead. What comes
            // out is what the service would have answered had it been asked this
            // way round.
            function mirrored(answered) {
                var laid = answered.laid, count = laid.lon.length;
                var lon = [], lat = [], along = [], points = [];
                for (var i = count - 1; i >= 0; i -= 1) {
                    lon.push(laid.lon[i]); lat.push(laid.lat[i]);
                    along.push(laid.length - laid.along[i]);
                    points.push(answered.points[i]);
                }
                return {laid: {lon: lon, lat: lat, along: along, length: laid.length}, points: points};
            }

            function beginHeights(from, to) {
                var laid;
                // A leg refused for its length is a leg with no heights, which
                // the route already knows how to say. Thrown from here it would
                // escape the click instead.
                try {
                    laid = straightSamples(from, to);
                } catch (refused) {
                    return Promise.reject(refused);
                }
                var batches = [];
                for (var i = 0; i < laid.lon.length; i += PLAN.heightsBatch) {
                    var slice = [];
                    for (var k = i; k < Math.min(i + PLAN.heightsBatch, laid.lon.length); k += 1) {
                        // Asked in the page's own coordinates. The service takes
                        // longitude and latitude as readily as the metric grid
                        // the build uses — measured, not assumed — so nothing
                        // here reprojects anything.
                        slice.push([Number(laid.lon[k].toFixed(7)), Number(laid.lat[k].toFixed(7))]);
                    }
                    batches.push(slice);
                }
                return inWaves(batches).then(function (points) { return {laid: laid, points: points}; });
            }

            function remember(key, answering) {
                asked[key] = answering;
                askedKeys.push(key);
                while (askedKeys.length > ASKED_MOST) { delete asked[askedKeys.shift()]; }
                // A refusal must not be remembered as one for ever: the next
                // click on the same ground should ask again. Two handlers rather
                // than a catch, so that this one sees only the refusal.
                answering.then(null, function () { if (asked[key] === answering) { forget(key); } });
            }

            function forget(key) {
                delete asked[key];
                var at = askedKeys.indexOf(key);
                if (at >= 0) { askedKeys.splice(at, 1); }
            }

            // The heights for a leg drawn straight: out of the cache if this
            // ground is already in hand, and otherwise out of the service —
            // unless nothing may be asked, which is what a live drag says, and
            // then there are none.
            function heightsFor(from, to, mayAsk) {
                var forward = forwards(from, to);
                var a = forward ? from : to, b = forward ? to : from;
                var key = endKey(a) + '|' + endKey(b);
                var answering = asked[key];
                if (!answering) {
                    if (!mayAsk) { return null; }
                    answering = beginHeights(a, b);
                    remember(key, answering);
                }
                return forward ? answering : answering.then(mirrored);
            }

            // The samples classify the ground and the split falls out of them:
            // where two neighbours disagree the shoreline lies between, and half
            // way between is as near as sampling every few metres can put it. No
            // coastline is consulted and none is needed.
            function straightParts(graph, from, to, answered) {
                var laid = answered.laid, points = answered.points, count = points.length;
                // What each sample is standing in, worked out once: a leg is
                // classified here and its shoreline split is read off the same
                // list, and asking the polygons twice for one position is the
                // shape a disagreement takes.
                var standing = new Array(count);
                for (var s = 0; s < count; s += 1) { standing[s] = graph.areasAt(laid.lon[s], laid.lat[s]); }
                // Where the samples change their mind about what is under them.
                // Named for what it is: in this file `edges` means edges of the
                // graph, and these are the ends of the runs.
                var changes = [0];
                for (var i = 1; i < count; i += 1) {
                    if (points[i].sea !== points[i - 1].sea) { changes.push(i); }
                }
                changes.push(count);

                function positionAt(distance) {
                    var t = laid.length > 0 ? distance / laid.length : 0;
                    return {lon: from.lon + t * (to.lon - from.lon), lat: from.lat + t * (to.lat - from.lat)};
                }

                var parts = [];
                for (var run = 0; run + 1 < changes.length; run += 1) {
                    var first = changes[run], last = changes[run + 1];
                    var began = run === 0 ? 0 : (laid.along[first - 1] + laid.along[first]) / 2;
                    var ended = last === count ? laid.length : (laid.along[last - 1] + laid.along[last]) / 2;
                    var head = positionAt(began), tail = positionAt(ended);
                    if (points[first].sea) {
                        parts.push({kind: 'water', lon: [head.lon, tail.lon], lat: [head.lat, tail.lat],
                                    along: [0, ended - began], length: ended - began,
                                    height: null, distance: null, read: false, tally: blankTally()});
                        continue;
                    }
                    var height = [], distance = [], read = false;
                    for (var s = first; s < last; s += 1) {
                        height.push(points[s].height);
                        distance.push(laid.along[s] - began);
                        if (!isNaN(points[s].height)) { read = true; }
                    }
                    // Two vertices and no more: the reader drew a straight line,
                    // so the two ends are every corner it has. The file's 5 m
                    // fill lays its points along it from these.
                    parts.push({kind: 'land', lon: [head.lon, tail.lon], lat: [head.lat, tail.lat],
                                along: [0, ended - began], length: ended - began,
                                height: height, distance: distance, read: read,
                                tally: straightTally(graph, laid, standing, first, last, began, ended)});
                }
                return parts;
            }

            // A route that may only follow recorded ways is not a plan for this
            // park: 19.9 km of UT.no's own routes run where no source records
            // anything. So where the network cannot carry a leg it is drawn
            // straight rather than refused.
            // **A leg the network cannot carry is not fetched while a drag is
            // live.** Its heights are seconds of somebody else's service, the
            // ground under a waypoint being dragged is new at every position,
            // and the endpoint cache answers only for ends already visited — so
            // asking at the rate a pointer moves is the uncapped request stream
            // this phase exists not to build. It is carried at its own straight
            // length with nothing read along it instead: the walked distance
            // under the reader's hand stays right, the route says the leg is
            // still being worked out, and the one request goes out when the
            // pointer is let go. Ground already in hand is used either way,
            // which is what makes dragging a point back where it came from cost
            // nothing at all.
            function resolve(graph, from, to, mayAsk) {
                // **A leg the file described is laid out the way it described
                // it**, before anything else is tried. It has to come first for
                // the same reason the recorded test does and one more: both ends
                // may well sit on a node, so routing would quietly replace a
                // recorded stretch, and the seam this restores is *inside* the
                // leg where the recorded test cannot see it at all.
                if (from.restore) {
                    var laid = restoredParts(graph, from, to, from.restore);
                    if (laid) { return Promise.resolve(laid); }
                }
                // **A leg between two points of the loaded recording is the
                // recording's**, whichever of the two modes put them there.
                // Tested before the network is, because both of its ends may
                // well sit on a node — a recording of a path this map already
                // draws is on the network at every point — and routing between
                // them would silently replace what was recorded with whatever
                // the router prefers.
                if (loaded && from.track === loaded.id && to.track === loaded.id && from.at !== to.at) {
                    return Promise.resolve(recordedParts(graph, from, to));
                }
                if (from.node >= 0 && to.node >= 0) {
                    var found = route(graph, from.node, to.node);
                    if (found) { return Promise.resolve(routedParts(graph, found)); }
                }
                var answering = heightsFor(from, to, mayAsk);
                if (!answering) { return Promise.resolve(waitingParts(from, to)); }
                return answering.then(function (answered) { return straightParts(graph, from, to, answered); });
            }

            // What such a leg is in the meantime: its own straight line, its own
            // length, and no heights. **It counts as walked and as drawn
            // straight**, which is what keeps the distance honest under the
            // hand, and it counts as unsettled, which is what keeps the file
            // from being written out of it. What it does not carry is a
            // protected-area tally: that is read off the height samples at the
            // same halfway rule the shoreline split uses, and there are no
            // samples yet. Under-reporting it for as long as the panel says the
            // leg is still being worked out is the honest half of that; making
            // one up at a coarser spacing would be a second rule to disagree
            // with the first.
            function waitingParts(from, to) {
                var length = panel().metresBetween(from.lon, from.lat, to.lon, to.lat);
                refuseLong(length);
                var tally = blankTally();
                tally.unmarked = length;
                return [{kind: 'land', lon: [from.lon, to.lon], lat: [from.lat, to.lat],
                         along: [0, length], length: length, height: [NaN, NaN], distance: [0, length],
                         read: false, tally: tally, provisional: true}];
            }


            // ---- reading a GPX back ------------------------------------------------
            // **This is the only place in the project where a reader and a
            // writer of the same file sit in one phase.** Every name the reader
            // looks for arrives in PLAN.gpx out of the same Python constant the
            // writer's own name comes from, so the two cannot drift: a page
            // reading `origin` while writing `Origin` would take every route it
            // ever wrote for a foreign track and say nothing about it.
            //
            // Addressed by namespace and local name rather than by tag, because
            // a prefix is the writer's choice and not the format's: a file that
            // spells this map's namespace `t:` instead of `trails:` says exactly
            // the same thing, and getElementsByTagName would miss all of it. The
            // GPX elements are looked up under any namespace at all, since a
            // consumer device that leaves the default namespace off writes a
            // file every other reader still accepts.
            function ours(parent, name) {
                return parent ? parent.getElementsByTagNameNS(PLAN.gpx.namespace, name) : [];
            }

            function firstText(parent, name) {
                var found = parent ? parent.getElementsByTagNameNS('*', name) : [];
                for (var i = 0; i < found.length; i += 1) {
                    // Only a child of this element, never a grandchild: a <trk>
                    // holds a <name> of its own and so does every <wpt> before
                    // it, and a search that went deep would give the track the
                    // first waypoint's name.
                    if (found[i].parentNode === parent) { return found[i].textContent; }
                }
                return null;
            }

            // Everything one loaded file says about itself, read once. Nothing
            // here decides anything: what the three modes do with it is below,
            // and a reader that also chose would have to be read twice to find
            // out what a file became.
            function parseGpx(text) {
                var doc = new DOMParser().parseFromString(text, 'application/xml');
                if (doc.getElementsByTagName('parsererror').length) {
                    throw new Error('this file is not XML that a browser can read');
                }
                var root = doc.documentElement;
                if (!root || root.localName !== 'gpx') {
                    throw new Error('this file is not GPX: its outermost element is <' + (root ? root.nodeName : 'nothing') + '>');
                }

                var segments = root.getElementsByTagNameNS('*', 'trkseg');
                var lon = [], lat = [], ele = [], ends = [], along = [], run = 0, s, p;
                for (s = 0; s < segments.length; s += 1) {
                    var points = segments[s].getElementsByTagNameNS('*', 'trkpt');
                    for (p = 0; p < points.length; p += 1) {
                        var x = parseFloat(points[p].getAttribute('lon')), y = parseFloat(points[p].getAttribute('lat'));
                        if (!isFinite(x) || !isFinite(y)) { continue; }
                        if (lon.length && !ends[lon.length - 1]) {
                            run += panel().metresBetween(lon[lon.length - 1], lat[lat.length - 1], x, y);
                        }
                        var height = firstText(points[p], 'ele');
                        lon.push(x); lat.push(y); along.push(run);
                        // A point with no <ele> keeps its place and loses only
                        // its height, which is the same distinction the writer
                        // keeps: there is ground here and no reading of it.
                        ele.push(height === null || height === '' ? NaN : parseFloat(height));
                        ends.push(false);
                    }
                    if (lon.length) { ends[lon.length - 1] = true; }
                }
                var breaks = 0;
                for (s = 0; s + 1 < lon.length; s += 1) { if (ends[s]) { breaks += 1; } }
                if (lon.length < 2) {
                    throw new Error('this file has ' + lon.length + ' trackpoints, and a route needs two');
                }

                // The track's own extensions, which is where a file this map
                // wrote says what it is. A chain export says its chain id and
                // has no waypoints at all; a planned route says its kind and
                // carries the points somebody clicked.
                var tracks = root.getElementsByTagNameNS('*', 'trk');
                var extensions = tracks.length ? firstChildNamed(tracks[0], 'extensions') : null;
                var kind = textOf(ours(extensions, PLAN.gpx.kindField));
                var chainId = textOf(ours(extensions, PLAN.gpx.chainField));

                var legs = [], unknown = Object.create(null);
                // Without a prototype, like every other table this page keys on
                // somebody else's words: `known['constructor']` on an object
                // literal is a function and reads as a kind this page knows.
                var known = Object.create(null);
                known.routed = true; known.land = true; known.water = true;
                known[CROSSING] = true;
                known[PLAN.gpx.trackKind] = true;
                var lists = ours(extensions, PLAN.gpx.legs);
                if (lists.length) {
                    var each = lists[0].getElementsByTagNameNS(PLAN.gpx.namespace, PLAN.gpx.leg);
                    for (s = 0; s < each.length; s += 1) {
                        var parts = each[s].getElementsByTagNameNS(PLAN.gpx.namespace, PLAN.gpx.part), made = [];
                        for (p = 0; p < parts.length; p += 1) {
                            // A part with no kind at all is named as that
                            // rather than as a kind called 'null', which is what
                            // an absent attribute reads as once it is a key.
                            var said = parts[p].getAttribute(PLAN.gpx.partKind);
                            if (said === null) { said = 'no kind at all'; }
                            if (!known[said]) { unknown[said] = (unknown[said] || 0) + 1; }
                            made.push({kind: said, m: parseFloat(parts[p].getAttribute(PLAN.gpx.partLength))});
                        }
                        legs.push(made);
                    }
                }

                // **The generated markers are skipped here and nowhere else.**
                // 6B marks every one the map placed by itself — at a park
                // boundary, at a hut — and a reader that took them for stations
                // somebody chose would give the route points nobody put down and
                // then route through them. Skipped rather than counted and
                // dropped later: one place to get it wrong is enough.
                var carried = root.getElementsByTagNameNS('*', 'wpt'), waypoints = [];
                var generated = 0, strange = 0;
                for (p = 0; p < carried.length; p += 1) {
                    var block = firstChildNamed(carried[p], 'extensions');
                    var origin = textOf(ours(block, PLAN.gpx.origin));
                    // What says `set`, and what says nothing at all — a file
                    // from anywhere else has no origin on its waypoints, and
                    // every one of those is a station somebody chose. Anything
                    // else is skipped, which is the conservative way round: a
                    // value this page has never heard of is likelier a later
                    // writer's second kind of marker than a station, and taking
                    // it would put a point on the route that nobody placed.
                    //
                    // The two reasons for skipping are counted apart because
                    // they mean different things to a reader: a marker this map
                    // placed is expected and a word this page does not know is a
                    // file from a later build, and one of those is worth saying.
                    if (origin === PLAN.gpx.generated) { generated += 1; continue; }
                    if (origin !== null && origin !== PLAN.gpx.set) { strange += 1; continue; }
                    waypoints.push({lat: parseFloat(carried[p].getAttribute('lat')),
                                    lon: parseFloat(carried[p].getAttribute('lon')),
                                    name: firstText(carried[p], 'name'),
                                    kind: firstText(carried[p], 'type'),
                                    // Null where the element is absent and a
                                    // string where it stands, empty included:
                                    // an unnamed cut is a cut.
                                    stage: textOf(ours(block, PLAN.gpx.stage))});
                }

                loadedCount += 1;
                return {
                    id: 'loaded-' + loadedCount,
                    name: (tracks.length ? firstText(tracks[0], 'name') : null) ||
                          firstText(firstChildNamed(root, 'metadata'), 'name') || 'the loaded file',
                    isRoute: kind === PLAN.gpx.kind,
                    chainId: chainId,
                    waypoints: waypoints, generated: generated, strange: strange, legs: legs,
                    unknown: Object.keys(unknown),
                    lon: Float64Array.from(lon), lat: Float64Array.from(lat),
                    ele: Float64Array.from(ele), along: Float64Array.from(along),
                    // **Counted, not taken off the element list.** An empty
                    // <trkseg>, or one whose points are all unreadable, is a
                    // segment that leaves no break behind, and a page reporting
                    // '2 breaks, which are crossings' where the route has one
                    // has miscounted the thing this file is most careful about.
                    ends: ends, n: lon.length, breaks: breaks, mode: null
                };
            }

            function firstChildNamed(parent, name) {
                if (!parent) { return null; }
                for (var i = 0; i < parent.childNodes.length; i += 1) {
                    if (parent.childNodes[i].localName === name) { return parent.childNodes[i]; }
                }
                return null;
            }

            function textOf(list) {
                return list && list.length ? list[0].textContent : null;
            }

            // Which recorded point a written position stands at. A waypoint of
            // this map's own is exact to seven decimals, which is 11 cm, so this
            // is a lookup and not a match — but it is written as a search over
            // the whole recording because a file may have been edited by hand,
            // and a waypoint that landed on the wrong point would move a leg
            // rather than fail.
            function recordedAt(lon, lat) {
                var best = -1, closest = Infinity;
                for (var i = 0; i < loaded.n; i += 1) {
                    var away = panel().metresBetween(lon, lat, loaded.lon[i], loaded.lat[i]);
                    if (away < closest) { closest = away; best = i; }
                }
                return {at: best, away: closest};
            }

            // ---- the three modes ---------------------------------------------------
            // What a loaded file may become. The names travel with the control
            // and with window.trailsPlan.load, so a browser check drives the
            // same three things a reader picks from.
            //
            // **The middle one is not routing a foreign track**, and the table
            // reads oddly until that is said: re-routing between waypoints
            // throws the recorded shape away, which is exactly right for one of
            // this map's own plans — a plan *is* a handful of waypoints, and the
            // track under it was drawn from them — and useless for a recording
            // of thousands of points and no waypoints at all. Given one of
            // those it routes between its two ends, which is a thing somebody
            // may well want and is never a surprise, because the status line
            // says the file had no waypoints in it.
            var MODES = [
                {key: 'asis', label: 'Take it as it is'},
                {key: 'align', label: 'Align to the network'},
                {key: 'match', label: 'Match where a path exists'}
            ];

            // ---- what a mode does to *this* file ------------------------------------
            // **Three names cannot be true of two kinds of file at once**, and
            // that is what the mode picker asked of them for as long as it stood
            // beside the button: it had to be answered before anybody knew what
            // was in the file. Read as a plan, 'take it as it is' means the
            // route as it was planned; read as a recording it means the line as
            // it was walked. Both readings are reasonable and the picker offered
            // one word for them.
            //
            // So the question is asked once the file has been read, in terms of
            // the file: what it turned out to be, what each mode would do to it,
            // and which one is offered first. **One table, keyed by both** —
            // the wording and the default are one decision, and two recordings
            // of one decision drifting apart is the failure this page has found
            // three times.
            //
            // Nothing is withheld. Routing between the two ends of a recording
            // is rarely what anybody wants and is occasionally exactly it, so it
            // is named rather than taken away: a mode that works and is refused
            // is a capability lost, where a mode that says what it will do is a
            // reader who chose.
            var READINGS = {
                route: {
                    first: 'asis',
                    asis: 'Restore the plan: its points, its legs, and the stretches it kept as recorded.',
                    align: 'Keep its points and plan between them again, over the network as it now stands.',
                    match: 'Keep its line and attach it to the network again wherever a path exists.'
                },
                chain: {
                    first: 'asis',
                    asis: 'Take the line as it is \\u2014 it came off this map and is already exact.',
                    align: 'Route between its two ends only \\u2014 the line itself is not kept.',
                    match: 'Lay it on the network again wherever a path exists.'
                },
                track: {
                    first: 'match',
                    asis: 'Take the recorded line exactly as it was walked.',
                    align: 'Route between its two ends only \\u2014 the recording is not kept.',
                    match: 'Put it on the network wherever a path exists, and keep the rest as recorded.'
                }
            };

            // Which of the three kinds a read file is. The same three questions
            // describeFile asks, in the same order, because a file that says it
            // is one of this map's routes is that whatever else it carries.
            function kindOf(read) {
                if (read.isRoute) { return 'route'; }
                if (read.chainId) { return 'chain'; }
                return 'track';
            }

            // A break between two segments is a crossing and is never walked.
            // **This is the one reading of a loaded file that must not be got
            // wrong quietly**: GPX has no way to say a segment is a boat, so a
            // break is all a crossing leaves behind, and a page that joined the
            // two ends with a walked line would draw somebody a route across a
            // fjord. It counts as a crossing, adds nothing to the walking
            // distance and carries no profile — the same as every other
            // crossing on this map.
            // **The kind is handed in where one is known.** A crossing is a
            // crossing whichever of the two it is, and both are dashed the same
            // — but a route restored from a file that said `ferry` and written
            // out again saying `water` has quietly changed what it claims about
            // a fjord somebody has to get across.
            function crossingPart(from, to, kind) {
                var length = panel().metresBetween(from.lon, from.lat, to.lon, to.lat);
                return {kind: kind || 'water', lon: [from.lon, to.lon], lat: [from.lat, to.lat],
                        along: [0, length], length: length, height: null, distance: null,
                        read: false, tally: blankTally()};
            }

            // The same ground, walked the other way. A route whose two ends are
            // swapped is phase 7's third edit and it reaches a matched leg like
            // any other, so the parts are turned round rather than matched
            // again — matching backwards would anchor from the far end and could
            // answer differently, and a route that changed when it was reversed
            // would be a route measured twice.
            function turnedRound(part) {
                var made = {kind: part.kind, length: part.length, tally: part.tally, read: part.read};
                made.lon = part.lon.slice().reverse();
                made.lat = part.lat.slice().reverse();
                made.along = part.along.map(function (value) { return part.length - value; }).reverse();
                if (part.index) {
                    made.index = {from: part.index.from + (part.index.count - 1) * part.index.step,
                                  step: -part.index.step, count: part.index.count};
                }
                if (part.height === null) { made.height = null; made.distance = null; return made; }
                made.height = part.height.slice().reverse();
                made.distance = part.distance.map(function (value) { return part.length - value; }).reverse();
                return made;
            }

            function walkedBackwards(parts) {
                var out = [];
                for (var i = parts.length - 1; i >= 0; i -= 1) { out.push(turnedRound(parts[i])); }
                return out;
            }

            // What a leg between two waypoints of the loaded recording is, which
            // is the whole of what the modes change. Anything not anchored to the
            // recording falls through to the routing and the sampling that were
            // already here, so a waypoint dragged off the track needs no case of
            // its own: it stops being anchored and its legs become ordinary ones.
            function recordedParts(graph, from, to) {
                var low = from.at < to.at ? from.at : to.at, high = from.at < to.at ? to.at : from.at;
                var parts = [], at = low, i;
                // **Every break inside the stretch, not only a stretch that is
                // nothing but a break.** Take one of the two waypoints either
                // side of a break out — which phase 7's Remove does in one
                // click, and which merges the two legs that met there — and the
                // leg left behind spans the gap. Walked straight across, that is
                // a line drawn over a fjord and counted as ground, which is the
                // one thing this distinction exists to prevent. It is also why
                // `loaded.along` does not advance across a break and this must
                // not either.
                for (i = low; i < high; i += 1) {
                    if (!loaded.ends[i]) { continue; }
                    parts.push.apply(parts, walkedBetween(graph, at, i));
                    parts.push(crossingPart({lon: loaded.lon[i], lat: loaded.lat[i]},
                                            {lon: loaded.lon[i + 1], lat: loaded.lat[i + 1]}));
                    at = i + 1;
                }
                parts.push.apply(parts, walkedBetween(graph, at, high));
                return from.at < to.at ? parts : walkedBackwards(parts);
            }

            // ---- restoring a plan ---------------------------------------------------
            // **Take it as it is, read as what the file describes.** For
            // somebody's recording that is the line as it was walked, and it
            // always was. For a route this map wrote it is the *plan* — the
            // stations, the legs, and what each leg is made of — and until this
            // it was not: the stations were rebuilt out of the track's ends and
            // its breaks, which is right for a file that carries no waypoints
            // and wrong for one that carries its own. Measured, six points went
            // out and two came back, with the walked distance right to a
            // decimetre so that nothing looked wrong.
            //
            // Whether there is a plan in the file to restore. Every part of the
            // test is load-bearing: without the leg list there is nothing saying
            // what a leg was made of, and where the waypoints and the legs do
            // not count up the file was written by something this page does not
            // understand and the old reading is the safe one.
            function restoring() {
                return !!loaded && loaded.mode === 'asis' && loaded.isRoute &&
                    loaded.legs.length > 0 && loaded.waypoints.length === loaded.legs.length + 1;
            }

            // The track point a walked distance falls on, searched forward from
            // where the last part ended. **Forward, and not a binary search.**
            // `along` is the *walking* axis, so it stands still across a break —
            // a crossing advances the walk by nothing — and one distance
            // therefore names two points either side of it. Which of them a part
            // means depends on where the part started, and only a walk knows
            // that. On a tie the earlier wins, because a walked part ends *at*
            // the break and the stretch after it is begun deliberately.
            function alongIndex(distance, from) {
                var best = from, i;
                for (i = from; i < loaded.n; i += 1) {
                    if (Math.abs(loaded.along[i] - distance) < Math.abs(loaded.along[best] - distance)) { best = i; }
                    if (loaded.along[i] > distance) { break; }
                }
                return best;
            }

            // The break standing at a walked distance, for the one case that
            // cannot be reached by walking forward: a leg whose first part is a
            // crossing, because its own waypoint is out on the water and is in
            // no <trkseg> at all. Half a metre, because the two sides of a break
            // carry the same distance exactly and nothing else is near it.
            function breakAt(distance) {
                for (var i = 0; i + 1 < loaded.n; i += 1) {
                    if (loaded.ends[i] && Math.abs(loaded.along[i] - distance) < 0.5) { return i; }
                }
                return -1;
            }

            // One walked part of a restored leg. **A routed part is routed
            // again rather than copied**, and that is the decision this rests
            // on: the file holds a line and the network holds the edges under
            // it, and only the edges can say which dataset drew each metre,
            // whether anything calls it waymarked, and where no source records a
            // path at all. Copied, a restored plan would state 32 km of
            // recorded ground — the same loss this is fixing, better hidden.
            //
            // Where the network can no longer carry it, the recording is what is
            // left and is kept, rather than a straight line over the terrain.
            // That is said afterwards rather than swallowed.
            function restoredWalked(graph, kind, first, last, metres) {
                if (kind !== 'routed') {
                    return [trackPart(graph, first, last, undefined, undefined, undefined, undefined,
                                      kind === 'land' ? 'land' : undefined)];
                }
                // **Routed between its own two ends first, and checked against
                // the length the file states.** For a leg the reader clicked
                // that is the whole of it: the router is deterministic and the
                // weights have not moved, so it comes back to the centimetre.
                var a = graph.nearestNode(loaded.lat[first], loaded.lon[first], PLAN.matchToleranceM);
                var b = graph.nearestNode(loaded.lat[last], loaded.lon[last], PLAN.matchToleranceM);
                if (a >= 0 && b >= 0 && a !== b) {
                    var found = route(graph, a, b);
                    if (found && found.edges.length) {
                        var laid = routedParts(graph, found), run = 0;
                        laid.forEach(function (part) { run += part.length; });
                        if (agrees(run, metres)) { return laid; }
                    }
                }
                // **And where it does not agree, the part is matched rather
                // than routed.** A routed part of a *matched* route is a run of
                // spans between anchors that were merged into one, and the
                // cheapest path between its two ends is not the concatenation of
                // the cheapest paths between the anchors along it — the same
                // thing this document already records about align on a matched
                // route, at 7,266 m against 7,307. Measured here at 2,899
                // against 3,142. The anchors are not in the file, but the
                // geometry they were derived from is, so the matcher recovers
                // them from the very line it produced.
                var matched = matchedParts(graph, first, last), total = 0;
                matched.forEach(function (part) { total += part.length; });
                if (agrees(total, metres)) { return matched; }
                // Neither reproduced it, so the file's own line is what is left.
                // It is exact and it is honest, and what it costs is the edges
                // underneath — which is what `drifted` then says out loud.
                return [trackPart(graph, first, last)];
            }

            // Two lengths of one stretch, one stated by the file and one worked
            // out again. A metre, or a thousandth, whichever is the larger: the
            // file rounds what it writes and the page recomputes its distances
            // from written coordinates, so exact equality is not on offer.
            function agrees(got, said) {
                if (!isFinite(said) || said <= 0) { return false; }
                return Math.abs(got - said) <= Math.max(1, said / 1000);
            }

            // A leg laid out the way its own part list says, instead of by
            // guessing where the seams are. **The seam is inside the leg**,
            // which is why nothing before this restored one: a matched leg is
            // `routed + track + routed`, so anchorRecordedLegs — which asks
            // whether a leg is *wholly* recorded — never fires on the very legs
            // that need it. Measured, align routed 1,038 recorded metres away
            // and came back 353 m short without a word.
            //
            // Null where the file and the track do not line up, which puts the
            // leg back on the ordinary machinery rather than on a guess.
            function restoredParts(graph, from, to, wanted) {
                var parts = [], i;
                var cursor = (from.at === undefined || from.at === null) ? -1 : from.at;
                var reached = cursor >= 0 ? loaded.along[cursor] : (from.station || 0);
                for (i = 0; i < wanted.length; i += 1) {
                    var kind = wanted[i].kind, metres = wanted[i].m;
                    if (kind === 'water' || kind === CROSSING) {
                        // A crossing carries no track and advances the walk by
                        // nothing; all it left behind is the break, and its two
                        // ends are the points either side of that — except where
                        // one of them is a waypoint out on the water, which is in
                        // the <wpt> list and nowhere else.
                        var gap = cursor >= 0 ? cursor : breakAt(reached);
                        var head = cursor >= 0 ? {lon: loaded.lon[cursor], lat: loaded.lat[cursor]} : from;
                        var more = i + 1 < wanted.length;
                        var resumes = (gap >= 0 && gap + 1 < loaded.n) ? gap + 1 : -1;
                        var tail = (more && resumes >= 0)
                            ? {lon: loaded.lon[resumes], lat: loaded.lat[resumes]} : to;
                        parts.push(crossingPart(head, tail, kind));
                        if (more) {
                            if (resumes < 0) { return null; }
                            cursor = resumes;
                            reached = loaded.along[cursor];
                        }
                        continue;
                    }
                    if (cursor < 0 || !isFinite(metres)) { return null; }
                    var end = alongIndex(reached + metres, cursor);
                    if (end <= cursor) { return null; }
                    parts.push.apply(parts, restoredWalked(graph, kind, cursor, end, metres));
                    cursor = end;
                    reached = loaded.along[cursor];
                }
                return parts.length ? parts : null;
            }

            // One stretch of walked recording, in whichever way the mode asks
            // for it. Nothing at all where the stretch is a single point: a
            // <trkseg> holding one trackpoint ends where it begins, and a leg of
            // no length is a leg the height service would be asked about.
            function walkedBetween(graph, first, last) {
                if (first >= last) { return []; }
                return loaded.mode === 'match'
                    ? matchedParts(graph, first, last) : [trackPart(graph, first, last)];
            }

            // Where the waypoints of a loaded file come from, per mode.
            function pointsForLoaded(graph) {
                var made = [], wanted = [], i;
                if (restoring()) {
                    // **Where each station sits along the walk**, summed off the
                    // leg list rather than measured off the track: a crossing has
                    // a length and contributes none of it to the walking, so the
                    // two are different sums and only one of them is the axis the
                    // track carries.
                    var reached = 0, stations = [0];
                    loaded.legs.forEach(function (parts) {
                        parts.forEach(function (part) {
                            if (part.kind !== 'water' && part.kind !== CROSSING && isFinite(part.m)) {
                                reached += part.m;
                            }
                        });
                        stations.push(reached);
                    });
                    var cursor = 0;
                    for (i = 0; i < loaded.waypoints.length; i += 1) {
                        var wp = loaded.waypoints[i];
                        var at = alongIndex(stations[i], cursor);
                        cursor = at;
                        // **A station is anchored to the track only where the
                        // track is actually under it.** A waypoint set on open
                        // water is in the <wpt> list and in no <trkseg> at all,
                        // because the crossing either side of it writes nothing
                        // — so anchoring it to the nearest trackpoint would move
                        // it to the shore, which is the very point that went
                        // missing. A metre, because a waypoint is written at the
                        // position the track passes through and the two agree to
                        // seven decimals or not at all.
                        var here = panel().metresBetween(wp.lon, wp.lat, loaded.lon[at], loaded.lat[at]) <= 1.0
                            ? anchored(graph, at) : snapped(graph, wp.lat, wp.lon);
                        here.station = stations[i];
                        // The cuts come back with the points they were made on,
                        // which is the whole reason they live on a waypoint: a
                        // tour is planned whole, walked in pieces, and read back
                        // in the pieces it was planned in.
                        if (typeof wp.stage === 'string') { here.stage = wp.stage; }
                        if (loaded.legs[i]) { here.restore = loaded.legs[i]; }
                        made.push(here);
                    }
                    return made;
                }
                if (loaded.mode === 'align') {
                    if (loaded.waypoints.length) {
                        loaded.waypoints.forEach(function (point) {
                            var here = snapped(graph, point.lat, point.lon);
                            if (typeof point.stage === 'string') { here.stage = point.stage; }
                            made.push(here);
                        });
                    } else {
                        made.push(snapped(graph, loaded.lat[0], loaded.lon[0]));
                        made.push(snapped(graph, loaded.lat[loaded.n - 1], loaded.lon[loaded.n - 1]));
                    }
                    anchorRecordedLegs(graph, made);
                    return made;
                }
                // As it is, and matched: the recording's own ends, and both
                // sides of every break. A break is where a segment stopped, so
                // the point before it and the point after it are two stations
                // with a crossing between them.
                //
                // **Collected as indices first and never two of one point.** A
                // <trkseg> holding a single trackpoint ends where it begins, so
                // it flags two ends in a row and would put two waypoints on one
                // position — a leg of no length, an extra pin, and a request to
                // the height service about nothing.
                wanted.push(0);
                for (i = 0; i + 1 < loaded.n; i += 1) {
                    if (loaded.ends[i]) { wanted.push(i); wanted.push(i + 1); }
                }
                wanted.push(loaded.n - 1);
                wanted.forEach(function (at) {
                    if (made.length && made[made.length - 1].at === at) { return; }
                    made.push(anchored(graph, at));
                });
                return made;
            }

            // **A leg the file says was kept as recorded is restored as that**,
            // not routed. Align mode rebuilds a plan from its waypoints, and
            // for four of the five kinds that is exact — the router is
            // deterministic and the weights have not moved — but the fifth came
            // out of a file rather than out of the network, and re-routing it
            // would quietly replace it with whatever path happens to lie there.
            function anchorRecordedLegs(graph, made) {
                // **Looked up from what the file wrote, not from where the page
                // has since snapped it.** `made[i]` has already been through
                // `snapped`, which moves a waypoint up to `snapM` — 150 m — onto
                // the network, and asking which recorded point is nearest *that*
                // can land on a different pass of a switchback and move the
                // whole leg. The written position is what the writer put down.
                var written = loaded.waypoints.length ? loaded.waypoints : null;
                for (var k = 0; k + 1 < made.length && k < loaded.legs.length; k += 1) {
                    var parts = loaded.legs[k];
                    if (!parts.length) { continue; }
                    var recorded = true;
                    for (var p = 0; p < parts.length; p += 1) {
                        if (parts[p].kind !== PLAN.gpx.trackKind) { recorded = false; break; }
                    }
                    if (!recorded) { continue; }
                    [k, k + 1].forEach(function (i) {
                        var from = written && written[i] ? written[i] : made[i];
                        var found = recordedAt(from.lon, from.lat);
                        // And it may decline. A waypoint of a recorded leg was
                        // written either at the recorded point itself — exact to
                        // seven decimals, 11 cm — or at a named thing within
                        // `namedM` of it, which is the whole of how far a
                        // waypoint is ever moved from the route it belongs to.
                        // Past that the file is not describing this recording,
                        // and the leg is routed rather than anchored to a point
                        // that happens to be nearest.
                        if (found.at >= 0 && found.away <= PLAN.namedM) { made[i] = anchored(graph, found.at); }
                    });
                }
            }

            // What the file turned out to be, said before anything is done with
            // it. A chain export is recognised and *not* treated as a plan: it
            // has no waypoints to route between and no legs to rebuild, so it
            // becomes one recorded leg like any other track — recognised, named
            // after itself, and immediately something to work on, which is what
            // this phase is for. Drawing it as the chain it already is was the
            // alternative and is phase 4's job: a chain is one click away on the
            // map, and a chain id out of an older build names nothing here.
            // **It takes the file rather than reading the one in hand**, because
            // it is now said twice and the first time is before anything has
            // been taken: the offer names what the file turned out to be so the
            // mode can be chosen against it, and the status line says the same
            // afterwards. One sentence, written once, or the two would
            // eventually describe the same file differently.
            function describeFile(read) {
                var said = [];
                if (read.isRoute) {
                    said.push('a route this map wrote: ' + read.waypoints.length +
                              (read.waypoints.length === 1 ? ' waypoint' : ' waypoints') +
                              ', ' + read.legs.length + (read.legs.length === 1 ? ' leg' : ' legs'));
                } else if (read.chainId) {
                    said.push('a chain export: ' + read.name + ' (' + read.chainId + ')');
                } else {
                    said.push('a track from somewhere else: no waypoints and no legs');
                }
                said.push(read.n.toLocaleString('en-GB') + ' recorded points');
                if (read.breaks) {
                    said.push(read.breaks + (read.breaks === 1 ? ' break, which is a crossing' : ' breaks, which are crossings'));
                }
                if (read.generated) {
                    said.push(read.generated + (read.generated === 1 ? ' marker' : ' markers') + ' this map placed, skipped');
                }
                if (read.strange) {
                    said.push(read.strange + (read.strange === 1 ? ' waypoint' : ' waypoints') +
                              ' whose origin this page does not know, skipped');
                }
                // Never fatal and never silent. A part naming a kind this page
                // has no case for cannot be restored, so its leg is routed
                // between its two waypoints instead — which is a route that came
                // back different, and a reader who is not told has no way to know.
                if (read.unknown.length) {
                    said.push('a kind this page does not know (' + read.unknown.join(', ') + '), so those legs are routed instead');
                }
                return said.join(' · ');
            }

            // ---- loading ------------------------------------------------------------
            // **Reading a file and taking it are two steps now**, and the seam
            // is where the reader is asked. Everything that can refuse the file
            // happens in the first — a document that is not XML, a GPX with no
            // track — so what is on the map is still untouched while the
            // question is on the screen, and a cancelled offer costs nothing but
            // the parse.
            function readGpx(text) {
                var began = performance.now();
                var read = parseGpx(text);
                read.parseMs = performance.now() - began;
                read.began = began;
                return read;
            }

            // **The clock is restarted here and not kept from the read.** What
            // `settleMs` is worth saying about is the wait between choosing a
            // mode and a route being drawn; the seconds a reader spent looking
            // at the question are not the page's to report.
            function takeGpx(read, mode) {
                var known = false;
                MODES.forEach(function (offered) { known = known || offered.key === mode; });
                if (!known) {
                    throw new Error(mode + ' is not one of ' +
                                    MODES.map(function (offered) { return offered.key; }).join(', '));
                }
                read.began = performance.now();
                // Filled in by refresh() once every leg has settled, which is
                // the figure worth having: from the mode being chosen to a route
                // drawn on the map. It is null while that is still happening
                // rather than 0, because a load that is still working and one
                // that took no time are not the same thing.
                read.settleMs = null;
                read.mode = mode;
                loaded = read;
                applyEdit(function (graph) {
                    // The index is built here rather than inside the first leg
                    // that needs it, so that what a matched load costs is one
                    // figure and not one figure with a surprise buried in it.
                    if (mode === 'match') { edgeIndex(graph); }
                    points = pointsForLoaded(graph);
                    chosen = -1;
                });
                // Loading a file is a plan, so plan mode comes on with it: a
                // route drawn on a map that will not let it be touched is the
                // state this phase exists to avoid.
                if (!on) { switchTo(true); }
                // **A file's own title becomes the tour's**, unless it is the
                // one every unnamed file carries — adopting that would turn a
                // default into a choice the first time anything was saved again.
                var standard = panel() ? panel().routeName() : null;
                tourName = (read.name && read.name !== standard) ? read.name : '';
                fitWanted = true;
                loadSaid = describeFile(loaded);
                pendingFile = null;
                refresh();
            }

            // Reading and taking in one, which is what every check and every
            // test drives and what the picker did before the question existed.
            // Kept exactly as it was: a phase that moves an entry point moves
            // every acceptance figure taken through it.
            function loadGpx(text, mode) {
                takeGpx(readGpx(text), mode);
            }

            // **What the file said it was, against what came back.** A restored
            // plan's routed stretches are routed again rather than copied, which
            // is what brings the edges back and with them everything the route
            // says about the ground it covers -- and it means that where a
            // source has moved since the export the route is a different one.
            // Correctly different, and silently so unless something looks.
            //
            // Two figures are worth comparing and both come out of the file
            // itself: the walking it states, and the ground it says was kept as
            // recorded. The second moves on its own where a stretch the network
            // once carried can no longer be routed and the recording is what is
            // left -- which is the right answer and not one to keep quiet about.
            function drifted() {
                if (!restoring()) { return ''; }
                var walked = 0, recorded = 0, said = [];
                loaded.legs.forEach(function (parts) {
                    parts.forEach(function (part) {
                        if (!isFinite(part.m)) { return; }
                        if (part.kind === 'water' || part.kind === CROSSING) { return; }
                        walked += part.m;
                        if (part.kind === PLAN.gpx.trackKind) { recorded += part.m; }
                    });
                });
                var shape = composeRoute();
                if (walked && Math.abs(shape.total - walked) > 1) {
                    said.push('the network has moved under this plan: ' + Math.round(shape.total) +
                              ' m walked against the ' + Math.round(walked) + ' the file states');
                }
                if (shape.tally.recorded - recorded > 1) {
                    said.push(Math.round(shape.tally.recorded - recorded) +
                              ' m the network no longer carries, kept as recorded');
                }
                return said.length ? ' \\u00b7 ' + said.join(' \\u00b7 ') : '';
            }

            // ---- showing what was loaded -------------------------------------------
            // **A loaded route is somewhere else.** The map stands wherever the
            // reader left it and a file may describe ground fifty kilometres
            // away, so a load that changes nothing on the screen reads as a load
            // that did nothing. It is fitted once, when the route has settled,
            // and never again: the map is the reader's from that moment and a
            // control that moves it twice is one that fights the hand.
            //
            // Far enough in to read the route and no further. A two-hundred
            // metre route fitted to the pixel would put the reader at street
            // level with nothing around it to say where in the park they are.
            var SHOW_MAX_ZOOM = 15;

            function showRoute() {
                var shape = composeRoute();
                var bounds = L.latLngBounds([]), i;
                for (i = 0; i < shape.lon.length; i += 1) { bounds.extend([shape.lat[i], shape.lon[i]]); }
                // **And the points, which are not all in the line.** A waypoint
                // set on open water lies inside a crossing, and a crossing draws
                // nothing — so a route fitted to its drawn geometry alone would
                // put that point outside the window it is a station of.
                points.forEach(function (point) { bounds.extend([point.lat, point.lon]); });
                if (!bounds.isValid()) { return; }
                // The room the route may not be fitted into, because something
                // is standing in it: the profile panel takes the foot of the map
                // at whatever height the reader dragged it to, and the plan
                // control takes the top right. Measured rather than assumed —
                // both are the reader's to resize.
                var panelBox = document.querySelector('.trails-profile-panel');
                var planBox = document.querySelector('.trails-plan-control');
                var below = panelBox ? Math.round(panelBox.getBoundingClientRect().height) : 0;
                var beside = planBox ? Math.round(planBox.getBoundingClientRect().width) : 0;
                map.fitBounds(bounds, {
                    paddingTopLeft: [20, 20],
                    paddingBottomRight: [beside + 20, below + 20],
                    maxZoom: SHOW_MAX_ZOOM
                });
            }

            // ---- the offer ----------------------------------------------------------
            // A file is read, described, and only taken once a mode has been
            // chosen against what it turned out to be.
            function offerFile(text, name) {
                var read = readGpx(text);
                pendingFile = {read: read, name: name, kind: kindOf(read),
                               mode: READINGS[kindOf(read)].first};
                loadSaid = '';
                refresh();
            }

            // Reading a file costs a parse and nothing else, so an offer taken
            // back leaves the map exactly as it was.
            function dismissFile() {
                pendingFile = null;
                refresh();
            }

            // ---- the route's own series ---------------------------------------
            // Laid out of the parts, with the walking distance as its axis: a
            // crossing has no ground under it, advances nothing and leaves a
            // break behind — the same break the panel already draws wherever
            // nothing was read. Two walked parts meeting at a waypoint both
            // sample it, so the second copy is dropped, exactly as two edges
            // meeting at a node are.
            //
            // **The coordinates are laid here too, in the same walk.** The
            // profile is drawn from heights against distance and the file is
            // written from vertices, and composing those in two passes would be
            // two walks over one route that could disagree — each still looking
            // like a route. What comes out is the shape a chain's series has:
            // lon, lat, along, height, distance and stretches, which is what the
            // writer's runsOf and denseOf already know how to read. That the
            // geometry existed per part and was never composed is the whole
            // reason this phase is not wiring.
            //
            // **The two kinds of NaN are carried apart rather than told apart
            // afterwards.** A crossing pushes one because there is no ground
            // under it; an unread sample is one because the model had no reading
            // for ground that is there. The first has to break the track and the
            // second may only drop an <ele>, and in this series both are a NaN
            // in `height` — distinguishable, if at all, by a distance that
            // repeats. So the boundary is recorded where it happens, as a
            // stretch that ends: getting it wrong draws a line across a fjord or
            // cuts a route into dozens of pieces, and both look right on a chart.
            // **A range of the same walk, and never a slice of its figures.**
            // A stage is legs `first` up to but not including `last`, and what
            // it states about itself has to be composed rather than subtracted:
            // an ascent is not the difference of two ascents, a steepest is a
            // maximum over its own window, and a marking bucket is a sum over
            // its own edges. Given no range this is the whole route, which is
            // every call that existed before stages did.
            function composeRoute(fromLeg, toLeg) {
                var first = fromLeg === undefined || fromLeg === null ? 0 : fromLeg;
                var last = toLeg === undefined || toLeg === null ? legs.length : toLeg;
                var lon = [], lat = [], along = [], height = [], distance = [], free = [];
                var stretches = [], stretch = null, tally = blankTally();
                var walked = 0, crossings = 0, crossed = 0, straight = 0, read = false, joined = false;
                // **Where the heights came from, carried apart from whether
                // there are any.** A routed part's are the build's DTM1 samples
                // and a straight leg's come from the same service on demand; a
                // stretch kept as it was recorded carries whatever the loaded
                // file had on its trackpoints, which this map never asked
                // anybody about. A file crediting Kartverket for a consumer GPS
                // reading, and saying it was sampled every 5 m, states two
                // things that are not so.
                var modelled = false, fromFile = false;

                function close() {
                    if (!stretch) { return; }
                    stretch.to = lon.length;
                    stretch.sampleTo = height.length;
                    stretches.push(stretch);
                    stretch = null;
                }

                // A crossing, a leg still being worked out and a leg the height
                // service refused all leave the same hole: ground the route does
                // not connect. A curve drawn through it would count a climb
                // across it and a track drawn through it would assert a way
                // across, and neither was measured. The NaN pushed here sits
                // between two stretches and inside neither, so nothing writes it
                // as a point.
                function breakHere() {
                    close();
                    if (height.length) { height.push(NaN); distance.push(walked); free.push(0); }
                    joined = false;
                }

                // **Where the reader's own points sit, in walked metres.**
                // Recorded as the walk happens and not summed from the legs
                // afterwards: a crossing contributes no walking distance and a
                // leg still being worked out contributes none either, so a sum
                // over the legs' own lengths would put every later point too far
                // along. Leg i runs from point i to point i + 1, so the distance
                // at the head of leg i is point i's, and the walk's end is the
                // last point's.
                var stations = [];
                legs.slice(first, last).forEach(function (leg) {
                    stations.push(walked);
                    if (!leg.parts) { breakHere(); return; }
                    leg.parts.forEach(function (part) {
                        addTally(tally, part.tally);
                        if (part.height === null) {
                            crossings += 1;
                            crossed += part.length;
                            breakHere();
                            return;
                        }
                        if (part.kind === 'land') { straight += part.length; }
                        if (!stretch) { stretch = {from: lon.length, sampleFrom: height.length}; }
                        var mark = part.kind === 'land' ? 1 : 0, at;
                        for (at = (joined ? 1 : 0); at < part.lon.length; at += 1) {
                            lon.push(part.lon[at]); lat.push(part.lat[at]); along.push(walked + part.along[at]);
                        }
                        for (at = (joined ? 1 : 0); at < part.height.length; at += 1) {
                            height.push(part.height[at]);
                            distance.push(walked + part.distance[at]);
                            free.push(mark);
                            if (!isNaN(part.height[at])) { read = true; }
                        }
                        if (part.read) {
                            if (part.kind === PLAN.gpx.trackKind) { fromFile = true; } else { modelled = true; }
                        }
                        joined = part.height.length > 0 && part.lon.length > 0;
                        walked += part.length;
                    });
                });
                close();
                // One per point, never one per leg: with no points down there is
                // nothing to mark, and the guard is what says so. A range of one
                // leg has two stations, which is the same rule counted from the
                // other end.
                if (last > first || points.length) { stations.push(walked); }
                return {lon: lon, lat: lat, along: along, height: height, distance: distance, free: free,
                        stations: stations,
                        stretches: stretches, tally: tally, total: walked, read: read,
                        modelled: modelled, fromFile: fromFile,
                        // Filtered once, here, and read by the sentence above
                        // the button, by the file's description and by the
                        // markers the file carries. Three readings of one list,
                        // rather than three places applying one threshold.
                        protected: reportedAreas(tally),
                        crossing: crossings > 0, crossings: crossings, crossed: crossed, straight: straight};
            }

            // Which protected areas the route actually passes through, in the
            // order a reader wants them: the most ground first.
            //
            // **The threshold is the decision this makes, and it is a decision
            // rather than a measurement.** Under it a route that clips the
            // corner of a boundary would report an area it never entered and
            // generate a pair of waypoints for it, metres apart, in the file
            // somebody takes into the terrain. Why it is where it is, and what
            // it is measured against, is in trails.routing.protection; it
            // arrives here rather than being spelled, so that the report the
            // build prints and the sentence this page writes cannot come to
            // disagree about what counts as passing through somewhere.
            function reportedAreas(tally) {
                var table = graphAreas(), out = [];
                Object.keys(tally.protected).forEach(function (id) {
                    var metres = tally.protected[id];
                    if (metres < PLAN.touchedM) { return; }
                    var area = table[id];
                    if (!area) { throw new Error('the route lies in ' + id + ', which the page has no entry for'); }
                    out.push({id: id, name: area.name, form: area.form, metres: metres});
                });
                return out.sort(function (a, b) { return b.metres - a.metres; });
            }

            // The areas by their own id rather than by their place in the
            // header's list, built once. The tally counts by id because an id
            // is what an edge names and what outlives the list it was read from.
            //
            // **Built once there is something to build it from, not once.** The
            // guard used to be `if (!areasById)`, and an empty lookup is an
            // object like any other: asked before the graph's own block had run
            // — which `state()` alone can do, since it composes the route
            // whether or not a point is down — it would stay empty for the life
            // of the page, and every route through an area would then throw
            // about an id the page 'has no entry for'. It is not reachable in
            // the page this builds, where `protectedAreas` is assigned in the
            // graph's block before its stream is even inflated. The count is
            // what the guard tests, rather than a flag beside the table: the
            // keys here are somebody else's register names, and a register that
            // names an area 'built' would answer about the flag.
            var areasById = null, areasFrom = -1;

            function graphAreas() {
                var table = (window.trailsGraph && window.trailsGraph.protectedAreas) || [];
                if (!areasById || areasFrom !== table.length) {
                    areasById = Object.create(null);
                    table.forEach(function (area) { areasById[area.id] = area; });
                    areasFrom = table.length;
                }
                return areasById;
            }

            // Read off the composed series by the build's own rule: a climb
            // counts once the series has turned away from its low point by the
            // threshold, and a gain smaller than that is noise the sampling
            // invented. The same rule in Python is trails.routing.elevation, and
            // two halves of one profile read under two rules would answer
            // differently without either looking wrong. Never summed off the
            // parts: the threshold restarts at every boundary, and over this
            // network summing gives two thirds of the figure.
            function climbOf(values, threshold) {
                var total = 0, at = 0;
                while (at < values.length) {
                    if (isNaN(values[at])) { at += 1; continue; }
                    var first = at;
                    while (at < values.length && !isNaN(values[at])) { at += 1; }
                    total += runClimb(values, first, at, threshold);
                }
                return total;
            }

            function runClimb(values, first, last, threshold) {
                var total = 0, anchor = values[first], extreme = values[first];
                for (var at = first + 1; at < last; at += 1) {
                    var height = values[at];
                    if (extreme >= anchor) {
                        if (height > extreme) { extreme = height; }
                        else if (extreme - height >= threshold) { total += extreme - anchor; anchor = extreme; extreme = height; }
                    } else if (height < extreme) { extreme = height; }
                    else if (height - extreme >= threshold) { anchor = extreme; extreme = height; }
                }
                // The run the series ends on is judged by the same threshold as
                // any other, or a metre of noise lands on the end of every one.
                if (extreme - anchor >= threshold) { total += extreme - anchor; }
                return total;
            }

            function figuresOf(shape) {
                var high = -Infinity, low = Infinity, upside = new Array(shape.height.length);
                for (var i = 0; i < shape.height.length; i += 1) {
                    var value = shape.height[i];
                    upside[i] = -value;
                    if (isNaN(value)) { continue; }
                    if (value > high) { high = value; }
                    if (value < low) { low = value; }
                }
                // Nothing read is not a climb of zero, the same distinction
                // the Python side keeps: a figure of zero is a statement about
                // flat ground.
                return {
                    ascent: shape.read ? climbOf(shape.height, PLAN.ascentThresholdM) : NaN,
                    descent: shape.read ? climbOf(upside, PLAN.ascentThresholdM) : NaN,
                    high: shape.read ? high : NaN,
                    low: shape.read ? low : NaN,
                    // A route has no single direction to name and no ascent that
                    // is true both ways round, so it names neither.
                    bearing: null, point: null
                };
            }

            // The two groups reported apart, never folded into the walking
            // total. A crossing is not walking and a stretch drawn straight is
            // not a path, and the reader is told both rather than shown one
            // number that quietly holds all three.
            function told(shape) {
                var said = [];
                if (shape.crossings) {
                    said.push(shape.crossings + (shape.crossings === 1 ? ' crossing, ' : ' crossings, ') +
                              (shape.crossed / 1000).toFixed(2) + ' km');
                }
                if (shape.straight > 0) {
                    said.push((shape.straight / 1000).toFixed(2) + ' km drawn straight, not a path');
                }
                // Said wherever it is true, because the climb above it was read
                // under a different rule from every other climb on this map and
                // the figure alone cannot say so.
                if (shape.fromFile) {
                    said.push(shape.modelled ? 'part of the climb is the loaded file\u2019s own heights, not the model'
                        : 'the climb is the loaded file\u2019s own heights, not the model');
                }
                var outstanding = unsettled();
                if (outstanding.waiting) {
                    said.push(outstanding.waiting + (outstanding.waiting === 1 ? ' leg' : ' legs') + ' still being worked out');
                }
                if (outstanding.refused.length) {
                    said.push(outstanding.refused.length + (outstanding.refused.length === 1 ? ' leg' : ' legs') +
                              ' with no heights: ' + outstanding.refused[0].failed);
                }
                return said;
            }

            // What the route is still missing. One count, read by the sentence
            // the reader sees and by the refusal that keeps the file from being
            // written: two counts of the same thing would eventually disagree
            // about whether a route is finished.
            function unsettled() {
                return {
                    // A leg carried through a live drag without its heights
                    // counts here too. Its length is real and is walked, so the
                    // distance under the reader's hand is right; its profile and
                    // what protects it are not there yet, and a file written
                    // from it would state ground nothing had been read along.
                    waiting: legs.filter(function (leg) {
                        return leg.provisional || (!leg.parts && !leg.failed);
                    }).length,
                    refused: legs.filter(function (leg) { return leg.failed; })
                };
            }

            // ---- drawing --------------------------------------------------------
            // Not the overlay pane, and not the marker pane either: what goes
            // into either is counted for ever, and both counts are acceptance
            // figures. A pane of its own also keeps the route above every trail
            // layer without depending on the order the layers were added in.
            var pane = map.createPane('trailsPlanRoute');
            pane.style.zIndex = 460;
            // **Nothing the route draws is ever a click target, and phase 7 did
            // not change that.** Clicking the route means one thing now — put a
            // waypoint into that leg — and it is decided by hit-testing the
            // geometry this page is already holding, in the one handler every
            // click goes through. An interactive line would have to be turned
            // off again the moment plan mode is, or the route would stand
            // between a reader and the trail underneath it: that is the mistake
            // the park boundary made for a fortnight, and one switch is one
            // switch too many to have to remember.
            pane.style.pointerEvents = 'none';

            function draw(parts, waiting) {
                var layers = [];
                parts.forEach(function (part) {
                    var corners = [];
                    for (var i = 0; i < part.lon.length; i += 1) { corners.push([part.lat[i], part.lon[i]]); }
                    if (corners.length < 2) { return; }
                    var colour = (waiting || part.kind === 'waiting') ? WAITING : ROUTE;
                    // The casing first, so it lies under. Dashed identically, or
                    // white would show through every gap.
                    [[CASING, 6], [colour, 2.6]].forEach(function (stroke) {
                        layers.push(L.polyline(corners, {
                            pane: 'trailsPlanRoute', color: stroke[0], weight: stroke[1], opacity: 0.95,
                            dashArray: DASH[part.kind], interactive: false
                        }).addTo(map));
                    });
                });
                return layers;
            }

            function undraw(layers) {
                layers.forEach(function (layer) { if (layer) { map.removeLayer(layer); } });
            }

            function straightAcross(from, to) {
                return [{kind: 'waiting', lon: [from.lon, to.lon], lat: [from.lat, to.lat]}];
            }

            // ---- the route ------------------------------------------------------
            var on = false;
            var points = [];
            var legs = [];
            var pins = [];
            var settling = 0;
            // Which waypoint the reader has hold of, as an index into points.
            // **A click on a pin selects it; it does not delete it.** The same
            // click is a few pixels away from one that places a point, there is
            // no way back from a deletion, and everything a selection makes
            // possible — take this one out, move it one place earlier or later —
            // has to be somewhere a reader can find it whatever the gesture is.
            var chosen = -1;
            // The graph once it has arrived, because a drag settles inside a
            // pointer event and cannot wait a microtask for a payload that has
            // been in the page since it loaded.
            var held = null;
            var dragging = null;

            // ---- the pins ---------------------------------------------------------
            // **A waypoint is an L.marker and no longer an L.circleMarker, and
            // that is what this phase costs in figures every review checks
            // first.** Measured before it was built: a circle marker added to
            // this map has no `dragging` at all and `draggable: true` on one is
            // silently ignored, while a marker gets a live handler. So a
            // waypoint that can be dragged is a marker — which draws no path and
            // lives in the marker pane — and a five-point route's plan pane goes
            // from 13 paths to 8 while the marker pane goes from 198 to 203.
            // `.leaflet-marker-icon` moves with them, from 0 to 5: folium
            // overwrites that class on its own markers and these are Leaflet's
            // own, so the probe that has always read 0 is reading the same fact
            // as the 203 through a second lens.
            //
            // Drawn as a div rather than an image so that its number is the
            // element's own text and selecting it is one attribute: a route
            // whose points can be reordered cannot be read without the numbers,
            // and rewriting five spans is a write nothing can feel.
            var PIN_PX = 18;

            // **A second ring where a stage changes hands**, and a ring rather
            // than a colour or a size: a pin already says two things — which
            // number it is and whether it is picked — and a third meaning has to
            // be readable beside both rather than instead of one. Drawn as a
            // shadow, so the icon keeps its size and its anchor and nothing
            // about where a click lands moves.
            function pinStyle(picked, ends) {
                return 'display:block;width:100%;height:100%;box-sizing:border-box;border-radius:50%;' +
                    'border:2px solid ' + ROUTE + ';background:' + (picked ? ROUTE : CASING) + ';' +
                    'color:' + (picked ? CASING : ROUTE) + ';text-align:center;' +
                    (ends ? 'box-shadow:0 0 0 2px ' + CASING + ',0 0 0 4px ' + ROUTE + ';' : '') +
                    'font:bold 10px/' + (PIN_PX - 4) + 'px sans-serif';
            }

            function pin(point) {
                var marker = L.marker([point.lat, point.lon], {
                    icon: L.divIcon({className: 'trails-plan-pin', iconSize: [PIN_PX, PIN_PX],
                                     iconAnchor: [PIN_PX / 2, PIN_PX / 2],
                                     html: '<span style="' + pinStyle(false) + '"></span>'}),
                    draggable: true, keyboard: false,
                    // Above every other marker on the map. Leaflet stacks
                    // markers within the pane by latitude, so a hut drawn at
                    // the same place as a waypoint covers it — measured: at the
                    // first waypoint of a route along a chain, the topmost
                    // element was folium's own `awesome-marker`, which would
                    // take the click that was meant for the pin and be read as
                    // a click on the route under it. The offset is far larger
                    // than the pixel spread of this map's markers at any zoom,
                    // because the term it is added to is a pixel position.
                    zIndexOffset: 100000
                }).addTo(map);
                marker.on('dragstart', beginDrag);
                marker.on('drag', overDrag);
                marker.on('dragend', endDrag);
                // What was last written to it, kept here rather than read back
                // off the element: a style set to '#111111' reads back as
                // 'rgb(17, 17, 17)', so an element cannot be asked whether it
                // already says what is about to be written to it.
                return {marker: marker, label: null, picked: null, ends: null, live: null};
            }

            function pinAt(marker) {
                for (var i = 0; i < pins.length; i += 1) { if (pins[i].marker === marker) { return i; } }
                return -1;
            }

            function pinFor(element) {
                for (var i = 0; i < pins.length; i += 1) {
                    if (pins[i].marker.getElement() === element) { return i; }
                }
                return -1;
            }

            // Applied as differences, never rewritten wholesale. This runs on
            // every edit and, while a waypoint is being dragged, several times a
            // second — and writing a style that is already set is one of the two
            // things that have frozen this map outright.
            function dressPins() {
                var most = Math.min(pins.length, points.length);
                for (var i = 0; i < most; i += 1) {
                    var record = pins[i], element = record.marker.getElement();
                    var label = String(i + 1), picked = i === chosen;
                    var ends = i > 0 && i + 1 < points.length && typeof points[i].stage === 'string';
                    if (element && record.label !== label) {
                        element.firstChild.textContent = label;
                        record.label = label;
                    }
                    if (element && (record.picked !== picked || record.ends !== ends)) {
                        element.firstChild.setAttribute('style', pinStyle(picked, ends));
                        record.picked = picked;
                        record.ends = ends;
                    }
                    // Out of plan mode a pin must no more stand between a reader
                    // and the line underneath than the route does, so it stops
                    // taking pointer events at all — and stops being draggable
                    // with them.
                    if (element && record.live !== on) {
                        element.style.pointerEvents = on ? 'auto' : 'none';
                        record.live = on;
                    }
                    if (record.marker.dragging) {
                        if (on) { record.marker.dragging.enable(); } else { record.marker.dragging.disable(); }
                    }
                    // The marker the pointer is holding is where the pointer put
                    // it. Writing a snapped position under it mid-drag would
                    // make it fight the hand moving it.
                    if (dragging && dragging.at === i) { continue; }
                    var where = record.marker.getLatLng();
                    if (where.lat !== points[i].lat || where.lng !== points[i].lon) {
                        record.marker.setLatLng([points[i].lat, points[i].lon]);
                    }
                }
            }

            function syncPins() {
                while (pins.length > points.length) { map.removeLayer(pins.pop().marker); }
                while (pins.length < points.length) { pins.push(pin(points[pins.length])); }
                dressPins();
            }

            // ---- stages -------------------------------------------------------------
            // **A tour is planned whole and walked in pieces.** A point can be
            // marked as the end of one, and what falls out is a run of stages
            // covering the route end to end. The first point and the last are
            // boundaries whether anybody says so, so only the ones between are
            // ever marked -- and a tour nobody has cut is one stage, which is
            // the same as no stages and is treated as none.
            //
            // **The mark lives on the point object**, which is what makes it
            // survive an edit: phase 7's model keeps a leg exactly while it runs
            // between the same two waypoint *objects*, so reordering and
            // inserting carry the mark along without a case of their own. A drag
            // is the exception and the trap -- it replaces the point with a new
            // object on purpose -- so `dragTo` copies it across, and so does
            // every other place that rebuilds a point from a position.
            //
            // `stage` is null where a point ends nothing, and a string where it
            // ends a stage: the text is the name, and empty means a stage with
            // no name of its own rather than no stage. One field for the mark
            // and the name together, because they are one decision and two
            // fields would be two ways to disagree.
            // Where the reader cut the tour, as point indices. **The ends are
            // not among them**: a tour begins and ends whether anybody says so,
            // and a pin at the finish marked as a transition would claim the
            // walk carries on past it.
            function cutsOf() {
                var out = [];
                for (var i = 1; i + 1 < points.length; i += 1) {
                    if (typeof points[i].stage === 'string') { out.push(i); }
                }
                return out;
            }

            function stagesOf() {
                if (points.length < 2) { return []; }
                var cuts = [0].concat(cutsOf());
                var i;
                cuts.push(points.length - 1);
                var out = [];
                for (i = 0; i + 1 < cuts.length; i += 1) {
                    out.push({from: cuts[i], to: cuts[i + 1], at: i,
                              name: points[cuts[i + 1]].stage || null});
                }
                return out;
            }

            // What a stage is called where nobody has named it: the two points
            // it runs between, in the numbers the list and the pins already
            // carry. Not its kilometres, which move whenever a point does.
            function stageName(stage) {
                return stage.name || (stage.from + 1) + '–' + (stage.to + 1);
            }

            // What its own file calls it: the tour and then the stage, where the
            // tour has a name, so a device listing several says which walk they
            // belong to as well as which piece of it.
            function stageTitle(stage) {
                var mine = stageName(stage);
                var whole = tourName || (panel() ? panel().routeName() : null);
                return whole ? whole + ' \u00b7 ' + mine : mine;
            }

            // Marking a point, and unmarking it. The ends are not offered: a
            // tour that ends where it ends needs nobody to say so, and a mark
            // there would make a stage of no legs.
            function cutAt(at, wanted) {
                if (at < 1 || at + 1 >= points.length) { return; }
                points[at].stage = wanted ? (points[at].stage || '') : null;
                refresh();
            }

            // Naming one, which is the same field. A name on the last point is
            // allowed and marks nothing -- the tour already ends there.
            function nameStage(at, name) {
                if (at < 0 || at >= points.length) { return; }
                // **An empty box over a point that ends nothing changes
                // nothing.** Clicking into the last stage's name and out of it
                // again wrote the empty string, which is a *string* and so a
                // mark — invisible until the route grew a point past it and a
                // stage boundary nobody had asked for appeared. Measured: two
                // stages became three.
                //
                // Naming the last stage and then walking further does keep the
                // boundary, and that is a decision rather than the defect: a
                // stage somebody named ends where they said it ended, and the
                // ground added after it is the next stage.
                if (name === '' && typeof points[at].stage !== 'string') { return; }
                if (points[at].stage === name) { return; }
                points[at].stage = name;
                refresh();
            }

            // What only this side knows about a *stage*, in the shape the writer
            // reads for a whole tour. It is the same two lists narrowed to the
            // stage's own legs and its own points -- and the points are
            // renumbered from one, because a stage's file is a route in its own
            // right and not an extract with holes in its numbering.
            function writableRange(from, to, title) {
                return {
                    why: '',
                    // Named as the stage it is, so a device listing four tracks
                    // shows four names and not the tour four times. The file
                    // name is the tour's, which is what `stem` is for.
                    name: title,
                    stem: tourName || null,
                    waypoints: points.slice(from, to + 1).map(nameOf),
                    legs: legs.slice(from, to).map(function (leg) {
                        return (leg.parts || []).map(function (part) {
                            return {kind: part.kind, length: part.length};
                        });
                    })
                };
            }

            // One stage as its own file. **Composed, never sliced**: its
            // crossings are read off its own shape, or a stage would carry an
            // `Enters` for a boundary it never reaches, in a file somebody takes
            // into the terrain.
            // Every stage on its own, and the whole tour with its cuts in it,
            // as one archive. **The tour goes in too**: the stages are what a
            // reader takes into the terrain and the tour is what they come back
            // to and edit, and an archive holding only the pieces would be a
            // set of files nothing can put together again.
            // **Never fatal and never silent.** Writing an archive is the one
            // thing here that finishes after the click that asked for it, so a
            // failure arrives as a rejected promise with nobody listening —
            // which is a button that does nothing and says nothing about it.
            function fileFailed(failure) {
                loadSaid = 'That file could not be written: ' +
                    (failure && failure.message ? failure.message : String(failure));
                refresh();
            }

            function saveStages() {
                var made = stagesOf().map(function (stage) {
                    var shape = composeRoute(stage.from, stage.to);
                    return panel().routeFile(figuresOf(shape), shape, told(shape),
                                             writableRange(stage.from, stage.to, stageTitle(stage)),
                                             stageName(stage));
                });
                var whole = composeRoute();
                made.push(panel().routeFile(figuresOf(whole), whole, told(whole), writable()));
                return panel().saveZip(made, writable()).catch(fileFailed);
            }

            function saveStage(stage) {
                var shape = composeRoute(stage.from, stage.to);
                var made = panel().routeFile(figuresOf(shape), shape, told(shape),
                                             writableRange(stage.from, stage.to, stageTitle(stage)),
                                             stageName(stage));
                panel().save(made.name, made.text);
            }

            // ---- the legs ---------------------------------------------------------
            function newLeg(graph, from, to, mayAsk) {
                var leg = {from: from, to: to, parts: null, failed: null, provisional: false, layers: []};
                // Something on the map the instant the gesture lands, replaced
                // when the leg is worked out. **Only this leg is drawn**, then
                // and later: rebuilding the whole route on every change is what
                // froze this map twice already, on a layer rather than on a
                // route, and a drag would do it eight times a second.
                leg.layers = draw(straightAcross(from, to));
                settling += 1;
                // Wrapped, so that a fault thrown on the way *into* the work
                // is a rejection like any other rather than an exception that
                // leaves the count of outstanding legs standing for ever.
                Promise.resolve().then(function () { return resolve(graph, from, to, mayAsk); }).then(function (parts) {
                    leg.parts = parts;
                    leg.provisional = parts.some(function (part) { return part.provisional; });
                }, function (failure) {
                    leg.failed = String(failure && failure.message ? failure.message : failure);
                // A third handler rather than a catch over the two above: a
                // fault while *drawing* is not a leg that could not be worked
                // out, and reporting it as one sends the next reader to the
                // wrong place. It belongs in the console, loudly.
                }).then(function () {
                    settling -= 1;
                    // **This one line is the whole of the cancellation.** Every
                    // edit that changes what a leg runs between replaces it with
                    // a new object, so a reply about ground a waypoint has since
                    // left arrives here and finds itself off the route — and no
                    // leg is ever drawn from an answer that is no longer wanted.
                    // A drag settling eight times a second leans on it hardest.
                    if (legs.indexOf(leg) < 0) { return; }
                    undraw(leg.layers);
                    leg.layers = draw(leg.parts || straightAcross(from, to), leg.provisional);
                    refresh();
                });
                return leg;
            }

            // **The legs follow from the waypoints rather than being edited
            // beside them.** Insert, remove, reorder and drag each rewrite the
            // list of points and nothing else; a leg survives exactly when it
            // still runs between the same two waypoints it already ran between,
            // and what an edit costs falls out of that — two legs for an insert,
            // one for a removal, the three that touch a point for a move.
            // Nothing here has to work out which legs an edit invalidated, which
            // is the arithmetic all four of them would otherwise get wrong in
            // four different ways.
            //
            // A waypoint that has moved is a *new* object rather than a mutated
            // one, so a drag needs no case of its own: the legs beside it stop
            // matching and are rebuilt, and everything beyond them is untouched.
            function relink(graph, mayAsk) {
                var kept = legs, i, k;
                legs = [];
                for (i = 0; i + 1 < points.length; i += 1) { legs.push(null); }
                for (i = 0; i < legs.length; i += 1) {
                    for (k = 0; k < kept.length; k += 1) {
                        if (kept[k] && kept[k].from === points[i] && kept[k].to === points[i + 1]) {
                            legs[i] = kept[k]; kept[k] = null; break;
                        }
                    }
                }
                kept.forEach(function (leg) { if (leg) { undraw(leg.layers); } });
                for (i = 0; i < legs.length; i += 1) {
                    if (!legs[i]) { legs[i] = newLeg(graph, points[i], points[i + 1], mayAsk); }
                }
            }

            function withGraph(run, always) {
                if (!window.trailsGraph) {
                    say('There is no routing graph in this page, so nothing can be routed.');
                    always();
                    return;
                }
                // Two handlers rather than a catch, for the reason above. The
                // release is a finally rather than a line after the call: the
                // work must be counted as over whether it succeeded or threw,
                // and a throw still reaches the console, loudly.
                window.trailsGraph.ready.then(function (graph) {
                    held = graph;
                    try { run(graph); } finally { always(); }
                }, function () {
                    say('The routing graph did not arrive, so nothing can be routed.');
                    always();
                });
            }

            // ---- the five edits ---------------------------------------------------
            // Every one of them runs through here. The graph is what turns a
            // position into a waypoint and a pair of waypoints into a leg, and a
            // route half-edited while it arrives would be a second state to keep
            // in step with this one.
            function applyEdit(change) {
                // Counted as outstanding from the gesture, not from the moment
                // the graph answers. A reader who has clicked is waiting, and a
                // state that reads 'nothing in hand' for the microtask in
                // between is one a check would believe.
                settling += 1;
                refresh();
                withGraph(function (graph) {
                    change(graph);
                    relink(graph, true);
                    syncPins();
                }, function () { settling -= 1; refresh(); });
            }

            // Snapped to the network where there is any within reach, so a route
            // can start from where the reader meant rather than from a metre
            // beside it; beyond that the raw point stands and the leg is drawn
            // straight.
            function snapped(graph, lat, lon) {
                var node = graph.nearestNode(lat, lon, PLAN.snapM);
                return node >= 0
                    ? {lat: graph.nodeLat[node], lon: graph.nodeLon[node], node: node}
                    : {lat: lat, lon: lon, node: -1};
            }

            function place(lat, lon) {
                applyEdit(function (graph) {
                    points.push(snapped(graph, lat, lon));
                    chosen = points.length - 1;
                });
            }

            // **Inserting is this phase's own addition and not one of the
            // numbered requirements**, which say only that waypoints can be
            // reordered and removed. Without it a route can be corrected only
            // from the end, which is how a fifteen-point plan gets thrown away
            // over a mistake at point three.
            //
            // **The index is checked inside the edit and not before it.** An
            // edit runs when the graph answers, which is a microtask later, so
            // two asked for in one turn would both be checked against the route
            // as it was before either — and the second would splice against a
            // list that had already moved under it.
            // ``trackAt`` is which point of the loaded recording the click
            // landed on, where it landed on a stretch kept as recorded. Passed
            // through rather than worked out again here: **without it a point
            // put into the middle of a recorded leg would split it into two legs
            // that are no longer the recording**, and the whole track would be
            // replaced by a routed line the moment a reader corrected one point
            // of it. With it both halves stay what they were.
            function insert(at, lat, lon, trackAt) {
                applyEdit(function (graph) {
                    if (at < 1 || at > points.length - 1) { return; }
                    points.splice(at, 0, trackAt === undefined || trackAt === null || !loaded
                        ? snapped(graph, lat, lon) : anchored(graph, trackAt));
                    chosen = at;
                });
            }

            // And removing merges the two legs that met at the point, which
            // falls out of the rule above rather than being arranged here.
            function remove(at) {
                applyEdit(function () {
                    if (at < 0 || at >= points.length) { return; }
                    points.splice(at, 1);
                    chosen = -1;
                });
            }

            // Reordering, one place at a time. The requirement is that the
            // points can be reordered and the route follows; a point moved past
            // its neighbour is the smallest gesture that does that, it composes
            // into any order at all, and it needs no second way of pointing at a
            // waypoint — the reader is already holding one.
            function moveBy(at, step) {
                applyEdit(function () {
                    var to = at + step;
                    if (at < 0 || at >= points.length || to < 0 || to >= points.length) { return; }
                    var moved = points[at];
                    points[at] = points[to];
                    points[to] = moved;
                    chosen = to;
                });
            }

            // **And to any place at all, which a list can ask for and a pin
            // cannot.** A splice rather than a run of swaps: a swap is a full
            // re-route of the two legs it touches, so dragging a point four
            // places up a list would route eight legs to arrive at the two that
            // actually changed. It is also a different gesture's meaning —
            // dropping a row between two others takes it out and puts it back
            // in, where a run of swaps would drag every point it passed one
            // place the other way.
            function moveTo(at, to) {
                applyEdit(function () {
                    if (at < 0 || at >= points.length || to < 0 || to >= points.length || at === to) { return; }
                    points.splice(to, 0, points.splice(at, 1)[0]);
                    chosen = to;
                });
            }

            // One misclick should not cost a route, and taking the last point
            // back is the gesture a reader reaches for before they know the rest
            // of these are there.
            function undo() {
                applyEdit(function () {
                    if (!points.length) { return; }
                    points.pop();
                    if (chosen >= points.length) { chosen = points.length - 1; }
                });
            }

            // ---- dragging ---------------------------------------------------------
            // **Throttled, because a drag is not a click.** Placing a point
            // costs 19-76 ms including its Dijkstra and composing the whole
            // route another 3, so the two legs a dragged waypoint moves are 40
            // to 160 ms of work; run at the rate a pointer reports its position
            // that is three of them queued per frame and a map that has stopped
            // answering. Every 120 ms it is six or eight settles a second, which
            // is the route following the hand. There was no throttle and no
            // cancellation anywhere in plan mode before this: the only
            // setTimeout near it belonged to the search box.
            var DRAG_EVERY_MS = 120;

            function beginDrag(event) {
                var at = pinAt(event.target);
                if (at < 0) { return; }
                dragging = {at: at, ran: 0, timer: null};
                chosen = at;
                refresh();
            }

            function overDrag(event) {
                if (!dragging || !held) { return; }
                var now = performance.now();
                var due = dragging.ran + DRAG_EVERY_MS - now;
                if (due > 0) {
                    // The trailing settle, so the position the pointer came to
                    // rest at is worked out even if it stops between two ticks.
                    if (dragging.timer === null) {
                        dragging.timer = setTimeout(function () {
                            dragging.timer = null;
                            overDrag(event);
                        }, due);
                    }
                    return;
                }
                dragging.ran = now;
                // The index was taken when the pointer went down and the array
                // is not shortened under a live drag, but a waypoint written
                // past the end of the list would be a route with a hole in it
                // that nothing raised about.
                if (dragging.at >= points.length) { return; }
                var where = event.target.getLatLng();
                points[dragging.at] = snapped(held, where.lat, where.lng);
                // Nothing may be asked of the height service while the pointer
                // is down: see `resolve`.
                relink(held, false);
                refresh();
            }

            function endDrag(event) {
                if (!dragging) { return; }
                if (dragging.timer !== null) { clearTimeout(dragging.timer); dragging.timer = null; }
                var at = dragging.at, where = event.target.getLatLng();
                dragging = null;
                // The same path every other edit takes, which is what makes a
                // drag that began before the payload arrived say so rather than
                // leave a pin somewhere its waypoint is not.
                applyEdit(function (graph) {
                    if (at >= points.length) { return; }
                    points[at] = snapped(graph, where.lat, where.lng);
                });
            }

            // ---- where a click lands ----------------------------------------------
            // How near a click has to fall to the drawn route to be taken as a
            // point going into it rather than one going on the end. Read as
            // pixels and turned into metres at the zoom the reader is looking
            // at, so it means near the line *as drawn* wherever the map is.
            var ON_ROUTE_PX = 8;

            // The distance from a position to a segment, and the point on that
            // segment nearest to it. Flat and local: a degree of latitude is
            // 111,320 m and a degree of longitude that times the cosine, which
            // is the approximation nearestNode is already written with and is
            // exact to well under a metre over the tens of metres this is ever
            // asked about.
            function nearSegment(lat, lon, cosine, aLat, aLon, bLat, bLon) {
                var ax = (aLon - lon) * cosine, ay = aLat - lat;
                var bx = (bLon - lon) * cosine, by = bLat - lat;
                var dx = bx - ax, dy = by - ay, span = dx * dx + dy * dy;
                var t = span > 0 ? -(ax * dx + ay * dy) / span : 0;
                t = t < 0 ? 0 : (t > 1 ? 1 : t);
                var cx = ax + t * dx, cy = ay + t * dy;
                return {away: Math.sqrt(cx * cx + cy * cy) * 111320,
                        lat: aLat + t * (bLat - aLat), lon: aLon + t * (bLon - aLon)};
            }

            // Which leg a click landed on, and where along it — or nothing.
            // Every vertex of the route is walked, which is thousands of them
            // over a long one and a millisecond or two against the 19 to 76 a
            // click already costs. A leg still being worked out is hit-tested
            // as the straight line it is drawn as, so a point can be put into
            // one before it settles.
            function onRoute(lat, lon) {
                var cosine = Math.cos(lat * Math.PI / 180);
                var withinM = ON_ROUTE_PX * 40075016.686 * cosine / Math.pow(2, map.getZoom() + 8);
                var best = null;
                for (var i = 0; i < legs.length; i += 1) {
                    var parts = legs[i].parts || straightAcross(legs[i].from, legs[i].to);
                    for (var p = 0; p < parts.length; p += 1) {
                        var part = parts[p];
                        for (var v = 0; v + 1 < part.lon.length; v += 1) {
                            var near = nearSegment(lat, lon, cosine, part.lat[v], part.lon[v],
                                                   part.lat[v + 1], part.lon[v + 1]);
                            if (near.away > withinM) { continue; }
                            if (best && near.away >= best.away) { continue; }
                            best = {leg: i, away: near.away, lat: near.lat, lon: near.lon, trackAt: null};
                            // Which point of the loaded recording the click
                            // landed on, where the part came out of one. The
                            // nearer of the segment's two ends rather than the
                            // position between them: a recorded point is
                            // something that was measured, and half way between
                            // two of them is not — and a waypoint standing
                            // where nothing was recorded cannot anchor the two
                            // halves of a stretch that has to stay recorded.
                            if (part.index) {
                                var onward = panel().metresBetween(near.lon, near.lat, part.lon[v], part.lat[v]);
                                var back = panel().metresBetween(near.lon, near.lat, part.lon[v + 1], part.lat[v + 1]);
                                best.trackAt = part.index.from + part.index.step * (onward <= back ? v : v + 1);
                            }
                        }
                    }
                }
                return best;
            }

            // What a waypoint is called, and where the file puts it. Where the
            // map already draws something named within reach — a hut, a quay, a
            // trailhead, a farm — the waypoint takes that thing's name, what it
            // is and **its position**, while the route itself stays on the
            // network: the file's track runs where a walker can walk and its
            // marker sits on the hut.
            //
            // Nearest wins rather than first, so two registers naming the same
            // hut a few metres apart cannot make the answer depend on the order
            // the layers were added in. Beyond reach the point keeps its own
            // position and is numbered, which is what it did before this
            // existed.
            function nameOf(point, index) {
                var best = null, closest = Infinity;
                for (var i = 0; i < NAMED.length; i += 1) {
                    var away = panel().metresBetween(point.lon, point.lat, NAMED[i].lon, NAMED[i].lat);
                    if (away < closest) { closest = away; best = NAMED[i]; }
                }
                // The stage mark rides along, because the writer is handed
                // this and not the point: a cut the reader made would otherwise
                // be in the plan and in no file it writes.
                var cut = typeof point.stage === 'string' ? point.stage : null;
                if (!best || closest > PLAN.namedM) {
                    return {lat: point.lat, lon: point.lon, name: null, kind: null,
                            away: null, number: index + 1, stage: cut};
                }
                return {lat: best.lat, lon: best.lon, name: best.name, kind: best.type,
                        away: closest, number: index + 1, stage: cut};
            }

            // ---- the control ------------------------------------------------------
            var toggle = document.createElement('button');
            toggle.type = 'button';
            toggle.style.cssText = 'font:inherit;font-size:12px;padding:2px 8px;cursor:pointer';
            var back = document.createElement('button');
            back.type = 'button';
            back.textContent = 'Take back the last point';
            back.style.cssText = 'font:inherit;font-size:12px;padding:2px 8px;margin-top:4px;cursor:pointer;display:block';
            var status = document.createElement('div');
            status.style.cssText = 'margin-top:4px;color:#555';

            // What can be done to the waypoint the reader has hold of, and only
            // while they have hold of one: a row of buttons that is always there
            // and usually does nothing is a row a reader stops reading. It is
            // also where reordering lives — dragging a pin moves it on the
            // ground and says nothing about where it comes in the sequence, so
            // the two need different gestures and only one of them can be a
            // drag.
            var edits = document.createElement('div');
            edits.style.cssText = 'margin-top:4px;display:none';
            var holding = document.createElement('div');
            holding.style.cssText = 'margin-bottom:2px;color:#333';
            var buttons = document.createElement('div');
            edits.appendChild(holding);
            edits.appendChild(buttons);

            function button(label, explains, act) {
                var made = document.createElement('button');
                made.type = 'button';
                made.textContent = label;
                made.title = explains;
                made.style.cssText = 'font:inherit;font-size:12px;padding:2px 6px;margin-right:4px;cursor:pointer';
                made.addEventListener('click', act);
                return made;
            }

            var earlier = button('\u25c0', 'Move this point one place earlier in the route',
                                 function () { moveBy(chosen, -1); });
            var later = button('\u25b6', 'Move this point one place later in the route',
                               function () { moveBy(chosen, 1); });
            var drop = button('Remove', 'Take this point out and join the two legs that met at it',
                              function () { remove(chosen); });
            buttons.appendChild(earlier);
            buttons.appendChild(later);
            buttons.appendChild(drop);

            // ---- the points, listed --------------------------------------
            // **A route is a sequence, and a map cannot show a sequence.** The
            // pins carry numbers, but reading eleven of them off a map to find
            // out that point 7 comes before point 8 is not reading, it is
            // searching. The list is the sequence itself: one row a point, in
            // order, with what it is called and how far into the walk it comes.
            //
            // It folds away behind the count, which was already saying "5
            // points" and is now the handle for the five. A second heading
            // saying the same number would be the two-panel mistake the legend
            // was just cured of.
            var listOpen = false, listStations = [], heldRow = null;

            // Which stage heading is being typed into, or null. The list is not
            // rebuilt while one is, for the reason it is not rebuilt while a row
            // is in the air.
            var namingRow = null;
            var listBox = document.createElement('div');
            // Named, like the picker and the mode beside it: its height is
            // computed now, so nothing can find it by the cap it used to carry.
            listBox.className = 'trails-plan-points';
            listBox.style.cssText = 'margin-top:4px;max-height:220px;overflow-y:auto;display:none';
            // The wheel is the map's except where this has somewhere left to
            // scroll, the same bargain the legend strikes: a list that will not
            // scroll is as useless as a map that will not zoom, and only one of
            // them can have any one turn.
            listBox.addEventListener('wheel', function (event) {
                var room = listBox.scrollHeight - listBox.clientHeight;
                if (room <= 0) { return; }
                if (event.deltaY < 0 ? listBox.scrollTop > 0 : listBox.scrollTop < room - 1) {
                    event.stopPropagation();
                }
            }, {passive: true});

            // **How much room there is above the profile panel.** That panel
            // is anchored to the foot of the map, takes its full width and is the
            // reader's own to drag taller; measured, twelve points with the
            // profile pulled to 725 px put 315 px of this control underneath it,
            // and the two corners share a z-index so whichever is written later
            // wins. Rather than fight over which covers which, this asks what is
            // left and stays inside it.
            function roomAbove() {
                if (!box) { return 0; }
                var mine = box.getBoundingClientRect().top;
                var below = map.getContainer().getBoundingClientRect().bottom;
                var profile = document.querySelector('.trails-profile-panel');
                if (profile) {
                    var seen = profile.getBoundingClientRect();
                    if (seen.height > 0) { below = Math.min(below, seen.top); }
                }
                // Eight, not twelve: the profile panel keeps 80 px of map
                // clear of itself, and this control's own floor plus its top
                // margin have to come out of that 80 or the two overlap at the
                // one place it matters — the panel dragged as tall as it goes.
                return Math.max(0, below - mine - 8);
            }

            function fitList() {
                if (!box) { return; }
                var room = roomAbove();
                // Everything but the list, and **off the scroll height** rather
                // than the offset: the box is capped below, so its offset height
                // is the cap and subtracting the list from that would measure the
                // cap instead of the buttons. The fixed part is measured rather
                // than assumed, because the buttons wrap differently in every
                // browser and the load status comes and goes.
                var fixed = box.scrollHeight - listBox.offsetHeight;
                // The floor is deliberate: under it the list is not worth showing
                // and the box's own overflow takes over. A scrollbar on the whole
                // control beats a control holding rows that cannot be reached.
                listBox.style.maxHeight = Math.max(40, Math.min(220, room - fixed)) + 'px';
                box.style.maxHeight = Math.max(40, room) + 'px';
            }

            function drawList(stations) {
                listStations = stations || [];
                // Never while a row is in the air. A leg settling mid-drag would
                // otherwise rebuild the rows under the pointer and the drop
                // would land on nothing.
                //
                // **And never under a name being typed**, which is the same rule
                // for the same reason and was missing: measured, typing a stage
                // name and letting a point settle rebuilt the heading and threw
                // the half-typed name away with it, with the caret going to the
                // document. A leg settles a few hundred milliseconds after a
                // click, which is well inside the time it takes to type a word.
                if (heldRow !== null || namingRow !== null) { return; }
                while (listBox.firstChild) { listBox.removeChild(listBox.firstChild); }
                // **A tour nobody has cut gets no headings.** One stage is the
                // whole route, and a heading over it would offer the same file
                // the button already offers, under a second name -- which is the
                // two-panel mistake the legend was cured of.
                //
                // **And only while the list is open.** Each heading composes its
                // own stage to state its kilometres and its climb, so building
                // them behind a shut box is a walk over the route per stage that
                // nobody is looking at: measured with two stages, a refresh cost
                // 9.65 ms shut against 10.20 open, which is to say shutting the
                // list saved almost nothing. During a drag that is eight of them
                // a second.
                var stages = (listOpen && points.length) ? stagesOf() : [];
                var heads = Object.create(null);
                if (stages.length > 1) {
                    stages.forEach(function (stage) { heads[stage.from] = stage; });
                }
                points.forEach(function (point, index) {
                    if (heads[index]) { listBox.appendChild(stageHead(heads[index])); }
                    var called = nameOf(point, index);
                    var row = document.createElement('div');
                    row.draggable = true;
                    row.style.cssText = 'display:flex;align-items:center;gap:6px;padding:2px 3px;' +
                        'border-radius:3px;cursor:pointer;' +
                        (index === chosen ? 'background:#e8eaf6' : '');
                    var grip = document.createElement('span');
                    grip.textContent = '\u2261';
                    grip.title = 'Drag to move this point in the route';
                    grip.style.cssText = 'cursor:grab;color:#9e9e9e;flex:none';
                    var number = document.createElement('span');
                    number.textContent = String(index + 1);
                    number.style.cssText = 'flex:none;min-width:14px;text-align:right;font-weight:600;color:' + ROUTE;
                    // What it is called where anything nearby is named, and its
                    // position where nothing is. A row that said only "3" would
                    // be the map's numbers again, in a column.
                    var says = document.createElement('span');
                    says.textContent = called.name
                        ? called.name
                        : point.lat.toFixed(4) + ', ' + point.lon.toFixed(4);
                    says.style.cssText = 'flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;' +
                        'white-space:nowrap;color:' + (called.name ? '#333' : '#777');
                    if (called.name) { says.title = called.name + (called.kind ? ' \u00b7 ' + called.kind : ''); }
                    // How far into the walk it comes, which is the one thing the
                    // profile beside it and the map above it both leave out.
                    var far = document.createElement('span');
                    far.style.cssText = 'flex:none;color:#777;font-variant-numeric:tabular-nums';
                    far.textContent = listStations.length > index
                        ? (listStations[index] / 1000).toFixed(2) + ' km' : '';
                    // **Where a stage ends**, on the point it ends at. Not
                    // offered on the first or the last: a tour ends where it
                    // ends and a mark there would make a stage of no legs.
                    var cut = document.createElement('button');
                    cut.type = 'button';
                    cut.className = 'trails-plan-cut';
                    cut.draggable = false;
                    var isCut = typeof point.stage === 'string';
                    var mayCut = index > 0 && index + 1 < points.length;
                    cut.textContent = '\u2014';
                    cut.title = isCut ? 'A stage ends here \u2014 click to join it to the next'
                        : 'End a stage here';
                    cut.style.cssText = 'flex:none;font:inherit;font-size:13px;line-height:1;padding:0 3px;' +
                        'border:0;background:none;cursor:pointer;visibility:' +
                        (mayCut ? 'visible' : 'hidden') + ';color:' + (isCut ? ROUTE : '#ccc');
                    cut.addEventListener('click', function (event) {
                        event.stopPropagation();
                        cutAt(index, !isCut);
                    });

                    // **Named, because a row now holds two buttons.** A check
                    // taking `row.querySelector('button')` got the cut where it
                    // meant the removal the moment a second one appeared — which
                    // is the same trap as aiming a click by position, one level
                    // up. Both are addressed by what they are.
                    var out = document.createElement('button');
                    out.type = 'button';
                    out.className = 'trails-plan-out';
                    out.draggable = false;
                    out.textContent = '\u00d7';
                    out.title = 'Take this point out and join the two legs that met at it';
                    out.style.cssText = 'flex:none;font:inherit;font-size:13px;line-height:1;padding:0 4px;' +
                        'border:0;background:none;color:#777;cursor:pointer';
                    out.addEventListener('click', function (event) {
                        // Or the row's own click would take hold of the point
                        // this one is removing.
                        event.stopPropagation();
                        remove(index);
                    });
                    row.addEventListener('click', function () {
                        chosen = chosen === index ? -1 : index;
                        refresh();
                    });
                    row.addEventListener('dragstart', function (event) {
                        heldRow = index;
                        event.dataTransfer.effectAllowed = 'move';
                        // Firefox starts no drag at all without something in the
                        // transfer, whatever the handlers say.
                        event.dataTransfer.setData('text/plain', String(index));
                        row.style.opacity = '0.4';
                    });
                    row.addEventListener('dragover', function (event) {
                        if (heldRow === null || heldRow === index) { return; }
                        event.preventDefault();
                        event.dataTransfer.dropEffect = 'move';
                        // An inset rather than a border, which would move every
                        // row below it by two pixels as the pointer passes.
                        row.style.boxShadow = 'inset 0 ' + (index < heldRow ? '2px' : '-2px') + ' 0 ' + ROUTE;
                    });
                    row.addEventListener('dragleave', function () { row.style.boxShadow = ''; });
                    row.addEventListener('drop', function (event) {
                        event.preventDefault();
                        row.style.boxShadow = '';
                        var from = heldRow;
                        heldRow = null;
                        if (from !== null && from !== index) { moveTo(from, index); }
                    });
                    row.addEventListener('dragend', function () {
                        heldRow = null;
                        row.style.opacity = '';
                        row.style.boxShadow = '';
                    });
                    row.appendChild(grip);
                    row.appendChild(number);
                    row.appendChild(says);
                    row.appendChild(far);
                    row.appendChild(cut);
                    row.appendChild(out);
                    listBox.appendChild(row);
                });
            }

            // The heading over a stage: what it is called, what it comes to, and
            // its own file. **Its figures are composed and never sliced** -- an
            // ascent is not the difference of two ascents -- so this is the same
            // walk the whole tour uses, narrowed to the legs of this stage.
            function stageHead(stage) {
                var shape = composeRoute(stage.from, stage.to);
                var figure = figuresOf(shape);
                var head = document.createElement('div');
                head.className = 'trails-plan-stage';
                head.style.cssText = 'display:flex;align-items:center;gap:6px;margin-top:4px;' +
                    'padding:2px 3px;border-top:1px solid #ddd;color:#555';

                // The name, and the two points it runs between where nobody has
                // given it one. A placeholder rather than a value, so that a
                // stage nobody named writes its own numbers and a stage somebody
                // named keeps the name through every edit that does not move it.
                var called = document.createElement('input');
                called.type = 'text';
                called.className = 'trails-plan-stage-name';
                called.value = stage.name || '';
                called.placeholder = stageName(stage);
                called.title = 'What this stage is called in its own file';
                called.style.cssText = 'flex:1 1 auto;min-width:0;font:inherit;font-size:12px;' +
                    'padding:1px 3px;border:1px solid transparent;background:none;color:#333';
                called.addEventListener('focus', function () {
                    called.style.borderColor = '#bbb';
                    namingRow = stage.at;
                });
                called.addEventListener('blur', function () {
                    called.style.borderColor = 'transparent';
                    namingRow = null;
                    nameStage(stage.to, called.value);
                });
                // Leaflet binds its own shortcuts to the container, so a typed
                // '+' would zoom the map mid-word.
                L.DomEvent.on(called, 'keydown keypress keyup', L.DomEvent.stopPropagation);

                var says = document.createElement('span');
                says.style.cssText = 'flex:none;font-variant-numeric:tabular-nums';
                says.textContent = (shape.total / 1000).toFixed(2) + ' km' +
                    (shape.read && isFinite(figure.ascent) ? ' \u00b7 \u2191' + Math.round(figure.ascent) + ' m' : '');

                var file = document.createElement('button');
                file.type = 'button';
                file.className = 'trails-plan-stage-file';
                file.textContent = 'GPX';
                file.title = 'Download this stage on its own';
                file.style.cssText = 'flex:none;font:inherit;font-size:11px;padding:1px 6px;cursor:pointer;' +
                    'display:' + ((panel() && panel().writes()) ? 'inline-block' : 'none');
                // Refused while any leg of the route is unsettled, for the
                // reason the whole tour's is: a file that states it breaks its
                // track only at crossings must not be written over a hole.
                file.disabled = !!writable().why;
                file.addEventListener('click', function (event) {
                    event.stopPropagation();
                    try {
                        saveStage(stage);
                    } catch (failure) {
                        fileFailed(failure);
                    }
                });

                head.appendChild(called);
                head.appendChild(says);
                head.appendChild(file);
                return head;
            }

            // **What the tour is called**, above the list because that is what
            // the list is a list of. A placeholder rather than a value where
            // nobody has typed one: a tour with no name of its own writes the
            // one every file carries by default, and showing that as a value
            // would turn a default into a choice the moment anything is saved.
            var titleRow = document.createElement('div');
            titleRow.style.cssText = 'margin-top:4px';
            var title = document.createElement('input');
            title.type = 'text';
            title.className = 'trails-plan-title';
            title.title = 'What this tour is called, in its files and in their names';
            title.style.cssText = 'width:100%;box-sizing:border-box;font:inherit;font-size:12px;' +
                'padding:1px 3px;border:1px solid #ddd;border-radius:3px;background:none;color:#333';
            title.addEventListener('blur', function () {
                tourName = title.value.trim();
                refresh();
            });
            // Leaflet binds its own shortcuts to the container, so a typed '+'
            // would zoom the map mid-word.
            L.DomEvent.on(title, 'keydown keypress keyup', L.DomEvent.stopPropagation);
            // Offered only where there are stages to gather. With one stage it
            // would hand over the same file the button already offers, twice,
            // under two names.
            var everything = document.createElement('button');
            everything.type = 'button';
            everything.className = 'trails-plan-zip';
            everything.textContent = 'All stages (zip)';
            everything.title = 'Every stage on its own, and the whole tour with its stages, in one archive';
            everything.style.cssText = 'margin-top:4px;font:inherit;font-size:11px;padding:1px 6px;cursor:pointer';
            everything.addEventListener('click', function () {
                try {
                    saveStages();
                } catch (failure) {
                    fileFailed(failure);
                }
            });

            titleRow.appendChild(title);
            titleRow.appendChild(everything);

            // Said rather than discovered. Three gestures share one click here
            // and none of them is guessable from a map that has never had more
            // than one.
            var hint = document.createElement('div');
            hint.style.cssText = 'margin-top:2px;color:#777;max-width:16em';
            hint.textContent = 'Drag a point to move it \u00b7 click one to work on it \u00b7 ' +
                'click the route to put one in \u00b7 click the count for the list';

            // What the last load turned out to be, or what went wrong with it.
            var loadSaid = '';

            // ---- the file control ---------------------------------------------------
            // **A page served from the disk may read a file the reader picks**,
            // and that single fact is what this phase rests on. Checked before
            // any of it was built: <input type="file"> plus FileReader returned
            // all 1,197,976 bytes of a chain export and DOMParser found its
            // trackpoints. Nothing else here would have mattered if it had
            // failed.
            //
            // The input is hidden behind a button of its own rather than shown:
            // a bare file input is a browser widget in the middle of a control
            // that is otherwise this map's, and it cannot be made to say what it
            // does. Hidden is not unreachable — it is still an input and still
            // takes a file from a driven check.
            var picker = document.createElement('input');
            picker.type = 'file';
            picker.accept = '.gpx,application/gpx+xml,application/xml,text/xml';
            picker.style.display = 'none';
            picker.className = 'trails-plan-file';

            var chooser = document.createElement('button');
            chooser.type = 'button';
            chooser.textContent = 'Load a GPX';
            chooser.title = 'Read a route or a recorded track back in and carry on from it';
            chooser.style.cssText = 'font:inherit;font-size:12px;padding:2px 8px;cursor:pointer';

            var modes = document.createElement('select');
            modes.className = 'trails-plan-mode';
            modes.style.cssText = 'font:inherit;font-size:12px;margin-left:4px;max-width:12em';
            MODES.forEach(function (mode) {
                var option = document.createElement('option');
                option.value = mode.key;
                option.textContent = mode.label;
                modes.appendChild(option);
            });

            var loading = document.createElement('div');
            loading.style.cssText = 'margin-top:4px';
            loading.appendChild(chooser);
            loading.appendChild(picker);

            // ---- the question ------------------------------------------------------
            // Shown between the file being read and anything being done with
            // it, and it is the only moment at which the plan on the map still
            // exists: taking a file replaces it and there is no way back, since
            // undo takes a point off the end and a load has no history. So this
            // is where the loss is said, and it is said as a count rather than
            // as a warning about files in general.
            var offerBox = document.createElement('div');
            offerBox.className = 'trails-plan-offer';
            offerBox.style.cssText = 'margin-top:4px;padding-top:4px;border-top:1px solid #ddd;max-width:22em';

            var offerSaid = document.createElement('div');
            offerSaid.style.cssText = 'color:#555';

            var offerRow = document.createElement('div');
            offerRow.style.cssText = 'margin-top:4px';
            var offerAsks = document.createElement('span');
            offerAsks.textContent = 'Read it as';
            offerRow.appendChild(offerAsks);
            offerRow.appendChild(modes);

            // What the chosen mode would do *to this file*, under the selector
            // rather than inside it: an option list is where a name goes and a
            // sentence does not fit in one.
            var offerMeans = document.createElement('div');
            offerMeans.style.cssText = 'margin-top:4px';

            var offerCosts = document.createElement('div');
            offerCosts.style.cssText = 'margin-top:4px;color:#8a5000';

            var offerButtons = document.createElement('div');
            offerButtons.style.cssText = 'margin-top:4px';
            var take = document.createElement('button');
            take.type = 'button';
            take.className = 'trails-plan-take';
            take.textContent = 'Load it';
            take.style.cssText = 'font:inherit;font-size:12px;padding:2px 8px;margin-right:6px;cursor:pointer';
            var drop = document.createElement('button');
            drop.type = 'button';
            drop.className = 'trails-plan-drop';
            drop.textContent = 'Cancel';
            drop.style.cssText = 'font:inherit;font-size:12px;padding:2px 8px;cursor:pointer';
            offerButtons.appendChild(take);
            offerButtons.appendChild(drop);

            offerBox.appendChild(offerSaid);
            offerBox.appendChild(offerRow);
            offerBox.appendChild(offerMeans);
            offerBox.appendChild(offerCosts);
            offerBox.appendChild(offerButtons);

            modes.addEventListener('change', function () {
                if (!pendingFile) { return; }
                pendingFile.mode = modes.value;
                refresh();
            });

            take.addEventListener('click', function () {
                if (!pendingFile) { return; }
                var ready = pendingFile;
                try {
                    takeGpx(ready.read, ready.mode);
                } catch (failure) {
                    // The same rule the read already follows: what is on the map
                    // stays. A mode that threw has not replaced anything, and
                    // the offer is dropped rather than left standing over a file
                    // that cannot be taken the way it was asked for.
                    pendingFile = null;
                    loadSaid = 'That file could not be loaded: ' +
                        (failure && failure.message ? failure.message : String(failure));
                    refresh();
                }
            });

            drop.addEventListener('click', function () { dismissFile(); });

            var loadStatus = document.createElement('div');
            loadStatus.style.cssText = 'margin-top:4px;color:#555;max-width:22em';

            chooser.addEventListener('click', function () { picker.click(); });

            picker.addEventListener('change', function () {
                var file = picker.files && picker.files[0];
                if (!file) { return; }
                var reader = new FileReader();
                // **Two handlers and not one catch over both.** The wait for the
                // disk and the work on what came back fail for different reasons
                // and a handler spanning them blames the wait: the panel spent
                // two runs looking for a payload that had arrived perfectly well
                // because a fault while drawing it was reported as one.
                reader.onerror = function () {
                    loadSaid = 'That file could not be read off the disk.';
                    picker.value = '';
                    refresh();
                };
                reader.onload = function () {
                    try {
                        // Read and described, not taken: the mode is asked for
                        // once there is something to ask it about.
                        offerFile(String(reader.result), file.name);
                    } catch (failure) {
                        // **What was already on the map stays.** `readGpx`
                        // refuses before anything is touched, so the recording
                        // that is loaded is still the one every waypoint is
                        // anchored to — and dropping it here would leave those
                        // anchors pointing at nothing, so the next edit would
                        // quietly turn a recorded stretch into a straight line.
                        loadSaid = 'That file could not be loaded: ' +
                            (failure && failure.message ? failure.message : String(failure));
                        refresh();
                    }
                    // Cleared, or picking the same file twice is not a change
                    // and the second pick does nothing at all.
                    picker.value = '';
                };
                reader.readAsText(file);
            });

            var control = L.control({position: 'topright'});
            var box = null;
            control.onAdd = function () {
                box = L.DomUtil.create('div', 'trails-plan-control');
                box.style.cssText = 'background:rgba(255,255,255,0.94);padding:6px 8px;border:1px solid #999;' +
                    'border-radius:4px;font-family:sans-serif;font-size:12px;line-height:1.4';
                box.appendChild(toggle);
                // Loading is how a plan starts from a file, so it is offered
                // whether or not plan mode is already on — and switching it on
                // is what loading does.
                //
                // **The mode is asked after the file has been read, not before
                // it.** It stood beside the button for as long as the answer was
                // thought to be a decision about the file rather than about what
                // is in it; it is not. Three mode names had to be true of a
                // planned route and of somebody's GPS recording at once, and a
                // reader picking the first of them lost the points their route
                // was planned with, with the page naming the number it was about
                // to discard. Asked here, the question can say what this file
                // turned out to be, what each answer would do to it, and what
                // taking it costs.
                box.appendChild(loading);
                box.appendChild(offerBox);
                box.appendChild(loadStatus);
                box.appendChild(back);
                box.appendChild(edits);
                box.appendChild(status);
                box.appendChild(titleRow);
                box.appendChild(listBox);
                box.style.overflowY = 'auto';
                // The wheel is the map's except where this has somewhere left to
                // scroll, the same bargain the legend and the list strike. The
                // list's own handler runs first and takes the turn while it can,
                // so the two nest rather than fight.
                box.addEventListener('wheel', function (event) {
                    var spare = box.scrollHeight - box.clientHeight;
                    if (spare <= 0) { return; }
                    if (event.deltaY < 0 ? box.scrollTop > 0 : box.scrollTop < spare - 1) {
                        event.stopPropagation();
                    }
                }, {passive: true});
                box.appendChild(hint);
                // Clicking inside the control must not reach the map, and the
                // wheel must, or the map reads as frozen under it.
                L.DomEvent.disableClickPropagation(box);
                return box;
            };
            control.addTo(map);

            // Leaflet appends to a top corner, and this one is reached for
            // before anything else in it, so it goes to the front. It had the
            // layer control for company here until the legend took that job over
            // and the corner emptied.
            var corner = control.getContainer().parentNode;
            corner.insertBefore(control.getContainer(), corner.firstChild);

            // The profile panel's height is a reader's to drag, and nothing
            // announces that. Watching the element is the one way to hear about
            // it that does not reach into the other control's own state.
            map.on('resize', fitList);
            if (typeof ResizeObserver !== 'undefined') {
                var watched = document.querySelector('.trails-profile-panel');
                if (watched) { new ResizeObserver(fitList).observe(watched); }
            }
            fitList();

            function say(message) {
                status.textContent = message;
            }

            function refresh() {
                toggle.textContent = on ? 'Stop planning' : 'Plan a route';
                back.style.display = on ? 'block' : 'none';
                back.disabled = !points.length;
                var holds = on && chosen >= 0 && chosen < points.length;
                edits.style.display = holds ? 'block' : 'none';
                if (holds) {
                    holding.textContent = 'Point ' + (chosen + 1) + ' of ' + points.length;
                    earlier.disabled = chosen === 0;
                    later.disabled = chosen === points.length - 1;
                }
                status.style.display = on ? '' : 'none';
                hint.style.display = on ? '' : 'none';
                // The count is the list's handle. It was already naming what the
                // list holds, and a second heading saying the same number is the
                // two-panel mistake the legend was cured of.
                var listable = on && points.length > 0;
                status.style.cursor = listable ? 'pointer' : '';
                status.title = listable ? 'Show or hide the points, one to a row' : '';
                listBox.style.display = (listable && listOpen) ? '' : 'none';
                // The title folds with the list: it names what the list holds,
                // and a box asking for a name over a route nobody has opened is
                // a row of the control spent on nothing.
                titleRow.style.display = (listable && listOpen) ? '' : 'none';
                if (document.activeElement !== title) {
                    title.value = tourName;
                    title.placeholder = (panel() && panel().routeName()) || 'This tour';
                }
                // Offered only where there is more than one stage to gather and
                // where the panel can write a file at all.
                var writes = !!(panel() && panel().writes());
                var gathered = writes && listOpen && stagesOf().length > 1;
                everything.style.display = gathered ? '' : 'none';
                everything.disabled = !!writable().why;
                if (on) {
                    say((listable ? (listOpen ? '\\u25be ' : '\\u25b8 ') : '')
                        + (points.length === 0 ? 'Click the map to place the first point.'
                           : points.length + (points.length === 1 ? ' point' : ' points') + (settling ? ' \\u00b7 working\\u2026' : '')));
                }
                // What the last load turned out to be, and what it cost once
                // every leg of it has settled. **Stamped here rather than where
                // the file was read**: the legs settle a microtask or more after
                // the load returns, so a figure taken at the end of loadGpx
                // would time the parsing and call it the load.
                if (loaded && loaded.settleMs === null && !settling) {
                    loaded.settleMs = performance.now() - loaded.began;
                    // Said here for the same reason the figure is: the route is
                    // only comparable with the file once every leg of it has
                    // settled, and before that the two disagree about ground
                    // that is still being worked out.
                    loadSaid += drifted();
                    // And shown, for the same reason again: a route half worked
                    // out has half a shape, and fitting the map to it would
                    // leave the reader looking at the wrong window.
                    if (fitWanted) { fitWanted = false; showRoute(); }
                }
                loadStatus.textContent = loadSaid;
                loadStatus.style.display = loadSaid ? '' : 'none';
                // The question, wherever one stands. **Its wording comes out of
                // the one table** rather than being assembled here: the sentence
                // under the selector and the mode it describes are one decision,
                // and writing either of them twice is how the two come apart.
                offerBox.style.display = pendingFile ? '' : 'none';
                if (pendingFile) {
                    offerSaid.textContent = pendingFile.name + ' \u2014 ' + describeFile(pendingFile.read);
                    modes.value = pendingFile.mode;
                    offerMeans.textContent = READINGS[pendingFile.kind][pendingFile.mode];
                    // Said as a count and only where there is something to lose.
                    // 'This replaces your plan' over an empty map is a warning
                    // about nothing, and a reader who is warned about nothing
                    // stops reading warnings.
                    offerCosts.textContent = points.length
                        ? 'This replaces the ' + points.length +
                          (points.length === 1 ? ' point' : ' points') + ' on the map. There is no way back.'
                        : '';
                    offerCosts.style.display = points.length ? '' : 'none';
                }
                // The pins say which point is which and which one is held, and
                // both change with every edit. Applied here as differences, so
                // that a refresh in the middle of a drag writes nothing.
                dressPins();
                present();
                // Last, because everything above it can change how tall this is.
                fitList();
            }

            // What only this side knows and the file cannot be written without:
            // where the reader put its points down, what each leg is made of,
            // and whether there is a hole in the route.
            //
            // **A hole refuses the file rather than being written into it.** The
            // file says it breaks its track only at crossings, and a leg still
            // being worked out or one the height service refused would break it
            // somewhere else with nothing in the file to say so.
            function writable() {
                var outstanding = unsettled(), waiting = outstanding.waiting, refused = outstanding.refused.length;
                return {
                    why: points.length < 2 ? 'Place a second point and there is a route to write.'
                        : waiting ? 'Still working out ' + waiting + (waiting === 1 ? ' leg.' : ' legs.')
                        : refused ? refused + (refused === 1 ? ' leg has' : ' legs have') +
                            ' no way and no heights, so the route has a gap that is not a crossing.'
                        : '',
                    name: tourName || null,
                    waypoints: points.map(nameOf),
                    legs: legs.map(function (leg) {
                        return (leg.parts || []).map(function (part) { return {kind: part.kind, length: part.length}; });
                    })
                };
            }

            // What the panel is shown. The route's series is composed here and
            // handed over; the panel draws the curve, the bands, the crosshair
            // and the reduction exactly as it does for a chain, and writes the
            // file from the same series it drew.
            function present() {
                var showing = panel();
                if (!points.length) {
                    // The list is drawn from the same walk the panel is fed, and
                    // for the same reason the panel is: how far along a point
                    // comes is the walk's answer, not a sum of the legs'.
                    drawList([]);
                    if (showing) { showing.series(null); }
                    return;
                }
                var shape = composeRoute();
                drawList(shape.stations || []);
                if (!showing) { return; }
                showing.series({label: 'planned route', figure: figuresOf(shape), shape: shape,
                                told: told(shape), plan: writable(),
                                // Which of the marks below the curve are where a
                                // stage changes hands. The panel draws the
                                // points; only the plan knows what they mean.
                                stages: cutsOf()});
            }

            function switchTo(want) {
                if (want === on) { return; }
                on = want;
                toggle.setAttribute('aria-pressed', on ? 'true' : 'false');
                var showing = panel();
                // While plan mode is on the map's clicks are its own, so the
                // panel stops answering them; the route is left drawn either
                // way, because switching off to look at something is not
                // throwing a plan away.
                if (showing) { showing.suspend(on); }
                // And the click-highlight lets go, for a harder reason than
                // tidiness: its only two ways out are a click on the line and a
                // click on empty ground, and from here on this handler owns
                // both. Left standing it would dim every line on the map for as
                // long as plan mode is on, with nothing a reader could do about
                // it. Not restored on the way out — it was a selection made by
                // clicking, and it is given up by planning.
                if (on && window.trailsHighlight) { window.trailsHighlight.clear(); }
                // Warmed here rather than at the first drag: a drag settles
                // inside a pointer event and cannot wait a microtask for a
                // payload that has been in the page since it loaded. Quietly,
                // because switching plan mode on is not yet a request to route
                // anything, and a page without a graph says so at the click.
                if (on && !held && window.trailsGraph) {
                    window.trailsGraph.ready.then(function (graph) { held = graph; }, function () { held = null; });
                }
                refresh();
            }

            status.addEventListener('click', function () {
                if (!on || !points.length) { return; }
                listOpen = !listOpen;
                refresh();
            });

            toggle.addEventListener('click', function () { switchTo(!on); });
            back.addEventListener('click', undo);

            // ---- the clicks --------------------------------------------------------
            // One handler for every click on the map, whatever it lands on.
            // Leaflet fires a layer's click for a line and the map's click only
            // for empty ground, so listening to either alone would miss half the
            // map — and a click reaching a line would open its popup as well.
            // Taken in the capture phase on the container and stopped there:
            // Leaflet's own listener sits on the same element in the bubble
            // phase and never runs.
            var pressed = null;
            var container = map.getContainer();

            // Whether a click landed on something that is not the ground.
            //
            // **A popup is not in the control container.** It lives in a pane
            // inside the map, so a handler that only steps around the controls
            // walks straight over it: measured, clicking the close button of a
            // chain's popup placed a waypoint behind it and left the popup open.
            // Everything inside a popup is the same case — a link, a name, the
            // text a reader is trying to select — because a popup is something
            // to read and not terrain to plan over.
            function overFurniture(event) {
                if (!event.target || !event.target.closest) { return false; }
                return !!event.target.closest('.leaflet-control-container, .leaflet-popup');
            }

            container.addEventListener('mousedown', function (event) {
                pressed = {x: event.clientX, y: event.clientY};
            }, true);

            container.addEventListener('click', function (event) {
                if (!on || overFurniture(event)) { return; }
                // A pan ends in a click too. Leaflet drops that one for its own
                // listeners; this one is not Leaflet's, so how far the pointer
                // travelled is what tells the two apart.
                if (pressed && Math.max(Math.abs(event.clientX - pressed.x), Math.abs(event.clientY - pressed.y)) > 3) { return; }
                event.stopPropagation();
                // **Three things one click can mean, and they are told apart
                // here because nothing else ever sees the click.** The handler
                // is on the container in the capture phase and stops it there,
                // so a pin's own Leaflet click would never run and a mode or a
                // modifier would be a second thing for a reader to hold in mind.
                //
                // A pin first, because a pin sits on the route and the route
                // runs under it; then the route itself, within a few pixels of
                // the line as drawn; and anything else is a point on the end,
                // which is what a click has meant here since plan mode existed.
                var element = event.target && event.target.closest
                    ? event.target.closest('.trails-plan-pin') : null;
                var at = element ? pinFor(element) : -1;
                if (at >= 0) {
                    // Clicking the one already held lets go of it, so there is a
                    // way out that is not an edit.
                    chosen = chosen === at ? -1 : at;
                    refresh();
                    return;
                }
                var where = map.mouseEventToLatLng(event);
                var hit = onRoute(where.lat, where.lng);
                if (hit) { insert(hit.leg + 1, hit.lat, hit.lon, hit.trackAt); return; }
                place(where.lat, where.lng);
            }, true);

            // Two clicks place two points, which the button takes back one at a
            // time; zooming as well would leave the reader somewhere else too.
            container.addEventListener('dblclick', function (event) {
                if (on && !overFurniture(event)) { event.stopPropagation(); }
            }, true);

            // What the plan is, and the entry a click uses, the way the graph
            // arrives as window.trailsGraph and the panel's selection as
            // window.trailsProfile: so a browser check can drive it and read it
            // rather than screenshot it.
            window.trailsPlan = {
                place: place,
                undo: undo,
                // Reading a file, which is the whole of phase 8's way in. It
                // takes the text rather than a File, so a browser check drives
                // exactly what the picker drives one step further on — the
                // FileReader is what turns one into the other and it was proved
                // before any of this was built.
                load: loadGpx,
                modes: MODES.map(function (mode) { return mode.key; }),
                // Reading a file without taking it, and the three steps the
                // picker drives: what it turned out to be and which mode is
                // offered first, then taking it or dropping it. A check reads
                // the answer rather than the screen, the way everything else on
                // this page is checked.
                offer: offerFile,
                take: function () {
                    if (!pendingFile) { throw new Error('no file is waiting to be taken'); }
                    takeGpx(pendingFile.read, pendingFile.mode);
                },
                choose: function (mode) {
                    if (!pendingFile) { throw new Error('no file is waiting to be taken'); }
                    if (!READINGS[pendingFile.kind][mode]) {
                        throw new Error(mode + ' is not one of ' +
                                        MODES.map(function (each) { return each.key; }).join(', '));
                    }
                    pendingFile.mode = mode;
                    refresh();
                },
                dismiss: dismissFile,
                readings: READINGS,
                // The four edits, each as the entry the gesture uses, so a
                // browser check can drive them and read what came out rather
                // than screenshot it. `dragTo` is what a drag does once the
                // pointer has been let go; that a waypoint can be dragged at all
                // is a thing only a real pointer over the icon proves, and the
                // check does both.
                insert: insert,
                remove: remove,
                moveTo: moveTo,
                moveBy: moveBy,
                dragTo: function (at, lat, lon) {
                    applyEdit(function (graph) {
                        if (at < 0 || at >= points.length) { return; }
                        // **A dragged waypoint is a new object on purpose** —
                        // that is what tells the legs beside it to rebuild — so
                        // anything the reader put on the old one has to be
                        // carried over by hand. Today that is the stage mark,
                        // and a mark lost by dragging a point would be lost
                        // silently, which is the worst way to lose one.
                        var was = points[at].stage;
                        points[at] = snapped(graph, lat, lon);
                        if (was !== undefined) { points[at].stage = was; }
                        chosen = at;
                    });
                },
                select: function (at) {
                    chosen = (at === null || at === undefined || at < 0 || at >= points.length) ? -1 : at;
                    refresh();
                },
                // Which leg a position falls on, and where along it — the same
                // answer the click uses to decide that it means an insertion.
                onRoute: onRoute,
                toggle: function (want) { switchTo(want === undefined ? !on : !!want); },
                state: function () {
                    var shape = composeRoute();
                    return {
                        on: on, working: settling > 0, chosen: chosen, dragging: !!dragging,
                        // A file read and not yet taken, with what it turned out
                        // to be and which mode is standing. Null while no
                        // question is on the screen, which is the same thing the
                        // control reads to decide whether to draw one.
                        pending: pendingFile === null ? null : {
                            name: pendingFile.name, kind: pendingFile.kind, mode: pendingFile.mode,
                            waypoints: pendingFile.read.waypoints.length,
                            legs: pendingFile.read.legs.length,
                            says: READINGS[pendingFile.kind][pendingFile.mode]
                        },
                        points: points.map(function (point) { return {lat: point.lat, lon: point.lon, node: point.node}; }),
                        legs: legs.map(function (leg) {
                            return {
                                settled: !!leg.parts, failed: leg.failed, provisional: leg.provisional,
                                parts: (leg.parts || []).map(function (part) {
                                    return {kind: part.kind, length: part.length, read: !!part.read,
                                            samples: part.height ? part.height.length : 0};
                                })
                            };
                        }),
                        walked: shape.total, crossings: shape.crossings, crossed: shape.crossed,
                        straight: shape.straight, read: shape.read, figure: figuresOf(shape),
                        // What the file states about the ground it covers, and
                        // the shape it is written from: a check can read these
                        // rather than parsing the file back, and then read the
                        // file to see that it says the same.
                        tally: shape.tally, stretches: shape.stretches.length,
                        vertices: shape.lon.length, samples: shape.height.length,
                        // Where each point the reader put down sits along the
                        // walk, which is what the profile marks them at.
                        stations: shape.stations,
                        writable: writable(),
                        // What was loaded and what it cost, so a check reads the
                        // figures rather than the status line they are written
                        // into. `index` is null until something asks for it,
                        // which is what says the index is built on demand and
                        // not at load.
                        loaded: loaded === null ? null : {
                            name: loaded.name, isRoute: loaded.isRoute, chain: loaded.chainId,
                            mode: loaded.mode, points: loaded.n, breaks: loaded.breaks,
                            waypoints: loaded.waypoints.length, generated: loaded.generated,
                            strange: loaded.strange,
                            legs: loaded.legs.length, unknown: loaded.unknown,
                            parseMs: loaded.parseMs, settleMs: loaded.settleMs,
                            said: loadSaid
                        },
                        index: gridded === null ? null : {
                            cellM: PLAN.indexCellM, buildMs: gridded.buildMs, entries: gridded.entries,
                            cells: gridded.cells, bytes: gridded.bytes
                        }
                    };
                }
            };

            // Plan mode lays its route out with the walk the profile panel
            // owns, so a page carrying one and not the other can plan nothing.
            // Said once, loudly, rather than thrown at the first click.
            if (panel()) {
                refresh();
            } else {
                console.error('plan mode: there is no profile panel in this page, so nothing can be planned');
                toggle.disabled = true;
                toggle.textContent = 'Plan a route';
                back.style.display = 'none';
                edits.style.display = 'none';
                hint.style.display = 'none';
                status.style.display = '';
                say('There is no profile panel in this page, so nothing can be planned.');
            }
        })();
        {% endmacro %}
    """)

    def __init__(self, plan: dict[str, Any], points: list[dict[str, object]]) -> None:
        """Initialize plan mode.

        Args:
            plan: What the page needs to route and to sample. See
                :func:`add_plan_mode`.
            points: The named things the map draws, as name, type and position
        """
        super().__init__()
        self._name = "PlanMode"
        # Through _script_json like everything else that lands inside a script
        # block: a service URL or a terrain name carrying a '<' would otherwise
        # close it, and json.dumps leaves that character alone.
        self.plan_json = _script_json(plan)
        # And these especially: every one of them is a name out of somebody
        # else's register, and one of them holding '</script>' would end the
        # page's whole script block.
        self.points_json = _script_json(points)


def add_plan_mode(fmap: folium.Map, plan: dict[str, Any], points: list[folium.FeatureGroup] | None = None) -> None:
    """Let a reader click a route together over the graph in the page.

    Switch it on and every click appends a waypoint, snapping to the network
    where one is within ``snapM`` and keeping the raw point beyond that. A
    waypoint can then be selected, removed, moved a place earlier or later in the
    sequence, dragged where it stands, or put into the middle of a leg by
    clicking the route; the route, its figures and its profile follow. The way
    from the point before is found with Dijkstra over the weighted graph — the
    cost of an edge is its length times its source's factor, both out of the
    payload's header, and a crossing costs the header's flat figure instead.
    Where no way exists the leg is drawn straight, its heights fetched from the
    height service on demand and cached by its two ends.

    **The four kinds of leg are parts of a leg, not legs.** A routed leg that
    takes a ferry is walked, then crossed, then walked; a straight leg over a
    strait splits at the shoreline into the same two things, and the samples are
    what split it. Walking and crossing are reported apart, always, and a
    crossing carries no profile at all.

    The route's profile goes to the panel :func:`add_profile_panel` put in the
    page, through the second way in that panel offers — so call this after both
    that and :func:`add_routing_graph`. The route is drawn into a pane of its
    own rather than the overlay pane, because what goes in there is counted among
    the map's paths for ever after. **A waypoint is a marker and does go into the
    marker pane**: a circle marker cannot be dragged — added to the map its
    ``dragging`` is undefined and ``draggable`` is ignored — so a five-point
    route costs five markers there and, drawing no path, gives eight back in its
    own pane.

    Args:
        fmap: Map holding the graph and the panel
        plan: What the page needs, none of it invented here.
            ``heightsUrl``, ``heightsCrs``, ``heightsBatch`` and
            ``heightsWorkers`` are the height service, the coordinates it is
            asked in, its own cap on points per request and the concurrency the
            build settled on; ``terrainModel`` and ``seaTerrain`` are the two
            answers that classify a sample — what makes it a ground height, and
            what makes it sea rather than ground; ``sampleStepM`` and
            ``ascentThresholdM`` are the build's own sampling step and ascent
            threshold, which a leg sampled on demand has to be read under or the
            two halves of one profile answer differently; ``snapM`` is how near
            a click has to land to be taken as a node; ``maxStraightM`` is how
            far a leg may be drawn straight before it is refused, which bounds
            what one misclick can ask of a public service; ``crossingKind`` and
            ``connectorKind`` are what the payload's header calls a crossing and
            an inferred connector, which the page tests every edge it routes over
            against — spelled in the page instead, a rename would leave it
            reading a ferry as walked ground; ``touchedM`` is how much of a
            route has to lie inside a protected area before it says so, and
            ``namedM`` how near a waypoint has to land to a named thing to be
            called after it. The names come from
            :mod:`trails.io.sources.hoydedata`, :mod:`trails.routing.elevation`,
            :mod:`trails.routing.protection` and :mod:`trails.routing.sources`.
        points: Feature groups whose named points a waypoint may be called
            after, from :func:`add_points` and :func:`add_labelled_points` given
            a ``point_type``. Without them a route's waypoints are numbered,
            which is what they were before this existed.

    Raises:
        ValueError: If ``plan`` leaves out something the page cannot route or
            sample without. A page that quietly sampled every 50 m, or read a
            climb at no threshold at all, would look exactly like one that did
            neither.
    """
    missing = sorted(set(PLAN_SETTINGS) - set(plan))
    if missing:
        raise ValueError(f"the page cannot plan a route without {', '.join(missing)}")
    absent = sorted(set(PLAN_GPX_SETTINGS) - set(plan.get("gpx") or {}))
    if absent:
        raise ValueError(f"the page cannot read a GPX back without gpx.{', gpx.'.join(absent)}")

    named: list[dict[str, object]] = []
    for group in points or []:
        named.extend(getattr(group, NAMED_POINTS_ATTR, []))
    _PlanMode(plan, named).add_to(fmap)


@dataclass(frozen=True)
class LegendRow:
    """One row of the legend, and the layer its checkbox switches.

    Attributes:
        label: The row's text. Written as text and never as markup, so a label
            holding ``<15 km`` stays a label rather than becoming a tag.
        colour: CSS colour of the swatch drawn before the label
        layer: The layer the checkbox adds to and removes from the map, or
            ``None`` for a row that only explains a colour
    """

    label: str
    colour: str
    layer: Any = None


class _Legend(MacroElement):
    """The legend, which is also the layer control.

    **One panel rather than two.** They said very nearly the same thing: of the
    30 rows the legend drew, 23 named a layer the control also listed, one named
    the same layer under a different name, and six were kinds inside a single
    layer. Two panels of the same list is two places to look and two places to
    drift, and measured on this map they cost a 297 x 557 box and a 441 x 737
    one for the privilege.

    So the legend keeps its colours and gains the checkbox, and folium's
    ``LayerControl`` goes. **What has to come with it is the part that control
    did quietly**: a layer added with ``show=False`` is on the map like any other
    until that control's template takes it off again. Without this the two layers
    this map starts with switched off would arrive switched on.

    A control rather than a box floating over the page, for the reason the search
    is one: a panel outside the map container swallows the wheel. It takes the
    wheel itself only where it has somewhere left to scroll, and lets it through
    to the map otherwise.
    """

    _template = Template("""
        {% macro script(this, kwargs) %}
        (function () {
            var map = {{ this._parent.get_name() }};
            var bases = [{{ this.base_names|join(', ') }}];
            var baseLabels = {{ this.base_labels_json }};
            var baseShown = {{ this.base_shown_json }};
            var layers = [{{ this.layer_names|join(', ') }}];
            var rows = {{ this.rows_json }};
            var title = {{ this.title_json }};
            var open = {{ 'false' if this.collapsed else 'true' }};

            var control = L.control({position: 'bottomleft'});
            control.onAdd = function () {
                var box = L.DomUtil.create('div');
                box.style.cssText = 'background:rgba(255,255,255,0.92);padding:8px 12px;border:1px solid #999;' +
                    'border-radius:4px;font-family:sans-serif;font-size:12px;line-height:1.4;' +
                    'max-height:70vh;overflow-y:auto';

                var header = document.createElement('div');
                header.style.cssText = 'font-weight:600;cursor:pointer;user-select:none';
                var body = document.createElement('div');

                // **Whichever base map was asked for, and only that one.**
                // Folium hands every base layer to the map and leaves it to the
                // layer control's template to take the unwanted ones off again;
                // with that control gone this does it, or two tile layers stack
                // and the last one drawn wins.
                var picked = document.createElement('div');
                picked.style.cssText = 'margin-bottom:6px;padding-bottom:6px;border-bottom:1px solid #ddd';
                bases.forEach(function (layer, index) {
                    if (!baseShown[index] && map.hasLayer(layer)) { map.removeLayer(layer); }
                    var line = document.createElement('label');
                    line.style.cssText = 'display:flex;align-items:center;gap:6px;margin:3px 0;cursor:pointer';
                    var pick = document.createElement('input');
                    pick.type = 'radio';
                    pick.name = 'trails-base-{{ this.get_name() }}';
                    pick.checked = map.hasLayer(layer);
                    pick.addEventListener('change', function () {
                        bases.forEach(function (other) {
                            if (other !== layer && map.hasLayer(other)) { map.removeLayer(other); }
                        });
                        if (!map.hasLayer(layer)) { map.addLayer(layer); }
                    });
                    var name = document.createElement('span');
                    name.textContent = baseLabels[index];
                    line.appendChild(pick);
                    line.appendChild(name);
                    picked.appendChild(line);
                });
                if (bases.length) { body.appendChild(picked); }

                // A row is a label where it switches something and a plain div
                // where it only explains a colour — but it keeps the checkbox's
                // width either way, or the two kinds of row would not line up.
                var drawn = [];
                rows.forEach(function (row, index) {
                    var layer = layers[index];
                    var line = document.createElement(layer ? 'label' : 'div');
                    line.style.cssText = 'display:flex;align-items:center;gap:6px;margin:3px 0' +
                        (layer ? ';cursor:pointer' : '');
                    var tick = null;
                    if (layer) {
                        if (!row.shown && map.hasLayer(layer)) { map.removeLayer(layer); }
                        tick = document.createElement('input');
                        tick.type = 'checkbox';
                        tick.style.cssText = 'flex:none;margin:0';
                        tick.checked = map.hasLayer(layer);
                        tick.addEventListener('change', function () {
                            if (tick.checked) { map.addLayer(layer); } else { map.removeLayer(layer); }
                            paint();
                        });
                        line.appendChild(tick);
                    } else {
                        var gap = document.createElement('span');
                        gap.style.cssText = 'display:inline-block;width:13px;flex:none';
                        line.appendChild(gap);
                    }
                    var swatch = document.createElement('span');
                    swatch.style.cssText = 'display:inline-block;width:18px;height:4px;flex:none;background:' + row.colour;
                    line.appendChild(swatch);
                    // As text. A label here routinely holds characters that
                    // would otherwise start a tag — the map's own read
                    // "Paths, approach ≤15 km" — and written as markup the
                    // whole row would vanish instead of saying so.
                    var name = document.createElement('span');
                    name.textContent = row.label;
                    line.appendChild(name);
                    body.appendChild(line);
                    drawn.push({line: line, layer: layer});
                });

                // A colour for something switched off is a colour for something
                // that is not on the map. The row stays — it is still the key to
                // that colour — but it says it is not speaking for the terrain.
                function paint() {
                    drawn.forEach(function (row) {
                        row.line.style.opacity = (row.layer && !map.hasLayer(row.layer)) ? '0.45' : '';
                    });
                }
                paint();

                function draw() {
                    header.textContent = (open ? '▾ ' : '▸ ') + title;
                    header.style.marginBottom = open ? '6px' : '0';
                    body.style.display = open ? '' : 'none';
                }
                header.addEventListener('click', function () { open = !open; draw(); });
                draw();

                box.appendChild(header);
                box.appendChild(body);
                L.DomEvent.disableClickPropagation(box);
                // The wheel is the map's, except where this box still has
                // somewhere to scroll in the direction it was turned. A list
                // this long that cannot be scrolled is as useless as a map that
                // will not zoom, and only one of the two can have any one turn.
                box.addEventListener('wheel', function (event) {
                    var room = box.scrollHeight - box.clientHeight;
                    if (room <= 0) { return; }
                    if (event.deltaY < 0 ? box.scrollTop > 0 : box.scrollTop < room - 1) {
                        event.stopPropagation();
                    }
                }, {passive: true});
                return box;
            };
            control.addTo(map);
        })();
        {% endmacro %}
    """)

    def __init__(self, title: str, rows: list[LegendRow], collapsed: bool) -> None:
        """Initialize the legend.

        Args:
            title: Legend heading, doubling as the fold handle
            rows: The rows, in the order they are drawn
            collapsed: Whether it starts folded away
        """
        super().__init__()
        self._name = "Legend"
        self.title_json = _script_json(title)
        self.collapsed = collapsed
        self.layer_names = [row.layer.get_name() if row.layer is not None else "null" for row in rows]
        self.rows_json = _script_json([{"label": row.label, "colour": row.colour, "shown": bool(getattr(row.layer, "show", True))} for row in rows])
        self.base_names: list[str] = []
        self.base_labels_json = "[]"
        self.base_shown_json = "[]"

    def render(self, **kwargs: Any) -> Any:
        """Collect the base layers, then render.

        They are whatever base layers the map holds when this renders, which is
        why the legend has to be added after them. Folium's own control walks the
        same children for the same reason.

        Args:
            **kwargs: Passed through to the parent

        Returns:
            Whatever branca's own render returns, which it does not document
        """
        labels: list[str] = []
        shown: list[bool] = []
        self.base_names = []
        for child in self._parent._children.values() if self._parent is not None else ():
            if isinstance(child, folium.TileLayer) and child.control and not child.overlay:
                self.base_names.append(child.get_name())
                labels.append(str(child.layer_name))
                shown.append(bool(child.show))
        self.base_labels_json = _script_json(labels)
        self.base_shown_json = _script_json(shown)
        return super().render(**kwargs)


def add_legend(fmap: folium.Map, title: str, entries: dict[str, str] | list[LegendRow], collapsed: bool = False) -> None:
    """Add the legend, which is also the map's layer control.

    Every row explains a colour, and a row given a layer also switches it. The
    base maps sit above them as radio buttons. **There is no separate layer
    control**: this replaces it, so nothing else may add one, and this has to be
    added after every layer it is to list.

    Enough sources make it tall enough to hide the terrain behind it, so it folds
    away at a click on its heading and scrolls within 70 % of the window.

    Args:
        fmap: Map to add the legend to
        title: Legend heading, which doubles as the fold handle
        entries: The rows in the order they are drawn. A mapping of label to
            colour gives a legend that only explains colours; a list of
            :class:`LegendRow` gives one that switches layers too.
        collapsed: Whether it starts folded away
    """
    rows = [LegendRow(label, colour) for label, colour in entries.items()] if isinstance(entries, dict) else list(entries)
    _Legend(title, rows, collapsed).add_to(fmap)
