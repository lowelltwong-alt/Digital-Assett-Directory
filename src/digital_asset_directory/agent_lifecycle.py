from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .transport import data_path, existing_data_file
from .utils import append_jsonl, utc_now, write_json

AGENT_LIFECYCLE_NAMESPACE = uuid.UUID("d7d89920-42cf-4c2d-9b7b-cfa3b7b33a24")


@dataclass(frozen=True, slots=True)
class LifecycleResult:
    session_id: str
    message: str = ""
    payload: dict[str, Any] | None = None


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


def stable_lifecycle_session_id(
    repo: Path,
    *,
    agent: str,
    external_session_id: str,
    session_key_agent: str | None = None,
) -> tuple[str, uuid.UUID]:
    key_agent = session_key_agent or agent
    internal_uuid = uuid.uuid5(
        AGENT_LIFECYCLE_NAMESPACE,
        f"{key_agent}|{repo.resolve()}|{external_session_id}",
    )
    return f"dad:session:{internal_uuid}", internal_uuid


def handle_lifecycle_event(
    event: str,
    *,
    hub_root: Path,
    repo: Path,
    agent: str,
    external_session_id: str | None = None,
    task: str | None = None,
    tool: str | None = None,
    tool_input_keys: list[str] | None = None,
    stop_hook_active: bool = False,
    session_key_agent: str | None = None,
) -> LifecycleResult:
    if not agent.strip():
        raise ValueError("agent must be a non-empty string")
    external_session_id = (external_session_id or "").strip() or "default"

    hub_root = hub_root.resolve()
    repo = repo.resolve()
    sid, internal_uuid = stable_lifecycle_session_id(
        repo,
        agent=agent,
        external_session_id=external_session_id,
        session_key_agent=session_key_agent,
    )
    # Resolve through the transport data plane so hook-created sessions land
    # where the CLI (preflight/postflight/enforce) reads them; existing_data_file
    # keeps sessions written before the data-root reroute reachable at the
    # legacy hub-relative path.
    session_path = existing_data_file(
        hub_root, "agent_sessions", f"{internal_uuid}.json"
    )
    created = utc_now()
    audit_path = data_path(hub_root, "audit_events") / f"{created[:10]}.jsonl"

    if event == "session-start":
        if not session_path.exists():
            session = {
                "schema_version": "0.1.0",
                "session_id": sid,
                "external_session_id": external_session_id,
                "created_at": created,
                "repository": str(repo),
                "agent": agent,
                "task": task or f"{agent} session; replace with task context in postflight",
                "status": "open",
                "baseline_changed_files": changed_files(repo),
                "required_postflight": True,
                "auto_created_by_hook": True,
            }
            write_json(session_path, session)
            append_jsonl(
                audit_path,
                {
                    "event_type": "agent_lifecycle_session_start",
                    "lifecycle_event": event,
                    **session,
                },
            )
        message = (
            f"Digital Asset Directory session: {sid}. Before completion run "
            f"asset-dir agent postflight --session {sid} --summary <summary> --hub {hub_root}"
        )
        return LifecycleResult(session_id=sid, message=message)

    if event == "post-tool":
        append_jsonl(
            audit_path,
            {
                "event_type": "agent_lifecycle_post_tool",
                "created_at": created,
                "session_id": sid,
                "repository": str(repo),
                "agent": agent,
                "tool": str(tool or "unknown"),
                "tool_input_keys": sorted(tool_input_keys or []),
            },
        )
        return LifecycleResult(session_id=sid)

    if event == "stop":
        if stop_hook_active or not session_path.exists():
            return LifecycleResult(session_id=sid)
        session_payload = json.loads(session_path.read_text(encoding="utf-8"))
        changed = changed_files(repo)
        if session_payload.get("status") == "open" and changed:
            draft = {
                "schema_version": "0.1.0",
                "handoff_id": f"dad:handoff-draft:{internal_uuid}",
                "session_id": sid,
                "created_at": created,
                "repository": str(repo),
                "agent": session_payload.get("agent", agent),
                "task": session_payload.get("task", ""),
                "summary": (
                    "Auto-captured draft because the session attempted to stop "
                    "with repository changes and no postflight."
                ),
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
                    f"Run asset-dir agent postflight --session {sid} --summary <summary> --hub {hub_root}"
                ],
                "review_status": "auto_captured_unreviewed",
            }
            write_json(
                data_path(hub_root, "raw_handoffs") / created[:10] / f"auto-{internal_uuid}.json",
                draft,
            )
            payload = {
                "decision": "block",
                "reason": (
                    "Changed working tree requires Digital Asset Directory postflight. "
                    f"Session: {sid}. Run asset-dir agent postflight --session {sid} "
                    f"--summary <summary> --hub {hub_root}."
                ),
            }
            return LifecycleResult(session_id=sid, payload=payload)
        return LifecycleResult(session_id=sid)

    return LifecycleResult(session_id=sid)
