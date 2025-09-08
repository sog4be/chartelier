"""Integration tests for data flow through the system."""

import json
from textwrap import dedent

import polars as pl
import pytest

from chartelier.processing import DataValidator


class TestDataFlow:
    """Integration tests for data processing flow."""

    @pytest.fixture
    def validator(self):
        """Create a DataValidator instance."""
        return DataValidator()

    def test_csv_to_dataframe_flow(self, validator):
        """Test complete flow from CSV string to validated DataFrame."""
        # IT-DATA-010: CSV data flow
        csv_data = dedent("""\
            date,sales,region,product
            2024-01-01,1000,North,Widget
            2024-01-02,1500,South,Gadget
            2024-01-03,1200,North,Widget
            2024-01-04,1800,East,Gadget
            2024-01-05,900,West,Widget
            2024-01-06,2000,South,Gadget
            2024-01-07,1100,North,Widget
        """).strip()

        # Validate the data
        result = validator.validate(csv_data, "csv")

        # Verify the DataFrame is properly created
        assert isinstance(result.df, pl.DataFrame)
        assert len(result.df) == 7
        assert len(result.df.columns) == 4

        # Verify metadata
        assert result.metadata.rows == 7
        assert result.metadata.cols == 4
        assert result.metadata.has_datetime is True
        assert result.metadata.has_category is True
        assert not result.metadata.sampled

        # Verify data types are correctly detected
        assert "date" in result.metadata.dtypes
        assert result.metadata.dtypes["sales"] == "integer"
        assert result.metadata.dtypes["region"] == "string"
        assert result.metadata.dtypes["product"] == "string"

        # Verify no warnings for valid data
        assert len(result.warnings) == 0

    def test_json_to_dataframe_flow(self, validator):
        """Test complete flow from JSON string to validated DataFrame."""
        json_data = [
            {"timestamp": "2024-01-01T10:00:00", "temperature": 22.5, "humidity": 65, "location": "Room A"},
            {"timestamp": "2024-01-01T11:00:00", "temperature": 23.0, "humidity": 63, "location": "Room A"},
            {"timestamp": "2024-01-01T12:00:00", "temperature": 23.5, "humidity": 61, "location": "Room A"},
            {"timestamp": "2024-01-01T10:00:00", "temperature": 21.0, "humidity": 70, "location": "Room B"},
            {"timestamp": "2024-01-01T11:00:00", "temperature": 21.5, "humidity": 68, "location": "Room B"},
        ]

        # Validate the data
        result = validator.validate(json.dumps(json_data), "json")

        # Verify the DataFrame
        assert isinstance(result.df, pl.DataFrame)
        assert len(result.df) == 5
        assert len(result.df.columns) == 4

        # Verify metadata
        assert result.metadata.rows == 5
        assert result.metadata.cols == 4
        assert result.metadata.dtypes["temperature"] == "float"
        assert result.metadata.dtypes["humidity"] == "integer"
        assert result.metadata.dtypes["location"] == "string"

    def test_large_data_sampling_flow(self, validator):
        """Test flow with large data that triggers sampling."""
        # Create large dataset
        rows = 15000  # Exceeds max_rows
        csv_lines = ["id,value,category"]
        for i in range(rows):
            csv_lines.append(f"{i},{i * 10},Category{i % 5}")

        large_csv = "\n".join(csv_lines)

        # Validate with sampling
        result = validator.validate(large_csv, "csv")

        # Verify sampling occurred
        assert result.metadata.sampled is True
        assert result.metadata.rows <= 10000
        assert result.metadata.original_rows == rows
        assert len(result.warnings) == 1
        assert "sampled" in result.warnings[0]

        # Verify DataFrame is valid
        assert isinstance(result.df, pl.DataFrame)
        assert len(result.df) == result.metadata.rows
        assert len(result.df.columns) == 3

    def test_mixed_data_types_flow(self, validator):
        """Test flow with mixed data types."""
        csv_data = dedent("""\
            id,name,age,score,is_active,joined_date,tags
            1,Alice,25,85.5,true,2024-01-15,python;sql
            2,Bob,30,92.0,false,2024-02-20,java;spring
            3,Charlie,28,78.5,true,2024-01-10,javascript;react
            4,Diana,35,88.0,true,2024-03-01,python;django
            5,Eve,27,95.5,false,2024-02-15,go;kubernetes
        """).strip()

        result = validator.validate(csv_data, "csv")

        # Verify all columns are processed
        assert result.metadata.cols == 7

        # Verify type detection
        assert result.metadata.dtypes["id"] == "integer"
        assert result.metadata.dtypes["name"] == "string"
        assert result.metadata.dtypes["age"] == "integer"
        assert result.metadata.dtypes["score"] == "float"
        assert result.metadata.dtypes["is_active"] == "boolean"
        assert result.metadata.dtypes["joined_date"] == "datetime"
        assert result.metadata.dtypes["tags"] == "string"

        # Verify metadata flags
        assert result.metadata.has_datetime is True
        # No column qualifies as categorical (all unique values)

    def test_null_handling_flow(self, validator):
        """Test flow with null values."""
        csv_data = dedent("""\
            col1,col2,col3,col4
            1,2.5,hello,2024-01-01
            2,,world,2024-01-02
            ,3.5,test,
            4,4.5,,2024-01-04
            5,5.5,sample,
        """).strip()

        result = validator.validate(csv_data, "csv")

        # Verify null ratios are calculated
        assert result.metadata.null_ratio["col1"] == 0.2  # 1 null out of 5
        assert result.metadata.null_ratio["col2"] == 0.2  # 1 null out of 5
        assert result.metadata.null_ratio["col3"] == 0.2  # 1 null out of 5
        assert result.metadata.null_ratio["col4"] == 0.4  # 2 nulls out of 5

        # Verify DataFrame handles nulls properly
        assert result.df["col1"].null_count() == 1
        assert result.df["col2"].null_count() == 1
        assert result.df["col3"].null_count() == 1
        assert result.df["col4"].null_count() == 2

    def test_columnar_json_flow(self, validator):
        """Test flow with columnar JSON format."""
        json_data = {
            "dates": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "values": [100, 150, 200],
            "categories": ["A", "B", "A"],
        }

        result = validator.validate(json.dumps(json_data), "json")

        # Verify DataFrame structure
        assert len(result.df) == 3
        assert len(result.df.columns) == 3
        assert list(result.df.columns) == ["dates", "values", "categories"]

        # Verify data integrity
        assert result.df["values"].to_list() == [100, 150, 200]
        assert result.df["categories"].to_list() == ["A", "B", "A"]
