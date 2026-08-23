# Route planning: notes for reviewing the phases

Working notes, not specification. The specification is
`route-planning-decisions.md` and `route-planning-phases.md`. This holds what a
reviewer needs that those two deliberately leave out: how the numbers in them
were arrived at, what this codebase does that will bite an implementation, and
what to look at in each phase.

## Where things stand

**Phases 1, 1B, 1C, 1D, 3, 2, 3B, 4, 5, 6, 6B, 6C and 7 are built and
reviewed.** The map is drawn from the graph, carries it, profiles it, exports it,
and plans a route on it that can be worked on and becomes a file saying which
protected areas it passes and how far through each.
`libs/src/trails/routing/`, `libs/src/trails/network/`,
`visualization/encoding.py`, `io/export/gpx.py`, `routing/track.py`,
`analysis/scripts/route_graph.py` and `lomsdal_visten.py`.
**All eight are built and checked.** The project runs on
**Python 3.14** and `uv.lock` is tracked from 1D.

**Phase 7** makes a route something to work on: insert into the middle, remove,
move a point earlier or later, and drag. It is all in `_PlanMode` and touched no
Python outside it. **Two acceptance figures moved by design and a third with
them** — the plan pane 13 → 8 paths, the marker pane 198 → 203, and
`.leaflet-marker-icon` 0 → 5 — because a waypoint that can be dragged is an
`L.marker` and not an `L.circleMarker`. Figures in *What phase 7 found*.

**Phase 6C** added the third thing an edge says about the ground it runs over:
`routing/protection.py`, `naturbase.Source.within`, a section of its own in the
payload, and the boundaries themselves in the page. It is the first phase since
2 to touch the graph — `GRAPH_LAYOUT` is `elevation+coverage+protection`,
`PAYLOAD_VERSION` is 3 — and the rebuild moved no figure and made no height
request. Figures in *What phase 6C found*.

**When an agent is working here the standing rule applies** — **documents only,
no code, no `git commit`**, because the pre-commit hook stashes unstaged changes
and would pull work out from under it. Check `git status` first.

**And launch that agent in a memory cage.** Phase 6's first session took 42 GiB
and the kernel's OOM killer ended it; the rule and the incident are in the trap
list, and the cage is under *The prompt that has worked*.

**Committing needs the user.** Commits are GPG-signed and the passphrase prompt
opens on their terminal, not here; it times out unsuccessfully more often than
not. Write the message to a file under the scratchpad, try once, and if it times
out say so and offer the `! git commit -F <path>` line rather than retrying
blindly.

The order these were done in is not the order they are numbered, and that was
deliberate: 1C → 1D → **3** → 2 → 3B → 4. Phase 3 went before 2 because its
acceptance is *the map behaves as it did* and 1C and 1D had just measured that in
a browser; a fresh baseline is perishable and phase 2's API wait is not. 3B waited
for 2 because two fifths of its payload is elevation.

**Phase 3B** put the graph in the page: `routing/order.py`,
`visualization/encoding.py`, a hand-written decoder in `maps.py` and
`edge_costs` in `norway.py`. **4.12 MB** in the page, later 4.93,
inflating in 0.34 s and reading into arrays in 75 ms, arriving as
`window.trailsGraph` and read by nothing yet. Every browser figure held and the
graph did not move. What it cost against the estimate, and the two findings the
review left, are in *What 3B found* below.

**And then the two fields it had left out**, on the same day and by decision
rather than by review: `waymarked` and `no_path_recorded` now travel in the
payload, are summed per chain by `routing/coverage.py`, and are shown in the
popup of every walked line layer. Nothing was recomputed for the payload; the
popup cost a `GRAPH_LAYOUT` bump and two offline minutes. Figures in *What 3B
found*.

**Phase 4** drew the profile panel: hand-written inline SVG, one path, two axes
and a crosshair, in a Leaflet control that folds itself away whenever nothing is
selected. The four figures and the compass point reach it as a table keyed by
each line's `trail-group-<chain_id>` class — the mechanism the search box
already used, and not the GeoJSON properties three drafts had assumed. The popup
gained *Ascent / descent* and *High point*, and the arrow lives in a pane of its
own so it is not counted among the map's paths. The curve is then **coloured by
gradient** — gentle under 15 %, steep, very steep, extreme over 40 %, read over
a 25 m window — added on request afterwards. What the review found is in *What
phase 4 found* below, and the bands in *What the gradient bands cost*.

**Phase 5** exports a selected chain: `routing/track.py` composes the dense
height-carrying line, `io/export/gpx.py` gained `<ele>`, `<extensions>` and a
`<metadata>` source list with no `<copyright>`, and the browser writes the same
file from the same walk. The page gained every source's licence and version, and
`name`, `source` and `noPath` per chain. Its review moved the payload's height
quantum from a decimetre to the **centimetre the service actually answers at**,
so that a downloaded file reproduces the ascent it states — see *What phase 5's
review found*.

**Phase 6** put plan mode in the page: clicking a route together out of all four
leg kinds, a Dijkstra over the carried graph, undo, and the route's own profile.
The route is drawn into a pane of its own, so the page's **11,589** paths do not
move. Its review is in *What phase 6's review found* — everything reproduced, and
the finding that came out of it lands on phase 5 rather than on 6.

**Phase 6B** makes that route a file. `composeRoute` now lays coordinates beside
the heights in one pass rather than in a second walk; both writers learned
`<wpt>`, before the track and carrying `origin`; each leg's mode travels on the
track as `<trails:legs>`, because four routed legs are one segment; and a
crossing is written as the gap it is, since GPX cannot say a segment is a boat.
Its review is in *What phase 6B's review found* — everything reproduced, and the
one finding was that a correction had landed in the decisions document and not
in the phase.

**And the popups now say whose GPX they offer.** *Download GPX* stood 36 times in
the page and meant two things; it stands once. Measured on the 42 km Rundtur, the
two files disagree by 262 m of ascent and one of them carries a timestamp on
every point.

**And the popup rows cost 175 times what the payload does, again.** 3B measured
that once — the two coverage rows were 1.57 MB of popup HTML against 0.009 in the
payload — and the steepness rows repeat it to the decimal: the payload is
**unchanged at 4.93 MB**, and the page went **37.7 to 39.4 MB**, of which about
1.4 is 11,064 popups each gaining thirty-one characters. Popup text is written
out per feature and compresses against nothing. **Showing a figure is the
expensive half; carrying it is nearly free.** Neither budget is threatened, and
the ratio is the thing to remember before adding the next row.

**And a highlighted line could not be let go of while planning.** The
click-highlight has exactly two ways out — a click on the line, and a click on
empty ground — and plan mode owns both from the moment it is switched on.
Measured against the built page with the clearing taken back out: pick a chain
and it goes from 4 px at 0.85 opacity to **8 px at 1.0**; switch plan mode on and
it stays there, with all eleven thousand other lines dimmed behind the route
being planned and nothing a reader can do about it. Plan mode now lets go of it
on the way in, and it is not restored on the way out — it was a selection made by
clicking, and planning is what gives it up.

The highlight gained a way in that is not a click, `window.trailsHighlight` with
`clear()` and `selected()`, the way the graph and the panel's selection are
already readable. **The general form is the same as the popup below it**: a
behaviour whose only exits are clicks is at the mercy of whatever else claims
clicks, and this map now has something that claims all of them.

**And a click inside a popup was a click on the ground.** Plan mode takes every
click in the capture phase on the map container — that is how one handler tells a
pin from the route from open terrain — and it stepped around
`.leaflet-control-container`. **A popup is not in there.** It lives in a pane
inside the map, so every click in one fell through: measured against the built
page with the old selector, clicking a chain's popup text placed a waypoint
(1 to 2), clicking its close button placed another (2 to 3) **and left the popup
open**, because the dispatcher's own `stopPropagation` meant Leaflet's closer
never ran. With `.leaflet-popup` named alongside the controls, both place nothing
and the button closes; a click on terrain still places. It had been there since
phase 7 and no check had ever clicked a popup while planning.

The general shape is worth keeping: **a handler that owns every click has to
enumerate everything that is not terrain**, and Leaflet's furniture is not all in
one container. What is in the map's own panes and is not ground: popups, and
nothing else today — tooltips take no pointer events.

**And the legend is the layer control.** They were two panels over nearly one
list: of the legend's 30 rows, **23 named a layer the control also listed**, one
named the same layer under a second name, and six were kinds inside a single
layer. Measured, they cost a 297 x 557 box and a 441 x 737 one; the merged panel
is **480 x 687** and folium's `LayerControl` is gone. Every row now switches its
own layer, a row whose layer is off is greyed rather than hidden — it is still
the key to that colour, it is just not speaking for the terrain — and the six
name kinds became **six layers**, so a planner can put the mountains on the map
without the marshes.

**What had to come with it is the part that control did quietly.** A folium layer
added with `show=False` is on the map like any other; it is `LayerControl`'s own
template that takes it off again. Remove the control and this map's two switched-
off layers arrive switched on, and so does the second base map — measured after
the fix, **one tile layer on the map** and the right one. The legend does that job
now, off the `show` each layer carries.

**And it settled a two-named layer.** The park boundary was *Park boundary
[Naturbase]* in the legend and *National park boundary [Naturbase]* in the
control. Nothing noticed for as long as the two lists were never compared. The
merged panel looks its layers up by the name they carry and **raises** where a row
finds none, so the next drift is a traceback rather than a row that switches
nothing.

Driven: the panel's 30 rows all switch, 7 start off — the six name kinds and the
farms — toggling *Paths in park [FKB] (53)* takes the map from **11,589 paths to
11,536 and back**, and toggling the mountain names on takes the marker pane from
**198 to 431**, both exactly the counts their labels state.

**And the crosshair marks the ground it is reading.** A dot on the map,
wherever the pointer stands on the curve, for a chain and for a planned route
alike — asked for because a profile is far easier to plan against when the climb
in the panel and the climb on the map are visibly the same climb. It takes the
direction arrow's pane, so the path count stays **11,589**, and the crosshair's
own colour, because the two are one thing shown in two places. It is taken back
when the pointer leaves, when the curve is redrawn under it and when a drag
starts: a dot outliving its reading claims a position nobody is pointing at.

**The position is not the sample's index**, and that is the whole of the work. A
series carries two axes of different lengths — heights every 5 m, and the line
through the vertices somebody surveyed — and the only thing they share is a
distance. Measured, on the 42 km chain: **2,123 vertices against 8,191 samples**;
on a planned route, 2,340 against 3,688. So the mark is found by walking the
vertices' own `along` axis, which was measured to be strictly non-decreasing on
both and to end exactly on `total` — that is what makes the binary search
admissible, and a binary search over an axis that went backwards would be
silently wrong rather than loudly. The arrow's midpoint now asks the same walk
instead of keeping a second one.

Measured against an independent projection of the mark back onto the line, at
about 4 m to the pixel: it lies **0.09 to 1.35 m** off the drawn line and **1.15
to 6.56 m** from the distance the panel names, against a reading rounded to 10 m.

**And one 1,519 m disagreement that was the probe's.** Projecting the mark onto
the line and taking the nearest point is not a way to check a mark on a round
trip: at the 21.19 km reading the line passes the same spot twice — 19.63 to
19.69 km and 21.17 to 21.22 km, both 7.5 m away — and the projection picked the
other pass. The mark was 3.22 m from where it belonged. **A nearest-point search
answers "where is the line closest" and not "where is the walker", and on an
out-and-back those are different questions.**

**And the row with the download button reads as one sentence.** Its three parts —
the button, how many points the file holds, and which sources it draws on with
their licences — were flex items, so the licences either fitted beside the count
or moved to a line of their own. A chain's list fitted and a route's did not,
which is why the two looked like different panels for the same job. Measured on a
route over two sources at 620 px, the list now begins on the count's own line and
runs to three. What the file covers — the marking buckets and the ground no
source records a path along — is deliberately still a line of its own: run
together with the licences it reads as one longer list of sources.

**And the profile's height is a reader's to drag**, which on a steep chain is
resolution rather than taste. The scale is the coarser of length-per-width and
relief-per-height, so where the height binds every pixel given is a finer scale.
Measured on the 3 km path off Øyfjellet: the chart at 205 px draws it 638 px
wide at 4.73 m/px, dragged to 445 px it draws **1,170 px wide at 2.58 m/px** —
past one reading a pixel — and the drawn ratio holds at 3.74 against the ground's
3.74 the whole way. Dragged to the floor of 60 px it is 96 px wide at 31 m/px,
and still true. On a long gentle route the width binds and dragging changes the
size and nothing else, which is honest: there is no detail there to uncover.

The drag is coalesced to one draw a frame rather than one a mouse move — 60
pulls in 998 ms, no error — the panel is bounded at 60 px and at the map's own
height less 80, and the map does not pan under it: centre and zoom identical
before and after. **A control that grows over the map has to be measured against
the map**, and this one leaves 80 px of it at full stretch.

**And the curve can be zoomed into, where there is anything to see.** That
proviso is the whole finding. Measured over the built graph, the median chain is
drawn at **0.16 m/px** against a series carrying a height every **5.12 m**, so
the panel already magnifies every reading it holds some thirty times, and only
**126 chains of 11,264** — 1,210 km of 5,853 — are drawn coarser than their own
samples. Zoom belongs to the long chain and to a planned route; on the other
99 % the wheel goes to the map as it always has, and the map's own 9 → 11 is
unmoved. The ceiling is the data's rather than a taste — one reading per pixel,
**6.31×** on the 42 km Rundtur in a 1,400 px window — and it is not a constant,
because it is the drawn scale over the reading spacing and the drawn scale moves
with the panel's width and height. The scale stays true in both axes at every step, and
not approximately: **both carry the same metres per pixel to six decimals** at
zoom 1, 2, 4, the ceiling and the panel's 60 px floor, so the drawn gradient is
the ground's on all of them. Dragging moves the
window, a double click puts the whole chain back, a new selection starts over.
The page did not move — **39.4 MB, the payload untouched at 4.93 MB**. A
behaviour is written once, which is why it is free where a popup row is not.

**And two defects in the grip that shipped yesterday**, both found by driving it
rather than by reading it, and both the same shape: the ceiling was measured as
the panel's height less the chart's, taken at the moment of the call. A redraw is
coalesced to the next frame, so two mouse moves inside one frame measure a fresh
chart against a stale box — the second read an overhead of **minus 620**, a
ceiling of **1,440**, and handed out a panel taller than the map. That is not a
corner: **Firefox reports `clientY` as −86 the moment the pointer leaves the foot
of the window**, so a drag running off the bottom delivers three of them at once,
and the panel opened at 900 px on a 900 px map. Folded, the same arithmetic reads
35 px of box against a 205 px chart — an overhead of minus 170, a ceiling of 990
— and a click on the map folds the panel, which a click can do in the middle of a
drag: measured, that reopened it at 705 px. Both are closed. The overhead is now
measured against the height the panel was **laid out** with, and the grip does
nothing while the panel is folded.

**And a chain's popup says the steepest ground it covers**, over 25 m and over
100 m, absolute. Absolute because this park's steepest chain climbs 9 m and drops
816, so a signed maximum would call it flat; two windows because one invites the
confusion the row exists to end — on that chain the steepest 25 m is 72 % and it
is **ten metres long**, the steepest 100 m is 62 %, and the whole descent
averages 27 %. The gradient rule moved to `routing/elevation.py` and `maps.py`
imports it, so the panel's colours and the popup's figure cannot drift apart.
Cost: a distance axis for a chain's series, which Python did not have, a new
`GRAPH_LAYOUT` and a rebuild that asked the height service nothing.

**Two things it turned up, and both are corrections to this documentation.**
It was written that over the 25 m window nothing exceeds 100 %; measured across
all 11,290 chains, **21 do and the worst reads 231 %** — an N50 road climbing
65 m over thirty metres of ground, steadily, over six consecutive samples. The
window tames the sampling, not the terrain.

And **the popup and the crosshair can differ by one per cent, for a reason worth
keeping.** Python spaces a chain's samples by the **arc length** of each edge;
the page sums the **chords** between the sample points, and a chord cuts the
corner of a bend. Measured on that chain the two axes run to the same total,
3,017.10 m, and differ by at most **0.128 m** along the way — enough to read
72.4640 % against 72.5631 % and land either side of a rounded 72.5. Scaling the
page's distances to the carried total fixes the total and not the distribution,
which this document already says about a different figure. **Where two
measurements of one thing straddle a rounding boundary, the boundary is the
finding, not the disagreement.**

**And the profile is now true to scale**, after a reader asked how a curve that
looks gentle can read −73 %. It could: the chain drops 808 m to 1 m over 3.0 km,
a quarter of it over 40 %, and the crosshair was right. The *picture* was not —
each axis was fitted to its own range, so the vertical ran 2.2 times coarser than
the horizontal on that chain and 7.5 times on the 42 km one, and a 36° descent
drew as 18°. One metres-per-pixel now serves both axes. Verified by comparing the
drawn bounding box against the ground: **within 0.2 %** on three chains, which is
the stroke's own half-pixel. A steep chain leaves width unused — 433 px of 1,238
— and the crosshair is hidden out there, because there is no ground to report.

**Phase 2** added `io/sources/hoydedata.py` and `routing/elevation.py`, a series
on every walked edge with its ascent and descent, and four figures on every
chain. 20,183 requests in 13.6 minutes, none at all on a second build or on a
forced `--rebuild`, and not one figure of the graph moved — checked against the
cached pre-phase-2 graph down to the geometry hash, the chain ids, the total
length to six decimals and the total cost. The one thing that did not come out
is the documented 996 m; that is in *What phase 2 found* below and the decisions
document now carries both columns.

**Phase 3** drew the map from the chains and removed the source flags. Every
browser figure held — 198 markers, one non-interactive path, 25 layers, search at
10 px above the zoom at 60, wheel 9 → 11 — and the path count fell 12,357 →
11,589, which is 11,290 chains plus 298 circle markers plus the boundary. It
found that `Ukjent` was being read as a name and deliberately did not fix it,
because that moves the count it was accepted against; the fix came immediately
after, as its own change, and moved the reference to 11,290.

**Phase 1C** refreshed `uv.lock` and nothing else. Not one figure moved, folium
did not move either, and what did change is in *What 1C found* below.

**Phase 1B** added `routing/coverage.py`, the five Turrutebasen fields and N50's
`malemetode` onto the chains, and `waymarked` and `no_path_recorded` onto every
walked edge. Every phase 1 figure came out unchanged — checked against the
cached phase 1 graph rather than against the printed report: identical chain
ids, identical geometry, identical total edge length and cost to the last digit.
Two things it changed on the way, both found by measuring:

- **`no_path_recorded` is a half-length test, not an all-or-nothing one.** The
  literal "nothing within 25 m" reports 12.7 km where the documented measurement
  says 19.9, and reports one of the three named trips as having none at all. The
  decisions document now carries the reasoning and both numbers.
- **`pd.NA` was landing on chains as the text `<NA>`.** See the trap list below.
  It cost 2,713 phantom FKB chains before it was tracked down, and it was in the
  phase 1 code all along, waiting for a source column in a nullable dtype.

What the review changed, both measured rather than argued:

- **Turrutebasen was weighted 1.00, not the specified 1.02.** The implementation
  carried a comment saying the decisions document leaves it out; it does not —
  the table gives 1.02 and phase 1B spells out the reasoning. Corrected.
- **`--route-noding-m` defaulted to 8 m and is now 0.** Built both ways: chains,
  components, reach, quays and Mosjøen come out *identical*, so all it bought was
  234,358 edges down to 166,900 and two minutes down to one. What it cost was
  4,086 nodes (4.5 %) where two edges meeting there lie more than a metre apart,
  191 over five, the worst 7.55 m — gaps in any track stitched from edges. Both
  budgets hold without it (3.3 MB against 5, two minutes against single-digit),
  so the standing rule applied: reach for it only if a budget is exceeded. The
  parameter stays available; only the default changed.

Three smaller findings from the same review are fixed. One of them was larger
than it looked and is worth remembering:
`test_a_node_sits_where_one_of_its_edges_begins` ended in
`... or edge.source == "UT.no"`, which read like a known displacement being
tolerated. It was not: the fixture put the crossing at `x=150`, on the straight
tail of the wiggly line, where the simplified copy and the drawn line coincide.
The measured displacement was **0.0** — the test had never had a case. Moving the
crossing onto a wiggle (`x=37`) produces 3.034 m, and the bound is now asserted
against the tolerance, with `assert worst > 1.0` so it cannot go vacuous again.
**A green test that exempts something is worth measuring before believing.** The
other two: `carry_positions`' docstring now matches the window projection it
uses, and `fingerprint` now digests each source's identity and attribute values,
so a change in the SSR road names or the Turrutebasen route names is noticed.

### What the map is now

Everything through 3B is committed and the tree is clean. Two changes to the map
are worth knowing because they are easy to read as regressions:

- **The map is drawn from chains**, so a drawn line and a selectable track are
  one object. `describe_whole_roads` and `highlight_keys` are gone — both faked
  what a chain now is. The source flags are gone with them, and FKB therefore
  loads over the full 15 km rather than 5.
- **A chain is never cut at the park boundary**, which costs a little colour
  accuracy: 2.4 km of FKB, 8.4 km of N50 and 14.8 km of OSM inside the park are
  drawn in the approach colour, and 35 km of FKB outside it in the park colour.
  That is the rule as written, not a bug.

Before that, an audit of the popups against what each layer's data actually
holds turned up two things now folded into phase 3: **OSM was the only line
layer showing no length**, though `clip_to` had computed it all along, and **no
layer showed provenance** though every Kartverket line layer carries it. N50 and
Turrutebasen now say how and when a line was captured — the difference between a
path somebody surveyed and one carried forward off an older map, which is 47 % of
N50's here.

`bakke` and `mo` were added to the drawn place-name types afterwards, because a
name in the register that the map never draws looks like a name the map has never
heard of. Not `utmark`: a land-use category for a tract, not a feature with a
position. **58 % of the register's points in the zone are still never drawn** —
6,260 of 10,737 across 131 of its 151 types — and since the search only finds
what is drawn, a known name can still come back empty. Mostly right, since 805
hills and 751 streams would bury the map, but it is a phase of its own if wanted.

The map's warm-cache runtime is **53 seconds**, and the graph's is about two
minutes on a full `--rebuild`. Both read one cached graph, keyed by a fingerprint
that covers the sources, the parameters, the values the chains are built from and
— since phase 2 — a `GRAPH_LAYOUT` marker for what comes *out*. It does not
cover the library versions, which is why an upgrade has to be measured with
`--rebuild` or it replays the cache and reports everything unchanged without
executing a line of shapely.

The measurement scripts that produced the figures lived in a session scratchpad
and are gone. Their methods are below so a figure can be re-derived rather than
taken on trust.

## Verifying a build, concretely

The three commands and the two probes a review starts from. Everything else in
this document assumes them.

**Rebuild and read the figures.** `command make graph ARGS="--rebuild"`, about
two minutes. `--rebuild` is not optional after a library or interpreter change:
the fingerprint does not cover versions, so a plain run replays the cache and
reports every figure unchanged without executing a line of shapely. Confirm the
run actually says *Building chains per source*.

**Load the built graph in Python.** The newest `route_graph_lomsdal-visten_*.pkl`
under `.cache/objects/`, by modification time — the hash is the fingerprint and
changes with every parameter:

    key = sorted(glob.glob(".cache/objects/route_graph_*.pkl"), key=os.path.getmtime)[-1]
    net = cache_module.Object(cache_dir=".cache/objects").load(os.path.basename(key)[:-4])["network"]
    net.chains, net.edges, net.nodes

**Rebuild the map and drive it.** `command make map`, about a minute warm.
`uv run --with playwright`, `p.firefox.launch()` against the `file://` URL of
`analysis/output/lomsdal-visten.html`, and **wait twenty seconds after load** —
the page is **39.4 MB**. It was 25.4 before 3B, 31.1 after the coverage rows,
36.0 after phase 4, 37.4 after phase 5, 37.5 after 6B, 37.7 after 6C, and 39.4
once every chain carried its two steepness figures into its popup. The five
probes, with what they read now:

| | |
|---|---|
| `.leaflet-marker-pane > *` | **198** with no route down, **203** with five waypoints |
| `.leaflet-marker-icon` | **0** with no route down, **5** with five waypoints — folium overwrites the class on its own markers, and phase 7's are Leaflet's own |
| `.leaflet-overlay-pane path` | **11,589**, of which exactly **1** has `pointer-events: none` |
| checkboxes in the legend | **30**, of which 7 start off — there is no `.leaflet-control-layers` any more |
| children of `.leaflet-top.leaflet-left`, by `getBoundingClientRect().top` | search **10 px**, zoom **60** |

and the wheel over the map, which takes zoom **9 → 11**. Reach the map object
with `window[Object.keys(window).find(k => k.startsWith('map_'))]`. There is no
`#map`; the container is `.leaflet-container`.

**The path count in this document said 11,591 until 3B measured it.** It is
11,589, which is what the decomposition beside it — 11,290 chains, 298 circle
markers, the boundary — added up to all along. A figure and its own explanation
disagreed by two for several days and neither was re-run. **When a figure is
written next to its decomposition, add the decomposition up.**

**And what protects the ground**, since 6C. `window.trailsGraph.protectedAreas`
is the 31 areas with their outlines, available **before** the stream inflates
because they travel in the header, and `graph.areasAt(lon, lat)` says which of
them a position lies in. A route's own list is `window.trailsProfile.shape.protected`
— already filtered by the threshold — and
`window.trailsProfilePanel.crossings()` returns the generated waypoints. That one
is a **method and not a field**: the walk costs 45 ms over a 37 km route, so it
happens when something asks and is then cached against the selection.
`window.trailsProfile.crossings` is that cache and is `undefined` until asked.

**And the graph in the page**, since 3B. `window.trailsGraph.ready` resolves to
it; `inflateMs` and `decodeMs` say what it cost — **229 ms and 50 ms** at 4.93 MB.
The round trip is checkable from the page alone: fold the decoded values as
`header.checksum` was folded and compare, over 948,465 vertices and 1,406,040
samples. Heights come back in **centimetres** since phase 5, so fold
`Math.round(h / header.elevationQuantum)` and not `h / 0.1`.

**And the panel and the export, since 4 and 5.** `window.trailsProfile` is the
selection — `figure` and the composed `shape` — and it is there to be read by a
probe rather than screenshotted. The panel's container is
`.trails-profile-panel`; **do not fall back to `document.body`** when looking for
its text, or a probe reads the first of eleven thousand popups instead and
reports nonsense confidently. That cost an hour.

**The panel itself is now four things to check rather than one.** It draws
**true to scale** — one metres-per-pixel for both axes, at every zoom — and the
bounding box against the ground's ratio holds within **0.2 %**, which is only the
stroke's half-pixel and is as much as that test can say. The sharp test reads the
horizontal scale off the distance marks, names the crosshair's sample with it,
and takes the vertical scale from that sample's height: **the two agree to six
decimals** at zoom 1, 2, 4, the ceiling and the 60 px floor. Do not test it with
the crosshair alone — it snaps to the nearest sample, and a probe that assumes
the sample it aimed at reports a 0.2 to 0.44 % bias of its own making.

It stands in **two rows above the chart** for a chain — title with the figures
right of it, and the button with the colour key right of that — and a third for a
route, which also says what ground its file covers. The row with the button is
**a sentence and not a row of boxes**: the licences begin where the point count
ends and wrap mid-list. As flex items they could only fit on that line or not,
and a route naming seven sources in 300 characters did not, so the whole list
dropped to a line of its own and left the count beside the button with nothing
after it. And its height is **a reader's to drag**, from a grip on the top edge, floor 60 px and
ceiling the map's height less 80 — so `chartHeight` is not a constant and a probe
that assumes 205 px is assuming a default nobody promised.

And it holds a **window** on the chain, which `window.trailsProfilePanel.view()`
reports: `zoom`, `at` — the distance at the left edge, in metres — `centre`, the
height at the middle, `shown`, `metresPerPixel` and `closest`, the furthest the
readings let it go. At rest that is zoom 1 and `at` 0 on every chain, and
`closest` is **1 on 99 % of them**, which is how the page says there is nothing
under the drawing to reach. Where `closest` is 1 the wheel belongs to the map and
the chart does not touch it: that is the same 9 → 11 as everywhere else, and it
is worth checking on a short chain rather than assuming it.

The crosshair now stops where the curve does. At a true scale a steep chain
leaves width unused — 638 px of 1,170 on the 3 km one — and there is no ground
out there to report, so a probe reading the panel past that point correctly gets
nothing.

A download is drivable: `browser.new_page(accept_downloads=True)`, then
`page.expect_download()` around a click on the panel's GPX control. Measured, a
blob download from a `file://` page works and keeps its offered filename.

**And the loading, since phase 8.** `window.trailsPlan.load(text, mode)` takes
the file's text and one of `asis`, `align`, `match` — the text rather than a
`File`, so a check drives exactly what the picker drives one step further on.
`state().loaded` says what the file turned out to be and what it cost;
`state().index` is the grid over the edge geometry and is **null until something
asks**, which is how the page says it is built on demand. The picker itself is
`.trails-plan-file` and takes `set_input_files` although it is hidden, and the
mode is `.trails-plan-mode`. A load is finished when `state().working` is false,
not when `load` returns: the legs settle a microtask or more later, which is why
`loaded.settleMs` is stamped by the refresh and not by the loader.

**Do not record a checksum as a reference figure.** It verifies that *this*
build's page decoded *this* build's stream; it is not a property of the network.
It moved once during the phase 4 review and cost half an hour: Turrutebasen
re-exported on 2026-08-17, the fingerprint noticed correctly, and the graph
rebuilt with **identical content in a different row order** — every edge geometry
the same as a multiset, every chain's geometry the same by id, total ascent and
descent the same to the cent, 0 chains added or removed. The counts, the lengths
and the costs are the durable references. A checksum is a decode check.

**And when one does move, read the two accumulators apart.** The first is the
plain sum and is blind to order; the second is Fletcher's and is not. An
unchanged first with a changed second says *the same values arrived in a
different order* — which is what pointed straight at the re-export rather than
at the phase under review.

**Do not probe the popups with `map.eachLayer`.** It walks the map's top-level
layers, which are the feature groups, and never reaches the lines inside them —
so it reports zero popups on a page that has eleven thousand. Count the label in
the HTML instead: *Marking, all sources* appears **11,269** times, one per chain
that is not a ferry, and *Unrecorded ground* **10**.

## How each figure was measured

Re-derive rather than believe, if a phase's output disagrees.

**Connectivity and components.** `unary_union` over every line, then `linemerge`;
union-find over exact edge endpoints — exact, not rounded to a grid, since
`unary_union` produces coincident coordinates at real junctions and a grid splits
near-coincident ones arbitrarily. Bridging adds a connector from every degree-1
endpoint to the nearest line within tolerance, then re-nodes.

**Reach across the park.** Not the share of length, which is the misleading
number: take the largest component's vertices that fall inside the park polygon
and compare their north-south extent to the park's own. 50.8 km of 53.9.

**Chains.** `linemerge` per source already yields maximal runs between junctions.
Strokes on top: at each node, bearings taken over the first 5 m of each arm, arms
paired greedily by smallest deflection, pairs above the threshold rejected.

**Elevation accuracy.** WCS tiles at several resolutions sampled at 300–400 real
FKB path vertices, compared against `ws.geonorge.no/hoydedata/v1/punkt` for the
same coordinates. At 1 m the WCS *is* the point endpoint: median 0.00 m.

**Sampling density.** A dense reference every 2.5 m along one real route, then
each coarser series interpolated onto it and the residual measured. Note the
bias: at 5 m spacing every second reference point coincides with a sample and
contributes zero error, so 5 m looks better than it is — the true advantage over
10 m is nearer 1.5x than 2x.

**Payload sizes.** Zigzag varints over deltas between consecutive points, one run
per edge, then gzip, then base64. Twelve times smaller than JSON arrays.

**Coincidence between two sources** — the figure behind the 34 % marked, the
94 % on a mapped line and the 19.9 km on nothing. Buffer each chain of the
subject by the tolerance, `STRtree`-query the mask for hits, union *only the
hits* and intersect. Buffering the whole union first is the obvious way and does
not finish. Always run it at two tolerances: if the answer moves little between
10 m and 25 m it is a property of the ground, and if it collapses below 5 m it
was GPS noise.

**Node displacement**, which decided `node_simplify_m`. Per edge, the distance
from each end's node position to that end's own coordinate, grouped by source.
Then, per node, the widest gap between any two edge ends meeting on it — that
second one is what a stitched route actually sees.

**A chain's elevation series.** Not sampled along the chain — the build samples
per *edge*, so points taken along the chain miss the store entirely. Take the
chain's edges, order them, and concatenate their series with the shared node
counted once. Verify the ordering before trusting it, by checking that
consecutive edges touch: 2,221 chains do not join up in the frame's own order,
so an unordered concatenation silently produces a plausible profile of a route
nobody could walk.

**Order them by walking the graph, not by projecting onto the chain.** This
document said "project each edge's first coordinate onto the chain" until 3B
measured it: that leaves 35 chains still not joining, because two edges of a
chain can project to the same place. It also mis-described phase 2, which walked
node to node from the start and used projection only to decide which *way* round
the finished run goes. `trails.routing.order.chain_order` is the walk, and both
the build and the page now use it — one walk, because two would eventually
disagree and both would still look like profiles.

**Reading the elevation store.** `.cache/elevation/hoydedata_25833.parquet`,
keyed on `east` and `north` as **integers in centimetres** — `round(x * 100)`,
not a rounded float. Getting that wrong returns a store full of misses that looks
like a store full of gaps.

**Payload encoding.** Zigzag varints over deltas, one run per edge, then gzip,
then base64 — geometry at 1e-6, elevations at 0.01 m. Measure the **edge table
separately**: as JSON it is 1.98 MB and as sorted delta-encoded columns 0.27,
which is the whole margin. Do not scale one payload from another; that produced
both of this phase's budget errors, in opposite directions.

**Provenance.** `malemetode`, `noyaktighet` and `datafangstdato` on N50;
`measurement_method`, `accuracy`, `origin` on Turrutebasen; FKB has none, and its
WFS `DescribeFeatureType` is what proves it rather than an absence in the loader.
Weight the breakdown by **length**, not by feature count — the two disagree
badly. Careful with fill rates: `notna()` counts `""` as populated, which made
FKB's fields look complete when they are at 3–6 %.

## What this codebase does that will bite

Every one of these cost real debugging time in the work leading up to this, and
every one was invisible until something was actually run.

- **A boundary polygon swallows clicks.** `folium.GeoJson` paths are interactive
  by default and a fill catches pointer events at 6 % opacity. The park boundary
  is drawn last, so for a long time *no* trail inside the park was clickable in
  any layer. Fixed with `interactive=False`; watch for it whenever something
  large is drawn on top.
- **A panel outside the map container swallows the wheel.** Anything positioned
  over the map must be a Leaflet control, added with
  `L.DomEvent.disableClickPropagation` but deliberately *not*
  `disableScrollPropagation`, and text inputs must stop key events or typing a
  `+` zooms the map.
- **Leaflet appends controls to the end of a corner.** To sit above the zoom
  buttons, a control has to be moved to the front of its corner after `addTo`.
- **folium overwrites Leaflet's own marker class** with `awesome-marker`, so
  `.leaflet-marker-icon` matches nothing. DOM probes must address
  `.leaflet-marker-pane > *`. This produced a false test failure and a false
  "zero markers" reading.
- **`json.dumps` does not escape `<`.** A value carrying `</script>` closes the
  block. `maps._script_json` exists for this; use it for anything embedded in a
  script tag.
- **Redraw cost is a real constraint.** Rebuilding a layer per keystroke, and
  writing a style that is already set, each froze the map badly enough that the
  wheel piled up and only landed when typing stopped. Apply differences; read
  before writing.
- **`sjoin_nearest` emits one row per tied match**, silently lengthening a frame.
- **Proximity alone is a weak join for lines.** At a junction the first metres of
  a side road lie within tolerance of the main road: 23 % of matches followed
  their road for under half their length until `min_overlap` was added.
- **Ids are not as unique as they look.** SSR road ids repeat where a road
  crosses a municipal boundary — correctly, that is what reunites it. And a
  single null in an integer column makes pandas store it as float, so `1113860`
  becomes `1113860.0` and hashes differently.
- **There are three ways a frame says nothing and `pd.NA` is the one that gets
  through.** `None` and a float `nan` are what an object column holds; a column
  in a nullable dtype holds `pd.NA`, which is neither, and Turrutebasen's loader
  produces `string` columns throughout. A check written as
  `value is None or isnan(value)` passes it, `str()` turns it into the text
  `<NA>`, and it lands on the chain as a value. As an attribute that fills an
  empty column and reports it 100 % populated; as an *identity* it makes every
  unnamed line in the source the same way as every other unnamed line, which put
  2,713 chains onto FKB that are not there. `pd.isna` is the test. The symptom
  was a chain count moving in a source nothing had been done to — attributes had
  been added to Turrutebasen and FKB was what moved.
  **Under pandas 3.0 this is half true, and the surviving half is the dangerous
  one.** The scalar is unchanged: `str(pd.NA)` and `f"{pd.NA}"` are still the
  text `<NA>`, so the trap above stands exactly as written. What moved is the
  *vectorised* path — `Series.astype(str)` no longer stringifies a missing value,
  it leaves it missing, and `.str.cat()` then drops it. Phase 1C found this the
  only way it shows: the graph's cache fingerprint changed without one figure in
  the graph changing, because `_values_digest` concatenates exactly that way.
  That reads like an improvement and is not. Dropping a missing value throws away
  its **position**: `['A', NA]` and `[NA, 'A']` both concatenate to `'A'` and
  digest the same, where pandas 2 wrote `<NA>` into the run and kept them apart.
  So the vectorised path is no longer a safe way to summarise a column, and the
  scalar path was never one. Neither is a substitute for `pd.isna`. What this
  costs `_values_digest` is written up under *What 1C found*.
- **A `var` silently overwrites a function of the same name in the same
  closure.** The panel's legend was built into `var scale`, which replaced the
  `scale()` it used to fit a series to its box. Nothing raised at parse time and
  the page looked fine until a chain was clicked. The page's script is one long
  IIFE, so every name in it shares one scope.
- **A `catch` spanning the wait *and* the work blames the wait.** The panel ended
  in `.then(draw).catch(say('the routing graph did not arrive'))`, so a fault
  while *drawing* was reported as a payload that never arrived. It sent me to the
  payload twice. Two handlers — `then(onValue, onReject)` — and the next run
  named the real fault itself.
- **Anything drawn into the overlay pane is counted among the map's paths for
  ever after.** 11,589 is an acceptance figure for every phase from 3 onwards, so
  the direction arrow and, from phase 6, the planned route belong in panes of
  their own. `map.createPane` plus `leaflet-zoom-hide`.
- **`map.eachLayer` does not reach the lines.** It walks the map's top-level
  layers, which are the feature groups; a probe using it reported **zero** popups
  on a page holding eleven thousand. Recurse into each group, or count the label
  in the built HTML instead.
- **A removed constant is invisible to every Python check.** Dropping `CURVE`
  left one reference behind in the arrow, and the whole panel threw at load —
  with `make hooks-run` green and the map building cleanly. Only a browser says
  so, which is why anything visual is driven before it is believed.
- **Merging pieces of a line does not deduplicate them.** Measuring how much of
  an edge lies near a mask, the natural form is to intersect the edge with each
  nearby line's buffer and merge the pieces. Those pieces overlap where the mask
  lines do, and at projected-CRS magnitudes they do not dissolve into one
  another: one edge came out at **3.6 times its own length**. Merge the buffers
  into one area first and intersect once. It is also 8× faster to shortcut the
  two cases that need no merge at all — one mask line covering the whole edge,
  which is 99 % of them, and only one line near it.
- **`shapely.intersection` on a long line loses the ground it retraces.** GEOS
  nodes a line before it overlays it, so where a track doubles back the repeated
  pass is counted once. Measured: a 14,681-point exported route intersected with
  the park as one line read **31,023.8 m** where midpoint containment per step
  and a segment-by-segment intersection both read **34,000** — 3 km, and it looks
  exactly like a bug in whatever produced the 34,000. Per *edge* it is small and
  one-directional: 67.5 m in 647.8 km, on five edges of 60,576. Measure a long
  line segment by segment, and treat a cross-check as a measurement that needs
  checking like any other.
- **A patch that matched nothing wrote nothing, and the build said yes anyway.**
  Editing this page's script by exact string replacement, one anchor turned out
  to appear **twice** — the plan panel and the profile panel assemble their boxes
  with the same two lines — so the guard tripped, the script exited before
  writing, and `make map` then rebuilt the *unchanged* file and printed its tick.
  Two minutes went into reading a feature that was never in the page. **A green
  build proves that a build ran, not that it built what you wrote.** Assert the
  count before replacing, and check the thing you added is in the output rather
  than checking that the command succeeded.
- **A driven click or drag lands on whatever is on top, not on what you meant.**
  Probing phase 7's drag read **one** recompute where there are eighteen, three
  times running, and it nearly went into a review as a broken throttle. Each time
  the mousedown had landed on an element covering the pin —
  `elementFromPoint` at the pin's own bounding-box centre returned a `div` that
  was not it, so Leaflet's drag never began and the waypoint never moved. Two
  clicks aimed at "empty ground" landed on the search box and on the profile
  panel, both of which are Leaflet controls covering a good part of the viewport.
  **Before driving a gesture, assert that `elementFromPoint` returns the thing
  you are aiming at**, and pick the target that way rather than by index. This is
  the twin of the `document.body` warning: that one is about reading the wrong
  element, this one about writing to it.
- **A waypoint that refuses to snap is a waypoint nothing can route to.** Phase
  8's anchored waypoints keep the recording's own position, which is right, and
  carried `node: -1`, which meant every leg with one anchored end and one
  ordinary one fell past `from.node >= 0 && to.node >= 0` and was drawn straight
  over the terrain. Neither acceptance file caught it because both were pure —
  every leg recorded, or every leg routed. **A field with a sentinel value is a
  branch, and the case where two kinds meet is the one nobody drives.**
- **A setting the template reads and the check does not list is `undefined`,
  and JavaScript says nothing.** `PLAN.matchAnchorM` was read by phase 8's
  matcher and left out of `PLAN_SETTINGS`; `along[i] - since < undefined` is
  `false`, so every recorded point became an anchor and the matcher matched
  **3.6 %** of a track that lies exactly on the network. Nothing threw, nothing
  logged, `make check` was green. The existing test walked the *list* and looked
  for each name in the page — **a contract checked in one direction is not
  checked** — and the converse is now a test of its own.
- **Edge length here is median 6.9 m and the longest walked edge is 6.8 km.**
  Noding cuts a line only where something meets it, so an isolated recording out
  in the terrain is *one* edge: **1,141** of the 234,358 are over 500 m, and
  UT.no's longest is 4.7 km with thirteen over 500 m. The 18.5 km edge quoted
  beside this figure at first is a **ferry crossing**, not a recording — a right
  mechanism with the wrong number standing next to it.
  Anything that reasons from the average — *the nearer end of the matched edge is
  a dozen metres away* — is right at the median and wrong exactly where a foreign
  track lives.
- **`DOMParser` logs a console error the page cannot suppress.** A file that is
  not XML produces *XML Parsing Error: syntax error* attributed to the page's own
  URL before `parsererror` can be found and the file refused properly. A probe
  treating `console.error` as failure reads a correct refusal as a fault.
- **`getElementsByTagName` matches the qualified name in an XML document.** A
  prefix is the writer's choice, not the format's, so a file spelling this map's
  namespace `t:` rather than `trails:` is missed entirely. Address extensions by
  `getElementsByTagNameNS(namespace, name)` and GPX's own elements under `'*'`,
  since a consumer device that leaves the default namespace off writes a file
  every other reader still accepts.
- **An unbounded walk over the graph takes the machine down, not the script.** A
  Dijkstra's path reconstruction — `while walk != a: used.append(edge)` — grew to
  **42 GiB in 376 seconds** and reached the kernel's OOM killer, which chose the
  terminal the session was running in. Two doors into it and both stand open in
  this graph: **14 edges have `from_node == to_node`** (UT.no and FKB), where
  stepping back across the edge does not leave the node; and `via[node]` starts
  at `-1`, which numpy reads as the **last edge** — `to[-1]` is node 116,353 —
  rather than raising. `timeout` does not help: it was set to 1200 s and the
  memory was gone after 376. Cap the script instead, with
  `resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3,) * 2)`, which turns
  exactly this into a `MemoryError` naming the line.

## Before handing a phase over

This has been done for 1B, 2, 3, 3B, 4, 5, 6, 6B, 6C, 7 and 8 — **eleven times,
and it found something every time.** A rule that was not implementable, six
acceptance
figures that would have failed a correct implementation, fifteen attributes
nobody had counted, a missing layer, a forgotten payload, a budget off in both
directions, a rounded label that two languages would round differently, an
acceptance its own builder could not execute, a phase that was three phases, two
central premises that were false, and a claim in the decisions document that no
one had measured. Reading the phase never finds these. The check is:

1. **Load the built graph and measure what the phase asserts.** Every figure in a
   phase should be reproducible from `.cache/objects/` in a few lines. One that
   is not is either wrong or was never measured.
2. **Ask what the phase needs that nothing provides.** The popup ascent, the node
   positions, the per-chain figures and the edge order were each specified for a
   consumer with no producer.
3. **Ask which phase receives each requirement of the decisions document.** That
   is the inverted form and it found the page encoding, which was specified over
   thirty lines and belonged to nobody.
4. **Read the phase end to end afterwards.** Patching a phase four times produces
   four contradictions; phases 2 and 4 both had to be rewritten as one text after
   being corrected in pieces.

Do not hand over a phase whose acceptance figures were derived rather than
measured. Two of them — FKB's 173 km and Sjøbergmarsjruta's 996 m — came from a
different method than the rule they were stated against, and both would have told
a correct implementation it had failed.

### The prompt that has worked

Five phases in, the shape is stable: point at the three documents and say to read
all of the phase, not the summary. Name the commit the tree is at. List the traps
by name — each one cost real time here and none is deducible. State the
acceptance as measured figures. Say what is **not** to be built and why, because
that is what stops a helpful agent widening the scope. Require a browser for
anything visual, with `uv run --with playwright` and no new dependency. End with
*run a code review, work the findings in or say why not, then stop and report*.

Give an agent an escape hatch — *if this is bigger than it reads, say so and
stop* — and take it seriously when used. It has been right both times it was
invoked.

**And launch it in a memory cage**, because an instruction can be forgotten and a
cgroup cannot:

    systemd-run --user --scope -p MemoryMax=16G -p MemorySwapMax=0 claude ...

Phase 6's first attempt died that way on 2026-08-22, taking 64 GB with it. The
agent's 1,102 lines survived in the working tree; the session did not.

**The cage and the script's own `RLIMIT_AS` do different jobs, and neither
replaces the other.** Measured here: a cgroup at its ceiling delivers SIGKILL and
exit 137 with **no traceback** — the machine survives and the agent learns
nothing — while `setrlimit` makes the allocation fail so Python raises
`MemoryError` and names the line. Set both: the cage protects the desktop from an
agent that forgot the rule, the rlimit is what lets it debug itself.

## Reviewing each phase

The two expensive gaps in the specification were found by *running things* and by
being questioned — not by reading it. Review the same way.

**Anything, first.** Did it add a dependency? Nothing in the eight phases needs
one — shapely, geopandas, requests and pyarrow cover all of it, and the browser
work adds nothing at all. A new entry in `pyproject.toml` or a changed `uv.lock`
is a finding until it is justified, not a detail.

**Phase 1, the graph.** First: was Turrutebasen included? Every documented figure
was measured without it, so a graph that has it will exceed the stated edge count
— correctly. Judge by the reach, which should hold at 94 %, and record the new
counts as the reference.

Then the figures are the test: chains, edge count, largest
component, reach, Mosjøen, and the ferry numbers. Check that chain ids are stable
across two builds — rebuild and diff them. Check a road that branches, such as
Tveråvegen, selects one arm and not eight. Check a ring-shaped chain does not
crash whatever looks for endpoints.

**Phase 1, simplification before noding — settled, kept here as the method.**
Phase 1 reported that Turrutebasen braids against FKB and introduced a
`node_simplify_m` to deal with it. The three checks below were run and the
outcome is in "Where things stand": the geometry on the edge was never thinned
(check 1 passed cleanly), and checks 2 and 3 decided it — measured, it changed
nothing but the edge count, and cost node accuracy. The default is now 0. Re-read
this if the parameter is ever proposed again.

1. **What ends up on the edge.** The specification allows simplifying *what goes
   into the noding* and requires the **full geometry to remain on the edge**. If
   the stored geometry has been thinned, that is a finding: accuracy was the one
   thing stated as non-negotiable, and this is exactly where it would quietly go.
   Compare an edge's vertex count against its source features.
2. **Whether it was needed at all.** 24,478 extra edges take the graph from about
   130,000 to 155,000, which a Dijkstra does not notice. The drawn objects are
   untouched, since Turrutebasen keeps its routes as units. The only real symptom
   is a route able to hop between Turrutebasen and FKB every ten metres — and the
   source weights, 1.02 against 1.05, already hold it on the better one. Ask what
   the measured cost was before accepting a mechanism against it.
3. **Whether it treats the cause.** The braiding produces crossings, not
   vertices, and none of those crossings is a junction: both lines carry on the
   same way. Filtering crossings by angle — the stroke rule applied to noding
   rather than chaining — addresses that directly, where simplification only
   removes the wiggles that happen to cross. If `node_simplify_m` survives
   review, it should be because it was measured to work, not because it was the
   first thing to hand.

The same question applies to UT.no, which has the same problem for the same
reason and where the specification already sanctions simplifying the noding
input.

**The order to do this in: build without it, measure, and reach for it only if a
budget is actually exceeded.** Simplification is not a free optimisation — fewer
crossings means different nodes, which means different chains and possibly
different connectivity. It is an intervention, and it needs its own before-and-
after on reach and chain counts, not just on the edge count it was aimed at.

Budgets worth stating, so "too large" is testable:

- ~~the graph's whole contribution to the page stays under about 5 MB~~ —
  **struck out after phase 5.** It was never measured, and measured it guards
  nothing: quadrupling the payload costs about thirty milliseconds of a 1.6 s
  load, and the payload is 4.93 MB of a 39.4 MB page. What it did do was force
  the edge table to be encoded, worth 1.7 MB. **A ceiling nobody can justify is
  still useful if it makes the right question unavoidable, and useless as a
  fact.** The load time replaces it
- noding stays within single-digit minutes

Neither looks threatened by 25,000 extra edges: a Dijkstra does not notice
155,000, the edge records add a few hundred kilobytes, and the geometry is
unchanged because it is the same vertices either way. If the measurement says
otherwise, that is worth knowing on its own.

**Phase 1B, what the graph carries.** Rewritten after the phase 1 review: three
of its four original points were already satisfied and are struck through in the
phases document. What is left is Turrutebasen's attributes, N50's `malemetode`,
and the two derived edge fields.

The acceptance is the same for all of it and it is the thing to check first:
**no figure from phase 1 may move.** Attributes ride along the chains, only
`identity_field` decides them. 11,290 chains, 234,358 edges, 757 and 747
components, 50.8 km = 94 %, 17 quays, Mosjøen at 2.17 m. If any shifts, something
touched the geometry, and that is the finding rather than the new column.

Then the two derived fields, each with a number to land on:

- `waymarked` — UT.no **31 %**, FKB **246 km**. These were re-measured under the
  rule as specified, after an earlier draft of the phase quoted 34 % and 173 km
  taken from *different* measurements: the first a plain length overlap rather
  than the half-length test, the second the `attach_nearest` name join at 25 m,
  which never saw N50's own marked paths. A correct implementation would have
  been told it had failed. **Check that a predicted figure was measured under the
  rule it is predicting, not merely near it.**
- `no_path_recorded` — near **19.9 km** of UT.no's 376, and it must be
  concentrated in three trips rather than spread thin. Spread thin means the
  25 m tolerance was not applied.

Two things the specification had wrong until they were checked, both worth
re-checking in the implementation: **ferries must be excluded** from both derived
fields — a crossing has no path mask within 25 m, so 149 km of it would be
flagged as pathless — and `waymarked` must be built from **masks over the raw
sources**, not from the edge's own attributes, because `rutemerking` reaches an
edge only through its chain, where `_combine` has already merged 158 km of it
into an ambiguous `JA / NEI`.

And the trap the whole design rests on: **its absence asserts nothing.** If any
text, name or docstring reads it as "there is a path here", that is a finding.

**Phase 1C, the dependency refresh.** Run phase 1's statistics before and after
and compare. Any movement in edges, components or reach is the upgrade's doing
and nothing else's — that is the whole reason it sits here rather than later.
Then drive the map in a browser: clicks reaching lines, the wheel reaching the
map, markers rendering at all. The trap list above was observed under **folium
0.20.0**, which is also what the upgrade left installed, so none of it needed
revisiting; the "0.17" this document used to give was the floor in
`pyproject.toml` read as a version. See *What 1C found* below.

**Phase 2, elevation — built.** The invariance is the test: the same route's
ascent at 5, 10 and 15 m sampling. Then check the cache actually holds — a second
run must issue no requests. Then check a coastal path: any profile touching
−276 m means `datakilde` is not being checked. All three passed; see *What phase
2 found* below for the one figure that did not.

Two things the phase was checked against reality for, before it was handed over:

- **Both ascent *and* descent, everywhere either is stored.** The specification
  said ascent alone until it was asked what a popup would actually show. A chain
  is oriented so its id is stable, not because a walker takes it that way, so an
  ascent figure is true in one direction and silent about the other. If only one
  number came back, that is the finding — and it was added to the phase while
  phase 2 was already being implemented, so it may need saying out loud.
- **Ask which ascent figure a number came from.** There are two and they are not
  interchangeable: per edge for routing weights, per chain over the full series
  for anything shown. Summing the per-edge ones does not approximate the
  per-chain one, it destroys it — 42 % of the edges are under 5 m and the median
  is 6.9 m, so under the threshold most report nothing at all. The decisions
  document said the opposite until this check; if a figure looks suspiciously
  low, this is why.
- **"Sjøbergmarsjruta" is three chains** — UT.no, Turrutebasen and FKB all draw
  it, all 20.48 km, all starting at the same rounded point. The acceptance names
  one figure against a name that resolves three ways, and the UT.no one is a
  consumer GPS track whose noise adds climb. Insist on all three.

What did *not* need changing, having been measured: 20,358 requests against a
documented 22,000, 1.02 million elevations against 1.1, and 16.4 minutes against
"about seventeen" — the endpoint answered a probe in 0.29 s. The graph nearly
doubled since those were written and the figures still hold, because
deduplication absorbs it.

**Phase 3, drawn from the graph.** Nothing new should work; everything old
should still work. This is the phase where a regression hides, and the specific
place it hides is a popup.

The phase was checked against the built graph before it was handed over, the way
1B was, and "popups keep what they show today" turned out **not to be achievable
as written**: fifteen attributes had to be added to the chains, UT.no's four
links and its summary among them. So the first thing to review is not the
mechanism but the content — open a popup of every one of the seven line layers
and compare it against the map committed at `8497154`.

What that inventory also turned up, and what to check it was honoured:

- **`is_dnt` splits Turrutebasen into two of the seven layers**, so a missing
  flag is a missing layer rather than a missing field. It is derivable from
  `maintenance_responsible`, but 113 of 244 chains carry more than one
  maintainer and three of those, 9.4 km, are part DNT and part not. Decided:
  `.any()`, as today. Check that the decision was taken rather than stumbled
  into.
- **`osm_id` on a chain is a list**, because 64 % of the OSM chains span more
  than one way — worst case 33. Decided: keep it joined, plural label.
- **`describe_whole_roads` should be gone.** A chain *is* the whole road arm now;
  that function existed to fake it. `road_length_km` becomes `length_m`. If both
  still exist, something was carried across that should have dissolved.
- **The whole-named-way figure** is now a sum over the chains sharing an
  identity. 132 of the 2,326 road chains carry more than one `road_id`.

And a correction to this document, which had it wrong for several days: **the
`--simplify-m` on the drawn copy does not contradict "do not simplify to save
space".** That rule governs the exported and routed geometry, which keeps full
precision. Folium writes drawn geometry as JSON coordinate arrays, measured at
22.4 MB for the network's vertices. Anyone "fixing" the apparent contradiction
by removing the simplification puts twenty megabytes into the page. The script
has said `GPX keeps full detail` all along; I read the two rules as one and they
are not.

The browser baseline is measured rather than remembered, because 1C and 1D both
drove the map and it read the same each time: **198** markers in
`.leaflet-marker-pane > *` and 0 under `.leaflet-marker-icon`, **12,357** paths
of which exactly **1** non-interactive, the search control at **10 px** against
the zoom at 60, and the wheel taking zoom **9 → 11**. All of those must come out
identical. The path count is the one figure that should move, roughly halving as
23,876 objects become 11,290 chains — it landed at **11,589**.

**Phase 3B, the page payload.** It exists because reading the decisions document
against the phases turned up an encoding specified over thirty lines — zigzag
varints, gzip, base64, `DecompressionStream` — that no phase had claimed, while
two later ones assume it. **Ask of any specification: which phase receives this?**
That question found this, and it found the popup ascent in phase 4.

Review it on the round trip, not the size: decode the whole graph in the browser
and compare against the source coordinates. A decoder correct for 99.9 % of runs
has a bug in the long ones.

Then the budget, which was measured after the phase was written and turned up two
errors in it. The geometry is **cheaper** than the scaling suggested — 2.35 MB
against 3.30, because gzip does better on more data than a linear scale assumes.
And the edge table, which the draft listed as a deliverable and left out of the
budget, is **1.98 MB as JSON** and puts the total at 6.5 MB, over. Sorted by
`from_node` with both columns delta-encoded it is **0.27 MB**. That seven-fold
difference is the whole margin — as the allowance stood then; see *Where the
5 MB went* below.

A second pass once phase 2 had run corrected the table again in the other
direction: the elevations were estimated at 2.2 MB and measure **0.98**, so the
total is 3.6 rather than 4.8. **Both errors were estimates standing where the
document demands measurements**, and they pointed opposite ways — which is what
estimates do.

The same pass found the ordering problem is larger than the phase first said.
**2,212 chains, one in five, have edges that do not join up in the frame's own
order**, with jumps to 20 km. So the order is not something sorting breaks; it
is already lost and has to be reconstructed and carried. Phase 2 solved that for
itself by projecting each edge onto the chain, without being asked to and without
saying so — check that 3B does not assume the frame order is meaningful just
because phase 2's figures came out right.

So the check is: was the table encoded or serialised, and did the sort scramble
what ties an edge to its chain? A scrambled graph is not obviously broken.
`cost` should not be in the payload at all — it is length times a source factor
and the browser has both.

**Budgeting a payload by scaling another payload does not work.** That is what
produced both errors here, in a document that insists elsewhere on measuring.
A third followed, and it is the instructive one: see *What 3B found*.

**Built. The check that mattered, kept for the next payload:** the header's
checksums prove the *page* agrees with the *encoder*, and nothing more. They are
computed from the same array the encoder writes, so an encoder that laid the
wrong geometry against an edge would write a checksum for the wrong geometry and
the page would confirm it. Decode the stream separately — from the format
description alone, not from the encoder — and compare against the frame. Over
all 234,358 edges that reads a worst coordinate error of 0.0557 m and a worst
height error of 0.0500 m, which are exactly half a quantum each and therefore
rounding and nothing else. **Two implementations agreeing is not a round trip
when one of them defined the answer.**

**Phase 4, the profile.** Two of its requirements arrived late and by being
questioned, which is worth knowing when reviewing it.

The **popup ascent** had fallen between phases 2, 3 and 4 — the decisions
document calls it the main thing the sampling buys and no phase had claimed it.
A first attempt to place it here reasoned that phase 4 was "the first to have
both" the elevations and the rebuilt popups; that was wrong, since popups are
rendered in Python at build time and need nothing from phase 3B's payload. Phase
4 owns it only because it is the first phase after phase 2 that touches the map.

**Descent, and the direction**, arrived when the plain question was asked: after
this phase, do I see ascent *and* descent per segment? The specification said
ascent alone, stored only per edge, with descent appearing solely in the panel's
description. And a first fix — anchoring the numbers to the endpoint elevations
— was refused for the right reason: it says which direction the figures describe
but not which end of the drawn line you are standing at. The answer is one
direction shown three ways, the arrow being the part that actually orients
anybody. **A number that depends on direction is not finished until the reader
can see the direction.**

Check it is hand-drawn SVG and nothing is fetched from
a CDN — a CDN script fails silently on `file://`. Check the map still zooms while
the panel is open.

**The readiness check found five things, and the phase was rewritten as one text
rather than patched.** What to check the rewrite kept:

- **Four acceptance figures were stale** and would have failed a correct
  implementation: 172 chains over nine hundred samples not 186, the 42 km
  Rundtur at 8,191 not 8,489, **41 rings not 52** — a figure `elevation.py` had
  said correctly since phase 2 — and 493 strongly wound not 452. What did
  reproduce, exactly: 36 samples at the median, a third under twenty, 0.93
  straightness, 34 % off a cardinal axis, and no chain running W, SW or NW.
- **The mechanism it named does not exist.** *"Phase 3 already puts the chains in
  the page as GeoJSON and the panel has the clicked feature in hand"* — the page
  holds **11,290 `L.polyline` and one `L.geoJson`**, the boundary. A polyline has
  no `feature.properties`. The claim stood three times across two phases and once
  more in `encoding.py`, and 3B was built without noticing because 3B does not
  depend on it. What does exist: `className="trail-group-<chain_id>"` on every
  line, and `SEARCH_NAMES_ATTR` — a side table keyed by that class, already
  shipped for the search box.
- **The bearing had no home.** The phase wants it in the popup (Python) and in
  the arrow (JavaScript) and says all three showings must agree, while
  forbidding exactly that pattern for ascent two paragraphs earlier. Measured at
  65.5° N: a flat `atan2(Δlon, Δlat)` instead of a metric bearing moves
  **4,444 of 11,249 chains — 40 % — into a different one of the eight points**,
  and 241 lie within half a degree of an octant boundary. **A rounded label is a
  threshold, and every rule this document has about thresholds applies to it.**
- **Three kinds of chain, a rule for one.** A ferry's series has length **zero**;
  two walked stubs, `osm-423700-7272625-5` and `osm-382608-7302481-2` at 5.1 and
  2.0 m, have **two samples and two gaps**. So `series.length === 0` stops the
  ferries and lets those two through to draw `M NaN,NaN` — nothing on screen, no
  error. **Test whether anything was read, not whether anything exists.**
- **The crosshair belonged to no phase.** The decisions document says the curve
  is *"one path, two axes and a crosshair"*; the word appeared nowhere in the
  phases document. That is the third time the inverted question has found
  something — after the page encoding and the popup ascent.

**Phase 5 and 6, export.** Open the file. A ferry or a water leg must break the
track into segments, not draw a line across the fjord. Import it somewhere.

**Phase 5's readiness check found six things, two of them already live.** The
phase was rewritten as one text; what to check the rewrite kept:

- **The writer thinned every export and nobody had noticed**, because
  `export_to_gpx` had **no tests at all**. Its default was 1e-5 degrees, and the
  six build-time files were losing **62 % of FKB's vertices and 65 % of UT.no's**
  against a rule saying exports carry full source precision. Fixed, with six
  tests; FKB goes 8.09 → 20.16 MB, which is what the rule costs.
- **Its point count was summed from the input**, so it reported 305,248 points
  for a file holding 115,655 — and phase 5 wants to *show* that count. Counted
  off the written element now, and the two agree for all six files. The size
  divided by 1024² and said MB.
- **The page carries nothing `<metadata>` needs.** Measured: `CC BY 4.0`, `ODbL`
  and `CC BY-NC` appear **zero times** in the built page, and no source version
  does either. They exist only in what the build prints to its console, and the
  browser is the thing asked to write them into the file.
- **The figures table has no name and no source**, which the `<extensions>` must
  carry. Same shape as phase 4's GeoJSON: a mechanism assumed rather than
  checked.
- **`no_path_recorded` belonged to no phase.** The decisions document lists five
  things an exported file carries and the phase enumerated four. Worse, two days
  earlier this document had written that the field was *phase 6's* — measured, it
  is phase 5's, it is on the chains as `no_path_m`, and it is not in the table.
- **The acceptance could not be run**: *"imports into Komoot and Outdooractive"*.
  No account, no network, manual. **A phase whose acceptance its builder cannot
  execute has no acceptance at all** — the first time that has happened in eight
  phases. Replaced with seven checks that run here, with the import kept as a
  person's step afterwards.

And one assumption checked rather than carried: **a blob download from a
`file://` page works.** Firefox saves it with the offered filename and raises
nothing. Ten minutes, and the whole phase rested on it.

**Phase 6, plan mode — built and reviewed**; see *What phase 6's review found*.
What it was checked against, kept for 6B and 6C:

- **The graph must not move**: 11,290 chains, 234,358 edges, 116,967 nodes,
  757/747 components, reach 50.8 km = 94 %, 17 quays, Mosjøen 2.17 m. **The
  payload must not move**: 4.93 MB, both checksums, heights at 0.01 m.
- **The page must not move**: 198 markers, **11,589** paths of which exactly one
  non-interactive, 25 layers, 10 px above 60, wheel 9 → 11. **If the path count
  moved, the route was drawn into the overlay pane** — that is the first thing to
  look at, and the arrow in phase 4 is the precedent.
- **A chain's own export still reproduces its stated ascent to 0.00 m.** Phase 5
  bought that with 0.8 MB; a change to how a series is composed can lose it
  without anything else looking wrong.
- **All four leg kinds, in one model.** The seam between routed and free legs was
  where the first split of this phase went, and it was moved precisely because a
  model knowing one kind would have to be widened. If the code has a routed-leg
  path and a free-leg path that do not meet, that is the finding.
- **Cost comes out of the header, not out of a second table.** Length times the
  source's factor, a crossing at the flat `flatM`. A cost column in the payload
  would be the thing 3B deliberately left out.
- **The on-demand heights are sampled at 5 m and read by the same ascent rule as
  the build.** Two halves of one profile answering differently is the failure,
  and it will not look like one.
- **A crossing carries no curve.** Not a flat line at zero — that is a claim
  about ground that is not there. Same rule as a ferry in phase 4.
- Ask what it needs that nothing provides, and grep the built page rather than
  assuming. **Three phases in a row assumed a mechanism that did not exist** —
  GeoJSON properties, the licences, the point table.

**Phase 6C, protected areas — checked and rewritten, not yet built.** What its
readiness check found is in *What phase 6C's readiness check found*. The short
of it: the spatial query is ten lines and the smallest part; the per-edge field
needs a **`GRAPH_LAYOUT` bump and a rebuild**, the first since phase 2; the named
points have no table — **1,411** `circleMarker` and 865 `marker` with their names
inside popup HTML; a free leg cannot answer from its samples at all; and the
phase has to set a threshold before it can report anything, because one of the
nineteen areas the network touches is met over ten metres.

**Phase 7, editing — handed over, being built.** What the readiness check found
is in *What phase 7's readiness check found*. When it reports, review it like
this:

**Two figures are allowed to move, and only these two.** This is the first phase
where that is true, and it inverts the habit of every review since 3. A
draggable waypoint is an `L.marker`, so a five-point route goes **plan pane
13 → 8** and **markers 198 → 203**. Anything else moving is a finding, and
**11,589 paths with exactly one non-interactive** is still the first thing to
look at. If the pins stayed `L.circleMarker` and the drag was written by hand,
then *neither* figure may move and the click question below got harder, not
easier — check which of the two was built before checking the numbers.

**Then the three decisions the phase told it to make rather than discover**, and
whether the reasoning was written down: how a click on a waypoint is told apart
from a click on the map, which today adds one; what throttles a drag and what
cancels a settle whose waypoint has moved on; and where the recompute was
narrowed. That last one has a right answer — free legs and the drag, not routed
legs, which cost 19–76 ms each against 3 ms for composing the whole route.

**Drive a drag, do not read the code for it.** Count the requests a drag over a
free leg issues, not whether a throttle exists: the failure is a leg drawn from a
reply that is no longer wanted, and it looks like a route until you measure it.

**And check the numbers keep up rather than that they are right at rest.** The
distance and the profile have to follow a live drag; a value correct only once
the mouse stops is the failure this phase exists to prevent.

**Phase 8, loading — built.** What it came to is in *What phase 8 found* and
what the readiness check found before it is in *What phase 8's readiness check
found*. Reviewing it, or anything that touches it:

**The index came first and it is 29–42 ms for 0.7 µs a lookup.** That was the
right order and it is worth keeping: with no index over the edges, one linear
pass over the 948,465 vertices costs 2 ms, so a recording matched naively is 2.9
to 10 seconds of frozen main thread. Anything added to the matcher that walks the
geometry rather than asking the grid puts that straight back, and it will not
look like a fault, because the result works.

**Time it on the whole corpus and quote the worst, not the median.** 35 tracks
under `.cache/downloads/ut/`, median 1,443 points and largest 5,147. A phase that
reports one number for matching has measured one track.

**Then the trap that has already cost this project once, and the half of it that
was not in the trap.** A track beside a parallel path snaps to the wrong one on
distance alone — 23 % of `attach_nearest` matches followed their road for under
half its length before `min_overlap`. That rule is in, and so is its converse,
which `attach_nearest` never needed: **a routed stretch may not be longer than
the recording it replaces.** Without it the 42.44 km Rundtur came back at 48.2.
Any change to the matching must keep both, and the corpus total is the test —
376.3 km recorded, 372.8 matched, nothing longer than its own recording.

**A loaded plan must ignore its generated waypoints.** 6B marks every one
`origin=generated`. Load a route this map exported with boundary markers in it
and count the waypoints that come back: more than were set means the route gained
stations nobody placed, and it will route through them. The reader takes a
waypoint that says `set` or says nothing at all, and skips everything else —
counting *this map placed it* and *this page does not know this word* apart,
because a file from a later build is worth saying out loud.

**It reads and writes the same format, which nothing else here does.** A fixed
leg is a fifth `<trails:part kind>`. Check both directions: an older file still
loads, and a file carrying the new kind says something a reader can act on.

**And the figures.** 11,589 paths with exactly one non-interactive, 25 layers,
10 px above 60, wheel 9 → 11, the plan's panes at 8 paths and 203 markers with
five points, the chain export at 16,415 points reading its ascent back to 0.00 m,
and the graph untouched at 11,290 / 234,358 / 116,967.

**This is the last phase, so the temptation to write *nothing is open* is
strongest here.** That sentence has been written eleven times in this document
and has been wrong every time — and it is wrong now: a part is a whole edge, so
3.5 km of the corpus is kept as recorded where the network does carry it, and
`.leaflet-marker-icon` and the recorded-ground bucket are both new surfaces
nothing downstream has been read against yet.

Round-trip one of this map's own exports and check it comes back identical —
that is what the `<extensions>` exist for.

## The question that found the expensive gaps

Both of the specification's serious omissions were found the same way, by asking:

> **What is visible on the map but missing from the graph?**

Ferries came out of it — they were drawn all along and had been silently passed
over because nobody walks a ferry, which would have cut off the entire western
approach and eleven of seventeen quays. Free legs over water came out of the same
question one step further on.

Ask it again against the inventory below before accepting that a phase is
complete. It is a better instrument than re-reading the specification, which
found only the cheap gaps.

**And ask it of the point layers too, not only the lines.** That was the third
omission and it went the same way: the map draws 104 cabins from N50, nine named
huts from SSR, seventeen quays and eighty trailheads, and nothing in the plan
used any of them. They are not routable and should not be — but a waypoint set
beside one should carry its name into the export, which is now phase 6. The
question is not only "is it in the graph" but "does anything use it at all".

### What the map draws today

Lines, all of which belong in the graph:

| layer | in the graph |
|---|---|
| Roads, public and private [N50+SSR] | yes |
| Ferry crossings [N50] | yes, as crossings — not walking |
| Paths in park and approach [FKB] | yes |
| Paths in park and approach [N50] | yes |
| Paths in park and approach [OSM] | yes |
| Marked and DNT routes [Turrutebasen] | yes, keeping their published unit |
| Routes and access routes [UT.no] | yes, keeping their published unit |

Points, none of which are routable and none of which should be:

Cabins and wilderness huts [N50] · Named huts [SSR] · Huts and shelters [OSM] ·
Quays [SSR] · Ferry quays [OSM] · Trailheads, farms and sæters [OSM] · Towns and
villages [OSM] and [SSR] · Farms and holdings [SSR] · Terrain names [SSR] ·
National park boundary [Naturbase]

That inventory was complete at `ec9ec7f` and still is, with one addition: the
place-name layer now also draws `bakke` and `mo`. If a layer is added later, it
has to be asked the question above.

**And ask the same question of the specification, one level up:** *which phase
receives this?* That is the inverted form, and it has found two things the
inventory question could not, because neither was ever on the map — the page
encoding, which was specified over thirty lines and belonged to no phase and is
now 3B, and the popup ascent, which fell between phases 2, 3 and 4. Run it
whenever the decisions document grows.

## Known open, and never asked

Separate from the decisions taken *against* something below. These are simply
unresolved, and a reader should be able to tell the two apart.

All of what stood here has since been settled, and is recorded where it belongs:

- The six build-time GPX files are built from chains from phase 3, and carry
  `<ele>` from phase 5.
- A plan is persisted as its GPX and nowhere else, with waypoints stored as
  **coordinates, never ids**, so a rebuild of the graph cannot orphan it. Loading
  one back is phase 8, with a choice on load between taking the track as it is,
  routing afresh between its waypoints, and matching it onto the network where a
  path exists.
- What happens when the sources change under a plan therefore answers itself:
  it is re-matched against the network as it now stands, and the difference is
  visible rather than silent.
- Snapping a waypoint to a hut or a quay, and splitting a route into days, are
  both after phase 8. Neither is blocked by anything earlier.

That has since been checked and answered: the zone holds 26 nature reserves and
one landscape protection area. None of the reserves touches the park, one —
Strauman — borders it. Phase 6 therefore reports protected areas rather than the
park alone, and `naturbase.Source` needs a spatial query to find them.

**Two came out of phase 7's review, in 6C's and 3B's code rather than in its
own.**

- **A boundary crossed inside a break gets one marker, not a pair.**
  `crossingsOf` restarts its "what was I in" list at every stretch, and a stretch
  ends at every crossing, not only at the route's ends. Walk into a reserve,
  take a ferry out of it, carry on outside: the file says *Enters Sirijorda
  naturreservat* and never says the route left. The rule 6C wrote — no marker
  where a route begins or ends inside an area — reads either way here, and the
  alternative is a generated waypoint at a position on water the track does not
  draw. It wants a decision about what such a marker claims, and then a figure.
- **`PAYLOAD_VERSION` is written and never checked.** `encode_graph` puts it in
  the header and the page's decoder never compares it, so a stale stream would
  be read as a current one and produce a confidently wrong graph rather than an
  error — which is the one thing the constant exists to prevent. Harmless while
  header and stream always come out of one `encode_graph` call. The fix is not
  the obvious one: the header cannot verify itself, so the decoder has to be
  handed the layout it was written for.

**The leg modes are written into every exported plan and no mode reads them
back.** Measured on a route that mixes routed and recorded legs: the file carries
all seven parts with their kinds and metres — `routed 19,884.1`, `track 816.4`,
`routed 1,295.7`, and so on — and loading it returns 42,284.1 m as **one** track
under `asis`, 6,354.9 m re-routed under `align`, or 41,909.1 m in **five** parts
under `match`. None of the three restores it. A **purely routed** plan does come
back bit-identical, because re-routing between the same waypoints reproduces the
same legs, and that is the common case; the gap is exactly a plan holding a
recorded leg.

It matters because the decisions document promises the opposite in as many
words — *"the waypoints let a plan be rebuilt, the modes let it be rebuilt
**exactly** rather than approximately"* — and because the fix is a decision about
the model rather than a repair: a fourth mode that restores, or `asis` taught to
honour the leg list it already receives. **This is the third thing in this
project written and never read**, after `PAYLOAD_VERSION` and the survey fields
FKB does not publish, and it is the only one of the three that a document
promises out loud.

One thing is open, and it is open by decision rather than by oversight:

**FKB's provenance cannot be queried, and FKB carries 90 % of the network's path
evidence.** Its WFS exposes `objtype`, `typeveg`, `vegkategori`, `vegfase`,
`vegnummer` and `kommunenummer` — nothing about how a line was captured or when.
N50, which does expose it, shows 47 % of its paths digitised from a map rather
than surveyed, with capture dates back to 1965 and accuracies to 50 m; and the
two are not independent, both being Kartverket. So "is there a path here" is
unanswerable, and phase 1B builds only the negative form of it. The Geonorge file
download would carry FKB's own `målemetode` and settle it — it needs an account
and a second loading path, which is why the module uses the WFS. That trade is
the open question, and nothing downstream is blocked on it.

One more, small and dated: the `Ukjent` fix showed that a register's word for
*nothing* is worth hunting for deliberately. Turrutebasen's is now excluded.
**No other source has been searched for its own placeholder**, and the same shape
of bug has now appeared three times — `pd.NA` as the text `<NA>`, an empty string
counted by `notna`, and "unknown" read as a name. A sweep of every carried column
for values that mean absence would be an hour's work and is nobody's phase.

Otherwise nothing is known to be open. **That has now been true nine times and
was wrong all nine** — the readiness checks found gaps in 1B, in 3, in 2, in 3B
(which this document had written itself), in 4, in 5, in 6, in 6B and in 6C, and
the 3B review then found the payload gap above. The check that finds them is not
reading the phase; it is measuring it against the built graph. **All eleven have
now had it.**

And the shape has moved. The early checks found *figures* that had drifted; the
last two found **premises** — 6B's *"the composed geometry already exists"* and
6C's *"a free leg gets it from the samples it fetches anyway"*, the second of
them written in the decisions document rather than in the phase. A wrong figure
fails an implementation loudly. A wrong premise sends it in the wrong direction
quietly, and it is the sentence that sounds most like background that is worth
measuring.

## What the profile zoom found

Not a phase. It is the second half of the panel work the true-scale fix started,
and it was the readiness check rather than the build that produced everything
worth writing down.

### The premise did not hold, and it was the whole premise

*Zoom shows detail the drawing is hiding.* Measured over the built graph, per
chain, at the panel's default 1,238 px by 205 px: the median chain is drawn at
**0.16 m/px**, and its series carries a height every **5.12 m**. The panel
magnifies the median chain **thirty times** already. Across all 11,264 chains
with a readable series, exactly **126 (1.1 %)** are drawn coarser than their own
samples — 1,210 km of 5,853. Eight are coarser by more than 4×.

So the feature is not for the map's lines. It is for the 42 km Rundtur, which
stands at 36.28 m/px against a 5.09 m spacing and hides 7.1×, and for the
**planned route**, which in this park is that long by nature. Building it as a
chain feature and testing it on chains would have found nothing wrong and shipped
something nobody could use.

Two thirds of the ratio is height rather than length, incidentally: **5,188 of
the 11,264 are bound by the height and not the width**. Those are the ones the
grip helps, and they are almost exactly the ones the zoom cannot.

### The ceiling is the data's, and it is not a constant

One reading per pixel, and past it the panel magnifies the straight lines drawn
between samples — a claim to resolution nothing supports. In the page that is
`base / spacing`, where `spacing` is the mean over the readable samples: the
mean rather than a median because the series is laid **per edge** and does not
sample evenly, and a median per render costs a sort.

Measured in the browser on the Rundtur, in a 1,400 px window: **6.31×**, taking
5.216 m/px against a 5.182 m mean spacing. Offline over a 1,238 px panel the same
chain gives 7.13× against a 5.09 m median. The two disagree because **the ceiling
is not a property of the chain** — it is the drawn scale over the reading
spacing, and the drawn scale moves with the panel's width, with the window, and
with wherever the reader dragged the grip. Recording 7.1× as a reference figure
would be recording a screenshot.

### The angle survives the zoom, measured rather than argued

By construction one `metresPerPixel` drives both `x()` and `y()`, and a zoom
changes only that number — so the angle cannot move. That is an argument, and
the argument is what a reviewer should distrust, so it was measured at every
step: zoom 1, 2, 4, the ceiling, on two chains, and at the 60 px floor with a
window standing over the box. **Both axes carry the same metres per pixel to six
decimals in every one of them**, and the drawn gradient equals the ground's to
the third: 32.900775 at rest, 5.215927 at the ceiling, 9.021299 at the floor.

Getting that measurement honest took three attempts, and the two failures are
worth keeping:

- **The bounding box of the curve is too blunt a ruler here.** At a true scale a
  chain long enough to zoom into draws as a ribbon twenty pixels tall, so half a
  stroke width is a whole per cent. It gave 0.07 % at rest, which is fine, and
  could not have told a real error from the stroke.
- **The crosshair snaps, and a probe that forgets it measures its own
  assumption.** Aiming the pointer at a chosen sample and then computing with
  *that* sample's height reads whatever neighbour the snap actually chose: it
  produced a steady 0.2 to 0.44 % that looked like a real bias and was entirely
  the probe's. At zoom 1 one pixel of this chain covers six samples, so no
  reading printed to 10 m and 1 m can name which.

What works: read the **horizontal** scale off the distance marks the axis draws —
they carry their own value, and no snapping is involved — then use *only* that
to say which sample the crosshair dot is sitting on, and let the vertical scale
fall out of that sample's height. The scale under test never takes part in
identifying the thing it is tested against. Where the axis cannot name a point
cleanly the probe declines to measure rather than guessing.

**And the printed gradient does not move either**, for a different reason: it is
read over a 25 m window from the full series, which the view never touches. What
the crosshair says at 20.61 km is what it says at every zoom.

### The panel's own shape is a gradient, and it decides what fits

At a true scale the box holds `tall × metresPerPixel` of height and
`wide × metresPerPixel` of length, so a window fits top to bottom exactly when
the ground across it averages gentler than `tall / wide` — **171 over 1,170, or
14.6 %** — and **that ratio does not move with the zoom**. Measured over the six
longest chains: everything fits to 4×, and at 8× three of them stand 108 to 163 m
over, which at that scale is 24 to 36 px.

At the reachable ceiling, with the panel at its default, nothing in this park
overflows: the worst is 534 m of relief over a 5.31 km window against 775 m
carried. It overflows the moment the reader drags the panel **short**, which is
the case the vertical drag exists for. Driven at the 60 px floor: the window
carries 136 m, the relief under it runs to **199 m**, and **412 of 1,368 drawn
points** fall outside the box and are clipped rather than painted over the height
labels. Where the relief does fit — 125 m against 136 — a vertical drag moves
nothing at all, because the middle is pinned. There is no way to drag the curve
off its own panel.

### Two defects in the grip, and one arithmetic behind both

Neither is in the zoom. Both are in the drag that shipped the day before, and
both are the same mistake: **the overhead was measured live, against a number
that had already moved.**

`most = map.getSize().y - (box.offsetHeight - chartHeight) - 80`. The redraw is
coalesced to one a frame, so between the ask and the frame `chartHeight` is the
new height and `box.offsetHeight` is still the old panel. Two moves in one frame
and the second computes an overhead of **minus 620**, a ceiling of **1,440**, and
grants a panel taller than the map. Measured: the panel opened at **900 px on a
900 px map**.

And it is not a corner case, because of the second thing this turned up:
**Firefox reports `clientY` as −86 the moment the pointer leaves the foot of the
window.** Not a clamp to 899, not a stop — a small negative number, which reads
as *dragged far upwards*. A drag that runs off the bottom of the screen therefore
delivers three such moves at once, which is exactly the two-in-one-frame case.

The same arithmetic with the panel **folded** reads 35 px of box against a 205 px
chart: an overhead of minus 170, a ceiling of 990. A click on the map folds the
panel, and a click can land mid-drag. Measured: reopened at **705 px**.

Both closed. The overhead is measured against `laidOut`, the height the panel was
last actually laid out with, and `stretchTo` returns while the panel is folded;
`fold()` drops any drag in progress so it cannot be picked up again later. After
the fix the ceiling holds at **750** from either direction and the floor at 60.

### Two ways the probe lied, and both are the recorded family

**Selecting a chain by firing its click also opens its popup.** `layer.fire('click')`
runs every handler bound to that layer, and one of them is the popup. Leaflet
then auto-pans the popup to the middle of the map — and a Leaflet popup calls
`disableScrollPropagation` on its own content. So a probe that selects a chain
and then turns the wheel at the map centre is turning it **over the popup**, gets
no zoom, and reports that the panel broke the map. It cost twenty minutes and one
wrong conclusion. `closePopup()` after the `fire`, or wheel somewhere the popup is
not.

**And a mouse driven outside the window does not report where it was sent.**
Playwright asked for y = 1,009; the page was told −86. Any probe that drags past
an edge is measuring the browser's coordinate handling and not the page. The way
to test a drag's limits is to dispatch the moves with the coordinates written
down: driven that way the same grip gave 60 at the floor and 750 at the ceiling,
cleanly, before and after the fix.

## What phase 2 found

**The documented 996 m does not reproduce, and the threshold is not why.** All
three digitisations of Sjøbergmarsjruta read near 1,190 m. Before saying so, the
*unthresholded* figure was measured on the same route sampled the same way: it
is 1,370 m against the decisions document's 1,214 m. The filter removes 200 m
here and 218 m there, so the two ascent rules behave alike; the series underneath
differs by some 160 m. Three other readings of "ignore gains under 5 m" were
tried and none lands on 996 m either, and two of them are not invariant, which
the document's own table requires of whatever produced it. The original
measurement scripts are gone, so what was sampled cannot be recovered. **A
predicted figure that cannot be reproduced is worth taking apart into the part
that does and the part that does not** — here the invariance reproduces exactly
and the level does not, and only the invariance was ever the point.

**The route resolves under two names.** UT.no publishes *Sjøbergmarsjruta* and
Turrutebasen *Sjøbergmarsjen*, which reaches FKB through the route-name join. The
first implementation of the check searched for the full name, found one
digitisation of three and printed a table that looked complete. The three chain
ids in the phase document are right; the name in it is one of two.

**A cache key covering only the inputs is half a key.** The elevation parameters
went into the fingerprint, so phase 1's graphs rebuilt — but when descent and the
high and low point were added afterwards, nothing about the *inputs* changed and
a cached graph without those columns was served to code that reads them. The
fingerprint now also carries a `GRAPH_LAYOUT` marker, bumped when a build starts
producing something a cached one does not carry. Worth remembering as a shape:
the digest of what went in cannot notice a change in what comes out.

**−43.9 m is real ground.** The lowest reading in the network is an N50 road
descending into a quarry — `datakilde: "dtm1"`, `terreng: "Steinbrudd"` — not an
unchecked depth contour. 580 of 1.4 million samples are below sea level, on 28
edges, and nothing is anywhere near −276 m. So the coastal check needs a second
question after "is it negative": *what does the endpoint say it read it from*.

**A chain's series is laid out of its edges', not sampled again.** Sampling the
chains separately would have doubled the requests for the same numbers, because
every edge already samples both its ends. Two independent constructions agree to
5 m over a 20 km route, which is what says the walk and the orientation are
right; the check is worth repeating if either is touched.

## What phase 4 found

**Everything measurable held.** Payload 4.12 MB, 198 markers, 11,589 paths with
exactly one non-interactive, 25 layers, wheel 9 → 11, no page errors. The panel's
series matched Python's `chain_series` over thirteen chains — the longest at
8,191 samples, a ring, a ferry, both blank stubs — same length, same gap
positions, worst deviation **0.0500 m**, which is exactly half a quantum. The
compass point agreed with Python on all **241** chains within half a degree of a
boundary. The popup reconciles to the entry: **11,267** ascent rows, one per
chain with a height, and **11,226** direction rows, which is those minus the 41
rings; the 23 missing bearings are the 21 ferries and the two blank stubs.

**The profile was drawn dashed, and the data was fine.** A user asked why a
6.5 km chain came out as a dotted line. It has **zero** gaps. `drawCurve` reduces
to one point per pixel column once the samples outnumber the columns, and it
lifted the pen on every column no sample happened to land in:

    2,532 samples · 1,977 columns · 285 columns empty · 222 separate strokes

An empty column is **not** a gap. Samples are laid per *edge* — every edge gets
at least two, whatever its length — so a chain of short edges clumps them and
leaves holes elsewhere; just above the switchover the ratio is barely one sample
per column. The phase warned about the neighbouring case, bucketing 36 samples
into 900 columns, and that corner *was* guarded. **The hole had simply moved to
the band next to the guard.** Fixed by skipping empty columns and lifting the pen
only where the model read nothing: 222 strokes → **1**, while a chain with nine
real gaps still comes back in three pieces.

**Nothing anybody had checked would have caught it.** The agent compared the
series; I compared the series; both were right. Nobody compared the *path drawn
from* the series. The probe that catches it is one line — `d.match(/M/g).length`,
which must be 1 for a chain with no gaps and was 222. **Verifying the data
reached the page is not verifying what the page drew with it.**

Two more, and one of them was mine:

- **The compass point was named twice**, in Python and again in the page, with
  the two rounding rules matched by hand and a comment saying why. It worked —
  0 of 241 boundary chains disagreed. But the phase forbids exactly this shape
  for ascent, and a rounded label is a threshold like any other. The label now
  travels as `point` and the page names nothing; a test fails if it starts again.
  Carrying it is also what makes rounding the numbers safe, so the table dropped
  from 2.32 to 2.07 MB — it had been writing `17.339999999999996` for a figure
  shown as whole metres, eleven thousand times.
- **I broke a figure while correcting figures.** Phase 4 said the bearings run
  N 15 %, NE 28 %, E 21 %, SE 23 %, S 13 %. The readiness check "corrected" that
  to N 16 % and S 12 %, measured with a `cos(mean latitude)` approximation
  instead of the projection — and the *original* was right: 14.7, 28.2, 21.2,
  22.9, 12.7. Two other figures moved the same way, 237 → **241** and 4,485 →
  **4,444**. **The shortcut was taken in the very commit that corrected four
  stale figures for having been derived rather than measured.**

## What phase 8 found

**Every acceptance figure reproduced and none of them moved.** With no route
down: 198 markers, **11,589** paths with exactly one non-interactive, 25 layers,
the search 10 px above the zoom at 60, the wheel 9 → 11, the plan pane 0. With
five waypoints down: the plan pane **8 paths** and the marker pane **203**, with
`.leaflet-marker-icon` at 5. The graph is unchanged at 11,290 chains, 234,358
edges, 116,967 nodes. The chain export still holds at **16,415 points**, 123
without an `<ele>`, its ascent reading back to **0.00 m**. No page errors on any
run. The page went from **37,780,664 to 37,850,638 bytes** — 70 kB, all of it
script, and it stays 37.8 MB.

**The round trip is exact, to the last bit.** A five-point route exported and
loaded back aligned comes home at `7265.882765177558` m walked against
`7265.882765177558`, ascent `1078.9098510742188` against
`1078.9098510742188`, 2,005 vertices against 2,005, five waypoints identical to
seven decimals, and four legs all `routed` as they went out. Written out again
it is the same file: 6 `<wpt>`, 5 of them `set`, 2,939 trackpoints. **The one
generated marker is skipped and said so** — *1 marker this map placed, skipped*.

### The first work was the index, and here is what it cost

29–42 ms to build, 799,863 entries over 613,278 cells, **8.85 MB**, and **0.7
microseconds a lookup** looking at 159 of the network's 714,107 segments.
Against the 2 ms linear pass the page had before, a lookup is some **2,800 times
cheaper**, and that is the whole of why a 5,147-point recording is matched
between two frames. Built on the first thing that asks and then kept: a reader
who never loads a file never pays for it, and `state().index` is `null` until
something does.

Three cell sizes were measured in the built page before one was chosen:

| cell | build | entries | per lookup | segments looked at |
|---|---:|---:|---:|---:|
| 50 m | 49 ms | 902,548 | 1.4 µs | 119 |
| **100 m** | **29 ms** | **799,863** | **0.7 µs** | **159** |
| 200 m | 31 ms | 754,842 | 0.7 µs | 242 |

The smaller cell loses on both counts, which is the part worth keeping: halving
the cell quadruples the cell count, and laying down the extra entries costs more
than the shorter scan saves.

**And what a whole load costs, over all 35 recordings and all three modes:**
median **37 ms** wall clock and **67 ms** at the worst, of which the settle —
from the file being handed over to a route drawn and every leg worked out — is a
median of 15 ms and 54 ms at the worst. Nothing here needed cutting into pieces,
which is a figure and not a hope: the largest recording is 5,147 points and the
largest file loaded is the 16,415-point chain export, which settles in 116 ms.

### The corpus is not foreign to the network, and that changes what it proves

**All 62,158 points of the 35 UT.no recordings lie at distance 0.0 from the
graph** — p50, p90, p99 and the maximum, every one of them 0.0. They are not
merely near it: UT.no *is* one of the graph's six sources, and these 35 files are
the ones it loads. The readiness check called them *genuinely foreign*, which is
true of the file — consumer GPS, timestamps on every point, no `<wpt>`, no
`<extensions>` — and false of the geometry.

Two consequences, and they pull in opposite directions:

- **It is the strongest ground truth a matcher could be given.** The right answer
  is known exactly, so anything short of matching end to end is a defect rather
  than a judgement call. Both of the two real defects below were found that way.
- **It cannot, by itself, exercise *keeps its own shape where no path is*.** With
  UT excluded 96.97 % of the points still lie within 25 m of another register's
  line, because FKB and Turrutebasen braid against UT.no — *Sjøbergmarsjruta* is
  drawn by all three, all 20.48 km of it, over the same ground.

**Before declaring a corpus foreign, measure its distance to the thing it is
meant to be foreign to.** The readiness check asked whether the files were
obtainable and answered well; it did not ask what was in them.

What rescued the acceptance was not a new corpus. Three recordings keep ground of
their own after matching — 1,038 m, 256 m and 2,164 m — for the reason in the
next section, and the map's own writer supplies the rest: a route exported as
recorded and loaded back carries `<trails:part kind="track">` and comes home as
recorded, which is the same claim tested from the other end.

### The two defects, and both were the graph rather than the matcher

**A recording out in the terrain is one edge, because noding cuts only where
lines meet.** Edge length here is median **6.9 m** and 49.3 m at the 90th
percentile — but **1,141 of the 234,358 edges are over 500 m** and UT.no's
longest is **4.7 km**, with thirteen over 500 m. (The 18.5 km edge is a ferry
crossing and belongs to a different sentence; the longest *walked* edge is 6.8 km
of OSM.) Trip 1113935 lies end to end on a single 4,729 m
UT.no edge and turns round 332 m short of its far end. Anchoring to the nearer
end of the matched edge — reasonable at the median, where the nearer end is a
dozen metres away — put an anchor at a place the walker never stood, and routing
to it handed back the whole edge. **The route came back 332 m longer than the
walk.** The rule that fixes it is one line and states something worth stating: an
anchor is a node the recording passed *within the tolerance of*, so a routed
stretch runs between two places it demonstrably stood.

**And `min_overlap` is one-directional, which is half a test.** It asks what
share of the recording lies along the path offered to replace it — exactly
`attach_nearest`'s rule — and a path that runs along the whole recording *and
then goes somewhere else as well* passes it. Measured: the 42.44 km *Rundtur*, a
round trip whose own line crosses itself, came back at **48.2 km**. At the
crossing the router took the wrong branch while still lying along the recording
everywhere it was asked about. The other half is a length: a routed stretch may
not exceed the recorded stretch it replaces by more than the tolerance at each
end. With both halves in, **no recording in the corpus comes back longer than it
was recorded** — 376.3 km recorded, 372.8 km matched, and 99.1 % of the ground on
the network's own lines.

**Neither of these is deducible from `attach_nearest`, and both are the same
shape of mistake.** That function joins whole features of comparable size, so it
never has to ask whether the counterpart is *longer* than the thing it is
attached to, and it never meets a counterpart kilometres long. The lesson it
teaches — proximity alone is a weak test for lines — is right and is not the
whole rule when one side of the pairing is a network.

### The one that cost the most, and it was invisible to every check

`PLAN.matchAnchorM` was read by the matcher and left out of `PLAN_SETTINGS`.
JavaScript has nothing to say about that: `along[i] - since < undefined` is
`false`, so every recorded point became an anchor, and **the matcher matched
3.6 % of a track that lies exactly on the network** — 269 m of 7,420. Nothing
threw, nothing logged, `make check` was green and the page looked right.

The test that should have caught it exists and runs the other way:
`test_every_setting_the_template_reads_is_one_it_insists_on` walks
`PLAN_SETTINGS` and asserts each name appears in the rendered page. **A contract
checked in one direction is not checked.** The converse is now a test of its own
and it fails on exactly this: strip `matchAnchorM` from the list and it names it.

### The claim the file was making about somebody else's numbers

A route made of a loaded recording credited **Høydedata DTM1** and stated
`ascentMethod: DTM1, sampled every 5 m, gains under 5 m ignored`. Every height
in it came off the reader's own trackpoints and this map never asked the service
about a metre of it. The file was naming Kartverket for a consumer GPS reading,
in a document somebody takes into the terrain — which is the precise claim the
`ascentMethod` field exists to stop being made by accident, made by the field
itself.

Found by reading a written file rather than by any check: `heightsWritten(runs)`
asks whether the file carries heights, and *where they came from* is a different
question that nothing had needed to ask before, because until this phase every
height on this map came from one place. A part now says which, the shape carries
`modelled` and `fromFile`, and the model is credited and its method stated only
where it was actually read. Where it was not, the description says so —
*the climb is the loaded file's own heights, not the model*, and *part of the
climb…* for a route that is some of each. A route with nothing of this map's in
it now writes no source list at all rather than `Sources: ` and a blank.

**The general form is worth keeping**: a field that has only ever had one
possible value is not a field anybody has checked. There was exactly one source
of heights for seven phases.

### What the review found, and what was done with each

Eight, and **the first three were the same mistake in three places**: a waypoint
anchored to the recording carried no node, so every leg with one anchored end and
one ordinary one fell past the routing test and was drawn straight over the
terrain. It never showed in the acceptance because both files driven there were
pure — every leg recorded, or every leg routed — and the defect only exists where
the two meet.

1. **A leg beside a recorded one was drawn straight, never routed.** Confirmed in
   three shapes: extending a loaded recording by clicking gave a straight line
   instead of a path, dragging an anchored waypoint made *both* its neighbours
   straight rather than "ordinary" as the comment beside it claimed, and — worst
   — a mixed route reloaded aligned came back with every routed leg beside a
   recorded one turned into a straight line, silently breaking the round trip
   this phase is built on. **Fixed**: an anchored waypoint now carries the node
   the recording reached, within the *match* tolerance rather than `snapM`, so a
   routed leg laid from that node steps at most 25 m — the same seam the matcher
   already leaves. Measured after: extending reaches `routed:1434` where it drew
   `land:1302`, a dragged waypoint's legs come back `routed`, and the mixed route
   returns `track:3470 · routed:3921`.
2. **A leg spanning a track break drew a walked line across the gap.** Only a leg
   that was *nothing but* a break was treated as a crossing, and phase 7's Remove
   merges the two legs either side of one in a single click. The result walked
   straight across and counted the gap as recorded ground — the one failure the
   whole crossing distinction exists to prevent. It also disagreed with
   `loaded.along`, which does not advance across a break. **Fixed**: every break
   inside a leg is a crossing, in both modes. Measured: removing the waypoint
   that ended a segment now gives `['track:1209', 'water:130']`, one crossing,
   130 m crossed, and the walked figure does not move.
3. **A recorded leg was anchored from where its waypoint had snapped to, not
   from what the file wrote.** `snapped` moves a waypoint up to 150 m onto the
   network before the lookup ran, and on a switchback the nearest recorded point
   to *that* is on another pass. **Fixed**: it reads the written position, and it
   may now decline — a waypoint of a recorded leg is written at the recorded
   point or at a named thing within `namedM` of it, so that is exactly how far it
   looks.
4. **A refused second file dropped the recording the route was still anchored
   to.** `loadGpx` refuses before it touches anything, so nulling it in the catch
   destroyed a good recording and the next edit turned a recorded stretch into a
   straight line with nothing said. **Fixed**: what is on the map stays.
5. **A `<trkseg>` holding one point made two waypoints on one position** — a leg
   of no length, an extra pin, and a request to the height service about nothing.
   **Fixed**, by collecting the indices first and never taking one twice.
6. **The break count came off the `<trkseg>` elements rather than the breaks.**
   An empty segment leaves no break, and the page said *2 breaks* where there was
   one. **Fixed**: counted.
7. **A `<trails:part>` with no `kind` was reported as a kind called `null`**, and
   the table of known kinds was an object literal, so `constructor` read as
   known. **Fixed**, and the table has no prototype — the same rule every other
   table here keyed on somebody else's words already follows.
8. **A test did not exercise the branch it documented.** `gpx=None` drops the key,
   so the `PLAN_SETTINGS` check fired first and the new one was never reached.
   **Fixed**, with `gpx={}`.

All eight were real and all eight were taken. **Every acceptance figure was
re-measured afterwards and none moved.**

### Three more, cheaper but not free

- **`DOMParser` logs a console error the page cannot suppress.** A file that is
  not XML produces *XML Parsing Error: syntax error* attributed to the page's own
  URL, before `parsererror` is found and the file refused with a sentence. The
  handling is right and the log is unavoidable; a probe treating `console.error`
  as failure reads it as one, which is the twin of the `elementFromPoint` trap —
  the probe is wrong, not the page.
- **A matched route restores exactly through *as it is* and not through
  *aligned*, and that is what the modes mean.** Written out and read back as
  recorded it comes home to `7307.4335` against `7307.4358` m — 2.3 mm over
  7.3 km, which is the file's seven decimals — and its ascent to 0.15 mm.
  Aligned, the same file comes back at 7,266 m: align mode routes between the
  waypoints, a matched route has two of them, and the cheapest path between two
  points is not the concatenation of the cheapest paths between the anchors
  along it. Nothing is wrong; a matched route's geometry is not derivable from
  two waypoints, and the file carries the geometry for exactly that reason.
- **`getElementsByTagName` matches the qualified name in an XML document.** A
  file spelling this map's namespace `t:` rather than `trails:` says the same
  thing and would have been missed entirely. Everything is addressed by
  namespace and local name, and the GPX elements under `'*'` so that a consumer
  device leaving the default namespace off still loads.

### What was deliberately not built, and what it would take

**Matching a part of an edge.** A part is a whole edge, so a recording that
walks half of a long one is kept as recorded rather than half-matched. On this
corpus that is 3.5 km of 376 — and it is the whole of the difference between
99.1 % and 100 %. Doing it would mean slicing an edge's geometry *and* its
height samples at two positions, apportioning its marking and its protected
shares by length, and a part that no longer stands for an edge — which is what
`tallyOf` consumes. It is a real extension of the model rather than a tuning
change, and it belongs to whoever wants the last percent.

## What phase 7 found

**Every acceptance figure reproduced, and the two the phase said would move
moved as it said.** With no route down: 198 markers, **11,589** paths with
exactly one non-interactive, 25 layers, the search 10 px above the zoom at 60,
the wheel 9 → 11. With five waypoints down: the plan pane **13 paths → 8** and
the marker pane **198 → 203**. The graph is unchanged at 11,290 chains, 234,358
edges, 116,967 nodes; the chain export still holds at **16,415 points**, 123
without an `<ele>`, its ascent reading back to **0.00 m**; `.cache/elevation/`
is byte-identical at 15,558,926 bytes with its mtime untouched. No page errors
on any run. The page went from **37,747,960 to 37,780,664 bytes** — 33 kB, all
of it script, and it stays 37.7 MB.

**A third figure moved with them, and it has to be said rather than found.**
`.leaflet-marker-icon` reads **5** with a five-point route where it has always
read 0. It is the same fact as the 203 seen through a second probe: that entry
exists in the table because *folium* overwrites Leaflet's class on its own
markers, and phase 7's pins are Leaflet's own `L.divIcon`s, which carry it.
Keeping the probe at 0 would mean stripping a framework class off our own
markers to make a number come out, which is exactly the kind of thing that bites
two phases later.

### The three decisions, and what decided them

**One click, three meanings, and no mode and no modifier.** A click on a pin
selects it, a click within **8 px** of the drawn route puts a waypoint into that
leg, and a click on anything else puts one on the end. All three are decided in
the one capture-phase handler on the container that already sees every click —
Leaflet never gets to see it, so a pin's own click handler could not have been
used even if it were wanted.

Two things follow and both were chosen against the alternative. **Nothing the
route draws became interactive**: the leg a click landed on is found by
hit-testing the geometry the page is already holding, because a line that
catches clicks would have to be switched off again the moment plan mode is, or
the route would stand between a reader and the trail underneath — the mistake
the park boundary made for a fortnight, and one switch too many to remember. And
**a click on a pin selects rather than deletes**: the same click is a few pixels
from one that places a point, there is no way back from a deletion, and what a
selection makes possible — remove, move a place earlier, move a place later —
has to be visible somewhere anyway, because dragging a pin moves it on the
ground and says nothing about where it comes in the sequence. Reordering needs a
gesture of its own and only one of the two can be a drag.

**The pins had to be lifted above every other marker, and only the browser said
so.** Leaflet stacks markers within the pane by latitude, so a hut drawn where a
waypoint stands covers it: measured at the first waypoint of a route along a
chain, `document.elementFromPoint` returned folium's own `awesome-marker`. That
click would have missed the pin, fallen through to the route under it, and
**inserted a waypoint where the reader meant to select one**. `zIndexOffset` is
100,000 rather than a small number because the term it is added to is a pixel
position, not an index.

**A live drag asks the height service for nothing, and that is measured.**
Driven with a real pointer over the icon and every request to the endpoint
intercepted and counted: **0 requests while the pointer is down**, 99 the moment
it is let go over open ground. There is no abort — the requests are simply not
issued — because aborting would have to poison the endpoint cache the decisions
document asks for, and a cancelled promise sitting in it would answer the next
identical leg with a failure.

A leg the network cannot carry is carried through the drag at its own straight
length with no heights read along it. That keeps the walked distance right under
the reader's hand — measured over one drag: 23.2, 21.8, 22.1, 25.5, 29.8,
34.3 km, following the pointer — while the leg counts as **unsettled**, so the
sentence above the button says *Still working out 2 legs* and the file stays
refused. What it does not carry is a protected-area tally: that is read off the
height samples at the halfway rule the shoreline split already uses, and there
are no samples yet. Inventing one at a coarser spacing would be a second rule to
disagree with the first.

**And the throttle, timed in the page rather than by the probe.** 80 mouse
moves over 1,443 ms settled the route **12 times**, and the gaps between them
read 117, 123, 114, 124, 115, 115, 122, 118, 123 ms — the constant, measured. The
trailing timer is what puts the last settle where the pointer came to rest.
Before this there was no throttle and no cancellation anywhere in plan mode.

**Each settle is two panel updates and only the second is ever seen.** The first
comes when the legs beside the waypoint are replaced and have no parts yet, and
it composes a route missing them — 9,948 m of the 20,213. The second comes 3 to
7 ms later when they resolve. It never reaches the screen: a leg settles in a
microtask, and microtasks drain before the browser paints. That holds only
because a live drag fetches nothing — a leg waiting on the network would paint
the hole. It is another reason for the rule, and worth knowing before somebody
moves the fetch back into the drag to make the profile "more responsive".

**The optimisation went where the phase said and nowhere else.** Routed legs
recompute in full — a five-point route's four legs are about 200 ms and nobody
notices. The free-leg cache is where the work went, and it gained two things: it
is **keyed on the pair rather than on the order**, and it is **bounded at 64
entries**. Measured: a free leg costs 4 requests the first time; moving its two
waypoints past each other, which turns it round, costs **0**; leaving it and
coming back to the same ground costs **0**. Every reorder of one place turns
exactly one leg round, which is why this is worth having and reversing a *routed*
leg's parts is not.

### One rule, four edits, and the cancellation for free

**The legs follow from the waypoints rather than being edited beside them.**
Every edit rewrites the list of points and nothing else; a leg survives exactly
when it still runs between the same two waypoint *objects*, and a waypoint that
has moved is a new object rather than a mutated one. Insert costs the two legs
that replace one, remove the one that replaces two, a move the three that touch
the point, and a drag needs no case of its own.

The cancellation is that rule read backwards, and it is one line: a reply about
ground a waypoint has since left arrives to find `legs.indexOf(leg) < 0`. There
is no token and no generation counter, because there is nothing for one to
disambiguate.

### What the edits actually did to a route

Along one chain, five waypoints, 20,212.893 m:

| | | |
|---|---|---|
| insert on the drawn route | 5 → 6 points, 4 → 5 legs | **20,212.878 m** |
| remove it again | back to 5 | **20,212.893 m**, bit for bit |
| move a point one place later | order changes | 31,720.9 m |
| move it back | | **20,212.893 m**, bit for bit |
| drag a point and let go | | follows, and the pin sits on the waypoint to the pixel |

**The 1.5 cm the insert costs is not float noise and is worth knowing.** An
inserted waypoint snaps to the nearest *node*, by the same rule a click has
always used — a route can only be split at one. Clicked at a vertex of the drawn
route, `12.817694, 65.637221`, it snapped to node 35382 at `12.817693,
65.637221`: one unit of the payload's 1e-6 quantum apart, which at this latitude
is **4.6 cm**. Diffed vertex by vertex, the route through the node drops that one
vertex and its neighbour 3.8 m back and is **2.9 cm shorter** over the
4.2 km leg; everything either side is identical. It is the right answer rather
than a rounding — the waypoint is on the network, which is where a waypoint goes
— and removing it again returns the route bit for bit.

### The file, against the route it was drawn from

After an insert, a remove, a reorder and a drag on one route: 5 set `<wpt>`
before the `<trk>`, each carrying `origin`, the 4 legs on the track, one segment
because there are no crossings, 12,203 trackpoints. The track's own points
measured back in Python with the page's own metre come to **29,921.38 m against
the 29,921.34 the page states — 3.8 cm over 29.9 km** — and every set waypoint
matches its position to seven decimals. A separate route validates against the
shipped GPX 1.1 schema with 6 set and 2 generated waypoints and its protected
area reported at 28,179 m, over the 100 m threshold.

The export needed nothing, as the phase said: it is written from `composeRoute`
and follows whatever is drawn.

### What the review found, and what was done with each

**Three findings, all in code phase 7 did not write, and one was taken.**

**Taken: a lookup memoised before there was anything to memoise.** `graphAreas()`
guarded on `if (!areasById)`, and an empty lookup is an object like any other —
asked once before the graph's own block had run, it would have stayed empty for
the life of the page and every route through a protected area would then have
thrown *the route lies in X, which the page has no entry for*, out of
`composeRoute` and so out of every refresh. It is **not reachable in this page**:
`protectedAreas` is assigned in the graph's block before its stream is inflated,
and the one entry that composes a route with nothing down — `state()` — runs
after it. The guard now tests the table it is built from rather than the memo,
which costs a length comparison and closes the class.

**Not taken, and recorded instead: `crossingsOf` restarts at every stretch.** A
route that walks into a reserve, boards a ferry that carries it out, and
continues outside gets an `Enters` waypoint and no `Leaves`. That is 6C's rule
applied per stretch rather than per route, and it is arguable *either* way — a
walker never crosses that boundary on the ground, and the only place a closing
marker could go is a position on water the file deliberately draws nothing at.
Changing it moves 6C's measured marker counts and is a decision about what a
generated waypoint asserts, not a defect in this phase. Under *Known open*.

**Not taken: `PAYLOAD_VERSION` is written into the header and never read.** True,
and the constant's own docstring promises otherwise. Honouring it needs the
*decoder* to carry the version it was written for, independently of the header it
is checking — the header cannot verify itself. That is a change to the payload
contract, and this phase's acceptance is that the graph is not touched. Under
*Known open*.

## What phase 8's readiness check found

**The assumption the whole phase rests on holds, and it was ten minutes.** A page
served from `file://` may read a file the reader picks: `<input type="file">`
plus `FileReader` returned all **1,197,976 bytes** of a chain export and
`DOMParser` found its trackpoints. Nothing else about this phase would have
mattered if it had failed — the same shape as the height-service check before
phase 6, and the same ten minutes.

**The matcher the phase named cannot be used where the work happens.**
`attach_nearest` with `min_overlap` is in `trails.utils.geo`, it is Python, it
takes GeoDataFrames, and it copies attributes **between two datasets**. Loading
happens in the page, on one track against 234,358 edges. The rule it teaches —
check that a line runs *along* its counterpart rather than merely near it — is
exactly right and is the reason the function is worth reading. The function is
not a component. **A phase naming a function is not the same as a phase naming a
mechanism**; ask which language it is in and what it takes.

**And the page has nothing to match with.** Measured: `nearestNode` is a linear
scan over 116,967 nodes at **0.135 ms**, and over the edge geometry there is
nothing — one linear pass over the **948,465** vertices costs **2 ms**. So a
foreign track matched naively is **2.9 s** at the corpus median and **10 s** at
its largest, on the main thread, before a single overlap test. The first work of
this phase is an index, and the phase called it *the ends are cheap*.

**This map writes two kinds of GPX and the phase treated them as one.** Measured:
a chain export carries **0 `<wpt>` and 0 legs** and its `chain_id`; a route
export carries **29 `<wpt>` and 4 legs** and no id. *"Anything this map wrote
restores exactly"* is therefore true of a plan and false of a chain, which has no
waypoints to route between. That is a third case and it was not among the three
modes.

**A fixed leg is a fifth kind, and 6B fixed the file format around four.** The
page knows `routed`, `land`, `water` and `ferry`. *"The whole track becomes one
fixed leg"* is none of them, and since 6B writes every part as
`<trails:part kind>`, a fifth changes what an exported file says — in a phase
that both reads that format and writes it.

**The acceptance could not be run, for the second time in this project.** *"A GPX
from Komoot loads"* — no account, no network. Phase 5's check found exactly this
and recorded that a phase whose acceptance its builder cannot execute has no
acceptance at all; two phases later the same sentence had been written again.
**Ask of every done-when whether the person writing it could run it today.**

**The replacement was already on disk, which is the part worth remembering.** 35
UT.no recordings under `.cache/downloads/ut/`: **62,158 points**, median
**1,443**, largest **5,147**, with **no `<wpt>`, no `<extensions>` and a
timestamp on every point**. Genuinely foreign, genuinely consumer GPS, fetched
months ago for a different reason. **Before declaring a test corpus
unobtainable, look at what the build already downloads.**

## What phase 7's readiness check found

**The first finding was what the phase did not say.** Thirteen lines and **not
one figure** — every other phase carries measured numbers its implementation is
held to, and this one carried none, so a review would have had nothing to check
it against. *A phase with no figures cannot fail, which is not the same as being
right.*

**The acceptance tested a mechanism the requirements never asked for.** *"The
distance keeps up while dragging"* — and the body listed insert, delete and
reorder. The decisions document's own numbered requirement is *"waypoints can be
reordered and removed"*, with dragging appearing nowhere but an aside about
caching. This is the inverted question run the other way: not *which phase
receives this requirement*, but **where did this acceptance criterion come
from**. Worth running on every phase's done-when.

**A waypoint cannot be dragged as it is drawn, and fixing it moves two figures
every review checks first.** Measured in the built page: a waypoint is an
`L.circleMarker` in the plan's pane with `interactive: false`; added to the map
its `dragging` is **undefined** and `draggable: true` is silently ignored, while
an `L.marker` gets a live handler with `enabled() === true` and lands in the
marker pane. So a draggable waypoint is a marker, and a five-point route goes
from **13 paths to 8** in the plan pane and from **198 to 203** markers. Both
have been reference figures since phase 3. **A phase that will move an acceptance
figure has to say so before it is built**, or the review that follows reports a
regression and is right to.

**Nothing the plan draws can be clicked** — measured, all 13 paths of a
five-point route are non-interactive. Deleting a waypoint needs the opposite, and
an interactive pin catches the click that currently falls through to the map,
where a click *places a new waypoint*. Two gestures, one event. The trap list
already holds the shape from phase 3's boundary polygon.

**Dragging over a free leg is an uncapped request stream, and nothing in plan
mode throttles or cancels.** Measured: the only `setTimeout` near it is the
search box's 150 ms debounce and a retry backoff. The decisions document
anticipated half — *cache them by their two endpoints* — but a cache only helps
for ends already visited, and a drag crosses new ground continuously. **6B's
review had already found this shape once**, an unbounded number of requests from
one misclick, and capped it at 20 km.

**And the optimisation the phase asked for was right for the wrong reason.**
Measured: placing a point costs **19–76 ms** including its Dijkstra, and
`state()` with the whole route composed costs **3 ms**. A full four-leg recompute
is about 200 ms — perceptible, not a problem. *Recompute only what changed* buys
nothing worth writing down for routed legs; it is essential for free legs, which
are seconds of network, and for a drag, which recomputes many times a second.
**An optimisation with the wrong justification gets applied in the wrong place.**

What is already there and needs nothing: the free-leg cache by endpoints, and an
export that follows what is drawn because 6B writes it from `composeRoute`.

## What phase 6C found

**The readiness check was right about all three missing mechanisms and wrong
about one figure it did not name the extent of.** 741.2 km reproduced to the
decimal, and so did every per-area kilometre; but the numerator is measured over
the walked network **with** its 8,684 inferred connectors, at 5,899.9 km, and
5,853.3 is the same network without them. A figure and its denominator drawn from
two populations, one line below the paragraph correcting 26 against 39 for
exactly that. Both are printed now, each saying which. **The lesson keeps needing
relearning in a new place: when a figure is written next to another figure, check
they are about the same thing.**

**Three claims in the specification were measurably wrong, and one of them would
have shipped.** *10 m lies inside the ±5 m the sampling accepts* — it does not:
Douglas-Peucker at 10 m moves this register's boundaries by up to **16.1 m**, at
5 m by **5.9 m**, and the difference is 0.02 MB on a 37.5 MB page. Built at 5 m,
and the two generated markers of a route through the park then sit **0.01 m and
0.42 m** from the boundary at full precision. *Five of the nineteen are met over
less than 400 m* — seven are. *No reserve touches the park* had already been
corrected to two; there are **three**, Strauman as well, and measured over all
thirty-one **no two overlap in area**, which is the property that lets the
figures be added up and which nothing had checked.

**The samples were the wrong instrument, and the decisions document had named
them.** *Decide it at the 5 m samples, the park share is how many fell inside
times five metres* — that is a count times a step where a length is available: a
boundary is a legal line with a published geometry, and the answer is
`shapely.intersection`. It is also what makes 5 m of Innervisten a figure rather
than an artefact. The samples decide it in exactly one place, a leg the reader
drew straight, where there is no edge and nothing else can.

**And a real distinction the readiness check did not reach: a share, not a
length.** Python measures these metres in EPSG:25833 and the page measures its
own distances from the ellipsoid, 0.03 % apart. Carried as metres a route lying
wholly inside one area states more ground inside it than it walked altogether —
a figure and its own subtotal disagreeing, in the sentence a reader trusts most.
The payload carries the share of each edge and the page multiplies by the length
it measured itself. Measured against the exported track: **34,014.2 m stated,
34,001.9 measured in Python off the file's own points.**

**The check that lied, and it took an hour.** Intersecting the 14,681-point
exported track with the park as one line reads **31,023.8 m** where two
independent measurements of the same thing — midpoint containment per step, and
segment by segment — both read **34,000**. GEOS nodes a line before it overlays
it, and a track that retraces itself loses the repeated pass. It sent me to look
for a 3 km bug in the page that was not there. **A cross-check is a measurement
and needs checking like one.**

The same artefact bites the build, and by how much was measured: **67.5 m in the
647.8 km** the walked network spends inside Lomsdal-Visten, five edges of 60,576,
the worst a 120.9 m UT.no edge with ten repeated vertices coming out 40 m short.
Every other area of the nineteen agrees to under a millimetre. The error only
goes one way, so an edge's figure is a lower bound; closing it costs forty times
the time.

**Every acceptance figure reproduced, in one run of one probe.** 198 markers,
**11,589** paths with exactly one non-interactive, 25 layers, the search 10 px
above the zoom at 60, the wheel taking zoom **9 → 11**, and the plan's own pane
**0 → 13 with five points → 0** once every point is taken back. The graph is
unchanged at 11,290 chains, 234,358 edges, 116,967 nodes, 948,465 vertices,
1,406,040 samples, 757/747 components, reach 50.8 km, 17 quays, Mosjøen 2.17 m.
The chain export still holds at **16,415 points**, 123 without an `<ele>`, its
ascent reading back to **0.00 m**. No page errors on any run.

**The rebuild asked the height service nothing.** `.cache/elevation/` is
byte-identical either side — 15,558,926 bytes, mtime untouched — which is what
20,183 requests would not have left. The point store is keyed on east and north
as integers in centimetres and nothing here moved a sample.

**What the phase cost the payload and the page.** The `protected` section is
0.43 MB of 6.59 raw and the page stays at **4.93 MB** encoded; the header gained
0.105 MB, being 31 areas at 4,195 ring vertices; the page went from 37.5 MB to
**37.7**. 64,736 edge-area pairs over 234,358 edges.

**Three routes were driven, one per thing the phase claims.** A five-point route
over UT.no's 42 km Rundtur — three routed legs and one drawn straight — reports
*34.01 km in Lomsdal-Visten nasjonalpark* of 36.89 walked, and its file carries
two generated `<wpt>`. A 5.5 km route out of the park across the shared boundary
writes *Enters Sirijorda naturreservat* and *Leaves Lomsdal-Visten nasjonalpark*
and nothing else, because it began inside one and ends inside the other. And a
437 m route over the single edge that clips Olaåsen tallies **67.3 m** of it,
reports none, writes no `<wpt>`, no `<protected>` block and **no Naturbase
credit** — the register is named exactly where a file states one of its figures.
All three validate against the shipped GPX 1.1 schema, `<wpt>` before `<trk>`.

**Nothing new is drawn, and that was a decision.** Anything in the overlay pane
joins the 11,589 for ever and the plan pane's 13 is an acceptance figure of its
own, so the boundaries are data in the page and never rendered. A boundary on
the screen belongs to phase 8, which has a reading page to put it on.

**A `<wpt>` gained a `<type>`, and GPX fixes where that goes**: name, then desc,
then type, then extensions, last of the twenty-odd a waypoint allows. Nothing
before this phase wrote one, so nothing had exercised the order.

### What phase 6C's review found

Four, and three were taken.

**A build over ground nothing protects crashed, after loading every source.**
`derive` reprojected the areas only `if len(protected)`, so an *empty* frame
stayed in the register's degrees while the edges were in EPSG:25833 — and the
measurement refuses a CRS mismatch, correctly, because a mask in degrees is near
nothing and would answer *outside everywhere*. The one path `load_protected` is
written to support was the one path that failed. `to_crs` works on an empty
frame; the guard was the whole bug. Regression test added.

**The overlap check printed the opposite of what it measured.** *overlap it in
area: none ← so the figures above may be added up* — with the annotation on the
line rather than on the answer, so a register that ever did overlap would have
named the offending areas and then said the figures add up, which is the one
thing an overlap means they do not. It has always read *none* here, which is why
nothing noticed. **An annotation belongs on the branch that earns it.**

**The boundary walk was 45 ms of a 50 ms panel refresh, on every click, for a
button that may never be pressed.** Measured on the 37 km route: 14,681 dense
points against 31 areas, run on each of the two refreshes a click causes and
growing with the route. Moved behind
`window.trailsProfilePanel.crossings()`, cached against the selection — so the
file and any check still get one answer, and a refresh now costs **3 ms**. A
method rather than a field, because asking costs something and the shape of the
interface should say so.

**And the verneform table was seven entries written from memory.** Three were
wrong — `AnnetVern` is not a code the register uses — and fourteen were missing,
including `Dyrefredningsomrade` and two `Landskapsvernomraade…` compounds that
exist within a day's drive of this park. The service publishes its own
`Kode_Verneform` **coded-value domain** at `{layer}?f=json`, twenty-four codes
with the names it gives them; that is now the table, verbatim. **A code table is
something to read, not to remember** — and the one place this was checked, the
44 areas over the zone's box, uses only four of the twenty-four.

## What phase 6C's readiness check found

**The phase was right about all three mechanisms it said were missing**, which
is the first time a readiness check has confirmed rather than corrected that
part. `naturbase.Source` has `find(name, layer, exact)` and no geometry.
The edges carry `waymarked`, `no_path_recorded`, `elevations`, `ascent` and
`descent` and nothing about where they are. The named points have no table:
**1,411** `L.circleMarker` — the phase said 1,410 — and **865** `L.marker`, names
inside popup HTML. And 6B's field is real, `gpx.py` carrying
`WAYPOINT_GENERATED`.

**The spatial query is the smallest part, not the first hurdle.** Built while
checking: the same ArcGIS endpoint with `geometry`,
`geometryType=esriGeometryEnvelope` and `spatialRel=esriSpatialRelIntersects`
instead of a `where` clause. One request, ten lines, and it answered for the
whole box. **A phase calling something "the first work" is worth timing before
believing it.**

**What that request measured is now the phase's reference.** 43 protected areas
in the network's bounding box — 39 nature reserves, two national parks, one
landscape protection area and one marine — of which **nineteen are touched by
the walked network**, 741.2 km of 5,853.3. Lomsdal-Visten holds 647.8 of it,
Holmvassdalen 25.7, Strauman 24.9, Stavvassdalen 17.1, Sirijorda 11.9, and the
smallest is **10 m of Innervisten marine protected area**.

**The premise that fails is in the decisions document, not only in the phase.**
Both said a free leg *"gets it from the samples it fetches anyway"*. At build
time that works, because Python has the polygons. In the browser it does not:
the samples give a position and the page carries **one** protected area of the
nineteen. The height service answers `datakilde`, `terreng` and `z`, and
`terreng` is ground cover — *Havflate*, *Skog*, *InnsjøRegulert* — not a
protected area, which the module's own comment says. So the page has to carry
the boundaries, and measured that is cheap: 25,144 vertices, 1.03 MB of GeoJSON,
0.37 gzipped, and simplified to 10 m — inside the ±5 m the sampling already
accepts at each crossing — **0.08 MB raw, 0.03 gzipped** against a 37.5 MB page.
**This is the second phase running whose central mechanism was assumed by the
specification rather than checked**, after 6B's route geometry.

**And a claim in both documents is measurably false.** *"None of the reserves
touches the park"* — **Sirijorda does**, sharing a boundary at 0.0 m, and so does
Innervisten. What it was used for survives, since touching is not overlapping and
a route strictly inside the park is still outside Sirijorda. The premise was
simply never measured, and 11.9 km of network runs inside Sirijorda.

**Two things the phase has to decide rather than discover**, both found by
looking at the measurement rather than at the text:

- **Which `verneform` count.** `naturbase.Layer` already separates the five, and
  the answer set as it stands includes a *marine* protected area. A walker
  reading that learns something different from a nature reserve.
- **How little counts as touching.** Five of the nineteen are met over less than
  400 m and one over ten. With no threshold a route brushing a boundary reports
  an area it never entered and generates a pair of waypoints for it. **A rounded
  label is a threshold** — phase 4's lesson — and so is a reported one.

**A figure without its extent cannot be re-derived.** The 26 reserves came from
the drawn zone, 39 from the network's own box; neither is wrong and neither said
which. This document demands reproducible figures and had let one through that
was not.

**Two national parks lie in the box** — Børgefjell/Burkijen besides
Lomsdal-Visten. The network does not reach the second, so nothing is wrong today;
a query written for *the* park rather than for parks is wrong the day it does.

## What phase 6B found

**The phase's own premise held, and it was the rewritten one.** `composeRoute`
returned `height`, `distance`, `free` and the totals and **no coordinates at
all**, so the first work was a track composer — and it is not a second walk. The
profile wants heights against distance and the file wants vertices, and laying
those out separately would be two walks over one route that could disagree while
each still looked like a route. `composeRoute` now produces the shape a chain's
series has — `lon`, `lat`, `along`, `height`, `distance`, `stretches` — which
`runsOf` and `denseOf` read unchanged. **The rewrite of this phase was worth
what it cost**: written against the earlier draft it would have been built as
wiring and found the geometry missing halfway through.

**Every acceptance figure reproduces, in one run of one probe.** 198 markers,
**11,589** paths with exactly one non-interactive, 25 layers, the search 10 px
above the zoom at 60, the wheel taking zoom **9 → 11**, and the plan's own pane
**0 → 13 with five points → 0** once every point is taken back. The graph is
untouched at 11,290 chains, 234,358 edges, 116,967 nodes. No page errors on any
run. The chain export still holds at **16,415 points**, 123 of them without an
`<ele>`, and its ascent still reads back off its own values to **0.00 m**.

**Four routes, one per leg kind, all exported and validated against the shipped
schema.**

| route | legs | segments | trackpoints |
|---|---|---:|---:|
| a five-point traverse of UT.no's own ways | 4 × `routed` | 1 | 14,821 |
| across a chain the height model has holes in | `routed` | 1 | 348, **16 without `<ele>`** |
| from a quay only a ferry reaches | `routed 2,027 m · ferry 5,057 m · routed 1,737 m` | **2** | 1,496 |
| between two components the network cannot join | `land 301 m` | 1 | 121 |

**The two kinds of NaN come apart correctly, and that is the check worth
keeping.** The crossing route breaks its track **once, at the crossing, and
nowhere else** — one crossing against one break. The route over unread ground
breaks **not at all** and keeps all sixteen of its unread points, each without an
`<ele>` and with its position intact. Both are the same NaN in `height`; what
tells them apart is the stretch boundary the composer records where it happens,
never a distance that repeats.

**A fifth route turned up the shoreline split without being asked for it.** Two
clicks on open ground off the coast came back as `land 248 m · water 835 m` —
the samples classified themselves and the leg split at the water's edge, so the
walked stretch ends and the crossing carries no curve. All hundred points the
file would hold are the land part; the crossing contributes none.

**The three marking buckets read as the network says they should.** Over the
walked network without its inferred connectors — **5,853.3 km** — the graph gives
**63.4 %** unknown, marked **17.8 %**, unmarked **18.8 %**, and FKB the largest
single source at **33.8 %**. On a route the same rule reads per edge: the 37 km
traverse comes back *marked 0.00 km · unmarked 0.39 km · unknown 37.00 km ·
0.3 m on connectors nobody drew · 5.97 km where no source records a path*. A
connector is its own answer and not folded into unknown, which is what the
payload has said since 3B and what would otherwise have been a fourth silent
bucket.

**A figure under a kilometre is written in metres.** *0.00 km on connectors
nobody drew* was the first version of that line and it reads as a figure that is
not there; the number was 0.26 m.

**One bug, and only the browser could have shown it.** `routeGpxOf` was handed
the plan's own description where it wanted what the panel had been told, so the
file's `<desc>` silently dropped the route's crossings while the panel above the
button went on showing them — a file that is plausible and silent about the one
thing it breaks its track for. Two lines, and a test now pins the two sentences
together. Nothing in Python could have caught it: both sides render, both are
strings, and the missing clause is missing rather than wrong.

**And a probe that lied for three runs.** The wheel read **9 → 9** in the full
run while reading 9 → 11 in a probe of its own. The cause is not the map:
`layer.fire('click')` opens the chain's popup, a Leaflet popup calls
`disableScrollPropagation` on its own content so the content can scroll, and the
popup sat over the middle of the map where the probe wheeled. `map.closePopup()`
before the wheel, and it reads 9 → 11 in the same run as everything else. The
tell was `document.elementFromPoint` returning a `<b>` — which only exists in
this page inside a popup table.

**A route's stated ascent reads back to within 0.03 m rather than 0.00**, and
that is the figure's own decimal rather than a disagreement. A chain's ascent is
rounded to a decimetre in Python before it reaches the page, so the file states
exactly what it holds; a route's is computed in the page at full precision and
written to one place. Half a decimetre is the whole of the gap, by construction.

**Two things deliberately not built.** The named ways a route follows — *via
Tveråvegen, Gamle Stavassveg* — which a chain's file carries as its identity: for
a route that is naming ground rather than measuring it, and naming ground is 6C.
And any survey-quality figure beside the unrecorded length, for the reason the
decisions document gives: FKB discloses nothing, so it would read *30 km not
disclosed*.

### What phase 6B's review found

**Eight findings, seven worked in and one declined.** Three were worth the
review on their own:

- **The dash table still spelled `'ferry'`** while `routedParts` had moved to the
  name the header hands in. Renaming `FERRY` in `trails.routing.sources` would
  have left `DASH[part.kind]` undefined, and a fjord crossing would have been
  drawn as a **solid line indistinguishable from walked ground** — the one thing
  this page must never draw, and nothing about it would have looked wrong.
  Keyed off the name that arrives, and a browser now reads the crossing's
  `stroke-dasharray` back as `2,8`.
- **The check that refuses an incomplete `export` did not reach inside it.**
  `route` and `waypoint` are dicts of eleven and three names; only the two keys
  were tested, so a `route` short of `partLength` built without a word and the
  page wrote `<trails:part kind="routed" undefined="2027.0"/>`. Now checked as
  their own lists and reported as `route.partLength`, so a caller is told where
  to look.
- **The `<desc>` and the `<extensions>` had stopped saying the same thing.**
  `metres` went into `SOURCE_CREDIT_FIELDS`, so the Python writer wrote it as an
  attribute while `_credit_line` still ignored it — two recordings of one list
  that disagree, in a module whose docstring says they are the same list twice.
  The page had it right; Python now writes the length first as well, with a test.

**And one claim in this documentation was over-reaching**, which is the finding
worth keeping. *A route's track holds one segment more than it has crossings*
is false at the ends: a crossing only adds a segment where it lies **between**
two walked stretches. Driven in a browser, the straight leg that split at the
shoreline — `land 248 m · water 835 m` — is one crossing and **one** stretch,
because the crossing is last. A phase-8 reader implementing `segments =
crossings + 1` would mis-map every leg of a route starting from a quay, which is
this document's own worked example. What is true is the narrower statement: every
break is a crossing.

**Two smaller ones fixed**: an unreachable branch that would have filed an edge's
metres as *on a connector nobody drew* while also crediting a named dataset —
two contradictory claims about one edge — now throws instead; and `add_plan_mode`
now documents the two settings it will refuse a page for.

**One declined, with the reason recorded so it is not reopened.** The review
argued that a leg the reader drew belongs in `undrawn` rather than `unmarked`,
since `undrawn` means *never asked* and nobody asked about a line somebody drew.
The decisions document settles it the other way and says why — *nobody marks a
line you drew across open ground*, so it is unmarked by construction rather than
unknown — and the file states the same metres separately as
`<trails:straight>`, with the panel saying *0.30 km drawn straight, not a path*.
A reader can tell the two apart without inference. What the review is right about
is that `undrawn` and a free leg are neighbours; if phase 8 ever finds the
distinction thin in practice, this paragraph is where to come back.

**What the review confirmed rather than found**, having driven the page's own
JavaScript in a harness: no NaN leaks into a `<trkseg>`; the vertex and sample
series stay in one coordinate across a routed-to-land boundary; and the `joined`
rule drops exactly the shared node and nothing else.

**Everything was re-driven after the fixes** and nothing moved: 198 · 11,589 · 1
· 25 · 10/60 · 9 → 11, the plan's pane 0 → 13 → 0, the chain still at 16,415
points, and both routes still validating with their breaks only at crossings.

## What phase 6's review found

**Every figure the phase reported reproduces**, checked against the built graph
and a driven browser rather than against the report. The graph is untouched —
11,290 chains, 234,358 edges, 116,967 nodes — the page holds at 198 markers,
**11,589** paths with exactly one non-interactive, 25 layers and 10 px above 60,
and the planned route lives in a pane of its own: **0 paths before, 13 with a
five-point route, 0 again** once every point is taken back. No page errors.

**The crossing carries no curve, and that was measured rather than looked at.** A
route from a quay only a ferry reaches comes back as `ferry 7,386 m / 0 samples`
beside `routed 62,225 m / 12,486 samples`, the two reported apart. In the composed
series **nothing sits at height zero** and the minimum is 0.46 m, so the curve
breaks where the ground stops instead of flattening across the fjord. Same rule a
ferry gets in phase 4 — and the failure it guards against would have looked like
data.

**The router had the defect that killed the phase's first session, and it is
fixed in the shipped code rather than only in the probe.** The back-walk was
`while (walk !== from)`, unbounded and appending, with `viaEdge` starting at −1 —
where a typed array answers `undefined` rather than raising, so it would have
laid `undefined` into the geometry and carried on. It now has a bound of
`header.edges`, an explicit `used < 0 || before < 0` throw, and a bound on the
search itself. Direction is read off a separate `viaNode` predecessor rather than
off the edge's own ends, which is what makes the **14 self-loop edges** safe. The
heap's sift carries a note on why it terminates instead of a bound, because it
moves over the array and not over the graph — the right distinction to draw.

**Three review findings, all real, all fixed.** A multi-edge ferry was charged the
flat cost per *edge*: 15 of the 21 ferry chains are cut into pieces and the
longest into seven, so that one was priced at 35 km of walking instead of 5. Now
split in proportion, as `graph.py::_cost` splits it — verified in both files, not
taken on trust. A misclick could ask the height service for an unbounded number of
points; now refused at 20 km and **said**, rather than coarsened, because
coarsening would make the two halves of a profile disagree invisibly. And a failed
batch left the other workers running.

**And one the phase found itself, which is the instructive one.** The page's metre
was a sphere at 110,574 m per degree — the *equatorial* figure — and read **0.56 %
short** at 65.6°N. It cancelled for a chain, which is scaled onto its carried
length, so nothing had ever shown it; a planned route has nothing to scale onto,
and it came to 900 m of stated distance on the traverse. Replaced with the WGS84
meridian series. Measured against the Python writer, the Rundtur's export went
from **16,339 to 16,415 points against Python's 16,421** — the gap closed from 82
to 6. **A constant that cancels in every case you have looked at is not a constant
that is right.**

### And the finding that lands on phase 5

**The 123 trackpoints with no `<ele>` are not a phase 6 regression, and phase 5's
acceptance contradicts itself.** The graph holds 1,831 unread samples of 1,406,040
(0.130 %) on 637 edges across 250 chains; the Rundtur has 53, which the
vertex/sample merge spreads to 123 written points. Both writers produce the same
123 — Python at 16,421 points, the browser at 16,415 — and the lines that omit the
element, `gpx.py:209` and `maps.py:1816`, are identical in HEAD.

Phase 5's done-when item 3 said *every trackpoint carries an `<ele>`*, and item 5
says the ascent must read back to the stored figure. **They cannot both hold**:
read as if every point had a height, the Rundtur gives 1,718.96 against a stated
1,721.80. The shipped code resolved it the right way and `gpx.py` says why —
*"the point is written without an `<ele>` rather than with an invented one.
Nothing downstream can tell an invented height from a read one."* Item 3 is
struck.

**And this document carried the false half of it.** *"Every point heighted"* was
written here as a verified result of the phase 5 review, and it was never true.
What the check actually establishes is that a file agrees with the figure it
states — and reading an ascent back means **breaking the run at every point
carrying no height**, which is exactly what `ascentMethod` describes. Read that
way the Rundtur lands on 1,721.80 against 1,721.80; read the lazy way it is 2.84 m
out. I made that mistake myself while checking this phase and was corrected by the
file.

**Two figures I reported as discrepancies were my own errors.** 251 chains against
the phase's 250 — the extra "chain" is the group of **8,684 bridge edges**, which
is not a chain. And 59 unread samples on the Rundtur against 53 — the raw
per-edge sum counts a shared node twice, and this document already says to compose
a chain's series with the shared node counted once. **Check a measurement against
this document's own methods before reporting a phase's figure as wrong.**

**What was not re-run**, nothing having contradicted it: the 20 km refusal, the
workers stopping after a failed batch, the click timings, the leg through a sound,
and the metre's own before-and-after.

**Two things deliberately not built**, and both are right: the plan is not
exportable, which is 6B, and switching plan mode off keeps the route drawn rather
than discarding it, since undo is the only edit this phase owns.

## What phase 6's readiness check found

**Phase 6 was not a phase.** Seventeen requirements, three of which needed
mechanisms that do not exist, and an acceptance spanning everything from a first
click to protected-area reporting. For comparison, phase 4 was *draw a profile
panel* and phase 5 *export one chain*, and each took an agent a full session plus
a review. Split into **6** (plan mode, all four leg kinds, Dijkstra, undo, the
route's profile), **6B** (the export and everything it reports) and **6C**
(protected areas and naming waypoints). Nothing dropped.

**The first split had four parts and the seam was in the wrong place.** It put
the free legs in a phase of their own, which meant building a route model that
knows one leg kind plus a stub refusing every click the graph cannot reach, then
widening the one and deleting the other in the next phase. **Throwaway work at a
seam is the seam telling you it is wrong** — phases 2 and 4 both had to be
rewritten as one text after being corrected in pieces, and this was the same
shape, caught before it cost anything. The size argument that produced it was
also weak: phase 4 was 1,171 lines and phase 5 was **3,299 across 27 files**, and
5 went through fine, so the ceiling was set lower than the evidence supports.
The export and the protected areas stay separate because they *read* a finished
route rather than shape it, and each brings a mechanism of its own.

**The assumption that could have sunk it holds.** A free leg needs heights
fetched from the page, and the page is a `file://` document — so the first thing
measured was whether that is even allowed. It is: `ws.geonorge.no` answers
directly, `{"datakilde":"dtm1","terreng":"Skog","z":131.55}`, no CORS error and
no proxy. And `terreng` is exactly the field the water classification needs, so
that rule costs nothing extra. **Ten minutes, and three later phases rested on
it.**

**Two figures were wrong, and one of them was an argument.**

- The phase said **FKB is 90 % of the network** and used that to justify keeping
  *unknown* out of *unmarked*. FKB is **33.8 %** by walked length — the largest
  single source, but not 90. The 90 % is a different measurement entirely: the
  share of *UT.no's routes* that have an FKB line within 25 m. The conclusion
  survives and the reason had to be replaced by the measured one: **63.4 % of the
  walked network is `unknown`**, which is a stronger argument than the one it
  replaced. **A wrong number under a right conclusion is still a wrong number,
  and it is the one someone will quote.**
- The Rundtur reads **10.3** of its 42 km with no path recorded, not 11.

**Two mechanisms assumed and absent** — the third and fourth time this has
happened:

- **Nothing on any edge or chain says which protected area it lies in.** The
  phase said edges carry it "from build time"; measured, they carry `waymarked`,
  `no_path_recorded`, `elevations`, `ascent` and `descent` and nothing about
  where they are. It is a new build field and a `GRAPH_LAYOUT` bump.
- **The named points are not machine-readable.** Naming a waypoint after a hut
  needs name, type and position; they exist as 1,410 `L.circleMarker` and 865
  `L.marker` with the names inside popup HTML. After phase 4's GeoJSON
  properties and phase 5's licences, **assume nothing about what the page can
  read — grep the built file.**

Credit where it is due: the phase said itself that `naturbase.Source` searches by
name and needs a spatial query. That one was known.

## Where the 5 MB went

Asked plainly — *why only 5 MB?* — and it turned out **nobody had ever
justified it.** The number appears once in the decisions document, in a note
referring to it as already settled, and it is settled nowhere: nothing was
measured to arrive at it, nothing against it. I then carried it into these
notes as "about 5 MB", which reads like a hedge and was really an unchecked
figure being passed on.

Measured, on the built page:

| | |
|---|---:|
| HTML parsed, to `DOMContentLoaded` | 1,195 ms |
| to `load` | 1,581 ms |
| the graph inflating, off the load | 229 ms |
| reading it into arrays | 50 ms |
| decoding base64: 5 / 10 / 20 MB | 7 / 18 / 34 ms |

**Quadrupling the payload would cost about thirty milliseconds of a 1.6 second
load.** It guards nothing. And the payload was then 4.93 MB of a 37.4 MB page —
rest is popup HTML and the coordinate arrays Folium writes for the drawn lines,
where nothing counts anything and where the two coverage rows cost **1.57 MB
against 0.009 in the payload**.

**But it earned its keep, and that is the part worth carrying forward.** It is
why the edge table is encoded rather than serialised, worth 1.7 MB; why the
coordinate quantum was weighed in metres rather than taken as free; and three
times it turned an estimate into a measurement. **A ceiling nobody can justify
is still useful if it makes the right question unavoidable — and useless as a
fact.** Struck as a fact, kept as a habit:

- encode and quantise always, because JSON coordinates are 22.4 MB against 1.8
  whatever the ceiling;
- argue for anything added on its own, never against a remaining margin —
  *"it still fits"* is not a reason;
- **the load time is the acceptance**, 1.6 s, re-readable on every build;
- look at the drawn side first, because that is where a megabyte gets added by
  accident.

The generalisable bit: **an inherited number that nobody can source is worth
attacking on sight.** This one had survived eight phases, and I had quoted it
in three documents without once asking where it came from.

## What phase 5's review found

**Everything the phase claimed reproduces**, and one of its checks holds more
widely than it was claimed to. The composed track goes from 541,060 vertices to
2,391,046 points, the median chain from **19 to 76** and the 42 km Rundtur from
1,330 to **16,421** — all three exactly. The widest gap is 4.992 m. And the
ascent read back off the composed heights matches the stored figure to
**0.000000 m** over **all 11,267** chains, not only the 5,254 longer than 200 m.

The page carries what the file needs: eight sources with the licences of the
decisions table, **Turrutebasen as CC0**, and `name`, `source` and `noPath` in
the figures table. A chain downloads from `file://` in Firefox — the 42 km
Rundtur at **1.19 MB**, schema-valid, none timed, no `<copyright>`. It was
written here that every point is heighted; **that was never true** and phase 6's
review measured it — see *And the finding that lands on phase 5*. Nothing phase 4
was accepted against moved.

**The licence disagreement the phase flagged is not one.**
`geonorge.Metadata.license` is a generic default for every Geonorge dataset, not
a statement about Turrutebasen, and every source with a module of its own matches
the table. Checked before deciding.

**The one finding: the file a reader downloads did not reproduce its own
figure.** It stated 1,721.8 m of ascent and its own `<ele>` values read 1,732.1.
Not the writers disagreeing — the payload's height quantum:

| heights at | worst deviation | over 1 m | over 5 m |
|---|---|---|---|
| 0.1 m | 10.30 m | 53 | 22 |
| 0.05 m | 9.93 m | 22 | 7 |
| 0.01 m | **0.00 m** | 0 | 0 |

Relative, on chains climbing more than 50 m, the decimetre was out by up to
**9.19 %**. **A rounded label is a threshold** — that was phase 4's lesson — and
so is a rounded *input* to a thresholded sum: the ascent rule counts a climb once
it clears 5 m, and shifting samples by half a decimetre flips borderline runs
either way, thousands of times along a route.

**What settled it was asking what the data actually holds**, which nobody had:
99.87 % of the 1,352,455 readings in the store lie exactly on a centimetre and
none between two. **There is no "exact" beyond 0.01 m** — the service answers in
centimetres. So the decimetre was not a modest claim about an uncertain model, it
was throwing away a digit that had been measured. The payload now carries it:
4.12 → **4.93 MB**, and the downloaded file reads
**+0.00 m** against what it states.

The argument that nearly stopped this was mine, and it was a category error:
*a decimetre already asserts more than the model resolves*. True of the ground —
DTM1 is good to about half a metre under canopy — and irrelevant to whether a
file agrees with itself, which is a question about **stored** precision. Both
sentences are about "accuracy" and they are about different things.

Two smaller consequences, both now constants of their own:

- `EXTENSION_DECIMALS` and the `<ele>` precision had been one number. A figure
  shown as whole metres wants one decimal; a height is what the figure was
  *computed from* and wants what the service gave. `ELEVATION_DECIMALS = 2`.
- The payload margin is worth less than it looks. Phases 6, 7 and 8 route,
  edit and load — none of them puts data into it. It was finished at 3B.

## What the gradient bands cost, and the two bugs on the way

Added after phase 4 on request: the curve is coloured by how steep the ground is
— gentle under 15 %, steep, very steep, extreme over 40 % — read over a 25 m
window, with a key and a crosshair reading.

**Measured before building anything, and the measurement changed the design
twice.** The fear was that a gradient off a height model is noise; it is not. On
level ground the model reads a median of **1.0 %** and a worst case of **9.2 %**
over the window, so nothing flat can reach the lowest boundary. And smoothing
barely moves the signal — 6.8 % between neighbours, 6.0 % over 50 m — which is
what says it is terrain rather than jitter. **The real hazard was the sampling,
not the model**: samples are laid per edge and a short edge still gets two, so
2 % of steps are under a metre apart and read up to **2,754 %**. That is why the
gradient is read over a window and refused below a 10 m run.

Verified against Python over six chains, band share by band share: a level N50
road comes back **100 % gentle in a single stroke**, a 540 m path climbing 183 m
comes back 11 / 21 / 32 / 37, and the 42 km Rundtur lands within a point of the
network average. Worst case 8,191 samples: compose and draw **134 ms**, against
127 before the colours.

**Two bugs, both mine, and neither visible to a single Python check.**
`make hooks-run` was green and the map built cleanly with both in place.

- **`CURVE is not defined`.** Removing the constant left one reference behind, in
  the arrow. The whole panel threw at load, so nothing worked at all.
- **`scale is not a function`.** The legend was built into a `var scale`, which
  shadowed the `scale()` the panel already used to fit a series to its box.

**And the thing that hid the second one for three builds**: the selection handler
ended in `.then(draw).catch(say('the routing graph did not arrive'))`, so an
error thrown *while drawing* was reported as a graph that never arrived. It sent
me to look at the payload, which was fine. Split into `then(draw, onReject)` the
bug named itself on the next run. **A catch that spans the work as well as the
wait will blame the wait.**

**One probe changed meaning and the notes have to say so.** `d.match(/M/g).length`
was the check that a gapless chain is drawn in one stroke. With the bands, every
change of colour legitimately starts a new stroke — the 42 km chain is 572 of
them. The check is now: **a chain with no gaps and one band** is one stroke, and
the level road is the case to use for it.

## What phase 5 found

**The two figures the phase gave for the filled file were measured under the
wrong rule** — the seventh finding of that kind, after the six the readiness
check turned up. *37 points* for the median chain and *8,490* for the 42 km
Rundtur are `length / 5`: a plain resample, which the same paragraph forbids in
the sentence above them. Under the rule as written they are 48 and 9,234. **Add
a figure's own decomposition up before quoting it**, and check that a predicted
figure was measured under the rule it is predicting.

**Keeping the vertices and interpolating the heights between them is not
enough**, and only a read-back showed it. A track built that way carries an
`<ele>` on every point and looks right on a chart, but the ascent read back off
those values comes out **47 m under** the figure the same file states for the
Rundtur, and 2,637 of 5,254 chains disagree with their own extensions. The fix
is to lay every sample into the track as the reading it is and space out only
what is still wider than 5 m; all 5,254 then reproduce their stored ascent
exactly. **Read a file's own numbers back out of the file.**

**"Sampled every 5 m" is 5 to 10 m.** `sample_count` gives `floor(length / 5) +
1` points spread evenly over the edge, so the step is `length / floor(length /
5)` — a 12 m edge gets three samples 6 m apart. Anything reasoning from a 5 m
step, including a gap rule written against it, has to know that.

**The two writers do not agree to the last point, and both reasons are the
page's payload rather than either writer.** On a 3.78 km chain, 1,373 points in
Python against 1,365 in the browser: nine pairs of vertices lie closer together
than the millionth of a degree the payload quantises to, and one sample gap
reads 9.98 m in one and 10.01 in the other, which `ceil(gap / 5)` turns into one
point or two. That second one matters beyond itself: **the page's flat-degree
metre and a projected metre differ by 1.28 m over 3.8 km after the scaling** —
three parts in ten thousand, not the parts per million a scaling argument
suggests, because scaling fixes the total and not the distribution. Compare the
two as curves, not by index, and account for the count difference rather than
tolerating it.

**The two writers cannot be compared by the test suite, and saying they are
compared is not the same as comparing them.** The suite runs no JavaScript and
should not start — so the claim belongs where it is true: the two are exported
on a real chain and compared **in a browser**, at acceptance, to a tolerance the
payload sets. Measured: the same extension fields exactly, every point of each
file within 5.6 cm of the other's line, and **no height apart at all** over the
points both put in one place — the payload carries the same centimetres the
height service answered with, so the page loses nothing on the way.

**Two different rounding rules agree only because of something invisible.**
``_figure`` rounds a half to even, the page's ``toFixed`` rounds one up, and
given ``17.25`` they would write ``17.2`` and ``17.3``. They never are given it:
``_figure_values`` has already rounded every figure before it leaves Python, so
what ``toFixed`` sees is on the grid and no longer a half. That coupling is now
written down in both places and held by a test over exact halves. **Where two
implementations agree, check *why* they agree.**

**A licence disagreed with itself in three places.** The decisions document's
table and this script's console line both say Turrutebasen is **CC0**;
`geonorge.Metadata.license` carries the class default of CC BY 4.0 and says
otherwise. The export takes the table's answer and says so where it does it, but
the disagreement is still there and belongs at the source.

**The height model publishes no version and is not ordered.** Every other source
answers with one or with the date its answer was read; DTM1 is asked point by
point and reaches a file through the graph. Its entry carries no version rather
than a date describing something else, and what a reader actually needs — the
rule the ascent was read under — is on every track as `ascentMethod`.

## What 3B found

**4.11 MB against an estimate of 3.6, and the estimate was mine.** The three
lines this document had budgeted all reproduce — the node columns at 0.26
against 0.27, the heights at 1.02 against 0.98, the sources at nothing. What was
missing had never been listed: the chain ids at 0.13, and `sampleCounts` at 0.12
and `vertexCounts` at 0.10, without which a concatenated stream cannot be cut
back into edges at all. The geometry came in at 2.46 against 2.35.

**That is the third time this payload was under-budgeted, and all three were the
same mistake.** The edge table was forgotten, then the elevations were scaled
instead of measured, and now the stream's own structure was left out. Not one of
them was a figure sized wrongly; every one was a section that was never on the
list. **Ask what else has to be in the file for the thing you budgeted to be
readable** — a length, a count, an id — because that is what does not occur to
anybody, and here it came to half a megabyte.

**Chain order beat `from_node` order, measured both ways.** Sorted by
`from_node` the node columns are 0.232 MB and this document's 0.27 reproduces —
but the edges of one chain are then scattered, so the link from a chain to its
edges costs an index and a sequence per edge, 0.453 MB. Laid out in chain order
each chain is one contiguous run: the link is one count per chain, 0.009 MB, and
the node columns cost 0.263 rather than 0.232 because consecutive edges still
share a node. 0.272 against 0.685. **The cheapest arrangement of a column is not
the cheapest arrangement of the file.**

**The ordering, measured rather than argued.** Every one of the 11,290 chains
comes back as a single run — 11,200 walk straight through, 41 are rings and 49
touch a node twice, and the walk gets through all of them in one pass. 9 edges
run against their chain. Composed from the payload, all **214,384** joins close
to **0.0000 m**, in Python and again in the page. So the run-break flag, which
exists so that two stretches are never laid end to end across a gap, is never
set here except at a chain's own beginning. It is tested against fixtures, not
against this map, and a reviewer who goes looking for it will find it dormant.

**Two findings in review, both about a figure or a name being read twice.**

- `order.py` said **91 edges run against their chain**; it is **9**, which
  `encoding.py` said correctly two files away. The 91 was a different quantity
  that had drifted onto the wrong sentence — 90 chains reach a node twice. And
  the walk's own docstring, inherited from phase 2, counted the 41 rings inside
  its "straight through" total and then added them again, which left 8 chains
  where there are 49. **Two files disagreeing about one measured number is the
  cheapest possible signal that neither was re-run.**
- `_source_table` keyed the byte code by source **name** while the table row is
  keyed by name *and* kind. Every source here carries exactly one kind, which is
  measured, so nothing was wrong — but a source that ever carried two would send
  every one of its edges to whichever row came last, and a path read as a
  crossing costs a route 5 km. `edge_costs` prices by name alone and assumes the
  same thing. It now raises, which is what the module does at every other such
  ambiguity.

**What the payload did not carry — added straight after, in three commits.**
`waymarked` and `no_path_recorded` are what a route sums to say how much of
itself is marked and how much runs where nothing is recorded. The phase named
five edge fields and these were not among them, so 3B correctly reported them
rather than adding them.

Adding them cost **no recomputation at all**, which is worth knowing before the
next one of these: both columns were already on the edges in the cached graph,
and the fingerprint covers what goes *into* a build, while the encoding happens
after it. What did need a `GRAPH_LAYOUT` bump was the popup, because that needs
the figures summed **per chain** and the chains carried nothing. Two minutes
offline, no request to any endpoint — the height store is separate and even a
`--rebuild` reads it.

Measured after: payload **4.11 → 4.12 MB**, the byte costing 0.234 raw and
0.009 gzipped. Every graph figure unchanged, every browser figure unchanged,
both checksums still matching, no page errors.

**And the part worth remembering.** The same two fields cost **1.57 MB in the
popups** — 29.6 to 31.1 MB — against 0.009 in the payload. **Popup text is
written out per feature and compresses against nothing, so showing a figure can
cost 175 times what carrying it does.** Neither budget is threatened; the ratio
is the surprise, and it is the right way round only because the payload is
encoded and the popup is not.

Three things decided while doing it, each of which could have gone the lazy way:

- **Marking is three-valued, so the popup gives kilometres per class** rather
  than a verdict. 467 chains are marked along part of their run and not the
  rest, and 3,711 km of 5,853 are honestly *not stated* — FKB says nothing about
  marking and is 90 % of the path evidence. A line labelled "marked" that is
  marked for a third of its length is worse than no answer.
- **Never asked is not nothing stated.** A crossing was never asked; an edge
  that came back `unknown` was asked and no source answered. The payload's first
  code is `null`, not `unknown`, and an unrecognised state raises rather than
  falling into code 0. That is the *fourth* appearance of this shape.
- **The label had to be new.** N50's `rutemerking` and Turrutebasen's `marking`
  already sit in those popups and are what one register says about its own
  lines. This is what any source says about the ground, so it reads *Marking,
  all sources*.

## What 1C found

The upgrade moved 102 packages and crossed three major versions — **pandas 2.3.2
→ 3.0.5**, mypy 1 → 2, pytest 8 → 9 — alongside numpy 2.3.3 → 2.5.2, shapely
2.1.1 → 2.1.2, geopandas 1.1.1 → 1.1.4 and pyarrow 21 → 25.

**Not one figure moved.** Chains, edges, nodes, vertices, components, reach,
quays, Mosjøen, and both phase 1B coverage figures came out identical, and so did
the graph underneath them: same geometry hash over all 234,358 edges, same
`chain_id` hash, same total length to six decimals (6,048,994.047071 m) and same
total cost (6,820,867.05014). Checked by rebuilding, not by re-reading a cache —
see the trap below.

**folium did not move at all**, 0.20.0 either side, so no trap in the list above
needed revisiting. The generated map is byte-identical once folium's per-build
random element ids are normalised away, and all five browser checks came out the
same: the boundary is still the one non-interactive path of 12,357 and a click
inside the park still reaches a line and opens its popup; the wheel over the
search box still zooms while `+` still types; the box still sits above the zoom
buttons; 198 markers in `.leaflet-marker-pane` and, as ever, zero under
`.leaflet-marker-icon`; and typing still applies differences rather than
rebuilding — `map.addLayer` stays flat across every keystroke and moves once,
after the debounce.

Three things did change, all of them the upgrade's doing and all confirmed
against a pre-upgrade `hooks-run` that was green:

- **The cache fingerprint changed without the graph changing.** pandas 3 stopped
  stringifying missing values in `Series.astype(str)`, which is how
  `_values_digest` builds its digest, so the key moved from `0013142f7bc05b97`
  to `82f3dc694c9a3831` and every cached graph rebuilds once. Content unchanged.
  Proven rather than inferred: restoring pandas 2's handling in that one function
  and nothing else re-derives the old key exactly. Five of the seven sources
  differ — the two that do not, UT.no and Ferries, are the two carrying no
  missing value in an identity or attribute column. The stored pickle also grew
  from 48.6 MB to 59.4 MB for the same 234,358 edges.

  **That diagnosis stopped one step short, and the step matters.** `str.cat`
  drops a missing value rather than writing a placeholder for it, so the digest
  had become blind to *whether a value is there at all*: three different frames
  of the same row count hashed identically. That is a false cache *hit*, not the
  harmless miss it looked like — and it half-defeats the reason the digest was
  added, which is that a name arriving from SSR changes neither the row count
  nor the length of the source it lands in. Fixed with `na_rep` on the same
  call; the graph rebuilds identical. Severity was low because the row count and
  the total length are in the key too, which narrows any collision.

  Worth generalising: a library that stops writing a placeholder for nothing is
  a *silent* change to anything that hashes or concatenates. It does not raise
  and it does not usually alter a figure — it alters what two different inputs
  look like to each other.

  **This left a real defect behind, found by the review and deliberately not
  fixed here.** `_values_digest` is now weaker than it was: dropping the missing
  values loses their positions, so `['A', NA]` and `[NA, 'A']` digest alike.
  Move an identity value between two rows of a source — row count, total length
  and geometry all unchanged — and the fingerprint does not notice, so `make
  graph` replays a cached graph built from different identities, which is
  precisely what `_values_digest` was added in the phase 1 review to prevent.
  The fix is a `na_rep` on the `.str.cat()` at `route_graph.py:415`, or hashing
  the raw values instead of a concatenation. It is left undone because it moves
  the cache key a third time in a phase whose whole value is that a moved figure
  has one cause; it should go in before anything else relies on that guard.
- **Four tests pinned pandas' defaults rather than this project's behaviour** —
  `[object]` for a text column and `datetime64[ns]` — both of which pandas 3
  changed, to `str` and `datetime64[us]`. They now read the dtype off the series
  they built, so they hold either side of the change. A fifth assertion in the
  same file had gone *vacuous* rather than red: `"b [object]:" not in result`
  passes for a reason that no longer has anything to do with what it was testing.
- **mypy could no longer target 3.11.** numpy 2.5 dropped 3.11 and writes its
  stubs with PEP 695 `type` statements, which mypy refuses to parse when told to
  target 3.11 — fatally, before any per-module override can apply. The setting is
  now 3.12, the lowest that parses. Two further errors surfaced from the new
  pandas and numpy stubs and are silenced at the two call sites with the reason
  named; neither is a runtime change, and `warn_unused_ignores` will flag them
  when the stubs catch up.

**The trap this phase nearly fell into**, worth keeping: `make graph` reads the
cached graph back, and the fingerprint covers the sources and the parameters but
not the library versions. Had the fingerprint *not* moved, a plain run after the
upgrade would have replayed the cache and reported every number unchanged without
executing a line of shapely. Rebuild with `--rebuild` and check that the run says
"Building chains per source", or the comparison proves nothing.

## After 1C and 1D — done, and what it turned up

All of what stood here has happened. Kept, because two of the findings were not
what they first looked like.

**`uv.lock` is tracked**, and `.gitignore` no longer hides it. It had been
ignored since the first commit under a `# uv` heading beside `.venv/`, which
reads as a template default rather than a decision. The version committed is the
one 1C verified, so the first tracked state is a checked one.

**shapely and branca were imported but never declared.** shapely appears in
thirteen modules — the whole of `routing/`, the exports, the geometry helpers and
the pipeline's transform step — and worked only because geopandas pulls it in;
branca carries the two `MacroElement`s the click-highlight and the search are
built on. Neither was found by looking for missing dependencies. Both turned up
while listing what the bounds ought to say. **A dependency that arrives
transitively looks exactly like a declared one, right up to the day it stops
arriving.**

**Raising the bounds forced the Python floor**, which is how 1D stopped being a
tidiness exercise and became unavoidable: `uv lock` refuses `numpy>=2.5.2`
against `requires-python = ">=3.11"`, because numpy 2.5 does not support it. The
floor is now 3.14 and all four version statements agree. The phase records what
that cost.

**And the `>=3.11` claim had been charging for itself invisibly.** The lockfile
carried two resolutions — numpy 2.4.6 below 3.12, 2.5.2 above — and only one was
ever run or tested. Moving to 3.14 collapsed them into one and removed a package
outright. A supported version nobody exercises is not free; it is a second build
that fails only for somebody else.

## Decisions taken not to do things

So they are not quietly reopened:

- No GraphHopper, and no server — the second asked separately from the first.
  Nothing measured requires one; the triggers that would are a second area, or
  turn restrictions and alternatives. Elevation used to be on that list and no
  longer is, since phase 2 provides it.
- No priority merge of the source geometries. Measured, it halves the reach.
- Elevation-aware routing is possible once phase 2 lands, but is a separate
  decision about the weights.
- No per-source switches on the build. `--no-osm`, `--no-n50`, `--no-fkb`,
  `--no-roads`, `--no-ut`, `--no-names` and `--fkb-km` are removed in phase 3.
  The layer control does the visual job better, and a graph missing a source is
  not smaller but wrong — quietly, and in a way that disagrees with every figure
  in the specification. A source that cannot load is an error.
- No `<copyright>` in the exported GPX, because a route mixing CC0, CC BY 4.0,
  ODbL and CC BY-NC has no single licence to name. The sources are listed
  instead.
- No timestamps on trackpoints, no speeds, no durations. A track carrying times
  reads as a recorded activity rather than a plan, and the rest would be guesses
  dressed as data.
- No reduced GPX variant: the target platforms cannot rebuild these paths from
  sparse points, and no point limit is known that would justify one.
- No offline elevation. The map's tiles are already online-only.
- **Not the strictest reading of the ascent threshold**, where any fall at all
  ends the climbing run. It is what produced the documented 996 m and it was
  recovered in review — 999.7 m on the same series the build uses — so the old
  figure was a defensible reading rather than a mistake. It is still the worse
  one: across three digitisations of the same slope it spreads 245 m, where the
  built rule holds them within 20. **The cross-source spread is the test of an
  ascent rule.** Invariance across sampling steps is necessary and not
  sufficient; the strict reading passes that and still measures the noise of a
  particular drawing rather than the hill.
- **`Ukjent` is no longer read as an identity**, and the reference moved with it:
  11,290 chains, FKB 6,201, Turrutebasen 244, 234,358 edges. Everything that
  matters held — 757 and 747 components, 79 % and 91 %, reach 50.8 km = 94 %,
  6 → 17 quays, Mosjøen 2.17 m, and both coverage figures to the decimal. The
  edge count fell by five through three fewer bridged loose ends, which is a
  knock-on of the split rather than a separate effect. This was the third time
  the same shape of bug appeared: a placeholder for *nothing* read as a value —
  `pd.NA` as the text `<NA>`, an empty string counted by `notna`, and now a
  register writing "unknown" into a name column. **Ask what a source writes when
  it has nothing to say, before trusting a column.**
- **No renaming of the `OSM` source to `OSM paths`.** It carries only paths, so
  the name is imprecise and the `N50 paths` / `N50 roads` split next to it makes
  that visible. But the source name is the **prefix of every chain id**, which
  keys the elevation cache, the highlight and the search — renaming moves all
  1,505 of them. The N50 split exists because N50 genuinely supplies both and
  both are loaded; within OSM there is nothing to disambiguate, and the layer is
  already labelled *Paths in park [OSM]*. The confusion this came from was a
  documentation one, in the cost table, and that is where it is fixed. If OSM
  roads are ever loaded, split then — that is the moment, exactly as it was for
  N50. Note the window: today a rename is free because nothing persists a chain
  id; from phase 2 it keys a cache and from phase 5 it is written into exported
  files.
- **No licence notice in the interface.** An earlier draft of the decisions
  document asked for one. Nothing here is published, and the obligations attach
  to distribution rather than use — and the mitigation is already in the right
  place, since the exported GPX is the only thing that leaves the machine and it
  carries its sources and their licences. Revisit only if the map is hosted or
  routes from it are published; ODbL's share-alike is the one with teeth.
- **No positive `on_path`.** Asked directly, measured, and refused: the sources
  over-record. FKB knows only `sti` and `traktorveg`, both asserting a physical
  feature, and calls 90 % of UT.no a path — while disclosing nothing about how
  any line was captured. N50, which does disclose, is 47 % digitised off older
  maps here, back to 1965, at accuracies to 50 m; and the two are not independent
  witnesses, both being Kartverket. Only the negative form survives, and only
  because a liberal recorder's silence means something. Two corrections to
  earlier reasoning are folded into the decisions document: FKB and N50 are not
  independent, and for paths it is **absence** that is evidence, not presence.
- **No survey-quality summary in the exported GPX.** Right in a popup, where the
  question is one line and the answer is concrete; useless in a file, where FKB's
  90 % would make it read *30 km not disclosed*.
- **No Geonorge file download for FKB.** It carries FKB's own `målemetode` and is
  the only thing that would settle the question above. It needs an account and a
  second loading path, which is exactly why the module uses the WFS. Open by
  decision, and nothing is blocked on it.
- **No park in the names of the Makefile targets.** `make map` and `make graph`
  exist, and both scripts hard-code `PARK_NAME`. Naming the targets for the park
  would be noise on every invocation while there is only one; the park is in
  `make help` instead, which is where someone looks. If a second is added, the
  scripts grow a `--park` option first and the targets follow it.
