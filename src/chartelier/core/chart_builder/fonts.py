"""Font configuration for Chartelier visualizations.

This module provides font stack definitions for consistent typography
across all chart types, with environment-aware fallbacks for CI/production.
"""

import os
from typing import ClassVar


class ChartierFonts:
    """Font stack management for Chartelier visualizations."""

    # Primary font stack for local development with Japanese support
    CHARTELIER_FONT_STACK: ClassVar[list[str]] = [
        "IBM Plex Sans JP",
        "IBM Plex Sans",
        "Noto Sans CJK JP",
        "Noto Sans",
        "sans-serif",
    ]

    # CI/Production font stack with commonly available fonts
    CI_FONT_STACK: ClassVar[list[str]] = [
        "Noto Sans",  # Ubuntu standard
        "DejaVu Sans",  # Commonly available in CI
        "Liberation Sans",  # Alternative open font
        "sans-serif",  # Final fallback
    ]

    @classmethod
    def get_font_stack(cls) -> list[str]:
        """Get appropriate font stack based on environment.

        Returns CI-optimized fonts when running in CI environment,
        otherwise returns the full font stack with Japanese support.

        Returns:
            List of font family names in priority order
        """
        # Detect CI environment
        if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
            return cls.CI_FONT_STACK
        return cls.CHARTELIER_FONT_STACK

    @classmethod
    def get_font_string(cls) -> str:
        """Get comma-separated font family string for Vega-Lite.

        Returns:
            Comma-separated font family string
        """
        return ", ".join(cls.get_font_stack())

    @classmethod
    def get_monospace_stack(cls) -> list[str]:
        """Get monospace font stack for code/data display.

        Returns:
            List of monospace font family names
        """
        if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
            return ["monospace"]
        return [
            "IBM Plex Mono",
            "Noto Sans Mono",
            "Consolas",
            "Monaco",
            "monospace",
        ]

    @classmethod
    def get_monospace_string(cls) -> str:
        """Get comma-separated monospace font family string.

        Returns:
            Comma-separated monospace font family string
        """
        return ", ".join(cls.get_monospace_stack())


# Global font configuration instance
chartelier_fonts = ChartierFonts()
