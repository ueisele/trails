"""Interactive Folium maps for trail data.

Builds layered maps that combine trail geometries, area boundaries and points of
interest. Every layer is toggleable so several data sources can be compared
visually::

    fmap = create_map(bounds=park.total_bounds, base=BaseMap.KARTVERKET_TOPO)
    add_boundary(fmap, park, name="National park")
    add_trails(fmap, trails, name="Turrutebasen", color="#1b5e20")
    fmap.save("map.html")
"""

from enum import Enum
from html import escape
from typing import Any

import folium
import geopandas as gpd
import pandas as pd

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


def _build_popup(row: pd.Series, fields: dict[str, str]) -> str | None:
    """Render a popup table from selected fields.

    Args:
        row: Row of a GeoDataFrame
        fields: Mapping of column name to display label

    Returns:
        HTML table, or None if the row has no populated fields
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
        dash_array: SVG dash pattern, e.g. ``"8,6"``. Use for connections that
            are not walked, such as ferry crossings.
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

        lines = list(geometry.geoms) if geometry.geom_type == "MultiLineString" else [geometry]
        popup_html = _build_popup(row, popup_fields) if popup_fields else None

        for line in lines:
            polyline = folium.PolyLine(
                locations=[(lat, lon) for lon, lat in line.coords],
                color=color,
                weight=weight,
                opacity=opacity,
                dash_array=dash_array,
            )
            if popup_html:
                polyline.add_child(folium.Popup(popup_html, max_width=320))
            polyline.add_to(group)

    group.add_to(fmap)
    return group


def add_points(
    fmap: folium.Map,
    gdf: gpd.GeoDataFrame,
    name: str,
    color: str = "red",
    icon: str = "home",
    popup_fields: dict[str, str] | None = None,
    label_field: str | None = "name",
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

        popup_html = _build_popup(row, popup_fields) if popup_fields else None
        marker = folium.Marker(
            location=(geometry.y, geometry.x),
            tooltip=tooltip,
            icon=folium.Icon(color=color, icon=icon, prefix="fa"),
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
    radius: float = 4.0,
    label_field: str = "name",
    always_label: tuple[str, ...] = (),
    kind_field: str = "kind",
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
        radius: Circle radius in pixels
        label_field: Column holding the label text
        always_label: Values of ``kind_field`` whose labels are always shown
        kind_field: Column consulted for ``always_label``
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
        if label_field not in row or pd.isna(row[label_field]):
            continue

        label = str(row[label_field])
        permanent = kind_field in row and row[kind_field] in always_label

        folium.CircleMarker(
            location=(geometry.y, geometry.x),
            radius=radius,
            color=color,
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            tooltip=folium.Tooltip(label, permanent=permanent, direction="right"),
        ).add_to(group)

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
        html = (
            f'<div style="font-family:sans-serif;font-size:{size:g}px;color:{text_color};'
            f'text-shadow:{shadow};white-space:nowrap;transform:translate(-50%,-50%)">{text}</div>'
        )
        # A zero-sized icon keeps Leaflet from reserving a box around the text.
        folium.Marker(location=(geometry.y, geometry.x), icon=folium.DivIcon(icon_size=(0, 0), icon_anchor=(0, 0), html=html)).add_to(group)

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

    layer = folium.GeoJson(gdf.to_json(), name=name, style_function=style, show=show)
    layer.add_to(fmap)
    return layer


def add_legend(fmap: folium.Map, title: str, entries: dict[str, str]) -> None:
    """Add a fixed-position legend to the map.

    Args:
        fmap: Map to add the legend to
        title: Legend heading
        entries: Mapping of label to CSS color
    """
    swatch = "display:inline-block;width:18px;height:4px;vertical-align:middle;margin-right:8px"
    # Labels routinely contain characters like "<15 km"; unescaped they would be
    # parsed as a tag and the whole entry would vanish from the rendered legend.
    rows = "".join(
        f"<div style='margin:3px 0'><span style='{swatch};background:{color}'></span>{escape(label)}</div>" for label, color in entries.items()
    )
    html = (
        '<div style="position:fixed;bottom:24px;left:24px;z-index:9999;background:rgba(255,255,255,0.92);'
        'padding:10px 14px;border:1px solid #999;border-radius:4px;font-family:sans-serif;font-size:12px;line-height:1.4">'
        f"<div style='font-weight:600;margin-bottom:6px'>{escape(title)}</div>{rows}</div>"
    )
    root = fmap.get_root()
    assert isinstance(root, folium.Figure), "map root must be a Figure to hold raw HTML"
    root.html.add_child(folium.Element(html))


def finalize(fmap: folium.Map) -> folium.Map:
    """Attach the layer control after all layers have been added.

    Args:
        fmap: Map to finalize

    Returns:
        The same map, for chaining
    """
    folium.LayerControl(collapsed=False).add_to(fmap)
    return fmap
