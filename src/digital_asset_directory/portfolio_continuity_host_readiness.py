"""Fail-closed Codex host readiness for the supervised continuity shadow."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import FormatChecker
from jsonschema.validators import validator_for

from .portfolio_continuity_codex_hook import (
    CODEX_HOOK_ADAPTER_ID,
    CODEX_HOOK_ADAPTER_REVISION_ID,
    read_codex_hook_failures,
)
from .portfolio_continuity_events import (
    ContinuityIntegrityError,
    _append_record_exact,
    continuity_ledger_path,
    read_observation_events,
)
from .portability_control import canonical_digest, runtime_adapter_interface_digest
from .transport import data_path, resolve_data_root


SCHEMA_VERSION = "dad.intent_continuity_host_readiness.v1"
ADAPTER_ARTIFACT_ID = "adapter:intent-continuity-codex-host"
EXPECTED_EVENTS = {"SessionStart", "PreCompact", "PostCompact", "Stop"}
EXPECTED_EVENT_KINDS = {
    "session_started",
    "interruption_observed",
    "resumption_observed",
    "turn_stopped",
}
TRUST_STATUSES = {"unverified", "trusted", "untrusted"}
DISCOVERY_STATUSES = {"unverified", "discovered", "not_discovered"}
AUTHORITY_BOUNDARY = (
    "Host readiness is read-only candidate evidence. It cannot trust a project or "
    "hook, authenticate host origin, bypass Codex review, run a hook, activate "
    "prompts or notifications, "
    "schedule work, mutate Git or tasks, archive work, or clean up a worktree."
)


class HostReadinessError(ValueError):
    """The host-readiness assessment cannot be built safely."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _aware_datetime(value: str, *, field: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HostReadinessError(f"{field} must be an ISO 8601 date-time") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HostReadinessError(f"{field} must include a timezone offset")
    return parsed.isoformat()


def _repository_layout(repo_root: Path) -> str:
    marker = repo_root / ".git"
    if marker.is_file():
        return "linked_worktree"
    if marker.is_dir():
        return "primary_worktree"
    return "unknown"


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HostReadinessError(f"{label} is unavailable or invalid") from exc
    if not isinstance(value, dict):
        raise HostReadinessError(f"{label} must contain one JSON object")
    return value


def _file_digest(path: Path) -> str:
    """Hash exact bytes so a host-triggering file change cannot be normalized away."""

    try:
        content = path.read_bytes()
    except OSError as exc:
        raise HostReadinessError("Codex hook definition is unavailable") from exc
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _load_adapter_card(repo_root: Path) -> dict[str, Any]:
    registry = _load_json(
        repo_root / "registry/portable-capability-registry.json",
        label="portable capability registry",
    )
    matches = [
        card
        for card in registry.get("cards", [])
        if isinstance(card, dict) and card.get("artifact_id") == ADAPTER_ARTIFACT_ID
    ]
    if len(matches) != 1:
        raise HostReadinessError("Expected one registered Codex continuity adapter")
    return matches[0]


def _enabled_hook_events(hook_document: Mapping[str, Any]) -> list[str]:
    hooks = hook_document.get("hooks")
    if not isinstance(hooks, dict):
        return []
    enabled: list[str] = []
    for event_name, groups in hooks.items():
        if not isinstance(event_name, str) or not isinstance(groups, list):
            continue
        if any(
            isinstance(group, dict)
            and isinstance(group.get("hooks"), list)
            and any(
                isinstance(handler, dict) and handler.get("type") == "command"
                for handler in group["hooks"]
            )
            for group in groups
        ):
            enabled.append(event_name)
    return sorted(set(enabled))


def _validate_assessment(repo_root: Path, assessment: Mapping[str, Any]) -> None:
    schema = _load_json(
        repo_root / "schemas/intent-continuity-host-readiness.schema.json",
        label="host-readiness schema",
    )
    validator_class = validator_for(schema)
    validator_class.check_schema(schema)
    errors = sorted(
        validator_class(schema, format_checker=FormatChecker()).iter_errors(
            dict(assessment)
        ),
        key=lambda error: list(error.path),
    )
    if errors:
        rendered = "; ".join(
            f"{list(error.path)}: {error.message}" for error in errors
        )
        raise HostReadinessError("Invalid host-readiness assessment: " + rendered)


def validate_host_readiness_assessment(
    repo_root: Path, assessment: Mapping[str, Any]
) -> None:
    """Validate one immutable host-readiness assessment and its digest."""

    _validate_assessment(repo_root, assessment)
    material = {
        key: value for key, value in assessment.items() if key != "assessment_digest"
    }
    if assessment.get("assessment_digest") != canonical_digest(material):
        raise HostReadinessError("assessment_digest does not match assessment material")


def host_readiness_ledger_path(hub_root: Path) -> Path:
    return data_path(hub_root, "raw_portfolio_intents") / "continuity-host-readiness.jsonl"


def read_host_readiness_assessments(
    repo_root: Path, hub_root: Path
) -> list[dict[str, Any]]:
    """Read validated private host-readiness evidence without inferring trust."""

    _root, mode = resolve_data_root(hub_root)
    if mode != "data_root":
        raise ContinuityIntegrityError(
            "Host-readiness evidence requires an initialized DAD_DATA_ROOT"
        )
    path = host_readiness_ledger_path(hub_root)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ContinuityIntegrityError(
                f"invalid host-readiness JSON at line {line_number}"
            ) from exc
        if not isinstance(value, dict):
            raise ContinuityIntegrityError(
                f"non-object host-readiness row at line {line_number}"
            )
        try:
            validate_host_readiness_assessment(repo_root, value)
        except HostReadinessError as exc:
            raise ContinuityIntegrityError(
                f"invalid host-readiness row at line {line_number}: {exc}"
            ) from exc
        assessment_id = str(value["assessment_digest"])
        prior = seen.get(assessment_id)
        if prior is not None:
            if prior != value:
                raise ContinuityIntegrityError(
                    f"conflicting host-readiness assessment: {assessment_id}"
                )
            raise ContinuityIntegrityError(
                f"duplicate host-readiness assessment: {assessment_id}"
            )
        seen[assessment_id] = value
        rows.append(value)
    return rows


def latest_host_readiness_assessment(
    repo_root: Path, hub_root: Path
) -> dict[str, Any] | None:
    root = repo_root.resolve()
    integration = _load_json(
        root / ".digital-asset/dad-integration.json",
        label="DAD integration contract",
    )
    repository_id = str(integration.get("repo_id", ""))
    rows = [
        row
        for row in read_host_readiness_assessments(root, hub_root)
        if row.get("repository_id") == repository_id
    ]
    if not rows:
        return None
    return max(
        rows,
        key=lambda row: (
            datetime.fromisoformat(str(row["assessed_at"]).replace("Z", "+00:00")),
            str(row["assessment_digest"]),
        ),
    )


def record_host_readiness_assessment(
    repo_root: Path, hub_root: Path, assessment: Mapping[str, Any]
) -> str:
    """Append one explicitly requested assessment to the private evidence ledger."""

    root = repo_root.resolve()
    validate_host_readiness_assessment(root, assessment)
    integration = _load_json(
        root / ".digital-asset/dad-integration.json",
        label="DAD integration contract",
    )
    if assessment.get("repository_id") != integration.get("repo_id"):
        raise ContinuityIntegrityError(
            "Host-readiness recording repository does not match the local contract"
        )
    _root, mode = resolve_data_root(hub_root)
    if mode != "data_root":
        raise ContinuityIntegrityError(
            "Host-readiness recording requires an initialized DAD_DATA_ROOT"
        )
    return _append_record_exact(
        host_readiness_ledger_path(hub_root),
        dict(assessment),
        identity_field="assessment_digest",
    )


def host_readiness_recording_failures(
    repo_root: Path, hub_root: Path, assessment: Mapping[str, Any]
) -> list[str]:
    """Require exact private-ledger membership without granting readiness."""

    validate_host_readiness_assessment(repo_root, assessment)
    recorded = read_host_readiness_assessments(repo_root, hub_root)
    if dict(assessment) not in recorded:
        return ["host_readiness_not_recorded"]
    latest = latest_host_readiness_assessment(repo_root, hub_root)
    return [] if latest == dict(assessment) else ["host_readiness_not_latest_recorded"]


def host_readiness_binding_failures(
    repo_root: Path, assessment: Mapping[str, Any]
) -> list[str]:
    """Compare recorded evidence with the exact current repository binding."""

    root = repo_root.resolve()
    validate_host_readiness_assessment(root, assessment)
    failures: list[str] = []
    integration = _load_json(
        root / ".digital-asset/dad-integration.json",
        label="DAD integration contract",
    )
    if assessment.get("repository_id") != integration.get("repo_id"):
        failures.append("host_readiness_repository_mismatch")
    adapter = assessment.get("adapter_binding", {})
    adapter_card = _load_adapter_card(root)
    if adapter.get("adapter_revision_id") != CODEX_HOOK_ADAPTER_REVISION_ID:
        failures.append("host_readiness_adapter_revision_stale")
    if adapter.get("portability_card_revision_id") != adapter_card.get("revision_id"):
        failures.append("host_readiness_portability_card_revision_stale")
    current_interface = runtime_adapter_interface_digest(root, ADAPTER_ARTIFACT_ID)
    if (
        adapter_card.get("adapter_interface_digest") != current_interface
        or
        adapter.get("declared_interface_digest") != current_interface
        or adapter.get("computed_interface_digest") != current_interface
        or adapter.get("interface_digest_matches") is not True
    ):
        failures.append("host_readiness_interface_binding_stale")
    hook = assessment.get("hook_definition", {})
    if hook.get("definition_digest") != _file_digest(root / ".codex/hooks.json"):
        failures.append("host_readiness_hook_definition_stale")
    dispatch = assessment.get("dispatch_evidence", {})
    if (
        assessment.get("status") != "ready_for_supervised_trial"
        or assessment.get("gate_failures")
        or dispatch.get("status") != "operator_attested"
        or dispatch.get("attested_event_found") is not True
        or dispatch.get("temporal_binding_valid") is not True
        or dispatch.get("origin_authenticated") is not False
    ):
        failures.append("host_readiness_not_ready")
    return sorted(set(failures))


def build_codex_host_readiness(
    repo_root: Path,
    hub_root: Path,
    *,
    project_trust_status: str = "unverified",
    hook_trust_status: str = "unverified",
    hook_discovery_status: str = "unverified",
    reviewed_hook_definition_digest: str = "",
    reviewer_id: str = "",
    reviewed_at: str = "",
    dispatch_observer_id: str = "",
    dispatch_attested_at: str = "",
    attested_event_id: str = "",
    codex_version: str = "",
    assessed_at: str | None = None,
) -> dict[str, Any]:
    """Assess trust, discovery, and dispatch without granting or simulating them."""

    root = repo_root.resolve()
    for label, value, allowed in (
        ("project_trust_status", project_trust_status, TRUST_STATUSES),
        ("hook_trust_status", hook_trust_status, TRUST_STATUSES),
        ("hook_discovery_status", hook_discovery_status, DISCOVERY_STATUSES),
    ):
        if value not in allowed:
            raise HostReadinessError(f"{label} is invalid")
    if any(len(value) > 120 for value in (reviewer_id, dispatch_observer_id, codex_version)):
        raise HostReadinessError(
            "reviewer_id, dispatch_observer_id, or codex_version is too long"
        )
    observed_review_at = (
        _aware_datetime(reviewed_at, field="reviewed_at") if reviewed_at else ""
    )
    observed_dispatch_attested_at = (
        _aware_datetime(dispatch_attested_at, field="dispatch_attested_at")
        if dispatch_attested_at
        else ""
    )
    observed_assessed_at = _aware_datetime(
        assessed_at or _utc_now(), field="assessed_at"
    )

    integration = _load_json(
        root / ".digital-asset/dad-integration.json",
        label="DAD integration contract",
    )
    repository_id = str(integration.get("repo_id", ""))
    if not repository_id:
        raise HostReadinessError("DAD integration contract has no repo_id")
    hook_path = root / ".codex/hooks.json"
    hook_document = _load_json(hook_path, label="Codex hook definition")
    hook_digest = _file_digest(hook_path)
    enabled_events = _enabled_hook_events(hook_document)
    shadow_config = _load_json(
        root / "config/intent-continuity-shadow-hooks.json",
        label="intent-continuity shadow config",
    )
    activation_gate = shadow_config.get("activation_gate", {})
    host_gate_configured = isinstance(activation_gate, dict) and all(
        (
            activation_gate.get("host_readiness_schema")
            == "schemas/intent-continuity-host-readiness.schema.json",
            activation_gate.get("project_trust_attestation_required") is True,
            activation_gate.get("exact_hook_trust_attestation_required") is True,
            activation_gate.get("real_codex_dispatch_required") is True,
            activation_gate.get("recorded_host_readiness_required") is True,
            activation_gate.get("linked_worktree_discovery_must_be_observed") is True,
        )
    )

    card = _load_adapter_card(root)
    declared_interface_digest = str(card.get("adapter_interface_digest", ""))
    computed_interface_digest = runtime_adapter_interface_digest(
        root, ADAPTER_ARTIFACT_ID
    )
    interface_matches = declared_interface_digest == computed_interface_digest

    current_events = [
        event
        for event in read_observation_events(continuity_ledger_path(hub_root))
        if event.get("adapter_id") == CODEX_HOOK_ADAPTER_ID
        and event.get("adapter_revision_id") == CODEX_HOOK_ADAPTER_REVISION_ID
        and event.get("source_kind") == "runtime_hook"
        and event.get("event_kind") in EXPECTED_EVENT_KINDS
        and isinstance(event.get("payload"), dict)
        and event["payload"].get("repository_id") == repository_id
    ]
    current_failures = [
        marker
        for marker in read_codex_hook_failures(hub_root)
        if marker.get("adapter_revision_id") == CODEX_HOOK_ADAPTER_REVISION_ID
        and marker.get("repository_id") == repository_id
    ]
    latest_dispatch_at = (
        max(str(event.get("observed_at", "")) for event in current_events)
        if current_events
        else ""
    )
    attestable_events = [
        {
            "event_id": str(event["event_id"]),
            "observed_at": str(event["observed_at"]),
            "event_kind": str(event["event_kind"]),
        }
        for event in sorted(
            current_events,
            key=lambda event: (str(event["observed_at"]), str(event["event_id"])),
        )[-5:]
    ]

    attestation_supplied = bool(
        reviewer_id and observed_review_at and reviewed_hook_definition_digest
    )
    reviewed_digest_matches = reviewed_hook_definition_digest == hook_digest
    dispatch_attestation_supplied = bool(
        dispatch_observer_id and observed_dispatch_attested_at and attested_event_id
    )
    attested_event = next(
        (
            event
            for event in current_events
            if event.get("event_id") == attested_event_id
        ),
        None,
    )
    temporal_binding_valid = False
    if attested_event is not None and observed_review_at and observed_dispatch_attested_at:
        reviewed_dt = datetime.fromisoformat(observed_review_at)
        event_dt = datetime.fromisoformat(str(attested_event["observed_at"]).replace("Z", "+00:00"))
        dispatch_attested_dt = datetime.fromisoformat(observed_dispatch_attested_at)
        assessed_dt = datetime.fromisoformat(observed_assessed_at)
        temporal_binding_valid = (
            reviewed_dt <= event_dt <= dispatch_attested_dt <= assessed_dt
        )
    dispatch_attestation_valid = bool(
        dispatch_attestation_supplied and attested_event is not None and temporal_binding_valid
    )
    layout = _repository_layout(root)

    failures: list[str] = []
    if set(enabled_events) != EXPECTED_EVENTS:
        failures.append("hook_event_set_not_exact")
    if shadow_config.get("status") != "supervised_silent_shadow":
        failures.append("shadow_config_not_supervised")
    if not host_gate_configured:
        failures.append("host_readiness_gate_not_configured")
    if not interface_matches:
        failures.append("adapter_interface_digest_mismatch")
    if project_trust_status != "trusted":
        failures.append("project_trust_not_attested")
    if hook_trust_status != "trusted":
        failures.append("exact_hook_trust_not_attested")
    if hook_discovery_status != "discovered":
        failures.append("project_hook_discovery_not_attested")
    if not attestation_supplied:
        failures.append("host_review_attestation_missing")
    if attestation_supplied and not reviewed_digest_matches:
        failures.append("reviewed_hook_definition_digest_mismatch")
    if not current_events:
        failures.append("real_codex_dispatch_not_observed")
    if not dispatch_attestation_supplied:
        failures.append("supervised_dispatch_attestation_missing")
    if dispatch_attestation_supplied and attested_event is None:
        failures.append("attested_dispatch_event_not_found")
    if dispatch_attestation_supplied and attested_event is not None and not temporal_binding_valid:
        failures.append("dispatch_attestation_temporal_mismatch")
    if current_failures:
        failures.append("hook_failure_markers_observed")

    linked_discovery_risk = layout == "linked_worktree" and not dispatch_attestation_valid
    if linked_discovery_risk:
        failures.append("linked_worktree_dispatch_unverified")

    actions: list[str] = []
    if project_trust_status != "trusted":
        actions.append("Open a Codex task rooted in this repository and review project trust.")
    if hook_trust_status != "trusted" or hook_discovery_status != "discovered":
        actions.append("Open /hooks, inspect the exact current command hooks, and trust only that definition.")
    if not attestation_supplied or not reviewed_digest_matches:
        actions.append("Record the reviewer, review time, and current hook-definition digest after Codex review.")
    if not current_events:
        actions.append(
            "Observe a supervised Codex lifecycle event and rerun this assessment; the ledger alone does not authenticate host origin."
        )
    if not dispatch_attestation_valid:
        actions.append(
            "After observing the host event, attest its exact event ID and time; ledger origin is not cryptographically authenticated."
        )
    if linked_discovery_risk:
        actions.append(
            "Treat linked-worktree hook discovery as unverified until an exact event ID is operator-attested."
        )
    if current_failures:
        actions.append("Review all content-free hook failure markers before starting the production trial.")

    material: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "assessed_at": observed_assessed_at,
        "repository_id": repository_id,
        "repository_layout": layout,
        "hook_definition": {
            "relative_path": ".codex/hooks.json",
            "definition_digest": hook_digest,
            "enabled_events": enabled_events,
            "event_set_exact": set(enabled_events) == EXPECTED_EVENTS,
            "shadow_status": str(shadow_config.get("status", "unknown")),
            "host_readiness_gate_configured": host_gate_configured,
        },
        "adapter_binding": {
            "artifact_id": ADAPTER_ARTIFACT_ID,
            "adapter_revision_id": CODEX_HOOK_ADAPTER_REVISION_ID,
            "portability_card_revision_id": str(card.get("revision_id", "")),
            "declared_interface_digest": declared_interface_digest,
            "computed_interface_digest": computed_interface_digest,
            "interface_digest_matches": interface_matches,
        },
        "host_observation": {
            "codex_version": codex_version,
            "project_trust_status": project_trust_status,
            "hook_trust_status": hook_trust_status,
            "hook_discovery_status": hook_discovery_status,
            "attestation_origin": (
                "operator_supplied" if attestation_supplied else "not_supplied"
            ),
            "reviewer_id": reviewer_id,
            "reviewed_at": observed_review_at,
            "reviewed_hook_definition_digest": reviewed_hook_definition_digest,
            "reviewed_digest_matches": reviewed_digest_matches,
        },
        "dispatch_evidence": {
            "status": (
                "operator_attested"
                if dispatch_attestation_valid
                else "observed_unattested"
                if current_events
                else "unverified"
            ),
            "current_revision_event_count": len(current_events),
            "latest_observed_at": latest_dispatch_at,
            "current_revision_failure_marker_count": len(current_failures),
            "linked_worktree_discovery_risk": linked_discovery_risk,
            "dispatch_attestation_origin": (
                "operator_supplied"
                if dispatch_attestation_supplied
                else "not_supplied"
            ),
            "dispatch_observer_id": dispatch_observer_id,
            "dispatch_attested_at": observed_dispatch_attested_at,
            "attested_event_id": attested_event_id,
            "attested_event_found": attested_event is not None,
            "temporal_binding_valid": temporal_binding_valid,
            "origin_authenticated": False,
            "verification_method": "operator_attested_event_id",
            "attestable_events": attestable_events,
        },
        "status": "ready_for_supervised_trial" if not failures else "not_ready",
        "gate_failures": sorted(set(failures)),
        "human_actions_required": actions,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    assessment = {
        **material,
        "assessment_digest": canonical_digest(material),
    }
    _validate_assessment(root, assessment)
    return assessment


__all__ = [
    "ADAPTER_ARTIFACT_ID",
    "AUTHORITY_BOUNDARY",
    "DISCOVERY_STATUSES",
    "EXPECTED_EVENTS",
    "HostReadinessError",
    "SCHEMA_VERSION",
    "TRUST_STATUSES",
    "build_codex_host_readiness",
    "host_readiness_binding_failures",
    "host_readiness_ledger_path",
    "host_readiness_recording_failures",
    "latest_host_readiness_assessment",
    "read_host_readiness_assessments",
    "record_host_readiness_assessment",
    "validate_host_readiness_assessment",
]
