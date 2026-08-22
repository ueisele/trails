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

Still nothing visible. Every walked edge gains a real elevation series, and every
chain the four figures that describe it.

**Fetching, and being a decent guest.** A source module for
`https://ws.geonorge.no/hoydedata/v1/punkt`: 50 points per request, retries, a
real User-Agent, and **six requests in parallel**. Twelve is faster and this is
somebody's public endpoint. Measured before hand-over, so the cost is not a
guess: 1.41 million samples reduce to **1,017,876 unique coordinates** once
rounded to the centimetre — 28 % are duplicates, mostly edge ends meeting at a
node — which is **20,358 requests**, and a probe answered in **0.29 s**. Six in
parallel is about sixteen minutes, once.

**The store is the part that matters.** Coordinate-keyed, under `.cache/`,
consulted before anything is requested — and it has to deduplicate *within* a
single run as well as between runs, because 28 % of the work is the same
coordinate twice. Without it every build asks again. `pyarrow` is already a
dependency and has had no user until now; this is what it was declared for.

**Sampling.** Every 5 m along each edge, with a floor of **both endpoints
whatever the length**: 97,974 edges are under 5 m and 28,373 under one metre, so
"every 5 m" has to mean a floor of two rather than of zero. Skip ferry edges —
there is no ground under a crossing and the endpoint would answer with depths.
**Sample bridged connectors**: nobody drew them, but there is ground under them.

**Reject the readings that are not elevations.** Over water the endpoint answers
with a depth — `datakilde: "dybdekurver"`, a negative `z` — and outside its
coverage with `null`. Check `datakilde` and carry a gap rather than a number.

### The figures, and why there are two sets

**Per edge: ascent and descent**, both with the 5 m threshold. This is the
granularity an elevation-aware weight needs, and it is the only thing it is good
for.

**Per chain: ascent, descent, high and low point**, computed over the chain's
**full series** — never summed from its edges. The difference is not a rounding:
42 % of the edges are shorter than 5 m and the median is 6.9 m, so under the
threshold most edges report no climb at all, and a chain of twenty of them rising
sixty metres would sum to zero. Summing does not approximate the figure, it
destroys it.

**Store descent wherever ascent is stored.** A chain is oriented so that its id
stays stable, not because a walker is obliged to take it that way, so an ascent
alone is true in one direction and silent about the other. Phase 4 shows both,
with the direction, and cannot invent the second number.

**High and low carry no threshold** and could not disagree with anything — but
the popup that shows them is rendered in Python at build time, so they have to
exist on the chain like the rest. Two numbers, and one rule instead of two.

**Done when** the four figures are on every chain and both are on every walked
edge, and:

- Sjøbergmarsjruta reads **1,176 m of ascent** on UT.no's digitisation, 1,196 on
  Turrutebasen's and 1,195 on FKB's, and each still reads within a few metres of
  its own figure at 10 and 15 m sampling. That invariance is the whole point of
  the threshold. **These replace the 996 m this phase asked for**, which was a
  defensible reading of the same rule but a worse one — see the decisions
  document: it makes three digitisations of one slope disagree by 245 m where the
  built rule holds them within 20.
- A second build touches the endpoint **not at all**.
- A coastal path's profile never dives to −276 m, which is what an unchecked
  `datakilde` looks like.
- **Not one figure of the graph moves.** 11,290 chains — FKB 6,201 · N50 roads
  2,326 · OSM 1,505 · N50 paths 958 · Turrutebasen 244 · UT.no 35 · ferries 21 —
  234,358 edges, 757 and 747 components, reach 50.8 km = 94 %, 17 quays, Mosjøen
  2.17 m. Elevation rides along; it decides nothing.

**Say which Sjøbergmarsjruta.** It is *three* chains, one each from UT.no,
Turrutebasen and FKB, all 20.48 km over the same ground and all starting at the
same rounded point — `ut-no-398130-7281098-20477`,
`turrutebasen-398130-7281098-20478`, `fkb-398130-7281098-20483`. Three
digitisations give three ascents, and UT.no's is a consumer GPS track whose noise
adds apparent climb the threshold suppresses but does not remove. Report all
three and record which the 996 m refers to; a single figure against a name that
resolves three ways is not an acceptance.

Done, except for one figure that does not reproduce and is written up below.
`libs/src/trails/io/sources/hoydedata.py` fetches and stores;
`libs/src/trails/routing/elevation.py` samples, lays a chain's series out of its
edges and reads the four figures off it; `network/norway.py` wires the two into
`build()`, so the map and the graph report share one cached graph as before. No
new dependency: `pyarrow` has its first user.

**The run**, at 5 m: **1,406,040 samples reduce to 1,017,874 distinct
coordinates**, two short of the 1,017,876 predicted and 28 % below the samples,
exactly as measured. 20,183 requests, six in parallel, **13.6 minutes** at 24.4
requests a second. The store is 11.7 MB of parquet for that build.

**A second build issues nothing at all** — not the plain rerun, which reads the
graph back whole, and not `--rebuild`, which re-samples all 1,017,874
coordinates and finds every one of them in the store.

**Nothing dived to −276 m.** The lowest reading in the network is **−43.9 m**,
and it is real ground: `datakilde: "dtm1"`, `terreng: "Steinbrudd"`, an N50 road
descending into a quarry. 580 samples of 1.4 million are below sea level, on 28
edges. 1,831 samples got no reading at all and are carried as gaps; two OSM
chains are nothing but gaps and report no figure rather than a flat one.

**Not one figure of the graph moved** — checked against the cached phase 1
graph rather than the printed report: same 11,290 chains and 234,358 edges, same
`chain_id` hash, same edge and chain geometry hashes, same total length to six
decimals and same total cost. The map is byte-identical once folium's per-build
element ids are normalised, and all six GPX exports are identical but for the
`<metadata><time>` every build rewrites.

**The four figures, and the name that resolves three ways.** UT.no publishes it
as *Sjøbergmarsjruta* and Turrutebasen as *Sjøbergmarsjen*, which reaches FKB
through the route-name join — so a search for either full name finds one
digitisation, misses two, and looks like a check. Matched on the stem:

| chain | ascent | descent | high | low | at 10 m | at 15 m |
|---|---:|---:|---:|---:|---:|---:|
| `ut-no-398130-7281098-20477` | **1,176 m** | 1,015 m | 903 m | 1.4 m | 1,174 | 1,170 |
| `turrutebasen-398130-7281098-20478` | **1,196 m** | 1,035 m | 903 m | 1.4 m | 1,188 | 1,182 |
| `fkb-398130-7281098-20483` | **1,195 m** | 1,034 m | 903 m | 1.4 m | 1,188 | 1,182 |

**The invariance holds**: 6 m of spread across 5, 10 and 15 m sampling on UT.no's
digitisation and 14 m on the other two, against 250 m of spread with no
threshold. That is what the threshold is for and it does it.

**The 996 m does not.** All three read near 1,190 m, and the disagreement is not
in the threshold — sampled uniformly every 5 m along the UT.no chain the
*unthresholded* figure is **1,370 m against the 1,214 m** in the decisions
document's table. The filter removes about the same amount either way, 200 m
here against 218 m there; it is the series underneath that differs by some
160 m. Three other definitions of "ignore gains under 5 m" were tried and none
lands on 996 either, and two of them are not invariant, which the document's own
table requires. The reasoning and what was ruled out are in the decisions
document under *Sample every 5 m*; the built figures are the reference from here
on, as phase 1's were.

Also worth knowing: **UT.no's digitisation reads lowest, not highest**, against
the expectation above that a consumer GPS track would add climb. And the
per-chain and per-edge figures came out 222.4 km against 148.4 km over the whole
network — the summed per-edge figure is 67 % of the real one, which is what the
two being kept apart buys.

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
folium polylines, simplified for rendering. This phase adds a *second* payload:
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
- The edge table beside it: `from_node`, `to_node`, `source`, `kind` and
  `chain_id`. **Not `cost`** — it is `length × source factor`, the length is in
  the geometry the browser already has, and the factors are six numbers; the 58
  ferry edges are the exception, flat. **Not the per-edge ascent** either: its
  only consumer is elevation-aware routing, which is explicitly not yet decided,
  and a route's own ascent is computed over its composed series for the same
  reason a chain's is.
- **A chain's edges have to come back in order, and the order is already lost.**
  The panel composes a chain's series from its edges' series laid end to end.
  Measured: **2,212 chains — one in five — have edges that do not join up in the
  frame's own order**, with jumps of up to 20 km, so this is not a matter of
  sorting by `from_node` breaking something that worked. The order has to be
  *reconstructed* and then carried: a position within the chain, written on the
  edge. Phase 2 solved it for itself by projecting each edge onto the chain — the
  browser has no chain geometry to project onto, so it must be told.

  This is the sharper form of the sorting trap below, and the reason it needs
  saying twice: a scrambled *tie* is caught by the round trip, a scrambled
  *order* is not, because every sample is still present and still correct. What
  comes out is a profile that looks like a profile.
- **The four per-chain figures — ascent, descent, high and low** — do not belong
  in this payload. They belong beside the drawn chains, which the map writes as
  polylines carrying a `trail-group-<chain_id>` class; phase 4 ships them as a
  table keyed by that class, the way the search box already ships its names. This
  phase carries the routing graph and the elevation series and nothing else.
- **Node positions**, which phase 6 needs to snap a click to the nearest node
  within 150 m and which nothing above provides. Do not ship a node table:
  derive the positions from the edge endpoints while decoding, so they cannot
  disagree with the geometry and cost nothing in payload. A linear scan over
  116,970 points answers a click in a few milliseconds, so no spatial index is
  needed in the browser — say so, or someone will build one.
- The elevation series, delta-encoded at **0.01 m** — the resolution the height
  service answers at, so that a file written from this payload reproduces the
  ascent it states. See phase 5.
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
| elevations, 1,406,040 samples at 0.01 m | **1.80 MB** |
| the two derived fields, one byte an edge | under 0.01 MB |
| the chain ids and the four count sections | **0.37 MB** |
| **total, as built** | **4.93 MB**, in a page of 37.4 |

The estimate above this table said 3.6 MB and was wrong twice over, both worth
keeping. It left out the stream's own structure — the chain ids and the counts
without which a concatenated stream cannot be cut back into edges, 0.37 MB — and
it budgeted the elevations at a decimetre. Phase 5 moved them to the centimetre
the height service actually answers at, so that an exported file reproduces the
ascent it states; that is the 0.8 MB between 4.12 and 4.93. **Ask what else has
to be in a file for the thing you budgeted to be readable.**

**The "allowance of 5 MB" these figures used to be measured against is gone**, and
the decisions document says why: it was never measured, and measured now it
guards nothing — quadrupling the payload costs about thirty milliseconds of a
1.6 second load. What replaces it is that anything put in here is argued for on
its own rather than against a remaining margin, and that the load time is the
acceptance.

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

It fits with room. An earlier draft of this table estimated the elevations at
2.2 MB before phase 2 had run; measured they are 0.98, so the total is 3.6 rather
than 4.8. The map itself is 24.2 MB, so this adds about a seventh to the page.
**Do not spend that margin on premature thrift**, and if something later does not
fit, report it rather than quietly quantising coarser — 1e-5 saves 0.7 MB and costs 1.11 m, which is
worse than the best source in the set and would undo what phase 1 was careful
about. And measure the decode: it is a number nobody has yet.

---

## Phase 4 — The profile panel

A panel at the foot of the map showing the selected chain's profile: distance
against elevation, its ascent, descent, high and low point. Foldable like the
legend, and folded until wanted.

**Draw it as inline SVG, by hand**, from the 5 m samples phase 3B put in the
page. No charting library: a script from a CDN does not load on a `file://` page
and fails silently, the way the OpenStreetMap tiles once did, and the legend, the
search and the click-highlight are all hand-written for the same reason. The
decisions document says what it consists of — **one path, two axes and a
crosshair**; the crosshair is specified there and had been claimed by no phase
until now, so it is written out under *The crosshair* below.

Where a series is longer than the panel is wide, reduce it to one point per pixel
column, keeping that column's minimum and maximum so no spike is lost. **That is
the exception, not the common case**: measured against the built graph, the
median chain has **36 samples** and 32 % have fewer than twenty; only **172 of
11,290** exceed nine hundred. The longest, the 42 km Rundtur
(`ut-no-414306-7244296-42442`), has **8,191**. So the reduction must not be the
only path through the code — bucketing 36 samples into 900 columns leaves 864 of
them empty, and a drawing routine that assumes one point per column produces a
broken path or none. Draw a short series as it is. The reduction touches the
curve alone, and nothing else smooths it.

**Ascent and descent are read, never recomputed.** Phase 2 computes them per
chain over its full series, and both the panel and the popup take them from
there. The temptation is to compute them in JavaScript, since the panel has the
series anyway — and then one number exists twice, in two languages, **against a
threshold**, and the popup and the panel disagree by a few metres on the same
chain. That is worse than either being wrong.

**High and low point come from the chain too**, though for a different reason:
they carry no threshold and could not disagree, but **the popup is rendered in
Python at build time**, so anything it shows has to exist there whatever its
provenance. Storing them is two numbers per chain and it keeps one rule instead
of two — *everything either place shows comes from the chain; the series is
decoded for the curve alone.*

**The popup shows ascent, descent and the high point** — which is what the
decisions document calls the main thing the build-time sampling buys, and it
needs nothing from phase 3B: each is one more entry in a field dict reading one
more chain column. The high point earns its place over the low one, because the
peaks stand around 1,200 m and whether a stretch stays at 400 m or climbs to
1,100 decides snow, weather and exposure in a way a low point does not.

### How the panel reaches a chain's numbers

Earlier drafts of this phase and of 3B said the chains are in the page as GeoJSON
and the panel has the clicked feature in hand. **They are not.** Measured in the
built page: **11,290 `L.polyline` and exactly one `L.geoJson`**, which is the park
boundary. A Leaflet polyline has no `feature.properties`, so there is nowhere on
it to put a number, and converting eleven thousand of them to `GeoJson` would
change the drawn objects a phase was accepted against.

What does exist is better and is already in use twice. Every drawn line carries
`className="trail-group-<chain_id>"` from `_group_class`, which is how the
click-highlight finds all of one route; and the search box already ships its text
into the page as **a table keyed by exactly that class**, because Leaflet path
options drop unknown keys — see `SEARCH_NAMES_ATTR` and `_record_search_names`.

**Do the same for the four figures and the bearing.** One table, keyed by the
chain's class, written at build time beside the layer rather than onto it. Five
values times 11,290 chains, in the page as JSON. That keeps the encoded payload to
what it is for — the routing graph and the elevation series — and it keeps the
panel from having to agree with anything.

### How steep it is, in colour

The curve carries its own gradient: **gentle under 15 %, steep 15–25 %, very
steep 25–40 %, extreme over 40 %**, each a colour and a stroke width, with a key
under the figures and the reading in the crosshair.

**The gradient is read over a 25 m window, never between neighbouring samples.**
Samples are laid per edge and every edge gets at least two whatever its length,
so 2 % of the steps in this network are under a metre apart and 3.4 % under two
— and a decimetre of model noise divided by a third of a metre is a cliff. Read
step by step the worst reads **2,754 %**; over the window nothing exceeds 100 %.
Where a chain is too short for the window, or a gap eats into it, less than 10 m
of run leaves the stretch uncoloured: no honest gradient comes out of two samples
and a stretch too short to measure is not thereby steep.

**The lowest boundary was chosen against the model's own noise.** On chains that
rise under three metres end to end — level ground — the height model reads a
median of **1.0 %** over the same window, a 99th percentile of 5.8 % and a worst
case of **9.2 %**. Not one level stretch reaches 15 %. So a coloured stretch is a
statement about the hill and never about the data, which is the whole reason the
boundary is not lower. Over the network the four bands hold **81.9 %, 11.5 %,
5.1 % and 1.5 %** of the ground.

**Smoothing was measured and rejected as unnecessary**: the median gradient reads
6.8 % between neighbours and 6.0 % over 50 m. Noise would collapse under that;
this does not, because it is terrain.

The stroke width escalates with the colour, so which stretch is the steep one
survives a red-green confusion. The crosshair is blue for the same reason — the
steepest band is red, and a red rule over a red curve reads as data.

### Which way the figures run

A chain is oriented so that its id stays stable, not because a walker is obliged
to take it that way. Ascent and descent are therefore true in a direction the
reader cannot see, and this phase has to make it visible — **once, three ways,
and all three must agree**:

- **In words**, from the bearing between the chain's endpoints, rounded to eight
  points: *+996 / −850 m towards NE*. Eight and not four, because 34 % of the
  chains lie more than 30° from a cardinal axis and a four-point label would be
  wrong about a third of the time; at eight nothing is more than 22.5° out.
- **As an arrow on the selected chain**, hand-drawn like the rest. This is what
  actually orients a reader — the words only work once you know which end is
  which.
- **As the profile's own direction**: the panel runs left to right in the same
  sense, so the curve rises where the walk rises.

Do not offer both directions. Two rows of numbers make the reader do the
matching, and the arrow is what removes the need for them.

**The bearing is computed once, in Python, in the metric CRS, and carried** —
into the same table as the four figures. It is not recomputed in the browser, for
exactly the reason ascent is not, and here the trap is sharper than a few metres.
At this latitude a degree of longitude is 0.41 of a degree of latitude, so a
bearing taken flat from `atan2(Δlon, Δlat)` is not the same bearing: measured,
that alone puts **4,444 of the 11,249 chains — 40 % — into a different one of the
eight points**. A further **241 chains lie within half a degree of an octant
boundary**, where any difference in method flips the label. Working in
`EPSG:25833`, where the graph is built, makes the question disappear.

Three things measured beforehand, so none is a surprise:

- **Every chain runs eastward.** `_canonical` orders by coordinate, so the
  bearing always falls in the eastern half: N 15 %, NE 28 %, E 21 %, SE 23 %,
  S 13 %, and never W, SW or NW. Not a bug, but it looks like one — put a
  comment where the bearing is computed.
- **41 chains are rings**, endpoints together. No bearing at all, and none
  needed: ascent equals descent whichever way round. They are the reason the five
  shares above do not add to a hundred.
- **493 are strongly wound**, straight-line distance under half their length.
  There the endpoint bearing is a simplification and stays one; the alternative
  is turning a label into a route description. The median chain is 0.93 as
  straight as its own length, so this is the exception rather than the rule.

### The three kinds of chain, and none of them may crash the panel

A profile exists for most chains and not all, and *most* is where this goes
wrong. Say what happens in all three cases rather than in the common one:

- **11,267 chains have a profile** and get everything described above.
- **21 ferries have no series at all** — length **zero**. There is no ground
  under a crossing and phase 2 samples none, so `ascent`, `descent`, `high_m`
  and `low_m` are all **`NaN`, not zero**. The popup keeps what it has —
  `_build_popup` drops a missing value already — and the panel says the crossing
  has no profile rather than drawing a flat line at zero. A flat line is a claim
  about the ground.
- **Two walked chains have a series in which nothing was read.**
  `osm-423700-7272625-5` and `osm-382608-7302481-2`, stubs of 5.1 m and 2.0 m
  outside the height model's coverage, each hold **two samples and two gaps**.
  **This is the case a length check does not catch**: `series.length === 0`
  stops the ferries and lets these two straight through, and what comes out is
  `M NaN,NaN` — a path the browser draws as nothing, with no error anywhere. The
  test is whether any sample was *read*, not whether any sample exists.

### The crosshair

Specified in the decisions document, claimed by no phase until this one. As the
pointer moves over the curve, a vertical line follows it and reads off the
distance along the chain and the height there. It reads from the **full** series,
not the reduced one — the reduction exists so the browser draws 900 points
instead of 8,191, and a reader hovering over a spike should be told the spike's
own height rather than the column's.

**Not in this phase:** marking that same position on the map. It is the obvious
next thing and it is a second mechanism — a marker to place, move and remove in
step with the pointer — and nothing in the decisions document asks for it. If it
is wanted, it is its own change.

### Where the panel sits

The legend already occupies the bottom left. Give the panel the width and leave
the legend its corner above it, or move the legend — but pick one. Both being
folded by default makes the clash rare, not absent. This is the one thing here
left to whoever builds it; everything else above is decided.

**Done when** clicking any chain with a profile draws it, shows an arrow for the
direction the figures describe, and reads the same ascent, descent, high point
and bearing in the popup as in the panel — with the panel taking every one of
them from the chain's table rather than recomputing it; and clicking one of the
twenty-three without a profile says so instead of drawing anything. The map still
zooms and pans while the panel is open.

Nothing that phase 3 was accepted against may move: **198** markers, **11,589**
paths of which exactly **1** non-interactive, **25** layers, the search control
at **10 px** above the zoom at 60, and the wheel taking zoom **9 → 11**. The
panel and the arrow are drawn into their own containers; if the path count moves,
the arrow was drawn as a path on the map and will be counted for ever after.

Three checks, for the three ways this goes wrong quietly:

- a chain along the shore, whose profile must not dive to −276 m where the
  sampling strayed over water;
- a chain whose arrow points one way while its curve rises the other. That is
  what a reversed series looks like, and no figure will reveal it;
- a chain whose popup and panel disagree about the bearing by one octant. That is
  what a second computation looks like, and the 241 chains near a boundary are
  where to look for it.

---

## Phase 5 — GPX export of a selection

The selected chain, downloadable, with real elevation — and the `<extensions>`
mechanism every later phase writes into, built here where there is one track and
no waypoints to get wrong.

**One file, dense.** Every vertex the chain has, extra points inserted only where
a gap exceeds 5 m, an `<ele>` on all of them. Do not resample every 5 m: that
drops the source's own vertices and rounds off every corner between two samples.
A sparser variant was considered and refused — Komoot and Outdooractive do not
know FKB's or N50's paths and cannot rebuild a line between points they were not
given.

**The two figures this paragraph carried were wrong, and wrong in the way this
document warns about.** It said the median chain comes to *37 points* and the
42 km Rundtur to *8,490* — those are `length / 5`, a plain resample of the very
kind the sentence above forbids, measured under a different rule from the one
they were stated against. Under the rule as written they are **48** and
**9,234**; under the rule as built, which lays the height samples in as well for
the reason below, they are **76** and **16,421**. A correct implementation would
have been told it had failed.

**And the fill has to land on the samples, not between them.** Keeping the
vertices and interpolating a height for each from the samples on either side
reads as the same curve and is not the same track: the ascent read back off the
file's own `<ele>` values then comes out **47 m under** the figure the same file
states for the Rundtur, and 2,637 chains disagree with their own extensions. Lay
every sample into the track as the reading it is, then space out whatever is
still wider than 5 m — the samples are laid per edge at `length / floor(length /
5)`, which is 5 to 10 m and not 5, so there is still work for that pass to do.
All 5,254 chains over 200 m then reproduce their stored ascent exactly.

`libs/src/trails/io/export/gpx.py` learns `<ele>` at the same time — it has
carried a comment marking the spot since it was written — so the six build-time
exports gain it too. The browser writes its own GPX; the two cannot share code
across that boundary but must agree on structure, and a test should compare them
on one chain rather than trusting that they do.

**Two faults in that writer were fixed before this phase, and the reason matters
more than the fix.** It thinned every export by default and reported a point
count taken from the geometry going in rather than the file coming out. Both had
lived since it was written, because **it had no tests at all**. It has six now.
Anything this phase adds to it gets one.

### What has to reach the page first

The browser writes this file, so everything in it has to be in the page. Most of
it is not, and that is the first work of this phase rather than a detail to
discover halfway through:

- **The per-chain name and source.** The figures table keyed by
  `trail-group-<chain_id>` carries `id, ascent, descent, high, low, length,
  point, bearing` and neither of these. The `<extensions>` need both. Add them to
  that table — it is the same mechanism, `figure_fields` in `add_trails`.
- **`no_path_m`**, for the line the decisions document asks for and this phase
  used to omit: *0.9 km with no path recorded in any source*. It is already on
  the chains, from `routing/coverage.chain_coverage`. It is not in the table.
- **The sources with their licences and versions.** Measured in the built page:
  `CC BY 4.0`, `ODbL` and `CC BY-NC` appear **zero times**, and so does any
  source version. They exist only in what the build prints to its console. They
  have to travel into the page as a block of their own — one entry per source,
  with its licence and the version or order date it was loaded at — because
  `<metadata>` is where they belong and the browser cannot invent them.
- **The ascent method as a string**: *DTM1, sampled every 5 m, gains under 5 m
  ignored*. The figure without it asserts nothing — the same route reads between
  965 and 1,214 m depending on the rule — and it is also what explains why Komoot
  will disagree.

### What the file says about itself

- **That it is a single chain**, with its name, its source and its chain id, in
  `<extensions>`. A file that identifies itself can be recognised on load rather
  than matched, which is what phase 8 reads; and an exported stretch becomes the
  start of a plan rather than a dead end.
- **The sources it draws on, each with its licence**, in `<metadata>`. A chain
  export usually has one source plus Kartverket's height model. **Do not fill in
  a single `<copyright>`** — a route mixing CC0, CC BY 4.0, ODbL and CC BY-NC has
  no one answer, and inventing one is worse than listing what is there.
- **The versions those sources were loaded at**, so a plan opened months later
  has a cause for any difference rather than a puzzle.
- **The ascent, with the method that produced it.**
- **The named ways the track follows**, in the track's `<desc>` — *via
  Tveråvegen, Gamle Stavassveg*. For a single chain that is its own identity.
- **How far it runs where no source records a path.** The wording says
  *recorded*, and it has to keep saying it: this is ground no register draws
  anything on, which is not ground with no path.
- **When it was written**, in `<metadata><time>`.
- **No `<time>` on the trackpoints**, and no speeds and no durations. A track
  carrying times reads as a recorded activity rather than a plan, and the rest
  would be guesses dressed as data.

**At the download, say what this file contains** rather than a generic notice: a
stretch of FKB is unproblematic, a stretch of OSM is share-alike, and the reader
should know which before pressing the button. Show the point count and the total
ascent beside it.

### Done when

**A blob download from a `file://` page works** — measured before this phase was
written, so it is not an assumption: Firefox saves it, with the offered filename,
and no error. Nothing here rests on that any more.

The export is finished when, **for a chain chosen in the browser**:

1. The file parses as XML and validates against the **GPX 1.1 schema**, which is
   ~30 kB and belongs in `libs/tests/fixtures/` rather than being fetched — no
   test may reach the network.
2. Its trackpoint count equals what the page said beside the button, and no gap
   between consecutive points exceeds 5 m.
3. No trackpoint carries a `<time>`, and a point the height model was never read
   at carries **no `<ele>`** rather than an invented one — 123 of the Rundtur's
   16,421. A reader breaks its run there; forcing an element onto every point
   contradicts item 5 below, which is what this phase is actually for.
4. `<metadata>` names the sources this chain actually uses, each with a licence,
   and holds no `<copyright>`.
5. Its ascent, read back off the `<ele>` values under the documented rule,
   matches the chain's stored figure.
6. The same chain exported by the Python writer and by the browser produces the
   same trackpoints and the same extension fields.
7. Nothing phase 4 was accepted against moves: **198** markers, **11,589** paths
   of which exactly **1** non-interactive, **25** layers, the search at **10 px**
   above the zoom at 60, and the wheel taking zoom **9 → 11**.

**Importing into Komoot and Outdooractive is a step for a person, and it is not
this phase's acceptance.** It cannot be run here — no account, no network to
either — and a phase whose acceptance its builder cannot execute has no
acceptance at all. The seven checks above are what an agent finishes against; the
import is the confirmation afterwards, and worth doing once.

---

## Phase 6 — Plan mode: clicking a route together

Switch it on and click. Every click appends a waypoint and routes from the one
before, so a route grows as far as you care to take it.

Appending is barely more work than a single pair — a route is a sequence of legs
and a click adds one — while restricting the phase to two points would leave it
too thin to use. What is genuinely harder is *changing* an existing sequence, and
that is phase 7.

**This used to be one phase covering everything through the export, the protected
areas and the naming of waypoints.** It was seventeen requirements and three
mechanisms that do not exist. The export is 6B and the protected areas are 6C;
nothing was dropped.

**A leg has four kinds and this phase builds all four**, because the one thing
worth not doing is shipping a route model that knows one of them. An earlier
split put the free legs in a phase of their own, which would have meant building
a model for routed legs, a stub refusing every click the graph cannot reach, and
then widening the one and deleting the other. Phases 2 and 4 both had to be
rewritten as one text after being corrected in pieces; this is the same shape,
seen in time.

| leg | distance counts as | profile | in the GPX |
|---|---|---|---|
| routed over the network | on foot | yes | one segment |
| free, over land | on foot | yes, sampled on demand | one segment |
| free, over water | **crossing** | none | ends the segment |
| a ferry crossing | **crossing** | none | ends the segment |

### Routing

- Snap a click to the nearest node within about 150 m; beyond that keep the raw
  point. The payload's decoder already offers `nearestNode`, and phase 3B
  measured it at **0.15 ms over 116,967 nodes** — a linear scan, no index.
- **Dijkstra with a binary heap over the weighted graph**, once per new leg. The
  cost of an edge is its length times its source's factor, both in the payload's
  header; a crossing costs the header's flat `flatM` instead. Nothing else is
  weighted — elevation-aware routing is a separate decision nobody has taken.
- **Take back the last point.** Without it one misclick ruins a route, and
  popping the final leg is trivial; everything beyond that is phase 7.
- Draw the route, show its **distance and ascent**, the crossings reported apart
  from the walking total. Both are summed off the edges the route uses — read,
  never recomputed, the rule phase 4 set.

### Legs the network cannot carry

A route that may only follow recorded ways is not a plan for this park: 19.9 km
of UT.no's own routes run where no source records anything, and the three-day
Rundtur reads **10.3 of its 42 km** that way.

- **A dashed straight leg** where no connection exists, counted apart from the
  routed distance and labelled as not a path.
- **Fetch its elevations on demand**, and cache them by the leg's endpoints.
  Measured before this was written: `ws.geonorge.no/hoydedata/v1/punkt` answers
  a `file://` page directly — `{"datakilde":"dtm1","terreng":"Skog","z":131.55}` —
  so no proxy and no CORS workaround is needed. Fifty points a request, the
  endpoint's own cap. Sample at the same 5 m the build uses and read the ascent
  by the same rule, or the two halves of one profile answer differently.
- **A free leg over water is not walking.** A private boat transfer of the kind
  UT.no's descriptions rely on: the samples classify it, `terreng: "Havflate"`
  instead of ground — the same field, in the same response, so the rule costs
  nothing beyond reading it. Its length goes to the crossings; it carries no
  profile; it ends a GPX segment. **A leg crossing a strait splits at the
  shoreline** into walked and crossed parts — the samples alternate, so the split
  falls out of them rather than needing a coastline.

### The profile

**Show the route's profile** in the panel from phase 4. It is the same panel, but
the series is now *composed* rather than read off one chain: the edges the route
uses, laid end to end, with the on-demand samples of any free leg spliced in at
the right place. The panel takes a chain's class today, so it needs a second way
in — one handed a series and a length rather than a class. The gradient bands,
the crosshair and the reduction all apply unchanged.

**Mark the straight stretches in the curve**, so the profile says the same thing
the map does. A crossing contributes no curve at all: there is no ground under
it, and a flat line at zero is a claim about the ground.

### Done when

A north-south traverse of the park can be planned by clicking a handful of points
along it, with its distance, ascent and profile shown and its crossings counted
apart; the last point can be taken back; a leg drawn across ground no source
records shows a profile fetched on demand; a leg across water shows none; and a
leg crossing a strait comes back as both. Check an approach from the coast —
Bønå or Visthus — since those only exist through a ferry. The case is known to be
possible: the main component spans **94 %** of the park and reaches all **17**
quays.

Nothing phases 4 and 5 were accepted against may move: **198** markers, **11,589**
paths of which exactly **1** non-interactive, **25** layers, the search at
**10 px** above the zoom at 60, the wheel taking zoom **9 → 11**, and a chain's
own export still reproducing its stated ascent to 0.00 m. **The route belongs in
a pane of its own** — anything drawn into the overlay pane is counted among the
map's paths for ever after.

---

## Phase 6B — A plan becomes a file — **built**

Phase 6 leaves the route on the screen. This makes it a file, through the writer
phase 5 built, and without it the feature stops one step short of its own point.

**Built, and what it decided is in the decisions document** under *What a route's
file says that a chain's cannot*: the leg modes go on the track and not on a
`<trkseg>`, a crossing's own line is never written, and a route with a hole in it
is refused rather than written. What the review found is in the review notes.

**It is not wiring, and an earlier draft of this phase said it was.** Measured
against the built page: `composeRoute` returns `height`, `distance`, `free` and
the route's totals, and **no coordinates at all**. A chain's shape carries `lat`,
`lon` and `stretches`; a plan's carries none of the three, and
`window.trailsProfile.runs` is `null` while a route is composed. `runsOf` and
`denseOf` — where the writer gets its points, its 5 m gap fill and its segments —
need exactly what is missing. The geometry does exist: all four leg kinds carry
`lon` and `lat` on the part. It is the composition that does not.

So the first work of this phase is a **track composer beside the profile
composer**, producing what the writer already knows how to read: coordinates,
heights, and a stretch boundary wherever the ground stops.

### The three mechanisms that do not exist

- **Neither writer can write a `<wpt>`.** `gpx.py` and `maps.py` contain the
  string zero times. And a waypoint is **not** part of the `<extensions>`
  mechanism: it is a GPX 1.1 top-level element written *before* `<trk>`, where
  the extensions are a block inside it. Extend the extensions for anything that
  is a scalar of the whole route; add waypoints as their own element in their own
  place, or the file will not validate.
- **A leg's mode has nowhere obvious to go, because legs and segments do not line
  up.** A segment is a stretch, and stretches break where the series breaks —
  four routed legs laid end to end are **one** segment, so a `<trkseg>`-level
  extension cannot carry four modes. Decide it here and say which: a list on the
  track naming each leg in order, or one segment per leg, which changes what a
  segment means. Do not leave it to be discovered while writing the file.
- **`creditsOf` is single-source.** It looks up `EXPORT.credits[figure.source]`,
  one string, because a chain has one source. A route has several, and this phase
  wants each with its length.

### And the distinction that will produce a wrong file quietly

**The composed series carries two kinds of `NaN` and they mean opposite things.**
A crossing pushes one because there is no ground under it; an unread sample is
one because the model had no reading for ground that is there. Phase 5 settled
what each deserves — the first breaks the track, the second only omits the
`<ele>` — and in a chain they are structurally apart, `stretches` against NaN
heights. In a plan they are both a NaN in `height`, told apart only by a
crossing's distance repeating the previous point's. Measured on a route over a
crossing: **12 NaN, of which one is the crossing.** Carry the distinction
explicitly rather than inferring it. Getting it wrong draws a line across a fjord
or cuts a route into dozens of pieces, and both look right on a chart.

### What the file says

- **Extend the `<extensions>` mechanism**, do not rebuild it, for everything that
  is a scalar of the whole route. A plan adds the clicked waypoints and each
  leg's mode: routed, free over land, crossing. Do it here rather than in phase
  8, because everything exported from now on should be loadable, and a file
  written before its description existed can never be restored exactly, only
  matched. Phase 8 adds the reading side.
- **Mark every `<wpt>` as set or generated.** Nothing generates one yet — 6C
  does — but the field goes in now, because phase 8 must never read a marker the
  map placed as a station somebody chose. The rule covers any marker the map adds
  by itself, now or later.
- **The sources list now spans several.** Report the length contributed by each
  and the licence that comes with it, so *3.2 km OSM (ODbL) · 1.1 km UT.no
  (CC BY-NC)* is visible before the download rather than a blanket warning. The
  page carries every source's licence and version since phase 5, and every edge's
  source since 3B; what it does not carry is a per-source length, which is a sum
  over the route's edges.
- **Say how much of it is waymarked**, as length in three buckets — marked,
  unmarked, unknown. This one *is* wiring: the page holds `waymarked` and
  `noPathRecorded` as a `Uint8Array` per edge since 3B, put there for exactly
  this. **Unknown is its own bucket and is never folded into unmarked**: measured
  over the walked network without its bridge connectors, **63.4 %** of the length
  is unknown, and FKB — the largest source at **33.8 %** — carries no marking
  information at all. Calling that unmarked asserts what no source says. Marked
  is 17.8 %, unmarked 18.8 %.
- **And how much runs where no source records a path** — *8 km with no path
  recorded*; the whole network holds 20.3 km of it on 189 edges. **State it as
  recorded, not as fact**: the sources over-record, so their silence is evidence
  and their lines are not. Do **not** add a survey-quality breakdown beside it —
  FKB discloses nothing about how it captured anything, so it would read *30 km
  not disclosed*. That question belongs to one line and is answered in its popup.
- **The download button is withheld today**, deliberately: phase 6 offers none
  for a composed series. Restoring it is this phase's visible outcome.

**Done when** a planned route downloads as a GPX that validates against the
shipped schema, carries its waypoints and each leg's mode, keeps a point the
height model never read while omitting only its `<ele>`, and states its own
ascent, its sources with their lengths and licences, its three marking buckets
and its unrecorded length — with the download line naming the licences the file
actually carries.

**Every break in the track is a crossing, and the rule runs only that way.** An
earlier draft of this paragraph asked for a break *at* every crossing, which is
false wherever one lies at either end: a route starting from a quay only a ferry
reaches has one crossing and **one** segment, and two crossings back to back
still yield two. Read the leg list for the order, and a break only as *a crossing
was here*. The decisions document carries the reasoning.

Nothing phase 6 was accepted against moves: **198** markers, **11,589** paths
with exactly one non-interactive, **25** layers, and the route in a pane of its
own.

**All of that was driven and measured**, on four routes covering all four leg
kinds. The figures are in the review notes; the shape of the file is in the
decisions document.

---

## Phase 6C — Where the route is, and what it passes — **built**

Two lookups the page cannot do today, and both are about naming ground rather
than finding it. The decisions document carries the reasoning; this is what was
measured before handing it over.

**Built.** The two decisions it owned are in the decisions document under *Which
protected areas count, and how much counts as passing through one*: **every one
of the register's five forms counts and every figure names the form**, and a
route reports an area it spends at least **100 m** in. What the build found is in
the review notes.

**Every reference figure below reproduced, and one of them was measured over an
extent it did not name.** The nineteen areas and the per-area kilometres came out
to the decimal — but 741.2 km is measured over the walked network *including* its
8,684 inferred connectors, at **5,899.9 km**, and 5,853.3 is the same network
without them. Both are printed now, each said which. It is the same fault the
26-against-39 correction below was written about, one line further down.

### What the network actually touches

The acceptance needs reference figures, so here they are. Over the bounding box
of the walked network Naturbase returns **43** protected areas — 39 nature
reserves, two national parks, one landscape protection area and one marine
protected area. **Nineteen are touched by the network**, 741.2 km — of the
5,899.9 km it walks, connectors and all, or of the 5,853.3 on ground a source
drew:

| area | verneform | km |
|---|---|---:|
| Lomsdal-Visten | Nasjonalpark | 647.82 |
| Holmvassdalen | Naturreservat | 25.69 |
| Strauman | Landskapsvernområde | 24.90 |
| Stavvassdalen | Naturreservat | 17.07 |
| Sirijorda | Naturreservat | 11.85 |
| *fourteen more* | Naturreservat | 13.80 |
| Innervisten | MarintVerneområde | **0.01** |

**An earlier draft said 26 reserves and no extent.** 26 is the count over the
smaller drawn zone; 39 is the count over the network's own box. Neither is wrong
and a figure without its extent cannot be re-derived, which this project requires
of every figure.

**And it said no reserve touches the park.** Measured, **Sirijorda does** — they
share a boundary at 0.0 m — and so does Innervisten. What that claim was used
for still holds, since sharing a boundary is not overlapping, but the premise
was wrong. Building it found a third: **Strauman** shares one too, and no two of
the thirty-one overlap in area, which is what lets the figures be added up.

**Seven are met over less than 400 m, not five** — 394.7, 323.7, 194.3, 150.8,
146.3, 67.3 and 5.1 m. The count was off; what it was used for, that a threshold
has to be decided, was not.

### Say which protected areas the route touches, and how far

*38 km, of which 22 in the national park and 3 in Strauman
landskapsvernområde*. Not the park alone: the rules inside a reserve differ from
those outside, and every approach to this one crosses ground reserves sit on.

- `naturbase.Source` **searches by name and needs a spatial query.** Measured,
  this is about ten lines: the same endpoint with `geometry`,
  `geometryType=esriGeometryEnvelope` and `spatialRel=esriSpatialRelIntersects`
  instead of a `where` clause. One request answers for the whole box. It is the
  first work of this phase and the smallest part of it.
- **Nothing on any edge or chain says which area it lies in.** Measured, the
  edges carry `waymarked`, `no_path_recorded`, `elevations`, `ascent` and
  `descent` and nothing about where they are. Deciding it at the 5 m samples, as
  the decisions document sets out, means a new field from build time — and
  therefore a `GRAPH_LAYOUT` bump and a rebuild. This is the first phase since 2
  to touch the graph.
- **A free leg does not get it from the samples it fetches**, and both this phase
  and the decisions document used to say it did. The samples give a position; the
  answer needs the polygons, and the browser has **one of the nineteen** — the
  height service returns `datakilde`, `terreng` and `z`, and `terreng` is ground
  cover, *Havflate* or *Skog*, not a protected area. So the page has to carry the
  boundaries. Measured: the nineteen come to 25,331 vertices, 1.03 MB of GeoJSON
  and 0.37 gzipped; simplified to 10 m, **0.08 MB raw and 0.03 gzipped**, against
  a 37.5 MB page. Cheap, and it still has to be decided rather than discovered.

  **The claim that 10 m lies inside the ±5 m the sampling accepts is false, and
  building it measured that.** Douglas-Peucker at 10 m moves this register's
  boundaries by up to **16.1 m**; at 5 m by **5.9 m**, which is the tolerance the
  claim is true at, and the difference between the two is 0.02 MB. Built at 5 m.
  What the page carries is the **31 areas that meet the zone**, not the 19 the
  network touches — a leg drawn straight can enter one no edge reaches — at 4,195
  vertices and 0.09 MB.

**Two decisions this phase owns.** *Which `verneform` count*: `naturbase.Layer`
already separates the five, and a walker reading that a route passes a marine
protected area learns something different from a nature reserve. And **how little
counts as touching**: five of the nineteen are met over less than 400 m and one
over **ten metres**. With no threshold a route that brushes a boundary reports an
area it never entered, and generates a pair of waypoints for it. A rounded label
is a threshold, and every rule this project has about thresholds applies here.

Put the figure in the exported description, and a **generated waypoint** at each
crossing so a reader sees where the route enters and leaves. GPX holds waypoints,
routes and tracks, and no polygons; the marker is the only way to carry a
boundary at all. Mark them generated — 6B put the field in and
`gpx.py` already carries `WAYPOINT_GENERATED`.

### Name a waypoint after what is there

When one lands within about 50 m of a named point the map already draws — a hut,
a quay, a trailhead, a farm — take that point's name, type and position for the
`<wpt>`, while the route stays on the network. It is the difference between a
file reading *Lavasshytta → Sæterskaret skogstue → Bønå ferjekai* and one reading
as three coordinates.

- **Those points are not machine-readable in the page.** They are drawn as
  **1,411** `L.circleMarker` and **865** `L.marker` with their names inside popup
  HTML. A lookup needs a table of name, type and position, keyed the way the
  chain figures already are — `CHAIN_FIGURES_ATTR` is the shape to copy.
  **This is the fourth time a phase has assumed a mechanism that does not
  exist**, after phase 4's GeoJSON properties, phase 5's licences and 6B's route
  geometry, so check for the table before planning around it.
- Lavasshytta is drawn, so the acceptance below can actually be run.

**Done when** a route through the park reports the length it spends in each
protected area it passes under the threshold this phase sets, its exported file
carries a generated waypoint where it enters and leaves one, and a waypoint set
beside Lavasshytta comes back named after it. The graph is rebuilt, so every
phase 1 figure must come out unchanged — 11,290 chains, 234,358 edges, 116,967
nodes, 757/747 components, reach 50.8 km = 94 %, 17 quays, Mosjøen 2.17 m — and
nothing phase 6B was accepted against moves.

**Done.** A five-point route over UT.no's 42 km Rundtur reports *34.01 km in
Lomsdal-Visten nasjonalpark* of 36.89 km walked, its file carries a generated
`<wpt>` where it enters and where it leaves, both **within 0.42 m** of the
boundary the register draws at full precision, and a point set beside
Lavasshytta comes back named *Lavasshytta*, type *hut*, 3.8 m away. Every phase 1
figure is unchanged, the rebuild made **no** height request — the point store is
byte-identical — and the page still reads 198 markers, 11,589 paths with one
non-interactive, 25 layers, 10 px over 60, zoom 9 → 11, the plan's own pane
0 → 13 → 0, and the Rundtur's chain export still 16,415 points whose ascent reads
back to 0.00 m.

**Nothing new is drawn.** The boundaries are carried as data and never rendered:
anything in the overlay pane joins the 11,589 for ever, and the plan pane's 13
paths at five points is an acceptance figure of its own. Showing a boundary on
the map is phase 8's business, where there is a reading page to put it on.

---

## Phase 7 — Editing the waypoints — **built**

Phase 6 can only append and undo. This is what makes a route something you can
work on rather than restart.

**Insert into the middle**, which splits a leg; **delete**, which merges two;
**reorder**, which changes which legs exist at all; and **drag**, which moves one
where it stands. The route, its numbers and its profile follow.

Two of those need saying plainly. **Insert is this phase's own addition** — the
decisions document's numbered requirement is *"waypoints can be reordered and
removed"* and says nothing about inserting; it is worth having and it is not in
the contract. And **drag was in the acceptance and in neither list of
requirements**, appearing only in an aside about caching. It is a requirement
here now, because the acceptance already tested it.

### Two acceptance figures will move, and that is not a regression

A waypoint today is an `L.circleMarker` in the `trailsPlanRoute` pane with
`interactive: false`. Measured in the built page: on the map its `dragging` is
**undefined** and `draggable: true` is silently ignored, while an `L.marker` gets
a live dragging handler and lands in the marker pane. So a draggable waypoint is
a marker, and for a five-point route the plan pane goes from **13 paths to 8**
while the marker pane goes from **198 to 203**.

Those two numbers are what every review since phase 3 checks first. Say which way
they moved and why, or the next one reports a regression. If the pins stay
circles and dragging is written by hand on the path, say that instead — but then
the paragraph below applies twice over.

### Clicking a waypoint and clicking the map are the same gesture

Everything the plan draws is non-interactive: measured, **all 13 paths** of a
five-point route. Selecting or deleting a waypoint needs the opposite, and the
moment a pin becomes interactive it catches the clicks that fall through to the
map today — where a click **places a new waypoint**. Decide it here and write the
decision down: a modifier, a mode, a hit only on the pin's centre, something. The
trap list already carries the shape, *a boundary polygon swallows clicks*, and it
cost this project a week of trails that could not be clicked.

### Dragging over a free leg is an uncapped request stream

There is no debounce and no cancellation anywhere in plan mode — measured, the
only `setTimeout` near it belongs to the search box. The decisions document
anticipates half of this: *"cache them by their two endpoints so dragging a
waypoint back and forth does not fetch the same ground twice."* The cache only
helps for ends already visited; dragged across new ground, every position fetches
new ground. **6B's own review found exactly this shape** — an unbounded number of
requests from one misclick — and capped it at 20 km. Dragging brings it back per
mouse move.

So this phase owns a **throttle while a drag is live and cancellation of a settle
whose waypoint has already moved on**, and a leg must not be drawn from a reply
that is no longer wanted.

### Recompute what changed, for the reason that holds

Measured: placing a point costs **19–76 ms** including its Dijkstra, and
`state()` with the whole route composed costs **3 ms**. Recomputing all four legs
of a five-point route is therefore about **200 ms** — perceptible and not a
problem. So *recompute only what changed* is not worth writing for routed legs.

It is worth everything for **free legs**, where one leg is seconds of network,
and for a drag, where the recompute happens many times a second. That is the
reason to give, and the redraw follows the same rule: the profile is composed in
3 ms, so redrawing all of it is fine, and it is the fetching that must be
avoided.

The export needs nothing: since 6B it is written from `composeRoute`, so it
already follows whatever is currently drawn without knowing how it got there.

**Done when** inserting, deleting, reordering and dragging each change the route
consistently; the distance and the profile keep up while a waypoint is dragged;
a drag over a free leg issues no request for ground it has left; and the exported
GPX matches what is drawn. The graph is untouched, so every figure holds —
11,290 chains, 234,358 edges, 116,967 nodes — and of the page's figures only the
two named above may move, in the direction named.

### Built, and what it came to

Every acceptance figure reproduced and the two named ones moved as predicted:
the plan pane **13 → 8** paths and the marker pane **198 → 203**. A third moved
with them, `.leaflet-marker-icon` from **0 to 5**, and it is the same fact
through a second lens — folium overwrites that class on its own markers and
these are Leaflet's own. Figures and the three decisions in *What phase 7 found*.

The shape it took: **the legs follow from the waypoints rather than being edited
beside them.** Every edit rewrites the list of points and nothing else; a leg
survives exactly when it still runs between the same two waypoint objects, and a
waypoint that has moved is a new object. Insert costs two legs, remove one, a
move the three that touch the point — and the cancellation is the same rule read
backwards: a reply about ground a waypoint has left arrives to find its leg off
the route.

---

## Phase 8 — Loading a route and working on it — **built**

Read a GPX back in and carry on from it: one of our own exports, or a track from
somewhere else.

It comes after phase 7 for a reason rather than by convenience — a loaded route
has to be immediately editable, and editing is what phase 7 builds. Before that
you could load a route and look at it, which is not the point.

**Loading happens in the browser**, on a page served from `file://`, and that
single fact governs the whole phase. Checked before handing it over: a page there
*may* read a file the reader picks — `<input type="file">` and `FileReader`
returned all 1,197,976 bytes of a chain export and `DOMParser` found its
trackpoints. Nothing else about this phase would matter if that had failed. The
page has no file control today; anything over the map has to be a Leaflet control
for the reasons in the trap list.

### The first work is a spatial index, not a matcher

The matching rule is right and it is worth stating first: **walk the track, find
where it runs along an edge within a tolerance, swap that stretch for the edge,
keep the rest verbatim** — and check that the track runs *along* the edge rather
than merely near it, because a track beside a parallel path snaps to the wrong
one on distance alone. `attach_nearest` with `min_overlap` in
`trails.utils.geo` is where that lesson was learned and is worth reading.

**It is not a component this phase can use.** It is Python, it takes
GeoDataFrames, and it copies attributes between two datasets; the work here
happens in a page, on one track against 234,358 edges. And the page has nothing
to do it with. Measured: `nearestNode` is a **linear scan over 116,967 nodes at
0.135 ms**, and over the edges there is nothing at all — one linear pass over the
948,465 edge vertices costs **2 ms**. Matched naively, a track of the median
foreign size below is **2.9 s** of frozen main thread and the largest is **10 s**,
before any overlap test. This map already froze once over redraw cost.

So: a grid or another index over the edge geometry, built once, is the first
work. Say what it costs to build and what a lookup costs, the way every other
figure here is stated.

### What this map wrote is two different files

Measured, and the phase used to treat them as one:

| | `<wpt>` | legs | carries |
|---|---:|---:|---|
| a chain export | **0** | **0** | its `chain_id` |
| a route export | 29 | 4 | its waypoints and their `origin` |

So *"anything this map wrote restores exactly"* is true of a **plan** and not of a
**chain**: a chain export has no waypoints to route between and no legs to
rebuild. It is recognised by its id and drawn as the chain it already is, or it
becomes one fixed leg like any other track. Decide which, and say so.

A route export restores from its `<wpt>` list, and **the `origin` field is what
makes that safe**: 6B marks every generated marker, and loading must ignore those
or a route gains stations nobody placed and starts routing through them.

### Three modes, and the third one is a leg kind that does not exist

| mode | what it does | effort |
|---|---|---|
| take it as it is | the whole track becomes one fixed leg, untouched | small |
| align to the network | read the `<wpt>` list and route between them afresh | small |
| **match where a path exists** | follow the track, swap the stretches that run along edges, keep the rest | **the real work** |

The middle one is not routing a foreign track. Re-routing between waypoints
throws the shape away — right for one of our own plans, which *is* a handful of
waypoints, useless for a track with thousands of points and none.

**A fixed leg is a fifth kind and the file format was fixed around four.** The
page knows `routed`, `land`, `water` and `ferry`; 6B writes each part as
`<trails:part kind>`, so a fifth changes what an exported file says — and this
phase both reads that format and writes it. Name the kind, and say what a reader
of an older file does with one it has never seen.

Build it as one phase even though the ends are cheap. Split, and the loading and
parsing gets written twice.

### The acceptance, which can actually be run

An earlier draft asked for a GPX from Komoot. There is no account and no network
here, and phase 5's readiness check already established that **a phase whose
acceptance its builder cannot execute has no acceptance at all**. The foreign
tracks are already on disk: **35 UT.no recordings** under `.cache/downloads/ut/`,
**62,158 points**, median **1,443** and largest **5,147**, with **no `<wpt>`, no
`<extensions>` and a timestamp on every point** — consumer GPS, genuinely
foreign, already fetched.

**Done when** a route this map exported loads back with the same waypoints, the
same leg modes and the same walked figure, with its generated markers ignored; a
chain export is recognised for what it is; every one of the 35 UT.no tracks loads
without error and each mode does what it says; a matched track keeps its own
shape where no path exists and follows the network where one does; and a loaded
route is editable by phase 7's four edits like any other. Nothing phase 7 was
accepted against moves: **11,589** paths with one non-interactive, **25** layers,
and the plan's own panes at **8 paths and 203 markers** with a five-point route.

### Built, and what it came to

**The index first, and it is the reason the rest is fast.** A uniform grid over
the edge geometry in scaled degrees, one entry per segment per cell its box
touches, laid out the way the node adjacency is: count, prefix-sum, fill. At
100 m cells it is **29–42 ms to build, 799,863 entries, 8.85 MB**, and a lookup
is **0.7 microseconds** against the 2 ms linear pass the page had before —
2,800 times cheaper. Built on the first thing that asks and then kept, so a
reader who never loads a file never pays for it. Three cell sizes were measured
before one was chosen, and the table is in *What phase 8 found*.

**Three modes, and the fifth kind is `track`.** Take it as it is makes the whole
recording one `track` leg between its own two ends; align reads the `<wpt>` list
and routes between the points afresh; match anchors the recording to the network
every 250 m, routes between the anchors, and keeps verbatim whatever the test
below refuses. A break between two segments is a **crossing** in all three, never
a walked line — GPX has no way to say a segment is a boat, so a break is all a
crossing leaves behind, and joining the two ends would draw somebody a route
across a fjord.

`track` is written as `<trails:part kind="track"/>` and its metres go in a
bucket of their own, `recorded`, beside `undrawn`. The buckets have to sum to
`walked`, and ground read off a file belongs in none of the four that were there:
no register was asked about it, which rules out marked, unmarked and unknown, and
it is not a connector. **A reader that has never seen it** — Komoot,
Outdooractive, an earlier build of this map — reads the track and the waypoints
exactly as before, because a part kind lives in `<extensions>` and GPX 1.1 says a
reader may ignore those. **This page**, given a kind it does not know, cannot
restore that leg exactly, so it routes it between its two waypoints and says how
many it had to: never fatal, never silent.

**A chain export becomes one recorded leg, and is recognised while it does.** It
has no waypoints to route between and no legs to rebuild, so treating it as a
plan was never available; drawing it as the chain it already is belongs to phase
4, where a chain is one click away, and a chain id out of an older build names
nothing in this graph. So it loads as a track like any other and the page says
what it was: *a chain export: Rundtur i Lomsdal-Visten… (ut-no-414306-7244296-42442)
· 16,415 recorded points*.

**The matching rule is `attach_nearest`'s and one more.** What share of the
recording lies along the path offered to replace it, at **0.6** over a **25 m**
tolerance — and, because that test is one-directional, a routed stretch may not
be **longer** than the recorded stretch it replaces by more than the tolerance at
each end. Without the second half the 42.44 km *Rundtur* came back at 48.2 km. A
heading test at **60°** runs per point and keeps a side path at a junction from
ever being a candidate, and an anchor is only taken at a node the recording
passed within the tolerance of, which is what stops a 4.7 km edge being handed
back for a walk that turned round 332 m short of its end.

**And a file says the height model only where the model was read.** A stretch
kept as recorded carries the heights the loaded file had on its trackpoints, so
crediting Kartverket for them and stating they were sampled from DTM1 every 5 m
was a false claim in a file somebody takes into the terrain. A part now says
which, and the description says *the climb is the loaded file's own heights, not
the model*.

**Editing works because a waypoint carries where it came from.** An anchored
waypoint holds its index into the recording, so a point put into the middle of a
recorded leg splits it into two recorded legs rather than replacing the whole
thing with a routed line — measured with a real click, `elementFromPoint`
asserted: 7,420 m in one part becomes 1,759 + 5,660 in two, and the walked figure
does not move. Drag one off the recording and it loses its index, and its legs
become ordinary ones. Nothing needed a case of its own: the rule that legs follow
from waypoints already said all of it.

**What it was accepted on.** All **35** UT.no recordings load in all three modes
with no error and no failed leg, median **37 ms** and **67 ms** at the worst.
Matched, **99.1 %** of 376.3 km lands on the network's own lines and no recording
comes back longer than it was recorded; three keep ground of their own, which is
the other half of the claim. A five-point route exported and loaded back aligned
returns `7265.882765177558` m walked against `7265.882765177558`, the same
ascent to the last bit, the same 2,005 vertices, the same five waypoints to seven
decimals, the same four `routed` legs — and its one generated marker skipped and
said so. A track kept as recorded, written out and read back aligned, comes home
as recorded, because the file says `kind="track"` and the reader honours it. The
chain export still reads 16,415 points and its ascent back to 0.00 m. **11,589**
paths with one non-interactive, **25** layers, **10 px above 60**, wheel
**9 → 11**, the plan's panes **8 paths and 203 markers** at five points.

**One thing was deliberately left undone**: a part is a whole edge, so a
recording that walks half of a long one is kept as recorded rather than
half-matched. That is 3.5 km of 376 and the whole difference between 99.1 % and
100 %. What it would take is in *What phase 8 found*.

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
