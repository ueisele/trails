# Error Handling & Data Validation Strategy

## Pipeline Error Handling Rules

### A) Data Fetch Failures (Geonorge down or network issues)

**Strategy: Retry with exponential backoff**

- **Retry count**: 5 attempts
- **Initial backoff**: 5 minutes
- **Backoff multiplier**: 2x (double each retry)
- **Maximum backoff**: 1 hour (cap)
- **Total maximum wait**: ~2 hours (5min + 10min + 20min + 40min + 60min)

**Retry schedule:**
1. Attempt 1: Immediate
2. Attempt 2: After 5 minutes
3. Attempt 3: After 10 minutes (cumulative: 15 min)
4. Attempt 4: After 20 minutes (cumulative: 35 min)
5. Attempt 5: After 40 minutes (cumulative: 75 min)
6. Attempt 6: After 60 minutes (capped, cumulative: 135 min)

**Implementation:**
```python
import time

def fetch_with_retry(url, max_retries=5, initial_backoff=300, max_backoff=3600):
    """Fetch data with exponential backoff retry."""
    backoff = initial_backoff

    for attempt in range(max_retries + 1):
        try:
            return fetch_data(url)
        except Exception as e:
            if attempt == max_retries:
                raise Exception(f"Failed after {max_retries + 1} attempts") from e

            wait_time = min(backoff, max_backoff)
            print(f"Attempt {attempt + 1} failed. Retrying in {wait_time/60:.1f} minutes...")
            time.sleep(wait_time)
            backoff *= 2  # Double for next attempt
```

**On final failure:**
- ❌ Fail entire pipeline
- 📧 Send failure notification
- 📝 Log detailed error information
- 🔄 Keep previous release available

---

### B) Data Validation

**Strategy: Checksum validation only (when provided)**

**Validation steps:**
1. **If Geonorge provides checksum (MD5/SHA256)**:
   - Verify downloaded file matches checksum
   - Reject and retry if mismatch

2. **If NO checksum provided**:
   - Accept downloaded file
   - Rely on later quality checks to catch issues

**Rationale:**
- Geonorge is authoritative source - trust their data format
- Schema/geometry validation happens during quality checks (see section F)
- Premature validation may reject valid but differently-structured data

---

### C) OSM Conversion Failures

**Strategy: Fail entire pipeline**

**Behavior:**
- ❌ Any conversion error stops the pipeline
- 📝 Log which features/attributes caused failure
- 🚫 Do NOT skip problematic features
- 🔄 Do NOT release partial/incomplete data

**Rationale:**
- Missing trail segments would create disconnected routing graphs
- Silent failures could go unnoticed
- Better to fix issues than ship broken data

**Failure scenarios:**
- Invalid geometry that can't convert to OSM
- Missing required attributes (objtype, geometry)
- Coordinate transformation errors
- OSM format generation errors

---

### D) GraphHopper Graph Building Failures

**Strategy: Fail entire pipeline**

**Behavior:**
- ❌ Graph build failure stops the pipeline
- 🚫 Do NOT release source OSM without graph
- 📝 Log GraphHopper error messages
- 🔍 Include diagnostics (Java heap size, file size, error trace)

**Rationale:**
- Unusable release without working graph
- Graph build failure indicates data problems
- Forces us to investigate and fix root cause

**Common failure causes:**
- Invalid OSM syntax
- Memory issues (adjust Java heap)
- Disconnected graph components
- Invalid routing profiles

---

### E) Notifications

**Notification Matrix:**

| Event | GitHub Actions Summary | Details |
|-------|----------------------|---------|
| ✅ **Pipeline success** | ✅ Yes | Release URL, data stats, validation results |
| ⚠️ **No changes detected** | ✅ Yes (info) | Source timestamp, reason for skip |
| ⚠️ **Data validation warnings** | ✅ Yes | Which checks failed, severity, counts |
| ❌ **Pipeline failure** | ✅ Yes | Error message, failed step, retry count |
| ❌ **Fetch retry attempt** | ✅ Yes (verbose mode) | Attempt number, backoff time, error |

**Notification channels:**
1. **GitHub Actions Summary** (always)
   - Job summary with emoji status
   - Links to logs
   - Key metrics and stats

2. **GitHub Issues** (on failure only)
   - Auto-create issue with label `pipeline-failure`
   - Include full error logs
   - Close automatically on next success

**Optional future enhancements:**
- Email notifications
- Slack/Discord webhooks
- Metrics dashboard

**NOT included (too noisy):**
- ❌ Pipeline start notifications
- ❌ Individual step completions
- ❌ Successful retry attempts

---

### F) Data Quality Checks

**All checks must pass before release:**

#### 1. ✅ Trail Count Validation
**Rule:** Trail count must not drop >20% from previous release

```python
def validate_trail_count(new_count, previous_count):
    """Ensure trail count hasn't dropped significantly."""
    if previous_count == 0:
        return True  # First release

    drop_percentage = (previous_count - new_count) / previous_count * 100

    if drop_percentage > 20:
        raise ValidationError(
            f"Trail count dropped {drop_percentage:.1f}% "
            f"({previous_count:,} → {new_count:,}). Possible data loss."
        )
    return True
```

**Purpose:** Detect accidental data loss or incomplete downloads

---

#### 2. ✅ Bounding Box Validation
**Rule:** Bounding box must not change drastically

```python
def validate_bounding_box(new_bbox, previous_bbox, max_shift_km=50):
    """Ensure we're still in Norway."""
    # Norway expected bounds (approximate)
    NORWAY_BBOX = {
        'min_lat': 57.0,  # Lindesnes
        'max_lat': 71.5,  # Nordkapp
        'min_lon': 4.0,   # Western coast
        'max_lon': 31.5,  # Eastern border
    }

    # Check if new data is within Norway
    if not bbox_within(new_bbox, NORWAY_BBOX):
        raise ValidationError("Bounding box outside Norway - wrong country?")

    # Check if center hasn't shifted more than max_shift_km
    if previous_bbox:
        center_shift = calculate_distance(
            get_center(new_bbox),
            get_center(previous_bbox)
        )
        if center_shift > max_shift_km:
            raise ValidationError(
                f"Bounding box center shifted {center_shift:.1f}km "
                f"(max: {max_shift_km}km)"
            )

    return True
```

**Purpose:** Detect wrong dataset or coordinate transformation errors

---

#### 3. ✅ Geometry ID Uniqueness
**Rule:** No duplicate `local_id` values (geometry segment IDs)

**IMPORTANT:** Do NOT check `trail_number` uniqueness - trails have multiple segments!

```python
def validate_unique_geometry_ids(gdf):
    """Ensure each geometry segment has unique ID."""
    duplicate_ids = gdf[gdf.duplicated(subset=['local_id'], keep=False)]

    if len(duplicate_ids) > 0:
        raise ValidationError(
            f"Found {len(duplicate_ids):,} duplicate local_id values. "
            f"Examples: {duplicate_ids['local_id'].head().tolist()}"
        )

    return True
```

**Analysis findings:**
- ✅ `local_id`: 134,047 unique for 134,047 segments (100% unique) - CHECK THIS
- ✅ `trail_number`: 9,985 unique for 163,558 records - DO NOT CHECK (trails have multiple segments)
- Example: "Pilegrimsleden" has 2,218 segments sharing the same `trail_number`

**Purpose:** Detect data corruption or processing errors

---

#### 4. ✅ Geometry Validation
**Rule:** All geometries must be valid

```python
def validate_geometries(gdf):
    """Ensure all geometries are valid."""
    invalid = gdf[~gdf.geometry.is_valid]

    if len(invalid) > 0:
        # Attempt to fix with buffer(0)
        gdf.geometry = gdf.geometry.buffer(0)
        invalid_after_fix = gdf[~gdf.geometry.is_valid]

        if len(invalid_after_fix) > 0:
            raise ValidationError(
                f"Found {len(invalid_after_fix):,} invalid geometries "
                f"that couldn't be auto-fixed"
            )

    # Check for empty geometries
    empty = gdf[gdf.geometry.is_empty]
    if len(empty) > 0:
        raise ValidationError(f"Found {len(empty):,} empty geometries")

    return True
```

**Purpose:** Prevent GraphHopper errors from invalid geometries

---

#### 5. ✅ GraphHopper Routing Test
**Rule:** Must successfully route between test points

```python
def validate_routing(graphhopper_dir, test_points):
    """Test GraphHopper can route between known trail points."""
    test_routes = [
        {
            'name': 'Oslo to Frognerseteren',
            'from': [59.9139, 10.7522],  # Oslo central
            'to': [59.9850, 10.6694],    # Frognerseteren
        },
        {
            'name': 'Preikestolen trail',
            'from': [58.9868, 6.1900],   # Parking
            'to': [58.9864, 6.1903],     # Preikestolen
        },
        # Add more known trails
    ]

    for route in test_routes:
        try:
            result = graphhopper_route(
                graphhopper_dir,
                route['from'],
                route['to']
            )

            if result.distance == 0:
                raise ValidationError(
                    f"Route '{route['name']}' returned zero distance"
                )

            if result.time == 0:
                raise ValidationError(
                    f"Route '{route['name']}' returned zero time"
                )

        except Exception as e:
            raise ValidationError(
                f"Failed to route '{route['name']}': {e}"
            )

    return True
```

**Purpose:** Ensure routing actually works, not just that graph builds

**Test points selection:**
- Use well-known Norwegian trails
- Include different regions (Oslo, Rogaland, Troms, etc.)
- Test both easy and difficult trails
- Include popular destinations (Preikestolen, Trolltunga, etc.)

---

## Validation Workflow

```
1. Download data
   ↓
2. Checksum validation (if provided)
   ↓ PASS
3. Convert to OSM
   ↓ PASS
4. Quality checks:
   ├── Trail count (-20% max)
   ├── Bounding box (Norway)
   ├── Unique geometry IDs
   └── Valid geometries
   ↓ ALL PASS
5. Build GraphHopper graph
   ↓ PASS
6. Routing tests (known trails)
   ↓ PASS
7. Create GitHub Release
   ↓
8. Success notification
```

**Any failure at any step → Fail entire pipeline**

---

## Error Recovery

### Manual Intervention Required

When pipeline fails:

1. **Check GitHub Actions logs** - Identify failed step
2. **Review error message** - Understand root cause
3. **Check GitHub Issue** - Auto-created with details
4. **Fix issue**:
   - Code bug → Fix and commit
   - Data issue → Report to Geonorge
   - Validation too strict → Adjust thresholds
5. **Trigger manual run** - Test fix
6. **Close issue** - Once resolved

### Automatic Recovery

Pipeline will automatically:
- ✅ Retry transient failures (network)
- ✅ Skip release if no data changes
- ✅ Keep previous release available
- ✅ Auto-close issues on next success

---

## Monitoring & Metrics

Track over time:
- Pipeline success rate
- Average run duration
- Data source update frequency
- Trail count trends
- Validation warning trends
- GraphHopper graph size trends

**Future:** Dashboard showing pipeline health and data quality metrics
