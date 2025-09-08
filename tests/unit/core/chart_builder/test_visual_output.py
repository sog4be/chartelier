"""Visual output tests for chart templates - generates actual images for manual inspection."""

import os
from pathlib import Path

import polars as pl
import pytest

from chartelier.core.chart_builder import ChartBuilder
from chartelier.core.enums import OutputFormat
from chartelier.core.models import MappingConfig
from chartelier.infra.logging import get_logger

logger = get_logger(__name__)


class TestVisualOutput:
    """Test cases that generate visual outputs for manual inspection."""

    @pytest.fixture
    def output_dir(self):
        """Create output directory for test images."""
        output_path = Path("test_outputs/charts")
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path

    @pytest.fixture
    def builder(self):
        """Create a ChartBuilder instance with all templates registered."""
        # ChartBuilder now automatically registers all templates in __init__
        return ChartBuilder()

    @pytest.fixture
    def time_series_data(self):
        """Create sample time series data for line chart."""
        import datetime  # noqa: PLC0415
        import random  # noqa: PLC0415

        dates = pl.date_range(
            datetime.date(2024, 1, 1),
            datetime.date(2024, 3, 31),  # 3 months for cleaner visualization
            interval="1d",
            eager=True,
        )

        # Create synthetic data with trend and seasonality
        random.seed(42)
        values = []
        for i in range(len(dates)):
            # Trend component
            trend = i * 0.5
            # Seasonal component
            import math  # noqa: PLC0415

            seasonal = 10 * math.sin(2 * math.pi * i / 30)  # 30-day cycle
            # Random noise
            noise = random.gauss(0, 2)
            value = 100 + trend + seasonal + noise
            values.append(value)

        return pl.DataFrame(
            {
                "date": [d.strftime("%Y-%m-%d") for d in dates],
                "value": values,
                "day_index": list(range(len(dates))),  # Add numeric index for regression
            }
        )

    @pytest.fixture
    def categorical_data(self):
        """Create sample categorical data for bar chart."""
        return pl.DataFrame(
            {
                "department": [
                    "Engineering",
                    "Marketing",
                    "Sales",
                    "Support",
                    "HR",
                    "Finance",
                ],
                "headcount": [45, 32, 28, 55, 12, 18],
            }
        )

    @pytest.fixture
    def distribution_data(self):
        """Create sample distribution data for histogram."""
        import random  # noqa: PLC0415

        random.seed(42)
        # Generate normal distribution data simulating test scores
        scores = [random.gauss(75, 12) for _ in range(500)]
        # Clip to valid range
        scores = [max(0, min(100, score)) for score in scores]

        return pl.DataFrame({"test_scores": scores})

    @pytest.mark.skipif(
        os.getenv("SKIP_VISUAL_TESTS", "true").lower() == "true",
        reason="Visual tests skipped by default. Set SKIP_VISUAL_TESTS=false to run.",
    )
    def test_p01_line_chart(self, builder, time_series_data, output_dir):
        """Generate P01 line chart with trend analysis."""
        mapping = MappingConfig(x="date", y="value")

        # Build chart with mean line (regression doesn't work with string dates)
        chart = builder.build(
            template_id="P01_line",
            data=time_series_data,
            mapping=mapping,
            auxiliary=["mean_line", "median_line"],
            width=1200,
            height=600,
        )

        # Export as SVG
        svg_output = builder.export(chart, OutputFormat.SVG)
        svg_path = output_dir / "P01_line_chart.svg"
        svg_path.write_text(svg_output)

        # Try PNG export if available
        try:
            png_output = builder.export(chart, OutputFormat.PNG, dpi=150)
            png_path = output_dir / "P01_line_chart.png"

            import base64  # noqa: PLC0415

            png_data = base64.b64decode(png_output)
            png_path.write_bytes(png_data)
            logger.info("Generated P01 line chart", svg=str(svg_path), png=str(png_path))
        except Exception as e:  # noqa: BLE001
            logger.info("Generated P01 line chart", svg=str(svg_path), png_error=str(e))

        assert svg_path.exists()

    @pytest.mark.skipif(
        os.getenv("SKIP_VISUAL_TESTS", "true").lower() == "true",
        reason="Visual tests skipped by default. Set SKIP_VISUAL_TESTS=false to run.",
    )
    def test_p02_bar_chart(self, builder, categorical_data, output_dir):
        """Generate P02 bar chart for category comparison."""
        mapping = MappingConfig(x="department", y="headcount")

        # Build chart with mean line to show average
        chart = builder.build(
            template_id="P02_bar",
            data=categorical_data,
            mapping=mapping,
            auxiliary=["mean_line"],
            width=1200,
            height=600,
        )

        # Export as SVG
        svg_output = builder.export(chart, OutputFormat.SVG)
        svg_path = output_dir / "P02_bar_chart.svg"
        svg_path.write_text(svg_output)

        # Try PNG export if available
        try:
            png_output = builder.export(chart, OutputFormat.PNG, dpi=150)
            png_path = output_dir / "P02_bar_chart.png"

            import base64  # noqa: PLC0415

            png_data = base64.b64decode(png_output)
            png_path.write_bytes(png_data)
            logger.info("Generated P02 bar chart", svg=str(svg_path), png=str(png_path))
        except Exception as e:  # noqa: BLE001
            logger.info("Generated P02 bar chart", svg=str(svg_path), png_error=str(e))

        assert svg_path.exists()

    @pytest.mark.skipif(
        os.getenv("SKIP_VISUAL_TESTS", "true").lower() == "true",
        reason="Visual tests skipped by default. Set SKIP_VISUAL_TESTS=false to run.",
    )
    def test_p03_histogram(self, builder, distribution_data, output_dir):
        """Generate P03 histogram for distribution analysis."""
        mapping = MappingConfig(x="test_scores")

        # Build histogram with mean and median lines
        chart = builder.build(
            template_id="P03_histogram",
            data=distribution_data,
            mapping=mapping,
            auxiliary=["mean_line", "median_line"],
            width=1200,
            height=600,
        )

        # Export as SVG
        svg_output = builder.export(chart, OutputFormat.SVG)
        svg_path = output_dir / "P03_histogram.svg"
        svg_path.write_text(svg_output)

        # Try PNG export if available
        try:
            png_output = builder.export(chart, OutputFormat.PNG, dpi=150)
            png_path = output_dir / "P03_histogram.png"

            import base64  # noqa: PLC0415

            png_data = base64.b64decode(png_output)
            png_path.write_bytes(png_data)
            logger.info("Generated P03 histogram", svg=str(svg_path), png=str(png_path))
        except Exception as e:  # noqa: BLE001
            logger.info("Generated P03 histogram", svg=str(svg_path), png_error=str(e))

        assert svg_path.exists()

    @pytest.mark.skipif(
        os.getenv("SKIP_VISUAL_TESTS", "true").lower() == "true",
        reason="Visual tests skipped by default. Set SKIP_VISUAL_TESTS=false to run.",
    )
    def test_all_templates_overview(self, builder, output_dir):
        """Generate an overview showing all three template types."""
        # Create a summary DataFrame for the test results
        summary_data = pl.DataFrame(
            {
                "template": ["P01_line", "P02_bar", "P03_histogram"],
                "pattern": ["Transition", "Difference", "Overview"],
                "description": [
                    "Time series with trend",
                    "Category comparison",
                    "Distribution analysis",
                ],
            }
        )

        # Save summary as CSV for reference
        summary_path = output_dir / "template_overview.csv"
        summary_data.write_csv(summary_path)

        logger.info(
            "Generated template overview",
            templates=summary_data["template"].to_list(),
            output_dir=str(output_dir),
        )

        assert summary_path.exists()


def test_visual_output_instructions():
    """Display instructions for running visual tests.

    VISUAL OUTPUT TEST INSTRUCTIONS
    ================================

    To generate chart images for manual inspection:
    1. Run: SKIP_VISUAL_TESTS=false pytest tests/unit/core/chart_builder/test_visual_output.py -v -s
    2. Check the generated images in: test_outputs/charts/
    3. Images will be saved in both SVG and PNG formats (if vl-convert is available)

    Generated files:
    - P01_line_chart.svg/png - Line chart showing time series with mean and median lines
    - P02_bar_chart.svg/png - Bar chart comparing categories with mean line
    - P03_histogram.svg/png - Histogram showing distribution with mean and median
    - template_overview.csv - Summary of all templates

    Each chart demonstrates:
    - The primary visualization pattern (Transition/Difference/Overview)
    - Auxiliary elements appropriate for that chart type
    - Compliance with Visualization Policy (e.g., zero origin for bars)
    """
    instructions = test_visual_output_instructions.__doc__
    logger.info("Visual test instructions", instructions=instructions)
