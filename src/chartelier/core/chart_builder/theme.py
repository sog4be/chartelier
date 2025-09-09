"""Structured theme and palettes using Pydantic models and Enums.

Provides a validated, extensible configuration for Chartelier visuals.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator

HEX_RE = re.compile(r"^#([0-9A-Fa-f]{6})$")


class QualitativePalette(Enum):
    """Qualitative palette identifiers."""

    OKABE_ITO_8 = "okabe_ito_8"
    QUAL_10 = "qual_10"


class ContinuousScheme(Enum):
    """Continuous palette identifiers (by scheme)."""

    BLUES_9 = "blues_9"


class AxisColors(BaseModel):
    """Axis-related colors for domain/tick/labels/units."""

    domain: str
    tick: str
    label: str
    unit: str

    @field_validator("domain", "tick", "label", "unit")
    @classmethod
    def _is_hex(cls, v: str) -> str:
        if not HEX_RE.match(v):
            raise ValueError("expected 6-digit HEX color like #RRGGBB")
        return v


class GridColors(BaseModel):
    """Grid line colors and opacities (major/minor)."""

    major: str
    minor: str
    major_opacity: float = Field(0.6, ge=0, le=1)
    minor_opacity: float = Field(0.4, ge=0, le=1)

    @field_validator("major", "minor")
    @classmethod
    def _is_hex(cls, v: str) -> str:
        if not HEX_RE.match(v):
            raise ValueError("expected 6-digit HEX color like #RRGGBB")
        return v


class TypographyColors(BaseModel):
    """Text colors for titles and legend entries."""

    title: str
    legend: str

    @field_validator("title", "legend")
    @classmethod
    def _is_hex(cls, v: str) -> str:
        if not HEX_RE.match(v):
            raise ValueError("expected 6-digit HEX color like #RRGGBB")
        return v


class ObjectColors(BaseModel):
    """Primary object colors: base, accent, positive, negative."""

    base: str
    accent: str
    positive: str
    negative: str

    @field_validator("base", "accent", "positive", "negative")
    @classmethod
    def _is_hex(cls, v: str) -> str:
        if not HEX_RE.match(v):
            raise ValueError("expected 6-digit HEX color like #RRGGBB")
        return v


class ThemeColors(BaseModel):
    """Top-level color grouping for theme application."""

    background: str
    axis: AxisColors
    grid: GridColors
    text: TypographyColors
    obj: ObjectColors

    @field_validator("background")
    @classmethod
    def _is_hex(cls, v: str) -> str:
        if not HEX_RE.match(v):
            raise ValueError("expected 6-digit HEX color like #RRGGBB")
        return v


class ThemePalettes(BaseModel):
    """Validated categorical/continuous palettes."""

    okabe_ito_8: list[str]
    qual_10: list[str]
    blues_9: list[str]

    @field_validator("okabe_ito_8")
    @classmethod
    def _okabe_len(cls, v: list[str]) -> list[str]:
        if len(v) != 8:
            raise ValueError("Okabe-Ito palette must have 8 colors")
        for c in v:
            if not HEX_RE.match(c):
                raise ValueError("palette color must be HEX #RRGGBB")
        return v

    @field_validator("qual_10")
    @classmethod
    def _qual10_len(cls, v: list[str]) -> list[str]:
        if len(v) != 10:
            raise ValueError("Qual-10 palette must have 10 colors")
        for c in v:
            if not HEX_RE.match(c):
                raise ValueError("palette color must be HEX #RRGGBB")
        return v

    @field_validator("blues_9")
    @classmethod
    def _blues9_len(cls, v: list[str]) -> list[str]:
        if len(v) != 9:
            raise ValueError("Blues(9) palette must have 9 colors")
        for c in v:
            if not HEX_RE.match(c):
                raise ValueError("palette color must be HEX #RRGGBB")
        return v


class ThemeConfig(BaseModel):
    """Theme configuration, including colors, palettes, and defaults."""

    colors: ThemeColors
    palettes: ThemePalettes
    default_line_width: float = 2.0
    default_area_opacity: float = Field(0.25, ge=0, le=1)


# Default theme instance
THEME = ThemeConfig(
    colors=ThemeColors(
        background="#FFFFFF",
        axis=AxisColors(
            domain="#475569",
            tick="#CBD5E1",
            label="#1F2937",
            unit="#64748B",
        ),
        grid=GridColors(
            major="#E2E8F0",
            minor="#F1F5F9",
            major_opacity=0.6,
            minor_opacity=0.4,
        ),
        text=TypographyColors(
            title="#0F172A",
            legend="#334155",
        ),
        obj=ObjectColors(
            base="#2563EB",
            accent="#06B6D4",
            positive="#009E73",
            negative="#D55E00",
        ),
    ),
    palettes=ThemePalettes(
        okabe_ito_8=[
            "#E69F00",
            "#56B4E9",
            "#009E73",
            "#F0E442",
            "#0072B2",
            "#D55E00",
            "#CC79A7",
            "#000000",
        ],
        qual_10=[
            "#4E79A7",
            "#F28E2B",
            "#E15759",
            "#76B7B2",
            "#59A14F",
            "#EDC948",
            "#B07AA1",
            "#FF9DA7",
            "#9C755F",
            "#BAB0AC",
        ],
        blues_9=[
            "#f7fbff",
            "#deebf7",
            "#c6dbef",
            "#9ecae1",
            "#6baed6",
            "#4292c6",
            "#2171b5",
            "#08519c",
            "#08306b",
        ],
    ),
)


def apply_theme(
    chart: Any,
    theme: ThemeConfig = THEME,
) -> Any:
    """Apply Chartelier visual theme to an Altair chart.

    Sets background, axis/legend/title colors, and grid styling.
    """
    return (
        chart.configure_view(fill=theme.colors.background, stroke=None)
        .configure_axis(
            domain=True,
            domainColor=theme.colors.axis.domain,
            labelColor=theme.colors.axis.label,
            tickColor=theme.colors.axis.tick,
            grid=True,
            gridColor=theme.colors.grid.major,
            gridOpacity=theme.colors.grid.major_opacity,
            titleColor=theme.colors.axis.label,
        )
        .configure_legend(
            labelColor=theme.colors.text.legend,
            titleColor=theme.colors.text.legend,
        )
        .configure_title(color=theme.colors.text.title)
    )


def categorical_palette_for_series_count(n: int, theme: ThemeConfig = THEME) -> list[str]:
    """Return a qualitative palette based on series count."""
    return theme.palettes.okabe_ito_8 if n <= 8 else theme.palettes.qual_10


def continuous_scheme_blues() -> tuple[str, int]:
    """Return the recommended continuous scheme name and count for Blues(9)."""
    return "blues", 9
