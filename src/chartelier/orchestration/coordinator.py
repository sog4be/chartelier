"""Coordinator for orchestrating the visualization pipeline."""

import io
import json
import signal
import time
from collections.abc import Iterator
from contextlib import contextmanager
from enum import Enum
from typing import Any, ClassVar, TypeVar

import polars as pl
from pydantic import BaseModel, Field

from chartelier.core.chart_builder import ChartBuilder
from chartelier.core.enums import ErrorCode, OutputFormat, PatternID
from chartelier.core.errors import ChartelierError
from chartelier.core.models import DataMetadata, ErrorDetail, MappingConfig
from chartelier.infra.logging import get_logger
from chartelier.interfaces.validators import ValidatedRequest
from chartelier.processing.chart_selector import ChartSelector
from chartelier.processing.data_mapper import DataMapper
from chartelier.processing.data_processor import DataProcessor
from chartelier.processing.data_validator import DataValidator
from chartelier.processing.pattern_selector import (
    PatternSelector,
)

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
    parsed_data: pl.DataFrame | None = Field(None, description="Parsed DataFrame", exclude=True)
    data_metadata: DataMetadata | None = Field(None, description="Data metadata", exclude=True)
    pattern_id: str | None = Field(None, description="Selected pattern ID (P01-P32)")
    template_id: str | None = Field(None, description="Selected template ID")
    processed_data: pl.DataFrame | None = Field(None, description="Processed data", exclude=True)
    mapping_config: dict[str, Any] | None = Field(None, description="Data mapping configuration")
    auxiliary_config: list[str] | None = Field(None, description="Auxiliary elements configuration")

    # Additional metadata
    data_sampled: bool = Field(default=False, description="Whether data was sampled")
    rows_count: int | None = Field(None, description="Number of rows in data")
    cols_count: int | None = Field(None, description="Number of columns in data")

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True

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


# Type variable for timeout decorator
T = TypeVar("T")


class TimeoutError(ChartelierError):
    """Raised when a pipeline phase times out."""

    def __init__(self, phase: str, timeout: float) -> None:
        """Initialize timeout error."""
        super().__init__(
            code=ErrorCode.E408_TIMEOUT,
            message=f"Pipeline phase '{phase}' timed out after {timeout} seconds",
            hint="The operation took too long. Try with smaller data or simpler query.",
            details=[ErrorDetail(field="phase", reason=f"{phase} exceeded {timeout}s timeout")],
        )


@contextmanager
def timeout(seconds: float) -> Iterator[None]:
    """Context manager for timeout.

    Args:
        seconds: Timeout in seconds

    Raises:
        TimeoutError: If operation exceeds timeout
    """

    def timeout_handler(signum: int, frame: Any) -> None:  # noqa: ARG001, ANN401
        raise TimeoutError("operation", seconds)

    # Set the timeout handler
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(int(seconds))

    try:
        yield
    finally:
        # Restore the original handler
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


class Coordinator:
    """Coordinates the visualization processing pipeline.

    This class orchestrates the entire visualization workflow from
    data validation through chart generation.
    """

    # Phase timeout configuration (in seconds)
    PHASE_TIMEOUTS: ClassVar[dict[PipelinePhase, int]] = {
        PipelinePhase.DATA_VALIDATION: 5,
        PipelinePhase.PATTERN_SELECTION: 10,
        PipelinePhase.CHART_SELECTION: 10,
        PipelinePhase.DATA_PROCESSING: 10,
        PipelinePhase.DATA_MAPPING: 5,
        PipelinePhase.CHART_BUILDING: 10,
    }

    # Overall pipeline timeout
    TOTAL_TIMEOUT: ClassVar[int] = 60

    # Phase configuration
    PHASE_CONFIG: ClassVar[dict[PipelinePhase, dict[str, Any]]] = {
        PipelinePhase.DATA_VALIDATION: {
            "required": True,
            "fallback": None,
        },
        PipelinePhase.PATTERN_SELECTION: {
            "required": True,  # Pattern selection failure is an error (ADR-0002)
            "fallback": None,
        },
        PipelinePhase.CHART_SELECTION: {
            "required": False,
            "fallback": "line_chart",  # Default to line chart
        },
        PipelinePhase.DATA_PROCESSING: {
            "required": False,
            "fallback": "original_data",  # Use original data
        },
        PipelinePhase.DATA_MAPPING: {
            "required": False,
            "fallback": "auto_mapping",  # Basic automatic mapping
        },
        PipelinePhase.CHART_BUILDING: {
            "required": True,
            "fallback": None,
        },
    }

    def __init__(self) -> None:
        """Initialize the coordinator."""
        self.logger = get_logger(self.__class__.__name__)

        # Initialize processing components
        self.data_validator = DataValidator()
        self.pattern_selector = PatternSelector()
        self.chart_selector = ChartSelector()
        self.data_processor = DataProcessor()
        self.data_mapper = DataMapper()
        self.chart_builder = ChartBuilder()

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
            # Execute pipeline phases in sequence
            # Data parsing is done in DATA_VALIDATION phase
            phases = [
                PipelinePhase.DATA_VALIDATION,
                PipelinePhase.PATTERN_SELECTION,
                PipelinePhase.CHART_SELECTION,
                PipelinePhase.DATA_PROCESSING,
                PipelinePhase.DATA_MAPPING,
                PipelinePhase.CHART_BUILDING,
            ]

            # Use overall timeout for entire pipeline
            with timeout(self.TOTAL_TIMEOUT):
                for phase in phases:
                    try:
                        self._execute_phase(phase, context)
                    except ChartelierError as e:
                        # Check if this phase is required
                        config = self.PHASE_CONFIG.get(phase, {})
                        if config.get("required", True):
                            # Required phase failed - propagate error
                            raise
                        # Optional phase failed - apply fallback and continue
                        self.logger.warning(
                            "Optional phase %s failed, applying fallback",
                            phase.value,
                            extra={"error": str(e), "fallback": config.get("fallback")},
                        )
                        context.fallback_applied = True
                        context.warnings.append(f"Phase {phase.value} failed: {e.message}. Using fallback.")

            # Build final response
            return self._build_success_response(context, request)

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

    def _parse_data(self, context: ProcessingContext) -> None:
        """Parse raw data into DataFrame.

        Args:
            context: Processing context to update

        Raises:
            ChartelierError: If data parsing fails
        """
        try:
            if context.data_format == "csv":
                # Parse CSV
                context.parsed_data = pl.read_csv(
                    io.StringIO(context.raw_data),
                    ignore_errors=False,
                    try_parse_dates=True,
                )
            elif context.data_format == "json":
                # Parse JSON - support both array of objects and columnar format
                data = json.loads(context.raw_data)
                if isinstance(data, list):
                    # Array of objects format
                    context.parsed_data = pl.DataFrame(data)
                elif isinstance(data, dict):
                    # Columnar format
                    context.parsed_data = pl.DataFrame(data)
                else:
                    msg = f"Unsupported JSON structure: {type(data)}"
                    raise ValueError(msg)  # noqa: TRY301
            else:
                msg = f"Unsupported data format: {context.data_format}"
                raise ValueError(msg)  # noqa: TRY301

            # Store basic stats
            if context.parsed_data is not None:
                context.rows_count = context.parsed_data.height
                context.cols_count = context.parsed_data.width

            self.logger.debug(
                "Data parsed successfully",
                extra={
                    "format": context.data_format,
                    "rows": context.rows_count,
                    "cols": context.cols_count,
                },
            )

        except Exception as e:
            raise ChartelierError(
                code=ErrorCode.E415_UNSUPPORTED_FORMAT,
                message=f"Failed to parse {context.data_format} data: {e}",
                hint="Ensure the data is valid CSV or JSON format",
                details=[ErrorDetail(field="data", reason=str(e))],
            ) from e

    def _execute_phase(self, phase: PipelinePhase, context: ProcessingContext) -> None:
        """Execute a single pipeline phase.

        Args:
            phase: The phase to execute
            context: Processing context to update

        Raises:
            ChartelierError: If phase execution fails
            TimeoutError: If phase exceeds timeout
        """
        phase_start = time.time()
        phase_timeout = self.PHASE_TIMEOUTS.get(phase, 10)

        try:
            self.logger.debug(
                "Executing pipeline phase: %s",
                phase.value,
                extra={"phase": phase.value, "timeout": phase_timeout},
            )

            # Execute phase with timeout
            with timeout(phase_timeout):
                if phase == PipelinePhase.DATA_VALIDATION:
                    self._execute_data_validation(context)
                elif phase == PipelinePhase.PATTERN_SELECTION:
                    self._execute_pattern_selection(context)
                elif phase == PipelinePhase.CHART_SELECTION:
                    self._execute_chart_selection(context)
                elif phase == PipelinePhase.DATA_PROCESSING:
                    self._execute_data_processing(context)
                elif phase == PipelinePhase.DATA_MAPPING:
                    self._execute_data_mapping(context)
                elif phase == PipelinePhase.CHART_BUILDING:
                    self._execute_chart_building(context)

            self.logger.debug(
                "Phase %s completed successfully",
                phase.value,
                extra={"phase": phase.value},
            )

        except TimeoutError as e:
            # Re-raise with phase information
            raise TimeoutError(phase.value, phase_timeout) from e

        finally:
            # Record phase timing
            phase_time = (time.time() - phase_start) * 1000
            context.processing_time_ms[phase.value] = phase_time

    def _execute_data_validation(self, context: ProcessingContext) -> None:
        """Execute data validation phase."""
        # Validate and parse data
        validated = self.data_validator.validate(context.raw_data, context.data_format)

        # Update context
        context.parsed_data = validated.df
        context.data_metadata = validated.metadata
        context.warnings.extend(validated.warnings)
        context.data_sampled = validated.metadata.sampled

        # Update row/col counts
        context.rows_count = validated.df.height
        context.cols_count = validated.df.width

    def _execute_pattern_selection(self, context: ProcessingContext) -> None:
        """Execute pattern selection phase."""
        if context.data_metadata is None:
            raise ChartelierError(
                code=ErrorCode.E500_INTERNAL,
                message="Data metadata not available for pattern selection",
                hint="This is an internal error. Please report it.",
            )

        # Select pattern
        selection = self.pattern_selector.select(context.data_metadata, context.query)

        # Update context
        context.pattern_id = selection.pattern_id.value

    def _execute_chart_selection(self, context: ProcessingContext) -> None:
        """Execute chart selection phase."""
        if context.pattern_id is None:
            # Use default pattern if not selected
            context.pattern_id = PatternID.P01.value
            context.warnings.append("Pattern selection failed, using default line chart pattern")

        # Select chart
        chart_selection = self.chart_selector.select_chart(
            pattern_id=PatternID(context.pattern_id),
            metadata=context.data_metadata
            if context.data_metadata
            else DataMetadata(
                rows=0, cols=0, dtypes={}, has_datetime=False, has_category=False, null_ratio={}, sampled=False
            ),
            query=context.query,
        )

        # Select auxiliary elements
        auxiliary_selection = self.chart_selector.select_auxiliary(
            template_id=chart_selection.template_id,
            query=context.query,
        )

        # Update context
        context.template_id = chart_selection.template_id
        if hasattr(auxiliary_selection, "auxiliary"):
            context.auxiliary_config = auxiliary_selection.auxiliary
        else:
            context.auxiliary_config = []

    def _execute_data_processing(self, context: ProcessingContext) -> None:
        """Execute data processing phase."""
        if context.parsed_data is None or context.template_id is None:
            # Skip processing if no data or template
            context.processed_data = context.parsed_data
            return

        # Process data
        processed = self.data_processor.process(
            data=context.parsed_data,
            template_id=context.template_id,
        )

        # Update context
        context.processed_data = processed.df
        # Store operations applied for metadata
        context.options["_operations_applied"] = processed.operations_applied
        context.warnings.extend([f"Data processing: {op}" for op in processed.operations_applied])

    def _execute_data_mapping(self, context: ProcessingContext) -> None:
        """Execute data mapping phase."""
        if context.processed_data is None or context.template_id is None:
            # Use auto mapping if no processed data
            context.mapping_config = self._get_auto_mapping(context)
            return

        # Map data to template
        mapping = self.data_mapper.map(
            data=context.processed_data,
            template_id=context.template_id,
            query=context.query,
            auxiliary_config={"elements": context.auxiliary_config} if context.auxiliary_config else None,
        )

        # Update context
        # MappingConfig is already a dict-like object
        context.mapping_config = {
            "x": mapping.x,
            "y": mapping.y,
            "color": mapping.color,
            "size": mapping.size,
            "facet": mapping.facet,
            "row": mapping.row,
            "column": mapping.column,
        }

    def _execute_chart_building(self, context: ProcessingContext) -> None:
        """Execute chart building phase."""
        if context.processed_data is None or context.template_id is None or context.mapping_config is None:
            raise ChartelierError(
                code=ErrorCode.E500_INTERNAL,
                message="Missing required data for chart building",
                hint="This is an internal error. Please report it.",
                details=[
                    ErrorDetail(field="processed_data", reason=str(context.processed_data is None)),
                    ErrorDetail(field="template_id", reason=str(context.template_id)),
                    ErrorDetail(field="mapping_config", reason=str(context.mapping_config is None)),
                ],
            )

        # Build chart
        chart = self.chart_builder.build(
            template_id=context.template_id,
            data=context.processed_data,
            mapping=MappingConfig(**context.mapping_config),
            auxiliary=context.auxiliary_config,
            auxiliary_config={"elements": context.auxiliary_config} if context.auxiliary_config else None,
        )

        # Export to requested format
        format = context.options.get("format", "png")
        try:
            if format == "png":
                # Try PNG first
                image_data = self.chart_builder.export(chart, format=OutputFormat.PNG)
            else:
                # SVG
                image_data = self.chart_builder.export(chart, format=OutputFormat.SVG)
        except Exception as e:
            # Fallback to SVG if PNG fails
            if format == "png":
                self.logger.warning(
                    "PNG export failed, falling back to SVG",
                    extra={"error": str(e)},
                )
                context.warnings.append("PNG export failed, returning SVG instead")
                context.fallback_applied = True
                image_data = self.chart_builder.export(chart, format=OutputFormat.SVG)
                format = "svg"
            else:
                raise

        # Store result in context (we'll retrieve it later)
        context.options["_chart_data"] = image_data
        context.options["_chart_format"] = format

    def _get_auto_mapping(self, context: ProcessingContext) -> dict[str, Any]:
        """Get automatic mapping for data."""
        if context.processed_data is None:
            return {}

        # Simple auto-mapping: first numeric column as y, first temporal/ordinal as x
        mapping = {}
        df = context.processed_data

        # Find x column (temporal or ordinal)
        for col in df.columns:
            dtype = str(df[col].dtype)
            if "Date" in dtype or "date" in dtype:
                mapping["x"] = col
                break

        # If no temporal, use first column
        if "x" not in mapping and len(df.columns) > 0:
            mapping["x"] = df.columns[0]

        # Find y column (numeric)
        for col in df.columns:
            if col != mapping.get("x"):
                dtype = str(df[col].dtype)
                if "Int" in dtype or "Float" in dtype:
                    mapping["y"] = col
                    break

        return mapping

    def _build_success_response(self, context: ProcessingContext, request: ValidatedRequest) -> VisualizationResult:
        """Build successful visualization response."""
        # Get chart data from context
        image_data = context.options.get("_chart_data")
        format = context.options.get("_chart_format", request.options.get("format", "png"))

        # Calculate total processing time
        total_time = sum(context.processing_time_ms.values())

        # Build metadata according to MCP specification
        metadata = {
            "pattern_id": context.pattern_id or "P01",  # Default to P01 if not set
            "template_id": context.template_id or "line",  # Default template
            "mapping": context.mapping_config or {},
            "auxiliary": context.auxiliary_config or [],
            "operations_applied": context.options.get("_operations_applied", []),
            "decisions": {
                "pattern": {"elapsed_ms": context.processing_time_ms.get(PipelinePhase.PATTERN_SELECTION.value, 0)},
                "chart": {"elapsed_ms": context.processing_time_ms.get(PipelinePhase.CHART_SELECTION.value, 0)},
            },
            "stats": {
                "rows": context.rows_count or 0,
                "cols": context.cols_count or 0,
                "sampled": context.data_sampled,
                "duration_ms": {
                    "total": total_time,
                    **dict(context.processing_time_ms.items()),
                },
            },
            "versions": {
                "api": "0.2.0",
                "templates": "2025.01",
                "patterns": "v1",
            },
            "warnings": context.warnings,
            "fallback_applied": context.fallback_applied,
        }

        return VisualizationResult(
            format=format,
            image_data=image_data,
            metadata=metadata,
        )
