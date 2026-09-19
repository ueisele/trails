"""Zoom blending's event lifecycle, with deterministic tile events and timers."""

import shutil
import subprocess
from importlib.resources import files

import pytest
from jinja2 import Template
from trails.visualization import maps


@pytest.mark.parametrize("base", list(maps.BaseMap))
def test_zoom_blend_is_emitted_before_tile_layers(base):
    """Every map installs the listener before even deferred tile layers arrive."""
    fmap = maps.create_map(center=(65.55, 13.05), base=base)
    html = fmap.get_root().render()
    script = Template(files("trails.visualization").joinpath("js", "zoom_blend.js").read_text()).render(
        this=next(child for child in fmap._children.values() if isinstance(child, maps._ZoomBlend))
    )
    assert html.count(script) == 1
    assert html.index(script) < html.index("L.tileLayer(")
    for layer in ("slope", "vegetation", "forest", "mire"):
        assert f".trails-zoom-blend .leaflet-layer.trails-{layer}-tiles" in html
    assert "{ mix-blend-mode: normal; }" in html
    assert "{ mix-blend-mode: multiply; }" in html


HARNESS = """
const assert = require('node:assert/strict');
class Evented {
    constructor() { this.events = {}; }
    on(type, fn) { (this.events[type] ||= new Set()).add(fn); return this; }
    off(type, fn) { this.events[type]?.delete(fn); return this; }
    fire(type, data = {}) {
        for (const fn of [...(this.events[type] || [])]) fn({target: this, ...data});
        return this;
    }
}
class GridLayer extends Evented {
    constructor(className = '') { super(); this.options = {className}; this._tileZoom = 15; this._tiles = {}; }
    isLoading() { return !!this.loading; }
    start() { this.loading = true; this.fire('loading'); }
    load() { this.loading = false; this.fire('load'); }
}
const L = {GridLayer}, classes = new Set(), layers = new Set();
const location = {search: ''};
const map = new Evented();
map.getContainer = () => ({classList: {add: c => classes.add(c), remove: c => classes.delete(c)}});
map.eachLayer = fn => layers.forEach(fn);
map.add = layer => { layers.add(layer); map.fire('layeradd', {layer}); };
map.remove = layer => { layers.delete(layer); map.fire('layerremove', {layer}); };
const timers = new Map(); let nextTimer = 0;
function setTimeout(fn, ms) { const id = ++nextTimer; timers.set(id, {fn, ms}); return id; }
function clearTimeout(id) { timers.delete(id); }
function on() { assert.equal(classes.has('trails-zoom-blend'), true); }
function off() { assert.equal(classes.has('trails-zoom-blend'), false); }
function fireTimer(ms = 3000) {
    const matches = [...timers].filter(([id, timer]) => timer.ms === ms);
    assert.equal(matches.length, 1);
    const [id, timer] = matches[0];
    timers.delete(id); timer.fn();
}
const a = new GridLayer('trails-slope-tiles'), b = new GridLayer('trails-mire-tiles');
map.add(a); // A layer already present when the listener is installed.
"""


@pytest.mark.parametrize(
    "scenario",
    [
        pytest.param(
            """
            map.add(b);
            map.fire('zoomstart'); on();
            a.start(); b.start();
            map.fire('zoomend'); on();
            a.load(); on();
            b.load(); off(); assert.equal(timers.size, 0);
        """,
            id="wait-for-every-layer",
        ),
        pytest.param(
            """
            map.fire('zoomstart'); on();
            a.start(); a.load(); on(); assert.equal(timers.size, 0);
            map.fire('zoomend'); off(); assert.equal(timers.size, 0);
        """,
            id="loaded-before-zoomend",
        ),
        pytest.param(
            """
            map.fire('zoomstart'); on();
            map.fire('zoomend'); off(); assert.equal(timers.size, 0);
        """,
            id="no-loading",
        ),
        pytest.param(
            """
            a.start(); map.fire('zoomstart'); map.fire('zoomend'); on();
            fireTimer(); off();
            a.load(); off();
        """,
            id="existing-load-and-fallback",
        ),
        pytest.param(
            """
            map.fire('zoomstart'); a.start(); map.fire('zoomend');
            assert.equal(timers.size, 1);
            map.fire('zoomstart'); on(); assert.equal(timers.size, 0);
            a.load(); on(); map.fire('zoomend'); off();
            assert.equal(timers.size, 0);
        """,
            id="new-pinch-cancels-old-fallback",
        ),
        pytest.param(
            """
            map.fire('zoomstart'); a.start(); map.fire('zoomend');
            map.fire('zoomstart'); map.fire('zoomend'); on();
            a.load(); off(); assert.equal(timers.size, 0);
        """,
            id="new-zoom-inherits-unfinished-load",
        ),
        pytest.param(
            """
            map.fire('zoomstart'); a.start(); map.fire('zoomend');
            b.start(); map.add(b); // onAdd may start tiles before layeradd.
            a.load(); on(); b.load(); off();
        """,
            id="layer-added-while-waiting",
        ),
        pytest.param(
            """
            map.add(b); map.fire('zoomstart'); a.start(); b.start(); map.fire('zoomend');
            map.remove(a); on(); map.remove(b); off(); assert.equal(timers.size, 0);
            assert.equal(a.events.load.size, 0);
            map.add(a); map.fire('zoomstart'); map.fire('zoomend'); on();
            a.load(); off(); assert.equal(timers.size, 0);
        """,
            id="removed-layers-do-not-strand-wait",
        ),
        pytest.param(
            """
            map.add(b); map.fire('zoomstart'); a.start(); b.start(); map.fire('zoomend');
            a._tiles = {old: {coords: {z: 14}}, current: {coords: {z: 15}}};
            b._tiles = {old: {coords: {z: 16}}};
            a.load(); on(); b.load(); on();
            fireTimer(50); on(); delete a._tiles.old;
            fireTimer(50); on(); delete b._tiles.old;
            fireTimer(50); off(); assert.equal(timers.size, 0);
        """,
            id="all-blended-layers-must-lose-older-and-newer-tiles",
        ),
        pytest.param(
            """
            map.add(b); map.fire('zoomstart'); a.start(); b.start(); map.fire('zoomend');
            a.load(); on(); assert.equal([...timers.values()].some(t => t.ms === 50), false);
            b.load(); off(); assert.equal(timers.size, 0);
        """,
            id="current-tiles-still-wait-for-every-load",
        ),
        pytest.param(
            """
            a._tiles = {old: {coords: {z: 14}}};
            map.fire('zoomstart'); a.start(); a.load(); on();
            assert.equal(timers.size, 0); map.fire('zoomend'); on();
            delete a._tiles.old; fireTimer(50); off(); assert.equal(timers.size, 0);
        """,
            id="loaded-before-zoomend-still-waits-for-pruning",
        ),
        pytest.param(
            """
            a._tiles = {old: {coords: {z: 14}}};
            map.fire('zoomstart'); map.fire('zoomend'); on();
            fireTimer(50); on(); fireTimer(); off(); assert.equal(timers.size, 0);
        """,
            id="old-ground-fallback-clears-poll",
        ),
        pytest.param(
            """
            a._tiles = {old: {coords: {z: 14}}};
            map.fire('zoomstart'); map.fire('zoomend'); on(); assert.equal(timers.size, 2);
            map.fire('zoomstart'); on(); assert.equal(timers.size, 0);
            a._tiles = {}; a.start(); map.fire('zoomend'); on();
            a.load(); off(); assert.equal(timers.size, 0);
        """,
            id="new-pinch-cancels-pruning-poll-and-fallback",
        ),
        pytest.param(
            """
            a._tiles = {old: {coords: {z: 14}}};
            map.fire('zoomstart'); map.fire('zoomend'); on();
            map.remove(a); off(); assert.equal(timers.size, 0);
        """,
            id="removing-last-old-ground-finishes-wait",
        ),
        pytest.param(
            """
            map.fire('zoomstart'); a.start(); map.fire('zoomend');
            b._tiles = {old: {coords: {z: 14}}}; map.add(b);
            a.load(); on(); b._tiles = {}; fireTimer(50); off();
        """,
            id="added-blended-layer-old-ground-is-included",
        ),
        pytest.param(
            """
            const sheet = new GridLayer(); sheet._tiles = {old: {coords: {z: 14}}}; map.add(sheet);
            map.fire('zoomstart'); sheet.start(); map.fire('zoomend'); on();
            sheet.load(); off(); assert.equal(timers.size, 0);
        """,
            id="unblended-old-ground-does-not-hold-wait",
        ),
        pytest.param(
            """
            a._tileZoom = 15; a._tiles = {native: {coords: {z: 15}}};
            map.getZoom = () => 18;
            map.fire('zoomstart'); map.fire('zoomend'); off(); assert.equal(timers.size, 0);
        """,
            id="overzoom-compares-to-tile-zoom",
        ),
        pytest.param(
            """
            const vector = new Evented(); map.add(vector);
            map.fire('zoomstart'); vector.fire('loading'); map.fire('zoomend'); off();
            map.remove(vector); assert.equal(timers.size, 0);
        """,
            id="vector-events-do-not-hold-blend",
        ),
    ],
)
def test_zoom_blend_lifecycle(scenario):
    """Exercise the emitted event handlers without sleeping for a timeout."""
    run_blend_script(scenario)


@pytest.mark.parametrize("search,held", [("?blend=never", True), ("?blend=always", False)])
def test_zoom_blend_address_override(search, held):
    """Each override bypasses the lifecycle and is read just once."""
    expected = "on" if held else "off"
    run_blend_script(
        f"""
        {expected}();
        location.search = '?blend={"always" if held else "never"}';
        map.add(b); map.fire('zoomstart'); {expected}();
        a.start(); b.start(); map.fire('zoomend'); {expected}();
        a._tiles = {{old: {{coords: {{z: 14}}}}}};
        a.load(); b.load(); {expected}();
        assert.equal(timers.size, 0);
        """,
        before=f"location.search = '{search}';",
    )


def test_zoom_blend_unknown_switch_uses_default():
    """Only the two measurement values override the normal lifecycle."""
    run_blend_script("map.fire('zoomstart'); on(); map.fire('zoomend'); off();", before="location.search = '?blend=other';")


@pytest.mark.parametrize("layer", ["slope", "vegetation", "forest", "mire"])
def test_zoom_blend_recognizes_each_blended_layer(layer):
    """Each named overlay, even with additional classes, can hold the wait."""
    run_blend_script(
        f"""
        a.options.className = 'extra trails-{layer}-tiles extra';
        a._tiles = {{old: {{coords: {{z: 14}}}}}};
        map.fire('zoomstart'); map.fire('zoomend'); on();
        a._tiles = {{}}; fireTimer(50); off();
        """
    )


def run_blend_script(scenario: str, before: str = "") -> None:
    """Run a scenario against the emitted script with deterministic event delivery.

    Args:
        scenario: Assertions to run after installing the script.
        before: Setup needed before the script reads the address.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed to execute the zoom blend unit tests")
    script = files("trails.visualization").joinpath("js", "zoom_blend.js").read_text()
    script = script.replace("{{ this._parent.get_name() }}", "globalThis.blendMap")
    subprocess.run(
        [node, "-"],
        input=HARNESS + "\nglobalThis.blendMap = map;\n" + before + "\n" + script + "\n" + scenario,
        text=True,
        capture_output=True,
        check=True,
        timeout=15,
    )
