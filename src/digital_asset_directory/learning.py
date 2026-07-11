from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .database import CatalogDB
from .ids import stable_id, session_id as new_session_id
from .models import HandoffRecord, LearningRuleRecord, LessonRecord, ReviewLaneRecord
from .dad_library import (
    CENTRAL_USAGE_LEDGER,
    central_usage_path,
    compile_context_pack,
    load_asset_patterns,
    load_offerings,
    record_trace_outcomes,
)
from .transport import data_path
from .logos_write_guard import assert_dad_write_allowed
from .utils import append_jsonl, sha256_bytes, sha256_file, split_multi, utc_now, write_json
from .exceptions_lake import hard_issue_lookup, looks_like_hard_issue_lookup_context

ASSET_USE_FEEDBACK_CODE = "DAD_ASSET_USE_FEEDBACK_V1"
REVIEW_FEEDBACK_CODE = "DAD_REVIEW_FEEDBACK_V1"
REVIEW_FEEDBACK_TYPES = {
    "red_team",
    "premortem",
    "audit",
    "code_review",
    "security_review",
    "swe_feedback",
}
REVIEW_FEEDBACK_SEVERITIES = {"critical", "high", "medium", "low", "info", "mixed"}
ACK_REQUIRED_LEVELS = {"require_ack", "human_gate"}
GENERATED_LESSON_INDEX_DIRS = {"by-repo", "by-capability"}


def raw_lessons_dir(hub_root: Path) -> Path:
    return data_path(hub_root, "raw_lessons")


def raw_handoffs_dir(hub_root: Path) -> Path:
    return data_path(hub_root, "raw_handoffs")


def audit_events_dir(hub_root: Path) -> Path:
    return data_path(hub_root, "audit_events")


def agent_sessions_dir(hub_root: Path) -> Path:
    return data_path(hub_root, "agent_sessions")


def learning_dir(hub_root: Path) -> Path:
    return data_path(hub_root, "learning")


def lesson_graph_path(hub_root: Path) -> Path:
    return learning_dir(hub_root) / LESSON_GRAPH_PATH.relative_to(Path("processed") / "learning")


def lesson_graph_manifest_path(hub_root: Path) -> Path:
    return learning_dir(hub_root) / LESSON_GRAPH_MANIFEST_PATH.relative_to(Path("processed") / "learning")


def _repo_public_facing(repo: Path) -> bool:
    contract = repo / ".digital-asset" / "dad-integration.json"
    if not contract.exists():
        return False
    try:
        payload = json.loads(contract.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(payload.get("public_facing"))


def _hard_issue_signals(*values: Any) -> list[str]:
    text = " ".join(str(value or "") for value in values).lower()
    signals: set[str] = set()
    if any(term in text for term in ("permission", "winerror", "access denied", "os.replace")):
        signals.add("permission_denied")
    if "stale" in text or "outdated" in text:
        signals.add("stale_report")
    if "malformed" in text or "jsonl" in text:
        signals.add("malformed_jsonl")
    if "timeout" in text:
        signals.add("command_timeout")
    if "tool unavailable" in text or "not available on path" in text:
        signals.add("tool_unavailable")
    if "test" in text and any(term in text for term in ("fail", "failed", "failure")):
        signals.add("test_failure")
    if any(term in text for term in ("fail", "failed", "failure", "exception", "error")):
        signals.add("failed_command")
    return sorted(signals)


def _maybe_hard_issue_lookup(
    hub_root: Path,
    target_repo: Path,
    *,
    task: str,
    context: list[str] | None = None,
    paths: list[str] | None = None,
    limit: int = 3,
) -> dict[str, Any] | None:
    context_values = context or []
    path_values = paths or []
    if not looks_like_hard_issue_lookup_context(task, context_values, path_values):
        return None
    query = " ".join([task, *context_values])
    try:
        return hard_issue_lookup(
            hub_root,
            query=query,
            signals=_hard_issue_signals(task, context_values, path_values),
            path_refs=path_values,
            limit=limit,
            target_public_facing=_repo_public_facing(target_repo),
        )
    except Exception as exc:
        return {
            "schema_version": "0.1.0",
            "status": "unavailable",
            "error": str(exc),
            "match_count": 0,
            "matches": [],
            "warnings": ["hard issue lookup unavailable; record exception/fix outcome if material"],
            "authority_boundary": "Unavailable lookup does not authorize skipping local validation or source authority.",
        }


def git_changed_files(repo: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    return [
        line[3:] if len(line) > 3 else line for line in result.stdout.splitlines() if line.strip()
    ]


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "unknown"


def _lesson_pointer(record: LessonRecord) -> dict[str, Any]:
    dated = record.created_at[:10]
    return {
        "lesson_id": record.lesson_id,
        "created_at": record.created_at,
        "repository": record.repository,
        "summary": record.summary,
        "reusable_patterns": record.reusable_patterns,
        "missing_capabilities": record.missing_capabilities,
        "session_id": record.session_id,
        "source_path": f"raw/lessons/{dated}/{record.lesson_id.split(':')[-1]}.json",
    }


def _learning_rule_pointer(record: LearningRuleRecord) -> dict[str, Any]:
    return {
        "rule_id": record.rule_id,
        "title": record.title,
        "summary": record.summary,
        "context_tags": record.context_tags,
        "applies_when": record.applies_when,
        "does_not_apply_when": record.does_not_apply_when,
        "required_actions": record.required_actions,
        "danger_if_ignored": record.danger_if_ignored,
        "evidence": record.evidence,
        "enforcement_level": record.enforcement_level,
        "review_status": record.review_status,
    }


def load_learning_rules(repo_root: Path) -> list[LearningRuleRecord]:
    path = repo_root / "registry" / "learning-rule-registry.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = [
        LearningRuleRecord.model_validate(item)
        for item in payload.get("rules", [])
        if item.get("review_status") == "reviewed"
    ]
    seen: set[str] = set()
    deduped: list[LearningRuleRecord] = []
    for record in sorted(records, key=lambda item: item.rule_id):
        if record.rule_id in seen:
            raise ValueError(f"Duplicate learning rule ID: {record.rule_id}")
        seen.add(record.rule_id)
        deduped.append(record)
    return deduped


def match_learning_rules(
    repo_root: Path,
    *,
    task: str = "",
    context: list[str] | None = None,
    paths: list[str] | None = None,
) -> list[dict[str, Any]]:
    context_values = context or []
    path_values = paths or []
    text_blob = "\n".join([task, *context_values, *path_values]).lower().replace("\\", "/")
    matched: list[dict[str, Any]] = []
    for record in load_learning_rules(repo_root):
        term_hits = [
            term
            for term in record.trigger_terms
            if term and term.lower() in text_blob
        ]
        path_hits = [
            pattern
            for pattern in record.trigger_path_patterns
            if pattern and pattern.lower().replace("\\", "/") in text_blob
        ]
        if not term_hits and not path_hits:
            continue
        pointer = _learning_rule_pointer(record)
        pointer["matched_terms"] = term_hits
        pointer["matched_path_patterns"] = path_hits
        matched.append(pointer)
    return matched


def required_learning_rule_ids(matches: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(match["rule_id"])
            for match in matches
            if match.get("enforcement_level") in ACK_REQUIRED_LEVELS
        }
    )


def route_lesson(repo_root: Path, record: LessonRecord) -> list[Path]:
    """Append a context-rich pointer to repo- and capability-scoped lesson indexes.

    The dated canonical JSON under raw/lessons/<date>/ stays the source of truth; these
    append-only JSONL indexes make a lesson findable by repository and by capability,
    instead of only by the date it was captured.
    """
    pointer = _lesson_pointer(record)
    base = raw_lessons_dir(repo_root)
    written: list[Path] = []

    repo_name = Path(record.repository).name if record.repository else "unknown"
    repo_index = base / "by-repo" / f"{_slug(repo_name)}.jsonl"
    append_jsonl(repo_index, pointer)
    written.append(repo_index)

    for capability in sorted(dict.fromkeys(record.missing_capabilities or ["_general"])):
        cap_index = base / "by-capability" / f"{_slug(capability)}.jsonl"
        append_jsonl(cap_index, pointer)
        written.append(cap_index)
    return written


def rebuild_lesson_routes(repo_root: Path) -> dict[str, Any]:
    """Rebuild by-repo and by-capability indexes from the canonical dated lesson files.

    Indexes are append-only at capture time, so re-running this dedupes by lesson_id.
    """
    base = raw_lessons_dir(repo_root)
    assert_dad_write_allowed(base)
    for sub in ("by-repo", "by-capability"):
        target = base / sub
        if target.exists():
            for path in target.glob("*.jsonl"):
                path.unlink()
    indexed = 0
    for record in _load_canonical_lessons(repo_root):
        route_lesson(repo_root, record)
        indexed += 1
    return {
        "lessons_indexed": indexed,
        "by_repo_dir": str(base / "by-repo"),
        "by_capability_dir": str(base / "by-capability"),
    }


LESSON_GRAPH_PATH = Path("processed") / "learning" / "lesson-graph.json"
LESSON_GRAPH_MANIFEST_PATH = Path("processed") / "learning" / "lesson-graph-manifest.json"
LESSON_GRAPH_EDGE_RULE = (
    "Edges are deterministic joins named in edge_basis. They are generated candidate "
    "evidence for review and pattern-gap discovery, not proof of relationship value."
)
DEFAULT_GRAPH_EDGE_REGISTRY = {
    "registry_version": "0.1.0",
    "status": "seed",
    "edge_types": [
        {
            "edge_type": "learned_in",
            "edge_class": "join",
            "direction": "lesson -> repo",
            "cardinality": "many-to-one",
            "semantics": "A canonical lesson record names the repository where the lesson was learned.",
            "allowed_bases": ["lesson.repository"],
            "evidence_required": ["canonical lesson record repository field"],
            "version": "0.1.0",
            "examples": ["lesson:dad:lesson:x -> repo:example"],
            "danger_if_wrong": "Lessons can be routed to the wrong repo history.",
            "review_status": "reviewed",
        },
        {
            "edge_type": "about_asset",
            "edge_class": "join",
            "direction": "lesson -> offering",
            "cardinality": "many-to-many",
            "semantics": "A lesson evidence pointer names a registered DAD offering.",
            "allowed_bases": ["lesson.evidence.asset-ref"],
            "evidence_required": ["asset:<offering_id> evidence pointer", "registered offering id"],
            "version": "0.1.0",
            "examples": ["lesson:dad:lesson:x -> offering:dad:offering:y"],
            "danger_if_wrong": "Asset feedback and upgrade targeting can attach to the wrong offering.",
            "review_status": "reviewed",
        },
        {
            "edge_type": "matches_pattern",
            "edge_class": "join",
            "direction": "lesson -> pattern",
            "cardinality": "many-to-many",
            "semantics": "A lesson reusable-pattern value matches a reviewed pattern id or label.",
            "allowed_bases": ["lesson.reusable_patterns.pattern-id-or-label"],
            "evidence_required": ["lesson reusable_patterns entry", "reviewed pattern registry row"],
            "version": "0.1.0",
            "examples": ["lesson:dad:lesson:x -> pattern:governed_learning_loop_system"],
            "danger_if_wrong": "Pattern-gap curation can be polluted by accidental prose matches.",
            "review_status": "reviewed",
        },
        {
            "edge_type": "uses_asset",
            "edge_class": "join",
            "direction": "repo -> offering",
            "cardinality": "many-to-many",
            "semantics": "A repo usage ledger row says the repo is using an offering.",
            "allowed_bases": ["usage.status.using"],
            "evidence_required": ["repo asset usage ledger row with status using"],
            "version": "0.1.0",
            "examples": ["repo:example -> offering:dad:offering:y"],
            "danger_if_wrong": "Upgrade mail can target repos that are not using the asset.",
            "review_status": "reviewed",
        },
        {
            "edge_type": "watches_asset",
            "edge_class": "join",
            "direction": "repo -> offering",
            "cardinality": "many-to-many",
            "semantics": "A repo usage ledger row says the repo is watching an offering for possible future use.",
            "allowed_bases": ["usage.status.watching"],
            "evidence_required": ["repo asset usage ledger row with status watching"],
            "version": "0.1.0",
            "examples": ["repo:example -> offering:dad:offering:y"],
            "danger_if_wrong": "Future-use recommendations can spam repos with irrelevant upgrades.",
            "review_status": "reviewed",
        },
    ],
}


def _pattern_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _load_graph_edge_registry(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "registry" / "graph-edge-registry.json"
    if not path.exists():
        return DEFAULT_GRAPH_EDGE_REGISTRY
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return f"sha256:{sha256_file(path)}"
    parts: list[str] = []
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        try:
            rel = child.relative_to(path).as_posix()
        except ValueError:
            rel = child.name
        if path.name == "lessons" and rel.split("/", 1)[0] in GENERATED_LESSON_INDEX_DIRS:
            continue
        parts.append(f"{rel}\0{sha256_file(child)}")
    digest_input = "\n".join(parts).encode("utf-8")
    return f"sha256:{sha256_bytes(digest_input)}"


def _load_canonical_lessons(repo_root: Path) -> list[LessonRecord]:
    base = raw_lessons_dir(repo_root)
    seen: set[str] = set()
    lessons: list[LessonRecord] = []
    for path in sorted(base.glob("*/*.json")):
        if path.parent.name in {"by-repo", "by-capability"}:
            continue
        try:
            record = LessonRecord.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if record.lesson_id in seen:
            continue
        seen.add(record.lesson_id)
        lessons.append(record)
    return lessons


def build_lesson_graph(repo_root: Path) -> dict[str, Any]:
    """Compile lessons, patterns, offerings, agent skills, repos, and usage.

    The graph is a rebuildable compilation of existing raw records: dated lesson files
    stay the source of truth, every edge carries the deterministic edge_basis that
    produced it, and reusable-pattern names that match no pattern card are surfaced as
    pattern-gap candidates instead of being dropped.
    """
    try:
        pattern_registry = load_asset_patterns(repo_root)
    except FileNotFoundError:
        pattern_registry = {"registry_version": "", "patterns": []}
    try:
        offerings = load_offerings(repo_root).get("offerings", [])
    except FileNotFoundError:
        offerings = []
    agent_skill_registry_path = repo_root / "registry" / "agent-skill-library.json"
    if agent_skill_registry_path.exists():
        agent_skills = json.loads(
            agent_skill_registry_path.read_text(encoding="utf-8")
        ).get("skills", [])
    else:
        agent_skills = []
    edge_registry = _load_graph_edge_registry(repo_root)
    edge_defs = {
        str(row["edge_type"]): row for row in edge_registry.get("edge_types", [])
    }

    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    pattern_gap_counts: dict[str, int] = {}
    unmatched_asset_refs: dict[str, int] = {}

    pattern_ids_by_key: dict[str, str] = {}
    for pattern in pattern_registry.get("patterns", []):
        pattern_id = str(pattern.get("id", ""))
        if not pattern_id:
            continue
        nodes[f"pattern:{pattern_id}"] = {
            "node_id": f"pattern:{pattern_id}",
            "node_type": "pattern",
            "label": str(pattern.get("label", pattern_id)),
            "leverage": str(pattern.get("leverage", "")),
        }
        pattern_ids_by_key[_pattern_key(pattern_id)] = pattern_id
        label_key = _pattern_key(str(pattern.get("label", "")))
        if label_key:
            pattern_ids_by_key.setdefault(label_key, pattern_id)

    offering_ids: set[str] = set()
    for offering in offerings:
        offering_id = str(offering.get("offering_id", ""))
        if not offering_id:
            continue
        offering_ids.add(offering_id)
        nodes[f"offering:{offering_id}"] = {
            "node_id": f"offering:{offering_id}",
            "node_type": "offering",
            "label": str(offering.get("name", offering_id)),
            "offering_type": str(offering.get("offering_type", "")),
        }

    for skill in agent_skills:
        skill_id = str(skill.get("skill_id", ""))
        if not skill_id:
            continue
        nodes[f"skill:{skill_id}"] = {
            "node_id": f"skill:{skill_id}",
            "node_type": "agent_skill",
            "label": str(skill.get("name", skill_id)),
            "version": str(skill.get("version", "")),
            "status": str(skill.get("status", "")),
            "review_status": str(skill.get("review_status", "")),
            "capabilities": sorted(
                str(value) for value in skill.get("capabilities", []) if str(value)
            ),
        }

    def repo_node_id(repository: str) -> str:
        name = Path(repository).name if repository else "unknown"
        node_id = f"repo:{_pattern_key(name) or 'unknown'}"
        nodes.setdefault(
            node_id,
            {"node_id": node_id, "node_type": "repo", "label": name or "unknown"},
        )
        return node_id

    def add_edge(
        source: str,
        target: str,
        edge_type: str,
        edge_basis: str,
        evidence_refs: list[str],
    ) -> None:
        edge_id = stable_id("lesson-graph-edge", source, target, edge_type)
        edge_def = edge_defs.get(edge_type, {"edge_class": "join"})
        edges.setdefault(
            edge_id,
            {
                "edge_id": edge_id,
                "source": source,
                "target": target,
                "edge_type": edge_type,
                "edge_class": str(edge_def.get("edge_class", "join")),
                "edge_basis": edge_basis,
                "method_version": "",
                "created_at": "",
                "evidence_refs": sorted(dict.fromkeys(evidence_refs)),
                "review_status": "candidate",
            },
        )

    lessons = _load_canonical_lessons(repo_root)
    for lesson in lessons:
        lesson_node = f"lesson:{lesson.lesson_id}"
        nodes[lesson_node] = {
            "node_id": lesson_node,
            "node_type": "lesson",
            "label": lesson.summary[:120],
            "created_at": lesson.created_at,
            "confidence": lesson.confidence,
            "review_status": lesson.review_status,
        }
        add_edge(
            lesson_node,
            repo_node_id(lesson.repository),
            "learned_in",
            "lesson.repository",
            [lesson.lesson_id],
        )
        for raw_pattern in lesson.reusable_patterns or []:
            key = _pattern_key(str(raw_pattern))
            if not key:
                continue
            pattern_id = pattern_ids_by_key.get(key)
            if pattern_id:
                add_edge(
                    lesson_node,
                    f"pattern:{pattern_id}",
                    "matches_pattern",
                    "lesson.reusable_patterns.pattern-id-or-label",
                    [lesson.lesson_id, f"pattern:{pattern_id}"],
                )
            else:
                pattern_gap_counts[key] = pattern_gap_counts.get(key, 0) + 1
        for evidence in lesson.evidence or []:
            text = str(evidence)
            if not text.startswith("asset:"):
                continue
            asset_id = text[len("asset:"):].strip()
            if asset_id in offering_ids:
                add_edge(
                    lesson_node,
                    f"offering:{asset_id}",
                    "about_asset",
                    "lesson.evidence.asset-ref",
                    [lesson.lesson_id, f"offering:{asset_id}"],
                )
            elif asset_id:
                unmatched_asset_refs[asset_id] = unmatched_asset_refs.get(asset_id, 0) + 1

    for row in _read_jsonl_records(central_usage_path(repo_root, CENTRAL_USAGE_LEDGER)):
        status = str(row.get("status", ""))
        if status not in {"using", "watching"}:
            continue
        asset_id = str(row.get("asset_id", ""))
        if asset_id not in offering_ids:
            continue
        edge_type = "uses_asset" if status == "using" else "watches_asset"
        add_edge(
            repo_node_id(str(row.get("repo", ""))),
            f"offering:{asset_id}",
            edge_type,
            f"usage.status.{status}",
            [str(row.get("usage_id", "")) or stable_id("usage-row", row)],
        )

    nodes_by_type: dict[str, int] = {}
    for node in nodes.values():
        nodes_by_type[node["node_type"]] = nodes_by_type.get(node["node_type"], 0) + 1
    edges_by_type: dict[str, int] = {}
    for edge in edges.values():
        edges_by_type[edge["edge_type"]] = edges_by_type.get(edge["edge_type"], 0) + 1

    payload = {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "edge_registry_version": str(edge_registry.get("registry_version", "")),
        "manifest_path": LESSON_GRAPH_MANIFEST_PATH.as_posix(),
        "pattern_library_version": str(pattern_registry.get("registry_version", "")),
        "lesson_count": len(lessons),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes_by_type": nodes_by_type,
        "edges_by_type": edges_by_type,
        "nodes": sorted(nodes.values(), key=lambda item: item["node_id"]),
        "edges": sorted(edges.values(), key=lambda item: item["edge_id"]),
        "pattern_gap_candidates": [
            {"reusable_pattern": key, "lesson_mentions": count}
            for key, count in sorted(
                pattern_gap_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "unmatched_asset_refs": [
            {"asset_id": key, "lesson_mentions": count}
            for key, count in sorted(
                unmatched_asset_refs.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "edge_rule": LESSON_GRAPH_EDGE_RULE,
        "authority_boundary": (
            "Lesson-graph nodes and edges are generated candidate evidence compiled "
            "from raw lessons, registries, and usage ledgers. They guide review and "
            "pattern-library growth; they do not prove value or source truth."
        ),
    }
    out_path = lesson_graph_path(repo_root)
    write_json(out_path, payload, allow_direct_fallback=True)
    edge_registry_hash = _hash_path(repo_root / "registry" / "graph-edge-registry.json")
    input_hashes = {
        "raw/lessons": _hash_path(raw_lessons_dir(repo_root)),
        "registry/asset-pattern-registry.json": _hash_path(
            repo_root / "registry" / "asset-pattern-registry.json"
        ),
        "registry/dad-offerings-registry.json": _hash_path(
            repo_root / "registry" / "dad-offerings-registry.json"
        ),
        "registry/agent-skill-library.json": _hash_path(agent_skill_registry_path),
        str(CENTRAL_USAGE_LEDGER): _hash_path(
            central_usage_path(repo_root, CENTRAL_USAGE_LEDGER)
        ),
        "registry/graph-edge-registry.json": edge_registry_hash,
    }
    edge_types_present = sorted(edges_by_type)
    manifest = {
        "schema_version": "0.1.0",
        "surface_id": "lesson-graph",
        "ontology_id": "knowledge",
        "generated_at": payload["generated_at"],
        "builder_version": "lesson-graph-builder.v0.2.0",
        "graph_path": LESSON_GRAPH_PATH.as_posix(),
        "manifest_path": LESSON_GRAPH_MANIFEST_PATH.as_posix(),
        "edge_registry_version": payload["edge_registry_version"],
        "edge_registry_hash": edge_registry_hash,
        "input_hashes": input_hashes,
        "methodology_hashes": {
            "builder_source": _hash_path(Path(__file__)),
        },
        "graph_content_hash": _hash_path(out_path),
        "freshness": {
            "state": "fresh",
            "computed_at": payload["generated_at"],
            "reasons": [],
        },
        "counts": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "node_type_count": len(nodes_by_type),
            "edge_type_count": len(edges_by_type),
        },
        "nodes_by_type": nodes_by_type,
        "edges_by_type": edges_by_type,
        "edge_definitions_present": {
            edge_type: edge_defs[edge_type]
            for edge_type in edge_types_present
            if edge_type in edge_defs
        },
        "method_versions_used": sorted(
            {
                str(edge.get("method_version", ""))
                for edge in edges.values()
                if str(edge.get("method_version", ""))
            }
        ),
        "coverage_report": {
            "registered_edge_types_with_zero_edges": sorted(
                edge_type
                for edge_type in edge_defs
                if edge_type not in edges_by_type
            ),
            "pattern_gap_candidate_count": len(pattern_gap_counts),
            "unmatched_asset_ref_count": len(unmatched_asset_refs),
            "lesson_records_without_pattern_edges": sum(
                1
                for lesson in lessons
                if not any(edge["source"] == f"lesson:{lesson.lesson_id}" and edge["edge_type"] == "matches_pattern" for edge in edges.values())
            ),
            "offering_count": len(offering_ids),
            "agent_skill_count": len(agent_skills),
        },
        "authority_boundary": payload["authority_boundary"],
    }
    manifest_path = lesson_graph_manifest_path(repo_root)
    write_json(manifest_path, manifest, allow_direct_fallback=True)
    return {"graph": payload, "path": str(out_path), "manifest_path": str(manifest_path)}


def add_lesson(repo_root: Path, database_path: Path, **kwargs: Any) -> LessonRecord:
    created = utc_now()
    record = LessonRecord(
        lesson_id=stable_id(
            "lesson", created, kwargs.get("repository", ""), kwargs.get("summary", "")
        ),
        created_at=created,
        repository=str(kwargs.get("repository", "")),
        task=str(kwargs.get("task", "")),
        agent=str(kwargs.get("agent", "human")),
        model=kwargs.get("model"),
        summary=str(kwargs.get("summary", "")),
        lessons=split_multi(kwargs.get("lessons")),
        files_changed=split_multi(kwargs.get("files_changed")),
        tests_run=split_multi(kwargs.get("tests_run")),
        tests_not_run=split_multi(kwargs.get("tests_not_run")),
        discoveries=split_multi(kwargs.get("discoveries")),
        failures=split_multi(kwargs.get("failures")),
        reusable_patterns=split_multi(kwargs.get("reusable_patterns")),
        missing_capabilities=split_multi(kwargs.get("missing_capabilities")),
        evidence=split_multi(kwargs.get("evidence")),
        confidence=kwargs.get("confidence", "medium"),
        review_status=kwargs.get("review_status", "candidate"),
        session_id=kwargs.get("session_id"),
    )
    dated = created[:10]
    write_json(
        raw_lessons_dir(repo_root) / dated / f"{record.lesson_id.split(':')[-1]}.json",
        record.model_dump(mode="json"),
    )
    route_lesson(repo_root, record)
    append_jsonl(
        audit_events_dir(repo_root) / f"{dated}.jsonl",
        {
            "event_type": "lesson_added",
            "created_at": created,
            "object_id": record.lesson_id,
            "repository": record.repository,
        },
    )
    with CatalogDB(database_path) as db:
        db.add_lesson(record)
    return record


def add_asset_use_feedback(
    repo_root: Path,
    database_path: Path,
    *,
    asset_id: str,
    repository: str,
    task: str,
    agent: str,
    used_for: str,
    use_outcome: str = "unknown",
    observed_usefulness: str = "unknown",
    observed_futurefulness: str = "unknown",
    interaction_stage: str = "after_use",
    expected_usefulness: str = "unknown",
    expected_futurefulness: str = "unknown",
    expected_value_reason: str = "",
    planned_use: str = "",
    found_by: str = "",
    found_query: str = "",
    issue_addressed: str = "",
    parts_used: list[str] | None = None,
    parts_not_used: list[str] | None = None,
    not_used_reason: str = "",
    upgrades_made: list[str] | None = None,
    difficulties: list[str] | None = None,
    things_learned: list[str] | None = None,
    reuse_when: list[str] | None = None,
    avoid_when: list[str] | None = None,
    pay_forward_guidance: str = "",
    next_agent_actions: list[str] | None = None,
    missing_parts_seen: list[str] | None = None,
    score_feedback: str = "",
    ceiling_feedback: str = "",
    evidence: list[str] | None = None,
    model: str | None = None,
    confidence: str = "medium",
) -> LessonRecord:
    allowed_outcomes = {"helped", "blocked", "no_effect", "unknown"}
    allowed_observations = {"low", "medium", "high", "unknown"}
    allowed_stages = {"before_use", "after_use"}
    if interaction_stage not in allowed_stages:
        raise ValueError(
            "interaction_stage must be one of: " + ", ".join(sorted(allowed_stages))
        )
    if use_outcome not in allowed_outcomes:
        raise ValueError(
            "use_outcome must be one of: " + ", ".join(sorted(allowed_outcomes))
        )
    if observed_usefulness not in allowed_observations:
        raise ValueError(
            "observed_usefulness must be one of: "
            + ", ".join(sorted(allowed_observations))
        )
    if observed_futurefulness not in allowed_observations:
        raise ValueError(
            "observed_futurefulness must be one of: "
            + ", ".join(sorted(allowed_observations))
        )
    if expected_usefulness not in allowed_observations:
        raise ValueError(
            "expected_usefulness must be one of: "
            + ", ".join(sorted(allowed_observations))
        )
    if expected_futurefulness not in allowed_observations:
        raise ValueError(
            "expected_futurefulness must be one of: "
            + ", ".join(sorted(allowed_observations))
        )

    missing_parts = missing_parts_seen or []
    evidence_items = evidence or []
    feedback_separator = re.compile(r"[,;\r\n]+")

    def clean_feedback_value(value: str) -> str:
        cleaned = feedback_separator.sub(" | ", str(value))
        return re.sub(r"\s*\|\s*", " | ", cleaned).strip()

    def join_feedback_values(values: list[str] | None) -> str:
        return " | ".join(
            cleaned
            for item in values or []
            if (cleaned := clean_feedback_value(item))
        )

    feedback_lines = [
        f"feedback_code={ASSET_USE_FEEDBACK_CODE}",
        f"interaction_stage={interaction_stage}",
        f"asset_id={clean_feedback_value(asset_id)}",
        f"found_by={clean_feedback_value(found_by)}",
        f"found_query={clean_feedback_value(found_query)}",
        f"issue_addressed={clean_feedback_value(issue_addressed)}",
        f"used_for={clean_feedback_value(used_for)}",
        f"planned_use={clean_feedback_value(planned_use)}",
        f"expected_usefulness={expected_usefulness}",
        f"expected_futurefulness={expected_futurefulness}",
        f"expected_value_reason={clean_feedback_value(expected_value_reason)}",
        "parts_used=" + join_feedback_values(parts_used),
        "parts_not_used=" + join_feedback_values(parts_not_used),
        f"not_used_reason={clean_feedback_value(not_used_reason)}",
        "upgrades_made=" + join_feedback_values(upgrades_made),
        "difficulties=" + join_feedback_values(difficulties),
        "things_learned=" + join_feedback_values(things_learned),
        "reuse_when=" + join_feedback_values(reuse_when),
        "avoid_when=" + join_feedback_values(avoid_when),
        f"pay_forward_guidance={clean_feedback_value(pay_forward_guidance)}",
        "next_agent_actions=" + join_feedback_values(next_agent_actions),
        f"use_outcome={use_outcome}",
        f"observed_usefulness={observed_usefulness}",
        f"observed_futurefulness={observed_futurefulness}",
    ]
    if missing_parts:
        feedback_lines.append("missing_parts_seen=" + join_feedback_values(missing_parts))
    if score_feedback:
        feedback_lines.append(f"score_feedback={clean_feedback_value(score_feedback)}")
    if ceiling_feedback:
        feedback_lines.append(f"ceiling_feedback={clean_feedback_value(ceiling_feedback)}")

    return add_lesson(
        repo_root,
        database_path,
        repository=repository,
        task=task,
        agent=agent,
        model=model,
        summary=f"Asset use feedback for {asset_id}: {interaction_stage}/{use_outcome}",
        lessons=feedback_lines,
        discoveries=[
            (
                "Observed asset usefulness feedback is candidate evidence for future "
                "score-range and ceiling-range calibration."
            ),
            (
                "Pay-forward guidance helps future agents reuse the asset in the right "
                "context without treating one use as source truth."
            )
        ],
        reusable_patterns=["asset_use_feedback_loop", "asset_use_pay_forward_loop"],
        missing_capabilities=missing_parts,
        evidence=[f"asset:{asset_id}", *evidence_items],
        confidence=confidence,
        review_status="candidate",
    )


def add_review_feedback(
    repo_root: Path,
    database_path: Path,
    *,
    repository: str,
    task: str,
    agent: str,
    review_type: str,
    findings: list[str],
    model: str | None = None,
    severity: str = "mixed",
    confirmed: list[str] | None = None,
    recommendations: list[str] | None = None,
    paths: list[str] | None = None,
    evidence: list[str] | None = None,
    confidence: str = "medium",
) -> LessonRecord:
    """Record red-team/premortem/audit/code-review findings from any agent as a minable lesson.

    Findings stay candidate evidence with agent and model attribution; DAD mines them for
    repeated failure patterns via the lesson graph and the swe_review_feedback_loop pattern
    card. Findings must be summaries and pointers, never copied source blobs or secrets.
    """
    if review_type not in REVIEW_FEEDBACK_TYPES:
        raise ValueError("review_type must be one of: " + ", ".join(sorted(REVIEW_FEEDBACK_TYPES)))
    if severity not in REVIEW_FEEDBACK_SEVERITIES:
        raise ValueError("severity must be one of: " + ", ".join(sorted(REVIEW_FEEDBACK_SEVERITIES)))
    cleaned_findings = [str(item).strip() for item in findings if str(item).strip()]
    if not cleaned_findings:
        raise ValueError("review feedback requires at least one non-empty finding")
    feedback_lines = [
        f"feedback_code={REVIEW_FEEDBACK_CODE}",
        f"review_type={review_type}",
        f"agent={agent}",
        f"model={model or 'unknown'}",
        f"severity={severity}",
        *[f"finding={item}" for item in cleaned_findings],
        *[f"confirmed={str(item).strip()}" for item in confirmed or [] if str(item).strip()],
        *[
            f"recommendation={str(item).strip()}"
            for item in recommendations or []
            if str(item).strip()
        ],
    ]
    return add_lesson(
        repo_root,
        database_path,
        repository=repository,
        task=task,
        agent=agent,
        model=model,
        summary=(
            f"{review_type} feedback from {agent}: "
            f"{len(cleaned_findings)} finding(s), severity {severity}"
        ),
        lessons=feedback_lines,
        discoveries=[
            "Review findings are candidate evidence for pattern mining; repeated finding "
            "classes across repos are promotion candidates for rules, harness checks, or "
            "pattern cards."
        ],
        files_changed=paths,
        reusable_patterns=["swe_review_feedback_loop"],
        missing_capabilities=[review_type],
        evidence=evidence,
        confidence=confidence,
        review_status="candidate",
    )


MATERIAL_LEARNING_LANE_IDS = (
    "review-lane:learning-loop-completion",
    "review-lane:digital-asset-pattern-discovery",
    "review-lane:conversation-prompt-value",
)


def _is_material_work(task: str, paths: list[str] | None = None) -> bool:
    task_text = task.lower()
    path_text = " ".join(paths or []).lower()
    substantial_signals = {
        "coding",
        "build",
        "implementation",
        "refactor",
        "investigation",
        "deploy",
        "cross-repo",
        "test",
        "governance",
        "mail",
        "enrollment",
        "schema",
        "registry",
        "asset",
        "harness",
        "template",
        "public",
        "private",
    }
    return any(signal in task_text or signal in path_text for signal in substantial_signals)


def recommended_review_lanes(task: str, paths: list[str] | None = None) -> list[dict[str, Any]]:
    """Return lightweight review lanes future agents can run as subagents or checklists."""
    material = _is_material_work(task, paths)
    mode = "subagent_when_available_else_checklist" if material else "checklist_if_useful"
    return [
        {
            "lane_id": "review-lane:red-team-and-premortem",
            "mode": mode,
            "purpose": "Independently check the change for bugs, false confidence, governance drift, sensitive-data movement, and missing tests.",
            "capture": "Add findings to the task summary and route reusable safety lessons through DAD postflight or candidate mail.",
            "required_for": "material coding, governance, schema, mail, enrollment, public/private, or cross-repo work",
        },
        {
            "lane_id": "review-lane:lesson-asset-harness-scout",
            "mode": mode,
            "purpose": "Look for reusable lessons, novel/important digital assets, coding-harness ideas, skill updates, and DAD needs discovered during the work.",
            "capture": "Record candidate lessons/assets/harness ideas in postflight and, for downstream repos, in the repo outbox when local policy allows.",
            "required_for": "material work where a reusable lesson, asset, harness, or workflow may have been learned",
        },
        {
            "lane_id": "review-lane:learning-loop-completion",
            "mode": mode,
            "purpose": "Find and close incomplete learning loops, escalating effort only for uncertainty, conflict, or high leverage.",
            "capture": "Record completed loops, incomplete loops, agent ratings, and the smallest next action.",
            "required_for": "every material build, refactor, investigation, or cross-repo task",
        },
        {
            "lane_id": "review-lane:digital-asset-pattern-discovery",
            "mode": mode,
            "purpose": "Find reusable assets, missed-asset signals, and novel patterns for discovering, grading, or applying assets.",
            "capture": "Dedupe against DAD and record privacy-safe candidates with targets and falsifiable validators.",
            "required_for": "every material build, refactor, investigation, or cross-repo task",
        },
        {
            "lane_id": "review-lane:conversation-prompt-value",
            "mode": mode,
            "purpose": "Capture explicit reusable conversation decisions and exceptional prompts absent from final artifacts.",
            "capture": "Store only privacy-safe summaries; exclude raw transcripts, hidden reasoning, secrets, and private payloads.",
            "required_for": "every material build, refactor, investigation, or cross-repo task",
        },
    ]


def parse_review_lane_records(values: Any) -> list[ReviewLaneRecord]:
    lanes: dict[str, ReviewLaneRecord] = {
        lane["lane_id"]: ReviewLaneRecord(
            lane_id=lane["lane_id"],
            status="not_run",
            reviewer="",
            summary="Review lane was recommended but not recorded.",
            findings=[],
            candidate_outputs=[],
            follow_up=["Record this lane as subagent, checklist, or not_applicable."],
        )
        for lane in recommended_review_lanes("")
    }
    for value in _review_lane_values(values):
        parsed = _parse_review_lane_value(value)
        lanes[parsed.lane_id] = parsed
    return list(lanes.values())


def _review_lane_values(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        return [values]
    return [str(value) for value in values if str(value).strip()]


def _parse_review_lane_value(value: str) -> ReviewLaneRecord:
    text = value.strip()
    if not text:
        raise ValueError("review lane record cannot be empty")
    if text.startswith("{"):
        payload = json.loads(text)
        return ReviewLaneRecord.model_validate(payload)
    parts = text.split(":", 3)
    if len(parts) < 3 or parts[0] != "review-lane":
        raise ValueError(
            "review lane must be JSON or review-lane:<name>:<status>[:summary]"
        )
    lane_id = f"{parts[0]}:{parts[1]}"
    status = parts[2]
    summary = parts[3] if len(parts) > 3 else ""
    return ReviewLaneRecord(
        lane_id=lane_id,
        status=status,
        reviewer="agent",
        summary=summary,
    )


def preflight(
    hub_root: Path,
    target_repo: Path,
    database_path: Path,
    agent: str,
    task: str,
    model: str | None = None,
) -> dict[str, Any]:
    sid = new_session_id()
    baseline_changed_files = git_changed_files(target_repo)
    learning_rule_matches = match_learning_rules(
        hub_root,
        task=task,
        paths=baseline_changed_files,
    )
    try:
        from .mail_center import mail_digest_status

        digest_status = mail_digest_status(target_repo.resolve())
    except Exception as exc:
        digest_status = {
            "status": "unavailable",
            "stale": True,
            "error": str(exc),
        }
    try:
        from .daemon import daemon_status

        heartbeat_status = daemon_status(hub_root)
    except Exception as exc:
        heartbeat_status = {
            "status": "unavailable",
            "stale": True,
            "error": str(exc),
        }
    try:
        from .mail_center import resurface_deferred_mail

        deferred_mail = resurface_deferred_mail(
            target_repo.resolve(), task=task, hub_root=hub_root
        )
    except Exception as exc:
        deferred_mail = {
            "deferred_total": 0,
            "match_basis": "",
            "items": [],
            "error": str(exc),
        }
    payload: dict[str, Any] = {
        "schema_version": "0.1.0",
        "session_id": sid,
        "created_at": utc_now(),
        "repository": str(target_repo.resolve()),
        "agent": agent,
        "model": model,
        "task": task,
        "status": "open",
        "baseline_changed_files": baseline_changed_files,
        "required_postflight": True,
        "learning_rule_matches": learning_rule_matches,
        "required_learning_rule_acknowledgements": required_learning_rule_ids(
            learning_rule_matches
        ),
        "learning_rule_acknowledgements": [],
        "mail_digest_status": digest_status,
        "daemon_status": heartbeat_status,
        "recommended_review_lanes": recommended_review_lanes(
            task,
            baseline_changed_files,
        ),
        "required_review_lane_ids": (
            list(MATERIAL_LEARNING_LANE_IDS)
            if _is_material_work(task, baseline_changed_files)
            else []
        ),
    }
    payload["context_pack"] = compile_context_pack(
        hub_root,
        target_repo,
        session_id=sid,
        task=task,
        mail_digest_status=digest_status,
        deferred_mail=deferred_mail,
    )
    payload["context_pack"]["daemon_status"] = {
        "status": heartbeat_status.get("status", ""),
        "stale": bool(heartbeat_status.get("stale")),
        "heartbeat_path": heartbeat_status.get("heartbeat_path", ""),
        "cycle_completed_at": heartbeat_status.get("cycle_completed_at", ""),
        "stale_after_hours": heartbeat_status.get("stale_after_hours", ""),
    }
    if heartbeat_status.get("stale"):
        payload["context_pack"].setdefault("warnings", []).append(
            "daemon heartbeat is stale or unavailable"
        )
    hard_lookup = _maybe_hard_issue_lookup(
        hub_root,
        target_repo,
        task=task,
        paths=baseline_changed_files,
    )
    if hard_lookup is not None:
        payload["hard_issue_lookup"] = hard_lookup
        payload["context_pack"]["hard_issue_lookup"] = {
            "match_count": hard_lookup.get("match_count", 0),
            "returned_count": hard_lookup.get("returned_count", 0),
            "lookup_basis": hard_lookup.get("lookup_basis", ""),
            "matches": [
                {
                    "event_id": item.get("event_id", ""),
                    "event_type": item.get("event_type", ""),
                    "lookup_review_status": item.get("lookup_review_status", ""),
                    "public_release_gate": item.get("public_release_gate", ""),
                    "match_basis": item.get("match_basis", {}),
                }
                for item in list(hard_lookup.get("matches") or [])[:3]
                if isinstance(item, dict)
            ],
            "warnings": list(hard_lookup.get("warnings") or [])[:5],
            "authority_boundary": hard_lookup.get("authority_boundary", ""),
        }
        if hard_lookup.get("match_count"):
            payload["context_pack"].setdefault("warnings", []).append(
                "hard issue lookup found prior exception/fix evidence; review before improvising"
            )
    write_json(agent_sessions_dir(hub_root) / f"{sid.split(':')[-1]}.json", payload)
    append_jsonl(
        audit_events_dir(hub_root) / f"{payload['created_at'][:10]}.jsonl",
        {"event_type": "agent_preflight", **payload},
    )
    return payload


def midflight(
    hub_root: Path,
    sid: str,
    *,
    context: list[str] | None = None,
    paths: list[str] | None = None,
    ack_rules: list[str] | None = None,
) -> dict[str, Any]:
    session_path, session = load_session(hub_root, sid)
    path_values = [
        *session.get("baseline_changed_files", []),
        *(paths or []),
    ]
    matches = match_learning_rules(
        hub_root,
        task=str(session.get("task", "")),
        context=context or [],
        paths=path_values,
    )
    required = required_learning_rule_ids(matches)
    acknowledged = sorted(set(session.get("learning_rule_acknowledgements", [])) | set(ack_rules or []))
    missing = sorted(set(required) - set(acknowledged))
    created = utc_now()
    result = {
        "schema_version": "0.1.0",
        "session_id": sid,
        "created_at": created,
        "status": "blocked_missing_learning_rule_ack" if missing else "ok",
        "matched_rules": matches,
        "required_learning_rule_acknowledgements": required,
        "learning_rule_acknowledgements": acknowledged,
        "missing_learning_rule_acknowledgements": missing,
        "recommended_review_lanes": recommended_review_lanes(
            str(session.get("task", "")),
            path_values,
        ),
    }
    hard_lookup = _maybe_hard_issue_lookup(
        hub_root,
        Path(session["repository"]),
        task=str(session.get("task", "")),
        context=context or [],
        paths=path_values,
    )
    if hard_lookup is not None:
        result["hard_issue_lookup"] = hard_lookup
    session["learning_rule_matches"] = matches
    session["required_learning_rule_acknowledgements"] = required
    session["learning_rule_acknowledgements"] = acknowledged
    session.setdefault("midflight_checks", []).append(result)
    write_json(session_path, session)
    append_jsonl(
        audit_events_dir(hub_root) / f"{created[:10]}.jsonl",
        {"event_type": "agent_midflight", **result},
    )
    return result


def load_session(hub_root: Path, sid: str) -> tuple[Path, dict[str, Any]]:
    path = agent_sessions_dir(hub_root) / f"{sid.split(':')[-1]}.json"
    if not path.exists():
        raise FileNotFoundError(f"Agent session not found: {sid}")
    return path, json.loads(path.read_text(encoding="utf-8"))


def postflight(
    hub_root: Path, database_path: Path, sid: str, summary: str, **kwargs: Any
) -> tuple[HandoffRecord, LessonRecord]:
    session_path, session = load_session(hub_root, sid)
    repository = Path(session["repository"])
    changed = split_multi(kwargs.get("files_changed")) or git_changed_files(repository)
    created = utc_now()
    review_lanes = parse_review_lane_records(kwargs.get("review_lanes"))
    required_lane_ids = set(session.get("required_review_lane_ids") or [])
    incomplete_required_lanes = sorted(
        lane.lane_id
        for lane in review_lanes
        if lane.lane_id in required_lane_ids
        and lane.status not in {"subagent", "checklist"}
    )
    if incomplete_required_lanes:
        raise ValueError(
            "material postflight requires completed learning review lanes: "
            + ", ".join(incomplete_required_lanes)
        )
    handoff = HandoffRecord(
        handoff_id=stable_id("handoff", sid, created),
        session_id=sid,
        created_at=created,
        repository=str(repository),
        agent=session.get("agent", "unknown"),
        task=session.get("task", ""),
        summary=summary,
        files_changed=changed,
        commands_run=split_multi(kwargs.get("commands_run")),
        tests_run=split_multi(kwargs.get("tests_run")),
        tests_not_run=split_multi(kwargs.get("tests_not_run")),
        confirmed=split_multi(kwargs.get("confirmed")),
        inferred=split_multi(kwargs.get("inferred")),
        assumptions=split_multi(kwargs.get("assumptions")),
        unknowns=split_multi(kwargs.get("unknowns")),
        lessons=split_multi(kwargs.get("lessons")),
        risks=split_multi(kwargs.get("risks")),
        next_actions=split_multi(kwargs.get("next_actions")),
        review_lanes=review_lanes,
        review_status=kwargs.get("review_status", "candidate"),
    )
    trace_outcomes = record_trace_outcomes(
        hub_root,
        trace_id=str(kwargs.get("trace") or session.get("context_pack", {}).get("trace_id", "")),
        session_id=sid,
        outcomes={
            "used": split_multi(kwargs.get("used")),
            "ignored": split_multi(kwargs.get("ignored")),
            "attempted_failed": split_multi(kwargs.get("attempted_failed")),
            "harmful": split_multi(kwargs.get("harmful")),
        },
        summary=summary,
    )
    dated = created[:10]
    write_json(
        raw_handoffs_dir(hub_root) / dated / f"{handoff.handoff_id.split(':')[-1]}.json",
        handoff.model_dump(mode="json"),
    )
    with CatalogDB(database_path) as db:
        db.add_handoff(handoff)
    lesson = add_lesson(
        hub_root,
        database_path,
        repository=str(repository),
        task=session.get("task", ""),
        agent=session.get("agent", "unknown"),
        model=session.get("model"),
        summary=summary,
        lessons=kwargs.get("lessons") or [summary],
        files_changed=changed,
        tests_run=kwargs.get("tests_run"),
        tests_not_run=kwargs.get("tests_not_run"),
        discoveries=kwargs.get("discoveries"),
        failures=kwargs.get("failures"),
        reusable_patterns=kwargs.get("reusable_patterns"),
        missing_capabilities=kwargs.get("missing_capabilities"),
        evidence=kwargs.get("evidence"),
        confidence=kwargs.get("confidence", "medium"),
        session_id=sid,
    )
    session.update(
        {
            "status": "closed",
            "closed_at": created,
            "handoff_id": handoff.handoff_id,
            "lesson_id": lesson.lesson_id,
            "trace_outcomes": trace_outcomes,
        }
    )
    write_json(session_path, session)
    append_jsonl(
        audit_events_dir(hub_root) / f"{dated}.jsonl",
        {
            "event_type": "agent_postflight",
            "created_at": created,
            "session_id": sid,
            "handoff_id": handoff.handoff_id,
            "lesson_id": lesson.lesson_id,
        },
    )
    return handoff, lesson


def open_sessions(hub_root: Path, repository: Path | None = None) -> list[dict[str, Any]]:
    sessions = []
    for path in agent_sessions_dir(hub_root).glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("status") != "open":
            continue
        if repository and Path(payload.get("repository", "")).resolve() != repository.resolve():
            continue
        sessions.append(payload)
    return sessions
