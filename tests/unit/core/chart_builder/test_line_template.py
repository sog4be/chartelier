"""Unit tests for line chart template."""

from datetime import UTC, datetime, timedelta

import altair as alt
import polars as pl
import pytest

from chartelier.core.chart_builder.templates.p01.line import LineTemplate
from chartelier.core.enums import AuxiliaryElement
from chartelier.core.models import MappingConfig


class TestLineTemplate:
    """Test suite for LineTemplate."""

    @pytest.fixture
    def template(self) -> LineTemplate:
        """Create line template instance."""
        return LineTemplate()

    @pytest.fixture
    def sample_time_series_data(self) -> pl.DataFrame:
        """Create sample time series data for testing."""
        base_date = datetime(2024, 1, 1, tzinfo=UTC)
        dates = [base_date + timedelta(days=i) for i in range(30)]
        return pl.DataFrame(
            {
                "date": dates,
                "value": [10 + i * 2 + (i % 7) for i in range(30)],
                "series": ["A"] * 15 + ["B"] * 15,
            }
        )

    @pytest.fixture
    def sample_numeric_data(self) -> pl.DataFrame:
        """Create sample numeric data for testing."""
        return pl.DataFrame(
            {
                "x": list(range(1, 21)),
                "y": [i * 1.5 + (i % 3) for i in range(1, 21)],
                "group": ["Group1"] * 10 + ["Group2"] * 10,
            }
        )

    def test_template_spec(self, template: LineTemplate) -> None:
        """Test template specification."""
        spec = template.spec
        assert spec.template_id == "P01_line"
        assert spec.name == "Line Chart"
        assert spec.pattern_ids == ["P01"]
        assert "x" in spec.required_encodings
        assert "y" in spec.required_encodings
        assert "color" in spec.optional_encodings

    def test_build_basic_line_chart(self, template: LineTemplate, sample_numeric_data: pl.DataFrame) -> None:
        """Test building a basic line chart."""
        mapping = MappingConfig(x="x", y="y")
        chart = template.build(sample_numeric_data, mapping)

        assert isinstance(chart, alt.Chart)
        # Check mark type - should be line with points
        chart_dict = chart.to_dict()
        assert chart_dict["mark"]["type"] == "line"
        assert chart_dict["mark"]["point"] is True
        # Check encodings
        assert "x" in chart_dict["encoding"]
        assert "y" in chart_dict["encoding"]

    def test_temporal_axis_detection(self, template: LineTemplate, sample_time_series_data: pl.DataFrame) -> None:
        """Test automatic detection of temporal data."""
        mapping = MappingConfig(x="date", y="value")
        chart = template.build(sample_time_series_data, mapping)

        # Check that temporal encoding is used for dates
        chart_dict = chart.to_dict()
        x_encoding = chart_dict["encoding"]["x"]
        assert x_encoding["type"] == "temporal" or ":T" in x_encoding["field"]  # Temporal encoding

    def test_numeric_axis_handling(self, template: LineTemplate, sample_numeric_data: pl.DataFrame) -> None:
        """Test handling of numeric axes."""
        mapping = MappingConfig(x="x", y="y")
        chart = template.build(sample_numeric_data, mapping)

        # Check that quantitative encoding is used for numbers
        chart_dict = chart.to_dict()
        x_encoding = chart_dict["encoding"]["x"]
        y_encoding = chart_dict["encoding"]["y"]
        assert x_encoding["type"] == "quantitative" or ":Q" in x_encoding["field"]  # Quantitative encoding
        assert y_encoding["type"] == "quantitative" or ":Q" in y_encoding["field"]  # Quantitative encoding

    def test_color_encoding(self, template: LineTemplate, sample_numeric_data: pl.DataFrame) -> None:
        """Test color encoding for multiple series."""
        mapping = MappingConfig(x="x", y="y", color="group")
        chart = template.build(sample_numeric_data, mapping)

        chart_dict = chart.to_dict()
        assert "color" in chart_dict["encoding"]
        color_encoding = chart_dict["encoding"]["color"]
        assert color_encoding["type"] == "nominal" or ":N" in color_encoding["field"]  # Nominal encoding for categories

    def test_auxiliary_mean_line(self, template: LineTemplate, sample_numeric_data: pl.DataFrame) -> None:
        """Test applying horizontal mean line auxiliary element."""
        mapping = MappingConfig(x="x", y="y")
        chart = template.build(sample_numeric_data, mapping)

        # Apply mean line
        chart_with_aux = template.apply_auxiliary(chart, [AuxiliaryElement.MEAN_LINE], sample_numeric_data, mapping)

        # Should return a layer chart with horizontal mean line
        assert isinstance(chart_with_aux, alt.LayerChart)


    def test_multiple_auxiliary_elements(self, template: LineTemplate, sample_numeric_data: pl.DataFrame) -> None:
        """Test applying multiple auxiliary elements."""
        mapping = MappingConfig(x="x", y="y")
        chart = template.build(sample_numeric_data, mapping)

        # Apply multiple auxiliary elements
        chart_with_aux = template.apply_auxiliary(
            chart, [AuxiliaryElement.MEAN_LINE, AuxiliaryElement.MOVING_AVG], sample_numeric_data, mapping
        )

        # Should return a layer chart with both elements
        assert isinstance(chart_with_aux, alt.LayerChart)

    def test_allowed_auxiliary_elements(self, template: LineTemplate) -> None:
        """Test that line chart allows appropriate auxiliary elements."""
        spec = template.spec
        allowed = spec.allowed_auxiliary

        # Line charts should allow trend and reference lines
        assert AuxiliaryElement.MEAN_LINE in allowed
        assert AuxiliaryElement.MOVING_AVG in allowed
        assert AuxiliaryElement.TARGET_LINE in allowed
        assert AuxiliaryElement.MEDIAN_LINE in allowed

    def test_no_zero_origin_required(self, template: LineTemplate, sample_numeric_data: pl.DataFrame) -> None:
        """Test that line charts don't enforce zero origin as per Visualization Policy."""
        mapping = MappingConfig(x="x", y="y")
        chart = template.build(sample_numeric_data, mapping)

        # Line charts should not force zero origin
        chart_dict = chart.to_dict()
        y_encoding = chart_dict["encoding"]["y"]
        # Scale should either not be set or not have zero=True
        if "scale" in y_encoding:
            assert y_encoding.get("scale", {}).get("zero") is not True
