from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .ids import stable_id
from .utils import atomic_write_text, json_dumps, utc_now

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

SCOPE_FILES = {
    "priority_content_extracts": "priority_content_extract_scope.json",
    "repo_learning_events": "repo_learning_loop_install_scope.json",
    "governance_map_adoption": "governance_map_adoption_scope.json",
    "ci_and_release_artifacts": "ci_release_artifact_scope.json",
}


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
