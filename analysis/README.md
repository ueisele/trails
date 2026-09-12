# Trail Data Analysis

Exploratory analysis and experimentation with trail data using Jupyter notebooks.

## Overview

This directory contains:
- **Notebooks** - Interactive analysis and visualization
- **Scripts** - One-off analysis tools
- **Cache** - Local data storage (git-ignored)

## Getting Started

### Launch JupyterLab

```bash
command make notebook
```

### Notebooks

- `01_data_exploration.ipynb` - Initial exploration of Norwegian trail data from Geonorge

Each notebook is self-contained and downloads/caches its own data.

### Documents

- `docs/route-planning-decisions.md` — what was decided about the route planning,
  and what was decided against
- `docs/route-planning-phases.md` — the phases it was built in, each with what it
  is accepted against
- `docs/route-planning-review-notes.md` — how every figure in those two was
  arrived at, what this codebase does that will bite, and what to pick up next.
  Start here if you are coming back to this after a while.
- `docs/abisko-decisions.md` — the second map, Abisko in Sweden: what was decided,
  what is open, and a log of how each open point was settled

### Scripts

**The map** — builds `analysis/output/lomsdal-visten.html` from seven sources,
or `abisko.html` from five, plus one GPX per source beside it. Every line it
draws is a chain out of the routing graph below, so a drawn line and a
selectable track are the same object; the two scripts share one cached build:

```bash
command make map
command make map ARGS="--park abisko"
```

Everything it downloads is cached, so a second run does not fetch again and takes
about a minute. The first run on an empty cache fetches some 150 MB from Geonorge
and Overpass and takes considerably longer. Re-fetch on purpose with
`--force-download`; `command make cache-clean` throws the cache away entirely,
which is rarely what you want.

**The Abisko ground** is two more targets. `command make tiles` copies the base-map
tiles for the box out of Lantmäteriet's open download over FTP (no login), and
`command make dem` builds z8–z13 height tiles from the 1 m height model, which
needs the Geotorget login in the environment — run it from `home/trails-map` as
`sops exec-env secrets.sops.env 'cd ../../trails && command make dem'`. Both
resume, both write under `analysis/output/`, and `make deploy ARGS="--tree …"`
uploads what they wrote. `analysis/docs/abisko-decisions.md` carries every figure.

**Or the whole chain at once**: `command make abisko` runs tiles, dem, the graph
with its report and the page, in that order, and from `home/trails-map`
`just abisko` is the same with the login supplied. Every step resumes or reads
the cache, so a rerun costs a few minutes of checking and the page; it builds
and does not publish.

Both targets pass `ARGS` through, so `command make map ARGS="--approach-km 10"`
works; the script itself is `analysis/scripts/lomsdal_visten.py`. Which map is
`--park` (default `lomsdal-visten`); the script's `PARKS` table says what a park
decides, and its `BUILDS` table which country's registers are read for it. The
Swedish build is over the park's box rather than a band round the boundary, so
`--approach-km` does nothing for it; it reads the Topografi 50 delivery, the
register's files and the height mosaic off the cache, and needs the Geotorget
login only when one of those is missing (`command make dem` is what puts the
mosaic there). Everything a Swedish page differs in — which registers, what a
popup says, what a file credits, where a straight leg's heights come from — is
`build_sweden`; the page itself is assembled by one function for both.

Worth knowing:

| | |
|---|---|
| `--output-dir DIR` | write somewhere other than `analysis/output/` |
| `--approach-km N` | how far beyond the park boundary to draw (default 15) |
| `--simplify-m N` | vertex tolerance for what is *drawn*; the GPX keeps full detail |
| `--highlight NAME` | mark every position the place-name register holds for a name |

**There is no way to leave a source out, and that is deliberate.** The `--no-*`
switches and `--fkb-km` were retired in phase 3: the map draws the routing graph,
and a graph missing a source is not smaller but wrong — without the roads the
largest component falls from 79 % of the network to 5 %, without the ferries
eleven of seventeen quays are unreachable. Switch a layer off in the legend
instead; it does the visual job better, per layer, instantly and without a
rebuild. See `docs/route-planning-decisions.md`.

**The routing graph** — builds nothing visible and draws nothing. It reports the
statistics the route planning is verified against: chains per source, edges,
components, how far the network reaches across the park, and whether the coast is
reachable without the ferries. Then what each source's chains carry, and what
every walked edge is told by the ground it runs over — how much of the network is
waymarked, and how much of it runs where no source records a path at all. That
last one reads in one direction only: the sources over-record, so their silence
means something and their lines do not.

```bash
command make graph
```

The built graph is cached under `.cache/objects/` and keyed by everything that
shapes it, so an unchanged rebuild is instant and a changed one is detected
automatically. Force one with `--rebuild`. See `docs/route-planning-phases.md`.

Both scripts build it through `trails.network.norway`, with the same parameters
and therefore the same cache key, so whichever runs first pays and the second is
instant. The parameters the map does not offer fall to that module's defaults
rather than to the map's own, which is what keeps the two agreeing. It takes
`--park` too, and reports Abisko's graph against its own landmarks.

**Sweden has its own module**, `trails.network.sweden`, built on the same shared
core (`trails.network.graphs`: parameters, fingerprint, derived fields, the build)
from three registers instead of seven: Lantmäteriet's *Topografi 50* delivery
(`io/sources/topografi50.py`, fetched through the Geotorget download API with the
login, read by box out of the country GeoPackage), Naturvårdsverket's nightly
files — the protected areas and the trail register, `io/sources/naturvardsregistret.py`,
no login — and OSM. Heights come off the cached 1 m model rather than a point
service; the place names are Lantmäteriet's *Ortnamn* (`io/sources/ortnamn.py`, the
country file fetched once with the login); and the page reads the same model off the height tiles `make dem` cut
(`maps.HeightTiles`, beside the provider's map tiles; the worker keeps them and
the offline panel counts them). A state trail's popup links to the county's page
for it on Naturkartan, one link per *BD* number on the chain, out of a hand-kept
catalogue (`analysis/routes/abisko-naturkartan.toml`, `io/sources/naturkartan.py`):
links only, since Naturkartan's terms allow private use alone and the line itself
is the register's. `analysis/docs/abisko-decisions.md` is the record.

### What the map does once it is open

The legend at the bottom left **is** the layer control: every row switches its own
layer and a row whose layer is off is greyed rather than hidden, so it is still
the key to that colour. The base maps sit above the rows.

**Click a line** and the panel at the foot draws its profile — distance against
height, coloured by how steep the ground is, with the ascent, the high and low
point, the steepest stretch and which protected areas it runs through. It is
drawn **true to scale**: one metre is the same number of pixels up as along, so
the angle you see is the angle on the ground. Then:

| | |
|---|---|
| move the pointer over the curve | a reading, and a dot on the map at that exact place |
| turn the wheel over the curve | zoom in, as far as one height reading per pixel — on a long route only, since most lines are already drawn finer than they were measured |
| drag the curve | move the window along; double-click puts the whole line back |
| drag the grip on the panel's top edge | make it taller, which on a steep line is resolution rather than taste |
| *Download GPX* | the line as a file, with a height on every point and no invented time |

**Plan a route** with the button at the top right. Every click on the map places
a waypoint and the way between is worked out over the network; click the route
itself to put a point in the middle, drag a pin to move it. Click the point count
to unfold the list: one row a point, with what it is called and how far into the
walk it comes, draggable to reorder and with its own button to take one out. The
route's own profile is drawn in the same panel and marks each of your points on
it, and *Download GPX* writes it with its waypoints, its legs and the protected
areas it enters and leaves.

**A tour can be walked in stages.** Mark a point in the list as the end of one and
the route falls into stages, each with a heading carrying its own kilometres, its
climb, a name you can give it and its own file. A point where one stage hands over
to the next carries a second ring, on the map and on the profile. *All stages (zip)* writes every
stage and the whole tour with its marks in one archive. Name the tour in the box
above the list; the marks travel in the file, so loading it back gives you the
tour and its stages.

**The ground can be kept on the device**, under *Offline* in the menu. It says
first whether this browser can keep anything at all — a service worker exists in
Safari and in a map added to the Home Screen, and in no third-party browser on
iOS, so that line is the one to read before anything else. Then a switch, which
makes the map answer from what it holds and never reach for a network, so
coverage is checkable at home rather than in a valley; switching it on with
nothing kept opens the chooser instead of handing over a blank map.

The chooser asks two things and shows the exact consequence of both: **what** —
a band along the route you planned, the map as it stands on the screen, or a band
along every path drawn here — and **how fine**, from z14 down to z18, which is
where Kartverket's own tiles stop. A 42 km tour is about 95 MB at z16 and 279 MB
at z18; everything drawn is 377 MB at z14 and 2.1 GB at z16, and is refused above
that. Anything larger than the device will hold is refused too, with the room it
actually has. *Delete* gives the space back.

Both the switch and what you kept survive a reload, with or without a signal.
And with the switch on, ground you did not keep stays blank **even when there is
a network** — which is the point of being able to turn it on at home: it shows
you what you are missing while you can still do something about it.

Everything else already worked with no signal: every line, every profile, the
routing, the search and the files are inside the document.

**A GPX can be loaded back.** The file is read and described first — a route
this map wrote, a chain export, or somebody else's track — and then it asks how to
read it, with the sensible answer already chosen and a sentence saying what each
one would do to *that* file: restore what the file describes — for one of this
map's own routes that is the plan itself, points, legs and all — route afresh
between its waypoints, or match it onto the network wherever a path exists. Loading replaces
whatever is on the map, so the question says how many points that is. Once the
route has settled the map goes to it.

### Checking the built page

```bash
command make drive                                          # the Lomsdal-Visten page
command make drive ARGS="--page analysis/output/abisko.html"   # the Abisko page
```

Drives the built map in a browser and reports **some 600 readings** (609 on the
Lomsdal-Visten page, 609 on Abisko's, 2026-09-12) — the counts the
page draws, the profile's scale at several zooms, the wheel, the crosshair's
mark, the point list, plan mode and the file it writes, the chrome on a phone,
which zoom the scale bar says it is on, that the map opens with the network off,
and that terrain the reader asked for is kept and drawn and can be deleted again.
**About ten minutes a page** — 16.6 MB of HTML for Lomsdal-Visten and 3.3 for
Abisko, loaded twice over for the offline check — and about two minutes of it
fetching real tiles from Kartverket on the first page, which is what it costs to
prove that a kept tile is terrain and not the worker's own blank. Run it as a
transient unit (`systemd-run --user --unit=abisko-drive …`); its output is
buffered until the unit ends.

**Drive it once, into a file, and grep the file.** Running it twice to see two
parts of one report costs two runs. While one behaviour is being written,
`ARGS="--only <word>"` is ten readings instead of six hundred. And **build before
driving**: the run reads the page `command make map` last built.

**The checks are the same for every page; what is a page's own is its `Scene`** in
`drive_map.py`, chosen by the page's stem: the long chain the profile checks select, the
ground the position and offline checks stand on and look at, the request pattern its heights
come by, and the figures its last build recorded. A page whose sheets are addressed from the
root — Abisko's — is served from its directory rather than opened off the disk. A reading whose
figure the scene has not recorded yet is reported as **new**, with what was read, so the first
drive of a page is the run that fills its scene in. A check that needs ground a scene does not
have is named in the scene's `skips` and reported as skipped by it (both scenes have all their
ground today); **any other skip is reported as GONE and exits 1**, because a
chain the page no longer holds takes every check past it along, and a short green run is the
one failure nobody reads.

**It does not overlap with `command make test`.** The tests assert on the page's
source; this asks a running browser what the page actually does, which is the
only thing that can tell you whether the drawn angle is right or a control has
gone under another. A red reading is labelled either a broken invariant — a
defect — or a moved figure, which happens legitimately when the sources change.

**Publishing** — puts the map the last `command make map` produced on the web, then drops it from
the edge cache so the new one is served at once:

```bash
command make deploy
command make deploy ARGS="--dry-run"     # says what it would do, changes nothing
```

It **does not build**. That separation is deliberate: a deploy that rebuilt first would make
"publish the thing I just looked at" impossible, and the thing you just looked at is the only one
worth publishing.

It puts up **the page and its companions**: the compressed page, the worker (`sw.js`, or
`abisko-sw.js` for the second map; uncompressed, `no-cache`, so an edge holding yesterday's
worker cannot hold yesterday's map with it), the manifest (`application/manifest+json`) and the
four icons. `ARGS="--map abisko --tree tiles --tree dem"` mirrors the two trees first.
Without the last of those the map cannot be added to a Home Screen — and without
that, iOS deletes everything the map kept after seven days of not being opened.

Where it goes is not configured here. This repository is public, so the bucket, endpoint, hostname
and zone would be account identifiers in a public place; they come from the environment instead —
`.env.example` names them, `.env` is git-ignored. The infrastructure that receives the upload lives
in a separate private repository as an OpenTofu module, whose `just deploy-env` prints every value.

**So `command make deploy` is the target that publishes and not the command anyone types.** It needs
seven settings and has a default for none of them. The infrastructure repository holds them and
drives the deploy: its own `just deploy` reads them out of state, unlocks the credentials and calls
this target. Publishing is therefore **`command make map` here, then `just deploy` there** — two
steps, in that order, because this one does not build.

A map named `<name>` is uploaded as `<name>.html` and is then readable at `https://<host>/<name>`.
Publishing a second map needs nothing but a second upload.

**Tile trees** are the other thing it uploads — the base-map tiles `command make tiles` copied and
the height tiles `command make dem` built — and they go up by `aws s3 sync` rather than one `cp`
each:

```bash
command make deploy ARGS="--tree tiles"              # analysis/output/tiles/ → s3://…/tiles/
command make deploy ARGS="--tree tiles --dry-run"    # lists the bucket, says what is missing there
command make deploy ARGS="--map abisko --tree dem"   # a page and a tree in one run
```

A tree is a hundred thousand small PNGs under a versioned prefix (`tiles/lantmateriet/topowebb/1/…`;
`make tiles` opens the next number when Lantmäteriet's file changes, `make map` draws the
newest complete one, and a phone that kept the old stand goes on drawing it offline until Keep
replaces the tiles; `ARGS="--drop-tree tiles/lantmateriet/topowebb/1"` deletes an old version
from the bucket and refuses the current one),
so every object is immutable and is sent with a year's `max-age`; `sync` compares size and
modification time against the bucket's listing and uploads only what is new, deletes nothing and
purges nothing. With `--tree` alone no page goes up; name `--map` too for both. The tree's
`index.json` — the copy's inventory, the one file in it that changes — goes up on its own with a
short lifetime.


## Structure

```
analysis/
├── notebooks/          # Jupyter notebooks
├── scripts/            # Analysis scripts
├── docs/               # How the route planning was decided, phased and reviewed
└── README.md           # This file
```

**Note**: Cached data is stored in the repository root `.cache/` directory, shared across all components.

## Note

This is an exploratory workspace. Code here can be messy and experimental. Production code belongs in `libs/src/trails/`.

## Exporting to Production

When analysis code is mature and reusable:
1. Move it to `libs/src/trails/`
2. Add tests in `libs/tests/`
3. Import in notebooks: `from trails.analysis import your_function`
