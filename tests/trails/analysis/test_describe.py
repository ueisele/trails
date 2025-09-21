"""Tests for the describe module."""

import pandas as pd

from trails.analysis.describe import describe_column, describe_dataframe


class TestDescribeColumn:
    """Tests for describe_column function."""

    def test_string_column_few_unique_values(self):
        """Test string column with less than 5 unique values."""
        series = pd.Series(["Marked", "Not marked", "Marked", "Marked", "Not marked", None])
        result = describe_column(series, "marking")

        assert "marking [object]:" in result
        assert "Non-null: 5/6 (83.3% complete)" in result
        assert "Unique values: 2" in result
        assert "Is unique: False" in result
        assert "Values: ['Marked (3)', 'Not marked (2)']" in result

    def test_string_column_many_unique_values(self):
        """Test string column with 5 or more unique values."""
        series = pd.Series(["A", "B", "C", "D", "E", "F", "A", "B", "A", "B"])
        result = describe_column(series, "category")

        assert "category [object]:" in result
        assert "Non-null: 10/10 (100.0% complete)" in result
        assert "Unique values: 6" in result
        assert "Is unique: False" in result
        assert "Top 5 values:" in result
        assert "- A: 3" in result
        assert "- B: 3" in result

    def test_int64_column(self):
        """Test Int64 numeric column."""
        series = pd.Series([1, 2, 3, 4, 5, None], dtype="Int64")
        result = describe_column(series, "count")

        assert "count [Int64]:" in result
        assert "Non-null: 5/6 (83.3% complete)" in result
        assert "Min: 1 (1)" in result
        assert "Max: 5 (1)" in result
        assert "Median: 3" in result
        assert "Mean: 3.00" in result

    def test_float64_column(self):
        """Test Float64 numeric column."""
        series = pd.Series([1.5, 2.3, 3.7, 4.1, 5.9], dtype="Float64")
        result = describe_column(series, "measurement")

        assert "measurement [Float64]:" in result
        assert "Non-null: 5/5 (100.0% complete)" in result
        assert "Min: 1.50 (1)" in result
        assert "Max: 5.90 (1)" in result
        assert "Median: 3.70" in result
        assert "Mean: 3.50" in result

    def test_datetime_column(self):
        """Test datetime64[ms, UTC] column."""
        dates = pd.to_datetime(["2023-01-01 10:00:00", "2023-06-15 14:30:00", "2024-12-31 23:59:59", None]).tz_localize("UTC")
        # Convert to millisecond precision
        series = pd.Series(dates).astype("datetime64[ms, UTC]")
        result = describe_column(series, "timestamp")

        assert "timestamp [datetime64[ms, UTC]]:" in result
        assert "Non-null: 3/4 (75.0% complete)" in result
        assert "Min: 2023-01-01 10:00:00+00:00 (1)" in result
        assert "Max: 2024-12-31 23:59:59+00:00 (1)" in result

    def test_empty_column(self):
        """Test column with all null values."""
        series = pd.Series([None, None, None])
        result = describe_column(series, "empty")

        assert "empty [object]:" in result
        assert "Non-null: 0/3 (0.0% complete)" in result
        # Should not include any other statistics
        assert "Unique values:" not in result
        assert "Is unique:" not in result

    def test_unique_column(self):
        """Test column where all values are unique."""
        series = pd.Series(["A", "B", "C", "D"])
        result = describe_column(series, "id")

        assert "id [object]:" in result
        assert "Is unique: True" in result

    def test_pandas_string_dtype(self):
        """Test with pandas string dtype."""
        series = pd.Series(["A", "B", "A", "C"], dtype="string")
        result = describe_column(series, "category")

        assert "category [string]:" in result
        assert "Values: ['A (2)', 'B (1)', 'C (1)']" in result

    def test_no_name_provided(self):
        """Test when no name is provided, uses series name."""
        series = pd.Series([1, 2, 3], name="my_column")
        result = describe_column(series)

        assert "my_column [int64]:" in result

    def test_no_name_at_all(self):
        """Test when neither name parameter nor series.name exists."""
        series = pd.Series([1, 2, 3])
        result = describe_column(series)

        assert "Column [int64]:" in result

    def test_large_numbers_formatting(self):
        """Test that large numbers are displayed correctly."""
        series = pd.Series(list(range(10000)))
        result = describe_column(series, "large")

        assert "Non-null: 10000/10000" in result
        assert "Unique values: 10000" in result

    def test_min_max_with_duplicates(self):
        """Test Min/Max with duplicate values."""
        series = pd.Series([1, 1, 2, 3, 4, 5, 5, 5])
        result = describe_column(series, "numbers")

        assert "Min: 1 (2)" in result  # 1 appears twice
        assert "Max: 5 (3)" in result  # 5 appears three times
        assert "Median: 3.50" in result  # Median is 3.5, no count shown


class TestDescribeDataFrame:
    """Tests for describe_dataframe function."""

    def test_describe_all_columns(self):
        """Test describing all columns in a DataFrame."""
        df = pd.DataFrame({"string": ["A", "B", "A"], "number": [1, 2, 3], "date": pd.to_datetime(["2023-01-01", "2023-02-01", "2023-03-01"])})
        result = describe_dataframe(df)

        assert "string [object]:" in result
        assert "number [int64]:" in result
        assert "date [datetime64[ns]]:" in result

    def test_describe_specific_columns(self):
        """Test describing specific columns only."""
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"], "c": [4, 5, 6]})
        result = describe_dataframe(df, columns=["a", "c"])

        assert "a [int64]:" in result
        assert "c [int64]:" in result
        assert "b [object]:" not in result

    def test_describe_nonexistent_column(self):
        """Test handling of nonexistent column names."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        result = describe_dataframe(df, columns=["a", "nonexistent"])

        assert "a [int64]:" in result
        # Should silently skip nonexistent columns
        assert "nonexistent" not in result

    def test_describe_sorted_by_completeness(self):
        """Test that columns are sorted by completeness (highest first)."""
        df = pd.DataFrame(
            {
                "complete": [1, 2, 3, 4],  # 100% complete
                "partial": [1, None, 3, None],  # 50% complete
                "mostly_empty": [None, None, None, 4],  # 25% complete
            }
        )
        result = describe_dataframe(df)

        # Find the order of columns in the result
        complete_pos = result.find("complete [int64]:")
        partial_pos = result.find("partial [float64]:")
        mostly_empty_pos = result.find("mostly_empty [float64]:")

        # Complete should come first, then partial, then mostly_empty
        assert complete_pos < partial_pos < mostly_empty_pos

    def test_describe_without_sorting(self):
        """Test that columns maintain original order when sorting is disabled."""
        df = pd.DataFrame(
            {
                "partial": [1, None, 3, None],  # 50% complete
                "complete": [1, 2, 3, 4],  # 100% complete
                "mostly_empty": [None, None, None, 4],  # 25% complete
            }
        )
        result = describe_dataframe(df, columns=["partial", "complete", "mostly_empty"], sort_by_completeness=False)

        # Find the order of columns in the result
        partial_pos = result.find("partial [float64]:")
        complete_pos = result.find("complete [int64]:")
        mostly_empty_pos = result.find("mostly_empty [float64]:")

        # Should maintain the original order: partial, complete, mostly_empty
        assert partial_pos < complete_pos < mostly_empty_pos
