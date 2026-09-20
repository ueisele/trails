"""Pinch move updates wait; only the measuring switch retains overlay ground."""

import json
import shutil
import subprocess
from importlib.resources import files

import pytest


@pytest.mark.parametrize("retain", [None, False, True])
@pytest.mark.parametrize("parent_covers", [False, True])
def test_only_the_sheet_keeps_old_ground_until_current_tiles_are_active(retain, parent_covers):
    """Exercise pending/active tiles, parent coverage, depth and zoom limits."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed to execute the retention tests")
    script = files("trails.visualization").joinpath("js", "tile_retention.js").read_text().replace("{{ this._parent.get_name() }}", "testMap")
    harness = """
const assert = require('node:assert/strict');
const L = {GridLayer: {include: methods => Object.assign(layer, methods)}};
const window = {location: {search: ''}};
const map = {on() {}};
const testMap = map;
const layer = {
    _map: {getZoom: () => 12}, options: {minZoom: 0, maxZoom: 18},
    _removeTile(key) { delete this._tiles[key]; },
    _removeAllTiles() { this._tiles = {}; },
    _retainParent(x, y, z, min) {
        assert.equal(min, z - 5);
        this._tiles.parent.retain = true;
        return parentCovers;
    },
    _retainChildren(x, y, z, max) {
        assert.equal(max, z + 3);
        this._tiles.child.retain = true;
    }
};
function seed() {
    layer._tiles = {
        pending: {current: true, active: false, coords: {x: 1, y: 1, z: 12}},
        active: {current: true, active: true, coords: {z: 12}},
        parent: {current: false, active: true, coords: {z: 11}},
        child: {current: false, active: true, coords: {z: 15}},
        outside: {current: false, active: true, coords: {z: 12}}
    };
}
"""
    expected = ["active", "pending"]
    if retain:
        expected = ["active", "parent", "pending"] if parent_covers else ["active", "child", "parent", "pending"]
    scenario = f"""
seed(); layer._pruneTiles();
assert.deepEqual(Object.keys(layer._tiles).sort(), {json.dumps(expected)});
layer._tiles.pending.active = true;
layer._pruneTiles();
assert.deepEqual(Object.keys(layer._tiles).sort(), ['active', 'pending']);
layer._map.getZoom = () => -1;
seed(); layer._pruneTiles(); assert.deepEqual(layer._tiles, {{}});
layer._map.getZoom = () => 19;
seed(); layer._pruneTiles(); assert.deepEqual(layer._tiles, {{}});
layer._map = null; layer._pruneTiles();
"""
    subprocess.run(
        [node, "-"],
        input=harness
        + f"\nconst parentCovers = {json.dumps(parent_covers)};\n"
        + (f"layer.options.retainGround = {json.dumps(retain)};\n" if retain is not None else "")
        + script
        + scenario,
        text=True,
        capture_output=True,
        check=True,
        timeout=15,
    )


GROUND_HARNESS = """
const assert = require('node:assert/strict');
const events = {};
const map = {
    zoom: 12, on(name, fn) { events[name] = fn; },
    eachLayer(fn) { fn(layer); }, getZoom() { return this.zoom; }
};
const testMap = map;
class GridLayer {
    static include(methods) { Object.assign(this.prototype, methods); }
    _update() { this.updates++; }
    _removeTile(key) { delete this._tiles[key]; }
    _removeAllTiles() { this._tiles = {}; }
    _tileCoordsToKey(c) { return [c.x, c.y, c.z].join(':'); }
    // Leaflet's ancestor/descendant walk, including its active short circuit.
    _retainParent(x, y, z, minZoom) {
        const x2 = Math.floor(x / 2), y2 = Math.floor(y / 2), z2 = z - 1;
        const tile = this._tiles[this._tileCoordsToKey({x: x2, y: y2, z: z2})];
        if (tile && tile.active) { tile.retain = true; return true; }
        else if (tile && tile.loaded) tile.retain = true;
        if (z2 > minZoom) return this._retainParent(x2, y2, z2, minZoom);
        return false;
    }
    _retainChildren(x, y, z, maxZoom) {
        for (let i = 2 * x; i < 2 * x + 2; i++) for (let j = 2 * y; j < 2 * y + 2; j++) {
            const tile = this._tiles[this._tileCoordsToKey({x: i, y: j, z: z + 1})];
            if (tile && tile.active) { tile.retain = true; continue; }
            else if (tile && tile.loaded) tile.retain = true;
            if (z + 1 < maxZoom) this._retainChildren(i, j, z + 1, maxZoom);
        }
    }
}
const L = {GridLayer};
const layer = new GridLayer();
Object.assign(layer, {_map: map, _tileZoom: 12, options: {minZoom: 0, maxZoom: 18}, updates: 0, _tiles: {}});
function tile(x, y, z, current, loaded, active) {
    const coords = {x, y, z};
    layer._tiles[layer._tileCoordsToKey(coords)] = {coords, current, loaded, active};
}
function levels() { return Object.values(layer._tiles).map(t => t.coords.z).sort((a, b) => a - b); }
"""


def run_ground(scenario: str, search: str = "") -> None:
    """Run the pruning override with Leaflet's loaded/active traversal semantics.

    Args:
        scenario: JavaScript assertions after installing the override.
        search: Address query read when installing it.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed to execute the retention tests")
    script = files("trails.visualization").joinpath("js", "tile_retention.js").read_text().replace("{{ this._parent.get_name() }}", "testMap")
    subprocess.run(
        [node, "-"],
        input=GROUND_HARNESS + f"\nconst window = {{location: {{search: {json.dumps(search)}}}}};\n" + script + scenario,
        text=True,
        capture_output=True,
        check=True,
        timeout=15,
    )


def test_move_updates_wait_for_zoomend_but_drags_and_detached_layers_still_work():
    """Zoom events still own their updates; only the move callback is suppressed."""
    run_ground("""
layer._onMoveEnd(); assert.equal(layer.updates, 1);
events.zoomstart();
layer._onMoveEnd(); assert.equal(layer.updates, 1);
map._animatingZoom = true;
layer._onMoveEnd(); assert.equal(layer.updates, 1);
map._animatingZoom = false;
layer._onMoveEnd(); assert.equal(layer.updates, 1);
events.zoomend();
layer._onMoveEnd(); assert.equal(layer.updates, 2);
map._animatingZoom = true;
layer._onMoveEnd(); assert.equal(layer.updates, 2);
layer._map = null; layer._onMoveEnd(); assert.equal(layer.updates, 2);
""")


@pytest.mark.parametrize("search", ["", "?ground=drop", "?ground=overlays"])
@pytest.mark.parametrize("left,target", [(12, 15), (15, 12), (12, 16), (16, 12)])
@pytest.mark.parametrize("active", [False, True])
def test_overlay_retains_only_loaded_left_level_and_only_until_activation(search, left, target, active):
    """Keep fading as well as active old tiles, but never unloaded or unrelated ones."""
    keep = search == "?ground=overlays"
    run_ground(
        f"""
layer._tileZoom = {left}; events.zoomstart();
map.zoom = layer._tileZoom = {target};
tile(0, 0, {target}, true, false, false);
tile(0, 0, {left}, false, true, {json.dumps(active)});
// Unloaded old ground and loaded old ground outside the current tile's area.
tile(1, 0, {left}, false, false, false);
tile(100, 100, {left}, false, true, true);
// An active intervening ancestor/child must not stop the walk short.
tile(0, 0, 14, false, true, true);
// Nor may an older chain survive another release.
tile(0, 0, 10, false, true, true);
layer._pruneTiles();
assert.deepEqual(levels(), {json.dumps(sorted([target, left] if keep else [target]))});
const current = layer._tiles['0:0:{target}'];
current.loaded = true; layer._pruneTiles();
assert.deepEqual(levels(), {json.dumps(sorted([target, left] if keep else [target]))});
current.active = true; layer._pruneTiles();
assert.deepEqual(levels(), [{target}]);
events.zoomend();
""",
        search,
    )


def test_overlay_switch_is_read_once_and_a_second_release_drops_the_older_level():
    """Rapid successive releases keep one left level even while images are fading."""
    run_ground(
        """
window.location.search = '';
events.zoomstart();
layer._tileZoom = map.zoom = 16;
tile(0, 0, 12, false, true, true);
tile(0, 0, 16, true, true, false);
layer._pruneTiles(); assert.deepEqual(levels(), [12, 16]);
events.zoomend(); events.zoomstart();
layer._tileZoom = map.zoom = 15;
layer._tiles['0:0:16'].current = false;
tile(0, 0, 15, true, false, false);
layer._pruneTiles(); assert.deepEqual(levels(), [15, 16]);
""",
        "?ground=overlays",
    )


@pytest.mark.parametrize("search", ["", "?ground=overlays"])
@pytest.mark.parametrize("left,target,kept", [(12, 16, True), (16, 12, False), (15, 12, True), (11, 16, True), (10, 16, False)])
def test_sheet_depths_are_unchanged_with_and_without_switch(search, left, target, kept):
    """The sheet keeps five levels of parents and three of children in either mode."""
    run_ground(
        f"""
layer.options.retainGround = true;
layer._tileZoom = {left}; events.zoomstart();
layer._tileZoom = map.zoom = {target};
tile(0, 0, {left}, false, true, true);
tile(0, 0, {target}, true, false, false);
layer._pruneTiles();
assert.deepEqual(levels(), {json.dumps(sorted([target, left] if kept else [target]))});
""",
        search,
    )
