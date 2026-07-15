from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from digital_asset_directory.portfolio_intents import (
    IntentIntegrityError,
    capture_plan,
    fold_plan_index,
    load_plan_revision,
    read_events,
    revise_plan,
    search_plans,
)
from digital_asset_directory.learning import preflight
from digital_asset_directory.transport import data_path, init_data_root
from digital_asset_directory.technical_product_os import (
    append_routing_receipt,
    append_workflow_run_event,
    build_routing_receipt,
    build_workflow_run_event,
    route_capabilities,
)


REPO = Path(__file__).resolve().parents[1]


def _private_hub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    hub = tmp_path / "hub"
    data = tmp_path / "data"
    hub.mkdir()
    init_data_root(data, hub_root=hub, force_onedrive=True)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data))
    return hub, data


def test_plan_capture_requires_initialized_private_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    monkeypatch.setenv("DAD_DATA_ROOT", str(tmp_path / "ghost"))
    with pytest.raises(IntentIntegrityError, match="initialized DAD_DATA_ROOT"):
        capture_plan(hub, title="Family", outcome="Build it")


def test_seed_is_private_non_authorizing_idempotent_and_revisable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub, data = _private_hub(tmp_path, monkeypatch)
    first = capture_plan(
        hub,
        title="Full stack family",
        outcome="Create a reusable engineering family",
        plan_markdown="Use C:\\Users\\lowel\\secret\\plan.md and token sk-12345678901234567890",
        request_id="request:one",
    )
    retry = capture_plan(
        hub,
        title="Full stack family",
        outcome="Create a reusable engineering family",
        plan_markdown="Use C:\\Users\\lowel\\secret\\plan.md and token sk-12345678901234567890",
        request_id="request:one",
    )
    assert retry["event_id"] == first["event_id"]
    assert first["execution_authorized"] is False
    assert not (data / "processed" / "portfolio_os" / "workstream-events.jsonl").exists()
    artifact = load_plan_revision(hub, first["plan_id"])
    assert "C:\\Users" not in artifact["plan_markdown"]
    assert "sk-12345678901234567890" not in artifact["plan_markdown"]

    revised = revise_plan(hub, first["plan_id"], lifecycle="decision_complete")
    assert revised["revision_id"] != first["revision_id"]
    assert revised["payload"]["predecessor_revision_id"] == first["revision_id"]
    index = fold_plan_index(read_events(hub))
    assert index["plan_count"] == 1
    assert index["plans"][0]["revision_count"] == 2
    assert (data / "processed" / "portfolio_os" / "plan-index.json").exists()
    assert (data / "processed" / "portfolio_os" / "plan-build-status.json").exists()


def test_conflicting_idempotency_request_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub, _data = _private_hub(tmp_path, monkeypatch)
    capture_plan(hub, title="A", outcome="First", request_id="same")
    with pytest.raises(IntentIntegrityError, match="different intent content"):
        capture_plan(hub, title="A", outcome="Changed", request_id="same")


def test_torn_journal_fails_safely(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hub, data = _private_hub(tmp_path, monkeypatch)
    path = data / "raw" / "portfolio" / "intent-events.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text('{"schema_version":', encoding="utf-8")
    with pytest.raises(IntentIntegrityError, match="Invalid intent journal"):
        read_events(hub)


def test_verified_complete_requires_acceptance_and_independent_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub, _data = _private_hub(tmp_path, monkeypatch)
    (hub / "schemas").mkdir()
    for name in ("capability-routing-receipt.schema.json", "workflow-run-event.schema.json"):
        shutil.copy2(REPO / "schemas" / name, hub / "schemas" / name)
    with pytest.raises(ValueError, match="acceptance evidence"):
        capture_plan(hub, title="Done", outcome="Done", implementation_state="verified_complete")
    candidate = capture_plan(
        hub,
        title="Done",
        outcome="Done",
        implementation_state="implemented_candidate",
        producer_ref="role:producer",
    )
    route = route_capabilities(REPO, "production ready platform cloud")
    receipt = build_routing_receipt(
        route,
        opaque_task_id="plan-proof",
        request_class="technical_product",
        request_tags=["validation"],
        repository_id="repo:fixture",
    )
    append_routing_receipt(hub, receipt)
    validation_event = None
    for state in ("started", "completed", "independently_validated"):
        event = build_workflow_run_event(
            workflow_id="workflow:production-readiness",
            workflow_revision_id="workflow-revision:production-readiness:v1",
            run_id="plan-proof-run",
            route_event_id=receipt["id"],
            event_state=state,
            capability_ids=["capability:platform-cloud-sre"],
            input_fingerprint="sha256:" + "1" * 64,
            output_fingerprint=("sha256:" + "2" * 64) if state != "started" else "",
            execution_mode="deterministic",
            producer_ref="role:producer",
            plan_revision_id=candidate["revision_id"],
            independent_checker_ref="role:checker" if state == "independently_validated" else "",
            independent_evaluation_ref="evaluation:plan-proof" if state == "independently_validated" else "",
            validation_outcome="supported_success" if state == "independently_validated" else "",
            evidence_refs=["test:acceptance"] if state == "independently_validated" else [],
        )
        append_workflow_run_event(hub, event)
        if state == "independently_validated":
            validation_event = event
    assert validation_event is not None
    event = revise_plan(
        hub,
        candidate["plan_id"],
        implementation_state="verified_complete",
        acceptance_evidence=["test:acceptance"],
        independent_check_ref=validation_event["id"],
        producer_ref="role:producer",
        independent_checker_ref="role:checker",
        validated_plan_revision_id=candidate["revision_id"],
    )
    assert event["payload"]["implementation_state"] == "verified_complete"


def test_self_fabricated_minimal_validation_receipt_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub, _data = _private_hub(tmp_path, monkeypatch)
    candidate = capture_plan(
        hub, title="Candidate", outcome="Verify it",
        implementation_state="implemented_candidate", producer_ref="role:producer",
    )
    ledger = data_path(hub, "usage") / "workflow-run-events.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps({
        "id": "run-event:fake",
        "event_state": "independently_validated",
        "plan_revision_id": candidate["revision_id"],
        "producer_ref": "role:producer",
        "independent_checker_ref": "role:checker",
        "validation_outcome": "supported_success",
        "evidence_refs": ["test:acceptance"],
    }) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="non-canonical"):
        revise_plan(
            hub,
            candidate["plan_id"],
            implementation_state="verified_complete",
            acceptance_evidence=["test:acceptance"],
            independent_check_ref="run-event:fake",
            producer_ref="role:producer",
            independent_checker_ref="role:checker",
            validated_plan_revision_id=candidate["revision_id"],
        )


def test_same_title_does_not_merge_distinct_plan_identity_and_search_is_partitioned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub, _data = _private_hub(tmp_path, monkeypatch)
    first = capture_plan(hub, title="Platform", outcome="Build a developer platform")
    second = capture_plan(hub, title="Platform", outcome="Build an evidence platform")
    public = capture_plan(
        hub, title="Platform", outcome="Publish a public platform", privacy_class="public"
    )
    assert len({first["plan_id"], second["plan_id"], public["plan_id"]}) == 3
    private_matches = search_plans(hub, "platform", privacy_partition="private")["matches"]
    public_matches = search_plans(hub, "platform", privacy_partition="public")["matches"]
    assert {row["plan_id"] for row in private_matches} == {first["plan_id"], second["plan_id"]}
    assert {row["plan_id"] for row in public_matches} == {public["plan_id"]}


def test_authority_and_classification_values_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub, _data = _private_hub(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="signed portfolio execution-control"):
        capture_plan(hub, title="A", outcome="B", lifecycle="approved_for_execution")
    with pytest.raises(ValueError, match="privacy class"):
        capture_plan(hub, title="A", outcome="B", privacy_class="secretish")
    with pytest.raises(ValueError, match="consequence class"):
        capture_plan(hub, title="A", outcome="B", consequence_class="extreme")

    candidate = capture_plan(hub, title="Approved", outcome="B")
    with pytest.raises(ValueError, match="signed portfolio execution-control"):
        revise_plan(
            hub, candidate["plan_id"], lifecycle="approved_for_execution",
            human_approval_ref="self-fabricated:approval",
        )


def test_preflight_captures_only_explicit_material_plan_seed_and_deduplicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub, data = _private_hub(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    database = data / "state" / "catalog.sqlite3"
    task = "Plan a full stack agent family over time with private client notes omitted"
    first = preflight(hub, repo, database, "codex", task)
    second = preflight(hub, repo, database, "codex", task)
    ordinary = preflight(hub, repo, database, "codex", "Explain the current status")
    architecture_review = preflight(
        hub, repo, database, "codex", "Review and explain the current architecture roadmap"
    )
    read_only_build_mentions = [
        "Review whether we should build a capability OS",
        "Research how to build an architecture for agents",
        "Audit how agents build products",
    ]
    read_only_results = [preflight(hub, repo, database, "codex", value) for value in read_only_build_mentions]

    assert first["intent_checkpoint"]["status"] == "captured"
    assert first["intent_checkpoint"]["event_id"] == second["intent_checkpoint"]["event_id"]
    assert "intent_checkpoint" not in ordinary
    assert "intent_checkpoint" not in architecture_review
    assert all("intent_checkpoint" not in row for row in read_only_results)
    assert first["related_work"]["execution_authorized"] is False
    plan_bytes = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (data / "private" / "portfolio" / "plans").rglob("*")
        if path.is_file()
    )
    assert task not in plan_bytes
    assert "client notes" not in plan_bytes


def test_generic_product_intents_keep_a_sanitized_identity_discriminator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub, data = _private_hub(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    database = data / "state" / "catalog.sqlite3"
    billing = preflight(hub, repo, database, "codex", "Build a billing product")
    inventory = preflight(hub, repo, database, "codex", "Build an inventory product")
    assert billing["intent_checkpoint"]["plan_id"] != inventory["intent_checkpoint"]["plan_id"]
    compound_billing = preflight(
        hub, repo, database, "codex",
        "Build a full stack agent family for the billing product",
    )
    compound_inventory = preflight(
        hub, repo, database, "codex",
        "Build a full stack agent family for the inventory product",
    )
    assert (
        compound_billing["intent_checkpoint"]["plan_id"]
        != compound_inventory["intent_checkpoint"]["plan_id"]
    )


def test_plan_journal_and_artifact_tampering_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub, data = _private_hub(tmp_path, monkeypatch)
    event = capture_plan(hub, title="Tamper", outcome="Detect changes")
    journal = data / "raw" / "portfolio" / "intent-events.jsonl"
    row = json.loads(journal.read_text(encoding="utf-8"))
    row["payload"]["lifecycle"] = "approved_for_execution"
    journal.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(IntentIntegrityError, match="digest mismatch"):
        read_events(hub)

    # Restore the journal, then tamper the immutable artifact.
    journal.write_text(json.dumps(event) + "\n", encoding="utf-8")
    artifact = next((data / "private" / "portfolio" / "plans").rglob("*.md"))
    artifact.write_text("changed after capture", encoding="utf-8")
    with pytest.raises(IntentIntegrityError, match="content digest mismatch"):
        load_plan_revision(hub, event["plan_id"])
