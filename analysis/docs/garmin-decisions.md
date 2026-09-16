# Garmin: getting a track and a map onto the fēnix 7

Started 2026-09-16, out of one conversation. Uwe plans routes in the generated map and exports
them as GPX; he wants them on a **Garmin fēnix 7** *without an internet connection*. Outdooractive
is the route he uses today and it needs the network.

**Nothing in this document has been measured on a device.** That is the difference between it and
`abisko-decisions.md` beside it, and it is the first thing to know before acting on any figure
here. Everything about the watch was read on 2026-09-16 off a vendor page, an owner's manual or a
Garmin forum thread; §9 lists what has to be checked against the actual fēnix 7 before it is built
on. Where a claim comes from this repository instead, it names the file, and those are measured.

---

## 1. The decision in one paragraph

**The track is already solved and needs no code. The map is a project, and only the small half of
it is worth doing.** A GPX reaches the fēnix 7 offline through **Garmin Explore** over Bluetooth,
and the map's existing share sheet already feeds it: `saveFile` in
`libs/src/trails/visualization/maps.py:5997` hands a named `File` to `navigator.share`, and Explore
is one of the targets the sheet offers. Nothing in `trails` changes for that. Separately, this
project carries paths no Garmin map has — FKB's `traktorveg_sti`, N50's, and the chains the router
builds from them — and those could be compiled into a **transparent Garmin overlay map** published
beside the tiles in the R2 bucket. A full topographic basemap from N50 and Topografi 50 could
follow it and probably should not: it is the same toolchain with twenty times the styling, to
replace something that already sits on the watch for nothing.

---

## 2. What was asked for

Stated by Uwe, 2026-09-16, in order:

1. Send a planned track to the fēnix 7 **without internet**.
2. If the map app already integrates several sources, **build Garmin maps from them too and serve
   them over R2**.
3. An **overlay of the paths** as a variant, perhaps both.
4. Not pay yearly for something that can be built.
5. Get the `.img` onto the watch **without a laptop**.

Point 1 is answered in §3 and costs nothing. Point 5 is answered **no** in §5, and that answer is
what shapes the rest. Points 2, 3 and 4 become §6 and §7.

---

## 3. The track, offline — Garmin Explore, and no code here

**Garmin Connect will not do this.** It creates a course in the cloud first, so it needs the
network. **Garmin Explore does**, and its App Store description is explicit that it works "with or
without Wi-Fi connectivity or cellular service"; only the sync back to the web account waits for a
connection.

The procedure, from the fēnix 7 forum thread in §10:

| when | what |
|---|---|
| at home, once | install Explore, sign in, pair the watch, let the first Bluetooth sync finish |
| in the field | Bluetooth on, open the GPX, choose Explore, tap the watch icon, sync |

Two warnings from the replies in that thread, both from users rather than from Garmin: create a
**collection** first, or courses already on the device may be lost; and the first sync took one
reporter **about 30 minutes**, so it is not a thing to start at the trailhead.

**Nothing in `trails` has to change for this.** The export already names the file on the `File`
rather than on the anchor, already prefers the share sheet under a coarse pointer, and already
falls back to a download — `saveFile`, `shareable` and `anchorFile` at
`maps.py:5997`, `:6023` and `:6030`. The reason that code exists is in
`route-planning-decisions.md`; it was written for iOS Safari naming a `blob:` download after its
own identifier, and Explore is the second thing it turns out to buy.

**Open, and cheap to settle:** whether Explore appears in the sheet at all on this iPhone, and
whether it makes one course or several out of an export whose `<trkseg>` breaks at a crossing
(`route-planning-decisions.md`, "In the GPX, a crossing ends a `<trkseg>`"). If it splits badly,
the fix is a second export variant — one unbroken track, no waypoints — which is a few lines beside
the existing writer. **Do not write that variant before measuring.** It may not be needed.

---

## 4. What the fēnix 7 does with maps — read, not measured

| claim | source | consequence here |
|---|---|---|
| third-party `.img` maps still install, same method as fēnix 5 and 6 | fēnix 7 forum | a self-built map is possible at all |
| several maps stack, each toggled on its own in map settings | fēnix 8 forum, fēnix 7 manual | an overlay can sit on TopoActive and be switched off |
| transparent overlays are a normal mkgmap technique | fēnix 7 forum | §7.1 is not exotic |
| the file is `gmapsupp.img` under a `Garmin` folder, capital G | OSM wiki | trivial, but the capital matters |
| Sapphire models carry 32 GB | Talkytoaster | size is not a constraint for one region |
| raster Custom Maps (KMZ) work, but around **3 MB** and only at deep zoom | fēnix 7 forum, one reporter | rules the raster route out for a region |
| TopoActive Europe is preloaded, covering Norway and Sweden | Garmin | the free basemap already exists, which is §7.2 |

The 3 MB figure has **one source and one reporter**. It is enough to stop the raster idea, because
a raster overlay of this project's box would be orders of magnitude over any plausible limit, but
it is not a number to quote elsewhere.

---

## 5. Why the `.img` needs a computer, and the false lead to ignore

**Answer: there is no way to do it from a phone.** The cause is single and it is not going to
move: the fēnix 7 presents itself over USB **only as an MTP device**. A forum reply puts the
history plainly — *"the last Fenix that worked as a USB mass storage was the Fenix 5."*

| route | works |
|---|---|
| iPhone, Files app | no — iOS has no MTP in Files |
| iPad over USB-C | no — same reason |
| Android as USB host over OTG | no — reported on a Galaxy Tab: *"it didn't recognize the storage on my f7x"* |
| any computer with an MTP client | yes |

**A false lead to know about before searching.** A summary circulating online describes an Android
app called *"Garmin Map Transfer"* that does exactly this, in convincing detail. It was checked on
2026-09-16: **it is not in the Play Store.** The description traces back to a low-quality GitHub
repository. Do not build a plan on it.

**This is neutral between the options, not an argument against building our own.** Kartmannen needs
the same cable and the same computer. The step happens once, before a trip, whichever map is
installed. On Linux it is unremarkable — gvfs or jmtpfs mount the watch — so the build stays here
on `forge` and only the last thirty centimetres of cable need a machine standing beside the watch.

---

## 6. Licences: what may be redistributed

The question only arises because of point 2 — publishing a built map in the bucket. Read out of
the source modules on 2026-09-16, which is where this project already records provenance:

| source | licence | module | may we republish a derived map |
|---|---|---|---|
| Topografi 50, vector | CC0 1.0 | `io/sources/topografi50.py:156` | yes, unconditionally |
| Naturvårdsverket, *Leder* | CC0 1.0 | `io/sources/naturvardsregistret.py:108` | yes, unconditionally |
| N50 Kartdata | CC BY 4.0 | `io/sources/n50.py:108` | yes, with attribution |
| `traktorveg_sti` (FKB-derived) | CC BY 4.0 | `io/sources/traktorvegsti.py:44` | yes, with attribution |
| Geonorge (generic) | CC BY 4.0 | `io/sources/geonorge.py:41` | yes, with attribution |
| Stedsnavn | CC BY 4.0 | `io/sources/stedsnavn.py:105` | yes, with attribution |
| Ortnamn | CC BY 4.0 | `io/sources/ortnamn.py:124` | yes, with attribution |
| Naturbase | NLOD | `io/sources/naturbase.py:122` | yes, with attribution |
| OpenStreetMap | ODbL 1.0 | `io/sources/overpass.py:68` | yes, share-alike |
| **UT.no** | **CC BY-NC 4.0** | `io/sources/ut.py:53` | **no** |
| **Naturkartan** | **links only** | `io/sources/naturkartan.py:38` | **no** |
| Lantmäteriet tiles | *värdefulla datamängder* terms | `io/sources/lantmateriet.py:149` | not needed — a vector map uses none |

**Both exclusions are already in force**, which is the point worth keeping: UT.no was taken out of
the published graph at `atlas` §3.6, and `abisko-decisions.md` records the resulting rule in one
line — *"Nothing NC."* A Garmin map built from the published graph inherits that and needs no new
review. Sweden is the cleaner of the two countries: its two load-bearing sources are CC0 outright.

**This is an argument in favour of building rather than buying**, and it is not a small one. A map
we compile may be given away. A Kartmannen licence never may.

---

## 7. Decided

### 7.1 The overlay first, and it is the small half

Build a **transparent overlay `.img`** holding only this project's own path network: `traktorveg_sti`,
N50's paths, and the router's chains. That is exactly what no bought or free Garmin map carries,
and it is the whole of the unique value.

It is small for a reason that is structural, not lucky: an overlay is **lines only**. No land cover,
no contours, no lettering rules, no zoom-dependent generalisation of areas. A handful of TYP codes
decides how a line looks, and the result can be judged on the wrist in one sitting.

**It is also the cheap way to learn the toolchain.** The basemap in §7.2 is the same chain with
twenty times the rules. Doing the small one first means the chain is proven before the expensive
decision is taken, and if the chain turns out to be unpleasant, very little has been spent.

### 7.2 No self-built basemap yet, and possibly never

A full topographic map from N50 and Topografi 50 is buildable and is **not scheduled**. Three
reasons, in order of weight:

- **It is a second cartography for one dataset.** The web map's appearance lives in `maps.py` and is
  Leaflet's. A Garmin map's appearance is a mkgmap style file plus a TYP file, interpreted by the
  watch's firmware. Nothing transfers between them, and only one of the two can be looked at on this
  box. The other is judged at arm's length, literally.
- **The free basemap is already installed.** TopoActive Europe covers Norway and Sweden and is on
  the watch. It is coarser than N50. It costs nothing and it is there while the overlay is being
  built.
- **It is sold.** §7.4.

Revisit this only if the overlay proves the chain *and* TopoActive turns out to be genuinely
inadequate underneath it. Both halves of that condition matter.

### 7.3 Not Outdoor Maps+

Garmin's subscription is **59,99 € a year** in Europe and it is the only genuinely recurring cost
in this whole area. It buys TOPO Pro — Norway, Sweden and Finland are covered; the British Isles,
the Netherlands, Belgium, Luxembourg and Portugal are not — plus satellite imagery, relief shading
and building footprints.

**Rejected**, and the reason is not only the price. Its content is downloaded to the watch over
Wi-Fi, so it is prepared at home like everything else here, and what it adds over TopoActive is
denser contours and nicer shading — not the paths this project exists for. One forum reader also
reports the download granularity is whole regions, so a small area pulls its neighbours with it.

### 7.4 Kartmannen is the fallback, not the plan

Kartmannen sells Garmin maps built from the same official data, and the fēnix 7 is named in its
device list.

| product | price | note |
|---|---|---|
| N50 Norge | from 449 kr | one-off; *"Kjøp en gang, bruk evig"* |
| Sverige | 599 NOK | |
| updates | 99 kr a year | **optional**, not a subscription |
| one municipality | free | too little for Lomsdal-Visten: the cache holds **eight** N50 kommune archives, 1811 to 1825 |

**The "yearly payment" objection does not apply to this one** and it should not be argued as if it
did; the recurring 60 € is Outdoor Maps+ in §7.3. What does apply is that Kartmannen has no FKB
paths, no chains, and a licence that forbids passing the result on.

Buy it if a good basemap is wanted before the overlay is finished. It is a purchase, not a
commitment, and it does not compete with §7.1.

### 7.5 R2 carries it, but be honest about what it reaches

The channel exists and needs no design: `home/trails-map` already provisions an R2 bucket, a custom
domain and a cache ruleset, and `just deploy` ships whole trees — `--tree tiles`, `--tree dem`. An
`--tree garmin` is one more of the same. The precedent for shipping sidecar files out of a map build
is also already set: the build writes six GPX files today.

**Write down what it does not do.** R2 delivers the `.img` to a computer, because §5 leaves no other
possibility. For a workflow driven from a phone that is a real asymmetry, and it should be stated on
the download page rather than discovered.

---

## 8. The order of work

Not a schedule. The order the pieces depend on each other.

1. **Measure §9 first.** Especially the Explore questions, which are free and which may remove work
   from §3.
2. **The bridge.** `ogr2osm` converts an OGR-readable source to OSM XML, which is the only thing
   mkgmap reads. It takes a Python translation file mapping source attributes to OSM tags. Half of
   this exists already: `io/sources/geonorge_codes.py` and `geonorge_translations.py` have the N50
   schema decoded.
3. **The compile.** `mkgmap` is a Java jar, so the toolchain grows a JDK. Note where that goes:
   `mise.toml` in this repo declares exactly one tool today, the AWS CLI, and the comment there
   explains that it is declared because nothing else claimed it. A JDK is the same case. `ogr2osm`
   is a Python package and belongs behind `uv run --with`, per the repo's rule.
4. **The TYP file.** How each line class is drawn. This is the part that can only be judged on the
   watch.
5. **Install and look at it.** MTP from a Linux machine standing next to the watch.
6. **Only then**: a `--tree garmin` in the deploy, and a download page saying what §7.5 says.

Steps 2 to 5 are one pipeline stage. It does not belong bolted onto `make map` — `make map` builds a
document, and this builds a device artifact from the same graph.

---

## 9. Open — and all of it needs the actual watch

Nothing below can be settled from here. Grouped by what it would change.

**Free, and settles §3:**

- Does Garmin Explore appear in the iOS share sheet for an `application/gpx+xml` file exported by
  the map? If not, saving to Files and importing from inside Explore is the fallback, still offline.
- Does Explore make **one** course or several from an export whose track breaks at a crossing?
- Do the export's waypoints survive the import, and do they reach the watch?
- Does the first Explore sync really take ~30 minutes, and does the collection warning hold?

**Needed before §7.1 is worth starting:**

- Does a transparent overlay actually render over TopoActive on this fēnix 7, and can both be toggled
  independently in map settings?
- How many line classes can be told apart at a glance on a 1.3 inch screen? This caps how much of the
  chain structure is worth encoding.
- What does the watch do with a dense line at low zoom — does it drop it, or draw it as mush?

**Needed before any install:**

- Which machine is doing the MTP step, and does it mount the watch. Untested on any machine here.

---

## 10. How the figures here were obtained

Everything in §4, §5 and §7.3–7.4 was read on **2026-09-16** from:

- Garmin Forums, fēnix 7: *How to upload a .gpx router or course … offline*
- Garmin Forums, fēnix 7: *Can you still load OSM maps?*
- Garmin Forums, fēnix 7: *Fenix 7 USB-OTG compatibility*
- Garmin Forums, fēnix 7: *Has anyone been able to get a Custom KMZ Map to work*
- Garmin Forums, fēnix 7: *using mkgmap to change zoom level details*
- Garmin Forums, fēnix 8: *How to use 3rd party maps and Custom Maps?*
- Garmin Forums, epix 2: *USB Drive Mode is needed! MTP is not supported on Mac*
- fēnix 7 owner's manual: *Garmin Explore*, *Managing Maps*, *Showing and Hiding Map Data*
- Garmin Explore on the App Store; Garmin newsroom on Outdoor Maps+ in Europe
- the5krunner and GPS Radler on Outdoor Maps+ pricing; GPSrChive on its European coverage
- kartmannen.no, Norwegian and Swedish product pages
- mkgmap.org.uk; `roelderickx/ogr2osm` on GitHub; OpenStreetMap wiki, *OSM Map On Garmin*
- Talkytoaster, fēnix 7 review, for the storage figure

Everything in §6 and the file references in §1 and §3 were read out of this repository on the same
day and are measured, not reported.

---

## 11. Changes

- **2026-09-16** — written. No code changed and none is proposed yet; §9 has to come first.
