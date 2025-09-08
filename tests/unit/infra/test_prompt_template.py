"""Unit tests for PromptTemplate utility."""

import textwrap
from pathlib import Path

import pytest
from jinja2 import UndefinedError

from chartelier.infra.prompt_template import PromptConfig, PromptMessage, PromptTemplate, PromptTemplateError


class TestPromptTemplate:
    """Tests for PromptTemplate class."""

    @pytest.fixture
    def simple_prompt_toml(self) -> str:
        """Create a simple prompt TOML content."""
        return textwrap.dedent("""\
            version = "v0.1.0"

            [[messages]]
            role = "system"
            content = "You are a helpful assistant."

            [[messages]]
            role = "user"
            content = "Hello {{ name }}, your task is: {{ task }}"
            do_strip = true
        """)

    @pytest.fixture
    def complex_prompt_toml(self) -> str:
        """Create a complex prompt TOML with multiple variables."""
        return textwrap.dedent("""\
            version = "v0.2.0"

            [[messages]]
            role = "system"
            content = '''
            You are an expert in {{ domain }}.
            Your expertise level is {{ level }}.
            '''
            do_strip = true

            [[messages]]
            role = "user"
            content = '''
            {% for item in items %}
            - {{ item }}
            {% endfor %}

            Task: {{ task }}
            '''
            do_strip = false
        """)

    def test_load_valid_toml(self, simple_prompt_toml: str, tmp_path: Path) -> None:
        """Test loading a valid TOML file."""
        # Write TOML to temp file
        prompt_file = tmp_path / "test_prompt.toml"
        prompt_file.write_text(simple_prompt_toml)

        # Load template
        template = PromptTemplate(prompt_file)

        # Verify loaded correctly
        assert template.version == "v0.1.0"
        assert len(template.config.messages) == 2
        assert template.config.messages[0].role == "system"
        assert template.config.messages[1].role == "user"

    def test_render_simple_template(self, simple_prompt_toml: str, tmp_path: Path) -> None:
        """Test rendering a simple template with variables."""
        # Setup
        prompt_file = tmp_path / "test_prompt.toml"
        prompt_file.write_text(simple_prompt_toml)
        template = PromptTemplate(prompt_file)

        # Render
        messages = template.render(name="Alice", task="Write a test")

        # Verify
        assert len(messages) == 2
        assert messages[0].role == "system"
        assert messages[0].content == "You are a helpful assistant."
        assert messages[1].role == "user"
        assert messages[1].content == "Hello Alice, your task is: Write a test"

    def test_render_complex_template(self, complex_prompt_toml: str, tmp_path: Path) -> None:
        """Test rendering a complex template with loops and conditionals."""
        # Setup
        prompt_file = tmp_path / "test_prompt.toml"
        prompt_file.write_text(complex_prompt_toml)
        template = PromptTemplate(prompt_file)

        # Render
        messages = template.render(
            domain="Data Science",
            level="Expert",
            items=["Item 1", "Item 2", "Item 3"],
            task="Analyze the data",
        )

        # Verify
        assert len(messages) == 2
        assert "Data Science" in messages[0].content
        assert "Expert" in messages[0].content
        assert "Item 1" in messages[1].content
        assert "Item 2" in messages[1].content
        assert "Item 3" in messages[1].content
        assert "Analyze the data" in messages[1].content

    def test_missing_variable_error(self, simple_prompt_toml: str, tmp_path: Path) -> None:
        """Test that missing variables raise UndefinedError."""
        # Setup
        prompt_file = tmp_path / "test_prompt.toml"
        prompt_file.write_text(simple_prompt_toml)
        template = PromptTemplate(prompt_file)

        # Should raise error for missing 'task' variable
        with pytest.raises(UndefinedError) as exc_info:
            template.render(name="Alice")  # Missing 'task'

        assert "task" in str(exc_info.value)

    def test_strip_whitespace(self, tmp_path: Path) -> None:
        """Test that do_strip correctly strips whitespace."""
        toml_content = textwrap.dedent("""\
            version = "v0.1.0"

            [[messages]]
            role = "user"
            content = "   Content with spaces   "
            do_strip = true

            [[messages]]
            role = "assistant"
            content = "   Content with spaces   "
            do_strip = false
        """)
        prompt_file = tmp_path / "test_prompt.toml"
        prompt_file.write_text(toml_content)
        template = PromptTemplate(prompt_file)

        messages = template.render()

        assert messages[0].content == "Content with spaces"  # Stripped
        assert messages[1].content == "   Content with spaces   "  # Not stripped

    def test_invalid_toml_error(self, tmp_path: Path) -> None:
        """Test that invalid TOML raises PromptTemplateError."""
        prompt_file = tmp_path / "invalid.toml"
        prompt_file.write_text("This is not valid TOML {]}")

        with pytest.raises(PromptTemplateError) as exc_info:
            PromptTemplate(prompt_file)

        assert "Invalid TOML" in str(exc_info.value)

    def test_invalid_role_error(self, tmp_path: Path) -> None:
        """Test that invalid role raises validation error."""
        toml_content = textwrap.dedent("""\
            version = "v0.1.0"

            [[messages]]
            role = "invalid_role"
            content = "Test content"
        """)
        prompt_file = tmp_path / "test.toml"
        prompt_file.write_text(toml_content)

        with pytest.raises(PromptTemplateError) as exc_info:
            PromptTemplate(prompt_file)

        assert "Invalid prompt configuration" in str(exc_info.value)

    def test_file_not_found_error(self) -> None:
        """Test that missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            PromptTemplate("/non/existent/file.toml")

    def test_from_component_method(self, simple_prompt_toml: str, tmp_path: Path) -> None:
        """Test the from_component class method."""
        # Create component structure
        component_dir = tmp_path / "component"
        prompts_dir = component_dir / "prompts"
        prompts_dir.mkdir(parents=True)

        prompt_file = prompts_dir / "test_prompt.toml"
        prompt_file.write_text(simple_prompt_toml)

        # Load using from_component
        template = PromptTemplate.from_component(component_dir, "test_prompt")

        # Verify it loaded correctly
        assert template.version == "v0.1.0"
        messages = template.render(name="Bob", task="Test task")
        assert len(messages) == 2

    def test_get_required_variables(self, simple_prompt_toml: str, tmp_path: Path) -> None:
        """Test getting required variables from template."""
        prompt_file = tmp_path / "test.toml"
        prompt_file.write_text(simple_prompt_toml)
        template = PromptTemplate(prompt_file)

        required_vars = template.get_required_variables()

        assert "name" in required_vars
        assert "task" in required_vars
        assert len(required_vars) == 2

    def test_invalid_jinja2_template(self, tmp_path: Path) -> None:
        """Test that invalid Jinja2 syntax raises error."""
        toml_content = textwrap.dedent("""\
            version = "v0.1.0"

            [[messages]]
            role = "user"
            content = "Invalid template {{ name"
        """)
        prompt_file = tmp_path / "test.toml"
        prompt_file.write_text(toml_content)

        with pytest.raises(PromptTemplateError) as exc_info:
            PromptTemplate(prompt_file)

        assert "Invalid Jinja2 template" in str(exc_info.value)

    def test_prompt_config_model(self) -> None:
        """Test PromptConfig Pydantic model."""
        config = PromptConfig(
            version="v0.1.0",
            messages=[
                PromptMessage(role="system", content="System message"),
                PromptMessage(role="user", content="User message", do_strip=False),
            ],
        )

        assert config.version == "v0.1.0"
        assert len(config.messages) == 2
        assert config.messages[0].do_strip is True  # Default value
        assert config.messages[1].do_strip is False

    def test_template_repr(self, simple_prompt_toml: str, tmp_path: Path) -> None:
        """Test string representation of PromptTemplate."""
        prompt_file = tmp_path / "test.toml"
        prompt_file.write_text(simple_prompt_toml)
        template = PromptTemplate(prompt_file)

        repr_str = repr(template)
        assert "PromptTemplate" in repr_str
        assert "test.toml" in repr_str
        assert "v0.1.0" in repr_str
