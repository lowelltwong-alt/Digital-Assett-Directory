#!/usr/bin/env python3
"""Claude Code hook bridge for mandatory session evidence and postflight capture.

This hook never edits source assets. It only writes hub session/audit evidence.
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_input() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def changed_files(cwd: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except Exception:
        return []
    return [line[3:] for line in result.stdout.splitlines() if len(line) > 3]


def main() -> int:
    event = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    payload = read_input()
    project = Path(payload.get("cwd") or payload.get("project_dir") or Path.cwd()).resolve()
    hub = Path(__file__).resolve().parents[1]
    external_session = str(
        payload.get("session_id") or payload.get("conversation_id") or uuid.uuid4()
    )
    internal_uuid = uuid.uuid5(
        uuid.UUID("d7d89920-42cf-4c2d-9b7b-cfa3b7b33a24"), f"claude|{project}|{external_session}"
    )
    sid = f"dad:session:{internal_uuid}"
    session_path = hub / "state" / "agent_sessions" / f"{internal_uuid}.json"
    audit_path = hub / "audit" / "events" / f"{now()[:10]}.jsonl"

    if event == "session-start":
        if not session_path.exists():
            session = {
                "schema_version": "0.1.0",
                "session_id": sid,
                "external_session_id": external_session,
                "created_at": now(),
                "repository": str(project),
                "agent": "claude-code",
                "task": "Claude Code session; replace with task context in postflight",
                "status": "open",
                "baseline_changed_files": changed_files(project),
                "required_postflight": True,
                "auto_created_by_hook": True,
            }
            write_json(session_path, session)
            append_jsonl(audit_path, {"event_type": "claude_session_start", **session})
        print(
            f"Digital Asset Directory session: {sid}. Before completion run asset-dir agent postflight --session {sid} --summary <summary> --hub {hub}"
        )
        return 0

    if event == "post-tool":
        tool = payload.get("tool_name") or payload.get("tool") or "unknown"
        append_jsonl(
            audit_path,
            {
                "event_type": "claude_post_tool",
                "created_at": now(),
                "session_id": sid,
                "repository": str(project),
                "tool": str(tool),
                "tool_input_keys": sorted((payload.get("tool_input") or {}).keys())
                if isinstance(payload.get("tool_input"), dict)
                else [],
            },
        )
        return 0

    if event == "stop":
        if payload.get("stop_hook_active"):
            return 0
        if not session_path.exists():
            return 0
        session = json.loads(session_path.read_text(encoding="utf-8"))
        changed = changed_files(project)
        if session.get("status") == "open" and changed:
            draft = {
                "schema_version": "0.1.0",
                "handoff_id": f"dad:handoff-draft:{internal_uuid}",
                "session_id": sid,
                "created_at": now(),
                "repository": str(project),
                "agent": "claude-code",
                "task": session.get("task", ""),
                "summary": "Auto-captured draft because the session attempted to stop with repository changes and no postflight.",
                "files_changed": changed,
                "commands_run": [],
                "tests_run": [],
                "tests_not_run": ["Unknown: complete the postflight explicitly"],
                "confirmed": ["Working tree contains changes"],
                "inferred": [],
                "assumptions": [],
                "unknowns": ["Tests, lessons, risks, and task outcome require explicit postflight"],
                "lessons": [],
                "risks": ["Uncaptured build learning"],
                "next_actions": [
                    f"Run asset-dir agent postflight --session {sid} --summary <summary> --hub {hub}"
                ],
                "review_status": "auto_captured_unreviewed",
            }
            write_json(hub / "raw" / "handoffs" / now()[:10] / f"auto-{internal_uuid}.json", draft)
            print(
                json.dumps(
                    {
                        "decision": "block",
                        "reason": f"Changed working tree requires Digital Asset Directory postflight. Session: {sid}. Run asset-dir agent postflight --session {sid} --summary <summary> --hub {hub}.",
                    }
                )
            )
            return 0
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
