(function () {
    var secure = location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
    if (!secure || !('serviceWorker' in navigator) || navigator.serviceWorker.controller) { return; }
    var map = {{ this._parent.get_name() }}, pending = new Map();
    var add = map.addLayer, remove = map.removeLayer, has = map.hasLayer;
    var timer, released = false;
    map.addLayer = function (layer) {
        if (layer instanceof L.TileLayer) { pending.set(L.stamp(layer), layer); return this; }
        return add.call(this, layer);
    };
    map.removeLayer = function (layer) {
        pending.delete(typeof layer === 'number' ? layer : L.stamp(layer));
        return remove.call(this, layer);
    };
    // Controls must see the requested state while tiles wait for control, or
    // the relief checkbox starts off although its queued layer will be drawn.
    map.hasLayer = function (layer) {
        return !!layer && (pending.has(typeof layer === 'number' ? layer : L.stamp(layer)) || has.call(this, layer));
    };
    function release() {
        if (released) { return; }
        released = true;
        clearTimeout(timer);
        navigator.serviceWorker.removeEventListener('controllerchange', controlled);
        map.addLayer = add; map.removeLayer = remove; map.hasLayer = has;
        pending.forEach(function (layer) { add.call(map, layer); });
        pending.clear();
    }
    function controlled() { if (navigator.serviceWorker.controller) { release(); } }
    // The large page builds synchronously. Start the three-second wait when
    // that task yields, so construction cannot spend the control deadline.
    Promise.resolve().then(function () {
        if (!released) { timer = setTimeout(release, 3000); }
    });
    navigator.serviceWorker.addEventListener('controllerchange', controlled);
    controlled();
})();
