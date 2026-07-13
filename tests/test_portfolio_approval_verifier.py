from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from digital_asset_directory import portfolio_authority as authority
from digital_asset_directory.portfolio_events import build_event


T0 = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _grant_event() -> dict:
    event, _ = build_event(
        event_kind="execution_lease_granted",
        stream_id="dad:portfolio-workstream:test",
        payload={
            "workstream_id": "dad:portfolio-workstream:test",
            "lease_id": "dad:portfolio-lease:00000000-0000-0000-0000-000000000001",
            "scope_digest": "dad:portfolio-lease-scope:" + "a" * 64,
            "granted_by": "human:reviewer",
            "approval_id": "approval:test:1",
        },
        prev_event_id="",
        recorded_at=T0.isoformat(),
        command_id="dad:portfolio-command:00000000-0000-0000-0000-000000000001",
    )
    return event


def _registry(public_key: bytes) -> dict:
    return {
        "schema_version": "dad.portfolio_approval_trust_registry.v1",
        "registry_id": "dad:registry:portfolio-approval-trust",
        "registry_sequence": 1,
        "previous_registry_digest": "",
        "root_anchor_status": "unanchored_shadow",
        "status": "reviewed_shadow_active",
        "authority_boundary": "Test-only unanchored shadow trust.",
        "keys": [
            {
                "key_id": authority.approval_key_id(public_key),
                "algorithm": "ed25519",
                "public_key_base64": _b64url(public_key),
                "authority_domain": "dad.test",
                "approver_ids": ["human:reviewer"],
                "allowed_event_kinds": ["execution_lease_granted"],
                "valid_from": (T0 - timedelta(days=1)).isoformat(),
                "valid_until": (T0 + timedelta(days=1)).isoformat(),
                "revoked_at": None,
                "key_status": "active",
                "review_status": "reviewed",
                "authority_refs": ["test:human-review"],
            }
        ],
    }


def _attestation(event: dict, registry: dict) -> dict:
    return {
        "schema_version": "dad.portfolio_approval_attestation.v1",
        "authority_context": "dad.portfolio_execution_authority.v1",
        "signature_algorithm": "ed25519",
        "canonicalization": "dad-ascii-json.v1",
        "digest_algorithm": "sha256",
        "audience": "dad.portfolio.execution-control",
        "execution_mode": "dry_run",
        "trust_registry_digest": authority.trust_registry_digest(registry),
        "attestation_id": "dad:portfolio-attestation:00000000-0000-0000-0000-000000000001",
        "approval_id": "approval:test:1",
        "authority_domain": "dad.test",
        "event_id": event["event_id"],
        "event_kind": event["event_kind"],
        "event_digest": authority.authority_event_digest(event),
        "event_schema_version": event["schema_version"],
        "stream_id": event["stream_id"],
        "prev_event_id": event["prev_event_id"],
        "command_id": event["command_id"],
        "event_recorded_at": event["recorded_at"],
        "key_id": registry["keys"][0]["key_id"],
        "approver_id": "human:reviewer",
        "issued_at": (T0 + timedelta(minutes=1)).isoformat(),
        "not_before": T0.isoformat(),
        "expires_at": (T0 + timedelta(hours=2)).isoformat(),
        "nonce": "0123456789abcdef",
        "signature": _b64url(b"s" * 64),
    }


def test_valid_exact_event_signature_becomes_shadow_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    public_key = b"k" * 32
    event = _grant_event()
    registry = _registry(public_key)
    attestation = _attestation(event, registry)
    seen: list[tuple[bytes, bytes, bytes]] = []

    def verify(key: bytes, signature: bytes, message: bytes) -> bool:
        seen.append((key, signature, message))
        return True

    monkeypatch.setattr(authority, "_verify_ed25519_signature", verify)
    result = authority.verify_approval_attestations(
        [event],
        [attestation],
        registry,
        as_of=T0 + timedelta(hours=1),
    )
    keys, report = authority._verified_event_keys(result)
    assert len(keys) == 1
    assert report["status"] == "verified_shadow_candidates"
    assert report["trust_anchor_status"] == "unanchored_shadow"
    assert seen[0][2].startswith(authority.SIGNATURE_PREFIX)
    assert b'"signature"' not in seen[0][2]


@pytest.mark.parametrize(
    ("mutation", "diagnostic"),
    [
        (lambda row: row.__setitem__("authority_domain", "other.domain"), "trust_scope_mismatch"),
        (lambda row: row.__setitem__("event_digest", "0" * 64), "attestation_event_mismatch"),
        (lambda row: row.__setitem__("approver_id", "human:other"), "attestation_actor_mismatch"),
        (
            lambda row: row.__setitem__("expires_at", (T0 + timedelta(days=2)).isoformat()),
            "attestation_not_current",
        ),
        (
            lambda row: row.__setitem__("not_before", (T0 + timedelta(minutes=30)).isoformat()),
            "attestation_not_current",
        ),
    ],
)
def test_scope_actor_digest_and_interval_mismatches_deny(
    monkeypatch: pytest.MonkeyPatch,
    mutation,
    diagnostic: str,
) -> None:
    public_key = b"k" * 32
    event = _grant_event()
    registry = _registry(public_key)
    attestation = _attestation(event, registry)
    mutation(attestation)
    monkeypatch.setattr(authority, "_verify_ed25519_signature", lambda *_args: True)
    result = authority.verify_approval_attestations(
        [event],
        [attestation],
        registry,
        as_of=T0 + timedelta(hours=1),
    )
    keys, report = authority._verified_event_keys(result)
    assert keys == frozenset()
    assert any(item.startswith(diagnostic) for item in report["diagnostics"])


def test_missing_crypto_backend_denies_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    event = _grant_event()
    registry = _registry(b"k" * 32)
    attestation = _attestation(event, registry)

    def unavailable(*_args) -> bool:
        raise authority.CryptoBackendUnavailable("missing")

    monkeypatch.setattr(authority, "_verify_ed25519_signature", unavailable)
    result = authority.verify_approval_attestations(
        [event],
        [attestation],
        registry,
        as_of=T0 + timedelta(hours=1),
    )
    keys, report = authority._verified_event_keys(result)
    assert keys == frozenset()
    assert report["status"] == "deny_all"
    assert "crypto_backend_unavailable" in report["diagnostics"]


def test_candidate_registry_and_duplicate_json_keys_deny(tmp_path: Path) -> None:
    candidate = authority.load_trust_registry(Path.cwd())
    result = authority.verify_approval_attestations([], [], candidate, as_of=T0)
    keys, report = authority._verified_event_keys(result)
    assert keys == frozenset()
    assert report["trust_registry_status"] == "candidate_deny_all"

    path = tmp_path / "duplicate.json"
    path.write_text('{"approval_id":"one","approval_id":"two"}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        authority.load_attestations(path)


def test_canonical_message_is_order_independent_and_signature_excluded() -> None:
    event = _grant_event()
    registry = _registry(b"k" * 32)
    row = _attestation(event, registry)
    reversed_row = dict(reversed(list(row.items())))
    assert authority.canonical_attestation_bytes(row) == authority.canonical_attestation_bytes(
        reversed_row
    )
    decoded = authority.canonical_attestation_bytes(row).removeprefix(authority.SIGNATURE_PREFIX)
    payload = json.loads(decoded)
    assert "signature" not in payload


def test_verifier_results_are_immutable(tmp_path: Path) -> None:
    result = authority.verify_approval_attestations(
        [],
        [],
        authority.load_trust_registry(tmp_path),
        as_of=T0,
    )
    with pytest.raises(AttributeError, match="immutable"):
        result._keys = frozenset()


def test_naive_observation_time_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timezone"):
        authority.verify_approval_attestations(
            [],
            [],
            authority.load_trust_registry(tmp_path),
            as_of=datetime(2026, 7, 13, 12, 0),
        )
