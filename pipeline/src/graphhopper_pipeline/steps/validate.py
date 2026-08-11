"""Validation step: Verify data quality before building GraphHopper graph."""

from datetime import datetime

import geopandas as gpd
import pandas as pd
from trails.pipeline import PipelineContext, PipelineStep, StepResult, StepStatus


class ValidateTrailDataStep(PipelineStep[tuple[gpd.GeoDataFrame, pd.DataFrame], tuple[gpd.GeoDataFrame, pd.DataFrame]]):
    """Validate trail data quality.

    Performs quality checks on trail data to ensure it's suitable for
    GraphHopper graph generation:
    - Geometry validity
    - Unique identifiers
    - Bounding box sanity check
    - Trail count sanity check
    - Required fields present
    """

    def __init__(self, country_code: str = "NO", expected_trail_count: int | None = None) -> None:
        """Initialize validation step.

        Args:
            country_code: ISO country code for bounds checking
            expected_trail_count: Expected trail count (for sanity check)
        """
        self.country_code = country_code
        self.expected_trail_count = expected_trail_count

    @property
    def name(self) -> str:
        """Step name."""
        return f"validate-data-{self.country_code.lower()}"

    @property
    def description(self) -> str:
        """Step description."""
        return f"Validate {self.country_code} trail data quality"

    def execute(
        self, context: PipelineContext, input_data: tuple[gpd.GeoDataFrame, pd.DataFrame]
    ) -> StepResult[tuple[gpd.GeoDataFrame, pd.DataFrame]]:
        """Execute validation.

        Args:
            context: Pipeline context
            input_data: Tuple of (spatial_gdf, attributes_df)

        Returns:
            StepResult with validation results
        """
        started_at = datetime.now()
        spatial_gdf, attributes_df = input_data

        issues: list[str] = []
        warnings: list[str] = []

        # 1. Check geometry validity
        invalid_geoms = (~spatial_gdf.geometry.is_valid).sum()
        if invalid_geoms > 0:
            issues.append(f"Found {invalid_geoms} invalid geometries")

        empty_geoms = spatial_gdf.geometry.is_empty.sum()
        if empty_geoms > 0:
            issues.append(f"Found {empty_geoms} empty geometries")

        # 2. Check unique identifiers
        if "local_id" in spatial_gdf.columns:
            duplicate_ids = spatial_gdf["local_id"].duplicated().sum()
            if duplicate_ids > 0:
                issues.append(f"Found {duplicate_ids} duplicate local_ids")
        else:
            issues.append("Missing required column: local_id")

        # 3. Check foreign key integrity
        if "hiking_trail_fk" in attributes_df.columns and "local_id" in spatial_gdf.columns:
            spatial_ids = set(spatial_gdf["local_id"])
            attr_fks = set(attributes_df["hiking_trail_fk"])

            orphaned_fks = attr_fks - spatial_ids
            if len(orphaned_fks) > 0:
                issues.append(f"{len(orphaned_fks)} attribute records reference non-existent geometries")

            unreferenced_ids = spatial_ids - attr_fks
            if len(unreferenced_ids) > 0:
                warnings.append(f"{len(unreferenced_ids)} geometries have no attribute data")

        # 4. Check bounding box
        if self.country_code == "NO" and spatial_gdf.crs:
            # Expected Norway bounds (EPSG:4326)
            bounds = spatial_gdf.total_bounds  # [minx, miny, maxx, maxy]

            expected_bounds = {
                "min_lon": 4.0,
                "max_lon": 32.0,
                "min_lat": 57.0,
                "max_lat": 72.0,
            }

            if not (expected_bounds["min_lon"] <= bounds[0] <= expected_bounds["max_lon"]):
                issues.append(f"Min longitude {bounds[0]:.2f} outside expected range")

            if not (expected_bounds["min_lon"] <= bounds[2] <= expected_bounds["max_lon"]):
                issues.append(f"Max longitude {bounds[2]:.2f} outside expected range")

            if not (expected_bounds["min_lat"] <= bounds[1] <= expected_bounds["max_lat"]):
                issues.append(f"Min latitude {bounds[1]:.2f} outside expected range")

            if not (expected_bounds["min_lat"] <= bounds[3] <= expected_bounds["max_lat"]):
                issues.append(f"Max latitude {bounds[3]:.2f} outside expected range")

        # 5. Check trail count
        trail_count = len(spatial_gdf)
        if self.expected_trail_count:
            # Check for >20% drop
            max_drop_percent = context.config.get("pipeline", {}).max_trail_count_drop_percent or 20.0
            drop_percent = ((self.expected_trail_count - trail_count) / self.expected_trail_count) * 100

            if drop_percent > max_drop_percent:
                issues.append(f"Trail count dropped {drop_percent:.1f}% (expected ~{self.expected_trail_count:,}, got {trail_count:,})")
            elif drop_percent > 5:
                warnings.append(f"Trail count dropped {drop_percent:.1f}% (expected ~{self.expected_trail_count:,})")

        # 6. Check required fields
        required_spatial_fields = ["local_id", "geometry"]
        for field in required_spatial_fields:
            if field not in spatial_gdf.columns:
                issues.append(f"Missing required spatial field: {field}")

        required_attribute_fields = ["hiking_trail_fk"]
        for field in required_attribute_fields:
            if field not in attributes_df.columns:
                issues.append(f"Missing required attribute field: {field}")

        # 7. Check CRS
        if spatial_gdf.crs is None:
            issues.append("Spatial data has no CRS defined")
        elif spatial_gdf.crs.to_epsg() != 4326:
            issues.append(f"Expected EPSG:4326, got {spatial_gdf.crs.to_epsg()}")

        # Determine result
        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        metadata: dict[str, int | list[str]] = {
            "trail_count": len(spatial_gdf),
            "attribute_count": len(attributes_df),
            "invalid_geometries": int(invalid_geoms),
            "empty_geometries": int(empty_geoms),
            "issues_count": len(issues),
            "warnings_count": len(warnings),
        }

        if issues:
            return StepResult(
                status=StepStatus.FAILED,
                error=f"Validation failed with {len(issues)} issue(s): " + "; ".join(issues),
                metadata=metadata,
                duration_seconds=duration,
                started_at=started_at,
                completed_at=completed_at,
            )

        # Log warnings but continue
        if warnings:
            metadata["warnings"] = warnings

        return StepResult(
            status=StepStatus.SUCCESS,
            output=input_data,  # Pass through unchanged
            metadata=metadata,
            duration_seconds=duration,
            started_at=started_at,
            completed_at=completed_at,
        )
