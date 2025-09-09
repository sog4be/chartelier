"""Unit tests for box plot template."""

import random

import altair as alt
import polars as pl
import pytest

from chartelier.core.chart_builder.templates.box_plot import BoxPlotTemplate
from chartelier.core.enums import AuxiliaryElement
from chartelier.core.models import MappingConfig


class TestBoxPlotTemplate:
    """Test suite for BoxPlotTemplate."""

    @pytest.fixture
    def template(self) -> BoxPlotTemplate:
        """Create box plot template instance."""
        return BoxPlotTemplate()

    @pytest.fixture
    def sample_distribution_data(self) -> pl.DataFrame:
        """Create sample data with different distributions for testing."""

        data = []
        random.seed(42)  # For reproducible tests

        # Group A: Normal distribution around 50
        for _ in range(50):
            data.append({"category": "A", "value": random.normalvariate(50, 10)})

        # Group B: Normal distribution around 70
        for _ in range(50):
            data.append({"category": "B", "value": random.normalvariate(70, 15)})

        # Group C: Normal distribution around 40
        for _ in range(50):
            data.append({"category": "C", "value": random.normalvariate(40, 8)})

        return pl.DataFrame(data)

    @pytest.fixture
    def sample_colored_distribution_data(self) -> pl.DataFrame:
        """Create sample data with color grouping for testing."""

        data = []
        random.seed(42)

        for category in ["A", "B"]:
            for group in ["Group1", "Group2"]:
                for _ in range(25):
                    base = 50 if category == "A" else 70
                    offset = 10 if group == "Group1" else -5
                    data.append({"category": category, "value": random.normalvariate(base + offset, 8), "group": group})

        return pl.DataFrame(data)

    def test_template_spec(self, template: BoxPlotTemplate) -> None:
        """Test template specification."""
        spec = template.spec
        assert spec.template_id == "P32_box_plot"
        assert spec.name == "Box Plot"
        assert spec.pattern_ids == ["P32"]
        assert "x" in spec.required_encodings
        assert "y" in spec.required_encodings
        assert "color" in spec.optional_encodings

    def test_build_basic_box_plot(self, template: BoxPlotTemplate, sample_distribution_data: pl.DataFrame) -> None:
        """Test building a basic box plot."""
        mapping = MappingConfig(x="category", y="value")
        chart = template.build(sample_distribution_data, mapping)

        assert isinstance(chart, alt.Chart)
        # Check mark type - should be boxplot
        chart_dict = chart.to_dict()
        assert chart_dict["mark"]["type"] == "boxplot"
        assert chart_dict["mark"]["size"] == 40
        assert chart_dict["mark"]["outliers"] is True
        # Check encodings
        assert "x" in chart_dict["encoding"]
        assert "y" in chart_dict["encoding"]

    def test_categorical_x_quantitative_y(
        self, template: BoxPlotTemplate, sample_distribution_data: pl.DataFrame
    ) -> None:
        """Test correct encoding types for box plot."""
        mapping = MappingConfig(x="category", y="value")
        chart = template.build(sample_distribution_data, mapping)

        chart_dict = chart.to_dict()
        x_encoding = chart_dict["encoding"]["x"]
        y_encoding = chart_dict["encoding"]["y"]

        # X should be nominal (categorical)
        assert x_encoding["type"] == "nominal" or ":N" in x_encoding["field"]
        # Y should be quantitative
        assert y_encoding["type"] == "quantitative" or ":Q" in y_encoding["field"]

    def test_color_encoding(self, template: BoxPlotTemplate, sample_colored_distribution_data: pl.DataFrame) -> None:
        """Test color encoding for grouped box plots."""
        mapping = MappingConfig(x="category", y="value", color="group")
        chart = template.build(sample_colored_distribution_data, mapping)

        chart_dict = chart.to_dict()
        assert "color" in chart_dict["encoding"]
        color_encoding = chart_dict["encoding"]["color"]
        assert color_encoding["type"] == "nominal" or ":N" in color_encoding["field"]

    def test_no_zero_origin_required(self, template: BoxPlotTemplate, sample_distribution_data: pl.DataFrame) -> None:
        """Test that box plots don't enforce zero origin."""
        mapping = MappingConfig(x="category", y="value")
        chart = template.build(sample_distribution_data, mapping)

        # Box plots should not force zero origin as per Visualization Policy
        chart_dict = chart.to_dict()
        y_encoding = chart_dict["encoding"]["y"]
        if "scale" in y_encoding:
            assert y_encoding["scale"]["zero"] is False

    def test_auxiliary_overall_mean_line(
        self, template: BoxPlotTemplate, sample_distribution_data: pl.DataFrame
    ) -> None:
        """Test applying overall mean line auxiliary element."""
        mapping = MappingConfig(x="category", y="value")
        chart = template.build(sample_distribution_data, mapping)

        # Apply mean line - should show overall mean across all categories
        chart_with_aux = template.apply_auxiliary(
            chart, [AuxiliaryElement.MEAN_LINE], sample_distribution_data, mapping
        )

        # Should return a layer chart with horizontal mean line
        assert isinstance(chart_with_aux, alt.LayerChart)

    def test_auxiliary_target_line(self, template: BoxPlotTemplate, sample_distribution_data: pl.DataFrame) -> None:
        """Test applying target line auxiliary element."""
        mapping = MappingConfig(x="category", y="value")
        chart = template.build(sample_distribution_data, mapping)

        # Apply target line
        chart_with_aux = template.apply_auxiliary(
            chart, [AuxiliaryElement.TARGET_LINE], sample_distribution_data, mapping
        )

        # Should return a layer chart with target line
        assert isinstance(chart_with_aux, alt.LayerChart)

    def test_auxiliary_threshold_band(self, template: BoxPlotTemplate, sample_distribution_data: pl.DataFrame) -> None:
        """Test applying threshold band auxiliary element."""
        mapping = MappingConfig(x="category", y="value")
        chart = template.build(sample_distribution_data, mapping)

        # Apply threshold band
        chart_with_aux = template.apply_auxiliary(
            chart, [AuxiliaryElement.THRESHOLD], sample_distribution_data, mapping
        )

        # Should return a layer chart with threshold band
        assert isinstance(chart_with_aux, alt.LayerChart)

    def test_allowed_auxiliary_elements(self, template: BoxPlotTemplate) -> None:
        """Test that box plot allows appropriate auxiliary elements."""
        spec = template.spec
        allowed = spec.allowed_auxiliary

        # Box plots should allow reference lines and annotations
        assert AuxiliaryElement.MEAN_LINE in allowed
        assert AuxiliaryElement.TARGET_LINE in allowed
        assert AuxiliaryElement.THRESHOLD in allowed
        assert AuxiliaryElement.ANNOTATION in allowed
        assert AuxiliaryElement.HIGHLIGHT in allowed

        # Should not allow trend analysis (not suitable for categorical data)
        assert AuxiliaryElement.REGRESSION not in allowed
        assert AuxiliaryElement.MOVING_AVG not in allowed

    def test_mapping_validation(self, template: BoxPlotTemplate) -> None:
        """Test mapping validation for required encodings."""
        # Valid mapping with all required fields
        valid_mapping = MappingConfig(x="category", y="value")
        is_valid, missing = template.spec.validate_mapping(valid_mapping)
        assert is_valid
        assert len(missing) == 0

        # Invalid mapping missing x
        invalid_mapping = MappingConfig(y="value")
        is_valid, missing = template.spec.validate_mapping(invalid_mapping)
        assert not is_valid
        assert "x" in missing

        # Invalid mapping missing y
        invalid_mapping = MappingConfig(x="category")
        is_valid, missing = template.spec.validate_mapping(invalid_mapping)
        assert not is_valid
        assert "y" in missing

    def test_consistent_color_scheme(
        self, template: BoxPlotTemplate, sample_colored_distribution_data: pl.DataFrame
    ) -> None:
        """Test that consistent color scheme is used."""
        mapping = MappingConfig(x="category", y="value", color="group")
        chart = template.build(sample_colored_distribution_data, mapping)

        chart_dict = chart.to_dict()
        color_encoding = chart_dict["encoding"]["color"]
        # Should use category10 color scheme for consistency
        assert "scale" in color_encoding
        assert color_encoding["scale"]["scheme"] == "category10"
