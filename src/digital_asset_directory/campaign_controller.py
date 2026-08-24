"""Provider-neutral, non-dispatching execution-control bridge for campaigns.

The bridge evaluates immutable local evidence against the existing Portfolio OS
lease and manual-dispatch projection. It can return only ``blocked`` or
``ready-manual`` candidate evidence. It never launches a worker, runs a
command, writes state, mutates Git, accesses a network, or grants authority.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Protocol

from .portfolio_execution import (
    CAMPAIGN_BINDING_SCHEMA,
    campaign_runtime_state_from_projection,
    validate_campaign_execution_control,
)


SHA256_PREFIX = "sha256:"
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
AUTHORIZATION_SCHEMA = "dad.campaign.execution_authorization.v1"
EVIDENCE_SNAPSHOT_SCHEMA = "dad.campaign.execution_evidence_snapshot.v1"
AUTHORITY_BOUNDARY = (
    "This bridge is a non-authoritative, non-dispatching packet projection. "
    "A ready-manual result does not authorize or perform a campaign job, "
    "subprocess, model call, network access, Git change, downstream write, "
    "publication, merge, deployment, or cleanup."
)


class CampaignRuntimeAdapter(Protocol):
    """Minimal provider-neutral host boundary; implementations remain inert."""

    adapter_id: str
    revision: str

    def snapshot(self, repo_root: Path) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class BudgetResult:
    within_budget: bool
    used_attempts: int
    used_cost_units: float
    used_output_mb: float
    used_wall_seconds: float
    used_context_tokens: int
    reason_codes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "within_budget": self.within_budget,
            "used_attempts": self.used_attempts,
            "used_cost_units": self.used_cost_units,
            "used_output_mb": self.used_output_mb,
            "used_wall_seconds": self.used_wall_seconds,
            "used_context_tokens": self.used_context_tokens,
            "reason_codes": list(self.reason_codes),
        }


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return SHA256_PREFIX + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def evidence_snapshot_digest(snapshot: Mapping[str, Any]) -> str:
    """Digest stable evidence while leaving observation time as metadata.

    ``observed_at`` records when a caller read the evidence, but is not evidence
    content and cannot be part of the lease/dispatch packet binding. Otherwise
    rebuilding the same snapshot a moment later makes an already approved packet
    impossible to reproduce.
    """

    material = {
        key: value
        for key, value in snapshot.items()
        if key not in {"snapshot_digest", "observed_at"}
    }
    return canonical_digest(material)


def file_digest(path: Path) -> str:
    return SHA256_PREFIX + hashlib.sha256(path.read_bytes()).hexdigest()


def _strict_json_loads(text: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON object key: {key}")
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=reject_duplicates)


def _digest(value: object) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _now(value: datetime | None) -> datetime:
    observed = value or datetime.now(timezone.utc)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return observed.astimezone(timezone.utc)


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def load_campaign_manifest(path: Path) -> dict[str, Any]:
    manifest = _strict_json_loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "long_run_campaign.v2":
        raise ValueError("unsupported campaign manifest")
    execution = manifest.get("execution", {})
    if execution.get("execution_authorized") is not False:
        raise ValueError("campaign manifest must explicitly deny execution before activation")
    if execution.get("mode") != "specification_only":
        raise ValueError("prelaunch bridge accepts specification_only manifests only")
    return manifest


def flatten_campaign_jobs(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Return top-level jobs plus declared atomic pilot child slots."""

    jobs: dict[str, dict[str, Any]] = {}
    for phase in manifest.get("phases", []):
        for wave in phase.get("waves", []):
            for subwave in wave.get("subwaves", []):
                for raw_job in subwave.get("jobs", []):
                    job = deepcopy(raw_job)
                    job_id = str(job.get("id", ""))
                    if not job_id or job_id in jobs:
                        raise ValueError("campaign job identity is missing or duplicated")
                    jobs[job_id] = job
                    execution = job.get("case_execution", {})
                    child_gate = execution.get("child_acceptance", {})
                    for slot in execution.get("slots", []):
                        child_id = str(slot.get("job_id", ""))
                        if not child_id or child_id in jobs:
                            raise ValueError("atomic child identity is missing or duplicated")
                        evidence_template = str(child_gate.get("evidence_path_template", ""))
                        child = deepcopy(slot)
                        child.update(
                            {
                                "id": child_id,
                                "parent_id": job_id,
                                "is_atomic_child": True,
                                "owner_role": execution.get("child_owner_role"),
                                "checker_role": execution.get("child_checker_role"),
                                "inputs": list(job.get("inputs", [])),
                                "input_digests": dict(job.get("input_digests", {})),
                                "outputs": list(job.get("outputs", [])),
                                "allowed_paths": list(job.get("allowed_paths", [])),
                                "qualification_evidence": list(
                                    job.get("qualification_evidence", [])
                                ),
                                "binding_table": execution.get("binding_table"),
                                "max_attempts": execution.get("max_attempts_per_child"),
                                "repair_limit": execution.get("repair_limit_per_child", 0),
                                "cost_ceiling": execution.get("cost_ceiling_per_child"),
                                "time_ceiling_minutes": execution.get(
                                    "time_ceiling_minutes_per_child",
                                    job.get("time_ceiling_minutes"),
                                ),
                                "context_ceiling_tokens": execution.get(
                                    "context_ceiling_tokens_per_child",
                                    job.get("context_ceiling_tokens"),
                                ),
                                "output_ceiling_mb": execution.get(
                                    "output_ceiling_mb_per_child"
                                ),
                                "acceptance": [
                                    {
                                        "id": f"G-{child_id}-COMPLETE",
                                        "revision": child_gate.get("revision"),
                                        "checker_role": execution.get(
                                            "child_checker_role"
                                        ),
                                        "evidence": evidence_template.replace(
                                            "{job_id}", child_id
                                        ),
                                        "revalidation_triggers": list(
                                            child_gate.get("revalidation_triggers", [])
                                        ),
                                    }
                                ],
                            }
                        )
                        jobs[child_id] = child
    return jobs


def _safe_relative_path(repo_root: Path, raw: str) -> Path:
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts or chr(92) in raw:
        raise ValueError(f"unsafe campaign path: {raw}")
    resolved = (repo_root / relative).resolve()
    root = repo_root.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"campaign path escaped repository: {raw}")
    return resolved


def _attempt_rows(
    state: Mapping[str, Any], job_id: str | None = None
) -> list[Mapping[str, Any]]:
    rows = [row for row in state.get("attempts", []) if isinstance(row, Mapping)]
    return rows if job_id is None else [row for row in rows if row.get("job_id") == job_id]


def reconcile_campaign_budget(
    manifest: Mapping[str, Any], state: Mapping[str, Any]
) -> BudgetResult:
    attempts = cost = output = wall = 0.0
    context = 0
    for row in _attempt_rows(state):
        attempts += int(row.get("attempt_count", 0))
        cost += float(row.get("cost_units", 0))
        output += float(row.get("output_mb", 0))
        wall += float(row.get("wall_seconds", 0))
        context += int(row.get("context_tokens", 0))
    ceilings = manifest.get("budgets", {})
    reasons: list[str] = []
    if attempts >= int(ceilings.get("max_attempts_total", 0)):
        reasons.append("attempt_budget_exhausted")
    if cost >= float(ceilings.get("cost_units", 0)):
        reasons.append("cost_budget_exhausted")
    if output >= float(ceilings.get("max_storage_mb", 0)):
        reasons.append("storage_budget_exhausted")
    wall_limit = float(ceilings.get("wall_clock_hours", 0)) * 3600
    if wall_limit <= 0 or wall >= wall_limit:
        reasons.append("wall_clock_budget_exhausted")
    return BudgetResult(
        within_budget=not reasons,
        used_attempts=int(attempts),
        used_cost_units=cost,
        used_output_mb=output,
        used_wall_seconds=wall,
        used_context_tokens=context,
        reason_codes=tuple(sorted(reasons)),
    )


def _job_budget_material(job: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: job.get(key)
        for key in (
            "max_attempts",
            "repair_limit",
            "cost_ceiling",
            "time_ceiling_minutes",
            "context_ceiling_tokens",
            "output_ceiling_mb",
        )
    }


def _job_budget_reasons(job: Mapping[str, Any], state: Mapping[str, Any]) -> list[str]:
    rows = _attempt_rows(state, str(job.get("id", "")))
    totals = {
        "attempts": sum(int(row.get("attempt_count", 0)) for row in rows),
        "cost": sum(float(row.get("cost_units", 0)) for row in rows),
        "wall": sum(float(row.get("wall_seconds", 0)) for row in rows),
        "context": sum(int(row.get("context_tokens", 0)) for row in rows),
        "output": sum(float(row.get("output_mb", 0)) for row in rows),
    }
    ceilings = {
        "job_attempt_budget_exhausted": (totals["attempts"], job.get("max_attempts")),
        "job_cost_budget_exhausted": (totals["cost"], job.get("cost_ceiling")),
        "job_wall_budget_exhausted": (
            totals["wall"],
            None
            if job.get("time_ceiling_minutes") is None
            else float(job.get("time_ceiling_minutes")) * 60,
        ),
        "job_context_budget_exhausted": (
            totals["context"],
            job.get("context_ceiling_tokens"),
        ),
        "job_output_budget_exhausted": (
            totals["output"],
            job.get("output_ceiling_mb"),
        ),
    }
    return [
        code
        for code, (used, ceiling) in ceilings.items()
        if ceiling is None or float(ceiling) <= 0 or used >= float(ceiling)
    ]


def validate_campaign_state(
    manifest: Mapping[str, Any], state: Mapping[str, Any]
) -> list[str]:
    errors: list[str] = []
    jobs = flatten_campaign_jobs(manifest)
    active = [row for row in state.get("leases", []) if row.get("state") == "active"]
    if len(active) > int(manifest.get("budgets", {}).get("max_parallel_jobs", 1)):
        errors.append("parallel_lease_limit_exceeded")
    if any(lease.get("job_id") not in jobs for lease in active):
        errors.append("active_lease_job_unknown")
    packets: dict[str, str] = {}
    for row in state.get("issued_packets", []):
        key = str(row.get("idempotency_key", ""))
        digest = str(row.get("packet_digest", ""))
        if not key or not _digest(digest):
            errors.append("issued_packet_identity_invalid")
        elif key in packets and packets[key] != digest:
            errors.append("idempotency_conflict")
        else:
            packets[key] = digest
    if state.get("stop_requested") is True or state.get("campaign_state") in {
        "stopping",
        "stopped",
        "blocked",
    }:
        errors.append("stop_transition_active")
    if state.get("runtime_state_errors"):
        errors.append("portfolio_runtime_state_invalid")
    return sorted(set(errors))


def required_authorization_effects(manifest: Mapping[str, Any]) -> list[str]:
    return sorted(
        {str(value) for value in manifest.get("authority", {}).get("allowed_effects", [])}
    )


def _authorization_binding(
    receipt: Mapping[str, Any],
    manifest: Mapping[str, Any],
    manifest_digest: str,
    job_id: str,
    *,
    as_of: datetime,
) -> list[str]:
    reasons: list[str] = []
    if receipt.get("schema_version") != AUTHORIZATION_SCHEMA:
        reasons.append("human_authorization_schema_invalid")
    if receipt.get("status") != "authorized":
        reasons.append("human_authorization_not_active")
    if receipt.get("campaign_id") != manifest.get("campaign_id"):
        reasons.append("human_authorization_campaign_mismatch")
    if receipt.get("campaign_revision") != manifest.get("revision"):
        reasons.append("human_authorization_revision_mismatch")
    if receipt.get("manifest_digest") != manifest_digest:
        reasons.append("human_authorization_digest_mismatch")
    if receipt.get("job_id") != job_id:
        reasons.append("human_authorization_job_mismatch")
    if not isinstance(receipt.get("authorization_id"), str) or not str(
        receipt.get("authorization_id", "")
    ).strip():
        reasons.append("human_authorization_identity_invalid")
    approval_refs = receipt.get("portfolio_approval_refs", {})
    if (
        not isinstance(approval_refs, Mapping)
        or set(approval_refs) != {"lease_approval_id", "dispatch_approval_id"}
        or any(
            not isinstance(value, str) or not value.strip()
            for value in approval_refs.values()
        )
        or len(set(approval_refs.values())) != 2
    ):
        reasons.append("human_authorization_portfolio_refs_invalid")
    if sorted(receipt.get("approved_effects", [])) != required_authorization_effects(
        manifest
    ):
        reasons.append("human_authorization_effects_mismatch")
    approver = receipt.get("approved_by")
    if (
        not isinstance(approver, str)
        or not approver.strip()
        or receipt.get("named_approver") != approver
    ):
        reasons.append("human_authorization_approver_invalid")
    approved = _timestamp(receipt.get("approved_at"))
    expires = _timestamp(receipt.get("expires_at"))
    if approved is None or expires is None or approved > as_of or as_of >= expires:
        reasons.append("human_authorization_expired_or_invalid")
    if set(receipt.get("prohibited_effects", [])) & set(
        receipt.get("approved_effects", [])
    ):
        reasons.append("human_authorization_effect_conflict")
    return reasons


def _evidence_snapshot_reasons(
    repo_root: Path,
    manifest: Mapping[str, Any],
    job: Mapping[str, Any],
    manifest_digest: str,
    authorization_receipt_digest: str,
    snapshot: Mapping[str, Any],
    *,
    as_of: datetime,
) -> list[str]:
    reasons: list[str] = []
    expected_header = {
        "schema_version": EVIDENCE_SNAPSHOT_SCHEMA,
        "campaign_id": manifest.get("campaign_id"),
        "campaign_revision": manifest.get("revision"),
        "manifest_digest": manifest_digest,
        "job_id": job.get("id"),
        "authorization_receipt_digest": authorization_receipt_digest,
    }
    for key, expected in expected_header.items():
        if snapshot.get(key) != expected:
            reasons.append(f"evidence_snapshot_mismatch:{key}")
    if not _digest(snapshot.get("source_revision")):
        reasons.append("source_revision_invalid")
    observed_at = _timestamp(snapshot.get("observed_at"))
    if observed_at is None or observed_at > as_of:
        reasons.append("evidence_snapshot_observed_at_invalid")
    claimed_snapshot_digest = snapshot.get("snapshot_digest")
    if claimed_snapshot_digest != evidence_snapshot_digest(snapshot):
        reasons.append("evidence_snapshot_digest_mismatch")

    resolved_inputs = snapshot.get("resolved_input_digests", {})
    expected_inputs = set(job.get("inputs", []))
    if not isinstance(resolved_inputs, Mapping) or set(resolved_inputs) != expected_inputs:
        reasons.append("resolved_input_set_mismatch")
        resolved_inputs = {}
    elif any(not _digest(value) for value in resolved_inputs.values()):
        reasons.append("resolved_input_digest_invalid")
    dependency_rows = snapshot.get("dependency_receipts", {})
    expected_dependencies = set(job.get("depends_on", []))
    if not isinstance(dependency_rows, Mapping) or set(dependency_rows) != expected_dependencies:
        reasons.append("dependency_receipt_set_mismatch")
        dependency_rows = {}
    for dependency in expected_dependencies:
        row = dependency_rows.get(dependency, {})
        if (
            not isinstance(row, Mapping)
            or not _digest(row.get("receipt_digest"))
            or row.get("result") != "pass"
            or row.get("state") != "complete"
            or row.get("verifier_status") != "pass"
        ):
            reasons.append(f"dependency_receipt_not_accepted:{dependency}")
    dependency_outputs = {
        path: digest
        for row in dependency_rows.values()
        if isinstance(row, Mapping)
        for path, digest in row.get("output_digests", {}).items()
    }
    for raw, expected in job.get("input_digests", {}).items():
        observed = resolved_inputs.get(raw)
        if str(expected).startswith("receipt-bound-output-digest:"):
            if observed != dependency_outputs.get(raw) or not _digest(observed):
                reasons.append(f"receipt_bound_input_unresolved:{raw}")
        elif observed != expected:
            reasons.append(f"input_stale:{raw}")

    qualification_rows = snapshot.get("qualification_evidence", {})
    expected_paths = set(job.get("qualification_evidence", []))
    if not isinstance(qualification_rows, Mapping) or set(qualification_rows) != expected_paths:
        reasons.append("qualification_evidence_set_mismatch")
        qualification_rows = {}
    observed_roles: set[str] = set()
    observed_revision_ids: set[str] = set()
    expected_adapter = manifest.get("execution", {}).get("adapter", {}).get("revision")
    for relative in expected_paths:
        row = qualification_rows.get(relative, {})
        if not isinstance(row, Mapping):
            reasons.append(f"qualification_invalid:{relative}")
            continue
        observed_roles.add(str(row.get("role", "")))
        revision_id = row.get("qualified_revision_id")
        if isinstance(revision_id, str) and revision_id.strip():
            observed_revision_ids.add(revision_id)
        expires = _timestamp(row.get("expires_at"))
        source_digests = row.get("source_digests", {})
        qualification_path = _safe_relative_path(repo_root, relative)
        try:
            qualification_source = _strict_json_loads(
                qualification_path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError, json.JSONDecodeError):
            qualification_source = None
        observed_qualification = dict(row)
        observed_qualification.pop("digest", None)
        if (
            row.get("status") != "qualified_candidate"
            or row.get("campaign_id") != manifest.get("campaign_id")
            or row.get("campaign_revision") != manifest.get("revision")
            or row.get("manifest_digest") != manifest_digest
            or not isinstance(row.get("profile_id"), str)
            or not str(row.get("profile_id", "")).strip()
            or not isinstance(revision_id, str)
            or not revision_id.strip()
            or row.get("adapter_revision") != expected_adapter
            or not isinstance(source_digests, Mapping)
            or not source_digests
            or any(not _digest(value) for value in source_digests.values())
            or not _digest(row.get("digest"))
            or not qualification_path.is_file()
            or row.get("digest") != file_digest(qualification_path)
            or qualification_source != observed_qualification
            or expires is None
            or as_of >= expires
        ):
            reasons.append(f"qualification_invalid:{relative}")
        if isinstance(source_digests, Mapping):
            for source_path, expected_digest in source_digests.items():
                source = _safe_relative_path(repo_root, str(source_path))
                if not source.is_file() or file_digest(source) != expected_digest:
                    reasons.append(f"qualification_source_stale:{relative}:{source_path}")
    required_roles = {str(job.get("owner_role", "")), str(job.get("checker_role", ""))}
    if not required_roles.issubset(observed_roles):
        reasons.append("required_role_qualification_missing")
    if len(observed_revision_ids) != len(expected_paths):
        reasons.append("qualification_revision_identity_conflict")

    if snapshot.get("adapter_revision") != expected_adapter:
        reasons.append("adapter_qualification_stale")
    verifier_path = _safe_relative_path(
        repo_root,
        "docs/campaigns/dad-high-value-recovery/checks/verify_receipt_durability.py",
    )
    if (
        not verifier_path.is_file()
        or snapshot.get("durability_verifier_digest") != file_digest(verifier_path)
    ):
        reasons.append("durability_verifier_stale")
    if snapshot.get("verification_errors"):
        reasons.append("evidence_snapshot_verification_failed")
    budget_receipts = snapshot.get("budget_receipt_digests", {})
    if not isinstance(budget_receipts, Mapping) or any(
        not isinstance(path, str)
        or not path
        or not _digest(digest)
        or not _safe_relative_path(repo_root, path).is_file()
        or file_digest(_safe_relative_path(repo_root, path)) != digest
        for path, digest in (
            budget_receipts.items() if isinstance(budget_receipts, Mapping) else []
        )
    ):
        reasons.append("budget_receipt_evidence_invalid")
    if not set(snapshot.get("observed_paths", [])).issubset(
        set(job.get("allowed_paths", []))
    ):
        reasons.append("observed_path_outside_job_scope")
    if not set(snapshot.get("observed_effects", [])).issubset(
        set(required_authorization_effects(manifest))
    ):
        reasons.append("observed_effect_outside_authority")
    return reasons


def _action_class(job: Mapping[str, Any]) -> str:
    """Return the single Portfolio action bound to this candidate packet."""

    return "implement" if job.get("outputs") else "inspect"


def _acceptance_evidence_paths(job: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            str(row.get("evidence"))
            for row in job.get("acceptance", [])
            if isinstance(row, Mapping) and str(row.get("evidence", "")).strip()
        }
    )


def _qualified_revision_for_role(
    qualifications: Mapping[str, Any], role: object
) -> str:
    matches = [
        str(row.get("qualified_revision_id", ""))
        for row in qualifications.values()
        if isinstance(row, Mapping) and row.get("role") == role
    ]
    return matches[0] if len(matches) == 1 else ""


def _packet_material(
    manifest: Mapping[str, Any],
    job: Mapping[str, Any],
    *,
    manifest_digest: str,
    authorization_receipt_digest: str,
    snapshot: Mapping[str, Any],
    source_revision: str,
) -> dict[str, Any]:
    qualifications = snapshot.get("qualification_evidence", {})
    dependencies = snapshot.get("dependency_receipts", {})
    return {
        "campaign_id": manifest["campaign_id"],
        "campaign_revision": manifest["revision"],
        "manifest_digest": manifest_digest,
        "job_id": job["id"],
        "parent_id": job.get("parent_id"),
        "source_revision": snapshot.get("source_revision", source_revision),
        "authorization_id": snapshot.get("authorization_id"),
        "named_approver": snapshot.get("named_approver"),
        "authorization_receipt_digest": authorization_receipt_digest,
        "authority_approval_ids": dict(snapshot.get("authority_approval_ids", {})),
        "budget_receipt_digests": dict(snapshot.get("budget_receipt_digests", {})),
        "input_digests": dict(snapshot.get("resolved_input_digests", {})),
        "dependency_receipt_digests": {
            key: row.get("receipt_digest")
            for key, row in dependencies.items()
            if isinstance(row, Mapping)
        },
        "qualification_evidence_digests": {
            key: row.get("digest")
            for key, row in qualifications.items()
            if isinstance(row, Mapping)
        },
        "depends_on": list(job.get("depends_on", [])),
        "idempotency_key": job.get("idempotency_key"),
        "worker_revision_id": _qualified_revision_for_role(
            qualifications, job.get("owner_role")
        ),
        "checker_revision_id": _qualified_revision_for_role(
            qualifications, job.get("checker_role")
        ),
        "action_class": _action_class(job),
        "output_paths": sorted(job.get("outputs", [])),
        "acceptance_evidence_paths": _acceptance_evidence_paths(job),
        "lease_minutes": job.get("lease_minutes"),
        "heartbeat_minutes": job.get("heartbeat_minutes"),
        "checkpoint": job.get("checkpoint"),
        "receipt": job.get("receipt"),
        "allowed_paths": sorted(job.get("allowed_paths", [])),
        "allowed_effects": required_authorization_effects(manifest),
        "owner_role": job.get("owner_role"),
        "checker_role": job.get("checker_role"),
        "campaign_budget_digest": canonical_digest(manifest.get("budgets", {})),
        "job_budget_digest": canonical_digest(_job_budget_material(job)),
        "durability_verifier_digest": snapshot.get("durability_verifier_digest"),
        "evidence_snapshot_digest": snapshot.get("snapshot_digest"),
        "adapter_revision": snapshot.get("adapter_revision"),
    }


def _expected_binding(
    packet_material: Mapping[str, Any], packet_digest: str
) -> dict[str, Any]:
    mapping = {
        "campaign_id": "campaign_id",
        "campaign_revision": "campaign_revision",
        "manifest_digest": "manifest_digest",
        "job_id": "job_id",
        "source_revision": "source_revision",
        "authorization_id": "authorization_id",
        "named_approver": "named_approver",
        "authorization_receipt_digest": "authorization_receipt_digest",
        "authority_approval_ids": "authority_approval_ids",
        "budget_receipt_digests": "budget_receipt_digests",
        "input_digests": "input_digests",
        "dependency_receipt_digests": "dependency_receipt_digests",
        "qualification_evidence_digests": "qualification_evidence_digests",
        "idempotency_key": "idempotency_key",
        "worker_revision_id": "worker_revision_id",
        "checker_revision_id": "checker_revision_id",
        "action_class": "action_class",
        "lease_minutes": "lease_minutes",
        "output_paths": "output_paths",
        "acceptance_evidence_paths": "acceptance_evidence_paths",
        "checkpoint_path": "checkpoint",
        "receipt_path": "receipt",
        "allowed_paths": "allowed_paths",
        "allowed_effects": "allowed_effects",
        "campaign_budget_digest": "campaign_budget_digest",
        "job_budget_digest": "job_budget_digest",
        "durability_verifier_digest": "durability_verifier_digest",
        "evidence_snapshot_digest": "evidence_snapshot_digest",
        "adapter_revision": "adapter_revision",
    }
    result = {
        "schema_version": CAMPAIGN_BINDING_SCHEMA,
        "packet_digest": packet_digest,
    }
    result.update({target: packet_material.get(source) for target, source in mapping.items()})
    return result


def build_execution_control_binding_candidate(
    packet: Mapping[str, Any],
    *,
    heartbeat_at: datetime,
    repair_attempt: int = 0,
    max_repairs: int = 0,
    reissue_of_attempt_id: str = "",
    prior_reconciliation_digest: str = "",
) -> dict[str, Any]:
    """Build inert binding material for a separately approved Portfolio request."""

    observed = _now(heartbeat_at)
    packet_digest = packet.get("packet_digest")
    if not _digest(packet_digest):
        raise ValueError("packet needs a SHA-256 packet digest")
    return {
        **_expected_binding(packet, str(packet_digest)),
        "heartbeat_at": observed.isoformat(),
        "heartbeat_minutes": packet.get("heartbeat_minutes"),
        "repair_attempt": repair_attempt,
        "max_repairs": max_repairs,
        "reissue_of_attempt_id": reissue_of_attempt_id,
        "prior_reconciliation_digest": prior_reconciliation_digest,
        "partial_effects_reconciled": True,
    }


def validate_job_ready(
    repo_root: Path,
    manifest: Mapping[str, Any],
    job_id: str,
    decision_receipt: Mapping[str, Any],
    *,
    state: Mapping[str, Any] | None = None,
    source_revision: str = "uncommitted-candidate",
    authorization_receipt_digest: str = "",
    as_of: datetime | None = None,
    packet_digest: str = "",
) -> dict[str, Any]:
    jobs = flatten_campaign_jobs(manifest)
    if job_id not in jobs:
        raise ValueError("unknown campaign job")
    job = jobs[job_id]
    supplied_state = state or {}
    observed = _now(as_of)
    supplied_projection = supplied_state.get("execution_control", {})
    if not isinstance(supplied_projection, Mapping):
        supplied_projection = {}
    supplied_binding = supplied_state.get("campaign_binding", {})
    if not isinstance(supplied_binding, Mapping):
        supplied_binding = {}
    supplied_snapshot = supplied_state.get("evidence_snapshot", {})
    if not isinstance(supplied_snapshot, Mapping):
        supplied_snapshot = {}
    runtime_state = campaign_runtime_state_from_projection(
        supplied_projection,
        campaign_id=str(manifest.get("campaign_id", "")),
        campaign_revision=str(manifest.get("revision", "")),
        job_id=job_id,
        campaign_binding=supplied_binding,
        durable_attempts=supplied_snapshot.get("campaign_budget_attempts", []),
        receipt_evidence_complete=not any(
            str(value).startswith("budget receipt")
            for value in supplied_snapshot.get("verification_errors", [])
        ),
    )
    state = {**supplied_state, **runtime_state}
    reasons = validate_campaign_state(manifest, state)
    manifest_path = repo_root / "docs/campaigns/dad-high-value-recovery/campaign.json"
    manifest_digest = file_digest(manifest_path)
    receipt_digest = authorization_receipt_digest or canonical_digest(decision_receipt)
    reasons.extend(
        _authorization_binding(
            decision_receipt, manifest, manifest_digest, job_id, as_of=observed
        )
    )
    observed_source_authority: dict[str, str] = {}
    for source in manifest.get("source_authority", []):
        raw = str(source.get("path", ""))
        path = _safe_relative_path(repo_root, raw)
        if not path.is_file() or file_digest(path) != source.get("digest"):
            reasons.append(f"source_stale:{raw}")
        elif path.is_file():
            observed_source_authority[raw] = file_digest(path)

    snapshot = state.get("evidence_snapshot", {})
    if not isinstance(snapshot, Mapping):
        snapshot = {}
    observed_source_revision = canonical_digest(
        {
            "manifest_digest": manifest_digest,
            "source_authority": observed_source_authority,
        }
    )
    if snapshot.get("source_revision") != observed_source_revision:
        reasons.append("source_revision_mismatch")
    if snapshot.get("authorization_id") != decision_receipt.get("authorization_id"):
        reasons.append("evidence_snapshot_mismatch:authorization_id")
    if dict(snapshot.get("authority_approval_ids", {})) != dict(
        decision_receipt.get("portfolio_approval_refs", {})
        if isinstance(decision_receipt.get("portfolio_approval_refs"), Mapping)
        else {}
    ):
        reasons.append("evidence_snapshot_mismatch:authority_approval_ids")
    if snapshot.get("named_approver") != decision_receipt.get("named_approver"):
        reasons.append("evidence_snapshot_mismatch:named_approver")
    reasons.extend(
        _evidence_snapshot_reasons(
            repo_root,
            manifest,
            job,
            manifest_digest,
            receipt_digest,
            snapshot,
            as_of=observed,
        )
    )
    budget = reconcile_campaign_budget(manifest, state)
    reasons.extend(budget.reason_codes)
    reasons.extend(_job_budget_reasons(job, state))
    if state.get("budget_evidence_complete") is not True:
        reasons.append("portfolio_budget_evidence_incomplete")

    canonical_manifest = _strict_json_loads(manifest_path.read_text(encoding="utf-8"))
    if manifest != canonical_manifest:
        reasons.append("campaign_manifest_not_canonical")
    if job.get("is_atomic_child"):
        reasons.append("atomic_child_execution_binding_not_implemented")
    if not set(job.get("outputs", [])).issubset(set(job.get("allowed_paths", []))):
        reasons.append("job_outputs_outside_allowed_paths")
    if not _acceptance_evidence_paths(job):
        reasons.append("acceptance_evidence_scope_missing")

    material = _packet_material(
        manifest,
        job,
        manifest_digest=manifest_digest,
        authorization_receipt_digest=receipt_digest,
        snapshot=snapshot,
        source_revision=source_revision,
    )
    actual_packet_digest = packet_digest or canonical_digest(material)
    for issued in state.get("issued_packets", []):
        if issued.get("idempotency_key") != job.get("idempotency_key"):
            continue
        if issued.get("packet_digest") == actual_packet_digest:
            reasons.append("idempotent_packet_already_issued")
        else:
            reasons.append("idempotency_conflict")
    expected_static = _expected_binding(material, actual_packet_digest)
    binding = state.get("campaign_binding", {})
    if not isinstance(binding, Mapping):
        binding = {}
    for key, expected in expected_static.items():
        if binding.get(key) != expected:
            reasons.append(f"campaign_binding_mismatch:{key}")
    if binding.get("heartbeat_minutes") != job.get("heartbeat_minutes"):
        reasons.append("campaign_binding_mismatch:heartbeat_minutes")
    job_attempts = sum(
        int(row.get("attempt_count", 0)) for row in _attempt_rows(state, job_id)
    )
    if binding.get("repair_attempt") != job_attempts:
        reasons.append("campaign_binding_mismatch:repair_attempt")
    if binding.get("max_repairs") != int(job.get("repair_limit", 0)):
        reasons.append("campaign_binding_mismatch:max_repairs")
    if job_attempts > int(job.get("repair_limit", 0)):
        reasons.append("repair_limit_exhausted")
    if job_attempts:
        reconciled = [
            row
            for row in _attempt_rows(state, job_id)
            if row.get("reconciled") is True
            and row.get("attempt_id") == binding.get("reissue_of_attempt_id")
            and row.get("reconciliation_digest")
            == binding.get("prior_reconciliation_digest")
        ]
        if not reconciled:
            reasons.append("prior_attempt_reconciliation_missing")
    projection = state.get("execution_control", {})
    if not isinstance(projection, Mapping):
        projection = {}
    control = validate_campaign_execution_control(projection, binding, as_of=observed)
    reasons.extend(control["reason_codes"])

    if not set(state.get("requested_paths", [])).issubset(
        set(job.get("allowed_paths", []))
    ):
        reasons.append("requested_path_outside_job_scope")
    if not set(state.get("requested_effects", [])).issubset(
        set(required_authorization_effects(manifest))
    ):
        reasons.append("requested_effect_outside_authorization")
    execution = manifest.get("execution", {})
    if (
        execution.get("mode") != "specification_only"
        or execution.get("execution_authorized") is not False
        or execution.get("launch_command") != "not-authorized"
    ):
        reasons.append("prelaunch_manifest_boundary_invalid")

    reasons = sorted(set(reasons))
    return {
        "status": "blocked" if reasons else "ready-manual",
        "reason_codes": reasons,
        "blocking_classes": sorted(
            {
                "human" if reason.startswith("human_authorization") else "machine"
                for reason in reasons
            }
        ),
        "manifest_digest": manifest_digest,
        "authorization_receipt_digest": receipt_digest,
        "packet_digest": actual_packet_digest,
        "budget": budget.as_dict(),
        "manual_packet_ready": not reasons,
        "execution_authorized": False,
        "dispatch_allowed": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def build_job_packet(
    repo_root: Path,
    manifest: Mapping[str, Any],
    job_id: str,
    decision_receipt: Mapping[str, Any],
    *,
    state: Mapping[str, Any] | None = None,
    source_revision: str = "uncommitted-candidate",
    authorization_receipt_digest: str = "",
    as_of: datetime | None = None,
) -> dict[str, Any]:
    jobs = flatten_campaign_jobs(manifest)
    if job_id not in jobs:
        raise ValueError("unknown campaign job")
    job = jobs[job_id]
    state = state or {}
    snapshot = state.get("evidence_snapshot", {})
    if not isinstance(snapshot, Mapping):
        snapshot = {}
    manifest_digest = file_digest(
        repo_root / "docs/campaigns/dad-high-value-recovery/campaign.json"
    )
    receipt_digest = authorization_receipt_digest or canonical_digest(decision_receipt)
    material = _packet_material(
        manifest,
        job,
        manifest_digest=manifest_digest,
        authorization_receipt_digest=receipt_digest,
        snapshot=snapshot,
        source_revision=source_revision,
    )
    packet_digest = canonical_digest(material)
    readiness = validate_job_ready(
        repo_root,
        manifest,
        job_id,
        decision_receipt,
        state=state,
        source_revision=source_revision,
        authorization_receipt_digest=receipt_digest,
        as_of=as_of,
        packet_digest=packet_digest,
    )
    return {
        "schema_version": "dad.campaign.job_packet_candidate.v2",
        "packet_digest": packet_digest,
        **material,
        "readiness": readiness,
        "execution_authorized": False,
        "dispatch_allowed": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def build_campaign_dry_run(
    repo_root: Path,
    manifest: Mapping[str, Any],
    job_id: str,
    decision_receipt: Mapping[str, Any],
    *,
    state: Mapping[str, Any] | None = None,
    source_revision: str = "uncommitted-candidate",
    authorization_receipt_digest: str = "",
    as_of: datetime | None = None,
) -> dict[str, Any]:
    packet = build_job_packet(
        repo_root,
        manifest,
        job_id,
        decision_receipt,
        state=state,
        source_revision=source_revision,
        authorization_receipt_digest=authorization_receipt_digest,
        as_of=as_of,
    )
    return {
        "schema_version": "dad.campaign.prelaunch_dry_run.v2",
        "status": packet["readiness"]["status"],
        "job_id": job_id,
        "packet": packet,
        "effects": {
            "subprocesses_started": 0,
            "model_calls": 0,
            "network_calls": 0,
            "git_changes": 0,
            "downstream_writes": 0,
            "campaign_state_writes": 0,
            "campaign_job_receipts_created": 0,
        },
        "execution_authorized": False,
        "dispatch_allowed": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def build_stop_checkpoint(
    manifest: Mapping[str, Any], *, reason_code: str, active_job_id: str = ""
) -> dict[str, Any]:
    material = {
        "campaign_id": manifest["campaign_id"],
        "campaign_revision": manifest["revision"],
        "reason_code": reason_code,
        "active_job_id": active_job_id,
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "schema_version": "dad.campaign.stop_checkpoint_candidate.v2",
        "checkpoint_digest": canonical_digest(material),
        **material,
        "required_control_actions": [
            "revoke_dispatch_intent_if_present",
            "release_or_revoke_lease_if_active",
            "reconcile_partial_effects_before_reissue",
            "persist_checkpoint_and_receipt_before_resume",
        ],
        "lease_action": "release_or_revoke_if_active",
        "successors_blocked": True,
        "evidence_preserved": True,
        "partial_effect_reconciliation_required": True,
        "checkpoint_write_performed": False,
        "execution_authorized": False,
        "dispatch_allowed": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


__all__ = [
    "AUTHORIZATION_SCHEMA",
    "AUTHORITY_BOUNDARY",
    "BudgetResult",
    "CampaignRuntimeAdapter",
    "EVIDENCE_SNAPSHOT_SCHEMA",
    "build_campaign_dry_run",
    "build_execution_control_binding_candidate",
    "build_job_packet",
    "build_stop_checkpoint",
    "canonical_digest",
    "file_digest",
    "flatten_campaign_jobs",
    "load_campaign_manifest",
    "reconcile_campaign_budget",
    "required_authorization_effects",
    "validate_campaign_state",
    "validate_job_ready",
]
