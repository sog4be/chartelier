"""System tests for MCP handler."""

import json

from chartelier.interfaces.mcp.handler import MCPHandler
from chartelier.interfaces.mcp.protocol import (
    JSONRPCRequest,
    JSONRPCResponse,
    MCPMethod,
)


class TestMCPHandler:
    """Test MCP handler functionality."""

    def test_initialize_request(self) -> None:
        """Test handling of initialize request."""
        handler = MCPHandler()

        # Create initialize request
        request = JSONRPCRequest(
            id=1,
            method=MCPMethod.INITIALIZE,
            params={"protocolVersion": "2024-11-05", "capabilities": {}},
        )

        # Handle request
        response_str = handler.handle_message(json.dumps(request.model_dump()))
        assert response_str is not None

        # Parse response
        response_data = json.loads(response_str)
        response = JSONRPCResponse(**response_data)

        # Verify response structure
        assert response.id == 1
        assert response.error is None
        assert response.result is not None

        # Verify initialize result
        result = response.result
        assert result["protocolVersion"] == "2024-11-05"
        assert result["serverInfo"]["name"] == "chartelier"
        assert result["serverInfo"]["version"] == "0.2.0"
        assert result["capabilities"]["tools"]["listChanged"] is False
        assert "chartelier_visualize" in result["instructions"]

    def test_initialized_notification(self) -> None:
        """Test handling of initialized notification."""
        handler = MCPHandler()

        # Send initialized notification (no ID for notifications)
        request = {"jsonrpc": "2.0", "method": "initialized"}

        # Handle notification - should return None
        response = handler.handle_message(json.dumps(request))
        assert response is None
        assert handler.initialized is True

    def test_tools_list_request(self) -> None:
        """Test handling of tools/list request."""
        handler = MCPHandler()

        # Create tools/list request
        request = JSONRPCRequest(
            id=2,
            method=MCPMethod.TOOLS_LIST,
        )

        # Handle request
        response_str = handler.handle_message(json.dumps(request.model_dump()))
        assert response_str is not None

        # Parse response
        response_data = json.loads(response_str)
        response = JSONRPCResponse(**response_data)

        # Verify response structure
        assert response.id == 2
        assert response.error is None
        assert response.result is not None

        # Verify tools list
        result = response.result
        assert "tools" in result
        assert len(result["tools"]) == 1

        # Verify chartelier_visualize tool
        tool = result["tools"][0]
        assert tool["name"] == "chartelier_visualize"
        assert "CSV/JSON" in tool["description"]
        assert tool["inputSchema"]["required"] == ["data", "query"]
        assert "data" in tool["inputSchema"]["properties"]
        assert "query" in tool["inputSchema"]["properties"]
        assert "options" in tool["inputSchema"]["properties"]

    def test_tools_call_not_implemented(self) -> None:
        """Test handling of tools/call request (not yet implemented)."""
        handler = MCPHandler()

        # Create tools/call request
        request = JSONRPCRequest(
            id=3,
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
        assert response_str is not None

        # Parse response
        response_data = json.loads(response_str)
        response = JSONRPCResponse(**response_data)

        # Verify response structure
        assert response.id == 3
        assert response.error is None
        assert response.result is not None

        # Should return error result for now (not implemented)
        result = response.result
        assert result["isError"] is True
        assert len(result["content"]) > 0
        assert result["content"][0]["type"] == "text"
        assert "not yet implemented" in result["content"][0]["text"]

    def test_unknown_tool_call(self) -> None:
        """Test handling of unknown tool call."""
        handler = MCPHandler()

        # Create tools/call request with unknown tool
        request = JSONRPCRequest(
            id=4,
            method=MCPMethod.TOOLS_CALL,
            params={
                "name": "unknown_tool",
                "arguments": {},
            },
        )

        # Handle request
        response_str = handler.handle_message(json.dumps(request.model_dump()))
        assert response_str is not None

        # Parse response
        response_data = json.loads(response_str)
        response = JSONRPCResponse(**response_data)

        # Verify error response
        assert response.id == 4
        assert response.error is None
        assert response.result is not None

        result = response.result
        assert result["isError"] is True
        assert "Unknown tool" in result["content"][0]["text"]

    def test_ping_request(self) -> None:
        """Test handling of ping request."""
        handler = MCPHandler()

        # Create ping request
        request = JSONRPCRequest(
            id=5,
            method=MCPMethod.PING,
        )

        # Handle request
        response_str = handler.handle_message(json.dumps(request.model_dump()))
        assert response_str is not None

        # Parse response
        response_data = json.loads(response_str)
        response = JSONRPCResponse(**response_data)

        # Verify response
        assert response.id == 5
        assert response.error is None
        assert response.result == {}

    def test_unknown_method(self) -> None:
        """Test handling of unknown method."""
        handler = MCPHandler()

        # Create request with unknown method
        request = JSONRPCRequest(
            id=6,
            method="unknown/method",
        )

        # Handle request
        response_str = handler.handle_message(json.dumps(request.model_dump()))
        assert response_str is not None

        # Parse response
        response_data = json.loads(response_str)
        response = JSONRPCResponse(**response_data)

        # Verify error response
        assert response.id == 6
        assert response.error is not None
        assert response.result is None
        assert response.error["code"] == -32601  # Method not found
        assert "Method not found" in response.error["message"]

    def test_invalid_json(self) -> None:
        """Test handling of invalid JSON."""
        handler = MCPHandler()

        # Send invalid JSON
        response_str = handler.handle_message("not valid json")
        assert response_str is not None

        # Parse error response
        response_data = json.loads(response_str)
        response = JSONRPCResponse(**response_data)

        # Verify parse error
        assert response.id == 0  # ID is 0 when it cannot be determined
        assert response.error is not None
        assert response.error["code"] == -32700  # Parse error
        assert "Parse error" in response.error["message"]

    def test_invalid_tool_params(self) -> None:
        """Test handling of invalid tool parameters."""
        handler = MCPHandler()

        # Create tools/call request with invalid params
        request = JSONRPCRequest(
            id=7,
            method=MCPMethod.TOOLS_CALL,
            params={
                # Missing required 'name' field
                "arguments": {},
            },
        )

        # Handle request
        response_str = handler.handle_message(json.dumps(request.model_dump()))
        assert response_str is not None

        # Parse response
        response_data = json.loads(response_str)
        response = JSONRPCResponse(**response_data)

        # Verify error response
        assert response.id == 7
        assert response.error is None
        assert response.result is not None

        result = response.result
        assert result["isError"] is True
        assert "Invalid parameters" in result["content"][0]["text"]

    def test_request_counting(self) -> None:
        """Test that requests are counted correctly."""
        handler = MCPHandler()
        assert handler.request_count == 0

        # Send first request
        request1 = JSONRPCRequest(id=1, method=MCPMethod.PING)
        handler.handle_message(json.dumps(request1.model_dump()))
        assert handler.request_count == 1

        # Send second request
        request2 = JSONRPCRequest(id=2, method=MCPMethod.TOOLS_LIST)
        handler.handle_message(json.dumps(request2.model_dump()))
        assert handler.request_count == 2
