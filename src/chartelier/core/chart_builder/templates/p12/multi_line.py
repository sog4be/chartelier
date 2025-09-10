"""Multi-line chart template for P12 pattern."""

from typing import Any

import altair as alt
import polars as pl

from chartelier.core.chart_builder.base import BaseTemplate, TemplateSpec
from chartelier.core.enums import AuxiliaryElement
from chartelier.core.models import MappingConfig


class MultiLineTemplate(BaseTemplate):
    """Multi-line chart template for showing multiple time series comparison."""

    def _get_spec(self) -> TemplateSpec:
        """Get template specification.

        Returns:
            Template specification for multi-line chart
        """
        return TemplateSpec(
            template_id="P12_multi_line",
            name="Multi-Line Chart",
            pattern_ids=["P12"],  # Transition + Difference - Multiple time series comparison
            required_encodings=["x", "y", "color"],  # Color is required for multiple series
            optional_encodings=["strokeDash", "opacity"],
            allowed_auxiliary=[
                AuxiliaryElement.MEAN_LINE,
                AuxiliaryElement.MEDIAN_LINE,
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
        """Build multi-line chart from data and mapping.

        Args:
            data: Input data frame
            mapping: Column to encoding mappings
            width: Chart width in pixels
            height: Chart height in pixels

        Returns:
            Altair multi-line chart
        """
        # Convert Polars DataFrame to Altair-compatible format
        chart_data = self.prepare_data_for_altair(data)

        # Create base chart
        chart = alt.Chart(chart_data).mark_line(
            point=True,  # Show points on each line
            strokeWidth=2,
        )

        # Build encodings
        encodings: dict[str, Any] = {}

        # Required encodings
        if mapping.x:
            # Detect if x is temporal or categorical
            if mapping.x in data.columns:
                x_dtype = str(data[mapping.x].dtype)
                x_name_lower = mapping.x.lower()

                # If it's actually a date/datetime type
                is_date_by_dtype = "date" in x_dtype.lower() or "time" in x_dtype.lower()
                is_date_by_name = "date" in x_name_lower or "time" in x_name_lower
                if is_date_by_dtype or is_date_by_name:
                    encodings["x"] = alt.X(f"{mapping.x}:T", title=mapping.x)
                # If it's a string type (categorical)
                elif x_dtype in {"String", "Utf8"}:
                    encodings["x"] = alt.X(f"{mapping.x}:N", title=mapping.x)
                # Default to quantitative for numeric types
                else:
                    encodings["x"] = alt.X(f"{mapping.x}:Q", title=mapping.x)
            else:
                encodings["x"] = alt.X(f"{mapping.x}:Q", title=mapping.x)

        if mapping.y:
            encodings["y"] = alt.Y(f"{mapping.y}:Q", title=mapping.y)

        # Required color encoding for multiple series
        if mapping.color:
            encodings["color"] = alt.Color(
                f"{mapping.color}:N",
                title=mapping.color,
                # Don't set scale here - let theme handle the color scheme
            )

        # Optional encodings
        if hasattr(mapping, "strokeDash") and mapping.strokeDash:
            encodings["strokeDash"] = alt.StrokeDash(f"{mapping.strokeDash}:N", title=mapping.strokeDash)

        # Apply encodings
        chart = chart.encode(**encodings)

        # Set size
        chart = chart.properties(
            width=width,
            height=height,
            title="Multi-Line Chart",  # Default title
        )

        return chart  # type: ignore[no-any-return]  # noqa: RET504 — Altair type inference

    def _apply_single_auxiliary(
        self,
        chart: alt.Chart,
        element: AuxiliaryElement,
        data: pl.DataFrame,
        mapping: MappingConfig,
    ) -> alt.Chart | alt.LayerChart:
        """Apply a single auxiliary element specific to multi-line charts.

        Args:
            chart: Chart to modify
            element: Auxiliary element to apply
            data: Input data frame
            mapping: Column mappings

        Returns:
            Modified chart
        """
        # For multi-line charts, certain elements need special handling
        if element == AuxiliaryElement.MEAN_LINE and mapping.y and mapping.color:
            # Calculate mean for each series
            mean_data = data.group_by(mapping.color).agg(pl.col(mapping.y).mean().alias("mean_value"))

            # Create horizontal mean lines for each series
            rule = (
                alt.Chart(self.prepare_data_for_altair(mean_data))
                .mark_rule(
                    strokeDash=[5, 5],
                    strokeWidth=2,
                )
                .encode(
                    y=alt.Y("mean_value:Q"),
                    color=alt.Color(f"{mapping.color}:N"),
                    tooltip=[
                        alt.Tooltip(f"{mapping.color}:N", title="Series"),
                        alt.Tooltip("mean_value:Q", format=".2f", title="Mean"),
                    ],
                )
            )
            return alt.layer(chart, rule)

        if element == AuxiliaryElement.HIGHLIGHT and mapping.x and mapping.y and mapping.color:
            # For multi-line charts, highlight max/min points across all series
            # but maintain the line chart structure
            y_col = data[mapping.y]
            max_idx = y_col.arg_max()
            min_idx = y_col.arg_min()

            if max_idx is not None and min_idx is not None:
                # Get the actual data points for highlighting
                max_point = data.row(max_idx, named=True)
                min_point = data.row(min_idx, named=True)

                # Create highlight data
                highlight_data = pl.DataFrame(
                    [
                        {
                            mapping.x: max_point[mapping.x],
                            mapping.y: max_point[mapping.y],
                            mapping.color: max_point[mapping.color],
                            "point_type": "Max",
                        },
                        {
                            mapping.x: min_point[mapping.x],
                            mapping.y: min_point[mapping.y],
                            mapping.color: min_point[mapping.color],
                            "point_type": "Min",
                        },
                    ]
                )

                # Create highlight layer with larger circles
                # Use the same color encoding as the main chart to maintain consistency
                highlights = (
                    alt.Chart(self.prepare_data_for_altair(highlight_data))
                    .mark_circle(
                        size=150,  # Larger than the line points
                        stroke="white",  # White border for visibility
                        strokeWidth=3,
                        opacity=0.8,
                    )
                    .encode(
                        x=f"{mapping.x}:T",  # Multi-line usually uses temporal x-axis
                        y=f"{mapping.y}:Q",
                        color=alt.Color(
                            f"{mapping.color}:N",
                            # Don't set scale here - let theme handle the color scheme
                            title=f"{mapping.color}, Highlighted Points",
                        ),
                    )
                )
                return alt.layer(chart, highlights)

        # Use base implementation for other elements
        return super()._apply_single_auxiliary(chart, element, data, mapping)
