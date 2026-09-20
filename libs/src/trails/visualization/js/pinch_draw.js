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
            try {
                this._draw();
            } finally {
                this._pinchScale = null;
                ctx.restore();
                this._redrawBounds = null;
            }
            if (snap && progress < 1 && this._map._animatingZoom) {
                this._redrawRequest = L.Util.requestAnimFrame(this._redraw, this);
            }
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
