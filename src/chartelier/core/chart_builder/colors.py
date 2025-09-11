"""Color system definitions for Chartelier visualization.

This module provides centralized color definitions following WCAG accessibility
standards and visualization best practices.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict

from chartelier.core.enums import AuxiliaryElement, PatternID


class StructuralColors(BaseModel):
    """Colors for chart structural elements (axes, grids, etc.)."""

    model_config = ConfigDict(frozen=True)

    BACKGROUND: str = "#FFFFFF"
    AXIS_LINE: str = "#475569"  # Moderate slate for unobtrusive structure
    TICK_LINE: str = "#CBD5E1"
    GRID_MAJOR: str = "#E2E8F0"
    GRID_MINOR: str = "#F1F5F9"  # Optional minor grid


class TextColors(BaseModel):
    """Colors for text elements with hierarchical emphasis."""

    model_config = ConfigDict(frozen=True)

    TITLE: str = "#0F172A"  # Darkest slate for maximum contrast
    LEGEND: str = "#334155"
    AXIS_LABEL: str = "#1F2937"
    AXIS_UNIT: str = "#64748B"  # Lighter for secondary information


class DataColors:
    """Colors for data representation."""

    # Primary colors
    BASE: str = "#08192D"  # Non-glaring blue for default lines/bars
    ACCENT: str = "#2563EB"  # Cyan for emphasis or second series

    # Categorical palette - using class attributes instead of dataclass fields
    CHARTELIER_QUAL_10: tuple[str, ...] = (
        "#08192D",  # Blue
        "#2EA9DF",  # Teal
        "#2D6D4B",  # Green
        "#F7C242",  # Yellow
        "#F75C2F",  # Orange
        "#D0104C",  # Red
        "#6F3381",  # Purple
        "#E03C8A",  # Pink
        "#9C755F",  # Brown
        "#BAB0AC",  # Gray
    )

    # Sequential palette (ColorBrewer Blues 9)
    BLUES_9: tuple[str, ...] = (
        "#f7fbff",
        "#deebf7",
        "#c6dbef",
        "#9ecae1",
        "#6baed6",
        "#4292c6",
        "#2171b5",
        "#08519c",
        "#08306b",
    )

    # Semantic colors (from CHARTELIER_QUAL_10 palette)
    POSITIVE: str = "#3DBE82"  # Green
    NEGATIVE: str = "#E95454"  # Red
    POSITIVE_FILL: str = "#5FCB98"  # Light green for area fills
    NEGATIVE_FILL: str = "#F17B7B"  # Light red for area fills


class StyleConstants:
    """Constants for visual styling (widths, opacity, etc.)."""

    # Line widths
    LINE_WIDTH_DEFAULT: float = 2.0
    LINE_WIDTH_THIN: float = 1.5
    LINE_WIDTH_THICK: float = 2.5
    GRID_LINE_WIDTH: float = 1.0

    # Opacity
    AREA_FILL_OPACITY: float = 0.25  # For area charts
    BAR_FILL_OPACITY: float = 0.9  # Solid but not 100%
    OVERLAY_OPACITY: float = 0.7  # For overlapping elements
    GRID_OPACITY: float = 0.6  # Major grid
    GRID_MINOR_OPACITY: float = 0.4  # Minor grid

    # Stroke patterns - using tuples for immutability
    DASH_PATTERN_SHORT: tuple[int, int] = (5, 5)
    DASH_PATTERN_MEDIUM: tuple[int, int] = (10, 5)
    DASH_PATTERN_LONG: tuple[int, int] = (10, 10)
    DOT_PATTERN: tuple[int, int] = (3, 3)


class ColorStrategy:
    """Strategy for selecting colors based on pattern and data characteristics."""

    def __init__(self) -> None:
        """Initialize color strategy with default palettes."""
        self.structural = StructuralColors()
        self.text = TextColors()
        self.data = DataColors()
        self.style = StyleConstants()

    def get_pattern_colors(self, pattern_id: PatternID, series_count: int = 1) -> dict[str, Any]:
        """Get color configuration for a specific pattern.

        Args:
            pattern_id: Visualization pattern identifier
            series_count: Number of data series to display

        Returns:
            Dictionary with color scheme configuration
        """
        strategies: dict[PatternID, dict[str, Any]] = {
            PatternID.P01: {  # Single time series
                "primary": self.data.BASE,
                "fill_opacity": self.style.AREA_FILL_OPACITY,
                "stroke_width": self.style.LINE_WIDTH_DEFAULT,
            },
            PatternID.P02: {  # Category comparison (bar)
                "primary": self.data.BASE,
                "fill_opacity": self.style.BAR_FILL_OPACITY,
                "stroke": self._darken_color(self.data.BASE, 0.2),
            },
            PatternID.P03: {  # Distribution (histogram)
                "primary": self.data.BASE,
                "fill_opacity": self.style.BAR_FILL_OPACITY,
                "edge_color": self.structural.GRID_MAJOR,
            },
            PatternID.P12: {  # Multiple time series
                "scheme": self._get_categorical_scheme(series_count),
                "stroke_width": self.style.LINE_WIDTH_DEFAULT,
            },
            PatternID.P13: {  # Distribution over time (faceted)
                "scheme": self._get_categorical_scheme(series_count),
                "custom_range": list(self.data.CHARTELIER_QUAL_10),
                "fill_opacity": self.style.BAR_FILL_OPACITY,
            },
            PatternID.P21: {  # Grouped bar
                "scheme": self._get_categorical_scheme(series_count),
                "fill_opacity": self.style.BAR_FILL_OPACITY,
            },
            PatternID.P23: {  # Overlay histogram
                "scheme": self._get_categorical_scheme(series_count),
                "fill_opacity": self.style.OVERLAY_OPACITY,
            },
            PatternID.P31: {  # Small multiples
                "primary": self.data.BASE,
                "accent": self.data.ACCENT,
                "stroke_width": self.style.LINE_WIDTH_THIN,
            },
            PatternID.P32: {  # Box plot comparison
                "primary": self.data.BASE,
                "fill_opacity": self.style.OVERLAY_OPACITY,
                "whisker_color": self.structural.AXIS_LINE,
            },
        }
        default_strategy: dict[str, Any] = {"primary": self.data.BASE}
        if pattern_id in strategies:
            return strategies[pattern_id]
        return default_strategy

    def get_auxiliary_colors(self, element: AuxiliaryElement) -> dict[str, Any]:
        """Get color configuration for auxiliary elements.

        Args:
            element: Type of auxiliary element

        Returns:
            Dictionary with element styling configuration
        """
        configs: dict[AuxiliaryElement, dict[str, Any]] = {
            AuxiliaryElement.TARGET_LINE: {
                "color": "#334155",  # Gray color for better visual neutrality
                "stroke_dash": list(self.style.DASH_PATTERN_MEDIUM),
                "stroke_width": self.style.LINE_WIDTH_DEFAULT,
                "opacity": 0.8,
            },
        }
        default_config: dict[str, Any] = {
            "color": self.structural.AXIS_LINE,
            "stroke_width": self.style.LINE_WIDTH_DEFAULT,
        }
        if element in configs:
            return configs[element]
        return default_config

    def _get_categorical_scheme(self, series_count: int) -> list[str]:
        """Select appropriate categorical color scheme based on series count.

        Args:
            series_count: Number of categories/series

        Returns:
            List of color values
        """
        # Always use CHARTELIER_QUAL_10 palette for consistency
        if series_count <= 10:
            return list(self.data.CHARTELIER_QUAL_10[:series_count])
        # For more than 10, cycle through the 10-color palette
        # This should be avoided per visualization policy
        return list(self.data.CHARTELIER_QUAL_10)

    def _darken_color(self, color: str, factor: float) -> str:
        """Darken a color by a given factor.

        Args:
            color: Hex color string
            factor: Darkening factor (0.0 = no change, 1.0 = black)

        Returns:
            Darkened hex color string
        """
        # Simple darkening by reducing RGB values
        # This is a placeholder - could use a proper color library
        if not color.startswith("#"):
            return color

        # Convert hex to RGB
        hex_color = color.lstrip("#")
        r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

        # Darken
        r = int(r * (1 - factor))
        g = int(g * (1 - factor))
        b = int(b * (1 - factor))

        return f"#{r:02x}{g:02x}{b:02x}"


# Global instance for easy access
color_strategy = ColorStrategy()
