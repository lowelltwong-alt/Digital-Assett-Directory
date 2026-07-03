from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer

from digital_asset_directory.cli import _discover_mail_repos, _mail_repo_candidates
from digital_asset_directory.config import MailRepoPolicy
from digital_asset_directory.mail_center import (
    central_inbox_path,
    collect_mail,
    compose_mail,
    deliver_mail,
    digest_mail,
    mail_digest_status,
    release_mail,
    review_central_mail,
    route_mail,
    review_mail,
    triage_mail,
)
import digital_asset_directory.mail_center as mail_center

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


def _policy(
    repo: Path,
    repo_id: str,
    *,
    visibility: str = "internal",
    public_facing: bool = False,
    delivery_allowed: bool = True,
    write_protected: bool = False,
    write_protection_reason: str = "",
) -> MailRepoPolicy:
    return MailRepoPolicy(
        id=repo_id,
        path=repo,
        alias=repo_id,
        visibility=visibility,
        public_facing=public_facing,
        mail_enabled=True,
        delivery_allowed=delivery_allowed,
        write_protected=write_protected,
        write_protection_reason=write_protection_reason,
    )


def test_compose_redacts_secret_like_payload_and_rejects_restricted_mail(tmp_path: Path):
    repo = tmp_path / "repo-a"
    repo.mkdir()

    result = compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Share daily digest guidance.",
        payload={
            "note": (
                "api_key=super-secret-value AWS AKIAABCDEFGHIJKLMNOP JWT "
                "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.abcdefghijkl "
                "db postgres://user:pass@example.com/db email test@example.com "
                "phone 555-123-4567 ssn 123-45-6789 should never persist"
            )
        },
        evidence=["generated unit test"],
        suggested_actions=["Review locally before adopting."],
    )

    assert result["appended"] is True
    assert (repo / ".digital-asset" / "mail" / "README.md").exists()
    assert (repo / ".digital-asset" / "mail" / ".gitignore").read_text(
        encoding="utf-8"
    ) == "*.jsonl\nlast_checked.json\n"
    records = _jsonl(repo / ".digital-asset" / "mail" / "outbox.jsonl")
    assert len(records) == 1
    serialized = json.dumps(records[0])
    assert "super-secret-value" not in serialized
    assert "AKIAABCDEFGHIJKLMNOP" not in serialized
    assert "eyJhbGciOiJIUzI1NiJ9" not in serialized
    assert "postgres://user:pass@example.com/db" not in serialized
    assert "test@example.com" not in serialized
    assert "555-123-4567" not in serialized
    assert "123-45-6789" not in serialized
    assert records[0]["payload"]["redaction_count"] >= 7
    assert "Best-effort credential/PII screening" in records[0]["payload"]["redaction_note"]

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
    central = _jsonl(central_inbox_path(hub, repo))
    assert central[0]["source_repo"].startswith("repo-path-sha256:")
    assert central[0]["source_provenance"]["canonical_source_repo"].startswith(
        "repo-path-sha256:"
    )
    assert central[0]["mail_id"] != "dad:mail:spoofed"
    assert central[0]["dedupe_key"] != "spoofed-key"
    central_text = json.dumps(central[0])
    assert "very-secret-value" not in central_text
    assert str(repo.resolve()).replace("\\", "/") not in central_text.replace("\\", "/")


def test_collect_sanitizes_local_paths_inside_mail_content(tmp_path: Path):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    local_ref = "C:/Users/lowel/OneDrive/Desktop/Git Projects/private-repo/docs/review.md"
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Local path refs should be hashed before central storage.",
        payload={"note": f"See {local_ref}"},
        evidence=[local_ref],
        suggested_actions=[f"Review {local_ref} locally."],
    )

    result = collect_mail(hub, [repo])
    central = _jsonl(central_inbox_path(hub, repo))
    central_text = json.dumps(central, sort_keys=True).replace("\\", "/")

    assert result["collected_count"] == 1
    assert "C:/Users" not in central_text
    assert "OneDrive" not in central_text
    assert "Git Projects" not in central_text
    assert "repo-path-sha256:" in central_text


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


def test_malformed_central_outbox_quarantines_bad_row_and_continues(tmp_path: Path):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()
    compose_mail(
        repo_a,
        message_type="workflow_suggestion",
        target_repo=str(repo_b),
        summary="Good row should still deliver.",
    )
    collect_mail(hub, [repo_a])
    route_mail(hub)
    outbox = hub / "processed" / "mail" / "outbox" / "routed.jsonl"
    with outbox.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("{not-json\n")

    delivered = deliver_mail(hub, [repo_b])

    assert delivered["blocked"] is False
    assert delivered["error_count"] == 1
    assert delivered["delivered_count"] == 1
    quarantine = _jsonl(hub / "processed" / "mail" / "quarantine" / "malformed_jsonl.jsonl")
    assert quarantine[0]["event_type"] == "malformed_jsonl"


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
        human_verified=True,
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


def test_central_review_handles_collected_mail_without_local_delivery(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "mock-trial"
    hub.mkdir()
    source.mkdir()
    composed = compose_mail(
        source,
        message_type="governance_notice",
        target_repo=str(hub),
        summary="Artifact registration drift should be triaged centrally by DAD.",
        payload={"safe_summary": "metadata-only registration drift"},
        evidence=["docs/artifact-registration-drift.md"],
        suggested_actions=["Review as candidate exception-lake signal."],
        allow_similar=True,
    )

    collected = collect_mail(hub, [source])
    central = _jsonl(central_inbox_path(hub, source))
    central_mail_id = central[0]["mail_id"]
    with pytest.raises(ValueError, match="No inbox mail found"):
        review_mail(hub, mail_id=central_mail_id, decision="accept")

    result = review_central_mail(
        hub,
        mail_id=composed["record"]["mail_id"],
        decision="accept",
        decided_by="codex",
        notes="DAD central triage only.",
    )

    assert collected["collected_count"] == 1
    assert result["appended"] is True
    assert result["decision"]["mail_id"] == central_mail_id
    assert result["decision"]["requested_mail_id"] == composed["record"]["mail_id"]
    assert result["decision"]["repository"] == "dad://central-mail"
    assert result["decision"]["review_status"] == "agent_triage"
    assert result["decision"]["public_release_gate_satisfied"] is False
    assert result["decision"]["target_repo_adoption_satisfied"] is False
    assert result["archive"] == "processed/mail/archive/central_review_decisions.jsonl"
    assert _jsonl(hub / result["archive"])[0]["decision_id"] == result["decision"]["decision_id"]
    archive_text = (hub / result["archive"]).read_text(encoding="utf-8")
    for fragment in [str(source), str(hub), "C:/Users", "C:\\Users", "OneDrive", "AppData"]:
        assert fragment.replace("\\", "/") not in archive_text.replace("\\", "/")
    assert not (hub / ".digital-asset" / "mail" / "archive.jsonl").exists()


def test_central_review_is_idempotent_and_not_public_release(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "private-source"
    target = tmp_path / "public-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    policies = [
        _policy(source, "private-source", visibility="private"),
        _policy(target, "public-target", visibility="public", public_facing=True),
    ]
    composed = compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo=str(target),
        summary="Private-origin mail must still need human release.",
        repo_policies=policies,
        allow_similar=True,
    )
    collect_mail(hub, [source], repo_policies=policies)
    route_mail(hub, repo_policies=policies)

    first = review_central_mail(
        hub,
        mail_id=composed["record"]["mail_id"],
        decision="defer",
        decided_by="Lowell",
        human_verified=True,
        repo_policies=policies,
    )
    second = review_central_mail(
        hub,
        mail_id=composed["record"]["mail_id"],
        decision="defer",
        decided_by="Lowell",
        human_verified=True,
        repo_policies=policies,
    )
    delivered = deliver_mail(hub, [target], repo_policies=policies)

    assert first["appended"] is True
    assert second["appended"] is False
    assert first["decision"]["human_verified"] is True
    assert first["decision"]["source_repo"] == "repo:private-source"
    assert first["decision"]["target_repo"] == "repo:public-target"
    assert first["decision"]["public_release_gate_satisfied"] is False
    assert delivered["delivered_count"] == 0
    assert delivered["held_for_release_count"] == 1


def test_central_inbox_filename_uses_policy_id_or_hash_not_absolute_path(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "private source with spaces"
    hub.mkdir()
    source.mkdir()
    policies = [_policy(source, "private-source", visibility="private")]
    compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Central inbox filename should be policy based.",
        repo_policies=policies,
        allow_similar=True,
    )

    collect_mail(hub, [source], repo_policies=policies)
    central_path = central_inbox_path(hub, source, policies)
    inbox_files = sorted((hub / "processed" / "mail" / "inbox").glob("*.jsonl"))

    assert central_path.name == "private-source.jsonl"
    assert inbox_files == [central_path]
    assert str(source).replace("\\", "/") not in central_path.as_posix()


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


def test_private_source_to_internal_target_delivers_with_provenance(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "private-source"
    target = tmp_path / "internal-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    policies = [
        _policy(source, "private-source", visibility="private"),
        _policy(target, "internal-target", visibility="internal"),
    ]

    compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo=str(target),
        summary="Internal target may review private-origin candidate mail.",
        repo_policies=policies,
    )
    collect_mail(hub, [source], repo_policies=policies)
    route_mail(hub, repo_policies=policies)
    delivered = deliver_mail(hub, [target], repo_policies=policies)

    assert delivered["delivered_count"] == 1
    assert delivered["held_for_release_count"] == 0
    inbox = _jsonl(target / ".digital-asset" / "mail" / "inbox.jsonl")
    assert inbox[0]["source_provenance"]["source_visibility"] == "private"
    assert inbox[0]["public_release"]["public_release_required"] is False


def test_private_source_to_public_target_is_held_until_human_release(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "private-source"
    target = tmp_path / "public-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    policies = [
        _policy(source, "private-source", visibility="private"),
        _policy(target, "public-target", visibility="public", public_facing=True),
    ]

    composed = compose_mail(
        source,
        message_type="workflow_suggestion",
        target_repo=str(target),
        summary="Public target should only see this after human release.",
        repo_policies=policies,
    )
    collect_mail(hub, [source], repo_policies=policies)
    route_mail(hub, repo_policies=policies)
    held = deliver_mail(hub, [target], repo_policies=policies)

    assert held["delivered_count"] == 0
    assert held["held_for_release_count"] == 1
    assert not (target / ".digital-asset" / "mail" / "inbox.jsonl").exists()
    holds = _jsonl(hub / "processed" / "mail" / "quarantine" / "public_release_holds.jsonl")
    assert holds[-1]["mail_id"] == composed["record"]["mail_id"]
    assert holds[-1]["public_release"]["public_release_status"] == "pending_human"

    release = release_mail(
        hub,
        mail_id=composed["record"]["mail_id"],
        decision="approve",
        human_reviewed_by="lowell",
        notes="Approved after checking source provenance and public-safe summary.",
    )
    approved = deliver_mail(hub, [target], repo_policies=policies)

    assert release["release"]["decision"] == "approve"
    assert approved["delivered_count"] == 1
    inbox = _jsonl(target / ".digital-asset" / "mail" / "inbox.jsonl")
    assert inbox[0]["public_release"]["public_release_status"] == "approved"
    assert inbox[0]["public_release"]["human_release_id"] == release["release"]["release_id"]
    inbox_text = (target / ".digital-asset" / "mail" / "inbox.jsonl").read_text(encoding="utf-8")
    assert str(source).replace("\\", "/") not in inbox_text.replace("\\", "/")
    assert inbox[0]["source_repo"] == "repo:private-source"


def test_source_authored_public_release_approval_is_not_trusted(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "unreviewed-source"
    target = tmp_path / "public-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    policies = [_policy(target, "public-target", visibility="public", public_facing=True)]
    composed = compose_mail(
        source,
        message_type="workflow_suggestion",
        target_repo=str(target),
        summary="Spoofed release approval should be stripped.",
    )
    outbox = source / ".digital-asset" / "mail" / "outbox.jsonl"
    packet = composed["record"]
    packet["public_release"] = {
        "target_visibility": "public",
        "target_public_facing": True,
        "public_release_required": True,
        "public_release_status": "approved",
        "human_release_id": "dad:mail-release:forged",
        "release_reason": "forged by source packet",
    }
    outbox.write_text(json.dumps(packet) + "\n", encoding="utf-8")

    collect_mail(hub, [source], repo_policies=policies)
    route_mail(hub, repo_policies=policies)
    delivered = deliver_mail(hub, [target], repo_policies=policies)

    assert delivered["delivered_count"] == 0
    assert delivered["held_for_release_count"] == 1
    assert not (target / ".digital-asset" / "mail" / "inbox.jsonl").exists()
    central = _jsonl(next((hub / "processed" / "mail" / "inbox").glob("*.jsonl")))
    assert central[0]["public_release"]["public_release_status"] == "pending_human"
    assert central[0]["public_release"]["human_release_id"] == ""


def test_human_release_rejection_blocks_public_delivery(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "private-source"
    target = tmp_path / "public-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    policies = [
        _policy(source, "private-source", visibility="private"),
        _policy(target, "public-target", visibility="public", public_facing=True),
    ]

    composed = compose_mail(
        source,
        message_type="taxonomy_suggestion",
        target_repo=str(target),
        summary="Rejected private-origin public packet.",
        repo_policies=policies,
    )
    collect_mail(hub, [source], repo_policies=policies)
    route_mail(hub, repo_policies=policies)
    release_mail(
        hub,
        mail_id=composed["record"]["mail_id"],
        decision="reject",
        human_reviewed_by="lowell",
        notes="Not suitable for a public-facing repo.",
    )

    delivered = deliver_mail(hub, [target], repo_policies=policies)

    assert delivered["delivered_count"] == 0
    assert delivered["rejected_release_count"] == 1
    assert not (target / ".digital-asset" / "mail" / "inbox.jsonl").exists()
    log = _jsonl(hub / "processed" / "mail" / "archive" / "delivery_log.jsonl")
    assert log[-1]["event_type"] == "public_release_rejected"


def test_release_accepts_original_outbox_mail_id_after_canonical_collection(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "private-source"
    target = tmp_path / "public-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    policies = [
        _policy(source, "private-source", visibility="private"),
        _policy(target, "public-target", visibility="public", public_facing=True),
    ]
    composed = compose_mail(
        source,
        message_type="workflow_suggestion",
        target_repo=str(target),
        summary="Custom local dedupe key should not make release impossible.",
        repo_policies=policies,
        dedupe_key="local-outbox-key-that-will-be-canonicalized",
    )
    collect_mail(hub, [source], repo_policies=policies)
    central = _jsonl(next((hub / "processed" / "mail" / "inbox").glob("*.jsonl")))

    release = release_mail(
        hub,
        mail_id=composed["record"]["mail_id"],
        decision="approve",
        human_reviewed_by="lowell",
    )

    assert central[0]["mail_id"] != composed["record"]["mail_id"]
    assert central[0]["source_provenance"]["original_mail_id"] == composed["record"]["mail_id"]
    assert release["release"]["mail_id"] == central[0]["mail_id"]
    assert release["release"]["requested_mail_id"] == composed["record"]["mail_id"]


def test_agent_review_is_triage_not_human_review(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    target = tmp_path / "target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    composed = compose_mail(
        source,
        message_type="capability_suggestion",
        target_repo=str(target),
        summary="Agent triage should not clear unread mail.",
    )
    collect_mail(hub, [source])
    route_mail(hub)
    deliver_mail(hub, [target])

    review_mail(target, mail_id=composed["record"]["mail_id"], decision="defer")
    agent_digest = digest_mail(target, checked_at="2026-06-30T10:00:00+00:00")
    human_decision = review_mail(
        target,
        mail_id=composed["record"]["mail_id"],
        decision="defer",
        human_verified=True,
        decided_by="lowell",
    )
    human_digest = digest_mail(target, checked_at="2026-06-30T10:05:00+00:00")

    assert agent_digest["unread_count"] == 1
    assert agent_digest["agent_triage_count"] == 1
    assert human_decision["appended"] is True
    assert human_digest["unread_count"] == 0
    assert human_digest["reviewed_count"] == 1


def test_mail_triage_records_future_adoption_pointer(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    target = tmp_path / "target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    composed = compose_mail(
        source,
        message_type="asset_suggestion",
        target_repo=str(target),
        summary="Target may want to watch a Rust parity harness.",
        payload={
            "asset_id": "dad:offering:rust-shadow-parity-harness",
            "source_ref": "assets/coding-harnesses/rust-shadow-parity-harness",
        },
        evidence=["registry/dad-offerings-registry.json"],
    )
    collect_mail(hub, [source])
    route_mail(hub)
    deliver_mail(hub, [target])

    result = triage_mail(
        target,
        mail_id=composed["record"]["mail_id"],
        intake_decision="save_for_future",
        importance="future",
        planned_use="Watch for Python/Rust parity work.",
        implementation_plan=["Review when replacing slow pytest cases."],
        recorded_by="unit-test",
    )

    adoption = result["adoption"]
    assert adoption["intake_decision"] == "save_for_future"
    assert adoption["implementation_status"] == "watching"
    assert adoption["update_tracking"]["watch_source"] is True
    assert adoption["update_tracking"]["upgrade_policy"] == "notify_via_dad_mail_before_local_change"
    assert "dad:offering:rust-shadow-parity-harness" in adoption["source_asset_refs"]
    records = _jsonl(target / ".digital-asset" / "mail" / "adoption.jsonl")
    assert records[0]["adoption_id"] == adoption["adoption_id"]


def test_write_protected_mailbox_blocks_local_review_triage_and_digest(tmp_path: Path):
    repo = tmp_path / "logos"
    repo.mkdir()
    policies = [
        _policy(
            repo,
            "logos-scripture-graph",
            write_protected=True,
            write_protection_reason="explicit local-write approval required",
        )
    ]

    with pytest.raises(ValueError, match="write-protected"):
        compose_mail(
            repo,
            message_type="lesson_suggestion",
            target_repo="central_only",
            summary="Should remain central-only.",
            repo_policies=policies,
        )
    with pytest.raises(ValueError, match="write-protected"):
        review_mail(repo, mail_id="dad:mail:test", decision="defer", repo_policies=policies)
    with pytest.raises(ValueError, match="write-protected"):
        triage_mail(
            repo,
            mail_id="dad:mail:test",
            intake_decision="defer",
            repo_policies=policies,
        )
    with pytest.raises(ValueError, match="write-protected"):
        digest_mail(repo, repo_policies=policies)


def test_public_safe_payload_policy_rejects_raw_blob_to_public_target(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "public-source"
    target = tmp_path / "public-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    policies = [
        _policy(source, "public-source", visibility="public", public_facing=True),
        _policy(target, "public-target", visibility="public", public_facing=True),
    ]

    compose_mail(
        source,
        message_type="asset_suggestion",
        target_repo=str(target),
        summary="Raw table should not go to a public-facing mailbox.",
        payload={"raw_rows": "a,b,c,d,e\n1,2,3,4,5"},
        repo_policies=policies,
    )
    collect_mail(hub, [source], repo_policies=policies)
    route_mail(hub, repo_policies=policies)
    delivered = deliver_mail(hub, [target], repo_policies=policies)

    assert delivered["delivered_count"] == 0
    assert delivered["held_for_release_count"] == 1
    assert delivered["skipped"][0]["reason"] == "public-safe payload violations"
    assert not (target / ".digital-asset" / "mail" / "inbox.jsonl").exists()


def test_public_safe_payload_policy_rejects_raw_evidence_to_public_target(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "public-source"
    target = tmp_path / "public-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    policies = [
        _policy(source, "public-source", visibility="public", public_facing=True),
        _policy(target, "public-target", visibility="public", public_facing=True),
    ]

    compose_mail(
        source,
        message_type="asset_suggestion",
        target_repo=str(target),
        summary="Long raw evidence should not go to a public-facing mailbox.",
        evidence=["x" * 1000],
        repo_policies=policies,
    )
    collect_mail(hub, [source], repo_policies=policies)
    route_mail(hub, repo_policies=policies)
    delivered = deliver_mail(hub, [target], repo_policies=policies)

    assert delivered["delivered_count"] == 0
    assert delivered["held_for_release_count"] == 1
    assert "payload_value_too_long:evidence" in delivered["skipped"][0]["violations"]


def test_public_safe_payload_policy_rejects_legacy_local_path_refs(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "public-source"
    target = tmp_path / "public-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    policies = [
        _policy(source, "public-source", visibility="public", public_facing=True),
        _policy(target, "public-target", visibility="public", public_facing=True),
    ]
    compose_mail(
        source,
        message_type="asset_suggestion",
        target_repo=str(target),
        summary="Legacy routed mail should not leak local paths to public repos.",
        payload={"note": "metadata-only"},
        repo_policies=policies,
    )
    collect_mail(hub, [source], repo_policies=policies)
    route_mail(hub, repo_policies=policies)
    routed_path = hub / "processed" / "mail" / "outbox" / "routed.jsonl"
    routed = _jsonl(routed_path)
    routed[0]["payload"]["note"] = (
        "See C:/Users/lowel/OneDrive/Desktop/Git Projects/private-repo/asset.json"
    )
    routed_path.write_text(json.dumps(routed[0], sort_keys=True) + "\n", encoding="utf-8")

    delivered = deliver_mail(hub, [target], repo_policies=policies)

    assert delivered["delivered_count"] == 0
    assert delivered["held_for_release_count"] == 1
    assert delivered["skipped"][0]["reason"] == "public-safe payload violations"
    assert "payload_contains_local_path_ref:payload.note" in delivered["skipped"][0]["violations"]
    assert not (target / ".digital-asset" / "mail" / "inbox.jsonl").exists()


def test_unreviewed_source_visibility_claim_is_downgraded_before_public_delivery(
    tmp_path: Path,
):
    hub = tmp_path / "dad"
    source = tmp_path / "unreviewed-source"
    target = tmp_path / "public-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    target_policy = [_policy(target, "public-target", visibility="public", public_facing=True)]
    composed = compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo=str(target),
        summary="Spoofed public provenance must not clear the public release gate.",
    )
    outbox = source / ".digital-asset" / "mail" / "outbox.jsonl"
    packet = composed["record"]
    packet["source_provenance"]["source_visibility"] = "public"
    outbox.write_text(json.dumps(packet) + "\n", encoding="utf-8")

    collect_mail(hub, [source], repo_policies=target_policy)
    route_mail(hub, repo_policies=target_policy)
    delivered = deliver_mail(hub, [target], repo_policies=target_policy)

    assert delivered["delivered_count"] == 0
    assert delivered["held_for_release_count"] == 1
    central = _jsonl(next((hub / "processed" / "mail" / "inbox").glob("*.jsonl")))
    assert central[0]["source_provenance"]["source_visibility"] == "unknown"


def test_same_basename_repo_targets_are_held_as_ambiguous(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    target_one = tmp_path / "one" / "shared"
    target_two = tmp_path / "two" / "shared"
    hub.mkdir()
    source.mkdir()
    target_one.mkdir(parents=True)
    target_two.mkdir(parents=True)
    policies = [
        _policy(source, "source", visibility="internal"),
        _policy(target_one, "shared-one", visibility="internal"),
        _policy(target_two, "shared-two", visibility="internal"),
    ]

    compose_mail(
        source,
        message_type="workflow_suggestion",
        target_repo="shared",
        summary="Bare basename target should not pick a repo arbitrarily.",
        repo_policies=policies,
    )
    collect_mail(hub, [source], repo_policies=policies)
    route_mail(hub, repo_policies=policies)
    delivered = deliver_mail(hub, [target_one, target_two], repo_policies=policies)

    assert delivered["delivered_count"] == 0
    assert delivered["skipped"][0]["reason"] == "target repo key is ambiguous"
    assert not (target_one / ".digital-asset" / "mail" / "inbox.jsonl").exists()
    assert not (target_two / ".digital-asset" / "mail" / "inbox.jsonl").exists()


def test_repo_all_uses_reviewed_config_allowlist_only(tmp_path: Path):
    hub = tmp_path / "dad"
    allowed = tmp_path / "allowed"
    stray = tmp_path / "stray"
    hub.mkdir()
    allowed.mkdir()
    stray.mkdir()
    (stray / ".digital-asset" / "mail").mkdir(parents=True)
    (stray / ".digital-asset" / "mail" / "inbox.jsonl").write_text("", encoding="utf-8")
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[SimpleNamespace(enabled=True, path=tmp_path)],
        mail_repos=[_policy(allowed, "allowed")],
    )

    assert _discover_mail_repos(["all"], cfg) == [allowed.resolve()]
    assert _discover_mail_repos(["all"], cfg, delivery=True) == [allowed.resolve()]


def test_repo_option_resolves_reviewed_aliases_and_rejects_ambiguous_names(tmp_path: Path):
    hub = tmp_path / "dad"
    target = tmp_path / "logos-scripture-graph-repo"
    first_same_name = tmp_path / "one" / "shared-name"
    second_same_name = tmp_path / "two" / "shared-name"
    hub.mkdir()
    target.mkdir()
    first_same_name.mkdir(parents=True)
    second_same_name.mkdir(parents=True)
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[
            _policy(target, "logos-scripture-graph"),
            _policy(first_same_name, "first-shared"),
            _policy(second_same_name, "second-shared"),
        ],
    )

    assert _discover_mail_repos(["logos-scripture-graph"], cfg) == [target.resolve()]
    assert _discover_mail_repos(["logos-scripture-graph-repo"], cfg) == [target.resolve()]
    assert _discover_mail_repos([str(target)], cfg) == [target.resolve()]
    with pytest.raises(typer.BadParameter, match="ambiguous"):
        _discover_mail_repos(["shared-name"], cfg)


def test_explicit_delivery_path_requires_reviewed_mail_policy(tmp_path: Path):
    hub = tmp_path / "dad"
    allowed = tmp_path / "allowed"
    stray = tmp_path / "stray"
    hub.mkdir()
    allowed.mkdir()
    stray.mkdir()
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[_policy(allowed, "allowed")],
    )

    with pytest.raises(typer.BadParameter, match="reviewed mail.repos"):
        _discover_mail_repos([str(stray)], cfg, delivery=True)

    assert _discover_mail_repos([str(allowed)], cfg, delivery=True) == [allowed.resolve()]


def test_explicit_reviewed_operation_path_requires_reviewed_mail_policy(tmp_path: Path):
    hub = tmp_path / "dad"
    allowed = tmp_path / "allowed"
    stray = tmp_path / "stray"
    hub.mkdir()
    allowed.mkdir()
    stray.mkdir()
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[_policy(allowed, "allowed")],
    )

    with pytest.raises(typer.BadParameter, match="reviewed mail.repos"):
        _discover_mail_repos([str(stray)], cfg, reviewed=True)

    assert _discover_mail_repos([str(allowed)], cfg, reviewed=True) == [allowed.resolve()]


def test_mail_discovery_reports_nested_configured_repos(tmp_path: Path):
    hub = tmp_path / "dad"
    nested = tmp_path / "group" / "nested-repo"
    hub.mkdir()
    nested.mkdir(parents=True)
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[SimpleNamespace(enabled=True, path=tmp_path)],
        mail_repos=[_policy(nested, "nested-repo")],
    )

    candidates = _mail_repo_candidates(cfg)

    nested_rows = [row for row in candidates if row["path"] == str(nested.resolve())]
    assert len(nested_rows) == 1
    assert nested_rows[0]["configured"] is True
    assert nested_rows[0]["visibility"] == "internal"


def test_strict_delivery_requires_reviewed_target_policy_for_explicit_paths(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    target = tmp_path / "target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    compose_mail(
        source,
        message_type="governance_notice",
        target_repo=str(target),
        summary="Explicit delivery still needs reviewed target policy in strict mode.",
    )
    collect_mail(hub, [source])
    route_mail(hub)

    delivered = deliver_mail(hub, [target], require_target_policy=True)

    assert delivered["delivered_count"] == 0
    assert delivered["skipped"][0]["reason"] == "target repo lacks reviewed mail policy"
    assert not (target / ".digital-asset" / "mail" / "inbox.jsonl").exists()


def test_collect_mail_errors_use_safe_repo_refs(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "C__Users__lowel__OneDrive__Desktop__Git Projects__source"
    hub.mkdir()
    outbox = source / ".digital-asset" / "mail" / "outbox.jsonl"
    outbox.parent.mkdir(parents=True)
    outbox.write_text("{bad-json}\n", encoding="utf-8")

    result = collect_mail(hub, [source])
    result_text = json.dumps(result, sort_keys=True).replace("\\", "/")

    assert result["collected_count"] == 0
    assert result["error_count"] == 1
    assert result["errors"][0]["repo"].startswith("repo-path-sha256:")
    assert "C__Users" not in result_text
    assert "OneDrive" not in result_text
    assert "Git Projects" not in result_text


def test_digest_tolerates_malformed_rows_and_updates_last_checked(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    mailbox = repo / ".digital-asset" / "mail"
    mailbox.mkdir(parents=True)
    (mailbox / "inbox.jsonl").write_text("{bad-json\n", encoding="utf-8")

    digest = digest_mail(repo, checked_at="2026-06-30T10:00:00+00:00")

    assert digest["parse_warning_count"] == 1
    assert digest["unread_count"] == 0
    assert (mailbox / "last_checked.json").exists()


def test_digest_tolerates_invalid_utf8_rows_and_updates_last_checked(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    mailbox = repo / ".digital-asset" / "mail"
    mailbox.mkdir(parents=True)
    (mailbox / "inbox.jsonl").write_bytes(b"\xff\n")

    digest = digest_mail(repo, checked_at="2026-06-30T10:00:00+00:00")

    assert digest["parse_warning_count"] == 1
    assert "Invalid UTF-8" in digest["parse_warnings"][0]["error"]
    assert digest["unread_count"] == 0
    assert (mailbox / "last_checked.json").exists()


def test_stale_jsonl_lock_is_recovered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    hub.mkdir()
    source.mkdir()
    compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Stale lock should be removed.",
    )
    central = central_inbox_path(hub, source)
    central.parent.mkdir(parents=True)
    lock = central.with_name(f".{central.name}.lock")
    lock.write_text("stale", encoding="utf-8")
    old_time = os.path.getmtime(lock) - 1_000
    os.utime(lock, (old_time, old_time))
    monkeypatch.setattr(mail_center, "STALE_LOCK_SECONDS", 1.0)

    result = collect_mail(hub, [source])

    assert result["collected_count"] == 1
    assert not lock.exists()


def test_active_jsonl_lock_timeout_is_reported_per_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    hub.mkdir()
    source.mkdir()
    compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Active lock should be reported.",
    )
    central = central_inbox_path(hub, source)
    central.parent.mkdir(parents=True)
    lock = central.with_name(f".{central.name}.lock")
    lock.write_text("active", encoding="utf-8")
    monkeypatch.setattr(mail_center, "LOCK_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(mail_center, "STALE_LOCK_SECONDS", 999.0)

    result = collect_mail(hub, [source])

    assert result["collected_count"] == 0
    assert result["error_count"] == 1
    assert "Timed out waiting for JSONL lock" in result["errors"][0]["error"]
    lock.unlink()


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
