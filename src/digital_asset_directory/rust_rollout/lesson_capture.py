from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from ..ids import stable_id
from ..utils import append_jsonl, utc_now, write_json


REQUIRED_LESSON_FIELDS = {
    "source_repo",
    "phase",
    "problem",
    "observed_failure_or_friction",
    "fix_or_workaround",
    "reusable_pattern",
    "applies_to_repo_types",
    "should_change_future_prompt",
    "should_change_future_template",
    "confidence",
    "evidence_refs",
}


def append_rust_rollout_lesson(ledger_path: Path, lesson: dict[str, Any]) -> dict[str, Any]:
    missing = sorted(field for field in REQUIRED_LESSON_FIELDS if field not in lesson)
    if missing:
        raise ValueError(f"Missing Rust rollout lesson fields: {', '.join(missing)}")
    record = {
        "schema_version": "dad_rust_rollout_lesson.v1",
        "lesson_id": lesson.get("lesson_id")
        or stable_id(
            "rust-rollout-lesson",
            str(lesson["source_repo"]),
            str(lesson["phase"]),
            str(lesson["problem"]),
            str(lesson["fix_or_workaround"]),
        ),
        "timestamp": lesson.get("timestamp") or utc_now(),
        **lesson,
    }
    append_jsonl(ledger_path, record)
    return record


def load_rust_rollout_lessons(ledger_path: Path) -> list[dict[str, Any]]:
    if not ledger_path.exists():
        return []
    lessons: list[dict[str, Any]] = []
    for line_number, line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            import json

            lessons.append(json.loads(line))
        except Exception as exc:  # pragma: no cover - defensive summary path
            lessons.append(
                {
                    "schema_version": "dad_rust_rollout_lesson_parse_error.v1",
                    "line_number": line_number,
                    "error": str(exc),
                }
            )
    return lessons


def summarize_rust_rollout_lessons(ledger_path: Path, out_dir: Path) -> dict[str, Any]:
    lessons = load_rust_rollout_lessons(ledger_path)
    by_phase = Counter(str(row.get("phase", "unknown")) for row in lessons)
    summary = {
        "schema_version": "dad_rust_rollout_lesson_summary.v1",
        "ledger_path": _display_path(ledger_path),
        "lesson_count": len(lessons),
        "count_by_phase": dict(sorted(by_phase.items())),
        "lessons": lessons,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "dad_forced_implementation_postflight.json", summary)
    (out_dir / "dad_forced_implementation_postflight.md").write_text(
        _summary_markdown(summary), encoding="utf-8"
    )
    return summary


def _summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# DAD Rust Implementation Lessons",
        "",
        f"Lesson count: {summary['lesson_count']}",
        "",
        "## By Phase",
        "",
    ]
    for phase, count in summary["count_by_phase"].items():
        lines.append(f"- `{phase}`: {count}")
    lines.extend(["", "## Lessons", ""])
    for lesson in summary["lessons"]:
        lines.append(f"- `{lesson.get('lesson_id', 'unknown')}`: {lesson.get('problem', '')}")
    lines.append("")
    return "\n".join(lines)


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()
