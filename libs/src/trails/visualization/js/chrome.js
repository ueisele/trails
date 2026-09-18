        (function () {
            // **The second mark**, taken before this panel builds anything. The
            // chrome is added last, so everything between it and the mark in the
            // head is the map itself: 11,302 polylines, 1,411 circle markers and
            // 867 labels, measured on this build. See `openCost`.
            if (window.trailsOpened) { window.trailsOpened.chrome = performance.now(); }
            var map = {{ this._parent.get_name() }};
            var NARROW = {{ this.narrow_px }};
            // What this map draws. `null` where nobody said, and then nothing
            // here can refuse anything.
            var DRAWN = {{ this.extent_json }};
            var CREDITS = {{ this.credits_json }};
            var UNTRANSLATED = {{ this.untranslated_json }};
            window.trailsUntranslated = UNTRANSLATED;
            // What a tile's address starts with, resolved against the page --
            // a third party's server, or our own bucket's prefix.
            var TILE_PREFIX = new URL({{ this.tile_prefix_json }}, location.href).href;
            var container = map.getContainer();

            // **The screen is measured, never remembered.** Every decision below
            // reads this instead of `map.getSize()`, which is a cache rather
            // than a measurement: Leaflet re-reads the container's
            // `clientWidth`/`clientHeight` only when `invalidateSize()` has set
            // `_sizeChanged`, and that runs from one `window` `resize` handler,
            // inside one `requestAnimationFrame` (Leaflet 1.9.4, `Map.getSize`
            // and `Map._onResize`).
            //
            // A rotation on iOS is animated, so the frame that lands during it
            // reports a box that is neither the screen being left nor the one
            // being arrived at -- and no second resize event ever comes to
            // correct it. Leaflet then holds that number for good.
            //
            // Reported after turning the phone back and forth a few times: the
            // wide menu standing on an upright screen, the profile panel cut to
            // a landscape width and hanging off the right edge, and the map
            // stopping short of the bottom with everything holding a margin
            // from an edge that was not there. One stale number, three symptoms
            // -- and the 350 ms second `place()` that was meant to catch the
            // settled screen could not, because re-asking a cache returns the
            // cache. Auto-detecting the container's size is Leaflet issue #941,
            // open since 2012 and still the caller's job; the observer below is
            // this page doing it.
            function mapRoom() {
                return {x: container.clientWidth || 0, y: container.clientHeight || 0};
            }

            function esc(text) {
                return String(text === null || text === undefined ? '' : text)
                    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
            }

            var ICONS = {
                search: '<circle cx="7.5" cy="7.5" r="5.2"/><path d="M11.4 11.4 15.5 15.5"/>',
                layers: '<path d="M9 2.3 15.7 6 9 9.7 2.3 6Z"/><path d="M2.3 9.6 9 13.3l6.7-3.7"/><path d="M2.3 12.9 9 16.6l6.7-3.7"/>',
                base: '<rect x="2.4" y="3.6" width="13.2" height="10.8" rx="1.3"/>' +
                      '<path d="M2.4 11 6.4 7.4l3.1 2.8 2.6-2.2 3.5 3"/><circle cx="6.2" cy="6.2" r="1.1"/>',
                plan: '<circle cx="4.3" cy="13.7" r="2"/><circle cx="13.7" cy="4.3" r="2"/><path d="M5.9 12.3C8.5 9.6 8.9 8 12.1 5.9"/>',
                profile: '<path d="M2.4 13.4 6 7.9l3 3.4 2.6-5.4 3.9 7.5Z"/>',
                info: '<circle cx="9" cy="9" r="6.6"/><path d="M9 8.2v4.1"/><circle cx="9" cy="5.7" r=".7" fill="currentColor" stroke="none"/>',
                burger: '<path d="M3 5.4h14M3 10h14M3 14.6h14"/>',
                undo: '<path d="M4 8.5h7.2a3.3 3.3 0 0 1 0 6.6H7"/><path d="M6.8 5.3 3.6 8.5l3.2 3.2"/>',
                chevron: '<path d="M7 4.5 12 9l-5 4.5"/>',
                close: '<path d="M4.8 4.8 13.2 13.2M13.2 4.8 4.8 13.2"/>',
                here: '<circle cx="9" cy="9" r="3.1"/><circle cx="9" cy="9" r="6.4"/>' +
                      '<path d="M9 1.4v2.2M9 14.4v2.2M1.4 9h2.2M14.4 9h2.2"/>',
                // A pin and not a second crosshair: `here` is where the reader
                // is and this is a place they point at, and two targets in one
                // column would be one drawing asked to mean two things.
                pick: '<path d="M9 16.1s5.1-4.9 5.1-8.3a5.1 5.1 0 1 0-10.2 0C3.9 11.2 9 16.1 9 16.1Z"/>' +
                      '<circle cx="9" cy="7.7" r="1.9"/>',
                // **A pennant, and deliberately neither a target nor a pin.**
                // `here` is two rings and `pick` is a pin; a goal is a third
                // thing at the same size in the same column, and the one shape
                // that reads as *somewhere to get to* without borrowing either.
                goal: '<path d="M5 16.2V2.6"/><path d="M5 3.4h8.3l-2.1 3.1 2.1 3.1H5Z"/>',
                // A disc with one half filled: the same drawing whichever way
                // the page is turned, which is right for a control that is
                // about the turning and not about either side of it.
                theme: '<circle cx="9" cy="9" r="6.4"/>' +
                       '<path d="M9 2.6a6.4 6.4 0 0 1 0 12.8Z" fill="currentColor" stroke="none"/>',
                // **Two drawings sharing a tray**, because they are one thing in
                // two conditions and not two things. The arrow is ground that
                // could come down to the device; the tick is ground that is
                // already here. A reader who has seen one recognises the other
                // without being told what changed.
                offline: '<path d="M9 2.9v7.5"/><path d="M6.1 7.6 9 10.5l2.9-2.9"/>' +
                         '<path d="M3.5 12.2v1.5a1.4 1.4 0 0 0 1.4 1.4h8.2a1.4 1.4 0 0 0 1.4-1.4v-1.5"/>',
                offlineKept: '<path d="M5.6 6.9 8.1 9.4l4.6-5"/>' +
                             '<path d="M3.5 12.2v1.5a1.4 1.4 0 0 0 1.4 1.4h8.2a1.4 1.4 0 0 0 1.4-1.4v-1.5"/>'
            };

            function icon(name, size) {
                var side = size || 18;
                return '<svg width="' + side + '" height="' + side + '" viewBox="0 0 18 18" fill="none" ' +
                    'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" ' +
                    'aria-hidden="true">' + ICONS[name] + '</svg>';
            }

            function offlineOn() {
                var said = window.trailsOffline && window.trailsOffline.state();
                return !!(said && said.on);
            }

            // **The only tool whose drawing depends on what it has done.** Every
            // other icon names a thing to open; this one also answers a question
            // the reader asks from the map -- is the ground on this device? --
            // and answering it in the row costs nothing they have to open.
            function iconFor(tool) {
                return icon(tool.key === 'offline' && offlineOn() ? 'offlineKept' : tool.key);
            }

            // What this map can do, in the order a reader meets it. `selector`
            // names a control that already exists and is adopted; the two
            // without one are built here or are a panel of their own.
            var TOOLS = [
                {key: 'search', label: 'Search', width: 300, selector: '.trails-search',
                 hint: 'A name, or a position, and the map lists what it finds.'},
                {key: 'layers', label: 'Layers', width: 344, selector: '.trails-legend',
                 hint: 'Every line and point drawn here, and what each one is.'},
                {key: 'base', label: 'Base map', width: 250, selector: '.trails-basemap',
                 hint: 'Which {{ this.provider_label }} sheet is drawn underneath.'},
                {key: 'plan', label: 'Plan a route', width: 330, selector: '.trails-plan-control',
                 hint: 'Set points, route between them, cut it into stages.'},
                {key: 'profile', label: 'Elevation profile', width: 320, selector: null,
                 hint: 'The climb of a trail you tap, or of a route you plan.'},
                // **A switch, and one the menu does not list.** It and the
                // picker are the two marks at the foot on a narrow screen --
                // which is the screen the menu is on -- so a row for them there
                // would be a second way to the same switch, one tap slower.
                // The rail keeps both, because on a wide screen there are no
                // marks and the rail is where every tool is.
                {key: 'here', label: 'Where I am', width: 300, selector: null, quick: true,
                 hint: 'Your own position on this map, while you ask for it.'},
                // **A switch and not a panel**, like the profile: there is
                // nothing to read in it, only a state the map is in. On a narrow
                // screen it is one of the two buttons at the foot, where the
                // rail is not.
                {key: 'pick', label: 'Copy a position', width: 300, selector: null, quick: true,
                 hint: 'Tap the map and its coordinates go to the clipboard.'},
                // **A switch and not a panel, for the same reason the picker is
                // one**: pressed, the next tap on the map is a goal and nothing
                // else, and it lets go of itself afterwards. What there is to do
                // with a goal once it is set -- how to read it, how to be rid of
                // it -- is at the foot, where somebody walking is already
                // looking, and not behind a tool they would have to open.
                {key: 'goal', label: 'Set a goal', width: 300, selector: null, quick: true,
                 hint: 'Tap the map and the mark points the way there.'},
                {key: 'offline', label: 'Offline', width: 330, selector: null,
                 hint: 'Keep the ground on this device, and walk with no signal.'},
                {key: 'theme', label: 'Theme', width: 300, selector: null,
                 hint: 'Light panels, dark panels, or whatever the machine says.'},
                {key: 'info', label: 'Sources', width: 360, selector: null,
                 hint: 'Who made this data, and under what licence.'}
            ];

            var byKey = {};
            TOOLS.forEach(function (tool) { byKey[tool.key] = tool; });

            // **The rail needs a column, and a phone held sideways has none.**
            // Nine tools at 46 px with a rule between them, plus the 10 px it
            // stands off each end. Reported from a phone in landscape: the last
            // tool ran off the bottom of the screen, and the way back to it was
            // a menu that was not there.
            //
            // So the wide layout is not about width alone. It is room in both
            // directions, and a screen that has one but not the other gets the
            // burger -- which opens a full-height sheet that scrolls, which is
            // the shape that fits a short screen.
            // Added up here and measured below, because arithmetic over a
            // stylesheet is a guess and this one was three pixels from being
            // wrong: reported from a phone in landscape where the rail still
            // stood, on a screen a hair taller than this sum.
            var RAIL_ROOM = TOOLS.length * 46 + (TOOLS.length - 1) + 20;

            function isNarrow(size) {
                return size.x < NARROW || size.y < RAIL_ROOM;
            }

            // **The base map picker comes out first, and the order is the
            // point.** It is built inside the legend, so adopting the legend
            // while it is still in there would carry it along and the two tools
            // would fight over one element.
            ['base', 'search', 'layers', 'plan'].forEach(function (key) {
                var tool = byKey[key];
                var found = container.querySelector(tool.selector);
                if (!found) { return; }
                // It keeps its contents and loses its frame: it is inside the
                // dock's frame now, and two borders around one list read as two
                // panels, which is the mistake the legend and the layer control
                // had already made once on this map.
                found.style.margin = '0';
                found.style.padding = '0';
                found.style.border = '0';
                found.style.borderRadius = '0';
                found.style.boxShadow = 'none';
                found.style.background = 'transparent';
                found.style.maxHeight = 'none';
                found.style.width = 'auto';
                // **And the float goes.** Leaflet puts `leaflet-control` on
                // every container it adds and floats it left, which is how a
                // corner stacks its controls — and a floated box shrinks to its
                // content. Adopted, that made the search 219 px wide inside a
                // 368 px panel however its own field was told to grow.
                found.style.setProperty('float', 'none');
                found.style.setProperty('clear', 'none');
                tool.holder = document.createElement('div');
                tool.holder.appendChild(found);
                tool.node = found;
            });

            // **The search was measured for a corner and now stands in a
            // panel.** Its 210 px were the corner's width; measured on a phone
            // they left 150 px of a 390 px screen unused beside a field 25 px
            // tall. In the dock it takes the row it is given.
            //
            // **The field's own row and not the box**, which holds the list of
            // results under it: laid out as a row, the box would put the list
            // beside the field instead of below it.
            if (byKey.search.node) {
                var field = byKey.search.node.querySelector('.trails-search-field');
                var searchRow = byKey.search.node.querySelector('.trails-search-row');
                if (field && searchRow) {
                    searchRow.style.display = 'flex';
                    searchRow.style.alignItems = 'center';
                    searchRow.style.gap = '8px';
                    field.style.width = 'auto';
                    field.style.flex = '1 1 auto';
                    field.style.minWidth = '0';
                }
            }

            // The legend's own fold handle is the dock's job now, and a panel
            // with two headings is the two-panel mistake in miniature. It is
            // unfolded first, or hiding the handle would leave a list nobody
            // can open.
            if (byKey.layers.node) {
                var legendHead = byKey.layers.node.querySelector('.trails-legend-head');
                var legendBody = byKey.layers.node.querySelector('.trails-legend-body');
                if (legendHead && legendBody) {
                    if (legendBody.style.display === 'none') { legendHead.click(); }
                    legendHead.style.display = 'none';
                }
            }

            // ---- what a finger needs, in one place ---------------------------
            // **Keyed off the pointer and not off the width.** Every other rule
            // on this page is about room, and room is a question about pixels;
            // how big a target has to be is a question about hands. A touch
            // laptop at 1400 px needs the bigger buttons and a mouse in a 390 px
            // window does not, and only `(pointer: coarse)` tells those two
            // apart.
            //
            // The query sets a **class** rather than styling directly, so a
            // browser check can ask for the coarse layout and measure it — the
            // same reason everything else here is a method rather than something
            // to read off a screenshot.
            //
            // `!important` is not decoration either: these elements carry their
            // sizes as inline styles, and inline beats a stylesheet. This is the
            // one place that has to win over them.
            var sheet = document.createElement('style');
            sheet.textContent = [
                '.trails-plan-up, .trails-plan-down { display: none; }',
                '.trails-coarse .trails-plan-up, .trails-coarse .trails-plan-down { display: inline-block; }',
                '.trails-coarse .trails-plan-grip { display: none; }',
                '.trails-coarse .trails-plan-points > div:not(.trails-plan-stage)',
                '  { min-height: 44px; gap: 8px; }',
                '.trails-coarse .trails-plan-control button { min-height: 36px; padding: 6px 12px; }',
                '.trails-coarse .trails-plan-points button',
                '  { min-width: 40px !important; min-height: 40px !important;',
                '    font-size: 17px !important; padding: 0 4px !important; }',
                '.trails-coarse .trails-legend label, .trails-coarse .trails-basemap label',
                '  { min-height: 40px; }',
                '.trails-coarse .trails-legend input, .trails-coarse .trails-basemap input',
                '  { width: 20px; height: 20px; }',
                // The row at the foot is what a thumb meets, and everything in
                // it is a box rather than a glyph: the marks are laid out at
                // 38 x 40 already, and this is the floor under the two that are
                // written as buttons beside them.
                '.trails-coarse .trails-profile-head button',
                '  { min-width: 40px; min-height: 40px; }',
                // The strip a finger drags the panel by. 7 px of bar is what a
                // mouse needs; a finger needs the strip around it.
                '.trails-profile-hold { min-height: 16px; }',
                '.trails-coarse .trails-profile-hold { min-height: 30px; padding-top: 8px; }',
                '.trails-coarse .trails-profile-undo { min-height: 40px; }',
                // The row of choices is a row of targets, and it is only there
                // when there is something to hit. 32 and not 40: it stands over
                // the row at the foot rather than in it, and every pixel it
                // takes is a pixel off the curve.
                '.trails-coarse .trails-profile-pick { min-height: 32px; }',
                // The scrollbar is furniture on a strip 26 px tall; the row
                // scrolls with a thumb and says so by clipping.
                '.trails-profile-picks::-webkit-scrollbar { display: none; }',
                // **16px is not a taste.** iOS Safari zooms the whole page when
                // a field smaller than that takes focus, which on a map is the
                // reader losing their place to type a name.
                // **Every field a reader types into, not only the search.**
                // The tour's name and a stage's name are the other two, both at
                // 12 px, and iOS Safari zooms the whole page when a field under
                // 16 takes focus. The search got this and they did not, which is
                // the same omission twice over.
                '.trails-coarse .trails-search-field,',
                '.trails-coarse .trails-plan-title,',
                '.trails-coarse .trails-plan-stage-name',
                '  { box-sizing: border-box; min-height: 40px !important; font-size: 16px !important; }'
            ].join('\n');
            document.head.appendChild(sheet);

            // **A label opened by a tap is a second heading over the ground.**
            // Leaflet opens a hover label on a *click* as well as on a hover --
            // its own rule, and on a touch device a tap is a click -- so tapping
            // a place put its name over the map and left it standing there until
            // something else was tapped, saying what the row at the foot says
            // and under the same name. The lines lost their labels outright when
            // this was reported for them; a place keeps its own, because a place
            // is named by nothing else on this page -- the docked popup is
            // headed with it -- and only the tap is taken off it.
            //
            // Closed rather than unbound, and only where the pointer is coarse:
            // under a mouse a hover label is a hover label and costs nothing.
            // Permanent ones are left alone outright -- those are the map's own
            // labelling, which is what a reader is reading the ground by.
            map.on('tooltipopen', function (event) {
                if (!event.tooltip || event.tooltip.options.permanent) { return; }
                if (!container.classList.contains('trails-coarse')) { return; }
                map.closeTooltip(event.tooltip);
            });

            var pointer = window.matchMedia ? window.matchMedia('(pointer: coarse)') : null;
            var forcedCoarse = null;
            function paintCoarse() {
                var on = forcedCoarse === null ? !!(pointer && pointer.matches) : forcedCoarse;
                if (container.classList.contains('trails-coarse') === on) { return; }
                container.classList.toggle('trails-coarse', on);
                // What a finger may hit, and how still it has to hold, is read
                // off this class too -- and Leaflet's drag threshold is merged
                // rather than read, so it is the one thing that has to be told.
                if (window.trailsReach && window.trailsReach.recount) {
                    window.trailsReach.recount();
                }
                // The profile's hint tells a reader which gestures to use, and
                // these are not the same gestures. A line telling somebody to
                // shift-drag is a line telling them to do something they cannot.
                if (window.trailsProfilePanel && window.trailsProfilePanel.repaint) {
                    window.trailsProfilePanel.repaint();
                }
            }
            if (pointer && pointer.addEventListener) { pointer.addEventListener('change', paintCoarse); }
            paintCoarse();

            var chrome = document.createElement('div');
            chrome.className = 'trails-chrome';
            // **Inset here, once, rather than in nine places.** The rail, the
            // burger, the dock, the menu and the sheet are all
            // children of this box, so holding it inside the safe area holds all
            // of them -- and the map underneath still reaches the physical edges,
            // which is what `viewport-fit=cover` is for.
            //
            // Reported from the device: with the insets live but this box still
            // at 0, a panel's heading and its close button were drawn under the
            // clock, and the button could not be tapped at all. Anything a finger
            // is meant to reach belongs below the point where the screen is its
            // full width.
            chrome.style.cssText = 'position:absolute;z-index:1100;' +
                'left:env(safe-area-inset-left);top:env(safe-area-inset-top);' +
                'right:env(safe-area-inset-right);bottom:env(safe-area-inset-bottom);' +
                'pointer-events:none;font-family:sans-serif;font-size:12px;line-height:1.4;color:var(--trails-ink)';
            // **The strips, when a panel has taken the screen.** The chrome is
            // held inside the safe area so nothing a finger wants lands under the
            // clock or the home indicator -- which on a full-screen sheet leaves
            // a band of map above it and another below, and a menu with the map
            // showing through at both ends reads as a mistake rather than as a
            // map. This sits behind the chrome and outside its inset, in the
            // panels' own colour, and only while a panel is covering the map.
            var veil = document.createElement('div');
            veil.className = 'trails-veil';
            veil.style.cssText = 'position:absolute;left:0;top:0;right:0;bottom:0;z-index:1099;' +
                'display:none;pointer-events:none;background:var(--trails-solid)';
            container.appendChild(veil);
            container.appendChild(chrome);

            function frame(cls) {
                var box = document.createElement('div');
                box.className = cls;
                box.style.cssText = 'position:absolute;display:none;flex-direction:column;overflow:hidden;' +
                    'pointer-events:auto;background:var(--trails-panel);box-shadow:0 2px 10px rgba(0,0,0,0.16)';
                L.DomEvent.disableClickPropagation(box);
                // The wheel is the map's except where this still has somewhere
                // to scroll — the bargain the legend and the plan list already
                // strike, written once more because this is the box that
                // scrolls now.
                box.addEventListener('wheel', function (event) {
                    var scroller = box.querySelector('.trails-chrome-body');
                    var room = scroller ? scroller.scrollHeight - scroller.clientHeight : 0;
                    if (room > 0 &&
                            (event.deltaY < 0 ? scroller.scrollTop > 0 : scroller.scrollTop < room - 1)) {
                        event.stopPropagation();
                        return;
                    }
                    // **The outermost panel is where a wheel stops.** Anything
                    // inside has already taken what it could use; what is left
                    // is a wheel over a panel, and a wheel over a panel that
                    // zooms the map behind it reads as the page losing hold of
                    // the pointer.
                    event.stopPropagation();
                }, {passive: true});
                chrome.appendChild(box);
                return box;
            }

            function headed(box, onClose) {
                var bar = document.createElement('div');
                bar.className = 'trails-chrome-bar';
                bar.style.cssText = 'display:flex;align-items:center;gap:8px;padding:9px 11px;' +
                    'border-bottom:1px solid var(--trails-rule);flex:none';
                var title = document.createElement('div');
                title.className = 'trails-chrome-title';
                title.style.cssText = 'flex:1;min-width:0;font-weight:600;font-size:14px;' +
                    'overflow:hidden;text-overflow:ellipsis;white-space:nowrap';
                var shut = document.createElement('button');
                shut.type = 'button';
                shut.className = 'trails-chrome-close';
                shut.setAttribute('aria-label', 'Close');
                shut.textContent = '\u00d7';
                // 40 px square. The point list's own buttons are 15 x 13 and
                // 9 x 17, which is the one kind of defect a finger cannot work
                // around by trying again.
                shut.style.cssText = 'flex:none;width:40px;height:40px;border:1px solid var(--trails-rule);' +
                    'border-radius:8px;background:var(--trails-solid);cursor:pointer;font-size:19px;line-height:1;color:var(--trails-ink-3)';
                shut.addEventListener('click', onClose);
                bar.appendChild(title);
                bar.appendChild(shut);
                var body = document.createElement('div');
                body.className = 'trails-chrome-body';
                body.style.cssText = 'flex:1;min-height:0;overflow:auto;padding:9px 11px 12px;' +
                    '-webkit-overflow-scrolling:touch';
                box.appendChild(bar);
                box.appendChild(body);
                return {title: title, body: body};
            }

            // **What is open, as three facts rather than as three styles.**
            // On a narrow screen the dock, the menu and the detail are all the
            // same full-screen sheet, so only one may be drawn — and reading
            // that off `style.display` while also writing it there is how two
            // of them end up stacked. Everything below decides; `place` draws.
            var openTool = null, menuOpen = false, detailShown = false;

            var dock = frame('trails-dock');
            var dockParts = headed(dock, function () { closeDock(); });
            var menu = frame('trails-menu');
            var menuParts = headed(menu, function () { closeMenu(); });
            var sheet = frame('trails-detail');
            var sheetParts = headed(sheet, function () { closeSheet(); });

            // ---- the sources panel, built from what the export was handed ----
            var sourcesHolder = document.createElement('div');
            (function () {
                var seen = {}, out = '';
                Object.keys(CREDITS).forEach(function (key) {
                    (CREDITS[key] || []).forEach(function (credit) {
                        if (seen[credit.name]) { return; }
                        seen[credit.name] = true;
                        out += '<div style="padding:8px 0;border-top:1px solid var(--trails-rule)">' +
                            '<div style="font-weight:600">' + esc(credit.name) + '</div>' +
                            '<div style="color:var(--trails-ink-3)">' + esc(credit.licence) +
                            (credit.version ? ' \u00b7 ' + esc(credit.version) : '') + '</div>' +
                            (credit.note ? '<div style="color:var(--trails-ink-5);font-size:11px;margin-top:2px">' +
                                esc(credit.note) + '</div>' : '') +
                            (credit.url ? '<div style="margin-top:3px"><a href="' + esc(credit.url) +
                                '" target="_blank" rel="noopener noreferrer">' +
                                esc(credit.attribution || credit.url) + '</a></div>' : '') +
                            '</div>';
                    });
                });
                sourcesHolder.innerHTML = out || '<p style="color:var(--trails-ink-5)">No sources were handed to this page.</p>';
            })();
            // **What this page cost to open, in the panel about the page.**
            // An installed app on a phone reported ten to twenty seconds where
            // every check in this project measures 1.8 s -- and every one of
            // those checks is Firefox on Linux, so the gap is exactly the part
            // that cannot be measured from here. The page therefore keeps its
            // own account and the reader can read it out on the device.
            //
            // **`worker` is the number this was built for.** With offline mode on
            // the document comes out of the Cache API, where it is held at its
            // decoded 15.7 MB rather than the 5.2 MB brotli the network sends --
            // beside a store holding gigabytes of tiles. If that is where the
            // seconds are, this line says so; if it is the parse, it says that
            // instead. Either way it stops being a guess.
            function openCost() {
                var nav = (performance.getEntriesByType('navigation') || [])[0];
                if (!nav) { return null; }
                var marks = window.trailsOpened || {};
                var graph = window.trailsGraph || {};
                var since = function (a, b) {
                    return (a && b && a > b) ? Math.round(a - b) : null;
                };
                // **The subresources, because that is where the answer was.**
                // Read off a phone: fetched 326 ms, map built 282 ms, graph
                // 168 ms -- and `Opened in 22.3 s`. Nothing the page does
                // accounts for twenty-one of those seconds, and `loadEventEnd`
                // does not fire until every image has settled. With the switch
                // on each tile is a `cache.match` against a store holding tens
                // of thousands of entries and several gigabytes, which is
                // exactly why it only happens with tiles kept.
                var tiles = [], others = [], worst = 0, spent = 0;
                (performance.getEntriesByType('resource') || []).forEach(function (each) {
                    if (each.name.indexOf(TILE_PREFIX) !== 0) { others.push(each); return; }
                    tiles.push(each);
                    spent += each.duration || 0;
                    if ((each.duration || 0) > worst) { worst = each.duration; }
                });
                return {
                    total: Math.round(nav.loadEventEnd || nav.domComplete || 0),
                    tiles: tiles.length,
                    tilesWorst: Math.round(worst),
                    tilesSpent: Math.round(spent),
                    others: others.length,
                    // Kept raw beside the differences above, because a figure
                    // this page cannot subtract is still one somebody can read.
                    interactive: Math.round(nav.domInteractive || 0),
                    contentLoaded: Math.round(nav.domContentLoadedEventEnd || 0),
                    loadStart: Math.round(nav.loadEventStart || 0),
                    // How long the worker held the request before answering: the
                    // cost of reading the document out of the Cache API.
                    worker: nav.workerStart ? since(nav.responseStart, nav.workerStart) : null,
                    fetch: since(nav.responseEnd, nav.requestStart),
                    // The head mark to the chrome mark is the map being built.
                    build: since(marks.chrome, marks.head),
                    parse: since(nav.domInteractive, nav.responseEnd),
                    after: since(nav.domComplete, nav.domInteractive),
                    graph: Math.round((graph.inflateMs || 0) + (graph.decodeMs || 0)) || null,
                    bytes: nav.decodedBodySize || 0,
                    wire: nav.transferSize || 0
                };
            }

            // **What iOS keeps for itself, asked of the browser.** The head
            // says `apple-mobile-web-app-status-bar-style: black-translucent`,
            // which draws the app edge to edge -- and the viewport meta says
            // nothing about `viewport-fit`, without which `env(safe-area-inset-*)`
            // reads zero. So the page asks for the whole screen and is never told
            // which part of it is covered, and everything at the bottom edge sits
            // under the home indicator.
            //
            // Which of the two ways out is right depends on numbers no check here
            // can produce: on Linux the insets are always zero and `standalone`
            // is always undefined. So the page reports what its own device says.
            function inset(side) {
                var probe = document.createElement('div');
                probe.style.cssText = 'position:absolute;visibility:hidden;' +
                    'padding-' + side + ':env(safe-area-inset-' + side + ')';
                document.body.appendChild(probe);
                var got = getComputedStyle(probe)['padding' + side.charAt(0).toUpperCase() + side.slice(1)];
                probe.remove();
                return got || '0px';
            }

            function seconds(ms) {
                // **Nought means not yet, and a nought reads as an answer.** The
                // reader opened `Sources` before `load` had fired and the line
                // said *opened in 0 ms* about a page that was still finishing --
                // the second time that figure has lied by rounding an absence to
                // a number.
                if (!ms) { return '—'; }
                return ms >= 1000 ? (ms / 1000).toFixed(1) + ' s' : Math.round(ms) + ' ms';
            }

            // **Filled when the panel is opened, not when it is built.** The
            // chrome is built before `load` has fired, so every figure that ends
            // at `loadEventEnd` was zero -- the line said *opened in 0 ms* about
            // a page that had taken 1.7 seconds. Written on the way in instead,
            // where the reader is about to look at it.
            var costLine = document.createElement('p');
            costLine.className = 'trails-open-cost';
            costLine.style.cssText = 'margin:0 0 8px;color:var(--trails-ink-5);font-size:11px;line-height:1.5';

            var tileLine = document.createElement('p');
            tileLine.className = 'trails-open-tiles';
            tileLine.style.cssText = 'margin:0 0 8px;color:var(--trails-ink-5);font-size:11px;line-height:1.5';

            function sayOpenCost() {
                var cost = openCost();
                if (!cost) { return; }
                var parts = ['Opened in ' + seconds(cost.total)];
                if (cost.bytes) { parts.push(Math.round(cost.bytes / 1e5) / 10 + ' MB document'); }
                // Both, and dashes where the browser will not say. `worker` is
                // the one this line was built for and the one Safari leaves
                // empty -- said out loud, so its absence is a reading rather
                // than a gap nobody notices.
                parts.push('worker ' + seconds(cost.worker));
                parts.push('fetched ' + seconds(cost.fetch));
                // **A dash rather than nothing, when a browser will not say.**
                // Safari fills neither `workerStart` nor `decodedBodySize` for a
                // document a worker answered, and this quietly left both out --
                // so a line read off a phone was missing the two figures it was
                // built to carry, and looked complete. `parsed` went the same
                // way, which was the one that mattered.
                parts.push('parsed ' + seconds(cost.parse));
                parts.push('map built ' + seconds(cost.build));
                parts.push('graph ' + seconds(cost.graph));
                costLine.textContent = parts.join(' · ') + '.';
                // **The tiles on their own line**, because the answer was there
                // and not in anything above it: `loadEventEnd` waits for every
                // image, and with the switch on every image is a lookup in a
                // cache holding gigabytes.
                var said = cost.tiles
                    ? cost.tiles + ' tiles, ' + seconds(cost.tilesSpent) + ' in all, worst ' +
                      seconds(cost.tilesWorst) + ' · ' + cost.others + ' other requests'
                    : 'No tiles were asked for';
                // **The browser's own milestones, raw.** Every figure on the
                // line above is a difference, and a difference disappears when
                // either end is missing -- which is how a line read off a phone
                // came back without the two numbers it was built to carry. These
                // are what the browser said, subtracted from nothing.
                said += ' · DOM ' + seconds(cost.interactive) +
                    ', content ' + seconds(cost.contentLoaded) +
                    ', load ' + seconds(cost.loadStart) + '.';
                tileLine.textContent = said;
                // **What the worker spent, from inside the worker.** `worker` on
                // the line above is one number covering everything `pageFor`
                // does; these three say which part of it. Written to a cache
                // rather than posted, because a navigation is answered before
                // any page is listening -- so it is read here, after the fact.
                if (!window.trailsOffline || !window.trailsOffline.dbRead) { return; }
                window.trailsOffline.dbRead('flags', 'timing').then(function (spent) {
                    if (spent) {
                        tileLine.textContent = said + ' Worker: store open ' + seconds(spent.open) +
                            ', page found ' + seconds(spent.match) + ', switch read ' + seconds(spent.flag) + '.';
                    }
                    // **Where the tiles came from, which the screen cannot say.**
                    // A tile out of the database, one out of the old cache and
                    // one off the network all simply appear; a blank simply does
                    // not, and shipped without this the ground stopped appearing
                    // with no way to ask where it had gone.
                    return window.trailsOffline.dbRead('flags', 'tiles-said');
                }).then(function (told) {
                    if (!told) { return; }
                    tileLine.textContent += ' Tiles: ' + told.db + ' from the store, ' +
                        told.seen + ' seen before, ' + told.legacy + ' from the old cache, ' +
                        told.net + ' fetched, ' + told.blank + ' blank' +
                        (told.why ? ' · ' + told.why : '') + '.';
                }).then(function () {
                    tileLine.textContent += ' Screen: safe area top ' + inset('top') +
                        ', bottom ' + inset('bottom') +
                        ' · standalone ' + (navigator.standalone === undefined
                            ? '—' : String(navigator.standalone)) + '.';
                }).catch(function () { return; });
            }

            window.trailsOpened = window.trailsOpened || {};
            window.trailsOpened.cost = openCost;

            // **How old this copy is, above the credits.** `Sources` is the
            // panel about the page rather than about the ground, and when this
            // map was built is exactly that -- it already says who made the
            // data and under what licence.
            //
            // It is also the only place a reader who never turns offline mode on
            // can find it. A map goes stale because an installed app resumes
            // instead of navigating, which is true whatever the switch says, and
            // until this the one cure sat behind a feature that reader does not
            // use. The row comes from the offline panel so there is one set of
            // facts and not two.
            if (window.trailsOffline && window.trailsOffline.freshness) {
                sourcesHolder.insertBefore(window.trailsOffline.freshness(), sourcesHolder.firstChild);
            }
            sourcesHolder.insertBefore(tileLine, sourcesHolder.firstChild);
            sourcesHolder.insertBefore(costLine, sourcesHolder.firstChild);
            byKey.info.holder = sourcesHolder;

            // ---- what is kept on this device ----------------------------------
            // Built by its own element, which owns the tile arithmetic and the
            // worker's ear; the dock only finds it somewhere to be.
            byKey.offline.holder = window.trailsOffline ? window.trailsOffline.holder : null;

            // **The panel holds no state, and that is the whole of its design.**
            // `window.trailsTheme` in the head owns the choice, because the
            // stamp has to be on the root before the first paint and this script
            // runs long after it. This draws three buttons and reads back what
            // it is told, so there is no second copy of the answer to disagree
            // with the first.
            var themeHolder = document.createElement('div');
            themeHolder.className = 'trails-theme';
            var themeSays = document.createElement('p');
            themeSays.style.cssText = 'margin:0 0 10px;color:var(--trails-ink-3)';
            themeSays.textContent = 'The panels, the menu and this text. The map itself is a ' +
                'photograph of the ground and stays as it is — a darkened slope would be a wrong ' +
                'slope, not a dark one.';
            var themeRow = document.createElement('div');
            themeRow.className = 'trails-theme-choices';
            themeRow.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;margin:0 0 10px';
            var themeState = document.createElement('p');
            themeState.className = 'trails-theme-state';
            themeState.style.cssText = 'margin:0;color:var(--trails-ink-5);font-size:11.5px';
            var THEMES = [
                {key: 'auto', label: 'Auto', hint: 'Follow the machine, and turn when it turns.'},
                {key: 'light', label: 'Light', hint: 'Light panels, whatever the machine says.'},
                {key: 'dark', label: 'Dark', hint: 'Dark panels, whatever the machine says.'}
            ];
            var themeButtons = {};
            THEMES.forEach(function (each) {
                var pick = document.createElement('button');
                pick.type = 'button';
                pick.className = 'trails-theme-choice';
                pick.setAttribute('data-theme-choice', each.key);
                pick.textContent = each.label;
                pick.title = each.hint;
                // 40 px, because this is a target for a thumb on a dark hillside
                // and the rest of the coarse layout is already there.
                pick.style.cssText = 'font:inherit;font-size:13px;font-weight:600;padding:9px 14px;' +
                    'min-height:40px;border-radius:7px;cursor:pointer';
                pick.addEventListener('click', function () {
                    if (window.trailsTheme) { window.trailsTheme.set(each.key); }
                    // Painted here as well as on the event, so a reader who has
                    // storage denied and a reader who picks what is already
                    // picked both see the press land.
                    paintTheme();
                });
                themeButtons[each.key] = pick;
                themeRow.appendChild(pick);
            });
            themeHolder.appendChild(themeSays);
            themeHolder.appendChild(themeRow);
            themeHolder.appendChild(themeState);
            byKey.theme.holder = themeHolder;

            function paintTheme() {
                var api = window.trailsTheme;
                var chosen = api ? api.choice() : 'auto';
                THEMES.forEach(function (each) {
                    var pick = themeButtons[each.key];
                    var lit = each.key === chosen;
                    pick.style.border = '1px solid ' + (lit ? 'var(--trails-strong)' : 'var(--trails-rule)');
                    pick.style.background = lit ? 'var(--trails-strong)' : 'transparent';
                    pick.style.color = lit ? 'var(--trails-on-strong)' : 'var(--trails-ink-2)';
                    pick.setAttribute('aria-pressed', String(lit));
                });
                if (!api) {
                    themeState.textContent = 'This page was built without the theme, so there is ' +
                        'nothing here to turn.';
                    return;
                }
                // **Auto says which way it currently falls.** *Auto* on its own
                // is the one answer a reader cannot check against the screen:
                // light and dark are visible, and following-the-machine looks
                // exactly like whichever one it landed on.
                themeState.textContent = chosen === 'auto'
                    ? 'Following this machine, which is asking for ' + (api.dark() ? 'dark' : 'light') +
                      ' just now.'
                    : 'Chosen here, and kept on this device until you change it.';
            }

            // The machine can turn under an open panel, and on auto that moves
            // the line above without anybody touching a button.
            document.addEventListener('trails:theme', function () { paintTheme(); });
            paintTheme();

            // **Redrawn where it stands rather than rebuilt.** The switch is
            // thrown inside the offline panel, which on a narrow screen is
            // covering the menu at the time -- so the row behind it has to be
            // right when the reader closes the panel, and the rail beside it has
            // to be right at once.
            function paintOfflineIcon() {
                var mark = iconFor(byKey.offline);
                if (railButtons.offline) { railButtons.offline.innerHTML = mark; }
                var row = menuParts.body.querySelector('[data-tool="offline"] span');
                if (row) { row.innerHTML = mark; }
            }

            document.addEventListener('trails:offline', function () {
                paintOfflineIcon();
                paintRail();
            });

            // **The one tool that used to be dead half the time.** It was
            // disabled while nothing was selected — greyed, with no reason
            // given, and on the rail with no text at all — so a reader meeting
            // it for the first time met a control that would not answer and
            // could not say why. It is never disabled now: with nothing to draw
            // it opens and says what it is and what it needs, which is what
            // every other tool here does.
            var profileHolder = document.createElement('div');
            profileHolder.className = 'trails-profile-empty';
            profileHolder.innerHTML =
                '<p style="margin:0 0 8px">The height of what you pick, drawn along the ' +
                'foot of the map.</p>' +
                '<p style="margin:0;color:var(--trails-ink-3)">Tap a path or a route on the map and its ' +
                'climb appears here — or plan a route with <b>Plan a route</b> and this ' +
                'draws the walk.</p>';
            byKey.profile.holder = profileHolder;

            // ---- where the reader is ------------------------------------------
            // **Only while it is asked for.** A map that starts watching a
            // reader because it was opened is a map that has decided something
            // for them; this asks the browser for a position when the button is
            // pressed and stops the moment it is pressed again, when the page is
            // hidden, or when the browser refuses to share at all. **A fix that
            // merely fails to arrive does not stop it** -- `failedHere` says
            // why, and it is the defect this section was rewritten for.
            //
            // **The accuracy is drawn.** A fix is a claim with a radius on it —
            // 8 m under an open sky, 300 m in a valley — and a page that draws it
            // as a dot has thrown away the half that matters on a mountain. The
            // circle is what the browser reports, at the scale the map is drawn
            // at, which is the only honest way to show it on a map whose whole
            // argument is metres per pixel.
            //
            // Blue, and not a themed colour: the tiles stay light in both sets,
            // so this is drawn on the same ground either way.
            var HERE_BLUE = '#1565c0';
            // **Red, and it is the only red on this map that is not a gradient
            // band.** Which way the reader is *facing* is a different question
            // from which way they are *going*, and two blues at one position
            // would be one answer in two sizes: the cone is blue, filled and
            // wide -- a movement with slack in it -- and this is red, thin and
            // hard-edged, which is what an instrument looks like.
            var HERE_FACING = '#d32f2f';
            // **The same red again, for a position the device can no longer
            // confirm.** A second red would be a second thing to learn, and
            // these two say one thing between them: *the instrument is
            // talking*. The rim is the compass reporting where the phone
            // points; this is the phone admitting it has stopped knowing where
            // it is. They are told apart by shape, which is how everything else
            // at this position is told apart -- thin arcs around the dot,
            // against the dot itself and the ring around it.
            var HERE_LOST = HERE_FACING;
            //: The namespace the marks are drawn in. The profile panel has its
            //: own copy of this line for its own arrow; a shared one would have
            //: to live above both closures, and one constant is not worth a
            //: third place to look.
            var HERE_SVG = 'http://www.w3.org/2000/svg';
            // **Green, because it is the one mark at this position that is not
            // about the reader.** The cone says how they are going and the rim
            // which way they are facing; this one says where to *go*, which is
            // a different kind of statement and gets a different colour. It is
            // also the only green this map draws: the ways are brown and slate,
            // the route is black, the position is blue and the compass red.
            var HERE_GOAL = '#00a152';
            //: How far the wedge reaches on the screen, and the head and its
            //: figure sit just past that. Pixels rather than metres, like the
            //: cone: a goal four kilometres off would otherwise have no mark on
            //: the screen at all, and the question it answers is which way.
            var AIM_REACH = 72;
            //: How wide the wedge may open before it stops being a direction.
            //: Past this it says no more than *look around you*, and a mark
            //: that points confidently into a fan a reader could walk anywhere
            //: inside is worse than no mark at all.
            var AIM_WIDEST = 120;
            //: And how narrow it may be drawn. Under a couple of degrees a
            //: wedge is a hairline, which the eye reads as a line rather than
            //: as a direction with a width; the head is what points, and this
            //: keeps the fan behind it visible while it is honestly tiny.
            var AIM_NARROWEST = 3;
            //: How far a fix has to have moved before the bearing between it and
            //: the one before is worth believing. Under this the two are one
            //: place seen twice, and a bearing off them spins with the noise.
            var MOVED_M = 10;
            //: How long a fix kept for its accuracy may go on standing for the
            //: reader. While the sky thins under somebody who has not moved,
            //: every fix after it says the same place and says it vaguer -- but
            //: a reader walking slowly under a sky that is getting worse would
            //: otherwise be shown where they were a quarter of an hour ago.
            var HOLD_MS = 90000;
            //: What the watch asks the browser for. Written once because it is
            //: asked twice: on the press, and on every retry while nothing is
            //: arriving.
            var HERE_WANTS = {enableHighAccuracy: true, maximumAge: 10000, timeout: 20000};
            //: How often a drought asks again, and how often the age under the
            //: dot is redrawn -- one timer for both, because they are one
            //: thing: the page doing what the reader was doing by hand.
            var LOST_AGAIN_MS = 30000;
            //: The fix on the screen, which is not always the last one that
            //: arrived: where it was, how wide its claim was, and when it was
            //: made.
            var hereKept = null;
            var hereWatch = null, hereDot = null, hereRing = null, hereFixes = 0;
            //: While the watch is on and nothing is arriving: which refusal it
            //: was, what there is to say about it, and when the drought began.
            //: `null` while fixes are coming, and everything red on this mark
            //: reads it.
            var hereLost = null, hereAgeTimer = null;
            //: The last bearing worth drawing, whether the device reported it or
            //: it was worked out here, and where it was worked out from.
            var hereBearing = null, hereFrom = null, hereMoving = false;
            //: Which way the device is pointing, while the compass says.
            var hereFacing = null, hereCompass = null, herePainting = false;
            var hereMarks = null, hereCone = null, hereHalo = null, hereAt = null;
            //: Where to walk, as it was worked out on the last fix: which way,
            //: how much of that direction the fix leaves open either side, what
            //: is being aimed at and how far off it is.
            var hereGoal = null;
            var hereAim = null, hereAimEdge = null, hereAimHead = null;
            var hereAimSaid = null, hereAimNamed = null, hereAimMs = null;
            // **What aiming cost in work rather than in time.** The
            // milliseconds beside these say as much about the machine as about
            // the page; these two are the page's own and every machine agrees
            // on them. `walked` is how many segments the passes over the route
            // touched, `sampled` how many segment-questions the ring's dozen
            // directions asked -- and the claim worth holding is that the
            // second is over a handful that survived the first, not over the
            // route again.
            var hereAimWalked = 0, hereAimSampled = 0;
            //: How old the dot is, said under it while no fix confirms it.
            var hereLostSaid = null;
            // **Where the reader is is the last thing drawn on this map.**
            // Reported: with a plan loaded the dot sat *under* the route --
            // because it was in the overlay pane at 400 and the route has a pane
            // of its own at 460, as do the profile's own marks at 450 and 470.
            // A position hidden under a line is not a position: it is the one
            // mark here that answers a question nothing else on the map can, and
            // a reader looks for it exactly when the map is busiest.
            //
            // Over the marker pane too, at 600. A place under the dot is still
            // where it was and can be read by moving a finger; the dot has
            // nowhere else to be. Below the tooltips and popups at 650 and
            // above, which are answers a reader asked for by touching something.
            var HERE_MARKS_Z = 610;
            var HERE_Z = 620;

            // **The bearing from one fix to the next**, which is the whole of
            // 2b: a phone reports a course over the ground only while it is
            // moving, and on the devices that do not report one at all this is
            // the only way to say which way somebody is walking.
            // The pane the dot and the ring are drawn into, made on the first
            // fix. Not `leaflet-zoom-hide`: these are Leaflet's own vectors and
            // its renderer animates them with the map, which is what keeps the
            // dot on its ground through a zoom.
            function herePane() {
                if (!map.getPane('trailsHere')) {
                    var pane = map.createPane('trailsHere');
                    pane.style.zIndex = HERE_Z;
                    // Nothing here is ever a click target -- both layers are
                    // built `interactive: false` -- and a pane over the whole
                    // map that took clicks would take them from every trail
                    // under it.
                    pane.style.pointerEvents = 'none';
                }
                return 'trailsHere';
            }

            function bearingBetween(from, to) {
                var lat1 = from.lat * Math.PI / 180, lat2 = to.lat * Math.PI / 180;
                var apart = (to.lng - from.lng) * Math.PI / 180;
                var y = Math.sin(apart) * Math.cos(lat2);
                var x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(apart);
                return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
            }

            //: Two bearings subtracted and brought back into -180..180, so a
            //: pair either side of north is four degrees apart and not 356.
            function swung(angle) { return ((angle % 360) + 540) % 360 - 180; }

            //: How far a point is, flat, in the same metre the rest of this
            //: page uses. Over the few hundred metres any of this measures, a
            //: degree of longitude is a constant and the error is under a
            //: centimetre.
            function awayFrom(at, cosine, lat, lon) {
                var dx = (lon - at.lng) * cosine, dy = lat - at.lat;
                return Math.sqrt(dx * dx + dy * dy) * 111320;
            }

            // **The nearest point of one segment, and how long the segment is.**
            // Plan mode has its own copy of this arithmetic, for putting a
            // waypoint into a leg; lifting one of them out would need a third
            // home for a function whose two callers have nothing else in common
            // -- and this one answers two things that one does not, because
            // *how far along* is what says which goal lies ahead.
            function nearOnSegment(at, cosine, aLat, aLon, bLat, bLon) {
                var ax = (aLon - at.lng) * cosine, ay = aLat - at.lat;
                var dx = (bLon - aLon) * cosine, dy = bLat - aLat;
                var span = dx * dx + dy * dy;
                var t = span > 0 ? -(ax * dx + ay * dy) / span : 0;
                t = t < 0 ? 0 : (t > 1 ? 1 : t);
                var cx = ax + t * dx, cy = ay + t * dy;
                return {away: Math.sqrt(cx * cx + cy * cy) * 111320,
                        lat: aLat + t * (bLat - aLat), lon: aLon + t * (bLon - aLon),
                        along: t * Math.sqrt(span) * 111320,
                        length: Math.sqrt(span) * 111320};
            }

            //: The nearest point among a handful of segments already known to be
            //: worth looking at, which is what makes asking the question a
            //: dozen times cheap.
            function nearestAmong(from, cosine, segments) {
                var found = null;
                for (var i = 0; i < segments.length; i += 1) {
                    var seg = segments[i];
                    var near = nearOnSegment(from, cosine, seg[0], seg[1], seg[2], seg[3]);
                    if (!found || near.away < found.away) { found = near; }
                }
                return found;
            }

            //: How far along the route the head looks when the reader is on it.
            //: Under this the bearing shivers with the fix; much over it and the
            //: head cuts the corners the route was drawn to go round. Three
            //: times the circle wherever that is more, so a vague fix looks
            //: further ahead and gets a steadier answer for it.
            var AHEAD_M = 60;
            var AHEAD_SPREADS = 3;

            //: The point a given distance along the route, walked from its
            //: start. One more pass over the segments, which is what the whole
            //: of this costs anyway.
            function alongAt(target, cosine, want) {
                var run = 0, found = null;
                target.segments(function (aLat, aLon, bLat, bLon) {
                    if (found) { return; }
                    var length = awayFrom({lat: aLat, lng: aLon}, cosine, bLat, bLon);
                    if (run + length >= want) {
                        var t = length > 0 ? (want - run) / length : 0;
                        found = {lat: aLat + t * (bLat - aLat), lon: aLon + t * (bLon - aLon)};
                    }
                    run += length;
                });
                return found;
            }

            //: How many places on the rim of the accuracy circle are asked.
            //: Every 30 degrees: the answer turns slowly with the reader's
            //: position and the extremes are on the rim, which is where the
            //: nearest point has moved furthest.
            var AIM_SAMPLES = 12;

            // **Which way the next goal is, and how much of that direction the
            // fix can actually support.** The wedge is not decoration around an
            // arrow: it is the answer, and the arrow is the middle of it.
            //
            // **Off the route it is asked and not derived.** The reader could be
            // anywhere in the circle the map already draws, so the question is
            // put from a dozen places on its rim: *standing there, which way
            // would I be sent?* The wedge is what those answers span.
            //
            // Which is not the same as the bound this started as -- every part
            // of the route within `d + 2r`, since that is provably where the
            // nearest point of any position in the circle lies. That bound is
            // true and far too generous: measured 62 m off a straight leg with
            // a 22 m circle, it made 121 degrees of a fan that is really 0. A
            // straight line sends every position in the circle off at the same
            // perpendicular, and it should say so. What opens the wedge is the
            // route bending, ending or doubling back -- the cases where which
            // way to walk really does depend on where in the circle you are.
            //
            // On the route, the goal is the next place along instead, and that
            // is a fixed point: the whole of the width is then `asin(r / d)`,
            // which is exact and needs no asking.
            function aimAlong(at, spread, target) {
                var cosine = Math.cos(at.lat * Math.PI / 180);
                hereAimWalked = 0;
                hereAimSampled = 0;
                // **A point the reader set needs no asking.** It does not move,
                // so the whole of the width is their own circle turning a
                // bearing to a fixed thing -- `asin(r / d)`, exactly, either
                // side. The dozen questions below exist because a *route* moves
                // the answer about; a goal does not.
                if (target.point) {
                    var straight = awayFrom(at, cosine, target.point.lat, target.point.lon);
                    // Inside the circle there is no direction to give: the
                    // reader may be standing on it. 180 either way is 360, which
                    // is wider than anything is drawn at, and that is the mark
                    // going quiet rather than a special case for arriving.
                    var half = straight > spread
                        ? Math.asin(Math.min(1, spread / straight)) * 180 / Math.PI : 180;
                    return {to: bearingBetween(at, {lat: target.point.lat, lng: target.point.lon}),
                            left: -half, right: half, away: straight, on: straight <= spread,
                            at: {lat: target.point.lat, lon: target.point.lon},
                            goal: target.point, name: target.name};
                }
                var best = null, run = 0, whole = 0, atLeg = null, spans = {};
                target.segments(function (aLat, aLon, bLat, bLon, which) {
                    hereAimWalked += 1;
                    // The legs arrive one at a time and in order, so the run
                    // resets where one hands over to the next and `spans` ends
                    // up holding how long each of them was. `whole` does not
                    // reset: a look-ahead is measured along the route and not
                    // along whichever leg it happens to fall in.
                    if (which !== atLeg) { atLeg = which; run = 0; }
                    var near = nearOnSegment(at, cosine, aLat, aLon, bLat, bLon);
                    if (!best || near.away < best.away) {
                        best = {away: near.away, lat: near.lat, lon: near.lon, leg: which,
                                run: run + near.along, along: whole + near.along,
                                way: bearingBetween({lat: aLat, lng: aLon}, {lat: bLat, lng: bLon})};
                    }
                    run += near.length;
                    whole += near.length;
                    spans[which] = run;
                });
                if (!best) { return null; }
                var to = bearingBetween(at, {lat: best.lat, lng: best.lon});
                var found = {to: to, left: 0, right: 0, away: best.away, on: best.away <= spread,
                             at: {lat: best.lat, lon: best.lon}, goal: null, name: target.name};
                if (!found.on) {
                    // The bound is still worth keeping, for what it is good
                    // for: the nearest point of *any* position in the circle is
                    // within `d + 2r` of the fix, so everything outside that can
                    // be dropped once and the dozen questions below are then
                    // asked of a handful of segments instead of the whole route.
                    var reach = best.away + 2 * spread;
                    var could = [];
                    target.segments(function (aLat, aLon, bLat, bLon) {
                        hereAimWalked += 1;
                        if (nearOnSegment(at, cosine, aLat, aLon, bLat, bLon).away <= reach) {
                            could.push([aLat, aLon, bLat, bLon]);
                        }
                    });
                    var north = spread / 111320, east = spread / (111320 * cosine);
                    hereAimSampled = could.length * AIM_SAMPLES;
                    for (var s = 0; s < AIM_SAMPLES; s += 1) {
                        var turn = s * 2 * Math.PI / AIM_SAMPLES;
                        // Where the reader might really be, and the bearing from
                        // *there* -- not from the fix. Which way to walk is a
                        // question asked at the place the walking starts.
                        var maybe = {lat: at.lat + north * Math.cos(turn),
                                     lng: at.lng + east * Math.sin(turn)};
                        var sent = nearestAmong(maybe, cosine, could);
                        if (!sent) { continue; }
                        var off = swung(bearingBetween(maybe, {lat: sent.lat, lng: sent.lon}) - to);
                        if (off < found.left) { found.left = off; }
                        if (off > found.right) { found.right = off; }
                    }
                    return found;
                }
                // On the route, as far as the fix can say. Which way *along* it
                // to look is the direction the reader is going, read off the
                // same bearing the cone is drawn from -- and without one there
                // is nothing for a goal to be ahead of, so the mark says so by
                // not being drawn.
                if (!target.goal) { return found; }
                // **Some routes have only one way along them.** A way to a goal
                // runs from where the reader was to the thing they asked for;
                // *ahead* is toward the goal and cannot be anything else, so it
                // is not asked. A planned route has waypoints at both ends of
                // every leg and can be walked either way, and there the
                // direction of travel is the only thing that says which.
                var forward = target.oneWay ? 1
                    : (hereBearing === null ? 0
                       : (Math.abs(swung(hereBearing - best.way)) < 90 ? 1 : -1));
                if (!forward) { return found; }
                var leg = best.leg;
                var remains = forward > 0 ? (spans[leg] - best.run) : best.run;
                var goal = target.goal(leg, forward);
                // **A goal under the reader is not one.** It is the place they
                // are standing at, the bearing to it spins with the noise, and
                // a reader walking through a waypoint means the one after it.
                while (goal && remains <= spread) {
                    leg += forward;
                    if (spans[leg] === undefined) { goal = null; break; }
                    remains += spans[leg];
                    goal = target.goal(leg, forward);
                }
                if (!goal) { return found; }
                // **On a route, which way to walk is the route and not the
                // goal.** Measured on a 19 km way to one: the bearing to the
                // goal and the bearing of the path under the reader's feet were
                // tens of degrees apart, and the path was right -- a head
                // pointing at the goal would send a reader across the lake the
                // route goes round. So it follows the route a little way ahead:
                // far enough not to shiver with the fix, near enough not to cut
                // the corner, and the distance is the fix's own for both
                // reasons. The label goes on naming the goal and what is left.
                var look = target.straight ? remains : Math.max(AHEAD_M, AHEAD_SPREADS * spread);
                var want = best.along + forward * look;
                var mark = alongAt(target, cosine, Math.max(0, Math.min(whole, want))) || goal;
                var straight = awayFrom(at, cosine, mark.lat, mark.lon);
                found.to = bearingBetween(at, {lat: mark.lat, lng: mark.lon});
                found.right = straight > spread
                    ? Math.asin(Math.min(1, spread / straight)) * 180 / Math.PI : 180;
                found.left = -found.right;
                found.away = remains;
                found.at = {lat: goal.lat, lon: goal.lon};
                found.goal = goal;
                return found;
            }

            // **What the mark aims at, and the reader never chooses it.** Plan
            // mode's route while it is being planned, and equally while it is
            // simply what the panel is showing -- leaving plan mode does not
            // put a plan away, and a reader walking one wants it aimed at
            // either side of that line. Otherwise whatever line is selected.
            // Neither, and there is no goal to draw.
            function aimTarget() {
                // **A goal first, because it is the one line here a reader set
                // on purpose while walking.** A plan is a tour made beforehand
                // and a selection is something they tapped in order to read it;
                // a goal is an instruction, and it outranks both.
                var goal = window.trailsGoal ? window.trailsGoal.state() : null;
                if (goal && goal.at) {
                    // **Whichever reading is standing**, because both are a way
                    // now: straight is a chain of straight legs and routed is a
                    // chain of routed ones, and a goal with stops on the way has
                    // a next place to walk to either way. Keying this on
                    // *routed* aimed the straight reading past every stop the
                    // reader had put down, at the goal beyond them.
                    if (goal.line) {
                        return {name: 'the goal', segments: window.trailsGoal.segments,
                                goal: window.trailsGoal.goal, oneWay: true,
                                // **A leg drawn straight is straight**, so the
                                // whole of it is one direction and the head can
                                // look to its far end. Cutting it at sixty
                                // metres would open the fan to what sixty metres
                                // is worth rather than to what the walk is:
                                // measured, a goal 9 km off went from a quarter
                                // of a degree to thirty-eight.
                                straight: goal.way !== 'routed'};
                    }
                    // Straight at it, where there is no way yet or none could be
                    // made. A route that failed is not a reason to stop saying
                    // which way the goal lies; it is the reason the reader most
                    // wants to know.
                    return {name: 'the goal', point: {lat: goal.at.lat, lon: goal.at.lon,
                                                      name: goal.name || 'the goal'}};
                }
                var showing = window.trailsProfile || null;
                var plan = window.trailsPlan;
                if (plan && plan.segments &&
                        (planOn() || !!(showing && showing.composed && showing.plan))) {
                    return {name: 'planned route', segments: plan.segments, goal: plan.goal};
                }
                if (!showing || !showing.className) { return null; }
                // **The lines themselves, because this map has no DOM for
                // them.** `preferCanvas` paints vectors into a pane's canvas, so
                // a selection is a class name and the geometry is only ever on
                // the layer -- which is how the reach and the highlight find one
                // too.
                var rings = [];
                map.eachLayer(function (layer) {
                    if (!layer.options || layer.options.className !== showing.className) { return; }
                    if (typeof layer.getLatLngs !== 'function') { return; }
                    var got = layer.getLatLngs();
                    if (!got || !got.length) { return; }
                    if (got[0] instanceof L.LatLng) { rings.push(got); return; }
                    got.forEach(function (ring) { if (ring && ring.length > 1) { rings.push(ring); } });
                });
                if (!rings.length) { return null; }
                return {
                    name: showing.label || null,
                    segments: function (visit) {
                        for (var r = 0; r < rings.length; r += 1) {
                            for (var v = 0; v + 1 < rings[r].length; v += 1) {
                                visit(rings[r][v].lat, rings[r][v].lng,
                                      rings[r][v + 1].lat, rings[r][v + 1].lng, r);
                            }
                        }
                    },
                    // A line the reader picked off the map carries no waypoints,
                    // so what lies ahead on it is where it ends -- and its own
                    // end, not the whole selection's: two stretches of one way
                    // that meet nowhere are two lines, and the reader is walking
                    // one of them.
                    goal: function (ring, forward) {
                        var line = rings[ring];
                        if (!line) { return null; }
                        var end = forward > 0 ? line[line.length - 1] : line[0];
                        return {lat: end.lat, lon: end.lng, name: 'the end'};
                    }
                };
            }

            //: A goal's distance at the size the mark can carry it: two figures
            //: and no more. '4.2 km' is what a reader does something with, and
            //: the 20 m under that is the ring's business rather than this
            //: label's.
            function aimSaid(metres) {
                if (metres >= 1000) { return (metres / 1000).toFixed(1) + ' km'; }
                if (metres >= 100) { return (Math.round(metres / 10) * 10) + ' m'; }
                return Math.round(metres) + ' m';
            }

            //: How long the dot has stood without confirmation, at the size the
            //: mark can carry. Rounded hard, because what the reader is judging
            //: is how far they might have walked since -- and no part of that
            //: answer turns on the difference between four minutes and four and
            //: a half.
            function lostSaid(since) {
                var mins = since === null ? 0 : Math.floor((Date.now() - since) / 60000);
                if (mins < 1) { return 'no fix'; }
                if (mins < 60) { return 'no fix for ' + mins + ' min'; }
                return 'no fix for ' + Math.round(mins / 60) + ' h';
            }

            // A wedge, and an arc, in the pane the direction arrow already uses
            // the idiom of: an SVG placed by hand at the position and turned by
            // an attribute, re-placed whenever the map moves under it. Not
            // Leaflet layers, because both are measured in pixels rather than in
            // metres -- the accuracy ring is the only mark here that is ground.
            function hereMarksNode() {
                if (hereMarks) { return hereMarks; }
                var pane = map.getPane('trailsHereMarks');
                if (!pane) {
                    pane = map.createPane('trailsHereMarks');
                    // Just under the dot, and over everything else this map
                    // draws -- the reason is in `herePane` above.
                    pane.style.zIndex = HERE_MARKS_Z;
                    pane.style.pointerEvents = 'none';
                    L.DomUtil.addClass(pane, 'leaflet-zoom-hide');
                }
                hereMarks = document.createElementNS(HERE_SVG, 'svg');
                hereMarks.setAttribute('class', 'trails-here-marks');
                hereMarks.setAttribute('width', '200');
                hereMarks.setAttribute('height', '200');
                hereMarks.setAttribute('viewBox', '-100 -100 200 200');
                hereMarks.style.cssText = 'position:absolute;margin:-100px 0 0 -100px;overflow:visible;display:none';
                hereCone = document.createElementNS(HERE_SVG, 'path');
                hereCone.setAttribute('class', 'trails-here-cone');
                hereHalo = document.createElementNS(HERE_SVG, 'g');
                hereHalo.setAttribute('class', 'trails-here-facing');
                // **Cased, the way every line on this map is cased.** Measured
                // at 0.18 with a white edge and nothing else: over contour lines
                // and a stream the fan was there to be found rather than seen.
                // A white edge under a green one is the idiom the routes and the
                // trails already use, and it costs one path.
                hereAimEdge = document.createElementNS(HERE_SVG, 'path');
                hereAimEdge.setAttribute('class', 'trails-here-aim-edge');
                hereAimEdge.setAttribute('fill', 'none');
                hereAimEdge.setAttribute('stroke', '#ffffff');
                hereAimEdge.setAttribute('stroke-width', '3.6');
                hereAimEdge.setAttribute('stroke-opacity', '0.8');
                hereAimEdge.setAttribute('stroke-linejoin', 'round');
                hereAim = document.createElementNS(HERE_SVG, 'path');
                hereAim.setAttribute('class', 'trails-here-aim');
                hereAim.setAttribute('fill', HERE_GOAL);
                hereAim.setAttribute('fill-opacity', '0.24');
                hereAim.setAttribute('stroke', HERE_GOAL);
                hereAim.setAttribute('stroke-width', '1.4');
                hereAim.setAttribute('stroke-opacity', '0.9');
                hereAim.setAttribute('stroke-linejoin', 'round');
                hereAimHead = document.createElementNS(HERE_SVG, 'path');
                hereAimHead.setAttribute('class', 'trails-here-aim-head');
                hereAimHead.setAttribute('fill', HERE_GOAL);
                hereAimHead.setAttribute('stroke', '#ffffff');
                hereAimHead.setAttribute('stroke-width', '1.2');
                hereAimHead.setAttribute('stroke-linejoin', 'round');
                hereAimSaid = aimText('trails-here-aim-said', 700);
                hereAimNamed = aimText('trails-here-aim-named', 500);
                // **How old the dot is, and only while it is old.** A red dot
                // says the device has stopped confirming it; a reader on a
                // mountain has to know whether that started twenty seconds ago
                // or twenty minutes, because that is the whole of how far they
                // may have walked from the place it is drawn at. The ring
                // cannot say it -- it is the last fix's own claim and does not
                // grow -- so this is said in words, which is what words are for.
                hereLostSaid = aimText('trails-here-lost', 600, HERE_LOST);
                // The cone under the wedge, and the rim over both: the rim is
                // 17 px of the 72 the wedge covers and would otherwise be
                // painted over at exactly the angle a reader is looking at.
                hereMarks.appendChild(hereCone);
                hereMarks.appendChild(hereAimEdge);
                hereMarks.appendChild(hereAim);
                hereMarks.appendChild(hereAimHead);
                hereMarks.appendChild(hereHalo);
                hereMarks.appendChild(hereAimSaid);
                hereMarks.appendChild(hereAimNamed);
                hereMarks.appendChild(hereLostSaid);
                pane.appendChild(hereMarks);
                return hereMarks;
            }

            // **The wedge is drawn once and turned after that.** Its shape never
            // changes -- 62 degrees and 64 px, which is what a course over the
            // ground is worth on a screen -- so only the angle and how strongly
            // it is painted ever move.
            function coneShape() {
                var wide = 62 * Math.PI / 180, reach = 64;
                var a = -wide / 2 - Math.PI / 2, b = wide / 2 - Math.PI / 2;
                return 'M 0 0 L ' + (reach * Math.cos(a)).toFixed(1) + ' ' + (reach * Math.sin(a)).toFixed(1) +
                    ' A ' + reach + ' ' + reach + ' 0 0 1 ' + (reach * Math.cos(b)).toFixed(1) + ' ' +
                    (reach * Math.sin(b)).toFixed(1) + ' Z';
            }

            function arcPath(radius, from, to) {
                var a = (from - 90) * Math.PI / 180, b = (to - 90) * Math.PI / 180;
                return 'M ' + (radius * Math.cos(a)).toFixed(2) + ' ' + (radius * Math.sin(a)).toFixed(2) +
                    ' A ' + radius + ' ' + radius + ' 0 ' + ((to - from) > 180 ? 1 : 0) + ' 1 ' +
                    (radius * Math.cos(b)).toFixed(2) + ' ' + (radius * Math.sin(b)).toFixed(2);
            }

            //: The rim, brightest where the reader is facing and running out
            //: behind them. Nothing is filled: the map shows through everywhere,
            //: and the dot still has a front.
            var HALO_BANDS = [[70, 0.95, 3.2], [110, 0.5, 2.6], [160, 0.22, 2]];

            //: A figure that stays readable over whatever the tile puts under
            //: it: the white is painted first and the green over it, which is
            //: what `paint-order` is for and is cheaper than a second node.
            function aimText(className, weight, colour) {
                var node = document.createElementNS(HERE_SVG, 'text');
                node.setAttribute('class', className);
                node.setAttribute('text-anchor', 'middle');
                node.setAttribute('fill', colour || HERE_GOAL);
                node.setAttribute('stroke', '#ffffff');
                node.setAttribute('stroke-width', '3.2');
                node.setAttribute('stroke-linejoin', 'round');
                node.setAttribute('paint-order', 'stroke');
                node.setAttribute('font-size', '11');
                node.setAttribute('font-weight', String(weight));
                return node;
            }

            //: The wedge, in absolute bearings rather than turned by an
            //: attribute the way the cone is: it is not symmetric about the
            //: direction it points -- a route bending away on one side opens
            //: that side and not the other -- so there is no angle to turn.
            function wedgePath(from, to, reach) {
                var a = (from - 90) * Math.PI / 180, b = (to - 90) * Math.PI / 180;
                return 'M 0 0 L ' + (reach * Math.cos(a)).toFixed(1) + ' ' + (reach * Math.sin(a)).toFixed(1) +
                    ' A ' + reach + ' ' + reach + ' 0 ' + ((to - from) > 180 ? 1 : 0) + ' 1 ' +
                    (reach * Math.cos(b)).toFixed(1) + ' ' + (reach * Math.sin(b)).toFixed(1) + ' Z';
            }

            //: The head, which is what actually points: the wedge says how much
            //: is not known and this says the middle of it.
            function headPath(to, reach) {
                var a = (to - 90) * Math.PI / 180;
                var tip = reach + 13, base = reach + 1, wide = 6.5;
                var cx = Math.cos(a), cy = Math.sin(a);
                return 'M ' + (tip * cx).toFixed(1) + ' ' + (tip * cy).toFixed(1) +
                    ' L ' + (base * cx - wide * cy).toFixed(1) + ' ' + (base * cy + wide * cx).toFixed(1) +
                    ' L ' + (base * cx + wide * cy).toFixed(1) + ' ' + (base * cy - wide * cx).toFixed(1) + ' Z';
            }

            //: Where the figure sits: past the head, on the same bearing, and
            //: upright wherever that is. A label turned with the mark would be
            //: upside down for half the compass.
            function aimLabel(node, said, to, out) {
                var a = (to - 90) * Math.PI / 180;
                if (!said) { node.setAttribute('display', 'none'); return; }
                node.removeAttribute('display');
                node.textContent = said;
                node.setAttribute('x', ((AIM_REACH + out) * Math.cos(a)).toFixed(1));
                node.setAttribute('y', ((AIM_REACH + out) * Math.sin(a) + 4).toFixed(1));
            }

            function paintAim() {
                // Nothing to aim at, a fan too wide to mean anything, or a
                // reader standing on the route with no direction of travel to
                // say what *ahead* is: in all three the mark is not drawn, which
                // is the only honest thing it can do.
                var wide = hereGoal ? hereGoal.right - hereGoal.left : 0;
                if (!hereGoal || wide > AIM_WIDEST || (hereGoal.on && !hereGoal.goal)) {
                    hereAim.setAttribute('display', 'none');
                    hereAimEdge.setAttribute('display', 'none');
                    hereAimHead.setAttribute('display', 'none');
                    hereAimSaid.setAttribute('display', 'none');
                    hereAimNamed.setAttribute('display', 'none');
                    return;
                }
                var pad = wide < AIM_NARROWEST ? (AIM_NARROWEST - wide) / 2 : 0;
                var shape = wedgePath(hereGoal.to + hereGoal.left - pad,
                                      hereGoal.to + hereGoal.right + pad, AIM_REACH);
                hereAim.removeAttribute('display');
                hereAim.setAttribute('d', shape);
                hereAimEdge.removeAttribute('display');
                hereAimEdge.setAttribute('d', shape);
                hereAimHead.removeAttribute('display');
                hereAimHead.setAttribute('d', headPath(hereGoal.to, AIM_REACH));
                aimLabel(hereAimSaid, aimSaid(hereGoal.away), hereGoal.to, 30);
                // The name only where there is one to give. Off the route the
                // goal *is* the route, and writing its name under the figure
                // would be the mark saying what it already is.
                aimLabel(hereAimNamed, hereGoal.goal ? hereGoal.goal.name : null, hereGoal.to, 42);
            }

            function paintHereMarks() {
                var node = hereMarksNode();
                // The goal counts as a reason to draw: a reader who has just
                // switched the position on has no bearing and no compass yet,
                // and *which way to the route* is the one thing that is already
                // known from the first fix.
                if (!hereDot || (hereBearing === null && hereFacing === null && !hereGoal && !hereLost)) {
                    // Hidden with the group rather than left as it was: the
                    // group comes back for a goal or a compass reading, and a
                    // label carrying *no fix for 4 min* from an hour ago would
                    // come back with it.
                    hereLostSaid.setAttribute('display', 'none');
                    node.style.display = 'none';
                    return;
                }
                node.style.display = '';
                if (hereBearing === null) {
                    hereCone.setAttribute('display', 'none');
                } else {
                    // Faded where the last fix did not move: the angle is the
                    // last one measured, and the fading is what says it is from
                    // before. *How you came here*, not *how you are going*.
                    var strong = hereMoving ? 0.62 : 0.26;
                    hereCone.removeAttribute('display');
                    hereCone.setAttribute('d', coneShape());
                    hereCone.setAttribute('transform', 'rotate(' + hereBearing + ')');
                    hereCone.setAttribute('fill', HERE_BLUE);
                    hereCone.setAttribute('fill-opacity', String(strong));
                    hereCone.setAttribute('stroke', '#ffffff');
                    hereCone.setAttribute('stroke-width', '1');
                    hereCone.setAttribute('stroke-opacity', String(hereMoving ? 0.45 : 0.22));
                }
                hereHalo.innerHTML = '';
                if (hereFacing !== null) {
                    HALO_BANDS.forEach(function (band) {
                        var arc = document.createElementNS(HERE_SVG, 'path');
                        arc.setAttribute('d', arcPath(17, hereFacing - band[0] / 2, hereFacing + band[0] / 2));
                        arc.setAttribute('fill', 'none');
                        arc.setAttribute('stroke', HERE_FACING);
                        arc.setAttribute('stroke-opacity', String(band[1]));
                        arc.setAttribute('stroke-width', String(band[2]));
                        arc.setAttribute('stroke-linecap', 'round');
                        hereHalo.appendChild(arc);
                    });
                    // The glow last, over the brightest band: it is what makes
                    // the rim readable on a sunlit tile without filling anything.
                    var lit = document.createElementNS(HERE_SVG, 'path');
                    lit.setAttribute('d', arcPath(17, hereFacing - 36, hereFacing + 36));
                    lit.setAttribute('fill', 'none');
                    lit.setAttribute('stroke', '#ffffff');
                    lit.setAttribute('stroke-opacity', '0.5');
                    lit.setAttribute('stroke-width', '5.4');
                    lit.setAttribute('stroke-linecap', 'round');
                    hereHalo.appendChild(lit);
                }
                // Under the dot rather than out along a bearing: this is
                // about the dot itself, and there may be no bearing at all --
                // a watch that lost the sky on its second fix has a place and
                // nothing else.
                if (hereLost) {
                    hereLostSaid.removeAttribute('display');
                    hereLostSaid.textContent = lostSaid(hereKept ? hereKept.when : null);
                    hereLostSaid.setAttribute('x', '0');
                    hereLostSaid.setAttribute('y', '26');
                } else {
                    hereLostSaid.setAttribute('display', 'none');
                }
                paintAim();
                placeHereMarks();
            }

            // **Worked out again without a new fix.** The goal moves when the
            // reader moves, and equally when what is selected changes or plan
            // mode is switched -- and a mark still pointing at the line that
            // was chosen before is worse than one that is not drawn.
            //
            // The spread is read off the ring rather than off the last fix: the
            // ring is what is *drawn*, and where a better fix is being held the
            // two are deliberately not the same number.
            function aimAgain() {
                var started = (window.performance && window.performance.now) ? window.performance.now() : 0;
                var target = hereDot ? aimTarget() : null;
                hereGoal = target && hereAt && hereRing
                    ? aimAlong(hereAt, hereRing.getRadius(), target) : null;
                // **What it cost**, because it is walked on every fix and a
                // route can be tens of thousands of vertices long. Recorded
                // rather than guarded against: the number is what says whether
                // it needs guarding, and this page has no other way to know.
                if (started) { hereAimMs = Math.round((window.performance.now() - started) * 10) / 10; }
                paintHereMarks();
            }

            function placeHereMarks() {
                if (!hereMarks || !hereAt || hereMarks.style.display === 'none') { return; }
                L.DomUtil.setPosition(hereMarks, map.latLngToLayerPoint(hereAt));
            }
            map.on('zoomend viewreset moveend resize', placeHereMarks);

            // **No panel, and nothing to press twice.** It used to open a tool
            // whose whole content was a paragraph and a button called *Show my
            // position* -- a page asking a reader whether they meant what they
            // had just asked for. The mark at the foot is the switch; what there
            // is to say arrives in the same line the picker says things in, and
            // the mark's own lamp says whether it is watching.
            //
            // The browser's own permission dialogue is not this page's and does
            // not go away: it is asked once by the device, not by the map.
            function paintHere(said) {
                if (said) { saySomething(said, true); }
                if (railButtons) { paintRail(); }
                if (typeof paintQuick === 'function') { paintQuick(); }
            }

            // **Red, and it keeps the dot.** A fix that stopped arriving used
            // to take the watch, the dot and the ring with it: the mark went
            // out and the reader had to press it again -- in the one place
            // where pressing it again is least likely to work, and reported
            // from exactly there. What this map knows when a fix fails is not
            // nothing. It is *where you were*, which is the second best answer
            // and the only one there is.
            //
            // So the dot stands and turns red, the ring turns red and dashed --
            // a dashed line being what this map draws for something it cannot
            // confirm -- and the switch goes red with them, which is the half a
            // reader sees without looking for it.
            //
            // **The radius is left where the last fix put it.** It is that
            // fix's own claim and is still true of that fix; growing it by a
            // guessed walking pace would be the map inventing the one figure it
            // does not have. How long ago the claim was made is said in words
            // under the dot instead, which is a fact rather than a guess.
            function paintHereColour() {
                var colour = hereLost ? HERE_LOST : HERE_BLUE;
                if (hereDot) { hereDot.setStyle({fillColor: colour}); }
                if (hereRing) {
                    hereRing.setStyle({color: colour, fillColor: colour,
                                       fillOpacity: hereLost ? 0.07 : 0.12,
                                       dashArray: hereLost ? '5 4' : null});
                }
            }

            // **And it asks again by itself, because the watch will not.**
            // Measured in a browser: once `watchPosition` has answered *position
            // unavailable*, it never calls back -- not when a position becomes
            // available again, not after a hundred seconds of one being there
            // to have. The watch is finished and only says so by silence, which
            // is why pressing the mark again is what has always worked and why
            // the reader was left doing it. This is that press, made by the
            // page, on a clock.
            //
            // A new watch and not `getCurrentPosition`: whatever arrives has to
            // land in `drawHere` like every other fix, and a one-off that
            // succeeded would leave nothing watching afterwards.
            function askAgain() {
                if (hereWatch === null || !navigator.geolocation) { return; }
                navigator.geolocation.clearWatch(hereWatch);
                hereWatch = navigator.geolocation.watchPosition(drawHere, failedHere, HERE_WANTS);
            }

            //: The drought's own clock: it asks again, and redraws the age under
            //: the dot, which is worked out from a clock and pushed by nothing.
            //: Thirty seconds, which is longer than the twenty the watch waits
            //: before giving up -- a retry inside that window would keep
            //: throwing away the attempt that was about to answer.
            function hereAgeing(on) {
                if (hereAgeTimer) { window.clearInterval(hereAgeTimer); hereAgeTimer = null; }
                if (on) {
                    hereAgeTimer = window.setInterval(function () {
                        paintHereMarks();
                        askAgain();
                    }, LOST_AGAIN_MS);
                }
            }

            function dropHere() {
                if (hereDot) { map.removeLayer(hereDot); hereDot = null; }
                if (hereRing) { map.removeLayer(hereRing); hereRing = null; }
                if (hereMarks) { hereMarks.style.display = 'none'; }
                hereBearing = null;
                hereFrom = null;
                hereMoving = false;
                hereAt = null;
                hereGoal = null;
                // A watch switched off keeps nothing: the next one is a reader
                // somewhere else, and the fix held for its accuracy would be a
                // claim about the place they left.
                hereKept = null;
                // A watch that is off is not a watch that is failing: the red
                // belongs to a mark that is still trying.
                hereLost = null;
                hereAgeing(false);
            }

            function stopHere(said) {
                if (hereWatch !== null && navigator.geolocation) {
                    navigator.geolocation.clearWatch(hereWatch);
                }
                stopCompass();
                hereWatch = null;
                hereFixes = 0;
                dropHere();
                paintHere(said === undefined ? '' : said);
            }

            // **Where a fix puts the map.** Asked for once, on the first fix:
            // a map that re-centres on every one cannot be read while walking,
            // because the reader pans to look ahead and the next fix takes it
            // back.
            //
            // **And a route on the panel stays in the picture.** A reader who
            // has planned one is asking *where am I on this* and not *where am
            // I*: inside its bounds the scale is theirs and only the middle
            // moves; outside them the map opens far enough to hold both, which
            // is the answer to the question they actually asked.
            //
            // Whatever the panel is showing counts as that route -- a planned
            // one and a tapped line alike. There is only ever one, and it is the
            // one they are looking at.
            function goThere(where) {
                var shape = window.trailsProfile && window.trailsProfile.shape;
                var box = null;
                if (shape && shape.lat && shape.lat.length) {
                    box = L.latLngBounds([shape.lat[0], shape.lon[0]], [shape.lat[0], shape.lon[0]]);
                    for (var i = 1; i < shape.lat.length; i += 1) {
                        box.extend([shape.lat[i], shape.lon[i]]);
                    }
                }
                if (box && box.isValid()) {
                    if (box.contains(where)) { map.panTo(where); return; }
                    map.fitBounds(box.extend(where), {padding: [40, 40]});
                    return;
                }
                map.setView(where, Math.max(map.getZoom(), 13));
            }

            // **A worse fix that says nothing new does not replace a better
            // one.** Standing still while the sky thins, the radius grows from
            // 8 m to 40 m without the reader having moved a step, and a ring
            // redrawn at 40 m says the map has learnt something -- when what
            // happened is that it learnt less. The better fix stands, and the
            // dot stands with it.
            //
            // **Kept only while the new claim contains the old one.** The old
            // disc lying wholly inside the new one is exactly the case where the
            // new fix rules out nothing the old one had not already ruled out:
            // keeping it is then the sharper reading of the same evidence and
            // not a guess about where somebody has got to. The moment the two
            // merely overlap -- which is what a reader who has walked off looks
            // like -- the new fix wins, ring, dot and all.
            //
            // Which is also why this cannot be *keep the smallest radius ever
            // seen*: a small circle re-centred on a later fix 30 m away is a
            // precise claim about the wrong place, and the one thing a position
            // on a mountain must never be is confidently wrong.
            function keepingBetter(fix, spread, when) {
                if (!hereKept || spread <= hereKept.spread) { return null; }
                if (when - hereKept.when >= HOLD_MS) { return null; }
                var far = window.trailsProfilePanel && window.trailsProfilePanel.metresBetween;
                if (!far) { return null; }
                var apart = far(hereKept.at.lng, hereKept.at.lat, fix.lng, fix.lat);
                return (apart + hereKept.spread <= spread) ? hereKept : null;
            }

            function drawHere(position) {
                var fix = L.latLng(position.coords.latitude, position.coords.longitude);
                var claimed = Math.max(1, position.coords.accuracy || 0);
                var when = position.timestamp || Date.now();
                // **A fix that arrives ends the drought, whatever it says.**
                // The dot goes back to blue, the switch with it, and the words
                // under the dot go. Nothing is said about that in the line at
                // the foot: the colour coming back is the whole sentence.
                var wasLost = hereLost;
                hereLost = null;
                // What is drawn is the better of the two claims, and what is
                // remembered is whichever of them was drawn.
                var kept = keepingBetter(fix, claimed, when);
                var where = kept ? kept.at : fix;
                var spread = kept ? kept.spread : claimed;
                if (!kept) { hereKept = {at: fix, spread: claimed, when: when}; }
                // **Wherever it is.** This used to refuse a fix outside the
                // ground the map draws and stop watching -- on the grounds that
                // a dot on a blank square is not an answer. It is one: it says
                // *not here*, which a reader who has just got off a bus in the
                // wrong valley would rather be told than argued with.
                if (!hereDot) {
                    hereRing = L.circle(where, {radius: spread, color: HERE_BLUE, weight: 1,
                                                opacity: 0.7, fillColor: HERE_BLUE, fillOpacity: 0.12,
                                                interactive: false, pane: herePane(),
                                                className: 'trails-here-ring'}).addTo(map);
                    hereDot = L.circleMarker(where, {radius: 6, color: '#ffffff', weight: 2.5,
                                                     fillColor: HERE_BLUE, fillOpacity: 1,
                                                     interactive: false, pane: herePane(),
                                                     className: 'trails-here-dot'}).addTo(map);
                } else {
                    hereRing.setLatLng(where);
                    hereRing.setRadius(spread);
                    hereDot.setLatLng(where);
                }
                if (wasLost) { hereAgeing(false); paintHereColour(); paintHere(''); }
                hereFixes += 1;
                if (hereFixes === 1) { goThere(where); }
                // **Which way, from whichever of the two can say.** The device's
                // own course over the ground where it reports one -- iOS does,
                // while it is moving -- and the bearing from the last fix that
                // was far enough away where it does not. A reader cannot tell
                // the two apart, which is the point of drawing them the same.
                var told = position.coords.heading;
                // The metre this page measures distance with, asked of the one
                // place that owns it -- the same rule the picker follows.
                var far = window.trailsProfilePanel && window.trailsProfilePanel.metresBetween;
                var moved = (hereFrom && far) ? far(hereFrom.lng, hereFrom.lat, where.lng, where.lat) : 0;
                if (told !== null && told !== undefined && !isNaN(told)) {
                    hereBearing = told;
                    hereMoving = true;
                    hereFrom = where;
                } else if (hereFrom && moved >= MOVED_M) {
                    hereBearing = bearingBetween(hereFrom, where);
                    hereMoving = true;
                    hereFrom = where;
                } else {
                    // **Kept, and faded.** Standing still is when a map is read,
                    // and *how you came here* is worth more then than nothing at
                    // all -- so the last angle stands and the fading is what
                    // says it is from before. Only a watch that was switched off
                    // and on again starts with no direction.
                    hereMoving = false;
                    if (!hereFrom) { hereFrom = where; }
                }
                hereAt = where;
                // **The goal routes from where the reader is**, and this is the
                // only place on the page that knows they have moved. Whether
                // that is worth routing again for is the goal's own judgement;
                // all this owes it is the news.
                if (window.trailsGoal && window.trailsGoal.stood) {
                    window.trailsGoal.stood(where.lat, where.lng, spread);
                }
                aimAgain();
                // **The circle is the sentence.** It was said in words as well,
                // once, with the fix that moved the map -- and a line of text is
                // the wrong place for a quantity a map can draw: it is read once
                // and then gone, while the ring is there for as long as the fix
                // is, at the scale everything else on this map is drawn at.
                //
                // Which is also why the ring is left true to scale and the core
                // is not: 24 m is 12 px at z15 and a third of a pixel at z10, so
                // a ring that never shrank would be saying *this uncertain* on a
                // map too coarse to mean it. Hidden under a core of constant
                // size, it says the one thing that is true there -- better than
                // this map can draw.
            }

            // **A fix that did not arrive is not a switch that was turned
            // off.** Reported from the phone: under a cliff the first fixes
            // often fail, and the watch used to stop itself over each one -- so
            // the reader pressed the mark again, and again, in the one place
            // where pressing it is least likely to work. With a goal set it was
            // worse than tedious: the way there is worked out from where the
            // reader is standing, and every failure took that place away.
            //
            // The watch stands now through anything that might still answer,
            // and says in red that it is not answering.
            //
            // **Except a refusal, which will not change its mind.** A browser
            // told not to share a position answers once and never again, and a
            // lamp left burning for it would be this page claiming to wait for
            // something that is not coming. That one stops, and the reason
            // stands on the screen because it is the one a reader can do
            // something about.
            function failedHere(problem) {
                var code = problem ? problem.code : 0;
                if (code === 1) {
                    stopHere('This browser was told not to share your position.');
                    return;
                }
                var why = code === 3
                    ? 'No position arrived in time — under a cliff or indoors that is ordinary.'
                    : 'This device could not work out where it is.';
                var first = !hereLost;
                hereLost = {code: code, why: why, since: first ? Date.now() : hereLost.since};
                paintHereColour();
                paintHereMarks();
                paintHere('');
                // **Said once, and drawn from then on.** A watch that times out
                // every twenty seconds would otherwise put the same sentence
                // over the map three times a minute, which is how a page
                // teaches somebody to stop reading it. It fades, too: the red
                // is what carries this afterwards, on the mark the reader is
                // already looking at.
                // **The first one asks again straight away.** The common
                // case is a fix that failed once -- stepping out from under a
                // cliff, a phone that has just woken -- and thirty seconds of
                // red for something the next attempt would have answered is
                // thirty seconds of a map saying it is lost when it is not.
                // Later failures wait for the clock, which is what keeps this
                // from being a loop.
                if (first) { saySomething(why); hereAgeing(true); askAgain(); }
            }

            // **Pressed once and it watches; pressed again and it stops.** No
            // panel, no second button, and nothing asked: a reader who pressed
            // *where am I* has said what they want.
            // **The compass, asked for on the press that starts the watch.**
            // iOS gives orientation only after `requestPermission`, and only
            // from a gesture -- the press on the mark is that gesture, which is
            // why this is asked here and not when the first fix lands. One
            // dialogue, on a press the reader made anyway, and never again: a
            // refusal leaves the rim off and asks nothing further.
            function heardCompass(event) {
                var facing = null;
                if (typeof event.webkitCompassHeading === 'number' && !isNaN(event.webkitCompassHeading)) {
                    // Safari's own, and already degrees clockwise from north.
                    facing = event.webkitCompassHeading;
                } else if (event.absolute && typeof event.alpha === 'number' && !isNaN(event.alpha)) {
                    // Everywhere else: alpha counts the other way round.
                    facing = (360 - event.alpha) % 360;
                }
                if (facing === null) { return; }
                // Turned with the screen, or a phone held sideways points across
                // itself. `screen.orientation` is what a browser tells a page
                // about that, and the fallback is the older number.
                var turned = 0;
                if (window.screen && window.screen.orientation &&
                        typeof window.screen.orientation.angle === 'number') {
                    turned = window.screen.orientation.angle;
                } else if (typeof window.orientation === 'number') {
                    turned = window.orientation;
                }
                hereFacing = (facing + turned + 360) % 360;
                // **One repaint a frame.** The sensor fires some sixty times a
                // second and every one of them would otherwise rebuild four
                // arcs: the mistake this page has made twice, on a curve and on
                // a drag.
                if (herePainting) { return; }
                herePainting = true;
                window.requestAnimationFrame(function () {
                    herePainting = false;
                    if (hereWatch !== null) { paintHereMarks(); }
                });
            }

            function startCompass() {
                if (hereCompass || !window.DeviceOrientationEvent) { return; }
                var kind = 'ondeviceorientationabsolute' in window
                    ? 'deviceorientationabsolute' : 'deviceorientation';
                function listen() {
                    hereCompass = kind;
                    window.addEventListener(kind, heardCompass);
                }
                if (typeof DeviceOrientationEvent.requestPermission === 'function') {
                    DeviceOrientationEvent.requestPermission().then(function (answer) {
                        if (answer === 'granted') { listen(); }
                    }, function () { /* refused, and nothing is asked again */ });
                    return;
                }
                listen();
            }

            function stopCompass() {
                if (hereCompass) { window.removeEventListener(hereCompass, heardCompass); }
                hereCompass = null;
                hereFacing = null;
            }

            function askHere(want) {
                var wanted = want === undefined ? hereWatch === null : !!want;
                if (!wanted) { stopHere(''); return false; }
                if (hereWatch !== null) { return true; }
                if (!navigator.geolocation) {
                    paintHere('This browser has no way to tell the page where it is.');
                    return false;
                }
                startCompass();
                hereWatch = navigator.geolocation.watchPosition(drawHere, failedHere, HERE_WANTS);
                paintHere('');
                return true;
            }

            // A tab that is put away is not a tab that needs to be watched.
            window.addEventListener('pagehide', function () { stopHere(''); });
            paintHere('');

            // **Every holder lives in the dock from the start, hidden rather
            // than detached.** Detached DOM measures zero, and two of these
            // controls size themselves against what is around them — a plan
            // list that caps itself against a box whose top reads 0 caps itself
            // against nothing. It also keeps them findable: plan mode is a mode
            // and outlives its panel, so `document.querySelector` has to answer
            // for it whether or not anybody has the panel open.
            TOOLS.forEach(function (tool) {
                if (!tool.holder) { return; }
                tool.holder.style.display = 'none';
                dockParts.body.appendChild(tool.holder);
            });

            // ---- the rail, on a wide screen ----------------------------------
            var rail = document.createElement('div');
            rail.className = 'trails-rail';
            // **The same corner as the burger**, so the tools are in one place
            // whichever screen a reader is on. It also gives Leaflet its own
            // corner back: the zoom buttons and the scale bar are the *map's*
            // instruments and keep the left, while search, layers, base map,
            // plan, profile and sources are the *page's* and take the right.
            rail.style.cssText = 'position:absolute;right:10px;top:10px;width:46px;pointer-events:auto;' +
                'background:var(--trails-panel);border:1px solid var(--trails-edge);border-radius:8px;overflow:hidden;' +
                'box-shadow:0 1px 3px rgba(0,0,0,0.18)';
            L.DomEvent.disableClickPropagation(rail);
            chrome.appendChild(rail);

            var railButtons = {};
            TOOLS.forEach(function (tool, index) {
                var button = document.createElement('button');
                button.type = 'button';
                button.title = tool.label;
                button.setAttribute('aria-label', tool.label);
                button.setAttribute('data-tool', tool.key);
                button.innerHTML = iconFor(tool);
                button.style.cssText = 'display:flex;align-items:center;justify-content:center;width:100%;' +
                    'height:44px;border:0;background:none;cursor:pointer;color:var(--trails-ink-3);' +
                    'border-bottom:' + (index < TOOLS.length - 1 ? '1px solid var(--trails-rule)' : '0');
                button.addEventListener('click', function () { pick(tool.key); });
                rail.appendChild(button);
                railButtons[tool.key] = button;
            });

            // **Asked of the rail while it is standing, and after it has
            // something in it.** Two conditions, and the first version of this
            // met only one: it read the height straight after `appendChild`,
            // where the rail is an empty bordered div two pixels tall, so the
            // `Math.max` kept the arithmetic and the measurement it was named
            // for never happened. It has to be here, below the loop that fills
            // it -- and it cannot be later than here, because once `place` has
            // run the rail may be `display: none` and a hidden box measures
            // zero. The sum above stays as the answer for a browser that will
            // not say.
            RAIL_ROOM = Math.max(RAIL_ROOM, Math.ceil(rail.offsetHeight) + 20);

            // ---- the burger, on a narrow one ---------------------------------
            // Top right, not top left: the zoom buttons keep their corner, so
            // going narrow takes nothing away that was there before.
            var burger = document.createElement('button');
            burger.type = 'button';
            burger.className = 'trails-burger';
            burger.title = 'Menu';
            burger.setAttribute('aria-label', 'Menu');
            burger.innerHTML = icon('burger', 21);
            burger.style.cssText = 'position:absolute;right:10px;top:10px;width:46px;height:46px;' +
                'pointer-events:auto;display:none;align-items:center;justify-content:center;' +
                'background:var(--trails-panel);border:1px solid var(--trails-edge);border-radius:10px;' +
                'cursor:pointer;color:var(--trails-ink);box-shadow:0 1px 3px rgba(0,0,0,0.18)';
            L.DomEvent.disableClickPropagation(burger);
            burger.addEventListener('click', function () { openMenu(); });
            chrome.appendChild(burger);

            // ---- copying a position off the map ------------------------------
            // **A switch that owns the next tap, whatever else does.** Plan mode
            // takes every click on the container in the capture phase and stops
            // it there; the click-highlight, the panel and every popup take a
            // line's own click. So this is not a fourth thing asking politely:
            // it is a capture handler on the same container that stops the click
            // where it lands, and plan mode asks it first whether it may have
            // the tap at all. One state, asked by everyone who owns clicks --
            // the rule the panel's `suspend` already follows.
            var picking = false, pickPressed = null, pickSaid = null;

            // Five decimals is a metre and a bit at this latitude, which is
            // finer than a phone's own fix and coarse enough to read out loud.
            function pickText(where) {
                return where.lat.toFixed(5) + ', ' + where.lng.toFixed(5);
            }

            // What was copied, said where the reader is looking -- at the foot,
            // over the map, above whatever stands there. **No hint before the
            // fact**: a reader who armed a picker knows what a tap does, and a
            // line telling them so is a line over the ground they are aiming at.
            var pickToast = document.createElement('div');
            pickToast.className = 'trails-pick-said';
            pickToast.style.cssText = 'position:absolute;left:10px;right:10px;display:none;' +
                'pointer-events:auto;background:var(--trails-strong);color:var(--trails-on-strong);' +
                'border-radius:10px;padding:9px 12px;font-size:13px;font-weight:600;' +
                'align-items:center;gap:8px;box-shadow:0 2px 12px rgba(0,0,0,0.45);' +
                'user-select:text;-webkit-user-select:text';
            L.DomEvent.disableClickPropagation(pickToast);
            pickToast.addEventListener('click', function () { hideCopied(); });
            chrome.appendChild(pickToast);

            // The mark goes on the container and not in the chrome: the chrome is
            // held inside the safe area, and this has to land on the pixel that
            // was tapped.
            var pickMark = document.createElement('div');
            pickMark.className = 'trails-pick-mark';
            pickMark.style.cssText = 'position:absolute;display:none;width:18px;height:18px;' +
                'margin:-9px 0 0 -9px;border-radius:50%;pointer-events:none;z-index:1000;' +
                'border:2px solid var(--trails-accent);background:rgba(127,176,240,0.35)';
            container.appendChild(pickMark);

            var pickTimer = null;
            function hideCopied() {
                if (pickTimer) { window.clearTimeout(pickTimer); pickTimer = null; }
                pickToast.style.display = 'none';
                pickMark.style.display = 'none';
                pickSaid = null;
            }

            // **One line, and two things say things in it.** The picker says what
            // it copied; the position switch says how accurate a fix is and why
            // one did not arrive. A second line for the second of them would be
            // two surfaces on a phone that have to agree about which is on top,
            // which is the defect this chrome exists to end.
            // **Three states and not two, because staying and taking a pointer
            // are two things.** `true` is something to read and dismiss -- a
            // copied coordinate, which is selectable text and has to be
            // tappable. `'notice'` stands for as long as a mode does and is not
            // a control. Anything else fades.
            //
            // Found by driving it: *Tap the map to set a goal* was said sticky,
            // which put a full-width band across the middle of the map with
            // `pointer-events: auto` on it -- and it then swallowed the very tap
            // it was asking for. A hint that eats its own gesture is a good
            // joke and a bad control.
            function showSaid(sticky) {
                pickToast.style.display = 'flex';
                // A notice takes no pointer: it stands over the map, and the
                // map is what is being tapped.
                pickToast.style.pointerEvents = sticky === true ? 'auto' : 'none';
                if (pickTimer) { window.clearTimeout(pickTimer); }
                pickTimer = sticky ? null : window.setTimeout(hideCopied, 2600);
                place();
            }

            function saySomething(text, sticky) {
                if (!text) { hideCopied(); return; }
                pickToast.innerHTML = '';
                var said = document.createElement('b');
                said.textContent = text;
                pickToast.appendChild(said);
                showSaid(sticky);
            }

            function sayCopied(text, went, high) {
                pickSaid = text;
                pickToast.innerHTML = '';
                var said = document.createElement('b');
                said.textContent = text;
                if (high) {
                    // **A tilde where it is not the tapped place's own height.**
                    // Within a few metres of the line the sample *is* the place;
                    // sixty metres off a path it is the nearest ground this map
                    // ever measured, and a figure that does not say so is a
                    // figure somebody trusts by mistake.
                    said.textContent = text + ' · ' + (high.away > EXACT_M ? '~' : '') +
                        Math.round(high.metres).toLocaleString('en-GB') + ' m';
                }
                var after = document.createElement('span');
                after.style.cssText = 'font-weight:400;font-size:11.5px;opacity:0.75';
                // **What a browser refused, said as a fact.** Safari writes to
                // the clipboard only from a gesture it believes in, and a
                // standalone app is where that is least certain -- so the text
                // stays on the screen, selectable, rather than the page claiming
                // something it did not do.
                after.textContent = went ? 'copied' : '— copy it by hand';
                pickToast.appendChild(said);
                pickToast.appendChild(after);
                // **What it says must not eat the next tap.** Driven, a second
                // position picked while the first was still on the screen landed
                // on this line and did nothing at all -- the handler steps around
                // everything in the chrome, and this is in the chrome. A refusal
                // stays until it is dismissed and keeps its pointer, because it
                // is a thing to read and select; a success goes on its own,
                // because it has already done what it says.
                showSaid(!went);
            }

            // **The nearest ground this map ever measured, where there is no
            // raster to ask.** The heights the page carries along the network
            // are sampled every 5 m into the routing graph, so a tap on a path
            // can be told its height and a tap on an open hillside cannot, and
            // the honest thing is to say the first and stay quiet about the
            // second rather than quote a number about somewhere else.
            //
            // **This is the fallback now, and no longer the answer.** Where the
            // map carries height tiles the tapped place has its own height and
            // `window.trailsPlan.heightAt` reads it; this stands for the map
            // that has none, and for the tile that is not there — off the
            // model's edge, or offline over ground that was never kept.
            //
            // Measured on the built graph before this was written: 949,704
            // vertices, and a scan over every one of them is **3 ms** -- once
            // per tap, which is why there is no index here and nothing to keep
            // in step with the geometry. `nearestNode` two panels away says the
            // same thing about a hundred thousand nodes.
            var NEAR_M = 100, EXACT_M = 25;

            function pathHeight(lat, lon) {
                var graph = window.trailsGraph;
                var panel = window.trailsProfilePanel;
                if (!graph || !graph.coordinates || !graph.heights || !panel) { return null; }
                // The metre this page measures distance with, asked of the one
                // place that owns it: a second haversine here would be a second
                // answer to *how far is that*.
                var far = panel.metresBetween;
                var scale = Math.cos(lat * Math.PI / 180);
                var best = -1, closest = Infinity, i;
                for (i = 0; i + 1 < graph.coordinates.length; i += 2) {
                    var dx = (graph.coordinates[i] - lon) * scale;
                    var dy = graph.coordinates[i + 1] - lat;
                    var away = dx * dx + dy * dy;
                    if (away < closest) { closest = away; best = i >> 1; }
                }
                if (best < 0) { return null; }
                // Which edge that vertex belongs to. `vertexAt` is a prefix
                // array, so this is a search and not a walk.
                var low = 0, high = graph.vertexAt.length - 1;
                while (low < high) {
                    var middle = (low + high + 1) >> 1;
                    if (graph.vertexAt[middle] <= best) { low = middle; } else { high = middle - 1; }
                }
                var edge = low;
                var v0 = graph.vertexAt[edge], v1 = graph.vertexAt[edge + 1];
                var s0 = graph.sampleAt[edge], s1 = graph.sampleAt[edge + 1];
                var samples = s1 - s0;
                if (!(v1 > v0) || samples < 1) { return null; }
                // **The nearest place on the line, not the nearest vertex.** Two
                // vertices 200 m apart can both be 100 m from a tap that is five
                // metres from the line between them, and refusing a height there
                // would be refusing one this map holds.
                var along = 0, total = 0, hit = 0, shortest = Infinity, v;
                var lastLon = graph.coordinates[2 * v0], lastLat = graph.coordinates[2 * v0 + 1];
                for (v = v0 + 1; v < v1; v += 1) {
                    var x = graph.coordinates[2 * v], y = graph.coordinates[2 * v + 1];
                    var span = far(lastLon, lastLat, x, y);
                    // Projected in degrees with the latitude's own scale, which
                    // is what every other point-to-line on this page uses; the
                    // metres come back out of `metresBetween`.
                    var ax = (lon - lastLon) * scale, ay = lat - lastLat;
                    var bx = (x - lastLon) * scale, by = y - lastLat;
                    var square = bx * bx + by * by;
                    var t = square > 0 ? Math.max(0, Math.min(1, (ax * bx + ay * by) / square)) : 0;
                    var onLon = lastLon + (x - lastLon) * t, onLat = lastLat + (y - lastLat) * t;
                    var gap = far(lon, lat, onLon, onLat);
                    if (gap < shortest) { shortest = gap; hit = total + span * t; }
                    total += span;
                    lastLon = x; lastLat = y;
                }
                if (!(shortest <= NEAR_M)) { return null; }
                // Every 5 m along the edge means the samples are spread evenly
                // between its ends, which is what `layEdges` writes and what an
                // index into them therefore means.
                var at = samples < 2 ? 0 : Math.round((total > 0 ? hit / total : 0) * (samples - 1));
                var value = graph.heights[s0 + Math.max(0, Math.min(samples - 1, at))];
                if (value === null || value === undefined || isNaN(value)) { return null; }
                return {metres: value, away: shortest};
            }

            //: Which tap the message on the screen belongs to. A height that
            //: arrives after the next tap is a figure about the last place.
            var pickTurn = 0;

            function copyHere(event) {
                var where = map.mouseEventToLatLng(event);
                var at = map.mouseEventToContainerPoint(event);
                pickMark.style.left = Math.round(at.x) + 'px';
                pickMark.style.top = Math.round(at.y) + 'px';
                pickMark.style.display = 'block';
                var text = pickText(where);
                var turn = (pickTurn += 1);
                // **Where there is a raster, the tapped place has its own
                // height, and it is worth the moment it takes.** The tiles are
                // fetched through the worker, so over kept ground this answers
                // offline and in a few milliseconds; over ground that was never
                // kept it is a tile off the network, and off the model's edge
                // there is none. Nothing is shown from the network's samples
                // while that is in flight: one tap would say two different
                // numbers a moment apart, and the second correcting the first
                // is how a reader learns to trust neither.
                var asking = (window.trailsPlan && window.trailsPlan.heightAt)
                    ? window.trailsPlan.heightAt(where.lat, where.lng) : null;
                // **Shown beside the position and never copied with it.** What
                // goes to the clipboard is what was asked for -- a position --
                // and a height read off a path 30 m away would be a figure
                // somebody pastes into a note as if it were measured there.
                var high = asking ? null : pathHeight(where.lat, where.lng);

                function fill(metres, went) {
                    // A tile that is not there is not a refusal to answer: it is
                    // ground this model does not cover, and the network's
                    // nearest sample is then all there is to say.
                    var found = (metres === null || metres === undefined || isNaN(metres))
                        ? pathHeight(where.lat, where.lng)
                        // Read where the tap was, so nothing is approximate
                        // about it and nothing says it is.
                        : {metres: metres, away: 0};
                    // Not over a later tap, and not over a message the reader
                    // has already dismissed.
                    if (!found || turn !== pickTurn || pickSaid !== text) { return; }
                    // **A number that arrives late is a new thing to read**, so
                    // it gets a whole message's worth of time rather than
                    // whatever was left of the one it lands in.
                    sayCopied(text, went, found);
                }

                function said(went) {
                    sayCopied(text, went, high);
                    if (!asking) { return; }
                    asking.then(function (metres) { fill(metres, went); },
                                function () { fill(null, went); });
                }

                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(text).then(function () {
                        said(true);
                    }, function () {
                        said(false);
                    });
                    return;
                }
                said(false);
            }

            // The same two facts plan mode's own handler is built from: what is
            // not terrain, and how far a pointer may roll and still be a tap.
            function overChrome(event) {
                if (!event.target || !event.target.closest) { return false; }
                return !!event.target.closest('.leaflet-control-container, .leaflet-popup, .trails-chrome');
            }
            var pressEvent = window.PointerEvent ? 'pointerdown' : 'mousedown';
            container.addEventListener(pressEvent, function (event) {
                pickPressed = {x: event.clientX, y: event.clientY};
            }, true);
            container.addEventListener('click', function (event) {
                if (!picking || overChrome(event)) { return; }
                var slop = window.trailsReach ? window.trailsReach.slop() : 3;
                if (pickPressed && Math.abs(event.clientX - pickPressed.x) +
                        Math.abs(event.clientY - pickPressed.y) >= slop) { return; }
                // Stopped here, which is the whole point of being in the capture
                // phase: no waypoint, no selection, no popup -- the tap meant a
                // position and nothing else.
                event.stopPropagation();
                copyHere(event);
            }, true);

            // ---- setting a goal ---------------------------------------------
            // **Armed, and it lets go of itself.** One tap sets a goal; a
            // switch that stayed on would make every later tap a goal, which is
            // the mistake plan mode is allowed to make because planning is a
            // mode a reader is *in* and this is one thing they are doing.
            // **Three things the next tap can mean, and it says which.** A goal,
            // a stop on the way to it and a place already set being put
            // somewhere else are all set by the same gesture and are not the
            // same act, so the switch carries which one it is armed for rather
            // than being a flag -- and the row at the foot lights the button or
            // the row that armed it.
            var aiming = null;
            //: Which place the tap moves while it is armed for `'move'`: an
            //: index into the goal's own list, stops first and the goal last.
            //: Meaningless otherwise, and read as such.
            var aimingAt = -1;

            function askAiming(want, at) {
                var wanted = want === 'stop' ? 'stop' : want === 'move' ? 'move'
                    : (want === undefined ? (aiming ? null : 'goal') : (want ? 'goal' : null));
                aiming = wanted;
                aimingAt = wanted === 'move' && typeof at === 'number' && at >= 0 ? at : -1;
                if (wanted === 'move' && aimingAt < 0) { aiming = null; }
                // Never both: the picker owns the next tap while it is on, and
                // two crosshairs over one map is a page that cannot say what a
                // tap will do.
                if (aiming && picking) { askPicking(false); }
                container.style.cursor = aiming ? 'crosshair' : '';
                // **And nothing is said over the map.** Arming for a goal used
                // to put *Tap the map to set a goal* over the ground, and
                // setting one answered *Goal set*: the lamp is lit, the
                // crosshair is up, and the target appears where the tap landed
                // -- so all three said in words what had just been done in
                // front of the reader. A page that explains its own obvious
                // acts teaches people to stop reading it. Reported from the
                // phone, and they went. The stop's own hint -- *or a stop to
                // take it away* -- outlived them, on the argument that no mark
                // says a tap on a stop removes it; reported from the phone as
                // well, standing across the very ground the tap was meant for,
                // and it went the same way.
                paintRail();
                paintQuick();
                // The row at the foot lights the button that armed this, and it
                // is the panel that draws that row.
                if (window.trailsProfilePanel && window.trailsProfilePanel.goal && goalNow) {
                    window.trailsProfilePanel.goal(goalNow);
                }
                return aiming;
            }

            // **The switch a lit lamp promises.** Three states and one press:
            //
            // * nothing set and not armed -- arm the next tap
            // * armed -- let go, and set nothing
            // * a goal standing -- show the way there on the panel
            //
            // The third used to put the goal away, on the argument that a
            // switch that is *on* is switched off by pressing it. Reported
            // from the phone, twice over: a goal with three stops on the way
            // lost to one press meant for something else, and no way to bring
            // the goal back on to the panel once another trail had been tapped
            // -- the goal stood, the lamp was lit, and the only control that
            // knew about it would destroy it. So the lit flag *shows*, and
            // putting a goal away is a line in its own menu, in words, where
            // a reader looks for what can be done with a thing.
            function pressGoal() {
                if (aiming) { askAiming(false); return; }
                if (goalSet() && window.trailsGoal) {
                    if (!window.trailsGoal.showProfile() && !window.trailsGoal.show()) { goalAdrift(); }
                    return;
                }
                askAiming(true);
            }

            //: One line of the page below, as a button.
            function adriftStep(label, told, act) {
                var made = document.createElement('button');
                made.type = 'button';
                made.className = 'trails-goal-adrift-step';
                made.textContent = label;
                made.title = told;
                made.style.cssText = 'display:block;width:100%;text-align:left;font:inherit;font-size:13px;' +
                    'margin-top:6px;padding:8px 10px;cursor:pointer;border:1px solid var(--trails-rule);' +
                    'border-radius:9px;background:var(--trails-solid);color:var(--trails-ink)';
                made.addEventListener('click', function (event) { event.stopPropagation(); act(); });
                return made;
            }

            // **A goal with no way to it is still a goal, and the flag has to
            // say so.** Reported from the phone: a position typed into the
            // search, set as a goal with the position switch off, and then the
            // flag did nothing at all -- no page, no way to be rid of it, a
            // green ring standing on the map for good. The cause is that the
            // panel draws the *way* there and there is none: routing starts
            // where the reader is, and nobody had told the page where that was.
            //
            // So this page says exactly that, and carries the three things the
            // reader can do about it. Nothing here is particular to a typed
            // position -- a goal taken from a hut's popup with the position off
            // was as stuck, and had been since the goal was written.
            function goalAdrift() {
                var said = window.trailsGoal.state();
                var at = said.at;
                if (!at) { return; }
                var node = document.createElement('div');
                node.className = 'trails-goal-adrift';
                node.style.cssText = 'font-family:sans-serif;font-size:13px;line-height:1.5';
                var where = document.createElement('div');
                where.style.cssText = 'font-weight:600';
                where.textContent = at.lat.toFixed(5) + ', ' + at.lon.toFixed(5);
                var why = document.createElement('div');
                why.style.cssText = 'color:var(--trails-ink-3);margin-bottom:4px';
                why.textContent = 'There is no way to show yet: the way to a goal is worked out from '
                    + 'where you are, and this page does not know that. Switch your position on and '
                    + 'it appears with the first fix.';
                node.appendChild(where);
                node.appendChild(why);
                node.appendChild(adriftStep('Where I am', 'Switch the position on and work the way out',
                    function () { askHere(true); closeSheet(); }));
                node.appendChild(adriftStep('⌖  Move the goal', 'The next tap on the map puts the goal there',
                    function () { askAiming('move', Math.max(0, (said.stops || []).length - 1)); closeSheet(); }));
                // **And the way out that does not need a position at all.** The
                // goal's own page carries this too, and that page is exactly
                // what cannot be reached from here: it is the *way there*, and
                // there is none. The places are places regardless.
                if (window.trailsPlan && window.trailsPlan.fromGoal) {
                    node.appendChild(adriftStep('Make a plan of this way',
                        'The places become the plan’s points, in order, and the goal comes off the map',
                        function () { if (window.trailsPlan.fromGoal()) { closeSheet(); } }));
                }
                node.appendChild(adriftStep('Drop the goal', 'Take the goal off the map', function () {
                    var stops = Math.max(0, (said.stops || []).length - 1);
                    if (stops > 0 && !window.confirm('Drop the goal and ' + stops +
                            (stops === 1 ? ' stop?' : ' stops?'))) { return; }
                    window.trailsGoal.clear();
                    closeSheet();
                }));
                readInSheet(said.name || 'The goal', node, false, 'goal-adrift');
            }

            function setGoalHere(event) {
                if (!window.trailsGoal) { return; }
                var where = map.mouseEventToLatLng(event);
                if (aiming === 'stop') {
                    // **A tap adds a stop, and only that.** It used to take a
                    // stop away as well, when it landed on one -- and the one
                    // thing that said so was the hint over the map, which went
                    // for standing across the ground the tap was meant for. A
                    // gesture with two meanings and nothing to say which is not
                    // a gesture; taking a stop away is in the list at the foot
                    // now, in words, where a reader looks for it.
                    var called = (window.trailsPlan && window.trailsPlan.named)
                        ? window.trailsPlan.named(where.lat, where.lng) : null;
                    // Named where something is named within reach and
                    // standing where it stands; otherwise the tap, which the
                    // goal takes as the line under it where there is one within
                    // a finger. A named thing does not snap: it is a place.
                    if (called) { window.trailsGoal.addStop(called.lat, called.lon, called.name); }
                    else { window.trailsGoal.addStop(where.lat, where.lng, null, true); }
                    askAiming(false);
                    return;
                }
                if (aiming === 'move') {
                    // **The place the list armed this for, put where the tap
                    // landed.** The last of the list is the goal and keeps its
                    // stops; any other is a stop and keeps its place in the
                    // order. Named and snapped by the same rule as setting one.
                    var moving = window.trailsGoal.state().stops || [];
                    var found = (window.trailsPlan && window.trailsPlan.named)
                        ? window.trailsPlan.named(where.lat, where.lng) : null;
                    if (aimingAt + 1 >= moving.length) {
                        if (found) { window.trailsGoal.move(found.lat, found.lon, found.name); }
                        else { window.trailsGoal.move(where.lat, where.lng, null, true); }
                    } else if (found) {
                        window.trailsGoal.moveStop(aimingAt, found.lat, found.lon, found.name);
                    } else {
                        window.trailsGoal.moveStop(aimingAt, where.lat, where.lng, null, true);
                    }
                    askAiming(false);
                    return;
                }
                // **Named where the map already names something within reach,
                // and standing where that thing stands** -- the rule a waypoint
                // follows. A goal called *Storvasshytta* is one a reader can
                // check they meant, and the hut is where they are going rather
                // than the pixel they hit.
                var named = (window.trailsPlan && window.trailsPlan.named)
                    ? window.trailsPlan.named(where.lat, where.lng) : null;
                if (named) { window.trailsGoal.set(named.lat, named.lon, named.name); }
                else { window.trailsGoal.set(where.lat, where.lng, null, true); }
                askAiming(false);
            }

            container.addEventListener('click', function (event) {
                if (!aiming || overChrome(event)) { return; }
                var slop = window.trailsReach ? window.trailsReach.slop() : 3;
                if (pickPressed && Math.abs(event.clientX - pickPressed.x) +
                        Math.abs(event.clientY - pickPressed.y) >= slop) { return; }
                // Stopped in the capture phase for the reason the picker's is:
                // no waypoint, no selection, no popup -- the tap meant a goal.
                event.stopPropagation();
                setGoalHere(event);
            }, true);

            function askPicking(want) {
                picking = want === undefined ? !picking : !!want;
                if (!picking) { hideCopied(); }
                container.style.cursor = picking ? 'crosshair' : '';
                paintRail();
                paintQuick();
                place();
                return picking;
            }

            // ---- the two quick marks, where the rail is not -------------------
            // **The rail is the desktop's answer and this is the phone's.** They
            // are the same two switches: on a wide screen they stand in the rail
            // with the other tools, on a narrow one the rail is hidden behind the
            // burger and these two are what a thumb reaches -- at the foot, on
            // the right, which is where a map on a phone has kept its position
            // button for a decade. Measured on the desktop before this was
            // built: the dock ends at x 1334 and the rail begins at 1344, so a
            // second stack there would not collide with anything -- and would
            // read as a second rail, 362 px under the first one.
            var quick = document.createElement('div');
            quick.className = 'trails-quick';
            quick.style.cssText = 'position:absolute;right:10px;display:none;flex-direction:column;' +
                'gap:8px;pointer-events:auto';
            function quickMark(key, label, act) {
                var made = document.createElement('button');
                made.type = 'button';
                made.className = 'trails-quick-' + key;
                made.title = label;
                made.setAttribute('aria-label', label);
                made.innerHTML = icon(key, 21);
                made.style.cssText = 'width:46px;height:46px;display:flex;align-items:center;' +
                    'justify-content:center;border-radius:10px;cursor:pointer;' +
                    'background:var(--trails-panel);border:1px solid var(--trails-edge);' +
                    'color:var(--trails-ink);box-shadow:0 1px 3px rgba(0,0,0,0.18)';
                made.addEventListener('click', function (event) {
                    event.stopPropagation();
                    act();
                });
                quick.appendChild(made);
                return made;
            }
            var quickPick = quickMark('pick', 'Copy a position', function () { askPicking(); });
            var quickGoal = quickMark('goal', 'Set a goal', function () { pressGoal(); });
            var quickHere = quickMark('here', 'Where I am', function () { askHere(); });
            L.DomEvent.disableClickPropagation(quick);
            chrome.appendChild(quick);

            function paintQuick() {
                // Called from the position switch as well, which is written
                // above these two and runs once before they exist.
                if (!quickPick || !quickHere || !quickGoal) { return; }
                // **The position mark has a third state.** Lit says *this is
                // on*; lit red says *this is on and getting nothing* -- which
                // is a thing a reader has to be able to take in from the corner
                // of an eye, on a screen held at arm's length in the rain, and
                // is why the colour comes before the words.
                [[quickPick, picking, false], [quickGoal, aiming || goalSet(), false],
                 [quickHere, hereWatch !== null, !!hereLost]].forEach(function (each) {
                    var lit = each[1], paint = each[2] ? HERE_LOST : 'var(--trails-accent)';
                    each[0].style.background = lit ? paint : 'var(--trails-panel)';
                    each[0].style.borderColor = lit ? paint : 'var(--trails-edge)';
                    each[0].style.color = lit ? 'var(--trails-on-accent)' : 'var(--trails-ink)';
                    each[0].setAttribute('aria-pressed', String(!!lit));
                });
                // And why, in words, for the reader who came back to a red
                // button and missed the line that faded. The title is a desktop
                // thing and the label is what a screen reader speaks; on a
                // phone it is neither, which is the whole reason the colour
                // had to carry it first.
                var told = hereLost ? hereLost.why : 'Where I am';
                quickHere.title = told;
                quickHere.setAttribute('aria-label', told);
            }

            // ---- what is being looked at, and who says so --------------------
            // **Planning on a phone had a bar of its own and does not need
            // one.** Measured before that bar: with the plan panel shut, the
            // only thing on a 390 px screen was the burger — nothing said plan
            // mode was on, and every tap placed a point; reaching the point list
            // was four taps. The bar answered that and cost a second row, above
            // the profile panel's own heading and saying a second version of the
            // same sentence. What plan mode has to say is pushed into that one
            // row now, and the state it is drawn from is here.
            // **One state, and everything that switches the profile sets this
            // one.** Three places offer the switch — the rail, the lit mark in
            // the panel's own row, and the plan control — and a second flag
            // beside this is two switches that can disagree, which is the
            // failure this chrome exists to end.
            //
            // Three values and not two. `null` means *nobody has said*, and the
            // default then depends on where the reader is: while planning on a
            // narrow screen the map is what is being tapped, so the panel does
            // not open by itself; everywhere else a selected line has a profile.
            // `true` and `false` are the reader overriding that, in either
            // direction, and they outlast the state that set the default.
            var planState = null, profileAsked = null, selection = null;
            //: What the goal control last said about itself. The rail's lamp,
            //: the row at the foot and the position mark all draw from this
            //: rather than asking it, the way plan mode's summary works.
            var goalNow = null;
            function goalSet() { return !!(goalNow && goalNow.at); }

            // **Plan mode's bar is the panel's own row now.** It stood above
            // the profile panel while a route was being made -- its figures over
            // the panel's figures, its profile switch over the panel's own -- and
            // the two rows said two versions of *what you are looking at*. There
            // is one row, it belongs to the panel, and what plan mode has to say
            // is pushed into it below.

            // ---- the profile panel, which is shown by having something to show
            var profileBox = null;
            function profilePanel() {
                if (!profileBox) { profileBox = container.querySelector('.trails-profile-panel'); }
                return profileBox;
            }

            // **While a route is being planned on a narrow screen the panel
            // does not open by itself.** The ground under it is exactly what the
            // reader is tapping: measured, two points put 389 px of panel on an
            // 844 px screen and left 439 px of map to place the next one on. It
            // is one tap away on the Profile tool and not gone — the bargain the
            // legend struck, in a second place.
            function profileDefault() {
                return !(mapRoom().x < NARROW && planOn());
            }

            function profileOn() {
                return profileAsked === null ? profileDefault() : profileAsked;
            }

            // Every switch calls this and none of them keeps a state of its own.
            // Asked for nothing, it flips whatever is showing now — which is why
            // a switch never has to know how the panel came to be where it is.
            function askProfile(want) {
                profileAsked = (want === undefined || want === null) ? !profileOn() : !!want;
                paintProfile();
                // The plan control draws the same switch and cannot be told by
                // painting: it is plan mode's element, in plan mode's scope.
                //
                // **Only while it is planning**, and that is not tidiness. Plan
                // mode's refresh ends in `present()`, which feeds the profile
                // panel — and with no points it feeds it *nothing*, which clears
                // whatever chain the reader had selected. Driven, hiding the
                // profile over a selected chain deselected the chain. The button
                // this repaint is for only stands while planning anyway.
                if (planOn() && window.trailsPlan && window.trailsPlan.repaint) {
                    window.trailsPlan.repaint();
                }
                place();
            }

            // **Two answers, not one.** The panel is a row that stands whenever
            // there is something to stand for -- a selected line, a place whose
            // popup was handed over, a route being planned -- and a set of pages
            // above it that the reader opens and folds. This used to be one
            // answer, which is why putting the profile away also took the row
            // with it and left a reader who had tapped a line with nothing at
            // all on the screen about it.
            function paintProfile() {
                var panel = profilePanel();
                var standing = !!(selection || planOn());
                if (panel) { panel.style.display = standing ? '' : 'none'; }
                var pager = window.trailsProfilePanel;
                if (pager && pager.pages && pager.page) {
                    var want = standing && profileOn();
                    // Asked only where the answer would change it: the panel
                    // tells this back through `placed`, and a call that always
                    // spoke would be a loop between the two.
                    if (pager.pages().open !== want) { pager.page(want ? true : false); }
                }
                paintRail();
            }

            // Whether the pages are showing, which is what the rail's own icon
            // says now that it is never greyed. The row underneath them is not
            // the answer: it stands whether they do or not.
            function profileShowing() {
                var pager = window.trailsProfilePanel;
                return !!(pager && pager.pages && pager.pages().open);
            }

            // Read off what plan mode last pushed rather than asked for. Asking
            // composes the whole route, which is 45 ms over a 37 km one, and
            // this is called on every paint.
            function planOn() { return !!(planState && planState.on); }
            // A plan with points in it, whether or not its mode is on: what a
            // place's page offers *Add to the plan* for.
            function planStanding() { return !!(planState && planState.points > 0); }

            function paintRail() {
                TOOLS.forEach(function (tool) {
                    var button = railButtons[tool.key];
                    if (!button) { return; }
                    var lit = openTool === tool.key;
                    button.style.background = lit ? 'var(--trails-accent)' : 'none';
                    // A tool the reader has switched on rather than opened:
                    // plan mode outlives its panel, and the profile panel stands
                    // at the foot rather than in the dock.
                    var running = (tool.key === 'plan' && planOn()) ||
                        (tool.key === 'profile' && profileShowing()) ||
                        (tool.key === 'here' && hereWatch !== null) ||
                        (tool.key === 'pick' && picking) ||
                        (tool.key === 'goal' && (aiming || goalSet())) ||
                        (tool.key === 'offline' && offlineOn());
                    // The one lamp with a third colour: watching, and getting
                    // nothing back.
                    var lost = tool.key === 'here' && hereLost && hereWatch !== null;
                    button.style.color = lit ? 'var(--trails-on-accent)'
                        : (lost ? HERE_LOST : (running ? 'var(--trails-accent)' : 'var(--trails-ink-3)'));
                    button.setAttribute('aria-pressed', String(lit));
                    if (tool.key === 'here') {
                        button.title = lost ? hereLost.why : tool.label;
                        button.setAttribute('aria-label', button.title);
                    }
                });
            }

            function buildMenu() {
                menuParts.title.textContent = 'Menu';
                menuParts.body.innerHTML = '';
                TOOLS.forEach(function (tool) {
                    // The two marks stand on this very screen; a row here would
                    // be the same switch, one tap further away.
                    if (tool.quick) { return; }
                    var row = document.createElement('button');
                    row.type = 'button';
                    row.setAttribute('data-tool', tool.key);
                    // 48 px, which is a finger, and the reason every row here is
                    // a whole line rather than an icon beside a word.
                    row.style.cssText = 'display:flex;align-items:center;gap:12px;width:100%;min-height:48px;' +
                        'padding:8px 4px;border:0;border-bottom:1px solid var(--trails-rule);background:none;' +
                        'cursor:pointer;text-align:left;color:var(--trails-ink);font:inherit';
                    row.innerHTML = '<span style="flex:none;width:26px;display:flex;justify-content:center;' +
                        'color:var(--trails-ink-3)">' + iconFor(tool) + '</span>' +
                        '<span style="flex:1;min-width:0"><b style="display:block;font-size:14px">' +
                        esc(tool.label) + '</b><span style="display:block;font-size:11.5px;color:var(--trails-ink-5)">' +
                        esc(tool.hint) + '</span></span>' +
                        '<span style="flex:none;color:var(--trails-ink-5)">' + icon('chevron', 15) + '</span>';
                    row.addEventListener('click', function () { pick(tool.key); });
                    menuParts.body.appendChild(row);
                });
            }

            function pick(key) {
                var tool = byKey[key];
                if (!tool) { return; }
                // The graph settles after the map is drawn, so this is read on
                // the way in rather than written once and left to go stale.
                if (key === 'info') { sayOpenCost(); }
                // With something selected this shows and hides the pages and
                // opens no dock: the panel *is* what the tool is for. With
                // nothing selected it falls through and the dock explains it.
                // **A switch and not a panel.** There is nothing to read in
                // it: it is a state the map is in, and the rail's own lamp is
                // what says so. Opening a dock to explain that would be a panel
                // whose whole content is the sentence in the menu beside it.
                if (key === 'pick') {
                    askPicking();
                    closeMenu();
                    return;
                }
                if (key === 'goal') {
                    pressGoal();
                    closeMenu();
                    return;
                }
                // The same, and for the same reason: what it opened was a
                // paragraph and a button asking whether the reader meant it.
                if (key === 'here') {
                    askHere();
                    closeMenu();
                    return;
                }
                if (key === 'profile' && selection) {
                    // **The pages, not the panel.** The row at the foot says
                    // what is selected and stands whether the pages are open or
                    // not; this is the same switch the lit mark in that row is,
                    // reached from the rail instead.
                    askProfile();
                    closeMenu();
                    return;
                }
                if (openTool === key) { closeDock(); return; }
                openTool = key;
                raise('tool');
                dockParts.title.textContent = tool.label;
                if (key === 'offline' && window.trailsOffline) { window.trailsOffline.refresh(); }
                TOOLS.forEach(function (each) {
                    if (each.holder) { each.holder.style.display = each.key === key ? '' : 'none'; }
                });
                menuOpen = false;
                paintRail();
                place();
            }

            // A tool closing on a narrow screen gives the detail back rather
            // than throwing it away: it was never closed, only covered.
            // **Which of them the reader opened last.** On a narrow screen the
            // dock, the menu and the detail are one full-screen sheet and only
            // one may be drawn -- and *which* one used to be fixed: a tool always
            // covered the detail. That is right when a tool is opened over
            // something being read and wrong the other way round, and the reader
            // who pressed the panel's own *i* met the wrong way round: the sheet
            // came up, the plan panel went, and closing the sheet gave back
            // nothing. Last opened is on top; closing it gives back what was
            // under it.
            var opened = {tool: 0, menu: 0, detail: 0}, opening = 0;
            function raise(what) { opening += 1; opened[what] = opening; }
            function topmost() {
                var best = null;
                if (openTool !== null && (!best || opened.tool > opened[best])) { best = 'tool'; }
                if (menuOpen && (!best || opened.menu > opened[best])) { best = 'menu'; }
                if (detailShown && (!best || opened.detail > opened[best])) { best = 'detail'; }
                return best;
            }

            function closeDock() { openTool = null; paintRail(); place(); }
            function closeMenu() { menuOpen = false; place(); }
            function closeSheet() { detailShown = false; place(); }

            function openMenu() {
                buildMenu();
                openTool = null;
                menuOpen = true;
                raise('menu');
                paintRail();
                place();
            }

            // ---- every popup docks -------------------------------------------
            // Leaflet keeps no public handle on what a popup was bound to, and
            // the name is worth more than the purity here: a sheet headed
            // "Details" says nothing, and the tooltip is the same text the
            // profile panel puts in its own heading, so the two agree.
            function titleFor(popup) {
                var source = popup._source;
                // The name the line carries, which is what the panel heads
                // itself with — so the sheet and the panel cannot disagree, and
                // neither needs a label drawn on the map to know it.
                var className = source && source.options ? source.options.className : null;
                var carried = className && window.trailsProfilePanel && window.trailsProfilePanel.nameOf
                    ? window.trailsProfilePanel.nameOf(className) : null;
                if (carried) { return carried; }
                if (source && source.getTooltip) {
                    var tooltip = source.getTooltip();
                    var content = tooltip && tooltip.getContent();
                    if (typeof content === 'string') {
                        return content.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
                    }
                    if (content && content.textContent) { return content.textContent.trim(); }
                }
                if (window.trailsProfile && window.trailsProfile.label) { return window.trailsProfile.label; }
                return 'Details';
            }

            // **One sheet, whatever is being read in it.** A popup docks here;
            // so does anything else the page has that is to be read rather than
            // glanced at. Two full-screen surfaces on a phone would be two
            // things that have to agree about which is on top, which is the
            // defect this chrome exists to end — so this is written once and
            // called from both.
            var detailKey = null;
            function readInSheet(title, content, asHtml, key) {
                sheetParts.title.textContent = title || 'Details';
                sheetParts.body.innerHTML = '';
                if (typeof content === 'string') {
                    var wrap = document.createElement('div');
                    // A popup's content is markup and a caller's string is text.
                    // Told apart by the caller rather than sniffed at: the day
                    // something guesses is the day a place name with an
                    // ampersand in it becomes an element.
                    if (asHtml) { wrap.innerHTML = content; } else { wrap.textContent = content; }
                    sheetParts.body.appendChild(wrap);
                } else if (content) {
                    sheetParts.body.appendChild(content);
                }
                sheetParts.body.scrollTop = 0;
                detailShown = true;
                detailKey = key || null;
                // **It comes to the top and dismisses nothing.** It used to clear
                // the open tool outright, on the grounds that a tap on the ground
                // is an answer to the map -- true of a popup, not of a panel's
                // own *i*, and either way the reader who closes the sheet wants
                // back what they had. Drawing one at a time on a narrow screen is
                // the painting's business, not this one's.
                raise('detail');
                paintRail();
                place();
            }

            // **What can be done with a place, as the page stands now.** A
            // goal always: that is what a place on a map is for. A stop on the
            // way only while a goal stands, because there is no way for it to be
            // on otherwise. A waypoint only while plan mode is on, because
            // adding one to a plan nobody is making would be a mode change
            // hiding inside a button.
            //
            // Asked for from the phone, together with the goal that becomes a
            // plan: *can I add coordinates as waypoints, and as intermediate
            // stops?* A typed position is a place like any other by the time it
            // is on the map, so both of them are offered here, on every place's
            // page, and the search needed nothing for it.
            function goalOffer(where, called) {
                var offers = [['trails-goal-take', 'Set as goal', 'Walk to this, and the mark points the way']];
                if (goalNow && goalNow.at) {
                    offers.push(['trails-stop-take', 'Add a stop on the way',
                                 'Go by way of this on the way to the goal']);
                }
                if (planOn() || planStanding()) {
                    // **While a plan stands, whether or not its mode is on.**
                    // With the mode on every tap on the map is a waypoint, so
                    // nothing can be selected there; the mode is switched off
                    // to look a place up, and that is when this is pressed.
                    // Reported from the phone. So it is one offer under one
                    // name, and it leaves the mode as it found it: bringing
                    // plan mode back would take the next place away again.
                    offers.push(['trails-point-take', 'Add to the plan',
                                 'Put this at the end of the plan']);
                }
                return '<div style="display:flex;flex-wrap:wrap;gap:6px;padding:7px 0 0;margin-top:5px;' +
                    'border-top:1px solid var(--trails-rule)">' +
                    offers.map(function (offer) {
                        return '<button type="button" class="' + offer[0] + '" data-lat="' + esc(where.lat) +
                            '" data-lon="' + esc(where.lng) + '" data-name="' + esc(called || '') + '" ' +
                            'title="' + esc(offer[2]) + '" ' +
                            'style="font:inherit;font-size:12px;padding:4px 10px;cursor:pointer;' +
                            'border:1px solid var(--trails-rule);border-radius:9px;' +
                            'background:var(--trails-solid);color:var(--trails-ink)">' + esc(offer[1]) + '</button>';
                    }).join('') + '</div>';
            }

            // **Delegated, on the document, because the button is markup and not
            // an element this holds.** The panel takes the popup's HTML in as a
            // page of its own, so there is nothing here to hang a listener on --
            // and re-finding the node after every popup would be a second thing
            // to keep in step with the panel's own paging. Leaflet's
            // `disableClickPropagation` stops mousedown and dblclick on the
            // panel and deliberately not click, which is what lets this work.
            document.addEventListener('click', function (event) {
                var button = (event.target && event.target.closest)
                    ? event.target.closest('.trails-goal-take, .trails-stop-take, .trails-point-take') : null;
                if (!button) { return; }
                event.stopPropagation();
                var lat = Number(button.getAttribute('data-lat'));
                var lon = Number(button.getAttribute('data-lon'));
                var called = button.getAttribute('data-name') || null;
                // **None of the three snaps.** A press on a page is not a
                // finger on the map: the place is where the popup says it is,
                // which for a hut is the hut and for a typed position is the
                // five decimals that were typed.
                if (button.classList.contains('trails-stop-take')) {
                    if (window.trailsGoal) { window.trailsGoal.addStop(lat, lon, called); }
                    askAiming(false);
                    return;
                }
                if (button.classList.contains('trails-point-take')) {
                    if (window.trailsPlan) { window.trailsPlan.place(lat, lon, true); }
                    return;
                }
                if (!window.trailsGoal) { return; }
                window.trailsGoal.set(lat, lon, called);
                // The armed tap is not wanted any more: this *was* the setting
                // of a goal, and a crosshair left over it would take the next
                // tap for a second one.
                askAiming(false);
                // **And a press has to show for something.** With a position
                // the panel turns to the way there on its own; with none there
                // is no way to turn to, and the page a reader had just read
                // stayed where it was -- which is the silence this was reported
                // as. `hereAt` and not the routing: a way that is being worked
                // out is on its way, and this is the case where none can be.
                if (!hereAt) { goalAdrift(); }
            });

            var adopting = false;
            map.on('popupopen', function (event) {
                if (adopting) { return; }
                var popup = event.popup;
                // **The content is a function now**, because a popup is built
                // when it is opened and not when the page is written -- see
                // `_LazyPopups`. Leaflet calls it for its own box; this asks
                // for the same thing rather than reading the box's node back
                // out, and it is handed the layer the way Leaflet hands it.
                var content = popup.getContent();
                if (typeof content === 'function') { content = content(popup._source || popup); }
                // Closed at once rather than a frame later, so it is never seen
                // to open. Leaflet re-appends the content node into its own box
                // the next time the same popup opens, which is what makes moving
                // it out of one safe.
                adopting = true;
                map.closePopup(popup);
                adopting = false;
                // **Into the panel, not over the map.** A popup used to become a
                // full-screen sheet, which answered *what did I just tap* by
                // covering the thing that had been tapped, the curve it drew and
                // the map it was on. It is a page of the panel now: beside the
                // profile where the tapped thing has one, alone where it has
                // not, which is what a place gets.
                if (window.trailsProfilePanel && window.trailsProfilePanel.detail) {
                    // **Whether it came off a place or off a line**, which the
                    // panel cannot see and has to know: a place replaces
                    // whatever was chosen, and a line's popup is that line's own
                    // second page. A marker has one position; a line has many.
                    var source = popup._source;
                    var isPoint = !!(source && source.getLatLng && !source.getLatLngs);
                    // **A place is somewhere to go, so it is offered as one.**
                    // Nearly every goal a reader sets is a named thing -- a hut,
                    // a quay, a summit -- and this is the moment they have just
                    // read what it is. Added to the markup here rather than
                    // built into the popup: a popup is composed in the build out
                    // of a table of columns, and a control is not one of them.
                    if (isPoint && window.trailsGoal) {
                        content = (content || '') + goalOffer(source.getLatLng(), titleFor(popup));
                    }
                    window.trailsProfilePanel.detail(titleFor(popup), content, isPoint);
                    paintProfile();
                    place();
                    return;
                }
                readInSheet(titleFor(popup), content, true, 'popup');
            });

            // A belt to the braces: with every popup adopted none is ever drawn,
            // but the pane's 700 against a control corner's 1000 is a defect on
            // any screen size and is not left standing on the chance that one is.
            var popupPane = map.getPane('popupPane');
            if (popupPane) { popupPane.style.zIndex = 1050; }

            // **The room the tools actually have.** The chrome is held inside
            // the safe area, so a phone held sideways offers the rail the
            // screen's height less the home indicator, and it is that -- not
            // the screen -- that has to be tall enough for nine tools. Read off
            // the box itself for the same reason as `mapRoom`: it is the only
            // number that cannot be out of date.
            function railRoom() {
                var size = mapRoom();
                return {x: chrome.clientWidth || size.x, y: chrome.clientHeight || size.y};
            }

            function narrowNow() { return isNarrow(railRoom()); }

            // ---- where everything stands -------------------------------------
            function place() {
                // **First, because whether the profile panel is drawn at all
                // depends on the width.** Driven from a desktop viewport down to
                // 390 px, the panel kept the display it had been given when the
                // screen was wide, and everything measured against its top was
                // then measured against a panel that should not have been there
                // — 346 px of map instead of 784. Anything that re-places has to
                // re-decide this.
                paintProfile();
                var size = mapRoom();
                var narrow = narrowNow();
                var landscape = narrow && size.x > size.y;
                chrome.classList.toggle('trails-chrome-narrow', narrow);
                rail.style.display = narrow ? 'none' : '';

                // **Leaflet's corners are Leaflet's.** The rail stood at the
                // left and this pushed the whole top-left corner 56 px aside to
                // make room for it — which put the zoom buttons at 66, exactly
                // where the dock opened, so every tool a reader opened covered
                // the zoom. Moved to the right, the rail needs no room from
                // anybody: nothing here touches a corner it did not make.

                // **What a soft keyboard covers.** It shrinks the *visual*
                // viewport and leaves the layout one alone, so the container
                // reports a height that is partly under the keyboard and a
                // full-screen sheet reaches under it with the field the reader
                // is typing into. Both places this page asks for typing — the
                // search and a stage's name — are fields inside such a sheet.
                // With no keyboard up the two viewports agree and nothing here
                // moves, which is the part a check can hold.
                var covered = window.visualViewport
                    ? Math.max(0, Math.round(size.y - window.visualViewport.height)) : 0;

                // The floor is the top of the profile panel where one is showing,
                // measured rather than assumed: it is the reader's own to drag.
                var floor = size.y - covered;
                var panel = profilePanel();
                var standing = !!(panel && panel.style.display !== 'none');
                if (standing) {
                    var seen = panel.getBoundingClientRect();
                    if (seen.height > 0) {
                        floor = Math.min(floor, Math.max(0, seen.top - container.getBoundingClientRect().top));
                    }
                }

                // **Every figure so far is measured from the top of the map,
                // and the panels do not stand there.** They are children of the
                // chrome, which is held inside the safe area, so a height taken
                // from the map's is that much too tall the moment a phone has
                // insets -- and the overflow all lands at the bottom, where the
                // last row of a list is.
                //
                // Measured with an iPhone's portrait insets simulated (top 59,
                // bottom 34) on a 390 x 844 screen: the full-height dock ran
                // from 59 to 903 on a screen that ends at 844, its scroll
                // stopped at its own maximum, and the legend's last row --
                // *Farms and holdings [SSR]* -- sat at 847, off the screen and
                // unreachable by any gesture. Reported from the phone as a row
                // that could not be scrolled to. Sideways the top inset is 0
                // and nothing ran over, which is why it only happened upright.
                //
                // `railRoom` is the chrome's own box, and `chromeTop` is where
                // that box begins in the map's coordinates -- the one number
                // that turns the figures above into the panels' own.
                var room = railRoom();
                var chromeTop = Math.max(0, Math.round(
                    chrome.getBoundingClientRect().top - container.getBoundingClientRect().top));

                // Drawn from the three facts, in one place. On a narrow
                // screen a tool covers the detail rather than replacing it.
                var top = narrow ? topmost() : null;
                menu.style.display = (menuOpen && narrow && top === 'menu') ? 'flex' : 'none';
                dock.style.display = (openTool && (!narrow || top === 'tool')) ? 'flex' : 'none';
                sheet.style.display = (detailShown && (!narrow || top === 'detail')) ? 'flex' : 'none';

                var covering = narrow && (openTool !== null || menuOpen ||
                    (!landscape && detailShown));
                burger.style.display = (narrow && !covering) ? 'flex' : 'none';
                veil.style.display = covering ? 'block' : 'none';
                // **Where the rail is not.** On a wide screen these two stand in
                // it with the other tools; here they are what a thumb reaches.
                // Above whatever is at the foot -- the row of a selection, the
                // keyboard, or the 16 px the attribution is left -- because that
                // is the one edge everything else at the foot is measured from.
                quick.style.display = (narrow && !covering) ? 'flex' : 'none';
                var footRoom = Math.max(covered, size.y - floor, 16);
                quick.style.bottom = (footRoom + 12) + 'px';
                paintQuick();
                // And what was copied stands over the marks that copied it.
                if (pickToast.style.display !== 'none') {
                    pickToast.style.bottom = (footRoom + (narrow ? 116 : 12)) + 'px';
                }

                if (narrow) {
                    // **A sheet with the veil behind it has the whole screen.**
                    // Reported with a picture: Sources opened over a panel
                    // showing a profile stopped at the top of that panel and
                    // left 450 px of nothing under it. The floor is where the
                    // *map* ends, which is what a box standing beside the panel
                    // has to respect -- and one of these is not beside it. The
                    // veil is over the panel, the marks at the foot are put
                    // away, and there is nothing down there to keep clear of.
                    //
                    // The keyboard is the one thing that still takes room:
                    // `covered` is what it hides, and both places this page
                    // asks for typing are fields inside one of these sheets.
                    // **The chrome's height and not the map's**, capped by
                    // the box these sheets actually live in: the map's height
                    // runs past the chrome's bottom edge by whatever the phone
                    // keeps at the top, and a scroller that tall ends its
                    // scroll below the screen.
                    var deep = Math.max(40, Math.min(room.y, size.y - covered - chromeTop));
                    [dock, menu, sheet].forEach(function (box) {
                        box.style.left = '0';
                        box.style.right = '0';
                        box.style.top = '0';
                        box.style.bottom = 'auto';
                        box.style.width = 'auto';
                        box.style.height = deep + 'px';
                        box.style.maxHeight = 'none';
                        box.style.border = '0';
                        box.style.borderBottom = '1px solid var(--trails-edge)';
                        box.style.borderRadius = '0';
                    });
                    if (landscape) {
                        // Sideways the width is there and the height is not, so
                        // the detail becomes a column and the map keeps the rest.
                        // **And there it is beside the panel rather than over
                        // it** -- nothing is veiled for a detail held sideways --
                        // so this one does stop where the panel starts.
                        sheet.style.right = 'auto';
                        sheet.style.width = Math.min(340, Math.round(size.x * 0.44)) + 'px';
                        sheet.style.height = Math.max(40, Math.min(room.y, floor - chromeTop)) + 'px';
                        sheet.style.borderRight = '1px solid var(--trails-edge)';
                    } else {
                        sheet.style.borderRight = '0';
                    }
                } else {
                    // **The floor is 40 and the margin 8, and both are the
                    // plan control's own numbers rather than new ones.** The
                    // profile panel keeps 80 px of map clear of itself, and a
                    // box standing at 10 from the top has to fit its margin and
                    // its floor into what is left of that 80 — at a floor of
                    // 140 it did not, and the dock hung 49 px into the panel
                    // with the profile dragged as tall as it goes.
                    var capped = Math.max(40, Math.min(room.y, floor - chromeTop) - 18);
                    // **Beside the rail that opened it**, which is now the right
                    // one: 46 of rail and 10 either side.
                    dock.style.right = '66px';
                    dock.style.top = '10px';
                    dock.style.left = 'auto';
                    dock.style.bottom = 'auto';
                    dock.style.width = ((byKey[openTool] && byKey[openTool].width) || 320) + 'px';
                    dock.style.height = 'auto';
                    dock.style.maxHeight = capped + 'px';
                    dock.style.border = '1px solid var(--trails-edge)';
                    dock.style.borderRadius = '4px';
                    // **Opposite the dock, because both can stand at once on a
                    // wide screen** — reading a popup with the layer list open is
                    // an ordinary thing to be doing. It takes the left, below the
                    // zoom rather than over it: 10 of margin and 54 of buttons.
                    sheet.style.right = 'auto';
                    sheet.style.left = '10px';
                    sheet.style.top = '76px';
                    sheet.style.bottom = 'auto';
                    sheet.style.width = '352px';
                    sheet.style.height = 'auto';
                    // **Its own ceiling, because it no longer starts at 10.**
                    // The dock's cap is measured from the top of the map; the
                    // sheet begins 66 px lower, below the zoom, and reusing that
                    // number ran it 66 px into the profile panel — seen in a
                    // screenshot, not in a reading.
                    sheet.style.maxHeight = Math.max(40, capped - 66) + 'px';
                    sheet.style.border = '1px solid var(--trails-edge)';
                    sheet.style.borderRight = '1px solid var(--trails-edge)';
                    sheet.style.borderRadius = '4px';
                }
            }

            // **Watched, not waited for.** A rotation is not one resize and it
            // is not two either: the box changes on every frame of the
            // animation and the only reading worth having is the last one. An
            // observer is given exactly that -- it fires for each real change
            // and stops when the box does -- where a timer has to guess how long
            // the animation lasts, and a 350 ms guess was both too short for a
            // slow turn and useless anyway, because what it re-read was
            // Leaflet's cache.
            //
            // It also tells Leaflet, which is the other half. `map.getSize()`
            // is what the map draws itself against, and nothing re-measures it
            // but `invalidateSize()`; left to the single `window` `resize`, a
            // map measured mid-rotation stays that size -- which is the band of
            // unfilled screen at the foot, with everything above it holding a
            // margin from an edge that is not there. Coalesced to one frame the
            // way Leaflet's own handler is, and `debounceMoveend` for the same
            // reason: an animated turn would otherwise fire a `moveend` a frame.
            var pending = null;
            function settled() {
                if (pending) { return; }
                pending = window.requestAnimationFrame(function () {
                    pending = null;
                    map.invalidateSize({debounceMoveend: true});
                    place();
                });
            }

            if (window.ResizeObserver) {
                // Nothing in `place` changes this box -- the chrome and the veil
                // are absolutely positioned inside it -- so this cannot feed
                // itself.
                new ResizeObserver(settled).observe(container);
            } else {
                // No observer: the window's own event, which is what Leaflet
                // listens to, so the layout follows the map's re-measurement
                // rather than racing it.
                window.addEventListener('resize', settled);
                window.addEventListener('orientationchange', settled);
            }
            // Leaflet re-measures for its own reasons as well -- an
            // `invalidateSize` from anywhere else -- and the layout follows
            // every one of them.
            map.on('resize', place);
            // The keyboard opening is not a map resize: the layout viewport does
            // not move, so neither Leaflet nor the observer hears about it.
            if (window.visualViewport) {
                window.visualViewport.addEventListener('resize', place);
                window.visualViewport.addEventListener('scroll', place);
            }

            // **The floor moves, and not only when the window does.** The panel
            // it is measured against is opened by a selection, laid out a
            // moment later, and is then the reader's own to drag taller. Placing
            // once on the selection measured it mid-flight: the detail sheet
            // came out 793 px tall on an 844 px screen against a panel whose top
            // had settled at 471, so the two overlapped by everything. Watching
            // the panel is the honest answer, and it covers the drag for free.
            if (window.ResizeObserver) {
                var watching = new ResizeObserver(function () { place(); });
                var watched = profilePanel();
                if (watched) { watching.observe(watched); }
            }

            // Read by a browser check rather than screenshotted, the way the
            // graph, the panel and the plan are already read.
            window.trailsChrome = {
                narrow: function () { return narrowNow(); },
                // Ask for the coarse layout, or hand it back to the pointer.
                // A check drives this rather than pretending to have a finger:
                // what it is measuring is the geometry, and whether Firefox
                // reports a synthetic touch context as coarse is a different
                // question and not this page's.
                coarse: function (force) {
                    forcedCoarse = (force === undefined || force === null) ? null : !!force;
                    paintCoarse();
                    return container.classList.contains('trails-coarse');
                },
                open: function (key) { pick(key); },
                // The one switch, for everything that offers one: the panel's
                // own lit mark, the rail and the plan control. Called with
                // nothing it flips; called with a boolean it says which way.
                profile: function (want) {
                    if (want === undefined) { return profileOn(); }
                    askProfile(want);
                    return profileOn();
                },
                // Anything else that is to be read rather than glanced at, in
                // the same sheet a popup docks into. The profile panel's
                // licences come through here: on a phone they are eleven lines
                // of the panel, and a sheet is where a page this size puts what
                // a reader has asked to see.
                detail: function (title, node, key) { readInSheet(title, node, false, key); },
                // Closing the sheet alone, which `close()` cannot do: that shuts
                // everything, and everything is not what a second press on one
                // panel's own button means.
                closeDetail: function () { closeSheet(); },
                // **Whether the next tap on the map is a position and nothing
                // else.** Asked by plan mode before it takes a click of its own,
                // set by the rail, by the mark at the foot and from here.
                picking: function (want) { return askPicking(want); },
                // The other switch at the foot, driven the same way.
                here: function (want) { return askHere(want); },
                // What the last tap copied, so a check can read it rather than
                // ask the clipboard -- which a headless browser will not hand
                // over without a permission nobody can grant it.
                copied: function () { return pickSaid; },
                // The panel telling the chrome it has changed shape, so whatever
                // is measured against its top -- a tool, the menu -- is measured
                // against where it actually is.
                placed: function () { place(); },
                menu: function () { openMenu(); },
                close: function () { closeDock(); closeMenu(); closeSheet(); },
                tools: TOOLS.map(function (tool) { return tool.key; }),
                // Told by the profile panel, because a folded panel and an empty
                // one look the same from outside it.
                selected: function (chosen) {
                    selection = chosen;
                    // The empty profile panel says there is nothing to draw. The
                    // moment there is, it is a wrong sentence on the screen.
                    if (chosen && openTool === 'profile') { closeDock(); }
                    // A reader's answer is about the profile and not about one
                    // line, so it stands when the selection goes; what goes with
                    // the selection is the panel itself, which has nothing to
                    // draw.
                    if (!chosen) { closeSheet(); }
                    paintProfile();
                    place();
                    // Which line is chosen is half of what the goal mark aims
                    // at, so choosing one is a reason to work it out again.
                    aimAgain();
                    // And the planned route's own points are drawn while that
                    // route is what is being shown, so this is where they come
                    // and go. Cheap on purpose: it dresses the pins and composes
                    // nothing.
                    if (window.trailsPlan && window.trailsPlan.dress) { window.trailsPlan.dress(); }
                },
                // What plan mode pushes on every refresh, and everything the bar
                // draws. Nothing here asks plan mode anything back.
                planning: function (summary) {
                    var was = planOn();
                    planState = summary;
                    // **Starting or stopping is a new question, so it takes the
                    // default back.** A reader who put the panel away while
                    // planning meant this panel and one who asked for it meant
                    // this route — neither meant *from now on*. And the default
                    // is not the same on both sides of that line: planning on a
                    // narrow screen holds the panel back, because the map is what
                    // is being tapped, and 784 px of it against 462 is what that
                    // rule is worth.
                    if (planOn() !== was) { profileAsked = null; }
                    if (window.trailsProfilePanel && window.trailsProfilePanel.planning) {
                        window.trailsProfilePanel.planning(summary);
                    }
                    paintProfile();
                    paintRail();
                    place();
                    // And so is plan mode: switching it on hands the goal to
                    // the route whatever else was chosen.
                    aimAgain();
                },
                // What the goal control pushes on every change, and what the
                // rail's lamp and the row at the foot draw themselves from.
                // Nothing here asks it anything back -- the same arrangement
                // plan mode's summary is pushed under.
                goal: function (said) {
                    goalNow = said;
                    if (window.trailsProfilePanel && window.trailsProfilePanel.goal) {
                        window.trailsProfilePanel.goal(said);
                    }
                    paintRail();
                    paintQuick();
                    // A goal is the first thing the position mark aims at, so a
                    // goal that has just arrived, moved or gone is a new answer.
                    aimAgain();
                    place();
                },
                // **Where the reader is, as it is drawn** -- which is not always
                // the last fix that arrived, because a sharper one may be being
                // held. Asked by the goal control, which routes from here and
                // must route from the place the map is showing.
                position: function () {
                    if (!hereAt || !hereRing) { return null; }
                    // **The place still stands when the fixes stop**, and says
                    // that it is standing. The goal routes from here and would
                    // otherwise have nothing to route from at exactly the
                    // moment a reader most wants the way there; what it gets is
                    // the last place the device was sure of, with the age of
                    // that certainty beside it.
                    return {lat: hereAt.lat, lon: hereAt.lng, spread: hereRing.getRadius(),
                            stale: !!hereLost, when: hereKept ? hereKept.when : null};
                },
                aiming: function (want, at) { return askAiming(want, at); },
                // What the armed tap will do, for whoever draws a control that
                // armed it: `'goal'`, `'stop'`, `'move'` or nothing -- and for
                // a move, which place in the goal's list it moves.
                aimingFor: function () { return aiming; },
                aimingAt: function () { return aiming === 'move' ? aimingAt : -1; },
                // **Where the mark says to walk, as it was worked out rather
                // than as it is drawn.** A check cannot measure an angle off a
                // canvas and should not have to read a path back to find one --
                // and the two figures that matter here, how wide the fan is and
                // whether the mark is drawn at all, are a decision and not a
                // shape.
                aim: function () {
                    if (!hereGoal) { return null; }
                    return {to: hereGoal.to, left: hereGoal.left, right: hereGoal.right,
                            wide: hereGoal.right - hereGoal.left, away: hereGoal.away,
                            on: hereGoal.on, at: hereGoal.at, target: hereGoal.name || null,
                            goal: hereGoal.goal ? hereGoal.goal.name : null, ms: hereAimMs,
                            walked: hereAimWalked, sampled: hereAimSampled,
                            drawn: !!(hereAim && hereAim.getAttribute('display') !== 'none')};
                },
                state: function () {
                    return {
                        narrow: narrowNow(),
                        tool: openTool,
                        menu: menuOpen,
                        detail: detailShown,
                        detailKey: detailKey,
                        profile: profileShowing(),
                        planning: planOn(),
                        picking: picking,
                        // Armed for the next tap, and whether there is a goal at
                        // all: two states of one switch, and the lamp is lit for
                        // either.
                        aiming: !!aiming,
                        aimingFor: aiming,
                        aimingAt: aiming === 'move' ? aimingAt : -1,
                        goal: goalSet(),
                        here: hereWatch !== null,
                        // Watching and getting nothing, which is a state of the
                        // switch and not the absence of one.
                        lost: hereLost ? hereLost.why : null,
                        lostSaid: hereLost ? lostSaid(hereKept ? hereKept.when : null) : null,
                        planPoints: planState ? planState.points : 0,
                        // The row at the foot, which is the panel's own now:
                        // standing while anything is selected or planned.
                        banner: !!(profilePanel() && profilePanel().style.display !== 'none'),
                        coarse: container.classList.contains('trails-coarse'),
                        threshold: NARROW,
                        // The other half of the rule. A check that worked the
                        // layout out from the width alone would be encoding a
                        // rule this page no longer follows.
                        column: RAIL_ROOM
                    };
                }
            };

            selection = window.trailsProfile || null;
            paintProfile();
            place();
        })();
