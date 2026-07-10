from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from digital_asset_directory.subagent_evaluations import content_hash


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "examples/subagent-evaluations/logos-t475-and-dad-graph-v1"
AUTHORITY = (
    "This reconstructed candidate record describes one bounded execution attempt. "
    "It does not identify a person, rank a model family, or authorize agent routing, "
    "promotion, consolidation, specialization, or supersession."
)
DIMENSIONS = (
    "correctness",
    "scope_discipline",
    "evidence_traceability",
    "efficiency_compute_fit",
    "escalation_calibration",
)


def sha_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def role_profile(slug: str, role_id: str, mission: str, outputs: list[str]) -> dict[str, Any]:
    row = {
        "schema_version": "0.1.0",
        "role_profile_id": f"dad:role-profile:{slug}",
        "revision_id": f"dad:role-profile-revision:{slug}:v1",
        "role_id": role_id,
        "mission": mission,
        "expected_inputs": ["bounded task prompt", "authority and scope contract", "evidence slice"],
        "expected_outputs": outputs,
        "stop_conditions": [
            "requested evidence is absent",
            "scope or authority boundary is ambiguous",
            "a higher-risk decision requires escalation",
        ],
        "prompt_hash": sha_text(f"{slug}:v1:{mission}"),
        "tool_policy_hash": sha_text("read only unless explicitly assigned a disjoint write scope"),
        "supersedes_revision_id": None,
        "status": "candidate",
        "review_status": "generated_candidate",
        "authority_boundary": AUTHORITY,
    }
    row["revision_sha256"] = content_hash(row)
    return row


ROLE_PROFILES = [
    role_profile(
        "sol-architecture-owner",
        "architecture_owner",
        "Own high-risk architecture, invariants, root-cause analysis, and final escalation gates.",
        ["architecture verdict", "failure modes", "acceptance tests", "bounded next action"],
    ),
    role_profile(
        "terra-integration-specialist",
        "integration_specialist",
        "Map medium-risk contracts, extension points, parity evidence, and task dependencies.",
        ["integration map", "dependency contract", "validation plan", "risks and unknowns"],
    ),
    role_profile(
        "luna-bounded-worker",
        "bounded_worker",
        "Perform low-cost exact inventories, counts, hashes, and repeated bounded checks without interpretation creep.",
        ["exact inventory", "source pointers", "counts or identifiers", "explicit limitations"],
    ),
]
ROLE_BY_ID = {row["role_id"]: row for row in ROLE_PROFILES}


ATTEMPT_DEFS = [
    {
        "slug": "logos-t475-banach",
        "runtime_id": "019f4c7d-67f1-7050-b058-363d5f409ac6",
        "nickname": "Banach",
        "role": "architecture_owner",
        "model": "gpt-5.6-sol",
        "effort": "high",
        "task_id": "T475",
        "task_summary": "Independently review the first T475 shadow evidence bundle.",
        "repo": "lowelltwong-alt/logos-scripture-graph",
        "revision": "reconstructed:pre-repair-t475-shadow",
        "evidence": ["repo://logos-scripture-graph/.ai/context/agent_work/T475/sol_acceptance_report.md"],
    },
    {
        "slug": "logos-t475-chandrasekhar",
        "runtime_id": "019f4c7d-9c0c-7052-9682-1be2e322707d",
        "nickname": "Chandrasekhar",
        "role": "integration_specialist",
        "model": "gpt-5.6-terra",
        "effort": "medium",
        "task_id": "T475",
        "task_summary": "Review first T475 parity evidence and classify expected deltas.",
        "repo": "lowelltwong-alt/logos-scripture-graph",
        "revision": "reconstructed:pre-repair-t475-shadow",
        "evidence": ["repo://logos-scripture-graph/.ai/context/agent_work/T475/terra_parity_report.md"],
    },
    {
        "slug": "logos-t475-dalton",
        "runtime_id": "019f4c7d-eea2-7061-a9e9-9f9a630a8b6d",
        "nickname": "Dalton",
        "role": "bounded_worker",
        "model": "gpt-5.6-luna",
        "effort": "low",
        "task_id": "T475",
        "task_summary": "Verify first T475 arithmetic, repeatability, and no-text evidence.",
        "repo": "lowelltwong-alt/logos-scripture-graph",
        "revision": "reconstructed:pre-repair-t475-shadow",
        "evidence": ["repo://logos-scripture-graph/.ai/context/agent_work/T475/luna_trial_log.md"],
    },
    {
        "slug": "logos-t475-planck",
        "runtime_id": "019f4d0e-343f-7cd3-a95d-560f3d6a56fb",
        "nickname": "Planck",
        "role": "architecture_owner",
        "model": "gpt-5.6-sol",
        "effort": "high",
        "task_id": "T475",
        "task_summary": "Specify the minimal editorial-sidecar repair and invariants.",
        "repo": "lowelltwong-alt/logos-scripture-graph",
        "revision": "c5d8e43980422b088105b62dc8c7c42884226466",
        "evidence": ["repo://logos-scripture-graph/pipelines/ingest/usfm_importer.py@c5d8e439"],
    },
    {
        "slug": "logos-t475-beauvoir",
        "runtime_id": "019f4d0e-59a1-7a23-b358-f185f2761594",
        "nickname": "Beauvoir",
        "role": "integration_specialist",
        "model": "gpt-5.6-terra",
        "effort": "medium",
        "task_id": "T475-T480",
        "task_summary": "Map the dependency contracts from repaired T475 evidence through T480.",
        "repo": "lowelltwong-alt/logos-scripture-graph",
        "revision": "c5d8e43980422b088105b62dc8c7c42884226466",
        "evidence": ["repo://logos-scripture-graph/.ai/control/t475_usfm_shadow_delta_gate.yaml"],
    },
    {
        "slug": "logos-t475-raman",
        "runtime_id": "019f4d0e-9b85-71a3-abe0-292d038091d2",
        "nickname": "Raman",
        "role": "bounded_worker",
        "model": "gpt-5.6-luna",
        "effort": "low",
        "task_id": "T475",
        "task_summary": "Identify exact editorial heading footnotes lost by the first candidate.",
        "repo": "lowelltwong-alt/logos-scripture-graph",
        "revision": "c5d8e43980422b088105b62dc8c7c42884226466",
        "evidence": ["repo://logos-scripture-graph/.ai/context/agent_work/T475/delta_summary.json"],
    },
    {
        "slug": "dad-graph-hypatia",
        "runtime_id": "019f4d2b-95bb-7b20-928c-1391af77d8a6",
        "nickname": "Hypatia",
        "role": "architecture_owner",
        "model": "gpt-5.6-sol",
        "effort": "high",
        "task_id": "DAD-SUBAGENT-GRAPH-V1",
        "task_summary": "Red-team the attempt-first DAD subagent evaluation architecture.",
        "repo": "lowelltwong-alt/Digital-Assett-Directory",
        "revision": "0a288b8",
        "evidence": ["subagent://019f4d2b-95bb-7b20-928c-1391af77d8a6/final"],
    },
    {
        "slug": "dad-graph-averroes",
        "runtime_id": "019f4d2b-be71-7b81-84e7-139dce0c6ea2",
        "nickname": "Averroes",
        "role": "integration_specialist",
        "model": "gpt-5.6-terra",
        "effort": "medium",
        "task_id": "DAD-SUBAGENT-GRAPH-V1",
        "task_summary": "Locate narrow DAD schema, CLI, graph, pipeline, and validation extension points.",
        "repo": "lowelltwong-alt/Digital-Assett-Directory",
        "revision": "0a288b8",
        "evidence": ["subagent://019f4d2b-be71-7b81-84e7-139dce0c6ea2/final"],
    },
    {
        "slug": "dad-graph-dalton",
        "runtime_id": "019f4d2c-0c80-7c43-b868-6250909eb6f0",
        "nickname": "Dalton",
        "role": "bounded_worker",
        "model": "gpt-5.6-luna",
        "effort": "low",
        "task_id": "DAD-SUBAGENT-GRAPH-V1",
        "task_summary": "Inventory DAD attempt records and separate evaluable agent runs from incomplete archaeology.",
        "repo": "lowelltwong-alt/Digital-Assett-Directory",
        "revision": "0a288b8",
        "evidence": ["subagent://019f4d2c-0c80-7c43-b868-6250909eb6f0/final"],
    },
    {
        "slug": "dad-graph-lorentz",
        "runtime_id": "019f4d58-e282-7070-9a5b-cfa4ac2fb354",
        "nickname": "Lorentz",
        "role": "architecture_owner",
        "model": "gpt-5.6-sol",
        "effort": "high",
        "task_id": "DAD-SUBAGENT-GRAPH-V1-POST-REVIEW",
        "task_summary": "Run an adversarial post-implementation review of the subagent graph.",
        "repo": "lowelltwong-alt/Digital-Assett-Directory",
        "revision": "worktree:codex/subagent-evaluation-graph@pre-fix",
        "evidence": [],
    },
    {
        "slug": "dad-graph-lorentz-remediation-review",
        "runtime_id": "019f4d58-e282-7070-9a5b-cfa4ac2fb354",
        "nickname": "Lorentz remediation review",
        "role": "architecture_owner",
        "model": "gpt-5.6-sol",
        "effort": "high",
        "task_id": "DAD-SUBAGENT-GRAPH-V1-REVIEW-2",
        "task_summary": "Verify closure of the first seven P1 findings and two P2 findings.",
        "repo": "lowelltwong-alt/Digital-Assett-Directory",
        "revision": "worktree:codex/subagent-evaluation-graph@remediation-1",
        "parent_slug": "dad-graph-lorentz",
        "evidence": [],
    },
    {
        "slug": "dad-graph-lorentz-privacy-review",
        "runtime_id": "019f4d58-e282-7070-9a5b-cfa4ac2fb354",
        "nickname": "Lorentz privacy review",
        "role": "architecture_owner",
        "model": "gpt-5.6-sol",
        "effort": "high",
        "task_id": "DAD-SUBAGENT-GRAPH-V1-REVIEW-3",
        "task_summary": "Verify reviewer identity, privacy, ledger reconciliation, evidence grade, and navigation fixes.",
        "repo": "lowelltwong-alt/Digital-Assett-Directory",
        "revision": "worktree:codex/subagent-evaluation-graph@remediation-2",
        "parent_slug": "dad-graph-lorentz-remediation-review",
        "evidence": [],
    },
    {
        "slug": "dad-graph-lorentz-uri-regression-review",
        "runtime_id": "019f4d58-e282-7070-9a5b-cfa4ac2fb354",
        "nickname": "Lorentz URI regression review",
        "role": "architecture_owner",
        "model": "gpt-5.6-sol",
        "effort": "high",
        "task_id": "DAD-SUBAGENT-GRAPH-V1-REVIEW-4",
        "task_summary": "Verify generic absolute-path rejection without breaking safe source URIs.",
        "repo": "lowelltwong-alt/Digital-Assett-Directory",
        "revision": "worktree:codex/subagent-evaluation-graph@privacy-fix-1",
        "parent_slug": "dad-graph-lorentz-privacy-review",
        "evidence": [],
    },
    {
        "slug": "dad-graph-lorentz-final-closure",
        "runtime_id": "019f4d58-e282-7070-9a5b-cfa4ac2fb354",
        "nickname": "Lorentz final closure",
        "role": "architecture_owner",
        "model": "gpt-5.6-sol",
        "effort": "high",
        "task_id": "DAD-SUBAGENT-GRAPH-V1-REVIEW-5",
        "task_summary": "Run the final absolute-path and source-URI closure probe.",
        "repo": "lowelltwong-alt/Digital-Assett-Directory",
        "revision": "worktree:codex/subagent-evaluation-graph@approved",
        "parent_slug": "dad-graph-lorentz-uri-regression-review",
        "evidence": [],
    },
    {
        "slug": "dad-graph-claude-opus-timeout",
        "runtime_id": "claude-cli-20260710-opus-audit",
        "nickname": "Claude Opus audit",
        "role": "architecture_owner",
        "provider": "anthropic",
        "model": "claude-opus",
        "effort": "high",
        "task_id": "DAD-SUBAGENT-GRAPH-V1-INDEPENDENT-AUDIT",
        "task_summary": "Independently audit the subagent graph implementation.",
        "repo": "lowelltwong-alt/Digital-Assett-Directory",
        "revision": "worktree:codex/subagent-evaluation-graph@pre-fix",
        "terminal_status": "failed",
        "evidence": [],
    },
    {
        "slug": "dad-graph-claude-sonnet-limit",
        "runtime_id": "claude-cli-20260710-sonnet-audit",
        "nickname": "Claude Sonnet audit",
        "role": "architecture_owner",
        "provider": "anthropic",
        "model": "claude-sonnet",
        "effort": "medium",
        "task_id": "DAD-SUBAGENT-GRAPH-V1-INDEPENDENT-AUDIT",
        "task_summary": "Run a bounded independent audit after the Opus timeout.",
        "repo": "lowelltwong-alt/Digital-Assett-Directory",
        "revision": "worktree:codex/subagent-evaluation-graph@pre-fix",
        "terminal_status": "failed",
        "evidence": [],
    },
]


def make_attempt(definition: dict[str, Any], sequence: int) -> dict[str, Any]:
    role = ROLE_BY_ID[definition["role"]]
    evidence_rel = Path(
        "examples/subagent-evaluations/logos-t475-and-dad-graph-v1/evidence"
    ) / f"{definition['slug']}.json"
    evidence_path = ROOT / evidence_rel
    return {
        "schema_version": "0.1.0",
        "attempt_id": f"dad:subagent-attempt:{definition['slug']}",
        "runtime_attempt_id": definition["runtime_id"],
        "parent_session_id": None,
        "parent_attempt_id": (
            f"dad:subagent-attempt:{definition['parent_slug']}"
            if definition.get("parent_slug")
            else None
        ),
        "task_id": definition["task_id"],
        "task_summary": definition["task_summary"],
        "invocation_sequence": sequence,
        "source_repository": definition["repo"],
        "repo_revision": definition["revision"],
        "worktree_attempt_id": None,
        "role_profile_id": role["role_profile_id"],
        "role_revision_id": role["revision_id"],
        "display_label": definition["nickname"],
        "runtime_claims": {
            "provider": definition.get("provider", "openai"),
            "model_id": definition["model"],
            "model_family": definition["model"],
            "reasoning_effort": definition["effort"],
            "verification_status": "reported",
        },
        "input_hashes": {"role_revision": role["revision_sha256"], "prompt": "unavailable"},
        "artifact_refs": [
            {
                "ref": f"source://{evidence_rel.as_posix()}",
                "sha256": f"sha256:{hashlib.sha256(evidence_path.read_bytes()).hexdigest()}",
            }
        ],
        "started_at": None,
        "ended_at": None,
        "terminal_status": definition.get("terminal_status", "completed"),
        "capture_provenance": "Reconstructed from the parent Codex task record and terminal subagent report.",
        "capture_completeness": {
            "status": "partial_reconstructed",
            "missing_fields": ["started_at", "ended_at", "exact_invocation_prompt_hash"],
        },
        "sensitivity": "internal",
        "authority_boundary": AUTHORITY,
    }


EVAL_DEFS = {
    "logos-t475-banach": {
        "scores": [96, 97, 95, 90, 96], "confidence": 0.75, "outcome": "successful",
        "capabilities": ["architecture_reasoning", "root_cause_analysis", "governance_authority_safety", "implementation_review"],
        "strengths": ["Identified the typed editorial-footnote loss as a P1 and the missing fixture as a P2."],
        "failures": [],
        "improve": ["Include exact repair acceptance arithmetic in the first report to shorten integration."],
    },
    "logos-t475-chandrasekhar": {
        "scores": [55, 90, 80, 88, 45], "confidence": 0.78, "outcome": "mixed", "gate_failed": True,
        "capabilities": ["contract_and_roadmap_mapping", "implementation_review", "escalation_judgment"],
        "strengths": ["Produced useful parity structure and remained within the review scope."],
        "failures": ["Initially classified the loss of three typed editorial footnotes as expected and was overruled by the architecture review."],
        "improve": ["Classify deltas by typed information loss before accepting count reductions as expected parity."],
    },
    "logos-t475-dalton": {
        "scores": [94, 99, 93, 98, 85], "confidence": 0.70, "outcome": "successful",
        "capabilities": ["bounded_evidence_inventory", "validation_design"],
        "strengths": ["Verified arithmetic, repeatability, and no-text constraints at low cost."],
        "failures": [],
        "improve": ["Flag unexplained typed-row removals for escalation even when arithmetic is internally consistent."],
    },
    "logos-t475-planck": {
        "scores": [96, 98, 95, 91, 97], "confidence": 0.78, "outcome": "successful",
        "capabilities": ["architecture_reasoning", "root_cause_analysis", "validation_design", "governance_authority_safety"],
        "strengths": ["Specified the minimal editorial-only sidecar route and protected verse text, counters, and word-token invariants."],
        "failures": [],
        "improve": ["Add a concise migration-state table when the repair changes generated candidate counts."],
    },
    "logos-t475-beauvoir": {
        "scores": [92, 97, 93, 94, 91], "confidence": 0.75, "outcome": "successful",
        "capabilities": ["contract_and_roadmap_mapping", "validation_design", "escalation_judgment"],
        "strengths": ["Mapped T476-T480 dependencies and preserved the independent-audit and owner gates."],
        "failures": [],
        "improve": ["Pair each future task boundary with the exact source artifact hash it consumes."],
    },
    "logos-t475-raman": {
        "scores": [97, 99, 96, 99, 90], "confidence": 0.80, "outcome": "successful",
        "capabilities": ["bounded_evidence_inventory", "validation_design"],
        "strengths": ["Found all three lost footnotes with exact IDs, references, and unscoped metadata."],
        "failures": [],
        "improve": ["Include source-line values in the compact final table whenever available."],
    },
    "dad-graph-hypatia": {
        "scores": [97, 98, 97, 92, 98], "confidence": 0.85, "outcome": "successful",
        "capabilities": ["architecture_reasoning", "root_cause_analysis", "governance_authority_safety", "validation_design"],
        "strengths": ["Separated role revisions, attempts, evaluations, model claims, and human decisions; identified leaderboard and identity-collapse hazards."],
        "failures": [],
        "improve": ["Distinguish mandatory V1 controls from later maturity controls to make implementation sequencing even clearer."],
    },
    "dad-graph-averroes": {
        "scores": [94, 98, 96, 96, 93], "confidence": 0.82, "outcome": "successful",
        "capabilities": ["contract_and_roadmap_mapping", "implementation_review", "validation_design"],
        "strengths": ["Located the exact graph surface, schema, CLI, transport, and test seams without proposing lesson-graph widening."],
        "failures": [],
        "improve": ["Include the transport data-plane registry seam in the first path summary."],
    },
    "dad-graph-dalton": {
        "scores": [96, 99, 97, 99, 92], "confidence": 0.82, "outcome": "successful",
        "capabilities": ["bounded_evidence_inventory", "governance_authority_safety"],
        "strengths": ["Counted 378 valid archaeological attempts and correctly refused to treat any as reviewed subagent evaluations."],
        "failures": [],
        "improve": ["Emit a deterministic inventory digest so future scans can detect changes without rescanning all rows."],
    },
    "dad-graph-lorentz": {
        "scores": [99, 99, 98, 94, 99], "confidence": 0.90, "outcome": "successful",
        "capabilities": ["architecture_reasoning", "root_cause_analysis", "implementation_review", "validation_design", "governance_authority_safety"],
        "strengths": ["Rejected the first implementation with seven reproducible P1 integrity findings and two P2 integration findings."],
        "failures": [],
        "improve": ["Separate must-fix V1 probes from longer-term maturity recommendations in the opening verdict."],
    },
    "dad-graph-lorentz-remediation-review": {
        "scores": [99, 99, 99, 95, 99], "confidence": 0.90, "outcome": "successful",
        "capabilities": ["architecture_reasoning", "root_cause_analysis", "implementation_review", "validation_design", "governance_authority_safety"],
        "strengths": ["Verified five prior findings closed and found three remaining P1 integrity gaps plus two P2 transparency gaps."],
        "failures": [],
        "improve": ["Run the exact ledger reconciliation probe before reporting code-level rubric replay as closed."],
    },
    "dad-graph-lorentz-privacy-review": {
        "scores": [99, 99, 99, 97, 99], "confidence": 0.90, "outcome": "successful",
        "capabilities": ["architecture_reasoning", "implementation_review", "validation_design", "governance_authority_safety"],
        "strengths": ["Confirmed reviewer linkage and observational-rating fixes, then found the remaining generic POSIX absolute-path bypass."],
        "failures": [],
        "improve": ["Include URI negative controls in the first generic path-regex probe."],
    },
    "dad-graph-lorentz-uri-regression-review": {
        "scores": [99, 99, 99, 98, 99], "confidence": 0.90, "outcome": "successful",
        "capabilities": ["implementation_review", "validation_design", "governance_authority_safety"],
        "strengths": ["Caught that the first generic path regex misclassified source URIs as drive paths."],
        "failures": [],
        "improve": ["Test boundary-sensitive regex branches with minimal direct strings before the full suite."],
    },
    "dad-graph-lorentz-final-closure": {
        "scores": [99, 99, 99, 99, 99], "confidence": 0.90, "outcome": "successful",
        "capabilities": ["implementation_review", "validation_design", "governance_authority_safety"],
        "strengths": ["Returned APPROVE after the final path/URI probe and focused suite passed."],
        "failures": [],
        "improve": ["Preserve the compact final closure verdict alongside the earlier detailed rejection trail."],
    },
    "dad-graph-claude-opus-timeout": {
        "scores": None, "confidence": 0.0, "outcome": "failed",
        "capabilities": ["implementation_review"],
        "strengths": [],
        "failures": ["Produced no verdict before the 15-minute execution ceiling."],
        "improve": ["Use a bounded diff packet and run an availability preflight before assigning the full audit."],
    },
    "dad-graph-claude-sonnet-limit": {
        "scores": None, "confidence": 0.0, "outcome": "failed",
        "capabilities": ["implementation_review"],
        "strengths": [],
        "failures": ["Could not start because the Claude session limit had been reached."],
        "improve": ["Check provider session capacity before routing an independent gate to the CLI."],
    },
}


def make_evaluation(attempt: dict[str, Any], definition: dict[str, Any], rubric: dict[str, Any], rubric_hash: str) -> dict[str, Any]:
    evidence_refs = [row["ref"] for row in attempt["artifact_refs"]]
    is_rated = definition["scores"] is not None
    if is_rated:
        dimensions = {
            dimension: {
                "status": "scored",
                "score": score,
                "evidence_refs": evidence_refs,
                "rationale": f"Parent review observed {dimension.replace('_', ' ')} in the captured bounded report.",
            }
            for dimension, score in zip(DIMENSIONS, definition["scores"], strict=True)
        }
        score = round(
            sum(
                dimensions[row["id"]]["score"] * row["weight"]
                for row in rubric["dimensions"]
            ),
            2,
        )
    else:
        dimensions = {
            dimension: {
                "status": "insufficient_evidence",
                "score": None,
                "evidence_refs": [],
                "rationale": "The attempted audit produced no review verdict to score.",
            }
            for dimension in DIMENSIONS
        }
        score = None
    capabilities = [
        {
            "capability_id": capability,
            "status": "scored" if is_rated else "insufficient_evidence",
            "rating": score,
            "confidence": definition["confidence"],
            "evidence_refs": evidence_refs if is_rated else [],
            "counterevidence_refs": evidence_refs if definition.get("failures") and is_rated else [],
            "rationale": (
                "Attempt-scoped candidate observation; no role-profile or model-family generalization."
                if is_rated
                else "No terminal review evidence was produced."
            ),
        }
        for capability in definition["capabilities"]
    ]
    evaluation = {
        "schema_version": "0.1.0",
        "evaluation_id": f"dad:subagent-evaluation:{attempt['attempt_id'].split(':')[-1]}",
        "attempt_id": attempt["attempt_id"],
        "attempt_snapshot_sha256": content_hash(attempt),
        "evaluator": "codex-parent-integrator",
        "evaluator_attempt_id": None,
        "evaluator_identity": {
            "actor_id": "codex-parent-integrator",
            "actor_type": "external_agent",
            "verification_status": "unverified",
            "relationship_to_attempt": "parent",
            "evidence_ref": None,
        },
        "evaluator_independence": "parent_review",
        "rubric_id": rubric["methodology_id"],
        "rubric_version": rubric["methodology_version"],
        "rubric_sha256": rubric_hash,
        "dimension_results": dimensions,
        "capability_results": capabilities,
        "aggregate_result": {
            "status": "parent_observational_rating" if is_rated else "insufficient_evidence",
            "score": score,
            "gate_failed": bool(definition.get("gate_failed", False)),
            "confidence": definition["confidence"],
        },
        "outcome": definition["outcome"],
        "strengths": definition["strengths"],
        "failures": definition["failures"],
        "improvement_recommendations": definition["improve"],
        "limitations": [
            "Parent review is not independent evidence.",
            "Evidence is a committed parent-captured summary, not a provider-signed terminal transcript.",
            "Attempt timing and the exact invocation prompt hash were unavailable during reconstruction.",
            "This score describes one bounded attempt only.",
        ],
        "evidence_bundle_sha256": "",
        "evidence_grade": (
            "parent_reconstructed_summary" if is_rated else "execution_failure_log"
        ),
        "evaluated_at": "2026-07-10T18:00:00Z",
        "review_status": "generated_candidate",
        "authority_boundary": AUTHORITY,
    }
    evaluation["evidence_bundle_sha256"] = content_hash(
        {
            key: evaluation[key]
            for key in (
                "dimension_results", "capability_results", "strengths", "failures",
                "improvement_recommendations", "limitations",
                "evidence_grade", "evaluator_identity",
            )
        }
    )
    return evaluation


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    rubric_path = ROOT / "registry/subagent-evaluation-methodologies/0.1.0.json"
    rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
    rubric_hash = f"sha256:{hashlib.sha256(rubric_path.read_bytes()).hexdigest()}"
    evidence_dir = args.out / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for definition in ATTEMPT_DEFS:
        evaluation = EVAL_DEFS[definition["slug"]]
        evidence_payload = {
            "schema_version": "dad.subagent.parent-captured-evidence.v1",
            "attempt_slug": definition["slug"],
            "runtime_attempt_id": definition["runtime_id"],
            "capture_type": (
                "tool_execution_failure"
                if definition.get("terminal_status") == "failed"
                else "parent_reconstructed_terminal_summary"
            ),
            "task_id": definition["task_id"],
            "observed_strengths": evaluation["strengths"],
            "observed_failures": evaluation["failures"],
            "improvement_recommendations": evaluation["improve"],
            "limitations": [
                "This is a parent-captured bounded summary, not hidden reasoning or a full source transcript.",
                "Exact start/end time and invocation prompt hash were unavailable.",
            ],
            "authority_boundary": AUTHORITY,
        }
        (evidence_dir / f"{definition['slug']}.json").write_text(
            json.dumps(evidence_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    attempts = [make_attempt(row, number) for number, row in enumerate(ATTEMPT_DEFS, start=1)]
    evaluations = [
        make_evaluation(attempt, EVAL_DEFS[definition["slug"]], rubric, rubric_hash)
        for attempt, definition in zip(attempts, ATTEMPT_DEFS, strict=True)
    ]
    write_jsonl(args.out / "role-profile-revisions.jsonl", ROLE_PROFILES)
    write_jsonl(args.out / "execution-attempts.jsonl", attempts)
    write_jsonl(args.out / "attempt-evaluations.jsonl", evaluations)
    write_jsonl(
        args.out / "unrated-inventory.jsonl",
        [
            {
                "inventory_id": "dad:subagent-unrated-inventory:legacy-worktree-attempts-20260710",
                "source": "processed/learning/worktree_attempts.jsonl",
                "record_count": 378,
                "agent_execution_identity_usable": False,
                "rating_status": "insufficient_evidence",
                "reason": "Path-derived archaeological attempts lack invocation, role revision, model-claim verification, terminal artifact, and reviewed evaluation evidence.",
                "observed_at": "2026-07-10T18:00:00Z",
                "sensitivity": "internal",
                "authority_boundary": AUTHORITY,
            }
        ],
    )
    summary_lines = [
        "# Logos T475 And DAD Graph V1 Attempt Reviews",
        "",
        "These are parent-reviewed, attempt-scoped observational ratings. They are not evidence-eligible profile, model, or role rankings.",
        "",
        "| Attempt | Role | Outcome | Observational score | Confidence | Improvement |",
        "|---|---|---:|---:|---:|---|",
    ]
    for attempt, evaluation in zip(attempts, evaluations, strict=True):
        improvement = evaluation["improvement_recommendations"][0].replace("|", "/")
        score = evaluation["aggregate_result"]["score"]
        score_text = f"{score:.2f}" if score is not None else "insufficient evidence"
        summary_lines.append(
            f"| {attempt['display_label']} (`{attempt['task_id']}`) | "
            f"{attempt['role_profile_id'].split(':')[-1]} | {evaluation['outcome']} | "
            f"{score_text} | "
            f"{evaluation['aggregate_result']['confidence']:.2f} | {improvement} |"
        )
    summary_lines.extend(
        [
            "",
            "The two `Dalton` rows are distinct execution attempts; the nickname is not an identity key.",
            "The five `Lorentz` review rows preserve successive reject/remediate/approve invocations under one runtime agent id.",
            "The older 378 DAD worktree-attempt rows remain unrated because they are path archaeology, not invocation records.",
            "No profile-level score or keep/combine/promote/supersede decision is authorized by this packet.",
            "",
        ]
    )
    (args.out / "review-summary.md").write_text("\n".join(summary_lines), encoding="utf-8")
    print(json.dumps({"out": str(args.out), "attempts": len(attempts), "evaluations": len(evaluations)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
