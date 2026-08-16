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
