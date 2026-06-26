from __future__ import annotations

from math import sqrt
from pathlib import Path
from typing import Any
import yaml

from .instance_class import classify_instance_class, information_content_class
from .models import AssetRecord

SCORE_METHODOLOGY_VERSION = "asset-value-v0.3-content-aware"

DEFAULT_WEIGHTS = {
    "reuse_potential": 0.15,
    "verification": 0.13,
    "provenance": 0.09,
    "composability": 0.12,
    "learning_loop_value": 0.11,
    "information_content": 0.17,
    "content_role": 0.08,
    "uniqueness": 0.06,
    "demand_signal": 0.05,
    "freshness": 0.04,
}

QUARANTINED_INSTANCE_CLASSES = {"generated", "temp_fixture", "worktree", "os_junk"}
EVIDENCE_GATED_TYPES = {"test", "evaluation", "schema"}


def load_scoring(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "config" / "scoring.yaml"
    return (
        yaml.safe_load(path.read_text(encoding="utf-8"))
        if path.exists()
        else {"weights": DEFAULT_WEIGHTS}
    )


def classify_instance(asset: AssetRecord) -> str:
    value = asset.metadata.get("instance_class")
    if isinstance(value, str) and value:
        return value
    return classify_instance_class(asset.logical_path)


def _content_profile(asset: AssetRecord) -> dict[str, Any]:
    profile = asset.metadata.get("content_profile")
    return profile if isinstance(profile, dict) else {}


def _profile_int(profile: dict[str, Any], key: str) -> int:
    try:
        return int(profile.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _information_content(asset: AssetRecord) -> float:
    metadata = asset.metadata or {}
    profile = _content_profile(asset)
    info_class = information_content_class(
        asset.logical_path,
        asset_type=asset.asset_type,
        size_bytes=asset.size_bytes,
        content_sha256=asset.content_sha256,
        metadata=metadata,
    )
    token_count = len(metadata.get("text_tokens") or [])
    text_len = len(str(metadata.get("chunk_text") or metadata.get("excerpt") or ""))
    line_count = _profile_int(profile, "non_empty_line_count")
    public_symbols = _profile_int(profile, "public_symbol_count")
    imports = _profile_int(profile, "import_count")
    semantic_count = (
        len(asset.tags) + len(asset.capabilities) + len(asset.needs) + len(asset.outcomes)
    )
    if asset.asset_type == "repository" or info_class == "repository_boundary":
        return min(1.0, 0.45 + 0.10 * len(asset.entrypoints) + 0.08 * semantic_count)
    if info_class == "os_junk":
        return 0.0
    if info_class in {"empty", "empty_marker"}:
        return 0.03 if info_class == "empty_marker" else 0.05
    if info_class == "content_profiled":
        line_signal = min(1.0, line_count / 160)
        symbol_signal = min(1.0, (public_symbols + imports * 0.4) / 12)
        if asset.asset_type == "code":
            return max(0.35, line_signal, symbol_signal)
        if asset.asset_type == "workflow":
            return max(0.30, min(0.85, line_signal * 0.75 + symbol_signal * 0.25))
        return max(0.25, line_signal * 0.8)
    if info_class == "metadata_only":
        return 0.12
    text_signal = max(min(1.0, token_count / 80), min(1.0, text_len / 4000))
    semantic_signal = min(1.0, semantic_count / 8)
    binary_signal = 0.20 if info_class == "binary_metadata" else 0.0
    return max(text_signal, semantic_signal * 0.8, binary_signal, 0.25)


def _has_direct_value_evidence(asset: AssetRecord, instance_class: str, information: float) -> bool:
    if instance_class in QUARANTINED_INSTANCE_CLASSES:
        return False
    profile = _content_profile(asset)
    has_bounded_profile = _profile_int(profile, "non_empty_line_count") > 0
    if not (asset.content_sha256 or has_bounded_profile) or information < 0.20:
        return False
    if asset.asset_type not in EVIDENCE_GATED_TYPES:
        return True
    return bool(
        asset.capabilities
        or asset.outcomes
        or asset.entrypoints
        or asset.metadata.get("pattern_evidence")
    )


def _freshness_value(asset: AssetRecord, instance_class: str) -> float:
    base = {"current": 1.0, "watch": 0.65, "stale": 0.25, "unknown": 0.45}.get(
        asset.freshness_status, 0.45
    )
    caps = {
        "temp_fixture": 0.25,
        "worktree": 0.45,
        "generated": 0.45,
        "os_junk": 0.0,
    }
    return min(base, caps.get(instance_class, base))


def _uniqueness_value(duplicate_count: int, is_representative: bool) -> float:
    if duplicate_count <= 1:
        return 1.0
    if is_representative:
        return 0.85
    return max(0.05, 1.0 - min(0.95, 0.20 * (duplicate_count - 1)))


def _content_role_value(asset: AssetRecord, instance_class: str) -> float:
    if instance_class in QUARANTINED_INSTANCE_CLASSES:
        return 0.0
    profile = _content_profile(asset)
    line_count = _profile_int(profile, "non_empty_line_count")
    public_symbols = _profile_int(profile, "public_symbol_count")
    imports = _profile_int(profile, "import_count")
    if asset.asset_type == "code":
        role = str(profile.get("code_role") or "unknown")
        if role == "package_marker":
            return 0.05
        if role == "entrypoint_wrapper":
            return 0.25
        if role in {"runtime_core", "entrypoint"}:
            return min(1.0, 0.55 + line_count / 350 + public_symbols / 20)
        if role == "test_support":
            return min(0.75, 0.35 + line_count / 400 + public_symbols / 30)
        if role in {"support_module", "script"}:
            return min(0.65, 0.25 + line_count / 500 + public_symbols / 40)
        return min(0.75, 0.20 + line_count / 450 + (public_symbols + imports) / 50)
    if asset.asset_type == "workflow":
        subtype = str(profile.get("workflow_subtype") or "workflow_unspecified")
        values = {
            "ci_validation_workflow": 0.78,
            "governance_workflow_doc": min(0.75, 0.35 + line_count / 220),
            "registry_or_config_wrapper": 0.38,
            "ruleset_config": 0.35,
            "ci_workflow_wrapper": 0.30,
            "issue_or_pr_template": 0.12,
            "ownership_metadata": 0.10,
            "archive_or_pinned_copy": 0.12,
            "workflow_unspecified": 0.25,
        }
        return float(values.get(subtype, 0.25))
    return min(1.0, line_count / 240) if line_count else 0.15


def _score_discount(
    instance_class: str,
    info_class: str,
    asset_type: str,
    profile: dict[str, Any],
    duplicate_count: int,
    is_representative: bool,
) -> tuple[float, list[str]]:
    factor = 1.0
    reasons: list[str] = []
    if instance_class == "os_junk" or info_class == "os_junk":
        factor = min(factor, 0.02)
        reasons.append("os_junk_floor")
    elif instance_class == "temp_fixture":
        factor = min(factor, 0.25)
        reasons.append("temp_fixture_lineage_not_independent_value")
    elif instance_class == "worktree":
        factor = min(factor, 0.45)
        reasons.append("worktree_copy_candidate_only")
    elif instance_class == "generated":
        factor = min(factor, 0.45)
        reasons.append("generated_output_not_source_truth")
    if info_class == "empty_marker":
        factor = min(factor, 0.25)
        reasons.append("empty_marker_not_independent_value")
    elif info_class == "empty":
        factor = min(factor, 0.30)
        reasons.append("empty_file_low_information")
    elif info_class == "metadata_only":
        factor = min(factor, 0.55)
        reasons.append("metadata_only_no_content_evidence")
    if asset_type == "code" and profile.get("code_role") == "package_marker":
        factor = min(factor, 0.30)
        reasons.append("package_marker_low_independent_value")
    if asset_type == "code" and profile.get("code_role") == "support_module":
        line_count = _profile_int(profile, "non_empty_line_count")
        if line_count < 50:
            factor = min(factor, 0.75)
            reasons.append("small_support_module_needs_usage_evidence")
    if asset_type == "code" and profile.get("code_role") == "test_support":
        line_count = _profile_int(profile, "non_empty_line_count")
        if line_count < 50:
            factor = min(factor, 0.85)
            reasons.append("small_test_support_module_needs_usage_evidence")
    if asset_type == "code" and profile.get("code_role") == "module":
        line_count = _profile_int(profile, "non_empty_line_count")
        public_symbols = _profile_int(profile, "public_symbol_count")
        if line_count < 40 and public_symbols <= 3:
            factor = min(factor, 0.88)
            reasons.append("small_module_needs_usage_evidence")
    if asset_type == "workflow":
        subtype = str(profile.get("workflow_subtype") or "")
        if subtype == "archive_or_pinned_copy":
            factor = min(factor, 0.50)
            reasons.append("workflow_archive_or_pinned_copy")
        elif subtype == "issue_or_pr_template":
            factor = min(factor, 0.45)
            reasons.append("workflow_issue_or_pr_template")
        elif subtype == "ownership_metadata":
            factor = min(factor, 0.40)
            reasons.append("workflow_ownership_metadata")
        elif subtype in {"ruleset_config", "registry_or_config_wrapper"}:
            factor = min(factor, 0.95)
            reasons.append("workflow_config_wrapper_needs_usage_evidence")
    if duplicate_count > 1 and not is_representative:
        factor = min(factor, max(0.18, 1.0 / sqrt(duplicate_count + 1)))
        reasons.append("duplicate_non_representative_discount")
    return factor, reasons


def score_asset(
    asset: AssetRecord,
    scoring: dict[str, Any],
    duplicate_counts: dict[str, int] | None = None,
) -> AssetRecord:
    weights = scoring.get("weights", DEFAULT_WEIGHTS)
    instance_class = classify_instance(asset)
    info_class = information_content_class(
        asset.logical_path,
        asset_type=asset.asset_type,
        size_bytes=asset.size_bytes,
        content_sha256=asset.content_sha256,
        metadata=asset.metadata,
    )
    duplicate_count = (duplicate_counts or {}).get(asset.asset_id, 1)
    representative_id = asset.metadata.get("duplicate_representative_id")
    is_representative = duplicate_count <= 1 or representative_id == asset.asset_id
    information = _information_content(asset)
    has_direct_evidence = _has_direct_value_evidence(asset, instance_class, information)
    profile = _content_profile(asset)
    content_role = _content_role_value(asset, instance_class)
    learning_types = {
        "evaluation",
        "test",
        "lesson",
        "decision",
        "workflow",
        "schema",
        "ontology",
        "skill",
        "model",
        "algorithm",
        "forecaster",
    }
    reusable_types = {
        "code",
        "schema",
        "ontology",
        "taxonomy",
        "prompt",
        "skill",
        "workflow",
        "model",
        "algorithm",
        "forecaster",
        "adapter",
        "connector",
        "evaluation",
        "test",
        "decision",
        "lesson",
    }
    reusable_type_bonus = (
        0.25 if asset.asset_type in reusable_types and has_direct_evidence else 0.0
    )
    verification_type_bonus = (
        0.55 if asset.asset_type in EVIDENCE_GATED_TYPES and has_direct_evidence else 0.0
    )
    learning_type_bonus = (
        0.45 if asset.asset_type in learning_types and has_direct_evidence else 0.0
    )
    components = {
        "reuse_potential": min(
            1.0,
            0.45 + 0.15 * len(asset.capabilities) + reusable_type_bonus,
        ),
        "verification": min(
            1.0,
            0.25 + verification_type_bonus + (0.15 if "evaluation" in asset.tags else 0.0),
        ),
        "provenance": (
            0.95
            if asset.content_sha256
            else 0.55
            if (asset.source_provenance or asset.source_id)
            else 0.2
        ),
        "composability": min(
            1.0, 0.25 + 0.13 * len(asset.capabilities) + 0.08 * len(asset.outcomes)
        ),
        "learning_loop_value": min(1.0, 0.30 + learning_type_bonus + 0.08 * len(asset.needs)),
        "information_content": information,
        "content_role": content_role,
        "uniqueness": _uniqueness_value(duplicate_count, is_representative),
        "demand_signal": min(1.0, 0.30 + 0.15 * len(asset.needs) + 0.10 * len(asset.outcomes)),
        "freshness": _freshness_value(asset, instance_class),
    }
    raw = sum(float(weights.get(name, 0)) * value for name, value in components.items())
    penalties = scoring.get("risk_penalties", {})
    risk = 0.0
    if asset.sensitivity == "unknown":
        risk += float(penalties.get("sensitive_unclassified", 0.08))
    if not asset.content_sha256 and not asset.source_provenance:
        risk += float(penalties.get("no_provenance", 0.08))
    if (
        asset.source_kind == "github"
        and asset.asset_type == "repository"
        and not asset.metadata.get("license")
    ):
        risk += float(penalties.get("unknown_license", 0.04))
    risk_factor = max(0.0, 1.0 - min(0.85, risk))
    raw *= risk_factor
    discount_factor, discount_reasons = _score_discount(
        instance_class,
        info_class,
        asset.asset_type,
        profile,
        duplicate_count,
        is_representative,
    )
    raw *= discount_factor

    asset.value_components = {k: round(v * 100, 2) for k, v in components.items()}
    if risk:
        asset.value_components["risk_factor"] = round(risk_factor * 100, 2)
    if discount_factor < 1.0:
        asset.value_components["score_discount_factor"] = round(discount_factor * 100, 2)
    asset.value_score = round(max(0.0, min(1.0, raw)) * 100, 2)
    asset.metadata["instance_class"] = instance_class
    asset.metadata["information_content_class"] = info_class
    asset.metadata["scoring_eligibility"] = (
        "eligible" if instance_class == "source" else "discounted"
    )
    asset.metadata["information_content"] = {
        "score": round(information * 100, 2),
        "text_token_count": len(asset.metadata.get("text_tokens") or []),
        "text_char_count": len(
            str(asset.metadata.get("chunk_text") or asset.metadata.get("excerpt") or "")
        ),
        "content_profile_present": bool(profile),
        "class": info_class,
        "methodology": "bounded text/token/semantic/profile evidence heuristic",
    }
    asset.metadata["score_methodology_version"] = SCORE_METHODOLOGY_VERSION
    asset.metadata["score_discount_reasons"] = discount_reasons
    asset.metadata["heuristic_strength"] = asset.confidence
    asset.metadata["score_methodology"] = {
        "version": SCORE_METHODOLOGY_VERSION,
        "inputs": [
            "asset_type",
            "content_sha256",
            "source_provenance",
            "capabilities",
            "needs",
            "outcomes",
            "tags",
            "freshness_status",
            "sensitivity",
            "instance_class",
            "information_content_class",
            "content_profile",
            "duplicate_representative_id",
            "duplicate_count",
        ],
        "normalization": (
            "weighted components in 0..1, multiplicative risk and instance discounts, "
            "output clamped to 0..100"
        ),
        "uncertainty": "heuristic_strength is not calibrated probability; human review required",
        "candidate_only": True,
    }
    return asset
