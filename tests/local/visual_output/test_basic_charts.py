"""Basic visual output tests for chart templates - generates representative images for manual inspection.

These tests are designed for local development and manual verification only.
They generate actual chart images to verify visual output quality.

Run with: pytest tests/local/visual_output/test_basic_charts.py -v
"""

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
        output_path = Path("tests/local/visual_output/charts")
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

    @pytest.fixture
    def multi_series_data(self):
        """Create sample multi-series time data for P12."""
        import datetime  # noqa: PLC0415
        import random  # noqa: PLC0415

        dates = pl.date_range(
            datetime.date(2024, 1, 1),
            datetime.date(2024, 2, 29),  # 2 months
            interval="1d",
            eager=True,
        )

        random.seed(42)
        data = []
        for i, date in enumerate(dates):
            # Series A: increasing trend
            value_a = 50 + i * 0.8 + random.gauss(0, 3)
            data.append({"date": date.strftime("%Y-%m-%d"), "value": value_a, "series": "Revenue"})

            # Series B: decreasing trend
            value_b = 80 - i * 0.5 + random.gauss(0, 4)
            data.append({"date": date.strftime("%Y-%m-%d"), "value": value_b, "series": "Cost"})

            # Series C: stable with noise
            value_c = 30 + random.gauss(0, 2)
            data.append({"date": date.strftime("%Y-%m-%d"), "value": value_c, "series": "Profit"})

        return pl.DataFrame(data)

    @pytest.fixture
    def grouped_data(self):
        """Create sample grouped data for P21."""
        import random  # noqa: PLC0415

        random.seed(42)
        data = []
        quarters = ["Q1", "Q2", "Q3", "Q4"]
        regions = ["North", "South", "East", "West"]

        for quarter in quarters:
            for region in regions:
                # Different performance patterns per region
                base = {"North": 100, "South": 85, "East": 95, "West": 75}[region]
                growth = quarters.index(quarter) * 10
                noise = random.gauss(0, 8)
                value = base + growth + noise
                data.append({"quarter": quarter, "region": region, "sales": value})

        return pl.DataFrame(data)

    @pytest.fixture
    def category_distribution_data(self):
        """Create sample data for P23 overlay histogram."""
        import random  # noqa: PLC0415

        random.seed(42)
        data = []

        # Group A: Normal distribution around 70
        for _ in range(200):
            data.append({"value": random.gauss(70, 12), "group": "Group A"})

        # Group B: Normal distribution around 85
        for _ in range(200):
            data.append({"value": random.gauss(85, 10), "group": "Group B"})

        # Group C: Normal distribution around 60
        for _ in range(200):
            data.append({"value": random.gauss(60, 15), "group": "Group C"})

        return pl.DataFrame(data)

    @pytest.fixture
    def box_plot_data(self):
        """Create sample data for P32 box plot."""
        import random  # noqa: PLC0415

        random.seed(42)
        data = []
        departments = ["Engineering", "Marketing", "Sales", "Support"]

        # Different salary distributions per department
        salary_params = {
            "Engineering": (95000, 25000),  # mean, std
            "Marketing": (75000, 18000),
            "Sales": (65000, 20000),
            "Support": (55000, 12000),
        }

        for dept in departments:
            mean, std = salary_params[dept]
            for _ in range(50):  # 50 employees per department
                salary = max(30000, random.gauss(mean, std))  # Floor at 30k
                data.append({"department": dept, "salary": salary})

        return pl.DataFrame(data)

    @pytest.fixture
    def facet_data(self):
        """Create sample data for P13 facet histogram."""
        import random  # noqa: PLC0415

        random.seed(42)
        data = []
        categories = ["Electronics", "Clothing", "Food", "Books"]

        for category in categories:
            # Different distribution centers for each category
            center = {"Electronics": 75, "Clothing": 65, "Food": 80, "Books": 70}[category]
            spread = {"Electronics": 15, "Clothing": 12, "Food": 8, "Books": 10}[category]

            for _ in range(100):
                value = random.gauss(center, spread)
                data.append({"category": category, "value": value})

        return pl.DataFrame(data)

    @pytest.fixture
    def small_multiples_data(self):
        """Create sample data for P31 small multiples."""
        import random  # noqa: PLC0415

        random.seed(42)
        data = []
        regions = ["North", "South", "East", "West"]
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
        products = ["Product A", "Product B"]

        for region in regions:
            for month in months:
                for product in products:
                    # Different baseline performance per region
                    base = {"North": 100, "South": 85, "East": 90, "West": 80}[region]
                    # Monthly growth factor
                    month_factor = months.index(month) * 5
                    # Product performance difference
                    product_factor = 10 if product == "Product A" else 0
                    # Random variation
                    noise = random.gauss(0, 8)

                    value = base + month_factor + product_factor + noise
                    data.append({"region": region, "month": month, "product": product, "value": value})

        return pl.DataFrame(data)

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

        # Override title with business context
        chart = chart.properties(title="Daily Revenue Trend - Q1 2024 Performance Analysis")

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

        # Override title with business context
        chart = chart.properties(title="Department Headcount Distribution - 2024 Organizational Review")

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

        # Override title with business context
        chart = chart.properties(title="Employee Performance Score Distribution - Annual Review 2024")

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

    def test_p12_multi_line_chart(self, builder, multi_series_data, output_dir):
        """Generate P12 multi-line chart for multiple time series comparison."""
        mapping = MappingConfig(x="date", y="value", color="series")

        # Build chart with mean lines per series (regression removed)
        chart = builder.build(
            template_id="P12_multi_line",
            data=multi_series_data,
            mapping=mapping,
            auxiliary=["mean_line"],
            width=1200,
            height=600,
        )

        # Override title with business context
        chart = chart.properties(title="Revenue vs Cost vs Profit Trends - Q1 2024 Financial Summary")

        # Export as SVG
        svg_output = builder.export(chart, OutputFormat.SVG)
        svg_path = output_dir / "P12_multi_line_chart.svg"
        svg_path.write_text(svg_output)

        # Try PNG export if available
        try:
            png_output = builder.export(chart, OutputFormat.PNG, dpi=150)
            png_path = output_dir / "P12_multi_line_chart.png"

            import base64  # noqa: PLC0415

            png_data = base64.b64decode(png_output)
            png_path.write_bytes(png_data)
            logger.info("Generated P12 multi-line chart", svg=str(svg_path), png=str(png_path))
        except Exception as e:  # noqa: BLE001
            logger.info("Generated P12 multi-line chart", svg=str(svg_path), png_error=str(e))

        assert svg_path.exists()

    def test_p13_facet_histogram(self, builder, facet_data, output_dir):
        """Generate P13 facet histogram for distribution changes over categories."""
        mapping = MappingConfig(x="value", facet="category")

        chart = builder.build(
            template_id="P13_facet_histogram",
            data=facet_data,
            mapping=mapping,
            width=1200,
            height=800,
        )

        # Override title with business context
        chart = chart.properties(title="Score Distribution by Product Category - Q4 2024 Analysis")

        # Export as SVG
        svg_output = builder.export(chart, OutputFormat.SVG)
        svg_path = output_dir / "P13_facet_histogram.svg"
        svg_path.write_text(svg_output)

        # Try PNG export if available
        try:
            png_output = builder.export(chart, OutputFormat.PNG, dpi=150)
            png_path = output_dir / "P13_facet_histogram.png"

            import base64  # noqa: PLC0415

            png_data = base64.b64decode(png_output)
            png_path.write_bytes(png_data)
            logger.info("Generated P13 facet histogram", svg=str(svg_path), png=str(png_path))
        except Exception as e:  # noqa: BLE001
            logger.info("Generated P13 facet histogram", svg=str(svg_path), png_error=str(e))

        assert svg_path.exists()

    def test_p21_grouped_bar_chart(self, builder, grouped_data, output_dir):
        """Generate P21 grouped bar chart for category comparison over time."""
        mapping = MappingConfig(x="quarter", y="sales", color="region")

        # Build chart with mean line across all groups
        chart = builder.build(
            template_id="P21_grouped_bar",
            data=grouped_data,
            mapping=mapping,
            auxiliary=["mean_line"],
            width=1200,
            height=800,
        )

        # Override title with business context
        chart = chart.properties(title="Quarterly Sales Performance by Region - 2024 Target Achievement")

        # Export as SVG
        svg_output = builder.export(chart, OutputFormat.SVG)
        svg_path = output_dir / "P21_grouped_bar_chart.svg"
        svg_path.write_text(svg_output)

        # Try PNG export if available
        try:
            png_output = builder.export(chart, OutputFormat.PNG, dpi=150)
            png_path = output_dir / "P21_grouped_bar_chart.png"

            import base64  # noqa: PLC0415

            png_data = base64.b64decode(png_output)
            png_path.write_bytes(png_data)
            logger.info("Generated P21 grouped bar chart", svg=str(svg_path), png=str(png_path))
        except Exception as e:  # noqa: BLE001
            logger.info("Generated P21 grouped bar chart", svg=str(svg_path), png_error=str(e))

        assert svg_path.exists()

    def test_p23_overlay_histogram(self, builder, category_distribution_data, output_dir):
        """Generate P23 overlay histogram for category-wise distribution comparison."""
        mapping = MappingConfig(x="value", color="group")

        # Build chart with mean lines per category
        chart = builder.build(
            template_id="P23_overlay_histogram",
            data=category_distribution_data,
            mapping=mapping,
            auxiliary=["mean_line", "median_line"],
            width=1200,
            height=600,
        )

        # Override title with business context
        chart = chart.properties(title="Customer Satisfaction Score Distribution by Segment - 2024 Survey Results")

        # Export as SVG
        svg_output = builder.export(chart, OutputFormat.SVG)
        svg_path = output_dir / "P23_overlay_histogram.svg"
        svg_path.write_text(svg_output)

        # Try PNG export if available
        try:
            png_output = builder.export(chart, OutputFormat.PNG, dpi=150)
            png_path = output_dir / "P23_overlay_histogram.png"

            import base64  # noqa: PLC0415

            png_data = base64.b64decode(png_output)
            png_path.write_bytes(png_data)
            logger.info("Generated P23 overlay histogram", svg=str(svg_path), png=str(png_path))
        except Exception as e:  # noqa: BLE001
            logger.info("Generated P23 overlay histogram", svg=str(svg_path), png_error=str(e))

        assert svg_path.exists()

    def test_p31_small_multiples(self, builder, small_multiples_data, output_dir):
        """Generate P31 small multiples for overview changes over categories."""
        mapping = MappingConfig(x="month", y="value", facet="region", color="product")

        chart = builder.build(
            template_id="P31_small_multiples",
            data=small_multiples_data,
            mapping=mapping,
            width=1400,
            height=800,
        )

        # Override title with business context
        chart = chart.properties(title="Regional Performance Overview - 2024 Comparative Analysis")

        # Export as SVG
        svg_output = builder.export(chart, OutputFormat.SVG)
        svg_path = output_dir / "P31_small_multiples.svg"
        svg_path.write_text(svg_output)

        # Try PNG export if available
        try:
            png_output = builder.export(chart, OutputFormat.PNG, dpi=150)
            png_path = output_dir / "P31_small_multiples.png"

            import base64  # noqa: PLC0415

            png_data = base64.b64decode(png_output)
            png_path.write_bytes(png_data)
            logger.info("Generated P31 small multiples", svg=str(svg_path), png=str(png_path))
        except Exception as e:  # noqa: BLE001
            logger.info("Generated P31 small multiples", svg=str(svg_path), png_error=str(e))

        assert svg_path.exists()

    def test_p32_box_plot(self, builder, box_plot_data, output_dir):
        """Generate P32 box plot for distribution comparison between categories."""
        mapping = MappingConfig(x="department", y="salary")

        # Build chart with overall mean line and target
        chart = builder.build(
            template_id="P32_box_plot",
            data=box_plot_data,
            mapping=mapping,
            auxiliary=["mean_line", "target_line"],
            width=1200,
            height=600,
        )

        # Override title with business context
        chart = chart.properties(title="Salary Distribution Analysis by Department - 2024 Compensation Review")

        # Export as SVG
        svg_output = builder.export(chart, OutputFormat.SVG)
        svg_path = output_dir / "P32_box_plot.svg"
        svg_path.write_text(svg_output)

        # Try PNG export if available
        try:
            png_output = builder.export(chart, OutputFormat.PNG, dpi=150)
            png_path = output_dir / "P32_box_plot.png"

            import base64  # noqa: PLC0415

            png_data = base64.b64decode(png_output)
            png_path.write_bytes(png_data)
            logger.info("Generated P32 box plot", svg=str(svg_path), png=str(png_path))
        except Exception as e:  # noqa: BLE001
            logger.info("Generated P32 box plot", svg=str(svg_path), png_error=str(e))

        assert svg_path.exists()

    def test_all_templates_overview(self, builder, output_dir):
        """Generate an overview showing all implemented template types."""
        # Create a summary DataFrame for all test results
        summary_data = pl.DataFrame(
            {
                "template": [
                    "P01_line",
                    "P02_bar",
                    "P03_histogram",
                    "P12_multi_line",
                    "P21_grouped_bar",
                    "P23_overlay_histogram",
                    "P32_box_plot",
                ],
                "pattern": [
                    "Transition",
                    "Difference",
                    "Overview",
                    "Transition+Difference",
                    "Difference+Transition",
                    "Difference+Overview",
                    "Overview+Difference",
                ],
                "description": [
                    "Time series with trend",
                    "Category comparison",
                    "Distribution analysis",
                    "Multiple time series comparison",
                    "Grouped category comparison over time",
                    "Category-wise distribution comparison",
                    "Statistical distribution comparison",
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

    BASIC VISUAL OUTPUT TEST INSTRUCTIONS
    ====================================

    To generate representative chart images for manual inspection:
    1. Run: pytest tests/local/visual_output/test_basic_charts.py -v -s
    2. Check the generated images in: tests/local/visual_output/charts/
    3. Images will be saved in both SVG and PNG formats (if vl-convert is available)

    Generated files:
    Basic Templates (P01-P03):
    - P01_line_chart.svg/png - Line chart showing time series with mean and median lines
    - P02_bar_chart.svg/png - Bar chart comparing categories with mean line
    - P03_histogram.svg/png - Histogram showing distribution with mean and median

    Advanced Templates (P12, P21, P23, P32):
    - P12_multi_line_chart.svg/png - Multi-line chart with per-series mean lines
    - P21_grouped_bar_chart.svg/png - Grouped bars showing quarterly regional performance
    - P23_overlay_histogram.svg/png - Overlaid histograms with category-specific mean/median
    - P32_box_plot.svg/png - Box plot comparing salary distributions by department

    Reference:
    - template_overview.csv - Summary of all 7 implemented templates

    Each chart demonstrates:
    - The primary visualization pattern (Transition/Difference/Overview + combinations)
    - Basic auxiliary elements appropriate for that chart type
    - Compliance with Visualization Policy (e.g., zero origin for bars, consistent colors)
    - Template-specific features (faceting, grouping, overlays, statistical summaries)

    For comprehensive auxiliary element testing, see test_auxiliary_matrix.py
    """
    instructions = test_visual_output_instructions.__doc__
    logger.info("Visual test instructions", instructions=instructions)
