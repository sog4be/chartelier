"""Line chart template for P01 pattern."""

from typing import Any

import altair as alt
import polars as pl

from chartelier.core.chart_builder.base import BaseTemplate, TemplateSpec
from chartelier.core.enums import AuxiliaryElement
from chartelier.core.models import MappingConfig


class LineTemplate(BaseTemplate):
    """Line chart template for showing transitions over time."""

    def _get_spec(self) -> TemplateSpec:
        """Get template specification.

        Returns:
            Template specification for line chart
        """
        return TemplateSpec(
            template_id="P01_line",
            name="Line Chart",
            pattern_ids=["P01"],  # Single series transition
            required_encodings=["x", "y"],
            optional_encodings=["color", "strokeDash"],
            allowed_auxiliary=[
                AuxiliaryElement.MEAN_LINE,
                AuxiliaryElement.MEDIAN_LINE,
                AuxiliaryElement.REGRESSION,
                AuxiliaryElement.MOVING_AVG,
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
        """Build line chart from data and mapping.

        Args:
            data: Input data frame
            mapping: Column to encoding mappings
            width: Chart width in pixels
            height: Chart height in pixels

        Returns:
            Altair line chart
        """
        # Convert Polars DataFrame to Altair-compatible format
        chart_data = self.prepare_data_for_altair(data)

        # Create base chart
        chart = alt.Chart(chart_data).mark_line(
            point=True,  # Show points on the line
            strokeWidth=2,
        )

        # Build encodings
        encodings: dict[str, Any] = {}

        # Required encodings
        if mapping.x:
            # Detect if x is temporal
            if mapping.x in data.columns:
                x_dtype = str(data[mapping.x].dtype)
                if "date" in x_dtype.lower() or "time" in x_dtype.lower():
                    encodings["x"] = alt.X(f"{mapping.x}:T", title=mapping.x)
                else:
                    encodings["x"] = alt.X(f"{mapping.x}:Q", title=mapping.x)
            else:
                encodings["x"] = alt.X(f"{mapping.x}:Q", title=mapping.x)

        if mapping.y:
            encodings["y"] = alt.Y(f"{mapping.y}:Q", title=mapping.y)

        # Optional encodings
        if mapping.color:
            encodings["color"] = alt.Color(f"{mapping.color}:N", title=mapping.color)

        # Apply encodings
        chart = chart.encode(**encodings)

        # Set size
        chart = chart.properties(
            width=width,
            height=height,
            title="Line Chart",  # Default title, can be customized later
        )

        # Don't apply config here - it will be applied at the top level
        # This allows the chart to be used in layers without config conflicts

        return chart  # type: ignore[no-any-return]  # noqa: RET504 — Altair type inference
