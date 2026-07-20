"""Operational envelope and foreground host for existing DAD cockpits.

The module reads only precomputed DAD projections.  It never scans a source
repository, appends an event, starts a daemon, or executes an operator action.
"""

from __future__ import annotations

from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from threading import Lock
import time
from typing import Any, Final, Iterator

from jsonschema import FormatChecker, ValidationError
from jsonschema.validators import validator_for

from .logos_write_guard import assert_dad_write_allowed
from .transport import data_path
from .utils import atomic_write_text, json_dumps


SCHEMA_VERSION: Final = "dad.operational_cockpit.v1"
MAX_IMMEDIATE_DECISIONS: Final = 3
DEFAULT_STALE_AFTER_SECONDS: Final = 26 * 60 * 60
MAX_FUTURE_SKEW_SECONDS: Final = 5 * 60
MAX_DECISION_TEXT_LENGTH: Final = 240
MAX_EVIDENCE_REFS: Final = 10
MAX_SOURCE_BYTES: Final = 2_000_000
LOOPBACK_HOST: Final = "127.0.0.1"
PUBLICATION_LOCK_TIMEOUT_SECONDS: Final = 10.0
AUTHORITY_BOUNDARY: Final = (
    "This operational cockpit is a local read-only projection over precomputed DAD "
    "reports. It cannot scan or mutate a source repository, dispatch an agent, execute "
    "a request, activate a daemon, schedule work, or grant authority."
)

_PUBLICATION_THREAD_LOCKS: dict[str, Lock] = {}
_PUBLICATION_THREAD_LOCKS_GUARD = Lock()


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    path: Path
    expected_schema: str
    owner: str
    producer_ref: str
    human_approval_required: bool = False
    timestamp_fields: tuple[str, ...] = ("generated_at",)
    required_fields: tuple[str, ...] = ()
    field_types: tuple[tuple[str, type], ...] = ()
    required_values: tuple[tuple[str, Any], ...] = ()
    validation_schema: Path | None = None
    nonnegative_fields: tuple[str, ...] = ()


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + sha256(payload.encode("utf-8")).hexdigest()


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _source_specs(hub_root: Path) -> tuple[SourceSpec, ...]:
    reports = data_path(hub_root, "central_reports")
    portfolio = data_path(hub_root, "portfolio_reports")
    events = data_path(hub_root, "events")
    return (
        SourceSpec(
            "portfolio_v1",
            reports / "portfolio_os" / "cockpit.json",
            "dad.portfolio_cockpit.v1",
            "portfolio_os",
            "src/digital_asset_directory/portfolio_cockpit.py",
            required_fields=(
                "status",
                "sources",
                "summary",
                "today",
                "execution_authorized",
            ),
            field_types=(("status", str), ("sources", dict), ("summary", dict), ("today", list)),
            required_values=(("execution_authorized", False),),
            validation_schema=hub_root / "schemas/portfolio-cockpit.schema.json",
        ),
        SourceSpec(
            "portfolio_v2",
            reports / "portfolio_os" / "cockpit-v2.json",
            "dad.portfolio_cockpit.v2",
            "agent_family_portfolio",
            "src/digital_asset_directory/agent_families.py",
            required_fields=(
                "status",
                "sources",
                "summary",
                "now",
                "digest",
                "candidate_only",
                "execution_authorized",
            ),
            field_types=(
                ("status", str),
                ("sources", dict),
                ("summary", dict),
                ("now", list),
                ("digest", list),
            ),
            required_values=(("candidate_only", True), ("execution_authorized", False)),
            validation_schema=hub_root / "schemas/portfolio-cockpit-v2.schema.json",
        ),
        SourceSpec(
            "capability_os",
            portfolio / "capability-os-cockpit.json",
            "dad.capability_os_cockpit.v1",
            "capability_os",
            "src/digital_asset_directory/capability_os_cockpit.py",
            required_fields=(
                "cockpit_id",
                "views",
                "decisions",
                "controls",
                "candidate_only",
                "execution_authorized",
            ),
            field_types=(
                ("cockpit_id", str),
                ("views", dict),
                ("decisions", list),
                ("controls", list),
            ),
            required_values=(("candidate_only", True), ("execution_authorized", False)),
            validation_schema=hub_root / "schemas/capability-os-cockpit.schema.json",
        ),
        SourceSpec(
            "convergence_radar",
            reports / "portfolio_os" / "convergence-radar.json",
            "dad.portfolio_convergence_report.v1",
            "portfolio_convergence",
            "src/digital_asset_directory/portfolio_convergence_git.py",
            human_approval_required=True,
            required_fields=(
                "report_id",
                "summary",
                "proposals",
                "candidate_only",
                "execution_authorized",
            ),
            field_types=(
                ("report_id", str),
                ("summary", dict),
                ("proposals", list),
            ),
            required_values=(("candidate_only", True), ("execution_authorized", False)),
            validation_schema=(hub_root / "schemas/portfolio-convergence-report.schema.json"),
        ),
        SourceSpec(
            "daemon",
            reports / "daemon-heartbeat.json",
            "dad.daemon.heartbeat.v1",
            "transport_daemon",
            "docs/DAD_TRANSPORT_AND_COMMS_REDESIGN.md",
            True,
            ("cycle_completed_at",),
            ("status", "reporting_privacy", "authority_boundary", "heartbeat_finalized"),
            (
                ("status", str),
                ("reporting_privacy", dict),
                ("authority_boundary", str),
                ("heartbeat_finalized", bool),
            ),
            required_values=(("status", "complete"), ("heartbeat_finalized", True)),
        ),
        SourceSpec(
            "event_pipeline",
            events / "reports" / "event_pipeline.json",
            "dad.event_pipeline.report.v1",
            "event_pipeline",
            "docs/DAD_EVENT_PIPELINE.md",
            required_fields=(
                "event_count",
                "response_state_count",
                "notice_without_response_state_count",
                "authority_boundary",
            ),
            field_types=(
                ("event_count", int),
                ("response_state_count", int),
                ("notice_without_response_state_count", int),
                ("authority_boundary", str),
            ),
            nonnegative_fields=(
                "event_count",
                "response_state_count",
                "notice_without_response_state_count",
            ),
        ),
    )


def _load_source(
    spec: SourceSpec,
    *,
    now: datetime,
    stale_after_seconds: int,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    base = {
        "source_id": spec.source_id,
        "owner": spec.owner,
        "producer_ref": spec.producer_ref,
        "human_approval_required": spec.human_approval_required,
        "expected_schema": spec.expected_schema,
        "observed_schema": "",
        "status": "missing",
        "freshness": "unknown",
        "generated_at": "",
        "age_seconds": None,
        "fingerprint": "",
        "problems": ["source_missing"],
    }
    if not spec.path.is_file():
        return base, None
    try:
        with spec.path.open("rb") as source_file:
            source_bytes = source_file.read(MAX_SOURCE_BYTES + 1)
    except OSError:
        return {
            **base,
            "status": "invalid",
            "problems": ["source_unreadable_or_invalid_json"],
        }, None
    if len(source_bytes) > MAX_SOURCE_BYTES:
        return {
            **base,
            "status": "invalid",
            "problems": ["source_exceeds_read_budget"],
        }, None
    try:
        value = json.loads(source_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {
            **base,
            "status": "invalid",
            "problems": ["source_unreadable_or_invalid_json"],
        }, None
    if not isinstance(value, dict):
        return {**base, "status": "invalid", "problems": ["source_must_be_object"]}, None

    observed_schema = str(value.get("schema_version", ""))
    timestamp = next(
        (
            parsed
            for field in spec.timestamp_fields
            if (parsed := _parse_datetime(value.get(field))) is not None
        ),
        None,
    )
    if observed_schema != spec.expected_schema:
        return (
            {
                **base,
                "observed_schema": observed_schema,
                "status": "invalid",
                "generated_at": timestamp.isoformat() if timestamp else "",
                "fingerprint": _canonical_digest(value),
                "problems": ["schema_version_mismatch"],
            },
            None,
        )
    if spec.validation_schema is not None:
        try:
            source_schema = json.loads(spec.validation_schema.read_text(encoding="utf-8"))
            source_validator_cls = validator_for(source_schema)
            source_validator_cls.check_schema(source_schema)
            source_validator_cls(source_schema, format_checker=FormatChecker()).validate(value)
        except OSError:
            return (
                {
                    **base,
                    "observed_schema": observed_schema,
                    "status": "invalid",
                    "generated_at": timestamp.isoformat() if timestamp else "",
                    "fingerprint": _canonical_digest(value),
                    "problems": ["source_validation_schema_unavailable"],
                },
                None,
            )
        except (json.JSONDecodeError, ValidationError):
            return (
                {
                    **base,
                    "observed_schema": observed_schema,
                    "status": "invalid",
                    "generated_at": timestamp.isoformat() if timestamp else "",
                    "fingerprint": _canonical_digest(value),
                    "problems": ["authoritative_schema_validation_failed"],
                },
                None,
            )

    missing_fields = sorted(set(spec.required_fields) - set(value))
    if missing_fields:
        return (
            {
                **base,
                "observed_schema": observed_schema,
                "status": "invalid",
                "generated_at": timestamp.isoformat() if timestamp else "",
                "fingerprint": _canonical_digest(value),
                "problems": ["missing_required_fields:" + ",".join(missing_fields)],
            },
            None,
        )
    type_problems = [
        field
        for field, expected_type in spec.field_types
        if (expected_type is int and isinstance(value.get(field), bool))
        or not isinstance(value.get(field), expected_type)
    ]
    value_problems = [
        field
        for field, required_value in spec.required_values
        if value.get(field) != required_value
    ]
    range_problems = [field for field in spec.nonnegative_fields if value.get(field, 0) < 0]
    if type_problems or value_problems or range_problems:
        problems = []
        if type_problems:
            problems.append("invalid_field_types:" + ",".join(sorted(type_problems)))
        if value_problems:
            problems.append("authority_contract_violation:" + ",".join(sorted(value_problems)))
        if range_problems:
            problems.append("invalid_field_ranges:" + ",".join(sorted(range_problems)))
        return (
            {
                **base,
                "observed_schema": observed_schema,
                "status": "invalid",
                "generated_at": timestamp.isoformat() if timestamp else "",
                "fingerprint": _canonical_digest(value),
                "problems": problems,
            },
            None,
        )
    if timestamp is None:
        return (
            {
                **base,
                "observed_schema": observed_schema,
                "status": "invalid",
                "fingerprint": _canonical_digest(value),
                "problems": ["timestamp_missing_or_invalid"],
            },
            None,
        )

    delta_seconds = int((now - timestamp).total_seconds())
    if delta_seconds < -MAX_FUTURE_SKEW_SECONDS:
        return (
            {
                **base,
                "observed_schema": observed_schema,
                "status": "invalid",
                "generated_at": timestamp.isoformat(),
                "fingerprint": _canonical_digest(value),
                "problems": ["timestamp_too_far_in_future"],
            },
            None,
        )
    age_seconds = max(0, delta_seconds)
    stale = age_seconds > stale_after_seconds
    return (
        {
            **base,
            "observed_schema": observed_schema,
            "status": "stale" if stale else "observed",
            "freshness": "stale" if stale else "current",
            "generated_at": timestamp.isoformat(),
            "age_seconds": age_seconds,
            "fingerprint": _canonical_digest(value),
            "problems": ["source_stale"] if stale else [],
        },
        None if stale else value,
    )


def _decision_rows(payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[tuple[str, dict[str, Any]]] = []
    portfolio_v2 = payloads.get("portfolio_v2")
    if portfolio_v2:
        candidates.extend(("portfolio_v2", row) for row in portfolio_v2.get("now", []))
    capability = payloads.get("capability_os")
    if capability:
        candidates.extend(("capability_os", row) for row in capability.get("decisions", []))

    decisions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source_id, row in candidates:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or row.get("title") or "Review source evidence")[
            :MAX_DECISION_TEXT_LENGTH
        ]
        next_action = str(row.get("next_action") or row.get("recommended_action") or "inspect")[
            :MAX_DECISION_TEXT_LENGTH
        ]
        raw_refs = row.get("evidence_refs", [])
        evidence_refs = (
            sorted(
                {ref[:MAX_DECISION_TEXT_LENGTH] for ref in raw_refs if isinstance(ref, str) and ref}
            )[:MAX_EVIDENCE_REFS]
            if isinstance(raw_refs, list)
            else []
        )
        fingerprint = _canonical_digest(
            {
                "source_id": source_id,
                "label": label,
                "next_action": next_action,
                "evidence_refs": evidence_refs,
            }
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        decisions.append(
            {
                "decision_id": "dad:operational-decision:" + fingerprint.split(":", 1)[1],
                "source_id": source_id,
                "label": label,
                "next_action": next_action,
                "evidence_refs": evidence_refs,
                "execution_authorized": False,
            }
        )
        if len(decisions) == MAX_IMMEDIATE_DECISIONS:
            break
    return decisions


def _event_pulse(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {
            "event_count": None,
            "response_state_count": None,
            "unanswered_notice_count": None,
            "cursor_fingerprint": "",
        }
    counts = {
        "event_count": payload.get("event_count"),
        "response_state_count": payload.get("response_state_count"),
        "unanswered_notice_count": payload.get("notice_without_response_state_count"),
    }
    return {**counts, "cursor_fingerprint": _canonical_digest(counts)}


_PORTFOLIO_SCOPE_FIELDS: Final = (
    "project_count",
    "branch_count",
    "worktree_count",
    "workstream_count",
    "attention_item_count",
    "unknown_count",
    "unassigned_attention_count",
)


def _convergence_overview(
    sources: dict[str, dict[str, Any]],
    payloads: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source = sources["convergence_radar"]
    payload = payloads.get("convergence_radar")
    if payload is None:
        return {
            "availability": "unavailable",
            "source_id": "convergence_radar",
            "source_fingerprint": "",
            "candidate_count": None,
            "evaluated_pair_count": None,
            "top_candidates": [],
        }

    candidates: list[dict[str, Any]] = []
    for row in payload.get("proposals", [])[:5]:
        if not isinstance(row, dict):
            continue
        left = row.get("left", {})
        right = row.get("right", {})
        evidence = row.get("evidence", {})
        if not all(isinstance(value, dict) for value in (left, right, evidence)):
            continue
        shared_tokens = evidence.get("shared_name_tokens", [])
        candidates.append(
            {
                "proposal_id": str(row.get("proposal_id", ""))[:MAX_DECISION_TEXT_LENGTH],
                "project_name": str(row.get("project_name", ""))[:MAX_DECISION_TEXT_LENGTH],
                "left_branch": str(left.get("branch", ""))[:MAX_DECISION_TEXT_LENGTH],
                "right_branch": str(right.get("branch", ""))[:MAX_DECISION_TEXT_LENGTH],
                "priority_score": row.get("priority_score"),
                "evidence_band": str(row.get("evidence_band", "weak_review")),
                "shared_name_tokens": (
                    [str(value)[:120] for value in shared_tokens[:8]]
                    if isinstance(shared_tokens, list)
                    else []
                ),
                "shared_touched_path_count": evidence.get("shared_touched_path_count", 0),
                "merge_base_distance": evidence.get("merge_base_distance"),
                "next_action": (
                    "Inspect exact diffs and ownership, then decide combine, supersede, "
                    "resume, or keep separate. No action is authorized."
                ),
                "human_decision_required": True,
                "execution_authorized": False,
            }
        )
    summary = payload.get("summary", {})
    return {
        "availability": "current",
        "source_id": "convergence_radar",
        "source_fingerprint": source["fingerprint"],
        "candidate_count": summary.get("proposal_count"),
        "evaluated_pair_count": summary.get("evaluated_pair_count"),
        "top_candidates": candidates,
    }


def _operator_overview(
    sources: dict[str, dict[str, Any]],
    payloads: dict[str, dict[str, Any]],
    *,
    evidence_status: str,
) -> dict[str, Any]:
    portfolio_source = sources["portfolio_v1"]
    portfolio_payload = payloads.get("portfolio_v1")
    summary = portfolio_payload.get("summary", {}) if portfolio_payload else {}
    portfolio_scope = {
        "availability": "current" if portfolio_payload else "unavailable",
        "source_id": "portfolio_v1",
        "source_fingerprint": portfolio_source["fingerprint"] if portfolio_payload else "",
        **{
            field: summary.get(field) if portfolio_payload else None
            for field in _PORTFOLIO_SCOPE_FIELDS
        },
        "all_clear": summary.get("all_clear") if portfolio_payload else None,
    }
    source_actions = [
        {
            "source_id": source_id,
            "status": source["status"],
            "problems": source["problems"],
            "owner": source["owner"],
            "producer_ref": source["producer_ref"],
            "human_approval_required": source["human_approval_required"],
        }
        for source_id, source in sources.items()
        if source["status"] != "observed"
    ]
    return {
        "portfolio_scope": portfolio_scope,
        "convergence": _convergence_overview(sources, payloads),
        "readiness": {
            "evidence_status": evidence_status,
            "projection_renderable": True,
            "source_gap_count": len(source_actions),
            "source_actions": source_actions,
        },
    }


def build_operational_cockpit(
    hub_root: Path,
    *,
    now: datetime | None = None,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
) -> dict[str, Any]:
    """Compose precomputed report health without scanning or mutating a source repo."""

    if stale_after_seconds < 1:
        raise ValueError("stale_after_seconds must be positive")
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    sources: dict[str, dict[str, Any]] = {}
    payloads: dict[str, dict[str, Any]] = {}
    for spec in _source_specs(hub_root):
        descriptor, payload = _load_source(
            spec,
            now=observed,
            stale_after_seconds=stale_after_seconds,
        )
        sources[spec.source_id] = descriptor
        if payload is not None:
            payloads[spec.source_id] = payload

    current_count = sum(row["status"] == "observed" for row in sources.values())
    stale_count = sum(row["status"] == "stale" for row in sources.values())
    missing_count = sum(row["status"] == "missing" for row in sources.values())
    invalid_count = sum(row["status"] == "invalid" for row in sources.values())
    decisions = _decision_rows(payloads)
    status = "current_candidate" if current_count == len(sources) else "partial_candidate"
    adapter_contract = {
        "core_kind": "portable_core",
        "repo_contract_ref": ".digital-asset/dad-integration.json",
        "event_outbox_ref": ".digital-asset/events/outbox.jsonl",
        "normal_write_boundary": ".digital-asset/mail/**",
        "data_policy": "metadata_and_derived_health_only",
        "rollout": "reviewed_opt_in_enrollment_wave",
        "execution_authorized": False,
    }
    operator_overview = _operator_overview(sources, payloads, evidence_status=status)
    snapshot_body = {
        "sources": sources,
        "decisions": decisions,
        "event_pulse": _event_pulse(payloads.get("event_pipeline")),
        "operator_overview": operator_overview,
        "adapter_contract": adapter_contract,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": observed.isoformat(),
        "snapshot_id": "dad:operational-cockpit:"
        + _canonical_digest(snapshot_body).split(":", 1)[1],
        "status": status,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "refresh_model": "foreground_on_demand_plus_separately_gated_reconciliation",
        "local_bind": LOOPBACK_HOST,
        "external_javascript": False,
        "data_classification": "local_private_metadata",
        "summary": {
            "source_count": len(sources),
            "current_count": current_count,
            "stale_count": stale_count,
            "missing_count": missing_count,
            "invalid_count": invalid_count,
            "immediate_decision_count": len(decisions),
            "all_sources_current": status == "current_candidate",
        },
        **snapshot_body,
    }


def _schema_path(hub_root: Path) -> Path:
    return hub_root / "schemas" / "operational-cockpit.schema.json"


def validate_operational_cockpit(hub_root: Path, cockpit: dict[str, Any]) -> None:
    schema = json.loads(_schema_path(hub_root).read_text(encoding="utf-8"))
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema, format_checker=FormatChecker()).validate(cockpit)
    summary = cockpit["summary"]
    status_counts = {
        name: sum(source["status"] == name for source in cockpit["sources"].values())
        for name in ("observed", "stale", "missing", "invalid")
    }
    if sum(status_counts.values()) != summary["source_count"]:
        raise ValueError("source status counts must cover every source")
    expected = {
        "current_count": status_counts["observed"],
        "stale_count": status_counts["stale"],
        "missing_count": status_counts["missing"],
        "invalid_count": status_counts["invalid"],
        "immediate_decision_count": len(cockpit["decisions"]),
    }
    if any(summary[field] != value for field, value in expected.items()):
        raise ValueError("summary counts do not match cockpit contents")
    all_current = status_counts["observed"] == summary["source_count"]
    if summary["all_sources_current"] != all_current:
        raise ValueError("all_sources_current does not match source states")
    expected_status = "current_candidate" if all_current else "partial_candidate"
    if cockpit["status"] != expected_status:
        raise ValueError("cockpit status does not match source states")

    overview = cockpit["operator_overview"]
    readiness = overview["readiness"]
    expected_actions = [
        {
            "source_id": source_id,
            "status": source["status"],
            "problems": source["problems"],
            "owner": source["owner"],
            "producer_ref": source["producer_ref"],
            "human_approval_required": source["human_approval_required"],
        }
        for source_id, source in cockpit["sources"].items()
        if source["status"] != "observed"
    ]
    if (
        readiness["evidence_status"] != cockpit["status"]
        or readiness["source_gap_count"] != len(expected_actions)
        or readiness["source_actions"] != expected_actions
    ):
        raise ValueError("operator readiness does not match source states")
    portfolio_scope = overview["portfolio_scope"]
    portfolio_source = cockpit["sources"]["portfolio_v1"]
    if portfolio_source["status"] == "observed":
        if (
            portfolio_scope["availability"] != "current"
            or portfolio_scope["source_fingerprint"] != portfolio_source["fingerprint"]
        ):
            raise ValueError("portfolio scope provenance does not match current source")
    elif (
        portfolio_scope["availability"] != "unavailable"
        or portfolio_scope["source_fingerprint"]
        or any(portfolio_scope[field] is not None for field in _PORTFOLIO_SCOPE_FIELDS)
        or portfolio_scope["all_clear"] is not None
    ):
        raise ValueError("unavailable portfolio scope must not expose counts")
    convergence = overview["convergence"]
    convergence_source = cockpit["sources"]["convergence_radar"]
    if convergence_source["status"] == "observed":
        if (
            convergence["availability"] != "current"
            or convergence["source_fingerprint"] != convergence_source["fingerprint"]
            or convergence["candidate_count"] != len(convergence["top_candidates"])
            or convergence["evaluated_pair_count"] is None
            or any(row["execution_authorized"] for row in convergence["top_candidates"])
        ):
            raise ValueError("convergence overview does not match current source")
    elif (
        convergence["availability"] != "unavailable"
        or convergence["source_fingerprint"]
        or convergence["candidate_count"] is not None
        or convergence["evaluated_pair_count"] is not None
        or convergence["top_candidates"]
    ):
        raise ValueError("unavailable convergence overview must not expose candidate evidence")

    digest_body = {
        "sources": cockpit["sources"],
        "decisions": cockpit["decisions"],
        "event_pulse": cockpit["event_pulse"],
        "operator_overview": cockpit["operator_overview"],
        "adapter_contract": cockpit["adapter_contract"],
    }
    expected_snapshot_id = (
        "dad:operational-cockpit:" + _canonical_digest(digest_body).split(":", 1)[1]
    )
    if cockpit["snapshot_id"] != expected_snapshot_id:
        raise ValueError("snapshot_id does not match snapshot body")


def operational_cockpit_html(cockpit: dict[str, Any]) -> str:
    """Render a script-free, evidence-transparent one-human cockpit."""

    summary = cockpit["summary"]
    overview = cockpit["operator_overview"]
    portfolio = overview["portfolio_scope"]
    readiness = overview["readiness"]
    pulse = cockpit["event_pulse"]
    convergence = overview["convergence"]

    def display_count(value: Any) -> str:
        if isinstance(value, int) and not isinstance(value, bool):
            return escape(str(value))
        return "unknown"

    decisions = (
        "".join(
            "<article class='decision'><p class='eyebrow'>Immediate review</p>"
            f"<h3>{escape(row['label'])}</h3><p>{escape(row['next_action'])}</p>"
            f"<p class='meta'>Source: {escape(row['source_id'])}. Proposal only; no execution authority.</p>"
            "<details><summary>Evidence references</summary><ul>"
            + (
                "".join(f"<li><code>{escape(ref)}</code></li>" for ref in row["evidence_refs"])
                or "<li>No evidence references supplied.</li>"
            )
            + "</ul></details></article>"
            for row in cockpit["decisions"]
        )
        or "<article class='decision'><h3>No immediate decision supplied</h3>"
        "<p>Inspect partial or stale sources below before treating the portfolio as clear.</p></article>"
    )
    if convergence["availability"] == "current":
        convergence_cards = (
            "".join(
                "<article class='decision'><p class='eyebrow'>Convergence review</p>"
                f"<h3>{escape(row['project_name'])}</h3>"
                f"<p><code>{escape(row['left_branch'])}</code> &harr; "
                f"<code>{escape(row['right_branch'])}</code></p>"
                f"<p>{escape(row['next_action'])}</p>"
                "<p class='meta'>Priority "
                f"{escape(str(row['priority_score']))}; "
                f"{display_count(row['shared_touched_path_count'])} shared touched paths; "
                f"merge-base distance {display_count(row['merge_base_distance'])}. "
                "Ordinal evidence only.</p>"
                "<details><summary>Bounded evidence</summary>"
                f"<p>Shared name tokens: {escape(', '.join(row['shared_name_tokens']) or 'none')}.</p>"
                f"<p><code>{escape(row['proposal_id'])}</code></p></details></article>"
                for row in convergence["top_candidates"]
            )
            or "<article class='decision'><h3>No convergence candidate crossed the review threshold</h3>"
            "<p>This is evidence of a bounded evaluation, not proof that every branch is unrelated.</p></article>"
        )
    else:
        convergence_cards = (
            "<article class='decision'><h3>Convergence radar unavailable</h3>"
            "<p>Run <code>asset-dir os status</code>, then "
            "<code>asset-dir os convergence-radar</code>, and rebuild this cockpit. "
            "No repository action is implied.</p></article>"
        )

    source_rows = "".join(
        "<tr>"
        f"<th scope='row'>{escape(source_id.replace('_', ' ').title())}</th>"
        f"<td><span class='status status-{escape(source['status'])}'>{escape(source['status'])}</span></td>"
        f"<td>{escape(source['freshness'])}</td>"
        f"<td>{escape(str(source['age_seconds']) if source['age_seconds'] is not None else 'unknown')}</td>"
        f"<td>{escape(', '.join(source['problems']) or 'none')}</td>"
        f"<td>{escape(source['owner'])}<br><code>{escape(source['producer_ref'])}</code></td>"
        "</tr>"
        for source_id, source in cockpit["sources"].items()
    )
    status_text = (
        "All six precomputed sources are current. This remains candidate evidence."
        if summary["all_sources_current"]
        else "Some sources are missing, stale, or invalid. DAD is deliberately withholding an all-clear."
    )
    portfolio_metrics = "".join(
        f"<div class='metric'><strong>{display_count(portfolio[field])}</strong>{escape(label)}</div>"
        for field, label in (
            ("project_count", "projects"),
            ("branch_count", "branches"),
            ("worktree_count", "worktrees"),
            ("workstream_count", "workstreams"),
        )
    )
    uncertainty_metrics = "".join(
        f"<div class='metric'><strong>{display_count(portfolio[field])}</strong>{escape(label)}</div>"
        for field, label in (
            ("attention_item_count", "attention items"),
            ("unknown_count", "unknowns"),
            ("unassigned_attention_count", "unassigned"),
        )
    )
    source_actions = (
        "".join(
            "<li><strong>"
            + escape(row["source_id"].replace("_", " ").title())
            + "</strong>: "
            + escape(", ".join(row["problems"]))
            + f" <span class='meta'>Owner {escape(row['owner'])}; producer "
            + f"<code>{escape(row['producer_ref'])}</code>"
            + ("; human approval required" if row["human_approval_required"] else "")
            + "</span></li>"
            for row in readiness["source_actions"]
        )
        or "<li>No source remediation is currently required.</li>"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; script-src 'none'; object-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'">
<meta name="dad-snapshot-id" content="{escape(cockpit["snapshot_id"])}">
<title>DAD Operational Cockpit</title>
<style>
:root{{--bg:#071215;--panel:#102126;--line:#36565d;--text:#eef9f5;--muted:#afc7c2;--mint:#70e1bd;--amber:#ffd27a;--red:#ffaaaa;color-scheme:dark}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:radial-gradient(circle at 80% 0,#153f49 0,transparent 36%),var(--bg);color:var(--text);font:16px/1.55 system-ui,sans-serif}}
a.skip{{position:absolute;left:-999px;top:.5rem;background:#fff;color:#000;padding:.75rem;z-index:3}}a.skip:focus{{left:.5rem}}
main{{width:min(1320px,94vw);margin:auto;padding:3rem 0 5rem}}h1{{font-size:clamp(2.3rem,7vw,5.5rem);line-height:.94;max-width:980px}}h2{{line-height:1.15;margin-top:2.5rem}}h3{{line-height:1.2}}.eyebrow{{color:var(--mint);text-transform:uppercase;letter-spacing:.12em;font-weight:800;font-size:.75rem}}.meta,.lede,caption{{color:var(--muted)}}code{{overflow-wrap:anywhere}}
.section-nav{{position:sticky;top:0;z-index:2;display:flex;flex-wrap:wrap;gap:.5rem;padding:.75rem 0;background:var(--bg)}}.section-nav a{{color:var(--mint);border:1px solid var(--line);border-radius:999px;padding:.55rem .85rem;text-decoration:none}}
.summary,.decisions,.scope-grid,.pulse-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem}}.scope-grid{{grid-template-columns:repeat(4,1fr)}}.metric,.decision,.table-wrap,.panel{{background:var(--panel);border:1px solid var(--line);border-radius:1rem;padding:1.1rem}}.metric strong{{font-size:2rem;display:block}}.table-wrap{{overflow:auto;margin-top:1rem;padding:0}}table{{width:100%;border-collapse:collapse}}caption{{text-align:left;padding:1rem}}th,td{{padding:.85rem 1rem;border-top:1px solid var(--line);text-align:left;vertical-align:top}}
.status{{font-weight:800}}.status-observed{{color:var(--mint)}}.status-stale{{color:var(--amber)}}.status-invalid,.status-missing{{color:var(--red)}}details{{margin-top:1rem}}summary{{cursor:pointer;color:var(--mint);min-height:44px;padding:.6rem 0}}
.notice{{border-left:.35rem solid var(--amber);padding:1rem;margin:1.5rem 0;background:var(--panel)}}:focus-visible{{outline:3px solid var(--amber);outline-offset:3px}}
@media(max-width:900px){{.summary,.decisions,.scope-grid,.pulse-grid{{grid-template-columns:1fr 1fr}}}}@media(max-width:620px){{.summary,.decisions,.scope-grid,.pulse-grid{{grid-template-columns:1fr}}}}@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto!important}}}}@media(prefers-contrast:more){{:root{{--line:#b8d8d2;--muted:#d6e5e2}}}}
</style>
</head>
<body>
<a class="skip" href="#main">Skip to main content</a>
<main id="main">
<p class="eyebrow">DAD &middot; local operational envelope</p>
<h1>See the whole field. Act on only what is proven.</h1>
<p class="lede">A foreground, loopback-only view over existing portfolio, capability, daemon, and event evidence. Page requests never scan repositories.</p>
<nav class="section-nav" aria-label="Cockpit sections"><a href="#decisions">Now</a><a href="#portfolio">Portfolio</a><a href="#convergence">Convergence</a><a href="#signals">Signals</a><a href="#sources">Sources</a><a href="#contract">Authority</a></nav>
<div class="notice" role="status">{escape(status_text)}</div>
<section class="summary" aria-label="Source summary"><div class="metric"><strong>{summary["current_count"]}/{summary["source_count"]}</strong>current sources</div><div class="metric"><strong>{summary["stale_count"] + summary["missing_count"] + summary["invalid_count"]}</strong>source gaps</div><div class="metric"><strong>{summary["immediate_decision_count"]}</strong>immediate decisions</div></section>
<h2 id="decisions">Now</h2>
<section class="decisions" aria-label="Immediate decisions">{decisions}</section>
<h2 id="portfolio">Portfolio scope</h2>
<p class="meta">Available only from a current, schema-validated Portfolio v1 source. Unknown is never shown as zero.</p>
<section class="scope-grid" aria-label="Portfolio scope">{portfolio_metrics}</section>
<section class="summary" aria-label="Portfolio uncertainty">{uncertainty_metrics}</section>
<h2 id="convergence">Convergence candidates</h2>
<p class="meta">Top five deterministic review candidates from branch names, touched paths, and merge-base distance. Similarity never authorizes an action.</p>
<section class="decisions" aria-label="Convergence candidates">{convergence_cards}</section>
<h2 id="signals">Operational signals</h2>
<section class="pulse-grid" aria-label="Event pulse"><div class="metric"><strong>{display_count(pulse["event_count"])}</strong>events</div><div class="metric"><strong>{display_count(pulse["response_state_count"])}</strong>responses</div><div class="metric"><strong>{display_count(pulse["unanswered_notice_count"])}</strong>unanswered notices</div></section>
<h2 id="sources">Source readiness</h2>
<section class="panel"><p><strong>{readiness["source_gap_count"]}</strong> source gaps. Serving coherence and evidence currency are separate: this page may be safely served while its evidence remains partial.</p><ol>{source_actions}</ol></section>
<div class="table-wrap"><table><caption>Source health and freshness; unknown state is never green.</caption><thead><tr><th scope="col">Source</th><th scope="col">Status</th><th scope="col">Freshness</th><th scope="col">Age (seconds)</th><th scope="col">Problems</th><th scope="col">Owner and producer</th></tr></thead><tbody>{source_rows}</tbody></table></div>
<footer id="contract"><p>Generated <time datetime="{escape(cockpit["generated_at"])}">{escape(cockpit["generated_at"])}</time>. Refresh the browser after an explicit snapshot rebuild.</p><p>{escape(cockpit["authority_boundary"])}</p></footer>
</main>
</body>
</html>"""


def _thread_lock_for(path: Path) -> Lock:
    key = os.path.normcase(str(path.resolve(strict=False)))
    with _PUBLICATION_THREAD_LOCKS_GUARD:
        return _PUBLICATION_THREAD_LOCKS.setdefault(key, Lock())


@contextmanager
def _publication_lock(root: Path) -> Iterator[None]:
    """Serialize a complete cockpit publication across threads and processes."""

    lock_path = root / ".operational-cockpit.publish.lock"
    assert_dad_write_allowed(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + PUBLICATION_LOCK_TIMEOUT_SECONDS
    thread_lock = _thread_lock_for(lock_path)
    if not thread_lock.acquire(timeout=PUBLICATION_LOCK_TIMEOUT_SECONDS):
        raise TimeoutError(f"Timed out acquiring cockpit publication lock: {lock_path}")
    descriptor: int | None = None
    acquired = False
    try:
        descriptor = os.open(
            str(lock_path),
            os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0),
            0o600,
        )
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b"0")
            os.fsync(descriptor)
        while not acquired:
            try:
                if os.name == "nt":
                    import msvcrt

                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out acquiring cockpit publication lock: {lock_path}")
                time.sleep(0.01)
        yield
    finally:
        if descriptor is not None:
            if acquired:
                with suppress(OSError):
                    if os.name == "nt":
                        import msvcrt

                        os.lseek(descriptor, 0, os.SEEK_SET)
                        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
        thread_lock.release()


def write_operational_cockpit(hub_root: Path, cockpit: dict[str, Any]) -> dict[str, Any]:
    validate_operational_cockpit(hub_root, cockpit)
    root = data_path(hub_root, "central_reports") / "portfolio_os"
    html_path = root / "operational-cockpit.html"
    json_path = root / "operational-cockpit.json"
    receipt_path = root / "operational-cockpit.receipt.json"
    html_text = operational_cockpit_html(cockpit)
    json_text = json_dumps(cockpit, pretty=True) + "\n"
    receipt = {
        "schema_version": "dad.operational_cockpit.receipt.v1",
        "snapshot_id": cockpit["snapshot_id"],
        "json_digest": "sha256:" + sha256(json_text.encode("utf-8")).hexdigest(),
        "html_digest": "sha256:" + sha256(html_text.encode("utf-8")).hexdigest(),
    }
    paths = (html_path, json_path, receipt_path)
    with _publication_lock(root):
        previous: dict[Path, str | None] = {}
        for path in paths:
            previous[path] = path.read_text(encoding="utf-8") if path.exists() else None
        try:
            atomic_write_text(html_path, html_text)
            atomic_write_text(json_path, json_text)
            atomic_write_text(receipt_path, json_dumps(receipt, pretty=True) + "\n")
        except Exception as exc:
            rollback_errors: list[str] = []
            for path in paths:
                try:
                    prior = previous[path]
                    if prior is None:
                        assert_dad_write_allowed(path)
                        path.unlink(missing_ok=True)
                    else:
                        atomic_write_text(path, prior)
                except OSError as rollback_exc:
                    rollback_errors.append(f"{path.name}:{type(rollback_exc).__name__}")
            if rollback_errors:
                raise OSError(
                    "Operational cockpit publication failed and rollback was incomplete: "
                    + ", ".join(rollback_errors)
                ) from exc
            raise
    return {
        "html_path": str(html_path),
        "json_path": str(json_path),
        "receipt_path": str(receipt_path),
        "status": cockpit["status"],
        "summary": cockpit["summary"],
        "execution_authorized": False,
    }


def _validated_bundle(
    hub_root: Path, snapshot_path: Path, html_path: Path, receipt_path: Path
) -> tuple[bytes, bytes, dict[str, Any]] | None:
    try:
        json_body = snapshot_path.read_bytes()
        html_body = html_path.read_bytes()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        cockpit = json.loads(json_body)
        validate_operational_cockpit(hub_root, cockpit)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError):
        return None
    if (
        not isinstance(receipt, dict)
        or receipt.get("schema_version") != "dad.operational_cockpit.receipt.v1"
    ):
        return None
    if (
        receipt.get("snapshot_id") != cockpit.get("snapshot_id")
        or receipt.get("json_digest") != "sha256:" + sha256(json_body).hexdigest()
        or receipt.get("html_digest") != "sha256:" + sha256(html_body).hexdigest()
        or cockpit["snapshot_id"].encode("utf-8") not in html_body
    ):
        return None
    return json_body, html_body, cockpit


def _handler(
    hub_root: Path, snapshot_path: Path, html_path: Path, receipt_path: Path
) -> type[BaseHTTPRequestHandler]:
    bundle_lock = Lock()
    last_valid_bundle = _validated_bundle(hub_root, snapshot_path, html_path, receipt_path)

    def current_bundle() -> tuple[bytes, bytes, dict[str, Any]] | None:
        nonlocal last_valid_bundle
        candidate = _validated_bundle(hub_root, snapshot_path, html_path, receipt_path)
        with bundle_lock:
            if candidate is not None:
                last_valid_bundle = candidate
            return last_valid_bundle

    class CockpitRequestHandler(BaseHTTPRequestHandler):
        server_version = "DADOperationalCockpit/1"

        def _send(
            self,
            status: HTTPStatus,
            content_type: str,
            body: bytes = b"",
            *,
            allow: str | None = None,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'",
            )
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            if allow is not None:
                self.send_header("Allow", allow)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            allowed_hosts = {
                LOOPBACK_HOST,
                f"{LOOPBACK_HOST}:{self.server.server_port}",
            }
            if self.headers.get("Host", "") not in allowed_hosts:
                self._send(
                    HTTPStatus.MISDIRECTED_REQUEST,
                    "application/json; charset=utf-8",
                    b'{"status":"host_not_allowed"}\n',
                )
                return
            bundle = current_bundle()
            if bundle is None:
                self._send(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "application/json; charset=utf-8",
                    b'{"status":"unavailable_or_invalid"}\n',
                )
                return
            json_body, html_body, cockpit = bundle
            if self.path in {"/", "/index.html"}:
                self._send(HTTPStatus.OK, "text/html; charset=utf-8", html_body)
            elif self.path == "/api/snapshot":
                self._send(HTTPStatus.OK, "application/json; charset=utf-8", json_body)
            elif self.path == "/healthz":
                body = (
                    json.dumps(
                        {
                            "status": "serving",
                            "serving_status": "coherent",
                            "evidence_status": cockpit["status"],
                            "snapshot_id": cockpit["snapshot_id"],
                            "source_summary": cockpit["summary"],
                            "bind": LOOPBACK_HOST,
                            "execution_authorized": False,
                        },
                        sort_keys=True,
                    ).encode("utf-8")
                    + b"\n"
                )
                self._send(HTTPStatus.OK, "application/json; charset=utf-8", body)
            else:
                self._send(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"not found\n")

        def do_HEAD(self) -> None:  # noqa: N802
            self.do_GET()

        def _deny_mutation(self) -> None:
            self._send(
                HTTPStatus.METHOD_NOT_ALLOWED,
                "text/plain; charset=utf-8",
                b"read only\n",
                allow="GET, HEAD",
            )

        do_POST = _deny_mutation
        do_PUT = _deny_mutation
        do_PATCH = _deny_mutation
        do_DELETE = _deny_mutation
        do_OPTIONS = _deny_mutation
        do_TRACE = _deny_mutation
        do_CONNECT = _deny_mutation
        do_MKCOL = _deny_mutation
        do_PROPFIND = _deny_mutation
        do_PROPPATCH = _deny_mutation
        do_COPY = _deny_mutation
        do_MOVE = _deny_mutation
        do_LOCK = _deny_mutation
        do_UNLOCK = _deny_mutation

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    return CockpitRequestHandler


def build_operational_cockpit_server(
    hub_root: Path,
    *,
    host: str = LOOPBACK_HOST,
    port: int = 8765,
) -> ThreadingHTTPServer:
    if host != LOOPBACK_HOST:
        raise ValueError(f"operational cockpit host must bind {LOOPBACK_HOST}")
    if not 0 <= port <= 65535:
        raise ValueError("port must be between 0 and 65535")
    root = data_path(hub_root, "central_reports") / "portfolio_os"
    server = ThreadingHTTPServer(
        (host, port),
        _handler(
            hub_root,
            root / "operational-cockpit.json",
            root / "operational-cockpit.html",
            root / "operational-cockpit.receipt.json",
        ),
    )
    server.daemon_threads = True
    return server


__all__ = [
    "AUTHORITY_BOUNDARY",
    "LOOPBACK_HOST",
    "MAX_SOURCE_BYTES",
    "build_operational_cockpit",
    "build_operational_cockpit_server",
    "operational_cockpit_html",
    "validate_operational_cockpit",
    "write_operational_cockpit",
]
