// Leaflet 1.9.3 returns pixel bounds at _tileZoom, including during overzoom.
// Pad in that same coordinate system: one tile, whatever its on-screen size.
(function () {
    var TILE_RING = 1;
    var tiledPixelBounds = L.GridLayer.prototype._getTiledPixelBounds;
    L.GridLayer.include({
        _getTiledPixelBounds: function (center) {
            var bounds = tiledPixelBounds.call(this, center);
            var margin = this.getTileSize().multiplyBy(TILE_RING);
            return L.bounds(bounds.min.subtract(margin), bounds.max.add(margin));
        }
    });
})();
