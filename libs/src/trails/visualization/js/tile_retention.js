// Leaflet 1.9.3's pruning, with the child depth changed from two to three.
// Only the sheet keeps old ground while new tiles arrive; overlays fade in afresh.
(function () {
    L.GridLayer.include({
        _pruneTiles: function () {
            if (!this._map) { return; }

            var key, tile;
            var zoom = this._map.getZoom();
            if (zoom > this.options.maxZoom || zoom < this.options.minZoom) {
                this._removeAllTiles();
                return;
            }

            for (key in this._tiles) {
                tile = this._tiles[key];
                tile.retain = tile.current;
            }

            for (key in this._tiles) {
                tile = this._tiles[key];
                if (this.options.retainGround && tile.current && !tile.active) {
                    var coords = tile.coords;
                    if (!this._retainParent(coords.x, coords.y, coords.z, coords.z - 5)) {
                        this._retainChildren(coords.x, coords.y, coords.z, coords.z + 3);
                    }
                }
            }

            for (key in this._tiles) {
                if (!this._tiles[key].retain) { this._removeTile(key); }
            }
        }
    });
})();
