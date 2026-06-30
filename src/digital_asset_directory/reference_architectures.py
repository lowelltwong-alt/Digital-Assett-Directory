from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

from .ids import stable_id
from .models import AssetRecord, EdgeRecord, ReferenceArchitectureRecord, ScanCycleEventRecord
from .repo_buildout import build_repo_groups
from .utils import append_jsonl, atomic_write_text, json_dumps, utc_now, write_jsonl

METHODOLOGY_VERSION = "reference-architecture-recognition-v0.1"
AUTHORITY_BOUNDARY = (
    "Generated reference-architecture candidates only. This command reads existing catalog "
    "metadata and optional generated graph evidence when explicitly requested; it does not "
    "rescan, read source file contents, call GitHub, call models, mutate source "
    "repositories, promote candidates to truth, or change value scores."
)
REFERENCE_SCORE_FORMULA = (
    "reference_score = 100 * (0.22*completeness + 0.20*usefulness + "
    "0.18*reusability + 0.15*composition + 0.15*validation_readiness + "
    "0.10*novelty) * (1 - 0.35*risk); failed required gates cap score at 25"
)

ROLE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "agent_navigation": {
        "label": "AI/navigation front door",
        "terms": [
            "agents.md",
            "claude.md",
            "ai_front_door",
            "ai_table_of_contents",
            "start_here",
            "front door",
            "navigation",
        ],
        "asset_types": set(),
    },
    "architecture_docs": {
        "label": "architecture/design docs",
        "terms": ["architecture", "design", "data_flow", "system", "adr", "decision"],
        "asset_types": set(),
    },
    "schemas_contracts": {
        "label": "schemas/contracts/registries",
        "terms": ["schema", "contract", "registry", "ontology", "taxonomy", "data_dictionary"],
        "asset_types": {"schema", "registry"},
    },
    "rules_governance": {
        "label": "rules/governance/gates",
        "terms": [
            "governance",
            "policy",
            "rule",
            "authority",
            "gate",
            "roadmap",
            "security",
            "privacy",
        ],
        "asset_types": set(),
    },
    "validators_tests": {
        "label": "validators/tests/quality checks",
        "terms": ["test", "validate", "validator", "pytest", "ruff", ".github/workflows", "ci"],
        "asset_types": {"test"},
    },
    "workflow_docs": {
        "label": "workflows/runbooks/processes",
        "terms": ["workflow", "process", "pipeline", "runbook", "operations", "handoff"],
        "asset_types": {"workflow"},
    },
    "templates_scaffolds": {
        "label": "templates/scaffolds",
        "terms": ["template", "scaffold", "cookiecutter", "new_repo", "bootstrap"],
        "asset_types": {"template"},
    },
    "learning_loops": {
        "label": "learning/pay-forward loops",
        "terms": ["lesson", "learning", "postflight", "preflight", "midflight", "pay-forward"],
        "asset_types": {"lesson", "handoff"},
    },
    "dataflow_normalization": {
        "label": "dataflow/normalization maps",
        "terms": ["data_flow", "normalization", "etl", "transform", "mapping", "canonical"],
        "asset_types": {"data_pipeline"},
    },
    "quality_eval": {
        "label": "evaluation/calibration/QA",
        "terms": ["eval", "scorecard", "calibration", "qa", "quality", "review"],
        "asset_types": set(),
    },
    "public_safe_boundary": {
        "label": "public-safe/private-source boundary",
        "terms": ["public_safe", "privacy", "redact", "secret", "source_scope", "boundary"],
        "asset_types": set(),
    },
}

CORE_REFERENCE_ROLES = {
    "agent_navigation",
    "architecture_docs",
    "schemas_contracts",
    "rules_governance",
    "validators_tests",
    "workflow_docs",
    "learning_loops",
}
HIGH_SIGNAL_ROLES = {
    "agent_navigation",
    "architecture_docs",
    "schemas_contracts",
    "rules_governance",
    "validators_tests",
    "workflow_docs",
    "learning_loops",
    "templates_scaffolds",
}
PRIVATE_PATH_TERMS = {
    "client",
    "secret",
    "credential",
    "token",
    "password",
    "private",
    "confidential",
    "attorney",
    "bar results",
    "downloads",
}


def _normalized(value: str) -> str:
    return value.replace("\\", "/").strip().strip("/").lower()


def _repo_relative_path(asset: AssetRecord) -> str:
    raw_relative = asset.metadata.get("relative_path")
    logical_path = (
        _normalized(raw_relative)
        if isinstance(raw_relative, str) and raw_relative.strip()
        else _normalized(asset.logical_path)
    )
    repository_root = asset.metadata.get("repository_root")
    if isinstance(repository_root, str) and repository_root.strip():
        root = _normalized(repository_root)
        if logical_path == root:
            return PurePosixPath(logical_path).name
        if logical_path.startswith(f"{root}/"):
            return logical_path[len(root) + 1 :]
    return logical_path


def _asset_haystack(asset: AssetRecord) -> str:
    return " ".join(
        [
            asset.asset_type,
            asset.title,
            _repo_relative_path(asset),
            " ".join(asset.tags),
            " ".join(asset.capabilities),
            " ".join(asset.needs),
        ]
    ).lower()


def classify_architecture_component_roles(asset: AssetRecord) -> list[str]:
    haystack = _asset_haystack(asset)
    roles: list[str] = []
    for role, definition in ROLE_DEFINITIONS.items():
        terms = definition["terms"]
        asset_types = definition["asset_types"]
        if asset.asset_type in asset_types or any(term in haystack for term in terms):
            roles.append(role)
    return sorted(set(roles))


def reference_architecture_score(
    components: dict[str, float],
    risk_score: float,
    gates: dict[str, bool],
) -> float:
    weights = {
        "completeness_score": 0.22,
        "usefulness_score": 0.20,
        "reusability_score": 0.18,
        "composition_score": 0.15,
        "validation_readiness": 0.15,
        "novelty_score": 0.10,
    }
    raw = sum(weights[key] * _clamp01(components.get(key, 0.0)) for key in weights)
    adjusted = 100.0 * raw * (1.0 - 0.35 * _clamp01(risk_score))
    score = round(max(0.0, min(100.0, adjusted)), 2)
    if not all(gates.values()):
        score = min(score, 25.0)
    return score


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _repo_label(repo_key: str, assets: list[AssetRecord]) -> str:
    repo_asset = next((asset for asset in assets if asset.asset_type == "repository"), None)
    if repo_asset:
        return repo_asset.title
    parts = [part for part in PurePosixPath(repo_key).parts if part]
    return parts[-1] if parts else repo_key


def _component_roles_for_group(
    assets: list[AssetRecord],
    *,
    component_limit: int,
) -> dict[str, list[AssetRecord]]:
    role_assets: dict[str, list[AssetRecord]] = defaultdict(list)
    for asset in assets:
        for role in classify_architecture_component_roles(asset):
            role_assets[role].append(asset)
    limited: dict[str, list[AssetRecord]] = {}
    selected_ids: set[str] = set()
    for role in sorted(role_assets):
        ranked = sorted(
            role_assets[role],
            key=lambda item: (-float(item.value_score), item.logical_path, item.asset_id),
        )
        limited_role: list[AssetRecord] = []
        for asset in ranked:
            if len(limited_role) >= 3:
                break
            if len(selected_ids) >= component_limit and asset.asset_id not in selected_ids:
                continue
            limited_role.append(asset)
            selected_ids.add(asset.asset_id)
        if limited_role:
            limited[role] = limited_role
    return limited


def _architecture_type(roles: set[str]) -> str:
    if {"rules_governance", "schemas_contracts", "validators_tests"}.issubset(roles):
        return "governance_control_plane"
    if {"schemas_contracts", "validators_tests"}.issubset(roles):
        return "schema_contract_architecture"
    if {"workflow_docs", "learning_loops"}.issubset(roles):
        return "learning_loop_architecture"
    if {"workflow_docs", "dataflow_normalization"}.issubset(roles):
        return "dataflow_normalization_architecture"
    if {"quality_eval", "validators_tests"}.issubset(roles):
        return "evaluation_quality_architecture"
    if {"agent_navigation", "rules_governance"}.issubset(roles):
        return "agent_skill_architecture"
    if "templates_scaffolds" in roles:
        return "template_scaffold_architecture"
    if "public_safe_boundary" in roles:
        return "public_safe_private_source_architecture"
    if len(roles) >= 3:
        return "repo_system_architecture"
    if "workflow_docs" in roles:
        return "workflow_reference_architecture"
    return "unknown_reference_architecture"


def _detected_patterns(roles: set[str]) -> list[str]:
    patterns = []
    if {"agent_navigation", "architecture_docs"}.issubset(roles):
        patterns.append("front-door-routes-to-architecture")
    if {"schemas_contracts", "validators_tests"}.issubset(roles):
        patterns.append("contracts-backed-by-validation")
    if {"rules_governance", "learning_loops"}.issubset(roles):
        patterns.append("governance-feeds-learning-loop")
    if {"workflow_docs", "schemas_contracts"}.issubset(roles):
        patterns.append("workflow-backed-by-structured-contracts")
    if {"templates_scaffolds", "rules_governance"}.issubset(roles):
        patterns.append("template-with-governance-dependencies")
    if {"public_safe_boundary", "schemas_contracts"}.issubset(roles):
        patterns.append("public-safe-boundary-with-contracts")
    if not patterns:
        patterns.append("multi-role-architecture-candidate")
    return patterns


def _composition_summary(roles: set[str]) -> str:
    parts = []
    if "agent_navigation" in roles:
        parts.append("AI navigation routes future agents to the right surfaces")
    if "architecture_docs" in roles:
        parts.append("architecture/design docs explain the system shape")
    if "schemas_contracts" in roles:
        parts.append("schemas and registries define contracts")
    if "rules_governance" in roles:
        parts.append("governance rules define authority and gates")
    if "validators_tests" in roles:
        parts.append("validators/tests check the contracts")
    if "workflow_docs" in roles:
        parts.append("workflow docs explain operational order")
    if "learning_loops" in roles:
        parts.append("learning-loop artifacts feed future improvement")
    if "templates_scaffolds" in roles:
        parts.append("templates/scaffolds make reuse concrete")
    if not parts:
        return "Catalog metadata suggests a reusable architecture shape, but the exact composition needs human review."
    return "; ".join(parts) + "."


def _why_good(roles: set[str], component_count: int) -> list[str]:
    reasons = [f"Detected {component_count} component assets across {len(roles)} architecture roles."]
    if {"schemas_contracts", "validators_tests"}.issubset(roles):
        reasons.append("It pairs declared contracts with validation, which makes reuse safer.")
    if {"agent_navigation", "rules_governance"}.issubset(roles):
        reasons.append("It gives future agents both an entrypoint and authority boundaries.")
    if {"workflow_docs", "learning_loops"}.issubset(roles):
        reasons.append("It records both how work should happen and how feedback should return.")
    if "templates_scaffolds" in roles:
        reasons.append("It has a concrete scaffold/template surface that can carry the architecture forward.")
    return reasons


def _missing_pieces(roles: set[str]) -> list[str]:
    missing = []
    expected = {
        "agent_navigation": "AI front door or table of contents",
        "architecture_docs": "architecture/design explanation",
        "schemas_contracts": "schemas, registries, or explicit contracts",
        "rules_governance": "authority, privacy, or human-gate rules",
        "validators_tests": "tests, validators, or CI checks",
        "workflow_docs": "runbook/workflow sequence",
        "learning_loops": "preflight/postflight/pay-forward learning loop",
        "templates_scaffolds": "template or scaffold for reuse",
    }
    for role, label in expected.items():
        if role not in roles:
            missing.append(label)
    return missing[:5]


def _reuse_guidance(roles: set[str]) -> list[str]:
    guidance = [
        "Reuse the architecture shape and dependency order, not source-owned facts or private data.",
        "Treat this as a candidate reference until a human verifies the component roles and validation commands.",
    ]
    if "schemas_contracts" in roles:
        guidance.append("When adapting, copy the contract idea only after checking schema semantics and authority.")
    if "templates_scaffolds" in roles:
        guidance.append("If promoted later, template dependencies must be recorded both forward and reverse.")
    if "learning_loops" in roles:
        guidance.append("Keep before/during/after/review learning events as data-only feedback.")
    return guidance


def _validation_plan(roles: set[str]) -> list[str]:
    plan = ["$env:PYTHONPATH='src'; python -m digital_asset_directory.cli validate"]
    if "validators_tests" in roles:
        plan.insert(0, "run the repo-local validator/test command for the candidate architecture")
    if "schemas_contracts" in roles:
        plan.append("validate records against the registered JSON Schemas before reuse")
    if "templates_scaffolds" in roles:
        plan.append("run template dependency validation before generating or upgrading templates")
    return plan


def _human_gates(roles: set[str], privacy_gate: bool) -> list[str]:
    gates = ["human review before promoting any candidate reference architecture"]
    if not privacy_gate or "public_safe_boundary" in roles:
        gates.append("privacy/public-release review before quoting or exporting details")
    if "templates_scaffolds" in roles:
        gates.append("human approval before updating reusable templates or downstream repos")
    return gates


def _sensitive_path(asset: AssetRecord) -> bool:
    text = _normalized(asset.logical_path)
    return asset.sensitivity == "restricted" or any(term in text for term in PRIVATE_PATH_TERMS)


def _scores_for_group(
    role_assets: dict[str, list[AssetRecord]],
    role_frequency: Counter[str],
    group_count: int,
    internal_edge_count: int,
) -> dict[str, float]:
    roles = set(role_assets)
    role_count = len(roles)
    component_count = len({asset.asset_id for assets in role_assets.values() for asset in assets})
    high_signal_count = len(roles & HIGH_SIGNAL_ROLES)
    rare_roles = sum(1 for role in roles if role_frequency[role] <= max(1, group_count // 4))
    completeness = _clamp01(role_count / 8.0)
    usefulness = _clamp01((high_signal_count / 8.0) + (0.15 if "validators_tests" in roles else 0.0))
    reusability = _clamp01(
        0.20
        + (0.20 if "architecture_docs" in roles else 0.0)
        + (0.20 if "schemas_contracts" in roles else 0.0)
        + (0.20 if "templates_scaffolds" in roles else 0.0)
        + (0.20 if "agent_navigation" in roles else 0.0)
    )
    composition = _clamp01(0.20 + min(0.45, internal_edge_count * 0.05) + role_count * 0.04)
    validation = _clamp01(
        (0.30 if "validators_tests" in roles else 0.0)
        + (0.25 if "schemas_contracts" in roles else 0.0)
        + (0.15 if "rules_governance" in roles else 0.0)
        + (0.10 if "quality_eval" in roles else 0.0)
        + min(0.20, component_count * 0.015)
    )
    novelty = _clamp01(0.25 + rare_roles * 0.08 + role_count * 0.035)
    risk = _clamp01(
        0.10
        + (0.18 if "validators_tests" not in roles else 0.0)
        + (0.12 if role_count < 4 else 0.0)
        + (0.12 if component_count < 5 else 0.0)
    )
    return {
        "completeness_score": round(completeness, 4),
        "usefulness_score": round(usefulness, 4),
        "reusability_score": round(reusability, 4),
        "composition_score": round(composition, 4),
        "validation_readiness": round(validation, 4),
        "novelty_score": round(novelty, 4),
        "risk_score": round(risk, 4),
    }


def build_reference_architecture_records(
    assets: list[AssetRecord],
    edges: list[EdgeRecord],
    *,
    scan_id: str = "catalog-without-scan",
    limit: int = 50,
    component_limit: int = 12,
    generated_at: str | None = None,
) -> list[ReferenceArchitectureRecord]:
    generated = generated_at or utc_now()
    edge_input_status = (
        "catalog candidate edges supplied to builder"
        if edges
        else "catalog candidate edges not loaded for bounded v1 runtime"
    )
    repo_groups = build_repo_groups(assets)
    role_groups: dict[str, dict[str, list[AssetRecord]]] = {}
    for repo_key, group_assets in repo_groups.items():
        role_assets = _component_roles_for_group(group_assets, component_limit=component_limit)
        if role_assets:
            role_groups[repo_key] = role_assets

    role_frequency: Counter[str] = Counter()
    for role_assets in role_groups.values():
        role_frequency.update(role_assets.keys())
    group_count = max(1, len(role_groups))
    edge_pairs = {
        tuple(sorted((edge.source_asset_id, edge.target_asset_id)))
        for edge in edges
        if edge.source_asset_id != edge.target_asset_id
    }
    records: list[ReferenceArchitectureRecord] = []
    for repo_key, role_assets in sorted(role_groups.items()):
        roles = set(role_assets)
        component_asset_ids = sorted(
            {asset.asset_id for assets_for_role in role_assets.values() for asset in assets_for_role}
        )
        if len(roles) < 2 or len(component_asset_ids) < 3:
            continue
        assets_by_id = {
            asset.asset_id: asset
            for assets_for_role in role_assets.values()
            for asset in assets_for_role
        }
        internal_edges = sum(
            1
            for left in component_asset_ids
            for right in component_asset_ids
            if left < right and tuple(sorted((left, right))) in edge_pairs
        )
        privacy_gate = not any(_sensitive_path(asset) for asset in assets_by_id.values())
        gates = {
            "evidence_gate": len(component_asset_ids) >= 3 and len(roles) >= 2,
            "source_boundary_gate": True,
            "privacy_gate": privacy_gate,
            "no_content_read_gate": True,
            "no_external_call_gate": True,
            "candidate_only_gate": True,
        }
        gate_failures = [key for key, passed in gates.items() if not passed]
        score_components = _scores_for_group(role_assets, role_frequency, group_count, internal_edges)
        if not privacy_gate:
            score_components["risk_score"] = _clamp01(score_components["risk_score"] + 0.20)
        reference_score = reference_architecture_score(
            score_components,
            score_components["risk_score"],
            gates,
        )
        architecture_type = _architecture_type(roles)
        role_ids = {
            role: sorted({asset.asset_id for asset in role_group})
            for role, role_group in sorted(role_assets.items())
        }
        label = _repo_label(repo_key, repo_groups[repo_key])
        architecture_key = f"{repo_key}::{architecture_type}"
        records.append(
            ReferenceArchitectureRecord(
                reference_architecture_id=stable_id(
                    "reference-architecture",
                    architecture_key,
                    ",".join(component_asset_ids),
                    METHODOLOGY_VERSION,
                ),
                architecture_key=architecture_key,
                architecture_label=f"{label} {architecture_type.replace('_', ' ')}",
                repository_key=repo_key,
                architecture_type=architecture_type,  # type: ignore[arg-type]
                component_asset_ids=component_asset_ids,
                component_roles=role_ids,
                detected_patterns=_detected_patterns(roles),
                composition_summary=_composition_summary(roles),
                why_it_is_good_reference=_why_good(roles, len(component_asset_ids)),
                missing_or_weak_pieces=_missing_pieces(roles),
                reuse_guidance=_reuse_guidance(roles),
                novelty_score=score_components["novelty_score"],
                usefulness_score=score_components["usefulness_score"],
                completeness_score=score_components["completeness_score"],
                reusability_score=score_components["reusability_score"],
                composition_score=score_components["composition_score"],
                validation_readiness=score_components["validation_readiness"],
                risk_score=score_components["risk_score"],
                reference_score=reference_score,
                score_components=score_components,
                gates=gates,
                gate_failures=gate_failures,
                smallest_bounded_experiment=(
                    "Review the listed component roles and verify whether they form a reusable "
                    "architecture before copying, templating, or applying it to another repo."
                ),
                validation_plan=_validation_plan(roles),
                human_gates=_human_gates(roles, privacy_gate),
                authority_boundary=AUTHORITY_BOUNDARY,
                evidence={
                    "methodology_version": METHODOLOGY_VERSION,
                    "formula": REFERENCE_SCORE_FORMULA,
                    "component_limit": component_limit,
                    "role_labels": {
                        role: ROLE_DEFINITIONS[role]["label"] for role in sorted(roles)
                    },
                    "component_paths": {
                        asset_id: assets_by_id[asset_id].logical_path
                        for asset_id in component_asset_ids
                        if asset_id in assets_by_id
                    },
                    "component_value_scores": {
                        asset_id: round(float(assets_by_id[asset_id].value_score), 2)
                        for asset_id in component_asset_ids
                        if asset_id in assets_by_id
                    },
                    "internal_candidate_edge_count": internal_edges,
                    "checked_inputs": [
                        "catalog assets metadata",
                        edge_input_status,
                        "asset paths/titles/types/tags/capabilities/needs",
                    ],
                    "not_checked": [
                        "source file contents",
                        "fresh filesystem recursion",
                        "GitHub or external APIs",
                        "model or embedding calls",
                    ],
                },
                methodology_version=METHODOLOGY_VERSION,
                generated_at=generated,
                scan_id=scan_id,
            )
        )
    return sorted(
        records,
        key=lambda record: (
            -record.reference_score,
            record.architecture_type,
            record.repository_key,
            record.reference_architecture_id,
        ),
    )[:limit]


def build_reference_architecture_scan_cycle_event(
    records: list[ReferenceArchitectureRecord],
    *,
    generated_at: str,
    scan_id: str,
    edges_included: bool = False,
) -> ScanCycleEventRecord:
    statuses = [
        {
            "signal_family_id": "reference_architecture_metadata_scan",
            "label": "Reference architecture metadata scan",
            "cycle_order": 1,
            "current_status": "covered_by_current_report" if records else "no_candidates_from_catalog",
            "requires_human_approval": False,
            "next_action": "Review generated architecture candidates before promoting or templating.",
        },
        {
            "signal_family_id": "source_content_architecture_review",
            "label": "Source content architecture review",
            "cycle_order": 2,
            "current_status": "gated_content_read_not_checked",
            "requires_human_approval": True,
            "next_action": "Only read bounded source content after explicit source-scope approval.",
        },
        {
            "signal_family_id": "template_dependency_architecture_pass",
            "label": "Template dependency architecture pass",
            "cycle_order": 3,
            "current_status": "candidate_next_pass",
            "requires_human_approval": False,
            "next_action": "Compare reference architectures against the template registry dependencies.",
        },
        {
            "signal_family_id": "architecture_composition_validation",
            "label": "Architecture composition validation",
            "cycle_order": 4,
            "current_status": "needs_human_review",
            "requires_human_approval": True,
            "next_action": "Human verifies whether component roles genuinely work together.",
        },
    ]
    checked_inputs = [
        "state/catalog.sqlite3 assets table",
        "catalog asset metadata fields used for architecture-role matching",
    ]
    intentionally_not_checked = [
        "source file contents",
        "fresh local filesystem recursion",
        "GitHub, CI, or external APIs",
        "model, embedding, or semantic enrichment calls",
        "source repository writes",
    ]
    if edges_included:
        checked_inputs.append("state/catalog.sqlite3 candidate edges table")
    else:
        intentionally_not_checked.append(
            "full candidate edge table, skipped by default to keep v1 bounded on large catalogs"
        )
    return ScanCycleEventRecord(
        event_id=stable_id("scan-cycle-event", scan_id, generated_at, "reference-architectures"),
        pass_type="reference_architecture_no_rescan_metadata_pass",
        methodology_version=METHODOLOGY_VERSION,
        scan_id=scan_id,
        generated_at=generated_at,
        checked_inputs=checked_inputs,
        intentionally_not_checked=intentionally_not_checked,
        signal_family_statuses=statuses,
        recommended_next_signal_family_ids=[
            "source_content_architecture_review",
            "template_dependency_architecture_pass",
            "architecture_composition_validation",
        ],
        blocked_or_gated_signal_family_ids=[
            "source_content_architecture_review",
            "architecture_composition_validation",
        ],
        next_scan_guidance=[
            "Do not repeat broad local scans; first review these metadata-only reference architecture candidates.",
            "Next pass should compare candidates to template dependencies and workflow-part records.",
            "Only run a content pass for a specific repo/path scope after human approval.",
        ],
        authority_boundary=AUTHORITY_BOUNDARY,
        applies_when=[
            "A future agent needs to know whether reference architectures were already scanned from catalog metadata.",
            "A future agent is choosing the next architecture-signal pass without repeating broad scans.",
        ],
        does_not_apply_when=[
            "The user explicitly approves a fresh broad source scan.",
            "The task requires source-owned architecture truth rather than generated candidate evidence.",
        ],
        danger_if_misapplied=(
            "A metadata-only architecture candidate can be mistaken for proof that a design is canonical, "
            "complete, or safe to copy. Human review is required before promotion or template updates."
        ),
    )


def _markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> list[str]:
    if not rows:
        return ["No rows.", ""]
    lines = [
        "| " + " | ".join(label for label, _ in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        cells = []
        for _, key in columns:
            value = row.get(key, "")
            if isinstance(value, float):
                text = f"{value:.2f}"
            elif isinstance(value, list):
                text = ", ".join(str(item) for item in value)
            else:
                text = str(value)
            text = text.replace("\n", " ").replace("|", "\\|")
            if key.endswith("id") or key in {"architecture_type"}:
                text = f"`{text}`" if text else text
            cells.append(text)
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return lines


def reference_architecture_markdown(
    records: list[ReferenceArchitectureRecord],
    *,
    generated_at: str,
    scan_id: str,
) -> str:
    rows = [
        {
            "score": record.reference_score,
            "architecture_type": record.architecture_type,
            "label": record.architecture_label,
            "roles": sorted(record.component_roles),
            "gates": ", ".join(record.gate_failures) or "pass",
        }
        for record in records
    ]
    lines = [
        "# Reference Architecture Candidates",
        "",
        f"Generated at: `{generated_at}`",
        f"Scan id: `{scan_id}`",
        f"Methodology: `{METHODOLOGY_VERSION}`",
        "",
        AUTHORITY_BOUNDARY,
        "",
        "## What Counts As A Reference Architecture",
        "",
        (
            "A reference architecture is a reusable system shape made from cooperating pieces: "
            "entrypoints, architecture docs, schemas/contracts, rules, validators, workflows, "
            "learning loops, templates, and public-safe boundaries. One strong file can be useful, "
            "but it is not a reference architecture by itself."
        ),
        "",
        "## Scoring Formula",
        "",
        f"`{REFERENCE_SCORE_FORMULA}`",
        "",
        "Scores are review-order signals only. Current component evidence is judged before upside or reuse.",
        "",
        "## Candidate Summary",
        "",
    ]
    lines.extend(
        _markdown_table(
            rows,
            [
                ("score", "score"),
                ("type", "architecture_type"),
                ("label", "label"),
                ("roles", "roles"),
                ("gates", "gates"),
            ],
        )
    )
    for index, record in enumerate(records, 1):
        component_paths = record.evidence.get("component_paths", {})
        lines.extend(
            [
                f"## {index}. {record.architecture_label}",
                "",
                f"- Reference score: **{record.reference_score:.2f}**",
                f"- Type: `{record.architecture_type}`",
                f"- Repository key: `{record.repository_key}`",
                f"- Patterns: `{', '.join(record.detected_patterns)}`",
                f"- Gates: `{', '.join(record.gate_failures) or 'pass'}`",
                f"- Composition: {record.composition_summary}",
                "",
                "Why it may be a good reference:",
                "",
                *[f"- {reason}" for reason in record.why_it_is_good_reference],
                "",
                "Components by role:",
                "",
            ]
        )
        for role, asset_ids in sorted(record.component_roles.items()):
            label = ROLE_DEFINITIONS.get(role, {}).get("label", role)
            lines.append(f"- `{role}` ({label})")
            for asset_id in asset_ids:
                path = component_paths.get(asset_id, asset_id)
                lines.append(f"  - `{path}`")
        lines.extend(["", "Missing or weak pieces:", ""])
        lines.extend(f"- {piece}" for piece in record.missing_or_weak_pieces)
        lines.extend(["", "Reuse guidance:", ""])
        lines.extend(f"- {item}" for item in record.reuse_guidance)
        lines.extend(["", "Smallest bounded experiment:", "", f"- {record.smallest_bounded_experiment}", ""])
        lines.extend(["Validation plan:", ""])
        lines.extend(f"- `{command}`" for command in record.validation_plan)
        lines.extend(["", "Human gates:", ""])
        lines.extend(f"- {gate}" for gate in record.human_gates)
        lines.append("")
    lines.extend(
        [
            "## Scan Cycle Notes",
            "",
            "- Checked: catalog asset metadata and existing candidate edges.",
            "- Not checked: source file contents, new local recursion, GitHub/API calls, model calls, or source writes.",
            "- Next: review candidates, then compare high-value candidates against template dependencies and workflow-part records.",
            "",
        ]
    )
    return "\n".join(lines)


def write_reference_architecture_outputs(
    repo_root: Path,
    assets: list[AssetRecord],
    edges: list[EdgeRecord],
    *,
    scan_id: str = "catalog-without-scan",
    limit: int = 50,
    component_limit: int = 12,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    records = build_reference_architecture_records(
        assets,
        edges,
        scan_id=scan_id,
        limit=limit,
        component_limit=component_limit,
        generated_at=generated,
    )
    report_dir = repo_root / "processed" / "reports"
    learning_dir = repo_root / "processed" / "learning"
    report_path = report_dir / "reference_architectures.md"
    payload_path = report_dir / "reference_architectures.json"
    candidates_path = learning_dir / "reference_architecture_candidates.jsonl"
    scan_cycle_event_path = learning_dir / "scan_cycle_events.jsonl"
    payload = {
        "schema": "reference_architecture_recognition.v1",
        "methodology_version": METHODOLOGY_VERSION,
        "generated_at": generated,
        "scan_id": scan_id,
        "candidate_only": True,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "formula": REFERENCE_SCORE_FORMULA,
        "summary": {
            "candidate_count": len(records),
            "top_score": records[0].reference_score if records else 0.0,
            "architecture_type_counts": dict(Counter(record.architecture_type for record in records)),
        },
        "records": [record.model_dump(mode="json") for record in records],
    }
    event = build_reference_architecture_scan_cycle_event(
        records,
        generated_at=generated,
        scan_id=scan_id,
        edges_included=bool(edges),
    )
    atomic_write_text(report_path, reference_architecture_markdown(records, generated_at=generated, scan_id=scan_id) + "\n")
    atomic_write_text(payload_path, json_dumps(payload, pretty=True) + "\n")
    write_jsonl(candidates_path, [record.model_dump(mode="json") for record in records])
    append_jsonl(scan_cycle_event_path, event.model_dump(mode="json"))
    return {
        "report": str(report_path),
        "payload": str(payload_path),
        "candidates": str(candidates_path),
        "scan_cycle_events": str(scan_cycle_event_path),
        "candidate_count": len(records),
        "candidate_only": True,
        "methodology_version": METHODOLOGY_VERSION,
        "top_score": records[0].reference_score if records else 0.0,
    }
