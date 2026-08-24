#!/usr/bin/env python3
"""Fail closed on malformed, stale, or weak campaign receipt logs.

This checker validates local durability and the machine receipt contract. It
does not validate the truth of referenced evidence, authorize execution, or
update controller state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


CAMPAIGN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = CAMPAIGN_ROOT.parents[2]
STATE_ROOT = CAMPAIGN_ROOT / "state"
MANIFEST_PATH = CAMPAIGN_ROOT / "campaign.json"
SCHEMA_VERSION = "dad.high_value_recovery.evidence_receipt.v1"
RESULTS = {
    "pass",
    "fail_repairable",
    "fail_terminal",
    "blocked_human",
    "inconclusive",
}
COVERAGE = {"complete", "partial", "coverage_unavailable"}
PRIVACY_CLASSES = {"public", "internal_metadata", "restricted_metadata"}
HANDOFF_STATES = {"complete", "failed", "blocked", "resumable"}
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
JOB_ID = re.compile(r"^J-[0-9]{3}(?:-C[0-9]{2})?$")
PLACEHOLDERS = {"", "replace", "unknown", "not-applicable", "not-authorized"}
REQUIRED_FIELDS = {
    "schema_version",
    "campaign_id",
    "campaign_revision",
    "job_id",
    "idempotency_key",
    "checkpoint_path",
    "receipt_path",
    "attempt_id",
    "gate_id",
    "gate_revision",
    "result",
    "source_revision",
    "input_digests",
    "dependency_receipt_digests",
    "producer_role",
    "producer_identity",
    "checker_role",
    "checker_identity",
    "independence_basis",
    "adapter",
    "worker_capability",
    "lease",
    "lease_minutes",
    "heartbeat_minutes",
    "command_or_query",
    "started_at",
    "completed_at",
    "exit_code",
    "evidence_paths",
    "evidence_digests",
    "output_digests",
    "affected_paths",
    "coverage",
    "privacy_class",
    "synthetic_or_fixture",
    "measured_budgets",
    "state",
    "next_action",
    "limitations",
    "revalidation_triggers",
    "authority_boundary",
    "case_binding",
    "case_binding_table_digest",
}


def _text(value: object) -> bool:
    return isinstance(value, str) and value.strip().casefold() not in PLACEHOLDERS


def _digest(value: object) -> bool:
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def _strict_json_loads(text: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON object key: {key}")
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=reject_duplicates)


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _manifest_jobs(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    jobs: dict[str, dict[str, Any]] = {}
    for phase in manifest.get("phases", []):
        for wave in phase.get("waves", []):
            for subwave in wave.get("subwaves", []):
                for job in subwave.get("jobs", []):
                    if isinstance(job, dict) and isinstance(job.get("id"), str):
                        jobs[job["id"]] = job
                        execution = job.get("case_execution", {})
                        child_gate = execution.get("child_acceptance", {})
                        for slot in execution.get("slots", []):
                            if not isinstance(slot, dict) or not isinstance(
                                slot.get("job_id"), str
                            ):
                                continue
                            child_id = str(slot["job_id"])
                            evidence_template = str(
                                child_gate.get("evidence_path_template", "")
                            )
                            jobs[child_id] = {
                                "id": child_id,
                                "parent_id": job["id"],
                                "is_atomic_child": True,
                                "owner_role": execution.get("child_owner_role"),
                                "checker_role": execution.get("child_checker_role"),
                                "inputs": list(job.get("inputs", [])),
                                "input_digests": dict(job.get("input_digests", {})),
                                "depends_on": list(slot.get("depends_on", [])),
                                "outputs": list(job.get("outputs", [])),
                                "allowed_paths": list(job.get("allowed_paths", [])),
                                "idempotency_key": slot.get("idempotency_key"),
                                "lease_minutes": slot.get("lease_minutes"),
                                "heartbeat_minutes": slot.get("heartbeat_minutes"),
                                "checkpoint": slot.get("checkpoint"),
                                "receipt": slot.get("receipt"),
                                "binding_table": execution.get("binding_table"),
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
                                            child_gate.get(
                                                "revalidation_triggers", []
                                            )
                                        ),
                                    }
                                ],
                            }
    return jobs


def _resolved_file_digest(repo_root: Path, relative: str) -> str:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise ValueError(f"unsafe repository-relative evidence path: {relative}")
    resolved = (repo_root / path).resolve(strict=True)
    root = repo_root.resolve(strict=True)
    if root not in resolved.parents or not resolved.is_file():
        raise ValueError(f"evidence path escaped repository or is not a file: {relative}")
    return f"sha256:{hashlib.sha256(resolved.read_bytes()).hexdigest()}"


def _string_list(value: object, *, nonempty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (not nonempty or bool(value))
        and all(_text(item) for item in value)
    )


def _validate_digest_map(
    name: str,
    value: object,
    expected_keys: set[str],
    errors: list[str],
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{name} must be an object")
        return
    if set(value) != expected_keys:
        errors.append(f"{name} keys must equal {sorted(expected_keys)}")
    invalid = sorted(key for key, digest in value.items() if not _digest(digest))
    if invalid:
        errors.append(f"{name} has invalid SHA-256 values for {invalid}")


def validate_receipt(
    row: dict[str, object],
    manifest: dict[str, Any],
    expected_job_id: str | None = None,
    *,
    repo_root: Path = REPO_ROOT,
    verify_files: bool = True,
    verify_dependency_receipts: bool = True,
) -> list[str]:
    """Return fail-closed receipt-contract errors without judging evidence truth."""

    errors: list[str] = []
    missing = sorted(REQUIRED_FIELDS - set(row))
    if missing:
        errors.append(f"missing required fields: {missing}")
        return errors

    if row["schema_version"] != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if row["campaign_id"] != manifest.get("campaign_id"):
        errors.append("campaign_id does not match manifest")
    if row["campaign_revision"] != manifest.get("revision"):
        errors.append("campaign_revision does not match manifest")
    if not _digest(row["source_revision"]):
        errors.append("source_revision must be sha256:<64 lowercase hex>")
    for field in (
        "attempt_id",
        "producer_role",
        "producer_identity",
        "checker_role",
        "checker_identity",
        "independence_basis",
        "command_or_query",
        "next_action",
    ):
        if not _text(row[field]):
            errors.append(f"{field} must be a concrete non-placeholder string")

    job_id = row["job_id"]
    jobs = _manifest_jobs(manifest)
    if not isinstance(job_id, str) or job_id not in jobs:
        errors.append("job_id must name a manifest job")
        return errors
    if expected_job_id is not None and job_id != expected_job_id:
        errors.append(f"job_id must be {expected_job_id}")
    job = jobs[job_id]
    if row["idempotency_key"] != job.get("idempotency_key"):
        errors.append("idempotency_key does not match manifest job/child slot")
    if row["checkpoint_path"] != job.get("checkpoint"):
        errors.append("checkpoint_path does not match manifest job/child slot")
    if row["receipt_path"] != job.get("receipt"):
        errors.append("receipt_path does not match manifest job/child slot")
    if row["lease_minutes"] != job.get("lease_minutes"):
        errors.append("lease_minutes does not match manifest job/child slot")
    if row["heartbeat_minutes"] != job.get("heartbeat_minutes"):
        errors.append("heartbeat_minutes does not match manifest job/child slot")
    if job.get("is_atomic_child"):
        if not _digest(row["case_binding"]):
            errors.append("atomic child case_binding must be a SHA-256 digest")
        if not _digest(row["case_binding_table_digest"]):
            errors.append("atomic child case_binding_table_digest must be a SHA-256 digest")
    elif row["case_binding"] is not None or row["case_binding_table_digest"] is not None:
        errors.append("top-level job receipts must not claim an atomic case binding")

    gates = {
        gate.get("id"): gate
        for gate in job.get("acceptance", [])
        if isinstance(gate, dict) and isinstance(gate.get("id"), str)
    }
    gate = gates.get(row["gate_id"])
    if gate is None:
        errors.append("gate_id must name an acceptance gate for this job")
        return errors
    if row["gate_revision"] != gate.get("revision"):
        errors.append("gate_revision does not match manifest")
    if row["result"] not in RESULTS:
        errors.append(f"result must be one of {sorted(RESULTS)}")
    if row["producer_role"] != job.get("owner_role"):
        errors.append("producer_role does not match job owner_role")
    if row["checker_role"] != gate.get("checker_role"):
        errors.append("checker_role does not match gate checker_role")
    if row["producer_identity"] == row["checker_identity"]:
        errors.append("producer_identity and checker_identity must differ")

    expected_inputs = set(job.get("inputs", []))
    _validate_digest_map("input_digests", row["input_digests"], expected_inputs, errors)
    if row["result"] == "pass" and row["input_digests"] != job.get("input_digests"):
        errors.append("pass input_digests must equal the current manifest revision")
    _validate_digest_map(
        "dependency_receipt_digests",
        row["dependency_receipt_digests"],
        set(job.get("depends_on", [])),
        errors,
    )
    if verify_files and verify_dependency_receipts:
        _resolved_dependencies, dependency_errors = resolve_dependency_receipts(
            repo_root,
            manifest,
            job_id,
            expected_digests=row["dependency_receipt_digests"],
        )
        errors.extend(dependency_errors)

    adapter = row["adapter"]
    if not isinstance(adapter, dict) or not _text(adapter.get("name")) or not _text(
        adapter.get("revision")
    ):
        errors.append("adapter requires concrete name and revision")
    capability = row["worker_capability"]
    if (
        not isinstance(capability, dict)
        or not _text(capability.get("profile_id"))
        or not _string_list(capability.get("qualification_evidence"), nonempty=True)
    ):
        errors.append("worker_capability requires profile_id and qualification_evidence")

    lease = row["lease"]
    if not isinstance(lease, dict):
        errors.append("lease must be an object")
    else:
        for field in ("lease_id", "state"):
            if not _text(lease.get(field)):
                errors.append(f"lease.{field} must be concrete")
        if lease.get("state") != "released":
            errors.append("accepted receipt lease.state must be released")
        issued = _timestamp(lease.get("issued_at"))
        expires = _timestamp(lease.get("expires_at"))
        released = _timestamp(lease.get("released_at"))
        if not all((issued, expires, released)):
            errors.append("lease timestamps must be timezone-aware ISO-8601")
        elif not (issued <= released <= expires):
            errors.append("lease timestamps must satisfy issued <= released <= expires")

    started = _timestamp(row["started_at"])
    completed = _timestamp(row["completed_at"])
    if started is None or completed is None or started > completed:
        errors.append("started_at/completed_at must be ordered timezone-aware ISO-8601")
    exit_code = row["exit_code"]
    if exit_code is not None and (
        isinstance(exit_code, bool) or not isinstance(exit_code, int)
    ):
        errors.append("exit_code must be an integer or null")

    evidence_paths = row["evidence_paths"]
    if not _string_list(evidence_paths, nonempty=True):
        errors.append("evidence_paths must be a non-empty concrete string list")
        evidence_keys: set[str] = set()
    else:
        evidence_keys = set(evidence_paths)
    _validate_digest_map("evidence_digests", row["evidence_digests"], evidence_keys, errors)
    if gate.get("evidence") not in evidence_keys:
        errors.append("evidence_paths must include the manifest gate evidence path")
    if row["checkpoint_path"] not in evidence_keys:
        errors.append("evidence_paths must include checkpoint_path")
    if verify_files and isinstance(row["evidence_digests"], dict):
        for relative, expected in row["evidence_digests"].items():
            try:
                observed = _resolved_file_digest(repo_root, str(relative))
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
            else:
                if observed != expected:
                    errors.append(f"evidence digest does not match file bytes: {relative}")

    output_digests = row["output_digests"]
    if not isinstance(output_digests, dict):
        errors.append("output_digests must be an object")
    else:
        output_keys = set(output_digests)
        declared_outputs = set(job.get("outputs", []))
        if row["result"] == "pass" and output_keys != declared_outputs:
            errors.append("pass output_digests keys must equal declared job outputs")
        elif not output_keys.issubset(declared_outputs):
            errors.append("output_digests contains paths outside declared job outputs")
        if any(not _digest(value) for value in output_digests.values()):
            errors.append("output_digests values must be SHA-256 digests")
        if verify_files:
            for relative, expected in output_digests.items():
                try:
                    observed = _resolved_file_digest(repo_root, str(relative))
                except (OSError, ValueError) as exc:
                    errors.append(str(exc))
                else:
                    if observed != expected:
                        errors.append(f"output digest does not match file bytes: {relative}")
    affected_paths = row["affected_paths"]
    if not _string_list(affected_paths):
        errors.append("affected_paths must be a concrete string list")
    elif not set(affected_paths).issubset(set(job.get("allowed_paths", []))):
        errors.append("affected_paths contains a path outside allowed_paths")

    if row["coverage"] not in COVERAGE:
        errors.append(f"coverage must be one of {sorted(COVERAGE)}")
    if row["result"] == "pass" and row["coverage"] != "complete":
        errors.append("pass requires complete coverage")
    if row["privacy_class"] not in PRIVACY_CLASSES:
        errors.append(f"privacy_class must be one of {sorted(PRIVACY_CLASSES)}")
    if not isinstance(row["synthetic_or_fixture"], bool):
        errors.append("synthetic_or_fixture must be boolean")
    if not _string_list(row["limitations"]):
        errors.append("limitations must be a concrete string list")
    if not _string_list(row["revalidation_triggers"], nonempty=True):
        errors.append("revalidation_triggers must be non-empty")
    elif not set(gate.get("revalidation_triggers", [])).issubset(
        set(row["revalidation_triggers"])
    ):
        errors.append("receipt omits a manifest revalidation trigger")

    budgets = row["measured_budgets"]
    required_budget_fields = {
        "wall_seconds",
        "cost_units",
        "context_tokens",
        "output_bytes",
        "attempt_number",
    }
    if not isinstance(budgets, dict) or set(budgets) != required_budget_fields:
        errors.append(f"measured_budgets keys must equal {sorted(required_budget_fields)}")
    elif any(
        isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0
        for value in budgets.values()
    ):
        errors.append("measured_budgets values must be non-negative numbers")
    elif not isinstance(budgets["attempt_number"], int) or budgets["attempt_number"] < 1:
        errors.append("measured_budgets.attempt_number must be a positive integer")

    if row["state"] not in HANDOFF_STATES:
        errors.append(f"state must be one of {sorted(HANDOFF_STATES)}")
    if not _text(row["authority_boundary"]) or "does not authorize" not in str(
        row["authority_boundary"]
    ).casefold():
        errors.append("authority_boundary must explicitly state that it does not authorize effects")
    return errors


def _read_jsonl(path: Path) -> tuple[list[dict[str, object]], str]:
    data = path.read_bytes()
    if not data or not data.endswith(b"\n"):
        raise ValueError("receipt log must be non-empty and newline-terminated")
    rows: list[dict[str, object]] = []
    for number, raw in enumerate(data.splitlines(), start=1):
        try:
            row = _strict_json_loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"line {number} is invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"line {number} must be a JSON object")
        rows.append(row)
    return rows, f"sha256:{hashlib.sha256(data).hexdigest()}"


def resolve_dependency_receipts(
    repo_root: Path,
    manifest: dict[str, Any],
    job_id: str,
    *,
    expected_digests: object | None = None,
) -> tuple[dict[str, dict[str, object]], list[str]]:
    """Resolve current direct dependency logs to validated, accepted PASS rows."""

    jobs = _manifest_jobs(manifest)
    job = jobs.get(job_id)
    if job is None:
        return {}, ["dependency resolution job is unknown"]
    strict_expected = isinstance(expected_digests, dict)
    expected = expected_digests if strict_expected else {}
    resolved: dict[str, dict[str, object]] = {}
    errors: list[str] = []
    for dependency in job.get("depends_on", []):
        dependency_job = jobs.get(dependency)
        if dependency_job is None:
            errors.append(f"dependency job is unknown: {dependency}")
            continue
        relative = str(dependency_job.get("receipt", ""))
        try:
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts or "\\" in relative:
                raise ValueError(f"unsafe dependency receipt path: {relative}")
            receipt_path = (repo_root / path).resolve(strict=True)
            root = repo_root.resolve(strict=True)
            if root not in receipt_path.parents or not receipt_path.is_file():
                raise ValueError(f"dependency receipt escaped repository: {relative}")
            rows, receipt_digest = _read_jsonl(receipt_path)
        except (OSError, ValueError) as exc:
            errors.append(f"dependency {dependency}: {exc}")
            continue
        if strict_expected and expected.get(dependency) != receipt_digest:
            errors.append(f"dependency receipt digest mismatch: {dependency}")
        latest = rows[-1]
        contract_errors = validate_receipt(
            latest,
            manifest,
            dependency,
            repo_root=repo_root,
            verify_files=True,
            verify_dependency_receipts=False,
        )
        if contract_errors:
            errors.extend(
                f"dependency {dependency}: {error}" for error in contract_errors
            )
            continue
        if (
            latest.get("result") != "pass"
            or latest.get("state") != "complete"
            or latest.get("coverage") != "complete"
        ):
            errors.append(f"dependency latest receipt is not accepted PASS: {dependency}")
            continue
        resolved[dependency] = {
            "receipt_digest": receipt_digest,
            "result": latest.get("result"),
            "state": latest.get("state"),
            "output_digests": dict(latest.get("output_digests", {})),
            "verifier_status": "pass",
        }
    return resolved, errors


def resolve_campaign_budget_receipts(
    repo_root: Path,
    manifest: dict[str, Any],
) -> tuple[list[dict[str, object]], dict[str, str], list[str]]:
    """Aggregate measured budgets from every existing validated receipt row."""

    attempts: list[dict[str, object]] = []
    receipt_digests: dict[str, str] = {}
    errors: list[str] = []
    seen_attempts: set[str] = set()
    for job_id, job in sorted(_manifest_jobs(manifest).items()):
        relative = str(job.get("receipt", ""))
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or "\\" in relative:
            errors.append(f"budget receipt path is unsafe: {job_id}:{relative}")
            continue
        receipt_path = (repo_root / path).resolve()
        root = repo_root.resolve()
        if root not in receipt_path.parents:
            errors.append(f"budget receipt escaped repository: {job_id}:{relative}")
            continue
        if not receipt_path.exists():
            continue
        try:
            rows, receipt_digest = _read_jsonl(receipt_path)
        except (OSError, ValueError) as exc:
            errors.append(f"budget receipt {job_id}: {exc}")
            continue
        receipt_digests[relative] = receipt_digest
        for index, row in enumerate(rows, start=1):
            contract_errors = validate_receipt(
                row,
                manifest,
                job_id,
                repo_root=repo_root,
                verify_files=True,
                verify_dependency_receipts=True,
            )
            if contract_errors:
                errors.extend(
                    f"budget receipt {job_id} line {index}: {error}"
                    for error in contract_errors
                )
                continue
            attempt_id = str(row["attempt_id"])
            if attempt_id in seen_attempts:
                errors.append(f"budget receipt attempt identity duplicated: {attempt_id}")
                continue
            seen_attempts.add(attempt_id)
            budgets = row["measured_budgets"]
            assert isinstance(budgets, dict)
            attempts.append(
                {
                    "job_id": job_id,
                    "attempt_id": attempt_id,
                    "attempt_count": 1,
                    "cost_units": budgets["cost_units"],
                    "wall_seconds": budgets["wall_seconds"],
                    "context_tokens": budgets["context_tokens"],
                    "output_mb": float(budgets["output_bytes"]) / (1024 * 1024),
                    "budget_evidence_complete": True,
                    "receipt_path": relative,
                    "receipt_digest": receipt_digest,
                }
            )
    return attempts, receipt_digests, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_id", nargs="?", help="Validate one job receipt log")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    args = parser.parse_args()

    if args.job_id is not None and JOB_ID.fullmatch(args.job_id) is None:
        print(json.dumps({"status": "invalid", "reason": "job_id must match J-NNN"}))
        return 1
    path = STATE_ROOT / "receipts.jsonl"
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        jobs = _manifest_jobs(manifest)
        if args.job_id is None:
            path = STATE_ROOT / "receipts.jsonl"
        elif args.job_id not in jobs:
            raise ValueError("job_id must name a manifest job or atomic child slot")
        else:
            path = REPO_ROOT / str(jobs[args.job_id]["receipt"])
        resolved = path.resolve(strict=True)
        state_resolved = STATE_ROOT.resolve(strict=True)
        if state_resolved not in resolved.parents:
            raise ValueError("receipt path escaped controller state root")
        rows, digest = _read_jsonl(resolved)
        contract_errors: list[str] = []
        for number, row in enumerate(rows, start=1):
            contract_errors.extend(
                f"line {number}: {error}"
                for error in validate_receipt(
                    row,
                    manifest,
                    args.job_id,
                    repo_root=REPO_ROOT,
                    verify_files=True,
                )
            )
        if contract_errors:
            raise ValueError("; ".join(contract_errors))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "invalid", "path": str(path), "reason": str(exc)}))
        return 1

    print(
        json.dumps(
            {
                "status": "valid",
                "path": str(resolved),
                "rows": len(rows),
                "digest": digest,
                "contract": SCHEMA_VERSION,
                "authority_boundary": (
                    "Receipt validation does not prove evidence truth or authorize execution."
                ),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
