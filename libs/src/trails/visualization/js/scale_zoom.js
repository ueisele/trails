            (function () {
                var map = {{ this._parent.get_name() }};
                var line = null;

                // **Ours rather than folium's, for one option.** folium's
                // `control_scale=True` emits `L.control.scale()` with no
                // arguments, and that draws a metric bar and an imperial one --
                // which under the zoom line below reads as the control drawn
                // twice. `maxWidth` is Leaflet's own default, written down
                // because the pairing in this docstring is arithmetic over it.
                L.control.scale({metric: true, imperial: false, maxWidth: 100, position: 'bottomleft'}).addTo(map);

                function said() {
                    var box = map.getContainer().querySelector('.leaflet-control-scale');
                    if (!box) { return; }
                    if (!line || line.parentNode !== box) {
                        line = document.createElement('div');
                        line.className = 'trails-scale-zoom';
                        box.appendChild(line);
                        // **Under the bar, which is where it was and where it
                        // belongs.** It went beside it for a while, to keep two
                        // lines out of the strip the home indicator sits on --
                        // and that was solving the wrong problem: the corner is
                        // now held inside the safe area, so there is nothing to
                        // squeeze out of. Asked for back the way it was.
                        //
                        // Not written into Leaflet's own scale line: that element
                        // has its text replaced on every move, and anything put
                        // inside it goes with it.
                    }
                    // The resolution the map is actually drawing at, asked of
                    // Leaflet rather than worked out from the zoom: a fractional
                    // zoom or a different projection would make the arithmetic
                    // here disagree with the ground the bar above it measured.
                    var middle = map.getCenter();
                    var across = map.distance(
                        map.containerPointToLatLng([0, 0]),
                        map.containerPointToLatLng([100, 0])) / 100;
                    var zoom = map.getZoom();
                    line.textContent = 'z' + (Math.round(zoom * 100) / 100) + ' · ' +
                        (across >= 10 ? Math.round(across) : Math.round(across * 100) / 100) + ' m/px';
                    map.eachLayer(function (layer) {
                        var options = layer.options || {};
                        if (!layer.getTileUrl || options.trailsShade || options.trailsSlope ||
                                options.trailsVegetation || options.trailsForest || options.trailsMire) { return; }
                        if (zoom > options.maxNativeZoom) { line.textContent += ' · tiles z' + options.maxNativeZoom; }
                    });
                    line.title = 'Zoom ' + zoom + ' at ' + middle.lat.toFixed(2) + '° N';
                }

                map.on('zoomend moveend trailsnativezoom', said);
                // Each path and pin fires layeradd during construction. Scanning
                // all layers for each of them made opening the large map quadratic.
                // Only tile layers can change the sheet's native zoom.
                map.on('layeradd layerremove', function (event) {
                    if (event.layer.getTileUrl) { said(); }
                });
                map.whenReady(said);
                said();
            })();
