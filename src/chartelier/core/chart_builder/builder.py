"""Chart builder for generating visualizations."""

import base64
from typing import Any

import altair as alt
import polars as pl

from chartelier.core.enums import OutputFormat, PatternID
from chartelier.core.errors import ChartBuildError, ExportError
from chartelier.core.models import MappingConfig
from chartelier.infra.logging import get_logger

from .base import BaseTemplate, TemplateSpec

logger = get_logger(__name__)


class ChartSpec:
    """Specification for a chart type."""

    def __init__(self, template_id: str, name: str, pattern_ids: list[PatternID]) -> None:
        """Initialize chart specification.

        Args:
            template_id: Unique template identifier
            name: Human-readable name
            pattern_ids: Supported pattern IDs
        """
        self.template_id = template_id
        self.name = name
        self.pattern_ids = pattern_ids


class ChartBuilder:
    """Main chart builder class managing templates and rendering."""

    def __init__(self) -> None:
        """Initialize chart builder."""
        self._templates: dict[str, BaseTemplate] = {}
        self._pattern_defaults: dict[PatternID, str] = {}
        self._initialize_templates()

    def _initialize_templates(self) -> None:
        """Initialize and register available templates."""
        # Import and register implemented templates
        from .templates import (  # noqa: PLC0415 — Lazy import to avoid circular dependencies
            BarTemplate,
            BoxPlotTemplate,
            FacetHistogramTemplate,
            GroupedBarTemplate,
            HistogramTemplate,
            LineTemplate,
            MultiLineTemplate,
            OverlayHistogramTemplate,
            SmallMultiplesTemplate,
        )

        # Register basic templates (P01-P03)
        self.register_template("P01_line", LineTemplate())
        self.register_template("P02_bar", BarTemplate())
        self.register_template("P03_histogram", HistogramTemplate())

        # Register advanced templates (P12, P13, P21, P23, P31, P32)
        self.register_template("P12_multi_line", MultiLineTemplate())
        self.register_template("P13_facet_histogram", FacetHistogramTemplate())
        self.register_template("P21_grouped_bar", GroupedBarTemplate())
        self.register_template("P23_overlay_histogram", OverlayHistogramTemplate())
        self.register_template("P31_small_multiples", SmallMultiplesTemplate())
        self.register_template("P32_box_plot", BoxPlotTemplate())

        # Set up pattern defaults
        self._pattern_defaults = {
            PatternID.P01: "P01_line",
            PatternID.P02: "P02_bar",
            PatternID.P03: "P03_histogram",
            PatternID.P12: "P12_multi_line",
            PatternID.P13: "P13_facet_histogram",
            PatternID.P21: "P21_grouped_bar",
            PatternID.P23: "P23_overlay_histogram",
            PatternID.P31: "P31_small_multiples",
            PatternID.P32: "P32_box_plot",
        }

    def register_template(self, template_id: str, template: BaseTemplate) -> None:
        """Register a template.

        Args:
            template_id: Unique template identifier
            template: Template instance
        """
        self._templates[template_id] = template
        logger.debug("Registered template", template_id=template_id)

    def get_available_charts(self, pattern_id: PatternID) -> list[ChartSpec]:
        """Get available charts for a pattern.

        Args:
            pattern_id: Pattern identifier

        Returns:
            List of available chart specifications
        """
        available = []
        for template_id, template in self._templates.items():
            if pattern_id.value in template.spec.pattern_ids:
                available.append(
                    ChartSpec(
                        template_id=template_id,
                        name=template.spec.name,
                        pattern_ids=[PatternID(pid) for pid in template.spec.pattern_ids],
                    )
                )

        # If no templates available, return default
        if not available and pattern_id in self._pattern_defaults:
            default_id = self._pattern_defaults[pattern_id]
            available.append(
                ChartSpec(
                    template_id=default_id,
                    name=f"Default {pattern_id.value} chart",
                    pattern_ids=[pattern_id],
                )
            )

        return available

    def get_template_spec(self, template_id: str) -> TemplateSpec | None:
        """Get template specification.

        Args:
            template_id: Template identifier

        Returns:
            Template specification or None if not found
        """
        template = self._templates.get(template_id)
        return template.spec if template else None

    def build(  # noqa: PLR0913 — Multiple parameters required for chart customization
        self,
        template_id: str,
        data: pl.DataFrame,
        mapping: MappingConfig,
        auxiliary: list[str] | None = None,
        auxiliary_config: dict[str, Any] | None = None,
        width: int = 800,
        height: int = 600,
    ) -> alt.Chart | alt.LayerChart:
        """Build chart using specified template.

        Args:
            template_id: Template identifier
            data: Input data
            mapping: Column mappings
            auxiliary: Auxiliary elements to apply
            auxiliary_config: Configuration for auxiliary elements
            width: Chart width
            height: Chart height

        Returns:
            Altair chart object

        Raises:
            ChartBuildError: If chart cannot be built
        """
        template = self._templates.get(template_id)
        if not template:
            msg = f"Template not found: {template_id}"
            raise ChartBuildError(msg)

        # Validate mapping
        is_valid, missing = template.spec.validate_mapping(mapping)
        if not is_valid:
            msg = f"Missing required mappings: {missing}"
            raise ChartBuildError(msg)

        try:
            # Build base chart (without theme)
            chart = template.build(data, mapping, width, height)

            # Apply auxiliary elements if requested
            if auxiliary:
                from chartelier.core.enums import (  # noqa: PLC0415 — Conditional import for optional feature
                    AuxiliaryElement,
                )

                aux_elements = []
                for aux_str in auxiliary:
                    try:
                        aux_elements.append(AuxiliaryElement(aux_str))
                    except ValueError:
                        logger.warning("Unknown auxiliary element", element=aux_str)

                if aux_elements:
                    # Pass auxiliary config if available (auxiliary_config parameter needs to be added to build method)
                    chart = template.apply_auxiliary(chart, aux_elements, data, mapping, auxiliary_config)  # type: ignore[assignment]

            # Apply theme to final chart (base + auxiliary elements)
            pattern_id = self._extract_pattern_id(template_id)
            series_count = self._count_series(data, mapping)
            return template.apply_theme(chart, pattern_id, series_count)

        except Exception as e:
            msg = f"Failed to build chart: {e}"
            raise ChartBuildError(msg) from e

    def _extract_pattern_id(self, template_id: str) -> PatternID | None:
        """Extract pattern ID from template ID.

        Args:
            template_id: Template identifier like "P01_line"

        Returns:
            Pattern ID or None if not found
        """
        try:
            pattern_part = template_id.split("_")[0]  # Extract P01 from P01_line
            from chartelier.core.enums import PatternID  # noqa: PLC0415

            return PatternID(pattern_part)
        except (ValueError, IndexError):
            return None

    def _count_series(self, data: pl.DataFrame, mapping: MappingConfig) -> int:
        """Count the number of series in the data based on color mapping.

        Args:
            data: Input data frame
            mapping: Column mappings

        Returns:
            Number of series
        """
        if mapping.color and mapping.color in data.columns:
            return data[mapping.color].n_unique()
        return 1

    def export(
        self,
        chart: alt.Chart | alt.LayerChart,
        format: OutputFormat = OutputFormat.PNG,  # noqa: A002 — OutputFormat enum parameter
        dpi: int = 300,
    ) -> str:
        """Export chart to specified format.

        Args:
            chart: Altair chart object
            format: Output format (PNG or SVG)
            dpi: DPI for PNG export

        Returns:
            Base64 encoded PNG or SVG string

        Raises:
            ExportError: If export fails
        """
        try:
            if format == OutputFormat.PNG:
                return self._export_png(chart, dpi)
            return self._export_svg(chart)
        except Exception as e:
            # Try fallback
            if format == OutputFormat.PNG:
                logger.warning("PNG export failed, falling back to SVG", error=str(e))
                try:
                    return self._export_svg(chart)
                except Exception as svg_error:
                    msg = f"Export failed for both PNG and SVG: {svg_error}"
                    raise ExportError(msg) from svg_error
            else:
                msg = f"SVG export failed: {e}"
                raise ExportError(msg) from e

    def _export_png(self, chart: alt.Chart | alt.LayerChart, dpi: int) -> str:
        """Export chart as PNG.

        Args:
            chart: Altair chart
            dpi: DPI setting

        Returns:
            Base64 encoded PNG

        Raises:
            Exception: If PNG export fails
        """
        try:
            import vl_convert as vlc  # noqa: PLC0415 — Optional dependency import

            # Convert to Vega-Lite spec
            vega_lite_spec = chart.to_json()

            # Convert to PNG using vl-convert
            png_data = vlc.vegalite_to_png(
                vl_spec=vega_lite_spec,
                scale=dpi / 96.0,  # Scale factor from base DPI
            )

            # Encode to base64
            return base64.b64encode(png_data).decode("utf-8")

        except ImportError as e:
            msg = "vl-convert-python not installed"
            raise ExportError(msg) from e

    def _export_svg(self, chart: alt.Chart | alt.LayerChart) -> str:
        """Export chart as SVG.

        Args:
            chart: Altair chart

        Returns:
            SVG string

        Raises:
            Exception: If SVG export fails
        """
        try:
            import vl_convert as vlc  # noqa: PLC0415 — Optional dependency import

            # Convert to Vega-Lite spec
            vega_lite_spec = chart.to_json()

            # Convert to SVG using vl-convert
            return vlc.vegalite_to_svg(vl_spec=vega_lite_spec)

        except ImportError:
            # Fallback to Altair's built-in SVG export if available
            try:
                # This requires altair_saver or similar
                return str(chart.to_svg())
            except Exception as e:
                msg = "SVG export failed - vl-convert-python not available"
                raise ExportError(msg) from e

    def export_with_fallback(
        self,
        chart: alt.Chart | alt.LayerChart,
        preferred_format: OutputFormat = OutputFormat.PNG,
        dpi: int = 300,
    ) -> tuple[str, OutputFormat, bool]:
        """Export chart with automatic fallback.

        Args:
            chart: Altair chart object
            preferred_format: Preferred output format
            dpi: DPI for PNG export

        Returns:
            Tuple of (output_data, actual_format, fallback_applied)
        """
        fallback_applied = False

        try:
            output = self.export(chart, preferred_format, dpi)
            return output, preferred_format, fallback_applied  # noqa: TRY300 — Success case return
        except ExportError:
            # Try fallback format
            fallback_format = OutputFormat.SVG if preferred_format == OutputFormat.PNG else OutputFormat.PNG

            try:
                logger.info(
                    "Falling back to alternative format",
                    from_format=preferred_format.value,
                    to_format=fallback_format.value,
                )
                output = self.export(chart, fallback_format, dpi)
                return output, fallback_format, True  # noqa: TRY300 — Fallback success return
            except ExportError as e:
                # Both formats failed, raise the error
                msg = f"Export failed for both formats: {e}"
                raise ExportError(msg) from e
