        window.trailsPopup = (function () {
            var MARKUP = /[&<>"']/g;
            var AS = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#x27;'};
            function esc(text) { return String(text).replace(MARKUP, function (c) { return AS[c]; }); }

            return function (shape, values) {
                var rows = [];
                var at = 0;
                var i;
                for (i = 0; i < shape.labels.length; i++, at++) {
                    if (values[at] === null || values[at] === undefined) { continue; }
                    rows.push("<tr><td style='padding:2px 8px 2px 0;color:var(--trails-ink-3)'>" + esc(shape.labels[i])
                        + "</td><td style='padding:2px 0'><b>" + esc(values[at]) + "</b></td></tr>");
                }
                // Above the first thing under it that survives, not above the
                // block: a route with no description on the park's site would
                // otherwise get a heading over nothing at all.
                var written = 0;
                function heading() {
                    if (shape.heading && !written) {
                        rows.push("<tr><td colspan='2' style='padding:7px 0 1px;color:var(--trails-ink-4)'>"
                            + esc(shape.heading) + "</td></tr>");
                    }
                    written += 1;
                }
                // **What somebody else states about this line, under their own
                // heading.** These read exactly like the rows above them and are
                // not the same kind of thing at all: a route's own site saying
                // *23,4 km, 2 d, +1088 m* stood in the middle of figures this map
                // had measured, where it looked like one of them disagreeing
                // with the rest by a kilometre.
                var stated = shape.published || [];
                for (i = 0; i < stated.length; i++, at++) {
                    if (values[at] === null || values[at] === undefined) { continue; }
                    heading();
                    rows.push("<tr><td style='padding:2px 8px 2px 0;color:var(--trails-ink-3)'>" + esc(stated[i])
                        + "</td><td style='padding:2px 0'><b>" + esc(values[at]) + "</b></td></tr>");
                }
                // noopener keeps the opened page from reaching back into this one.
                function link(url, text) {
                    rows.push("<tr><td colspan='2' style='padding:3px 0'><a href=\"" + esc(url)
                        + "\" target=\"_blank\" rel=\"noopener noreferrer\">" + esc(text) + "</a></td></tr>");
                }
                for (i = 0; i < shape.links.length; i++, at++) {
                    if (values[at] === null || values[at] === undefined) { continue; }
                    heading();
                    // One URL under the column's text -- or, for a line that
                    // several pages describe, a list of [text, url] pairs, each
                    // a link of its own.
                    if (Array.isArray(values[at])) {
                        values[at].forEach(function (pair) { link(pair[1], pair[0]); });
                    } else {
                        link(values[at], shape.links[i]);
                    }
                }
                // Set off by a rule, so it reads as provenance rather than as
                // another attribute of the feature.
                if (shape.source) {
                    rows.push("<tr><td colspan='2' style='padding:5px 0 0;border-top:1px solid var(--trails-rule);"
                        + "color:var(--trails-ink-4)'>Source: " + esc(shape.source) + "</td></tr>");
                }
                if (!rows.length) { return null; }
                return "<table style='font-family:sans-serif;font-size:12px'>" + rows.join('') + "</table>";
            };
        })();
