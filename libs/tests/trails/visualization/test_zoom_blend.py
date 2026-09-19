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
    isLoading() { return !!this.loading; }
    start() { this.loading = true; this.fire('loading'); }
    load() { this.loading = false; this.fire('load'); }
}
const L = {GridLayer}, classes = new Set(), layers = new Set();
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
function fireTimer() {
    assert.equal(timers.size, 1);
    const [id, timer] = [...timers][0];
    assert.equal(timer.ms, 1500);
    timers.delete(id); timer.fn();
}
const a = new GridLayer(), b = new GridLayer();
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
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed to execute the zoom blend unit tests")
    script = files("trails.visualization").joinpath("js", "zoom_blend.js").read_text()
    script = script.replace("{{ this._parent.get_name() }}", "globalThis.blendMap")
    subprocess.run(
        [node, "-"],
        input=HARNESS + "\nglobalThis.blendMap = map;\n" + script + "\n" + scenario,
        text=True,
        capture_output=True,
        check=True,
        timeout=15,
    )
