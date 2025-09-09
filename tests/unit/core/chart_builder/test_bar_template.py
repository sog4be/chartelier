"""Unit tests for bar chart template."""

import altair as alt
import polars as pl
import pytest

from chartelier.core.chart_builder.templates.p02.bar import BarTemplate
from chartelier.core.enums import AuxiliaryElement
from chartelier.core.models import MappingConfig


class TestBarTemplate:
    """Test suite for BarTemplate."""

    @pytest.fixture
    def template(self) -> BarTemplate:
        """Create bar template instance."""
        return BarTemplate()

    @pytest.fixture
    def sample_data(self) -> pl.DataFrame:
        """Create sample data for testing."""
        return pl.DataFrame(
            {
                "category": ["A", "B", "C", "D", "E"],
                "value": [10, 25, 15, 30, 20],
                "group": ["X", "Y", "X", "Y", "X"],
            }
        )

    def test_template_spec(self, template: BarTemplate) -> None:
        """Test template specification."""
        spec = template.spec
        assert spec.template_id == "P02_bar"
        assert spec.name == "Bar Chart"
        assert spec.pattern_ids == ["P02"]
        assert "x" in spec.required_encodings
        assert "y" in spec.required_encodings
        assert "color" in spec.optional_encodings

    def test_build_basic_bar_chart(self, template: BarTemplate, sample_data: pl.DataFrame) -> None:
        """Test building a basic bar chart."""
        mapping = MappingConfig(x="category", y="value")
        chart = template.build(sample_data, mapping)

        assert isinstance(chart, alt.Chart)
        # Check mark type
        assert chart.mark == "bar"
        # Check encodings are applied
        chart_dict = chart.to_dict()
        assert "x" in chart_dict["encoding"]
        assert "y" in chart_dict["encoding"]

    def test_vertical_bars_with_categorical_x(self, template: BarTemplate, sample_data: pl.DataFrame) -> None:
        """Test vertical bars with categorical x-axis."""
        mapping = MappingConfig(x="category", y="value")
        chart = template.build(sample_data, mapping)

        # Check that y-axis has zero scale (required for bar charts)
        chart_dict = chart.to_dict()
        y_encoding = chart_dict["encoding"]["y"]
        assert y_encoding["scale"]["zero"] is True

    def test_horizontal_bars_with_numeric_x(self, template: BarTemplate) -> None:
        """Test horizontal bars when x is numeric and y is categorical."""
        data = pl.DataFrame(
            {
                "category": ["A", "B", "C", "D"],
                "value": [10, 25, 15, 30],
            }
        )
        mapping = MappingConfig(x="value", y="category")
        chart = template.build(data, mapping)

        # Check that x-axis has zero scale for horizontal bars
        chart_dict = chart.to_dict()
        x_encoding = chart_dict["encoding"]["x"]
        assert x_encoding["scale"]["zero"] is True

    def test_color_encoding(self, template: BarTemplate, sample_data: pl.DataFrame) -> None:
        """Test color encoding."""
        mapping = MappingConfig(x="category", y="value", color="group")
        chart = template.build(sample_data, mapping)

        chart_dict = chart.to_dict()
        assert "color" in chart_dict["encoding"]

    def test_auxiliary_mean_line(self, template: BarTemplate, sample_data: pl.DataFrame) -> None:
        """Test applying mean line auxiliary element."""
        mapping = MappingConfig(x="category", y="value")
        chart = template.build(sample_data, mapping)

        # Apply mean line
        chart_with_aux = template.apply_auxiliary(chart, [AuxiliaryElement.MEAN_LINE], sample_data, mapping)

        # Should return a layer chart with mean line
        assert isinstance(chart_with_aux, alt.LayerChart)

    def test_auxiliary_threshold_band(self, template: BarTemplate, sample_data: pl.DataFrame) -> None:
        """Test applying threshold band auxiliary element."""
        mapping = MappingConfig(x="category", y="value")
        chart = template.build(sample_data, mapping)

        # Apply threshold band
        chart_with_aux = template.apply_auxiliary(chart, [AuxiliaryElement.THRESHOLD], sample_data, mapping)

        # Should return a layer chart with threshold band
        assert isinstance(chart_with_aux, alt.LayerChart)

    def test_zero_origin_enforced(self, template: BarTemplate, sample_data: pl.DataFrame) -> None:
        """Test that bar charts enforce zero origin as per Visualization Policy."""
        mapping = MappingConfig(x="category", y="value")
        chart = template.build(sample_data, mapping)

        # Y-axis must have zero=True for vertical bars
        chart_dict = chart.to_dict()
        y_encoding = chart_dict["encoding"]["y"]
        assert y_encoding["scale"]["zero"] is True
