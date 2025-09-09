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

    def _apply_single_auxiliary(
        self,
        chart: alt.Chart,
        element: AuxiliaryElement,
        data: pl.DataFrame,
        mapping: MappingConfig,
    ) -> alt.Chart | alt.LayerChart:
        """Apply a single auxiliary element specific to facet histograms.

        Args:
            chart: Chart to modify
            element: Auxiliary element to apply
            data: Input data frame
            mapping: Column mappings

        Returns:
            Modified chart
        """
        # For facet histograms, mean and median lines should be computed per facet
        if element == AuxiliaryElement.MEAN_LINE and mapping.x and mapping.facet:
            # Calculate mean for each facet group
            mean_data = data.group_by(mapping.facet).agg(pl.col(mapping.x).mean().alias("mean_value"))

            # Create vertical mean lines for each facet
            rule = (
                alt.Chart(self.prepare_data_for_altair(mean_data))
                .mark_rule(
                    color="red",
                    strokeDash=[5, 5],
                    strokeWidth=2,
                )
                .encode(
                    x="mean_value:Q",
                    facet=alt.Facet(f"{mapping.facet}:N", columns=3),
                    tooltip=[
                        alt.Tooltip(f"{mapping.facet}:N", title="Group"),
                        alt.Tooltip("mean_value:Q", format=".2f", title="Mean"),
                    ],
                )
            )
            return alt.layer(chart, rule)

        if element == AuxiliaryElement.MEDIAN_LINE and mapping.x and mapping.facet:
            # Calculate median for each facet group
            median_data = data.group_by(mapping.facet).agg(pl.col(mapping.x).median().alias("median_value"))

            # Create vertical median lines for each facet
            rule = (
                alt.Chart(self.prepare_data_for_altair(median_data))
                .mark_rule(
                    color="blue",
                    strokeDash=[5, 5],
                    strokeWidth=2,
                )
                .encode(
                    x="median_value:Q",
                    facet=alt.Facet(f"{mapping.facet}:N", columns=3),
                    tooltip=[
                        alt.Tooltip(f"{mapping.facet}:N", title="Group"),
                        alt.Tooltip("median_value:Q", format=".2f", title="Median"),
                    ],
                )
            )
            return alt.layer(chart, rule)

        if element == AuxiliaryElement.THRESHOLD and mapping.x:
            # Show threshold bands as vertical regions across all facets
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
        return super()._apply_single_auxiliary(chart, element, data, mapping)
