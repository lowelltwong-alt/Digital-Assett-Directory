"""Governed, provider-neutral source-repository knowledge ingestion.

The source repository keeps authority.  This module creates an internal,
candidate-only snapshot from Git metadata plus an explicit content allowlist.
Privacy-excluded paths are represented by opaque path hashes and aggregate
families; their names and bytes never enter DAD.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SCHEMA_VERSION = "dad.source_knowledge_ingestion.v1"
SOURCE_REPOSITORY_ID = "dad://repo/mock-trial-4-26"
SOURCE_DISPLAY_NAME = "Albert / Mock Trial4.26"
OWNER = "Lowell"
AUTHORITY_BOUNDARY = (
    "Albert remains authoritative for its repository meaning and product data. "
    "DAD owns only this internal, revision-bound candidate snapshot. No record "
    "is adopted policy, public-release material, or downstream write authority "
    "without separate human review."
)

APPROVED_READ_PATHS = (
    ".digital-asset/context-map.json",
    ".digital-asset/dad-integration.json",
    ".github/workflows/ci-contracts.yml",
    ".github/workflows/ocr-quality.yml",
    ".github/workflows/simulation-red-team.yml",
    ".github/workflows/ui-browser.yml",
    "AGENTS.md",
    "AI_AGENT_RUNTIME_ORCHESTRATION.md",
    "AI_FRONT_DOOR.md",
    "AI_LEARNING_LOOP_LESSONS.md",
    "AI_MONTE_CARLO_SIMULATOR_BUILD_LESSONS.md",
    "AI_SUBAGENT_DECISION_FLOW.md",
    "AI_TOC.md",
    "config/albert_agent_runtime_orchestration.json",
    "config/albert_subagent_decision_flow.json",
    "config/digital_asset_catalog.json",
    "config/legal_case_edge_type_registry.json",
    "config/new_case_workflow_phases.json",
    "registries/litigation_witness_prep_technique_registry.v1.json",
    "simulation/validate_simulation_red_team_ci.py",
    "tests/test_ci_module_path_scoping.py",
)

# Exact bytes are narrower than approved reads. Navigation prose and lesson
# catalogs are normalized and hash-bound because they may contain case-local
# names or evidence paths even when their reusable rules are safe.
APPROVED_COPY_PATHS = (
    ".digital-asset/context-map.json",
    ".github/workflows/ci-contracts.yml",
    ".github/workflows/ocr-quality.yml",
    ".github/workflows/simulation-red-team.yml",
    ".github/workflows/ui-browser.yml",
    "config/albert_agent_runtime_orchestration.json",
    "config/albert_subagent_decision_flow.json",
    "config/new_case_workflow_phases.json",
    "simulation/validate_simulation_red_team_ci.py",
    "tests/test_ci_module_path_scoping.py",
)

PRIVACY_EXCLUDED_PREFIXES = (
    "outputs/cases/",
    "source/",
    "reports/",
    "simulation/output/",
    "analysis/",
    "case_config/",
    "exports/",
    "training/",
    "reviews/",
)
PRIVATE_REFERENCE_ONLY_PATHS = {
    "ai_workland/generated/file_manifest.json",
    "data/digital_assets/digital_asset_edges.jsonl",
    "data/digital_assets/digital_asset_graph.json",
    "data/digital_assets/digital_asset_nodes.jsonl",
}

SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b(?:password|passwd|api[_-]?key|client[_-]?secret)\s*[:=]\s*['\"][^'\"\r\n]{8,}"),
)


@dataclass(frozen=True)
class GitEntry:
    path: str
    mode: str
    blob_id: str
    size: int


def _run_git(repo: Path, *args: str, text: bool = True) -> str | bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
        errors="surrogateescape" if text else None,
    )
    return completed.stdout


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    payload = path.read_bytes()
    if b"\x00" not in payload:
        try:
            payload.decode("utf-8")
        except UnicodeDecodeError:
            pass
        else:
            payload = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return _sha256_bytes(payload)


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}:{hashlib.sha256(value.encode('utf-8')).hexdigest()[:20]}"


def _bounded(value: Any, limit: int = 600) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _jsonl_dump(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _status_map(repo: Path) -> tuple[dict[str, str], str]:
    raw = str(_run_git(repo, "status", "--porcelain=v1", "--untracked-files=all"))
    statuses: dict[str, str] = {}
    for line in raw.splitlines():
        if len(line) < 4:
            continue
        code, path = line[:2], line[3:].replace("\\", "/")
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        statuses[path] = code
    return statuses, _sha256_bytes(raw.encode("utf-8"))


def _git_entries(repo: Path) -> list[GitEntry]:
    raw = str(_run_git(repo, "ls-files", "--stage"))
    parsed: list[tuple[str, str, str]] = []
    blob_ids: list[str] = []
    for line in raw.splitlines():
        prefix, path = line.split("\t", 1)
        mode, blob_id, stage = prefix.split()
        if stage != "0":
            continue
        parsed.append((path.replace("\\", "/"), mode, blob_id))
        blob_ids.append(blob_id)
    batch = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "--batch-check=%(objectname) %(objectsize)"],
        input="\n".join(blob_ids) + "\n",
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    sizes = {line.split()[0]: int(line.split()[1]) for line in batch.splitlines() if line.strip()}
    return [GitEntry(path, mode, blob, sizes[blob]) for path, mode, blob in parsed]


def _privacy_family(path: str) -> str | None:
    if path in PRIVATE_REFERENCE_ONLY_PATHS:
        return None
    for prefix in PRIVACY_EXCLUDED_PREFIXES:
        if path.startswith(prefix):
            return prefix.rstrip("/") + "/**"
    if path.startswith("data/") and not path.startswith("data/digital_assets/"):
        return "data/non-asset/**"
    return None


def classify_candidate(path: str) -> str:
    lowered = path.lower()
    name = PurePosixPath(lowered).name
    if path in PRIVATE_REFERENCE_ONLY_PATHS:
        return "private-reference-only"
    if _privacy_family(path):
        return "rejected-or-unsafe"
    if "lesson" in lowered or "learning_loop" in lowered or "learning-loop" in lowered:
        return "lesson"
    if any(term in lowered for term in ("agent", "subagent", "orchestration", "assignment")):
        return "agent-or-subagent-definition"
    if any(term in lowered for term in ("workflow", "harness", "decision_flow", ".github/")):
        return "workflow-or-harness"
    if any(term in lowered for term in ("schema", "registry", "registries/")):
        return "schema-or-registry"
    if lowered.startswith("tests/") or name.startswith("test_") or any(
        term in lowered for term in ("validator", "validate_", "benchmark", "eval")
    ):
        return "test-or-evaluation-pack"
    if any(term in lowered for term in ("asset", "catalog", "graph")):
        return "digital-asset"
    if any(
        term in lowered
        for term in ("governance", "privacy", "security", "authority", "architecture", "policy", "contract")
    ):
        return "architecture-or-governance-pattern"
    if lowered.startswith(("apps/", "templates/", "config/", "scripts/")):
        return "unknown-pending-content-review"
    return "repo-specific-not-reusable"


def _copy_safety_errors(path: Path, source_root: Path) -> list[str]:
    data = path.read_bytes()
    if b"\x00" in data:
        return ["binary_content_not_allowed"]
    text = data.decode("utf-8", errors="replace")
    errors = [f"secret_pattern:{index}" for index, pattern in enumerate(SECRET_PATTERNS) if pattern.search(text)]
    forbidden_roots = {str(source_root), str(source_root.parent), str(Path.home())}
    normalized = text.replace("\\", "/").lower()
    for root in forbidden_roots:
        root_text = root.replace("\\", "/").lower()
        if root_text and root_text in normalized:
            errors.append("absolute_private_path")
            break
    return sorted(set(errors))


def _load_json(source_root: Path, relative: str) -> dict[str, Any]:
    payload = json.loads((source_root / relative).read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _knowledge_record(
    *,
    kind: str,
    source_id: str,
    source_path: str,
    title: str,
    summary: str,
    source_revision: str,
    file_hash: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record_id = f"dad:source-knowledge:albert:{kind}:{source_id.lower()}"
    dedupe_refs: list[str] = []
    dedupe_status = "no_exact_registered_identity_found"
    if source_id == "ALBERT-LESSON-072":
        dedupe_status = "deduplicated_as_source_provenance_for_existing_dad_rule"
        dedupe_refs = [
            "dad:learning-event:ci-unrelated-module-false-blocker:6631e5cb9401",
            "learning-rule:ci-tests-follow-declared-module-dependency-edges",
            "ci-module-boundary-governance",
            "skill:dad-ci-module-boundary-governance",
        ]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_id": record_id,
        "classification": kind,
        "source_id": source_id,
        "source_repository": SOURCE_REPOSITORY_ID,
        "source_path": source_path,
        "source_revision": source_revision,
        "source_file_sha256": file_hash,
        "title": _bounded(title, 240),
        "bounded_description": _bounded(summary),
        "applicability": _bounded((details or {}).get("applicability", "Human review required before reuse.")),
        "non_applicability": _bounded((details or {}).get("non_applicability", "Do not use as source-repository authority or automatic policy.")),
        "dependencies": list((details or {}).get("dependencies", [])),
        "reverse_consumers": list((details or {}).get("reverse_consumers", [])),
        "dedupe_status": dedupe_status,
        "dedupe_refs": dedupe_refs,
        "authority": "source_repository_authoritative_dad_candidate_snapshot",
        "privacy_classification": "internal_reusable_candidate",
        "license_status": "internal_only_review_required",
        "validation_status": "deterministically_extracted_unreviewed",
        "owner": OWNER,
        "freshness": "revision_bound",
        "supersession_state": "current_observed_candidate",
        "human_review_required": True,
        "review_status": "generated_candidate",
        "details": details or {},
    }


def _extract_knowledge(source_root: Path, revision: str, hashes: dict[str, str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    lesson_path = "AI_LEARNING_LOOP_LESSONS.md"
    for line in (source_root / lesson_path).read_text(encoding="utf-8").splitlines():
        if not re.match(r"^\| `ALBERT-LESSON-\d{3}` \|", line):
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if len(cells) < 8:
            continue
        records.append(
            _knowledge_record(
                kind="lesson",
                source_id=cells[0],
                source_path=lesson_path,
                title=cells[3],
                summary=cells[2],
                source_revision=revision,
                file_hash=hashes[lesson_path],
                details={
                    "tags": [tag.strip().strip("`") for tag in cells[1].split(",")],
                    "rule": _bounded(cells[3]),
                    "applicability": cells[4],
                    "non_applicability": cells[5],
                    "transfer_domains": _bounded(cells[6]),
                    "evidence_refs": _bounded(cells[7]),
                },
            )
        )

    monte_path = "AI_MONTE_CARLO_SIMULATOR_BUILD_LESSONS.md"
    heading_index = 0
    for line in (source_root / monte_path).read_text(encoding="utf-8").splitlines():
        if not line.startswith("## ") or line.startswith("## Table"):
            continue
        heading_index += 1
        title = line[3:].strip()
        records.append(
            _knowledge_record(
                kind="lesson",
                source_id=f"ALBERT-MONTE-CARLO-LESSON-{heading_index:02d}",
                source_path=monte_path,
                title=title,
                summary="Reusable simulator-build lesson section preserved in the approved source snapshot.",
                source_revision=revision,
                file_hash=hashes[monte_path],
            )
        )

    catalog_path = "config/digital_asset_catalog.json"
    catalog = _load_json(source_root, catalog_path)
    for item in catalog.get("assets", []):
        source_id = str(item.get("asset_id", "")).strip()
        if not source_id:
            continue
        records.append(
            _knowledge_record(
                kind="digital-asset",
                source_id=source_id,
                source_path=catalog_path,
                title=str(item.get("name", source_id)),
                summary=str(item.get("reuse_value", item.get("current_use", ""))),
                source_revision=revision,
                file_hash=hashes[catalog_path],
                details={
                    "category": item.get("category"),
                    "asset_type": item.get("asset_type"),
                    "maturity": item.get("maturity"),
                    "custody_boundary": _bounded(item.get("custody_boundary")),
                    "future_ai_use": _bounded(item.get("how_future_ai_should_use")),
                    "non_applicability": _bounded(item.get("do_not_use_for")),
                    "dependencies": [],
                    "source_dependency_count": len(item.get("paths", [])),
                    "source_dependency_paths_withheld": True,
                },
            )
        )

    for index, item in enumerate(catalog.get("high_compounding_asset_families", []), start=1):
        records.append(
            _knowledge_record(
                kind="digital-asset",
                source_id=f"asset-family:{index:02d}",
                source_path=catalog_path,
                title=str(item.get("family", f"Asset family {index}")),
                summary=str(item.get("why_high_leverage", "")),
                source_revision=revision,
                file_hash=hashes[catalog_path],
                details={"candidate_type": "asset_family"},
            )
        )

    for item in catalog.get("workflow_asset_patterns", []):
        source_id = str(item.get("pattern_id", "")).strip()
        if source_id:
            records.append(
                _knowledge_record(
                    kind="workflow-or-harness",
                    source_id=f"asset-pattern:{source_id}",
                    source_path=catalog_path,
                    title=str(item.get("name", source_id)),
                    summary=str(item.get("reuse_or_improve", "")),
                    source_revision=revision,
                    file_hash=hashes[catalog_path],
                    details={
                        "candidate_type": "workflow_asset_pattern",
                        "recognition_signals": item.get("recognition_signals", [])[:20],
                    },
                )
            )

    runtime_path = "config/albert_agent_runtime_orchestration.json"
    runtime = _load_json(source_root, runtime_path)
    for item in runtime.get("executor_adapters", []):
        source_id = str(item.get("adapter_id", "")).strip()
        if source_id:
            records.append(
                _knowledge_record(
                    kind="workflow-or-harness",
                    source_id=f"executor-adapter:{source_id}",
                    source_path=runtime_path,
                    title=source_id,
                    summary="Source-specific runtime adapter candidate retained as provider-neutral orchestration evidence, not an activated DAD adapter.",
                    source_revision=revision,
                    file_hash=hashes[runtime_path],
                    details={
                        "critical_task_eligible": item.get("critical_task_eligible"),
                        "requirements": item.get("requirements", [])[:20],
                    },
                )
            )
    for source_id, requirements in runtime.get("capability_profiles", {}).items():
        records.append(
            _knowledge_record(
                kind="agent-or-subagent-definition",
                source_id=f"capability-profile:{source_id}",
                source_path=runtime_path,
                title=source_id,
                summary="Source capability-profile candidate for bounded orchestration and model-retirement review.",
                source_revision=revision,
                file_hash=hashes[runtime_path],
                details={"requirements": requirements},
            )
        )
    for source_id, contract in runtime.get("mesh_roles", {}).items():
        records.append(
            _knowledge_record(
                kind="agent-or-subagent-definition",
                source_id=f"mesh-role:{source_id}",
                source_path=runtime_path,
                title=source_id,
                summary=str(contract.get("authority", "")),
                source_revision=revision,
                file_hash=hashes[runtime_path],
                details={
                    "may_approve_own_work": contract.get("may_approve_own_work"),
                    "may_override_validator": contract.get("may_override_validator"),
                },
            )
        )
    for item in runtime.get("task_classes", []):
        source_id = str(item.get("task_class", "")).strip()
        if source_id:
            records.append(
                _knowledge_record(
                    kind="workflow-or-harness",
                    source_id=f"task-class:{source_id}",
                    source_path=runtime_path,
                    title=source_id,
                    summary="Source task-class routing candidate; DAD capability tiers and current runtime qualification remain controlling.",
                    source_revision=revision,
                    file_hash=hashes[runtime_path],
                    details={
                        "critical": item.get("critical"),
                        "effort": item.get("effort"),
                        "worker_count": item.get("worker_count"),
                        "independent_checker_count": item.get("independent_checker_count"),
                    },
                )
            )

    role_path = "config/albert_subagent_decision_flow.json"
    decision_flow = _load_json(source_root, role_path)
    for item in decision_flow.get("roles", []):
        source_id = str(item.get("role_id", "")).strip()
        if source_id:
            records.append(
                _knowledge_record(
                    kind="agent-or-subagent-definition",
                    source_id=source_id,
                    source_path=role_path,
                    title=str(item.get("display_alias", source_id)),
                    summary=str(item.get("purpose", "")),
                    source_revision=revision,
                    file_hash=hashes[role_path],
                    details={"effort": item.get("effort"), "runtime_status": item.get("runtime_status")},
                )
            )

    for index, item in enumerate(decision_flow.get("routing_rules", []), start=1):
        records.append(
            _knowledge_record(
                kind="workflow-or-harness",
                source_id=f"routing-rule:{index:02d}",
                source_path=role_path,
                title=f"Routing rule {index:02d}: {item.get('primary_role_id', 'unknown')}",
                summary=str(item.get("when", "")),
                source_revision=revision,
                file_hash=hashes[role_path],
                details={
                    "primary_role_id": item.get("primary_role_id"),
                    "support_role_ids": item.get("support_role_ids", []),
                    "effort": item.get("effort"),
                },
            )
        )
    for item in decision_flow.get("decision_surfaces", []):
        source_id = str(item.get("surface_id", "")).strip()
        if source_id:
            records.append(
                _knowledge_record(
                    kind="workflow-or-harness",
                    source_id=f"decision-surface:{source_id}",
                    source_path=role_path,
                    title=source_id,
                    summary=str(item.get("promotion_boundary", "")),
                    source_revision=revision,
                    file_hash=hashes[role_path],
                    details={"required_artifacts": item.get("required_artifacts", [])[:20]},
                )
            )

    phase_path = "config/new_case_workflow_phases.json"
    for item in _load_json(source_root, phase_path).get("phase_order", []):
        source_id = str(item.get("phase_id", "")).strip()
        if source_id:
            records.append(
                _knowledge_record(
                    kind="workflow-or-harness",
                    source_id=source_id,
                    source_path=phase_path,
                    title=str(item.get("title", source_id)),
                    summary=str(item.get("purpose", "")),
                    source_revision=revision,
                    file_hash=hashes[phase_path],
                    details={"gate": _bounded(item.get("gate")), "expected_outputs": item.get("expected_outputs", [])[:20]},
                )
            )

    edge_path = "config/legal_case_edge_type_registry.json"
    legal_registry = _load_json(source_root, edge_path)
    for item in legal_registry.get("edge_types", []):
        source_id = str(item.get("edge_type", "")).strip()
        if source_id:
            records.append(
                _knowledge_record(
                    kind="schema-or-registry",
                    source_id=f"legal-edge:{source_id}",
                    source_path=edge_path,
                    title=source_id,
                    summary=str(item.get("description", "")),
                    source_revision=revision,
                    file_hash=hashes[edge_path],
                    details={
                        "family": item.get("family"),
                        "status": item.get("status"),
                        "source_anchor_required": item.get("source_anchor_required"),
                        "human_review_required_default": item.get("human_review_required_default"),
                        "promotion_boundary": _bounded(item.get("promotion_boundary")),
                    },
                )
            )

    for item in legal_registry.get("research_basis", []):
        source_id = str(item.get("basis_id", "")).strip()
        if source_id:
            records.append(
                _knowledge_record(
                    kind="schema-or-registry",
                    source_id=f"legal-research-basis:{source_id}",
                    source_path=edge_path,
                    title=source_id,
                    summary=str(item.get("note", "")),
                    source_revision=revision,
                    file_hash=hashes[edge_path],
                    details={
                        "source_url": item.get("source_url"),
                        "applies_to": item.get("applies_to", [])[:20],
                    },
                )
            )

    technique_path = "registries/litigation_witness_prep_technique_registry.v1.json"
    witness_registry = _load_json(source_root, technique_path)
    for item in witness_registry.get("techniques", []):
        source_id = str(item.get("id", "")).strip()
        if source_id:
            records.append(
                _knowledge_record(
                    kind="architecture-or-governance-pattern",
                    source_id=f"witness-prep:{source_id}",
                    source_path=technique_path,
                    title=str(item.get("name", source_id)),
                    summary=str(item.get("what", "")),
                    source_revision=revision,
                    file_hash=hashes[technique_path],
                    details={
                        "category": item.get("category"),
                        "repo_status": item.get("repo_status"),
                        "applicability": _bounded(item.get("when")),
                        "risk_if_misused": _bounded(item.get("risk_if_misused")),
                        "jurisdiction_note": _bounded(item.get("jurisdiction_note")),
                    },
                )
            )
    for index, item in enumerate(witness_registry.get("repo_findings", []), start=1):
        records.append(
            _knowledge_record(
                kind="architecture-or-governance-pattern",
                source_id=f"witness-registry-finding:{index:02d}",
                source_path=technique_path,
                title=f"Witness registry finding {index:02d}",
                summary=str(item.get("finding", "")),
                source_revision=revision,
                file_hash=hashes[technique_path],
                details={"status": item.get("status"), "source_refs_withheld": True},
            )
        )
    return sorted(records, key=lambda row: row["record_id"])


def _graph(
    inventory: list[dict[str, Any]], knowledge: list[dict[str, Any]], revision: str
) -> dict[str, Any]:
    repo_node = {
        "node_id": SOURCE_REPOSITORY_ID,
        "node_type": "source_repository",
        "label": SOURCE_DISPLAY_NAME,
        "review_status": "source_authority_reference",
        "privacy_classification": "internal",
    }
    policy_node = {
        "node_id": "policy:dad-source-knowledge-ingestion",
        "node_type": "governance_policy",
        "label": "DAD source knowledge ingestion policy",
        "review_status": "candidate",
        "privacy_classification": "internal",
    }
    revision_node = {
        "node_id": f"dad:source-revision:albert:{revision}",
        "node_type": "source_revision",
        "label": revision,
        "review_status": "observed_revision",
        "privacy_classification": "internal",
    }
    snapshot_node = {
        "node_id": "dad:source-knowledge-snapshot:albert:2026-07-16",
        "node_type": "source_snapshot",
        "label": "Albert governed knowledge snapshot 2026-07-16",
        "review_status": "generated_candidate",
        "privacy_classification": "internal",
    }
    nodes: list[dict[str, Any]] = [repo_node, policy_node, revision_node, snapshot_node]
    edges: list[dict[str, Any]] = []
    edges.append(
        {
            "edge_id": _stable_id("edge", f"{snapshot_node['node_id']}|source_snapshot_of|{revision_node['node_id']}"),
            "source": snapshot_node["node_id"],
            "target": revision_node["node_id"],
            "edge_type": "source_snapshot_of",
            "evidence_refs": [revision],
            "review_status": "candidate",
        }
    )
    artifact_by_path: dict[str, str] = {}
    for row in inventory:
        path = row.get("source_path")
        if not path or row["classification"] == "rejected-or-unsafe":
            continue
        node_id = row["record_id"]
        artifact_by_path[str(path)] = node_id
        nodes.append(
            {
                "node_id": node_id,
                "node_type": "source_artifact_candidate",
                "label": str(path),
                "classification": row["classification"],
                "review_status": row["review_status"],
                "privacy_classification": row["privacy_classification"],
            }
        )
        edges.append(
            {
                "edge_id": _stable_id("edge", f"{SOURCE_REPOSITORY_ID}|contains|{node_id}"),
                "source": SOURCE_REPOSITORY_ID,
                "target": node_id,
                "edge_type": "contains",
                "evidence_refs": [row["record_id"]],
                "review_status": "candidate",
            }
        )
    for row in knowledge:
        node_id = row["record_id"]
        nodes.append(
            {
                "node_id": node_id,
                "node_type": row["classification"],
                "label": row["title"],
                "review_status": row["review_status"],
                "privacy_classification": row["privacy_classification"],
                "dedupe_status": row["dedupe_status"],
            }
        )
        source_node = artifact_by_path.get(row["source_path"])
        if source_node:
            edges.append(
                {
                    "edge_id": _stable_id("edge", f"{node_id}|extracted_from|{source_node}"),
                    "source": node_id,
                    "target": source_node,
                    "edge_type": "extracted_from",
                    "evidence_refs": [row["source_path"], row["source_file_sha256"]],
                    "review_status": "candidate",
                }
            )
        for ref in row["dedupe_refs"]:
            target = f"dad-reference:{ref}"
            if not any(node["node_id"] == target for node in nodes):
                nodes.append(
                    {
                        "node_id": target,
                        "node_type": "dad_registered_reference",
                        "label": ref,
                        "review_status": "registered_reference",
                        "privacy_classification": "internal",
                    }
                )
            edges.append(
                {
                    "edge_id": _stable_id("edge", f"{node_id}|possible_duplicate_of|{target}"),
                    "source": node_id,
                    "target": target,
                    "edge_type": "possible_duplicate_of",
                    "evidence_refs": [row["record_id"]],
                    "review_status": "human_review_required",
                }
            )
    edges.append(
        {
            "edge_id": _stable_id("edge", "repo|governed_by|source-ingestion-policy"),
            "source": SOURCE_REPOSITORY_ID,
            "target": policy_node["node_id"],
            "edge_type": "governed_by",
            "evidence_refs": ["assets/source-knowledge-ingestion/policy.json"],
            "review_status": "candidate",
        }
    )
    unique_nodes = {node["node_id"]: node for node in nodes}
    return {
        "schema_version": "dad.source_knowledge_graph.v1",
        "graph_id": "dad:source-knowledge-graph:albert",
        "source_repository": SOURCE_REPOSITORY_ID,
        "source_revision": revision,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "nodes": [unique_nodes[key] for key in sorted(unique_nodes)],
        "edges": sorted(edges, key=lambda row: row["edge_id"]),
        "review_status": "generated_candidate",
    }


def build_snapshot(source_root: Path, destination: Path) -> dict[str, Any]:
    source_root = source_root.resolve()
    destination = destination.resolve()
    head_before = str(_run_git(source_root, "rev-parse", "HEAD")).strip()
    branch = str(_run_git(source_root, "branch", "--show-current")).strip()
    statuses, status_digest_before = _status_map(source_root)
    entries = _git_entries(source_root)
    entry_by_path = {entry.path: entry for entry in entries}

    inventory: list[dict[str, Any]] = []
    exclusion_counts: Counter[str] = Counter()
    classification_counts: Counter[str] = Counter()
    approved_read_hashes: dict[str, str] = {}
    sanitization_findings: dict[str, list[str]] = {}
    copied_hashes: dict[str, str] = {}
    copy_errors: dict[str, list[str]] = {}

    for entry in entries:
        privacy_family = _privacy_family(entry.path)
        classification = classify_candidate(entry.path)
        classification_counts[classification] += 1
        if privacy_family:
            exclusion_counts[privacy_family] += 1
            source_path: str | None = None
            source_path_hash = _sha256_bytes(entry.path.encode("utf-8"))
            disposition = "privacy_excluded_metadata_only"
            privacy = "restricted_path_opaque_metadata_only"
        else:
            source_path = entry.path
            source_path_hash = _sha256_bytes(entry.path.encode("utf-8"))
            disposition = "candidate_metadata_only"
            privacy = "internal_reusable_candidate"
        record_id = _stable_id("dad:source-artifact:albert", entry.path)
        inventory.append(
            {
                "schema_version": SCHEMA_VERSION,
                "record_id": record_id,
                "source_repository": SOURCE_REPOSITORY_ID,
                "source_revision": head_before,
                "source_path": source_path,
                "source_path_sha256": source_path_hash,
                "privacy_family": privacy_family,
                "git_blob_id": f"git-sha1:{entry.blob_id}",
                "git_blob_size": entry.size,
                "worktree_status": statuses.get(entry.path, "  "),
                "classification": classification,
                "disposition": disposition,
                "authority": "source_repository_authoritative_dad_observation",
                "privacy_classification": privacy,
                "bounded_description": (
                    f"Opaque {privacy_family} source item; content and path withheld."
                    if privacy_family
                    else f"{classification} candidate at the declared source-relative path."
                ),
                "applicability": "Candidate for bounded human review only.",
                "non_applicability": "Not source truth, adopted policy, public-release content, or downstream mutation authority.",
                "dependencies": [],
                "reverse_consumers": [],
                "evidence_status": "git_index_metadata_observed",
                "owner": OWNER,
                "freshness": "revision_bound",
                "supersession_state": "current_observed_candidate",
                "human_review_required": True,
                "review_status": "generated_candidate",
            }
        )

    for relative in APPROVED_READ_PATHS:
        source = source_root / relative
        if not source.exists() or not source.is_file():
            sanitization_findings[relative] = ["approved_path_missing"]
            continue
        approved_read_hashes[relative] = _sha256_file(source)
        findings = _copy_safety_errors(source, source_root)
        if findings:
            sanitization_findings[relative] = findings
        matching = next((row for row in inventory if row.get("source_path") == relative), None)
        if matching:
            matching["content_sha256"] = approved_read_hashes[relative]
            matching["disposition"] = "normalized_extract_and_hash_only"
            matching["evidence_status"] = "approved_content_read_hash_verified"

    copies_root = destination / "copies"
    if copies_root.exists():
        shutil.rmtree(copies_root)
    for relative in APPROVED_COPY_PATHS:
        source = source_root / relative
        if not source.exists() or not source.is_file():
            copy_errors[relative] = ["approved_path_missing"]
            continue
        errors = _copy_safety_errors(source, source_root)
        if errors:
            copy_errors[relative] = errors
            continue
        target = copies_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied_hashes[relative] = _sha256_file(target)
        matching = next((row for row in inventory if row.get("source_path") == relative), None)
        if matching:
            matching["disposition"] = "exact_internal_candidate_snapshot"
            matching["content_sha256"] = copied_hashes[relative]
            matching["evidence_status"] = "content_allowlisted_hash_verified"
        elif relative in statuses and statuses[relative] == "??":
            classification = classify_candidate(relative)
            inventory.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "record_id": _stable_id("dad:source-artifact:albert", relative),
                    "source_repository": SOURCE_REPOSITORY_ID,
                    "source_revision": head_before,
                    "source_path": relative,
                    "source_path_sha256": _sha256_bytes(relative.encode("utf-8")),
                    "privacy_family": None,
                    "git_blob_id": None,
                    "git_blob_size": source.stat().st_size,
                    "worktree_status": "??",
                    "classification": classification,
                    "disposition": "exact_internal_candidate_snapshot_untracked",
                    "content_sha256": copied_hashes[relative],
                    "authority": "source_worktree_candidate_dad_observation",
                    "privacy_classification": "internal_reusable_candidate",
                    "bounded_description": f"Untracked {classification} candidate at the declared source-relative path.",
                    "applicability": "Provisional evidence only; source commit and human review required.",
                    "non_applicability": "Not source truth, adopted policy, public-release content, or downstream mutation authority.",
                    "dependencies": [],
                    "reverse_consumers": [],
                    "evidence_status": "content_allowlisted_hash_verified_untracked",
                    "owner": OWNER,
                    "freshness": "dirty_worktree_revision_bound",
                    "supersession_state": "provisional_untracked_candidate",
                    "human_review_required": True,
                    "review_status": "generated_candidate",
                }
            )
            classification_counts[classification] += 1

    required_parse_paths = {
        "AI_LEARNING_LOOP_LESSONS.md",
        "AI_MONTE_CARLO_SIMULATOR_BUILD_LESSONS.md",
        "config/digital_asset_catalog.json",
        "config/albert_subagent_decision_flow.json",
        "config/new_case_workflow_phases.json",
        "config/legal_case_edge_type_registry.json",
        "registries/litigation_witness_prep_technique_registry.v1.json",
    }
    missing_parse = sorted(required_parse_paths - approved_read_hashes.keys())
    if missing_parse:
        raise ValueError(f"Required approved parse paths were not safely copied: {missing_parse}")
    knowledge = _extract_knowledge(source_root, head_before, approved_read_hashes)
    inventory = sorted(inventory, key=lambda row: row["record_id"])
    graph = _graph(inventory, knowledge, head_before)

    destination.mkdir(parents=True, exist_ok=True)
    _jsonl_dump(destination / "inventory.jsonl", inventory)
    _jsonl_dump(destination / "knowledge-records.jsonl", knowledge)
    _json_dump(destination / "knowledge-graph.json", graph)

    head_after = str(_run_git(source_root, "rev-parse", "HEAD")).strip()
    _, status_digest_after = _status_map(source_root)
    if head_after != head_before or status_digest_after != status_digest_before:
        raise RuntimeError("Source repository changed during read-only ingestion")

    outputs = {
        "inventory": "inventory.jsonl",
        "knowledge_records": "knowledge-records.jsonl",
        "knowledge_graph": "knowledge-graph.json",
        "copies_root": "copies",
    }
    output_hashes = {
        name: _sha256_file(destination / relative)
        for name, relative in outputs.items()
        if name != "copies_root"
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_id": "dad:source-knowledge-snapshot:albert:2026-07-16",
        "source_repository": SOURCE_REPOSITORY_ID,
        "source_display_name": SOURCE_DISPLAY_NAME,
        "source_revision": head_before,
        "source_branch_observed": branch,
        "source_worktree_status_sha256": status_digest_before,
        "source_mutated": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "privacy_policy": {
            "excluded_content_read_count": 0,
            "excluded_inventory_source_paths_persisted": 0,
            "excluded_records_use_opaque_path_hashes": True,
            "private_workspace_enumerated": False,
            "private_workspace_content_copied": False,
        },
        "license_status": "internal_only_source_license_review_required_before_export_or_promotion",
        "tracked_path_count": len(entries),
        "inventory_record_count": len(inventory),
        "privacy_excluded_count": sum(exclusion_counts.values()),
        "candidate_count": len(entries) - sum(exclusion_counts.values()),
        "classification_counts": dict(sorted(classification_counts.items())),
        "privacy_exclusion_family_counts": dict(sorted(exclusion_counts.items())),
        "approved_copy_count": len(copied_hashes),
        "approved_copy_hashes": dict(sorted(copied_hashes.items())),
        "approved_read_count": len(approved_read_hashes),
        "approved_read_hashes": dict(sorted(approved_read_hashes.items())),
        "sanitization_findings": dict(sorted(sanitization_findings.items())),
        "copy_rejections": copy_errors,
        "knowledge_record_count": len(knowledge),
        "knowledge_record_counts": dict(sorted(Counter(row["classification"] for row in knowledge).items())),
        "graph_node_count": len(graph["nodes"]),
        "graph_edge_count": len(graph["edges"]),
        "outputs": outputs,
        "output_hashes": output_hashes,
        "human_review_required": True,
        "promotion_status": "not_promoted_candidate_only",
        "review_status": "generated_candidate",
        "generated_by": "src/digital_asset_directory/source_knowledge_ingestion.py",
    }
    _json_dump(destination / "manifest.json", manifest)
    return manifest


def validate_snapshot(destination: Path) -> dict[str, Any]:
    destination = destination.resolve()
    errors: list[str] = []
    manifest_path = destination / "manifest.json"
    if not manifest_path.exists():
        return {"valid": False, "errors": ["manifest_missing"]}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    inventory = [json.loads(line) for line in (destination / "inventory.jsonl").read_text(encoding="utf-8").splitlines() if line]
    knowledge = [json.loads(line) for line in (destination / "knowledge-records.jsonl").read_text(encoding="utf-8").splitlines() if line]
    graph = json.loads((destination / "knowledge-graph.json").read_text(encoding="utf-8"))
    if len(inventory) != manifest.get("inventory_record_count"):
        errors.append("inventory_count_mismatch")
    if len(knowledge) != manifest.get("knowledge_record_count"):
        errors.append("knowledge_count_mismatch")
    if len(graph.get("nodes", [])) != manifest.get("graph_node_count"):
        errors.append("graph_node_count_mismatch")
    if len(graph.get("edges", [])) != manifest.get("graph_edge_count"):
        errors.append("graph_edge_count_mismatch")
    if manifest.get("privacy_policy", {}).get("excluded_content_read_count") != 0:
        errors.append("excluded_content_read")
    if manifest.get("privacy_policy", {}).get("excluded_inventory_source_paths_persisted") != 0:
        errors.append("excluded_inventory_source_path_persisted")
    for row in inventory:
        if row.get("privacy_family") and row.get("source_path"):
            errors.append(f"excluded_source_path_exposed:{row['record_id']}")
        if row.get("review_status") != "generated_candidate":
            errors.append(f"unexpected_promotion:{row['record_id']}")
    for relative, expected in manifest.get("approved_copy_hashes", {}).items():
        copy_path = destination / "copies" / relative
        if not copy_path.exists() or _sha256_file(copy_path) != expected:
            errors.append(f"copy_hash_mismatch:{relative}")
    for name, relative in manifest.get("outputs", {}).items():
        if name == "copies_root":
            continue
        expected = manifest.get("output_hashes", {}).get(name)
        if expected and _sha256_file(destination / relative) != expected:
            errors.append(f"output_hash_mismatch:{name}")
    node_ids = {node.get("node_id") for node in graph.get("nodes", [])}
    for edge in graph.get("edges", []):
        if edge.get("source") not in node_ids or edge.get("target") not in node_ids:
            errors.append(f"dangling_graph_edge:{edge.get('edge_id')}")
    lesson_072 = next((row for row in knowledge if row.get("source_id") == "ALBERT-LESSON-072"), None)
    if not lesson_072 or "learning-rule:ci-tests-follow-declared-module-dependency-edges" not in lesson_072.get("dedupe_refs", []):
        errors.append("ci_lesson_dedupe_missing")
    if manifest.get("promotion_status") != "not_promoted_candidate_only":
        errors.append("candidate_promotion_boundary_missing")
    return {
        "schema_version": "dad.source_knowledge_ingestion_validation.v1",
        "valid": not errors,
        "errors": sorted(set(errors)),
        "tracked_path_count": manifest.get("tracked_path_count"),
        "candidate_count": manifest.get("candidate_count"),
        "privacy_excluded_count": manifest.get("privacy_excluded_count"),
        "knowledge_record_count": len(knowledge),
        "graph_node_count": len(graph.get("nodes", [])),
        "graph_edge_count": len(graph.get("edges", [])),
    }
