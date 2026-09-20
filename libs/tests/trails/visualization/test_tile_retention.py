"""Only a sheet opts into keeping parents and children during a zoom change."""

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
