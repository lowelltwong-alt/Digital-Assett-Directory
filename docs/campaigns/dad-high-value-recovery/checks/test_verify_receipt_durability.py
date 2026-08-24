from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path


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
    return {
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
        "authority_boundary": (
            "This receipt does not authorize external, destructive, publication, "
            "merge, deployment, or downstream effects."
        ),
    }


def test_valid_receipt_passes_contract() -> None:
    assert CHECKER.validate_receipt(
        _valid_receipt(), MANIFEST, "J-100", verify_files=False
    ) == []


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
    errors = CHECKER.validate_receipt(receipt, MANIFEST, "J-100", verify_files=False)
    assert "pass input_digests must equal the current manifest revision" in errors


def test_same_producer_and_checker_fails() -> None:
    receipt = _valid_receipt()
    receipt["checker_identity"] = receipt["producer_identity"]
    errors = CHECKER.validate_receipt(receipt, MANIFEST, "J-100", verify_files=False)
    assert "producer_identity and checker_identity must differ" in errors


def test_incomplete_coverage_cannot_pass() -> None:
    receipt = _valid_receipt()
    receipt["coverage"] = "partial"
    errors = CHECKER.validate_receipt(receipt, MANIFEST, "J-100", verify_files=False)
    assert "pass requires complete coverage" in errors


def test_pass_requires_all_outputs_and_checkpoint_evidence() -> None:
    receipt = _valid_receipt()
    receipt["output_digests"].pop(next(iter(receipt["output_digests"])))
    errors = CHECKER.validate_receipt(receipt, MANIFEST, "J-100", verify_files=False)
    assert "pass output_digests keys must equal declared job outputs" in errors

    receipt = _valid_receipt()
    checkpoint = receipt["checkpoint_path"]
    receipt["evidence_paths"].remove(checkpoint)
    receipt["evidence_digests"].pop(checkpoint)
    errors = CHECKER.validate_receipt(receipt, MANIFEST, "J-100", verify_files=False)
    assert "evidence_paths must include checkpoint_path" in errors


def test_atomic_child_is_flattened_and_requires_case_binding() -> None:
    jobs = CHECKER._manifest_jobs(MANIFEST)
    assert len([job_id for job_id in jobs if "-C" in job_id]) == 70
    receipt = _valid_receipt("J-510-C01")
    receipt["case_binding"] = "sha256:" + "4" * 64
    receipt["case_binding_table_digest"] = "sha256:" + "5" * 64
    assert CHECKER.validate_receipt(
        receipt, MANIFEST, "J-510-C01", verify_files=False
    ) == []

    receipt["case_binding"] = None
    errors = CHECKER.validate_receipt(
        receipt, MANIFEST, "J-510-C01", verify_files=False
    )
    assert "atomic child case_binding must be a SHA-256 digest" in errors


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
