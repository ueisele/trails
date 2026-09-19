// A pinch scales the old ground, which Leaflet keeps past load until pruning.
// Keep the four overlays unmultiplied until that ground is gone (phase 8e).
(function () {
    var map = {{ this._parent.get_name() }};
    var ZOOM_BLEND_WAIT_MS = 3000;
    var ZOOM_BLEND_POLL_MS = 50;
    var container = map.getContainer(), pending = new Set();
    // Temporary address switch for the phone's blend measurement, read once.
    var blend = new URLSearchParams(location.search).get('blend');
    if (blend === 'never') { container.classList.add('trails-zoom-blend'); return; }
    if (blend === 'always') { return; }
    var zooming = false, active = false, timer, poll;

    function finish() {
        clearTimeout(timer);
        clearTimeout(poll);
        timer = undefined;
        poll = undefined;
        active = false;
        pending.clear();
        container.classList.remove('trails-zoom-blend');
    }
    function currentTilesOnly() {
        var current = true;
        map.eachLayer(function (layer) {
            if (!(layer instanceof L.GridLayer) ||
                !/(?:^|\s)trails-(slope|vegetation|forest|mire)-tiles(?:\s|$)/.test(layer.options.className || '')) { return; }
            var tiles = layer._tiles || {};
            if (Object.keys(tiles).some(function (key) { return tiles[key].coords.z !== layer._tileZoom; })) { current = false; }
        });
        return current;
    }
    function settled() {
        clearTimeout(poll);
        poll = undefined;
        if (!active || zooming || pending.size !== 0) { return; }
        if (currentTilesOnly()) { finish(); }
        else { poll = setTimeout(settled, ZOOM_BLEND_POLL_MS); }
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
        clearTimeout(poll);
        timer = undefined;
        poll = undefined;
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
        settled();
        if (active) { timer = setTimeout(finish, ZOOM_BLEND_WAIT_MS); }
    });
})();
