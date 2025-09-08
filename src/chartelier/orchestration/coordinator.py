"""Coordinator for orchestrating the visualization pipeline."""

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from chartelier.core.enums import ErrorCode
from chartelier.core.errors import ChartelierError
from chartelier.core.models import ErrorDetail
from chartelier.infra.logging import get_logger
from chartelier.interfaces.validators import ValidatedRequest

logger = get_logger(__name__)


class PipelinePhase(str, Enum):
    """Pipeline processing phases."""

    DATA_VALIDATION = "data_validation"
    PATTERN_SELECTION = "pattern_selection"
    CHART_SELECTION = "chart_selection"
    DATA_PROCESSING = "data_processing"
    DATA_MAPPING = "data_mapping"
    CHART_BUILDING = "chart_building"


class ProcessingContext(BaseModel):
    """Context shared between pipeline phases."""

    raw_data: str = Field(..., description="Raw data string (CSV or JSON)")
    data_format: str = Field(..., description="Data format (csv or json)")
    query: str = Field(..., description="User's visualization query")
    options: dict[str, Any] = Field(default_factory=dict, description="Visualization options")

    # Phase results (will be populated as pipeline progresses)
    pattern_id: str | None = Field(None, description="Selected pattern ID (P01-P32)")
    template_id: str | None = Field(None, description="Selected template ID")
    processed_data: Any | None = Field(None, description="Processed data")
    mapping_config: dict[str, Any] | None = Field(None, description="Data mapping configuration")
    auxiliary_config: list[str] | None = Field(None, description="Auxiliary elements configuration")

    # Metadata
    warnings: list[str] = Field(default_factory=list, description="Warning messages")
    processing_time_ms: dict[str, float] = Field(default_factory=dict, description="Processing time per phase")
    fallback_applied: bool = Field(default=False, description="Whether fallback was applied")


class VisualizationResult(BaseModel):
    """Result of visualization processing."""

    format: str = Field(..., description="Output format (png or svg)")
    image_data: str | None = Field(None, description="Base64-encoded image data")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Processing metadata")
    error: dict[str, Any] | None = Field(None, description="Error information if failed")


class Coordinator:
    """Coordinates the visualization processing pipeline.

    This class orchestrates the entire visualization workflow from
    data validation through chart generation.
    """

    def __init__(self) -> None:
        """Initialize the coordinator."""
        self.logger = get_logger(self.__class__.__name__)

    def process(self, request: ValidatedRequest) -> VisualizationResult:
        """Process a visualization request through the pipeline.

        Args:
            request: Validated request from the interface layer

        Returns:
            VisualizationResult with either image data or error information
        """
        start_time = time.time()

        # Create processing context from validated request
        context = ProcessingContext(
            raw_data=request.data,
            data_format=request.data_format,
            query=request.query,
            options=request.options,
        )

        self.logger.info(
            "Starting visualization pipeline",
            extra={
                "data_format": context.data_format,
                "data_size_bytes": request.data_size_bytes,
                "query_length": len(context.query),
            },
        )

        try:
            # For now, return a not-implemented error
            # This will be replaced with actual pipeline execution in future PRs
            raise ChartelierError(  # noqa: TRY301
                code=ErrorCode.E500_INTERNAL,
                message="Visualization pipeline not yet implemented",
                hint="This functionality will be implemented in subsequent PRs (D1-J2)",
                details=[
                    ErrorDetail(field="phase", reason="data_validation: pending"),
                    ErrorDetail(field="phase", reason="pattern_selection: pending"),
                    ErrorDetail(field="phase", reason="chart_selection: pending"),
                    ErrorDetail(field="phase", reason="data_processing: pending"),
                    ErrorDetail(field="phase", reason="data_mapping: pending"),
                    ErrorDetail(field="phase", reason="chart_building: pending"),
                ],
            )

        except ChartelierError as e:
            # Handle known errors
            processing_time = (time.time() - start_time) * 1000

            self.logger.warning(
                "Pipeline processing failed",
                extra={
                    "error_code": e.code.value,
                    "error_message": e.message,
                    "processing_time_ms": processing_time,
                },
            )

            return VisualizationResult(
                format=request.options.get("format", "png"),
                error={
                    "code": e.code.value,
                    "message": e.message,
                    "hint": e.hint,
                    "details": e.details,
                },
                metadata={
                    "processing_time_ms": processing_time,
                    "warnings": context.warnings,
                    "fallback_applied": context.fallback_applied,
                },
            )

        except Exception as e:
            # Handle unexpected errors
            processing_time = (time.time() - start_time) * 1000

            self.logger.exception("Unexpected error in pipeline")

            return VisualizationResult(
                format=request.options.get("format", "png"),
                error={
                    "code": ErrorCode.E500_INTERNAL.value,
                    "message": "Internal server error",
                    "hint": "An unexpected error occurred. Please try again or contact support.",
                    "details": [{"error": str(e)}],
                },
                metadata={
                    "processing_time_ms": processing_time,
                    "warnings": context.warnings,
                },
            )

    def _execute_phase(self, phase: PipelinePhase, context: ProcessingContext) -> None:
        """Execute a single pipeline phase.

        Args:
            phase: The phase to execute
            context: Processing context to update

        Note:
            This method will be implemented in future PRs as each
            processing component is added.
        """
        phase_start = time.time()

        try:
            # Phase execution will be implemented in future PRs
            # For now, just log the phase
            self.logger.debug("Executing pipeline phase", extra={"phase": phase.value})

            # Placeholder for future implementation
            if phase == PipelinePhase.DATA_VALIDATION:
                pass  # Will call DataValidator (PR-D1)
            elif phase == PipelinePhase.PATTERN_SELECTION:
                pass  # Will call PatternSelector (PR-E2)
            elif phase == PipelinePhase.CHART_SELECTION:
                pass  # Will call ChartSelector (PR-G1)
            elif phase == PipelinePhase.DATA_PROCESSING:
                pass  # Will call DataProcessor (PR-H1/H2)
            elif phase == PipelinePhase.DATA_MAPPING:
                pass  # Will call DataMapper (PR-I1)
            elif phase == PipelinePhase.CHART_BUILDING:
                pass  # Will call ChartBuilder (PR-F1)

        finally:
            # Record phase timing
            phase_time = (time.time() - phase_start) * 1000
            context.processing_time_ms[phase.value] = phase_time
