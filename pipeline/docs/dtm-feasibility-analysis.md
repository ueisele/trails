# DTM10 Feasibility Analysis for GitHub Actions & Releases

## Executive Summary

**Can we use DTM10 (20GB) with GitHub Actions?** ❌ **Not directly** - GitHub Actions runners have ~25-29GB free disk space, which is insufficient for 20GB DTM + build artifacts.

**Can we release the GraphHopper graph on GitHub Releases?** ✅ **Yes, with chunking** - GitHub Release assets have a 2GB per-file limit, but support up to 1,000 files per release.

**Recommended Approach:** Use SRTM (current implementation) OR implement a hybrid caching strategy for DTM10.

## GitHub Actions Constraints

### Disk Space Available

| Component | Size | Purpose |
|-----------|------|---------|
| Total OS Disk | 84 GB | Ubuntu runner |
| Preinstalled Software | ~55 GB | System, runtimes, tools |
| **Available for builds** | **~25-29 GB** | **User workspace** |
| Temp disk (/mnt) | 14 GB | Temporary storage |

### Our Pipeline Requirements (with DTM10)

| Component | Size | Location |
|-----------|------|----------|
| Pipeline code | <100 MB | Workspace |
| Trail data (Turrutebasen) | ~50 MB | Cache |
| OSM file output | ~50 MB | Output |
| **DTM10 download** | **~20 GB** | **Cache** |
| GraphHopper JAR | ~100 MB | Cache |
| GraphHopper graph | **~500 MB - 2 GB** | Output |
| Elevation cache (SRTM) | ~500 MB | Cache |
| **Total needed** | **~22-24 GB** | **Various** |

### Assessment

**Feasibility**: ⚠️ **Marginal** - Would consume 90-95% of available space
- Very tight margins
- Risk of out-of-disk errors
- No room for temporary build files
- Java heap space conflicts with disk cache

## GraphHopper Graph Size Analysis

### Expected Graph Size (Norway Trails)

Based on GraphHopper sizing guidelines:

**Input:**
- Trail segments: ~134,000
- OSM ways: ~163,000
- Total trail length: ~50,000 km estimated

**Graph Size Estimates:**

| Scenario | Size | Reasoning |
|----------|------|-----------|
| **Without elevation** | ~200-400 MB | Base graph only |
| **With SRTM (~30m)** | ~400-800 MB | +100-200% for elevation nodes |
| **With DTM10 (10m)** | ~800 MB - 2 GB | +200-300% for denser elevation |

**Why DTM10 increases size:**
- 3x more elevation samples per trail segment (10m vs 30m)
- More elevation nodes stored in graph structure
- Higher precision elevation values (more storage per value)
- Additional interpolation metadata

### Real-World Example

For reference, Germany's complete road network:
- OSM file: ~3 GB
- GraphHopper graph: ~8-10 GB
- With elevation: ~12-15 GB

Norway trails are much smaller (trails only, not all roads), so:
- **Estimated graph size: 500 MB - 1.5 GB** (with DTM10)
- **Estimated graph size: 200-500 MB** (with SRTM)

## GitHub Releases Constraints

### File Size Limits

| Limit | Value | Impact |
|-------|-------|--------|
| **Max file size** | **2 GB per file** | **Must split large files** |
| Max files per release | 1,000 files | Not a concern |
| Total release size | Unlimited | Not a concern |
| Bandwidth | Unlimited | Not a concern |

### Our Release Artifacts (with DTM10)

| Artifact | Estimated Size | GitHub Release Compatible? |
|----------|---------------|----------------------------|
| OSM file (.pbf) | ~50 MB | ✅ Yes (well under 2GB) |
| GraphHopper graph (tarball) | ~800 MB - 2 GB | ⚠️ Marginal (may exceed 2GB) |
| Metadata JSON | <1 MB | ✅ Yes |

### Solutions for >2GB Graph

**Option 1: Split graph tarball**
```bash
# Split into 1GB chunks
tar -czf - graphhopper-data/ | split -b 1G - graph-part-

# Results in:
# graph-part-aa (1GB)
# graph-part-ab (1GB)
# graph-part-ac (remaining)
```

**Option 2: Compress per-directory**
```bash
# GraphHopper graph structure
graphhopper-data/
├── nodes_ch_fastest.dat (largest)
├── edges_ch_fastest.dat (large)
├── properties
└── ...

# Package individually
tar -czf nodes.tar.gz graphhopper-data/nodes*
tar -czf edges.tar.gz graphhopper-data/edges*
tar -czf misc.tar.gz graphhopper-data/properties ...
```

**Option 3: Use XZ compression**
```bash
# Better compression than gzip
tar -cJf graph.tar.xz graphhopper-data/

# Typically 30-40% smaller than .tar.gz
# Estimated size: ~500 MB - 1.2 GB (likely under 2GB)
```

## Alternative Architectures

### Option A: External Storage (Recommended)

**Use external storage for DTM10, keep SRTM in pipeline**

```yaml
# GitHub Actions workflow
steps:
  - name: Check for cached DTM
    uses: actions/cache@v3
    with:
      path: .cache/dtm
      key: dtm10-norway-${{ hashFiles('trail_bounds.txt') }}

  - name: Download DTM if needed
    run: |
      if [ ! -d .cache/dtm ]; then
        # Download from external CDN/S3
        wget https://cdn.example.com/dtm10-norway.tar.gz
        tar -xzf dtm10-norway.tar.gz -C .cache/
      fi
```

**Benefits:**
- ✅ DTM cached across workflow runs
- ✅ Only download when trail bounds change
- ✅ Can use external fast storage (S3, CDN)
- ✅ Doesn't consume GitHub Actions disk space

**Drawbacks:**
- ❌ Requires external infrastructure
- ❌ Additional cost (S3 storage)
- ❌ More complex setup

### Option B: Self-Hosted Runner

**Use self-hosted GitHub Actions runner with more disk**

```yaml
jobs:
  build:
    runs-on: [self-hosted, large-disk]
```

**Benefits:**
- ✅ Full control over disk space (can have TBs)
- ✅ Can cache DTM10 permanently
- ✅ Faster builds (no repeated downloads)
- ✅ Can use SSD for GraphHopper performance

**Drawbacks:**
- ❌ Infrastructure management overhead
- ❌ Security considerations
- ❌ Costs (server hosting)

### Option C: Hybrid Approach (Best Balance)

**Use SRTM by default, offer DTM10 as optional manual build**

```yaml
# Default: SRTM (automatic, weekly)
# Manual: DTM10 (on-demand, self-hosted)

on:
  schedule:
    - cron: '0 6 * * 6'  # Weekly with SRTM
  workflow_dispatch:
    inputs:
      elevation_source:
        type: choice
        options: [srtm, dtm10]
```

**Benefits:**
- ✅ Works within GitHub Actions free tier
- ✅ SRTM "good enough" for most use cases
- ✅ DTM10 available for quality releases
- ✅ Flexible deployment model

## Recommendations

### For GitHub Actions

**Short-term (Recommended):** ✅ **Keep SRTM**
- Uses ~500MB elevation cache (manageable)
- Fits comfortably in GitHub Actions disk space
- 30m resolution sufficient for most routing needs
- Zero external dependencies

**Medium-term (If needed):** Implement **GitHub Actions Cache** for DTM10
```yaml
- uses: actions/cache@v3
  with:
    path: .cache/dtm
    key: dtm10-norway-v1
    restore-keys: dtm10-norway-
```
- Cache persists across runs (7 days minimum)
- Only download once per week (or when cache expires)
- Still risky with 20GB size

**Long-term (Best quality):** Use **self-hosted runner** for DTM10 builds
- Monthly "quality" releases with DTM10
- Weekly "standard" releases with SRTM
- Best of both worlds

### For GitHub Releases

**Current (works now):** OSM + Graph with SRTM
- OSM file: ~50 MB ✅
- Graph tarball: ~300-500 MB ✅
- Total: ~400-600 MB ✅

**If we use DTM10:** Use **XZ compression**
```bash
tar -cJf norway-trails-graph.tar.xz graphhopper-data/
# Estimated: 500 MB - 1.2 GB (likely under 2GB ✅)
```

**If graph exceeds 2GB:** Split into chunks
```bash
tar -czf - graphhopper-data/ | split -b 1800M - graph-chunk-
# Creates: graph-chunk-aa, graph-chunk-ab, etc.
# Each under 2GB ✅
```

## Cost Analysis

### GitHub Actions Free Tier

- **2,000 minutes/month** for free
- **~30-60 minutes per build** with SRTM
- **Supports ~30-40 builds/month** ✅

### With DTM10 on GitHub Actions

- **~60-120 minutes per build** (DTM download + processing)
- **Supports ~15-30 builds/month** ⚠️
- **High risk of running out of disk space** ❌

### Alternative: External Storage

**S3 Pricing Example:**
- Storage: 20GB × $0.023/GB = **$0.46/month**
- Bandwidth: 20GB/week × 4 = 80GB × $0.09/GB = **$7.20/month**
- **Total: ~$8/month**

### Self-Hosted Runner

**Example: Hetzner Cloud**
- CX41: 8 vCPU, 32GB RAM, 240GB SSD = **€15.30/month** (~$17/month)
- Perfect for DTM10 (plenty of disk space)
- Can run 24/7, handle multiple builds

## Conclusion

### DTM10 with GitHub Actions?

**Verdict:** ❌ **Not feasible** without external storage or self-hosted runners

**Reasons:**
1. 20GB DTM + build artifacts exceed ~25-29GB available space
2. Risk of out-of-disk errors during build
3. No room for temporary files or cache
4. Would consume entire monthly free tier

### DTM10 Graph on GitHub Releases?

**Verdict:** ✅ **Yes, feasible** with proper compression

**Strategy:**
1. Use XZ compression (tar.xz) → likely stays under 2GB
2. If exceeds 2GB, split into 1.8GB chunks
3. Include reassembly script in release notes

### Recommended Implementation Path

**Phase 1 (Current):** ✅ **SRTM elevation** (implemented)
- Works perfectly within GitHub Actions
- 30m resolution sufficient for trail routing
- Zero infrastructure overhead
- **Estimated cost:** $0/month

**Phase 2 (Future):** ⏳ **Self-hosted runner for DTM10**
- Monthly "premium" releases with DTM10 (10m resolution)
- Weekly "standard" releases with SRTM (30m resolution)
- Cached DTM10 data for fast builds
- **Estimated cost:** ~$17/month (Hetzner) or ~$8/month (S3 + GitHub Actions)

**Phase 3 (Optional):** ⏳ **Hybrid provider** (DTM10 + SRTM fallback)
- Best quality where available
- Automatic global coverage
- Requires Phase 2 infrastructure

## Decision Matrix

| Factor | SRTM (Current) | DTM10 (GitHub Actions) | DTM10 (Self-Hosted) |
|--------|----------------|------------------------|---------------------|
| **Disk space** | ✅ 500MB | ❌ 20GB | ✅ Unlimited |
| **GitHub Actions** | ✅ Works | ❌ Too tight | ✅ Custom runner |
| **Monthly cost** | ✅ $0 | ❌ Risky | ⚠️ ~$17 |
| **Build time** | ✅ 30-60 min | ❌ 60-120 min | ✅ 30-60 min (cached) |
| **Elevation quality** | ⚠️ 30m | ✅ 10m | ✅ 10m |
| **Maintenance** | ✅ None | ❌ High | ⚠️ Medium |
| **GitHub Release** | ✅ <2GB | ⚠️ 1-2GB | ⚠️ 1-2GB |

### Final Recommendation

**Keep SRTM** for automated weekly releases. The 30m resolution is:
- ✅ Sufficient for hiking trail routing
- ✅ Works perfectly within GitHub free tier
- ✅ Zero infrastructure overhead
- ✅ Proven and reliable

**Only implement DTM10 if:**
- User feedback indicates 30m resolution insufficient
- Willing to pay for self-hosted runner (~$17/month)
- Need for technical trail routing (climbing, steep terrain)

**Current SRTM implementation is the right choice** for an automated, zero-cost pipeline. ✅
