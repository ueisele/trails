# Release Step Design

## Overview

The release step packages pipeline outputs and creates GitHub Releases for easy distribution. This is the final step in the automated pipeline.

## Requirements

### Input
- OSM file (PBF or XML) from transform step
- GraphHopper graph directory from build step
- Build metadata (version, date, statistics)

### Output
- GitHub Release with versioned tag
- Packaged artifacts (OSM file, graph tarball)
- Release notes with build statistics
- Asset URLs for download

### Dependencies
- GitHub CLI (`gh`) or GitHub API access
- Git repository with push access
- Release notes template
- Compression tools (tar, gzip)

## Release Strategy

### Versioning

Use date-based versioning with data source version:
```
v{date}-{source}-{version}
```

Examples:
- `v2025-10-03-geonorge-20251001` - October 3, 2025 release with Geonorge data from Oct 1
- `v2025-10-10-geonorge-20251008` - October 10, 2025 release with Geonorge data from Oct 8

### Release Conditions

Only create release if:
1. **Data has changed**: OSM file hash differs from previous release
2. **Build succeeded**: All pipeline steps completed successfully
3. **Validation passed**: Quality checks passed

### Retention Policy

From `config/pipeline.toml`:
- Keep last `retention_count` releases (default: 2)
- Delete older releases automatically
- Preserve tags for history

## Implementation Options

### Option 1: GitHub CLI (Recommended for MVP)

**Pros:**
- Simple command-line interface
- Handles authentication automatically
- Built-in asset upload
- Well-documented

**Cons:**
- Requires `gh` CLI installed
- Less control over release details
- Harder to test

**Implementation:**
```python
import subprocess
from pathlib import Path

def create_release_with_gh(
    tag: str,
    title: str,
    notes: str,
    assets: list[Path]
) -> str:
    """Create GitHub release using gh CLI."""

    # Create release
    cmd = [
        "gh", "release", "create", tag,
        "--title", title,
        "--notes", notes,
    ]

    # Add assets
    for asset in assets:
        cmd.extend([str(asset)])

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise ReleaseError(f"Release creation failed: {result.stderr}")

    return result.stdout.strip()  # Release URL
```

### Option 2: GitHub API via PyGithub

**Pros:**
- More control over release details
- Better error handling
- Easier to test with mocks
- Can query existing releases

**Cons:**
- Requires authentication token
- More complex implementation
- Need to handle uploads manually

**Implementation:**
```python
from github import Github
from pathlib import Path

class GitHubReleaser:
    def __init__(self, token: str, repo: str):
        self.gh = Github(token)
        self.repo = self.gh.get_repo(repo)

    def create_release(
        self,
        tag: str,
        name: str,
        body: str,
        assets: list[Path]
    ) -> str:
        """Create GitHub release via API."""

        # Create release
        release = self.repo.create_git_release(
            tag=tag,
            name=name,
            message=body,
            draft=False,
            prerelease=False
        )

        # Upload assets
        for asset in assets:
            release.upload_asset(
                str(asset),
                content_type="application/octet-stream"
            )

        return release.html_url
```

## Release Step Implementation

### Step Class Structure

```python
from datetime import datetime
from pathlib import Path
from trails.pipeline import PipelineStep, PipelineContext, StepResult, StepStatus

@dataclass
class ReleaseArtifacts:
    """Artifacts to include in release."""
    osm_file: Path
    graph_dir: Path
    build_stats: dict[str, Any]

class CreateReleaseStep(PipelineStep[ReleaseArtifacts, str]):
    """Create GitHub Release with pipeline artifacts."""

    def __init__(
        self,
        country_code: str = "NO",
        retention_count: int = 2
    ) -> None:
        self.country_code = country_code
        self.retention_count = retention_count

    @property
    def name(self) -> str:
        return f"create-release-{self.country_code.lower()}"

    @property
    def description(self) -> str:
        return f"Create GitHub Release for {self.country_code}"

    def execute(
        self,
        context: PipelineContext,
        input_data: ReleaseArtifacts
    ) -> StepResult[str]:
        """Execute release creation."""

        started_at = datetime.now()

        # 1. Check if release needed
        if not self._should_create_release(context, input_data):
            return StepResult(
                status=StepStatus.SKIPPED,
                metadata={"reason": "No data changes since last release"},
                duration_seconds=0,
                started_at=started_at,
                completed_at=datetime.now()
            )

        # 2. Generate release version
        version = self._generate_version(input_data)

        # 3. Package artifacts
        packaged = self._package_artifacts(context, input_data)

        # 4. Generate release notes
        notes = self._generate_release_notes(input_data)

        # 5. Create release
        try:
            release_url = self._create_github_release(
                tag=version,
                title=f"{self.country_code} Trail Data {version}",
                notes=notes,
                assets=packaged,
                dry_run=context.dry_run
            )
        except Exception as e:
            return StepResult(
                status=StepStatus.FAILED,
                error=f"Release creation failed: {str(e)}",
                duration_seconds=(datetime.now() - started_at).total_seconds(),
                started_at=started_at,
                completed_at=datetime.now()
            )

        # 6. Clean up old releases
        if not context.dry_run:
            self._cleanup_old_releases(keep_count=self.retention_count)

        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        return StepResult(
            status=StepStatus.SUCCESS,
            output=release_url,
            metadata={
                "version": version,
                "release_url": release_url,
                "assets": [str(p) for p in packaged],
                "osm_size_mb": input_data.osm_file.stat().st_size / (1024 * 1024),
                "graph_size_mb": self._get_dir_size_mb(input_data.graph_dir),
            },
            duration_seconds=duration,
            started_at=started_at,
            completed_at=completed_at
        )
```

### Key Methods

#### 1. Check if Release Needed

```python
def _should_create_release(
    self,
    context: PipelineContext,
    artifacts: ReleaseArtifacts
) -> bool:
    """Check if release is needed based on data changes."""

    # Calculate hash of current OSM file
    current_hash = self._calculate_file_hash(artifacts.osm_file)

    # Get hash from last release
    try:
        last_release = self._get_latest_release()
        last_hash = last_release.get("osm_hash")

        if last_hash == current_hash:
            return False  # No changes
    except ReleaseNotFoundError:
        pass  # First release, create it

    return True
```

#### 2. Generate Version

```python
def _generate_version(self, artifacts: ReleaseArtifacts) -> str:
    """Generate release version tag."""

    date = datetime.now().strftime("%Y-%m-%d")
    source = "geonorge"

    # Get data version from build stats
    data_version = artifacts.build_stats.get("version", "unknown")

    return f"v{date}-{source}-{data_version}"
```

#### 3. Package Artifacts

```python
def _package_artifacts(
    self,
    context: PipelineContext,
    artifacts: ReleaseArtifacts
) -> list[Path]:
    """Package artifacts for release."""

    output_dir = context.output_dir
    packaged: list[Path] = []

    # 1. Copy OSM file
    osm_output = output_dir / f"{self.country_code.lower()}-trails.osm.pbf"
    shutil.copy(artifacts.osm_file, osm_output)
    packaged.append(osm_output)

    # 2. Compress graph directory
    graph_tarball = output_dir / f"{self.country_code.lower()}-graph.tar.gz"
    self._create_tarball(artifacts.graph_dir, graph_tarball)
    packaged.append(graph_tarball)

    # 3. Generate metadata JSON
    metadata_file = output_dir / "metadata.json"
    metadata = {
        "country": self.country_code,
        "generated_at": datetime.now().isoformat(),
        "statistics": artifacts.build_stats,
        "files": {
            "osm": osm_output.name,
            "graph": graph_tarball.name,
        }
    }
    metadata_file.write_text(json.dumps(metadata, indent=2))
    packaged.append(metadata_file)

    return packaged
```

#### 4. Generate Release Notes

```python
def _generate_release_notes(self, artifacts: ReleaseArtifacts) -> str:
    """Generate release notes with build statistics."""

    stats = artifacts.build_stats

    notes = f"""# {self.country_code} Trail Data Release

## Summary

GraphHopper-ready routing graph generated from Norwegian trail data (Turrutebasen).

## Statistics

- **Trails**: {stats.get('trail_count', 0):,}
- **Trail Segments**: {stats.get('way_count', 0):,}
- **Graph Nodes**: {stats.get('node_count', 0):,}
- **Graph Edges**: {stats.get('edge_count', 0):,}
- **OSM File Size**: {stats.get('osm_size_mb', 0):.1f} MB
- **Graph Size**: {stats.get('graph_size_mb', 0):.1f} MB

## Files

- `{self.country_code.lower()}-trails.osm.pbf` - OSM format trail data
- `{self.country_code.lower()}-graph.tar.gz` - GraphHopper routing graph
- `metadata.json` - Build metadata and statistics

## Usage

### With GraphHopper

```bash
# Extract graph
tar -xzf {self.country_code.lower()}-graph.tar.gz

# Start GraphHopper server
java -jar graphhopper.jar server config.yml
```

### OSM File

The OSM PBF file can be used with:
- GraphHopper for routing
- QGIS for visualization
- osmium tools for processing

## Data Source

- **Provider**: Kartverket / Geonorge
- **Dataset**: Turrutebasen (Norwegian Trails)
- **License**: CC0 1.0 (Public Domain)
- **Version**: {stats.get('version', 'unknown')}
- **Updated**: {stats.get('updated_at', 'unknown')}

## Pipeline

Generated by automated pipeline:
1. Fetch data from Geonorge
2. Validate data quality
3. Transform to OSM format
4. Build GraphHopper graph

---

🤖 Generated with [GraphHopper Trails Pipeline](https://github.com/ueisele/trails)
"""

    return notes
```

#### 5. Create GitHub Release

```python
def _create_github_release(
    self,
    tag: str,
    title: str,
    notes: str,
    assets: list[Path],
    dry_run: bool = False
) -> str:
    """Create GitHub release using gh CLI."""

    if dry_run:
        print(f"[DRY RUN] Would create release: {tag}")
        return f"https://github.com/example/repo/releases/tag/{tag}"

    # Create release with gh CLI
    cmd = [
        "gh", "release", "create", tag,
        "--title", title,
        "--notes", notes,
    ]

    # Add assets
    for asset in assets:
        cmd.append(str(asset))

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False
    )

    if result.returncode != 0:
        raise RuntimeError(f"gh release create failed: {result.stderr}")

    # Extract release URL from output
    return result.stdout.strip()
```

#### 6. Cleanup Old Releases

```python
def _cleanup_old_releases(self, keep_count: int) -> None:
    """Delete old releases, keeping only the most recent."""

    # List all releases
    result = subprocess.run(
        ["gh", "release", "list", "--limit", "100"],
        capture_output=True,
        text=True,
        check=True
    )

    # Parse release list
    releases = []
    for line in result.stdout.strip().split("\n"):
        if line:
            parts = line.split("\t")
            if len(parts) >= 1:
                releases.append(parts[0])  # Tag name

    # Filter to country-specific releases
    country_releases = [
        r for r in releases
        if r.startswith(f"v") and self.country_code.lower() in r.lower()
    ]

    # Delete old releases
    if len(country_releases) > keep_count:
        for tag in country_releases[keep_count:]:
            print(f"Deleting old release: {tag}")
            subprocess.run(
                ["gh", "release", "delete", tag, "--yes"],
                check=True
            )
```

## Testing Strategy

### Unit Tests

```python
def test_release_step_initialization():
    """Test release step initializes correctly."""
    step = CreateReleaseStep(country_code="NO", retention_count=2)

    assert step.country_code == "NO"
    assert step.retention_count == 2
    assert step.name == "create-release-no"

def test_generate_version():
    """Test version generation."""
    step = CreateReleaseStep(country_code="NO")

    artifacts = ReleaseArtifacts(
        osm_file=Path("trails.osm.pbf"),
        graph_dir=Path("graph/"),
        build_stats={"version": "20251001"}
    )

    version = step._generate_version(artifacts)

    assert version.startswith("v2025-")
    assert "geonorge" in version
    assert "20251001" in version

def test_should_create_release_no_previous():
    """Test release creation when no previous release exists."""
    step = CreateReleaseStep(country_code="NO")

    # Mock no previous release
    with patch.object(step, "_get_latest_release", side_effect=ReleaseNotFoundError):
        assert step._should_create_release(context, artifacts) is True

def test_should_create_release_data_changed():
    """Test release creation when data has changed."""
    step = CreateReleaseStep(country_code="NO")

    # Mock previous release with different hash
    with patch.object(step, "_get_latest_release", return_value={"osm_hash": "abc123"}):
        with patch.object(step, "_calculate_file_hash", return_value="xyz789"):
            assert step._should_create_release(context, artifacts) is True

def test_should_create_release_no_changes():
    """Test release skipped when no data changes."""
    step = CreateReleaseStep(country_code="NO")

    # Mock previous release with same hash
    with patch.object(step, "_get_latest_release", return_value={"osm_hash": "abc123"}):
        with patch.object(step, "_calculate_file_hash", return_value="abc123"):
            assert step._should_create_release(context, artifacts) is False

def test_package_artifacts():
    """Test artifact packaging."""
    step = CreateReleaseStep(country_code="NO")

    packaged = step._package_artifacts(context, artifacts)

    assert len(packaged) == 3  # OSM, graph tarball, metadata
    assert packaged[0].suffix == ".pbf"
    assert packaged[1].suffix == ".gz"
    assert packaged[2].name == "metadata.json"

def test_generate_release_notes():
    """Test release notes generation."""
    step = CreateReleaseStep(country_code="NO")

    notes = step._generate_release_notes(artifacts)

    assert "# NO Trail Data Release" in notes
    assert "Statistics" in notes
    assert "Usage" in notes
    assert "CC0 1.0" in notes
```

### Integration Tests

- Test with mock GitHub CLI
- Test with real artifacts (small sample)
- Test cleanup with multiple releases
- Test dry-run mode

## Error Handling

### Common Errors

1. **gh CLI not installed**: Check before running, provide helpful error
2. **No authentication**: Check `gh auth status` first
3. **Network issues**: Retry with exponential backoff
4. **Asset upload failure**: Retry individual assets
5. **Disk space**: Check before packaging

### Recovery Strategies

- **Partial upload**: Delete failed release and retry
- **Cleanup failure**: Log warning but don't fail pipeline
- **Network timeout**: Increase timeout for large files

## Configuration

From `config/pipeline.toml`:

```toml
[pipeline.release]
retention_count = 2  # Keep last 2 releases
name_format = "v{date}-{source}-{version}"
```

## Next Steps

1. Implement `CreateReleaseStep` class
2. Add artifact packaging methods
3. Integrate gh CLI commands
4. Write comprehensive tests
5. Integrate into main pipeline
6. Test with real GitHub repository
7. Document release process for users

## References

- [GitHub CLI Documentation](https://cli.github.com/manual/gh_release_create)
- [GitHub Releases API](https://docs.github.com/en/rest/releases/releases)
- [PyGithub Documentation](https://pygithub.readthedocs.io/)
