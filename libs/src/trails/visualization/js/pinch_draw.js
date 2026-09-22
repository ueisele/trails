// Leaflet 1.9.3: keep the last projection during zoom, but paint it in screen
// pixels. Only Canvas is changed; zoomend still projects and updates normally.
(function () {
    var canvas = L.Canvas.prototype;
    var getEvents = canvas.getEvents;
    var updateTransform = canvas._updateTransform;
    var onZoomEnd = canvas._onZoomEnd;
    var redraw = canvas._redraw;
    var fillStroke = canvas._fillStroke;
    var updateCircle = canvas._updateCircle;
    var updatePoly = canvas._updatePoly;
    var clipPoints = L.Polygon.prototype._clipPoints;
    var polygonClips = new WeakMap();
    var PINCH_CLIP_MARGIN = 0.5; // Spare ground on each side, reused until the view leaves it.

    L.Polygon.include({
        _clipPoints: function () {
            if (this._renderer instanceof L.Canvas) {
                // Remember the extent at the same time Leaflet makes the parts,
                // with exactly Polygon._clipPoints' stroke tolerance.
                var bounds = this._renderer._bounds, weight = this.options.weight;
                var padding = new L.Point(weight, weight);
                polygonClips.set(this, L.bounds(bounds.min.subtract(padding), bounds.max.add(padding)));
            }
            return clipPoints.call(this);
        }
    });
    var SNAP_DURATION = 250; // Leaflet 1.9.3's transform transition and fallback timer.

    // Invert x(t) for Leaflet's cubic-bezier(0,0,0.25,1), then read y(t).
    function snapEase(time) {
        if (time <= 0 || time >= 1) { return Math.max(0, Math.min(1, time)); }
        var low = 0, high = 1, t;
        for (var i = 0; i < 24; i++) {
            t = (low + high) / 2;
            var x = 0.75 * t * t * (1 - t) + t * t * t;
            if (x < time) { low = t; } else { high = t; }
        }
        return t * t * (3 - 2 * t);
    }

    L.Canvas.include({
        getEvents: function () {
            var events = getEvents.call(this);
            events.zoomstart = this._pinchStart;
            return events;
        },

        _pinchStart: function () {
            this._pinchDrawing = true;
            this._pinchPolygons = new Map();
        },

        _updateTransform: function (center, zoom) {
            if (!this._pinchDrawing) {
                return updateTransform.call(this, center, zoom);
            }
            var view = this._pinchViewAt(center, zoom);
            if (this._map._animatingZoom) {
                this._pinchSnap = {
                    start: this._pinchView || this._pinchViewAt(this._map.getCenter(), this._map.getZoom()),
                    end: view,
                    // CSS transitions share this frame's timeline time, even
                    // when intervening zoomanim handlers take time to run.
                    time: document.timeline.currentTime
                };
            } else {
                // Leaflet clears _animatingZoom before its final zoom event.
                this._pinchSnap = null;
                this._pinchView = view;
            }
            // The bitmap covers the viewport, without a CSS scale or transition.
            L.DomUtil.setPosition(this._container, view.position);
            this._redrawRequest = this._redrawRequest || L.Util.requestAnimFrame(this._redraw, this);
        },

        _pinchViewAt: function (center, zoom) {
            // The same offset as Renderer._updateTransform, in layer pixels.
            var scale = this._map.getZoomScale(zoom, this._zoom);
            var half = this._map.getSize().multiplyBy(0.5 + this.options.padding);
            var offset = half.multiplyBy(-scale).add(this._map.project(this._center, zoom))
                .subtract(this._map._getNewPixelOrigin(center, zoom));
            var position = this._map.containerPointToLayerPoint(
                this._map.getSize().multiplyBy(-this.options.padding)).round();
            return {scale: scale, offset: offset, position: position};
        },

        _onZoomEnd: function () {
            L.Util.cancelAnimFrame(this._redrawRequest);
            this._redrawRequest = null;
            this._pinchDrawing = false;
            this._pinchView = null;
            this._pinchSnap = null;
            this._pinchPolygons = null;
            onZoomEnd.call(this);
        },

        _redraw: function (time) {
            var snap = this._pinchSnap, progress;
            if (snap) {
                var now = time === undefined ? document.timeline.currentTime : time;
                progress = Math.max(0, Math.min(1, (now - snap.time) / SNAP_DURATION));
                var eased = snapEase(progress);
                this._pinchView = {
                    scale: snap.start.scale + (snap.end.scale - snap.start.scale) * eased,
                    offset: snap.start.offset.add(snap.end.offset.subtract(snap.start.offset).multiplyBy(eased)),
                    position: snap.end.position
                };
            }
            var view = this._pinchView;
            if (!this._pinchDrawing || !view) {
                return redraw.call(this);
            }
            this._redrawRequest = null;
            var ctx = this._ctx, scale = view.scale, ratio = L.Browser.retina ? 2 : 1;
            var origin = this._bounds.min;
            // Invert the viewport into the old projection. _draw's own bounds
            // test skips paths outside it and clips painting to that rectangle.
            var min = view.position.subtract(view.offset).divideBy(scale).add(origin);
            this._redrawBounds = null;
            this._clear();
            this._redrawBounds = L.bounds(min, min.add(this._bounds.getSize().divideBy(scale)));
            ctx.save();
            ctx.setTransform(ratio * scale, 0, 0, ratio * scale,
                ratio * (view.offset.x - view.position.x - scale * origin.x),
                ratio * (view.offset.y - view.position.y - scale * origin.y));
            this._pinchScale = scale;
            // Use the screen, not the padded bitmap: the old renderer padding
            // already covers a small zoom out without making any new parts.
            var visibleMin = this._map.containerPointToLayerPoint(new L.Point(0, 0))
                .subtract(view.offset).divideBy(scale).add(origin);
            this._pinchBounds = L.bounds(visibleMin, visibleMin.add(this._map.getSize().divideBy(scale)));
            try {
                this._draw();
            } finally {
                this._pinchScale = null;
                this._pinchBounds = null;
                ctx.restore();
                this._redrawBounds = null;
            }
            if (snap && progress < 1 && this._map._animatingZoom) {
                this._redrawRequest = L.Util.requestAnimFrame(this._redraw, this);
            }
        },

        _updatePoly: function (layer, closed) {
            if (!this._pinchScale || !closed || !this._drawing || layer.options.noClip) {
                return updatePoly.call(this, layer, closed);
            }
            var original = polygonClips.get(layer);
            // A polygon clipped before installation has no remembered extent.
            if (!original) {
                return updatePoly.call(this, layer, closed);
            }
            var held = this._pinchPolygons.get(layer);
            if (!held || held.original !== original) {
                held = {original: original, bounds: original, parts: layer._parts};
                this._pinchPolygons.set(layer, held);
            }
            var stroke = layer.options.weight / this._pinchScale;
            var padding = new L.Point(stroke, stroke), view = this._pinchBounds;
            var needed = L.bounds(view.min.subtract(padding), view.max.add(padding));
            if (!held.bounds.contains(needed)) {
                var margin = needed.getSize().multiplyBy(PINCH_CLIP_MARGIN);
                held.bounds = L.bounds(needed.min.subtract(margin), needed.max.add(margin));
                held.parts = this._pinchClipPolygon(layer, held.bounds);
            }
            // Both fill and stroke use the new extent; Leaflet's parts survive
            // even a failed paint, and its normal zoomend still owns the next clip.
            var parts = layer._parts;
            layer._parts = held.parts;
            try {
                return updatePoly.call(this, layer, closed);
            } finally {
                layer._parts = parts;
            }
        },

        _pinchClipPolygon: function (layer, bounds) {
            var parts = [];
            for (var i = 0; i < layer._rings.length; i++) {
                var part = L.PolyUtil.clipPolygon(layer._rings[i], bounds, true);
                if (part.length) {
                    parts.push(L.LineUtil.simplify(part, layer.options.smoothFactor));
                }
            }
            return parts;
        },

        _fillStroke: function (ctx, layer) {
            var scale = this._pinchScale;
            if (!scale) {
                return fillStroke.call(this, ctx, layer);
            }
            // Leaflet's fill/stroke, with screen-sized strokes and dash lengths.
            // Never change a path's options, including its weight or dash array.
            var options = layer.options;
            if (options.fill) {
                ctx.globalAlpha = options.fillOpacity;
                ctx.fillStyle = options.fillColor || options.color;
                ctx.fill(options.fillRule || 'evenodd');
            }
            if (options.stroke && options.weight !== 0) {
                if (ctx.setLineDash) {
                    ctx.setLineDash((options._dashArray || []).map(function (length) { return length / scale; }));
                }
                ctx.globalAlpha = options.opacity;
                ctx.lineWidth = options.weight / scale;
                ctx.strokeStyle = options.color;
                ctx.lineCap = options.lineCap;
                ctx.lineJoin = options.lineJoin;
                ctx.stroke();
            }
        },

        _updateCircle: function (layer) {
            var scale = this._pinchScale;
            if (!scale) {
                return updateCircle.call(this, layer);
            }
            if (!this._drawing || layer._empty()) { return; }
            var point = layer._point, ctx = this._ctx;
            // Round exactly as Leaflet does, then compensate, including ellipses.
            var radius = Math.max(Math.round(layer._radius), 1);
            var ratio = (Math.max(Math.round(layer._radiusY), 1) || radius) / radius;
            if (ratio !== 1) { ctx.save(); ctx.scale(1, ratio); }
            ctx.beginPath();
            ctx.arc(point.x, point.y / ratio, radius / scale, 0, Math.PI * 2, false);
            if (ratio !== 1) { ctx.restore(); }
            this._fillStroke(ctx, layer);
        }
    });
})();
