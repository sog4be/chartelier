"""Data processor with safe, registered operations only."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

import polars as pl

from chartelier.core.errors import ProcessingError
from chartelier.infra.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ProcessedData:
    """Result of data processing operations."""

    df: pl.DataFrame
    operations_applied: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class DataProcessor:
    """Process data using only registered safe operations."""

    def __init__(self) -> None:
        """Initialize data processor with safe operations registry."""
        self._operations = self._get_safe_operations()

    def process(
        self,
        data: pl.DataFrame,
        template_id: str,
        operations: list[dict[str, Any]] | None = None,
    ) -> ProcessedData:
        """Process data with a sequence of safe operations.

        Args:
            data: Input DataFrame
            template_id: Template identifier (for future template-specific requirements)
            operations: List of operations to apply, each with 'name' and 'params'

        Returns:
            ProcessedData with transformed DataFrame and operation history

        Raises:
            ProcessingError: If a required operation fails
        """
        if operations is None:
            # Return original data if no operations specified
            return ProcessedData(df=data)

        result = ProcessedData(df=data.clone())

        for i, operation in enumerate(operations):
            op_name = operation.get("name")
            params = operation.get("params", {})

            if not op_name:
                result.warnings.append(f"Operation {i}: Missing operation name, skipping")
                continue

            if op_name not in self._operations:
                result.warnings.append(f"Operation '{op_name}' is not registered, skipping for safety")
                logger.warning(
                    "Unregistered operation requested",
                    extra={"operation": op_name, "template_id": template_id},
                )
                continue

            try:
                # Execute the registered operation
                result.df = self._execute_operation(result.df, op_name, params)
                result.operations_applied.append(f"{op_name}({params})")
                logger.debug(
                    "Applied operation",
                    extra={"operation": op_name, "params_keys": list(params.keys())},
                )
            except Exception as e:
                error_msg = f"Operation '{op_name}' failed: {e}"
                # Check if operation is marked as required
                if operation.get("required", False):
                    raise ProcessingError(error_msg) from e
                # Otherwise, add warning and continue with original data
                result.warnings.append(error_msg)
                logger.warning(
                    "Operation failed, continuing",
                    extra={"operation": op_name, "error": str(e)},
                )

        return result

    def _execute_operation(self, df: pl.DataFrame, op_name: str, params: dict[str, Any]) -> pl.DataFrame:
        """Execute a single safe operation.

        Args:
            df: Input DataFrame
            op_name: Operation name
            params: Operation parameters

        Returns:
            Transformed DataFrame
        """
        operation = self._operations[op_name]
        return operation(df, **params)

    def _get_safe_operations(self) -> dict[str, Callable[..., pl.DataFrame]]:
        """Get registry of safe operations.

        All operations must be:
        - Side-effect free
        - Idempotent
        - Use only Polars expression DSL (no eval/exec)

        Returns:
            Dictionary mapping operation names to functions
        """
        return {
            # Basic aggregation operations
            "groupby_agg": self._op_groupby_agg,
            "filter": self._op_filter,
            "sort": self._op_sort,
            "pivot": self._op_pivot,
            "melt": self._op_melt,
            # Sampling operations
            "sample": self._op_sample,
            "head": self._op_head,
            "tail": self._op_tail,
            # Time series operations
            "resample": self._op_resample,
            "rolling": self._op_rolling,
            # Data transformation operations
            "rename": self._op_rename,
            "select": self._op_select,
            "drop": self._op_drop,
            "cast": self._op_cast,
            "fill_null": self._op_fill_null,
            # Calculation operations
            "with_column": self._op_with_column,
            "normalize": self._op_normalize,
            "cumsum": self._op_cumsum,
            "rank": self._op_rank,
            "bin": self._op_bin,
        }

    # === Operation implementations ===

    def _op_groupby_agg(self, df: pl.DataFrame, by: str | list[str], agg: dict[str, str]) -> pl.DataFrame:
        """Group by columns and aggregate."""
        if isinstance(by, str):
            by = [by]

        agg_exprs = []
        for col, func in agg.items():
            if func == "sum":
                agg_exprs.append(pl.col(col).sum().alias(f"{col}_sum"))
            elif func == "mean":
                agg_exprs.append(pl.col(col).mean().alias(f"{col}_mean"))
            elif func == "count":
                agg_exprs.append(pl.col(col).count().alias(f"{col}_count"))
            elif func == "min":
                agg_exprs.append(pl.col(col).min().alias(f"{col}_min"))
            elif func == "max":
                agg_exprs.append(pl.col(col).max().alias(f"{col}_max"))
            elif func == "std":
                agg_exprs.append(pl.col(col).std().alias(f"{col}_std"))
            else:
                msg = f"Unsupported aggregation function: {func}"
                raise ValueError(msg)

        return df.group_by(by).agg(agg_exprs)

    def _op_filter(self, df: pl.DataFrame, condition: str) -> pl.DataFrame:
        """Filter rows based on condition using Polars expression syntax."""
        # Parse safe condition string into Polars expression
        # This is a simplified version - in production, use a proper expression parser
        try:
            # Only allow simple column comparisons for safety
            if "==" in condition:
                col, val = condition.split("==")
                col = col.strip()
                val = val.strip().strip("'\"")
                return df.filter(pl.col(col) == val)
            if ">" in condition:
                col, val = condition.split(">")
                return df.filter(pl.col(col.strip()) > float(val.strip()))
            if "<" in condition:
                col, val = condition.split("<")
                return df.filter(pl.col(col.strip()) < float(val.strip()))
            msg = f"Unsupported filter condition: {condition}"
            raise ValueError(msg)  # noqa: TRY301
        except Exception as e:
            msg = f"Invalid filter condition '{condition}': {e}"
            raise ValueError(msg) from e

    def _op_sort(self, df: pl.DataFrame, by: str | list[str], descending: bool = False) -> pl.DataFrame:
        """Sort DataFrame by columns."""
        if isinstance(by, str):
            by = [by]
        return df.sort(by, descending=descending)

    def _op_pivot(
        self,
        df: pl.DataFrame,
        values: str | list[str],
        index: str | list[str],
        columns: str | list[str],
        aggregate_function: str = "sum",
    ) -> pl.DataFrame:
        """Create pivot table."""
        # Map aggregate function string to Polars function
        agg_func_map = {
            "sum": "sum",
            "mean": "mean",
            "count": "count",
            "min": "min",
            "max": "max",
        }

        if aggregate_function not in agg_func_map:
            msg = f"Unsupported aggregate function: {aggregate_function}"
            raise ValueError(msg)

        return df.pivot(
            values=values,
            index=index,
            on=columns,
            aggregate_function=agg_func_map[aggregate_function],  # type: ignore[arg-type]
        )

    def _op_melt(
        self,
        df: pl.DataFrame,
        id_vars: list[str] | None = None,
        value_vars: list[str] | None = None,
    ) -> pl.DataFrame:
        """Melt DataFrame from wide to long format."""
        return df.melt(id_vars=id_vars, value_vars=value_vars)

    def _op_sample(self, df: pl.DataFrame, n: int | None = None, fraction: float | None = None) -> pl.DataFrame:
        """Sample rows (deterministic with fixed seed)."""
        if n is not None:
            return df.sample(n=min(n, len(df)), seed=42)
        if fraction is not None:
            return df.sample(fraction=fraction, seed=42)
        raise ValueError("Either 'n' or 'fraction' must be specified")

    def _op_head(self, df: pl.DataFrame, n: int = 5) -> pl.DataFrame:
        """Get first n rows."""
        return df.head(n)

    def _op_tail(self, df: pl.DataFrame, n: int = 5) -> pl.DataFrame:
        """Get last n rows."""
        return df.tail(n)

    def _op_resample(self, df: pl.DataFrame, time_column: str, every: str, agg: dict[str, str]) -> pl.DataFrame:
        """Resample time series data."""
        # Convert time column to datetime if needed
        df_resampled = df.with_columns(pl.col(time_column).cast(pl.Datetime))

        # Build aggregation expressions
        agg_exprs = []
        for col, func in agg.items():
            if func == "sum":
                agg_exprs.append(pl.col(col).sum())
            elif func == "mean":
                agg_exprs.append(pl.col(col).mean())
            elif func == "count":
                agg_exprs.append(pl.col(col).count())
            elif func == "min":
                agg_exprs.append(pl.col(col).min())
            elif func == "max":
                agg_exprs.append(pl.col(col).max())
            else:
                msg = f"Unsupported aggregation function: {func}"
                raise ValueError(msg)

        return df_resampled.group_by_dynamic(time_column, every=every).agg(agg_exprs)

    def _op_rolling(self, df: pl.DataFrame, window_size: int, agg: dict[str, str]) -> pl.DataFrame:
        """Apply rolling window operations."""
        result = df.clone()

        for col, func in agg.items():
            if func == "mean":
                result = result.with_columns(pl.col(col).rolling_mean(window_size).alias(f"{col}_rolling_mean"))
            elif func == "sum":
                result = result.with_columns(pl.col(col).rolling_sum(window_size).alias(f"{col}_rolling_sum"))
            elif func == "min":
                result = result.with_columns(pl.col(col).rolling_min(window_size).alias(f"{col}_rolling_min"))
            elif func == "max":
                result = result.with_columns(pl.col(col).rolling_max(window_size).alias(f"{col}_rolling_max"))
            elif func == "std":
                result = result.with_columns(pl.col(col).rolling_std(window_size).alias(f"{col}_rolling_std"))
            else:
                msg = f"Unsupported rolling function: {func}"
                raise ValueError(msg)

        return result

    def _op_rename(self, df: pl.DataFrame, mapping: dict[str, str]) -> pl.DataFrame:
        """Rename columns."""
        return df.rename(mapping)

    def _op_select(self, df: pl.DataFrame, columns: list[str]) -> pl.DataFrame:
        """Select specific columns."""
        return df.select(columns)

    def _op_drop(self, df: pl.DataFrame, columns: list[str]) -> pl.DataFrame:
        """Drop specific columns."""
        return df.drop(columns)

    def _op_cast(self, df: pl.DataFrame, column: str, dtype: str) -> pl.DataFrame:
        """Cast column to different data type."""
        dtype_map = {
            "int": pl.Int64,
            "float": pl.Float64,
            "str": pl.Utf8,
            "bool": pl.Boolean,
            "date": pl.Date,
            "datetime": pl.Datetime,
        }

        if dtype not in dtype_map:
            msg = f"Unsupported data type: {dtype}"
            raise ValueError(msg)

        return df.with_columns(pl.col(column).cast(dtype_map[dtype]))

    def _op_fill_null(
        self,
        df: pl.DataFrame,
        column: str,
        value: Any = None,  # noqa: ANN401
        strategy: str | None = None,
    ) -> pl.DataFrame:
        """Fill null values in column."""
        if value is not None:
            return df.with_columns(pl.col(column).fill_null(value))
        if strategy == "forward":
            return df.with_columns(pl.col(column).forward_fill())
        if strategy == "backward":
            return df.with_columns(pl.col(column).backward_fill())
        if strategy == "mean":
            return df.with_columns(pl.col(column).fill_null(pl.col(column).mean()))
        if strategy == "median":
            return df.with_columns(pl.col(column).fill_null(pl.col(column).median()))
        raise ValueError("Either 'value' or valid 'strategy' must be specified")

    def _op_with_column(self, df: pl.DataFrame, name: str, expression: str) -> pl.DataFrame:
        """Add new column with safe expression.

        Only supports simple arithmetic operations for safety.
        """
        # Parse safe expression - this is a simplified version
        # In production, use a proper expression parser with whitelist
        try:
            # Support basic arithmetic between columns
            if "+" in expression:
                cols = [c.strip() for c in expression.split("+")]
                expr = pl.col(cols[0])
                for col in cols[1:]:
                    expr = expr + pl.col(col)
                return df.with_columns(expr.alias(name))
            if "-" in expression:
                cols = [c.strip() for c in expression.split("-")]
                expr = pl.col(cols[0]) - pl.col(cols[1])
                return df.with_columns(expr.alias(name))
            if "*" in expression:
                cols = [c.strip() for c in expression.split("*")]
                expr = pl.col(cols[0])
                for col in cols[1:]:
                    expr = expr * float(col) if col.replace(".", "").isdigit() else expr * pl.col(col)
                return df.with_columns(expr.alias(name))
            if "/" in expression:
                cols = [c.strip() for c in expression.split("/")]
                expr = pl.col(cols[0]) / pl.col(cols[1])
                return df.with_columns(expr.alias(name))
            # Simple column reference
            return df.with_columns(pl.col(expression).alias(name))
        except Exception as e:
            msg = f"Invalid expression '{expression}': {e}"
            raise ValueError(msg) from e

    def _op_normalize(self, df: pl.DataFrame, column: str, method: str = "minmax") -> pl.DataFrame:
        """Normalize column values."""
        if method == "minmax":
            return df.with_columns(
                ((pl.col(column) - pl.col(column).min()) / (pl.col(column).max() - pl.col(column).min())).alias(
                    f"{column}_normalized"
                )
            )
        if method == "zscore":
            return df.with_columns(
                ((pl.col(column) - pl.col(column).mean()) / pl.col(column).std()).alias(f"{column}_normalized")
            )
        msg = f"Unsupported normalization method: {method}"
        raise ValueError(msg)

    def _op_cumsum(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Calculate cumulative sum."""
        return df.with_columns(pl.col(column).cum_sum().alias(f"{column}_cumsum"))

    def _op_rank(
        self, df: pl.DataFrame, column: str, method: str = "average", descending: bool = False
    ) -> pl.DataFrame:
        """Rank values in column."""
        return df.with_columns(pl.col(column).rank(method=method, descending=descending).alias(f"{column}_rank"))  # type: ignore[arg-type]

    def _op_bin(self, df: pl.DataFrame, column: str, n_bins: int = 10, labels: list[str] | None = None) -> pl.DataFrame:
        """Bin continuous values into discrete intervals."""
        # Calculate bin edges
        min_val = df[column].min()
        max_val = df[column].max()

        if min_val is None or max_val is None:
            msg = f"Column '{column}' contains only null values"
            raise ValueError(msg)

        # Create bins using qcut for equal-frequency binning
        # or cut for equal-width binning
        return df.with_columns(pl.col(column).qcut(n_bins, labels=labels).alias(f"{column}_binned"))
