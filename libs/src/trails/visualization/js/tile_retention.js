// Leaflet 1.9.3's pruning, with the child depth changed from two to three.
// The sheet keeps old ground both ways; overlays keep the finer level just left.
(function () {
    var map = {{ this._parent.get_name() }};
    var tileReady = L.GridLayer.prototype._tileReady;
    map.on('zoomstart', function () {
        map._groundZooming = true;
        map.eachLayer(function (layer) {
            if (layer instanceof L.GridLayer) { layer._groundZoom = layer._tileZoom; }
        });
    });
    map.on('zoomend', function () { map._groundZooming = false; });

    L.GridLayer.include({
        _tileReady: function (coords, err, el) {
            var tile = this._tiles[this._tileCoordsToKey(coords)];
            if (!err && tile && tile.current && !this.options.retainGround) {
                for (var key in this._tiles) {
                    var old = this._tiles[key], fine = old.coords;
                    if (old.current || !old.loaded || fine.z <= coords.z) { continue; }
                    var scale = Math.pow(2, fine.z - coords.z);
                    if (Math.floor(fine.x / scale) === coords.x && Math.floor(fine.y / scale) === coords.y) {
                        tile._groundReplacement = true;
                        break;
                    }
                }
            }
            // Keep Leaflet's load/error events and loading bookkeeping. Its fade
            // starts at zero; replace that before this task can be painted.
            tileReady.call(this, coords, err, el);
            if (tile && tile._groundReplacement && this._tiles[this._tileCoordsToKey(coords)] === tile) {
                L.DomUtil.setOpacity(tile.el, 1);
                if (!tile.active) { this._onOpaqueTile(tile); }
                tile.active = true;
                this._pruneTiles();
            }
        },

        // Leaflet 1.9.3's fade loop, except a replacement stays opaque. Merely
        // setting opacity in _tileReady would be undone by the next fade frame.
        _updateOpacity: function () {
            if (!this._map || L.Browser.ielt9) { return; }
            L.DomUtil.setOpacity(this._container, this.options.opacity);
            var now = +new Date(), nextFrame = false, willPrune = false;
            for (var key in this._tiles) {
                var tile = this._tiles[key];
                if (!tile.current || !tile.loaded) { continue; }
                var fade = tile._groundReplacement ? 1 : Math.min(1, (now - tile.loaded) / 200);
                L.DomUtil.setOpacity(tile.el, fade);
                if (fade < 1) {
                    nextFrame = true;
                } else {
                    if (tile.active) { willPrune = true; }
                    else { this._onOpaqueTile(tile); }
                    tile.active = true;
                }
            }
            if (willPrune && !this._noPrune) { this._pruneTiles(); }
            if (nextFrame) {
                L.Util.cancelAnimFrame(this._fadeFrame);
                this._fadeFrame = L.Util.requestAnimFrame(this._updateOpacity, this);
            }
        },

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
                if (!this.options.retainGround &&
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
                } else if (!this.options.retainGround && tile.current && !tile.active) {
                    var left = this._groundZoom;
                    var current = tile.coords;
                    if (left > current.z) {
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
