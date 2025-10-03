"""Fetch step: Download trail data from sources."""

from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd

from trails.io.sources.geonorge import Source as GeonorgeSource
from trails.io.sources.language import Language
from trails.pipeline import PipelineContext, PipelineStep, StepResult, StepStatus


class FetchTrailsStep(PipelineStep[None, tuple[gpd.GeoDataFrame, pd.DataFrame]]):
    """Fetch trail data from Geonorge.

    Downloads the latest Turrutebasen data and extracts:
    - Spatial layer (geometries)
    - Attribute table (trail information)
    """

    def __init__(self, country_code: str = "NO") -> None:
        """Initialize fetch step.

        Args:
            country_code: ISO country code to fetch data for
        """
        self.country_code = country_code

    @property
    def name(self) -> str:
        """Step name."""
        return f"fetch-trails-{self.country_code.lower()}"

    @property
    def description(self) -> str:
        """Step description."""
        return f"Fetch trail data from Geonorge for {self.country_code}"

    def should_skip(self, context: PipelineContext, input_data: None) -> tuple[bool, str | None]:
        """Check if we should skip fetching.

        Args:
            context: Pipeline context
            input_data: Input data (not used)

        Returns:
            Tuple of (should_skip, reason)
        """
        # Check if data is already cached and recent
        cache_dir = context.cache_dir
        if cache_dir:
            # Check for recent cache (less than 7 days old)
            cache_marker = cache_dir / f"turrutebasen_{self.country_code.lower()}_downloaded.txt"
            if cache_marker.exists():
                mtime = datetime.fromtimestamp(cache_marker.stat().st_mtime)
                age_days = (datetime.now() - mtime).days

                if age_days < 7:
                    return True, f"Data cached {age_days} days ago, skipping fetch"

        return False, None

    def execute(self, context: PipelineContext, input_data: None) -> StepResult[tuple[gpd.GeoDataFrame, pd.DataFrame]]:
        """Execute the fetch step.

        Args:
            context: Pipeline context
            input_data: No input required

        Returns:
            StepResult containing (spatial_gdf, attributes_df)
        """
        started_at = datetime.now()

        try:
            # Initialize Geonorge source
            cache_dir_str = str(context.cache_dir) if context.cache_dir else ".cache"
            source = GeonorgeSource(cache_dir=cache_dir_str)

            # Load Turrutebasen data with English translations
            trail_data = source.load_turrutebasen(language=Language.EN)

            # Extract spatial and attribute layers
            spatial_layer_name = "hiking_trail_centerline"
            attribute_table_name = "hiking_trail_info_table"

            if spatial_layer_name not in trail_data.spatial_layers:
                return StepResult(
                    status=StepStatus.FAILED,
                    error=f"Expected spatial layer '{spatial_layer_name}' not found",
                )

            if attribute_table_name not in trail_data.attribute_tables:
                return StepResult(
                    status=StepStatus.FAILED,
                    error=f"Expected attribute table '{attribute_table_name}' not found",
                )

            spatial_gdf = trail_data.spatial_layers[spatial_layer_name]
            attributes_df = trail_data.attribute_tables[attribute_table_name]

            # Convert to WGS84 (EPSG:4326) for OSM
            if spatial_gdf.crs and spatial_gdf.crs.to_epsg() != 4326:
                spatial_gdf = spatial_gdf.to_crs("EPSG:4326")

            # Mark as downloaded
            if context.cache_dir:
                cache_marker = context.cache_dir / f"turrutebasen_{self.country_code.lower()}_downloaded.txt"
                cache_marker.write_text(f"Downloaded at {datetime.now().isoformat()}")

            completed_at = datetime.now()
            duration = (completed_at - started_at).total_seconds()

            return StepResult(
                status=StepStatus.SUCCESS,
                output=(spatial_gdf, attributes_df),
                metadata={
                    "source": "Geonorge Turrutebasen",
                    "version": trail_data.version,
                    "trail_count": len(spatial_gdf),
                    "attribute_count": len(attributes_df),
                    "source_crs": str(trail_data.crs),
                    "output_crs": "EPSG:4326",
                },
                duration_seconds=duration,
                started_at=started_at,
                completed_at=completed_at,
            )

        except Exception as e:
            completed_at = datetime.now()
            duration = (completed_at - started_at).total_seconds()

            return StepResult(
                status=StepStatus.FAILED,
                error=f"Failed to fetch trail data: {e}",
                duration_seconds=duration,
                started_at=started_at,
                completed_at=completed_at,
            )
