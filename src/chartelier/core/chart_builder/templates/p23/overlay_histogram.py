"""Overlay histogram template for P23 pattern."""

import math
from typing import Any

import altair as alt
import polars as pl

from chartelier.core.chart_builder.base import BaseTemplate, TemplateSpec
from chartelier.core.enums import AuxiliaryElement
from chartelier.core.models import MappingConfig


class OverlayHistogramTemplate(BaseTemplate):
    """Overlay histogram template for showing category-wise distribution comparison."""

    def _get_spec(self) -> TemplateSpec:
        """Get template specification.

        Returns:
            Template specification for overlay histogram
        """
        return TemplateSpec(
            template_id="P23_overlay_histogram",
            name="Overlay Histogram",
            pattern_ids=["P23"],  # Difference + Overview - Category-wise distribution comparison
            required_encodings=["x", "color"],  # x for values, color for category grouping
            optional_encodings=["opacity"],
            allowed_auxiliary=[
                AuxiliaryElement.TARGET_LINE,
            ],
        )

    def build(
        self,
        data: pl.DataFrame,
        mapping: MappingConfig,
        width: int = 800,
        height: int = 600,
    ) -> alt.Chart:
        """Build overlay histogram from data and mapping.

        Args:
            data: Input data frame
            mapping: Column to encoding mappings
            width: Chart width in pixels
            height: Chart height in pixels

        Returns:
            Altair overlay histogram chart
        """
        # Convert Polars DataFrame to Altair-compatible format
        chart_data = self.prepare_data_for_altair(data)

        # Calculate optimal bin count using Sturges' rule
        n_rows = len(data)
        bin_count = self._calculate_bin_count(n_rows)

        # Create base chart with binning
        chart = alt.Chart(chart_data).mark_bar(
            opacity=0.7,  # Semi-transparent bars for overlay effect
            stroke="white",  # White stroke to separate overlapping bars
            strokeWidth=0.5,
        )

        # Build encodings
        encodings: dict[str, Any] = {}

        # Required encoding with binning
        if mapping.x:
            # Detect if x is numeric
            x_dtype = str(data[mapping.x].dtype) if mapping.x in data.columns else ""
            is_numeric = any(t in x_dtype.lower() for t in ["int", "float", "decimal"])

            if is_numeric:
                # Apply binning for numeric data
                encodings["x"] = alt.X(
                    f"{mapping.x}:Q",
                    bin=alt.Bin(maxbins=bin_count),
                    title=mapping.x,
                )
            else:
                # For categorical data, use as-is
                encodings["x"] = alt.X(f"{mapping.x}:N", title=mapping.x)

        # Required color encoding for category comparison
        if mapping.color:
            encodings["color"] = alt.Color(
                f"{mapping.color}:N",
                title=mapping.color,
                # Don't set scale here - let theme handle the color scheme
            )
            # Y-axis with stack=None for overlay effect (not stacked)
            encodings["y"] = alt.Y(
                "count()",
                title="Frequency",
                scale=alt.Scale(zero=True),  # Histograms must start at zero
                stack=None,  # This prevents stacking - creates overlay effect
            )
        else:
            # Y-axis is always count for histogram (default case)
            encodings["y"] = alt.Y(
                "count()",
                title="Frequency",
                scale=alt.Scale(zero=True),  # Histograms must start at zero
            )

        # Apply encodings
        chart = chart.encode(**encodings)

        # Set size and title
        chart = chart.properties(
            width=width,
            height=height,
            title="Overlay Histogram",  # Default title
        )

        return chart  # type: ignore[no-any-return]  # noqa: RET504 — Altair type inference

    def _calculate_bin_count(self, n: int) -> int:
        """Calculate optimal bin count using Sturges' rule.

        Args:
            n: Number of data points

        Returns:
            Optimal number of bins
        """
        if n <= 0:
            return 10  # Default fallback
        # Sturges' rule: k = ⌈log₂(n) + 1⌉
        bin_count = math.ceil(math.log2(n) + 1)
        # Limit bins to reasonable range
        return max(5, min(bin_count, 50))
