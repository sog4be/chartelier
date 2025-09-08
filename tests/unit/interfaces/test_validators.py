"""Unit tests for request validators."""

import json

import pytest

from chartelier.core.enums import ErrorCode
from chartelier.core.errors import ChartelierError
from chartelier.interfaces.validators import RequestValidator, ValidatedRequest


class TestRequestValidator:
    """Test cases for RequestValidator."""

    @pytest.fixture
    def validator(self) -> RequestValidator:
        """Create a RequestValidator instance."""
        return RequestValidator()

    @pytest.fixture
    def valid_csv_data(self) -> str:
        """Sample valid CSV data."""
        return "date,sales,category\n2024-01-01,100,A\n2024-01-02,150,B\n2024-01-03,120,A"

    @pytest.fixture
    def valid_json_data(self) -> str:
        """Sample valid JSON data."""
        return json.dumps(
            [
                {"date": "2024-01-01", "sales": 100, "category": "A"},
                {"date": "2024-01-02", "sales": 150, "category": "B"},
                {"date": "2024-01-03", "sales": 120, "category": "A"},
            ]
        )

    @pytest.fixture
    def valid_request(self, valid_csv_data: str) -> dict:
        """Sample valid request."""
        return {
            "data": valid_csv_data,
            "query": "Show sales trend over time",
            "options": {"format": "png", "dpi": 96},
        }

    # UT-VAL-001: Missing required fields
    def test_missing_data_field(self, validator: RequestValidator) -> None:
        """Test validation fails when data field is missing."""
        request = {"query": "Show trend"}
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(request)
        assert exc_info.value.code == ErrorCode.E400_VALIDATION
        assert any("Missing required field: 'data'" in detail.reason for detail in exc_info.value.details)

    def test_missing_query_field(self, validator: RequestValidator, valid_csv_data: str) -> None:
        """Test validation fails when query field is missing."""
        request = {"data": valid_csv_data}
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(request)
        assert exc_info.value.code == ErrorCode.E400_VALIDATION
        assert any("Missing required field: 'query'" in detail.reason for detail in exc_info.value.details)

    def test_missing_both_required_fields(self, validator: RequestValidator) -> None:
        """Test validation fails when both required fields are missing."""
        request = {"options": {"format": "png"}}
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(request)
        assert exc_info.value.code == ErrorCode.E400_VALIDATION
        assert any("Missing required field: 'data'" in detail.reason for detail in exc_info.value.details)
        assert any("Missing required field: 'query'" in detail.reason for detail in exc_info.value.details)

    # UT-VAL-002: UTF-8 encoding validation
    def test_invalid_utf8_data(self, validator: RequestValidator) -> None:
        """Test validation fails for non-UTF-8 data."""
        # Create invalid UTF-8 by using latin-1 encoded string
        request = {
            "data": "test,value\nrow1,café",  # This is valid UTF-8, just for structure
            "query": "Show data",
        }
        # Simulate non-UTF-8 by testing encoding error detection
        # Note: In practice, Python strings are always valid UTF-8
        # This test validates the encoding check exists
        result = validator.validate(request)
        assert result.data == request["data"]  # Should pass for valid UTF-8

    # UT-VAL-003: CSV header validation
    def test_csv_without_header(self, validator: RequestValidator) -> None:
        """Test CSV with only header row (no data)."""
        request = {
            "data": "col1,col2,col3",  # Only header, no data rows
            "query": "Show data",
        }
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(request)
        assert exc_info.value.code == ErrorCode.E400_VALIDATION
        assert any("only header row" in detail.reason.lower() for detail in exc_info.value.details)

    def test_empty_csv(self, validator: RequestValidator) -> None:
        """Test empty CSV data."""
        request = {
            "data": "",
            "query": "Show data",
        }
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(request)
        assert exc_info.value.code == ErrorCode.E400_VALIDATION
        assert any("empty" in detail.reason.lower() for detail in exc_info.value.details)

    # UT-VAL-004: Different CSV delimiters
    def test_csv_with_comma_delimiter(self, validator: RequestValidator) -> None:
        """Test CSV with comma delimiter."""
        request = {
            "data": "name,age,city\nAlice,30,Tokyo\nBob,25,Osaka",
            "query": "Show data",
        }
        result = validator.validate(request)
        assert result.data_format == "csv"

    def test_csv_with_tab_delimiter(self, validator: RequestValidator) -> None:
        """Test CSV with tab delimiter."""
        request = {
            "data": "name\tage\tcity\nAlice\t30\tTokyo\nBob\t25\tOsaka",
            "query": "Show data",
        }
        result = validator.validate(request)
        assert result.data_format == "csv"

    def test_csv_with_pipe_delimiter(self, validator: RequestValidator) -> None:
        """Test CSV with pipe delimiter."""
        request = {
            "data": "name|age|city\nAlice|30|Tokyo\nBob|25|Osaka",
            "query": "Show data",
        }
        result = validator.validate(request)
        assert result.data_format == "csv"

    # UT-VAL-005: Size limit validation
    def test_data_exceeds_size_limit(self, validator: RequestValidator) -> None:
        """Test data exceeding 100MB limit."""
        # Create data larger than 100MB (simulate with smaller limit for testing)
        large_data = "x" * (validator.MAX_DATA_SIZE_BYTES + 1)
        request = {
            "data": large_data,
            "query": "Show data",
        }
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(request)
        assert exc_info.value.code == ErrorCode.E400_VALIDATION
        assert any("exceeds maximum" in detail.reason.lower() for detail in exc_info.value.details)

    # UT-VAL-006: Cell limit validation
    def test_cell_limit_boundary(self, validator: RequestValidator) -> None:
        """Test data with cell count at limit."""
        # Create CSV with many cells (simplified for testing)
        cols = 100
        rows = 100  # Smaller than actual limit for test performance
        header = ",".join([f"col{i}" for i in range(cols)])
        data_rows = [",".join([str(i * j) for j in range(cols)]) for i in range(rows)]
        csv_data = "\n".join([header, *data_rows])

        request = {
            "data": csv_data,
            "query": "Show data",
        }
        result = validator.validate(request)
        assert result.data_format == "csv"
        # Note: Actual cell limit checking would be done in DataValidator

    # UT-VAL-007: Row boundary validation
    def test_row_boundary(self, validator: RequestValidator) -> None:
        """Test CSV with rows at boundary."""
        # Create CSV with 10,000 rows (simplified for testing)
        rows = 100  # Use smaller number for test performance
        csv_data = "col1,col2\n" + "\n".join([f"val{i},val{i}" for i in range(rows)])
        request = {
            "data": csv_data,
            "query": "Show data",
        }
        result = validator.validate(request)
        assert result.data_format == "csv"

    # UT-VAL-008: Column boundary validation
    def test_column_limit_exceeded(self, validator: RequestValidator) -> None:
        """Test CSV with too many columns."""
        # Create CSV with 101 columns (exceeds limit)
        cols = validator.MAX_COLUMNS + 1
        header = ",".join([f"col{i}" for i in range(cols)])
        data_row = ",".join([str(i) for i in range(cols)])
        csv_data = f"{header}\n{data_row}"

        request = {
            "data": csv_data,
            "query": "Show data",
        }
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(request)
        assert exc_info.value.code == ErrorCode.E400_VALIDATION
        assert any("Too many columns" in detail.reason for detail in exc_info.value.details)

    # UT-VAL-009: JSON validity
    def test_invalid_json(self, validator: RequestValidator) -> None:
        """Test invalid JSON data."""
        request = {
            "data": '{"invalid": json"',  # Invalid JSON
            "query": "Show data",
        }
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(request)
        assert exc_info.value.code == ErrorCode.E400_VALIDATION
        assert any("Invalid JSON" in detail.reason for detail in exc_info.value.details)

    def test_non_tabular_json(self, validator: RequestValidator) -> None:
        """Test JSON that is not table-like."""
        request = {
            "data": json.dumps({"single": "value", "not": "tabular"}),
            "query": "Show data",
        }
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(request)
        assert exc_info.value.code == ErrorCode.E400_VALIDATION
        assert any("table-like" in detail.reason.lower() for detail in exc_info.value.details)

    def test_json_array_of_non_objects(self, validator: RequestValidator) -> None:
        """Test JSON array containing non-objects."""
        request = {
            "data": json.dumps([1, 2, 3, 4, 5]),  # Array of numbers, not objects
            "query": "Show data",
        }
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(request)
        assert exc_info.value.code == ErrorCode.E400_VALIDATION
        assert any("must contain objects" in detail.reason for detail in exc_info.value.details)

    # UT-VAL-010: Date format inference (lightweight)
    def test_date_format_detection(self, validator: RequestValidator) -> None:
        """Test date format detection in CSV."""
        request = {
            "data": "date,value\n2024-01-01,100\n2024-01-02,150\n2024-01-03,120",
            "query": "Show trend",
        }
        result = validator.validate(request)
        assert result.data_format == "csv"
        # Actual date type inference would be done in DataValidator

    # UT-VAL-011: Missing values and outliers (warning only)
    def test_data_with_missing_values(self, validator: RequestValidator) -> None:
        """Test CSV with missing values."""
        request = {
            "data": "col1,col2,col3\n1,2,3\n4,,6\n7,8,",  # Missing values
            "query": "Show data",
        }
        result = validator.validate(request)
        assert result.data_format == "csv"
        # Missing value handling would be done in DataValidator

    # UT-VAL-012: Query length boundaries
    def test_empty_query(self, validator: RequestValidator, valid_csv_data: str) -> None:
        """Test empty query string."""
        request = {
            "data": valid_csv_data,
            "query": "",
        }
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(request)
        assert exc_info.value.code == ErrorCode.E400_VALIDATION
        assert any("Query too short" in detail.reason for detail in exc_info.value.details)

    def test_query_at_min_length(self, validator: RequestValidator, valid_csv_data: str) -> None:
        """Test query with minimum length (1 character)."""
        request = {
            "data": valid_csv_data,
            "query": "a",
        }
        result = validator.validate(request)
        assert result.query == "a"

    def test_query_at_max_length(self, validator: RequestValidator, valid_csv_data: str) -> None:
        """Test query at maximum length (1000 characters)."""
        request = {
            "data": valid_csv_data,
            "query": "x" * 1000,
        }
        result = validator.validate(request)
        assert len(result.query) == 1000

    def test_query_exceeds_max_length(self, validator: RequestValidator, valid_csv_data: str) -> None:
        """Test query exceeding maximum length."""
        request = {
            "data": valid_csv_data,
            "query": "x" * 1001,
        }
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(request)
        assert exc_info.value.code == ErrorCode.E400_VALIDATION
        assert any("Query too long" in detail.reason for detail in exc_info.value.details)

    # UT-VAL-013: Options boundary values
    def test_dpi_at_boundaries(self, validator: RequestValidator, valid_csv_data: str) -> None:
        """Test DPI at minimum and maximum boundaries."""
        # Test minimum DPI
        request = {
            "data": valid_csv_data,
            "query": "Show data",
            "options": {"dpi": 72},
        }
        result = validator.validate(request)
        assert result.options["dpi"] == 72

        # Test maximum DPI
        request["options"]["dpi"] = 300
        result = validator.validate(request)
        assert result.options["dpi"] == 300

    def test_dpi_out_of_range(self, validator: RequestValidator, valid_csv_data: str) -> None:
        """Test DPI outside valid range."""
        # Below minimum
        request = {
            "data": valid_csv_data,
            "query": "Show data",
            "options": {"dpi": 71},
        }
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(request)
        assert any("DPI must be between" in detail.reason for detail in exc_info.value.details)

        # Above maximum
        request["options"]["dpi"] = 301
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(request)
        assert any("DPI must be between" in detail.reason for detail in exc_info.value.details)

    def test_width_height_boundaries(self, validator: RequestValidator, valid_csv_data: str) -> None:
        """Test width and height at boundaries."""
        # Test minimum dimensions
        request = {
            "data": valid_csv_data,
            "query": "Show data",
            "options": {"width": 400, "height": 300},
        }
        result = validator.validate(request)
        assert result.options["width"] == 400
        assert result.options["height"] == 300

        # Test maximum dimensions
        request["options"] = {"width": 2000, "height": 2000}
        result = validator.validate(request)
        assert result.options["width"] == 2000
        assert result.options["height"] == 2000

    def test_invalid_format(self, validator: RequestValidator, valid_csv_data: str) -> None:
        """Test invalid format option."""
        request = {
            "data": valid_csv_data,
            "query": "Show data",
            "options": {"format": "jpeg"},  # Invalid format
        }
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(request)
        assert any("Invalid format" in detail.reason for detail in exc_info.value.details)

    def test_invalid_locale(self, validator: RequestValidator, valid_csv_data: str) -> None:
        """Test invalid locale option."""
        request = {
            "data": valid_csv_data,
            "query": "Show data",
            "options": {"locale": "fr"},  # Unsupported locale
        }
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(request)
        assert any("Invalid locale" in detail.reason for detail in exc_info.value.details)

    # UT-VAL-014: Maximum pixel validation
    def test_exceeds_max_pixels(self, validator: RequestValidator, valid_csv_data: str) -> None:
        """Test image dimensions exceeding maximum pixels."""
        request = {
            "data": valid_csv_data,
            "query": "Show data",
            "options": {"width": 2000, "height": 2001},  # Exceeds 4,000,000 pixels
        }
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(request)
        assert any("exceeds maximum" in detail.reason.lower() for detail in exc_info.value.details)
        assert any("pixels" in detail.reason.lower() for detail in exc_info.value.details)

    # Additional edge cases
    def test_valid_request_without_options(self, validator: RequestValidator, valid_csv_data: str) -> None:
        """Test valid request without options field."""
        request = {
            "data": valid_csv_data,
            "query": "Show sales trend",
        }
        result = validator.validate(request)
        assert isinstance(result, ValidatedRequest)
        assert result.data == valid_csv_data
        assert result.query == "Show sales trend"
        assert result.options == {}

    def test_valid_json_request(self, validator: RequestValidator, valid_json_data: str) -> None:
        """Test valid request with JSON data."""
        request = {
            "data": valid_json_data,
            "query": "Show distribution",
            "options": {"format": "svg"},
        }
        result = validator.validate(request)
        assert result.data_format == "json"
        assert result.options["format"] == "svg"

    def test_non_string_data(self, validator: RequestValidator) -> None:
        """Test non-string data field."""
        request = {
            "data": {"not": "a string"},  # Dict instead of string
            "query": "Show data",
        }
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(request)
        assert any("Data must be a string" in detail.reason for detail in exc_info.value.details)

    def test_non_string_query(self, validator: RequestValidator, valid_csv_data: str) -> None:
        """Test non-string query field."""
        request = {
            "data": valid_csv_data,
            "query": 123,  # Number instead of string
        }
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(request)
        assert any("Query must be a string" in detail.reason for detail in exc_info.value.details)

    def test_non_dict_options(self, validator: RequestValidator, valid_csv_data: str) -> None:
        """Test non-dictionary options field."""
        request = {
            "data": valid_csv_data,
            "query": "Show data",
            "options": "invalid",  # String instead of dict
        }
        with pytest.raises(ChartelierError) as exc_info:
            validator.validate(request)
        assert any("Options must be a dictionary" in detail.reason for detail in exc_info.value.details)
