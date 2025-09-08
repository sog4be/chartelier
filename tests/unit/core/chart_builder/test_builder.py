"""Unit tests for ChartBuilder class."""

import altair as alt
import polars as pl
import pytest

from chartelier.core.chart_builder import ChartBuilder, ChartSpec
from chartelier.core.chart_builder.templates import LineTemplate
from chartelier.core.enums import PatternID
from chartelier.core.errors import ChartBuildError
from chartelier.core.models import MappingConfig


class TestChartBuilder:
    """Test cases for ChartBuilder."""

    @pytest.fixture
    def builder(self):
        """Create a ChartBuilder instance."""
        builder = ChartBuilder()
        # Register a test template
        builder.register_template("P01_line", LineTemplate())
        return builder

    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing."""
        return pl.DataFrame(
            {
                "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
                "value": [10, 20, 15],
                "category": ["A", "A", "A"],
            }
        )

    def test_register_template(self, builder):
        """Test template registration."""
        # Template should be registered
        assert "P01_line" in builder._templates  # noqa: SLF001 — Testing internal state

        # Should be able to get template spec
        spec = builder.get_template_spec("P01_line")
        assert spec is not None
        assert spec.template_id == "P01_line"

    def test_get_available_charts(self, builder):
        """Test getting available charts for a pattern."""
        # Get charts for P01 pattern
        charts = builder.get_available_charts(PatternID.P01)
        assert len(charts) == 1
        assert charts[0].template_id == "P01_line"

        # Get charts for pattern without templates (should return default)
        charts = builder.get_available_charts(PatternID.P02)
        assert len(charts) == 1
        assert charts[0].template_id == "P02_bar"

    def test_build_chart_success(self, builder, sample_data):
        """Test successful chart building."""
        mapping = MappingConfig(x="date", y="value")

        chart = builder.build(
            template_id="P01_line",
            data=sample_data,
            mapping=mapping,
            width=800,
            height=600,
        )

        assert isinstance(chart, alt.Chart)

    def test_build_chart_missing_template(self, builder, sample_data):
        """Test building with non-existent template."""
        mapping = MappingConfig(x="date", y="value")

        with pytest.raises(ChartBuildError, match="Template not found"):
            builder.build(
                template_id="nonexistent",
                data=sample_data,
                mapping=mapping,
            )

    def test_build_chart_invalid_mapping(self, builder, sample_data):
        """Test building with invalid mapping."""
        # Missing required y field
        mapping = MappingConfig(x="date")

        with pytest.raises(ChartBuildError, match="Missing required mappings"):
            builder.build(
                template_id="P01_line",
                data=sample_data,
                mapping=mapping,
            )

    def test_build_with_auxiliary(self, builder, sample_data):
        """Test building chart with auxiliary elements."""
        mapping = MappingConfig(x="date", y="value")

        chart = builder.build(
            template_id="P01_line",
            data=sample_data,
            mapping=mapping,
            auxiliary=["mean_line", "regression"],
        )

        # Chart with auxiliary elements becomes a LayerChart
        assert isinstance(chart, (alt.Chart, alt.LayerChart))


class TestChartSpec:
    """Test cases for ChartSpec."""

    def test_chart_spec_creation(self):
        """Test ChartSpec initialization."""
        spec = ChartSpec(
            template_id="test_template",
            name="Test Template",
            pattern_ids=[PatternID.P01, PatternID.P12],
        )

        assert spec.template_id == "test_template"
        assert spec.name == "Test Template"
        assert len(spec.pattern_ids) == 2
        assert PatternID.P01 in spec.pattern_ids
