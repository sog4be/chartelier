"""Small multiples template for P31 pattern."""

from typing import Any

import altair as alt
import polars as pl

from chartelier.core.chart_builder.base import BaseTemplate, TemplateSpec
from chartelier.core.enums import AuxiliaryElement
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
                AuxiliaryElement.MEAN_LINE,
                AuxiliaryElement.MEDIAN_LINE,
                AuxiliaryElement.REGRESSION,
                AuxiliaryElement.MOVING_AVG,
                AuxiliaryElement.TARGET_LINE,
                AuxiliaryElement.THRESHOLD,
                AuxiliaryElement.ANNOTATION,
            ],
        )

    def build(
        self,
        data: pl.DataFrame,
        mapping: MappingConfig,
        width: int = 800,
        height: int = 600,
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

        # Create base chart - using line with points for time series
        chart = alt.Chart(chart_data).mark_line(
            point=True,
            strokeWidth=2,
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
            encodings["color"] = alt.Color(f"{mapping.color}:N", title=mapping.color)

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

    def _apply_single_auxiliary(
        self,
        chart: alt.Chart,
        element: AuxiliaryElement,
        data: pl.DataFrame,
        mapping: MappingConfig,
    ) -> alt.Chart | alt.LayerChart:
        """Apply a single auxiliary element specific to small multiples.

        Args:
            chart: Chart to modify
            element: Auxiliary element to apply
            data: Input data frame
            mapping: Column mappings

        Returns:
            Modified chart
        """
        # For small multiples, auxiliary elements should be computed per facet
        if element == AuxiliaryElement.MEAN_LINE and mapping.y and mapping.facet:
            # Calculate mean for each facet group
            mean_data = data.group_by(mapping.facet).agg(pl.col(mapping.y).mean().alias("mean_value"))

            # Create horizontal mean lines for each facet
            rule = (
                alt.Chart(self.prepare_data_for_altair(mean_data))
                .mark_rule(
                    color="red",
                    strokeDash=[5, 5],
                    strokeWidth=2,
                )
                .encode(
                    y="mean_value:Q",
                    facet=alt.Facet(f"{mapping.facet}:N", columns=3),
                    tooltip=[
                        alt.Tooltip(f"{mapping.facet}:N", title="Group"),
                        alt.Tooltip("mean_value:Q", format=".2f", title="Mean"),
                    ],
                )
            )
            return alt.layer(chart, rule)

        if element == AuxiliaryElement.REGRESSION and mapping.x and mapping.y and mapping.facet:
            # Create regression lines for each facet
            regression = (
                alt.Chart(self.prepare_data_for_altair(data))
                .transform_regression(
                    on=mapping.x,
                    regression=mapping.y,
                    groupby=[mapping.facet],  # Separate regression per facet
                )
                .mark_line(strokeDash=[3, 3], strokeWidth=1.5, color="blue")
                .encode(
                    x=f"{mapping.x}:Q",
                    y=f"{mapping.y}:Q",
                    facet=alt.Facet(f"{mapping.facet}:N", columns=3),
                )
            )
            return alt.layer(chart, regression)

        if element == AuxiliaryElement.TARGET_LINE and mapping.y:
            # For small multiples, target line should be horizontal across all facets
            target_value = 0  # Placeholder - would come from auxiliary config
            rule = (
                alt.Chart(pl.DataFrame({"target": [target_value]}))
                .mark_rule(
                    color="green",
                    strokeDash=[10, 5],
                    strokeWidth=2,
                )
                .encode(y="target:Q", tooltip=alt.Tooltip("target:Q", title="Target"))
            )
            return alt.layer(chart, rule)

        if element == AuxiliaryElement.THRESHOLD and mapping.y:
            # Threshold band for acceptable range across all facets
            lower_threshold = -10  # Placeholder values
            upper_threshold = 10
            band = (
                alt.Chart(
                    pl.DataFrame(
                        {
                            "lower": [lower_threshold],
                            "upper": [upper_threshold],
                        }
                    )
                )
                .mark_rect(
                    opacity=0.2,
                    color="gray",
                )
                .encode(
                    y=alt.Y("lower:Q"),
                    y2=alt.Y2("upper:Q"),
                )
            )
            return alt.layer(band, chart)  # Band behind chart

        # Use base implementation for other elements
        return super()._apply_single_auxiliary(chart, element, data, mapping)
