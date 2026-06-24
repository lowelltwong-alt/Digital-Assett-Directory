from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .database import CatalogDB
from .ids import stable_id, session_id as new_session_id
from .models import HandoffRecord, LessonRecord
from .utils import append_jsonl, split_multi, utc_now, write_json


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
