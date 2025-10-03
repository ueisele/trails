"""Release step: Create GitHub Release with pipeline artifacts."""

import hashlib
import json
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from trails.pipeline import PipelineContext, PipelineStep, StepResult, StepStatus


@dataclass
class ReleaseArtifacts:
    """Artifacts to include in release."""

    osm_file: Path
    graph_dir: Path
    build_stats: dict[str, Any]


class CreateReleaseStep(PipelineStep[ReleaseArtifacts, str]):
    """Create GitHub Release with pipeline artifacts.

    This step:
    1. Checks if release is needed (data changed)
    2. Generates release version tag
    3. Packages artifacts (OSM file, graph tarball, metadata)
    4. Creates GitHub Release with notes
    5. Cleans up old releases per retention policy
    """

    def __init__(self, country_code: str = "NO", retention_count: int = 2) -> None:
        """Initialize release step.

        Args:
            country_code: ISO country code
            retention_count: Number of releases to keep
        """
        self.country_code = country_code
        self.retention_count = retention_count

    @property
    def name(self) -> str:
        """Step name."""
        return f"create-release-{self.country_code.lower()}"

    @property
    def description(self) -> str:
        """Step description."""
        return f"Create GitHub Release for {self.country_code}"

    def execute(
        self, context: PipelineContext, input_data: ReleaseArtifacts
    ) -> StepResult[str]:
        """Execute release creation.

        Args:
            context: Pipeline context
            input_data: Release artifacts

        Returns:
            StepResult with release URL
        """
        started_at = datetime.now()

        # Validate inputs
        if not input_data.osm_file.exists():
            return StepResult(
                status=StepStatus.FAILED,
                error=f"OSM file not found: {input_data.osm_file}",
                duration_seconds=0,
                started_at=started_at,
                completed_at=datetime.now(),
            )

        if not input_data.graph_dir.exists():
            return StepResult(
                status=StepStatus.FAILED,
                error=f"Graph directory not found: {input_data.graph_dir}",
                duration_seconds=0,
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Check if gh CLI is available
        if not context.dry_run and not self._check_gh_cli():
            return StepResult(
                status=StepStatus.FAILED,
                error="GitHub CLI (gh) not found. Install from https://cli.github.com/",
                duration_seconds=0,
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Check if release is needed
        try:
            if not self._should_create_release(input_data, context.dry_run):
                completed_at = datetime.now()
                return StepResult(
                    status=StepStatus.SKIPPED,
                    metadata={"reason": "No data changes since last release"},
                    duration_seconds=(completed_at - started_at).total_seconds(),
                    started_at=started_at,
                    completed_at=completed_at,
                )
        except Exception as e:
            # If we can't check, create release anyway (first time)
            print(f"Could not check previous releases: {e}")
            print("Creating release...")

        # Generate version
        version = self._generate_version(input_data)

        # Package artifacts
        try:
            packaged = self._package_artifacts(context, input_data, version)
        except Exception as e:
            return StepResult(
                status=StepStatus.FAILED,
                error=f"Artifact packaging failed: {str(e)}",
                duration_seconds=(datetime.now() - started_at).total_seconds(),
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Generate release notes
        notes = self._generate_release_notes(input_data, version)

        # Create release
        try:
            release_url = self._create_github_release(
                tag=version,
                title=f"{self.country_code} Trail Data {version}",
                notes=notes,
                assets=packaged,
                dry_run=context.dry_run,
            )
        except Exception as e:
            return StepResult(
                status=StepStatus.FAILED,
                error=f"Release creation failed: {str(e)}",
                duration_seconds=(datetime.now() - started_at).total_seconds(),
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Clean up old releases
        if not context.dry_run:
            try:
                self._cleanup_old_releases(keep_count=self.retention_count)
            except Exception as e:
                # Don't fail pipeline if cleanup fails
                print(f"Warning: Cleanup of old releases failed: {e}")

        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        return StepResult(
            status=StepStatus.SUCCESS,
            output=release_url,
            metadata={
                "version": version,
                "release_url": release_url,
                "asset_count": len(packaged),
                "osm_size_mb": input_data.osm_file.stat().st_size / (1024 * 1024),
                "graph_size_mb": self._get_dir_size_mb(input_data.graph_dir),
            },
            duration_seconds=duration,
            started_at=started_at,
            completed_at=completed_at,
        )

    def _check_gh_cli(self) -> bool:
        """Check if GitHub CLI is available.

        Returns:
            True if gh CLI is available
        """
        try:
            result = subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def _should_create_release(self, artifacts: ReleaseArtifacts, dry_run: bool) -> bool:
        """Check if release is needed based on data changes.

        Args:
            artifacts: Release artifacts
            dry_run: If true, always return True

        Returns:
            True if release should be created
        """
        if dry_run:
            return True

        # Calculate hash of current OSM file
        current_hash = self._calculate_file_hash(artifacts.osm_file)

        # Get hash from last release
        try:
            last_release_info = self._get_latest_release_info()
            last_hash = last_release_info.get("osm_hash")

            if last_hash == current_hash:
                print(f"OSM file unchanged (hash: {current_hash[:8]}...)")
                return False  # No changes

            if last_hash:
                print(f"OSM file changed (old: {last_hash[:8]}..., new: {current_hash[:8]}...)")
            else:
                print(f"OSM file changed (new: {current_hash[:8]}...)")
        except Exception:
            # First release or can't check - create it
            print("No previous release found or unable to check")

        return True

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file.

        Args:
            file_path: Path to file

        Returns:
            Hex digest of SHA256 hash
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _get_latest_release_info(self) -> dict[str, Any]:
        """Get information about latest release.

        Returns:
            Dict with release info including osm_hash

        Raises:
            RuntimeError: If unable to get release info
        """
        # Get latest release
        result = subprocess.run(
            ["gh", "release", "view", "--json", "body,tagName"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError("No previous release found")

        release_data = json.loads(result.stdout)

        # Try to extract hash from release body
        body = release_data.get("body", "")
        osm_hash = None

        # Look for hash in body (format: "OSM Hash: abc123...")
        for line in body.split("\n"):
            if "OSM Hash:" in line:
                osm_hash = line.split("OSM Hash:")[1].strip()
                break

        return {
            "tag": release_data.get("tagName"),
            "osm_hash": osm_hash,
        }

    def _generate_version(self, artifacts: ReleaseArtifacts) -> str:
        """Generate release version tag.

        Args:
            artifacts: Release artifacts

        Returns:
            Version string (e.g., "v2025-10-03-geonorge-20251001")
        """
        date = datetime.now().strftime("%Y-%m-%d")
        source = "geonorge"

        # Get data version from build stats
        data_version = artifacts.build_stats.get("version", "unknown")

        return f"v{date}-{source}-{data_version}"

    def _package_artifacts(
        self,
        context: PipelineContext,
        artifacts: ReleaseArtifacts,
        version: str,
    ) -> list[Path]:
        """Package artifacts for release.

        Args:
            context: Pipeline context
            artifacts: Release artifacts
            version: Release version

        Returns:
            List of packaged artifact paths
        """
        output_dir = context.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        packaged: list[Path] = []

        # 1. Copy OSM file
        osm_output = output_dir / f"{self.country_code.lower()}-trails-{version}.osm.pbf"
        shutil.copy(artifacts.osm_file, osm_output)
        packaged.append(osm_output)
        print(f"Packaged OSM file: {osm_output.name} ({osm_output.stat().st_size / 1024 / 1024:.1f} MB)")

        # 2. Compress graph directory
        graph_tarball = output_dir / f"{self.country_code.lower()}-graph-{version}.tar.gz"
        self._create_tarball(artifacts.graph_dir, graph_tarball)
        packaged.append(graph_tarball)
        print(f"Packaged graph: {graph_tarball.name} ({graph_tarball.stat().st_size / 1024 / 1024:.1f} MB)")

        # 3. Generate metadata JSON
        metadata_file = output_dir / f"metadata-{version}.json"
        metadata = {
            "country": self.country_code,
            "version": version,
            "generated_at": datetime.now().isoformat(),
            "statistics": artifacts.build_stats,
            "files": {
                "osm": osm_output.name,
                "graph": graph_tarball.name,
            },
            "osm_hash": self._calculate_file_hash(artifacts.osm_file),
        }
        metadata_file.write_text(json.dumps(metadata, indent=2))
        packaged.append(metadata_file)
        print(f"Generated metadata: {metadata_file.name}")

        return packaged

    def _create_tarball(self, source_dir: Path, output_file: Path) -> None:
        """Create compressed tarball of directory.

        Args:
            source_dir: Directory to compress
            output_file: Output .tar.gz file
        """
        with tarfile.open(output_file, "w:gz") as tar:
            tar.add(source_dir, arcname=source_dir.name)

    def _generate_release_notes(self, artifacts: ReleaseArtifacts, version: str) -> str:
        """Generate release notes with build statistics.

        Args:
            artifacts: Release artifacts
            version: Release version

        Returns:
            Formatted release notes
        """
        stats = artifacts.build_stats

        # Calculate file sizes
        osm_size_mb = artifacts.osm_file.stat().st_size / (1024 * 1024)
        graph_size_mb = self._get_dir_size_mb(artifacts.graph_dir)

        # Generate OSM hash for tracking changes
        osm_hash = self._calculate_file_hash(artifacts.osm_file)

        notes = f"""# {self.country_code} Trail Data Release

## Summary

GraphHopper-ready routing graph generated from Norwegian trail data (Turrutebasen).

## Statistics

- **Trails**: {stats.get('trail_count', 0):,}
- **Trail Segments**: {stats.get('way_count', 0):,}
- **Graph Nodes**: {stats.get('node_count', 0):,}
- **Graph Edges**: {stats.get('edge_count', 0):,}
- **OSM File Size**: {osm_size_mb:.1f} MB
- **Graph Size**: {graph_size_mb:.1f} MB

## Files

- `{self.country_code.lower()}-trails-{version}.osm.pbf` - OSM format trail data
- `{self.country_code.lower()}-graph-{version}.tar.gz` - GraphHopper routing graph
- `metadata-{version}.json` - Build metadata and statistics

## Usage

### With GraphHopper

```bash
# Extract graph
tar -xzf {self.country_code.lower()}-graph-{version}.tar.gz

# Start GraphHopper server (example)
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

## Technical Details

- **OSM Hash**: `{osm_hash}`

---

🤖 Generated with [GraphHopper Trails Pipeline](https://github.com/ueisele/trails)
"""

        return notes

    def _create_github_release(
        self,
        tag: str,
        title: str,
        notes: str,
        assets: list[Path],
        dry_run: bool = False,
    ) -> str:
        """Create GitHub release using gh CLI.

        Args:
            tag: Release tag
            title: Release title
            notes: Release notes
            assets: List of asset files
            dry_run: If true, don't actually create release

        Returns:
            Release URL

        Raises:
            RuntimeError: If release creation fails
        """
        if dry_run:
            print(f"[DRY RUN] Would create release: {tag}")
            print(f"[DRY RUN] Title: {title}")
            print(f"[DRY RUN] Assets: {[a.name for a in assets]}")
            return f"https://github.com/example/repo/releases/tag/{tag}"

        # Write notes to temporary file (safer than passing as argument)
        notes_file = Path(f"/tmp/release-notes-{tag}.md")
        notes_file.write_text(notes)

        try:
            # Create release with gh CLI
            cmd = [
                "gh",
                "release",
                "create",
                tag,
                "--title",
                title,
                "--notes-file",
                str(notes_file),
            ]

            # Add assets
            for asset in assets:
                cmd.append(str(asset))

            print(f"Creating GitHub release: {tag}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                raise RuntimeError(f"gh release create failed: {result.stderr}")

            # Extract release URL from output
            release_url = result.stdout.strip()
            print(f"✅ Release created: {release_url}")

            return release_url

        finally:
            # Clean up notes file
            if notes_file.exists():
                notes_file.unlink()

    def _cleanup_old_releases(self, keep_count: int) -> None:
        """Delete old releases, keeping only the most recent.

        Args:
            keep_count: Number of releases to keep
        """
        print(f"Cleaning up old releases (keeping {keep_count})...")

        # List all releases
        result = subprocess.run(
            ["gh", "release", "list", "--limit", "100"],
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse release list (format: "tag\ttitle\ttype\tpublished")
        releases = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("\t")
                if len(parts) >= 1:
                    releases.append(parts[0])  # Tag name

        # Filter to country-specific releases
        country_prefix = f"v{datetime.now().year}"
        country_releases = [r for r in releases if r.startswith(country_prefix) and self.country_code.lower() in r.lower()]

        # Delete old releases
        if len(country_releases) > keep_count:
            for tag in country_releases[keep_count:]:
                print(f"Deleting old release: {tag}")
                subprocess.run(
                    ["gh", "release", "delete", tag, "--yes", "--cleanup-tag"],
                    check=True,
                )

    def _get_dir_size_mb(self, path: Path) -> float:
        """Calculate directory size in MB.

        Args:
            path: Directory path

        Returns:
            Size in megabytes
        """
        total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        return total / (1024 * 1024)
