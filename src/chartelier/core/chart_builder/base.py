"""Base template abstract class for chart generation."""

from abc import ABC, abstractmethod
from typing import Any

import altair as alt
import polars as pl

from chartelier.core.chart_builder.colors import color_strategy
from chartelier.core.chart_builder.themes import default_theme
from chartelier.core.enums import AuxiliaryElement, PatternID
from chartelier.core.models import MappingConfig


class TemplateSpec:
    """Specification for a chart template."""

    def __init__(  # noqa: PLR0913 — Template specification requires multiple parameters
        self,
        template_id: str,
        name: str,
        pattern_ids: list[str],
        required_encodings: list[str],
        optional_encodings: list[str],
        allowed_auxiliary: list[AuxiliaryElement],
    ) -> None:
        """Initialize template specification.

        Args:
            template_id: Unique template identifier
            name: Human-readable template name
            pattern_ids: List of pattern IDs this template supports
            required_encodings: Required data encodings (e.g., x, y)
            optional_encodings: Optional data encodings (e.g., color, size)
            allowed_auxiliary: List of allowed auxiliary elements
        """
        self.template_id = template_id
        self.name = name
        self.pattern_ids = pattern_ids
        self.required_encodings = required_encodings
        self.optional_encodings = optional_encodings
        self.allowed_auxiliary = allowed_auxiliary

    def validate_mapping(self, mapping: MappingConfig) -> tuple[bool, list[str]]:
        """Validate if mapping satisfies template requirements.

        Args:
            mapping: Column mapping configuration

        Returns:
            Tuple of (is_valid, missing_fields)
        """
        missing = []
        mapping_dict = mapping.model_dump(exclude_none=True)

        for required in self.required_encodings:
            if required not in mapping_dict:
                missing.append(required)

        return len(missing) == 0, missing


class BaseTemplate(ABC):
    """Abstract base class for all chart templates."""

    def __init__(self) -> None:
        """Initialize base template."""
        self.spec = self._get_spec()
        self.theme = default_theme
        self.color_strategy = color_strategy

    @abstractmethod
    def _get_spec(self) -> TemplateSpec:
        """Get template specification.

        Returns:
            Template specification
        """

    @abstractmethod
    def build(
        self,
        data: pl.DataFrame,
        mapping: MappingConfig,
        width: int = 800,
        height: int = 600,
    ) -> alt.Chart:
        """Build Altair chart from data and mapping.

        Args:
            data: Input data frame
            mapping: Column to encoding mappings
            width: Chart width in pixels
            height: Chart height in pixels

        Returns:
            Altair chart object
        """

    def apply_theme(
        self,
        chart: alt.Chart,
        pattern_id: PatternID | None = None,
        series_count: int = 1,
    ) -> alt.Chart:
        """Apply theme settings to a chart.

        Args:
            chart: Altair chart object
            pattern_id: Optional pattern ID for pattern-specific styling
            series_count: Number of series for color scheme selection

        Returns:
            Chart with theme applied
        """
        if pattern_id:
            return self.theme.apply_pattern_specific(chart, pattern_id, series_count)
        return self.theme.apply_to_chart(chart)

    def apply_auxiliary(
        self,
        chart: alt.Chart,
        auxiliary: list[AuxiliaryElement],
        data: pl.DataFrame,
        mapping: MappingConfig,
        auxiliary_config: dict[str, Any] | None = None,
    ) -> alt.Chart | alt.LayerChart:
        """Apply auxiliary elements to chart.

        Args:
            chart: Base chart object
            auxiliary: List of auxiliary elements to apply
            data: Input data frame
            mapping: Column mappings
            auxiliary_config: Configuration for auxiliary elements

        Returns:
            Chart with auxiliary elements applied
        """
        # Filter to only allowed auxiliary elements
        allowed = [aux for aux in auxiliary if aux in self.spec.allowed_auxiliary]
        config = auxiliary_config or {}

        for element in allowed[:3]:  # Max 3 auxiliary elements
            element_config = config.get(element.value, {})
            chart = self._apply_single_auxiliary(chart, element, data, mapping, element_config)  # type: ignore[assignment]

        return chart

    def _apply_single_auxiliary(  # noqa: PLR0911, PLR0912, PLR0915, C901
        self,
        chart: alt.Chart,
        element: AuxiliaryElement,
        data: pl.DataFrame,
        mapping: MappingConfig,
        element_config: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> alt.Chart | alt.LayerChart:
        """Apply a single auxiliary element.

        Args:
            chart: Chart to modify
            element: Auxiliary element to apply
            data: Input data frame
            mapping: Column mappings
            element_config: Configuration for the specific element

        Returns:
            Modified chart
        """
        # Default implementation - subclasses can override
        # Get auxiliary element styling from color strategy
        aux_style = self.color_strategy.get_auxiliary_colors(element)

        if element == AuxiliaryElement.MEAN_LINE and mapping.y:
            mean_val = data[mapping.y].mean()
            if mean_val is not None:
                rule_data = self.prepare_data_for_altair(pl.DataFrame({"mean": [mean_val]}))
                rule = (
                    alt.Chart(rule_data)
                    .mark_rule(
                        color=aux_style.get("color", "red"),
                        strokeDash=aux_style.get("stroke_dash", [5, 5]),
                        strokeWidth=aux_style.get("stroke_width", 2),
                        opacity=aux_style.get("opacity", 0.8),
                    )
                    .encode(y="mean:Q")
                )
                # Use alt.layer for proper composition
                return alt.layer(chart, rule)

        elif element == AuxiliaryElement.MEDIAN_LINE and mapping.y:
            median_val = data[mapping.y].median()
            if median_val is not None:
                rule_data = self.prepare_data_for_altair(pl.DataFrame({"median": [median_val]}))
                rule = (
                    alt.Chart(rule_data)
                    .mark_rule(
                        color=aux_style.get("color", "orange"),
                        strokeDash=aux_style.get("stroke_dash", [5, 5]),
                        strokeWidth=aux_style.get("stroke_width", 2),
                        opacity=aux_style.get("opacity", 0.8),
                    )
                    .encode(y="median:Q")
                )
                return alt.layer(chart, rule)

        elif element == AuxiliaryElement.TARGET_LINE and mapping.y:
            # Use the 75th percentile as a target line example
            target_val = data[mapping.y].quantile(0.75)
            if target_val is not None:
                rule_data = self.prepare_data_for_altair(pl.DataFrame({"target": [target_val]}))
                rule = (
                    alt.Chart(rule_data)
                    .mark_rule(
                        color=aux_style.get("color", "green"),
                        strokeDash=aux_style.get("stroke_dash", [10, 5]),
                        strokeWidth=aux_style.get("stroke_width", 2),
                        opacity=aux_style.get("opacity", 0.8),
                    )
                    .encode(y="target:Q")
                )
                return alt.layer(chart, rule)

        elif element == AuxiliaryElement.THRESHOLD and mapping.y:
            # Create threshold bands (e.g., mean ± 1 std dev)
            y_col = data[mapping.y]
            # Only apply threshold to numeric data
            if y_col.dtype.is_numeric():
                mean_val = y_col.mean()
                std_val = y_col.std()
                if (
                    mean_val is not None
                    and std_val is not None
                    and isinstance(mean_val, (int, float))
                    and isinstance(std_val, (int, float))
                ):
                    upper_threshold = float(mean_val) + float(std_val)
                    lower_threshold = float(mean_val) - float(std_val)

                    # Create threshold area
                    threshold_data = pl.DataFrame({"lower": [lower_threshold], "upper": [upper_threshold]})

                    area = (
                        alt.Chart(self.prepare_data_for_altair(threshold_data))
                        .mark_rect(
                            opacity=aux_style.get("opacity", 0.3),
                            color=aux_style.get("fill_color", self.color_strategy.data.NEGATIVE_FILL),
                        )
                        .encode(y="lower:Q", y2="upper:Q")
                    )
                    return alt.layer(chart, area)

        elif element == AuxiliaryElement.REGRESSION and mapping.x and mapping.y:
            # Create regression layer from base data
            regression = (
                alt.Chart(self.prepare_data_for_altair(data))
                .transform_regression(
                    on=mapping.x,
                    regression=mapping.y,
                )
                .mark_line(
                    color=aux_style.get("color", self.color_strategy.data.ACCENT),
                    strokeDash=aux_style.get("stroke_dash", [3, 3]),
                    strokeWidth=aux_style.get("stroke_width", 1.5),
                    opacity=aux_style.get("opacity", 0.7),
                )
                .encode(
                    x=f"{mapping.x}:Q",
                    y=f"{mapping.y}:Q",
                )
            )
            # Use alt.layer for proper composition
            return alt.layer(chart, regression)

        elif element == AuxiliaryElement.MOVING_AVG and mapping.x and mapping.y:
            # Create a simple moving average using Altair's transform_window
            # Determine proper x-axis encoding based on data type
            x_col_data = data[mapping.x]
            x_encoding = f"{mapping.x}:N"  # Default to nominal

            # Check if x column contains dates or numeric values
            if hasattr(x_col_data, "dtype"):
                if "date" in str(x_col_data.dtype).lower() or "time" in str(x_col_data.dtype).lower():
                    x_encoding = f"{mapping.x}:T"
                elif x_col_data.dtype.is_numeric():
                    x_encoding = f"{mapping.x}:Q"

            moving_avg = (
                alt.Chart(self.prepare_data_for_altair(data))
                .transform_window(
                    rolling_mean=f"mean({mapping.y})",
                    frame=[-4, 0],  # 5-point moving average (current + 4 previous)
                )
                .mark_line(
                    color=aux_style.get("color", self.color_strategy.structural.AXIS_LINE),
                    strokeWidth=aux_style.get("stroke_width", 1.5),
                    strokeDash=aux_style.get("stroke_dash", []),
                    opacity=aux_style.get("opacity", 0.7),
                )
                .encode(x=x_encoding, y="rolling_mean:Q")
            )
            return alt.layer(chart, moving_avg)

        elif element == AuxiliaryElement.ANNOTATION:
            # Add annotations to highlight interesting data points
            # For basic implementation, annotate the max and min values

            # Determine which column to annotate based on mapping
            if mapping.y:
                # Standard case: annotate y values (bar charts, line charts)
                y_col = data[mapping.y]
                max_idx = y_col.arg_max()
                min_idx = y_col.arg_min()

                if max_idx is not None and min_idx is not None and mapping.x:
                    # Get the actual data points for annotation
                    max_point = data.row(max_idx, named=True)
                    min_point = data.row(min_idx, named=True)

                    # Create annotation data
                    annotation_data = pl.DataFrame(
                        [
                            {
                                mapping.x: max_point[mapping.x],
                                mapping.y: max_point[mapping.y],
                                "annotation": f"Max: {float(max_point[mapping.y]):.1f}",
                            },
                            {
                                mapping.x: min_point[mapping.x],
                                mapping.y: min_point[mapping.y],
                                "annotation": f"Min: {float(min_point[mapping.y]):.1f}",
                            },
                        ]
                    )

                    # Determine proper x-axis encoding based on data type and column name
                    x_col_data = data[mapping.x]
                    x_name_lower = mapping.x.lower()
                    x_encoding = f"{mapping.x}:N"  # Default to nominal for categorical data

                    # Check if x column contains dates or numeric values
                    if hasattr(x_col_data, "dtype"):
                        dtype_str = str(x_col_data.dtype).lower()
                        # Check both dtype and column name for temporal detection
                        if (
                            "date" in dtype_str
                            or "time" in dtype_str
                            or "date" in x_name_lower
                            or "time" in x_name_lower
                        ):
                            x_encoding = f"{mapping.x}:T"
                        elif hasattr(x_col_data.dtype, "is_numeric") and x_col_data.dtype.is_numeric():
                            x_encoding = f"{mapping.x}:Q"
                        # For string/categorical data, keep :N (nominal)

                    annotations = (
                        alt.Chart(self.prepare_data_for_altair(annotation_data))
                        .mark_text(
                            align="center",  # Center for better readability on bars
                            dx=0,
                            dy=-10,  # Position above the bar
                            fontSize=12,
                            color=aux_style.get("text_color", self.color_strategy.text.AXIS_LABEL),
                            fontWeight="bold",
                        )
                        .encode(x=x_encoding, y=f"{mapping.y}:Q", text="annotation:N")
                    )
                    return alt.layer(chart, annotations)

            elif mapping.x:
                # Histogram case: annotate x values (distribution characteristics)
                x_col = data[mapping.x]
                # Only apply annotations to numeric data
                if x_col.dtype.is_numeric():
                    mean_val = x_col.mean()
                    std_val = x_col.std()

                    if (
                        mean_val is not None
                        and std_val is not None
                        and isinstance(mean_val, (int, float))
                        and isinstance(std_val, (int, float))
                    ):
                        mean_float = float(mean_val)
                        std_float = float(std_val)
                        # Create annotations for mean and std dev
                        annotation_data = pl.DataFrame(
                            [
                                {
                                    mapping.x: mean_float,
                                    "annotation": f"Mean: {mean_float:.1f}",
                                    "y_pos": 30,  # Fixed y position for histogram
                                },
                                {
                                    mapping.x: mean_float + std_float,
                                    "annotation": f"+1SD: {(mean_float + std_float):.1f}",
                                    "y_pos": 20,
                                },
                            ]
                        )

                        annotations = (
                            alt.Chart(self.prepare_data_for_altair(annotation_data))
                            .mark_text(
                                align="center",
                                dx=0,
                                dy=-10,
                                fontSize=10,
                                color=aux_style.get("text_color", self.color_strategy.text.AXIS_LABEL),
                                fontWeight="bold",
                            )
                            .encode(x=f"{mapping.x}:Q", y="y_pos:Q", text="annotation:N")
                        )
                        return alt.layer(chart, annotations)

        elif element == AuxiliaryElement.HIGHLIGHT:
            # Highlight specific data points (max/min values) with different colors and shapes

            # Determine which column to highlight based on mapping
            if mapping.y:
                # Standard case: highlight y values (bar charts, line charts)
                y_col = data[mapping.y]
                max_idx = y_col.arg_max()
                min_idx = y_col.arg_min()

                if max_idx is not None and min_idx is not None and mapping.x:
                    # Get the actual data points for highlighting
                    max_point = data.row(max_idx, named=True)
                    min_point = data.row(min_idx, named=True)

                    # Create highlight data
                    highlight_data = pl.DataFrame(
                        [
                            {mapping.x: max_point[mapping.x], mapping.y: max_point[mapping.y], "point_type": "Max"},
                            {mapping.x: min_point[mapping.x], mapping.y: min_point[mapping.y], "point_type": "Min"},
                        ]
                    )

                    # Determine proper x-axis encoding based on data type and column name
                    x_col_data = data[mapping.x]
                    x_name_lower = mapping.x.lower()
                    x_encoding = f"{mapping.x}:N"  # Default to nominal

                    # Check if x column contains dates or numeric values
                    if hasattr(x_col_data, "dtype"):
                        dtype_str = str(x_col_data.dtype).lower()
                        # Check both dtype and column name for temporal detection
                        if (
                            "date" in dtype_str
                            or "time" in dtype_str
                            or "date" in x_name_lower
                            or "time" in x_name_lower
                        ):
                            x_encoding = f"{mapping.x}:T"
                        elif hasattr(x_col_data.dtype, "is_numeric") and x_col_data.dtype.is_numeric():
                            x_encoding = f"{mapping.x}:Q"

                    highlights = (
                        alt.Chart(self.prepare_data_for_altair(highlight_data))
                        .mark_circle(
                            size=aux_style.get("size", 100),  # Larger than normal points
                            stroke=self.color_strategy.structural.BACKGROUND,  # White border for visibility
                            strokeWidth=2,
                        )
                        .encode(
                            x=x_encoding,
                            y=f"{mapping.y}:Q",
                            color=alt.Color(
                                "point_type:N",
                                scale=alt.Scale(
                                    domain=["Max", "Min"],
                                    range=[
                                        self.color_strategy.data.NEGATIVE,
                                        self.color_strategy.data.BASE,
                                    ],  # Semantic colors
                                ),
                                legend=alt.Legend(title="Highlighted Points"),
                            ),
                        )
                    )
                    return alt.layer(chart, highlights)

            elif mapping.x:
                # Histogram case: highlight distribution characteristics
                x_col = data[mapping.x]
                # Only apply highlights to numeric data
                if x_col.dtype.is_numeric():
                    mean_val = x_col.mean()
                    std_val = x_col.std()

                    if (
                        mean_val is not None
                        and std_val is not None
                        and isinstance(mean_val, (int, float))
                        and isinstance(std_val, (int, float))
                    ):
                        mean_float = float(mean_val)
                        std_float = float(std_val)
                        # Highlight mean and standard deviation points
                        highlight_data = pl.DataFrame(
                            [
                                {
                                    mapping.x: mean_float,
                                    "point_type": "Mean",
                                    "y_pos": 25,  # Fixed y position
                                },
                                {mapping.x: mean_float + std_float, "point_type": "+1SD", "y_pos": 15},
                            ]
                        )

                        highlights = (
                            alt.Chart(self.prepare_data_for_altair(highlight_data))
                            .mark_circle(
                                size=aux_style.get("size", 80),
                                stroke=self.color_strategy.structural.BACKGROUND,
                                strokeWidth=2,
                            )
                            .encode(
                                x=f"{mapping.x}:Q",
                                y="y_pos:Q",
                                color=alt.Color(
                                    "point_type:N",
                                    scale=alt.Scale(
                                        domain=["Mean", "+1SD"],
                                        range=[
                                            self.color_strategy.data.NEGATIVE,
                                            self.color_strategy.data.ACCENT,
                                        ],
                                    ),
                                    legend=alt.Legend(title="Distribution Points"),
                                ),
                            )
                        )
                        return alt.layer(chart, highlights)

        return chart

    def prepare_data_for_altair(self, data: pl.DataFrame) -> dict[str, Any]:
        """Convert Polars DataFrame to Altair-compatible format.

        Args:
            data: Polars DataFrame

        Returns:
            Dictionary in records format for Altair
        """
        # Convert to records format (list of dicts)
        records = data.to_dicts()

        # Convert datetime objects to ISO format strings for JSON serialization
        for record in records:
            for key, value in record.items():
                if hasattr(value, "isoformat"):
                    record[key] = value.isoformat()

        return {"values": records}
