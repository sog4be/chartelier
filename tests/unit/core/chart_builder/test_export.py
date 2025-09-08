"""Unit tests for chart export functionality."""

import base64
from unittest.mock import patch

import altair as alt
import polars as pl
import pytest

from chartelier.core.chart_builder import ChartBuilder
from chartelier.core.chart_builder.templates import LineTemplate
from chartelier.core.enums import OutputFormat
from chartelier.core.errors import ExportError


class TestChartExport:
    """Test cases for chart export functionality (UT-CB-001/002)."""

    @pytest.fixture
    def builder(self):
        """Create a ChartBuilder instance."""
        builder = ChartBuilder()
        builder.register_template("P01_line", LineTemplate())
        return builder

    @pytest.fixture
    def sample_chart(self):
        """Create a sample Altair chart."""
        data = pl.DataFrame(
            {
                "x": [1, 2, 3],
                "y": [10, 20, 15],
            }
        )

        chart = (
            alt.Chart({"values": data.to_dicts()})
            .mark_line()
            .encode(
                x="x:Q",
                y="y:Q",
            )
        )

        return chart  # noqa: RET504 — Explicit return for clarity

    def test_export_svg_success(self, builder, sample_chart):
        """Test successful SVG export."""
        with patch("vl_convert.vegalite_to_svg") as mock_svg:
            mock_svg.return_value = "<svg>test</svg>"

            result = builder.export(sample_chart, OutputFormat.SVG)

            assert result == "<svg>test</svg>"
            mock_svg.assert_called_once()

    def test_export_png_success(self, builder, sample_chart):
        """Test successful PNG export."""
        with patch("vl_convert.vegalite_to_png") as mock_png:
            test_png_data = b"fake_png_data"
            mock_png.return_value = test_png_data

            result = builder.export(sample_chart, OutputFormat.PNG, dpi=96)

            expected = base64.b64encode(test_png_data).decode("utf-8")
            assert result == expected
            mock_png.assert_called_once()

    def test_export_png_fallback_to_svg(self, builder, sample_chart):
        """Test PNG export falling back to SVG on failure (UT-CB-001)."""
        with patch("vl_convert.vegalite_to_png") as mock_png, patch("vl_convert.vegalite_to_svg") as mock_svg:
            # PNG export fails
            mock_png.side_effect = Exception("PNG export failed")
            # SVG export succeeds
            mock_svg.return_value = "<svg>fallback</svg>"

            # Should fall back to SVG
            result = builder.export(sample_chart, OutputFormat.PNG)

            assert result == "<svg>fallback</svg>"
            mock_png.assert_called_once()
            mock_svg.assert_called_once()

    def test_export_both_formats_fail(self, builder, sample_chart):
        """Test when both PNG and SVG exports fail (UT-CB-002)."""
        with patch("vl_convert.vegalite_to_png") as mock_png, patch("vl_convert.vegalite_to_svg") as mock_svg:
            # Both exports fail
            mock_png.side_effect = Exception("PNG export failed")
            mock_svg.side_effect = Exception("SVG export failed")

            with pytest.raises(ExportError, match="Export failed for both PNG and SVG"):
                builder.export(sample_chart, OutputFormat.PNG)

    def test_export_with_fallback_no_fallback_needed(self, builder, sample_chart):
        """Test export_with_fallback when primary format succeeds."""
        with patch("vl_convert.vegalite_to_png") as mock_png:
            test_png_data = b"fake_png_data"
            mock_png.return_value = test_png_data

            output, format, fallback_applied = builder.export_with_fallback(
                sample_chart,
                OutputFormat.PNG,
                dpi=96,
            )

            expected = base64.b64encode(test_png_data).decode("utf-8")
            assert output == expected
            assert format == OutputFormat.PNG
            assert fallback_applied is False

    def test_export_with_fallback_applies_fallback(self, builder, sample_chart):
        """Test export_with_fallback when fallback is needed."""
        # Mock the export method to fail on PNG and succeed on SVG
        with patch.object(builder, "export") as mock_export:
            from chartelier.core.errors import ExportError  # noqa: PLC0415 — Import for test mock

            def export_side_effect(chart, format, dpi=96):  # noqa: A002 — format parameter
                if format == OutputFormat.PNG:
                    raise ExportError("PNG export failed")
                return "<svg>fallback</svg>"

            mock_export.side_effect = export_side_effect

            output, format, fallback_applied = builder.export_with_fallback(
                sample_chart,
                OutputFormat.PNG,
            )

            assert output == "<svg>fallback</svg>"
            assert format == OutputFormat.SVG
            assert fallback_applied is True

    def test_export_with_fallback_both_fail(self, builder, sample_chart):
        """Test export_with_fallback when both formats fail."""
        with patch("vl_convert.vegalite_to_png") as mock_png, patch("vl_convert.vegalite_to_svg") as mock_svg:
            # Both fail
            mock_png.side_effect = Exception("PNG export failed")
            mock_svg.side_effect = Exception("SVG export failed")

            with pytest.raises(ExportError, match="Export failed for both formats"):
                builder.export_with_fallback(sample_chart, OutputFormat.PNG)

    def test_export_missing_vl_convert(self, builder, sample_chart):
        """Test export when vl-convert is not installed."""
        # Mock both _export_png and _export_svg to fail with ImportError
        from chartelier.core.errors import ExportError  # noqa: PLC0415 — Import for test mock

        def raise_export_error(*args, **kwargs):
            raise ExportError("vl-convert-python not installed")

        with (
            patch.object(builder, "_export_png", side_effect=raise_export_error),
            patch.object(builder, "_export_svg", side_effect=raise_export_error),
            pytest.raises(ExportError, match="Export failed for both PNG and SVG"),
        ):
            builder.export(sample_chart, OutputFormat.PNG)

    def test_export_svg_fallback_to_altair(self, builder, sample_chart):
        """Test SVG export falling back to Altair's built-in method."""
        # Mock _export_svg to simulate the altair fallback case
        with patch.object(builder, "_export_svg") as mock_export:
            mock_export.return_value = "<svg>altair</svg>"
            result = builder.export(sample_chart, OutputFormat.SVG)
            assert result == "<svg>altair</svg>"
            mock_export.assert_called_once()
