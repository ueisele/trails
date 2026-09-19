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
            // The same offset as Renderer._updateTransform, in layer pixels.
            var scale = this._map.getZoomScale(zoom, this._zoom);
            var half = this._map.getSize().multiplyBy(0.5 + this.options.padding);
            var offset = half.multiplyBy(-scale).add(this._map.project(this._center, zoom))
                .subtract(this._map._getNewPixelOrigin(center, zoom));
            var position = this._map.containerPointToLayerPoint(
                this._map.getSize().multiplyBy(-this.options.padding)).round();
            // The bitmap covers the viewport, without a CSS scale or transition.
            L.DomUtil.setPosition(this._container, position);
            this._pinchView = {scale: scale, offset: offset, position: position};
            this._redrawRequest = this._redrawRequest || L.Util.requestAnimFrame(this._redraw, this);
        },

        _onZoomEnd: function () {
            L.Util.cancelAnimFrame(this._redrawRequest);
            this._redrawRequest = null;
            this._pinchDrawing = false;
            this._pinchView = null;
            onZoomEnd.call(this);
        },

        _redraw: function () {
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
