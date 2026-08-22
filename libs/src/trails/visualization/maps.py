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
from enum import Enum
from html import escape
from typing import Any

import folium
import geopandas as gpd
import pandas as pd
from branca.element import MacroElement
from jinja2 import Template

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
        Folium map with base layers attached; call :func:`finalize` when done
        adding overlays.

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

#: Over how much ground a gradient is read, in metres. **Not between neighbouring
#: samples.** They are laid per edge and every edge gets at least two whatever
#: its length, so 2 % of the steps in this network are under a metre apart and
#: 3.4 % under two — and a decimetre of model noise divided by a third of a metre
#: is a cliff. Read step by step the worst reads **2,754 %**; over this window
#: nothing exceeds 100 %.
GRADIENT_WINDOW_M = 25.0

#: The least ground a gradient may be read over. Where a chain is too short for
#: the window, or a gap eats into it, what is left can be a couple of metres —
#: and no honest gradient comes out of that. Below this the stretch is left
#: uncoloured rather than called steep on the strength of two samples.
GRADIENT_MIN_RUN_M = 10.0

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
)

#: What ``waypoint`` holds, checked for the same reason as
#: :data:`EXPORT_ROUTE_SETTINGS`.
EXPORT_WAYPOINT_SETTINGS = ("name", "origin", "set")


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

    for column, text in (link_fields or {}).items():
        if column not in row:
            continue
        url = row[column]
        if pd.isna(url) or not str(url).startswith(_LINK_SCHEMES):
            continue
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
        popup_html = _build_popup(row, popup_fields or {}, link_fields, source) if (popup_fields or link_fields or source) else None

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

    Call after the layers have been added, and before :func:`finalize`.

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

    Call after the layers have been added, and before :func:`finalize`.

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
        show: Whether the layer starts visible

    Returns:
        The feature group that was added
    """
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    group = folium.FeatureGroup(name=f"{name} ({len(gdf)})", show=show)

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
        searchable: Whether :func:`add_search` can find these by their label
        show: Whether the layer starts visible

    Returns:
        The feature group that was added
    """
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    group = folium.FeatureGroup(name=f"{name} ({len(gdf)})", show=show)
    search_names: dict[str, str] = {}

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

    _record_search_names(group, search_names)
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
                    vertexAt: vertexAt, coordinates: coordinates,
                    sampleAt: sampleAt, heights: heights,
                    nodeLon: nodeLon, nodeLat: nodeLat,
                    nearestNode: nearestNode.bind(null, nodeLon, nodeLat)
                };
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
    map, or the map reads as frozen the moment the panel is open.

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

            // Where to put the arrow: half way along, by distance.
            function midpoint(shape) {
                if (!shape.along.length) { return null; }
                var half = shape.total / 2;
                for (var i = 1; i < shape.along.length; i += 1) {
                    if (shape.along[i] >= half) {
                        var span = shape.along[i] - shape.along[i - 1];
                        var t = span > 0 ? (half - shape.along[i - 1]) / span : 0;
                        return L.latLng(shape.lat[i - 1] + t * (shape.lat[i] - shape.lat[i - 1]),
                                        shape.lon[i - 1] + t * (shape.lon[i] - shape.lon[i - 1]));
                    }
                }
                return L.latLng(shape.lat[0], shape.lon[0]);
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

            function pointsIn(runs) {
                return runs.reduce(function (total, run) { return total + run.lon.length; }, 0);
            }

            function heightsWritten(runs) {
                return runs.some(function (run) { return run.ele.some(function (value) { return !isNaN(value); }); });
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
                return out.concat(heightsWritten(runs) ? EXPORT.heights : []);
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

            function fileNameOf(stem) {
                return (EXPORT.filePrefix + '-' + (stem || 'track')).replace(/[^A-Za-z0-9._-]+/g, '-') + '.gpx';
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
                out.push('    <desc>' + escaped(described + '. Sources: ' + credits.map(creditLine).join(' \\u00b7 ')) + '</desc>');
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
            function routeGpxOf(figure, shape, runs, plan, extra) {
                var credits = routeCredits(shape, runs);
                var told = planned(figure, shape, extra).concat([markingLine(shape.tally)]);
                var figures = routeFigures(figure, shape);

                var out = [];
                openGpx(out);
                metadataOf(out, EXPORT.route.name, EXPORT.route.description, credits);

                // After the metadata and before the track, which is where GPX
                // 1.1 puts a waypoint: it is a top-level element of its own and
                // **not** part of the extensions mechanism, and a file placing
                // it anywhere else parses and fails the schema.
                plan.waypoints.forEach(function (point, index) {
                    out.push('  <wpt lat="' + point.lat.toFixed(EXPORT.coordinateDecimals) +
                        '" lon="' + point.lon.toFixed(EXPORT.coordinateDecimals) + '">');
                    out.push('    <name>' + escaped(EXPORT.waypoint.name + ' ' + (index + 1)) + '</name>');
                    // Set or generated, on every one. Nothing generates a
                    // waypoint yet, and the field goes in before anything does:
                    // a reader loading this file back must never take a marker
                    // the map placed for a station somebody chose, and a file
                    // written before the field existed could only ever be
                    // matched afterwards, never restored.
                    out.push('    <extensions>');
                    out.push('      ' + element(EXPORT.waypoint.origin, EXPORT.waypoint.set));
                    out.push('    </extensions>');
                    out.push('  </wpt>');
                });

                out.push('  <trk>');
                out.push('    <name>' + escaped(EXPORT.route.name) + '</name>');
                out.push('    <desc>' + escaped(told.join(' \\u00b7 ')) + '</desc>');
                out.push('    <extensions>');
                out.push('      ' + element(EXPORT.route.kindField, EXPORT.route.kind));
                EXPORT.route.fields.forEach(function (pair) {
                    var value = figures[pair[0]];
                    if (value === null || value === undefined || isNaN(value)) { return; }
                    out.push('      ' + element(pair[1], fixed(value)));
                });
                if (heightsWritten(runs) && EXPORT.ascentMethod) {
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
                out.push('    </extensions>');
                segmentsOf(out, runs);
                out.push('  </trk>');
                out.push('</gpx>');
                return out.join('\\n') + '\\n';
            }

            function saveFile(name, body) {
                var blob = new Blob([body], {type: 'application/gpx+xml'});
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

            // ---- the panel -------------------------------------------------
            var header = document.createElement('div');
            header.style.cssText = 'font-weight:600;cursor:pointer;user-select:none';
            var body = document.createElement('div');
            var summary = document.createElement('div');
            summary.style.cssText = 'margin:4px 0 2px;color:#333';
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
            var offer = document.createElement('div');
            offer.style.cssText = 'margin:4px 0 2px;display:none';
            var download = document.createElement('button');
            download.type = 'button';
            download.textContent = 'Download GPX';
            download.style.cssText = 'font:inherit;font-size:12px;padding:2px 8px;margin-right:8px;cursor:pointer';
            var carries = document.createElement('span');
            carries.style.cssText = 'color:#333';
            var licensed = document.createElement('div');
            licensed.style.cssText = 'margin:2px 0 0;color:#666;font-size:11px';
            // What kind of ground the file covers, which only a route states:
            // its three marking buckets, and the length no source records a path
            // along. A chain leaves this row empty.
            var noted = document.createElement('div');
            noted.style.cssText = 'margin:2px 0 0;color:#666;font-size:11px';
            offer.appendChild(download);
            offer.appendChild(carries);
            offer.appendChild(licensed);
            offer.appendChild(noted);

            body.appendChild(summary);
            body.appendChild(offer);
            body.appendChild(key);
            body.appendChild(chart);

            var control = L.control({position: 'bottomleft'});
            var box = null;
            control.onAdd = function () {
                box = L.DomUtil.create('div', 'trails-profile-panel');
                box.style.cssText = 'background:rgba(255,255,255,0.94);padding:6px 10px;border:1px solid #999;' +
                    'border-radius:4px;font-family:sans-serif;font-size:12px;line-height:1.4;' +
                    // Clear of the attribution, which sits in the corner opposite
                    // and would otherwise be covered by a panel this wide.
                    'margin-bottom:22px';
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
                var named = open && selected && selected.label ? ' \\u00b7 ' + selected.label : '';
                header.textContent = (open ? '\\u25be ' : '\\u25b8 ') + title + named;
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
            // can be looked up in the full series.
            function drawPoints(shape, columns) {
                var runs = [], run = [], i;
                if (shape.height.length <= columns) {
                    // The common case, and it has to be: the median chain here
                    // holds 36 samples and a third of them fewer than twenty.
                    // Bucketing those into 900 columns leaves 864 empty and the
                    // curve full of holes it has no business having.
                    for (i = 0; i < shape.height.length; i += 1) {
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
                // is one subtraction rather than a scan.
                var missed = new Int32Array(shape.height.length + 1);
                for (i = 0; i < shape.height.length; i += 1) {
                    var value = shape.height[i];
                    missed[i + 1] = missed[i] + (isNaN(value) ? 1 : 0);
                    if (isNaN(value)) { continue; }
                    var column = Math.max(0, Math.min(columns - 1, Math.floor((shape.distance[i] / shape.total) * columns)));
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
                    var at = ((c + 0.5) / columns) * shape.total;
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

            function drawCurve(shape, plot, x, y, slope) {
                // One stroke per run of segments sharing a band, so the curve is
                // its own legend: where it turns amber the ground turned steep.
                // And per run sharing a *drawing*, so a stretch the plan drew
                // straight is dashed here as it is dashed on the map — the
                // profile has to say the same thing the map does about the same
                // ground.
                var strokes = [], current;
                drawPoints(shape, Math.max(1, Math.floor(plot.width))).forEach(function (points) {
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
                // Cleared before every early return below, so the row never
                // outlives the curve that explained it.
                freeKey.style.display = 'none';
                if (!open) { return; }

                var width = Math.max(240, body.clientWidth || (map.getSize().x - 40));
                chart.setAttribute('viewBox', '0 0 ' + width + ' ' + chartHeight);
                chart.setAttribute('width', width);
                if (!selected || !selected.shape || !selected.shape.read) { return; }

                var shape = selected.shape;
                if (!(shape.total > 0)) { return; }
                var plot = {left: PAD.left, right: width - PAD.right, top: PAD.top, bottom: chartHeight - PAD.bottom};
                plot.width = plot.right - plot.left;
                var lowest = Infinity, highest = -Infinity;
                for (var i = 0; i < shape.height.length; i += 1) {
                    if (isNaN(shape.height[i])) { continue; }
                    if (shape.height[i] < lowest) { lowest = shape.height[i]; }
                    if (shape.height[i] > highest) { highest = shape.height[i]; }
                }
                // A stretch of flat ground is flat ground, not a mountain: give
                // it a range of its own rather than letting the height model's
                // centimetre wobble fill the panel.
                if (highest - lowest < 20) {
                    var middle = (highest + lowest) / 2;
                    lowest = middle - 10; highest = middle + 10;
                }
                var x = function (value) { return plot.left + (shape.total > 0 ? (value / shape.total) * plot.width : 0); };
                var y = function (value) { return plot.bottom - ((value - lowest) / (highest - lowest)) * (plot.bottom - plot.top); };

                ticks(lowest, highest, 4).forEach(function (value) {
                    chart.appendChild(line(plot.left, y(value), plot.right, y(value), '#eceff1'));
                    chart.appendChild(text(plot.left - 6, y(value) + 3, metres(value) + ' m', 'end'));
                });
                // One number of decimals for the whole axis, decided by how far
                // the chain runs: 0.00 beside 1.0 reads as two different scales.
                var decimals = shape.total < 2000 ? 2 : 1;
                ticks(0, shape.total, 6).forEach(function (value) {
                    chart.appendChild(line(x(value), plot.top, x(value), plot.bottom, '#eceff1'));
                    chart.appendChild(text(x(value), plot.bottom + 14, (value / 1000).toFixed(decimals), 'middle'));
                });
                chart.appendChild(text(plot.right, plot.bottom + 14, 'km', 'end'));
                chart.appendChild(line(plot.left, plot.top, plot.left, plot.bottom, AXIS));
                chart.appendChild(line(plot.left, plot.bottom, plot.right, plot.bottom, AXIS));

                var slope = gradients(shape);
                var strokes = drawCurve(shape, plot, x, y, slope);
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
                    chart.appendChild(curve);
                });

                // The crosshair's own parts, made once and moved afterwards.
                // Rebuilding them per mouse move is the mistake that froze this
                // map twice already, on a layer rather than on a chart.
                var rule = line(plot.left, plot.top, plot.left, plot.bottom, CROSS);
                var dot = document.createElementNS(SVG, 'circle');
                dot.setAttribute('r', '2.5'); dot.setAttribute('fill', CROSS);
                var reading = text(plot.right, plot.top + 8, '', 'end');
                reading.setAttribute('fill', CROSS);
                [rule, dot, reading].forEach(function (node) { node.style.display = 'none'; chart.appendChild(node); });
                crosshair = {rule: rule, dot: dot, reading: reading, plot: plot, width: width, x: x, y: y, at: -1, slope: slope};
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
                if (!crosshair || !selected || !selected.shape) { return; }
                var shape = selected.shape;
                // The drawing is scaled to whatever width the panel ended up
                // with, so a pointer position has to go back through the
                // viewBox before it means anything in the chart's own units.
                var rect = chart.getBoundingClientRect();
                var px = ((event.clientX - rect.left) / rect.width) * crosshair.width;
                var at = nearest(shape.distance, ((px - crosshair.plot.left) / crosshair.plot.width) * shape.total);
                if (at === crosshair.at) { return; }
                crosshair.at = at;
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

            chart.addEventListener('mouseleave', function () {
                if (!crosshair) { return; }
                crosshair.at = -1;
                [crosshair.rule, crosshair.dot, crosshair.reading].forEach(function (node) { node.style.display = 'none'; });
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
                if (shape.read) { told.push('high ' + metres(figure.high) + ' m', 'low ' + metres(figure.low) + ' m'); }
                told = told.concat(extra || []);
                if (!shape.read) {
                    told.push(shape.total > 0 ? 'no height was read along it' : 'no ground under any of it');
                }
                return told;
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
                say(climb(figure) + ' \\u00b7 high ' + metres(figure.high) + ' m \\u00b7 low ' + metres(figure.low) +
                    ' m \\u00b7 ' + (shape.total / 1000).toFixed(2) + ' km' +
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
                offer.style.display = (selected && (!selected.composed || selected.plan)) ? '' : 'none';
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
                    carries.textContent = selected.plan.why ? selected.plan.why
                        : [points.toLocaleString('en-GB') + ' points'].concat(
                            planned(selected.figure, selected.shape, selected.told)).join(' \\u00b7 ');
                    licensed.textContent = routeCredits(selected.shape, selected.runs).map(licenceLine).join(' \\u00b7 ');
                    noted.textContent = markingLine(selected.shape.tally);
                    return;
                }
                download.disabled = points < 2;
                carries.textContent = [
                    points.toLocaleString('en-GB') + ' points',
                    heightsWritten(selected.runs) ? climb(selected.figure) : 'no height along this stretch',
                    (selected.figure.length / 1000).toFixed(2) + ' km',
                ].join(' \\u00b7 ');
                licensed.textContent = creditsOf(selected.figure, selected.runs).map(licenceLine).join(' \\u00b7 ');
            }

            if (EXPORT) {
                download.addEventListener('click', function () {
                    if (!selected || !selected.runs) { return; }
                    if (selected.composed) {
                        if (!selected.plan || selected.plan.why) { return; }
                        saveFile(fileNameOf(EXPORT.route.fileStem),
                                 routeGpxOf(selected.figure, selected.shape, selected.runs, selected.plan, selected.told));
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
                metresBetween: metresBetween
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
    chart_height: int = 150,
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
    """Plan mode: clicking a route together, leg by leg.

    Switch it on and every click appends a waypoint and works out the way from
    the one before, so a route grows as far as a reader cares to take it. Taking
    the last point back is the only edit there is; changing an existing sequence
    is a different problem and a later phase.

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
            var TALLIED = MARKING.concat(['undrawn', 'unrecorded']);

            function blankTally() {
                var out = {sources: Object.create(null)};
                TALLIED.forEach(function (field) { out[field] = 0; });
                return out;
            }

            function addTally(into, from) {
                if (!from) { return; }
                Object.keys(from.sources).forEach(function (name) {
                    into.sources[name] = (into.sources[name] || 0) + from.sources[name];
                });
                TALLIED.forEach(function (field) { into[field] += from[field]; });
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
            function straightTally(length) {
                var out = blankTally();
                out.unmarked = length;
                return out;
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
            function straightSamples(from, to) {
                var length = panel().metresBetween(from.lon, from.lat, to.lon, to.lat);
                // **Refused rather than quietly coarsened.** Sampling is fixed
                // at the build's step, so the only way to bound the work is to
                // bound the leg: at 5 m and fifty points a request, the width
                // of this map is some 180 requests to somebody else's service,
                // from one misclick out to sea. Coarsening instead would make
                // the two halves of a profile answer differently and nothing
                // would look wrong, so the leg says what it will not do.
                if (length > PLAN.maxStraightM) {
                    throw new Error((length / 1000).toFixed(1) + ' km is further than a leg may be drawn straight (' +
                                    (PLAN.maxStraightM / 1000).toFixed(1) + ' km)');
                }
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
            var asked = Object.create(null);

            function heightsFor(from, to) {
                var key = [from.lon, from.lat, to.lon, to.lat].map(function (value) { return value.toFixed(7); }).join(',');
                if (asked[key]) { return asked[key]; }
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
                var answering = inWaves(batches).then(function (points) { return {laid: laid, points: points}; });
                asked[key] = answering;
                // A refusal must not be remembered as one for ever: the next
                // click on the same ground should ask again.
                answering.catch(function () { if (asked[key] === answering) { delete asked[key]; } });
                return answering;
            }

            // The samples classify the ground and the split falls out of them:
            // where two neighbours disagree the shoreline lies between, and half
            // way between is as near as sampling every few metres can put it. No
            // coastline is consulted and none is needed.
            function straightParts(from, to, answered) {
                var laid = answered.laid, points = answered.points, count = points.length;
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
                                tally: straightTally(ended - began)});
                }
                return parts;
            }

            // A route that may only follow recorded ways is not a plan for this
            // park: 19.9 km of UT.no's own routes run where no source records
            // anything. So where the network cannot carry a leg it is drawn
            // straight rather than refused.
            function resolve(graph, from, to) {
                if (from.node >= 0 && to.node >= 0) {
                    var found = route(graph, from.node, to.node);
                    if (found) { return Promise.resolve(routedParts(graph, found)); }
                }
                return heightsFor(from, to).then(function (answered) { return straightParts(from, to, answered); });
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
            function composeRoute() {
                var lon = [], lat = [], along = [], height = [], distance = [], free = [];
                var stretches = [], stretch = null, tally = blankTally();
                var walked = 0, crossings = 0, crossed = 0, straight = 0, read = false, joined = false;

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

                legs.forEach(function (leg) {
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
                        joined = part.height.length > 0 && part.lon.length > 0;
                        walked += part.length;
                    });
                });
                close();
                return {lon: lon, lat: lat, along: along, height: height, distance: distance, free: free,
                        stretches: stretches, tally: tally, total: walked, read: read,
                        crossing: crossings > 0, crossings: crossings, crossed: crossed, straight: straight};
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
                    waiting: legs.filter(function (leg) { return !leg.parts && !leg.failed; }).length,
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
            // Nothing here is ever a click target. In plan mode a click places a
            // waypoint wherever it lands, and out of it the route must not stand
            // between a reader and the line underneath — the mistake the park
            // boundary made for a fortnight.
            pane.style.pointerEvents = 'none';

            function draw(parts) {
                var layers = [];
                parts.forEach(function (part) {
                    var corners = [];
                    for (var i = 0; i < part.lon.length; i += 1) { corners.push([part.lat[i], part.lon[i]]); }
                    if (corners.length < 2) { return; }
                    var colour = part.kind === 'waiting' ? WAITING : ROUTE;
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

            function pin(point) {
                return L.circleMarker([point.lat, point.lon], {
                    pane: 'trailsPlanRoute', radius: 5, weight: 2, color: ROUTE,
                    fillColor: CASING, fillOpacity: 1, interactive: false
                }).addTo(map);
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

            function addLeg(graph, from, to) {
                var leg = {from: from, to: to, parts: null, failed: null, layers: []};
                legs.push(leg);
                // Something on the map the instant the click lands, replaced when
                // the leg is worked out. **Only this leg is redrawn**, then and
                // later: rebuilding the route on every click is what froze this
                // map twice already, on a layer rather than on a route.
                leg.layers = draw(straightAcross(from, to));
                settling += 1;
                refresh();
                // Wrapped, so that a fault thrown on the way *into* the work
                // is a rejection like any other rather than an exception that
                // leaves the count of outstanding legs standing for ever.
                Promise.resolve().then(function () { return resolve(graph, from, to); }).then(function (parts) {
                    leg.parts = parts;
                }, function (failure) {
                    leg.failed = String(failure && failure.message ? failure.message : failure);
                // A third handler rather than a catch over the two above: a
                // fault while *drawing* is not a leg that could not be worked
                // out, and reporting it as one sends the next reader to the
                // wrong place. It belongs in the console, loudly.
                }).then(function () {
                    settling -= 1;
                    // The point may have been taken back while this was in
                    // flight, in which case the leg is off the route and nothing
                    // it has to say matters any more.
                    if (legs.indexOf(leg) < 0) { return; }
                    undraw(leg.layers);
                    leg.layers = draw(leg.parts || straightAcross(from, to));
                    refresh();
                });
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
                    try { run(graph); } finally { always(); }
                }, function () {
                    say('The routing graph did not arrive, so nothing can be routed.');
                    always();
                });
            }

            function place(lat, lon) {
                // Counted as outstanding from the click, not from the moment
                // the graph answers. A reader who has clicked is waiting, and a
                // state that reads 'nothing in hand' for the microtask in
                // between is one a check would believe.
                settling += 1;
                refresh();
                withGraph(function (graph) {
                    // Snapped to the network where there is any within reach, so
                    // a route can start from where the reader meant rather than
                    // from a metre beside it; beyond that the raw point stands
                    // and the leg is drawn straight.
                    var node = graph.nearestNode(lat, lon, PLAN.snapM);
                    var point = node >= 0
                        ? {lat: graph.nodeLat[node], lon: graph.nodeLon[node], node: node}
                        : {lat: lat, lon: lon, node: -1};
                    points.push(point);
                    pins.push(pin(point));
                    if (points.length > 1) { addLeg(graph, points[points.length - 2], point); }
                }, function () { settling -= 1; refresh(); });
            }

            // One misclick should not cost a route. Everything beyond taking the
            // last point back — moving one, inserting one, dropping one from the
            // middle — is a later phase.
            function undo() {
                if (!points.length) { return; }
                points.pop();
                undraw([pins.pop()]);
                var leg = legs.pop();
                if (leg) { undraw(leg.layers); }
                refresh();
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

            var control = L.control({position: 'topright'});
            var box = null;
            control.onAdd = function () {
                box = L.DomUtil.create('div', 'trails-plan-control');
                box.style.cssText = 'background:rgba(255,255,255,0.94);padding:6px 8px;border:1px solid #999;' +
                    'border-radius:4px;font-family:sans-serif;font-size:12px;line-height:1.4';
                box.appendChild(toggle);
                box.appendChild(back);
                box.appendChild(status);
                // Clicking inside the control must not reach the map, and the
                // wheel must, or the map reads as frozen under it.
                L.DomEvent.disableClickPropagation(box);
                return box;
            };
            control.addTo(map);

            // Leaflet appends to a top corner, and the layer control sharing
            // this one is expanded over twenty-five layers, so anything added
            // after it lands below the fold. Moved to the front of the corner
            // after addTo, the way a control that has to sit above the zoom
            // buttons is.
            var corner = control.getContainer().parentNode;
            corner.insertBefore(control.getContainer(), corner.firstChild);

            function say(message) {
                status.textContent = message;
            }

            function refresh() {
                toggle.textContent = on ? 'Stop planning' : 'Plan a route';
                back.style.display = on ? 'block' : 'none';
                back.disabled = !points.length;
                status.style.display = on ? '' : 'none';
                if (on) {
                    say(points.length === 0 ? 'Click the map to place the first point.'
                        : points.length + (points.length === 1 ? ' point' : ' points') + (settling ? ' \\u00b7 working\\u2026' : ''));
                }
                present();
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
                    waypoints: points.map(function (point) { return {lat: point.lat, lon: point.lon}; }),
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
                if (!showing) { return; }
                if (!points.length) { showing.series(null); return; }
                var shape = composeRoute();
                showing.series({label: 'planned route', figure: figuresOf(shape), shape: shape,
                                told: told(shape), plan: writable()});
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
                refresh();
            }

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

            function overControl(event) {
                return !!(event.target && event.target.closest && event.target.closest('.leaflet-control-container'));
            }

            container.addEventListener('mousedown', function (event) {
                pressed = {x: event.clientX, y: event.clientY};
            }, true);

            container.addEventListener('click', function (event) {
                if (!on || overControl(event)) { return; }
                // A pan ends in a click too. Leaflet drops that one for its own
                // listeners; this one is not Leaflet's, so how far the pointer
                // travelled is what tells the two apart.
                if (pressed && Math.max(Math.abs(event.clientX - pressed.x), Math.abs(event.clientY - pressed.y)) > 3) { return; }
                event.stopPropagation();
                var where = map.mouseEventToLatLng(event);
                place(where.lat, where.lng);
            }, true);

            // Two clicks place two points, which the button takes back one at a
            // time; zooming as well would leave the reader somewhere else too.
            container.addEventListener('dblclick', function (event) {
                if (on && !overControl(event)) { event.stopPropagation(); }
            }, true);

            // What the plan is, and the entry a click uses, the way the graph
            // arrives as window.trailsGraph and the panel's selection as
            // window.trailsProfile: so a browser check can drive it and read it
            // rather than screenshot it.
            window.trailsPlan = {
                place: place,
                undo: undo,
                toggle: function (want) { switchTo(want === undefined ? !on : !!want); },
                state: function () {
                    var shape = composeRoute();
                    return {
                        on: on, working: settling > 0,
                        points: points.map(function (point) { return {lat: point.lat, lon: point.lon, node: point.node}; }),
                        legs: legs.map(function (leg) {
                            return {
                                settled: !!leg.parts, failed: leg.failed,
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
                        writable: writable()
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
                status.style.display = '';
                say('There is no profile panel in this page, so nothing can be planned.');
            }
        })();
        {% endmacro %}
    """)

    def __init__(self, plan: dict[str, Any]) -> None:
        """Initialize plan mode.

        Args:
            plan: What the page needs to route and to sample. See
                :func:`add_plan_mode`.
        """
        super().__init__()
        self._name = "PlanMode"
        # Through _script_json like everything else that lands inside a script
        # block: a service URL or a terrain name carrying a '<' would otherwise
        # close it, and json.dumps leaves that character alone.
        self.plan_json = _script_json(plan)


def add_plan_mode(fmap: folium.Map, plan: dict[str, Any]) -> None:
    """Let a reader click a route together over the graph in the page.

    Switch it on and every click appends a waypoint, snapping to the network
    where one is within ``snapM`` and keeping the raw point beyond that. The way
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
    that and :func:`add_routing_graph`. Nothing is drawn into the overlay or
    marker panes: the route, its waypoints and everything else here live in a
    pane of their own, because what goes into either of those is counted among
    the map's markers and paths for ever after.

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
            reading a ferry as walked ground. The names come from
            :mod:`trails.io.sources.hoydedata`, :mod:`trails.routing.elevation`
            and :mod:`trails.routing.sources`.

    Raises:
        ValueError: If ``plan`` leaves out something the page cannot route or
            sample without. A page that quietly sampled every 50 m, or read a
            climb at no threshold at all, would look exactly like one that did
            neither.
    """
    missing = sorted(set(PLAN_SETTINGS) - set(plan))
    if missing:
        raise ValueError(f"the page cannot plan a route without {', '.join(missing)}")

    _PlanMode(plan).add_to(fmap)


class _Legend(MacroElement):
    """A legend that can be folded away.

    A control rather than a box floating over the page, for the same reason the
    search is one: a panel outside the map container swallows the wheel, and
    with two dozen entries this one covers a good part of the map.
    """

    _template = Template("""
        {% macro script(this, kwargs) %}
        (function () {
            var control = L.control({position: 'bottomleft'});
            control.onAdd = function () {
                var box = L.DomUtil.create('div');
                box.style.cssText = 'background:rgba(255,255,255,0.92);padding:8px 12px;border:1px solid #999;' +
                    'border-radius:4px;font-family:sans-serif;font-size:12px;line-height:1.4;' +
                    'max-height:70vh;overflow-y:auto';

                var header = document.createElement('div');
                header.style.cssText = 'font-weight:600;cursor:pointer;user-select:none';
                var body = document.createElement('div');
                body.innerHTML = {{ this.rows_json }};
                var title = {{ this.title_json }};
                var open = {{ 'false' if this.collapsed else 'true' }};

                function draw() {
                    header.textContent = (open ? '\u25be ' : '\u25b8 ') + title;
                    header.style.marginBottom = open ? '6px' : '0';
                    body.style.display = open ? '' : 'none';
                }
                header.addEventListener('click', function () { open = !open; draw(); });
                draw();

                box.appendChild(header);
                box.appendChild(body);
                L.DomEvent.disableClickPropagation(box);
                return box;
            };
            control.addTo({{ this._parent.get_name() }});
        })();
        {% endmacro %}
    """)

    def __init__(self, title: str, rows: str, collapsed: bool) -> None:
        """Initialize the legend.

        Args:
            title: Legend heading, doubling as the fold handle
            rows: Rendered HTML of the entries
            collapsed: Whether it starts folded away
        """
        super().__init__()
        self._name = "Legend"
        self.title_json = _script_json(title)
        self.rows_json = _script_json(rows)
        self.collapsed = collapsed


def add_legend(fmap: folium.Map, title: str, entries: dict[str, str], collapsed: bool = False) -> None:
    """Add a legend that folds away at a click on its heading.

    Enough sources and enough layers make a legend tall enough to hide the
    terrain behind it, so it has to be possible to get it out of the way
    without losing the key to the colours.

    Args:
        fmap: Map to add the legend to
        title: Legend heading, which doubles as the fold handle
        entries: Mapping of label to CSS color
        collapsed: Whether it starts folded away
    """
    swatch = "display:inline-block;width:18px;height:4px;vertical-align:middle;margin-right:8px"
    # Labels routinely contain characters like "<15 km"; unescaped they would be
    # parsed as a tag and the whole entry would vanish from the rendered legend.
    rows = "".join(
        f"<div style='margin:3px 0'><span style='{swatch};background:{color}'></span>{escape(label)}</div>" for label, color in entries.items()
    )
    _Legend(title, rows, collapsed).add_to(fmap)


def finalize(fmap: folium.Map) -> folium.Map:
    """Attach the layer control after all layers have been added.

    Args:
        fmap: Map to finalize

    Returns:
        The same map, for chaining
    """
    folium.LayerControl(collapsed=False).add_to(fmap)
    return fmap
