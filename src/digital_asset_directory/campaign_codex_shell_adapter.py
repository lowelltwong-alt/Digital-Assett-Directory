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
    EVIDENCE_SNAPSHOT_SCHEMA,
    build_campaign_dry_run,
    build_stop_checkpoint,
    canonical_digest,
    evidence_snapshot_digest,
    file_digest,
    flatten_campaign_jobs,
    load_campaign_manifest,
)
from .portfolio_execution import (
    campaign_runtime_state_from_projection,
    load_execution_control,
)


adapter_id = "adapter:codex-host"
revision = "dad-campaign-codex-shell-adapter:0.2.0-prelaunch"
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
    path = (
        repo_root
        / "docs/campaigns/dad-high-value-recovery/checks/verify_receipt_durability.py"
    )
    spec = importlib.util.spec_from_file_location("dad_campaign_receipt_checker", path)
    if spec is None or spec.loader is None:
        raise ValueError("receipt durability verifier could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_local_host_snapshot(repo_root: Path) -> dict[str, Any]:
    registry_path = repo_root / "registry/runtime-adapter-registry.json"
    registry = _strict_json_loads(registry_path.read_text(encoding="utf-8"))
    row = next(
        (item for item in registry.get("adapters", []) if item.get("adapter_id") == adapter_id),
        None,
    )
    if row is None:
        raise ValueError("registered Codex host adapter is missing")
    if registry.get("execution_authorized") is not False or row.get(
        "execution_authorized", False
    ) is not False:
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
    authorization = _strict_json_loads(
        authorization_receipt_path.read_text(encoding="utf-8")
    )
    verifier_path = (
        repo_root
        / "docs/campaigns/dad-high-value-recovery/checks/verify_receipt_durability.py"
    )
    verification_errors: list[str] = []
    try:
        checker = _load_receipt_checker(repo_root)
        dependencies, dependency_errors = checker.resolve_dependency_receipts(
            repo_root, dict(manifest), job_id
        )
        verification_errors.extend(str(value) for value in dependency_errors)
        budget_attempts, budget_receipt_digests, budget_errors = (
            checker.resolve_campaign_budget_receipts(repo_root, dict(manifest))
        )
        verification_errors.extend(str(value) for value in budget_errors)
    except (OSError, ValueError, ImportError) as exc:
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
            digest = dependency_outputs.get(relative)
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


def _load_authority_attestations(
    repo_root: Path, paths: Iterable[Path]
) -> list[dict[str, Any]]:
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
    as_of: datetime | None = None,
) -> dict[str, Any]:
    observed = _now(as_of)
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
        as_of=observed,
    )
    try:
        projection = load_execution_control(
            repo_root, as_of=observed, attestations=attestations
        )
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
    return build_stop_checkpoint(
        manifest, reason_code=reason_code, active_job_id=active_job_id
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
        payload = prepare_dry_run(
            args.repo.resolve(),
            args.manifest.resolve(),
            args.decision_receipt.resolve(),
            job_id=args.job,
            source_revision=args.source_revision,
            authority_attestation_paths=args.attestation,
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
    "normalize_codex_shell_receipt",
    "prepare_dry_run",
    "prepare_shutdown",
    "revision",
]
