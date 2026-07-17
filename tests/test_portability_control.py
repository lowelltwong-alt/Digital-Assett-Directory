from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import digital_asset_directory.portability_control as pc
from digital_asset_directory.harness_engineering import validate_harness_revision
from digital_asset_directory.portfolio_execution import request_execution_lease


ROOT = Path(__file__).resolve().parents[1]


def _inventory(new_ids: list[str]) -> dict:
    return {
        "baseline_commit": "b34cf64",
        "surfaces": {},
        "current_identity_count": len(new_ids),
        "baseline_identity_count": 0,
        "new_identity_ids": new_ids,
        "changed_identity_ids": [],
        "requiring_disposition_ids": new_ids,
        "observation_digests": {item: pc.canonical_digest(item) for item in new_ids},
        "inventory_digest": pc.canonical_digest(new_ids),
        "model_calls": 0,
    }


def _receipt(receipt_id: str, nonce: str, *, model: str = "fixture-a") -> dict:
    now = datetime.now(timezone.utc)
    return {
        "schema_version": "dad.model_attempt_receipt.v2",
        "receipt_id": receipt_id,
        "issuer_id": "receipt-issuer:synthetic-fixture",
        "verification_method": "synthetic_fixture",
        "runtime_id": "runtime:synthetic",
        "adapter_revision_id": "adapter-revision:synthetic-fixture:0.1.0",
        "assignment_id": "assignment:one",
        "attempt_id": "attempt:" + nonce,
        "provider_id": "provider:fixture",
        "model_family": model,
        "model_release": "fixture-release",
        "evidence_digest": pc.canonical_digest({"receipt": receipt_id}),
        "nonce": nonce,
        "observed_at": now.isoformat(),
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "verification_state": "verified",
        "core_revision_id": "core:one",
        "harness_revision_id": "harness:one",
        "corpus_revision_id": "corpus:one",
        "role_id": "role:one",
        "candidate_only": True,
        "execution_authorized": False,
    }


def test_current_portability_registry_is_valid_and_baselined() -> None:
    result = pc.validate_portability(ROOT)
    assert result["valid"] is True
    assert result["model_calls"] == 0
    assert result["inventory"]["baseline_integrity"] == "verified"
    assert result["inventory"]["surfaces"]["dad_skill_registry"]["baseline_count"] == 40
    assert set(result["inventory"]["new_identity_ids"]) == {
        "workflow:ml-synthetic-data-opportunity-review",
        "workflow:ml-synthetic-helper-research-refresh",
    }


def test_baseline_cache_is_commit_scoped_and_never_caches_current_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"show": 0, "tree": 0}

    def fake_show(_root: Path, _commit: str, _relative: str) -> dict:
        calls["show"] += 1
        return {}

    def fake_run(*_args, **_kwargs):
        calls["tree"] += 1
        return SimpleNamespace(stdout="", returncode=0)

    pc._baseline_snapshot.cache_clear()
    monkeypatch.setattr(pc, "_json_at_commit", fake_show)
    monkeypatch.setattr(pc.subprocess, "run", fake_run)
    first = pc._baseline_snapshot(str(ROOT.resolve()), "a" * 40)
    again = pc._baseline_snapshot(str(ROOT.resolve()), "a" * 40)
    assert first is again
    assert calls == {"show": len(pc._SOURCE_SPECS), "tree": 1}
    pc._baseline_snapshot(str(ROOT.resolve()), "b" * 40)
    assert calls == {"show": len(pc._SOURCE_SPECS) * 2, "tree": 2}
    pc._baseline_snapshot.cache_clear()


def test_portability_harness_revision_is_immutable_and_valid() -> None:
    import json

    revision = json.loads(
        (ROOT / "assets/agent-skills/portable-capability-governance/harness-revision.json").read_text(
            encoding="utf-8"
        )
    )
    assert validate_harness_revision(ROOT, revision)["lifecycle_state"] == "candidate"


def test_classifier_is_quiet_for_brainstorming_and_routes_reusable_work() -> None:
    assert pc.classify_eligibility("brainstorm some ideas")["applicability"] == "not_applicable"
    assert pc.classify_eligibility("create a reusable agent skill")["applicability"] == "portable_required"
    assert pc.classify_eligibility("ordinary task", ["assets/agent-skills/new/SKILL.md"])["applicability"] == "portable_required"
    assert pc.classify_eligibility("ordinary task", [".github/workflows/ci.yml"])["applicability"] == "portable_required"
    bound = pc.assess_lifecycle(
        ROOT,
        stage="preflight",
        task="Create a reusable library permanently tied to GPT-9",
    )
    assert bound["gate_outcome"] == "block"
    assert "normative_runtime_binding_in_request" in bound["finding_codes"]

    lease = pc.assess_lifecycle(
        ROOT,
        stage="implementation_lease",
        task="Create a reusable library",
        protected_transition=True,
    )
    assert lease["gate_outcome"] == "block"
    assert "missing_exact_portability_binding" in lease["finding_codes"]

    exact = pc.assess_lifecycle(
        ROOT,
        stage="implementation_lease",
        task="Revise the reusable portability skill",
        paths=["assets/agent-skills/portable-capability-governance/SKILL.md"],
        artifact_ids=["skill:portable-capability-governance"],
        protected_transition=True,
    )
    assert exact["gate_outcome"] == "pass"
    assert exact["bound_artifact_ids"] == ["skill:portable-capability-governance"]

    mismatch = pc.assess_lifecycle(
        ROOT,
        stage="implementation_lease",
        task="Create a reusable library named totally-new-library",
        paths=["src/totally_new_library.py"],
        artifact_ids=["skill:portable-capability-governance"],
        protected_transition=True,
    )
    assert mismatch["gate_outcome"] == "block"
    assert "missing_exact_portability_binding" in mismatch["finding_codes"]


def test_execution_lease_dispatcher_denies_governed_scope_without_exact_identity() -> None:
    result = request_execution_lease(
        ROOT,
        "workstream:unused",
        owner_id="role:builder",
        owner_kind="agent",
        repo_binding_id="repo-binding:unused",
        action_classes=["implement"],
        requested_paths=["src"],
        not_before=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        return_state="paused",
        rationale_code="bounded_build",
    )
    assert result["status"] == "portability_disposition_required"
    assert result["events_appended"] == 0
    assert result["execution_authorized"] is False


def test_new_identity_without_card_is_a_hard_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pc, "inventory", lambda _root: _inventory(["skill:unregistered-new-skill"]))
    result = pc.validate_portability(ROOT)
    assert result["valid"] is False
    assert {row["code"] for row in result["findings"]} >= {"missing_portability_disposition"}
    assessment = pc.assess_lifecycle(ROOT, stage="release", protected_transition=True)
    assert assessment["gate_outcome"] == "block"


def test_baseline_or_portable_content_tampering_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = _inventory([])
    baseline["baseline_integrity"] = "failed"
    monkeypatch.setattr(pc, "inventory", lambda _root: baseline)
    assert "baseline_integrity_failure" in {
        row["code"] for row in pc.validate_portability(ROOT)["findings"]
    }

    registry = deepcopy(pc.load_registry(ROOT))
    registry["cards"][0]["content_digest"] = "sha256:" + "0" * 64
    monkeypatch.setattr(pc, "load_registry", lambda _root: registry)
    assert "content_digest_mismatch" in {
        row["code"] for row in pc.validate_portability(ROOT)["findings"]
    }


def test_existing_identity_revision_needs_fresh_disposition(monkeypatch: pytest.MonkeyPatch) -> None:
    observed = _inventory([])
    observed["changed_identity_ids"] = ["skill:portable-capability-governance"]
    observed["requiring_disposition_ids"] = ["skill:portable-capability-governance"]
    observed["observation_digests"] = {
        "skill:portable-capability-governance": "sha256:" + "f" * 64
    }
    monkeypatch.setattr(pc, "inventory", lambda _root: observed)
    result = pc.validate_portability(ROOT)
    assert result["valid"] is False
    assert "stale_portability_disposition" in {row["code"] for row in result["findings"]}


def test_changed_governed_file_needs_exact_card_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pc,
        "changed_governed_files",
        lambda _root, _baseline: ["assets/agent-skills/existing/routines.yaml"],
    )
    result = pc.validate_portability(ROOT)
    assert result["valid"] is False
    assert "undispositioned_governed_file" in {
        row["code"] for row in result["findings"]
    }


def test_oversized_portable_source_is_not_silently_unscanned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = pc._resolved_portable_files

    def oversized(root: Path, card: dict):
        resolved = original(root, card)
        if card.get("artifact_id") != "skill:portable-capability-governance":
            return resolved
        return [("synthetic", SimpleNamespace(stat=lambda: SimpleNamespace(st_size=2_000_000)))]

    monkeypatch.setattr(pc, "_resolved_portable_files", oversized)
    monkeypatch.setattr(pc, "_portable_files_digest", lambda _root, card: card.get("content_digest"))
    monkeypatch.setattr(pc, "_portable_source_text", lambda _root, _card: "")
    result = pc.validate_portability(ROOT)
    assert "oversized_portable_source_unscanned" in {
        row["code"] for row in result["findings"]
    }


def test_source_runtime_binding_and_suspected_secret_block_protected_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pc, "_portable_source_text", lambda _root, _card: "always use GPT-9")
    monkeypatch.setattr(pc, "inventory", lambda _root: _inventory([]))
    assert "normative_runtime_binding_in_source" in {
        row["code"] for row in pc.validate_portability(ROOT)["findings"]
    }

    registry = deepcopy(pc.load_registry(ROOT))
    registry["cards"][0]["context_contract"] = "api_key is supplied later"
    monkeypatch.setattr(pc, "load_registry", lambda _root: registry)
    monkeypatch.setattr(pc, "_portable_source_text", lambda _root, _card: "")
    gate = pc.assess_lifecycle(ROOT, stage="release", protected_transition=True)
    assert gate["gate_outcome"] == "block"
    assert "suspected_secret" in gate["quarantine_codes"]


def test_research_cursor_fields_are_not_mistaken_for_cursor_runtime_binding() -> None:
    assert pc._line_has_normative_runtime_binding("cursor_required: true") is False
    assert pc._line_has_normative_runtime_binding("Use pointer-only results after the cursor is stored.") is False
    assert pc._line_has_normative_runtime_binding("always use Cursor for this workflow") is True
    assert pc._line_has_normative_runtime_binding("always use cursor for this workflow") is True
    assert pc._line_has_normative_runtime_binding("read-only GPT adapter observation") is False
    assert pc._line_has_normative_runtime_binding("runtime-specific APIs are fallback adapters only") is False
    assert pc._line_has_normative_runtime_binding("always use GPT-9; fallback adapter available") is True
    assert (
        pc._line_has_normative_runtime_binding(
            "GPT-9 is required; use fallback adapter only for outages"
        )
        is True
    )


def test_portable_digest_is_stable_across_text_line_endings(tmp_path: Path) -> None:
    card = {"portable_files": ["contract.txt"]}
    path = tmp_path / "contract.txt"
    path.write_bytes(b"first\nsecond\n")
    lf_digest = pc._portable_files_digest(tmp_path, card)
    path.write_bytes(b"first\r\nsecond\r\n")
    assert pc._portable_files_digest(tmp_path, card) == lf_digest


def test_live_personal_source_is_verified_locally_but_absence_is_ci_safe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "missing-codex-home"))
    unavailable = pc.validate_portability(ROOT)
    assert unavailable["valid"] is True
    assert "external_source_unavailable" in {
        row["code"] for row in unavailable["findings"]
    }

    live_root = tmp_path / "codex-home"
    skill = live_root / "skills/portable-capability-governance/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("tampered live procedure", encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(live_root))
    tampered = pc.validate_portability(ROOT)
    assert tampered["valid"] is False
    assert "content_digest_mismatch" in {row["code"] for row in tampered["findings"]}


def test_normative_model_binding_fails_but_marked_prose_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = deepcopy(pc.load_registry(ROOT))
    registry["cards"][0]["artifact_id"] = "skill:gpt-9-bound"
    registry["cards"][0]["context_contract"] += " Documentation may compare GPT with alternatives."
    monkeypatch.setattr(pc, "load_registry", lambda _root: registry)
    monkeypatch.setattr(pc, "inventory", lambda _root: _inventory([]))
    result = pc.validate_portability(ROOT)
    assert "normative_runtime_binding_in_core" in {row["code"] for row in result["findings"]}


def test_secret_handling_does_not_echo_value(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = deepcopy(pc.load_registry(ROOT))
    registry["cards"][0]["context_contract"] = "Synthetic sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ012345 canary"
    monkeypatch.setattr(pc, "load_registry", lambda _root: registry)
    monkeypatch.setattr(pc, "inventory", lambda _root: _inventory([]))
    result = pc.validate_portability(ROOT)
    assert "confirmed_secret" in {row["code"] for row in result["findings"]}
    assert "ABCDEFGHIJKLMNOPQRSTUVWXYZ" not in repr(result)


def test_receipts_require_registered_issuer_adapter_and_no_replay() -> None:
    first = _receipt("model-attempt-receipt:first", "nonce-one")
    assert pc.verify_attempt_receipt(ROOT, first)["verified"] is True
    replay = _receipt("model-attempt-receipt:second", "nonce-one", model="fixture-b")
    result = pc.verify_attempt_receipt(ROOT, replay, prior_receipts=[first])
    assert result["verified"] is False
    assert "receipt_replay_detected" in result["reason_codes"]
    forged = {**first, "issuer_id": "receipt-issuer:unknown", "receipt_id": "model-attempt-receipt:forged", "nonce": "nonce-two"}
    assert "unregistered_receipt_issuer" in pc.verify_attempt_receipt(ROOT, forged)["reason_codes"]


def test_verified_receipt_requires_complete_model_identity() -> None:
    incomplete = {**_receipt("model-attempt-receipt:incomplete", "nonce-incomplete"), "provider_id": ""}
    result = pc.verify_attempt_receipt(ROOT, incomplete)
    assert result["verified"] is False
    assert "model_identity_incomplete" in result["reason_codes"]


def test_non_fixture_attestation_fails_closed_without_verifier() -> None:
    receipt = {
        **_receipt("model-attempt-receipt:attestation", "nonce-attestation"),
        "verification_method": "signed_attestation",
        "attestation_ref": "sha256:" + "a" * 64,
    }
    result = pc.verify_attempt_receipt(ROOT, receipt)
    assert result["verified"] is False
    assert "attestation_verifier_unavailable" in result["reason_codes"]


def test_qualification_detects_replay_across_selected_receipts() -> None:
    one = _receipt("model-attempt-receipt:replay-one", "nonce-shared", model="fixture-a")
    two = _receipt("model-attempt-receipt:replay-two", "nonce-shared", model="fixture-b")
    qualification = {
        "schema_version": "dad.portable_runtime_qualification.v1",
        "qualification_id": "runtime-qualification:replay",
        "methodology_id": "dad:methodology:portable-runtime-qualification:0.1.0",
        "role_id": "role:one", "core_revision_id": "core:one",
        "adapter_revision_id": "adapter-revision:synthetic-fixture:0.1.0",
        "harness_revision_id": "harness:one", "corpus_revision_id": "corpus:one",
        "operating_envelope_digest": pc.canonical_digest("fixture"),
        "receipt_ids": [one["receipt_id"], two["receipt_id"]], "matched_attempts": 2,
        "predeclared_margin": 0.1, "protected_cohorts": ["boundary"],
        "evaluator_integrity": "verified", "hard_gate_failures": [], "result": "pass",
        "human_promotion_required": True, "candidate_only": True, "execution_authorized": False,
    }
    result = pc.qualify_runtime(ROOT, qualification, [one, two])
    assert result["result"] == "no_winner"
    assert "receipt_unverified" in result["reason_codes"]


def test_hostname_or_user_label_cannot_become_receipt_evidence() -> None:
    receipt = {**_receipt("model-attempt-receipt:host", "nonce-host"), "hostname": "gpt-provider", "user_label": "frontier"}
    with pytest.raises(ValueError, match="Additional properties"):
        pc.verify_attempt_receipt(ROOT, receipt)


def test_synthetic_cross_model_result_never_self_promotes() -> None:
    one = _receipt("model-attempt-receipt:one", "nonce-qual-one", model="fixture-a")
    two = _receipt("model-attempt-receipt:two", "nonce-qual-two", model="fixture-b")
    qualification = {
        "schema_version": "dad.portable_runtime_qualification.v1",
        "qualification_id": "runtime-qualification:fixture",
        "methodology_id": "dad:methodology:portable-runtime-qualification:0.1.0",
        "role_id": "role:one",
        "core_revision_id": "core:one",
        "adapter_revision_id": "adapter-revision:synthetic-fixture:0.1.0",
        "harness_revision_id": "harness:one",
        "corpus_revision_id": "corpus:one",
        "operating_envelope_digest": pc.canonical_digest("fixture"),
        "receipt_ids": [one["receipt_id"], two["receipt_id"]],
        "matched_attempts": 2,
        "predeclared_margin": 0.1,
        "protected_cohorts": ["boundary"],
        "evaluator_integrity": "verified",
        "hard_gate_failures": [],
        "result": "pass",
        "human_promotion_required": True,
        "candidate_only": True,
        "execution_authorized": False,
    }
    result = pc.qualify_runtime(ROOT, qualification, [one, two])
    assert result["result"] == "no_winner"
    assert "live_diversity_not_authorized" in result["reason_codes"]
    assert result["execution_authorized"] is False

    qualification["core_revision_id"] = "core:different"
    mismatch = pc.qualify_runtime(ROOT, qualification, [one, two])
    assert "qualification_binding_mismatch" in mismatch["reason_codes"]


def test_rollback_revalidates_current_route_and_health_is_bounded() -> None:
    blocked = pc.rollback_eligible({"health": "unavailable", "retirement_state": "retired", "privacy_eligible": True, "authority_eligible": True, "qualification_current": True})
    assert blocked["eligible"] is False
    assert blocked["action"] == "resumable_checkpoint"
    health = pc.health_snapshot(ROOT)
    assert len(health["decisions"]) <= 3
    assert health["model_calls"] == 0


def test_exception_candidate_never_creates_reviewed_exception() -> None:
    candidate = pc.exception_candidate("skill:bound", "requires certified hardware")
    assert candidate["reviewed_exception_created"] is False
    assert candidate["execution_authorized"] is False
