"""Error handling and exception definitions for Chartelier."""

from typing import Any

from .enums import ErrorCode, MCPErrorCode, PipelinePhase
from .models import ErrorDetail, ErrorResponse


class ChartelierError(Exception):
    """Base exception for all Chartelier errors."""

    def __init__(
        self,
        message: str,
        code: ErrorCode,
        details: list[ErrorDetail] | None = None,
        hint: str | None = None,
        phase: PipelinePhase | None = None,
    ):
        """Initialize Chartelier error.

        Args:
            message: Human-readable error message
            code: Error code from ErrorCode enum
            details: Optional detailed error information
            hint: Optional correction hint for the user
            phase: Optional pipeline phase where error occurred
        """
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or []
        self.hint = hint
        self.phase = phase

    def to_error_response(self, correlation_id: str, fallback_attempted: bool = False) -> ErrorResponse:
        """Convert exception to ErrorResponse model.

        Args:
            correlation_id: Request correlation ID
            fallback_attempted: Whether fallback was attempted

        Returns:
            ErrorResponse model instance
        """
        return ErrorResponse(
            code=self.code.value,
            message=self.message,
            details=self.details if self.details else None,
            hint=self.hint,
            correlation_id=correlation_id,
            phase=self.phase.value if self.phase else None,
            fallback_attempted=fallback_attempted,
        )


class ValidationError(ChartelierError):
    """Raised when request validation fails."""

    def __init__(
        self,
        message: str,
        details: list[ErrorDetail] | None = None,
        hint: str | None = None,
    ):
        """Initialize validation error."""
        super().__init__(
            message=message,
            code=ErrorCode.E400_VALIDATION,
            details=details,
            hint=hint,
            phase=PipelinePhase.DATA_VALIDATION,
        )


class DataTooLargeError(ChartelierError):
    """Raised when input data exceeds size limits."""

    def __init__(
        self,
        message: str,
        max_size_mb: int = 100,
        actual_size_mb: float | None = None,
    ):
        """Initialize data too large error."""
        hint = f"Please reduce data size to under {max_size_mb}MB"
        if actual_size_mb:
            hint += f" (current: {actual_size_mb:.1f}MB)"

        super().__init__(
            message=message,
            code=ErrorCode.E413_TOO_LARGE,
            hint=hint,
            phase=PipelinePhase.DATA_VALIDATION,
        )


class UnsupportedFormatError(ChartelierError):
    """Raised when data format is not supported."""

    def __init__(
        self,
        message: str,
        supported_formats: list[str] | None = None,
    ):
        """Initialize unsupported format error."""
        hint = None
        if supported_formats:
            hint = f"Supported formats: {', '.join(supported_formats)}"

        super().__init__(
            message=message,
            code=ErrorCode.E415_UNSUPPORTED_FORMAT,
            hint=hint,
            phase=PipelinePhase.DATA_VALIDATION,
        )


class BusinessError(ChartelierError):
    """Raised when business logic validation fails."""

    def __init__(
        self,
        message: str,
        details: list[ErrorDetail] | None = None,
        hint: str | None = None,
        phase: PipelinePhase | None = None,
    ):
        """Initialize business error."""
        super().__init__(
            message=message,
            code=ErrorCode.E422_UNPROCESSABLE,
            details=details,
            hint=hint,
            phase=phase,
        )


class PatternSelectionError(BusinessError):
    """Raised when pattern selection fails."""

    def __init__(
        self,
        message: str,
        query: str | None = None,
        hint: str | None = None,
    ):
        """Initialize pattern selection error."""
        if not hint and query:
            hint = (
                "Please provide a clearer visualization intent. "
                "For example: 'Show monthly trends' or 'Compare categories'"
            )

        super().__init__(
            message=message,
            hint=hint,
            phase=PipelinePhase.PATTERN_SELECTION,
        )


class MappingError(BusinessError):
    """Raised when data mapping fails."""

    def __init__(
        self,
        message: str,
        required_fields: list[str] | None = None,
        available_columns: list[str] | None = None,
    ):
        """Initialize mapping error."""
        details = []
        if required_fields:
            for field in required_fields:
                details.append(
                    ErrorDetail(
                        field=field,
                        reason=f"Required field '{field}' could not be mapped",
                        suggestion=f"Ensure data has a column suitable for '{field}' encoding",
                    )
                )

        hint = None
        if available_columns:
            hint = f"Available columns: {', '.join(available_columns[:10])}"
            if len(available_columns) > 10:
                hint += f" (and {len(available_columns) - 10} more)"

        super().__init__(
            message=message,
            details=details if details else None,
            hint=hint,
            phase=PipelinePhase.DATA_MAPPING,
        )


class UpstreamError(ChartelierError):
    """Raised when upstream service (LLM) fails."""

    def __init__(
        self,
        message: str,
        service: str = "LLM",
        phase: PipelinePhase | None = None,
    ):
        """Initialize upstream error."""
        super().__init__(
            message=message,
            code=ErrorCode.E424_UPSTREAM_LLM,
            hint=f"{service} service is temporarily unavailable. Please try again later.",
            phase=phase,
        )


class TimeoutError(ChartelierError):
    """Raised when operation times out."""

    def __init__(
        self,
        message: str,
        timeout_seconds: int | None = None,
        phase: PipelinePhase | None = None,
    ):
        """Initialize timeout error."""
        hint = "Operation took too long. Consider simplifying your request or reducing data size."
        if timeout_seconds:
            hint = f"Operation exceeded {timeout_seconds}s timeout. " + hint

        super().__init__(
            message=message,
            code=ErrorCode.E408_TIMEOUT,
            hint=hint,
            phase=phase,
        )


class RateLimitError(ChartelierError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        retry_after_seconds: int | None = None,
    ):
        """Initialize rate limit error."""
        hint = "Too many requests. Please wait before trying again."
        if retry_after_seconds:
            hint = f"Rate limit exceeded. Please retry after {retry_after_seconds} seconds."

        super().__init__(
            message=message,
            code=ErrorCode.E429_RATE_LIMITED,
            hint=hint,
        )


class SystemError(ChartelierError):
    """Raised for internal system errors."""

    def __init__(
        self,
        message: str = "An internal error occurred",
        phase: PipelinePhase | None = None,
    ):
        """Initialize system error."""
        super().__init__(
            message=message,
            code=ErrorCode.E500_INTERNAL,
            hint="This is an unexpected error. Please try again or contact support if the issue persists.",
            phase=phase,
        )


class DependencyUnavailableError(ChartelierError):
    """Raised when required dependency is unavailable."""

    def __init__(
        self,
        message: str,
        dependency: str | None = None,
    ):
        """Initialize dependency unavailable error."""
        hint = "A required service is unavailable. Please try again later."
        if dependency:
            hint = f"Service '{dependency}' is unavailable. " + hint

        super().__init__(
            message=message,
            code=ErrorCode.E503_DEPENDENCY_UNAVAILABLE,
            hint=hint,
        )


class ChartBuildError(BusinessError):
    """Raised when chart building fails."""

    def __init__(
        self,
        message: str,
        template_id: str | None = None,
        hint: str | None = None,
    ):
        """Initialize chart build error."""
        if not hint:
            hint = "Failed to build the chart. Check data compatibility with the selected template."
            if template_id:
                hint = f"Failed to build chart with template '{template_id}'. " + hint

        super().__init__(
            message=message,
            hint=hint,
            phase=PipelinePhase.CHART_BUILDING,
        )


class ExportError(SystemError):
    """Raised when chart export fails."""

    def __init__(
        self,
        message: str,
        format: str | None = None,  # noqa: A002 — format parameter refers to file format
    ):
        """Initialize export error."""
        hint = "Failed to export the chart."
        if format:
            hint = (
                f"Failed to export chart as {format}. "
                "The chart may be too complex or the export format may not be supported."
            )

        super().__init__(
            message=message,
            phase=PipelinePhase.CHART_BUILDING,
        )
        self.hint = hint


def map_to_mcp_error_code(error: ChartelierError) -> MCPErrorCode:
    """Map Chartelier error to MCP error code.

    Args:
        error: Chartelier error instance

    Returns:
        Corresponding MCP error code
    """
    if isinstance(error, ValidationError):
        return MCPErrorCode.INVALID_PARAMS
    if isinstance(error, (BusinessError, UpstreamError, TimeoutError, RateLimitError)):
        return MCPErrorCode.APPLICATION_ERROR
    if isinstance(error, (SystemError, DependencyUnavailableError)):
        return MCPErrorCode.INTERNAL_ERROR
    return MCPErrorCode.APPLICATION_ERROR


def create_mcp_error_response(
    error: ChartelierError,
    request_id: Any | None = None,  # noqa: ANN401
    correlation_id: str = "",
) -> dict[str, Any]:
    """Create MCP-compliant error response.

    Args:
        error: Chartelier error instance
        request_id: JSON-RPC request ID
        correlation_id: Request correlation ID

    Returns:
        MCP error response dictionary
    """
    mcp_code = map_to_mcp_error_code(error)
    error_response = error.to_error_response(correlation_id)

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": mcp_code.value,
            "message": error.message,
            "data": {
                "code": error_response.code,
                "details": [d.model_dump() for d in error_response.details] if error_response.details else None,
                "hint": error_response.hint,
                "correlation_id": error_response.correlation_id,
                "phase": error_response.phase,
                "fallback_attempted": error_response.fallback_attempted,
            },
        },
    }
