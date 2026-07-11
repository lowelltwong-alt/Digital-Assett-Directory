from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

import yaml

from .transport import data_path
from .utils import atomic_write_text, json_dumps, sha256_file, utc_now


LOGOS_LLOS_SURFACES: dict[str, tuple[str, ...]] = {
    "logos-governance-architecture": (
        "governance/LOGOS_LEARNING_LOOP_OPERATING_STANDARD.yaml",
        "governance/registry/LLOS_ROUTE_REGISTRY.yaml",
    ),
    "logos-scripture-graph": (
        ".ai/control/llos_v1_adapter.yaml",
    ),
    "logos-boundary-literature": (
        "governance/LLOS_STANDARD_MIRROR.yaml",
        "governance/LLOS_LESSON_INDEX.yaml",
    ),
    "logos-doctrine-genealogy": (
        "governance/llos_v1_adapter.yaml",
        "governance/llos_v1_lesson_index.yaml",
    ),
}
POLICY_PATH = ".digital-asset/dad-write-policy.json"
REPORT_NAME = "logos_llos_audit.json"
EXPECTED_UPSTREAM = "governance/LOGOS_LEARNING_LOOP_OPERATING_STANDARD.yaml"


def _governed_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    merged: dict[str, Any] = {}
    for value in yaml.safe_load_all(text):
        if isinstance(value, dict):
            merged.update(value)
    return merged


def _surface_version(payload: dict[str, Any]) -> str:
    upstream = payload.get("upstream_standard") or payload.get("upstream_governance")
    upstream = upstream if isinstance(upstream, dict) else {}
    return str(
        payload.get("surface_version")
        or payload.get("llos_surface_version")
        or upstream.get("surface_version")
        or payload.get("source_contract", {}).get("surface_version")
        or ""
    )


def _is_false(mapping: Any, *keys: str) -> bool:
    return isinstance(mapping, dict) and all(mapping.get(key) is False for key in keys)


def _semantic_errors(repo_id: str, relative: str, payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if repo_id == "logos-governance-architecture":
        if relative.endswith("LOGOS_LEARNING_LOOP_OPERATING_STANDARD.yaml"):
            if payload.get("schema_version") != "logos.llos.standard.v1" or payload.get("standard_id") != "LLOS-v1":
                errors.append("invalid canonical LLOS identity")
            if not _is_false(
                payload.get("dad_bridge"),
                "write_inside_logos_repo", "deliver_to_logos_inbox",
                "mutate_logos_contract", "mutate_logos_index",
            ):
                errors.append("canonical DAD bridge is not deny-write")
            if not _is_false(
                payload.get("communication"),
                "dad_push_to_logos_allowed", "dad_direct_logos_inbox_write_allowed",
                "candidate_return_authorizes_local_change",
            ):
                errors.append("canonical communication boundary is unsafe")
        else:
            routes = payload.get("routes")
            if (
                payload.get("schema_version") != "logos.llos.routes.v1"
                or not isinstance(routes, dict)
                or set(routes) != {"governance", "scripture", "boundary", "doctrine", "dad_candidate"}
                or not all(isinstance(value, dict) for value in routes.values())
            ):
                errors.append("invalid canonical route registry")
        return errors

    upstream = payload.get("upstream_standard") or payload.get("upstream_governance")
    upstream = upstream if isinstance(upstream, dict) else {}
    upstream_repo = upstream.get("repo") or upstream.get("repository")
    if relative.lower().endswith(("adapter.yaml", "mirror.yaml")):
        if upstream_repo != "logos-governance-architecture" or upstream.get("path") != EXPECTED_UPSTREAM:
            errors.append("adapter upstream identity or path is invalid")

    if repo_id == "logos-scripture-graph":
        if payload.get("object_type") != "scripture_llos_v1_adapter":
            errors.append("invalid Scripture adapter identity")
        dad = payload.get("asymmetric_transport_boundary", {}).get("dad_central", {})
        if not _is_false(dad, "may_push_or_write_any_file_into_logos", "may_write_logos_inbox"):
            errors.append("Scripture DAD boundary is unsafe")
        if not _is_false(payload.get("authority"), "authorizes_dad_write_to_logos", "authorizes_scripture_data_change"):
            errors.append("Scripture authority boundary is unsafe")
    elif repo_id == "logos-boundary-literature":
        if relative.endswith("LLOS_STANDARD_MIRROR.yaml"):
            if payload.get("object_type") != "llos_standard_mirror":
                errors.append("invalid Boundary adapter identity")
            if not _is_false(payload.get("dad_bridge"), "dad_may_write_inside_logos_repo", "dad_may_deliver_to_logos_inbox"):
                errors.append("Boundary DAD bridge is unsafe")
            if not _is_false(payload.get("authority"), "authorizes_source_import", "authorizes_canonical_authority", "authorizes_cross_repo_override"):
                errors.append("Boundary authority boundary is unsafe")
        elif payload.get("object_type") != "llos_lesson_index" or payload.get("lessons") != []:
            errors.append("invalid Boundary lesson index")
    elif repo_id == "logos-doctrine-genealogy":
        if relative.endswith("llos_v1_adapter.yaml"):
            if payload.get("object_type") != "llos_v1_adapter":
                errors.append("invalid Doctrine adapter identity")
            if not _is_false(payload.get("dad_bridge"), "may_write_doctrine_files", "may_push_or_write_logos_inbox"):
                errors.append("Doctrine DAD bridge is unsafe")
            if not _is_false(payload.get("authority"), "authorizes_runtime_adapters", "authorizes_data_authority", "authorizes_theology_authority"):
                errors.append("Doctrine authority boundary is unsafe")
        elif payload.get("object_type") != "llos_v1_lesson_index" or payload.get("lessons") != []:
            errors.append("invalid Doctrine lesson index")
    return errors


def _roots_overlap(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def audit_logos_llos(hub_root: Path, repo_policies: Sequence[Any]) -> dict[str, Any]:
    """Read reviewed LLOS control files and write only a central metadata report."""

    policy_by_id = {str(getattr(row, "id", "")): row for row in repo_policies}
    rows: list[dict[str, Any]] = []
    for repo_id, relatives in LOGOS_LLOS_SURFACES.items():
        policy = policy_by_id.get(repo_id)
        if policy is None:
            rows.append({"repo_id": repo_id, "status": "not_configured", "files": []})
            continue
        communication_root = Path(getattr(policy, "path")).resolve()
        raw_control_root = getattr(policy, "llos_control_path", None)
        configured_control_root = str(raw_control_root).strip() if raw_control_root is not None else ""
        if not configured_control_root:
            rows.append(
                {
                    "repo_id": repo_id,
                    "control_root_source": "unconfigured",
                    "status": "upgrade_required",
                    "surface_versions": [],
                    "missing_paths": list(relatives),
                    "semantic_errors": ["llos_control_path is required for Logos audits"],
                    "dad_write_policy": "missing_or_unsafe",
                    "files": [
                        {"path": relative, "status": "control_root_unconfigured"}
                        for relative in relatives
                    ],
                }
            )
            continue
        repo_root = Path(configured_control_root).resolve()
        if _roots_overlap(communication_root, repo_root):
            rows.append(
                {
                    "repo_id": repo_id,
                    "control_root_source": "invalid_llos_control_path",
                    "status": "upgrade_required",
                    "surface_versions": [],
                    "missing_paths": list(relatives),
                    "semantic_errors": [
                        "llos_control_path must be distinct from and outside the live communication root"
                    ],
                    "dad_write_policy": "missing_or_unsafe",
                    "files": [
                        {"path": relative, "status": "control_root_unsafe"}
                        for relative in relatives
                    ],
                }
            )
            continue
        files: list[dict[str, Any]] = []
        versions: set[str] = set()
        semantic_errors: list[str] = []
        for relative in relatives:
            path = repo_root / relative
            if not path.is_file():
                files.append({"path": relative, "status": "missing"})
                continue
            try:
                payload = _governed_yaml(path)
            except (OSError, UnicodeError, yaml.YAMLError):
                error = "unreadable or invalid YAML"
                semantic_errors.append(f"{relative}: {error}")
                files.append(
                    {
                        "path": relative,
                        "status": "invalid",
                        "semantic_errors": [error],
                    }
                )
                continue
            version = _surface_version(payload)
            if version:
                versions.add(version)
            file_errors = _semantic_errors(repo_id, relative, payload)
            semantic_errors.extend(f"{relative}: {error}" for error in file_errors)
            files.append(
                {
                    "path": relative,
                    "status": "present",
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                    "surface_version": version,
                    "semantic_errors": file_errors,
                }
            )
        marker = repo_root / POLICY_PATH
        marker_payload: dict[str, Any] = {}
        if marker.is_file():
            try:
                parsed = json.loads(marker.read_text(encoding="utf-8"))
                marker_payload = parsed if isinstance(parsed, dict) else {}
            except (OSError, json.JSONDecodeError):
                marker_payload = {}
        marker_ok = (
            marker_payload.get("schema_version") == "dad.logos.write-policy.v1"
            and marker_payload.get("repo_id") == repo_id
            and marker_payload.get("dad_write_allowed") is False
            and marker_payload.get("approved_explicit_approval_ids") == []
            and marker_payload.get("approval_mode") == "fresh_explicit_owner_approval"
            and marker_payload.get("logos_local_outbox_write_allowed") is True
            and marker_payload.get("logos_local_dad_central_read_allowed") is True
            and marker_payload.get("dad_read_approved_metadata_allowed") is True
            and marker_payload.get("dad_push_or_inbox_write_allowed") is False
            and marker_payload.get("rollout_approval_is_standing_write_permission") is False
        )
        missing = [item["path"] for item in files if item["status"] == "missing"]
        rows.append(
            {
                "repo_id": repo_id,
                "control_root_source": "llos_control_path",
                "status": "current" if not missing and not semantic_errors and versions == {"1.0.0"} and marker_ok else "upgrade_required",
                "surface_versions": sorted(versions),
                "missing_paths": missing,
                "semantic_errors": semantic_errors,
                "dad_write_policy": "blocked" if marker_ok else "missing_or_unsafe",
                "files": files,
            }
        )

    report = {
        "schema_version": "dad.logos.llos-audit.v1",
        "generated_at": utc_now(),
        "expected_surface_version": "1.0.0",
        "repos": rows,
        "current_count": sum(row["status"] == "current" for row in rows),
        "upgrade_required_count": sum(row["status"] != "current" for row in rows),
        "source_write_count": 0,
        "authority_boundary": (
            "This audit reads only reviewed Logos control paths and writes only to DAD_DATA_ROOT. "
            "It cannot modify, deliver to, admit for, or authorize any Logos repository."
        ),
    }
    report_path = data_path(hub_root, "central_reports") / REPORT_NAME
    atomic_write_text(report_path, json_dumps(report, pretty=True) + "\n")
    return {**report, "report_path": str(report_path)}
