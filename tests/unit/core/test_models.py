"""Unit tests for Pydantic models."""

import json

import pytest
from pydantic import ValidationError as PydanticValidationError

from chartelier.core.enums import AuxiliaryElement, Locale, OutputFormat, PatternID
from chartelier.core.models import (
    ChartMetadata,
    ChartSelection,
    DataMetadata,
    ErrorDetail,
    ErrorResponse,
    MappingConfig,
    PatternSelection,
    ProcessedData,
    ProcessingStats,
    VersionInfo,
    VisualizeOptions,
    VisualizeRequest,
)


class TestVisualizeOptions:
    """Test VisualizeOptions model."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        options = VisualizeOptions()
        assert options.format == OutputFormat.PNG
        assert options.dpi == 300
        assert options.width == 1200
        assert options.height == 900
        assert options.locale is None

    def test_custom_values(self) -> None:
        """Test custom values are accepted."""
        options = VisualizeOptions(
            format=OutputFormat.SVG,
            dpi=96,
            width=800,
            height=600,
            locale=Locale.JA,
        )
        assert options.format == OutputFormat.SVG
        assert options.dpi == 96
        assert options.width == 800
        assert options.height == 600
        assert options.locale == Locale.JA

    def test_validation_constraints(self) -> None:
        """Test validation constraints are enforced."""
        # DPI too low
        with pytest.raises(PydanticValidationError) as exc_info:
            VisualizeOptions(dpi=50)
        assert "greater than or equal to 72" in str(exc_info.value)

        # Width too large
        with pytest.raises(PydanticValidationError) as exc_info:
            VisualizeOptions(width=3000)
        assert "less than or equal to 2000" in str(exc_info.value)

    def test_json_serialization(self) -> None:
        """Test JSON serialization/deserialization."""
        options = VisualizeOptions(format=OutputFormat.SVG, dpi=150)
        json_str = options.model_dump_json()
        parsed = VisualizeOptions.model_validate_json(json_str)
        assert parsed == options


class TestVisualizeRequest:
    """Test VisualizeRequest model."""

    def test_minimal_request(self) -> None:
        """Test minimal valid request."""
        request = VisualizeRequest(
            data="date,value\\n2024-01,100",
            query="Show trends",
        )
        assert request.data == "date,value\\n2024-01,100"
        assert request.query == "Show trends"
        assert request.options is None

    def test_full_request(self) -> None:
        """Test request with all fields."""
        request = VisualizeRequest(
            data="date,value\\n2024-01,100",
            query="Show monthly trends",
            options=VisualizeOptions(format=OutputFormat.SVG),
        )
        assert request.options is not None
        assert request.options.format == OutputFormat.SVG

    def test_empty_data_validation(self) -> None:
        """Test empty data is rejected."""
        with pytest.raises(PydanticValidationError) as exc_info:
            VisualizeRequest(data="", query="Show trends")
        assert "Data cannot be empty" in str(exc_info.value)

        with pytest.raises(PydanticValidationError) as exc_info:
            VisualizeRequest(data="   ", query="Show trends")
        assert "Data cannot be empty" in str(exc_info.value)

    def test_query_length_validation(self) -> None:
        """Test query length constraints."""
        # Too short
        with pytest.raises(PydanticValidationError) as exc_info:
            VisualizeRequest(data="data", query="")
        assert "at least 1 character" in str(exc_info.value)

        # Too long
        with pytest.raises(PydanticValidationError) as exc_info:
            VisualizeRequest(data="data", query="x" * 1001)
        assert "at most 1000 characters" in str(exc_info.value)


class TestDataMetadata:
    """Test DataMetadata model."""

    def test_creation(self) -> None:
        """Test metadata creation."""
        metadata = DataMetadata(
            rows=100,
            cols=5,
            dtypes={"date": "datetime", "value": "float"},
            has_datetime=True,
            has_category=False,
            null_ratio={"date": 0.0, "value": 0.1},
            sampled=True,
            original_rows=10000,
        )
        assert metadata.rows == 100
        assert metadata.cols == 5
        assert metadata.dtypes["date"] == "datetime"
        assert metadata.has_datetime is True
        assert metadata.null_ratio["value"] == 0.1
        assert metadata.sampled is True
        assert metadata.original_rows == 10000


class TestChartMetadata:
    """Test ChartMetadata model."""

    def test_minimal_metadata(self) -> None:
        """Test minimal metadata requirements."""
        stats = ProcessingStats(rows=100, cols=5)
        metadata = ChartMetadata(
            pattern_id=PatternID.P01,
            template_id="line",
            stats=stats,
        )
        assert metadata.pattern_id == PatternID.P01
        assert metadata.template_id == "line"
        assert metadata.auxiliary == []
        assert metadata.warnings == []
        assert metadata.fallback_applied is False

    def test_full_metadata(self) -> None:
        """Test metadata with all fields."""
        stats = ProcessingStats(
            rows=100,
            cols=5,
            sampled=True,
            duration_ms={"data_validation": 100.5, "pattern_selection": 200.3},
        )
        mapping = MappingConfig(x="date", y="value", color="category")
        metadata = ChartMetadata(
            pattern_id=PatternID.P12,
            template_id="multi_line",
            mapping=mapping,
            auxiliary=[AuxiliaryElement.REGRESSION, AuxiliaryElement.ANNOTATION],
            operations_applied=["groupby", "sort"],
            decisions={"pattern_reasoning": "Time series with multiple categories"},
            warnings=["Data was sampled to 10000 rows"],
            stats=stats,
            versions=VersionInfo(api="0.2.1"),
            fallback_applied=True,
        )
        assert len(metadata.auxiliary) == 2
        assert AuxiliaryElement.REGRESSION in metadata.auxiliary
        assert metadata.fallback_applied is True
        assert metadata.versions.api == "0.2.1"


class TestErrorResponse:
    """Test ErrorResponse model."""

    def test_minimal_error(self) -> None:
        """Test minimal error response."""
        error = ErrorResponse(
            code="E422_UNPROCESSABLE",
            message="Cannot process request",
            correlation_id="test-123",
        )
        assert error.code == "E422_UNPROCESSABLE"
        assert error.message == "Cannot process request"
        assert error.details is None
        assert error.hint is None

    def test_detailed_error(self) -> None:
        """Test error with details."""
        details = [
            ErrorDetail(
                field="x",
                reason="No suitable column for x-axis",
                suggestion="Add a date or numeric column",
            )
        ]
        error = ErrorResponse(
            code="E422_UNPROCESSABLE",
            message="Mapping failed",
            details=details,
            hint="Check your data structure",
            correlation_id="test-456",
            phase="data_mapping",
            fallback_attempted=True,
        )
        assert len(error.details) == 1
        assert error.details[0].field == "x"
        assert error.hint == "Check your data structure"
        assert error.phase == "data_mapping"
        assert error.fallback_attempted is True

    def test_json_serialization(self) -> None:
        """Test error JSON serialization."""
        error = ErrorResponse(
            code="E500_INTERNAL",
            message="Internal error",
            correlation_id="test-789",
        )
        json_data = json.loads(error.model_dump_json())
        assert json_data["code"] == "E500_INTERNAL"
        assert json_data["correlation_id"] == "test-789"


class TestPatternSelection:
    """Test PatternSelection model."""

    def test_creation(self) -> None:
        """Test pattern selection creation."""
        selection = PatternSelection(
            pattern_id=PatternID.P01,
            reasoning="Single time series data",
            confidence=0.95,
        )
        assert selection.pattern_id == PatternID.P01
        assert selection.reasoning == "Single time series data"
        assert selection.confidence == 0.95

    def test_confidence_validation(self) -> None:
        """Test confidence range validation."""
        with pytest.raises(PydanticValidationError) as exc_info:
            PatternSelection(pattern_id=PatternID.P01, confidence=1.5)
        assert "less than or equal to 1" in str(exc_info.value)


class TestChartSelection:
    """Test ChartSelection model."""

    def test_creation(self) -> None:
        """Test chart selection creation."""
        selection = ChartSelection(
            template_id="line",
            auxiliary=[AuxiliaryElement.MEAN_LINE, AuxiliaryElement.THRESHOLD],
            reasoning="Time series with reference lines",
        )
        assert selection.template_id == "line"
        assert len(selection.auxiliary) == 2
        assert AuxiliaryElement.MEAN_LINE in selection.auxiliary


class TestProcessedData:
    """Test ProcessedData model."""

    def test_creation(self) -> None:
        """Test processed data creation."""
        processed = ProcessedData(
            operations_applied=["filter", "groupby", "sort"],
            row_count=50,
            col_count=3,
            warnings=["Removed 10 rows with null values"],
        )
        assert len(processed.operations_applied) == 3
        assert processed.row_count == 50
        assert len(processed.warnings) == 1
