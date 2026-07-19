"""Operational envelope and foreground host for existing DAD cockpits.

The module reads only precomputed DAD projections.  It never scans a source
repository, appends an event, starts a daemon, or executes an operator action.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Lock
from typing import Any, Final

from jsonschema import FormatChecker, ValidationError
from jsonschema.validators import validator_for

from .transport import data_path
from .utils import atomic_write_text, json_dumps


SCHEMA_VERSION: Final = "dad.operational_cockpit.v1"
MAX_IMMEDIATE_DECISIONS: Final = 3
DEFAULT_STALE_AFTER_SECONDS: Final = 26 * 60 * 60
MAX_FUTURE_SKEW_SECONDS: Final = 5 * 60
MAX_DECISION_TEXT_LENGTH: Final = 240
MAX_EVIDENCE_REFS: Final = 10
LOOPBACK_HOST: Final = "127.0.0.1"
AUTHORITY_BOUNDARY: Final = (
    "This operational cockpit is a local read-only projection over precomputed DAD "
    "reports. It cannot scan or mutate a source repository, dispatch an agent, execute "
    "a request, activate a daemon, schedule work, or grant authority."
)


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    path: Path
    expected_schema: str
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
            "daemon",
            reports / "daemon-heartbeat.json",
            "dad.daemon.heartbeat.v1",
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
        value = json.loads(spec.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
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
    snapshot_body = {
        "sources": sources,
        "decisions": decisions,
        "event_pulse": _event_pulse(payloads.get("event_pipeline")),
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
    digest_body = {
        "sources": cockpit["sources"],
        "decisions": cockpit["decisions"],
        "event_pulse": cockpit["event_pulse"],
        "adapter_contract": cockpit["adapter_contract"],
    }
    expected_snapshot_id = (
        "dad:operational-cockpit:" + _canonical_digest(digest_body).split(":", 1)[1]
    )
    if cockpit["snapshot_id"] != expected_snapshot_id:
        raise ValueError("snapshot_id does not match snapshot body")


def operational_cockpit_html(cockpit: dict[str, Any]) -> str:
    summary = cockpit["summary"]
    decisions = (
        "".join(
            "<article class='decision'><p class='eyebrow'>Immediate review</p>"
            f"<h2>{escape(row['label'])}</h2><p>{escape(row['next_action'])}</p>"
            f"<p class='meta'>Source: {escape(row['source_id'])}</p></article>"
            for row in cockpit["decisions"]
        )
        or "<article class='decision'><h2>No immediate decision supplied</h2><p>Inspect partial or stale sources below before treating the portfolio as clear.</p></article>"
    )
    source_rows = "".join(
        "<tr>"
        f"<th scope='row'>{escape(source_id.replace('_', ' ').title())}</th>"
        f"<td><span class='status status-{escape(source['status'])}'>{escape(source['status'])}</span></td>"
        f"<td>{escape(source['freshness'])}</td>"
        f"<td>{escape(str(source['age_seconds']) if source['age_seconds'] is not None else 'unknown')}</td>"
        f"<td>{escape(', '.join(source['problems']) or 'none')}</td>"
        "</tr>"
        for source_id, source in cockpit["sources"].items()
    )
    status_text = (
        "All five precomputed sources are current. This remains candidate evidence."
        if summary["all_sources_current"]
        else "Some sources are missing, stale, or invalid. DAD is deliberately withholding an all-clear."
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; script-src 'none'; object-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'">
<meta name="dad-snapshot-id" content="{escape(cockpit["snapshot_id"])}"><title>DAD Operational Cockpit</title><style>
:root{{--bg:#071215;--panel:#102126;--line:#28444b;--text:#eef9f5;--muted:#9db8b3;--mint:#70e1bd;--amber:#ffd27a;--red:#ff9d9d}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 80% 0,#153f49 0,transparent 36%),var(--bg);color:var(--text);font:16px/1.55 system-ui,sans-serif}}
main{{width:min(1220px,94vw);margin:auto;padding:3rem 0 5rem}}h1{{font-size:clamp(2.3rem,7vw,5.5rem);line-height:.94;max-width:900px}}h2{{line-height:1.15}}.eyebrow{{color:var(--mint);text-transform:uppercase;letter-spacing:.12em;font-weight:800;font-size:.75rem}}.meta,.lede,caption{{color:var(--muted)}}
.summary,.decisions{{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem}}.metric,.decision,.table-wrap{{background:var(--panel);border:1px solid var(--line);border-radius:1rem;padding:1.1rem}}.metric strong{{font-size:2rem;display:block}}.table-wrap{{overflow:auto;margin-top:1.5rem;padding:0}}table{{width:100%;border-collapse:collapse}}caption{{text-align:left;padding:1rem}}th,td{{padding:.85rem 1rem;border-top:1px solid var(--line);text-align:left;vertical-align:top}}.status{{font-weight:800}}.status-observed{{color:var(--mint)}}.status-stale{{color:var(--amber)}}.status-invalid,.status-missing{{color:var(--red)}}
.notice{{border-left:.35rem solid var(--amber);padding:1rem;margin:1.5rem 0;background:var(--panel)}}:focus-visible{{outline:3px solid var(--amber);outline-offset:3px}}@media(max-width:850px){{.summary,.decisions{{grid-template-columns:1fr}}}}@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto!important}}}}
</style></head><body><main>
<p class="eyebrow">DAD · local operational envelope</p><h1>One human. Honest state. No hidden execution.</h1>
<p class="lede">A foreground, loopback-only view over existing portfolio, capability, daemon, and event evidence. Page requests never scan repositories.</p>
<div class="notice" role="status">{escape(status_text)}</div>
<section class="summary" aria-label="Source summary"><div class="metric"><strong>{summary["current_count"]}/{summary["source_count"]}</strong>current sources</div><div class="metric"><strong>{summary["stale_count"] + summary["missing_count"] + summary["invalid_count"]}</strong>source gaps</div><div class="metric"><strong>{summary["immediate_decision_count"]}</strong>immediate decisions</div></section>
<h2>Now</h2><section class="decisions" aria-label="Immediate decisions">{decisions}</section>
<div class="table-wrap"><table><caption>Source health and freshness; unknown state is never green.</caption><thead><tr><th scope="col">Source</th><th scope="col">Status</th><th scope="col">Freshness</th><th scope="col">Age (seconds)</th><th scope="col">Problems</th></tr></thead><tbody>{source_rows}</tbody></table></div>
<footer><p>Generated {escape(cockpit["generated_at"])}. Refresh the browser after an explicit snapshot rebuild.</p><p>{escape(cockpit["authority_boundary"])}</p></footer>
</main></body></html>"""


def write_operational_cockpit(hub_root: Path, cockpit: dict[str, Any]) -> dict[str, Any]:
    validate_operational_cockpit(hub_root, cockpit)
    root = data_path(hub_root, "central_reports") / "portfolio_os"
    html_path = root / "operational-cockpit.html"
    json_path = root / "operational-cockpit.json"
    receipt_path = root / "operational-cockpit.receipt.json"
    html_text = operational_cockpit_html(cockpit)
    json_text = json_dumps(cockpit, pretty=True) + "\n"
    atomic_write_text(html_path, html_text)
    atomic_write_text(json_path, json_text)
    receipt = {
        "schema_version": "dad.operational_cockpit.receipt.v1",
        "snapshot_id": cockpit["snapshot_id"],
        "json_digest": "sha256:" + sha256(json_text.encode("utf-8")).hexdigest(),
        "html_digest": "sha256:" + sha256(html_text.encode("utf-8")).hexdigest(),
    }
    atomic_write_text(receipt_path, json_dumps(receipt, pretty=True) + "\n")
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
            bundle = current_bundle()
            if bundle is None:
                self._send(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "application/json; charset=utf-8",
                    b'{"status":"unavailable_or_invalid"}\n',
                )
                return
            json_body, html_body, _cockpit = bundle
            if self.path in {"/", "/index.html"}:
                self._send(HTTPStatus.OK, "text/html; charset=utf-8", html_body)
            elif self.path == "/api/snapshot":
                self._send(HTTPStatus.OK, "application/json; charset=utf-8", json_body)
            elif self.path == "/healthz":
                body = (
                    json.dumps(
                        {
                            "status": "serving",
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
    "build_operational_cockpit",
    "build_operational_cockpit_server",
    "operational_cockpit_html",
    "validate_operational_cockpit",
    "write_operational_cockpit",
]
