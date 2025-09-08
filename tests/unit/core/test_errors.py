"""Unit tests for error handling."""

import json

from chartelier.core.enums import ErrorCode, MCPErrorCode, PipelinePhase
from chartelier.core.errors import (
    BusinessError,
    ChartelierError,
    DataTooLargeError,
    DependencyUnavailableError,
    ErrorDetail,
    MappingError,
    PatternSelectionError,
    RateLimitError,
    SystemError,
    TimeoutError,
    UnsupportedFormatError,
    UpstreamError,
    ValidationError,
    create_mcp_error_response,
    map_to_mcp_error_code,
)


class TestChartelierError:
    """Test base ChartelierError class."""

    def test_basic_error(self) -> None:
        """Test basic error creation."""
        error = ChartelierError(
            message="Test error",
            code=ErrorCode.E500_INTERNAL,
        )
        assert str(error) == "Test error"
        assert error.code == ErrorCode.E500_INTERNAL
        assert error.details == []
        assert error.hint is None
        assert error.phase is None

    def test_full_error(self) -> None:
        """Test error with all fields."""
        details = [
            ErrorDetail(
                field="test_field",
                reason="Test reason",
                suggestion="Test suggestion",
            )
        ]
        error = ChartelierError(
            message="Full error",
            code=ErrorCode.E422_UNPROCESSABLE,
            details=details,
            hint="Test hint",
            phase=PipelinePhase.DATA_VALIDATION,
        )
        assert error.message == "Full error"
        assert len(error.details) == 1
        assert error.hint == "Test hint"
        assert error.phase == PipelinePhase.DATA_VALIDATION

    def test_to_error_response(self) -> None:
        """Test conversion to ErrorResponse."""
        error = ChartelierError(
            message="Test error",
            code=ErrorCode.E400_VALIDATION,
            hint="Fix your input",
            phase=PipelinePhase.DATA_VALIDATION,
        )
        response = error.to_error_response(
            correlation_id="test-123",
            fallback_attempted=True,
        )
        assert response.code == "E400_VALIDATION"
        assert response.message == "Test error"
        assert response.hint == "Fix your input"
        assert response.correlation_id == "test-123"
        assert response.phase == "data_validation"
        assert response.fallback_attempted is True


class TestValidationError:
    """Test ValidationError class."""

    def test_creation(self) -> None:
        """Test validation error creation."""
        error = ValidationError(
            message="Invalid input",
            hint="Check your data format",
        )
        assert error.code == ErrorCode.E400_VALIDATION
        assert error.phase == PipelinePhase.DATA_VALIDATION
        assert error.hint == "Check your data format"


class TestDataTooLargeError:
    """Test DataTooLargeError class."""

    def test_with_size_info(self) -> None:
        """Test error with size information."""
        error = DataTooLargeError(
            message="Data too large",
            max_size_mb=100,
            actual_size_mb=150.5,
        )
        assert error.code == ErrorCode.E413_TOO_LARGE
        assert "reduce data size to under 100MB" in error.hint
        assert "current: 150.5MB" in error.hint

    def test_without_actual_size(self) -> None:
        """Test error without actual size."""
        error = DataTooLargeError(
            message="Data too large",
            max_size_mb=50,
        )
        assert "reduce data size to under 50MB" in error.hint
        assert "current:" not in error.hint


class TestUnsupportedFormatError:
    """Test UnsupportedFormatError class."""

    def test_with_supported_formats(self) -> None:
        """Test error with supported formats list."""
        error = UnsupportedFormatError(
            message="Format not supported",
            supported_formats=["csv", "json"],
        )
        assert error.code == ErrorCode.E415_UNSUPPORTED_FORMAT
        assert error.hint == "Supported formats: csv, json"

    def test_without_formats(self) -> None:
        """Test error without formats list."""
        error = UnsupportedFormatError(message="Format not supported")
        assert error.hint is None


class TestPatternSelectionError:
    """Test PatternSelectionError class."""

    def test_with_query(self) -> None:
        """Test error with query but no hint."""
        error = PatternSelectionError(
            message="Cannot determine pattern",
            query="vague request",
        )
        assert error.code == ErrorCode.E422_UNPROCESSABLE
        assert error.phase == PipelinePhase.PATTERN_SELECTION
        assert "clearer visualization intent" in error.hint

    def test_with_custom_hint(self) -> None:
        """Test error with custom hint."""
        error = PatternSelectionError(
            message="Pattern failed",
            hint="Try specifying time period",
        )
        assert error.hint == "Try specifying time period"


class TestMappingError:
    """Test MappingError class."""

    def test_with_required_fields(self) -> None:
        """Test error with required fields."""
        error = MappingError(
            message="Mapping failed",
            required_fields=["x", "y"],
            available_columns=["date", "value", "category"],
        )
        assert error.code == ErrorCode.E422_UNPROCESSABLE
        assert error.phase == PipelinePhase.DATA_MAPPING
        assert len(error.details) == 2
        assert error.details[0].field == "x"
        assert "Available columns: date, value, category" in error.hint

    def test_with_many_columns(self) -> None:
        """Test error with many available columns."""
        columns = [f"col_{i}" for i in range(20)]
        error = MappingError(
            message="Mapping failed",
            available_columns=columns,
        )
        assert "col_0" in error.hint
        assert "col_9" in error.hint
        assert "(and 10 more)" in error.hint


class TestUpstreamError:
    """Test UpstreamError class."""

    def test_default_service(self) -> None:
        """Test error with default service."""
        error = UpstreamError(
            message="Service failed",
            phase=PipelinePhase.PATTERN_SELECTION,
        )
        assert error.code == ErrorCode.E424_UPSTREAM_LLM
        assert "LLM service is temporarily unavailable" in error.hint

    def test_custom_service(self) -> None:
        """Test error with custom service."""
        error = UpstreamError(
            message="API failed",
            service="OpenAI",
        )
        assert "OpenAI service is temporarily unavailable" in error.hint


class TestTimeoutError:
    """Test TimeoutError class."""

    def test_with_timeout_value(self) -> None:
        """Test error with timeout value."""
        error = TimeoutError(
            message="Operation timed out",
            timeout_seconds=60,
            phase=PipelinePhase.CHART_BUILDING,
        )
        assert error.code == ErrorCode.E408_TIMEOUT
        assert "exceeded 60s timeout" in error.hint
        assert error.phase == PipelinePhase.CHART_BUILDING

    def test_without_timeout_value(self) -> None:
        """Test error without timeout value."""
        error = TimeoutError(message="Timed out")
        assert "Operation took too long" in error.hint


class TestRateLimitError:
    """Test RateLimitError class."""

    def test_with_retry_after(self) -> None:
        """Test error with retry-after value."""
        error = RateLimitError(
            message="Rate limited",
            retry_after_seconds=30,
        )
        assert error.code == ErrorCode.E429_RATE_LIMITED
        assert "retry after 30 seconds" in error.hint

    def test_without_retry_after(self) -> None:
        """Test error without retry-after."""
        error = RateLimitError(message="Too many requests")
        assert "Please wait before trying again" in error.hint


class TestSystemError:
    """Test SystemError class."""

    def test_default_message(self) -> None:
        """Test error with default message."""
        error = SystemError()
        assert error.message == "An internal error occurred"
        assert error.code == ErrorCode.E500_INTERNAL
        assert "unexpected error" in error.hint

    def test_custom_message(self) -> None:
        """Test error with custom message."""
        error = SystemError(
            message="Database connection failed",
            phase=PipelinePhase.DATA_VALIDATION,
        )
        assert error.message == "Database connection failed"
        assert error.phase == PipelinePhase.DATA_VALIDATION


class TestDependencyUnavailableError:
    """Test DependencyUnavailableError class."""

    def test_with_dependency_name(self) -> None:
        """Test error with dependency name."""
        error = DependencyUnavailableError(
            message="Service unavailable",
            dependency="vl-convert",
        )
        assert error.code == ErrorCode.E503_DEPENDENCY_UNAVAILABLE
        assert "Service 'vl-convert' is unavailable" in error.hint

    def test_without_dependency_name(self) -> None:
        """Test error without dependency name."""
        error = DependencyUnavailableError(message="Service down")
        assert "required service is unavailable" in error.hint


class TestErrorMapping:
    """Test error mapping functions."""

    def test_map_to_mcp_error_code(self) -> None:
        """Test mapping to MCP error codes."""
        # Validation error
        error = ValidationError("test")
        assert map_to_mcp_error_code(error) == MCPErrorCode.INVALID_PARAMS

        # Business errors
        error = BusinessError("test")
        assert map_to_mcp_error_code(error) == MCPErrorCode.APPLICATION_ERROR

        error = PatternSelectionError("test")
        assert map_to_mcp_error_code(error) == MCPErrorCode.APPLICATION_ERROR

        # Upstream errors
        error = UpstreamError("test")
        assert map_to_mcp_error_code(error) == MCPErrorCode.APPLICATION_ERROR

        # System errors
        error = SystemError("test")
        assert map_to_mcp_error_code(error) == MCPErrorCode.INTERNAL_ERROR

        error = DependencyUnavailableError("test")
        assert map_to_mcp_error_code(error) == MCPErrorCode.INTERNAL_ERROR

    def test_create_mcp_error_response(self) -> None:
        """Test MCP error response creation."""
        error = ValidationError(
            message="Invalid data format",
            hint="Use CSV or JSON",
        )

        response = create_mcp_error_response(
            error=error,
            request_id=123,
            correlation_id="test-correlation",
        )

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 123
        assert response["error"]["code"] == MCPErrorCode.INVALID_PARAMS.value
        assert response["error"]["message"] == "Invalid data format"

        error_data = response["error"]["data"]
        assert error_data["code"] == "E400_VALIDATION"
        assert error_data["hint"] == "Use CSV or JSON"
        assert error_data["correlation_id"] == "test-correlation"
        assert error_data["phase"] == "data_validation"
        assert error_data["fallback_attempted"] is False

    def test_mcp_response_json_serializable(self) -> None:
        """Test MCP error response is JSON serializable."""
        details = [
            ErrorDetail(
                field="x",
                reason="Missing column",
                suggestion="Add date column",
            )
        ]
        error = MappingError(
            message="Mapping failed",
            required_fields=["x"],
        )
        error.details = details

        response = create_mcp_error_response(
            error=error,
            request_id="req-456",
            correlation_id="corr-789",
        )

        # Should not raise
        json_str = json.dumps(response)
        parsed = json.loads(json_str)

        assert parsed["error"]["data"]["details"][0]["field"] == "x"
