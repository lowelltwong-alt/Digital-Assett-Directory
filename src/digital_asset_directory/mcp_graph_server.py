"""Compatibility facade for the local read-only DAD graph MCP server.

The canonical implementation lives in :mod:`digital_asset_directory.mcp_server`.
This module preserves the branch-stack import path without creating a second
MCP authority surface.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .mcp_server import (
    MCPError,
    call_mcp_tool,
    handle_mcp_request,
    list_mcp_resources,
    mcp_tool_definitions,
    read_mcp_resource,
    serve_stdio,
)
from .utils import json_dumps


class DADGraphMCPServer:
    """Small class-style adapter over the canonical function-based server."""

    def __init__(self, hub_root: Path) -> None:
        self.hub_root = hub_root.resolve()

    def list_resources(self) -> list[dict[str, Any]]:
        return list_mcp_resources(self.hub_root)

    def read_resource(self, uri: str) -> dict[str, Any]:
        return {"contents": [read_mcp_resource(self.hub_root, uri)]}

    def list_tools(self) -> list[dict[str, Any]]:
        return mcp_tool_definitions()

    def call_tool(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        payload = call_mcp_tool(self.hub_root, name, arguments or {})
        return {
            "content": [{"type": "text", "text": json_dumps(payload, pretty=True)}],
            "structuredContent": payload,
            "isError": False,
        }

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        request_id = request.get("id")
        method = str(request.get("method", ""))
        params = request.get("params") or {}
        try:
            if method == "notifications/initialized":
                return None
            if method == "ping":
                result: dict[str, Any] = {}
            elif method == "resources/list":
                result = {"resources": self.list_resources()}
            elif method == "resources/read":
                result = self.read_resource(str(params.get("uri", "")))
            elif method == "tools/list":
                result = {"tools": self.list_tools()}
            elif method == "tools/call":
                result = self.call_tool(
                    str(params.get("name", "")),
                    params.get("arguments") if isinstance(params.get("arguments"), dict) else {},
                )
            else:
                response = handle_mcp_request(self.hub_root, request)
                if response is None or "error" in response:
                    return response
                return response
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except MCPError as exc:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": exc.code, "message": str(exc)},
            }
        except TypeError as exc:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": str(exc)},
            }


def run_stdio_server(hub_root: Path) -> None:
    """Run the canonical content-length stdio MCP server."""

    serve_stdio(hub_root)
