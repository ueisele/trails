"""The XYZ tile grid: which tiles a box touches, and where one tile lies.

Web Mercator, 256 px, ``y`` counted from the top -- Leaflet's ``{z}/{x}/{y}``,
Lantmäteriet's GeoPackage rows, and the addresses the bucket serves. One
place for the arithmetic, so the map tiles copied out of the download and the
height tiles built from the elevation model land on the same grid.
"""

import math
from collections.abc import Iterable

#: ``(min_lon, min_lat, max_lon, max_lat)`` in WGS 84.
Bounds = tuple[float, float, float, float]

#: Half the Web Mercator world in metres: the projection's extent is ±this.
HALF_WORLD_M = 20037508.342789244

#: Pixels along one side of a tile.
TILE_PX = 256


def tile_range(bounds: Bounds, zoom: int) -> tuple[int, int, int, int]:
    """The XYZ tiles a box touches at one zoom.

    Args:
        bounds: ``(min_lon, min_lat, max_lon, max_lat)``
        zoom: Zoom level

    Returns:
        ``(x0, y0, x1, y1)``, inclusive; ``y`` counts from the top
    """
    min_lon, min_lat, max_lon, max_lat = bounds
    n = 1 << zoom

    def column(lon: float) -> int:
        return math.floor((lon + 180.0) / 360.0 * n)

    def row(lat: float) -> int:
        phi = math.radians(lat)
        return math.floor((1.0 - math.log(math.tan(phi) + 1.0 / math.cos(phi)) / math.pi) / 2.0 * n)

    return column(min_lon), row(max_lat), column(max_lon), row(min_lat)


def tile_count(bounds: Bounds, zooms: Iterable[int]) -> int:
    """How many tiles a box holds over the given zooms.

    Args:
        bounds: The box
        zooms: Zoom levels

    Returns:
        The count
    """
    total = 0
    for zoom in zooms:
        x0, y0, x1, y1 = tile_range(bounds, zoom)
        total += (x1 - x0 + 1) * (y1 - y0 + 1)
    return total


def tile_bounds(zoom: int, x: int, y: int) -> tuple[float, float, float, float]:
    """Where one tile lies, in Web Mercator metres.

    Args:
        zoom: Zoom level
        x: Column
        y: Row, from the top

    Returns:
        ``(min_x, min_y, max_x, max_y)`` in EPSG:3857
    """
    side = 2.0 * HALF_WORLD_M / (1 << zoom)
    min_x = -HALF_WORLD_M + x * side
    max_y = HALF_WORLD_M - y * side
    return min_x, max_y - side, min_x + side, max_y


def tile_resolution(zoom: int, latitude: float) -> float:
    """Ground metres per pixel of a tile at one latitude.

    Args:
        zoom: Zoom level
        latitude: Degrees north

    Returns:
        Metres on the ground that one pixel spans there
    """
    return 2.0 * HALF_WORLD_M / (1 << zoom) / TILE_PX * math.cos(math.radians(latitude))
