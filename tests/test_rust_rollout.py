from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from textwrap import dedent

import pytest

from digital_asset_directory.rust_rollout.apply import apply_rust_rollout_scaffold
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

    mail = build_rust_rollout_mail_packets(config, tmp_path / "mail")
    assert mail["packet_count"] == 4
    logos_packet = json.loads((tmp_path / "mail" / "logos" / "logos-scripture-graph.json").read_text())
    non_logos_packet = json.loads(
        (tmp_path / "mail" / "non_logos" / "digital-assett-directory.json").read_text()
    )
    assert logos_packet["message_type"] == "capability_suggestion"
    assert logos_packet["payload"]["rust_rollout_packet_type"] == "rust_logos_instruction_only"
    assert non_logos_packet["message_type"] == "capability_suggestion"
    assert non_logos_packet["payload"]["rust_rollout_packet_type"] == "rust_forced_rollout_candidate"
    assert non_logos_packet["payload"]["external_send_performed"] is False
    assert non_logos_packet["payload"]["github_write_performed"] is False


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
    summary = summarize_rust_rollout_lessons(ledger, tmp_path / "reports")
    assert summary["lesson_count"] == 1
    assert (tmp_path / "reports" / "dad_forced_implementation_postflight.md").exists()


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
