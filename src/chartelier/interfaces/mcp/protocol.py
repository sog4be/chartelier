"""MCP protocol message models and definitions."""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class JSONRPCMessage(BaseModel):
    """Base JSON-RPC 2.0 message."""

    jsonrpc: Literal["2.0"] = "2.0"


class JSONRPCRequest(JSONRPCMessage):
    """JSON-RPC 2.0 request message."""

    id: int | str | None = None  # Notifications don't have ID
    method: str
    params: dict[str, Any] | None = None


class JSONRPCResponse(JSONRPCMessage):
    """JSON-RPC 2.0 response message."""

    id: int | str
    result: Any | None = None
    error: dict[str, Any] | None = None


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 error object."""

    code: int
    message: str
    data: Any | None = None


class MCPMethod(str, Enum):
    """MCP protocol methods."""

    INITIALIZE = "initialize"
    INITIALIZED = "initialized"
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    PING = "ping"


class ServerInfo(BaseModel):
    """MCP server information."""

    name: str = "chartelier"
    version: str = "0.2.0"
    title: str = "Chartelier MCP Server"


class ToolsCapability(BaseModel):
    """Tools capability configuration."""

    listChanged: bool = False  # noqa: N815


class ServerCapabilities(BaseModel):
    """MCP server capabilities."""

    tools: ToolsCapability | None = None


class InitializeResult(BaseModel):
    """Response for initialize method."""

    protocolVersion: str = "2025-06-18"  # noqa: N815
    serverInfo: ServerInfo = Field(default_factory=ServerInfo)  # noqa: N815
    capabilities: ServerCapabilities = Field(default_factory=lambda: ServerCapabilities(tools=ToolsCapability()))
    instructions: str = (
        "Use `chartelier_visualize` to convert CSV/JSON + intent (ja/en) into a static chart. "
        "Required: data, query. Defaults: format=png, dpi=300, size=1200x900. Timeout 60s. "
        "Pattern selection failure returns error."
    )


class ToolInputSchema(BaseModel):
    """Schema definition for tool input parameters."""

    type: Literal["object"] = "object"
    required: list[str]
    properties: dict[str, dict[str, Any]]


class Tool(BaseModel):
    """MCP tool definition."""

    name: str
    description: str
    inputSchema: ToolInputSchema  # noqa: N815


class ToolsListResult(BaseModel):
    """Response for tools/list method."""

    tools: list[Tool]


class ToolCallParams(BaseModel):
    """Parameters for tools/call method."""

    name: str
    arguments: dict[str, Any]


class ImageContent(BaseModel):
    """Image content in tool response."""

    type: Literal["image"] = "image"
    data: str  # Base64 encoded image
    mimeType: str  # noqa: N815


class TextContent(BaseModel):
    """Text content in tool response."""

    type: Literal["text"] = "text"
    text: str


class ToolCallResult(BaseModel):
    """Response for tools/call method."""

    content: list[ImageContent | TextContent]
    structuredContent: dict[str, Any] | None = None  # noqa: N815
    isError: bool = False  # noqa: N815


def get_chartelier_tool() -> Tool:
    """Get the chartelier_visualize tool definition."""
    return Tool(
        name="chartelier_visualize",
        description=(
            "CSV/JSON + intent (ja/en) -> static chart (PNG/SVG). "
            "Uses 9 predefined patterns; pattern selection failure returns error."
        ),
        inputSchema=ToolInputSchema(
            required=["data", "query"],
            properties={
                "data": {"type": "string", "description": "CSV or table-like JSON (UTF-8)"},
                "query": {"type": "string", "maxLength": 1000},
                "options": {
                    "type": "object",
                    "properties": {
                        "format": {"enum": ["png", "svg"], "default": "png"},
                        "dpi": {"type": "integer", "minimum": 72, "maximum": 300, "default": 300},
                        "width": {"type": "integer", "minimum": 600, "maximum": 2000, "default": 1200},
                        "height": {"type": "integer", "minimum": 400, "maximum": 2000, "default": 900},
                        "locale": {"enum": ["ja", "en"]},
                    },
                },
            },
        ),
    )
