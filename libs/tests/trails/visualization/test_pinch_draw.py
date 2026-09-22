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
let clock = 0;
const document = {timeline: {get currentTime() { return clock; }}};
class Point {
    constructor(x, y) { this.x = x; this.y = y; }
    add(p) { return new Point(this.x + p.x, this.y + p.y); }
    subtract(p) { return new Point(this.x - p.x, this.y - p.y); }
    multiplyBy(s) { return new Point(this.x * s, this.y * s); }
    divideBy(s) { return this.multiplyBy(1 / s); }
    round() { return new Point(Math.round(this.x), Math.round(this.y)); }
}
const bounds = (min, max) => ({min, max, getSize: () => max.subtract(min),
    contains: b => b.min.x >= min.x && b.min.y >= min.y && b.max.x <= max.x && b.max.y <= max.y});
const queue = new Map(); let next = 0, oldTransform = 0, oldEnd = 0, oldRedraw = 0, oldFill = 0, oldCircle = 0;
class Canvas {
    getEvents() { return {zoomend: this._onZoomEnd, zoom: () => {}}; }
    _updateTransform() { oldTransform++; }
    _onZoomEnd() { oldEnd++; if (this.checkEnd) this.checkEnd(); }
    _redraw() { oldRedraw++; }
    _fillStroke() { oldFill++; }
    _updateCircle() { oldCircle++; }
    _updatePoly(layer, closed) {
        if (!this._drawing) return;
        this.painted = {parts: layer._parts, closed};
        if (this.failPoly) throw new Error('polygon draw failed');
    }
}
Canvas.include = methods => Object.assign(Canvas.prototype, methods);
class Polygon {
    _clipPoints() { this._parts = this.options.noClip ? this._rings : [[this._renderer._bounds.min]]; }
}
Polygon.include = methods => Object.assign(Polygon.prototype, methods);
const clips = [], simplifications = [];
const L = {Canvas, Polygon, Point, Browser: {retina: false}, bounds,
    PolyUtil: {clipPolygon: (ring, extent, round) => { clips.push({ring, extent, round}); return ring.slice(); }},
    LineUtil: {simplify: (part, tolerance) => { simplifications.push({part, tolerance}); return part.slice(); }},
    DomUtil: {setPosition: (element, position) => { element.position = position; }},
    Util: {requestAnimFrame: (fn, self) => { queue.set(++next, () => fn.call(self, clock)); return next; },
        cancelAnimFrame: id => queue.delete(id)}};
function flush() { const pending = [...queue.values()]; queue.clear(); pending.forEach(fn => fn()); }
const canvas = new Canvas();
canvas.options = {padding: 0.1};
canvas._bounds = bounds(new Point(-40, -80), new Point(440, 880));
canvas._container = {}; canvas._center = new Point(200, 400); canvas._zoom = 10;
canvas._map = {getZoomScale: z => 2 ** (z - 10), getSize: () => new Point(400, 800),
    getCenter: () => canvas._center, getZoom: () => 10,
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


def test_polygon_without_a_remembered_clip_keeps_its_parts():
    """Polygons clipped before installation still paint through Leaflet."""
    run_script("""
        const polygon = new Polygon(); polygon._renderer = canvas;
        polygon.options = {weight: 3.5, smoothFactor: 1};
        polygon._parts = [[new Point(0, 0), new Point(400, 0), new Point(400, 800)]];
        const original = polygon._parts;
        canvas._pinchStart(); canvas._drawing = true; canvas._pinchScale = 0.25;
        canvas._pinchBounds = bounds(new Point(-600, -1200), new Point(1000, 2000));
        canvas._updatePoly(polygon, true);
        assert.equal(canvas.painted.parts, original); assert.equal(canvas.painted.closed, true);
        assert.equal(polygon._parts, original); assert.equal(clips.length, 0);
        assert.equal(canvas._pinchPolygons.size, 0);
    """)


def test_polygon_retains_its_clip_until_the_view_leaves_it():
    """Remember the original extent and amortize new clipping across redraws."""
    run_script("""
        const polygon = new Polygon();
        polygon._renderer = canvas;
        polygon.options = {weight: 3.5, smoothFactor: 0.75};
        polygon._rings = [[new Point(-1000, -1000), new Point(1000, -1000), new Point(1000, 1000)]];
        polygon._clipPoints();
        const original = polygon._parts;
        // Changing the renderer later cannot change where these parts were clipped.
        canvas._bounds = bounds(new Point(100, 200), new Point(300, 600));
        canvas._pinchStart(); canvas._drawing = true; canvas._pinchScale = 1;
        canvas._pinchBounds = bounds(new Point(0, 0), new Point(400, 800));
        canvas._updatePoly(polygon, true);
        assert.equal(clips.length, 0); assert.equal(canvas.painted.parts, original);
        const held = canvas._pinchPolygons.get(polygon);
        assert.deepEqual(held.bounds.min, new Point(-43.5, -83.5));
        assert.deepEqual(held.bounds.max, new Point(443.5, 883.5));
        canvas._pinchScale = 0.25;
        canvas._pinchBounds = bounds(new Point(-600, -1200), new Point(1000, 2000));
        canvas._updatePoly(polygon, true);
        assert.equal(clips.length, 1); assert.equal(simplifications.length, 1);
        assert.equal(clips[0].ring, polygon._rings[0]); assert.equal(clips[0].round, true);
        assert.equal(simplifications[0].tolerance, polygon.options.smoothFactor);
        assert.notEqual(canvas.painted.parts, original); assert.equal(polygon._parts, original);
        const parts = canvas.painted.parts;
        canvas._pinchBounds = bounds(new Point(-610, -1210), new Point(1010, 2010));
        for (let i = 0; i < 5; i++) canvas._updatePoly(polygon, true);
        assert.equal(clips.length, 1); assert.equal(canvas.painted.parts, parts);
        canvas._pinchBounds = bounds(new Point(-3000, -6000), new Point(3400, 6800));
        canvas._updatePoly(polygon, true); assert.equal(clips.length, 2);
        canvas.checkEnd = () => {
            assert.equal(canvas._pinchPolygons, null); assert.equal(polygon._parts, original);
            polygon._clipPoints();
        };
        canvas._onZoomEnd(); assert.equal(oldEnd, 1);
        assert.notEqual(polygon._parts, original);
    """)


@pytest.mark.parametrize("snap", [False, True])
def test_polygon_restores_parts_even_when_paint_fails(snap):
    """Transient parts cannot leak into Leaflet through a failed pinch or snap draw."""
    run_script(
        f"""
        const polygon = new Polygon(); polygon._renderer = canvas;
        polygon.options = {{weight: 3.5, smoothFactor: 1}};
        polygon._rings = [[new Point(-1000, -1000), new Point(1000, -1000), new Point(1000, 1000)]];
        polygon._clipPoints(); const original = polygon._parts;
        canvas._draw = () => {{ canvas._drawing = true; canvas._updatePoly(polygon, true); }};
        canvas._pinchStart(); canvas._map._animatingZoom = {str(snap).lower()};
        canvas._updateTransform(canvas._center, 8); clock = 200; canvas.failPoly = true;
        assert.throws(flush, /polygon draw failed/);
        assert.equal(polygon._parts, original); assert.notEqual(canvas.painted.parts, original);
        assert.equal(canvas._pinchBounds, null); assert.equal(canvas._pinchScale, null); assert.equal(saves, 0);
        canvas.failPoly = false; canvas._onZoomEnd();
        assert.equal(canvas._pinchPolygons, null);
        """
    )


def test_polylines_unclipped_polygons_and_svg_keep_their_paths():
    """Only clipped Canvas polygons enter the retained pinch clipping path."""
    run_script("""
        const polygon = new Polygon(); polygon._renderer = canvas;
        polygon.options = {weight: 3.5, smoothFactor: 1};
        polygon._rings = [[new Point(0, 0)]]; polygon._clipPoints();
        canvas._pinchStart(); canvas._drawing = true; canvas._pinchScale = 0.25;
        canvas._pinchBounds = bounds(new Point(-600, -1200), new Point(1000, 2000));
        canvas._updatePoly(polygon, false);
        assert.equal(canvas.painted.parts, polygon._parts); assert.equal(clips.length, 0);
        polygon.options.noClip = true; polygon._clipPoints();
        canvas._updatePoly(polygon, true);
        assert.equal(canvas.painted.parts, polygon._rings); assert.equal(clips.length, 0);
        polygon._renderer = {_bounds: canvas._bounds}; polygon.options.noClip = false;
        polygon._clipPoints(); assert.equal(clips.length, 0);
        assert.equal(canvas._pinchPolygons.size, 0);
    """)


def test_pinch_restores_context_if_drawing_throws():
    """A failed draw cannot leave compensation or the context transform installed."""
    run_script("""
        canvas._pinchStart(); canvas._updateTransform(canvas._center, 11);
        canvas._draw = () => { throw new Error('draw failed'); };
        assert.throws(flush, /draw failed/);
        assert.equal(saves, 0); assert.equal(canvas._pinchScale, null); assert.equal(canvas._redrawBounds, null);
    """)


@pytest.mark.parametrize("pinched", [False, True])
@pytest.mark.parametrize("retina", [False, True])
def test_snap_follows_leaflet_curve_and_finishes_in_event_order(pinched, retina):
    """Interpolate scale and translation, keep paint sizes, and hand back at zoomend."""
    run_script(
        f"""
        L.Browser.retina = {str(retina).lower()};
        canvas._pinchStart();
        if ({str(pinched).lower()}) {{ canvas._updateTransform(canvas._center, 10.65); flush(); }}
        const start = canvas._pinchView || canvas._pinchViewAt(canvas._map.getCenter(), canvas._map.getZoom());
        const targetCenter = new Point(230, 410);
        canvas._map._getNewPixelOrigin = (center, zoom) => center.subtract(canvas._center).multiplyBy(2 ** (zoom - 10));
        const end = canvas._pinchViewAt(targetCenter, 11);
        canvas._map._animatingZoom = true;
        canvas._updateTransform(targetCenter, 11);
        assert.equal(queue.size, 1);
        // Parameter t=.5 on cubic-bezier(0,0,.25,1) gives x=.21875, y=.5.
        clock = 250 * 0.21875; flush();
        assert.ok(Math.abs(canvas._pinchView.scale - (start.scale + end.scale) / 2) < 1e-6);
        assert.ok(Math.abs(canvas._pinchView.offset.x - (start.offset.x + end.offset.x) / 2) < 1e-5);
        assert.ok(Math.abs(canvas._pinchView.offset.y - (start.offset.y + end.offset.y) / 2) < 1e-5);
        assert.equal(queue.size, 1);
        const scale = canvas._pinchView.scale;
        assert.ok(Math.abs(strokes.at(-1).width * scale - 3) < 1e-9);
        assert.ok(strokes.at(-1).dash.every((v, i) => Math.abs(v * scale - [6, 2][i]) < 1e-9));
        assert.ok(Math.abs(arcs.at(-1)[2] * scale - 10) < 1e-9);
        clock = 250; flush();
        assert.deepEqual(canvas._pinchView, end); assert.equal(queue.size, 0);
        // _onZoomTransitionEnd: clear flag, zoom (end transform), zoomend, moveend.
        canvas._map._animatingZoom = false;
        canvas._updateTransform(targetCenter, 11);
        assert.deepEqual(canvas._pinchView, end); assert.equal(canvas._pinchSnap, null);
        assert.equal(queue.size, 1);
        canvas._onZoomEnd();
        assert.equal(queue.size, 0); assert.equal(canvas._pinchView, null);
        assert.equal(canvas._pinchSnap, null); assert.equal(oldEnd, 1);
        canvas._redraw(); assert.equal(oldRedraw, 1);
        """
    )


def test_zoomend_cancels_an_unfinished_snap():
    """An early transition end must not leave a drawing callback behind."""
    run_script("""
        canvas._pinchStart(); canvas._map._animatingZoom = true;
        canvas._updateTransform(canvas._center, 11);
        clock = 30; flush(); assert.equal(queue.size, 1);
        canvas._map._animatingZoom = false;
        canvas._updateTransform(canvas._center, 11);
        assert.equal(canvas._pinchView.scale, 2);
        canvas._onZoomEnd(); assert.equal(queue.size, 0);
        const count = draws; clock = 300; flush(); assert.equal(draws, count);
        assert.equal(canvas._pinchSnap, null);
    """)


def test_snap_uses_the_frame_timestamp_when_other_handlers_take_time():
    """Paint the frame shared with CSS, regardless of when a callback executes."""
    run_script("""
        canvas._pinchStart(); canvas._map._animatingZoom = true;
        canvas._updateTransform(canvas._center, 11);
        queue.clear(); clock = 200;
        canvas._redraw(250 * 0.21875);
        assert.ok(Math.abs(canvas._pinchView.scale - 1.5) < 1e-6);
        assert.equal(queue.size, 1);
        canvas._onZoomEnd(); assert.equal(queue.size, 0);
    """)


def run_script(scenario: str) -> None:
    """Execute the packaged override with deterministic frames and drawing calls."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed to execute the pinch draw unit tests")
    script = files("trails.visualization").joinpath("js", "pinch_draw.js").read_text()
    subprocess.run([node, "-"], input=HARNESS + script + scenario, text=True, capture_output=True, check=True, timeout=15)
