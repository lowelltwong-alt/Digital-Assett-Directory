#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record DAD agent lifecycle hook events without binding to one AI runtime."
    )
    parser.add_argument("event", choices=["session-start", "post-tool", "stop"])
    parser.add_argument("--hub", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--external-session-id")
    parser.add_argument("--task", default="")
    parser.add_argument("--tool", default="")
    parser.add_argument("--tool-input-key", action="append", default=[])
    parser.add_argument("--stop-hook-active", action="store_true")
    args = parser.parse_args()

    sys.path.insert(0, str(args.hub.resolve() / "src"))
    from digital_asset_directory.agent_lifecycle import handle_lifecycle_event

    result = handle_lifecycle_event(
        args.event,
        hub_root=args.hub,
        repo=args.repo,
        agent=args.agent,
        external_session_id=args.external_session_id or os.environ.get("DAD_AGENT_SESSION_ID"),
        task=args.task or None,
        tool=args.tool or None,
        tool_input_keys=args.tool_input_key,
        stop_hook_active=args.stop_hook_active,
    )
    if result.payload is not None:
        print(json.dumps(result.payload, sort_keys=True))
    elif result.message:
        print(result.message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
