"""Pattern selection component for visualization pattern classification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field

from chartelier.core.enums import ErrorCode, PatternID
from chartelier.core.errors import ChartelierError
from chartelier.core.models import DataMetadata, ErrorDetail
from chartelier.infra.llm_client import (
    LLMClient,
    LLMTimeoutError,
    ResponseFormat,
    get_llm_client,
)
from chartelier.infra.logging import get_logger
from chartelier.infra.prompt_template import PromptTemplate

logger = get_logger(__name__)


class PatternSelectionError(ChartelierError):
    """Raised when pattern selection fails."""

    def __init__(self, reason: str, hint: str | None = None) -> None:
        """Initialize pattern selection error.

        Args:
            reason: Reason for failure
            hint: Hint for resolution
        """
        super().__init__(
            code=ErrorCode.E422_UNPROCESSABLE,
            message=f"Failed to select visualization pattern: {reason}",
            hint=hint or "Try describing what you want to compare, track, or understand about your data",
            details=[ErrorDetail(field="pattern_selection", reason=reason)],
        )


class PatternSelection(BaseModel):
    """Result of pattern selection process."""

    pattern_id: PatternID = Field(..., description="Selected pattern ID (P01-P32)")
    reasoning: str | None = Field(None, description="Reasoning for the selection")
    confidence: float | None = Field(None, description="Confidence score (0-1)")


class PatternSelector:
    """Selects visualization patterns based on data and query."""

    # Model to prompt version mapping
    MODEL_PROMPT_VERSIONS: ClassVar[dict[str, str]] = {
        "gpt-4o-mini": "v0.1.0",  # Recommended version for gpt-4o-mini
        # Add more model-specific versions as needed
    }

    # Default prompt version for models not in the mapping
    DEFAULT_PROMPT_VERSION: ClassVar[str] = "v0.1.0"

    # Default model to use
    DEFAULT_MODEL: ClassVar[str] = "gpt-4o-mini"

    def __init__(self, llm_client: LLMClient | None = None, model: str | None = None) -> None:
        """Initialize the pattern selector.

        Args:
            llm_client: LLM client for pattern classification
            model: Model name to use for pattern classification (default: gpt-4o-mini)
        """
        self.llm_client = llm_client or get_llm_client()
        self.logger = get_logger(self.__class__.__name__)
        self.model = model or self.DEFAULT_MODEL

        # Determine prompt version based on model
        prompt_version = self.MODEL_PROMPT_VERSIONS.get(self.model, self.DEFAULT_PROMPT_VERSION)

        # Load prompt template with determined version
        self.prompt_template = PromptTemplate.from_component(Path(__file__).parent, prompt_version)

        self.logger.debug(
            "Initialized PatternSelector",
            extra={
                "model": self.model,
                "prompt_version": prompt_version,
            },
        )

    def select(self, metadata: DataMetadata, query: str) -> PatternSelection:
        """Select a visualization pattern based on data and query.

        Args:
            metadata: Data metadata including column types and statistics
            query: User's visualization query

        Returns:
            PatternSelection with chosen pattern ID

        Raises:
            PatternSelectionError: If pattern selection fails
        """
        self.logger.debug(
            "Starting pattern selection",
            extra={
                "rows": metadata.rows,
                "cols": metadata.cols,
                "has_datetime": metadata.has_datetime,
                "has_category": metadata.has_category,
            },
        )

        try:
            # Prepare template variables
            data_info = self._format_data_info(metadata)

            # Render prompt using template
            messages = self.prompt_template.render(
                query=query,
                data_info=data_info,
            )

            response = self.llm_client.complete(
                messages=messages,
                response_format=ResponseFormat.JSON,
                temperature=0.0,  # Deterministic selection
                model=self.model,  # Use configured model
            )

            # Parse and validate response
            return self._parse_response(response.content)

        except LLMTimeoutError as e:
            self.logger.warning(
                "LLM timeout during pattern selection",
                extra={"timeout": e.details[0].reason if e.details else "unknown"},
            )
            raise PatternSelectionError(
                reason="Pattern selection timed out",
                hint="The request took too long. Try simplifying your query or try again.",
            ) from e

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.warning(
                "Failed to parse LLM response",
                extra={"error": str(e)},
            )
            raise PatternSelectionError(
                reason=f"Invalid response format: {e}",
                hint="The system couldn't interpret the analysis. Please rephrase your query.",
            ) from e

        except Exception as e:
            self.logger.exception("Unexpected error in pattern selection")
            raise PatternSelectionError(
                reason=f"Unexpected error: {e}",
                hint="An unexpected error occurred. Please try again.",
            ) from e

    def _format_data_info(self, metadata: DataMetadata) -> str:
        """Format data metadata into readable description.

        Args:
            metadata: Data metadata

        Returns:
            Formatted data description
        """
        lines = [
            f"- Rows: {metadata.rows:,}",
            f"- Columns: {metadata.cols}",
        ]

        # Add column type information
        type_counts: dict[str, int] = {}
        for dtype in metadata.dtypes.values():
            type_counts[dtype] = type_counts.get(dtype, 0) + 1

        for dtype, count in type_counts.items():
            lines.append(f"- {dtype.capitalize()} columns: {count}")

        # Add special characteristics
        if metadata.has_datetime:
            lines.append("- Contains datetime/temporal data")
        if metadata.has_category:
            lines.append("- Contains categorical data")

        # Add column names with types (limit to first 10)
        lines.append("\nColumn details (first 10):")
        for i, (col, dtype) in enumerate(metadata.dtypes.items()):
            if i >= 10:
                lines.append(f"  ... and {len(metadata.dtypes) - 10} more columns")
                break
            null_pct = metadata.null_ratio.get(col, 0) * 100
            lines.append(f"  - {col}: {dtype} (null: {null_pct:.1f}%)")

        return "\n".join(lines)

    def _parse_response(self, response_text: str) -> PatternSelection:
        """Parse LLM response into PatternSelection.

        Args:
            response_text: JSON response from LLM

        Returns:
            PatternSelection object

        Raises:
            json.JSONDecodeError: If response is not valid JSON
            ValueError: If pattern_id is invalid
        """
        data = json.loads(response_text)

        # Validate pattern_id
        pattern_id_str = data.get("pattern_id", "").upper()
        if pattern_id_str not in [p.value for p in PatternID]:
            valid_patterns = ", ".join([p.value for p in PatternID])
            error_msg = f"Invalid pattern_id: {pattern_id_str}. Must be one of: {valid_patterns}"
            raise ValueError(error_msg)

        # Get the PatternID enum
        pattern_id = PatternID(pattern_id_str)

        # Extract optional fields
        reasoning = data.get("reasoning")
        confidence = data.get("confidence")

        # Validate confidence if present
        if confidence is not None:
            try:
                confidence = float(confidence)
                if not 0 <= confidence <= 1:
                    self.logger.warning(
                        "Confidence score out of range, ignoring",
                        extra={"confidence": confidence},
                    )
                    confidence = None
            except (TypeError, ValueError):
                self.logger.warning(
                    "Invalid confidence score, ignoring",
                    extra={"confidence": data.get("confidence")},
                )
                confidence = None

        self.logger.info(
            "Pattern selected successfully",
            extra={
                "pattern_id": pattern_id.value,
                "confidence": confidence,
            },
        )

        return PatternSelection(
            pattern_id=pattern_id,
            reasoning=reasoning,
            confidence=confidence,
        )
