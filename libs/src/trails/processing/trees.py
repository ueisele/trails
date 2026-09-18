"""Which box each map's own tile trees are cut to, and out of which height model.

Three trees are cut here rather than fetched -- the height tiles (§6.3), the
relief shadow (§6.6) and the slope classes (§6.7) -- and all three are cut from
one height model over one box, for one map. That box is the thing several
places have to agree on and none of them may guess:

- the three build scripts under ``analysis/scripts/``, which cut the tiles;
- :data:`trails.visualization.maps.PROVIDERS`, whose ``extent`` is *the same
  box*, because the offline panel lays a ring of tiles round what it keeps and
  a ring past the tree is a row of 404s that reads as the connection giving out
  (analysis/docs/abisko-decisions.md §8.2);
- the deploy, which mirrors ``analysis/output/<tree>/`` as it finds it.

So it is written once, here, and read from here.

**A box, not a band.** The Swedish map is built over a box already and this is
that box. The Norwegian one is built over a band round the park, whose edge
moves whenever the register redraws the boundary; the tiles are cut to a
rounded-out box that holds the band with room to spare, because a tree smaller
than the map is the one shape that must not happen.
"""

import dataclasses
import importlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..utils.tiles import Bounds

if TYPE_CHECKING:  # pragma: no cover - imported for the signature alone
    import numpy as np
    from affine import Affine


@dataclasses.dataclass(frozen=True)
class Tree:
    """The tile trees of one map: where they are cut, from what, and how deep."""

    #: The map, by the key :data:`analysis/scripts/lomsdal_visten.PARKS` uses.
    park: str
    #: The directory the trees sit under in the bucket, which is the
    #: :data:`~trails.visualization.maps.PROVIDERS` key of the sheet they are
    #: drawn over: ``dem/<provider>/<version>/{z}/{x}/{y}.png``.
    provider: str
    #: The box, ``(min_lon, min_lat, max_lon, max_lat)``. Every tile of it at
    #: every level below is cut, and not one outside it.
    box: Bounds
    #: The module that reads the model, by name: a key of :data:`MODELS`.
    model: str
    #: Post spacing the model is read at, in metres. Four, on both maps: it is
    #: the first level finer than a z13 tile pixel at either latitude, so a
    #: bilinear tile never averages posts the model does not have.
    posts_m: float = 4.0
    #: The coarsest level of every tree. At z8 a box of this size is a handful
    #: of tiles and the offline panel's estimate wants them.
    min_zoom: int = 8
    #: The finest height tile: at 65–68° N a z13 pixel is 7–8 m, and finer
    #: tiles would be the same numbers on a finer grid (§6.3).
    dem_max_zoom: int = 13
    #: The finest relief and slope tile. Not for the usual reason: z14 and z15
    #: draw the same ground, and what the deeper tree buys is that the image is
    #: not blown up at the z16 the offline panel keeps to (§6.6).
    ground_max_zoom: int = 15
    #: The version segment of each tree. A tree whose tiles change is a new
    #: address and never a changed object, or a phone would mix two builds.
    dem_version: int = 1
    shade_version: int = 1
    slope_version: int = 1
    vegetation_version: int = 1
    forest_version: int = 1
    #: The module that reads the laser's word on what stands on the ground,
    #: by name: a key of :data:`STRUCTURES`. The vegetation and forest trees
    #: (§6.11) are cut from it rather than from the height model; None for a
    #: map that has no such source, and then those two trees are not cut.
    structure: str | None = None

    def prefix(self, tree: str) -> str:
        """Where one of the trees is addressed from, root-relative.

        Args:
            tree: ``dem``, ``shade``, ``slope``, ``vegetation`` or ``forest``

        Returns:
            The address every tile of it starts with

        Raises:
            KeyError: If ``tree`` is not one of the five
        """
        version = {
            "dem": self.dem_version, "shade": self.shade_version, "slope": self.slope_version,
            "vegetation": self.vegetation_version, "forest": self.forest_version,
        }[tree]  # fmt: skip
        return f"/{tree}/{self.provider}/{version}/"

    def zooms(self, tree: str) -> range:
        """The levels one of the trees is cut over.

        Args:
            tree: ``dem``, ``shade``, ``slope``, ``vegetation`` or ``forest``

        Returns:
            The levels, coarsest first

        Raises:
            KeyError: If ``tree`` is not one of the five
        """
        top = {
            "dem": self.dem_max_zoom, "shade": self.ground_max_zoom, "slope": self.ground_max_zoom,
            "vegetation": self.ground_max_zoom, "forest": self.ground_max_zoom,
        }[tree]  # fmt: skip
        return range(self.min_zoom, top + 1)


#: What each model is called where a script has to name one, and what reads it.
#: The value is the module path, resolved by the scripts rather than imported
#: here: this module is read to find out *which* model, long before one is read.
MODELS = {
    "markhojd": "trails.io.sources.markhojd",
    "hoydedata-dtm": "trails.io.sources.hoydedata_dtm",
}

#: And what reads the vegetation codes, the same way: Sweden's are published
#: classed, Norway's are computed from its two height models, and both answer
#: with NMD's three code bands at 10 m (§6.11).
STRUCTURES = {
    "nmd": "trails.io.sources.nmd",
    "hoydedata-vegetation": "trails.io.sources.hoydedata_vegetation",
}


def read_model(tree: Tree, cache_dir: str | Path, force_download: bool = False) -> tuple[np.ndarray, Affine, str, float]:
    """The height model over one map's box, and the three things cutting it needs.

    The two models are read by different modules -- one through a STAC API with
    a login, one through a keyless image service -- and answer with the same
    pair, so the three cutters do not know which map they are cutting. The
    module is resolved here rather than imported at the top, because naming a
    model is a great deal cheaper than reading one.

    Args:
        tree: The map's trees
        cache_dir: Where the model's cache lives
        force_download: Read the model again rather than its cache

    Returns:
        The heights (rows from the north), their georeferencing, the projection
        they are in, and what the model writes where it has nothing
    """
    module: Any = importlib.import_module(MODELS[tree.model])
    heights, transform = module.Source(cache_dir=cache_dir).mosaic(tree.box, posts_m=tree.posts_m, force_download=force_download)
    return heights, transform, module.CRS, module.NODATA


def read_structure(tree: Tree, cache_dir: str | Path, force_download: bool = False) -> tuple[np.ndarray, Affine, str]:
    """The vegetation codes over one map's box, and what cutting them needs.

    Args:
        tree: The map's trees
        cache_dir: Where the source's cache lives
        force_download: Read the source again rather than its cache

    Returns:
        The three code bands (rows from the north), their georeferencing, and
        the projection they are in

    Raises:
        ValueError: If the map names no structure source
    """
    if tree.structure is None:
        raise ValueError(f"{tree.park} names no vegetation source; nothing to cut")
    module: Any = importlib.import_module(STRUCTURES[tree.structure])
    codes, transform = module.Source(cache_dir=cache_dir).structure(tree.box, force_download=force_download)
    return codes, transform, module.CRS


#: One entry per map that carries trees of its own.
TREES: dict[str, Tree] = {
    # The band the Norwegian map draws -- 15 km round the park, measured
    # 12.056–13.695 E and 65.175–65.921 N on the build of 2026-09-17 -- rounded
    # out to quarter and twentieth degrees, so the band lies strictly inside it
    # and a boundary the register redraws does not put the map outside its own
    # tiles. 78 × 86 km of ground; 37,915 tiles per ground tree, 2,475 heights.
    "lomsdal-visten": Tree(
        park="lomsdal-visten",
        provider="kartverket",
        box=(12.0, 65.15, 13.75, 65.95),
        model="hoydedata-dtm",
        # Kartverket's surface model less its terrain model, classed to NMD's
        # codes (§6.11).
        structure="hoydedata-vegetation",
    ),
    # The Abisko box itself (§2, widened §9.24): the sheet was copied for it and
    # the height mosaic read over it, so the graph, the water grid, the page and
    # these three trees all cover exactly it.
    "abisko": Tree(
        park="abisko",
        provider="lantmateriet",
        box=(18.15, 68.139, 19.10, 68.46),
        model="markhojd",
        # Two since the classes went to seven and the palette to the light one
        # drawn multiplied (§6.7).
        slope_version=2,
        # Naturvårdsverket's NMD 2018 object height and cover (§6.11).
        structure="nmd",
    ),
}
