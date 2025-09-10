"""Histogram template for P03 pattern."""

import math
from typing import Any

import altair as alt
import polars as pl

from chartelier.core.chart_builder.base import BaseTemplate, TemplateSpec
from chartelier.core.enums import AuxiliaryElement, PatternID
from chartelier.core.models import MappingConfig


class HistogramTemplate(BaseTemplate):
    """Histogram template for showing data distribution."""

    def _get_spec(self) -> TemplateSpec:
        """Get template specification.

        Returns:
            Template specification for histogram
        """
        return TemplateSpec(
            template_id="P03_histogram",
            name="Histogram",
            pattern_ids=["P03"],  # Overview only - Distribution/composition
            required_encodings=["x"],
            optional_encodings=["color", "opacity"],
            allowed_auxiliary=[
                AuxiliaryElement.MEAN_LINE,
                AuxiliaryElement.MEDIAN_LINE,
                AuxiliaryElement.THRESHOLD,
                AuxiliaryElement.ANNOTATION,
            ],
        )

    def build(
        self,
        data: pl.DataFrame,
        mapping: MappingConfig,
        width: int = 800,
        height: int = 600,
    ) -> alt.Chart:
        """Build histogram from data and mapping.

        Args:
            data: Input data frame
            mapping: Column to encoding mappings
            width: Chart width in pixels
            height: Chart height in pixels

        Returns:
            Altair histogram chart
        """
        # Convert Polars DataFrame to Altair-compatible format
        chart_data = self.prepare_data_for_altair(data)

        # Calculate optimal bin count using Sturges' rule
        n_rows = len(data)
        bin_count = self._calculate_bin_count(n_rows)

        # Get P03 pattern colors from color strategy
        pattern_colors = self.color_strategy.get_pattern_colors(PatternID.P03)

        # Create base chart with binning and primary color
        chart = alt.Chart(chart_data).mark_bar(
            color=pattern_colors.get("primary", self.color_strategy.data.BASE),
            opacity=pattern_colors.get("fill_opacity", self.color_strategy.style.BAR_FILL_OPACITY),
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
                # For categorical data, use as-is (essentially a bar chart)
                encodings["x"] = alt.X(f"{mapping.x}:N", title=mapping.x)

        # Y-axis is always count for histogram
        encodings["y"] = alt.Y(
            "count()",
            title="Frequency",
            scale=alt.Scale(zero=True),  # Histograms must start at zero
        )

        # Optional encodings
        if mapping.color:
            encodings["color"] = alt.Color(f"{mapping.color}:N", title=mapping.color)

        # Apply encodings
        chart = chart.encode(**encodings)

        # Set size and title
        chart = chart.properties(
            width=width,
            height=height,
            title="Histogram",  # Default title
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

    def _apply_single_auxiliary(
        self,
        chart: alt.Chart,
        element: AuxiliaryElement,
        data: pl.DataFrame,
        mapping: MappingConfig,
        element_config: dict[str, Any] | None = None,
    ) -> alt.Chart | alt.LayerChart:
        """Apply a single auxiliary element specific to histograms.

        Args:
            chart: Chart to modify
            element: Auxiliary element to apply
            data: Input data frame
            mapping: Column mappings

        Returns:
            Modified chart
        """
        # For histograms, mean and median lines should be vertical
        if element == AuxiliaryElement.MEAN_LINE and mapping.x:
            mean_val = data[mapping.x].mean()
            if mean_val is not None:
                rule = (
                    alt.Chart(pl.DataFrame({"mean": [mean_val]}))
                    .mark_rule(
                        color="red",
                        strokeDash=[5, 5],
                        strokeWidth=2,
                    )
                    .encode(
                        x="mean:Q",
                        tooltip=alt.Tooltip("mean:Q", format=".2f", title="Mean"),
                    )
                )
                return alt.layer(chart, rule)

        elif element == AuxiliaryElement.MEDIAN_LINE and mapping.x:
            median_val = data[mapping.x].median()
            if median_val is not None:
                rule = (
                    alt.Chart(pl.DataFrame({"median": [median_val]}))
                    .mark_rule(
                        color="blue",
                        strokeDash=[5, 5],
                        strokeWidth=2,
                    )
                    .encode(
                        x="median:Q",
                        tooltip=alt.Tooltip("median:Q", format=".2f", title="Median"),
                    )
                )
                return alt.layer(chart, rule)

        elif element == AuxiliaryElement.THRESHOLD and mapping.x:
            # Show threshold bands as vertical regions
            # Placeholder values - would come from auxiliary config
            lower_threshold = 0
            upper_threshold = 100
            band = (
                alt.Chart(
                    pl.DataFrame(
                        {
                            "lower": [lower_threshold],
                            "upper": [upper_threshold],
                        }
                    )
                )
                .mark_rect(
                    opacity=0.15,
                    color="green",
                )
                .encode(
                    x=alt.X("lower:Q"),
                    x2=alt.X2("upper:Q"),
                )
            )
            return alt.layer(band, chart)  # Band behind histogram

        # Default to base implementation for other elements
        return super()._apply_single_auxiliary(chart, element, data, mapping, element_config)
