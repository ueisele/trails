// Leaflet 1.9.3's pruning, with the child depth changed from two to three.
// The sheet keeps old ground; ?ground=overlays measures one left level per overlay.
(function () {
    var map = {{ this._parent.get_name() }};
    var retainOverlays = new URLSearchParams(window.location.search).get('ground') === 'overlays';
    map.on('zoomstart', function () {
        map._groundZooming = true;
        map.eachLayer(function (layer) {
            if (layer instanceof L.GridLayer) { layer._groundZoom = layer._tileZoom; }
        });
    });
    map.on('zoomend', function () { map._groundZooming = false; });

    L.GridLayer.include({
        // updateWhenZooming guards the zoom path, but a throttled move can
        // otherwise enter _update's >1-level _setView fallback mid-pinch.
        _onMoveEnd: function () {
            if (!this._map || this._map._animatingZoom || this._map._groundZooming) { return; }
            this._update();
        },

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
                // A second release can arrive before the first level has faded.
                // Remove older levels before walking: an active intervening tile
                // would stop Leaflet's walk short of the level just left.
                if (retainOverlays && !this.options.retainGround &&
                    tile.coords.z !== this._tileZoom && tile.coords.z !== this._groundZoom) {
                    this._removeTile(key);
                    continue;
                }
                tile.retain = tile.current;
            }

            for (key in this._tiles) {
                tile = this._tiles[key];
                if (this.options.retainGround && tile.current && !tile.active) {
                    var coords = tile.coords;
                    if (!this._retainParent(coords.x, coords.y, coords.z, coords.z - 5)) {
                        this._retainChildren(coords.x, coords.y, coords.z, coords.z + 3);
                    }
                } else if (retainOverlays && tile.current && !tile.active) {
                    var left = this._groundZoom;
                    var current = tile.coords;
                    if (left < current.z) {
                        this._retainParent(current.x, current.y, current.z, left);
                    } else if (left > current.z) {
                        this._retainChildren(current.x, current.y, current.z, left);
                    }
                }
            }

            for (key in this._tiles) {
                if (!this._tiles[key].retain) { this._removeTile(key); }
            }
        }
    });
})();
