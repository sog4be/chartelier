"""Bar chart template for P02 pattern."""

from typing import Any

import altair as alt
import polars as pl

from chartelier.core.chart_builder.base import BaseTemplate, TemplateSpec
from chartelier.core.enums import AuxiliaryElement, PatternID
from chartelier.core.models import MappingConfig


class BarTemplate(BaseTemplate):
    """Bar chart template for showing differences between categories."""

    def _get_spec(self) -> TemplateSpec:
        """Get template specification.

        Returns:
            Template specification for bar chart
        """
        return TemplateSpec(
            template_id="P02_bar",
            name="Bar Chart",
            pattern_ids=["P02"],  # Difference only - Category comparison
            required_encodings=["x", "y"],
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
        """Build bar chart from data and mapping.

        Args:
            data: Input data frame
            mapping: Column to encoding mappings
            width: Chart width in pixels
            height: Chart height in pixels

        Returns:
            Altair bar chart
        """
        # Convert Polars DataFrame to Altair-compatible format
        chart_data = self.prepare_data_for_altair(data)

        # Get P02 pattern colors from color strategy
        pattern_colors = self.color_strategy.get_pattern_colors(PatternID.P02)

        # Create base chart with primary color for single series
        chart = alt.Chart(chart_data).mark_bar(
            color=pattern_colors.get("primary", self.color_strategy.data.BASE),
            opacity=pattern_colors.get("fill_opacity", self.color_strategy.style.BAR_FILL_OPACITY),
        )

        # Build encodings
        encodings: dict[str, Any] = {}

        # Required encodings - detect if we need horizontal or vertical bars
        if mapping.x and mapping.y:
            # Check data types to determine orientation
            x_dtype = str(data[mapping.x].dtype) if mapping.x in data.columns else ""
            y_dtype = str(data[mapping.y].dtype) if mapping.y in data.columns else ""

            # If x is categorical and y is numeric, use vertical bars
            # If x is numeric and y is categorical, use horizontal bars
            is_x_numeric = any(t in x_dtype.lower() for t in ["int", "float", "decimal"])
            is_y_numeric = any(t in y_dtype.lower() for t in ["int", "float", "decimal"])

            if is_x_numeric and not is_y_numeric:
                # Horizontal bars
                encodings["x"] = alt.X(
                    f"{mapping.x}:Q",
                    title=mapping.x,
                    scale=alt.Scale(zero=True),  # Bar charts must start at zero
                )
                encodings["y"] = alt.Y(f"{mapping.y}:N", title=mapping.y, sort="-x")
            else:
                # Vertical bars (default)
                encodings["x"] = alt.X(f"{mapping.x}:N", title=mapping.x)
                encodings["y"] = alt.Y(
                    f"{mapping.y}:Q",
                    title=mapping.y,
                    scale=alt.Scale(zero=True),  # Bar charts must start at zero
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
            title="Bar Chart",  # Default title, can be customized later
        )

        return chart  # type: ignore[no-any-return]  # noqa: RET504 — Altair type inference
