        (function () {
            var shape = {{ this.shape_json }};
            {{ this._parent.get_name() }}.eachLayer(function (layer) {
                // An empty list is a feature whose only line is the source, and
                // an empty list is falsy -- so this asks whether the option is
                // there and not whether it says anything.
                if (!layer.options || layer.options.popup === undefined) { return; }
                layer.bindPopup(function (source) {
                    return window.trailsPopup(shape, source.options.popup);
                }, {maxWidth: 320});
            });
        })();
