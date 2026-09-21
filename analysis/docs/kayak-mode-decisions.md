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

### 3.5 Where the canoe trails are — phase R, 2026-09-21

**Nobody publishes the canoe trails of this box as lines.** Searched: Naturkartan (its
search page answers 403 to a script; its entries found by web search), the three county
boards' pages for Malingsbo-Kloten (Dalarna, Västmanland, Örebro), Sveaskog's ecopark page
and its plan, Ljusnarsberg's and Lindesberg's visitor pages, Nordic Discovery (the canoe
centre at Kloten), opencanoe.se, and Naturvårdsverket's own register — the one open source
that has a canoe trail type at all.

| who | what they publish | lines | terms |
|---|---|---|---|
| Naturvårdsverket, *Leder* (`Leder_shp.zip`) | trail type `Kanotled` exists nationally; **0 in the box** (98 trails: 85 `Vandringsled`, 12 `Naturstig`, 1 both) | — | open data |
| Naturvårdsverket, *Anordningar* | 129 facilities in the box: 6 `Vindskydd`, 6 `Eldstad`, 6 `Rastplats`, 3 `Bro`, 30 car parks, 77 information boards, 1 wood store; named for their lakes (*Vindskydd Sågsjön*, *Rastplats med vindskydd vid Håvtjärnen*), none typed as a landing or a canoe rest place (`Kajakramp`, `Brygga` exist in the table, none here) | points, on the map already | open data |
| Nordic Discovery, Kloten | *Norra kanotleden* 50 km, *Södra kanotleden* 20 km, 70 km together, "plus 30 km in Malingsbo"; rest places with shelters and fire pits along them; an overview map as a raster PDF (`media.nordicdiscovery.se/2019/10/översiktskarta-2019-10-12.pdf`, 6 MB, one page) and a 1:50,000 waterproof map for rent | none; the PDF is a drawing, © Mikael Nilsson / Nordic Discovery | all rights reserved |
| Naturkartan | one entry, *Malingsbosjön paddling* (Smedjebacken kommun): a place with a kayak jetty, a rest place and a bathing place; no route, no GPX | — | Naturkartan's terms |
| Länsstyrelsen Dalarna / Västmanland / Örebro | "you can hike, paddle and fish"; the reservatskartan web map per county; nothing on the canoe trails | — | — |
| Sveaskog, Ekopark Malingsbo | "canoe waters"; the ecopark plan is a scanned PDF | — | — |
| opencanoe.se (Curt Svensson, 2008) | Hedströmmen, Gåsmossen to Skinnskatteberg, ~27 km, three portages, easy rapids, an embedded Google map | none | © 2008 |
| OSM | plan §3.3: nothing | — | ODbL |

**What follows.** There is no phase 6: no source offers a line under terms the map could
carry, and the register's canoe trail type, which would have been the Bergslagsleden of the
water, is empty here. What the map will have instead is the water network of phase 1 —
every shore, every crossing, the class-2 rivers — which is the whole of what a canoe trail
drawing adds, minus the drawing's choice of a line; and the register's shelters and fire
places, which are the canoe trails' rest places and are on the map already as facilities.
Nordic Discovery's names, *Norra* and *Södra kanotleden*, are a company's names for its
rentals' routes and are not carried. Should the county boards ever register a `Kanotled`
here, `naturvardsregistret.trail_type_label` already knows the word and the *Leder* layer
would draw it without a change.

## 4. Open

- **The flow's direction** in Topografi 50's lines — phase 1's first measurement.
- **k and P** — phase 2's sweep; 1.5 and 4 until then.
- **Whether N50's river lines carry a size class** — phase 1, for Norway's streams.
- ~~Whether anybody publishes the canoe trails as lines~~ — phase R, 2026-09-21: nobody (§3.5).

## 5. Changes

- 2026-09-21 — phase 0: the plan and this record opened.
- 2026-09-21 — phase R: the research in §3.5; there is no phase 6.

## 6. How the figures here were obtained

Scratch in `~/mockups/kayak-mode/`: `measure-water.py` reads the water surfaces through
`topografi50.Source.water` and the `hydrolinje` layer of the cached `hydrografi` GeoPackage
by box, counts them, simplifies the outlines at 5, 10 and 25 m, and joins them into bodies
and systems with an STRtree; `measure-water-2.py` the shoreline length, the size classes and
the largest lakes; `canoe-osm.py` the Overpass query and `canoe-osm.json` its answer; `register-canoe.py` the register's trails by type and its facilities by type and subtype over the box, through `naturvardsregistret.Source`; the overview map PDF beside them. Run
from the `trails` checkout with `mise exec -- uv run python <script>`.
