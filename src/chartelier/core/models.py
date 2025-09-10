"""Pydantic models for Chartelier data structures."""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from .enums import AuxiliaryElement, Locale, OutputFormat, PatternID


class VisualizeOptions(BaseModel):
    """Optional visualization parameters."""

    format: OutputFormat = Field(default=OutputFormat.PNG, description="Output image format")
    dpi: int = Field(default=300, ge=72, le=300, description="Dots per inch for PNG output")
    width: int = Field(default=1200, ge=600, le=2000, description="Image width in pixels")
    height: int = Field(default=900, ge=400, le=2000, description="Image height in pixels")
    locale: Locale | None = Field(default=None, description="Locale for labels and messages")


class VisualizeRequest(BaseModel):
    """Request model for visualization tool."""

    data: str = Field(..., description="CSV or JSON data as UTF-8 string", max_length=104857600)
    query: str = Field(..., description="Natural language visualization intent", min_length=1, max_length=1000)
    options: VisualizeOptions | None = Field(default=None, description="Optional parameters")

    @field_validator("data")
    @classmethod
    def validate_data_not_empty(cls, v: str) -> str:
        """Ensure data is not empty or just whitespace."""
        if not v or not v.strip():
            raise ValueError("Data cannot be empty")
        return v


class DataMetadata(BaseModel):
    """Metadata about the input data after validation."""

    rows: int = Field(..., ge=0, description="Number of data rows")
    cols: int = Field(..., ge=0, description="Number of columns")
    dtypes: dict[str, str] = Field(..., description="Column name to data type mapping")
    has_datetime: bool = Field(..., description="Whether data contains datetime columns")
    has_category: bool = Field(..., description="Whether data contains categorical columns")
    null_ratio: dict[str, float] = Field(default_factory=dict, description="Column null ratios")
    sampled: bool = Field(default=False, description="Whether data was sampled due to size limits")
    original_rows: int | None = Field(default=None, description="Original row count before sampling")


class MappingConfig(BaseModel):
    """Column to visualization encoding mappings."""

    x: str | None = Field(default=None, description="X-axis column")
    y: str | None = Field(default=None, description="Y-axis column")
    color: str | None = Field(default=None, description="Color encoding column")
    facet: str | None = Field(default=None, description="Facet column for small multiples")
    size: str | None = Field(default=None, description="Size encoding column")
    shape: str | None = Field(default=None, description="Shape encoding column")
    row: str | None = Field(default=None, description="Row facet column")
    column: str | None = Field(default=None, description="Column facet column")


class ProcessingStats(BaseModel):
    """Statistics about processing performance."""

    rows: int = Field(..., description="Number of rows processed")
    cols: int = Field(..., description="Number of columns processed")
    sampled: bool = Field(default=False, description="Whether sampling was applied")
    duration_ms: dict[str, float] = Field(default_factory=dict, description="Phase durations in milliseconds")


class VersionInfo(BaseModel):
    """Version information for API and components."""

    api: str = Field(default="0.2.0", description="API version")
    templates: str = Field(default="2025.01", description="Template catalog revision")
    patterns: str = Field(default="v1", description="Pattern definition version")


class ChartMetadata(BaseModel):
    """Metadata about the generated chart."""

    pattern_id: PatternID = Field(..., description="Selected visualization pattern")
    template_id: str = Field(..., description="Specific chart template used")
    mapping: MappingConfig | None = Field(default=None, description="Column mappings used")
    auxiliary: list[AuxiliaryElement] = Field(default_factory=list, description="Applied auxiliary elements")
    auxiliary_config: dict[str, Any] = Field(default_factory=dict, description="Configuration for auxiliary elements")
    operations_applied: list[str] = Field(default_factory=list, description="Data processing operations")
    decisions: dict[str, Any] = Field(default_factory=dict, description="Decision reasoning and timings")
    warnings: list[str] = Field(default_factory=list, description="Processing warnings")
    stats: ProcessingStats = Field(..., description="Processing statistics")
    versions: VersionInfo = Field(default_factory=VersionInfo, description="Version information")
    fallback_applied: bool = Field(default=False, description="Whether fallback was used")


class VisualizeResponse(BaseModel):
    """Response model for successful visualization."""

    format: OutputFormat = Field(..., description="Output image format")
    image: str = Field(..., description="Base64 encoded PNG or SVG string")
    metadata: ChartMetadata = Field(..., description="Chart generation metadata")


class ErrorDetail(BaseModel):
    """Detailed error information."""

    field: str | None = Field(default=None, description="Field that caused the error")
    reason: str | None = Field(default=None, description="Detailed reason for the error")
    suggestion: str | None = Field(default=None, description="Suggested correction")


class ErrorResponse(BaseModel):
    """Response model for errors."""

    code: str = Field(..., description="Error code (e.g., E422_UNPROCESSABLE)")
    message: str = Field(..., description="Human-readable error message")
    details: list[ErrorDetail] | None = Field(default=None, description="Detailed error information")
    hint: str | None = Field(default=None, description="Correction hint for the user")
    correlation_id: str = Field(..., description="Request correlation ID for tracing")
    phase: str | None = Field(default=None, description="Pipeline phase where error occurred")
    fallback_attempted: bool = Field(default=False, description="Whether fallback was attempted")


class PatternSelection(BaseModel):
    """Result of pattern selection process."""

    pattern_id: PatternID = Field(..., description="Selected pattern ID")
    reasoning: str | None = Field(default=None, description="LLM reasoning for selection")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0, description="Selection confidence")


class ChartSelection(BaseModel):
    """Result of chart template selection."""

    template_id: str = Field(..., description="Selected template ID")
    auxiliary: list[AuxiliaryElement] = Field(default_factory=list, description="Selected auxiliary elements")
    reasoning: str | None = Field(default=None, description="Selection reasoning")


class ProcessedData(BaseModel):
    """Result of data processing phase."""

    operations_applied: list[str] = Field(..., description="Applied operations in order")
    row_count: int = Field(..., ge=0, description="Row count after processing")
    col_count: int = Field(..., ge=0, description="Column count after processing")
    warnings: list[str] = Field(default_factory=list, description="Processing warnings")
