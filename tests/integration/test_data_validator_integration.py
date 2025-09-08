"""Integration tests for DataValidator with focus on deterministic sampling."""

from __future__ import annotations

import json

import polars as pl
import pytest

from chartelier.processing.data_validator import DataValidator


class TestDataValidatorIntegration:
    """Integration tests for DataValidator."""

    @pytest.fixture
    def validator(self):
        """Create a DataValidator instance."""
        return DataValidator()

    def test_large_csv_deterministic_sampling(self, validator):
        """Test deterministic sampling with large CSV data."""
        # Create large CSV data
        rows = 50000
        csv_lines = ["id,value,category,amount"]
        for i in range(rows):
            csv_lines.append(f"{i},{i * 10},cat_{i % 100},{i * 0.5}")
        large_csv = "\n".join(csv_lines)

        # Validate multiple times
        results = []
        for _ in range(3):
            result = validator.validate(large_csv, "csv")
            results.append(result)

        # All results should be identical
        assert all(r.metadata.rows == results[0].metadata.rows for r in results)
        assert all(r.metadata.sampled for r in results)
        assert all(r.metadata.original_rows == rows for r in results)

        # DataFrames should be identical
        for i in range(1, len(results)):
            assert results[i].df.equals(results[0].df)

    def test_large_json_deterministic_sampling(self, validator):
        """Test deterministic sampling with large JSON data."""
        # Create large JSON data
        rows = 15000
        json_data = [{"id": i, "name": f"item_{i}", "value": i * 1.5, "active": i % 2 == 0} for i in range(rows)]
        large_json = json.dumps(json_data)

        # Validate twice
        result1 = validator.validate(large_json, "json")
        result2 = validator.validate(large_json, "json")

        # Results should be identical
        assert result1.metadata.rows == result2.metadata.rows
        assert result1.metadata.sampled == result2.metadata.sampled
        assert result1.df.equals(result2.df)

        # Check that sampling occurred
        assert result1.metadata.rows <= validator.constraints["max_rows"]
        assert result1.metadata.original_rows == rows

    def test_mixed_data_types_sampling(self, validator):
        """Test sampling preserves data types correctly."""
        # Create DataFrame with various data types
        rows = 20000
        csv_lines = ["int_col,float_col,str_col,bool_col,date_col"]
        for i in range(rows):
            csv_lines.append(f"{i},{i * 0.1},text_{i},{i % 2 == 0},2024-01-{(i % 28) + 1:02d}")
        mixed_csv = "\n".join(csv_lines)

        result = validator.validate(mixed_csv, "csv")

        # Check that data types are preserved after sampling
        assert result.metadata.dtypes["int_col"] == "integer"
        assert result.metadata.dtypes["float_col"] == "float"
        assert result.metadata.dtypes["str_col"] == "string"
        assert result.metadata.dtypes["bool_col"] == "boolean"
        assert result.metadata.dtypes["date_col"] == "datetime"

        # Verify sampling occurred
        assert result.metadata.sampled
        assert result.metadata.rows <= validator.constraints["max_rows"]

    def test_cell_limit_enforcement(self, validator):
        """Test that cell limit is enforced correctly."""
        # Create DataFrame that exceeds cell limit but not row limit
        cols = 100  # Maximum allowed columns
        rows = 12000  # 100 * 12000 = 1,200,000 cells (exceeds 1M limit)

        data = {f"col_{i}": range(rows) for i in range(cols)}
        test_df = pl.DataFrame(data)
        csv_data = test_df.write_csv()

        result = validator.validate(csv_data, "csv")

        # Check that sampling was applied due to cell limit
        assert result.metadata.sampled
        assert result.metadata.rows * result.metadata.cols <= validator.constraints["max_cells"]
        assert result.metadata.original_rows == rows

        # Verify first and last rows are preserved
        dataframe = result.df
        assert dataframe["col_0"][0] == 0
        assert dataframe["col_0"][-1] == rows - 1

    def test_boundary_conditions(self, validator):
        """Test various boundary conditions for sampling."""
        # Test cases: (rows, expected_sampled)
        test_cases = [
            (validator.constraints["max_rows"] - 1, False),  # Just under limit
            (validator.constraints["max_rows"], False),  # Exactly at limit
            (validator.constraints["max_rows"] + 1, True),  # Just over limit
            (1, False),  # Single row
            (2, False),  # Two rows
        ]

        for rows, expected_sampled in test_cases:
            csv_lines = ["value"]
            csv_lines.extend([str(i) for i in range(rows)])
            csv_data = "\n".join(csv_lines)

            result = validator.validate(csv_data, "csv")

            assert result.metadata.sampled == expected_sampled, f"Failed for rows={rows}"
            if expected_sampled:
                assert result.metadata.rows <= validator.constraints["max_rows"]
                assert result.metadata.original_rows == rows
            else:
                assert result.metadata.rows == rows

    def test_columnar_json_format(self, validator):
        """Test sampling with columnar JSON format."""
        # Create columnar JSON (dict of arrays)
        rows = 15000
        json_data = {
            "ids": list(range(rows)),
            "values": [i * 2 for i in range(rows)],
            "labels": [f"label_{i}" for i in range(rows)],
        }
        json_str = json.dumps(json_data)

        result = validator.validate(json_str, "json")

        # Check that sampling was applied
        assert result.metadata.sampled
        assert result.metadata.rows <= validator.constraints["max_rows"]
        assert result.metadata.original_rows == rows

        # Verify data integrity
        dataframe = result.df
        # First and last elements should be preserved
        assert dataframe["ids"][0] == 0
        assert dataframe["ids"][-1] == rows - 1

        # Values should maintain relationship
        for i in range(len(dataframe)):
            assert dataframe["values"][i] == dataframe["ids"][i] * 2
            assert dataframe["labels"][i] == f"label_{dataframe['ids'][i]}"

    def test_sampling_with_null_values(self, validator):
        """Test that sampling correctly handles null values."""
        # Create data with nulls
        rows = 12000
        csv_lines = ["id,value,optional"]
        for i in range(rows):
            optional = "" if i % 3 == 0 else str(i)
            csv_lines.append(f"{i},{i * 10},{optional}")
        csv_data = "\n".join(csv_lines)

        result = validator.validate(csv_data, "csv")

        # Check sampling occurred
        assert result.metadata.sampled

        # Check null ratio is calculated correctly for sampled data
        sampled_null_count = result.df["optional"].null_count()
        sampled_rows = len(result.df)
        expected_ratio = sampled_null_count / sampled_rows if sampled_rows > 0 else 0.0

        assert abs(result.metadata.null_ratio["optional"] - expected_ratio) < 0.01

    def test_consistent_warning_messages(self, validator):
        """Test that warning messages are consistent and informative."""
        # Create data that will trigger sampling
        rows = 15000
        csv_lines = ["col1,col2"]
        csv_lines.extend([f"{i},{i * 2}" for i in range(rows)])
        large_csv = "\n".join(csv_lines)

        result = validator.validate(large_csv, "csv")

        # Check warning message format
        assert len(result.warnings) > 0
        warning = result.warnings[0]
        assert "sampled" in warning.lower()
        # Check for formatted numbers (with commas)
        assert f"{rows:,}" in warning or str(rows) in warning  # Original row count
        assert f"{result.metadata.rows:,}" in warning or str(result.metadata.rows) in warning  # Sampled row count
        assert "due to size limits" in warning.lower()
