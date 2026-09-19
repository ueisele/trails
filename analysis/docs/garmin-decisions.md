# Garmin: getting a track and a map onto the fēnix 7

Started 2026-09-16, out of one conversation. Uwe plans routes in the generated map and exports
them as GPX; he wants them on a **Garmin fēnix 7** *without an internet connection*. Outdooractive
is the route he uses today and it needs the network.

**Nothing in this document has been measured on a device.** That is the difference between it and
`abisko-decisions.md` beside it, and it is the first thing to know before acting on any figure
here. Everything about the watch was read on 2026-09-16 off a vendor page, an owner's manual or a
Garmin forum thread; §12 lists what has to be checked against the actual fēnix 7 before it is built
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
replace something that already sits on the watch for nothing. The one hard limit is that an `.img`
needs a computer standing beside the watch (§5) — and §10.6 is the answer to that, which weighs
eleven grams.

---

## 2. What was asked for

Stated by Uwe, 2026-09-16, in the order it came up:

1. Send a planned track to the fēnix 7 **without internet**.
2. If the map app already integrates several sources, **build Garmin maps from them too and serve
   them over R2**.
3. An **overlay of the paths** as a variant, perhaps both.
4. Not pay yearly for something that can be built.
5. Get the `.img` onto the watch **without a laptop**.
6. *Why* was the phone route closed, when it is clearly a useful feature.
7. Would a **Coros APEX 4** do better, and can maps be generated for it.
8. Is there a watch with a **more open map ecosystem**.
9. Could **custom firmware** open the phone route.

Point 1 is answered in §3 and costs nothing. Point 5 is answered **no** in §5, and that answer is
what shapes the rest. Point 6 is §6, points 7 and 8 are §8, point 9 is §7. Points 2, 3 and 4 become
§9 and §10.

---

## 3. The track, offline — Garmin Explore, and no code here

**Garmin Connect will not do this.** It creates a course in the cloud first, so it needs the
network. **Garmin Explore does**, and its App Store description is explicit that it works "with or
without Wi-Fi connectivity or cellular service"; only the sync back to the web account waits for a
connection.

The procedure, from the fēnix 7 forum thread in §13:

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

**Measured 2026-09-19, and the variant is needed after all — but not the one guessed above.**
The share sheet works and an export imports into Explore in one piece: the `<trkseg>` breaks were
never the problem (the Abisko–Björkliden route has one segment and 4,920 points). The problem is
the *kind* of thing Explore makes of it. Garmin's support page "Importing GPX Files in the Garmin
Explore App" (read 2026-09-19, rendered in a browser because the page is client-side) is explicit:

| in the GPX | in Explore | reaches the watch |
|---|---|---|
| `<trk>` | a **Track**, condensed to 20,000 points | only after a manual *Copy as Course* |
| `<rte>` | a **Course**, condensed to 200 points | yes, on sync |

So `trails`'s export, which writes `<trk>`, lands as a Track and needs one extra tap per route on
the phone. The same test file, rewritten by hand as a `<rte>`, was imported twice on the iPhone
(Uwe, 2026-09-19): **both came in as a Course and synced to the fēnix 7 without the extra step.**
The two files differed in one thing, and it decides who does the condensing:

| file | `<rtept>` written | points Explore kept | max. deviation from the full line |
|---|---|---|---|
| A | 200, Douglas-Peucker in UTM 34N at 3.5 m | **200** | 3.5 m |
| B | all 4,920 | **122** | not measured; Explore's own choice |

Explore's own condensing keeps fewer points than the cap allows, so the line is better when the
export cuts it to 200 itself. Decided: **variant A is the shape of the Garmin export.**

**What the Garmin variant is**, the whole of it, so it can be built without re-deriving anything:

- One `<rte>` in place of the `<trk>`, carrying the same `<name>` and `<desc>`. No `<trkseg>` at
  all, so a crossing does not break it — a course is one line by definition.
- At most **200** `<rtept>`, chosen by Douglas-Peucker on projected metres with the tolerance
  searched down until the count fits; every kept point is an original vertex and keeps its `<ele>`.
  Measured on the route above and on eleven ut.no tracks of 8–18 km: the tolerance that fits lands
  between 2.5 and 9.3 m. Under 10 m is nothing on a walk; **it is not nothing on a phone screen
  at z14 for a switchback**, which is why the cap belongs to this variant and not to the ordinary
  export.
- **No `<wpt>` at all.** A `<wpt>` is a top-level element with no tie to the route, so Explore
  imports each as a Waypoint of its own and syncs it to the watch as a saved location. In the
  ordinary export the set points are the plan — what the map re-routes through on loading the
  file back — and the generated ones are the park boundaries; the watch re-routes nothing, start
  and end are the course's own ends, and a pass worth marking would be a Garmin course point,
  which GPX cannot carry. Left in, "Point 1, 2, 3" would pile up on the wrist as nameless
  locations, one set per route. Uwe asked whether they are needed, 2026-09-19; they are not.
- None of the `trails:` extensions. The Garmin file is for a watch, not for loading back into the
  map; the ordinary export is the one that carries provenance and can be re-read.
- The watch shows the first **15 characters** of a course name (Garmin, "Importing a Third-Party
  Course into Garmin Connect"), so *Abisko to Björkliden via pass* is *Abisko to Björk* on the
  wrist. A name is the reader's; the file does not shorten it.

Where it goes: a second button beside the route export in `profile_panel.js` (`saveNow`, the
`routeGpxOf` writer), sharing `metadataOf`, `waypoint` and `saveFile`. Nothing in the Python
writer, which never exports a planned route. **Not built yet** — recorded here on 2026-09-19 so
the build is a build and not a re-measurement.

One figure to know from the same test: Explore's list header showed **9.2 km** for the imported
track while its own statistics said 12.9 km and the file holds 12.87 km in one segment. The
straight line from start to end is 9.31 km. It is Explore's display, not the file, and it was not
chased further.

---

## 4. What the fēnix 7 does with maps — read, not measured

| claim | source | consequence here |
|---|---|---|
| third-party `.img` maps still install, same method as fēnix 5 and 6 | fēnix 7 forum | a self-built map is possible at all |
| several maps stack, each toggled on its own in map settings | fēnix 8 forum, fēnix 7 manual | an overlay can sit on TopoActive and be switched off |
| transparent overlays are a normal mkgmap technique | fēnix 7 forum | §10.1 is not exotic |
| the file is `gmapsupp.img` under a `Garmin` folder, capital G | OSM wiki | trivial, but the capital matters |
| Sapphire models carry 32 GB | Talkytoaster | size is not a constraint for one region |
| raster Custom Maps (KMZ) work, but around **3 MB** and only at deep zoom | fēnix 7 forum, one reporter | rules the raster route out for a region |
| TopoActive Europe is preloaded, covering Norway and Sweden | Garmin | the free basemap already exists, which is §10.2 |

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
| any computer with a working MTP client | yes, but see §10.6 — the obvious client is the wrong one |

**A false lead to know about before searching.** A summary circulating online describes an Android
app called *"Garmin Map Transfer"* that does exactly this, in convincing detail. It was checked on
2026-09-16: **it is not in the Play Store.** The description traces back to a low-quality GitHub
repository. Do not build a plan on it.

**This is neutral between the options, not an argument against building our own.** Kartmannen needs
the same cable and the same computer. The step happens once, before a trip, whichever map is
installed — and §10.6 shows the computer does not have to be a laptop.

> **Corrected 2026-09-16.** The first draft of this section said that on Linux the step is
> unremarkable because "gvfs or jmtpfs mount the watch". **jmtpfs is exactly the one that fails on
> Garmin**, and it fails on the operation we need. See §10.6; the sentence was written before that
> was looked up, and it would have cost an evening.

---

## 6. Why the door is shut, which is three decisions and not one

Asked because a closed phone route looks like something aimed at the user. It is not. Three
companies decided three separate things, and none of them was about maps.

**Garmin: mass storage out, MTP in.** A mass storage device hands the host its block device, and
while the host has it the watch cannot reach its own filesystem. For a watch that records, runs
Connect IQ apps and plays music that is no longer possible. MTP works at file level: the watch
keeps its filesystem and serves requests against it. Android made the same move in 2011 for the
same reason.

**The trigger looks like music, not maps.** The Garmin forum reports mass storage gone on every
newer watch with music or Garmin Pay, while the fēnix 6 base model without music kept a USB Drive
Mode. That correlation is the evidence, and it points at licensed offline audio rather than at
cartography. Note the strength: these are user statements. Garmin has never explained it publicly.

**The obvious suspicion fails on the timeline**, which is worth writing down so it is not raised
again:

| event | when |
|---|---|
| mass storage disappears, fēnix 5 Plus and 6 | 2018–2019 |
| Outdoor Maps+ announced | December 2022 |
| Outdoor Maps+ extended to Europe | 2024 |

Four years. When the door closed the subscription did not exist, so it cannot have been the cause.

**Apple: no MTP.** The Files app speaks USB Mass Storage and reads ExFAT, FAT32, HFS+ and APFS.
There is no MTP initiator in the iOS SDK, not even for developers. Nothing to do with Garmin.

**Android: responder, not initiator.** A phone is built to be read by a computer, not to read one.
The USB host API exists but carries no MTP initiator, so an app would have to build one on libusb.
Nobody has done it for the fēnix.

**And the part that genuinely is a product decision.** The watch *can* receive maps wirelessly:
Outdoor Maps+ downloads straight to a fēnix 7 over Wi-Fi, no cable and no computer. So there is no
technical barrier to a watch taking a map without a cable. That channel is simply closed to
anything that is not the vendor's own map — and Coros does exactly the same (§8). Whether that is
intent or merely nobody building a feature that earns nothing cannot be known from here, and is
not claimed here.

---

## 7. Custom firmware and Connect IQ: both refused, for different reasons

### 7.1 Custom firmware — no, because it is encrypted

The well-known trick, turning a fēnix 5 Plus into a D2 Delta, looks like more than it was. **No
custom code ran.** Garmin's own firmware was swapped between two models with a matching hardware
ID, matching flags, a higher version number and a corrected checksum. The same author records what
happened next: Garmin began encrypting its firmware, and until that encryption is broken nothing
can be changed. The fēnix 7 is from 2022 and sits inside that era.

There is security research on GarminOS, by Anvil Secure. It did achieve code execution, but
**through the MonkeyC virtual machine** — buffer overflows, type confusion, permission bypass — not
by replacing firmware. An exploited memory-corruption bug is not a foundation for something to
rely on in Nordland, and it gets patched.

**The premise deserves correcting too.** The watch is not open. It tolerates one file format in one
folder, because the map reader is an old and partly understood format. Underneath is a wholly
in-house, undocumented operating system with no open project anywhere near it.

### 7.2 Connect IQ stops exactly one step short

Connect IQ is the sanctioned extension point, and it reaches routes but not maps.

- **It can take routes from the phone.** A CIQ app may receive data over Bluetooth and persist it;
  `PersistedContent` saves courses and routes onto the device. That is how dwMap and IQMapReceiver
  work — courses and waypoints from the phone, no cable. This is real, and it is a second path
  beside Explore for §3.
- **It cannot supply map data.** `MapTrackView` renders the device's *own* built-in map. There is
  no API that takes tiles.
- **The mirror approach is not a substitute.** Locus Map for Garmin has the phone render and the
  watch display. That is a screen on a wrist, not a map on a watch: it needs the phone awake beside
  you, drains both batteries, requires an Android phone, and is reported unreliable offline.
- **The memory rules it out anyway.** A data field gets 256 KB on a fēnix 7 and the whole device has
  5 MB of RAM; pushing tiles across Bluetooth is described in the field as the bottleneck.

So Connect IQ is the right tool for the half that already works and cannot be the tool for the half
that does not.

---

## 8. The other watches, and which ecosystem is actually open

Asked because if some other vendor were open, switching would be cheaper than building. It is not.

| platform | own map data | how |
|---|---|---|
| **Garmin** | yes | `.img` over USB — tolerated, well documented, a whole tool landscape |
| **Coros** | yes, unofficially | `.csm` is `.img`, reverse engineered |
| **Bangle.js** | yes, by design | its own tile uploader, open source |
| Apple Watch | no | a third-party app brings its own maps |
| Wear OS | partly | open platform, but map data is bound to each app |
| Suunto | no | OSM only; *"there are no other maps that can be chosen at the moment"* |
| Amazfit | no | prepared tiles from the Zepp app only |

**The conclusion is the surprising one: the watch already in hand is the most open mainstream
option.** Not because Garmin encourages it — see §7.1 — but because it is tolerated and a
community grew around it. No switch is worth making for this.

### 8.1 Coros, which is the interesting case

The APEX 4 arrived 15 October 2025, costs 429 to 479 dollars by size, and carries 32 GB with free
offline topo and street maps.

**Its map files are Garmin's format.** A developer took them apart: the extension is `.csm`, but the
headers carry `GARMIN` and `DSKIMG`. He built SwissTopo maps for his watch with **ogr2osm, mkgmap
and Osmosis** — the same chain §11 proposes here — laid out as one-degree tiles under `OSM/`, split
into L and R halves when oversized.

**That is the part worth keeping**: the toolchain in §11 is not vendor-locked. One overlay could
serve both watches.

Three cautions, and they are real. It is reverse engineering and nothing about it is supported; the
author soft-locked his watch twice and had to factory reset. It was done on a Vertix 1, while the
APEX 4 has a new map engine with street names and a POI database, and nobody has published whether
the format survived. And **the transfer wall is identical**: Coros states that its watches connect
only to a Mac or PC for file transfers, phones and tablets not supported.

One more, and it is the one that would matter most here: DC Rainmaker's review reports track
quality degrading while navigation is running — *"connect the dots"* in the mountains. That is
precisely this project's use case. Later firmware may have improved it; no solid measurement was
found.

---

## 9. Licences: what may be redistributed

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

## 10. Decided

### 10.1 The overlay first, and it is the small half

Build a **transparent overlay `.img`** holding only this project's own path network: `traktorveg_sti`,
N50's paths, and the router's chains. That is exactly what no bought or free Garmin map carries,
and it is the whole of the unique value.

It is small for a reason that is structural, not lucky: an overlay is **lines only**. No land cover,
no contours, no lettering rules, no zoom-dependent generalisation of areas. A handful of TYP codes
decides how a line looks, and the result can be judged on the wrist in one sitting.

**It is also the cheap way to learn the toolchain.** The basemap in §10.2 is the same chain with
twenty times the rules. Doing the small one first means the chain is proven before the expensive
decision is taken, and if the chain turns out to be unpleasant, very little has been spent.

### 10.2 No self-built basemap yet, and possibly never

A full topographic map from N50 and Topografi 50 is buildable and is **not scheduled**. Three
reasons, in order of weight:

- **It is a second cartography for one dataset.** The web map's appearance lives in `maps.py` and is
  Leaflet's. A Garmin map's appearance is a mkgmap style file plus a TYP file, interpreted by the
  watch's firmware. Nothing transfers between them, and only one of the two can be looked at on this
  box. The other is judged at arm's length, literally.
- **The free basemap is already installed.** TopoActive Europe covers Norway and Sweden and is on
  the watch. It is coarser than N50. It costs nothing and it is there while the overlay is being
  built.
- **It is sold.** §10.4.

Revisit this only if the overlay proves the chain *and* TopoActive turns out to be genuinely
inadequate underneath it. Both halves of that condition matter.

### 10.3 Not Outdoor Maps+

Garmin's subscription is **59,99 € a year** in Europe and it is the only genuinely recurring cost
in this whole area. It buys TOPO Pro — Norway, Sweden and Finland are covered; the British Isles,
the Netherlands, Belgium, Luxembourg and Portugal are not — plus satellite imagery, relief shading
and building footprints.

**Rejected**, and the reason is not only the price. Its content is downloaded to the watch over
Wi-Fi, so it is prepared at home like everything else here, and what it adds over TopoActive is
denser contours and nicer shading — not the paths this project exists for. One forum reader also
reports the download granularity is whole regions, so a small area pulls its neighbours with it.

### 10.4 Kartmannen is the fallback, not the plan

Kartmannen sells Garmin maps built from the same official data, and the fēnix 7 is named in its
device list.

| product | price | note |
|---|---|---|
| N50 Norge | from 449 kr | one-off; *"Kjøp en gang, bruk evig"* |
| Sverige | 599 NOK | |
| updates | 99 kr a year | **optional**, not a subscription |
| one municipality | free | too little for Lomsdal-Visten: the cache holds **eight** N50 kommune archives, 1811 to 1825 |

**The "yearly payment" objection does not apply to this one** and it should not be argued as if it
did; the recurring 60 € is Outdoor Maps+ in §10.3. What does apply is that Kartmannen has no FKB
paths, no chains, and a licence that forbids passing the result on.

Buy it if a good basemap is wanted before the overlay is finished. It is a purchase, not a
commitment, and it does not compete with §10.1.

### 10.5 R2 carries it, and what it reaches

The channel exists and needs no design: `home/trails-map` already provisions an R2 bucket, a custom
domain and a cache ruleset, and `just deploy` ships whole trees — `--tree tiles`, `--tree dem`. An
`--tree garmin` is one more of the same. The precedent for shipping sidecar files out of a map build
is also already set: the build writes six GPX files today.

R2 delivers the `.img` to a computer, because §5 leaves no other possibility. Say so on the download
page rather than letting it be discovered — but say it alongside §10.6, because the computer can be
the size of a matchbox.

### 10.6 The Pi bridge: an eleven-gram computer closes the last gap

The gap in §5 is *a computer standing next to the watch*. Nothing says it has to be a laptop. A
**Raspberry Pi Zero 2 W** is the answer, and the parts list is three items, two of which travel
anyway.

**Hardware.** The Pi Zero's micro-USB data port defaults to host mode, so a plain OTG adapter is
enough; the board is about 10 g. The **official Raspberry Pi Zero case** is the right one — it has
cutouts for both micro-USB ports, and a four-port hub box was considered and rejected: this device
has one job and one port, and a hub chip draws current for nothing.

**Wiring**, which answers "do I need two USB":

- **PWR IN** to the power bank.
- **USB**, the data port, through the OTG adapter to the Garmin cable, which itself ends in USB-A.
- Two cables at the Pi, **one** port on the power bank. The watch draws through the Pi.
- Keep the adapter permanently on the Garmin cable; then it is not a separate small thing to lose.

**Power: ordinary USB is plenty.**

| draw | at 5 V |
|---|---|
| Pi Zero 2 W, idle | 100–140 mA |
| Pi Zero 2 W, all four cores | up to 500 mA |
| fēnix 7, charging | 180 mA, under 1 W |

Worst case about 0.7 A, realistically 0.4 to 0.5 A, against the 1 to 2 A any power bank supplies.
One transfer of a 300 MB map at the reported 2.6 MB/s is about two minutes; with boot, call it five
minutes at half an amp, roughly 40 mAh — under one percent of a 10,000 mAh bank.

**The trap is the opposite of the obvious one.** Power banks cut off below roughly 50–100 mA and the
Pi idles at 100–140 mA, uncomfortably close to that line. Keeping the Wi-Fi up raises the draw;
better, do not leave it idling. Use a short, decent cable too — under-voltage on a Pi looks like a
software fault.

**The tool choice is the part that would cost an evening.** `jmtpfs` is the obvious pick for a
headless box and is **exactly the one that fails on Garmin**: deleting, creating folders and
renaming work, while copying a file *to* the watch ends in an I/O error, with the transfer's final
move from temp to destination the suspected cause. What works: gvfs-backed file managers, at a
reported 2.6 MB/s, and **`aft-mtp-cli`** from android-file-transfer-linux, which is what people use
to put an `.img` into `Garmin` by hand. **MTP allows one connection at a time**, so the gvfs
automounter has to be off or the command-line tool only ever sees "device busy".

**Getting data to the Pi is Wi-Fi, not Bluetooth** — iOS has no general Bluetooth file transfer to
a foreign device. Two shapes, and a third that beats both:

1. **The Pi joins the iPhone's hotspot** and pulls the `.img` from R2 itself. No file ever touches
   the phone. This fits the existing loop: rebuild on `forge` from the phone, deploy to R2, tell the
   Pi to fetch.
2. **The Pi runs an access point** and the phone uploads. The offline fallback, but it needs the
   file on the phone first, so it only moves the problem.
3. **Pre-load the SD card before departure.** Then the normal case needs no network at all.

Drive it from **a small web page the Pi serves**, not SSH. One button in Safari beats typing at a
command line in the rain.

**Unmeasured, and it must be tested at home.** The write failures above come from a fēnix 5 Plus and
the successes from desktop machines. Nothing here has been run on a Pi with a fēnix 7.

---

## 11. The order of work

Not a schedule. The order the pieces depend on each other.

1. **Measure §12 first.** Especially the Explore questions, which are free and which may remove work
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
5. **Install and look at it.** MTP from a Linux machine standing next to the watch — §10.6 for which
   tool, because the obvious one does not work.
6. **Only then**: a `--tree garmin` in the deploy, and a download page saying what §10.5 says.

Steps 2 to 5 are one pipeline stage. It does not belong bolted onto `make map` — `make map` builds a
document, and this builds a device artifact from the same graph.

The Pi in §10.6 is **not** on this path. It is a separate, cheap experiment that can be run at any
time, including before any of the above, because it needs only a map file that already exists.

---

## 12. Open — and all of it needs hardware in hand

Nothing below can be settled from here. Grouped by what it would change.

**§3 is settled** (2026-09-19): the export imports, a `<rte>` lands as a Course and syncs. Still
unmeasured from that test: whether the `<wpt>` reach the watch as locations, and whether the first
sync really takes ~30 minutes.

**Needed before §10.1 is worth starting:**

- Does a transparent overlay actually render over TopoActive on this fēnix 7, and can both be toggled
  independently in map settings?
- How many line classes can be told apart at a glance on a 1.3 inch screen? This caps how much of the
  chain structure is worth encoding.
- What does the watch do with a dense line at low zoom — does it drop it, or draw it as mush?

**Needed before §10.6 goes in a rucksack:**

- Does `aft-mtp-cli` on a Pi Zero 2 W actually write an `.img` into the fēnix 7's `Garmin` folder,
  and does the watch then show the map? This is the whole bet and it is untested.
- Does the power bank in question keep the Pi alive through an idle minute?
- How long does a realistic map take end to end, including boot?

---

## 13. How the figures here were obtained

Everything about devices — §4, §5, §6, §7, §8, §10.3, §10.4 and §10.6 — was read on **2026-09-16**
from:

- Garmin Forums, fēnix 7: *How to upload a .gpx router or course … offline*; *Can you still load OSM
  maps?*; *Fenix 7 USB-OTG compatibility*; *Has anyone been able to get a Custom KMZ Map to work*;
  *using mkgmap to change zoom level details*; *What is the difference between the two USB modes?*
- Garmin Forums, fēnix 8: *How to use 3rd party maps and Custom Maps?*; epix 2: *USB Drive Mode is
  needed! MTP is not supported on Mac*; fēnix 5 Plus: *MTP issues on Debian*
- fēnix 7 owner's manual: *Garmin Explore*, *Managing Maps*, *Showing and Hiding Map Data*
- Garmin Explore on the App Store; Garmin newsroom on Outdoor Maps+, announcement and Europe
- the5krunner and GPS Radler on Outdoor Maps+ pricing; GPSrChive on its European coverage
- kartmannen.no, Norwegian and Swedish product pages
- mkgmap.org.uk; `roelderickx/ogr2osm`; OpenStreetMap wiki, *OSM Map On Garmin*; Talkytoaster
- **§6–§7**: mbirth.uk, *Pimp my Garmin*; Anvil Secure, *Compromising Garmin's Sport Watches*;
  Herbert Oppmann's GCD format notes; Connect IQ docs, *MapTrackView* and *Persisting Data*;
  `libmtp`; Apple Developer Forums on MSC and MTP
- **§8**: coros.com APEX 4 pages; DC Rainmaker's APEX 4 review; panaetius.github.io, *Custom maps on
  Coros watches*; COROS Help Center, *Watch Drive Not Detected by Computer*; Suunto community forum;
  Amazfit FAQ; Espruino `BangleApps/openstmap`; workoutdoors.net
- **§10.6**: Jeff Geerling and CNX Software on Pi Zero 2 W power; Garmin forum on charger wattage;
  Raspberry Pi forums on OTG host mode; android-file-transfer-linux

Everything in §9 and the file references in §1 and §3 were read out of this repository on the same
day and are measured, not reported.

---

## 14. Changes

- **2026-09-16** — written. No code changed and none is proposed yet; §12 has to come first.
- **2026-09-16** — extended with §6 (why the door is shut), §7 (firmware and Connect IQ), §8 (the
  other watches, Coros in particular) and §10.6 (the Pi bridge). **One correction**: §5 had claimed
  jmtpfs mounts the watch unremarkably on Linux. It does not — it fails on exactly the write we
  need. Sections renumbered once to fit the new material; there are no external references to break.
- **2026-09-19** — §3 measured on the iPhone and the fēnix 7. The trkseg guess was wrong; the real
  cause is that Explore makes a Track of a `<trk>` and a Course of a `<rte>`, and it condenses a
  course to 200 points worse than we do. The Garmin variant is specified in §3 and not yet built.
  §12's first block closed.
