"""Deterministic A0-A4 authority, quarantine, kill, and recovery candidates.

The module is intentionally incapable of real execution or signature creation.
It evaluates exact evidence and produces append-only control events.  Restrictive
controls can take effect in a future outer executor; recovery always needs new,
explicit human and independent evidence.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from jsonschema.validators import validator_for


REGISTRY_PATH = Path("registry/autonomy-oversight-registry.json")
EVENT_SCHEMA_PATH = Path("schemas/autonomy-control-event.schema.json")
SCOPE_HIERARCHY = (
    "attempt",
    "workflow_revision",
    "role",
    "family",
    "adapter",
    "repository",
    "portfolio",
)
GLOBAL_KILL_SIGNALS = frozenset(
    {
        "protected_data_crossing",
        "authority_or_lease_bypass",
        "unbounded_or_cross_repo_mutation",
        "trust_compromise",
        "audit_corruption",
        "repeated_runaway_across_isolation",
        "affected_scope_indeterminate",
    }
)
_AUTHORITY_LEVELS = {"A0", "A1", "A2", "A3", "A4"}
_CONSEQUENCES = {"small", "medium", "large", "critical", "outlier"}


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object in {path}")
    return value


def _validate(value: dict[str, Any], path: Path) -> None:
    schema = _load_object(path)
    cls = validator_for(schema)
    cls.check_schema(schema)
    errors = sorted(cls(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "<root>"
        raise ValueError(f"Invalid {path.name} at {location}: {error.message}")


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_autonomy_registry(repo_root: Path) -> dict[str, Any]:
    registry = _load_object(repo_root / REGISTRY_PATH)
    if registry.get("real_execution_authority") is not False:
        raise ValueError("Autonomy registry must deny real execution")
    if registry.get("automatic_recovery_allowed") is not False:
        raise ValueError("Autonomy registry must deny automatic recovery")
    if tuple(registry.get("scope_hierarchy", [])) != SCOPE_HIERARCHY:
        raise ValueError("Autonomy scope hierarchy drifted")
    if set(registry.get("global_kill_signals", [])) != GLOBAL_KILL_SIGNALS:
        raise ValueError("Autonomy global-kill policy drifted")
    return registry


def exact_action_digest(action: dict[str, Any]) -> str:
    """Digest only stable exact-action fields; descriptive notes grant no authority."""

    fields = (
        "action_id",
        "authority_level",
        "scope_type",
        "scope_id",
        "operation",
        "effect_class",
        "consequence",
        "target_ref",
        "parameters_digest",
    )
    material_level = str(action.get("authority_level", ""))
    execution_bindings = (
        "plan_revision_id",
        "checkpoint_digest",
        "harness_revision_id",
        "runtime_route_decision_id",
    ) if material_level in {"A2", "A3"} else ()
    fields = (*fields, *execution_bindings)
    missing = [field for field in fields if field not in action]
    if missing:
        raise ValueError(f"Action missing exact authority fields: {missing}")
    material = {field: action[field] for field in fields}
    if material["authority_level"] not in _AUTHORITY_LEVELS:
        raise ValueError("Unknown authority level")
    if material["scope_type"] not in SCOPE_HIERARCHY:
        raise ValueError("Unknown authority scope")
    if material["consequence"] not in _CONSEQUENCES:
        raise ValueError("Unknown consequence")
    if not str(material["parameters_digest"]).startswith("sha256:"):
        raise ValueError("Action parameters require an immutable digest")
    return canonical_digest(material)


def _matching_allowlist(action: dict[str, Any], allowlist: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    for row in allowlist:
        if (
            row.get("status") == "active"
            and row.get("authority_level") == action["authority_level"]
            and row.get("scope_type") == action["scope_type"]
            and row.get("scope_id") == action["scope_id"]
            and row.get("operation") == action["operation"]
            and row.get("effect_class") == action["effect_class"]
            and row.get("target_ref") == action["target_ref"]
        ):
            return row
    return None


def _lease_reasons(
    action: dict[str, Any], lease: dict[str, Any] | None, *, now: datetime
) -> list[str]:
    if not lease:
        return ["exact_lease_missing"]
    reasons: list[str] = []
    if lease.get("status") != "active":
        reasons.append("lease_not_active")
    if lease.get("action_digest") != exact_action_digest(action):
        reasons.append("lease_action_digest_mismatch")
    if lease.get("scope_type") != action["scope_type"] or lease.get("scope_id") != action["scope_id"]:
        reasons.append("lease_scope_mismatch")
    try:
        if _parse_time(str(lease.get("expires_at", ""))) <= now:
            reasons.append("lease_expired")
    except ValueError:
        reasons.append("lease_expiry_invalid")
    if int(lease.get("attempts_used", 0)) >= int(lease.get("maximum_attempts", 1)):
        reasons.append("lease_spent")
    return sorted(set(reasons))


def evaluate_authority(
    repo_root: Path,
    action: dict[str, Any],
    *,
    allowlist: Iterable[dict[str, Any]] = (),
    lease: dict[str, Any] | None = None,
    active_quarantines: Iterable[tuple[str, str]] = (),
    global_kill_active: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate eligibility while retaining the repository-wide deny-execute gate."""

    registry = load_autonomy_registry(repo_root)
    digest = exact_action_digest(action)
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    level = action["authority_level"]
    reasons: list[str] = []
    if global_kill_active:
        reasons.append("global_kill_active")
    quarantine_set = set(active_quarantines)
    scope_index = SCOPE_HIERARCHY.index(action["scope_type"])
    for quarantined_type, quarantined_id in quarantine_set:
        if quarantined_type == "portfolio" or (
            quarantined_type == action["scope_type"] and quarantined_id == action["scope_id"]
        ):
            reasons.append("scope_quarantined")
        elif quarantined_type in SCOPE_HIERARCHY and SCOPE_HIERARCHY.index(quarantined_type) > scope_index:
            if action.get(f"{quarantined_type}_id") == quarantined_id:
                reasons.append("ancestor_scope_quarantined")
    matched_allowlist: dict[str, Any] | None = None
    if level == "A4":
        reasons.append("authority_level_prohibited")
    elif level in {"A2", "A3"}:
        matched_allowlist = _matching_allowlist(action, allowlist)
        if not matched_allowlist:
            reasons.append("exact_allowlist_missing")
        reasons.extend(_lease_reasons(action, lease, now=observed))
    if level == "A3":
        if not action.get("human_confirmation_ref"):
            reasons.append("exact_human_confirmation_missing")
        if not action.get("independent_check_ref"):
            reasons.append("independent_check_missing")
    if action["consequence"] in {"critical", "outlier"} and not action.get("independent_check_ref"):
        reasons.append("critical_independent_check_missing")
    reasons = sorted(set(reasons))
    eligible = not reasons
    return {
        "schema_version": "dad.autonomy_authority_decision.v1",
        "decision_id": f"dad:autonomy-decision:{canonical_digest({'digest': digest, 'reasons': reasons}).split(':', 1)[1]}",
        "action_digest": digest,
        "authority_level": level,
        "consequence": action["consequence"],
        "status": "eligible_candidate" if eligible else "blocked",
        "reason_codes": reasons,
        "matched_allowlist_id": str((matched_allowlist or {}).get("allowlist_id", "")),
        "lease_id": str((lease or {}).get("lease_id", "")),
        "human_gate_required": level in {"A2", "A3"},
        "execution_authorized": bool(registry["real_execution_authority"]),
        "authority_boundary": registry["authority_boundary"],
    }


def build_control_event(
    repo_root: Path,
    *,
    event_kind: str,
    scope_type: str,
    scope_id: str,
    authority_level: str,
    consequence: str,
    payload: dict[str, Any],
    previous_event_id: str = "",
    recorded_at: datetime | None = None,
) -> dict[str, Any]:
    material = {
        "event_kind": event_kind,
        "scope_type": scope_type,
        "scope_id": scope_id,
        "authority_level": authority_level,
        "consequence": consequence,
        "payload": payload,
        "previous_event_id": previous_event_id,
    }
    event = {
        "schema_version": "dad.autonomy_control_event.v1",
        "event_id": f"dad:autonomy-event:{canonical_digest(material).split(':', 1)[1]}",
        "event_kind": event_kind,
        "recorded_at": (recorded_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        "scope_type": scope_type,
        "scope_id": scope_id,
        "authority_level": authority_level,
        "consequence": consequence,
        "previous_event_id": previous_event_id,
        "payload": deepcopy(payload),
        "human_gate_required": event_kind in {"lease_candidate", "recovery_approved"},
        "execution_authorized": False,
    }
    _validate(event, repo_root / EVENT_SCHEMA_PATH)
    return event


def quarantine_candidate(
    repo_root: Path,
    *,
    scope_type: str,
    scope_id: str,
    consequence: str,
    reason_codes: Iterable[str],
) -> dict[str, Any]:
    if scope_type not in SCOPE_HIERARCHY:
        raise ValueError("Unknown quarantine scope")
    reasons = sorted(set(reason_codes))
    if not reasons:
        raise ValueError("Quarantine requires evidence-backed reason codes")
    return build_control_event(
        repo_root,
        event_kind="quarantine_started",
        scope_type=scope_type,
        scope_id=scope_id,
        authority_level="A0",
        consequence=consequence,
        payload={"reason_codes": reasons, "restrictive_only": True},
    )


def global_kill_candidate(
    repo_root: Path,
    *,
    observed_signals: Iterable[str],
    incident_id: str,
) -> dict[str, Any]:
    matched = sorted(set(observed_signals) & GLOBAL_KILL_SIGNALS)
    if not matched:
        raise ValueError("Global kill requires a verified systemic signal")
    return build_control_event(
        repo_root,
        event_kind="global_kill_started",
        scope_type="portfolio",
        scope_id="portfolio:dad",
        authority_level="A0",
        consequence="critical",
        payload={
            "incident_id": incident_id,
            "matched_systemic_signals": matched,
            "reject_new_leases": True,
            "cancel_or_checkpoint_mutable_attempts": True,
            "preserve_read_only_evidence": True,
            "automatic_recovery": False,
        },
    )


def reduce_control_state(repo_root: Path, events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Fold control events. Recovery requests never change restrictive state."""

    quarantines: set[tuple[str, str]] = set()
    global_kill = False
    recovery_requests: list[str] = []
    last_event_id = ""
    for event in events:
        _validate(event, repo_root / EVENT_SCHEMA_PATH)
        if event["previous_event_id"] and event["previous_event_id"] != last_event_id:
            raise ValueError("Autonomy event chain mismatch")
        last_event_id = event["event_id"]
        key = (event["scope_type"], event["scope_id"])
        if event["event_kind"] == "quarantine_started":
            quarantines.add(key)
        elif event["event_kind"] == "global_kill_started":
            global_kill = True
            quarantines.add(("portfolio", event["scope_id"]))
        elif event["event_kind"] == "recovery_requested":
            recovery_requests.append(event["event_id"])
        elif event["event_kind"] == "recovery_approved":
            payload = event["payload"]
            required = {
                "human_verified",
                "human_approval_ref",
                "independent_check_ref",
                "root_cause_ref",
                "recovery_drill_ref",
            }
            if required.issubset(payload) and payload["human_verified"] is True and all(
                payload[name] for name in required - {"human_verified"}
            ):
                if event["scope_type"] == "portfolio":
                    global_kill = False
                quarantines.discard(key)
    return {
        "global_kill_active": global_kill,
        "active_quarantines": [
            {"scope_type": item[0], "scope_id": item[1]}
            for item in sorted(quarantines, key=lambda item: (SCOPE_HIERARCHY.index(item[0]), item[1]))
        ],
        "recovery_request_event_ids": recovery_requests,
        "automatic_recovery": False,
        "execution_authorized": False,
    }


__all__ = [
    "SCOPE_HIERARCHY",
    "build_control_event",
    "evaluate_authority",
    "exact_action_digest",
    "global_kill_candidate",
    "load_autonomy_registry",
    "quarantine_candidate",
    "reduce_control_state",
]
