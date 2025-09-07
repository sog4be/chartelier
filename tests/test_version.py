"""Test version information."""

import chartelier


def test_version() -> None:
    """Test that version is accessible and formatted correctly."""
    assert hasattr(chartelier, "__version__")
    assert isinstance(chartelier.__version__, str)
    assert chartelier.__version__ == "0.1.0"


def test_version_format() -> None:
    """Test that version follows semantic versioning format."""
    version_parts = chartelier.__version__.split(".")
    assert len(version_parts) == 3
    for part in version_parts:
        assert part.isdigit()
        assert int(part) >= 0
