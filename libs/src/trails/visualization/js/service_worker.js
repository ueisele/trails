            (function () {
                var map = {{ this._parent.get_name() }};
                var secure = location.protocol === 'https:' ||
                    location.hostname === 'localhost' || location.hostname === '127.0.0.1';
                window.trailsWorker = {kept: false, newer: false, why: null, bytes: null, ask: null};
                // **The origin is asked about before the browser, and that
                // order is the whole of it.** WebKit does not expose
                // `navigator.serviceWorker` at all off a secure origin, so a
                // check that asks about the browser first answers *no worker in
                // this browser* for Safari over http:// -- blaming the browser
                // for what the address bar did, and sending the reader off to
                // look for a browser that would have worked all along.
                // Measured on iOS Safari against http://atlas.cairn.zone.
                if (!secure) {
                    window.trailsWorker.why = 'not a secure origin';
                    return;
                }
                if (!('serviceWorker' in navigator)) {
                    window.trailsWorker.why = 'no worker in this browser';
                    return;
                }
                // **No `registration.update()` after this, on purpose.** It was
                // there for one evening: a browser checks for a newer script on
                // its own only around a navigation, and the thought was that an
                // installed app might not navigate for days. Measured that same
                // evening against a logging server, from the phone the map is
                // read on: Safari fetches the script on *every* `register()`
                // already -- one request a load, a 304 where it sends a validator
                // and the whole file where it does not -- and `update()` on top
                // of it fetched the script a second time on every load,
                // uncoalesced. Firefox folded the two into one. So the eager
                // check cost nothing to leave out and was doubling the one
                // request that was already being made
                // (analysis/docs/abisko-decisions.md §9.30).
                navigator.serviceWorker.register('{{ this.worker }}'{{ this.scope_arg }}).then(function () {
                    window.trailsWorker.kept = true;
                }, function (failure) {
                    window.trailsWorker.why = String(failure);
                });
                navigator.serviceWorker.addEventListener('message', function (event) {
                    var word = (event.data || {}).trails;
                    // The reader pressed Reload and the new page is in the cache
                    // behind them, so this is the reload they asked for.
                    if (word === 'taken') { location.reload(); return; }
                    if (word === 'stuck') { stuck(); return; }
                    if (word === 'checked') {
                        window.trailsWorker.checking = false;
                        if (event.data.newer) {
                            window.trailsWorker.newer = true;
                            window.trailsWorker.bytes = event.data.bytes || null;
                            say();
                        }
                        tellPage(event.data);
                        return;
                    }
                    // `pageFor` still says this on a navigation, and there the
                    // body has already been taken -- so there is no size to
                    // quote and nothing left to fetch.
                    if (word !== 'newer') { return; }
                    window.trailsWorker.newer = true;
                    say();
                });

                // **The panel is where the answer is read**, because that is
                // where the question was asked from and where the map's age is
                // written. The banner only appears when there is something.
                function tellPage(detail) {
                    var event;
                    try {
                        event = new CustomEvent('trails:checked', {detail: detail});
                    } catch (old) {
                        event = document.createEvent('CustomEvent');
                        event.initCustomEvent('trails:checked', false, false, detail);
                    }
                    document.dispatchEvent(event);
                }

                // **Asked for by hand, and by nothing else.** There is no timer
                // behind this and nothing on resume: a HEAD is cheap but a radio
                // woken on every glance at the app is not, and the reader
                // carrying this map is the one furthest from a charger.
                window.trailsWorker.ask = function () {
                    if (!navigator.onLine) { return false; }
                    if (!navigator.serviceWorker.controller) { return false; }
                    window.trailsWorker.checking = true;
                    // **What is on the screen, handed in with the question.**
                    // The worker cannot see it: it holds a cache, and the cache
                    // is refreshed behind whatever answer it served, so a
                    // comparison made there is about a page nobody is looking
                    // at. `document.lastModified` is this page's own — measured
                    // through the worker, where it still carries the published
                    // `Last-Modified` and not the time it was drawn.
                    navigator.serviceWorker.controller.postMessage(
                        {trails: 'check', mark: Date.parse(document.lastModified) || null});
                    return true;
                };

                function stuck() {
                    var line = document.querySelector('.trails-newer');
                    if (!line) { return; }
                    var again = line.querySelector('.trails-newer-reload');
                    if (again) { again.disabled = false; again.textContent = 'Try again'; }
                    var told = line.querySelector('.trails-newer-said');
                    if (told) { told.textContent = 'It could not be fetched — no connection.'; }
                }

                function say() {
                    if (document.querySelector('.trails-newer')) { return; }
                    var line = document.createElement('div');
                    line.className = 'trails-newer';
                    // **The one thing this page draws outside the chrome**, and
                    // therefore the one the inset on that box does not reach.
                    // With `viewport-fit=cover` `top: 10px` is the physical top
                    // edge, so this landed under the camera and the button could
                    // not be tapped -- reported from the device, and it is the
                    // worst place for it to happen: this is the button that takes
                    // the next version, so a reader who cannot press it cannot
                    // reach the fix for it either.
                    //
                    // `calc` rather than moving it into the chrome, because a map
                    // built without `add_chrome` still has a worker and still
                    // needs to say this.
                    line.style.cssText = 'position:absolute;left:50%;transform:translateX(-50%);' +
                        'top:calc(10px + env(safe-area-inset-top));' +
                        'z-index:1100;display:flex;gap:10px;align-items:center;padding:6px 10px;font-size:12px;' +
                        'border:1px solid var(--trails-rule);border-radius:8px;background:var(--trails-panel);' +
                        'color:var(--trails-ink-2);box-shadow:0 1px 6px rgba(0,0,0,0.2)';
                    var said = document.createElement('span');
                    said.className = 'trails-newer-said';
                    // **The size, when the HEAD came back with one.** It is what
                    // the button is about to spend, and a reader on a phone in a
                    // valley is entitled to see it before pressing.
                    //
                    // Usually it did not: Cloudflare drops `content-length` on a
                    // compressed answer, measured against the published page, so
                    // in production this is the short line. Kept because it is
                    // three lines that degrade into the sentence below, and
                    // because guessing a figure would be worse than omitting
                    // one.
                    said.textContent = window.trailsWorker.bytes
                        ? 'A newer map is ready · ' +
                          (window.trailsWorker.bytes / 1e6).toFixed(1) + ' MB.'
                        : 'A newer map is ready.';
                    // **A button, because there may be no other way to reload.**
                    // Installed to a home screen there is no address bar and no
                    // reload control, so *reload to see it* was an instruction
                    // the reader could not carry out. The tiles are not touched
                    // by it: the terrain cache carries no version and the worker
                    // sweeps only `trails-page-` on activate.
                    var again = document.createElement('button');
                    again.type = 'button';
                    again.className = 'trails-newer-reload';
                    again.textContent = 'Reload';
                    again.style.cssText = 'font:inherit;font-size:12px;font-weight:600;padding:4px 10px;' +
                        'border-radius:6px;border:1px solid var(--trails-strong);background:var(--trails-strong);' +
                        'color:var(--trails-on-strong);cursor:pointer';
                    // **The body is fetched here and nowhere else.** Looking
                    // costs a HEAD; this is the tap that pays for the map, and
                    // the worker reloads the page once it is in the cache. The
                    // tiles are not touched by it: the terrain cache carries no
                    // version and the worker sweeps only `trails-page-`.
                    again.addEventListener('click', function () {
                        if (!navigator.serviceWorker.controller) { location.reload(); return; }
                        again.disabled = true;
                        again.textContent = 'Fetching…';
                        navigator.serviceWorker.controller.postMessage({trails: 'take'});
                    });
                    var shut = document.createElement('button');
                    shut.type = 'button';
                    shut.className = 'trails-newer-close';
                    shut.textContent = '×';
                    shut.setAttribute('aria-label', 'Leave it for now');
                    shut.style.cssText = 'font:inherit;font-size:15px;line-height:1;padding:0 4px;border:0;' +
                        'background:none;color:var(--trails-ink-3);cursor:pointer';
                    shut.addEventListener('click', function () { line.remove(); });
                    line.appendChild(said);
                    line.appendChild(again);
                    line.appendChild(shut);
                    // **Into the chrome where there is one.** The `calc` above
                    // is the same arithmetic the overlay does, and it went out
                    // once and was reported still under the camera -- so rather
                    // than argue about why, this hangs the line inside the box
                    // whose inset is *visibly* working: the one the menu and the
                    // panels sit in. The `calc` stays for a map built without
                    // `add_chrome`, where there is no such box and a worker still
                    // has to be able to say this.
                    var into = map.getContainer().querySelector('.trails-chrome');
                    if (into) { line.style.top = '10px'; line.style.pointerEvents = 'auto'; }
                    (into || map.getContainer()).appendChild(line);
                }

                // **Nothing asks on the way back in, and that is deliberate.**
                // This did: a HEAD on `visibilitychange`, ten minutes apart, and
                // the body fetched behind it whenever the answer was yes. Two
                // things were wrong with it on a walk. The body is 5.2 MB spent
                // by a rule nobody invoked, over whatever connection happens to
                // be attached -- the exact thing the offline switch exists to
                // prevent. And the HEAD itself wakes the radio every time the
                // app is glanced at, which is the expensive act on a phone that
                // is days from a charger.
                //
                // What replaced it is in the offline panel: it says how old this
                // map is, and it has a button that asks. Being out of date is
                // visible rather than silent, acting on it is one tap, and the
                // page in the foreground makes no requests at all -- which is a
                // claim the driven suite can measure.
            })();
