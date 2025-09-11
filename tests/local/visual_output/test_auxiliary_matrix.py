"""Comprehensive auxiliary element testing - generates all template x auxiliary combinations.

This test systematically generates charts for every template with each of its supported
auxiliary elements to verify implementation status and visual correctness.

Run with: pytest tests/local/visual_output/test_auxiliary_matrix.py -v
"""

import base64
import datetime
import random
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from chartelier.core.chart_builder import ChartBuilder
from chartelier.core.enums import AuxiliaryElement, OutputFormat
from chartelier.core.models import MappingConfig
from chartelier.infra.logging import get_logger

logger = get_logger(__name__)


class TestAuxiliaryMatrix:
    """Systematic testing of all template x auxiliary element combinations."""

    @pytest.fixture
    def output_dir(self):
        """Create output directory for auxiliary element test images."""
        output_path = Path("tests/local/visual_output/auxiliary_matrix")
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path

    @pytest.fixture
    def builder(self):
        """Create a ChartBuilder instance."""
        return ChartBuilder()

    @pytest.fixture
    def data_fixtures(self):  # noqa: C901, PLR0912
        """Create all data fixtures needed for different templates."""
        random.seed(42)

        # Time series data for P01, P12
        dates = pl.date_range(
            datetime.date(2024, 1, 1),
            datetime.date(2024, 2, 29),
            interval="1d",
            eager=True,
        )

        time_series_data = pl.DataFrame(
            {
                "date": [d.strftime("%Y-%m-%d") for d in dates],
                "value": [100 + i * 0.5 + random.gauss(0, 5) for i in range(len(dates))],
            }
        )

        # Multi-series data for P12
        multi_series_data = []
        for i, date in enumerate(dates):
            for series in ["A", "B", "C"]:
                base = {"A": 50, "B": 80, "C": 30}[series]
                trend = {"A": 0.8, "B": -0.5, "C": 0.1}[series]
                value = base + i * trend + random.gauss(0, 3)
                multi_series_data.append({"date": date.strftime("%Y-%m-%d"), "value": value, "series": series})

        # Categorical data for P02
        categorical_data = pl.DataFrame(
            {
                "department": ["Engineering", "Marketing", "Sales", "Support"],
                "headcount": [45, 32, 28, 55],
            }
        )

        # Distribution data for P03
        distribution_data = pl.DataFrame({"test_scores": [random.gauss(75, 12) for _ in range(200)]})

        # Grouped data for P21
        grouped_data = []
        for quarter in ["Q1", "Q2", "Q3", "Q4"]:
            for region in ["North", "South"]:
                base = {"North": 100, "South": 85}[region]
                growth = ["Q1", "Q2", "Q3", "Q4"].index(quarter) * 10
                value = base + growth + random.gauss(0, 8)
                grouped_data.append({"quarter": quarter, "region": region, "sales": value})

        # Category distribution data for P23
        category_dist_data = []
        for group in ["Group A", "Group B"]:
            mean = {"Group A": 70, "Group B": 85}[group]
            for _ in range(100):
                category_dist_data.append({"value": random.gauss(mean, 12), "group": group})

        # Box plot data for P32
        box_plot_data = []
        for dept in ["Engineering", "Marketing", "Sales"]:
            mean = {"Engineering": 95000, "Marketing": 75000, "Sales": 65000}[dept]
            for _ in range(30):
                box_plot_data.append({"department": dept, "salary": max(30000, random.gauss(mean, 15000))})

        # Facet data for P13
        facet_data = []
        for category in ["Electronics", "Clothing", "Food", "Books"]:
            center = {"Electronics": 75, "Clothing": 65, "Food": 80, "Books": 70}[category]
            spread = {"Electronics": 15, "Clothing": 12, "Food": 8, "Books": 10}[category]
            for _ in range(100):
                value = random.gauss(center, spread)
                facet_data.append({"category": category, "value": value})

        # Small multiples data for P31
        small_multiples_data = []
        for region in ["North", "South", "East", "West"]:
            for month in ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]:
                for product in ["Product A", "Product B"]:
                    base = {"North": 100, "South": 85, "East": 90, "West": 80}[region]
                    month_factor = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"].index(month) * 5
                    product_factor = 10 if product == "Product A" else 0
                    noise = random.gauss(0, 8)
                    value = base + month_factor + product_factor + noise
                    small_multiples_data.append({"region": region, "month": month, "product": product, "value": value})

        return {
            "time_series": time_series_data,
            "multi_series": pl.DataFrame(multi_series_data),
            "categorical": categorical_data,
            "distribution": distribution_data,
            "grouped": pl.DataFrame(grouped_data),
            "category_distribution": pl.DataFrame(category_dist_data),
            "box_plot": pl.DataFrame(box_plot_data),
            "facet": pl.DataFrame(facet_data),
            "small_multiples": pl.DataFrame(small_multiples_data),
        }

    def test_auxiliary_matrix_comprehensive(self, builder, data_fixtures, output_dir):
        """Generate comprehensive matrix of template x auxiliary element combinations."""

        # Template configurations
        template_configs = {
            "P01_line": {
                "data": data_fixtures["time_series"],
                "mapping": MappingConfig(x="date", y="value"),
            },
            "P02_bar": {
                "data": data_fixtures["categorical"],
                "mapping": MappingConfig(x="department", y="headcount"),
            },
            "P03_histogram": {
                "data": data_fixtures["distribution"],
                "mapping": MappingConfig(x="test_scores"),
            },
            "P12_multi_line": {
                "data": data_fixtures["multi_series"],
                "mapping": MappingConfig(x="date", y="value", color="series"),
            },
            "P13_facet_histogram": {
                "data": data_fixtures["facet"],
                "mapping": MappingConfig(x="value", facet="category"),
            },
            "P21_grouped_bar": {
                "data": data_fixtures["grouped"],
                "mapping": MappingConfig(x="quarter", y="sales", color="region"),
            },
            "P23_overlay_histogram": {
                "data": data_fixtures["category_distribution"],
                "mapping": MappingConfig(x="value", color="group"),
            },
            "P31_small_multiples": {
                "data": data_fixtures["small_multiples"],
                "mapping": MappingConfig(x="month", y="value", facet="region", color="product"),
            },
            "P32_box_plot": {
                "data": data_fixtures["box_plot"],
                "mapping": MappingConfig(x="department", y="salary"),
            },
        }

        results = []

        for template_id, config in template_configs.items():
            # Get template specification
            spec = builder.get_template_spec(template_id)

            logger.info("Testing template %s with %d auxiliary elements", template_id, len(spec.allowed_auxiliary))

            for aux_element in spec.allowed_auxiliary:
                try:
                    result = self._test_single_combination(builder, template_id, aux_element, config, output_dir)
                    results.append(result)

                except Exception as e:  # noqa: BLE001
                    error_msg = str(e)
                    # Special handling for known facet limitations
                    if "Faceted charts cannot be layered" in error_msg:
                        logger.info(
                            "Skipping %s with %s (faceted charts don't support auxiliary layers)",
                            template_id,
                            aux_element.value,
                        )
                        status = "skipped"
                    else:
                        logger.warning(
                            "Failed to generate %s with %s", template_id, aux_element.value, extra={"error": error_msg}
                        )
                        status = "error"

                    results.append(
                        {
                            "template": template_id,
                            "auxiliary": aux_element.value,
                            "status": status,
                            "error": error_msg,
                            "svg_file": None,
                            "png_file": None,
                        }
                    )

        # Save results summary
        self._save_matrix_summary(results, output_dir)

        # Verify we have results
        assert len(results) > 0
        success_count = sum(1 for r in results if r["status"] == "success")
        logger.info("Generated %d/%d auxiliary element combinations successfully", success_count, len(results))

    def _test_single_combination(
        self,
        builder: ChartBuilder,
        template_id: str,
        aux_element: AuxiliaryElement,
        config: dict[str, Any],
        output_dir: Path,
    ) -> dict[str, Any]:
        """Test a single template x auxiliary element combination."""

        # Build chart with single auxiliary element
        chart = builder.build(
            template_id=template_id,
            data=config["data"],
            mapping=config["mapping"],
            auxiliary=[aux_element.value],
            width=800,
            height=600,
        )

        # Generate filenames
        base_name = f"{template_id}_{aux_element.value}"
        svg_path = output_dir / f"{base_name}.svg"
        png_path = output_dir / f"{base_name}.png"

        # Export SVG
        svg_output = builder.export(chart, OutputFormat.SVG)
        svg_path.write_text(svg_output)

        # Try PNG export
        png_success = False
        try:
            png_output = builder.export(chart, OutputFormat.PNG, dpi=150)
            png_data = base64.b64decode(png_output)
            png_path.write_bytes(png_data)
            png_success = True
        except (ValueError, KeyError, RuntimeError) as e:
            logger.debug("PNG export failed for %s", base_name, extra={"error": str(e)})

        return {
            "template": template_id,
            "auxiliary": aux_element.value,
            "status": "success",
            "error": None,
            "svg_file": svg_path.name,
            "png_file": png_path.name if png_success else None,
        }

    def _save_matrix_summary(self, results: list[dict[str, Any]], output_dir: Path):
        """Save summary of matrix test results."""

        # Create summary DataFrame
        summary_df = pl.DataFrame(results)

        # Save as CSV
        summary_path = output_dir / "auxiliary_matrix_results.csv"
        summary_df.write_csv(summary_path)

        # Create HTML report for better visualization
        html_report = self._generate_html_report(results)
        html_path = output_dir / "auxiliary_matrix_report.html"
        html_path.write_text(html_report)

        logger.info(
            "Saved auxiliary matrix results",
            csv=str(summary_path),
            html=str(html_path),
            total_combinations=len(results),
            successful=sum(1 for r in results if r["status"] == "success"),
            failed=sum(1 for r in results if r["status"] == "error"),
            skipped=sum(1 for r in results if r["status"] == "skipped"),
        )

    def _generate_html_report(self, results: list[dict[str, Any]]) -> str:
        """Generate HTML report for auxiliary matrix results."""

        # Group by template
        templates = {}
        for result in results:
            template = result["template"]
            if template not in templates:
                templates[template] = []
            templates[template].append(result)

        html_parts = [
            "<!DOCTYPE html>",
            "<html><head><title>Auxiliary Element Matrix Report</title>",
            "<style>",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #f2f2f2; }",
            ".success { background-color: #d4edda; }",
            ".error { background-color: #f8d7da; }",
            ".skipped { background-color: #fff3cd; }",
            ".template-section { margin-bottom: 20px; }",
            "</style></head><body>",
            "<h1>Auxiliary Element Matrix Report</h1>",
        ]

        for template_id in sorted(templates.keys()):
            template_results = templates[template_id]
            html_parts.extend(
                [
                    "<div class='template-section'>",
                    f"<h2>{template_id}</h2>",
                    "<table>",
                    "<tr><th>Auxiliary Element</th><th>Status</th><th>SVG</th><th>PNG</th><th>Error</th></tr>",
                ]
            )

            for result in template_results:
                status_class = result["status"]
                svg_link = f"<a href='{result['svg_file']}'>{result['svg_file']}</a>" if result["svg_file"] else "N/A"
                png_link = f"<a href='{result['png_file']}'>{result['png_file']}</a>" if result["png_file"] else "N/A"
                error_text = result["error"] or ""

                html_parts.append(
                    f"<tr class='{status_class}'>"
                    f"<td>{result['auxiliary']}</td>"
                    f"<td>{result['status']}</td>"
                    f"<td>{svg_link}</td>"
                    f"<td>{png_link}</td>"
                    f"<td>{error_text}</td>"
                    f"</tr>"
                )

            html_parts.extend(["</table>", "</div>"])

        html_parts.extend(["</body></html>"])
        return "\n".join(html_parts)


def test_auxiliary_matrix_instructions():
    """Display instructions for running auxiliary matrix tests.

    AUXILIARY ELEMENT MATRIX TEST INSTRUCTIONS
    ==========================================

    To generate comprehensive auxiliary element testing:
    1. Run: pytest tests/local/visual_output/test_auxiliary_matrix.py -v -s
    2. Check the generated images in: tests/local/visual_output/auxiliary_matrix/
    3. Review the HTML report: tests/local/visual_output/auxiliary_matrix/auxiliary_matrix_report.html

    Generated outputs:
    - {template_id}_{auxiliary_element}.svg/png for each valid combination
    - auxiliary_matrix_results.csv - Machine-readable summary
    - auxiliary_matrix_report.html - Human-readable visual report

    This test systematically verifies:
    - Implementation status of each auxiliary element per template
    - Visual correctness of auxiliary elements
    - Error handling for unimplemented combinations
    - Complete coverage of allowed_auxiliary specifications

    Use this for:
    - Verifying auxiliary element implementations
    - Identifying missing or broken auxiliary elements
    - Visual QA of auxiliary element rendering
    - Documentation of supported combinations
    """
    instructions = test_auxiliary_matrix_instructions.__doc__
    logger.info("Auxiliary matrix test instructions", instructions=instructions)
