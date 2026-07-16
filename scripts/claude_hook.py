#!/usr/bin/env python3
"""Claude Code hook bridge for the DAD agent lifecycle adapter."""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

SCRIPT_HUB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_HUB / "src"))


def read_input() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def main() -> int:
    from digital_asset_directory.agent_lifecycle import command_signature_digest, handle_lifecycle_event

    event = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    payload = read_input()
    project = Path(payload.get("cwd") or payload.get("project_dir") or Path.cwd()).resolve()
    hub = Path(os.environ.get("DAD_HUB") or SCRIPT_HUB).resolve()
    external_session = str(
        payload.get("session_id") or payload.get("conversation_id") or uuid.uuid4()
    )
    tool_input = payload.get("tool_input")
    tool_input_keys = sorted(tool_input.keys()) if isinstance(tool_input, dict) else []
    command = str(tool_input.get("command", "")) if isinstance(tool_input, dict) else ""
    lowered_command = command.lower()
    suppressors = []
    if any(marker in lowered_command for marker in ("hyperfine", "--benchmark", "cold-cache", "pytest-repeat", "--count=")):
        suppressors.append("intentional_benchmark_or_isolation")
    tool_outcome = "failed" if payload.get("is_error") is True else "unknown"

    result = handle_lifecycle_event(
        event,
        hub_root=hub,
        repo=project,
        agent="claude-code",
        external_session_id=external_session,
        tool=str(payload.get("tool_name") or payload.get("tool") or "unknown"),
        tool_input_keys=tool_input_keys,
        tool_input_digest=command_signature_digest(command) if command else None,
        tool_outcome=tool_outcome,
        repeat_suppressors=suppressors,
        stop_hook_active=bool(payload.get("stop_hook_active")),
        session_key_agent="claude",
    )
    if result.payload is not None:
        print(json.dumps(result.payload, sort_keys=True))
    elif result.message:
        print(result.message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
