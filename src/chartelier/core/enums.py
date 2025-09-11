"""Enumerations for Chartelier core types."""

from enum import Enum, IntEnum


class PatternID(str, Enum):
    """Visualization pattern identifiers from 3x3 matrix.

    First digit: Primary intent (1=Transition, 2=Difference, 3=Overview)
    Second digit: Secondary intent (0=None, 1=Transition, 2=Difference, 3=Overview)
    """

    P01 = "P01"  # Transition only - Single time series
    P02 = "P02"  # Difference only - Category comparison
    P03 = "P03"  # Overview only - Distribution/composition
    P12 = "P12"  # Transition + Difference - Multiple time series comparison
    P13 = "P13"  # Transition + Overview - Distribution over time
    P21 = "P21"  # Difference + Transition - Difference changes over time
    P23 = "P23"  # Difference + Overview - Category-wise distribution comparison
    P31 = "P31"  # Overview + Transition - Overall picture over time
    P32 = "P32"  # Overview + Difference - Distribution comparison between categories


class ErrorCode(str, Enum):
    """Application error codes for structured error responses."""

    E400_VALIDATION = "E400_VALIDATION"
    E413_TOO_LARGE = "E413_TOO_LARGE"
    E415_UNSUPPORTED_FORMAT = "E415_UNSUPPORTED_FORMAT"
    E422_UNPROCESSABLE = "E422_UNPROCESSABLE"
    E424_UPSTREAM_LLM = "E424_UPSTREAM_LLM"
    E408_TIMEOUT = "E408_TIMEOUT"
    E429_RATE_LIMITED = "E429_RATE_LIMITED"
    E500_INTERNAL = "E500_INTERNAL"
    E503_DEPENDENCY_UNAVAILABLE = "E503_DEPENDENCY_UNAVAILABLE"


class MCPErrorCode(IntEnum):
    """MCP JSON-RPC 2.0 standard error codes."""

    PARSE_ERROR = -32700  # Parse error
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    APPLICATION_ERROR = -32500  # Custom application errors


class OutputFormat(str, Enum):
    """Supported output image formats."""

    PNG = "png"
    SVG = "svg"


class Locale(str, Enum):
    """Supported locales for messages and labels."""

    EN = "en"
    JA = "ja"


class PipelinePhase(str, Enum):
    """Processing pipeline phases for tracking and metrics."""

    DATA_VALIDATION = "data_validation"
    PATTERN_SELECTION = "pattern_selection"
    CHART_SELECTION = "chart_selection"
    DATA_PROCESSING = "data_processing"
    DATA_MAPPING = "data_mapping"
    CHART_BUILDING = "chart_building"
    EXPORT = "export"


class AuxiliaryElement(str, Enum):
    """Available auxiliary visual elements for charts."""

    # Reference lines
    TARGET_LINE = "target_line"
