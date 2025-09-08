"""Base template abstract class for chart generation."""

from abc import ABC, abstractmethod
from typing import Any

import altair as alt
import polars as pl

from chartelier.core.enums import AuxiliaryElement
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
        width: int = 800,
        height: int = 600,
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

    def apply_auxiliary(
        self,
        chart: alt.Chart,
        auxiliary: list[AuxiliaryElement],
        data: pl.DataFrame,
        mapping: MappingConfig,
    ) -> alt.Chart | alt.LayerChart:
        """Apply auxiliary elements to chart.

        Args:
            chart: Base chart object
            auxiliary: List of auxiliary elements to apply
            data: Input data frame
            mapping: Column mappings

        Returns:
            Chart with auxiliary elements applied
        """
        # Filter to only allowed auxiliary elements
        allowed = [aux for aux in auxiliary if aux in self.spec.allowed_auxiliary]

        for element in allowed[:3]:  # Max 3 auxiliary elements
            chart = self._apply_single_auxiliary(chart, element, data, mapping)  # type: ignore[assignment]

        return chart

    def _apply_single_auxiliary(
        self,
        chart: alt.Chart,
        element: AuxiliaryElement,
        data: pl.DataFrame,
        mapping: MappingConfig,
    ) -> alt.Chart | alt.LayerChart:
        """Apply a single auxiliary element.

        Args:
            chart: Chart to modify
            element: Auxiliary element to apply
            data: Input data frame
            mapping: Column mappings

        Returns:
            Modified chart
        """
        # Default implementation - subclasses can override
        if element == AuxiliaryElement.MEAN_LINE and mapping.y:
            mean_val = data[mapping.y].mean()
            if mean_val is not None:
                rule = (
                    alt.Chart(pl.DataFrame({"mean": [mean_val]}))
                    .mark_rule(
                        color="red",
                        strokeDash=[5, 5],
                    )
                    .encode(y="mean:Q")
                )
                # Use alt.layer for proper composition
                return alt.layer(chart, rule)

        elif element == AuxiliaryElement.REGRESSION and mapping.x and mapping.y:
            # Create regression layer from base data
            regression = (
                alt.Chart(self.prepare_data_for_altair(data))
                .transform_regression(
                    on=mapping.x,
                    regression=mapping.y,
                )
                .mark_line(
                    color="blue",
                    strokeDash=[3, 3],
                )
                .encode(
                    x=f"{mapping.x}:Q",
                    y=f"{mapping.y}:Q",
                )
            )
            # Use alt.layer for proper composition
            return alt.layer(chart, regression)

        return chart

    def prepare_data_for_altair(self, data: pl.DataFrame) -> dict[str, Any]:
        """Convert Polars DataFrame to Altair-compatible format.

        Args:
            data: Polars DataFrame

        Returns:
            Dictionary in records format for Altair
        """
        # Convert to records format (list of dicts)
        return {"values": data.to_dicts()}
