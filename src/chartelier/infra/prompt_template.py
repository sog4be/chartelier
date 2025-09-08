"""Prompt template utility for managing LLM prompts with Jinja2."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import toml
from jinja2 import Environment, StrictUndefined, Template, TemplateError, UndefinedError, meta
from pydantic import BaseModel, Field, field_validator

from chartelier.infra.llm_client import LLMMessage
from chartelier.infra.logging import get_logger

logger = get_logger(__name__)


class PromptMessage(BaseModel):
    """Definition of a single prompt message."""

    role: str = Field(..., description="Message role (system|user|assistant)")
    content: str = Field(..., description="Jinja2 template string for message content")
    do_strip: bool = Field(default=True, description="Whether to strip whitespace from rendered content")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate that role is one of the allowed values."""
        allowed_roles = {"system", "user", "assistant", "developer"}
        if v not in allowed_roles:
            msg = f"Role must be one of {allowed_roles}, got: {v}"
            raise ValueError(msg)
        return v


class PromptConfig(BaseModel):
    """Complete prompt configuration from TOML file."""

    version: str = Field(..., description="Prompt template version")
    messages: list[PromptMessage] = Field(..., description="List of prompt messages")


class PromptTemplateError(Exception):
    """Base exception for prompt template errors."""


class PromptTemplate:
    """Utility for managing prompt templates with Jinja2 rendering.

    This class loads prompt templates from TOML files and renders them
    with provided variables using Jinja2.

    Example:
        >>> template = PromptTemplate.from_component(
        ...     Path(__file__).parent,
        ...     "pattern_selection"
        ... )
        >>> messages = template.render(
        ...     query="Show sales trend",
        ...     data_info="1000 rows, 5 columns"
        ... )
    """

    def __init__(self, prompt_path: str | Path) -> None:
        """Initialize prompt template from TOML file.

        Args:
            prompt_path: Path to the TOML file containing prompt configuration

        Raises:
            FileNotFoundError: If the TOML file doesn't exist
            PromptTemplateError: If the TOML file is invalid
        """
        self.prompt_path = Path(prompt_path)
        if not self.prompt_path.exists():
            msg = f"Prompt template file not found: {self.prompt_path}"
            raise FileNotFoundError(msg)

        self.config = self._load_config()

        # Initialize Jinja2 environment with strict undefined to catch missing variables
        # Note: autoescape=False is safe here as we're generating LLM prompts, not HTML
        self.env = Environment(
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,  # noqa: S701 - Safe for LLM prompts, not HTML
        )

        # Pre-compile templates for better performance
        self._compiled_templates: list[tuple[PromptMessage, Template]] = []
        for message in self.config.messages:
            try:
                template = self.env.from_string(message.content)
                self._compiled_templates.append((message, template))
            except TemplateError as e:
                msg = f"Invalid Jinja2 template in {self.prompt_path}: {e}"
                raise PromptTemplateError(msg) from e

        logger.debug(
            "Loaded prompt template",
            extra={
                "path": str(self.prompt_path),
                "version": self.config.version,
                "message_count": len(self.config.messages),
            },
        )

    def _load_config(self) -> PromptConfig:
        """Load and parse TOML configuration file.

        Returns:
            Parsed prompt configuration

        Raises:
            PromptTemplateError: If TOML parsing or validation fails
        """
        try:
            with self.prompt_path.open(encoding="utf-8") as f:
                data = toml.load(f)
        except toml.TomlDecodeError as e:
            msg = f"Invalid TOML in {self.prompt_path}: {e}"
            raise PromptTemplateError(msg) from e
        except Exception as e:
            msg = f"Error reading {self.prompt_path}: {e}"
            raise PromptTemplateError(msg) from e

        try:
            return PromptConfig(**data)
        except Exception as e:
            msg = f"Invalid prompt configuration in {self.prompt_path}: {e}"
            raise PromptTemplateError(msg) from e

    @classmethod
    def from_component(cls, component_path: Path, prompt_name: str) -> PromptTemplate:
        """Create PromptTemplate from component directory and prompt name.

        This is a convenience method that constructs the path to the prompt
        file based on the component's directory structure.

        Args:
            component_path: Path to the component directory (usually Path(__file__).parent)
            prompt_name: Name of the prompt file without extension

        Returns:
            PromptTemplate instance

        Example:
            >>> template = PromptTemplate.from_component(
            ...     Path(__file__).parent,
            ...     "pattern_selection"
            ... )
        """
        prompt_path = component_path / "prompts" / f"{prompt_name}.toml"
        return cls(prompt_path)

    def render(self, **kwargs: Any) -> list[LLMMessage]:  # noqa: ANN401
        """Render the prompt template with provided variables.

        Args:
            **kwargs: Variables to be used in the Jinja2 templates

        Returns:
            List of rendered LLMMessage objects

        Raises:
            UndefinedError: If a required template variable is missing
            TemplateError: If template rendering fails
        """
        messages = []

        for message, template in self._compiled_templates:
            try:
                content = template.render(**kwargs)
            except UndefinedError as e:
                msg = f"Missing required variable for prompt template: {e}. Available variables: {list(kwargs.keys())}"
                raise UndefinedError(msg) from e
            except TemplateError as e:
                msg = f"Error rendering prompt template: {e}"
                raise TemplateError(msg) from e

            # Strip whitespace if configured
            if message.do_strip:
                content = content.strip()

            messages.append(LLMMessage(role=message.role, content=content))

        logger.debug(
            "Rendered prompt template",
            extra={
                "template": str(self.prompt_path.name),
                "message_count": len(messages),
                "variables": list(kwargs.keys()),
            },
        )

        return messages

    def get_required_variables(self) -> set[str]:
        """Get set of variable names used in the templates.

        This uses Jinja2's meta API to find undeclared variables.

        Returns:
            Set of variable names required by the templates
        """
        all_variables = set()
        for message in self.config.messages:
            ast = self.env.parse(message.content)
            variables = meta.find_undeclared_variables(ast)  # type: ignore[no-untyped-call]
            all_variables.update(variables)

        return all_variables

    @property
    def version(self) -> str:
        """Get the version of the prompt template."""
        return self.config.version

    def __repr__(self) -> str:
        """String representation of PromptTemplate."""
        return f"PromptTemplate(path={self.prompt_path}, version={self.config.version})"
