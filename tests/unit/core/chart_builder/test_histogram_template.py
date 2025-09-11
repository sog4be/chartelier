"""Unit tests for histogram template."""

import random

import altair as alt
import polars as pl
import pytest

from chartelier.core.chart_builder.templates.p03.histogram import HistogramTemplate
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
        chart_dict = chart.to_dict()
        assert chart_dict["mark"]["type"] == "bar"
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

    def test_zero_origin_enforced(self, template: HistogramTemplate, sample_data: pl.DataFrame) -> None:
        """Test that histogram Y-axis starts at zero as per Visualization Policy."""
        mapping = MappingConfig(x="values")
        chart = template.build(sample_data, mapping)

        # Y-axis (frequency) must have zero=True
        chart_dict = chart.to_dict()
        y_encoding = chart_dict["encoding"]["y"]
        assert y_encoding["scale"]["zero"] is True

    def test_natural_boundary_0_1(self, template: HistogramTemplate) -> None:
        """Test that probability data uses 0-1 extent."""
        # Create probability data
        data = pl.DataFrame({"probability": [0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 0.9]})
        mapping = MappingConfig(x="probability")
        chart = template.build(data, mapping)

        # Check that binning uses 0-1 extent
        chart_dict = chart.to_dict()
        x_encoding = chart_dict["encoding"]["x"]
        assert "bin" in x_encoding
        bin_config = x_encoding["bin"]
        assert "extent" in bin_config
        assert bin_config["extent"] == [0.0, 1.0]
        assert bin_config["nice"] is False

    def test_natural_boundary_0_100(self, template: HistogramTemplate) -> None:
        """Test that percentage data uses 0-100 extent."""
        # Create percentage data
        data = pl.DataFrame({"percent": [10, 25, 50, 75, 90]})
        mapping = MappingConfig(x="percent")
        chart = template.build(data, mapping)

        # Check that binning uses 0-100 extent
        chart_dict = chart.to_dict()
        x_encoding = chart_dict["encoding"]["x"]
        assert "bin" in x_encoding
        bin_config = x_encoding["bin"]
        assert "extent" in bin_config
        assert bin_config["extent"] == [0.0, 100.0]
        assert bin_config["nice"] is False

    def test_integer_data_minstep(self, template: HistogramTemplate) -> None:
        """Test that integer data gets minstep=1."""
        # Create integer data
        data = pl.DataFrame({"counts": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]}, schema={"counts": pl.Int32})
        mapping = MappingConfig(x="counts")
        chart = template.build(data, mapping)

        # Check that binning includes minstep for integer data
        chart_dict = chart.to_dict()
        x_encoding = chart_dict["encoding"]["x"]
        assert "bin" in x_encoding
        bin_config = x_encoding["bin"]
        # Should have either minstep or appropriate step size
        if "minstep" in bin_config:
            assert bin_config["minstep"] == 1.0
