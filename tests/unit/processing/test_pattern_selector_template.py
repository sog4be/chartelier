"""Unit tests for PatternSelector with PromptTemplate integration."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chartelier.core.models import DataMetadata
from chartelier.infra.llm_client import MockLLMClient
from chartelier.processing.pattern_selector import PatternSelector


class TestPatternSelectorTemplate:
    """Test cases for PatternSelector using PromptTemplate."""

    @pytest.fixture
    def sample_metadata(self) -> DataMetadata:
        """Create sample data metadata."""
        return DataMetadata(
            rows=1000,
            cols=5,
            dtypes={
                "date": "datetime",
                "sales": "float",
                "region": "string",
                "product": "string",
                "quantity": "integer",
            },
            has_datetime=True,
            has_category=True,
            null_ratio={"date": 0.0, "sales": 0.05, "region": 0.0, "product": 0.0, "quantity": 0.02},
            sampled=False,
        )

    def test_prompt_template_loaded(self) -> None:
        """Test that PromptTemplate is properly loaded."""
        selector = PatternSelector(llm_client=MockLLMClient())

        # Check that prompt_template is loaded
        assert hasattr(selector, "prompt_template")
        assert selector.prompt_template is not None
        assert selector.prompt_template.version == "v0.1.0"

    def test_prompt_template_file_exists(self) -> None:
        """Test that the prompt TOML file exists in the expected location."""
        prompt_path = (
            Path(__file__).parent.parent.parent.parent
            / "src"
            / "chartelier"
            / "processing"
            / "pattern_selector"
            / "prompts"
            / "v0.1.0.toml"
        )
        assert prompt_path.exists(), f"Prompt file not found at {prompt_path}"

    def test_prompt_template_rendering(self, sample_metadata: DataMetadata) -> None:
        """Test that prompt template correctly renders with provided variables."""
        mock_response = json.dumps(
            {
                "pattern_id": "P01",
                "reasoning": "Time series visualization",
                "confidence": 0.95,
            }
        )
        mock_client = MockLLMClient(default_response=mock_response)
        selector = PatternSelector(llm_client=mock_client)

        # Execute selection
        selector.select(sample_metadata, "Show sales trend over time")

        # Check that the messages were properly formed
        assert mock_client.last_messages is not None
        assert len(mock_client.last_messages) == 2

        # Check system message
        assert mock_client.last_messages[0].role == "system"
        assert "data visualization expert" in mock_client.last_messages[0].content

        # Check user message contains query and data info
        user_content = mock_client.last_messages[1].content
        assert "Show sales trend over time" in user_content
        assert "1,000" in user_content  # Row count
        assert "datetime" in user_content.lower()

    @patch("chartelier.processing.pattern_selector.processor.PromptTemplate")
    def test_prompt_template_called_correctly(
        self, mock_template_class: MagicMock, sample_metadata: DataMetadata
    ) -> None:
        """Test that PromptTemplate is initialized and called correctly."""
        # Setup mock
        mock_template_instance = MagicMock()
        mock_template_class.from_component.return_value = mock_template_instance
        mock_template_instance.render.return_value = [
            MagicMock(role="system", content="System prompt"),
            MagicMock(role="user", content="User prompt"),
        ]

        # Create selector
        mock_response = json.dumps({"pattern_id": "P01", "reasoning": "Test"})
        mock_client = MockLLMClient(default_response=mock_response)
        selector = PatternSelector(llm_client=mock_client)

        # Check template was loaded from correct location
        mock_template_class.from_component.assert_called_once()
        call_args = mock_template_class.from_component.call_args
        assert call_args[0][1] == "v0.1.0"  # prompt version

        # Execute selection
        selector.select(sample_metadata, "Test query")

        # Check template.render was called with correct variables
        mock_template_instance.render.assert_called_once()
        render_kwargs = mock_template_instance.render.call_args.kwargs
        assert "query" in render_kwargs
        assert render_kwargs["query"] == "Test query"
        assert "data_info" in render_kwargs

    def test_prompt_template_variables_complete(self, sample_metadata: DataMetadata) -> None:
        """Test that all required template variables are provided."""
        selector = PatternSelector(llm_client=MockLLMClient())

        # Get required variables from template
        required_vars = selector.prompt_template.get_required_variables()

        # Check that we know about all required variables
        expected_vars = {"query", "data_info"}
        assert required_vars == expected_vars, f"Template requires {required_vars}, expected {expected_vars}"
