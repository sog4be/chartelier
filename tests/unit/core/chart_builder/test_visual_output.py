"""Visual output tests for chart templates - generates actual images for manual inspection."""

import os
from pathlib import Path

import polars as pl
import pytest

from chartelier.core.chart_builder import ChartBuilder
from chartelier.core.chart_builder.templates import LineTemplate
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
        """Create a ChartBuilder instance with templates."""
        builder = ChartBuilder()
        builder.register_template("P01_line", LineTemplate())
        return builder

    @pytest.fixture
    def time_series_data(self):
        """Create sample time series data."""
        import datetime  # noqa: PLC0415
        import random  # noqa: PLC0415

        dates = pl.date_range(
            datetime.date(2024, 1, 1),
            datetime.date(2024, 12, 31),
            interval="1d",
            eager=True,
        )

        # Create synthetic data with trend and seasonality
        random.seed(42)
        values = []
        for i in range(len(dates)):
            # Trend component
            trend = i * 0.5
            # Seasonal component (simple sine wave approximation)
            import math  # noqa: PLC0415

            seasonal = 10 * math.sin(2 * math.pi * i / 30)  # 30-day cycle
            # Random noise
            noise = random.gauss(0, 2)
            value = 100 + trend + seasonal + noise
            values.append(value)

        return pl.DataFrame(
            {
                "date": [d.strftime("%Y-%m-%d") for d in dates],  # Convert to string
                "value": values,
                "category": ["A"] * len(dates),
            }
        )

    @pytest.fixture
    def multi_series_data(self):
        """Create sample multi-series data."""
        data = []
        categories = ["Product A", "Product B", "Product C"]

        for month in range(1, 13):
            for category in categories:
                base_value = {"Product A": 100, "Product B": 80, "Product C": 120}[category]
                value = base_value + (month - 1) * 5 + (10 if month > 6 else 0)
                data.append(
                    {
                        "month": f"2024-{month:02d}-01",
                        "category": category,
                        "sales": value + (month % 3) * 5,
                    }
                )

        return pl.DataFrame(data)

    @pytest.fixture
    def categorical_data(self):
        """Create sample categorical data."""
        return pl.DataFrame(
            {
                "category": ["A", "B", "C", "D", "E"],
                "value": [45, 32, 28, 55, 40],
                "group": ["Group 1", "Group 1", "Group 2", "Group 2", "Group 3"],
            }
        )

    @pytest.mark.skipif(
        os.getenv("SKIP_VISUAL_TESTS", "true").lower() == "true",
        reason="Visual tests skipped by default. Set SKIP_VISUAL_TESTS=false to run.",
    )
    def test_line_chart_basic(self, builder, time_series_data, output_dir):
        """Generate basic line chart."""
        mapping = MappingConfig(x="date", y="value")

        chart = builder.build(
            template_id="P01_line",
            data=time_series_data,
            mapping=mapping,
            width=1200,
            height=600,
        )

        # Save as SVG
        svg_output = builder.export(chart, OutputFormat.SVG)
        svg_path = output_dir / "P01_line_basic.svg"
        svg_path.write_text(svg_output)

        # Try to save as PNG if vl-convert is available
        try:
            png_output = builder.export(chart, OutputFormat.PNG, dpi=150)
            png_path = output_dir / "P01_line_basic.png"

            # Decode base64 and save
            import base64  # noqa: PLC0415

            png_data = base64.b64decode(png_output)
            png_path.write_bytes(png_data)

            logger.info("Saved PNG", path=str(png_path))
        except Exception as e:  # noqa: BLE001
            logger.warning("PNG export failed", error=str(e))

        logger.info("Saved SVG", path=str(svg_path))
        assert svg_path.exists()

    @pytest.mark.skipif(
        os.getenv("SKIP_VISUAL_TESTS", "true").lower() == "true",
        reason="Visual tests skipped by default. Set SKIP_VISUAL_TESTS=false to run.",
    )
    def test_line_chart_with_auxiliary(self, builder, time_series_data, output_dir):
        """Generate line chart with auxiliary elements."""
        mapping = MappingConfig(x="date", y="value")

        # Test with mean line
        chart = builder.build(
            template_id="P01_line",
            data=time_series_data[:30],  # Use first 30 days for cleaner visualization
            mapping=mapping,
            auxiliary=["mean_line", "regression"],
            width=1200,
            height=600,
        )

        svg_output = builder.export(chart, OutputFormat.SVG)
        svg_path = output_dir / "P01_line_with_auxiliary.svg"
        svg_path.write_text(svg_output)

        logger.info("Saved SVG with auxiliary elements", path=str(svg_path))
        assert svg_path.exists()

    @pytest.mark.skipif(
        os.getenv("SKIP_VISUAL_TESTS", "true").lower() == "true",
        reason="Visual tests skipped by default. Set SKIP_VISUAL_TESTS=false to run.",
    )
    def test_line_chart_multi_series(self, builder, multi_series_data, output_dir):
        """Generate multi-series line chart."""
        mapping = MappingConfig(x="month", y="sales", color="category")

        chart = builder.build(
            template_id="P01_line",
            data=multi_series_data,
            mapping=mapping,
            width=1200,
            height=600,
        )

        svg_output = builder.export(chart, OutputFormat.SVG)
        svg_path = output_dir / "P01_line_multi_series.svg"
        svg_path.write_text(svg_output)

        logger.info("Saved multi-series SVG", path=str(svg_path))
        assert svg_path.exists()

    @pytest.mark.skipif(
        os.getenv("SKIP_VISUAL_TESTS", "true").lower() == "true",
        reason="Visual tests skipped by default. Set SKIP_VISUAL_TESTS=false to run.",
    )
    def test_export_formats_comparison(self, builder, categorical_data, output_dir):
        """Compare PNG and SVG outputs."""
        mapping = MappingConfig(x="category", y="value")

        chart = builder.build(
            template_id="P01_line",
            data=categorical_data,
            mapping=mapping,
            width=800,
            height=400,
        )

        # Export in different DPI settings for PNG
        dpi_settings = [96, 150, 300]

        for dpi in dpi_settings:
            try:
                png_output = builder.export(chart, OutputFormat.PNG, dpi=dpi)
                png_path = output_dir / f"comparison_dpi_{dpi}.png"

                import base64  # noqa: PLC0415

                png_data = base64.b64decode(png_output)
                png_path.write_bytes(png_data)

                # Get file size for comparison
                file_size_kb = png_path.stat().st_size / 1024
                logger.info("Saved PNG", dpi=dpi, path=str(png_path), size_kb=f"{file_size_kb:.1f}")
            except Exception as e:  # noqa: BLE001
                logger.warning("PNG export failed", dpi=dpi, error=str(e))

        # Also save SVG for comparison
        svg_output = builder.export(chart, OutputFormat.SVG)
        svg_path = output_dir / "comparison.svg"
        svg_path.write_text(svg_output)

        file_size_kb = svg_path.stat().st_size / 1024
        logger.info("Saved SVG", path=str(svg_path), size_kb=f"{file_size_kb:.1f}")

        assert svg_path.exists()


def test_visual_output_instructions():
    """Display instructions for running visual tests.

    VISUAL OUTPUT TEST INSTRUCTIONS
    ================================

    To generate chart images for manual inspection:
    1. Run: SKIP_VISUAL_TESTS=false pytest tests/unit/core/chart_builder/test_visual_output.py -v -s
    2. Check the generated images in: test_outputs/charts/
    3. Images will be saved in both SVG and PNG formats (if vl-convert is available)

    Generated files:
    - P01_line_basic.svg/png - Basic line chart
    - P01_line_with_auxiliary.svg - Line chart with mean line and regression
    - P01_line_multi_series.svg - Multi-series line chart
    - comparison_dpi_*.png - PNG exports at different DPI settings
    - comparison.svg - SVG for format comparison
    """
    instructions = test_visual_output_instructions.__doc__
    logger.info("Visual test instructions", instructions=instructions)
