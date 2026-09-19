"""Canvas pinch painting: emission, compensation and the redraw lifecycle."""

import shutil
import subprocess
from importlib.resources import files

import pytest
from trails.visualization import maps


@pytest.mark.parametrize("base", list(maps.BaseMap))
def test_pinch_draw_is_emitted_before_layers(base):
    """Install the Canvas override before any layer creates a renderer."""
    fmap = maps.create_map(center=(65.55, 13.05), base=base)
    html = fmap.get_root().render()
    script = files("trails.visualization").joinpath("js", "pinch_draw.js").read_text()
    assert html.count(script) == 1
    assert html.index(script) < html.index("L.tileLayer(")
    assert sum(isinstance(child, maps._PinchDraw) for child in fmap._children.values()) == 1


HARNESS = """
const assert = require('node:assert/strict');
class Point {
    constructor(x, y) { this.x = x; this.y = y; }
    add(p) { return new Point(this.x + p.x, this.y + p.y); }
    subtract(p) { return new Point(this.x - p.x, this.y - p.y); }
    multiplyBy(s) { return new Point(this.x * s, this.y * s); }
    divideBy(s) { return this.multiplyBy(1 / s); }
    round() { return new Point(Math.round(this.x), Math.round(this.y)); }
}
const bounds = (min, max) => ({min, max, getSize: () => max.subtract(min)});
const queue = new Map(); let next = 0, oldTransform = 0, oldEnd = 0, oldRedraw = 0, oldFill = 0, oldCircle = 0;
class Canvas {
    getEvents() { return {zoomend: this._onZoomEnd, zoom: () => {}}; }
    _updateTransform() { oldTransform++; }
    _onZoomEnd() { oldEnd++; }
    _redraw() { oldRedraw++; }
    _fillStroke() { oldFill++; }
    _updateCircle() { oldCircle++; }
}
Canvas.include = methods => Object.assign(Canvas.prototype, methods);
const L = {Canvas, Browser: {retina: false}, bounds,
    DomUtil: {setPosition: (element, position) => { element.position = position; }},
    Util: {requestAnimFrame: (fn, self) => { queue.set(++next, () => fn.call(self)); return next; },
        cancelAnimFrame: id => queue.delete(id)}};
function flush() { const pending = [...queue.values()]; queue.clear(); pending.forEach(fn => fn()); }
const canvas = new Canvas();
canvas.options = {padding: 0.1};
canvas._bounds = bounds(new Point(-40, -80), new Point(440, 880));
canvas._container = {}; canvas._center = new Point(200, 400); canvas._zoom = 10;
canvas._map = {getZoomScale: z => 2 ** (z - 10), getSize: () => new Point(400, 800),
    project: (p, z) => p.multiplyBy(2 ** (z - 10)), _getNewPixelOrigin: () => new Point(0, 0),
    containerPointToLayerPoint: p => p};
let draws = 0, clears = 0, transforms = [], saves = 0, arcs = [], strokes = [];
canvas._ctx = {save: () => saves++, restore: () => saves--,
    setTransform: (...t) => transforms.push(t), scale: () => {}, beginPath: () => {},
    arc: (...a) => arcs.push(a), fill: () => {}, setLineDash: dash => { canvas._ctx.dash = dash; },
    stroke: () => strokes.push({width: canvas._ctx.lineWidth, dash: canvas._ctx.dash})};
canvas._clear = () => { assert.equal(canvas._redrawBounds, null); clears++; };
const options = Object.freeze({fill: true, stroke: true, weight: 3, _dashArray: Object.freeze([6, 2]),
    fillOpacity: 0.2, opacity: 1, color: 'blue', lineCap: 'round', lineJoin: 'round'});
const layer = {_point: new Point(200, 400), _radius: 10, _radiusY: 5, _empty: () => false, options};
let drawnBounds;
canvas._draw = () => {
    draws++; drawnBounds = canvas._redrawBounds; canvas._drawing = true;
    canvas._updateCircle(layer); canvas._drawing = false;
};
"""


@pytest.mark.parametrize("scale", [0.5, 1.75, 4])
@pytest.mark.parametrize("retina", [False, True])
def test_pinch_compensates_without_mutating_paths(scale, retina):
    """Coalesce frames, transform geometry, compensate paint, then return to Leaflet."""
    run_script(
        f"""
        L.Browser.retina = {str(retina).lower()};
        const scale = {scale}, ratio = L.Browser.retina ? 2 : 1;
        canvas._updateTransform(canvas._center, 10); assert.equal(oldTransform, 1);
        canvas._fillStroke(canvas._ctx, layer); assert.equal(oldFill, 1);
        canvas._updateCircle(layer); assert.equal(oldCircle, 1);
        const events = canvas.getEvents(); assert.ok(events.zoom); events.zoomstart.call(canvas);
        for (let i = 0; i < 20; i++) canvas._updateTransform(canvas._center, 10 + Math.log2(scale));
        assert.equal(queue.size, 1); assert.equal(draws, 0); flush();
        assert.equal(draws, 1); assert.equal(clears, 1); assert.equal(saves, 0);
        assert.deepEqual(canvas._container.position, new Point(-40, -80));
        assert.ok(Math.abs(transforms[0][0] - ratio * scale) < 1e-9);
        assert.ok(Math.abs(transforms[0][3] - ratio * scale) < 1e-9);
        // The old origin maps to the same offset as Leaflet, less canvas position.
        const offset = new Point(-40 * scale, -80 * scale);
        assert.ok(Math.abs(transforms[0][0] * -40 + transforms[0][4] - ratio * (offset.x + 40)) < 1e-9);
        assert.ok(Math.abs(drawnBounds.min.x - -40 / scale) < 1e-9);
        assert.ok(Math.abs(drawnBounds.getSize().x - 480 / scale) < 1e-9);
        assert.ok(Math.abs(strokes[0].width * scale - 3) < 1e-9);
        assert.ok(strokes[0].dash.every((v, i) => Math.abs(v * scale - [6, 2][i]) < 1e-9));
        assert.ok(Math.abs(arcs[0][2] * scale - 10) < 1e-9);
        assert.equal(layer._radius, 10); assert.equal(layer._radiusY, 5);
        assert.equal(canvas._pinchScale, null); assert.equal(canvas._redrawBounds, null);
        flush(); assert.equal(draws, 1); // A held frame does no work.
        canvas._updateTransform(canvas._center, 11); assert.equal(queue.size, 1);
        events.zoomend.call(canvas); assert.equal(queue.size, 0); assert.equal(oldEnd, 1);
        assert.equal(canvas._pinchView, null); assert.equal(canvas._pinchDrawing, false);
        canvas._redraw(); assert.equal(oldRedraw, 1);
        canvas._updateTransform(canvas._center, 10); assert.equal(oldTransform, 2);
        canvas._fillStroke(canvas._ctx, layer); assert.equal(oldFill, 2);
        canvas._updateCircle(layer); assert.equal(oldCircle, 2);
        """
    )


def test_pinch_restores_context_if_drawing_throws():
    """A failed draw cannot leave compensation or the context transform installed."""
    run_script("""
        canvas._pinchStart(); canvas._updateTransform(canvas._center, 11);
        canvas._draw = () => { throw new Error('draw failed'); };
        assert.throws(flush, /draw failed/);
        assert.equal(saves, 0); assert.equal(canvas._pinchScale, null); assert.equal(canvas._redrawBounds, null);
    """)


def run_script(scenario: str) -> None:
    """Execute the packaged override with deterministic frames and drawing calls."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed to execute the pinch draw unit tests")
    script = files("trails.visualization").joinpath("js", "pinch_draw.js").read_text()
    subprocess.run([node, "-"], input=HARNESS + script + scenario, text=True, capture_output=True, check=True, timeout=15)
