"""MCP protocol handler implementation."""

import json
from typing import Any

from pydantic import ValidationError

from chartelier.core.enums import MCPErrorCode
from chartelier.core.errors import ChartelierError
from chartelier.infra.logging import get_logger
from chartelier.interfaces.mcp.protocol import (
    InitializeResult,
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    MCPMethod,
    TextContent,
    ToolCallParams,
    ToolCallResult,
    ToolsListResult,
    get_chartelier_tool,
)
from chartelier.interfaces.validators import RequestValidator

logger = get_logger(__name__)


class MCPHandler:
    """Handler for MCP protocol messages."""

    def __init__(self) -> None:
        """Initialize the MCP handler."""
        self.initialized = False
        self.request_count = 0
        self.validator = RequestValidator()

    def handle_message(self, message: str) -> str | None:
        """Handle a JSON-RPC message and return response.

        Args:
            message: Raw JSON-RPC message string

        Returns:
            JSON-RPC response string or None if no response needed
        """
        try:
            # Parse JSON-RPC request
            data = json.loads(message)
            request = JSONRPCRequest(**data)

            # Log request (without data content)
            if request.id is not None:
                logger.info(
                    "Received MCP request",
                    extra={
                        "method": request.method,
                        "id": request.id,
                        "request_count": self.request_count,
                    },
                )
            else:
                logger.info(
                    "Received MCP notification",
                    extra={
                        "method": request.method,
                        "request_count": self.request_count,
                    },
                )
            self.request_count += 1

            # Route to appropriate handler
            if request.method == MCPMethod.INITIALIZE:
                result = self._handle_initialize(request.params or {})
            elif request.method == MCPMethod.INITIALIZED:
                # No response needed for initialized notification
                self.initialized = True
                logger.info("MCP connection initialized")
                return None
            elif request.method == MCPMethod.TOOLS_LIST:
                result = self._handle_tools_list()
            elif request.method == MCPMethod.TOOLS_CALL:
                result = self._handle_tools_call(request.params or {})
            elif request.method == MCPMethod.PING:
                result = {}  # Empty object for ping response
            else:
                # Method not found
                error = JSONRPCError(
                    code=MCPErrorCode.METHOD_NOT_FOUND,
                    message=f"Method not found: {request.method}",
                )
                response = JSONRPCResponse(id=request.id if request.id is not None else 0, error=error.model_dump())
                return json.dumps(response.model_dump(exclude_none=True))

            # Create success response (only if we have a result and an ID)
            if request.id is not None:
                response = JSONRPCResponse(id=request.id, result=result)
                return json.dumps(response.model_dump(exclude_none=True))
            # Notifications don't need a response
            return None  # noqa: TRY300

        except json.JSONDecodeError as e:
            # Invalid JSON
            logger.error("Invalid JSON received: %s", e)  # noqa: TRY400
            error_response = JSONRPCResponse(
                id=0,  # Use 0 when ID cannot be determined
                error=JSONRPCError(
                    code=MCPErrorCode.PARSE_ERROR,
                    message="Parse error: Invalid JSON",
                    data=str(e),
                ).model_dump(),
            )
            return json.dumps(error_response.model_dump(exclude_none=True))
        except Exception as e:
            # Internal error
            logger.exception("Internal error handling MCP request")
            error_response = JSONRPCResponse(
                id=data.get("id", 0) if "data" in locals() else 0,
                error=JSONRPCError(
                    code=MCPErrorCode.INTERNAL_ERROR,
                    message="Internal error",
                    data=str(e),
                ).model_dump(),
            )
            return json.dumps(error_response.model_dump(exclude_none=True))

    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle initialize request.

        Args:
            params: Initialize parameters

        Returns:
            Initialize result
        """
        logger.info("Handling initialize request", extra={"params": params})
        result = InitializeResult()
        return result.model_dump(by_alias=True)

    def _handle_tools_list(self) -> dict[str, Any]:
        """Handle tools/list request.

        Returns:
            Tools list result
        """
        logger.info("Handling tools/list request")
        tool = get_chartelier_tool()
        result = ToolsListResult(tools=[tool])
        return result.model_dump(by_alias=True)

    def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle tools/call request.

        Args:
            params: Tool call parameters

        Returns:
            Tool call result
        """
        try:
            # Parse parameters
            try:
                call_params = ToolCallParams(**params)
            except ValidationError as e:
                # Invalid parameters
                logger.warning("Invalid tool call parameters: %s", e)
                error_result = ToolCallResult(
                    content=[TextContent(text=f"Invalid parameters: {e}")],
                    isError=True,
                )
                return error_result.model_dump(by_alias=True)
            logger.info(
                "Handling tools/call request",
                extra={
                    "tool_name": call_params.name,
                    "has_arguments": bool(call_params.arguments),
                },
            )

            # Currently only support chartelier_visualize
            if call_params.name != "chartelier_visualize":
                error_result = ToolCallResult(
                    content=[
                        TextContent(text=f"Unknown tool: {call_params.name}. Only 'chartelier_visualize' is supported.")
                    ],
                    isError=True,
                )
                return error_result.model_dump(by_alias=True)

            # Validate request using RequestValidator
            try:
                validated_request = self.validator.validate(call_params.arguments or {})
                logger.info(
                    "Request validated successfully",
                    extra={
                        "data_format": validated_request.data_format,
                        "data_size_bytes": validated_request.data_size_bytes,
                        "query_length": len(validated_request.query),
                    },
                )
            except ChartelierError as e:
                logger.warning("Request validation failed: %s", e)
                error_result = ToolCallResult(
                    content=[TextContent(text=f"Validation error: {e.message}")],
                    structuredContent={
                        "error": {
                            "code": e.code.value,
                            "message": e.message,
                            "hint": e.hint,
                            "details": e.details,
                        }
                    },
                    isError=True,
                )
                return error_result.model_dump(by_alias=True)

            # For now, return a placeholder response
            # This will be replaced with actual Coordinator call in PR-C3
            placeholder_result = ToolCallResult(
                content=[
                    TextContent(
                        text="Chart generation not yet implemented. This will be implemented in subsequent PRs."
                    )
                ],
                structuredContent={
                    "metadata": {
                        "status": "not_implemented",
                        "message": "Coordinator integration pending (PR-C3)",
                        "validated_data_format": validated_request.data_format,
                    }
                },
                isError=True,
            )
            return placeholder_result.model_dump(by_alias=True)
        except ChartelierError as e:
            # Chartelier-specific error (for future use)
            logger.error("Chartelier error: %s", e)  # noqa: TRY400
            error_result = ToolCallResult(
                content=[TextContent(text=str(e))],
                structuredContent={"error": {"code": e.code.value, "message": e.message, "hint": e.hint}},
                isError=True,
            )
            return error_result.model_dump(by_alias=True)
        except Exception as e:
            # Unexpected error
            logger.exception("Unexpected error in tools/call")
            error_result = ToolCallResult(
                content=[TextContent(text=f"Internal error: {e}")],
                isError=True,
            )
            return error_result.model_dump(by_alias=True)
