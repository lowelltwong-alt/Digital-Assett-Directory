"""Research-to-skill intake pipeline.

External research findings enter a quarantine folder, pass named screening checks,
and become library entries only through a human-approved promotion that writes
pointer artifacts - never copies of external content. Trusted-source tiers lower
friction (intake without extra justification); they never skip screening or the
human approval gate.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .ids import stable_id
from .utils import append_jsonl, atomic_write_text, json_dumps, utc_now

TRUSTED_SOURCE_REGISTRY = Path("registry") / "trusted-source-registry.json"
INTAKE_DIR = Path("processed") / "research" / "intake"
POINTER_ASSET_DIR = Path("assets") / "external"
SCREENING_CHECKS = ("prompt_injection", "license", "provenance", "compatibility")
SCREENING_RESULTS = {"pass", "fail", "not_applicable", "not_run"}
INTAKE_KINDS = {"skill", "harness", "asset", "lesson", "doc"}
PROMOTION_TARGETS = {"offering", "skill_pointer"}
INTAKE_AUTHORITY_BOUNDARY = (
    "Intake records are quarantined candidate metadata about external sources. "
    "They carry links, provenance, and screening state only - never external file "
    "contents - and do not authorize checkout, install, or downstream delivery."
)
KIND_TO_OFFERING_TYPE = {
    "harness": "harness",
    "asset": "asset",
    "lesson": "best_practice",
    "doc": "best_practice",
}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json_dumps(payload, pretty=True) + "\n")


def _slug(value: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:60] or "item"


def _audit(hub_root: Path, event: dict[str, Any]) -> None:
    created = str(event.get("created_at") or utc_now())
    append_jsonl(hub_root / "audit" / "events" / f"{created[:10]}.jsonl", event)


def load_trusted_sources(hub_root: Path) -> dict[str, Any]:
    return _load_json(hub_root / TRUSTED_SOURCE_REGISTRY)


def match_trusted_source(hub_root: Path, source_url: str) -> tuple[dict[str, Any] | None, str]:
    """Match a URL against the trusted-source registry by domain/prefix patterns."""
    normalized = source_url.lower().strip()
    for scheme in ("https://", "http://"):
        if normalized.startswith(scheme):
            normalized = normalized[len(scheme):]
    normalized = normalized.rstrip("/")
    try:
        registry = load_trusted_sources(hub_root)
    except FileNotFoundError:
        return None, "unknown"
    for source in registry.get("sources", []):
        for pattern in source.get("url_patterns", []):
            cleaned = str(pattern).lower().strip().rstrip("/")
            if normalized == cleaned or normalized.startswith(cleaned + "/"):
                return source, str(source.get("trust_tier", "known"))
    return None, "unknown"


def _intake_path(hub_root: Path, intake_id: str, name: str) -> Path:
    return hub_root / INTAKE_DIR / f"{_slug(name)}-{intake_id.rsplit(':', 1)[-1][:8]}.json"


def _find_intake(hub_root: Path, intake_id: str) -> tuple[Path, dict[str, Any]]:
    for path in sorted((hub_root / INTAKE_DIR).glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("intake_id") == intake_id:
            return path, payload
    raise ValueError(f"Unknown intake record: {intake_id}")


def intake_external_candidate(
    hub_root: Path,
    *,
    name: str,
    kind: str,
    source_url: str,
    research_ref: str = "",
    license_name: str = "",
    notes: str = "",
    justification: str = "",
) -> dict[str, Any]:
    if kind not in INTAKE_KINDS:
        raise ValueError("kind must be one of: " + ", ".join(sorted(INTAKE_KINDS)))
    if not source_url.strip():
        raise ValueError("source_url is required")
    source, tier = match_trusted_source(hub_root, source_url)
    if tier == "unknown" and not justification.strip():
        raise ValueError(
            "Source is not in the trusted-source registry. Provide --justification "
            "explaining why this source is worth quarantining, or add the source to "
            "registry/trusted-source-registry.json via human review first."
        )
    created = utc_now()
    intake_id = stable_id("research-intake", name, source_url, created)
    record = {
        "schema_version": "0.1.0",
        "intake_id": intake_id,
        "created_at": created,
        "name": name,
        "kind": kind,
        "source_url": source_url,
        "source_id": str(source.get("source_id", "")) if source else "",
        "trust_tier": tier,
        "trust_note": (
            "Trust tier lowers intake friction only; screening and human approval "
            "are still required before promotion."
        ),
        "justification": justification,
        "research_ref": research_ref,
        "license": license_name,
        "notes": notes,
        "status": "quarantined",
        "screening": {check: {"result": "not_run", "notes": "", "screened_by": ""} for check in SCREENING_CHECKS},
        "approval": {"approved_by": "", "approval_id": "", "decided_at": ""},
        "promotion": {},
        "authority_boundary": INTAKE_AUTHORITY_BOUNDARY,
    }
    path = _intake_path(hub_root, intake_id, name)
    _write_json(path, record)
    _audit(
        hub_root,
        {
            "event_type": "research_intake_quarantined",
            "created_at": created,
            "intake_id": intake_id,
            "name": name,
            "source_url": source_url,
            "trust_tier": tier,
        },
    )
    return {"intake": record, "path": str(path)}


def record_screening(
    hub_root: Path,
    intake_id: str,
    *,
    check: str,
    result: str,
    notes: str = "",
    screened_by: str = "agent",
) -> dict[str, Any]:
    if check not in SCREENING_CHECKS:
        raise ValueError("check must be one of: " + ", ".join(SCREENING_CHECKS))
    if result not in SCREENING_RESULTS - {"not_run"}:
        raise ValueError("result must be pass, fail, or not_applicable")
    path, record = _find_intake(hub_root, intake_id)
    if record.get("status") == "promoted":
        raise ValueError("Cannot re-screen a promoted intake record")
    record["screening"][check] = {"result": result, "notes": notes, "screened_by": screened_by}
    results = {item["result"] for item in record["screening"].values()}
    if "fail" in results:
        record["status"] = "quarantined"
    elif results <= {"pass", "not_applicable"}:
        record["status"] = "screened"
    _write_json(path, record)
    _audit(
        hub_root,
        {
            "event_type": "research_intake_screened",
            "created_at": utc_now(),
            "intake_id": intake_id,
            "check": check,
            "result": result,
            "status": record["status"],
        },
    )
    return {"intake": record, "path": str(path)}


def _pointer_markdown(record: dict[str, Any], *, approval_id: str) -> str:
    return "\n".join(
        [
            f"# External pointer: {record['name']}",
            "",
            f"- Kind: {record['kind']}",
            f"- Source: {record['source_url']}",
            f"- Source ID / trust tier: {record.get('source_id') or 'unregistered'} / {record['trust_tier']}",
            f"- License: {record.get('license') or 'review upstream'}",
            f"- Research ref: {record.get('research_ref') or 'none'}",
            f"- Intake: {record['intake_id']}",
            f"- Approval: {approval_id}",
            "",
            record.get("notes", ""),
            "",
            "This is a pointer artifact. The asset lives at the source URL; DAD stores no",
            "copy of external content. Re-run screening if the upstream changes, and use",
            "checkout mode `pointer` only.",
            "",
        ]
    )


def promote_intake(
    hub_root: Path,
    intake_id: str,
    *,
    approved_by: str,
    approval_id: str,
    target: str,
    capabilities: list[str] | None = None,
    task_types: list[str] | None = None,
) -> dict[str, Any]:
    if target not in PROMOTION_TARGETS:
        raise ValueError("target must be one of: " + ", ".join(sorted(PROMOTION_TARGETS)))
    if not approved_by.strip() or approved_by.strip().lower() in {"agent", "unknown"}:
        raise ValueError("promotion requires a named human in approved_by")
    if not approval_id.strip():
        raise ValueError("promotion requires an approval_id")
    path, record = _find_intake(hub_root, intake_id)
    if record.get("status") != "screened":
        raise ValueError(
            f"Intake status is '{record.get('status')}'; all screening checks must pass "
            "before promotion"
        )
    from .dad_library import check_offering_novelty

    novelty = check_offering_novelty(
        hub_root, name=record["name"], capabilities=capabilities or [record["kind"]]
    )
    if novelty["verdict"] in {"duplicate", "possible_duplicate"}:
        raise ValueError(
            f"Offer-check verdict is {novelty['verdict']} of "
            f"{novelty['matches'][0]['offering_id']}; reject this intake, rename it, or "
            "route it as a known_upgrades entry instead of a new promotion."
        )
    slug = _slug(record["name"])
    pointer_dir = hub_root / POINTER_ASSET_DIR / slug
    pointer_path = pointer_dir / "POINTER.md"
    pointer_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(pointer_path, _pointer_markdown(record, approval_id=approval_id))
    today = utc_now()[:10]
    review_due = (
        datetime.now(timezone.utc) + timedelta(days=90)
    ).date().isoformat()
    registry_ref = ""
    if target == "offering":
        registry_path = hub_root / "registry" / "dad-offerings-registry.json"
        registry = _load_json(registry_path)
        offering_id = f"dad:offering:external-{slug}"
        if any(item["offering_id"] == offering_id for item in registry["offerings"]):
            raise ValueError(f"Offering already exists: {offering_id}")
        registry["offerings"].append(
            {
                "offering_id": offering_id,
                "name": record["name"],
                "version": "0.1.0",
                "offering_type": KIND_TO_OFFERING_TYPE.get(record["kind"], "best_practice"),
                "path": f"assets/external/{slug}",
                "languages": [],
                "repo_types": [],
                "domains": [],
                "context_tags": ["external_pointer", record["kind"]],
                "task_types": task_types or ["coding"],
                "capabilities": capabilities or [record["kind"]],
                "applies_when": [record.get("notes") or f"A task matches {record['name']}."],
                "does_not_apply_when": [
                    "The upstream source changed since the last screening pass."
                ],
                "public_safe": False,
                "upgrade_channel": "manual_review",
                "known_upgrades": [],
                "source_refs": [record["source_url"], f"assets/external/{slug}/POINTER.md"],
                "review_status": "reviewed",
                "authority_boundary": (
                    "External pointer offering; re-screen upstream changes before reuse "
                    "and never copy external content into repos."
                ),
            }
        )
        _write_json(registry_path, registry)
        registry_ref = f"registry/dad-offerings-registry.json#{offering_id}"
    else:
        registry_path = hub_root / "registry" / "agent-skill-library.json"
        registry = _load_json(registry_path)
        skill_id = f"skill:external-{slug}"
        if any(item["skill_id"] == skill_id for item in registry["skills"]):
            raise ValueError(f"Skill already exists: {skill_id}")
        registry["skills"].append(
            {
                "skill_id": skill_id,
                "name": record["name"],
                "version": "0.1.0",
                "status": "active",
                "skill_format": "pointer_only",
                "path": f"assets/external/{slug}",
                "entrypoint": f"assets/external/{slug}/POINTER.md",
                "description": record.get("notes") or f"External pointer skill for {record['name']}.",
                "trigger_examples": [f"A task matches {record['name']} ({record['kind']})."],
                "does_not_apply_when": [
                    "The upstream source changed since the last screening pass."
                ],
                "capabilities": capabilities or [record["kind"]],
                "checkout_modes": ["pointer"],
                "update_policy": "manual_review",
                "lifecycle": {
                    "supersedes": [],
                    "superseded_by": [],
                    "retirement_reason": "",
                    "replacement_skill_id": "",
                    "change_notice_templates": [],
                },
                "dependencies": [],
                "source_evidence": [record["source_url"], f"assets/external/{slug}/POINTER.md"],
                "authority_boundary": (
                    "External pointer skill; checkout mode pointer only, and re-screen "
                    "upstream changes before reuse."
                ),
                "review_status": "reviewed",
                "last_reviewed_at": today,
                "next_review_due_at": review_due,
            }
        )
        _write_json(registry_path, registry)
        registry_ref = f"registry/agent-skill-library.json#{skill_id}"
    record["status"] = "promoted"
    record["approval"] = {
        "approved_by": approved_by,
        "approval_id": approval_id,
        "decided_at": utc_now(),
    }
    record["promotion"] = {
        "target": target,
        "registry_ref": registry_ref,
        "pointer_path": f"assets/external/{slug}/POINTER.md",
        "novelty_verdict": novelty["verdict"],
    }
    _write_json(path, record)
    _audit(
        hub_root,
        {
            "event_type": "research_intake_promoted",
            "created_at": record["approval"]["decided_at"],
            "intake_id": intake_id,
            "target": target,
            "registry_ref": registry_ref,
            "approved_by": approved_by,
            "approval_id": approval_id,
        },
    )
    return {"intake": record, "registry_ref": registry_ref, "pointer_path": str(pointer_path)}


def list_intake(hub_root: Path, *, status: str = "") -> dict[str, Any]:
    records = []
    intake_dir = hub_root / INTAKE_DIR
    if intake_dir.exists():
        for path in sorted(intake_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if status and payload.get("status") != status:
                continue
            records.append(
                {
                    "intake_id": payload.get("intake_id"),
                    "name": payload.get("name"),
                    "kind": payload.get("kind"),
                    "trust_tier": payload.get("trust_tier"),
                    "status": payload.get("status"),
                    "source_url": payload.get("source_url"),
                }
            )
    return {
        "intake_count": len(records),
        "records": records,
        "authority_boundary": INTAKE_AUTHORITY_BOUNDARY,
    }
