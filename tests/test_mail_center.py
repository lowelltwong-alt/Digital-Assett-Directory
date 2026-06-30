from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_asset_directory.mail_center import (
    collect_mail,
    compose_mail,
    deliver_mail,
    digest_mail,
    mail_digest_status,
    route_mail,
    review_mail,
)

pytestmark = pytest.mark.integration


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def test_compose_redacts_secret_like_payload_and_rejects_restricted_mail(tmp_path: Path):
    repo = tmp_path / "repo-a"
    repo.mkdir()

    result = compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Share daily digest guidance.",
        payload={"note": "api_key=super-secret-value should never persist"},
        evidence=["generated unit test"],
        suggested_actions=["Review locally before adopting."],
    )

    assert result["appended"] is True
    assert (repo / ".digital-asset" / "mail" / "README.md").exists()
    records = _jsonl(repo / ".digital-asset" / "mail" / "outbox.jsonl")
    assert len(records) == 1
    assert "super-secret-value" not in json.dumps(records[0])
    assert records[0]["payload"]["redaction_count"] == 1
    assert records[0]["payload"]["note"] == "api_key=[REDACTED] should never persist"

    with pytest.raises(ValueError, match="confidential or restricted"):
        compose_mail(
            repo,
            message_type="lesson_suggestion",
            target_repo="central_only",
            summary="Rejected",
            sensitivity="restricted",
        )


def test_collect_canonicalizes_source_identity_and_redaction(tmp_path: Path):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Original summary",
    )
    outbox = repo / ".digital-asset" / "mail" / "outbox.jsonl"
    spoofed = _jsonl(outbox)[0]
    spoofed["source_repo"] = "C:/pretend/source"
    spoofed["mail_id"] = "dad:mail:spoofed"
    spoofed["dedupe_key"] = "spoofed-key"
    spoofed["payload"]["note"] = "token=very-secret-value"
    outbox.write_text(json.dumps(spoofed) + "\n", encoding="utf-8")

    result = collect_mail(hub, [repo])

    assert result["collected_count"] == 1
    slug = str(repo.resolve()).replace("\\", "/").replace(":", "").replace("/", "__")
    central = _jsonl(hub / "processed" / "mail" / "inbox" / f"{slug}.jsonl")
    assert central[0]["source_repo"] == str(repo.resolve()).replace("\\", "/")
    assert central[0]["mail_id"] != "dad:mail:spoofed"
    assert central[0]["dedupe_key"] != "spoofed-key"
    assert "very-secret-value" not in json.dumps(central[0])


def test_collect_dedupes_same_content_with_changed_packet_ids(tmp_path: Path):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    compose_mail(
        repo,
        message_type="asset_suggestion",
        target_repo="central_only",
        summary="Same content should dedupe.",
    )
    outbox = repo / ".digital-asset" / "mail" / "outbox.jsonl"
    duplicate = _jsonl(outbox)[0]
    duplicate["mail_id"] = "dad:mail:changed"
    duplicate["dedupe_key"] = "changed"
    _append_jsonl(outbox, duplicate)

    result = collect_mail(hub, [repo])

    assert result["collected_count"] == 1
    assert result["duplicate_count"] == 1


def test_collect_rejects_restricted_hand_written_outbox_packet(tmp_path: Path):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    composed = compose_mail(
        repo,
        message_type="governance_notice",
        target_repo="central_only",
        summary="Rejected at collect.",
    )
    outbox = repo / ".digital-asset" / "mail" / "outbox.jsonl"
    packet = composed["record"]
    packet["sensitivity"] = "restricted"
    outbox.write_text(json.dumps(packet) + "\n", encoding="utf-8")

    result = collect_mail(hub, [repo])

    assert result["collected_count"] == 0
    assert result["error_count"] == 1
    assert "confidential or restricted" in result["errors"][0]["error"]


def test_collect_route_deliver_dedupes_duplicate_deliveries(tmp_path: Path):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()

    composed = compose_mail(
        repo_a,
        message_type="workflow_suggestion",
        target_repo=str(repo_b),
        summary="Repo B can use the mail digest workflow.",
        evidence=["repo-a/.digital-asset/mail/outbox.jsonl"],
        suggested_actions=["Run asset-dir mail digest once a day."],
    )

    collected = collect_mail(hub, [repo_a])
    routed = route_mail(hub)
    delivered = deliver_mail(hub, [repo_b])
    delivered_again = deliver_mail(hub, [repo_b])

    assert collected["collected_count"] == 1
    assert routed["routed_count"] == 1
    assert delivered["delivered_count"] == 1
    assert delivered_again["delivered_count"] == 0
    assert delivered_again["acknowledged_duplicate_count"] == 1
    inbox = _jsonl(repo_b / ".digital-asset" / "mail" / "inbox.jsonl")
    archive = _jsonl(repo_b / ".digital-asset" / "mail" / "archive.jsonl")
    assert [item["mail_id"] for item in inbox] == [composed["record"]["mail_id"]]
    assert [item["message_type"] for item in archive] == ["inbox_ack"]


def test_deliver_requires_explicit_repo_allowlist(tmp_path: Path):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    allowed_repo = tmp_path / "repo-allowed"
    outside_repo = tmp_path / "outside-existing-repo"
    hub.mkdir()
    repo_a.mkdir()
    allowed_repo.mkdir()
    outside_repo.mkdir()

    compose_mail(
        repo_a,
        message_type="workflow_suggestion",
        target_repo=str(outside_repo),
        summary="Should not be delivered without allowlist membership.",
    )
    collect_mail(hub, [repo_a])
    route_mail(hub)
    delivered = deliver_mail(hub, [allowed_repo])

    assert delivered["delivered_count"] == 0
    assert delivered["skipped"][0]["reason"] == "target repo is not in the allowed delivery list"
    assert not (outside_repo / ".digital-asset").exists()


def test_central_only_delivery_is_not_treated_as_filesystem_path(tmp_path: Path):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()

    compose_mail(
        repo_a,
        message_type="taxonomy_suggestion",
        target_repo="central_only",
        summary="Candidate taxonomy note stays in the hub.",
    )

    collect_mail(hub, [repo_a])
    route_mail(hub)
    delivered = deliver_mail(hub, [repo_b])

    assert delivered["central_only_count"] == 1
    assert delivered["delivered_count"] == 0
    assert delivered["skipped"] == []
    assert not (tmp_path / "central_only").exists()


def test_malformed_central_outbox_blocks_delivery(tmp_path: Path):
    hub = tmp_path / "dad"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_b.mkdir()
    outbox = hub / "processed" / "mail" / "outbox" / "routed.jsonl"
    outbox.parent.mkdir(parents=True)
    outbox.write_text("{not-json\n", encoding="utf-8")

    delivered = deliver_mail(hub, [repo_b])

    assert delivered["blocked"] is True
    assert delivered["error_count"] == 1
    assert delivered["delivered_count"] == 0


def test_review_archive_digest_and_daily_freshness(tmp_path: Path):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()

    composed = compose_mail(
        repo_a,
        message_type="capability_suggestion",
        target_repo=str(repo_b),
        summary="Add capability-matrix guidance to the repo front door.",
    )
    collect_mail(hub, [repo_a])
    route_mail(hub)
    deliver_mail(hub, [repo_b])

    decision = review_mail(
        repo_b,
        mail_id=composed["record"]["mail_id"],
        decision="reject",
        decided_by="unit-test",
        notes="Not useful for this repo yet.",
    )
    digest = digest_mail(repo_b, checked_at="2026-06-30T10:00:00+00:00")
    fresh = mail_digest_status(repo_b, now="2026-06-30T11:00:00+00:00")
    stale = mail_digest_status(repo_b, now="2026-07-01T12:00:00+00:00")

    assert decision["appended"] is True
    assert digest["inbox_count"] == 1
    assert digest["unread_count"] == 0
    assert fresh["status"] == "fresh"
    assert fresh["stale"] is False
    assert stale["status"] == "stale"
    assert stale["stale"] is True


def test_reviewed_mail_is_not_redelivered_after_inbox_compaction(tmp_path: Path):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()
    composed = compose_mail(
        repo_a,
        message_type="capability_suggestion",
        target_repo=str(repo_b),
        summary="Archive decisions should preserve duplicate detection.",
    )
    collect_mail(hub, [repo_a])
    route_mail(hub)
    deliver_mail(hub, [repo_b])
    review_mail(repo_b, mail_id=composed["record"]["mail_id"], decision="archive")
    (repo_b / ".digital-asset" / "mail" / "inbox.jsonl").write_text("", encoding="utf-8")

    delivered_again = deliver_mail(hub, [repo_b])

    assert delivered_again["delivered_count"] == 0
    assert delivered_again["acknowledged_duplicate_count"] == 1


def test_digest_ignores_forged_archive_decision_rows(tmp_path: Path):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()
    composed = compose_mail(
        repo_a,
        message_type="lesson_suggestion",
        target_repo=str(repo_b),
        summary="Forged archive rows should not mark mail reviewed.",
    )
    collect_mail(hub, [repo_a])
    route_mail(hub)
    deliver_mail(hub, [repo_b])
    archive = repo_b / ".digital-asset" / "mail" / "archive.jsonl"
    _append_jsonl(archive, {"mail_id": composed["record"]["mail_id"], "decision": "reject"})

    digest = digest_mail(repo_b, checked_at="2026-06-30T10:00:00+00:00")

    assert digest["unread_count"] == 1


def test_missing_digest_status_is_stale_without_writing(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    status = mail_digest_status(repo)

    assert status == {"status": "missing", "stale": True, "last_checked_at": None}
    assert not (repo / ".digital-asset").exists()


def test_invalid_naive_and_future_digest_status_are_stale(tmp_path: Path):
    repo = tmp_path / "repo"
    mailbox = repo / ".digital-asset" / "mail"
    mailbox.mkdir(parents=True)
    last_checked = mailbox / "last_checked.json"

    last_checked.write_text("not-json", encoding="utf-8")
    assert mail_digest_status(repo)["status"] == "invalid"
    assert mail_digest_status(repo)["stale"] is True

    last_checked.write_text('{"last_checked_at":"2026-06-30T10:00:00"}', encoding="utf-8")
    naive = mail_digest_status(repo, now="2026-06-30T11:00:00+00:00")
    assert naive["status"] == "invalid"
    assert naive["stale"] is True

    last_checked.write_text(
        '{"last_checked_at":"2026-07-01T10:00:00+00:00"}',
        encoding="utf-8",
    )
    future = mail_digest_status(repo, now="2026-06-30T11:00:00+00:00")
    assert future["status"] == "future"
    assert future["stale"] is True


def test_symlinked_mailbox_escape_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    outside = tmp_path / "outside-mail"
    repo.mkdir()
    outside.mkdir()
    (repo / ".digital-asset").mkdir()
    try:
        (repo / ".digital-asset" / "mail").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(ValueError, match="escapes repository boundary"):
        compose_mail(
            repo,
            message_type="lesson_suggestion",
            target_repo="central_only",
            summary="Should fail before writing outside repo.",
        )
