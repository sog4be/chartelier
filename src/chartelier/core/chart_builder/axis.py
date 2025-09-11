"""Axis domain and binning utilities for chart templates."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import polars as pl

# Constants for binning decisions
EPS = 1e-12
CLOSE_FRAC = 0.10  # "Close enough to boundary" threshold (10%)
SYMM_FRAC = 0.20  # Symmetry threshold (20%)
NICE_STEPS_UNIT = (1.0, 2.0, 2.5, 5.0)

# Pattern matching for column names
PERCENT_HINT = re.compile(r"(percent|pct|%)", re.IGNORECASE)
RATIO_HINT = re.compile(r"(prob|rate|ratio)", re.IGNORECASE)


@dataclass(frozen=True)
class BinDecision:
    """Binning decision for histogram X-axis.

    Attributes:
        extent: Tuple of (lower, upper) bounds for the axis, or None to let Vega-Lite decide
        step: Bin width, or None to use maxbins instead
        minstep: Minimum step size (e.g., 1 for integer series)
        nice: Whether to use Vega-Lite's nice rounding
        reason: Human-readable reason for the decision
    """

    extent: tuple[float, float] | None = None
    step: float | None = None
    minstep: float | None = None
    nice: bool = True
    reason: str = "default"


def _pow10_ceiling(x: float) -> float:
    """Find the smallest power of 10 >= x.

    Args:
        x: Input value

    Returns:
        Smallest power of 10 that is >= x
    """
    if x <= 0:
        return 1.0
    k = math.floor(math.log10(x))
    p = 10.0**k
    return p if x <= p + EPS else 10.0 * p


def _pow10_ceiling_abs(x: float) -> float:
    """Find the smallest power of 10 >= |x|.

    Args:
        x: Input value

    Returns:
        Smallest power of 10 that is >= |x|
    """
    return _pow10_ceiling(abs(x))


def _nice_round(value: float, mode: str = "floor") -> float:
    """Round a value to nice numbers (1, 2, 5, 10 pattern).

    Args:
        value: Value to round
        mode: "floor" for rounding down, "ceil" for rounding up

    Returns:
        Nicely rounded value
    """
    if value == 0:
        return 0.0

    sign = 1.0 if value > 0 else -1.0
    v = abs(value)
    k = math.floor(math.log10(v))
    base = 10.0**k
    candidates = [m * base for m in (1.0, 2.0, 5.0, 10.0)]

    if sign > 0:
        if mode == "floor":
            cand = max([c for c in candidates if c <= v + EPS] or [v])
        else:  # ceil
            cand = min([c for c in candidates if c >= v - EPS] or [v])
    # For negative values, floor means more negative, ceil means less negative
    elif mode == "floor":
        cand = min([c for c in candidates if c >= v - EPS] or [v])
    else:  # ceil
        cand = max([c for c in candidates if c <= v + EPS] or [v])

    return sign * cand


def _closest_nice_step(desired: float) -> float:
    """Find the closest nice step size to the desired value.

    Args:
        desired: Desired step size

    Returns:
        Closest nice step size from the 1-2-2.5-5 pattern
    """
    if desired <= 0:
        return 1.0

    k = math.floor(math.log10(desired))
    base = 10.0**k

    # Include both current scale and next scale for better matching
    cands = []
    for scale in [base / 10.0, base, base * 10.0]:
        for mult in NICE_STEPS_UNIT:
            cands.append(mult * scale)

    # Find the closest candidate
    return min(cands, key=lambda s: abs(s - desired))


def _is_integer_series(s: pl.Series) -> bool:
    """Check if a series contains integer data.

    Args:
        s: Polars series to check

    Returns:
        True if the series has integer dtype
    """
    return s.dtype in (
        pl.Int8,
        pl.Int16,
        pl.Int32,
        pl.Int64,
        pl.UInt8,
        pl.UInt16,
        pl.UInt32,
        pl.UInt64,
    )


def decide_histogram_binning(df: pl.DataFrame, col: str, target_bins: int) -> BinDecision:  # noqa: C901, PLR0911, PLR0912, PLR0915
    """Decide histogram X-axis extent and step for optimal binning.

    This function implements a decision tree for determining the best binning
    strategy based on data characteristics and column semantics:
    1. Natural boundaries (0-1 for probabilities, 0-100 for percentages)
    2. Power-of-10 snapping for clean ranges
    3. Symmetric ranges for data spanning negative and positive
    4. Quantile-based fallback with nice rounding

    Args:
        df: DataFrame containing the data
        col: Column name to analyze
        target_bins: Target number of bins (e.g., from Sturges' rule)

    Returns:
        BinDecision with extent, step, and other binning parameters
    """
    if col not in df.columns:
        return BinDecision(reason="column_not_found")

    s = df[col].drop_nulls()
    if s.len() == 0:
        return BinDecision(reason="empty")

    # Try to cast to numeric
    try:
        s = s.cast(pl.Float64, strict=True)  # Use strict=True to catch non-numeric
    except Exception:  # noqa: BLE001
        return BinDecision(reason="non_numeric")

    # Filter out null values after casting
    s = s.drop_nulls()
    if s.len() == 0:
        return BinDecision(reason="empty")

    # Calculate statistics
    name = col.lower()
    q01 = float(s.quantile(0.01) or 0.0)
    q99 = float(s.quantile(0.99) or 0.0)
    minv = float(s.min() or 0.0)  # type: ignore[arg-type]
    maxv = float(s.max() or 0.0)  # type: ignore[arg-type]

    # Check if integer series for minstep
    is_integer = _is_integer_series(df[col])

    # A) Check for 0-1 range (probabilities, ratios, rates)
    is_prob_like = bool(RATIO_HINT.search(name)) or (minv >= -1e-9 and maxv <= 1.0 + 1e-9)
    if is_prob_like and maxv <= 1.0 + 1e-6 and minv >= -1e-6:
        L, U = 0.0, 1.0  # noqa: N806
        desired = (U - L) / max(1, target_bins)
        step = _closest_nice_step(desired)
        minstep = 1.0 if is_integer else None
        return BinDecision(extent=(L, U), step=step, minstep=minstep, nice=False, reason="bounded_0_1")

    # B) Check for 0-100 range (percentages)
    is_percent_like = bool(PERCENT_HINT.search(name))
    # Also check if data is in percentage-like range even without name hint
    if not is_percent_like and minv >= 0 and maxv <= 100 and (maxv > 50 or (maxv - minv) > 30):
        is_percent_like = True

    if is_percent_like and maxv <= 100.0 + 1e-6 and minv >= -1e-6:
        L, U = 0.0, 100.0  # noqa: N806
        desired = (U - L) / max(1, target_bins)
        step = _closest_nice_step(desired)
        minstep = 1.0 if is_integer else None
        return BinDecision(extent=(L, U), step=step, minstep=minstep, nice=False, reason="bounded_0_100")

    # C) Snap to 0-10^k for non-negative data
    if minv >= -EPS:
        Ustar = _pow10_ceiling(maxv + EPS)  # noqa: N806
        # Calculate how much blank space would be added
        data_range = maxv - minv
        blank_frac_top = (Ustar - maxv) / data_range if data_range > EPS else 0

        # Check if data starts near zero (absolute value check)
        near_zero = abs(minv) <= CLOSE_FRAC * data_range if data_range > EPS else True

        # Only snap if the blank space is small OR data starts near zero
        if blank_frac_top <= CLOSE_FRAC or near_zero:
            L, U = 0.0, Ustar  # noqa: N806
            desired = (U - L) / max(1, target_bins)
            step = _closest_nice_step(desired)
            minstep = 1.0 if is_integer else None
            return BinDecision(extent=(L, U), step=step, minstep=minstep, nice=False, reason="snap_0_pow10")

    # D) Snap to -10^k to 0 for non-positive data
    if maxv <= EPS:
        Lstar = -_pow10_ceiling(abs(minv) + EPS)  # noqa: N806
        # Calculate how much blank space would be added
        data_range = abs(minv - maxv)
        blank_frac_bot = (abs(Lstar) - abs(minv)) / data_range if data_range > EPS else 0

        # Check if data ends near zero (absolute value check)
        near_zero = abs(maxv) <= CLOSE_FRAC * data_range if data_range > EPS else True

        # Only snap if the blank space is small OR data ends near zero
        if blank_frac_bot <= CLOSE_FRAC or near_zero:
            L, U = Lstar, 0.0  # noqa: N806
            desired = (U - L) / max(1, target_bins)
            step = _closest_nice_step(desired)
            minstep = 1.0 if is_integer else None
            return BinDecision(extent=(L, U), step=step, minstep=minstep, nice=False, reason="snap_negpow10_0")

    # E) Symmetric range (-U, +U)
    if minv < 0 < maxv:
        abs_minv = abs(minv)
        abs_maxv = abs(maxv)
        if abs(abs_minv - abs_maxv) <= SYMM_FRAC * (abs_maxv + abs_minv):
            Ustar = _pow10_ceiling_abs(max(abs_minv, abs_maxv) + EPS)  # noqa: N806
            L, U = -Ustar, Ustar  # noqa: N806
            desired = (U - L) / max(1, target_bins)
            step = _closest_nice_step(desired)
            minstep = 1.0 if is_integer else None
            return BinDecision(extent=(L, U), step=step, minstep=minstep, nice=False, reason="snap_sym_pow10")

    # F) Fallback: quantile-based with nice rounding
    L = _nice_round(q01, mode="floor")  # noqa: N806
    U = _nice_round(q99, mode="ceil")  # noqa: N806
    if U - L < EPS:
        # Handle edge case where range is too small
        L, U = q01 - 0.5, q99 + 0.5  # noqa: N806

    desired = (U - L) / max(1, target_bins)
    step = _closest_nice_step(desired)
    minstep = 1.0 if is_integer else None
    return BinDecision(extent=(L, U), step=step, minstep=minstep, nice=False, reason="quantile_nice_round")
