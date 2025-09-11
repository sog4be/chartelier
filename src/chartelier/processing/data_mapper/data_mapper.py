"""Data mapper for mapping processed data columns to chart template encodings."""

import json
from pathlib import Path
from typing import Any, ClassVar

import polars as pl
from pydantic import ValidationError

from chartelier.core.chart_builder.base import TemplateSpec
from chartelier.core.chart_builder.builder import ChartBuilder
from chartelier.core.errors import DataMappingError
from chartelier.core.models import MappingConfig
from chartelier.infra.llm_client import LLMClient, ResponseFormat, get_llm_client
from chartelier.infra.logging import get_logger
from chartelier.infra.prompt_template import PromptTemplate

logger = get_logger(__name__)


class DataMapper:
    """Maps processed data columns to chart template encodings.

    This component is responsible for:
    1. Validating data types against template requirements
    2. Using LLM to suggest optimal column mappings
    3. Providing deterministic fallback when LLM fails
    4. Ensuring all required encodings are satisfied
    """

    # Encoding type constraints based on Altair/Vega-Lite specifications (Polars types)
    ENCODING_CONSTRAINTS: ClassVar[dict[str, dict[str, list[str]]]] = {
        "x": {
            "temporal": ["Datetime", "Date"],
            "ordinal": ["Int", "UInt"],
            "quantitative": ["Float", "Int", "UInt", "Decimal"],
            "nominal": ["String", "Categorical", "Utf8"],
        },
        "y": {
            "quantitative": ["Float", "Int", "UInt", "Decimal"],
            "ordinal": ["Int", "UInt"],
            "nominal": ["String", "Categorical", "Utf8"],
        },
        "color": {
            "nominal": ["String", "Categorical", "Utf8"],
            "ordinal": ["Int", "UInt"],
            "quantitative": ["Float", "Decimal"],
        },
        "size": {
            "quantitative": ["Float", "Int", "UInt", "Decimal"],
        },
        "facet": {
            "nominal": ["String", "Categorical", "Utf8"],
            "ordinal": ["Int", "UInt"],
        },
        "row": {
            "nominal": ["String", "Categorical", "Utf8"],
            "ordinal": ["Int", "UInt"],
        },
        "column": {
            "nominal": ["String", "Categorical", "Utf8"],
            "ordinal": ["Int", "UInt"],
        },
    }

    def __init__(
        self,
        chart_builder: ChartBuilder | None = None,
        llm_client: LLMClient | None = None,
        model: str = "gpt-3.5-turbo",
        prompt_version: str = "v0.1.0",
    ) -> None:
        """Initialize the data mapper.

        Args:
            chart_builder: Optional ChartBuilder instance for template spec retrieval
            llm_client: Optional LLM client for custom configuration
            model: LLM model to use for mapping suggestions
            prompt_version: Version of the prompt template to use
        """
        self.chart_builder = chart_builder or ChartBuilder()
        self.logger = logger
        self.llm_client = llm_client or get_llm_client()
        self.model = model

        # Load prompt template
        template_dir = Path(__file__).parent
        self.prompt_template = PromptTemplate.from_component(template_dir, prompt_version)

        self.logger.debug(
            "Initialized DataMapper",
            extra={
                "model": self.model,
                "prompt_version": prompt_version,
            },
        )

    def map(
        self,
        data: pl.DataFrame,
        template_id: str,
        query: str,
        auxiliary_config: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> MappingConfig:
        """Map data columns to template encodings.

        Args:
            data: Processed data frame
            template_id: Selected template ID
            query: User's original query for context
            auxiliary_config: Optional auxiliary element configuration

        Returns:
            MappingConfig with column to encoding mappings

        Raises:
            DataMappingError: If required encodings cannot be satisfied
        """
        self.logger.info(
            "Starting data mapping",
            extra={
                "template_id": template_id,
                "columns": list(data.columns),
                "shape": data.shape,
            },
        )

        # Get template specification
        template_spec = self.chart_builder.get_template_spec(template_id)
        if not template_spec:
            msg = f"Template '{template_id}' not found"
            raise DataMappingError(
                message=msg,
            )

        # Extract column metadata
        column_info = self._analyze_columns(data)

        # Try LLM-based mapping first
        try:
            mapping = self._map_with_llm(
                column_info=column_info,
                template_spec=template_spec,
                query=query,
            )
            self.logger.info("LLM mapping successful")
        except Exception as e:  # noqa: BLE001
            self.logger.warning("LLM mapping failed, using fallback: %s", e)
            mapping = self._deterministic_fallback(
                column_info=column_info,
                template_spec=template_spec,
            )

        # Validate required encodings are satisfied
        is_valid, missing = template_spec.validate_mapping(mapping)
        if not is_valid:
            msg = f"Required encodings not satisfied: {missing}"
            raise DataMappingError(
                message=msg,
                required_fields=missing,
                available_columns=list(data.columns),
            )

        # Type validation and casting
        mapping = self._validate_and_cast_types(data, mapping, template_spec)

        self.logger.info(
            "Data mapping completed",
            extra={"mapping": mapping.model_dump(exclude_none=True)},
        )

        return mapping

    def _analyze_columns(self, data: pl.DataFrame) -> dict[str, dict[str, Any]]:
        """Analyze column characteristics for mapping.

        Args:
            data: Input data frame

        Returns:
            Dictionary of column name to metadata
        """
        column_info = {}

        for col in data.columns:
            dtype = str(data[col].dtype)

            # Determine if column has temporal characteristics
            # Polars uses Datetime, Date types
            is_temporal = "Datetime" in dtype or dtype == "Date"

            # Check if numeric (Polars uses capitalized type names)
            is_numeric = any(t in dtype for t in ["Int", "UInt", "Float", "Decimal"])

            # Check cardinality for categorical detection
            n_unique = data[col].n_unique()
            cardinality_ratio = n_unique / len(data) if len(data) > 0 else 0
            is_categorical = dtype in ["String", "Categorical", "Utf8", "Object"] or (
                is_numeric and n_unique < 20 and cardinality_ratio < 0.05
            )

            # Sample values (excluding nulls)
            non_null = data[col].drop_nulls()
            sample_values = non_null.head(5).to_list() if len(non_null) > 0 else []

            column_info[col] = {
                "dtype": dtype,
                "is_temporal": is_temporal,
                "is_numeric": is_numeric,
                "is_categorical": is_categorical,
                "n_unique": n_unique,
                "cardinality_ratio": cardinality_ratio,
                "has_nulls": data[col].null_count() > 0,
                "sample_values": sample_values,
            }

        return column_info

    def _map_with_llm(
        self,
        column_info: dict[str, dict[str, Any]],
        template_spec: TemplateSpec,
        query: str,
    ) -> MappingConfig:
        """Use LLM to suggest optimal column mappings.

        Args:
            column_info: Column metadata
            template_spec: Template specification
            query: User's query for context

        Returns:
            MappingConfig based on LLM suggestion
        """
        # Prepare column descriptions
        column_descriptions = []
        for col_name, info in column_info.items():
            desc = f"- {col_name}: type={info['dtype']}"
            if info["is_temporal"]:
                desc += " (temporal)"
            elif info["is_categorical"]:
                desc += f" (categorical, {info['n_unique']} unique)"
            elif info["is_numeric"]:
                desc += " (numeric)"
            column_descriptions.append(desc)

        # Prepare template variables
        template_vars = {
            "query": query,
            "column_descriptions": "\n".join(column_descriptions),
            "required_encodings": str(template_spec.required_encodings),
            "optional_encodings": str(template_spec.optional_encodings),
        }

        # Generate prompt from template
        messages = self.prompt_template.render(**template_vars)

        try:
            # Use LLMClient for the API call
            response = self.llm_client.complete(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=500,
                response_format=ResponseFormat.JSON,
            )

            mapping_dict = json.loads(response.content)

            # Filter out any invalid column names
            valid_columns = set(column_info.keys())
            filtered_mapping = {k: v for k, v in mapping_dict.items() if v in valid_columns}

            return MappingConfig(**filtered_mapping)

        except (json.JSONDecodeError, ValidationError, KeyError) as e:
            self.logger.warning("Failed to parse LLM response: %s", e)
            raise

    def _deterministic_fallback(  # noqa: C901, PLR0912
        self,
        column_info: dict[str, dict[str, Any]],
        template_spec: TemplateSpec,
    ) -> MappingConfig:
        """Provide deterministic mapping based on data types.

        Args:
            column_info: Column metadata
            template_spec: Template specification

        Returns:
            MappingConfig based on heuristics
        """
        mapping = {}
        used_columns = set()

        # Sort columns by name for deterministic behavior
        sorted_columns = sorted(column_info.items())

        # Map required encodings
        for encoding in template_spec.required_encodings:
            if encoding == "x":
                # Prefer temporal, then numeric, then categorical
                for col_name, info in sorted_columns:
                    if col_name not in used_columns and info["is_temporal"]:
                        mapping["x"] = col_name
                        used_columns.add(col_name)
                        break
                if "x" not in mapping:
                    for col_name, info in sorted_columns:
                        if col_name not in used_columns and info["is_numeric"]:
                            mapping["x"] = col_name
                            used_columns.add(col_name)
                            break
                if "x" not in mapping and sorted_columns:
                    # Use first available column
                    col_name = sorted_columns[0][0]
                    if col_name not in used_columns:
                        mapping["x"] = col_name
                        used_columns.add(col_name)

            elif encoding == "y":
                # Prefer numeric columns
                for col_name, info in sorted_columns:
                    if col_name not in used_columns and info["is_numeric"]:
                        mapping["y"] = col_name
                        used_columns.add(col_name)
                        break
                if "y" not in mapping and sorted_columns:
                    # Use first available column
                    for col_name, _ in sorted_columns:
                        if col_name not in used_columns:
                            mapping["y"] = col_name
                            used_columns.add(col_name)
                            break

            elif encoding == "color":
                # Prefer categorical columns
                for col_name, info in sorted_columns:
                    if col_name not in used_columns and info["is_categorical"]:
                        mapping["color"] = col_name
                        used_columns.add(col_name)
                        break

        # Map optional encodings if columns available
        for encoding in template_spec.optional_encodings:
            if encoding == "color" and "color" not in mapping:
                for col_name, info in sorted_columns:
                    if col_name not in used_columns and info["is_categorical"]:
                        mapping["color"] = col_name
                        used_columns.add(col_name)
                        break
            elif encoding == "size" and "size" not in mapping:
                for col_name, info in sorted_columns:
                    if col_name not in used_columns and info["is_numeric"]:
                        mapping["size"] = col_name
                        used_columns.add(col_name)
                        break

        return MappingConfig(**mapping)

    def _validate_and_cast_types(
        self,
        data: pl.DataFrame,
        mapping: MappingConfig,
        template_spec: TemplateSpec,  # noqa: ARG002
    ) -> MappingConfig:
        """Validate and attempt to cast column types to match encoding requirements.

        Args:
            data: Input data frame
            mapping: Current mapping configuration
            template_spec: Template specification

        Returns:
            Validated MappingConfig
        """
        mapping_dict = mapping.model_dump(exclude_none=True)

        for encoding, column in mapping_dict.items():
            if column not in data.columns:
                continue

            dtype = str(data[column].dtype)

            # Check if type is compatible with encoding
            if encoding in self.ENCODING_CONSTRAINTS:
                # Check all possible encoding types for this field
                is_compatible = False
                for allowed_types in self.ENCODING_CONSTRAINTS[encoding].values():
                    if any(dtype.startswith(t) for t in allowed_types):
                        is_compatible = True
                        break

                if not is_compatible:
                    self.logger.warning(
                        "Type mismatch for %s=%s (dtype=%s), will attempt casting",
                        encoding,
                        column,
                        dtype,
                    )
                    # Type casting would be handled by the processing layer if needed

        return mapping

    def _generate_mapping_hint(
        self,
        column_info: dict[str, dict[str, Any]],
        missing: list[str],
    ) -> str:
        """Generate helpful hint for mapping errors.

        Args:
            column_info: Column metadata
            missing: List of missing required encodings

        Returns:
            Hint message
        """
        hints = []

        for encoding in missing:
            if encoding == "x":
                temporal_cols = [col for col, info in column_info.items() if info["is_temporal"]]
                if temporal_cols:
                    hints.append(f"For {encoding}, consider using temporal column: {temporal_cols[0]}")
                else:
                    numeric_cols = [col for col, info in column_info.items() if info["is_numeric"]]
                    if numeric_cols:
                        hints.append(f"For {encoding}, consider using numeric column: {numeric_cols[0]}")

            elif encoding == "y":
                numeric_cols = [col for col, info in column_info.items() if info["is_numeric"]]
                if numeric_cols:
                    hints.append(f"For {encoding}, consider using numeric column: {numeric_cols[0]}")

        if hints:
            return " ".join(hints)
        return f"Required encodings {missing} could not be mapped. Check if your data has appropriate columns."
