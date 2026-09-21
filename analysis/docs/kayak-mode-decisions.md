# The kayak mode: what has been decided, what is open, and what changed

*Opened 2026-09-21. The plan that produced it is `kayak-mode-phases.md`; once a phase lands,
its built-note goes under §5 here, and this file is the record — the plan is not.*

## 1. The decision in one paragraph

A third way of planning beside walking and staying on paths, where the water is the way and
the land is the portage. Asked for by Uwe on 2026-09-20, taken up on 2026-09-21 after the
Malingsbo-Kloten map was called done, and decided the same day as the plan's §1 proposed: one
price rule (shore 1, open water k, land P times the walking price, a path P alone), the
narrow rivers as class-2 lines downstream only and cut at dams, k and P measured by a sweep,
the canoe trails researched before anything named is added; in `trails`, with the water
network in `libs`; the profile over water read off the height tiles, where a lake is a plane;
on all three maps.

## 2. Decided

The plan's §1, in full. What was Uwe's rule is quoted there; what was a proposal beside it
(the portage chords between neighbouring pieces of water, the tiles as the source of a lake's
level, all three maps) is settled with it and is not reopened without his word.

## 3. What was measured

The plan's §3: the water of the Malingsbo-Kloten box (1,332 lakes and 108 river surfaces,
31,987 ha, 2,701 km of shoreline), the lines the page lacks (6,709 `Vattendrag`, 118 km of
them class 2; 97 dam points, 11 lock gates, 2,121 flow arrows), how the water hangs together
(1,190 bodies by touch, 433 systems with the lines, the largest 754 surfaces over the whole
box), and OSM's silence on canoe trails (0 relations, 0 portages, 6 slipways). Measured
2026-09-21, scratch in `~/mockups/kayak-mode/`.

### 3.5 Where the canoe trails are

*Phase R writes this.*

## 4. Open

- **The flow's direction** in Topografi 50's lines — phase 1's first measurement.
- **k and P** — phase 2's sweep; 1.5 and 4 until then.
- **Whether N50's river lines carry a size class** — phase 1, for Norway's streams.
- **Whether anybody publishes the canoe trails as lines** — phase R.

## 5. Changes

- 2026-09-21 — phase 0: the plan and this record opened.

## 6. How the figures here were obtained

Scratch in `~/mockups/kayak-mode/`: `measure-water.py` reads the water surfaces through
`topografi50.Source.water` and the `hydrolinje` layer of the cached `hydrografi` GeoPackage
by box, counts them, simplifies the outlines at 5, 10 and 25 m, and joins them into bodies
and systems with an STRtree; `measure-water-2.py` the shoreline length, the size classes and
the largest lakes; `canoe-osm.py` the Overpass query and `canoe-osm.json` its answer. Run
from the `trails` checkout with `mise exec -- uv run python <script>`.
