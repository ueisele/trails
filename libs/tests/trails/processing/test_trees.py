"""The one place the tile trees' boxes, models and versions are written down."""

import dataclasses

import pytest
from trails.processing import trees
from trails.utils.tiles import tile_count


class TestPrefix:
    def test_a_tree_is_addressed_by_its_own_version(self):
        abisko = trees.TREES["abisko"]
        assert abisko.prefix("dem") == "/dem/lantmateriet/1/"
        assert abisko.prefix("shade") == "/shade/lantmateriet/1/"
        # Two since the seven classes and the light palette (§6.7).
        assert abisko.prefix("slope") == "/slope/lantmateriet/2/"

    def test_every_map_has_its_own_tree_directories(self):
        """A version change in one box must never replace another box's tiles."""
        for layer in ("dem", "shade", "slope", "vegetation", "forest", "mire"):
            prefixes = [tree.prefix(layer) for tree in trees.TREES.values()]
            assert len(set(prefixes)) == len(trees.TREES)
            assert all(prefix.startswith(f"/{layer}/") for prefix in prefixes)

    def test_a_tree_nobody_cuts_is_a_named_failure(self):
        with pytest.raises(KeyError):
            trees.TREES["abisko"].prefix("heather")

    def test_every_map_names_a_vegetation_source(self):
        """Sweden's classes come published, Norway's are computed; both are cut (§6.11)."""
        for tree in trees.TREES.values():
            assert tree.structure == ("nmd" if tree.provider.startswith("lantmateriet") else "hoydedata-vegetation")
        assert trees.TREES["lomsdal-visten"].structure == "hoydedata-vegetation"
        assert set(trees.STRUCTURES) == {"nmd", "hoydedata-vegetation"}

    def test_every_map_names_a_mire_source_and_the_tree_is_addressed_like_the_others(self):
        """Sweden's off the sheet's wetlands and the moisture model, Norway's off N50's bogs (§6.13)."""
        for tree in trees.TREES.values():
            assert tree.mire == ("marktacke-slu" if tree.provider.startswith("lantmateriet") else "n50")
        assert trees.TREES["lomsdal-visten"].mire == "n50"
        assert set(trees.MIRES) == {"marktacke-slu", "n50"}
        assert trees.TREES["abisko"].prefix("mire") == "/mire/lantmateriet/3/"
        assert trees.TREES["lomsdal-visten"].zooms("mire") == range(8, 16)
        with pytest.raises(ValueError, match="names no mire source"):
            trees.read_mire(dataclasses.replace(trees.TREES["abisko"], mire=None), "unused")


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
        counted = {park: tile_count(tree.box, tree.zooms("shade")) for park, tree in trees.TREES.items()}
        assert counted == {"lomsdal-visten": 37_915, "abisko": 9_330, "malingsbo-kloten": 9_756}

    def test_the_new_map_starts_each_tree_at_version_one(self):
        tree = trees.TREES["malingsbo-kloten"]
        for layer in ("dem", "shade", "slope", "vegetation", "forest", "mire"):
            assert tree.prefix(layer) == f"/{layer}/lantmateriet-malingsbo-kloten/1/"


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
