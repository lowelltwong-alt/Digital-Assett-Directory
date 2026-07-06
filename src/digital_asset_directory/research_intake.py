"""Research-to-skill intake pipeline.

External research findings enter a quarantine folder, pass named screening checks,
and become library entries only through a human-approved promotion that writes
pointer artifacts - never copies of external content. Trusted-source tiers lower
friction (intake without extra justification); they never skip screening or the
human approval gate.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .ids import stable_id
from .utils import append_jsonl, atomic_write_text, json_dumps, utc_now, write_jsonl

TRUSTED_SOURCE_REGISTRY = Path("registry") / "trusted-source-registry.json"
LANGUAGE_PLAYBOOKS_MANIFEST = Path("assets") / "language-coding-playbooks" / "playbooks.json"
INTAKE_DIR = Path("processed") / "research" / "intake"
INTAKE_GRAPH_PATH = Path("processed") / "research" / "intake-graph.json"
INTAKE_GRAPH_EDGES_PATH = Path("processed") / "research" / "intake-graph-edges.jsonl"
POINTER_ASSET_DIR = Path("assets") / "external"
SCREENING_CHECKS = ("prompt_injection", "license", "provenance", "compatibility")
SCREENING_RESULTS = {"pass", "fail", "not_applicable", "not_run"}
INTAKE_KINDS = {"skill", "harness", "asset", "lesson", "doc"}
PROMOTION_TARGETS = {"offering", "skill_pointer"}
INTAKE_GRAPH_METHOD_VERSION = "research-intake-graph-v0.1"
CADENCE_DAYS = {
    "weekly": 7,
    "monthly": 30,
    "quarterly": 90,
}
INTAKE_AUTHORITY_BOUNDARY = (
    "Intake records are quarantined candidate metadata about external sources. "
    "They carry links, provenance, and screening state only - never external file "
    "contents - and do not authorize checkout, install, or downstream delivery."
)
LANGUAGE_FRONTIER_WATCH_AUTHORITY_BOUNDARY = (
    "Language frontier watch rows are source pointers and cadence hints only. "
    "They do not prove a technique is current, safe, useful, or adopted DAD guidance. "
    "Every candidate still needs pointer-only intake, screening, local validation, "
    "and human-reviewed promotion before downstream recommendation."
)
INTAKE_GRAPH_AUTHORITY_BOUNDARY = (
    "The research intake graph is a generated candidate context surface. It explains "
    "what DAD knows about each external pointer from local intake metadata, screening "
    "state, trust tier, license, capability tags, and suggested DAD routes. It stores "
    "no external source contents and does not promote an intake, install code, or "
    "override the reviewed graph-edge registry."
)
KIND_TO_OFFERING_TYPE = {
    "harness": "harness",
    "asset": "asset",
    "lesson": "best_practice",
    "doc": "best_practice",
}
INTAKE_GRAPH_SURFACES: dict[str, dict[str, Any]] = {
    "dad-surface:agent-skill-library": {
        "label": "Agent Skill Library",
        "target_control_plane": "agent_skills",
        "terms": ("skill", "plugin", "prompt", "claude", "codex", "agent"),
        "kind": "skill",
    },
    "dad-surface:coding-harnesses": {
        "label": "Coding Harnesses",
        "target_control_plane": "coding_harnesses",
        "terms": (
            "harness",
            "pytest",
            "hypothesis",
            "coverage",
            "mutation",
            "fuzz",
            "miri",
            "nextest",
            "criterion",
        ),
        "kind": "harness",
    },
    "dad-surface:ai-engineering-preflight": {
        "label": "AI Engineering Preflight",
        "target_control_plane": "reusable_assets",
        "terms": (
            "agent",
            "agentic",
            "openai",
            "anthropic",
            "codex",
            "claude",
            "frontier eval",
            "long running",
        ),
    },
    "dad-surface:legal-intake-budget-billing-map": {
        "label": "Legal Intake, Budgeting, And Billing Map",
        "target_control_plane": "governance_maps",
        "terms": (
            "legal",
            "law",
            "intake",
            "billing",
            "budget",
            "ledes",
            "utbms",
            "sali",
            "lmss",
            "matter",
            "timekeeper",
            "rate",
        ),
    },
    "dad-surface:python-test-performance-orchestration": {
        "label": "Python Test And Performance Orchestration",
        "target_control_plane": "coding_harnesses",
        "terms": (
            "python",
            "pytest",
            "hypothesis",
            "coverage",
            "mutmut",
            "cosmic ray",
            "pyperf",
        ),
    },
    "dad-surface:rust-shadow-parity": {
        "label": "Rust Shadow Parity",
        "target_control_plane": "coding_harnesses",
        "terms": (
            "rust",
            "cargo",
            "miri",
            "proptest",
            "quickcheck",
            "fuzz",
            "nextest",
            "criterion",
            "cargo-mutants",
        ),
    },
    "dad-surface:language-frontier-research": {
        "label": "Language Frontier Research",
        "target_control_plane": "reusable_assets",
        "terms": ("rust", "python", "language", "frontier", "compiler", "stdlib"),
    },
    "dad-surface:simulation-budget-risk-modeling": {
        "label": "Simulation, Budget, And Risk Modeling",
        "target_control_plane": "reusable_assets",
        "terms": (
            "simulation",
            "monte carlo",
            "pymc",
            "numpyro",
            "stan",
            "scipy",
            "or-tools",
            "optimization",
            "bayesian",
        ),
    },
    "dad-surface:frontier-math-formal-methods": {
        "label": "Frontier Math And Formal Methods",
        "target_control_plane": "reusable_assets",
        "terms": (
            "math",
            "lean",
            "mathlib",
            "alphageometry",
            "sage",
            "sympy",
            "theorem",
            "formal",
            "symbolic",
            "geometry",
        ),
    },
    "dad-surface:external-research-review-queue": {
        "label": "External Research Review Queue",
        "target_control_plane": "mail_center",
        "terms": (),
    },
}
INTAKE_GRAPH_CAPABILITY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("agentic-harness", ("agentic", "agent", "codex", "claude", "openai", "anthropic")),
    ("evaluation-harness", ("frontier eval", "gold")),
    ("legal-taxonomy", ("sali", "lmss", "utbms", "legal", "matter")),
    ("legal-billing", ("ledes", "billing", "budget", "rate", "timekeeper")),
    ("python-testing", ("python", "pytest", "hypothesis", "coverage", "mutmut", "pyperf")),
    ("rust-testing", ("rust", "cargo", "miri", "nextest", "proptest", "quickcheck")),
    ("fuzzing", ("fuzz", "cargo-fuzz", "hypothesis", "proptest", "quickcheck")),
    ("mutation-testing", ("mutation", "mutmut", "cargo-mutants", "cosmic ray")),
    ("benchmarking", ("benchmark", "criterion", "pyperf")),
    ("simulation", ("simulation", "monte carlo", "pymc", "numpyro", "stan")),
    ("optimization", ("or-tools", "optimization", "scipy")),
    ("formal-math", ("lean", "mathlib", "theorem", "formal", "alphageometry")),
    ("symbolic-math", ("sympy", "sage", "symbolic", "algebra")),
)
INTAKE_GRAPH_NEED_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "dad:need:coding-harness-feedback",
        (
            "harness",
            "eval",
            "pytest",
            "hypothesis",
            "coverage",
            "mutation",
            "fuzz",
            "benchmark",
            "miri",
            "nextest",
            "criterion",
        ),
    ),
    (
        "dad:need:harness-enforcement-tradeoff-feedback",
        ("harness", "gate", "mutation", "fuzz", "coverage", "compatibility", "screening"),
    ),
    (
        "dad:need:language-frontier-signals",
        ("rust", "python", "language", "frontier", "cargo", "miri", "stdlib", "compiler"),
    ),
    (
        "dad:need:skill-capability-updates",
        ("skill", "plugin", "agent", "codex", "claude", "openai", "anthropic"),
    ),
    (
        "dad:need:rust-rollout-feedback",
        ("rust", "cargo", "miri", "criterion", "nextest", "proptest", "cargo-mutants"),
    ),
    (
        "dad:need:address-model-and-workflow-card-feedback",
        ("workflow", "taxonomy", "ontology", "graph", "intake", "matter", "billing"),
    ),
    (
        "dad:need:subagent-review-and-asset-scout-findings",
        ("research", "asset", "harness", "skill", "legal", "math", "simulation"),
    ),
)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json_dumps(payload, pretty=True) + "\n")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:60] or "item"


def _audit(hub_root: Path, event: dict[str, Any]) -> None:
    created = str(event.get("created_at") or utc_now())
    append_jsonl(hub_root / "audit" / "events" / f"{created[:10]}.jsonl", event)


def _record_text(record: dict[str, Any]) -> str:
    return " ".join(
        str(record.get(key) or "")
        for key in (
            "name",
            "kind",
            "source_url",
            "source_id",
            "trust_tier",
            "license",
            "notes",
            "research_ref",
            "justification",
        )
    ).lower()


def _matched_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    matched: set[str] = set()
    for term in terms:
        if not term:
            continue
        pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
        if re.search(pattern, text):
            matched.add(term)
    return sorted(matched)


def _source_pointer(record: dict[str, Any]) -> dict[str, str]:
    source_url = str(record.get("source_url") or "")
    parsed = urlparse(source_url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path_parts = [part for part in parsed.path.split("/") if part]
    source_id = str(record.get("source_id") or "")
    if source_id:
        key = source_id
        label = source_id
    elif host == "github.com" and len(path_parts) >= 2:
        key = f"github.com/{path_parts[0]}/{path_parts[1]}"
        label = f"{path_parts[0]}/{path_parts[1]}"
    else:
        key = host or source_url
        label = host or source_url
    return {
        "node_id": f"external-source:{_slug(key)}",
        "label": label,
        "host": host,
        "source_key": key,
    }


def _screening_summary(record: dict[str, Any]) -> dict[str, str]:
    screening = record.get("screening", {})
    return {
        check: str(screening.get(check, {}).get("result", "not_run"))
        for check in SCREENING_CHECKS
    }


def _intake_records(hub_root: Path) -> list[tuple[Path, dict[str, Any]]]:
    intake_root = hub_root / INTAKE_DIR
    if not intake_root.exists():
        return []
    records: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(intake_root.glob("*.json")):
        records.append((path, json.loads(path.read_text(encoding="utf-8"))))
    return records


def _intake_routes(record: dict[str, Any]) -> list[dict[str, Any]]:
    text = _record_text(record)
    routes: list[dict[str, Any]] = []
    for surface_id, surface in INTAKE_GRAPH_SURFACES.items():
        if surface_id == "dad-surface:external-research-review-queue":
            continue
        term_hits = _matched_terms(text, surface.get("terms", ()))
        kind_hit = bool(surface.get("kind") and record.get("kind") == surface["kind"])
        if term_hits or kind_hit:
            routes.append(
                {
                    "surface_id": surface_id,
                    "label": surface["label"],
                    "target_control_plane": surface["target_control_plane"],
                    "matched_terms": term_hits,
                    "matched_kind": str(record.get("kind") or "") if kind_hit else "",
                }
            )
    if not routes:
        surface = INTAKE_GRAPH_SURFACES["dad-surface:external-research-review-queue"]
        routes.append(
            {
                "surface_id": "dad-surface:external-research-review-queue",
                "label": surface["label"],
                "target_control_plane": surface["target_control_plane"],
                "matched_terms": [],
                "matched_kind": "",
            }
        )
    return sorted(routes, key=lambda item: item["surface_id"])


def _intake_capabilities(record: dict[str, Any]) -> list[dict[str, Any]]:
    text = _record_text(record)
    capabilities: list[dict[str, Any]] = []
    for capability, terms in INTAKE_GRAPH_CAPABILITY_RULES:
        term_hits = _matched_terms(text, terms)
        if term_hits:
            capabilities.append(
                {
                    "capability_id": f"capability:{capability}",
                    "label": capability.replace("-", " ").title(),
                    "matched_terms": term_hits,
                }
            )
    return sorted(capabilities, key=lambda item: item["capability_id"])


def _intake_needs(record: dict[str, Any]) -> list[dict[str, Any]]:
    text = _record_text(record)
    needs: list[dict[str, Any]] = []
    for need_id, terms in INTAKE_GRAPH_NEED_RULES:
        term_hits = _matched_terms(text, terms)
        if term_hits:
            needs.append({"need_id": need_id, "matched_terms": term_hits})
    if not needs:
        needs.append(
            {
                "need_id": "dad:need:subagent-review-and-asset-scout-findings",
                "matched_terms": ["external-intake"],
            }
        )
    return sorted(needs, key=lambda item: item["need_id"])


def _safe_relpath(hub_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(hub_root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _add_node(nodes: dict[str, dict[str, Any]], node: dict[str, Any]) -> None:
    node_id = str(node["node_id"])
    existing = nodes.get(node_id)
    if not existing:
        nodes[node_id] = node
        return
    for key, value in node.items():
        if key not in existing or existing[key] in ("", [], {}):
            existing[key] = value


def _research_edge(
    *,
    source: str,
    target: str,
    edge_type: str,
    relationship: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    registered = edge_type in {"gap_evidence_for", "member_of"}
    return {
        "edge_id": stable_id(
            "research-intake-edge",
            edge_type,
            relationship,
            source,
            target,
            INTAKE_GRAPH_METHOD_VERSION,
        ),
        "source": source,
        "target": target,
        "edge_type": edge_type,
        "relationship": relationship,
        "edge_basis": INTAKE_GRAPH_METHOD_VERSION,
        "edge_registry_status": "registered_candidate" if registered else "local_research_context_only",
        "confidence": "candidate",
        "review_status": "candidate",
        "evidence": evidence,
    }


def build_research_intake_graph(hub_root: Path) -> dict[str, Any]:
    """Write a pointer-only candidate graph over external research intake records."""
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    records = _intake_records(hub_root)

    for path, record in records:
        intake_id = str(record.get("intake_id") or "")
        if not intake_id:
            continue
        intake_node_id = f"research-intake:{intake_id}"
        source = _source_pointer(record)
        routes = _intake_routes(record)
        capabilities = _intake_capabilities(record)
        needs = _intake_needs(record)
        _add_node(
            nodes,
            {
                "node_id": intake_node_id,
                "node_type": "research_intake",
                "label": record.get("name"),
                "intake_id": intake_id,
                "kind": record.get("kind"),
                "status": record.get("status"),
                "review_status": "candidate",
                "trust_tier": record.get("trust_tier"),
                "source_id": record.get("source_id"),
                "source_url": record.get("source_url"),
                "license": record.get("license"),
                "screening": _screening_summary(record),
                "intake_path": _safe_relpath(hub_root, path),
                "external_side_summary": {
                    "source_pointer": record.get("source_url"),
                    "source_id": record.get("source_id") or source["source_key"],
                    "trust_tier": record.get("trust_tier"),
                    "license": record.get("license") or "review_upstream",
                    "safe_notes": str(record.get("notes") or "")[:500],
                    "promotion_status": record.get("status"),
                },
                "suggested_surfaces": [route["surface_id"] for route in routes],
                "capability_tags": [item["capability_id"] for item in capabilities],
                "authority_boundary": INTAKE_GRAPH_AUTHORITY_BOUNDARY,
            },
        )
        _add_node(
            nodes,
            {
                "node_id": source["node_id"],
                "node_type": "external_source_pointer",
                "label": source["label"],
                "host": source["host"],
                "source_key": source["source_key"],
                "review_status": "candidate",
                "authority_boundary": (
                    "External source pointer only. DAD has not copied or vendored "
                    "the source and this node does not imply trust or adoption."
                ),
            },
        )
        edge = _research_edge(
            source=intake_node_id,
            target=source["node_id"],
            edge_type="source_pointer",
            relationship="points_to_external_source",
            evidence={
                "intake_path": _safe_relpath(hub_root, path),
                "source_url": record.get("source_url"),
                "source_id": record.get("source_id") or "",
            },
        )
        edges[edge["edge_id"]] = edge

        for route in routes:
            surface_id = route["surface_id"]
            surface_node_id = f"combination:dad:research-route:{_slug(surface_id)}"
            _add_node(
                nodes,
                {
                    "node_id": surface_node_id,
                    "node_type": "research_route_candidate",
                    "label": route["label"],
                    "surface_id": surface_id,
                    "target_control_plane": route["target_control_plane"],
                    "review_status": "candidate",
                    "authority_boundary": (
                        "A route candidate says where reviewers should look. It does "
                        "not adopt the intake or make the target surface authoritative."
                    ),
                },
            )
            edge = _research_edge(
                source=intake_node_id,
                target=surface_node_id,
                edge_type="member_of",
                relationship="routes_to_dad_surface",
                evidence={
                    "matched_terms": route["matched_terms"],
                    "matched_kind": route["matched_kind"],
                    "target_control_plane": route["target_control_plane"],
                },
            )
            edges[edge["edge_id"]] = edge

        for capability in capabilities:
            capability_node_id = f"combination:dad:research-capability:{_slug(capability['capability_id'])}"
            _add_node(
                nodes,
                {
                    "node_id": capability_node_id,
                    "node_type": "research_capability_candidate",
                    "label": capability["label"],
                    "capability_id": capability["capability_id"],
                    "review_status": "candidate",
                    "authority_boundary": (
                        "Capability grouping is generated from intake metadata and "
                        "requires review before use as DAD guidance."
                    ),
                },
            )
            edge = _research_edge(
                source=intake_node_id,
                target=capability_node_id,
                edge_type="member_of",
                relationship="supports_capability_candidate",
                evidence={"matched_terms": capability["matched_terms"]},
            )
            edges[edge["edge_id"]] = edge

        for need in needs:
            need_id = need["need_id"]
            _add_node(
                nodes,
                {
                    "node_id": f"need:{need_id}",
                    "node_type": "dad_need",
                    "label": need_id,
                    "need_id": need_id,
                    "review_status": "reviewed_registry_row",
                    "authority_boundary": "Need node points to registry/dad-needs-registry.json.",
                },
            )
            edge = _research_edge(
                source=intake_node_id,
                target=f"need:{need_id}",
                edge_type="gap_evidence_for",
                relationship="intake_suggests_need",
                evidence={"matched_terms": need["matched_terms"]},
            )
            edges[edge["edge_id"]] = edge

    node_list = sorted(nodes.values(), key=lambda item: item["node_id"])
    edge_list = sorted(edges.values(), key=lambda item: item["edge_id"])
    status_counts: dict[str, int] = {}
    trust_counts: dict[str, int] = {}
    kind_counts: dict[str, int] = {}
    surface_counts: dict[str, int] = {}
    for _, record in records:
        status = str(record.get("status") or "unknown")
        trust = str(record.get("trust_tier") or "unknown")
        kind = str(record.get("kind") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        trust_counts[trust] = trust_counts.get(trust, 0) + 1
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        for route in _intake_routes(record):
            surface_counts[route["surface_id"]] = surface_counts.get(route["surface_id"], 0) + 1

    payload = {
        "schema_version": "0.1.0",
        "graph_id": "dad:research-intake-graph",
        "generated_at": utc_now(),
        "method_version": INTAKE_GRAPH_METHOD_VERSION,
        "source_path": str(INTAKE_DIR).replace("\\", "/"),
        "node_count": len(node_list),
        "edge_count": len(edge_list),
        "intake_count": len(records),
        "status_counts": dict(sorted(status_counts.items())),
        "trust_counts": dict(sorted(trust_counts.items())),
        "kind_counts": dict(sorted(kind_counts.items())),
        "surface_counts": dict(sorted(surface_counts.items())),
        "edge_registry_alignment": {
            "registered_candidate_edge_types": ["gap_evidence_for", "member_of"],
            "local_research_context_edge_types": ["source_pointer"],
            "promotion_required_for_main_graph": True,
        },
        "nodes": node_list,
        "edges": edge_list,
        "outputs": {
            "graph": str(INTAKE_GRAPH_PATH).replace("\\", "/"),
            "edges_jsonl": str(INTAKE_GRAPH_EDGES_PATH).replace("\\", "/"),
        },
        "authority_boundary": INTAKE_GRAPH_AUTHORITY_BOUNDARY,
    }
    _write_json(hub_root / INTAKE_GRAPH_PATH, payload)
    write_jsonl(hub_root / INTAKE_GRAPH_EDGES_PATH, edge_list)
    _audit(
        hub_root,
        {
            "event_type": "research_intake_graph_built",
            "created_at": payload["generated_at"],
            "intake_count": len(records),
            "node_count": len(node_list),
            "edge_count": len(edge_list),
            "method_version": INTAKE_GRAPH_METHOD_VERSION,
        },
    )
    return payload


def load_trusted_sources(hub_root: Path) -> dict[str, Any]:
    return _load_json(hub_root / TRUSTED_SOURCE_REGISTRY)


def _load_language_registry(hub_root: Path) -> dict[str, Any]:
    return _load_json(hub_root / "registry" / "language-coding-advantage-registry.json")


def match_trusted_source(hub_root: Path, source_url: str) -> tuple[dict[str, Any] | None, str]:
    """Match a URL against the trusted-source registry by domain/prefix patterns."""
    normalized = source_url.lower().strip()
    if normalized.startswith("http://"):
        return None, "unknown"
    if normalized.startswith("https://"):
        normalized = normalized[len("https://"):]
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


def build_language_frontier_watchlist(
    hub_root: Path,
    *,
    language: str = "",
    cadence: str = "",
    include_manual: bool = False,
    limit: int = 0,
) -> dict[str, Any]:
    """Return a pointer-only plan for language frontier source refreshes."""
    requested_language = language.strip().lower()
    requested_cadence = cadence.strip().lower()
    if requested_cadence and requested_cadence not in {
        "weekly",
        "monthly",
        "quarterly",
        "manual",
    }:
        raise ValueError("cadence must be one of: weekly, monthly, quarterly, manual")

    trusted = load_trusted_sources(hub_root)
    language_registry = _load_language_registry(hub_root)
    language_records = {
        str(item.get("language_id")): item
        for item in language_registry.get("languages", [])
    }
    source_to_languages: dict[str, list[str]] = {}
    for language_id, record in language_records.items():
        for source_id in record.get("trusted_source_ids", []):
            source_to_languages.setdefault(str(source_id), []).append(language_id)

    rows: list[dict[str, Any]] = []
    for source in trusted.get("sources", []):
        source_id = str(source.get("source_id") or "")
        source_languages = [
            str(item).lower()
            for item in source.get("language_focus", [])
        ] or sorted(source_to_languages.get(source_id, []))
        if not source_languages:
            continue
        source_cadence = str(source.get("check_cadence") or "manual")
        if source_cadence == "manual" and not include_manual:
            continue
        if requested_language and requested_language not in source_languages:
            continue
        if requested_cadence and requested_cadence != source_cadence:
            continue
        language_routes = [
            {
                "language_id": language_id,
                "recommendable": bool(language_records.get(language_id, {}).get("recommendable")),
                "primary_assets": language_records.get(language_id, {}).get("primary_assets", []),
                "harness_routes": [
                    item.get("harness_id")
                    for item in language_records.get(language_id, {}).get(
                        "harness_routes",
                        [],
                    )
                    if item.get("harness_id")
                ],
            }
            for language_id in source_languages
            if language_id in language_records
        ]
        rows.append(
            {
                "source_id": source_id,
                "label": source.get("label"),
                "trust_tier": source.get("trust_tier"),
                "review_status": source.get("review_status"),
                "language_focus": source_languages,
                "check_cadence": source_cadence,
                "cadence_days": CADENCE_DAYS.get(source_cadence),
                "due_hint": (
                    "manual_only"
                    if source_cadence == "manual"
                    else f"refresh_every_{CADENCE_DAYS[source_cadence]}_days"
                ),
                "url_patterns": source.get("url_patterns", []),
                "frontier_watch": source.get("frontier_watch", []),
                "intake_actions": source.get("intake_actions", []),
                "asset_kinds": source.get("asset_kinds", []),
                "language_routes": language_routes,
                "candidate_mail_contract": {
                    "message_type": "capability_suggestion",
                    "dad_need_id": "dad:need:language-frontier-signals",
                    "required_fields": [
                        "language",
                        "source_id_or_url",
                        "safe_summary",
                        "why_ai_coding_may_improve",
                        "applicability_limits",
                        "proof_surface",
                        "proof_surface_refs",
                        "validation_or_eval_idea",
                        "target_dad_surface",
                    ],
                    "forbidden_fields": [
                        "copied_third_party_docs",
                        "copied_source",
                        "raw_private_rows",
                        "credentials_or_tokens",
                        "raw_logs",
                        "long_source_blobs",
                        "benchmark_claim_without_same_workload_evidence",
                    ],
                },
            }
        )

    rows.sort(
        key=lambda item: (
            item["cadence_days"] if item["cadence_days"] is not None else 9999,
            item["source_id"],
        )
    )
    if limit > 0:
        rows = rows[:limit]

    languages = sorted(
        {
            language_id
            for row in rows
            for language_id in row.get("language_focus", [])
        }
    )
    return {
        "schema_version": "0.1.0",
        "report_id": "dad:language-frontier-watchlist",
        "generated_at": utc_now(),
        "filters": {
            "language": requested_language or "all",
            "cadence": requested_cadence or "all",
            "include_manual": include_manual,
            "limit": limit,
        },
        "source_count": len(rows),
        "languages": languages,
        "rows": rows,
        "next_agent_action": (
            "Pick one row, review the source pointer directly, then create a "
            "pointer-only research intake or DAD mail packet only if it names "
            "a proof surface, applicability limits, and a local validation idea."
        ),
        "authority_boundary": LANGUAGE_FRONTIER_WATCH_AUTHORITY_BOUNDARY,
    }


def build_language_playbook_report(
    hub_root: Path,
    *,
    language: str,
    include_text: bool = False,
) -> dict[str, Any]:
    """Return the operational language coding playbook and matching registry route."""
    requested_language = language.strip().lower()
    if not requested_language:
        raise ValueError("language is required")

    manifest = _load_json(hub_root / LANGUAGE_PLAYBOOKS_MANIFEST)
    registry = _load_language_registry(hub_root)
    playbooks: dict[str, dict[str, Any]] = {}
    for item in manifest.get("playbooks", []):
        language_id = str(item.get("language_id") or "")
        if not language_id:
            raise ValueError("Language playbook manifest row missing language_id")
        if language_id in playbooks:
            raise ValueError(f"Duplicate language playbook row: {language_id}")
        playbooks[language_id] = item
    languages = {
        str(item.get("language_id")): item
        for item in registry.get("languages", [])
    }
    if requested_language not in playbooks or requested_language not in languages:
        available = sorted(set(playbooks) & set(languages))
        raise ValueError(
            "Unknown language playbook. Available language ids: "
            + ", ".join(available)
        )

    playbook = playbooks[requested_language]
    language_record = languages[requested_language]
    playbook_path = _resolve_language_playbook_path(hub_root, playbook)
    proof_surfaces = {
        str(item.get("category_id")): item
        for item in registry.get("proof_surface_categories", [])
    }
    missing_proof_refs = [
        str(proof_id)
        for proof_id in language_record.get("proof_surface_refs", [])
        if str(proof_id) not in proof_surfaces
    ]
    if missing_proof_refs:
        raise ValueError(
            f"Language {requested_language} references unknown proof surfaces: "
            + ", ".join(sorted(missing_proof_refs))
        )
    selected_proofs = [
        proof_surfaces[str(proof_id)]
        for proof_id in language_record.get("proof_surface_refs", [])
    ]
    report: dict[str, Any] = {
        "schema_version": "0.1.0",
        "report_id": "dad:language-coding-playbook",
        "generated_at": utc_now(),
        "language_id": requested_language,
        "label": language_record.get("label"),
        "status": language_record.get("status"),
        "recommendable": bool(language_record.get("recommendable")),
        "playbook_path": playbook.get("path"),
        "primary_question": playbook.get("primary_question"),
        "preflight_triggers": playbook.get("preflight_triggers", []),
        "must_check": playbook.get("must_check", []),
        "mail_back_to_dad": playbook.get("mail_back_to_dad", []),
        "primary_assets": language_record.get("primary_assets", []),
        "trusted_source_ids": language_record.get("trusted_source_ids", []),
        "check_cadence": language_record.get("check_cadence"),
        "frontier_questions": language_record.get("frontier_questions", []),
        "proof_surfaces": selected_proofs,
        "ai_advantages": language_record.get("ai_advantages", []),
        "ai_overlooked_patterns": language_record.get("ai_overlooked_patterns", []),
        "ai_overlooked_operations": language_record.get("ai_overlooked_operations", []),
        "agent_coding_guidelines": language_record.get("agent_coding_guidelines", []),
        "codebase_watch_targets": language_record.get("codebase_watch_targets", []),
        "frontier_promotion_policy": language_record.get("frontier_promotion_policy", {}),
        "harness_routes": language_record.get("harness_routes", []),
        "validation_gates": language_record.get("validation_gates", []),
        "adoption_rules": language_record.get("adoption_rules", []),
        "anti_patterns": language_record.get("anti_patterns", []),
        "research_intake_packet": language_record.get("research_intake_packet", {}),
        "next_agent_action": (
            "Use this playbook before material language work, run the named proof "
            "operations locally, then send only pointer-safe frontier or harness "
            "feedback back to DAD when the result is reusable."
        ),
        "authority_boundary": manifest.get("authority_boundary")
        or LANGUAGE_FRONTIER_WATCH_AUTHORITY_BOUNDARY,
    }
    if include_text:
        report["playbook_text"] = playbook_path.read_text(encoding="utf-8")
    return report


def _resolve_language_playbook_path(hub_root: Path, playbook: dict[str, Any]) -> Path:
    raw_path = str(playbook.get("path") or "")
    if not raw_path:
        raise ValueError("Language playbook manifest row missing path")
    rel_path = Path(raw_path)
    if rel_path.is_absolute() or ".." in rel_path.parts:
        raise ValueError(f"Unsafe language playbook path: {raw_path}")
    if rel_path.suffix.lower() != ".md":
        raise ValueError(f"Language playbook path must be a markdown file: {raw_path}")
    root = (hub_root / LANGUAGE_PLAYBOOKS_MANIFEST.parent).resolve()
    candidate = (hub_root / rel_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"Language playbook path is outside assets/language-coding-playbooks: {raw_path}"
        ) from exc
    if not candidate.exists():
        raise ValueError(f"Language playbook path does not exist: {raw_path}")
    return candidate


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
