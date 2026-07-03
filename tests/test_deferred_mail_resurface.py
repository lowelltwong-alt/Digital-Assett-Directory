from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_asset_directory.mail_center import resurface_deferred_mail

pytestmark = pytest.mark.integration


def _mailbox_repo(
    tmp_path: Path,
    *,
    intake_decision: str = "save_for_future",
    later_decision: str | None = None,
) -> Path:
    repo = tmp_path / "repo"
    mail_dir = repo / ".digital-asset" / "mail"
    mail_dir.mkdir(parents=True)
    message = {
        "mail_id": "dad:mail:parity-1",
        "thread_id": "dad:thread:parity",
        "message_type": "asset_suggestion",
        "source_repo": "dad",
        "target_repo": str(repo),
        "created_at": "2026-06-01T00:00:00+00:00",
        "dedupe_key": "parity-1",
        "payload": {
            "summary": "Adopt the rust shadow parity timing harness",
            "asset_id": "dad:offering:rust-shadow-parity-harness",
        },
        "evidence": ["assets/coding-harnesses/rust-shadow-parity-harness"],
        "suggested_actions": ["review parity harness"],
    }
    (mail_dir / "inbox.jsonl").write_text(json.dumps(message) + "\n", encoding="utf-8")
    adoption_rows = [
        {
            "adoption_id": "dad:adoption:1",
            "mail_id": "dad:mail:parity-1",
            "repository": str(repo),
            "intake_decision": intake_decision,
            "recorded_at": "2026-06-02T00:00:00+00:00",
            "source_asset_refs": ["dad:offering:rust-shadow-parity-harness"],
        }
    ]
    if later_decision:
        adoption_rows.append(
            {
                "adoption_id": "dad:adoption:2",
                "mail_id": "dad:mail:parity-1",
                "repository": str(repo),
                "intake_decision": later_decision,
                "recorded_at": "2026-06-03T00:00:00+00:00",
                "source_asset_refs": ["dad:offering:rust-shadow-parity-harness"],
            }
        )
    (mail_dir / "adoption.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in adoption_rows), encoding="utf-8"
    )
    return repo


def test_deferred_mail_resurfaces_on_task_match(tmp_path: Path):
    repo = _mailbox_repo(tmp_path)
    result = resurface_deferred_mail(repo, task="improve rust parity timing claims")
    assert result["deferred_total"] == 1
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["mail_id"] == "dad:mail:parity-1"
    assert "parity" in item["matched_terms"]
    assert item["repo_watches_asset"] is False
    assert result["match_basis"]


def test_unrelated_task_does_not_resurface_without_watch_signal(tmp_path: Path):
    repo = _mailbox_repo(tmp_path)
    result = resurface_deferred_mail(repo, task="write markdown release notes")
    assert result["deferred_total"] == 1
    assert result["items"] == []


def test_watched_asset_resurfaces_even_with_unrelated_task(tmp_path: Path):
    repo = _mailbox_repo(tmp_path)
    hub = tmp_path / "hub"
    ledger = hub / "processed" / "usage" / "repo-asset-usage.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(
        json.dumps(
            {
                "usage_id": "u1",
                "repo": str(repo.resolve()).replace("\\", "/"),
                "asset_id": "dad:offering:rust-shadow-parity-harness",
                "status": "watching",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result = resurface_deferred_mail(repo, task="write markdown release notes", hub_root=hub)
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["repo_watches_asset"] is True
    assert item["why_now"] == "repo now uses or watches a referenced asset"


def test_later_triage_decision_supersedes_deferral(tmp_path: Path):
    repo = _mailbox_repo(tmp_path, later_decision="implement_now")
    result = resurface_deferred_mail(repo, task="improve rust parity timing claims")
    assert result["deferred_total"] == 0
    assert result["items"] == []


def test_repo_without_mailbox_fails_soft(tmp_path: Path):
    repo = tmp_path / "bare-repo"
    repo.mkdir()
    result = resurface_deferred_mail(repo, task="anything at all")
    assert result["deferred_total"] == 0
    assert result["items"] == []
