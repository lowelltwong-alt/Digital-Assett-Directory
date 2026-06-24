from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .database import CatalogDB
from .ids import stable_id, session_id as new_session_id
from .models import HandoffRecord, LessonRecord
from .utils import append_jsonl, split_multi, utc_now, write_json

ASSET_USE_FEEDBACK_CODE = "DAD_ASSET_USE_FEEDBACK_V1"


def git_changed_files(repo: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    return [
        line[3:] if len(line) > 3 else line for line in result.stdout.splitlines() if line.strip()
    ]


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "unknown"


def _lesson_pointer(record: LessonRecord) -> dict[str, Any]:
    dated = record.created_at[:10]
    return {
        "lesson_id": record.lesson_id,
        "created_at": record.created_at,
        "repository": record.repository,
        "summary": record.summary,
        "reusable_patterns": record.reusable_patterns,
        "missing_capabilities": record.missing_capabilities,
        "session_id": record.session_id,
        "source_path": f"raw/lessons/{dated}/{record.lesson_id.split(':')[-1]}.json",
    }


def route_lesson(repo_root: Path, record: LessonRecord) -> list[Path]:
    """Append a context-rich pointer to repo- and capability-scoped lesson indexes.

    The dated canonical JSON under raw/lessons/<date>/ stays the source of truth; these
    append-only JSONL indexes make a lesson findable by repository and by capability,
    instead of only by the date it was captured.
    """
    pointer = _lesson_pointer(record)
    base = repo_root / "raw" / "lessons"
    written: list[Path] = []

    repo_name = Path(record.repository).name if record.repository else "unknown"
    repo_index = base / "by-repo" / f"{_slug(repo_name)}.jsonl"
    append_jsonl(repo_index, pointer)
    written.append(repo_index)

    for capability in sorted(dict.fromkeys(record.missing_capabilities or ["_general"])):
        cap_index = base / "by-capability" / f"{_slug(capability)}.jsonl"
        append_jsonl(cap_index, pointer)
        written.append(cap_index)
    return written


def rebuild_lesson_routes(repo_root: Path) -> dict[str, Any]:
    """Rebuild by-repo and by-capability indexes from the canonical dated lesson files.

    Indexes are append-only at capture time, so re-running this dedupes by lesson_id.
    """
    base = repo_root / "raw" / "lessons"
    for sub in ("by-repo", "by-capability"):
        target = base / sub
        if target.exists():
            for path in target.glob("*.jsonl"):
                path.unlink()
    seen: set[str] = set()
    indexed = 0
    for path in sorted(base.glob("*/*.json")):
        if path.parent.name in {"by-repo", "by-capability"}:
            continue
        try:
            record = LessonRecord.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if record.lesson_id in seen:
            continue
        seen.add(record.lesson_id)
        route_lesson(repo_root, record)
        indexed += 1
    return {
        "lessons_indexed": indexed,
        "by_repo_dir": str(base / "by-repo"),
        "by_capability_dir": str(base / "by-capability"),
    }


def add_lesson(repo_root: Path, database_path: Path, **kwargs: Any) -> LessonRecord:
    created = utc_now()
    record = LessonRecord(
        lesson_id=stable_id(
            "lesson", created, kwargs.get("repository", ""), kwargs.get("summary", "")
        ),
        created_at=created,
        repository=str(kwargs.get("repository", "")),
        task=str(kwargs.get("task", "")),
        agent=str(kwargs.get("agent", "human")),
        model=kwargs.get("model"),
        summary=str(kwargs.get("summary", "")),
        lessons=split_multi(kwargs.get("lessons")),
        files_changed=split_multi(kwargs.get("files_changed")),
        tests_run=split_multi(kwargs.get("tests_run")),
        tests_not_run=split_multi(kwargs.get("tests_not_run")),
        discoveries=split_multi(kwargs.get("discoveries")),
        failures=split_multi(kwargs.get("failures")),
        reusable_patterns=split_multi(kwargs.get("reusable_patterns")),
        missing_capabilities=split_multi(kwargs.get("missing_capabilities")),
        evidence=split_multi(kwargs.get("evidence")),
        confidence=kwargs.get("confidence", "medium"),
        review_status=kwargs.get("review_status", "candidate"),
        session_id=kwargs.get("session_id"),
    )
    dated = created[:10]
    write_json(
        repo_root / "raw" / "lessons" / dated / f"{record.lesson_id.split(':')[-1]}.json",
        record.model_dump(mode="json"),
    )
    route_lesson(repo_root, record)
    append_jsonl(
        repo_root / "audit" / "events" / f"{dated}.jsonl",
        {
            "event_type": "lesson_added",
            "created_at": created,
            "object_id": record.lesson_id,
            "repository": record.repository,
        },
    )
    with CatalogDB(database_path) as db:
        db.add_lesson(record)
    return record


def add_asset_use_feedback(
    repo_root: Path,
    database_path: Path,
    *,
    asset_id: str,
    repository: str,
    task: str,
    agent: str,
    used_for: str,
    use_outcome: str = "unknown",
    observed_usefulness: str = "unknown",
    observed_futurefulness: str = "unknown",
    interaction_stage: str = "after_use",
    expected_usefulness: str = "unknown",
    expected_futurefulness: str = "unknown",
    expected_value_reason: str = "",
    planned_use: str = "",
    found_by: str = "",
    found_query: str = "",
    parts_used: list[str] | None = None,
    parts_not_used: list[str] | None = None,
    not_used_reason: str = "",
    upgrades_made: list[str] | None = None,
    difficulties: list[str] | None = None,
    things_learned: list[str] | None = None,
    missing_parts_seen: list[str] | None = None,
    score_feedback: str = "",
    ceiling_feedback: str = "",
    evidence: list[str] | None = None,
    model: str | None = None,
    confidence: str = "medium",
) -> LessonRecord:
    allowed_outcomes = {"helped", "blocked", "no_effect", "unknown"}
    allowed_observations = {"low", "medium", "high", "unknown"}
    allowed_stages = {"before_use", "after_use"}
    if interaction_stage not in allowed_stages:
        raise ValueError(
            "interaction_stage must be one of: " + ", ".join(sorted(allowed_stages))
        )
    if use_outcome not in allowed_outcomes:
        raise ValueError(
            "use_outcome must be one of: " + ", ".join(sorted(allowed_outcomes))
        )
    if observed_usefulness not in allowed_observations:
        raise ValueError(
            "observed_usefulness must be one of: "
            + ", ".join(sorted(allowed_observations))
        )
    if observed_futurefulness not in allowed_observations:
        raise ValueError(
            "observed_futurefulness must be one of: "
            + ", ".join(sorted(allowed_observations))
        )
    if expected_usefulness not in allowed_observations:
        raise ValueError(
            "expected_usefulness must be one of: "
            + ", ".join(sorted(allowed_observations))
        )
    if expected_futurefulness not in allowed_observations:
        raise ValueError(
            "expected_futurefulness must be one of: "
            + ", ".join(sorted(allowed_observations))
        )

    missing_parts = missing_parts_seen or []
    evidence_items = evidence or []
    used_parts = parts_used or []
    unused_parts = parts_not_used or []
    upgrades = upgrades_made or []
    difficulty_items = difficulties or []
    learned_items = things_learned or []
    feedback_lines = [
        f"feedback_code={ASSET_USE_FEEDBACK_CODE}",
        f"interaction_stage={interaction_stage}",
        f"asset_id={asset_id}",
        f"found_by={found_by}",
        f"found_query={found_query}",
        f"used_for={used_for}",
        f"planned_use={planned_use}",
        f"expected_usefulness={expected_usefulness}",
        f"expected_futurefulness={expected_futurefulness}",
        f"expected_value_reason={expected_value_reason}",
        "parts_used=" + ";".join(used_parts),
        "parts_not_used=" + ";".join(unused_parts),
        f"not_used_reason={not_used_reason}",
        "upgrades_made=" + ";".join(upgrades),
        "difficulties=" + ";".join(difficulty_items),
        "things_learned=" + ";".join(learned_items),
        f"use_outcome={use_outcome}",
        f"observed_usefulness={observed_usefulness}",
        f"observed_futurefulness={observed_futurefulness}",
    ]
    if missing_parts:
        feedback_lines.append("missing_parts_seen=" + ";".join(missing_parts))
    if score_feedback:
        feedback_lines.append(f"score_feedback={score_feedback}")
    if ceiling_feedback:
        feedback_lines.append(f"ceiling_feedback={ceiling_feedback}")

    return add_lesson(
        repo_root,
        database_path,
        repository=repository,
        task=task,
        agent=agent,
        model=model,
        summary=f"Asset use feedback for {asset_id}: {interaction_stage}/{use_outcome}",
        lessons=feedback_lines,
        discoveries=[
            (
                "Observed asset usefulness feedback is candidate evidence for future "
                "score-range and ceiling-range calibration."
            )
        ],
        reusable_patterns=["asset_use_feedback_loop"],
        missing_capabilities=missing_parts,
        evidence=[f"asset:{asset_id}", *evidence_items],
        confidence=confidence,
        review_status="candidate",
    )


def preflight(
    hub_root: Path,
    target_repo: Path,
    database_path: Path,
    agent: str,
    task: str,
    model: str | None = None,
) -> dict[str, Any]:
    sid = new_session_id()
    payload: dict[str, Any] = {
        "schema_version": "0.1.0",
        "session_id": sid,
        "created_at": utc_now(),
        "repository": str(target_repo.resolve()),
        "agent": agent,
        "model": model,
        "task": task,
        "status": "open",
        "baseline_changed_files": git_changed_files(target_repo),
        "required_postflight": True,
    }
    write_json(hub_root / "state" / "agent_sessions" / f"{sid.split(':')[-1]}.json", payload)
    append_jsonl(
        hub_root / "audit" / "events" / f"{payload['created_at'][:10]}.jsonl",
        {"event_type": "agent_preflight", **payload},
    )
    return payload


def load_session(hub_root: Path, sid: str) -> tuple[Path, dict[str, Any]]:
    path = hub_root / "state" / "agent_sessions" / f"{sid.split(':')[-1]}.json"
    if not path.exists():
        raise FileNotFoundError(f"Agent session not found: {sid}")
    return path, json.loads(path.read_text(encoding="utf-8"))


def postflight(
    hub_root: Path, database_path: Path, sid: str, summary: str, **kwargs: Any
) -> tuple[HandoffRecord, LessonRecord]:
    session_path, session = load_session(hub_root, sid)
    repository = Path(session["repository"])
    changed = split_multi(kwargs.get("files_changed")) or git_changed_files(repository)
    created = utc_now()
    handoff = HandoffRecord(
        handoff_id=stable_id("handoff", sid, created),
        session_id=sid,
        created_at=created,
        repository=str(repository),
        agent=session.get("agent", "unknown"),
        task=session.get("task", ""),
        summary=summary,
        files_changed=changed,
        commands_run=split_multi(kwargs.get("commands_run")),
        tests_run=split_multi(kwargs.get("tests_run")),
        tests_not_run=split_multi(kwargs.get("tests_not_run")),
        confirmed=split_multi(kwargs.get("confirmed")),
        inferred=split_multi(kwargs.get("inferred")),
        assumptions=split_multi(kwargs.get("assumptions")),
        unknowns=split_multi(kwargs.get("unknowns")),
        lessons=split_multi(kwargs.get("lessons")),
        risks=split_multi(kwargs.get("risks")),
        next_actions=split_multi(kwargs.get("next_actions")),
        review_status=kwargs.get("review_status", "candidate"),
    )
    dated = created[:10]
    write_json(
        hub_root / "raw" / "handoffs" / dated / f"{handoff.handoff_id.split(':')[-1]}.json",
        handoff.model_dump(mode="json"),
    )
    with CatalogDB(database_path) as db:
        db.add_handoff(handoff)
    lesson = add_lesson(
        hub_root,
        database_path,
        repository=str(repository),
        task=session.get("task", ""),
        agent=session.get("agent", "unknown"),
        model=session.get("model"),
        summary=summary,
        lessons=kwargs.get("lessons") or [summary],
        files_changed=changed,
        tests_run=kwargs.get("tests_run"),
        tests_not_run=kwargs.get("tests_not_run"),
        discoveries=kwargs.get("discoveries"),
        failures=kwargs.get("failures"),
        reusable_patterns=kwargs.get("reusable_patterns"),
        missing_capabilities=kwargs.get("missing_capabilities"),
        evidence=kwargs.get("evidence"),
        confidence=kwargs.get("confidence", "medium"),
        session_id=sid,
    )
    session.update(
        {
            "status": "closed",
            "closed_at": created,
            "handoff_id": handoff.handoff_id,
            "lesson_id": lesson.lesson_id,
        }
    )
    write_json(session_path, session)
    append_jsonl(
        hub_root / "audit" / "events" / f"{dated}.jsonl",
        {
            "event_type": "agent_postflight",
            "created_at": created,
            "session_id": sid,
            "handoff_id": handoff.handoff_id,
            "lesson_id": lesson.lesson_id,
        },
    )
    return handoff, lesson


def open_sessions(hub_root: Path, repository: Path | None = None) -> list[dict[str, Any]]:
    sessions = []
    for path in (hub_root / "state" / "agent_sessions").glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("status") != "open":
            continue
        if repository and Path(payload.get("repository", "")).resolve() != repository.resolve():
            continue
        sessions.append(payload)
    return sessions
