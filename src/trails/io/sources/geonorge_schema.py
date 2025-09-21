"""
Schema definitions for Geonorge (Kartverket) data.

Defines column types and standardization rules for Norwegian trail data.
"""

import warnings
from typing import Any, Literal, TypeVar

import geopandas as gpd
import pandas as pd

# Type aliases
ColumnType = Literal["code", "string", "Int64", "Float64", "datetime", "geometry"]
T = TypeVar("T", gpd.GeoDataFrame, pd.DataFrame)

# Column type definitions
# Maps column names to their expected data types
COLUMN_SCHEMA: dict[str, ColumnType] = {
    # ===== CODE COLUMNS (need lookup in geonorge_codes) =====
    "objtype": "code",
    "rutefolger": "code",
    "rutebredde": "code",
    "gradering": "code",
    "sesong": "code",
    "tilpasning": "code",
    "tilrettelegging": "code",
    "trafikkbelastning": "code",
    "malemetode": "code",
    "merking": "code",
    "belysning": "code",
    "skilting": "code",
    "underlagstype": "code",
    "rutetype": "code",
    "rutebetydning": "code",
    "ryddebredde": "code",
    "preparering": "code",
    "spesialfotrutetype": "code",
    "spesialskiloypetype": "code",
    "spesialsykkelrutetype": "code",
    "spesialannenrutetype": "code",
    # ===== DATETIME COLUMNS =====
    "datafangstdato": "datetime",
    "oppdateringsdato": "datetime",
    "kopidato": "datetime",
    # ===== NUMERIC MEASUREMENT COLUMNS =====
    "noyaktighet": "Int64",  # Accuracy in meters
    "SHAPE_Length": "Float64",  # Geometry length
    "antallskispor": "Int64",  # Number of ski tracks
    "anleggsnummer": "Int64",  # Facility number
    "omradeid": "Int64",  # Area ID
    "skoytetrase": "Int64",  # Skating track (0/1)
    # ===== TEXT IDENTIFIER COLUMNS =====
    "lokalid": "string",
    "navnerom": "string",
    "versjonid": "string",
    "uukoblingsid": "string",
    # ===== TEXT ATTRIBUTE COLUMNS =====
    "rutenavn": "string",
    "rutenummer": "string",
    "ruteinformasjon": "string",
    "ruteinfoid": "string",
    "vedlikeholdsansvarlig": "string",
    "informasjon": "string",
    "opphav": "string",
    "originaldatavert": "string",
    # ===== FOREIGN KEY COLUMNS =====
    "fotrute_fk": "string",
    "annenrute_fk": "string",
    "skiloype_fk": "string",
    "sykkelrute_fk": "string",
    # ===== GEOMETRY COLUMN =====
    "geometry": "geometry",
}


def is_empty(value: Any) -> bool:
    """Check if a value should be considered empty/missing.

    Args:
        value: Value to check

    Returns:
        True if the value is empty/missing
    """
    return pd.isna(value) or value == "" or value is None


def standardize_types(df: T) -> T:
    """Standardize column types according to schema.

    Converts columns to their expected types based on COLUMN_SCHEMA.
    Handles empty values consistently by converting them to pd.NA.

    Args:
        df: DataFrame to standardize

    Returns:
        DataFrame with standardized types
    """
    df = df.copy()

    # Track columns without schema for warning
    unknown_columns = []

    for column in df.columns:
        if column not in COLUMN_SCHEMA:
            # Keep unknown columns as-is
            unknown_columns.append(column)
            continue

        dtype = COLUMN_SCHEMA[column]

        if dtype == "code":
            # Convert to string, handling numeric codes
            # Check if the value is a whole number (1.0, 2.0) or has decimals (1.5, 2.3)
            def convert_code(x: Any) -> Any:
                if is_empty(x):
                    return pd.NA
                if pd.api.types.is_number(x):
                    # Convert numeric codes to string
                    # For whole numbers like 1.0, this gives us "1" instead of "1.0"
                    if x == int(x):  # Check if it's a whole number
                        return str(int(x))
                    else:
                        # Keep decimal for values like 1.5
                        return str(x)
                return str(x)

            df[column] = df[column].apply(convert_code).astype("string")

        elif dtype == "string":
            # Convert to nullable string
            df[column] = df[column].apply(lambda x: pd.NA if is_empty(x) else str(x)).astype("string")

        elif dtype == "Int64":
            # Convert to nullable integer with empty handling
            df[column] = df[column].apply(lambda x: pd.NA if is_empty(x) else x)
            df[column] = pd.to_numeric(df[column], errors="coerce").astype("Int64")

        elif dtype == "Float64":
            # Convert to nullable float with empty handling
            df[column] = df[column].apply(lambda x: pd.NA if is_empty(x) else x)
            df[column] = pd.to_numeric(df[column], errors="coerce").astype("Float64")

        elif dtype == "datetime":
            # Convert to datetime with empty handling
            # GDAL typically provides datetime64[ms, UTC] already
            if df[column].dtype == "datetime64[ms, UTC]":
                # Already in correct format, just handle any empty values
                # No need to convert as datetime columns handle NaT properly
                pass
            else:
                # Convert to datetime with UTC timezone
                df[column] = pd.to_datetime(df[column].apply(lambda x: pd.NA if is_empty(x) else x), utc=True, errors="coerce")

        elif dtype == "geometry":
            # Geometry column is handled by geopandas, no conversion needed
            pass

    # Warn about unknown columns if any were found
    if unknown_columns:
        warnings.warn(
            f"No schema defined for columns: {', '.join(sorted(unknown_columns))}. These columns will be kept as-is without type standardization.",
            UserWarning,
            stacklevel=2,
        )

    return df


def get_code_columns() -> list[str]:
    """Get list of columns that contain codes.

    Returns:
        List of column names that have type "code" in the schema
    """
    return [col for col, dtype in COLUMN_SCHEMA.items() if dtype == "code"]


def get_column_type(column: str) -> ColumnType | None:
    """Get the expected type for a column.

    Args:
        column: Column name

    Returns:
        Column type from schema, or None if not defined
    """
    return COLUMN_SCHEMA.get(column)


def has_schema(column: str) -> bool:
    """Check if a column has a defined schema.

    Args:
        column: Column name

    Returns:
        True if the column is in the schema
    """
    return column in COLUMN_SCHEMA
