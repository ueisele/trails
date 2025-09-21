"""Functions for describing and analyzing data columns."""

import pandas as pd


def describe_column(series: pd.Series, name: str | None = None) -> str:
    """Generate a detailed text description of a pandas Series/column.

    Provides statistics appropriate to the column's dtype:
    - For string/object with <5 unique values: shows all values with counts
    - For string/object with ≥5 unique values: shows top 5 values with counts
    - For datetime columns: shows min/max dates
    - For numeric columns: shows min/max/median/mean
    - For all types: shows non-null count, unique count, and uniqueness

    Args:
        series: The pandas Series to describe
        name: Optional name to display (uses series.name if not provided)

    Returns:
        Formatted string description of the column

    Examples:
        >>> import pandas as pd
        >>> s = pd.Series(["A", "B", "A", "C", "B", "A"])
        >>> print(describe_column(s, "category"))
        category [object]:
          Non-null: 6/6 (100.0% complete)
          Unique values: 3
          Is unique: False
          Values: ['A (3)', 'B (2)', 'C (1)']
    """
    lines = []

    # Get column name
    col_name = name if name is not None else series.name
    if col_name is None:
        col_name = "Column"

    # Get dtype string
    dtype_str = str(series.dtype)

    # Header line
    lines.append(f"{col_name} [{dtype_str}]:")

    # Non-null count
    non_null = series.notna().sum()
    total = len(series)
    pct_complete = (non_null / total * 100) if total > 0 else 0
    lines.append(f"  Non-null: {non_null}/{total} ({pct_complete:.1f}% complete)")

    # If column is empty, only show non-null
    if non_null == 0:
        return "\n".join(lines)

    # Get non-null values for further analysis
    valid_series = series.dropna()

    # Unique values count
    n_unique = valid_series.nunique()
    lines.append(f"  Unique values: {n_unique}")

    # Is unique check
    is_unique = n_unique == non_null
    lines.append(f"  Is unique: {is_unique}")

    # Type-specific statistics
    if pd.api.types.is_datetime64_any_dtype(series):
        # Datetime statistics with counts
        min_val = valid_series.min()
        max_val = valid_series.max()
        min_count = (valid_series == min_val).sum()
        max_count = (valid_series == max_val).sum()
        lines.append(f"  Min: {min_val} ({min_count})")
        lines.append(f"  Max: {max_val} ({max_count})")

    elif pd.api.types.is_numeric_dtype(series):
        # Numeric statistics with counts for min/max
        min_val = valid_series.min()
        max_val = valid_series.max()
        min_count = (valid_series == min_val).sum()
        max_count = (valid_series == max_val).sum()

        if pd.api.types.is_float_dtype(series):
            lines.append(f"  Min: {min_val:.2f} ({min_count})")
            lines.append(f"  Max: {max_val:.2f} ({max_count})")
        else:
            lines.append(f"  Min: {min_val} ({min_count})")
            lines.append(f"  Max: {max_val} ({max_count})")

        median_val = valid_series.median()
        if pd.api.types.is_float_dtype(series):
            lines.append(f"  Median: {median_val:.2f}")
        else:
            # For integer types, check if median is a whole number
            if median_val == int(median_val):
                lines.append(f"  Median: {int(median_val)}")
            else:
                lines.append(f"  Median: {median_val:.2f}")

        lines.append(f"  Mean: {valid_series.mean():.2f}")

    # String/object type
    value_counts = valid_series.value_counts()

    if n_unique < 5:
        # Show all values with counts
        values_list = []
        for value, count in value_counts.items():
            values_list.append(f"{value} ({count})")
        lines.append(f"  Values: {values_list}")
    else:
        # Show top 5 values
        lines.append("  Top 5 values:")
        for value, count in value_counts.head(5).items():
            lines.append(f"    - {value}: {count}")

    return "\n".join(lines)


def describe_dataframe(df: pd.DataFrame, columns: list[str] | None = None, sort_by_completeness: bool = True) -> str:
    """Generate descriptions for multiple columns in a DataFrame.

    Columns can be sorted by completeness (highest first) to show the most
    complete data at the top, or displayed in the order provided.

    Args:
        df: The DataFrame to describe
        columns: List of column names to describe (None for all columns)
        sort_by_completeness: If True, sort columns by completeness (default True)

    Returns:
        Formatted string with descriptions of all requested columns
    """
    if columns is None:
        columns = df.columns.tolist()

    # Calculate completeness for each valid column
    valid_columns = []
    for col in columns:
        if col in df.columns:
            completeness = df[col].notna().sum() / len(df) * 100 if len(df) > 0 else 0
            valid_columns.append((col, completeness))

    # Sort by completeness if requested
    if sort_by_completeness:
        valid_columns.sort(key=lambda x: x[1], reverse=True)

    # Generate descriptions in order
    descriptions = []
    for col, _ in valid_columns:
        descriptions.append(describe_column(df[col], col))

    return "\n\n".join(descriptions)
