        (function () {
            var map = {{ this._parent.get_name() }};
            var bases = [{{ this.base_names|join(', ') }}];
            var baseLabels = {{ this.base_labels_json }};
            var baseShown = {{ this.base_shown_json }};
            var layers = [{{ this.layer_names|join(', ') }}];
            var rows = {{ this.rows_json }};
            var title = {{ this.title_json }};
            var open = {{ 'false' if this.collapsed else 'true' }};

            // **What a reader switched stays switched over a reload.**
            // Reported from the phone, 2026-09-17: *"Nach jedem Neuladen wird
            // Slope Layer wieder deaktiviert."* Everything this panel switches
            // -- which sheet is underneath, how the ground on it is drawn, and
            // which of the map's own layers are drawn over it -- is a state a
            // reader is *in* while they walk, like the theme, like the offline
            // switch, like plan mode's *stay on paths*, all of which this page
            // already remembers. A page reloaded in a valley must not quietly
            // undo what somebody chose on the way up.
            //
            // **Per map, because both maps share one origin.** The key carries
            // the same name the caches and the offline switch do, so the second
            // map cannot answer for the first.
            //
            // **And only what the reader themself flipped.** A search result in
            // a layer that is off switches that layer on -- that is what it is
            // for -- and the tick follows the map; but nothing is written from
            // there, or looking a place up would quietly change what the map
            // draws the next morning.
            //
            // Storage can be denied outright -- Safari in private browsing
            // throws on read, not only on write -- and then the build's own
            // default stands, which is what it did before this existed.
            var GROUND_KEY = {{ this.ground_key_json }};

            function groundSaid(which) {
                try { return window.localStorage.getItem(GROUND_KEY + which); } catch (blocked) { return null; }
            }

            function groundKept(which, fallback) {
                var said = groundSaid(which);
                return said === null ? fallback : said === 'on';
            }

            function keepGround(which, want) {
                try { window.localStorage.setItem(GROUND_KEY + which, want ? 'on' : 'off'); } catch (blocked) { return; }
            }

            // **The layers under one key, by the name their row carries.** One
            // entry holding a word per label rather than one key per layer: a
            // build that renames a row, adds one or drops one finds nothing for
            // it and takes the build's own default, and there is nothing left
            // behind to clean up. The sheet is kept by its label for the same
            // reason and not by its index -- an index means a different sheet
            // the day a second one is offered.
            function keptLayers() {
                var text = groundSaid('layers');
                if (!text) { return {}; }
                try {
                    var said = JSON.parse(text);
                    return said && typeof said === 'object' ? said : {};
                } catch (broken) { return {}; }
            }

            function keepLayer(label, want) {
                var said = keptLayers();
                said[label] = want ? 'on' : 'off';
                try { window.localStorage.setItem(GROUND_KEY + 'layers', JSON.stringify(said)); } catch (blocked) { return; }
            }

            // The switch is drawn from what the reader kept and the map is then
            // put into that state, rather than the tick saying one thing and
            // the ground showing another.
            function standAs(layer, want) {
                if (want && !map.hasLayer(layer)) { map.addLayer(layer); }
                if (!want && map.hasLayer(layer)) { map.removeLayer(layer); }
            }

            var control = L.control({position: 'bottomleft'});
            control.onAdd = function () {
                var box = L.DomUtil.create('div', 'trails-legend');
                // **No 70vh here any more.** A fixed share of the window was the
                // one panel on this map that never asked what else was on
                // screen, and measured at 390 px it took 77 % of the map before
                // anything had been clicked — and its own fold handle left the
                // map at y = -206 the moment a profile opened, which is the
                // profile grip's old defect in a second place. The chrome caps
                // it against the profile panel now, the way the plan control is.
                box.style.cssText = 'background:var(--trails-panel);padding:8px 12px;border:1px solid var(--trails-edge);' +
                    'border-radius:4px;font-family:sans-serif;font-size:12px;line-height:1.4;' +
                    'overflow-y:auto';

                var header = document.createElement('div');
                header.className = 'trails-legend-head';
                header.style.cssText = 'font-weight:600;cursor:pointer;user-select:none';
                var body = document.createElement('div');
                body.className = 'trails-legend-body';

                // **Whichever base map was asked for, and only that one.**
                // Folium hands every base layer to the map and leaves it to the
                // layer control's template to take the unwanted ones off again;
                // with that control gone this does it, or two tile layers stack
                // and the last one drawn wins.
                var picked = document.createElement('div');
                // Its own name because the chrome lifts it out of here into a
                // panel of its own: which base map is drawn is a different
                // question from which overlays are on, and on a narrow screen
                // the two cannot share one list.
                picked.className = 'trails-basemap';
                picked.style.cssText = 'margin-bottom:6px;padding-bottom:6px;border-bottom:1px solid var(--trails-rule)';
                // Which sheet was chosen last, by the name on its row. A name
                // this build no longer offers matches nothing, and then the
                // build's own choice stands.
                var keptSheet = groundSaid('sheet');
                var wantedBase = keptSheet === null ? -1 : baseLabels.indexOf(keptSheet);
                bases.forEach(function (layer, index) {
                    var wantBase = wantedBase >= 0 ? index === wantedBase : !!baseShown[index];
                    standAs(layer, wantBase);
                    var line = document.createElement('label');
                    line.style.cssText = 'display:flex;align-items:center;gap:6px;margin:3px 0;cursor:pointer';
                    var pick = document.createElement('input');
                    pick.type = 'radio';
                    pick.name = 'trails-base-{{ this.get_name() }}';
                    pick.checked = wantBase;
                    pick.addEventListener('change', function () {
                        bases.forEach(function (other) {
                            if (other !== layer && map.hasLayer(other)) { map.removeLayer(other); }
                        });
                        if (!map.hasLayer(layer)) { map.addLayer(layer); }
                        try { window.localStorage.setItem(GROUND_KEY + 'sheet', baseLabels[index]); } catch (blocked) { return; }
                    });
                    var name = document.createElement('span');
                    name.textContent = baseLabels[index];
                    line.appendChild(pick);
                    line.appendChild(name);
                    picked.appendChild(line);
                });
                // **The relief shadow belongs to the sheet, not to the layers.**
                // It is neither a line nor a point and has no colour for the
                // legend to explain; it answers how the ground underneath is
                // drawn, which is this panel's one question. So it is a checkbox
                // under the sheets, where a reader who wants the map plain finds
                // it beside the choice of map -- and the legend stays a list of
                // things with a colour and a count (decisions §6.6).
                var relief = {{ this.relief_name }};
                if (relief) {
                    var shading = document.createElement('label');
                    shading.className = 'trails-relief';
                    shading.style.cssText = 'display:flex;align-items:center;gap:6px;margin:6px 0 3px;cursor:pointer';
                    var shadeTick = document.createElement('input');
                    shadeTick.type = 'checkbox';
                    shadeTick.style.cssText = 'flex:none;margin:0';
                    shadeTick.checked = groundKept('relief', map.hasLayer(relief));
                    standAs(relief, shadeTick.checked);
                    shadeTick.addEventListener('change', function () {
                        standAs(relief, shadeTick.checked);
                        keepGround('relief', shadeTick.checked);
                    });
                    var word = document.createElement('span');
                    word.textContent = 'Relief shading';
                    shading.appendChild(shadeTick);
                    shading.appendChild(word);
                    picked.appendChild(shading);
                }
                // **The slope classes, under the relief, with the colours they
                // are drawn in.** The same kind of thing as the shadow -- how
                // the ground is drawn -- so the same place; but these have
                // colours that mean something, so the rows that say what are
                // drawn under the checkbox, and only while it is on
                // (decisions §6.7). The two classes that are ours rather
                // than the SLF's or swisstopo's say so on their row.
                var slope = {{ this.slope_name }};
                var slopeClasses = {{ this.slope_classes_json }};
                if (slope) {
                    var classing = document.createElement('label');
                    classing.className = 'trails-slope';
                    classing.style.cssText = 'display:flex;align-items:center;gap:6px;margin:3px 0;cursor:pointer';
                    var slopeTick = document.createElement('input');
                    slopeTick.type = 'checkbox';
                    slopeTick.style.cssText = 'flex:none;margin:0';
                    slopeTick.checked = groundKept('slope', map.hasLayer(slope));
                    standAs(slope, slopeTick.checked);
                    var slopeWord = document.createElement('span');
                    slopeWord.textContent = 'Slope classes';
                    classing.appendChild(slopeTick);
                    classing.appendChild(slopeWord);
                    picked.appendChild(classing);
                    var slopeRows = document.createElement('div');
                    slopeRows.className = 'trails-slope-classes';
                    slopeRows.style.cssText = 'margin:0 0 4px 22px;font-size:12px;line-height:1.5';
                    slopeClasses.forEach(function (row) {
                        var line = document.createElement('div');
                        line.style.cssText = 'display:flex;align-items:center;gap:6px';
                        var swatch = document.createElement('span');
                        swatch.style.cssText = 'display:inline-block;width:18px;height:11px;flex:none;border:1px solid #999;'
                            + 'background:' + row.colour + ';opacity:0.6';
                        var text = document.createElement('span');
                        text.textContent = (row.to === null ? row.from + '° and more' : row.from + '–' + row.to + '°')
                            + (row.source === 'ours' ? ' (ours)' : '');
                        line.appendChild(swatch);
                        line.appendChild(text);
                        slopeRows.appendChild(line);
                    });
                    var slopeNote = document.createElement('div');
                    slopeNote.style.cssText = 'color:#666;margin-top:2px';
                    slopeNote.textContent = 'Steepness of the ground down its fall line; the profile grades the path.';
                    slopeRows.appendChild(slopeNote);
                    slopeRows.style.display = slopeTick.checked ? '' : 'none';
                    picked.appendChild(slopeRows);
                    slopeTick.addEventListener('change', function () {
                        standAs(slope, slopeTick.checked);
                        slopeRows.style.display = slopeTick.checked ? '' : 'none';
                        keepGround('slope', slopeTick.checked);
                    });
                }
                // **What stands on the ground, under the slope classes (§6.11).**
                // The same kind of thing again -- how the ground is drawn -- with
                // colours that mean something, so the rows sit under the
                // checkbox and show only while it is on. Two switches, because
                // the willow and the forest answer different questions.
                var vegetation = {{ this.vegetation_name }};
                var vegetationClasses = {{ this.vegetation_classes_json }};
                if (vegetation) {
                    var growing = document.createElement('label');
                    growing.className = 'trails-vegetation';
                    growing.style.cssText = 'display:flex;align-items:center;gap:6px;margin:3px 0;cursor:pointer';
                    var vegetationTick = document.createElement('input');
                    vegetationTick.type = 'checkbox';
                    vegetationTick.style.cssText = 'flex:none;margin:0';
                    vegetationTick.checked = groundKept('vegetation', map.hasLayer(vegetation));
                    standAs(vegetation, vegetationTick.checked);
                    var vegetationWord = document.createElement('span');
                    vegetationWord.textContent = 'Vegetation 0.5–5 m';
                    growing.appendChild(vegetationTick);
                    growing.appendChild(vegetationWord);
                    picked.appendChild(growing);
                    var vegetationRows = document.createElement('div');
                    vegetationRows.className = 'trails-vegetation-classes';
                    vegetationRows.style.cssText = 'margin:0 0 4px 22px;font-size:12px;line-height:1.5';
                    vegetationClasses.forEach(function (row) {
                        var line = document.createElement('div');
                        line.style.cssText = 'display:flex;align-items:center;gap:6px';
                        var swatch = document.createElement('span');
                        swatch.style.cssText = 'display:inline-block;width:18px;height:11px;flex:none;border:1px solid #999;'
                            + 'background:' + row.colour + ';opacity:0.6';
                        var text = document.createElement('span');
                        text.textContent = row.label;
                        line.appendChild(swatch);
                        line.appendChild(text);
                        vegetationRows.appendChild(line);
                    });
                    var vegetationNote = document.createElement('div');
                    vegetationNote.style.cssText = 'color:#666;margin-top:2px';
                    vegetationNote.textContent = 'How much of each 10 m cell carries bushes and low trees, by laser; under a tenth is not drawn, '
                        + 'and grey is ground nobody has flown.';
                    vegetationRows.appendChild(vegetationNote);
                    vegetationRows.style.display = vegetationTick.checked ? '' : 'none';
                    picked.appendChild(vegetationRows);
                    vegetationTick.addEventListener('change', function () {
                        standAs(vegetation, vegetationTick.checked);
                        vegetationRows.style.display = vegetationTick.checked ? '' : 'none';
                        keepGround('vegetation', vegetationTick.checked);
                    });
                }
                var forest = {{ this.forest_name }};
                var forestColour = {{ this.forest_colour_json }};
                if (forest) {
                    var wooded = document.createElement('label');
                    wooded.className = 'trails-forest';
                    wooded.style.cssText = 'display:flex;align-items:center;gap:6px;margin:3px 0;cursor:pointer';
                    var forestTick = document.createElement('input');
                    forestTick.type = 'checkbox';
                    forestTick.style.cssText = 'flex:none;margin:0';
                    forestTick.checked = groundKept('forest', map.hasLayer(forest));
                    standAs(forest, forestTick.checked);
                    var forestSwatch = document.createElement('span');
                    forestSwatch.style.cssText = 'display:inline-block;width:18px;height:11px;flex:none;border:1px solid #999;'
                        + 'background:' + forestColour + ';opacity:0.6';
                    var forestWord = document.createElement('span');
                    forestWord.textContent = 'Forest over 5 m';
                    wooded.appendChild(forestTick);
                    wooded.appendChild(forestSwatch);
                    wooded.appendChild(forestWord);
                    picked.appendChild(wooded);
                    forestTick.addEventListener('change', function () {
                        standAs(forest, forestTick.checked);
                        keepGround('forest', forestTick.checked);
                    });
                }
                if (bases.length) { body.appendChild(picked); }

                // A row is a label where it switches something and a plain div
                // where it only explains a colour — but it keeps the checkbox's
                // width either way, or the two kinds of row would not line up.
                var drawn = [];
                var layersKept = keptLayers();
                rows.forEach(function (row, index) {
                    var layer = layers[index];
                    var line = document.createElement(layer ? 'label' : 'div');
                    line.style.cssText = 'display:flex;align-items:center;gap:6px;margin:3px 0' +
                        (layer ? ';cursor:pointer' : '');
                    var tick = null;
                    if (layer) {
                        // What the reader left it at, and the build's own
                        // `show` where they never touched it -- which is also
                        // what takes the layers folium hands to the map but
                        // this page starts without back off it.
                        var wantRow = layersKept[row.label] === undefined
                            ? !!row.shown : layersKept[row.label] === 'on';
                        standAs(layer, wantRow);
                        tick = document.createElement('input');
                        tick.type = 'checkbox';
                        tick.style.cssText = 'flex:none;margin:0';
                        tick.checked = wantRow;
                        tick.addEventListener('change', function () {
                            standAs(layer, tick.checked);
                            keepLayer(row.label, tick.checked);
                            paint();
                        });
                        line.appendChild(tick);
                    } else {
                        var gap = document.createElement('span');
                        gap.style.cssText = 'display:inline-block;width:13px;flex:none';
                        line.appendChild(gap);
                    }
                    var swatch = document.createElement('span');
                    if (row.glyphs.length) {
                        // A pin layer's key is its pins: every glyph it drew, in
                        // its colour. Built at build time out of the same two
                        // paths the map draws, so there is no text in it.
                        swatch.style.cssText = 'display:inline-flex;gap:2px;flex:none;line-height:0';
                        swatch.innerHTML = row.glyphs.join('');
                    } else {
                        swatch.style.cssText = 'display:inline-block;width:18px;height:4px;flex:none;background:' + row.colour;
                    }
                    line.appendChild(swatch);
                    // As text. A label here routinely holds characters that
                    // would otherwise start a tag — the map's own read
                    // "Paths, approach ≤15 km" — and written as markup the
                    // whole row would vanish instead of saying so.
                    var name = document.createElement('span');
                    name.textContent = row.label;
                    line.appendChild(name);
                    body.appendChild(line);
                    drawn.push({line: line, layer: layer, tick: tick});
                });

                // A colour for something switched off is a colour for something
                // that is not on the map. The row stays — it is still the key to
                // that colour — but it says it is not speaking for the terrain.
                function paint() {
                    drawn.forEach(function (row) {
                        row.line.style.opacity = (row.layer && !map.hasLayer(row.layer)) ? '0.45' : '';
                    });
                }
                paint();

                // **What a box says is what the map holds, not what was last
                // pressed on it.** Reported from the phone: a search result in a
                // layer that was switched off switches that layer on -- which is
                // what it is for, or the row would move the map to a blank spot
                // -- and this panel went on saying *off* about names that were
                // drawn. The only way back was to tick the row on and off again.
                //
                // Leaflet fires these for every add and every remove, whoever
                // asked for it, so following them is following the map itself.
                // **Collapsed into one repaint**, because a layer group adds its
                // features one by one and each of those is an event: 12,461 of
                // them on the Lomsdal page for a single tick.
                var following = null;
                function follow() {
                    drawn.forEach(function (row) {
                        if (row.tick && row.layer) { row.tick.checked = map.hasLayer(row.layer); }
                    });
                    paint();
                }
                map.on('layeradd layerremove', function () {
                    if (following) { return; }
                    following = window.setTimeout(function () { following = null; follow(); }, 0);
                });

                function draw() {
                    header.textContent = (open ? '▾ ' : '▸ ') + title;
                    header.style.marginBottom = open ? '6px' : '0';
                    body.style.display = open ? '' : 'none';
                }
                header.addEventListener('click', function () { open = !open; draw(); });
                draw();

                box.appendChild(header);
                box.appendChild(body);
                L.DomEvent.disableClickPropagation(box);
                // The wheel is the map's, except where this box still has
                // somewhere to scroll in the direction it was turned. A list
                // this long that cannot be scrolled is as useless as a map that
                // will not zoom, and only one of the two can have any one turn.
                box.addEventListener('wheel', function (event) {
                    var room = box.scrollHeight - box.clientHeight;
                    if (room <= 0) { return; }
                    if (event.deltaY < 0 ? box.scrollTop > 0 : box.scrollTop < room - 1) {
                        event.stopPropagation();
                    }
                }, {passive: true});
                return box;
            };
            control.addTo(map);
        })();
