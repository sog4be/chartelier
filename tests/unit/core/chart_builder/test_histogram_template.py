"""Unit tests for histogram template."""

import random

import altair as alt
import polars as pl
import pytest

from chartelier.core.chart_builder.templates.p03.histogram import HistogramTemplate
from chartelier.core.enums import AuxiliaryElement
from chartelier.core.models import MappingConfig


class TestHistogramTemplate:
    """Test suite for HistogramTemplate."""

    @pytest.fixture
    def template(self) -> HistogramTemplate:
        """Create histogram template instance."""
        return HistogramTemplate()

    @pytest.fixture
    def sample_data(self) -> pl.DataFrame:
        """Create sample data for testing."""
        # Generate test data that roughly follows a bell curve shape
        # Using a simple approach without numpy
        random.seed(42)
        values = []

        # Generate values clustered around 50 with some spread
        for _ in range(1000):
            # Create a simple distribution by averaging multiple random values
            # This approximates a normal distribution (central limit theorem)
            avg = sum(random.uniform(0, 100) for _ in range(3)) / 3  # noqa: S311 — Not cryptographic use
            # Shift and scale to center around 50 with spread
            value = 20 + avg * 0.6
            values.append(value)

        return pl.DataFrame(
            {
                "values": values,
                "category": ["A", "B"] * 500,
            }
        )

    def test_template_spec(self, template: HistogramTemplate) -> None:
        """Test template specification."""
        spec = template.spec
        assert spec.template_id == "P03_histogram"
        assert spec.name == "Histogram"
        assert spec.pattern_ids == ["P03"]
        assert "x" in spec.required_encodings
        assert "color" in spec.optional_encodings

    def test_build_basic_histogram(self, template: HistogramTemplate, sample_data: pl.DataFrame) -> None:
        """Test building a basic histogram."""
        mapping = MappingConfig(x="values")
        chart = template.build(sample_data, mapping)

        assert isinstance(chart, alt.Chart)
        # Check mark type
        assert chart.mark == "bar"
        # Check encodings
        chart_dict = chart.to_dict()
        assert "x" in chart_dict["encoding"]
        assert "y" in chart_dict["encoding"]
        # Y should be count
        assert chart_dict["encoding"]["y"]["aggregate"] == "count"

    def test_binning_applied(self, template: HistogramTemplate, sample_data: pl.DataFrame) -> None:
        """Test that binning is applied to numeric data."""
        mapping = MappingConfig(x="values")
        chart = template.build(sample_data, mapping)

        # Check that binning is applied to x-axis
        chart_dict = chart.to_dict()
        x_encoding = chart_dict["encoding"]["x"]
        assert "bin" in x_encoding
        assert x_encoding["bin"]["maxbins"] > 0

    def test_sturges_rule_calculation(self, template: HistogramTemplate) -> None:
        """Test Sturges' rule calculation for bin count."""
        # Test various data sizes
        # Using _calculate_bin_count is intentional for testing internal logic
        assert 5 <= template._calculate_bin_count(10) <= 50  # noqa: SLF001
        assert 5 <= template._calculate_bin_count(100) <= 50  # noqa: SLF001
        assert 5 <= template._calculate_bin_count(1000) <= 50  # noqa: SLF001
        assert 5 <= template._calculate_bin_count(10000) <= 50  # noqa: SLF001

        # Edge cases
        assert template._calculate_bin_count(0) == 10  # noqa: SLF001 — Default fallback
        assert template._calculate_bin_count(1) == 5  # noqa: SLF001 — Minimum

    def test_categorical_data_handling(self, template: HistogramTemplate) -> None:
        """Test histogram with categorical data (acts like bar chart)."""
        data = pl.DataFrame(
            {
                "categories": ["A", "B", "C", "A", "B", "C", "A", "A"],
            }
        )
        mapping = MappingConfig(x="categories")
        chart = template.build(data, mapping)

        # Should use nominal encoding for categorical data
        chart_dict = chart.to_dict()
        x_encoding = chart_dict["encoding"]["x"]
        assert x_encoding["type"] == "nominal" or ":N" in x_encoding["field"]

    def test_color_encoding(self, template: HistogramTemplate, sample_data: pl.DataFrame) -> None:
        """Test color encoding for grouped histograms."""
        mapping = MappingConfig(x="values", color="category")
        chart = template.build(sample_data, mapping)

        chart_dict = chart.to_dict()
        assert "color" in chart_dict["encoding"]

    def test_auxiliary_mean_line(self, template: HistogramTemplate, sample_data: pl.DataFrame) -> None:
        """Test applying vertical mean line auxiliary element."""
        mapping = MappingConfig(x="values")
        chart = template.build(sample_data, mapping)

        # Apply mean line
        chart_with_aux = template.apply_auxiliary(chart, [AuxiliaryElement.MEAN_LINE], sample_data, mapping)

        # Should return a layer chart with vertical mean line
        assert isinstance(chart_with_aux, alt.LayerChart)

    def test_auxiliary_median_line(self, template: HistogramTemplate, sample_data: pl.DataFrame) -> None:
        """Test applying vertical median line auxiliary element."""
        mapping = MappingConfig(x="values")
        chart = template.build(sample_data, mapping)

        # Apply median line
        chart_with_aux = template.apply_auxiliary(chart, [AuxiliaryElement.MEDIAN_LINE], sample_data, mapping)

        # Should return a layer chart with vertical median line
        assert isinstance(chart_with_aux, alt.LayerChart)

    def test_auxiliary_threshold_band(self, template: HistogramTemplate, sample_data: pl.DataFrame) -> None:
        """Test applying vertical threshold band auxiliary element."""
        mapping = MappingConfig(x="values")
        chart = template.build(sample_data, mapping)

        # Apply threshold band
        chart_with_aux = template.apply_auxiliary(chart, [AuxiliaryElement.THRESHOLD], sample_data, mapping)

        # Should return a layer chart with vertical threshold band
        assert isinstance(chart_with_aux, alt.LayerChart)

    def test_zero_origin_enforced(self, template: HistogramTemplate, sample_data: pl.DataFrame) -> None:
        """Test that histogram Y-axis starts at zero as per Visualization Policy."""
        mapping = MappingConfig(x="values")
        chart = template.build(sample_data, mapping)

        # Y-axis (frequency) must have zero=True
        chart_dict = chart.to_dict()
        y_encoding = chart_dict["encoding"]["y"]
        assert y_encoding["scale"]["zero"] is True
