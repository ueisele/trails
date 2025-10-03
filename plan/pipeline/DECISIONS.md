# Pipeline Planning Decisions Summary

All key decisions made during the GraphHopper pipeline planning phase.

## 1. Deployment & Orchestration

**Deployment Environment:** GitHub Actions
**Storage:** GitHub Releases (downloadable via `make graphhopper-download`)
**GraphHopper Deployment:** Local initially (download releases), can evolve to cloud later
**Orchestration:** GitHub Actions built-in workflow orchestration

**Rationale:**
- Serverless, no infrastructure to maintain
- Free tier sufficient (2000 min/month)
- Simple setup (YAML file)
- Easy local development with `act`
- Can push to any cloud storage later

**Alternative considered:** AWS Lambda/Step Functions (rejected: 15min timeout too short, more complex)

---

## 2. Data Storage

**Release Content:** Only necessary files (GraphHopper graph)
**Versioning:** Date-based + source data version (e.g., `v2025-10-03-geonorge-20251001`)
**Retention:** Keep last 2 releases only
**Download:** `make graphhopper-download` (calls `pipeline/scripts/download-graph.sh`)

**Storage locations:**
- Primary: GitHub Releases
- Future: Can add S3/GCS when hosting GraphHopper remotely

---

## 3. Update Frequency

**Schedule:** Every Saturday 6 AM UTC (cron: `0 6 * * 6`)
**Conditional:** Only release if source data changed
**Manual Trigger:** Always available via workflow_dispatch
**Geonorge Update Pattern:** Monday nights (we check Saturday, captures full week)

**Check strategy:**
- Verify source data changed (checksum/last-modified)
- Skip build if no changes
- Log "No changes detected"

---

## 4. Error Handling & Validation

### Retry Strategy
- **Fetch failures:** 5 retries with exponential backoff
- **Initial backoff:** 5 minutes
- **Backoff multiplier:** 2x (double each retry)
- **Max backoff:** 1 hour (capped)
- **Total max wait:** ~2 hours

### Validation
- **Checksum:** Validate if provided by Geonorge
- **OSM conversion:** Fail entire pipeline on error
- **GraphHopper build:** Fail entire pipeline on error

### Quality Checks (all must pass)
1. ✅ Trail count must not drop >20%
2. ✅ Bounding box must not change drastically (Norway bounds expected)
3. ✅ Unique `local_id` per geometry segment (NOT `trail_number` - trails have multiple segments)
4. ✅ All geometries must be valid
5. ✅ GraphHopper routing tests must pass (known trails: Oslo-Frognerseteren, Preikestolen, etc.)

### Notifications
- GitHub Actions Summary (always)
- Auto-create GitHub Issue on failure
- Auto-close issue on next success

---

## 5. MVP Scope

### Data Sources (Norway only initially)
- ✅ Turrutebasen (trails) - Geonorge
- ✅ Elevation data (DEM) - Geonorge
- ✅ Land cover (AR5) - Geonorge

### GraphHopper Configuration
- **Profile:** Hiking only (for MVP)
- **Multi-country ready:** Architecture supports adding Sweden, Denmark, etc. later

### Trail Attributes (16 total)

**Tier 1 - Essential (5):**
1. objtype (100%) → highway tag
2. rutefolger (94%) → highway refinement + surface inference
3. merking (100%) → trail_marking tag
4. rutenavn (95.4%) → name tag
5. rutenummer (100%) → ref tag

**Tier 2 - Recommended (3):**
6. gradering (36.2%) → sac_scale tag (with inference from rutefolger)
7. rutebetydning (29.5%) → importance tag
8. skilting (34.7%) → information tag (when present)

**Tier 3 - Conditional (3):**
9. spesialfotrutetype (29.7%) → tourism tag (optional)
10. belysning (7.2%) → lit tag (only when "Yes")
11. sesong (2.6%) → access:conditional (only when set)

**Tier 4 - Quality Indicators (5):**
12. rutetype (4.0%) → route hierarchy (complements rutebetydning)
13. trafikkbelastning (0.4%) → traffic penalty (when present)
14. vedlikeholdsansvarlig (100%) → maintainer quality score
15. noyaktighet (100%) → position accuracy confidence
16. oppdateringsdato (100%) → data freshness score

**Key insight:** Many essential attributes have low completeness, so we use **inference strategy**:
- Surface type inferred from `rutefolger` (94% complete)
- Difficulty inferred from `rutefolger` when missing
- Use quality indicators to prefer high-quality routes

---

## 6. Project Structure

**Approved Structure:** V3 (Maximum Locality)

**Principle:** Each component is self-contained with its own src, tests, docs, scripts

```
trails/
├── .github/          # Workflows (must be in root)
├── lib/              # Shared library
│   ├── src/trails/
│   ├── tests/trails/ # Mirrors src structure
│   ├── docs/
│   └── README.md
├── pipeline/         # GraphHopper pipeline
│   ├── src/graphhopper_pipeline/
│   ├── tests/graphhopper_pipeline/ # Mirrors src structure
│   ├── config/
│   ├── scripts/
│   ├── docs/
│   └── README.md
├── analysis/         # Personal exploration
│   ├── notebooks/
│   ├── scripts/
│   ├── docs/
│   └── README.md
├── app/              # Future: GraphHopper server + frontend
└── docs/             # Cross-cutting documentation only
```

**Key decisions:**
- ✅ Tests mirror src structure exactly (`src/trails/sources/norway.py` → `tests/trails/sources/test_norway.py`)
- ✅ Each component owns its tests, docs, scripts
- ✅ Multi-country ready from day one
- ✅ Makefile calls scripts (scripts contain complex logic)
- ✅ All dependencies in main pyproject.toml

---

## 7. Code & Dependencies

**Code Reuse:** Full reuse of existing `trails` library code
**Dependencies:** All in main `pyproject.toml` (no separate files)
**Configuration:** TOML for static config, env vars for secrets

**Testing Strategy:**
- Unit tests: `tests/{component}/{package}/` (fast, always run)
- Integration tests: Same structure, marked with `@pytest.mark.integration` (slow, manual)
- Routing validation: Part of pipeline execution (not a test)

---

## 8. Implementation Plan

### Phase 1: Cleanup (1 day)
- Clean up `src/trails/io/export/gpx.py`
- Review notebooks (keep analysis-worthy, remove experiments)
- Clear notebook outputs

### Phase 2: Restructure (1 day)
- Create new directory structure
- Move code to new locations
- Update imports

### Phase 3: Shared Library Interface (1 day)
- Create base classes
- Refactor Geonorge code
- Create TrailNetwork model
- Create OSM format module

### Phase 4: Implement Pipeline (5-7 days)
- Orchestrator
- Pipeline steps (fetch, transform, build, release)
- Country-specific mappings
- Validation and quality checks

### Phase 5: Testing (2-3 days)
- Unit tests
- Integration tests
- Local pipeline testing

### Phase 6: CI/CD (1-2 days)
- GitHub Actions workflow
- Automated pipeline testing
- Release automation

**Total estimated time:** 12-18 days

---

## Key Technical Details

### Trail Data Facts
- **134,047** hiking trail segments (spatial)
- **163,558** trail info records (attribute table)
- **9,985** unique trail_numbers (trails have multiple segments)
- **local_id** is unique per segment (validate this, NOT trail_number)

### OSM Conversion Strategy
- GraphHopper needs OSM format (PBF or XML)
- Convert Turrutebasen attributes to OSM tags
- Inference for missing data (especially surface type)
- Quality indicators influence routing preferences

### Multi-Country Architecture
- Abstract base: `TrailDataSource` (in lib)
- Country implementations: `GeonorgeSource` (Norway), `LantmäterietSource` (Sweden)
- Pipeline-specific: Country mappings to OSM tags
- Config per country: `pipeline/config/countries/{country}.toml`

---

## Open Questions / Future Enhancements

1. ❓ Which GPX export notebook to keep/remove?
2. 🔮 When to add Sweden/Denmark support?
3. 🔮 When to move GraphHopper to cloud hosting?
4. 🔮 When to add frontend application?
5. 🔮 Land cover integration for routing preferences?

---

## Documentation References

- **Project Structure:** `plan/pipeline/project-structure.md`
- **Attribute Mapping:** `plan/pipeline/turrutebasen-attributes-for-routing.md`
- **Error Handling:** `plan/pipeline/error-handling-validation.md`
- **Key Questions:** `plan/pipeline/key-questions.md`
- **GraphHopper Proposals:** `docs/graphhopper_implementation_proposals.md`
