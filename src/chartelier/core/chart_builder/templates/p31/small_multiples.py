"""Small multiples template for P31 pattern."""

from typing import Any

import altair as alt
import polars as pl

from chartelier.core.chart_builder.base import BaseTemplate, TemplateSpec
from chartelier.core.enums import AuxiliaryElement, PatternID
from chartelier.core.models import MappingConfig


class SmallMultiplesTemplate(BaseTemplate):
    """Small multiples template for showing overall picture over time."""

    def _get_spec(self) -> TemplateSpec:
        """Get template specification.

        Returns:
            Template specification for small multiples
        """
        return TemplateSpec(
            template_id="P31_small_multiples",
            name="Small Multiples",
            pattern_ids=["P31"],  # Overview + Transition - Overall picture over time
            required_encodings=["x", "y", "facet"],  # x for time, y for values, facet for grouping
            optional_encodings=["color"],
            allowed_auxiliary=[
                AuxiliaryElement.TARGET_LINE,
            ],
        )

    def build(
        self,
        data: pl.DataFrame,
        mapping: MappingConfig,
        width: int = 1200,
        height: int = 800,
    ) -> alt.Chart:
        """Build small multiples chart from data and mapping.

        Args:
            data: Input data frame
            mapping: Column to encoding mappings
            width: Chart width in pixels
            height: Chart height in pixels

        Returns:
            Altair small multiples chart
        """
        # Convert Polars DataFrame to Altair-compatible format
        chart_data = self.prepare_data_for_altair(data)

        # Get P31 pattern colors from color strategy
        pattern_colors = self.color_strategy.get_pattern_colors(PatternID.P31)
        series_count = data[mapping.color].n_unique() if mapping.color and mapping.color in data.columns else 1

        # Create base chart - using line with points for time series
        chart = alt.Chart(chart_data).mark_line(
            point=True,
            strokeWidth=pattern_colors.get("stroke_width", 2),
        )

        # Build encodings
        encodings: dict[str, Any] = {}

        # Required encodings
        if mapping.x:
            # Detect if x is temporal or categorical
            x_dtype = str(data[mapping.x].dtype) if mapping.x in data.columns else ""
            x_name_lower = mapping.x.lower()

            is_date_by_dtype = "date" in x_dtype.lower() or "time" in x_dtype.lower()
            is_date_by_name = "date" in x_name_lower or "time" in x_name_lower
            if is_date_by_dtype or is_date_by_name:
                encodings["x"] = alt.X(f"{mapping.x}:T", title=mapping.x)
            elif x_dtype in {"String", "Utf8"}:
                encodings["x"] = alt.X(f"{mapping.x}:N", title=mapping.x)
            else:
                encodings["x"] = alt.X(f"{mapping.x}:Q", title=mapping.x)

        if mapping.y:
            encodings["y"] = alt.Y(f"{mapping.y}:Q", title=mapping.y)

        # Required facet encoding
        if mapping.facet:
            # Determine if facet should be temporal, ordinal, or nominal
            facet_dtype = str(data[mapping.facet].dtype) if mapping.facet in data.columns else ""
            facet_name_lower = mapping.facet.lower()

            if "date" in facet_dtype.lower() or "time" in facet_dtype.lower():
                encodings["facet"] = alt.Facet(
                    f"{mapping.facet}:T",
                    title=mapping.facet,
                    columns=3,  # Arrange in 3 columns for better layout
                    sort="ascending",
                )
            elif "date" in facet_name_lower or "time" in facet_name_lower:
                encodings["facet"] = alt.Facet(f"{mapping.facet}:T", title=mapping.facet, columns=3, sort="ascending")
            else:
                encodings["facet"] = alt.Facet(f"{mapping.facet}:N", title=mapping.facet, columns=3)

        # Optional encodings
        if mapping.color:
            # Apply custom color scheme for small multiples
            # Since P31 doesn't have a custom scheme defined in colors.py,
            # we'll use CHARTELIER_QUAL_10 for consistency
            encodings["color"] = alt.Color(
                f"{mapping.color}:N",
                title=mapping.color,
                scale=alt.Scale(range=list(self.color_strategy.data.CHARTELIER_QUAL_10[:series_count])),
            )

        # Apply encodings
        chart = chart.encode(**encodings)

        # Set size and title - adjust for small multiples
        chart = chart.properties(
            width=width // 3,  # Smaller individual charts for faceting
            height=height // 2,  # Adjust height for multiple rows
            title="Small Multiples",  # Default title
        ).resolve_scale(
            y="independent"  # Allow different y-scales for each facet
        )

        return chart  # type: ignore[no-any-return]  # noqa: RET504 — Altair type inference
