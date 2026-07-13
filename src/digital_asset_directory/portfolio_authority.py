"""Trusted shadow approval verification for the Portfolio OS authority plane.

This module verifies public-key signatures only. It never signs, stores private
keys, executes work, launches an agent, touches Git, or writes another
repository. Missing crypto support, trust material, or valid attestations is a
normal deny-all result. Repository trust remains unanchored shadow evidence.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import FormatChecker
from jsonschema.validators import validator_for

AUTHORITY_CONTEXT = "dad.portfolio_execution_authority.v1"
ATTESTATION_SCHEMA_VERSION = "dad.portfolio_approval_attestation.v1"
TRUST_REGISTRY_SCHEMA_VERSION = "dad.portfolio_approval_trust_registry.v1"
SIGNATURE_PREFIX = b"DAD-AUTHORITY-ATTESTATION\x00v1\x00"
MAX_ATTESTATION_DURATION = timedelta(hours=24)
CLOCK_SKEW = timedelta(minutes=5)
APPROVAL_EVENT_KINDS = frozenset(
    {
        "execution_lease_granted",
        "dispatch_intent_approved",
        "dispatch_reconciliation_recorded",
    }
)
SIGNED_FIELDS = (
    "schema_version",
    "authority_context",
    "signature_algorithm",
    "canonicalization",
    "digest_algorithm",
    "audience",
    "execution_mode",
    "trust_registry_digest",
    "attestation_id",
    "approval_id",
    "authority_domain",
    "event_id",
    "event_kind",
    "event_digest",
    "event_schema_version",
    "stream_id",
    "prev_event_id",
    "command_id",
    "event_recorded_at",
    "key_id",
    "approver_id",
    "issued_at",
    "not_before",
    "expires_at",
    "nonce",
)
_VERIFIER_SEAL = object()


class CryptoBackendUnavailable(RuntimeError):
    """A reviewed Ed25519 verification backend is not installed."""


@dataclass(frozen=True)
class VerificationReport:
    status: str
    trust_registry_status: str
    trust_anchor_status: str
    attestation_count: int
    verified_attestation_count: int
    diagnostics: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "dad.portfolio_approval_verification.v1",
            "status": self.status,
            "trust_registry_status": self.trust_registry_status,
            "trust_anchor_status": self.trust_anchor_status,
            "attestation_count": self.attestation_count,
            "verified_attestation_count": self.verified_attestation_count,
            "diagnostics": list(self.diagnostics),
            "authority_boundary": (
                "Signatures are unanchored shadow evidence only. No executor exists, "
                "repository keys cannot authorize real mutation, and dispatch_allowed "
                "remains false."
            ),
        }


class VerifiedApprovals:
    """Opaque shadow-verifier result accepted by the execution fold."""

    __slots__ = ("_keys", "_report", "_seal")

    def __init__(
        self,
        *,
        keys: frozenset[tuple[str, str, str, str]],
        report: VerificationReport,
        _seal: object,
    ) -> None:
        if _seal is not _VERIFIER_SEAL:
            raise TypeError("VerifiedApprovals can only be created by the trusted verifier")
        object.__setattr__(self, "_keys", keys)
        object.__setattr__(self, "_report", report)
        object.__setattr__(self, "_seal", _seal)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("VerifiedApprovals is immutable")

    @property
    def report(self) -> dict[str, Any]:
        return self._report.as_dict()


def _now(value: datetime | None) -> datetime:
    observed = value or datetime.now(timezone.utc)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return observed.astimezone(timezone.utc)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def _strict_json_loads(text: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON object key: {key}")
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=reject_duplicates)


def _schema_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / name


def _schema_errors(value: Any, name: str) -> list[str]:
    try:
        schema = json.loads(_schema_path(name).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"schema_unavailable:{name}:{type(exc).__name__}"]
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema, format_checker=FormatChecker())
    return [
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}:{error.message}"
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def canonical_attestation_bytes(attestation: Mapping[str, Any]) -> bytes:
    """Return the domain-separated, fixed-field bytes covered by the signature."""

    message = {field: attestation.get(field) for field in SIGNED_FIELDS}
    if any(not isinstance(value, str) for value in message.values()):
        raise ValueError("all signed attestation fields must be strings")
    for field, value in message.items():
        if not value and field != "prev_event_id":
            raise ValueError(f"signed attestation field must be non-empty: {field}")
        if any(ord(char) < 0x21 or ord(char) > 0x7E for char in value):
            raise ValueError(f"signed attestation field must use printable ASCII: {field}")
    canonical = json.dumps(
        message,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return SIGNATURE_PREFIX + canonical


def authority_event_digest(event: Mapping[str, Any]) -> str:
    """Digest the complete immutable authority-event envelope."""

    canonical = json.dumps(
        dict(event),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def trust_registry_digest(registry: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        dict(registry),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def approval_key_id(public_key: bytes) -> str:
    if len(public_key) != 32:
        raise ValueError("Ed25519 public keys must contain exactly 32 raw bytes")
    return f"dad:portfolio-approval-key:{hashlib.sha256(public_key).hexdigest()}"


def _decode_base64url(value: str, *, expected_length: int) -> bytes:
    if "=" in value:
        raise ValueError("base64url input must be canonical and unpadded")
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * ((4 - len(value) % 4) % 4))
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid base64url input") from exc
    if len(decoded) != expected_length:
        raise ValueError(f"decoded value must contain {expected_length} bytes")
    if base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=") != value:
        raise ValueError("base64url input is not canonical")
    return decoded


def load_trust_registry(hub_root: Path) -> dict[str, Any]:
    path = hub_root / "registry" / "portfolio-approval-trust-registry.json"
    try:
        value = _strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {
            "schema_version": TRUST_REGISTRY_SCHEMA_VERSION,
            "registry_id": "dad:registry:portfolio-approval-trust",
            "registry_sequence": 0,
            "previous_registry_digest": "",
            "root_anchor_status": "unanchored_shadow",
            "status": "candidate_deny_all",
            "authority_boundary": f"Trust registry unavailable: {type(exc).__name__}",
            "keys": [],
        }
    return value if isinstance(value, dict) else {}


def load_attestations(path: Path) -> list[dict[str, Any]]:
    value = _strict_json_loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict) and "attestations" in value:
        value = value["attestations"]
    elif isinstance(value, dict):
        value = [value]
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(
            "attestation file must contain one object, a list, or an attestations packet"
        )
    return [dict(item) for item in value]


def _approval_actor(event: Mapping[str, Any]) -> str:
    payload = event.get("payload", {})
    if not isinstance(payload, dict):
        return ""
    field = {
        "execution_lease_granted": "granted_by",
        "dispatch_intent_approved": "approved_by",
        "dispatch_reconciliation_recorded": "decided_by",
    }.get(str(event.get("event_kind", "")), "")
    return str(payload.get(field, "")) if field else ""


def _verify_ed25519_signature(public_key: bytes, signature: bytes, message: bytes) -> bool:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise CryptoBackendUnavailable("cryptography Ed25519 backend is unavailable") from exc
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
    except (InvalidSignature, ValueError):
        return False
    return True


def _empty_result(
    *,
    status: str,
    registry_status: str,
    anchor_status: str,
    count: int,
    diagnostics: Iterable[str],
) -> VerifiedApprovals:
    report = VerificationReport(
        status=status,
        trust_registry_status=registry_status,
        trust_anchor_status=anchor_status,
        attestation_count=count,
        verified_attestation_count=0,
        diagnostics=tuple(sorted(set(diagnostics))),
    )
    return VerifiedApprovals(keys=frozenset(), report=report, _seal=_VERIFIER_SEAL)


def _verified_event_keys(
    approvals: VerifiedApprovals | None,
) -> tuple[frozenset[tuple[str, str, str, str]], dict[str, Any]]:
    if approvals is None:
        empty = _empty_result(
            status="deny_all",
            registry_status="not_loaded",
            anchor_status="not_loaded",
            count=0,
            diagnostics=("trusted_verifier_not_supplied",),
        )
        return empty._keys, empty.report
    if not isinstance(approvals, VerifiedApprovals) or approvals._seal is not _VERIFIER_SEAL:
        empty = _empty_result(
            status="deny_all",
            registry_status="invalid_result",
            anchor_status="invalid_result",
            count=0,
            diagnostics=("untrusted_verification_result_ignored",),
        )
        return empty._keys, empty.report
    return approvals._keys, approvals.report


def verify_approval_attestations(
    events: Iterable[Mapping[str, Any]],
    attestations: Iterable[Mapping[str, Any]],
    trust_registry: Mapping[str, Any],
    *,
    as_of: datetime | None = None,
) -> VerifiedApprovals:
    """Verify exact-event attestations as unanchored shadow evidence."""

    observed = _now(as_of)
    rows = [dict(item) for item in attestations]
    diagnostics: list[str] = []
    registry = dict(trust_registry)
    registry_status = str(registry.get("status", "invalid"))
    anchor_status = str(registry.get("root_anchor_status", "invalid"))

    registry_errors = _schema_errors(registry, "portfolio-approval-trust-registry.schema.json")
    if registry_errors:
        return _empty_result(
            status="deny_all",
            registry_status="invalid",
            anchor_status=anchor_status,
            count=len(rows),
            diagnostics=[f"trust_registry_schema:{item}" for item in registry_errors],
        )
    if registry_status != "reviewed_shadow_active" or anchor_status != "unanchored_shadow":
        return _empty_result(
            status="deny_all",
            registry_status=registry_status,
            anchor_status=anchor_status,
            count=len(rows),
            diagnostics=("trust_registry_not_shadow_active",),
        )

    keys: dict[str, dict[str, Any]] = {}
    for key in registry.get("keys", []):
        key_id = str(key.get("key_id", ""))
        if key_id in keys:
            diagnostics.append(f"duplicate_trust_key:{key_id}")
        keys[key_id] = dict(key)
    if diagnostics:
        return _empty_result(
            status="deny_all",
            registry_status=registry_status,
            anchor_status=anchor_status,
            count=len(rows),
            diagnostics=diagnostics,
        )

    approval_events: dict[str, list[dict[str, Any]]] = {}
    for source in events:
        event = dict(source)
        kind = str(event.get("event_kind", ""))
        if kind not in APPROVAL_EVENT_KINDS:
            continue
        payload = event.get("payload", {})
        approval_id = str(payload.get("approval_id", "")) if isinstance(payload, dict) else ""
        approval_events.setdefault(approval_id, []).append(event)

    attestation_ids = [str(item.get("attestation_id", "")) for item in rows]
    nonces = [str(item.get("nonce", "")) for item in rows]
    duplicate_ids = {value for value in attestation_ids if attestation_ids.count(value) > 1}
    duplicate_nonces = {value for value in nonces if nonces.count(value) > 1}
    registry_digest = trust_registry_digest(registry)
    verified: set[tuple[str, str, str, str]] = set()
    backend_missing = False

    for index, attestation in enumerate(rows):
        approval_id = str(attestation.get("approval_id", f"row-{index}"))
        errors = _schema_errors(attestation, "portfolio-approval-attestation.schema.json")
        if errors:
            diagnostics.append(f"attestation_schema:{approval_id}:{'|'.join(errors)}")
            continue
        if attestation["attestation_id"] in duplicate_ids:
            diagnostics.append(f"duplicate_attestation_id:{attestation['attestation_id']}")
            continue
        if attestation["nonce"] in duplicate_nonces:
            diagnostics.append(f"duplicate_attestation_nonce:{attestation['nonce']}")
            continue
        if attestation["trust_registry_digest"] != registry_digest:
            diagnostics.append(f"trust_registry_digest_mismatch:{approval_id}")
            continue

        matches = approval_events.get(approval_id, [])
        if len(matches) != 1:
            label = "approval_id_reused" if len(matches) > 1 else "approval_event_missing"
            diagnostics.append(f"{label}:{approval_id}")
            continue
        event = matches[0]
        event_id = str(event.get("event_id", ""))
        kind = str(event.get("event_kind", ""))
        digest = authority_event_digest(event)
        envelope_fields = {
            "event_id": event_id,
            "event_kind": kind,
            "event_digest": digest,
            "event_schema_version": str(event.get("schema_version", "")),
            "stream_id": str(event.get("stream_id", "")),
            "prev_event_id": str(event.get("prev_event_id", "")),
            "command_id": str(event.get("command_id", "")),
            "event_recorded_at": str(event.get("recorded_at", "")),
        }
        if any(attestation[field] != value for field, value in envelope_fields.items()):
            diagnostics.append(f"attestation_event_mismatch:{approval_id}")
            continue
        actor = _approval_actor(event)
        if attestation["approver_id"] != actor:
            diagnostics.append(f"attestation_actor_mismatch:{approval_id}")
            continue

        key = keys.get(str(attestation["key_id"]))
        if key is None:
            diagnostics.append(f"unknown_trust_key:{approval_id}")
            continue
        try:
            public_key = _decode_base64url(str(key["public_key_base64"]), expected_length=32)
            expected_key_id = approval_key_id(public_key)
        except ValueError:
            diagnostics.append(f"invalid_public_key:{approval_id}")
            continue
        if expected_key_id != key["key_id"]:
            diagnostics.append(f"trust_key_fingerprint_mismatch:{approval_id}")
            continue
        if (
            key["key_status"] != "active"
            or key["authority_domain"] != attestation["authority_domain"]
            or actor not in key["approver_ids"]
            or kind not in key["allowed_event_kinds"]
        ):
            diagnostics.append(f"trust_scope_mismatch:{approval_id}")
            continue

        try:
            issued_at = _parse_time(str(attestation["issued_at"]))
            not_before = _parse_time(str(attestation["not_before"]))
            expires_at = _parse_time(str(attestation["expires_at"]))
            key_start = _parse_time(str(key["valid_from"]))
            key_end = _parse_time(str(key["valid_until"]))
            event_time = _parse_time(str(event["recorded_at"]))
            revoked_at = (
                _parse_time(str(key["revoked_at"])) if key.get("revoked_at") is not None else None
            )
        except ValueError:
            diagnostics.append(f"invalid_attestation_time:{approval_id}")
            continue
        if (
            not (not_before <= issued_at < expires_at)
            or expires_at - not_before > MAX_ATTESTATION_DURATION
            or issued_at > observed + CLOCK_SKEW
            or issued_at < event_time - CLOCK_SKEW
            or not (not_before <= observed < expires_at)
            or not (key_start <= issued_at < key_end)
            or not (key_start <= observed < key_end)
            or (revoked_at is not None and observed >= revoked_at)
        ):
            diagnostics.append(f"attestation_not_current:{approval_id}")
            continue

        try:
            signature = _decode_base64url(str(attestation["signature"]), expected_length=64)
            signature_valid = _verify_ed25519_signature(
                public_key, signature, canonical_attestation_bytes(attestation)
            )
        except CryptoBackendUnavailable:
            backend_missing = True
            diagnostics.append("crypto_backend_unavailable")
            break
        except (ValueError, TypeError):
            diagnostics.append(f"invalid_signature_encoding:{approval_id}")
            continue
        if not signature_valid:
            diagnostics.append(f"invalid_signature:{approval_id}")
            continue
        verified.add((event_id, kind, digest, approval_id))

    if backend_missing:
        return _empty_result(
            status="deny_all",
            registry_status=registry_status,
            anchor_status=anchor_status,
            count=len(rows),
            diagnostics=diagnostics,
        )

    report = VerificationReport(
        status="verified_shadow_candidates" if verified else "deny_all",
        trust_registry_status=registry_status,
        trust_anchor_status=anchor_status,
        attestation_count=len(rows),
        verified_attestation_count=len(verified),
        diagnostics=tuple(sorted(set(diagnostics))),
    )
    return VerifiedApprovals(keys=frozenset(verified), report=report, _seal=_VERIFIER_SEAL)


__all__ = [
    "APPROVAL_EVENT_KINDS",
    "ATTESTATION_SCHEMA_VERSION",
    "AUTHORITY_CONTEXT",
    "CryptoBackendUnavailable",
    "SIGNATURE_PREFIX",
    "TRUST_REGISTRY_SCHEMA_VERSION",
    "approval_key_id",
    "authority_event_digest",
    "canonical_attestation_bytes",
    "load_attestations",
    "load_trust_registry",
    "trust_registry_digest",
    "verify_approval_attestations",
]
