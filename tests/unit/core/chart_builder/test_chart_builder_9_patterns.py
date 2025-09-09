"""Integration tests for ChartBuilder with all 9 patterns."""

import datetime
import random

import polars as pl
import pytest

from chartelier.core.chart_builder.builder import ChartBuilder
from chartelier.core.enums import PatternID
from chartelier.core.models import MappingConfig


class TestChartBuilder9Patterns:
    """Test suite for ChartBuilder with all 9 visualization patterns."""

    @pytest.fixture
    def chart_builder(self) -> ChartBuilder:
        """Create chart builder instance."""
        return ChartBuilder()

    @pytest.fixture
    def sample_time_series_data(self) -> pl.DataFrame:
        """Create sample time series data for pattern testing."""

        data = []
        base_date = datetime.date(2024, 1, 1)
        for i in range(30):
            date = base_date + datetime.timedelta(days=i)
            data.append(
                {
                    "date": date,
                    "value": 10 + i * 0.5 + (i % 7),  # Trend with weekly cycle
                    "series": "A" if i < 15 else "B",
                    "category": "Cat1" if i % 2 == 0 else "Cat2",
                    "region": "North" if i < 10 else ("Central" if i < 20 else "South"),
                }
            )
        return pl.DataFrame(data)

    @pytest.fixture
    def sample_category_data(self) -> pl.DataFrame:
        """Create sample categorical data for pattern testing."""

        data = []
        random.seed(42)
        categories = ["A", "B", "C", "D"]
        groups = ["Group1", "Group2", "Group3"]

        for cat in categories:
            for group in groups:
                for _ in range(20):
                    base_value = ord(cat) - ord("A") + 1  # A=1, B=2, C=3, D=4
                    group_offset = (ord(group[-1]) - ord("1")) * 10  # Group1=0, Group2=10, Group3=20
                    value = base_value * 10 + group_offset + random.normalvariate(0, 3)
                    data.append(
                        {"category": cat, "group": group, "value": value, "measurement": random.normalvariate(50, 15)}
                    )

        return pl.DataFrame(data)

    def test_all_patterns_have_templates(self, chart_builder: ChartBuilder) -> None:
        """Test that all 9 patterns have registered templates."""
        for pattern_id in PatternID:
            charts = chart_builder.get_available_charts(pattern_id)
            assert len(charts) > 0, f"No templates found for pattern {pattern_id.value}"

            # Check that default template exists
            assert pattern_id in chart_builder._pattern_defaults  # noqa: SLF001 — Test needs to verify internal state
            default_template_id = chart_builder._pattern_defaults[pattern_id]  # noqa: SLF001 — Test needs to verify internal state
            assert default_template_id in chart_builder._templates  # noqa: SLF001 — Test needs to verify internal state

    def test_pattern_p01_line_chart(self, chart_builder: ChartBuilder, sample_time_series_data: pl.DataFrame) -> None:
        """Test P01 (Transition only) - single time series."""
        pattern_charts = chart_builder.get_available_charts(PatternID.P01)
        assert len(pattern_charts) > 0

        template_id = "P01_line"
        mapping = MappingConfig(x="date", y="value")
        chart = chart_builder.build(template_id, sample_time_series_data, mapping)
        assert chart is not None

    def test_pattern_p02_bar_chart(self, chart_builder: ChartBuilder, sample_category_data: pl.DataFrame) -> None:
        """Test P02 (Difference only) - category comparison."""
        pattern_charts = chart_builder.get_available_charts(PatternID.P02)
        assert len(pattern_charts) > 0

        template_id = "P02_bar"
        mapping = MappingConfig(x="category", y="value")
        chart = chart_builder.build(template_id, sample_category_data, mapping)
        assert chart is not None

    def test_pattern_p03_histogram(self, chart_builder: ChartBuilder, sample_category_data: pl.DataFrame) -> None:
        """Test P03 (Overview only) - distribution."""
        pattern_charts = chart_builder.get_available_charts(PatternID.P03)
        assert len(pattern_charts) > 0

        template_id = "P03_histogram"
        mapping = MappingConfig(x="measurement")
        chart = chart_builder.build(template_id, sample_category_data, mapping)
        assert chart is not None

    def test_pattern_p12_multi_line(self, chart_builder: ChartBuilder, sample_time_series_data: pl.DataFrame) -> None:
        """Test P12 (Transition + Difference) - multiple time series comparison."""
        pattern_charts = chart_builder.get_available_charts(PatternID.P12)
        assert len(pattern_charts) > 0

        template_id = "P12_multi_line"
        mapping = MappingConfig(x="date", y="value", color="series")
        chart = chart_builder.build(template_id, sample_time_series_data, mapping)
        assert chart is not None

    def test_pattern_p13_facet_histogram(self, chart_builder: ChartBuilder, sample_category_data: pl.DataFrame) -> None:
        """Test P13 (Transition + Overview) - distribution over time/categories."""
        pattern_charts = chart_builder.get_available_charts(PatternID.P13)
        assert len(pattern_charts) > 0

        template_id = "P13_facet_histogram"
        mapping = MappingConfig(x="measurement", facet="group")
        chart = chart_builder.build(template_id, sample_category_data, mapping)
        assert chart is not None

    def test_pattern_p21_grouped_bar(self, chart_builder: ChartBuilder, sample_category_data: pl.DataFrame) -> None:
        """Test P21 (Difference + Transition) - grouped comparison."""
        pattern_charts = chart_builder.get_available_charts(PatternID.P21)
        assert len(pattern_charts) > 0

        template_id = "P21_grouped_bar"
        mapping = MappingConfig(x="category", y="value", color="group")
        chart = chart_builder.build(template_id, sample_category_data, mapping)
        assert chart is not None

    def test_pattern_p23_overlay_histogram(
        self, chart_builder: ChartBuilder, sample_category_data: pl.DataFrame
    ) -> None:
        """Test P23 (Difference + Overview) - category-wise distribution comparison."""
        pattern_charts = chart_builder.get_available_charts(PatternID.P23)
        assert len(pattern_charts) > 0

        template_id = "P23_overlay_histogram"
        mapping = MappingConfig(x="measurement", color="group")
        chart = chart_builder.build(template_id, sample_category_data, mapping)
        assert chart is not None

    def test_pattern_p31_small_multiples(
        self, chart_builder: ChartBuilder, sample_time_series_data: pl.DataFrame
    ) -> None:
        """Test P31 (Overview + Transition) - overall picture over time."""
        pattern_charts = chart_builder.get_available_charts(PatternID.P31)
        assert len(pattern_charts) > 0

        template_id = "P31_small_multiples"
        mapping = MappingConfig(x="date", y="value", facet="region")
        chart = chart_builder.build(template_id, sample_time_series_data, mapping)
        assert chart is not None

    def test_pattern_p32_box_plot(self, chart_builder: ChartBuilder, sample_category_data: pl.DataFrame) -> None:
        """Test P32 (Overview + Difference) - distribution comparison between categories."""
        pattern_charts = chart_builder.get_available_charts(PatternID.P32)
        assert len(pattern_charts) > 0

        template_id = "P32_box_plot"
        mapping = MappingConfig(x="group", y="measurement")
        chart = chart_builder.build(template_id, sample_category_data, mapping)
        assert chart is not None

    def test_template_specs_consistency(self, chart_builder: ChartBuilder) -> None:
        """Test that template specifications are consistent."""
        for template_id, template in chart_builder._templates.items():  # noqa: SLF001 — Test needs to verify internal state
            spec = template.spec

            # Template ID should match registration key
            assert spec.template_id == template_id

            # Should have at least one pattern ID
            assert len(spec.pattern_ids) > 0

            # Should have at least one required encoding
            assert len(spec.required_encodings) > 0

            # Pattern IDs should be valid
            for pattern_id in spec.pattern_ids:
                assert pattern_id in [p.value for p in PatternID]

    def test_template_registration_completeness(self, chart_builder: ChartBuilder) -> None:
        """Test that template registration is complete for all patterns."""
        expected_templates = {
            "P01_line": ["P01"],
            "P02_bar": ["P02"],
            "P03_histogram": ["P03"],
            "P12_multi_line": ["P12"],
            "P13_facet_histogram": ["P13"],
            "P21_grouped_bar": ["P21"],
            "P23_overlay_histogram": ["P23"],
            "P31_small_multiples": ["P31"],
            "P32_box_plot": ["P32"],
        }

        # Check all expected templates are registered
        for template_id, expected_patterns in expected_templates.items():
            assert template_id in chart_builder._templates  # noqa: SLF001 — Test needs to verify internal state
            template = chart_builder._templates[template_id]  # noqa: SLF001 — Test needs to verify internal state
            assert template.spec.pattern_ids == expected_patterns

    def test_fallback_behavior(self, chart_builder: ChartBuilder) -> None:
        """Test that fallback templates are properly configured."""
        for pattern_id in PatternID:
            # Should have a default template
            assert pattern_id in chart_builder._pattern_defaults  # noqa: SLF001 — Test needs to verify internal state
            default_template_id = chart_builder._pattern_defaults[pattern_id]  # noqa: SLF001 — Test needs to verify internal state

            # Default template should exist
            assert default_template_id in chart_builder._templates  # noqa: SLF001 — Test needs to verify internal state

            # Default template should support the pattern
            template = chart_builder._templates[default_template_id]  # noqa: SLF001 — Test needs to verify internal state
            assert pattern_id.value in template.spec.pattern_ids
