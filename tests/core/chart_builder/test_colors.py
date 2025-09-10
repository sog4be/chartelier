"""Tests for the color system module."""

from chartelier.core.chart_builder.colors import (
    ColorStrategy,
    DataColors,
    StructuralColors,
    StyleConstants,
    TextColors,
    color_strategy,
)
from chartelier.core.enums import AuxiliaryElement, PatternID


class TestStructuralColors:
    """Test structural color definitions."""

    def test_color_values(self) -> None:
        """Test that structural colors have correct hex values."""
        colors = StructuralColors()
        assert colors.BACKGROUND == "#FFFFFF"
        assert colors.AXIS_LINE == "#475569"
        assert colors.TICK_LINE == "#CBD5E1"
        assert colors.GRID_MAJOR == "#E2E8F0"
        assert colors.GRID_MINOR == "#F1F5F9"


class TestTextColors:
    """Test text color definitions."""

    def test_color_hierarchy(self) -> None:
        """Test that text colors follow hierarchical contrast."""
        colors = TextColors()
        assert colors.TITLE == "#0F172A"  # Darkest
        assert colors.LEGEND == "#334155"
        assert colors.AXIS_LABEL == "#1F2937"
        assert colors.AXIS_UNIT == "#64748B"  # Lightest


class TestDataColors:
    """Test data color definitions."""

    def test_primary_colors(self) -> None:
        """Test primary color definitions."""
        colors = DataColors()
        assert colors.BASE == "#08192D"
        assert colors.ACCENT == "#2563EB"

    def test_categorical_palettes(self) -> None:
        """Test categorical color palettes."""
        colors = DataColors()

        # Chartelier qualitative palette should have 10 colors
        assert len(colors.CHARTELIER_QUAL_10) == 10
        assert colors.CHARTELIER_QUAL_10[0] == "#08192D"  # Blue

    def test_sequential_palette(self) -> None:
        """Test sequential color palette."""
        colors = DataColors()
        assert len(colors.BLUES_9) == 9
        assert colors.BLUES_9[0] == "#f7fbff"  # Lightest
        assert colors.BLUES_9[-1] == "#08306b"  # Darkest

    def test_semantic_colors(self) -> None:
        """Test semantic color definitions."""
        colors = DataColors()
        assert colors.POSITIVE == "#3DBE82"  # Green
        assert colors.NEGATIVE == "#E95454"  # Red
        assert colors.POSITIVE_FILL == "#5FCB98"  # Light green for area fills
        assert colors.NEGATIVE_FILL == "#F17B7B"  # Light red for area fills


class TestStyleConstants:
    """Test style constant definitions."""

    def test_line_widths(self) -> None:
        """Test line width constants."""
        style = StyleConstants()
        assert style.LINE_WIDTH_DEFAULT == 2.0
        assert style.LINE_WIDTH_THIN == 1.5
        assert style.LINE_WIDTH_THICK == 2.5
        assert style.GRID_LINE_WIDTH == 1.0

    def test_opacity_values(self) -> None:
        """Test opacity constants."""
        style = StyleConstants()
        assert style.AREA_FILL_OPACITY == 0.25
        assert style.BAR_FILL_OPACITY == 0.9
        assert style.OVERLAY_OPACITY == 0.7
        assert style.GRID_OPACITY == 0.6
        assert style.GRID_MINOR_OPACITY == 0.4

    def test_stroke_patterns(self) -> None:
        """Test stroke pattern definitions."""
        style = StyleConstants()
        assert style.DASH_PATTERN_SHORT == (5, 5)
        assert style.DASH_PATTERN_MEDIUM == (10, 5)
        assert style.DASH_PATTERN_LONG == (10, 10)
        assert style.DOT_PATTERN == (3, 3)


class TestColorStrategy:
    """Test color strategy functionality."""

    def test_pattern_colors_p01(self) -> None:
        """Test color configuration for P01 pattern."""
        strategy = ColorStrategy()
        colors = strategy.get_pattern_colors(PatternID.P01)

        assert "primary" in colors
        assert colors["primary"] == strategy.data.BASE
        assert "fill_opacity" in colors
        assert colors["fill_opacity"] == strategy.style.AREA_FILL_OPACITY

    def test_pattern_colors_p12(self) -> None:
        """Test color configuration for P12 pattern (multiple series)."""
        strategy = ColorStrategy()

        # Test with few series
        colors = strategy.get_pattern_colors(PatternID.P12, series_count=5)
        assert "scheme" in colors
        assert len(colors["scheme"]) == 5

        # Test with many series
        colors = strategy.get_pattern_colors(PatternID.P12, series_count=9)
        assert "scheme" in colors
        assert len(colors["scheme"]) == 9

    def test_categorical_scheme_selection(self) -> None:
        """Test that appropriate categorical scheme is selected based on series count."""
        strategy = ColorStrategy()

        # Test through public interface - P12 uses categorical scheme
        # Should always use CHARTELIER_QUAL_10 for consistency
        colors_5 = strategy.get_pattern_colors(PatternID.P12, series_count=5)
        assert "scheme" in colors_5
        assert len(colors_5["scheme"]) == 5
        assert colors_5["scheme"][0] == strategy.data.CHARTELIER_QUAL_10[0]

        # Should still use Chartelier qualitative for > 8 series
        colors_9 = strategy.get_pattern_colors(PatternID.P12, series_count=9)
        assert "scheme" in colors_9
        assert len(colors_9["scheme"]) == 9
        assert colors_9["scheme"][0] == strategy.data.CHARTELIER_QUAL_10[0]

    def test_auxiliary_colors_mean_line(self) -> None:
        """Test color configuration for mean line auxiliary element."""
        strategy = ColorStrategy()
        colors = strategy.get_auxiliary_colors(AuxiliaryElement.MEAN_LINE)

        assert colors["color"] == strategy.data.NEGATIVE
        assert colors["stroke_dash"] == list(strategy.style.DASH_PATTERN_SHORT)
        assert colors["stroke_width"] == strategy.style.LINE_WIDTH_DEFAULT
        assert colors["opacity"] == 0.8

    def test_auxiliary_colors_threshold(self) -> None:
        """Test color configuration for threshold auxiliary element."""
        strategy = ColorStrategy()
        colors = strategy.get_auxiliary_colors(AuxiliaryElement.THRESHOLD)

        assert colors["fill_color"] == strategy.data.NEGATIVE_FILL
        assert colors["opacity"] == 0.3
        assert colors["edge_color"] == strategy.data.NEGATIVE

    def test_pattern_colors_with_edge_cases(self) -> None:
        """Test pattern color functionality with edge cases."""
        strategy = ColorStrategy()

        # Test with high series count (should handle gracefully)
        colors = strategy.get_pattern_colors(PatternID.P12, series_count=15)
        assert "scheme" in colors
        # Should still return a scheme even with high series count
        assert len(colors["scheme"]) == 10  # Capped at max available colors

    def test_global_instance(self) -> None:
        """Test that global color_strategy instance is available."""
        assert color_strategy is not None
        assert isinstance(color_strategy, ColorStrategy)
