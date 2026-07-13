"""Validate one task-local agent mesh manifest and optional prior revision."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema


class ManifestValidationError(ValueError):
    """Raised when semantic mesh invariants fail."""


MATERIAL_ROLE_FIELDS = (
    "mission",
    "inputs",
    "dependencies",
    "authority",
    "acceptance_conditions",
    "stop_conditions",
    "handoff",
)


def canonical_digest(manifest: dict[str, Any]) -> str:
    payload = {key: value for key, value in manifest.items() if key != "manifest_digest"}
    data = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ManifestValidationError(f"duplicate {label}")


def _assert_acyclic(roles: dict[str, dict[str, Any]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(role_id: str) -> None:
        if role_id in visiting:
            raise ManifestValidationError("role dependency graph contains a cycle")
        if role_id in visited:
            return
        visiting.add(role_id)
        for dependency in roles[role_id]["dependencies"]:
            visit(dependency)
        visiting.remove(role_id)
        visited.add(role_id)

    for role_id in sorted(roles):
        visit(role_id)


def _base_semantics(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    roles = {role["role_id"]: role for role in manifest["roles"]}
    if len(roles) != len(manifest["roles"]):
        raise ManifestValidationError("duplicate role_id")
    writer = manifest["writer_role_id"]
    checker = manifest["checker_role_id"]
    if writer == checker:
        raise ManifestValidationError("writer and checker must be distinct")
    if writer not in roles or checker not in roles:
        raise ManifestValidationError("writer or checker role is missing")
    declared_writers = [role_id for role_id, role in roles.items() if role["writer_checker_relation"] == "writer"]
    declared_checkers = [role_id for role_id, role in roles.items() if role["writer_checker_relation"] == "checker"]
    if declared_writers != [writer] or declared_checkers != [checker]:
        raise ManifestValidationError("writer/checker relation conflicts with declared identities")
    for role_id, role in roles.items():
        unknown = set(role["dependencies"]) - set(roles)
        if unknown or role_id in role["dependencies"]:
            raise ManifestValidationError(f"invalid dependencies for role {role_id}")
        recipients = set(role["handoff"]["recipient_role_ids"])
        if not recipients <= set(roles):
            raise ManifestValidationError(f"unknown handoff recipient for role {role_id}")
    _assert_acyclic(roles)
    obligation_ids = [row["obligation_id"] for row in manifest["proof_obligations"]]
    _unique(obligation_ids, "proof obligation ID")
    for row in manifest["proof_obligations"]:
        if row["owner_role_id"] not in roles or row["checker_role_id"] not in roles:
            raise ManifestValidationError("proof obligation references unknown role")
        if row["owner_role_id"] == row["checker_role_id"]:
            raise ManifestValidationError("proof obligation cannot be self-checked")
        if row["checker_role_id"] != checker:
            raise ManifestValidationError(
                "proof obligation checker must equal the top-level checker role"
            )
    _unique([row["decision_id"] for row in manifest["unresolved_decisions"]], "decision ID")
    return roles


def _validate_prior(
    current: dict[str, Any], prior: dict[str, Any], current_roles: dict[str, dict[str, Any]]
) -> None:
    if current["mesh_id"] != prior["mesh_id"] or current["task_id"] != prior["task_id"]:
        raise ManifestValidationError("current and prior mesh/task identity conflict")
    if current.get("supersedes_revision_id") != prior["revision_id"]:
        raise ManifestValidationError("current revision must supersede the exact prior revision")
    if current["revision_id"] == prior["revision_id"]:
        raise ManifestValidationError("current revision_id must be new")
    reconciliations = current.get("reconciliations")
    if not isinstance(reconciliations, list):
        raise ManifestValidationError("--prior requires reconciliations")
    prior_roles = {role["role_id"]: role for role in prior["roles"]}
    seen_prior: set[str] = set()
    seen_current: set[str] = set()
    for row in reconciliations:
        disposition = row["disposition"]
        prior_id = row.get("prior_role_id")
        current_ids = row["current_role_ids"]
        if disposition == "added":
            if prior_id is not None or not current_ids or any(item in prior_roles for item in current_ids):
                raise ManifestValidationError("added reconciliation must name only new current roles")
        else:
            if prior_id not in prior_roles or prior_id in seen_prior:
                raise ManifestValidationError("each prior role must be reconciled exactly once")
            seen_prior.add(prior_id)
        if any(item not in current_roles or item in seen_current for item in current_ids):
            raise ManifestValidationError("current role reconciliation conflict")
        seen_current.update(current_ids)
        if disposition == "reused" and current_ids != [prior_id]:
            raise ManifestValidationError("reused role must preserve its role ID")
        if disposition == "replaced" and (
            len(current_ids) != 1 or any(item in prior_roles for item in current_ids)
        ):
            raise ManifestValidationError(
                "replaced role must map to exactly one new current role"
            )
        if disposition == "split" and (
            len(current_ids) < 2 or any(item in prior_roles for item in current_ids)
        ):
            raise ManifestValidationError(
                "split role must map to at least two new child roles"
            )
        if disposition == "removed" and current_ids:
            raise ManifestValidationError("removed role cannot name a current role")
        if disposition == "blocked" and current_ids != [prior_id]:
            raise ManifestValidationError("blocked role must preserve its role ID")
        if disposition in {"replaced", "split", "removed", "added"} and not row[
            "material_drift"
        ]:
            raise ManifestValidationError(
                f"{disposition} reconciliation requires material_drift=true"
            )
        if disposition == "reused":
            changed = any(prior_roles[prior_id][field] != current_roles[prior_id][field] for field in MATERIAL_ROLE_FIELDS)
            if changed != row["material_drift"]:
                raise ManifestValidationError("material role drift flag does not match changed contract")
    if seen_prior != set(prior_roles):
        raise ManifestValidationError("missing prior role reconciliation")
    if seen_current != set(current_roles):
        raise ManifestValidationError("every current role must be reconciled exactly once")


def validate_manifest(
    manifest: dict[str, Any], schema: dict[str, Any], *, prior: dict[str, Any] | None = None,
    check_digest: bool = True,
) -> str:
    jsonschema.Draft202012Validator(schema).validate(manifest)
    roles = _base_semantics(manifest)
    digest = canonical_digest(manifest)
    if check_digest and manifest["manifest_digest"] != digest:
        raise ManifestValidationError("manifest_digest mismatch")
    if prior is not None:
        jsonschema.Draft202012Validator(schema).validate(prior)
        _base_semantics(prior)
        if prior["manifest_digest"] != canonical_digest(prior):
            raise ManifestValidationError("prior manifest_digest mismatch")
        _validate_prior(manifest, prior, roles)
    return digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--prior", type=Path)
    parser.add_argument("--schema", type=Path, default=Path(__file__).parents[1] / "references/agent-mesh-manifest.schema.json")
    parser.add_argument("--print-digest", action="store_true")
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        schema = json.loads(args.schema.read_text(encoding="utf-8"))
        prior = json.loads(args.prior.read_text(encoding="utf-8")) if args.prior else None
        digest = validate_manifest(manifest, schema, prior=prior, check_digest=not args.print_digest)
    except (OSError, json.JSONDecodeError, jsonschema.ValidationError, ManifestValidationError) as exc:
        print(json.dumps({"status": "invalid", "reason": str(exc)}), file=sys.stderr)
        return 1
    if args.print_digest:
        print(digest)
    else:
        print(json.dumps({"status": "valid", "manifest_digest": digest}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
