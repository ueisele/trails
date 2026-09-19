// Leaflet 1.9.3's pruning, normally with the child depth changed from two to three.
// Keep already drawn ground until the coarser tiles arrive; create no tiles here.
(function () {
    // Temporary measurement switch, read once before any tile layer is added.
    var dropGround = new URLSearchParams(location.search).get('ground') === 'drop';
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
                if (!dropGround && tile.current && !tile.active) {
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
