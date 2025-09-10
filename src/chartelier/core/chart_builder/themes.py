"""Theme management for Chartelier visualization.

This module provides theme application mechanisms for consistent styling
across all chart types.
"""

from typing import Any

import altair as alt

from chartelier.core.chart_builder.colors import (
    ColorStrategy,
    DataColors,
    StructuralColors,
    StyleConstants,
    TextColors,
)
from chartelier.core.chart_builder.fonts import chartelier_fonts


class Theme:
    """Base theme class for applying consistent styling to charts."""

    def __init__(self) -> None:
        """Initialize theme with default color definitions."""
        self.structural = StructuralColors()
        self.text = TextColors()
        self.data = DataColors()
        self.style = StyleConstants()
        self.color_strategy = ColorStrategy()

    def apply_to_chart(self, chart: alt.Chart) -> alt.Chart:
        """Apply theme settings to an Altair chart.

        Args:
            chart: Altair chart object

        Returns:
            Chart with theme applied
        """
        configured_chart: alt.Chart = (
            chart.configure(
                background=self.structural.BACKGROUND,
                padding=20,
            )
            .configure_axis(
                domainColor=self.structural.AXIS_LINE,
                domainWidth=1,
                grid=False,  # Disable grid lines
                labelColor=self.text.AXIS_LABEL,
                labelFont=chartelier_fonts.get_font_string(),
                labelFontSize=11,
                tickColor=self.structural.TICK_LINE,
                tickSize=5,
                tickWidth=1,
                titleColor=self.text.AXIS_LABEL,
                titleFont=chartelier_fonts.get_font_string(),
                titleFontSize=12,
                titleFontWeight="normal",
            )
            .configure_axisX(
                labelAngle=0,  # Keep labels horizontal for readability
            )
            .configure_axisY(
                grid=False,  # Disable grid lines
            )
            .configure_legend(
                labelColor=self.text.LEGEND,
                labelFont=chartelier_fonts.get_font_string(),
                labelFontSize=11,
                titleColor=self.text.LEGEND,
                titleFont=chartelier_fonts.get_font_string(),
                titleFontSize=12,
                orient="top-right",  # Default to top-right to avoid axis overlap
            )
            .configure_title(
                color=self.text.TITLE,
                font=chartelier_fonts.get_font_string(),
                fontSize=18,  # Increased from 14 for better visibility
                fontWeight="bold",
                anchor="start",
            )
            .configure_view(
                strokeWidth=0,  # No border around chart area
            )
        )
        return configured_chart

    def get_base_config(self) -> dict[str, Any]:
        """Get base configuration dictionary for manual application.

        Returns:
            Dictionary with theme configuration
        """
        return {
            "background": self.structural.BACKGROUND,
            "padding": 20,
            "axis": {
                "domainColor": self.structural.AXIS_LINE,
                "domainWidth": 1,
                "grid": False,  # Disable grid lines
                "labelColor": self.text.AXIS_LABEL,
                "labelFont": chartelier_fonts.get_font_string(),
                "labelFontSize": 11,
                "tickColor": self.structural.TICK_LINE,
                "tickSize": 5,
                "tickWidth": 1,
                "titleColor": self.text.AXIS_LABEL,
                "titleFont": chartelier_fonts.get_font_string(),
                "titleFontSize": 12,
                "titleFontWeight": "normal",
            },
            "axisX": {
                "labelAngle": 0,
            },
            "axisY": {
                "grid": False,  # Disable grid lines
            },
            "legend": {
                "labelColor": self.text.LEGEND,
                "labelFont": chartelier_fonts.get_font_string(),
                "labelFontSize": 11,
                "titleColor": self.text.LEGEND,
                "titleFont": chartelier_fonts.get_font_string(),
                "titleFontSize": 12,
                "orient": "top-right",
            },
            "title": {
                "color": self.text.TITLE,
                "font": chartelier_fonts.get_font_string(),
                "fontSize": 18,  # Increased from 14 for better visibility
                "fontWeight": "bold",
                "anchor": "start",
            },
            "view": {
                "strokeWidth": 0,
            },
            "range": {
                "category": self.data.CHARTELIER_QUAL_10,
            },
        }

    def apply_pattern_specific(self, chart: alt.Chart, pattern_id: str, series_count: int = 1) -> alt.Chart:
        """Apply pattern-specific color configuration.

        Args:
            chart: Altair chart object
            pattern_id: Pattern identifier
            series_count: Number of data series

        Returns:
            Chart with pattern-specific colors applied
        """
        # First apply base theme
        chart = self.apply_to_chart(chart)

        # Get pattern-specific colors
        pattern_colors = self.color_strategy.get_pattern_colors(pattern_id, series_count)  # type: ignore[arg-type]

        # Apply categorical scheme if specified
        if "scheme" in pattern_colors:
            if isinstance(pattern_colors["scheme"], list):
                chart = chart.configure_range(category=pattern_colors["scheme"])
            elif pattern_colors["scheme"] == "blues" and "custom_range" in pattern_colors:
                chart = chart.configure_range(ramp=pattern_colors["custom_range"])

        return chart


# Global default theme instance
default_theme = Theme()
