"""Portfolio OS workstream kernel tests (collaboration V0).

Covers the required matrix from the collaboration mission: redaction across
every persisted field, stable identity, relation identity, idempotency,
concurrency, transactional capture, torn-tail recovery, corrupt interior
events, lifecycle last-event-wins, incubation/snooze/dismissal behavior,
Today cap and tie ordering, relationship fixtures, mature-overlap honesty,
shared conversation context, terminal states, HTML/path safety, dependency
rollup, sprawl clusters, refresh change detection, schema conformance, and
the no-Git-mutation boundary.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier, current_thread

import pytest
from jsonschema.validators import validator_for

from digital_asset_directory import portfolio_events as pe
from digital_asset_directory import portfolio_relations as pr
from digital_asset_directory import portfolio_workstreams as pw

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
SECRET = "api_key=sk-" + "a" * 24
RAW_SECRET = "sk-" + "a" * 24


def _capture_one(hub: Path, text: str = "rust parser cache for tokenizer", **kwargs):
    result = pw.capture_ideas(hub, [text], conversation_id="c1", now=T0, **kwargs)
    return result["proposals"][0]["workstream_id"], result


def _validator(schema_path: Path):
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    cls = validator_for(schema)
    cls.check_schema(schema)
    return cls(schema)


# ---------------------------------------------------------------------------
# Privacy / redaction / paths / HTML
# ---------------------------------------------------------------------------


def test_redaction_covers_every_persisted_field(tmp_path: Path) -> None:
    hub = tmp_path
    pw.capture_ideas(
        hub,
        [f"idea alpha beta {SECRET}"],
        conversation_id=f"conv-{RAW_SECRET}",
        conversation_title=f"title {SECRET}",
        now=T0,
    )
    ws_id, _ = (
        pw.workstream_id_for(
            pw.idea_id_for(f"conv-{RAW_SECRET}", pw.load_state(hub, now=T0)["ideas"][0]["text"])
        ),
        None,
    )
    ws_id = pw.load_state(hub, now=T0)["workstreams"][0]["workstream_id"]
    pw.record_capsule(
        hub,
        ws_id,
        pause_reason=f"pause {SECRET}",
        blocker=f"block {SECRET}",
        last_check=f"check {SECRET}",
        next_action=f"next {SECRET}",
        now=T0,
    )
    pw.record_feedback(hub, ws_id, "dismiss", note=f"note {SECRET}", now=T0 + timedelta(hours=1))
    pw.record_binding(hub, ws_id, "worktree", r"C:\Users\someone\proj\wt-a", label=f"lbl {SECRET}", now=T0 + timedelta(hours=2))
    raw = pe.ledger_path(hub).read_text(encoding="utf-8")
    assert RAW_SECRET not in raw
    assert "C:\\Users" not in raw and "C:/Users" not in raw
    assert "[LOCAL_PATH]/wt-a" in raw


def test_malicious_html_is_escaped_and_paths_minimized(tmp_path: Path) -> None:
    hub = tmp_path
    pw.capture_ideas(
        hub,
        ["<script>alert(1)</script> graph cache layer for C:\\Users\\lowel\\notes.txt"],
        conversation_id="c1",
        now=T0,
    )
    state = pw.load_state(hub, now=T0)
    html = pw.workstream_state_html(state)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    ledger = pe.ledger_path(hub).read_text(encoding="utf-8")
    assert "C:\\\\Users" not in ledger and "lowel" not in ledger
    assert "[LOCAL_PATH]/notes.txt" in ledger


def test_state_output_is_local_private(tmp_path: Path) -> None:
    state = pw.load_state(tmp_path, now=T0)
    assert state["public_safe"] is False
    assert state["data_classification"] == "local_private_metadata"


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


def test_idea_identity_stable_across_secret_rotation(tmp_path: Path) -> None:
    hub = tmp_path
    r1 = pw.capture_ideas(hub, [f"rotate key {SECRET} for parser"], conversation_id="c1", now=T0)
    r2 = pw.capture_ideas(
        hub, ["rotate key api_key=sk-" + "b" * 24 + " for parser"], conversation_id="c1", now=T0 + timedelta(days=1)
    )
    assert r1["proposals"][0]["idea_id"] == r2["proposals"][0]["idea_id"]
    assert r2["events_appended"] == 0  # minimization happens before identity


def test_workstream_identity_stable_across_binding_renames(tmp_path: Path) -> None:
    hub = tmp_path
    ws_id, _ = _capture_one(hub)
    pw.record_binding(hub, ws_id, "branch", "feature/old-name", now=T0)
    pw.record_binding(hub, ws_id, "branch", "feature/new-name", now=T0 + timedelta(days=1))
    state = pw.load_state(hub, now=T0 + timedelta(days=1))
    ws = state["workstreams"][0]
    assert ws["workstream_id"] == ws_id
    assert {b["ref"] for b in ws["bindings"]} == {"feature/old-name", "feature/new-name"}


def test_relation_identity_includes_source_target_type_and_evidence(tmp_path: Path) -> None:
    target = pr.RelationTarget(
        target_kind="workstream", target_id="dad:ws:X", target_label="t", text="rust parser cache tokenizer"
    )
    rels_a, _ = pr.classify_relations("src-A", "rust parser speedup tokenizer", [target])
    rels_b, _ = pr.classify_relations("src-B", "rust parser speedup tokenizer", [target])
    assert rels_a and rels_b
    assert rels_a[0]["relation_id"] != rels_b[0]["relation_id"]  # source differs
    rels_a2, _ = pr.classify_relations("src-A", "rust parser speedup tokenizer", [target])
    assert rels_a[0]["relation_id"] == rels_a2[0]["relation_id"]  # deterministic


def test_solo_capture_is_idempotent(tmp_path: Path) -> None:
    hub = tmp_path
    pw.capture_ideas(hub, ["one idea alpha beta"], now=T0)
    r2 = pw.capture_ideas(hub, ["one idea alpha beta"], now=T0 + timedelta(seconds=5))
    assert r2["events_appended"] == 0
    assert pw.load_state(hub, now=T0 + timedelta(days=1))["summary"]["idea_count"] == 1


# ---------------------------------------------------------------------------
# Idempotency and the event chain
# ---------------------------------------------------------------------------


def test_feedback_retry_dedupes_with_explicit_command_id(tmp_path: Path) -> None:
    hub = tmp_path
    ws_id, _ = _capture_one(hub)
    r1 = pw.record_feedback(
        hub, ws_id, "dismiss", command_id="retry-command-1", now=T0 + timedelta(days=1)
    )
    r2 = pw.record_feedback(
        hub,
        ws_id,
        "dismiss",
        command_id="retry-command-1",
        now=T0 + timedelta(days=1, seconds=30),
    )
    assert r1["events_appended"] == 1
    assert r2["events_appended"] == 0 and r2["status"] == "deduplicated"
    state = pw.load_state(hub, now=T0 + timedelta(days=2))
    assert state["workstreams"][0]["dismiss_count"] == 1


def test_genuine_repeat_after_stream_advanced_appends(tmp_path: Path) -> None:
    hub = tmp_path
    ws_id, _ = _capture_one(hub)
    pw.record_feedback(hub, ws_id, "dismiss", now=T0 + timedelta(days=1))
    pw.record_capsule(hub, ws_id, next_action="try again", now=T0 + timedelta(days=2))
    r3 = pw.record_feedback(hub, ws_id, "dismiss", now=T0 + timedelta(days=3))
    assert r3["events_appended"] == 1
    state = pw.load_state(hub, now=T0 + timedelta(days=4))
    assert state["workstreams"][0]["dismiss_count"] == 2


def test_capsule_last_check_update_lands(tmp_path: Path) -> None:
    hub = tmp_path
    ws_id, _ = _capture_one(hub)
    pw.record_capsule(hub, ws_id, next_action="do X", last_check="tests pass", now=T0)
    r2 = pw.record_capsule(hub, ws_id, next_action="do X", last_check="tests FAIL", now=T0 + timedelta(hours=2))
    assert r2["events_appended"] == 1
    state = pw.load_state(hub, now=T0 + timedelta(days=1))
    assert state["workstreams"][0]["capsule"]["last_check"] == "tests FAIL"


def test_capture_recapture_same_conversation_is_idempotent(tmp_path: Path) -> None:
    hub = tmp_path
    _capture_one(hub)
    _, r2 = _capture_one(hub)
    assert r2["events_appended"] == 0


# ---------------------------------------------------------------------------
# Durability: torn tail, corrupt interior, concurrency, transactional pair
# ---------------------------------------------------------------------------


def test_torn_tail_is_quarantined_and_append_survives(tmp_path: Path) -> None:
    hub = tmp_path
    _capture_one(hub)
    path = pe.ledger_path(hub)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write('{"event_id": "dad:torn:fragment", "event_kind": "idea_cap')
    result = pw.capture_ideas(hub, ["second idea sql cache warmup"], conversation_id="c2", now=T0)
    assert result["tail_fragments_quarantined"] == 1
    assert result["events_appended"] == 2
    state = pw.load_state(hub, now=T0)
    assert state["summary"]["idea_count"] == 2
    assert state["summary"]["workstream_count"] == 2
    quarantine = pe.quarantine_path(path)
    assert quarantine.exists() and "dad:torn:fragment" in quarantine.read_text(encoding="utf-8")
    assert not any("orphan" in row["note"] for row in state["coverage"])


def test_corrupt_interior_line_is_counted_not_healed(tmp_path: Path) -> None:
    hub = tmp_path
    _capture_one(hub)
    path = pe.ledger_path(hub)
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(lines[0] + "\n{not json}\n" + "\n".join(lines[1:]) + "\n", encoding="utf-8")
    state = pw.load_state(hub, now=T0)
    assert state["ledger_diagnostics"]["corrupt_line_count"] == 1
    assert state["summary"]["workstream_count"] == 1  # rest of the fold intact


def test_orphan_idea_is_reported_not_silent(tmp_path: Path) -> None:
    hub = tmp_path
    _capture_one(hub)
    path = pe.ledger_path(hub)
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(lines[0] + "\n", encoding="utf-8")  # drop the workstream event
    state = pw.load_state(hub, now=T0)
    assert state["summary"]["workstream_count"] == 0
    assert any("idea without workstream" in row["note"] for row in state["coverage"])


def test_concurrent_appends_are_safe(tmp_path: Path) -> None:
    hub = tmp_path
    ws_id, _ = _capture_one(hub)

    def worker(index: int) -> int:
        result = pw.record_feedback(
            hub, ws_id, "dismiss", note=f"pass {index}", now=T0 + timedelta(days=1, minutes=index)
        )
        return int(result["events_appended"])

    with ThreadPoolExecutor(max_workers=8) as pool:
        appended = list(pool.map(worker, range(8)))
    events, diagnostics = pe.read_events(pe.ledger_path(hub))
    assert diagnostics["corrupt_line_count"] == 0
    assert diagnostics["invalid_envelope_count"] == 0
    notes = {
        event["payload"]["note"]
        for event in events
        if event["event_kind"] == "focus_feedback"
    }
    assert notes == {f"pass {i}" for i in range(8)}
    assert sum(appended) == 8


def test_append_precondition_rejection_leaves_ledger_unchanged(tmp_path: Path) -> None:
    hub = tmp_path
    ws_id, _ = _capture_one(hub)
    path = pe.ledger_path(hub)
    before = path.read_bytes()
    event, _ = pe.build_event(
        event_kind="focus_feedback",
        stream_id=ws_id,
        prev_event_id="",
        recorded_at=(T0 + timedelta(days=1)).isoformat(),
        payload={
            "workstream_id": ws_id,
            "action": "resume",
            "note": "",
            "snooze_until": "",
            "review_at": "",
            "trigger_signature": "",
        },
    )

    def reject(_events: list[dict], _diagnostics: dict) -> None:
        raise RuntimeError("precondition rejected")

    with pytest.raises(RuntimeError, match="precondition rejected"):
        pe.append_events(
            path,
            [event],
            recorded_at=(T0 + timedelta(days=1)).isoformat(),
            validate_existing=reject,
        )
    assert path.read_bytes() == before
    assert not pe.lock_path(path).exists()


def test_concurrent_sovereignty_transitions_validate_under_append_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registered = pw.register_project(tmp_path, "LawFirm OS", now=T0)
    project_id = registered["project_id"]
    workers_ready = Barrier(2)
    legacy_reads_ready = Barrier(2)
    original_read_events = pw.read_events

    # This barrier makes the former read-before-lock implementation fail
    # deterministically: both callers validate the same pre-transition state.
    # The fixed implementation does not call this alias; it reads and validates
    # inside portfolio_events.append_events while that function owns the lock.
    def synchronize_legacy_read(path: Path):
        result = original_read_events(path)
        if current_thread().name.startswith("sovereignty-race"):
            legacy_reads_ready.wait(timeout=5)
        return result

    monkeypatch.setattr(pw, "read_events", synchronize_legacy_read)

    def transition(index: int) -> dict:
        workers_ready.wait(timeout=5)
        return pw.record_sovereignty(
            tmp_path,
            project_id,
            "dad_governed_child",
            decided_by=f"reviewer-{index}",
            approval_ref=f"approval-{index}",
            now=T0 + timedelta(minutes=index + 1),
        )

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="sovereignty-race") as pool:
        results = list(pool.map(transition, range(2)))

    assert sorted(result["status"] for result in results) == [
        "illegal_transition",
        "recorded",
    ]
    assert sum(int(result["events_appended"]) for result in results) == 1
    events, diagnostics = pe.read_events(pe.ledger_path(tmp_path))
    assert not diagnostics["problems"]
    sovereignty_events = [
        event for event in events if event["event_kind"] == "sovereignty_recorded"
    ]
    assert len(sovereignty_events) == 1


def test_multi_idea_capture_is_one_transactional_append(tmp_path: Path) -> None:
    hub = tmp_path
    result = pw.capture_ideas(
        hub, ["idea one parser cache", "idea two cache benchmarks"], conversation_id="c1", now=T0
    )
    assert result["events_appended"] == 4  # 2 ideas + 2 workstreams, one buffer
    state = pw.load_state(hub, now=T0)
    assert state["summary"]["idea_count"] == 2 and state["summary"]["workstream_count"] == 2


# ---------------------------------------------------------------------------
# Lifecycle: last-event-wins, terminal states
# ---------------------------------------------------------------------------


def test_resume_then_snooze_is_snoozed(tmp_path: Path) -> None:
    hub = tmp_path
    ws_id, _ = _capture_one(hub)
    pw.record_feedback(hub, ws_id, "resume", now=T0 + timedelta(days=1))
    pw.record_feedback(hub, ws_id, "snooze", snooze_days=10, now=T0 + timedelta(days=2))
    state = pw.load_state(hub, now=T0 + timedelta(days=3))
    assert state["workstreams"][0]["lifecycle_state"] == "snoozed"
    item = next(f for f in state["focus_queue"] if f["workstream_id"] == ws_id)
    assert item["priority"] == 0 and any("snoozed until" in r for r in item["suppressed_reasons"])


def test_snooze_then_resume_is_active(tmp_path: Path) -> None:
    hub = tmp_path
    ws_id, _ = _capture_one(hub)
    pw.record_feedback(hub, ws_id, "snooze", snooze_days=10, now=T0 + timedelta(days=1))
    pw.record_feedback(hub, ws_id, "resume", now=T0 + timedelta(days=2))
    state = pw.load_state(hub, now=T0 + timedelta(days=3))
    assert state["workstreams"][0]["lifecycle_state"] == "active"


def test_terminal_states_reachable_and_reopenable(tmp_path: Path) -> None:
    hub = tmp_path
    ws_id, _ = _capture_one(hub)
    pw.record_feedback(hub, ws_id, "archive", now=T0 + timedelta(days=1))
    state = pw.load_state(hub, now=T0 + timedelta(days=2))
    assert state["workstreams"][0]["lifecycle_state"] == "archived"
    pw.record_feedback(hub, ws_id, "snooze", snooze_days=5, now=T0 + timedelta(days=3))
    state = pw.load_state(hub, now=T0 + timedelta(days=4))
    assert state["workstreams"][0]["lifecycle_state"] == "archived"  # illegal, ignored
    assert any("illegal_transition" in p for p in state["ledger_diagnostics"]["fold_problems"])
    pw.record_feedback(hub, ws_id, "resume", now=T0 + timedelta(days=5))
    state = pw.load_state(hub, now=T0 + timedelta(days=6))
    assert state["workstreams"][0]["lifecycle_state"] == "active"


def test_merge_and_supersede_verbs_reach_their_states(tmp_path: Path) -> None:
    hub = tmp_path
    r = pw.capture_ideas(hub, ["idea one parser cache", "idea two cache benchmarks"], conversation_id="c1", now=T0)
    ws_a = r["proposals"][0]["workstream_id"]
    ws_b = r["proposals"][1]["workstream_id"]
    pw.record_feedback(hub, ws_a, "merge", now=T0 + timedelta(days=1))
    pw.record_feedback(hub, ws_b, "supersede", now=T0 + timedelta(days=1))
    board = pw.load_state(hub, now=T0 + timedelta(days=2))["board"]
    assert {c["workstream_id"] for c in board["merged"]} == {ws_a}
    assert {c["workstream_id"] for c in board["superseded"]} == {ws_b}


# ---------------------------------------------------------------------------
# Attention: incubation, cooldown, convergence, Today cap, ordering
# ---------------------------------------------------------------------------


def test_incubation_is_silent_until_review_date(tmp_path: Path) -> None:
    hub = tmp_path
    ws_id, _ = _capture_one(hub)
    pw.record_feedback(hub, ws_id, "incubate", review_days=10, now=T0 + timedelta(days=1))
    state = pw.load_state(hub, now=T0 + timedelta(days=5))
    item = next(f for f in state["focus_queue"] if f["workstream_id"] == ws_id)
    assert item["priority"] == 0 and any("incubating" in r for r in item["suppressed_reasons"])
    state = pw.load_state(hub, now=T0 + timedelta(days=12))
    item = next(f for f in state["focus_queue"] if f["workstream_id"] == ws_id)
    assert item["trigger_kind"] == "incubation_review" and item["priority"] > 0


def test_dismiss_cooldown_then_resurface(tmp_path: Path) -> None:
    hub = tmp_path
    ws_id, _ = _capture_one(hub)
    state = pw.load_state(hub, now=T0 + timedelta(days=8))
    item = next(f for f in state["focus_queue"] if f["workstream_id"] == ws_id)
    assert item["trigger_kind"] == "weekly_decision"
    pw.record_feedback(
        hub, ws_id, "dismiss", trigger_signature=item["trigger_signature"], now=T0 + timedelta(days=8)
    )
    state = pw.load_state(hub, now=T0 + timedelta(days=9))
    item = next(f for f in state["focus_queue"] if f["workstream_id"] == ws_id)
    assert item["priority"] == 0 and any("dismissed within" in r for r in item["suppressed_reasons"])
    state = pw.load_state(hub, now=T0 + timedelta(days=13))
    item = next(f for f in state["focus_queue"] if f["workstream_id"] == ws_id)
    assert item["priority"] > 0  # cooldown over, one dismissal is not suppression


def test_repeated_dismissal_converges_to_decision_proposal(tmp_path: Path) -> None:
    hub = tmp_path
    ws_id, _ = _capture_one(hub)
    for day in (8, 12, 16):
        state = pw.load_state(hub, now=T0 + timedelta(days=day))
        item = next(f for f in state["focus_queue"] if f["workstream_id"] == ws_id)
        pw.record_feedback(
            hub, ws_id, "dismiss", trigger_signature=item["trigger_signature"], now=T0 + timedelta(days=day)
        )
    state = pw.load_state(hub, now=T0 + timedelta(days=17))
    item = next(f for f in state["focus_queue"] if f["workstream_id"] == ws_id)
    assert item["trigger_kind"] == "decision_proposed"
    assert "Dismissed 3 time(s)" in item["reasons"][0]
    pw.record_feedback(hub, ws_id, "incubate", review_days=30, now=T0 + timedelta(days=17))
    state = pw.load_state(hub, now=T0 + timedelta(days=18))
    item = next(f for f in state["focus_queue"] if f["workstream_id"] == ws_id)
    assert item["priority"] == 0  # accepted decision ends the reminders


def test_blocker_interrupt_is_immune_to_dismissal(tmp_path: Path) -> None:
    hub = tmp_path
    ws_id, _ = _capture_one(hub)
    pw.record_capsule(hub, ws_id, blocker="waiting on API keys", next_action="ping vendor", now=T0)
    for day in (1, 2, 3, 4):
        pw.record_feedback(hub, ws_id, "dismiss", now=T0 + timedelta(days=day))
    state = pw.load_state(hub, now=T0 + timedelta(days=5))
    item = next(f for f in state["focus_queue"] if f["workstream_id"] == ws_id)
    assert item["trigger_kind"] == "blocker" and item["tier"] == "interrupt"


def test_today_capped_at_three_with_deterministic_tie_order(tmp_path: Path) -> None:
    hub = tmp_path
    texts = [
        "alpha widget lattice",
        "beta quantum lattice",
        "gamma raster harmonics",
        "delta vector harmonics",
        "epsilon tensor doodads",
    ]
    for index, text in enumerate(texts):
        pw.capture_ideas(hub, [text], conversation_id=f"c{index}", now=T0)
    state = pw.load_state(hub, now=T0 + timedelta(days=9))
    surfaced = [f for f in state["focus_queue"] if f["priority"] > 0]
    assert len(surfaced) == 5
    assert len(state["today"]) == 3
    assert state["summary"]["today_item_count"] == 3
    expected = sorted(surfaced, key=lambda i: (-i["priority"], i["last_activity_at"], i["workstream_id"]))
    assert [i["workstream_id"] for i in state["today"]] == [i["workstream_id"] for i in expected[:3]]
    again = pw.load_state(hub, now=T0 + timedelta(days=9))
    assert json.dumps(state, sort_keys=True) == json.dumps(again, sort_keys=True)


def test_pause_reason_and_next_action_stay_silent(tmp_path: Path) -> None:
    hub = tmp_path
    ws_id, _ = _capture_one(hub)
    pw.record_capsule(hub, ws_id, pause_reason="waiting for design review", now=T0)
    state = pw.load_state(hub, now=T0 + timedelta(days=30))
    item = next(f for f in state["focus_queue"] if f["workstream_id"] == ws_id)
    assert item["priority"] == 0
    assert state["workstreams"][0]["lifecycle_state"] == "paused"


# ---------------------------------------------------------------------------
# Relationship classification fixtures
# ---------------------------------------------------------------------------


def _single_target(text: str, *, mature: bool = False) -> list[pr.RelationTarget]:
    return [
        pr.RelationTarget(
            target_kind="workstream", target_id="dad:ws:T", target_label="prior", text=text, mature=mature
        )
    ]


def test_relationship_fixture_matrix() -> None:
    prior = "rust parser cache for tokenizer speedup"
    cases = [
        ("finish the rust parser cache tokenizer speedup work", "continuation"),
        ("rust parser cache for tokenizer speedup", "duplicate"),
        ("prototype an alternative rust parser cache tokenizer benchmark", "experiment"),
        ("scrap the rust parser cache tokenizer approach and revert", "contradiction"),
        ("rust tokenizer grammar visualizer for teaching", "sibling"),
    ]
    for idea, expected in cases:
        relations, _ = pr.classify_relations("src", idea, _single_target(prior))
        assert relations, f"no relation for {idea!r}"
        assert relations[0]["relationship_type"] == expected, (
            f"{idea!r} -> {relations[0]['relationship_type']} (expected {expected}); "
            f"score={relations[0]['score']}"
        )
        assert relations[0]["reason"]


def test_weak_mature_overlap_is_sibling_not_continuation() -> None:
    report = {
        "projects": [
            {
                "project_id": "p1",
                "name": "billing-sim",
                "branches": [{"name": "feature/invoice-export", "subject": "invoice export csv generator quarterly"}],
            }
        ]
    }
    targets = pr.targets_from_portfolio_report(report)
    relations, _ = pr.classify_relations("src", "invoice export dashboard widgets", targets)
    assert relations
    assert relations[0]["relationship_type"] == "sibling"  # audit C9: no resume_existing from 2 weak tokens


def test_common_word_without_does_not_force_conflict_interrupt() -> None:
    relations, _ = pr.classify_relations(
        "src",
        "auth flow without extra fields streamlined",
        _single_target("payment audit checklist without gaps"),
    )
    for relation in relations:
        assert relation["relationship_type"] != "contradiction" or relation["score"] >= pr.MARKER_MIN_SCORE


def test_empty_token_idea_reports_coverage_not_divergence() -> None:
    relations, coverage = pr.classify_relations("src", "и и и", _single_target("rust parser cache"))
    assert relations == []
    assert "idea_text_yielded_no_tokens" in coverage


def test_multiple_ideas_one_conversation_relate_and_share_context(tmp_path: Path) -> None:
    hub = tmp_path
    result = pw.capture_ideas(
        hub,
        ["rust parser cache for tokenizer", "rust parser cache benchmarks harness"],
        conversation_id="c1",
        conversation_title="parser planning",
        now=T0,
    )
    second = result["proposals"][1]
    assert second["relations"], "co-captured ideas must see each other (audit C10)"
    assert second["relations"][0]["target_kind"] == "co_captured_idea"
    assert "captured together" in second["relations"][0]["reason"]
    state = pw.load_state(hub, now=T0)
    conv = state["conversations"][0]
    assert conv["title"] == "parser planning" and len(conv["idea_ids"]) == 2


# ---------------------------------------------------------------------------
# Dependencies, board, sprawl
# ---------------------------------------------------------------------------


def test_dependency_rollup_finds_bottleneck_and_suppresses_downstream(tmp_path: Path) -> None:
    hub = tmp_path
    r = pw.capture_ideas(
        hub,
        ["alpha kernel scheduler", "beta driver harness", "gamma release packaging", "delta docs sweep"],
        conversation_id="c1",
        now=T0,
    )
    ws = [p["workstream_id"] for p in r["proposals"]]
    pw.record_binding(
        hub,
        ws[0],
        "blocks",
        ws[1],
        assertion_status="accepted",
        asserted_by="human",
        approval_ref="test:dependency:a-b",
        now=T0,
    )
    pw.record_binding(
        hub,
        ws[1],
        "blocks",
        ws[2],
        assertion_status="accepted",
        asserted_by="human",
        approval_ref="test:dependency:b-c",
        now=T0 + timedelta(minutes=1),
    )
    state = pw.load_state(hub, now=T0 + timedelta(days=9))
    bottleneck = state["dependencies"]["bottlenecks"][0]
    assert bottleneck["workstream_id"] == ws[0] and bottleneck["blocking_count"] == 2
    downstream = next(f for f in state["focus_queue"] if f["workstream_id"] == ws[1])
    assert downstream["priority"] == 0
    assert any("waiting on upstream" in r_ for r_ in downstream["suppressed_reasons"])
    top = next(f for f in state["focus_queue"] if f["workstream_id"] == ws[0])
    assert any("unblocks 2" in r_ for r_ in top["reasons"])
    pw.record_feedback(hub, ws[0], "archive", now=T0 + timedelta(days=10))
    state = pw.load_state(hub, now=T0 + timedelta(days=11))
    assert (
        not state["dependencies"]["bottlenecks"]
        or state["dependencies"]["bottlenecks"][0]["workstream_id"] == ws[1]
    )


def test_dependency_binding_requires_known_target(tmp_path: Path) -> None:
    hub = tmp_path
    ws_id, _ = _capture_one(hub)
    result = pw.record_binding(hub, ws_id, "depends_on", "dad:portfolio-workstream:missing", now=T0)
    assert result["status"] == "unknown_dependency_target" and result["events_appended"] == 0


def test_sprawl_cluster_reports_untended_siblings(tmp_path: Path) -> None:
    hub = tmp_path
    pw.capture_ideas(
        hub,
        [
            "graph cache warm layer for queries",
            "graph cache warm layer for reports",
            "graph cache warm layer for exports",
        ],
        conversation_id="c1",
        now=T0,
    )
    state = pw.load_state(hub, now=T0 + timedelta(days=5))
    assert state["sprawl_clusters"], "three untended siblings should cluster"
    assert len(state["sprawl_clusters"][0]["workstream_ids"]) == 3
    ws_id = state["sprawl_clusters"][0]["workstream_ids"][0]
    pw.record_capsule(hub, ws_id, next_action="pick this one, merge the rest", now=T0 + timedelta(days=5))
    state = pw.load_state(hub, now=T0 + timedelta(days=6))
    assert not state["sprawl_clusters"] or len(state["sprawl_clusters"][0]["workstream_ids"]) == 2


# ---------------------------------------------------------------------------
# Refresh (M8) and outputs
# ---------------------------------------------------------------------------


def test_refresh_reports_today_changed_only_on_change(tmp_path: Path) -> None:
    hub = tmp_path
    _capture_one(hub)
    first = pw.refresh(hub, now=T0 + timedelta(days=9))
    assert first["today_changed"] is True and first["today_count"] == 1
    second = pw.refresh(hub, now=T0 + timedelta(days=9))
    assert second["today_changed"] is False
    state = pw.load_state(hub, now=T0 + timedelta(days=9))
    ws_id = state["workstreams"][0]["workstream_id"]
    pw.record_feedback(hub, ws_id, "snooze", snooze_days=30, now=T0 + timedelta(days=9))
    third = pw.refresh(hub, now=T0 + timedelta(days=10))
    assert third["today_changed"] is True and third["today_count"] == 0


# ---------------------------------------------------------------------------
# Schema conformance and boundaries
# ---------------------------------------------------------------------------


def test_state_conforms_to_registered_schema(tmp_path: Path) -> None:
    hub = tmp_path
    r = pw.capture_ideas(
        hub, ["alpha kernel scheduler", "alpha kernel scheduler benchmarks"], conversation_id="c1", now=T0
    )
    ws = [p["workstream_id"] for p in r["proposals"]]
    pw.record_capsule(hub, ws[0], next_action="write the fixture", blocker="", now=T0)
    pw.record_binding(
        hub,
        ws[0],
        "blocks",
        ws[1],
        assertion_status="accepted",
        asserted_by="human",
        approval_ref="test:schema:dependency",
        now=T0,
    )
    pw.record_feedback(hub, ws[1], "dismiss", now=T0 + timedelta(days=1))
    state = pw.load_state(hub, now=T0 + timedelta(days=9))
    _validator(ROOT / "schemas" / "portfolio-workstream-state.schema.json").validate(state)


def test_ledger_events_conform_to_envelope_schema(tmp_path: Path) -> None:
    hub = tmp_path
    r = pw.capture_ideas(hub, ["alpha kernel scheduler"], conversation_id="c1", now=T0)
    ws_id = r["proposals"][0]["workstream_id"]
    pw.record_capsule(hub, ws_id, next_action="x", now=T0)
    pw.record_feedback(hub, ws_id, "snooze", snooze_days=2, now=T0 + timedelta(days=1))
    pw.record_binding(hub, ws_id, "repo", "gatehouse", now=T0 + timedelta(days=2))
    validator = _validator(ROOT / "schemas" / "portfolio-workstream-event.schema.json")
    lines = pe.ledger_path(hub).read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 5
    for line in lines:
        validator.validate(json.loads(line))


def test_schemas_are_registered() -> None:
    registry = json.loads((ROOT / "registry" / "schema-registry.json").read_text(encoding="utf-8"))
    assert registry["schemas"]["portfolio_execution_control_event"] == "schemas/portfolio-execution-control-event.schema.json"
    assert registry["schemas"]["portfolio_workstream_state"] == "schemas/portfolio-workstream-state.schema.json"
    assert registry["schemas"]["portfolio_workstream_event"] == "schemas/portfolio-workstream-event.schema.json"


def test_kernel_modules_never_touch_git_or_network() -> None:
    src = ROOT / "src" / "digital_asset_directory"
    for name in ("portfolio_events.py", "portfolio_execution.py", "portfolio_relations.py", "portfolio_attention.py", "portfolio_workstreams.py"):
        text = (src / name).read_text(encoding="utf-8")
        for forbidden in ("subprocess", "os.system", "socket", "urllib", "requests", "http.client"):
            assert forbidden not in text, f"{name} references {forbidden}"


def test_unknown_workstream_commands_fail_closed(tmp_path: Path) -> None:
    hub = tmp_path
    for result in (
        pw.record_capsule(hub, "dad:portfolio-workstream:missing", next_action="x", now=T0),
        pw.record_feedback(hub, "dad:portfolio-workstream:missing", "resume", now=T0),
        pw.record_binding(hub, "dad:portfolio-workstream:missing", "repo", "r", now=T0),
    ):
        assert result["status"] == "unknown_workstream" and result["events_appended"] == 0
