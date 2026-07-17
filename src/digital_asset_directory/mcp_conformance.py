"""Synthetic, provider-neutral conformance checks for a future remote adapter."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

REQUIRED_METHODS = ("initialize", "resources/list", "tools/list", "prompts/list")


def run_synthetic_conformance(handler: Callable[[dict[str, Any]], Mapping[str, Any]]) -> dict[str, Any]:
    """Exercise only synthetic requests; never connects, authenticates, or writes."""

    failures: list[str] = []
    for method in REQUIRED_METHODS:
        try:
            response = handler({"jsonrpc": "2.0", "id": method, "method": method, "params": {}})
        except Exception:
            failures.append(f"handler_exception:{method}")
            continue
        if not isinstance(response, Mapping) or "error" in response or "result" not in response:
            failures.append(f"missing_result:{method}")

    hostile = [
        ("unknown_method", {"jsonrpc": "2.0", "id": 20, "method": "shell/execute", "params": {}}),
        ("path_uri", {"jsonrpc": "2.0", "id": 21, "method": "resources/read", "params": {"uri": "dad://registry/../secret"}}),
        ("oversized", {"jsonrpc": "2.0", "id": 22, "method": "prompts/get", "params": {"name": "dad_preflight_briefing", "arguments": {"task": "x" * 10000, "agent": "synthetic"}}}),
    ]
    for label, request in hostile:
        try:
            response = handler(request)
        except Exception:
            continue
        if not isinstance(response, Mapping) or "error" not in response:
            failures.append(f"hostile_not_rejected:{label}")

    return {
        "schema_version": "dad.mcp.remote_conformance_report.v1",
        "status": "passed" if not failures else "failed",
        "synthetic_only": True,
        "remote_connected": False,
        "execution_authorized": False,
        "failure_codes": sorted(set(failures)),
    }


__all__ = ["REQUIRED_METHODS", "run_synthetic_conformance"]
