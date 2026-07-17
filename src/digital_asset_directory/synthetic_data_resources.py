from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from jsonschema.validators import validator_for


REGISTRY = Path("registry/synthetic-data-resource-registry.json")
SCHEMA = Path("schemas/synthetic-data-resource-registry.schema.json")

POSITIVE_SIGNALS = {
    "scarce_labels",
    "rare_cases",
    "privacy_safe_fixture",
    "controllable_ground_truth",
    "simulation_available",
    "coverage_stress",
    "domain_randomization",
}
BLOCKING_SIGNALS = {
    "source_terms_unknown",
    "unowned_target",
    "unmeasured_domain_gap",
    "sensitive_source_unapproved",
    "no_evaluation_path",
}
CONSEQUENCES = {"low", "medium", "high"}
EXACT_OPEN_LICENSES = {"MIT", "Apache-2.0", "GPL-3.0", "LGPL-3.0", "BSD-3-Clause", "MPL-2.0"}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_synthetic_resources(repo_root: Path) -> dict[str, Any]:
    payload = _load_json(repo_root / REGISTRY)
    schema = _load_json(repo_root / SCHEMA)
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema, format_checker=validator_cls.FORMAT_CHECKER).validate(payload)
    ids = [row["resource_id"] for row in payload["resources"]]
    if len(ids) != len(set(ids)):
        raise ValueError("synthetic resource IDs must be unique")
    return payload


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _resource_tokens(row: dict[str, Any]) -> set[str]:
    return _tokens(json.dumps(row, sort_keys=True))


def synthetic_catalog(repo_root: Path, query: str = "", domain: str = "") -> dict[str, Any]:
    registry = load_synthetic_resources(repo_root)
    wanted = _tokens(query)
    domain_tokens = _tokens(domain)
    rows = []
    for row in registry["resources"]:
        tokens = _resource_tokens(row)
        if wanted and not wanted <= tokens:
            continue
        if domain_tokens and not domain_tokens <= _tokens(" ".join(row["domains"])):
            continue
        rows.append(row)
    return {
        "schema_version": "synthetic_data.catalog.v1",
        "query": query,
        "domain": domain,
        "candidate_only": True,
        "count": len(rows),
        "resources": rows,
        "unresolved_names": registry["unresolved_names"],
        "authority_boundary": registry["authority_boundary"],
    }


def _parse_signals(signals: str | list[str]) -> set[str]:
    if isinstance(signals, str):
        values = {item.strip() for item in signals.split(",") if item.strip()}
    else:
        values = {item.strip() for item in signals if item.strip()}
    unknown = values - POSITIVE_SIGNALS - BLOCKING_SIGNALS
    if unknown:
        raise ValueError(f"unknown synthetic-data signals: {', '.join(sorted(unknown))}")
    return values


def synthetic_route(
    repo_root: Path,
    *,
    objective: str,
    modality: str = "unknown",
    domain: str = "",
    signals: str | list[str] = "",
    real_holdout_available: bool = False,
    consequence: str = "medium",
    limit: int = 5,
) -> dict[str, Any]:
    """Return a deterministic, suggestion-only synthetic-data opportunity route."""
    if not objective.strip():
        raise ValueError("objective must not be empty")
    if consequence not in CONSEQUENCES:
        raise ValueError("consequence must be low, medium, or high")
    if limit < 1 or limit > 20:
        raise ValueError("limit must be between 1 and 20")
    signal_set = _parse_signals(signals)
    blockers = sorted(signal_set & BLOCKING_SIGNALS)
    positives = sorted(signal_set & POSITIVE_SIGNALS)
    if blockers:
        disposition = "blocked"
    elif not positives:
        disposition = "insufficient_evidence"
    elif consequence == "high" and not real_holdout_available:
        disposition = "real_holdout_required"
    else:
        disposition = "candidate_synthetic_path"

    registry = load_synthetic_resources(repo_root)
    task_tokens = _tokens(f"{objective} {modality} {domain}")
    requested_modality = modality.strip().lower()
    requested_domains = _tokens(domain)
    ranked: list[tuple[int, str, dict[str, Any]]] = []
    for row in registry["resources"]:
        if row["status"] == "retired":
            continue
        row_modalities = {str(value).lower() for value in row["modalities"]}
        row_domains = _tokens(" ".join(row["domains"]))
        if requested_modality != "unknown" and requested_modality not in row_modalities:
            continue
        if requested_domains and not requested_domains & row_domains:
            continue
        score = len(task_tokens & _resource_tokens(row))
        if requested_modality != "unknown":
            score += 4
        if requested_domains:
            score += 3
        if score:
            ranked.append((score, row["resource_id"], row))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    candidates = []
    for score, _, row in ranked[:limit]:
        if row["synthetic_scope"] == "real_validation_benchmark":
            candidate_role = "real_holdout_candidate"
        elif row["synthetic_scope"] == "augmentation":
            candidate_role = "augmentation_candidate"
        elif "simulator" in row["artifact_classes"]:
            candidate_role = "simulation_candidate"
        else:
            candidate_role = "generator_or_dataset_candidate"
        candidates.append({
            "resource_id": row["resource_id"],
            "name": row["name"],
            "score": score,
            "candidate_role": candidate_role,
            "status": row["status"],
            "synthetic_scope": row["synthetic_scope"],
            "artifact_classes": row["artifact_classes"],
            "license": row["license"],
            "access": row["access"],
            "terms_review_required": row["access"] != "open" or row["license"] not in EXACT_OPEN_LICENSES,
            "use_when": row["use_when"],
            "avoid_when": row["avoid_when"],
            "validation_requirements": row["validation_requirements"],
            "primary_sources": row["primary_sources"],
        })
    if disposition == "candidate_synthetic_path" and not candidates:
        disposition = "insufficient_evidence"
    if disposition != "candidate_synthetic_path":
        candidates = []

    gates = ["confirm source terms and license", "lock generation recipe and seed", "measure synthetic-to-target domain gap"]
    if consequence in {"medium", "high"}:
        gates.append("independent checker")
    if not real_holdout_available:
        gates.append("obtain a representative real holdout before real-world performance claims")
    return {
        "schema_version": "synthetic_data.route.v1",
        "objective": objective.strip(),
        "modality": modality,
        "domain": domain,
        "signals": sorted(signal_set),
        "disposition": disposition,
        "candidate_only": True,
        "dispatch_authorized": False,
        "candidates": candidates,
        "required_gates": gates,
        "stop_conditions": blockers or (["No positive synthetic-data need was supplied."] if not positives else []),
        "registry_version": registry["registry_version"],
        "authority_boundary": registry["authority_boundary"],
    }
