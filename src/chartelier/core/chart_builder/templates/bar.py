"""Bar chart template for P02 pattern."""

from typing import Any

import altair as alt
import polars as pl

from chartelier.core.chart_builder.base import BaseTemplate, TemplateSpec
from chartelier.core.enums import AuxiliaryElement
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
                AuxiliaryElement.MEAN_LINE,
                AuxiliaryElement.MEDIAN_LINE,
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

        # Create base chart
        chart = alt.Chart(chart_data).mark_bar()

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

    def _apply_single_auxiliary(
        self,
        chart: alt.Chart,
        element: AuxiliaryElement,
        data: pl.DataFrame,
        mapping: MappingConfig,
    ) -> alt.Chart | alt.LayerChart:
        """Apply a single auxiliary element specific to bar charts.

        Args:
            chart: Chart to modify
            element: Auxiliary element to apply
            data: Input data frame
            mapping: Column mappings

        Returns:
            Modified chart
        """
        # Use base implementation for common elements
        if element in [AuxiliaryElement.MEAN_LINE, AuxiliaryElement.MEDIAN_LINE]:
            return super()._apply_single_auxiliary(chart, element, data, mapping)

        # Bar chart specific implementations
        if element == AuxiliaryElement.TARGET_LINE and mapping.y:
            # For bar charts, target line should be horizontal
            # This would be configured with actual target value from metadata
            target_value = 0  # Placeholder - would come from auxiliary config
            rule = (
                alt.Chart(pl.DataFrame({"target": [target_value]}))
                .mark_rule(
                    color="green",
                    strokeDash=[10, 5],
                    strokeWidth=2,
                )
                .encode(y="target:Q")
            )
            return alt.layer(chart, rule)

        if element == AuxiliaryElement.THRESHOLD and mapping.y:
            # Threshold band for acceptable range
            # Placeholder values - would come from auxiliary config
            lower_threshold = -10
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
            return alt.layer(band, chart)  # Band behind bars

        return chart
