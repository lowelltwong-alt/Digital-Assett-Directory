"""Test-only construction of opaque shadow-verifier results.

Production code must use raw signed attestations and the fixed trust registry.
"""

from __future__ import annotations

from typing import Any, Iterable

from digital_asset_directory.portfolio_authority import (
    VerificationReport,
    VerifiedApprovals,
    _VERIFIER_SEAL,
    authority_event_digest,
)


def trusted_test_approvals(
    events: Iterable[dict[str, Any]],
    approval_ids: Iterable[str],
) -> VerifiedApprovals:
    wanted = set(approval_ids)
    keys: set[tuple[str, str, str, str]] = set()
    for event in events:
        payload = event.get("payload", {})
        approval_id = str(payload.get("approval_id", "")) if isinstance(payload, dict) else ""
        if approval_id not in wanted:
            continue
        keys.add(
            (
                str(event.get("event_id", "")),
                str(event.get("event_kind", "")),
                authority_event_digest(event),
                approval_id,
            )
        )
    report = VerificationReport(
        status="verified_shadow_candidates" if keys else "deny_all",
        trust_registry_status="test_only",
        trust_anchor_status="unanchored_shadow",
        attestation_count=len(keys),
        verified_attestation_count=len(keys),
        diagnostics=(),
    )
    return VerifiedApprovals(
        keys=frozenset(keys),
        report=report,
        _seal=_VERIFIER_SEAL,
    )
