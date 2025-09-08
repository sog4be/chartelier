"""Unit tests for DataValidator."""

import json
from textwrap import dedent

import polars as pl
import pytest

from chartelier.core.enums import ErrorCode
from chartelier.core.errors import ChartelierError
from chartelier.processing.data_validator import DATA_CONSTRAINTS, DataValidator


class TestDataValidator:
    """Test cases for DataValidator."""

    @pytest.fixture
    def validator(self):
        """Create a DataValidator instance."""
        return DataValidator()

    @pytest.fixture
    def sample_csv(self):
        """Sample CSV data."""
        return dedent("""\
            date,value,category
            2024-01-01,100,A
            2024-01-02,150,B
            2024-01-03,200,A
            2024-01-04,120,C
            2024-01-05,180,B
        """).strip()

    @pytest.fixture
    def sample_json(self):
        """Sample JSON data (records format)."""
        data = [
            {"id": 1, "name": "Alice", "score": 85.5},
            {"id": 2, "name": "Bob", "score": 92.0},
            {"id": 3, "name": "Charlie", "score": 78.5},
        ]
        return json.dumps(data)

    @pytest.fixture
    def sample_json_columnar(self):
        """Sample JSON data (columnar format)."""
        data = {
            "id": [1, 2, 3],
            "name": ["Alice", "Bob", "Charlie"],
            "score": [85.5, 92.0, 78.5],
        }
        return json.dumps(data)

    def test_validate_csv_success(self, validator, sample_csv):
        """Test successful CSV validation."""
        result = validator.validate(sample_csv, "csv")

        assert result.df is not None
        assert isinstance(result.df, pl.DataFrame)
        assert result.metadata.rows == 5
        assert result.metadata.cols == 3
        assert "date" in result.metadata.dtypes
        assert "value" in result.metadata.dtypes
        assert "category" in result.metadata.dtypes
        assert result.metadata.has_datetime is True
        # Category column has 3 unique values out of 5 rows (60%), not categorical enough
        assert len(result.warnings) == 0

    def test_validate_json_records_success(self, validator, sample_json):
        """Test successful JSON validation (records format)."""
        result = validator.validate(sample_json, "json")

        assert result.df is not None
        assert isinstance(result.df, pl.DataFrame)
        assert result.metadata.rows == 3
        assert result.metadata.cols == 3
        assert "id" in result.metadata.dtypes
        assert "name" in result.metadata.dtypes
        assert "score" in result.metadata.dtypes
        assert len(result.warnings) == 0

    def test_validate_json_columnar_success(self, validator, sample_json_columnar):
        """Test successful JSON validation (columnar format)."""
        result = validator.validate(sample_json_columnar, "json")

        assert result.df is not None
        assert isinstance(result.df, pl.DataFrame)
        assert result.metadata.rows == 3
        assert result.metadata.cols == 3
        assert len(result.warnings) == 0

    def test_validate_empty_data(self, validator):
        """Test validation of empty data."""
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate("", "csv")
        assert exc_info.value.code == ErrorCode.E422_UNPROCESSABLE

    def test_validate_invalid_format(self, validator):
        """Test validation with unsupported format."""
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate("some data", "xml")
        assert exc_info.value.code == ErrorCode.E422_UNPROCESSABLE

    def test_validate_invalid_csv(self, validator):
        """Test validation of malformed CSV."""
        invalid_csv = "col1,col2\n1,2,3\n4,5"  # Inconsistent column count
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(invalid_csv, "csv")
        assert exc_info.value.code == ErrorCode.E422_UNPROCESSABLE

    def test_validate_invalid_json(self, validator):
        """Test validation of malformed JSON."""
        invalid_json = '{"key": "value"'  # Missing closing brace
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(invalid_json, "json")
        assert exc_info.value.code == ErrorCode.E422_UNPROCESSABLE

    def test_validate_too_many_columns(self, validator):
        """Test validation with too many columns."""
        # Create CSV with more than max columns
        cols = [f"col{i}" for i in range(DATA_CONSTRAINTS["max_columns"] + 1)]
        csv_data = ",".join(cols) + "\n" + ",".join(["1"] * len(cols))

        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(csv_data, "csv")
        assert exc_info.value.code == ErrorCode.E400_VALIDATION
        assert "Too many columns" in exc_info.value.message

    def test_validate_with_sampling(self, validator):
        """Test validation with data sampling due to row limit."""
        # Create CSV with more than max rows
        rows = DATA_CONSTRAINTS["max_rows"] + 100
        csv_lines = ["col1,col2,col3"]
        csv_lines.extend([f"{i},value{i},cat{i % 3}" for i in range(rows)])
        large_csv = "\n".join(csv_lines)

        result = validator.validate(large_csv, "csv")

        assert result.metadata.sampled is True
        assert result.metadata.rows <= DATA_CONSTRAINTS["max_rows"]
        assert result.metadata.original_rows == rows
        assert len(result.warnings) > 0
        assert "sampled" in result.warnings[0].lower()

    def test_deterministic_sampling(self, validator):
        """Test that sampling is deterministic."""
        # Create large CSV
        rows = DATA_CONSTRAINTS["max_rows"] + 100
        csv_lines = ["col1,col2"]
        csv_lines.extend([f"{i},{i * 2}" for i in range(rows)])
        large_csv = "\n".join(csv_lines)

        # Validate twice
        result1 = validator.validate(large_csv, "csv")
        result2 = validator.validate(large_csv, "csv")

        # Results should be identical
        assert result1.metadata.rows == result2.metadata.rows
        assert result1.df.equals(result2.df)

    def test_null_ratio_calculation(self, validator):
        """Test null ratio calculation."""
        csv_with_nulls = dedent("""\
            col1,col2,col3
            1,2,3
            4,,6
            7,8,
            ,,12
        """).strip()
        result = validator.validate(csv_with_nulls, "csv")

        assert result.metadata.null_ratio["col1"] == 0.25  # 1 null out of 4
        assert result.metadata.null_ratio["col2"] == 0.5  # 2 nulls out of 4
        assert result.metadata.null_ratio["col3"] == 0.25  # 1 null out of 4

    def test_dtype_detection(self, validator):
        """Test data type detection."""
        mixed_csv = dedent("""\
            int_col,float_col,str_col,bool_col,date_col
            1,1.5,hello,true,2024-01-01
            2,2.5,world,false,2024-01-02
            3,3.5,test,true,2024-01-03
        """).strip()

        result = validator.validate(mixed_csv, "csv")

        assert result.metadata.dtypes["int_col"] == "integer"
        assert result.metadata.dtypes["float_col"] == "float"
        assert result.metadata.dtypes["str_col"] == "string"
        assert result.metadata.dtypes["bool_col"] == "boolean"
        assert result.metadata.dtypes["date_col"] == "datetime"
        assert result.metadata.has_datetime is True

    def test_category_detection(self, validator):
        """Test categorical column detection."""
        # More rows with fewer categories to trigger categorical detection
        csv_with_categories = dedent("""\
            id,category,value
            1,A,100
            2,B,200
            3,A,150
            4,A,175
            5,B,225
            6,A,130
            7,B,245
            8,A,155
        """).strip()

        result = validator.validate(csv_with_categories, "csv")
        assert result.metadata.has_category is True  # 2 unique values out of 8 rows (25%)

    def test_utf8_validation(self, validator):
        """Test UTF-8 encoding validation."""
        # This would need actual non-UTF8 bytes, which is hard to represent in a string
        # We'll test the method directly
        assert validator._check_utf8("Hello, 世界! 🌍") is True  # noqa: SLF001

    def test_cell_limit_sampling(self, validator):
        """Test sampling when cell limit is exceeded."""
        # Create data that exceeds cell limit
        cols = 50
        rows = DATA_CONSTRAINTS["max_cells"] // cols + 100

        csv_lines = [",".join([f"col{i}" for i in range(cols)])]
        csv_lines.extend([",".join([str(j * cols + i) for i in range(cols)]) for j in range(rows)])
        large_csv = "\n".join(csv_lines)

        result = validator.validate(large_csv, "csv")

        assert result.metadata.sampled is True
        total_cells = result.metadata.rows * result.metadata.cols
        assert total_cells <= DATA_CONSTRAINTS["max_cells"]
        assert len(result.warnings) > 0

    def test_empty_dataframe_handling(self, validator):
        """Test handling of CSV that results in empty DataFrame."""
        empty_csv = "col1,col2,col3\n"  # Header only

        result = validator.validate(empty_csv, "csv")
        # Polars will create a DataFrame with 0 rows but columns defined
        assert result.metadata.rows == 0
        assert result.metadata.cols == 3

    def test_json_invalid_structure(self, validator):
        """Test JSON with invalid structure."""
        invalid_json = json.dumps("just a string")

        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(invalid_json, "json")
        assert exc_info.value.code == ErrorCode.E422_UNPROCESSABLE

    def test_equidistant_sampling_indices(self, validator):
        """Test that equidistant sampling selects correct indices."""
        # Create a simple DataFrame to test sampling
        test_dataframe = pl.DataFrame({"id": range(100), "value": range(100, 200)})

        # Apply sampling with target of 10 rows
        validator.constraints["max_rows"] = 10
        sampled = validator._apply_deterministic_sampling(test_dataframe)  # noqa: SLF001

        assert len(sampled) == 10
        # Check that samples are evenly distributed
        ids = sampled["id"].to_list()
        # First and last should be included
        assert ids[0] == 0
        assert ids[-1] == 99
        # Check roughly equidistant
        for i in range(1, len(ids)):
            assert ids[i] > ids[i - 1]

    def test_sampling_edge_cases(self, validator):
        """Test edge cases in deterministic sampling."""
        # Test empty DataFrame
        empty_df = pl.DataFrame({"col": []})
        sampled = validator._apply_deterministic_sampling(empty_df)  # noqa: SLF001
        assert len(sampled) == 0

        # Test single row
        single_df = pl.DataFrame({"col": [1]})
        sampled = validator._apply_deterministic_sampling(single_df)  # noqa: SLF001
        assert len(sampled) == 1
        assert sampled["col"].to_list() == [1]

        # Test two rows with target of 1
        two_df = pl.DataFrame({"col": [1, 2]})
        validator.constraints["max_rows"] = 1
        sampled = validator._apply_deterministic_sampling(two_df)  # noqa: SLF001
        assert len(sampled) == 1
        assert sampled["col"].to_list() == [1]  # Should return first row

        # Test two rows with target of 2
        validator.constraints["max_rows"] = 2
        sampled = validator._apply_deterministic_sampling(two_df)  # noqa: SLF001
        assert len(sampled) == 2
        assert sampled["col"].to_list() == [1, 2]

        # Test exact match of rows to target
        validator.constraints["max_rows"] = 5
        exact_df = pl.DataFrame({"col": range(5)})
        sampled = validator._apply_deterministic_sampling(exact_df)  # noqa: SLF001
        assert len(sampled) == 5
        assert sampled["col"].to_list() == list(range(5))

    def test_sampling_preserves_first_and_last(self, validator):
        """Test that sampling always includes first and last rows."""
        for size in [10, 50, 100, 1000]:
            test_df = pl.DataFrame({"id": range(size), "value": [f"val_{i}" for i in range(size)]})

            for target in [2, 5, 10, 20]:
                if target >= size:
                    continue

                validator.constraints["max_rows"] = target
                sampled = validator._apply_deterministic_sampling(test_df)  # noqa: SLF001

                ids = sampled["id"].to_list()
                # First and last rows must be included
                assert ids[0] == 0, f"First row missing for size={size}, target={target}"
                assert ids[-1] == size - 1, f"Last row missing for size={size}, target={target}"
                # Check ascending order
                assert ids == sorted(ids), f"Rows not in order for size={size}, target={target}"

    def test_sampling_distribution(self, validator):
        """Test that sampled rows are evenly distributed."""
        test_df = pl.DataFrame({"id": range(1000)})
        validator.constraints["max_rows"] = 10

        sampled = validator._apply_deterministic_sampling(test_df)  # noqa: SLF001
        ids = sampled["id"].to_list()

        # Check that the gaps between samples are roughly equal
        gaps = [ids[i] - ids[i - 1] for i in range(1, len(ids))]
        avg_gap = sum(gaps) / len(gaps)

        # All gaps should be within 50% of average (allowing for rounding)
        for gap in gaps:
            assert 0.5 * avg_gap <= gap <= 1.5 * avg_gap, f"Uneven distribution: gap={gap}, avg={avg_gap}"

    def test_sampling_with_multiple_columns(self, validator):
        """Test sampling with multiple columns and cell limit."""
        # Create DataFrame with 50 columns and 1000 rows (50,000 cells)
        data = {f"col_{i}": range(1000) for i in range(50)}
        test_df = pl.DataFrame(data)

        # Set max_cells to 10,000 (should result in 200 rows max)
        validator.constraints["max_cells"] = 10_000
        validator.constraints["max_rows"] = 500  # Higher than cell limit allows

        sampled = validator._apply_deterministic_sampling(test_df)  # noqa: SLF001

        # Should be limited by max_cells / columns = 10,000 / 50 = 200
        assert len(sampled) <= 200
        assert len(sampled.columns) == 50  # All columns preserved

        # Verify first and last rows
        assert sampled["col_0"].to_list()[0] == 0
        assert sampled["col_0"].to_list()[-1] == 999

    def test_deterministic_sampling_consistency(self, validator):
        """Test that sampling produces consistent results across multiple runs."""
        # Create various test DataFrames
        test_cases = [
            (100, 10),  # 100 rows, sample 10
            (1000, 50),  # 1000 rows, sample 50
            (10000, 100),  # 10000 rows, sample 100
            (57, 13),  # Prime numbers for edge case
        ]

        for total_rows, target_rows in test_cases:
            test_df = pl.DataFrame(
                {
                    "id": range(total_rows),
                    "value": [f"v_{i}" for i in range(total_rows)],
                    "number": [i * 2.5 for i in range(total_rows)],
                }
            )

            validator.constraints["max_rows"] = target_rows

            # Run sampling multiple times
            results = []
            for _ in range(5):
                sampled = validator._apply_deterministic_sampling(test_df)  # noqa: SLF001
                results.append(sampled["id"].to_list())

            # All results should be identical
            first_result = results[0]
            for i, result in enumerate(results[1:], 1):
                assert (
                    result == first_result
                ), f"Inconsistent sampling for rows={total_rows}, target={target_rows}, iteration={i}"
