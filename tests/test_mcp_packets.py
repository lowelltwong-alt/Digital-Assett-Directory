from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from digital_asset_directory.mcp_packets import (
    MCPPacketError,
    prepare_lifecycle_packet,
    record_lifecycle_result,
)


DIGEST = "sha256:" + "a" * 64


def _packet(**overrides):
    values = {
        "request_id": "req-mcp-1",
        "action_kind": "postflight",
        "repository_id": "dad",
        "source_snapshot_digest": DIGEST,
        "expected_preconditions_digest": DIGEST,
        "approval_ref": "approval-1",
    }
    values.update(overrides)
    return prepare_lifecycle_packet(**values)


def test_lifecycle_packet_is_digest_bound_and_non_authorizing():
    packet = _packet()
    assert packet["packet_id"].startswith("dad:mcp-action-packet:")
    assert packet["execution_authorized"] is False
    assert packet["mutations_performed"] is False
    assert _packet()["packet_id"] == packet["packet_id"]


def test_packet_rejects_invalid_kind_digest_and_expiry():
    with pytest.raises(MCPPacketError):
        _packet(action_kind="shell")
    with pytest.raises(MCPPacketError):
        _packet(source_snapshot_digest="bad")
    with pytest.raises(MCPPacketError):
        _packet(expires_hours=169)


def test_result_requires_distinct_checker_and_deduplicates(tmp_path):
    packet = _packet()
    values = {
        "result_status": "verified",
        "before_snapshot_digest": DIGEST,
        "after_snapshot_digest": DIGEST,
        "worker_id": "worker-1",
        "checker_id": "checker-1",
        "evidence_refs": ["test:mcp:1"],
    }
    first = record_lifecycle_result(tmp_path, packet, **values)
    second = record_lifecycle_result(tmp_path, packet, **values)
    assert first["status"] == "recorded"
    assert second["status"] == "deduplicated"
    with pytest.raises(MCPPacketError):
        record_lifecycle_result(tmp_path, packet, **{**values, "checker_id": "worker-1"})


def test_expired_packet_fails_closed(tmp_path):
    packet = _packet(now=datetime.now(timezone.utc) - timedelta(days=8), expires_hours=1)
    with pytest.raises(MCPPacketError, match="expired"):
        record_lifecycle_result(
            tmp_path,
            packet,
            result_status="aborted",
            before_snapshot_digest=DIGEST,
            after_snapshot_digest=DIGEST,
            worker_id="worker-1",
            checker_id="checker-1",
            evidence_refs=["test:mcp:expired"],
        )


def test_result_rejects_unknown_packet_fields(tmp_path):
    packet = {**_packet(), "shell_command": "git reset --hard"}
    with pytest.raises(MCPPacketError, match="unknown fields"):
        record_lifecycle_result(
            tmp_path,
            packet,
            result_status="aborted",
            before_snapshot_digest=DIGEST,
            after_snapshot_digest=DIGEST,
            worker_id="worker-1",
            checker_id="checker-1",
            evidence_refs=["test:mcp:unknown-field"],
        )


def test_result_rejects_forged_packet_identity_or_gate(tmp_path):
    packet = {**_packet(), "packet_id": "dad:mcp-action-packet:forged"}
    with pytest.raises(MCPPacketError, match="identity"):
        record_lifecycle_result(
            tmp_path,
            packet,
            result_status="verified",
            before_snapshot_digest=DIGEST,
            after_snapshot_digest=DIGEST,
            worker_id="worker-1",
            checker_id="checker-1",
            evidence_refs=["test:mcp:forged"],
        )
    packet = {**_packet(), "mutations_performed": True}
    with pytest.raises(MCPPacketError, match="authorizing|mutations"):
        record_lifecycle_result(
            tmp_path,
            packet,
            result_status="verified",
            before_snapshot_digest=DIGEST,
            after_snapshot_digest=DIGEST,
            worker_id="worker-1",
            checker_id="checker-1",
            evidence_refs=["test:mcp:mutated"],
        )
