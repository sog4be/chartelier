"""Tests for the theme management module."""

import os
from unittest.mock import patch

import altair as alt
import polars as pl

from chartelier.core.chart_builder.themes import Theme, default_theme
from chartelier.core.enums import PatternID


class TestTheme:
    """Test theme functionality."""

    def test_theme_initialization(self) -> None:
        """Test that theme initializes with correct components."""
        theme = Theme()
        assert theme.structural is not None
        assert theme.text is not None
        assert theme.data is not None
        assert theme.style is not None
        assert theme.color_strategy is not None

    def test_apply_to_chart(self) -> None:
        """Test applying theme to a chart."""
        theme = Theme()

        # Create a simple chart
        data = pl.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
        chart = alt.Chart({"values": data.to_dicts()}).mark_line()

        # Apply theme
        themed_chart = theme.apply_to_chart(chart)

        # Check that chart has config applied
        assert themed_chart is not None
        # Note: Direct config inspection is limited in Altair,
        # but we can verify the chart is still valid
        assert isinstance(themed_chart, alt.Chart)

    def test_get_base_config(self) -> None:
        """Test getting base configuration dictionary."""
        theme = Theme()
        config = theme.get_base_config()

        # Check structure
        assert "background" in config
        assert "axis" in config
        assert "legend" in config
        assert "title" in config
        assert "view" in config
        assert "range" in config

        # Check values
        assert config["background"] == theme.structural.BACKGROUND
        assert config["axis"]["domainColor"] == theme.structural.AXIS_LINE
        assert config["axis"]["gridColor"] == theme.structural.GRID_MAJOR
        assert config["legend"]["labelColor"] == theme.text.LEGEND
        assert config["title"]["color"] == theme.text.TITLE

    def test_apply_pattern_specific(self) -> None:
        """Test applying pattern-specific theme settings."""
        theme = Theme()

        # Create a simple chart
        data = pl.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
        chart = alt.Chart({"values": data.to_dicts()}).mark_line()

        # Apply pattern-specific theme
        themed_chart = theme.apply_pattern_specific(chart, PatternID.P01)

        # Verify chart is valid
        assert isinstance(themed_chart, alt.Chart)

        # Apply with multiple series
        themed_chart = theme.apply_pattern_specific(chart, PatternID.P12, series_count=5)
        assert isinstance(themed_chart, alt.Chart)

    def test_axis_configuration(self) -> None:
        """Test axis configuration in theme."""
        theme = Theme()
        config = theme.get_base_config()

        axis_config = config["axis"]
        assert axis_config["domainWidth"] == 1
        assert axis_config["gridOpacity"] == theme.style.GRID_OPACITY
        assert axis_config["gridWidth"] == theme.style.GRID_LINE_WIDTH
        assert axis_config["labelFontSize"] == 11
        assert axis_config["titleFontSize"] == 12
        # Check font configuration
        assert "labelFont" in axis_config
        assert "titleFont" in axis_config
        assert isinstance(axis_config["labelFont"], str)
        assert isinstance(axis_config["titleFont"], str)

    def test_legend_configuration(self) -> None:
        """Test legend configuration in theme."""
        theme = Theme()
        config = theme.get_base_config()

        legend_config = config["legend"]
        assert legend_config["labelFontSize"] == 11
        assert legend_config["titleFontSize"] == 12
        assert legend_config["orient"] == "top-right"
        # Check font configuration
        assert "labelFont" in legend_config
        assert "titleFont" in legend_config
        assert isinstance(legend_config["labelFont"], str)
        assert isinstance(legend_config["titleFont"], str)

    def test_title_configuration(self) -> None:
        """Test title configuration in theme."""
        theme = Theme()
        config = theme.get_base_config()

        title_config = config["title"]
        assert title_config["fontSize"] == 14
        assert title_config["fontWeight"] == "bold"
        assert title_config["anchor"] == "start"
        # Check font configuration
        assert "font" in title_config
        assert isinstance(title_config["font"], str)

    def test_global_default_theme(self) -> None:
        """Test that global default_theme instance is available."""
        assert default_theme is not None
        assert isinstance(default_theme, Theme)

        # Verify it has all components
        assert default_theme.structural is not None
        assert default_theme.text is not None
        assert default_theme.data is not None
        assert default_theme.style is not None

    def test_font_configuration_local(self) -> None:
        """Test font configuration in local environment."""
        with patch.dict(os.environ, {}, clear=True):
            theme = Theme()
            config = theme.get_base_config()

            # Check that font stacks contain expected fonts
            axis_font = config["axis"]["labelFont"]
            assert "IBM Plex Sans JP" in axis_font or "Noto Sans" in axis_font
            assert "sans-serif" in axis_font

    def test_font_configuration_ci(self) -> None:
        """Test font configuration in CI environment."""
        with patch.dict(os.environ, {"CI": "true"}):
            theme = Theme()
            config = theme.get_base_config()

            # Check that CI fonts are used
            axis_font = config["axis"]["labelFont"]
            assert "Noto Sans" in axis_font
            assert "IBM Plex Sans JP" not in axis_font
            assert "sans-serif" in axis_font
