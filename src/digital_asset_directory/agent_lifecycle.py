from __future__ import annotations

import json
import hashlib
import re
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .transport import data_path, existing_data_file
from .utils import append_jsonl, utc_now, write_json

AGENT_LIFECYCLE_NAMESPACE = uuid.UUID("d7d89920-42cf-4c2d-9b7b-cfa3b7b33a24")
_VOLATILE_COMMAND_TOKEN = re.compile(
    r"(?i)(?:[0-9a-f]{8}-[0-9a-f-]{27,}|20\d{2}-\d{2}-\d{2}[T_ ][0-9:.+-]+|"
    r"(?:/tmp|\\temp\\|\\tmp\\)[^\s\"']+)"
)
_COMMAND_TOOLS = {"bash", "shell", "shell_command", "powershell", "cmd"}
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class LifecycleResult:
    session_id: str
    message: str = ""
    payload: dict[str, Any] | None = None


def command_signature_digest(command: str) -> str:
    """Return a privacy-safe signature without retaining command text."""

    normalized = " ".join(_VOLATILE_COMMAND_TOKEN.sub("<volatile>", command).split())
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def repo_state_digest(cwd: Path) -> tuple[str, str]:
    """Hash HEAD plus exact content of every dirty/untracked path."""

    try:
        head = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "HEAD"],
            capture_output=True,
            timeout=15,
            check=False,
        )
        status = subprocess.run(
            ["git", "-C", str(cwd), "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            capture_output=True,
            timeout=15,
            check=False,
        )
    except Exception:
        return "", "coverage_unavailable"
    if head.returncode:
        try:
            head = subprocess.run(
                ["git", "-C", str(cwd), "symbolic-ref", "-q", "HEAD"],
                capture_output=True,
                timeout=15,
                check=False,
            )
        except Exception:
            return "", "coverage_unavailable"
    if head.returncode or status.returncode:
        return "", "coverage_unavailable"
    digest = hashlib.sha256()
    digest.update(head.stdout.strip())
    entries = [entry for entry in status.stdout.split(b"\0") if entry]
    for entry in entries:
        digest.update(b"\0" + entry)
        raw_path = entry[3:] if len(entry) >= 4 and entry[2:3] == b" " else entry
        try:
            relative = raw_path.decode("utf-8", errors="surrogateescape")
            path = cwd / relative
            if path.is_file():
                with path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1_048_576), b""):
                        digest.update(chunk)
            else:
                digest.update(b"<missing-or-non-file>")
        except OSError:
            return "", "coverage_unavailable"
    return "sha256:" + digest.hexdigest(), "exact_git_worktree"


def _prior_repeat_count(audit_path: Path, *, session_id: str, tool: str, signature: str, state: str) -> tuple[int, int, bool]:
    count = 0
    max_duration = 0
    latest_failed = False
    if not audit_path.exists():
        return count, max_duration, latest_failed
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (
            row.get("event_type") == "agent_lifecycle_post_tool"
            and row.get("session_id") == session_id
            and str(row.get("tool", "")).lower() == tool.lower()
            and row.get("tool_input_digest") == signature
            and row.get("repo_state_digest") == state
        ):
            count += 1
            max_duration = max(max_duration, int(row.get("duration_ms") or 0))
            latest_failed = row.get("tool_outcome") == "failed"
    return count, max_duration, latest_failed


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
    tool_input_digest: str | None = None,
    duration_ms: int | None = None,
    tool_outcome: str = "unknown",
    repeat_suppressors: list[str] | None = None,
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
            if (repo / "registry" / "portable-capability-registry.json").exists():
                from .portability_control import assess_lifecycle

                session["portability_gate"] = assess_lifecycle(
                    repo,
                    stage="preflight",
                    task=str(session["task"]),
                    paths=session["baseline_changed_files"],
                )
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

    if event == "pre-tool":
        normalized_tool = str(tool or "unknown").lower()
        safe_input_digest = (
            tool_input_digest
            if tool_input_digest and _DIGEST.fullmatch(tool_input_digest)
            else command_signature_digest(tool_input_digest or "") if tool_input_digest else ""
        )
        state, state_coverage = repo_state_digest(repo)
        repeat_count, prior_duration, prior_failed = (0, 0, False)
        if safe_input_digest and normalized_tool in _COMMAND_TOOLS and state_coverage == "exact_git_worktree":
            repeat_count, prior_duration, prior_failed = _prior_repeat_count(
                audit_path,
                session_id=sid,
                tool=normalized_tool,
                signature=safe_input_digest,
                state=state,
            )
        suppressors = sorted(set(repeat_suppressors or []))
        if prior_failed:
            suppressors.append("prior_failure_retry")
        candidate = bool(
            not suppressors
            and state_coverage == "exact_git_worktree"
            and (repeat_count >= 2 or (repeat_count >= 1 and prior_duration >= 5_000))
        )
        append_jsonl(
            audit_path,
            {
                "event_type": "agent_lifecycle_pre_tool",
                "created_at": created,
                "session_id": sid,
                "repository": str(repo),
                "agent": agent,
                "tool": normalized_tool,
                "tool_input_digest": safe_input_digest,
                "repo_state_digest": state,
                "state_coverage": state_coverage,
                "prior_same_state_count": repeat_count,
                "suppressor_codes": sorted(set(suppressors)),
                "redundant_work_candidate": candidate,
                "model_calls": 0,
            },
        )
        message = ""
        if candidate:
            message = (
                "DAD redundant-work guard: this normalized command already ran against the "
                "same repository state. Reuse prior immutable evidence or add a state-keyed "
                "cache/narrower test unless this is an intentional benchmark or failure retry."
            )
        return LifecycleResult(session_id=sid, message=message)

    if event == "post-tool":
        portability_gate: dict[str, Any] | None = None
        current_changed = changed_files(repo)
        if (repo / "registry" / "portable-capability-registry.json").exists() and current_changed:
            from .portability_control import assess_lifecycle

            portability_gate = assess_lifecycle(
                repo,
                stage="midflight",
                task=task or "",
                paths=current_changed,
            )
        safe_input_digest = (
            tool_input_digest
            if tool_input_digest and _DIGEST.fullmatch(tool_input_digest)
            else command_signature_digest(tool_input_digest or "") if tool_input_digest else ""
        )
        state, state_coverage = repo_state_digest(repo)
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
                "tool_input_digest": safe_input_digest,
                "repo_state_digest": state,
                "state_coverage": state_coverage,
                "duration_ms": duration_ms,
                "tool_outcome": tool_outcome if tool_outcome in {"succeeded", "failed", "unknown"} else "unknown",
                "suppressor_codes": sorted(set(repeat_suppressors or [])),
                "portability_gate": portability_gate,
            },
        )
        return LifecycleResult(session_id=sid)

    if event == "stop":
        if stop_hook_active or not session_path.exists():
            return LifecycleResult(session_id=sid)
        session_payload = json.loads(session_path.read_text(encoding="utf-8"))
        changed = changed_files(repo)
        if (repo / "registry" / "portable-capability-registry.json").exists():
            from .portability_control import assess_lifecycle

            session_payload["portability_stop_gate"] = assess_lifecycle(
                repo,
                stage="postflight",
                task=str(session_payload.get("task", "")),
                paths=changed,
            )
            write_json(session_path, session_payload)
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
