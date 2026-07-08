"""Compatibility facade for the local read-only DAD graph MCP server.

The canonical implementation lives in :mod:`digital_asset_directory.mcp_server`.
This module preserves the branch-stack import path without creating a second
MCP authority surface.
"""

from __future__ import annotations

from .mcp_server import DADGraphMCPServer, MCPError, run_stdio_server

__all__ = ["DADGraphMCPServer", "MCPError", "run_stdio_server"]
