"""Model-neutral agent-family registry, routing, health, pilots, and cockpit v2.

All projections are read-only candidate evidence. The module does not dispatch
agents, mutate source repositories, activate schedules, or approve lifecycle,
security, privacy, legal, deployment, or release decisions.
"""

from __future__ import annotations

from collections import Counter, deque
from datetime import datetime, timezone
from html import escape
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Any, Iterable

import yaml
from jsonschema import FormatChecker
from jsonschema.validators import validator_for

from .transport import data_path
from .utils import atomic_write_text, json_dumps


REGISTRY_PATH = Path("registry/agent-family-portfolio-registry.json")
REGISTRY_SCHEMA = Path("schemas/agent-family-portfolio-registry.schema.json")
ROUTING_SCHEMA = Path("schemas/agent-family-routing-decision.schema.json")
HEALTH_SCHEMA = Path("schemas/agent-family-health.schema.json")
PILOT_SCHEMA = Path("schemas/agent-family-pilot.schema.json")
COCKPIT_V2_SCHEMA = Path("schemas/portfolio-cockpit-v2.schema.json")
QUALITY_FAMILY_ID = "family:quality-verification-release"
SCHEMA_VERSION = "dad.portfolio_cockpit.v2"
MAX_NOW = 3
AUTHORITY_BOUNDARY = (
    "This is a local read-only candidate projection. It cannot dispatch agents, "
    "change instructions or lifecycle state, mutate a source repository, create "
    "tasks or notifications, activate automation, or approve security, privacy, "
    "legal, deployment, release, exception, or adoption decisions."
)
_PROVIDER_TERMS = re.compile(
    r"(?:^|[-_:])(openai|anthropic|google|microsoft|gpt|claude|gemini)(?:$|[-_:])",
    re.IGNORECASE,
)
_BAND_ORDER = {
    "human_decision": 0,
    "integrity_unknown": 1,
    "dependency_unlock": 2,
    "weekly_maintenance": 3,
}


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(value: dict[str, Any], schema_path: Path) -> None:
    schema = _load_json(schema_path)
    cls = validator_for(schema)
    cls.check_schema(schema)
    errors = sorted(
        cls(schema, format_checker=FormatChecker()).iter_errors(value),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        first = errors[0]
        path = "/".join(str(part) for part in first.absolute_path) or "$"
        raise ValueError(f"{schema_path.name} validation failed at {path}: {first.message}")


def load_agent_family_registry(repo_root: Path) -> dict[str, Any]:
    registry = _load_json(repo_root / REGISTRY_PATH)
    _validate(registry, repo_root / REGISTRY_SCHEMA)
    family_ids = [row["family_id"] for row in registry["families"]]
    if len(family_ids) != len(set(family_ids)):
        raise ValueError("agent family IDs must be unique")
    orders = [row["build_order"] for row in registry["families"]]
    if len(orders) != len(set(orders)):
        raise ValueError("agent family build_order values must be unique")
    return registry


def _normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def agent_family_catalog(repo_root: Path, query: str = "") -> dict[str, Any]:
    registry = load_agent_family_registry(repo_root)
    needle = _normalize_text(query)
    rows = []
    for row in registry["families"]:
        searchable = _normalize_text(
            " ".join(
                [
                    row["family_id"],
                    row["name"],
                    *row["domains"],
                    *row["trigger_terms"],
                    *row["capabilities"],
                ]
            )
        )
        if not needle or all(token in searchable.split() for token in needle.split()):
            rows.append(row)
    return {
        "schema_version": "dad.agent_family_catalog.v1",
        "query": query,
        "candidate_only": True,
        "execution_authorized": False,
        "count": len(rows),
        "families": rows,
        "authority_boundary": registry["authority_boundary"],
    }


def route_agent_families(
    repo_root: Path,
    request: str,
    *,
    material: bool = True,
    risk_tags: Iterable[str] = (),
) -> dict[str, Any]:
    """Return the smallest deterministic family set supported by declared terms."""

    registry = load_agent_family_registry(repo_root)
    tags = sorted({_normalize_text(tag) for tag in risk_tags if _normalize_text(tag)})
    haystack = f" {_normalize_text(request)} {' '.join(tags)} "
    scored: list[tuple[int, int, str]] = []
    for row in registry["families"]:
        matched = {
            term
            for term in row["trigger_terms"]
            if f" {_normalize_text(term)} " in haystack
        }
        if matched:
            scored.append((-len(matched), row["build_order"], row["family_id"]))
    selected = [family_id for _, _, family_id in sorted(scored)]
    supporting: list[str] = []
    producer_ids = [family_id for family_id in selected if family_id != QUALITY_FAMILY_ID]
    if material and producer_ids and QUALITY_FAMILY_ID not in selected:
        supporting.append(QUALITY_FAMILY_ID)
    all_selected = set(selected) | set(supporting)
    rows_by_id = {row["family_id"]: row for row in registry["families"]}
    human_gates = sorted(
        {
            gate
            for family_id in all_selected
            for gate in rows_by_id[family_id]["human_gates"]
        }
    )
    result = {
        "schema_version": "dad.agent_family_routing_decision.v1",
        "request": request,
        "material": material,
        "risk_tags": tags,
        "selected_family_ids": selected,
        "supporting_family_ids": supporting,
        "rejected_family_ids": [
            row["family_id"] for row in registry["families"] if row["family_id"] not in all_selected
        ],
        "checker_family_id": QUALITY_FAMILY_ID if QUALITY_FAMILY_ID in all_selected else None,
        "human_gates": human_gates,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": registry["authority_boundary"],
    }
    _validate(result, repo_root / ROUTING_SCHEMA)
    return result


def agent_family_dependency_graph(
    repo_root: Path, focus_node: str | None = None
) -> dict[str, Any]:
    registry = load_agent_family_registry(repo_root)
    edges = registry["graph_contract"]["dependency_edges"]
    nodes = sorted({value for row in edges for value in (row["source"], row["target"])})
    if focus_node is not None and focus_node not in nodes:
        raise ValueError(f"unknown agent-family graph node: {focus_node}")
    if focus_node is None:
        selected_edges = list(edges)
    else:
        queue: deque[str] = deque([focus_node])
        visited = {focus_node}
        selected: dict[tuple[str, str, str], dict[str, Any]] = {}
        while queue:
            node = queue.popleft()
            for edge in edges:
                if node not in {edge["source"], edge["target"]}:
                    continue
                key = (edge["source"], edge["edge_type"], edge["target"])
                selected[key] = edge
                other = edge["target"] if edge["source"] == node else edge["source"]
                if other not in visited:
                    visited.add(other)
                    queue.append(other)
        selected_edges = [selected[key] for key in sorted(selected)]
    return {
        "schema_version": "dad.agent_family_dependency_graph.v1",
        "focus_node": focus_node,
        "candidate_only": True,
        "execution_authorized": False,
        "nodes": nodes if focus_node is None else sorted(
            {value for row in selected_edges for value in (row["source"], row["target"])}
        ),
        "edges": selected_edges,
        "forbidden_claims": registry["graph_contract"]["forbidden_claims"],
        "source_fingerprint": _canonical_hash(registry["graph_contract"]),
        "authority_boundary": registry["authority_boundary"],
    }


def _issue(
    *,
    family_id: str,
    issue_kind: str,
    severity: str,
    reason: str,
    source: str = "",
    target: str = "",
    evidence_refs: Iterable[str],
    human: bool,
    next_action: str,
) -> dict[str, Any]:
    semantic = {
        "family_id": family_id,
        "issue_kind": issue_kind,
        "reason": reason,
        "dependency_source": source,
        "dependency_target": target,
        "evidence_refs": sorted(set(evidence_refs)),
        "human_decision_required": human,
        "next_action": next_action,
    }
    fingerprint = _canonical_hash(semantic)
    return {
        "issue_id": f"family-issue:{fingerprint.split(':', 1)[1][:24]}",
        "fingerprint": fingerprint,
        "severity": severity,
        **semantic,
    }


def agent_family_health(
    repo_root: Path,
    *,
    now: datetime | None = None,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    payload = registry or load_agent_family_registry(repo_root)
    if registry is not None:
        _validate(payload, repo_root / REGISTRY_SCHEMA)
    family_rows: list[dict[str, Any]] = []
    issues: dict[str, dict[str, Any]] = {}
    for row in sorted(payload["families"], key=lambda item: item["build_order"]):
        skill_name = row["skill_ref"].split(":", 1)[1]
        skill_path = Path("assets/agent-skills") / skill_name / "SKILL.md"
        pack_path = Path(row["pack_ref"])
        validation_path = Path(row["validation_ref"])
        evidence_refs = [str(skill_path).replace("\\", "/"), str(pack_path).replace("\\", "/")]
        missing = [
            str(path).replace("\\", "/")
            for path in (skill_path, pack_path, validation_path)
            if not (repo_root / path).exists()
        ]
        dependency_issues: list[str] = []
        reasons: list[str] = []
        candidate_actions: list[str] = []
        health_state = "watch"
        if missing:
            health_state = "stale"
            reasons.append("required_artifact_missing")
            dependency_issues.extend(missing)
            issue = _issue(
                family_id=row["family_id"],
                issue_kind="missing_dependency",
                severity="danger",
                reason="One or more declared family artifacts are missing.",
                source=row["family_id"],
                target=",".join(sorted(missing)),
                evidence_refs=evidence_refs,
                human=False,
                next_action="Restore or revise the declared artifact references, then rerun validation.",
            )
            issues[issue["fingerprint"]] = issue
        else:
            pack = yaml.safe_load((repo_root / pack_path).read_text(encoding="utf-8"))
            role_ids = [str(role.get("role_id", "")) for role in pack.get("roles", [])]
            workers = [role_id for role_id in role_ids if role_id.endswith("-worker")]
            checkers = [
                role_id for role_id in role_ids if role_id.endswith("-independent-checker")
            ]
            if len(workers) != 1 or len(checkers) != 1 or workers[0] == checkers[0]:
                health_state = "unknown"
                reasons.append("writer_checker_contract_invalid")
                issue = _issue(
                    family_id=row["family_id"],
                    issue_kind="integrity_unknown",
                    severity="danger",
                    reason="The declared pack does not expose exactly one distinct worker and independent checker.",
                    source=str(pack_path).replace("\\", "/"),
                    evidence_refs=[str(pack_path).replace("\\", "/")],
                    human=False,
                    next_action="Repair the role declaration and rerun family contract validation.",
                )
                issues[issue["fingerprint"]] = issue
            stable_values = [row["family_id"], row["skill_ref"], *role_ids]
            if any(_PROVIDER_TERMS.search(value) for value in stable_values):
                health_state = "unknown"
                reasons.append("provider_in_stable_identity")
                issue = _issue(
                    family_id=row["family_id"],
                    issue_kind="integrity_unknown",
                    severity="danger",
                    reason="A provider or model term appears in stable family or role identity.",
                    evidence_refs=evidence_refs,
                    human=False,
                    next_action="Move provider/model identity to expiring attempt metadata.",
                )
                issues[issue["fingerprint"]] = issue
        if row["lifecycle_state"] == "candidate":
            reasons.append("candidate_requires_human_review")
            candidate_actions.append("review_for_pilot_or_keep_incubating")
            issue = _issue(
                family_id=row["family_id"],
                issue_kind="human_decision",
                severity="info",
                reason="Implemented candidate awaits a named-human pilot or incubation decision.",
                evidence_refs=evidence_refs,
                human=True,
                next_action="Review evidence and choose pilot, keep incubating, revise, or reject.",
            )
            issues[issue["fingerprint"]] = issue
        elif row["lifecycle_state"] in {"reviewed", "active"} and not missing:
            health_state = "current"
            reasons.append("reviewed_artifacts_present")
        elif row["lifecycle_state"] == "superseded":
            health_state = "superseded"
            reasons.append("declared_superseded")
        family_rows.append(
            {
                "family_id": row["family_id"],
                "name": row["name"],
                "build_order": row["build_order"],
                "lifecycle_state": row["lifecycle_state"],
                "health_state": health_state,
                "reasons": sorted(set(reasons)),
                "evidence_refs": sorted(set(evidence_refs)),
                "dependency_issues": sorted(set(dependency_issues)),
                "candidate_actions": sorted(set(candidate_actions)),
            }
        )
    issue_rows = sorted(
        issues.values(),
        key=lambda item: (
            not item["human_decision_required"],
            {"danger": 0, "warning": 1, "info": 2}[item["severity"]],
            item["family_id"],
            item["issue_id"],
        ),
    )
    counts = Counter(row["health_state"] for row in family_rows)
    result = {
        "schema_version": "dad.agent_family_health.v1",
        "generated_at": observed.isoformat(),
        "status": "partial_candidate" if counts["stale"] or counts["unknown"] else "generated_candidate",
        "candidate_only": True,
        "execution_authorized": False,
        "source_fingerprint": _canonical_hash(payload),
        "summary": {
            "family_count": len(family_rows),
            "current_count": counts["current"],
            "watch_count": counts["watch"],
            "stale_count": counts["stale"],
            "unknown_count": counts["unknown"],
            "issue_count": len(issue_rows),
            "human_decision_count": sum(
                1 for item in issue_rows if item["human_decision_required"]
            ),
        },
        "families": family_rows,
        "issues": issue_rows,
        "authority_boundary": payload["authority_boundary"],
    }
    _validate(result, repo_root / HEALTH_SCHEMA)
    return result


def _git_bytes(repo_path: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise ValueError(completed.stderr.decode("utf-8", errors="replace").strip())
    return completed.stdout


def _stack_metadata(paths: list[str]) -> dict[str, Any]:
    counts = Counter()
    lower_names = set()
    for raw_path in paths:
        path = PurePosixPath(raw_path.replace("\\", "/"))
        suffix = path.suffix.lower() or "[none]"
        counts[suffix] += 1
        lower_names.add(path.name.lower())
    indicators = []
    manifest_indicators = {
        "package.json": "node_or_web",
        "pyproject.toml": "python",
        "requirements.txt": "python",
        "cargo.toml": "rust",
        "go.mod": "go",
        "pom.xml": "jvm",
        "build.gradle": "jvm",
        "dockerfile": "container",
        "wrangler.jsonc": "cloudflare",
    }
    for filename, indicator in manifest_indicators.items():
        if filename in lower_names:
            indicators.append(indicator)
    if any(suffix in counts for suffix in (".tsx", ".jsx", ".vue", ".svelte")):
        indicators.append("frontend")
    if any(suffix in counts for suffix in (".sql", ".ttl", ".jsonld")):
        indicators.append("data_or_graph")
    return {
        "tracked_file_count": len(paths),
        "extension_counts": dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:30]),
        "stack_indicators": sorted(set(indicators)),
    }


def inspect_agent_family_pilot(
    repo_root: Path,
    pilot_repo: Path,
    pilot_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Inspect Git path metadata only and prove the source status fingerprint is unchanged."""

    registry = load_agent_family_registry(repo_root)
    try:
        pilot = next(row for row in registry["pilots"] if row["pilot_id"] == pilot_id)
    except StopIteration as exc:
        raise ValueError(f"unknown agent-family pilot: {pilot_id}") from exc
    before = _canonical_hash(_git_bytes(pilot_repo, "status", "--porcelain=v1", "-z").hex())
    tracked = _git_bytes(pilot_repo, "ls-files", "-z").decode(
        "utf-8", errors="surrogateescape"
    ).split("\x00")
    tracked_paths = [path for path in tracked if path][:50000]
    observed_metadata = _stack_metadata(tracked_paths)
    after = _canonical_hash(_git_bytes(pilot_repo, "status", "--porcelain=v1", "-z").hex())
    if before != after:
        raise RuntimeError("pilot source Git fingerprint changed during read-only inspection")
    result = {
        "schema_version": "dad.agent_family_pilot.v1",
        "generated_at": (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        "pilot_id": pilot["pilot_id"],
        "repo_id": pilot["repo_id"],
        "candidate_only": True,
        "execution_authorized": False,
        "mutation_observed": False,
        "source_git_fingerprint_before": before,
        "source_git_fingerprint_after": after,
        "privacy_scope": pilot["privacy_scope"],
        "observed_metadata": observed_metadata,
        "recommended_family_ids": pilot["family_ids"],
        "overlay_ids": pilot["overlay_ids"],
        "evidence_refs": [
            f"registry/agent-family-portfolio-registry.json#{pilot_id}",
            "git:tracked-path-metadata",
            "git:status-fingerprint",
        ],
        "human_gates": [pilot["human_gate"]],
        "authority_boundary": registry["authority_boundary"],
    }
    _validate(result, repo_root / PILOT_SCHEMA)
    return result


def _family_band(issue: dict[str, Any]) -> str:
    if issue["human_decision_required"] or issue["issue_kind"] == "human_decision":
        return "human_decision"
    if issue["issue_kind"] == "integrity_unknown":
        return "integrity_unknown"
    if issue["issue_kind"] in {"missing_dependency", "stale_dependency", "conflict"}:
        return "dependency_unlock"
    return "weekly_maintenance"


def build_portfolio_cockpit_v2(
    health: dict[str, Any],
    portfolio_v1: dict[str, Any] | None = None,
    capability_snapshot: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    family_items = [
        {
            "attention_id": issue["issue_id"],
            "source": "agent_families",
            "band": _family_band(issue),
            "label": issue["family_id"].split(":", 1)[1].replace("-", " "),
            "family_id": issue["family_id"],
            "reasons": [issue["issue_kind"], issue["reason"]],
            "next_action": issue["next_action"],
            "human_decision_required": issue["human_decision_required"],
            "selected_now": False,
            "fingerprint": issue["fingerprint"],
            "evidence_refs": issue["evidence_refs"],
        }
        for issue in health["issues"]
    ]
    portfolio_items: list[dict[str, Any]] = []
    capability_items: list[dict[str, Any]] = []
    portfolio_source = {
        "status": "unavailable",
        "schema_version": "",
        "fingerprint": "",
        "problems": ["portfolio_v1_not_supplied"],
    }
    if isinstance(portfolio_v1, dict):
        if portfolio_v1.get("schema_version") == "dad.portfolio_cockpit.v1":
            portfolio_source = {
                "status": "observed",
                "schema_version": "dad.portfolio_cockpit.v1",
                "fingerprint": _canonical_hash(portfolio_v1),
                "problems": [],
            }
            for item in portfolio_v1.get("today", []):
                band = str(item.get("band", "weekly_maintenance"))
                if band not in _BAND_ORDER:
                    band = "weekly_maintenance"
                portfolio_items.append(
                    {
                        "attention_id": str(item.get("attention_id", "")),
                        "source": "portfolio_v1",
                        "band": band,
                        "label": str(item.get("label", "")),
                        "family_id": "",
                        "reasons": sorted({str(reason) for reason in item.get("reasons", [])}),
                        "next_action": str(item.get("next_action", "")),
                        "human_decision_required": band == "human_decision",
                        "selected_now": False,
                        "fingerprint": str(item.get("fingerprint", _canonical_hash(item))),
                        "evidence_refs": ["portfolio-cockpit-v1:today"],
                    }
                )
        else:
            portfolio_source = {
                "status": "invalid",
                "schema_version": str(portfolio_v1.get("schema_version", "")),
                "fingerprint": _canonical_hash(portfolio_v1),
                "problems": ["unsupported_portfolio_schema"],
            }
    capability_source: dict[str, Any] | None = None
    if isinstance(capability_snapshot, dict):
        if capability_snapshot.get("schema_version") == "dad.capability_portfolio_snapshot.v1":
            capability_source = {
                "status": "observed",
                "schema_version": "dad.capability_portfolio_snapshot.v1",
                "fingerprint": str(capability_snapshot.get("catalog_fingerprint", "")),
                "problems": [],
            }
            for item in capability_snapshot.get("operator", {}).get("digest", []):
                capability_items.append(
                    {
                        "attention_id": str(item.get("decision_id", "")),
                        "source": "capability_os",
                        "band": "human_decision",
                        "label": str(item.get("label", "")),
                        "family_id": "",
                        "reasons": sorted(
                            {
                                str(item.get("kind", "capability_os")),
                                str(item.get("recommended_action", "review")),
                            }
                        ),
                        "next_action": str(item.get("recommended_action", "review")),
                        "human_decision_required": True,
                        "selected_now": False,
                        "fingerprint": str(item.get("fingerprint", _canonical_hash(item))),
                        "evidence_refs": sorted(
                            {str(ref) for ref in item.get("evidence_refs", [])}
                        ),
                    }
                )
        else:
            capability_source = {
                "status": "invalid",
                "schema_version": str(capability_snapshot.get("schema_version", "")),
                "fingerprint": _canonical_hash(capability_snapshot),
                "problems": ["unsupported_capability_snapshot_schema"],
            }
    deduped = {
        item["fingerprint"]: item
        for item in [*portfolio_items, *family_items, *capability_items]
    }
    digest = sorted(
        deduped.values(),
        key=lambda item: (
            _BAND_ORDER[item["band"]],
            not item["human_decision_required"],
            item["attention_id"],
        ),
    )
    now_items = digest[:MAX_NOW]
    selected = {item["fingerprint"] for item in now_items}
    for item in digest:
        item["selected_now"] = item["fingerprint"] in selected
    sources = {
        "portfolio_v1": portfolio_source,
        "agent_families": {
            "status": "observed",
            "schema_version": health["schema_version"],
            "fingerprint": health["source_fingerprint"],
            "problems": (
                []
                if health["status"] == "generated_candidate"
                else ["agent_family_health_partial"]
            ),
        },
    }
    source_refs = {
        "portfolio_v1": portfolio_source["fingerprint"],
        "agent_families": health["source_fingerprint"],
    }
    if capability_source is not None:
        sources["capability_os"] = capability_source
        source_refs["capability_os"] = capability_source["fingerprint"]
    all_observed = all(source["status"] == "observed" for source in sources.values())
    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": observed.isoformat(),
        "status": (
            "generated_candidate"
            if all_observed and health["status"] == "generated_candidate"
            else "partial_candidate"
        ),
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "sources": sources,
        "summary": {
            "now_count": len(now_items),
            "digest_count": len(digest),
            "family_count": health["summary"]["family_count"],
            "family_issue_count": health["summary"]["issue_count"],
            "portfolio_item_count": len(portfolio_items),
            "capability_item_count": len(capability_items),
        },
        "now": now_items,
        "digest": digest,
        "source_refs": source_refs,
    }
    return result


_STYLE = """
:root{color-scheme:dark;--bg:#081117;--panel:#10222b;--line:#294a57;--text:#f6f8f7;--muted:#a6bbc2;--mint:#78e0bd;--amber:#ffc96f}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 85% 0,#173f4c 0,transparent 38%),var(--bg);color:var(--text);font:15px/1.55 ui-sans-serif,system-ui,sans-serif}.shell{width:min(1350px,94vw);margin:auto;padding:44px 0 72px}
h1{font-size:clamp(2.3rem,6vw,5.2rem);line-height:.95;max-width:980px}.muted,.meta{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.card,.table{background:var(--panel);border:1px solid var(--line);border-radius:16px}.card{padding:18px}.eyebrow{color:var(--mint);text-transform:uppercase;letter-spacing:.12em;font-size:.72rem;font-weight:800}.badge{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:.2rem .55rem}.table{overflow:auto;margin-top:16px}table{width:100%;border-collapse:collapse}th,td{padding:12px;border-top:1px solid var(--line);text-align:left;vertical-align:top}th{color:var(--muted)}footer{margin-top:42px;color:var(--muted)}:focus-visible{outline:3px solid var(--amber);outline-offset:3px}@media(max-width:900px){.grid{grid-template-columns:1fr}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
""".strip()


def portfolio_cockpit_v2_html(cockpit: dict[str, Any]) -> str:
    cards = "".join(
        (
            '<article class="card">'
            f'<div class="eyebrow">{escape(item["band"].replace("_", " "))} · {escape(item["source"])}</div>'
            f'<h2>{escape(item["label"])}</h2>'
            f'<p>{escape(" · ".join(item["reasons"]))}</p>'
            f'<p>{escape(item["next_action"])}</p>'
            f'<span class="badge">{"human decision" if item["human_decision_required"] else "candidate evidence"}</span>'
            "</article>"
        )
        for item in cockpit["now"]
    ) or '<article class="card"><h2>No immediate decision</h2><p>Inspect the digest before treating this as all clear.</p></article>'
    rows = "".join(
        "<tr>"
        f'<td>{escape(item["band"])}</td><td>{escape(item["label"])}</td>'
        f'<td>{escape(item["source"])}</td><td>{escape(item["next_action"])}</td>'
        "</tr>"
        for item in cockpit["digest"]
    ) or '<tr><td colspan="4">No current digest items.</td></tr>'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; script-src 'none'; object-src 'none'; frame-src 'none'; form-action 'none'">
<title>DAD Portfolio Cockpit v2</title><style>{_STYLE}</style></head>
<body><main class="shell"><div class="eyebrow">DAD · family-of-families control plane</div>
<h1>One human. Three decisions. Full evidence.</h1>
<p class="muted">Read-only candidate health over the unchanged portfolio cockpit v1 and the model-neutral agent-family mesh. This page has no execution controls.</p>
<section class="grid" aria-label="Now">{cards}</section>
<div class="table"><table><caption>Full digest</caption><thead><tr><th>Band</th><th>Item</th><th>Source</th><th>Next action</th></tr></thead><tbody>{rows}</tbody></table></div>
<footer>Generated {escape(cockpit["generated_at"])}. {escape(cockpit["authority_boundary"])}</footer>
</main></body></html>"""


def write_agent_family_health(hub_root: Path, health: dict[str, Any]) -> dict[str, Any]:
    _validate(health, hub_root / HEALTH_SCHEMA)
    path = data_path(hub_root, "central_reports") / "agent_families" / "health.json"
    atomic_write_text(path, json_dumps(health, pretty=True) + "\n")
    return {"json_path": str(path), "summary": health["summary"]}


def write_portfolio_cockpit_v2(hub_root: Path, cockpit: dict[str, Any]) -> dict[str, Any]:
    _validate(cockpit, hub_root / COCKPIT_V2_SCHEMA)
    base = data_path(hub_root, "central_reports") / "portfolio_os"
    html_path = base / "cockpit-v2.html"
    json_path = base / "cockpit-v2.json"
    atomic_write_text(html_path, portfolio_cockpit_v2_html(cockpit))
    atomic_write_text(json_path, json_dumps(cockpit, pretty=True) + "\n")
    return {
        "json_path": str(json_path),
        "html_path": str(html_path),
        "status": cockpit["status"],
        "summary": cockpit["summary"],
        "now": cockpit["now"],
    }


def load_portfolio_cockpit_v1(hub_root: Path) -> dict[str, Any] | None:
    path = data_path(hub_root, "central_reports") / "portfolio_os" / "cockpit.json"
    if not path.exists():
        return None
    try:
        value = _load_json(path)
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


__all__ = [
    "AUTHORITY_BOUNDARY",
    "MAX_NOW",
    "SCHEMA_VERSION",
    "agent_family_catalog",
    "agent_family_dependency_graph",
    "agent_family_health",
    "build_portfolio_cockpit_v2",
    "inspect_agent_family_pilot",
    "load_agent_family_registry",
    "load_portfolio_cockpit_v1",
    "portfolio_cockpit_v2_html",
    "route_agent_families",
    "write_agent_family_health",
    "write_portfolio_cockpit_v2",
]
