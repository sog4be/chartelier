"""System tests for MCP response format compliance."""

import base64
import json
from unittest.mock import patch

from chartelier.interfaces.mcp.handler import MCPHandler
from chartelier.interfaces.mcp.protocol import JSONRPCRequest, JSONRPCResponse, MCPMethod
from chartelier.orchestration.coordinator import VisualizationResult


class TestMCPResponseFormat:
    """Test MCP response format compliance with specification."""

    def test_success_response_with_png(self) -> None:
        """Test successful response format with PNG image."""
        handler = MCPHandler()

        # Mock coordinator to return success with PNG
        mock_result = VisualizationResult(
            format="png",
            image_data=base64.b64encode(b"fake_png_data").decode("utf-8"),
            metadata={
                "pattern_id": "P12",
                "template_id": "multi_line",
                "mapping": {"x": "month", "y": "sales", "color": "category"},
                "auxiliary": ["target_line"],
                "operations_applied": ["groupby_agg", "sort"],
                "decisions": {
                    "pattern": {"elapsed_ms": 120},
                    "chart": {"elapsed_ms": 85},
                },
                "stats": {
                    "rows": 9500,
                    "cols": 12,
                    "sampled": True,
                    "duration_ms": {"total": 4210},
                },
                "versions": {
                    "api": "0.2.0",
                    "templates": "2025.01",
                    "patterns": "v1",
                },
                "warnings": [],
                "fallback_applied": False,
            },
        )

        with patch.object(handler.coordinator, "process", return_value=mock_result):
            # Create tools/call request
            request = JSONRPCRequest(
                id=1,
                method=MCPMethod.TOOLS_CALL,
                params={
                    "name": "chartelier_visualize",
                    "arguments": {
                        "data": "x,y\n1,2\n3,4",
                        "query": "Show a line chart",
                    },
                },
            )

            # Handle request
            response_str = handler.handle_message(json.dumps(request.model_dump()))
            response_data = json.loads(response_str)
            response = JSONRPCResponse(**response_data)

            # Verify response structure
            assert response.id == 1
            assert response.error is None
            assert response.result is not None

            result = response.result
            assert result["isError"] is False

            # Verify content has image with correct MIME type
            assert len(result["content"]) == 1
            image_content = result["content"][0]
            assert image_content["type"] == "image"
            assert image_content["mimeType"] == "image/png"
            assert image_content["data"] == mock_result.image_data

            # Verify structuredContent has only metadata
            assert "structuredContent" in result
            assert "metadata" in result["structuredContent"]
            assert "format" not in result["structuredContent"]  # format should not be in structuredContent
            assert "image" not in result["structuredContent"]  # image should not be in structuredContent

            # Verify metadata structure
            metadata = result["structuredContent"]["metadata"]
            assert metadata["pattern_id"] == "P12"
            assert metadata["template_id"] == "multi_line"
            assert metadata["mapping"] == {"x": "month", "y": "sales", "color": "category"}
            assert metadata["auxiliary"] == ["target_line"]
            assert metadata["operations_applied"] == ["groupby_agg", "sort"]
            assert metadata["fallback_applied"] is False

    def test_success_response_with_svg(self) -> None:
        """Test successful response format with SVG image."""
        handler = MCPHandler()

        # Mock coordinator to return success with SVG
        svg_data = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="100" height="100"/></svg>'
        mock_result = VisualizationResult(
            format="svg",
            image_data=svg_data,
            metadata={
                "pattern_id": "P01",
                "template_id": "line",
                "mapping": {"x": "time", "y": "value"},
                "auxiliary": [],
                "operations_applied": [],
                "decisions": {
                    "pattern": {"elapsed_ms": 50},
                    "chart": {"elapsed_ms": 30},
                },
                "stats": {
                    "rows": 100,
                    "cols": 2,
                    "sampled": False,
                    "duration_ms": {"total": 200},
                },
                "versions": {
                    "api": "0.2.0",
                    "templates": "2025.01",
                    "patterns": "v1",
                },
                "warnings": ["PNG export failed, returning SVG instead"],
                "fallback_applied": True,
            },
        )

        with patch.object(handler.coordinator, "process", return_value=mock_result):
            # Create tools/call request
            request = JSONRPCRequest(
                id=2,
                method=MCPMethod.TOOLS_CALL,
                params={
                    "name": "chartelier_visualize",
                    "arguments": {
                        "data": "x,y\n1,2",
                        "query": "Show chart",
                        "options": {"format": "svg"},
                    },
                },
            )

            # Handle request
            response_str = handler.handle_message(json.dumps(request.model_dump()))
            response_data = json.loads(response_str)
            response = JSONRPCResponse(**response_data)

            result = response.result
            assert result["isError"] is False

            # Verify SVG content
            image_content = result["content"][0]
            assert image_content["type"] == "image"
            assert image_content["mimeType"] == "image/svg+xml"
            assert image_content["data"] == svg_data

            # Verify metadata
            metadata = result["structuredContent"]["metadata"]
            assert metadata["fallback_applied"] is True
            assert len(metadata["warnings"]) == 1

    def test_error_response_format(self) -> None:
        """Test error response format compliance."""
        handler = MCPHandler()

        # Mock coordinator to return error
        mock_result = VisualizationResult(
            format="png",
            error={
                "code": "E422_UNPROCESSABLE",
                "message": "Pattern selection failed",
                "hint": "Try specifying: 1) What aspect to visualize, 2) Time period if relevant",
                "details": None,
            },
            metadata={
                "processing_time_ms": 1500,
                "warnings": ["Data sampled to 10000 rows"],
                "fallback_applied": False,
            },
        )

        with patch.object(handler.coordinator, "process", return_value=mock_result):
            # Create tools/call request
            request = JSONRPCRequest(
                id=3,
                method=MCPMethod.TOOLS_CALL,
                params={
                    "name": "chartelier_visualize",
                    "arguments": {
                        "data": "x,y\n1,2",
                        "query": "Make a chart",
                    },
                },
            )

            # Handle request
            response_str = handler.handle_message(json.dumps(request.model_dump()))
            response_data = json.loads(response_str)
            response = JSONRPCResponse(**response_data)

            result = response.result
            assert result["isError"] is True

            # Verify content has text error message
            assert len(result["content"]) == 1
            text_content = result["content"][0]
            assert text_content["type"] == "text"
            assert "Pattern selection failed" in text_content["text"]
            assert "Try specifying" in text_content["text"]

            # Verify structuredContent has error and metadata
            assert "structuredContent" in result
            assert "error" in result["structuredContent"]
            assert "metadata" in result["structuredContent"]

            # Verify error structure
            error = result["structuredContent"]["error"]
            assert error["code"] == "E422_UNPROCESSABLE"
            assert error["message"] == "Pattern selection failed"
            assert error["hint"] == "Try specifying: 1) What aspect to visualize, 2) Time period if relevant"
            assert "correlation_id" in error
            assert error["correlation_id"].startswith("req-")

            # Verify metadata in error response
            metadata = result["structuredContent"]["metadata"]
            assert metadata["processing_time_ms"] == 1500
            assert metadata["warnings"] == ["Data sampled to 10000 rows"]

    def test_response_with_all_metadata_fields(self) -> None:
        """Test response includes all required metadata fields."""
        handler = MCPHandler()

        # Mock coordinator with complete metadata
        mock_result = VisualizationResult(
            format="png",
            image_data=base64.b64encode(b"test").decode("utf-8"),
            metadata={
                "pattern_id": "P21",
                "template_id": "grouped_bar",
                "mapping": {
                    "x": "category",
                    "y": "value",
                    "color": "group",
                },
                "auxiliary": ["target_line"],
                "operations_applied": ["filter", "groupby_agg", "sort"],
                "decisions": {
                    "pattern": {"elapsed_ms": 95, "reasoning": "Comparing categories over time"},
                    "chart": {"elapsed_ms": 45, "selected_from": ["grouped_bar", "stacked_bar"]},
                },
                "stats": {
                    "rows": 5000,
                    "cols": 8,
                    "sampled": True,
                    "duration_ms": {
                        "total": 3500,
                        "data_validation": 200,
                        "pattern_selection": 95,
                        "chart_selection": 45,
                        "data_processing": 800,
                        "data_mapping": 150,
                        "chart_building": 2210,
                    },
                },
                "versions": {
                    "api": "0.2.0",
                    "templates": "2025.01",
                    "patterns": "v1",
                },
                "warnings": [
                    "Data sampled to 5000 rows",
                    "Column 'date' converted to datetime",
                ],
                "fallback_applied": False,
            },
        )

        with patch.object(handler.coordinator, "process", return_value=mock_result):
            request = JSONRPCRequest(
                id=4,
                method=MCPMethod.TOOLS_CALL,
                params={
                    "name": "chartelier_visualize",
                    "arguments": {"data": "x,y\n1,2", "query": "chart"},
                },
            )

            response_str = handler.handle_message(json.dumps(request.model_dump()))
            response_data = json.loads(response_str)
            response = JSONRPCResponse(**response_data)

            metadata = response.result["structuredContent"]["metadata"]

            # Verify all required fields are present
            assert metadata["pattern_id"] == "P21"
            assert metadata["template_id"] == "grouped_bar"
            assert metadata["mapping"]["x"] == "category"
            assert metadata["auxiliary"] == ["target_line"]
            assert len(metadata["operations_applied"]) == 3
            assert metadata["decisions"]["pattern"]["elapsed_ms"] == 95
            assert metadata["stats"]["rows"] == 5000
            assert metadata["stats"]["cols"] == 8
            assert metadata["stats"]["sampled"] is True
            assert metadata["stats"]["duration_ms"]["total"] == 3500
            assert metadata["versions"]["api"] == "0.2.0"
            assert len(metadata["warnings"]) == 2
            assert metadata["fallback_applied"] is False
