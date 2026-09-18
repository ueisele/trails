        (function () {
            var map = {{ this._parent.get_name() }};
            var groups = [{{ this.group_names|join(', ') }}];
            var names = {{ this.names_json }};
            //: What each group is called, for the second line of a row: a name
            //: alone does not say whether it is a lake, a trail or a hut, and
            //: the layer it was drawn in already says so.
            var labels = {{ this.labels_json }};

            //: How many rows the list draws at once. Deliberately short: a list
            //: that has to be scrolled past twenty-four on a phone is a list the
            //: query was not specific enough for, and the count says how many
            //: more there are.
            var ROWS = 24;
            //: How near two points of one name in one layer have to be to be
            //: taken for one place. Lines do not use it: the pieces of a named
            //: way are pieces of it however far apart they were drawn, and two
            //: waters of one name a valley apart are two answers.
            var SAME_M = 2000;
            //: The typed position's mark. Not the goal's green and not the
            //: position's blue: it is neither, and a reader with all three on
            //: the map at once has to be able to say which is which.
            var MARK = '#8e24aa';
            var CASING = '#ffffff';

            // A real Leaflet control rather than a box floating over the page.
            // Anchored in the map, it moves with it -- and, decisively, a wheel
            // turned over it still bubbles to the map and zooms. A panel outside
            // the container swallows the wheel instead, which reads as the map
            // having frozen the moment you finish typing.
            var input = document.createElement('input');
            input.type = 'search';
            input.placeholder = {{ this.placeholder_json }};
            input.autocomplete = 'off';
            input.className = 'trails-search-field';
            input.style.cssText = 'width:210px;font-size:12px;padding:3px 6px;border:1px solid var(--trails-rule);border-radius:3px';

            var count = document.createElement('span');
            count.style.cssText = 'flex:none;color:var(--trails-ink-4)';

            // **The field and its count are a row of their own now**, because
            // the list stands under them. The chrome lays this row out when it
            // adopts the box into its dock, and it is this row it lays out --
            // flexing the box itself would put the list beside the field.
            var line = document.createElement('div');
            line.className = 'trails-search-row';
            line.style.cssText = 'display:flex;align-items:center;gap:8px';
            line.appendChild(input);
            line.appendChild(count);

            var list = document.createElement('div');
            list.className = 'trails-search-results';
            list.style.cssText = 'display:none;margin-top:4px;max-height:46vh;overflow-y:auto;overflow-x:hidden';

            var control = L.control({position: 'topleft'});
            control.onAdd = function () {
                var box = L.DomUtil.create('div', 'trails-search');
                box.style.cssText = 'background:var(--trails-panel);padding:6px 8px;border:1px solid var(--trails-edge);' +
                    'border-radius:4px;font-family:sans-serif;font-size:12px';
                box.appendChild(line);
                box.appendChild(list);
                // Clicking and dragging inside the box must not reach the map;
                // scrolling must. Leaflet has a separate opt-out for each, and
                // only the click one is wanted here -- except over the list,
                // which scrolls itself: a wheel turned over twenty-four rows
                // means those rows, and letting it through would zoom the map
                // out from under the row being read.
                L.DomEvent.disableClickPropagation(box);
                L.DomEvent.disableScrollPropagation(list);
                // Leaflet binds its own keyboard shortcuts to the container, so
                // typing a "+" would otherwise zoom the map mid-word.
                L.DomEvent.on(input, 'keydown keypress keyup', L.DomEvent.stopPropagation);
                return box;
            };
            control.addTo(map);

            // Leaflet appends to a top corner, which would leave the box below
            // the zoom buttons. It is the first thing reached for, so it belongs
            // above them.
            var corner = control.getContainer().parentNode;
            corner.insertBefore(control.getContainer(), corner.firstChild);

            // Norwegian names are unreachable from most keyboards otherwise, so
            // "tveravegen" has to find "Tveravegen" with its ring. Combining
            // marks fall out by decomposition; the Norwegian and Sami letters
            // are letters in their own right and do not, so each is named.
            function fold(text) {
                return (text || '').toLowerCase()
                    .replace(/ø/g, 'o').replace(/æ/g, 'ae').replace(/å/g, 'a')
                    .replace(/ŋ/g, 'n').replace(/ŧ/g, 't').replace(/đ/g, 'd')
                    .normalize('NFD').replace(/[\u0300-\u036f]/g, '');
            }

            // ---- a position, typed ------------------------------------------
            // **Two sides, each of them an angle**, and the same shape twice: an
            // optional hemisphere letter in front, degrees, optionally minutes
            // and seconds behind a degree sign, an optional letter after.
            // Between the two a comma, or nothing but space.
            //
            // **Minutes need the degree sign, and that is deliberate.** `68 23`
            // with no symbol is two numbers, and nothing can say whether they
            // are a latitude and a longitude or 68 degrees and 23 minutes of one
            // of them -- so the symbol is what says which, and a side without
            // one is a plain decimal.
            //
            // The decimal point is a point. A comma is what parts the two sides
            // here -- the form this map's own picker copies -- and it cannot
            // also be a decimal separator without `68,39275, 18,68033` becoming
            // four numbers.
            //
            // **And something has to part them.** With the separator optional,
            // `68.39275` alone was read as a position: the second side has to
            // match something, so the expression backed off and took `68.3927`
            // and `5`. A comma or a space between the two, always.
            var PAIR = new RegExp('^\\s*' +
                '(?:([NSEWnsew])\\s*)?([+-]?\\d{1,3}(?:\\.\\d+)?)' +
                '(?:\\s*[°º]\\s*(?:(\\d{1,3}(?:\\.\\d+)?)\\s*[\'′]' +
                '(?:\\s*(\\d{1,3}(?:\\.\\d+)?)\\s*["″])?)?)?' +
                '\\s*([NSEWnsew])?' +
                '(?:\\s*[,;]\\s*|\\s+)' +
                '(?:([NSEWnsew])\\s*)?([+-]?\\d{1,3}(?:\\.\\d+)?)' +
                '(?:\\s*[°º]\\s*(?:(\\d{1,3}(?:\\.\\d+)?)\\s*[\'′]' +
                '(?:\\s*(\\d{1,3}(?:\\.\\d+)?)\\s*["″])?)?)?' +
                '\\s*([NSEWnsew])?\\s*$');

            //: One side of a pair, in degrees, with whichever hemisphere letter
            //: it carried. Null where it carried two, which is not an angle.
            function angleOf(before, degrees, minutes, seconds, after) {
                if (before && after) { return null; }
                var value = parseFloat(degrees);
                if (minutes !== undefined) {
                    var sum = Math.abs(value) + parseFloat(minutes) / 60 +
                        (seconds === undefined ? 0 : parseFloat(seconds) / 3600);
                    value = value < 0 ? -sum : sum;
                }
                var letter = (before || after || '').toUpperCase();
                if (letter === 'S' || letter === 'W') { value = -Math.abs(value); }
                return {value: value, letter: letter};
            }

            // **What the map itself copies, read back.** The picker at the foot
            // puts `68.39275, 18.68033` on the clipboard; this is the only thing
            // on the page that turns that string back into the place it came
            // from, which is what makes the two of them a round trip.
            //
            // **N names the latitude wherever it stands.** With letters the
            // order does not matter -- `E 18.68033, N 68.39275` is the same
            // position -- and without them the first side is the latitude,
            // because that is the order this map writes one in.
            function readCoordinate(text) {
                var found = PAIR.exec(text || '');
                if (!found) { return null; }
                var one = angleOf(found[1], found[2], found[3], found[4], found[5]);
                var other = angleOf(found[6], found[7], found[8], found[9], found[10]);
                if (!one || !other) { return null; }
                var lat = one, lon = other;
                if (one.letter || other.letter) {
                    var latish = /^[NS]$/, lonish = /^[EW]$/;
                    if (latish.test(other.letter) || lonish.test(one.letter)) { lat = other; lon = one; }
                    // Two letters naming the same axis -- `N 68, N 18` -- is not
                    // a position, and neither is one axis left unnamed while the
                    // other is named twice.
                    if (lat.letter && !latish.test(lat.letter)) { return null; }
                    if (lon.letter && !lonish.test(lon.letter)) { return null; }
                }
                if (Math.abs(lat.value) > 90 || Math.abs(lon.value) > 180) { return null; }
                return {lat: lat.value, lon: lon.value};
            }

            //: A position said the way the picker copies one, which is the form
            //: it can be typed back in as.
            function saidAt(at) {
                return at.lat.toFixed(5) + ', ' + at.lon.toFixed(5);
            }

            // ---- the mark ----------------------------------------------------
            //: The one mark a typed position leaves. One, and not one per
            //: search: two rings on the map with nothing to tell them apart is a
            //: reader wondering which of them they typed.
            var mark = null;

            //: How wide the mark's own target is, against 18 px of ring drawn
            //: in the middle of it. **The one mark on this map that takes a
            //: tap** -- the goal's ring and the position's dot take none, and
            //: are reached through the row at the foot -- so it is the one that
            //: has to be a finger wide. 36 and not 44: a transparent box over
            //: the map takes the taps meant for whatever runs under it, and 18
            //: px of halo is already more than the 12 px a line is hit by.
            //: Pinching in is how a reader says they meant the trail instead.
            var MARK_PX = 36, RING_PX = 18;

            function markIcon() {
                return '<span style="display:flex;align-items:center;justify-content:center;' +
                    'width:100%;height:100%"><span style="display:block;box-sizing:border-box;' +
                    'width:' + RING_PX + 'px;height:' + RING_PX + 'px;' +
                    'border-radius:50%;border:3px solid ' + MARK + ';background:' + CASING +
                    ';box-shadow:0 0 0 2px ' + CASING + '"></span></span>';
            }

            //: What the mark says when it is opened -- in the sheet on a narrow
            //: screen and in a popup on a wide one, because that is where every
            //: other popup on this map goes. The button is the chrome's own, so
            //: a typed position becomes a goal through the code a hut does.
            //
            //: **And it does not offer the goal itself.** The chrome adds *Set
            //: as goal* to the page of every popup that has one position, which
            //: is what this is -- offering it here too put the same button on
            //: the page twice, reported from the phone within the hour.
            function markPage(at) {
                return '<div style="font-family:sans-serif;font-size:12px;line-height:1.5">' +
                    '<div style="font-size:13px;font-weight:600">' + saidAt(at) + '</div>' +
                    '<div style="color:var(--trails-ink-3)">A position typed into the search.</div>' +
                    '<div style="padding-top:6px"><button type="button" class="trails-search-drop" ' +
                    'style="font:inherit;font-size:12px;padding:4px 10px;cursor:pointer;' +
                    'border:1px solid var(--trails-rule);border-radius:9px;' +
                    'background:var(--trails-solid);color:var(--trails-ink-2)">Take the mark away</button></div>' +
                    '</div>';
            }

            function dropMark() {
                if (!mark) { return false; }
                // Its page goes with it. The popup is the mark's own and closes
                // with it either way; on a narrow screen that page has been
                // handed to the chrome's sheet, which is a copy of the markup
                // and has to be told.
                map.closePopup();
                map.removeLayer(mark);
                mark = null;
                return true;
            }

            // Delegated on the document for the reason the chrome's own goal
            // button is: the page this writes is handed to the sheet as markup,
            // so there is no node here to hang a listener on.
            document.addEventListener('click', function (event) {
                var button = (event.target && event.target.closest)
                    ? event.target.closest('.trails-search-drop') : null;
                if (!button) { return; }
                event.stopPropagation();
                dropMark();
                if (window.trailsChrome && window.trailsChrome.closeDetail) { window.trailsChrome.closeDetail(); }
            });

            function markAt(at) {
                dropMark();
                mark = L.marker([at.lat, at.lon], {
                    icon: L.divIcon({className: 'trails-search-mark', iconSize: [MARK_PX, MARK_PX],
                                     iconAnchor: [MARK_PX / 2, MARK_PX / 2], html: markIcon()}),
                    keyboard: false, zIndexOffset: 1100
                });
                mark.bindTooltip(saidAt(at), {direction: 'right'});
                mark.bindPopup(markPage(at), {maxWidth: 320});
                mark.addTo(map);
                // **Zoomed in, never out.** A reader already at z16 typed a
                // position in order to see it where they are looking, and
                // pulling them back to z14 to show it would answer a question
                // nobody asked.
                map.setView([at.lat, at.lon], Math.max(map.getZoom(), 14));
                mark.openPopup();
                return true;
            }

            // ---- what there is to find ---------------------------------------
            var entries = [];
            groups.forEach(function (group, index) {
                group.eachLayer(function (layer) {
                    var text = layer.options.searchName || names[layer.options.className] || null;
                    entries.push({layer: layer, group: index, text: text, folded: fold(text),
                                  point: !!layer.getLatLng});
                });
            });

            //: Where an entry is, worked out once and kept. A line answers with
            //: the middle of its own extent, which is what a list can point at;
            //: taking it costs a walk over every point of the line, and a
            //: thousand of those on every keystroke is what this remembers.
            function whereOf(entry) {
                if (entry.at === undefined) {
                    var layer = entry.layer;
                    if (layer.getLatLng) { entry.at = layer.getLatLng(); }
                    else if (layer.getBounds) {
                        var bounds = layer.getBounds();
                        entry.at = bounds && bounds.isValid() ? bounds.getCenter() : null;
                    } else { entry.at = null; }
                }
                return entry.at;
            }

            //: What the list measures from: where the reader is if the page
            //: knows, and otherwise the middle of what they are looking at.
            //: Either way it is the place they are asking from.
            function asking() {
                var said = window.trailsChrome && window.trailsChrome.position
                    ? window.trailsChrome.position() : null;
                if (said) { return {at: L.latLng(said.lat, said.lon), mine: true}; }
                return {at: map.getCenter(), mine: false};
            }

            function farSaid(metres) {
                if (metres === null) { return ''; }
                if (metres < 1000) { return Math.round(metres / 10) * 10 + ' m'; }
                if (metres < 10000) { return (metres / 1000).toFixed(1) + ' km'; }
                return Math.round(metres / 1000) + ' km';
            }

            //: A name that *is* what was typed is a better answer than one that
            //: starts with it, which is better than one whose second word starts
            //: with it, which is better than one that merely holds it somewhere:
            //: "Abisko" before "Abiskojaure" before "Nedre Abiskojaure" before
            //: "Stora Abiskojaure", whatever order they were drawn in.
            function rankOf(folded, query) {
                if (folded === query) { return 0; }
                var at = folded.indexOf(query);
                if (at === 0) { return 1; }
                return /[\s\-(/]/.test(folded.charAt(at - 1)) ? 2 : 3;
            }

            // ---- the list ----------------------------------------------------
            //: What the list is showing, in the order it shows it. Read by a
            //: check through `window.trailsSearch`, and by `take`.
            var results = [];
            var query = '';

            function saidOf(found) {
                return {name: found.name, kind: found.kind, coordinate: !!found.coordinate,
                        lat: found.at ? found.at.lat : null, lon: found.at ? found.at.lng : null};
            }

            function apply() {
                query = fold(input.value.trim());
                results = [];
                var typed = readCoordinate(input.value);
                if (typed) {
                    results.push({coordinate: typed, name: saidAt(typed), kind: 'A position typed in',
                                  at: L.latLng(typed.lat, typed.lon)});
                }
                if (!query) {
                    count.textContent = '';
                    paint(0);
                    return;
                }

                var from = asking();
                var matched = [];
                entries.forEach(function (entry) {
                    if (!entry.text || entry.folded.indexOf(query) === -1) { return; }
                    var at = whereOf(entry);
                    matched.push({entry: entry, at: at, rank: rankOf(entry.folded, query),
                                  far: at ? map.distance(from.at, at) : Infinity});
                });
                matched.sort(function (one, other) {
                    return one.rank - other.rank || one.far - other.far;
                });

                // **One row per thing and not per drawing.** The sources cut a
                // named way into as many chains as they please and name every
                // one, so *Abiskojaure - Alesjaure (BD 26)* was four rows of one
                // trail; the row says how many lines carry the name and points
                // at the nearest of them, which is the piece a reader asking
                // from here would walk to.
                //
                // **A place is not a line, and is kept apart by distance
                // instead.** Two waters of one name a valley apart are two
                // answers; the same hut in two registers is one, twice.
                var kept = {};
                var over = 0;
                for (var at = 0; at < matched.length; at += 1) {
                    var found = matched[at];
                    var key = found.entry.group + ' ' + found.entry.text;
                    var seen = kept[key];
                    if (found.entry.point) {
                        var twice = false;
                        var near = seen || (kept[key] = []);
                        for (var was = 0; was < near.length; was += 1) {
                            if (found.at && near[was] && map.distance(near[was], found.at) < SAME_M) { twice = true; break; }
                        }
                        if (twice) { continue; }
                        near.push(found.at);
                    } else if (seen !== undefined) {
                        results[seen].lines += 1;
                        continue;
                    }
                    if (results.length >= ROWS) { over += 1; continue; }
                    if (!found.entry.point) { kept[key] = results.length; }
                    results.push({entry: found.entry, at: found.at, name: found.entry.text,
                                  kind: labels[found.entry.group] || '', lines: 1,
                                  far: from.mine && found.at ? found.far : null});
                }

                // **The count is of what matched and not of what is listed**, so
                // it answers the question a reader asks of a search -- is that
                // name on this map, and how often -- rather than describing the
                // list they can already see.
                count.textContent = matched.length === 1 ? '1 match' : matched.length + ' matches';
                paint(over);
            }

            function paint(more) {
                list.innerHTML = '';
                list.style.display = results.length ? 'block' : 'none';
                results.forEach(function (found, index) {
                    var row = document.createElement('button');
                    row.type = 'button';
                    row.className = 'trails-search-result';
                    row.style.cssText = 'display:block;width:100%;text-align:left;font:inherit;' +
                        'padding:6px 4px;border:0;border-top:1px solid var(--trails-rule);' +
                        'background:none;color:var(--trails-ink);cursor:pointer';
                    var said = document.createElement('div');
                    said.style.cssText = 'font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap';
                    said.textContent = found.name;
                    var under = document.createElement('div');
                    under.style.cssText = 'font-size:11px;color:var(--trails-ink-4);overflow:hidden;' +
                        'text-overflow:ellipsis;white-space:nowrap';
                    var says = [found.kind];
                    if (found.lines > 1) { says.push(found.lines + ' lines'); }
                    if (found.far !== null && found.far !== undefined) { says.push(farSaid(found.far)); }
                    under.textContent = says.join(' · ');
                    row.appendChild(said);
                    row.appendChild(under);
                    row.addEventListener('click', function (event) {
                        event.stopPropagation();
                        take(index);
                    });
                    list.appendChild(row);
                });
                if (more > 0) {
                    var rest = document.createElement('div');
                    rest.className = 'trails-search-rest';
                    rest.style.cssText = 'font-size:11px;color:var(--trails-ink-4);padding:6px 4px;' +
                        'border-top:1px solid var(--trails-rule)';
                    rest.textContent = 'and ' + more + ' more — type a little further';
                    list.appendChild(rest);
                }
            }

            // **A row is the thing itself, so taking one does what tapping it on
            // the map does** -- the highlight widening the line, its own details
            // arriving, the panel selecting it, a place opening its popup. All of
            // that is wired to the click already, and a second path through it
            // would be a second set of rules to keep in step.
            //
            // **Without the point it was tapped at**, which is the rule the
            // panel's own row of chips follows: this came from a name and not
            // from a finger, so there is no spot on the map to gather the other
            // things that tap could have meant.
            //
            // **And a name drawn on the map takes no tap at all**, here or on
            // the ground: the lettering is a label and not a feature, so its row
            // moves the map to it and changes nothing else -- which is all there
            // was ever to do with it.
            function take(index) {
                var found = results[index];
                if (!found) { return false; }
                // **On a narrow screen the list is standing on the map**, in the
                // chrome's dock, and the thing a row names would land behind it:
                // measured at 390 x 844, the dock takes the top 500 px and the
                // map's middle -- where a row puts what it chose -- is at 422.
                // The tool has answered, so it gets out of the way; the field
                // keeps what was typed, and one press has the list back.
                if (window.trailsChrome && window.trailsChrome.narrow && window.trailsChrome.narrow()) {
                    window.trailsChrome.close();
                }
                if (found.coordinate) { return markAt(found.coordinate); }
                // **A layer switched off is switched on by taking one of its
                // rows.** It holds its features whether or not it is on the map,
                // so it can be searched while it is off -- but it draws nothing,
                // and a row that moved the map to a blank spot would read as a
                // search that had found the wrong thing.
                if (!map.hasLayer(groups[found.entry.group])) { map.addLayer(groups[found.entry.group]); }
                var bounds = found.entry.layer.getBounds ? found.entry.layer.getBounds() : null;
                if (bounds && bounds.isValid() && !bounds.getNorthEast().equals(bounds.getSouthWest())) {
                    map.fitBounds(bounds, {maxZoom: 15, padding: [40, 40]});
                } else if (found.at) {
                    map.setView(found.at, Math.max(map.getZoom(), 14));
                }
                // A frame later, so that a layer switched on above has been
                // drawn: a click fired at a feature whose element does not exist
                // yet selects it and leaves nothing on the screen to show for it.
                window.setTimeout(function () {
                    found.entry.layer.fire('click', {layer: found.entry.layer});
                }, 0);
                return true;
            }

            var pending = null;
            input.addEventListener('input', function () {
                window.clearTimeout(pending);
                pending = window.setTimeout(apply, 150);
            });
            input.addEventListener('keydown', function (event) {
                // **Enter takes the first row**, which is what it already meant:
                // it used to fit the map around every match at once, and the
                // first row is that same answer narrowed to the one the ranking
                // says was wanted. A typed position is always the first row.
                if (event.key === 'Enter') { window.clearTimeout(pending); apply(); take(0); }
                if (event.key === 'Escape') { input.value = ''; window.clearTimeout(pending); apply(); }
            });

            // Read by a browser check rather than screenshotted, the way the
            // graph, the panel and the goal are already read -- and driven by
            // one too: `find` applies at once rather than after the pause a
            // typed character takes, so a check reads a list instead of sleeping
            // until one arrives.
            window.trailsSearch = {
                read: readCoordinate,
                find: function (text) {
                    input.value = text === undefined || text === null ? '' : text;
                    window.clearTimeout(pending);
                    apply();
                    return results.map(saidOf);
                },
                results: function () { return results.map(saidOf); },
                take: take,
                said: function () { return count.textContent; },
                mark: function () {
                    if (!mark) { return null; }
                    var at = mark.getLatLng();
                    return {lat: at.lat, lon: at.lng};
                },
                dropMark: dropMark
            };
        })();
