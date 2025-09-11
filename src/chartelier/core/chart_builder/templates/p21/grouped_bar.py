"""Grouped bar chart template for P21 pattern."""

from typing import Any

import altair as alt
import polars as pl

from chartelier.core.chart_builder.base import BaseTemplate, TemplateSpec
from chartelier.core.enums import AuxiliaryElement
from chartelier.core.models import MappingConfig


class GroupedBarTemplate(BaseTemplate):
    """Grouped bar chart template for showing difference changes over time."""

    def _get_spec(self) -> TemplateSpec:
        """Get template specification.

        Returns:
            Template specification for grouped bar chart
        """
        return TemplateSpec(
            template_id="P21_grouped_bar",
            name="Grouped Bar Chart",
            pattern_ids=["P21"],  # Difference + Transition - Difference changes over time
            required_encodings=["x", "y", "color"],  # x for time/categories, y for values, color for grouping
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
        """Build grouped bar chart from data and mapping.

        Args:
            data: Input data frame
            mapping: Column to encoding mappings
            width: Chart width in pixels
            height: Chart height in pixels

        Returns:
            Altair grouped bar chart
        """
        # Convert Polars DataFrame to Altair-compatible format
        chart_data = self.prepare_data_for_altair(data)

        # Create base chart
        chart = alt.Chart(chart_data).mark_bar()

        # Build encodings
        encodings: dict[str, Any] = {}

        # Required encodings
        if mapping.x:
            # Detect if x is temporal or categorical
            x_dtype = str(data[mapping.x].dtype) if mapping.x in data.columns else ""
            x_name_lower = mapping.x.lower()

            is_date_by_dtype = "date" in x_dtype.lower() or "time" in x_dtype.lower()
            is_date_by_name = "date" in x_name_lower or "time" in x_name_lower
            if is_date_by_dtype or is_date_by_name:
                encodings["x"] = alt.X(f"{mapping.x}:T", title=mapping.x)
            elif x_dtype in {"String", "Utf8"}:
                encodings["x"] = alt.X(f"{mapping.x}:N", title=mapping.x)
            else:
                encodings["x"] = alt.X(f"{mapping.x}:Q", title=mapping.x)

        if mapping.y:
            encodings["y"] = alt.Y(
                f"{mapping.y}:Q",
                title=mapping.y,
                scale=alt.Scale(zero=True),  # Bar charts must start at zero
            )

        # Required color encoding for grouping
        if mapping.color:
            encodings["color"] = alt.Color(
                f"{mapping.color}:N",
                title=mapping.color,
                # Don't set scale here - let theme handle the color scheme
            )

        # Use x-offset for grouped bars instead of column faceting
        # This allows auxiliary elements to be layered properly
        if mapping.x and mapping.color:
            encodings["xOffset"] = alt.XOffset(f"{mapping.color}:N")

        # Apply encodings
        chart = chart.encode(**encodings)

        # Set size and title
        chart = chart.properties(
            width=width // 4,  # Narrower bars for grouping
            height=height,
            title="Grouped Bar Chart",  # Default title
        )

        return chart  # type: ignore[no-any-return]  # noqa: RET504 — Altair type inference
