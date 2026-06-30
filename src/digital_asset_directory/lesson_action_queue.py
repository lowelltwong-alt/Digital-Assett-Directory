from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .ids import stable_id
from .models import LessonAutomationDecisionRecord
from .utils import atomic_write_text, json_dumps, utc_now, write_jsonl

METHODOLOGY_VERSION = "lesson-automation-next-action-queue-v0.1"
AUTHORITY_BOUNDARY = (
    "Generated lesson-automation next-action queue only. This command reads existing "
    "processed scope reports and the scan-cycle log; it does not rescan source repos, "
    "read source file contents, call GitHub, call models, mutate downstream repos, "
    "install hooks, or promote generated candidates to truth."
)
PRIORITY_FORMULA = (
    "priority_score = 100 * (0.30*scope_readiness + 0.25*lesson_yield + "
    "0.20*safety_margin + 0.15*approval_specificity + 0.10*cycle_urgency)"
)
DECISION_TEMPLATE_PATH = Path("processed/learning/lesson_automation_action_decisions.jsonl")

SCOPE_FILES = {
    "priority_content_extracts": "priority_content_extract_scope.json",
    "repo_learning_events": "repo_learning_loop_install_scope.json",
    "governance_map_adoption": "governance_map_adoption_scope.json",
    "ci_and_release_artifacts": "ci_release_artifact_scope.json",
}

SCOPE_HYGIENE_RULES = (
    {
        "rule_id": "inspection_or_extract_path",
        "label": "inspection/extract path",
        "markers": (
            "_zip_inspect",
            "zip_inspect",
            "/_inspect/",
            "/inspect/",
            "/extracted/",
            "_extract",
            "extract_",
        ),
        "recommended_action": "Exclude extracted or inspection copies unless the approval is specifically about those variants.",
    },
    {
        "rule_id": "backup_or_snapshot_variant",
        "label": "backup/snapshot variant",
        "markers": (
            "backup",
            ".bak",
            "main-clean-",
            "/snapshot/",
            "_snapshot",
            "snapshot_",
        ),
        "recommended_action": "Prefer the canonical source path and keep backups as lineage evidence.",
    },
    {
        "rule_id": "private_or_sensitive_name",
        "label": "private/sensitive name",
        "markers": (
            "/private/",
            "_private_",
            "-private-",
            "private_repo",
            "runtime-private",
            "talent_intelligence_private",
        ),
        "recommended_action": "Require explicit human confirmation before approving private-looking paths.",
    },
    {
        "rule_id": "generated_dependency_or_cache_path",
        "label": "generated/dependency/cache path",
        "markers": (
            "/node_modules/",
            "/.venv/",
            "/venv/",
            "/__pycache__/",
            "/.pytest_cache/",
            "/dist/",
            "/build/",
        ),
        "recommended_action": "Do not use dependency, cache, or build-output paths as primary lesson sources.",
    },
    {
        "rule_id": "fixture_or_seed_pack_path",
        "label": "fixture/seed pack path",
        "markers": (
            "/seed_pack/",
            "_seed_pack",
            "/fixtures/",
            "/fixture/",
            ".pytest-tmp-root",
            "pytest-of-",
        ),
        "recommended_action": "Treat fixtures and seed packs as test evidence unless the approval is specifically about scaffolds.",
    },
)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _bounded(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)


def _scope_summary_count(scope: dict[str, Any] | None) -> int:
    if not scope:
        return 0
    summary = scope.get("summary", {})
    for key in (
        "candidate_count",
        "reported_repo_count",
        "candidate_repo_count_before_limit",
        "total_candidate_count_before_limit",
    ):
        value = summary.get(key)
        if isinstance(value, int | float):
            return int(value)
    return 0


def _scope_hygiene_flags(candidate: dict[str, Any]) -> list[dict[str, str]]:
    path_text = " ".join(
        str(candidate.get(key, ""))
        for key in ("logical_path", "relative_path", "asset_id")
        if candidate.get(key)
    )
    normalized = "/" + path_text.replace("\\", "/").lower().strip("/")
    flags: list[dict[str, str]] = []
    for rule in SCOPE_HYGIENE_RULES:
        if any(marker in normalized for marker in rule["markers"]):
            flags.append(
                {
                    "rule_id": str(rule["rule_id"]),
                    "label": str(rule["label"]),
                    "recommended_action": str(rule["recommended_action"]),
                }
            )
    return flags


def _scope_ready(status: str, scope: dict[str, Any] | None) -> float:
    if status in {
        "scoped_not_extracted",
        "installation_scope_ready",
        "adoption_scope_ready",
        "lesson_candidates_synthesized",
        "promotion_candidates_packaged",
    }:
        return 1.0
    if scope:
        return 0.75
    if status.startswith("covered"):
        return 0.0
    if status.startswith("deferred"):
        return 0.25
    return 0.35


def _lesson_yield(signal_family_id: str, scope: dict[str, Any] | None) -> float:
    count = _scope_summary_count(scope)
    if signal_family_id in {"priority_content_extracts", "ci_and_release_artifacts"}:
        return _bounded(count / 100)
    if signal_family_id in {"repo_learning_events", "governance_map_adoption"}:
        return _bounded(count / 30)
    if signal_family_id == "github_pr_issue_metadata":
        return 0.45
    if signal_family_id == "bounded_git_history":
        return 0.55
    if signal_family_id == "private_source_public_safe_workflows":
        return 0.5
    return 0.2 if count else 0.0


def _safety_margin(signal_family_id: str, scope: dict[str, Any] | None) -> float:
    if signal_family_id == "priority_content_extracts":
        return 0.78
    if signal_family_id == "repo_learning_events":
        return 0.55
    if signal_family_id == "governance_map_adoption":
        return 0.52
    if signal_family_id == "ci_and_release_artifacts":
        return 0.48
    if signal_family_id == "github_pr_issue_metadata":
        return 0.3
    if scope:
        return 0.6
    return 0.4


def _approval_specificity(signal_family_id: str, scope: dict[str, Any] | None) -> float:
    if scope:
        return 1.0
    if signal_family_id == "github_pr_issue_metadata":
        return 0.25
    return 0.4


def _cycle_urgency(order: int, max_order: int) -> float:
    if max_order <= 0:
        return 0.0
    return _bounded((max_order - order + 1) / max_order)


def _priority_score(components: dict[str, float]) -> float:
    return round(
        100
        * (
            0.30 * components["scope_readiness"]
            + 0.25 * components["lesson_yield"]
            + 0.20 * components["safety_margin"]
            + 0.15 * components["approval_specificity"]
            + 0.10 * components["cycle_urgency"]
        ),
        2,
    )


def _scope_path(repo_root: Path, signal_family_id: str) -> Path | None:
    filename = SCOPE_FILES.get(signal_family_id)
    if not filename:
        return None
    return repo_root / "processed" / "reports" / filename


def _top_examples(signal_family_id: str, scope: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not scope:
        return []
    examples: list[dict[str, Any]] = []
    if "repo_scopes" in scope:
        for repo_scope in scope.get("repo_scopes", [])[:5]:
            examples.append(
                {
                    "repo_key": repo_scope.get("repo_key", ""),
                    "candidate_count": repo_scope.get("candidate_count", 0),
                    "categories": sorted(
                        {
                            candidate.get("primary_category_id", "")
                            for candidate in repo_scope.get("candidates", [])[:10]
                            if candidate.get("primary_category_id")
                        }
                    ),
                }
            )
    elif "repo_candidates" in scope:
        for candidate in scope.get("repo_candidates", [])[:5]:
            examples.append(
                {
                    "repo_key": candidate.get("repo_key", ""),
                    "priority_score": candidate.get("priority_score"),
                    "status": candidate.get("install_status")
                    or candidate.get("adoption_status")
                    or candidate.get("review_status", ""),
                    "family_key": candidate.get("family_key", ""),
                }
            )
    return examples


def _recommended_command(signal_family_id: str, scope_path: Path | None) -> str:
    if signal_family_id == "priority_content_extracts":
        return (
            "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend "
            "priority-content-extract --approval-id <human-approval-id> "
            "--repo-key <approved-repo-key> --category <approved-category> "
            "--scope-file processed/reports/priority_content_extract_scope.json "
            "--max-bytes-per-file 20000 --limit 50"
        )
    if signal_family_id == "repo_learning_events":
        return (
            "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli agent "
            "install-learning-loop --repo <approved-repo-path> --mode files-only"
        )
    if signal_family_id == "governance_map_adoption":
        return (
            "Create a normal source-repo change from templates/cross-repo-governance-dependency-map/ "
            "only after Lowell selects the repo family, upstream authority, child mirrors, validators, and tests."
        )
    if signal_family_id == "ci_and_release_artifacts":
        return (
            "Do not read CI/release artifacts yet. First approve or implement a bounded, redacted "
            "artifact extractor that consumes processed/reports/ci_release_artifact_scope.json."
        )
    if signal_family_id == "github_pr_issue_metadata":
        return "Keep deferred until Lowell approves read-only token scope, privacy boundary, and API rate limits."
    if scope_path:
        return f"Review `{scope_path.as_posix()}` and choose the bounded next command explicitly."
    return "No generated next command is available yet."


def _action_kind(signal_family_id: str) -> str:
    return {
        "priority_content_extracts": "bounded_content_extract",
        "repo_learning_events": "source_repo_files_only_install",
        "governance_map_adoption": "source_repo_governance_adoption",
        "ci_and_release_artifacts": "extractor_gap_or_bounded_content_extract",
        "github_pr_issue_metadata": "external_api_gate",
        "bounded_git_history": "bounded_git_history_review",
        "private_source_public_safe_workflows": "public_safe_metadata_review",
    }.get(signal_family_id, "coverage_followup")


def build_lesson_automation_next_action_queue(
    repo_root: Path,
    *,
    generated_at: str | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    cycle_path = repo_root / "processed" / "reports" / "scan_coverage_cycle.json"
    cycle = _load_json(cycle_path) or {}
    entries = list(cycle.get("cycle_entries") or cycle.get("recommended_cycle") or [])
    max_order = max((int(entry.get("cycle_order") or entry.get("order") or 0) for entry in entries), default=0)
    actions: list[dict[str, Any]] = []
    for entry in entries:
        family_id = str(entry.get("signal_family_id") or "")
        if not family_id:
            continue
        status = str(entry.get("current_status") or "")
        requires_human_approval = bool(entry.get("requires_human_approval"))
        scope_path = _scope_path(repo_root, family_id)
        scope = _load_json(scope_path) if scope_path else None
        if status.startswith("covered") and not requires_human_approval:
            continue
        components = {
            "scope_readiness": _scope_ready(status, scope),
            "lesson_yield": _lesson_yield(family_id, scope),
            "safety_margin": _safety_margin(family_id, scope),
            "approval_specificity": _approval_specificity(family_id, scope),
            "cycle_urgency": _cycle_urgency(
                int(entry.get("cycle_order") or entry.get("order") or 0), max_order
            ),
        }
        human_gate_reason = "human approval required" if requires_human_approval else "no human gate"
        if family_id in {"repo_learning_events", "governance_map_adoption"}:
            human_gate_reason = "source-repo mutation requires explicit repo selection"
        elif family_id in {"priority_content_extracts", "ci_and_release_artifacts"}:
            human_gate_reason = "content reading requires bounded approval, caps, and redaction"
        elif family_id == "github_pr_issue_metadata":
            human_gate_reason = "external API and token scope require explicit approval"
        action = {
            "action_id": stable_id("lesson-automation-action", family_id, status),
            "signal_family_id": family_id,
            "label": entry.get("label", family_id),
            "action_kind": _action_kind(family_id),
            "current_status": status,
            "cycle_order": int(entry.get("cycle_order") or entry.get("order") or 0),
            "requires_human_approval": requires_human_approval,
            "human_gate_reason": human_gate_reason,
            "scope_file": str(scope_path) if scope_path and scope_path.exists() else "",
            "scope_present": bool(scope),
            "scope_summary": scope.get("summary", {}) if scope else {},
            "top_examples": _top_examples(family_id, scope),
            "recommended_next_action": entry.get("next_action", ""),
            "recommended_command_or_next_step": _recommended_command(family_id, scope_path),
            "priority_score": _priority_score(components),
            "priority_components": components,
            "priority_formula": PRIORITY_FORMULA,
            "methodology_version": METHODOLOGY_VERSION,
            "review_status": "generated_candidate",
            "authority_boundary": AUTHORITY_BOUNDARY,
            "applies_when": [
                "A future agent or Lowell is choosing the next lesson-automation action from existing generated scopes.",
                "The goal is to avoid repeating broad scans while moving gated work toward explicit approval.",
            ],
            "does_not_apply_when": [
                "The user has already approved a specific repo, category, source mutation, or content read.",
                "The task is to inspect a named repo directly rather than choose among cycle gates.",
            ],
            "danger_if_misapplied": (
                "A high queue priority can be mistaken for permission to read content, call APIs, "
                "or mutate source repos. It is only a review-routing score."
            ),
        }
        actions.append(action)
    actions = sorted(
        actions,
        key=lambda item: (-float(item["priority_score"]), item["cycle_order"], item["signal_family_id"]),
    )[:limit]
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "generated_at": generated,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "priority_formula": PRIORITY_FORMULA,
        "summary": {
            "action_count": len(actions),
            "cycle_entry_count": len(entries),
            "scope_files_present": sorted(
                family_id
                for family_id in SCOPE_FILES
                if (repo_root / "processed" / "reports" / SCOPE_FILES[family_id]).exists()
            ),
            "source_repos_mutated": 0,
            "content_files_read": 0,
            "filesystem_recursions": 0,
            "github_calls": 0,
            "model_calls": 0,
        },
        "checked_inputs": [
            "processed/reports/scan_coverage_cycle.json",
            "processed/reports/priority_content_extract_scope.json",
            "processed/reports/repo_learning_loop_install_scope.json",
            "processed/reports/governance_map_adoption_scope.json",
            "processed/reports/ci_release_artifact_scope.json",
        ],
        "intentionally_not_done": [
            "source repo mutation",
            "source file content reads",
            "fresh filesystem recursion",
            "GitHub, CI, or package registry calls",
            "model or embedding calls",
            "roadmap phase completion",
        ],
        "medium_risk_review": {
            "risk_tier": "medium",
            "why_not_high": (
                "The queue influences future-agent routing but remains generated-only, reversible, "
                "and does not change schemas, scoring defaults, source repos, hooks, or roadmap gates."
            ),
            "self_red_team": [
                "Priority scores can be over-trusted as approval.",
                "Existing scope reports can be stale after a new scan.",
                "Source-mutation actions can look as easy as generated-output actions unless gates are explicit.",
                "CI/release artifacts may contain sensitive data and need a stricter extractor than ordinary docs.",
            ],
            "premortem": (
                "The likely failure mode is a future agent running the recommended command without "
                "a concrete human approval id, repo key, category, source boundary, and byte cap."
            ),
            "rollback": "Delete generated processed/reports/lesson_automation_next_actions.* outputs; no source repos are touched.",
        },
        "actions": actions,
        "review_status": "generated_candidate",
    }


def lesson_automation_next_actions_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Lesson Automation Next Actions",
        "",
        AUTHORITY_BOUNDARY,
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Methodology: `{result['methodology_version']}`",
        f"- Action count: **{summary['action_count']}**",
        f"- Source repos mutated: **{summary['source_repos_mutated']}**",
        f"- Content files read: **{summary['content_files_read']}**",
        f"- GitHub/model calls: **{summary['github_calls']}** / **{summary['model_calls']}**",
        "",
        "## Priority Formula",
        "",
        f"`{result['priority_formula']}`",
        "",
        "Scores route review only. They do not authorize source mutation, content reads, API calls, or promotion.",
        "",
        "## Action Queue",
        "",
        "| Priority | Family | Status | Gate | Scope | Next step |",
        "|---:|---|---|---|---|---|",
    ]
    for action in result["actions"]:
        scope = "yes" if action["scope_present"] else "no"
        lines.append(
            "| {score:.2f} | `{family}` | `{status}` | {gate} | {scope} | {step} |".format(
                score=float(action["priority_score"]),
                family=action["signal_family_id"],
                status=action["current_status"],
                gate=str(action["human_gate_reason"]).replace("|", "/"),
                scope=scope,
                step=str(action["recommended_next_action"]).replace("|", "/"),
            )
        )
    lines.extend(["", "## Recommended Commands Or Next Steps", ""])
    for action in result["actions"]:
        lines.extend(
            [
                f"### {action['signal_family_id']}",
                "",
                f"- Priority: **{action['priority_score']}**",
                f"- Action kind: `{action['action_kind']}`",
                f"- Human gate: {action['human_gate_reason']}",
                f"- Scope file: `{action['scope_file'] or 'missing'}`",
                "",
                "```text",
                str(action["recommended_command_or_next_step"]),
                "```",
                "",
            ]
        )
        if action["top_examples"]:
            lines.append("Top examples from scope:")
            for example in action["top_examples"][:5]:
                lines.append(f"- `{example.get('repo_key', '')}`: {example}")
            lines.append("")
    lines.extend(
        [
            "## Medium-Risk Review",
            "",
            f"- Risk tier: `{result['medium_risk_review']['risk_tier']}`",
            f"- Why not high: {result['medium_risk_review']['why_not_high']}",
            f"- Premortem: {result['medium_risk_review']['premortem']}",
            f"- Rollback: {result['medium_risk_review']['rollback']}",
            "",
            "Self red-team:",
            "",
        ]
    )
    for item in result["medium_risk_review"]["self_red_team"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Intentionally Not Done", ""])
    for item in result["intentionally_not_done"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def lesson_automation_next_actions_prompt_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Fresh-Eyes Prompt: Lesson Automation Next Actions",
        "",
        "Review this generated queue and choose at most one next action to approve.",
        "",
        "Constraints:",
        "",
        "- Do not mutate source repos unless the selected action explicitly requires it and Lowell approves that repo.",
        "- Do not read source file contents without approval id, repo key, category, byte cap, and redaction boundary.",
        "- Do not call GitHub or other APIs without a separate token/privacy gate.",
        "- Treat priority scores as routing, not proof of value or permission.",
        "",
        "Questions:",
        "",
        "1. Which action should happen next, if any?",
        "2. What exact repo key, category, source path, or repo family is approved?",
        "3. What byte caps, stop conditions, and redaction checks are required?",
        "4. Which action should remain deferred because the source is active, sensitive, or too noisy?",
        "5. What evidence would show the action improved lesson automation?",
        "",
        "Top queued actions:",
        "",
    ]
    for action in result["actions"][:10]:
        lines.append(
            f"- `{action['signal_family_id']}`: priority {action['priority_score']}, "
            f"status `{action['current_status']}`, gate `{action['human_gate_reason']}`"
        )
    lines.append("")
    return "\n".join(lines)


def write_lesson_automation_next_action_outputs(
    repo_root: Path,
    *,
    limit: int = 25,
    generated_at: str | None = None,
) -> dict[str, Any]:
    result = build_lesson_automation_next_action_queue(
        repo_root,
        generated_at=generated_at,
        limit=limit,
    )
    reports_dir = repo_root / "processed" / "reports"
    paths = {
        "queue_markdown": reports_dir / "lesson_automation_next_actions.md",
        "queue_json": reports_dir / "lesson_automation_next_actions.json",
        "approval_prompt": reports_dir / "lesson_automation_next_actions_approval_prompt.md",
    }
    atomic_write_text(paths["queue_markdown"], lesson_automation_next_actions_markdown(result))
    atomic_write_text(paths["queue_json"], json_dumps(result, pretty=True) + "\n")
    atomic_write_text(paths["approval_prompt"], lesson_automation_next_actions_prompt_markdown(result))
    return {
        "output_type": "generated_candidate_queue",
        "review_status": "generated_candidate",
        "summary": result["summary"],
        "outputs": {key: str(path) for key, path in paths.items()},
    }


def load_lesson_automation_decisions(path: Path) -> list[LessonAutomationDecisionRecord]:
    if not path.exists():
        return []
    records: list[LessonAutomationDecisionRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(LessonAutomationDecisionRecord.model_validate_json(line))
    return records


def write_lesson_automation_decisions(
    path: Path,
    records: list[LessonAutomationDecisionRecord],
) -> None:
    write_jsonl(path, [record.model_dump(mode="json") for record in records])


def _decision_is_pending(record: LessonAutomationDecisionRecord) -> bool:
    return (
        record.decision == "pending"
        and not record.reviewer
        and not record.reviewed_at
        and not record.approval_id
        and not record.rationale
        and not record.notes
    )


def build_lesson_automation_decision_template(
    actions: list[dict[str, Any]],
    *,
    limit: int = 25,
) -> list[LessonAutomationDecisionRecord]:
    records: list[LessonAutomationDecisionRecord] = []
    for index, action in enumerate(actions[:limit], start=1):
        sample_id = f"lesson-automation-decision-{index:03d}"
        records.append(
            LessonAutomationDecisionRecord(
                decision_id=stable_id(
                    "lesson-automation-decision",
                    sample_id,
                    str(action["action_id"]),
                ),
                sample_id=sample_id,
                action_id=str(action["action_id"]),
                signal_family_id=str(action["signal_family_id"]),
                action_kind=str(action["action_kind"]),
                approved_scope_file=str(action.get("scope_file") or ""),
                evidence={
                    "methodology_version": METHODOLOGY_VERSION,
                    "priority_score": action.get("priority_score"),
                    "priority_components": action.get("priority_components", {}),
                    "priority_formula": action.get("priority_formula", PRIORITY_FORMULA),
                    "current_status": action.get("current_status"),
                    "human_gate_reason": action.get("human_gate_reason"),
                    "recommended_command_or_next_step": action.get("recommended_command_or_next_step"),
                    "top_examples": action.get("top_examples", []),
                    "generated_candidate_only": True,
                },
                stop_conditions=[
                    "Stop before source repo mutation unless allow_source_mutation is true and a repo selector is present.",
                    "Stop before content reads unless allow_content_read is true with byte/file caps and redaction required.",
                    "Stop before GitHub/API calls unless allow_external_api is true with token and privacy notes.",
                    "Stop before model calls unless allow_model_call is true and provider/privacy gates are approved.",
                ],
                validation_commands=[
                    "python -m pytest",
                    "PYTHONPATH=src python -m digital_asset_directory.cli validate",
                    "PYTHONPATH=src python -m digital_asset_directory.cli roadmap check --no-update",
                ],
            )
        )
    return records


def _dedupe(values: list[str]) -> list[str]:
    return sorted({value.strip() for value in values if value.strip()})


def _validate_decision(record: LessonAutomationDecisionRecord) -> None:
    if record.decision == "pending":
        return
    if not record.reviewer.strip():
        raise ValueError("--reviewer is required for a non-pending decision.")
    if record.decision in {"defer", "reject"} and not (record.rationale or record.notes):
        raise ValueError("--rationale or --notes is required when deferring or rejecting.")
    if record.decision != "approve":
        return
    if not record.approval_id.strip():
        raise ValueError("--approval-id is required for approval.")
    has_target = bool(record.approved_repo_keys or record.approved_categories or record.approved_repo_paths)
    if not has_target:
        raise ValueError("Approval requires at least one repo key, category, or repo path.")
    if record.action_kind in {"bounded_content_extract", "extractor_gap_or_bounded_content_extract"}:
        if not record.allow_content_read:
            raise ValueError("Content-read actions require --allow-content-read.")
        if record.allow_source_mutation:
            raise ValueError("Content-read approvals must not allow source mutation.")
        if record.max_bytes_per_file <= 0 or record.max_files <= 0:
            raise ValueError("Content-read approvals require positive byte and file caps.")
        if not record.redaction_required:
            raise ValueError("Content-read approvals require redaction.")
    if record.action_kind in {"source_repo_files_only_install", "source_repo_governance_adoption"}:
        if not record.allow_source_mutation:
            raise ValueError("Source-repo actions require --allow-source-mutation.")
        if record.allow_content_read:
            raise ValueError("Source-repo mutation approvals must not include content-read permission.")
    if record.action_kind == "external_api_gate":
        if not record.allow_external_api:
            raise ValueError("External API approvals require --allow-external-api.")
        if not record.token_scope_note or not record.privacy_boundary_note:
            raise ValueError("External API approvals require token-scope and privacy-boundary notes.")
    if record.allow_model_call and not record.privacy_boundary_note:
        raise ValueError("Model-call approvals require a privacy-boundary note.")


def update_lesson_automation_decision_record(
    records: list[LessonAutomationDecisionRecord],
    *,
    sample_id: str,
    reviewer: str,
    decision: str,
    reviewed_at: str,
    approval_id: str = "",
    approved_repo_keys: list[str] | None = None,
    approved_categories: list[str] | None = None,
    approved_repo_paths: list[str] | None = None,
    approved_include_paths: list[str] | None = None,
    approved_exclude_paths: list[str] | None = None,
    max_bytes_per_file: int = 0,
    max_files: int = 0,
    allow_content_read: bool = False,
    allow_source_mutation: bool = False,
    allow_external_api: bool = False,
    allow_model_call: bool = False,
    redaction_required: bool = True,
    token_scope_note: str = "",
    privacy_boundary_note: str = "",
    rationale: str = "",
    notes: str = "",
    stop_conditions: list[str] | None = None,
    validation_commands: list[str] | None = None,
) -> tuple[list[LessonAutomationDecisionRecord], LessonAutomationDecisionRecord]:
    allowed_decisions = {"approve", "defer", "reject", "pending"}
    if decision not in allowed_decisions:
        raise ValueError(f"decision must be one of {sorted(allowed_decisions)}.")
    updated_records: list[LessonAutomationDecisionRecord] = []
    updated: LessonAutomationDecisionRecord | None = None
    for record in records:
        if record.sample_id != sample_id:
            updated_records.append(record)
            continue
        data = record.model_dump(mode="json")
        data.update(
            {
                "reviewer": reviewer,
                "reviewed_at": reviewed_at if decision != "pending" else None,
                "decision": decision,
                "approval_id": approval_id,
                "approved_repo_keys": _dedupe(approved_repo_keys or []),
                "approved_categories": _dedupe(approved_categories or []),
                "approved_repo_paths": _dedupe(approved_repo_paths or []),
                "approved_include_paths": _dedupe(approved_include_paths or []),
                "approved_exclude_paths": _dedupe(approved_exclude_paths or []),
                "max_bytes_per_file": max_bytes_per_file,
                "max_files": max_files,
                "allow_content_read": allow_content_read,
                "allow_source_mutation": allow_source_mutation,
                "allow_external_api": allow_external_api,
                "allow_model_call": allow_model_call,
                "redaction_required": redaction_required,
                "token_scope_note": token_scope_note,
                "privacy_boundary_note": privacy_boundary_note,
                "rationale": rationale,
                "notes": notes,
                "review_status": "generated_candidate"
                if decision == "pending"
                else ("rejected" if decision == "reject" else "reviewed"),
            }
        )
        if stop_conditions:
            data["stop_conditions"] = _dedupe(stop_conditions)
        if validation_commands:
            data["validation_commands"] = list(validation_commands)
        updated = LessonAutomationDecisionRecord.model_validate(data)
        _validate_decision(updated)
        updated_records.append(updated)
    if updated is None:
        raise ValueError(f"No lesson automation decision sample found for {sample_id}.")
    return updated_records, updated


def summarize_lesson_automation_decisions(
    records: list[LessonAutomationDecisionRecord],
) -> dict[str, Any]:
    pending = [record for record in records if _decision_is_pending(record)]
    return {
        "template_count": len(records),
        "pending_count": len(pending),
        "reviewed_count": len(records) - len(pending),
        "approved_count": sum(1 for record in records if record.decision == "approve"),
        "deferred_count": sum(1 for record in records if record.decision == "defer"),
        "rejected_count": sum(1 for record in records if record.decision == "reject"),
        "content_read_approval_count": sum(1 for record in records if record.allow_content_read),
        "source_mutation_approval_count": sum(
            1 for record in records if record.allow_source_mutation
        ),
        "external_api_approval_count": sum(1 for record in records if record.allow_external_api),
    }


def lesson_automation_decision_markdown(records: list[LessonAutomationDecisionRecord]) -> str:
    summary = summarize_lesson_automation_decisions(records)
    lines = [
        "# Lesson Automation Decision Template",
        "",
        "Generated human-decision template. Pending rows are not approvals.",
        "",
        f"- Template rows: **{summary['template_count']}**",
        f"- Reviewed rows: **{summary['reviewed_count']}**",
        f"- Approved rows: **{summary['approved_count']}**",
        f"- Deferred rows: **{summary['deferred_count']}**",
        f"- Rejected rows: **{summary['rejected_count']}**",
        "",
        "| Sample | Family | Kind | Decision | Reviewer | Gate fields |",
        "|---|---|---|---|---|---|",
    ]
    for record in records:
        gate_fields = []
        if record.allow_content_read:
            gate_fields.append(f"content cap {record.max_files} files/{record.max_bytes_per_file} bytes")
        if record.allow_source_mutation:
            gate_fields.append("source mutation allowed")
        if record.allow_external_api:
            gate_fields.append("external API allowed")
        lines.append(
            "| `{sample}` | `{family}` | `{kind}` | `{decision}` | `{reviewer}` | {gate_fields} |".format(
                sample=record.sample_id,
                family=record.signal_family_id,
                kind=record.action_kind,
                decision=record.decision,
                reviewer=record.reviewer,
                gate_fields=", ".join(gate_fields) or "none",
            )
        )
    lines.extend(
        [
            "",
            "## Red-Team",
            "",
            "- This template records decisions; it does not execute the approved action.",
            "- An approval without exact repo/category/path selectors is invalid.",
            "- Content-read approvals require byte/file caps and redaction.",
            "- Source-repo write approvals require an explicit mutation flag and repo selector.",
            "- External API approvals require token-scope and privacy-boundary notes.",
            "",
        ]
    )
    return "\n".join(lines)


def _path_for_command(repo_root: Path, path_text: str) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except (OSError, ValueError):
        return path_text.replace("\\", "/")


def _repeat_option(option: str, values: list[str]) -> str:
    return " ".join(f'{option} "{value}"' for value in values)


def _ps_quote(value: str) -> str:
    return f'"{value.replace(chr(34), "`" + chr(34))}"'


def _approval_id_for(record: LessonAutomationDecisionRecord, generated_at: str) -> str:
    date = generated_at[:10] if len(generated_at) >= 10 else "undated"
    family = record.signal_family_id.replace("_", "-")
    return f"approval:lowell:{family}:{date}"


def _scope_categories(scope: dict[str, Any] | None, record: LessonAutomationDecisionRecord) -> list[str]:
    if scope:
        categories = [
            str(item.get("category_id", "")).strip()
            for item in scope.get("categories", [])
            if str(item.get("category_id", "")).strip()
        ]
        if categories:
            return sorted(set(categories))
    categories = [
        str(category).strip()
        for example in record.evidence.get("top_examples", [])
        for category in example.get("categories", [])
        if str(category).strip()
    ]
    return sorted(set(categories))


def _scope_repo_keys(record: LessonAutomationDecisionRecord, *, limit: int) -> list[str]:
    return [
        str(example.get("repo_key", "")).strip()
        for example in record.evidence.get("top_examples", [])[:limit]
        if str(example.get("repo_key", "")).strip()
    ]


def _label_command(
    record: LessonAutomationDecisionRecord,
    *,
    decision: str,
    rationale: str,
    approval_id: str = "",
    repo_keys: list[str] | None = None,
    categories: list[str] | None = None,
    repo_paths: list[str] | None = None,
    include_paths: list[str] | None = None,
    exclude_paths: list[str] | None = None,
    max_bytes_per_file: int = 0,
    max_files: int = 0,
    allow_content_read: bool = False,
    allow_source_mutation: bool = False,
    allow_external_api: bool = False,
    token_scope_note: str = "",
    privacy_boundary_note: str = "",
) -> str:
    parts = [
        "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend "
        "lesson-automation-decision-label",
        "--sample-id",
        _ps_quote(record.sample_id),
        "--reviewer",
        _ps_quote("Lowell"),
        "--decision",
        decision,
    ]
    if approval_id:
        parts.extend(["--approval-id", _ps_quote(approval_id)])
    for repo_key in repo_keys or []:
        parts.extend(["--repo-key", _ps_quote(repo_key)])
    for category in categories or []:
        parts.extend(["--category", category])
    for repo_path in repo_paths or []:
        parts.extend(["--repo-path", _ps_quote(repo_path)])
    for include_path in include_paths or []:
        parts.extend(["--include-path", _ps_quote(include_path)])
    for exclude_path in exclude_paths or []:
        parts.extend(["--exclude-path", _ps_quote(exclude_path)])
    if max_bytes_per_file:
        parts.extend(["--max-bytes-per-file", str(max_bytes_per_file)])
    if max_files:
        parts.extend(["--max-files", str(max_files)])
    if allow_content_read:
        parts.append("--allow-content-read")
    if allow_source_mutation:
        parts.append("--allow-source-mutation")
    if allow_external_api:
        parts.append("--allow-external-api")
    if token_scope_note:
        parts.extend(["--token-scope-note", _ps_quote(token_scope_note)])
    if privacy_boundary_note:
        parts.extend(["--privacy-boundary-note", _ps_quote(privacy_boundary_note)])
    parts.extend(["--rationale", _ps_quote(rationale)])
    return " ".join(parts)


def _approval_packet_entry(
    repo_root: Path,
    record: LessonAutomationDecisionRecord,
    *,
    generated_at: str,
    repo_limit: int,
    max_bytes_per_file: int,
    max_files: int,
) -> dict[str, Any]:
    scope_path = Path(record.approved_scope_file) if record.approved_scope_file else None
    if scope_path and not scope_path.is_absolute():
        scope_path = repo_root / scope_path
    scope = _load_json(scope_path) if scope_path else None
    base = {
        "sample_id": record.sample_id,
        "decision_id": record.decision_id,
        "signal_family_id": record.signal_family_id,
        "action_kind": record.action_kind,
        "current_decision": record.decision,
        "priority_score": record.evidence.get("priority_score"),
        "priority_formula": record.evidence.get("priority_formula", PRIORITY_FORMULA),
        "methodology_version": record.evidence.get("methodology_version", METHODOLOGY_VERSION),
        "top_examples": record.evidence.get("top_examples", []),
        "scope_file": str(scope_path) if scope_path else "",
        "review_status": "generated_candidate",
        "applies_when": [
            "A human is deciding whether to label this lesson-automation decision row.",
            "The goal is to convert a pending generated candidate into an explicit approve, defer, or reject decision.",
        ],
        "does_not_apply_when": [
            "The row has already been reviewed.",
            "The user is asking to execute an approved action rather than label the approval ledger.",
        ],
        "danger_if_misapplied": (
            "A suggested label command can be mistaken for approval. It is only a prepared command; "
            "Lowell must explicitly authorize or run it before any row is reviewed."
        ),
    }
    if record.decision != "pending":
        return {
            **base,
            "recommended_decision": "already_reviewed",
            "label_command": "",
            "rationale": "This row is no longer pending.",
            "approval_fields": {},
        }
    if record.action_kind == "bounded_content_extract":
        repo_keys = _scope_repo_keys(record, limit=repo_limit)
        categories = _scope_categories(scope, record)
        rationale = (
            "Approve bounded read-only extraction from generated scope rows so DAD can synthesize "
            "context-bound lesson candidates. No source repo mutation, no GitHub/API/model calls, "
            "redaction required."
        )
        return {
            **base,
            "recommended_decision": "approve",
            "rationale": rationale,
            "approval_fields": {
                "approval_id": _approval_id_for(record, generated_at),
                "approved_repo_keys": repo_keys,
                "approved_categories": categories,
                "max_bytes_per_file": max_bytes_per_file,
                "max_files": max_files,
                "allow_content_read": True,
                "allow_source_mutation": False,
                "redaction_required": True,
            },
            "label_command": _label_command(
                record,
                decision="approve",
                approval_id=_approval_id_for(record, generated_at),
                repo_keys=repo_keys,
                categories=categories,
                max_bytes_per_file=max_bytes_per_file,
                max_files=max_files,
                allow_content_read=True,
                rationale=rationale,
            ),
        }
    if record.action_kind in {"source_repo_files_only_install", "source_repo_governance_adoption"}:
        rationale = (
            "Defer source-repo mutation until Lowell selects exact repo paths and confirms write permission."
        )
        return {
            **base,
            "recommended_decision": "defer",
            "rationale": rationale,
            "approval_fields": {"allow_source_mutation": False},
            "label_command": _label_command(record, decision="defer", rationale=rationale),
        }
    if record.action_kind == "extractor_gap_or_bounded_content_extract":
        rationale = "Defer until a specific bounded CI/release artifact extractor and redaction policy exists."
        return {
            **base,
            "recommended_decision": "defer",
            "rationale": rationale,
            "approval_fields": {"allow_content_read": False},
            "label_command": _label_command(record, decision="defer", rationale=rationale),
        }
    if record.action_kind == "external_api_gate":
        rationale = "Defer until read-only token scope, rate limits, and privacy boundary are approved."
        return {
            **base,
            "recommended_decision": "defer",
            "rationale": rationale,
            "approval_fields": {"allow_external_api": False},
            "label_command": _label_command(record, decision="defer", rationale=rationale),
        }
    rationale = "Defer because no deterministic executor or approval scope is available for this row yet."
    return {
        **base,
        "recommended_decision": "defer",
        "rationale": rationale,
        "approval_fields": {},
        "label_command": _label_command(record, decision="defer", rationale=rationale),
    }


def build_lesson_automation_approval_packet(
    repo_root: Path,
    records: list[LessonAutomationDecisionRecord],
    *,
    generated_at: str | None = None,
    repo_limit: int = 5,
    max_bytes_per_file: int = 20000,
    max_files: int = 50,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    pending = [record for record in records if record.decision == "pending"]
    entries = [
        _approval_packet_entry(
            repo_root,
            record,
            generated_at=generated,
            repo_limit=repo_limit,
            max_bytes_per_file=max_bytes_per_file,
            max_files=max_files,
        )
        for record in pending
    ]
    return {
        "methodology_version": "lesson-automation-approval-packet-v0.1",
        "generated_at": generated,
        "authority_boundary": (
            "Generated approval packet only. This packet prepares decision-label commands from "
            "pending generated rows; it does not apply labels, approve actions, execute commands, "
            "read source contents, mutate source repos, call GitHub, call models, or promote candidates."
        ),
        "summary": {
            "decision_count": len(records),
            "pending_count": len(pending),
            "recommended_approve_count": sum(
                1 for entry in entries if entry["recommended_decision"] == "approve"
            ),
            "recommended_defer_count": sum(
                1 for entry in entries if entry["recommended_decision"] == "defer"
            ),
            "label_commands_generated": sum(1 for entry in entries if entry["label_command"]),
            "labels_applied": 0,
            "commands_executed": 0,
            "source_repos_mutated": 0,
            "content_files_read": 0,
            "github_calls": 0,
            "model_calls": 0,
        },
        "checked_inputs": [
            "processed/learning/lesson_automation_action_decisions.jsonl",
            "processed/reports/*_scope.json when referenced by a pending row",
        ],
        "intentionally_not_done": [
            "decision-label command execution",
            "approval application",
            "content extraction",
            "source repo mutation",
            "GitHub/API/model calls",
            "roadmap phase completion",
        ],
        "risk_review": {
            "risk_tier": "low",
            "why_not_high": (
                "This packet is generated output and changes no behavior, schema, registry, score, "
                "source repo, hook, or roadmap gate."
            ),
            "self_red_team": [
                "A suggested command can be mistaken for human approval.",
                "A future agent could run all suggested commands instead of only the one Lowell approves.",
                "Scope files may be stale after a new scan and should be regenerated before use.",
            ],
            "premortem": (
                "The likely failure is copying a generated approve command after the source scope changed. "
                "Regenerate the packet and inspect repo keys, categories, caps, and rationale first."
            ),
            "rollback": "Delete generated lesson_automation_approval_packet.* outputs; no source repos are touched.",
        },
        "approval_entries": entries,
        "review_status": "generated_candidate",
    }


def lesson_automation_approval_packet_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Lesson Automation Approval Packet",
        "",
        result["authority_boundary"],
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Methodology: `{result['methodology_version']}`",
        f"- Pending decisions: **{summary['pending_count']}**",
        f"- Recommended approvals: **{summary['recommended_approve_count']}**",
        f"- Recommended deferrals: **{summary['recommended_defer_count']}**",
        f"- Labels applied: **{summary['labels_applied']}**",
        f"- Commands executed: **{summary['commands_executed']}**",
        f"- Source repos mutated: **{summary['source_repos_mutated']}**",
        f"- Content files read: **{summary['content_files_read']}**",
        "",
        "## Recommended Decision Commands",
        "",
    ]
    for entry in result["approval_entries"]:
        lines.extend(
            [
                f"### {entry['sample_id']} - {entry['signal_family_id']}",
                "",
                f"- Recommended decision: `{entry['recommended_decision']}`",
                f"- Action kind: `{entry['action_kind']}`",
                f"- Priority score: `{entry['priority_score']}`",
                f"- Rationale: {entry['rationale']}",
                f"- Danger if misapplied: {entry['danger_if_misapplied']}",
                "",
            ]
        )
        if entry["label_command"]:
            lines.extend(["```powershell", entry["label_command"], "```", ""])
    lines.extend(
        [
            "## Risk Review",
            "",
            f"- Risk tier: `{result['risk_review']['risk_tier']}`",
            f"- Why not high: {result['risk_review']['why_not_high']}",
            f"- Premortem: {result['risk_review']['premortem']}",
            f"- Rollback: {result['risk_review']['rollback']}",
            "",
            "Self red-team:",
            "",
        ]
    )
    for item in result["risk_review"]["self_red_team"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Intentionally Not Done", ""])
    for item in result["intentionally_not_done"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_lesson_automation_approval_packet_outputs(
    repo_root: Path,
    *,
    decisions_file: Path | None = None,
    generated_at: str | None = None,
    repo_limit: int = 5,
    max_bytes_per_file: int = 20000,
    max_files: int = 50,
) -> dict[str, Any]:
    path = decisions_file or repo_root / DECISION_TEMPLATE_PATH
    if not path.is_absolute():
        path = repo_root / path
    records = load_lesson_automation_decisions(path)
    result = build_lesson_automation_approval_packet(
        repo_root,
        records,
        generated_at=generated_at,
        repo_limit=repo_limit,
        max_bytes_per_file=max_bytes_per_file,
        max_files=max_files,
    )
    reports_dir = repo_root / "processed" / "reports"
    paths = {
        "packet_markdown": reports_dir / "lesson_automation_approval_packet.md",
        "packet_json": reports_dir / "lesson_automation_approval_packet.json",
    }
    atomic_write_text(paths["packet_markdown"], lesson_automation_approval_packet_markdown(result))
    atomic_write_text(paths["packet_json"], json_dumps(result, pretty=True) + "\n")
    return {
        "output_type": "generated_approval_packet",
        "review_status": "generated_candidate",
        "summary": result["summary"],
        "outputs": {key: str(path) for key, path in paths.items()},
    }


def _scope_candidates_for_approval(
    scope: dict[str, Any],
    *,
    repo_keys: list[str],
    categories: list[str],
    max_files: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    repo_allow = {str(repo_key).strip().lower() for repo_key in repo_keys}
    category_allow = {str(category).strip().lower() for category in categories}
    rows: list[dict[str, Any]] = []
    repo_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    flagged_candidate_count = 0
    hygiene_rule_counts: dict[str, int] = {}
    flagged_repo_counts: dict[str, int] = {}
    flagged_category_counts: dict[str, int] = {}
    for repo_scope in scope.get("repo_scopes", []):
        repo_key = str(repo_scope.get("repo_key", ""))
        if repo_key.lower() not in repo_allow:
            continue
        for candidate in repo_scope.get("candidates", []):
            category = str(candidate.get("primary_category_id", ""))
            if category.lower() not in category_allow:
                continue
            repo_counts[repo_key] = repo_counts.get(repo_key, 0) + 1
            category_counts[category] = category_counts.get(category, 0) + 1
            hygiene_flags = _scope_hygiene_flags(candidate)
            if hygiene_flags:
                flagged_candidate_count += 1
                flagged_repo_counts[repo_key] = flagged_repo_counts.get(repo_key, 0) + 1
                flagged_category_counts[category] = flagged_category_counts.get(category, 0) + 1
                for flag in hygiene_flags:
                    rule_id = str(flag["rule_id"])
                    hygiene_rule_counts[rule_id] = hygiene_rule_counts.get(rule_id, 0) + 1
            if len(rows) >= max_files:
                continue
            rows.append(
                {
                    "repo_key": repo_key,
                    "category": category,
                    "asset_id": candidate.get("asset_id", ""),
                    "logical_path": candidate.get("logical_path", ""),
                    "relative_path": candidate.get("relative_path", ""),
                    "asset_type": candidate.get("asset_type", ""),
                    "value_score": candidate.get("value_score", 0),
                    "match_reasons": candidate.get("match_reasons", []),
                    "hygiene_flags": hygiene_flags,
                    "content_read_status": candidate.get(
                        "content_read_status", "not_read_by_scope_pack"
                    ),
                    "review_status": candidate.get("review_status", "generated_candidate"),
                }
            )
    return rows, {
        "matched_candidate_count": sum(repo_counts.values()),
        "reported_candidate_count": len(rows),
        "truncated_candidate_count": max(0, sum(repo_counts.values()) - len(rows)),
        "repo_counts": dict(sorted(repo_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "flagged_candidate_count": flagged_candidate_count,
        "unflagged_candidate_count": max(0, sum(repo_counts.values()) - flagged_candidate_count),
        "reported_flagged_candidate_count": sum(1 for row in rows if row.get("hygiene_flags")),
        "hygiene_rule_counts": dict(sorted(hygiene_rule_counts.items())),
        "flagged_repo_counts": dict(sorted(flagged_repo_counts.items())),
        "flagged_category_counts": dict(sorted(flagged_category_counts.items())),
    }


def build_lesson_automation_approval_impact(
    repo_root: Path,
    records: list[LessonAutomationDecisionRecord],
    *,
    sample_id: str = "lesson-automation-decision-001",
    generated_at: str | None = None,
    repo_limit: int = 5,
    max_bytes_per_file: int = 20000,
    max_files: int = 50,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    packet = build_lesson_automation_approval_packet(
        repo_root,
        records,
        generated_at=generated,
        repo_limit=repo_limit,
        max_bytes_per_file=max_bytes_per_file,
        max_files=max_files,
    )
    entry = next(
        (item for item in packet["approval_entries"] if item["sample_id"] == sample_id),
        None,
    )
    if entry is None:
        raise ValueError(f"No pending approval entry found for {sample_id}.")
    decision_record = next((record for record in records if record.sample_id == sample_id), None)
    if decision_record is None:
        raise ValueError(f"No decision record found for {sample_id}.")
    scope_file = Path(str(entry.get("scope_file") or ""))
    scope = _load_json(scope_file) if scope_file.exists() else None
    approval_fields = entry.get("approval_fields") or {}
    repo_keys = list(approval_fields.get("approved_repo_keys") or [])
    categories = list(approval_fields.get("approved_categories") or [])
    max_file_count = int(approval_fields.get("max_files") or max_files)
    candidate_rows: list[dict[str, Any]] = []
    candidate_summary: dict[str, Any] = {
        "matched_candidate_count": 0,
        "reported_candidate_count": 0,
        "truncated_candidate_count": 0,
        "repo_counts": {},
        "category_counts": {},
        "flagged_candidate_count": 0,
        "unflagged_candidate_count": 0,
        "reported_flagged_candidate_count": 0,
        "hygiene_rule_counts": {},
        "flagged_repo_counts": {},
        "flagged_category_counts": {},
    }
    if scope:
        candidate_rows, candidate_summary = _scope_candidates_for_approval(
            scope,
            repo_keys=repo_keys,
            categories=categories,
            max_files=max_file_count,
        )
    max_bytes = int(approval_fields.get("max_bytes_per_file") or max_bytes_per_file)
    matched_count = int(candidate_summary["matched_candidate_count"])
    flagged_count = int(candidate_summary["flagged_candidate_count"])
    suggested_human_decision = (
        "narrow_before_approval" if flagged_count else "approve_generated_scope_if_human_agrees"
    )
    include_paths = [
        str(row.get("logical_path") or row.get("relative_path") or "")
        for row in candidate_rows
        if not row.get("hygiene_flags") and (row.get("logical_path") or row.get("relative_path"))
    ]
    excluded_paths = [
        str(row.get("logical_path") or row.get("relative_path") or "")
        for row in candidate_rows
        if row.get("hygiene_flags") and (row.get("logical_path") or row.get("relative_path"))
    ]
    can_generate_exact_narrowed_command = bool(
        flagged_count
        and include_paths
        and int(candidate_summary["truncated_candidate_count"]) == 0
        and len(candidate_rows) == matched_count
    )
    narrowed_max_files = len(include_paths) if can_generate_exact_narrowed_command else 0
    narrowed_rationale = (
        "Approve bounded read-only extraction from the unflagged generated scope rows only. "
        "Hygiene-flagged inspection, backup, fixture, seed-pack, private-looking, dependency, "
        "or cache paths remain excluded unless separately approved. No source repo mutation, "
        "no GitHub/API/model calls, redaction required."
    )
    narrowed_approval_command = (
        _label_command(
            decision_record,
            decision="approve",
            approval_id=str(approval_fields.get("approval_id") or ""),
            repo_keys=repo_keys,
            categories=categories,
            include_paths=include_paths,
            exclude_paths=[],
            max_bytes_per_file=max_bytes,
            max_files=narrowed_max_files,
            allow_content_read=True,
            rationale=narrowed_rationale,
        )
        if can_generate_exact_narrowed_command
        else ""
    )
    max_possible_bytes = min(matched_count, max_file_count) * max_bytes
    return {
        "methodology_version": "lesson-automation-approval-impact-v0.3",
        "generated_at": generated,
        "authority_boundary": (
            "Generated approval impact brief only. This command reads pending decision rows, "
            "the generated approval packet, and generated scope metadata; it does not apply "
            "labels, approve actions, execute commands, read source contents, mutate source repos, "
            "call GitHub, call models, or promote candidates."
        ),
        "summary": {
            "sample_id": sample_id,
            "signal_family_id": entry.get("signal_family_id", ""),
            "action_kind": entry.get("action_kind", ""),
            "recommended_decision": entry.get("recommended_decision", ""),
            "approved_repo_count": len(repo_keys),
            "approved_category_count": len(categories),
            "matched_candidate_count": matched_count,
            "reported_candidate_count": int(candidate_summary["reported_candidate_count"]),
            "truncated_candidate_count": int(candidate_summary["truncated_candidate_count"]),
            "flagged_candidate_count": flagged_count,
            "unflagged_candidate_count": int(candidate_summary["unflagged_candidate_count"]),
            "reported_flagged_candidate_count": int(
                candidate_summary["reported_flagged_candidate_count"]
            ),
            "suggested_human_decision": suggested_human_decision,
            "max_bytes_per_file": max_bytes,
            "max_files": max_file_count,
            "max_possible_bytes_if_later_executed": max_possible_bytes,
            "scope_file_present": bool(scope),
            "labels_applied": 0,
            "commands_executed": 0,
            "content_files_read": 0,
            "source_repos_mutated": 0,
            "github_calls": 0,
            "model_calls": 0,
        },
        "approval_command": entry.get("label_command", ""),
        "narrowed_approval": {
            "available": can_generate_exact_narrowed_command,
            "recommended_decision": (
                "approve_clean_subset_if_human_agrees"
                if can_generate_exact_narrowed_command
                else "regenerate_or_manually_narrow_before_approval"
            ),
            "include_path_count": len(include_paths),
            "excluded_flagged_path_count": len(excluded_paths),
            "max_files": narrowed_max_files,
            "max_possible_bytes_if_later_executed": narrowed_max_files * max_bytes,
            "include_paths": include_paths,
            "excluded_flagged_paths": excluded_paths,
            "approval_command": narrowed_approval_command,
            "rationale": narrowed_rationale if can_generate_exact_narrowed_command else "",
            "danger_if_misapplied": (
                "This command is still only a generated suggestion. It must be explicitly "
                "approved by Lowell before the decision ledger is updated or content is read."
            ),
        },
        "approval_fields": approval_fields,
        "candidate_summary": candidate_summary,
        "scope_hygiene": {
            "suggested_human_decision": suggested_human_decision,
            "flagged_candidate_count": flagged_count,
            "unflagged_candidate_count": int(candidate_summary["unflagged_candidate_count"]),
            "reported_flagged_candidate_count": int(
                candidate_summary["reported_flagged_candidate_count"]
            ),
            "hygiene_rule_counts": candidate_summary["hygiene_rule_counts"],
            "flagged_repo_counts": candidate_summary["flagged_repo_counts"],
            "flagged_category_counts": candidate_summary["flagged_category_counts"],
            "recommended_narrowing": (
                "Exclude flagged inspection, extract, backup, private-looking, dependency/cache, "
                "fixture, or seed-pack paths unless Lowell explicitly approves those classes."
            ),
            "applies_when": [
                "A generated approval scope is being reviewed before content reads or source-repo actions.",
                "Candidate paths include extracted copies, backups, fixtures, private-looking names, or build/cache outputs.",
            ],
            "does_not_apply_when": [
                "Lowell has explicitly approved those flagged path classes for this exact action.",
                "The task is only recording raw metadata and will not unlock a content read or source mutation.",
            ],
            "danger_if_misapplied": (
                "Over-narrowing can hide useful lineage evidence, while under-narrowing can spend "
                "human approval on copied, private-looking, or generated noise."
            ),
        },
        "candidate_rows": candidate_rows,
        "proof_unlocked_after_human_approval": [
            "content_read_approval_recorded",
            "priority_extract_execution_plan_ready after regenerating execution plan",
            "priority_observations_present only after running the approved extractor",
        ],
        "post_approval_sequence": [
            "Run only the human-approved decision-label command.",
            "Regenerate lesson-automation-execution-plan.",
            "Inspect the generated priority-content-extract command.",
            "Run the extractor only if the command exactly matches the approved repo keys, categories, caps, and approval id.",
            "Regenerate repo-completion-proof-check.",
        ],
        "checked_inputs": [
            "processed/learning/lesson_automation_action_decisions.jsonl",
            "processed/reports/lesson_automation_approval_packet.json or regenerated packet data",
            "processed/reports/priority_content_extract_scope.json",
        ],
        "intentionally_not_done": [
            "decision-label command execution",
            "approval application",
            "content extraction",
            "source repo mutation",
            "GitHub/API/model calls",
            "roadmap phase completion",
        ],
        "risk_review": {
            "risk_tier": "medium",
            "why_not_high": (
                "The brief is generated-only and reads metadata, but the decision it supports "
                "would unlock a real content-read command if Lowell approves it."
            ),
            "self_red_team": [
                "A generated impact brief can be mistaken for approval.",
                "Path metadata can be stale if the catalog has not been refreshed after source changes.",
                "Flagged hygiene paths can be mistaken for automatic rejection instead of a narrowing cue.",
                "The byte cap is an upper bound, not a guarantee that all sensitive content will be harmless.",
                "Category matching is deterministic path metadata, not proof that content is useful.",
            ],
            "premortem": (
                "The likely failure is approving a broad repo/category set without checking the "
                "candidate path list, hygiene flags, and max possible bytes."
            ),
            "rollback": "Delete generated lesson_automation_approval_impact.* outputs; no source repos are touched.",
        },
        "review_status": "generated_candidate",
    }


def lesson_automation_approval_impact_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Lesson Automation Approval Impact",
        "",
        result["authority_boundary"],
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Methodology: `{result['methodology_version']}`",
        f"- Sample id: `{summary['sample_id']}`",
        f"- Signal family: `{summary['signal_family_id']}`",
        f"- Recommended decision: `{summary['recommended_decision']}`",
        f"- Proposed repo count: **{summary['approved_repo_count']}**",
        f"- Proposed category count: **{summary['approved_category_count']}**",
        f"- Matched candidate paths: **{summary['matched_candidate_count']}**",
        f"- Candidate paths shown: **{summary['reported_candidate_count']}**",
        f"- Hygiene-flagged candidate paths: **{summary['flagged_candidate_count']}**",
        f"- Suggested human decision: `{summary['suggested_human_decision']}`",
        f"- Max possible bytes if later executed: **{summary['max_possible_bytes_if_later_executed']}**",
        f"- Labels applied: **{summary['labels_applied']}**",
        f"- Commands executed: **{summary['commands_executed']}**",
        f"- Content files read: **{summary['content_files_read']}**",
        f"- Source repos mutated: **{summary['source_repos_mutated']}**",
        "",
        "## Proposed Approval Command",
        "",
        "```powershell",
        result["approval_command"],
        "```",
        "",
        "## Narrowed Clean-Subset Command",
        "",
    ]
    narrowed = result["narrowed_approval"]
    if narrowed["available"]:
        lines.extend(
            [
                f"- Recommended decision: `{narrowed['recommended_decision']}`",
                f"- Included unflagged paths: **{narrowed['include_path_count']}**",
                f"- Excluded flagged paths: **{narrowed['excluded_flagged_path_count']}**",
                f"- Max files: **{narrowed['max_files']}**",
                f"- Max possible bytes if later executed: **{narrowed['max_possible_bytes_if_later_executed']}**",
                f"- Danger if misapplied: {narrowed['danger_if_misapplied']}",
                "",
                "```powershell",
                narrowed["approval_command"],
                "```",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"- Recommended decision: `{narrowed['recommended_decision']}`",
                "- Exact clean-subset command unavailable because the scope is truncated, unflagged paths are missing, or no hygiene flags were found.",
                "",
            ]
        )
    lines.extend(
        [
        "## Candidate Counts",
        "",
        "By repo:",
        ]
    )
    for repo_key, count in result["candidate_summary"]["repo_counts"].items():
        lines.append(f"- `{repo_key}`: **{count}**")
    lines.extend(["", "By category:"])
    for category, count in result["candidate_summary"]["category_counts"].items():
        lines.append(f"- `{category}`: **{count}**")
    hygiene = result["scope_hygiene"]
    lines.extend(["", "## Scope Hygiene", ""])
    lines.append(f"- Suggested human decision: `{hygiene['suggested_human_decision']}`")
    lines.append(f"- Flagged candidate paths: **{hygiene['flagged_candidate_count']}**")
    lines.append(f"- Unflagged candidate paths: **{hygiene['unflagged_candidate_count']}**")
    lines.append(f"- Recommendation: {hygiene['recommended_narrowing']}")
    lines.extend(["", "By hygiene rule:"])
    if hygiene["hygiene_rule_counts"]:
        for rule_id, count in hygiene["hygiene_rule_counts"].items():
            lines.append(f"- `{rule_id}`: **{count}**")
    else:
        lines.append("- None.")
    lines.extend(["", "Context boundary:"])
    lines.append("- Applies when: " + "; ".join(hygiene["applies_when"]))
    lines.append("- Does not apply when: " + "; ".join(hygiene["does_not_apply_when"]))
    lines.append(f"- Danger if misapplied: {hygiene['danger_if_misapplied']}")
    lines.extend(["", "## Candidate Path Sample", ""])
    lines.append("| Repo | Category | Path | Type | Score | Hygiene flags | Match reasons |")
    lines.append("|---|---|---|---|---:|---|---|")
    for row in result["candidate_rows"][:100]:
        path = row.get("relative_path") or row.get("logical_path") or ""
        hygiene_flags = ", ".join(flag["rule_id"] for flag in row.get("hygiene_flags") or [])
        lines.append(
            "| `{repo}` | `{category}` | `{path}` | `{asset_type}` | {score:.1f} | `{hygiene}` | `{reasons}` |".format(
                repo=row.get("repo_key", ""),
                category=row.get("category", ""),
                path=str(path).replace("|", "/"),
                asset_type=row.get("asset_type", ""),
                score=float(row.get("value_score") or 0),
                hygiene=hygiene_flags or "none",
                reasons=", ".join(row.get("match_reasons") or []),
            )
        )
    lines.extend(["", "## Proof Unlocked After Human Approval", ""])
    for item in result["proof_unlocked_after_human_approval"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Post-Approval Sequence", ""])
    for item in result["post_approval_sequence"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Risk Review", ""])
    lines.append(f"- Risk tier: `{result['risk_review']['risk_tier']}`")
    lines.append(f"- Why not high: {result['risk_review']['why_not_high']}")
    lines.append(f"- Premortem: {result['risk_review']['premortem']}")
    lines.append(f"- Rollback: {result['risk_review']['rollback']}")
    lines.extend(["", "Self red-team:"])
    for item in result["risk_review"]["self_red_team"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Intentionally Not Done", ""])
    for item in result["intentionally_not_done"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_lesson_automation_approval_impact_outputs(
    repo_root: Path,
    *,
    decisions_file: Path | None = None,
    sample_id: str = "lesson-automation-decision-001",
    generated_at: str | None = None,
    repo_limit: int = 5,
    max_bytes_per_file: int = 20000,
    max_files: int = 50,
) -> dict[str, Any]:
    path = decisions_file or repo_root / DECISION_TEMPLATE_PATH
    if not path.is_absolute():
        path = repo_root / path
    records = load_lesson_automation_decisions(path)
    result = build_lesson_automation_approval_impact(
        repo_root,
        records,
        sample_id=sample_id,
        generated_at=generated_at,
        repo_limit=repo_limit,
        max_bytes_per_file=max_bytes_per_file,
        max_files=max_files,
    )
    reports_dir = repo_root / "processed" / "reports"
    paths = {
        "impact_markdown": reports_dir / "lesson_automation_approval_impact.md",
        "impact_json": reports_dir / "lesson_automation_approval_impact.json",
    }
    atomic_write_text(paths["impact_markdown"], lesson_automation_approval_impact_markdown(result))
    atomic_write_text(paths["impact_json"], json_dumps(result, pretty=True) + "\n")
    return {
        "output_type": "generated_approval_impact_brief",
        "review_status": "generated_candidate",
        "summary": result["summary"],
        "outputs": {key: str(path) for key, path in paths.items()},
    }


def _execution_entry_for_decision(
    repo_root: Path,
    record: LessonAutomationDecisionRecord,
) -> dict[str, Any]:
    _validate_decision(record)
    base = {
        "decision_id": record.decision_id,
        "sample_id": record.sample_id,
        "signal_family_id": record.signal_family_id,
        "action_kind": record.action_kind,
        "approval_id": record.approval_id,
        "reviewer": record.reviewer,
        "reviewed_at": record.reviewed_at,
        "approval_evidence": {
            "approved_scope_file": record.approved_scope_file,
            "approved_repo_keys": record.approved_repo_keys,
            "approved_categories": record.approved_categories,
            "approved_repo_paths": record.approved_repo_paths,
            "approved_include_paths": record.approved_include_paths,
            "approved_exclude_paths": record.approved_exclude_paths,
            "max_bytes_per_file": record.max_bytes_per_file,
            "max_files": record.max_files,
            "allow_content_read": record.allow_content_read,
            "allow_source_mutation": record.allow_source_mutation,
            "allow_external_api": record.allow_external_api,
            "allow_model_call": record.allow_model_call,
            "redaction_required": record.redaction_required,
            "token_scope_note": record.token_scope_note,
            "privacy_boundary_note": record.privacy_boundary_note,
            "rationale": record.rationale,
        },
        "stop_conditions": record.stop_conditions,
        "validation_commands": record.validation_commands,
        "source_repos_mutated_by_plan": 0,
        "content_files_read_by_plan": 0,
        "github_calls_by_plan": 0,
        "model_calls_by_plan": 0,
    }
    scope_file = _path_for_command(repo_root, record.approved_scope_file)
    if record.action_kind == "bounded_content_extract":
        command = (
            "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend "
            f'priority-content-extract --approval-id "{record.approval_id}" '
            f'{_repeat_option("--repo-key", record.approved_repo_keys)} '
            f'{_repeat_option("--category", record.approved_categories)} '
            f'{_repeat_option("--include-path", record.approved_include_paths)} '
            f'{_repeat_option("--exclude-path", record.approved_exclude_paths)} '
            f'--scope-file "{scope_file}" '
            f"--max-bytes-per-file {record.max_bytes_per_file} "
            f"--limit {record.max_files}"
        )
        return {
            **base,
            "execution_status": "ready_for_manual_run",
            "execution_mode": "generated_command_only",
            "command": " ".join(command.split()),
            "manual_next_step": "",
            "danger_if_misapplied": (
                "Running this command reads approved source content into generated observations. "
                "Do not broaden repo keys, categories, byte caps, or file limits."
            ),
        }
    if record.action_kind == "source_repo_files_only_install":
        commands = [
            "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli agent "
            f'install-learning-loop --repo "{path}" --mode files-only'
            for path in record.approved_repo_paths
        ]
        status = "ready_for_manual_run" if commands else "blocked_missing_repo_path"
        return {
            **base,
            "execution_status": status,
            "execution_mode": "manual_source_repo_write_command",
            "command": "\n".join(commands),
            "manual_next_step": (
                "" if commands else "Resolve approved repo keys to exact repo paths before installation."
            ),
            "danger_if_misapplied": (
                "This writes files into source repos. Run only for explicitly approved repo paths."
            ),
        }
    if record.action_kind == "source_repo_governance_adoption":
        return {
            **base,
            "execution_status": "manual_source_repo_change_required",
            "execution_mode": "no_auto_executor",
            "command": "",
            "manual_next_step": (
                "Create a normal source-repo change from "
                "templates/cross-repo-governance-dependency-map/ for the approved repo family."
            ),
            "danger_if_misapplied": (
                "Governance maps and child mirrors can imply authority. Human review must select "
                "upstream authority, child mirrors, validators, and tests before editing source repos."
            ),
        }
    if record.action_kind == "extractor_gap_or_bounded_content_extract":
        return {
            **base,
            "execution_status": "blocked_missing_executor",
            "execution_mode": "requires_future_extractor",
            "command": "",
            "manual_next_step": (
                "Implement or approve a bounded CI/release artifact extractor before reading artifacts."
            ),
            "danger_if_misapplied": (
                "CI and release artifacts may contain secrets or noisy generated logs. Do not reuse "
                "the priority-content extractor without a specific artifact redaction policy."
            ),
        }
    if record.action_kind == "external_api_gate":
        return {
            **base,
            "execution_status": "blocked_external_api_gate",
            "execution_mode": "no_auto_executor",
            "command": "",
            "manual_next_step": "Configure read-only token scope, rate limits, and privacy boundary first.",
            "danger_if_misapplied": "External metadata can leak private repo context or exceed source terms.",
        }
    return {
        **base,
        "execution_status": "manual_review_required",
        "execution_mode": "unknown_action_kind",
        "command": "",
        "manual_next_step": "Review this approved action manually; no deterministic executor is registered.",
        "danger_if_misapplied": "Unknown action kinds must not be executed automatically.",
    }


def build_lesson_automation_execution_plan(
    repo_root: Path,
    records: list[LessonAutomationDecisionRecord],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    approved = [
        record
        for record in records
        if record.decision == "approve" and record.review_status == "reviewed"
    ]
    rejected_or_deferred = [
        record for record in records if record.decision in {"defer", "reject"}
    ]
    pending = [record for record in records if record.decision == "pending"]
    entries = [_execution_entry_for_decision(repo_root, record) for record in approved]
    ready_statuses = {"ready_for_manual_run"}
    return {
        "methodology_version": "lesson-automation-execution-plan-v0.1",
        "generated_at": generated,
        "authority_boundary": (
            "Generated execution plan only. This command reads reviewed decision rows and writes "
            "runnable command text for approved actions; it does not execute commands, read source "
            "content, mutate source repos, call GitHub, call models, or promote candidates to truth."
        ),
        "summary": {
            "decision_count": len(records),
            "approved_count": len(approved),
            "pending_count": len(pending),
            "deferred_or_rejected_count": len(rejected_or_deferred),
            "execution_entry_count": len(entries),
            "ready_for_manual_run_count": sum(
                1 for entry in entries if entry["execution_status"] in ready_statuses
            ),
            "blocked_or_manual_count": sum(
                1 for entry in entries if entry["execution_status"] not in ready_statuses
            ),
            "commands_executed": 0,
            "source_repos_mutated": 0,
            "content_files_read": 0,
            "github_calls": 0,
            "model_calls": 0,
        },
        "checked_inputs": [
            "processed/learning/lesson_automation_action_decisions.jsonl",
        ],
        "intentionally_not_done": [
            "command execution",
            "source repo mutation",
            "source file content reads",
            "fresh filesystem recursion",
            "GitHub, CI, package registry, or model calls",
            "roadmap phase completion",
        ],
        "applies_when": [
            "A human has reviewed one or more lesson-automation decision rows.",
            "A future agent needs exact commands or manual next steps for approved actions.",
        ],
        "does_not_apply_when": [
            "All decision rows are pending, deferred, or rejected.",
            "The user asks to approve a new action; use the decision-label command first.",
        ],
        "danger_if_misapplied": (
            "A generated execution plan can be mistaken for completed execution. It only contains "
            "commands or manual steps and never proves that a lesson was extracted or installed."
        ),
        "execution_entries": entries,
        "review_status": "generated_candidate",
    }


def lesson_automation_execution_plan_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Lesson Automation Execution Plan",
        "",
        result["authority_boundary"],
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Methodology: `{result['methodology_version']}`",
        f"- Approved decisions: **{summary['approved_count']}**",
        f"- Pending decisions: **{summary['pending_count']}**",
        f"- Ready for manual run: **{summary['ready_for_manual_run_count']}**",
        f"- Commands executed: **{summary['commands_executed']}**",
        f"- Source repos mutated: **{summary['source_repos_mutated']}**",
        f"- Content files read: **{summary['content_files_read']}**",
        "",
    ]
    if not result["execution_entries"]:
        lines.extend(
            [
                "No approved execution entries exist yet.",
                "",
                "Next step: label a row in `processed/learning/lesson_automation_action_decisions.jsonl` "
                "with `recommend lesson-automation-decision-label`, then regenerate this plan.",
                "",
            ]
        )
    else:
        lines.extend(["## Entries", ""])
        for entry in result["execution_entries"]:
            lines.extend(
                [
                    f"### {entry['sample_id']} - {entry['signal_family_id']}",
                    "",
                    f"- Status: `{entry['execution_status']}`",
                    f"- Mode: `{entry['execution_mode']}`",
                    f"- Approval id: `{entry['approval_id']}`",
                    f"- Danger if misapplied: {entry['danger_if_misapplied']}",
                    "",
                ]
            )
            if entry["command"]:
                lines.extend(["```powershell", entry["command"], "```", ""])
            if entry["manual_next_step"]:
                lines.append(f"Manual next step: {entry['manual_next_step']}")
                lines.append("")
    lines.extend(["## Intentionally Not Done", ""])
    for item in result["intentionally_not_done"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_lesson_automation_execution_plan_outputs(
    repo_root: Path,
    *,
    decisions_file: Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    path = decisions_file or repo_root / DECISION_TEMPLATE_PATH
    if not path.is_absolute():
        path = repo_root / path
    records = load_lesson_automation_decisions(path)
    result = build_lesson_automation_execution_plan(
        repo_root,
        records,
        generated_at=generated_at,
    )
    reports_dir = repo_root / "processed" / "reports"
    paths = {
        "plan_markdown": reports_dir / "lesson_automation_execution_plan.md",
        "plan_json": reports_dir / "lesson_automation_execution_plan.json",
    }
    atomic_write_text(paths["plan_markdown"], lesson_automation_execution_plan_markdown(result))
    atomic_write_text(paths["plan_json"], json_dumps(result, pretty=True) + "\n")
    return {
        "output_type": "generated_execution_plan",
        "review_status": "generated_candidate",
        "summary": result["summary"],
        "outputs": {key: str(path) for key, path in paths.items()},
    }


def write_lesson_automation_decision_template_outputs(
    repo_root: Path,
    *,
    limit: int = 25,
    generated_at: str | None = None,
) -> dict[str, Any]:
    queue = build_lesson_automation_next_action_queue(
        repo_root,
        generated_at=generated_at,
        limit=limit,
    )
    records = build_lesson_automation_decision_template(queue["actions"], limit=limit)
    decision_path = repo_root / DECISION_TEMPLATE_PATH
    report_path = repo_root / "processed" / "reports" / "lesson_automation_decision_template.md"
    report_json_path = repo_root / "processed" / "reports" / "lesson_automation_decision_template.json"
    write_lesson_automation_decisions(decision_path, records)
    payload = {
        "methodology_version": METHODOLOGY_VERSION,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": summarize_lesson_automation_decisions(records),
        "decision_template": [record.model_dump(mode="json") for record in records],
        "review_status": "generated_candidate",
    }
    atomic_write_text(report_path, lesson_automation_decision_markdown(records))
    atomic_write_text(report_json_path, json_dumps(payload, pretty=True) + "\n")
    return {
        "output_type": "generated_decision_template",
        "review_status": "generated_candidate",
        "summary": payload["summary"],
        "outputs": {
            "decision_template": str(decision_path),
            "report_markdown": str(report_path),
            "report_json": str(report_json_path),
        },
    }
