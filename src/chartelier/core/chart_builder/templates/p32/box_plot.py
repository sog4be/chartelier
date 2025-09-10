"""Box plot template for P32 pattern."""

from typing import Any

import altair as alt
import polars as pl

from chartelier.core.chart_builder.base import BaseTemplate, TemplateSpec
from chartelier.core.enums import AuxiliaryElement
from chartelier.core.models import MappingConfig


class BoxPlotTemplate(BaseTemplate):
    """Box plot template for showing distribution comparison between categories."""

    def _get_spec(self) -> TemplateSpec:
        """Get template specification.

        Returns:
            Template specification for box plot
        """
        return TemplateSpec(
            template_id="P32_box_plot",
            name="Box Plot",
            pattern_ids=["P32"],  # Overview + Difference - Distribution comparison between categories
            required_encodings=["x", "y"],  # x for categories, y for values
            optional_encodings=["color"],
            allowed_auxiliary=[
                AuxiliaryElement.MEAN_LINE,
                AuxiliaryElement.TARGET_LINE,
                AuxiliaryElement.THRESHOLD,
                AuxiliaryElement.ANNOTATION,
                AuxiliaryElement.HIGHLIGHT,
            ],
        )

    def build(
        self,
        data: pl.DataFrame,
        mapping: MappingConfig,
        width: int = 800,
        height: int = 600,
    ) -> alt.Chart:
        """Build box plot from data and mapping.

        Args:
            data: Input data frame
            mapping: Column to encoding mappings
            width: Chart width in pixels
            height: Chart height in pixels

        Returns:
            Altair box plot chart
        """
        # Convert Polars DataFrame to Altair-compatible format
        chart_data = self.prepare_data_for_altair(data)

        # Create base chart with box plot
        chart = alt.Chart(chart_data).mark_boxplot(
            size=40,  # Box width
            outliers=True,  # Show outlier points
        )

        # Build encodings
        encodings: dict[str, Any] = {}

        # Required encodings
        if mapping.x:
            # X should be categorical for box plots
            encodings["x"] = alt.X(f"{mapping.x}:N", title=mapping.x)

        if mapping.y:
            # Y should be quantitative for box plots
            encodings["y"] = alt.Y(
                f"{mapping.y}:Q",
                title=mapping.y,
                scale=alt.Scale(zero=False),  # Box plots don't need zero origin
            )

        # Optional encodings
        if mapping.color:
            encodings["color"] = alt.Color(
                f"{mapping.color}:N",
                title=mapping.color,
                # Don't set scale here - let theme handle the color scheme
            )

        # Apply encodings
        chart = chart.encode(**encodings)

        # Set size and title
        chart = chart.properties(
            width=width,
            height=height,
            title="Box Plot",  # Default title
        )

        return chart  # type: ignore[no-any-return]  # noqa: RET504 — Altair type inference

    def _apply_single_auxiliary(
        self,
        chart: alt.Chart,
        element: AuxiliaryElement,
        data: pl.DataFrame,
        mapping: MappingConfig,
        element_config: dict[str, Any] | None = None,
    ) -> alt.Chart | alt.LayerChart:
        """Apply a single auxiliary element specific to box plots.

        Args:
            chart: Chart to modify
            element: Auxiliary element to apply
            data: Input data frame
            mapping: Column mappings

        Returns:
            Modified chart
        """
        # For box plots, auxiliary elements should complement the statistical summary
        if element == AuxiliaryElement.MEAN_LINE and mapping.y:
            # Add overall mean line across all categories
            overall_mean = data[mapping.y].mean()
            if overall_mean is not None:
                rule = (
                    alt.Chart(pl.DataFrame({"mean": [overall_mean]}))
                    .mark_rule(
                        color="red",
                        strokeDash=[5, 5],
                        strokeWidth=2,
                    )
                    .encode(y="mean:Q", tooltip=alt.Tooltip("mean:Q", format=".2f", title="Overall Mean"))
                )
                return alt.layer(chart, rule)

        elif element == AuxiliaryElement.TARGET_LINE and mapping.y:
            # Add target value line
            target_value = 0  # Placeholder - would come from auxiliary config
            rule = (
                alt.Chart(pl.DataFrame({"target": [target_value]}))
                .mark_rule(
                    color="green",
                    strokeDash=[10, 5],
                    strokeWidth=2,
                )
                .encode(y="target:Q", tooltip=alt.Tooltip("target:Q", title="Target"))
            )
            return alt.layer(chart, rule)

        elif element == AuxiliaryElement.THRESHOLD and mapping.y:
            # Add threshold band for acceptable range
            lower_threshold = -10  # Placeholder values
            upper_threshold = 10
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
                    opacity=0.2,
                    color="gray",
                )
                .encode(
                    y=alt.Y("lower:Q"),
                    y2=alt.Y2("upper:Q"),
                )
            )
            return alt.layer(band, chart)  # Band behind box plot

        elif element == AuxiliaryElement.HIGHLIGHT and mapping.x and mapping.color:
            # Highlight specific categories (would be configured via auxiliary config)
            # For now, just enhance the color encoding
            return chart

        # Use base implementation for other elements
        return super()._apply_single_auxiliary(chart, element, data, mapping, element_config)
