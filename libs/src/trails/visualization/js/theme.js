        // **In the head, and stamped before the first paint.** The choice is
        // read and applied here rather than when the chrome is built, because
        // anything later means the page is painted once in the wrong set and
        // corrected in front of the reader -- a white flash on a phone held at
        // dusk, which is the exact moment this feature exists for.
        (function () {
            var KEY = 'trails:theme';
            var root = document.documentElement;
            var media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

            function kept() {
                // Storage can be denied outright -- Safari in private browsing
                // throws on read, not only on write -- and a page that cannot
                // remember a choice must still honour the machine's.
                try {
                    var got = window.localStorage.getItem(KEY);
                    return got === 'light' || got === 'dark' ? got : 'auto';
                } catch (blocked) { return 'auto'; }
            }

            var choice = kept();

            // **Auto removes the stamp rather than writing one.** The three CSS
            // blocks above are built on that: no stamp lets
            // `prefers-color-scheme` decide, and a stamp has to beat it in both
            // directions. Writing `data-theme="auto"` would match neither the
            // light block nor the dark one and leave a reader in whichever set
            // came first.
            function stamp() {
                if (choice === 'auto') { root.removeAttribute('data-theme'); }
                else { root.setAttribute('data-theme', choice); }
            }

            function dark() {
                return choice === 'auto' ? !!(media && media.matches) : choice === 'dark';
            }

            // Everything drawn through CSS follows the stamp on its own. What
            // cannot is anything painted with attributes read at stroke time --
            // the elevation curve is the one on this page -- so the change is
            // announced and those redraw themselves.
            function tell() {
                var said = {choice: choice, dark: dark()};
                var event;
                try {
                    event = new CustomEvent('trails:theme', {detail: said});
                } catch (old) {
                    event = document.createEvent('CustomEvent');
                    event.initCustomEvent('trails:theme', false, false, said);
                }
                document.dispatchEvent(event);
            }

            stamp();

            // **The first of three marks, and the earliest one this page can
            // take.** An installed app on a phone reported ten to twenty seconds
            // to open where every check in this project measures 1.8 s -- and
            // every one of those checks is Firefox on Linux. Rather than guess
            // across that gap, the page keeps its own account of what opening it
            // cost and the Sources panel reads it out. This macro is in the head,
            // so it runs before the body exists.
            window.trailsOpened = {head: performance.now()};

            window.trailsTheme = {
                choices: ['auto', 'light', 'dark'],
                choice: function () { return choice; },
                dark: dark,
                set: function (want) {
                    if (want !== 'auto' && want !== 'light' && want !== 'dark') { return; }
                    if (want === choice) { return; }
                    choice = want;
                    stamp();
                    try {
                        // The default is *absence*, so auto clears the key
                        // instead of writing the word. A reader who has never
                        // chosen and a reader who has chosen auto want the same
                        // thing, and one of them should not be carrying a
                        // setting about it.
                        if (want === 'auto') { window.localStorage.removeItem(KEY); }
                        else { window.localStorage.setItem(KEY, want); }
                    } catch (blocked) { /* the choice still holds for this visit */ }
                    tell();
                }
            };

            // On auto the machine is still the one deciding, so its change is
            // this page's change too.
            if (media && media.addEventListener) {
                media.addEventListener('change', function () { if (choice === 'auto') { tell(); } });
            }
        })();
