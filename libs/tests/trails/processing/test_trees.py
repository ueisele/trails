"""The one place the tile trees' boxes, models and versions are written down."""

import pytest
from trails.processing import trees
from trails.utils.tiles import tile_range


class TestPrefix:
    def test_a_tree_is_addressed_by_its_own_version(self):
        abisko = trees.TREES["abisko"]
        assert abisko.prefix("dem") == "/dem/lantmateriet/1/"
        assert abisko.prefix("shade") == "/shade/lantmateriet/1/"
        # Two since the seven classes and the light palette (§6.7).
        assert abisko.prefix("slope") == "/slope/lantmateriet/2/"

    def test_the_two_maps_are_stacked_and_never_mixed(self):
        """A directory per source, which is what §6.3's address line is for."""
        for tree in ("dem", "shade", "slope", "vegetation", "forest"):
            swedish = trees.TREES["abisko"].prefix(tree)
            norwegian = trees.TREES["lomsdal-visten"].prefix(tree)
            assert swedish != norwegian
            assert swedish.startswith(f"/{tree}/") and norwegian.startswith(f"/{tree}/")

    def test_a_tree_nobody_cuts_is_a_named_failure(self):
        with pytest.raises(KeyError):
            trees.TREES["abisko"].prefix("heather")

    def test_both_maps_name_a_vegetation_source(self):
        """Sweden's classes come published, Norway's are computed; both are cut (§6.11)."""
        assert trees.TREES["abisko"].structure == "nmd"
        assert trees.TREES["lomsdal-visten"].structure == "hoydedata-vegetation"
        assert set(trees.STRUCTURES) == {"nmd", "hoydedata-vegetation"}


class TestZooms:
    def test_the_heights_stop_shallower_than_the_ground_layers(self):
        """z13 for the heights, because a pixel there is the model's own
        resolution; z15 for the relief and the slope, because what the deeper
        tree buys is that the image is not blown up at z16 (§6.6)."""
        for tree in trees.TREES.values():
            assert list(tree.zooms("dem"))[-1] == 13
            assert list(tree.zooms("shade"))[-1] == list(tree.zooms("slope"))[-1] == 15
            assert tree.zooms("dem").start == tree.zooms("shade").start == 8


class TestBoxes:
    def test_the_norwegian_box_holds_the_band_the_map_draws(self):
        """The band measured 12.056–13.695 E, 65.175–65.921 N on the build of
        2026-09-17. The box is that rounded outwards — and it must be outwards,
        or the offline panel's ring falls off the tree (§8.2, §6.10)."""
        west, south, east, north = trees.TREES["lomsdal-visten"].box
        assert west < 12.055613 and east > 13.694636
        assert south < 65.174945 and north > 65.921291

    def test_every_box_is_west_south_east_north(self):
        for tree in trees.TREES.values():
            west, south, east, north = tree.box
            assert west < east and south < north

    def test_the_posts_are_finer_than_a_z13_pixel_on_both_maps(self):
        """The rule §6.3 set and §6.10 kept: read the model one level finer than
        the finest tile pixel, so the bilinear warp never averages posts the
        model does not have. A z13 pixel is 7.07 m at Abisko and 7.91 m here."""
        from trails.utils.tiles import tile_resolution

        for tree in trees.TREES.values():
            middle = (tree.box[1] + tree.box[3]) / 2.0
            assert tree.posts_m < tile_resolution(tree.dem_max_zoom, middle)

    def test_what_the_boxes_cost_in_tiles(self):
        """Recorded so that a box quietly widened shows up as a number rather
        than as an afternoon of building."""
        counted = {}
        for park, tree in trees.TREES.items():
            total = 0
            for zoom in tree.zooms("shade"):
                x0, y0, x1, y1 = tile_range(tree.box, zoom)
                total += (x1 - x0 + 1) * (y1 - y0 + 1)
            counted[park] = total
        assert counted == {"lomsdal-visten": 37_915, "abisko": 9_330}


class TestModels:
    def test_every_tree_names_a_model_that_is_there(self):
        import importlib

        for tree in trees.TREES.values():
            module = importlib.import_module(trees.MODELS[tree.model])
            # What `read_model` needs of one, checked here rather than on a
            # build that has already spent twenty minutes reading squares.
            assert hasattr(module, "Source") and hasattr(module, "CRS") and hasattr(module, "NODATA")
            assert hasattr(module.Source, "mosaic")

    def test_every_model_states_its_height_datum(self):
        """`atlas` §6.2: a model delivered on the ellipsoid reads 20–45 m high
        over Norway with nothing to show for it, so the datum is a required
        field and is asserted rather than trusted."""
        import importlib

        for tree in trees.TREES.values():
            module = importlib.import_module(trees.MODELS[tree.model])
            assert module.METADATA.datum in ("NN2000", "RH 2000")
