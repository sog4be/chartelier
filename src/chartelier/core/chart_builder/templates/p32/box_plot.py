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
                AuxiliaryElement.TARGET_LINE,
            ],
        )

    def build(
        self,
        data: pl.DataFrame,
        mapping: MappingConfig,
        width: int = 1200,
        height: int = 800,
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
