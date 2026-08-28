from __future__ import annotations

import importlib.util
import hashlib
import json
import sys
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "receipt_checker", HERE / "verify_receipt_durability.py"
)
CHECKER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CHECKER)
MANIFEST = json.loads((HERE.parent / "campaign.json").read_text(encoding="utf-8"))


def _job(job_id: str) -> dict:
    return CHECKER._manifest_jobs(MANIFEST)[job_id]


def _valid_receipt(job_id: str = "J-100") -> dict:
    job = _job(job_id)
    gate = job["acceptance"][0]
    evidence = gate["evidence"]
    receipt = {
        "schema_version": CHECKER.SCHEMA_VERSION,
        "campaign_id": MANIFEST["campaign_id"],
        "campaign_revision": MANIFEST["revision"],
        "job_id": job_id,
        "idempotency_key": job["idempotency_key"],
        "checkpoint_path": job["checkpoint"],
        "receipt_path": job["receipt"],
        "attempt_id": f"{job_id}:attempt:1",
        "gate_id": gate["id"],
        "gate_revision": gate["revision"],
        "result": "pass",
        "source_revision": "sha256:" + "1" * 64,
        "input_digests": dict(job["input_digests"]),
        "dependency_receipt_digests": {
            dep: "sha256:" + "2" * 64 for dep in job["depends_on"]
        },
        "producer_role": job["owner_role"],
        "producer_identity": "writer-1",
        "checker_role": gate["checker_role"],
        "checker_identity": "checker-1",
        "independence_basis": "different runtime task and no writer authority",
        "adapter": {"name": "codex-local", "revision": "adapter-r1"},
        "worker_capability": {
            "profile_id": "bounded-writer-r1",
            "qualification_evidence": ["checks/evidence/launch/qualification.json"],
        },
        "lease": {
            "lease_id": f"lease-{job_id}-1",
            "issued_at": "2026-08-20T10:00:00+00:00",
            "expires_at": "2026-08-20T11:00:00+00:00",
            "released_at": "2026-08-20T10:30:00+00:00",
            "state": "released",
        },
        "lease_minutes": job["lease_minutes"],
        "heartbeat_minutes": job["heartbeat_minutes"],
        "command_or_query": "recorded deterministic command summary",
        "started_at": "2026-08-20T10:00:00+00:00",
        "completed_at": "2026-08-20T10:30:00+00:00",
        "exit_code": 0,
        "evidence_paths": [evidence, job["checkpoint"]],
        "evidence_digests": {
            evidence: "sha256:" + "3" * 64,
            job["checkpoint"]: "sha256:" + "4" * 64,
        },
        "output_digests": {
            output: "sha256:" + "5" * 64 for output in job["outputs"]
        },
        "affected_paths": [],
        "coverage": "complete",
        "privacy_class": "internal_metadata",
        "synthetic_or_fixture": False,
        "measured_budgets": {
            "wall_seconds": 1800,
            "cost_units": 1,
            "context_tokens": 1000,
            "output_bytes": 100,
            "attempt_number": 1,
        },
        "state": "complete",
        "next_action": "await controller dependency release",
        "limitations": [],
        "revalidation_triggers": list(gate["revalidation_triggers"]),
        "case_binding": None,
        "case_binding_table_digest": None,
        "case_envelope_path": None,
        "cohort_closure_digest": (
            "sha256:" + "6" * 64
            if job_id in {"J-510", "J-520", "J-530", "J-600"}
            else None
        ),
        "terminal_route": None,
        "navigation_receipt_digest": None,
        "producer_attempt_digest": "",
        "checker_record_path": (
            "docs/campaigns/dad-high-value-recovery/checks/evidence/pilot/"
            f"{job_id}-attempt-1-checker.json"
        ),
        "checker_record_digest": "sha256:" + "7" * 64,
        "authority_boundary": (
            "This receipt does not authorize external, destructive, publication, "
            "merge, deployment, or downstream effects."
        ),
    }
    if job.get("is_atomic_child"):
        receipt["case_envelope_path"] = job["case_envelope"]
    if job_id == "J-600":
        receipt["dependency_receipt_digests"] = {"J-530": "sha256:" + "2" * 64}
        receipt["terminal_route"] = {
            "dependency_route_id": "p5c-pass",
            "predecessor_job_id": "J-530",
            "predecessor_receipt_digest": "sha256:" + "2" * 64,
            "predecessor_result": "pass",
            "predecessor_state": "complete",
            "predecessor_coverage": "complete",
            "trigger_class": "value-gate-pass",
            "closure_digest": receipt["cohort_closure_digest"],
            "closure_complete": True,
            "navigation_receipt_digest": "sha256:" + "8" * 64,
            "permitted_decisions": ["scale", "narrow", "retire", "re-audit"],
        }
        receipt["navigation_receipt_digest"] = "sha256:" + "8" * 64
    receipt["producer_attempt_digest"] = CHECKER.producer_attempt_digest(receipt)
    return receipt


def _checker_record(receipt: dict, *, disposition: str = "pass") -> dict:
    record = {
        "schema_version": CHECKER.CHECKER_RECORD_SCHEMA_VERSION,
        "campaign_id": receipt["campaign_id"],
        "campaign_revision": receipt["campaign_revision"],
        "job_id": receipt["job_id"],
        "attempt_id": receipt["attempt_id"],
        "producer_attempt_digest": receipt["producer_attempt_digest"],
        "producer_identity": receipt["producer_identity"],
        "checker_role": receipt["checker_role"],
        "checker_identity": receipt["checker_identity"],
        "independence_basis": receipt["independence_basis"],
        "disposition": disposition,
        "checked_at": "2026-08-20T10:31:00+00:00",
        "limitations": [],
        "record_digest": "",
    }
    record["record_digest"] = CHECKER.checker_record_digest(record)
    return record


def _contract_errors(receipt: dict, job_id: str | None = None) -> list[str]:
    receipt["producer_attempt_digest"] = CHECKER.producer_attempt_digest(receipt)
    record = _checker_record(receipt)
    return CHECKER.validate_receipt(
        receipt,
        MANIFEST,
        job_id or str(receipt["job_id"]),
        verify_files=False,
        checker_record=record,
    )


def _write_checker_record(repo_root: Path, receipt: dict) -> None:
    receipt["producer_attempt_digest"] = CHECKER.producer_attempt_digest(receipt)
    record = _checker_record(receipt)
    path = repo_root / receipt["checker_record_path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(record, sort_keys=True).encode("utf-8")
    path.write_bytes(payload)
    receipt["checker_record_digest"] = (
        "sha256:" + hashlib.sha256(payload).hexdigest()
    )


def test_valid_receipt_passes_contract() -> None:
    assert _contract_errors(_valid_receipt(), "J-100") == []


def test_campaign_budget_aggregation_reads_validated_durable_rows(
    tmp_path: Path,
) -> None:
    receipt = _valid_receipt()
    receipt["evidence_digests"] = {}
    for relative_evidence in receipt["evidence_paths"]:
        evidence_path = tmp_path / relative_evidence
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_bytes(f"evidence:{relative_evidence}".encode())
        receipt["evidence_digests"][relative_evidence] = (
            "sha256:" + hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        )
    receipt["output_digests"] = {}
    for relative_output in _job("J-100")["outputs"]:
        output_path = tmp_path / relative_output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(f"output:{relative_output}".encode())
        receipt["output_digests"][relative_output] = (
            "sha256:" + hashlib.sha256(output_path.read_bytes()).hexdigest()
        )
    _write_checker_record(tmp_path, receipt)
    relative = Path(_job("J-100")["receipt"])
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, sort_keys=True) + "\n"
    path.write_text(payload, encoding="utf-8")
    observed_digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    attempts, digests, errors = CHECKER.resolve_campaign_budget_receipts(
        tmp_path, MANIFEST
    )
    assert errors == []
    assert attempts == [
        {
            "job_id": "J-100",
            "attempt_id": "J-100:attempt:1",
            "attempt_count": 1,
            "cost_units": 1,
            "wall_seconds": 1800,
            "context_tokens": 1000,
            "output_mb": 100 / (1024 * 1024),
            "budget_evidence_complete": True,
            "receipt_path": relative.as_posix(),
            "receipt_digest": observed_digest,
        }
    ]
    assert digests == {
        relative.as_posix(): observed_digest
    }


def test_receipt_log_duplicate_json_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.jsonl"
    path.write_bytes(b'{"job_id":"J-100","job_id":"J-110"}\n')
    try:
        CHECKER._read_jsonl(path)
    except ValueError as exc:
        assert "duplicate JSON object key" in str(exc)
    else:
        raise AssertionError("ambiguous duplicate-key receipt was accepted")


def test_minimal_prose_receipt_fails_closed() -> None:
    errors = CHECKER.validate_receipt(
        {"job_id": "J-100"}, MANIFEST, "J-100", verify_files=False
    )
    assert any("missing required fields" in error for error in errors)


def test_stale_pass_input_digest_fails() -> None:
    receipt = _valid_receipt()
    first = next(iter(receipt["input_digests"]))
    receipt["input_digests"][first] = "sha256:" + "f" * 64
    errors = _contract_errors(receipt, "J-100")
    assert "pass input_digests must equal the current manifest revision" in errors


def test_same_producer_and_checker_fails() -> None:
    receipt = _valid_receipt()
    receipt["checker_identity"] = receipt["producer_identity"]
    errors = _contract_errors(receipt, "J-100")
    assert "producer_identity and checker_identity must differ" in errors


def test_producer_attempt_digest_detects_postcheck_material_tampering() -> None:
    receipt = _valid_receipt()
    record = _checker_record(receipt)
    assert CHECKER.validate_receipt(
        receipt,
        MANIFEST,
        "J-100",
        verify_files=False,
        checker_record=record,
    ) == []

    receipt["limitations"].append("added after checker bound the attempt")
    errors = CHECKER.validate_receipt(
        receipt,
        MANIFEST,
        "J-100",
        verify_files=False,
        checker_record=record,
    )
    assert "producer_attempt_digest does not match canonical producer material" in errors


def test_checker_challenge_stale_self_and_circular_records_fail_closed() -> None:
    receipt = _valid_receipt()
    receipt["producer_attempt_digest"] = CHECKER.producer_attempt_digest(receipt)
    challenged = _checker_record(receipt, disposition="challenge")
    errors = CHECKER.validate_receipt(
        receipt,
        MANIFEST,
        "J-100",
        verify_files=False,
        checker_record=challenged,
    )
    assert "checker record disposition is not pass" in errors

    receipt = _valid_receipt()
    stale = _checker_record(receipt)
    stale["producer_attempt_digest"] = "sha256:" + "f" * 64
    stale["record_digest"] = CHECKER.checker_record_digest(stale)
    errors = CHECKER.validate_receipt(
        receipt,
        MANIFEST,
        "J-100",
        verify_files=False,
        checker_record=stale,
    )
    assert "checker record producer_attempt_digest does not match receipt" in errors

    receipt = _valid_receipt()
    receipt["checker_identity"] = receipt["producer_identity"]
    receipt["producer_attempt_digest"] = CHECKER.producer_attempt_digest(receipt)
    self_checked = _checker_record(receipt)
    errors = CHECKER.validate_receipt(
        receipt,
        MANIFEST,
        "J-100",
        verify_files=False,
        checker_record=self_checked,
    )
    assert "checker record cannot be self-checked" in errors

    receipt = _valid_receipt()
    receipt["checker_record_path"] = receipt["receipt_path"]
    errors = _contract_errors(receipt, "J-100")
    assert "checker record path is circular with producer-controlled material" in errors

    receipt = _valid_receipt()
    receipt["checker_record_path"] = receipt["evidence_paths"][0]
    errors = _contract_errors(receipt, "J-100")
    assert "checker record path is circular with producer-controlled material" in errors


def test_incomplete_coverage_cannot_pass() -> None:
    receipt = _valid_receipt()
    receipt["coverage"] = "partial"
    errors = _contract_errors(receipt, "J-100")
    assert "pass requires complete coverage" in errors


def test_pass_requires_all_outputs_and_checkpoint_evidence() -> None:
    receipt = _valid_receipt()
    receipt["output_digests"].pop(next(iter(receipt["output_digests"])))
    errors = _contract_errors(receipt, "J-100")
    assert "pass output_digests keys must equal declared job outputs" in errors

    receipt = _valid_receipt()
    checkpoint = receipt["checkpoint_path"]
    receipt["evidence_paths"].remove(checkpoint)
    receipt["evidence_digests"].pop(checkpoint)
    errors = _contract_errors(receipt, "J-100")
    assert "evidence_paths must include checkpoint_path" in errors


def test_atomic_child_is_flattened_and_requires_case_binding() -> None:
    jobs = CHECKER._manifest_jobs(MANIFEST)
    assert len([job_id for job_id in jobs if "-C" in job_id]) == 70
    receipt = _valid_receipt("J-510-C01")
    receipt["case_binding"] = "sha256:" + "4" * 64
    receipt["case_binding_table_digest"] = "sha256:" + "5" * 64
    receipt["input_digests"][_job("J-510-C01")["binding_table"]] = (
        receipt["case_binding_table_digest"]
    )
    assert _contract_errors(receipt, "J-510-C01") == []

    receipt["case_binding"] = None
    errors = _contract_errors(receipt, "J-510-C01")
    assert "atomic child case_binding must be a SHA-256 digest" in errors


def test_atomic_receipt_uses_materialized_binding_row_idempotency(
    tmp_path: Path, monkeypatch,
) -> None:
    job_id = "J-510-C01"
    table = _case_binding_table()
    binding = next(row for row in table["bindings"] if row["job_id"] == job_id)
    table_file_digest = "sha256:" + "d" * 64
    receipt = _valid_receipt(job_id)
    receipt["idempotency_key"] = binding["idempotency_key"]
    receipt["case_binding"] = binding["case_digest"]
    receipt["case_binding_table_digest"] = table["binding_table_digest"]
    binding_path = _job(job_id)["binding_table"]
    receipt["input_digests"][binding_path] = table_file_digest
    for digest_field in ("evidence_digests", "output_digests"):
        for relative in receipt[digest_field]:
            path = tmp_path / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"artifact:{relative}".encode())
            receipt[digest_field][relative] = (
                "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            )
    _write_checker_record(tmp_path, receipt)
    provenance = {
        "binding_table_path": binding_path,
        "binding_table_file_digest": table_file_digest,
        "binding_table_digest": table["binding_table_digest"],
    }
    monkeypatch.setattr(CHECKER, "resolve_case_binding_table", lambda *_args: (table, []))
    monkeypatch.setattr(
        CHECKER, "resolve_case_binding_provenance", lambda *_args: (provenance, [])
    )
    assert CHECKER.validate_receipt(
        receipt,
        MANIFEST,
        job_id,
        repo_root=tmp_path,
        verify_files=True,
        verify_dependency_receipts=False,
    ) == []

    for invalid in (
        _job(job_id)["idempotency_key"],
        binding["idempotency_key"].replace(binding["case_digest"], "sha256:" + "e" * 64),
    ):
        receipt["idempotency_key"] = invalid
        receipt["producer_attempt_digest"] = CHECKER.producer_attempt_digest(receipt)
        _write_checker_record(tmp_path, receipt)
        errors = CHECKER.validate_receipt(
            receipt,
            MANIFEST,
            job_id,
            repo_root=tmp_path,
            verify_files=True,
            verify_dependency_receipts=False,
        )
        assert "atomic child receipt does not match binding-table material" in errors


def _case_binding_table() -> dict:
    bindings = []
    for job_id, job in sorted(CHECKER._manifest_jobs(MANIFEST).items()):
        if not job.get("is_atomic_child"):
            continue
        case_digest = "sha256:" + hashlib.sha256(job_id.encode()).hexdigest()
        bindings.append(
            {
                "job_id": job_id,
                "case_id": f"case:{job_id}",
                "case_digest": case_digest,
                "sequence": job["sequence"],
                "depends_on": job["depends_on"],
                "idempotency_key": job["idempotency_key"].replace(
                    "{case_digest}", case_digest
                ),
                "checkpoint_path": job["checkpoint"],
                "receipt_path": job["receipt"],
                "envelope_path": job["case_envelope"],
            }
        )
    table = {
        "schema_version": CHECKER.CASE_BINDING_TABLE_SCHEMA,
        "campaign_id": MANIFEST["campaign_id"],
        "campaign_revision": MANIFEST["revision"],
        "bindings": bindings,
        "binding_table_digest": "",
    }
    table["binding_table_digest"] = CHECKER._digest_without(
        table, "binding_table_digest"
    )
    return table


def test_binding_table_requires_exact_unique_materialized_slot_contract() -> None:
    table = _case_binding_table()
    assert CHECKER.validate_case_binding_table(MANIFEST, table) == []

    table["bindings"][1]["case_digest"] = table["bindings"][0]["case_digest"]
    table["binding_table_digest"] = CHECKER._digest_without(
        table, "binding_table_digest"
    )
    errors = CHECKER.validate_case_binding_table(MANIFEST, table)
    assert "case binding table case digests must be valid and unique" in errors


def test_case_binding_provenance_requires_accepted_j500_and_exact_table_bytes(
    tmp_path: Path,
) -> None:
    receipt = _valid_receipt("J-500")
    binding_path = _job("J-510")["case_execution"]["binding_table"]
    table = _case_binding_table()
    table_bytes = json.dumps(table, sort_keys=True).encode()
    for relative in receipt["evidence_paths"]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"evidence:{relative}".encode())
        receipt["evidence_digests"][relative] = (
            "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        )
    for relative in receipt["output_digests"]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(table_bytes if relative == binding_path else f"output:{relative}".encode())
        receipt["output_digests"][relative] = (
            "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        )
    _write_checker_record(tmp_path, receipt)
    log_path = tmp_path / receipt["receipt_path"]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8")

    provenance, errors = CHECKER.resolve_case_binding_provenance(tmp_path, MANIFEST)
    assert errors == []
    assert set(provenance) == {
        "binding_table_path",
        "binding_table_file_digest",
        "binding_table_digest",
        "j500_receipt_digest",
        "checker_record_digest",
        "checker_disposition",
        "verifier_status",
        "j500_result",
        "j500_state",
        "j500_coverage",
    }
    assert provenance["binding_table_digest"] == table["binding_table_digest"]

    table_path = tmp_path / binding_path
    table_path.write_bytes(b" " + table_bytes)
    _provenance, errors = CHECKER.resolve_case_binding_provenance(tmp_path, MANIFEST)
    assert any("does not bind the current binding-table file bytes" in error for error in errors)

    table_path.write_bytes(table_bytes)
    checker_path = tmp_path / receipt["checker_record_path"]
    checker = json.loads(checker_path.read_text(encoding="utf-8"))
    checker["disposition"] = "challenge"
    checker["record_digest"] = CHECKER.checker_record_digest(checker)
    checker_path.write_text(json.dumps(checker, sort_keys=True), encoding="utf-8")
    _provenance, errors = CHECKER.resolve_case_binding_provenance(tmp_path, MANIFEST)
    assert any("checker record disposition is not pass" in error for error in errors)


def _cohort_closure(parent_job_id: str = "J-510") -> dict:
    children = [
        job_id
        for job_id, job in CHECKER._manifest_jobs(MANIFEST).items()
        if job.get("parent_id") == parent_job_id
    ]
    stop_trigger = "manual-bounded-stop"
    closure = {
        "schema_version": CHECKER.COHORT_CLOSURE_SCHEMA,
        "campaign_id": MANIFEST["campaign_id"],
        "campaign_revision": MANIFEST["revision"],
        "parent_job_id": parent_job_id,
        "started_children": [],
        "unstarted_or_withdrawn_children": [
            {
                "job_id": child,
                "reason_code": "not_started_at_stop",
                "reason_digest": CHECKER.canonical_digest(
                    {"job_id": child, "reason_code": "not_started_at_stop"}
                ),
            }
            for child in children
        ],
        "active_lease_count": 0,
        "unreconciled_effect_count": 0,
        "post_stop_receipt_count": 0,
        "post_stop_lease_count": 0,
        "stop_trigger": stop_trigger,
        "stop_trigger_digest": CHECKER.canonical_digest(stop_trigger),
        "closure_complete": True,
        "closure_digest": "",
    }
    closure["closure_digest"] = CHECKER._digest_without(closure, "closure_digest")
    return closure


def test_cohort_closure_requires_exact_partition_and_zero_runtime_residue() -> None:
    closure = _cohort_closure()
    assert CHECKER.validate_cohort_closure(MANIFEST, "J-510", closure) == []

    closure["active_lease_count"] = 1
    closure["closure_digest"] = CHECKER._digest_without(closure, "closure_digest")
    errors = CHECKER.validate_cohort_closure(MANIFEST, "J-510", closure)
    assert "cohort closure runtime residue is nonzero: active_lease_count" in errors


def test_cohort_closure_requires_ordered_prefix_suffix_and_exact_row_keys() -> None:
    closure = _cohort_closure()
    c02 = next(
        row
        for row in closure["unstarted_or_withdrawn_children"]
        if row["job_id"] == "J-510-C02"
    )
    closure["unstarted_or_withdrawn_children"].remove(c02)
    closure["started_children"] = [
        {
            "job_id": "J-510-C02",
            "receipt_digest": "sha256:" + "1" * 64,
            "checker_record_digest": "sha256:" + "2" * 64,
            "checker_disposition": "pass",
            "durability_verified": True,
        }
    ]
    closure["closure_digest"] = CHECKER._digest_without(closure, "closure_digest")
    errors = CHECKER.validate_cohort_closure(MANIFEST, "J-510", closure)
    assert any("sequence-ordered started prefix" in error for error in errors)

    reordered = _cohort_closure()
    reordered["unstarted_or_withdrawn_children"][:2] = reversed(
        reordered["unstarted_or_withdrawn_children"][:2]
    )
    reordered["closure_digest"] = CHECKER._digest_without(
        reordered, "closure_digest"
    )
    errors = CHECKER.validate_cohort_closure(MANIFEST, "J-510", reordered)
    assert any("sequence-ordered started prefix" in error for error in errors)

    surplus = _cohort_closure()
    surplus["unstarted_or_withdrawn_children"][0]["unexpected"] = True
    surplus["closure_digest"] = CHECKER._digest_without(surplus, "closure_digest")
    errors = CHECKER.validate_cohort_closure(MANIFEST, "J-510", surplus)
    assert any("unstarted child keys are invalid" in error for error in errors)

    missing = _cohort_closure()
    missing["unstarted_or_withdrawn_children"][0].pop("reason_digest")
    missing["closure_digest"] = CHECKER._digest_without(missing, "closure_digest")
    errors = CHECKER.validate_cohort_closure(MANIFEST, "J-510", missing)
    assert any("unstarted child keys are invalid" in error for error in errors)


def test_cohort_closure_resolves_exact_child_log_and_checker_acceptance(
    tmp_path: Path, monkeypatch,
) -> None:
    child_id = "J-510-C01"
    checker_digest = "sha256:" + "c" * 64
    child_receipt = {
        "job_id": child_id,
        "checker_record_digest": checker_digest,
        "result": "pass",
        "state": "complete",
        "coverage": "complete",
    }
    payload = (json.dumps(child_receipt, sort_keys=True) + "\n").encode()
    child_path = tmp_path / _job(child_id)["receipt"]
    child_path.parent.mkdir(parents=True, exist_ok=True)
    child_path.write_bytes(payload)
    receipt_digest = "sha256:" + hashlib.sha256(payload).hexdigest()

    closure = _cohort_closure()
    closure["unstarted_or_withdrawn_children"] = [
        row
        for row in closure["unstarted_or_withdrawn_children"]
        if row["job_id"] != child_id
    ]
    closure["started_children"] = [
        {
            "job_id": child_id,
            "receipt_digest": receipt_digest,
            "checker_record_digest": checker_digest,
            "checker_disposition": "pass",
            "durability_verified": True,
        }
    ]
    closure["closure_digest"] = CHECKER._digest_without(closure, "closure_digest")
    closure_path = tmp_path / _job("J-510")["case_execution"]["closure_path"]
    closure_path.parent.mkdir(parents=True, exist_ok=True)
    closure_path.write_text(json.dumps(closure, sort_keys=True), encoding="utf-8")
    monkeypatch.setattr(CHECKER, "validate_receipt", lambda *_args, **_kwargs: [])
    resolved, errors = CHECKER.resolve_cohort_closure(tmp_path, MANIFEST, "J-510")
    assert errors == []
    assert resolved["started_children"][0]["receipt_digest"] == receipt_digest

    forged = json.loads(json.dumps(closure))
    forged["started_children"][0]["receipt_digest"] = "sha256:" + "f" * 64
    forged["closure_digest"] = CHECKER._digest_without(forged, "closure_digest")
    closure_path.write_text(json.dumps(forged, sort_keys=True), encoding="utf-8")
    _resolved, errors = CHECKER.resolve_cohort_closure(tmp_path, MANIFEST, "J-510")
    assert f"cohort child receipt log digest does not match: {child_id}" in errors

    closure_path.write_text(json.dumps(closure, sort_keys=True), encoding="utf-8")
    child_path.write_bytes(payload + payload)
    _resolved, errors = CHECKER.resolve_cohort_closure(tmp_path, MANIFEST, "J-510")
    assert f"cohort child receipt log digest does not match: {child_id}" in errors

    child_path.write_bytes(payload)
    monkeypatch.setattr(
        CHECKER,
        "validate_receipt",
        lambda *_args, **_kwargs: ["checker record disposition is not pass"],
    )
    _resolved, errors = CHECKER.resolve_cohort_closure(tmp_path, MANIFEST, "J-510")
    assert any("checker record disposition is not pass" in error for error in errors)


def test_terminal_routes_require_exact_trigger_and_outcome_contracts() -> None:
    route = _valid_receipt("J-600")["terminal_route"]
    assert CHECKER.validate_terminal_route(route) == []

    corrupt = {
        **route,
        "dependency_route_id": "p5c-valid-terminal",
        "predecessor_result": "fail_terminal",
        "predecessor_state": "failed",
        "trigger_class": "metric-corruption",
        "permitted_decisions": ["narrow", "retire"],
    }
    errors = CHECKER.validate_terminal_route(corrupt)
    assert "terminal_route trigger_class does not match route_id" in errors

    inconclusive = {
        **route,
        "dependency_route_id": "p5c-inconclusive",
        "predecessor_result": "inconclusive",
        "predecessor_state": "blocked",
        "predecessor_coverage": "coverage_unavailable",
        "trigger_class": "metric-corruption",
        "permitted_decisions": ["re-audit"],
    }
    assert CHECKER.validate_terminal_route(inconclusive) == []
    integrity_override = {
        **inconclusive,
        "predecessor_result": "pass",
        "predecessor_state": "complete",
        "predecessor_coverage": "complete",
    }
    assert (
        "terminal_route inconclusive outcome contract is invalid"
        in CHECKER.validate_terminal_route(integrity_override)
    )

    missing_closure = {**route, "closure_complete": False}
    assert "terminal_route closure_complete must be true" in CHECKER.validate_terminal_route(
        missing_closure
    )


def _navigation_receipt(
    route: dict,
    *,
    post_j600: bool = False,
    j600_receipt_digest: str | None = None,
    repo_root: Path = CHECKER.REPO_ROOT,
) -> dict:
    template = (
        CHECKER.NAVIGATION_POST_RECEIPT_TEMPLATE
        if post_j600
        else CHECKER.NAVIGATION_PRE_RECEIPT_TEMPLATE
    )
    paths = [CHECKER.NAVIGATION_INDEX_PATH, CHECKER.NAVIGATION_HANDOFF_PATH]
    if post_j600:
        paths.append(CHECKER.NAVIGATION_SUPERSESSION_PATH)
    paths.append(template.replace("{route_id}", route["dependency_route_id"]))
    navigation = {
        "schema_version": "dad.campaign.navigation_receipt.v1",
        "campaign_id": MANIFEST["campaign_id"],
        "campaign_revision": MANIFEST["revision"],
        **{
            key: route[key]
            for key in (
                "dependency_route_id",
                "predecessor_job_id",
                "predecessor_receipt_digest",
                "predecessor_result",
                "predecessor_state",
                "predecessor_coverage",
                "trigger_class",
                "closure_digest",
            )
        },
        "projection_digest": CHECKER._navigation_projection_digest(
            MANIFEST,
            route,
            post_j600=post_j600,
            navigation_paths=paths,
            j600_receipt_digest=j600_receipt_digest,
        ),
        "navigation_stage": (
            CHECKER.NAVIGATION_POST_STAGE
            if post_j600
            else CHECKER.NAVIGATION_PRE_STAGE
        ),
        "navigation_paths": paths,
        "output_digests": {
            path: CHECKER._resolved_file_digest(repo_root, path)
            for path in paths[:-1]
        },
        "writer_role": "campaign-navigation-writer",
        "writer_identity": "navigation-writer-1",
        "checker_role": "independent-checker",
        "checker_identity": "navigation-checker-1",
        "checker_disposition": "pass",
        "independence_basis": "different task and no writer authority",
        "checked_at": "2026-08-20T10:31:00+00:00",
    }
    if post_j600:
        navigation["navigation_receipt_digest"] = route["navigation_receipt_digest"]
        navigation["j600_receipt_digest"] = j600_receipt_digest
    return navigation


def test_navigation_receipt_binds_route_and_distinct_checker() -> None:
    route = _valid_receipt("J-600")["terminal_route"]
    navigation = _navigation_receipt(route)
    assert CHECKER.validate_navigation_receipt(MANIFEST, route, navigation) == []
    navigation["checker_identity"] = navigation["writer_identity"]
    assert (
        "navigation writer and checker identities must differ"
        in CHECKER.validate_navigation_receipt(MANIFEST, route, navigation)
    )


def test_navigation_receipts_reject_partial_stale_and_cross_stage_replay() -> None:
    route = _valid_receipt("J-600")["terminal_route"]
    pre = _navigation_receipt(route)
    partial = {**pre, "output_digests": dict(pre["output_digests"])}
    partial["output_digests"].pop(next(iter(partial["output_digests"])))
    assert any(
        "output_digests keys" in error
        for error in CHECKER.validate_navigation_receipt(MANIFEST, route, partial)
    )
    stale = {**pre, "output_digests": dict(pre["output_digests"])}
    first = next(iter(stale["output_digests"]))
    stale["output_digests"][first] = "sha256:" + "f" * 64
    assert any(
        "does not match file bytes" in error
        for error in CHECKER.validate_navigation_receipt(MANIFEST, route, stale)
    )

    j600_digest = "sha256:" + "9" * 64
    post = _navigation_receipt(
        route, post_j600=True, j600_receipt_digest=j600_digest
    )
    assert CHECKER.validate_post_j600_navigation_receipt(
        MANIFEST, route, post, j600_receipt_digest=j600_digest
    ) == []
    missing_pre_digest = dict(post)
    missing_pre_digest.pop("navigation_receipt_digest")
    assert any(
        "fields must equal" in error
        for error in CHECKER.validate_post_j600_navigation_receipt(
            MANIFEST,
            route,
            missing_pre_digest,
            j600_receipt_digest=j600_digest,
        )
    )
    wrong_pre_digest = {
        **post,
        "navigation_receipt_digest": "sha256:" + "0" * 64,
    }
    assert any(
        "does not bind the pre-J600 receipt digest" in error
        for error in CHECKER.validate_post_j600_navigation_receipt(
            MANIFEST,
            route,
            wrong_pre_digest,
            j600_receipt_digest=j600_digest,
        )
    )
    assert any(
        "fields must equal" in error or "stage" in error
        for error in CHECKER.validate_navigation_receipt(MANIFEST, route, post)
    )


def _install_terminal_route_fakes(
    tmp_path: Path, monkeypatch, candidates: dict[str, tuple[str, str, str, str]]
) -> None:
    receipt_path_to_job: dict[str, str] = {}
    for job_id in candidates:
        relative = _job(job_id)["receipt"]
        receipt_path_to_job[str(tmp_path / relative)] = job_id
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")

    def fake_read_jsonl(path: Path):
        job_id = receipt_path_to_job[str(path)]
        result, state, coverage, _trigger = candidates[job_id]
        receipt = _valid_receipt(job_id)
        receipt.update(result=result, state=state, coverage=coverage)
        return [receipt], CHECKER.canonical_digest({"receipt": job_id})

    def fake_closure(_root: Path, _manifest: dict, parent_job_id: str):
        trigger = candidates[parent_job_id][3]
        return {
            "closure_digest": CHECKER.canonical_digest({"closure": parent_job_id}),
            "trigger_class": trigger,
        }, []

    monkeypatch.setattr(CHECKER, "_read_jsonl", fake_read_jsonl)
    monkeypatch.setattr(CHECKER, "validate_receipt", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(CHECKER, "resolve_cohort_closure", fake_closure)
    monkeypatch.setattr(
        CHECKER,
        "_read_repo_json",
        lambda *_args, **_kwargs: ({}, "sha256:" + "a" * 64),
    )
    monkeypatch.setattr(
        CHECKER, "validate_navigation_receipt", lambda *_args, **_kwargs: []
    )


@pytest.mark.parametrize(
    ("expected_route", "candidates"),
    [
        (
            "p5a-valid-terminal",
            {"J-510": ("fail_terminal", "failed", "complete", "privacy")},
        ),
        (
            "p5a-inconclusive",
            {"J-510": ("inconclusive", "blocked", "partial", "missing")},
        ),
        (
            "p5b-valid-terminal",
            {
                "J-510": ("pass", "complete", "complete", "stage-pass"),
                "J-520": ("fail_terminal", "failed", "complete", "safety"),
            },
        ),
        (
            "p5b-inconclusive",
            {
                "J-510": ("pass", "complete", "complete", "stage-pass"),
                "J-520": (
                    "blocked_human",
                    "blocked",
                    "coverage_unavailable",
                    "stale",
                ),
            },
        ),
        (
            "p5c-pass",
            {
                "J-510": ("pass", "complete", "complete", "stage-pass"),
                "J-520": ("pass", "complete", "complete", "stage-pass"),
                "J-530": ("pass", "complete", "complete", "value-gate-pass"),
            },
        ),
        (
            "p5c-valid-terminal",
            {
                "J-510": ("pass", "complete", "complete", "stage-pass"),
                "J-520": ("pass", "complete", "complete", "stage-pass"),
                "J-530": (
                    "fail_terminal",
                    "failed",
                    "complete",
                    "guardrail-failure",
                ),
            },
        ),
        (
            "p5c-inconclusive",
            {
                "J-510": ("pass", "complete", "complete", "stage-pass"),
                "J-520": ("pass", "complete", "complete", "stage-pass"),
                "J-530": (
                    "inconclusive",
                    "blocked",
                    "coverage_unavailable",
                    "checker-integrity",
                ),
            },
        ),
    ],
)
def test_terminal_route_selection_accepts_each_exact_stage_route(
    tmp_path: Path,
    monkeypatch,
    expected_route: str,
    candidates: dict[str, tuple[str, str, str, str]],
) -> None:
    _install_terminal_route_fakes(tmp_path, monkeypatch, candidates)
    route, dependencies, errors = CHECKER.resolve_terminal_route(
        tmp_path, MANIFEST, dependency_route_id=expected_route
    )
    assert errors == []
    assert route["dependency_route_id"] == expected_route
    assert set(dependencies) == {route["predecessor_job_id"]}


def test_terminal_route_selection_rejects_later_receipt_after_early_terminal(
    tmp_path: Path, monkeypatch,
) -> None:
    candidates = {
        "J-510": ("fail_terminal", "failed", "complete", "privacy"),
        "J-530": ("pass", "complete", "complete", "value-gate-pass"),
    }
    _install_terminal_route_fakes(tmp_path, monkeypatch, candidates)
    route, dependencies, errors = CHECKER.resolve_terminal_route(
        tmp_path, MANIFEST, dependency_route_id="p5c-pass"
    )
    assert route == {}
    assert dependencies == {}
    assert "post-terminal predecessor receipt residue is forbidden: J-530" in errors


def test_terminal_route_revalidates_pre_j600_then_current_post_j600_outputs(
    tmp_path: Path, monkeypatch,
) -> None:
    outcomes = {
        "J-510": ("pass", "complete", "complete", "stage-pass"),
        "J-520": ("pass", "complete", "complete", "stage-pass"),
        "J-530": ("pass", "complete", "complete", "value-gate-pass"),
    }
    parent_paths: dict[str, str] = {}
    for job_id in outcomes:
        path = tmp_path / _job(job_id)["receipt"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
        parent_paths[str(path)] = job_id

    for relative in (
        CHECKER.NAVIGATION_INDEX_PATH,
        CHECKER.NAVIGATION_HANDOFF_PATH,
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"pre:{relative}\n", encoding="utf-8")

    predecessor_digest = CHECKER.canonical_digest({"receipt": "J-530"})
    closure_digest = CHECKER.canonical_digest({"closure": "J-530"})
    route_candidate = {
        "dependency_route_id": "p5c-pass",
        "predecessor_job_id": "J-530",
        "predecessor_receipt_digest": predecessor_digest,
        "predecessor_result": "pass",
        "predecessor_state": "complete",
        "predecessor_coverage": "complete",
        "trigger_class": "value-gate-pass",
        "closure_digest": closure_digest,
        "closure_complete": True,
        "permitted_decisions": ["scale", "narrow", "retire", "re-audit"],
    }
    pre_receipt = _navigation_receipt(route_candidate, repo_root=tmp_path)
    pre_path = tmp_path / CHECKER.NAVIGATION_PRE_RECEIPT_TEMPLATE.replace(
        "{route_id}", "p5c-pass"
    )
    pre_path.parent.mkdir(parents=True, exist_ok=True)
    pre_path.write_text(json.dumps(pre_receipt, sort_keys=True), encoding="utf-8")

    original_read_jsonl = CHECKER._read_jsonl

    def fake_read_jsonl(path: Path):
        job_id = parent_paths.get(str(path))
        if job_id is None:
            return original_read_jsonl(path)
        result, state, coverage, _trigger = outcomes[job_id]
        receipt = _valid_receipt(job_id)
        receipt.update(result=result, state=state, coverage=coverage)
        return [receipt], CHECKER.canonical_digest({"receipt": job_id})

    def fake_closure(_root: Path, _manifest: dict, parent_job_id: str):
        return {
            "closure_digest": CHECKER.canonical_digest(
                {"closure": parent_job_id}
            ),
            "trigger_class": outcomes[parent_job_id][3],
        }, []

    monkeypatch.setattr(CHECKER, "_read_jsonl", fake_read_jsonl)
    monkeypatch.setattr(CHECKER, "validate_receipt", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(CHECKER, "resolve_cohort_closure", fake_closure)

    pre_route, _dependencies, errors = CHECKER.resolve_terminal_route(
        tmp_path, MANIFEST
    )
    assert errors == []
    assert pre_route["navigation_receipt_digest"] == (
        "sha256:" + hashlib.sha256(pre_path.read_bytes()).hexdigest()
    )

    for relative in (
        CHECKER.NAVIGATION_INDEX_PATH,
        CHECKER.NAVIGATION_HANDOFF_PATH,
        CHECKER.NAVIGATION_SUPERSESSION_PATH,
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"post:{relative}\n", encoding="utf-8")
    j600 = {
        "result": "pass",
        "state": "complete",
        "coverage": "complete",
        "terminal_route": pre_route,
        "navigation_receipt_digest": pre_route["navigation_receipt_digest"],
    }
    j600_path = tmp_path / _job("J-600")["receipt"]
    j600_path.parent.mkdir(parents=True, exist_ok=True)
    j600_bytes = (json.dumps(j600, sort_keys=True) + "\n").encode()
    j600_path.write_bytes(j600_bytes)
    j600_digest = "sha256:" + hashlib.sha256(j600_bytes).hexdigest()
    post_receipt = _navigation_receipt(
        pre_route,
        post_j600=True,
        j600_receipt_digest=j600_digest,
        repo_root=tmp_path,
    )
    post_path = tmp_path / CHECKER.NAVIGATION_POST_RECEIPT_TEMPLATE.replace(
        "{route_id}", "p5c-pass"
    )
    post_path.write_text(json.dumps(post_receipt, sort_keys=True), encoding="utf-8")

    post_route, _dependencies, errors = CHECKER.resolve_terminal_route(
        tmp_path, MANIFEST
    )
    assert errors == []
    assert post_route == pre_route

    index_path = tmp_path / CHECKER.NAVIGATION_INDEX_PATH
    index_path.write_text("tampered post-navigation bytes\n", encoding="utf-8")
    route, dependencies, errors = CHECKER.resolve_terminal_route(tmp_path, MANIFEST)
    assert route == {}
    assert dependencies == {}
    assert any("does not match file bytes" in error for error in errors)


def test_evidence_digest_is_verified_against_file_bytes(tmp_path: Path) -> None:
    receipt = _valid_receipt()
    for relative in receipt["evidence_paths"]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"current evidence: {relative}\n", encoding="utf-8")
        receipt["evidence_digests"][relative] = (
            "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        )
    for relative in receipt["output_digests"]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"current output: {relative}\n", encoding="utf-8")
        receipt["output_digests"][relative] = (
            "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        )
    _write_checker_record(tmp_path, receipt)
    assert CHECKER.validate_receipt(
        receipt,
        MANIFEST,
        "J-100",
        repo_root=tmp_path,
        verify_files=True,
    ) == []

    evidence = receipt["evidence_paths"][0]
    receipt["evidence_digests"][evidence] = "sha256:" + "f" * 64
    errors = CHECKER.validate_receipt(
        receipt,
        MANIFEST,
        "J-100",
        repo_root=tmp_path,
        verify_files=True,
    )
    assert any("evidence digest does not match file bytes" in error for error in errors)


def test_checker_record_digest_binds_exact_file_bytes(tmp_path: Path) -> None:
    receipt = _valid_receipt()
    for digest_field in ("evidence_digests", "output_digests"):
        for relative in receipt[digest_field]:
            path = tmp_path / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"artifact:{relative}".encode())
            receipt[digest_field][relative] = (
                "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            )
    _write_checker_record(tmp_path, receipt)
    assert CHECKER.validate_receipt(
        receipt,
        MANIFEST,
        "J-100",
        repo_root=tmp_path,
        verify_files=True,
    ) == []

    checker_path = tmp_path / receipt["checker_record_path"]
    checker_path.write_bytes(b" " + checker_path.read_bytes())
    errors = CHECKER.validate_receipt(
        receipt,
        MANIFEST,
        "J-100",
        repo_root=tmp_path,
        verify_files=True,
    )
    assert (
        "receipt checker_record_digest does not match checker file bytes" in errors
    )


def test_append_only_retry_validates_historical_checker_but_only_latest_outputs(
    tmp_path: Path, monkeypatch, capsys,
) -> None:
    def materialize(receipt: dict, marker: str) -> None:
        for digest_field in ("evidence_digests", "output_digests"):
            for relative in receipt[digest_field]:
                path = tmp_path / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(f"{marker}:{relative}".encode())
                receipt[digest_field][relative] = (
                    "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
                )

    first = _valid_receipt("J-100")
    materialize(first, "attempt-1")
    _write_checker_record(tmp_path, first)
    frozen_first = json.loads(json.dumps(first))

    second = _valid_receipt("J-100")
    second["attempt_id"] = "J-100:attempt:2"
    second["checker_record_path"] = (
        "docs/campaigns/dad-high-value-recovery/checks/evidence/pilot/"
        "J-100-attempt-2-checker.json"
    )
    second["measured_budgets"]["attempt_number"] = 2
    materialize(second, "attempt-2-repair")
    _write_checker_record(tmp_path, second)

    stale_errors = CHECKER.validate_receipt(
        first,
        MANIFEST,
        "J-100",
        repo_root=tmp_path,
        verify_files=True,
    )
    assert any("does not match file bytes" in error for error in stale_errors)

    receipt_path = tmp_path / _job("J-100")["receipt"]
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(first, sort_keys=True)
        + "\n"
        + json.dumps(second, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "campaign.json"
    manifest_path.write_text(json.dumps(MANIFEST), encoding="utf-8")
    state_root = (
        tmp_path / "docs/campaigns/dad-high-value-recovery/state"
    )
    monkeypatch.setattr(CHECKER, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(CHECKER, "STATE_ROOT", state_root)
    monkeypatch.setattr(
        sys,
        "argv",
        ["verify_receipt_durability.py", "J-100", "--manifest", str(manifest_path)],
    )

    assert CHECKER.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "valid"
    assert result["rows"] == 2
    persisted_rows, _digest = CHECKER._read_jsonl(receipt_path)
    assert persisted_rows[0] == frozen_first
    assert persisted_rows[0]["checker_record_path"] != persisted_rows[1][
        "checker_record_path"
    ]

    attempts, _receipt_digests, errors = CHECKER.resolve_campaign_budget_receipts(
        tmp_path, MANIFEST
    )
    assert errors == []
    assert [row["attempt_id"] for row in attempts] == [
        "J-100:attempt:1",
        "J-100:attempt:2",
    ]


def test_direct_dependency_log_digest_and_latest_pass_are_resolved(tmp_path: Path) -> None:
    receipt = _valid_receipt("J-100")
    for relative in receipt["evidence_paths"]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"dependency evidence: {relative}\n", encoding="utf-8")
        receipt["evidence_digests"][relative] = (
            "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        )
    for relative in receipt["output_digests"]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"dependency output: {relative}\n", encoding="utf-8")
        receipt["output_digests"][relative] = (
            "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        )
    _write_checker_record(tmp_path, receipt)
    log_path = tmp_path / receipt["receipt_path"]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(receipt, sort_keys=True) + "\n").encode("utf-8")
    log_path.write_bytes(data)
    expected = "sha256:" + hashlib.sha256(data).hexdigest()

    resolved, errors = CHECKER.resolve_dependency_receipts(
        tmp_path,
        MANIFEST,
        "J-110",
        expected_digests={"J-100": expected},
    )
    assert errors == []
    assert resolved["J-100"]["receipt_digest"] == expected
    assert resolved["J-100"]["result"] == "pass"

    _resolved, errors = CHECKER.resolve_dependency_receipts(
        tmp_path,
        MANIFEST,
        "J-110",
        expected_digests={"J-100": "sha256:" + "f" * 64},
    )
    assert "dependency receipt digest mismatch: J-100" in errors
