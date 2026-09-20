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
- `docs/malingsbo-kloten-decisions.md` — the third map, Malingsbo-Kloten in Bergslagen:
  the box, the sources, the decisions and the build's figures
- `docs/garmin-decisions.md` — getting a planned track, and possibly a map, onto a
  Garmin fēnix 7 without an internet connection: what works today, why the phone
  route is shut, what Coros and the other watches do instead, and the eleven-gram
  computer that would close the gap. Unlike the others, **nothing in it has been
  measured on a device** — it says so at the top and lists what must be checked first

### Scripts

**The map** — builds `analysis/output/lomsdal-visten.html` from seven sources,
or `abisko.html` and `malingsbo-kloten.html` from five each, plus one GPX per source beside it. Every line it
draws is a chain out of the routing graph below, so a drawn line and a
selectable track are the same object; the two scripts share one cached build:

```bash
command make map
command make map ARGS="--park abisko"
command make map ARGS="--park malingsbo-kloten"
```

Everything it downloads is cached, so a second run does not fetch again and takes
about a minute. The first run on an empty cache fetches some 150 MB from Geonorge
and Overpass and takes considerably longer. Re-fetch on purpose with
`--force-download`; `command make cache-clean` throws the cache away entirely,
which is rarely what you want.

**The ground under a map** is five more targets, and **all three maps have all five**.
`command make dem` builds z8–z13 height tiles from the country's height model,
`command make shade` cuts the relief shadow the page lays under the contours out of the
same cached model, z8–z15, `command make slope` colours how steep that ground is,
in classes, cut exactly as the relief is, `command make vegetation` colours what
stands on it off the country's laser survey — the cover of bushes and low trees in six
steps, the ground the laser has not flown in grey, and the forest over 5 m as a tree of its
own — and `command make mire` colours where the ground is bog and marsh: the sheet's
wetlands, wet or firm, and over Sweden the wet ground a soil-moisture model finds beyond
them. All five take `PARK=<map>` — default
`lomsdal-visten`, as `make map` and `make graph` default — and which box each is cut to
and out of which model is `trails.processing.trees.TREES`, written once and read by the
scripts and by `maps.PROVIDERS` alike. All five resume, all write under
`analysis/output/<tree>/<provider>/<version>/`, and `command make packs` packs what they
wrote. `analysis/docs/abisko-decisions.md` carries Abisko's and Lomsdal-Visten's figures — §6.3, §6.6,
§6.7, §6.11 and §6.13 for the shapes, §6.10 for the Norwegian model and its box;
`analysis/docs/malingsbo-kloten-decisions.md` §10 carries the third map's. The Swedish
vegetation comes off Naturvårdsverket's nationwide NMD 2018 rasters, fetched and converted
once into the cache by `command make nmd` (7.2 GB down, no login); the Norwegian off
`hoydedata.no`'s surface model, no login either. The Swedish mire needs two logins on a cold
cache — Geotorget's for Lantmäteriet's Marktäcke, once the product is ordered there, and the
one Skogsstyrelsen publishes on its download page for the 8.4 GB soil-moisture mosaic, in
`SKOGSSTYRELSEN_FTP_USERNAME` and `SKOGSSTYRELSEN_FTP_PASSWORD`; both live in
`home/trails-map`'s `secrets.sops.env`, so a cold `make mire PARK=abisko` runs from there as
`sops exec-env secrets.sops.env 'cd ../../trails && command make mire PARK=abisko'` — and the
Norwegian none, off N50's bogs.

**All three maps copy their sheet, and the Swedish height models need a login.** `command make tiles PARK=abisko`
copies Lantmäteriet's tiles for the box out of its open download over FTP (no login), and its
height model does need the Geotorget login, so run that from `home/trails-map` as
`sops exec-env secrets.sops.env 'cd ../../trails && command make dem PARK=abisko'`.
For Malingsbo-Kloten both commands take `PARK=malingsbo-kloten`; its sheet and height tiles
stand under `lantmateriet-malingsbo-kloten/`, apart from Abisko's `lantmateriet/`.
`command make tiles PARK=lomsdal-visten` renders Kartverket's sheet for the box off the WMS,
without its hillshade (§6.12), and Lomsdal-Visten's height model comes off `hoydedata.no` with
no login, no order and no key at all. Every page draws its trees from packs:
`command make packs PARK=…` writes every tree of a map as packs of 85 tiles — PMTiles
archives under `analysis/output/packs/` — and `just deploy --tree packs` uploads those.

**Or the whole chain at once**: `command make abisko` runs tiles, dem, shade, slope, vegetation, mire, the graph
with its report and the page, in that order, and from `home/trails-map`
`just abisko` is the same with the login supplied. `command make lomsdal-visten` is the same
chain without any credential. `command make malingsbo-kloten` runs the Swedish chain for
the third map; with a cold cache, run it from `home/trails-map` as
`sops exec-env secrets.sops.env 'cd ../../trails && command make malingsbo-kloten'`.
Every step resumes or reads the cache, so a rerun costs a few minutes of checking and the
page; all three build and none publishes.

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
`build_sweden`; the page itself is assembled by one function for all three.

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
`--park` too, and reports each map's graph against its own landmarks: Abisko for that map,
Kopparberg for Malingsbo-Kloten.

**Sweden has its own module**, `trails.network.sweden`, built on the same shared
core (`trails.network.graphs`: parameters, fingerprint, derived fields, the build)
from three registers instead of seven: Lantmäteriet's *Topografi 50* delivery
(`io/sources/topografi50.py`, fetched through the Geotorget download API with the
login, read by box out of the country GeoPackage), Naturvårdsverket's nightly
files — the protected areas and the trail register, `io/sources/naturvardsregistret.py`,
no login — and OSM. Heights come off the cached 1 m model rather than a point
service; the place names are Lantmäteriet's *Ortnamn* (`io/sources/ortnamn.py`, the
country file fetched once with the login).

**All three pages read their heights off tiles, and all draw the relief and the slope classes.**
The page reads the model off the height tiles `make dem` cut (`maps.HeightTiles`, beside the
provider's map tiles; the worker keeps them and the offline panel counts them), so a leg
planned with no network still has a profile and a tap anywhere is told its own height.
Sweden's model is Lantmäteriet's 1 m *Markhöjdmodell* (`io/sources/markhojd.py`, Geotorget
login); Norway's is Kartverket's national model off `hoydedata.no`'s image service
(`io/sources/hoydedata_dtm.py`, no login), where what the model leaves empty is open sea and
is read as nought metres. **The relief is shaded from that same model**
(`maps.ShadeTiles`, `processing/shade_tiles.py`): neither Lantmäteriet's sheet nor
Kartverket's carries shading, so the page draws its own over the base and under
everything it draws itself, black with an alpha channel so level ground stays the
sheet's own colour. It is a checkbox under the sheet in the base-map panel and starts on.
**And the slope is classed over it** (`maps.SlopeTiles`, `processing/slope_tiles.py`): how
steep the ground is down its fall line, in the SLF's avalanche classes with one of our
own at 25° below them and one over 55° above, one light colour each, multiplied over the
sheet so its lettering stays black; a second checkbox under the relief's, off until asked,
with the class colours listed under it while it is on. **And what stands on the ground is
coloured over both** (`maps.VegetationTiles`, `maps.ForestTiles`,
`processing/vegetation_tiles.py`): the laser's reading of the cover of what is between 0.5
and 5 m — willow, dwarf birch, young mountain birch — in six blue-green steps with a grey for
the ground nobody has flown, and the forest over 5 m apart in sepia, two more checkboxes under
the slope's, both off until asked. Sweden's
classes are NMD 2018's (`io/sources/nmd.py`); Norway's are computed to the same codes from
Kartverket's surface model less its terrain model (`io/sources/hoydedata_vegetation.py`).
**And where the ground is mire** (`maps.MireTiles`, `processing/mire_tiles.py`, §6.13): the
sheet's wetlands, wet or firm, and over Sweden the ground a soil-moisture model calls wet
beyond them, in three violet steps under one more checkbox — Lantmäteriet's Marktäcke and
SLU's moisture mosaic for Sweden (`io/sources/mire_sweden.py`), N50's bogs for Norway
(`io/sources/mire_norway.py`), where the sheet draws one kind of bog and one row is shown.
A state trail's popup links to the county's page
for it on Naturkartan, one link per *BD* number on the chain, out of a hand-kept
catalogue (`analysis/routes/abisko-naturkartan.toml`, `io/sources/naturkartan.py`):
links only, since Naturkartan's terms allow private use alone and the line itself
is the register's. `analysis/docs/abisko-decisions.md` is the record.

### What the map does once it is open

The legend at the bottom left **is** the layer control: every row switches its own
layer and a row whose layer is off is greyed rather than hidden, so it is still
the key to that colour. It says what the map holds, whoever switched it — a search
result in a layer that was off switches that layer on, and the row ticks itself. The base maps sit above the rows.

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

**Search for a name, or type a position.** The box at the top left lists what it
finds — one row per thing, nearest first, saying which layer each came from and,
where a named way is drawn in several lines, how many. Tap a row and the map goes
to it and it is selected, exactly as if you had tapped it on the ground; nothing
else is hidden while you search, so the answer keeps the map around it. On a phone
the panel steps aside when you take a row, since it is standing on the ground the
row points at. A pair of
coordinates is a name here too: `68.39275, 18.68033` — the form the *Copy a
position* tool writes to the clipboard — or `68°23'34"N 18°40'49"E` is read as
the place it names, marked on the map, and can be set as a goal like any hut.

**A tap says how high it is**, beside the position it copies. The Abisko and Malingsbo-Kloten pages read the tapped
place itself off the height model under it, which covers each whole box, so a spot on an open flank
has its own figure; Lomsdal-Visten carries heights along the paths alone, so a tap near one reads
the nearest sample, marked `~` where that sample is more than 25 m off, and a tap far from any path
says nothing rather than a number about somewhere else. Only the position goes to the clipboard —
the height stands beside it on the screen.

**What a place offers, it offers from its page.** Tap a hut, a quay or a position you typed, and
under what it says about itself are the things that can be done with it as the map stands: *Set as
goal* always, *Add a stop on the way* while a goal stands, *Add to the plan* while a plan stands —
switch plan mode off to look places up, since with it on every tap is a waypoint, and the press
leaves the mode off so the next place can be picked too. That is how coordinates become waypoints
and stops — the search reads them, the place's page does the rest. And a tap lands on the line
wherever it lands on it — the middle of a long stretch of trail as much as a junction — and the
route runs along the line from there; a tap beside the line walks to it. And a goal you have set, with its stops, becomes a route to edit with *Make a
plan of this way*, on the goal's own page and on the page the flag opens: the places become the
plan's points in order, your own position in front of them if the page knows it.

**Plan a route** with the button at the top right. Every click on the map places
a waypoint and the way between is worked out over the network; click the route
itself to put a point in the middle, drag a pin to move it. Click the point count
to unfold the list: one row a point, with what it is called and how far into the
walk it comes, draggable to reorder and with its own button to take one out. The
route's own profile is drawn in the same panel and marks each of your points on
it, and *Download GPX* writes it with its waypoints, its legs and the protected
areas it enters and leaves. *For Garmin (course)* adds a GPX course for Garmin
Explore, with at most 200 points, their heights and the same source credits.
It is offered for the whole tour and each stage, and in the profile panel;
its filename ends in `-garmin.gpx`. Keep the ordinary GPX to load the plan back:
the Garmin course carries no waypoints or leg provenance. The measurement and
format decision are in [garmin-decisions §3](docs/garmin-decisions.md#3-the-course-offline--garmin-explore).

**A tour can be walked in stages.** Mark a point in the list as the end of one and
the route falls into stages, each with a heading carrying its own kilometres, its
climb, a name you can give it and a download icon, all on one line. The icon opens
a menu with *This stage (GPX)* followed by *For Garmin (course)*. A point where one stage hands over
to the next carries a second ring, on the map and on the profile. *All stages (zip)* writes every
stage and the whole tour with its marks, plus their Garmin courses, in one archive.
It comes first in both the plan and profile download menus, followed by *Whole tour (GPX)*
and *For Garmin (course)*; with only one stage, the archive entry is hidden.
Name the tour in the box above the list; the marks travel in the file, so loading it back gives you the
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
command make drive ARGS="--page analysis/output/malingsbo-kloten.html"
command make drive-all                                      # every built page with a scene
```

Drives the built map in a browser and reports **some 700 readings** (689 on the
Lomsdal-Visten page, 720 on Abisko's, 2026-09-17) — the counts the
page draws, the profile's scale at several zooms, the wheel, the crosshair's
mark, the point list, plan mode and the file it writes, the chrome on a phone,
which zoom the scale bar says it is on, what the panel remembers over a reload,
that the map opens with the network off,
and that terrain the reader asked for is kept and drawn and can be deleted again.
**About eight minutes a page** — 17.1 MB of HTML for Lomsdal-Visten and 3.6 for
Abisko, loaded twice over for the offline check — and about two minutes of it
fetching real tiles from Kartverket on the first page, which is what it costs to
prove that a kept tile is terrain and not the worker's own blank. Run it as a
transient unit (`systemd-run --user --unit=abisko-drive …`); its output is
buffered until the unit ends, and the pages are worth driving side by side in
separate units rather than one after the other. `command make drive-all` does that for every
built page whose scene is recorded and keeps a log per page. Malingsbo-Kloten's first build
is 23.3 MB (2026-09-20); its drive readings are recorded in phase 5.

**Drive it once, into a file, and grep the file.** Running it twice to see two
parts of one report costs two runs. And **build before driving**: the run reads
the page `command make map` last built.

**Drive what the change touched, and the whole suite once before publishing.**
`ARGS="--only the_relief_under_the_map,what_the_panel_remembers"` takes the words
a check's own name holds and runs those — seven checks and two minutes against
sixty and eight. The checks it leaves out are not reported at all: a skip means
*this could not be driven*, and "you did not ask for it" is a different sentence.

**The report says where the minutes went**, per check and dearest first. Measured
2026-09-17: half of a run is six checks, and what is left in them is work rather
than waiting — the dearest sits out a 31-second cap because sitting it out is the
rule being driven.

**The checks are the same for every page; what is a page's own is its `Scene`** in
`drive_map.py`, chosen by the page's stem: the long chain the profile checks select, the
ground the position and offline checks stand on and look at, the request pattern its heights
come by, and the figures its last build recorded. A page whose sheets are addressed from the
root — Abisko's and Malingsbo-Kloten's — is served from its directory rather than opened off the disk. A reading whose
figure the scene has not recorded yet is reported as **new**, with what was read, so the first
drive of a page is the run that fills its scene in. A check that needs ground a scene does not
have is named in the scene's `skips` and reported as skipped by it (the Lomsdal-Visten and Abisko scenes have all their
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
`abisko-sw.js` or `malingsbo-kloten-sw.js` for the Swedish maps; uncompressed, `no-cache`, so an edge holding yesterday's
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

For Malingsbo-Kloten, build and review `command make map ARGS="--park malingsbo-kloten"`
here, then run `just deploy --map malingsbo-kloten --tree packs` from `home/trails-map`.
Add `--tree dem` if the page reads heights per tile. Abisko takes `--park abisko` and
`--map abisko`; Lomsdal-Visten is the default for both commands.

A map named `<name>` is uploaded as `<name>.html` and is then readable at `https://<host>/<name>`.
The pages are `/lomsdal-visten`, `/abisko` and `/malingsbo-kloten`; publishing another map
needs nothing but another upload.

**Tile trees** are the other thing it uploads — the base-map tiles `command make tiles` copied,
the height tiles `command make dem` built, the relief `command make shade` cut, the slope
classes `command make slope` coloured, the vegetation and forest `command make vegetation`
coloured and the mire `command make mire` coloured — and they go up
by `aws s3 sync` rather than one `cp` each:

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
