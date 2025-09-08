"""Integration tests for PatternSelector with other components."""

import json
import textwrap

import polars as pl
import pytest

from chartelier.core.enums import PatternID
from chartelier.core.errors import ChartelierError
from chartelier.infra.llm_client import MockLLMClient
from chartelier.processing.data_validator import DataValidator
from chartelier.processing.pattern_selector import PatternSelectionError, PatternSelector


class TestPatternSelectorIntegration:
    """Integration tests for PatternSelector."""

    @pytest.fixture
    def sample_csv_data(self) -> str:
        """Create sample CSV data."""
        return textwrap.dedent("""\
            date,sales,region,product
            2024-01-01,1000.50,North,Widget A
            2024-01-02,1200.75,South,Widget B
            2024-01-03,950.25,East,Widget A
            2024-01-04,1100.00,West,Widget C
            2024-01-05,1300.50,North,Widget B\
        """)

    @pytest.fixture
    def sample_json_data(self) -> str:
        """Create sample JSON data."""
        return json.dumps(
            [
                {"month": "2024-01", "revenue": 50000, "department": "Sales"},
                {"month": "2024-02", "revenue": 55000, "department": "Sales"},
                {"month": "2024-03", "revenue": 48000, "department": "Marketing"},
                {"month": "2024-04", "revenue": 52000, "department": "Marketing"},
            ]
        )

    def test_pattern_selection_with_validated_csv_data(self, sample_csv_data: str) -> None:
        """Test pattern selection with data validated by DataValidator (CSV)."""
        # Validate data
        validator = DataValidator()
        validated_data = validator.validate(sample_csv_data, "csv")

        # Setup mock LLM for pattern selection
        mock_response = json.dumps(
            {
                "pattern_id": "P12",
                "reasoning": "Multiple time series comparison for sales by region",
                "confidence": 0.85,
            }
        )
        mock_client = MockLLMClient(default_response=mock_response)
        selector = PatternSelector(llm_client=mock_client)

        # Select pattern
        result = selector.select(validated_data.metadata, "Compare sales trends by region")

        # Verify
        assert result.pattern_id == PatternID.P12
        assert result.confidence == 0.85
        assert validated_data.metadata.has_datetime is True
        # Note: has_category may be False if strings are all unique

    def test_pattern_selection_with_validated_json_data(self, sample_json_data: str) -> None:
        """Test pattern selection with data validated by DataValidator (JSON)."""
        # Validate data
        validator = DataValidator()
        validated_data = validator.validate(sample_json_data, "json")

        # Setup mock LLM for pattern selection
        mock_response = json.dumps(
            {
                "pattern_id": "P21",
                "reasoning": "Department revenue differences over time",
                "confidence": 0.9,
            }
        )
        mock_client = MockLLMClient(default_response=mock_response)
        selector = PatternSelector(llm_client=mock_client)

        # Select pattern
        result = selector.select(validated_data.metadata, "Show revenue differences by department over time")

        # Verify
        assert result.pattern_id == PatternID.P21
        assert result.confidence == 0.9

    def test_pattern_selection_with_large_sampled_data(self) -> None:
        """Test pattern selection with large data that gets sampled."""
        # Create large dataset that will trigger sampling
        # Generate timestamp data (15000 rows by repeating dates)
        base_dates = pl.date_range(
            pl.date(2020, 1, 1),
            pl.date(2024, 1, 1),
            interval="1d",
            eager=True,
        )
        # Repeat dates to get 15000 rows
        timestamps = base_dates.sample(n=15000, with_replacement=True, seed=42).sort()

        large_data = pl.DataFrame(
            {
                "timestamp": timestamps,
                "value": list(range(15000)),
                "category": ["A", "B", "C"] * 5000,
            }
        )

        # Convert to CSV string
        csv_data = large_data.write_csv()

        # Validate (will trigger sampling)
        validator = DataValidator()
        validated_data = validator.validate(csv_data, "csv")

        # Verify sampling occurred
        assert validated_data.metadata.sampled is True
        assert validated_data.metadata.original_rows == 15000
        assert validated_data.metadata.rows < 15000

        # Setup mock LLM
        mock_response = json.dumps(
            {
                "pattern_id": "P01",
                "reasoning": "Single time series trend",
                "confidence": 0.95,
            }
        )
        mock_client = MockLLMClient(default_response=mock_response)
        selector = PatternSelector(llm_client=mock_client)

        # Select pattern
        result = selector.select(validated_data.metadata, "Show value trend over time")

        # Verify
        assert result.pattern_id == PatternID.P01
        # Verify the prompt mentions sampling
        assert mock_client.last_messages is not None
        user_msg = next((m for m in mock_client.last_messages if m.role == "user"), None)
        assert user_msg is not None
        # The row count in prompt should be the sampled count
        assert str(validated_data.metadata.rows) in user_msg.content.replace(",", "")

    def test_pattern_selection_different_data_types(self) -> None:
        """Test pattern selection with different data type combinations."""
        test_cases = [
            # Pure numeric data
            (
                {"values": [1, 2, 3, 4, 5]},
                "Show distribution of values",
                PatternID.P03,
            ),
            # Time series data
            (
                {
                    "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
                    "metric": [100, 110, 105],
                },
                "Show metric trend",
                PatternID.P01,
            ),
            # Categorical comparison
            (
                {
                    "category": ["A", "B", "C", "A", "B"],
                    "score": [10, 20, 15, 12, 22],
                },
                "Compare scores by category",
                PatternID.P02,
            ),
        ]

        for data_dict, query, expected_pattern in test_cases:
            # Create DataFrame
            df = pl.DataFrame(data_dict)
            json_data = df.write_json()  # Default is row-oriented

            # Validate
            validator = DataValidator()
            validated_data = validator.validate(json_data, "json")

            # Mock LLM response
            mock_response = json.dumps(
                {
                    "pattern_id": expected_pattern.value,
                    "reasoning": f"Test case for {expected_pattern.value}",
                    "confidence": 0.8,
                }
            )
            mock_client = MockLLMClient(default_response=mock_response)
            selector = PatternSelector(llm_client=mock_client)

            # Select pattern
            result = selector.select(validated_data.metadata, query)
            assert result.pattern_id == expected_pattern

    def test_error_propagation_from_pattern_selector(self) -> None:
        """Test that PatternSelectionError is properly raised and contains expected information."""
        # Create valid data
        data = json.dumps([{"x": 1, "y": 2}, {"x": 3, "y": 4}])
        validator = DataValidator()
        validated_data = validator.validate(data, "json")

        # Setup selector with timeout simulation
        mock_client = MockLLMClient(simulate_timeout=True)
        selector = PatternSelector(llm_client=mock_client)

        # Verify error is raised with proper structure
        with pytest.raises(PatternSelectionError) as exc_info:
            selector.select(validated_data.metadata, "Visualize data")

        error = exc_info.value
        assert error.code.value == "E422_UNPROCESSABLE"
        assert "timed out" in error.message.lower()
        assert error.hint is not None
        assert len(error.details) > 0

    def test_pattern_selection_with_empty_valid_data(self) -> None:
        """Test pattern selection with empty but valid data."""
        # Create empty DataFrame with columns
        empty_data = json.dumps([])

        # This should fail validation (no rows)
        validator = DataValidator()
        with pytest.raises(ChartelierError):  # More specific exception
            validator.validate(empty_data, "json")

    def test_pattern_selection_metadata_edge_cases(self) -> None:
        """Test pattern selection with edge case metadata."""
        # All null values
        data_with_nulls = pl.DataFrame(
            {
                "col1": [None, None, None],
                "col2": [1.0, None, 3.0],
            }
        )
        csv_data = data_with_nulls.write_csv()

        validator = DataValidator()
        validated_data = validator.validate(csv_data, "csv")

        # High null ratio should be reflected in metadata
        assert validated_data.metadata.null_ratio["col1"] == 1.0
        assert validated_data.metadata.null_ratio["col2"] > 0

        # Mock response
        mock_response = json.dumps(
            {
                "pattern_id": "P03",
                "reasoning": "Distribution analysis despite nulls",
                "confidence": 0.6,
            }
        )
        mock_client = MockLLMClient(default_response=mock_response)
        selector = PatternSelector(llm_client=mock_client)

        # Should still work
        result = selector.select(validated_data.metadata, "Analyze distribution")
        assert result.pattern_id == PatternID.P03
        assert result.confidence == 0.6
