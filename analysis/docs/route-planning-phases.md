# Route planning: the phases

Seven phases. Every decision they rest on is in `route-planning-decisions.md` —
read it first, and do not re-derive what it already settles by measurement.

## How to work through them

**One phase at a time, then stop.** For each:

1. Implement it.
2. Run a code review over the change.
3. Work the findings in — or, where a finding is wrong or not worth acting on,
   say so and why.
4. Stop. Report what was built, what the review found, and what is left.

Do not start the next phase. It begins when the maintainer says so, and not
before. If a phase turns out to be bigger than it reads here, say so and stop
rather than quietly carrying on.

**Every phase ends green**: `command make hooks-run` passes, new library code has
tests, and anything that touches the browser has been driven in a real browser
rather than reasoned about. That last one is not optional — see the list of bugs
in the decisions document that were only ever visible that way.

**Performance is not a phase.** It is a condition of phases 3, 4 and 7, which all
touch a map already carrying twelve thousand features. Two mistakes have already
been made and fixed there: rebuilding a layer per keystroke instead of applying
the difference, and writing a style that was already set. Both froze the map. The
same knife edge runs under every redraw below.

---

## Phase 1 — The network graph

Nothing visible changes. This is the foundation everything else stands on, and it
is verifiable on its own numbers.

**Build** a library module under `libs/src/trails/routing/`, free of Folium, of
the browser and of this one park, so the pipeline can consume it later. It takes
named GeoDataFrames and a clipping geometry; it returns chains and edges. The
extent, the source loading and everything Folium stay in the calling script.

- Chains per source: node each alone, `linemerge`, then chain through junctions
  by the rule in the decisions document — identity first, the 45° stroke rule
  where there is none. UT.no trips and Turrutebasen routes keep their published
  unit.
- Identity to feed that rule: route names from Turrutebasen onto FKB via
  `attach_nearest`, alongside the road names already joined from SSR.
- The routing graph: union of everything, noded, loose ends bridged at 25 m,
  each edge weighted `length × source factor` and carrying the chain it lies on.
- Ferry crossings belong in it — without them eleven of the seventeen quays, and
  with them the whole west side of the park, are unreachable. Flat cost, not
  length; marked as a different kind of edge from the start, because everything
  downstream has to keep them out of the walking figures.
- Cached under `.cache/`, like every other expensive step here.

An edge in this phase is `(from, to, cost, source, chain, geometry)`. Elevation
is phase 2's business and no field is reserved for it here.

Chain ids must be **stable across builds** — they key the elevation cache, the
highlight and the search. Derive them from the geometry, never from the order
chains come out in.

**Done when** a script prints the graph's statistics and they match the decisions
document: about 19,000 in-source chains falling under 10,000 with the stroke rule,
a routing graph near 130,000 edges, a largest component holding roughly 79 % and
spanning 94 % of the park north to south, and Mosjøen on it.

Those numbers are the test. If they come out far off, something is wrong in the
construction, not in the document.

---

## Phase 2 — Elevation

Still nothing visible. Every edge gains a real elevation series.

- A source module for `https://ws.geonorge.no/hoydedata/v1/punkt`: 50 points per
  request, retries, a real User-Agent, **six** requests in parallel. Twelve is
  faster but this is 22,000 requests against a public service; six puts the run
  at about seventeen minutes, once.
- A coordinate-keyed store under `.cache/`, consulted before anything is
  requested. This is the part that matters — without it the build hammers a
  public service on every run.
- Sampling every 5 m along each edge, and a per-edge ascent computed with the 5 m
  threshold. Skip ferry edges: there is no ground under them and the endpoint
  would answer with depths. The edge from phase 1 gains `elevations` and `ascent`; nothing else
  about it changes.
- Reject the readings that are not elevations. Over water the endpoint answers
  with a depth — `datakilde: "dybdekurver"`, a negative `z` — and outside its
  coverage with `null`. Check `datakilde` and carry a gap rather than a number.

**Done when** Sjøbergmarsjruta reads about 996 m of ascent, and still reads
within a few metres of that when the sampling step is changed to 10 or 15 m. That
invariance is the whole point of the threshold. A second build must not touch the
endpoint at all.

---

## Phase 3 — The map drawn from the graph

The riskiest change, and it adds no feature. Worth its own phase for exactly that
reason.

Replace the raw per-source layers with chains from the graph. What changes is
that a drawn line and a selectable track become the same object — a chain. The
merged routing graph is *not* what gets drawn; it stays underneath, with every
edge naming the chain it lies on.

- Each source keeps its own layer, colour and switch. Turning UT.no off still
  leaves the network beneath it.
- The "in park" and "approach" layers survive, but a chain is **never cut at the
  boundary**. Put it in the layer holding the greater part of its length.
- Where several sources describe the same valley, their lines still lie over one
  another as separate objects, and a click still takes the topmost. Two UT.no
  trips sharing a stretch remain two trips.
- A click selects one chain, never a branching network.
- Popups keep what they show today and gain the distinction between the stretch
  and the whole named way, so neither number lies.
- The search still matches by name across every chain carrying it.

**Done when** the map looks and behaves as it does today, the object count has
gone *down* — under 10,000 against today's 23,041 — and clicking a road that
branches selects only the arm under the cursor.

---

## Phase 4 — The profile panel

A panel at the foot of the map showing the selected chain's profile: distance
against elevation, total ascent and descent, high and low point. Foldable like
the legend, and it stays folded until wanted.

Draw it from the 5 m samples as **inline SVG, by hand** — no charting library.
A script from a CDN does not load on a `file://` page and fails silently, as the
OpenStreetMap tiles once did. Reduce the series to one point per pixel column,
keeping each column's minimum and maximum, so ten thousand samples cost nine
hundred points on screen and no spike is lost. Compute the ascent from the full
series.

The only smoothing is the threshold on the reported ascent, never on the curve.

Settle where it sits: the legend already occupies the bottom left. Give the panel
the width and leave the legend its corner above, or move the legend — but pick
one.

**Done when** clicking any chain draws its profile, and the map still zooms and
pans while it is on screen. Check a chain that runs along the shore: its profile
must not dive to −276 m where the sampling strayed over water.

---

## Phase 5 — GPX export of a selection

The selected chain, downloadable, with real elevation.

- One file, dense: every vertex, filled so no gap exceeds 5 m, an `<ele>` on
  each. A sparser variant would be unusable — the target platforms do not know
  these paths and cannot rebuild the line between distant points. Show the point
  count and total ascent next to the button.
- `libs/src/trails/io/export/gpx.py` learns `<ele>` at the same time — it has
  carried a comment marking the spot since it was written — so the build-time
  exports gain it too. The browser writes its own GPX; the two cannot share code
  across that boundary but must agree on structure.
- The licence note belongs at the download, not only in documentation.

**Done when** a downloaded file imports into Komoot and Outdooractive and shows
an elevation profile there.

---

## Phase 6 — Setting waypoints and routing between them

Plan mode proper: switch it on and click. Every click appends a waypoint and
routes from the one before, so a route grows as far as you care to take it.

Appending is barely more work than a single pair — a route is a sequence of legs
and a click adds one — while restricting the phase to two points would leave it
too thin to use. What is genuinely harder is *changing* an existing sequence, and
that is phase 7.

- Snap a click to the nearest node within about 150 m; beyond that keep the raw
  point.
- Dijkstra with a binary heap over the weighted graph, once per new leg.
- Take back the last point. Without it one misclick ruins a route, and popping
  the final leg is trivial — everything beyond that is phase 7.
- Draw the route, show its distance and ascent.
- Where no connection exists, a dashed straight leg, counted separately and
  labelled as not a path. Fetch its elevations on demand and cache them by the
  leg's endpoints.
- A free leg **over water** — a private boat transfer, of the kind UT.no's route
  descriptions rely on — is not walking. The elevation samples classify it:
  `terreng: "Havflate"` instead of ground. Its length goes to the crossings, not
  the walking total; it carries no profile; it ends a GPX segment. A leg that
  crosses a strait splits at the shoreline into walked and crossed parts.
- **Show the route's profile** in the panel from phase 4. It is the same panel,
  but the series is now composed rather than read off one chain: the edges the
  route uses, laid end to end, with the on-demand samples of any straight leg
  spliced in at the right place. Mark the straight stretches in the curve too, so
  the profile says the same thing the map does.
- **Export it**, through the writer from phase 5, with the clicked waypoints
  along as `<wpt>`. Little more than wiring — the composed geometry and its
  elevations already exist, because the profile needs them — and without it the
  phase stops one step short of the point of the whole feature.

Crossings — ferries and free legs over water alike — are reported apart from the
walking distance and break the GPX track into segments, so neither reads as
though it was swum.

**Done when** a north-south traverse of the park can be planned by clicking a
handful of points along it, on routed legs, with its distance, ascent and profile
shown, and the result imports into Komoot. Check an approach from the coast too —
Bønå or Visthus — since those only exist through a ferry. That case is known to be possible —
the main component spans 94 % of the park.

---

## Phase 7 — Editing the waypoints

Phase 6 can only append and undo. This is what makes a route something you can
work on rather than restart.

- Insert into the middle, which splits a leg; delete, which merges two; reorder,
  which changes which legs exist at all. The route, its numbers and its profile
  follow.
- Recompute only the legs a change actually touches — and only redraw the part of
  the profile that changed with them. The export follows whatever is currently
  drawn, without needing to know how it got there.

**Done when** reordering waypoints changes the route consistently, the distance
keeps up while dragging, and the exported GPX matches what is drawn.

---

## After the seven

Not planned, but worth knowing they are near, so nothing is built that would
block them:

- **Elevation-aware routing.** With a height on every edge it is a change to the
  weights and nothing else. Check that routes do not start taking absurd detours
  before turning it on.
- **The pipeline consuming the same graph.** `pipeline/TODO.md` and
  `pipeline/docs/trail-network-sources.md` both point at this. It is why phase 1
  is a library module and not script-local code.
