"""Main entry point for the GraphHopper pipeline."""

import argparse
import sys
from pathlib import Path

from trails.pipeline import PipelineContext

from graphhopper_pipeline.config import load_country_config, load_pipeline_config
from graphhopper_pipeline.steps import BuildGraphHopperStep, FetchTrailsStep, TransformToOSMStep, ValidateTrailDataStep


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

    # Store fetch output
    fetch_output = result.output
    if fetch_output is None:
        print("❌ Fetch returned no data")
        return 1

    # Execute validate step
    print("Step 2: Validate trail data")
    print("-" * 60)

    validate_step = ValidateTrailDataStep(
        country_code=args.country,
        expected_trail_count=country_config.expected_trail_count,
    )

    validate_result = validate_step.execute(context, fetch_output)

    if validate_result.failed:
        print(f"❌ Validation failed: {validate_result.error}")
        return 1

    print(f"✅ Validation succeeded in {validate_result.duration_seconds:.1f}s")
    print(f"   Issues: {validate_result.metadata.get('issues_count', 0)}")
    print(f"   Warnings: {validate_result.metadata.get('warnings_count', 0)}")
    if validate_result.metadata.get("warnings"):
        for warning in validate_result.metadata["warnings"]:
            print(f"   ⚠️  {warning}")
    print()

    # Store validated output
    validated_output = validate_result.output
    if validated_output is None:
        print("❌ Validation returned no data")
        return 1

    # Execute transform step
    print("Step 3: Transform to OSM")
    print("-" * 60)

    transform_step = TransformToOSMStep(country_code=args.country)

    transform_result = transform_step.execute(context, validated_output)

    if transform_result.failed:
        print(f"❌ Transform failed: {transform_result.error}")
        return 1

    print(f"✅ Transform succeeded in {transform_result.duration_seconds:.1f}s")
    print(f"   Input trails: {transform_result.metadata.get('input_trail_count', 0):,}")
    print(f"   OSM ways generated: {transform_result.metadata.get('way_count', 0):,}")
    print(f"   Output format: {transform_result.metadata.get('output_format', 'unknown')}")
    print(f"   Output file: {transform_result.output}")
    print()

    # Store transform output
    transform_output = transform_result.output
    if transform_output is None:
        print("❌ Transform returned no output file")
        return 1

    # Execute build step
    print("Step 4: Build GraphHopper graph")
    print("-" * 60)

    build_step = BuildGraphHopperStep(
        country_code=args.country,
        graphhopper_version=pipeline_config.graphhopper_version,
    )

    build_result = build_step.execute(context, transform_output)

    if build_result.failed:
        print(f"❌ Build failed: {build_result.error}")
        return 1

    print(f"✅ Build succeeded in {build_result.duration_seconds:.1f}s")
    print(f"   Graph size: {build_result.metadata.get('graph_size_mb', 0):.1f} MB")
    print(f"   Nodes: {build_result.metadata.get('node_count', 0):,}")
    print(f"   Edges: {build_result.metadata.get('edge_count', 0):,}")
    if "import_time_seconds" in build_result.metadata:
        print(f"   Import time: {build_result.metadata['import_time_seconds']:.1f}s")
    print(f"   Graph directory: {build_result.output}")
    print()

    # TODO: Add release step
    # - Package graph and OSM files
    # - Create GitHub release
    # - Upload artifacts

    print("=" * 60)
    print("Pipeline execution completed successfully!")
    print("\nGenerated files:")
    print(f"  - OSM: {transform_output}")
    print(f"  - Graph: {build_result.output}")
    print("\nNote: Release step not yet implemented")

    return 0


if __name__ == "__main__":
    sys.exit(main())
