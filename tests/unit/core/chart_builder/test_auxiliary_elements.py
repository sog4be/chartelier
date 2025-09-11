"""Unit tests for auxiliary elements functionality."""

import altair as alt
import polars as pl
import pytest

from chartelier.core.chart_builder.builder import ChartBuilder
from chartelier.core.enums import AuxiliaryElement, PatternID
from chartelier.core.models import MappingConfig


class TestTargetLineAuxiliary:
    """Test target_line auxiliary element functionality."""

    @pytest.fixture
    def sample_data(self) -> pl.DataFrame:
        """Create sample data for testing."""
        return pl.DataFrame(
            {
                "x": ["A", "B", "C", "D", "E"],
                "y": [10, 25, 15, 30, 20],
                "category": ["cat1", "cat1", "cat2", "cat2", "cat1"],
            }
        )

    @pytest.fixture
    def time_series_data(self) -> pl.DataFrame:
        """Create time series data for testing."""
        return pl.DataFrame(
            {
                "date": pl.date_range(
                    start=pl.date(2024, 1, 1),
                    end=pl.date(2024, 1, 10),
                    interval="1d",
                    eager=True,
                ),
                "value": [100, 110, 105, 115, 120, 118, 125, 130, 128, 135],
            }
        )

    @pytest.fixture
    def chart_builder(self) -> ChartBuilder:
        """Create a ChartBuilder instance."""
        return ChartBuilder()

    def test_target_line_default_percentile(self, chart_builder: ChartBuilder, sample_data: pl.DataFrame) -> None:
        """Test target_line with default 75th percentile."""
        mapping = MappingConfig(x="x", y="y")

        # Build chart with target_line auxiliary
        chart = chart_builder.build(
            template_id="P02_bar",
            data=sample_data,
            mapping=mapping,
            auxiliary=["target_line"],
        )

        # Check that the chart is a LayerChart (base + target line)
        assert isinstance(chart, alt.LayerChart)

        # Verify the chart has 2 layers (bar chart + rule)
        assert len(chart.layer) == 2

        # The second layer should be a rule mark
        assert chart.layer[1].mark.type == "rule"

    def test_target_line_with_custom_value(self, chart_builder: ChartBuilder, sample_data: pl.DataFrame) -> None:
        """Test target_line with custom target value."""
        mapping = MappingConfig(x="x", y="y")

        # Build chart with custom target value
        chart = chart_builder.build(
            template_id="P02_bar",
            data=sample_data,
            mapping=mapping,
            auxiliary=["target_line"],
            auxiliary_config={"target_line": {"target_value": 22}},
        )

        # Check that the chart is a LayerChart
        assert isinstance(chart, alt.LayerChart)

        # Verify the chart has 2 layers
        assert len(chart.layer) == 2

        # The second layer should be a rule mark
        assert chart.layer[1].mark.type == "rule"

        # Check the data in the rule layer
        rule_data = chart.layer[1].data["values"]
        assert rule_data[0]["target"] == 22

    def test_target_line_with_custom_percentile(self, chart_builder: ChartBuilder, sample_data: pl.DataFrame) -> None:
        """Test target_line with custom percentile."""
        mapping = MappingConfig(x="x", y="y")

        # Build chart with custom percentile (median)
        chart = chart_builder.build(
            template_id="P02_bar",
            data=sample_data,
            mapping=mapping,
            auxiliary=["target_line"],
            auxiliary_config={"target_line": {"percentile": 0.5}},
        )

        # Check that the chart is a LayerChart
        assert isinstance(chart, alt.LayerChart)

        # The rule should be at the median value (20)
        rule_data = chart.layer[1].data["values"]
        expected_median = sample_data["y"].median()
        assert rule_data[0]["target"] == expected_median

    def test_target_line_with_label(self, chart_builder: ChartBuilder, sample_data: pl.DataFrame) -> None:
        """Test target_line with text label."""
        mapping = MappingConfig(x="x", y="y")

        # Build chart with target line and label
        chart = chart_builder.build(
            template_id="P02_bar",
            data=sample_data,
            mapping=mapping,
            auxiliary=["target_line"],
            auxiliary_config={
                "target_line": {
                    "target_value": 25,
                    "label": "Target Goal",
                }
            },
        )

        # Check that the chart is a LayerChart with 3 layers (bar + rule + text)
        assert isinstance(chart, alt.LayerChart)
        assert len(chart.layer) == 3

        # The third layer should be a text mark
        assert chart.layer[2].mark.type == "text"

        # Check the label text
        text_data = chart.layer[2].data["values"]
        assert text_data[0]["label"] == "Target Goal"
        assert text_data[0]["target"] == 25

    def test_target_line_on_line_chart(self, chart_builder: ChartBuilder, time_series_data: pl.DataFrame) -> None:
        """Test target_line on a line chart."""
        mapping = MappingConfig(x="date", y="value")

        # Build line chart with target_line
        chart = chart_builder.build(
            template_id="P01_line",
            data=time_series_data,
            mapping=mapping,
            auxiliary=["target_line"],
            auxiliary_config={"target_line": {"target_value": 120}},
        )

        # Check that the chart is a LayerChart
        assert isinstance(chart, alt.LayerChart)
        assert len(chart.layer) == 2

        # First layer should be line, second should be rule
        assert chart.layer[0].mark.type == "line"
        assert chart.layer[1].mark.type == "rule"

    def test_multiple_auxiliary_elements_limited(self, chart_builder: ChartBuilder, sample_data: pl.DataFrame) -> None:
        """Test that auxiliary elements are limited to max 3."""
        mapping = MappingConfig(x="x", y="y")

        # Try to add more than 3 auxiliary elements (when we have more types)
        # For now, we only have target_line, so this just tests the single element
        chart = chart_builder.build(
            template_id="P02_bar",
            data=sample_data,
            mapping=mapping,
            auxiliary=["target_line"],  # Only one type available currently
        )

        # Should work fine with one auxiliary element
        assert isinstance(chart, alt.LayerChart)

    def test_target_line_not_allowed_on_histogram(self, chart_builder: ChartBuilder, sample_data: pl.DataFrame) -> None:
        """Test that target_line is not applied to histogram templates."""
        mapping = MappingConfig(x="y")  # Histogram only needs x

        # Build histogram (P03) - should not add target_line even if requested
        chart = chart_builder.build(
            template_id="P03_histogram",
            data=sample_data,
            mapping=mapping,
            auxiliary=["target_line"],  # This should be ignored
        )

        # Should return a simple Chart, not LayerChart (no auxiliary applied)
        assert isinstance(chart, alt.Chart)
        assert chart.mark.type == "bar"  # Histogram uses bar mark

    @pytest.mark.parametrize(
        ("template_id", "pattern_id"),
        [
            ("P01_line", PatternID.P01),
            ("P02_bar", PatternID.P02),
            ("P12_multi_line", PatternID.P12),
            ("P21_grouped_bar", PatternID.P21),
            ("P31_small_multiples", PatternID.P31),
            ("P32_box_plot", PatternID.P32),
        ],
    )
    def test_target_line_supported_templates(
        self,
        chart_builder: ChartBuilder,
        sample_data: pl.DataFrame,
        template_id: str,
        pattern_id: PatternID,
    ) -> None:
        """Test that target_line is supported on appropriate templates."""
        # Get template spec
        spec = chart_builder.get_template_spec(template_id)
        assert spec is not None

        # Verify target_line is in allowed auxiliary
        assert AuxiliaryElement.TARGET_LINE in spec.allowed_auxiliary

        # Verify the template supports the expected pattern
        assert pattern_id.value in spec.pattern_ids

    def test_invalid_percentile_ignored(self, chart_builder: ChartBuilder, sample_data: pl.DataFrame) -> None:
        """Test that invalid percentile values are ignored and default is used."""
        mapping = MappingConfig(x="x", y="y")

        # Build chart with invalid percentile (> 1)
        chart = chart_builder.build(
            template_id="P02_bar",
            data=sample_data,
            mapping=mapping,
            auxiliary=["target_line"],
            auxiliary_config={"target_line": {"percentile": 1.5}},  # Invalid
        )

        # Should still create a chart with default percentile
        assert isinstance(chart, alt.LayerChart)

        # The rule should be at the default 75th percentile
        rule_data = chart.layer[1].data["values"]
        expected_value = sample_data["y"].quantile(0.75)
        assert rule_data[0]["target"] == expected_value
