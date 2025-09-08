"""Request validators for Chartelier interfaces."""

import csv
import io
import json
from typing import Any, ClassVar

from pydantic import BaseModel, Field, ValidationError, field_validator

from chartelier.core.enums import ErrorCode
from chartelier.core.errors import ChartelierError
from chartelier.core.models import ErrorDetail


class ValidatedRequest(BaseModel):
    """Validated request data."""

    data: str = Field(..., description="CSV or JSON data string")
    query: str = Field(..., min_length=1, max_length=1000, description="Natural language query")
    options: dict[str, Any] = Field(default_factory=dict, description="Visualization options")
    data_format: str = Field(..., description="Detected data format (csv or json)")
    data_size_bytes: int = Field(..., description="Size of data in bytes")

    @field_validator("query")
    @classmethod
    def validate_query_length(cls, v: str) -> str:
        """Validate query length."""
        if len(v) == 0:
            raise ValueError("Query cannot be empty")
        if len(v) > 1000:
            raise ValueError("Query exceeds maximum length of 1000 characters")
        return v


class RequestValidator:
    """Validator for incoming visualization requests.

    This is a pure function component that performs format validation
    without any external dependencies.
    """

    # Validation constraints
    MAX_DATA_SIZE_MB = 100
    MAX_DATA_SIZE_BYTES = MAX_DATA_SIZE_MB * 1024 * 1024
    MAX_CELLS = 1_000_000
    MAX_ROWS = 10_000
    MAX_COLUMNS = 100
    MAX_QUERY_LENGTH = 1000
    MIN_QUERY_LENGTH = 1
    MAX_IMAGE_PIXELS = 4_000_000

    # Option constraints
    DPI_MIN = 72
    DPI_MAX = 300
    WIDTH_MIN = 400
    WIDTH_MAX = 2000
    HEIGHT_MIN = 300
    HEIGHT_MAX = 2000
    VALID_FORMATS: ClassVar[list[str]] = ["png", "svg"]
    VALID_LOCALES: ClassVar[list[str]] = ["ja", "en"]

    def validate(self, request: dict[str, Any]) -> ValidatedRequest:
        """Validate a visualization request.

        Args:
            request: Raw request dictionary

        Returns:
            ValidatedRequest object

        Raises:
            ChartelierError: If validation fails
        """
        errors = []

        # Check required fields
        if "data" not in request:
            errors.append("Missing required field: 'data'")
        if "query" not in request:
            errors.append("Missing required field: 'query'")

        if errors:
            error_details = [ErrorDetail(reason=error) for error in errors]
            raise ChartelierError(
                code=ErrorCode.E400_VALIDATION,
                message="Request validation failed",
                details=error_details,
                hint="Ensure both 'data' and 'query' fields are present in the request",
            )

        data = request["data"]
        query = request["query"]
        options = request.get("options", {})

        # Validate data
        data_validation = self._validate_data(data)
        if data_validation["errors"]:
            error_details = [ErrorDetail(field="data", reason=error) for error in data_validation["errors"]]
            raise ChartelierError(
                code=ErrorCode.E400_VALIDATION,
                message="Data validation failed",
                details=error_details,
                hint=data_validation.get("hint", "Check your data format and encoding"),
            )

        # Validate query
        query_validation = self._validate_query(query)
        if query_validation["errors"]:
            error_details = [ErrorDetail(field="query", reason=error) for error in query_validation["errors"]]
            raise ChartelierError(
                code=ErrorCode.E400_VALIDATION,
                message="Query validation failed",
                details=error_details,
                hint=query_validation.get("hint", "Query must be between 1 and 1000 characters"),
            )

        # Validate options
        options_validation = self._validate_options(options)
        if options_validation["errors"]:
            error_details = [ErrorDetail(field="options", reason=error) for error in options_validation["errors"]]
            raise ChartelierError(
                code=ErrorCode.E400_VALIDATION,
                message="Options validation failed",
                details=error_details,
                hint=options_validation.get("hint", "Check option values are within valid ranges"),
            )

        # Create validated request
        try:
            return ValidatedRequest(
                data=data,
                query=query,
                options=options,
                data_format=data_validation["format"],
                data_size_bytes=data_validation["size_bytes"],
            )
        except ValidationError as e:
            error_details = [
                ErrorDetail(
                    field=str(err.get("loc", [""])[0]) if err.get("loc") else "", reason=err.get("msg", str(err))
                )
                for err in e.errors()
            ]
            raise ChartelierError(
                code=ErrorCode.E400_VALIDATION,
                message="Failed to create validated request",
                details=error_details,
            ) from e

    def _validate_data(self, data: object) -> dict[str, Any]:
        """Validate data field.

        Args:
            data: Data to validate

        Returns:
            Validation result dictionary
        """
        result: dict[str, Any] = {"errors": [], "format": None, "size_bytes": 0, "hint": None}

        # Check if data is a string
        if not isinstance(data, str):
            result["errors"].append("Data must be a string")
            result["hint"] = "Provide data as a CSV or JSON string"
            return result

        # Check size
        size_bytes = len(data.encode("utf-8"))
        result["size_bytes"] = size_bytes
        if size_bytes > self.MAX_DATA_SIZE_BYTES:
            result["errors"].append(
                f"Data size ({size_bytes / 1024 / 1024:.1f}MB) exceeds maximum of {self.MAX_DATA_SIZE_MB}MB"
            )
            result["hint"] = "Reduce data size or use sampling"
            return result

        # Check if empty
        if not data.strip():
            result["errors"].append("Data cannot be empty")
            result["hint"] = "Provide valid CSV or JSON data"
            return result

        # Check UTF-8 encoding
        try:
            data.encode("utf-8")
        except UnicodeEncodeError:
            result["errors"].append("Data contains invalid UTF-8 characters")
            result["hint"] = "Ensure data is properly UTF-8 encoded"
            return result

        # Detect format
        data_format = self._detect_data_format(data)
        if not data_format:
            result["errors"].append("Unable to determine data format (expected CSV or JSON)")
            result["hint"] = "Provide data in valid CSV or JSON format"
            return result

        result["format"] = data_format

        # Format-specific validation
        if data_format == "csv":
            csv_validation = self._validate_csv(data)
            result["errors"].extend(csv_validation.get("errors", []))
            if csv_validation.get("hint"):
                result["hint"] = csv_validation["hint"]
            result.update(csv_validation)
        elif data_format == "json":
            json_validation = self._validate_json(data)
            result["errors"].extend(json_validation.get("errors", []))
            if json_validation.get("hint"):
                result["hint"] = json_validation["hint"]
            result.update(json_validation)

        return result

    def _validate_query(self, query: object) -> dict[str, Any]:
        """Validate query field.

        Args:
            query: Query to validate

        Returns:
            Validation result dictionary
        """
        result: dict[str, Any] = {"errors": [], "hint": None}

        # Check if query is a string
        if not isinstance(query, str):
            result["errors"].append("Query must be a string")
            result["hint"] = "Provide a natural language description of your visualization intent"
            return result

        # Check length
        query_length = len(query)
        if query_length < self.MIN_QUERY_LENGTH:
            result["errors"].append(f"Query too short (minimum {self.MIN_QUERY_LENGTH} character)")
            result["hint"] = "Provide a meaningful query describing what you want to visualize"
        elif query_length > self.MAX_QUERY_LENGTH:
            result["errors"].append(f"Query too long (maximum {self.MAX_QUERY_LENGTH} characters, got {query_length})")
            result["hint"] = "Shorten your query to focus on the key visualization intent"

        return result

    def _validate_options(self, options: object) -> dict[str, Any]:
        """Validate options field.

        Args:
            options: Options to validate

        Returns:
            Validation result dictionary
        """
        result: dict[str, Any] = {"errors": [], "hint": None}

        # Options can be None or empty
        if options is None:
            return result

        # Check if options is a dictionary
        if not isinstance(options, dict):
            result["errors"].append("Options must be a dictionary")
            result["hint"] = "Provide options as key-value pairs"
            return result

        # Validate individual option fields
        self._validate_format_option(options, result)
        self._validate_dpi_option(options, result)
        self._validate_width_option(options, result)
        self._validate_height_option(options, result)
        self._validate_total_pixels(options, result)
        self._validate_locale_option(options, result)

        return result

    def _validate_format_option(self, options: dict[str, Any], result: dict[str, Any]) -> None:
        """Validate format option."""
        if "format" in options:
            format_value = options["format"]
            if format_value not in self.VALID_FORMATS:
                result["errors"].append(
                    f"Invalid format '{format_value}'. Must be one of: {', '.join(self.VALID_FORMATS)}"
                )

    def _validate_dpi_option(self, options: dict[str, Any], result: dict[str, Any]) -> None:
        """Validate DPI option."""
        if "dpi" in options:
            dpi = options["dpi"]
            if not isinstance(dpi, int):
                result["errors"].append("DPI must be an integer")
            elif not (self.DPI_MIN <= dpi <= self.DPI_MAX):
                result["errors"].append(f"DPI must be between {self.DPI_MIN} and {self.DPI_MAX} (got {dpi})")

    def _validate_width_option(self, options: dict[str, Any], result: dict[str, Any]) -> None:
        """Validate width option."""
        if "width" in options:
            width = options["width"]
            if not isinstance(width, int):
                result["errors"].append("Width must be an integer")
            elif not (self.WIDTH_MIN <= width <= self.WIDTH_MAX):
                result["errors"].append(f"Width must be between {self.WIDTH_MIN} and {self.WIDTH_MAX} (got {width})")

    def _validate_height_option(self, options: dict[str, Any], result: dict[str, Any]) -> None:
        """Validate height option."""
        if "height" in options:
            height = options["height"]
            if not isinstance(height, int):
                result["errors"].append("Height must be an integer")
            elif not (self.HEIGHT_MIN <= height <= self.HEIGHT_MAX):
                result["errors"].append(
                    f"Height must be between {self.HEIGHT_MIN} and {self.HEIGHT_MAX} (got {height})"
                )

    def _validate_total_pixels(self, options: dict[str, Any], result: dict[str, Any]) -> None:
        """Validate total image pixels."""
        if "width" in options and "height" in options:
            width = options["width"]
            height = options["height"]
            if isinstance(width, int) and isinstance(height, int):
                total_pixels = width * height
                if total_pixels > self.MAX_IMAGE_PIXELS:
                    result["errors"].append(
                        f"Total image size ({total_pixels:,} pixels) exceeds maximum of "
                        f"{self.MAX_IMAGE_PIXELS:,} pixels"
                    )
                    result["hint"] = "Reduce width or height to stay within pixel limit"

    def _validate_locale_option(self, options: dict[str, Any], result: dict[str, Any]) -> None:
        """Validate locale option."""
        if "locale" in options:
            locale = options["locale"]
            if locale not in self.VALID_LOCALES:
                result["errors"].append(f"Invalid locale '{locale}'. Must be one of: {', '.join(self.VALID_LOCALES)}")

    def _detect_data_format(self, data: str) -> str | None:
        """Detect data format (CSV or JSON).

        Args:
            data: Data string to analyze

        Returns:
            'csv', 'json', or None if format cannot be determined
        """
        data_stripped = data.strip()

        # If it looks like JSON (starts with { or [), treat it as JSON
        # even if it fails to parse (will be caught in validation)
        if data_stripped.startswith(("[", "{")):
            return "json"

        # Try CSV
        try:
            # Use csv.Sniffer to detect CSV format
            sniffer = csv.Sniffer()
            sample = data_stripped[:8192]  # Use first 8KB as sample
            sniffer.sniff(sample)
        except csv.Error:
            pass
        else:
            return "csv"

        # Fallback: if it contains common CSV patterns
        lines = data_stripped.split("\n", 2)
        if len(lines) >= 2:
            # Check for comma, tab, or pipe delimiters
            for delimiter in [",", "\t", "|"]:
                if delimiter in lines[0] and delimiter in lines[1]:
                    return "csv"

        return None

    def _validate_csv(self, data: str) -> dict[str, Any]:
        """Validate CSV data.

        Args:
            data: CSV string to validate

        Returns:
            Validation result dictionary
        """
        result: dict[str, Any] = {"errors": [], "hint": None, "estimated_cells": 0}

        try:
            # Parse CSV to check structure
            reader = csv.reader(io.StringIO(data))
            rows = list(reader)

            if not rows:
                result["errors"].append("CSV data is empty")
                result["hint"] = "Provide at least a header row and one data row"
                return result

            # Check for header
            if len(rows) == 1:
                result["errors"].append("CSV has only header row, no data")
                result["hint"] = "Add data rows to your CSV"
                return result

            # Check dimensions
            num_rows = len(rows) - 1  # Exclude header
            num_cols = len(rows[0]) if rows else 0
            estimated_cells = num_rows * num_cols

            result["estimated_cells"] = estimated_cells

            # Check cell limit
            if estimated_cells > self.MAX_CELLS:
                # This is a warning, not an error - will trigger sampling
                pass  # Sampling will be handled by DataValidator

            # Check row limit
            if num_rows > self.MAX_ROWS:
                # This is a warning, not an error - will trigger sampling
                pass  # Sampling will be handled by DataValidator

            # Check column limit
            if num_cols > self.MAX_COLUMNS:
                result["errors"].append(f"Too many columns ({num_cols}). Maximum is {self.MAX_COLUMNS}")
                result["hint"] = "Reduce the number of columns in your data"

            # Check for consistent column count
            for _i, row in enumerate(rows[1:], start=2):
                if len(row) != num_cols:
                    # Warning only, can still process
                    break

        except (csv.Error, TypeError, ValueError) as e:
            result["errors"].append(f"Failed to parse CSV: {e}")
            result["hint"] = "Ensure your CSV is properly formatted with consistent delimiters"

        return result

    def _validate_json(self, data: str) -> dict[str, Any]:
        """Validate JSON data.

        Args:
            data: JSON string to validate

        Returns:
            Validation result dictionary
        """
        result: dict[str, Any] = {"errors": [], "hint": None, "estimated_cells": 0}

        try:
            parsed = json.loads(data)

            # Check if it's table-like (array of objects or nested structure)
            if isinstance(parsed, list):
                if not parsed:
                    result["errors"].append("JSON array is empty")
                    result["hint"] = "Provide an array with at least one data object"
                    return result

                # Check if all elements are dictionaries (table-like)
                if all(isinstance(item, dict) for item in parsed):
                    # Estimate dimensions
                    num_rows = len(parsed)
                    num_cols = len(set().union(*(item.keys() for item in parsed))) if parsed else 0
                    estimated_cells = num_rows * num_cols

                    result["estimated_cells"] = estimated_cells

                    # Check limits
                    if num_rows > self.MAX_ROWS:
                        # Warning, not error - will trigger sampling
                        pass

                    if num_cols > self.MAX_COLUMNS:
                        result["errors"].append(f"Too many columns ({num_cols}). Maximum is {self.MAX_COLUMNS}")
                        result["hint"] = "Reduce the number of fields in your JSON objects"

                else:
                    result["errors"].append("JSON array must contain objects for table-like data")
                    result["hint"] = "Provide an array of objects with consistent fields"

            elif isinstance(parsed, dict):
                # Check if it's a valid table-like structure (e.g., {"columns": [...], "data": [...]})
                if "data" in parsed or "records" in parsed or "rows" in parsed:
                    # Acceptable table-like format
                    pass
                else:
                    result["errors"].append("JSON object does not represent table-like data")
                    result["hint"] = "Provide data as an array of objects or a structured table format"
            else:
                result["errors"].append("JSON must be an array or object representing tabular data")
                result["hint"] = "Provide data as an array of objects"

        except json.JSONDecodeError as e:
            result["errors"].append(f"Invalid JSON: {e}")
            result["hint"] = "Ensure your JSON is properly formatted"
        except (TypeError, ValueError, AttributeError) as e:
            result["errors"].append(f"Failed to validate JSON structure: {e}")

        return result
