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
CHECKER_RECORD_SCHEMA_VERSION = "dad.high_value_recovery.checker_record.v1"
CHECKER_RECEIPT_DIGEST_SEMANTICS = "checker-file-bytes"
CASE_BINDING_TABLE_SCHEMA = "dad.campaign.atomic_case_binding_table.v2"
COHORT_CLOSURE_SCHEMA = "dad.campaign.cohort_closure.v1"
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
RECEIPT_BOUND_DIGEST = "receipt-bound-output-digest:"
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
    "case_envelope_path",
    "cohort_closure_digest",
    "terminal_route",
    "navigation_receipt_digest",
    "producer_attempt_digest",
    "checker_record_path",
    "checker_record_digest",
}

CHECKER_RECORD_FIELDS = {
    "schema_version",
    "campaign_id",
    "campaign_revision",
    "job_id",
    "attempt_id",
    "producer_attempt_digest",
    "producer_identity",
    "checker_role",
    "checker_identity",
    "independence_basis",
    "disposition",
    "checked_at",
    "limitations",
    "record_digest",
}
CHECKER_DISPOSITIONS = {"pass", "challenge"}
PRODUCER_DIGEST_EXCLUDED_FIELDS = {
    "producer_attempt_digest",
    "checker_role",
    "checker_identity",
    "independence_basis",
    "checker_record_path",
    "checker_record_digest",
}
TERMINAL_ROUTE_IDS = {
    "p5a-valid-terminal",
    "p5a-inconclusive",
    "p5b-valid-terminal",
    "p5b-inconclusive",
    "p5c-pass",
    "p5c-valid-terminal",
    "p5c-inconclusive",
}
TERMINAL_ROUTE_SPECS = {
    "p5a-valid-terminal": ("J-510", "fail_terminal", ["narrow", "retire"]),
    "p5a-inconclusive": ("J-510", "inconclusive", ["re-audit"]),
    "p5b-valid-terminal": ("J-520", "fail_terminal", ["narrow", "retire"]),
    "p5b-inconclusive": ("J-520", "inconclusive", ["re-audit"]),
    "p5c-pass": (
        "J-530",
        "pass",
        ["scale", "narrow", "retire", "re-audit"],
    ),
    "p5c-valid-terminal": ("J-530", "fail_terminal", ["narrow", "retire"]),
    "p5c-inconclusive": ("J-530", "inconclusive", ["re-audit"]),
}
TERMINAL_ROUTE_TRIGGERS = {
    "p5a-valid-terminal": {"privacy", "source-authority", "harmful", "material-safety"},
    "p5a-inconclusive": {
        "missing",
        "stale",
        "unjoinable",
        "metric-corruption",
        "checker-integrity",
    },
    "p5b-valid-terminal": {"frozen-benefit-failure", "safety", "authority"},
    "p5b-inconclusive": {
        "missing",
        "stale",
        "unjoinable",
        "metric-corruption",
        "checker-integrity",
    },
    "p5c-pass": {"value-gate-pass"},
    "p5c-valid-terminal": {
        "frozen-benefit-failure",
        "guardrail-failure",
        "safety",
        "authority",
    },
    "p5c-inconclusive": {
        "missing",
        "stale",
        "unjoinable",
        "metric-corruption",
        "checker-integrity",
    },
}
TERMINAL_ROUTE_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,127}$")
NAVIGATION_RECEIPT_SCHEMA = "dad.campaign.navigation_receipt.v1"
NAVIGATION_PRE_STAGE = "accepted-terminal-route"
NAVIGATION_POST_STAGE = "post-j600-signed-decision"
NAVIGATION_INDEX_PATH = (
    "docs/campaigns/dad-high-value-recovery/07_EVIDENCE_INDEX.md"
)
NAVIGATION_HANDOFF_PATH = "docs/campaigns/dad-high-value-recovery/handoff.md"
NAVIGATION_SUPERSESSION_PATH = (
    "docs/campaigns/dad-high-value-recovery/08_SUPERSESSION_AND_ARCHIVE_MAP.md"
)
NAVIGATION_PRE_RECEIPT_TEMPLATE = (
    "docs/campaigns/dad-high-value-recovery/checks/evidence/navigation/"
    "{route_id}.json"
)
NAVIGATION_POST_RECEIPT_TEMPLATE = (
    "docs/campaigns/dad-high-value-recovery/checks/evidence/navigation/"
    "{route_id}-post-j600.json"
)


def _text(value: object) -> bool:
    return isinstance(value, str) and value.strip().casefold() not in PLACEHOLDERS


def _digest(value: object) -> bool:
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def canonical_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def producer_attempt_digest(row: dict[str, object]) -> str:
    """Digest immutable producer material without circular checker fields."""

    material = {
        key: row[key]
        for key in sorted(REQUIRED_FIELDS - PRODUCER_DIGEST_EXCLUDED_FIELDS)
        if key in row
    }
    return canonical_digest(material)


def checker_record_digest(record: dict[str, object]) -> str:
    return canonical_digest(
        {key: value for key, value in record.items() if key != "record_digest"}
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
                        if job["id"] in jobs:
                            raise ValueError(f"duplicate manifest job identity: {job['id']}")
                        jobs[job["id"]] = job
                        execution = job.get("case_execution", {})
                        child_gate = execution.get("child_acceptance", {})
                        for slot in execution.get("slots", []):
                            if not isinstance(slot, dict) or not isinstance(
                                slot.get("job_id"), str
                            ):
                                continue
                            child_id = str(slot["job_id"])
                            if child_id in jobs:
                                raise ValueError(
                                    f"duplicate atomic child identity: {child_id}"
                                )
                            evidence_template = str(
                                child_gate.get("evidence_path_template", "")
                            )
                            envelope_template = str(
                                execution.get(
                                    "case_envelope_path_template",
                                    "processed/reports/dad-high-value-recovery/"
                                    "pilot-case-envelopes/{job_id}.json",
                                )
                            )
                            envelope = envelope_template.replace("{job_id}", child_id)
                            jobs[child_id] = {
                                "id": child_id,
                                "parent_id": job["id"],
                                "is_atomic_child": True,
                                "sequence": slot.get("sequence"),
                                "owner_role": execution.get("child_owner_role"),
                                "checker_role": execution.get("child_checker_role"),
                                "inputs": list(job.get("inputs", [])),
                                "input_digests": dict(job.get("input_digests", {})),
                                "depends_on": list(slot.get("depends_on", [])),
                                "outputs": [envelope],
                                "allowed_paths": [envelope],
                                "case_envelope": envelope,
                                "idempotency_key": slot.get("idempotency_key"),
                                "lease_minutes": slot.get("lease_minutes"),
                                "heartbeat_minutes": slot.get("heartbeat_minutes"),
                                "checkpoint": slot.get("checkpoint"),
                                "receipt": slot.get("receipt"),
                                "binding_table": execution.get("binding_table"),
                                "binding_revision": execution.get("binding_revision"),
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


def _read_repo_json(repo_root: Path, relative: str) -> tuple[dict[str, object], str]:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise ValueError(f"unsafe repository-relative JSON path: {relative}")
    resolved = (repo_root / path).resolve(strict=True)
    root = repo_root.resolve(strict=True)
    if root not in resolved.parents or not resolved.is_file():
        raise ValueError(f"JSON path escaped repository or is not a file: {relative}")
    value = _strict_json_loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON artifact must be an object: {relative}")
    return value, f"sha256:{hashlib.sha256(resolved.read_bytes()).hexdigest()}"


def _digest_without(value: dict[str, object], digest_field: str) -> str:
    return canonical_digest(
        {key: item for key, item in value.items() if key != digest_field}
    )


def validate_case_binding_table(
    manifest: dict[str, Any], table: dict[str, object]
) -> list[str]:
    """Validate all pilot child bindings, not merely one claimed case digest."""

    errors: list[str] = []
    if table.get("schema_version") != CASE_BINDING_TABLE_SCHEMA:
        errors.append("case binding table schema is invalid")
    if table.get("campaign_id") != manifest.get("campaign_id"):
        errors.append("case binding table campaign_id does not match manifest")
    if table.get("campaign_revision") != manifest.get("revision"):
        errors.append("case binding table campaign_revision does not match manifest")
    if table.get("binding_table_digest") != _digest_without(
        table, "binding_table_digest"
    ):
        errors.append("case binding table self-digest does not match")

    jobs = _manifest_jobs(manifest)
    expected = {
        job_id: job for job_id, job in jobs.items() if job.get("is_atomic_child")
    }
    raw_rows = table.get("bindings")
    if not isinstance(raw_rows, list):
        return [*errors, "case binding table bindings must be an array"]
    rows = [row for row in raw_rows if isinstance(row, dict)]
    if len(rows) != len(raw_rows):
        errors.append("case binding table contains a non-object row")
    job_ids = [str(row.get("job_id", "")) for row in rows]
    case_ids = [str(row.get("case_id", "")) for row in rows]
    case_digests = [str(row.get("case_digest", "")) for row in rows]
    if set(job_ids) != set(expected) or len(job_ids) != len(expected):
        errors.append("case binding table must bind every atomic child exactly once")
    if len(set(job_ids)) != len(job_ids):
        errors.append("case binding table contains a duplicate child slot")
    if any(not _text(value) for value in case_ids) or len(set(case_ids)) != len(case_ids):
        errors.append("case binding table case identities must be concrete and unique")
    if any(not _digest(value) for value in case_digests) or len(
        set(case_digests)
    ) != len(case_digests):
        errors.append("case binding table case digests must be valid and unique")

    for row in rows:
        job_id = str(row.get("job_id", ""))
        job = expected.get(job_id)
        if job is None:
            continue
        case_digest = str(row.get("case_digest", ""))
        expected_idempotency = str(job.get("idempotency_key", "")).replace(
            "{case_digest}", case_digest
        )
        expected_values = {
            "sequence": job.get("sequence"),
            "depends_on": job.get("depends_on"),
            "idempotency_key": expected_idempotency,
            "checkpoint_path": job.get("checkpoint"),
            "receipt_path": job.get("receipt"),
            "envelope_path": job.get("case_envelope"),
        }
        for field, expected_value in expected_values.items():
            if row.get(field) != expected_value:
                errors.append(f"case binding row mismatch: {job_id}:{field}")
    return sorted(set(errors))


def validate_cohort_closure(
    manifest: dict[str, Any], parent_job_id: str, closure: dict[str, object]
) -> list[str]:
    """Require a complete exact child partition with no live runtime residue."""

    errors: list[str] = []
    if closure.get("schema_version") != COHORT_CLOSURE_SCHEMA:
        errors.append("cohort closure schema is invalid")
    if closure.get("campaign_id") != manifest.get("campaign_id"):
        errors.append("cohort closure campaign_id does not match manifest")
    if closure.get("campaign_revision") != manifest.get("revision"):
        errors.append("cohort closure campaign_revision does not match manifest")
    if closure.get("parent_job_id") != parent_job_id:
        errors.append("cohort closure parent_job_id does not match")
    if closure.get("closure_digest") != _digest_without(closure, "closure_digest"):
        errors.append("cohort closure self-digest does not match")

    jobs = _manifest_jobs(manifest)
    expected_order = [
        job_id
        for job_id, job in sorted(
            jobs.items(), key=lambda item: int(item[1].get("sequence") or 0)
        )
        if job.get("is_atomic_child") and job.get("parent_id") == parent_job_id
    ]
    expected = set(expected_order)
    started = closure.get("started_children")
    unstarted = closure.get("unstarted_or_withdrawn_children")
    if not isinstance(started, list) or not isinstance(unstarted, list):
        return [*errors, "cohort closure child partition must contain arrays"]
    started_rows = [row for row in started if isinstance(row, dict)]
    unstarted_rows = [row for row in unstarted if isinstance(row, dict)]
    if len(started_rows) != len(started) or len(unstarted_rows) != len(unstarted):
        errors.append("cohort closure child partition contains a non-object row")
    started_ids = [str(row.get("job_id", "")) for row in started_rows]
    unstarted_ids = [str(row.get("job_id", "")) for row in unstarted_rows]
    combined = started_ids + unstarted_ids
    if set(started_ids) & set(unstarted_ids) or set(combined) != expected:
        errors.append("cohort closure does not exactly partition the child slots")
    if len(set(combined)) != len(combined):
        errors.append("cohort closure contains a duplicate child slot")
    if (
        started_ids != expected_order[: len(started_ids)]
        or unstarted_ids != expected_order[len(started_ids) :]
    ):
        errors.append(
            "cohort closure must contain a sequence-ordered started prefix and "
            "unstarted suffix"
        )
    started_keys = {
        "job_id",
        "receipt_digest",
        "checker_record_digest",
        "checker_disposition",
        "durability_verified",
    }
    unstarted_keys = {"job_id", "reason_code", "reason_digest"}
    for row in started_rows:
        if set(row) != started_keys:
            errors.append(
                f"cohort closure started child keys are invalid: {row.get('job_id')}"
            )
        if (
            not _digest(row.get("receipt_digest"))
            or not _digest(row.get("checker_record_digest"))
            or row.get("checker_disposition") != "pass"
            or row.get("durability_verified") is not True
        ):
            errors.append(
                f"cohort closure started child is not durably accepted: {row.get('job_id')}"
            )
    for row in unstarted_rows:
        if set(row) != unstarted_keys:
            errors.append(
                f"cohort closure unstarted child keys are invalid: {row.get('job_id')}"
            )
        if not _text(row.get("reason_code")) or not _digest(
            row.get("reason_digest")
        ):
            errors.append(
                "cohort closure unstarted child lacks immutable reason: "
                f"{row.get('job_id')}"
            )
    for field in (
        "active_lease_count",
        "unreconciled_effect_count",
        "post_stop_receipt_count",
        "post_stop_lease_count",
    ):
        if closure.get(field) != 0:
            errors.append(f"cohort closure runtime residue is nonzero: {field}")
    if closure.get("stop_trigger") is None or not _digest(
        closure.get("stop_trigger_digest")
    ):
        errors.append("cohort closure stop trigger is not digest-bound")
    if closure.get("closure_complete") is not True:
        errors.append("cohort closure is not complete")
    return sorted(set(errors))


def validate_terminal_route(route: object) -> list[str]:
    if not isinstance(route, dict):
        return ["terminal_route must be an object"]
    required = {
        "dependency_route_id",
        "predecessor_job_id",
        "predecessor_receipt_digest",
        "predecessor_result",
        "predecessor_state",
        "predecessor_coverage",
        "trigger_class",
        "closure_digest",
        "closure_complete",
        "navigation_receipt_digest",
        "permitted_decisions",
    }
    errors: list[str] = []
    if set(route) != required:
        errors.append(f"terminal_route keys must equal {sorted(required)}")
        return errors
    route_id = route.get("dependency_route_id")
    if (
        not isinstance(route_id, str)
        or TERMINAL_ROUTE_PATTERN.fullmatch(route_id) is None
        or route_id not in TERMINAL_ROUTE_IDS
    ):
        errors.append("terminal_route dependency_route_id is invalid")
    if route.get("predecessor_job_id") not in {"J-510", "J-520", "J-530"}:
        errors.append("terminal_route predecessor_job_id is invalid")
    if not _digest(route.get("predecessor_receipt_digest")):
        errors.append("terminal_route predecessor_receipt_digest is invalid")
    if not _digest(route.get("closure_digest")):
        errors.append("terminal_route closure_digest is invalid")
    if route.get("closure_complete") is not True:
        errors.append("terminal_route closure_complete must be true")
    if not _digest(route.get("navigation_receipt_digest")):
        errors.append("terminal_route navigation_receipt_digest is invalid")
    if route.get("predecessor_result") not in RESULTS:
        errors.append("terminal_route predecessor_result is invalid")
    if route.get("predecessor_state") not in HANDOFF_STATES:
        errors.append("terminal_route predecessor_state is invalid")
    if route.get("predecessor_coverage") not in COVERAGE:
        errors.append("terminal_route predecessor_coverage is invalid")
    if not _text(route.get("trigger_class")):
        errors.append("terminal_route trigger_class must be concrete")
    decisions = route.get("permitted_decisions")
    if not _string_list(decisions, nonempty=True) or not set(decisions).issubset(
        {"scale", "narrow", "retire", "re-audit"}
    ):
        errors.append("terminal_route permitted_decisions are invalid")
    spec = TERMINAL_ROUTE_SPECS.get(str(route_id))
    if spec is not None:
        predecessor, required_result, permitted = spec
        if route.get("predecessor_job_id") != predecessor:
            errors.append("terminal_route predecessor does not match route_id")
        if decisions != permitted:
            errors.append("terminal_route permitted_decisions do not match route_id")
        if route.get("trigger_class") not in TERMINAL_ROUTE_TRIGGERS[str(route_id)]:
            errors.append("terminal_route trigger_class does not match route_id")
        result = route.get("predecessor_result")
        state = route.get("predecessor_state")
        coverage = route.get("predecessor_coverage")
        if required_result == "pass" and (result, state, coverage) != (
            "pass",
            "complete",
            "complete",
        ):
            errors.append("terminal_route p5c pass outcome contract is invalid")
        elif required_result == "fail_terminal" and (result, state, coverage) != (
            "fail_terminal",
            "failed",
            "complete",
        ):
            errors.append("terminal_route valid-terminal outcome contract is invalid")
        elif required_result == "inconclusive" and not (
            result in {"inconclusive", "blocked_human"}
            and state == "blocked"
            and coverage in {"partial", "coverage_unavailable"}
        ):
            errors.append("terminal_route inconclusive outcome contract is invalid")
    return errors


def resolve_case_binding_table(
    repo_root: Path, manifest: dict[str, Any]
) -> tuple[dict[str, object], list[str]]:
    """Load and validate the one shared immutable pilot binding table."""

    paths = {
        str(job.get("case_execution", {}).get("binding_table", ""))
        for job in _manifest_jobs(manifest).values()
        if isinstance(job.get("case_execution"), dict)
        and job.get("case_execution", {}).get("slots")
    }
    if len(paths) != 1 or not next(iter(paths), ""):
        return {}, ["pilot stages must declare one shared case binding table path"]
    relative = next(iter(paths))
    try:
        table, _file_digest = _read_repo_json(repo_root, relative)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, [f"case binding table is unavailable: {exc}"]
    errors = validate_case_binding_table(manifest, table)
    return (table if not errors else {}), errors


def resolve_case_binding_provenance(
    repo_root: Path, manifest: dict[str, Any]
) -> tuple[dict[str, object], list[str]]:
    """Bind the shared table to one checker-accepted J-500 receipt and file."""

    table, errors = resolve_case_binding_table(repo_root, manifest)
    if errors:
        return {}, errors
    jobs = _manifest_jobs(manifest)
    j500 = jobs.get("J-500")
    if j500 is None:
        return {}, ["case binding provenance requires manifest job J-500"]
    table_paths = {
        str(job.get("case_execution", {}).get("binding_table", ""))
        for job in jobs.values()
        if isinstance(job.get("case_execution"), dict)
        and job.get("case_execution", {}).get("slots")
    }
    table_path = next(iter(table_paths), "")
    if table_path not in j500.get("outputs", []):
        return {}, ["J-500 does not declare the shared binding table as an output"]
    try:
        _table_copy, table_file_digest = _read_repo_json(repo_root, table_path)
        relative_receipt = str(j500.get("receipt", ""))
        receipt_path = Path(relative_receipt)
        if (
            receipt_path.is_absolute()
            or ".." in receipt_path.parts
            or "\\" in relative_receipt
        ):
            raise ValueError(f"unsafe J-500 receipt path: {relative_receipt}")
        resolved_receipt = (repo_root / receipt_path).resolve(strict=True)
        root = repo_root.resolve(strict=True)
        if root not in resolved_receipt.parents or not resolved_receipt.is_file():
            raise ValueError("J-500 receipt escaped repository or is not a file")
        rows, j500_receipt_digest = _read_jsonl(resolved_receipt)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, [f"case binding J-500 provenance is unavailable: {exc}"]
    latest = rows[-1]
    receipt_errors = validate_receipt(
        latest,
        manifest,
        "J-500",
        repo_root=repo_root,
        verify_files=True,
        verify_dependency_receipts=False,
    )
    errors = [f"case binding J-500 receipt: {error}" for error in receipt_errors]
    latest_outputs = latest.get("output_digests")
    if (
        not isinstance(latest_outputs, dict)
        or latest_outputs.get(table_path) != table_file_digest
    ):
        errors.append("J-500 receipt does not bind the current binding-table file bytes")
    if (
        latest.get("result"),
        latest.get("state"),
        latest.get("coverage"),
    ) != ("pass", "complete", "complete"):
        errors.append("J-500 binding-table provenance is not accepted PASS")
    if errors:
        return {}, sorted(set(errors))
    return {
        "binding_table_path": table_path,
        "binding_table_file_digest": table_file_digest,
        "binding_table_digest": table.get("binding_table_digest"),
        "j500_receipt_digest": j500_receipt_digest,
        "checker_record_digest": latest.get("checker_record_digest"),
        "checker_disposition": "pass",
        "verifier_status": "pass",
        "j500_result": "pass",
        "j500_state": "complete",
        "j500_coverage": "complete",
    }, []


def resolve_cohort_closure(
    repo_root: Path, manifest: dict[str, Any], parent_job_id: str
) -> tuple[dict[str, object], list[str]]:
    """Load one declared cohort closure and require an exact terminal partition."""

    parent = _manifest_jobs(manifest).get(parent_job_id)
    if parent is None or not isinstance(parent.get("case_execution"), dict):
        return {}, [f"cohort closure parent is unknown: {parent_job_id}"]
    relative = str(parent["case_execution"].get("closure_path", ""))
    if not relative:
        return {}, [f"cohort closure path is missing: {parent_job_id}"]
    try:
        closure, _file_digest = _read_repo_json(repo_root, relative)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, [f"cohort closure {parent_job_id} is unavailable: {exc}"]
    errors = validate_cohort_closure(manifest, parent_job_id, closure)
    jobs = _manifest_jobs(manifest)
    for row in closure.get("started_children", []):
        if not isinstance(row, dict):
            continue
        child_id = str(row.get("job_id", ""))
        child = jobs.get(child_id)
        if (
            child is None
            or not child.get("is_atomic_child")
            or child.get("parent_id") != parent_job_id
        ):
            errors.append(f"cohort closure started child is outside cohort: {child_id}")
            continue
        relative_receipt = str(child.get("receipt", ""))
        try:
            receipt_path = Path(relative_receipt)
            if (
                receipt_path.is_absolute()
                or ".." in receipt_path.parts
                or "\\" in relative_receipt
            ):
                raise ValueError(f"unsafe child receipt path: {relative_receipt}")
            resolved_receipt = (repo_root / receipt_path).resolve(strict=True)
            root = repo_root.resolve(strict=True)
            if root not in resolved_receipt.parents or not resolved_receipt.is_file():
                raise ValueError("child receipt escaped repository or is not a file")
            receipt_rows, receipt_digest = _read_jsonl(resolved_receipt)
        except (OSError, ValueError) as exc:
            errors.append(f"cohort child receipt {child_id} is unavailable: {exc}")
            continue
        if row.get("receipt_digest") != receipt_digest:
            errors.append(f"cohort child receipt log digest does not match: {child_id}")
        latest = receipt_rows[-1]
        child_errors = validate_receipt(
            latest,
            manifest,
            child_id,
            repo_root=repo_root,
            verify_files=True,
            verify_dependency_receipts=False,
        )
        errors.extend(f"cohort child {child_id}: {error}" for error in child_errors)
        if latest.get("checker_record_digest") != row.get("checker_record_digest"):
            errors.append(f"cohort child checker digest does not match: {child_id}")
        if (
            latest.get("result"),
            latest.get("state"),
            latest.get("coverage"),
        ) != ("pass", "complete", "complete"):
            errors.append(f"cohort child terminal receipt is not accepted PASS: {child_id}")
    return (closure if not errors else {}), errors


def _navigation_projection_digest(
    manifest: dict[str, Any],
    route: dict[str, object],
    *,
    post_j600: bool,
    navigation_paths: list[str],
    j600_receipt_digest: str | None = None,
) -> str:
    """Rebuild the controller's immutable projection digest without receipt bytes."""

    route_material = dict(route)
    if not post_j600:
        # The accepted-terminal-route projection necessarily predates its own
        # receipt and must never claim or bind that future file digest.
        route_material.pop("navigation_receipt_digest", None)
    receipt_path = navigation_paths[-1]
    material: dict[str, object] = {
        "campaign_id": manifest.get("campaign_id"),
        "campaign_revision": manifest.get("revision"),
        **route_material,
        "writer_role": "campaign-navigation-writer",
        "checker_role": "independent-checker",
        "action_class": "validate",
        "navigation_paths": navigation_paths,
        "expected_navigation_receipt_path": receipt_path,
        "navigation_stage": NAVIGATION_POST_STAGE if post_j600 else NAVIGATION_PRE_STAGE,
        "final_receipt_requires_signed_j600": post_j600,
        "required_receipt_bindings": [
            "projection_digest",
            "navigation_stage",
            "navigation_paths",
            "output_digests",
            "dependency_route_id",
            "predecessor_receipt_digest",
            "closure_digest",
            *(
                ["navigation_receipt_digest", "j600_receipt_digest"]
                if post_j600
                else []
            ),
        ],
    }
    if post_j600:
        material["j600_receipt_digest"] = j600_receipt_digest
    return canonical_digest(material)


def _validate_navigation_receipt_stage(
    manifest: dict[str, Any],
    route: dict[str, object],
    receipt: dict[str, object],
    *,
    post_j600: bool,
    j600_receipt_digest: str | None = None,
    repo_root: Path = REPO_ROOT,
    verify_current_outputs: bool = True,
) -> list[str]:
    """Validate one immutable, stage-specific navigation acceptance receipt."""

    required = {
        "schema_version",
        "campaign_id",
        "campaign_revision",
        "dependency_route_id",
        "predecessor_job_id",
        "predecessor_receipt_digest",
        "predecessor_result",
        "predecessor_state",
        "predecessor_coverage",
        "trigger_class",
        "closure_digest",
        "projection_digest",
        "navigation_stage",
        "navigation_paths",
        "output_digests",
        "writer_role",
        "writer_identity",
        "checker_role",
        "checker_identity",
        "checker_disposition",
        "independence_basis",
        "checked_at",
    }
    if post_j600:
        required.add("j600_receipt_digest")
        required.add("navigation_receipt_digest")
    errors: list[str] = []
    if set(receipt) != required:
        errors.append(f"navigation receipt fields must equal {sorted(required)}")
    navigation = manifest.get("terminal_navigation", {})
    if receipt.get("schema_version") != NAVIGATION_RECEIPT_SCHEMA:
        errors.append("navigation receipt schema_version is invalid")
    if receipt.get("campaign_id") != manifest.get("campaign_id"):
        errors.append("navigation receipt campaign_id does not match manifest")
    if receipt.get("campaign_revision") != manifest.get("revision"):
        errors.append("navigation receipt campaign_revision does not match manifest")
    route_mapping = {
        "dependency_route_id": "dependency_route_id",
        "predecessor_job_id": "predecessor_job_id",
        "predecessor_receipt_digest": "predecessor_receipt_digest",
        "predecessor_result": "predecessor_result",
        "predecessor_state": "predecessor_state",
        "predecessor_coverage": "predecessor_coverage",
        "trigger_class": "trigger_class",
        "closure_digest": "closure_digest",
    }
    for receipt_field, route_field in route_mapping.items():
        if receipt.get(receipt_field) != route.get(route_field):
            errors.append(f"navigation receipt {receipt_field} does not match route")
    route_id = route.get("dependency_route_id")
    template_key = (
        "post_j600_receipt_path_template" if post_j600 else "receipt_path_template"
    )
    expected_template = (
        NAVIGATION_POST_RECEIPT_TEMPLATE
        if post_j600
        else NAVIGATION_PRE_RECEIPT_TEMPLATE
    )
    if not isinstance(navigation, dict) or navigation.get(template_key) != expected_template:
        errors.append("navigation receipt path template does not match its stage")
    expected_receipt_path = expected_template.replace("{route_id}", str(route_id))
    expected_paths = [NAVIGATION_INDEX_PATH, NAVIGATION_HANDOFF_PATH]
    if post_j600:
        expected_paths.append(NAVIGATION_SUPERSESSION_PATH)
    expected_paths.append(expected_receipt_path)
    if receipt.get("navigation_paths") != expected_paths:
        errors.append("navigation receipt paths do not match its exact stage")
    mutable_paths = set(expected_paths[:-1])
    _validate_digest_map(
        "navigation receipt output_digests",
        receipt.get("output_digests"),
        mutable_paths,
        errors,
    )
    if verify_current_outputs and isinstance(receipt.get("output_digests"), dict):
        for relative, digest in receipt["output_digests"].items():
            try:
                observed = _resolved_file_digest(repo_root, relative)
            except (OSError, ValueError) as exc:
                errors.append(f"navigation output is unavailable: {relative}: {exc}")
                continue
            if digest != observed:
                errors.append(
                    f"navigation output digest does not match file bytes: {relative}"
                )
    expected_stage = NAVIGATION_POST_STAGE if post_j600 else NAVIGATION_PRE_STAGE
    if receipt.get("navigation_stage") != expected_stage:
        errors.append("navigation receipt stage is invalid")
    if not _digest(receipt.get("projection_digest")):
        errors.append("navigation receipt projection_digest is invalid")
    elif receipt.get("projection_digest") != _navigation_projection_digest(
        manifest,
        route,
        post_j600=post_j600,
        navigation_paths=expected_paths,
        j600_receipt_digest=j600_receipt_digest,
    ):
        errors.append("navigation receipt projection_digest does not match projection")
    if post_j600:
        if not _digest(j600_receipt_digest):
            errors.append("post-J600 navigation requires a signed J-600 receipt digest")
        if receipt.get("j600_receipt_digest") != j600_receipt_digest:
            errors.append("navigation receipt j600_receipt_digest does not match")
        if not _digest(route.get("navigation_receipt_digest")):
            errors.append("post-J600 navigation route must bind the pre-J600 receipt")
        if receipt.get("navigation_receipt_digest") != route.get(
            "navigation_receipt_digest"
        ):
            errors.append(
                "post-J600 navigation receipt does not bind the pre-J600 receipt digest"
            )
    navigation_writer = (
        navigation.get("writer_role")
        if isinstance(navigation, dict)
        else None
    ) or "campaign-navigation-writer"
    navigation_checker = (
        navigation.get("checker_role")
        if isinstance(navigation, dict)
        else None
    ) or "independent-checker"
    if receipt.get("writer_role") != navigation_writer:
        errors.append("navigation receipt writer_role does not match manifest")
    if receipt.get("checker_role") != navigation_checker:
        errors.append("navigation receipt checker_role does not match manifest")
    if not _text(receipt.get("writer_identity")) or not _text(
        receipt.get("checker_identity")
    ):
        errors.append("navigation receipt identities must be concrete")
    if receipt.get("writer_identity") == receipt.get("checker_identity"):
        errors.append("navigation writer and checker identities must differ")
    if receipt.get("checker_disposition") != "pass":
        errors.append("navigation receipt checker disposition is not pass")
    if not _text(receipt.get("independence_basis")):
        errors.append("navigation receipt independence_basis must be concrete")
    if _timestamp(receipt.get("checked_at")) is None:
        errors.append("navigation receipt checked_at must be timezone-aware")
    return errors


def validate_navigation_receipt(
    manifest: dict[str, Any],
    route: dict[str, object],
    receipt: dict[str, object],
    *,
    repo_root: Path = REPO_ROOT,
    verify_current_outputs: bool = True,
) -> list[str]:
    """Validate accepted-terminal-route navigation before J-600."""

    return _validate_navigation_receipt_stage(
        manifest,
        route,
        receipt,
        post_j600=False,
        repo_root=repo_root,
        verify_current_outputs=verify_current_outputs,
    )


def validate_post_j600_navigation_receipt(
    manifest: dict[str, Any],
    route: dict[str, object],
    receipt: dict[str, object],
    *,
    j600_receipt_digest: str,
    repo_root: Path = REPO_ROOT,
) -> list[str]:
    """Validate the distinct signed-decision navigation receipt after J-600."""

    return _validate_navigation_receipt_stage(
        manifest,
        route,
        receipt,
        post_j600=True,
        j600_receipt_digest=j600_receipt_digest,
        repo_root=repo_root,
    )


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


def validate_checker_record(
    record: dict[str, object], receipt: dict[str, object]
) -> list[str]:
    """Validate an independently produced record against one producer attempt."""

    errors: list[str] = []
    if set(record) != CHECKER_RECORD_FIELDS:
        errors.append(
            f"checker record fields must equal {sorted(CHECKER_RECORD_FIELDS)}"
        )
        return errors
    if record.get("schema_version") != CHECKER_RECORD_SCHEMA_VERSION:
        errors.append("checker record schema_version is invalid")
    for field in ("campaign_id", "campaign_revision", "job_id", "attempt_id"):
        if record.get(field) != receipt.get(field):
            errors.append(f"checker record {field} does not match receipt")
    if record.get("producer_attempt_digest") != receipt.get(
        "producer_attempt_digest"
    ):
        errors.append("checker record producer_attempt_digest does not match receipt")
    if record.get("producer_identity") != receipt.get("producer_identity"):
        errors.append("checker record producer_identity does not match receipt")
    for field in (
        "checker_role",
        "checker_identity",
        "independence_basis",
    ):
        if record.get(field) != receipt.get(field):
            errors.append(f"checker record {field} does not match receipt")
    if record.get("checker_identity") == record.get("producer_identity"):
        errors.append("checker record cannot be self-checked")
    if record.get("disposition") not in CHECKER_DISPOSITIONS:
        errors.append("checker record disposition must be pass or challenge")
    if record.get("disposition") != "pass":
        errors.append("checker record disposition is not pass")
    checked = _timestamp(record.get("checked_at"))
    completed = _timestamp(receipt.get("completed_at"))
    if checked is None or completed is None or checked < completed:
        errors.append("checker record checked_at must be at or after producer completion")
    if not _string_list(record.get("limitations")):
        errors.append("checker record limitations must be a concrete string list")
    expected_digest = checker_record_digest(record)
    if record.get("record_digest") != expected_digest:
        errors.append("checker record canonical digest does not match")
    return errors


def validate_receipt(
    row: dict[str, object],
    manifest: dict[str, Any],
    expected_job_id: str | None = None,
    *,
    repo_root: Path = REPO_ROOT,
    verify_files: bool = True,
    verify_dependency_receipts: bool = True,
    checker_record: dict[str, object] | None = None,
    verify_terminal_route: bool = True,
) -> list[str]:
    """Return fail-closed receipt-contract errors without judging evidence truth."""

    errors: list[str] = []
    missing = sorted(REQUIRED_FIELDS - set(row))
    if missing:
        errors.append(f"missing required fields: {missing}")
        return errors
    unexpected = sorted(set(row) - REQUIRED_FIELDS)
    if unexpected:
        errors.append(f"unexpected receipt fields: {unexpected}")
        return errors

    if row["schema_version"] != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if row["campaign_id"] != manifest.get("campaign_id"):
        errors.append("campaign_id does not match manifest")
    if row["campaign_revision"] != manifest.get("revision"):
        errors.append("campaign_revision does not match manifest")
    if not _digest(row["source_revision"]):
        errors.append("source_revision must be sha256:<64 lowercase hex>")
    if row["producer_attempt_digest"] != producer_attempt_digest(row):
        errors.append("producer_attempt_digest does not match canonical producer material")
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
    if not job.get("is_atomic_child") and row["idempotency_key"] != job.get(
        "idempotency_key"
    ):
        errors.append("idempotency_key does not match manifest job/child slot")
    if row["checkpoint_path"] != job.get("checkpoint"):
        errors.append("checkpoint_path does not match manifest job/child slot")
    if row["receipt_path"] != job.get("receipt"):
        errors.append("receipt_path does not match manifest job/child slot")
    if row["lease_minutes"] != job.get("lease_minutes"):
        errors.append("lease_minutes does not match manifest job/child slot")
    if row["heartbeat_minutes"] != job.get("heartbeat_minutes"):
        errors.append("heartbeat_minutes does not match manifest job/child slot")
    binding_provenance: dict[str, object] = {}
    if job.get("is_atomic_child"):
        if not _digest(row["case_binding"]):
            errors.append("atomic child case_binding must be a SHA-256 digest")
        if not _digest(row["case_binding_table_digest"]):
            errors.append("atomic child case_binding_table_digest must be a SHA-256 digest")
        if row["case_envelope_path"] != job.get("case_envelope"):
            errors.append("atomic child case_envelope_path does not match its unique slot")
        if (
            isinstance(row["output_digests"], dict)
            and row["output_digests"]
            and set(row["output_digests"]) != {job.get("case_envelope")}
        ):
            errors.append("atomic child output_digests must contain only its case envelope")
        if verify_files:
            table, table_errors = resolve_case_binding_table(repo_root, manifest)
            errors.extend(table_errors)
            binding_provenance, provenance_errors = resolve_case_binding_provenance(
                repo_root, manifest
            )
            errors.extend(provenance_errors)
            matches = [
                binding
                for binding in table.get("bindings", [])
                if isinstance(binding, dict) and binding.get("job_id") == job_id
            ]
            if len(matches) != 1:
                errors.append("atomic child has no unique accepted binding-table row")
            elif (
                matches[0].get("case_digest") != row["case_binding"]
                or table.get("binding_table_digest")
                != row["case_binding_table_digest"]
                or matches[0].get("idempotency_key") != row["idempotency_key"]
                or matches[0].get("envelope_path") != row["case_envelope_path"]
            ):
                errors.append("atomic child receipt does not match binding-table material")
            binding_table_path = str(job.get("binding_table", ""))
            atomic_inputs = row["input_digests"]
            if binding_provenance and (
                not isinstance(atomic_inputs, dict)
                or atomic_inputs.get(binding_table_path)
                != binding_provenance.get("binding_table_file_digest")
            ):
                errors.append(
                    "atomic child input does not bind accepted J-500 table file bytes"
                )
    elif (
        row["case_binding"] is not None
        or row["case_binding_table_digest"] is not None
        or row["case_envelope_path"] is not None
    ):
        errors.append("top-level job receipts must not claim an atomic case binding")

    parent_is_cohort = job_id in {"J-510", "J-520", "J-530"}
    if parent_is_cohort:
        if not _digest(row["cohort_closure_digest"]):
            errors.append("cohort parent receipt requires cohort_closure_digest")
        if verify_files:
            closure, closure_errors = resolve_cohort_closure(
                repo_root, manifest, str(job_id)
            )
            errors.extend(closure_errors)
            if closure and closure.get("closure_digest") != row["cohort_closure_digest"]:
                errors.append("cohort parent receipt closure digest does not match artifact")
    elif job_id == "J-600":
        if not _digest(row["cohort_closure_digest"]):
            errors.append("J-600 receipt requires selected cohort_closure_digest")
    elif row["cohort_closure_digest"] is not None:
        errors.append("non-cohort receipt must not claim cohort_closure_digest")

    if job_id == "J-600":
        errors.extend(validate_terminal_route(row["terminal_route"]))
        if not _digest(row["navigation_receipt_digest"]):
            errors.append("J-600 receipt requires navigation_receipt_digest")
        if isinstance(row["terminal_route"], dict):
            route = row["terminal_route"]
            if route.get("closure_digest") != row.get("cohort_closure_digest"):
                errors.append("J-600 route and receipt closure digests differ")
            if route.get("navigation_receipt_digest") != row.get(
                "navigation_receipt_digest"
            ):
                errors.append("J-600 route and receipt navigation digests differ")
            if set(row["dependency_receipt_digests"]) != {
                route.get("predecessor_job_id")
            }:
                errors.append("J-600 receipt must bind only the selected predecessor")
            if (
                verify_files
                and verify_terminal_route
                and isinstance(route.get("dependency_route_id"), str)
            ):
                resolved_route, resolved_dependencies, route_errors = (
                    resolve_terminal_route(
                        repo_root,
                        manifest,
                        dependency_route_id=str(route["dependency_route_id"]),
                    )
                )
                errors.extend(route_errors)
                if resolved_route and resolved_route != route:
                    errors.append("J-600 terminal_route does not match live durable evidence")
                expected_dependency_digests = {
                    key: value.get("receipt_digest")
                    for key, value in resolved_dependencies.items()
                }
                if (
                    resolved_dependencies
                    and row["dependency_receipt_digests"]
                    != expected_dependency_digests
                ):
                    errors.append(
                        "J-600 dependency receipt digest does not match selected route"
                    )
    elif row["terminal_route"] is not None or row["navigation_receipt_digest"] is not None:
        errors.append("ordinary receipt must omit terminal navigation material")

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
    manifest_input_digests = job.get("input_digests", {})
    if row["result"] == "pass" and isinstance(manifest_input_digests, dict):
        stale_inputs = sorted(
            relative
            for relative, expected in manifest_input_digests.items()
            if not str(expected).startswith(RECEIPT_BOUND_DIGEST)
            and row["input_digests"].get(relative) != expected
        )
        if stale_inputs:
            errors.append("pass input_digests must equal the current manifest revision")
    expected_dependency_ids = (
        {str(row["terminal_route"].get("predecessor_job_id", ""))}
        if job_id == "J-600" and isinstance(row["terminal_route"], dict)
        else set(job.get("depends_on", []))
    )
    _validate_digest_map(
        "dependency_receipt_digests",
        row["dependency_receipt_digests"],
        expected_dependency_ids,
        errors,
    )
    if verify_files and verify_dependency_receipts and job_id != "J-600":
        resolved_dependencies, dependency_errors = resolve_dependency_receipts(
            repo_root,
            manifest,
            job_id,
            expected_digests=row["dependency_receipt_digests"],
        )
        errors.extend(dependency_errors)
        if not dependency_errors and isinstance(manifest_input_digests, dict):
            if any(
                str(expected).startswith(RECEIPT_BOUND_DIGEST)
                for expected in manifest_input_digests.values()
            ) and not binding_provenance:
                binding_provenance, provenance_errors = (
                    resolve_case_binding_provenance(repo_root, manifest)
                )
                errors.extend(provenance_errors)
            for relative, expected in manifest_input_digests.items():
                if not str(expected).startswith(RECEIPT_BOUND_DIGEST):
                    continue
                if relative == binding_provenance.get("binding_table_path"):
                    expected_digest = binding_provenance.get(
                        "binding_table_file_digest"
                    )
                    if row["input_digests"].get(relative) != expected_digest:
                        errors.append(
                            "receipt-bound case table input does not match accepted "
                            f"J-500 provenance: {relative}"
                        )
                    continue
                projected = {
                    dependency["output_digests"].get(relative)
                    for dependency in resolved_dependencies.values()
                    if isinstance(dependency.get("output_digests"), dict)
                    and _digest(dependency["output_digests"].get(relative))
                }
                if len(projected) != 1:
                    errors.append(
                        "receipt-bound input must resolve to exactly one direct "
                        f"dependency digest: {relative}"
                    )
                elif row["input_digests"].get(relative) != next(iter(projected)):
                    errors.append(
                        "receipt-bound input digest does not match direct dependency "
                        f"projection: {relative}"
                    )

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

    checker_path = row["checker_record_path"]
    if (
        not _text(checker_path)
        or not str(checker_path).startswith(
            "docs/campaigns/dad-high-value-recovery/checks/evidence/"
        )
        or not str(checker_path).endswith(".json")
    ):
        errors.append("checker_record_path must be a concrete campaign evidence JSON path")
    if not _digest(row["checker_record_digest"]):
        errors.append("checker_record_digest must be a SHA-256 digest")
    if checker_path in {
        row["receipt_path"],
        row["checkpoint_path"],
        *(
            row["evidence_paths"]
            if isinstance(row["evidence_paths"], list)
            else []
        ),
        *(
            row["output_digests"].keys()
            if isinstance(row["output_digests"], dict)
            else []
        ),
    }:
        errors.append("checker record path is circular with producer-controlled material")
    supplied_checker = checker_record
    if verify_files and _text(checker_path):
        try:
            file_checker, checker_file_digest = _read_repo_json(
                repo_root, str(checker_path)
            )
            if supplied_checker is not None and supplied_checker != file_checker:
                errors.append("supplied checker record differs from durable checker file")
            supplied_checker = file_checker
            if row["checker_record_digest"] != checker_file_digest:
                errors.append(
                    "receipt checker_record_digest does not match checker file bytes"
                )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"checker record is unavailable: {exc}")
    if supplied_checker is not None:
        errors.extend(validate_checker_record(supplied_checker, row))

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
    elif checker_path in affected_paths:
        errors.append("producer affected_paths must not include checker_record_path")

    if row["coverage"] not in COVERAGE:
        errors.append(f"coverage must be one of {sorted(COVERAGE)}")
    if row["result"] == "pass" and row["coverage"] != "complete":
        errors.append("pass requires complete coverage")
    if row["result"] == "pass" and row["state"] != "complete":
        errors.append("pass requires complete state")
    if row["result"] == "fail_terminal" and (
        row["state"] != "failed" or row["coverage"] != "complete"
    ):
        errors.append("fail_terminal requires failed state and complete coverage")
    if row["result"] in {"inconclusive", "blocked_human"} and (
        row["state"] not in {"blocked", "resumable"}
        or row["coverage"] not in {"partial", "coverage_unavailable"}
    ):
        errors.append(
            "inconclusive or blocked_human requires blocked/resumable state and incomplete coverage"
        )
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


def validate_receipt_history(
    repo_root: Path,
    manifest: dict[str, Any],
    job_id: str | None,
    rows: list[dict[str, object]],
) -> list[str]:
    """Validate an append-only log without rebinding old attempts to current outputs."""

    errors: list[str] = []
    seen_attempts: set[object] = set()
    seen_checker_paths: set[object] = set()
    for number, row in enumerate(rows, start=1):
        attempt_id = row.get("attempt_id")
        checker_path = row.get("checker_record_path")
        attempt_key = attempt_id if isinstance(attempt_id, str) else repr(attempt_id)
        checker_key = checker_path if isinstance(checker_path, str) else repr(checker_path)
        if attempt_key in seen_attempts:
            errors.append(f"line {number}: duplicate attempt_id in receipt log")
        seen_attempts.add(attempt_key)
        if checker_key in seen_checker_paths:
            errors.append(f"line {number}: checker_record_path must be unique per attempt")
        seen_checker_paths.add(checker_key)

        is_latest = number == len(rows)
        checker_record: dict[str, object] | None = None
        if not is_latest and isinstance(checker_path, str):
            try:
                checker_record, checker_file_digest = _read_repo_json(
                    repo_root, checker_path
                )
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(
                    f"line {number}: historical checker record is unavailable: {exc}"
                )
            else:
                if row.get("checker_record_digest") != checker_file_digest:
                    errors.append(
                        "line "
                        f"{number}: receipt checker_record_digest does not match "
                        "historical checker file bytes"
                    )
        row_errors = validate_receipt(
            row,
            manifest,
            job_id,
            repo_root=repo_root,
            verify_files=is_latest,
            verify_dependency_receipts=is_latest,
            checker_record=checker_record,
        )
        errors.extend(f"line {number}: {error}" for error in row_errors)
    return errors


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
        try:
            checker_record, _checker_file_digest = _read_repo_json(
                repo_root, str(latest.get("checker_record_path", ""))
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"dependency {dependency}: checker record unavailable: {exc}")
            continue
        if checker_record.get("disposition") != "pass":
            errors.append(f"dependency checker disposition is not pass: {dependency}")
            continue
        resolved[dependency] = {
            "receipt_digest": receipt_digest,
            "result": latest.get("result"),
            "state": latest.get("state"),
            "coverage": latest.get("coverage"),
            "checker_disposition": checker_record.get("disposition"),
            "checker_record_digest": latest.get("checker_record_digest"),
            "closure_digest": latest.get("cohort_closure_digest"),
            "output_digests": dict(latest.get("output_digests", {})),
            "verifier_status": "pass",
        }
    return resolved, errors


def _resolve_accepted_j600_receipt(
    repo_root: Path, manifest: dict[str, Any]
) -> tuple[dict[str, object], str, list[str]]:
    """Resolve the durable signed J-600 receipt without recursing into routing."""

    job = _manifest_jobs(manifest).get("J-600")
    if job is None:
        return {}, "", ["post-J600 navigation requires manifest job J-600"]
    relative = str(job.get("receipt", ""))
    try:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or "\\" in relative:
            raise ValueError(f"unsafe J-600 receipt path: {relative}")
        resolved = (repo_root / path).resolve(strict=True)
        root = repo_root.resolve(strict=True)
        if root not in resolved.parents or not resolved.is_file():
            raise ValueError("J-600 receipt escaped repository or is not a file")
        rows, receipt_digest = _read_jsonl(resolved)
    except (OSError, ValueError) as exc:
        return {}, "", [f"post-J600 signed receipt is unavailable: {exc}"]
    latest = rows[-1]
    errors = validate_receipt(
        latest,
        manifest,
        "J-600",
        repo_root=repo_root,
        verify_files=True,
        verify_dependency_receipts=False,
        verify_terminal_route=False,
    )
    if (
        latest.get("result"),
        latest.get("state"),
        latest.get("coverage"),
    ) != ("pass", "complete", "complete"):
        errors.append("post-J600 navigation requires an accepted PASS J-600 receipt")
    return (
        (latest if not errors else {}),
        receipt_digest,
        [f"J-600: {error}" for error in errors],
    )


def resolve_terminal_route(
    repo_root: Path,
    manifest: dict[str, Any],
    *,
    dependency_route_id: str | None = None,
) -> tuple[dict[str, object], dict[str, dict[str, object]], list[str]]:
    """Resolve exactly one checker-accepted terminal predecessor for J-600."""

    jobs = _manifest_jobs(manifest)
    candidates: list[tuple[dict[str, object], dict[str, object]]] = []
    errors: list[str] = []
    terminal_outcome_seen = False
    for predecessor in ("J-510", "J-520", "J-530"):
        job = jobs.get(predecessor)
        if job is None:
            errors.append(f"terminal predecessor is missing from manifest: {predecessor}")
            continue
        relative = str(job.get("receipt", ""))
        path = repo_root / relative
        if terminal_outcome_seen:
            if path.exists():
                errors.append(
                    "post-terminal predecessor receipt residue is forbidden: "
                    f"{predecessor}"
                )
            continue
        if not path.exists():
            errors.append(
                "terminal route prerequisite receipt is missing before selection: "
                f"{predecessor}"
            )
            continue
        try:
            rows, receipt_digest = _read_jsonl(path)
        except (OSError, ValueError) as exc:
            errors.append(f"terminal predecessor {predecessor}: {exc}")
            continue
        latest = rows[-1]
        contract_errors = validate_receipt(
            latest,
            manifest,
            predecessor,
            repo_root=repo_root,
            verify_files=True,
            verify_dependency_receipts=False,
        )
        if contract_errors:
            errors.extend(
                f"terminal predecessor {predecessor}: {error}"
                for error in contract_errors
            )
            continue
        closure, closure_errors = resolve_cohort_closure(
            repo_root, manifest, predecessor
        )
        if closure_errors:
            errors.extend(
                f"terminal predecessor {predecessor}: {error}"
                for error in closure_errors
            )
            continue
        result = str(latest.get("result", ""))
        state = str(latest.get("state", ""))
        coverage = str(latest.get("coverage", ""))
        stage = {"J-510": "p5a", "J-520": "p5b", "J-530": "p5c"}[
            predecessor
        ]
        trigger_class = str(
            closure.get("trigger_class", closure.get("stop_trigger", ""))
        )
        if (
            result in {"inconclusive", "blocked_human"}
            and state == "blocked"
            and coverage in {"partial", "coverage_unavailable"}
        ):
            route_id = f"{stage}-inconclusive"
        elif predecessor == "J-530" and (result, state, coverage) == (
            "pass",
            "complete",
            "complete",
        ):
            route_id = "p5c-pass"
        elif (result, state, coverage) == (
            "fail_terminal",
            "failed",
            "complete",
        ):
            route_id = f"{stage}-valid-terminal"
        elif predecessor in {"J-510", "J-520"} and (
            result,
            state,
            coverage,
        ) == ("pass", "complete", "complete"):
            continue
        else:
            errors.append(
                "terminal predecessor outcome does not select or advance a route: "
                f"{predecessor}"
            )
            continue
        terminal_outcome_seen = True
        permitted = TERMINAL_ROUTE_SPECS[route_id][2]
        route = {
            "dependency_route_id": route_id,
            "predecessor_job_id": predecessor,
            "predecessor_receipt_digest": receipt_digest,
            "predecessor_result": result,
            "predecessor_state": state,
            "predecessor_coverage": coverage,
            "trigger_class": trigger_class,
            "closure_digest": closure.get("closure_digest"),
            "closure_complete": True,
            "permitted_decisions": permitted,
        }
        navigation = manifest.get("terminal_navigation", {})
        receipt_template = (
            str(navigation.get("receipt_path_template", ""))
            if isinstance(navigation, dict)
            else ""
        )
        expected_template = (
            "docs/campaigns/dad-high-value-recovery/checks/evidence/"
            "navigation/{route_id}.json"
        )
        if receipt_template != expected_template:
            errors.append("terminal navigation receipt_path_template is invalid")
            continue
        navigation_relative = receipt_template.replace("{route_id}", route_id)
        post_template = (
            str(navigation.get("post_j600_receipt_path_template", ""))
            if isinstance(navigation, dict)
            else ""
        )
        if post_template != NAVIGATION_POST_RECEIPT_TEMPLATE:
            errors.append("terminal navigation post-J600 receipt template is invalid")
            continue
        post_relative = post_template.replace("{route_id}", route_id)
        post_path = repo_root / post_relative
        j600_receipt: dict[str, object] = {}
        j600_receipt_digest = ""
        if post_path.exists():
            (
                j600_receipt,
                j600_receipt_digest,
                j600_errors,
            ) = _resolve_accepted_j600_receipt(repo_root, manifest)
            errors.extend(j600_errors)
        try:
            navigation_receipt, navigation_file_digest = _read_repo_json(
                repo_root, navigation_relative
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(
                f"terminal navigation receipt {route_id} is unavailable: {exc}"
            )
            continue
        navigation_errors = validate_navigation_receipt(
            manifest,
            route,
            navigation_receipt,
            repo_root=repo_root,
            verify_current_outputs=not bool(j600_receipt),
        )
        if navigation_errors:
            errors.extend(
                f"terminal navigation receipt {route_id}: {error}"
                for error in navigation_errors
            )
            continue
        route["navigation_receipt_digest"] = navigation_file_digest
        if post_path.exists():
            if not j600_receipt:
                continue
            if j600_receipt.get("terminal_route") != route:
                errors.append("J-600 receipt terminal route does not match pre-navigation")
                continue
            if j600_receipt.get("navigation_receipt_digest") != navigation_file_digest:
                errors.append("J-600 receipt does not bind the immutable pre-navigation receipt")
                continue
            try:
                post_receipt, _post_file_digest = _read_repo_json(
                    repo_root, post_relative
                )
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(
                    f"post-J600 navigation receipt {route_id} is unavailable: {exc}"
                )
                continue
            post_errors = validate_post_j600_navigation_receipt(
                manifest,
                route,
                post_receipt,
                j600_receipt_digest=j600_receipt_digest,
                repo_root=repo_root,
            )
            if post_errors:
                errors.extend(
                    f"post-J600 navigation receipt {route_id}: {error}"
                    for error in post_errors
                )
                continue
        route_errors = validate_terminal_route(route)
        if route_errors:
            errors.extend(
                f"terminal predecessor {predecessor}: {error}"
                for error in route_errors
            )
            continue
        candidates.append((route, latest))

    if len(candidates) != 1:
        errors.append(
            f"terminal route selection requires exactly one candidate; found {len(candidates)}"
        )
        return {}, {}, sorted(set(errors))
    if errors:
        return {}, {}, sorted(set(errors))
    route, receipt = candidates[0]
    if (
        dependency_route_id is not None
        and route.get("dependency_route_id") != dependency_route_id
    ):
        errors.append(
            "requested dependency_route_id does not match the sole terminal candidate"
        )
        return {}, {}, sorted(set(errors))
    predecessor = str(route["predecessor_job_id"])
    dependency = {
        predecessor: {
            "receipt_digest": route["predecessor_receipt_digest"],
            "result": receipt.get("result"),
            "state": receipt.get("state"),
            "coverage": receipt.get("coverage"),
            "checker_disposition": "pass",
            "checker_record_digest": receipt.get("checker_record_digest"),
            "closure_digest": receipt.get("cohort_closure_digest"),
            "output_digests": dict(receipt.get("output_digests", {})),
            "verifier_status": "pass",
        }
    }
    return route, dependency, sorted(set(errors))


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
        history_errors = validate_receipt_history(
            repo_root, manifest, job_id, rows
        )
        if history_errors:
            errors.extend(
                f"budget receipt {job_id} {error}" for error in history_errors
            )
            continue
        for index, row in enumerate(rows, start=1):
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
        contract_errors = validate_receipt_history(
            REPO_ROOT, manifest, args.job_id, rows
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
