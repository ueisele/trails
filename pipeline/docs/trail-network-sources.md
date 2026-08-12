# Trail Network Sources

Which datasets should feed the routing graph, and how do we combine them without
duplicating trails?

Supersedes the earlier `osm-integration-proposal.md`, which framed this as a
Turrutebasen + OpenStreetMap question. Measurements since then show that two
Kartverket datasets — FKB and N50 — carry far more of the network than either,
and change what the merge strategy should be.

## The measurement that drives this

Turrutebasen holds only *organised* routes: waymarked and maintained by some
body. It is not a map of where you can walk. Measured inside three national
parks (2026-08 extracts, lengths in km):

| Park | Turrutebasen | FKB | Turrutebasen ⊆ FKB (25 m) | ⊆ FKB (50 m) | FKB adds |
|---|---|---|---|---|---|
| Lomsdal-Visten | 19.4 | 210.8 | 100.0 % | 100.0 % | 191.4 |
| Jotunheimen | 234.7 | 410.5 | 95.7 % | 99.0 % | 179.8 |
| Rondane | 171.3 | 894.9 | 96.1 % | 97.0 % | 725.0 |

Two things follow.

**Turrutebasen is essentially a subset of FKB.** Between 96 % and 100 % of its
length already exists in FKB within 25 m, and 97–100 % within 50 m. There is
almost nothing in Turrutebasen that FKB does not already have as geometry.

**FKB adds a lot.** Between 180 and 725 km of walkable paths per park that
Turrutebasen does not contain at all.

## What this means for the architecture

The earlier proposal assumed every additional source brings a mix of new trails
and duplicates, so it designed a geometric deduplication pass: buffer each
candidate way, discard it if it overlaps an existing trail by more than 80 %.

For FKB that machinery is unnecessary. Since Turrutebasen is contained in FKB,
there is nothing to merge geometrically. The better structure is:

- **FKB provides the geometry** — the full walkable network
- **Turrutebasen provides the attributes** — name, waymarking, difficulty,
  significance, maintainer, season

So instead of deduplicating two networks, attach Turrutebasen's attributes to the
FKB segments they correspond to. That is an attribute join along geometry, not a
merge, and it avoids the failure mode the old proposal itself flagged: parallel
trails wrongly collapsed into one.

The 1–4 % of Turrutebasen that FKB does not cover still needs a decision — see
open questions.

## The sources

### Turrutebasen (Kartverket, CC0)

Marked and maintained routes with rich attributes. Nationwide, one download,
already integrated. 139,191 hiking segments.

**Role: the attribute source.** It is what tells you a path is waymarked, who
maintains it, and how hard it is. As a geometry source it is largely redundant.

Note: every centerline is a `MultiLineString`, and all values are code-expanded
by the loader (`Sti`, not `ST`).

### FKB via the Traktorveg og Skogsbilveg WFS (Kartverket, CC BY 4.0)

The detailed path network Kartverket's topographic map draws at high zoom.
`typeveg` in (`sti`, `traktorveg`).

**Role: the geometry base.** Richest source by a wide margin — 2 to 10 times
Turrutebasen's length in the parks measured.

Access: `https://wms.geonorge.no/skwms1/wms.traktorveg_skogsbilveger`, GeoJSON,
bbox-paged, no account needed. The FKB-TraktorvegSti *file* download is
access-restricted; the WFS is not. Features arrive in very short pieces, so merge
them before use.

### N50 Kartdata (Kartverket, CC BY 4.0)

The generalised network the topo map draws at lower zoom.

**Role: a cross-check and a gap-filler, not a primary source.** It is *not* a
subset of FKB: within 5 km of Lomsdal-Visten, 51 km of N50 path (14 %) has no FKB
line within 50 m, including 26 stretches over 500 m and one of 6.8 km. It also
carries categories the WFS does not serve at all — `barmarksløype`,
`gangOgSykkelveg` — plus ferries and cabins.

Geometry is coarser: 61 vertices per km against FKB's 150.

Access: ordered per municipality through the Geonorge order API.

### OpenStreetMap (ODbL)

Independently surveyed, so genuinely different in coverage, and the only source
with community knowledge like `sac_scale`, `trail_visibility` or hut operators.

**Role: optional supplement.** It is the one source that still needs the
deduplication pass, because it overlaps the Kartverket data without deriving from
it — 96.8 % of Turrutebasen was within 25 m of an OSM way in Lomsdal-Visten, but
that leaves a real residual, and OSM's own extra paths are not a subset of
anything.

Licence matters here: ODbL is share-alike. Mixing OSM geometry into a published
routing graph has consequences that CC BY 4.0 and CC0 do not. Decide this before
integrating, not after.

## Deduplication, only where it is needed

Applies to OSM alone. The approach from the original proposal stands:

```
For each OSM way:
  1. Buffer the way by a tolerance
  2. Measure the intersection with the union of the Kartverket network
  3. If the overlap exceeds the threshold -> duplicate, discard
  4. Otherwise -> keep
```

| Parameter | Suggested | Alternatives | Note |
|---|---|---|---|
| Buffer | 30 m | 20 m strict, 50 m lenient | Covers GPS and survey differences |
| Overlap threshold | 80 % | 70 % / 90 % | Balances precision and recall |
| OSM highway types | path, footway, track, cycleway, service | + bridleway, steps | Start conservative |

Risks unchanged from the original: parallel trails collapsing into one (mitigate
with a tight buffer and a high threshold), and performance over large geometry
sets (use a spatial index and buffer the Kartverket union once).

## Open questions

1. **The uncovered Turrutebasen remainder.** 1–4 % of its length has no FKB
   counterpart. Is that a real gap in FKB, a positional offset, or route types
   FKB does not model? Needs a look at the actual segments before deciding
   whether to carry them through as extra geometry.
2. **How to attach attributes.** Nearest-line matching within a tolerance, or a
   shared identifier? Turrutebasen and FKB have no common key, so it will be
   geometric — which needs its own tolerance and a rule for one-to-many matches.
3. **Whether to include OSM at all**, given ODbL and the fact that FKB already
   covers more ground.
4. **Whether N50 is worth carrying** once FKB is in, or whether its unique 14 %
   is mostly categories nobody routes on.

## Reproducing the numbers

The library modules used for all measurements above:

- `trails.io.sources.geonorge` — Turrutebasen
- `trails.io.sources.traktorvegsti` — FKB paths via WFS
- `trails.io.sources.n50` — N50, ordered per municipality
- `trails.io.sources.overpass` — OSM
- `trails.io.sources.naturbase` — park boundaries for clipping
- `trails.utils.geo.merge_lines` — for FKB's fragmented features

Containment is measured as `source.difference(other.union_all().buffer(tol))`,
in EPSG:25833.

## Related

`land-cover-integration.md` covers a different question — what the *terrain* is
(forest, marsh, rock) for routing preferences, rather than which paths exist. The
two meet at surface tags: `typeveg` from FKB and N50 can feed the same
`surface=*` tags that `rutefolger` from Turrutebasen does today.
