"""Unit tests for the Coordinator class."""

from chartelier.core.enums import ErrorCode
from chartelier.interfaces.validators import ValidatedRequest
from chartelier.orchestration import (
    Coordinator,
    PipelinePhase,
    ProcessingContext,
    VisualizationResult,
)


class TestCoordinator:
    """Test Coordinator functionality."""

    def test_coordinator_initialization(self) -> None:
        """Test Coordinator initialization."""
        coordinator = Coordinator()
        assert coordinator is not None
        assert coordinator.logger is not None

    def test_process_returns_not_implemented_error(self) -> None:
        """Test that process returns not-implemented error for now."""
        coordinator = Coordinator()

        # Create a valid request
        request = ValidatedRequest(
            data="x,y\n1,2\n3,4",
            query="Show a line chart",
            options={"format": "png"},
            data_format="csv",
            data_size_bytes=13,
        )

        # Process the request
        result = coordinator.process(request)

        # Verify result structure
        assert isinstance(result, VisualizationResult)
        assert result.format == "png"
        assert result.image_data is None
        assert result.error is not None

        # Verify error details
        assert result.error["code"] == ErrorCode.E500_INTERNAL.value
        assert "not yet implemented" in result.error["message"]
        assert result.error["hint"] is not None
        assert result.error["details"] is not None

        # Verify metadata
        assert result.metadata is not None
        assert "processing_time_ms" in result.metadata
        assert result.metadata["processing_time_ms"] > 0
        assert "warnings" in result.metadata
        assert isinstance(result.metadata["warnings"], list)

    def test_process_with_different_formats(self) -> None:
        """Test process with different output formats."""
        coordinator = Coordinator()

        # Test with SVG format
        request_svg = ValidatedRequest(
            data='[{"x": 1, "y": 2}]',
            query="Create a chart",
            options={"format": "svg"},
            data_format="json",
            data_size_bytes=18,
        )

        result_svg = coordinator.process(request_svg)
        assert result_svg.format == "svg"

        # Test with PNG format (default)
        request_png = ValidatedRequest(
            data="a,b\n1,2",
            query="Create a chart",
            options={},
            data_format="csv",
            data_size_bytes=8,
        )

        result_png = coordinator.process(request_png)
        assert result_png.format == "png"

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

    def test_execute_phase_placeholder(self) -> None:
        """Test _execute_phase method (placeholder for now)."""
        coordinator = Coordinator()
        context = ProcessingContext(
            raw_data="test",
            data_format="csv",
            query="test query",
        )

        # Execute a phase (should just log for now)
        coordinator._execute_phase(PipelinePhase.DATA_VALIDATION, context)  # noqa: SLF001

        # Check that timing was recorded
        assert PipelinePhase.DATA_VALIDATION.value in context.processing_time_ms
        assert context.processing_time_ms[PipelinePhase.DATA_VALIDATION.value] >= 0

    def test_process_handles_unexpected_errors(self) -> None:
        """Test that process handles unexpected errors gracefully."""
        coordinator = Coordinator()

        # Create a request that might trigger unexpected behavior
        request = ValidatedRequest(
            data="test",
            query="test",
            options={},
            data_format="unknown",
            data_size_bytes=4,
        )

        # Should still return a valid result with error
        result = coordinator.process(request)

        assert isinstance(result, VisualizationResult)
        assert result.error is not None
        assert result.error["code"] == ErrorCode.E500_INTERNAL.value
