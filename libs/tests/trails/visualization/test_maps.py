"""Tests for Folium map building."""

import ast
import base64
import hashlib
import json
import math
import pathlib
import re
import shutil
import struct
import subprocess
import tempfile
import zipfile
import zlib
from importlib.resources import files

import folium
import geopandas as gpd
import pytest
from lxml import etree
from shapely.geometry import LineString, MultiLineString, Point, Polygon
from trails.io.export.gpx import export_to_gpx
from trails.processing import mire_tiles, packs, slope_tiles, vegetation_tiles
from trails.routing.sources import BRIDGE, FERRY
from trails.visualization import maps


@pytest.fixture
def trails() -> gpd.GeoDataFrame:
    """Two trail segments, one of them a MultiLineString."""
    return gpd.GeoDataFrame(
        {
            "trail_name": ["Sjøbergmarsjen", None],
            "difficulty": ["Easy (Green)", None],
            "geometry": [
                LineString([(12.8, 65.4), (12.81, 65.41)]),
                MultiLineString([[(12.9, 65.5), (12.91, 65.51)], [(12.92, 65.52), (12.93, 65.53)]]),
            ],
        },
        crs="EPSG:4326",
    )


@pytest.fixture
def park() -> gpd.GeoDataFrame:
    """A square park boundary."""
    return gpd.GeoDataFrame(
        {"navn": ["Lomsdal-Visten"], "geometry": [Polygon([(12.4, 65.3), (13.3, 65.3), (13.3, 65.7), (12.4, 65.7)])]},
        crs="EPSG:4326",
    )


@pytest.fixture
def shelters() -> gpd.GeoDataFrame:
    """Two point features."""
    return gpd.GeoDataFrame(
        {"name": ["Stavassgården", None], "kind": ["wilderness_hut", "shelter"], "geometry": [Point(12.85, 65.45), Point(12.86, 65.46)]},
        crs="EPSG:4326",
    )


#: Everything between a `vendored:` fence and its close, which is somebody
#: else's file written into the page.
VENDORED = re.compile(r"<!-- vendored:.*?/vendored:[a-z_]+ -->", re.S)


def ours(html: str) -> str:
    """The page with the third-party files it carries inline taken out.

    Leaflet and jQuery are written into the page rather than linked from a CDN,
    which on a slow connection is worth three DNS lookups and three TLS
    handshakes. Their source is not this page's, though: Leaflet carries
    `http://` addresses in its own comments and defines a function called
    `disableScrollPropagation`, and two checks about what *this* page does began
    reading what Leaflet does.

    Args:
        html: A rendered page.

    Returns:
        The same page without the fenced third-party blocks.
    """
    return VENDORED.sub("", html)


class TestCreateMap:
    """Tests for create_map."""

    def test_centers_on_bounds(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        assert fmap.location == [65.5, 12.9]

    def test_accepts_explicit_center(self):
        fmap = maps.create_map(center=(65.5, 12.9))
        assert fmap.location == [65.5, 12.9]

    def test_requires_bounds_or_center(self):
        with pytest.raises(ValueError, match="bounds or center"):
            maps.create_map()

    def test_uses_kartverket_tiles_by_default(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        assert "/tiles/kartverket/topo/1/{z}/{x}/{y}.png" in fmap.get_root().render()

    @pytest.mark.parametrize("base", list(maps.BaseMap))
    def test_every_tile_layer_waits_for_the_pinch_and_has_a_transparent_error_tile(self, base):
        fmap = maps.create_map(center=(68.30, 18.70), base=base, extra_bases=tuple(maps.BaseMap))
        layers = [child for child in fmap._children.values() if isinstance(child, folium.TileLayer)]
        assert len(layers) == (4 if base is maps.BaseMap.OPENSTREETMAP else 9)
        for layer in layers:
            assert layer.options["update_when_zooming"] is False
            assert layer.options["update_when_idle"] is False
            assert layer.options["keep_buffer"] == 4
            uri = layer.options["error_tile_url"]
            assert uri.startswith("data:image/png;base64,")
            png = base64.b64decode(uri.split(",", 1)[1])
            assert png[:8] == b"\x89PNG\r\n\x1a\n"
            assert struct.unpack(">IIBB", png[16:26]) == (1, 1, 8, 6), "one RGBA pixel"
            start = png.index(b"IDAT")
            size = struct.unpack(">I", png[start - 4 : start])[0]
            assert zlib.decompress(png[start + 4 : start + 4 + size]) == b"\0" * 5, "unfiltered transparent black"
        html = ours(fmap.get_root().render())
        assert html.count('"updateWhenZooming": false') == len(layers)
        assert html.count('"updateWhenIdle": false') == len(layers)
        assert html.count('"keepBuffer": 4') == len(layers)
        assert html.count('"errorTileUrl": "data:image/png;base64,') == len(layers)

    @pytest.mark.parametrize("base", list(maps.BaseMap))
    def test_only_base_tile_layers_retain_ground(self, base):
        fmap = maps.create_map(center=(68.30, 18.70), base=base, extra_bases=tuple(maps.BaseMap))
        layers = [child for child in fmap._children.values() if isinstance(child, folium.TileLayer)]
        assert layers[0].overlay is False
        for layer in layers:
            if layer.overlay:
                assert "retain_ground" not in layer.options
            else:
                assert layer.options["retain_ground"] is True
        html = ours(fmap.get_root().render())
        assert html.count('"retainGround": true') == sum(not layer.overlay for layer in layers)
        for removed in ("trails-zoom-blend", "trails-tiles-plain", "URLSearchParams(location.search)"):
            assert removed not in html

    def test_only_the_base_with_its_own_tree_is_bounded(self):
        fmap = maps.create_map(center=(68.30, 18.70), base=maps.BaseMap.LANTMATERIET_TOPO, extra_bases=tuple(maps.BaseMap))
        layers = [child for child in fmap._children.values() if isinstance(child, folium.TileLayer)]
        for layer in layers:
            if layer.overlay or layer.layer_name == "Lantmäteriet Topo":
                assert layer.options["bounds"] == [[68.139, 18.15], [68.46, 19.1]]
            elif layer.layer_name.startswith("Kartverket"):
                assert layer.options["bounds"] == [[65.15, 12.0], [65.95, 13.75]]
            else:
                assert "bounds" not in layer.options, "OSM answers beyond the tree"

    def test_sheet_retention_precedes_any_tile_layer(self):
        html = ours(maps.create_map(center=(65.55, 13.05)).get_root().render())
        start = html.index("L.GridLayer.include({")
        end = html.index("L.tileLayer(", start)
        pruning = html[start:end]
        assert "if (!this._map) { return; }" in pruning
        assert "zoom > this.options.maxZoom || zoom < this.options.minZoom" in pruning
        assert "this._removeAllTiles();" in pruning
        assert "tile.retain = tile.current;" in pruning
        assert "if (this.options.retainGround && tile.current && !tile.active)" in pruning
        assert "if (!this._retainParent(coords.x, coords.y, coords.z, coords.z - 5))" in pruning
        assert "this._retainChildren(coords.x, coords.y, coords.z, coords.z + 3);" in pruning
        assert "if (!this._tiles[key].retain) { this._removeTile(key); }" in pruning

    @pytest.mark.parametrize("base", list(maps.BaseMap))
    def test_every_page_loads_one_ring_at_the_tile_scale_before_any_tile_layer(self, base):
        html = ours(maps.create_map(center=(65.55, 13.05), base=base).get_root().render())
        start = html.index("var TILE_RING = 1;")
        end = html.index("L.tileLayer(")
        assert start < end
        ring = html[start:end]
        assert "var tiledPixelBounds = L.GridLayer.prototype._getTiledPixelBounds;" in ring
        assert "L.GridLayer.include({" in ring
        assert "_getTiledPixelBounds: function (center)" in ring
        assert "var bounds = tiledPixelBounds.call(this, center);" in ring
        assert "var margin = this.getTileSize().multiplyBy(TILE_RING);" in ring
        assert "return L.bounds(bounds.min.subtract(margin), bounds.max.add(margin));" in ring
        assert html.count("var TILE_RING = 1;") == 1

    # **Base layers only.** Since §6.10 a map on Kartverket's sheet also carries
    # the relief and the slope classes, which are tile layers too -- but they are
    # overlays, drawn over whichever sheet is chosen rather than instead of it.
    @staticmethod
    def sheets(fmap):
        """The base layers of a map, which is what the picker chooses between."""
        return [child for child in fmap._children.values() if isinstance(child, folium.TileLayer) and not child.overlay]

    def test_adds_extra_base_layers(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7), extra_bases=(maps.BaseMap.OPENSTREETMAP,))
        assert len(self.sheets(fmap)) == 2

    def test_base_layers_are_named_not_labelled_with_urls(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7), extra_bases=(maps.BaseMap.KARTVERKET_GRAYSCALE,))
        names = sorted(layer.layer_name for layer in self.sheets(fmap))
        assert names == ["Kartverket Grayscale", "Kartverket Topo"]

    def test_grayscale_uses_the_same_pack_backed_sheet(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7), extra_bases=(maps.BaseMap.KARTVERKET_GRAYSCALE,))
        colour, gray = self.sheets(fmap)
        assert gray.tiles == colour.tiles == "/tiles/kartverket/topo/1/{z}/{x}/{y}.png"
        assert gray.options["class_name"] == "trails-grayscale"
        assert ".trails-grayscale { filter: grayscale(1); }" in fmap.get_root().render()

    def test_only_the_primary_base_is_displayed_on_load(self):
        # Leaflet stacks every base layer it is given, so a visible extra would
        # cover the primary one entirely.
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7), extra_bases=(maps.BaseMap.OPENSTREETMAP,))
        shown = [layer for layer in self.sheets(fmap) if layer.show]
        assert len(shown) == 1
        assert "kartverket" in shown[0].tiles.lower()

    def test_openstreetmap_is_not_a_default_extra(self):
        # OSM tiles 403 on file:// URLs because no Referer is sent.
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        rendered = fmap.get_root().render()
        assert "tile.openstreetmap.org" not in rendered

    def test_does_not_duplicate_the_primary_base(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7), base=maps.BaseMap.OPENSTREETMAP, extra_bases=(maps.BaseMap.OPENSTREETMAP,))
        assert len(self.sheets(fmap)) == 1


class TestWhatThePageFetches:
    """What a reader has to reach a third party for, and what they do not.

    Measured on the published map before any of this: **832 kB over four hosts**,
    and on a slow link the four DNS lookups and four TLS handshakes cost more
    than the bytes -- some 2.8 seconds at a 200 ms round trip, spent before the
    map can draw a line.
    """

    def built(self) -> str:
        """A rendered page with nothing added to it."""
        return maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7)).get_root().render()

    def test_three_of_foliums_defaults_are_dropped(self):
        """Each was taken out of a built page on its own and the page driven.

        `bootstrap.min.css` (194,901 B) and `bootstrap.bundle.min.js` (80,496 B)
        changed **nothing measurable** once the two rules they were really
        providing are said here. `bootstrap-glyphicons.css` (13,018 B) had one
        effect, the attribution's size, and it came from its own host.
        """
        html = self.built()
        assert "bootstrap.min.css" not in html
        assert "bootstrap.bundle.min.js" not in html
        assert "bootstrap-glyphicons.css" not in html
        # What they were for, said in three rules rather than 288 kB.
        assert "*, *::before, *::after { box-sizing: border-box; }" in html
        assert "font-size: 10px !important;" in html

    def test_the_webfont_is_gone_and_the_outlines_are_not(self):
        """252 kB of stylesheet and webfont bought exactly four glyphs.

        The outlines are Font Awesome's own, so the markers are unchanged to the
        pixel, and awesome-markers still writes the same `<i class="fa fa-...">`.
        Thirteen more since 2026-09-17, at about a kilobyte of path each: the
        glyph says what a place is for, and a bed, a roof and a ford are not
        one house.
        """
        html = self.built()
        assert "fontawesome-free" not in html
        assert {"house-chimney", "campground", "ship", "anchor"} <= set(maps.MARKER_ICONS)
        assert {
            "bed",
            "house",
            "person-shelter",
            "tent",
            "train",
            "bus",
            "bridge",
            "water",
            "phone",
            "square-parking",
            "restroom",
            "fire",
            "circle-info",
        } <= set(maps.MARKER_ICONS)
        # Each one a viewBox and a path, and nothing the size of a webfont.
        for box, path in maps.MARKER_ICONS.values():
            assert box.startswith("0 0 ")
            assert len(path) < 2000
        for name in maps.MARKER_ICONS:
            assert f".awesome-marker i.fa-{name} {{ background-image:" in html
        # And the notice travels with them, as it does in the stylesheet this
        # replaces: the icons are CC BY 4.0.
        assert "CC BY 4.0" in maps.__doc__ or "Fonticons" in pathlib.Path(maps.__file__).read_text(encoding="utf-8")

    def test_leaflet_and_jquery_are_written_into_the_page(self):
        """A handshake cannot be pipelined and a download can.

        Fenced by a comment naming each, so a reader can see where somebody
        else's code begins and a check can cut it out.
        """
        html = self.built()
        assert "<!-- vendored:leaflet -->" in html
        assert "<!-- vendored:jquery -->" in html
        assert "leaflet@1.9.3/dist/leaflet.js" not in html
        assert 'src="https://code.jquery.com' not in html
        # **An `Element` and not a `MacroElement`, which cost a build.** A
        # macro's header block renders with the map's *children*, and folium
        # writes its own `<script src>` links while rendering the map -- so an
        # inlined Leaflet landed after the script that uses it and the page came
        # up with `L is not defined`. Leaflet has to be first in the header.
        assert html.index("<!-- vendored:leaflet -->") < html.index("L.map(")

    def test_no_third_party_host_is_left(self):
        """**None.** The map draws its own pins now, which is what awesome-markers
        was for -- 42,683 bytes of script, stylesheet and rotation rules plus four
        sprite images, for a coloured teardrop with a glyph in it.

        Read through `ours`, because Leaflet's own attribution names
        leafletjs.com and that is a string it writes, not a file it fetches.
        """
        html = ours(self.built())
        hosts = {address.split("/")[2] for address in re.findall(r'(?:src|href)="(https://[^"]+)"', html)}
        assert hosts == set(), hosts


class TestServiceWorker:
    """The map, when there is no network to fetch it with."""

    def test_the_worker_is_stamped_with_the_page_it_was_built_beside(self, tmp_path):
        """A browser installs a worker only when its bytes change. So the stamp
        is the page's own digest: a deploy that changes the map changes the
        worker, which changes the cache name, which drops the old map -- and a
        rebuild that changes nothing changes nothing."""
        page = tmp_path / "lomsdal-visten.html"
        page.write_text("<html>a map</html>", encoding="utf-8")
        written = maps.write_service_worker(page)
        assert written.name == "sw.js"
        first = written.read_text(encoding="utf-8")
        assert "__VERSION__" not in first
        assert maps.write_service_worker(page).read_text(encoding="utf-8") == first

        page.write_text("<html>a different map</html>", encoding="utf-8")
        assert maps.write_service_worker(page).read_text(encoding="utf-8") != first

    def test_it_keeps_the_page_by_the_address_it_was_opened_at(self):
        """The worker does not know what the map is called: the object is
        `lomsdal-visten.html` in the bucket and is served at `/lomsdal-visten`,
        and a cache keyed on the wrong one of those answers nothing.

        Without this the map is not cached until the *second* visit -- the first
        registers a worker that was not there to intercept it -- so offline would
        work from the third."""
        assert "function keepWhatIsOpen()" in maps.SERVICE_WORKER
        assert 'self.clients.matchAll({type: "window"})' in maps.SERVICE_WORKER
        assert "return write(PAGES, client.url, made);" in maps.SERVICE_WORKER

    def test_the_document_is_stale_first_and_the_tiles_are_cache_first(self):
        """A reader gets the map they already have, at no bytes, and the new one
        lands for the next visit. Terrain does not change while somebody walks
        over it, so a tile that is held is simply served."""
        assert 'if (request.mode === "navigate")' in maps.SERVICE_WORKER
        assert "return kept || fresh;" in maps.SERVICE_WORKER
        assert "if (kept) { return kept; }" in maps.SERVICE_WORKER
        # Bounded, because a cache with no ceiling is a quota with no floor.
        assert "var TILE_CAP = 150 * 1000 * 1000;" in maps.SERVICE_WORKER
        assert "function trim(store, total, done, removedKey)" in maps.SERVICE_WORKER

    def test_it_is_registered_only_where_a_worker_can_exist(self):
        """A worker needs a secure origin, so a page opened off the disk gets
        none -- which is also why the suite serves the built page over HTTP to
        drive any of this."""
        html = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7)).get_root().render()
        assert "navigator.serviceWorker.register('sw.js')" in html
        assert "location.protocol === 'https:'" in html
        assert "location.hostname === 'localhost'" in html
        # And why it is not there, when it is not: a page that silently has no
        # offline copy looks exactly like one that has.
        assert "window.trailsWorker.why" in html
        # **The origin is asked about first.** WebKit hides
        # `navigator.serviceWorker` entirely off a secure origin, so a check
        # that asks about the browser first calls Safari over http:// a browser
        # without workers -- which is how a reader on the real site was sent
        # looking for a browser they were already using.
        origin, browser = (
            html.index("window.trailsWorker.why = 'not a secure origin'"),
            html.index("window.trailsWorker.why = 'no worker in this browser'"),
        )
        assert origin < browser

    def test_a_reader_is_told_when_a_newer_map_is_waiting(self):
        """Stale-first means a fix arrives one visit late. The line is a plain
        one in the corner with a way out, not a sheet: a panel that opens itself
        is a panel that interrupts."""
        html = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7)).get_root().render()
        assert "A newer map is ready" in html
        assert "trails-newer-close" in html


class TestOfflineWorker:
    """What the worker does with terrain somebody asked for, as against terrain
    they happened to pan over."""

    def test_one_store_uses_disjoint_key_only_indexes(self):
        worker = maps.SERVICE_WORKER
        assert 'var KEPT = "packs";' in worker
        assert "var SEEN =" not in worker
        assert 'open.transaction([KEPT, FLAGS], "readonly")' in worker
        assert 'row.kept ? "db" : "seen"' in worker
        assert 'store.index("browsed-at").openKeyCursor()' in worker
        assert "store.index('kept').openKeyCursor(bounds)" in worker
        assert "openCursor(" not in worker and "getAll(" not in worker

    def test_every_cache_an_earlier_version_wrote_is_swept(self):
        """Nothing reads a cache any longer, so whatever is left in one is
        unreachable — gigabytes on a phone no code can answer from, which is
        worse than deleting them. It runs on activation, after the navigation
        has been answered: `caches.keys()` is the call measured at 23 seconds
        on a phone with the ground kept, and it must not happen in front of
        anybody."""
        assert 'var CAST_OFF = new RegExp("^__CACHE__-(page-|state$|terrain$|tiles$)");' in maps.SERVICE_WORKER
        sweep = maps.SERVICE_WORKER.split("function sweepOldCaches()")[1].split("\nfunction ")[0]
        assert "CAST_OFF.test(name) ? caches.delete(name) : null" in sweep

    def test_the_sweep_is_scoped_to_its_own_map(self, tmp_path):
        """Two maps on one origin share Cache Storage. The first map's sweep
        must not take the second's kept ground for a cast-off, nor the other way
        round -- so the pattern carries the map's own cache prefix, and the
        alternatives after it start with what a sibling's never does."""
        page = tmp_path / "lomsdal-visten.html"
        page.write_text("<html></html>", encoding="utf-8")
        first = maps.write_service_worker(page).read_text(encoding="utf-8")
        assert 'var CAST_OFF = new RegExp("^trails-(page-|state$|terrain$|tiles$)");' in first
        second = maps.write_service_worker(page, maps.PROVIDERS["lantmateriet"], maps.Companions.named("abisko")).read_text(encoding="utf-8")
        assert 'var CAST_OFF = new RegExp("^trails-abisko-(page-|state$|terrain$|tiles$)");' in second
        pattern = re.compile("^trails-(page-|state$|terrain$|tiles$)")
        assert pattern.match("trails-tiles") and not pattern.match("trails-abisko-tiles")
        pattern = re.compile("^trails-abisko-(page-|state$|terrain$|tiles$)")
        assert pattern.match("trails-abisko-tiles") and not pattern.match("trails-tiles")

    def test_nothing_on_the_way_to_a_tile_touches_a_cache(self):
        """A cache read anywhere in this path brings back the cost the whole
        change was about: the first `caches.open()` of any cache is 23.2 s on a
        phone with the ground kept, whichever cache it happens to be."""
        tile = maps.SERVICE_WORKER.split("function tileFor(request, event)")[1].split("\nfunction ")[0]
        assert "caches." not in tile
        assert "fromLegacy" not in maps.SERVICE_WORKER

    def test_the_old_page_caches_are_swept_after_the_navigation(self):
        """Every deploy used to mint a cache named after the page's digest and
        hold 15.7 MB in it, so a reader who has been through a few is carrying
        several. The one thing the sweep must not do is happen in front of
        somebody: `caches.keys()` is the call measured at 23 s on a phone with
        the ground kept."""
        activate = maps.SERVICE_WORKER.split('addEventListener("activate"')[1].split("\nfunction ")[0]
        assert "self.clients.claim().then(keepWhatIsOpen).then(sweepOldCaches)" in activate

    def test_a_row_is_replaced_in_place_so_nothing_has_to_be_carried_over(self):
        """Fetch before you evict was a whole dance when the page lived in a
        cache named after a digest: the new one had to be filled before the old
        was dropped, and a worker whose fetch failed had to move the old copy
        across by hand. A row keyed by the address is replaced where it lies."""
        assert "carryOver" not in maps.SERVICE_WORKER
        paging = maps.SERVICE_WORKER.split("function pageFor(request)")[1].split("\nfunction ")[0]
        assert "rowFor(answer).then(function (made) { return write(PAGES, request.url, made); });" in paging

    def test_the_switch_survives_the_worker_being_killed(self):
        """A service worker is not a process that stays alive: the browser starts
        it for a fetch and stops it again, and every variable it held goes with
        it. A flag living only in that scope would be true on the first tile of a
        walk and false on the second."""
        assert 'var STATE = "offline";' in maps.SERVICE_WORKER
        assert "function offlineNow()" in maps.SERVICE_WORKER
        assert "read(FLAGS, STATE)" in maps.SERVICE_WORKER
        assert 'write(FLAGS, STATE, on ? "on" : "off")' in maps.SERVICE_WORKER
        # Memoised, and the memo replaced rather than left when the page speaks.
        assert "switched = Promise.resolve(!!on);" in maps.SERVICE_WORKER

    def test_a_tile_that_is_not_kept_is_a_blank_and_not_a_failure(self):
        """Offline, Leaflet drawing a broken image over the terrain says the page
        is wrong; drawing nothing says the ground was not kept, which is true."""
        assert "function blank()" in maps.SERVICE_WORKER
        assert 'status: 200, headers: {"content-type": "image/png"}' in maps.SERVICE_WORKER
        assert 'if (off) { answered("blank"); return blank(); }' in maps.SERVICE_WORKER
        # Every path retains a count and adds only two time accumulators; no
        # samples are retained as the number of tiles grows.
        assert "var told = {mem: 0, db: 0, seen: 0, legacy: 0, net: 0, blank: 0, why: null, at: 0};" in maps.SERVICE_WORKER
        for path in ("mem", "db", "seen", "net", "blank"):
            assert f"{path}: {{total: 0, worst: 0}}" in maps.SERVICE_WORKER
        assert "told.time[which].total += spent;" in maps.SERVICE_WORKER
        assert "told.time[which].worst = Math.max(told.time[which].worst, spent);" in maps.SERVICE_WORKER
        assert 'answered(body ? "net" : "blank")' in maps.SERVICE_WORKER

    def test_tile_deadlines_and_concurrency_are_counted_without_changing_the_throttle(self):
        worker = maps.SERVICE_WORKER
        assert "if (!missed) { missed = true; told.deadlines += 1; }" in worker
        assert "told.peak = Math.max(told.peak, inFlight);" in worker
        assert ".finally(function () { inFlight -= 1; });" in worker
        assert "clearTimeout(timer); done(value);" in worker
        assert "clearTimeout(timer); fail(error);" in worker
        assert "}, 400);" in worker
        assert "if (Date.now() - told.at < 1000) { return; }" in worker

    def test_a_lookup_has_one_deadline_and_coalesces_per_tick(self):
        worker = maps.SERVICE_WORKER
        tile = worker.split("function tileFor(request, event)")[1].split("\nfunction ")[0]
        assert tile.count("within(") == 1
        assert "within(2500, lookup(address.url, state, plain), null, late)" in tile
        assert "state.expired = true;" in tile
        assert "setTimeout(flushLookups, 0)" in worker
        assert "if (items.every(function (item) { return item.state.expired; }))" in worker
        assert "migrateStand" not in worker

    def test_warm_lookups_place_a_get_before_yielding_the_new_transaction(self):
        """WebKit can commit an empty transaction before its complete event."""
        lookup = maps.SERVICE_WORKER.split("function flushLookups()")[1].split("\nfunction ")[0]
        creation = lookup.split('var deal = open.transaction([KEPT, FLAGS], "readonly");')[1]
        assert "readBatch(deal);" in creation
        assert "await " not in creation
        first_get = lookup.split("function readBatch(tx) {", 1)[1].split("tx.objectStore(KEPT).get(plain);", 1)[0]
        assert ".then(" not in first_get and "await " not in first_get
        assert "new Promise" not in first_get and "setTimeout" not in first_get

    def test_browse_bytes_and_write_cadence_survive_a_worker_restart(self):
        worker = maps.SERVICE_WORKER
        assert "var DB_AT = 6;" in worker
        assert "var TILE_CAP = 150 * 1000 * 1000;" in worker
        assert "setTimeout(flushPuts, 0)" in worker
        assert "size: body.byteLength" in worker
        assert "total.writes % 50 === 0" in worker
        assert "PackIO.saveTotals(deal, held, total)" in worker
        assert "if (removed >= 50 || total.bytes <= TILE_CAP) { done(); }" in worker
        assert "if (event) { event.waitUntil(kept); }" in worker

    def test_upgrade_recreates_packs_and_discards_browse_without_a_walk(self):
        worker = maps.SERVICE_WORKER
        upgrade = worker.split("function upgrade(db, tx)")[1].split("function prefix")[0]
        assert "db.deleteObjectStore('browse')" in upgrade
        assert "db.deleteObjectStore('packs')" in upgrade
        assert "db.createObjectStore('packs')" in upgrade
        for flag in ("held", "stand", "browse-bytes"):
            assert f"flags.delete('{flag}')" in upgrade
        assert "Cursor(" not in upgrade and ".get(" not in upgrade
        assert "PackIO.upgrade(made, ask.transaction)" in worker

    def test_a_deliberate_download_is_not_answered_by_the_worker(self):
        """The panel fetches what the reader asked to keep with `cache:
        'reload'`. Without this branch a download begun while the switch was on
        would be answered by the worker's own blank tile, every blank would be
        written into the terrain cache as terrain, and the reader would be told
        their park was kept -- and it would be white.

        It sits **after** the navigate branch on purpose: pressing reload makes a
        navigation with the same flag, and offline that has to be answered from
        the cache rather than sent to a network that is not there."""
        fetching = maps.SERVICE_WORKER.split('addEventListener("fetch"')[1]
        assert 'if (request.cache === "reload") { return; }' in fetching
        assert fetching.index('request.mode === "navigate"') < fetching.index('request.cache === "reload"')

    def test_the_document_does_not_reach_for_a_network_that_is_switched_off(self):
        """A reader who asked for offline did not ask for a request that hangs
        until it times out."""
        paging = maps.SERVICE_WORKER.split("function pageFor(request)")[1].split("\nfunction ")[0]
        assert "if (off && kept) { return kept; }" in paging

    def test_a_newer_map_can_be_asked_for_without_navigating(self):
        """The check lived inside `pageFor`, which runs on a navigation — so the
        only way to hear about a new map was to do the thing you were about to be
        told to do. Installed to a home screen there is no reload control, and a
        reader with the switch on never reaches the network at all: exactly the
        one carrying a stale map for a fortnight."""
        assert 'if (said.trails === "check")' in maps.SERVICE_WORKER
        assert "function askForNewer(mark) {" in maps.SERVICE_WORKER
        looking = maps.SERVICE_WORKER.split("function askForNewer(mark) {")[1].split("\nfunction ")[0]
        # **A HEAD, and only a HEAD.** The page is 5.2 MB over the wire, and
        # spending that to be told nothing had changed is what a reader walking
        # would pay for — so looking costs a few hundred bytes and nothing else.
        assert 'fetch(both.url, {method: "HEAD", cache: "reload"})' in looking
        assert '{cache: "reload"}' not in looking
        # And what it answers with is the size, because that is what the reader
        # is about to be asked to spend.
        assert 'bytes: Number(head.headers.get("content-length")) || null' in looking

    def test_the_body_is_fetched_only_when_the_reader_asks_for_it(self):
        """The look used to fetch the body behind the reader whenever the answer
        was yes: 5.2 MB spent by a rule nobody invoked, over whatever connection
        happened to be attached. That is the thing the offline switch exists to
        prevent, and it was doing it in the switch's own page."""
        assert 'if (said.trails === "take")' in maps.SERVICE_WORKER
        taking = maps.SERVICE_WORKER.split("function takeNewer()")[1].split("\nfunction ")[0]
        assert 'fetch(both.url, {cache: "reload"})' in taking
        assert "return write(PAGES, both.url, made);" in taking
        # **The HEAD runs again rather than being trusted from a minute ago.**
        # With the switch off `pageFor` may have taken the new page in between,
        # and the reload would then spend 5.2 MB arriving where it already was.
        assert 'if (!movedFrom(both.row, head)) { return tell("taken"); }' in taking
        # A tap that could not be honoured says so instead of reloading into the
        # same map it was already showing.
        assert 'return tell("stuck");' in taking

    def test_the_newer_line_carries_a_way_to_act_on_it(self):
        """It said *reload to see it* to a reader who, installed to a home
        screen, has no address bar and no reload control — an instruction that
        cannot be carried out."""
        html = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7)).get_root().render()
        assert "trails-newer-reload" in html
        assert "postMessage({trails: 'take'})" in html
        assert "A newer map is ready" in html
        # The size the button is about to spend, quoted before it is pressed.
        assert "(window.trailsWorker.bytes / 1e6).toFixed(1) + ' MB.'" in html

    def test_nothing_asks_on_the_way_back_in(self):
        """A HEAD on every resume wakes the radio each time the app is glanced
        at, and the body behind it was 5.2 MB nobody asked for. Energy outranks
        freshness for a reader days from a charger: the age is made visible and
        the asking is a button."""
        html = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7)).get_root().render()
        # The two halves of what was removed, by name.
        assert "var asked = 0;" not in html
        assert "if (Date.now() - asked < 600000) { return; }" not in html
        # What is left is asked for by hand, and refuses to ask with nothing to
        # ask over.
        assert "window.trailsWorker.ask = function () {" in html
        asking = html.split("window.trailsWorker.ask = function () {")[1].split("};")[0]
        assert "if (!navigator.onLine) { return false; }" in asking
        # **And it hands in what is on the screen.** The worker holds a cache
        # and the cache is refreshed behind whatever answer it served, so a
        # comparison made there is about a page nobody is looking at — which is
        # how *check for a newer map* came to answer *up to date* to somebody
        # reading the old one.
        assert "postMessage(" in asking
        assert "{trails: 'check', mark: Date.parse(document.lastModified) || null}" in asking
        # And the only listener left on a resume is the wake lock and a redraw.
        for block in html.split("document.addEventListener('visibilitychange'")[1:]:
            assert "postMessage" not in block.split("});")[0]

    def test_the_check_is_about_the_page_on_the_screen(self):
        """Reported from the phone: *check for a newer map* said the map was up
        to date while the reader was looking at the old one — and it was telling
        the truth about the wrong thing. ``pageFor`` writes the fresh body
        *behind* the answer it serves, so one visit after a publish leaves the
        cache holding the new map and the screen showing the old, and a
        comparison made against the cache then says there is nothing to do.
        There was: reload.

        The page hands in its own identity, which is ``document.lastModified``
        and is exact through the worker — measured on the published page, where
        it carries the header and not the moment the page was drawn. Compared as
        instants, because one of the two is an HTTP date and the other is
        whatever the browser writes locally. The cache is still compared where
        the page cannot say: a worker woken with no page to ask, or a server
        that sends an etag and no ``last-modified``."""
        assert "function newerThanShown(mark, row, head) {" in maps.SERVICE_WORKER
        judging = maps.SERVICE_WORKER.split("function newerThanShown(mark, row, head) {")[1].split("\nfunction ")[0]
        assert 'var said = Date.parse(head.headers.get("last-modified"));' in judging
        assert "if (mark && said && !isNaN(said)) { return said > mark; }" in judging
        assert "return movedFrom(row, head);" in judging
        assert "event.waitUntil(askForNewer(said.mark));" in maps.SERVICE_WORKER


class TestOfflinePanel:
    """The tool that says what is kept, keeps more, and gets the space back."""

    @staticmethod
    def rendered():
        return maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7)).get_root().render()

    @staticmethod
    def panel():
        return files("trails.visualization").joinpath("js", "offline_panel.js").read_text(encoding="utf-8")

    @staticmethod
    def script():
        """The panel's script file.

        Every figure this panel quotes is worked out at load, and the way to hold
        it to that is to be able to look at the code without the prose that
        explains it: the prose is allowed to name 6.76 GB, and the script is not.
        """
        return TestOfflinePanel.panel()

    def test_the_page_says_whether_this_browser_can_keep_it_at_all(self):
        """The page has computed `window.trailsWorker.why` since the worker was
        added and showed it nowhere. On iOS a service worker exists in Safari and
        in a home-screen web app and in no third-party browser, so for some
        readers every other feature here was already dead and the page was
        silent about it."""
        panel = self.panel()
        assert "Not available in this browser" in panel
        assert "a worker exists in Safari and in this map added to the Home Screen" in panel
        # And the other refusal, which is not about the browser at all: a page
        # opened off the disk gets no worker because the origin is not secure,
        # and sending that reader after Safari sends them after the wrong thing.
        assert "opened from a file rather than from a web address" in panel
        assert "have.why.indexOf('secure') === -1" in panel
        # An insecure origin comes in two kinds, and only one of them has an
        # address the reader can fix. The http one gets that address handed
        # over rather than described.
        assert "location.protocol === 'file:'" in panel
        assert "The address is http, not https" in panel
        assert "location.host + location.pathname" in panel
        # Three states and not two: the registration settles after load, and
        # answering *not available* while it is pending is a wrong answer rather
        # than a slow one.
        assert "Asking this browser whether it can keep the map" in panel
        assert "navigator.serviceWorker.ready" in panel

    def test_the_switch_with_nothing_kept_asks_instead_of_lying(self):
        """A switch that silently gives a blank map is a switch that lied."""
        panel = self.panel()
        assert "if (want && !any)" in panel
        assert "chooser = true;" in panel

    def test_four_pieces_of_ground_and_only_one_follows_the_paths(self):
        """**A band along everything drawn was the wrong shape for this park.**
        In Lomsdal-Visten one walks off the path, and a band along the paths puts
        a white tile under anybody who leaves one -- so the scope that keeps
        everything is a filled box now. The band stays, because along a line it
        is still the cheapest useful shape by a long way: measured on a real
        42.3 km loop, 1,722 tiles at z16 against 131,033 for the box.

        The viewport is gone with it. It was never a piece of terrain so much as
        a piece of screen, and what it was reached for -- *this valley and the
        ridge behind it* -- is what the drawn area says properly."""
        panel = self.panel()
        scopes = re.findall(r"\{key: '(\w+)', label: '([^']+)', pad: (\d), ceiling: (\w+),", panel)
        assert [key for key, _, _, _ in scopes] == ["all", "band", "rect", "draw"]
        assert {key: int(pad) for key, _, pad, _ in scopes} == {"all": 1, "band": 2, "rect": 1, "draw": 1}
        # Only the one that keeps everything stops short of where the source does.
        assert {key: ceiling for key, _, _, ceiling in scopes} == {
            "all": "CAP_ZOOM",
            "band": "TOP",
            "rect": "TOP",
            "draw": "TOP",
        }
        assert "level > here.ceiling" in panel

    def test_the_whole_map_fills_a_box_rather_than_following_a_band(self):
        """The whole finite tree includes ground between and beyond the paths."""
        panel = self.panel()
        assert "if (which === 'all') { return null; }" in panel
        levels = panel.split("function levelsFor(coreAt, top, pad) {")[1].split("\n                }")[0]
        assert "if (!coreAt)" in levels
        assert "for (z = OVERVIEW; z <= top; z += 1) { out[z] = overviewAt(z, null, true); }" in levels
        overview = panel.split("function overviewAt(z, core, whole) {")[1].split("\n                }")[0]
        assert "var box = EXTENT;" in overview
        assert "new Set" not in overview

    def test_the_selection_is_measured_once_and_halved_down_to_z11(self):
        """A tile at z-1 is the tile at z with both coordinates shifted right, so
        one pass answers every level below it. **And the margin is laid on each
        level while the unpadded set is what goes down**: padding first and
        halving the padded set compounds the margin all the way to z11, where a
        tile is eight kilometres across."""
        panel = self.panel()
        levels = panel.split("function levelsFor(coreAt, top, pad) {")[1].split("\n                }")[0]
        assert "var below = coreAt(top);" in levels
        assert "out[top] = padded(below, pad, top);" in levels
        assert "out[z] = padded(up, pad, z);" in levels
        assert "below = up;" in levels
        assert "below = padded" not in levels
        # z11 whatever the reader picked, because a map that cannot be zoomed out
        # of is not a map anybody navigates with. FLOOR is the coarsest zoom
        # somebody may *choose*; it is not the floor of the pyramid.
        assert "for (z = top - 1; z >= BOTTOM; z -= 1)" in levels
        assert "var BOTTOM = 11;" in panel

    def test_every_scope_adds_the_overview_without_listing_its_tiles(self):
        """The overview is a lazy rectangle union, including the z11 overlap."""
        panel = self.panel()
        assert "var OVERVIEW = 8;" in panel
        assert "for (z = OVERVIEW; z <= BOTTOM; z += 1) { out[z] = overviewAt(z, out[z]); }" in panel
        overview = panel.split("function overviewAt(z, core, whole) {")[1].split("function overviewCost()")[0]
        assert "var box = EXTENT;" in overview
        assert "var size = (x1 - x0 + 1) * (y1 - y0 + 1);" in overview
        assert "if (!inside(v)) { size += 1; }" in overview
        assert "if (!core || !core.has(v))" in overview
        assert "while (x <= x1)" in overview
        assert "new Set" not in overview and ".push(" not in overview
        assert "var layers = packLayers(), at = 0, z = OVERVIEW, parents = null, level;" in panel
        bounds = panel.split("bounds: function () {")[1].split("},")[0]
        assert "var box = EXTENT;" in bounds
        assert "return [[box.s, box.w], [box.n, box.e]];" in bounds

    def test_the_overview_is_priced_separately_without_charging_the_overlap_twice(self):
        """Scope and overview add to the same total the run and quota use."""
        panel = self.panel()
        assert "levels[z] = overviewAt(z);" in panel
        assert "overview: overviewCost()" in panel
        assert "trails-offline-overview" in panel
        assert "count(counted.packs - counted.overview.packs)" in panel
        assert "megabytes(counted.bytes - counted.overview.bytes)" in panel
        assert "'overview, ' + count(counted.overview.packs)" in panel
        assert "counted.bytes > free * 0.9" in panel

    def test_a_straight_run_between_two_vertices_is_walked_and_not_skipped(self):
        """The drawn geometry is simplified at 8 m, so a straight across a
        plateau can be hundreds of metres between two vertices -- and a tile at
        z18 is 63 m. Taking only the endpoints would leave holes along every
        straight, which is the ground somebody walks fastest and looks at
        least."""
        panel = self.panel()
        assert "function walk(a, b, z, into)" in panel
        # Half a tile a step, so a tile can never be stepped over.
        assert "Math.abs(dx), Math.abs(dy)) * 2" in panel

    def test_the_zooms_offered_stop_where_the_source_does(self):
        """Both providers' tile trees end at z17; the ceiling is injected."""
        assert "var TOP = {{ this.top }};" in self.panel()
        assert "var FLOOR = 14;" in self.panel()
        norwegian = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(norwegian)
        assert "var TOP = 17;" in norwegian.get_root().render()
        swedish = maps.create_map(bounds=(18.15, 68.17, 19.0, 68.46), base=maps.BaseMap.LANTMATERIET_TOPO, extra_bases=())
        maps.add_chrome(swedish)
        assert "var TOP = 17;" in swedish.get_root().render()

    def test_the_budget_is_measured_at_load_rather_than_written_down(self):
        """It is what the whole map costs at the zoom that scope is capped at --
        using the measured pack weights -- and every other scope is held to it, so nothing
        on this panel can quietly cost more than the choice that keeps
        everything. Worked out at load, because a figure typed in here is a
        figure that goes stale the first time the sources move."""
        panel = self.panel()
        assert "cap = cost('all', CAP_ZOOM).bytes;" in panel
        # Both finite trees are offered through their native z17.
        assert "var CAP_ZOOM = {{ this.cap }};" in panel
        assert maps.PROVIDERS["kartverket"].cap == 17
        assert maps.PROVIDERS["lantmateriet"].cap == 17 == maps.PROVIDERS["lantmateriet"].top
        assert all(provider.cap <= provider.top for provider in maps.PROVIDERS.values())
        assert maps._OfflinePanel(maps.PROVIDERS["lantmateriet"], maps.Companions.named("abisko")).cap == 17
        # Every zoom whose result would go over it is refused, and says why.
        assert "cap !== null && known && known.bytes > cap" in panel
        assert "'Over the budget: '" in panel
        # A comment may name the measurement -- that is what comments here are
        # for. The code may not, because a figure written into the code is one
        # that keeps being quoted after it has stopped being true.
        code = "\n".join(line for line in self.script().split("\n") if not line.strip().startswith("//"))
        assert "6.76" not in code

    def test_the_buffer_key_holds_every_corner_and_not_their_number(self):
        """**Measured against the shape on the screen, not reasoned about.**
        Dragging a handle moves a point in the middle of the list and leaves both
        the count and the last corner alone, so a key made of those two is the
        same key for two different areas -- and the panel answered out of the
        buffer with the area the shape used to have."""
        panel = self.panel()
        sig = panel.split("function sig(which, level) {")[1].split("\n                }")[0]
        assert "at[0].toFixed(5) + ',' + at[1].toFixed(5)" in sig
        assert ".join(';')" in sig
        assert "drawn.length" not in sig
        # And the buffer is what the zoom row reads, or every repaint prices five
        # levels of a turned rectangle to draw a row of buttons.
        assert "memo[at] = weigh(levelsFor(coreOf(which), level, scopeOf(which).pad));" in panel

    def test_a_ring_is_clipped_to_the_finite_tree_before_testing_tiles(self):
        panel = self.panel()
        assert "fracTile(Math.min(n, EXTENT.n), Math.max(w, EXTENT.w), z)" in panel
        assert "fracTile(Math.max(s, EXTENT.s), Math.min(e, EXTENT.e), z)" in panel
        assert "while (zoom > FLOOR && cost(scope, zoom).bytes > budget()) { zoom -= 1; }" in panel

    def test_the_preview_paints_kept_tiles_inside_the_screen_tile(self):
        """**Two other ways of drawing this are wrong and both were built.**
        Testing only the screen tile's centre paints nothing at all zoomed out,
        because the centre almost never lands in a kept tile; filling the whole
        screen tile whenever it holds any kept one turns a valley into a county
        -- reported from a phone, where an area a few kilometres across was
        painted a hundred kilometres wide."""
        panel = self.panel()
        tile = panel.split("createTile: function (coords) {")[1].split("\n                });")[0]
        assert "var step = Math.pow(2, z - coords.z);" in tile
        # The screen the finer of the two: then and only then the whole tile.
        assert "if (step <= 1) {" in tile
        assert "ink.fillRect(0, 0, side, side);" in tile
        # The screen the coarser: sub-rectangles of side/step, one per kept tile.
        assert "var px = side / step" in tile
        assert "ink.fillRect(i * px, j * px, px, px);" in tile
        # And under a pixel it draws nothing rather than rounding a speck up.
        assert "if (step > side) { return canvas; }" in tile
        # A grid layer, so the preview costs what the screen costs whether the
        # selection is 400 tiles or 131,000.
        assert "L.GridLayer.extend({" in panel

    def test_the_panel_says_which_level_is_the_one_coloured_in(self):
        """Every level carries its own one-tile margin, so the same selection is
        223 km2 at z15 and 1,712 km2 at z11. Without this line the shape looks as
        though it grew when the reader zoomed out."""
        panel = self.panel()
        saying = panel.split("function sayLayer() {")[1].split("\n                }")[0]
        assert "'Coloured in: level z'" in saying
        assert "' tiles of '" in saying
        assert "km2" in saying
        assert "map.on('zoomend', function () { if (chooser) { sayLayer(); } });" in panel

    def test_a_band_and_a_box_need_a_line_and_say_which_one_they_took(self):
        """The planned route first, because a reader who has planned one is
        keeping ground for that; the selected track otherwise. Neither, and the
        two scopes are not offered at all -- the rule the route scope has always
        followed, rather than a button that answers nothing."""
        panel = self.panel()
        source = panel.split("function source() {")[1].split("\n                }")[0]
        assert "var planned = routeLine();" in source
        assert "'the route you planned'" in source
        assert "window.trailsProfile" in source
        assert "'the track you have selected'" in source
        assert "return from || (each.key !== 'band' && each.key !== 'rect');" in panel
        # And it is said on the panel, because which of the two was taken changes
        # what the selection is and nothing else on the screen would show it.
        assert "' Drawn round ' + from.from + '.'" in panel

    def test_the_box_round_the_route_is_turned_to_lie_close(self):
        """A convex hull and rotating calipers: the minimum-area enclosing
        rectangle always has one side flush with a hull edge, so trying each edge
        is the whole algorithm. **Worked in metres about the line's own centre**,
        because an angle in degrees of latitude and longitude is not an angle on
        the ground -- at 65 degrees north a degree of longitude is 46 km and a
        degree of latitude 111."""
        panel = self.panel()
        rect = panel.split("function rectRing(points, by) {")[1].split("\n                }")[0]
        assert "convex(" in rect
        assert "111320 * Math.cos(mid[0] * Math.PI / 180)" in rect
        assert "Math.atan2(b[1] - a[1], b[0] - a[0])" in rect
        assert "if (!best || area < best.area)" in rect
        # The margin is a slider in metres, 0 to 5 km, because ground to leave
        # the line by is the thing being asked for and it is not a zoom.
        assert "said.margin.max = '5000';" in panel
        assert "'Room round the line'" in panel

    def test_a_corner_is_a_finger_wide_and_the_tap_stops_at_it(self):
        """44 px of target around a 15 px dot: the dot is what a finger aims at
        and the target is what it hits. And the tap stops there, or the map's own
        click places a second corner directly on top of the one just touched."""
        panel = self.panel()
        assert "iconSize: [44, 44]" in panel
        assert "L.DomEvent.stopPropagation(event);" in panel
        # **Outline while dragging, tiles when it lands.** A point-in-polygon
        # pass over the whole bounding box, dozens of times a second, on a phone.
        dragging = panel.split("handle.on('drag', function () {")[1].split("});")[0]
        assert "outline.setLatLngs(drawn)" in dragging
        assert "again()" not in dragging
        assert "again();" in panel.split("handle.on('dragend', function () {")[1].split("});")[0]
        # Joined in the order they were tapped, and left tangled if they were
        # tapped across each other: quietly taking the convex hull would keep
        # ground nobody asked for and give no way of saying so.
        assert "Corners are joined in the order they were tapped" in panel
        assert "convex(drawn" not in panel

    def test_what_will_not_fit_is_refused_against_the_room_there_is(self):
        """A ceiling per scope catches the whole map above z16; it does not catch
        a phone with 3 GB free and a selection that fits the budget twice over.
        This is measured on the device: a Firefox profile answered 3.3 GB, and a
        phone will answer something else again."""
        panel = self.panel()
        assert "counted.bytes > free * 0.9" in panel
        assert "That is more than this device will hold" in panel

    def test_only_the_base_layer_that_is_showing_is_kept(self):
        """Topo and grayscale share a host, so keeping both would silently double
        every figure on this panel."""
        assert "function base()" in self.panel()

    def test_a_run_that_kept_nothing_switches_nothing_on(self):
        """**Measured, not reasoned about**: with the network down, a download of
        40 tiles kept 0 and turned offline mode on anyway — which hands over
        exactly the blank map this chooser exists to prevent, while saying it is
        what the reader asked for. Counted as tiles found plus tiles fetched,
        which is what this selection has on the device — the two figures the loop
        could only get by asking the cache for every tile in turn."""
        panel = self.panel()
        settle = panel.split("function keep() {")[1].split("}).then(function () {\n                        working = null;")[1]
        assert "kept: state.held + state.added," in settle
        assert "if (!lastRun.kept) { return refresh(); }" in settle
        assert settle.index("if (!lastRun.kept)") < settle.index("remember(true)")
        # And it is said, because a run where nothing arrived looks exactly like
        # a run that was never started.
        assert "Nothing arrived" in panel

    def test_the_chooser_is_not_rebuilt_every_twenty_five_tiles(self):
        """Progress arrives every 25 tiles, and rebuilding the chooser that often
        re-reads the plan's whole route to decide which scopes to offer and takes
        the focus off whatever the reader was on -- including the Stop button
        they are reaching for."""
        panel = self.panel()
        drawing = panel.split("function draw() {")[1].split("\n                }")[0]
        assert "if (!working) { drawChooser(); }" in drawing
        assert drawing.count("drawChooser(") == 1
        # Built once when the run starts, so Stop is there to be pressed.
        assert "drawChooser();\n                    draw();\n                    return state.done_;" in panel

    def test_the_slider_and_the_corner_buttons_survive_being_counted(self):
        """A margin slider is a control somebody drags, and a drag on an element
        that is thrown away and made again on every recount ends the moment the
        first figure arrives. So the chooser is built once and filled: only the
        two rows of buttons are rewritten."""
        panel = self.panel()
        build = panel.split("function build() {")[1].split("\n                }")[0]
        assert "said.margin = document.createElement('input');" in build
        assert "said.margin.addEventListener('input'" in build
        assert "said.go.addEventListener('click'" in build
        chooser = panel.split("function drawChooser() {")[1].split("\n                }\n\n                function draw()")[0]
        assert "said.chooser.innerHTML" not in chooser
        assert "said.which.innerHTML = '';" in chooser
        assert "said.fine.innerHTML = '';" in chooser

    def test_the_ceiling_belongs_to_the_scope_and_not_to_the_button(self):
        """Disabling a button is what the screen does; it is not what is true.
        `choose('all', 18)` has to come back clamped, and so does a level that
        would go over the budget, or the invariant is painted on rather than
        held."""
        panel = self.panel()
        chosen = panel.split("choose: function (which, level)")[1].split("\n                    },")[0]
        assert "zoom > here.ceiling" in chosen
        assert "zoom > TOP" in chosen and "zoom < FLOOR" in chosen
        assert "while (zoom > FLOOR && cost(scope, zoom).bytes > budget())" in chosen

    def test_the_drawn_area_can_be_set_from_outside(self):
        """There is no way to tap four corners from a script and have the map
        believe it, and the check that this panel keeps what it says it will keep
        has to ask for a piece of ground small enough to be a check rather than a
        bulk fetch off somebody else's service."""
        panel = self.panel()
        assert "area: function (ring) {" in panel
        given = panel.split("area: function (ring) {")[1].split("\n                    },")[0]
        assert "drawn = (ring || []).map(" in given
        assert "return again();" in given

    def test_the_reader_can_get_the_space_back(self):
        """A gigabyte somebody cannot get rid of from inside the thing that took
        it is a gigabyte taken without asking."""
        panel = self.panel()
        assert "function forget()" in panel
        assert "caches.delete(TERRAIN), caches.delete(TILES)" in panel
        assert "Delete the terrain kept on this device?" in panel

    def test_it_is_a_tool_in_the_dock_like_every_other_one(self):
        """And its holder is left detached: the dock is what puts a panel on the
        screen, and one appended to the map container sits over the terrain until
        it gets there."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)
        html = fmap.get_root().render()
        assert "{key: 'offline', label: 'Offline'" in html
        assert "byKey.offline.holder = window.trailsOffline" in html
        assert "map.getContainer().appendChild(holder)" not in self.panel()
        # And it is refreshed when it is looked at rather than only at load: the
        # figures on it are what the device holds now, not what it held then.
        assert "if (key === 'offline' && window.trailsOffline) { window.trailsOffline.refresh(); }" in html

    def test_the_preview_stays_out_of_the_box_it_is_measured_against(self):
        """The outline is a layer on this map like any other, and `mapBox` reads
        the box off the layers -- so without a mark on it, an area drawn outside
        the paths would move the box that the whole map scope is."""
        panel = self.panel()
        assert "if (layer.options && layer.options.trailsOffline) { return; }" in panel
        assert "trailsOffline: true" in panel

    def test_persistence_is_asked_for_from_the_press_and_not_at_load(self):
        """WebKit deletes storage a script created once an origin has gone seven
        days without a visit -- exactly the walk somebody keeps terrain for a
        fortnight before. A browser grants persistence from a user gesture: an
        origin nobody has touched asking to be kept for ever is what that rule
        exists to refuse."""
        panel = self.panel()
        asked = panel.split("said.go.addEventListener('click', function () {")[1].split("\n                    });")[0]
        assert "navigator.storage.persist()" in asked

    def test_a_route_is_asked_of_the_plan_rather_than_read_off_the_map(self):
        """`state()` answers everything else about a route and deliberately not
        this: it is read on every check and by the chrome, and two million
        coordinates is not a status."""
        assert "window.trailsPlan.geometry" in self.panel()
        planning = files("trails.visualization").joinpath("js", "plan_mode.js").read_text(encoding="utf-8")
        assert "geometry: function () {" in planning
        assert "return {lon: shape.lon, lat: shape.lat};" in planning

    def test_pack_estimates_are_exact_counts_with_measured_mean_weights(self):
        panel = self.panel()
        assert "while ((next = walk.next())) { packs += 1; bytes += next.bytes; }" in panel
        assert "guessed:" not in panel

    def test_the_box_follows_the_legend(self):
        """`mapBox` walks 11,303 rings, so it is remembered — but the legend can
        take a layer off the map, and if the outermost line was on it the box
        being offered is no longer the box this map draws. The band scope it
        replaced had no such gap: it re-read the layers every time."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        # The panel is only on the page when the chrome puts it there.
        maps.add_chrome(fmap)
        html = fmap.get_root().render()
        assert "map.on('layeradd layerremove', function () { box = null; });" in html

    def test_the_chooser_says_which_chip_is_chosen(self):
        """Chosen was a background colour and nothing else, which a screen reader
        cannot see. Five other controls on this page already say it out loud."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        # The panel is only on the page when the chrome puts it there.
        maps.add_chrome(fmap)
        html = fmap.get_root().render()
        assert "pick.setAttribute('aria-pressed', String(each.key === scope));" in html
        assert "pick.setAttribute('aria-pressed', String(level === zoom));" in html

    def test_the_screen_is_held_awake_for_the_length_of_the_run(self):
        """The download is six `fetch` calls from the page and nothing else — no
        Background Fetch, no worker doing it out of sight — so a phone that locks
        freezes it. 130,000 tiles is not a run anybody watches to the end holding
        the thing."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "navigator.wakeLock.request('screen')" in html
        # Taken again on the way back: the browser drops the lock whenever the
        # page is hidden and does not hand it back.
        awake = html.split("document.addEventListener('visibilitychange', function () {")
        assert any("if (working) { keepAwake(); }" in block for block in awake[1:])
        # And let go when the run ends, or the screen stays on for as long as the
        # tab lives.
        assert "letSleep();" in html

    def test_the_screen_is_asked_for_again_when_the_run_comes_back(self):
        """Whether ``visibilitychange`` fires for a standalone home-screen app on
        iOS has been an open question in this project since the offline side was
        built, and a Playwright Firefox on Linux cannot answer it.

        Two things rode on the answer and now neither does. The run itself
        already resumed on the one-second poll behind ``whenInFront``; the wake
        lock did not. The browser drops the lock every time the page is hidden
        and does not hand it back, so on a device where that event never fires,
        one glance at a message left the rest of a long download to a screen
        free to sleep — and a sleeping screen parks the run, because nothing is
        fetched while the app is away.

        Asking for the screen again where the run resumes is what makes the
        question stop mattering. A no-op while the lock is held, which is every
        tile but the first after a glance elsewhere.

        Settled on the device on 2026-09-11: the icon is the cairn, and the lock
        is granted and stays held for the length of a download. What that does
        not say is what happens across a switch to another app, which is exactly
        what this removes the need to know."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "keepAwake();\n                        return fetch(url, {cache: 'reload', mode: 'cors'});" in html
        # The poll behind the event, which is what the run already leaned on.
        assert "var poll = window.setInterval(go, 1000);" in html

    def test_holding_the_screen_is_optional_in_every_branch(self):
        """The API is absent on older iOS and refused off a secure origin. A run
        without it wants babysitting; a run that threw on the way to asking for
        it would keep nothing at all."""
        panel = files("trails.visualization").joinpath("js", "offline_panel.js").read_text(encoding="utf-8")
        assert "if (awake || !navigator.wakeLock || !navigator.wakeLock.request) { return; }" in panel
        assert "}).catch(function () { awake = null; });" in panel
        # The run can end while the request is in flight, and a lock nobody
        # releases is a screen that never sleeps again.
        assert "if (!working) { held.release(); return; }" in panel

    def test_the_run_says_what_a_progress_bar_cannot(self):
        """That it needs this page in front is a property of where it runs; that
        stopping is free is a property of the cache being checked before every
        tile. Neither is visible, and guessing either one wrong costs an
        evening."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "the run pauses when the phone locks or you switch " in html
        assert "picks up when you come back. Stopping costs nothing either." in html
        # And the claim it makes is one the loop keeps: every tile is asked of
        # the cache before it is asked of the network, so a stopped run costs
        # nothing to pick up.
        assert "return dbRead(KEPT, next.url).then(function (there) {" in html
        assert "if (there && there.kept && there.complete) { missed = 0; state.held += 1; kept = true; size = there.size; return null; }" in html

    def test_a_run_never_holds_more_than_one_tile(self):
        """The pre-scan that let a resumed run open at the figure it had reached
        was `cache.keys()` over the terrain cache: one `Request` object per tile,
        131,033 of them for the whole map at z16, at the one moment the page can
        least afford it. Measured in Firefox at 920 ms for 40,000 entries and
        linear — about three seconds and a hundred thousand objects, on a phone
        already holding a 15.7 MB document."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        # Nothing in the run enumerates, and nothing in it is a list of tiles.
        run = html.split("function keep() {")[1].split("function forget()")[0]
        # Read as code and not as prose: the comment above the loop names the
        # call it replaced.
        code = "\n".join(line for line in run.split("\n") if not line.strip().startswith("//"))
        assert "cache.keys()" not in code
        assert "wanted()" not in code
        # One tile in hand at a time, out of a walk over the chosen levels.
        assert "var walk = walker();" in html
        assert "var next = walk.next();" in run
        assert "if (!next) { return Promise.resolve(); }" in run
        # And the counter counts both halves, so it is a figure from the first
        # tile rather than after a pass that has to finish first.
        assert "counted: true" in run
        assert "state.done += 1;" in run

    def test_the_panel_says_how_old_the_map_is(self):
        """Nothing asks for a newer map on its own any more, so being out of
        date has to be visible rather than silent — otherwise an app opened on
        the fourth day of a walk shows the first day's map and says nothing."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)
        html = fmap.get_root().render()
        assert "trails-offline-age" in html
        # **Read, not stamped.** A build time written into the HTML changes the
        # page's bytes on every rebuild, which changes the worker's digest,
        # which drops the cached page — recording the age would itself become a
        # reason to download the map again.
        assert "Date.parse(document.lastModified)" in html
        assert "'This map was built ' + Math.round(hours) + ' h ago.'" in html
        # And no timer keeps it true: a tick behind a locked screen is a wake-up
        # to redraw a string nobody is reading.
        panel = self.script()
        assert "setInterval" not in panel.split("function age()")[1].split("function ask()")[0]
        # **One interval exists in this panel, and it is not this.** A paused
        # download polls for the app coming back, because `visibilitychange` in a
        # standalone iOS app is unverified here and waiting on it alone would
        # park the run for ever. It is armed only while a run is waiting, where
        # nothing else is running at all.
        assert panel.count("setInterval") == 1
        assert "var poll = window.setInterval(go, 1000);" in panel

    def test_the_only_thing_that_asks_for_a_newer_map_is_a_button(self):
        """A manual check nobody knows to press is the same as no check, and an
        age with no way to act on it is a complaint."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)
        html = fmap.get_root().render()
        assert "trails-offline-check" in html
        assert "check.addEventListener('click', ask);" in html
        assert "window.trailsWorker.ask()" in html
        # Unavailable rather than failing when tapped.
        assert "row.check.disabled = waiting || !askable;" in html
        # **And a way out of *Checking…*.** The answer is a message from a
        # worker, and a worker can be stopped between the question and the
        # answer — which would leave the only button that asks disabled for the
        # rest of the session, on the page somebody is carrying up a valley.
        assert "checkSaid = 'No answer — try again.';" in html
        # And the answer is said even when it is *nothing to do*, which is most
        # of the time and is not a reason to leave the button looking unread.
        assert "'This is the newest one.'" in html
        assert "'The map could not be reached.'" in html

    def test_a_download_gives_up_on_the_connection_not_on_the_tile(self):
        """One tile that will not come is a tile; twelve in a row is the signal.
        Grinding through the rest is a hundred thousand more attempts to wake a
        radio that has nothing to answer — in the one situation where the
        battery is the whole question."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)
        html = fmap.get_root().render()
        assert "if (missed >= 12) { state.stop = true; state.stalled = true; }" in html
        # Reset on every success, so bad tiles arriving in ones and twos never
        # trip it — twelve rather than three because six requests run at once.
        assert "missed = 0;" in html and "return Promise.resolve(answer).then(function (body) {" in html
        # A run the connection stopped still switches on for what arrived; only
        # a run the reader stopped leaves the chooser where it was.
        assert "if (state.stop && !state.stalled) { return refresh(); }" in html
        assert "'The connection gave out \\u2014 '" in html

    def test_a_download_is_not_begun_without_a_connection(self):
        """`navigator.onLine` lies in one direction only: when it says false
        there is genuinely nothing, and beginning is then a hundred thousand
        fetches into a radio with nobody to talk to."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)
        html = fmap.get_root().render()
        keep = html.split("function keep() {")[1].split("function forget()")[0]
        assert "if (!navigator.onLine) {" in keep
        assert "lastRun = {total: 0, kept: 0, failed: 0, offline: true};" in keep
        assert "'No connection \\u2014 nothing was tried, and nothing '" in html


class TestThePageAccountsForItsOwnOpening:
    """The one gap no check here can cross: how long this costs on the device."""

    @staticmethod
    def rendered():
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)
        return fmap.get_root().render()

    def test_the_page_marks_its_own_opening(self):
        """An installed app on a phone reported ten to twenty seconds to open
        where every check in this project measures 1.8 s — and every one of them
        is Firefox on Linux, so the gap is exactly the part that cannot be
        measured from here."""
        html = self.rendered()
        # The head macro runs before the body exists; the chrome is added last,
        # so what lies between the two marks is the map being built.
        assert "window.trailsOpened = {head: performance.now()};" in html
        assert "if (window.trailsOpened) { window.trailsOpened.chrome = performance.now(); }" in html
        assert "function openCost() {" in html
        assert "build: since(marks.chrome, marks.head)," in html

    def test_it_asks_what_the_worker_cost(self):
        """With offline mode on the document comes out of the Cache API, where
        it is held at its decoded 15.7 MB rather than the 5.2 MB brotli the
        network sends — beside a store holding gigabytes of tiles. That is the
        suspicion this line exists to confirm or kill."""
        html = self.rendered()
        assert "worker: nav.workerStart ? since(nav.responseStart, nav.workerStart) : null," in html

    def test_the_figures_are_read_on_the_way_in(self):
        """The chrome is built before `load` has fired, so every figure that ends
        at `loadEventEnd` was zero: the line said *opened in 0 ms* about a page
        that had taken 1.7 seconds."""
        html = self.rendered()
        assert "if (key === 'info') { sayOpenCost(); }" in html
        assert "measurements.appendChild(costLine);" in html
        assert "measurements.appendChild(tileLine);" in html
        assert "sourcesHolder.insertBefore(measurements, sourcesHolder.firstChild);" in html
        # Built empty and filled later, rather than composed once and left.
        assert "function sayOpenCost() {" in html
        assert "costLine.textContent = parts.join" in html


class TestTheFurnitureStaysInsideTheScreen:
    """What a finger can reach, on a phone that keeps two strips for itself."""

    @staticmethod
    def rendered():
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)
        return fmap.get_root().render()

    def test_the_map_reaches_the_edges_and_the_furniture_does_not(self):
        """Reported from the device: with `viewport-fit=cover` live but the
        overlay still at zero, a panel's heading and its close button were drawn
        under the clock and the button could not be tapped at all. The map is
        meant to fill the screen; anything a finger is for belongs below the
        point where the screen is its full width."""
        html = self.rendered()
        assert "left:env(safe-area-inset-left);top:env(safe-area-inset-top);" in html
        assert "right:env(safe-area-inset-right);bottom:env(safe-area-inset-bottom);" in html
        # Leaflet's own corners are not inside that box, so they are held by
        # their four containers instead.
        assert ".leaflet-bottom { padding-bottom: env(safe-area-inset-bottom); }" in html
        assert ".leaflet-top { padding-top: env(safe-area-inset-top); }" in html

    def test_the_newer_map_line_clears_the_camera(self):
        """The one thing this page draws outside the chrome, and so the one the
        inset on that box does not reach. It landed under the camera and its
        button could not be tapped — which is the worst place for it, because
        that button is how the next version is taken: a reader who cannot press
        it cannot reach the fix for it either."""
        html = self.rendered()
        assert "top:calc(10px + env(safe-area-inset-top));" in html
        assert "'position:absolute;top:10px;left:50%" not in html
        # **And hung inside the box whose inset is visibly working.** The `calc`
        # went out once and was reported still under the camera; the overlay that
        # holds the menu and the panels was demonstrably right in the same
        # screenshot. The `calc` stays for a map built without `add_chrome`,
        # where there is no such box.
        assert "var into = map.getContainer().querySelector('.trails-chrome');" in html
        assert "(into || map.getContainer()).appendChild(line);" in html
        # Inside a box that is `pointer-events: none`, a button has to ask for
        # them back or it cannot be pressed — which is this line's whole point.
        assert "line.style.pointerEvents = 'auto';" in html

    def test_the_page_is_as_tall_as_the_screen(self):
        """folium writes `html, body { height: 100% }`, and with
        `viewport-fit=cover` on iOS that resolves to the viewport inside the
        insets — so the map stopped above the home indicator and the browser's
        own background showed there. Reported as a black band under the map,
        with the scale sitting on top of it."""
        html = self.rendered()
        assert "html, body { width: 100dvw; height: 100dvh; }" in html
        # Sideways the same thing happened on the left: a band of the browser's
        # background where the map should have been.
        # folium's own rule stays as the fallback: a browser that does not know
        # the unit drops this declaration and keeps the behaviour that was right
        # before any of this.
        assert "height: 100%;" in html

    def test_the_profile_leaves_room_for_the_rail_and_the_edge(self):
        """It took the whole map minus 20 px, which was true while the map ended
        where the screen's usable part did. It does not any more — reported from
        a phone held sideways as the profile sticking out to the right, into the
        inset and under the rail."""
        # Read off the element rather than a rendered page: the profile panel
        # is added by a chain, not by `add_chrome`.
        panel = files("trails.visualization").joinpath("js", "profile_panel.js").read_text(encoding="utf-8")
        assert "var railRoom = narrow ? 0 : 66;" in panel
        assert "env(safe-area-inset-left)" in panel
        assert "env(safe-area-inset-right)" in panel
        # The old arithmetic is gone rather than wrapped.
        assert "(map.getSize().x - (narrow ? 0 : 20)) + 'px'" not in panel

    def test_a_full_screen_panel_looks_like_one(self):
        """The chrome is held inside the safe area, so a full-screen sheet
        leaves a band of map above it and another below — which reads as a
        mistake rather than as a map. The strips take the panels' own colour
        while a panel is covering, and only then."""
        html = self.rendered()
        assert "veil.className = 'trails-veil';" in html
        assert "background:var(--trails-solid)" in html
        assert "veil.style.display = covering ? 'block' : 'none';" in html
        # Behind the chrome and outside its inset, or it would be the band it is
        # there to fill.
        veil = html.split("veil.style.cssText = ")[1].split(";\n")[0]
        assert "left:0;top:0;right:0;bottom:0" in veil
        assert "z-index:1099" in veil

    def test_the_inset_is_applied_once(self):
        """The rail, the burger, the dock, the menu, the sheet and the plan bar
        are all children of the overlay, so a rule of their own would be the
        same inset a second time."""
        html = self.rendered()
        assert "margin-top: env(safe-area-inset-top)" not in html


class TestTheWideLayoutNeedsRoomInBothDirections:
    """A phone held sideways is wide enough for the rail and far too short."""

    @staticmethod
    def rendered():
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)
        return fmap.get_root().render()

    def test_a_short_screen_gets_the_burger(self):
        """Reported from a phone in landscape: the rail ran off the bottom of
        the screen, and the way back to the tool that had gone was a menu that
        was not there. The burger opens a full-height sheet that scrolls, which
        is the shape a short screen can use."""
        html = self.rendered()
        assert "var RAIL_ROOM = TOOLS.length * 46 + (TOOLS.length - 1) + 20;" in html
        assert "return size.x < NARROW || size.y < RAIL_ROOM;" in html
        # Every place that asked about width asks this instead, or the two
        # would disagree about which layout is on.
        assert "var narrow = narrowNow();" in html
        assert "narrow: narrowNow()," in html
        assert "var narrow = size.x < NARROW;" not in html
        # And it asks the box the rail actually stands in. The chrome is held
        # inside the safe area, so sideways the rail has the screen's height
        # less the home indicator, and it is that which has to fit nine tools.
        assert "return {x: chrome.clientWidth || size.x, y: chrome.clientHeight || size.y};" in html

    def test_the_rail_is_measured_after_it_has_been_filled(self):
        """Arithmetic over a stylesheet is a guess, and this one was a few pixels
        from being wrong. The first attempt to measure instead of guess did not
        measure anything: it read the height straight after `appendChild`, where
        the rail is an empty bordered div two pixels tall, so the `Math.max` kept
        the arithmetic and the number never moved. It belongs below the loop that
        fills it — and no later, because once `place` has run the rail may be
        `display: none` and a hidden box measures zero."""
        html = self.rendered()
        assert "RAIL_ROOM = Math.max(RAIL_ROOM, Math.ceil(rail.offsetHeight) + 20);" in html
        after = html.split("chrome.appendChild(rail);")[1].split("RAIL_ROOM = Math.max")[0]
        # The nine buttons are in it by then...
        assert "rail.appendChild(button);" in after
        # ...and nothing has hidden it yet: `place` is the only thing that ever
        # sets the rail's display, and it has not run.
        assert "rail.style.display" not in after
        assert "place();" not in after

    def test_the_screen_is_measured_and_never_remembered(self):
        """`map.getSize()` is a cache, not a measurement: Leaflet re-reads the
        container only when `invalidateSize()` has set `_sizeChanged`, and that
        runs from one `window` `resize` inside one `requestAnimationFrame`. A
        rotation on iOS is animated, so the frame that lands during it records a
        box that never existed and nothing arrives to correct it — reported as
        the wide menu on an upright screen, the profile hanging off the right
        edge and the map stopping short of the bottom. Three symptoms, one
        number. A second `place()` on a 350 ms timer could not help: re-asking a
        cache returns the cache."""
        html = self.rendered()
        assert "return {x: container.clientWidth || 0, y: container.clientHeight || 0};" in html
        # The timer that guessed how long a rotation takes is gone.
        assert "placeAgain" not in html
        assert "350);" not in html

    def test_the_box_is_watched_rather_than_the_events_guessed(self):
        """An observer fires for every real change of the box and stops when the
        box does, which is the last frame of the rotation and the only reading
        worth having. It also tells Leaflet: nothing but `invalidateSize()`
        re-measures what the map draws itself against."""
        html = self.rendered()
        assert "new ResizeObserver(settled).observe(container);" in html
        assert "map.invalidateSize({debounceMoveend: true});" in html
        # Coalesced to a frame, the way Leaflet's own resize handler is.
        assert "pending = window.requestAnimationFrame(function () {" in html
        # And a fallback for a browser without the observer, on the event
        # Leaflet itself listens to.
        assert "window.addEventListener('orientationchange', settled);" in html

    def test_the_profile_asks_the_chrome_rather_than_deciding_again(self):
        """It worked the answer out again from the width, and the two have just
        stopped agreeing — so the chrome would show the burger while the profile
        still left room for a rail that was not there."""
        panel = files("trails.visualization").joinpath("js", "profile_panel.js").read_text(encoding="utf-8")
        assert "var said = window.trailsChrome && window.trailsChrome.state();" in panel
        assert "var narrow = said ? said.narrow : mapRoom().x < NARROW;" in panel

    def test_nothing_decides_a_layout_from_leaflet_s_cached_size(self):
        """The class of the bug rather than the three instances of it. Leaflet's
        `getSize` returns `this._size.clone()` unless `_sizeChanged` is set, and
        only `invalidateSize()` sets it — so any layout worked out from it can be
        working from a screen that stopped existing at the last rotation. Every
        one of them was: the chrome's own decision, the profile's fallback, its
        width, its height and its ceiling. They now read the container, which
        cannot be out of date because it is not stored.

        Mechanical, and it reads the source rather than the rendering: a new
        `map.getSize()` in layout code fails here. The canvas renderer must use
        Leaflet's own cached size to transform its existing projection; it does
        not decide the layout of any control.
        """
        source = pathlib.Path(maps.__file__).read_text(encoding="utf-8")
        source += "".join(
            path.read_text(encoding="utf-8") for path in files("trails.visualization").joinpath("js").iterdir() if path.name != "pinch_draw.js"
        )
        live = [(number, line) for number, line in enumerate(source.splitlines(), 1) if "map.getSize()" in line and not line.strip().startswith("//")]
        assert live == [], live

    def test_the_sheet_a_short_screen_gets_can_be_scrolled(self):
        """Which is the whole reason the burger is the right answer here: the
        menu is bounded to the room there is and its body carries the overflow,
        so nine tools fit a screen that cannot show nine tools.

        The room there is, on a narrow screen, is the screen: the veil is over
        the panel at the foot, so a sheet has no reason to stop where the map
        does. What still takes room is the keyboard, which hides part of the
        viewport under fields these sheets are the only ones to hold.

        **The screen less what the phone keeps for itself**, which is the
        chrome's box and not the map's: a sheet as tall as the map begins where
        the chrome begins and ends the top inset below the glass, taking the end
        of its own scroll with it (§9.37)."""
        html = self.rendered()
        assert "var deep = Math.max(40, Math.min(room.y, size.y - covered - chromeTop));" in html
        assert "box.style.height = deep + 'px';" in html
        # Held sideways the detail is a column beside the panel rather than a
        # sheet over it, and there the panel's top is the floor again -- in the
        # chrome's terms, like everything else here.
        assert "sheet.style.height = Math.max(40, Math.min(room.y, floor - chromeTop)) + 'px';" in html
        assert "overflow: auto" in html or "overflow:auto" in html

    def test_every_height_is_measured_in_the_chrome_s_own_terms(self):
        """The class of the bug rather than the one panel it was reported on.

        The figures `place` starts from -- the keyboard, the profile panel's top
        -- are all measured from the top of the *map*, which with
        `viewport-fit=cover` reaches the physical edges of the screen. The
        panels are children of the chrome, which is held inside the safe area.
        `chromeTop` is the one number that turns the first into the second, and
        every height that ends up on a panel goes through it: the full-screen
        sheets, the sideways detail column, and the dock's ceiling on a wide
        screen, which is the one a desktop sees.

        Reported as a row of the layer list that could not be reached upright
        (§9.37), where the panel ended 59 px below the glass and its scroll
        ended with it.
        """
        html = self.rendered()
        assert "var room = railRoom();" in html
        assert "chrome.getBoundingClientRect().top - container.getBoundingClientRect().top" in html
        # The wide screen's ceiling. Every inset is zero on a desktop, so this
        # says the same thing it said before -- which is why it may be written
        # once for both.
        assert "var capped = Math.max(40, Math.min(room.y, floor - chromeTop) - 18);" in html


class TestNothingInThePanelIsDeclaredTwice:
    """The one mistake this file makes twice in an afternoon."""

    def test_no_name_is_declared_twice_in_the_offline_panel(self):
        """`paint` was added beside the `paint` that draws the selection preview,
        and `awake` beside the `awake` that holds the wake lock. The first was
        caught by reading; the second reached the browser and the driven run
        stopped with *awake is not a function*. It is one script, one scope, and
        several thousand lines — so the check is mechanical rather than careful."""
        panel = files("trails.visualization").joinpath("js", "offline_panel.js").read_text(encoding="utf-8")
        # **Only the panel's own scope**, which is exactly one indentation. A
        # name inside a function may repeat as often as it likes; these are the
        # ones that share a namespace several thousand lines wide.
        top = "                "
        names: dict[str, int] = {}
        for line in panel.split("\n"):
            if not line.startswith(top) or line[len(top) : len(top) + 1] == " ":
                continue
            found = re.match(r"(?:function (\w+)\s*\(|var (\w+)\s*=)", line[len(top) :])
            if not found:
                continue
            name = found.group(1) or found.group(2)
            names[name] = names.get(name, 0) + 1
        twice = sorted(name for name, seen in names.items() if seen > 1)
        assert not twice, f"declared more than once in one scope: {twice}"


class TestATileIsAskedForMoreThanOnce:
    """A scatter of refusals is a hole in the map where the reader was standing."""

    @staticmethod
    def rendered():
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)
        return fmap.get_root().render()

    def test_three_tries_a_tile(self):
        """Reported from a real download: refusals arriving now and then, each
        one a tile the run simply gave up on."""
        html = self.rendered()
        assert "var TRIES = 3;" in html
        assert "return fetchTile(next.url, 1, 0);" in html
        # The wait grows with the attempt, because what this exists for is a
        # server briefly out of patience and coming straight back is what made
        # it so.
        assert "return later(400 * attempt).then(function () {" in html

    def test_nothing_is_asked_for_while_the_app_is_away(self):
        """Reported from a real download: the refusals came when the app had
        been briefly inactive. They are not the server saying no — iOS freezes a
        web app that is not in front, in-flight requests are cut, and the radio
        is not back the instant the reader is. Retrying into that spends every
        try on the one situation where none of them can work."""
        html = self.rendered()
        # Named `whenInFront` and not `awake`: the panel already has an `awake`,
        # which holds the wake lock. See the check that no name in this scope is
        # declared twice — it was added because this one reached the browser.
        assert "function whenInFront() {" in html
        assert "if (!document.hidden) { return Promise.resolve(); }" in html
        # The fetch waits for the app rather than for a clock.
        assert "return whenInFront().then(function () {" in html
        # **A failure across a suspension costs no try.** The app went away
        # mid-request; that says nothing about the tile or the connection.
        assert "if (putAway !== away || document.hidden) {" in html
        # And it cannot wait for ever: a run left in the background stops.
        assert "var WAITS = 8;" in html
        assert "if (waited >= WAITS) { return null; }" in html
        # **The event, and a poll behind it.** Whether `visibilitychange` fires
        # for a standalone home-screen app on iOS has never been measured here —
        # it is one of the open questions this project carries — and waiting on
        # it alone would park the run for ever after the first interruption.
        assert "var poll = window.setInterval(go, 1000);" in html
        assert "window.clearInterval(poll);" in html

    def test_only_where_a_second_ask_can_change_the_answer(self):
        """Asking again about any refusal would be two more radio wakes for the
        same answer, which is the bill this map spent the afternoon reducing. A
        400 is Kartverket saying the tile is not there — z19 and z20 answer 400,
        measured — and no amount of asking makes one."""
        html = self.rendered()
        assert "var worth = !answer || answer.status === 429 || answer.status >= 500;" in html
        assert "if (!worth || attempt >= TRIES) { return answer && answer.status === 404 ? false : null; }" in html

    def test_the_stall_guard_still_counts_tiles(self):
        """Twelve in a row is the connection, not the tiles — and with retries a
        tile is only counted once it has refused three times over, so the guard
        did not quietly become thirty-six attempts before it fires."""
        html = self.rendered()
        keep = html.split("function keep() {")[1].split("function forget()")[0]
        assert "if (missed >= 12) { state.stop = true; state.stalled = true; }" in keep
        # `missed` moves once per tile, in the branch that has already given up.
        assert keep.count("missed += 1;") == 2


class TestTheTwoScriptsAgreeAboutTheDatabase:
    """The one disagreement that stops the map opening at all."""

    @staticmethod
    def rendered():
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)
        return fmap.get_root().render()

    def test_the_worker_and_the_page_open_the_same_version(self):
        """A connection held at an older version blocks the other side's
        upgrade, and with no `onblocked` the wait never ends. Measured on this
        suite: the page held version 1 while the worker asked for 2, a
        navigation never answered, and the driven run sat at zero per cent CPU
        for twenty minutes. On a phone the app simply would not have opened."""
        html = self.rendered()
        worker = re.search(r"var DB_AT = (\d+);", maps.SERVICE_WORKER)
        page = re.search(r"window\.indexedDB\.open\('trails', (\d+)\)", html)
        assert worker and page, "both sides must name a version"
        assert worker.group(1) == page.group(1)
        assert worker.group(1) == "6"

    def test_neither_side_hangs_and_neither_side_blocks(self):
        """Two halves. Saying so beats waiting — blocked means somebody holds an
        older connection. And stepping aside when the other wants to upgrade is
        what makes the deadlock impossible rather than merely reported."""
        html = self.rendered()
        assert "ask.onblocked" in maps.SERVICE_WORKER
        assert "ask.onblocked" in html
        assert "open.onversionchange = function () { open.close(); opened = null; };" in maps.SERVICE_WORKER
        assert "open.onversionchange = function () { open.close(); db.open = null; };" in html

    def test_both_sides_make_every_store(self):
        """Whichever opens first runs the upgrade, so both have to know about
        all three — a store missing on one side is a transaction that throws on
        the other."""
        html = self.rendered()
        for store in ("pages", "flags", "packs"):
            assert f"createObjectStore('{store}')" in html
            assert f"contains({store.upper()})" in maps.SERVICE_WORKER or f'"{store}"' in maps.SERVICE_WORKER
        for source in (html, maps.SERVICE_WORKER):
            assert "PackIO.upgrade(made, ask.transaction)" in source
            assert "store.createIndex('browsed-at', 'browsedAt')" in source
            assert "store.createIndex('kept', 'keptAt')" in source

    def test_sources_reads_the_real_tally(self):
        html = self.rendered()
        assert "['mem', 'db', 'seen', 'net', 'blank'].forEach" in html
        assert "spent.total.toFixed(1)" in html and "spent.worst.toFixed(1)" in html
        assert "told.deadlines" in html and "told.peak" in html


class TestNothingGrowsWithTheDownload:
    """What an installed app can hold while it keeps a hundred thousand tiles."""

    @staticmethod
    def rendered():
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)
        return fmap.get_root().render()

    def test_a_tile_is_one_number_in_a_set(self):
        """It was a string key `"x,y"` into an object whose value was an `[x, y]`
        array — three allocations a tile, and the whole map at z16 is 131,033
        tiles. `Set.size` also replaces `Object.keys(set).length`, which built a
        131,033-element array to ask how many there were, on every repaint of
        the zoom row."""
        html = self.rendered()
        assert "var SPAN = 262144;" in html
        assert "function key(x, y) { return x * SPAN + y; }" in html
        assert "function keyX(v) { return Math.floor(v / SPAN); }" in html
        # Every producer of a level makes a Set, and every consumer asks it.
        assert "var out = new Set(), x, y;" in html
        assert "out.add(key(x, y));" in html
        assert "while ((next = walk.next())) { packs += 1; bytes += next.bytes; }" in html
        assert "var n = set.size;" in html
        assert "if (set.has(key(x0 + i, y0 + j)))" in html
        # And nothing builds a keys array out of a level any more. Read as code
        # and not as prose: the comment above `key` names what it replaced.
        code = "\n".join(line for line in html.split("\n") if not line.strip().startswith("//"))
        assert "Object.keys(set)" not in code
        assert "Object.keys(core)" not in code

    def test_the_addresses_are_walked_and_never_listed(self):
        """This built the address of all 131,033 tiles into an array — some 14 MB
        of strings — and the only other caller used it to ask how long the array
        was."""
        html = self.rendered()
        assert "function walker(picked) {" in html
        assert "var parent = parents.next();" in html
        assert "var layer = base(), walk = packWalk(picked.levels);" in html
        # The count comes from the weights, which already had it.
        assert "return {packs: base() ? picked.packs : 0, bytes: picked.bytes};" in html
        run = html.split("function walker(picked) {")[1].split("\n                function ")[0]
        assert "urls.push(" not in run
        # **And the move off the old store is gone with the store.** It ran
        # once, on the one device that had ground in a cache — 59,091 tiles,
        # measured — and what it was for cannot happen again: nothing writes
        # a cache any more.
        assert "moveGround" not in html

    def test_what_is_kept_is_written_down_not_counted_out(self):
        """`cache.keys()` over the terrain cache ran on every `refresh` — on
        load, on the switch, and every time the panel was opened. Measured in
        Firefox: 1,000 entries 25 ms, 10,000 202 ms, 40,000 920 ms. At 131,033
        that is about three seconds and as many `Request` objects, each time."""
        html = self.rendered()
        assert "var HELD = 'held';" in html
        counting = html.split("var HELD = 'held';")[1].split("function note(")[0]
        assert "dbRead('flags', HELD)" in counting
        assert "cache.keys()" not in "\n".join(line for line in counting.split("\n") if not line.strip().startswith("//"))
        # **And not beside the tiles.** It was, which reads well — storage
        # cleared under the page would take both — and it meant that opening this
        # panel opened a Cache Storage holding tens of thousands of entries and
        # several gigabytes. Measured on an installed app at twenty seconds.
        assert "window.indexedDB.open('trails', 6)" in html
        # `forget` clears the row too, which is the property the first place was
        # chosen for.
        assert "db().then(function (open) { return PackIO.forget(open); })" in html
        # Written as the run goes, so a run the phone interrupts still leaves a
        # figure behind — which is exactly the run that used to leave the panel
        # saying nothing was kept.
        assert "var tx = open.transaction(['packs', 'flags'], 'readwrite')" in html

    def test_no_record_means_zero_packs_kept(self):
        """The upgrade dropped old tiles; every pack now commits with its count.
        A missing record after upgrade or null after Forget means zero packs."""
        html = self.rendered()
        assert "var none = {packs: 0, bytes: 0, top: 0, known: true, stale: null};" in html
        assert "if (!held) { return none; }" in html
        assert "known: false" not in html
        assert "kept packs not counted" not in html
        assert "var lines = [count(have.kept ? have.kept.packs : 0) + ' packs kept'];" in html
        assert "var maybe = have.kept && have.kept.packs;" in html
        guard = html.split("function anyKept() {")[1].split("function toggle(")[0]
        assert "return there.packs > 0;" in guard
        assert "dbRead" not in guard


class TestTheSheetCarriesAToken:
    """Making the browser ask again for a tile it thinks it already has."""

    @staticmethod
    def rendered():
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)
        return fmap.get_root().render()

    def test_the_token_moves_where_the_answer_moves(self):
        """A browser holds an image by its address, so a tile the reader saw as
        blank stays blank on that address for the life of the document —
        Leaflet rebuilding the `<img>` does not help, because the memory cache
        answers and no request reaches the worker at all. Measured: with the
        switch newly off, `fetch` of a blanked tile returned 89,757 bytes while
        an `<img>` on the same address still loaded 1 × 1."""
        html = self.rendered()
        assert "function restamp() {" in html
        assert "layer.setUrl(plainUrl(layer) + '?trails=' + stamp);" in html
        # Thrown, and downloaded — the two moments the worker's answer changes.
        assert html.count("restamp();") == 2
        # And both sit behind the worker being told, which is the moment its
        # answer actually changes — not in `refresh`, which runs on every settle
        # and would make every visible tile be asked for again each time.
        for call in html.split("restamp();")[:-1]:
            assert "tellWorker(" in call[-300:], "a token moved without the worker being told"

    def test_the_worker_looks_up_without_the_token(self):
        """Everything on that side is keyed on the tile itself, so a token that
        moves costs one lookup and no bytes. Driven with the network off: kept
        ground still draws under its new address."""
        assert 'var plain = request.url.split("?")[0];' in maps.SERVICE_WORKER
        tile = maps.SERVICE_WORKER.split("function tileFor(request, event)")[1].split("\nfunction ")[0]
        assert "lookup(address.url, state, plain)" in tile
        # Stored without it too, or a second token would orphan what the first
        # one wrote.
        assert "browsePut(url, body)" in maps.SERVICE_WORKER
        # **Stripped rather than matched with `ignoreSearch`**, which would turn
        # every one of a hundred thousand keys into a comparison.
        assert "ignoreSearch" not in tile

    def test_the_download_builds_addresses_without_the_token(self):
        """What goes into a cache is keyed on the plain address, so moving the
        token never orphans a tile."""
        html = self.rendered()
        assert "layer.options.trailsUrl = layer._url.split('?')[0];" in html
        assert "url: packPrefix(layer.prefix) + level + '/'" in html
        # **And absolute.** The worker looks a tile up by the request's
        # address, which is absolute; a sheet from our own bucket is
        # addressed root-relative, and keyed as written every tile of it
        # would be kept under a name the worker never asks for.
        assert "var url = new URL(prefix, location.href);" in html

    def test_a_sheet_switched_in_gets_the_token_without_moving_it(self):
        """A base layer arrives with no token at all, and switching sheets is
        not a reason to make every reader ask for their tiles again."""
        html = self.rendered()
        change = html.split("map.on('baselayerchange', function () {")[1].split("});")[0]
        assert "eachSheet(stampOn);" in change
        assert "restamp" not in change


class TestTheSwitchWaitsForTheWorker:
    """Throwing the switch and redrawing the map are not the same instant."""

    @staticmethod
    def rendered():
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)
        return fmap.get_root().render()

    def test_the_flag_is_waited_for_and_not_merely_posted(self):
        """Writing the flag is asynchronous — it goes into the worker's own
        cache — while the refresh that follows every call redraws the sheets at
        once. Posted and not waited for, those tiles were answered by a worker
        still holding the old flag: switching offline mode off left the ground
        blank until something made Leaflet ask again. Driven, and it did."""
        html = self.rendered()
        assert "navigator.serviceWorker.addEventListener('message', heard);" in html
        assert "if (!event.data || event.data.trails !== 'offline') { return; }" in html
        # The worker has always sent this reply; nothing listened to it.
        assert 'event.source.postMessage({trails: "offline", on: !!said.on})' in maps.SERVICE_WORKER

    def test_a_worker_that_never_answers_does_not_hold_the_panel(self):
        """A panel that never finishes refreshing is worse than one that
        refreshes a moment early — and the flag is written either way."""
        html = self.rendered()
        assert "window.setTimeout(function () { done(false); }, 2000);" in html
        assert "navigator.serviceWorker.removeEventListener('message', heard);" in html

    def test_the_download_hands_the_switch_over_before_it_redraws(self):
        """The one caller that dropped the promise on the floor, and the one
        where the redraw matters most: the switch has just gone on, and every
        tile on the screen is about to be asked for again."""
        html = self.rendered()
        assert "return packsChanged().then(function () { return tellWorker(true); }).then(function () {" in html


class TestNativeZoomFollowsWhatIsKept:
    """Zooming past the ground on the device shows that ground magnified."""

    @staticmethod
    def rendered():
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)
        return fmap.get_root().render()

    def test_the_ceiling_follows_the_finest_level_held(self):
        """Both sheets carry `maxNativeZoom: 18`, so Leaflet asks for the real
        tile at every zoom. One level past what is kept the worker answers a
        blank — a valid 200 — so Leaflet counts it loaded and prunes the coarse
        ground the reader does own. Driven: 24 tiles at z15, 0 at z16."""
        html = self.rendered()
        assert "function fitNativeZoom(top) {" in html
        assert "layer.options.maxNativeZoom = want;" in html
        assert "layer.redraw();" in html
        # **Only while the switch is on.** With it off the reader wants the real
        # z17 from Kartverket and can have it.
        # And never above the level a tree was actually cut to: the sheet goes
        # deeper than the relief overlay does, and asking the shadow for a level
        # nobody built would blank it.
        assert "var want = (on() && top) ? Math.min(top, layer.options.trailsNative) : layer.options.trailsNative;" in html
        # The sheet's own ceiling is remembered once, so turning offline mode off
        # gives back what the layer was built with rather than a guess.
        assert "layer.options.trailsNative = layer.options.maxNativeZoom;" in html

    def test_the_finest_level_comes_from_the_pass_that_was_already_being_made(self):
        """Asking the cache a second time for one number is a second walk over a
        hundred thousand keys, in the panel that already pays for one."""
        html = self.rendered()
        assert "if (next.kind === 'map') { state.top = Math.max(state.top, Math.min(state.requested, next.z + 3)); }" in html
        assert "held.top = Math.max(held.top, top)" in html
        assert "fitNativeZoom(both[0].top);" in html

    def test_a_sheet_switched_under_the_reader_gets_the_same_ceiling(self):
        """A base layer arrives with its own 18, and the offline switch does not
        move when it does."""
        html = self.rendered()
        assert "map.on('baselayerchange', function () {" in html
        assert "fitNativeZoom(snapshot && snapshot.kept ? snapshot.kept.top : 0);" in html

    def test_the_chooser_preview_is_not_taken_for_a_sheet(self):
        """The preview is a grid layer that paints its tiles and fetches none;
        a ceiling on it would mean nothing and redrawing it would repaint the
        selection for no reason."""
        html = self.rendered()
        assert "if (!layer.getTileUrl || !layer.options) { return; }" in html


class TestSourcesFreshness:
    """The map's age where a reader who never turns offline mode on can see it."""

    def test_only_the_measurements_fold_behind_the_header_stopwatch(self):
        """The age action and credits stay outside the two folded paragraphs."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)
        html = fmap.get_root().render()
        assert "measurementsButton.innerHTML = icon('stopwatch', 19);" in html
        assert "measurementsButton.style.cssText = dockParts.close.style.cssText;" in html
        assert "measurementsButton.style.marginRight = 'auto';" in html
        assert "dockParts.title.style.flex = key === 'info' ? '0 1 auto' : '1';" in html
        assert "measurementsButton.setAttribute('aria-label', 'Measurements');" in html
        assert "measurementsButton.setAttribute('aria-controls', measurements.id);" in html
        assert "dockParts.close.parentNode.insertBefore(measurementsButton, dockParts.close);" in html
        assert re.findall(r"measurements.appendChild\((\w+)\)", html) == ["costLine", "tileLine"]

    def test_the_fold_resets_on_open_and_reports_its_state(self):
        """Opening another tool cannot inherit the Sources control or its state."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)
        html = fmap.get_root().render()
        assert "measurements.hidden = !measurements.hidden;" in html
        assert "measurementsButton.setAttribute('aria-expanded', String(!measurements.hidden));" in html
        opened = html.split("openTool = key;")[1].split("raise('tool');")[0]
        assert "measurementsButton.hidden = key !== 'info';" in opened
        assert "measurements.hidden = true;" in opened
        assert "measurementsButton.setAttribute('aria-expanded', 'false');" in opened

    def test_sources_carries_the_age_and_the_check(self):
        """A map goes stale because an installed app resumes instead of
        navigating, and that is true whatever the offline switch says. The one
        cure lived behind a feature half the readers never turn on — and
        `Sources` is already the panel about the page rather than the ground."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)
        html = fmap.get_root().render()
        assert "sourcesHolder.insertBefore(window.trailsOffline.freshness(), sourcesHolder.firstChild);" in html
        # **One set of facts, not two.** The row is handed out by the offline
        # panel rather than rebuilt, so both say the same thing at the same
        # moment and a check started in one is answered in the other.
        assert "freshness: freshRow," in html
        assert "freshRows.push({age: when, check: check});" in html
        assert "freshRows.forEach(function (row) {" in html

    def test_the_row_is_drawn_apart_from_the_panel(self):
        """`draw` returns early when the offline panel has no holder — a row
        handed to `Sources` has to stay true whether or not anybody has opened
        the offline tool."""
        panel = files("trails.visualization").joinpath("js", "offline_panel.js").read_text(encoding="utf-8")
        fresh = panel.split("function drawFresh() {")[1].split("\n                }")[0]
        assert "if (!holder)" not in fresh


class TestScaleZoom:
    """The map saying which zoom it is on."""

    def test_the_scale_bar_says_the_zoom_and_the_ground_it_is_drawing_at(self):
        """The chooser asks the reader for a zoom, so a reader picking z16 out of
        a list has to be able to see what z16 looks like. It also makes a
        screenshot readable back to a zoom, which every report about this page
        has so far had to reconstruct from the bar."""
        html = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7)).get_root().render()
        assert "trails-scale-zoom" in html
        assert "m/px" in html
        # Asked of Leaflet rather than worked out from the zoom, so the line and
        # the bar above it are measuring the same ground.
        assert "map.containerPointToLatLng([100, 0])" in html

    def test_one_bar_and_not_two(self):
        """folium's `control_scale=True` emits a bare `L.control.scale()`, and a
        bare Leaflet scale draws a metric bar and an imperial one. Under the zoom
        line, in that corner, the stack reads as the same control drawn twice —
        reported from a phone in exactly those words."""
        html = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7)).get_root().render()
        assert "L.control.scale({metric: true, imperial: false, maxWidth: 100, position: 'bottomleft'})" in html
        # And folium is not also adding its own, or there would be two controls
        # rather than two bars, which is the same corner and a worse cause. The
        # `.addTo` is what makes this the emitted call and not the comment above
        # it explaining why the bare one is not wanted.
        assert "L.control.scale().addTo" not in html

    def test_the_figures_are_drawn_once(self):
        """Leaflet's own rule is `text-shadow: 1px 1px #fff` — a white copy of
        the number a pixel down and right, which is how you keep it legible over
        a translucent box with the map showing through. This box is opaque, so
        the copy only smears; reported from a phone as `20 km` looking blurred,
        doubled about half a millimetre apart."""
        html = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7)).get_root().render()
        # **Ours, and not the first block carrying that selector.** Leaflet's own
        # stylesheet is inlined into this page and declares it too — which is the
        # whole reason there is something here to override.
        blocks = [block.split("}")[0] for block in html.split(".leaflet-control-scale-line {")[1:]]
        theirs = [block for block in blocks if "text-shadow: 1px 1px #fff" in block]
        ours = [block for block in blocks if "--trails-panel" in block]
        assert theirs, "Leaflet stopped shipping the rule this overrides"
        assert ours and "text-shadow: none !important;" in ours[0]

    def test_it_takes_the_box_and_not_the_measuring_bar(self):
        """A line with a rule under it in that corner is claiming to be a
        distance, and this one is not."""
        html = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7)).get_root().render()
        style = html.split(".trails-scale-zoom {")[1].split("}")[0]
        assert "border-top: none" in style


class TestManifest:
    """What makes the map installable, which is what makes an offline copy
    survive being left alone for a week."""

    def test_it_opens_at_the_address_the_object_is_served_at(self):
        """The object is `lomsdal-visten.html` in the bucket and is served at
        `/lomsdal-visten`, the same distinction the worker already has to make.
        And it is relative, because nothing identifying the host may be written
        into this repository."""
        page = pathlib.Path(tempfile.mkdtemp()) / "lomsdal-visten.html"
        page.write_text("<html>a map</html>", encoding="utf-8")
        written = maps.write_manifest(page, "Lomsdal-Visten")
        assert written.name == "manifest.webmanifest"
        said = json.loads(written.read_text(encoding="utf-8"))
        assert said["start_url"] == "./lomsdal-visten"
        assert said["scope"] == "./"
        assert said["display"] == "standalone"
        assert said["name"] == "Lomsdal-Visten"
        assert "http" not in said["start_url"]

    def test_its_icons_ride_in_it_rather_than_being_two_more_objects(self):
        """A repository that carries a PNG carries it for ever, and a second
        object to deploy for 700 bytes is not a trade."""
        page = pathlib.Path(tempfile.mkdtemp()) / "lomsdal-visten.html"
        page.write_text("<html>a map</html>", encoding="utf-8")
        said = json.loads(maps.write_manifest(page, "Lomsdal-Visten").read_text(encoding="utf-8"))
        assert {icon["sizes"] for icon in said["icons"]} == {"192x192", "512x512"}
        for icon in said["icons"]:
            assert icon["src"] in ("./icon-192.png", "./icon-512.png")
            # A full square with the cairn well inside it, so a launcher may crop
            # it to a circle or a squircle without cutting a stone off.
            assert icon["purpose"] == "any maskable"

    def test_the_mark_ships_as_files_at_every_size_the_page_links_to(self):
        """A page that links to `icon-180.png` and does not write one is a home
        screen showing a screenshot. Every size in `ICON_SIZES` is a link
        somewhere — the document, the manifest — so a missing one is a broken
        reference and this raises rather than shipping it."""
        for mark in (maps.ROOT.mark, maps.Companions.of("abisko").mark):
            for side in maps.ICON_SIZES:
                source = maps.ICON_DIR / f"{mark}-{side}.png"
                assert source.is_file(), f"no source icon for {mark} at {side}"
                raw = source.read_bytes()
                assert raw.startswith(b"\x89PNG\r\n\x1a\n")
                assert struct.unpack(">II", raw[16:24]) == (side, side)

    def test_the_icons_are_written_beside_the_page(self, tmp_path):
        """Named for the page and not for the source: the document links to
        `icon-180.png` whatever the file in the package is called."""
        page = tmp_path / "lomsdal-visten.html"
        page.write_text("<html></html>", encoding="utf-8")

        written = maps.write_icons(page)

        assert [each.name for each in written] == [f"icon-{side}.png" for side in maps.ICON_SIZES]
        for each in written:
            assert each.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")

    def test_a_missing_size_is_refused_rather_than_shipped(self, tmp_path, monkeypatch):
        """Silently writing three of four leaves the page pointing at an object
        that is not there, and nothing says so until somebody adds it to a home
        screen."""
        monkeypatch.setattr(maps, "ICON_DIR", tmp_path / "empty")
        with pytest.raises(FileNotFoundError, match="icon-32.png"):
            maps.write_icons(tmp_path / "lomsdal-visten.html")

    def test_the_page_carries_its_name_its_mark_and_the_manifest(self):
        """Folium writes no title at all, so the tab and a home-screen icon were
        both labelled with the URL."""
        html = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7), title="Lomsdal-Visten").get_root().render()
        assert "<title>Lomsdal-Visten</title>" in html
        assert '<link rel="manifest" href="manifest.webmanifest">' in html
        # **A file and not a `data:` URI.** Safari will not fetch one for a touch
        # icon, so inline the link is well-formed and dead, and the home screen
        # falls back to a screenshot of the map. Reported from a phone.
        assert '<link rel="apple-touch-icon" href="icon-180.png">' in html
        assert '<link rel="icon" type="image/png" sizes="32x32" href="icon-32.png">' in html
        assert "data:image/png;base64," not in html.split("</head>")[0]
        assert '<meta name="apple-mobile-web-app-capable" content="yes">' in html

    def test_the_written_page_leaves_the_browser_its_own_zoom(self, tmp_path):
        """Folium hardcodes `maximum-scale=1.0, user-scalable=no` into every map
        it writes, and nothing in this project chose it: it takes the browser's
        pinch and double-tap zoom away from the whole document.

        **What it does not achieve is most of it**, and the docstring says so.
        Leaflet sets `touch-action: none` on `.leaflet-container` for a touch
        device and this page's furniture is appended inside that container, which
        fills the screen; a descendant cannot re-grant what an ancestor took
        away. On iOS it never mattered either way. This removes a restriction the
        page was making without meaning to, and no more than that."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7), title="Lomsdal-Visten")
        written = maps.save_map(fmap, tmp_path / "map.html")
        page = written.read_text(encoding="utf-8")
        assert page.count('name="viewport"') == 1
        assert "width=device-width" in page
        assert "user-scalable" not in page
        assert "maximum-scale" not in page

    def test_a_folium_that_stops_writing_it_says_so_at_build_time(self):
        """Rather than leaving a rewrite in place that matches nothing. A silent
        no-op here would put `user-scalable=no` back on the published map and
        every check would stay green."""
        with pytest.raises(AssertionError, match="found 0"):
            maps._viewport("<html><head></head></html>")
        with pytest.raises(AssertionError, match="no longer writes"):
            maps._viewport('<meta name="viewport" content="width=device-width" />')

    def test_the_page_says_a_phone_s_own_width_exactly_once(self):
        """**A tag written across two lines is a tag `grep` cannot see.** Folium's
        map template writes the viewport meta itself, broken over a newline
        inside the tag, and a line-based search for `<meta[^>]*>` reports that
        the page has none. It has had one all along. A second one was added on
        that reading and taken straight back out: folium's renders after the
        head this builds, so the duplicate would have been dead weight that
        merely looked authoritative.

        This asserts the count rather than the text, which is the only form of
        this assertion that could have caught either mistake."""
        html = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7), title="Lomsdal-Visten").get_root().render()
        assert html.count('name="viewport"') == 1
        assert "width=device-width" in html

    def test_a_map_without_a_title_carries_none_of_it(self):
        """`create_map` is used by a dozen tests and by anything else that wants
        a map; a head is something a published page asks for."""
        html = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7)).get_root().render()
        assert "<title>" not in html


class TestTwoMapsOnOneOrigin:
    """A second map beside the first, on the same origin and in the same bucket,
    as its own app: its own worker, manifest, icons, database and caches, and
    another provider's tiles. The first map keeps every name it has -- installed
    copies hold them, and a worker whose address starts answering 404 is a
    registration the browser may drop."""

    @staticmethod
    def abisko(tmp_path):
        companions = maps.Companions.named("abisko")
        fmap = maps.create_map(
            bounds=(18.15, 68.17, 19.0, 68.46),
            base=maps.BaseMap.LANTMATERIET_TOPO,
            extra_bases=(),
            title="Abisko Atlas",
            companions=companions,
        )
        maps.add_chrome(fmap)
        page = tmp_path / "abisko.html"
        page.write_text(fmap.get_root().render(), encoding="utf-8")
        return page, companions

    def test_the_first_map_keeps_its_names(self):
        assert maps.ROOT == maps.Companions()
        assert maps.ROOT.worker == "sw.js"
        assert maps.ROOT.manifest == "manifest.webmanifest"
        assert maps.ROOT.icon_named(180) == "icon-180.png"
        assert maps.ROOT.database == "trails"
        assert maps.ROOT.cache == "trails"
        assert maps.ROOT.scope == "./"

    def test_a_later_map_carries_its_stem_in_every_name(self):
        named = maps.Companions.named("abisko")
        assert named.worker == "abisko-sw.js"
        assert named.manifest == "abisko.webmanifest"
        assert named.icon_named(32) == "abisko-icon-32.png"
        # And a drawing of its own to copy them from: two maps, two marks.
        assert named.mark == "atlas-abisko"
        assert named.database == "trails-abisko"
        assert named.cache == "trails-abisko"
        # A prefix the browser matches: the page itself, and nothing beside it.
        assert named.scope == "./abisko"

    def test_the_stem_alone_decides_the_set(self):
        """One rule, kept in the library so the build and the deploy cannot
        disagree: the first map keeps the root names its installed copies hold,
        every other map carries its stem."""
        assert maps.Companions.of("lomsdal-visten") is maps.ROOT
        assert maps.Companions.of("abisko") == maps.Companions.named("abisko")
        assert maps.FIRST_MAP == "lomsdal-visten"

    def test_every_object_beside_the_page_is_listed(self):
        assert maps.ROOT.files() == ("sw.js", "manifest.webmanifest", "icon-32.png", "icon-180.png", "icon-192.png", "icon-512.png")
        named = maps.Companions.of("abisko").files()
        assert named[:2] == ("abisko-sw.js", "abisko.webmanifest")
        assert named[2:] == tuple(f"abisko-icon-{side}.png" for side in maps.ICON_SIZES)
        assert not set(named) & set(maps.ROOT.files()), "a shared name is the other map's object overwritten"

    def test_the_providers_end_where_their_sources_do(self):
        """Both sheets end at z17, with measured weights at every source level."""
        kartverket, lantmateriet = maps.PROVIDERS["kartverket"], maps.PROVIDERS["lantmateriet"]
        assert kartverket.top == 17 and lantmateriet.top == 17
        assert set(kartverket.weight) == set(range(8, 18))
        assert set(lantmateriet.weight) == set(range(8, 18))
        assert [kartverket.weight[z] for z in range(8, 11)] == [11417, 15036, 18338]
        assert [lantmateriet.weight[z] for z in range(8, 11)] == [16066, 14279, 12273]
        assert lantmateriet.weight[13] == 25719
        # Our own bucket, root-relative: no host in the page, and the same page
        # served locally over the same tree draws the same tiles.
        assert lantmateriet.tiles.startswith("/tiles/lantmateriet/")
        assert "://" not in lantmateriet.tiles
        assert kartverket.tiles == "/tiles/kartverket/topo/1/"
        # Our trees end at their box and the panel's margin must end there too.
        assert lantmateriet.extent == (18.15, 68.139, 19.10, 68.46)
        assert kartverket.extent == (12.0, 65.15, 13.75, 65.95)

    def test_pack_addresses_replace_stand_migration(self):
        worker = maps.SERVICE_WORKER
        for retired in ("migrateStand", "walkStand", "STAND_WALK", "keptFor", "var STAND ="):
            assert retired not in worker
        assert "openCursor(" not in worker
        assert worker.count("openKeyCursor(") == 2, "only bounded trim and explicit Forget visit indexed keys"

    def test_a_tile_tree_version_reaches_the_provider_the_layer_and_the_page(self, tmp_path):
        """A new stand of Lantmäteriet's file is a new version segment; the
        build names it once and the page, its worker and the panel follow."""
        try:
            drawn = maps.tile_tree_version("lantmateriet", 2)
            assert drawn.tiles == "/tiles/lantmateriet/topowebb/2/"
            assert drawn.extent == (18.15, 68.139, 19.10, 68.46), "the rest of the provider is untouched"
            assert maps.provider_of(maps.BaseMap.LANTMATERIET_TOPO) is drawn
            page, companions = self.abisko(tmp_path)
            html = page.read_text(encoding="utf-8")
            assert "/tiles/lantmateriet/topowebb/2/{z}/{x}/{y}.png" in html
            assert 'var TILE_PREFIX = new URL("/tiles/lantmateriet/topowebb/2/", location.href).href;' in html
            worker = maps.write_service_worker(page, maps.PROVIDERS["lantmateriet"], companions).read_text(encoding="utf-8")
            assert "/tiles/lantmateriet/topowebb/2/" in worker
        finally:
            maps.tile_tree_version("lantmateriet", 1)
        assert maps.PROVIDERS["lantmateriet"].tiles == "/tiles/lantmateriet/topowebb/1/"
        try:
            assert maps.tile_tree_version("kartverket", 2).tiles == "/tiles/kartverket/topo/2/"
        finally:
            maps.tile_tree_version("kartverket", 1)

    def test_the_panel_hands_the_page_the_extent_of_its_tree(self, tmp_path):
        """Each page carries the box its own trees were cut to as ``EXTENT``,
        and all six layers end at that same box."""
        page, _companions = self.abisko(tmp_path)
        html = page.read_text(encoding="utf-8")
        assert 'var EXTENT = {"w": 18.15, "s": 68.139, "e": 19.1, "n": 68.46};' in html
        assert "function padded(core, pad, z)" in html
        norway = tmp_path / "lomsdal-visten.html"
        fmap = maps.create_map(bounds=(12.0, 65.0, 13.0, 66.0), companions=maps.Companions.of("lomsdal-visten"))
        maps.add_chrome(fmap)
        maps.save_map(fmap, norway)
        assert 'var EXTENT = {"w": 12.0, "s": 65.15, "e": 13.75, "n": 65.95};' in norway.read_text(encoding="utf-8")

    def test_a_trailing_slash_is_dropped_before_the_companions_are_linked(self, tmp_path):
        """`/abisko/` draws the map at the edge, but `abisko-sw.js` linked
        relatively from there is `/abisko/abisko-sw.js`, which is 404. The
        head's first script trims the slash, ahead of every link."""
        page, _companions = self.abisko(tmp_path)
        html = page.read_text(encoding="utf-8")
        trim = html.index("history.replaceState(history.state, '', path.slice(0, -1)")
        assert trim < html.index('<link rel="apple-touch-icon"')
        assert trim < html.index('<link rel="manifest"')
        assert trim < html.index("navigator.serviceWorker.register(")
        assert "path.length > 1 &&" in html, "the root itself is left alone"

    def test_the_search_folds_the_sami_letters_too(self):
        """ŋ, ŧ and đ have no decomposition, so NFD leaves them and *hongga*
        could not find Hoŋggá; folded beside ø and æ, which are the same case."""
        fmap = maps.create_map(bounds=(18.15, 68.17, 19.0, 68.46))
        group = folium.FeatureGroup(name="Names")
        group.add_to(fmap)
        maps.add_search(fmap, [group])
        html = fmap.get_root().render()
        assert ".replace(/ø/g, 'o').replace(/æ/g, 'ae').replace(/å/g, 'a')" in html
        assert ".replace(/ŋ/g, 'n').replace(/ŧ/g, 't').replace(/đ/g, 'd')" in html

    def test_the_swedish_page_names_no_host_and_no_norwegian_server(self, tmp_path):
        page, _companions = self.abisko(tmp_path)
        html = page.read_text(encoding="utf-8")
        assert "/tiles/lantmateriet/topowebb/1/{z}/{x}/{y}.png" in html
        # The comments still tell Kartverket's story; no address or literal does.
        assert "'kartverket'" not in html
        assert "Lantmäteriet" in html
        assert "hint: 'Which Lantmäteriet sheet is drawn underneath.'" in html
        assert 'var TILE_PREFIX = new URL("/tiles/lantmateriet/topowebb/1/", location.href).href;' in html

    def test_the_swedish_sheet_is_held_to_its_finest_level(self, tmp_path):
        """Leaflet asks for the real tile at every zoom up to `maxNativeZoom`
        and magnifies past it; a sheet ending at z17 is drawn scaled at z18
        rather than requested and answered 404."""
        fmap = maps.create_map(bounds=(18.15, 68.17, 19.0, 68.46), base=maps.BaseMap.LANTMATERIET_TOPO, extra_bases=())
        layers = [child for child in fmap._children.values() if isinstance(child, folium.TileLayer) and not child.overlay]
        assert [(layer.options["max_zoom"], layer.options["max_native_zoom"]) for layer in layers] == [(18, 17)]
        # The relief overlay is drawn over the same sheet and stops two levels
        # earlier, which is where the height model stops having anything to add.
        relief = getattr(fmap, maps.MAP_SHADE_ATTR)
        assert (relief.options["max_zoom"], relief.options["max_native_zoom"]) == (18, 15)
        # Norway uses the same native z17 sheet and z15 overlays.
        norwegian = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        sheets = [child for child in norwegian._children.values() if isinstance(child, folium.TileLayer) and not child.overlay]
        assert {(layer.options["max_zoom"], layer.options["max_native_zoom"]) for layer in sheets} == {(18, 17)}
        over = getattr(norwegian, maps.MAP_SHADE_ATTR)
        assert (over.options["max_zoom"], over.options["max_native_zoom"]) == (18, 15)

    def test_the_page_registers_its_own_worker_at_its_own_scope(self, tmp_path):
        page, _companions = self.abisko(tmp_path)
        html = page.read_text(encoding="utf-8")
        assert "navigator.serviceWorker.register('abisko-sw.js', {scope: './abisko'})" in html
        assert "register('sw.js')" not in html
        # The first map registers as it always has, at the script's own scope.
        first = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7)).get_root().render()
        assert "navigator.serviceWorker.register('sw.js').then" in first

    def test_the_page_does_not_ask_twice_for_a_newer_worker(self, tmp_path):
        """A `registration.update()` after `register()` was here for one evening.
        Measured from the phone against a logging server: Safari fetches the
        script on every `register()` already, and the extra call fetched it a
        second time on every load, uncoalesced — the whole file, since Safari
        mostly sends no validator. Firefox folded the two into one. So the
        eager check doubled the one request already being made, and the
        takeover the worker does on its own is the whole of the mechanism."""
        page, _companions = self.abisko(tmp_path)
        html = page.read_text(encoding="utf-8")
        assert "registration.update" not in html.replace("No `registration.update()`", "")
        assert "registered.update()" not in html
        assert "navigator.serviceWorker.register('abisko-sw.js', {scope: './abisko'}).then(function () {" in html

    def test_the_worker_takes_over_without_waiting_for_every_tab_to_close(self):
        """Asking is only half of it. Without these two a new worker installs and
        then waits, and the page goes on being served by the one it had."""
        source = maps.SERVICE_WORKER
        assert "self.skipWaiting();" in source
        assert "self.clients.claim()" in source

    def test_the_page_opens_its_own_database_and_caches(self, tmp_path):
        page, _companions = self.abisko(tmp_path)
        html = page.read_text(encoding="utf-8")
        assert "window.indexedDB.open('trails-abisko', 6)" in html
        assert "var TERRAIN = 'trails-abisko-terrain';" in html
        assert "var TILES = 'trails-abisko-tiles';" in html
        assert "var KEY = 'trails-abisko-offline';" in html
        assert "var TOP = 17;" in html
        assert '"14": 483317' in html and '"18"' not in html.split("var PACK_WEIGHT = ")[1].split(";")[0]

    def test_the_worker_matches_the_page(self, tmp_path):
        """The two are separate scripts and share nothing but what the build
        wrote into both; a worker naming another map's database would open it."""
        page, companions = self.abisko(tmp_path)
        worker = maps.write_service_worker(page, maps.PROVIDERS["lantmateriet"], companions)
        assert worker.name == "abisko-sw.js"
        script = worker.read_text(encoding="utf-8")
        assert 'var DB = "trails-abisko";' in script
        assert 'var TILES = "trails-abisko-tiles";' in script
        assert 'var TERRAIN = "trails-abisko-terrain";' in script
        assert 'var TILE_PREFIX = new URL("/tiles/lantmateriet/topowebb/1/", self.location.href).href;' in script
        assert "request.url.indexOf(TILE_PREFIX) === 0" in script
        assert not re.search(r"__[A-Z_]+__", script), "a placeholder the build did not fill"

    def test_the_first_maps_worker_still_intercepts_kartverket(self, tmp_path):
        page = tmp_path / "lomsdal-visten.html"
        page.write_text("<html></html>", encoding="utf-8")
        script = maps.write_service_worker(page).read_text(encoding="utf-8")
        assert 'var DB = "trails";' in script
        assert 'var TILES = "trails-tiles";' in script
        assert 'var TILE_PREFIX = new URL("/tiles/kartverket/topo/1/", self.location.href).href;' in script
        # And since §6.10 it keeps this map's three trees beside them, which sit
        # in our own bucket and are therefore addressed from the root.
        assert 'var HEIGHT_PREFIX = "/dem/kartverket/1/" ? new URL("/dem/kartverket/1/", self.location.href).href : null;' in script
        assert 'var SHADE_PREFIX = "/shade/kartverket/1/" ? new URL("/shade/kartverket/1/", self.location.href).href : null;' in script
        assert 'var SLOPE_PREFIX = "/slope/kartverket/1/" ? new URL("/slope/kartverket/1/", self.location.href).href : null;' in script
        assert not re.search(r"__[A-Z_]+__", script)

    def test_the_second_maps_worker_keeps_the_height_tiles_too(self, tmp_path):
        """A straight leg planned offline reads its heights off the tiles, so
        the worker has to answer them from what was kept, like the map tiles."""
        page, companions = self.abisko(tmp_path)
        script = maps.write_service_worker(page, maps.PROVIDERS["lantmateriet"], companions).read_text(encoding="utf-8")
        assert 'var HEIGHT_PREFIX = "/dem/lantmateriet/1/" ? new URL("/dem/lantmateriet/1/", self.location.href).href : null;' in script
        assert "(HEIGHT_PREFIX && request.url.indexOf(HEIGHT_PREFIX) === 0)" in script

    def test_the_offline_panel_keeps_the_height_tiles_at_the_zoom_the_page_reads(self, tmp_path):
        page, _companions = self.abisko(tmp_path)
        html = page.read_text(encoding="utf-8")
        heights = html.split("var HEIGHTS = ")[1].split(";\n")[0]
        assert '"url": "/dem/lantmateriet/1/{z}/{x}/{y}.png"' in heights
        assert '"zoom": 13' in heights
        assert '"13": 92693' in heights
        # Over the same set the map is kept over, after the map tiles of it.
        assert "[HEIGHTS, 'height']" in html
        assert "state.bytes += size;" in html

    def test_the_relief_is_drawn_over_the_sheet_and_is_on_when_the_page_opens(self, tmp_path):
        """What the paper map has and ours had not: a shadow under the contours.
        It is a drawing decision rather than data, so it has a checkbox — and it
        starts on, because the plasticity is the point of building it."""
        fmap = maps.create_map(bounds=(18.15, 68.17, 19.0, 68.46), base=maps.BaseMap.LANTMATERIET_TOPO, extra_bases=())
        relief = getattr(fmap, maps.MAP_SHADE_ATTR)
        assert relief.overlay is True and relief.show is True
        assert relief.options["opacity"] == 0.55
        # Over every base layer whatever order they are switched in.
        assert relief.options["z_index"] == 250
        # Held to the box the tree was cut to, so panning west of it asks for
        # nothing rather than collecting 404s the offline panel reads as a
        # connection giving out.
        assert relief.options["bounds"] == [[68.139, 18.15], [68.46, 19.10]]

    def test_the_relief_is_switched_beside_the_sheet_and_not_among_the_layers(self, tmp_path):
        """It is neither a line nor a point, has no colour for the legend to
        explain and no count; it is how the ground underneath is drawn, which
        is the base-map panel's one question. So its checkbox goes there, under
        the sheets, and the legend stays a list of things with a colour."""
        fmap = maps.create_map(bounds=(18.15, 68.17, 19.0, 68.46), base=maps.BaseMap.LANTMATERIET_TOPO, extra_bases=())
        maps.add_legend(fmap, "Abisko", [maps.LegendRow("a line", "#000", None)])
        html = fmap.get_root().render()
        relief = getattr(fmap, maps.MAP_SHADE_ATTR).get_name()
        assert f"var relief = {relief};" in html
        assert "shading.className = 'trails-relief';" in html
        assert "word.textContent = 'Relief shading';" in html
        assert "picked.appendChild(shading);" in html
        # And a map with no relief says so in the same place, rather than
        # drawing a checkbox that switches nothing. Both of this project's maps
        # carry one since §6.10, so the case is a sheet no tree of ours covers.
        bare = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7), base=maps.BaseMap.OPENSTREETMAP)
        maps.add_legend(bare, "Somewhere", [maps.LegendRow("a line", "#000", None)])
        assert "var relief = null;" in bare.get_root().render()

    def test_the_relief_credits_the_body_whose_model_it_is(self, tmp_path):
        """It is cut from Lantmäteriet's height model and laid over Lantmäteriet's
        sheet. Leaflet keys its attributions by the string, so naming the same
        body twice adds a count rather than a second line."""
        fmap = maps.create_map(bounds=(18.15, 68.17, 19.0, 68.46), base=maps.BaseMap.LANTMATERIET_TOPO, extra_bases=())
        relief = getattr(fmap, maps.MAP_SHADE_ATTR)
        assert relief.options["attribution"] == maps._LANTMATERIET_ATTRIBUTION

    def test_the_relief_is_never_taken_for_the_sheet(self, tmp_path):
        """The offline panel finds the base map by walking the map's layers for
        the first one with tiles. A reader who switches the sheet off and on
        again puts it back behind the overlay, at which point the download would
        fetch the shadow and call it the map."""
        page, _companions = self.abisko(tmp_path)
        html = page.read_text(encoding="utf-8")
        assert "if (layer.options && (layer.options.trailsShade || layer.options.trailsSlope" in html
        assert "|| layer.options.trailsVegetation || layer.options.trailsForest" in html
        assert "|| layer.options.trailsMire)) { return; }" in html
        assert '"trailsShade": true' in html or '"trails_shade": true' in html

    def test_the_vegetation_legend_names_the_ground_nobody_flew(self):
        """Uwe, 2026-09-18: *"Erkenne ich in den Kacheln den Unterschied zwischen kein Bewuchs
        und nicht beflogen?"* -- since the grey, yes, and the legend says which is which."""
        rows = maps.VegetationTiles.classes()
        assert len(rows) == 7
        assert rows[0] == {"from": 10, "to": 20, "colour": vegetation_tiles.COLOURS[0], "label": "10–20 % of the ground"}
        assert rows[-1] == {"colour": vegetation_tiles.UNSURVEYED_COLOUR, "label": "not surveyed by the laser"}
        fmap = maps.create_map(bounds=(18.15, 68.17, 19.0, 68.46), base=maps.BaseMap.LANTMATERIET_TOPO, extra_bases=())
        maps.add_legend(fmap, "Abisko", [maps.LegendRow("a line", "#000", None)])
        html = fmap.get_root().render()
        written = json.loads(html.split("var vegetationClasses = ")[1].split(";\n")[0])
        assert written == rows
        assert "text.textContent = row.label;" in html
        assert "and grey is ground nobody has flown." in html

    def test_the_mire_legend_lists_the_classes_the_tree_carries(self):
        """Three over Sweden, one over Norway (§6.13): a class the data cannot support is not a row."""
        swedish = maps.PROVIDERS["lantmateriet"].mire.classes()
        assert [row["label"] for row in swedish] == ["wet mire, hard going", "mire", "wet ground, soft", "moist ground, usually passable"]
        assert [row["colour"] for row in swedish] == list(mire_tiles.COLOURS)
        assert [row["hatch"] for row in swedish] == [None, None, [2, 2], [2, 6]]
        norwegian = maps.PROVIDERS["kartverket"].mire.classes()
        assert norwegian == [{"colour": mire_tiles.COLOURS[1], "hatch": None, "label": "mire"}]
        fmap = maps.create_map(bounds=(18.15, 68.17, 19.0, 68.46), base=maps.BaseMap.LANTMATERIET_TOPO, extra_bases=())
        maps.add_legend(fmap, "Abisko", [maps.LegendRow("a line", "#000", None)])
        html = fmap.get_root().render()
        written = json.loads(html.split("var mireClasses = ")[1].split(";\n")[0])
        assert written == swedish
        assert "mireWord.textContent = 'Mire and wet ground';" in html
        assert "repeating-linear-gradient(45deg," in html
        assert "solid below z13, and the moist ground from z13 up only" in html
        assert "follows the weather" in html
        layer = getattr(fmap, maps.MAP_MIRE_ATTR)
        assert layer.options["class_name"] == "trails-mire-tiles" and layer.options["z_index"] == 266
        assert layer.options["trails_mire"] is True and layer.show is False
        # The data is credited on the Sources panel, not in the map's foot (2026-09-19).
        assert "Marktäcke" not in layer.options["attribution"]

    def test_the_worker_answers_the_relief_from_what_was_kept(self, tmp_path):
        """A sheet answered from the store with no shadow over it would look
        like the download had half failed."""
        page, companions = self.abisko(tmp_path)
        script = maps.write_service_worker(page, maps.PROVIDERS["lantmateriet"], companions).read_text(encoding="utf-8")
        assert 'var SHADE_PREFIX = "/shade/lantmateriet/1/" ? new URL("/shade/lantmateriet/1/", self.location.href).href : null;' in script
        assert "(SHADE_PREFIX && request.url.indexOf(SHADE_PREFIX) === 0)" in script
        # And a tile of it is found under an older stand like any other.
        assert "[SHADE_PREFIX, 15]" in script

    def test_the_offline_panel_keeps_the_relief_at_every_level_it_draws(self, tmp_path):
        """Unlike the heights, which are read at one zoom and so kept at one:
        the relief is drawn, so a reader who keeps ground to z16 and pans out to
        z12 wants it there too."""
        page, _companions = self.abisko(tmp_path)
        html = page.read_text(encoding="utf-8")
        shade = html.split("var SHADE = ")[1].split(";\n")[0]
        assert '"url": "/shade/lantmateriet/1/{z}/{x}/{y}.png"' in shade
        assert '"top": 15' in shade
        assert "if (z > layer.top) { at += 1; z = OVERVIEW; continue; }" in html
        assert "[SHADE, 'shade']" in html

    def test_the_slope_classes_are_drawn_over_the_relief_and_start_off(self, tmp_path):
        """How steep the ground is, off the paths, in the SLF's classes with one
        of ours below them. Tiles like the relief and directly over it, so a
        class keeps its hue and the shadow only darkens it; off until asked
        for, because an eighth of the ground coloured is a lot of colour for
        a reader following a marked trail."""
        fmap = maps.create_map(bounds=(18.15, 68.17, 19.0, 68.46), base=maps.BaseMap.LANTMATERIET_TOPO, extra_bases=())
        slope = getattr(fmap, maps.MAP_SLOPE_ATTR)
        assert slope.overlay is True and slope.show is False
        assert slope.options["opacity"] == 1.0, "the alpha is in the palette, chosen on the mockup"
        assert slope.options["z_index"] == 260 > getattr(fmap, maps.MAP_SHADE_ATTR).options["z_index"]
        # Multiplied over the sheet, so its lettering stays black: the class
        # name is what the theme's one rule hangs on.
        assert slope.options["class_name"] == "trails-slope-tiles"
        html = fmap.get_root().render()
        assert ".leaflet-layer.trails-slope-tiles, .leaflet-layer.trails-vegetation-tiles," in html
        assert ".leaflet-layer.trails-forest-tiles, .leaflet-layer.trails-mire-tiles { mix-blend-mode: multiply; }" in html
        assert (slope.options["max_zoom"], slope.options["max_native_zoom"]) == (18, 15)
        assert slope.options["bounds"] == [[68.139, 18.15], [68.46, 19.10]]
        assert slope.options["attribution"] == maps._LANTMATERIET_ATTRIBUTION

    def test_the_slope_classes_are_the_documented_ones_and_the_legend_says_whose(self, tmp_path):
        """Four SLF classes, swisstopo's over 50, and ours at either end --
        marked as ours -- one light colour each. The rows sit under the
        checkbox in the base-map panel, beside the relief's, and say what they
        measure: the ground's fall line, where the profile grades the path."""
        fmap = maps.create_map(bounds=(18.15, 68.17, 19.0, 68.46), base=maps.BaseMap.LANTMATERIET_TOPO, extra_bases=())
        maps.add_legend(fmap, "Abisko", [maps.LegendRow("a line", "#000", None)])
        html = fmap.get_root().render()
        slope = getattr(fmap, maps.MAP_SLOPE_ATTR).get_name()
        assert f"var slope = {slope};" in html
        classes = html.split("var slopeClasses = ")[1].split(";\n")[0]
        rows = json.loads(classes)
        assert [row["from"] for row in rows] == [25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0]
        assert rows[-1]["to"] is None and rows[0]["to"] == 30.0
        assert [row["source"] for row in rows] == ["ours", "SLF", "SLF", "SLF", "SLF", "swisstopo", "ours"]
        assert [row["colour"] for row in rows] == list(slope_tiles.COLOURS)
        assert "classing.className = 'trails-slope';" in html
        assert "slopeWord.textContent = 'Slope classes';" in html
        assert "slopeRows.className = 'trails-slope-classes';" in html
        assert "the profile grades the path" in html
        # Drawn under the relief's checkbox, in the same block.
        assert html.index("picked.appendChild(shading);") < html.index("picked.appendChild(classing);")
        bare = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7), base=maps.BaseMap.OPENSTREETMAP)
        maps.add_legend(bare, "Somewhere", [maps.LegendRow("a line", "#000", None)])
        assert "var slope = null;" in bare.get_root().render()

    def test_the_two_ground_switches_are_remembered_across_a_reload(self, tmp_path):
        """Reported from the phone, 2026-09-17: *"Nach jedem Neuladen wird Slope
        Layer wieder deaktiviert."* Both switches say how the ground underneath
        is drawn, which is a state a reader is *in* while they walk — as the
        theme is, as the offline switch is, as plan mode's *stay on paths* is,
        all of which this page already remembers. A page reloaded in a valley
        must not undo what somebody chose on the way up, in either direction:
        the shadow turned off in full sun stays off too.

        **Keyed per map, because both maps share one origin**, under the same
        name the caches and the offline switch carry. And where storage is
        denied — Safari in private browsing throws on read, not only on write —
        the build's own default stands, which is what happened before this
        existed."""
        fmap = maps.create_map(
            bounds=(18.15, 68.17, 19.0, 68.46),
            base=maps.BaseMap.LANTMATERIET_TOPO,
            extra_bases=(),
            companions=maps.Companions.named("abisko"),
        )
        maps.add_legend(fmap, "Abisko", [maps.LegendRow("a line", "#000", None)])
        html = fmap.get_root().render()
        assert 'var GROUND_KEY = "trails-abisko-ground-";' in html
        # What was kept decides, and the build's state is only the fallback.
        assert "shadeTick.checked = groundKept('relief', map.hasLayer(relief));" in html
        assert "slopeTick.checked = groundKept('slope', map.hasLayer(slope));" in html
        # The map is then put into that state, rather than the checkbox being
        # drawn one way and the ground another.
        assert "standAs(relief, shadeTick.checked);" in html
        assert "standAs(slope, slopeTick.checked);" in html
        assert "keepGround('relief', shadeTick.checked);" in html
        assert "keepGround('slope', slopeTick.checked);" in html
        # Denied storage is the build's default and not a crash: Safari in
        # private browsing throws on read, not only on write.
        assert "try { return window.localStorage.getItem(GROUND_KEY + which); } catch (blocked) { return null; }" in html
        assert "return said === null ? fallback : said === 'on';" in html
        # The first map's key is not the second's.
        first = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(first, "Lomsdal", [maps.LegendRow("a line", "#000", None)])
        assert 'var GROUND_KEY = "trails-ground-";' in first.get_root().render()

    def test_the_layers_and_the_chosen_sheet_are_remembered_too(self):
        """Asked for after the two above: *"Auch der Layer Zustand wird
        gemerkt?"* — no, and now yes. Which sheet is underneath and which of the
        map's own layers are drawn over it are the same kind of thing as the
        relief switch, and a reader who put four layers away on the way up had
        them all back at the next reload.

        **The layers under one key, by the name on their row.** One entry
        holding a word per label rather than one key per layer: a build that
        renames a row, adds one or drops one finds nothing for it and takes the
        build's own `show`, and there is nothing left behind to clean up. The
        sheet is kept by its label for the same reason and not by its index — an
        index means a different sheet the day a second one is offered.

        **And only what the reader flipped themself.** A search result in a
        layer that is off switches that layer on, and the tick follows the map;
        nothing is written from there, or looking a place up would quietly
        change what the map draws tomorrow."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        layer = maps.add_trails(
            fmap,
            gpd.GeoDataFrame({"geometry": [LineString([(12.8, 65.4), (12.81, 65.41)])]}, crs="EPSG:4326"),
            name="Paths",
        )
        maps.add_legend(fmap, "Lomsdal", [maps.LegendRow("Paths", "#000", layer)])
        html = fmap.get_root().render()
        # The row takes what was kept and the build's own `show` where nothing was.
        assert "var layersKept = keptLayers();" in html
        assert "? !!row.shown : layersKept[row.label] === 'on';" in html
        assert "standAs(layer, wantRow);" in html
        assert "keepLayer(row.label, tick.checked);" in html
        # One entry, keyed by label, and a broken one reads as nothing kept.
        assert "window.localStorage.setItem(GROUND_KEY + 'layers', JSON.stringify(said));" in html
        assert "} catch (broken) { return {}; }" in html
        # The sheet by its name, and a name this build no longer offers matches
        # nothing at all.
        assert "var wantedBase = keptSheet === null ? -1 : baseLabels.indexOf(keptSheet);" in html
        assert "var wantBase = wantedBase >= 0 ? index === wantedBase : !!baseShown[index];" in html
        assert "window.localStorage.setItem(GROUND_KEY + 'sheet', baseLabels[index]);" in html
        # Nothing is written where the map switches a layer on by itself: the
        # follower only ticks the box.
        follows = html.split("function follow() {")[1].split("}\n")[0]
        assert "keepLayer" not in follows

    def test_the_slope_classes_are_never_taken_for_the_sheet(self, tmp_path):
        page, _companions = self.abisko(tmp_path)
        html = page.read_text(encoding="utf-8")
        assert "if (layer.options && (layer.options.trailsShade || layer.options.trailsSlope" in html
        assert "|| layer.options.trailsVegetation || layer.options.trailsForest" in html
        assert "|| layer.options.trailsMire)) { return; }" in html
        assert '"trailsSlope": true' in html or '"trails_slope": true' in html

    def test_the_worker_answers_the_slope_classes_from_what_was_kept(self, tmp_path):
        page, companions = self.abisko(tmp_path)
        script = maps.write_service_worker(page, maps.PROVIDERS["lantmateriet"], companions).read_text(encoding="utf-8")
        assert 'var SLOPE_PREFIX = "/slope/lantmateriet/2/" ? new URL("/slope/lantmateriet/2/", self.location.href).href : null;' in script
        assert "(SLOPE_PREFIX && request.url.indexOf(SLOPE_PREFIX) === 0)" in script
        assert "[SLOPE_PREFIX, 15]" in script
        assert "[VEGETATION_PREFIX, 15], [FOREST_PREFIX, 15]" in script

    def test_the_offline_panel_keeps_the_slope_classes_whether_or_not_they_are_on(self, tmp_path):
        """The switch is the reader's to flip in the field, and a class that
        was never kept is a blank tile where a wall is. So every level up to
        the tree's top, after the relief of the same level."""
        page, _companions = self.abisko(tmp_path)
        html = page.read_text(encoding="utf-8")
        slope = html.split("var SLOPE = ")[1].split(";\n")[0]
        assert '"url": "/slope/lantmateriet/2/{z}/{x}/{y}.png"' in slope
        assert '"top": 15' in slope
        assert "if (z > layer.top) { at += 1; z = OVERVIEW; continue; }" in html
        assert "[SLOPE, 'slope']" in html
        # And the vegetation and the forest walk after it, each once (§6.11).
        assert "[VEGETATION, 'vegetation']" in html
        assert "[FOREST, 'forest']" in html
        # And the relief is not walked again after the classes.
        assert "[SHADE, 'shade']" in html
        assert "[SLOPE, 'slope']" in html
        assert "slope: SLOPE ? new URL(SLOPE.url.split('{z}')[0], location.href).href : null," in html
        assert "vegetation: VEGETATION ? new URL(VEGETATION.url.split('{z}')[0], location.href).href : null," in html
        assert "forest: FOREST ? new URL(FOREST.url.split('{z}')[0], location.href).href : null" in html
        assert "state.bytes += size;" in html
        assert "size = body.byteLength;" in html

    def test_the_first_map_carries_the_relief_too(self, tmp_path):
        """Since §6.10 Kartverket's sheet has a height model of this project's
        behind it as well, cut off hoydedata.no, so this page draws the shadow
        and the slope classes exactly as the second one does."""
        page = tmp_path / "lomsdal-visten.html"
        fmap = maps.create_map(bounds=(12.0, 65.0, 13.0, 66.0), companions=maps.Companions.of("lomsdal-visten"))
        assert getattr(fmap, maps.MAP_SHADE_ATTR, None) is not None
        assert getattr(fmap, maps.MAP_SLOPE_ATTR, None) is not None
        maps.add_chrome(fmap)
        maps.save_map(fmap, page)
        html = page.read_text(encoding="utf-8")
        assert '"url": "/shade/kartverket/1/{z}/{x}/{y}.png"' in html
        assert '"url": "/slope/kartverket/1/{z}/{x}/{y}.png"' in html
        script = maps.write_service_worker(page, maps.PROVIDERS["kartverket"], maps.Companions.of("lomsdal-visten")).read_text(encoding="utf-8")
        assert 'var SHADE_PREFIX = "/shade/kartverket/1/" ? new URL' in script

    def test_the_first_map_carries_height_tiles_too(self, tmp_path):
        """And reads them rather than a point service, which is what makes a leg
        planned with no network have a profile and a tap have a height (§6.10)."""
        page = tmp_path / "lomsdal-visten.html"
        fmap = maps.create_map(bounds=(12.0, 65.0, 13.0, 66.0), companions=maps.Companions.of("lomsdal-visten"))
        maps.add_chrome(fmap)
        maps.save_map(fmap, page)
        assert '"url": "/dem/kartverket/1/{z}/{x}/{y}.png"' in page.read_text(encoding="utf-8")

    def test_the_manifest_and_the_icons_are_the_maps_own(self, tmp_path):
        page, companions = self.abisko(tmp_path)
        manifest = maps.write_manifest(page, "Abisko Atlas", companions)
        assert manifest.name == "abisko.webmanifest"
        said = json.loads(manifest.read_text(encoding="utf-8"))
        assert said["id"] == "./abisko"
        assert said["start_url"] == "./abisko"
        assert said["scope"] == "./abisko"
        assert [icon["src"] for icon in said["icons"]] == ["./abisko-icon-192.png", "./abisko-icon-512.png"]
        icons = maps.write_icons(page, companions)
        assert [icon.name for icon in icons] == [f"abisko-icon-{side}.png" for side in maps.ICON_SIZES]
        # A variant of the mark, not a copy of it: the two would sit side by side
        # on a Home Screen.
        for icon, side in zip(icons, maps.ICON_SIZES, strict=True):
            assert icon.read_bytes() != (maps.ICON_DIR / f"atlas-{side}.png").read_bytes()
        html = page.read_text(encoding="utf-8")
        assert '<link rel="manifest" href="abisko.webmanifest">' in html
        assert '<link rel="apple-touch-icon" href="abisko-icon-180.png">' in html
        assert '<link rel="icon" type="image/png" sizes="32x32" href="abisko-icon-32.png">' in html
        # And none of the first map's names, which would be its files overwritten.
        assert not (tmp_path / "sw.js").exists() and not (tmp_path / "manifest.webmanifest").exists()
        assert not (tmp_path / "icon-180.png").exists()

    def test_a_base_without_a_provider_draws_but_cannot_keep(self):
        """OpenStreetMap's tiles are nobody's to copy into a bucket, so a map
        on them gets no offline panel -- said at `add_chrome`, not in a browser."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7), base=maps.BaseMap.OPENSTREETMAP, extra_bases=())
        with pytest.raises(KeyError, match="no tile provider"):
            maps.add_chrome(fmap)


class TestHeightTiles:
    """The height tiles beside a provider's map tiles, and what the page is told about them."""

    def test_both_providers_carry_them_each_under_its_own_directory(self):
        """A directory per source, because the two are stacked and never mixed
        (§6.3's address line, kept when Norway got its own tree in §6.10)."""
        swedish = maps.PROVIDERS["lantmateriet"].heights
        norwegian = maps.PROVIDERS["kartverket"].heights
        assert swedish is not None and norwegian is not None
        assert swedish.template == "/dem/lantmateriet/1/{z}/{x}/{y}.png"
        assert norwegian.template == "/dem/kartverket/1/{z}/{x}/{y}.png"
        # One ceiling, because a z13 pixel is 7.1 m at Abisko and 7.9 m here and
        # neither model has more to give past it.
        assert swedish.top == norwegian.top == 13

    def test_the_ground_trees_are_cut_over_the_same_box_the_extent_names(self):
        """The three trees and the panel's margin are one box, or the margin is
        a row of 404s (§8.2). Written once in `processing.trees` and read here."""
        from trails.processing import trees as tree_table

        for key, park in (("lantmateriet", "abisko"), ("kartverket", "lomsdal-visten")):
            provider, tree = maps.PROVIDERS[key], tree_table.TREES[park]
            assert provider.extent == tree.box
            assert provider.heights is not None and provider.heights.tiles == tree.prefix("dem")
            assert provider.shade is not None and provider.shade.tiles == tree.prefix("shade")
            assert provider.slope is not None and provider.slope.tiles == tree.prefix("slope")
            assert provider.shade.top == provider.slope.top == tree.ground_max_zoom

    def test_the_settings_carry_the_packing_the_tiles_were_written_with(self):
        """The page unpacks a pixel by the same two numbers `dem_tiles` packed
        it with, handed over rather than spelled twice."""
        from trails.processing import dem_tiles

        settings = maps.HeightTiles(tiles="/dem/x/1/", top=12, weight={12: 100}).as_settings()
        assert settings == {
            "url": "/dem/x/1/{z}/{x}/{y}.png",
            "zoom": 12,
            "offset": dem_tiles.TERRARIUM_OFFSET,
            "step": dem_tiles.TERRARIUM_STEP,
            "weight": {"12": 100},
            "pack_weight": {},
        }

    def test_a_plan_with_tiles_needs_no_service_and_one_with_neither_is_refused(self):
        fmap, _ = TestPlanMode().drawn()
        planned = TestPlanMode().planned(heightsUrl="", heightsTiles=maps.PROVIDERS["lantmateriet"].heights.as_settings())
        maps.add_plan_mode(fmap, planned)
        html = fmap.get_root().render()
        assert '"heightsTiles": {"url": "/dem/lantmateriet/1/{z}/{x}/{y}.png"' in html
        assert "if (PLAN.heightsTiles) {" in html
        # The reader: bilinear between the four pixel centres, (0, 0, 0) as no height,
        # and a 1 x 1 answer -- the worker's blank -- as a tile that is not there.
        assert "r * 256 + g + b / tiles.step - tiles.offset" in html
        assert "read.width === HEIGHT_TILE_PX && read.height === HEIGHT_TILE_PX ? read : null" in html
        with pytest.raises(ValueError, match="heightsUrl or heightsTiles"):
            maps.add_plan_mode(fmap, TestPlanMode().planned(heightsUrl=""))


class TestPins:
    """The map draws its own pins, which is what the last third-party host was for."""

    def test_a_pin_is_a_colour_and_an_outline(self):
        """awesome-markers was 42,683 bytes of script, stylesheet and rotation
        rules plus four sprite images, for a coloured teardrop with a glyph in
        it. The glyph is a nested `<svg>` with its own viewBox, so Font Awesome's
        outline scales into the bulb without a number worked out by hand."""
        drawn = maps._pin("darkred", "house-chimney")
        assert 'fill="#a23336"' in drawn
        assert maps.PIN_SHAPE in drawn
        assert maps.MARKER_ICONS["house-chimney"][1] in drawn
        assert 'class="trails-pin"' in drawn

    def test_an_outline_this_page_does_not_carry_is_said(self):
        """A `KeyError` with one word in it is not an answer. The page carries
        the outlines it draws and nothing else -- a webfont for the whole of Font
        Awesome was 252 kB for four glyphs -- so asking for a fifth is a thing to
        be told about at build time, with the answer in the message."""
        with pytest.raises(ValueError, match="this page draws"):
            maps._pin("darkred", "home")
        with pytest.raises(ValueError, match="no pin colour"):
            maps._pin("puce", "ship")

    def test_the_palette_is_the_whole_one_and_not_the_five_in_use(self):
        """`add_points` takes a colour by name and always has. Narrowing it to
        what one caller happens to ask for turns a working argument into a
        `KeyError` for the next one, which is what five tests said when it was
        tried."""
        assert {"red", "green", "orange", "black"} <= set(maps.PIN_COLOURS)
        assert maps.PIN_COLOURS["darkred"] == "#a23336"

    def test_the_pins_shrink_when_the_reader_is_far_out(self):
        """Reported: they are too big, and most of all zoomed out -- 198 of them
        at 35 x 45 over the terrain at the zoom this park opens at.

        Scaled and not resized, and about the **tip**: Leaflet puts its own
        transform on the icon element to place it, so the scale lives on a span
        inside, and `transform-origin: bottom center` keeps the point of the pin
        on the position it marks at every zoom.
        """
        html = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7)).get_root().render()
        assert "map.getContainer().style.setProperty('--trails-pin', scale.toFixed(3));" in html
        assert "transform-origin: bottom center; transform: scale(var(--trails-pin, 1));" in html
        # An inline `<svg>` in a block gets a descender's worth of space under
        # it, which scaled about the bottom lifts the tip off the position.
        assert ".trails-pin { display: block; line-height: 0;" in html


class TestPopupShape:
    """What a whole layer's popups have in common, worked out once.

    A popup used to be markup built per feature at build time. It is a shape per
    layer and a list of values per feature now, put together in the browser when
    a reader opens one -- so these say what travels, and `TestPopupText` says
    what the page makes of it.
    """

    def test_the_labels_travel_and_the_columns_do_not_leave_the_build(self, trails):
        shape = maps._popup_shape(trails, {"trail_name": "Route", "difficulty": "Difficulty"})

        assert shape["labels"] == ["Route", "Difficulty"]
        assert shape["columns"] == ["trail_name", "difficulty"]

    def test_a_column_the_layer_does_not_have_is_dropped_once(self, trails):
        """Not per row: a column the frame lacks is missing from every row of it,
        and the values are read positionally against these labels."""
        shape = maps._popup_shape(trails, {"trail_name": "Route", "absent": "Absent"})

        assert shape["labels"] == ["Route"]
        assert shape["columns"] == ["trail_name"]

    def test_a_layer_with_nothing_to_show_has_no_shape(self, trails):
        assert maps._popup_shape(trails, {"absent": "Absent"}) is None

    def test_the_source_and_the_heading_travel_once(self, trails):
        gdf = trails.copy()
        gdf["ut_url"] = "https://ut.no/turforslag/1113860"
        shape = maps._popup_shape(gdf, {"trail_name": "Route"}, {"ut_url": "Route page"}, "Turrutebasen", "Published elsewhere")

        assert shape["source"] == "Turrutebasen"
        assert shape["heading"] == "Published elsewhere"
        assert shape["links"] == ["Route page"]

    def test_a_link_column_may_hold_a_page_per_state_trail(self, trails):
        """The register's state trails run on into each other, so one chain is
        *BD 21 / BD 92 / BD 16 / BD 91* and four Naturkartan pages describe it.
        One text per column cannot name four pages: the column carries
        (text, url) pairs, the page writes one link per pair, and a pair whose
        URL is not http(s) is dropped as a bare URL would be."""
        gdf = trails.copy()
        gdf["naturkartan"] = [
            (("→ BD 21 on Naturkartan", "https://www.naturkartan.se/sv/bd21"), ("→ BD 92 on Naturkartan", "javascript:alert(1)")),
            None,
        ]
        shape = maps._popup_shape(gdf, {"trail_name": "Route"}, {"naturkartan": "→ On Naturkartan"}, "Leder", "Published elsewhere")

        assert shape["links"] == ["→ On Naturkartan"]
        assert maps._popup_values(gdf.iloc[0], shape) == ["Sjøbergmarsjen", [["→ BD 21 on Naturkartan", "https://www.naturkartan.se/sv/bd21"]]]
        # A chain without a page says nothing under the heading, as before.
        assert maps._popup_values(gdf.iloc[1], shape) == []
        # And the page writes each pair as a link of its own, with its own text.
        assert "values[at].forEach(function (pair) { link(pair[1], pair[0]); })" in files("trails.visualization").joinpath(
            "js", "popup_text.js"
        ).read_text(encoding="utf-8")

    def test_what_somebody_else_states_travels_in_its_own_group(self, trails):
        """A route's own site saying *23,4 km, 2 d, +1088 m* is their claim, not
        this map's measurement — and it stood among the figures above, where it
        read as one of them disagreeing with the length by a kilometre. It goes
        under the same heading as their pages."""
        gdf = trails.copy()
        gdf["ut_summary"] = "23,4 km, 2 d, +1088 m"
        shape = maps._popup_shape(
            gdf,
            {"trail_name": "Route"},
            source="UT.no",
            link_heading="Published elsewhere, not by this map",
            published_fields={"ut_summary": "UT.no states"},
        )

        assert shape["labels"] == ["Route"]
        assert shape["published"] == ["UT.no states"]
        # And the values follow the same three groups in the same order, or a
        # positional list is read against the wrong labels.
        assert maps._popup_values(gdf.iloc[0], shape) == ["Sjøbergmarsjen", "23,4 km, 2 d, +1088 m"]

    def test_a_stated_figure_alone_is_enough_for_a_shape(self, trails):
        """A layer whose only popup content is somebody else's claim still has
        one to show."""
        gdf = trails.copy()
        gdf["ut_summary"] = "23,4 km"
        assert maps._popup_shape(gdf, {"absent": "Absent"}, published_fields={"ut_summary": "UT.no states"}) is not None

    def test_a_source_alone_is_enough_for_a_shape(self, trails):
        """A feature the source says nothing else about should still name it."""
        assert maps._popup_shape(trails, {"absent": "Absent"}, source="N50") is not None

    def test_only_the_shape_reaches_the_page_and_not_the_columns(self, trails):
        """The column a value was read from is the build's business, and there
        are eleven of them per layer."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_trails(fmap, trails, name="Paths [N50]", popup_fields={"trail_name": "Route"}, source="N50")

        html = fmap.get_root().render()
        assert '"labels": ["Route"]' in html
        assert '"source": "N50"' in html
        assert '"columns"' not in html


class TestPopupValues:
    """What one feature carries, positionally, against its layer's labels."""

    def test_a_missing_value_is_a_hole_and_not_a_row(self, trails):
        shape = maps._popup_shape(trails, {"trail_name": "Route", "difficulty": "Difficulty"})

        assert maps._popup_values(trails.iloc[0], shape) == ["Sjøbergmarsjen", "Easy (Green)"]

    def test_a_row_that_fills_nothing_carries_nothing(self, trails):
        shape = maps._popup_shape(trails, {"trail_name": "Route", "difficulty": "Difficulty"})

        assert maps._popup_values(trails.iloc[1], shape) is None

    def test_a_source_alone_is_enough_for_a_popup(self, trails):
        """The empty list is the feature whose only line is its source, and it
        is not the same as no popup at all."""
        shape = maps._popup_shape(trails, {"trail_name": "Route"}, source="N50")

        assert maps._popup_values(trails.iloc[1], shape) == []

    def test_trailing_holes_are_dropped(self, trails):
        """A short list is read exactly as a padded one, and most rows are short."""
        gdf = trails.copy()
        gdf["ut_url"] = None
        shape = maps._popup_shape(gdf, {"trail_name": "Route"}, {"ut_url": "Route page"})

        assert maps._popup_values(gdf.iloc[0], shape) == ["Sjøbergmarsjen"]

    def test_everything_travels_as_text(self, trails):
        """What the build wrote into the markup, and what JSON can carry: a
        numpy float is neither."""
        gdf = trails.copy()
        gdf["length_km"] = [4.2, 7.0]
        shape = maps._popup_shape(gdf, {"length_km": "Length"})

        assert maps._popup_values(gdf.iloc[0], shape) == ["4.2"]

    def test_a_link_travels_as_its_url(self, trails):
        row = trails.iloc[1].copy()
        row["ut_url"] = "https://ut.no/turforslag/1"
        gdf = trails.copy()
        gdf["ut_url"] = "https://ut.no/turforslag/1"
        shape = maps._popup_shape(gdf, {}, {"ut_url": "Route"})

        assert maps._popup_values(row, shape) == ["https://ut.no/turforslag/1"]

    def test_rejects_non_http_links(self, trails):
        """A URL from a data file must not be able to run script on click, and
        the browser is handed no chance to try: it never leaves the build."""
        row = trails.iloc[0].copy()
        row["ut_url"] = "javascript:alert(1)"
        gdf = trails.copy()
        gdf["ut_url"] = "javascript:alert(1)"
        shape = maps._popup_shape(gdf, {"trail_name": "Route"}, {"ut_url": "Open"})

        assert maps._popup_values(row, shape) == ["Sjøbergmarsjen"]

    def test_a_missing_link_is_a_hole(self, trails):
        gdf = trails.copy()
        gdf["guide_url_en"] = None
        shape = maps._popup_shape(gdf, {"trail_name": "Route"}, {"guide_url_en": "Description"})

        assert maps._popup_values(gdf.iloc[0], shape) == ["Sjøbergmarsjen"]


class TestPopupText:
    """The table itself, which is written once and runs in the browser.

    Every popup on the built page used to be markup in the file -- 12,898 of
    them, 16.62 MB, handed to jQuery before the map drew anything, to show one
    at a time. This is the same table, built when a reader opens one.
    """

    @pytest.fixture
    def page(self, trails) -> str:
        """A page with a layer whose popups carry a value, a link and a source."""
        gdf = trails.copy()
        gdf["ut_url"] = "https://ut.no/turforslag/1113860"
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_trails(
            fmap,
            gdf,
            name="UT.no",
            popup_fields={"trail_name": "Route"},
            link_fields={"ut_url": "Route page"},
            source="UT.no",
            link_heading="Published elsewhere",
        )
        return fmap.get_root().render()

    def test_it_is_built_when_one_is_opened(self, page):
        """Leaflet takes a function as popup content and calls it on open, which
        is the whole mechanism."""
        assert "layer.bindPopup(function (source) {" in page
        assert "return window.trailsPopup(shape, source.options.popup);" in page

    def test_a_feature_with_no_popup_is_passed_over_and_an_empty_one_is_not(self, page):
        """An empty list is a feature whose only line is the source, and an empty
        list is falsy."""
        assert "if (!layer.options || layer.options.popup === undefined) { return; }" in page

    def test_the_values_ride_on_the_layer(self, trails):
        gdf = trails.copy()
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, gdf, name="Paths [N50]", popup_fields={"trail_name": "Route"}, source="N50")

        lines = [child for child in group._children.values() if isinstance(child, folium.PolyLine)]
        # Three lines from two rows, because the second row is a
        # MultiLineString -- and it fills no field, so both of its lines carry
        # the empty list and show the source alone.
        assert [line.options["popup"] for line in lines] == [["Sjøbergmarsjen"], [], []]

    def test_the_rows_are_the_rows_the_build_wrote(self, page):
        assert "\"<tr><td style='padding:2px 8px 2px 0;color:var(--trails-ink-3)'>\" + esc(shape.labels[i])" in page
        assert '"</td><td style=\'padding:2px 0\'><b>" + esc(values[at]) + "</b></td></tr>"' in page
        assert "return \"<table style='font-family:sans-serif;font-size:12px'>\" + rows.join('') + \"</table>\";" in page

    def test_every_string_it_writes_is_escaped(self, page):
        """Values are third-party data and must not be able to inject markup."""
        assert "var AS = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '\"': '&quot;', \"'\": '&#x27;'};" in page
        assert "function esc(text) { return String(text).replace(MARKUP, function (c) { return AS[c]; }); }" in page
        # A link's URL and text both pass through `link(url, text)`, whether
        # the text is the column's or a pair's own.
        for written in ("shape.labels[i]", "values[at]", "shape.heading", "url", "text", "shape.source"):
            assert f"esc({written})" in page
        assert "link(values[at], shape.links[i]);" in page
        assert "link(pair[1], pair[0]);" in page

    def test_a_link_cannot_reach_back_into_this_page(self, page):
        assert 'target=\\"_blank\\" rel=\\"noopener noreferrer\\"' in page

    def test_the_heading_stands_above_the_first_link_that_survives(self, page):
        """A route with no description elsewhere must not get a heading over nothing."""
        assert "if (shape.heading && !written) {" in page
        assert page.index("if (shape.heading && !written) {") < page.index('esc(text) + "</a></td></tr>"')

    def test_the_source_is_set_off_by_a_rule(self, page):
        assert "border-top:1px solid var(--trails-rule);" in page
        assert '"color:var(--trails-ink-4)\'>Source: " + esc(shape.source)' in page

    def test_a_table_with_no_rows_is_not_a_popup(self, page):
        assert "if (!rows.length) { return null; }" in page

    def test_it_is_written_before_any_layer_that_calls_it(self, trails):
        """Folium renders a map's children in the order they were added, and the
        layers are added after `create_map` returns."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_trails(fmap, trails, name="Paths [N50]", popup_fields={"trail_name": "Route"})

        html = fmap.get_root().render()
        assert html.index("window.trailsPopup = (function () {") < html.index("window.trailsPopup(shape,")


class TestWhatSomebodyElseStates:
    """Their figures under their heading, and ours above it."""

    def test_the_heading_stands_before_the_first_thing_under_it(self, trails):
        """Above the first row that survives and not above the block: a route
        with nothing published about it would otherwise get a heading over
        nothing at all. That rule used to be the links'; the stated figures come
        first now, so it is written once and both of them call it."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_trails(fmap, trails, name="Routes [UT.no]", popup_fields={"trail_name": "Route"}, source="UT.no")

        html = fmap.get_root().render()
        assert "function heading() {" in html
        assert "var stated = shape.published || [];" in html
        # The stated rows are written in the same hand as the figures above them
        # — the reader is told which is which by the heading, not by the styling.
        assert "for (i = 0; i < stated.length; i++, at++) {" in html
        assert html.index("var stated = shape.published") < html.index("for (i = 0; i < shape.links.length")


class TestLabelledPoints:
    """Tests for add_labelled_points."""

    def test_a_click_opens_a_popup_when_fields_are_given(self, shelters):
        """Without one the dot is interactive but answers nothing, which reads as broken."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_labelled_points(fmap, shelters, name="Places [SSR]", popup_fields={"name": "Name"}, source="SSR")

        markers = [child for child in group._children.values() if isinstance(child, folium.CircleMarker)]
        # The second shelter has no name, so it is not drawn at all.
        assert [marker.options.get("popup") for marker in markers] == [["Stavassgården"]]

    def test_the_popup_names_its_source(self, shelters):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_labelled_points(fmap, shelters, name="Places [SSR]", popup_fields={"name": "Name"}, source="SSR")

        assert '"source": "SSR"' in fmap.get_root().render()

    def test_without_popup_fields_only_the_tooltip_remains(self, shelters):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_labelled_points(fmap, shelters, name="Places")

        markers = [child for child in group._children.values() if isinstance(child, folium.CircleMarker)]
        assert not any("popup" in marker.options for marker in markers)
        assert "window.trailsPopup(shape," not in fmap.get_root().render()

    def test_labels_are_recorded_for_the_search(self, shelters):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_labelled_points(fmap, shelters, name="Places")

        assert "Stavassgården" in getattr(group, maps.SEARCH_NAMES_ATTR).values()


class TestCanvas:
    """The map draws into a canvas, and what had to move with it."""

    def test_the_map_draws_into_a_canvas(self):
        """Leaflet writes a `d` attribute per path on every move, and with
        11,589 of them that write is the largest single cost of a pan. Measured
        at 390 x 844 with a coarse pointer, the median of six `setView` steps:
        51 ms with SVG against 34 with canvas, and 12,472 DOM elements to 882.
        """
        html = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7)).get_root().render()

        assert '"preferCanvas": true' in html

    def test_the_legend_says_what_the_map_holds(self, trails):
        """Reported from the phone: a search result in a layer that was switched
        off switches that layer on -- which is what it is for -- and the legend
        went on saying *off* about names that were drawn. The only way back was
        to tick the row on and off again.

        Leaflet fires `layeradd` and `layerremove` for every add and remove,
        whoever asked, so following them is following the map. Collapsed into one
        repaint, because a group adds its features one by one and each is an
        event -- 12,461 of them on the Lomsdal page for a single tick."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="Paths", search_field="trail_name")
        maps.add_legend(fmap, "What is drawn", [maps.LegendRow("Paths", "#000000", group)])

        html = fmap.get_root().render()
        assert "map.on('layeradd layerremove', function () {" in html
        assert "if (row.tick && row.layer) { row.tick.checked = map.hasLayer(row.layer); }" in html
        # One repaint and not one per feature.
        assert "if (following) { return; }" in html

    def test_the_search_draws_nothing_and_hides_nothing(self, trails):
        """It used to reach into how every feature was drawn -- `display` on an
        element, `stroke` and `interactive` on a canvas layer that has none --
        in order to leave only the matches standing. A list answers the same
        question without touching the map, so none of that is here any more."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="Paths", search_field="trail_name")
        maps.add_search(fmap, [group])

        html = fmap.get_root().render()
        box = html[html.index("var ROWS = 24;") : html.index("window.trailsSearch = {")]
        code = "\n".join(line for line in box.splitlines() if not line.strip().startswith("//"))
        assert "setStyle" not in code
        assert "layer._path" not in code
        assert "layer._icon" not in code
        assert "options.interactive" not in code
        # And the one property it does decide -- which rows there are -- is
        # nothing the highlight uses, so the two still cannot undo each other.
        assert "opacity" not in code

    def test_a_row_is_the_thing_itself(self, trails):
        """Everything a click on a line does is wired to that event already, so
        a row fires the click rather than doing any of it a second way -- and
        without the point it was tapped at, which is what keeps the panel's own
        row of choices still."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="Paths", search_field="trail_name")
        maps.add_search(fmap, [group])

        html = fmap.get_root().render()
        assert "found.entry.layer.fire('click', {layer: found.entry.layer});" in html

    def test_a_row_switches_its_own_layer_on(self, shelters):
        """A layer that is off holds its features and draws none of them, so a
        row of it would otherwise move the map to a blank spot."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_points(fmap, shelters, name="Huts", label_field="name")
        maps.add_search(fmap, [group])

        html = fmap.get_root().render()
        assert "if (!map.hasLayer(groups[found.entry.group])) { map.addLayer(groups[found.entry.group]); }" in html

    def test_a_row_taken_on_a_phone_gets_the_panel_out_of_the_way(self, shelters):
        """On a narrow screen the list stands in the dock, over the map, and the
        thing a row names would land behind it: at 390 x 844 the dock takes the
        top 500 px and the map's middle is at 422."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_points(fmap, shelters, name="Huts", label_field="name")
        maps.add_search(fmap, [group])

        html = fmap.get_root().render()
        assert "if (window.trailsChrome && window.trailsChrome.narrow && window.trailsChrome.narrow()) {" in html

    def test_a_position_is_read_and_marked(self, shelters):
        """What the picker copies, read back: the same five decimals, and a mark
        that offers what a place offers."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_points(fmap, shelters, name="Huts", label_field="name")
        maps.add_search(fmap, [group])

        html = fmap.get_root().render()
        assert "function readCoordinate(text) {" in html
        assert "return at.lat.toFixed(5) + ', ' + at.lon.toFixed(5);" in html
        assert "mark.openPopup();" in html
        # **And the mark's own page does not offer the goal.** The chrome puts
        # *Set as goal* on the page of every popup that has one position, and a
        # second offer here was the same button twice.
        made = html[html.index("function markPage(at) {") : html.index("function dropMark() {")]
        assert "trails-goal-take" not in made
        assert "goalOffer" not in html

    def test_a_position_needs_something_between_its_two_sides(self, shelters):
        """Measured while it was written: with the separator optional, the
        expression backed off and read `68.39275` alone as `68.3927, 5`."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_points(fmap, shelters, name="Huts", label_field="name")
        maps.add_search(fmap, [group])

        assert "'(?:\\\\s*[,;]\\\\s*|\\\\s+)' +" in fmap.get_root().render()


class TestAFingerCanHitALine:
    """Reported from a phone: a trail can only be selected by tapping around.

    The cause is in leaflet 1.9.4 and was read there rather than guessed at.
    The map draws into a canvas, so a hit is Leaflet's own arithmetic:
    ``Path._clickTolerance`` is ``weight / 2`` plus the renderer's ``tolerance``
    option, which is ``0``. A 3 px line has to be hit within 1.5 px of its
    centre. And ``Draggable.options.clickTolerance`` is 3, so a finger that
    rolls two pixels while pressing has dragged the map -- after which
    ``Canvas._onClick`` asks ``_draggableMoved`` and throws the hit away
    altogether.
    """

    @staticmethod
    def rendered():
        return maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7)).get_root().render()

    def test_the_halo_is_measured_from_the_paint(self):
        """A 4 px line and a 2 px line reach the same distance beyond what a
        reader can see, which is the distance a reader is aiming at."""
        html = self.rendered()
        assert f"var FINGER = {maps.FINGER_PX};" in html
        assert "var paint = layer.options.stroke ? (layer.options.weight || 0) / 2 : 0;" in html
        assert "return near === Infinity ? null : Math.max(0, near - paint);" in html

    def test_the_nearest_line_wins_and_not_the_topmost(self):
        """Leaflet keeps the last layer in draw order that contains the point,
        which is right at 1.5 px and wrong at 13: six sources run through one
        valley here, and `_ClickHighlight` calls `bringToFront` on the one it
        selects -- so the last selection would go on winning every nearby tap."""
        html = self.rendered()
        assert "if (gap <= best) { best = gap; hit = layer; }" in html
        assert "this._fireEvent(hit ? [hit] : false, event);" in html

    def test_a_mouse_keeps_leaflet_s_own_handler(self):
        """Nothing about a fine pointer moves -- including which line a hover
        names, which is decided by a handler this does not touch."""
        html = self.rendered()
        assert "var leaflets = L.Canvas.prototype._onClick;" in html
        assert "if (!coarse()) { return leaflets.call(this, event); }" in html
        assert "var MOUSE_SLOP = L.Draggable.prototype.options.clickTolerance;" in html

    def test_a_finger_may_roll_and_still_be_a_tap(self):
        html = self.rendered()
        assert f"var SLOP = {maps.TAP_SLOP_PX};" in html
        assert "L.Draggable.mergeOptions({clickTolerance: coarse() ? SLOP : MOUSE_SLOP});" in html

    def test_a_line_nobody_can_see_cannot_take_the_tap(self):
        """The search filter hides a canvas line by clearing `interactive`,
        because there is no element to hide. The widened reach has to respect
        that or a hidden line would answer a tap from thirteen pixels away."""
        assert "if (!layer.options.interactive) { continue; }" in self.rendered()

    def test_it_is_set_up_before_any_line_is_drawn(self, trails):
        """`Path._updateBounds` pads `_pxBounds` with the reach that was in
        force when the path was projected, and `_containsPoint` refuses anything
        outside that box before measuring a segment. The hit test here carries
        its own padding, so nothing is broken by a late setup -- but the two
        answers stay the same only while this runs first."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="Paths", color="#1b5e20")

        html = fmap.get_root().render()
        assert html.index("window.trailsReach = {") < html.index(f"var {group.get_name()} = L.featureGroup")

    def test_the_chrome_tells_it_when_the_pointer_changes(self):
        """The reach reads the class on every tap, but Leaflet's drag threshold
        is merged rather than read, so that one has to be told."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "window.trailsReach.recount();" in html

    def test_plan_mode_tells_a_tap_from_a_pan_by_the_same_number(self):
        """It takes every click before Leaflet sees one, so it decides this for
        itself -- and a 3 px test of its own would drop a five-pixel roll that
        moved nothing, which is a tap that does nothing at all."""
        planning = files("trails.visualization").joinpath("js", "plan_mode.js").read_text(encoding="utf-8")
        assert "var slop = window.trailsReach ? window.trailsReach.slop() : 3;" in planning
        assert "Math.abs(event.clientX - pressed.x) + Math.abs(event.clientY - pressed.y) >= slop" in planning


class TestClickHighlight:
    """Tests for add_click_highlight."""

    def test_it_can_be_let_go_of_without_a_click(self, trails):
        """Both of its ways out are clicks -- on the line, or on empty ground --
        and something else can own those. Plan mode does, so the highlight needs
        a way in that is not a click or it dims the map with no way back.
        """
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="Paths", color="#1b5e20")
        maps.add_click_highlight(fmap, [group])

        html = fmap.get_root().render()

        assert "window.trailsHighlight = {" in html
        assert "clear: clear," in html
        assert "selected: function () { return selected; }" in html

    def test_renders_after_the_layers_it_drives(self, trails):
        """The snippet names the feature groups, so they must exist by then."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="UT.no", group_field="trail_name")
        maps.add_click_highlight(fmap, [group])

        html = fmap.get_root().render()
        assert html.index(f"var {group.get_name()} = L.featureGroup") < html.index(f"var groups = [{group.get_name()}]")

    def test_uses_the_given_boost_and_dimming(self, trails):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="UT.no", group_field="trail_name")
        maps.add_click_highlight(fmap, [group], weight_boost=6.0, dim_opacity=0.3)

        html = fmap.get_root().render()
        assert "var boost = 6.0;" in html
        assert "var dim = 0.3;" in html

    def test_without_groups_nothing_is_added(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_click_highlight(fmap, [])

        assert "var groups = [" not in fmap.get_root().render()

    def test_the_chosen_line_is_lifted_over_the_planned_route(self):
        """Reported from the device: a chosen line stays *under* the planned
        route. `bringToFront` can only reach as far as its own pane, and that is
        not a stacking accident but the arrangement — the trails are Leaflet's
        overlay pane at 400 and a planned route has a pane of its own at 460 —
        so widening a line the route runs along widened something nobody could
        see.

        It is drawn a second time in a pane above it rather than moved: a canvas
        layer belongs to the renderer of the pane it was made in, and moving it
        would mean taking it out of the group the legend switches. The copy
        takes no clicks, so the line underneath is still the thing being tapped
        and the reach that ranks what a tap could have meant skips it."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = folium.FeatureGroup(name="Trails").add_to(fmap)
        maps.add_click_highlight(fmap, [group])

        html = fmap.get_root().render()
        assert "var pane = map.createPane('trailsPicked');" in html
        assert "pane.style.zIndex = 465;" in html
        assert "pane.style.pointerEvents = 'none';" in html
        assert "interactive: false, pane: liftPane(), className: 'trails-picked'" in html
        # A chain split into pieces is several layers and one selection.
        assert "lift(layer);" in html
        # And it goes when the selection does, or the map would keep a widened
        # line nothing on the page still claims.
        assert "lifted.forEach(function (copy) { map.removeLayer(copy); });" in html
        assert html.count("drop();") == 2


class TestAddTrails:
    """Tests for add_trails."""

    def test_adds_one_polyline_per_line_part(self, trails):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="Turrutebasen")

        polylines = [child for child in group._children.values() if isinstance(child, folium.PolyLine)]
        # One plain LineString plus two parts of the MultiLineString.
        assert len(polylines) == 3

    def test_tooltip_field_labels_each_line(self, trails):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="UT.no", tooltip_field="trail_name")

        polyline = next(child for child in group._children.values() if isinstance(child, folium.PolyLine))
        tooltip = next(child for child in polyline._children.values() if isinstance(child, folium.Tooltip))
        assert tooltip.text == "Sjøbergmarsjen"

    def test_source_reaches_every_popup(self, trails):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="Paths [N50]", popup_fields={"trail_name": "Route"}, source="N50")

        lines = [child for child in group._children.values() if isinstance(child, folium.PolyLine)]
        # Every drawn line gets one, including the row with no populated field,
        # and the source itself is said once for the layer.
        assert len(lines) == 3
        assert all("popup" in line.options for line in lines)
        assert '"source": "N50"' in fmap.get_root().render()

    def test_link_fields_reach_the_popup(self, trails):
        gdf = trails.copy()
        gdf["ut_url"] = "https://ut.no/turforslag/1113860"
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))

        maps.add_trails(fmap, gdf, name="UT.no", link_fields={"ut_url": "Open on ut.no"})

        assert "ut.no/turforslag/1113860" in fmap.get_root().render()

    def test_group_field_marks_every_part_of_one_route(self, trails):
        gdf = trails.copy()
        gdf["trip_id"] = [1113860, 116015]
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))

        group = maps.add_trails(fmap, gdf, name="UT.no", group_field="trip_id")

        classes = [child.options["className"] for child in group._children.values() if isinstance(child, folium.PolyLine)]
        # The second route is a MultiLineString: both its parts carry one class.
        assert classes == ["trail-group-1113860", "trail-group-116015", "trail-group-116015"]

    def test_group_value_is_reduced_to_a_css_token(self, trails):
        gdf = trails.copy()
        gdf["route"] = ["Tverådalen - Bønå", "x"]
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))

        group = maps.add_trails(fmap, gdf, name="UT.no", group_field="route")

        polyline = next(child for child in group._children.values() if isinstance(child, folium.PolyLine))
        assert polyline.options["className"].startswith("trail-group-Tver-dalen---B-n--")

    def test_names_that_flatten_alike_stay_distinct(self):
        """Without the digest both of these would become one selection."""
        assert maps._group_class("Bønå") != maps._group_class("Bønö")

    def test_plain_ids_are_not_given_a_digest(self):
        assert maps._group_class(1113860) == "trail-group-1113860"

    def test_a_whole_float_id_matches_the_integer(self):
        """One null in the column turns the whole thing into floats."""
        assert maps._group_class(1113860.0) == maps._group_class(1113860)

    def test_rows_without_a_group_value_get_no_class(self, trails):
        gdf = trails.copy()
        gdf["trip_id"] = [1113860, None]
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))

        group = maps.add_trails(fmap, gdf, name="UT.no", group_field="trip_id")

        classes = [child.options.get("className") for child in group._children.values() if isinstance(child, folium.PolyLine)]
        assert classes == ["trail-group-1113860", None, None]

    def test_layer_name_includes_feature_count(self, trails):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="Turrutebasen")
        assert group.layer_name == "Turrutebasen (2)"

    def test_reprojects_to_wgs84(self, trails):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        metric = trails.to_crs("EPSG:25833")
        group = maps.add_trails(fmap, metric, name="Turrutebasen")

        polyline = next(child for child in group._children.values() if isinstance(child, folium.PolyLine))
        lat, lon = polyline.locations[0]
        assert 65.0 < lat < 66.0
        assert 12.0 < lon < 14.0

    def test_dash_array_is_passed_through(self, trails):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="Ferries", dash_array="10,7")

        polyline = next(child for child in group._children.values() if isinstance(child, folium.PolyLine))
        assert polyline.options["dashArray"] == "10,7"

    def test_solid_by_default(self, trails):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="Trails")

        polyline = next(child for child in group._children.values() if isinstance(child, folium.PolyLine))
        assert polyline.options.get("dashArray") is None

    def test_skips_empty_geometries(self):
        gdf = gpd.GeoDataFrame({"geometry": [None, LineString([(12.8, 65.4), (12.81, 65.41)])]}, crs="EPSG:4326")
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, gdf, name="Trails")

        polylines = [child for child in group._children.values() if isinstance(child, folium.PolyLine)]
        assert len(polylines) == 1


class TestAddPoints:
    """Tests for add_points."""

    def test_adds_one_marker_per_point(self, shelters):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_points(fmap, shelters, name="Huts")

        markers = [child for child in group._children.values() if isinstance(child, folium.Marker)]
        assert len(markers) == 2

    def test_uses_label_field_as_tooltip(self, shelters):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_points(fmap, shelters, name="Huts")

        markers = [child for child in group._children.values() if isinstance(child, folium.Marker)]
        tooltips = [next((c for c in marker._children.values() if isinstance(c, folium.Tooltip)), None) for marker in markers]
        assert tooltips[0] is not None
        assert tooltips[0].text == "Stavassgården"
        # The second shelter has no name, so it gets no tooltip.
        assert tooltips[1] is None


class TestNamedPoints:
    """Tests for the table a waypoint takes its name from.

    The markers themselves cannot answer *what is at this position*: their names
    are one unlabelled entry in the popup values they carry, read positionally
    against the layer's labels, which is not a lookup.
    """

    @pytest.fixture
    def huts(self) -> gpd.GeoDataFrame:
        """A named hut and an unnamed one."""
        return gpd.GeoDataFrame(
            {"name": ["Lavasshytta", None], "geometry": [Point(12.98079, 65.77416), Point(12.9, 65.5)]},
            crs="EPSG:4326",
        )

    def test_a_layer_given_a_type_carries_what_it_draws(self, huts):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_points(fmap, huts, name="Huts", point_type="hut")

        assert getattr(group, maps.NAMED_POINTS_ATTR) == [{"name": "Lavasshytta", "type": "hut", "lat": 65.77416, "lon": 12.98079}]

    def test_a_layer_without_one_answers_nothing(self, huts):
        # Opt-in per layer: a place name drawn as text asserts no single
        # position — a valley has none — and a waypoint must not take one.
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_points(fmap, huts, name="Huts")

        assert getattr(group, maps.NAMED_POINTS_ATTR) == []

    def test_circles_carry_the_same_table_as_pins(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        farms = gpd.GeoDataFrame({"name": ["Strompdalen"], "geometry": [Point(13.05, 65.45)]}, crs="EPSG:4326")
        group = maps.add_labelled_points(fmap, farms, name="Farms", point_type="farm")

        assert getattr(group, maps.NAMED_POINTS_ATTR) == [{"name": "Strompdalen", "type": "farm", "lat": 65.45, "lon": 13.05}]

    def test_text_labels_never_carry_one(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        valleys = gpd.GeoDataFrame({"name": ["Lomsdalen"], "geometry": [Point(13.05, 65.45)]}, crs="EPSG:4326")
        group = maps.add_text_labels(fmap, valleys, name="Terrain names")

        assert not hasattr(group, maps.NAMED_POINTS_ATTR)


class TestAddLabelledPoints:
    """Tests for add_labelled_points."""

    @pytest.fixture
    def places(self) -> gpd.GeoDataFrame:
        """A town, a hamlet and an unnamed place."""
        return gpd.GeoDataFrame(
            {
                "name": ["Mosjøen", "Tverråga", None],
                "kind": ["town", "hamlet", "hamlet"],
                "geometry": [Point(13.19, 65.83), Point(13.17, 65.78), Point(12.9, 65.5)],
            },
            crs="EPSG:4326",
        )

    def test_skips_unlabelled_features(self, places):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_labelled_points(fmap, places, name="Places")

        circles = [child for child in group._children.values() if isinstance(child, folium.CircleMarker)]
        assert len(circles) == 2

    def test_always_label_makes_tooltip_permanent(self, places):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_labelled_points(fmap, places, name="Places", always_label=("town",))

        circles = [child for child in group._children.values() if isinstance(child, folium.CircleMarker)]
        tooltips = [next(c for c in circle._children.values() if isinstance(c, folium.Tooltip)) for circle in circles]
        assert tooltips[0].options["permanent"] is True
        assert tooltips[1].options["permanent"] is False

    def test_layer_name_includes_count(self, places):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_labelled_points(fmap, places, name="Places")
        assert group.layer_name == "Places (3)"


class TestAddTextLabels:
    """Tests for add_text_labels."""

    @pytest.fixture
    def names(self) -> gpd.GeoDataFrame:
        """Two named positions of one valley plus an unnamed row."""
        return gpd.GeoDataFrame(
            {
                "name": ["Eiterådalen", "Eiterådalen", None],
                "font_size": [12.0, 12.0, 10.0],
                "geometry": [Point(13.14, 65.67), Point(13.14, 65.60), Point(13.0, 65.5)],
            },
            crs="EPSG:4326",
        )

    def test_draws_one_label_per_position(self, names):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, names, name="Terrain names")

        markers = [child for child in group._children.values() if isinstance(child, folium.Marker)]
        # The repeated name is drawn at both of its positions; the unnamed row is skipped.
        assert len(markers) == 2

    def test_uses_a_div_icon_rather_than_a_marker_symbol(self, names):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, names, name="Terrain names")

        marker = next(child for child in group._children.values() if isinstance(child, folium.Marker))
        icon = next(child for child in marker._children.values() if isinstance(child, folium.DivIcon))
        # A zero-sized icon means no pin or circle is drawn, only the text.
        assert icon.options["icon_size"] == (0, 0)

    def test_renders_the_label_text(self, names):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, names, name="Terrain names")

        marker = next(child for child in group._children.values() if isinstance(child, folium.Marker))
        icon = next(child for child in marker._children.values() if isinstance(child, folium.DivIcon))
        assert "Eiterådalen" in icon.options["html"]

    def test_size_field_controls_the_font_size(self, names):
        gdf = names.copy()
        gdf.loc[0, "font_size"] = 17.5
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_text_labels(fmap, gdf, name="Terrain names", size_field="font_size")

        assert "font-size:17.5px" in fmap.get_root().render()

    def test_default_size_applies_without_a_size_field(self, names):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_text_labels(fmap, names, name="Terrain names", default_size=13)

        assert "font-size:13px" in fmap.get_root().render()


class TestAddBoundary:
    """Tests for add_boundary."""

    def test_adds_geojson_layer(self, park):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        layer = maps.add_boundary(fmap, park, name="Park")

        assert isinstance(layer, folium.GeoJson)
        assert layer.layer_name == "Park"


class TestAddRoutingGraph:
    """Tests for the routing graph the page carries but never draws."""

    def test_the_payload_and_its_header_reach_the_page(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_routing_graph(fmap, {"version": 1, "edges": 3}, "H4sIAAAAAAAA")

        html = fmap.get_root().render()
        assert '"edges": 3' in html
        assert '"H4sIAAAAAAAA"' in html
        assert "window.trailsGraph" in html

    def test_it_draws_nothing_and_joins_no_layer_control(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_routing_graph(fmap, {"version": 1, "edges": 0}, "")
        assert not [child for child in fmap._children.values() if isinstance(child, folium.GeoJson | folium.FeatureGroup)]

    def test_the_decoder_fetches_nothing(self):
        """A script pulled from a CDN does not load on a file:// page: it fails
        silently, the way the OpenStreetMap tiles once did."""
        bounds = (12.4, 65.3, 13.4, 65.7)
        plain = maps.create_map(bounds=bounds).get_root().render()

        fmap = maps.create_map(bounds=bounds)
        maps.add_routing_graph(fmap, {"version": 1, "edges": 0}, "")
        with_graph = fmap.get_root().render()

        assert with_graph.count("://") == plain.count("://")


class TestChainFigures:
    """Tests for the figures a line carries beside the layer it is drawn in."""

    @pytest.fixture
    def measured(self) -> gpd.GeoDataFrame:
        """Two chains, one of them with nothing read along it."""
        return gpd.GeoDataFrame(
            {
                "chain_id": ["ut-no-1-2-3", "ferries-4-5-6"],
                "ascent": [996.4, float("nan")],
                "descent": [850.2, float("nan")],
                "bearing_deg": [47.3, 12.0],
                "geometry": [
                    LineString([(12.8, 65.4), (12.81, 65.41)]),
                    LineString([(12.9, 65.5), (12.91, 65.51)]),
                ],
            },
            crs="EPSG:4326",
        )

    def fields(self) -> dict[str, str]:
        """The columns to carry, and the keys they travel under."""
        return {"ascent": "ascent", "descent": "descent", "bearing_deg": "bearing"}

    def test_figures_travel_beside_the_layer_keyed_by_the_class(self, measured):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, measured, name="Chains", group_field="chain_id", figure_fields=self.fields())

        figures = getattr(group, maps.CHAIN_FIGURES_ATTR)
        assert figures["trail-group-ut-no-1-2-3"]["ascent"] == pytest.approx(996.4)
        assert figures["trail-group-ut-no-1-2-3"]["bearing"] == pytest.approx(47.3)

    def test_a_figure_is_rounded_rather_than_carried_at_float_precision(self, measured):
        """17.339999999999996 is eleven thousand times over, for digits a tenth
        of a metre already exceeds."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        rough = measured.assign(ascent=[17.339999999999996, float("nan")])
        group = maps.add_trails(fmap, rough, name="Chains", group_field="chain_id", figure_fields=self.fields())

        assert getattr(group, maps.CHAIN_FIGURES_ATTR)["trail-group-ut-no-1-2-3"]["ascent"] == 17.3

    def test_a_label_travels_as_itself_rather_than_as_a_number(self, measured):
        """The compass point is a string and is carried, not re-derived."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        labelled = measured.assign(compass=["NE", None])
        group = maps.add_trails(fmap, labelled, name="Chains", group_field="chain_id", figure_fields={**self.fields(), "compass": "point"})

        figures = getattr(group, maps.CHAIN_FIGURES_ATTR)
        assert figures["trail-group-ut-no-1-2-3"]["point"] == "NE"
        assert figures["trail-group-ferries-4-5-6"]["point"] is None

    def test_each_entry_names_the_chain_it_is_about(self, measured):
        """A class is not an id: _group_class reshapes anything that is not a
        CSS token, so what the figures describe travels as a value."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, measured, name="Chains", group_field="chain_id", figure_fields=self.fields())

        figures = getattr(group, maps.CHAIN_FIGURES_ATTR)
        assert figures["trail-group-ut-no-1-2-3"][maps.FIGURE_ID_KEY] == "ut-no-1-2-3"

    def test_a_missing_figure_travels_as_null_rather_than_zero(self, measured):
        """A crossing has no ground under it. Zero would be a claim about it."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, measured, name="Chains", group_field="chain_id", figure_fields=self.fields())

        assert getattr(group, maps.CHAIN_FIGURES_ATTR)["trail-group-ferries-4-5-6"]["ascent"] is None

    def test_without_figure_fields_nothing_is_recorded(self, measured):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, measured, name="Chains", group_field="chain_id")

        assert getattr(group, maps.CHAIN_FIGURES_ATTR) == {}


class TestProfilePanel:
    """Tests for the profile panel."""

    def drawn(self) -> tuple[folium.Map, folium.FeatureGroup]:
        """A map with one measured chain drawn on it."""
        gdf = gpd.GeoDataFrame(
            {
                "chain_id": ["ut-no-1-2-3"],
                "ascent": [996.4],
                "geometry": [LineString([(12.8, 65.4), (12.81, 65.41)])],
            },
            crs="EPSG:4326",
        )
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        return fmap, maps.add_trails(fmap, gdf, name="Chains", group_field="chain_id", figure_fields={"ascent": "ascent"})

    @pytest.fixture
    def group(self) -> tuple[folium.Map, folium.FeatureGroup]:
        """The same map, as a fixture."""
        return self.drawn()

    def test_what_the_curve_was_drawn_from_stands_under_it(self, group):
        """The colour key, the point count, the licences and the ground note
        were hidden outright on any page with a chrome, because a full-screen
        sheet held them. There is no sheet: they are back, at the foot of the
        page the curve is on, where scrolling reaches them and the drawing is
        not asked to give up a line for them."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "meta.style.display = '';" in html
        # The drawing first and what it was drawn from under it. A licence line
        # over a curve is a licence line in the way.
        assert html.index("body.appendChild(chart);") < html.index("body.appendChild(meta);")

    def test_the_i_is_a_page_and_not_a_sheet(self, group):
        """It used to open the chrome's full-screen sheet, which answered *what
        was this drawn from* by covering the drawing, the map and the line that
        had been tapped to get there. The same content is the second page of the
        same panel, one swipe from the curve, and the row underneath says which
        of the two is showing."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "function detailFigures(withFigures) {" in html
        assert "window.trailsChrome.detail(named, box, 'profile');" not in html
        # Read off the element that shows it rather than composed again: one
        # sentence, in two places, from one derivation.
        assert "said.textContent = part[0];" in html
        assert "kind: 'details'" in html

    def test_the_heading_shows_three_of_the_list_the_sheet_shows_all_of(self, group):
        """Six lines of figures over a drawing that got four. The heading takes
        how far, how much climb and how steep at worst; the sheet takes the same
        list entire, in the same order — a second list for the second rendering
        is how a page comes to tell two stories about one route."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "saidText = lines.slice(0, 3).join(" in html
        assert "figures.forEach(function (line, at) {" in html

    def test_the_row_says_what_it_is_over_how_far_it_goes(self, group):
        """Two lines of 44 px, which is what plan mode's bar has been measuring
        with all along: the name in bold and the figures under it, each on one
        line and each ending in an ellipsis rather than wrapping. The figures
        that do not fit are on the page the name opens."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "name.className = 'trails-profile-name';" in html
        assert "summary.className = 'trails-profile-figures';" in html
        assert "white-space:nowrap;overflow:hidden;text-overflow:ellipsis'" in html
        # The two lines are one sentence about one thing, so they are written in
        # one call and can never be about two.
        assert "name.textContent = planning()" in html

    def test_the_mark_and_the_page_it_names_are_the_same_page(self, group):
        """The pages were appended once, in the order they are written in, and
        the marks are drawn in the order the pages come — two lists of the same
        three things, agreeing until the day one of them was conditional. With a
        route being planned the mark for *points and stages* slid the box to the
        details of whatever line had been chosen before it, and the *i* showed
        the points."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "if (order !== laidPages) {" in html
        assert "wanted.forEach(function (node) { track.appendChild(node); });" in html
        # Only when it changes: appending a node moves it, and a moved node
        # loses where it was scrolled to.
        assert "var laidPages = '';" in html

    def test_the_handle_is_the_strip_and_not_the_bar(self, group):
        """Seven pixels of bar is what a mouse needs. A finger that missed by
        four pixels scrolled the page underneath instead of resizing the panel —
        reported as a height that could hardly be set at all. The strip around
        the bar, dots included, is what can be pressed, and `touch-action: none`
        is what stops the browser reading the drag as a scroll before the handler
        sees it."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "hold.className = 'trails-profile-hold';" in html
        assert "touch-action:none" in html
        assert "hold.addEventListener('touchstart', function (event) {" in html
        assert "hold.addEventListener('mousedown', function (event) {" in html

    def test_a_finger_is_given_more_of_the_handle_than_a_mouse(self):
        """How big a target has to be is a question about hands, and the rules
        that answer it live with the chrome — one place that has to win over
        every panel's inline styles."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert ".trails-profile-hold { min-height: 16px; }" in html
        assert ".trails-coarse .trails-profile-hold { min-height: 30px; padding-top: 8px; }" in html

    def test_a_popup_belongs_to_the_thing_it_came_off(self, group):
        """Cleared when the selection goes and not when it changes: a line's own
        popup arrives *before* the click that selects the line — Leaflet fires
        the popup's handler first — so clearing on every change would throw away
        the page that had just arrived. Driven, plan mode showed the table of
        whatever line had been chosen before it, on the page where the points
        belong."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "if (given === null) { if (!suspended) { detailHtml = null; } choices = []; }" in html

    def test_a_place_takes_the_panel_over_whole(self, group):
        """Tapping a place while a line was chosen left the line's curve standing
        with the place's table beside it: two things in one panel, and the row
        naming the second while the first was drawn. A place is a selection of
        its own — no curve, no colour key, no file, and nothing under its name
        telling the reader to click a line to see a profile."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "if (isPoint && !suspended) {" in html
        assert "if (window.trailsHighlight) { window.trailsHighlight.clear(); }" in html
        # Nothing under the name: it said *click a line to see its profile*,
        # under the name of the thing the reader had just chosen.
        assert "if (selected.detail) { say(''); return; }" in html
        # And nothing below the table that belongs to a drawing it has not got.
        assert "if (!(selected && selected.shape)) { return box; }" in html

    def test_a_press_on_what_it_says_opens_it_or_puts_it_away(self, group):
        """It used to walk to the page it names first and fold only from there,
        so a reader who wanted the map back got the table they had not asked for
        and had to press again. What is open goes; what is shut comes up on the
        page this line has been pointing at all along — *tap for the points*
        while a route is being planned, the details otherwise."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "if (pagesOpen) { showPages(false); return; }" in html
        assert "var wanted = planning() ? 'list' : 'details';" in html

    def test_a_reading_belongs_to_the_finger_that_made_it(self, group):
        """A mouse leaving the chart has always taken the rule, the dot and the
        reading with it; a finger lifted left all three standing, so the row went
        on saying *612 m at 8.42 km* over a page about something else. Turning
        the page is leaving the curve for the same reason."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        lifted = html.split("function fingersUp(event) {")[1].split("}")[0:6]
        assert any("forget();" in part for part in lifted)
        assert "// Turning the page is leaving the curve, and a reading of a" in html

    def test_swiping_is_taken_everywhere_but_across_the_drawing(self, group):
        """One finger on the curve reads it — distance, height, gradient — and
        that gesture is both older and worth more than this one: it is the only
        way to ask a phone what is under a place. So the swipe is taken on the
        row at the foot and on the pages that are not the curve, and the marks
        are what move a reader off the profile."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "swipeFrom(header);" in html
        assert "swipeFrom(detailBox);" in html
        assert "swipeFrom(pointsPage);" in html
        assert "swipeFrom(chart)" not in html

    def test_the_archive_is_offered_only_where_there_are_stages(self, group):
        """A tour cut into stages can be had as one file or as an archive of
        them; a tour that is one stage would be offered the same file twice under
        two names. The plan panel's own save has always said so, and it is said
        once here rather than twice."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "stagesDownload.style.display = cut > 1 ? 'block' : 'none';" in html
        clicking = html.split("download.addEventListener('click', function (event) {")[1].split("\n                });")[0]
        assert "if (selected && selected.composed) {" in clicking
        assert "if (cut > 1)" not in clicking
        assert "saveNow();" in clicking
        assert "saveEntry('Whole tour (GPX)'," in html
        assert "saveEntry('All stages (zip)'," in html
        # Plan mode's own writer, asked for by name: a second writer would
        # eventually disagree with the first about a route it was handed the
        # same way.
        assert "window.trailsPlan.saveStages()" in html

    def test_the_file_is_a_mark_beside_the_other_two(self, group):
        """The plan control gave up its words a fortnight ago and this was the
        last panel speaking in them. It is addressed by a class rather than by
        what it says: a probe aiming at a control's words has an expiry date,
        which this suite has already learned twice about aiming by position."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "download.className = 'trails-profile-gpx';" in html
        assert "download.textContent = 'Download GPX';" not in html
        # The button and its menu travel together, so the menu can be placed
        # against the button rather than against the row.
        assert "saveWrap.appendChild(download);" in html
        assert "tools.appendChild(saveWrap);" in html
        assert "download.addEventListener('click', function (event) {" in html
        # And the chart is named, because the mark put a second `<svg>` in the
        # panel ahead of it: `panel svg` had quietly begun meaning a 17 px icon.
        assert "chart.setAttribute('class', 'trails-profile-chart');" in html

    def test_a_second_press_on_the_lit_mark_folds_the_pages_away(self, group):
        """Which is what a mark that opened something is expected to do — and
        the only way to a whole map that does not also give up the selection.
        The row stays; it is 44 px and it is what says something is chosen."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "if (lit) { showPages(false); return; }" in html
        # **And the answer is kept where every other switch for it is kept.** A
        # fold that set only this closed itself again the moment anything
        # repainted: while planning on a narrow screen the chrome's default is
        # *shut*, so it asked for shut back half a frame after a reader had asked
        # for open. Driven, the list page opened and was gone before it could be
        # read.
        assert "window.trailsChrome.profile(want);" in html
        assert "if (pagesOpen === want) { return; }" in html

    def test_neither_hint_is_drawn_and_nothing_stands_in_for_them(self, group):
        """Reported from a phone: the hint anchored at `box.left` and the reading
        anchored at `box.right` are written to the same `box.top + 8`, and on
        390 px the reading lay wholly inside the hint. Taken out on a wide screen
        too, where the two never meet and it was still prose inside a drawing.

        Nothing replaces them, in the sheet or anywhere: a gesture that has to be
        described is not discovered by describing it. What stays is the window —
        *12.34 km of 42.44* is state and not instruction."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "Touch the curve to read it" not in html
        assert "Drag a stretch to look into it" not in html
        assert "more detail than this" not in html
        assert "' km of '" in html

    def test_the_reading_goes_into_the_heading_and_not_into_the_plot(self, group):
        """That is what makes the collision impossible rather than merely fixed:
        there is no second place for a reading to be drawn. It takes the
        crosshair's own colour, off the same token the crosshair reads."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "crosshair = {rule: rule, dot: dot, plot: plot" in html
        assert "reading: reading" not in html
        assert "readingNow = (shape.distance[at] / 1000).toFixed(2)" in html
        assert "summary.style.color = readingNow ? 'var(--trails-accent)' : 'var(--trails-ink-2)';" in html
        # And which of the two it is saying is a fact rather than a colour: a
        # probe comparing a computed rgb() against the token's hex never matches.
        assert "summary.classList.toggle('trails-profile-reading', !!readingNow);" in html

    def test_the_page_takes_the_ground_then_the_sources_then_the_key(self, group):
        """The order is an argument. What a walk covers is about this route; who
        may be asked about it is about the file; and the colour key is the only
        thing on the page that says nothing about this route at all — it
        explains a drawing rule that holds for every walk there will ever be. So
        it goes last, and it is built from the same two functions the panel's own
        key uses, because a second wording of *gentle under 15 %* is the
        two-panel mistake in miniature.

        **And the figures above them are drawn only where nothing else says
        them.** A line's own popup carries the length, the climb, the steepest
        and the high point; the list repeated all four and added two, so the two
        go into that table and the list is left to a planned route, which has no
        popup at all."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "var figures = withFigures" in html
        assert "var figures = detailFigures(!table);" in html
        # The one the table is missing, in the table's own hand. The low point
        # is not one of them: it is written beside the high one, where the rest
        # of the figures are written.
        assert "addRow(table, 'Points read'," in html
        assert "addRow(table, 'Low point'" not in html
        assert "[[noted.textContent, 'The ground this covers']," in html
        assert "[licensed.textContent, 'Sources and licences']].forEach(function (part) {" in html
        assert "coloured.textContent = 'How the curve is coloured';" in html
        assert "function bandLabel(at) {" in html
        assert "row.appendChild(bandSwatch(band.width, band.colour, false));" in html

    def test_the_way_out_takes_the_selection_with_it(self, group):
        """It used to put the panel away and leave the line selected underneath,
        so a reader who wanted the map back pressed this and then had to find the
        line again to undo its highlight. Folding is what the lit mark does; this
        is *done with this thing* — and while a route is being planned, the thing
        being finished is the planning."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "hide.className = 'trails-profile-hide';" in html
        assert "if (planNow && window.trailsPlan) { window.trailsPlan.toggle(false); return; }" in html
        assert "if (window.trailsHighlight) { window.trailsHighlight.clear(); }" in html
        # Only where there is something to be done with.
        assert "hide.style.display = (open || planning()) ? 'flex' : 'none';" in html

    def test_the_gradient_bands_and_their_rule_reach_the_page(self, group):
        """The bands are a measurement, not a taste: 15 % sits above the worst
        gradient the height model reads on ground that is level."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        for lower, label, colour, _ in maps.GRADIENT_BANDS:
            assert label in html
            assert colour in html
            assert str(lower) in html
        assert str(maps.GRADIENT_WINDOW_M) in html
        assert str(maps.GRADIENT_MIN_RUN_M) in html

    def test_the_profile_height_is_a_reader_s_to_drag(self, group):
        """And the drag is coalesced to one draw a frame.

        A redraw per mouse move is the mistake that froze this map twice, and a
        chain of eight thousand samples is four hundred separate strokes.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "cursor:ns-resize" in html
        assert "function stretchTo(pixels)" in html
        assert "awaiting = false;" in html
        # **The box before the drawing**, because a drag that started on the
        # list is asking for a taller list and would otherwise wait for the
        # reader to turn back to the curve.
        assert "                        sizePages();\n                        render();" in html

    def test_the_profile_height_is_bounded_at_both_ends(self, group):
        """Room for a curve at all, and never so tall that the panel is the map.

        Measured against the height the panel was **laid out** with rather than
        the one it was last asked for. A redraw is coalesced to the next frame,
        so two moves inside one frame otherwise measure a fresh chart against a
        stale box: the second reads an overhead of minus 620, a ceiling of 1,440,
        and hands out a panel taller than the map. Firefox reports clientY as -86
        the moment the pointer leaves the foot of the window, so a drag that runs
        off the bottom delivers three such moves at once.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "var least = 60;" in html
        assert "mapRoom().y - (box.offsetHeight - laidOut) - 80" in html
        assert "laidOut = chartHeight;" in html

    def test_the_profile_height_does_not_move_while_the_panel_is_folded(self, group):
        """Folded, the box is one line with no chart in it, so the overhead
        measures as minus 170 and the ceiling comes out taller than the map
        instead of shorter. A click on the map folds the panel, and a click can
        land in the middle of a drag: measured, that reopened it at 705 px.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "Folded, the box is one line with no chart in it" in html
        assert "if (!open && stretching) { stretching = null;" in html

    def test_the_height_is_held_to_a_ceiling_that_moves(self, group):
        """It was clamped only where it was asked for, so a window made shorter
        afterwards left the panel taller than the map: measured, a 725 px panel
        in a 620 px window put its own grip at -127, off the top of the map and
        out of a reader's reach for good.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "if (open) { stretchTo(chartHeight); }" in html

    def test_the_wheel_is_the_map_s_except_over_a_curve_that_can_use_it(self, group):
        """A panel that swallows a wheel and does nothing with it reads as the
        map having frozen, which is why this panel has only ever taken clicks.
        So the chart takes the wheel exactly where there is detail under the
        drawing to reach: 126 chains of 11,264, and every route worth planning.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "chart.addEventListener('wheel'" in html
        assert "if (!crosshair || !(crosshair.closest > 1.001)) { return; }" in html
        assert "}, {passive: false});" in html

    def test_the_zoom_stops_at_one_reading_per_pixel(self, group):
        """The ceiling is the data's rather than a taste. Past it the panel
        magnifies the straight lines drawn between samples, which claims a
        resolution nothing supports: 7.1x on the 42 km chain, 1 on most.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "var spacing = readable > 1 ? shape.total / (readable - 1) : shape.total;" in html
        assert "var closest = spacing > 0 ? Math.max(1, base / spacing) : 1;" in html
        assert "view.zoom = Math.min(closest, Math.max(1, view.zoom));" in html

    def test_a_zoomed_window_is_drawn_at_the_same_true_scale(self, group):
        """One metres-per-pixel for both axes, whatever the window: zooming
        changes how much of the chain is on the panel and never its angle.

        The heights may be lifted off that scale now — a long route is a ribbon
        at the ground's own — but the lift is one factor over the whole drawing
        and does not move with the zoom either, so what this is about is
        unchanged: the shape of a window is the shape of the ground in it."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "var metresPerPixel = base / view.zoom;" in html
        assert "return box.left + (value - from) / metresPerPixel;" in html
        assert "var metresPerY = metresPerPixel / liftBy;" in html
        assert "return middleY - (value - view.centre) / metresPerY;" in html

    def test_the_heights_can_be_lifted_off_the_ground_scale(self, group):
        """Reported: on a long tour there is nothing to see. There is not — 44 km
        across a phone's panel is 119 metres to the pixel, so 691 m of relief
        draws as six pixels: a straight line with a colour on it.

        Lifted, the band fills the box. Never more than ten times, because a
        20 m rise blown up to fill a panel is a lie a picture tells better than
        words can correct it, and never less than once, so a steep chain that
        already fills the box is drawn exactly as it was."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "var LIFT_MAX = 10;" in html
        assert "var LIFT_FILL = 0.86;" in html
        assert "liftBy = Math.min(LIFT_MAX, Math.max(1, tall * metresPerPixel * LIFT_FILL / relief));" in html
        # Everything the height axis is measured in follows the lift, and
        # nothing the distance axis is.
        assert "var carries = tall * metresPerY;" in html
        assert "var spare = Math.min(18, tall / 4) * metresPerY;" in html
        assert "return box.left + (value - from) / metresPerPixel;" in html

    def test_the_lift_is_said_where_the_drawing_is(self, group):
        """A picture at two possible scales has to say which one it is at, and
        the place to say it is over the picture: in the menu it would be a
        setting nobody connects to the shape they are looking at.

        The factor is what the mark says, because the lift is worked out from
        the route and the panel's height — it is not a setting with a number a
        reader chose."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "lift.className = 'trails-profile-lift';" in html
        assert "lift.textContent = lifted ? factor : '1:1';" in html
        assert "lift.style.left = '2px';" in html
        # Over the axis and not over the curve, opposite the way back, and only
        # where there is a drawing to say it about.
        assert "whole.style.right = '2px';" in html
        assert "lift.style.display = drawing ? '' : 'none';" in html

    def test_the_scale_a_reader_chose_is_kept(self, group):
        """It is a decision about reading rather than about this route: somebody
        who wants the ground's own scale wants it for the next line they tap as
        well. Lifted is the default, which is the answer to the report — and the
        key is only written for the answer that is not the default, so a browser
        that keeps nothing still opens on the readable one."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "var SCALE_KEY = 'trails:profile-scale';" in html
        assert "var lifted = keptScale() !== 'true';" in html
        assert "if (lifted) { window.localStorage.removeItem(SCALE_KEY); }" in html
        assert "else { window.localStorage.setItem(SCALE_KEY, 'true'); }" in html
        # And a browser that refuses to keep anything still draws.
        assert "catch (blocked) { /* a browser that keeps nothing still draws */ }" in html

    def test_what_is_steep_is_still_steep_at_either_scale(self, group):
        """What is given up by lifting is that the drawn angle is the angle on
        the ground. What is not given up is the answer to *is this steep*: the
        colours are read off the ground rather than off the picture, and the
        crosshair says a gradient rather than an angle. That is what makes the
        lift honest rather than merely labelled."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "var slope = gradients(shape);" in html
        assert "var strokes = drawCurve(shape, plot, x, y, slope, from, to);" in html
        # And the panel says which scale it is at, for a check and for anything
        # else that has to know.
        assert "return {mode: lifted ? 'readable' : 'true', lift: liftNow};" in html

    def test_a_window_steeper_than_the_panel_is_clipped(self, group):
        """The panel's own shape is a gradient, 14.6 %, and it does not move with
        the zoom. Unclipped, a steeper window runs over the height labels and out
        of the panel into the map.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "createElementNS(SVG, 'clipPath')" in html
        assert "group.setAttribute('clip-path', 'url(#' + id + ')');" in html
        # And the waypoint marks get a frame of their own, wider by their own
        # radius: every route has a point at nought and one at its end, and the
        # curve's frame would draw both as half discs.
        # The stations are not framed: they stand under the axis, outside
        # the plot the curve is clipped to.
        assert "var marks = framed(" not in html
        assert "marks.setAttribute('class', 'trails-profile-stations');" in html

    def test_the_profile_marks_the_points_a_route_was_planned_with(self, group):
        """ "Where is the climb" is half an answer until the profile says which
        two points it lies between. Drawn as the pin is drawn — a pale disc, a
        dark ring, the same number — because they are the same point seen from
        above and from the side.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "(shape.stations || []).forEach(function (metres, index) {" in html
        assert "var sample = nearest(shape.distance, station.metres);" in html
        # A point on ground nothing was read along still happened, and it rests
        # on the floor of the box: at the ceiling it read as a summit, which a
        # waypoint set on the water is the one thing it must not.
        assert "var level = read ? y(value) : box.bottom;" in html
        assert "var ink = read ? STATION : STATION_UNREAD;" in html

    def test_the_heading_says_how_steep_the_ground_gets(self, group):
        """Absolute, over the 25 m window the curve is banded by: a signed
        maximum would call this park's steepest chain flat, since it climbs 9 m
        and drops 816.

        A chain's figure is the build's, the same number its popup carries. The
        page's own series would answer 80.87 where the build says 81 -- they
        differ by the arc length Python spaces its samples at against the chords
        this page sums -- and one page showing both would be showing two answers
        about one chain. A composed route has no build figure and no popup, so
        there the page computes it.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "function steepestOf(shape, freeOnly) {" in html
        assert "var slope = gradients(shape), worst = NaN;" in html
        # A route works it out; a chain is handed it.
        assert "var worst = steepestOf(shape);" in html
        assert "told.push('steepest ' + Math.round(worst) + ' %');" in html
        assert "var steepest = figure.steepest;" in html

    def test_a_window_belongs_to_the_chain_it_was_opened_on(self, group):
        """Carried over, it would open the panel somewhere in the middle of
        whatever the reader just clicked, at a scale chosen for something else.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "view.zoom = 1; view.at = 0; view.centre = null;" in html

    def test_the_crosshair_marks_its_position_on_the_map(self, group):
        """The hill under the pointer and the hill on the map are the same hill.

        In the direction arrow's pane, for the arrow's reason: the map's path
        count is what phase 3 was accepted against and nothing this panel draws
        may join it.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "standing = positionAt(shape, shape.distance[at]);" in html
        assert "function placeHere() {" in html
        assert "L.DomUtil.setPosition(here, map.latLngToLayerPoint(standing));" in html
        assert "map.on('zoomend viewreset moveend resize', placeHere);" in html

    def test_the_mark_is_drawn_above_the_route_it_reports_on(self, group):
        """It shared the direction arrow's pane at 450 and plan mode's route
        pane is 460, so the one mark whose whole job is to say where on this
        route you are was drawn underneath the route."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "map.createPane('trailsProfileHere')" in html
        assert "over.style.zIndex = 470;" in html
        assert "over.appendChild(here);" in html
        # And it takes no clicks, so plan mode's dispatcher never sees it.
        assert "over.style.pointerEvents = 'none';" in html

    def test_a_position_is_looked_up_on_the_axis_that_has_one(self, group):
        """A series has two axes and they are not the same length: heights every
        5 m, and the line through the vertices somebody surveyed. Only a distance
        is shared between them, so a sample's index cannot index a vertex.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "function positionAt(shape, metres) {" in html
        assert "if (shape.along[middle] < metres) { low = middle + 1; } else { high = middle; }" in html
        # And the arrow asks the same walk rather than keeping one of its own.
        assert "return positionAt(shape, shape.total / 2);" in html

    def test_the_mark_does_not_outlive_the_reading_that_put_it_there(self, group):
        """A dot left on the map after the pointer has gone claims a position
        nobody is pointing at. It goes when the pointer leaves the chart, when
        the curve is redrawn under it, and when a drag starts.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "function forget() {" in html
        assert "chart.addEventListener('mouseleave', forget);" in html
        assert "if (standing) { standing = null; placeHere(); }" in html

    def test_the_panel_says_which_part_of_the_chain_it_is_showing(self, group):
        """A window is a thing to be read rather than screenshotted, the same as
        the series and the figures above it.
        """
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "view: function () {" in html
        assert "metresPerPixel: crosshair ? crosshair.mpp : null," in html
        assert "closest: crosshair ? crosshair.closest : null" in html

    def test_the_lowest_band_clears_what_the_model_reads_on_level_ground(self):
        """Measured: level chains read a median of 1.0 % over a 25 m window and
        never more than 9.2 %. A boundary under that would colour the data."""
        assert maps.GRADIENT_BANDS[0][0] == 0.0
        assert maps.GRADIENT_BANDS[1][0] > 9.2

    def test_the_gradient_is_never_read_between_neighbouring_samples(self):
        """Samples are laid per edge, so two of them can be a third of a metre
        apart, where a decimetre of model noise reads as a cliff — 2,754 % at
        the worst. The window and its floor are what stop that."""
        assert maps.GRADIENT_MIN_RUN_M >= 10.0
        assert maps.GRADIENT_WINDOW_M >= 2 * maps.GRADIENT_MIN_RUN_M

    def test_the_crosshair_is_not_the_colour_of_the_steepest_band(self):
        """A red rule over a red stretch of curve reads as part of the data."""
        fmap, layer = self.drawn()
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert f"CROSS = '{maps.GRADIENT_BANDS[-1][2]}'" not in html

    def test_the_page_names_no_compass_point_of_its_own(self, group):
        """A rounded label is a threshold, so it is decided once, in Python, and
        carried. A second rule in the page would name a different direction from
        the popup on any chain lying near a boundary between two points."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "figure.point" in html
        for derived in ("octant(", "OCTANTS", "/ 45 + 0.5"):
            assert derived not in html, f"the page derives the compass point itself: {derived}"

    def test_the_figures_reach_the_page(self, group):
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "trail-group-ut-no-1-2-3" in html
        assert "996.4" in html

    def test_the_field_names_travel_once_and_the_page_puts_them_back(self, group):
        """Every figure has the same twelve fields, so written as objects the
        table is twelve field names per chain -- 1.26 MB of the 2.84 the built
        page carried. Everything that reads a figure still reads it by name."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert '"fields": ["id", "ascent"' in html
        assert '"trail-group-ut-no-1-2-3": ["ut-no-1-2-3", 996.4' in html
        assert "for (i = 0; i < fields.length; i++) { figure[fields[i]] = values[i]; }" in html

    def test_it_draws_nothing_on_the_map(self, group):
        """The arrow belongs in a container of its own: anything drawn into the
        overlay pane is counted among the map's paths for ever after."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])
        assert not [child for child in fmap._children.values() if isinstance(child, folium.GeoJson | folium.Marker)]
        html = fmap.get_root().render()
        assert "createPane" in html
        assert "L.polyline" not in html.split("var figures")[-1]

    def test_it_fetches_nothing(self, group):
        """A charting library from a CDN does not load on a file:// page: it
        fails silently, the way the OpenStreetMap tiles once did.

        Every URL the panel does carry is a **namespace**, and a namespace names
        a language rather than a place: the SVG one, which is what
        createElementNS takes, and GPX's own, which the panel writes into the
        file it produces. Nothing resolves either, and the schema location
        beside the second is a hint to a validator that will never see this
        page."""
        namespaces = ("http://www.w3.org/2000/svg", "http://www.topografix.com/GPX/1/1", "http://www.w3.org/2001/XMLSchema-instance")

        def addresses(html: str) -> int:
            """How many places a page names, once the namespaces are taken out.

            Both sides go through this and not just the panel's. The page
            carries Leaflet inline, whose own comments name addresses; and the
            marker outlines carry the SVG namespace, which stands in every page
            whether a panel was added or not. Subtracting on one side only
            compares two different questions.
            """
            bare_text = ours(html)
            for namespace in namespaces:
                bare_text = bare_text.replace(namespace, "")
            return bare_text.count("://")

        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])
        with_panel = addresses(fmap.get_root().render())

        bare, _ = self.drawn()
        assert with_panel == addresses(bare.get_root().render())

    def test_the_wheel_still_reaches_the_map(self, group):
        """disableClickPropagation, and deliberately not the scroll one: a panel
        that swallows the wheel reads as a map that has frozen."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = ours(fmap.get_root().render())
        assert "disableClickPropagation" in html
        assert "disableScrollPropagation" not in html

    def exported(self, **changed: object) -> dict[str, object]:
        """What the page has to be handed before it can write a GPX file.

        Args:
            **changed: Settings to override or, with a value of None, to drop

        Returns:
            A complete set, minus anything set to None
        """
        settings: dict[str, object] = {
            "credits": {"UT.no": [{"name": "UT.no", "licence": "CC BY-NC 4.0", "note": "non-commercial", "version": "downloaded 2026-08-12"}]},
            "heights": [{"name": "Høydedata DTM1", "licence": "CC BY 4.0", "note": ""}],
            "fields": [["id", "chain"], ["ascent", "ascent"]],
            "creditFields": ["name", "licence", "version"],
            "gapM": 5.0,
            "decimals": 1,
            "elevationDecimals": 2,
            "coordinateDecimals": 7,
            "namespace": "https://github.com/ueisele/trails/gpx/1",
            "prefix": "trails",
            "creator": "trails-analysis",
            "description": "One chain",
            "ascentMethod": "DTM1, sampled every 5 m, gains under 5 m ignored",
            "identitySeparator": " / ",
            "filePrefix": "lomsdal-visten",
            "sourceLength": "metres",
            "route": {
                "name": "Planned route in Lomsdal-Visten",
                "description": "A route planned on the Lomsdal-Visten map",
                "fileStem": "route",
                "kindField": "kind",
                "kind": "route",
                "fields": [["ascent", "ascent"], ["walked", "walked"], ["unknown", "unknown"]],
                "legs": "legs",
                "leg": "leg",
                "part": "part",
                "partKind": "kind",
                "partLength": "m",
                "areas": "protected",
                "area": "area",
                "areaId": "id",
                "areaName": "name",
                "areaForm": "form",
                "areaLength": "m",
            },
            "waypoint": {
                "name": "Point",
                "origin": "origin",
                "set": "set",
                "generated": "generated",
                "enters": "Enters",
                "leaves": "Leaves",
                "area": "area",
                "stage": "stage",
            },
            "protected": [{"name": "Naturvernområder", "licence": "NLOD", "note": ""}],
        }
        settings.update(changed)
        return {name: value for name, value in settings.items() if value is not None}

    def test_the_licences_and_the_versions_reach_the_page(self, group):
        """The browser writes the exported file, so everything in it has to be
        in the page. Measured before this: CC BY 4.0, ODbL and CC BY-NC appeared
        **zero times** in the built page, and so did any source version — they
        existed only in what the build printed to its console."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer], export=self.exported())

        html = fmap.get_root().render()
        assert "CC BY-NC 4.0" in html
        assert "downloaded 2026-08-12" in html
        assert "DTM1, sampled every 5 m, gains under 5 m ignored" in html

    def test_a_panel_given_no_export_offers_no_download(self, group):
        """Phase 4's panel, unchanged: it draws and says nothing about files."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "var EXPORT = null" in html
        # The words about licences that remain are the ones explaining why no
        # <copyright> is written; none of them is a licence the page carries.
        assert "CC BY-NC 4.0" not in html
        assert "Høydedata" not in html

    @pytest.mark.parametrize("export_enabled,has_garmin", [(False, False), (True, False), (True, True)])
    def test_render_handles_an_absent_export_or_garmin_entry(self, group, export_enabled, has_garmin):
        """Execute the emitted offer renderer with the optional menu entry absent.

        No export must leave the original hidden controls untouched. An export
        with no entry also exercises both defensive writes; a present entry
        must still follow the ordinary button's refusal state.
        """
        node = shutil.which("node")
        if node is None:
            pytest.skip("Node is needed to execute the profile render test")
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer], export=self.exported() if export_enabled else None)
        html = fmap.get_root().render()
        settings = re.search(r"var EXPORT = [^\n]+;", html)
        assert settings is not None
        source = settings[0] + "\n" + export_javascript(html, "offered")
        source += "\nvar garminDownload = " + ("{disabled: false}" if has_garmin else "undefined") + ";"
        source += r"""
            var offer = {style: {display: 'none'}}, download = {style: {display: 'none'}, disabled: false};
            var noted = {textContent: ''}, carries = {textContent: ''}, licensed = {textContent: ''};
            // Supply geometry/credits rather than the DOM or the router: only
            // the production render path and its optional controls are at issue.
            function runsOf(shape) { return shape.runs; }
            function pointsIn(runs) { return runs.length; }
            function routeCredits() { return []; }
            function creditsOf() { return []; }
            function licenceLine() { return ''; }
            function markingLine() { return ''; }
            var shape = {runs: [1, 2], tally: {}}, selected, states = [];
            [null, {detail: true}, {}, {figure: {}, shape: shape},
             {composed: true, shape: shape, plan: {why: 'unsettled'}},
             {composed: true, shape: shape, plan: {}}].forEach(function (selection) {
                selected = selection;
                offered();
                states.push({display: download.style.display, disabled: download.disabled,
                             garmin: garminDownload ? garminDownload.disabled : null,
                             offer: offer.style.display, text: carries.textContent});
            });
            console.log(JSON.stringify(states));
        """
        result = subprocess.run([node, "-"], input=source, text=True, capture_output=True, timeout=15)
        assert result.returncode == 0, result.stderr
        states = json.loads(result.stdout)
        if not export_enabled:
            assert states == [{"display": "none", "disabled": False, "garmin": None, "offer": "none", "text": ""}] * 6
        else:
            assert states[-2]["disabled"] is True
            assert states[-1]["disabled"] is False
            assert states[-1]["display"] == "flex"
            assert states[-1]["text"] == "2 points"
            assert states[-2]["garmin"] is (True if has_garmin else None)
            assert states[-1]["garmin"] is (False if has_garmin else None)

    def test_an_export_missing_a_setting_is_refused(self, group):
        """A page that quietly wrote 'undefined' into a licence is worse than
        one that was never built."""
        fmap, layer = group

        with pytest.raises(ValueError, match="licence|credits|ascentMethod"):
            maps.add_profile_panel(fmap, [layer], export=self.exported(credits=None, ascentMethod=None))

    def test_every_setting_the_template_reads_is_one_it_insists_on(self, group):
        """The two lists are the same list. A setting the template reads and the
        check does not require is one a caller can leave out and find missing in
        a browser, which is the expensive place to find it."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer], export=self.exported())

        html = fmap.get_root().render()
        for setting in maps.EXPORT_SETTINGS:
            assert f"EXPORT.{setting}" in html, setting
        for setting in maps.EXPORT_ROUTE_SETTINGS:
            assert f"EXPORT.route.{setting}" in html, setting
        for setting in maps.EXPORT_WAYPOINT_SETTINGS:
            assert f"EXPORT.waypoint.{setting}" in html, setting

    def test_a_route_setting_missing_from_inside_its_own_block_is_refused(self, group):
        """Checking only the top-level key lets a `route` short of `partLength`
        build without a word, and the page then writes
        `<trails:part kind="routed" undefined="2027.0"/>`."""
        fmap, layer = group
        short = dict(self.exported())
        short["route"] = {name: value for name, value in short["route"].items() if name != "partLength"}
        short["waypoint"] = {name: value for name, value in short["waypoint"].items() if name != "origin"}

        with pytest.raises(ValueError, match="route.partLength.*waypoint.origin"):
            maps.add_profile_panel(fmap, [layer], export=short)

    def test_the_figures_a_file_is_written_from_travel_as_the_page_names_them(self, group):
        """Every field the export writes has to be a key the figures table
        actually carries; one that is not is a field the browser would write as
        'undefined' into the file that leaves the machine."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer], export=self.exported())

        html = fmap.get_root().render()
        assert '["id", "chain"]' in html or '["id","chain"]' in html

    def test_the_offer_says_nothing_where_the_panel_has_said_what_went_wrong(self, group):
        """Three things can stop a chain reaching the panel — no graph in the
        page, a graph that never arrived, a line the graph does not hold — and
        each is said once, by the line that knows which it was. A row under it
        still reading 'decoding' would contradict it, and a reader believes what
        is next to the button they were about to press."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer], export=self.exported())

        html = fmap.get_root().render()
        assert html.count("selected.missing = true") == 3
        assert "selected.missing ? '' :" in html

    def test_without_groups_nothing_is_added(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_profile_panel(fmap, [])

        # The class name alone is no longer proof: the theme's stylesheet names
        # every panel it colours, whether or not one was added. What only a real
        # panel produces is the call that makes one.
        assert "L.DomUtil.create('div', 'trails-profile-panel')" not in fmap.get_root().render()

    def test_without_figures_nothing_is_added(self):
        """A layer nobody measured has no profile to offer."""
        gdf = gpd.GeoDataFrame({"chain_id": ["a"], "geometry": [LineString([(12.8, 65.4), (12.81, 65.41)])]}, crs="EPSG:4326")
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        layer = maps.add_trails(fmap, gdf, name="Chains", group_field="chain_id")
        maps.add_profile_panel(fmap, [layer])

        # The class name alone is no longer proof: the theme's stylesheet names
        # every panel it colours, whether or not one was added. What only a real
        # panel produces is the call that makes one.
        assert "L.DomUtil.create('div', 'trails-profile-panel')" not in fmap.get_root().render()

    def test_it_starts_folded(self, group):
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        assert "var open = false;" in fmap.get_root().render()

    def test_a_line_is_named_from_what_it_carries(self, group):
        """It used to be read off the line's own hover label, which is how the
        name came to be drawn on the map at all — and on a phone that label
        opens on a tap and stays there: a second heading over the ground,
        saying what the row at the foot already says.

        The name travels with the figures and is the same string the file writer
        uses. The hover label is still read where there is one, so a page built
        with labels and without carried names still names its lines."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "var figure = figures[className] || {};" in html
        assert "if (figure.name) { return figure.name; }" in html
        # And then the label, and then the id — a line has to be called
        # something even where nothing said what.
        assert "var tooltip = layer && layer.getTooltip && layer.getTooltip();" in html
        assert "return figure.id;" in html

    def test_the_name_is_lent_to_whoever_has_only_the_class(self, group):
        """The chrome heads a docked popup with the line's name and used to read
        the map's own label for it — so removing the label would have left the
        info page headed *Details*. One table, one name, asked for by class."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "nameOf: function (className) { return (figures[className] || {}).name || null; }," in html

    def test_a_place_tapped_shows_its_page(self, group):
        """Reported from the phone about the search's own mark: *I have no way of
        selecting the point I set again.* Pressing the panel's heading folds the
        pages away -- which is what a reader who wanted the map back has just
        done -- and with them folded, tapping a place brought the panel back as a
        46 px strip carrying its name and nothing else. Asking to read a place is
        asking."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "showDetails: function () {" in html
        # From both branches, and the early return for a place was the branch
        # that needed it.
        assert html.count("this.showDetails();") == 2

    def test_a_place_read_while_planning_keeps_its_page(self, group):
        """Reported from the phone as *how do I add a coordinate as a waypoint*,
        and the answer was that you could not: the offer stood on the page of the
        place, plan mode refreshes the panel on every edit, and each refresh fed
        it a route or a null -- both of which threw the popup's page away. So the
        button was in the document where no finger could reach it.

        While plan mode owns the map nothing else can open a popup -- every click
        is a waypoint -- so the one there is one the reader asked for, out of the
        search. It outlives the plan's refreshes, the panel unfolds at it, and it
        goes when plan mode does."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "if (detailHtml && (isPoint || suspended)) { this.showDetails(); }" in html
        assert "if (pages[turn].key === 'details') { goPage(turn); break; }" in html
        assert "hold.style.display = ((open || (suspended && detailHtml)) && pagesOpen) ? 'block' : 'none';" in html
        assert "if (was) { detailHtml = null; fold(); }" in html

    def test_a_composed_route_is_not_the_thing_the_popup_came_off(self, group):
        """Reported: taking the planned route from the row of choices left the ⓘ
        page showing the table of the line chosen before it. A popup is cleared
        when the selection *goes* and not when it changes — deliberately, because
        a line's popup arrives before the click that selects it — but nothing
        ever hands a popup for a route somebody planned. Its page is its own
        figures, which is what it has to say about itself."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "if (given && given.composed && !suspended) { detailHtml = null; }" in html
        # And the page is still offered, because a composed route says its
        # figures there rather than a table.
        assert "if (detailHtml || (!(planNow && planNow.on) && saidLines.length)) {" in html

    def test_the_points_and_stages_are_a_page_after_plan_mode_too(self, group):
        """The points and the stages are what a planned route *is*, and going
        back into plan mode to read them is a mode change to look at something.

        Read-only there: the row of edits at its head carries the tour's name
        and the way back, and both are edits."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "(selected && selected.composed && selected.plan &&" in html
        assert "selected.plan.waypoints && selected.plan.waypoints.length)) {" in html
        assert "undoRow.style.display = (planNow && planNow.on) ? 'flex' : 'none';" in html

    def test_a_tap_keeps_what_else_it_reached(self, group):
        """Six sources can map one valley and the tap takes the nearest paint —
        the right rule, and not an answer the reader gave: two lines a pixel
        apart are a coin toss. The tap now keeps everything within the same
        reach that picked the winner, ranked the same way, and the row at the
        foot offers them.

        The same measurement and not a second one: a row offering a line the tap
        could never have hit would be worse than no row at all."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "function near(point) {" in html
        assert "near: near," in html
        assert "window.trailsReach.near(map.latLngToLayerPoint(at)).forEach(function (found) {" in html
        assert "if (event && event.latlng) { gather(event.latlng); }" in html
        # A line with nothing to show for it is not offered.
        assert "if (!key || seen[key]) { return; }" in html

    def test_the_row_of_choices_is_only_there_when_there_is_a_choice(self, group):
        """A row that is always there costs a line of a 390 px panel for the
        ordinary tap that hit one line and meant it. It appears at two, and the
        panel is a different height with it — which the pages cap themselves
        against and the chrome lays the page out around, so both are told, and
        told only when it actually comes or goes."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "var wanted = selected && choices.length > 1;" in html
        assert "picks.style.display = wanted ? 'flex' : 'none';" in html
        assert "if (was !== picks.style.display) {" in html
        assert "if (window.trailsChrome && window.trailsChrome.placed) { window.trailsChrome.placed(); }" in html
        # Nothing selected is nothing to choose between.
        assert "if (given === null) { if (!suspended) { detailHtml = null; } choices = []; }" in html

    def test_one_chip_per_source_and_not_one_per_line(self, group):
        """Measured at the busiest crossing on this map: thirteen lines within
        one finger, eight of them FKB fragments of the same path, and a row of
        thirteen chips reading `fkb-373967-7264149-8` is not a choice anybody
        can make.

        *Which source* is the question a bundle raises, and the figures already
        carry the answer. The nearest line of each source is the one the chip
        selects — which is the line the tap would have taken anyway — and the
        lit chip is decided by source too, because one path drawn in eight
        pieces is eight class names and one answer. Six at most: past that a
        reader is reading a list rather than choosing."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "return figure.source || figure.name || className;" in html
        assert "return entry.source || entry.label || 'this line';" in html
        assert "return sourceKey(selected.className) === entry.key;" in html
        assert "var CHOICES_MAX = 6;" in html
        assert "choices = choices.slice(0, Math.max(1, CHOICES_MAX - mine.length)).concat(mine);" in html

    def test_the_planned_route_is_a_choice_like_any_other(self, group):
        """Reported from a phone: leaving plan mode leaves the route drawn and
        on the panel — which is right — and then one tap on any other line took
        the panel for good. The route's line is in a pane that takes no clicks
        at all, deliberately, so that it never stands between a reader and the
        trail under it; the only way back was switching plan mode on and off
        again, which is a mode change to look at something.

        **Last in the row, however near it ran.** It is not one of this map's
        sources and it lies on them by construction — it was routed along them —
        so ranking it by distance dropped it into the middle of the row and
        moved the sources a reader was choosing between. Not offered at all
        while plan mode is on: there the panel is showing it already, and a tap
        means *put a point here*.

        **And taking it makes the line let go.** Reported: the panel changed to
        the route while the trail underneath stayed widened and the rest of the
        map stayed faded — and the two being out of step then made every second
        press of that trail's chip mark nothing at all."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "? window.trailsPlan.onRoute(at.lat, at.lng, reach) : null;" in html
        # At the same distance as everything else the tap could have meant: the
        # tighter reach is for aiming a point into a leg.
        assert "var reach = (window.trailsReach && window.trailsReach.finger) || undefined;" in html
        assert "choices = choices.slice(0, Math.max(1, CHOICES_MAX - mine.length)).concat(mine);" in html
        # **Two of the reader's own lines can be offered now**, so they are
        # gathered apart from the sources and appended after them: the planned
        # route and, after it, the way to a goal. `mine` is what they are.
        assert "mine.push({gap: Infinity, mine: 'plan', key: 'plan', className: null," in html
        # Told apart by *which* composed route it is and not by `composed`,
        # which both of them are: two can be offered at once.
        assert "if (entry.mine === 'plan') { return !!(selected.composed && !selected.goal); }" in html
        # `hold` and not `clear`: on a tap the panel's handler runs before the
        # highlight's own, so clearing would be undone by the line that was
        # tapped a moment later.
        assert "if (window.trailsHighlight.hold) { window.trailsHighlight.hold(); }" in html
        # And the other composed route has to let go of the panel, which the
        # highlight above does not cover: it is not on the map's highlight at
        # all, it is what the panel is drawing.
        assert "if (!litChoice(entry)) {" in html
        assert "if (window.trailsGoal) { window.trailsGoal.letGo(); }" in html
        # The plan is worked out at all only where plan mode is off.
        assert "var route = (!planNow && window.trailsPlan && window.trailsPlan.onRoute)" in html

    def test_a_planned_route_takes_the_tap_wherever_it_runs(self, group):
        """It is the one line on this map the reader made, and it lies on the
        others by construction — it was routed along them — so a tap in reach of
        it that chose the trail underneath answered a question nobody asked.

        **Including where no trail is under it.** A leg over trackless ground
        has no line to carry the tap and the route's own takes none, so a tap
        out there used to be a tap on nothing: it put the panel away, with the
        route drawn under the finger that did it.

        The trails the tap also reached are still in the row, one press away,
        and the route stands last in it."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "function planChoice() {" in html
        assert "var mine = event && event.latlng ? planChoice() : null;" in html
        assert "if (mine) { takeChoice(mine); return; }" in html
        # And on ground with nothing else on it, where Leaflet fires the map's
        # own click rather than a line's.
        assert "map.on('click', function (event) {" in html
        assert "var mine = planChoice();" in html
        # Plan mode still owns its own clicks, and nothing here runs there.
        assert html.count("if (suspended) { return; }") >= 2

    def test_pressing_a_chip_is_the_click_it_stands_for(self, group):
        """Everything a click on that line does — the highlight widening it, its
        own details arriving, the panel selecting it — is already wired to that
        event, and a second path through them is a second set of rules to keep
        in step.

        **And it carries no point, which is what keeps the row still.** The list
        came from a measurement to the *paint*, and selecting a line widens it
        by four pixels and brings it to the front: re-asking after the press
        moved the pressed chip to the head of the row, under the reader's
        finger, every time. Reported from a phone, and the row belongs to the
        tap that made it rather than to what is selected now."""
        fmap, layer = group
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "entry.layer.fire('click', {layer: entry.layer});" in html
        assert "if (litChoice(entry)) { paintChoices(); return; }" in html
        # Which is only sound because the list is taken at the tap: a click with
        # no point on it leaves the row alone.
        assert "if (event && event.latlng) { gather(event.latlng); }" in html

    def test_the_way_to_a_goal_is_a_choice_after_the_planned_route(self):
        """Both are lines the reader made rather than sources this map carries,
        and both lie on the sources by construction — they were routed along
        them — so ranking either by distance would drop it into the middle of
        the row and move the sources somebody was choosing between. Their place
        is a fact about what they are.

        The goal goes last of the two because it is the more recent of the two
        things they made, and last is where the one a tap takes has stood since
        the planned route was put there."""
        fmap, layer = self.drawn()
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "mine.push({gap: Infinity, mine: 'goal', key: 'goal', className: null," in html
        # **And only where it runs.** Offered wherever the tap landed, it took
        # every tap on the map — the row's own rule is that a line the reader
        # made takes the tap — and a way tapped in order to be read was
        # answered with the goal.
        assert "if (wayThere && wayThere.line && window.trailsGoal.near(at.lat, at.lng, reach)) {" in html
        # Room kept for both, rather than for one: six chips is the ceiling and
        # the reader's own lines are not what it is protecting them from.
        assert "choices = choices.slice(0, Math.max(1, CHOICES_MAX - mine.length)).concat(mine);" in html
        # And a tap takes the goal before the plan, for the same reason it
        # takes the plan before a trail: it is the more particular instruction.
        assert "if (choices[at].mine === 'goal') { return choices[at]; }" in html

    def test_a_goal_is_a_page_of_the_panel_and_not_a_row_over_it(self):
        """The switch that *sets* a goal is in the rail, because arming the next
        tap is what the rail does. What there is to do with one once it is set
        — which way to read it, add a stop, work it out again — heads a page of
        the panel beside the profile, the way the plan's points do.

        **Wanted while the goal is what the panel shows, and not while a goal
        merely stands.** The row used to stand over the heading whenever a goal
        stood at all, with the list of places under it: over every trail the
        reader tapped to read. Reported from the phone, and it is a page now,
        there with the goal's series and gone with it.

        What the row said — the name, how many places it goes by, the figures
        — is the heading's now, from the series the goal control hands over,
        like every other route on this panel. And being rid of a goal is a
        line in its own menu, in words: the × stood one thumb-width from *add
        a stop*."""
        fmap, layer = self.drawn()
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "goalRow.className = 'trails-profile-goal';" in html
        assert "placesPage.className = 'trails-profile-places';" in html
        assert "placesPage.appendChild(goalRow);" in html
        assert "placesPage.appendChild(goalList);" in html
        assert "if (selected && selected.goal) {" in html
        assert "made.push({key: 'places', kind: 'list', node: placesPage," in html
        assert html.count("[body, detailBox, pointsPage, placesPage]") == 3
        assert "box.appendChild(goalRow);" not in html
        assert "box.appendChild(goalList);" not in html
        assert "window.trailsGoal.way('direct')" in html
        assert "window.trailsGoal.way('routed')" in html
        assert "window.trailsGoal.again()" in html
        # Nothing said in the row: no name, no count, no figures.
        assert "trails-profile-goal-said" not in html
        assert "km off the paths" not in html
        # Except the one line the heading has no room for: the heading shows
        # three lines of figures and how much of the way was never a path came
        # fourth. A reader being shown a line has to know which part of it is
        # a promise and which a bearing.
        assert "goalNote.className = 'trails-profile-goal-note';" in html
        assert "notes.push((goalNow.straight / 1000).toFixed(2) + ' km of it drawn straight, not a path');" in html
        # The lines the heading has no room for, one under the other: what the
        # straight part wades through, and how steep it gets there.
        assert "notes = notes.concat(goalNow.rivers || []);" in html
        assert "notes.push('steepest ' + goalNow.steepest + ' % on the straight part');" in html
        assert "} else if (!goalNow.line && routed) { notes.push('No way there \\u2014 drawn straight'); }" in html
        # Rid of by the panel's own button, drawn as a struck flag while the
        # way is what the panel shows -- and by nothing else. The line in the
        # goal's menu was asked for from the phone as *how do I leave this*.
        assert "trails-profile-goal-clear" not in html
        assert "trails-profile-stop-drop" not in html
        hide = html.split("hide.addEventListener('click', function (event) {")[1].split("            });")[0]
        assert "if (selected && selected.goal && window.trailsGoal) {" in hide
        assert "var stops = window.trailsGoal.state().stops.length - 1;" in hide
        # A goal alone is a tap to set again; stops are work, and asked about.
        assert "if (stops > 0 && !window.confirm('Drop the goal and ' + stops +" in hide
        assert "window.trailsGoal.clear();" in hide
        # For anything else shown, the × lets go of the goal's note that the
        # panel is drawing it, or the next fix would put the way back.
        assert "if (window.trailsGoal) { window.trailsGoal.letGo(); }" in hide
        # The same flag the lit switch carries, struck through, only then.
        assert "var goalShown = !!(!planning() && selected && selected.goal);" in html
        assert "hide.innerHTML = planning() ? '\\u2713' : goalShown ? GOAL_STRUCK : '\\u00d7';" in html
        assert "hide.title = planning() ? 'Finish planning' : goalShown ? 'Drop the goal' : 'Put this away';" in html
        assert "hide.classList.toggle('trails-profile-hide-goal', goalShown);" in html
        assert '<path d="M5 3.4h8.3l-2.1 3.1 2.1 3.1H5Z"/>' in html.split("var GOAL_STRUCK = ")[1].split(";")[0]

    def test_stay_on_paths_is_a_switch_on_the_goal_page_with_its_state_on_its_face(self):
        """It was a tool in the menu with a lamp on the rail, and from the
        phone: *I cannot see whether it is on*. It sits under Direct/Routed,
        where the way it changes is read, as an on/off switch whose knob says
        which -- and it turns the one closure that prices open ground, for
        the plan as well as the goal, reading its state back from there."""
        fmap, layer = self.drawn()
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "goalPaths.className = 'trails-profile-goal-paths';" in html
        assert "goalPaths.setAttribute('role', 'switch');" in html
        assert "window.trailsPlan.stayOnPaths(!window.trailsPlan.stayOnPaths());" in html
        painted = html.split("function paintPaths() {")[1].split("var goalNote")[0]
        assert "goalPaths.setAttribute('aria-checked', String(on));" in painted
        assert "knob.style.transform = on ? 'translateX(14px)' : 'none';" in painted
        row, switch, note = (html.index(f"placesPage.appendChild({each});") for each in ("goalRow", "goalPaths", "goalNote"))
        assert row < switch < note
        # And nowhere else: not a tool, not a lamp on the rail.
        assert "key: 'paths'" not in html

    def test_the_goal_profile_marks_its_stations_as_the_map_does(self):
        """Reported from the phone: the profile put a 1 on where the reader
        stands, a place the map marks with no number, and a 2 on the stop the
        map calls 1. The series says what each station is now -- start, stop,
        goal -- and the profile draws a dot, the numbers the map gives, and the
        map's own ring. The list on the goal's page shows the ring too."""
        fmap, layer = self.drawn()
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "marks: spec.marks || null," in html
        drawn = html.split("var mark = selected && selected.marks ? selected.marks[index] : null;")[1].split("});")[0]
        assert "if (kind === 'start') {" in drawn
        assert "var radius = kind === 'start' ? STATION_R - 3 : STATION_R;" in drawn
        assert "ring.setAttribute('r', String(STATION_R + 2.5));" in drawn
        assert "if (kind === 'goal') { return; }" in drawn
        assert "mark && mark.label ? mark.label : String(index + 1)" in drawn
        # Rendered, because this region of the template writes the character.
        assert "number.textContent = last ? '\u25ce' : String(at + 1);" in html

    def test_the_stations_stand_in_a_strip_under_the_axis_and_the_chart_grows_for_it(self):
        """They sat on the curve at their own height, which put the goal's ring
        over the end of the curve and stacked a plan's close points on each
        other -- reported from the phone, both. A strip under the axis holds
        them now, one row per what fits, the kilometres below it; the chart and
        the page grow by the rows, so the curve keeps its height. Laid out
        before the kilometres are drawn, because they stand below the strip."""
        fmap, layer = self.drawn()
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "var STATION_R = 6;" in html
        assert "var STRIP = 16;" in html
        laid = html.split("var laidStations = [], rows = 0;")[1].split("var decimals")[0]
        assert "return other.row === row && Math.abs(other.here - here) < 2 * STATION_R + 2;" in laid
        assert "var stripHeight = rows ? STRIP + (rows - 1) * (2 * STATION_R + 3) : 0;" in laid
        assert "if (stripHeight !== stripNow) { stripNow = stripHeight; sizePages(); }" in laid
        assert "chart.setAttribute('viewBox', '0 0 ' + width + ' ' + (chartHeight + stripHeight));" in laid
        assert "box.bottom + stripHeight + 14, (value / 1000).toFixed(decimals), 'middle')" in html
        assert "chart.appendChild(text(plot.right, box.bottom + stripHeight + 14, 'km', 'end'));" in html
        assert "if (curved) { pagesBox.style.height = (chartHeight + stripNow) + 'px'; return; }" in html
        assert "var at = box.bottom + STRIP / 2 + 1 + station.row * (2 * STATION_R + 3);" in html
        assert "var rule = line(here, level, here, at - radius, ink);" in html

    def test_the_way_to_a_goal_can_become_a_plan(self):
        """Asked for from the phone. A goal is set in a moment and walked at
        once; a plan is edited, cut into stages and written to a file -- and a
        goal with three stops on the way is already the thing a plan is for.

        The reader's position goes in front where the page knows it, because
        that is where the way being looked at starts. The goal goes with the
        conversion: two routes over the same places, one editable and one not,
        is a page that cannot say which is being walked."""
        fmap, layer = self.drawn()
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()

        assert "window.trailsPlan.fromGoal();" in html
        assert "goalToPlan.textContent = 'Make a plan of this way';" in html
        # Offered while a goal stands, whether or not a way to it has been
        # worked out: the places are places either way.
        assert "goalToPlan.style.display = standing ? 'block' : 'none';" in html

    def test_a_goal_has_figures_of_its_own(self):
        """Reported from the phone as *the info is from another way*, and it
        was. The row under the drawing — the point count, the licences, the
        marking — returned before it was reached whenever a composed route had
        no plan attached, on the grounds that only a plan is composed. A goal is
        composed too, and has none: so its page kept whatever the line read
        before it had said, word for word, about a walk that was not this one."""
        fmap, layer = self.drawn()
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "if (!selected) { return; }" in html
        assert "var plan = selected.plan;" in html
        assert "carries.textContent = (plan && plan.why) ? plan.why" in html
        # And the page is filled whether or not it is the one being shown: the
        # pages lie side by side in a track that slides, so the page a reader is
        # swiping towards is on the screen before it arrives — long enough to
        # read the wrong name off it.
        assert "pages.forEach(function (page) { if (page.kind === 'details') { fillDetail(); } });" in html

    def test_the_goal_row_offers_a_stop_on_the_way(self):
        """The rail arms the one thing a reader does with nothing set; a stop is
        something they add to a journey that already exists, and this row is
        that journey. How many places it goes by is said before the figures: two
        stops turn a line into a journey, and somebody looking at 19 km has to
        know whether that is the way there or the way there by way of two huts.

        And *route again* stands for both readings now, because both are worked
        out from where the reader is and both can be out of date."""
        fmap, layer = self.drawn()
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "var goalStop = goalButton('trails-profile-goal-stop', '+', 'Add a stop on the way'," in html
        assert "window.trailsChrome.aiming('stop');" in html
        assert "goalAgain.style.display = 'flex';" in html
        # How many places it goes by is said in the heading, by the label the
        # goal control hands over with its series.
        assert "if (stops > 0) { said += " not in html

    def test_every_place_on_the_way_is_a_row_with_a_menu(self):
        """Reported from the phone: with stops on the way the only edit left
        was adding another. A stop could be taken away by a tap the hint used
        to explain and nothing explains now; it could not be moved at all; and
        the goal could not be moved without every stop going with it. The
        marks on the map cannot carry any of that, so it is said here in
        words, the way the plan's list says it about a route's points.

        One row per place, stops first and the goal last, each with how far
        into the way it comes; and a menu per row in the plan's shape — a
        labelled line and not a glyph. A stop can be moved, stepped one place
        either way and removed; the goal can only be moved, and moving it
        keeps the stops. Moved by the next tap, which is the gesture that set
        it: HTML5 dragging does not exist under a finger.

        Drawn from what the goal control last said and edited through its
        entry: the plan's list is one node lent between two owners, and a
        second rendering of a sequence is how two of them come to disagree."""
        fmap, layer = self.drawn()
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "goalList.className = 'trails-profile-stops';" in html
        assert "var stops = (goalNow && goalNow.at && goalNow.stops) ? goalNow.stops : [];" in html
        assert "row.className = 'trails-profile-stop';" in html
        assert "far.textContent = typeof stop.into === 'number' ? (stop.into / 1000).toFixed(2) + ' km' : '';" in html
        # The four lines of the menu, and which rows offer which.
        assert "menu.className = 'trails-profile-stopmenu';" in html
        assert "last ? '\u2316  Move the goal' : '\u2316  Move this stop'," in html
        assert "function () { if (window.trailsChrome) { window.trailsChrome.aiming('move', at); } }));" in html
        assert "'Walk to this stop one place earlier', !last && at > 0," in html
        assert "'Walk to this stop one place later', !last && at + 2 < stops.length," in html
        assert "'Take this stop out and walk straight on to the next', !last," in html
        assert "function () { if (window.trailsGoal) { window.trailsGoal.dropStop(at); } });" in html
        # Lit while the next tap moves it, the way the + lights while it adds.
        assert "(at === moving ? 'background:color-mix(in srgb, var(--trails-accent) 14%, transparent)' : '');" in html
        # An open menu outlives a repaint: the goal control repaints this on
        # every position fix, and a menu that shut itself while a reader was
        # reading it is a menu nobody can use while walking.
        assert "var stopMenuAt = -1;" in html
        assert "menu.style.cssText = 'display:' + (at === stopMenuAt ? 'block' : 'none') + ';width:100%;'" in html
        # On the goal's page, under its row of switches.
        assert html.index("placesPage.appendChild(goalRow);") < html.index("placesPage.appendChild(goalList);")


class TestPlanMode:
    """Tests for clicking a route together over the graph in the page."""

    def planned(self, **changed: object) -> dict[str, object]:
        """What the page has to be handed before it can plan a route.

        Args:
            **changed: Settings to override or, with a value of None, to drop

        Returns:
            A complete set, minus anything set to None
        """
        settings: dict[str, object] = {
            "heightsUrl": "https://ws.geonorge.no/hoydedata/v1/punkt",
            "heightsCrs": 4326,
            "heightsBatch": 50,
            "heightsWorkers": 6,
            # A deadline, because `fetch` has none: a server that accepts a
            # connection and then says nothing would leave a leg outstanding for
            # ever, and plan mode saying *working…* with nothing left to finish
            # it. See `heightsTimeoutMs` in the build's own settings.
            "heightsTimeoutMs": 8000,
            # No height tiles: this is the first map, whose heights are a
            # service. The second map's are tested on their own below.
            "heightsTiles": None,
            # As wide as the widest line this map draws, which is the build's
            # decision and not the page's: a route thinner than the line under
            # it reads as the lesser of the two.
            "routeWidth": 4.0,
            "terrainModel": "dtm",
            "seaTerrain": "Havflate",
            "sampleStepM": 5.0,
            "ascentThresholdM": 5.0,
            "snapM": 150.0,
            # The same reach measured on the screen: a gesture snaps within
            # whichever is smaller, so a tap means the line under it rather than
            # one a finger away.
            "snapPx": 12,
            "maxStraightM": 20000.0,
            # What a metre of open ground costs against a metre of path, in the
            # currency the edge costs are in. Above the dearest factor any drawn
            # line carries, or a route would rather cross a bog than take a
            # surveyed line.
            "offPathFactor": 3.0,
            # And what a metre of it costs where the graph's water grid says
            # it is sea or lake: dear enough that a road round a sound beats
            # a dotted line across it.
            "waterFactor": 30.0,
            "crossingKind": "ferry",
            "connectorKind": "bridge",
            "touchedM": 100.0,
            "namedM": 50.0,
            "indexCellM": 100.0,
            "matchToleranceM": 25.0,
            "matchMinOverlap": 0.6,
            "matchMinRunM": 100.0,
            "matchMaxTurnDeg": 60.0,
            "matchAnchorM": 250.0,
            "gpx": {
                "namespace": "https://github.com/ueisele/trails/gpx/1",
                "kindField": "kind",
                "kind": "route",
                "chainField": "chain",
                "legs": "legs",
                "leg": "leg",
                "part": "part",
                "partKind": "kind",
                "partLength": "m",
                "origin": "origin",
                "set": "set",
                "generated": "generated",
                "trackKind": "track",
                "stage": "stage",
            },
        }
        settings.update(changed)
        kept = {name: value for name, value in settings.items() if value is not None}
        # The one setting whose value *is* None on the first map: dropped it
        # would read as missing, and it is not missing, it is a map without
        # height tiles. Handed in explicitly to override.
        if "heightsTiles" not in changed:
            kept["heightsTiles"] = None
        return kept

    def drawn(self) -> tuple[folium.Map, folium.FeatureGroup]:
        """A map carrying a chain, the graph and the panel, ready for plan mode."""
        gdf = gpd.GeoDataFrame(
            {"chain_id": ["ut-no-1-2-3"], "ascent": [996.4], "geometry": [LineString([(12.8, 65.4), (12.81, 65.41)])]},
            crs="EPSG:4326",
        )
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        layer = maps.add_trails(fmap, gdf, name="Chains", group_field="chain_id", figure_fields={"ascent": "ascent"})
        maps.add_routing_graph(fmap, {"version": 2, "edges": 0}, "")
        maps.add_profile_panel(fmap, [layer])
        return fmap, layer

    def test_every_setting_the_template_reads_is_one_it_insists_on(self):
        """The two lists are the same list. A setting the template reads and the
        check does not require is one a caller can leave out and find missing in
        a browser, which is the expensive place to find it."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()
        for setting in maps.PLAN_SETTINGS:
            assert f"PLAN.{setting}" in html, setting

    def test_every_setting_the_template_reads_is_one_the_check_knows_about(self):
        """The converse of the test above, and the one that was missing.

        That direction — list to template — says nothing about a name the
        template reads that is not on the list, and JavaScript has no complaint
        to make about one: ``PLAN.matchAnchorM`` was left out of
        :data:`PLAN_SETTINGS` while the matcher read it, ``along[i] - since <
        undefined`` is ``false``, and every recorded point became an anchor. The
        matcher then matched **3.6 %** of a track that lies exactly on the
        network, and nothing threw, nothing logged, and the page looked right.
        """
        planning = files("trails.visualization").joinpath("js", "plan_mode.js").read_text(encoding="utf-8")
        read = set(re.findall(r"PLAN\.([A-Za-z_][A-Za-z0-9_]*)", planning)) - {"gpx"}
        assert read - set(maps.PLAN_SETTINGS) == set()
        assert set(maps.PLAN_SETTINGS) - read - {"gpx"} == set()

        inside = set(re.findall(r"PLAN\.gpx\.([A-Za-z_][A-Za-z0-9_]*)", planning))
        assert inside - set(maps.PLAN_GPX_SETTINGS) == set()
        assert set(maps.PLAN_GPX_SETTINGS) - inside == set()

    def test_every_name_the_reader_looks_for_is_one_the_check_insists_on(self):
        """Phase 8 both reads and writes this file, which nothing else here does.
        A ``gpx`` short of one name leaves the page looking for an element called
        ``undefined``, finding none, and reporting one of its own routes as a
        foreign track without a word."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()
        for setting in maps.PLAN_GPX_SETTINGS:
            assert f"PLAN.gpx.{setting}" in html, setting

    def test_a_plan_that_cannot_read_a_file_back_is_refused(self):
        """The same refusal as a missing sampling step, for the same reason: a
        page that guessed a field name would load its own routes as foreign
        tracks and nothing about it would look wrong."""
        fmap, _ = self.drawn()
        short = self.planned()
        short["gpx"] = {name: value for name, value in short["gpx"].items() if name not in ("origin", "trackKind")}

        with pytest.raises(ValueError, match="gpx.origin|gpx.trackKind"):
            maps.add_plan_mode(fmap, short)

    def test_a_plan_with_no_gpx_block_at_all_is_refused(self):
        """Checked as its own list rather than by the presence of the key above
        it, which is how :data:`EXPORT_ROUTE_SETTINGS` is checked and for the
        same reason."""
        fmap, _ = self.drawn()

        # An empty block rather than no block: dropping the key means the check
        # above this one fires first, and the branch this test is about is never
        # reached — which is what it did until a review said so.
        with pytest.raises(ValueError, match=r"read a GPX back without gpx\."):
            maps.add_plan_mode(fmap, self.planned(gpx={}))

        with pytest.raises(ValueError, match="without gpx$"):
            maps.add_plan_mode(fmap, self.planned(gpx=None))

    def test_a_plan_missing_a_setting_is_refused(self):
        """A page that quietly sampled every 50 m, or read a climb at no
        threshold at all, would look exactly like one that did neither."""
        fmap, _ = self.drawn()

        with pytest.raises(ValueError, match="sampleStepM|ascentThresholdM"):
            maps.add_plan_mode(fmap, self.planned(sampleStepM=None, ascentThresholdM=None))

    def test_the_build_s_own_step_and_threshold_reach_the_page(self):
        """Two halves of one profile read under two rules answer differently,
        and nothing about the answer looks wrong."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned(sampleStepM=7.5, ascentThresholdM=3.25))

        html = fmap.get_root().render()
        assert "7.5" in html
        assert "3.25" in html

    def test_every_mode_says_what_it_does_to_every_kind_of_file(self):
        """The mode names have to be true of a planned route and of somebody's
        GPS recording at once, and they cannot be: read as a plan, *take it as it
        is* means the route as it was planned; read as a recording it means the
        line as it was walked. So the question is asked once the file has been
        read, in terms of the file -- and the wording lives in one table keyed by
        both, because a sentence and the mode it describes are one decision.

        Checked in **both** directions. A kind missing a mode leaves the sentence
        under the selector ``undefined`` and JavaScript has nothing to say about
        it; a kind naming a mode that does not exist is a sentence no reader can
        ever reach. That asymmetry cost this page an hour once already.
        """
        planning = files("trails.visualization").joinpath("js", "plan_mode.js").read_text(encoding="utf-8")
        modes = set(re.findall(r"\{key: '([a-z]+)', label:", planning))
        assert modes

        table = planning.split("var READINGS = {")[1].split("\n            };")[0]
        kinds = re.findall(r"\n                ([a-z]+): \{(.*?)\n                \}", table, re.S)
        assert {kind for kind, _ in kinds} == {"route", "chain", "track"}

        for kind, block in kinds:
            named = set(re.findall(r"\n                    ([a-z]+):", block))
            assert named - {"first"} == modes, kind
            first = re.search(r"first: '([a-z]+)'", block)
            assert first and first.group(1) in modes, kind

    def test_the_mode_is_asked_after_the_file_has_been_read(self):
        """It stood beside the button and had to be answered before anybody knew
        what was in the file. A reader picking the first of the three lost the
        points their route was planned with -- measured, six set waypoints in the
        file and two points on the map -- while the page named the number it was
        about to discard.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        # The picker reads and describes; nothing is taken by picking a file.
        assert "offerFile(String(reader.result), file.name);" in html
        assert "loadGpx(String(reader.result)" not in html
        assert "class ='trails-plan-offer'" not in html
        assert "offerBox.className = 'trails-plan-offer';" in html

    def test_a_file_read_and_not_taken_replaces_nothing(self):
        """The question is the only moment at which the plan on the map still
        exists: taking a file replaces it and there is no way back, because undo
        takes a point off the end and a load has no history. So reading must
        touch nothing -- one place puts a file on the map, and it is the one the
        reader reaches through an answer.
        """
        planning = files("trails.visualization").joinpath("js", "plan_mode.js").read_text(encoding="utf-8")

        assert planning.count("points = pointsForLoaded(graph);") == 1
        assert planning.count("loaded = read;") == 1
        taking = planning.split("function takeGpx(read, mode) {")[1].split("\n            }")[0]
        assert "points = pointsForLoaded(graph);" in taking
        assert "loaded = read;" in taking

        # And what it costs is said before it happens, as a count rather than
        # as a warning about files in general. **It no longer says there is no
        # way back**: the history covers a load, so undo restores the plan the
        # file replaced. The sentence was true when it was written and the
        # question is still worth asking -- it says what the file turned out to
        # be and what each mode would do to it, which was never the half about
        # the way back.
        assert "' points' ) + ' on the map." not in planning
        assert "on the map. Undo brings them back." in planning

    def test_a_plan_is_restored_from_its_own_leg_list(self):
        """*Take it as it is*, read as what the file describes. The seam is
        **inside** a leg -- a matched leg is ``routed + track + routed`` -- which
        is why nothing restored one before: ``anchorRecordedLegs`` asks whether a
        leg is *wholly* recorded and so never fires on the legs that need it.
        Measured, align routed 1,038 recorded metres away and came back 353 m
        short without a word; restored, the same route comes home at 5,986.6 m
        with its three points and its four parts.

        The order in ``resolve`` is the test worth having: both ends of a
        restored leg may well sit on a node, so a routing branch reached first
        would replace a recorded stretch with whatever path lies there.
        """
        planning = files("trails.visualization").joinpath("js", "plan_mode.js").read_text(encoding="utf-8")
        deciding = planning.split("function resolve(graph, from, to, mayAsk, partly) {")[1]

        assert deciding.index("from.restore") < deciding.index("from.track === loaded.id")
        assert deciding.index("from.restore") < deciding.index("onNetwork(from) && onNetwork(to)")
        # **And only for the pair the file described.** Reported from the phone
        # with the file: point 5 of eight taken out, and the new leg from 4 to
        # 6 was laid out as the file's leg from 4 to 5 -- ending in the open,
        # 8 km short of its far point, the walk shorter by exactly the leg
        # that was dropped. The description lives on the first point and now
        # names the second; a dragged point is a new object and a removed one
        # leaves its neighbour facing another, and neither matches.
        assert "if (from.restore && from.restoreTo === to) {" in deciding
        assert "for (i = 0; i + 1 < made.length; i += 1) { made[i].restoreTo = made[i + 1]; }" in planning

        # And it is offered only where there is a plan in the file to restore.
        assert "loaded.mode === 'asis' && loaded.isRoute" in planning
        assert "loaded.waypoints.length === loaded.legs.length + 1" in planning

    def test_a_restored_routed_stretch_is_held_to_the_length_the_file_states(self):
        """A routed part of a *matched* route is a run of spans between anchors
        merged into one, and the cheapest path between its two ends is not the
        concatenation of the cheapest paths between the anchors along it -- the
        same thing this project already measured about align on a matched route,
        7,266 m against 7,307. Here it read **2,899 against 3,142**, and routing
        alone would have restored a plan 243 m short while calling it exact.

        So each way of laying the stretch is checked against the length the file
        states, and they are tried in the order that keeps the most: routed,
        then matched off the very geometry the router produced, then the file's
        own line -- which is exact and costs the edges underneath, and is what
        ``drifted`` then says out loud.
        """
        planning = files("trails.visualization").joinpath("js", "plan_mode.js").read_text(encoding="utf-8")
        laying = planning.split("function restoredWalked(")[1].split("\n            function agrees")[0]

        assert laying.count("agrees(") == 2
        assert laying.index("routedParts(graph, found)") < laying.index("matchedParts(graph, first, last)")
        assert laying.index("matchedParts(graph, first, last)") < laying.rindex("trackPart(graph, first, last)")

    def test_a_waypoint_off_the_track_keeps_the_position_it_was_written_at(self):
        """A point set on open water is in the ``<wpt>`` list and in no
        ``<trkseg>`` at all -- the crossing either side of it writes no geometry,
        which is what stops a file drawing a line across a fjord. Anchoring it to
        the nearest trackpoint would put it on the shore, and the shore is where
        it went: measured, three points out and eight back with the offshore one
        gone. Restored, it comes home at the position it was set.

        **And it stays there.** The position used to be snapped once it was off
        the track, which moves it up to ``snapM`` — so it came home to a node
        rather than to where it was written, and the legs either side of it were
        routed between somewhere elses. Caught by the reload check the day
        gestures stopped snapping at 150 m and raw waypoints became ordinary:
        19.1 km saved, 68.3 km restored, and nothing about the drawing looked
        wrong. A file says where the reader put a point, there is nothing to
        improve on that, and a leg from a point off the network reaches it by a
        connector anyway.
        """
        planning = files("trails.visualization").joinpath("js", "plan_mode.js").read_text(encoding="utf-8")
        placing = planning.split("if (restoring()) {")[1].split("if (loaded.mode === 'align')")[0]

        assert "<= 1.0" in placing
        assert "anchored(graph, at) : {lat: wp.lat, lon: wp.lon, node: -1};" in placing
        # And a crossing contributes none of its length to the walking, so the
        # stations cannot be summed off the parts without saying so.
        assert "part.kind !== 'water' && part.kind !== CROSSING" in placing

    def test_a_loaded_route_is_shown_once_and_not_once_a_refresh(self):
        """The map stands wherever the reader left it and a file may describe
        ground fifty kilometres away, so a load that changes nothing on the
        screen reads as a load that did nothing. Driven: the map at zoom 9 over
        the park moves to zoom 13 over a loaded recording with all 1,233 of its
        vertices inside the window, and a map deliberately moved 50 km away
        comes back to a loaded route with every point of it in view.

        **The fit follows the settle, not the load.** A route half worked out has
        half a shape, and fitting to that leaves the reader looking at the wrong
        window. And it happens once: the map is the reader's from that moment,
        and a control that moves it twice is one that fights the hand.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        assert "fitWanted = true;" in html
        assert "if (fitWanted) { fitWanted = false; showRoute(); }" in html
        # Fitted to what is drawn *and* to the points, which are not the same
        # set: a waypoint on open water lies inside a crossing, and a crossing
        # draws nothing at all.
        showing = html.split("function showRoute() {")[1].split("\n            }")[0]
        assert "points.forEach(" in showing
        assert "maxZoom: SHOW_MAX_ZOOM" in showing
        # Measured rather than assumed: both controls are the reader's to resize.
        assert "getBoundingClientRect().height" in showing
        assert "getBoundingClientRect().width" in showing

    def test_a_stage_mark_survives_being_dragged(self):
        """A tour is planned whole and walked in pieces, and the mark lives on
        the point object so that reordering and inserting carry it along without
        a case of their own. **A drag is the exception and the trap**: phase 7's
        model replaces a dragged waypoint with a *new* object on purpose, which
        is what tells the legs beside it to rebuild — so anything the reader put
        on the old one is lost unless it is carried over by hand, and a mark lost
        by dragging a point would be lost silently.

        Driven: three stages cut, one named, then point 5 dragged and point 2
        moved to the front. All three survive both, and come back out of the file
        the same way.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        assert "var was = points[at].stage;" in html
        assert "if (was !== undefined) { points[at].stage = was; }" in html
        # And it reaches the file, which is a different list from the point.
        assert "stage: cut};" in html
        assert "if (typeof wp.stage === 'string') { here.stage = wp.stage; }" in html

    def test_a_tour_nobody_has_cut_is_offered_no_stages(self):
        """One stage is the whole route, and a heading over it would offer the
        file the button already offers under a second name -- which is the
        two-panel mistake the legend was cured of. The archive follows the same
        rule for a harder reason: with one stage it would hand over the same
        file twice.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        assert "if (stages.length > 1) {" in html
        # And only where the panel can write a file at all, and only while the
        # list is showing -- each heading composes its own stage to state its
        # figures, which is a walk over the route per stage nobody is looking at.
        #
        # **Showing, not folded open.** The list is lent to the profile panel,
        # where it stands whether or not this control's own fold has been
        # touched; everything drawn *because* the list is showing was still
        # asking that fold, so a route cut into two stages drew neither heading
        # and the save menu opened empty.
        assert "function listShowing() { return lentOut || listOpen; }" in html
        assert "var gathered = writes && listShowing() && stagesOf().length > 1;" in html
        assert "var stages = (listShowing() && points.length) ? stagesOf() : [];" in html
        # The ends are never marked: a tour ends where it ends, and a mark there
        # would make a stage of no legs.
        assert "if (at < 1 || at + 1 >= points.length) { return; }" in html

    def test_a_stage_states_what_it_was_composed_to_state(self):
        """Its ascent is not the difference of two ascents, its steepest is a
        maximum over its own window, and its crossings are its own -- a stage
        that inherited an ``Enters`` from ground it never covers would be a file
        stating something about somewhere else. So a range is a narrowing of the
        one walk and never a slice of its figures.

        Driven: three stages of a 32,175.4 m tour come to 12,351.6, 12,403.9 and
        7,419.9 m, which is the walk exactly.
        """
        planning = files("trails.visualization").joinpath("js", "plan_mode.js").read_text(encoding="utf-8")

        assert "composeRoute(stage.from, stage.to)" in planning
        assert planning.count("function composeRoute(fromLeg, toLeg, over)") == 1
        # And the writer works its runs and its crossings out from the shape it
        # is handed, which is what makes a stage's file its own.
        panelling = files("trails.visualization").joinpath("js", "profile_panel.js").read_text(encoding="utf-8")
        writing = panelling.split("routeFile: function")[1].split("routeName:")[0]
        assert "runsOf(shape)" in writing
        assert "crossingsOf(shape, runs)" in writing

    def test_the_archive_is_written_here_because_nothing_may_be_added(self):
        """Several files as one download, against several downloads in a row --
        which rests on an assumption about what a browser lets a page opened off
        the disk do unattended, where an archive rests on arithmetic. Measured
        before it was written: a hand-made zip downloads from this page, keeps
        its name, opens in Python with a clean ``testzip()``, and every member
        reads back byte for byte. Deflated it is 1.87 MB of GPX in 282 kB.

        **Stamped with the time it was written**, which is a correction: it went
        in at zero on the rule that no trackpoint carries a time, and that rule
        is about the *route* -- a time on a trackpoint claims somebody walked
        there at that hour. When an archive was written claims nothing about the
        walk. And zero is not absent: the DOS field counts from 1980, so every
        member showed 1980-01-01, a wrong answer stated confidently.
        """
        fmap, _ = self.drawn()

        html = fmap.get_root().render()

        assert "function crc32(bytes) {" in html
        assert "new CompressionStream('deflate-raw')" in html
        # Stored where the browser cannot deflate, and where deflating made it
        # bigger -- a zip that grew its own members advertises itself badly.
        assert "u16(deflated ? 8 : 0)" in html
        assert "small.length < member.body.length" in html
        # One stamp for the whole archive, in the local header and again in the
        # central directory entry: the members were written in one act.
        assert html.count("u16(stamp.time), u16(stamp.date), u32(sum)") == 2
        assert "var stamp = dosStamp(new Date());" in html

    def test_a_point_where_a_stage_changes_hands_says_so(self):
        """A pin already carries two things -- which number it is and whether it
        is picked -- so a third meaning has to be readable beside both rather
        than instead of one. A second ring, drawn as a shadow so the icon keeps
        its size and its anchor and nothing about where a click lands moves.

        **The ends are not marked.** A tour begins and ends whether anybody says
        so, and a ring at the finish would claim the walk carries on past it.
        Driven with cuts after points 3 and 5: exactly pins 3 and 5 carry it, the
        marker pane stays at one per point, and the two stations on the profile
        carry two circles where the others carry one.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        assert "function pinStyle(picked, ends) {" in html
        assert "box-shadow:0 0 0 2px " in html
        # Never the first or the last, in the one list all three readings of a
        # cut are taken from.
        assert "for (var i = 1; i + 1 < points.length; i += 1) {" in html
        assert "stages: cutsOf()});" in html

    def test_it_draws_nothing_on_the_map(self):
        """The route belongs in a pane of its own: anything drawn into the
        overlay pane is counted among the map's paths for ever after, and 11,589
        is an acceptance figure for every phase from the third."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())
        assert not [child for child in fmap._children.values() if isinstance(child, folium.GeoJson | folium.Marker)]
        html = fmap.get_root().render()
        assert "createPane('trailsPlanRoute')" in html
        planning = html.split("var PLAN =")[-1]
        # **Which pane is an argument now**, because the goal draws the same
        # shapes — same width, same casing, same dashes — in its own pane and
        # its own colour: what a route *is* is not the goal's to differ in, only
        # which route it is. The default is still the plan's own.
        assert "var pane = into ? into.pane : 'trailsPlanRoute';" in planning
        # Every layer it makes names that pane. One that did not would land in
        # the overlay pane by default, which is the whole thing being avoided.
        assert planning.count("L.polyline(") == planning.count("pane: pane") - planning.count("L.circleMarker(")

    def test_a_click_in_a_popup_is_not_a_click_on_the_ground(self):
        """A popup is not in the control container -- it lives in a pane inside
        the map -- so a dispatcher that only steps around the controls walks
        over it. Measured: the close button of a chain's popup placed a waypoint
        behind it and left the popup open.

        The chrome is in the list for the same reason and was added later: it
        hangs off the map container rather than off a corner, so that a panel
        can cover the corners on a narrow screen. **The assertion names the
        members and not the string**, because a check that pins the exact list
        fails on the next thing that legitimately joins it.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        assert "function overFurniture(event) {" in html
        stepped = html.split("return !!event.target.closest('")[-1].split("')")[0]
        assert {part.strip() for part in stepped.split(",")} >= {
            ".leaflet-control-container",
            ".leaflet-popup",
            ".trails-chrome",
        }
        assert "if (!on || overFurniture(event)) { return; }" in html
        # **And the double click steps around the same list**, written as the
        # single click is since the picker joined them: one guard for what is
        # not terrain, one for the switch that owns the next tap whatever else
        # does.
        assert html.count("if (!on || overFurniture(event)) { return; }") >= 2
        # **Two switches now, and the same yielding.** The goal switch owns the
        # next tap exactly as the picker does, so plan mode stands back for
        # either rather than stopping the click.
        assert "window.trailsChrome.state().aiming)) { return; }" in html

    def test_switching_on_lets_go_of_a_highlighted_line(self):
        """The click-highlight's only two ways out are a click on the line and a
        click on empty ground, and plan mode owns both from the moment it is on.
        Left standing it dims every line on the map with no way back.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        assert "if (on && window.trailsHighlight) { window.trailsHighlight.clear(); }" in html

    def test_the_points_are_listed_in_order_behind_their_own_count(self):
        """A route is a sequence and a map cannot show a sequence: reading eleven
        numbered pins off a map to find that 7 comes before 8 is searching, not
        reading. The list is lent to the profile panel, which is where a reader
        planning a route is looking; where nothing borrows it — a page built
        without a panel — it stays behind the count that names it.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        assert "function drawList(stations) {" in html
        assert "listOpen = !listOpen;" in html
        assert "listBox.style.display = (listShowing() && (lentOut || listable)) ? '' : 'none';" in html
        # Moved rather than copied: a second rendering of a sequence is how two
        # of them come to disagree about the order.
        assert "if (!lentOut && panel() && panel().list) { lentOut = !!panel().list(listBox, titleRow); }" in html
        assert "if (!lentOut) { box.appendChild(listBox); }" in html
        # **And the name goes with it**, because it is what the list is a list
        # of: lent away without it, a reader planning on a phone had no way to
        # call the tour anything.
        assert "if (!lentOut) { box.appendChild(titleRow); }" in html
        assert "undoRow.insertBefore(named, undoOne);" in html
        # Drawn from the walk the panel is fed, so how far along a point comes is
        # the walk's answer and not a sum of the legs'.
        assert "drawList(shape.stations || []);" in html

    def test_the_route_is_as_wide_as_the_widest_line_under_it(self):
        """Reported from the device: the planned route reads thinner than a
        UT.no route beside it — and it was, 2.6 px of colour against 4.0,
        however wide the white casing around it made the whole mark.

        The width is the build's to decide, because which line is widest is a
        fact about the layers a build draws and not about planning. The casing
        keeps the 1.7 px it stands proud on each side: that is what makes the
        route legible over a dark line, not what makes it thick."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()
        assert "var HALO_PX = 1.7;" in html
        assert "[[CASING, PLAN.routeWidth + HALO_PX * 2], [colour, PLAN.routeWidth]]" in html
        # And a build that does not say how wide is refused, like every other
        # setting plan mode is handed.
        assert "routeWidth" in maps.PLAN_SETTINGS

    def test_the_list_is_an_overview_where_nothing_can_be_edited(self):
        """Outside plan mode the same list is a route somebody is reading: the
        grip promises a drag that would change the route, the menu offers four
        edits, and the stage name is a field. None of them is drawn there.

        What stays is what the route says about itself — the order, the names,
        how far into the walk each point comes — and the stage files, because
        writing one changes nothing. A read-only input is not the answer: it
        still looks like something to type into, so a stage nobody can rename is
        written as text."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()
        assert "var editable = on;" in html
        assert "row.draggable = editable;" in html
        assert "'display:' + (editable ? '' : 'none');" in html
        assert "if (!editable) { return; }" in html
        # The stage keeps its name and its file, and loses its caret.
        assert "named.textContent = stage.name || stageName(stage);" in html
        assert "head.appendChild(file);" in html

    def test_the_highlight_can_be_told_a_tap_was_not_its_own(self):
        """The panel takes a tap in reach of a planned route for the route, and
        the line under that route must not light up as well — but both handlers
        are on the same click and this one runs second, so clearing from over
        there was undone half a millisecond later. Measured: the trail stayed
        widened with the route on the panel.

        Held for the turn of the loop the click is in, which is what makes it a
        statement about *this* tap rather than a mode."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = folium.FeatureGroup(name="Trails").add_to(fmap)
        maps.add_click_highlight(fmap, [group])

        html = fmap.get_root().render()
        assert "function hold() {" in html
        assert "window.setTimeout(function () { held = false; }, 0);" in html
        assert "if (held) { return; }" in html
        assert "hold: hold," in html

    def test_a_row_can_be_dragged_to_any_place_in_the_route(self):
        """A splice and not a run of swaps: a swap is a full re-route of the two
        legs it touches, so dragging a point four places would route eight legs
        to arrive at the two that changed -- and dropping a row between two
        others means taking it out and putting it back in, where a run of swaps
        would drag every point it passed one place the other way.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        assert "function moveTo(at, to) {" in html
        assert "points.splice(to, 0, points.splice(at, 1)[0]);" in html
        assert "row.draggable = editable;" in html
        # Firefox starts no drag at all without something in the transfer.
        assert "event.dataTransfer.setData('text/plain', String(index));" in html
        assert "if (from !== null && from !== index) { moveTo(from, index); }" in html

    def test_the_list_is_not_rebuilt_under_a_row_in_the_air(self):
        """A leg settling mid-drag would rebuild the rows under the pointer and
        the drop would land on nothing."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        # And never under a name being typed, which is the same rule for the
        # same reason: measured, typing a stage name and letting a point settle
        # rebuilt the heading and threw the half-typed name away with it.
        assert "if (heldRow !== null || namingRow !== null) { return; }" in html

    def test_the_list_keeps_inside_the_room_the_profile_leaves_it(self):
        """The profile panel is anchored to the foot of the map, takes its full
        width and is the reader's own to drag taller. Measured, twelve points
        with the profile pulled to 725 px put 315 px of this control underneath
        it, and the two corners share a z-index so whichever is written later
        wins. So this asks what is left rather than fighting over it.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        assert "function roomAbove() {" in html
        assert "document.querySelector('.trails-profile-panel')" in html
        assert "map.on('resize', fitList);" in html
        # The panel's height is a reader's to drag and nothing announces that.
        assert "new ResizeObserver(fitList).observe(watched);" in html
        # Off the scroll height, not the offset: the box is capped below, so its
        # offset height is the cap and subtracting the list would measure the cap.
        assert "var fixed = box.scrollHeight - listBox.offsetHeight;" in html

    def test_the_list_is_named_so_it_can_be_found(self):
        """Its height is computed, so nothing can find it by the cap it carried."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        assert "listBox.className = 'trails-plan-points';" in fmap.get_root().render()

    def test_the_points_a_reader_put_down_are_recorded_as_the_walk_happens(self):
        """A crossing contributes no walking distance and a leg still being
        worked out contributes none either, so a sum over the legs' own lengths
        would put every later point too far along. Leg i runs from point i to
        point i + 1, so the distance at the head of leg i is point i's.
        """
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()

        assert "var stations = [];" in html
        assert "stations.push(walked);\n                    if (!leg.parts)" in html
        # One per point and never one per leg: with nothing down there is
        # nothing to mark, and the guard is what says so. A range of one leg has
        # two stations, which is the same rule counted from the other end.
        assert "if (last > first || points.length) { stations.push(walked); }" in html
        assert "stations: shape.stations," in html

    def test_a_waypoint_is_a_marker_because_a_circle_cannot_be_dragged(self):
        """198 markers and 13 plan-pane paths were both acceptance figures, and
        phase 7 moves them on purpose. Measured in the built page: a
        ``circleMarker`` added to the map has no ``dragging`` at all and
        ``draggable: true`` on one is silently ignored, while an ``L.marker``
        gets a live handler and lands in the marker pane. So a draggable
        waypoint is a marker — 198 becomes 203 — and it draws no path, so the
        plan pane's 13 becomes 8."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "L.marker(" in planning
        assert "L.circleMarker(" not in planning
        # A div rather than an image, so the number is the element's own text
        # and selecting one is a single attribute rather than a second layer.
        assert "L.divIcon({className: 'trails-plan-pin'" in planning
        assert "draggable: true" in planning

    def test_a_pin_is_dead_to_the_pointer_out_of_plan_mode(self):
        """A pin has to catch clicks to be selected and dragged, and everything
        this page draws over the trails is otherwise deliberately not a click
        target: the park boundary swallowing every click inside it cost a
        fortnight. So the pointer events go off with plan mode, and dragging
        with them."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "element.style.pointerEvents = on ? 'auto' : 'none';" in planning
        assert "record.marker.dragging.enable(); } else { record.marker.dragging.disable();" in planning

    def test_a_crossing_keeps_the_ground_it_covers(self):
        """A crossing writes no track points -- GPX cannot say a segment is a
        boat -- but a routed ferry carries N50's own line and a water leg the
        reader's two points, so where it crosses a boundary is as computable as
        anywhere. It used to be dropped along with the points, and every
        boundary crossed inside a break was lost with it."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned(), [])

        html = fmap.get_root().render()
        assert "gaps.push({before: stretches.length, lon: part.lon, lat: part.lat});" in html
        assert "stations: stations, gaps: gaps," in html

    def test_the_named_points_reach_the_page_as_a_table(self):
        """A waypoint set beside a hut can only be called after it if the page
        holds a table of what is where. 1,411 circle markers and 865 markers
        keep their names as one unlabelled entry in the popup values they carry,
        which is not a lookup."""
        fmap, _ = self.drawn()
        huts = gpd.GeoDataFrame({"name": ["Lavasshytta"], "geometry": [Point(12.98079, 65.77416)]}, crs="EPSG:4326")
        layer = maps.add_points(fmap, huts, name="Huts", point_type="hut")
        maps.add_plan_mode(fmap, self.planned(), [layer])

        planning = fmap.get_root().render().split("var NAMED =")[-1]
        assert '"name": "Lavasshytta"' in planning or '"name":"Lavasshytta"' in planning
        assert '"type": "hut"' in planning or '"type":"hut"' in planning

    def test_a_name_carrying_a_script_tag_cannot_close_the_block(self):
        """Every one of these is a name out of somebody else's register, and
        json.dumps does not escape '<'."""
        fmap, _ = self.drawn()
        nasty = gpd.GeoDataFrame({"name": ["</script><script>alert(1)</script>"], "geometry": [Point(12.98, 65.77)]}, crs="EPSG:4326")
        layer = maps.add_points(fmap, nasty, name="Huts", point_type="hut")
        maps.add_plan_mode(fmap, self.planned(), [layer])

        planning = fmap.get_root().render().split("var NAMED =")[-1]
        assert "</script><script>" not in planning.split("})();")[0]

    def test_without_a_table_a_waypoint_is_numbered(self):
        """Which is what it did before this existed."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var NAMED =")[-1]
        assert planning.lstrip().startswith("[]")

    def test_the_threshold_is_applied_once_and_carried_rather_than_spelled(self):
        """A rounded label is a threshold and so is a reported one. Applied in
        two places it becomes two thresholds, and the sentence above the button
        would name areas the file's markers do not."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned(touchedM=250.0))

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert planning.count("PLAN.touchedM") == 1
        assert "250" in fmap.get_root().render()

    def test_what_protects_the_ground_is_summed_per_edge_like_the_rest(self):
        """A part keeps its geometry and its heights and nothing downstream can
        get back to the edge a metre came from."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "graph.protectedAt[edge]" in planning
        assert "graph.protectedShare[p] * metres" in planning

    def test_a_crossing_is_asked_nothing_about_what_protects_it(self):
        """There is no walking distance under a ferry, so there is no protected
        walking distance either."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "if (source.kind !== CROSSING) { addProtected(out, graph, edge, metres); }" in planning

    def test_a_connector_is_asked(self):
        """Nobody drew it, but a walker covers its ground and that ground lies
        inside a boundary or outside it — so the protected question is put
        before the connector is taken out of the other two."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        protecting = planning.index("addProtected(out, graph, edge, metres)")
        connector = planning.index("if (source.kind === CONNECTOR) { out.undrawn += metres; return; }")
        assert protecting < connector

    def test_a_leg_drawn_straight_reads_its_areas_off_its_own_samples(self):
        """The page has one protected area of the nineteen drawn and the height
        service answers ground cover, not protection — so the boundaries have to
        be carried, and a straight leg is decided at the samples it fetched."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "graph.areasAt(laid.lon[s], laid.lat[s])" in planning

    def test_a_leg_drawn_straight_asks_the_water_grid_what_is_water(self):
        """The regression the first Lomsdal-Visten drive found (§6.10): the runs
        were split on `points[i].sea`, which only ever had a value because the
        point service answered `terreng: Havflate`. Both maps read height tiles
        now, and a tile reader pushes `sea: false` for every sample -- correctly,
        there is no sea in a model of the ground -- so a leg over Vistenfjorden
        came back as 0.00 km of water and a profile along the bottom of it. The
        grid is what the router already prices the leg by, it holds lakes too,
        and it answers offline. The service's flag stays honoured beside it."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        parts = planning.split("function straightParts(")[1].split("\n            function ")[0]
        assert "wet[w] = !!points[w].sea" in parts
        assert "|| (!!graph.waterAt(laid.lon[w], laid.lat[w])" in parts
        # And a river is waded, not crossed: Lantmateriet draws a wide
        # watercourse as a water surface, so the grid alone cut the leg at
        # Abiskojakka's bank and the width sentence then measured the truncated
        # run -- 14 m where the outline says 22.
        assert "&& !graph.riverAt(laid.lon[w], laid.lat[w]).length);" in parts
        # And the runs are cut from that reading, not from the flag again.
        assert "if (wet[i] !== wet[i - 1]) { changes.push(i); }" in parts
        assert "if (wet[first]) {" in parts
        assert "points[first].sea" not in parts

    def test_the_wheel_still_reaches_the_map(self):
        """disableClickPropagation, and deliberately not the scroll one: a
        control that swallows the wheel reads as a map that has frozen."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "disableClickPropagation" in planning
        assert "disableScrollPropagation" not in planning

    def test_the_only_address_it_carries_is_the_height_service(self):
        """A routing library from a CDN does not load on a file:// page: it
        fails silently, the way the OpenStreetMap tiles once did. The one
        address here is the service a leg drawn straight asks for its heights,
        and it is asked when a reader draws one, not when the page loads."""
        fmap, _ = self.drawn()
        bare = fmap.get_root().render().count("://")

        maps.add_plan_mode(fmap, self.planned())
        planning = fmap.get_root().render()
        # Two, since phase 8: the height service, and the namespace a file this
        # map wrote puts its extensions in. **A namespace is an identifier and
        # never fetched** — it is compared against, which is the whole reason
        # the reader addresses elements by it rather than by their prefix.
        assert planning.count("://") == bare + 2
        # Two fetches, both asked when a reader draws a straight leg and never
        # on load: the service, and the height tiles a map without a service
        # reads instead -- through the worker, from our own bucket.
        assert planning.count("fetch(") == 2
        assert "getElementsByTagNameNS(PLAN.gpx.namespace" in planning

    def test_the_cost_comes_out_of_the_header(self):
        """Length times the source's factor, and a crossing at the header's flat
        figure. A cost column in the payload is the thing the encoder
        deliberately left out, and a second table here would be the same
        mistake wearing a different hat."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "graph.header.sources[graph.sources[i]]" in planning
        assert "cost[i] = length[i] * source.factor" in planning
        assert "source.flatM" in planning

    def test_it_lays_its_route_out_with_the_panel_s_own_walk(self):
        """Two walks laying edges end to end would eventually disagree, and a
        route composed by the wrong one still looks like a route. The Python
        side keeps its one in trails.routing.order for the same reason."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "panel().layEdges(" in planning
        assert "function layEdges(" not in planning
        assert "panel().metresBetween" in planning

    def test_every_walk_over_the_graph_is_bounded_and_throws(self):
        """An unbounded walk that appends is what a defect here looks like from
        the outside: not an error but a page that has hung. The Python sibling
        of the back-walk, written without a bound, took 42 GB before the kernel
        stopped it."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "pops > mostPops" in planning
        assert "steps > graph.header.edges" in planning
        assert planning.count("throw new Error(") >= 3

    def test_the_sentinel_is_tested_for_and_never_indexed_with(self):
        """A typed array answers a negative index with undefined rather than
        raising, so an unset predecessor would put undefined into the geometry
        and carry on."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "while (viaEdge[walk] >= 0) {" in planning
        assert "if (before < 0) { throw new Error('node ' + walk + ' was reached by nothing'); }" in planning
        # Which way round an edge is walked comes off the predecessor, not off
        # the edge's own ends: fourteen edges in this graph begin and end at the
        # same node and say nothing about direction.
        assert "graph.fromNode[used] !== before" in planning

    def test_a_crossing_carries_no_profile(self):
        """Not a flat line at zero, which is a claim about ground that is not
        there. The same rule a ferry chain follows in the panel."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "kind: CROSSING" in planning
        assert "kind: 'water'" in planning
        # Both are written with no series at all rather than with an empty one.
        assert planning.count("height: null, distance: null, read: false") == 2

    def test_the_kinds_it_classifies_by_come_from_the_build(self):
        """A ferry and an inferred connector are named in
        :mod:`trails.routing.sources`, and the page tests every edge it routes
        over against both names. Spelled in the page, a rename there would leave
        it counting a crossing as walked ground and nothing would look wrong."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned(crossingKind=FERRY, connectorKind=BRIDGE))

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "var CROSSING = PLAN.crossingKind, CONNECTOR = PLAN.connectorKind;" in planning
        assert f'"crossingKind": "{FERRY}"' in fmap.get_root().render()
        assert f'"connectorKind": "{BRIDGE}"' in fmap.get_root().render()

    def test_the_route_is_laid_out_in_one_walk_and_not_two(self):
        """The profile is drawn from heights against distance and the file is
        written from vertices, and two walks over one route would eventually
        disagree while each still looked like a route."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        # One walk, which a stage narrows rather than repeats: a second walk
        # over a range would be the same failure at a smaller scale.
        assert planning.count("function composeRoute(fromLeg, toLeg, over)") == 1
        # The shape a chain's series has, which is what the writer reads.
        for field in ("lon:", "lat:", "along:", "height:", "distance:", "stretches:"):
            assert field in planning.split("function composeRoute(fromLeg, toLeg, over)")[-1], field

    def test_a_crossing_ends_a_stretch_and_an_unread_sample_does_not(self):
        """The two kinds of NaN mean opposite things: no ground under a
        crossing, against ground with no reading of it. The first has to break
        the track and the second may only drop an ``<ele>``, so the boundary is
        recorded where it happens rather than inferred from a repeated
        distance."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function breakHere()" in planning
        # A crossing closes the stretch; a NaN height inside one is only a NaN.
        assert "crossed += part.length;" in planning
        assert "breakHere();" in planning

    def test_what_a_route_is_made_of_is_summed_per_edge(self):
        """A part keeps its geometry and its heights, and nothing downstream can
        get back to which edge a metre came from."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function tallyOf(graph, list)" in planning
        assert "graph.header.waymarked[graph.waymarked[edge]]" in planning
        assert "graph.noPathRecorded[edge]" in planning

    def test_unknown_is_never_folded_into_unmarked(self):
        """Measured over the walked network without its connectors, 63.4 % of
        the length is unknown and FKB — the largest source at 33.8 % — carries
        no marking field at all. Calling that unmarked asserts what no source
        says, and a connector nobody drew was never asked at all."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "var MARKING = ['marked', 'unmarked', 'unknown'];" in planning
        assert "var TALLIED = MARKING.concat(['undrawn', 'recorded', 'unrecorded']);" in planning
        # And the fifth, which phase 8 adds beside `undrawn` and for the same
        # reason: no register was asked about ground read off a loaded file.
        assert "tally.recorded = run;" in planning
        # A state the payload names and this page has no bucket for is a defect,
        # not a fourth silent bucket created by an index into an object.
        assert "the payload names a marking state this page has no bucket for" in planning

    def test_the_four_kinds_are_all_there_from_the_first_line(self):
        """A model that knew only routed legs would have to be widened the first
        time a ferry or a strait turned up, and both turn up here."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        for kind in ("routed", "land", "water", "ferry"):
            assert f"{kind}:" in planning or f"'{kind}'" in planning, kind

    def test_a_crossing_is_priced_as_a_whole_crossing(self):
        """Noding cuts a ferry wherever something meets it: 15 of the 21 ferry
        chains here are in several pieces and the longest is in seven. Charging
        the flat figure per edge priced that one at 35 km of walking instead of
        5, and a page that does so refuses crossings the build called
        affordable. trails.routing.graph._cost splits it the same way."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "source.flatM * (whole[i] > 0 ? length[i] / whole[i] : 1)" in planning

    def test_a_leg_drawn_straight_has_a_stated_ceiling(self):
        """Sampling is fixed at the build's step, so the only way to bound what
        one misclick asks of a public service is to bound the leg — and to say
        so, because coarsening instead would make the two halves of one profile
        answer differently with nothing looking wrong."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "length > PLAN.maxStraightM" in planning
        assert "is further than a leg may be drawn straight" in planning

    def test_one_refused_batch_stops_the_rest(self):
        """Once a leg has given up there is nothing left to use, and a page that
        carries on fetching the remainder is the opposite of the restraint the
        concurrency is set for."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "if (stopped || next >= batches.length)" in planning

    def test_the_legs_follow_from_the_waypoints_rather_than_being_edited(self):
        """Four edits and one rule. A leg survives exactly when it still runs
        between the same two waypoint objects, so inserting costs the two legs
        that replace one, removing costs the one that replaces two, and moving a
        point costs the three that touch it — and nothing has to work out which
        legs an edit invalidated, which is the arithmetic all four would
        otherwise get wrong in four different ways."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function relink(graph, mayAsk)" in planning
        assert "kept[k].from === points[i] && kept[k].to === points[i + 1]" in planning
        for edit in ("function insert(at, lat, lon, trackAt)", "function remove(at)", "function moveBy(at, step)"):
            assert edit in planning, edit
        # And a waypoint that has moved is a new object, so a drag needs no
        # case of its own in the rule above.
        assert "points[dragging.at] = snapped(held, where.lat, where.lng, fingerReach(where.lat));" in planning

    def test_a_reply_about_ground_a_waypoint_has_left_is_dropped(self):
        """The whole of the cancellation, and it has to be: a drag settles eight
        times a second and every settle replaces the legs beside the point. A
        leg drawn from an answer that is no longer wanted is a route that
        disagrees with its own waypoints."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "if (legs.indexOf(leg) < 0) { return; }" in planning

    def test_a_live_drag_asks_the_height_service_for_nothing(self):
        """The cache is keyed on ends already visited and the ground under a
        dragged waypoint is new at every position, so a free leg fetched per
        mouse move is an uncapped stream of requests to somebody else's service
        — the shape 6B's review already found once and capped at 20 km. The leg
        is carried at its own straight length instead, and counts as unsettled
        so no file is written from it."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function heightsFor(from, to, mayAsk)" in planning
        assert "if (!mayAsk) { return null; }" in planning
        assert "relink(held, false);" in planning
        assert "function waitingParts(from, to)" in planning
        assert "provisional: true" in planning
        assert "return leg.provisional || (!leg.parts && !leg.failed);" in planning

    def test_a_drag_is_throttled_and_settles_where_the_pointer_stopped(self):
        """Placing a point costs 19-76 ms with its Dijkstra, so two legs is 40
        to 160 ms; run at the rate a pointer reports, that is three of them
        queued per frame. There was no throttle anywhere in plan mode before
        this — the only setTimeout near it was the search box's."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "var DRAG_EVERY_MS = 120;" in planning
        # A trailing settle, or the position the hand came to rest at is never
        # the one the route is worked out from.
        assert "dragging.timer = setTimeout(" in planning
        assert "clearTimeout(dragging.timer)" in planning

    def test_the_free_leg_cache_is_keyed_on_the_pair_and_bounded(self):
        """Moving a point one place past its neighbour turns exactly one leg
        round, so a cache that told A-to-B from B-to-A would fetch ground the
        page is already holding. And a drag leaves one leg's samples behind
        every time the pointer is let go, which is what a cache kept for the
        life of the page could not do before."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function forwards(from, to) { return endKey(from) <= endKey(to); }" in planning
        assert "function mirrored(answered)" in planning
        assert "var ASKED_MOST = 64;" in planning
        assert "while (askedKeys.length > ASKED_MOST) { delete asked[askedKeys.shift()]; }" in planning

    def test_a_click_on_the_route_is_hit_tested_and_never_caught(self):
        """An interactive route would have to stop catching clicks the moment
        plan mode is switched off, or it would stand between a reader and the
        trail underneath it — the mistake the park boundary made for a
        fortnight. The leg a click landed on is found in the geometry the page
        already holds instead, in the one handler every click goes through."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "pane.style.pointerEvents = 'none';" in planning
        # Two now and not one: the goal's way is drawn by the same function
        # into a pane of its own, and neither line is ever a click target.
        # Three now: the plan's own route, the way to a goal, and the stops on
        # the way to one. None of them is ever a click target.
        assert planning.count("interactive: false") == 3
        assert "function onRoute(lat, lon, withinPx)" in planning
        # Two reaches for two questions: aiming a point into a leg is the
        # tighter one, and whether a tap *meant* the route is asked at the same
        # distance as every other line under the finger.
        assert "var reach = withinPx || ON_ROUTE_PX;" in planning
        assert "var ON_ROUTE_PX = 8;" in planning
        # Pin, then route, then a point on the end: a pin sits on the route.
        decided = planning.split("container.addEventListener('click'")[-1]
        assert decided.index("closest('.trails-plan-pin')") < decided.index("onRoute(where.lat")
        assert decided.index("onRoute(where.lat") < decided.index("place(where.lat")

    def test_a_click_on_a_pin_selects_it_rather_than_deleting_it(self):
        """The same click is a few pixels from one that places a point and
        there is no way back from a deletion. What a selection makes possible
        has to be visible anyway: dragging a pin says nothing about where it
        comes in the sequence, so reordering needs a gesture of its own."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "chosen = chosen === at ? -1 : at;" in planning
        assert "moveBy(chosen, -1)" in planning and "moveBy(chosen, 1)" in planning
        assert "remove(chosen)" in planning

    def test_the_pins_are_written_as_differences(self):
        """Rebuilding a layer per keystroke and writing a style already set have
        each frozen this map on their own, and a drag does it several times a
        second. What was written is kept beside the pin rather than read back:
        an element answers 'rgb(17, 17, 17)' to a '#111111' just set to it."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "if (element && record.label !== label)" in planning
        # Whether it is picked and whether it ends a stage, both compared
        # against what was last written rather than read back off the element:
        # a style set to '#111111' reads back as 'rgb(17, 17, 17)'.
        assert "if (element && (record.picked !== picked || record.ends !== ends))" in planning
        # And the marker under the pointer is never written back to, or it
        # fights the hand moving it.
        assert "if (dragging && dragging.at === i) { continue; }" in planning

    def test_a_plan_is_kept_as_the_file_the_page_already_writes(self):
        """A reload threw the plan away, which is the one thing a reader cannot
        get back by clicking again. What is kept is the GPX the download button
        offers and it comes back through the picker's own reader — a shorter
        payload of its own would be a second recording of one decision, which is
        how the file name, the mode wording and the ascent all came apart."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "var made = panel().routeFile(figuresOf(shape), shape, told(shape), plan);" in planning
        assert "window.localStorage.setItem(keptKey(), made.text);" in planning
        assert "loadGpx(text, 'asis');" in planning

    def test_the_key_outlives_a_build(self):
        """folium hashes the container's id afresh every time the page is
        written, so a plan keyed on that would be thrown away on every deploy —
        the one moment a reader would least expect to lose something."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "return 'trails.plan.' + (prefix || 'map');" in planning
        assert "var prefix = panel() ? panel().prefix() : null;" in planning

    def test_a_full_quota_is_said_and_not_swallowed(self):
        """A reader who believes their plan is being kept and finds it gone is
        worse off than one who was told it is too large to keep."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "refused.name === 'QuotaExceededError'" in planning
        assert "too large to keep in this browser" in planning
        # And a payload that cannot be read is let go of once, or the page fails
        # the same way on every load with no way for a reader to clear it.
        assert "could not be read, so it has been let go." in planning

    def test_the_plan_is_written_when_the_editing_stops_and_when_the_tab_goes(self):
        """A drag refreshes at the rate the pointer reports, and a phone closes
        tabs without asking — iOS delivers no beforeunload at all."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "keptWhen = setTimeout(writeKept, KEEP_AFTER_MS);" in planning
        assert "window.addEventListener('pagehide'" in planning

    def test_the_whole_tour_is_offered_where_the_route_is_made(self):
        """The panel over the profile writes exactly this file and has always
        offered it — but on a narrow screen that panel is not on the screen by
        default, so a reader planning on a phone had no way to the one file they
        came for. One writer asked from three places: this button, the profile's
        own, and the archive's tour member."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "oneFile.textContent = 'Whole tour (GPX)';" in planning
        assert "var made = writer(figuresOf(shape), shape, told(shape), writable());" in planning
        assert "var writer = garmin ? panel().garminFile : panel().routeFile;" in planning
        # Why it is refused, where it is: 'still working out 2 legs' is the
        # difference between a button that is waiting and one that is broken.
        assert "oneFile.title = refusing ||" in planning

    def test_a_plan_that_comes_back_on_its_own_has_a_way_out(self):
        """A kept plan is restored on every load until there is nothing left to
        restore, and emptying a twenty-point route a point at a time is not a
        way out. It goes through the same edit funnel as every other change, so
        undo brings it back — which is what makes a button that clears the map
        safe to offer."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "asTool(fresh, 'again', 'Start again" in planning
        assert "points.length = 0;" in planning
        # The recording goes with it: a waypoint anchored to a file nobody is
        # working from is a point looked up in the wrong track.
        assert "loaded = null;" in planning

    def test_the_list_is_capped_by_the_room_and_not_by_a_constant(self):
        """It was 220 px whatever the screen: a twelve-point route scrolled
        inside a panel with 350 px of room under it, and running off the end of
        that scroller is what handed the wheel to the map."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "listBox.style.maxHeight = Math.max(40, room - fixed) + 'px';" in planning

    def test_a_wheel_over_a_panel_does_not_end_in_a_zoom(self):
        """Each scroller inside takes what it can use and the outermost panel
        swallows the rest. Where the chrome holds this control the chrome is that
        boundary; where there is none, this box is."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "if (!box.closest || !box.closest('.trails-chrome')) { event.stopPropagation(); }" in planning

    def test_a_row_says_what_the_walk_into_it_is_made_of(self):
        """It said the point's own coordinates — sixteen characters answering a
        question nobody asks of a list. Measured on a seven-point route in this
        park, seven of seven rows said a coordinate, because out here there is
        rarely anything named within reach."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function groundInto(index)" in planning
        assert "return 'over a crossing';" in planning
        assert "return 'along a path';" in planning
        # The coordinate is kept, in the row's own menu: occasionally exactly
        # what somebody wants, and usually not.
        assert "where.textContent = point.lat.toFixed(4) + ', ' + point.lon.toFixed(4);" in planning

    def test_everything_a_row_can_do_is_in_one_menu(self):
        """Four unlabelled marks — an em dash that cut a stage, a cross that
        removed a point, two arrows that only appeared under a coarse pointer —
        plus a box of edits that showed up when a point was picked and was empty
        the rest of the time."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "menu.className = 'trails-plan-rowmenu';" in planning
        assert "more.className = 'trails-plan-more';" in planning
        # In the row and not over it: floated above, the list's own scroller cut
        # it off on every row near the foot.
        assert "menu.style.cssText = 'display:none;width:100%;" in planning

    def test_one_word_and_the_rest_are_marks(self):
        """The word that is kept is the one that ends the work; the rest are
        tools and carry marks, with a title and an aria-label, exactly as the
        rail beside them does."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "toggle.textContent = on ? 'Done' : 'Plan a route';" in planning
        assert "function asTool(button, name, explains)" in planning
        assert "button.setAttribute('aria-label', explains);" in planning
        assert "tools.className = 'trails-plan-tools';" in planning

    def test_the_description_is_behind_the_mark_and_is_its_own_sentence(self):
        """Glued in front of the file's description it read "…kept in this
        browser only. a route this map wrote: …" — a lower-case word after a full
        stop, which is what gluing two sentences written apart always gives."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "loadDetail = describeFile(loaded);" in planning
        assert "loadSaid = 'Back as you left it.';" in planning
        assert "window.trailsChrome.detail('This route', told, 'plan');" in planning

    def test_a_height_request_that_never_answers_is_given_up_on(self):
        """`fetch` has no deadline of its own: a server that accepts a connection
        and then says nothing leaves a promise that neither resolves nor rejects.
        The retry below it never sees a refusal to retry, the leg stays
        outstanding, and plan mode says *working…* with nothing left that will
        ever finish it — reported from the map, and reproduced on the build
        before it.

        Aborted rather than merely raced, so the connection goes with the wait: a
        page that gave up on the answer and left the socket open would be leaning
        on somebody else's service on the way out."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()
        assert "var stop = window.AbortController ? new AbortController() : null;" in html
        assert "window.setTimeout(function () { stop.abort(); }, PLAN.heightsTimeoutMs)" in html
        # Let go of only when the whole exchange is over, body and all: a header
        # that arrives and a body that never finishes is the same hang one step
        # later.
        assert "return asking.then(function (answers) {" in html
        assert "throw new Error('the height model did not answer within '" in html
        # And what it becomes is a refusal like any other, which the retry and
        # then the leg already know how to say.
        assert "if (attempt >= ATTEMPTS) { throw failure; }" in html

    def test_a_page_without_a_panel_says_so_rather_than_throwing(self):
        """Plan mode composes with the walk the panel owns, so a page carrying
        one and not the other can plan nothing — said once, loudly."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()
        assert "console.error('plan mode: there is no profile panel" in html

    def test_the_route_hands_out_segments_rather_than_its_shape(self):
        """``geometry()`` hands the whole shape back as two arrays and
        ``state()`` composes the route to answer anything at all — 45 ms over a
        37 km one. A mark worked out on every fix can afford neither, and it
        does not want the shape: it wants to measure one point against every
        segment and keep three numbers.

        Every segment says which leg it came from, which is what lets the caller
        ask for *the next waypoint ahead* without knowing anything about how a
        route is put together."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()
        assert "function eachSegment(visit) {" in html
        assert "visit(part.lat[v], part.lon[v], part.lat[v + 1], part.lon[v + 1], i);" in html
        assert "segments: eachSegment," in html
        assert "goal: placeAt," in html
        # Every waypoint is a goal, because the bends between them belong to the
        # router: the points are exactly the places the reader chose.
        assert "function placeAt(leg, forward) {" in html
        assert "name: said.name || ('Waypoint ' + said.number)};" in html

    def test_a_goal_lives_where_the_router_does(self):
        """A goal is not a plan — a plan is a tour made beforehand, at a table,
        and a goal is a point set while walking — but the router, the graph and
        the snapping are all in this control, and a second copy of any of them
        would be a second answer to the same question.

        Its own pane over the planned route, because a goal is the more
        particular of the two and the one the reader set last; and its line
        takes no clicks, for the reason the plan's own does not."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "window.trailsGoal = {" in planning
        assert "createPane('trailsGoalRoute')" in planning
        assert "made.style.zIndex = 462;" in planning
        assert "made.style.pointerEvents = 'none';" in planning
        # Composed by the same walk that composes the plan's own route: the
        # heights laid end to end, the holes left as holes, the crossings
        # counted. Two walks would give two answers to *how far and how high*.
        # Composed over the legs of the chain — one where the goal stands
        # alone, one more for every stop the reader put on the way.
        assert "? composeRoute(null, null, legs) : null;" in planning
        assert "draw(leg.parts, leg.provisional, {pane: goalPane(), colour: GOAL_COLOUR})" in planning

    def test_the_way_to_a_goal_becomes_the_plan_s_points(self):
        """Asked for from the phone. A goal is set in a moment and walked at
        once; a plan is edited, cut into stages and written to a file -- and a
        goal with three stops on the way is already the thing a plan is for.

        Here rather than in the panel that offers it, because both halves of it
        are here: the goal and the plan share this closure. The reader's own
        position goes in front where the page knows it, and the goal goes with
        the conversion -- two routes over the same places, one editable and one
        not, is a page that cannot say which is being walked."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()
        made = html[html.index("function planFromGoal() {") : html.index("// **Inserting is this phase")]
        assert "var here = goalHere();" in made
        assert "places.unshift({lat: here.lat, lon: here.lon});" in made
        assert "planFromPlaces(places);" in made
        assert "clearGoal();" in made
        # Asked only where there is something to lose.
        assert "if (points.length && !window.confirm('Replace the '" in made
        assert "fromGoal: planFromGoal," in html

    def test_a_plan_can_be_made_of_places_somebody_already_put_down(self):
        """The other half of turning a goal into a plan: the places arrive as
        they were put down and are not snapped a second time -- each was already
        laid on the line under a finger, or typed exactly -- and plan mode comes
        on with them, the way it does for a loaded file."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()
        made = html[html.index("function planFromPlaces(places) {") : html.index("// **Inserting is this phase")]
        assert "snapped(graph, each.lat, each.lon, SAME_SPOT_M)" in made
        assert "if (!on) { switchTo(true); }" in made
        # Nothing a loaded file left behind survives the route it described.
        assert "loaded = null;" in made
        assert "fromPlaces: planFromPlaces," in html

    def test_a_goal_is_routed_from_where_the_reader_is(self):
        """Not from where the goal was set and not from the goal outwards: a way
        to somewhere starts where you are. Which means it goes stale as the
        reader walks — so it is worked out again once they have *left* it, and
        their own circle is part of how far off they look, because a fix that is
        40 m vague reads as 40 m off a line it is standing on.

        And at most every half minute. A fix arrives about once a second and
        each route is a search over the network; a line rebuilt whenever the fix
        shivered would shiver with it, and the distance left would stop counting
        down and start jittering."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "var GOAL_ASTRAY_M = 50;" in planning
        assert "var GOAL_ASTRAY_SPREADS = 3;" in planning
        assert "var GOAL_AGAIN_MS = 30000;" in planning
        assert "if (Date.now() - goalWhen < GOAL_AGAIN_MS) { return false; }" in planning
        assert "var astray = Math.max(GOAL_ASTRAY_M, GOAL_ASTRAY_SPREADS * (spread || 0));" in planning
        assert "return away > astray ? goalAgain({lat: lat, lon: lon}) : false;" in planning
        # Where the reader is, asked of the one thing that knows — and it is the
        # figure the ring is drawn at, which is not always the last fix.
        assert "window.trailsChrome.position()" in planning

    def test_a_reply_about_ground_the_reader_has_left_is_dropped(self):
        """One token and not a queue. A way worked out from where somebody stood
        two minutes ago is not a shorter answer to the same question, it is an
        answer to a question nobody asked — the same one line that cancels a
        plan's leg, for the same reason."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "goalToken = mine;" in planning
        # Once now and not three times: the legs are made together and the
        # token is looked at once, where the answer for the whole chain lands.
        assert planning.count("if (goalToken !== mine) { return; }") == 1

    def test_a_goal_is_kept_in_a_key_of_its_own(self):
        """A reader sets one in a hut with a signal and reads it in the fog an
        hour later, by which time the tab has been thrown away and rebuilt at
        least once. Its own key beside the plan's, so restoring one cannot touch
        the other — and after the graph, because a routed goal is routed on the
        way in."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function goalKeptKey() { return keptKey() + '.goal'; }" in planning
        assert "window.trailsGraph.ready.then(function () { restoreKept(); restoreGoal(); }," in planning
        # A goal that is not there is not a goal stored as null: the entry goes.
        assert "if (!goalAt) { window.localStorage.removeItem(goalKeptKey()); return; }" in planning

    def test_a_goal_takes_the_name_the_map_already_gives_the_ground(self):
        """A waypoint standing beside a hut takes the hut's name and the hut's
        position; a goal set by tapping one is the same question asked by
        somebody else, and two answers to it would differ the day the register
        does. So the chrome asks this control rather than carrying its own
        table."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "named: function (lat, lon) {" in planning
        # At the reach a finger covers, held at `namedM` where a finger is
        # wider: a goal set beside a hut used to become the hut from 50 m away
        # however far in the reader had pinched, and there was no zoom at which
        # it did not. Narrowing only — the figure is the build's judgement about
        # naming, and nothing here widens it.
        assert "var said = nameOf({lat: lat, lon: lon}, 0, namedReach(lat));" in planning
        assert "function namedReach(lat) {" in planning
        assert "return Math.min(PLAN.namedM, fingerReach(lat));" in planning
        # **A number or nothing, and `undefined` is not the test.** `nameOf` is
        # handed to `Array.prototype.map` in two places, which calls it with the
        # value, the index and *the array* — so the day a third parameter was
        # added, `closest > []` coerced to `closest > NaN`, the reach rejected
        # nothing, and every waypoint in every file was named after the nearest
        # thing at any distance: *Steinbua, Tosenfjellet* 2,419 m away, *Gamme*
        # 9,196 m away, measured in the file it wrote. Belt and braces both.
        assert "var reach = typeof within === 'number' ? within : PLAN.namedM;" in planning
        assert "points.map(function (point, at) { return nameOf(point, at); })" in planning
        assert ".map(nameOf)" not in planning
        # And a waypoint already down is named without asking the screen, or the
        # list would say a different word every time the reader pinched and the
        # file a different one again.
        assert "var said = nameOf(points[at], at);" in planning
        assert "var called = nameOf(point, index);" in planning

    def test_the_plan_does_not_take_the_panel_back_from_a_goal(self):
        """Two composed routes can be offered and the panel is one panel. A
        refresh of the plan is still a refresh — the list, the bar, the figures
        — but it is not a reason to take the panel from a route the reader
        chose. Plan mode being switched *on* is: there the panel is what
        planning is read in."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function feedPanel(spec) {" in planning
        assert "if (goalShowing && !on) { return; }" in planning
        assert "if (on) { goalShowing = false; }" in planning
        # And nothing feeds the panel round it.
        assert "showing.series(" not in planning.split("function present() {")[1].split("function switchTo")[0]

    def test_what_is_walkable_is_walked_and_only_the_rest_crossed(self):
        """Reported from the phone: a goal with no continuous way to it was
        answered with *there is no way there*. What happened underneath is that
        the fallback for an unroutable pair is one straight line from end to
        end, and a line that long is refused outright — so a journey that is
        twenty kilometres of path and two of open ground came out as nothing.

        The three pieces are assembled here and judged nowhere: what the reader
        walks to reach the network, the network, and what they walk at the far
        end. Either walk is left out where it has no length, and the whole of
        *whether this was worth doing* is settled before it is asked for — see
        :meth:`test_a_point_off_the_network_is_joined_to_it_not_moved_on_to_it`.

        Asked for by the goal and not by the plan: a plan's legs are what its
        file is written from, and changing what a leg is made of changes every
        figure and every file that comes out of one."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function partlyRouted(graph, from, to, joined, mayAsk) {" in planning
        assert "var middle = over ? routedParts(graph, over) : [];" in planning
        assert "return ends[0].concat(middle, ends[1]); });" in planning
        # **Both ends, and neither need be on a path.** The reader is as likely
        # to be off the network as the goal is — somebody standing in a bog is
        # exactly the person asking which way — and `snapped` gives up beyond
        # its own reach, which is right for placing a waypoint and wrong here.
        assert "var joined = joinedRoute(graph, from, to);" in planning
        # And the goal is the one caller that asks for it, with both of its ends
        # where the reader put them: a stop is a place the reader chose and
        # nothing may move it -- `placed` keeps the position and only asks
        # whether it already stands on the line.
        assert "return resolve(graph, placed(graph, head), placed(graph, tail), true, true);" in planning
        assert "return {lat: point.lat, lon: point.lon, node: at.node, edge: at.edge, along: at.along};" in planning

    def test_a_tap_snaps_to_the_line_it_lands_on(self):
        """At a fixed 150 m the same tap meant the same thing at every zoom.

        Pinched right in, with two paths drawn a finger apart on the screen, a
        waypoint put down on one of them could be taken as the other, and
        nothing about that looked wrong — the pin simply appeared on the wrong
        line. The further out the reader was the more nearly right the figure
        became, which is why it survived: 150 m is about a finger's width at
        z12 and a quarter of the screen at z16.

        A gesture now snaps within whichever is smaller, ``snapM`` or the halo
        every other line on this page is hit by, turned into metres at the zoom
        the reader is looking at::

            z12  191 m -> held at 150     z15   24 m
            z13   96 m                    z16   12 m
            z14   48 m                    z17    6 m

        **And a waypoint read out of a file does not ask the screen.** Whether
        a recorded point was on the network is a question about the ground and
        has to answer the same whatever the map happens to be showing, so the
        reach is handed in rather than looked up, and the file's callers leave
        it out."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function snapped(graph, lat, lon, within) {" in planning
        assert "var reach = within === undefined ? PLAN.snapM : within;" in planning
        assert "var node = graph.nearestNode(lat, lon, reach);" in planning
        # And the line itself, not only its junctions: see
        # test_a_tap_lands_on_the_line_and_not_only_on_its_junctions.
        assert "var line = nearestOnNetwork(graph, lat, lon, reach);" in planning
        assert "function fingerReach(lat) {" in planning
        assert "return Math.min(PLAN.snapM, across);" in planning
        # Every gesture asks the screen.
        # The finger is the default and a caller that is not one says so: a
        # place pressed on a page is where that place is.
        assert "points.push(snapped(graph, lat, lon, exact ? SAME_SPOT_M : fingerReach(lat)));" in planning
        assert "points[dragging.at] = snapped(held, where.lat, where.lng, fingerReach(where.lat));" in planning
        # And the file does not ask the screen — nor, restoring a plan, does it
        # move the point at all: a file says where the reader put one, and a leg
        # from a point off the network reaches it by a connector anyway. Snapped
        # here, a plan whose waypoints were not on the network came back
        # somewhere else — 19.1 km saved, 68.3 km restored, measured.
        assert "anchored(graph, at) : {lat: wp.lat, lon: wp.lon, node: -1};" in planning
        # Align mode still snaps, because that is the whole of what it offers.
        assert "var here = snapped(graph, point.lat, point.lon);" in planning

    def test_a_tap_lands_on_the_line_and_not_only_on_its_junctions(self):
        """Reported from the phone: once one leg was drawn straight, every tap
        after it was too, until a tap landed on *a path further on* -- which
        was the next junction. A node is where edges meet or a chain ends, and
        ``snapped`` asked only the nodes, so a tap in the middle of a long
        stretch of trail found nothing within a finger's width and stood as
        open ground. Measured: 37 % of Abisko's network by length lies more
        than 21 m from any node, 13 % more than 150 m; edges run to 13 km.

        The line itself is asked as well, over the grid match mode builds, and
        a point put on it remembers its edge and how far along. The router
        starts from either end of that edge at the edge's own price, and the
        piece walked to the end travels as a cut, drawn as the path it is --
        in a leg between two points on the network and in the joined way a
        goal is routed by. A junction within reach still wins over the line
        beside it, give or take two metres."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        # The line, over the index, and never a crossing or a connector.
        assert "function nearestOnNetwork(graph, lat, lon, withinM) {" in planning
        assert "var index = edgeIndex(graph);" in planning
        assert "if (kind === CROSSING || kind === CONNECTOR) { continue; }" in planning
        assert "return {edge: best, along: along, lon: foot.lon, lat: foot.lat, m: Math.sqrt(closest) * 111320};" in planning
        # A junction as near as the line is the junction.
        assert "var NODE_FIRST_M = 2;" in planning
        assert "if (!line || nodeM <= line.m + NODE_FIRST_M) {" in planning
        assert "if (line) { return {lat: line.lat, lon: line.lon, node: -1, edge: line.edge, along: line.along}; }" in planning
        # On the network is on a node or on an edge; either end of the edge at
        # the edge's own price, with the piece to it as a cut.
        assert "function onNetwork(point) { return point.node >= 0 || point.edge >= 0; }" in planning
        assert "function endsOf(graph, point) {" in planning
        assert "var length = work.length[edge], rate = length > 0 ? work.cost[edge] / length : 0;" in planning
        assert "return [{node: graph.fromNode[edge], cost: along * rate, cut: {edge: edge, from: along, to: 0}}," in planning
        # One search from every end to every end, stopped by the cheapest
        # whole way in hand; two points on one edge take the piece between.
        assert "function routeBetween(graph, from, to) {" in planning
        assert "if (found && taken.cost >= found.cost) { break; }" in planning
        assert "if (direct && (!found || direct.cost <= found.cost)) { return direct; }" in planning
        assert "function route(graph, from, to) { return routeBetween(graph, {node: from}, {node: to}); }" in planning
        assert "if (onNetwork(from) && onNetwork(to)) {" in planning
        # The cut is path: laid like an edge, tallied by its metres.
        assert "function cutPart(graph, cut) {" in planning
        assert "tallyEdge(tally, graph, edge, hi - lo);" in planning
        assert "var head = found.head ? cutPart(graph, found.head) : null;" in planning
        # And the joined way takes an end on the network by its edge, not by
        # a walk over the ground to a node.
        assert "var toEnds = endsOf(graph, to);" in planning
        assert "for (i = 0; i < nodes && !toEnds.length; i += 1) {" in planning
        assert "joined.tailCut = tailCuts[joined.tail] || null;" in planning
        assert "joined.headCut ? pieceOf(joined.headCut) : walkTo(graph, from, enter, mayAsk)," in planning
        # A goal's leg asks once, at the same spot, whether its ends stand on
        # the line: a tap was put there, a hut from a popup was not.
        assert "return resolve(graph, placed(graph, head), placed(graph, tail), true, true);" in planning
        assert "var at = snapped(graph, point.lat, point.lon, SAME_SPOT_M);" in planning
        # Warmed with the graph when plan mode comes on.
        switching = planning[planning.index("function switchTo(want) {") : planning.index("status.addEventListener('click'")]
        assert "edgeIndex(graph);" in switching
        # A check can see a leg that settled and drew nothing, and a point
        # on an edge.
        assert "drawn: leg.layers.length," in planning
        assert "edge: point.edge === undefined ? -1 : point.edge," in planning

    def test_a_row_is_named_by_the_greater_part_of_its_leg(self):
        """A hut stands a few metres off the path and the walk to it is a
        straight piece of a leg that is otherwise all path; the row called that
        leg *drawn straight*, which the map plainly did not show. Reported from
        the phone beside a leg of 5.4 km with 63 m of it off the path."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        naming = planning[planning.index("function groundInto(index) {") : planning.index("function shutMenus() {")]
        assert "var crossing = false, recorded = false, straight = 0, walked = 0;" in naming
        assert "if (straight > 0 && straight >= walked / 2) { return 'drawn straight'; }" in naming
        assert "if (crossing) { return 'over a crossing'; }" in naming

    def test_a_plan_reaches_the_network_rather_than_being_moved_on_to_it(self):
        """The other half of what a point that did not snap used to mean.

        A waypoint beyond the snap was kept raw and its leg was drawn straight
        end to end — so 28 m of finger movement, either side of the reach, threw
        the answer between *your point moved 135 m, and here is 3.39 km of
        path* and *your point stands, and here is 2.27 km straight across the
        mountain*. Measured in a browser at those two taps. With the reach cut
        to a finger that cliff would be met far more often, not less.

        A plan's legs now reach the network the way a goal's do, by a short walk
        to it, so the two sides of the reach differ by the length of that walk
        and nothing else.

        **Except under a live drag**, and for the reason the height service is
        already not asked there: the search is 64 ms on a long leg, a drag
        settles every ``DRAG_EVERY_MS`` with two legs to redo, and the two
        together are a route that cannot keep up with the finger holding it.
        What the reader sees while dragging is the leg at its own straight
        length saying it is still being worked out — which is what
        ``waitingParts`` has always been for — and the search runs once, when
        the finger lifts."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "return resolve(graph, from, to, mayAsk, mayAsk); }" in planning

    def test_a_tapped_goal_takes_the_line_under_the_finger_too(self):
        """The rule the plan follows, asked of the goal — and it is one rule.

        A finger's width on the screen is the finest a reader can point at the
        zoom they are looking at, so a line inside it is the line they were
        pointing at and taking it as one is not a guess. Zooming in is how they
        say otherwise: 48 m of ground at z14, 12 m at z16, 3 m at z18, and the
        tiles here go to 18.

        **Third in a ladder of three.** A named thing within ``namedM`` wins,
        because a hut is a place and not a position; then a line within a
        finger; then the tap as it fell.

        **And nothing that is not a tap snaps.** A goal taken from a place's
        popup arrives already named — the reader pressed a button on something
        they were reading, and a place moved on to the path beside it is no
        longer that place. One restored from the last visit was snapped when it
        was set. A file is read under ``snapM`` or not at all, which is a
        question about the ground rather than about a screen.

        The graph is asked, so the answer lands a microtask after the tap rather
        than in it; where it never arrives the tap stands, because a goal set in
        a page that cannot route is still a goal."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function onTheLine(lat, lon, then) {" in planning
        assert "var at = snapped(graph, lat, lon, fingerReach(lat));" in planning
        # The tap stands where no graph ever arrives.
        assert "}, function () { if (!asked) { then(lat, lon); } });" in planning
        # Both take it, and only when told the position came off a finger.
        assert "function setGoal(lat, lon, name, tapped) {" in planning
        assert "function addStop(lat, lon, name, tapped) {" in planning
        assert "onTheLine(lat, lon, function (at, on) { setGoal(at, on, name); });" in planning
        assert "onTheLine(lat, lon, function (at, on) { addStop(at, on, name); });" in planning

    def test_one_walker_and_one_sum_for_two_routes(self):
        """The plan and the goal share everything that decides an answer — the
        router, the connector layer, the composing, the drawing — and kept a
        copy each of two small pieces of geometry that decide nothing.

        The triple loop over a list of legs was written twice and differed in
        one expression: what a leg still being worked out counts as. The gap
        from a position to a segment was written *three* times, two of them
        character for character the same. Three copies of one piece of
        arithmetic is three places for it to stop agreeing, and the page has
        found that failure three times in other guises.

        (A fourth copy stands in the position mark, which is its own component
        with its own closure and reaches none of this.)"""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function segmentsOf(list, over, visit) {" in planning
        assert "segmentsOf(legs, function (leg) { return straightAcross(leg.from, leg.to); }, visit);" in planning
        assert "segmentsOf(goalLegs, function () { return []; }, visit);" in planning
        assert "return nearSegment(lat, lon, cosine, aLat, aLon, bLat, bLon).away;" in planning
        assert "return awayFromLine(lat, lon, cosine, goalShape.lat[at], goalShape.lon[at]," in planning
        # One sum, and it is the one that hands back the foot as well.
        assert planning.count("var t = span > 0 ? -(ax * dx + ay * dy) / span : 0;") == 1

    def test_a_way_round_has_to_beat_walking(self):
        """A leg between two waypoints that both sit on the network used to take
        whatever the router found, however long, because nothing compared it
        with anything. Reported from the phone for a goal and measured again in
        a browser for a plan, with the same three taps: 77.20 km for 10.00 km
        flown, one leg of it 66.73 km for a straight 2.15 km. Both points had
        been snapped, one of them on to a fragment of path in the next valley,
        and the way between those two nodes genuinely is a loop round half the
        park — it is the answer to a question nobody asked.

        The same comparison the connector layer makes and in the same metres, so
        a leg here can never be dearer than the straight line's price either --
        ``offPathFactor`` times the line it could have flown, over ground.
        **Priced by what it crosses**, like every connector: two waypoints on
        paths either side of a sound would otherwise lose the road round it to
        a dotted line over the water, because the road is more than three
        times the line.

        **Except where there is nothing to draw instead.** A leg longer than
        ``maxStraightM`` cannot be drawn straight at all — it is refused for its
        sampling — and refusing a long way round in favour of nothing is the
        worse of the two answers, so past that length the route stands."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "if (found && worthRouting(graph, from, to, found.cost)) {" in planning
        assert "function worthRouting(graph, from, to, cost) {" in planning
        assert "if (flown > PLAN.maxStraightM) { return true; }" in planning
        assert "return cost <= priced(graph, from.lon, from.lat, to.lon, to.lat);" in planning

    def test_a_point_off_the_network_is_joined_to_it_not_moved_on_to_it(self):
        """Reported from the phone with a screenshot: with several stops set,
        one of them stood beside the way instead of on it, and the walk came out
        at 138 km between places 20 km apart. Both are one defect, measured in a
        browser before it was touched — 67 m of gap, and a leg of 66.6 km for a
        straight 2.15 km.

        A stop used to be *snapped*: replaced by the nearest node within
        ``snapM``, so the mark stayed where the reader put it while the way ran
        from somewhere else. And having replaced it, the router was asked for
        the way between two node numbers and took whatever it found — which for
        a node on a fragment of path in the next valley is a loop round half the
        park. Nothing in either step asked whether the answer was worth having.

        **The whole graph is joined to each end of the leg by connectors**, each
        priced at ``offPathFactor`` metres to the metre, with the leg's own
        straight line as one more connector between the two ends; then the
        cheapest way through wins. That makes the three readings one reading:
        walking straight is the direct connector winning, a routed leg is two
        connectors with the network between them, and *most of the way is a
        path* is the same thing with one long connector on the end. No
        threshold, because the comparison is the rule — and it is the cost of
        the path that the old rule never put on the scales.

        Seeded from the far end at every node at once, so the search settles
        what it costs to get from each node to where the leg ends, walk off the
        network included; the entry is then the node that minimises the walk to
        it plus that. The route is read back out of the same search: ``viaNode``
        points at the *next* node on the way, because the search ran backwards,
        so the edges come out already in the order they are walked."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function joinedRoute(graph, from, to) {" in planning
        assert "var off = offPath();" in planning
        # Every node seeded with the walk off the network at it, except the
        # ones already dearer than walking the whole way — an exact bound and
        # not a heuristic. Measured on one 13.6 km leg, routed and redrawn:
        # 157 ms unbounded against 64 ms bounded.
        assert "var leave = far(graph.nodeLon[i], graph.nodeLat[i], to.lon, to.lat) * off;" in planning
        assert "if (leave >= plain) { continue; }" in planning
        assert "if (Math.min(floorTop, exactTop) >= plain) { break; }" in planning
        # The straight line as one more connector, and what everything else has
        # to beat.
        assert "var plain = priced(graph, from.lon, from.lat, to.lon, to.lat);" in planning
        assert "var head = -1, headCut = null, cheapest = plain;" in planning
        assert "var floor = far(graph.nodeLon[i], graph.nodeLat[i], from.lon, from.lat) * off + best[i];" in planning
        assert "var whole = priced(graph, from.lon, from.lat, graph.nodeLon[next.node], graph.nodeLat[next.node]) + best[next.node];" in planning
        # Bounded like every other loop over this graph, with room for each
        # seed to come back once at its true price.
        assert "var pops = 0, mostPops = 2 * nodes + 2 * graph.header.edges + 1;" in planning
        # And the way out read off the same search, forwards.
        assert "function leavingAt(graph, head) {" in planning
        assert "while (work.viaEdge[walk] >= 0) {" in planning
        assert "reversed.push(graph.fromNode[used] !== walk);" in planning
        assert "if (steps > graph.header.edges) { throw new Error('the way out is longer than the graph'); }" in planning
        # And where the direct connector wins, the leg is drawn the way every
        # other straight leg is — not by `walkTo`, which swallows a refusal from
        # the height service. A plan has to say it could not get its heights;
        # the goal takes the tolerant reading in `oneLeg`, where it belongs.
        assert "// it belongs, in `oneLeg`." in planning
        # And the two searches it replaced are gone, not left beside it.
        assert "nearestReached" not in planning
        assert "route(graph, tail, -1);" not in planning

    def test_a_straight_walk_is_priced_by_what_it_crosses(self):
        """Reported from the phone with a screenshot: a goal on the headland
        across a 1.2 km sound from the end of the path was reached by a dotted
        line over the water. A connector was priced by its length alone, so the
        sound cost 3.6 km and the road round the head of it is longer.

        **A metre over water costs ``waterFactor`` instead of ``offPathFactor``**,
        read off the grid the graph carries, once per cell along the line. A
        price and not a rule, so an island with no path still gets an answer:
        every connector there crosses water and the one that crosses least
        wins. And a page whose graph carries no grid prices every metre as
        ground, which is what every page did before.

        **Priced when it is asked for.** Every node is seeded with its price
        over ground, which is a floor, and priced for real when that floor
        reaches the top of the queue. That keeps the grid from being asked
        about 117,000 connectors on every tick of a drag, and the bound and
        the pruning need nothing more than a floor.

        **And a floor is not a label.** The first version wrote the floor into
        ``best`` and repriced on pop; measured against an eagerly priced search
        on seven legs to one headland, three disagreed, one by a straight walk
        of 2.1 km where the road was there to take. A settled node's offer to
        a neighbour was refused against the neighbour's floor, the floor was
        then raised, and the settled node never offered again. So the floors
        have a queue of their own and ``best`` holds only exact prices."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function priced(graph, aLon, aLat, bLon, bLat) {" in planning
        assert "if (!grid || !(PLAN.waterFactor > offPath())) { return length * offPath(); }" in planning
        assert "var pieces = Math.max(1, Math.ceil(length / grid.cellM)), wet = 0;" in planning
        assert "if (graph.waterAt(aLon + t * (bLon - aLon), aLat + t * (bLat - aLat))) { wet += 1; }" in planning
        assert "return (length - water) * offPath() + water * PLAN.waterFactor;" in planning
        # Lazily, and in a queue of its own: a floor is priced for real when
        # it is the cheaper top, and only an exact price is ever a label.
        assert "var floors = new Heap(), heap = new Heap(), i;" in planning
        assert "floors.push(i, leave);" in planning
        assert "best[i] = leave;" not in planning
        assert "if (Math.min(floorTop, exactTop) >= plain) { break; }" in planning
        assert "if (floorTop <= exactTop) {" in planning
        # A node already reached over the network for no more than its floor
        # is not priced: its connector costs at least the floor.
        assert "if (best[seed.node] <= seed.cost) { continue; }" in planning
        assert "var truly = priced(graph, graph.nodeLon[seed.node], graph.nodeLat[seed.node], to.lon, to.lat);" in planning
        assert "if (truly < best[seed.node]) {" in planning
        # And the entry side walks its floors in order and stops at the first
        # floor dearer than the best whole.
        assert "var entries = new Heap();" in planning
        assert "if (next.cost >= cheapest) { break; }" in planning

    def test_the_water_grid_is_inflated_and_counted_before_anything_routes(self):
        """The grid travels in the header as its own gzipped block and is
        checked the way the stream is: the header says how many cells are
        water, and a grid that inflated to a different number is refused
        rather than used, because a grid that came out short would price
        fjords as ground with nothing looking wrong. Both are inflated before
        either is used, so no search runs in the gap between them."""
        fmap, _ = self.drawn()
        maps.add_routing_graph(fmap, {"nodes": 0, "edges": 0, "chains": 0, "water": None}, "")

        page = fmap.get_root().render()
        assert "function waterGrid(spec, packed) {" in page
        assert "if (set !== spec.set) {" in page
        assert "return (grid.bits[row * grid.stride + (col >> 3)] & (0x80 >> (col & 7))) !== 0;" in page
        assert "if (col < 0 || row < 0 || col >= spec.cols || row >= spec.rows) { return false; }" in page
        assert "graph.waterAt = function (lon, lat) { return waterAt(graph.water, lon, lat); };" in page
        assert "graph.ready = Promise.all([inflate(bytesOf(encoded)), grid]).then(function (both) {" in page

    def test_the_part_that_was_never_a_path_is_said(self):
        """A line on a map is a promise, and a partly routed one is a promise
        only for the part that came off the network. Said whenever there is any
        of it and not only where the whole way is trackless: the reader is being
        shown a line, and which part of it is not a path is what they have to
        know before they set off along it."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "straight: goalShape ? (goalShape.straight + goalShape.crossed) : null," in planning

    def test_a_stretch_too_long_to_sample_is_still_a_stretch_to_walk(self):
        """Reported from the phone, 112 km from the goal: the way *was* routed,
        the approach to the network came out at ninety-odd kilometres, and the
        height service refuses a straight stretch past ``maxStraightM`` — which
        sank the whole answer and reported *no way there* with a route in hand.

        That refusal is a fact about sampling and not about the ground. The
        stretch is drawn for what it is, with nothing claimed about its heights,
        and the profile shows a hole in it — which is what a hole in what is
        known looks like everywhere else on this page. Not marked provisional
        either: nothing is still being worked out there, this is the answer."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "if (length > PLAN.maxStraightM) { return Promise.resolve(plainParts(from, to, length)); }" in planning
        assert "function plainParts(from, to, length) {" in planning
        # And a refusal for any other reason does not take the route down
        # with it either.
        assert "function () { return plainParts(from, to, length); }" in planning

    def test_a_tap_means_the_goal_only_where_the_way_there_runs(self):
        """Reported from the phone: with a goal set, the panel answered every
        tap with the goal. The row offers the way there wherever it runs — its
        line takes no clicks, so the row is the only way to it — and the row's
        own rule is that a line the reader made takes the tap. Offered
        unconditionally, that made *every* tap the reader's own line, and a way
        tapped in order to be read came back named *to the goal*.

        The same question the planned route answers with ``onRoute``, asked of
        this, and at the same reach the panel asks of every other line under the
        finger."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function nearGoal(lat, lon, withinPx) {" in planning
        assert "var reach = (withinPx || ON_ROUTE_PX) * 40075016.686 * cosine /" in planning
        assert "near: nearGoal," in planning
        # And the shape itself, handed out rather than carried in `state()`:
        # it is read on every check and by the chrome, and a route is not a
        # status. The plan's own geometry is handed out under the same rule.
        assert "return goalShape ? {lon: goalShape.lon, lat: goalShape.lat} : null;" in planning

    def test_setting_a_goal_opens_the_way_there(self):
        """A goal worked out a second ago is what the reader is looking at, and
        a panel still showing whatever they were reading before it is a page
        answering a question nobody has any more. Opened at the curve, because
        the profile is the half of *how do I get there* that the map cannot
        draw.

        Only when it was **set**, and not on the routing that happens on its own
        as they walk: taking the panel out from under somebody every half minute
        is not an answer, it is an interruption."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "if (goalShape && goalFresh) { goalFresh = false; showGoalProfile(); }" in planning
        assert "function showGoalProfile() {" in planning
        assert "return showing.page('profile') === 'profile';" in planning
        # **Named like a route, because it is drawn like one.** The heading is
        # where every route on the panel says what it is, and the goal's says
        # the name and how many places the way goes by; the row of switches
        # that used to say them is a page now.
        assert "showing.series({label: 'To ' + (goalAt.name || 'the goal') + byStops," in planning
        assert "var byStops = goalVia.length ? ' \\u00b7 by ' + goalVia.length + (goalVia.length === 1 ? ' stop' : ' stops') : '';" in planning
        assert "showProfile: showGoalProfile," in planning
        # Set by setting a goal and by asking for it to be routed, and by
        # nothing else — least of all by the re-routing rule.
        # Set wherever the reader changed what the way *is* — a goal, a stop,
        # or which reading of it — and never by the routing that happens on its
        # own as they walk.
        assert planning.count("goalFresh = true;") == 3

    def test_the_route_s_points_are_drawn_while_the_route_is(self):
        """Reported from the phone: after plan mode was left the numbered discs
        stayed on the map, standing over every other line a reader chose
        afterwards — a route's own furniture over somebody else's reading.

        They are drawn while it is being planned and while it is what the panel
        is showing; the line itself stays either way, which is what says the plan
        has not gone anywhere. The test is the one the row at the foot lights the
        route's chip by, and it has to be that one: ``composed`` alone is true of
        the way to a goal as well, and a goal's points are not these.

        Dressed rather than repainted when the selection changes: `repaint`
        composes the whole route to find out what to draw, 45 ms over a long one,
        on every tap that changes what is chosen."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function planShowing() {" in planning
        assert "return !!(said && said.composed && !said.goal);" in planning
        assert "var shown = on || planShowing();" in planning
        assert "element.style.display = shown ? '' : 'none';" in planning
        assert "dress: dressPins," in planning

    def test_both_readings_of_a_goal_are_a_chain_of_legs(self):
        """Asked for from a phone: stops between the reader and a goal, in both
        readings. What that turns into is that *direct* and *routed* stop being
        two things — one is a chain of straight legs and the other a chain of
        routed ones, and everything downstream works on one shape rather than on
        two: the profile, the row of choices, the figures and the mark.

        Which also gives the straight reading a profile it never had. A line
        across a mountainside is a climb whether or not anybody laid a path
        along it, and a reader choosing between the two is entitled to know what
        each of them costs.

        A straight leg is not snapped: it runs between the places the reader put
        down, and moving one of them onto the network would be routing without
        saying so."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "function goalLegBetween(graph, head, tail) {" in planning
        assert "if (goalWay !== 'routed') { return walkTo(graph, head, tail, true); }" in planning
        assert "var chain = [{lat: from.lat, lon: from.lon}].concat(stopsOf());" in planning
        # One refusal must not throw the chain away: a stop of five that cannot
        # be reached is a fact about that stop and not about the journey.
        assert "function oneLeg(graph, head, tail) {" in planning
        # A leg that could not be worked out is still ground the reader has to
        # cross: drawn straight with nothing claimed about it, and still marked
        # failed so the row says why. Handing back nothing left a hole in the
        # way with a stop standing in the middle of it.
        assert "return {from: head, to: tail, parts: plainParts(head, tail, length)," in planning

    def test_a_stop_goes_into_the_leg_it_is_nearest(self):
        """A reader putting a stop down means *and by way of here*, and where in
        the order that falls is a fact about the ground rather than something to
        be asked. No reach and no threshold: every point has a nearest leg,
        which is what makes the answer always defined — the same shape as the
        rule that decides whether routing is worth taking at all."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "goalVia.splice(legNearest(lat, lon), 0, {lat: lat, lon: lon, name: name || null});" in planning
        assert "function legNearest(lat, lon) {" in planning
        assert "return Math.min(best, goalVia.length);" in planning
        # Leg i ends at stop i, which is what makes the mark name the next place
        # rather than the last one.
        assert "return {lat: stops[leg].lat, lon: stops[leg].lon, name: stopSaid(leg)};" in planning

    def test_a_straight_part_says_which_river_it_wades_through(self):
        """Measured over the eight municipalities of this build: 589 rivers as
        outlines, half of them under 17 m across, five in six under 30 m. That
        is a breadth a walker fords or does not by depth and current, which no
        layer records -- so a river is never priced, and what the page can say
        it says: which river the straight part meets and how wide the water is
        there. The outlines travel packed as differences and are unpacked once."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        html = fmap.get_root().render()
        assert "graph.rivers = riversOf(header.rivers);" in html
        assert "graph.riverAt = areasAt.bind(null, graph.rivers);" in html
        unpacked = html.split("function riversOf(table) {")[1].split("function nearestNode(")[0]
        assert "lon += steps[i]; lat += steps[i + 1];" in unpacked
        assert "ring.push([lon * quantum, lat * quantum]);" in unpacked
        planning = html.split("var PLAN =")[-1]
        crossing = planning.split("function riverCrossings(graph, from, to) {")[1].split("function straightParts(")[0]
        # Every cut of a ring, in order along the line; inside or out at the
        # start settled by the same even-odd test the areas use; a run that
        # ends in the water is counted too.
        assert "var inside = graph.riverAt(from.lon, from.lat).indexOf(which) >= 0;" in crossing
        assert "cuts.sort(function (a, b) { return a - b; });" in crossing
        assert "if (began !== null) { found.push({name: river.name, width: (1 - began) * length, at: began * length}); }" in crossing
        assert "rivers: riverCrossings(graph, head, tail)," in planning
        # Composed in walking order, said wherever a route is described.
        assert "if (part.rivers) { rivers = rivers.concat(part.rivers); }" in planning
        assert "rivers: rivers};" in planning
        assert "return 'crosses ' + (river.name || 'a river') + ', ' + Math.round(river.width) + ' m wide there';" in planning
        told = planning.split("function told(shape) {")[1].split("function riverSaid(")[0]
        assert "said.push(riverSaid(river));" in told
        # And the goal's own page: the rivers, and the worst gradient on the
        # straight part alone.
        assert "rivers: goalShape ? goalShape.rivers.map(riverSaid) : []," in planning
        assert "var worst = panel().steepestOf(goalShape, true);" in planning

    def test_stay_on_paths_prices_open_ground_at_ten_to_one(self):
        """The build's three is a judgement about ground nobody has looked at.
        Measured at Krutåga: 740 m straight from the last junction to a goal 100
        m off a road counted 2.2 km, and the road round, 2.6 km with a bridge,
        lost to it. A switch and not a better number: which of the two a reader
        wants depends on what they can see from where they stand. Everything
        priced is priced again when it turns, and it is remembered."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "var PATHS_FACTOR = 10;" in planning
        assert "function offPath() { return staying() ? PATHS_FACTOR : PLAN.offPathFactor; }" in planning
        # The one place the build's figure is read; every price goes through it.
        assert planning.count("PLAN.offPathFactor") == 1
        assert "var off = offPath();" in planning
        assert "return (length - water) * offPath() + water * PLAN.waterFactor;" in planning
        switching = planning.split("function stayOnPaths(want) {")[1].split("\n            }\n")[0]
        assert "window.localStorage.setItem(keptKey() + '.paths', 'yes');" in switching
        assert "withGraph(function (graph) { relink(graph, true); }, function () { refresh(); });" in switching
        assert "if (goalAt) { goalToken = null; routeToGoal(goalHere()); }" in switching
        assert "stayOnPaths: stayOnPaths," in planning

    def test_the_way_to_a_goal_says_what_each_station_is(self):
        """A dot where the reader stands, the stops by the numbers the map's
        marks carry, the goal as its ring: the profile is drawn from this and
        cannot count the start as a stop again."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        series = planning.split("showing.series({label: 'To ' + (goalAt.name || 'the goal') + byStops,")[1].split("return true;")[0]
        assert "marks: [{kind: 'start'}].concat(goalVia.map(function (stop, at) {" in series
        assert "return {kind: 'numbered', label: String(at + 1)};" in series
        assert "}), [{kind: 'goal'}])});" in series

    def test_a_new_goal_is_a_new_journey(self):
        """The stops were put down on the way to somewhere. Kept across a change
        of destination they would be a detour nobody asked for, and the reader
        would have to find and remove each of them — so setting a goal clears
        them, and only setting a goal does.

        They are kept beside it, though: a page rebuilt in a valley would
        otherwise quietly straighten the way out."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        assert "goalVia = [];" in planning.split("function setGoal(lat, lon, name, tapped) {")[1]
        assert "via: goalVia.map(function (stop) {" in planning
        # Restored after the goal, because setting one is what clears them.
        assert "(said.via || []).forEach(function (stop) {" in planning
        # **And the goal moved is not a new journey.** A reader who wants the
        # end of the same journey a little further along the shore keeps the
        # stops; only `set` clears them.
        moving = planning.split("function moveGoal(lat, lon, name, tapped) {")[1].split("function metresInto() {")[0]
        assert "goalAt = {lat: lat, lon: lon, name: name || null};" in moving
        assert "goalVia = [];" not in moving
        assert "move: moveGoal," in planning

    def test_a_stop_moved_or_stepped_keeps_the_others_where_they_are(self):
        """A stop put somewhere else is the same stop: it keeps its place in
        the order, because the reader chose where it falls when they put it
        down, and a stop nudged fifty metres has not changed which hut it is
        walked to before. That is what tells it apart from dropping one and
        adding one, where `legNearest` would decide the order afresh.

        One place earlier or later is a swap with a neighbour, the plan's own
        gesture: the smallest change to the order, and it composes into any.
        Both go through the goal's entry, so the list at the foot holds no
        order of its own."""
        fmap, _ = self.drawn()
        maps.add_plan_mode(fmap, self.planned())

        planning = fmap.get_root().render().split("var PLAN =")[-1]
        moved = planning.split("function moveStop(at, lat, lon, name, tapped) {")[1].split("function stepStop(at, step) {")[0]
        assert "goalVia[at] = {lat: lat, lon: lon, name: name || null};" in moved
        assert "legNearest" not in moved
        stepped = planning.split("function stepStop(at, step) {")[1].split("function moveGoal(")[0]
        assert "if (at < 0 || at >= goalVia.length || to < 0 || to >= goalVia.length) { return false; }" in stepped
        assert "goalVia[to] = moved;" in stepped
        assert "moveStop: moveStop," in planning
        assert "stepStop: stepStop," in planning
        # And each place says how far into the way it comes: leg i ends at
        # stop i, so the figure is the legs up to and including its own, and
        # null where one is not made yet -- a partial sum said as a distance
        # is a distance nobody walked.
        assert "into: at < into.length ? into[at] : null};" in planning
        assert "if (walked === null || !parts) { walked = null; into.push(null); continue; }" in planning


class TestRoutingGraphAreas:
    """Tests for the boundaries the page is handed with the graph."""

    def rendered(self, areas: list[dict[str, object]]) -> str:
        """A page carrying a graph header with these areas in it.

        Args:
            areas: What the header says is protected

        Returns:
            The rendered page
        """
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_routing_graph(fmap, {"version": 3, "edges": 0, "protected": areas}, "")
        return fmap.get_root().render()

    def test_the_test_is_bound_before_the_stream_is_inflated(self):
        """It needs nothing from the stream — the outlines are in the header —
        and a caller asking what protects a position should not wait for two
        million coordinates it is not going to look at."""
        html = self.rendered([])

        assert "graph.areasAt = areasAt.bind(null, graph.protectedAreas)" in html
        assert html.index("graph.areasAt = areasAt") < html.index("graph.ready = Promise.all([inflate")

    def test_an_area_carries_its_outline_and_its_box(self):
        """The box settles thirty of thirty-one areas in four comparisons, and
        only then are four thousand vertices walked."""
        area = {"id": "VV0001", "name": "Somewhere", "form": "naturreservat", "bounds": [12.0, 65.0, 13.0, 66.0], "rings": [[[12.0, 65.0]]]}
        html = self.rendered([area])

        assert "VV0001" in html
        assert "areas[a].bounds" in html
        assert "areas[a].rings" in html

    def test_a_page_without_a_protected_list_still_answers(self):
        """An older payload, or a build over ground nothing protects."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_routing_graph(fmap, {"version": 3, "edges": 0}, "")

        assert "header.protected || []" in fmap.get_root().render()


def export_javascript(source: str, name: str, indent: int = 12) -> str:
    """Extract an emitted function for the Node export tests without rewriting it."""
    match = re.search(rf"^{' ' * indent}function {name}\([^\n]*\) \{{.*?^{' ' * indent}\}}", source, re.M | re.S)
    assert match is not None, name
    return match[0]


@pytest.fixture(scope="module")
def garmin_exports(tmp_path_factory):
    """Execute the page's composers' file entries and ZIP writer with fixed shapes.

    Like the worker tests below, this uses the installed Node, not a browser
    dependency. Only composition and delivery are supplied by the harness: the
    emitted runs, metadata, writers, file names and archive bytes are exercised.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed to execute the GPX writer tests")
    directory = tmp_path_factory.mktemp("garmin-exports")
    panel = TestProfilePanel()
    fmap, layer = panel.drawn()
    maps.add_profile_panel(fmap, [layer], export=panel.exported())
    html = fmap.get_root().render()
    html = html[html.index("            function metres(value)") :]
    # Function declarations have no DOM side effects. Keeping the emitted
    # bodies tests the production code, including its common densification.
    functions = re.findall(r"^            function \w+\([^\n]*\) \{(?:[^\n]*\}$|.*?^            \})", html, re.M | re.S)
    entries = []
    for name in ("routeFile", "garminFile"):
        match = re.search(rf"{name}: function \(.*?^                \}},", html, re.M | re.S)
        assert match is not None
        entries.append(match[0])
    planning = files("trails.visualization").joinpath("js", "plan_mode.js").read_text(encoding="utf-8")
    saves = "\n".join(export_javascript(planning, name) for name in ("saveWhole", "saveStage", "saveStages"))
    source = "\n".join(functions)
    source += "\n" + export_javascript(html, "saveNow", 16)
    source += "\n" + export_javascript(html, "saveGarminNow", 16)
    source += "\nvar EXPORT = " + json.dumps(panel.exported()) + ";"
    source += "\nvar outputDirectory = " + json.dumps(str(directory)) + ";"
    source += "\nvar entry = {" + "\n".join(entries) + "};\n" + saves
    source += r"""
        var window = {}, GRADE = {window: 25, minRun: 10};
        var RealDate = Date;
        Date = class extends RealDate {
            constructor(...args) { super(...(args.length ? args : ['2026-09-20T12:00:00Z'])); }
        };
        var figure = {id: 'test-chain', name: 'Test & chain', source: 'UT.no',
                      ascent: 300, descent: 290, high: 140, low: 80};
        // A winding 4.8 km chain with a crossing between two walked runs.
        // Every 41st sample has no height, so both kinds of vertex are tested.
        function shapeOf(from, to, breaks) {
            var shape = {lon: [], lat: [], along: [], height: [], distance: [], stretches: [],
                         read: true, crossed: breaks ? 100 : 0, straight: 0, protected: [],
                         tally: {sources: {'UT.no': (to - from) * 4}, marked: 0, unmarked: 0,
                                 unknown: (to - from) * 4, undrawn: 0, unrecorded: 0, recorded: 0}};
            var distance = 0;
            for (var i = from; i <= to; i += 1) {
                var x = 13 + i * 4 / 46270;
                var y = 65.5 + (60 * Math.sin(i / 30) + 12 * Math.sin(i / 7)) / 111492;
                if (i > from) {
                    distance += metresBetween(shape.lon[i - from - 1], shape.lat[i - from - 1], x, y);
                }
                shape.lon.push(x); shape.lat.push(y); shape.along.push(distance); shape.distance.push(distance);
                shape.height.push(i % 41 === 0 ? NaN : 110 + 25 * Math.sin(i / 50));
            }
            var n = shape.lon.length;
            shape.total = distance;
            shape.stretches = breaks
                ? [{from: 0, to: 591, sampleFrom: 0, sampleTo: 591},
                   {from: 610, to: n, sampleFrom: 610, sampleTo: n}]
                : [{from: 0, to: n, sampleFrom: 0, sampleTo: n}];
            return shape;
        }
        var whole = shapeOf(0, 1200, true);
        var stages = [{from: 0, to: 1, name: 'Over the pass'}, {from: 1, to: 2, name: 'Down & home'}];
        var stageShapes = [shapeOf(0, 590, false), shapeOf(610, 1200, false)];
        function composeRoute(from) { return from === undefined ? whole : stageShapes[from]; }
        function figuresOf() { return figure; }
        function told(shape) { return shape.crossed ? ['1 crossing, 0.10 km'] : []; }
        function stagesOf() { return stages; }
        function stageName(stage) { return stage.name; }
        function stageTitle(stage) { return 'A tour with its full name — ' + stage.name; }
        function planOf(shape, name) {
            return {name: name, stem: 'Tour', waypoints: [
                {lon: shape.lon[0], lat: shape.lat[0], name: 'Start & quay'},
                {lon: shape.lon.at(-1), lat: shape.lat.at(-1), name: 'End'}
            ], legs: [[{kind: 'routed', length: shape.total}]], why: null};
        }
        function writable() { return planOf(whole, 'A tour with its full name'); }
        function writableRange(from, to, name) { return planOf(stageShapes[from], name); }
        function fileFailed(failure) { throw failure; }
        function saveFile(name, body) { require('node:fs').writeFileSync(outputDirectory + '/' + name, body); }
        entry.save = saveFile;
        entry.saveZip = function (made) {
            return zipOf(made).then(async function (blob) {
                saveFile('everything.zip', Buffer.from(await blob.arrayBuffer()));
            });
        };
        function panel() { return entry; }
        saveWhole(); saveWhole(true);
        var selected = {composed: true, figure: figure, shape: whole, runs: runsOf(whole),
                        plan: writable(), told: told(whole)};
        var delivered = [];
        function saveProfile(name, text) { delivered.push({name: name, text: text}); }
        var diskSave = saveFile;
        saveFile = saveProfile;
        saveNow(); saveGarminNow();
        selected.plan.why = 'still working out a leg';
        saveNow(); saveGarminNow();
        saveFile = diskSave;
        saveFile('profile-files.json', JSON.stringify(delivered));
        stages.forEach(function (stage) { saveStage(stage); saveStage(stage, true); });
        var short = shapeOf(0, 19, false), shortPlan = planOf(short, 'Short <walk>');
        [false, true].forEach(function (garmin) {
            var made = (garmin ? entry.garminFile : entry.routeFile)(figure, short, [], shortPlan, 'short');
            saveFile(made.name, made.text);
        });
        var runs = runsOf(short);
        saveFile('chain.gpx', gpxOf(figure, short, runs));
        saveFile('chain-points.json', JSON.stringify(runs));
        var cases = [];
        [0, 1, 2, 199, 200, 201, 1000].forEach(function (n) {
            ['straight', 'closed', 'repeated'].forEach(function (kind) {
                var run = {lon: [], lat: [], ele: []};
                for (var i = 0; i < n; i += 1) {
                    var angle = 2 * Math.PI * i / Math.max(n - 1, 1);
                    run.lon.push(kind === 'straight' ? 13 + i / 100000 :
                                 kind === 'closed' ? 13 + Math.cos(angle) / 100 : 13);
                    run.lat.push(kind === 'closed' ? 65.5 + Math.sin(angle) / 100 : 65.5);
                    run.ele.push(i);
                }
                cases.push({kind: kind, n: n, kept: garminPoints([run]).map(function (p) { return p.ele; })});
            });
        });
        saveFile('simplification.json', JSON.stringify(cases));
        saveStages().catch(function (error) { console.error(error); process.exitCode = 1; });
    """
    # Kept only in pytest's temporary directory, for diagnosis on failure.
    (directory / "writer.js").write_text(source, encoding="utf-8")
    result = subprocess.run([node, "-"], input=source, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return directory


class TestGarminExport:
    """Read the written GPX and ZIP independently of the JavaScript writer."""

    @staticmethod
    def read(directory, stem="Tour", garmin=False):
        suffix = "-garmin" if garmin else ""
        return etree.parse(str(directory / f"lomsdal-visten-{stem}{suffix}.gpx"))

    @staticmethod
    def vertices(tree, tag):
        return [(p.get("lon"), p.get("lat"), p.findtext("{*}ele")) for p in tree.findall(f".//{{*}}{tag}")]

    @pytest.mark.parametrize("stem", ["Tour", "Tour-Over-the-pass", "Tour-Down-home", "Tour-short"])
    def test_course_schema_structure_metadata_and_original_vertices(self, garmin_exports, stem):
        ordinary = self.read(garmin_exports, stem)
        course = self.read(garmin_exports, stem, True)
        schema = pathlib.Path(__file__).resolve().parents[2] / "fixtures/trails/io/export/gpx_1_1.xsd"
        etree.XMLSchema(etree.parse(str(schema))).assertValid(course)
        root = course.getroot()
        assert len(root.findall("{*}rte")) == 1
        assert not root.findall(".//{*}wpt")
        assert not root.findall(".//{*}trk")
        assert not root.findall("{*}rte/{*}extensions")
        assert {etree.QName(child).localname for child in root.find("{*}rte")} == {"name", "desc", "rtept"}
        assert etree.tostring(root.find("{*}metadata")) == etree.tostring(ordinary.find("{*}metadata"))
        assert course.findtext("{*}rte/{*}name") == ordinary.findtext("{*}trk/{*}name")
        assert course.findtext("{*}rte/{*}desc") == ordinary.findtext("{*}trk/{*}desc")
        full, kept = self.vertices(ordinary, "trkpt"), self.vertices(course, "rtept")
        assert 2 <= len(kept) <= 200
        assert (kept[0], kept[-1]) == (full[0], full[-1])
        assert set(kept) <= set(full)
        # Order matters too: the same points shuffled would pass set membership.
        cursor = iter(full)
        assert all(any(vertex == point for vertex in cursor) for point in kept)
        assert any(point[2] is None for point in kept)
        assert any(point[2] is not None for point in kept)
        if len(full) <= 200:
            assert kept == full

    def test_deviation_in_metres_across_the_joined_runs(self, garmin_exports):
        ordinary = self.read(garmin_exports)
        assert len(ordinary.findall(".//{*}trkseg")) == 2
        full = self.vertices(ordinary, "trkpt")
        kept = self.vertices(self.read(garmin_exports, garmin=True), "rtept")
        # Independent local projection, followed by Shapely point-to-line
        # distance on the coordinates actually written, including rounding.
        phi = math.radians(sum(float(p[1]) for p in full) / len(full))
        per_lat = 111132.92 - 559.82 * math.cos(2 * phi) + 1.175 * math.cos(4 * phi) - 0.0023 * math.cos(6 * phi)
        per_lon = 111412.84 * math.cos(phi) - 93.5 * math.cos(3 * phi) + 0.118 * math.cos(5 * phi)

        def projected(p):
            return ((float(p[0]) - 13) * per_lon, (float(p[1]) - 65.5) * per_lat)

        line = LineString([projected(p) for p in kept])
        deviation = max(Point(projected(p)).distance(line) for p in full)
        assert len(full) > 1000
        assert len(kept) == 200
        assert deviation < 15, f"{len(full)} -> {len(kept)} points, maximum deviation {deviation:.3f} m"
        print(f"Garmin test chain: {len(full)} -> {len(kept)} points; maximum deviation {deviation:.3f} m")

    def test_stages_keep_their_own_ends_names_and_archive_members(self, garmin_exports):
        whole = self.vertices(self.read(garmin_exports), "trkpt")
        first = self.read(garmin_exports, "Tour-Over-the-pass", True)
        last = self.read(garmin_exports, "Tour-Down-home", True)
        assert first.findtext("{*}rte/{*}name") == "A tour with its full name — Over the pass"
        assert last.findtext("{*}rte/{*}name") == "A tour with its full name — Down & home"
        assert self.vertices(first, "rtept")[0] == whole[0]
        assert self.vertices(last, "rtept")[-1] == whole[-1]
        assert self.vertices(first, "rtept")[-1] != whole[-1]
        assert self.vertices(last, "rtept")[0] != whole[0]
        expected = {f"lomsdal-visten-{stem}{suffix}.gpx" for stem in ("Tour", "Tour-Over-the-pass", "Tour-Down-home") for suffix in ("", "-garmin")}
        with zipfile.ZipFile(garmin_exports / "everything.zip") as archive:
            assert set(archive.namelist()) == expected
            assert archive.testzip() is None
            for name in expected:
                assert archive.read(name) == (garmin_exports / name).read_bytes()

    def test_ordinary_route_bytes_match_the_pre_garmin_writer(self, garmin_exports):
        # SHA-256 of these deterministic files produced by the writer before
        # Garmin was added (2026-09-20), with the same fixed metadata timestamp.
        expected = {
            "Tour": "f7cfdb2ab0f3c12729d174b71fbd3204f446bf8beb9001fde3233ebdcfabcf21",
            "Tour-Over-the-pass": "e04b32dbbf9a212e72bbb8f275ec655860b36ab02f31a37c2ec013c2bbb45a5d",
            "Tour-Down-home": "0237ed3c728d77c8d6765ca64ee2d66848cf690ddfd3afe23e65e0b333777fec",
            "Tour-short": "b166e18904dd59f0eb06ea3bcf6f868ba0cbf3504355488eea53e3ff6b305c6e",
        }
        for stem, digest in expected.items():
            assert hashlib.sha256((garmin_exports / f"lomsdal-visten-{stem}.gpx").read_bytes()).hexdigest() == digest

    def test_profile_downloads_match_the_plan_and_refuse_unfinished_routes(self, garmin_exports):
        delivered = json.loads((garmin_exports / "profile-files.json").read_text())
        assert [file["name"] for file in delivered] == ["lomsdal-visten-Tour.gpx", "lomsdal-visten-Tour-garmin.gpx"]
        for file in delivered:
            assert file["text"] == (garmin_exports / file["name"]).read_text()

    def test_short_degenerate_closed_and_repeated_lines(self, garmin_exports):
        for case in json.loads((garmin_exports / "simplification.json").read_text()):
            n, kept = case["n"], case["kept"]
            if n <= 200:
                assert kept == list(range(n))
            else:
                assert 2 <= len(kept) <= 200
                assert (kept[0], kept[-1]) == (0, n - 1)
                assert kept == sorted(set(kept))
                if case["kind"] == "repeated":
                    assert len(kept) == 2

    def test_ordinary_javascript_and_python_chain_geometry_and_credits_agree(self, garmin_exports, tmp_path):
        runs = json.loads((garmin_exports / "chain-points.json").read_text())
        coordinates = [(x, y, float("nan") if z is None else z) for x, y, z in zip(runs[0]["lon"], runs[0]["lat"], runs[0]["ele"], strict=True)]
        frame = gpd.GeoDataFrame(
            {"name": ["Test & chain"], "id": ["test-chain"], "ascent": [300.0]}, geometry=[LineString(coordinates)], crs="EPSG:4326"
        )
        settings = TestProfilePanel().exported()
        path, _ = export_to_gpx(
            frame,
            tmp_path / "python.gpx",
            name_field="name",
            title="Test & chain",
            description=settings["description"],
            sources=settings["credits"]["UT.no"] + settings["heights"],
            extension_fields=dict(settings["fields"]),
            ascent_method=settings["ascentMethod"],
        )
        python = etree.parse(str(path))
        javascript = etree.parse(str(garmin_exports / "chain.gpx"))
        python_points, javascript_points = self.vertices(python, "trkpt"), self.vertices(javascript, "trkpt")
        assert len(python_points) == len(javascript_points)
        for expected, actual in zip(python_points, javascript_points, strict=True):
            assert (float(actual[0]), float(actual[1])) == pytest.approx((float(expected[0]), float(expected[1])), abs=5.1e-8, rel=0)
            assert actual[2] == expected[2]
        assert python.findtext("{*}trk/{*}name") == javascript.findtext("{*}trk/{*}name")
        assert python.findtext("{*}metadata/{*}desc") == javascript.findtext("{*}metadata/{*}desc")
        for query in ("{*}metadata/{*}extensions/{*}source", "{*}trk/{*}extensions/*"):
            assert [(p.tag, dict(p.attrib), p.text) for p in python.findall(query)] == [
                (p.tag, dict(p.attrib), p.text) for p in javascript.findall(query)
            ]

    def test_every_download_entry_offers_the_course_with_the_same_refusal(self):
        panel = files("trails.visualization").joinpath("js", "profile_panel.js").read_text(encoding="utf-8")
        planning = files("trails.visualization").joinpath("js", "plan_mode.js").read_text(encoding="utf-8")
        assert "garminDownload.disabled = download.disabled;" in panel
        assert "saveMenu.appendChild(garminDownload);" in panel
        assert "offer.appendChild(garminDownload);" not in panel
        assert (
            panel.index("saveEntry('Whole tour (GPX)',")
            < panel.index("saveEntry('For Garmin (course)',")
            < panel.index("saveEntry('All stages (zip)',")
        )
        assert "function () { saveGarminNow(); }" in panel
        assert "garminFile.disabled = oneFile.disabled;" in planning
        assert "var garmin = file.cloneNode(false);" in planning
        assert "saveStage(stage, true);" in planning
        assert "saveWhole(true);" in planning
        assert "For Garmin (course)" in panel and "For Garmin (course)" in planning


class TestComposedProfile:
    """Tests for the second way into the panel, which a planned route uses."""

    def drawn(self) -> folium.Map:
        """A map carrying one chain and the panel."""
        gdf = gpd.GeoDataFrame(
            {"chain_id": ["ut-no-1-2-3"], "ascent": [996.4], "geometry": [LineString([(12.8, 65.4), (12.81, 65.41)])]},
            crs="EPSG:4326",
        )
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        layer = maps.add_trails(fmap, gdf, name="Chains", group_field="chain_id", figure_fields={"ascent": "ascent"})
        maps.add_profile_panel(fmap, [layer])
        return fmap

    def test_the_panel_offers_a_second_way_in(self):
        """A planned route has no chain and no row in the figures table."""
        html = self.drawn().get_root().render()
        assert "window.trailsProfilePanel" in html
        assert "series: function (spec)" in html
        assert "suspend: function (taken)" in html

    def test_one_walk_and_one_metre_are_handed_out_rather_than_copied(self):
        html = self.drawn().get_root().render()
        assert "layEdges: layEdges" in html
        assert "metresBetween: metresBetween" in html

    def test_a_composed_route_is_offered_as_a_file(self):
        """Phase 6 withheld the button because writing a plan out was its own
        phase. This is that phase, and restoring it is its visible outcome."""
        html = self.drawn().get_root().render()
        assert "function routeGpxOf(figure, shape, runs, plan, extra, crossings)" in html
        assert "saveFile(fileNameOf((selected.plan.stem) || EXPORT.route.fileStem)," in html

    def test_the_name_rides_with_the_bytes_and_not_only_on_the_anchor(self):
        """iOS Safari saves a `blob:` URL under the blob's own identifier and
        ignores `a.download`, which is a reader getting a line of hex where the
        tour should be — reported from the device, on a file this page had
        already named correctly. A `File` carries the name itself."""
        html = self.drawn().get_root().render()
        assert "new File([body], name, {type: type})" in html
        assert "anchor.download = name;" in html

    def test_a_finger_is_offered_the_share_sheet_where_there_is_one(self):
        """How a phone saves anything, and the one route that keeps the name
        whatever the browser does with the anchor. `canShare` decides it and not
        a user agent string: Chrome on Android refuses a `.gpx` there and falls
        through to the anchor, which on Android names the file correctly."""
        html = self.drawn().get_root().render()
        assert "navigator.share({files: [file]})" in html
        assert "return navigator.canShare({files: [file]});" in html
        # A closed sheet is not a failure, and saving the file anyway would be
        # doing something nobody asked for.
        assert "if (failure && failure.name === 'AbortError') { return; }" in html

    def test_the_button_most_routes_are_downloaded_with_names_the_tour(self):
        """It named none of them. This button took the export's own stem
        outright, so every route came off it as `-route.gpx` however carefully
        the tour had been named, while the stage buttons two panels away read
        `stem` and got it right. `stem` is the file's name; the export's stem is
        what a tour nobody named falls back to."""
        html = self.drawn().get_root().render()
        assert "saveFile(fileNameOf(EXPORT.route.fileStem)," not in html

    def test_the_file_says_what_the_panel_above_the_button_says(self):
        """One sentence written once. Handed `plan` instead of what the panel was
        told, the file quietly dropped the route's crossings from its own
        description while the panel went on showing them — a file that is
        plausible and silent about the one thing it breaks its track for."""
        html = self.drawn().get_root().render()
        assert "planned(figure, shape, extra).concat([markingLine(shape.tally)])" in html
        assert "routeGpxOf(selected.figure, selected.shape, selected.runs, selected.plan, selected.told, crossings())" in html

    def test_a_series_composed_without_a_description_is_not_offered(self):
        """The file has to say what its legs are and where its waypoints went. A
        button this panel could not honour is worse than no button at all."""
        html = self.drawn().get_root().render()
        assert "var writable = !!(selected && !selected.detail && (!selected.composed || selected.plan));" in html
        # And a place has no walk to write out at all: the mark would do nothing.
        assert "if (selected && selected.detail) { carries.textContent = ''; licensed.textContent = ''; return; }" in html
        assert "offer.style.display = writable ? 'block' : 'none';" in html
        # The mark stands in the row at the foot now, laid out as a box a thumb
        # can hit, so the condition has to be said to it as well.
        assert "download.style.display = writable ? 'flex' : 'none';" in html

    def test_a_route_with_a_hole_in_it_is_refused_and_said(self):
        """The file states that it breaks its track only at crossings. A leg
        still being worked out, or one the height service refused, would break
        it somewhere else with nothing in the file to say so."""
        html = self.drawn().get_root().render()
        # The plan is guarded for, because a composed route without one is the
        # way to a goal — which is never written to a file and therefore has
        # nothing to refuse.
        assert "download.disabled = !plan || points < 2 || !!plan.why;" in html
        assert "if (!selected.plan || selected.plan.why) { return; }" in html

    def test_the_panel_stops_answering_clicks_while_something_else_owns_them(self):
        html = self.drawn().get_root().render()
        assert "if (suspended) { return; }" in html
        assert "map.on('click', function (event) {" in html
        assert html.count("if (suspended) { return; }") >= 2

    def test_a_straight_stretch_is_dashed_in_the_curve(self):
        """The profile has to say the same thing the map does about the same
        ground, and a chain is never any of it."""
        html = self.drawn().get_root().render()
        assert "FREE_DASH" in html
        assert "current.free !== free" in html
        assert "drawn straight, not a path" in html

    def test_the_crossings_are_read_off_the_series_the_file_is_written_from(self):
        """The one series in this page with a point every few metres over the
        whole route. The vertices alone are a source's own corners, and a leg
        drawn straight has two of them for twenty kilometres."""
        html = self.drawn().get_root().render()
        assert "function crossingsOf(shape, runs)" in html
        assert "routeGpxOf(selected.figure, selected.shape, selected.runs, selected.plan, selected.told, crossings())" in html

    def test_the_crossings_are_asked_for_rather_than_worked_out_every_refresh(self):
        """Measured: the boundary walk is 45 ms of a 50 ms refresh over a 37 km
        route and it grows with the route, while the only thing that needs it is
        a button a reader may never press. Cached against the selection, so the
        file and a check still get one answer."""
        html = self.drawn().get_root().render()
        assert "if (!selected.crossings) { selected.crossings = crossingsOf(selected.shape, selected.runs); }" in html
        assert "crossings: crossings" in html
        # And not in the row that is rebuilt on every click.
        assert "selected.runs = runsOf(selected.shape);\n                var points = pointsIn(selected.runs);" in html

    def test_a_boundary_crossed_inside_a_break_is_still_a_pair(self):
        """Walk into a reserve, ferry out of it, carry on outside: the file used
        to say *Enters Sirijorda naturreservat* and never that the route left.
        `crossingsOf` restarted its list of what it was inside at every written
        run, and a crossing writes none -- so what happened across the break was
        lost in both directions."""
        html = self.drawn().get_root().render()
        # One list over the whole route, never restarted per run.
        assert "var before = [], last = null, started = false;" in html
        # The gaps stand in their place in the walk rather than beside it.
        assert "gaps.forEach(function (gap) { if (gap.before === r) { series.push(stepped(gap)); } });" in html

    def test_a_crossing_is_stepped_as_finely_as_the_runs_are(self):
        """A ferry from N50 has a source's corners and a water leg two points, so
        a boundary between two of them would put the marker at their midpoint --
        hundreds of metres out, where the runs are accurate to a few."""
        html = self.drawn().get_root().render()
        assert "var CROSSING_STEP_M = 5;" in html
        assert "/ CROSSING_STEP_M);" in html

    def test_beginning_inside_an_area_is_still_not_a_crossing(self):
        """The rule survives the rewrite: the route's own first point sets what
        it began inside and marks nothing."""
        html = self.drawn().get_root().render()
        walk = html[html.index("var before = [], last = null, started = false;") :]
        walk = walk[: walk.index("return out;")]
        assert "if (started) {" in walk
        assert "started = true;" in walk

    def test_only_the_areas_the_route_reports_get_a_marker(self):
        """The threshold is applied once, where the figures are, so a boundary
        grazed for ten metres cannot bring a pair of markers in through this
        door after the sentence above declined to mention it."""
        html = self.drawn().get_root().render()
        assert "(shape.protected || []).forEach(function (area) { reported[area.id] = area; });" in html
        assert "if (reported[id] && before.indexOf(id) < 0)" in html

    def test_a_boundary_marker_says_it_was_generated(self):
        """Phase 8 loads a file back and must never read a marker the map placed
        as a station somebody chose, or a loaded route gains points nobody put
        down and starts routing through them."""
        html = self.drawn().get_root().render()
        assert "EXPORT.waypoint.generated, crossing.id" in html
        assert "EXPORT.waypoint.set, null" in html

    def test_the_areas_are_written_as_figures_and_not_as_a_sentence(self):
        """A sentence has to be parsed back, and phase 8 has to know which
        boundary was meant rather than which words were written."""
        html = self.drawn().get_root().render()
        assert "EXPORT.route.areas" in html
        assert "EXPORT.route.areaId" in html
        assert "EXPORT.route.areaLength" in html

    def test_the_register_is_credited_wherever_a_file_states_one_of_its_figures(self):
        """A file naming a source it did not draw on is exactly as wrong as one
        leaving a source out."""
        html = self.drawn().get_root().render()
        assert ".concat((shape.protected || []).length ? EXPORT.protected : []);" in html

    def test_what_protects_the_route_is_said_once_and_shown_twice(self):
        """The sentence above the button and the sentence in the file are one
        sentence, so the areas go into `planned` rather than beside it."""
        html = self.drawn().get_root().render()
        assert ".concat(extra || []).concat(protectedIn(shape));" in html
        assert "function protectedIn(shape)" in html

    def test_the_metre_is_the_ellipsoid_and_not_a_sphere(self):
        """Measured over 4,000 real edges: the sphere read 0.56 % short, which
        is 900 m on a 160 km route stating its own distance. Nothing scales a
        planned route onto a length it carries, because it carries none."""
        html = self.drawn().get_root().render()
        assert "111132.92" in html
        assert "111412.84" in html
        assert "110574" not in html


class TestLegend:
    """The legend, which is also the map's layer control."""

    @staticmethod
    def points(show=True):
        """A one-point layer to hang a legend row on."""
        return gpd.GeoDataFrame({"name": ["Hut"]}, geometry=[Point(13.0, 65.5)], crs="EPSG:4326"), show

    def test_legend_renders_entries(self):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(fmap, "Lomsdal-Visten", {"Turrutebasen": "#1b5e20"})

        html = fmap.get_root().render()
        assert "Lomsdal-Visten" in html
        assert "#1b5e20" in html

    def test_a_row_given_a_layer_switches_it(self):
        """The legend replaced the layer control, so this is the only thing on
        the page that can put a layer on the map or take it off."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        gdf, _ = self.points()
        layer = maps.add_points(fmap, gdf, name="Huts")
        maps.add_legend(fmap, "Legend", [maps.LegendRow("Huts (1)", "#800080", layer)])

        html = fmap.get_root().render()
        assert "tick.type = 'checkbox';" in html
        assert "standAs(layer, tick.checked);" in html
        assert "if (want && !map.hasLayer(layer)) { map.addLayer(layer); }" in html
        assert layer.get_name() in html.split("var layers = [")[1].split("]")[0]

    def test_a_row_without_a_layer_switches_nothing(self):
        """A mapping still gives a legend that only explains colours, and those
        rows keep the checkbox's width so the labels line up with the ones that
        have a box."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(fmap, "Legend", {"Turrutebasen": "#1b5e20"})

        html = fmap.get_root().render()
        assert "var layers = [null];" in html
        assert "width:13px;flex:none" in html

    def test_a_layer_that_starts_off_is_taken_off(self):
        """**Folium's layer control did this in its own template**, so with that
        control gone the legend has to: a layer added with show=False is on the
        map like any other until something removes it. It is the build's `show`
        that says so, and since the rows are remembered it is the fallback for a
        row the reader never touched rather than the last word on it."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        gdf, _ = self.points()
        layer = maps.add_points(fmap, gdf, name="Huts", show=False)
        maps.add_legend(fmap, "Legend", [maps.LegendRow("Huts (1)", "#800080", layer)])

        html = fmap.get_root().render()
        assert '"shown": false' in html
        assert "? !!row.shown : layersKept[row.label] === 'on';" in html
        assert "if (!want && map.hasLayer(layer)) { map.removeLayer(layer); }" in html

    def test_the_base_maps_become_radio_buttons(self):
        """And only the one asked for stays on the map, for the same reason:
        folium hands every base layer to the map and left the unwanted ones to
        the control's template. Which one is asked for is the reader's last
        choice where they made one, and the build's otherwise."""
        # Two sheets, asked for: neither map offers a second one now (§6.10), and
        # what is being driven here is the control rather than either map's choice.
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7), extra_bases=(maps.BaseMap.KARTVERKET_GRAYSCALE,))
        maps.add_legend(fmap, "Legend", {"x": "#000000"})

        html = fmap.get_root().render()
        assert '["Kartverket Topo", "Kartverket Grayscale"]' in html
        assert "[true, false]" in html
        assert "pick.type = 'radio';" in html
        assert "var wantBase = wantedBase >= 0 ? index === wantedBase : !!baseShown[index];" in html
        assert "standAs(layer, wantBase);" in html

    def test_nothing_else_adds_a_layer_control(self):
        """Two controls over one list is two places to look and two to drift."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(fmap, "Legend", {"x": "#000000"})

        assert not [child for child in fmap._children.values() if isinstance(child, folium.LayerControl)]
        assert not hasattr(maps, "finalize")

    def test_a_switched_off_row_says_so(self):
        """A colour for something not on the map is still the key to that
        colour, but it is not speaking for the terrain."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(fmap, "Legend", {"x": "#000000"})

        html = fmap.get_root().render()
        assert "row.line.style.opacity = (row.layer && !map.hasLayer(row.layer)) ? '0.45' : '';" in html

    def test_the_wheel_is_the_map_s_where_the_list_cannot_scroll(self):
        """A list this long that will not scroll is as useless as a map that
        will not zoom, and only one of the two can have any one turn."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(fmap, "Legend", {"x": "#000000"})

        html = fmap.get_root().render()
        assert "var room = box.scrollHeight - box.clientHeight;" in html
        assert "if (room <= 0) { return; }" in html


class TestTextLabelColours:
    """Tests for per-label colouring in add_text_labels."""

    @pytest.fixture
    def typed_names(self) -> gpd.GeoDataFrame:
        """A river and a valley with their own colours, plus one without."""
        return gpd.GeoDataFrame(
            {
                "name": ["Vefsna", "Eiterådalen", "Namnlaus"],
                "color": ["#0288d1", "#6d4c41", None],
                "geometry": [Point(13.1, 65.7), Point(13.14, 65.6), Point(13.2, 65.5)],
            },
            crs="EPSG:4326",
        )

    def _html(self, group) -> list[str]:
        """Collect the rendered HTML of every label in a group."""
        markers = [child for child in group._children.values() if isinstance(child, folium.Marker)]
        icons = [next(c for c in m._children.values() if isinstance(c, folium.DivIcon)) for m in markers]
        return [icon.options["html"] for icon in icons]

    def test_colour_field_sets_each_label_individually(self, typed_names):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, typed_names, name="Names", color_field="color")

        html = " ".join(self._html(group))
        assert "color:#0288d1" in html
        assert "color:#6d4c41" in html

    def test_missing_colour_falls_back_to_the_default(self, typed_names):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, typed_names, name="Names", color_field="color", color="#455a64")

        assert any("color:#455a64" in html for html in self._html(group))

    def test_without_a_colour_field_all_labels_share_one_colour(self, typed_names):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, typed_names, name="Names", color="#37474f")

        assert all("color:#37474f" in html for html in self._html(group))


class TestLegendEscaping:
    """Legend text must survive characters that would otherwise start a tag."""

    def test_a_label_that_would_start_a_tag_stays_a_label(self):
        """The map's own legend reads "Paths, approach ≤15 km". Built as markup
        the browser would read "<15 km ..." as a tag and drop the whole row, so
        a label is written as text and can no longer make markup at all.
        """
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(fmap, "Legend", {"Paths, approach <15 km [OSM] (1965)": "#ce93d8"})

        html = fmap.get_root().render()
        assert "name.textContent = row.label;" in html
        # It survives whole, and as an escape rather than as a live "<".
        assert "Paths, approach \\u003c15 km [OSM] (1965)" in html
        assert "approach <15 km" not in html

    def test_boundary_does_not_intercept_clicks(self, park):
        """It is drawn last, so an interactive fill would swallow every trail click."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_boundary(fmap, park, name="National park")

        assert '"interactive": false' in fmap.get_root().render()

    def test_title_cannot_inject_markup(self):
        """The heading is written as text, so markup in it stays text."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(fmap, "A <b>bold</b> title", {"x": "#000000"})

        html = fmap.get_root().render()
        assert "<b>bold</b>" not in html
        assert "bold" in html

    def test_nothing_can_close_the_script_block(self):
        """A value carrying </script> would end the block and start markup."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_legend(fmap, "T </script><img src=x>", {"Also </script> here": "#000000"})

        html = fmap.get_root().render()
        assert "</script><img" not in html
        assert "\\u003c/script>" in html

    def test_popup_values_are_escaped(self, trails):
        """The escaping moved into the browser with the table; see
        `TestPopupText`. What the build must not do is escape it twice, or a
        name with an ampersand in it arrives reading `&amp;amp;`."""
        gdf = trails.copy()
        gdf["trail_name"] = "Sti <b>merket</b>"
        shape = maps._popup_shape(gdf, {"trail_name": "Route"})

        assert maps._popup_values(gdf.iloc[0], shape) == ["Sti <b>merket</b>"]

    def test_label_text_is_escaped(self):
        gdf = gpd.GeoDataFrame({"name": ["Dal <test>"], "geometry": [Point(13.1, 65.6)]}, crs="EPSG:4326")
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, gdf, name="Names")

        marker = next(child for child in group._children.values() if isinstance(child, folium.Marker))
        icon = next(c for c in marker._children.values() if isinstance(c, folium.DivIcon))
        assert "&lt;test&gt;" in icon.options["html"]


class TestTextLabelSymbols:
    """Tests for the glyph drawn before a label."""

    @pytest.fixture
    def typed_names(self) -> gpd.GeoDataFrame:
        """A valley and a river with glyphs, plus one without."""
        return gpd.GeoDataFrame(
            {
                "name": ["Eiterådalen", "Vefsna", "Namnlaus"],
                "symbol": ["∨", "≈", None],
                "geometry": [Point(13.14, 65.6), Point(13.1, 65.7), Point(13.2, 65.5)],
            },
            crs="EPSG:4326",
        )

    def _html(self, group) -> list[str]:
        """Collect the rendered HTML of every label in a group."""
        markers = [child for child in group._children.values() if isinstance(child, folium.Marker)]
        icons = [next(c for c in m._children.values() if isinstance(c, folium.DivIcon)) for m in markers]
        return [icon.options["html"] for icon in icons]

    def test_symbol_precedes_the_name(self, typed_names):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, typed_names, name="Names", symbol_field="symbol")

        assert any("∨ Eiterådalen" in html for html in self._html(group))
        assert any("≈ Vefsna" in html for html in self._html(group))

    def test_missing_symbol_leaves_the_name_alone(self, typed_names):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, typed_names, name="Names", symbol_field="symbol")

        assert any(">Namnlaus</div>" in html for html in self._html(group))

    def test_no_symbol_field_means_plain_names(self, typed_names):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, typed_names, name="Names")

        assert all(" " not in html for html in self._html(group))

    def test_symbols_are_escaped_like_the_name(self, typed_names):
        gdf = typed_names.copy()
        gdf.loc[0, "symbol"] = "<b>"
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_text_labels(fmap, gdf, name="Names", symbol_field="symbol")

        assert any("&lt;b&gt;" in html for html in self._html(group))


class TestChrome:
    """Tests for the rail, the burger, and the one sheet under both."""

    def test_one_sheet_holds_whatever_is_read_in_it(self):
        """What is still read in it — the plan panel's own *i*, which is about a
        file that was loaded rather than about the route — and anything else the
        page has that is to be read rather than glanced at. Two full-screen
        surfaces on a phone would be two things that have to agree about which is
        on top, which is the defect this chrome exists to end, so it is written
        once. A popup no longer comes here at all: it is a page of the panel, and
        this is the fallback for a page built without one."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "function readInSheet(title, content, asHtml, key)" in html
        assert "readInSheet(titleFor(popup), content, true, 'popup')" in html
        assert "detail: function (title, node, key) { readInSheet(title, node, false, key); }," in html
        # A popup's content is markup and a caller's string is text, told apart
        # by the caller rather than sniffed at: the day something guesses is the
        # day a place name with an ampersand in it becomes an element.
        assert "if (asHtml) { wrap.innerHTML = content; } else { wrap.textContent = content; }" in html

    def test_a_popup_becomes_a_page_of_the_panel(self):
        """It used to become a sheet over the whole screen, which answered *what
        did I just tap* by covering the thing that had been tapped, the curve it
        drew and the map it was on. It goes to the panel now — beside the profile
        where the tapped thing has one, alone where it has not, which is what a
        place gets — and only a page with no panel falls back to the sheet."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "window.trailsProfilePanel.detail(titleFor(popup), content, isPoint);" in html
        # **And it says which kind of thing it came off.** A place replaces
        # whatever was chosen; a line's popup is that line's own second page.
        # A marker has one position, a line has many.
        assert "var isPoint = !!(source && source.getLatLng && !source.getLatLngs);" in html
        # Asked first, and the sheet only where there is nothing to ask.
        assert html.index("window.trailsProfilePanel.detail(titleFor(popup)") < html.index("readInSheet(titleFor(popup), content, true, 'popup')")

    def test_the_row_at_the_foot_stands_for_a_selection_or_a_plan(self):
        """Plan mode had a bar of its own and it stood above the profile panel's
        heading — its figures over the panel's figures, its profile switch over
        the panel's own — so two rows said two versions of *what you are looking
        at*. There is one row, it belongs to the panel, and what plan mode has to
        say is pushed into it."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "trails-planbar" not in html
        assert "var standing = !!(selection || planOn());" in html
        assert "window.trailsProfilePanel.planning(summary);" in html
        # Two answers, not one: the row stands, and the pages are the switch.
        assert "if (pager.pages().open !== want) { pager.page(want ? true : false); }" in html

    def test_the_picker_owns_the_next_tap_whatever_else_does(self):
        """It is the one switch on this map that has to work in every mode — so
        it is not a fourth thing asking politely. Plan mode takes every click on
        the container in the capture phase and stops it there, and a line's click
        is taken by the highlight, the panel and its popup; this is a capture
        handler on the same container that stops the click where it lands, and
        plan mode asks it first whether it may have the tap at all."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "if (!picking || overChrome(event)) { return; }" in html
        assert "event.stopPropagation();\n                copyHere(event);" in html
        # The same two facts plan mode's own handler is built from: what is not
        # terrain, and how far a pointer may roll and still be a tap.
        assert "var slop = window.trailsReach ? window.trailsReach.slop() : 3;" in html
        assert "picking: function (want) { return askPicking(want); }," in html

    def test_a_position_is_five_decimals_and_the_page_says_what_it_did(self):
        """Five decimals is a metre and a bit at this latitude — finer than a
        phone's own fix and coarse enough to read out loud. And Safari writes to
        the clipboard only from a gesture it believes in, so a refusal leaves the
        text on the screen, selectable, rather than the page claiming something
        it did not do."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "return where.lat.toFixed(5) + ', ' + where.lng.toFixed(5);" in html
        assert "after.textContent = went ? 'copied' : '\u2014 copy it by hand';" in html
        assert "pickTimer = sticky ? null : window.setTimeout(hideCopied, 2600);" in html
        # **Nothing is said before the fact.** A reader who armed a picker knows
        # what a tap does, and a line telling them so is a line over the ground
        # they are aiming at: arming draws no message at all.
        armed = html.split("function askPicking(want) {")[1].split("}")[0]
        assert "sayCopied" not in armed
        assert "hideCopied" in armed

    def test_the_height_comes_off_the_network_where_there_are_no_tiles(self):
        """Where the map carries no height raster, the only heights it has are
        the ones sampled every 5 m along the network, in the routing graph — so a
        tap on a path can be told its height and a tap on an open hillside
        cannot, and the honest thing is to say the first and stay quiet about the
        second rather than quote a number about somewhere else. That is the first
        map, and on the second it is the fallback: the tile that is not there,
        off the model's edge or offline over ground that was never kept.

        Measured on the built graph before this was written: 949,704 vertices,
        and a scan over every one of them is 3 ms — once per tap, which is why
        there is no index here to keep in step with the geometry."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "var NEAR_M = 100, EXACT_M = 25;" in html
        assert "if (!(shortest <= NEAR_M)) { return null; }" in html
        # The metre this page measures distance with, asked of the one place
        # that owns it: a second haversine here would be a second answer to
        # *how far is that*.
        assert "var far = panel.metresBetween;" in html
        # A tilde where it is not the tapped place's own height.
        assert "(high.away > EXACT_M ? '~' : '')" in html
        # Asked only where nothing better can be: a page with height tiles reads
        # the tapped pixel and this never runs, which is the next test.
        assert "var high = asking ? null : pathHeight(where.lat, where.lng);" in html
        # **And never copied.** What goes to the clipboard is what was asked for
        # — a position — and a height read off a path 30 m away would be a figure
        # somebody pastes into a note as if it were measured there.
        assert "navigator.clipboard.writeText(text)" in html
        assert "return where.lat.toFixed(5) + ', ' + where.lng.toFixed(5);" in html

    def test_the_tapped_place_has_its_own_height_where_the_map_carries_tiles(self):
        """A height model cut to the map's own grid is on the page already — for
        the legs of a planned route the network cannot carry — and it covers the
        whole box, not the paths in it. So the picker asks it, and asks the
        network's samples only where it has no answer: off the model's edge, or
        offline over ground that was never kept.

        **One reader, not two.** The panel that plans a route decodes these tiles
        and holds the last two dozen of them; a second decoder in the chrome
        would be a second answer to *how high is that*, and would fetch the same
        tile again to give it. The picker asks `window.trailsPlan.heightAt`,
        which is that reader asked about one point.

        **And the tap asks once.** A leg is asked for once and its profile is the
        whole point of it, so a leg retries; a tap is cheap to repeat, and a
        retry chain behind a message that fades after 2.6 s is a number nobody
        sees arrive."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)
        html = fmap.get_root().render()
        assert "window.trailsPlan.heightAt(where.lat, where.lng) : null;" in html
        # Nothing from the network's samples while a tile is in flight: one tap
        # would say two different numbers a moment apart.
        assert "var high = asking ? null : pathHeight(where.lat, where.lng);" in html
        # Read where the tap was, so nothing is approximate about it and the
        # tilde stays off.
        assert ": {metres: metres, away: 0};" in html
        # Not over a later tap, and not over a message already dismissed.
        assert "if (!found || turn !== pickTurn || pickSaid !== text) { return; }" in html
        # A tile that is not there is ground the model does not cover, and then
        # the network's nearest sample is all there is to say.
        assert "? pathHeight(where.lat, where.lng)" in html

        # The other half: the panel hands one out only where there are tiles.
        fmap, _ = TestPlanMode().drawn()
        maps.add_plan_mode(
            fmap,
            TestPlanMode().planned(heightsUrl="", heightsTiles=maps.PROVIDERS["lantmateriet"].heights.as_settings()),
        )
        with_tiles = fmap.get_root().render()
        assert "heightAt: PLAN.heightsTiles ? function (lat, lon) {" in with_tiles
        assert "return tileHeights({lon: [lon], lat: [lat]}, true).then(function (points) {" in with_tiles
        # One tile, asked once: `once` is the picker's, and a leg keeps the three
        # attempts.
        assert "return once ? fetchHeightTile(wanted[k][0], wanted[k][1], z)" in with_tiles

    def test_what_it_said_does_not_eat_the_next_tap(self):
        """It stands over the map, and the map is what is being tapped. Driven: a
        second position picked while the first was still on the screen landed on
        the message and did nothing at all — the handler steps around everything
        in the chrome, and this is in the chrome. A success is a notice and takes
        no pointer; a refusal is a thing to read, select and dismiss, and keeps
        one.

        **Three states now, because the same defect came back in a new shape.**
        *Tap the map to set a goal* has to stand for as long as the switch is
        armed, so it was said sticky — and sticky meant tappable, so a
        full-width band lay across the middle of the map and swallowed the very
        tap it was asking for. Staying and taking a pointer are two things, and
        only the second of them is what makes a message a control."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "pickToast.style.pointerEvents = sticky === true ? 'auto' : 'none';" in html
        # And a notice that stands is still a notice: no timer, no pointer.
        assert "pickTimer = sticky ? null : window.setTimeout(hideCopied, 2600);" in html
        # One line, and two things say things in it: what the picker copied, and
        # how accurate a fix is. A second line for the second would be two
        # surfaces on a phone that have to agree about which is on top.
        assert "function saySomething(text, sticky) {" in html
        assert "showSaid(!went);" in html

    def test_the_two_marks_stand_where_the_rail_is_not(self):
        """The rail is the desktop's answer and these are the phone's — the same
        two switches, drawn where the rail is hidden behind the burger. Measured
        on the desktop before this was built: an open tool ends at x 1334 and the
        rail begins at 1344, so a second stack there would collide with nothing
        and read as a second rail 362 px under the first."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "quick.style.display = (narrow && !covering) ? 'flex' : 'none';" in html
        # Above whatever is at the foot: the row of a selection, a keyboard, or
        # the 16 px the attribution is left.
        assert "var footRoom = Math.max(covered, size.y - floor, 16);" in html
        assert "quick.style.bottom = (footRoom + 12) + 'px';" in html
        # And on a wide screen it is a lamp in the rail, like plan mode's.
        assert "(tool.key === 'pick' && picking) ||" in html
        assert "{key: 'pick', label: 'Copy a position', width: 300, selector: null," in html

    def test_the_offline_tool_has_a_drawing_and_it_says_which_state_it_is_in(self):
        """It had none at all: `icon()` reads `ICONS[key]` and there was no
        `offline` entry, so the row on a phone was a heading and a hint beside an
        empty column. The two it has now share a tray — one thing in two
        conditions, not two things — and the reader is told from the row whether
        the ground is on the device."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert 'offline: \'<path d="M9 2.9v7.5"/>' in html
        assert 'offlineKept: \'<path d="M5.6 6.9 8.1 9.4l4.6-5"/>' in html
        assert "icon(tool.key === 'offline' && offlineOn() ? 'offlineKept' : tool.key)" in html
        # Both places the tool is drawn ask the same question, or the rail and
        # the menu would disagree about the same switch.
        assert "iconFor(tool) + '</span>'" in html
        assert "button.innerHTML = iconFor(tool);" in html

    def test_the_switch_is_announced_so_the_row_behind_it_can_follow(self):
        """The switch is thrown inside the offline panel, which on a narrow
        screen is covering the menu at the time. Announced on every refresh and
        not only on the toggle: the worker settles after load and a download
        finishing changes the answer too, and neither is a click."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "new CustomEvent('trails:offline', {detail: snapshot})" in html
        assert "document.addEventListener('trails:offline', function () {" in html
        # And it lights on the rail while it is on, as plan mode and the
        # position watch already do — the three tools that outlive their panel.
        assert "(tool.key === 'offline' && offlineOn())" in html

    def test_the_last_one_opened_is_the_one_drawn(self):
        """On a narrow screen the dock, the menu and the detail are one
        full-screen sheet and only one may be drawn. Which one used to be fixed —
        a tool always covered the detail — so a reader pressing the panel's own
        *i* watched the plan panel go and got nothing back when they closed the
        sheet."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "function raise(what) { opening += 1; opened[what] = opening; }" in html
        assert "var top = narrow ? topmost() : null;" in html
        # And the sheet dismisses nothing: what it covers on a narrow screen it
        # gives back when it closes.
        assert "openTool = null;\n                menuOpen = false;\n                paintRail();" not in html
        assert "closeDetail: function () { closeSheet(); }," in html

    def test_one_state_decides_whether_the_profile_stands(self):
        """Three places offer the switch — the rail, the plan bar and the plan
        control — and a second flag beside this one is two switches that can
        disagree. Three values and not two: null means nobody has said, and the
        default then depends on where the reader is."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "profileAsked = (want === undefined || want === null) ? !profileOn() : !!want;" in html
        assert "return profileAsked === null ? profileDefault() : profileAsked;" in html
        # While planning on a narrow screen the map is what is being tapped.
        assert "return !(mapRoom().x < NARROW && planOn());" in html
        assert "profile: function (want) {" in html

    def test_the_rail_takes_the_corner_the_burger_already_has(self):
        """It stood at the left and pushed Leaflet's whole top-left corner 56 px
        aside to make room — which put the zoom buttons at 66, exactly where the
        dock opened, so every tool a reader opened covered the zoom. Moved to the
        right it needs room from nobody, and nothing touches a corner it did not
        make."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "rail.style.cssText = 'position:absolute;right:10px;top:10px;width:46px" in html
        assert "corner.style.marginLeft" not in html
        assert "dock.style.right = '66px';" in html


class TestTheme:
    """Tests for the two sets of colours the furniture is drawn from."""

    def test_three_blocks_and_not_two(self):
        """A web page has three theme states, not two: an explicit choice stamps
        `data-theme` on the root and the default setting stamps nothing at all,
        so `prefers-color-scheme` alone separates light from dark for most
        readers while a stamped choice has to beat it in both directions."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))

        html = fmap.get_root().render()
        assert ":root {" in html
        assert "@media (prefers-color-scheme: dark)" in html
        assert ':root:not([data-theme="light"])' in html
        assert ':root[data-theme="dark"]' in html
        # Native controls — the legend's checkboxes, the search field — are the
        # browser's to paint, and this is how it is told which set to use.
        assert "color-scheme: dark;" in html

    def test_the_data_keeps_its_own_colours(self):
        """The four gradient bands, the route's black and the sea line are
        statements about the ground, not furniture. Green meaning *gentle* in the
        morning and something else at night would be the drawing lying to keep up
        with the panels."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        gdf = gpd.GeoDataFrame(
            {
                "chain_id": ["ut-no-1-2-3"],
                "ascent": [996.4],
                "geometry": [LineString([(12.8, 65.4), (12.81, 65.41)])],
            },
            crs="EPSG:4326",
        )
        layer = maps.add_trails(fmap, gdf, name="Chains", group_field="chain_id", figure_fields={"ascent": "ascent"})
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        for _, _, colour, _ in maps.GRADIENT_BANDS:
            assert colour in html
        assert "var ROUTE = '#111111'" in html or "'#111111'" in html
        assert "var SEA = '#4fa3c7';" in html

    def test_the_reader_can_choose_the_set_and_the_choice_is_kept(self):
        """The three CSS blocks were written for a switch that did not exist,
        and the docstring said so. This is the switch: auto, light, dark, kept
        on the device, reachable from the rail on a wide screen and from the
        menu on a narrow one."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "window.trailsTheme = {" in html
        assert "{key: 'theme', label: 'Theme'" in html
        for choice in ("auto", "light", "dark"):
            assert f"{{key: '{choice}'" in html
        # **Auto removes the stamp rather than writing one.** The three blocks
        # are built on that: `data-theme="auto"` would match neither the light
        # block nor the dark one.
        assert "if (choice === 'auto') { root.removeAttribute('data-theme'); }" in html
        assert "else { root.setAttribute('data-theme', choice); }" in html
        assert "window.localStorage.removeItem(KEY); }" in html

    def test_the_stamp_is_on_the_root_before_the_first_paint(self):
        """Applying a kept choice from the chrome's script would paint the page
        once in the wrong set and correct it in front of the reader — a white
        flash on a phone held at dusk, which is the moment the feature exists
        for. So it goes in the head, above everything that draws."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert html.index("window.trailsTheme = {") < html.index("var TOOLS = [")
        # And it survives a browser that refuses storage outright rather than
        # taking the whole theme down with it: Safari in private browsing throws
        # on the read, not only on the write.
        assert "} catch (blocked) { return 'auto'; }" in html

    def test_what_is_painted_with_attributes_is_told_to_redraw(self):
        """Everything drawn through CSS follows the stamp on its own. The
        elevation curve does not — it is the one thing here painted with SVG
        attributes read at stroke time — and a switch that moved every other
        surface and left the curve in the old set is the bug this prevents."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        gdf = gpd.GeoDataFrame(
            {
                "chain_id": ["ut-no-1-2-3"],
                "ascent": [996.4],
                "geometry": [LineString([(12.8, 65.4), (12.81, 65.41)])],
            },
            crs="EPSG:4326",
        )
        # The panel is drawn only where there is a figure to draw, so the field
        # is what puts its script on the page at all.
        layer = maps.add_trails(fmap, gdf, name="Chains", group_field="chain_id", figure_fields={"ascent": "ascent"})
        maps.add_profile_panel(fmap, [layer])

        html = fmap.get_root().render()
        assert "document.dispatchEvent(event);" in html
        assert "document.addEventListener('trails:theme', function () { render(); });" in html
        # The machine still decides on auto, so its own change is announced too.
        assert "media.addEventListener('change', function () { if (choice === 'auto') { tell(); } });" in html

    def test_auto_says_which_way_it_currently_falls(self):
        """*Auto* is the one answer a reader cannot check against the screen:
        light and dark are visible, and following-the-machine looks exactly like
        whichever one it landed on."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "Following this machine, which is asking for" in html
        assert "(api.dark() ? 'dark' : 'light')" in html

    def test_the_panel_keeps_no_copy_of_the_choice(self):
        """The head owns the choice because the stamp has to be on the root
        before the first paint. A panel holding its own copy would be a second
        answer able to disagree with the first."""
        panel = self.chrome()
        assert "var chosen = api ? api.choice() : 'auto';" in panel
        assert "if (window.trailsTheme) { window.trailsTheme.set(each.key); }" in panel
        # A page built without the theme still opens; the panel says why it can
        # turn nothing rather than throwing on the first click.
        assert "This page was built without the theme" in panel

    def test_a_docked_popup_is_headed_by_the_carried_name(self):
        """It read the line's own hover label, which is the label that is no
        longer drawn — so without this the info page would be headed *Details*
        for every line on the map. The panel owns the table of names; this asks
        it by class, and falls back to the label for a page that still has
        one."""
        chrome = self.chrome()
        assert "window.trailsProfilePanel.nameOf" in chrome
        assert "if (carried) { return carried; }" in chrome
        assert "if (source && source.getTooltip) {" in chrome
        assert "return 'Details';" in chrome

    @staticmethod
    def chrome():
        return files("trails.visualization").joinpath("js", "chrome.js").read_text(encoding="utf-8")

    def test_the_panels_say_their_own_ink(self):
        """Not one of them set a `color`: they inherited the document's black,
        which is right on a white panel and 1.4:1 on a dark one — measured in a
        browser, which is the only place it could have been."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))

        html = fmap.get_root().render()
        assert ".trails-profile-panel, .trails-plan-control, .trails-legend, .trails-search," in html
        assert "color: var(--trails-ink);" in html


class TestWhereTheReaderIs:
    """Tests for the reader's own position on the map."""

    def test_nothing_is_watched_until_it_is_asked_for(self):
        """A map that starts following a reader on its own has decided something
        for them. It watches when the mark is pressed and stops when it is
        pressed again, when the page is hidden, or when the browser refuses.

        **And nothing is asked twice.** What the mark opened used to be a panel
        whose whole content was a paragraph and a button called *Show my
        position* — a page asking a reader whether they meant what they had just
        asked for. The browser's own permission dialogue is not this page's and
        stays."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "navigator.geolocation.watchPosition(drawHere, failedHere," in html
        assert "function askHere(want) {" in html
        assert "var quickHere = quickMark('here', 'Where I am', function () { askHere(); });" in html
        assert "hereButton" not in html
        assert "window.addEventListener('pagehide', function () { stopHere(''); });" in html

    def test_the_accuracy_is_drawn_and_not_only_the_dot(self):
        """A fix is a claim with a radius on it — 8 m under an open sky, 300 m in
        a valley — and a page that draws it as a dot has thrown away the half
        that matters on a mountain."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "hereRing = L.circle(where, {radius: spread" in html
        assert "var claimed = Math.max(1, position.coords.accuracy || 0);" in html

    def test_the_accuracy_is_a_circle_and_not_a_sentence(self):
        """It was said in words as well, once, with the fix that moved the map —
        and a line of text is the wrong place for a quantity a map can draw: it
        is read once and then gone, while the ring is there for as long as the
        fix is, at the scale everything else here is drawn at.

        The ring stays true to scale and the core does not: 24 m is 12 px at z15
        and a third of a pixel at z10, so a ring that never shrank would be
        saying *this uncertain* on a map too coarse to mean it."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "hereRing = L.circle(where, {radius: spread" in html
        assert "hereRing.setRadius(spread);" in html
        assert "hereDot = L.circleMarker(where, {radius: 6," in html
        # Nothing says it in words any more; what is still said is why a fix did
        # not arrive, which is not a quantity.
        assert "Accurate to about" not in html
        assert "This browser was told not to share your position." in html

    def test_the_map_is_moved_once_and_never_again(self):
        """A map that re-centres on every fix cannot be read while walking: the
        reader pans to look ahead and the next fix takes it back. It moves on the
        first one, wherever that is — it used to stay put for a fix far from the
        view, which answered *where am I* by not showing them."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "if (hereFixes === 1) {" in html
        assert "goThere(where);" in html
        assert "awayFromView" not in html

    def test_a_route_on_the_panel_stays_in_the_picture(self):
        """A reader who has planned one is asking *where am I on this* and not
        *where am I*: inside its bounds the scale is theirs and only the middle
        moves; outside them the map opens far enough to hold both. Whatever the
        panel is showing counts as that route — a planned one and a tapped line
        alike, because there is only ever one and it is the one being looked
        at."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "function goThere(where) {" in html
        assert "var shape = window.trailsProfile && window.trailsProfile.shape;" in html
        assert "if (box.contains(where)) { map.panTo(where); return; }" in html
        assert "map.fitBounds(box.extend(where), {padding: [40, 40]});" in html
        # And with nothing on the panel, the fix decides the view on its own.
        assert "map.setView(where, Math.max(map.getZoom(), 13));" in html

    def test_a_position_anywhere_is_drawn(self):
        """It used to refuse a fix outside the ground this map draws and stop
        watching, on the grounds that a dot on a blank square is not an answer.
        It is one: it says *not here*, which a reader who has got off a bus in
        the wrong valley would rather be told than argued with."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "outsideMap" not in html
        assert "Your position is outside the ground this map draws" not in html

    def test_the_two_switches_are_not_in_the_menu(self):
        """They are the two marks at the foot on a narrow screen — which is the
        screen the menu is on — so a row for them there would be a second way to
        the same switch, one tap slower. The rail keeps both, because on a wide
        screen there are no marks and the rail is where every tool is."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "if (tool.quick) { return; }" in html
        assert "{key: 'here', label: 'Where I am', width: 300, selector: null, quick: true," in html
        assert "{key: 'pick', label: 'Copy a position', width: 300, selector: null, quick: true," in html

    def test_a_refusal_says_which_refusal_it_was(self):
        """Told not to share, no fix in time, and a device that cannot work it
        out are three different things, and only the first is the reader's own
        doing."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "var code = problem ? problem.code : 0;" in html
        assert "This browser was told not to share your position." in html
        assert "var why = code === 3" in html

    def test_a_fix_that_does_not_arrive_does_not_stop_the_watch(self):
        """Reported from the phone: under a cliff the first fixes often fail,
        and the watch used to stop itself over each one — so the reader pressed
        the mark again, and again, in the one place where pressing it is least
        likely to work. With a goal set it took away the place the way there was
        worked out from, every time.

        A refusal is the exception and still stops it: a browser told not to
        share a position answers once and never again, and a lamp left burning
        for it would be the page claiming to wait for something that is not
        coming."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        failed = html.split("function failedHere(problem) {")[1].split("\n            }")[0]
        assert "stopHere('This browser was told not to share your position.');" in failed
        assert "hereLost = {code: code, why: why, since: first ? Date.now() : hereLost.since};" in failed
        # Nothing else in there stops anything: that is the whole change.
        assert failed.count("stopHere(") == 1
        # And it is said once rather than on every timeout.
        assert "if (first) { saySomething(why); hereAgeing(true); askAgain(); }" in failed

    def test_a_drought_asks_again_by_itself(self):
        """Measured in a browser: once `watchPosition` has answered *position
        unavailable* it never calls back — not when a position becomes available
        again, not after a hundred seconds of one being there to have. The watch
        is finished and says so only by silence, which is why pressing the mark
        again is what has always worked, and why the reader was left doing it.

        Thirty seconds between tries, which is longer than the twenty the watch
        waits before giving up: a retry inside that window would keep throwing
        away the attempt that was about to answer. The first failure is the
        exception and asks at once, because the common case is one fix that
        failed."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "var HERE_WANTS = {enableHighAccuracy: true, maximumAge: 10000, timeout: 20000};" in html
        assert "var LOST_AGAIN_MS = 30000;" in html
        again = html.split("function askAgain() {")[1].split("\n            }")[0]
        # A new watch and not a one-off: whatever arrives has to land in
        # `drawHere` like every other fix, and a `getCurrentPosition` that
        # succeeded would leave nothing watching afterwards.
        assert "navigator.geolocation.clearWatch(hereWatch);" in again
        assert "hereWatch = navigator.geolocation.watchPosition(drawHere, failedHere, HERE_WANTS);" in again
        assert "if (hereWatch === null || !navigator.geolocation) { return; }" in again
        # One watch, asked for the same things from both places.
        assert html.count("watchPosition(drawHere, failedHere, HERE_WANTS)") == 2

    def test_a_position_it_cannot_confirm_is_drawn_red(self):
        """What the map knows when a fix fails is not nothing: it is *where you
        were*, which is the second best answer and the only one there is. The
        dot stands and turns red, the ring turns red and dashed, and the switch
        goes red with them — the half a reader sees without looking for it.

        The radius is left where the last fix put it. It is that fix's own claim
        and still true of it; growing it by a guessed walking pace would be the
        map inventing the one figure it does not have."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "var HERE_LOST = HERE_FACING;" in html
        paint = html.split("function paintHereColour() {")[1].split("\n            }")[0]
        assert "var colour = hereLost ? HERE_LOST : HERE_BLUE;" in paint
        assert "if (hereDot) { hereDot.setStyle({fillColor: colour}); }" in paint
        assert "dashArray: hereLost ? '5 4' : null" in paint
        # Nothing here touches the radius.
        assert "setRadius" not in paint
        # The two marks at the foot and the rail's lamp, from the same state.
        assert "[quickHere, hereWatch !== null, !!hereLost]].forEach(function (each) {" in html
        assert "var lost = tool.key === 'here' && hereLost && hereWatch !== null;" in html

    def test_how_old_the_dot_is_is_said_under_it(self):
        """A red dot says the device has stopped confirming it; a reader on a
        mountain has to know whether that started twenty seconds ago or twenty
        minutes, because that is the whole of how far they may have walked from
        the place it is drawn at. The ring cannot say it — it is the last fix's
        own claim and does not grow — so it is said in words.

        Rounded hard, and redrawn on a timer, because nothing else pushes a
        figure worked out from a clock."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        said = html.split("function lostSaid(since) {")[1].split("\n            }")[0]
        assert "if (mins < 1) { return 'no fix'; }" in said
        assert "if (mins < 60) { return 'no fix for ' + mins + ' min'; }" in said
        assert "return 'no fix for ' + Math.round(mins / 60) + ' h';" in said
        assert "hereLostSaid = aimText('trails-here-lost', 600, HERE_LOST);" in html
        assert "hereLostSaid.textContent = lostSaid(hereKept ? hereKept.when : null);" in html
        # A watch with no bearing and no compass still draws the marks, because
        # the words under the dot are now a reason to.
        assert "if (!hereDot || (hereBearing === null && hereFacing === null && !hereGoal && !hereLost)) {" in html
        ageing = html.split("function hereAgeing(on) {")[1].split("\n            }")[0]
        assert "paintHereMarks();" in ageing
        assert "}, LOST_AGAIN_MS);" in ageing
        assert "if (hereAgeTimer) { window.clearInterval(hereAgeTimer); hereAgeTimer = null; }" in ageing
        # A label left standing would come back with the group, which returns
        # for a goal or a compass reading long after the fix it was about.
        hidden = html.split("function paintHereMarks() {")[1].split("node.style.display = 'none';")[0]
        assert "hereLostSaid.setAttribute('display', 'none');" in hidden

    def test_the_last_place_is_what_the_goal_routes_from(self):
        """The goal is worked out from where the reader is standing and would
        otherwise have nothing to stand on at exactly the moment they most want
        the way there. It gets the last place the device was sure of, said to be
        the last place and dated."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "stale: !!hereLost, when: hereKept ? hereKept.when : null};" in html
        assert "lost: hereLost ? hereLost.why : null," in html
        # A fix ending the drought takes the red with it, and says nothing.
        assert "var wasLost = hereLost;" in html
        assert "if (wasLost) { hereAgeing(false); paintHereColour(); paintHere(''); }" in html
        # A watch switched off is not a watch that is failing.
        dropped = html.split("function dropHere() {")[1].split("\n            }")[0]
        assert "hereLost = null;" in dropped
        assert "hereAgeing(false);" in dropped

    def test_which_way_is_asked_of_whichever_can_say(self):
        """A phone reports a course over the ground only while it is moving, and
        several report none at all — so where the device says nothing, the
        bearing from the last fix far enough away is the answer, and a reader
        cannot tell the two apart. Under ten metres the two fixes are one place
        seen twice and a bearing off them spins with the noise."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "var MOVED_M = 10;" in html
        assert "function bearingBetween(from, to) {" in html
        assert "var told = position.coords.heading;" in html
        assert "if (told !== null && told !== undefined && !isNaN(told)) {" in html
        assert "} else if (hereFrom && moved >= MOVED_M) {" in html
        assert "hereBearing = bearingBetween(hereFrom, where);" in html
        # The metre is asked of the one place that owns it rather than worked
        # out a second time here.
        assert "var far = window.trailsProfilePanel && window.trailsProfilePanel.metresBetween;" in html

    def test_standing_still_keeps_the_last_direction_and_fades_it(self):
        """*How you came here* is worth more than nothing while a map is being
        read, which is exactly when nobody is walking. The angle stands and the
        fading is what says it is from before; only a watch switched off and on
        again starts with no direction at all."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "var strong = hereMoving ? 0.62 : 0.26;" in html
        assert "hereCone.setAttribute('fill-opacity', String(strong));" in html
        # Nothing in the standing branch clears the bearing.
        standing = html.split("hereBearing = bearingBetween(hereFrom, where);")[1].split("hereAt = where;")[0]
        assert "hereMoving = false;" in standing
        assert "hereBearing" not in standing
        # Switching off does clear it, so the next watch starts blank.
        dropped = html.split("function dropHere() {")[1].split("\n            }")[0]
        assert "hereBearing = null;" in dropped
        assert "hereMoving = false;" in dropped

    def test_the_facing_rim_is_arcs_and_fills_nothing(self):
        """A needle over the dot covers the map it is pointing at. The rim is
        three bands round the core, brightest where the reader faces and running
        out behind them, with a white glow over the brightest so it reads on a
        sunlit tile — and every one of them `fill: none`, so the map shows
        through everywhere."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "var HALO_BANDS = [[70, 0.95, 3.2], [110, 0.5, 2.6], [160, 0.22, 2]];" in html
        assert "arc.setAttribute('d', arcPath(17, hereFacing - band[0] / 2, hereFacing + band[0] / 2));" in html
        assert "lit.setAttribute('d', arcPath(17, hereFacing - 36, hereFacing + 36));" in html
        rim = html.split("if (hereFacing !== null) {")[1].split("placeHereMarks();")[0]
        assert rim.count("setAttribute('fill', 'none')") == 2
        # Red, because facing is a different question from going and the cone
        # already owns the blue.
        assert "var HERE_FACING = '#d32f2f';" in html

    def test_the_compass_is_asked_for_on_the_press_that_starts_the_watch(self):
        """iOS gives orientation only after `requestPermission` and only from a
        gesture; the press on the mark is that gesture. One dialogue, on a press
        the reader made anyway — a refusal leaves the rim off and asks nothing
        further, and the watch that ends takes the listener with it."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "if (typeof DeviceOrientationEvent.requestPermission === 'function') {" in html
        assert "if (answer === 'granted') { listen(); }" in html
        assert "}, function () { /* refused, and nothing is asked again */ });" in html
        # Started with the watch and stopped with it, and the newer event name
        # where the browser has it.
        started = html.split("function askHere(want) {")[1].split("\n            }")[0]
        assert "startCompass();" in started
        assert "stopCompass();" in html.split("function stopHere(said) {")[1].split("\n            }")[0]
        assert "? 'deviceorientationabsolute' : 'deviceorientation';" in html
        assert "window.removeEventListener(hereCompass, heardCompass);" in html

    def test_the_compass_reading_is_turned_with_the_screen(self):
        """Safari reports degrees clockwise from north; everywhere else counts
        alpha the other way round. And a phone held sideways points across
        itself unless the screen's own angle is added back."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "facing = event.webkitCompassHeading;" in html
        assert "facing = (360 - event.alpha) % 360;" in html
        assert "turned = window.screen.orientation.angle;" in html
        assert "hereFacing = (facing + turned + 360) % 360;" in html

    def test_the_sensor_repaints_once_a_frame(self):
        """It fires some sixty times a second and every one of them would
        otherwise rebuild four arcs — the mistake this page has made twice, on a
        curve and on a drag."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "if (herePainting) { return; }" in html
        assert "herePainting = true;" in html
        assert "window.requestAnimationFrame(function () {" in html
        assert "if (hereWatch !== null) { paintHereMarks(); }" in html

    def test_the_marks_are_pixels_in_a_pane_of_their_own(self):
        """The cone and the rim are measured on the screen and not on the
        ground — the accuracy ring is the only mark here that is metres — so
        they are an SVG placed by hand and turned by an attribute, the idiom the
        direction arrow already uses, re-placed whenever the map moves under it.
        Just under the dot, so neither can cover it."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "pane = map.createPane('trailsHereMarks');" in html
        assert "pane.style.zIndex = HERE_MARKS_Z;" in html
        assert "pane.style.pointerEvents = 'none';" in html
        assert "L.DomUtil.setPosition(hereMarks, map.latLngToLayerPoint(hereAt));" in html
        assert "map.on('zoomend viewreset moveend resize', placeHereMarks);" in html
        # Nothing is drawn before there is anything to say — and the goal
        # counts as something: a reader who has just switched the position on
        # has no bearing and no compass yet, while *which way to the route* is
        # known from the first fix.
        assert "if (!hereDot || (hereBearing === null && hereFacing === null && !hereGoal && !hereLost)) {" in html

    def test_a_vaguer_fix_does_not_replace_a_sharper_one(self):
        """Standing still while the sky thins, the reported radius grows from
        8 m to 40 m without the reader having moved a step — and a ring redrawn
        at 40 m says the map has learnt something, when what happened is that it
        learnt less.

        Kept only while the new claim *contains* the old one, which is exactly
        the case where the new fix rules out nothing the old one had not already
        ruled out. Two discs that merely overlap are a reader who has walked
        off, and then the new fix wins — because keeping the smallest radius
        ever seen and re-centring it on a later fix 30 m away would be a precise
        claim about the wrong place."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "function keepingBetter(fix, spread, when) {" in html
        assert "if (!hereKept || spread <= hereKept.spread) { return null; }" in html
        assert "return (apart + hereKept.spread <= spread) ? hereKept : null;" in html
        # What is drawn is the better claim; what is remembered is what was drawn.
        assert "var kept = keepingBetter(fix, claimed, when);" in html
        assert "var where = kept ? kept.at : fix;" in html
        assert "var spread = kept ? kept.spread : claimed;" in html
        assert "if (!kept) { hereKept = {at: fix, spread: claimed, when: when}; }" in html

    def test_a_kept_fix_does_not_stand_for_ever(self):
        """Every fix after it says the same place and says it vaguer, so nothing
        breaks the hold on its own — but a reader walking slowly under a sky
        that is getting worse would be shown where they were a quarter of an
        hour ago. And a watch switched off keeps nothing at all: the next one is
        somebody somewhere else."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "var HOLD_MS = 90000;" in html
        assert "if (when - hereKept.when >= HOLD_MS) { return null; }" in html
        assert "var when = position.timestamp || Date.now();" in html
        dropped = html.split("function dropHere() {")[1].split("\n            }")[0]
        assert "hereKept = null;" in dropped

    def test_the_position_is_the_last_thing_drawn_on_the_map(self):
        """Reported from a phone: with a plan loaded the dot sat *under* the
        route. It was in the overlay pane at 400 and the route has a pane of its
        own at 460 — as do the profile's own marks at 450 and 470 — so anything
        the reader had asked the page to draw covered the one mark that answers
        a question nothing else on the map can.

        Over the marker pane at 600 as well: a place under the dot is still
        where it was and can be read by moving a finger, and the dot has nowhere
        else to be. Below the tooltips and popups, which are answers a reader
        asked for by touching something."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "var HERE_MARKS_Z = 610;" in html
        assert "var HERE_Z = 620;" in html
        assert "var pane = map.createPane('trailsHere');" in html
        assert "pane.style.zIndex = HERE_Z;" in html
        # Both layers are drawn into it, and neither takes a click: a pane over
        # the whole map that did would take them from every trail under it.
        assert "interactive: false, pane: herePane()," in html
        assert "interactive: false, pane: herePane()," in html.split("hereDot = L.circleMarker")[1]
        # And over every other pane this page makes, whichever part of it made
        # them: 350 offline, 450 and 470 for the profile's own marks, 460 for
        # the planned route, 465 for the line a reader chose. Read out of the
        # source rather than listed here, because a pane added later would
        # otherwise pass this quietly — as 465 did, on the run that added it.
        source = pathlib.Path(maps.__file__).read_text(encoding="utf-8")
        source += "".join(path.read_text(encoding="utf-8") for path in files("trails.visualization").joinpath("js").iterdir())
        made = [int(z) for z in re.findall(r"\.style\.zIndex = (\d+);", source)]
        assert made, "no pane z-index was found at all"
        # The popup pane is the exception and is meant to be: a popup is an
        # answer the reader asked for by touching something.
        # 462 is the way to a goal: over the planned route at 460, because a
        # goal is the more particular of the two and the one the reader set
        # last. Added on the run that added goals, deliberately.
        assert sorted(made) == [350, 450, 460, 462, 465, 470, 1050]

    def test_off_the_route_the_wedge_is_asked_and_not_derived(self):
        """Asked for from a phone: a mark saying which way the next goal is.
        Off the route that goal is the route — its nearest point, which is what
        getting back on it means.

        **How wide the wedge opens is put as a question to the accuracy circle
        the map already draws.** The reader could be anywhere in it, so the
        question is asked from a dozen places on its rim: *standing there, which
        way would I be sent?* The wedge is what those answers span.

        Which is not the bound this started as — every part of the route within
        ``d + 2r``, since that is provably where the nearest point of any
        position in the circle lies. That bound is true and far too generous:
        measured 62 m off a straight leg with a 22 m circle, it made 121° of a
        fan that is really 0°, because a straight line sends every position in
        the circle off at the same perpendicular. The bound is kept for the one
        thing it is good for — dropping everything the dozen questions need not
        look at."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "var AIM_SAMPLES = 12;" in html
        assert "var reach = best.away + 2 * spread;" in html
        assert "could.push([aLat, aLon, bLat, bLon]);" in html
        assert "var sent = nearestAmong(maybe, cosine, could);" in html
        # The bearing from where the reader might really be, and not from the
        # fix: which way to walk is a question asked where the walking starts.
        assert "var off = swung(bearingBetween(maybe, {lat: sent.lat, lng: sent.lon}) - to);" in html
        # And the wedge is not symmetric about the direction it points, so
        # there is no angle to turn it by the way the cone is turned.
        assert "function wedgePath(from, to, reach) {" in html

    def test_on_the_route_the_goal_is_the_next_waypoint_ahead(self):
        """The nearest point is then under the reader's feet and says nothing.
        Which way *along* the route to look is the direction they are going,
        read off the same bearing the cone is drawn from — and without one there
        is nothing for a goal to be ahead of, so the mark is not drawn.

        A goal already under the reader is not one either: the bearing to it
        spins with the noise, and somebody walking through a waypoint means the
        one after it."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        # **And some routes have only one way along them.** A way to a goal
        # runs from where the reader was to the thing they asked for, so *ahead*
        # is toward the goal and is not asked; a planned route has waypoints at
        # both ends of every leg and can be walked either way.
        assert "if (!target.goal) { return found; }" in html
        assert "var forward = target.oneWay ? 1" in html
        assert "(Math.abs(swung(hereBearing - best.way)) < 90 ? 1 : -1));" in html
        assert "var remains = forward > 0 ? (spans[leg] - best.run) : best.run;" in html
        assert "while (goal && remains <= spread) {" in html
        assert "if (spans[leg] === undefined) { goal = null; break; }" in html
        # A waypoint is one point and does not move about, so only the reader's
        # own circle opens the wedge here.
        assert "found.right = straight > spread" in html

    def test_a_wedge_too_wide_to_mean_anything_is_not_drawn(self):
        """Past a fan of 120° it says no more than *look around you*, and a mark
        pointing confidently into ground a reader could walk anywhere inside is
        worse than no mark. The other two silences are the same rule: nothing
        to aim at, and standing on the route with no direction of travel to say
        what *ahead* means."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "var AIM_WIDEST = 120;" in html
        assert "if (!hereGoal || wide > AIM_WIDEST || (hereGoal.on && !hereGoal.goal)) {" in html
        # And a floor, because under a couple of degrees a wedge is a hairline
        # the eye reads as a line rather than as a direction with a width.
        assert "var AIM_NARROWEST = 3;" in html
        assert "var pad = wide < AIM_NARROWEST ? (AIM_NARROWEST - wide) / 2 : 0;" in html

    def test_the_goal_follows_the_selection_and_not_only_the_fix(self):
        """The goal moves when the reader moves, and equally when what is
        selected changes or plan mode is switched. A mark still pointing at the
        line that was chosen before is worse than one that is not drawn.

        The spread it is worked out at is read off the ring rather than off the
        last fix: the ring is what is *drawn*, and where a better fix is being
        held the two are deliberately not the same number."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "function aimAgain() {" in html
        assert "? aimAlong(hereAt, hereRing.getRadius(), target) : null;" in html
        # Called from the fix, from choosing a line and from switching plan
        # mode — the three things that can change the answer.
        # The fix reaches the goal control first — it routes from where the
        # reader is, and this is the only place that knows they have moved.
        assert "window.trailsGoal.stood(where.lat, where.lng, spread);" in html
        # Four call sites: the fix, choosing a line, switching plan mode, and a
        # goal arriving or going — the four things that can change the answer.
        assert html.count("aimAgain();") == 4

    def test_which_line_the_mark_aims_at_is_not_a_choice_the_reader_makes(self):
        """Plan mode's route while it is being planned, and equally while it is
        simply what the panel is showing — leaving plan mode does not put a plan
        away, and a reader walking one wants the mark aimed at it either side of
        that line. Otherwise whatever line is selected, whose geometry is only
        ever on the layer: this map paints its vectors into a canvas, so a
        selection is a class name and there is no node to read."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "(planOn() || !!(showing && showing.composed && showing.plan))" in html
        assert "return {name: 'planned route', segments: plan.segments, goal: plan.goal};" in html
        assert "if (!layer.options || layer.options.className !== showing.className) { return; }" in html
        assert "if (got[0] instanceof L.LatLng) { rings.push(got); return; }" in html
        # A line picked off the map carries no waypoints, so what lies ahead on
        # it is where that ring ends — its own end and not the selection's.
        assert "var end = forward > 0 ? line[line.length - 1] : line[0];" in html

    def test_the_wedge_is_read_rather_than_measured_off_a_canvas(self):
        """A check cannot measure an angle off a canvas and should not have to
        read a path back to find one — and the two figures that matter, how wide
        the fan is and whether the mark is drawn at all, are a decision rather
        than a shape."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "aim: function () {" in html
        assert "wide: hereGoal.right - hereGoal.left, away: hereGoal.away," in html
        assert "drawn: !!(hereAim && hereAim.getAttribute('display') !== 'none')};" in html
        # And what it cost, because it is walked on every fix and a route can
        # be tens of thousands of vertices long. Recorded rather than guarded
        # against: the number is what says whether it needs guarding.
        assert "if (started) { hereAimMs = Math.round((window.performance.now() - started) * 10) / 10; }" in html

    def test_the_goal_is_the_only_green_on_this_map(self):
        """The cone says how the reader is going and the rim which way they are
        facing; this one says where to *go*, which is a different kind of
        statement and gets a different colour. The ways are brown and slate, the
        route is black, the position is blue and the compass red — so green is
        free, and its being free is the reason.

        The figure past the head is upright wherever the head points: a label
        turned with the mark would be upside down for half the compass."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "var HERE_GOAL = '#00a152';" in html
        assert "hereAim.setAttribute('fill', HERE_GOAL);" in html
        # Cased the way every line on this map is cased. Measured at 0.18 with
        # a white edge and nothing else: over contour lines and a stream the fan
        # was there to be found rather than seen.
        assert "hereAimEdge.setAttribute('stroke', '#ffffff');" in html
        assert "hereAim.setAttribute('stroke', HERE_GOAL);" in html
        assert "node.setAttribute('paint-order', 'stroke');" in html
        assert "function aimLabel(node, said, to, out) {" in html
        # And the name only where there is one to give: off the route the goal
        # *is* the route, and its name under the figure would be the mark
        # saying what it already is.
        assert "aimLabel(hereAimNamed, hereGoal.goal ? hereGoal.goal.name : null, hereGoal.to, 42);" in html

    def test_a_goal_outranks_the_plan_and_the_selection(self):
        """A plan is a tour made beforehand and a selection is something the
        reader tapped in order to read it; a goal is an instruction, set while
        walking, and it is the one line here that means *take me there*.

        And a routed goal that could not be given a way is still aimed at
        straight. A route that failed is not a reason to stop saying which way
        the goal lies — it is the reason the reader most wants to know."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        aiming = html.split("function aimTarget() {")[1].split("function aimSaid")[0]
        assert "var goal = window.trailsGoal ? window.trailsGoal.state() : null;" in aiming
        # Before either of the other two are so much as looked at.
        assert aiming.index("window.trailsGoal") < aiming.index("window.trailsProfile")
        # Whichever reading is standing, because both are a way now: keying
        # this on *routed* aimed the straight one past every stop the reader had
        # put down, at the goal beyond them.
        assert "if (goal.line) {" in aiming
        assert "straight: goal.way !== 'routed'};" in aiming
        assert "return {name: 'the goal', point: {lat: goal.at.lat, lon: goal.at.lon," in aiming

    def test_a_point_the_reader_set_needs_no_asking(self):
        """The wedge over a route is asked of a dozen places on the accuracy
        circle because a route moves the answer about — which point of it is
        nearest depends on where in the circle you are. A goal does not move.
        So the whole of the width is the reader's own circle turning a bearing
        to a fixed thing, which is ``asin(r / d)`` exactly, either side.

        Inside the circle there is no direction to give at all: 180 either way
        is 360, which is wider than anything is drawn at — the mark going quiet
        rather than a special case for arriving."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "if (target.point) {" in html
        assert "var straight = awayFrom(at, cosine, target.point.lat, target.point.lon);" in html
        assert "? Math.asin(Math.min(1, spread / straight)) * 180 / Math.PI : 180;" in html
        assert "left: -half, right: half, away: straight, on: straight <= spread," in html

    def test_on_a_route_the_head_follows_the_route(self):
        """Measured on a 19 km way to a goal: the bearing to the goal and the
        bearing of the path under the reader's feet were tens of degrees apart,
        and the path was right — a head pointing at the goal would send somebody
        across the lake the route goes round.

        So it follows the route a little way ahead: far enough not to shiver
        with the fix, near enough not to cut the corner, and the distance is the
        fix's own for both reasons. What the label names is unchanged — the goal
        and what is left of it."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "var AHEAD_M = 60;" in html
        assert "var AHEAD_SPREADS = 3;" in html
        # **A leg drawn straight is straight**, so the head looks to its far
        # end: cutting it at sixty metres would open the fan to what sixty
        # metres is worth rather than to what the walk is — measured, a goal
        # 9 km off went from a quarter of a degree to thirty-eight.
        assert "var look = target.straight ? remains : Math.max(AHEAD_M, AHEAD_SPREADS * spread);" in html
        assert "var mark = alongAt(target, cosine, Math.max(0, Math.min(whole, want))) || goal;" in html
        # The distance said is still the distance to the goal, and the point
        # marked is still the goal: only where the head points has changed.
        assert "found.away = remains;" in html
        assert "found.at = {lat: goal.lat, lon: goal.lon};" in html

    def test_the_flag_says_something_when_there_is_no_way_to_show(self):
        """Reported from the phone: a position typed into the search, set as a
        goal with the position switch off, and then the flag did nothing at all
        -- no page, no way to be rid of it, a green ring standing on the map for
        good. The panel draws the *way* to a goal and there is none until the
        page knows where the reader is, so the flag says that instead, and
        carries the three things they can do about it."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "if (!window.trailsGoal.showProfile() && !window.trailsGoal.show()) { goalAdrift(); }" in html
        assert "function goalAdrift() {" in html
        adrift = html[html.index("function goalAdrift() {") : html.index("function setGoalHere(event)")]
        assert "askHere(true)" in adrift
        assert "askAiming('move'" in adrift
        assert "window.trailsGoal.clear();" in adrift
        # The same question the panel's own drop asks, for the same reason.
        assert "window.confirm('Drop the goal and '" in adrift

    def test_the_goal_switch_arms_one_tap_and_lets_go(self):
        """A switch that stayed on would make every later tap a goal, which is
        the mistake plan mode is allowed to make because planning is a mode a
        reader is *in* and this is one thing they are doing.

        Never both switches at once, either: the picker owns the next tap while
        it is on, and two crosshairs over one map is a page that cannot say what
        a tap will do."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "function askAiming(want, at) {" in html
        assert "if (aiming && picking) { askPicking(false); }" in html
        assert "askAiming(false);" in html
        # **And it says nothing while it does it.** *Tap the map to set a goal*
        # stood over the ground while the lamp was lit and the crosshair was up,
        # and setting one answered *Goal set* under a target that had just
        # appeared where the tap landed: three ways of saying in words what had
        # been done in front of the reader. A page that explains its own obvious
        # acts teaches people to stop reading it. Reported from the phone.
        assert "'Tap the map to set a goal.'" not in html
        assert "'Goal set.'" not in html
        assert "'Goal cleared.'" not in html
        # A notice that stands is still one that takes no pointer — the trap
        # that hint fell into while it existed, and the rule that outlives it.
        assert "pickToast.style.pointerEvents = sticky === true ? 'auto' : 'none';" in html
        # **And a lit lamp pressed shows the goal.** It used to put the goal
        # away, on the argument that a switch that is *on* is switched off by
        # pressing it. Reported from the phone, twice over: a journey with
        # three stops lost to one press meant for something else, and no way
        # to bring the goal back on to the panel once another trail had been
        # tapped. Three states, one press — arm, let go, show — and putting a
        # goal away is a line in its own menu, in words.
        assert "function pressGoal() {" in html
        assert "if (aiming) { askAiming(false); return; }" in html
        assert "if (goalSet() && window.trailsGoal) {" in html
        assert "if (!window.trailsGoal.showProfile() && !window.trailsGoal.show()) { goalAdrift(); }" in html
        # The press itself still drops nothing -- what is below it is a page in
        # words, which is where putting a goal away belongs.
        pressed = html[html.index("function pressGoal() {") : html.index("function adriftStep(")]
        assert "window.trailsGoal.clear();" not in pressed
        assert "quickMark('goal', 'Set a goal', function () { pressGoal(); });" in html
        # And it is the tap and nothing else: no waypoint, no selection, no
        # popup, which is what the capture phase is for.
        assert "setGoalHere(event);" in html

    def test_a_place_is_offered_as_a_goal(self):
        """Nearly every goal a reader sets is a named thing — a hut, a quay, a
        summit — and the popup is the moment they have just read what it is.

        Added to the markup as the popup is docked, and not built into the popup
        itself: a popup is composed in the build out of a table of columns, and
        a control is not one of them. The listener is on the document because
        the button is markup the panel takes in as a page, so there is nothing
        here to hang one on — and Leaflet stops mousedown and dblclick on the
        panel and deliberately not click, which is what lets that work."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "function goalOffer(where, called) {" in html
        assert "content = (content || '') + goalOffer(source.getLatLng(), titleFor(popup));" in html
        assert "if (isPoint && window.trailsGoal) {" in html
        assert "event.target.closest('.trails-goal-take, .trails-stop-take, .trails-point-take')" in html
        # Escaped into the attributes it rides in, like every other name this
        # page takes out of somebody else's register.
        assert "'\" data-name=\"' + esc(called || '') + '\" '" in html

    def test_a_place_offers_what_can_be_done_with_it_now(self):
        """Asked for from the phone: coordinates as waypoints, and as stops on
        the way. A typed position is a place like any other by the time it is on
        the map, so the offer is made on every place's page and the search
        needed nothing for it -- but only where there is something to add to: a
        stop needs a goal to be on the way to, and a waypoint needs a plan."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        offers = html[html.index("function goalOffer(where, called) {") : html.index("var adopting = false;")]
        assert "if (goalNow && goalNow.at) {" in offers
        assert "'Add a stop on the way'" in offers
        # One offer while a plan stands, whether or not its mode is on -- with
        # the mode on every tap is a waypoint and nothing can be selected, so
        # this is pressed with the mode off, and it leaves the mode as it is:
        # bringing plan mode back would take the next place away again.
        assert "if (planOn() || planStanding()) {" in offers
        assert "'Add to the plan'" in offers
        assert "'Add a waypoint'" not in offers
        assert "function planStanding() { return !!(planState && planState.points > 0); }" in html
        source = files("trails.visualization").joinpath("js", "plan_mode.js").read_text(encoding="utf-8")
        placing = source[source.index("function place(lat, lon, exact) {") : source.index("function planFromPlaces(places) {")]
        assert "switchTo(" not in placing
        # None of the three snaps: a press on a page is not a finger on the map.
        assert "window.trailsGoal.addStop(lat, lon, called);" in offers
        assert "window.trailsPlan.place(lat, lon, true);" in offers

    def test_the_goal_is_the_only_green_line_this_map_draws(self):
        """The same green the position mark aims in, because they are one
        answer: the line is where to walk and the wedge is which way along it.
        A second green would read as a second thing."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)
        source = files("trails.visualization").joinpath("js", "plan_mode.js").read_text(encoding="utf-8")

        assert "var HERE_GOAL = '#00a152';" in fmap.get_root().render()
        assert "var GOAL_COLOUR = '#00a152';" in source

    def test_a_tap_does_not_leave_a_label_over_the_ground(self):
        """Leaflet opens a hover label on a *click* as well as on a hover — its
        own rule, and on a touch device a tap is a click — so tapping a place
        put its name over the map and left it standing there until something
        else was tapped: a second heading over the ground, saying what the row
        at the foot says and under the same name.

        The lines lost their labels outright when this was first reported. A
        place keeps its own, because a place is named by nothing else on this
        page — the docked popup is headed with it — so the label is closed
        rather than unbound, and only where the pointer is coarse. Permanent
        ones are left alone outright: those are the map's own labelling, which
        is what a reader is reading the ground by."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "map.on('tooltipopen', function (event) {" in html
        assert "if (!event.tooltip || event.tooltip.options.permanent) { return; }" in html
        assert "if (!container.classList.contains('trails-coarse')) { return; }" in html
        assert "map.closeTooltip(event.tooltip);" in html

    def test_the_plan_s_points_come_and_go_with_the_selection(self):
        """Whether the route's own numbered discs are drawn depends on which
        route the panel is showing, so a selection changing is when they come and
        go. Dressed and not repainted: repainting composes the whole route to
        find out what to draw."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "if (window.trailsPlan && window.trailsPlan.dress) { window.trailsPlan.dress(); }" in html

    def test_the_switch_knows_what_the_next_tap_will_do_and_says_nothing(self):
        """A goal, a stop on the way to it and a place already set being put
        somewhere else are all set by the same gesture and are not the same act,
        so the switch carries which one it is armed for rather than being a
        flag — and the row at the foot lights the button or the row that armed
        it. Nothing is said over the map: the stop's hint was the last notice
        standing there, and it stood across the ground the tap was meant for.
        Reported from the phone, and it went.

        **And a tap while armed for a stop adds one, and only that.** It used
        to take a stop away as well when it landed on one, and the one thing
        that said so was the hint. A gesture with two meanings and nothing to
        say which is not a gesture; taking a stop away is in the list at the
        foot now, in words.

        The stop's own button is in the row at the foot and not in the rail: the
        rail arms the one thing a reader does with nothing set, and a stop is
        something they add to a journey that already exists."""
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)

        html = fmap.get_root().render()
        assert "var wanted = want === 'stop' ? 'stop' : want === 'move' ? 'move'" in html
        # No notice and nothing left that could raise one: the code that said
        # the hint is gone, not just the words.
        assert "'Tap the map to add a stop" not in html
        assert "sayAiming" not in html
        assert "aimNotice" not in html
        assert "if (aiming === 'stop') {" in html
        assert "window.trailsGoal.dropStop(standing);" not in html
        assert "window.trailsGoal.stopAt(" not in html
        assert "window.trailsGoal.addStop(called.lat, called.lon, called.name);" in html
        # **A move is armed for one place, and the tap goes to that place.**
        # The last of the goal's list is the goal and keeps its stops; any
        # other is a stop and keeps its place in the order. Armed for a move
        # with no place named is not armed at all.
        assert "if (aiming === 'move') {" in html
        assert "aimingAt = wanted === 'move' && typeof at === 'number' && at >= 0 ? at : -1;" in html
        assert "if (wanted === 'move' && aimingAt < 0) { aiming = null; }" in html
        assert "if (aimingAt + 1 >= moving.length) {" in html
        assert "else { window.trailsGoal.move(where.lat, where.lng, null, true); }" in html
        assert "window.trailsGoal.moveStop(aimingAt, where.lat, where.lng, null, true);" in html
        # And what it is armed for is readable, because the row at the foot
        # lights the button or the row that armed it.
        assert "aimingFor: function () { return aiming; }," in html
        assert "aimingAt: function () { return aiming === 'move' ? aimingAt : -1; }," in html
        assert "aimingAt: aiming === 'move' ? aimingAt : -1," in html


class TestGlyphPerRow:
    """The glyph says what a place is for; the colour says who placed it."""

    @pytest.fixture
    def huts(self) -> gpd.GeoDataFrame:
        return gpd.GeoDataFrame(
            {
                "name": ["Abiskojaure", "Nissonjokk", "Renvaktarstuga"],
                "glyph": ["bed", "person-shelter", None],
                "geometry": [Point(18.6, 68.3), Point(18.62, 68.31), Point(18.65, 68.32)],
            },
            crs="EPSG:4326",
        )

    def test_a_row_is_drawn_with_its_own_glyph_and_falls_back_to_the_layers(self, huts):
        fmap = maps.create_map(bounds=(18.15, 68.17, 19.0, 68.46))
        group = maps.add_points(fmap, huts, name="Cabins", color="darkred", icon="house", icon_field="glyph")

        markers = [child for child in group._children.values() if isinstance(child, folium.Marker)]
        drawn = [next(c for c in marker._children.values() if isinstance(c, folium.DivIcon)).options["html"] for marker in markers]
        assert maps.MARKER_ICONS["bed"][1] in drawn[0]
        assert maps.MARKER_ICONS["person-shelter"][1] in drawn[1]
        assert maps.MARKER_ICONS["house"][1] in drawn[2]
        # And the layer says which it drew, in order, once each.
        assert getattr(group, maps.PIN_GLYPHS_ATTR) == ["bed", "person-shelter", "house"]

    def test_a_glyph_this_page_does_not_draw_is_refused_by_name(self, huts):
        huts.loc[0, "glyph"] = "hut"
        fmap = maps.create_map(bounds=(18.15, 68.17, 19.0, 68.46))
        with pytest.raises(ValueError, match="no outline for 'hut'"):
            maps.add_points(fmap, huts, name="Cabins", icon_field="glyph")

    def test_the_legend_shows_the_pins_a_layer_drew(self, huts):
        fmap = maps.create_map(bounds=(18.15, 68.17, 19.0, 68.46))
        group = maps.add_points(fmap, huts, name="Cabins", color="darkred", icon="house", icon_field="glyph")
        maps.add_legend(fmap, "Legend", [maps.LegendRow("Cabins", "#a23336", group, glyphs=tuple(getattr(group, maps.PIN_GLYPHS_ATTR)))])

        html = fmap.get_root().render()
        # Three pins in the row's colour, the glyph in each, at half the map's size.
        assert html.count(f'width=\\"{maps.PIN_WIDTH // 2}\\" height=\\"{maps.PIN_HEIGHT // 2}\\"') == 3
        assert "swatch.innerHTML = row.glyphs.join('');" in html

    def test_a_row_without_glyphs_keeps_its_bar(self, trails):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        group = maps.add_trails(fmap, trails, name="Paths")
        maps.add_legend(fmap, "Legend", [maps.LegendRow("Paths", "#000000", group)])

        html = fmap.get_root().render()
        assert '"glyphs": []' in html


class TestPinLinks:
    """A pin can say where its timetable is; a line always could."""

    @pytest.fixture
    def quays(self) -> gpd.GeoDataFrame:
        return gpd.GeoDataFrame(
            {
                "name": ["Bønå hurtigbåtkai", "Stranda"],
                "lines": ["18-167", None],
                "entur_url": ["https://entur.no/nearby-stop-place-detail?id=NSR:StopPlace:48932", None],
                "geometry": [Point(12.75372, 65.64458), Point(12.19784, 65.46645)],
            },
            crs="EPSG:4326",
        )

    def test_a_quay_carries_its_link_and_one_without_carries_none(self, quays):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_points(
            fmap,
            quays,
            name="Quays",
            popup_fields={"name": "Quay", "lines": "Boat lines"},
            link_fields={"entur_url": "→ Departures at Entur"},
            link_heading="Published elsewhere, not by this map",
        )

        html = fmap.get_root().render()
        assert "Departures at Entur" in html
        assert "nearby-stop-place-detail?id=NSR:StopPlace:48932" in html
        # Read back what each marker actually carries: three values for the
        # served quay, and for the other one only its name, because a trailing
        # empty says nothing the builder cannot assume.
        # Folium writes a trailing comma, which is fine for JavaScript and not for JSON.
        popups = [json.loads(re.sub(r",\s*\]$", "]", found)) for found in re.findall(r'"popup": (\[.*?\]),', html, re.S)]
        assert ["Bønå hurtigbåtkai", "18-167", "https://entur.no/nearby-stop-place-detail?id=NSR:StopPlace:48932"] in popups
        assert ["Stranda"] in popups

    def test_without_link_fields_a_pin_popup_is_what_it_was(self, quays):
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_points(fmap, quays, name="Quays", popup_fields={"name": "Quay"})

        html = fmap.get_root().render()
        assert '"links": []' in html


class TestGlyphColumnMustExist:
    """A caller that meant to say something per row and said nothing."""

    def test_a_missing_glyph_column_stops_the_build(self):
        """Measured once: the load that fills this column was dropped by a bad
        patch, and 49 quays that should have been ships and anchors were drawn
        as the layer's default while the build reported success."""
        quays = gpd.GeoDataFrame({"name": ["Bønå"], "geometry": [Point(12.75, 65.64)]}, crs="EPSG:4326")
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        with pytest.raises(ValueError, match="which it does not carry"):
            maps.add_points(fmap, quays, name="Ferry quays [OSM]", icon_field="glyph")

    def test_an_empty_layer_is_not_an_error(self):
        # Abisko draws no quay at all, and an empty layer carries no columns
        # worth complaining about.
        empty = gpd.GeoDataFrame({"name": [], "geometry": []}, crs="EPSG:4326")
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        assert maps.add_points(fmap, empty, name="Ferry quays [OSM]", icon_field="glyph") is not None


@pytest.fixture
def full_pack_fixture(tmp_path):
    """A full 85-tile Python archive to compare with the worker's dumped bytes."""
    tile = tmp_path / "tile.png"
    tile.write_bytes(base64.b64decode(maps._ERROR_TILE_URL.split(",")[1]))
    tiles = {(z, x, y): tile for z in range(2, 6) for x in range(2 ** (z - 2)) for y in range(2 ** (z - 2))}
    reference = tmp_path / "python.pmtiles"
    packs.write_pack(tiles, reference)
    return tile, tiles, reference


class TestPackWorker:
    """Run the emitted JavaScript against the independent Python format reader."""

    @staticmethod
    def run_worker(tmp_path, script, provider="kartverket"):
        node = shutil.which("node")
        if node is None:
            pytest.skip("Node is needed to execute the worker unit tests")
        page = tmp_path / "map.html"
        page.write_text("pack test", encoding="utf-8")
        worker = maps.write_service_worker(page, maps.PROVIDERS[provider]).read_text(encoding="utf-8")
        source = 'var self = {navigator: {onLine: true}, location: {href: "https://atlas.test/sw.js"}, addEventListener: function () {}};\n'
        source += worker + "\n" + script
        result = subprocess.run([node, "-"], input=source, text=True, capture_output=True, check=True, timeout=15)
        return json.loads(result.stdout)

    @pytest.mark.parametrize("cancelled", [False, True])
    def test_drive_waits_for_overlapping_settles_between_transactions(self, tmp_path, cancelled):
        """A completed old settle cannot hide a newer run awaiting its warm-up."""
        drive = pathlib.Path(__file__).resolve().parents[4] / "analysis" / "scripts" / "drive_map.py"
        probes = [
            node.value
            for node in ast.walk(ast.parse(drive.read_text(encoding="utf-8")))
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and "async function driveWaitSettled()" in node.value
        ]
        assert len(probes) == 1
        result = self.run_worker(
            tmp_path,
            """
            // Controlled asynchronous gates stand in for fillRecent's awaits.
            // There is no timer, network fill, tile request or open transaction.
            const oldGate=Promise.withResolvers(), newGate=Promise.withResolvers();
            fillRecent=async function (gate) { await gate.promise; };
            """
            + probes[0]
            + """
            (async () => {
                const oldRun=fillRecent(oldGate);
                let returned=false;
                const idle=driveWaitSettled().then(()=>{returned=true;});
                const newRun=fillRecent(newGate).catch(()=>{});
                oldGate.resolve();await oldRun;
                // Let the barrier resume from the old promise, without a sleep.
                await new Promise(setImmediate);
                const during={returned,settles:driveSettles.size,timer:settleTimer,
                    transaction:warmTransaction,fills:filling.size,requests:inFlight};
                if (__CANCELLED__) newGate.reject(Error('cancelled')); else newGate.resolve();
                await newRun;await idle;
                console.log(JSON.stringify({during,returned,settles:driveSettles.size}));
            })().catch(error=>{console.error(error);process.exitCode=1;});
            """.replace("__CANCELLED__", json.dumps(cancelled)),
        )
        assert result == {
            "during": {"returned": False, "settles": 1, "timer": None, "transaction": None, "fills": 0, "requests": 0},
            "returned": True,
            "settles": 0,
        }

    def test_pack_bytes_count_replacement_eviction_oversize_and_clear(self, tmp_path):
        result = self.run_worker(
            tmp_path,
            """
            const body = size => PackIO.write(new Map([[0,new ArrayBuffer(size)]]));
            const small=body(2_000_000), large=body(20_000_000);
            holdPack('a',large); holdPack('b',large); holdPack('c',small);
            recent(packs,'a'); holdPack('d',large);
            const lru=[...packs.keys()], bytes=packBytes;
            holdPack('a',small); const replaced=packBytes;
            dropPack('c'); const deleted=packBytes;
            const huge=body(PACK_BYTES), returned=holdPack('huge',huge);
            const oversized=!packs.has('huge') && returned.body===huge && packBytes===deleted;
            clearPacks();
            console.log(JSON.stringify({limit:PACK_BYTES,lru,bytes,replaced,deleted,oversized,
                expected:[2*large.byteLength+small.byteLength,large.byteLength+2*small.byteLength,large.byteLength+small.byteLength],
                cleared:[packs.size,packBytes]}));
            """,
        )
        assert result["limit"] == 48_000_000
        assert result["lru"] == ["c", "a", "d"]
        assert [result[key] for key in ("bytes", "replaced", "deleted")] == result["expected"]
        assert result["oversized"]
        assert result["cleared"] == [0, 0]

    def test_only_memory_before_lookup_is_tallied_as_memory(self, tmp_path):
        result = self.run_worker(
            tmp_path,
            """
            (async()=>{
                const a=packFor(TILE_PREFIX+'14/1/1.png'),body=PackIO.write(new Map([[a.id,new ArrayBuffer(8)]]));
                notePack=()=>{};write=async()=>true;
                let clock=0, pending=[];
                performance.now=()=>clock;
                lookup=()=>new Promise(done=>pending.push(done));
                const work=[tileFor(new Request(a.tile)),tileFor(new Request(a.tile))];
                await Promise.resolve(); clock=42;
                pending.forEach(done=>done({body,complete:true,path:'db'}));await Promise.all(work);
                const cold=JSON.parse(JSON.stringify(told));
                clearPacks();
                lookup=async()=>{clock+=10;holdPack(a.url,body);return null;};
                await tileFor(new Request(a.tile));await tileFor(new Request(a.tile));
                clearTimeout(telling);
                console.log(JSON.stringify({cold:{mem:cold.mem,db:cold.db,time:cold.time.db.total},
                    final:{mem:told.mem,db:told.db,time:told.time.db.total}}));
            })().catch(e=>{console.error(e);process.exitCode=1;});
            """,
        )
        assert result == {"cold": {"mem": 0, "db": 2, "time": 84}, "final": {"mem": 1, "db": 3, "time": 94}}

    @pytest.mark.parametrize("cancel", [False, True])
    def test_store_warmup_is_serial_bounded_and_stops_on_a_tile_request(self, tmp_path, cancel):
        result = self.run_worker(
            tmp_path,
            """
            (async()=>{
                const tile=packFor(TILE_PREFIX+'14/4/4.png'),body=PackIO.write(new Map([[tile.id,new ArrayBuffer(8)]]));
                let gets=[],transactions=0,active=0,peak=0,network=0,aborted=false;
                fetch=async()=>{network++;throw Error('network forbidden');};
                setTimeout=()=>1;clearTimeout=()=>{};
                const tx={objectStore:()=>({get:url=>{
                    gets.push(url);active++;peak=Math.max(peak,active);const ask={};
                    setImmediate(()=>{
                        active--;if(aborted)return;
                        // A missing row is harmless; only rows that exist enter memory.
                        ask.result=gets.length===2?undefined:{pack:body,complete:true};
                        if(CANCEL && gets.length===2){notePack(tile);return;}
                        ask.onsuccess();
                        if(!active)setImmediate(()=>tx.oncomplete());
                    });return ask;
                }}),abort:()=>{aborted=true;setImmediate(()=>tx.onabort());}};
                base=async()=>({transaction:(store,mode)=>{
                    if(store!=='packs'||mode!=='readonly')throw Error('wrong transaction');transactions++;return tx;
                }});
                const urls=[tile.url,packFor(TILE_PREFIX+'14/8/8.png').url,
                    packFor(SHADE_PREFIX+'14/4/4.png').url,packFor(SLOPE_PREFIX+'14/8/8.png').url,
                    packFor(HEIGHT_PREFIX+'13/4/4.png').url];
                await warmRecent(urls,requestGeneration);
                console.log(JSON.stringify({gets:gets.length,transactions,peak,network,aborted,packs:packs.size,
                    first:gets[0]===tile.url,unique:new Set(gets).size===gets.length,
                    heights:gets.some(u=>u.includes('/dem/')),sheetFirst:gets.slice(0,18).every(u=>u.includes('/tiles/'))}));
            })().catch(e=>{console.error(e);process.exitCode=1;});
            """.replace("CANCEL", json.dumps(cancel)),
        )
        assert result == {
            "gets": 2 if cancel else 32,
            "transactions": 1,
            "peak": 1,
            "network": 0,
            "aborted": cancel,
            "packs": 1 if cancel else 31,
            "first": True,
            "unique": True,
            "heights": False,
            "sheetFirst": True,
        }

    @pytest.mark.parametrize("provider", ["kartverket", "lantmateriet"])
    def test_warmup_refreshes_complete_neighbours_before_loading_more_packs(self, tmp_path, provider):
        """An already complete neighbour must not stay cold in the byte-budget LRU."""
        result = self.run_worker(
            tmp_path,
            """
            (async()=>{
                const asked=packFor(TILE_PREFIX+'14/4/4.png'), neighbour=packFor(TILE_PREFIX+'14/3/3.png'),
                    incoming=packFor(TILE_PREFIX+'14/4/3.png');
                const body=a=>PackIO.write(new Map([[a.id,new Uint8Array(8).fill(7).buffer]]));
                const neighbourBody=body(neighbour), incomingBody=body(incoming);
                holdPack(neighbour.url,neighbourBody);
                holdPack('old ground',PackIO.write(new Map([[0,new ArrayBuffer(1024)]])));
                holdPack(asked.url,body(asked));
                PACK_BYTES=packBytes;
                let reads=[],active=0,transactions=0,lookups=0,network=0;
                const paths=[];
                fetch=async()=>{network++;throw Error('network forbidden');};
                setTimeout=()=>1;clearTimeout=()=>{};switched=Promise.resolve(true);
                const tx={objectStore:()=>({get:url=>{
                    reads.push(url);active++;const ask={};
                    setImmediate(()=>{
                        active--;ask.result=url===incoming.url?{pack:incomingBody,complete:true}:undefined;
                        ask.onsuccess();if(!active)setImmediate(()=>tx.oncomplete());
                    });return ask;
                }})};
                base=async()=>({transaction:(store,mode)=>{
                    if(store!==KEPT||mode!=='readonly')throw Error('wrong transaction');transactions++;return tx;
                }});
                await warmRecent([asked.url],requestGeneration);
                const retained=packs.has(neighbour.url),coldGone=!packs.has('old ground');
                lookup=async()=>{lookups++;return {body:neighbourBody,complete:true,path:'db'};};
                tally=path=>paths.push(path);
                await tileFor(new Request(neighbour.tile));
                console.log(JSON.stringify({retained,coldGone,paths,lookups,network,transactions,
                    reads:reads.length,reread:reads.includes(neighbour.url),bounded:packBytes<=PACK_BYTES}));
            })().catch(e=>{console.error(e);process.exitCode=1;});
            """,
            provider,
        )
        assert result == {
            "retained": True,
            "coldGone": True,
            "paths": ["mem"],
            "lookups": 0,
            "network": 0,
            "transactions": 1,
            "reads": 7,
            "reread": False,
            "bounded": True,
        }

    @pytest.mark.parametrize("provider", ["kartverket", "lantmateriet"])
    def test_addresses_at_every_level_and_box_edge(self, tmp_path, provider):
        own = maps.PROVIDERS[provider]
        west, south, east, north = own.extent
        addresses, expected = [], []
        for layer in (own, own.heights, own.shade, own.slope, own.vegetation, own.forest, own.mire):
            for zoom in range(8, layer.top + 1):
                level = max(z for z in packs.pack_levels(range(8, layer.top + 1)) if z <= zoom)
                for lon, lat in ((west, south), (west, north), (east, south), (east, north)):
                    x = int((lon + 180) / 360 * 2**zoom)
                    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * 2**zoom)
                    addresses.append(f"https://atlas.test{layer.tiles}{zoom}/{x}/{y}.png")
                    expected.append(
                        {
                            "url": f"https://atlas.test/packs{layer.tiles}{level}/{x >> (zoom - level)}/{y >> (zoom - level)}.pmtiles",
                            "id": packs.tile_id(zoom, x, y),
                            "tile": addresses[-1],
                            "height": layer is own.heights,
                        }
                    )
        assert self.run_worker(tmp_path, f"console.log(JSON.stringify({json.dumps(addresses)}.map(packFor)));", provider) == expected

    def test_tile_id_matches_python_on_twelve_addresses(self, tmp_path):
        addresses = [
            (0, 0, 0),
            (1, 0, 0),
            (1, 1, 0),
            (1, 0, 1),
            (1, 1, 1),
            (6, 34, 16),
            (8, 137, 65),
            (10, 565, 243),
            (13, 4500, 2010),
            (14, 8738, 4200),
            (17, 70000, 33000),
            (26, 67108863, 67108863),
        ]
        assert self.run_worker(tmp_path, f"console.log(JSON.stringify({json.dumps(addresses)}.map(a => tileId(...a))));") == [
            packs.tile_id(*tile) for tile in addresses
        ]

    def test_reader_slices_exact_python_bytes_and_bounds_memory(self, tmp_path):
        tile = tmp_path / "tile.png"
        tile.write_bytes(base64.b64decode(maps._ERROR_TILE_URL.split(",")[1]))
        path = tmp_path / "fixture.pmtiles"
        tiles = {(z, x, y): tile for z in range(2, 6) for x in range(2 ** (z - 2)) for y in range(2 ** (z - 2))}
        packs.write_pack(tiles, path)
        reader = packs.PackReader(path)
        encoded = base64.b64encode(path.read_bytes()).decode()
        result = self.run_worker(
            tmp_path,
            f"""
            var bytes = Uint8Array.from(Buffer.from('{encoded}', 'base64')).buffer;
            var held = holdPack('fixture', bytes);
            var answers = {json.dumps(list(tiles))}.map(a => Buffer.from(sliceTile(held, tileId(...a))).toString('base64'));
            var rejected = 0;
            for (var at of [0, 7, 48, 97, 98, 99, 127]) {{
                var corrupt = bytes.slice(0); new Uint8Array(corrupt)[at] ^= 255;
                try {{ holdPack('bad', corrupt); }} catch (_) {{ rejected++; }}
            }}
            clearPacks(); PACK_BYTES = 8 * bytes.byteLength;
            for (var i = 0; i < 60; i++) {{ holdPack('pack' + i, bytes); }}
            recent(packs, 'pack52'); holdPack('pack60', bytes);
            console.log(JSON.stringify({{answers, rejected, packs: packs.size, directories: directories.size,
                oldestGone: !packs.has('pack53'), touchedStays: packs.has('pack52'), missing: sliceTile(held, tileId(2, 3, 3))}}));
        """,
        )
        assert result.pop("answers") == [base64.b64encode(reader.read_tile(*address)).decode() for address in tiles]
        assert result == {"rejected": 7, "packs": 8, "directories": 48, "oldestGone": True, "touchedStays": True, "missing": None}

    @pytest.mark.parametrize("provider", ["kartverket", "lantmateriet"])
    def test_all_worker_placeholders_are_filled(self, tmp_path, provider):
        page = tmp_path / "map.html"
        page.write_text("page", encoding="utf-8")
        own = maps.PROVIDERS[provider]
        worker = maps.write_service_worker(page, own).read_text(encoding="utf-8")
        assert not re.search(r"__[A-Z_]+__", worker)
        for name, layer in (
            ("TILE", own),
            ("HEIGHT", own.heights),
            ("SHADE", own.shade),
            ("SLOPE", own.slope),
            ("VEGETATION", own.vegetation),
            ("FOREST", own.forest),
            ("MIRE", own.mire),
        ):
            assert f"[{name}_PREFIX, {layer.top}]" in worker

    def test_page_waits_for_first_controller_but_only_on_secure_origins(self):
        html = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7)).get_root().render()
        assert "!secure || !('serviceWorker' in navigator) || navigator.serviceWorker.controller" in html
        assert "setTimeout(release, 3000)" in html
        assert "addEventListener('controllerchange', controlled)" in html
        assert html.index("pending.set(L.stamp(layer), layer)") < html.index("var tile_layer_")
        # The page reads the complete row; the fixed Sources renderer is phase 6b's second half.
        fmap = maps.create_map(bounds=(12.4, 65.3, 13.4, 65.7))
        maps.add_chrome(fmap)
        assert "dbRead('flags', 'tiles-said')" in fmap.get_root().render()
        assert "mem: 0" in maps.SERVICE_WORKER and "mem: {total: 0, worst: 0}" in maps.SERVICE_WORKER

    def test_network_stays_on_ranges_and_accepts_an_ignored_range_header(self, tmp_path):
        tile = tmp_path / "tile.png"
        tile.write_bytes(base64.b64decode(maps._ERROR_TILE_URL.split(",")[1]))
        path = tmp_path / "fixture.pmtiles"
        packs.write_pack({(14, 1, 1): tile, (15, 2, 2): tile}, path)
        encoded = base64.b64encode(path.read_bytes()).decode()
        result = self.run_worker(
            tmp_path,
            f"""
            (async function () {{
                var bytes = Uint8Array.from(Buffer.from('{encoded}', 'base64')).buffer;
                var requests = [], writes = [], ignoreRange = false;
                browsePut = async function (url, body) {{
                    if (!(body instanceof ArrayBuffer)) throw Error('not an ArrayBuffer');
                    writes.push({{url, size: body.byteLength}});
                }};
                fetch = async function (url, options) {{
                    var range = options && options.headers.Range;
                    requests.push(range || 'whole');
                    if (!range || ignoreRange) return new Response(bytes);
                    var ends = range.slice(6).split('-').map(Number), end = Math.min(ends[1], bytes.byteLength - 1);
                    return new Response(bytes.slice(ends[0], end + 1), {{status: 206, headers: {{
                        'content-range': 'bytes ' + ends[0] + '-' + end + '/' + bytes.byteLength
                    }}}});
                }};
                var a = packFor(TILE_PREFIX + '14/1/1.png'), b = packFor(TILE_PREFIX + '15/2/2.png');
                var one = await networkTile(a), rangeWrites = writes.slice();
                await Promise.all([networkTile(b), networkTile(a), networkTile(b)]);
                Date.now = () => 100000;
                await networkTile(b);  // Even a later tile stays on ranges.
                var beforeSettle = requests.slice();
                packs.clear(); directories.clear(); ignoreRange = true;
                var whole = await networkTile(a);
                console.log(JSON.stringify({{requests, rangeWrites, writes, beforeSettle,
                    same: Buffer.from(one).equals(Buffer.from(whole))}}));
            }})().catch(e => {{ console.error(e); process.exitCode = 1; }});
        """,
        )
        assert result["requests"][0] == "bytes=0-16383"
        assert len(result["beforeSettle"]) == 6, "burst tiles stay ranged, even after a slow store lookup or at the two-second boundary"
        assert all(request.startswith("bytes=") for request in result["beforeSettle"])
        assert result["rangeWrites"] == [{"url": "https://atlas.test/packs/tiles/kartverket/topo/1/14/1/1.pmtiles", "size": 68}]
        assert result["requests"].count("whole") == 0
        assert result["requests"][-1] == "bytes=0-16383"
        assert result["same"]
        whole_writes = [row for row in result["writes"] if row["size"] > 68]
        assert len(whole_writes) == 1
        assert all(row["size"] == 68 for row in result["writes"] if row not in whole_writes)

    def test_idle_window_resets_is_bounded_and_fills_sheet_before_overlays(self, tmp_path):
        result = self.run_worker(
            tmp_path,
            """
            (async () => {
                const body = PackIO.write(new Map([[0,new Uint8Array(8).buffer]]));
                let now=1000, timer, armed=0, cleared=0, active=0, peak=0;
                const requests=[], releases=[], writes=[], waits=[], reads=[];
                let warmedAfterWrites=-1;
                warmRecent=async()=>{warmedAfterWrites=writes.length;};
                Date.now=()=>now;
                setTimeout=(fn,ms)=>{if(ms!==SETTLE_MS)throw Error('wrong idle delay');timer=fn;return ++armed;};
                clearTimeout=()=>{cleared++;};
                read=async(store,url)=>{reads.push(url);return url.endsWith('?stored')?{complete:true}:null;};
                switched=Promise.resolve(false);
                browsePut=async(url,body)=>{writes.push(url);};
                fetch=async(url)=>{
                    requests.push(url);peak=Math.max(peak,++active);
                    await new Promise((done,fail)=>releases.push(ok=>{active--;ok?done():fail(Error('gone'));}));
                    return new Response(body);
                };
                const turn=()=>new Promise(done=>setImmediate(done)), event={waitUntil:p=>waits.push(p)};
                const base=packFor(TILE_PREFIX+'14/1/1.png'), shade=packFor(SHADE_PREFIX+'14/1/1.png'),
                    height=packFor(HEIGHT_PREFIX+'13/1/1.png');
                // Old addresses and repeated tile requests cannot grow the map.
                for(let i=0;i<70;i++)notePack({...base,url:base.url+'?old='+i},event);
                const bounded=askedPacks.size;
                now+=SETTLE_MS+1;
                notePack(shade,event);notePack(height,event);
                notePack({...base,url:base.url+'?stored'},event);
                holdPack(base.url+'?memory',body);
                notePack({...base,url:base.url+'?memory'},event);
                for(let i=0;i<3;i++)notePack({...base,url:base.url+'?sheet='+i},event);
                const before=requests.length, shared=waits.every(p=>p===waits[0]);
                timer();await turn();
                const first=requests.slice();
                releases[0](true);await turn();
                const third=requests.slice();
                releases[1](false);releases[2](true);await turn();
                const last=requests.slice();releases[3](true);
                await waits[0];
                console.log(JSON.stringify({bounded,before,shared,reset:cleared===armed-1,peak,
                    first:first.map(u=>u.split('?')[1]),third:third.map(u=>u.split('?')[1]),
                    sheetFirst:last[3]===shade.url,height:requests.includes(height.url),writes:writes.length,
                    complete:packs.get(shade.url).complete,directory:directories.has(shade.url),
                    memoryRead:reads.includes(base.url+'?memory'),filling:filling.size,warmedAfterWrites}));
            })().catch(e=>{console.error(e);process.exitCode=1;});
            """,
        )
        assert result == {
            "bounded": 48,
            "before": 0,
            "shared": True,
            "reset": True,
            "peak": 2,
            "first": ["sheet=0", "sheet=1"],
            "third": ["sheet=0", "sheet=1", "sheet=2"],
            "sheetFirst": True,
            "height": False,
            "writes": 3,
            "complete": True,
            "directory": True,
            "memoryRead": False,
            "filling": 0,
            "warmedAfterWrites": 3,
        }

    @pytest.mark.parametrize("offline", ["switch", "network", "moving"])
    def test_idle_fill_stops_offline_or_when_a_new_request_arrives(self, tmp_path, offline):
        result = self.run_worker(
            tmp_path,
            """
            (async()=>{
                let requested=0,reads=0,timer;
                const a=packFor(TILE_PREFIX+'14/1/1.png');
                setTimeout=fn=>{timer=fn;return 1;};clearTimeout=()=>{};
                switched=Promise.resolve(MODE==='switch');self.navigator.onLine=MODE!=='network';
                fetch=async()=>{requested++;throw Error('must not fetch');};
                read=async()=>{reads++;if(MODE==='moving')notePack(a);return null;};
                let pending;notePack(a,{waitUntil:p=>{pending=p;}});timer();await pending;
                console.log(JSON.stringify({requested,reads}));
            })().catch(e=>{console.error(e);process.exitCode=1;});
            """.replace("MODE", json.dumps(offline)),
        )
        assert result == {"requested": 0, "reads": int(offline == "moving")}

    @pytest.mark.parametrize("offline", [False, True])
    @pytest.mark.parametrize("kept", [False, True])
    def test_partial_lookup_uses_memory_then_row_then_blank_or_network(self, tmp_path, offline, kept):
        result = self.run_worker(
            tmp_path,
            """
            (async function () {
                var bytes = new Uint8Array(8).fill(7).buffer, paths = [], reads = 0, network = 0;
                var a = packFor(TILE_PREFIX + '14/1/1.png'), b = packFor(TILE_PREFIX + '15/2/2.png');
                var body = PackIO.write(new Map([[a.id, bytes]]));
                tally = path => paths.push(path); switched = Promise.resolve(OFFLINE);
                lookup = async (key, state) => {
                    reads++; state.off = OFFLINE; return {body, complete: false, path: KEPT ? 'db' : 'seen'};
                };
                networkTile = async () => { network++; return bytes; };
                const sizes = [];
                for (const tile of [a.tile, a.tile, b.tile]) {
                    sizes.push((await (await tileFor(new Request(tile))).arrayBuffer()).byteLength);
                }
                console.log(JSON.stringify({paths, reads, network, sizes}));
            })().catch(e => { console.error(e); process.exitCode = 1; });
            """.replace("OFFLINE", json.dumps(offline)).replace("KEPT", json.dumps(kept)),
        )
        assert result == {
            "paths": ["db" if kept else "seen", "mem", "blank" if offline else "net"],
            "reads": 2,
            "network": 0 if offline else 1,
            "sizes": [8, 8, 68 if offline else 8],
        }

    def test_writer_and_merge_agree_byte_for_byte_with_python(self, tmp_path, full_pack_fixture):
        tile, tiles, reference = full_pack_fixture
        result = self.run_worker(
            tmp_path,
            f"""
            const tileBytes = Uint8Array.from(Buffer.from('{base64.b64encode(tile.read_bytes()).decode()}', 'base64')).buffer;
            const ids = {json.dumps([packs.tile_id(*t) for t in tiles])};
            const tiles = new Map(ids.map(id => [id, tileBytes]));
            const full = PackIO.write(tiles), first = PackIO.write(new Map([[ids[0], tileBytes]]));
            const merged = PackIO.merge(first, tiles), pack = PackIO.unpack(merged);
            console.log(JSON.stringify({{full: Buffer.from(full).toString('base64'),
                merged: Buffer.from(merged).equals(Buffer.from(full)), count: pack.entries.size,
                slices: ids.every(id => Buffer.from(PackIO.slice(pack, id)).equals(Buffer.from(tileBytes)))}}));
        """,
        )
        written = tmp_path / "worker.pmtiles"
        written.write_bytes(base64.b64decode(result["full"]))
        assert written.read_bytes() == reference.read_bytes()
        reader = packs.PackReader(written)
        assert all(reader.read_tile(*address) == tile.read_bytes() for address in tiles)
        assert result["merged"] and result["slices"] and result["count"] == 85

    @pytest.mark.parametrize("present", [0, 1, 2, 3, 4])
    def test_keep_replaces_every_incomplete_row_whole_and_reuses_complete_rows(self, tmp_path, present):
        result = self.run_worker(
            tmp_path,
            f"""
            (async () => {{
                const bytes = new Uint8Array(8).fill(9).buffer, ids = [0, 1, 2, 3];
                const full = PackIO.write(new Map(ids.map(id => [id, bytes]))), requests = [];
                const request = async (...args) => {{ requests.push(args); return new Response(full); }};
                const localBytes = new Uint8Array(8).fill(1).buffer;
                const row = {present} ?
                    PackIO.row(PackIO.write(new Map(ids.slice(0, {present}).map(id => [id, localBytes]))), false, false, 'p') : null;
                const body = await PackIO.complete(row, request);
                const at = requests.length;
                for (const kept of [false, true]) await PackIO.complete(PackIO.row(body, kept, true, 'p'), request);
                console.log(JSON.stringify({{requests, skipped: at === requests.length,
                    same: Buffer.from(body).equals(Buffer.from(full))}}));
            }})().catch(e => {{console.error(e);process.exitCode=1;}});
        """,
        )
        assert result["same"] and result["skipped"]
        assert result["requests"] == [[]], "even an archive containing every tile is replaced if complete is false"

    def test_merge_replaces_bytes_without_duplicating_ids(self, tmp_path):
        result = self.run_worker(
            tmp_path,
            """
            const a = new Uint8Array(8).fill(1).buffer, b = new Uint8Array(9).fill(2).buffer;
            const first = PackIO.write(new Map([[0,a],[1,a]]));
            const merged = PackIO.unpack(PackIO.merge(first,new Map([[1,b],[2,b]])));
            console.log(JSON.stringify({ids:[...merged.entries.keys()],
                bytes:[0,1,2].map(id=>[...new Uint8Array(PackIO.slice(merged,id))])}));
        """,
        )
        assert result == {"ids": [0, 1, 2], "bytes": [[1] * 8, [2] * 9, [2] * 9]}

    @pytest.mark.parametrize("opener", ["worker", "page"])
    @pytest.mark.parametrize("scratch", [False, True])
    def test_version_six_preserves_every_pack_flag_and_page(self, tmp_path, opener, scratch):
        panel = (pathlib.Path(maps.__file__).parent / "js" / "offline_panel.js").read_text()
        page_open = "function db(" + panel.split("function db(", 1)[1].split("\n                function dbRead", 1)[0]
        script = page_open + "\nconst open = await db();" if opener == "page" else "const open = await base();"
        result = self.run_worker(
            tmp_path,
            """
            (async()=>{
                const stores=new Set(['pages','flags','packs']),deleted=[],changed=[];
                if(SCRATCH)stores.add('bench');
                const fixtureDB={objectStoreNames:{contains:n=>stores.has(n)},close:()=>{},
                    deleteObjectStore:n=>{deleted.push(n);stores.delete(n);},
                    createObjectStore:n=>{changed.push(n);return {createIndex:()=>{}};}};
                indexedDB={open:(name,version)=>{
                    if(version!==6)throw Error('wrong version');
                    const ask={result:fixtureDB,transaction:{objectStore:n=>({delete:k=>changed.push(k)})}};
                    queueMicrotask(()=>{ask.onupgradeneeded({oldVersion:5});ask.onsuccess();});return ask;
                }};
                const window={indexedDB};
                SCRIPT
                console.log(JSON.stringify({stores:[...stores],deleted,changed}));
            })().catch(e=>{console.error(e);process.exitCode=1;});
            """.replace("SCRATCH", json.dumps(scratch)).replace("SCRIPT", script),
        )
        assert result == {"stores": ["pages", "flags", "packs"], "deleted": ["bench"] if scratch else [], "changed": []}

    def test_upgrade_discards_only_terrain_and_creates_both_indexes(self, tmp_path):
        result = self.run_worker(
            tmp_path,
            """
            const stores = new Set(['pages','flags','packs','browse']), indexes = [], deleted = [], flags = [];
            IDBKeyRange = {bound: (a,b)=>[a,b]};
            PackIO.upgrade({objectStoreNames:{contains:name=>stores.has(name)},
                deleteObjectStore:name=>{deleted.push(name);stores.delete(name);},
                createObjectStore:name=>{stores.add(name);return {createIndex:(...args)=>indexes.push(args)};}
            },{objectStore:()=>({delete:key=>flags.push(key)})});
            console.log(JSON.stringify({stores:[...stores],deleted,indexes,flags}));
        """,
        )
        assert result["stores"] == ["pages", "flags", "packs"]
        assert result["deleted"] == ["browse", "packs"]
        assert result["indexes"] == [["browsed-at", "browsedAt"], ["kept", "keptAt"]]
        assert result["flags"] == ["held", "stand", "browse-bytes", ["browse-size:", "browse-size:\uffff"]]

    @pytest.mark.parametrize("failure", ["partial response", "truncated body", "HTTP error"])
    def test_keep_rejects_failed_or_incomplete_whole_responses(self, tmp_path, failure):
        result = self.run_worker(
            tmp_path,
            """
            (async () => {
                const bytes=new Uint8Array(8).buffer,body=PackIO.write(new Map([[0,bytes],[1,bytes]]));
                const row=PackIO.row(PackIO.write(new Map([[0,bytes]])),false,false,'url');
                let refused=false;
                const response=FAILURE==='partial response'?new Response(body,{status:206}):
                    FAILURE==='truncated body'?new Response(body.slice(0,128)):new Response('failed',{status:503});
                try {await PackIO.complete(row,async()=>response);}catch(e){refused=true;}
                console.log(JSON.stringify({refused,unchanged:!row.complete && PackIO.unpack(row.pack).entries.size===1}));
            })().catch(e=>{console.error(e);process.exitCode=1;});
        """.replace("FAILURE", json.dumps(failure)),
        )
        assert result == {"refused": True, "unchanged": True}

    @pytest.mark.parametrize("answer", [False, None])
    def test_keep_preserves_absent_and_refused_request_results(self, tmp_path, answer):
        result = self.run_worker(
            tmp_path,
            """
            (async () => {
                const row=PackIO.row(PackIO.write(new Map([[0,new Uint8Array(8).buffer]])),false,false,'url');
                console.log(JSON.stringify(await PackIO.complete(row,async()=>ANSWER)));
            })().catch(e=>{console.error(e);process.exitCode=1;});
        """.replace("ANSWER", json.dumps(answer)),
        )
        assert result is answer

    def test_local_complete_archive_never_seeds_remote_range_offsets(self, tmp_path, full_pack_fixture):
        tile, tiles, _ = full_pack_fixture
        remote = tmp_path / "remote.pmtiles"
        packs.write_pack(tiles, remote, metadata={"encoding": "height bytes"})
        result = self.run_worker(
            tmp_path,
            f"""
            (async () => {{
                const remote=Uint8Array.from(Buffer.from('{base64.b64encode(remote.read_bytes()).decode()}','base64')).buffer;
                const local=PackIO.merge(remote,new Map()), id=tileId(2,0,0), requests=[];
                const address=packFor(TILE_PREFIX+'2/0/0.png');
                tally=()=>{{}};switched=Promise.resolve(false);
                lookup=async()=>({{body:local,complete:true,path:'db'}});
                await tileFor(new Request(address.tile));
                const cachedDirectory=directories.has(address.url);
                packs.clear();lookup=async()=>null;
                fetch=async(url,options)=>{{
                    requests.push(options.headers.Range);
                    const [start,last]=options.headers.Range.slice(6).split('-').map(Number);
                    const end=Math.min(last,remote.byteLength-1);
                    return new Response(remote.slice(start,end+1),{{status:206,headers:{{
                        'content-range':'bytes '+start+'-'+end+'/'+remote.byteLength}}}});
                }};
                const answer=await (await tileFor(new Request(address.tile))).arrayBuffer();
                console.log(JSON.stringify({{cachedDirectory,requests,offsetsDiffer:PackIO.header(local).data!==PackIO.header(remote).data,
                    same:Buffer.from(answer).equals(Buffer.from(PackIO.slice(PackIO.unpack(remote),id)))}}));
            }})().catch(e=>{{console.error(e);process.exitCode=1;}});
        """,
        )
        assert result["offsetsDiffer"] and result["same"]
        assert not result["cachedDirectory"]
        assert result["requests"][0] == "bytes=0-16383"

    def test_slow_network_is_awaited_outside_the_store_deadline(self, tmp_path):
        result = self.run_worker(
            tmp_path,
            """
            (async function () {
                tally = () => {};
                switched = Promise.resolve(false);
                lookup = async () => null;
                networkTile = async () => {
                    await new Promise(done => setTimeout(done, 2700));
                    return new Uint8Array([1, 2, 3]).buffer;
                };
                var began = performance.now();
                var response = await tileFor(new Request(TILE_PREFIX + '14/1/1.png'));
                console.log(JSON.stringify({bytes: (await response.arrayBuffer()).byteLength,
                    deadlines: told.deadlines, waited: performance.now() - began >= 2500, inFlight}));
            })().catch(e => { console.error(e); process.exitCode = 1; });
            """,
        )
        assert result == {"bytes": 3, "deadlines": 0, "waited": True, "inFlight": 0}

    def test_first_control_gate_releases_on_control_or_timeout(self, tmp_path):
        gate = files("trails.visualization").joinpath("js", "tile_start.js").read_text(encoding="utf-8")
        gate = gate.replace("{{ this._parent.get_name() }}", "namedMap")
        result = self.run_worker(
            tmp_path,
            """
            var vm = require('node:vm'), results = [];
            for (var scenario of ['insecure', 'controlled', 'control', 'timeout']) {
                var added = [], active = new Set(), timer, arm, handler, delay = null;
                function Tile() {}
                var layer = new Tile(); layer.id = 1;
                var cancelled = new Tile(); cancelled.id = 2;
                var map = {
                    addLayer: function (l) { active.add(l.id); added.push(l.id); return this; },
                    removeLayer: function (l) { active.delete(l.id); return this; },
                    hasLayer: function (l) { return active.has(typeof l === 'number' ? l : l.id); }
                };
                var originalHas = map.hasLayer;
                var sw = {controller: scenario === 'controlled' ? {} : null,
                    addEventListener: function (_, fn) { handler = fn; }, removeEventListener: function () { handler = null; }};
                vm.runInNewContext(__GATE__, {namedMap: map, L: {TileLayer: Tile, stamp: l => l.id},
                    location: {protocol: scenario === 'insecure' ? 'http:' : 'https:', hostname: 'atlas.test'},
                    Promise: {resolve: () => ({then: fn => { arm = fn; }})},
                    navigator: {serviceWorker: sw}, setTimeout: (fn, ms) => { timer = fn; delay = ms; }, clearTimeout: () => {}});
                map.addLayer(layer);
                var before = added.length;
                var requested = map.hasLayer(layer) && map.hasLayer(layer.id);
                if (arm) {
                    if (delay !== null) throw Error('construction consumed the control deadline');
                    arm();
                }
                if (timer) {
                    map.addLayer(layer); map.addLayer(cancelled);
                    // The legend removes a switched-off layer only if hasLayer says it is present.
                    if (map.hasLayer(cancelled)) map.removeLayer(cancelled);
                    if (scenario === 'control') { sw.controller = {}; handler(); } else { timer(); }
                }
                if (!requested || map.hasLayer(cancelled) || map.hasLayer !== originalHas) {
                    throw Error('the gate lost the requested layer state');
                }
                results.push({scenario, before, added, delay, listening: !!handler});
            }
            console.log(JSON.stringify(results));
        """.replace("__GATE__", json.dumps(gate)),
        )
        assert result == [
            {"scenario": "insecure", "before": 1, "added": [1], "delay": None, "listening": False},
            {"scenario": "controlled", "before": 1, "added": [1], "delay": None, "listening": False},
            {"scenario": "control", "before": 0, "added": [1], "delay": 3000, "listening": False},
            {"scenario": "timeout", "before": 0, "added": [1], "delay": 3000, "listening": False},
        ]


class TestPackPanel:
    @staticmethod
    def function(name):
        panel = files("trails.visualization").joinpath("js", "offline_panel.js").read_text(encoding="utf-8")
        return "function " + name + "(" + panel.split("function " + name + "(", 1)[1].split("\n                }", 1)[0] + "\n}"

    @pytest.mark.parametrize("provider", ["kartverket", "lantmateriet"])
    def test_worker_and_panel_use_the_same_level_rule_at_every_zoom(self, tmp_path, provider):
        panel_rule = self.function("packLevel")
        own = maps.PROVIDERS[provider]
        layers = [own, own.heights, own.shade, own.slope, own.vegetation, own.forest, own.mire]
        addresses = [(layer.top, z) for layer in layers for z in range(8, layer.top + 1)]
        result = TestPackWorker.run_worker(
            tmp_path,
            f"""
            var workerRule = packLevel;
            var panelRule = ({panel_rule});
            console.log(JSON.stringify({json.dumps(addresses)}.map(a => [workerRule(...a), panelRule(...a)])));
        """,
            provider,
        )
        for (top, z), (worker, panel) in zip(addresses, result, strict=True):
            expected = max(level for level in packs.pack_levels(range(8, top + 1)) if level <= z)
            assert worker == panel == expected

    def setup(self, provider):
        own = maps.PROVIDERS[provider]
        west, south, east, north = own.extent
        settings = {
            "HEIGHTS": own.heights, "SHADE": own.shade, "SLOPE": own.slope,
            "VEGETATION": own.vegetation, "FOREST": own.forest, "MIRE": own.mire,
        }  # fmt: skip
        setup = f"var location = {{href: 'https://atlas.test/map.html'}}, TOP = {own.top}, OVERVIEW = 8, BOTTOM = 11, SPAN = 262144;"
        setup += "var EXTENT = " + json.dumps({"w": west, "s": south, "e": east, "n": north}) + ";"
        setup += "var PACK_WEIGHT = " + json.dumps(own.pack_weight) + ";"
        for name, layer in settings.items():
            assert layer is not None
            setup += f"var {name} = {json.dumps(layer.as_settings())};"
            assert set(layer.pack_weight) == set(packs.pack_levels(range(8, layer.top + 1)))
        setup += "function key(x,y) {return x*SPAN+y;} function keyX(v){return Math.floor(v/SPAN);} function keyY(v){return v%SPAN;}"
        for name in [
            "fracTile",
            "edgeAt",
            "padded",
            "overviewAt",
            "overviewCost",
            "levelsFor",
            "packPrefix",
            "packLayers",
            "parentsAt",
            "packWalk",
            "weigh",
        ]:
            setup += self.function(name)
        return setup

    @pytest.mark.parametrize("provider,count", [("kartverket", 9651), ("lantmateriet", 2396)])
    def test_whole_box_iterator_counts_packs_once_with_measured_weights(self, tmp_path, provider, count):
        setup = self.setup(provider)
        setup += """
            var levels = levelsFor(null, 17, 1);
            var walk=packWalk(levels), row, urls=new Set(), total=0, bytes=0;
            while ((row=walk.next())) { urls.add(row.url); total++; bytes+=row.bytes; }
            console.log(JSON.stringify({total:total, unique:urls.size, bytes:bytes, weighed:weigh(levels)}));
        """
        result = TestPackWorker.run_worker(tmp_path, setup, provider)
        assert result["total"] == result["unique"] == count
        assert result["weighed"] == {"packs": count, "bytes": result["bytes"]}

    @pytest.mark.parametrize("provider,count", [("kartverket", 9651), ("lantmateriet", 2396)])
    def test_whole_box_to_z17_never_builds_a_set(self, tmp_path, provider, count):
        script = (
            self.setup(provider)
            + """
            // A whole-map estimate and download must work without allocating
            // any tile or pack set, even for the 449,790 z17 tiles in Norway.
            globalThis.Set = function () { throw Error('whole-map set allocated'); };
            var levels = levelsFor(null, 17, 1), walk = packWalk(levels), count = 0;
            while (walk.next()) {
                if (++count > 10000) throw Error('pack iterator did not terminate');
            }
            console.log(JSON.stringify({count, weighed: weigh(levels).packs}));
        """
        )
        assert TestPackWorker.run_worker(tmp_path, script, provider) == {"count": count, "weighed": count}

    @pytest.mark.parametrize("provider", ["kartverket", "lantmateriet"])
    def test_whole_map_budget_waits_for_a_request_and_is_counted_once(self, tmp_path, provider):
        panel = files("trails.visualization").joinpath("js", "offline_panel.js").read_text(encoding="utf-8")
        budget = "var memo = {};" + panel.split("var memo = {};", 1)[1].split("var chosen = null;", 1)[0]
        script = (
            self.setup(provider)
            + self.function("sig")
            + """
            var CAP_ZOOM = 17, weighs = 0, originalWeigh = weigh;
            function coreOf() { return null; }
            function scopeOf() { return {pad: 1}; }
            weigh = function (levels) { weighs++; return originalWeigh(levels); };
            """
            + budget
            + """
            var before = {weighs, cap, entries: Object.keys(memo).length};
            var first = budget(), second = budget(), estimate = cost('all', CAP_ZOOM).bytes;
            console.log(JSON.stringify({before, weighs, agrees: first > 0 && first === second && second === estimate}));
            """
        )
        assert TestPackWorker.run_worker(tmp_path, script, provider) == {
            "before": {"weighs": 0, "cap": None, "entries": 0},
            "weighs": 1,
            "agrees": True,
        }

    @pytest.mark.parametrize(
        "provider,position,overview,tiny",
        [
            ("kartverket", (65.55, 13.05), {"packs": 73, "bytes": 42219642}, {"packs": 131, "bytes": 83626772}),
            ("lantmateriet", (68.32, 18.72), {"packs": 23, "bytes": 16723884}, {"packs": 81, "bytes": 51462724}),
        ],
    )
    def test_overview_keeps_the_sheet_and_overlays_but_only_scope_heights(self, tmp_path, provider, position, overview, tiny):
        script = (
            self.setup(provider)
            + f"var position = {json.dumps(position)};"
            + """
            var centre = fracTile(position[0], position[1], 14);
            var x = Math.floor(centre.x), y = Math.floor(centre.y);
            var levels = levelsFor(function () { return new Set([key(x, y)]); }, 14, 1);
            var walk = packWalk(levels), row, heights = [], expected = new Set();
            // Independent scope pyramid, including its padded z11 ground:
            // the overview must neither enlarge it nor erase it at that level.
            for (var z = 11; z <= HEIGHTS.zoom; z++) {
                var sx = x >> (14 - z), sy = y >> (14 - z), edge = edgeAt(z);
                for (var dx = -1; dx <= 1; dx++) {
                    for (var dy = -1; dy <= 1; dy++) {
                        var px = sx + dx, py = sy + dy;
                        if (px < edge.x0 || px > edge.x1 || py < edge.y0 || py > edge.y1) continue;
                        expected.add(packFor(new URL(HEIGHTS.url.split('{z}')[0], location.href).href +
                            z + '/' + px + '/' + py + '.png').url);
                    }
                }
            }
            while ((row = walk.next())) { if (row.kind === 'height') heights.push(row.url); }
            var overviewLevels = {};
            for (var z = 8; z <= 11; z++) overviewLevels[z] = overviewAt(z);
            var overviewKinds = new Set(); walk = packWalk(overviewLevels);
            while ((row = walk.next())) overviewKinds.add(row.kind);
            console.log(JSON.stringify({overview: overviewCost(), tiny: weigh(levels),
                kinds: Array.from(overviewKinds).sort(), heights: heights.sort(), expected: Array.from(expected).sort()}));
        """
        )
        result = TestPackWorker.run_worker(tmp_path, script, provider)
        assert result["overview"] == overview
        assert result["tiny"] == tiny
        assert result["kinds"] == ["forest", "map", "mire", "shade", "slope", "vegetation"]
        assert len(result["heights"]) == 4
        assert result["heights"] == result["expected"]

    @pytest.mark.parametrize("provider", ["kartverket", "lantmateriet"])
    def test_sparse_scope_addresses_match_worker_at_every_zoom(self, tmp_path, provider):
        script = (
            self.setup(provider)
            + """
            var results = [];
            for (var selected = 8; selected <= TOP; selected++) {
                var levels = {}, expected = new Set();
                for (var z = 8; z <= selected; z++) {
                    var edge = edgeAt(z);
                    levels[z] = new Set([key(edge.x0, edge.y0), key(edge.x1, edge.y1)]);
                    packLayers().forEach(function (layer) {
                        if (z > layer.top) return;
                        levels[z].forEach(function (v) {
                            expected.add(packFor(new URL(layer.prefix, location.href).href + z + '/' +
                                keyX(v) + '/' + keyY(v) + '.png').url);
                        });
                    });
                }
                var walk = packWalk(levels), actual = [], next;
                while ((next = walk.next())) {
                    actual.push(next.url);
                    if (actual.length > 1000) throw Error('pack iterator did not terminate');
                }
                results.push({actual: actual.sort(), expected: Array.from(expected).sort()});
            }
            console.log(JSON.stringify(results));
        """
        )
        for result in TestPackWorker.run_worker(tmp_path, script, provider):
            assert result["actual"] == result["expected"]

    def test_both_upgrade_handlers_drop_tiles_and_its_obsolete_count(self):
        panel = files("trails.visualization").joinpath("js", "offline_panel.js").read_text(encoding="utf-8")
        worker = files("trails.visualization").joinpath("js", "worker.js").read_text(encoding="utf-8")
        assert "made.deleteObjectStore('tiles')" in panel
        assert 'made.deleteObjectStore("tiles")' in worker
        assert "ask.transaction.objectStore('flags').delete(HELD)" in panel
        assert 'ask.transaction.objectStore(FLAGS).delete("held")' in worker
        assert "answer.blob()" not in panel

    def test_the_scale_reads_the_current_sheet_ceiling(self):
        scale = files("trails.visualization").joinpath("js", "scale_zoom.js").read_text(encoding="utf-8")
        assert "zoom > options.maxNativeZoom" in scale
        assert "' · tiles z' + options.maxNativeZoom" in scale
        assert "trailsnativezoom" in scale

    def test_scale_ignores_vector_layers_but_follows_sheet_and_kept_zoom_changes(self, tmp_path):
        scale = files("trails.visualization").joinpath("js", "scale_zoom.js").read_text(encoding="utf-8")
        scale = scale.replace("{{ this._parent.get_name() }}", "namedMap")
        script = (
            """
            var handlers = {}, scans = 0, line;
            var box = {appendChild: function (made) { line = made; line.parentNode = box; }};
            var sheet = {getTileUrl: function () {}, options: {maxNativeZoom: 17}};
            var layers = [sheet], zoom = 18;
            var namedMap = {
                getContainer: () => ({querySelector: () => box}),
                getCenter: () => ({lat: 65.5}), containerPointToLatLng: p => p,
                distance: () => 100, getZoom: () => zoom,
                eachLayer: fn => { scans++; layers.forEach(fn); },
                on: (events, fn) => { events.split(' ').forEach(event => { handlers[event] = fn; }); },
                whenReady: fn => fn()
            };
            var document = {createElement: () => ({})};
            var L = {control: {scale: () => ({addTo: () => {}})}};
        """
            + scale
            + """
            var initial = line.textContent, initialScans = scans;
            for (var i = 0; i < 12500; i++) {
                var path = {options: {}};
                layers.push(path); handlers.layeradd({layer: path});
                handlers.layerremove({layer: path}); layers.pop();
            }
            var vectorScans = scans - initialScans;
            layers = []; handlers.layerremove({layer: sheet});
            var removed = line.textContent;
            layers = [sheet]; handlers.layeradd({layer: sheet});
            var added = line.textContent;
            zoom = 17; sheet.options.maxNativeZoom = 16; handlers.trailsnativezoom();
            var kept = line.textContent;
            sheet.options.maxNativeZoom = 17; handlers.trailsnativezoom();
            var restored = line.textContent;
            zoom = 18; handlers.zoomend();
            console.log(JSON.stringify({initial, vectorScans, removed, added, kept, restored, zoomed: line.textContent}));
        """
        )
        assert TestPackWorker.run_worker(tmp_path, script) == {
            "initial": "z18 · 1 m/px · tiles z17",
            "vectorScans": 0,
            "removed": "z18 · 1 m/px",
            "added": "z18 · 1 m/px · tiles z17",
            "kept": "z17 · 1 m/px · tiles z16",
            "restored": "z17 · 1 m/px",
            "zoomed": "z18 · 1 m/px · tiles z17",
        }
