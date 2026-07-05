from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from textwrap import dedent

import pytest
from jsonschema.validators import validator_for
from typer.testing import CliRunner

import digital_asset_directory.cli as cli_module
from digital_asset_directory.cli import app
from digital_asset_directory.mail_center import compose_mail, diagnose_mail_dirty_state
from digital_asset_directory.rust_rollout.apply import apply_rust_rollout_scaffold
from digital_asset_directory.rust_rollout import mail_packets as rust_mail_packets
from digital_asset_directory.rust_rollout.lesson_capture import (
    append_rust_rollout_lesson,
    summarize_rust_rollout_lessons,
)
from digital_asset_directory.rust_rollout.mail_packets import build_rust_rollout_mail_packets
from digital_asset_directory.rust_rollout.planner import build_rust_rollout_plan, write_rust_rollout_plan
from digital_asset_directory.rust_rollout.policy import (
    can_apply_forced_rollout,
    is_logos_repo,
    load_rust_repo_records,
    rollout_mode,
)


ROOT = Path(__file__).resolve().parents[1]
RUNNER = CliRunner()


def _make_hub(path: Path) -> Path:
    (path / "registry").mkdir(parents=True)
    (path / "registry" / "source-of-truth.json").write_text("{}", encoding="utf-8")
    (path / "src" / "digital_asset_directory").mkdir(parents=True)
    (path / "src" / "digital_asset_directory" / "cli.py").write_text("", encoding="utf-8")
    (path / "AI_FRONT_DOOR.md").write_text("# AI Front Door\n", encoding="utf-8")
    (path / "MACHINE_NAVIGATION_MANIFEST.json").write_text(
        '{"manifest_version":"test"}\n', encoding="utf-8"
    )
    (path / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "digital-asset-directory"',
                'version = "0.1.0"',
                "[project.scripts]",
                'asset-dir = "digital_asset_directory.cli:app"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (path / "config").mkdir()
    (path / "config" / "sources.example.yaml").write_text(
        "project:\n  database: state/catalog.sqlite3\n", encoding="utf-8"
    )
    return path


def _validate_mail(payload: dict) -> None:
    schema = json.loads((ROOT / "schemas" / "mail-message.schema.json").read_text())
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema).validate(payload)


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "repo_rust_status.yaml"
    path.write_text(
        dedent(
            """
            schema_version: dad_rust_adoption_matrix.v1
            repos:
              - repo: Digital-Assett-Directory
                repo_name: Digital-Assett-Directory
                local_path: dad
                active_status: active
                rollout_enabled: true
                rust_status: immediate
                priority: 1
                first_rust_slice: "tools/dad_scan_core: local scanner"
                target_repo_owns_rust_files: true
              - repo: logos-scripture-graph
                repo_name: logos-scripture-graph
                local_path: logos
                active_status: active
                rollout_enabled: true
                rust_status: immediate
                priority: 2
                first_rust_slice: "expand existing scanner"
              - repo: missing-path-repo
                repo_name: missing-path-repo
                active_status: active
                rollout_enabled: true
                rust_status: high_next
                priority: 3
                first_rust_slice: "tools/missing_core"
              - repo: archived-repo
                repo_name: archived-repo
                local_path: archived
                active_status: archived
                rollout_enabled: true
                rust_status: high_next
                priority: 4
                first_rust_slice: "tools/archived_core"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def test_logos_policy_is_case_insensitive_and_force_independent(tmp_path: Path) -> None:
    assert is_logos_repo("LAIRCA-Logos-Grounded-Theological-Model")
    assert rollout_mode("logos-scripture-graph") == "instruction_mail_only"
    assert rollout_mode("Digital-Assett-Directory") == "dad_forced_implementation"
    assert rollout_mode("") == "unknown_review_required"

    records = load_rust_repo_records(_config(tmp_path))
    logos = next(record for record in records if record.repo == "logos-scripture-graph")
    decision = can_apply_forced_rollout(logos)

    assert decision.can_apply is False
    assert "logos" in decision.block_reason
    assert decision.instruction_mail_required is True


def test_missing_path_and_archived_repos_block_forced_rollout(tmp_path: Path) -> None:
    records = load_rust_repo_records(_config(tmp_path))
    missing = next(record for record in records if record.repo == "missing-path-repo")
    archived = next(record for record in records if record.repo == "archived-repo")

    assert can_apply_forced_rollout(missing).block_reason == "missing configured local_path"
    assert "active_status blocks rollout" in can_apply_forced_rollout(archived).block_reason


def test_target_repo_must_own_rust_files_to_apply(tmp_path: Path) -> None:
    config = tmp_path / "repo_rust_status.yaml"
    config.write_text(
        dedent(
            """
            schema_version: dad_rust_adoption_matrix.v1
            repos:
              - repo: shared-rust-owner
                repo_name: shared-rust-owner
                local_path: target
                active_status: active
                rollout_enabled: true
                rust_status: high_next
                priority: 1
                first_rust_slice: "tools/shared_core"
                target_repo_owns_rust_files: false
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    record = load_rust_repo_records(config)[0]
    decision = can_apply_forced_rollout(record)

    assert decision.can_apply is False
    assert "target_repo_owns_rust_files" in decision.block_reason


def test_rollout_plan_and_mail_packets_are_deterministic_local_artifacts(tmp_path: Path) -> None:
    config = _config(tmp_path)
    plan = build_rust_rollout_plan(config)

    assert plan["repo_count"] == 4
    assert [row["repo"] for row in plan["forced_rollout_eligible"]] == [
        "Digital-Assett-Directory"
    ]
    assert [row["repo"] for row in plan["logos_instruction_mail_only"]] == [
        "logos-scripture-graph"
    ]

    written = write_rust_rollout_plan(config, tmp_path / "reports")
    assert (tmp_path / "reports" / "rollout_plan.json").exists()
    assert len(written["written"]) == 4
    assert not Path(written["plan"]["config_path"]).is_absolute()

    mail = build_rust_rollout_mail_packets(config, tmp_path / "mail")
    assert mail["packet_count"] == 4
    logos_packet = json.loads((tmp_path / "mail" / "logos" / "logos-scripture-graph.json").read_text())
    non_logos_packet = json.loads(
        (tmp_path / "mail" / "non_logos" / "digital-assett-directory.json").read_text()
    )
    _validate_mail(logos_packet)
    _validate_mail(non_logos_packet)
    assert logos_packet["message_type"] == "capability_suggestion"
    assert logos_packet["payload"]["rust_rollout_packet_type"] == "rust_logos_instruction_only"
    assert logos_packet["review_status"] == "generated_candidate"
    assert logos_packet["sensitivity"] == "internal"
    assert logos_packet["source_provenance"]["source_repo_id"] == "dad"
    assert logos_packet["source_provenance"]["collected_by"] == ""
    assert logos_packet["source_provenance"]["collected_at"] == ""
    assert logos_packet["public_release"]["public_release_required"] is True
    assert logos_packet["public_release"]["public_release_status"] == "pending_human"
    assert non_logos_packet["message_type"] == "capability_suggestion"
    assert non_logos_packet["payload"]["rust_rollout_packet_type"] == "rust_forced_rollout_candidate"
    assert non_logos_packet["payload"]["delivery_status"] == "staged_not_deliverable"
    assert non_logos_packet["payload"]["requires_target_policy_review"] is True
    assert non_logos_packet["payload"]["external_send_performed"] is False
    assert non_logos_packet["payload"]["github_write_performed"] is False


def test_mail_packet_identity_changes_when_recommendation_changes(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first = build_rust_rollout_mail_packets(config, tmp_path / "mail-a")
    first_packet = next(
        packet
        for packet in first["packets"]
        if packet["target_repo"] == "Digital-Assett-Directory"
    )

    text = config.read_text(encoding="utf-8")
    config.write_text(
        text.replace(
            'first_rust_slice: "tools/dad_scan_core: local scanner"',
            'first_rust_slice: "tools/dad_scan_core_manifest_lint"',
        ),
        encoding="utf-8",
    )
    second = build_rust_rollout_mail_packets(config, tmp_path / "mail-b")
    second_packet = next(
        packet
        for packet in second["packets"]
        if packet["target_repo"] == "Digital-Assett-Directory"
    )

    assert second_packet["thread_id"] == first_packet["thread_id"]
    assert second_packet["mail_id"] != first_packet["mail_id"]
    assert second_packet["dedupe_key"] != first_packet["dedupe_key"]
    assert (
        second_packet["payload"]["rust_rollout_revision_id"]
        != first_packet["payload"]["rust_rollout_revision_id"]
    )


def test_mail_doctor_allows_same_rust_packet_in_staging_and_reference(
    tmp_path: Path,
) -> None:
    hub = tmp_path / "dad"
    config = _config(tmp_path)
    tracked = hub / "mail" / "outbox" / "rust_rollout"
    staged = hub / "processed" / "mail" / "staged" / "rust_rollout"
    build_rust_rollout_mail_packets(config, tracked)
    build_rust_rollout_mail_packets(config, staged)

    doctor = diagnose_mail_dirty_state(hub)

    assert doctor["dirty"] is False
    assert doctor["summary"]["rust_invalid_packet_count"] == 0
    assert any(
        item["observation_type"] == "rust_rollout_staged_reference_same_identity"
        for item in doctor["observations"]
    )


def test_mail_doctor_blocks_stale_rust_packet_semantic_identity_conflict(
    tmp_path: Path,
) -> None:
    hub = tmp_path / "dad"
    config = _config(tmp_path)
    tracked = hub / "mail" / "outbox" / "rust_rollout"
    staged = hub / "processed" / "mail" / "staged" / "rust_rollout"
    build_rust_rollout_mail_packets(config, tracked)
    text = config.read_text(encoding="utf-8")
    config.write_text(
        text.replace(
            'first_rust_slice: "tools/dad_scan_core: local scanner"',
            'first_rust_slice: "tools/dad_scan_core_manifest_lint"',
        ),
        encoding="utf-8",
    )
    build_rust_rollout_mail_packets(config, staged)

    doctor = diagnose_mail_dirty_state(hub)

    assert doctor["dirty"] is True
    assert "rust_rollout_semantic_identity_conflict" in {
        issue["issue_type"] for issue in doctor["issues"]
    }


def test_mail_packet_build_skips_unchanged_rewrites(monkeypatch, tmp_path: Path) -> None:
    config = _config(tmp_path)
    out_dir = tmp_path / "mail"
    first = build_rust_rollout_mail_packets(config, out_dir)

    assert first["write_counts"]["written"] == 5

    def fail_write_json(path: Path, packet: dict[str, object]) -> None:
        raise AssertionError(f"unchanged packet should not be rewritten: {path}")

    monkeypatch.setattr(rust_mail_packets, "write_json", fail_write_json)
    second = rust_mail_packets.build_rust_rollout_mail_packets(config, out_dir)

    assert second["write_counts"] == {"written": 0, "unchanged": 5}


def test_mail_packet_build_blocks_stale_output_files(tmp_path: Path) -> None:
    config = _config(tmp_path)
    out_dir = tmp_path / "mail"
    stale = out_dir / "non_logos" / "obsolete-repo.json"
    stale.parent.mkdir(parents=True)
    stale.write_text('{"mail_id":"stale"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="obsolete-repo.json"):
        build_rust_rollout_mail_packets(config, out_dir)


def test_cli_rust_rollout_build_mail_blocks_live_mail_dirt_even_with_ack(
    tmp_path: Path,
) -> None:
    hub = _make_hub(tmp_path / "dad")
    source = tmp_path / "source"
    out_dir = tmp_path / "staged-mail"
    source.mkdir()
    config = _config(tmp_path)
    compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Dirty central mail should block default Rust packet regeneration.",
    )
    packet = json.loads(
        (source / ".digital-asset" / "mail" / "outbox.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    central = hub / "processed" / "mail" / "inbox" / "direct.jsonl"
    central.parent.mkdir(parents=True)
    central.write_text(json.dumps(packet) + "\n", encoding="utf-8")

    blocked = RUNNER.invoke(
        app,
        [
            "rust-rollout",
            "build-mail",
            "--config",
            str(config),
            "--out-dir",
            str(out_dir),
            "--hub",
            str(hub),
        ],
    )

    assert blocked.exit_code == 2
    blocked_payload = json.loads(blocked.output)
    assert blocked_payload["operation"] == "rust-rollout build-mail"
    assert blocked_payload["blocked"] is True
    assert not out_dir.exists()

    still_blocked = RUNNER.invoke(
        app,
        [
            "rust-rollout",
            "build-mail",
            "--config",
            str(config),
            "--out-dir",
            str(out_dir),
            "--dirty-state-ack",
            "regenerate staged packets after reviewing dirty mail report",
            "--hub",
            str(hub),
        ],
    )

    assert still_blocked.exit_code == 2
    still_blocked_payload = json.loads(still_blocked.output)
    assert still_blocked_payload["dirty_ack_rejected"] is True
    assert "central_inbox_uncollected_row" in still_blocked_payload["disallowed_issue_types"]
    assert not out_dir.exists()


def test_cli_rust_rollout_build_mail_ack_requires_matching_dirty_fingerprint(
    tmp_path: Path,
) -> None:
    hub = _make_hub(tmp_path / "dad")
    source = tmp_path / "source"
    out_dir = tmp_path / "staged-mail"
    source.mkdir()
    config = _config(tmp_path)
    packet = compose_mail(
        source,
        message_type="capability_suggestion",
        target_repo="repo",
        summary="Rust reference packet has stale delivery status.",
    )["record"]
    packet["payload"]["delivery_status"] = "delivered"
    rust_reference = hub / "mail" / "outbox" / "rust_rollout" / "non_logos" / "repo.json"
    rust_reference.parent.mkdir(parents=True)
    rust_reference.write_text(json.dumps(packet) + "\n", encoding="utf-8")

    missing_fingerprint = RUNNER.invoke(
        app,
        [
            "rust-rollout",
            "build-mail",
            "--config",
            str(config),
            "--out-dir",
            str(out_dir),
            "--dirty-state-ack",
            "regenerate staged packets after reviewing dirty Rust packet report",
            "--hub",
            str(hub),
        ],
    )

    assert missing_fingerprint.exit_code == 2
    missing_payload = json.loads(missing_fingerprint.output)
    assert missing_payload["dirty_ack_rejected"] is True
    assert missing_payload["dirty_state_fingerprint_required"] is True
    dirty_fingerprint = missing_payload["dirty_state_fingerprint"]
    assert dirty_fingerprint.startswith("sha256:")
    assert not out_dir.exists()

    stale_fingerprint = RUNNER.invoke(
        app,
        [
            "rust-rollout",
            "build-mail",
            "--config",
            str(config),
            "--out-dir",
            str(out_dir),
            "--dirty-state-ack",
            "regenerate staged packets after reviewing dirty Rust packet report",
            "--dirty-state-fingerprint",
            "sha256:stale",
            "--hub",
            str(hub),
        ],
    )

    assert stale_fingerprint.exit_code == 2
    stale_payload = json.loads(stale_fingerprint.output)
    assert stale_payload["dirty_ack_rejected"] is True
    assert stale_payload["provided_dirty_state_fingerprint"] == "sha256:stale"
    assert stale_payload["expected_dirty_state_fingerprint"] == dirty_fingerprint
    assert not out_dir.exists()

    allowed = RUNNER.invoke(
        app,
        [
            "rust-rollout",
            "build-mail",
            "--config",
            str(config),
            "--out-dir",
            str(out_dir),
            "--dirty-state-ack",
            "regenerate staged packets after reviewing dirty Rust packet report",
            "--dirty-state-fingerprint",
            dirty_fingerprint,
            "--hub",
            str(hub),
        ],
    )

    assert allowed.exit_code == 0
    allowed_payload = json.loads(allowed.output)
    assert allowed_payload["packet_count"] == 4
    assert allowed_payload["mail_dirty_check"]["bypassed"] is True
    assert "dirty Rust packet" in allowed_payload["mail_dirty_check"]["dirty_state_ack"]
    assert allowed_payload["mail_dirty_check"]["dirty_state_fingerprint"] == dirty_fingerprint
    assert (out_dir / "README.md").exists()
    bypass_log = hub / "processed" / "mail" / "archive" / "dirty_gate_bypass.jsonl"
    bypass_rows = [
        json.loads(line)
        for line in bypass_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert bypass_rows[0]["event_type"] == "mail_dirty_gate_bypass"
    assert bypass_rows[0]["operation"] == "rust-rollout build-mail"
    assert bypass_rows[0]["dirty_state_fingerprint"] == dirty_fingerprint
    assert bypass_rows[0]["allowed_dirty_ack_issue_types"] == [
        "rust_rollout_duplicate_packet_identity",
        "rust_rollout_packet_delivery_status",
        "rust_rollout_packet_invalid",
        "rust_rollout_semantic_identity_conflict",
    ]


def test_cli_rust_rollout_build_mail_write_claim_cannot_be_bypassed(
    tmp_path: Path,
) -> None:
    hub = _make_hub(tmp_path / "dad")
    source = tmp_path / "source"
    out_dir = tmp_path / "staged-mail"
    source.mkdir()
    config = _config(tmp_path)
    packet = compose_mail(
        source,
        message_type="capability_suggestion",
        target_repo="repo",
        summary="Rust reference packet claims an external write.",
    )["record"]
    packet["payload"]["delivery_status"] = "staged_not_deliverable"
    packet["payload"]["external_send_performed"] = True
    rust_reference = hub / "mail" / "outbox" / "rust_rollout" / "non_logos" / "repo.json"
    rust_reference.parent.mkdir(parents=True)
    rust_reference.write_text(json.dumps(packet) + "\n", encoding="utf-8")

    result = RUNNER.invoke(
        app,
        [
            "rust-rollout",
            "build-mail",
            "--config",
            str(config),
            "--out-dir",
            str(out_dir),
            "--dirty-state-ack",
            "regenerate staged packets after reviewing dirty Rust packet report",
            "--hub",
            str(hub),
        ],
    )

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["dirty_ack_rejected"] is True
    assert "rust_rollout_packet_write_claim" in payload["disallowed_issue_types"]
    assert not out_dir.exists()


def test_cli_rust_rollout_build_mail_defaults_to_ignored_staging(tmp_path: Path) -> None:
    hub = _make_hub(tmp_path / "dad")
    config = _config(tmp_path)

    result = RUNNER.invoke(
        app,
        [
            "rust-rollout",
            "build-mail",
            "--config",
            str(config),
            "--hub",
            str(hub),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["packet_count"] == 4
    assert payload["out_dir"].replace("\\", "/").endswith(
        "processed/mail/staged/rust_rollout"
    )
    assert (hub / "processed" / "mail" / "staged" / "rust_rollout" / "README.md").exists()
    assert not (hub / "mail" / "outbox" / "rust_rollout" / "README.md").exists()
    assert not (
        hub / "processed" / "mail" / "archive" / "rust_rollout_snapshot_promotion.jsonl"
    ).exists()


def test_cli_rust_rollout_build_mail_rejects_promotion_ack_for_staging(
    tmp_path: Path,
) -> None:
    hub = _make_hub(tmp_path / "dad")
    config = _config(tmp_path)

    result = RUNNER.invoke(
        app,
        [
            "rust-rollout",
            "build-mail",
            "--config",
            str(config),
            "--promote-reference-snapshot-ack",
            "this should not create promotion evidence for staging",
            "--hub",
            str(hub),
        ],
    )

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["schema_version"] == "dad_rust_rollout_snapshot_promotion_scope_gate.v1"
    assert payload["blocked"] is True
    assert "mail/outbox/rust_rollout" in payload["authority_boundary"]
    assert not (
        hub / "processed" / "mail" / "archive" / "rust_rollout_snapshot_promotion.jsonl"
    ).exists()
    assert not (hub / "processed" / "mail" / "staged" / "rust_rollout").exists()


def test_cli_rust_rollout_build_mail_blocks_custom_in_repo_output_root(
    tmp_path: Path,
) -> None:
    hub = _make_hub(tmp_path / "dad")
    config = _config(tmp_path)
    out_dir = hub / "docs" / "rust" / "generated_packets"

    result = RUNNER.invoke(
        app,
        [
            "rust-rollout",
            "build-mail",
            "--config",
            str(config),
            "--out-dir",
            str(out_dir),
            "--hub",
            str(hub),
        ],
    )

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["schema_version"] == "dad_rust_rollout_output_root_gate.v1"
    assert payload["allowed_in_repo_output_roots"] == [
        "processed/mail/staged/rust_rollout",
        "mail/outbox/rust_rollout",
    ]
    assert not out_dir.exists()


def test_cli_rust_rollout_build_mail_blocks_other_repo_output_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _make_hub(tmp_path / "dad")
    config = _config(tmp_path)
    other_repo = tmp_path / "other-repo"
    out_dir = other_repo / ".digital-asset" / "mail" / "rust_rollout"
    other_repo.mkdir()
    monkeypatch.setattr(cli_module, "_system_temp_root", lambda: tmp_path / "safe-temp")

    result = RUNNER.invoke(
        app,
        [
            "rust-rollout",
            "build-mail",
            "--config",
            str(config),
            "--out-dir",
            str(out_dir),
            "--hub",
            str(hub),
        ],
    )

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["schema_version"] == "dad_rust_rollout_external_output_gate.v1"
    assert payload["blocked"] is True
    assert payload["out_dir"].startswith("path-sha256:")
    assert "arbitrary absolute paths" in payload["authority_boundary"]
    assert not out_dir.exists()


@pytest.mark.parametrize(
    "out_dir_parts",
    [
        (".digital-asset", "mail", "rust_rollout"),
        ("processed", "mail", "inbox", "rust_rollout"),
        ("processed", "mail", "outbox", "rust_rollout"),
        ("processed", "mail", "archive", "rust_rollout"),
        ("processed", "mail", "quarantine", "rust_rollout"),
        ("processed", "mail", "releases", "rust_rollout"),
    ],
)
def test_cli_rust_rollout_build_mail_blocks_live_mailbox_targets(
    tmp_path: Path,
    out_dir_parts: tuple[str, ...],
) -> None:
    hub = _make_hub(tmp_path / "dad")
    config = _config(tmp_path)
    out_dir = hub.joinpath(*out_dir_parts)

    result = RUNNER.invoke(
        app,
        [
            "rust-rollout",
            "build-mail",
            "--config",
            str(config),
            "--out-dir",
            str(out_dir),
            "--hub",
            str(hub),
        ],
    )

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["schema_version"] == "dad_rust_rollout_live_mail_target_gate.v1"
    assert payload["blocked"] is True
    assert payload["required_out_dir"] == "processed/mail/staged/rust_rollout"
    assert "must not write generated packets directly into live mailboxes" in payload[
        "authority_boundary"
    ]
    assert not out_dir.exists()


def test_cli_rust_rollout_build_mail_requires_ack_for_tracked_snapshot(
    tmp_path: Path,
) -> None:
    hub = _make_hub(tmp_path / "dad")
    config = _config(tmp_path)
    tracked = hub / "mail" / "outbox" / "rust_rollout"

    blocked = RUNNER.invoke(
        app,
        [
            "rust-rollout",
            "build-mail",
            "--config",
            str(config),
            "--out-dir",
            str(tracked),
            "--hub",
            str(hub),
        ],
    )

    assert blocked.exit_code == 2
    blocked_payload = json.loads(blocked.output)
    assert blocked_payload["required_ack"] == "--promote-reference-snapshot-ack"
    assert not tracked.exists()

    allowed = RUNNER.invoke(
        app,
        [
            "rust-rollout",
            "build-mail",
            "--config",
            str(config),
            "--out-dir",
            str(tracked),
            "--promote-reference-snapshot-ack",
            "reviewed staged diff and intentionally promoted tracked snapshot",
            "--hub",
            str(hub),
        ],
    )

    assert allowed.exit_code == 0
    payload = json.loads(allowed.output)
    assert payload["tracked_reference_snapshot_promotion"]["acknowledged"] is True
    assert "intentionally promoted" in payload["tracked_reference_snapshot_promotion"]["ack"]
    assert (
        payload["tracked_reference_snapshot_promotion"]["audit_log"]
        == "processed/mail/archive/rust_rollout_snapshot_promotion.jsonl"
    )
    assert payload["tracked_reference_snapshot_promotion"]["snapshot_json_file_count"] == 4
    assert (tracked / "README.md").exists()
    audit_rows = [
        json.loads(line)
        for line in (
            hub / "processed" / "mail" / "archive" / "rust_rollout_snapshot_promotion.jsonl"
        )
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert len(audit_rows) == 1
    assert audit_rows[0]["event_type"] == "rust_rollout_reference_snapshot_promoted"
    assert audit_rows[0]["out_dir"] == "mail/outbox/rust_rollout"
    assert audit_rows[0]["packet_count"] == 4
    assert len(audit_rows[0]["packet_manifest"]) == 4
    assert all(item["sha256"].startswith("sha256:") for item in audit_rows[0]["packet_manifest"])
    assert "not delivery" in audit_rows[0]["authority_boundary"]


def test_lesson_append_and_summary(tmp_path: Path) -> None:
    ledger = tmp_path / "lesson_ledger.jsonl"
    lesson = append_rust_rollout_lesson(
        ledger,
        {
            "source_repo": "Digital-Assett-Directory",
            "phase": "phase-1",
            "problem": "fmt failed",
            "observed_failure_or_friction": "cargo fmt --check found generated formatting",
            "fix_or_workaround": "run cargo fmt before check",
            "reusable_pattern": "format generated Rust first",
            "applies_to_repo_types": ["mixed_python_rust_repo"],
            "should_change_future_prompt": True,
            "should_change_future_template": True,
            "confidence": "high",
            "evidence_refs": ["tools/dad_scan_core"],
        },
    )

    assert lesson["lesson_id"].startswith("dad:rust-rollout-lesson:")
    assert lesson["append_status"] == "appended"
    duplicate = append_rust_rollout_lesson(
        ledger,
        {
            "source_repo": "Digital-Assett-Directory",
            "phase": "phase-1",
            "problem": "fmt failed",
            "observed_failure_or_friction": "cargo fmt --check found generated formatting",
            "fix_or_workaround": "run cargo fmt before check",
            "reusable_pattern": "format generated Rust first",
            "applies_to_repo_types": ["mixed_python_rust_repo"],
            "should_change_future_prompt": True,
            "should_change_future_template": True,
            "confidence": "high",
            "evidence_refs": ["tools/dad_scan_core"],
        },
    )
    assert duplicate["append_status"] == "already_present"
    summary = summarize_rust_rollout_lessons(ledger, tmp_path / "reports")
    assert summary["lesson_count"] == 1
    assert (tmp_path / "reports" / "dad_forced_implementation_postflight.md").exists()


def test_rust_rollout_lesson_schema_validates_live_ledger() -> None:
    registry = json.loads((ROOT / "registry" / "schema-registry.json").read_text())
    schema_path = ROOT / registry["schemas"]["rust_rollout_lesson"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)

    ledger_path = ROOT / "lessons" / "rust_rollout" / "lesson_ledger.jsonl"
    rows = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert rows
    for row in rows:
        validator.validate(row)


def test_apply_refuses_logos_and_missing_path_and_writes_owned_scaffold(tmp_path: Path) -> None:
    config = _config(tmp_path)
    records = load_rust_repo_records(config)
    dad_repo = tmp_path / "dad"
    dad_repo.mkdir()
    logos = next(record for record in records if record.repo == "logos-scripture-graph")
    missing = next(record for record in records if record.repo == "missing-path-repo")
    dad = next(record for record in records if record.repo == "Digital-Assett-Directory")

    assert (
        apply_rust_rollout_scaffold(
            repo_root=tmp_path, record=logos, approval_id="dad:approval:test", force=True
        ).status
        == "blocked"
    )
    assert (
        apply_rust_rollout_scaffold(
            repo_root=tmp_path, record=missing, approval_id="dad:approval:test", force=True
        ).status
        == "blocked"
    )

    result = apply_rust_rollout_scaffold(
        repo_root=tmp_path, record=dad, approval_id="dad:approval:test", force=True
    )

    assert result.status == "applied"
    assert result.approval_id == "dad:approval:test"
    assert (dad_repo / "docs" / "rust" / "TARGET_REPO_RUST_OWNERSHIP.md").exists()
    text = (dad_repo / "docs" / "rust" / "TARGET_REPO_RUST_OWNERSHIP.md").read_text()
    assert "Do not depend on a local DAD path" in text
    assert "../Digital-Assett-Directory" not in text


def test_apply_requires_approval_and_sanitizes_crate_name(tmp_path: Path) -> None:
    config = tmp_path / "repo_rust_status.yaml"
    config.write_text(
        dedent(
            """
            schema_version: dad_rust_adoption_matrix.v1
            repos:
              - repo: bad-slice
                repo_name: bad-slice
                local_path: target
                active_status: active
                rollout_enabled: true
                rust_status: high_next
                priority: 1
                first_rust_slice: "tools/../../escape: malicious"
                target_repo_owns_rust_files: true
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    target = tmp_path / "target"
    target.mkdir()
    record = load_rust_repo_records(config)[0]

    missing_approval = apply_rust_rollout_scaffold(repo_root=tmp_path, record=record, force=True)

    assert missing_approval.status == "blocked"
    assert "approval-id" in missing_approval.message

    result = apply_rust_rollout_scaffold(
        repo_root=tmp_path, record=record, approval_id="dad:approval:test", force=True
    )

    assert result.status == "applied"
    assert (target / "tools" / "rust_leaf_tool" / "README.md").exists()
    assert not (tmp_path / "escape").exists()


def test_apply_blocks_dirty_git_target(tmp_path: Path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git is not available")
    config = _config(tmp_path)
    target = tmp_path / "dad"
    target.mkdir()
    subprocess.run(["git", "-C", str(target), "init", "-b", "main"], check=True)
    (target / "uncommitted.txt").write_text("dirty\n", encoding="utf-8")
    record = next(
        record for record in load_rust_repo_records(config) if record.repo == "Digital-Assett-Directory"
    )

    result = apply_rust_rollout_scaffold(
        repo_root=tmp_path, record=record, approval_id="dad:approval:test", force=True
    )

    assert result.status == "blocked"
    assert "dirty" in result.message
