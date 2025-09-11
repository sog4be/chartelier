"""Unit tests for the Coordinator class."""

from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from chartelier.core.enums import ErrorCode, PatternID
from chartelier.core.errors import ChartelierError
from chartelier.core.models import DataMetadata
from chartelier.interfaces.validators import ValidatedRequest
from chartelier.orchestration import (
    Coordinator,
    PipelinePhase,
    ProcessingContext,
    VisualizationResult,
)
from chartelier.processing.data_validator import ValidatedData
from chartelier.processing.pattern_selector import PatternSelection, PatternSelectionError


class TestCoordinator:
    """Test Coordinator functionality."""

    def test_coordinator_initialization(self) -> None:
        """Test Coordinator initialization."""
        coordinator = Coordinator()
        assert coordinator is not None
        assert coordinator.logger is not None

    def test_process_with_mocked_pipeline(self) -> None:
        """Test full pipeline with mocked components."""
        coordinator = Coordinator()
        request = ValidatedRequest(
            data="x,y\n1,2\n3,4",
            query="Show a line chart",
            options={"format": "svg"},
            data_format="csv",
            data_size_bytes=13,
        )

        # Create test data
        test_df = pl.DataFrame({"x": [1, 3], "y": [2, 4]})
        test_metadata = DataMetadata(
            rows=2,
            cols=2,
            dtypes={"x": "int", "y": "int"},
            has_datetime=False,
            has_category=False,
            null_ratio={},
            sampled=False,
        )

        # Mock all components
        with (
            patch.object(coordinator.data_validator, "validate") as mock_validate,
            patch.object(coordinator.pattern_selector, "select") as mock_pattern,
            patch.object(coordinator.chart_selector, "select_chart") as mock_chart,
            patch.object(coordinator.chart_selector, "select_auxiliary") as mock_aux,
            patch.object(coordinator.data_processor, "process") as mock_process,
            patch.object(coordinator.data_mapper, "map") as mock_map,
            patch.object(coordinator.chart_builder, "build") as mock_build,
            patch.object(coordinator.chart_builder, "export") as mock_export,
            patch.object(coordinator.chart_builder, "get_template_spec") as mock_spec,
        ):
            # Setup mocks
            mock_validate.return_value = ValidatedData(
                df=test_df,
                metadata=test_metadata,
                warnings=[],
            )

            mock_pattern.return_value = PatternSelection(
                pattern_id=PatternID.P01,
                reasoning="Time series data",
            )

            mock_chart.return_value = MagicMock(
                template_id="line_chart",
            )

            mock_aux.return_value = MagicMock(
                auxiliary=[],
            )

            mock_process.return_value = MagicMock(
                df=test_df,
                operations_applied=["sort"],
            )

            mock_spec.return_value = MagicMock()

            # Return a MappingConfig-like object with proper attributes
            mock_mapping = MagicMock()
            mock_mapping.x = "x"
            mock_mapping.y = "y"
            mock_mapping.color = None
            mock_mapping.size = None
            mock_mapping.facet = None
            mock_mapping.row = None
            mock_mapping.column = None
            mock_map.return_value = mock_mapping

            mock_build.return_value = MagicMock()  # Chart object
            mock_export.return_value = "<svg>...</svg>"

            # Execute
            result = coordinator.process(request)

            # Verify result
            assert result.format == "svg"
            assert result.image_data == "<svg>...</svg>"
            assert result.error is None
            assert result.metadata["pattern_id"] == PatternID.P01.value
            assert result.metadata["template_id"] == "line_chart"
            assert result.metadata["stats"]["rows"] == 2
            assert result.metadata["stats"]["cols"] == 2

    def test_data_validation_with_csv(self) -> None:
        """Test data validation with CSV data."""
        coordinator = Coordinator()
        context = ProcessingContext(
            raw_data="x,y\n1,2\n3,4",
            data_format="csv",
            query="test",
            options={},
        )

        # Mock the validator to parse correctly
        test_df = pl.DataFrame({"x": [1, 3], "y": [2, 4]})
        test_metadata = DataMetadata(
            rows=2,
            cols=2,
            dtypes={"x": "int", "y": "int"},
            has_datetime=False,
            has_category=False,
            null_ratio={},
            sampled=False,
        )

        with patch.object(coordinator.data_validator, "validate") as mock_validate:
            mock_validate.return_value = ValidatedData(
                df=test_df,
                metadata=test_metadata,
                warnings=[],
            )

            coordinator._execute_data_validation(context)  # noqa: SLF001

            # Verify validate was called with raw data
            mock_validate.assert_called_once_with("x,y\n1,2\n3,4", "csv")

            # Verify context was updated
            assert context.parsed_data is not None
            assert isinstance(context.parsed_data, pl.DataFrame)
            assert context.data_metadata is not None
            assert context.rows_count == 2
            assert context.cols_count == 2

    def test_parse_data_methods(self) -> None:
        """Test internal data parsing methods."""
        coordinator = Coordinator()

        # Test CSV parsing
        context_csv = ProcessingContext(
            raw_data="x,y\n1,2\n3,4",
            data_format="csv",
            query="test",
            options={},
        )
        coordinator._parse_data(context_csv)  # noqa: SLF001
        assert context_csv.parsed_data is not None
        assert context_csv.rows_count == 2
        assert context_csv.cols_count == 2

        # Test JSON parsing
        context_json = ProcessingContext(
            raw_data='[{"x": 1, "y": 2}]',
            data_format="json",
            query="test",
            options={},
        )
        coordinator._parse_data(context_json)  # noqa: SLF001
        assert context_json.parsed_data is not None

        # Test invalid format
        context_invalid = ProcessingContext(
            raw_data="data",
            data_format="xml",
            query="test",
            options={},
        )
        with pytest.raises(ChartelierError) as exc_info:
            coordinator._parse_data(context_invalid)  # noqa: SLF001
        assert exc_info.value.code == ErrorCode.E415_UNSUPPORTED_FORMAT

    def test_processing_context_creation(self) -> None:
        """Test ProcessingContext model."""
        context = ProcessingContext(
            raw_data="x,y\n1,2",
            data_format="csv",
            query="Show data",
            options={"format": "png"},
        )

        assert context.raw_data == "x,y\n1,2"
        assert context.data_format == "csv"
        assert context.query == "Show data"
        assert context.options == {"format": "png"}

        # Check default values
        assert context.pattern_id is None
        assert context.template_id is None
        assert context.processed_data is None
        assert context.mapping_config is None
        assert context.auxiliary_config is None
        assert context.warnings == []
        assert context.processing_time_ms == {}
        assert context.fallback_applied is False
        assert context.data_sampled is False
        assert context.rows_count is None
        assert context.cols_count is None

    def test_pipeline_phase_enum(self) -> None:
        """Test PipelinePhase enum values."""
        assert PipelinePhase.DATA_VALIDATION.value == "data_validation"
        assert PipelinePhase.PATTERN_SELECTION.value == "pattern_selection"
        assert PipelinePhase.CHART_SELECTION.value == "chart_selection"
        assert PipelinePhase.DATA_PROCESSING.value == "data_processing"
        assert PipelinePhase.DATA_MAPPING.value == "data_mapping"
        assert PipelinePhase.CHART_BUILDING.value == "chart_building"

        # Check all phases are defined
        all_phases = list(PipelinePhase)
        assert len(all_phases) == 6

    def test_visualization_result_model(self) -> None:
        """Test VisualizationResult model."""
        # Test with error
        result_with_error = VisualizationResult(
            format="png",
            error={
                "code": "E500",
                "message": "Error occurred",
                "hint": "Try again",
                "details": [],
            },
            metadata={"processing_time_ms": 100},
        )

        assert result_with_error.format == "png"
        assert result_with_error.image_data is None
        assert result_with_error.error is not None
        assert result_with_error.error["code"] == "E500"

        # Test without error (future success case)
        result_success = VisualizationResult(
            format="svg",
            image_data="<svg>...</svg>",
            metadata={"pattern_id": "P01"},
        )

        assert result_success.format == "svg"
        assert result_success.image_data == "<svg>...</svg>"
        assert result_success.error is None
        assert result_success.metadata["pattern_id"] == "P01"

    def test_phase_timing_recorded(self) -> None:
        """Test that phase execution times are recorded."""
        coordinator = Coordinator()
        context = ProcessingContext(
            raw_data="x,y\n1,2",
            data_format="csv",
            query="test",
            options={},
        )
        context.parsed_data = pl.DataFrame({"x": [1], "y": [2]})

        # Mock the validation phase
        with patch.object(coordinator.data_validator, "validate") as mock_validate:
            mock_validate.return_value = ValidatedData(
                df=context.parsed_data,
                metadata=DataMetadata(
                    rows=1,
                    cols=2,
                    dtypes={"x": "int", "y": "int"},
                    has_datetime=False,
                    has_category=False,
                    null_ratio={},
                    sampled=False,
                ),
                warnings=[],
            )

            coordinator._execute_phase(PipelinePhase.DATA_VALIDATION, context)  # noqa: SLF001

            assert PipelinePhase.DATA_VALIDATION.value in context.processing_time_ms
            assert context.processing_time_ms[PipelinePhase.DATA_VALIDATION.value] > 0

    def test_required_phase_failure_propagates(self) -> None:
        """Test that required phase failures are propagated."""
        coordinator = Coordinator()
        request = ValidatedRequest(
            data="x,y\n1,2",
            data_format="csv",
            query="test",
            options={},
            data_size_bytes=100,
        )

        # Mock pattern selector to fail (required phase)
        with patch.object(coordinator.pattern_selector, "select") as mock_select:
            mock_select.side_effect = PatternSelectionError(
                reason="Cannot determine pattern",
                hint="Be more specific",
            )

            result = coordinator.process(request)

            assert result.error is not None
            assert result.error["code"] == ErrorCode.E422_UNPROCESSABLE.value
            assert "Cannot determine pattern" in result.error["message"]

    def test_auto_mapping_generation(self) -> None:
        """Test automatic mapping generation."""
        coordinator = Coordinator()
        context = ProcessingContext(
            raw_data="",
            data_format="csv",
            query="test",
            options={},
        )

        # Test with temporal column
        context.processed_data = pl.DataFrame(
            {
                "date": pl.date_range(
                    start=pl.date(2024, 1, 1),
                    end=pl.date(2024, 1, 3),
                    interval="1d",
                    eager=True,
                ),
                "value": [10, 20, 30],
            }
        )

        mapping = coordinator._get_auto_mapping(context)  # noqa: SLF001

        assert mapping["x"] == "date"
        assert mapping["y"] == "value"

        # Test without temporal column
        context.processed_data = pl.DataFrame(
            {
                "category": ["A", "B", "C"],
                "count": [10, 20, 30],
            }
        )

        mapping = coordinator._get_auto_mapping(context)  # noqa: SLF001

        assert mapping["x"] == "category"
        assert mapping["y"] == "count"
