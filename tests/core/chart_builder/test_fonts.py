"""Tests for font configuration module."""

import os
from unittest.mock import patch

from chartelier.core.chart_builder.fonts import ChartierFonts, chartelier_fonts


class TestChartierFonts:
    """Test font configuration and environment detection."""

    def test_default_font_stack(self) -> None:
        """Test default font stack for local development."""
        with patch.dict(os.environ, {}, clear=True):
            font_stack = ChartierFonts.get_font_stack()
            assert font_stack == ChartierFonts.CHARTELIER_FONT_STACK
            assert "IBM Plex Sans JP" in font_stack
            assert "sans-serif" in font_stack

    def test_ci_font_stack(self) -> None:
        """Test CI environment font stack."""
        with patch.dict(os.environ, {"CI": "true"}):
            font_stack = ChartierFonts.get_font_stack()
            assert font_stack == ChartierFonts.CI_FONT_STACK
            assert "Noto Sans" in font_stack
            assert "IBM Plex Sans JP" not in font_stack

    def test_github_actions_detection(self) -> None:
        """Test GitHub Actions environment detection."""
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            font_stack = ChartierFonts.get_font_stack()
            assert font_stack == ChartierFonts.CI_FONT_STACK

    def test_font_string_generation(self) -> None:
        """Test comma-separated font string generation."""
        with patch.dict(os.environ, {}, clear=True):
            font_string = ChartierFonts.get_font_string()
            assert isinstance(font_string, str)
            assert "," in font_string
            assert font_string.startswith("IBM Plex Sans JP")
            assert font_string.endswith("sans-serif")

    def test_ci_font_string(self) -> None:
        """Test CI font string generation."""
        with patch.dict(os.environ, {"CI": "true"}):
            font_string = ChartierFonts.get_font_string()
            assert isinstance(font_string, str)
            assert font_string.startswith("Noto Sans")

    def test_monospace_font_stack(self) -> None:
        """Test monospace font stack."""
        with patch.dict(os.environ, {}, clear=True):
            mono_stack = ChartierFonts.get_monospace_stack()
            assert "IBM Plex Mono" in mono_stack
            assert "monospace" in mono_stack

    def test_ci_monospace_font_stack(self) -> None:
        """Test CI monospace font stack."""
        with patch.dict(os.environ, {"CI": "true"}):
            mono_stack = ChartierFonts.get_monospace_stack()
            assert mono_stack == ["monospace"]

    def test_monospace_string_generation(self) -> None:
        """Test monospace font string generation."""
        with patch.dict(os.environ, {}, clear=True):
            mono_string = ChartierFonts.get_monospace_string()
            assert isinstance(mono_string, str)
            assert "monospace" in mono_string

    def test_global_instance(self) -> None:
        """Test global chartelier_fonts instance."""
        assert chartelier_fonts is not None
        assert isinstance(chartelier_fonts, ChartierFonts)

        # Test that methods work on global instance
        with patch.dict(os.environ, {}, clear=True):
            font_string = chartelier_fonts.get_font_string()
            assert isinstance(font_string, str)
