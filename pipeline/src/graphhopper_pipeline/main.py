"""Main entry point for the GraphHopper pipeline."""

import argparse
import sys
from pathlib import Path

from graphhopper_pipeline.config import load_country_config, load_pipeline_config
from graphhopper_pipeline.steps import FetchTrailsStep
from trails.pipeline import PipelineContext


def main() -> int:
    """Run the GraphHopper data pipeline.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(description="GraphHopper trail data pipeline")
    parser.add_argument(
        "--country",
        default="NO",
        help="Country code to process (default: NO)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no actual changes)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to pipeline config file",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        help="Working directory for temporary files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for final artifacts",
    )

    args = parser.parse_args()

    # Load configuration
    pipeline_config = load_pipeline_config(args.config)
    country_config = load_country_config(args.country)

    print(f"GraphHopper Pipeline v{pipeline_config.version}")
    print(f"Processing: {country_config.name} ({country_config.code})")
    print(f"Dry run: {args.dry_run}")
    print("=" * 60)

    # Create pipeline context
    work_dir = args.work_dir or Path.cwd() / pipeline_config.work_dir
    output_dir = args.output_dir or Path.cwd() / pipeline_config.output_dir

    context = PipelineContext(
        config={"pipeline": pipeline_config, "country": country_config},
        work_dir=work_dir,
        output_dir=output_dir,
        cache_dir=pipeline_config.cache_dir,
        dry_run=args.dry_run,
    )

    print(f"\nWork directory: {context.work_dir}")
    print(f"Output directory: {context.output_dir}")
    print(f"Cache directory: {context.cache_dir}")
    print()

    # Execute fetch step
    print("Step 1: Fetch trail data")
    print("-" * 60)

    fetch_step = FetchTrailsStep(country_code=args.country)

    # Check if should skip
    should_skip, skip_reason = fetch_step.should_skip(context, None)
    if should_skip:
        print(f"⏭️  Skipping: {skip_reason}")
        return 0

    # Execute fetch
    result = fetch_step.execute(context, None)

    if result.failed:
        print(f"❌ Fetch failed: {result.error}")
        return 1

    print(f"✅ Fetch succeeded in {result.duration_seconds:.1f}s")
    print(f"   Trails: {result.metadata.get('trail_count', 0):,}")
    print(f"   Attributes: {result.metadata.get('attribute_count', 0):,}")
    print(f"   Version: {result.metadata.get('version', 'unknown')}")
    print()

    # TODO: Add more pipeline steps here
    # - Transform to OSM
    # - Validate data
    # - Build GraphHopper graph
    # - Create release

    print("=" * 60)
    print("Pipeline execution completed successfully!")
    print("\nNote: Additional steps (transform, build, release) not yet implemented")

    return 0


if __name__ == "__main__":
    sys.exit(main())
