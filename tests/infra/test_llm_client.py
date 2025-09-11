"""Tests for LLM client implementations."""

import json
from unittest.mock import MagicMock, patch

import pytest

from chartelier.core.enums import ErrorCode
from chartelier.infra.llm_client import (
    LiteLLMClient,
    LLMAPIError,
    LLMMessage,
    LLMResponse,
    LLMSettings,
    LLMTimeoutError,
    MockLLMClient,
    ResponseFormat,
    get_llm_client,
)


class TestLLMMessage:
    """Tests for LLMMessage model."""

    def test_message_creation(self):
        """Test creating an LLM message."""
        msg = LLMMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_message_validation(self):
        """Test message validation."""
        with pytest.raises(ValueError):
            LLMMessage()  # Missing required fields


class TestLLMResponse:
    """Tests for LLMResponse model."""

    def test_response_creation(self):
        """Test creating an LLM response."""
        response = LLMResponse(
            content="Response text",
            model="gpt-3.5-turbo",
            usage={"tokens": 100},
            finish_reason="stop",
        )
        assert response.content == "Response text"
        assert response.model == "gpt-3.5-turbo"
        assert response.usage == {"tokens": 100}
        assert response.finish_reason == "stop"

    def test_response_minimal(self):
        """Test creating response with minimal fields."""
        response = LLMResponse(content="Response")
        assert response.content == "Response"
        assert response.model is None
        assert response.usage is None
        assert response.finish_reason is None


class TestLLMSettings:
    """Tests for LLM settings."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = LLMSettings()
        assert settings.model == "gpt-5-mini"
        assert settings.timeout == 10
        assert settings.max_retries == 3
        assert settings.retry_delay == 1.0
        assert settings.temperature == 0.0
        assert settings.disable_llm is False

    def test_settings_from_env(self, monkeypatch):
        """Test loading settings from environment variables."""
        monkeypatch.setenv("CHARTELIER_LLM_API_KEY", "test-key")
        monkeypatch.setenv("CHARTELIER_LLM_MODEL", "gpt-4")
        monkeypatch.setenv("CHARTELIER_LLM_TIMEOUT", "30")
        monkeypatch.setenv("CHARTELIER_LLM_DISABLE_LLM", "true")

        settings = LLMSettings()
        assert settings.api_key == "test-key"
        assert settings.model == "gpt-4"
        assert settings.timeout == 30
        assert settings.disable_llm is True


class TestLLMErrors:
    """Tests for LLM error classes."""

    def test_timeout_error(self):
        """Test LLM timeout error."""
        error = LLMTimeoutError(timeout=10, model="gpt-3.5-turbo")
        assert error.code == ErrorCode.E408_TIMEOUT
        assert "10 seconds" in error.message
        assert error.hint is not None
        assert len(error.details) == 2

    def test_api_error(self):
        """Test LLM API error."""
        error = LLMAPIError(message="API failed", status_code=500)
        assert error.code == ErrorCode.E424_UPSTREAM_LLM
        assert "API failed" in error.message
        assert error.hint is not None
        assert len(error.details) == 2

    def test_api_error_without_status(self):
        """Test LLM API error without status code."""
        error = LLMAPIError(message="API failed")
        assert error.code == ErrorCode.E424_UPSTREAM_LLM
        assert len(error.details) == 1


class TestMockLLMClient:
    """Tests for mock LLM client."""

    def test_mock_default_response(self):
        """Test mock client with default response."""
        client = MockLLMClient()
        messages = [LLMMessage(role="user", content="Hello")]

        response = client.complete(messages)
        assert response.content == "Mock response"
        assert response.model == "mock-model"
        assert client.call_count == 1
        assert client.last_messages == messages

    def test_mock_custom_response(self):
        """Test mock client with custom response."""
        client = MockLLMClient(default_response="Custom response")
        messages = [LLMMessage(role="user", content="Hello")]

        response = client.complete(messages)
        assert response.content == "Custom response"

    def test_mock_json_response(self):
        """Test mock client with JSON response format."""
        client = MockLLMClient(default_response='{"key": "value"}')
        messages = [LLMMessage(role="user", content="Hello")]

        response = client.complete(messages, response_format=ResponseFormat.JSON)
        assert response.content == '{"key": "value"}'
        parsed = json.loads(response.content)
        assert parsed["key"] == "value"

    def test_mock_json_response_non_json_default(self):
        """Test mock client converts non-JSON to JSON."""
        client = MockLLMClient(default_response="Not JSON")
        messages = [LLMMessage(role="user", content="Hello")]

        response = client.complete(messages, response_format=ResponseFormat.JSON)
        parsed = json.loads(response.content)
        assert parsed["response"] == "Not JSON"

    def test_mock_simulate_timeout(self):
        """Test mock client simulating timeout."""
        client = MockLLMClient(simulate_timeout=True)
        messages = [LLMMessage(role="user", content="Hello")]

        with pytest.raises(LLMTimeoutError) as exc_info:
            client.complete(messages)
        assert exc_info.value.code == ErrorCode.E408_TIMEOUT

    def test_mock_simulate_error(self):
        """Test mock client simulating API error."""
        client = MockLLMClient(simulate_error=True)
        messages = [LLMMessage(role="user", content="Hello")]

        with pytest.raises(LLMAPIError) as exc_info:
            client.complete(messages)
        assert exc_info.value.code == ErrorCode.E424_UPSTREAM_LLM
        assert "Mock API error" in str(exc_info.value)


class TestLiteLLMClient:
    """Tests for LiteLLM client."""

    def test_litellm_not_installed(self):
        """Test handling when litellm is not installed."""
        with patch.dict("sys.modules", {"litellm": None}):
            with pytest.raises(ImportError) as exc_info:
                LiteLLMClient()
            assert "litellm is not installed" in str(exc_info.value)

    def test_litellm_successful_completion(self):
        """Test successful completion with LiteLLM."""
        with patch.object(LiteLLMClient, "_ensure_litellm"):
            client = LiteLLMClient()

            # Mock litellm module inside client
            mock_litellm = MagicMock()
            client._litellm = mock_litellm  # noqa: SLF001 — Testing internals

            # Mock litellm response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test response"
            mock_response.choices[0].finish_reason = "stop"
            mock_response.model = "gpt-3.5-turbo"
            mock_response.usage.model_dump.return_value = {"total_tokens": 50}

            mock_litellm.completion.return_value = mock_response

            messages = [LLMMessage(role="user", content="Hello")]

            response = client.complete(messages)
            assert response.content == "Test response"
            assert response.model == "gpt-3.5-turbo"
            assert response.usage == {"total_tokens": 50}
            assert response.finish_reason == "stop"

            # Verify litellm was called correctly
            mock_litellm.completion.assert_called_once()
            call_kwargs = mock_litellm.completion.call_args[1]
            assert call_kwargs["model"] == "gpt-5-mini"  # Using new default model
            assert len(call_kwargs["messages"]) == 1
            assert call_kwargs["messages"][0]["role"] == "user"
            assert call_kwargs["messages"][0]["content"] == "Hello"

    def test_litellm_json_format(self):
        """Test JSON response format with LiteLLM."""
        with patch.object(LiteLLMClient, "_ensure_litellm"):
            client = LiteLLMClient()

            # Mock litellm module inside client
            mock_litellm = MagicMock()
            client._litellm = mock_litellm  # noqa: SLF001 — Testing internals

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = '{"result": "test"}'
            mock_response.choices[0].finish_reason = "stop"
            mock_response.model = "gpt-3.5-turbo"
            mock_response.usage = None

            mock_litellm.completion.return_value = mock_response

            messages = [LLMMessage(role="user", content="Generate JSON")]

            response = client.complete(messages, response_format=ResponseFormat.JSON)
            assert response.content == '{"result": "test"}'

            # Verify response format was set
            call_kwargs = mock_litellm.completion.call_args[1]
            assert "response_format" in call_kwargs
            assert call_kwargs["response_format"]["type"] == "json_object"

    def test_litellm_timeout_with_retry(self):
        """Test timeout handling with retry in LiteLLM."""
        settings = LLMSettings(max_retries=2, retry_delay=0.01)

        with patch.object(LiteLLMClient, "_ensure_litellm"):
            client = LiteLLMClient(settings)

            # Mock litellm module inside client
            mock_litellm = MagicMock()
            client._litellm = mock_litellm  # noqa: SLF001 — Testing internals

            # Create custom exception class that matches litellm's
            class MockTimeout(Exception):  # noqa: N818 — Matches litellm naming
                pass

            mock_litellm.Timeout = MockTimeout
            mock_litellm.completion.side_effect = MockTimeout("Request timed out")

            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(LLMTimeoutError) as exc_info:
                client.complete(messages)

            assert exc_info.value.code == ErrorCode.E408_TIMEOUT
            # Should have tried twice (initial + 1 retry)
            assert mock_litellm.completion.call_count == 2

    def test_litellm_api_error(self):
        """Test API error handling in LiteLLM."""
        settings = LLMSettings(max_retries=1)

        with patch.object(LiteLLMClient, "_ensure_litellm"):
            client = LiteLLMClient(settings)

            # Mock litellm module inside client
            mock_litellm = MagicMock()
            client._litellm = mock_litellm  # noqa: SLF001 — Testing internals

            # Create a proper exception class
            class MockAPIError(Exception):
                pass

            mock_litellm.APIError = MockAPIError
            mock_litellm.completion.side_effect = MockAPIError("Rate limit exceeded")

            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(LLMAPIError) as exc_info:
                client.complete(messages)

            assert exc_info.value.code == ErrorCode.E424_UPSTREAM_LLM
            assert "Rate limit exceeded" in str(exc_info.value)

    def test_litellm_with_api_key(self):
        """Test LiteLLM with API key setting."""
        settings = LLMSettings(api_key="test-api-key")

        with patch.object(LiteLLMClient, "_ensure_litellm"):
            client = LiteLLMClient(settings)

            # Mock litellm module inside client
            mock_litellm = MagicMock()
            client._litellm = mock_litellm  # noqa: SLF001 — Testing internals

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Response"
            mock_response.choices[0].finish_reason = "stop"
            mock_response.model = "gpt-3.5-turbo"
            mock_response.usage = None

            mock_litellm.completion.return_value = mock_response

            messages = [LLMMessage(role="user", content="Hello")]

            client.complete(messages)

            # Verify API key was passed
            call_kwargs = mock_litellm.completion.call_args[1]
            assert call_kwargs["api_key"] == "test-api-key"


class TestGetLLMClient:
    """Tests for get_llm_client factory function."""

    def test_get_mock_when_disabled(self):
        """Test getting mock client when LLM is disabled."""
        settings = LLMSettings(disable_llm=True)
        client = get_llm_client(settings)
        assert isinstance(client, MockLLMClient)

    @patch("chartelier.infra.llm_client.LiteLLMClient")
    def test_get_litellm_when_available(self, mock_litellm_class):
        """Test getting LiteLLM client when available."""
        mock_litellm_class.return_value = MagicMock()
        settings = LLMSettings(disable_llm=False)
        get_llm_client(settings)
        mock_litellm_class.assert_called_once_with(settings)

    def test_fallback_to_mock_when_litellm_unavailable(self):
        """Test fallback to mock when litellm is not available."""
        with patch.object(LiteLLMClient, "__init__", side_effect=ImportError("No litellm")):
            settings = LLMSettings(disable_llm=False)
            client = get_llm_client(settings)
            assert isinstance(client, MockLLMClient)
