"""Inert Codex adapter for local campaign execution-control qualification.

The adapter reads repository-local evidence and the existing Portfolio OS
projection, then calls the provider-neutral bridge. It has no launch command
and cannot invoke Codex, a shell, Git, a network, or a downstream repository.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Mapping

from .campaign_controller import (
    COHORT_PARENT_IDS,
    EVIDENCE_SNAPSHOT_SCHEMA,
    build_campaign_dry_run,
    build_cohort_reconciliation_projection,
    build_navigation_projection,
    build_stop_checkpoint,
    canonical_digest,
    evidence_snapshot_digest,
    file_digest,
    flatten_campaign_jobs,
    load_campaign_manifest,
    materialize_atomic_child,
    validate_cohort_reconciliation_projection,
)
from .portfolio_execution import (
    campaign_runtime_state_from_projection,
    load_execution_control,
)


adapter_id = "adapter:codex-host"
revision = "dad-campaign-codex-shell-adapter:0.3.0-prelaunch"
AUTHORITY_BOUNDARY = (
    "This manual host adapter normalizes inert, repository-local candidate "
    "evidence only. It cannot launch Codex, execute a campaign job, invoke a "
    "shell, read credentials, write state, or authorize any effect."
)


def _strict_json_loads(text: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON object key: {key}")
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=reject_duplicates)


def _now(value: datetime | None) -> datetime:
    observed = value or datetime.now(timezone.utc)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return observed.astimezone(timezone.utc)


def _safe_path(repo_root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or chr(92) in relative:
        raise ValueError(f"unsafe repository-relative path: {relative}")
    resolved = (repo_root / path).resolve()
    root = repo_root.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"path escaped repository: {relative}")
    return resolved


def _load_receipt_checker(repo_root: Path) -> ModuleType:
    path = repo_root / "docs/campaigns/dad-high-value-recovery/checks/verify_receipt_durability.py"
    spec = importlib.util.spec_from_file_location("dad_campaign_receipt_checker", path)
    if spec is None or spec.loader is None:
        raise ValueError("receipt durability verifier could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _derive_atomic_receipt_evidence(
    repo_root: Path,
    manifest: Mapping[str, Any],
    parent_job_id: str,
    checker: ModuleType,
    *,
    current_job_id: str = "",
) -> tuple[list[dict[str, Any]], list[str]]:
    """Resolve accepted child receipts/checkers without writing reconciliation state."""

    jobs = flatten_campaign_jobs(manifest)
    children = sorted(
        (
            job
            for job in jobs.values()
            if job.get("is_atomic_child") and job.get("parent_id") == parent_job_id
        ),
        key=lambda row: int(row.get("sequence", 0)),
    )
    accepted: list[dict[str, Any]] = []
    errors: list[str] = []
    for child in children:
        child_id = str(child.get("id", ""))
        receipt_path = _safe_path(repo_root, str(child.get("receipt", "")))
        if not receipt_path.is_file():
            continue
        try:
            rows, receipt_digest = checker._read_jsonl(receipt_path)
        except (OSError, ValueError, AttributeError) as exc:
            errors.append(f"atomic-prefix-receipt-invalid:{child_id}:{exc}")
            continue
        if not rows:
            errors.append(f"atomic-prefix-receipt-empty:{child_id}")
            continue
        latest = rows[-1]
        receipt_errors = checker.validate_receipt(
            latest,
            dict(manifest),
            child_id,
            repo_root=repo_root,
            verify_files=True,
            verify_dependency_receipts=True,
        )
        if receipt_errors:
            errors.extend(f"atomic-prefix-receipt:{child_id}:{error}" for error in receipt_errors)
            continue
        outcome = (
            latest.get("result"),
            latest.get("state"),
            latest.get("coverage"),
        )
        if child_id == current_job_id and outcome[0] == "fail_repairable":
            continue
        if outcome != ("pass", "complete", "complete"):
            errors.append(f"atomic-prefix-receipt-not-accepted:{child_id}")
            continue
        accepted.append(
            {
                "job_id": child_id,
                "case_digest": latest.get("case_binding"),
                "binding_table_digest": latest.get("case_binding_table_digest"),
                "receipt_digest": receipt_digest,
                "checker_record_digest": latest.get("checker_record_digest"),
                "checker_disposition": "pass",
                "durability_verified": True,
            }
        )
    return accepted, errors


def build_local_host_snapshot(repo_root: Path) -> dict[str, Any]:
    registry_path = repo_root / "registry/runtime-adapter-registry.json"
    registry = _strict_json_loads(registry_path.read_text(encoding="utf-8"))
    row = next(
        (item for item in registry.get("adapters", []) if item.get("adapter_id") == adapter_id),
        None,
    )
    if row is None:
        raise ValueError("registered Codex host adapter is missing")
    if (
        registry.get("execution_authorized") is not False
        or row.get("execution_authorized", False) is not False
    ):
        raise ValueError("Codex host adapter must deny execution")
    return {
        "schema_version": "dad.campaign.local_host_snapshot.v2",
        "adapter_id": adapter_id,
        "adapter_revision": revision,
        "registration_mode": row.get("registration_mode"),
        "protocol_methods": list(row.get("protocol_methods", [])),
        "registry_status": row.get("status"),
        "campaign_gate": "execution-control-evidence-only",
        "intent_continuity_host_readiness_gate": (
            "separate-future-supervised-continuity-trial-only"
        ),
        "execution_authorized": False,
        "launch_available": False,
        "snapshot_digest": canonical_digest(row),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def build_execution_evidence_snapshot(
    repo_root: Path,
    manifest: Mapping[str, Any],
    job_id: str,
    authorization_receipt_path: Path,
    *,
    source_revision: str = "uncommitted-candidate",
    pre_parent_reconciliation: Mapping[str, Any] | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Build a content-bound, read-only snapshot; errors become blocking evidence."""

    observed = _now(as_of)
    jobs = flatten_campaign_jobs(manifest)
    if job_id not in jobs:
        raise ValueError("unknown campaign job")
    job = jobs[job_id]
    manifest_path = repo_root / "docs/campaigns/dad-high-value-recovery/campaign.json"
    manifest_digest = file_digest(manifest_path)
    receipt_digest = file_digest(authorization_receipt_path)
    authorization = _strict_json_loads(authorization_receipt_path.read_text(encoding="utf-8"))
    verifier_path = (
        repo_root / "docs/campaigns/dad-high-value-recovery/checks/verify_receipt_durability.py"
    )
    verification_errors: list[str] = []
    case_binding_table: dict[str, Any] = {}
    case_binding_provenance: dict[str, Any] = {}
    cohort_closure: dict[str, Any] = {}
    cohort_reconciliation: dict[str, Any] = {}
    terminal_route: dict[str, Any] = {}
    atomic_case_binding: dict[str, Any] = {}
    atomic_case_outcomes: list[dict[str, Any]] = []
    try:
        checker = _load_receipt_checker(repo_root)
        dependencies, dependency_errors = checker.resolve_dependency_receipts(
            repo_root, dict(manifest), job_id
        )
        verification_errors.extend(str(value) for value in dependency_errors)
        if job.get("is_atomic_child") or job_id in COHORT_PARENT_IDS:
            resolved_table, table_errors = checker.resolve_case_binding_table(
                repo_root, dict(manifest)
            )
            verification_errors.extend(str(value) for value in table_errors)
            if isinstance(resolved_table, Mapping):
                case_binding_table = dict(resolved_table)
            resolved_provenance, provenance_errors = checker.resolve_case_binding_provenance(
                repo_root, dict(manifest)
            )
            verification_errors.extend(str(value) for value in provenance_errors)
            if isinstance(resolved_provenance, Mapping):
                case_binding_provenance = dict(resolved_provenance)
            receipt_evidence, receipt_errors = _derive_atomic_receipt_evidence(
                repo_root,
                manifest,
                str(job.get("parent_id") or job_id),
                checker,
                current_job_id=job_id if job.get("is_atomic_child") else "",
            )
            verification_errors.extend(receipt_errors)
            if job.get("is_atomic_child"):
                atomic_case_outcomes = receipt_evidence
            if job.get("is_atomic_child") and not table_errors:
                materialized = materialize_atomic_child(manifest, job_id, case_binding_table)
                atomic_case_binding = {
                    "case_id": materialized.get("case_id"),
                    "case_digest": materialized.get("case_binding"),
                    "case_binding_table_digest": materialized.get("case_binding_table_digest"),
                    "case_envelope_path": materialized.get("case_envelope_path"),
                }
            if job_id in COHORT_PARENT_IDS:
                reason_material = pre_parent_reconciliation or {}
                required_reason_fields = {
                    "schema_version",
                    "campaign_id",
                    "campaign_revision",
                    "parent_job_id",
                    "unstarted_or_withdrawn_children",
                    "active_lease_count",
                    "unreconciled_effect_count",
                    "post_stop_receipt_count",
                    "post_stop_lease_count",
                    "stop_trigger",
                    "stop_trigger_digest",
                    "reason_material_digest",
                }
                if set(reason_material) != required_reason_fields:
                    verification_errors.append(
                        "pre-parent-reconciliation-reason-material-fields-invalid"
                    )
                started_rows = [
                    {
                        key: row[key]
                        for key in (
                            "job_id",
                            "receipt_digest",
                            "checker_record_digest",
                            "checker_disposition",
                            "durability_verified",
                        )
                    }
                    for row in receipt_evidence
                ]
                cohort_reconciliation = build_cohort_reconciliation_projection(
                    manifest,
                    job_id,
                    started_children=started_rows,
                    reason_material=reason_material,
                )
                verification_errors.extend(
                    validate_cohort_reconciliation_projection(
                        manifest, job_id, cohort_reconciliation
                    )
                )
        if job_id == "J-600":
            resolved_route, route_dependencies, route_errors = checker.resolve_terminal_route(
                repo_root, dict(manifest)
            )
            verification_errors.extend(str(value) for value in route_errors)
            if isinstance(resolved_route, Mapping):
                terminal_route = dict(resolved_route)
            if isinstance(route_dependencies, Mapping):
                dependencies = dict(route_dependencies)
            predecessor = str(terminal_route.get("predecessor_job_id", ""))
            if predecessor:
                resolved_closure, closure_errors = checker.resolve_cohort_closure(
                    repo_root, dict(manifest), predecessor
                )
                verification_errors.extend(str(value) for value in closure_errors)
                if isinstance(resolved_closure, Mapping):
                    cohort_closure = dict(resolved_closure)
        budget_attempts, budget_receipt_digests, budget_errors = (
            checker.resolve_campaign_budget_receipts(repo_root, dict(manifest))
        )
        verification_errors.extend(str(value) for value in budget_errors)
    except (OSError, ValueError, ImportError, AttributeError) as exc:
        dependencies = {}
        budget_attempts = []
        budget_receipt_digests = {}
        verification_errors.append(f"dependency-verifier:{exc}")

    dependency_outputs = {
        path: digest
        for row in dependencies.values()
        for path, digest in row.get("output_digests", {}).items()
    }
    resolved_inputs: dict[str, str] = {}
    for relative, expected in job.get("input_digests", {}).items():
        if str(expected).startswith("receipt-bound-output-digest:"):
            digest = (
                case_binding_provenance.get("binding_table_file_digest")
                if relative == case_binding_provenance.get("binding_table_path")
                else dependency_outputs.get(relative)
            )
            if isinstance(digest, str):
                resolved_inputs[relative] = digest
            else:
                verification_errors.append(f"receipt-bound-input-unresolved:{relative}")
            continue
        path = _safe_path(repo_root, relative)
        if path.is_file():
            resolved_inputs[relative] = file_digest(path)
        else:
            verification_errors.append(f"input-missing:{relative}")

    qualifications: dict[str, dict[str, Any]] = {}
    for relative in job.get("qualification_evidence", []):
        try:
            path = _safe_path(repo_root, relative)
            row = _strict_json_loads(path.read_text(encoding="utf-8"))
            if not isinstance(row, dict):
                raise ValueError("qualification must be an object")
            row = {**row, "digest": file_digest(path)}
            for source_path, expected_digest in row.get("source_digests", {}).items():
                source = _safe_path(repo_root, str(source_path))
                if not source.is_file() or file_digest(source) != expected_digest:
                    verification_errors.append(
                        f"qualification-source-stale:{relative}:{source_path}"
                    )
            qualifications[relative] = row
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            verification_errors.append(f"qualification-invalid:{relative}:{exc}")

    authority_sources: dict[str, str] = {}
    for source in manifest.get("source_authority", []):
        relative = str(source.get("path", ""))
        path = _safe_path(repo_root, relative)
        if path.is_file():
            authority_sources[relative] = file_digest(path)
    effective_source_revision = canonical_digest(
        {
            "manifest_digest": manifest_digest,
            "source_authority": authority_sources,
        }
    )
    if (
        isinstance(source_revision, str)
        and source_revision.startswith("sha256:")
        and len(source_revision) == 71
        and source_revision != effective_source_revision
    ):
        verification_errors.append("source-revision-expected-mismatch")
    material = {
        "schema_version": EVIDENCE_SNAPSHOT_SCHEMA,
        "campaign_id": manifest.get("campaign_id"),
        "campaign_revision": manifest.get("revision"),
        "manifest_digest": manifest_digest,
        "job_id": job_id,
        "authorization_id": authorization.get("authorization_id"),
        "named_approver": authorization.get("named_approver"),
        "authorization_receipt_digest": receipt_digest,
        "authority_approval_ids": dict(
            authorization.get("portfolio_approval_refs", {})
            if isinstance(authorization.get("portfolio_approval_refs"), Mapping)
            else {}
        ),
        "campaign_budget_attempts": budget_attempts,
        "budget_receipt_digests": budget_receipt_digests,
        "source_revision": effective_source_revision,
        "resolved_input_digests": resolved_inputs,
        "dependency_receipts": dependencies,
        "qualification_evidence": qualifications,
        "durability_verifier_digest": file_digest(verifier_path),
        "adapter_revision": revision,
        "observed_paths": [],
        "observed_effects": [],
        "observed_at": observed.isoformat(),
        "verification_errors": sorted(set(verification_errors)),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    if job.get("is_atomic_child") or job_id in COHORT_PARENT_IDS:
        material["case_binding_table"] = case_binding_table
        material["case_binding_provenance"] = case_binding_provenance
    if job.get("is_atomic_child"):
        material["atomic_case_binding"] = atomic_case_binding
        material["atomic_case_outcomes"] = atomic_case_outcomes
    if job_id in COHORT_PARENT_IDS:
        material["pre_parent_reconciliation"] = cohort_reconciliation
    if job_id == "J-600":
        material["terminal_route"] = terminal_route
        material["cohort_closure"] = cohort_closure
    return {**material, "snapshot_digest": evidence_snapshot_digest(material)}


def _matching_binding(
    projection: Mapping[str, Any],
    manifest: Mapping[str, Any],
    job_id: str,
) -> dict[str, Any]:
    matches = [
        row.get("campaign_binding")
        for row in projection.get("leases", [])
        if isinstance(row, Mapping)
        and row.get("status") == "active"
        and isinstance(row.get("campaign_binding"), Mapping)
        and row["campaign_binding"].get("campaign_id") == manifest.get("campaign_id")
        and row["campaign_binding"].get("campaign_revision") == manifest.get("revision")
        and row["campaign_binding"].get("job_id") == job_id
    ]
    return dict(matches[0]) if len(matches) == 1 else {}


def _load_authority_attestations(repo_root: Path, paths: Iterable[Path]) -> list[dict[str, Any]]:
    """Load explicit repository-local envelopes without granting them trust."""

    root = repo_root.resolve()
    envelopes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for supplied in paths:
        path = supplied if supplied.is_absolute() else repo_root / supplied
        resolved = path.resolve(strict=True)
        if root not in resolved.parents or not resolved.is_file():
            raise ValueError("authority attestation must be a repository-local file")
        value = _strict_json_loads(resolved.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("authority attestation envelope must be a JSON object")
        label = resolved.relative_to(root).as_posix()
        if label in seen:
            raise ValueError("authority attestation path was repeated")
        envelopes.append(value)
        seen.add(label)
    return envelopes


def _load_pre_parent_reconciliation(repo_root: Path, supplied: Path) -> dict[str, Any]:
    path = supplied if supplied.is_absolute() else repo_root / supplied
    resolved = path.resolve(strict=True)
    root = repo_root.resolve(strict=True)
    if root not in resolved.parents or not resolved.is_file():
        raise ValueError("pre-parent reconciliation must be a repository-local JSON file")
    value = _strict_json_loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("pre-parent reconciliation must be a JSON object")
    return value


def normalize_codex_shell_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    effects = dict(receipt.get("effects", {}))
    if any(value != 0 for value in effects.values()):
        raise ValueError("inert adapter receipt claimed an execution effect")
    return {
        "schema_version": "dad.campaign.codex_shell_receipt.v2",
        "status": receipt.get("status"),
        "job_id": receipt.get("job_id"),
        "packet_digest": receipt.get("packet", {}).get("packet_digest"),
        "effects": effects,
        "execution_authorized": False,
        "dispatch_allowed": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def assert_no_execution_effect(receipt: Mapping[str, Any]) -> None:
    normalized = normalize_codex_shell_receipt(receipt)
    required = {
        "subprocesses_started",
        "model_calls",
        "network_calls",
        "git_changes",
        "downstream_writes",
        "campaign_state_writes",
        "campaign_job_receipts_created",
    }
    if set(normalized["effects"]) != required:
        raise ValueError("dry-run effect inventory is incomplete")
    if receipt.get("dispatch_allowed") is not False:
        raise ValueError("inert adapter cannot return dispatch_allowed")


def prepare_dry_run(
    repo_root: Path,
    manifest_path: Path,
    decision_receipt_path: Path,
    *,
    job_id: str,
    source_revision: str = "uncommitted-candidate",
    authority_attestation_paths: Iterable[Path] = (),
    pre_parent_reconciliation: Mapping[str, Any] | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    observed = _now(as_of)
    if pre_parent_reconciliation is not None and job_id not in COHORT_PARENT_IDS:
        raise ValueError("pre-parent reconciliation is valid only for J-510/J-520/J-530")
    canonical_manifest_path = (
        repo_root / "docs/campaigns/dad-high-value-recovery/campaign.json"
    ).resolve()
    if manifest_path.resolve() != canonical_manifest_path:
        raise ValueError("manifest must be the canonical repository campaign.json")
    manifest = load_campaign_manifest(manifest_path)
    decision = _strict_json_loads(decision_receipt_path.read_text(encoding="utf-8"))
    attestations = _load_authority_attestations(repo_root, authority_attestation_paths)
    evidence = build_execution_evidence_snapshot(
        repo_root,
        manifest,
        job_id,
        decision_receipt_path,
        source_revision=source_revision,
        pre_parent_reconciliation=pre_parent_reconciliation,
        as_of=observed,
    )
    try:
        projection = load_execution_control(repo_root, as_of=observed, attestations=attestations)
    except (OSError, ValueError) as exc:
        projection = {
            "executor": {"available": False, "dispatch_allowed": False},
            "leases": [],
            "dispatches": [],
            "diagnostics": [f"execution-control-load-failed:{exc}"],
        }
    binding = _matching_binding(projection, manifest, job_id)
    runtime_state = campaign_runtime_state_from_projection(
        projection,
        campaign_id=str(manifest.get("campaign_id", "")),
        campaign_revision=str(manifest.get("revision", "")),
        job_id=job_id,
        campaign_binding=binding,
        durable_attempts=evidence.get("campaign_budget_attempts", []),
        receipt_evidence_complete=not any(
            str(value).startswith("budget receipt")
            for value in evidence.get("verification_errors", [])
        ),
    )
    state = {
        **runtime_state,
        "execution_control": projection,
        "campaign_binding": binding,
        "evidence_snapshot": evidence,
    }
    if isinstance(evidence.get("case_binding_table"), Mapping):
        state["case_binding_table"] = dict(evidence["case_binding_table"])
    if isinstance(evidence.get("atomic_case_outcomes"), list):
        state["atomic_case_outcomes"] = [
            dict(row) for row in evidence["atomic_case_outcomes"] if isinstance(row, Mapping)
        ]
    if isinstance(evidence.get("terminal_route"), Mapping):
        state["terminal_route"] = dict(evidence["terminal_route"])
    result = build_campaign_dry_run(
        repo_root,
        manifest,
        job_id,
        decision,
        state=state,
        source_revision=str(evidence.get("source_revision", "")),
        authorization_receipt_digest=file_digest(decision_receipt_path),
        as_of=observed,
    )
    result["adapter"] = build_local_host_snapshot(repo_root)
    assert_no_execution_effect(result)
    return result


def prepare_shutdown(
    manifest_path: Path, *, reason_code: str, active_job_id: str = ""
) -> dict[str, Any]:
    manifest = load_campaign_manifest(manifest_path)
    return build_stop_checkpoint(manifest, reason_code=reason_code, active_job_id=active_job_id)


def prepare_navigation_projection(
    manifest_path: Path,
    *,
    terminal_route: Mapping[str, Any],
    navigation_receipt_digest: str = "",
    j600_receipt_digest: str = "",
    include_supersession_map: bool = False,
) -> dict[str, Any]:
    """Project a separately leased navigation request without writing or dispatching."""

    return build_navigation_projection(
        load_campaign_manifest(manifest_path),
        terminal_route=terminal_route,
        navigation_receipt_digest=navigation_receipt_digest,
        j600_receipt_digest=j600_receipt_digest,
        include_supersession_map=include_supersession_map,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    qualify = subparsers.add_parser("qualify")
    qualify.add_argument("--repo", type=Path, default=Path("."))
    qualify.add_argument("--manifest", type=Path, required=True)
    qualify.add_argument("--decision-receipt", type=Path, required=True)
    qualify.add_argument("--job", default="J-100")
    qualify.add_argument("--source-revision", default="uncommitted-candidate")
    qualify.add_argument(
        "--pre-parent-reconciliation",
        type=Path,
        help="Repository-local read-only cohort reason-material JSON",
    )
    qualify.add_argument(
        "--attestation",
        action="append",
        type=Path,
        default=[],
        help="Explicit repository-local Portfolio authority attestation envelope",
    )
    shutdown = subparsers.add_parser("shutdown")
    shutdown.add_argument("--manifest", type=Path, required=True)
    shutdown.add_argument("--reason", required=True)
    shutdown.add_argument("--active-job", default="")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "qualify":
        repo_root = args.repo.resolve()
        reconciliation = (
            _load_pre_parent_reconciliation(repo_root, args.pre_parent_reconciliation)
            if args.pre_parent_reconciliation is not None
            else None
        )
        payload = prepare_dry_run(
            repo_root,
            args.manifest.resolve(),
            args.decision_receipt.resolve(),
            job_id=args.job,
            source_revision=args.source_revision,
            authority_attestation_paths=args.attestation,
            pre_parent_reconciliation=reconciliation,
        )
    else:
        payload = prepare_shutdown(
            args.manifest.resolve(),
            reason_code=args.reason,
            active_job_id=args.active_job,
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "adapter_id",
    "assert_no_execution_effect",
    "build_execution_evidence_snapshot",
    "build_local_host_snapshot",
    "_load_authority_attestations",
    "_load_pre_parent_reconciliation",
    "normalize_codex_shell_receipt",
    "prepare_dry_run",
    "prepare_navigation_projection",
    "prepare_shutdown",
    "revision",
]
