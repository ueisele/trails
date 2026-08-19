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
        figure_fields: Mapping of a numeric column to the key it travels under,
            for the figures :func:`add_profile_panel` shows. Recorded per
            ``group_field`` value, beside the layer rather than on it, alongside
            the value itself under :data:`FIGURE_ID_KEY`.
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
                // Single precision holds a decimetre exactly to sixteen
                // kilometres of altitude, which is four orders of magnitude
                // more than this ground, and halves what the series costs in
                // memory. The coordinates get double precision, where a
                // millionth of a degree needs it.
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
    """

    _template = Template("""
        {% macro script(this, kwargs) %}
        (function () {
            var map = {{ this._parent.get_name() }};
            var groups = [{{ this.group_names|join(', ') }}];
            var figures = {{ this.figures_json }};
            var title = {{ this.title_json }};
            var chartHeight = {{ this.chart_height }};
            var open = {{ 'false' if this.collapsed else 'true' }};

            var SVG = 'http://www.w3.org/2000/svg';
            // Room for the axes: the left margin holds a four-digit height, the
            // bottom one a distance.
            var PAD = {left: 52, right: 16, top: 12, bottom: 22};
            var CURVE = '#33691e', AXIS = '#9e9e9e', TEXT = '#555', CROSS = '#c62828';

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
            // Metres between two positions. Near enough for an axis at this
            // latitude, and the result is scaled onto the length the chain
            // carries before anything is shown, so the axis cannot end
            // somewhere the popup does not.
            function metresBetween(lon1, lat1, lon2, lat2) {
                var dx = (lon2 - lon1) * 111320 * Math.cos(((lat1 + lat2) / 2) * Math.PI / 180);
                var dy = (lat2 - lat1) * 110574;
                return Math.sqrt(dx * dx + dy * dy);
            }

            // The payload holds a chain's edges as one contiguous run in the
            // chain's own order; bit 0 of an edge's flag says it runs against
            // the chain, bit 1 that it begins a stretch which does not join what
            // came before. Two joined edges both sample the node between them,
            // so the second copy of it is dropped.
            function compose(graph, index) {
                var first = graph.chainAt[index], last = graph.chainAt[index + 1];
                var lon = [], lat = [], along = [], height = [], distance = [];
                var reached = 0, read = false, crossing = false, joined = false;
                for (var edge = first; edge < last; edge += 1) {
                    var flipped = graph.flags[edge] & 1;
                    var apart = (graph.flags[edge] & 2) && lon.length > 0;
                    var v0 = graph.vertexAt[edge], v1 = graph.vertexAt[edge + 1];
                    var began = reached;
                    crossing = crossing || graph.header.sources[graph.sources[edge]].kind === 'ferry';

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

                    var s0 = graph.sampleAt[edge], s1 = graph.sampleAt[edge + 1], samples = s1 - s0;
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
                        // lies rather than s * 5.
                        distance.push(samples > 1 ? began + (length * s) / (samples - 1) : began);
                        if (!isNaN(value)) { read = true; }
                    }
                    joined = samples > 0;
                }
                return {lon: lon, lat: lat, along: along, height: height, distance: distance,
                        total: reached, read: read, crossing: crossing};
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

            // ---- the panel -------------------------------------------------
            var header = document.createElement('div');
            header.style.cssText = 'font-weight:600;cursor:pointer;user-select:none';
            var body = document.createElement('div');
            var summary = document.createElement('div');
            summary.style.cssText = 'margin:4px 0 2px;color:#333';
            var chart = document.createElementNS(SVG, 'svg');
            chart.setAttribute('height', chartHeight);
            chart.style.cssText = 'display:block;width:100%;height:' + chartHeight + 'px;cursor:crosshair';
            body.appendChild(summary);
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
            ['#ffffff', CURVE].forEach(function (colour, index) {
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

            function drawCurve(shape, plot, x, y) {
                var parts = [], pen = false, i;
                var columns = Math.max(1, Math.floor(plot.width));
                if (shape.height.length <= columns) {
                    // The common case, and it has to be: the median chain here
                    // holds 36 samples and a third of them fewer than twenty.
                    // Bucketing those into 900 columns leaves 864 empty and the
                    // curve full of holes it has no business having.
                    for (i = 0; i < shape.height.length; i += 1) {
                        if (isNaN(shape.height[i])) { pen = false; continue; }
                        parts.push((pen ? 'L' : 'M') + x(shape.distance[i]).toFixed(1) + ' ' + y(shape.height[i]).toFixed(1));
                        pen = true;
                    }
                    return parts.join(' ');
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
                    if (previous >= 0 && missed[firstAt[c]] > missed[lastAt[previous] + 1]) { pen = false; }
                    var at = x(((c + 0.5) / columns) * shape.total).toFixed(1);
                    var pair = lowAt[c] <= highAt[c] ? [low[c], high[c]] : [high[c], low[c]];
                    parts.push((pen ? 'L' : 'M') + at + ' ' + y(pair[0]).toFixed(1));
                    if (pair[0] !== pair[1]) { parts.push('L' + at + ' ' + y(pair[1]).toFixed(1)); }
                    pen = true;
                    previous = c;
                }
                return parts.join(' ');
            }

            function render() {
                while (chart.firstChild) { chart.removeChild(chart.firstChild); }
                crosshair = null;
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

                var curve = document.createElementNS(SVG, 'path');
                curve.setAttribute('d', drawCurve(shape, plot, x, y));
                curve.setAttribute('fill', 'none');
                curve.setAttribute('stroke', CURVE);
                curve.setAttribute('stroke-width', '1.6');
                curve.setAttribute('stroke-linejoin', 'round');
                chart.appendChild(curve);

                // The crosshair's own parts, made once and moved afterwards.
                // Rebuilding them per mouse move is the mistake that froze this
                // map twice already, on a layer rather than on a chart.
                var rule = line(plot.left, plot.top, plot.left, plot.bottom, CROSS);
                var dot = document.createElementNS(SVG, 'circle');
                dot.setAttribute('r', '2.5'); dot.setAttribute('fill', CROSS);
                var reading = text(plot.right, plot.top + 8, '', 'end');
                reading.setAttribute('fill', CROSS);
                [rule, dot, reading].forEach(function (node) { node.style.display = 'none'; chart.appendChild(node); });
                crosshair = {rule: rule, dot: dot, reading: reading, plot: plot, width: width, x: x, y: y, at: -1};
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
                crosshair.reading.textContent = (shape.distance[at] / 1000).toFixed(2) + ' km \\u00b7 ' + (read ? metres(value) + ' m' : 'not read');
            });

            chart.addEventListener('mouseleave', function () {
                if (!crosshair) { return; }
                crosshair.at = -1;
                [crosshair.rule, crosshair.dot, crosshair.reading].forEach(function (node) { node.style.display = 'none'; });
            });

            // ---- what is selected -------------------------------------------
            var selected = null;

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

            function describe() {
                if (!selected) { say('Click a line to see its profile.'); return; }
                var figure = selected.figure, shape = selected.shape;
                if (!shape) { say('Decoding the network\\u2026'); return; }
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

            function show(className, label) {
                selected = className === null ? null : {className: className, figure: figures[className], label: label, shape: null, mid: null};
                if (selected && !selected.figure) { selected = null; }
                // Open on a chain and folded away again the moment there is
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
                render();
                placeArrow();
                if (!selected) { return; }
                if (!window.trailsGraph) { say('There is no routing graph in this page, so there is no profile to draw.'); return; }
                var wanted = selected.className;
                window.trailsGraph.ready.then(function (graph) {
                    // The reader may well have clicked something else while a
                    // megabyte of arithmetic was going on.
                    if (!selected || selected.className !== wanted) { return; }
                    var index = graph.chainOf[selected.figure.id];
                    if (index === undefined) { say('This line is not in the routing graph.'); return; }
                    selected.shape = scale(compose(graph, index), selected.figure.length);
                    selected.mid = midpoint(selected.shape);
                    describe();
                    render();
                    placeArrow();
                }).catch(function () { say('The routing graph did not arrive, so there is no profile to draw.'); });
            }

            groups.forEach(function (group) {
                group.eachLayer(function (layer) {
                    if (!layer.setStyle || !layer.options.className) { return; }
                    layer.on('click', function () {
                        var className = layer.options.className;
                        show(selected && selected.className === className ? null : className, labelOf(layer, className));
                    });
                });
            });
            // Leaflet only fires a map click where the click hit no layer, which
            // is what clears the selection on empty terrain — the same rule the
            // click-highlight follows, so the two cannot drift apart.
            map.on('click', function () { show(null); });
            // A panel this wide is sized against the map, so a resized window
            // has to size it again before anything is drawn into it.
            map.on('resize', function () { fold(); render(); placeArrow(); });

            fold();
            describe();
            render();
        })();
        {% endmacro %}
    """)

    def __init__(
        self, groups: list[folium.FeatureGroup], figures: dict[str, dict[str, object]], title: str, chart_height: int, collapsed: bool
    ) -> None:
        """Initialize the panel.

        Args:
            groups: Feature groups whose lines can be selected
            figures: Mapping of CSS class to the figures of the line carrying it
            title: Panel heading, doubling as the fold handle
            chart_height: Height of the drawing area in pixels
            collapsed: Whether it starts folded away
        """
        super().__init__()
        self._name = "ProfilePanel"
        self.group_names = [group.get_name() for group in groups]
        self.figures_json = _script_json(figures)
        self.title_json = _script_json(title)
        self.chart_height = int(chart_height)
        self.collapsed = collapsed


def add_profile_panel(
    fmap: folium.Map,
    groups: list[folium.FeatureGroup],
    title: str = "Elevation profile",
    chart_height: int = 150,
    collapsed: bool = True,
) -> None:
    """Draw the selected chain's profile at the foot of the map.

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

    Call after the layers and after :func:`add_routing_graph`, whose payload it
    reads. It shares the bottom left with the legend and the scale bar and puts
    itself under both, so the order it is added in does not matter.

    Args:
        fmap: Map holding the layers
        groups: Feature groups returned by :func:`add_trails`
        title: Panel heading, which doubles as the fold handle
        chart_height: Height of the drawing area in pixels
        collapsed: Whether it starts folded away
    """
    if not groups:
        return

    figures: dict[str, dict[str, object]] = {}
    for group in groups:
        figures.update(getattr(group, CHAIN_FIGURES_ATTR, {}))
    if not figures:
        return

    _ProfilePanel(groups, figures, title, chart_height, collapsed).add_to(fmap)


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
