"""Facet histogram template for P13 pattern."""

import math
from typing import Any

import altair as alt
import polars as pl

from chartelier.core.chart_builder.base import BaseTemplate, TemplateSpec
from chartelier.core.enums import AuxiliaryElement
from chartelier.core.models import MappingConfig


class FacetHistogramTemplate(BaseTemplate):
    """Facet histogram template for showing distribution changes over time/categories."""

    def _get_spec(self) -> TemplateSpec:
        """Get template specification.

        Returns:
            Template specification for facet histogram
        """
        return TemplateSpec(
            template_id="P13_facet_histogram",
            name="Facet Histogram",
            pattern_ids=["P13"],  # Transition + Overview - Distribution over time
            required_encodings=["x", "facet"],  # x for values, facet for time/category grouping
            optional_encodings=["color", "opacity"],
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
        """Build facet histogram from data and mapping.

        Args:
            data: Input data frame
            mapping: Column to encoding mappings
            width: Chart width in pixels
            height: Chart height in pixels

        Returns:
            Altair facet histogram chart
        """
        # Convert Polars DataFrame to Altair-compatible format
        chart_data = self.prepare_data_for_altair(data)

        # Calculate optimal bin count using Sturges' rule
        n_rows = len(data)
        bin_count = self._calculate_bin_count(n_rows)

        # Create base chart with binning
        chart = alt.Chart(chart_data).mark_bar()

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

        # Y-axis is always count for histogram
        encodings["y"] = alt.Y(
            "count()",
            title="Frequency",
            scale=alt.Scale(zero=True),  # Histograms must start at zero
        )

        # Required facet encoding
        if mapping.facet:
            # Determine if facet should be temporal, ordinal, or nominal
            facet_dtype = str(data[mapping.facet].dtype) if mapping.facet in data.columns else ""
            facet_name_lower = mapping.facet.lower()

            if "date" in facet_dtype.lower() or "time" in facet_dtype.lower():
                encodings["facet"] = alt.Facet(
                    f"{mapping.facet}:T",
                    title=mapping.facet,
                    columns=3,  # Arrange in 3 columns for better layout
                )
            elif "date" in facet_name_lower or "time" in facet_name_lower:
                encodings["facet"] = alt.Facet(f"{mapping.facet}:T", title=mapping.facet, columns=3)
            else:
                encodings["facet"] = alt.Facet(f"{mapping.facet}:N", title=mapping.facet, columns=3)

        # Optional encodings
        if mapping.color:
            encodings["color"] = alt.Color(f"{mapping.color}:N", title=mapping.color)

        # Apply encodings
        chart = chart.encode(**encodings)

        # Set size and title - adjust width for faceting
        chart = chart.properties(
            width=width // 3,  # Smaller individual charts for faceting
            height=height // 2,  # Adjust height for multiple rows
            title="Facet Histogram",  # Default title
        ).resolve_scale(
            y="independent"  # Allow different y-scales for each facet
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
        # Limit bins to reasonable range for faceted view
        return max(5, min(bin_count, 20))  # Fewer bins for readability in small multiples
