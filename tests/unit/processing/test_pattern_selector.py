"""Unit tests for PatternSelector component."""

import json
from unittest.mock import MagicMock, patch

import pytest

from chartelier.core.enums import PatternID
from chartelier.core.models import DataMetadata
from chartelier.infra.llm_client import MockLLMClient
from chartelier.processing.pattern_selector import PatternSelection, PatternSelectionError, PatternSelector


class TestPatternSelector:
    """Test cases for PatternSelector."""

    @pytest.fixture
    def sample_metadata(self) -> DataMetadata:
        """Create sample data metadata."""
        return DataMetadata(
            rows=1000,
            cols=5,
            dtypes={
                "date": "datetime",
                "sales": "float",
                "region": "string",
                "product": "string",
                "quantity": "integer",
            },
            has_datetime=True,
            has_category=True,
            null_ratio={"date": 0.0, "sales": 0.05, "region": 0.0, "product": 0.0, "quantity": 0.02},
            sampled=False,
        )

    def test_ut_ps_001_successful_pattern_selection(self, sample_metadata: DataMetadata) -> None:
        """UT-PS-001: Test successful pattern selection with valid response."""
        # Arrange
        mock_response = json.dumps(
            {
                "pattern_id": "P12",
                "reasoning": "Multiple time series comparison for sales by region",
                "confidence": 0.9,
            }
        )
        mock_client = MockLLMClient(default_response=mock_response)
        selector = PatternSelector(llm_client=mock_client)

        # Act
        result = selector.select(sample_metadata, "Compare sales trends across regions")

        # Assert
        assert isinstance(result, PatternSelection)
        assert result.pattern_id == PatternID.P12
        assert result.reasoning == "Multiple time series comparison for sales by region"
        assert result.confidence == 0.9
        assert mock_client.call_count == 1

    def test_ut_ps_002_llm_timeout_handling(self, sample_metadata: DataMetadata) -> None:
        """UT-PS-002: Test proper error handling when LLM times out."""
        # Arrange
        mock_client = MockLLMClient(simulate_timeout=True)
        selector = PatternSelector(llm_client=mock_client)

        # Act & Assert
        with pytest.raises(PatternSelectionError) as exc_info:
            selector.select(sample_metadata, "Show sales trend")

        error = exc_info.value
        assert error.code.value == "E422_UNPROCESSABLE"
        assert "timed out" in error.message.lower()
        assert "try simplifying" in error.hint.lower()

    def test_ut_ps_003_invalid_response_handling(self, sample_metadata: DataMetadata) -> None:
        """UT-PS-003: Test error handling for invalid LLM responses."""
        # Test invalid JSON
        mock_client = MockLLMClient(default_response="Not a JSON response")
        selector = PatternSelector(llm_client=mock_client)

        with pytest.raises(PatternSelectionError) as exc_info:
            selector.select(sample_metadata, "Show data")

        error = exc_info.value
        assert "Invalid response format" in error.message

        # Test invalid pattern_id
        mock_response = json.dumps({"pattern_id": "P99", "reasoning": "Invalid pattern"})
        mock_client = MockLLMClient(default_response=mock_response)
        selector = PatternSelector(llm_client=mock_client)

        with pytest.raises(PatternSelectionError) as exc_info:
            selector.select(sample_metadata, "Show data")

        error = exc_info.value
        assert "Invalid response format" in error.message

    def test_ut_ps_004_structured_error_response(self, sample_metadata: DataMetadata) -> None:
        """UT-PS-004: Test that errors have proper structure and details."""
        # Arrange
        mock_client = MockLLMClient(simulate_error=True)
        selector = PatternSelector(llm_client=mock_client)

        # Act & Assert
        with pytest.raises(PatternSelectionError) as exc_info:
            selector.select(sample_metadata, "Visualize data")

        error = exc_info.value
        assert error.code.value == "E422_UNPROCESSABLE"
        assert error.hint is not None
        assert len(error.details) > 0
        assert error.details[0].field == "pattern_selection"

    def test_ut_ps_005_metadata_utilization(self, sample_metadata: DataMetadata) -> None:
        """UT-PS-005: Test that metadata is properly utilized in pattern selection."""
        # Arrange
        mock_response = json.dumps({"pattern_id": "P01", "reasoning": "Time series trend"})
        mock_client = MockLLMClient(default_response=mock_response)
        selector = PatternSelector(llm_client=mock_client)

        # Act
        selector.select(sample_metadata, "Show trend")

        # Assert
        # Check that the prompt includes metadata information
        assert mock_client.last_messages is not None
        user_message = next((m for m in mock_client.last_messages if m.role == "user"), None)
        assert user_message is not None
        prompt = user_message.content

        # Verify metadata is included in prompt
        assert "1,000" in prompt  # Row count
        assert "5" in prompt  # Column count
        assert "datetime" in prompt.lower()  # Has datetime
        assert "categorical" in prompt.lower() or "string" in prompt.lower()  # Has category

    def test_pattern_selection_all_patterns(self, sample_metadata: DataMetadata) -> None:
        """Test that all pattern IDs can be successfully selected."""
        for pattern_id in PatternID:
            # Arrange
            mock_response = json.dumps(
                {
                    "pattern_id": pattern_id.value,
                    "reasoning": f"Selected {pattern_id.value}",
                    "confidence": 0.8,
                }
            )
            mock_client = MockLLMClient(default_response=mock_response)
            selector = PatternSelector(llm_client=mock_client)

            # Act
            result = selector.select(sample_metadata, f"Query for {pattern_id.value}")

            # Assert
            assert result.pattern_id == pattern_id

    def test_confidence_validation(self, sample_metadata: DataMetadata) -> None:
        """Test confidence score validation."""
        # Test out of range confidence (should be ignored but not fail)
        mock_response = json.dumps(
            {
                "pattern_id": "P01",
                "reasoning": "Test",
                "confidence": 1.5,  # Out of range
            }
        )
        mock_client = MockLLMClient(default_response=mock_response)
        selector = PatternSelector(llm_client=mock_client)

        result = selector.select(sample_metadata, "Test query")
        assert result.pattern_id == PatternID.P01
        assert result.confidence is None  # Invalid confidence should be ignored

        # Test invalid confidence type
        mock_response = json.dumps(
            {
                "pattern_id": "P02",
                "reasoning": "Test",
                "confidence": "high",  # Invalid type
            }
        )
        mock_client = MockLLMClient(default_response=mock_response)
        selector = PatternSelector(llm_client=mock_client)

        result = selector.select(sample_metadata, "Test query")
        assert result.pattern_id == PatternID.P02
        assert result.confidence is None

    def test_missing_optional_fields(self, sample_metadata: DataMetadata) -> None:
        """Test that optional fields can be missing."""
        # Response with only required field
        mock_response = json.dumps({"pattern_id": "P03"})
        mock_client = MockLLMClient(default_response=mock_response)
        selector = PatternSelector(llm_client=mock_client)

        result = selector.select(sample_metadata, "Show distribution")
        assert result.pattern_id == PatternID.P03
        assert result.reasoning is None
        assert result.confidence is None

    def test_data_info_formatting(self) -> None:
        """Test data info formatting with various metadata configurations."""
        selector = PatternSelector(llm_client=MockLLMClient())

        # Test with minimal metadata
        metadata = DataMetadata(
            rows=10,
            cols=2,
            dtypes={"col1": "integer", "col2": "float"},
            has_datetime=False,
            has_category=False,
            null_ratio={"col1": 0.0, "col2": 0.1},
            sampled=False,
        )

        # Test the _format_data_info method (accessing for test purposes)
        # This is acceptable for testing internal behavior
        data_info = selector._format_data_info(metadata)  # noqa: SLF001
        assert "Rows: 10" in data_info
        assert "Columns: 2" in data_info
        assert "datetime" not in data_info.lower() or "Contains datetime" not in data_info

        # Test with many columns (should truncate)
        many_cols = {f"col{i}": "float" for i in range(20)}
        metadata = DataMetadata(
            rows=1000,
            cols=20,
            dtypes=many_cols,
            has_datetime=True,
            has_category=True,
            null_ratio=dict.fromkeys(many_cols, 0.0),
            sampled=True,
            original_rows=5000,
        )

        # Test the _format_data_info method (accessing for test purposes)
        data_info = selector._format_data_info(metadata)  # noqa: SLF001
        assert "and 10 more columns" in data_info
        assert "Contains datetime" in data_info
        assert "Contains categorical" in data_info

    def test_model_parameter_default(self, sample_metadata: DataMetadata) -> None:
        """Test that default model is gpt-4o-mini."""
        mock_response = json.dumps({"pattern_id": "P01", "reasoning": "Test"})
        mock_client = MockLLMClient(default_response=mock_response)
        selector = PatternSelector(llm_client=mock_client)

        # Check default model is set
        assert selector.model == "gpt-4o-mini"

        # Execute selection and verify model is passed to LLM client
        selector.select(sample_metadata, "Test query")
        assert mock_client.last_kwargs.get("model") == "gpt-4o-mini"

    def test_model_parameter_custom(self, sample_metadata: DataMetadata) -> None:
        """Test using a custom model."""
        mock_response = json.dumps({"pattern_id": "P02", "reasoning": "Test"})
        mock_client = MockLLMClient(default_response=mock_response)
        custom_model = "gpt-4-turbo"
        selector = PatternSelector(llm_client=mock_client, model=custom_model)

        # Check custom model is set
        assert selector.model == custom_model

        # Execute selection and verify model is passed to LLM client
        selector.select(sample_metadata, "Test query")
        assert mock_client.last_kwargs.get("model") == custom_model

    @patch("chartelier.processing.pattern_selector.processor.PromptTemplate")
    def test_model_to_prompt_version_mapping(
        self, mock_template_class: MagicMock, sample_metadata: DataMetadata
    ) -> None:
        """Test that model-specific prompt versions are loaded correctly."""
        # Setup mock
        mock_template_instance = MagicMock()
        mock_template_class.from_component.return_value = mock_template_instance

        # Test gpt-4o-mini uses v0.1.0
        mock_client = MockLLMClient()
        PatternSelector(llm_client=mock_client, model="gpt-4o-mini")

        # Verify from_component was called with v0.1.0
        call_args = mock_template_class.from_component.call_args
        assert call_args[0][1] == "v0.1.0"

        # Reset mock
        mock_template_class.reset_mock()

        # Test unknown model uses default version
        PatternSelector(llm_client=mock_client, model="claude-3-opus")
        call_args = mock_template_class.from_component.call_args
        assert call_args[0][1] == "v0.1.0"  # Should use default

    def test_prompt_version_constants(self) -> None:
        """Test that class constants are properly defined."""
        assert PatternSelector.DEFAULT_MODEL == "gpt-4o-mini"
        assert PatternSelector.DEFAULT_PROMPT_VERSION == "v0.1.0"
        assert "gpt-4o-mini" in PatternSelector.MODEL_PROMPT_VERSIONS
        assert PatternSelector.MODEL_PROMPT_VERSIONS["gpt-4o-mini"] == "v0.1.0"
