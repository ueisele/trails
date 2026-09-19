// A pinch scales the old ground until the new tiles load. Keep WebKit from
// multiplying four scaled layer buffers during that interval (phase 8d).
(function () {
    var map = {{ this._parent.get_name() }};
    var ZOOM_BLEND_WAIT_MS = 1500;
    var container = map.getContainer(), pending = new Set();
    var zooming = false, active = false, timer;

    function finish() {
        clearTimeout(timer);
        timer = undefined;
        active = false;
        pending.clear();
        container.classList.remove('trails-zoom-blend');
    }
    function settled() {
        if (active && !zooming && pending.size === 0) { finish(); }
    }
    function loading(event) {
        if (active) { pending.add(event.target); }
    }
    function loaded(event) {
        pending.delete(event.target);
        settled();
    }
    function watch(layer) {
        if (!(layer instanceof L.GridLayer)) { return; }
        layer.on('loading', loading).on('load', loaded);
        if (active && layer.isLoading()) { pending.add(layer); }
    }
    map.eachLayer(watch);
    map.on('layeradd', function (event) { watch(event.layer); });
    map.on('layerremove', function (event) {
        var layer = event.layer;
        if (!(layer instanceof L.GridLayer)) { return; }
        layer.off('loading', loading).off('load', loaded);
        pending.delete(layer);
        settled();
    });
    map.on('zoomstart', function () {
        clearTimeout(timer);
        timer = undefined;
        active = true;
        zooming = true;
        pending.clear();
        container.classList.add('trails-zoom-blend');
        // Include a layer already loading when a second pinch interrupts the wait.
        map.eachLayer(function (layer) {
            if (layer instanceof L.GridLayer && layer.isLoading()) { pending.add(layer); }
        });
    });
    map.on('zoomend', function () {
        zooming = false;
        if (!active) { return; }
        if (pending.size === 0) { finish(); }
        else { timer = setTimeout(finish, ZOOM_BLEND_WAIT_MS); }
    });
})();
