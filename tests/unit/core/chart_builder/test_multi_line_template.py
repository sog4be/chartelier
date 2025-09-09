"""Unit tests for multi-line chart template."""

from datetime import UTC, datetime, timedelta

import altair as alt
import polars as pl
import pytest

from chartelier.core.chart_builder.templates.p12.multi_line import MultiLineTemplate
from chartelier.core.enums import AuxiliaryElement
from chartelier.core.models import MappingConfig


class TestMultiLineTemplate:
    """Test suite for MultiLineTemplate."""

    @pytest.fixture
    def template(self) -> MultiLineTemplate:
        """Create multi-line template instance."""
        return MultiLineTemplate()

    @pytest.fixture
    def sample_multi_series_data(self) -> pl.DataFrame:
        """Create sample multi-series time data for testing."""
        base_date = datetime(2024, 1, 1, tzinfo=UTC)
        dates = [base_date + timedelta(days=i) for i in range(30)]
        data = []
        for i, date in enumerate(dates):
            # Series A: increasing trend
            data.append({"date": date, "value": 10 + i * 1.5, "series": "A"})
            # Series B: decreasing trend
            data.append({"date": date, "value": 50 - i * 0.8, "series": "B"})
        return pl.DataFrame(data)

    @pytest.fixture
    def sample_numeric_multi_series_data(self) -> pl.DataFrame:
        """Create sample numeric multi-series data for testing."""
        data = []
        for x in range(1, 21):
            data.append({"x": x, "y": x * 2, "group": "Group1"})
            data.append({"x": x, "y": x * 1.5 + 5, "group": "Group2"})
            data.append({"x": x, "y": x * 0.8 + 10, "group": "Group3"})
        return pl.DataFrame(data)

    def test_template_spec(self, template: MultiLineTemplate) -> None:
        """Test template specification."""
        spec = template.spec
        assert spec.template_id == "P12_multi_line"
        assert spec.name == "Multi-Line Chart"
        assert spec.pattern_ids == ["P12"]
        assert "x" in spec.required_encodings
        assert "y" in spec.required_encodings
        assert "color" in spec.required_encodings  # Color is required for multi-line
        assert "strokeDash" in spec.optional_encodings

    def test_build_multi_line_chart(self, template: MultiLineTemplate, sample_multi_series_data: pl.DataFrame) -> None:
        """Test building a multi-line chart."""
        mapping = MappingConfig(x="date", y="value", color="series")
        chart = template.build(sample_multi_series_data, mapping)

        assert isinstance(chart, alt.Chart)
        # Check mark type - should be line with points
        chart_dict = chart.to_dict()
        assert chart_dict["mark"]["type"] == "line"
        assert chart_dict["mark"]["point"] is True
        # Check encodings
        assert "x" in chart_dict["encoding"]
        assert "y" in chart_dict["encoding"]
        assert "color" in chart_dict["encoding"]

    def test_temporal_axis_detection(self, template: MultiLineTemplate, sample_multi_series_data: pl.DataFrame) -> None:
        """Test automatic detection of temporal data."""
        mapping = MappingConfig(x="date", y="value", color="series")
        chart = template.build(sample_multi_series_data, mapping)

        # Check that temporal encoding is used for dates
        chart_dict = chart.to_dict()
        x_encoding = chart_dict["encoding"]["x"]
        assert x_encoding["type"] == "temporal" or ":T" in x_encoding["field"]

    def test_color_encoding_required(
        self, template: MultiLineTemplate, sample_numeric_multi_series_data: pl.DataFrame
    ) -> None:
        """Test color encoding for multiple series."""
        mapping = MappingConfig(x="x", y="y", color="group")
        chart = template.build(sample_numeric_multi_series_data, mapping)

        chart_dict = chart.to_dict()
        assert "color" in chart_dict["encoding"]
        color_encoding = chart_dict["encoding"]["color"]
        assert color_encoding["type"] == "nominal" or ":N" in color_encoding["field"]

    def test_auxiliary_mean_line_per_series(
        self, template: MultiLineTemplate, sample_numeric_multi_series_data: pl.DataFrame
    ) -> None:
        """Test applying mean line auxiliary element per series."""
        mapping = MappingConfig(x="x", y="y", color="group")
        chart = template.build(sample_numeric_multi_series_data, mapping)

        # Apply mean line - should compute per series
        chart_with_aux = template.apply_auxiliary(
            chart, [AuxiliaryElement.MEAN_LINE], sample_numeric_multi_series_data, mapping
        )

        # Should return a layer chart with mean lines per series
        assert isinstance(chart_with_aux, alt.LayerChart)

    def test_allowed_auxiliary_elements(self, template: MultiLineTemplate) -> None:
        """Test that multi-line chart allows appropriate auxiliary elements."""
        spec = template.spec
        allowed = spec.allowed_auxiliary

        # Multi-line charts should allow trend and reference lines
        assert AuxiliaryElement.MEAN_LINE in allowed
        assert AuxiliaryElement.MOVING_AVG in allowed
        assert AuxiliaryElement.TARGET_LINE in allowed
        assert AuxiliaryElement.MEDIAN_LINE in allowed

    def test_mapping_validation(self, template: MultiLineTemplate) -> None:
        """Test mapping validation for required encodings."""
        # Valid mapping with all required fields
        valid_mapping = MappingConfig(x="x", y="y", color="series")
        is_valid, missing = template.spec.validate_mapping(valid_mapping)
        assert is_valid
        assert len(missing) == 0

        # Invalid mapping missing color (required for multi-line)
        invalid_mapping = MappingConfig(x="x", y="y")
        is_valid, missing = template.spec.validate_mapping(invalid_mapping)
        assert not is_valid
        assert "color" in missing

    def test_consistent_color_scheme(
        self, template: MultiLineTemplate, sample_numeric_multi_series_data: pl.DataFrame
    ) -> None:
        """Test that consistent color scheme is used."""
        mapping = MappingConfig(x="x", y="y", color="group")
        chart = template.build(sample_numeric_multi_series_data, mapping)

        chart_dict = chart.to_dict()
        color_encoding = chart_dict["encoding"]["color"]
        # Should use category10 color scheme for consistency
        assert "scale" in color_encoding
        assert color_encoding["scale"]["scheme"] == "category10"
