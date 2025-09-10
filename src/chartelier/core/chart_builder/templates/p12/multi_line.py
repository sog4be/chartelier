"""Multi-line chart template for P12 pattern."""

from typing import Any

import altair as alt
import polars as pl

from chartelier.core.chart_builder.base import BaseTemplate, TemplateSpec
from chartelier.core.enums import AuxiliaryElement
from chartelier.core.models import MappingConfig


class MultiLineTemplate(BaseTemplate):
    """Multi-line chart template for showing multiple time series comparison."""

    def _calculate_time_axis_config(self, data: pl.DataFrame, x_col_name: str) -> dict[str, Any]:
        """Calculate appropriate time axis configuration based on data characteristics.

        Args:
            data: Input DataFrame
            x_col_name: Name of the x-axis column

        Returns:
            Axis configuration dictionary
        """
        # Use x_col_name to avoid unused argument warning
        _ = x_col_name
        num_points = len(data)
        axis_config: dict[str, Any] = {}

        if num_points <= 10:
            # For small datasets, show all labels
            axis_config = {"tickCount": num_points}
        # For larger datasets, try to determine time unit based on date range
        # Default to a reasonable number of ticks based on data size
        elif num_points <= 30:
            axis_config = {"tickCount": min(num_points // 2, 15)}
        elif num_points <= 100:
            axis_config = {"tickCount": 10}
        else:
            axis_config = {"tickCount": 15}

        return axis_config

    def _calculate_y_scale(self, data: pl.DataFrame, y_col_name: str) -> dict[str, Any] | None:
        """Calculate Y-axis scale for better visibility of small changes.

        Args:
            data: Input DataFrame
            y_col_name: Name of the y-axis column

        Returns:
            Scale configuration or None
        """
        try:
            y_col = data[y_col_name]
            y_min = y_col.min()
            y_max = y_col.max()

            if y_min is None or y_max is None:
                return None

            # Convert to float for calculations
            y_min_float = float(y_min)  # type: ignore[arg-type]
            y_max_float = float(y_max)  # type: ignore[arg-type]
            y_range = y_max_float - y_min_float

            # If the data range is small relative to the max value,
            # adjust the Y-axis to focus on the actual data range
            if y_max_float > 0 and y_range / y_max_float < 0.3:  # Less than 30% of the full range
                # Add 20% padding above and below the data range
                padding = y_range * 0.2
                y_domain = [y_min_float - padding, y_max_float + padding]
                return {"domain": y_domain}
        except (TypeError, ValueError):
            # If conversion fails, return None to use default scale
            return None

        return None

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
                AuxiliaryElement.TARGET_LINE,
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
            point=False,  # No markers by default
            strokeWidth=2,
        )

        # Build encodings
        encodings: dict[str, Any] = {}

        # Required encodings
        if mapping.x and mapping.x in data.columns:
            x_dtype = str(data[mapping.x].dtype)
            x_name_lower = mapping.x.lower()

            # Check if temporal
            is_temporal = (
                "date" in x_dtype.lower()
                or "time" in x_dtype.lower()
                or "date" in x_name_lower
                or "time" in x_name_lower
            )

            if is_temporal:
                axis_config = self._calculate_time_axis_config(data, mapping.x)
                encodings["x"] = alt.X(
                    f"{mapping.x}:T", title=mapping.x, axis=alt.Axis(**axis_config) if axis_config else None
                )
            elif x_dtype in {"String", "Utf8"}:
                encodings["x"] = alt.X(f"{mapping.x}:N", title=mapping.x)
            else:
                encodings["x"] = alt.X(f"{mapping.x}:Q", title=mapping.x)
        elif mapping.x:
            encodings["x"] = alt.X(f"{mapping.x}:Q", title=mapping.x)

        if mapping.y:
            # Calculate Y-axis scale for better visibility
            scale_config = self._calculate_y_scale(data, mapping.y)
            if scale_config:
                encodings["y"] = alt.Y(f"{mapping.y}:Q", title=mapping.y, scale=alt.Scale(**scale_config))
            else:
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
        element_config: dict[str, Any] | None = None,
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
        return super()._apply_single_auxiliary(chart, element, data, mapping, element_config)
