"""Unit tests for ChartSelector component."""

import json
from unittest.mock import MagicMock, Mock

import pytest

from chartelier.core.chart_builder.builder import ChartBuilder, ChartSpec
from chartelier.core.enums import AuxiliaryElement, PatternID
from chartelier.core.models import DataMetadata
from chartelier.infra.llm_client import MockLLMClient
from chartelier.processing.chart_selector import ChartSelection, ChartSelector


class TestChartSelector:
    """Test cases for ChartSelector."""

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

    @pytest.fixture
    def mock_chart_builder(self) -> Mock:
        """Create mock ChartBuilder."""
        mock = Mock(spec=ChartBuilder)

        # Setup get_available_charts to return different charts for different patterns
        def get_available_charts(pattern_id: PatternID) -> list[ChartSpec]:
            if pattern_id == PatternID.P01:
                return [
                    ChartSpec("P01_line", "Line Chart", [PatternID.P01]),
                    ChartSpec("P01_area", "Area Chart", [PatternID.P01]),
                ]
            if pattern_id == PatternID.P02:
                return [ChartSpec("P02_bar", "Bar Chart", [PatternID.P02])]
            return [ChartSpec(f"{pattern_id.value}_default", "Default Chart", [pattern_id])]

        mock.get_available_charts.side_effect = get_available_charts

        # Setup get_template_spec
        mock_spec = MagicMock()
        mock_spec.allowed_auxiliary = [
            AuxiliaryElement.MEAN_LINE,
            AuxiliaryElement.REGRESSION,
            AuxiliaryElement.ANNOTATION,
        ]
        mock.get_template_spec.return_value = mock_spec

        return mock

    def test_ut_cs_001_successful_chart_selection(
        self, sample_metadata: DataMetadata, mock_chart_builder: Mock
    ) -> None:
        """UT-CS-001: Test successful chart selection with LLM."""
        # Arrange
        mock_response = json.dumps({"template_id": "P01_line", "reasoning": "Line chart best for time series"})
        mock_client = MockLLMClient(default_response=mock_response)
        selector = ChartSelector(llm_client=mock_client, chart_builder=mock_chart_builder)

        # Act
        result = selector.select_chart(PatternID.P01, sample_metadata, "Show sales trend over time")

        # Assert
        assert isinstance(result, ChartSelection)
        assert result.template_id == "P01_line"
        assert result.reasoning == "Line chart best for time series"
        assert result.fallback_applied is False
        assert mock_client.call_count == 1

    def test_ut_cs_002_llm_timeout_fallback(self, sample_metadata: DataMetadata, mock_chart_builder: Mock) -> None:
        """UT-CS-002: Test fallback when LLM times out."""
        # Arrange
        mock_client = MockLLMClient(simulate_timeout=True)
        selector = ChartSelector(llm_client=mock_client, chart_builder=mock_chart_builder)

        # Act
        result = selector.select_chart(PatternID.P01, sample_metadata, "Show trend")

        # Assert
        assert isinstance(result, ChartSelection)
        assert result.template_id == "P01_line"  # First available chart
        assert result.fallback_applied is True
        assert "Fallback" in result.reasoning

    def test_ut_cs_003_invalid_response_fallback(self, sample_metadata: DataMetadata, mock_chart_builder: Mock) -> None:
        """UT-CS-003: Test fallback for invalid LLM responses."""
        # Test invalid JSON
        mock_client = MockLLMClient(default_response="Not JSON")
        selector = ChartSelector(llm_client=mock_client, chart_builder=mock_chart_builder)

        result = selector.select_chart(PatternID.P01, sample_metadata)
        assert result.fallback_applied is True
        assert result.template_id == "P01_line"

        # Test invalid template_id
        mock_response = json.dumps({"template_id": "P99_invalid", "reasoning": "Invalid"})
        mock_client = MockLLMClient(default_response=mock_response)
        selector = ChartSelector(llm_client=mock_client, chart_builder=mock_chart_builder)

        result = selector.select_chart(PatternID.P01, sample_metadata)
        assert result.fallback_applied is True
        assert result.template_id == "P01_line"

    def test_ut_cs_004_auxiliary_selection(self, sample_metadata: DataMetadata, mock_chart_builder: Mock) -> None:
        """UT-CS-004: Test auxiliary element selection with constraints."""
        # Test successful selection
        mock_response = json.dumps(
            {
                "auxiliary": ["mean_line", "regression"],
                "reasoning": "Mean line and regression show trend",
            }
        )
        mock_client = MockLLMClient(default_response=mock_response)
        selector = ChartSelector(llm_client=mock_client, chart_builder=mock_chart_builder)

        result = selector.select_auxiliary("P01_line", "Show trend with average", sample_metadata)
        assert len(result) == 2
        assert "mean_line" in result
        assert "regression" in result

        # Test max 3 elements constraint
        mock_response = json.dumps(
            {
                "auxiliary": ["mean_line", "regression", "annotation", "median_line", "target_line"],
                "reasoning": "Multiple elements",
            }
        )
        mock_client = MockLLMClient(default_response=mock_response)
        selector = ChartSelector(llm_client=mock_client, chart_builder=mock_chart_builder)

        result = selector.select_auxiliary("P01_line", "Add many annotations")
        assert len(result) <= 3  # Should be limited to max 3

        # Test filtering invalid elements
        mock_response = json.dumps(
            {
                "auxiliary": ["mean_line", "invalid_element", "regression"],
                "reasoning": "Some invalid",
            }
        )
        mock_client = MockLLMClient(default_response=mock_response)
        selector = ChartSelector(llm_client=mock_client, chart_builder=mock_chart_builder)

        result = selector.select_auxiliary("P01_line", "Add elements")
        assert "invalid_element" not in result
        assert "mean_line" in result
        assert "regression" in result

    def test_single_chart_option(self, sample_metadata: DataMetadata, mock_chart_builder: Mock) -> None:
        """Test behavior when only one chart option is available."""
        # Arrange
        mock_client = MockLLMClient()
        selector = ChartSelector(llm_client=mock_client, chart_builder=mock_chart_builder)

        # Act - P02 has only one chart
        result = selector.select_chart(PatternID.P02, sample_metadata)

        # Assert
        assert result.template_id == "P02_bar"
        assert result.fallback_applied is False
        assert "Only one chart type available" in result.reasoning
        assert mock_client.call_count == 0  # LLM should not be called

    def test_no_charts_available(self, sample_metadata: DataMetadata) -> None:
        """Test behavior when no charts are available for pattern."""
        # Arrange
        mock_builder = Mock(spec=ChartBuilder)
        mock_builder.get_available_charts.return_value = []
        mock_client = MockLLMClient()
        selector = ChartSelector(llm_client=mock_client, chart_builder=mock_builder)

        # Act
        result = selector.select_chart(PatternID.P31, sample_metadata)

        # Assert
        assert result.fallback_applied is True
        assert "P31_default" in result.template_id

    def test_auxiliary_with_no_template_spec(self, mock_chart_builder: Mock) -> None:
        """Test auxiliary selection when template spec is not found."""
        # Arrange
        mock_chart_builder.get_template_spec.return_value = None
        mock_client = MockLLMClient()
        selector = ChartSelector(llm_client=mock_client, chart_builder=mock_chart_builder)

        # Act
        result = selector.select_auxiliary("unknown_template", "Add auxiliary")

        # Assert
        assert result == []

    def test_auxiliary_with_no_allowed_elements(self, mock_chart_builder: Mock) -> None:
        """Test auxiliary selection when no elements are allowed."""
        # Arrange
        mock_spec = MagicMock()
        mock_spec.allowed_auxiliary = []
        mock_chart_builder.get_template_spec.return_value = mock_spec
        mock_client = MockLLMClient()
        selector = ChartSelector(llm_client=mock_client, chart_builder=mock_chart_builder)

        # Act
        result = selector.select_auxiliary("P01_line", "Add auxiliary")

        # Assert
        assert result == []

    def test_auxiliary_llm_failure(self, sample_metadata: DataMetadata, mock_chart_builder: Mock) -> None:
        """Test auxiliary selection when LLM fails."""
        # Arrange
        mock_client = MockLLMClient(simulate_timeout=True)
        selector = ChartSelector(llm_client=mock_client, chart_builder=mock_chart_builder)

        # Act
        result = selector.select_auxiliary("P01_line", "Add auxiliary", sample_metadata)

        # Assert
        assert result == []  # Should return empty list on failure

    def test_data_info_formatting(self) -> None:
        """Test data info formatting for prompts."""
        selector = ChartSelector(llm_client=MockLLMClient())

        # Test with various metadata
        metadata = DataMetadata(
            rows=5000,
            cols=10,
            dtypes={f"col{i}": "float" for i in range(5)} | {f"cat{i}": "string" for i in range(5)},
            has_datetime=True,
            has_category=True,
            null_ratio={},
            sampled=True,
        )

        # Access internal method for testing
        data_info = selector._format_data_info(metadata)  # noqa: SLF001

        assert "5,000" in data_info
        assert "10" in data_info
        assert "Float columns: 5" in data_info
        assert "String columns: 5" in data_info
        assert "temporal data" in data_info
        assert "categorical data" in data_info

    def test_model_configuration(self, sample_metadata: DataMetadata, mock_chart_builder: Mock) -> None:
        """Test model configuration for ChartSelector."""
        # Test default model
        selector = ChartSelector(chart_builder=mock_chart_builder)
        assert selector.model == "gpt-5-mini"

        # Test custom model
        custom_model = "gpt-4-turbo"
        selector = ChartSelector(chart_builder=mock_chart_builder, model=custom_model)
        assert selector.model == custom_model

        # Verify model is passed to LLM
        mock_response = json.dumps({"template_id": "P01_line"})
        mock_client = MockLLMClient(default_response=mock_response)
        selector = ChartSelector(llm_client=mock_client, chart_builder=mock_chart_builder, model=custom_model)

        selector.select_chart(PatternID.P01, sample_metadata)
        assert mock_client.last_kwargs.get("model") == custom_model

    def test_auxiliary_descriptions(self) -> None:
        """Test auxiliary element descriptions."""
        selector = ChartSelector(llm_client=MockLLMClient())

        # Test known elements
        desc = selector._get_auxiliary_description(AuxiliaryElement.MEAN_LINE)  # noqa: SLF001
        assert "average" in desc.lower()

        desc = selector._get_auxiliary_description(AuxiliaryElement.REGRESSION)  # noqa: SLF001
        assert "trend" in desc.lower()

        # Test that all auxiliary elements have descriptions
        for element in AuxiliaryElement:
            desc = selector._get_auxiliary_description(element)  # noqa: SLF001
            # Should return non-empty string for known elements
            assert isinstance(desc, str)
