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
        width: int = 1200,
        height: int = 800,
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

    def _apply_single_auxiliary(
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

        if element == AuxiliaryElement.TARGET_LINE and mapping.y:
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
