"""Provider-neutral, deterministic runtime discovery and route decisions.

The resolver consumes explicit local registrations or host receipts.  It does
not probe a provider, scan the network, read credentials, or execute a model.
Every result is a replayable candidate route with a short-lived lease packet.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from jsonschema.validators import validator_for


REGISTRY_PATH = Path("registry/runtime-adapter-registry.json")
SNAPSHOT_SCHEMA_PATH = Path("schemas/runtime-capability-snapshot.schema.json")
DECISION_SCHEMA_PATH = Path("schemas/runtime-route-decision.schema.json")
AUTHORITY_BOUNDARY = (
    "Runtime routes are deterministic candidate coordination evidence. They do not authorize "
    "model execution, provider access, credential use, side effects, fallback after a side "
    "effect, or a producer checking its own material output."
)

_VERIFICATION_RANK = {
    "provider_verified": 0,
    "runtime_verified": 1,
    "locally_observed": 2,
    "reported": 3,
}
_RELIABILITY_RANK = {"verified": 0, "observed": 1, "reported": 2, "unknown": 3}
_LATENCY_RANK = {"low": 0, "medium": 1, "high": 2, "unknown": 3}
_PRIVACY_ORDER = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
_REGISTRATION_FIELDS = {
    "registration_id",
    "runtime_id",
    "adapter_id",
    "provider_id",
    "runtime_label",
    "health",
    "verification_status",
    "capability_ids",
    "tool_ids",
    "privacy_classes",
    "effort_classes",
    "max_context_tokens",
    "cost_status",
    "estimated_cost_per_million_tokens",
    "latency_class",
    "reliability_class",
    "qualified_role_ids",
    "observed_at",
    "expires_at",
}


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _now(value: datetime | None = None) -> datetime:
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object in {path}")
    return value


def _validate(value: dict[str, Any], schema_path: Path) -> None:
    schema = _load_object(schema_path)
    cls = validator_for(schema)
    cls.check_schema(schema)
    errors = sorted(cls(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "<root>"
        raise ValueError(f"Invalid {schema_path.name} at {location}: {error.message}")


def load_adapter_registry(repo_root: Path) -> dict[str, Any]:
    registry = _load_object(repo_root / REGISTRY_PATH)
    if registry.get("execution_authorized") is not False:
        raise ValueError("Runtime adapter registry must deny execution")
    adapters = registry.get("adapters")
    if not isinstance(adapters, list) or not adapters:
        raise ValueError("Runtime adapter registry has no adapters")
    ids = [str(row.get("adapter_id", "")) for row in adapters]
    if len(ids) != len(set(ids)) or any(not item.startswith("adapter:") for item in ids):
        raise ValueError("Runtime adapter identities must be unique and explicit")
    allowed_methods = {"discover", "health", "normalize_receipt"}
    for adapter in adapters:
        if set(adapter.get("protocol_methods", [])) != allowed_methods:
            raise ValueError("Adapters may expose only discover, health, and normalize_receipt")
    return registry


def build_capability_snapshot(
    repo_root: Path,
    registrations: Iterable[dict[str, Any]],
    *,
    source: str = "explicit_local_registration",
    now: datetime | None = None,
    ttl: timedelta = timedelta(hours=24),
) -> dict[str, Any]:
    """Normalize explicit registrations without probing or accepting secrets/endpoints."""

    observed = _now(now)
    registry = load_adapter_registry(repo_root)
    adapter_ids = {row["adapter_id"] for row in registry["adapters"]}
    rows: list[dict[str, Any]] = []
    for original in registrations:
        if not isinstance(original, dict):
            raise ValueError("Runtime registrations must be objects")
        unexpected = set(original) - _REGISTRATION_FIELDS
        if unexpected:
            raise ValueError(f"Unsupported or sensitive registration fields: {sorted(unexpected)}")
        row = deepcopy(original)
        if row.get("adapter_id") not in adapter_ids:
            raise ValueError(f"Unknown runtime adapter: {row.get('adapter_id')}")
        if row.get("adapter_id") == "adapter:cursor-host" and not row.get("provider_id"):
            raise ValueError("Cursor-host provider identity must come from a receipt")
        row.setdefault("observed_at", observed.isoformat())
        row.setdefault("expires_at", (observed + ttl).isoformat())
        row.setdefault("health", "unknown")
        row.setdefault("verification_status", "reported")
        row.setdefault("capability_ids", [])
        row.setdefault("tool_ids", [])
        row.setdefault("privacy_classes", ["public"])
        row.setdefault("effort_classes", ["low"])
        row.setdefault("max_context_tokens", 1)
        row.setdefault("cost_status", "unknown")
        row.setdefault("latency_class", "unknown")
        row.setdefault("reliability_class", "unknown")
        row.setdefault("qualified_role_ids", [])
        rows.append(row)
    rows.sort(key=lambda row: row["runtime_id"])
    if len({row["runtime_id"] for row in rows}) != len(rows):
        raise ValueError("Runtime IDs must be unique within a snapshot")
    material = {
        "source": source,
        "observed_at": observed.isoformat(),
        "runtimes": rows,
    }
    snapshot = {
        "schema_version": "dad.runtime_capability_snapshot.v1",
        "snapshot_id": f"dad:runtime-snapshot:{_canonical_hash(material).split(':', 1)[1]}",
        "observed_at": observed.isoformat(),
        "expires_at": (observed + ttl).isoformat(),
        "source": source,
        "runtimes": rows,
        "candidate_only": True,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    _validate(snapshot, repo_root / SNAPSHOT_SCHEMA_PATH)
    return snapshot


def _request_requirements(request: dict[str, Any]) -> dict[str, Any]:
    required = {"request_id", "plan_revision_id", "harness_revision_id", "capability_ids", "tool_ids", "privacy_class", "effort_class", "context_tokens", "role_id", "consequence"}
    missing = sorted(required - set(request))
    if missing:
        raise ValueError(f"Runtime route request missing fields: {missing}")
    if request["privacy_class"] not in _PRIVACY_ORDER:
        raise ValueError("Unknown privacy class")
    if request["effort_class"] not in {"low", "medium", "high"}:
        raise ValueError("Unknown effort class")
    if request["consequence"] not in {"small", "medium", "large", "critical", "outlier"}:
        raise ValueError("Unknown consequence")
    if int(request["context_tokens"]) < 1:
        raise ValueError("context_tokens must be positive")
    return request


def _rejection_reasons(
    runtime: dict[str, Any], request: dict[str, Any], *, now: datetime
) -> list[str]:
    reasons: list[str] = []
    if runtime["health"] != "available":
        reasons.append("runtime_not_available")
    try:
        if _parse_time(runtime["expires_at"]) <= now:
            reasons.append("runtime_snapshot_expired")
    except (TypeError, ValueError):
        reasons.append("runtime_expiry_invalid")
    if not set(request["capability_ids"]).issubset(runtime["capability_ids"]):
        reasons.append("missing_capability")
    if not set(request["tool_ids"]).issubset(runtime["tool_ids"]):
        reasons.append("missing_tool")
    if request["privacy_class"] not in runtime["privacy_classes"]:
        reasons.append("privacy_not_supported")
    if request["effort_class"] not in runtime["effort_classes"]:
        reasons.append("effort_not_supported")
    if int(runtime["max_context_tokens"]) < int(request["context_tokens"]):
        reasons.append("context_too_small")
    role_id = str(request["role_id"])
    if role_id not in runtime["qualified_role_ids"]:
        reasons.append("role_not_qualified")
    if runtime["runtime_id"] in set(request.get("independent_from_runtime_ids", [])):
        reasons.append("checker_runtime_conflict")
    if runtime["provider_id"] in set(request.get("independent_from_provider_ids", [])):
        reasons.append("checker_provider_conflict")
    if request.get("maximum_cost") is not None and runtime["cost_status"] == "unknown":
        reasons.append("unknown_cost_under_hard_cap")
    estimated = runtime.get("estimated_cost_per_million_tokens")
    if request.get("maximum_cost") is not None and isinstance(estimated, (int, float)):
        request_cost = float(estimated) * int(request["context_tokens"]) / 1_000_000
        if request_cost > float(request["maximum_cost"]):
            reasons.append("cost_cap_exceeded")
    if runtime["runtime_id"] in set(request.get("excluded_runtime_ids", [])):
        reasons.append("runtime_excluded")
    return sorted(set(reasons))


def _ranking_key(runtime: dict[str, Any], consequence: str) -> tuple[Any, ...]:
    cost = runtime.get("estimated_cost_per_million_tokens")
    cost_rank = float(cost) if isinstance(cost, (int, float)) else float("inf")
    privacy_rank = len(runtime["privacy_classes"])
    stable = runtime["runtime_id"]
    if consequence in {"large", "critical", "outlier"}:
        return (
            _VERIFICATION_RANK[runtime["verification_status"]],
            _RELIABILITY_RANK[runtime["reliability_class"]],
            privacy_rank,
            cost_rank,
            _LATENCY_RANK[runtime["latency_class"]],
            stable,
        )
    return (
        privacy_rank,
        cost_rank,
        _LATENCY_RANK[runtime["latency_class"]],
        _RELIABILITY_RANK[runtime["reliability_class"]],
        _VERIFICATION_RANK[runtime["verification_status"]],
        stable,
    )


def resolve_runtime(
    repo_root: Path,
    request: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    request = _request_requirements(deepcopy(request))
    observed = _now(now)
    _validate(snapshot, repo_root / SNAPSHOT_SCHEMA_PATH)
    if _parse_time(snapshot["expires_at"]) <= observed:
        raise ValueError("Runtime capability snapshot is expired")
    eligible: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    for runtime in snapshot["runtimes"]:
        reasons = _rejection_reasons(runtime, request, now=observed)
        if reasons:
            rejections.append({"runtime_id": runtime["runtime_id"], "reason_codes": reasons})
        else:
            eligible.append(runtime)
    eligible.sort(key=lambda row: _ranking_key(row, request["consequence"]))
    selected = eligible[0]["runtime_id"] if eligible else ""
    fallback = eligible[1]["runtime_id"] if len(eligible) > 1 else ""
    digest = _canonical_hash(request)
    decision_material = {
        "request_digest": digest,
        "snapshot_id": snapshot["snapshot_id"],
        "selected": selected,
        "fallback": fallback,
    }
    decision = {
        "schema_version": "dad.runtime_route_decision.v1",
        "decision_id": f"dad:runtime-route:{_canonical_hash(decision_material).split(':', 1)[1]}",
        "request_id": str(request["request_id"]),
        "plan_revision_id": str(request["plan_revision_id"]),
        "harness_revision_id": str(request["harness_revision_id"]),
        "snapshot_id": snapshot["snapshot_id"],
        "status": "selected" if selected else "blocked",
        "selected_runtime_id": selected,
        "fallback_runtime_id": fallback,
        "eligible_runtime_ids": [row["runtime_id"] for row in eligible],
        "rejections": sorted(rejections, key=lambda row: row["runtime_id"]),
        "ranking_basis": (
            ["verification", "qualification", "reliability", "privacy", "cost", "latency", "stable_identity"]
            if request["consequence"] in {"large", "critical", "outlier"}
            else ["smallest_sufficient", "privacy", "cost", "latency", "reliability", "stable_identity"]
        ),
        "lease": {
            "lease_id": f"dad:runtime-lease:{_canonical_hash(decision_material).split(':', 1)[1]}",
            "request_digest": digest,
            "selected_runtime_id": selected,
            "expires_at": (observed + timedelta(minutes=30)).isoformat(),
            "maximum_attempts": 2,
            "fallback_permitted_before_side_effect": True,
        },
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    _validate(decision, repo_root / DECISION_SCHEMA_PATH)
    return decision


def resolve_fallback(
    decision: dict[str, Any],
    *,
    failed_runtime_id: str,
    attempts_used: int,
    side_effect_started: bool,
) -> dict[str, Any]:
    """Return the single preselected fallback or a deterministic block."""

    if side_effect_started:
        return {"status": "blocked", "reason": "side_effect_already_started"}
    if attempts_used != 1:
        return {"status": "blocked", "reason": "fallback_limit_exceeded"}
    if failed_runtime_id != decision.get("selected_runtime_id"):
        return {"status": "blocked", "reason": "failed_runtime_identity_mismatch"}
    fallback = str(decision.get("fallback_runtime_id", ""))
    if not fallback:
        return {"status": "blocked", "reason": "no_preauthorized_fallback"}
    return {
        "status": "fallback_selected",
        "runtime_id": fallback,
        "attempt_number": 2,
        "request_digest": decision["lease"]["request_digest"],
        "execution_authorized": False,
    }


__all__ = [
    "build_capability_snapshot",
    "load_adapter_registry",
    "resolve_fallback",
    "resolve_runtime",
]
