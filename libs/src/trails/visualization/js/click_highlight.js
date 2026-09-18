        (function () {
            var map = {{ this._parent.get_name() }};
            var groups = [{{ this.group_names|join(', ') }}];
            var boost = {{ this.weight_boost }};
            var dim = {{ this.dim_opacity }};
            var selected = null;
            //: The chosen line drawn a second time, over everything else this
            //: map puts on the ground.
            var lifted = [];

            function eachPath(fn) {
                groups.forEach(function (group) {
                    group.eachLayer(function (layer) {
                        if (layer.setStyle && layer.options.className) { fn(layer); }
                    });
                });
            }

            // Captured before anything is restyled, so a restore is always exact.
            eachPath(function (layer) {
                layer._baseStyle = {
                    color: layer.options.color,
                    weight: layer.options.weight,
                    opacity: layer.options.opacity
                };
            });

            function step_back(layer) {
                // Width is reset alongside the fade, or a route that was selected
                // a moment ago would stay widened underneath the new one.
                layer.setStyle({weight: layer._baseStyle.weight, opacity: dim});
            }

            // **`bringToFront` can only reach as far as its own pane.**
            // Reported from the device: a chosen line stays *under* the planned
            // route -- and that is not a stacking accident but the arrangement,
            // because the trails are Leaflet's overlay pane at 400 and a planned
            // route has a pane of its own at 460. Widening a line the route runs
            // along therefore widened something nobody could see.
            //
            // A pane above it, and the chosen line drawn into it a second time.
            // Not moved: a canvas layer belongs to the renderer of the pane it
            // was made in, and moving it would mean taking it out of the group
            // the legend switches and putting it back somewhere else. A copy is
            // one layer for as long as a selection lasts, and it takes no clicks
            // -- the line underneath is still the thing being tapped, and the
            // reach that ranks what a tap could have meant skips anything that
            // is not interactive, so it cannot be offered as a choice of its own.
            function liftPane() {
                if (!map.getPane('trailsPicked')) {
                    var pane = map.createPane('trailsPicked');
                    // Over the planned route at 460 and under the profile's own
                    // mark at 470: this is a line on the ground, and that is a
                    // reading of where somebody is on it.
                    pane.style.zIndex = 465;
                    pane.style.pointerEvents = 'none';
                }
                return 'trailsPicked';
            }

            function drop() {
                lifted.forEach(function (copy) { map.removeLayer(copy); });
                lifted = [];
            }

            function lift(layer) {
                if (!layer.getLatLngs) { return; }
                var base = layer._baseStyle;
                lifted.push(L.polyline(layer.getLatLngs(), {
                    color: base.color, weight: base.weight + boost, opacity: 1,
                    interactive: false, pane: liftPane(), className: 'trails-picked'
                }).addTo(map));
            }

            function clear() {
                if (selected === null) { return; }
                selected = null;
                drop();
                eachPath(function (layer) { layer.setStyle(layer._baseStyle); });
            }

            // **A tap somebody else has already answered.** The panel takes a
            // tap in reach of a planned route for the route, and a line under
            // that route must not light up as well -- but both handlers are on
            // the same click and this one runs second, so clearing from over
            // there was undone half a millisecond later. Measured: the trail
            // stayed widened with the route on the panel.
            //
            // Held for the turn of the loop the click is in, which is what makes
            // it a statement about *this* tap rather than a mode.
            var held = false;
            function hold() {
                held = true;
                clear();
                window.setTimeout(function () { held = false; }, 0);
            }

            function select(key) {
                // Restyling is the expensive part on a map with thousands of lines,
                // so only what actually changes is touched: the first selection
                // fades everything once, and each later one repaints just the two
                // routes involved.
                var previous = selected;
                selected = key;
                drop();
                eachPath(function (layer) {
                    var mine = layer.options.className === key;
                    if (mine) {
                        layer.setStyle({weight: layer._baseStyle.weight + boost, opacity: 1});
                        // Kept, because it is what puts the chosen line over the
                        // other trails in its own pane; the copy above is what
                        // puts it over what is drawn in the panes above that.
                        layer.bringToFront();
                        // A chain split into pieces is several layers and one
                        // selection, so every piece is lifted.
                        lift(layer);
                    } else if (previous === null || layer.options.className === previous) {
                        step_back(layer);
                    }
                });
            }

            eachPath(function (layer) {
                layer.on('click', function () {
                    if (held) { return; }
                    if (selected === layer.options.className) { clear(); } else { select(layer.options.className); }
                });
            });

            // Leaflet only fires a map click when the click hit no layer, so this
            // clears the selection on empty terrain without fighting the handler above.
            {{ this._parent.get_name() }}.on('click', clear);

            // **And a way in that is not a click**, because both of the ways out
            // above are clicks and something else can own those. Plan mode does:
            // it takes every click on the container and stops it there, so a
            // highlight made before switching it on had no way back and left the
            // whole map faded behind the route being planned. Exposed the way the
            // graph and the panel's selection are, so a browser check reads it
            // rather than measuring opacities.
            window.trailsHighlight = {
                clear: clear,
                // Let go, and stay let go for this click: what the panel calls
                // when a tap meant the planned route rather than the line the
                // route was drawn along.
                hold: hold,
                selected: function () { return selected; }
            };
        })();
