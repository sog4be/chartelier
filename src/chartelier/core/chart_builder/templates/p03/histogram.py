"""Histogram template for P03 pattern."""

import math
from typing import Any

import altair as alt
import polars as pl

from chartelier.core.chart_builder.axis import decide_histogram_binning
from chartelier.core.chart_builder.base import BaseTemplate, TemplateSpec
from chartelier.core.enums import PatternID
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
            allowed_auxiliary=[],  # Target line not applicable for histograms (y-axis is frequency)
        )

    def build(
        self,
        data: pl.DataFrame,
        mapping: MappingConfig,
        width: int = 1200,
        height: int = 800,
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
                # Decide extent/step for bounded/natural ranges
                decision = decide_histogram_binning(data, mapping.x, bin_count)

                # Build bin configuration
                bin_kwargs: dict[str, Any] = {"nice": decision.nice}
                if decision.extent:
                    bin_kwargs["extent"] = list(decision.extent)
                if decision.step:
                    bin_kwargs["step"] = decision.step
                if decision.minstep:
                    bin_kwargs["minstep"] = decision.minstep
                else:
                    # If no specific step is decided, use maxbins
                    bin_kwargs["maxbins"] = bin_count

                encodings["x"] = alt.X(
                    f"{mapping.x}:Q",
                    bin=alt.Bin(**bin_kwargs),
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
