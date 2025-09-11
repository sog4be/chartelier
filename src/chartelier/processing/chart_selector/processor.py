"""Chart selection component for choosing optimal chart types and auxiliary elements."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel, Field

from chartelier.core.chart_builder.builder import ChartBuilder
from chartelier.core.enums import AuxiliaryElement, PatternID
from chartelier.infra.llm_client import (
    LLMAPIError,
    LLMClient,
    LLMTimeoutError,
    ResponseFormat,
    get_llm_client,
)
from chartelier.infra.logging import get_logger
from chartelier.infra.prompt_template import PromptTemplate

if TYPE_CHECKING:
    from chartelier.core.models import DataMetadata

logger = get_logger(__name__)


class ChartSelection(BaseModel):
    """Result of chart selection process."""

    template_id: str = Field(..., description="Selected template ID")
    auxiliary: list[str] = Field(default_factory=list, description="Selected auxiliary elements")
    reasoning: str | None = Field(None, description="Reasoning for the selection")
    fallback_applied: bool = Field(default=False, description="Whether fallback was used")


class ChartSelector:
    """Selects optimal chart types and auxiliary elements based on pattern and data."""

    # Default model
    DEFAULT_MODEL: ClassVar[str] = "gpt-5-mini"

    # Maximum auxiliary elements
    MAX_AUXILIARY_ELEMENTS: ClassVar[int] = 3

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        chart_builder: ChartBuilder | None = None,
        model: str | None = None,
    ) -> None:
        """Initialize the chart selector.

        Args:
            llm_client: LLM client for chart selection
            chart_builder: Chart builder for template information
            model: Model name to use for selection (default: gpt-5-mini)
        """
        self.llm_client = llm_client or get_llm_client()
        self.chart_builder = chart_builder or ChartBuilder()
        self.logger = get_logger(self.__class__.__name__)
        self.model = model or self.DEFAULT_MODEL

        # Load prompt templates
        template_dir = Path(__file__).parent
        self.chart_prompt = PromptTemplate.from_component(template_dir, "chart_selection")
        self.auxiliary_prompt = PromptTemplate.from_component(template_dir, "auxiliary_selection")

        self.logger.debug(
            "Initialized ChartSelector",
            extra={
                "model": self.model,
            },
        )

    def select_chart(
        self,
        pattern_id: PatternID,
        metadata: DataMetadata,
        query: str | None = None,
    ) -> ChartSelection:
        """Select optimal chart type for the given pattern and data.

        Args:
            pattern_id: Selected pattern ID
            metadata: Data metadata
            query: User's visualization query (optional)

        Returns:
            ChartSelection with chosen template ID
        """
        self.logger.debug(
            "Starting chart selection",
            extra={
                "pattern_id": pattern_id.value,
                "rows": metadata.rows,
                "cols": metadata.cols,
            },
        )

        # Get available charts for the pattern
        available_charts = self.chart_builder.get_available_charts(pattern_id)

        if not available_charts:
            # No charts available for pattern (shouldn't happen with proper setup)
            self.logger.warning(
                "No charts available for pattern",
                extra={"pattern_id": pattern_id.value},
            )
            return self._get_fallback_chart(pattern_id)

        if len(available_charts) == 1:
            # Only one option, use it directly
            return ChartSelection(
                template_id=available_charts[0].template_id,
                auxiliary=[],
                reasoning="Only one chart type available for this pattern",
                fallback_applied=False,
            )

        try:
            # Use LLM to select best chart
            return self._select_with_llm(pattern_id, available_charts, metadata, query)

        except (LLMTimeoutError, LLMAPIError) as e:
            self.logger.warning(
                "LLM selection failed, using fallback",
                extra={
                    "pattern_id": pattern_id.value,
                    "error": str(e),
                },
            )
            return self._get_fallback_chart(pattern_id)

    def select_auxiliary(
        self,
        template_id: str,
        query: str,
        metadata: DataMetadata | None = None,
        auxiliary_config: dict[str, Any] | None = None,
    ) -> list[str]:
        """Select auxiliary elements for the chart.

        Args:
            template_id: Selected template ID
            query: User's visualization query
            metadata: Data metadata (optional)
            auxiliary_config: Configuration for auxiliary elements (optional)

        Returns:
            List of auxiliary element IDs (max 3)
        """
        self.logger.debug(
            "Starting auxiliary selection",
            extra={"template_id": template_id},
        )

        # Get template spec to know allowed auxiliary elements
        template_spec = self.chart_builder.get_template_spec(template_id)
        if not template_spec:
            self.logger.warning(
                "Template spec not found",
                extra={"template_id": template_id},
            )
            return []

        allowed_auxiliary = template_spec.allowed_auxiliary
        if not allowed_auxiliary:
            return []

        try:
            # Use LLM to select auxiliary elements
            return self._select_auxiliary_with_llm(
                template_id,
                allowed_auxiliary,
                query,
                metadata,
                auxiliary_config,
            )

        except (LLMTimeoutError, LLMAPIError) as e:
            self.logger.warning(
                "Auxiliary selection failed, skipping",
                extra={
                    "template_id": template_id,
                    "error": str(e),
                },
            )
            return []

    def _select_with_llm(
        self,
        pattern_id: PatternID,
        available_charts: list[Any],
        metadata: DataMetadata,
        query: str | None,
    ) -> ChartSelection:
        """Select chart using LLM.

        Args:
            pattern_id: Pattern ID
            available_charts: List of available chart specifications
            metadata: Data metadata
            query: User query

        Returns:
            ChartSelection
        """
        # Format chart options
        chart_options = [
            {
                "id": chart.template_id,
                "name": chart.name,
            }
            for chart in available_charts
        ]

        # Format data info
        data_info = self._format_data_info(metadata)

        # Render prompt
        messages = self.chart_prompt.render(
            pattern_id=pattern_id.value,
            chart_options=json.dumps(chart_options, indent=2),
            data_info=data_info,
            query=query or "Visualize the data",
        )

        # Call LLM
        response = self.llm_client.complete(
            messages=messages,
            response_format=ResponseFormat.JSON,
            temperature=0.0,
            model=self.model,
        )

        # Parse response
        try:
            data = json.loads(response.content)
            template_id = data.get("template_id")

            # Validate template_id
            valid_ids = [c.template_id for c in available_charts]
            if template_id not in valid_ids:
                self.logger.warning(
                    "Invalid template_id from LLM",
                    extra={
                        "template_id": template_id,
                        "valid_ids": valid_ids,
                    },
                )
                return self._get_fallback_chart(pattern_id)

            return ChartSelection(
                template_id=template_id,
                auxiliary=[],
                reasoning=data.get("reasoning"),
                fallback_applied=False,
            )

        except (json.JSONDecodeError, KeyError) as e:
            self.logger.warning(
                "Failed to parse LLM response",
                extra={"error": str(e)},
            )
            return self._get_fallback_chart(pattern_id)

    def _select_auxiliary_with_llm(
        self,
        template_id: str,
        allowed_auxiliary: list[AuxiliaryElement],
        query: str,
        metadata: DataMetadata | None,
        auxiliary_config: dict[str, Any] | None,  # noqa: ARG002 — Reserved for future use
    ) -> list[str]:
        """Select auxiliary elements using LLM.

        Args:
            template_id: Template ID
            allowed_auxiliary: Allowed auxiliary elements
            query: User query
            metadata: Data metadata
            auxiliary_config: Auxiliary configuration

        Returns:
            List of auxiliary element IDs
        """
        # Format auxiliary options
        auxiliary_options = [
            {
                "id": elem.value,
                "name": elem.value.replace("_", " ").title(),
                "description": self._get_auxiliary_description(elem),
            }
            for elem in allowed_auxiliary
        ]

        # Format data info if available
        data_info = self._format_data_info(metadata) if metadata else "Data information not available"

        # Render prompt
        messages = self.auxiliary_prompt.render(
            template_id=template_id,
            auxiliary_options=json.dumps(auxiliary_options, indent=2),
            query=query,
            data_info=data_info,
            max_elements=self.MAX_AUXILIARY_ELEMENTS,
        )

        # Call LLM
        response = self.llm_client.complete(
            messages=messages,
            response_format=ResponseFormat.JSON,
            temperature=0.0,
            model=self.model,
        )

        # Parse response
        try:
            data = json.loads(response.content)
            selected = data.get("auxiliary", [])

            # Validate, remove duplicates, and limit to max elements
            valid_ids = [elem.value for elem in allowed_auxiliary]
            selected = [aid for aid in selected if aid in valid_ids]
            # Remove duplicates while preserving order
            seen: set[str] = set()
            unique_selected = []
            for item in selected:
                if item not in seen:
                    seen.add(item)
                    unique_selected.append(item)
            selected = unique_selected
            selected = selected[: self.MAX_AUXILIARY_ELEMENTS]

            self.logger.info(
                "Auxiliary elements selected",
                extra={
                    "template_id": template_id,
                    "selected": selected,
                },
            )

            return selected  # noqa: TRY300 — Return in try block is intentional

        except (json.JSONDecodeError, KeyError) as e:
            self.logger.warning(
                "Failed to parse auxiliary response",
                extra={"error": str(e)},
            )
            return []

    def _get_fallback_chart(self, pattern_id: PatternID) -> ChartSelection:
        """Get fallback chart for a pattern.

        Args:
            pattern_id: Pattern ID

        Returns:
            ChartSelection with default template
        """
        # Use pattern's default template
        default_template = f"{pattern_id.value}_default"

        # Get first available chart if default doesn't exist
        available_charts = self.chart_builder.get_available_charts(pattern_id)
        if available_charts:
            default_template = available_charts[0].template_id

        self.logger.info(
            "Using fallback chart",
            extra={
                "pattern_id": pattern_id.value,
                "template_id": default_template,
            },
        )

        return ChartSelection(
            template_id=default_template,
            auxiliary=[],
            reasoning="Fallback to default chart for pattern",
            fallback_applied=True,
        )

    def _format_data_info(self, metadata: DataMetadata) -> str:
        """Format data metadata for prompt.

        Args:
            metadata: Data metadata

        Returns:
            Formatted string
        """
        lines = [
            f"- Rows: {metadata.rows:,}",
            f"- Columns: {metadata.cols}",
        ]

        # Add column types
        type_counts: dict[str, int] = {}
        for dtype in metadata.dtypes.values():
            type_counts[dtype] = type_counts.get(dtype, 0) + 1

        for dtype, count in type_counts.items():
            lines.append(f"- {dtype.capitalize()} columns: {count}")

        # Add characteristics
        if metadata.has_datetime:
            lines.append("- Contains temporal data")
        if metadata.has_category:
            lines.append("- Contains categorical data")

        return "\n".join(lines)

    def _get_auxiliary_description(self, element: AuxiliaryElement) -> str:
        """Get description for an auxiliary element.

        Args:
            element: Auxiliary element

        Returns:
            Description string
        """
        descriptions = {
            AuxiliaryElement.TARGET_LINE: "Display target or goal reference line",
        }
        return descriptions.get(element, "")
