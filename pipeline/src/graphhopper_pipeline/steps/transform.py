"""Transform step: Convert trail data to OSM format."""

from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
from lxml import etree
from trails.pipeline import PipelineContext, PipelineStep, StepResult, StepStatus

from graphhopper_pipeline.config import CountryConfig, load_country_config


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

            # Validate input
            errors = self.validate_input(input_data)
            if errors:
                return StepResult(
                    status=StepStatus.FAILED,
                    error=f"Input validation failed: {'; '.join(errors)}",
                    started_at=started_at,
                    completed_at=datetime.now(),
                )

            # Load country configuration
            country_config = load_country_config(self.country_code)

            # Step 1: Join spatial and attribute data
            joined_gdf = self._join_data(spatial_gdf, attributes_df)

            # Step 2: Generate OSM XML
            osm_xml_path = context.work_dir / "trails.osm"
            way_count = self._generate_osm_xml(joined_gdf, osm_xml_path, country_config)

            # Step 3: Convert to PBF (if osmium available)
            osm_pbf_path = context.work_dir / "trails.osm.pbf"
            pbf_converted = self._convert_to_pbf(osm_xml_path, osm_pbf_path)

            completed_at = datetime.now()
            duration = (completed_at - started_at).total_seconds()

            # Return XML path if PBF conversion failed
            output_path = osm_pbf_path if pbf_converted else osm_xml_path

            return StepResult(
                status=StepStatus.SUCCESS,
                output=output_path,
                metadata={
                    "input_trail_count": len(spatial_gdf),
                    "input_attribute_count": len(attributes_df),
                    "joined_count": len(joined_gdf),
                    "way_count": way_count,
                    "output_format": "pbf" if pbf_converted else "xml",
                    "output_path": str(output_path),
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
                error=f"Transform failed: {e}",
                duration_seconds=duration,
                started_at=started_at,
                completed_at=completed_at,
            )

    def _join_data(
        self, spatial_gdf: gpd.GeoDataFrame, attributes_df: pd.DataFrame
    ) -> gpd.GeoDataFrame:
        """Join spatial and attribute data.

        Creates one row per (geometry, trail_name) combination to handle
        many-to-one relationships (one segment, multiple trail names).

        Args:
            spatial_gdf: Spatial geometries
            attributes_df: Trail attributes

        Returns:
            Joined GeoDataFrame with one row per OSM way
        """
        # Join on local_id = hiking_trail_fk
        joined = spatial_gdf.merge(
            attributes_df,
            left_on="local_id",
            right_on="hiking_trail_fk",
            how="inner",
        )

        return joined

    def _generate_osm_xml(
        self, joined_gdf: gpd.GeoDataFrame, output_path: Path, country_config: CountryConfig
    ) -> int:
        """Generate OSM XML from joined trail data.

        Args:
            joined_gdf: Joined spatial and attribute data
            output_path: Path to write OSM XML
            country_config: Country configuration with OSM mappings

        Returns:
            Number of ways generated
        """
        # Create root element
        root = etree.Element(
            "osm",
            version="0.6",
            generator="graphhopper-trails-pipeline",
        )

        # Track nodes and assign IDs
        node_id = 1
        coord_to_node: dict[tuple[float, float], int] = {}

        # Generate nodes from all trail geometries
        for _, row in joined_gdf.iterrows():
            geom = row.geometry
            if geom.geom_type == "LineString":
                for coord in geom.coords:
                    # Round to avoid float precision issues
                    coord_key = (round(coord[0], 7), round(coord[1], 7))

                    if coord_key not in coord_to_node:
                        etree.SubElement(
                            root,
                            "node",
                            id=str(node_id),
                            lat=str(coord[1]),
                            lon=str(coord[0]),
                        )
                        coord_to_node[coord_key] = node_id
                        node_id += 1

        # Generate ways
        way_id = 1000000
        for _, row in joined_gdf.iterrows():
            geom = row.geometry
            if geom.geom_type != "LineString":
                continue

            way = etree.SubElement(root, "way", id=str(way_id), version="1")

            # Add node references
            for coord in geom.coords:
                coord_key = (round(coord[0], 7), round(coord[1], 7))
                etree.SubElement(way, "nd", ref=str(coord_to_node[coord_key]))

            # Add OSM tags
            tags = self._map_to_osm_tags(row, country_config)
            for key, value in tags.items():
                if value:  # Skip empty values
                    etree.SubElement(way, "tag", k=key, v=str(value))

            way_id += 1

        # Write XML
        tree = etree.ElementTree(root)
        tree.write(
            str(output_path),
            encoding="utf-8",
            xml_declaration=True,
            pretty_print=True,
        )

        way_count = way_id - 1000000
        return way_count

    def _map_to_osm_tags(self, row: pd.Series, country_config: CountryConfig) -> dict[str, str]:
        """Map Turrutebasen attributes to OSM tags.

        Args:
            row: Trail data row
            country_config: Country configuration with mappings

        Returns:
            Dictionary of OSM tags
        """
        tags = {}

        # Apply OSM mappings from config
        for field, mapping in country_config.osm_mappings.items():
            if field in row and pd.notna(row[field]):
                value = row[field]

                # Use value mapping if available
                if mapping.values and value in mapping.values:
                    tags[mapping.osm_tag] = mapping.values[value]
                else:
                    tags[mapping.osm_tag] = str(value)

        # Apply inference rules
        inference_rules = country_config.inference_rules

        # Infer difficulty (gradering) from route type (rutefolger)
        if "gradering" in inference_rules and "rutefolger" in row:
            rutefolger_value = row["rutefolger"]
            gradering_mapping = inference_rules["gradering"]

            if rutefolger_value in gradering_mapping and "sac_scale" not in tags:
                tags["sac_scale"] = gradering_mapping[rutefolger_value]

        # Infer surface from route type
        if "surface" in inference_rules and "rutefolger" in row:
            rutefolger_value = row["rutefolger"]
            surface_mapping = inference_rules["surface"]

            if rutefolger_value in surface_mapping and "surface" not in tags:
                tags["surface"] = surface_mapping[rutefolger_value]

        # Always add source attribution
        tags["source"] = "Kartverket Turrutebasen"

        # Add reference to original ID
        if "local_id" in row:
            tags["ref:geonorge"] = str(row["local_id"])

        return tags

    def _convert_to_pbf(self, osm_xml_path: Path, osm_pbf_path: Path) -> bool:
        """Convert OSM XML to PBF format using osmium.

        Args:
            osm_xml_path: Input OSM XML file
            osm_pbf_path: Output PBF file

        Returns:
            True if conversion succeeded, False otherwise
        """
        import subprocess

        try:
            # Try using osmium-tool
            result = subprocess.run(
                ["osmium", "cat", str(osm_xml_path), "-o", str(osm_pbf_path)],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode == 0:
                return True

            # If osmium failed, log but don't fail the step
            return False

        except (FileNotFoundError, subprocess.TimeoutExpired):
            # osmium not available or timed out
            return False
