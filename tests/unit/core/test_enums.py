"""Unit tests for enumerations."""

import pytest

from chartelier.core.enums import (
    AuxiliaryElement,
    ErrorCode,
    Locale,
    MCPErrorCode,
    OutputFormat,
    PatternID,
    PipelinePhase,
)


class TestPatternID:
    """Test PatternID enumeration."""

    def test_all_patterns_defined(self) -> None:
        """Test all 9 patterns are defined."""
        patterns = list(PatternID)
        assert len(patterns) == 9

        # Check specific patterns exist
        assert PatternID.P01 in patterns
        assert PatternID.P02 in patterns
        assert PatternID.P03 in patterns
        assert PatternID.P12 in patterns
        assert PatternID.P13 in patterns
        assert PatternID.P21 in patterns
        assert PatternID.P23 in patterns
        assert PatternID.P31 in patterns
        assert PatternID.P32 in patterns

    def test_pattern_values(self) -> None:
        """Test pattern values are strings."""
        assert PatternID.P01.value == "P01"
        assert PatternID.P12.value == "P12"
        assert PatternID.P32.value == "P32"

    def test_pattern_from_string(self) -> None:
        """Test creating pattern from string."""
        pattern = PatternID("P01")
        assert pattern == PatternID.P01

        with pytest.raises(ValueError):
            PatternID("P99")  # Invalid pattern


class TestErrorCode:
    """Test ErrorCode enumeration."""

    def test_error_codes_defined(self) -> None:
        """Test all error codes are defined."""
        codes = list(ErrorCode)
        assert len(codes) == 9

        # Check specific codes
        assert ErrorCode.E400_VALIDATION in codes
        assert ErrorCode.E413_TOO_LARGE in codes
        assert ErrorCode.E422_UNPROCESSABLE in codes
        assert ErrorCode.E500_INTERNAL in codes

    def test_error_code_values(self) -> None:
        """Test error code string values."""
        assert ErrorCode.E400_VALIDATION.value == "E400_VALIDATION"
        assert ErrorCode.E422_UNPROCESSABLE.value == "E422_UNPROCESSABLE"
        assert ErrorCode.E500_INTERNAL.value == "E500_INTERNAL"


class TestMCPErrorCode:
    """Test MCPErrorCode enumeration."""

    def test_standard_codes(self) -> None:
        """Test standard JSON-RPC error codes."""
        assert MCPErrorCode.INVALID_REQUEST.value == -32600
        assert MCPErrorCode.METHOD_NOT_FOUND.value == -32601
        assert MCPErrorCode.INVALID_PARAMS.value == -32602
        assert MCPErrorCode.INTERNAL_ERROR.value == -32603
        assert MCPErrorCode.APPLICATION_ERROR.value == -32500

    def test_codes_are_integers(self) -> None:
        """Test error codes are integers."""
        for code in MCPErrorCode:
            assert isinstance(code.value, int)
            assert code.value < 0  # JSON-RPC errors are negative


class TestOutputFormat:
    """Test OutputFormat enumeration."""

    def test_formats(self) -> None:
        """Test supported formats."""
        assert OutputFormat.PNG.value == "png"
        assert OutputFormat.SVG.value == "svg"
        assert len(list(OutputFormat)) == 2

    def test_format_from_string(self) -> None:
        """Test creating format from string."""
        fmt = OutputFormat("png")
        assert fmt == OutputFormat.PNG

        with pytest.raises(ValueError):
            OutputFormat("pdf")  # Unsupported format


class TestLocale:
    """Test Locale enumeration."""

    def test_locales(self) -> None:
        """Test supported locales."""
        assert Locale.JA.value == "ja"
        assert Locale.EN.value == "en"
        assert len(list(Locale)) == 2

    def test_locale_from_string(self) -> None:
        """Test creating locale from string."""
        locale = Locale("ja")
        assert locale == Locale.JA

        with pytest.raises(ValueError):
            Locale("fr")  # Unsupported locale


class TestPipelinePhase:
    """Test PipelinePhase enumeration."""

    def test_phases_defined(self) -> None:
        """Test all pipeline phases are defined."""
        phases = list(PipelinePhase)
        assert len(phases) == 7

        # Check phases in order
        assert PipelinePhase.DATA_VALIDATION in phases
        assert PipelinePhase.PATTERN_SELECTION in phases
        assert PipelinePhase.CHART_SELECTION in phases
        assert PipelinePhase.DATA_PROCESSING in phases
        assert PipelinePhase.DATA_MAPPING in phases
        assert PipelinePhase.CHART_BUILDING in phases
        assert PipelinePhase.EXPORT in phases

    def test_phase_values(self) -> None:
        """Test phase string values."""
        assert PipelinePhase.DATA_VALIDATION.value == "data_validation"
        assert PipelinePhase.PATTERN_SELECTION.value == "pattern_selection"
        assert PipelinePhase.EXPORT.value == "export"


class TestAuxiliaryElement:
    """Test AuxiliaryElement enumeration."""

    def test_target_line_element(self) -> None:
        """Test target line auxiliary element (the only supported element)."""
        assert AuxiliaryElement.TARGET_LINE.value == "target_line"

    def test_total_elements(self) -> None:
        """Test total number of auxiliary elements."""
        elements = list(AuxiliaryElement)
        assert len(elements) == 1  # Only target_line is supported
