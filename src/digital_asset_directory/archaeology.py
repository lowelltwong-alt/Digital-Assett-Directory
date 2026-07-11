from __future__ import annotations

import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from .config import LocalSource
from .ids import stable_id
from .models import (
    AssetRecord,
    ChangePatternRecord,
    CounterfactualLessonRecord,
    FailureSignalRecord,
    RepoLearningEventRecord,
    RepoTimelineEventRecord,
    RootCauseHypothesisRecord,
    WorktreeAttemptRecord,
)
from .transport import data_relative_path
from .logos_write_guard import assert_dad_write_allowed
from .utils import append_jsonl, atomic_write_text, utc_now, write_jsonl

AUTHORITY_BOUNDARY = (
    "Generated candidate only; source repositories retain authority; context-bound "
    "lessons require human review before reuse or promotion."
)
SAFETY_CONFIRMATION = (
    "This repository learning event is data only. It does not request code execution, "
    "credential access, source mutation, dependency installation, or automatic promotion."
)
FAILURE_TERMS = {
    "blocked",
    "drift",
    "error",
    "fail",
    "failed",
    "failure",
    "false negative",
    "false positive",
    "fixme",
    "flaky",
    "missing gate",
    "regression",
    "revert",
    "todo",
}
STABILIZER_TERMS = {
    "approval",
    "contract",
    "evaluation",
    "gate",
    "gold",
    "human review",
    "review packet",
    "schema",
    "test",
    "validator",
}
CONTEXT_TERM_MAP: dict[str, tuple[str, ...]] = {
    "route_isolation": ("route", "routing", "form classification", "route isolation"),
    "chunking": ("chunk", "chunking", "span", "context packet"),
    "gold_promotion": ("gold", "golden", "promotion", "reviewed gold"),
    "schema_contract": ("schema", "validator", "contract", "json schema"),
    "source_authority": ("authority", "source of truth", "canon", "provenance"),
    "human_gate": ("human review", "review gate", "approval", "preflight", "postflight"),
    "duplicate_variant": ("duplicate", "variant", "delta", "near duplicate", "same file"),
    "temp_fixture_noise": ("pytest-tmp", "tmp", "temp", "fixture", "synthetic"),
    "dependency_ordering": ("dependency", "before", "after", "precede", "ordering"),
    "late_stabilizer": ("late", "stabilizer", "validator", "gate", "test"),
    "repeated_failure": ("repeat", "again", "regression", "failure", "failed", "revert"),
    "counterfactual_sequence": ("counterfactual", "better order", "should precede"),
    "score_methodology": ("score", "grade", "confidence", "threshold", "formula", "methodology"),
    "calibration": ("calibration", "label", "false positive", "false negative", "weight"),
}


@dataclass(frozen=True)
class ArchaeologyResult:
    attempts: list[WorktreeAttemptRecord]
    timeline_events: list[RepoTimelineEventRecord]
    change_patterns: list[ChangePatternRecord]
    failure_signals: list[FailureSignalRecord]
    repo_learning_events: list[RepoLearningEventRecord]


@dataclass(frozen=True)
class RootCauseResult:
    root_causes: list[RootCauseHypothesisRecord]
    counterfactual_lessons: list[CounterfactualLessonRecord]


def _asset_text(asset: AssetRecord) -> str:
    metadata = asset.metadata
    return " ".join(
        [
            asset.title,
            asset.description,
            asset.logical_path,
            " ".join(asset.tags),
            " ".join(asset.capabilities),
            str(metadata.get("excerpt", ""))[:6000],
            str(metadata.get("chunk_text", ""))[:12000],
            " ".join(str(token) for token in metadata.get("text_tokens", [])[:500]),
        ]
    ).lower()


def infer_context_tags(*texts: str) -> list[str]:
    combined = " ".join(text.lower() for text in texts if text)
    tags = {
        tag
        for tag, terms in CONTEXT_TERM_MAP.items()
        if any(term in combined for term in terms)
    }
    if any(term in combined for term in FAILURE_TERMS):
        tags.add("repeated_failure")
    if any(term in combined for term in STABILIZER_TERMS):
        tags.add("late_stabilizer")
    if "_codex_worktrees" in combined or ".pytest-tmp-root" in combined:
        tags.add("temp_fixture_noise" if ".pytest-tmp-root" in combined else "dependency_ordering")
    return sorted(tags)


def _path_parts(logical_path: str) -> list[str]:
    return [part for part in PurePosixPath(logical_path.replace("\\", "/")).parts if part]


def _attempt_from_asset(asset: AssetRecord) -> tuple[str, str, str, str] | None:
    parts = _path_parts(asset.logical_path)
    lowered = [part.lower() for part in parts]
    if "_codex_worktrees" in lowered:
        index = lowered.index("_codex_worktrees")
        if len(parts) > index + 1:
            root_parts = parts[: index + 2]
            attempt_path = "/".join(root_parts)
            task_hint = parts[index + 1]
            lineage = re.sub(r"-t\d+.*$", "", task_hint.lower()) or task_hint.lower()
            return "worktree", lineage, attempt_path, task_hint
    if ".pytest-tmp-root" in lowered or any(part in {"tmp", "temp"} for part in lowered):
        marker_indexes = [
            lowered.index(marker)
            for marker in (".pytest-tmp-root", "tmp", "temp")
            if marker in lowered
        ]
        index = min(marker_indexes) if marker_indexes else 0
        end = min(len(parts), index + 5)
        attempt_path = "/".join(parts[:end])
        task_hint = parts[end - 1] if end else "temp"
        return "temp", task_hint.lower(), attempt_path, task_hint
    if "99_archive" in lowered or "archive" in lowered or "zips" in lowered:
        index = min(
            [lowered.index(part) for part in ("99_archive", "archive", "zips") if part in lowered]
        )
        end = min(len(parts), index + 3)
        attempt_path = "/".join(parts[:end])
        task_hint = parts[end - 1] if end else "archive"
        return "archive", task_hint.lower(), attempt_path, task_hint
    if asset.asset_type == "repository":
        return "repository", PurePosixPath(asset.logical_path).name.lower(), asset.logical_path, asset.title
    return None


def build_worktree_attempts(
    assets: list[AssetRecord],
    *,
    scan_id: str,
    source_id: str = "all",
    include_worktrees: bool = True,
    include_temp: bool = True,
    generated_at: str | None = None,
) -> list[WorktreeAttemptRecord]:
    generated = generated_at or utc_now()
    groups: dict[tuple[str, str, str, str], list[AssetRecord]] = defaultdict(list)
    for asset in assets:
        if source_id != "all" and asset.source_id != source_id:
            continue
        attempt = _attempt_from_asset(asset)
        if not attempt:
            continue
        kind, _lineage, _path, _hint = attempt
        if kind == "worktree" and not include_worktrees:
            continue
        if kind == "temp" and not include_temp:
            continue
        groups[attempt].append(asset)

    records: list[WorktreeAttemptRecord] = []
    for (kind, lineage, attempt_path, task_hint), group_assets in sorted(groups.items()):
        context_tags = infer_context_tags(
            attempt_path,
            task_hint,
            " ".join(asset.title for asset in group_assets[:25]),
            " ".join(asset.logical_path for asset in group_assets[:25]),
        )
        records.append(
            WorktreeAttemptRecord(
                attempt_id=stable_id("worktree-attempt", kind, lineage, attempt_path),
                attempt_kind=kind,  # type: ignore[arg-type]
                repo_lineage_key=lineage,
                attempt_path=attempt_path,
                task_hint=task_hint,
                branch_name=task_hint if kind == "worktree" else "",
                source_asset_ids=[asset.asset_id for asset in group_assets[:100]],
                context_tags=context_tags,
                evidence={
                    "asset_count": len(group_assets),
                    "sample_paths": [asset.logical_path for asset in group_assets[:12]],
                    "candidate_only": True,
                },
                generated_at=generated,
                scan_id=scan_id,
            )
        )
    return records


def _resolve_asset_path(asset: AssetRecord, local_sources: list[LocalSource]) -> Path | None:
    logical = asset.logical_path.replace("\\", "/")
    for source in local_sources:
        alias = source.path_alias.strip("/")
        if logical == alias:
            return source.path
        prefix = f"{alias}/"
        if logical.startswith(prefix):
            return source.path / logical[len(prefix) :]
    return None


def _git_log(repo_path: Path, max_commits: int) -> list[dict[str, Any]]:
    if not (repo_path / ".git").exists():
        return []
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "log",
                f"-n{max_commits}",
                "--date=iso-strict",
                "--name-only",
                "--pretty=format:---DAD-COMMIT---%H%x09%ad%x09%s",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    commits: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("---DAD-COMMIT---"):
            if current:
                commits.append(current)
            payload = line.replace("---DAD-COMMIT---", "", 1)
            parts = payload.split("\t", 2)
            current = {
                "hash": parts[0] if parts else "",
                "date": parts[1] if len(parts) > 1 else "",
                "subject": parts[2] if len(parts) > 2 else "",
                "changed_paths": [],
            }
        elif current is not None:
            current["changed_paths"].append(line)
    if current:
        commits.append(current)
    return commits


def build_repo_timeline_events(
    assets: list[AssetRecord],
    local_sources: list[LocalSource],
    *,
    scan_id: str,
    source_id: str = "all",
    max_repos: int = 25,
    max_commits: int = 200,
    generated_at: str | None = None,
) -> list[RepoTimelineEventRecord]:
    generated = generated_at or utc_now()
    repo_assets = [
        asset
        for asset in assets
        if asset.asset_type == "repository" and (source_id == "all" or asset.source_id == source_id)
    ][:max_repos]
    records: list[RepoTimelineEventRecord] = []
    for asset in repo_assets:
        path = _resolve_asset_path(asset, local_sources)
        if not path:
            continue
        for commit in _git_log(path, max_commits):
            subject = str(commit["subject"])
            changed_paths = list(commit["changed_paths"])[:100]
            lower_subject = subject.lower()
            event_type = "commit"
            if "merge" in lower_subject:
                event_type = "merge"
            if "revert" in lower_subject:
                event_type = "revert"
            context_tags = infer_context_tags(subject, " ".join(changed_paths), asset.logical_path)
            records.append(
                RepoTimelineEventRecord(
                    timeline_event_id=stable_id(
                        "repo-timeline-event", asset.asset_id, str(commit["hash"])
                    ),
                    repository_path=asset.logical_path,
                    event_type=event_type,  # type: ignore[arg-type]
                    occurred_at=str(commit["date"] or generated),
                    asset_ids=[asset.asset_id],
                    changed_paths=changed_paths,
                    summary=subject or "Local git commit",
                    evidence={
                        "commit": commit["hash"],
                        "bounded_history": True,
                        "max_commits": max_commits,
                    },
                    context_tags=context_tags,
                    generated_at=generated,
                    scan_id=scan_id,
                )
            )
    return records


def _failure_terms_in(text: str) -> list[str]:
    lowered = text.lower()
    return sorted(term for term in FAILURE_TERMS if term in lowered)


def _signal_type(terms: list[str], asset: AssetRecord | None = None) -> str:
    joined = " ".join(terms)
    if "revert" in joined:
        return "revert"
    if "drift" in joined:
        return "drift"
    if "todo" in joined or "fixme" in joined:
        return "todo_fixme"
    if asset and asset.asset_type == "test":
        return "test_failure"
    if "missing gate" in joined:
        return "missing_gate"
    return "error_word"


def build_failure_signals(
    assets: list[AssetRecord],
    timeline_events: list[RepoTimelineEventRecord],
    *,
    scan_id: str,
    source_id: str = "all",
    generated_at: str | None = None,
) -> list[FailureSignalRecord]:
    generated = generated_at or utc_now()
    signals: list[FailureSignalRecord] = []
    for asset in assets:
        if source_id != "all" and asset.source_id != source_id:
            continue
        text = _asset_text(asset)
        terms = _failure_terms_in(text)
        if not terms:
            continue
        context_tags = infer_context_tags(text, asset.logical_path)
        signals.append(
            FailureSignalRecord(
                failure_signal_id=stable_id("failure-signal", "asset", asset.asset_id, ",".join(terms)),
                signal_type=_signal_type(terms, asset),  # type: ignore[arg-type]
                asset_ids=[asset.asset_id],
                signal_terms=terms,
                summary=f"Failure-like terms in {asset.title}",
                evidence={
                    "logical_path": asset.logical_path,
                    "asset_type": asset.asset_type,
                    "candidate_only": True,
                },
                context_tags=context_tags,
                confidence="medium",
                risk="high" if "temp_fixture_noise" in context_tags else "medium",
                generated_at=generated,
                scan_id=scan_id,
            )
        )
    for event in timeline_events:
        terms = _failure_terms_in(f"{event.summary} {' '.join(event.changed_paths)}")
        if not terms:
            continue
        signals.append(
            FailureSignalRecord(
                failure_signal_id=stable_id(
                    "failure-signal", "timeline", event.timeline_event_id, ",".join(terms)
                ),
                signal_type=_signal_type(terms),  # type: ignore[arg-type]
                asset_ids=event.asset_ids,
                signal_terms=terms,
                summary=f"Failure-like local history event: {event.summary}",
                evidence={"timeline_event_id": event.timeline_event_id, "candidate_only": True},
                context_tags=sorted(set(event.context_tags) | {"repeated_failure"}),
                confidence="medium",
                risk="medium",
                generated_at=generated,
                scan_id=scan_id,
            )
        )
    return sorted(signals, key=lambda item: item.failure_signal_id)


def _is_stabilizer(asset_or_path: str) -> bool:
    lowered = asset_or_path.lower()
    return any(term in lowered for term in STABILIZER_TERMS)


def build_change_patterns(
    assets: list[AssetRecord],
    attempts: list[WorktreeAttemptRecord],
    timeline_events: list[RepoTimelineEventRecord],
    failure_signals: list[FailureSignalRecord],
    *,
    scan_id: str,
    source_id: str = "all",
    generated_at: str | None = None,
    limit: int = 100,
) -> list[ChangePatternRecord]:
    generated = generated_at or utc_now()
    patterns: dict[str, ChangePatternRecord] = {}

    path_counts: Counter[str] = Counter()
    pair_counts: Counter[tuple[str, str]] = Counter()
    for event in timeline_events:
        paths = sorted(set(event.changed_paths))
        for path in paths:
            path_counts[path] += 1
        for index, left in enumerate(paths[:20]):
            for right in paths[index + 1 : 20]:
                pair_counts[(left, right)] += 1

    for path, count in path_counts.most_common(limit):
        if count < 2:
            continue
        record = ChangePatternRecord(
            change_pattern_id=stable_id("change-pattern", "repeated_edit", path),
            pattern_type="repeated_edit",
            paths=[path],
            summary=f"`{path}` changed {count} times in bounded local history.",
            evidence={"change_count": count, "bounded_history": True},
            context_tags=infer_context_tags(path, "repeated edit"),
            confidence="medium",
            risk="medium",
            generated_at=generated,
            scan_id=scan_id,
        )
        patterns[record.change_pattern_id] = record

    for (left, right), count in pair_counts.most_common(limit):
        if count < 2:
            continue
        record = ChangePatternRecord(
            change_pattern_id=stable_id("change-pattern", "co_change", left, right),
            pattern_type="co_change",
            paths=[left, right],
            summary=f"`{left}` and `{right}` changed together {count} times.",
            evidence={"co_change_count": count, "bounded_history": True},
            context_tags=infer_context_tags(left, right, "changed together"),
            confidence="medium",
            risk="medium",
            generated_at=generated,
            scan_id=scan_id,
        )
        patterns[record.change_pattern_id] = record

    basename_groups: dict[str, list[AssetRecord]] = defaultdict(list)
    for asset in assets:
        if source_id != "all" and asset.source_id != source_id:
            continue
        basename_groups[PurePosixPath(asset.logical_path.replace("\\", "/")).name.lower()].append(asset)
    for basename, group in sorted(basename_groups.items()):
        if len(group) < 3 or basename in {"readme.md", "license", ".gitignore"}:
            continue
        context_tags = infer_context_tags(basename, "variant duplicate same file")
        record = ChangePatternRecord(
            change_pattern_id=stable_id("change-pattern", "variant_file", basename),
            pattern_type="variant_file",
            asset_ids=[asset.asset_id for asset in group[:50]],
            paths=[asset.logical_path for asset in group[:20]],
            summary=f"`{basename}` appears across {len(group)} assets and may need variant review.",
            evidence={"same_basename_count": len(group), "candidate_only": True},
            context_tags=sorted(set(context_tags) | {"duplicate_variant"}),
            confidence="low" if len(group) < 5 else "medium",
            risk="medium",
            generated_at=generated,
            scan_id=scan_id,
        )
        patterns[record.change_pattern_id] = record
        if len(patterns) >= limit * 3:
            break

    failure_asset_ids = {aid for signal in failure_signals for aid in signal.asset_ids}
    stabilizers = [
        asset
        for asset in assets
        if (source_id == "all" or asset.source_id == source_id)
        and _is_stabilizer(f"{asset.title} {asset.logical_path} {asset.description}")
    ][:50]
    if failure_asset_ids and stabilizers:
        record = ChangePatternRecord(
            change_pattern_id=stable_id(
                "change-pattern",
                "late_stabilizer",
                ",".join(sorted(list(failure_asset_ids))[:20]),
                ",".join(asset.asset_id for asset in stabilizers[:10]),
            ),
            pattern_type="late_stabilizer",
            asset_ids=[*sorted(failure_asset_ids)[:25], *(asset.asset_id for asset in stabilizers[:25])],
            paths=[asset.logical_path for asset in stabilizers[:25]],
            summary=(
                "Failure-like signals and stabilizer assets both appear in the current "
                "catalog; review whether tests, schemas, gates, or gold packets arrived late."
            ),
            evidence={
                "failure_signal_count": len(failure_signals),
                "stabilizer_sample_count": len(stabilizers),
                "attempt_count": len(attempts),
                "candidate_only": True,
            },
            context_tags=["dependency_ordering", "late_stabilizer", "repeated_failure"],
            confidence="low",
            risk="high",
            generated_at=generated,
            scan_id=scan_id,
        )
        patterns[record.change_pattern_id] = record

    return sorted(patterns.values(), key=lambda item: item.change_pattern_id)[: limit * 3]


def _load_repo_learning_events_from_assets(
    assets: list[AssetRecord], *, scan_id: str, source_id: str = "all"
) -> list[RepoLearningEventRecord]:
    records: list[RepoLearningEventRecord] = []
    for asset in assets:
        if source_id != "all" and asset.source_id != source_id:
            continue
        if not asset.logical_path.replace("\\", "/").endswith(
            ".digital-asset-directory/learning/events.jsonl"
        ):
            continue
        text = str(asset.metadata.get("chunk_text") or asset.metadata.get("excerpt") or "")
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                records.append(RepoLearningEventRecord.model_validate_json(line))
            except Exception:
                continue
    return sorted(records, key=lambda item: item.event_id)


def run_archaeology(
    assets: list[AssetRecord],
    local_sources: list[LocalSource],
    *,
    scan_id: str,
    source_id: str = "all",
    include_worktrees: bool = True,
    include_temp: bool = True,
    max_repos: int = 25,
    max_commits: int = 200,
    generated_at: str | None = None,
) -> ArchaeologyResult:
    generated = generated_at or utc_now()
    attempts = build_worktree_attempts(
        assets,
        scan_id=scan_id,
        source_id=source_id,
        include_worktrees=include_worktrees,
        include_temp=include_temp,
        generated_at=generated,
    )
    timeline_events = build_repo_timeline_events(
        assets,
        local_sources,
        scan_id=scan_id,
        source_id=source_id,
        max_repos=max_repos,
        max_commits=max_commits,
        generated_at=generated,
    )
    failure_signals = build_failure_signals(
        assets,
        timeline_events,
        scan_id=scan_id,
        source_id=source_id,
        generated_at=generated,
    )
    change_patterns = build_change_patterns(
        assets,
        attempts,
        timeline_events,
        failure_signals,
        scan_id=scan_id,
        source_id=source_id,
        generated_at=generated,
    )
    repo_events = _load_repo_learning_events_from_assets(assets, scan_id=scan_id, source_id=source_id)
    return ArchaeologyResult(attempts, timeline_events, change_patterns, failure_signals, repo_events)


def build_root_cause_lessons(
    archaeology: ArchaeologyResult,
    *,
    scan_id: str,
    generated_at: str | None = None,
) -> RootCauseResult:
    generated = generated_at or utc_now()
    root_causes: list[RootCauseHypothesisRecord] = []
    lessons: list[CounterfactualLessonRecord] = []
    late_patterns = [
        pattern for pattern in archaeology.change_patterns if pattern.pattern_type == "late_stabilizer"
    ]
    repeated_failures = archaeology.failure_signals[:50]
    for pattern in late_patterns[:25]:
        source_events = [
            pattern.change_pattern_id,
            *(signal.failure_signal_id for signal in repeated_failures[:10]),
        ]
        evidence_asset_ids = sorted(set(pattern.asset_ids))[:50]
        context_tags = sorted(
            set(pattern.context_tags)
            | {"counterfactual_sequence", "dependency_ordering", "late_stabilizer"}
        )
        root = RootCauseHypothesisRecord(
            root_cause_id=stable_id("root-cause", pattern.change_pattern_id),
            hypothesis=(
                "Repeated failure or rework may have been caused by stabilizers such as "
                "tests, schemas, validators, review gates, or gold packets arriving too late."
            ),
            evidence_asset_ids=evidence_asset_ids,
            source_events=source_events,
            context_tags=context_tags,
            applies_when=[
                "A similar task has route, schema, evaluation, promotion, or source-authority risk.",
                "Failure-like signals appear before validation, review, or gold artifacts are stable.",
            ],
            does_not_apply_when=[
                "The source sequence is unknown or the stabilizer was present before the failure.",
                "The work is exploratory and intentionally pre-contract.",
            ],
            confidence=pattern.confidence,
            risk="high",
            authority_boundary=AUTHORITY_BOUNDARY,
            generated_at=generated,
            scan_id=scan_id,
        )
        lesson = CounterfactualLessonRecord(
            lesson_candidate_id=stable_id("counterfactual-lesson", root.root_cause_id),
            lesson_candidate=(
                "In similar contexts, establish the smallest validation/review route before "
                "promoting outputs or expanding implementation."
            ),
            applies_when=root.applies_when,
            does_not_apply_when=root.does_not_apply_when,
            danger_if_misapplied=(
                "Applied too broadly, this can turn every exploratory task into a heavy "
                "governance exercise and hide genuine requirement changes."
            ),
            counterfactual_better_order=[
                "Identify source authority and context tags.",
                "Create or select the minimal test/schema/review gate.",
                "Run the implementation or promotion step.",
                "Capture after-work evidence and update the lesson only after review.",
            ],
            evidence_asset_ids=evidence_asset_ids,
            source_events=source_events,
            context_tags=context_tags,
            confidence=pattern.confidence,
            risk="high",
            authority_boundary=AUTHORITY_BOUNDARY,
            generated_at=generated,
            scan_id=scan_id,
        )
        root_causes.append(root)
        lessons.append(lesson)
    return RootCauseResult(root_causes=root_causes, counterfactual_lessons=lessons)


def _summary_counts(archaeology: ArchaeologyResult) -> dict[str, int]:
    return {
        "attempt_count": len(archaeology.attempts),
        "timeline_event_count": len(archaeology.timeline_events),
        "change_pattern_count": len(archaeology.change_patterns),
        "failure_signal_count": len(archaeology.failure_signals),
        "repo_learning_event_count": len(archaeology.repo_learning_events),
    }


def archaeology_markdown(
    archaeology: ArchaeologyResult, *, generated_at: str, review_sample: int
) -> str:
    counts = _summary_counts(archaeology)
    lines = [
        "# Worktree Archaeology",
        "",
        "Generated candidate report only. Worktrees and temp repos are noisy process evidence.",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Attempts: **{counts['attempt_count']}**",
        f"- Timeline events: **{counts['timeline_event_count']}**",
        f"- Change patterns: **{counts['change_pattern_count']}**",
        f"- Failure signals: **{counts['failure_signal_count']}**",
        f"- Repo learning events: **{counts['repo_learning_event_count']}**",
        "",
        "## Attempt Sample",
        "",
    ]
    for attempt in archaeology.attempts[:review_sample]:
        lines.extend(
            [
                f"### {attempt.task_hint or attempt.attempt_path}",
                f"- Kind: `{attempt.attempt_kind}`",
                f"- Path: `{attempt.attempt_path}`",
                f"- Context tags: `{attempt.context_tags}`",
                f"- Asset evidence count: **{len(attempt.source_asset_ids)}**",
                "",
            ]
        )
    lines.extend(["## Change Pattern Sample", ""])
    for pattern in archaeology.change_patterns[:review_sample]:
        lines.extend(
            [
                f"- `{pattern.pattern_type}` `{pattern.change_pattern_id}`: {pattern.summary}",
                f"  Context: `{pattern.context_tags}`",
            ]
        )
    lines.extend(["", "## Failure Signal Sample", ""])
    for signal in archaeology.failure_signals[:review_sample]:
        lines.extend(
            [
                f"- `{signal.signal_type}` `{signal.failure_signal_id}`: {signal.summary}",
                f"  Terms: `{signal.signal_terms}` Context: `{signal.context_tags}`",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def root_cause_markdown(result: RootCauseResult, *, generated_at: str, review_sample: int) -> str:
    lines = [
        "# Root Cause Lesson Candidates",
        "",
        "Generated candidate report only. Counterfactual lessons require context review.",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Root cause hypotheses: **{len(result.root_causes)}**",
        f"- Counterfactual lessons: **{len(result.counterfactual_lessons)}**",
        "",
    ]
    for lesson in result.counterfactual_lessons[:review_sample]:
        lines.extend(
            [
                f"## {lesson.lesson_candidate_id}",
                "",
                f"- Lesson candidate: {lesson.lesson_candidate}",
                f"- Context tags: `{lesson.context_tags}`",
                f"- Applies when: {'; '.join(lesson.applies_when)}",
                f"- Does not apply when: {'; '.join(lesson.does_not_apply_when)}",
                f"- Danger if misapplied: {lesson.danger_if_misapplied}",
                "- Better order:",
            ]
        )
        for step in lesson.counterfactual_better_order:
            lines.append(f"  - {step}")
        lines.append("")
    return "\n".join(lines)


def context_tag_coverage_markdown(
    archaeology: ArchaeologyResult,
    root_causes: RootCauseResult,
    *,
    generated_at: str,
) -> str:
    counter: Counter[str] = Counter()
    for collection in [
        archaeology.attempts,
        archaeology.timeline_events,
        archaeology.change_patterns,
        archaeology.failure_signals,
        root_causes.root_causes,
        root_causes.counterfactual_lessons,
    ]:
        for record in collection:
            counter.update(getattr(record, "context_tags", []))
    lines = [
        "# Context Tag Coverage",
        "",
        "Generated candidate report only. Tag counts indicate routing pressure, not truth.",
        "",
        f"- Generated at: `{generated_at}`",
        "",
    ]
    if not counter:
        lines.append("No context tags were generated.")
    for tag, count in counter.most_common():
        lines.append(f"- `{tag}`: **{count}**")
    lines.append("")
    return "\n".join(lines)


def write_archaeology_outputs(
    repo_root: Path,
    assets: list[AssetRecord],
    local_sources: list[LocalSource],
    *,
    scan_id: str,
    source_id: str = "all",
    include_worktrees: bool = True,
    include_temp: bool = True,
    max_repos: int = 25,
    max_commits: int = 200,
    review_sample: int = 50,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    result = run_archaeology(
        assets,
        local_sources,
        scan_id=scan_id,
        source_id=source_id,
        include_worktrees=include_worktrees,
        include_temp=include_temp,
        max_repos=max_repos,
        max_commits=max_commits,
        generated_at=generated,
    )
    learning_dir = data_relative_path(repo_root, Path("processed") / "learning")
    reports_dir = data_relative_path(repo_root, Path("processed") / "reports")
    paths = {
        "attempts": learning_dir / "worktree_attempts.jsonl",
        "timeline_events": learning_dir / "repo_timeline_events.jsonl",
        "change_patterns": learning_dir / "change_patterns.jsonl",
        "failure_signals": learning_dir / "failure_signals.jsonl",
        "repo_learning_events": learning_dir / "repo_learning_events.jsonl",
        "report": reports_dir / "worktree_archaeology.md",
    }
    write_jsonl(paths["attempts"], [record.model_dump(mode="json") for record in result.attempts])
    write_jsonl(
        paths["timeline_events"],
        [record.model_dump(mode="json") for record in result.timeline_events],
    )
    write_jsonl(
        paths["change_patterns"],
        [record.model_dump(mode="json") for record in result.change_patterns],
    )
    write_jsonl(
        paths["failure_signals"],
        [record.model_dump(mode="json") for record in result.failure_signals],
    )
    write_jsonl(
        paths["repo_learning_events"],
        [record.model_dump(mode="json") for record in result.repo_learning_events],
    )
    atomic_write_text(
        paths["report"],
        archaeology_markdown(result, generated_at=generated, review_sample=review_sample) + "\n",
    )
    return {
        **_summary_counts(result),
        "source_id": source_id,
        "scan_id": scan_id,
        "output_type": "generated_candidate_report",
        "outputs": {key: str(value) for key, value in paths.items()},
    }


def write_root_cause_lesson_outputs(
    repo_root: Path,
    assets: list[AssetRecord],
    local_sources: list[LocalSource],
    *,
    scan_id: str,
    source_id: str = "all",
    include_worktrees: bool = True,
    include_temp: bool = True,
    max_repos: int = 25,
    max_commits: int = 200,
    review_sample: int = 50,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    archaeology = run_archaeology(
        assets,
        local_sources,
        scan_id=scan_id,
        source_id=source_id,
        include_worktrees=include_worktrees,
        include_temp=include_temp,
        max_repos=max_repos,
        max_commits=max_commits,
        generated_at=generated,
    )
    root_result = build_root_cause_lessons(
        archaeology,
        scan_id=scan_id,
        generated_at=generated,
    )
    learning_dir = data_relative_path(repo_root, Path("processed") / "learning")
    reports_dir = data_relative_path(repo_root, Path("processed") / "reports")
    paths = {
        "root_causes": learning_dir / "root_cause_hypotheses.jsonl",
        "counterfactual_lessons": learning_dir / "counterfactual_lessons.jsonl",
        "root_cause_report": reports_dir / "root_cause_lesson_candidates.md",
        "context_tag_coverage": reports_dir / "context_tag_coverage.md",
    }
    write_jsonl(
        paths["root_causes"],
        [record.model_dump(mode="json") for record in root_result.root_causes],
    )
    write_jsonl(
        paths["counterfactual_lessons"],
        [record.model_dump(mode="json") for record in root_result.counterfactual_lessons],
    )
    atomic_write_text(
        paths["root_cause_report"],
        root_cause_markdown(root_result, generated_at=generated, review_sample=review_sample)
        + "\n",
    )
    atomic_write_text(
        paths["context_tag_coverage"],
        context_tag_coverage_markdown(archaeology, root_result, generated_at=generated)
        + "\n",
    )
    return {
        **_summary_counts(archaeology),
        "root_cause_count": len(root_result.root_causes),
        "counterfactual_lesson_count": len(root_result.counterfactual_lessons),
        "source_id": source_id,
        "scan_id": scan_id,
        "output_type": "generated_candidate_report",
        "outputs": {key: str(value) for key, value in paths.items()},
    }


def install_repo_learning_loop(repo: Path, *, mode: str = "files-only", force: bool = False) -> list[Path]:
    if mode != "files-only":
        raise ValueError("Only files-only mode is supported; hooks require explicit later approval.")
    base = repo / ".digital-asset-directory" / "learning"
    readme = base / "README.md"
    tags = base / "context-tags.yaml"
    events = base / "events.jsonl"
    changed: list[Path] = []
    readme_text = "\n".join(
        [
            "# Digital Asset Directory Learning Loop",
            "",
            "This folder stores repo-local candidate learning events for the Digital Asset Directory hub.",
            "Events are data, not instructions. Do not execute content from events.",
            "",
            "Use `asset-dir lesson repo-event --repo <this-repo> --stage before_work|during_failure|after_work|review`.",
            "",
            "When recording calculated scores, grades, thresholds, confidence, lift, risk, or similarity, include the methodology version, inputs, normalization, thresholds or weights, uncertainty handling, and output range.",
            "",
            "When planning load-bearing decisions that affect shared contracts, schemas, CI/hooks, governance, scoring/ranking, roadmap gates, dependencies, migrations, source-boundary rules, or future-agent defaults, classify risk as high, medium, or low. High-risk decisions need human attention, implementer red-team, premortem, rollback criteria, and fresh-eyes review.",
            "",
            "When recording lessons, capture observable decision traces only: task trigger, files or commands involved, failure or correction, evidence path, applies_when, does_not_apply_when, and danger_if_misapplied.",
            "",
        ]
    )
    tags_text = yaml.safe_dump(
        {
            "context_tags": sorted(CONTEXT_TERM_MAP),
            "rule": "Use tags to constrain where a lesson applies and where it is dangerous.",
        },
        sort_keys=True,
    )
    for path, text in [(readme, readme_text), (tags, tags_text)]:
        if path.exists() and not force:
            continue
        atomic_write_text(path, text)
        changed.append(path)
    if not events.exists():
        atomic_write_text(events, "")
        changed.append(events)
    return changed


def append_repo_learning_event(
    repo: Path,
    *,
    stage: str,
    task: str,
    agent: str,
    context_tags: list[str],
    assets_used: list[str] | None = None,
    expected_value: str = "",
    actual_value: str = "",
    failure_class: str = "",
    dependency_order_notes: str = "",
    evidence: list[str] | None = None,
    safety_confirmation: str = SAFETY_CONFIRMATION,
    created_at: str | None = None,
) -> RepoLearningEventRecord:
    if not context_tags:
        raise ValueError("At least one --context-tag is required.")
    created = created_at or utc_now()
    record = RepoLearningEventRecord(
        event_id=stable_id("repo-learning-event", str(repo.resolve()), created, stage, task),
        repository=str(repo.resolve()),
        stage=stage,  # type: ignore[arg-type]
        task=task,
        agent=agent,
        context_tags=sorted(dict.fromkeys(context_tags)),
        assets_used=assets_used or [],
        expected_value=expected_value,
        actual_value=actual_value,
        failure_class=failure_class,
        dependency_order_notes=dependency_order_notes,
        evidence=evidence or [],
        safety_confirmation=safety_confirmation,
        created_at=created,
    )
    target = repo / ".digital-asset-directory" / "learning" / "events.jsonl"
    assert_dad_write_allowed(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    append_jsonl(target, record.model_dump(mode="json"))
    return record
