(function () {
    var secure = location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
    if (!secure || !('serviceWorker' in navigator) || navigator.serviceWorker.controller) { return; }
    var map = {{ this._parent.get_name() }}, pending = new Map();
    var add = map.addLayer, remove = map.removeLayer;
    map.addLayer = function (layer) {
        if (layer instanceof L.TileLayer) { pending.set(L.stamp(layer), layer); return this; }
        return add.call(this, layer);
    };
    map.removeLayer = function (layer) {
        pending.delete(typeof layer === 'number' ? layer : L.stamp(layer));
        return remove.call(this, layer);
    };
    function release() {
        clearTimeout(timer);
        navigator.serviceWorker.removeEventListener('controllerchange', controlled);
        map.addLayer = add; map.removeLayer = remove;
        pending.forEach(function (layer) { add.call(map, layer); });
        pending.clear();
    }
    function controlled() { if (navigator.serviceWorker.controller) { release(); } }
    var timer = setTimeout(release, 3000);
    navigator.serviceWorker.addEventListener('controllerchange', controlled);
    controlled();
})();
