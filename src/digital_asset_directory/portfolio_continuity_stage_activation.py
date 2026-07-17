"""Append-only, revision-bound human approval evidence for later attention stages.

The control plane can make a stage *authorized* only inside the exact approval
scope.  It never delivers a prompt, schedules work, mutates tasks or Git, or
authorizes cleanup.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import FormatChecker
from jsonschema.validators import validator_for

from .portfolio_continuity_events import (
    ContinuityIntegrityError,
    ContinuityValidationError,
    _append_record_exact,
)
from .portfolio_continuity_trial import validate_activation_state
from .transport import data_path, resolve_data_root


APPROVABLE_STAGE_IDS = (
    "session_start_summary",
    "weekly_changed_only_digest",
    "breakpoint_prompts",
)
STAGE_ORDER = (
    "manual",
    "supervised_silent_shadow",
    *APPROVABLE_STAGE_IDS,
)
DECISIONS = ("approve", "revoke", "kill")
AUTHORITY_BOUNDARY = (
    "Stage approval records are operator-attested, revision-bound evidence for one "
    "named attention stage only. They cannot deliver content, schedule work, invoke "
    "models, mutate Git or tasks, archive work, clean up worktrees, authorize general "
    "execution, or bypass a predecessor stage, expiry, rollback, or kill decision."
)
STATE_AUTHORITY_BOUNDARY = (
    "The stage activation state is a deterministic candidate projection of exact "
    "approval records. Scoped stage authorization does not deliver anything, grant "
    "general execution authority, or permit automatic cleanup."
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ContinuityValidationError("stage approval time must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _schema_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / name


@lru_cache(maxsize=2)
def _validator(name: str) -> Any:
    schema = json.loads(_schema_path(name).read_text(encoding="utf-8"))
    validator_class = validator_for(schema)
    validator_class.check_schema(schema)
    return validator_class(schema, format_checker=FormatChecker())


def _validate(value: Any, schema_name: str) -> None:
    problems: list[str] = []
    for error in sorted(
        _validator(schema_name).iter_errors(value), key=lambda item: list(item.path)
    ):
        path = "$" + "".join(f"[{part!r}]" for part in error.path)
        problems.append(f"{path}: {error.message}")
    if problems:
        raise ContinuityValidationError("; ".join(problems))


def eligibility_state_digest(state: Mapping[str, Any]) -> str:
    """Digest stable trial and host evidence, excluding the observation clock."""

    validate_activation_state(state)
    material = {key: value for key, value in state.items() if key != "evaluated_at"}
    return "sha256:" + hashlib.sha256(
        _canonical(material).encode("utf-8")
    ).hexdigest()


def validate_stage_approval(record: Any) -> None:
    _validate(record, "portfolio-continuity-stage-approval.schema.json")
    material = {
        key: value
        for key, value in record.items()
        if key not in {"approval_event_id", "schema_version", "authority_boundary"}
    }
    expected = "dad:continuity-stage-approval:" + hashlib.sha256(
        _canonical(material).encode("utf-8")
    ).hexdigest()
    if record["approval_event_id"] != expected:
        raise ContinuityValidationError(
            "approval_event_id does not match stage approval material"
        )
    if _parse_time(str(record["valid_until"])) <= _parse_time(
        str(record["recorded_at"])
    ):
        raise ContinuityValidationError("stage approval valid_until must be later")


def validate_stage_activation_state(state: Any) -> None:
    _validate(state, "portfolio-continuity-stage-activation-state.schema.json")
    material = {key: value for key, value in state.items() if key != "state_digest"}
    expected = "sha256:" + hashlib.sha256(
        _canonical(material).encode("utf-8")
    ).hexdigest()
    if state["state_digest"] != expected:
        raise ContinuityValidationError(
            "stage activation state digest does not match material"
        )


def _stage_approval_record(
    *,
    stage_id: str,
    decision: str,
    approved_by: str,
    approval_ref: str,
    trial_id: str,
    eligibility_state_digest: str,
    adapter_interface_digest: str,
    predecessor_approval_event_id: str,
    rollback_criteria: Sequence[str],
    kill_criteria: Sequence[str],
    recorded_at: str,
    valid_until: str,
    fixture_only: bool,
) -> dict[str, Any]:
    material = {
        "stage_id": stage_id,
        "decision": decision,
        "approved_by": approved_by,
        "approval_ref": approval_ref,
        "trial_id": trial_id,
        "eligibility_state_digest": eligibility_state_digest,
        "adapter_interface_digest": adapter_interface_digest,
        "predecessor_approval_event_id": predecessor_approval_event_id,
        "rollback_criteria": sorted(set(rollback_criteria)),
        "kill_criteria": sorted(set(kill_criteria)),
        "recorded_at": recorded_at,
        "valid_until": valid_until,
        "fixture_only": fixture_only,
        "operator_attested": True,
        "stage_activation_authority_only": True,
        "execution_authorized": False,
        "automatic_cleanup_allowed": False,
    }
    record = {
        "schema_version": "dad.portfolio_continuity_stage_approval.v1",
        "approval_event_id": "dad:continuity-stage-approval:"
        + hashlib.sha256(_canonical(material).encode("utf-8")).hexdigest(),
        **material,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    validate_stage_approval(record)
    return record


def build_fixture_stage_approval(**kwargs: Any) -> dict[str, Any]:
    """Build synthetic approval evidence that can never authorize a real stage."""

    return _stage_approval_record(**kwargs, fixture_only=True)


def stage_approval_ledger_path(hub_root: Path) -> Path:
    return data_path(hub_root, "raw_portfolio_intents") / "continuity-stage-approvals.jsonl"


def record_stage_approval(
    hub_root: Path,
    *,
    stage_id: str,
    decision: str,
    approved_by: str,
    approval_ref: str,
    trial_id: str,
    eligibility_state_digest: str,
    adapter_interface_digest: str,
    predecessor_approval_event_id: str,
    rollback_criteria: Sequence[str],
    kill_criteria: Sequence[str],
    valid_until: str,
) -> dict[str, Any]:
    """Append one operator-attested record using the production process clock."""

    record = _stage_approval_record(
        stage_id=stage_id,
        decision=decision,
        approved_by=approved_by,
        approval_ref=approval_ref,
        trial_id=trial_id,
        eligibility_state_digest=eligibility_state_digest,
        adapter_interface_digest=adapter_interface_digest,
        predecessor_approval_event_id=predecessor_approval_event_id,
        rollback_criteria=rollback_criteria,
        kill_criteria=kill_criteria,
        recorded_at=_utc_now().isoformat(),
        valid_until=valid_until,
        fixture_only=False,
    )
    _root, mode = resolve_data_root(hub_root)
    if mode != "data_root":
        raise ContinuityIntegrityError(
            "Stage approval writes require an initialized DAD_DATA_ROOT"
        )
    status = _append_record_exact(
        stage_approval_ledger_path(hub_root),
        record,
        identity_field="approval_event_id",
    )
    return {"status": status, "approval": record}


def read_stage_approvals(hub_root: Path) -> list[dict[str, Any]]:
    _root, mode = resolve_data_root(hub_root)
    if mode != "data_root":
        raise ContinuityIntegrityError(
            "Stage approval reads require an initialized DAD_DATA_ROOT"
        )
    path = stage_approval_ledger_path(hub_root)
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        try:
            record = json.loads(raw)
            validate_stage_approval(record)
        except (json.JSONDecodeError, ContinuityValidationError) as exc:
            raise ContinuityIntegrityError(
                f"invalid stage approval at line {line_number}: {exc}"
            ) from exc
        event_id = str(record["approval_event_id"])
        if event_id in seen:
            raise ContinuityIntegrityError(f"duplicate stage approval: {event_id}")
        seen[event_id] = record
        records.append(record)
    return records


def fold_stage_activation(
    approvals: Sequence[Mapping[str, Any]],
    *,
    activation_state: Mapping[str, Any],
    adapter_interface_digest: str,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    """Project ordered stage authority without performing any stage effect."""

    validate_activation_state(activation_state)
    evaluated = _parse_time(evaluated_at) if evaluated_at else _utc_now()
    eligibility_digest = eligibility_state_digest(activation_state)
    latest: dict[str, dict[str, Any]] = {}
    seen_event_ids: dict[str, dict[str, Any]] = {}
    fixture_count = 0
    for approval in approvals:
        validate_stage_approval(approval)
        event_id = str(approval["approval_event_id"])
        if event_id in seen_event_ids:
            raise ContinuityIntegrityError(f"duplicate stage approval: {event_id}")
        seen_event_ids[event_id] = dict(approval)
        if approval["fixture_only"]:
            fixture_count += 1
            continue
        stage_id = str(approval["stage_id"])
        # Input order is immutable ledger append order. A later safety decision
        # must win even if its producer clock moved backwards.
        latest[stage_id] = dict(approval)

    trial_eligible = activation_state["status"] == "eligible_for_human_activation"
    stages: list[dict[str, Any]] = [
        {
            "stage_id": "manual",
            "order": 1,
            "status": "active",
            "activation_authorized": True,
            "approval_event_id": "",
            "valid_until": "",
            "rollback_criteria": [],
            "kill_criteria": [],
            "gate_failures": [],
        },
        {
            "stage_id": "supervised_silent_shadow",
            "order": 2,
            "status": str(activation_state["status"]),
            "activation_authorized": trial_eligible,
            "approval_event_id": "",
            "valid_until": "",
            "rollback_criteria": [],
            "kill_criteria": [],
            "gate_failures": list(activation_state["gate_failures"]),
        },
    ]
    predecessor_active = trial_eligible
    predecessor_event_id = ""
    for order, stage_id in enumerate(APPROVABLE_STAGE_IDS, start=3):
        record = latest.get(stage_id)
        failures: list[str] = []
        status = "separate_human_approval_required"
        authorized = False
        if not predecessor_active:
            status = "blocked_by_predecessor_stage"
            failures.append("predecessor_stage_not_active")
        elif record is None:
            failures.append("stage_approval_missing")
        elif _parse_time(str(record["recorded_at"])) > evaluated:
            status = "invalid_future_record"
            failures.append("stage_approval_recorded_after_evaluation")
        elif (
            record["trial_id"] != activation_state["trial_id"]
            or record["eligibility_state_digest"] != eligibility_digest
            or record["adapter_interface_digest"] != adapter_interface_digest
        ):
            status = "stale_binding"
            failures.append("stage_approval_binding_stale")
        elif record["predecessor_approval_event_id"] != predecessor_event_id:
            status = "predecessor_binding_mismatch"
            failures.append("predecessor_approval_binding_mismatch")
        elif record["decision"] == "revoke":
            status = "revoked"
            failures.append("stage_approval_revoked")
        elif record["decision"] == "kill":
            status = "killed"
            failures.append("stage_kill_switch_engaged")
        elif _parse_time(str(record["valid_until"])) <= evaluated:
            status = "expired"
            failures.append("stage_approval_expired")
        else:
            status = "active"
            authorized = True
        stages.append(
            {
                "stage_id": stage_id,
                "order": order,
                "status": status,
                "activation_authorized": authorized,
                "approval_event_id": str(record["approval_event_id"]) if record else "",
                "valid_until": str(record["valid_until"]) if record else "",
                "rollback_criteria": list(record["rollback_criteria"]) if record else [],
                "kill_criteria": list(record["kill_criteria"]) if record else [],
                "gate_failures": sorted(set(failures)),
            }
        )
        predecessor_active = authorized
        predecessor_event_id = (
            str(record["approval_event_id"]) if authorized and record else ""
        )

    state: dict[str, Any] = {
        "schema_version": "dad.portfolio_continuity_stage_activation_state.v1",
        "evaluated_at": evaluated.isoformat(),
        "trial_id": str(activation_state["trial_id"]),
        "eligibility_state_digest": eligibility_digest,
        "adapter_interface_digest": adapter_interface_digest,
        "stages": stages,
        "fixture_approval_count": fixture_count,
        "automatic_cleanup_allowed": False,
        "execution_authorized": False,
        "authority_boundary": STATE_AUTHORITY_BOUNDARY,
    }
    state["state_digest"] = "sha256:" + hashlib.sha256(
        _canonical(state).encode("utf-8")
    ).hexdigest()
    validate_stage_activation_state(state)
    return state


__all__ = [
    "APPROVABLE_STAGE_IDS",
    "AUTHORITY_BOUNDARY",
    "DECISIONS",
    "STAGE_ORDER",
    "build_fixture_stage_approval",
    "eligibility_state_digest",
    "fold_stage_activation",
    "read_stage_approvals",
    "record_stage_approval",
    "stage_approval_ledger_path",
    "validate_stage_activation_state",
    "validate_stage_approval",
]
