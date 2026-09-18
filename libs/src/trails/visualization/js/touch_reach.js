        (function () {
            var map = {{ this._parent.get_name() }};
            var FINGER = {{ this.finger_px }};
            var SLOP = {{ this.tap_slop_px }};
            // Read before it is replaced, so the mouse gets Leaflet's own
            // number back rather than a copy of it written down here.
            var MOUSE_SLOP = L.Draggable.prototype.options.clickTolerance;

            // The same test the chrome makes, made the same way: the class
            // first, so a browser check can drive a finger it does not have,
            // and the media query behind it so a page built without the chrome
            // still knows one when it sees one.
            function coarse() {
                var box = map.getContainer();
                return box.classList.contains('trails-coarse') ||
                    !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches);
            }

            // Merged onto the prototype rather than set on the instance:
            // Leaflet's own options object is the instance's prototype, and
            // `Draggable` reads `clickTolerance` afresh on every move, so this
            // reaches the map's dragging handler although it was built first.
            function apply() {
                L.Draggable.mergeOptions({clickTolerance: coarse() ? SLOP : MOUSE_SLOP});
            }
            apply();

            // How far the point is from what the layer *paints*, or null where
            // it is nowhere near. The bounding box is Leaflet's, padded again
            // here because the padding it was given was the old, thin one.
            function away(layer, point) {
                var box = layer._pxBounds;
                if (!box) { return null; }
                if (point.x < box.min.x - FINGER || point.x > box.max.x + FINGER ||
                        point.y < box.min.y - FINGER || point.y > box.max.y + FINGER) {
                    return null;
                }
                var paint = layer.options.stroke ? (layer.options.weight || 0) / 2 : 0;
                if (layer._point && layer._radius !== undefined) {
                    return Math.max(0, point.distanceTo(layer._point) - layer._radius - paint);
                }
                // A shape with an inside is not a distance question at all --
                // in it or not in it -- so it stays Leaflet's own answer.
                if (!layer._parts || (L.Polygon && layer instanceof L.Polygon)) {
                    return layer._containsPoint && layer._containsPoint(point) ? 0 : null;
                }
                // `_parts` and not `_rings`: clipped to the screen and
                // simplified for this zoom, which is both the cheaper list and
                // the one the reader is actually looking at.
                var near = Infinity;
                for (var i = 0; i < layer._parts.length; i += 1) {
                    var part = layer._parts[i];
                    for (var j = 1; j < part.length; j += 1) {
                        near = Math.min(near, L.LineUtil.pointToSegmentDistance(point, part[j - 1], part[j]));
                    }
                }
                return near === Infinity ? null : Math.max(0, near - paint);
            }

            var leaflets = L.Canvas.prototype._onClick;
            L.Canvas.include({
                _onClick: function (event) {
                    if (!coarse()) { return leaflets.call(this, event); }
                    var point = this._map.mouseEventToLayerPoint(event);
                    var hit = null;
                    var best = Infinity;
                    for (var order = this._drawFirst; order; order = order.next) {
                        var layer = order.layer;
                        // Leaflet's own switch for a line that is drawn but not
                        // to be clicked -- the planned route and the way to a
                        // goal are both drawn in panes that take no clicks, and
                        // a line nobody can hit is not what a tap meant.
                        if (!layer.options.interactive) { continue; }
                        var gap = away(layer, point);
                        if (gap === null || gap > FINGER) { continue; }
                        // Leaflet's rule, kept: a click that ended a drag is the
                        // end of the drag, not a click on whatever lay under it.
                        if ((event.type === 'click' || event.type === 'preclick') &&
                                this._map._draggableMoved(layer)) { continue; }
                        // `<=` and not `<`, so an exact tie goes to the layer
                        // drawn last -- Leaflet's own tie-break, and the one the
                        // layer order was chosen for.
                        if (gap <= best) { best = gap; hit = layer; }
                    }
                    this._fireEvent(hit ? [hit] : false, event);
                }
            });

            // **Everything the tap reached, nearest first.** The loop above
            // measures the gap to every line in order to pick one; *what else
            // was under there* is the same measurement asked a second way, and
            // it has to be the same one -- a row of choices offering a line the
            // tap could never have hit would be worse than no row.
            //
            // Not gated on a coarse pointer, although the winner still is:
            // which line a click *takes* is Leaflet's business under a mouse and
            // stays so, while six sources through one valley are no easier to
            // aim at with a pointer than with a thumb.
            function near(point) {
                var found = [];
                map.eachLayer(function (layer) {
                    if (!layer.options || !layer.options.interactive) { return; }
                    var gap = away(layer, point);
                    if (gap === null || gap > FINGER) { return; }
                    found.push({layer: layer, gap: gap});
                });
                found.sort(function (a, b) { return a.gap - b.gap; });
                return found;
            }

            // Exposed the way the graph and the highlight are: so a browser
            // check reads the reach and drives a tap at a measured distance
            // rather than guessing at one, and so plan mode -- which takes
            // every click before Leaflet sees it -- can tell a tap from the end
            // of a pan by the same number and the same arithmetic.
            window.trailsReach = {
                finger: FINGER,
                slop: function () { return coarse() ? SLOP : MOUSE_SLOP; },
                away: away,
                near: near,
                recount: apply
            };
        })();
