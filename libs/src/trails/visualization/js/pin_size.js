            (function () {
                var map = {{ this._parent.get_name() }};
                function sized() {
                    // Full size from zoom 13, where a reader is looking at one
                    // place; seven tenths at 9 and below, where they are looking
                    // at the park.
                    var scale = Math.max(0.7, Math.min(1, 0.7 + (map.getZoom() - 9) * 0.075));
                    map.getContainer().style.setProperty('--trails-pin', scale.toFixed(3));
                }
                map.on('zoomend', sized);
                sized();
            })();
