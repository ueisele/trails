# Turrutebasen Attributes for GraphHopper Routing

## Available Attributes from Turrutebasen

**Data source:** 134,047 hiking trail segments + 163,558 trail info records (Geonorge Turrutebasen, October 2024)

**Note:** Some attributes are in the spatial layer (geometry), others in the info table (linked by foreign key).

### Core Trail Attributes

| Attribute (Norwegian) | English Name | Completeness | Type | Example Values | OSM Relevance | Recommendation |
|-----------|------|------|---------------|----------------|----------------|----------------|
| **objtype** | object_type | 100% | code | "Hiking trail" | Trail type classification | ✅ **ESSENTIAL** - Maps to highway tag |
| **rutefolger** | trail_follows | 94.0% | code | "Path/trail", "Hiking road", "Car road", "Tractor road", "Water/waterway" | What the route follows | ✅ **ESSENTIAL** - Determines routing cost |
| **gradering** | difficulty | 36.2% (info) | code | "Easy (Green)", "Medium (Blue)", "Strenuous (Red)", "Expert (Black)", "Not graded" | Difficulty rating | ✅ **ESSENTIAL** - Affects route preferences |
| **underlagstype** | surface_type | 2.8% | code | "Natural ground", "Gravel", "Asphalt/concrete", "Other surface" | Surface type | ✅ **ESSENTIAL** - Critical for routing decisions |
| **merking** | marking | 100% | code | "Marked", "Not marked", "Seasonally marked" | Trail marking | ✅ **RECOMMENDED** - Safety consideration |
| **sesong** | season | 2.6% | code | "Year-round", "Summer", "Winter" | Season availability | ✅ **RECOMMENDED** - Seasonal routing |
| **rutebredde** | trail_width | 2.4% | code | "0.5 - up to 1.5 m", "3 - 6 m", "0-0.5 m", "1.5 - up to 3 m", "over 6 m" | Width categories | ⚠️ **OPTIONAL** - Nice to have |
| **tilpasning** | accessibility | 0.9% (info) | code | "Wheelchair", "Walking", "Baby stroller", "Other" | Accessibility | ⚠️ **OPTIONAL** - For specialized routing |

### Route Classification

| Attribute (Norwegian) | English Name | Completeness | Type | Example Values | OSM Relevance | Recommendation |
|-----------|------|------|---------------|----------------|----------------|----------------|
| **rutetype** | trail_type | 4.0% (info) | code | "Main route", "Branch route", "Alternative route" | Route hierarchy | ✅ **RECOMMENDED** - Affects route priority |
| **rutebetydning** | trail_significance | 29.5% (info) | code | "National significance", "Regional significance", "Local significance" | Importance level | ⚠️ **OPTIONAL** - Could affect preferences |

### Infrastructure & Maintenance

| Attribute (Norwegian) | English Name | Completeness | Type | Example Values | OSM Relevance | Recommendation |
|-----------|------|------|---------------|----------------|----------------|----------------|
| **vedlikeholdsansvarlig** | maintenance_responsible | 100% (info) | string | "Strømstad kommune", "Sotenäs kommune", "Lysekil kommune" | Maintenance authority | ❌ **SKIP** - Not relevant for routing |
| **belysning** | lighting | 7.2% | code | "Yes", "No" | Lighting availability | ⚠️ **OPTIONAL** - Night routing consideration |
| **skilting** | signage | 34.7% | code | "Yes", "No" | Signage presence | ⚠️ **OPTIONAL** - Navigation confidence |
| **tilrettelegging** | facilitation | N/A | code | (POI data - benches, cabins, etc.) | Facilities | ❌ **SKIP** - POI data, not routing |

### Specialized Trail Types

| Attribute (Norwegian) | English Name | Completeness | Type | Example Values | OSM Relevance | Recommendation |
|-----------|------|------|---------------|----------------|----------------|----------------|
| **spesialfotrutetype** | special_hiking_trail_type | 29.7% (info) | code | "Coastal trail", "Exercise trail", "Historical travel route", "Nature trail", "Cultural trail" | Special classification | ⚠️ **OPTIONAL** - Tagging only |
| **spesialskiloypetype** | special_ski_trail_type | N/A | code | (ski-specific) | Ski trail type | ❌ **SKIP** - Not for hiking MVP |
| **spesialsykkelrutetype** | special_bike_trail_type | N/A | code | (bike-specific) | Bike trail type | ❌ **SKIP** - Not for hiking MVP |
| **spesialannenrutetype** | special_other_trail_type | N/A | code | (paddling, horse riding, etc.) | Other trail types | ❌ **SKIP** - Not for hiking MVP |

### Measurements & Metadata

| Attribute (Norwegian) | English Name | Completeness | Type | Example Values | OSM Relevance | Recommendation |
|-----------|------|------|---------------|----------------|----------------|----------------|
| **rutenavn** | trail_name | 95.4% (info) | string | "Kuststigen Strømstad kommune", "Bohusleden", "Kuststigen Sotenäs kommune" | Route name | ✅ **RECOMMENDED** - For identification |
| **rutenummer** | trail_number | 100% (info) | string | "F_20180315_1", "F_20180315", "F_20180315_3" | Route number/ID | ✅ **RECOMMENDED** - For identification |
| **SHAPE_Length** | geometry_length | 100% | Float64 | 1219.77, 571.32, 588.26, 3229.42, 330.94 (meters) | Geometry length | ❌ **SKIP** - Calculated by GraphHopper |
| **noyaktighet** | accuracy | 100% | Int64 | 2000, 53, 90, 1500, 2500 (meters) | Position accuracy | ❌ **SKIP** - Metadata only |
| **malemetode** | measurement_method | 100% | code | "Free-hand drawn on map", "GNSS: Code measurement, single", "Digitized from orthophoto: 0.5 m resolution" | Measurement method | ❌ **SKIP** - Metadata only |
| **trafikkbelastning** | traffic_load | 0.4% | code | "Without motorized traffic", "Low traffic load", "Some traffic load", "High traffic load" | Traffic level | ⚠️ **OPTIONAL** - For road sections only |

### Dates & Identifiers

| Attribute (Norwegian) | English Name | Completeness | Type | Example Values | OSM Relevance | Recommendation |
|-----------|------|------|---------------|----------------|----------------|----------------|
| **lokalid** | local_id | 100% | string | (internal IDs) | Local ID | ❌ **SKIP** - Internal reference |
| **datafangstdato** | data_capture_date | 100% | datetime | 2018-03-15, 2012-04-29, 2009-07-04, 2017-04-03, 2016-09-16 | Data capture date | ❌ **SKIP** - Metadata only |
| **oppdateringsdato** | update_date | 100% | datetime | 2023-10-25, 2024-03-14, 2024-07-25, 2024-10-04, 2024-11-11 | Last update date | ❌ **SKIP** - Metadata only |

### Data Completeness Notes

**High completeness (>90%):**
- ✅ object_type, trail_follows, marking (spatial layer)
- ✅ trail_name, trail_number, maintenance_responsible (info table)
- ✅ All metadata fields (dates, IDs, measurements)

**Medium completeness (30-90%):**
- ⚠️ difficulty (36.2%), signage (34.7%), trail_significance (29.5%)

**Low completeness (<10%):**
- ❌ surface_type (2.8%), season (2.6%), trail_width (2.4%)
- ❌ lighting (7.2%), trail_type (4.0%), accessibility (0.9%)
- ❌ traffic_load (0.4%)

**Implication:** Some ESSENTIAL attributes like `difficulty` and `surface_type` have low completeness. We'll need fallback/default values for routing.

## Proposed OSM Tag Mapping for GraphHopper

### ESSENTIAL Attributes (MVP Must-Have)

```python
# These directly affect routing costs and preferences

1. objtype → highway tag
   - Fotrute → highway=path
   - Sykkelrute → highway=cycleway
   - Skiløype → piste:type=nordic (or skip for hiking MVP)

2. rutefolger → highway/surface refinement
   - ST (Sti) → highway=path, surface=ground
   - TV (Turvei) → highway=path, surface=compacted
   - BV (Bilvei) → highway=unclassified
   - SB (Skogsbilvei) → highway=track
   - IT (I terreng) → highway=path, trail_visibility=no
   - US (Utydelig sti) → highway=path, trail_visibility=bad

3. gradering → sac_scale (SAC mountain hiking scale)
   - G (Grønn/Easy) → sac_scale=hiking
   - B (Blå/Medium) → sac_scale=mountain_hiking
   - R (Rød/Strenuous) → sac_scale=demanding_mountain_hiking
   - S (Svart/Expert) → sac_scale=alpine_hiking

4. underlagstype → surface
   - 1 (Asfalt/betong) → surface=asphalt
   - 2 (Grus) → surface=gravel
   - 3 (Naturlig grunn) → surface=ground
   - 4 (Annet) → surface=unpaved
```

### RECOMMENDED Attributes (Enhance Routing Quality)

```python
5. merking → trail_marking
   - JA → trail_marking=yes
   - NEI → trail_marking=no
   - SM → trail_marking=seasonal

6. sesong → seasonal restrictions
   - S (Sommer) → access:conditional=no @ (Nov-Apr)
   - V (Vinter) → access:conditional=no @ (May-Oct)
   - H (Helårs) → (no restriction)

7. rutetype → importance tag
   - 1 (Hovedrute) → importance=high
   - 2 (Forgreningsrute) → importance=medium
   - 3 (Materute) → importance=low

8. rutenavn/rutenummer → name/ref tags
   - rutenavn → name=*
   - rutenummer → ref=*
```

### OPTIONAL Attributes (Nice to Have)

```python
9. rutebredde → width
   - 0 → width=0.3
   - 1 → width=1.0
   - 2 → width=2.0
   - 3 → width=4.5
   - 4 → width=8.0

10. tilpasning → accessibility tags
    - R (Rullestol) → wheelchair=yes
    - B (Barnevogn) → stroller=yes

11. belysning → lit tag
    - JA → lit=yes
    - NEI → lit=no

12. trafikkbelastning → (for road sections only)
    - 1 → motor_vehicle=no
    - 2 → traffic_class=low
    - 5 → traffic_class=high
```

## Updated Recommendation for MVP (Based on Data Analysis)

### Tier 1 - MUST INCLUDE (High completeness + Essential for routing)

| Attribute | Completeness | Reason | Default/Fallback Strategy |
|-----------|--------------|--------|---------------------------|
| **objtype** | 100% | Trail type → highway tag | N/A - always present |
| **rutefolger** | 94.0% | Route surface/type → routing cost | Default to "Path/trail" for missing 6% |
| **merking** | 100% | Trail marking → safety/confidence | N/A - always present |
| **rutenavn** | 95.4% | Trail identification | Use rutenummer if missing |
| **rutenummer** | 100% | Trail reference ID | N/A - always present |

### Tier 2 - STRONGLY RECOMMENDED (Medium completeness + High value)

| Attribute | Completeness | Reason | Default/Fallback Strategy |
|-----------|--------------|--------|---------------------------|
| **gradering** | 36.2% | Difficulty → route preference | Default to "Not graded" or infer from rutefolger:<br>- "In terrain" → Medium<br>- "Hiking road" → Easy<br>- "Path/trail" → Easy-Medium |
| **skilting** | 34.7% | Signage → navigation confidence | Only use when present, don't default |
| **rutebetydning** | 29.5% | Significance → route priority | Default to "Local significance" |
| **spesialfotrutetype** | 29.7% | Special trail type → tagging only | Optional tag, skip if missing |

### Tier 3 - CONDITIONAL (Low completeness - use with caution)

| Attribute | Completeness | Reason | Strategy |
|-----------|--------------|--------|----------|
| **belysning** | 7.2% | Lighting → night routing | Only tag when explicitly "Yes" |
| **rutetype** | 4.0% | Trail hierarchy → priority | **Include:** Use when present, complements rutebetydning for finer-grained route priority |
| **underlagstype** | 2.8% | Surface type → routing cost | **Infer from rutefolger instead:**<br>- "Hiking road" → surface=compacted<br>- "Car road" → surface=asphalt<br>- "Path/trail" → surface=ground<br>- "In terrain" → surface=ground<br>Don't use explicit underlagstype due to low coverage |
| **sesong** | 2.6% | Season restriction | Only apply restriction when explicitly set |
| **rutebredde** | 2.4% | Width → accessibility | Skip for MVP (too sparse) |
| **tilpasning** | 0.9% | Accessibility | Skip for MVP (too sparse) |
| **trafikkbelastning** | 0.4% | Traffic load → routing cost penalty | **Include:** When present, penalize high-traffic routes for hiking preference |

### Tier 3.5 - METADATA AS QUALITY INDICATORS

| Attribute | Completeness | Reason | Strategy |
|-----------|--------------|--------|----------|
| **vedlikeholdsansvarlig** | 100% (info) | Maintenance authority → trail quality | **Include:** Can weight routes by known reliable maintainers (e.g., DNT vs. local volunteers) |
| **noyaktighet** | 100% | Position accuracy → data quality | **Include:** Use as confidence score - prefer routes with <100m accuracy over >1000m accuracy |
| **oppdateringsdato** | 100% | Last update date → data freshness | **Include:** Prefer recently updated routes (within 2 years) over old data (>5 years) |

### Tier 4 - SKIP ENTIRELY

**Low value or not relevant for hiking MVP:**
- ❌ **tilrettelegging** - POI data, not routing attributes
- ❌ **spesialskiloypetype** - Ski-specific
- ❌ **spesialsykkelrutetype** - Bike-specific
- ❌ **spesialannenrutetype** - Other activity types
- ❌ **preparering**, **ryddebredde** - Ski-specific
- ❌ **lokalid**, **datafangstdato** - Metadata only
- ❌ **SHAPE_Length**, **malemetode** - Calculated or metadata

### Final MVP Attribute List

**Include in OSM conversion:**

1. ✅ **objtype** (100%) → highway tag
2. ✅ **rutefolger** (94%) → highway refinement + surface inference
3. ✅ **merking** (100%) → trail_marking tag
4. ✅ **rutenavn** (95.4%) → name tag
5. ✅ **rutenummer** (100%) → ref tag
6. ✅ **gradering** (36.2%) → sac_scale tag (with inference)
7. ✅ **rutebetydning** (29.5%) → importance tag (with default)
8. ✅ **skilting** (34.7%) → information tag (when present)
9. ⚠️ **spesialfotrutetype** (29.7%) → optional tourism tag
10. ⚠️ **belysning** (7.2%) → lit tag (only when "Yes")
11. ⚠️ **sesong** (2.6%) → access:conditional (only when explicitly set)

**NEW - Quality indicators (metadata as routing factors):**
12. ✅ **rutetype** (4.0%) → route hierarchy (when present, complements rutebetydning)
13. ✅ **trafikkbelastning** (0.4%) → traffic penalty (when present)
14. ✅ **vedlikeholdsansvarlig** (100%) → maintainer quality score
15. ✅ **noyaktighet** (100%) → position accuracy confidence
16. ✅ **oppdateringsdato** (100%) → data freshness score

**Total: 8 core + 3 conditional + 5 quality indicators = 16 attributes**

### Key Strategy Changes Based on Data

1. **Infer surface from `rutefolger`** - `underlagstype` too sparse (2.8%), but use when present
2. **Include `rutetype`** - Despite 4.0% coverage, valuable when present for route hierarchy
3. **Add `rutebetydning`** - Better coverage (29.5%), provides base priority level
4. **Add `skilting`** - Decent coverage (34.7%), helps with navigation confidence
5. **Quality indicators** - Use metadata (maintainer, accuracy, freshness) to score route quality
6. **Inference-based approach** - For `gradering` and `underlagstype`, infer missing values from `rutefolger` which has excellent 94% coverage

## GraphHopper Configuration Impact

With these attributes, GraphHopper can:

1. **Calculate accurate costs** based on surface, difficulty, and trail type
2. **Prefer marked trails** over unmarked routes
3. **Respect seasonal restrictions** (summer-only routes in winter)
4. **Prioritize main routes** over alternatives
5. **Provide route identification** with names and numbers

## Summary: Data-Driven MVP Approach

**Based on real data analysis, our strategy is:**

1. **Leverage high-completeness attributes** (objtype, rutefolger, merking, trail names)
2. **Infer missing essential data** (surface type from rutefolger, difficulty from context)
3. **Use sparse attributes conditionally** (only when explicitly present, not as defaults)
4. **Prefer better-coverage alternatives** (rutebetydning over rutetype for priority)

**Result:** 8 core + 3 conditional attributes that will provide good routing quality despite data gaps.

**Next step:** Define the exact OSM tag mapping and inference rules for the data pipeline.
