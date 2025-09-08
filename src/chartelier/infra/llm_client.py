"""LLM Client implementation for interacting with language models."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from chartelier.core.enums import ErrorCode
from chartelier.core.errors import ChartelierError
from chartelier.core.models import ErrorDetail
from chartelier.infra.logging import get_logger

logger = get_logger(__name__)


class ResponseFormat(str, Enum):
    """Supported response formats for LLM."""

    TEXT = "text"
    JSON = "json"


class LLMMessage(BaseModel):
    """Message structure for LLM communication."""

    role: str = Field(..., description="Message role (system, user, assistant)")
    content: str = Field(..., description="Message content")


class LLMResponse(BaseModel):
    """Response structure from LLM."""

    content: str = Field(..., description="Response content")
    model: str | None = Field(None, description="Model used for generation")
    usage: dict[str, Any] | None = Field(None, description="Usage statistics")
    finish_reason: str | None = Field(None, description="Reason for completion")


class LLMSettings(BaseSettings):
    """Settings for LLM client configuration."""

    model_config = SettingsConfigDict(
        env_prefix="CHARTELIER_LLM_",
        env_file=".env",
        extra="ignore",
    )

    api_key: str | None = Field(None, description="API key for LLM service")
    model: str = Field("gpt-3.5-turbo", description="Default model to use")
    timeout: int = Field(10, description="Request timeout in seconds")
    max_retries: int = Field(3, description="Maximum number of retries")
    retry_delay: float = Field(1.0, description="Initial retry delay in seconds")
    temperature: float = Field(0.0, description="Temperature for generation")
    max_tokens: int | None = Field(None, description="Maximum tokens to generate")
    disable_llm: bool = Field(default=False, description="Disable LLM calls (use mock)")


class LLMTimeoutError(ChartelierError):
    """Raised when LLM request times out."""

    def __init__(self, timeout: int, model: str | None = None) -> None:
        """Initialize LLM timeout error."""
        super().__init__(
            code=ErrorCode.E408_TIMEOUT,
            message=f"LLM request timed out after {timeout} seconds",
            hint="Consider increasing the timeout or simplifying the request",
            details=[
                ErrorDetail(field="timeout_seconds", reason=str(timeout)),
                ErrorDetail(field="model", reason=model or "unknown"),
            ],
        )


class LLMAPIError(ChartelierError):
    """Raised when LLM API returns an error."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Initialize LLM API error."""
        details = [ErrorDetail(field="api_error", reason=message)]
        if status_code:
            details.append(ErrorDetail(field="status_code", reason=str(status_code)))

        super().__init__(
            code=ErrorCode.E424_UPSTREAM_LLM,
            message=f"LLM API error: {message}",
            hint="Check API key and service status",
            details=details,
        )


class LLMClient(Protocol):
    """Protocol for LLM client implementations."""

    def complete(
        self,
        messages: list[LLMMessage],
        *,
        response_format: ResponseFormat = ResponseFormat.TEXT,
        **kwargs: Any,  # noqa: ANN401 — LLM libraries require flexible kwargs
    ) -> LLMResponse:
        """Complete a chat conversation.

        Args:
            messages: List of messages in the conversation
            response_format: Expected response format
            **kwargs: Additional parameters for the LLM

        Returns:
            LLM response

        Raises:
            LLMTimeoutError: If the request times out
            LLMAPIError: If the API returns an error
        """
        ...


class BaseLLMClient(ABC):
    """Base class for LLM client implementations."""

    def __init__(self, settings: LLMSettings | None = None) -> None:
        """Initialize the LLM client.

        Args:
            settings: LLM settings, defaults to environment variables
        """
        self.settings = settings or LLMSettings()
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    def complete(
        self,
        messages: list[LLMMessage],
        *,
        response_format: ResponseFormat = ResponseFormat.TEXT,
        **kwargs: Any,  # noqa: ANN401 — LLM libraries require flexible kwargs
    ) -> LLMResponse:
        """Complete a chat conversation."""
        ...

    def _retry_with_backoff(
        self,
        func: Any,  # noqa: ANN401 — Generic retry function
        *args: Any,  # noqa: ANN401 — Generic retry function
        **kwargs: Any,  # noqa: ANN401 — Generic retry function
    ) -> Any:  # noqa: ANN401 — Generic retry function
        """Execute function with exponential backoff retry.

        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Function result

        Raises:
            Exception: If all retries fail
        """
        last_exception = None
        delay = self.settings.retry_delay

        for attempt in range(self.settings.max_retries):
            try:
                return func(*args, **kwargs)
            except (LLMTimeoutError, LLMAPIError) as e:
                last_exception = e
                if attempt < self.settings.max_retries - 1:
                    self.logger.warning(
                        "LLM request failed, retrying",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": self.settings.max_retries,
                            "delay": delay,
                            "error": str(e),
                        },
                    )
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    self.logger.exception(
                        "LLM request failed after all retries",
                        extra={
                            "attempts": self.settings.max_retries,
                            "error": str(e),
                        },
                    )

        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected retry failure")  # Should not reach here


class LiteLLMClient(BaseLLMClient):
    """LiteLLM-based client implementation."""

    def __init__(self, settings: LLMSettings | None = None) -> None:
        """Initialize LiteLLM client."""
        super().__init__(settings)
        self._client = None
        self._ensure_litellm()

    def _ensure_litellm(self) -> None:
        """Ensure litellm is available."""
        try:
            import litellm  # noqa: PLC0415 — Lazy import for optional dependency

            self._litellm = litellm
        except ImportError as e:
            msg = "litellm is not installed. Install with: pip install chartelier[litellm]"
            raise ImportError(msg) from e

    def complete(  # noqa: C901 — Exception handling requires complexity
        self,
        messages: list[LLMMessage],
        *,
        response_format: ResponseFormat = ResponseFormat.TEXT,
        **kwargs: Any,  # noqa: ANN401 — LiteLLM requires flexible kwargs
    ) -> LLMResponse:
        """Complete a chat conversation using LiteLLM.

        Args:
            messages: List of messages in the conversation
            response_format: Expected response format
            **kwargs: Additional parameters for the LLM

        Returns:
            LLM response
        """
        # Convert messages to dict format
        message_dicts = [{"role": msg.role, "content": msg.content} for msg in messages]

        # Prepare kwargs
        request_kwargs = {
            "model": kwargs.get("model", self.settings.model),
            "messages": message_dicts,
            "temperature": kwargs.get("temperature", self.settings.temperature),
            "timeout": self.settings.timeout,
        }

        if self.settings.max_tokens:
            request_kwargs["max_tokens"] = self.settings.max_tokens

        if self.settings.api_key:
            request_kwargs["api_key"] = self.settings.api_key

        if response_format == ResponseFormat.JSON:
            request_kwargs["response_format"] = {"type": "json_object"}

        # Log request
        self.logger.debug(
            "Sending LLM request",
            extra={
                "model": request_kwargs["model"],
                "message_count": len(messages),
                "response_format": response_format.value,
            },
        )

        def _call_litellm(**kwargs: Any) -> Any:  # noqa: ANN401 — Internal wrapper
            """Inner function that wraps litellm call with exception translation."""
            try:
                return self._litellm.completion(**kwargs)
            except Exception as e:
                # Check exception type by name or by isinstance if possible
                exception_name = e.__class__.__name__

                # Check if it's a litellm Timeout exception
                if exception_name in ("Timeout", "MockTimeout"):
                    raise LLMTimeoutError(
                        timeout=self.settings.timeout,
                        model=kwargs.get("model", "unknown"),
                    ) from e
                # Check if it's a litellm APIError exception
                if exception_name in ("APIError", "MockAPIError"):
                    raise LLMAPIError(
                        message=str(e),
                        status_code=getattr(e, "status_code", None),
                    ) from e
                # Try isinstance checks if the attributes are actual types
                if hasattr(self._litellm, "Timeout"):
                    try:
                        if isinstance(e, self._litellm.Timeout):
                            raise LLMTimeoutError(
                                timeout=self.settings.timeout,
                                model=kwargs.get("model", "unknown"),
                            ) from e
                    except TypeError:
                        # isinstance failed, continue
                        pass

                    try:
                        if hasattr(self._litellm, "APIError") and isinstance(e, self._litellm.APIError):
                            raise LLMAPIError(
                                message=str(e),
                                status_code=getattr(e, "status_code", None),
                            ) from e
                    except TypeError:
                        # isinstance failed, continue
                        pass

                # Re-raise other exceptions
                raise

        try:
            # Execute with retry
            response = self._retry_with_backoff(
                _call_litellm,
                **request_kwargs,
            )

            # Extract response
            content = response.choices[0].message.content

            return LLMResponse(
                content=content,
                model=response.model,
                usage=response.usage.model_dump() if response.usage else None,
                finish_reason=response.choices[0].finish_reason,
            )

        except (LLMTimeoutError, LLMAPIError):
            # Re-raise our errors as-is
            raise
        except Exception as e:
            self.logger.exception("Unexpected error in LLM request")
            raise LLMAPIError(message=f"Unexpected error: {e}") from e


class MockLLMClient(BaseLLMClient):
    """Mock LLM client for testing."""

    def __init__(
        self,
        settings: LLMSettings | None = None,
        *,
        default_response: str | None = None,
        simulate_timeout: bool = False,
        simulate_error: bool = False,
    ) -> None:
        """Initialize mock LLM client.

        Args:
            settings: LLM settings
            default_response: Default response to return
            simulate_timeout: Whether to simulate timeout
            simulate_error: Whether to simulate API error
        """
        super().__init__(settings)
        self.default_response = default_response or "Mock response"
        self.simulate_timeout = simulate_timeout
        self.simulate_error = simulate_error
        self.call_count = 0
        self.last_messages: list[LLMMessage] | None = None

    def complete(
        self,
        messages: list[LLMMessage],
        *,
        response_format: ResponseFormat = ResponseFormat.TEXT,
        **kwargs: Any,  # noqa: ANN401, ARG002 — Mock interface compatibility
    ) -> LLMResponse:
        """Mock completion that returns predefined responses.

        Args:
            messages: List of messages in the conversation
            response_format: Expected response format
            **kwargs: Additional parameters (ignored)

        Returns:
            Mock LLM response
        """
        self.call_count += 1
        self.last_messages = messages

        # Simulate timeout
        if self.simulate_timeout:
            raise LLMTimeoutError(
                timeout=self.settings.timeout,
                model="mock-model",
            )

        # Simulate API error
        if self.simulate_error:
            raise LLMAPIError(
                message="Mock API error",
                status_code=500,
            )

        # Generate response based on format
        if response_format == ResponseFormat.JSON:
            # Try to parse the default response as JSON, or create a simple JSON
            try:
                json.loads(self.default_response)
                content = self.default_response
            except (json.JSONDecodeError, TypeError):
                content = json.dumps({"response": self.default_response})
        else:
            content = self.default_response

        return LLMResponse(
            content=content,
            model="mock-model",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            finish_reason="stop",
        )


def get_llm_client(settings: LLMSettings | None = None) -> LLMClient:
    """Factory function to get appropriate LLM client.

    Args:
        settings: LLM settings

    Returns:
        LLM client instance
    """
    settings = settings or LLMSettings()

    if settings.disable_llm:
        logger.info("LLM disabled, using mock client")
        return MockLLMClient(settings)

    try:
        return LiteLLMClient(settings)
    except ImportError:
        logger.warning("LiteLLM not available, falling back to mock client")
        return MockLLMClient(settings)
