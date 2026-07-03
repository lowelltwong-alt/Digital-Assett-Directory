from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from ..utils import write_json
from .models import RustRolloutDecision
from .policy import can_apply_forced_rollout, load_rust_repo_records


def build_rust_rollout_plan(config_path: Path) -> dict[str, Any]:
    records = load_rust_repo_records(config_path)
    decisions = [can_apply_forced_rollout(record) for record in records]
    counts = Counter(decision.rollout_mode for decision in decisions)
    block_counts = Counter(
        decision.block_reason for decision in decisions if decision.block_reason
    )
    return {
        "schema_version": "dad_rust_rollout_plan.v1",
        "config_path": str(config_path),
        "repo_count": len(decisions),
        "counts_by_rollout_mode": dict(sorted(counts.items())),
        "counts_by_block_reason": dict(sorted(block_counts.items())),
        "forced_rollout_eligible": [
            decision.to_dict() for decision in decisions if decision.can_apply
        ],
        "logos_instruction_mail_only": [
            decision.to_dict()
            for decision in decisions
            if decision.rollout_mode == "instruction_mail_only"
        ],
        "blocked": [
            decision.to_dict()
            for decision in decisions
            if not decision.can_apply and decision.rollout_mode != "instruction_mail_only"
        ],
        "decisions": [decision.to_dict() for decision in decisions],
        "authority_boundary": (
            "Candidate rollout plan only. DAD may not mutate a target repo unless a "
            "human invokes an apply command and the policy decision permits it."
        ),
    }


def write_rust_rollout_plan(config_path: Path, out_dir: Path) -> dict[str, Any]:
    plan = build_rust_rollout_plan(config_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "rollout_plan.json", plan)
    write_json(out_dir / "eligibility_report.json", _eligibility_report(plan))
    (out_dir / "rollout_plan.md").write_text(_plan_markdown(plan), encoding="utf-8")
    (out_dir / "eligibility_report.md").write_text(
        _eligibility_markdown(plan), encoding="utf-8"
    )
    return {
        "plan": plan,
        "written": [
            str(out_dir / "rollout_plan.json"),
            str(out_dir / "rollout_plan.md"),
            str(out_dir / "eligibility_report.json"),
            str(out_dir / "eligibility_report.md"),
        ],
    }


def decision_by_repo(plan: dict[str, Any], repo: str) -> RustRolloutDecision:
    for row in plan.get("decisions", []):
        if str(row.get("repo")) == repo or str(row.get("repo_name")) == repo:
            return RustRolloutDecision(**row)
    raise ValueError(f"Unknown repo in Rust rollout plan: {repo}")


def _eligibility_report(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "dad_rust_rollout_eligibility_report.v1",
        "repo_count": plan["repo_count"],
        "counts_by_rollout_mode": plan["counts_by_rollout_mode"],
        "counts_by_block_reason": plan["counts_by_block_reason"],
        "eligible_repos": [
            row["repo"] for row in plan["forced_rollout_eligible"]
        ],
        "logos_instruction_mail_only": [
            row["repo"] for row in plan["logos_instruction_mail_only"]
        ],
        "blocked_repos": [
            {"repo": row["repo"], "reason": row["block_reason"]}
            for row in plan["blocked"]
        ],
    }


def _plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# DAD Rust Rollout Plan",
        "",
        f"Repo count: {plan['repo_count']}",
        "",
        "## Counts",
        "",
    ]
    for key, value in plan["counts_by_rollout_mode"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Decisions", "", "| Repo | Mode | Can apply | Reason | First slice |", "|---|---|---:|---|---|"])
    for row in plan["decisions"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(row["repo"]),
                    _cell(row["rollout_mode"]),
                    "yes" if row["can_apply"] else "no",
                    _cell(row["block_reason"] or ""),
                    _cell(row["recommended_first_rust_slice"]),
                ]
            )
            + " |"
        )
    lines.extend(["", plan["authority_boundary"], ""])
    return "\n".join(lines)


def _eligibility_markdown(plan: dict[str, Any]) -> str:
    report = _eligibility_report(plan)
    lines = ["# DAD Rust Rollout Eligibility", ""]
    lines.append("## Eligible")
    lines.extend(f"- `{repo}`" for repo in report["eligible_repos"])
    lines.append("")
    lines.append("## Logos Instruction Mail Only")
    lines.extend(f"- `{repo}`" for repo in report["logos_instruction_mail_only"])
    lines.append("")
    lines.append("## Blocked")
    for row in report["blocked_repos"]:
        lines.append(f"- `{row['repo']}`: {row['reason']}")
    lines.append("")
    return "\n".join(lines)


def _cell(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")
