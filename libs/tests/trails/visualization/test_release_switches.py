"""The measuring switches preserve ordinary retention and need no layer options."""

import json
import shutil
import subprocess
from importlib.resources import files

import pytest
from trails.visualization import maps


@pytest.mark.parametrize("search,drop", [("", False), ("?ground=other", False), ("?ground=drop", True), ("?tiles=plain&ground=drop", True)])
def test_ground_switch_prunes_loaded_old_ground_and_reads_once(search, drop):
    """Old parents/children go only under the switch; current pending tiles stay."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed to execute the retention tests")
    script = files("trails.visualization").joinpath("js", "tile_retention.js").read_text()
    harness = """
const assert = require('node:assert/strict');
const L = {GridLayer: {include: methods => Object.assign(layer, methods)}};
const layer = {
    _map: {getZoom: () => 12}, options: {minZoom: 0, maxZoom: 18},
    _removeTile(key) { delete this._tiles[key]; },
    _removeAllTiles() { this._tiles = {}; },
    _retainParent(x, y, z, min) {
        assert.equal(min, z - 5);
        this._tiles.parent.retain = true;
        return false;
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
    expected = ["active", "pending"] if drop else ["active", "child", "parent", "pending"]
    scenario = f"""
seed(); layer._pruneTiles();
assert.deepEqual(Object.keys(layer._tiles).sort(), {json.dumps(expected)});
location.search = {json.dumps("" if drop else "?ground=drop")};
seed(); layer._pruneTiles();
assert.deepEqual(Object.keys(layer._tiles).sort(), {json.dumps(expected)});
layer._map.getZoom = () => 19;
seed(); layer._pruneTiles(); assert.deepEqual(layer._tiles, {{}});
layer._map = null; layer._pruneTiles();
"""
    subprocess.run(
        [node, "-"],
        input=harness + f"\nconst location = {{search: {json.dumps(search)}}};\n" + script + scenario,
        text=True,
        capture_output=True,
        check=True,
        timeout=15,
    )


@pytest.mark.parametrize("base", list(maps.BaseMap))
def test_tile_rendering_switch_is_emitted_before_tiles(base):
    """Every page gets the scoped rule and the read-once address script."""
    html = maps.create_map(center=(65.55, 13.05), base=base).get_root().render()
    switch = "new URLSearchParams(location.search).get('tiles') === 'plain'"
    assert html.count(switch) == 1
    assert html.index(switch) < html.index("L.tileLayer(")
    assert ".leaflet-container.trails-tiles-plain .leaflet-tile { image-rendering: auto; }" in html


@pytest.mark.parametrize("search,plain", [("", False), ("?tiles=other", False), ("?tiles=plain", True), ("?ground=drop&tiles=plain", True)])
def test_tile_rendering_switch_reads_only_the_initial_address(search, plain):
    """Unknown values keep the ordinary theme; later address changes do nothing."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed to execute the tile-rendering tests")
    fmap = maps.create_map(center=(65.55, 13.05))
    element = next(child for child in fmap._children.values() if isinstance(child, maps._TileRendering))
    script = element._template.module.script(element, {})
    subprocess.run(
        [node, "-"],
        input=f"""
const assert = require('node:assert/strict');
const location = {{search: {json.dumps(search)}}}, classes = new Set();
const {fmap.get_name()} = {{getContainer: () => ({{classList: {{add: c => classes.add(c)}}}})}};
{script}
assert.equal(classes.has('trails-tiles-plain'), {json.dumps(plain)});
location.search = {json.dumps("" if plain else "?tiles=plain")};
assert.equal(classes.has('trails-tiles-plain'), {json.dumps(plain)});
""",
        text=True,
        capture_output=True,
        check=True,
        timeout=15,
    )
