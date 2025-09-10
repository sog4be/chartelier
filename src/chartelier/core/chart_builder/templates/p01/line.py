"""Line chart template for P01 pattern."""

from typing import Any

import altair as alt
import polars as pl

from chartelier.core.chart_builder.base import BaseTemplate, TemplateSpec
from chartelier.core.enums import AuxiliaryElement, PatternID
from chartelier.core.models import MappingConfig


class LineTemplate(BaseTemplate):
    """Line chart template for showing transitions over time."""

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

        # Get P01 pattern colors from color strategy
        pattern_colors = self.color_strategy.get_pattern_colors(PatternID.P01)

        # Create base chart with primary color for single series
        chart = alt.Chart(chart_data).mark_line(
            point=False,  # No markers by default
            strokeWidth=pattern_colors.get("stroke_width", self.color_strategy.style.LINE_WIDTH_DEFAULT),
            color=pattern_colors.get("primary", self.color_strategy.data.BASE),  # Use primary color for single series
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
