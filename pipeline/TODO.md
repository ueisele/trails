# Pipeline TODO

Next steps for the GraphHopper pipeline, written after a code review of the
unpushed work (2026-08-12). Ordered by what unblocks what — these are triggers,
not deadlines.

## Where things stand

All five steps are implemented in Python: fetch, validate, transform, build and
release, 1,628 lines with no placeholder markers left in them.

What is *not* true yet:

- The **workflow does not call them**. `.github/workflows/pipeline-build.yml`
  still runs `touch work/trails.osm.pbf` (line 152) and
  `touch graphhopper-data/graph.bin` (line 194) instead of the real steps.
- The transform produces ways, but their **tag values are raw Norwegian**, so
  GraphHopper cannot route on them yet. See step 2 below.
- The pipeline is **manual only**: the weekly cron is commented out until the
  placeholders are gone.

Already fixed and verified:

- `graphhopper_pipeline` is importable (added to the wheel packages)
- transform emits one way per line part — all 139,191 centerlines are
  MultiLineString and used to be dropped silently
- fetch/validate/transform speak Turrutebasen's Norwegian field names throughout
- the join no longer renames `objtype` away, so every way carries a `highway` tag
- `make check` covers `pipeline/`; the `test-pipeline` CI job passes

Measured on 2,000 real segments after those fixes: 2,314 ways, 163,695 nodes,
a `highway` tag on every way. Before: zero ways.

## 1. Make the workflow run the real steps

**Trigger: this is the next thing to do.**

Replace the two `touch` placeholders with the actual pipeline invocation. Only
then does it become visible whether the five steps hold together end to end —
so far only the transform step has been exercised against real data.

- `.github/workflows/pipeline-build.yml:152` — transform job
- `.github/workflows/pipeline-build.yml:194` — build job

## 2. Emit real OSM tag values

**Trigger: before the first routing test. Nothing downstream means anything
until this is done.**

Today a way looks like `highway=Fotrute`, `sac_scale=Enkel (Grønn)`,
`trail_marking=Merket` — the source terms, passed through verbatim. GraphHopper
needs OSM vocabulary (`highway=path`, `sac_scale=hiking`, …).

Two pieces:

- `config.py:133` reads only `field = "tag"` pairs from the TOML. The
  `OSMMapping.values` field exists but is never populated, so value tables
  cannot be expressed in `config/countries/no.toml` at all.
- Decide the vocabulary for the five observed `rutefolger` values. Distribution
  over 139,191 segments (2026-08 extract): Sti 80,924 · Bilvei 24,041 ·
  Traktorvei 17,602 · Skogsbilvei 4,876 · Gangvei 2,391.

This is the `highway_refinement` mapping the config already names but never
implements.

Worth adding alongside: an `@pytest.mark.integration` test asserting that the
generated `highway` values are in the OSM vocabulary. Right now 97 green tests
sit on a pipeline that cannot route — that is the same trap as before, one level
up.

## 3. Fix the release step — all three together

**Trigger: before the first real release.**

These share the tag and artifact format, so splitting them wastes effort.

- `release.py:297` — the tag is built from the raw ATOM `updated` timestamp,
  e.g. `v2026-08-12-geonorge-2026-08-09T17:37:08+02:00`. A `:` is illegal in a
  git ref, so `gh release create` rejects it outright.
- `release.py:275` — `_get_latest_release_info` searches for `"OSM Hash:"` while
  the notes it writes contain `- **OSM Hash**: \`hash\``. The previous hash is
  never recovered, so a release is cut on every run even when the data is
  byte-identical.
- `release.py:323` — the artifact is always named `*.osm.pbf`, even when the
  transform fell back to XML because osmium was unavailable. Consumers get a
  parse error.

Decide the tag format here too: it currently carries **no country code**.
`_cleanup_old_releases` therefore cannot filter by country — the old
`country_code in tag` test only ever passed because "no" is a substring of
"geonorge". Multi-country support needs the format extended.

## 4. Rethink the skip semantics

**Trigger: before re-enabling the weekly cron.**

`main.py:88-91` returns 0 for the *entire* pipeline when
`FetchTrailsStep.should_skip` is true, and that fires whenever the cache marker
is younger than 7 days. On a weekly schedule the elapsed time is 7 days minus a
few minutes, so `(now - mtime).days` is 6 and the run silently does nothing while
reporting success.

A skip should skip the fetch, not the pipeline — or the freshness window should
not be the same length as the schedule interval.

## Stale documentation

`pipeline/README.md` still describes a weekly schedule ("Every Saturday at
6:00 AM UTC") and marks all five steps as implemented without noting that the
workflow does not call them. It was left untouched because it carries unrelated
uncommitted changes.
