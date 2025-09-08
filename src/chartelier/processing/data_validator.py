"""Data validation and profiling using Polars."""

from __future__ import annotations

import json
from io import StringIO
from typing import Any

import polars as pl
from pydantic import BaseModel, Field

from chartelier.core.enums import ErrorCode
from chartelier.core.errors import ChartelierError
from chartelier.core.models import DataMetadata, ErrorDetail
from chartelier.infra.logging import get_logger

logger = get_logger(__name__)

# Data constraints
DATA_CONSTRAINTS: dict[str, int | str | bool] = {
    "max_cells": 1_000_000,  # 10,000 rows x 100 columns
    "max_rows": 10_000,
    "max_columns": 100,
    "sampling_strategy": "interval",  # Equidistant sampling
    "preserve_header": True,
}


class ValidatedData(BaseModel):
    """Result of data validation process."""

    df: Any = Field(..., description="Polars DataFrame (stored as Any for Pydantic compatibility)")
    metadata: DataMetadata = Field(..., description="Data metadata and statistics")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True


class DataValidator:
    """Validates and profiles input data using Polars."""

    def __init__(self) -> None:
        """Initialize the DataValidator."""
        self.constraints = DATA_CONSTRAINTS

    def validate(self, data: str, data_format: str) -> ValidatedData:
        """Validate data and extract metadata.

        Args:
            data: Raw data string (CSV or JSON).
            data_format: Format of the data ('csv' or 'json').

        Returns:
            ValidatedData containing the DataFrame, metadata, and warnings.

        Raises:
            ChartelierError: If data validation fails.
        """
        logger.debug("Starting data validation", extra={"format": data_format})

        # Check UTF-8 encoding
        if not self._check_utf8(data):
            raise ChartelierError(
                code=ErrorCode.E400_VALIDATION,
                message="Data is not valid UTF-8",
                hint="Ensure your data is UTF-8 encoded",
            )

        # Parse data into DataFrame
        try:
            dataframe = self._parse_data(data, data_format)
        except Exception as e:
            logger.exception("Failed to parse data", extra={"format": data_format, "error": str(e)})
            raise ChartelierError(
                code=ErrorCode.E422_UNPROCESSABLE,
                message=f"Failed to parse {data_format.upper()} data",
                hint=f"Ensure your data is valid {data_format.upper()} format",
                details=[ErrorDetail(reason=str(e))],
            ) from e

        # Check if data is completely empty (no columns)
        if len(dataframe.columns) == 0:
            raise ChartelierError(
                code=ErrorCode.E400_VALIDATION,
                message="Data has no columns",
                hint="Provide data with at least one column",
            )

        warnings: list[str] = []
        original_rows = len(dataframe)

        # Check constraints and apply sampling if needed
        dataframe, sampling_warning = self._check_constraints(dataframe)
        if sampling_warning:
            warnings.append(sampling_warning)

        # Generate metadata
        metadata = self._generate_metadata(dataframe, sampled=bool(sampling_warning), original_rows=original_rows)

        logger.info(
            "Data validation completed",
            extra={
                "rows": metadata.rows,
                "cols": metadata.cols,
                "sampled": metadata.sampled,
            },
        )

        return ValidatedData(df=dataframe, metadata=metadata, warnings=warnings)

    def _check_utf8(self, data: str) -> bool:
        """Check if data is valid UTF-8.

        Args:
            data: Raw data string.

        Returns:
            True if valid UTF-8, False otherwise.
        """
        try:
            data.encode("utf-8")
        except UnicodeEncodeError:
            return False
        else:
            return True

    def _parse_data(self, data: str, data_format: str) -> pl.DataFrame:
        """Parse data string into Polars DataFrame.

        Args:
            data: Raw data string.
            data_format: Format of the data ('csv' or 'json').

        Returns:
            Parsed Polars DataFrame.

        Raises:
            ValueError: If format is unsupported.
            Exception: If parsing fails.
        """
        if data_format.lower() == "csv":
            return self._parse_csv(data)
        if data_format.lower() == "json":
            return self._parse_json(data)
        msg = f"Unsupported data format: {data_format}"
        raise ValueError(msg)

    def _parse_csv(self, data: str) -> pl.DataFrame:
        """Parse CSV string into Polars DataFrame.

        Args:
            data: CSV string.

        Returns:
            Parsed DataFrame.
        """
        # Handle empty data
        if not data.strip():
            raise ValueError("Empty CSV data")

        return pl.read_csv(
            StringIO(data),
            infer_schema_length=1000,
            try_parse_dates=True,
            ignore_errors=False,
        )

    def _parse_json(self, data: str) -> pl.DataFrame:
        """Parse JSON string into Polars DataFrame.

        Args:
            data: JSON string.

        Returns:
            Parsed DataFrame.
        """
        # Try to parse as records format first
        try:
            json_data = json.loads(data)
            if isinstance(json_data, list):
                # Array of records
                return pl.DataFrame(json_data)
            if isinstance(json_data, dict):
                # Object with arrays (columnar format)
                return pl.DataFrame(json_data)
            msg = f"Unsupported JSON structure: {type(json_data)}"
            raise ValueError(msg)
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON: {e}"
            raise ValueError(msg) from e

    def _check_constraints(self, dataframe: pl.DataFrame) -> tuple[pl.DataFrame, str | None]:
        """Check data constraints and apply sampling if needed.

        Args:
            dataframe: Input DataFrame.

        Returns:
            Tuple of (processed DataFrame, warning message if sampled).
        """
        rows, cols = dataframe.shape
        total_cells = rows * cols

        # Check column limit
        max_columns = int(self.constraints["max_columns"])
        if cols > max_columns:
            raise ChartelierError(
                code=ErrorCode.E400_VALIDATION,
                message=f"Too many columns: {cols} (max: {max_columns})",
                hint=f"Reduce the number of columns to {max_columns} or less",
            )

        # Check cell limit and row limit
        max_cells = int(self.constraints["max_cells"])
        max_rows = int(self.constraints["max_rows"])
        if total_cells > max_cells or rows > max_rows:
            dataframe = self._apply_deterministic_sampling(dataframe)
            return dataframe, (
                f"Data was sampled from {rows:,} rows to {len(dataframe):,} rows "
                f"due to size limits (max {max_rows:,} rows "
                f"or {max_cells:,} cells)"
            )

        return dataframe, None

    def _apply_deterministic_sampling(self, dataframe: pl.DataFrame) -> pl.DataFrame:
        """Apply deterministic equidistant sampling to reduce data size.

        This method ensures:
        1. Deterministic results for the same input
        2. First and last rows are always included
        3. Evenly distributed sampling across the dataset

        Args:
            dataframe: Input DataFrame.

        Returns:
            Sampled DataFrame.
        """
        target_rows = self._calculate_target_rows(dataframe)

        # Handle edge cases early
        if len(dataframe) <= target_rows:
            return dataframe
        if target_rows <= 0:
            logger.warning("Target rows is 0 or negative, returning empty DataFrame")
            return dataframe.head(0)
        if target_rows == 1:
            return dataframe.head(1)

        # Calculate and apply sampling indices
        indices = self._calculate_sampling_indices(len(dataframe), target_rows)
        return self._apply_sampling_indices(dataframe, indices)

    def _calculate_target_rows(self, dataframe: pl.DataFrame) -> int:
        """Calculate the target number of rows after sampling."""
        max_rows = int(self.constraints["max_rows"])
        max_cells = int(self.constraints["max_cells"])

        return min(
            max_rows,
            max_cells // max(1, len(dataframe.columns)),
        )

    def _calculate_sampling_indices(self, total_rows: int, target_rows: int) -> list[int]:
        """Calculate deterministic sampling indices."""
        if target_rows <= 0 or total_rows <= 0:
            return []

        # Always include first and last
        indices = [0]

        # Add intermediate rows with even distribution
        if target_rows > 2:
            step = (total_rows - 1) / (target_rows - 1)
            for i in range(1, target_rows - 1):
                index = round(i * step)
                if index not in indices:
                    indices.append(index)

        # Always include last row if target_rows > 1
        last_index = total_rows - 1
        if target_rows > 1 and last_index not in indices:
            indices.append(last_index)

        # Ensure we don't exceed target_rows (handle rounding edge cases)
        if len(indices) > target_rows:
            indices = self._trim_indices(indices, target_rows)

        return sorted(indices)

    def _trim_indices(self, indices: list[int], target_rows: int) -> list[int]:
        """Trim indices list to target_rows while keeping first and last."""
        if target_rows <= 2:
            return indices[:target_rows]

        middle_count = target_rows - 2
        if middle_count <= 0:
            return [indices[0], indices[-1]][:target_rows]

        middle_indices = indices[1:-1]
        step = len(middle_indices) / middle_count
        selected_middle = [middle_indices[round(i * step)] for i in range(middle_count)]
        return [indices[0], *selected_middle, indices[-1]]

    def _apply_sampling_indices(self, dataframe: pl.DataFrame, indices: list[int]) -> pl.DataFrame:
        """Apply sampling indices to dataframe."""
        df_with_index = dataframe.with_row_index("_row_idx")
        sampled = df_with_index.filter(pl.col("_row_idx").is_in(indices))
        return sampled.drop("_row_idx")

    def _generate_metadata(
        self,
        dataframe: pl.DataFrame,
        sampled: bool = False,
        original_rows: int | None = None,
    ) -> DataMetadata:
        """Generate metadata about the DataFrame.

        Args:
            dataframe: Polars DataFrame.
            sampled: Whether data was sampled.
            original_rows: Original row count before sampling.

        Returns:
            DataMetadata object.
        """
        rows, cols = dataframe.shape

        # Map Polars dtypes to string representations
        dtypes: dict[str, str] = {}
        for col in dataframe.columns:
            dtype = dataframe[col].dtype
            if dtype in (pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64):
                dtypes[col] = "integer"
            elif dtype in (pl.Float32, pl.Float64):
                dtypes[col] = "float"
            elif dtype == pl.Boolean:
                dtypes[col] = "boolean"
            elif dtype == pl.Utf8:
                dtypes[col] = "string"
            elif dtype in (pl.Date, pl.Datetime, pl.Time):
                dtypes[col] = "datetime"
            elif dtype == pl.Categorical:
                dtypes[col] = "category"
            else:
                dtypes[col] = str(dtype).lower()

        # Check for datetime and categorical columns
        has_datetime = any(dataframe[col].dtype in (pl.Date, pl.Datetime, pl.Time) for col in dataframe.columns)
        has_category = any(
            dataframe[col].dtype == pl.Categorical
            or (dataframe[col].dtype == pl.Utf8 and rows > 0 and dataframe[col].n_unique() < rows * 0.5)
            for col in dataframe.columns
        )

        # Calculate null ratios
        null_ratio: dict[str, float] = {}
        for col in dataframe.columns:
            null_count = dataframe[col].null_count()
            null_ratio[col] = null_count / rows if rows > 0 else 0.0

        return DataMetadata(
            rows=rows,
            cols=cols,
            dtypes=dtypes,
            has_datetime=has_datetime,
            has_category=has_category,
            null_ratio=null_ratio,
            sampled=sampled,
            original_rows=original_rows if sampled else None,
        )
