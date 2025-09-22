"""Interactive area selection for trail export."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import folium
import geopandas as gpd
from folium import plugins
from folium.plugins import Geocoder

try:
    import ipyleaflet
    import ipywidgets as widgets

    IPYLEAFLET_AVAILABLE = True
except ImportError:
    IPYLEAFLET_AVAILABLE = False


def create_selection_map(
    gdf: gpd.GeoDataFrame,
    center: tuple[float, float] | None = None,
    zoom_start: int = 6,
) -> folium.Map:
    """Create an interactive map with area selection tools.

    Args:
        gdf: GeoDataFrame with trail data to display
        center: Optional center point (lat, lon)
        zoom_start: Initial zoom level

    Returns:
        Folium map with draw tools
    """
    # Convert to WGS84 for web mapping
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf_wgs = gdf.to_crs(epsg=4326)
    else:
        gdf_wgs = gdf.copy()

    # Calculate center if not provided
    if center is None:
        bounds = gdf_wgs.total_bounds
        center = ((bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2)

    # Create base map
    m = folium.Map(
        location=center,
        zoom_start=zoom_start,
        control_scale=True,
    )

    # Add tile layers
    folium.TileLayer("OpenStreetMap").add_to(m)
    folium.TileLayer("CartoDB positron", show=False).add_to(m)

    # Add trails as a simple layer (for context)
    trail_group = folium.FeatureGroup(name="All Trails", show=True)

    # Sample trails for performance
    sample_size = min(1000, len(gdf_wgs))
    sampled = gdf_wgs.sample(n=sample_size) if len(gdf_wgs) > sample_size else gdf_wgs

    for _, trail in sampled.iterrows():
        if trail.geometry:
            folium.GeoJson(
                trail.geometry.__geo_interface__,
                style_function=lambda x: {
                    "color": "gray",
                    "weight": 1,
                    "opacity": 0.5,
                },
            ).add_to(trail_group)

    trail_group.add_to(m)

    # Add draw tools with simplified options
    draw = plugins.Draw(
        export=True,
        position="topleft",
        draw_options={
            "rectangle": {
                "shapeOptions": {
                    "color": "#ff0000",
                    "weight": 2,
                    "fillOpacity": 0.1,
                }
            },
            "polygon": False,
            "polyline": False,
            "circle": False,
            "circlemarker": False,
            "marker": False,
        },
        edit_options={"edit": False, "remove": True},
    )
    draw.add_to(m)

    # Add a marker click handler to show coordinates
    m.add_child(folium.LatLngPopup())

    # Add geocoder for city search

    Geocoder(position="topleft", collapsed=False, placeholder="Search for a city...", error_message="Nothing found").add_to(m)

    # Add instructions
    instructions = """
    <div style='position: fixed; top: 80px; right: 10px; width: 320px;
                background-color: white; padding: 15px; border: 2px solid gray;
                border-radius: 5px; z-index: 1000; font-size: 14px;'>
        <h4 style="margin-top: 0;">Area Selection Instructions</h4>

        <p style="margin: 10px 0;"><b>🔍 Search for a City:</b></p>
        <ul style="margin: 5px 0; padding-left: 20px;">
            <li>Use the search box (top-left) to find any Norwegian city</li>
            <li>Type city name and press Enter</li>
            <li>Map will zoom to that location</li>
        </ul>

        <p style="margin: 10px 0;"><b>📍 Select Area:</b></p>
        <ol style="margin: 5px 0; padding-left: 20px;">
            <li>After zooming to your city, click the square icon (□)</li>
            <li>Draw a rectangle around your desired area</li>
            <li>Or click on map to see coordinates</li>
        </ol>

        <p style="margin: 10px 0; color: #666;">
            <b>Example bounds:</b><br>
            (min_lon, min_lat, max_lon, max_lat)<br>
            (8.5, 58.8, 9.2, 59.2)
        </p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(instructions))  # type: ignore[attr-defined]

    # Add layer control
    folium.LayerControl().add_to(m)

    return m


def parse_drawn_bounds(drawn_features: str) -> tuple[float, float, float, float] | None:
    """Parse bounds from folium draw export.

    Args:
        drawn_features: JSON string from folium draw export

    Returns:
        Bounding box as (minx, miny, maxx, maxy) or None
    """
    try:
        data = json.loads(drawn_features)
        features = data.get("features", [])

        if not features:
            return None

        # Get the first rectangle
        feature = features[0]
        geometry = feature.get("geometry", {})

        if geometry.get("type") == "Polygon":
            coords = geometry.get("coordinates", [[]])[0]
            if len(coords) >= 4:
                lons = [c[0] for c in coords]
                lats = [c[1] for c in coords]
                return (min(lons), min(lats), max(lons), max(lats))
    except (json.JSONDecodeError, KeyError, IndexError):
        pass

    return None


def export_trails_for_area(
    trails_gdf: gpd.GeoDataFrame,
    bounds: tuple[float, float, float, float],
    output_path: Path,
    buffer_km: float = 0,
    max_trails: int | None = None,
    simplify: bool = True,
) -> tuple[Path, dict[str, Any]]:
    """Export trails within a selected area to GPX.

    Args:
        trails_gdf: GeoDataFrame with all trails
        bounds: Bounding box (minx, miny, maxx, maxy) in WGS84
        output_path: Path for GPX file
        buffer_km: Buffer around bounds in kilometers
        max_trails: Maximum number of trails to export
        simplify: Whether to simplify geometries

    Returns:
        Tuple of (output_path, statistics)
    """
    from .gpx import export_to_gpx, filter_trails_by_bbox

    # Convert bounds CRS if needed
    if trails_gdf.crs and trails_gdf.crs.to_epsg() != 4326:
        # Create a GeoDataFrame with the bounds to transform
        from shapely.geometry import box

        bounds_gdf = gpd.GeoDataFrame([1], geometry=[box(*bounds)], crs="EPSG:4326")
        bounds_gdf = bounds_gdf.to_crs(trails_gdf.crs)
        bounds_geom = bounds_gdf.geometry[0]
        bounds = bounds_geom.bounds

    # Filter trails
    filtered = filter_trails_by_bbox(trails_gdf, bounds, buffer_m=buffer_km * 1000)

    if len(filtered) == 0:
        return output_path, {"error": "No trails found in selected area"}

    # Export to GPX
    return export_to_gpx(
        filtered,
        output_path,
        simplify_tolerance=0.00001 if simplify else None,
        max_trails=max_trails,
    )


def save_selection_preset(
    name: str,
    bounds: tuple[float, float, float, float],
    description: str = "",
    presets_file: Path = Path(".cache/area_presets.json"),
) -> None:
    """Save an area selection as a named preset.

    Args:
        name: Name for the preset
        bounds: Bounding box (minx, miny, maxx, maxy)
        description: Optional description
        presets_file: Path to presets file
    """
    presets_file.parent.mkdir(parents=True, exist_ok=True)

    # Load existing presets
    presets = {}
    if presets_file.exists():
        with open(presets_file) as f:
            presets = json.load(f)

    # Add new preset
    presets[name] = {
        "bounds": bounds,
        "description": description,
        "created": datetime.now().isoformat(),
    }

    # Save
    with open(presets_file, "w") as f:
        json.dump(presets, f, indent=2)


def load_selection_preset(
    name: str,
    presets_file: Path = Path(".cache/area_presets.json"),
) -> tuple[float, float, float, float] | None:
    """Load a saved area selection preset.

    Args:
        name: Name of the preset
        presets_file: Path to presets file

    Returns:
        Bounding box or None if not found
    """
    if not presets_file.exists():
        return None

    with open(presets_file) as f:
        presets = json.load(f)

    preset = presets.get(name)
    if preset:
        return tuple(preset["bounds"])

    return None


def create_interactive_selection_map(
    gdf: gpd.GeoDataFrame,
    center: tuple[float, float] | None = None,
    zoom_start: int = 5,
) -> tuple[Any, dict]:
    """Create an interactive ipyleaflet map with area selection.

    This function creates a truly interactive map in Jupyter notebooks
    where drawn rectangles automatically update a bounds variable.

    Args:
        gdf: GeoDataFrame with trail data to display
        center: Optional center point (lat, lon)
        zoom_start: Initial zoom level

    Returns:
        Tuple of (map widget, bounds_container dict)
        The bounds_container will have a 'bounds' key that updates automatically

    Raises:
        ImportError: If ipyleaflet is not installed
    """
    if not IPYLEAFLET_AVAILABLE:
        raise ImportError("ipyleaflet is required for interactive selection. Install it with: uv add --group jupyter ipyleaflet")

    # Convert to WGS84 for web mapping
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf_wgs = gdf.to_crs(epsg=4326)
    else:
        gdf_wgs = gdf.copy()

    # Calculate center if not provided
    if center is None:
        bounds = gdf_wgs.total_bounds
        center = ((bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2)

    # Create the map
    m = ipyleaflet.Map(
        center=center,
        zoom=zoom_start,
        layout=widgets.Layout(width="100%", height="600px"),
    )

    # Add tile layers
    m.add_layer(ipyleaflet.basemap_to_tiles(ipyleaflet.basemaps.OpenStreetMap.Mapnik))

    # Sample trails for display (for performance)
    sample_size = min(1000, len(gdf_wgs))
    sampled = gdf_wgs.sample(n=sample_size) if len(gdf_wgs) > sample_size else gdf_wgs

    # Add trail lines for context
    for _, trail in sampled.iterrows():
        if trail.geometry and trail.geometry.geom_type == "LineString":
            coords = [[lat, lon] for lon, lat in trail.geometry.coords]
            polyline = ipyleaflet.Polyline(
                locations=coords,
                color="gray",
                weight=1,
                opacity=0.5,
            )
            m.add_layer(polyline)

    # Container to store bounds (mutable object to allow updates)
    bounds_container: dict[str, Any] = {"bounds": None, "rectangle": None}

    # Status label
    status_label = widgets.HTML(
        value="<b>📍 Draw a rectangle to select an area</b>",
        layout=widgets.Layout(margin="10px"),
    )

    # Create draw control
    draw_control = ipyleaflet.DrawControl(
        rectangle={
            "shapeOptions": {
                "color": "#ff0000",
                "weight": 2,
                "fillOpacity": 0.1,
            }
        },
        polygon={},
        polyline={},
        circle={},
        circlemarker={},
        marker={},
    )

    def handle_draw(self: Any, action: str, geo_json: dict[str, Any]) -> None:
        """Handle drawn shapes and extract bounds."""
        if action == "created" and geo_json["geometry"]["type"] == "Polygon":
            # Extract coordinates from the drawn rectangle
            coords = geo_json["geometry"]["coordinates"][0]
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]

            # Calculate bounds
            min_lon, max_lon = min(lons), max(lons)
            min_lat, max_lat = min(lats), max(lats)
            bounds_container["bounds"] = (min_lon, min_lat, max_lon, max_lat)

            # Remove previous rectangle if exists
            if bounds_container["rectangle"]:
                try:
                    m.remove_layer(bounds_container["rectangle"])
                except Exception:
                    pass

            # Add visual rectangle
            rectangle = ipyleaflet.Rectangle(
                bounds=((min_lat, min_lon), (max_lat, max_lon)),
                color="red",
                fill_color="red",
                fill_opacity=0.1,
                weight=2,
            )
            m.add_layer(rectangle)
            bounds_container["rectangle"] = rectangle

            # Update status
            status_label.value = (
                f"<b style='color: green;'>✅ Area selected!</b><br>Bounds: ({min_lon:.3f}, {min_lat:.3f}, {max_lon:.3f}, {max_lat:.3f})"
            )

            # Clear the drawn shape from draw control
            draw_control.clear()

    # Connect the draw handler
    draw_control.on_draw(handle_draw)
    m.add_control(draw_control)

    # Add custom search button for Norwegian places using Kartverket API
    search_box = widgets.Text(
        placeholder="Search Norwegian place...",
        layout=widgets.Layout(width="200px"),
    )
    search_button = widgets.Button(
        description="Search",
        button_style="primary",
        layout=widgets.Layout(width="80px"),
    )

    def search_norwegian_place(b: Any) -> None:
        """Search for Norwegian place names using Kartverket API."""
        search_term = search_box.value.strip()
        if not search_term:
            return

        import requests

        try:
            # Use Kartverket's stedsnavn API
            response = requests.get("https://ws.geonorge.no/stedsnavn/v1/navn", params={"sok": search_term + "*", "treffPerSide": 5}, timeout=5)

            if response.status_code == 200:
                data = response.json()
                metadata = data.get("metadata", {})
                if metadata.get("totaltAntallTreff", 0) > 0:
                    # Get first result
                    first_result = data["navn"][0]

                    # Extract coordinates
                    representasjonspunkt = first_result.get("representasjonspunkt")
                    if representasjonspunkt:
                        # Coordinates appear to be in lat/lon format directly
                        lat = representasjonspunkt.get("nord", 0)
                        lon = representasjonspunkt.get("øst", 0)

                        # Update map center
                        m.center = (lat, lon)
                        m.zoom = 11

                        place_name = first_result.get("skrivemåte", search_term)
                        status_label.value = f"<b style='color: green;'>📍 Found: {place_name}</b>"
                else:
                    status_label.value = f"<b style='color: orange;'>⚠️ No results for: {search_term}</b>"
            else:
                status_label.value = "<b style='color: red;'>❌ Search failed</b>"

        except Exception as e:
            status_label.value = f"<b style='color: red;'>❌ Search error: {str(e)[:50]}</b>"

    search_button.on_click(search_norwegian_place)

    # Also search on Enter key
    search_box.on_submit(lambda x: search_norwegian_place(None))

    # Create search widget box
    search_widget = widgets.HBox(
        [search_box, search_button],
        layout=widgets.Layout(margin="5px"),
    )

    # Compact instructions
    instructions = widgets.HTML(
        value="""
        <div style='padding: 5px 10px; background: #f0f0f0; border-radius: 3px; font-size: 12px;'>
            <b>🗺️ Quick Guide:</b>
            1) Search city with 🔍
            2) Draw rectangle with ◻ tool
            3) Bounds auto-captured in <code>selected_bounds</code>
        </div>
        """,
        layout=widgets.Layout(margin="5px 0"),
    )

    # Create the widget layout
    map_widget = widgets.VBox([instructions, search_widget, m, status_label])

    return map_widget, bounds_container
