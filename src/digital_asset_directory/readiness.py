from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import AssetRecord
from .utils import atomic_write_text, utc_now

MOCK_TRIAL_EXCLUSION_TERMS = ("mock trial", "mock-trial", "mock_trial", "mock trial4.26")


def _contains_any(value: str, terms: tuple[str, ...]) -> bool:
    lowered = value.lower()
    return any(term in lowered for term in terms)


def _governance_readiness(asset: AssetRecord) -> dict[str, Any]:
    entrypoints = set(asset.entrypoints)
    governance_files = {"AGENTS.md", "CLAUDE.md", "AI_FRONT_DOOR.md"}
    present = sorted(entrypoints & governance_files)
    missing = sorted(governance_files - entrypoints)
    return {
        "present": present,
        "missing": missing,
        "score": len(present),
    }


def downstream_pilot_candidates_markdown(
    assets: list[AssetRecord],
    *,
    limit: int = 10,
    excluded_terms: tuple[str, ...] = MOCK_TRIAL_EXCLUSION_TERMS,
) -> tuple[str, dict[str, Any]]:
    repositories = [asset for asset in assets if asset.asset_type == "repository"]
    excluded = [
        asset
        for asset in repositories
        if _contains_any(f"{asset.title} {asset.logical_path}", excluded_terms)
    ]
    candidates = [asset for asset in repositories if asset not in excluded]

    def rank_key(asset: AssetRecord) -> tuple[float, int, str]:
        readiness = _governance_readiness(asset)
        stability_bonus = 10 if asset.freshness_status != "current" else 0
        return (asset.value_score + readiness["score"] * 5 + stability_bonus, readiness["score"], asset.title)

    ranked = sorted(candidates, key=rank_key, reverse=True)
    lines = [
        "# Downstream Governance Pilot Candidates",
        "",
        "Generated candidate report only. No downstream repository hooks were installed.",
        "",
        f"- Generated at: `{utc_now()}`",
        f"- Repository assets considered: **{len(repositories)}**",
        f"- Candidate repositories: **{len(candidates)}**",
        f"- Excluded active/changing repositories: **{len(excluded)}**",
        "- Default exclusion: Mock Trial repositories while active work is in progress.",
        "",
        "## Recommended Candidates",
        "",
    ]
    if not ranked:
        lines.append("No eligible downstream pilot candidates were found in the current catalog.")
    for index, asset in enumerate(ranked[:limit], start=1):
        readiness = _governance_readiness(asset)
        churn_risk = "medium" if asset.freshness_status == "current" else "low"
        lines.extend(
            [
                f"### {index}. {asset.title}",
                f"- Asset ID: `{asset.asset_id}`",
                f"- Path: `{asset.logical_path}`",
                f"- Value score: **{asset.value_score}**",
                f"- Freshness: `{asset.freshness_status}`",
                f"- Active churn risk: `{churn_risk}`",
                f"- Sensitivity: `{asset.sensitivity}`",
                f"- Governance files present: {', '.join(readiness['present']) or 'none'}",
                f"- Governance files missing: {', '.join(readiness['missing']) or 'none'}",
                "- Required human decision: approve or reject as pilot before installing hooks.",
                "",
            ]
        )
    if excluded:
        lines.extend(["## Excluded Repositories", ""])
        for asset in sorted(excluded, key=lambda item: item.title):
            lines.append(f"- `{asset.logical_path}`: excluded by active Mock Trial safety rule.")
        lines.append("")
    lines.extend(
        [
            "## Stop Conditions",
            "",
            "- Do not install governance until the user selects a pilot repository.",
            "- Do not mutate source repositories from this report.",
            "- Run preflight/postflight around any later hook installation.",
            "",
        ]
    )
    summary = {
        "repository_count": len(repositories),
        "candidate_count": len(candidates),
        "excluded_count": len(excluded),
        "output_type": "generated_candidate_report",
    }
    return "\n".join(lines), summary


def write_downstream_pilot_candidates(
    repo_root: Path, assets: list[AssetRecord], *, limit: int = 10
) -> dict[str, Any]:
    output = repo_root / "processed" / "reports" / "downstream_pilot_candidates.md"
    text, summary = downstream_pilot_candidates_markdown(assets, limit=limit)
    atomic_write_text(output, text + "\n")
    return {**summary, "output": str(output)}


def phase4_readiness_markdown() -> str:
    return "\n".join(
        [
            "# Phase 4 Semantic Enrichment Readiness",
            "",
            "Conservative boundary template. Do not enable embeddings or model enrichment from this file.",
            "",
            "## Current Conservative Decision",
            "",
            "- External provider use: not approved.",
            "- Embeddings/model enrichment: deferred.",
            "- Approved enrichment surface: deterministic local content profiles, calibrated reports, and generated candidate metadata only.",
            "- Provider/privacy boundary: no raw source content, private data, secrets, or raw chat leaves the local repository boundary for semantic enrichment.",
            "- Gate evidence: `roadmap/evidence/phase-4-semantic-enrichment.md`.",
            "",
            "## Required Decisions",
            "",
            "- Provider/privacy boundary approved: local-only/no-external-provider boundary",
            "- Deterministic baseline retained: yes",
            "- Evaluation harness shows measurable benefit: Phase 2.5 score-delta validation",
            "- Generated metadata remains candidate status: yes",
            "",
            "## Minimum Evaluation Criteria",
            "",
            "- Compare deterministic-only outputs against enriched outputs on the same catalog.",
            "- Measure useful-at-K, false positives, missing useful links, and review burden.",
            "- Keep all enriched tags, summaries, links, and scores as generated candidates.",
            "- Treat any future embedding/provider proposal as a new human gate, not as already approved.",
            "",
        ]
    )


def phase5_readiness_markdown() -> str:
    return "\n".join(
        [
            "# Phase 5 Alerting And Research Radar Readiness",
            "",
            "Conservative boundary template. Do not schedule scans or run external research from this file.",
            "",
            "## Current Conservative Decision",
            "",
            "- Alert channel: local generated reports under `processed/` only.",
            "- Scheduled scans: not approved.",
            "- External missing-part research automation: not approved.",
            "- External code intake: human license, provenance, security, and compatibility review required before reuse.",
            "- Gate evidence: `roadmap/evidence/phase-5-alerting-and-research-radar.md`.",
            "",
            "## Required Decisions",
            "",
            "- Alert channels approved: local generated reports only",
            "- Rate limits and source terms reviewed: zero scheduled external calls; source-terms review required before any future external research",
            "- External code review gates active: yes",
            "- No autonomous merge or promotion path: yes",
            "",
            "## Minimum Safety Criteria",
            "",
            "- Alerting must point to generated candidate evidence, not source truth.",
            "- External research must record license, provenance, freshness, and review status.",
            "- No external code may be merged without human license/security review.",
            "- Treat any future notification channel, scheduled scan, or external search provider as a new human gate.",
            "",
        ]
    )


def write_phase45_readiness_reports(repo_root: Path) -> dict[str, str]:
    phase4 = repo_root / "processed" / "reports" / "phase4_semantic_enrichment_readiness.md"
    phase5 = repo_root / "processed" / "reports" / "phase5_alerting_research_readiness.md"
    atomic_write_text(phase4, phase4_readiness_markdown() + "\n")
    atomic_write_text(phase5, phase5_readiness_markdown() + "\n")
    return {"phase4_readiness": str(phase4), "phase5_readiness": str(phase5)}
