# Route planning: the phases

Eight phases, with 1B, 1C, 1D and 3B added after the first was already under way. Every
decision they rest on is in `route-planning-decisions.md` — read it first, and do
not re-derive what it already settles by measurement.

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

**No phase needs a new dependency.** What is already in `pyproject.toml` covers
all of them: shapely and geopandas build the graph, requests fetches the
elevations, pyarrow holds the point store, and everything from phase 3 onward is
JavaScript in the page. Do not reach for `networkx` for the graph or `scipy` for
the spatial queries — shapely's `STRtree` and a hand-written union-find are
enough, and phase 4 draws its chart by hand for reasons of its own. If a phase
genuinely does need something new, say so in its report and justify it; a
dependency should never arrive unremarked in the lockfile.

**Dependency upgrades never share a phase with a feature.** Refreshing `uv.lock`
alongside a change makes a failing review ambiguous — the change or the new
version? Phase 1C does nothing else, which is what makes it safe.

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
  where there is none. UT.no trips keep their published unit, one feature per
  trip; Turrutebasen goes through the rule, where identity reassembles each named
  route across the segments the register draws it as.
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

## Phase 1B — What the graph has to carry

Small. Phase 1 settled three of the four points this phase was written for and
the review settled a fourth, so what remains is two pieces of work, both
specified below with the figures they have to land on. Nothing here is an open
question. It does not block phase 2.

### Still to do

**Turrutebasen carries nothing but its name.** Built, its 244 chains hold
`chain_id`, `source`, `kind`, `identity` and `length_m` and no attribute at all,
because `route_graph.py` gives it `attributes=()`. It is the one source that
*describes* its routes rather than merely drawing them, so this is where phase
6's reporting has to come from. Measured over the zone, what is actually there:

| field | where | in the zone |
|---|---|---|
| `marking` | centreline | **770 of 770 "Marked"** |
| `signage` | centreline | 88 "Yes", the rest empty |
| `maintenance_responsible` | info table | 100 % — *Helgeland friluftsråd* and four local groups |
| `difficulty` | info table | 27 % — Easy · Medium · Strenuous · Expert |
| `trail_significance` | info table | 31 % — local, regional |
| `season`, `surface_type`, `trail_width`, `trail_type` | both | **empty here** |

So carry `marking` and `signage` from the centreline, and join
`maintenance_responsible`, `difficulty` and `trail_significance` from the info
table the way `trail_name` already is. Leave the four empty ones alone: they are
in the schema and hold nothing in this zone, and a column of nulls on every chain
is worse than no column.

**Derive `waymarked` onto every walking edge**, `marked` · `unmarked` ·
`unknown`, by the rule in the decisions document under *How much of a route is
waymarked*. Build it as **two masks out of the raw sources**, then test every
edge against both the same way:

| mask | from |
|---|---|
| marked | every Turrutebasen feature, plus every N50 path with `rutemerking = JA` |
| unmarked | every N50 path with `rutemerking = NEI` |

An edge is `marked` where at least **half its length lies within 10 m** of the
marked mask; failing that `unmarked` on the same test against the unmarked mask;
failing both, `unknown`. Marked wins where an edge meets both.

Do it with masks and not by reading the edge's own source, however natural that
looks. `rutemerking` lives on the **chain**, where `_combine` has already merged
a run that changes character into `JA / NEI` — 38 chains and 158 km of it — so an
edge reaching through `chain_id` gets an answer that is ambiguous exactly where
it matters. Masks avoid the problem instead of unpicking it, and they treat all
seven sources alike: a Turrutebasen edge lies on its own feature and comes out
marked without a special case.

**Ferries are excluded, not classified.** They are not walking, everything
downstream keeps them out of the walking figures, and a crossing is neither
marked nor unmarked nor unknown.

The half-length guard is not optional. Proximity alone once put 23 % of the road
names on the side road at a junction, and an edge that merely crosses a marked
route would otherwise count whole.

Measured under exactly this rule, so it is a real acceptance and not an estimate:

| | marked |
|---|---:|
| UT.no | **115.8 km of 376 = 31 %** |
| FKB | **246.3 km of 1,979 = 12 %** |

An earlier draft of this phase predicted 34 % and 173 km. Both were wrong,
because both came from a different measurement — the 34 % from a plain length
overlap rather than the half-length test, and the 173 km from the
`attach_nearest` name join at 25 m, which never saw N50's own marked paths at
all. A correct implementation would have been told it had failed. The
`unmarked`/`unknown` split is **not** predicted here; report it and it becomes
the reference, as phase 1's numbers did.

**Derive `no_path_recorded` onto every edge**, and derive nothing else about
paths. True where nothing from FKB, N50 paths, N50 roads or OSM lies within
**25 m** — a deliberately generous tolerance, because the more that counts as
recorded, the more it means when nothing is.

Built, "nothing within 25 m" turned out to mean *less than half the edge*, by
the same guard as above and for the same reason. Read as all-or-nothing it hands
an edge's whole length to whatever it touches once, reports 12.7 km rather than
19.9, and reports *Dagstur i Godvassdalen* as having none at all. The decisions
document carries the measurement; the figure it lands on is **20.2 km**.

Its absence asserts **nothing whatever**: the sources over-record, so a line's
presence is no evidence of a path. That one-directionality has to survive into
the name, the docstring and any text that ever shows it. The reasoning, and why
a positive `on_path` cannot be built, is in the decisions document under *Whether
there is a path at all*.

The question is only meaningful for edges from a route register — UT.no,
Turrutebasen, and later a free leg. An FKB edge *is* the record, so for it the
question is empty and the test answers itself.

**Ferries are excluded here too, and this one would go wrong silently.** A
crossing has nothing from the path mask within 25 m of it, so the rule as written
would flag all 149 km of ferry as having no path recorded — true, meaningless,
and it would land in the route's figure beside the walking. Bridged connectors
are in the same position: nobody drew them, which is what a bridge *is*.

Expect **19.9 km of UT.no's 376**, concentrated in three trips: *Alternative
Midtre – Nedre Breivatn* entirely, *Dagstur i Godvassdalen* about half, and
11.2 km of the 42.4 km *Rundtur i Lomsdal-Visten*. Spread thin across many trips
instead means the 25 m tolerance was not applied. It came out at 20.2 km, in
those three trips: 4.7 of 4.7, 3.6 of 7.2, and 10.3 of 42.4.

**Carry N50's `malemetode` onto the chain** while you are in there — not as an
input to anything derived, but for the popup. Across the zone 47 % of N50's paths
are `dig`, digitised from a map rather than seen, with capture dates back to 1965
and accuracies as coarse as 50 m. "Digitised from a map" beside a path is worth
more to a planner than any category computed from it.

### Two things not to be surprised by

- **The cache key changes, so the first run rebuilds.** Attributes are part of
  the build's fingerprint, which is what stops a graph answering for a source set
  it was not built from. Two minutes. Not a fault.
- **No figure from phase 1 may move.** Attributes ride along the chains, they do
  not decide them; only `identity_field` does that. So 11,290 chains, 234,358
  edges, 757 and 747 components, 50.8 km = 94 % reach, 17 quays and Mosjøen at
  2.17 m all have to come out exactly as before. If any of them shifts, something
  touched the geometry, and that is the finding — not the new column.

**Done when** the chains carry Turrutebasen's five fields and N50's `malemetode`,
every walking edge carries `waymarked` and `no_path_recorded`, ferries carry
neither, the three measured figures land — **31 % of UT.no marked, 246 km of FKB
marked, 19.9 km with no path recorded** — and phase 1's statistics are unchanged
to the last digit.

Done: 115.8 km of UT.no marked = 31 %, 246.3 km of FKB marked, 20.2 km with no
path recorded, and every phase 1 figure identical — checked against the cached
phase 1 graph rather than the printed report, down to the chain ids, the
geometry and the total cost. The `unmarked`/`unknown` split it was to report is
in the decisions document, where it is now the reference. **Unknown is the
largest bucket in the network**, 3,700 km of the 5,850 walked, which is what
makes it its own answer rather than a rounding of unmarked.

**Not to be built here**, decided and reasoned in the decisions document: no
positive `on_path`, no filtering of the graph by how well a path is evidenced,
and no Geonorge file download for FKB. The last is the only thing that would
change the picture — it carries FKB's own `målemetode` — and it needs an account
and a second loading path. It is recorded as open, not as work.

### Settled, recorded so it is not reopened

- ~~Carry the attributes onto chains **and edges**~~ — **chains only, with one
  exception.** An edge names its chain, so a route reads any attribute through
  `chain_id` in one lookup; copying five columns onto 234,358 edges buys nothing.
  Bridge edges name no chain and correctly carry no attribute — nobody drew them.
  The exceptions are `waymarked` and `no_path_recorded` above, both summed in
  kilometres and therefore needing the finer grain.
- ~~The cache key covers the extent and the source set~~ — **it does:** the
  approach distance, every parameter that shapes the graph, and per source its
  name, row count, total length, cost factor and `keep_whole`. The review added
  the values the chains are built *from*, because the road names come from SSR
  and the route names from Turrutebasen, and neither shows up in the row count or
  length of the source it lands in.
- ~~Turrutebasen belongs in the graph~~ — **it is in**, at the specified 1.02,
  contributing 235 km as 244 chains and 25,965 edges. The edge count came out at
  234,358 against the documented 129,616, exactly as predicted, and the reach did
  not move: 50.8 km = 94 %. The decisions document now carries phase 1's output
  as its reference.
- ~~Refuse to build a partial graph~~ — **satisfied by construction.**
  `route_graph.py` has no per-source switches and no fallback: a source that
  fails to load raises. Retiring the switches the *map* still carries is phase
  3's work and is listed there.

---

## Phase 1C — Refresh the dependencies

Maintenance, not a feature, and here for two reasons.

**Everything from phase 3 onward is folium and Leaflet work.** That library has
changed behaviour under this project before — `class_name` handling, which
`Icon` colours are accepted, and the marker class it overwrites. Upgrading after
the browser phases would put that work at risk and need its own regression pass;
upgrading now means phase 3's acceptance — *the map behaves as it did* — covers
the upgrade too.

**And phase 1 has just produced verified numbers.** Edges, components, reach,
chain counts. If an upgrade to shapely or geopandas moves the graph, the same
statistics script says so at once, and there is nothing else it could have been.
Later, a difference could be the upgrade or the new work.

- `uv lock --upgrade`, then `command make hooks-run`.
- Rebuild the map and drive it in a browser. The things that have broken before
  are the things to check: clicks reaching lines, the wheel reaching the map,
  markers appearing at all.
- Re-run phase 1's statistics and compare. Any movement is the upgrade's doing.
- Record what changed in folium's behaviour: the trap list in the review notes
  was observed under 0.20.0, not the 0.17 that document used to name — that
  figure was the floor in `pyproject.toml`, never an installed version.

**Done when** the numbers are unchanged, the map behaves as before, and anything
that did change is written down rather than discovered later.

Done: 102 packages moved, across three major versions — pandas 2 → 3, mypy 1 → 2,
pytest 8 → 9 — and every figure came out identical, checked against the geometry
and the chain ids rather than the printed report. folium did not move at all, so
no trap needed revisiting, and the map is byte-identical but for the element ids
folium regenerates each build. What did change, and the trap of comparing a
cached graph against itself, is in the review notes under *What 1C found*.

---

## Phase 1D — Settle the Python version — **done**

The project stated its Python version in four places and no two agreed. They now
all read **3.14**: `requires-python = ">=3.14"`, ruff's `target-version = "py314"`,
mypy's `python_version = "3.14"`, and `.python-version`.

What decided it was not that 3.14 exists but that raising the dependency bounds
made the floor unavoidable: `uv lock` refuses `numpy>=2.5.2` against a floor of
3.11, because numpy 2.5 does not support it. Tested at each candidate, 3.12,
3.13 and 3.14 all resolve — and 3.14 resolves *better*, collapsing the split the
mypy workaround was written for:

    Updated numpy v2.4.6, v2.5.2 -> v2.5.2
    Removed overrides v7.7.0

So the lockfile now carries one resolution rather than two, one of which was
never run or tested, and the workaround is deleted rather than documented
further.

**What it cost**, all of it ruff-driven and mechanical:

- `Generic[T]` subclasses and functions become PEP 695 type parameters — UP046
  and UP047, four sites in `pipeline/base.py` and `geonorge_schema.py`. This
  arrives at any floor above 3.11, since PEP 695 is 3.12.
- One `except (A, B):` becomes `except A, B:` — PEP 758, and 3.14 only. The one
  change here that a reader may find worse rather than better; a floor of 3.13
  would have avoided it and nothing else.
- B027 surfaced once `PipelineStep` was rewritten: `cleanup` is an empty method
  on an ABC. It is an optional hook and making it abstract would force every
  subclass to write an empty override, so it carries a `noqa` with that reason.

**Verified**: `command make hooks-run` green, every graph figure identical on a
`--rebuild` — 11,290 chains, 234,358 edges, 757 and 747 components, 50.8 km =
94 %, 17 quays, Mosjøen 2.17 m, UT.no 31 % marked, FKB 246.3 km, 20.2 km with no
path recorded — and all five browser checks unchanged: 198 markers in
`.leaflet-marker-pane > *` and none under `.leaflet-marker-icon`, 12,357 paths of
which exactly one non-interactive, the search above the zoom buttons at 10 px
against 60, and the wheel taking the map from zoom 9 to 11.

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
  would answer with depths. **Bridged connectors are sampled** — nobody drew
  them, but there is ground under them. The edge from phase 1 gains `elevations`
  and `ascent`; nothing else about it changes.
- **A per-chain ascent as well, computed over the chain's full series** — not
  summed from its edges. The two are not the same figure and the difference is
  not small: 42 % of the edges are shorter than 5 m and the median is 6.9 m, so
  under a 5 m threshold most edges report zero climb and a chain of twenty of
  them climbing sixty metres would sum to nothing. The per-*edge* figure is for
  elevation-aware routing, where per-edge is exactly right. The per-*chain*
  figure is what a popup shows, and phase 4 draws its panel from the same call.
- **Sample at least both endpoints, whatever the edge's length.** 97,974 edges
  are under 5 m and 28,373 are under one metre; "every 5 m" has to mean a floor
  of two, not a floor of zero.

Measured before this phase was handed over, so the cost is not a guess:
**1,017,876 unique coordinates** after rounding to the centimetre — 28 % of the
1.41 million samples are duplicates, mostly edge ends meeting at a node, which
is what the store has to catch *within* one build and not only between builds.
At 50 points per request that is **20,358 requests**, and the endpoint answered
a probe in **0.29 s**, so six in parallel puts the run at **about sixteen
minutes**. `datakilde: "dtm1"`, `terreng: "Skog"` and `access-control-allow-origin: *`
are all as the decisions document describes them.
- Reject the readings that are not elevations. Over water the endpoint answers
  with a depth — `datakilde: "dybdekurver"`, a negative `z` — and outside its
  coverage with `null`. Check `datakilde` and carry a gap rather than a number.

**Done when** Sjøbergmarsjruta reads about 996 m of ascent, and still reads
within a few metres of that when the sampling step is changed to 10 or 15 m. That
invariance is the whole point of the threshold. A second build must not touch the
endpoint at all.

**Say which Sjøbergmarsjruta.** It is *three* chains, one each from UT.no,
Turrutebasen and FKB, all 20.48 km over the same ground and all starting at the
same rounded point — `ut-no-398130-7281098-20477`,
`turrutebasen-398130-7281098-20478`, `fkb-398130-7281098-20483`. Three
digitisations give three ascents, and UT.no's is a consumer GPS track whose noise
adds apparent climb that the threshold suppresses but does not remove. Report all
three and record which one the 996 m refers to; a single figure against a name
that resolves three ways is not an acceptance.

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

### What the chains do not carry yet — check this before starting

"Popups keep what they show today" is not achievable as things stand, and the
gap is the bulk of this phase's work. Measured against the built graph:

**Recoverable without adding anything.** `name` and `trail_name` are in
`identity`; `category_label` follows from `category`; `survey_method` follows
from `malemetode`; `road_category` follows from `vegkategori`. And
`road_length_km` simply *becomes* `length_m` — a chain is now the whole road arm,
which is the thing `describe_whole_roads` was written to fake. That function goes.

**Genuinely missing, and each has to be added as a chain attribute:**

| layer | missing |
|---|---|
| UT.no | `ut_summary`, and all four links — `ut_url`, `guide_url_no`, `guide_url_en`, `gpx_url` |
| OSM | `surface`, `sac_scale`, `trail_visibility`, `osm_id` |
| Turrutebasen | `trail_number`, `trail_follows`, `special_hiking_trail_type`, `origin`, `data_capture_date` |
| N50 paths | `vedlikeholdsansvarlig`, `medium`, `datafangstdato` |
| N50 roads · ferries | `datafangstdato` |

The UT.no popups are the richest on the map and the only ones carrying links.
Losing them would make this phase a regression dressed as a refactor.

**And one that is not a popup field at all: `is_dnt`.** It splits Turrutebasen
into *two* of the seven line layers — "Marked routes" and "DNT routes" — so
without it one layer cannot be built.

It is derivable: `maintenance_responsible` is on all 244 Turrutebasen chains,
100 % filled, and the test is the same `DNT|Turistforening` the script uses
today. But chaining creates a case that does not exist now. **113 of the 245
chains carry more than one maintainer**, because a chain runs across segments
different clubs look after, and on **three of them, 9.4 km, one is DNT and the
other is not**:

    DNT | Sør-Helgeland / UL Fremskritt
    DNT | Sør-Helgeland / Vevelstad Idrettslag
    DNT | Brurskanken Turlag / Vefsn kommune og Marsøras venner

Today each segment sits in exactly one of the two layers. A chain has to go
wholly into one — and that is a choice, not a derivation. The rule used at the
park boundary, *the layer holding the greater part of its length*, cannot be
applied here: by the time the question is asked, `_combine` has already merged
away which maintainer held which stretch.

**Decided: keep `.any()`, as today.** A chain touching DNT anywhere is DNT, so
those three go to the DNT layer. It is wrong in the direction that draws a red
DNT line over 9.4 km of 235 that DNT does not look after — acceptable because the
layer is called "DNT routes" rather than "maintained solely by DNT". The exact
alternative is to carry the flag on the *pieces*, before chaining, and weight it
by length per chain; that is more faithful and means the chain builder has to
carry something it otherwise would not. Not worth it for 4 % of one source.

### Three decisions this phase has to make

- **Where the map gets the graph.** Recommended: call the same cached `build()`
  that `route_graph.py` uses, so both scripts produce the identical graph and the
  second of them is instant. That means lifting `load_sources`, `masks_from` and
  `build` out of the script into the library — do that first, before adding
  attributes, or the attribute work has to be moved twice.
- **What `osm_id` means for a chain.** Measured: 64 % of the OSM chains span
  more than one way — median 2, worst 33 — so for most of them a single id is
  simply wrong. **Decided: keep it joined**, as `typeveg` and every other
  multi-valued field already are, and **rename the label to the plural**, so it
  does not read as one id when it is thirty-three. Dropping it would discard
  something the source has; a special case would be the only one on the map.
- **The whole-named-way figure.** The popup is to show the stretch *and* the
  named way's total — *3.2 km of Tveråvegen's 15.6*. That is now a sum over the
  chains sharing an identity, computed once at build time. Note that 132 of the
  2,326 road chains carry more than one `road_id`.

The six build-time GPX exports come from the chains from this phase on — that is
in the decisions document rather than above, and it is easy to miss.

**`--simplify-m` stays, and it is not in conflict with "do not simplify".** That
rule governs the geometry that is *exported and routed*, which keeps full source
precision; the *drawn* copy is a separate thing and always has been — the script
already says so, `GPX keeps full detail`. Folium writes drawn geometry as JSON
coordinate arrays, and the decisions document measured what that costs: 22.4 MB
for the network's vertices. Removing the simplification would not be a fidelity
fix, it would put twenty megabytes of coordinates into the page. Leave it.

**Retire the source flags while you are here.** `--no-osm`, `--no-n50`,
`--no-fkb`, `--no-roads`, `--no-ut` and `--no-names` predate the layer control,
which does the job better — per layer, instantly, without a rebuild. With a graph
they become actively harmful: a missing source does not make it smaller, it makes
it wrong. `--fkb-km` goes too, folded into `--approach-km`; the density it
guarded against is what chains solve. What remains is `--approach-km` as a graph
parameter, `--simplify-m` for the drawn copy, `--force-download` and
`--highlight`.

That means FKB is loaded over the full 15 km rather than 5 km — every other
source already was, and every figure in the decisions document assumes it.

**Done when** the map looks and behaves as it does today, clicking a road that
branches selects only the arm under the cursor, and the object count has roughly
halved: **11,290** chains against today's 23,876. Built per source: FKB 6,201 ·
N50 roads 2,326 · OSM 1,505 · N50 paths 958 · Turrutebasen 244 · UT.no 35 whole
trips · ferries 21.

"Behaves as it does today" is measured, not remembered. Phases 1C and 1D both
drove the map in Firefox and it read the same each time; that is the baseline,
and it is the sharpest it will ever be:

| | before this phase |
|---|---|
| markers in `.leaflet-marker-pane > *` | **198**, and 0 under `.leaflet-marker-icon` |
| paths in the overlay pane | **12,357**, of which exactly **1** non-interactive — the park boundary |
| search control | top **10 px**, above the zoom buttons at 60 |
| wheel over the search box | zoom **9 → 11** |

Every one of those except the path count must come out identical. The path count
is the one figure that *should* move, and roughly halve — it is what this phase
is for.

Popups are part of "behaves as it does today": check UT.no's four links and its
summary, Turrutebasen's marking and maintainer, and a road showing both its own
length and its named way's total. A popup that quietly lost a line is the most
likely way for this phase to look finished when it is not.

---

## Phase 3B — Get the graph into the page

Nothing visible again, and it exists because two later phases assume it. Phase 4
draws a profile from the 5 m samples and phase 6 runs a Dijkstra over the
weighted graph — and after phase 2 both of those live in Python and neither is
in the browser. The decisions document specifies the encoding in detail under
*Full source precision*; no phase had claimed it.

**Two representations, and they must not be unified.** Phase 3 draws chains as
folium GeoJSON, simplified for rendering. This phase adds a *second* payload:
the routing graph at full source precision, which is never drawn. Drawing and
routing are different units — that is the whole point of the chain/edge split —
and an attempt to serve both from one copy loses either the accuracy or the
render budget.

**Build:**

- A Python encoder: zigzag varints over the delta between consecutive points,
  one run per edge, quantised at 1e-6 — 0.11 m, an order of magnitude finer than
  the best source in the set — then gzip, then base64. It belongs to the map
  script, not the graph builder: the graph module returns plain geometry and
  attributes and stays architecture-neutral.
- The edge table beside it: `from_node`, `to_node`, `cost`, `source`, `kind`,
  `chain_id`, and the per-edge ascent from phase 2.
- **Node positions**, which phase 6 needs to snap a click to the nearest node
  within 150 m and which nothing above provides. Do not ship a node table:
  derive the positions from the edge endpoints while decoding, so they cannot
  disagree with the geometry and cost nothing in payload. A linear scan over
  116,970 points answers a click in a few milliseconds, so no spatial index is
  needed in the browser — say so, or someone will build one.
- The elevation series, delta-encoded at 0.1 m.
- A JavaScript decoder in the page, inflating with `DecompressionStream`. Hand
  written, like the legend, the search and the profile — a CDN script does not
  load from `file://` and fails silently.

**The test that matters is a round trip.** Encode, decode in the browser, and
compare against the source coordinates: nothing may move by more than the
quantisation. Do it over the whole graph, not a sample — a decoder that is
correct for 99.9 % of runs is a decoder with a bug in the long ones.

**Done when** the page opens and behaves exactly as phase 3 left it — 198
markers, one non-interactive path, search at 10 px, wheel 9 → 11 — and the
payload comes in under budget. These were encoded and measured rather than
scaled, because an earlier draft of this phase scaled them and got two things
wrong:

| | measured |
|---|---:|
| geometry, 948,465 vertices, varint + gzip + base64 | **2.35 MB** |
| edge table, sorted by `from_node`, both columns delta-encoded | **0.27 MB** |
| source per edge, one byte | under 0.01 MB |
| elevations, ~1.41 million samples at 0.1 m | ~2.2 MB, *estimated* — phase 2 has not run |
| **total** | **≈ 4.8 MB** against an allowance of 5 |

**The edge table has to be encoded, not serialised.** An earlier draft listed it
without budgeting it, and as JSON it is 1.98 MB, which puts the total at 6.5 MB
and over. Sorted by `from_node` with both columns delta-encoded it is 0.27 MB —
a seven-fold difference, and the single most consequential decision in this
phase. Sorting changes the edge order, so whatever ties an edge to its chain and
its geometry has to survive the reordering; get that wrong and the graph is
quietly scrambled rather than obviously broken.

**Do not ship `cost`.** It is `length × source factor`, the length is in the
geometry the browser already has, and the factors are six numbers. The exception
is the 58 ferry edges, whose cost is flat.

It fits, but not with room: 4.8 MB of 5, and the map itself is 24.2 MB, so this
is a fifth again on the page. **If it does not fit, report it rather than
quietly quantising coarser** — 1e-5 saves 0.7 MB and costs 1.11 m, which is
worse than the best source in the set and would undo what phase 1 was careful
about. And measure the decode: it is a number nobody has yet.

---

## Phase 4 — The profile panel

A panel at the foot of the map showing the selected chain's profile: distance
against elevation, total ascent and descent, high and low point. Foldable like
the legend, and it stays folded until wanted.

Draw it from the 5 m samples — which reach the browser through phase 3B, not
through this phase — as **inline SVG, by hand**, and no charting library.
A script from a CDN does not load on a `file://` page and fails silently, as the
OpenStreetMap tiles once did. Reduce the series to one point per pixel column,
keeping each column's minimum and maximum, so ten thousand samples cost nine
hundred points on screen and no spike is lost. Compute the ascent from the full
series.

The only smoothing is the threshold on the reported ascent, never on the curve.

**Put the ascent in every chain's popup too, not only in the panel.** The
decisions document calls this "the main thing the build-time sampling buys" and
no phase had claimed it: phase 2 puts `ascent` on the *edge* and does not touch
the map, phase 3 rebuilds the popups before any elevation exists, and this phase
is the first to have both. It belongs here.

**A chain's ascent is not the sum of its edges' ascents.** The reported figure
ignores gains under 5 m, and that threshold breaks at every edge boundary — with
234,358 edges averaging 26 m, summing per-edge figures would count a great deal
of noise that the threshold exists to discard. Compute it the way the panel
already has to: over the chain's full series, once. Two places asking the same
question must not get two answers, so derive the popup's figure and the panel's
from the same call.

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
  each.
- **Every file says what it is.** Build the `<extensions>` mechanism here, with
  the writer, rather than retrofitting it in phase 6 — and give it something to
  carry straight away: that this is a single chain, its name, its source and its
  chain id. A file that identifies itself can be recognised on load instead of
  matched, and an exported stretch becomes something you can bring back in as the
  start of a plan. Phase 6 then only adds fields to a mechanism that already
  exists. A sparser variant would be unusable — the target platforms do not know
  these paths and cannot rebuild the line between distant points. Show the point
  count and total ascent next to the button.
- `libs/src/trails/io/export/gpx.py` learns `<ele>` at the same time — it has
  carried a comment marking the spot since it was written — so the build-time
  exports gain it too. The browser writes its own GPX; the two cannot share code
  across that boundary but must agree on structure.
- **Name the sources in the file, and say which before it leaves.** Put the
  sources actually used, with their licences, into `<metadata>` — a chain export
  usually has one, plus Kartverket's height model. Do not fill in a single
  `<copyright>`: see the decisions document, a route mixing CC0, CC BY 4.0, ODbL
  and CC BY-NC has no one answer, and inventing one would be worse than listing
  what is there.
- Carry the rest of what the decisions document asks for: the source versions
  the file was built from, the ascent figure with the method that produced it,
  the named ways the track follows, and `<metadata><time>`. And **no timestamps
  on the trackpoints** — a track carrying them reads as a recorded activity
  rather than a plan.
- Replace the generic licence note at the download with what this file actually
  contains. A stretch of FKB is unproblematic; a stretch of OSM is share-alike.
  The reader should know which before pressing the button, not afterwards.

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
- **Export it**, through the writer from phase 5. Little more than wiring — the
  composed geometry and its elevations already exist, because the profile needs
  them — and without it the phase stops one step short of the point of the whole
  feature.
- The sources list now spans several: report the length contributed by each and
  the licence that comes with it, so *3.2 km OSM (ODbL) · 1.1 km UT.no (CC BY-NC)*
  is visible before the download rather than a blanket warning.
- **Say which protected areas the route touches and how far** — *38 km, of which
  22 in the national park and 3 in Strauman landskapsvernområde*. Not the park
  alone: the zone holds 26 nature reserves besides, none touching the park but
  every approach crossing the ground they sit on. `naturbase.Source` needs a
  spatial query for this; it searches by name today. The boundary has been drawn all along and the plan made no use of
  it, yet the rules inside differ from those outside. Decide it at the 5 m
  samples, as the decisions document sets out, so edges carry it from build time
  and free legs get it from the samples they fetch anyway.
- Put the figure in the exported description, and a **generated waypoint** at
  each crossing so a reader sees where the route enters and leaves.
- **Mark every `<wpt>` as set or generated.** A boundary marker is not a waypoint
  anyone chose, and phase 8 must not read it back as one — a loaded route would
  otherwise gain stations nobody placed and route through them. The rule covers
  any marker the map adds by itself, now or later.
- **Say how much of it is waymarked**, as length and in three buckets — marked,
  unmarked, unknown. FKB is the largest source and carries no marking data at
  all, so calling those stretches unmarked would assert what the data does not
  say. See the decisions document. The edges carry the field from phase 1B.
- **And how much of it runs where no source records a path** — *8 km with no
  path recorded*. Also from phase 1B, also summed off the edges, and for this
  park it says more about the day ahead than any other single figure: the
  three-day Rundtur reads 11 of its 42 km that way. State it as recorded, not as
  fact: the sources over-record, so their silence is evidence and their lines are
  not. Do **not** add a survey-quality breakdown beside it — FKB is 90 % of the
  network and discloses nothing, so it would read *30 km not disclosed*. That
  belongs in the popup, where the question is about one line, and it is there.
- **Name a waypoint after what is there.** When one lands within about 50 m of
  a named point the map already draws — a hut, a quay, a trailhead, a farm —
  take that point's name, type and position for the `<wpt>`, while the route
  itself stays on the network. It costs a nearest-lookup against layers already
  in the page, and it is the difference between a file that reads *Lavasshytta →
  Sæterskaret skogstue → Bønå ferjekai* and one that reads as three coordinates.
- **Extend what phase 5 started.** The `<extensions>` mechanism is already
  there; a plan adds the clicked waypoints as `<wpt>` and each leg's mode —
  routed, free over land, crossing. Do it here, not in phase 8: everything
  exported from now on should be loadable, and a file written before its
  description existed can never be restored exactly, only matched. Phase 8 adds
  the reading side and nothing else.

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

## Phase 8 — Loading a route and working on it

Read a GPX back in and carry on from it: one of our own exports, or a track from
Komoot, or one a friend sent.

It comes after phase 7 for a reason rather than by convenience — a loaded route
has to be immediately editable, and editing is what phase 7 builds. Before that
you could load a route and look at it, which is not the point.

**Ask on load what should happen to it.** Three answers, and they cost very
different amounts:

| mode | what it does | effort |
|---|---|---|
| take it as it is | the whole track becomes one fixed leg, untouched | trivial |
| align to the network | read the `<wpt>` list and route between them afresh | small |
| **match where a path exists** | follow the track, replace the stretches that run along network edges, leave the rest as drawn | **the real work** |

The middle one is not routing. Re-routing between waypoints throws the shape away
— fine for one of our own plans, which *is* a handful of waypoints, useless for a
foreign track that has thousands of points and no waypoints at all. What it needs
is map-matching: walk the track, find where it follows an edge within a
tolerance, swap that stretch for the edge, keep the remainder verbatim.

That is `attach_nearest` with `min_overlap` applied along a track instead of
between datasets, and it inherits the same trap: a track running beside a
parallel path will snap to the wrong one unless the overlap is checked, not just
the distance.

Build it as one phase even though the ends are cheap. Split, and the loading and
parsing gets written twice.

**Anything this map wrote restores exactly**, without matching: a chain export
names itself since phase 5, a plan carries its waypoints and leg modes since
phase 6. Only foreign tracks go through matching.

**Done when** a track exported from this map loads back identically, and a GPX
from Komoot loads, matches onto the network where one exists, and can then be
edited like any other plan.

---

## After the eight

Not planned, but worth knowing they are near, so nothing is built that would
block them:

- **Naming the huts a route passes**, not only those chosen as waypoints —
  *passes Lavasshytta at km 12*. A search along the finished route rather than a
  field that already exists, which is why it waits.
- **Splitting a route into days.** Purely additive on a finished route, and what
  the multi-day UT.no routes imply.
- **Moving a waypoint onto a hut or a quay**, rather than only naming it after
  one. Phase 6 takes the name and leaves the route on the network, which is the
  part that matters; making the route physically reach a building 30 m off the
  path is a separate question and probably not wanted.

- **Elevation-aware routing.** With a height on every edge it is a change to the
  weights and nothing else. Check that routes do not start taking absurd detours
  before turning it on.
- **The pipeline consuming the same graph.** `pipeline/TODO.md` and
  `pipeline/docs/trail-network-sources.md` both point at this. It is why phase 1
  is a library module and not script-local code.
- **A local height service.** The decisions document names the one place a server
  would earn its keep today: replacing repeated calls to a public endpoint with a
  local DTM extract — no routing server, just a small service, and
  `docs/trail_routing_architecture_guide.md` sketches the shape. Deliberately no
  phase: it is **not needed while phase 2's point store keeps a second build from
  asking again**, and that is the condition to watch. If builds start hammering
  `hoydedata` because the store is missing them, this is the answer, not a bigger
  cache.

Everything in this section is here because it was checked against the decisions
document and found to have no phase *on purpose*. That check is worth repeating
whenever the decisions document grows: **ask of every specification which phase
receives it.** It is what turned up the popup ascent, which had fallen between
phases 2, 3 and 4, and the page encoding, which is now phase 3B.
