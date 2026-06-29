from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

from .config import LocalSource
from .ids import stable_id
from .models import AlertRecord, AssetRecord, EdgeRecord, RepoBuildoutRecommendationRecord
from .utils import atomic_write_text, json_dumps, utc_now

METHODOLOGY_VERSION = "repo-buildout-advisor-v0.1"
AUTHORITY_BOUNDARY = (
    "Generated candidate buildout advice only. This command does not rescan, mutate the "
    "target repository, call GitHub, call models, install hooks, promote candidates to "
    "truth, change current value scores, or mark roadmap phases complete."
)
PRIORITY_FORMULA = (
    "priority_score = 100 * (0.25*repo_relevance + 0.20*gap_severity + "
    "0.20*workflow_leverage + 0.15*validation_readiness + 0.10*evidence_strength + "
    "0.10*low_risk_bonus); failed required gates cap priority at 25"
)

RECOMMENDATION_ORDER = {
    "manual_task_alert": 0,
    "front_door_ai_navigation": 1,
    "governance_human_gates": 2,
    "schemas_contracts_validators": 3,
    "workflow_parts_reusable_subsystems": 4,
    "learning_pay_forward_loops": 5,
    "dataflow_normalization": 6,
    "testing_qa_ci": 7,
    "duplicate_variant_semantic_evolution": 8,
    "security_privacy_public_safe": 9,
    "internal_composition": 10,
    "proposal_or_background_connection": 11,
    "cross_repo_inspiration": 12,
}

DUPLICATE_EDGE_TYPES = {
    "exact_duplicate_of",
    "near_duplicate_of",
    "noise_variant_of",
    "archived_variant_of",
    "lineage_evidence_for",
}

REPO_ENTRYPOINT_NAMES = {
    "AI_FRONT_DOOR.md",
    "AI_TABLE_OF_CONTENTS.md",
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
}

VALIDATION_HINTS = {
    "python": "python -m pytest",
    "pyproject": "python -m pytest",
    "package": "npm test",
    "schema": "run the repo-local schema validator or contract tests",
    "default": "run the repo-local tests or validator named by the target repo",
}


def _normalized_path(value: str) -> str:
    return value.replace("\\", "/").strip().strip("/").lower()


def _path_parts(value: str) -> tuple[str, ...]:
    return tuple(part for part in PurePosixPath(_normalized_path(value)).parts if part)


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().replace("\\", "/"))
    return slug.strip("-._").lower() or "repo"


def _repo_root_key(asset: AssetRecord) -> str:
    if asset.asset_type == "repository":
        return _normalized_path(asset.logical_path)
    repository_root = asset.metadata.get("repository_root")
    if isinstance(repository_root, str) and repository_root.strip():
        return _normalized_path(repository_root)
    parts = _path_parts(asset.logical_path)
    if len(parts) >= 3 and parts[0] in {"git-projects", "github", "repos"}:
        if re.match(r"^\d{2}[_-]", parts[1]) or "git_projects" in parts[1]:
            return "/".join(parts[:3])
    if len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0] if parts else "."


def _repo_label_from_key(key: str) -> str:
    parts = _path_parts(key)
    return parts[-1] if parts else key


def _candidate_repo_keys(repo: str, local_sources: list[LocalSource] | None = None) -> set[str]:
    raw = repo.strip()
    normalized = _normalized_path(raw)
    keys = {normalized}
    if normalized:
        keys.add(_safe_slug(normalized).replace("-", " "))
        keys.add(Path(raw).name.lower())
    path = Path(raw)
    if path.is_absolute() and local_sources:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        for source in local_sources:
            try:
                relative = resolved.relative_to(source.path.resolve())
            except (ValueError, OSError):
                continue
            alias_key = f"{source.path_alias}/{relative.as_posix()}".rstrip("/")
            keys.add(_normalized_path(alias_key))
    return {key for key in keys if key}


def build_repo_groups(assets: list[AssetRecord]) -> dict[str, list[AssetRecord]]:
    groups: dict[str, list[AssetRecord]] = defaultdict(list)
    for asset in assets:
        groups[_repo_root_key(asset)].append(asset)
    return dict(groups)


def resolve_repo_scope(
    repo: str,
    assets: list[AssetRecord],
    local_sources: list[LocalSource] | None = None,
) -> dict[str, Any]:
    groups = build_repo_groups(assets)
    aliases = _candidate_repo_keys(repo, local_sources)
    by_id = {asset.asset_id: asset for asset in assets}
    matched_keys: set[str] = set()

    if repo in by_id:
        matched_keys.add(_repo_root_key(by_id[repo]))

    exact_keys = {key for key in groups if key in aliases}
    if not exact_keys:
        exact_keys = {
            key
            for key, group_assets in groups.items()
            if any(_normalized_path(asset.logical_path) in aliases for asset in group_assets)
        }
    if exact_keys:
        matched_keys.update(exact_keys)
    else:
        for key, group_assets in groups.items():
            label = _repo_label_from_key(key).lower()
            key_parts = set(_path_parts(key))
            for alias in aliases:
                alias_label = _repo_label_from_key(alias).lower()
                if key.endswith(f"/{alias}") or alias.endswith(f"/{key}"):
                    matched_keys.add(key)
                elif alias == label or alias_label == label:
                    matched_keys.add(key)
                elif alias in key_parts and alias == label:
                    matched_keys.add(key)
                elif any(_normalized_path(asset.logical_path) == alias for asset in group_assets):
                    matched_keys.add(key)

    if not matched_keys:
        raise ValueError(
            "Target repo is not present in the current catalog. Run an approved local scan first; "
            "repo-buildout will not rescan automatically."
        )
    raw_repo = repo.strip()
    path_like_query = "/" in raw_repo or "\\" in raw_repo or Path(raw_repo).is_absolute()
    if len(matched_keys) > 1:
        matched_labels = {_repo_label_from_key(key).lower() for key in matched_keys}
        if not path_like_query or len(matched_labels) != 1:
            choices = ", ".join(sorted(matched_keys)[:10])
            raise ValueError(f"Target repo is ambiguous in the current catalog: {choices}")

    key = sorted(matched_keys, key=lambda item: (len(item), item), reverse=True)[0]
    grouped_assets: dict[str, AssetRecord] = {}
    for matched_key in matched_keys:
        for asset in groups[matched_key]:
            grouped_assets[asset.asset_id] = asset
    scoped_assets = sorted(
        grouped_assets.values(),
        key=lambda asset: (
            asset.asset_type != "repository",
            -float(asset.value_score),
            asset.logical_path,
            asset.asset_id,
        ),
    )
    repo_asset = next((asset for asset in scoped_assets if asset.asset_type == "repository"), None)
    return {
        "target_repo_key": key,
        "target_repo_label": repo_asset.title if repo_asset else _repo_label_from_key(key),
        "repo_asset": repo_asset,
        "assets": scoped_assets,
        "asset_ids": {asset.asset_id for asset in scoped_assets},
        "aliases_considered": sorted(aliases),
    }


def load_optional_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"_load_error": f"Invalid JSON: {path}"}


def load_optional_jsonl(path: Path | None) -> list[dict[str, Any]]:
    if not path or not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                records.append({"_load_error": f"Invalid JSONL line in {path}"})
    return records


def load_default_repo_buildout_artifacts(repo_root: Path) -> dict[str, Any]:
    processed = repo_root / "processed"
    return {
        "workflow_guidance": load_optional_json(
            processed / "workflow_parts" / "workflow_part_usage_guidance.json"
        ),
        "manual_tasks": load_optional_json(processed / "reports" / "manual_task_queue.json"),
        "semantic_evolution": load_optional_jsonl(
            processed / "learning" / "semantic_evolution_candidates.jsonl"
        ),
        "background_connections": load_optional_jsonl(
            processed / "learning" / "background_connection_candidates.jsonl"
        ),
        "bottom_up_proposals": load_optional_jsonl(
            processed / "proposals" / "bottom_up_proposals.jsonl"
        ),
        "top_down_proposals": load_optional_jsonl(
            processed / "proposals" / "top_down_proposals.jsonl"
        ),
    }


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def repo_buildout_priority_score(components: dict[str, float], gates: dict[str, bool]) -> float:
    weights = {
        "repo_relevance": 0.25,
        "gap_severity": 0.20,
        "workflow_leverage": 0.20,
        "validation_readiness": 0.15,
        "evidence_strength": 0.10,
        "low_risk_bonus": 0.10,
    }
    raw = sum(weights[key] * _clamp01(float(components.get(key, 0.0))) for key in weights)
    score = round(100.0 * _clamp01(raw), 2)
    if not all(gates.values()):
        score = min(score, 25.0)
    return score


def _risk_bonus(risk: str) -> float:
    return {"low": 1.0, "medium": 0.55, "high": 0.2}.get(risk, 0.4)


def _confidence_from_evidence(count: int) -> float:
    if count >= 5:
        return 1.0
    if count >= 3:
        return 0.75
    if count >= 2:
        return 0.55
    if count == 1:
        return 0.35
    return 0.0


def _asset_value_summary(assets: list[AssetRecord]) -> str:
    if not assets:
        return "Current value cannot be assessed because no scoped asset evidence was found."
    scores = sorted(float(asset.value_score) for asset in assets)
    midpoint = scores[len(scores) // 2]
    top = max(assets, key=lambda asset: (float(asset.value_score), asset.title))
    return (
        f"Current scoped evidence: {len(assets)} asset(s), median value {midpoint:.1f}, "
        f"top asset `{top.title}` at {float(top.value_score):.1f}. Judge current score before "
        "using any upside claim."
    )


def _make_recommendation(
    *,
    scope: dict[str, Any],
    recommendation_type: str,
    title: str,
    rationale: str,
    evidence_assets: list[AssetRecord],
    components: dict[str, float],
    risk: str,
    source_boundary: str,
    upside_lift_conditions: list[str],
    smallest_bounded_experiment: str,
    validation_plan: list[str],
    human_gates: list[str] | None = None,
    red_team_note: str,
    evidence: dict[str, Any],
    generated_at: str,
    scan_id: str,
    cross_repo_inspiration: bool = False,
    scan_watermark_ok: bool = True,
) -> RepoBuildoutRecommendationRecord:
    evidence_ids = sorted({asset.asset_id for asset in evidence_assets})
    gates = {
        "evidence_gate": bool(evidence_ids),
        "source_boundary_gate": source_boundary
        not in {"unsafe", "source_mutation_required", "unreviewed_external_code"},
        "privacy_gate": not any(asset.sensitivity in {"restricted"} for asset in evidence_assets),
        "no_target_mutation_gate": True,
        "no_external_call_gate": True,
        "scan_watermark_gate": scan_watermark_ok,
    }
    gate_failures = [key for key, passed in gates.items() if not passed]
    normalized_components = {key: round(_clamp01(float(value)), 4) for key, value in components.items()}
    normalized_components.setdefault("low_risk_bonus", _risk_bonus(risk))
    priority = repo_buildout_priority_score(normalized_components, gates)
    key = scope["target_repo_key"]
    recommendation_id = stable_id(
        "repo-buildout-recommendation",
        key,
        recommendation_type,
        title.casefold(),
        ",".join(evidence_ids),
    )
    return RepoBuildoutRecommendationRecord(
        recommendation_id=recommendation_id,
        target_repo_key=key,
        target_repo_label=scope["target_repo_label"],
        recommendation_type=recommendation_type,  # type: ignore[arg-type]
        title=title,
        rationale=rationale,
        priority_score=priority,
        priority_components=normalized_components,
        gates=gates,
        gate_failures=gate_failures,
        risk=risk,  # type: ignore[arg-type]
        evidence_asset_ids=evidence_ids or [scope["assets"][0].asset_id],
        current_value_summary=_asset_value_summary(evidence_assets or scope["assets"][:1]),
        upside_lift_conditions=upside_lift_conditions,
        smallest_bounded_experiment=smallest_bounded_experiment,
        validation_plan=validation_plan,
        human_gates=human_gates or [],
        red_team_note=red_team_note,
        authority_boundary=AUTHORITY_BOUNDARY,
        source_boundary=source_boundary,
        cross_repo_inspiration=cross_repo_inspiration,
        evidence={
            "methodology_version": METHODOLOGY_VERSION,
            "formula": PRIORITY_FORMULA,
            **evidence,
        },
        methodology_version=METHODOLOGY_VERSION,
        generated_at=generated_at,
        scan_id=scan_id,
    )


def _assets_with_name(assets: list[AssetRecord], names: set[str]) -> list[AssetRecord]:
    return [
        asset
        for asset in assets
        if PurePosixPath(asset.logical_path.replace("\\", "/")).name in names
        or asset.title in names
    ]


def _assets_matching_terms(assets: list[AssetRecord], terms: set[str]) -> list[AssetRecord]:
    matches = []
    for asset in assets:
        haystack = (
            f"{asset.asset_type} {asset.title} {asset.description} {asset.logical_path} "
            f"{' '.join(asset.tags)} {' '.join(asset.capabilities)} {' '.join(asset.needs)}"
        ).lower()
        if any(term in haystack for term in terms):
            matches.append(asset)
    return matches


def _repo_assets_by_path(assets: list[AssetRecord]) -> dict[str, AssetRecord]:
    return {_normalized_path(asset.logical_path): asset for asset in assets}


def _external_asset_for_path(path: str, assets: list[AssetRecord]) -> AssetRecord | None:
    normalized = _normalized_path(path)
    by_path = _repo_assets_by_path(assets)
    if normalized in by_path:
        return by_path[normalized]
    return next(
        (asset for asset in assets if _normalized_path(asset.logical_path).endswith(normalized)),
        None,
    )


def _scoped_alerts(alerts: list[AlertRecord], asset_ids: set[str]) -> list[AlertRecord]:
    return [
        alert
        for alert in alerts
        if alert.status == "open" and asset_ids.intersection(alert.asset_ids)
    ]


def _duplicate_pairs(edges: list[EdgeRecord], asset_ids: set[str]) -> list[EdgeRecord]:
    return [
        edge
        for edge in edges
        if edge.edge_type in DUPLICATE_EDGE_TYPES
        and edge.source_asset_id in asset_ids
        and edge.target_asset_id in asset_ids
    ]


def _duplicate_composition_skip_ids(
    assets: list[AssetRecord], duplicate_pairs: set[tuple[str, str]]
) -> set[str]:
    by_id = {asset.asset_id: asset for asset in assets}
    skip_ids: set[str] = set()
    noise_terms = (
        "archive",
        "backup",
        "copy",
        "temp",
        ".pytest",
        "_codex_worktrees",
        "generated",
    )
    for left_id, right_id in duplicate_pairs:
        left = by_id.get(left_id)
        right = by_id.get(right_id)
        if not left or not right:
            continue
        left_path = left.logical_path.lower()
        right_path = right.logical_path.lower()
        left_noisy = any(term in left_path for term in noise_terms)
        right_noisy = any(term in right_path for term in noise_terms)
        if left_noisy and not right_noisy:
            skip_ids.add(left_id)
        elif right_noisy and not left_noisy:
            skip_ids.add(right_id)
        elif float(left.value_score) != float(right.value_score):
            skip_ids.add(left_id if float(left.value_score) < float(right.value_score) else right_id)
        else:
            skip_ids.update({left_id, right_id})
    return skip_ids


def _capability_need_pairs(
    assets: list[AssetRecord], edges: list[EdgeRecord]
) -> list[tuple[AssetRecord, AssetRecord, str]]:
    existing = {
        tuple(sorted((edge.source_asset_id, edge.target_asset_id)))
        for edge in edges
        if edge.edge_type not in DUPLICATE_EDGE_TYPES
    }
    duplicate_pairs = {
        tuple(sorted((edge.source_asset_id, edge.target_asset_id)))
        for edge in edges
        if edge.edge_type in DUPLICATE_EDGE_TYPES
    }
    duplicate_asset_ids = _duplicate_composition_skip_ids(assets, duplicate_pairs)
    pairs = []
    for source in assets:
        if source.asset_id in duplicate_asset_ids:
            continue
        for target in assets:
            if source.asset_id == target.asset_id:
                continue
            if target.asset_id in duplicate_asset_ids:
                continue
            pair_key = tuple(sorted((source.asset_id, target.asset_id)))
            if pair_key in existing or pair_key in duplicate_pairs:
                continue
            shared = sorted(set(source.capabilities) & set(target.needs))
            if shared:
                pairs.append((source, target, shared[0]))
    return sorted(
        pairs,
        key=lambda row: (-float(row[0].value_score), row[2], row[0].logical_path, row[1].logical_path),
    )


def _validation_plan_for_assets(assets: list[AssetRecord]) -> list[str]:
    text = " ".join(f"{asset.logical_path} {asset.asset_type}" for asset in assets).lower()
    if "pyproject.toml" in text or ".py" in text or "python" in text:
        return [VALIDATION_HINTS["python"]]
    if "package.json" in text or ".tsx" in text or ".ts" in text:
        return [VALIDATION_HINTS["package"]]
    if "schema" in text:
        return [VALIDATION_HINTS["schema"]]
    return [VALIDATION_HINTS["default"]]


def _artifact_warning(name: str, artifact: Any) -> str | None:
    if artifact:
        if isinstance(artifact, dict) and artifact.get("_load_error"):
            return str(artifact["_load_error"])
        return None
    return f"Optional generated input `{name}` was not present; recommendation quality is reduced."


def _record_from_manual_task(
    item: dict[str, Any], scope: dict[str, Any], assets_by_id: dict[str, AssetRecord]
) -> AssetRecord | None:
    asset_id = str(item.get("asset_id") or "")
    if asset_id in assets_by_id:
        return assets_by_id[asset_id]
    path = str(item.get("logical_path") or item.get("representative_path") or "")
    return _external_asset_for_path(path, list(assets_by_id.values()))


def build_repo_buildout_plan(
    repo: str,
    assets: list[AssetRecord],
    edges: list[EdgeRecord],
    alerts: list[AlertRecord],
    *,
    local_sources: list[LocalSource] | None = None,
    artifacts: dict[str, Any] | None = None,
    scan_id: str = "catalog-without-scan",
    scan_changed_count: int = 0,
    limit: int = 10,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    artifact_data = artifacts or {}
    scope = resolve_repo_scope(repo, assets, local_sources)
    scoped_assets: list[AssetRecord] = scope["assets"]
    asset_ids: set[str] = scope["asset_ids"]
    scoped_by_id = {asset.asset_id: asset for asset in scoped_assets}
    scoped_edges = [
        edge
        for edge in edges
        if edge.source_asset_id in asset_ids or edge.target_asset_id in asset_ids
    ]
    internal_edges = [
        edge
        for edge in scoped_edges
        if edge.source_asset_id in asset_ids and edge.target_asset_id in asset_ids
    ]
    scoped_alert_records = _scoped_alerts(alerts, asset_ids)
    repo_asset = scope["repo_asset"] or scoped_assets[0]
    warnings = [
        warning
        for name in (
            "workflow_guidance",
            "manual_tasks",
            "semantic_evolution",
            "background_connections",
            "bottom_up_proposals",
            "top_down_proposals",
        )
        if (warning := _artifact_warning(name, artifact_data.get(name)))
    ]
    if scan_changed_count:
        warnings.append(
            f"Latest scan changed during run ({scan_changed_count} file(s)); treat output as triage."
        )

    recommendations: list[RepoBuildoutRecommendationRecord] = []
    scan_watermark_ok = scan_id != "catalog-without-scan"
    entrypoints = _assets_with_name(scoped_assets, REPO_ENTRYPOINT_NAMES)
    observed_entrypoints = {
        PurePosixPath(asset.logical_path.replace("\\", "/")).name for asset in entrypoints
    }
    missing_entrypoints = sorted(REPO_ENTRYPOINT_NAMES - observed_entrypoints)
    entrypoint_gap = 1.0 if missing_entrypoints else 0.25
    recommendations.append(
        _make_recommendation(
            scope=scope,
            recommendation_type="front_door_ai_navigation",
            title="Make repo entry and AI navigation deterministic",
            rationale=(
                "Future agents need one front door, TOC-style routing, tags, and use-when "
                "triggers before they compose or mutate repo workflows."
            ),
            evidence_assets=entrypoints or [repo_asset],
            components={
                "repo_relevance": 1.0,
                "gap_severity": entrypoint_gap,
                "workflow_leverage": 0.85,
                "validation_readiness": 0.75,
                "evidence_strength": _confidence_from_evidence(len(entrypoints)),
                "low_risk_bonus": 0.75,
            },
            risk="medium" if missing_entrypoints else "low",
            source_boundary="same_repo_report_only",
            upside_lift_conditions=[
                "Add or verify front-door and TOC rows with path, role, tags, and use-when triggers.",
                "Link generated graph/report surfaces as candidate evidence, not source truth.",
            ],
            smallest_bounded_experiment=(
                "Open the repo front-door files and check whether an AI can route to tests, "
                "schemas, workflows, and authority rules in under five minutes."
            ),
            validation_plan=["review repo-local front door, TOC, and start-here docs"],
            human_gates=[] if not missing_entrypoints else ["human review of new AI navigation text"],
            red_team_note=(
                "Navigation work can become busywork if it lists filenames without routing triggers. "
                "Keep it small and deterministic."
            ),
            evidence={
                "entrypoint_asset_ids": [asset.asset_id for asset in entrypoints],
                "missing_entrypoints": missing_entrypoints,
            },
            generated_at=generated,
            scan_id=scan_id,
            scan_watermark_ok=scan_watermark_ok,
        )
    )

    governance_assets = _assets_matching_terms(
        scoped_assets, {"preflight", "postflight", "human gate", "roadmap", "governance", "policy"}
    )
    recommendations.append(
        _make_recommendation(
            scope=scope,
            recommendation_type="governance_human_gates",
            title="Verify load-bearing decisions and human gates before buildout",
            rationale=(
                "Repo buildout recommendations can affect many downstream agents. Governance assets "
                "should identify high-risk decisions before implementation."
            ),
            evidence_assets=governance_assets or [repo_asset],
            components={
                "repo_relevance": 0.9,
                "gap_severity": 0.65 if not governance_assets else 0.25,
                "workflow_leverage": 0.8,
                "validation_readiness": 0.65,
                "evidence_strength": _confidence_from_evidence(len(governance_assets)),
                "low_risk_bonus": 0.55,
            },
            risk="medium",
            source_boundary="same_repo_report_only",
            upside_lift_conditions=[
                "Define high, medium, and low risk build decisions.",
                "Use a fresh-eyes review prompt before changing shared schemas, scoring, hooks, or gates.",
            ],
            smallest_bounded_experiment=(
                "Pick one proposed change and run a load-bearing decision review before editing."
            ),
            validation_plan=["run repo-local governance or roadmap validation if present"],
            human_gates=["human approval for high-risk schema, scoring, hook, or roadmap defaults"],
            red_team_note=(
                "A report can make a weak idea look official. Human gates must decide authority, "
                "not the generated priority score."
            ),
            evidence={"governance_asset_count": len(governance_assets)},
            generated_at=generated,
            scan_id=scan_id,
            scan_watermark_ok=scan_watermark_ok,
        )
    )

    schema_assets = [asset for asset in scoped_assets if asset.asset_type == "schema"]
    validator_assets = _assets_matching_terms(scoped_assets, {"validate", "validator", "test", "pytest"})
    if schema_assets or validator_assets:
        recommendations.append(
            _make_recommendation(
                scope=scope,
                recommendation_type="schemas_contracts_validators",
                title="Tie schemas and validators into an explicit contract loop",
                rationale=(
                    "Schemas are more valuable when validators and tests prove conformance before "
                    "generated outputs or repo changes are trusted."
                ),
                evidence_assets=(schema_assets[:4] + validator_assets[:4]) or [repo_asset],
                components={
                    "repo_relevance": 0.95,
                    "gap_severity": 0.8 if schema_assets and not validator_assets else 0.35,
                    "workflow_leverage": 0.9,
                    "validation_readiness": 0.9 if validator_assets else 0.35,
                    "evidence_strength": _confidence_from_evidence(
                        len(schema_assets) + len(validator_assets)
                    ),
                    "low_risk_bonus": 0.65,
                },
                risk="medium" if schema_assets and not validator_assets else "low",
                source_boundary="same_repo_report_only",
                upside_lift_conditions=[
                    "Pair each important schema with a validator or test fixture.",
                    "Record validation commands beside the workflow that depends on the schema.",
                ],
                smallest_bounded_experiment=(
                    "Select one high-value schema and verify there is a deterministic validation command."
                ),
                validation_plan=_validation_plan_for_assets(schema_assets + validator_assets),
                human_gates=[],
                red_team_note=(
                    "A schema without a validator can inflate confidence. A validator without source "
                    "authority can also be misleading."
                ),
                evidence={
                    "schema_count": len(schema_assets),
                    "validator_or_test_count": len(validator_assets),
                },
                generated_at=generated,
                scan_id=scan_id,
                scan_watermark_ok=scan_watermark_ok,
            )
        )

    workflow_guidance = artifact_data.get("workflow_guidance") or {}
    review_rows = [
        row
        for row in workflow_guidance.get("review_use_candidates", [])
        if _external_asset_for_path(str(row.get("representative_path") or ""), scoped_assets)
    ]
    if review_rows:
        row_assets = [
            asset
            for row in review_rows[:5]
            if (asset := _external_asset_for_path(str(row.get("representative_path") or ""), scoped_assets))
        ]
        recommendations.append(
            _make_recommendation(
                scope=scope,
                recommendation_type="workflow_parts_reusable_subsystems",
                title="Use reviewed workflow parts as repo-local buildout examples",
                rationale=(
                    "Reviewed workflow parts are useful as examples, but assembly still needs "
                    "declared inputs, outputs, side effects, validation, and gates."
                ),
                evidence_assets=row_assets or [repo_asset],
                components={
                    "repo_relevance": 1.0,
                    "gap_severity": 0.45,
                    "workflow_leverage": 0.95,
                    "validation_readiness": 0.65,
                    "evidence_strength": _confidence_from_evidence(len(review_rows)),
                    "low_risk_bonus": 0.55,
                },
                risk="medium",
                source_boundary="same_repo_report_only",
                upside_lift_conditions=[
                    "Declare dataflow for each reusable part before assembly.",
                    "Keep rejected workflow-part patterns nearby as false-positive guards.",
                ],
                smallest_bounded_experiment=(
                    "Choose one accepted workflow-part row and write the inputs, outputs, "
                    "side effects, and validation command before using it."
                ),
                validation_plan=["run the validation command tied to the selected workflow part"],
                human_gates=["human gate if the part crosses source or authority boundaries"],
                red_team_note=(
                    "Workflow-part labels are review guidance, not permission to copy or execute code."
                ),
                evidence={"review_use_rows": review_rows[:5]},
                generated_at=generated,
                scan_id=scan_id,
                scan_watermark_ok=scan_watermark_ok,
            )
        )

    learning_assets = _assets_matching_terms(
        scoped_assets, {"learning", "lesson", "handoff", "postflight", "pay-forward", "feedback"}
    )
    recommendations.append(
        _make_recommendation(
            scope=scope,
            recommendation_type="learning_pay_forward_loops",
            title="Install or verify the repo-local learning pay-forward loop",
            rationale=(
                "Buildout work should capture before-use expectations, after-use value, failure "
                "signals, and context limits so future agents do not repeat the same mistakes."
            ),
            evidence_assets=learning_assets or [repo_asset],
            components={
                "repo_relevance": 0.85,
                "gap_severity": 0.75 if not learning_assets else 0.25,
                "workflow_leverage": 0.85,
                "validation_readiness": 0.55,
                "evidence_strength": _confidence_from_evidence(len(learning_assets)),
                "low_risk_bonus": 0.75,
            },
            risk="low",
            source_boundary="same_repo_report_only",
            upside_lift_conditions=[
                "Record what asset was used, why, expected value, actual value, and reuse limits.",
                "Keep lessons context-bound with applies_when, does_not_apply_when, and danger notes.",
            ],
            smallest_bounded_experiment=(
                "Capture one before-work and one after-work repo learning event for the next build task."
            ),
            validation_plan=["inspect `.digital-asset-directory/learning/events.jsonl` if installed"],
            human_gates=[],
            red_team_note=(
                "Learning loops become noise if every small observation becomes a universal rule."
            ),
            evidence={"learning_asset_count": len(learning_assets)},
            generated_at=generated,
            scan_id=scan_id,
            scan_watermark_ok=scan_watermark_ok,
        )
    )

    data_assets = _assets_matching_terms(
        scoped_assets, {"data", "normalize", "mapping", "schema", "csv", "jsonl", "dataset"}
    )
    if data_assets:
        recommendations.append(
            _make_recommendation(
                scope=scope,
                recommendation_type="dataflow_normalization",
                title="Document dataflow and normalization before expanding data assets",
                rationale=(
                    "Data-heavy repos are easiest to improve when source order, normalization, "
                    "identity keys, validation, and privacy boundaries are explicit."
                ),
                evidence_assets=data_assets[:6],
                components={
                    "repo_relevance": 0.9,
                    "gap_severity": 0.6,
                    "workflow_leverage": 0.8,
                    "validation_readiness": 0.5,
                    "evidence_strength": _confidence_from_evidence(len(data_assets)),
                    "low_risk_bonus": 0.45,
                },
                risk="medium",
                source_boundary="same_repo_report_only",
                upside_lift_conditions=[
                    "Declare source order, canonical IDs, dedupe rules, and row-level privacy posture.",
                    "Separate public-safe metadata from private or source-owned rows.",
                ],
                smallest_bounded_experiment=(
                    "Trace one input through normalization, validation, and output without changing data."
                ),
                validation_plan=["run the repo-local data normalization validator if present"],
                human_gates=["human review before importing private rows or external data"],
                red_team_note=(
                    "Data normalization mistakes can create false authority and duplicate identities."
                ),
                evidence={"data_asset_count": len(data_assets)},
                generated_at=generated,
                scan_id=scan_id,
                scan_watermark_ok=scan_watermark_ok,
            )
        )

    code_assets = [asset for asset in scoped_assets if asset.asset_type in {"code", "algorithm"}]
    test_assets = [asset for asset in scoped_assets if asset.asset_type == "test"]
    if code_assets or test_assets:
        recommendations.append(
            _make_recommendation(
                scope=scope,
                recommendation_type="testing_qa_ci",
                title="Use tests and QA as the first buildout stabilizer",
                rationale=(
                    "Repo improvements should add or confirm the smallest validation command before "
                    "larger architecture changes."
                ),
                evidence_assets=(test_assets[:5] + code_assets[:3]) or [repo_asset],
                components={
                    "repo_relevance": 0.95,
                    "gap_severity": 0.8 if code_assets and not test_assets else 0.3,
                    "workflow_leverage": 0.75,
                    "validation_readiness": 0.95 if test_assets else 0.25,
                    "evidence_strength": _confidence_from_evidence(len(code_assets) + len(test_assets)),
                    "low_risk_bonus": 0.7,
                },
                risk="medium" if code_assets and not test_assets else "low",
                source_boundary="same_repo_report_only",
                upside_lift_conditions=[
                    "Put the smallest high-signal validator before broad refactors.",
                    "Record exact validation commands in the repo front door or operations docs.",
                ],
                smallest_bounded_experiment=(
                    "Run the smallest repo-local test command and add one missing test only if needed."
                ),
                validation_plan=_validation_plan_for_assets(scoped_assets),
                human_gates=[],
                red_team_note=(
                    "Late validators create rework; too many broad tests too early can also freeze exploration."
                ),
                evidence={"code_asset_count": len(code_assets), "test_asset_count": len(test_assets)},
                generated_at=generated,
                scan_id=scan_id,
                scan_watermark_ok=scan_watermark_ok,
            )
        )

    duplicate_edges = _duplicate_pairs(internal_edges, asset_ids)
    semantic_rows = [
        row
        for row in artifact_data.get("semantic_evolution", [])
        if asset_ids.intersection(set(row.get("source_asset_ids", [])))
        or any(_normalized_path(path).startswith(scope["target_repo_key"]) for path in row.get("representative_paths", []))
    ]
    if duplicate_edges or semantic_rows:
        evidence_assets = [
            scoped_by_id[edge.source_asset_id]
            for edge in duplicate_edges
            if edge.source_asset_id in scoped_by_id
        ]
        evidence_assets.extend(
            scoped_by_id[edge.target_asset_id]
            for edge in duplicate_edges
            if edge.target_asset_id in scoped_by_id
        )
        recommendations.append(
            _make_recommendation(
                scope=scope,
                recommendation_type="duplicate_variant_semantic_evolution",
                title="Review duplicate variants as deltas, not independent build targets",
                rationale=(
                    "Near-duplicates can preserve useful evolution, but they should not inflate current "
                    "asset value or consume the buildout queue as separate work."
                ),
                evidence_assets=evidence_assets[:6] or [repo_asset],
                components={
                    "repo_relevance": 0.9,
                    "gap_severity": 0.7,
                    "workflow_leverage": 0.75,
                    "validation_readiness": 0.5,
                    "evidence_strength": _confidence_from_evidence(
                        len(duplicate_edges) + len(semantic_rows)
                    ),
                    "low_risk_bonus": 0.6,
                },
                risk="medium",
                source_boundary="same_repo_report_only",
                upside_lift_conditions=[
                    "Preserve the family-level delta when semantic evolution is real.",
                    "Down-rank exact or cosmetic copies as lineage evidence.",
                ],
                smallest_bounded_experiment=(
                    "Pick one duplicate family and write the plus/minus/delta table before editing either copy."
                ),
                validation_plan=["run semantic evolution review for the relevant basename if stale"],
                human_gates=["human review before deleting, merging, or declaring a canonical variant"],
                red_team_note=(
                    "Duplicate similarity is not complementarity. The useful signal is the delta, not the copy."
                ),
                evidence={
                    "duplicate_edge_count": len(duplicate_edges),
                    "semantic_evolution_row_count": len(semantic_rows),
                },
                generated_at=generated,
                scan_id=scan_id,
                scan_watermark_ok=scan_watermark_ok,
            )
        )

    sensitive_assets = [
        asset
        for asset in scoped_assets
        if asset.sensitivity in {"confidential", "restricted"}
        or any(term in asset.logical_path.lower() for term in ("secret", "private", "credential"))
    ]
    security_assets = _assets_matching_terms(
        scoped_assets, {"security", "privacy", "public-safe", "secret", "credential"}
    )
    recommendations.append(
        _make_recommendation(
            scope=scope,
            recommendation_type="security_privacy_public_safe",
            title="Keep security, privacy, and public-safe boundaries explicit",
            rationale=(
                "Buildout advice may later be reused across repos or public artifacts, so private "
                "lanes and untrusted generated evidence need visible boundaries."
            ),
            evidence_assets=(security_assets[:5] + sensitive_assets[:5]) or [repo_asset],
            components={
                "repo_relevance": 0.9,
                "gap_severity": 0.85 if sensitive_assets and not security_assets else 0.35,
                "workflow_leverage": 0.7,
                "validation_readiness": 0.55,
                "evidence_strength": _confidence_from_evidence(
                    len(security_assets) + len(sensitive_assets)
                ),
                "low_risk_bonus": 0.5,
            },
            risk="high" if sensitive_assets else "medium",
            source_boundary="same_repo_report_only",
            upside_lift_conditions=[
                "Mark private data lanes, source-owned facts, and public-safe metadata separately.",
                "Treat generated recommendations and external feedback as untrusted data.",
            ],
            smallest_bounded_experiment=(
                "Review one generated report for raw private content before it is copied into tracked docs."
            ),
            validation_plan=["run secret scan or repo-local privacy check if present"],
            human_gates=["human review before public release, external intake, or private-row import"],
            red_team_note=(
                "The highest-risk failure is a useful report leaking private rows or instructions."
            ),
            evidence={
                "security_asset_count": len(security_assets),
                "sensitive_asset_count": len(sensitive_assets),
            },
            generated_at=generated,
            scan_id=scan_id,
            scan_watermark_ok=scan_watermark_ok,
        )
    )

    internal_pairs = _capability_need_pairs(scoped_assets, internal_edges)
    if internal_pairs:
        source, target, shared = internal_pairs[0]
        recommendations.append(
            _make_recommendation(
                scope=scope,
                recommendation_type="internal_composition",
                title=f"Try an internal composition around `{shared}`",
                rationale=(
                    "One repo-local asset declares a capability that matches another asset's need. "
                    "This is a bounded composition candidate, not proof that the connection works."
                ),
                evidence_assets=[source, target],
                components={
                    "repo_relevance": 1.0,
                    "gap_severity": 0.65,
                    "workflow_leverage": 0.85,
                    "validation_readiness": 0.55,
                    "evidence_strength": 0.65,
                    "low_risk_bonus": 0.6,
                },
                risk="medium",
                source_boundary="same_repo_report_only",
                upside_lift_conditions=[
                    "Declare inputs, outputs, and side effects before connecting the assets.",
                    "Run the smallest validator after the composition experiment.",
                ],
                smallest_bounded_experiment=(
                    f"Inspect `{source.logical_path}` and `{target.logical_path}` and draft a no-code "
                    "composition contract for the shared capability/need."
                ),
                validation_plan=_validation_plan_for_assets([source, target]),
                human_gates=[],
                red_team_note=(
                    "Shared vocabulary can be accidental. Do not confuse lexical match with usable dataflow."
                ),
                evidence={
                    "source_asset_id": source.asset_id,
                    "target_asset_id": target.asset_id,
                    "shared_capability_or_need": shared,
                    "duplicate_edges_excluded": len(duplicate_edges),
                },
                generated_at=generated,
                scan_id=scan_id,
                scan_watermark_ok=scan_watermark_ok,
            )
        )

    manual_tasks = artifact_data.get("manual_tasks") or {}
    manual_rows = []
    for item in manual_tasks.get("ranked_alerts", []):
        if (asset := _record_from_manual_task(item, scope, scoped_by_id)):
            manual_rows.append((item, asset))
    if manual_rows:
        item, asset = manual_rows[0]
        recommendations.append(
            _make_recommendation(
                scope=scope,
                recommendation_type="manual_task_alert",
                title=f"Address top manual-review alert: {item.get('title') or item.get('alert_type')}",
                rationale=str(item.get("recommended_manual_action") or "Review current alert evidence."),
                evidence_assets=[asset],
                components={
                    "repo_relevance": 1.0,
                    "gap_severity": _clamp01(float(item.get("priority_score") or 0.0) / 100.0),
                    "workflow_leverage": 0.55,
                    "validation_readiness": 0.45,
                    "evidence_strength": 0.65,
                    "low_risk_bonus": 0.55,
                },
                risk="medium",
                source_boundary=str(item.get("source_boundary") or "same_repo_report_only"),
                upside_lift_conditions=[
                    "Resolve the alert as metadata/review work first; do not mutate source files from DAD.",
                    "If the alert is source-owned, carry the authority boundary into the target repo.",
                ],
                smallest_bounded_experiment="Open the alert evidence and decide whether it is true, noise, or deferred.",
                validation_plan=["rerun the alert-producing DAD command after a future approved scan"],
                human_gates=["human review before source-repo mutation"],
                red_team_note=(
                    "Manual queue priority is review order, not proof that the alert is correct."
                ),
                evidence={"manual_task_row": item},
                generated_at=generated,
                scan_id=scan_id,
                scan_watermark_ok=scan_watermark_ok,
            )
        )

    generated_candidates = [
        row
        for key in ("background_connections", "bottom_up_proposals", "top_down_proposals")
        for row in artifact_data.get(key, [])
        if asset_ids.intersection(
            set(row.get("source_asset_ids", []))
            | set(row.get("target_asset_ids", []))
            | set(row.get("cold_asset_ids", []))
        )
    ]
    if generated_candidates:
        candidate = generated_candidates[0]
        evidence_ids = [
            scoped_by_id[asset_id]
            for asset_id in (
                list(candidate.get("source_asset_ids", []))
                + list(candidate.get("target_asset_ids", []))
                + list(candidate.get("cold_asset_ids", []))
            )
            if asset_id in scoped_by_id
        ]
        recommendations.append(
            _make_recommendation(
                scope=scope,
                recommendation_type="proposal_or_background_connection",
                title="Review existing proposal or background-connection candidate",
                rationale=(
                    "Existing generated candidates already mention this repo. Use them as review "
                    "packets before inventing a new build direction."
                ),
                evidence_assets=evidence_ids or [repo_asset],
                components={
                    "repo_relevance": 1.0,
                    "gap_severity": 0.55,
                    "workflow_leverage": 0.75,
                    "validation_readiness": 0.45,
                    "evidence_strength": 0.55,
                    "low_risk_bonus": 0.45,
                },
                risk="medium",
                source_boundary="generated_candidate_review_only",
                upside_lift_conditions=[
                    "Confirm the candidate is useful, safe, novel, and actionable.",
                    "Use human labels before letting it affect defaults or future scoring.",
                ],
                smallest_bounded_experiment="Review one candidate packet and label it accept, reject, or defer.",
                validation_plan=["rerun proposal or background connection review summary after labels"],
                human_gates=["human candidate review"],
                red_team_note=(
                    "Generated candidates can repeat stale or weak ideas; do not treat frequency as value."
                ),
                evidence={"candidate": candidate},
                generated_at=generated,
                scan_id=scan_id,
                scan_watermark_ok=scan_watermark_ok,
            )
        )

    external_rows = [
        row
        for row in workflow_guidance.get("review_use_candidates", [])
        if not _external_asset_for_path(str(row.get("representative_path") or ""), scoped_assets)
    ]
    external_assets = [
        asset
        for row in external_rows[:8]
        if (asset := _external_asset_for_path(str(row.get("representative_path") or ""), assets))
    ]
    if external_assets:
        recommendations.append(
            _make_recommendation(
                scope=scope,
                recommendation_type="cross_repo_inspiration",
                title="Compare one reviewed cross-repo workflow part as inspiration only",
                rationale=(
                    "A reviewed workflow part from another repo may suggest a build pattern, but source "
                    "authority does not transfer across repositories."
                ),
                evidence_assets=external_assets[:3],
                components={
                    "repo_relevance": 0.45,
                    "gap_severity": 0.45,
                    "workflow_leverage": 0.75,
                    "validation_readiness": 0.35,
                    "evidence_strength": _confidence_from_evidence(len(external_assets)),
                    "low_risk_bonus": 0.2,
                },
                risk="high",
                source_boundary="cross_repo_inspiration_human_gated",
                upside_lift_conditions=[
                    "Translate only the workflow shape, not source-owned facts or private data.",
                    "Create a repo-local bounded experiment instead of copying the external asset.",
                ],
                smallest_bounded_experiment=(
                    "Read the external workflow-part row and draft a target-repo-local analogue without code changes."
                ),
                validation_plan=["run target repo tests after any separately approved implementation"],
                human_gates=["human approval before cross-repo copying, installation, or mutation"],
                red_team_note=(
                    "Cross-repo similarity is often lexical. Require dataflow and authority review."
                ),
                evidence={"external_workflow_part_rows": external_rows[:5]},
                generated_at=generated,
                scan_id=scan_id,
                cross_repo_inspiration=True,
                scan_watermark_ok=scan_watermark_ok,
            )
        )

    recommendations = sorted(
        recommendations,
        key=lambda record: (
            -record.priority_score,
            RECOMMENDATION_ORDER.get(record.recommendation_type, 99),
            record.title,
        ),
    )[:limit]

    type_counts = Counter(asset.asset_type for asset in scoped_assets)
    strongest = sorted(
        scoped_assets,
        key=lambda asset: (-float(asset.value_score), asset.asset_type, asset.logical_path),
    )[: min(12, len(scoped_assets))]
    internal_combinations = [
        {
            "source_asset_id": source.asset_id,
            "target_asset_id": target.asset_id,
            "shared_need_or_capability": shared,
            "source_path": source.logical_path,
            "target_path": target.logical_path,
            "candidate_only": True,
        }
        for source, target, shared in internal_pairs[:10]
    ]
    return {
        "schema": "repo_buildout_advisor.v1",
        "methodology_version": METHODOLOGY_VERSION,
        "generated_at": generated,
        "scan_id": scan_id,
        "candidate_only": True,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "formula": PRIORITY_FORMULA,
        "target_repo": {
            "key": scope["target_repo_key"],
            "label": scope["target_repo_label"],
            "repo_asset_id": repo_asset.asset_id if repo_asset else None,
            "aliases_considered": scope["aliases_considered"],
        },
        "asset_summary": {
            "asset_count": len(scoped_assets),
            "asset_type_counts": dict(sorted(type_counts.items())),
            "edge_count": len(scoped_edges),
            "internal_edge_count": len(internal_edges),
            "open_alert_count": len(scoped_alert_records),
            "current_value_summary": _asset_value_summary(scoped_assets),
        },
        "strongest_assets": [
            {
                "asset_id": asset.asset_id,
                "title": asset.title,
                "asset_type": asset.asset_type,
                "value_score": round(float(asset.value_score), 2),
                "logical_path": asset.logical_path,
            }
            for asset in strongest
        ],
        "internal_combinations": internal_combinations,
        "recommendations": [record.model_dump(mode="json") for record in recommendations],
        "human_decisions_required": sorted(
            {gate for record in recommendations for gate in record.human_gates}
        ),
        "warnings": warnings,
        "red_team_premortem": [
            "False positive: lexical overlap can look like workflow fit. Guard: require asset IDs, dataflow, and validation.",
            "Authority failure: cross-repo inspiration can be mistaken for permission to copy. Guard: human gate.",
            "Score overtrust: priority score is review order only. Guard: candidate-only boundary and formula.",
            "Stale evidence: generated inputs can lag the catalog. Guard: warnings and scan watermark.",
            "Privacy failure: reports must cite metadata and asset IDs, not raw private source dumps.",
        ],
    }


def _markdown_table(items: list[dict[str, Any]], columns: list[tuple[str, str]]) -> list[str]:
    if not items:
        return ["No items.", ""]
    lines = [
        "| " + " | ".join(label for label, _ in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for item in items:
        row = []
        for _, key in columns:
            value = item.get(key, "")
            if isinstance(value, float):
                text = f"{value:.2f}"
            elif isinstance(value, list):
                text = ", ".join(str(part) for part in value)
            else:
                text = str(value)
            text = text.replace("\n", " ").replace("|", "\\|")
            if key.endswith("path") or key == "logical_path":
                text = f"`{text}`" if text else text
            elif key.endswith("id") or key in {"asset_type", "recommendation_type", "risk"}:
                text = f"`{text}`" if text else text
            row.append(text)
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    return lines


def repo_buildout_markdown(result: dict[str, Any]) -> str:
    summary = result["asset_summary"]
    lines = [
        f"# Repo Buildout Advisor: {result['target_repo']['label']}",
        "",
        f"Generated at: `{result['generated_at']}`",
        f"Scan id: `{result['scan_id']}`",
        f"Methodology: `{result['methodology_version']}`",
        "",
        result["authority_boundary"],
        "",
        "## Current Asset Map",
        "",
        f"- Target repo key: `{result['target_repo']['key']}`",
        f"- Asset count: **{summary['asset_count']}**",
        f"- Asset type counts: `{summary['asset_type_counts']}`",
        f"- Candidate edges touching repo: **{summary['edge_count']}**",
        f"- Internal candidate edges: **{summary['internal_edge_count']}**",
        f"- Open alerts: **{summary['open_alert_count']}**",
        f"- Current value summary: {summary['current_value_summary']}",
        "",
        "## Strongest Existing Assets",
        "",
    ]
    lines.extend(
        _markdown_table(
            result["strongest_assets"],
            [
                ("score", "value_score"),
                ("type", "asset_type"),
                ("title", "title"),
                ("path", "logical_path"),
            ],
        )
    )
    lines.extend(["## Recommended Build Order", ""])
    recommendation_rows = [
        {
            "priority_score": item["priority_score"],
            "recommendation_type": item["recommendation_type"],
            "risk": item["risk"],
            "title": item["title"],
            "gates": ", ".join(item["gate_failures"]) or "pass",
        }
        for item in result["recommendations"]
    ]
    lines.extend(
        _markdown_table(
            recommendation_rows,
            [
                ("priority", "priority_score"),
                ("type", "recommendation_type"),
                ("risk", "risk"),
                ("title", "title"),
                ("gates", "gates"),
            ],
        )
    )
    for index, item in enumerate(result["recommendations"], 1):
        lines.extend(
            [
                f"### {index}. {item['title']}",
                "",
                f"- Type: `{item['recommendation_type']}`",
                f"- Priority score: **{item['priority_score']:.2f}**",
                f"- Risk: `{item['risk']}`",
                f"- Current evidence: {item['current_value_summary']}",
                f"- Rationale: {item['rationale']}",
                f"- Evidence asset ids: `{', '.join(item['evidence_asset_ids'])}`",
                f"- Source boundary: `{item['source_boundary']}`",
                f"- Smallest bounded experiment: {item['smallest_bounded_experiment']}",
                f"- Red-team note: {item['red_team_note']}",
                "",
                "Lift conditions:",
                "",
                *[f"- {condition}" for condition in item["upside_lift_conditions"]],
                "",
                "Validation plan:",
                "",
                *[f"- `{command}`" for command in item["validation_plan"]],
                "",
            ]
        )
        if item["human_gates"]:
            lines.extend(["Human gates:", "", *[f"- {gate}" for gate in item["human_gates"]], ""])
    lines.extend(["## Internal Combination Candidates", ""])
    lines.extend(
        _markdown_table(
            result["internal_combinations"],
            [
                ("shared", "shared_need_or_capability"),
                ("source", "source_path"),
                ("target", "target_path"),
            ],
        )
    )
    lines.extend(["## Human Decisions Required", ""])
    if result["human_decisions_required"]:
        lines.extend(f"- {gate}" for gate in result["human_decisions_required"])
    else:
        lines.append("No human gates beyond normal source-authority review were detected.")
    lines.extend(["", "## Warnings", ""])
    if result["warnings"]:
        lines.extend(f"- {warning}" for warning in result["warnings"])
    else:
        lines.append("No warnings.")
    lines.extend(["", "## Red Team And Premortem", ""])
    lines.extend(f"- {item}" for item in result["red_team_premortem"])
    lines.extend(
        [
            "",
            "## Exact DAD Validation Commands",
            "",
            "```powershell",
            "python -m pytest",
            "python -m ruff check src tests scripts noxfile.py",
            "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli validate",
            "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli roadmap check --no-update",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def repo_buildout_fresh_eyes_prompt(result: dict[str, Any]) -> str:
    return "\n".join(
        [
            "You are doing a fresh-eyes red-team review of a Digital Asset Directory generated repo buildout report.",
            "",
            f"Target repo: {result['target_repo']['label']} ({result['target_repo']['key']})",
            f"Methodology: {result['methodology_version']}",
            "",
            "Read the generated Markdown and JSON outputs. Check whether recommendations are useful, safe, novel, and actionable.",
            "",
            "Focus especially on:",
            "- false positives from lexical overlap or duplicate variants;",
            "- source-authority boundary mistakes;",
            "- privacy or public-safe leakage;",
            "- missing validators, schemas, gates, or learning loops;",
            "- whether current evidence is judged before upside;",
            "- whether cross-repo inspiration is human-gated;",
            "- whether the priority formula is applied consistently.",
            "",
            "Do not edit source repos. Do not call GitHub. Do not promote candidates to truth.",
            "Write findings as a separate evidence note or reply with concrete corrections.",
            "",
        ]
    )


def write_repo_buildout_outputs(
    repo_root: Path,
    repo: str,
    assets: list[AssetRecord],
    edges: list[EdgeRecord],
    alerts: list[AlertRecord],
    *,
    local_sources: list[LocalSource] | None = None,
    artifacts: dict[str, Any] | None = None,
    scan_id: str = "catalog-without-scan",
    scan_changed_count: int = 0,
    limit: int = 10,
    generated_at: str | None = None,
) -> dict[str, Any]:
    result = build_repo_buildout_plan(
        repo,
        assets,
        edges,
        alerts,
        local_sources=local_sources,
        artifacts=artifacts,
        scan_id=scan_id,
        scan_changed_count=scan_changed_count,
        limit=limit,
        generated_at=generated_at,
    )
    slug = _safe_slug(result["target_repo"]["key"])
    output_dir = repo_root / "processed" / "reports" / "repo_buildout"
    markdown_path = output_dir / f"{slug}.md"
    json_path = output_dir / f"{slug}.json"
    prompt_path = output_dir / f"{slug}_fresh_eyes_prompt.md"
    index_path = output_dir / "index.md"
    atomic_write_text(markdown_path, repo_buildout_markdown(result) + "\n")
    atomic_write_text(json_path, json_dumps(result, pretty=True) + "\n")
    atomic_write_text(prompt_path, repo_buildout_fresh_eyes_prompt(result))

    index_lines = [
        "# Repo Buildout Advisor Index",
        "",
        "Generated repo-specific buildout reports. Candidate evidence only.",
        "",
    ]
    for path in sorted(output_dir.glob("*.md")):
        if path.name == "index.md" or path.name.endswith("_fresh_eyes_prompt.md"):
            continue
        index_lines.append(f"- `{path.name}`")
    atomic_write_text(index_path, "\n".join(index_lines) + "\n")
    return {
        "report": str(markdown_path),
        "payload": str(json_path),
        "fresh_eyes_prompt": str(prompt_path),
        "index": str(index_path),
        "target_repo": result["target_repo"],
        "recommendation_count": len(result["recommendations"]),
        "candidate_only": True,
        "methodology_version": METHODOLOGY_VERSION,
        "warnings": result["warnings"],
    }
