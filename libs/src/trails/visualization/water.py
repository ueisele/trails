"""Where the water is, as a grid of bits the page can ask in constant time.

**Why a grid and not the outlines.** The page prices a straight walk by what it
crosses, and it prices thousands of them in one search: every node of the
graph is joined to each end of a leg by a straight connector, and a connector
over a fjord has to cost more than one over ground or the way to a headland
runs across the water in front of it. Outlines would answer that too, but a
connector tested against the coast is a loop over every vertex of the sea, and
the sea here has 47,000 of them at ten metres. A grid answers with one
subtraction, one division and one bit, and a 1.2 km connector asks it
forty-eight times.

**What it costs.** Measured for the Lomsdal-Visten build, 81 by 90 km: at 25 m
a cell, 3,230 by 3,589 cells, 1.45 MB of bits in memory and 146 kB gzipped into
the page, three per cent of the page. Sea and lakes both, because a straight
leg across a tarn is as much a fiction as one across a fjord. The outlines
simplified to ten metres would have been 5.5 MB in memory and 0.94 MB in the
page, and slower to ask.

**What it is for and what it is not for.** The bits decide a *price*, and a
price is allowed to be a cell out: a connector that touches one cell of sea
because the shore is 25 m from where the reader tapped costs one cell's worth
more than it should, and every connector from that point pays the same,
so nothing between them is decided by it. Nothing is drawn from the grid. What
a straight leg shows as water on the profile still comes from the height
service, which classifies each sample by what it is standing on.

The cells are laid out in degrees rather than metres, so that the page can ask
about a longitude and a latitude without projecting either. A cell is
``cell_m`` tall everywhere and ``cell_m`` wide at the middle latitude of the
box, a shade wider at its southern edge and narrower at its northern one -- a
per cent across a park, and a price does not notice.
"""

import base64
import gzip
import math
from typing import Any

import geopandas as gpd
import numpy as np
import shapely

#: Metres in a degree of latitude, and of longitude at the equator. The same
#: figure the page measures its snapping and matching reaches in.
METRES_PER_DEGREE = 111_320.0

#: Everything a mask entry in the header has to carry before the page may use
#: it. ``west``, ``south``, ``dLon`` and ``dLat`` place the grid and size a
#: cell; ``cols`` and ``rows`` bound it; ``cellM`` is the cell's height in
#: metres, which is the step a connector is sampled at; ``bits`` is the grid,
#: row-major from the south-west, eight cells to a byte with the westernmost
#: in the high bit, gzipped and base64-encoded; and ``set`` is how many of the
#: bits are on, which is what lets the page say it inflated the grid it was
#: sent and not some of it.
WATER_FIELDS = ("west", "south", "dLon", "dLat", "cols", "rows", "cellM", "bits", "set")

#: The CRS the grid is laid out in, which is the one the page asks in.
GRID_CRS = "EPSG:4326"


def water_mask(water: gpd.GeoDataFrame, bounds: tuple[float, float, float, float], cell_m: float = 25.0) -> dict[str, Any]:
    """Rasterise the water into the grid the page carries.

    Args:
        water: The sea and the lakes as outlines, in any CRS
        bounds: ``(west, south, east, north)`` in degrees, the box to cover.
            Ground outside it answers *not water*, so the box has to reach as
            far as a leg may be laid.
        cell_m: The cell's height in metres, and its width at the middle
            latitude

    Returns:
        The header entry, with every field of :data:`WATER_FIELDS`

    Raises:
        ValueError: If the box is empty or the cell is not a positive size
    """
    west, south, east, north = (float(value) for value in bounds)
    if not east > west or not north > south:
        raise ValueError(f"the box ({west}, {south}, {east}, {north}) has no area to cover")
    if not cell_m > 0:
        raise ValueError(f"a cell has to be a positive size, not {cell_m} m")

    d_lat = cell_m / METRES_PER_DEGREE
    d_lon = cell_m / (METRES_PER_DEGREE * math.cos(math.radians((south + north) / 2)))
    cols = _cells(east - west, d_lon)
    rows = _cells(north - south, d_lat)
    mask = np.zeros((rows, cols), dtype=bool)

    # Each outline is asked only about the cells under its own box. The sea
    # comes in pieces the size of a municipality and each piece asks about a
    # few million cells; a tarn asks about a dozen. Cell centres, so that a
    # cell is water when its middle is, which is the reading the page gives
    # back for a position inside it.
    for geometry in water.to_crs(GRID_CRS).geometry:
        if geometry is None or geometry.is_empty:
            continue
        min_x, min_y, max_x, max_y = geometry.bounds
        first_col, last_col = max(0, math.floor((min_x - west) / d_lon)), min(cols, math.ceil((max_x - west) / d_lon))
        first_row, last_row = max(0, math.floor((min_y - south) / d_lat)), min(rows, math.ceil((max_y - south) / d_lat))
        if last_col <= first_col or last_row <= first_row:
            continue
        xs = west + (np.arange(first_col, last_col) + 0.5) * d_lon
        ys = south + (np.arange(first_row, last_row) + 0.5) * d_lat
        grid_x, grid_y = np.meshgrid(xs, ys)
        shapely.prepare(geometry)
        inside = shapely.contains_xy(geometry, grid_x.ravel(), grid_y.ravel()).reshape(last_row - first_row, last_col - first_col)
        mask[first_row:last_row, first_col:last_col] |= inside

    packed = np.packbits(mask, axis=1).tobytes()
    # A fixed timestamp, for the same reason the graph's stream has one: two
    # builds of the same ground produce the same page.
    encoded = base64.b64encode(gzip.compress(packed, compresslevel=9, mtime=0)).decode("ascii")
    return {
        "west": west,
        "south": south,
        "dLon": d_lon,
        "dLat": d_lat,
        "cols": cols,
        "rows": rows,
        "cellM": float(cell_m),
        "bits": encoded,
        "set": int(mask.sum()),
    }


#: What every river entry carries. ``name`` is None where N50 has none, ``bounds``
#: is the box a line is tested against before its rings are, ``rings`` are the
#: outline's rings -- the outer first, then any islands -- each a flat list of
#: integers in :data:`RIVER_QUANTUM` degrees, the first pair absolute and every
#: pair after it a difference from the one before. Measured for the
#: Lomsdal-Visten box at 3 m: 413 rivers, 39,700 vertices, which as rounded
#: floats would be 770 kB of the page and as differences are a third of that.
RIVER_FIELDS = ("name", "bounds", "rings")

#: The grid a river vertex is written on, in degrees: a metre, which is finer
#: than the outline was simplified to.
RIVER_QUANTUM = 1e-5


def river_table(rivers: gpd.GeoDataFrame, bounds: tuple[float, float, float, float], tolerance_m: float = 3.0) -> dict[str, Any]:
    """Lay the rivers out as the outlines the page carries.

    **Outlines and not a grid, because these decide a sentence and not a
    price.** The water grid answers thousands of connectors in one search and
    may be a cell out; a river is asked about once, of the straight parts a
    leg ended up with, and what it answers is *this line meets the Krutåga,
    and the water is 19 m wide there* -- a figure a reader weighs a crossing
    by, which a 25 m cell could not give.

    Args:
        rivers: The rivers as outlines, carrying ``name``, in any CRS
        bounds: ``(west, south, east, north)`` in degrees; a river wholly
            outside it is left out, one across its edge is clipped to it
        tolerance_m: How far a simplified outline may stray from the drawn one

    Returns:
        The header entry: ``quantum`` and ``rivers``, each river with every
        field of :data:`RIVER_FIELDS`

    Raises:
        ValueError: If the box is empty or the tolerance is negative
    """
    west, south, east, north = (float(value) for value in bounds)
    if not east > west or not north > south:
        raise ValueError(f"the box ({west}, {south}, {east}, {north}) has no area to cover")
    if tolerance_m < 0:
        raise ValueError(f"a tolerance is a distance, not {tolerance_m} m")
    entries: list[dict[str, Any]] = []
    if len(rivers) == 0:
        return {"quantum": RIVER_QUANTUM, "rivers": entries}
    box = shapely.box(west, south, east, north)
    clipped = rivers.to_crs(GRID_CRS)
    clipped = clipped[clipped.geometry.intersects(box)].copy()
    clipped["geometry"] = clipped.geometry.intersection(box)
    # Simplified in metres, because a tolerance in degrees is a different
    # distance north-south from east-west; then back, because the page asks
    # in degrees.
    metric = clipped.to_crs(clipped.estimate_utm_crs())
    metric["geometry"] = metric.geometry.simplify(tolerance_m, preserve_topology=True) if tolerance_m > 0 else metric.geometry
    for name, geometry in zip(clipped["name"], metric.to_crs(GRID_CRS).geometry, strict=True):
        if geometry is None or geometry.is_empty:
            continue
        # A MultiPolygon is what clipping hands back wherever the box cuts a
        # river in two, and a Polygon has no `geoms`. Annotated the way the
        # protected areas' own ring table annotates it: shapely's stubs type
        # a frame's geometry as the base class, which has neither `geoms` nor
        # `exterior`, and the check is the geometry's own word for what it is.
        outline: Any = geometry
        pieces: list[Any] = list(outline.geoms) if outline.geom_type == "MultiPolygon" else [outline]
        for piece in pieces:
            if piece.geom_type != "Polygon" or piece.is_empty:
                continue
            rings = [_deltas(ring.coords) for ring in [piece.exterior, *piece.interiors]]
            rings = [ring for ring in rings if len(ring) >= 6]
            if not rings:
                continue
            min_x, min_y, max_x, max_y = piece.bounds
            entries.append(
                {
                    "name": None if name is None or (isinstance(name, float) and math.isnan(name)) else str(name),
                    "bounds": [float(min_x), float(min_y), float(max_x), float(max_y)],
                    "rings": rings,
                }
            )
    return {"quantum": RIVER_QUANTUM, "rivers": entries}


def _deltas(coords: Any) -> list[int]:
    """Write a ring as quantised differences, the first vertex absolute.

    The closing vertex a ring repeats is dropped: the page closes every ring
    itself, and a repeated vertex is a zero-length edge to test a line against.

    Args:
        coords: The ring's coordinates in degrees

    Returns:
        A flat list, ``[lon, lat, dlon, dlat, dlon, dlat, ...]`` in
        :data:`RIVER_QUANTUM` units
    """
    points = [(round(x / RIVER_QUANTUM), round(y / RIVER_QUANTUM)) for x, y in coords]
    if len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]
    out: list[int] = []
    last = (0, 0)
    for point in points:
        out.extend((point[0] - last[0], point[1] - last[1]))
        last = point
    return out


def check_rivers(entry: dict[str, Any]) -> dict[str, Any]:
    """Refuse a river table the page could not read.

    Args:
        entry: What :func:`river_table` returned, or something claiming to be

    Returns:
        The same entry

    Raises:
        ValueError: If the quantum is not a positive number, or any river is
            short of a field of :data:`RIVER_FIELDS`, or a ring has an odd
            number of values or fewer than three vertices
    """
    quantum = entry.get("quantum") if isinstance(entry, dict) else None
    if not isinstance(quantum, (int, float)) or not quantum > 0:
        raise ValueError(f"a river quantum is a positive number of degrees, not {quantum!r}")
    rivers = entry.get("rivers")
    if not isinstance(rivers, list):
        raise ValueError("the river table is a list of rivers")
    for position, river in enumerate(rivers):
        missing = sorted(set(RIVER_FIELDS) - set(river))
        if missing:
            raise ValueError(f"river {position} is short of {', '.join(missing)}")
        for ring in river["rings"]:
            if len(ring) % 2 or len(ring) < 6:
                raise ValueError(f"river {position} has a ring of {len(ring)} values, which is not three or more vertices")
    return entry


def _cells(span: float, size: float) -> int:
    """Count the cells a span needs, without a floating-point hair adding one.

    Args:
        span: Degrees to cover
        size: Degrees per cell

    Returns:
        Enough cells to cover the span, and no more: a box that is exactly four
        cells wide comes out at four, not five
    """
    return max(1, math.ceil(span / size - 1e-9))


def check_water(mask: dict[str, Any]) -> dict[str, Any]:
    """Refuse a mask entry the page could not use.

    Args:
        mask: What :func:`water_mask` produced, or what claims to be

    Returns:
        The entry, unchanged

    Raises:
        ValueError: If it is short of any of :data:`WATER_FIELDS`, or if its
            bits are not the size its rows and columns say. Either would make
            the page price every connector as ground, quietly, which is exactly
            the answer this grid exists to stop.
    """
    missing = sorted(set(WATER_FIELDS) - set(mask))
    if missing:
        raise ValueError(f"the water mask is short of {', '.join(missing)}")
    rows, cols = int(mask["rows"]), int(mask["cols"])
    packed = gzip.decompress(base64.b64decode(mask["bits"]))
    stride = (cols + 7) // 8
    if len(packed) != rows * stride:
        raise ValueError(f"the water mask says {rows} rows of {cols} cells, which is {rows * stride} bytes, and carries {len(packed)}")
    return mask
