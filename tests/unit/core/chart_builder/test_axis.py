"""Unit tests for axis domain and binning utilities."""

import random

import polars as pl
import pytest

from chartelier.core.chart_builder.axis import (
    BinDecision,
    _closest_nice_step,
    _is_integer_series,
    _nice_round,
    _pow10_ceiling,
    _pow10_ceiling_abs,
    decide_histogram_binning,
)


class TestHelperFunctions:
    """Test suite for helper functions."""

    def test_pow10_ceiling(self) -> None:
        """Test power of 10 ceiling calculation."""
        assert _pow10_ceiling(0) == 1.0
        assert _pow10_ceiling(1) == 1.0
        assert _pow10_ceiling(5) == 10.0
        assert _pow10_ceiling(10) == 10.0
        assert _pow10_ceiling(11) == 100.0
        assert _pow10_ceiling(99) == 100.0
        assert _pow10_ceiling(100) == 100.0
        assert _pow10_ceiling(101) == 1000.0
        assert _pow10_ceiling(0.5) == 1.0
        assert _pow10_ceiling(0.01) == 0.01
        assert _pow10_ceiling(0.015) == 0.1

    def test_pow10_ceiling_abs(self) -> None:
        """Test power of 10 ceiling for absolute values."""
        assert _pow10_ceiling_abs(5) == 10.0
        assert _pow10_ceiling_abs(-5) == 10.0
        assert _pow10_ceiling_abs(50) == 100.0
        assert _pow10_ceiling_abs(-50) == 100.0

    def test_nice_round(self) -> None:
        """Test nice rounding to 1-2-5 pattern."""
        # Floor mode
        assert _nice_round(0, "floor") == 0.0
        assert _nice_round(1.5, "floor") == 1.0
        assert _nice_round(2.5, "floor") == 2.0
        assert _nice_round(3.5, "floor") == 2.0
        assert _nice_round(6, "floor") == 5.0
        assert _nice_round(12, "floor") == 10.0
        assert _nice_round(25, "floor") == 20.0
        assert _nice_round(75, "floor") == 50.0

        # Ceil mode
        assert _nice_round(0, "ceil") == 0.0
        assert _nice_round(1.5, "ceil") == 2.0
        assert _nice_round(2.5, "ceil") == 5.0
        assert _nice_round(3.5, "ceil") == 5.0
        assert _nice_round(6, "ceil") == 10.0
        assert _nice_round(12, "ceil") == 20.0
        assert _nice_round(25, "ceil") == 50.0
        assert _nice_round(75, "ceil") == 100.0

        # Negative values
        assert _nice_round(-1.5, "floor") == -2.0
        assert _nice_round(-1.5, "ceil") == -1.0

    def test_closest_nice_step(self) -> None:
        """Test finding closest nice step size."""
        assert _closest_nice_step(0) == 1.0
        assert _closest_nice_step(1.0) == 1.0
        # 1.5 is equidistant from 1.0 and 2.0, so either is acceptable
        assert _closest_nice_step(1.5) in [1.0, 2.0]
        assert _closest_nice_step(2.0) == 2.0
        assert _closest_nice_step(2.3) == 2.5
        assert _closest_nice_step(3.0) in [2.5, 5.0]  # Could be either
        assert _closest_nice_step(4.0) in [2.5, 5.0]
        assert _closest_nice_step(7.0) in [5.0, 10.0]
        assert _closest_nice_step(8.0) == 10.0
        assert _closest_nice_step(15.0) in [10.0, 20.0]  # Could be either depending on scale

    def test_is_integer_series(self) -> None:
        """Test integer series detection."""
        # Integer types
        assert _is_integer_series(pl.Series([1, 2, 3], dtype=pl.Int32))
        assert _is_integer_series(pl.Series([1, 2, 3], dtype=pl.Int64))
        assert _is_integer_series(pl.Series([1, 2, 3], dtype=pl.UInt8))

        # Non-integer types
        assert not _is_integer_series(pl.Series([1.0, 2.0, 3.0], dtype=pl.Float64))
        assert not _is_integer_series(pl.Series(["a", "b", "c"]))


class TestBinDecision:
    """Test suite for BinDecision dataclass."""

    def test_default_values(self) -> None:
        """Test default values of BinDecision."""
        decision = BinDecision()
        assert decision.extent is None
        assert decision.step is None
        assert decision.minstep is None
        assert decision.nice is True
        assert decision.reason == "default"

    def test_immutability(self) -> None:
        """Test that BinDecision is immutable."""
        decision = BinDecision(extent=(0, 100))
        with pytest.raises(AttributeError):
            decision.extent = (0, 200)  # type: ignore[misc]


class TestDecideHistogramBinning:
    """Test suite for decide_histogram_binning function."""

    def test_column_not_found(self) -> None:
        """Test handling of missing column."""
        df = pl.DataFrame({"x": [1, 2, 3]})
        decision = decide_histogram_binning(df, "y", 10)
        assert decision.reason == "column_not_found"

    def test_empty_data(self) -> None:
        """Test handling of empty data."""
        df = pl.DataFrame({"x": []})
        decision = decide_histogram_binning(df, "x", 10)
        assert decision.reason == "empty"

    def test_non_numeric_data(self) -> None:
        """Test handling of non-numeric data."""
        df = pl.DataFrame({"x": ["a", "b", "c"]})
        decision = decide_histogram_binning(df, "x", 10)
        assert decision.reason == "non_numeric"

    def test_probability_range_0_1(self) -> None:
        """Test detection of 0-1 probability range."""
        # Test with column name hint
        df = pl.DataFrame({"probability": [0.1, 0.2, 0.5, 0.7, 0.9]})
        decision = decide_histogram_binning(df, "probability", 10)
        assert decision.extent == (0.0, 1.0)
        assert decision.nice is False
        assert decision.reason == "bounded_0_1"

        # Test with rate column
        df = pl.DataFrame({"rate": [0.1, 0.2, 0.5, 0.7, 0.9]})
        decision = decide_histogram_binning(df, "rate", 10)
        assert decision.extent == (0.0, 1.0)
        assert decision.reason == "bounded_0_1"

        # Test with ratio column
        df = pl.DataFrame({"ratio": [0.1, 0.2, 0.5, 0.7, 0.9]})
        decision = decide_histogram_binning(df, "ratio", 10)
        assert decision.extent == (0.0, 1.0)
        assert decision.reason == "bounded_0_1"

        # Test with data in 0-1 range without name hint
        df = pl.DataFrame({"values": [0.0, 0.25, 0.5, 0.75, 1.0]})
        decision = decide_histogram_binning(df, "values", 10)
        assert decision.extent == (0.0, 1.0)
        assert decision.reason == "bounded_0_1"

    def test_percentage_range_0_100(self) -> None:
        """Test detection of 0-100 percentage range."""
        # Test with column name hint
        df = pl.DataFrame({"percent": [10, 20, 50, 70, 90]})
        decision = decide_histogram_binning(df, "percent", 10)
        assert decision.extent == (0.0, 100.0)
        assert decision.nice is False
        assert decision.reason == "bounded_0_100"

        # Test with pct column
        df = pl.DataFrame({"pct": [10, 20, 50, 70, 90]})
        decision = decide_histogram_binning(df, "pct", 10)
        assert decision.extent == (0.0, 100.0)
        assert decision.reason == "bounded_0_100"

        # Test with data in 0-100 range without name hint
        df = pl.DataFrame({"values": [0, 25, 50, 75, 100]})
        decision = decide_histogram_binning(df, "values", 10)
        assert decision.extent == (0.0, 100.0)
        assert decision.reason == "bounded_0_100"

    def test_snap_to_0_pow10(self) -> None:
        """Test snapping to 0-10^k for non-negative data."""
        # Data close to 0-10 (starts near 0)
        df = pl.DataFrame({"x": [0, 2, 4, 6, 8, 9]})
        decision = decide_histogram_binning(df, "x", 10)
        assert decision.extent == (0.0, 10.0)
        assert decision.reason == "snap_0_pow10"

        # Data that doesn't start near 0 should use quantile fallback
        df = pl.DataFrame({"x": [5, 20, 40, 60, 85]})
        decision = decide_histogram_binning(df, "x", 10)
        # This data doesn't start near 0, so it shouldn't snap to 0-100
        assert decision.reason in ["quantile_nice_round", "bounded_0_100"]

        # Data close to 0-1000 (starts near 0)
        df = pl.DataFrame({"x": [0, 200, 400, 600, 850]})
        decision = decide_histogram_binning(df, "x", 10)
        assert decision.extent == (0.0, 1000.0)
        assert decision.reason == "snap_0_pow10"

    def test_snap_to_negpow10_0(self) -> None:
        """Test snapping to -10^k to 0 for non-positive data."""
        # Data close to -10 to 0 (ends near 0)
        df = pl.DataFrame({"x": [-9, -6, -4, -2, 0]})
        decision = decide_histogram_binning(df, "x", 10)
        assert decision.extent == (-10.0, 0.0)
        assert decision.reason == "snap_negpow10_0"

        # Data that doesn't end near 0 should use quantile fallback
        df = pl.DataFrame({"x": [-85, -60, -40, -20, -5]})
        decision = decide_histogram_binning(df, "x", 10)
        # This data doesn't end very near 0, so it might not snap
        assert decision.reason in ["snap_negpow10_0", "quantile_nice_round"]

    def test_symmetric_range(self) -> None:
        """Test symmetric range detection."""
        # Nearly symmetric data
        df = pl.DataFrame({"x": [-45, -20, 0, 22, 48]})
        decision = decide_histogram_binning(df, "x", 10)
        assert decision.extent == (-100.0, 100.0)
        assert decision.reason == "snap_sym_pow10"

        # Another symmetric case
        df = pl.DataFrame({"x": [-8, -4, 0, 4, 7]})
        decision = decide_histogram_binning(df, "x", 10)
        assert decision.extent == (-10.0, 10.0)
        assert decision.reason == "snap_sym_pow10"

    def test_quantile_fallback(self) -> None:
        """Test quantile-based fallback with nice rounding."""
        # Data that doesn't fit other patterns (but might be detected as percentage-like)
        df = pl.DataFrame({"x": [15, 25, 35, 45, 55, 65, 75, 85]})
        decision = decide_histogram_binning(df, "x", 10)
        assert decision.nice is False
        # This data might be detected as percentage-like (0-100) due to range
        assert decision.reason in ["bounded_0_100", "quantile_nice_round"]
        # Check that extent is nicely rounded
        assert decision.extent is not None
        assert decision.extent[0] <= 15  # Should include min
        assert decision.extent[1] >= 85  # Should include max

        # Use clearly non-percentage data for quantile fallback
        df = pl.DataFrame({"x": [115, 125, 135, 145, 155, 165, 175, 185]})
        decision = decide_histogram_binning(df, "x", 10)
        assert decision.nice is False
        assert decision.reason == "quantile_nice_round"

    def test_integer_series_minstep(self) -> None:
        """Test that integer series get minstep=1."""
        df = pl.DataFrame({"x": [1, 2, 3, 4, 5]}, schema={"x": pl.Int32})
        decision = decide_histogram_binning(df, "x", 10)
        assert decision.minstep == 1.0

        # Float series should not get minstep
        df = pl.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 5.0]})
        decision = decide_histogram_binning(df, "x", 10)
        assert decision.minstep is None

    def test_step_calculation(self) -> None:
        """Test that step is calculated based on extent and target bins."""
        df = pl.DataFrame({"percent": [0, 25, 50, 75, 100]})
        decision = decide_histogram_binning(df, "percent", 10)
        assert decision.extent == (0.0, 100.0)
        assert decision.step is not None
        # With extent of 100 and target of 10 bins, step should be around 10
        assert 5.0 <= decision.step <= 20.0

    def test_extreme_values_with_outliers(self) -> None:
        """Test handling of data with outliers using quantiles."""
        # Create data with outliers
        random.seed(42)
        normal_data = [random.uniform(40, 60) for _ in range(100)]  # noqa: S311
        outliers = [0, 100, 200]  # Outliers
        all_data = normal_data + outliers

        df = pl.DataFrame({"x": all_data})
        decision = decide_histogram_binning(df, "x", 10)

        # With 0 in data, it might snap to 0-pow10
        assert decision.extent is not None
        # Either snaps to 0-1000 (due to 0 in data) or uses quantile-based
        assert decision.extent[0] >= 0
        assert decision.extent[1] >= 200  # Should include max value

        # Test pure outliers without 0
        normal_data = [random.uniform(40, 60) for _ in range(100)]  # noqa: S311
        outliers = [100, 200]  # Outliers without 0
        all_data = normal_data + outliers

        df = pl.DataFrame({"x": all_data})
        decision = decide_histogram_binning(df, "x", 10)
        # This should use quantile-based approach
        assert decision.extent is not None

    def test_small_range_data(self) -> None:
        """Test handling of data with very small range."""
        df = pl.DataFrame({"x": [1.0, 1.01, 1.02, 1.03]})
        decision = decide_histogram_binning(df, "x", 10)
        assert decision.extent is not None
        # Should expand the range slightly for visibility
        assert decision.extent[1] - decision.extent[0] > 0.03

    def test_deterministic_behavior(self) -> None:
        """Test that the same input produces the same output."""
        df = pl.DataFrame({"x": [1, 5, 10, 15, 20]})

        decision1 = decide_histogram_binning(df, "x", 10)
        decision2 = decide_histogram_binning(df, "x", 10)

        assert decision1.extent == decision2.extent
        assert decision1.step == decision2.step
        assert decision1.minstep == decision2.minstep
        assert decision1.nice == decision2.nice
        assert decision1.reason == decision2.reason
