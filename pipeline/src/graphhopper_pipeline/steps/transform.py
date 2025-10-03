"""Transform step: Convert trail data to OSM format."""

from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd

from trails.pipeline import PipelineContext, PipelineStep, StepResult, StepStatus


class TransformToOSMStep(PipelineStep[tuple[gpd.GeoDataFrame, pd.DataFrame], Path]):
    """Transform trail data to OSM format.

    Converts Turrutebasen data to OSM PBF format suitable for GraphHopper.

    This is a complex step that involves:
    1. Joining spatial and attribute data
    2. Mapping Turrutebasen attributes to OSM tags
    3. Inferring missing attributes
    4. Generating OSM XML
    5. Converting to PBF format
    """

    def __init__(self, country_code: str = "NO") -> None:
        """Initialize transform step.

        Args:
            country_code: ISO country code for configuration
        """
        self.country_code = country_code

    @property
    def name(self) -> str:
        """Step name."""
        return f"transform-to-osm-{self.country_code.lower()}"

    @property
    def description(self) -> str:
        """Step description."""
        return f"Transform {self.country_code} trail data to OSM format"

    def validate_input(self, input_data: tuple[gpd.GeoDataFrame, pd.DataFrame]) -> list[str]:
        """Validate input data.

        Args:
            input_data: Tuple of (spatial_gdf, attributes_df)

        Returns:
            List of validation errors
        """
        errors = []

        spatial_gdf, attributes_df = input_data

        # Check spatial data
        if spatial_gdf.empty:
            errors.append("Spatial GeoDataFrame is empty")

        if "geometry" not in spatial_gdf.columns:
            errors.append("Spatial GeoDataFrame missing 'geometry' column")

        if "local_id" not in spatial_gdf.columns:
            errors.append("Spatial GeoDataFrame missing 'local_id' column")

        # Check attribute data
        if attributes_df.empty:
            errors.append("Attributes DataFrame is empty")

        if "hiking_trail_fk" not in attributes_df.columns:
            errors.append("Attributes DataFrame missing 'hiking_trail_fk' column")

        # Check relationship
        if not errors:
            spatial_ids = set(spatial_gdf["local_id"])
            attr_fks = set(attributes_df["hiking_trail_fk"])

            orphaned = attr_fks - spatial_ids
            if len(orphaned) > 0:
                errors.append(f"{len(orphaned)} attribute records reference non-existent geometries")

        return errors

    def execute(
        self, context: PipelineContext, input_data: tuple[gpd.GeoDataFrame, pd.DataFrame]
    ) -> StepResult[Path]:
        """Execute the transform step.

        Args:
            context: Pipeline context
            input_data: Tuple of (spatial_gdf, attributes_df)

        Returns:
            StepResult containing path to OSM PBF file
        """
        started_at = datetime.now()

        try:
            spatial_gdf, attributes_df = input_data

            # TODO: Implement OSM conversion
            # This is a placeholder for the complex transformation logic
            # Full implementation would include:
            # 1. Load country configuration for mapping rules
            # 2. Join spatial and attribute data
            # 3. Apply attribute mapping (Turrutebasen -> OSM tags)
            # 4. Infer missing attributes (e.g., surface from rutefolger)
            # 5. Generate OSM XML with proper structure
            # 6. Convert XML to PBF using osmium/osmconvert

            # For now, return a placeholder result
            output_path = context.work_dir / "trails.osm.pbf"

            return StepResult(
                status=StepStatus.FAILED,
                error="Transform step not yet implemented - requires OSM conversion logic",
                metadata={
                    "input_trail_count": len(spatial_gdf),
                    "input_attribute_count": len(attributes_df),
                    "output_path": str(output_path),
                },
                started_at=started_at,
                completed_at=datetime.now(),
            )

        except Exception as e:
            completed_at = datetime.now()
            duration = (completed_at - started_at).total_seconds()

            return StepResult(
                status=StepStatus.FAILED,
                error=f"Transform failed: {e}",
                duration_seconds=duration,
                started_at=started_at,
                completed_at=completed_at,
            )
