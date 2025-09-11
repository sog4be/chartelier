"""Tests for DataProcessor with safe operations."""

import polars as pl
import pytest

from chartelier.core.errors import ProcessingError
from chartelier.processing.data_processor import DataProcessor, ProcessedData


class TestDataProcessor:
    """Test DataProcessor functionality."""

    @pytest.fixture
    def processor(self) -> DataProcessor:
        """Create a DataProcessor instance."""
        return DataProcessor()

    @pytest.fixture
    def sample_df(self) -> pl.DataFrame:
        """Create a sample DataFrame for testing."""
        return pl.DataFrame(
            {
                "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
                "category": ["A", "B", "A", "B", "A"],
                "value": [10, 20, 15, 25, 30],
                "quantity": [1, 2, 3, 4, 5],
            }
        )

    def test_process_no_operations(self, processor: DataProcessor, sample_df: pl.DataFrame) -> None:
        """Test processing with no operations returns original data."""
        result = processor.process(sample_df, "test_template")

        assert isinstance(result, ProcessedData)
        assert result.df.equals(sample_df)
        assert len(result.operations_applied) == 0
        assert len(result.warnings) == 0

    def test_process_empty_operations(self, processor: DataProcessor, sample_df: pl.DataFrame) -> None:
        """Test processing with empty operations list."""
        result = processor.process(sample_df, "test_template", operations=[])

        assert result.df.equals(sample_df)
        assert len(result.operations_applied) == 0

    def test_groupby_agg(self, processor: DataProcessor, sample_df: pl.DataFrame) -> None:
        """Test groupby aggregation operation."""
        operations = [
            {"name": "groupby_agg", "params": {"by": "category", "agg": {"value": "sum", "quantity": "mean"}}}
        ]

        result = processor.process(sample_df, "test_template", operations)

        assert len(result.df) == 2  # Two categories
        assert "value_sum" in result.df.columns
        assert "quantity_mean" in result.df.columns
        assert len(result.operations_applied) == 1

    def test_filter_operation(self, processor: DataProcessor, sample_df: pl.DataFrame) -> None:
        """Test filter operation."""
        operations = [{"name": "filter", "params": {"condition": "category == 'A'"}}]

        result = processor.process(sample_df, "test_template", operations)

        assert len(result.df) == 3  # Three rows with category 'A'
        assert all(result.df["category"] == "A")

    def test_sort_operation(self, processor: DataProcessor, sample_df: pl.DataFrame) -> None:
        """Test sort operation."""
        operations = [{"name": "sort", "params": {"by": "value", "descending": True}}]

        result = processor.process(sample_df, "test_template", operations)

        assert result.df["value"].to_list() == [30, 25, 20, 15, 10]

    def test_sample_operation_deterministic(self, processor: DataProcessor, sample_df: pl.DataFrame) -> None:
        """Test that sample operation is deterministic."""
        operations = [{"name": "sample", "params": {"n": 3}}]

        result1 = processor.process(sample_df, "test_template", operations)
        result2 = processor.process(sample_df, "test_template", operations)

        assert len(result1.df) == 3
        assert result1.df.equals(result2.df)  # Should be identical due to fixed seed

    def test_head_tail_operations(self, processor: DataProcessor, sample_df: pl.DataFrame) -> None:
        """Test head and tail operations."""
        # Test head
        operations = [{"name": "head", "params": {"n": 2}}]
        result = processor.process(sample_df, "test_template", operations)
        assert len(result.df) == 2
        assert result.df["date"].to_list() == ["2024-01-01", "2024-01-02"]

        # Test tail
        operations = [{"name": "tail", "params": {"n": 2}}]
        result = processor.process(sample_df, "test_template", operations)
        assert len(result.df) == 2
        assert result.df["date"].to_list() == ["2024-01-04", "2024-01-05"]

    def test_rename_operation(self, processor: DataProcessor, sample_df: pl.DataFrame) -> None:
        """Test rename columns operation."""
        operations = [{"name": "rename", "params": {"mapping": {"value": "amount", "quantity": "qty"}}}]

        result = processor.process(sample_df, "test_template", operations)

        assert "amount" in result.df.columns
        assert "qty" in result.df.columns
        assert "value" not in result.df.columns
        assert "quantity" not in result.df.columns

    def test_select_drop_operations(self, processor: DataProcessor, sample_df: pl.DataFrame) -> None:
        """Test select and drop column operations."""
        # Test select
        operations = [{"name": "select", "params": {"columns": ["date", "value"]}}]
        result = processor.process(sample_df, "test_template", operations)
        assert result.df.columns == ["date", "value"]

        # Test drop
        operations = [{"name": "drop", "params": {"columns": ["quantity"]}}]
        result = processor.process(sample_df, "test_template", operations)
        assert "quantity" not in result.df.columns
        assert len(result.df.columns) == 3

    def test_cast_operation(self, processor: DataProcessor) -> None:
        """Test type casting operation."""
        df = pl.DataFrame({"value": ["1", "2", "3"]})
        operations = [{"name": "cast", "params": {"column": "value", "dtype": "int"}}]

        result = processor.process(df, "test_template", operations)

        assert result.df["value"].dtype == pl.Int64

    def test_fill_null_operation(self, processor: DataProcessor) -> None:
        """Test null value filling operation."""
        df = pl.DataFrame({"value": [1, None, 3, None, 5]})

        # Test with value
        operations = [{"name": "fill_null", "params": {"column": "value", "value": 0}}]
        result = processor.process(df, "test_template", operations)
        assert result.df["value"].null_count() == 0
        assert result.df["value"].to_list() == [1, 0, 3, 0, 5]

        # Test with forward fill
        df = pl.DataFrame({"value": [1, None, None, 4, None]})
        operations = [{"name": "fill_null", "params": {"column": "value", "strategy": "forward"}}]
        result = processor.process(df, "test_template", operations)
        assert result.df["value"].to_list() == [1, 1, 1, 4, 4]

    def test_with_column_operation(self, processor: DataProcessor, sample_df: pl.DataFrame) -> None:
        """Test adding new column with expression."""
        operations = [{"name": "with_column", "params": {"name": "total", "expression": "value + quantity"}}]

        result = processor.process(sample_df, "test_template", operations)

        assert "total" in result.df.columns
        expected = [11, 22, 18, 29, 35]
        assert result.df["total"].to_list() == expected

    def test_normalize_operation(self, processor: DataProcessor, sample_df: pl.DataFrame) -> None:
        """Test normalization operation."""
        # MinMax normalization
        operations = [{"name": "normalize", "params": {"column": "value", "method": "minmax"}}]

        result = processor.process(sample_df, "test_template", operations)

        assert "value_normalized" in result.df.columns
        normalized = result.df["value_normalized"]
        assert normalized.min() == pytest.approx(0.0)
        assert normalized.max() == pytest.approx(1.0)

    def test_cumsum_operation(self, processor: DataProcessor, sample_df: pl.DataFrame) -> None:
        """Test cumulative sum operation."""
        operations = [{"name": "cumsum", "params": {"column": "value"}}]

        result = processor.process(sample_df, "test_template", operations)

        assert "value_cumsum" in result.df.columns
        assert result.df["value_cumsum"].to_list() == [10, 30, 45, 70, 100]

    def test_rank_operation(self, processor: DataProcessor, sample_df: pl.DataFrame) -> None:
        """Test ranking operation."""
        operations = [{"name": "rank", "params": {"column": "value", "method": "average", "descending": False}}]

        result = processor.process(sample_df, "test_template", operations)

        assert "value_rank" in result.df.columns
        # Ranks should be 1, 3, 2, 4, 5 for values 10, 20, 15, 25, 30
        assert result.df["value_rank"].to_list() == [1.0, 3.0, 2.0, 4.0, 5.0]

    def test_bin_operation(self, processor: DataProcessor) -> None:
        """Test binning operation."""
        df = pl.DataFrame({"value": list(range(1, 11))})  # 1 to 10
        operations = [{"name": "bin", "params": {"column": "value", "n_bins": 3}}]

        result = processor.process(df, "test_template", operations)

        assert "value_binned" in result.df.columns
        # Should have 3 distinct bin categories
        assert result.df["value_binned"].n_unique() <= 3

    def test_pivot_operation(self, processor: DataProcessor) -> None:
        """Test pivot operation."""
        df = pl.DataFrame(
            {
                "date": ["2024-01-01", "2024-01-01", "2024-01-02", "2024-01-02"],
                "category": ["A", "B", "A", "B"],
                "value": [10, 20, 15, 25],
            }
        )

        operations = [
            {
                "name": "pivot",
                "params": {"values": "value", "index": "date", "columns": "category", "aggregate_function": "sum"},
            }
        ]

        result = processor.process(df, "test_template", operations)

        assert "A" in result.df.columns
        assert "B" in result.df.columns
        assert len(result.df) == 2  # Two dates

    def test_melt_operation(self, processor: DataProcessor) -> None:
        """Test melt operation."""
        df = pl.DataFrame({"id": [1, 2], "A": [10, 20], "B": [30, 40]})

        operations = [{"name": "melt", "params": {"id_vars": ["id"], "value_vars": ["A", "B"]}}]

        result = processor.process(df, "test_template", operations)

        assert "variable" in result.df.columns
        assert "value" in result.df.columns
        assert len(result.df) == 4  # 2 ids x 2 variables

    def test_rolling_operation(self, processor: DataProcessor, sample_df: pl.DataFrame) -> None:
        """Test rolling window operation."""
        operations = [{"name": "rolling", "params": {"window_size": 2, "agg": {"value": "mean"}}}]

        result = processor.process(sample_df, "test_template", operations)

        assert "value_rolling_mean" in result.df.columns
        # First value should be None (window size 2)
        assert result.df["value_rolling_mean"][0] is None
        # Second value should be mean of first two: (10+20)/2 = 15
        assert result.df["value_rolling_mean"][1] == 15.0

    def test_unregistered_operation_warning(self, processor: DataProcessor, sample_df: pl.DataFrame) -> None:
        """Test that unregistered operations are skipped with warning."""
        operations = [{"name": "unknown_operation", "params": {"some": "param"}}]

        result = processor.process(sample_df, "test_template", operations)

        # Data should be unchanged
        assert result.df.equals(sample_df)
        # Should have warning
        assert len(result.warnings) == 1
        assert "not registered" in result.warnings[0]
        # No operations applied
        assert len(result.operations_applied) == 0

    def test_operation_without_name(self, processor: DataProcessor, sample_df: pl.DataFrame) -> None:
        """Test operation without name is skipped with warning."""
        operations = [{"params": {"some": "param"}}]

        result = processor.process(sample_df, "test_template", operations)

        assert result.df.equals(sample_df)
        assert len(result.warnings) == 1
        assert "Missing operation name" in result.warnings[0]

    def test_required_operation_failure(self, processor: DataProcessor, sample_df: pl.DataFrame) -> None:
        """Test that required operation failure raises error."""
        operations = [{"name": "filter", "params": {"condition": "invalid syntax"}, "required": True}]

        with pytest.raises(ProcessingError) as exc_info:
            processor.process(sample_df, "test_template", operations)

        assert "Operation 'filter' failed" in str(exc_info.value)

    def test_optional_operation_failure(self, processor: DataProcessor, sample_df: pl.DataFrame) -> None:
        """Test that optional operation failure continues with warning."""
        operations = [{"name": "filter", "params": {"condition": "invalid syntax"}, "required": False}]

        result = processor.process(sample_df, "test_template", operations)

        # Data should be unchanged
        assert result.df.equals(sample_df)
        # Should have warning about failure
        assert len(result.warnings) == 1
        assert "Operation 'filter' failed" in result.warnings[0]

    def test_multiple_operations_pipeline(self, processor: DataProcessor, sample_df: pl.DataFrame) -> None:
        """Test pipeline of multiple operations."""
        operations = [
            {"name": "filter", "params": {"condition": "value > 10"}},
            {"name": "sort", "params": {"by": "value", "descending": True}},
            {"name": "select", "params": {"columns": ["category", "value"]}},
            {"name": "with_column", "params": {"name": "doubled", "expression": "value * 2"}},
        ]

        result = processor.process(sample_df, "test_template", operations)

        # Check final result
        assert len(result.df) == 4  # Filtered to 4 rows (values: 20, 15, 25, 30)
        assert result.df.columns == ["category", "value", "doubled"]
        assert result.df["value"].to_list() == [30, 25, 20, 15]  # Sorted descending
        assert result.df["doubled"].to_list() == [60.0, 50.0, 40.0, 30.0]
        assert len(result.operations_applied) == 4

    def test_idempotency(self, processor: DataProcessor, sample_df: pl.DataFrame) -> None:
        """Test that operations are idempotent."""
        operations = [
            {"name": "sort", "params": {"by": "value"}},
            {"name": "sample", "params": {"n": 3}},
            {"name": "normalize", "params": {"column": "value", "method": "minmax"}},
        ]

        # Apply operations twice
        result1 = processor.process(sample_df, "test_template", operations)
        result2 = processor.process(sample_df, "test_template", operations)

        # Results should be identical
        assert result1.df.equals(result2.df)
        assert result1.operations_applied == result2.operations_applied

    def test_empty_dataframe_handling(self, processor: DataProcessor) -> None:
        """Test handling of empty DataFrame."""
        empty_df = pl.DataFrame({"value": []})
        operations = [
            {"name": "sort", "params": {"by": "value"}},
        ]

        result = processor.process(empty_df, "test_template", operations)

        assert len(result.df) == 0
        assert len(result.operations_applied) == 1
        assert len(result.warnings) == 0
