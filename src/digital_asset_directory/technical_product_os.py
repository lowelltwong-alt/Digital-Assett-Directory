from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable
from uuid import uuid4

from jsonschema.validators import validator_for
import yaml

from .mail_center import append_jsonl_locked
from .transport import data_path
from .utils import atomic_write_text, json_dumps


REGISTRY_PATH = Path("registry/technical-product-company-os-registry.json")
REGISTRY_SCHEMA = Path("schemas/technical-product-company-os-registry.schema.json")
ROUTE_SCHEMA = Path("schemas/capability-routing-receipt.schema.json")
RUN_SCHEMA = Path("schemas/workflow-run-event.schema.json")
SNAPSHOT_SCHEMA = Path("schemas/capability-portfolio-snapshot.schema.json")
GRAPH_SCHEMA = Path("schemas/capability-operational-graph.schema.json")
SPECIALIST_PACK_PATHS = {
    "pack:mcp-integration-specialist-pack": Path("assets/agent-skills/mcp-integration-specialist-pack/subagents.yaml"),
    "pack:ui-ux-specialist-pack": Path("assets/agent-skills/ui-ux-specialist-pack/subagents.yaml"),
}
ROUTE_LEDGER_NAME = "capability-routing-receipts.jsonl"
RUN_LEDGER_NAME = "workflow-run-events.jsonl"
AUTHORITY_BOUNDARY = (
    "Capability OS outputs are candidate, read-only coordination evidence. Source repositories "
    "retain local meaning and Lowell retains product, automation, external-adapter, privacy, "
    "security, budget, release, and exception authority."
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_PATH_RE = re.compile(r"(?:^[A-Za-z]:[\\/]|(?:^|\s)/(?:Users|home|var|etc|tmp)/)")
_SECRET_RE = re.compile(
    r"(?:sk-(?:proj-)?[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"AKIA[A-Z0-9]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"(?:password|api[_-]?key|access[_-]?token|secret)\s*[:=]\s*\S+|"
    r"bearer\s+[A-Za-z0-9._~+/=-]{16,})",
    re.IGNORECASE,
)
_SUPPORTED_VALIDATION_OUTCOMES = {
    "supported_success",
    "supported_partial",
    "supported_failure",
    "unknown",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object in {path}")
    return value


def _validate(value: dict[str, Any], schema_path: Path) -> None:
    schema = _load_json(schema_path)
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    errors = sorted(
        validator_cls(schema).iter_errors(value), key=lambda item: list(item.path)
    )
    if errors:
        details = []
        for error in errors[:12]:
            location = ".".join(str(part) for part in error.path) or "<root>"
            details.append(f"{location}: {error.message}")
        raise ValueError(f"Invalid {schema_path.name}: {'; '.join(details)}")


def _tokens(value: str) -> set[str]:
    return set(_TOKEN_RE.findall(value.casefold()))


def _contains_phrase(value: str, phrase: str) -> bool:
    value_normalized = " ".join(_TOKEN_RE.findall(value.casefold()))
    phrase_normalized = " ".join(_TOKEN_RE.findall(phrase.casefold()))
    return bool(phrase_normalized) and f" {phrase_normalized} " in f" {value_normalized} "


def _clauses(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[.;!?\n]+", value.casefold()) if part.strip()]


def _negated_match(value: str, phrase: str) -> bool:
    negative_markers = ("do not", "don't", "avoid", "without", "not a request", "no ")
    return any(
        _contains_phrase(clause, phrase) and any(marker in clause for marker in negative_markers)
        for clause in _clauses(value)
    )


def _workflow_intent_suppressed(value: str, trigger: str) -> bool:
    counter_signals = (
        "do not",
        "don't",
        "avoid",
        "not a request",
        "only discuss",
        "discuss only",
        "compare only",
        "quoted",
    )
    return any(
        _contains_phrase(clause, trigger) and any(signal in clause for signal in counter_signals)
        for clause in _clauses(value)
    )


def _incidental_capability_context(query: str, capability_id: str) -> bool:
    normalized = " ".join(_TOKEN_RE.findall(query.casefold()))
    if capability_id == "capability:integration-api-mcp-automation":
        integration_intent = any(
            _contains_phrase(normalized, term)
            for term in (
                "integrate", "integration", "connect", "connector", "configure",
                "expose", "design mcp", "build mcp", "create mcp", "migrate",
                "oauth", "webhook", "queue", "mcp resource", "mcp prompt", "mcp tool",
            )
        )
        incidental = any(
            _contains_phrase(normalized, term)
            for term in (
                "uses mcp", "mcp dependency", "mcp dependencies",
                "fix one test in an mcp server", "fix test in mcp server",
                "mcp server test", "mcp files",
            )
        )
        return incidental and not integration_intent
    if capability_id == "capability:product-ux-accessibility":
        ui_intent = any(
            _contains_phrase(normalized, term)
            for term in (
                "design", "redesign", "user journey", "information architecture",
                "accessibility", "usability", "keyboard focus", "screen reader",
                "interaction", "dashboard", "cockpit",
            )
        )
        incidental = any(
            _contains_phrase(normalized, term)
            for term in ("ui files", "frontend files", "uses a design system")
        )
        return incidental and not ui_intent
    return False


def select_specialist_roles(
    repo_root: Path,
    pack_id: str,
    query: str,
    *,
    activation_evidence: Iterable[str] = (),
    maximum_primary: int = 3,
) -> dict[str, Any]:
    """Select a bounded expert subset after family routing and evidence gating."""
    relative_path = SPECIALIST_PACK_PATHS.get(pack_id)
    if relative_path is None:
        raise ValueError(f"Unknown specialist pack: {pack_id}")
    pack = yaml.safe_load((repo_root / relative_path).read_text(encoding="utf-8"))
    if not isinstance(pack, dict) or not isinstance(pack.get("roles"), list):
        raise ValueError(f"Invalid specialist pack: {pack_id}")
    policy_limit = int(pack.get("routing_policy", {}).get("maximum_primary_roles", 3))
    limit = max(1, min(3, policy_limit, maximum_primary))
    evidence = sorted({str(item) for item in activation_evidence if str(item).strip()})
    considered: list[dict[str, Any]] = []
    scored: list[tuple[int, str]] = []
    for role in pack["roles"]:
        matched: list[str] = []
        negated: list[str] = []
        score = 0
        for term in role["search_terms"]:
            if _negated_match(query, term):
                negated.append(term)
                continue
            exact, lexical, overlap = _strong_term_match(query, term)
            if exact or lexical:
                matched.append(term)
                score += (8 if exact else 0) + overlap
        reasons: list[str] = []
        if not evidence:
            reasons.append("activation_evidence_required")
        if negated:
            reasons.append("negative_intent_suppressed")
        if not matched:
            reasons.append("no_role_method_match")
        eligible = bool(evidence) and not negated and bool(matched)
        if eligible:
            scored.append((score, role["role_id"]))
        considered.append(
            {
                "role_id": role["role_id"],
                "eligible": eligible,
                "matched_terms": sorted(set(matched)),
                "reason_codes": reasons or ["method_match_with_activation_evidence"],
            }
        )
    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = [role_id for _, role_id in scored[:limit]]
    selected_set = set(selected)
    for row in considered:
        if row["eligible"] and row["role_id"] not in selected_set:
            row["reason_codes"] = ["eligible_not_selected_due_to_smallest_set_limit"]
    return {
        "schema_version": "dad.specialist_role_route.v1",
        "status": "generated_candidate" if evidence else "blocked_candidate",
        "candidate_only": True,
        "execution_authorized": False,
        "pack_id": pack_id,
        "pack_revision": str(pack["version"]),
        "activation_evidence": evidence,
        "maximum_primary_roles": limit,
        "whole_pack_activation": False,
        "selected_role_ids": selected,
        "considered": considered,
        "rejection_reason_codes": [] if selected else (["activation_evidence_required"] if not evidence else ["no_role_method_match"]),
        "authority_boundary": str(pack["authority_boundary"]),
    }


def _strong_term_match(query: str, term: str) -> tuple[bool, bool, int]:
    exact = _contains_phrase(query, term)
    term_tokens = _tokens(term)
    overlap = len(term_tokens & _tokens(query))
    strong_lexical = bool(term_tokens) and (
        (len(term_tokens) == 1 and overlap == 1)
        or (len(term_tokens) > 1 and overlap >= 2 and overlap / len(term_tokens) >= 0.5)
    )
    return exact, strong_lexical, overlap


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"Expected object at {path}:{line_number}")
        rows.append(value)
    return rows


def _path_fingerprint(path: Path) -> str:
    if not path.exists():
        return _canonical_hash({"state": "missing"})
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _assert_privacy_safe(value: Any, *, path: str = "<root>") -> None:
    forbidden_keys = {
        "raw_prompt",
        "prompt",
        "prompt_hash",
        "conversation",
        "source_row",
        "client_payload",
        "secret",
        "credential",
        "model_id",
        "provider_id",
        "absolute_path",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            if key.casefold() in forbidden_keys:
                raise ValueError(f"Privacy-unsafe telemetry field: {path}.{key}")
            _assert_privacy_safe(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_privacy_safe(child, path=f"{path}[{index}]")
    elif isinstance(value, str):
        if _PATH_RE.search(value):
            raise ValueError(f"Absolute or sensitive path-like value is not allowed at {path}")
        if _SECRET_RE.search(value):
            raise ValueError(f"Secret-looking telemetry value is not allowed at {path}")


def load_technical_product_registry(repo_root: Path) -> dict[str, Any]:
    registry = _load_json(repo_root / REGISTRY_PATH)
    _validate(registry, repo_root / REGISTRY_SCHEMA)
    ranks = [int(row["coverage_rank"]) for row in registry["capabilities"]]
    if ranks != list(range(1, 11)):
        raise ValueError("Technical product capability ranks must be exactly 1 through 10")
    capability_ids = {str(row["capability_id"]) for row in registry["capabilities"]}
    if len(capability_ids) != 10:
        raise ValueError("Technical product capability IDs must be unique")
    for row in registry["capabilities"]:
        missing = set(row["depends_on"]) - capability_ids
        if missing:
            raise ValueError(f"Unresolved capability dependencies: {sorted(missing)}")
    workflow_ids: set[str] = set()
    revisions: set[str] = set()
    for workflow in registry["workflows"]:
        workflow_id = str(workflow["workflow_id"])
        revision_id = str(workflow["revision_id"])
        if workflow_id in workflow_ids or revision_id in revisions:
            raise ValueError("Workflow and workflow revision IDs must be unique")
        workflow_ids.add(workflow_id)
        revisions.add(revision_id)
        missing = set(workflow["capability_sequence"]) - capability_ids
        if missing:
            raise ValueError(f"Workflow references unknown capabilities: {sorted(missing)}")
    return registry


def _source_files(repo_root: Path) -> list[Path]:
    candidates = [
        REGISTRY_PATH,
        Path("registry/agent-family-portfolio-registry.json"),
        Path("registry/agent-skill-library.json"),
        Path("registry/subagent-capability-registry.json"),
        Path("registry/workflow-part-type-registry.json"),
        Path("registry/control-plane-registry.json"),
        Path("registry/source-of-truth.json"),
        Path("registry/design-authority.json"),
    ]
    return [path for path in candidates if (repo_root / path).exists()]


def build_capability_index(repo_root: Path) -> dict[str, Any]:
    registry = load_technical_product_registry(repo_root)
    portfolio = _load_json(repo_root / "registry" / "agent-family-portfolio-registry.json")
    skills = _load_json(repo_root / "registry" / "agent-skill-library.json")
    implementation_states = {
        str(row["family_id"]): str(row.get("lifecycle_state", "unknown"))
        for row in portfolio.get("families", [])
    }
    implementation_states.update(
        {
            str(row["skill_id"]): str(row.get("status", "unknown"))
            for row in skills.get("skills", [])
        }
    )
    source_fingerprints = {
        path.as_posix(): f"sha256:{hashlib.sha256((repo_root / path).read_bytes()).hexdigest()}"
        for path in _source_files(repo_root)
    }
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for row in registry["capabilities"]:
        nodes.append(
            {
                "node_id": row["capability_id"],
                "node_type": "capability",
                "name": row["name"],
                "coverage_rank": row["coverage_rank"],
                "authority_ref": REGISTRY_PATH.as_posix(),
                "review_status": registry["status"],
            }
        )
        for implementation in row["implementation_refs"]:
            nodes.append(
                {
                    "node_id": implementation,
                    "node_type": "implementation",
                    "name": implementation.split(":", 1)[-1],
                    "authority_ref": REGISTRY_PATH.as_posix(),
                    "review_status": implementation_states.get(implementation, registry["status"]),
                }
            )
            edges.append(
                {
                    "source": implementation,
                    "edge_type": "implements",
                    "target": row["capability_id"],
                    "review_status": "candidate",
                    "evidence_ref": REGISTRY_PATH.as_posix(),
                }
            )
        for dependency in row["depends_on"]:
            edges.append(
                {
                    "source": row["capability_id"],
                    "edge_type": "depends_on",
                    "target": dependency,
                    "review_status": "candidate",
                    "evidence_ref": REGISTRY_PATH.as_posix(),
                }
            )
        for validator in row["validated_by"]:
            edges.append(
                {
                    "source": row["capability_id"],
                    "edge_type": "validated_by",
                    "target": validator,
                    "review_status": "candidate",
                    "evidence_ref": REGISTRY_PATH.as_posix(),
                }
            )
    for workflow in registry["workflows"]:
        nodes.extend(
            [
                {
                    "node_id": workflow["workflow_id"],
                    "node_type": "workflow_definition",
                    "name": workflow["workflow_id"].split(":", 1)[-1],
                    "authority_ref": REGISTRY_PATH.as_posix(),
                    "review_status": workflow["status"],
                },
                {
                    "node_id": workflow["revision_id"],
                    "node_type": "workflow_revision",
                    "name": workflow["revision_id"],
                    "authority_ref": REGISTRY_PATH.as_posix(),
                    "review_status": workflow["status"],
                },
            ]
        )
        edges.append(
            {
                "source": workflow["revision_id"],
                "edge_type": "derived_from",
                "target": workflow["workflow_id"],
                "review_status": "candidate",
                "evidence_ref": REGISTRY_PATH.as_posix(),
            }
        )
        for capability_id in workflow["capability_sequence"]:
            edges.append(
                {
                    "source": workflow["revision_id"],
                    "edge_type": "depends_on",
                    "target": capability_id,
                    "review_status": "candidate",
                    "evidence_ref": REGISTRY_PATH.as_posix(),
                }
            )
    unique_nodes = {row["node_id"]: row for row in nodes}
    for edge in edges:
        for endpoint in (edge["source"], edge["target"]):
            node_type = (
                "family"
                if endpoint.startswith("family:")
                else "specialist_pack"
                if endpoint.startswith("pack:")
                else "skill"
                if endpoint.startswith("skill:")
                else "validator"
                if endpoint.startswith("role:")
                else "adapter"
                if endpoint.startswith("adapter:")
                else "implementation"
            )
            unique_nodes.setdefault(
                endpoint,
                {
                    "node_id": endpoint,
                    "node_type": node_type,
                    "name": endpoint.split(":", 1)[-1],
                    "authority_ref": REGISTRY_PATH.as_posix(),
                    "review_status": registry["status"],
                },
            )
    sorted_nodes = sorted(unique_nodes.values(), key=lambda row: row["node_id"])
    sorted_edges = sorted(
        edges, key=lambda row: (row["source"], row["edge_type"], row["target"])
    )
    catalog_fingerprint = _canonical_hash(
        {"source_fingerprints": source_fingerprints, "nodes": sorted_nodes, "edges": sorted_edges}
    )
    return {
        "schema_version": "dad.capability_index.v1",
        "status": "generated_candidate",
        "candidate_only": True,
        "execution_authorized": False,
        "catalog_fingerprint": catalog_fingerprint,
        "source_fingerprints": source_fingerprints,
        "nodes": sorted_nodes,
        "edges": sorted_edges,
        "summary": {"node_count": len(sorted_nodes), "edge_count": len(sorted_edges)},
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def evaluate_decision_right(
    repo_root: Path,
    *,
    requested_right: str,
    consequence_tier: str,
    privacy_class: str,
    actor_class: str = "",
    verified_gates: Iterable[str] = (),
    actor_id: str = "",
    producer_id: str = "",
    checker_id: str = "",
    action_digest: str = "",
    lease_ref: str = "",
    lease_expires_at: str = "",
    human_approval_ref: str = "",
    checker_evaluation_ref: str = "",
    human_gate_verified: bool = False,
    checker_gate_verified: bool = False,
    domain_gate_verified: bool = False,
    lease_verified: bool = False,
    final_confirmation_verified: bool = False,
    rollback_present: bool = False,
) -> dict[str, Any]:
    registry = load_technical_product_registry(repo_root)
    right = next(
        (row for row in registry["decision_rights"] if row["right_id"] == requested_right),
        None,
    )
    tier = next(
        (row for row in registry["consequence_tiers"] if row["tier"] == consequence_tier),
        None,
    )
    reasons: list[str] = []
    gates = {str(gate) for gate in verified_gates}
    if human_gate_verified:
        gates.add("human_gate")
    if checker_gate_verified:
        gates.add("checker_gate")
    if domain_gate_verified:
        gates.add("domain_gate")
    if lease_verified:
        gates.add("verified_unexpired_lease")
    if final_confirmation_verified:
        gates.add("final_confirmation")
    if rollback_present:
        gates.add("rollback")
    if right is None:
        reasons.append("unknown_decision_right")
    if tier is None:
        reasons.append("unknown_consequence_tier")
    if privacy_class == "unknown" and requested_right in {"retrieve", "draft", "execute"}:
        reasons.append("unknown_privacy_class")
    if requested_right == "prohibited" or consequence_tier == "C4":
        reasons.append("prohibited_action")
    if right is not None:
        if actor_class not in right["allowed_actor_classes"]:
            reasons.append("actor_class_not_allowed")
        if consequence_tier not in right["allowed_consequence_tiers"]:
            reasons.append("decision_right_tier_mismatch")
        for gate in right["required_gates"]:
            if gate not in gates:
                reasons.append(f"required_gate_missing_{gate}")
    if requested_right in {"draft", "validate", "execute"} and not actor_id:
        reasons.append("actor_identity_missing")
    if requested_right == "validate":
        if not producer_id or not checker_id:
            reasons.append("producer_checker_identity_missing")
        elif producer_id == checker_id or checker_id != actor_id:
            reasons.append("producer_checker_separation_failed")
    if requested_right == "execute":
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", action_digest):
            reasons.append("action_digest_missing_or_invalid")
        if not lease_ref:
            reasons.append("lease_reference_missing")
        if not human_approval_ref:
            reasons.append("human_approval_reference_missing")
        if not checker_evaluation_ref:
            reasons.append("checker_evaluation_reference_missing")
        try:
            expiry = datetime.fromisoformat(lease_expires_at.replace("Z", "+00:00"))
            if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
                reasons.append("lease_expired_or_timezone_missing")
        except (TypeError, ValueError):
            reasons.append("lease_expiry_missing_or_invalid")
        reasons.append("trusted_execution_verifier_unavailable")
    if tier:
        if tier["human_gate"] and not human_gate_verified:
            reasons.append("human_gate_missing")
        if tier["checker_gate"] and not checker_gate_verified:
            reasons.append("checker_gate_missing")
        if tier["lease_required"] and not lease_verified:
            reasons.append("lease_missing")
        if tier["final_confirmation_required"] and not final_confirmation_verified:
            reasons.append("final_confirmation_missing")
        if tier["rollback_required"] and not rollback_present:
            reasons.append("rollback_missing")
    if requested_right == "execute" and not domain_gate_verified and consequence_tier in {"C2", "C3"}:
        reasons.append("domain_gate_missing")
    allowed = not reasons
    policy_eligible = not (
        set(reasons) - {"trusted_execution_verifier_unavailable"}
    )
    return {
        "requested_right": requested_right,
        "consequence_tier": consequence_tier,
        "privacy_class": privacy_class,
        "actor_class": actor_class,
        "actor_id": actor_id,
        "verified_gates": sorted(gates),
        "allowed": allowed,
        "policy_eligible": policy_eligible,
        "reason_codes": sorted(set(reasons)) or ["all_required_gates_verified"],
        "execution_authorized": allowed and requested_right == "execute",
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def route_capabilities(
    repo_root: Path,
    query: str,
    *,
    requested_right: str = "recommend",
    consequence_tier: str = "C0",
    privacy_class: str = "internal_metadata",
    semantic_scores: dict[str, float] | None = None,
    maximum_primary: int = 3,
    permission_granted: bool = True,
    environment_eligible_capability_ids: Iterable[str] | None = None,
    tool_eligible_capability_ids: Iterable[str] | None = None,
    suppressed_capability_ids: Iterable[str] = (),
    lifecycle_states: dict[str, str] | None = None,
) -> dict[str, Any]:
    registry = load_technical_product_registry(repo_root)
    index = build_capability_index(repo_root)
    maximum_primary = max(1, min(3, maximum_primary))
    query_tokens = _tokens(query)
    normalized_query = " ".join(sorted(query_tokens))
    hard_block = (
        requested_right == "prohibited"
        or consequence_tier == "C4"
        or not permission_granted
    )
    if privacy_class == "unknown" and requested_right in {"retrieve", "draft", "execute"}:
        hard_block = True
    if requested_right == "execute":
        hard_block = True
    scored: list[tuple[float, int, dict[str, Any], list[str], list[str]]] = []
    considered: list[dict[str, Any]] = []
    semantic_scores = semantic_scores or {}
    environment_eligible = (
        set(environment_eligible_capability_ids)
        if environment_eligible_capability_ids is not None
        else None
    )
    tool_eligible = (
        set(tool_eligible_capability_ids)
        if tool_eligible_capability_ids is not None
        else None
    )
    suppressed = set(suppressed_capability_ids)
    lifecycle_states = lifecycle_states or {}
    for row in registry["capabilities"]:
        lexical = 0
        exact = 0
        matched_terms: list[str] = []
        channels: list[str] = []
        negated_terms: list[str] = []
        for term in row["trigger_terms"]:
            exact_match, strong_lexical, overlap = _strong_term_match(query, term)
            if _negated_match(query, term):
                negated_terms.append(term)
                continue
            if strong_lexical:
                lexical += overlap
                matched_terms.append(term)
            if exact_match:
                exact += 1
        if exact:
            channels.append("exact")
        if lexical:
            channels.append("lexical")
        semantic = max(0.0, float(semantic_scores.get(row["capability_id"], 0.0)))
        if semantic:
            channels.append("semantic")
        score = exact * 8.0 + lexical * 2.0 + semantic
        lifecycle_state = lifecycle_states.get(row["capability_id"], registry["status"])
        incidental_context = _incidental_capability_context(query, row["capability_id"])
        eligible = (
            not hard_block
            and row["capability_id"] not in suppressed
            and not negated_terms
            and lifecycle_state not in {"stale", "superseded", "retired", "blocked"}
            and (environment_eligible is None or row["capability_id"] in environment_eligible)
            and (tool_eligible is None or row["capability_id"] in tool_eligible)
            and not incidental_context
        )
        reasons = []
        if hard_block:
            reasons.append("authority_or_privacy_gate_blocked")
        if not permission_granted:
            reasons.append("permission_gate_blocked")
        if row["capability_id"] in suppressed:
            reasons.append("explicitly_suppressed")
        if incidental_context:
            reasons.append("incidental_context_suppressed")
        if negated_terms:
            reasons.append("negative_intent_suppressed")
        if lifecycle_state in {"stale", "superseded", "retired", "blocked"}:
            reasons.append(f"lifecycle_{lifecycle_state}")
        if environment_eligible is not None and row["capability_id"] not in environment_eligible:
            reasons.append("environment_ineligible")
        if tool_eligible is not None and row["capability_id"] not in tool_eligible:
            reasons.append("tool_ineligible")
        if score > 0:
            reasons.append("query_match")
        else:
            reasons.append("no_query_match")
        considered.append(
            {
                "capability_id": row["capability_id"],
                "eligible": eligible,
                "reason_codes": reasons,
                "retrieval_channels": channels,
                "matched_terms": sorted(set(matched_terms)),
                "negated_terms": sorted(set(negated_terms)),
                "lifecycle_state": lifecycle_state,
            }
        )
        if eligible and score > 0:
            scored.append((score, int(row["coverage_rank"]), row, channels, matched_terms))
    scored.sort(key=lambda item: (-item[0], item[1], item[2]["capability_id"]))
    selected = [item[2]["capability_id"] for item in scored[:maximum_primary]]
    by_id = {row["capability_id"]: row for row in registry["capabilities"]}
    supporting: set[str] = set()
    frontier = list(selected)
    while frontier:
        current = frontier.pop()
        for dependency in by_id[current]["depends_on"]:
            if dependency not in selected and dependency not in supporting:
                supporting.add(dependency)
                frontier.append(dependency)
    validators = sorted(
        {
            validator
            for capability_id in [*selected, *supporting]
            for validator in by_id[capability_id]["validated_by"]
        }
    )
    workflow_matches: list[dict[str, Any]] = []
    for workflow in registry["workflows"]:
        matched_triggers = [
            term
            for term in workflow["trigger_terms"]
            if _contains_phrase(query, term) and not _workflow_intent_suppressed(query, term)
        ]
        suppressed_triggers = [
            term
            for term in workflow["trigger_terms"]
            if _contains_phrase(query, term) and _workflow_intent_suppressed(query, term)
        ]
        if matched_triggers:
            workflow_matches.append(
                {
                    "workflow_id": workflow["workflow_id"],
                    "revision_id": workflow["revision_id"],
                    "score": sum(8 + len(_tokens(term)) for term in matched_triggers),
                    "reason_codes": ["positive_exact_workflow_intent"],
                    "matched_triggers": matched_triggers,
                }
            )
        elif suppressed_triggers:
            workflow_matches.append(
                {
                    "workflow_id": workflow["workflow_id"],
                    "revision_id": workflow["revision_id"],
                    "score": 0,
                    "reason_codes": ["negative_workflow_intent_suppressed"],
                    "matched_triggers": suppressed_triggers,
                    "suppressed": True,
                }
            )
    workflow_matches.sort(key=lambda row: (-row["score"], row["workflow_id"]))
    active_workflow_matches = [row for row in workflow_matches if not row.get("suppressed")]
    suppressed_workflow_matches = [row for row in workflow_matches if row.get("suppressed")]
    return {
        "schema_version": "dad.capability_route.v1",
        "router_revision": registry["retrieval_policy"]["router_revision"],
        "status": "blocked_candidate" if hard_block else "generated_candidate",
        "candidate_only": True,
        "execution_authorized": False,
        "query_fingerprint": _canonical_hash({"tokens": normalized_query}),
        "requested_right": requested_right,
        "consequence_tier": consequence_tier,
        "privacy_class": privacy_class,
        "considered": considered,
        "selected_capabilities": selected,
        "supporting_capabilities": sorted(supporting),
        "required_validators": validators,
        "workflow_matches": active_workflow_matches[:3],
        "suppressed_workflow_matches": suppressed_workflow_matches[:3],
        "rejection_reason_codes": (
            ["authority_or_privacy_gate_blocked"] if hard_block else ([] if selected else ["no_capability_match"])
        ),
        "retrieval_channels": ["authority_and_eligibility", "exact", "lexical", "optional_semantic", "dependency", "validator"],
        "semantic_status": "provided" if semantic_scores else "disabled_not_run",
        "catalog_fingerprint": index["catalog_fingerprint"],
        "capability_descriptor_revision": registry["registry_version"],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def build_routing_receipt(
    route: dict[str, Any],
    *,
    opaque_task_id: str,
    request_class: str,
    request_tags: Iterable[str],
    repository_id: str,
    synthetic_or_fixture: bool = False,
    event_type: str = "dad.capability.route.decided.v1",
    corrects_event_id: str = "",
    human_gate_status: str = "candidate_only",
    checker_gate_status: str = "candidate_only",
    domain_gate_status: str = "candidate_only",
    execution_lease_ref: str = "",
    independent_evaluation_ref: str = "",
    route_outcome: str = "accepted_candidate",
    override_reason_codes: Iterable[str] = (),
    now: datetime | None = None,
) -> dict[str, Any]:
    tags = sorted({str(tag) for tag in request_tags})
    semantic_fingerprint = _canonical_hash(
        {
            "opaque_task_id": opaque_task_id,
            "request_class": request_class,
            "request_tags": tags,
            "repository_id": repository_id,
            "route_revision": route["router_revision"],
            "catalog_fingerprint": route["catalog_fingerprint"],
            "capability_descriptor_revision": route["capability_descriptor_revision"],
            "selected_workflow_revisions": [
                row["revision_id"] for row in route.get("workflow_matches", [])
            ],
        }
    )
    route_id = uuid4().hex
    receipt: dict[str, Any] = {
        "specversion": "1.0",
        "id": f"route-event:{route_id}",
        "source": "dad://capability-os/router",
        "type": event_type,
        "subject": f"route:{route_id}",
        "time": (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        "dataschema": ROUTE_SCHEMA.as_posix(),
        "route_revision": route["router_revision"],
        "catalog_fingerprint": route["catalog_fingerprint"],
        "capability_descriptor_revision": route["capability_descriptor_revision"],
        "opaque_task_id": opaque_task_id,
        "request_class": request_class,
        "request_tags": tags,
        "requested_right": route["requested_right"],
        "consequence_tier": route["consequence_tier"],
        "privacy_class": route["privacy_class"],
        "repository_id": repository_id,
        "considered": [
            {
                "capability_id": row["capability_id"],
                "eligible": row["eligible"],
                "reason_codes": row["reason_codes"],
                "retrieval_channels": row["retrieval_channels"],
            }
            for row in route["considered"]
        ],
        "selected_capabilities": route["selected_capabilities"],
        "supporting_capabilities": route["supporting_capabilities"],
        "required_validators": route["required_validators"],
        "selected_workflow_revisions": [
            row["revision_id"] for row in route.get("workflow_matches", [])
        ],
        "rejection_reason_codes": route["rejection_reason_codes"],
        "route_outcome": route_outcome,
        "override_reason_codes": sorted(set(override_reason_codes)),
        "human_gate_status": human_gate_status,
        "checker_gate_status": checker_gate_status,
        "domain_gate_status": domain_gate_status,
        "synthetic_or_fixture": synthetic_or_fixture,
        "semantic_task_fingerprint": semantic_fingerprint,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    if execution_lease_ref:
        receipt["execution_lease_ref"] = execution_lease_ref
    if independent_evaluation_ref:
        receipt["independent_evaluation_ref"] = independent_evaluation_ref
    if corrects_event_id:
        receipt["corrects_event_id"] = corrects_event_id
    return receipt


def _route_ledger(repo_root: Path) -> Path:
    return data_path(repo_root, "usage") / ROUTE_LEDGER_NAME


def _run_ledger(repo_root: Path) -> Path:
    return data_path(repo_root, "usage") / RUN_LEDGER_NAME


def _event_datetime(value: Any) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Correction events require valid ISO timestamps") from exc
    if parsed.tzinfo is None:
        raise ValueError("Correction events require timezone-aware timestamps")
    return parsed.astimezone(timezone.utc)


def _validate_correction_reference(
    event: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    correction_type: str,
    scope_fields: Iterable[str],
) -> None:
    target_id = str(event.get("corrects_event_id", ""))
    is_correction = event.get("type") == correction_type
    if is_correction != bool(target_id):
        raise ValueError("Correction event type and corrects_event_id must be supplied together")
    if not is_correction:
        return
    if target_id == event.get("id"):
        raise ValueError("Correction event cannot correct itself")
    effective = {str(row.get("id", "")): row for row in _effective_events(rows)}
    target = effective.get(target_id)
    if target is None:
        raise ValueError("Correction target must exist and remain effective")
    for field in scope_fields:
        if event.get(field) != target.get(field):
            raise ValueError(f"Correction target scope mismatch: {field}")
    if _event_datetime(event.get("time")) <= _event_datetime(target.get("time")):
        raise ValueError("Correction event must be newer than its target")


def append_routing_receipt(repo_root: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    _assert_privacy_safe(receipt)
    _validate(receipt, repo_root / ROUTE_SCHEMA)
    path = _route_ledger(repo_root)
    rows = _read_jsonl(path)
    route_type = str(receipt.get("type", ""))
    if route_type == "dad.capability.route.overridden.v1":
        if receipt.get("route_outcome") != "overridden" or not receipt.get(
            "override_reason_codes"
        ):
            raise ValueError("Overridden route events require outcome and reason evidence")
    if route_type == "dad.capability.route.corrected.v1" and not receipt.get(
        "override_reason_codes"
    ):
        raise ValueError("Corrected route events require correction reason evidence")
    if route_type == "dad.capability.route.decided.v1" and receipt.get(
        "corrects_event_id"
    ):
        raise ValueError("Decided route events cannot carry correction references")
    _validate_correction_reference(
        receipt,
        rows,
        correction_type=(
            "dad.capability.route.corrected.v1"
            if route_type != "dad.capability.route.overridden.v1"
            else "dad.capability.route.overridden.v1"
        ),
        scope_fields=("source", "opaque_task_id", "repository_id"),
    )
    identity = (receipt["source"], receipt["id"])
    if any((row.get("source"), row.get("id")) == identity for row in rows):
        return {"appended": False, "reason": "duplicate_event_identity", "path": str(path), "receipt": receipt}
    semantic_identity = (
        receipt["semantic_task_fingerprint"],
        receipt["route_revision"],
        receipt["catalog_fingerprint"],
        tuple(receipt["selected_capabilities"]),
        tuple(receipt["selected_workflow_revisions"]),
        receipt["type"],
    )
    if receipt["type"] == "dad.capability.route.decided.v1" and any(
        (
            row.get("semantic_task_fingerprint"),
            row.get("route_revision"),
            row.get("catalog_fingerprint"),
            tuple(row.get("selected_capabilities", [])),
            tuple(row.get("selected_workflow_revisions", [])),
            row.get("type"),
        )
        == semantic_identity
        for row in rows
    ):
        return {"appended": False, "reason": "duplicate_semantic_route_retry", "path": str(path), "receipt": receipt}
    append_jsonl_locked(path, receipt)
    return {"appended": True, "reason": "new_event", "path": str(path), "receipt": receipt}


def build_workflow_run_event(
    *,
    workflow_id: str,
    workflow_revision_id: str,
    run_id: str,
    route_event_id: str,
    event_state: str,
    capability_ids: Iterable[str],
    input_fingerprint: str,
    execution_mode: str,
    producer_ref: str,
    synthetic_or_fixture: bool = False,
    privacy_class: str = "internal_metadata",
    output_fingerprint: str = "",
    independent_checker_ref: str = "",
    independent_evaluation_ref: str = "",
    validation_outcome: str = "",
    result_reason_codes: Iterable[str] = (),
    token_status: str = "unknown",
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cache_read_tokens: int | None = None,
    cost_status: str = "unknown",
    cost_amount: float | None = None,
    cost_currency: str | None = None,
    duration_ms: int | None = None,
    model_call_count: int = 0,
    adapter_id: str = "",
    context_cache_hit: bool = False,
    context_capsule_ref: str = "",
    corrects_event_id: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    event_id = uuid4().hex
    type_by_state = {
        "started": "dad.workflow.run.started.v1",
        "running": "dad.workflow.run.running.v1",
        "completed": "dad.workflow.run.completed.v1",
        "failed": "dad.workflow.run.failed.v1",
        "aborted": "dad.workflow.run.aborted.v1",
        "independently_validated": "dad.workflow.run.validated.v1",
        "corrected": "dad.workflow.run.corrected.v1",
    }
    if event_state not in type_by_state:
        raise ValueError(f"Unsupported workflow event state: {event_state}")
    event: dict[str, Any] = {
        "specversion": "1.0",
        "id": f"run-event:{event_id}",
        "source": "dad://capability-os/workflow-runner",
        "type": type_by_state[event_state],
        "subject": f"workflow-run:{run_id}",
        "time": (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        "dataschema": RUN_SCHEMA.as_posix(),
        "workflow_id": workflow_id,
        "workflow_revision_id": workflow_revision_id,
        "run_id": run_id,
        "route_event_id": route_event_id,
        "event_state": event_state,
        "capability_ids": sorted(set(capability_ids)),
        "input_fingerprint": input_fingerprint,
        "execution_mode": execution_mode,
        "producer_ref": producer_ref,
        "synthetic_or_fixture": synthetic_or_fixture,
        "privacy_class": privacy_class,
        "token_usage": {"status": token_status, "input_tokens": input_tokens, "output_tokens": output_tokens, "cache_read_tokens": cache_read_tokens},
        "cost_usage": {"status": cost_status, "amount": cost_amount, "currency": cost_currency},
        "model_call_count": model_call_count,
        "context_cache_hit": context_cache_hit,
        "result_reason_codes": sorted(set(result_reason_codes)),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    optional = {
        "output_fingerprint": output_fingerprint,
        "independent_checker_ref": independent_checker_ref,
        "independent_evaluation_ref": independent_evaluation_ref,
        "validation_outcome": validation_outcome,
        "adapter_id": adapter_id,
        "context_capsule_ref": context_capsule_ref,
        "corrects_event_id": corrects_event_id,
    }
    for key, value in optional.items():
        if value:
            event[key] = value
    if duration_ms is not None:
        event["duration_ms"] = duration_ms
    return event


def append_workflow_run_event(repo_root: Path, event: dict[str, Any]) -> dict[str, Any]:
    _assert_privacy_safe(event)
    _validate(event, repo_root / RUN_SCHEMA)
    if event["execution_mode"] == "external_adapter" and not event.get("adapter_id"):
        raise ValueError("external_adapter execution requires adapter_id")
    routes = _effective_events(_read_jsonl(_route_ledger(repo_root)))
    route = next((row for row in routes if row.get("id") == event["route_event_id"]), None)
    if route is None:
        raise ValueError("Workflow run event requires an existing routing receipt")
    routed_capabilities = set(route.get("selected_capabilities", [])) | set(
        route.get("supporting_capabilities", [])
    )
    if not set(event["capability_ids"]) <= routed_capabilities:
        raise ValueError("Workflow run capabilities must be linked by the routing receipt")
    if event["workflow_revision_id"] not in set(route.get("selected_workflow_revisions", [])):
        raise ValueError("Workflow revision must be selected by the routing receipt")
    all_run_rows = _read_jsonl(_run_ledger(repo_root))
    _validate_correction_reference(
        event,
        all_run_rows,
        correction_type="dad.workflow.run.corrected.v1",
        scope_fields=(
            "source",
            "run_id",
            "route_event_id",
            "workflow_id",
            "workflow_revision_id",
        ),
    )
    prior_events = [
        row
        for row in _effective_events(all_run_rows)
        if row.get("run_id") == event["run_id"]
    ]
    prior_states = {str(row.get("event_state", "")) for row in prior_events}
    if event["event_state"] != "started" and event["event_state"] != "corrected" and "started" not in prior_states:
        raise ValueError("Workflow lifecycle event requires a prior started event")
    if event["event_state"] == "started" and "started" in prior_states:
        raise ValueError("Workflow run may have only one effective started event")
    if event["event_state"] == "independently_validated" and "completed" not in prior_states:
        raise ValueError("Independent validation requires a prior completed event")
    if event["event_state"] == "independently_validated":
        if not event.get("independent_checker_ref") or not event.get("independent_evaluation_ref"):
            raise ValueError("Independent validation requires checker and evaluation references")
        if event.get("validation_outcome") not in _SUPPORTED_VALIDATION_OUTCOMES:
            raise ValueError("Independent validation requires a supported validation outcome")
        if event.get("independent_checker_ref") == event.get("producer_ref") or event.get(
            "independent_checker_ref"
        ) in {"self", "producer:self"}:
            raise ValueError("Independent checker must be distinct from the producer")
    path = _run_ledger(repo_root)
    identity = (event["source"], event["id"])
    if any((row.get("source"), row.get("id")) == identity for row in all_run_rows):
        return {"appended": False, "reason": "duplicate_event_identity", "path": str(path), "event": event}
    append_jsonl_locked(path, event)
    return {"appended": True, "reason": "new_event", "path": str(path), "event": event}


def _effective_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_identity: dict[tuple[str, str], dict[str, Any]] = {}
    corrected: set[str] = set()
    for row in sorted(rows, key=lambda item: (str(item.get("time", "")), str(item.get("id", "")))):
        identity = (str(row.get("source", "")), str(row.get("id", "")))
        by_identity.setdefault(identity, row)
        if row.get("corrects_event_id"):
            corrected.add(str(row["corrects_event_id"]))
    return [row for (_, event_id), row in by_identity.items() if event_id not in corrected]


def _empty_usage(entity_id: str) -> dict[str, Any]:
    return {
        "entity_id": entity_id,
        "observation_status": "unobserved",
        "eligible_considered_count": 0,
        "selected_count": 0,
        "executed_count": 0,
        "completed_count": 0,
        "independently_validated_count": 0,
        "supported_success_count": 0,
        "supported_partial_count": 0,
        "supported_failure_count": 0,
        "supported_unknown_count": 0,
        "last_considered_at": None,
        "last_selected_at": None,
        "last_executed_at": None,
        "last_used_at": None,
        "last_independently_validated_at": None,
    }


def _latest(current: str | None, candidate: str) -> str:
    return max(current or "", candidate)


def _usage_projection(
    registry: dict[str, Any],
    route_rows: list[dict[str, Any]],
    run_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    capability_usage = {
        row["capability_id"]: _empty_usage(row["capability_id"])
        for row in registry["capabilities"]
    }
    workflow_usage = {
        row["revision_id"]: _empty_usage(row["revision_id"])
        for row in registry["workflows"]
    }
    operational_routes = [row for row in route_rows if not row.get("synthetic_or_fixture", False)]
    for route in operational_routes:
        time = str(route.get("time", ""))
        for considered in route.get("considered", []):
            entity_id = str(considered.get("capability_id", ""))
            materially_retrieved = "query_match" in {
                str(reason) for reason in considered.get("reason_codes", [])
            }
            if (
                entity_id in capability_usage
                and considered.get("eligible")
                and materially_retrieved
            ):
                usage = capability_usage[entity_id]
                usage["eligible_considered_count"] += 1
                usage["last_considered_at"] = _latest(usage["last_considered_at"], time)
        for entity_id in route.get("selected_capabilities", []):
            if entity_id in capability_usage:
                usage = capability_usage[entity_id]
                usage["selected_count"] += 1
                usage["last_selected_at"] = _latest(usage["last_selected_at"], time)
        for revision_id in route.get("selected_workflow_revisions", []):
            if revision_id in workflow_usage:
                usage = workflow_usage[revision_id]
                usage["selected_count"] += 1
                usage["last_selected_at"] = _latest(usage["last_selected_at"], time)
                usage["observation_status"] = "observed"
    runs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in run_rows:
        if not event.get("synthetic_or_fixture", False):
            runs[str(event.get("run_id", ""))].append(event)
    for events in runs.values():
        events.sort(key=lambda item: (str(item.get("time", "")), str(item.get("id", ""))))
        first = events[0]
        workflow_revision_id = str(first.get("workflow_revision_id", ""))
        capability_ids = sorted({str(capability) for event in events for capability in event.get("capability_ids", [])})
        states = {str(event.get("event_state", "")) for event in events}
        started_events = [event for event in events if event.get("event_state") == "started"]
        completed_events = [event for event in events if event.get("event_state") == "completed"]
        validation_events = [event for event in events if event.get("event_state") == "independently_validated" and event.get("independent_checker_ref") and event.get("independent_evaluation_ref") and event.get("validation_outcome") in _SUPPORTED_VALIDATION_OUTCOMES]
        targets = [capability_usage[entity_id] for entity_id in capability_ids if entity_id in capability_usage]
        if workflow_revision_id in workflow_usage:
            targets.append(workflow_usage[workflow_revision_id])
        for usage in targets:
            if started_events:
                usage["executed_count"] += 1
                usage["last_executed_at"] = _latest(usage["last_executed_at"], str(started_events[-1]["time"]))
                usage["last_used_at"] = _latest(usage["last_used_at"], str(started_events[-1]["time"]))
            if completed_events:
                usage["completed_count"] += 1
            if validation_events:
                usage["independently_validated_count"] += 1
                usage["last_independently_validated_at"] = _latest(usage["last_independently_validated_at"], str(validation_events[-1]["time"]))
                outcome = str(validation_events[-1]["validation_outcome"])
                usage[{"supported_success": "supported_success_count", "supported_partial": "supported_partial_count", "supported_failure": "supported_failure_count", "unknown": "supported_unknown_count"}[outcome]] += 1
            if usage["eligible_considered_count"] or usage["executed_count"] or states:
                usage["observation_status"] = "observed"
    for usage in capability_usage.values():
        if usage["eligible_considered_count"] or usage["selected_count"] or usage["executed_count"]:
            usage["observation_status"] = "observed"
    for usage in workflow_usage.values():
        if usage["selected_count"] or usage["executed_count"]:
            usage["observation_status"] = "observed"
    return (
        sorted(capability_usage.values(), key=lambda row: row["entity_id"]),
        sorted(workflow_usage.values(), key=lambda row: row["entity_id"]),
    )


def _gap_candidates(
    capabilities: list[dict[str, Any]],
    route_rows: list[dict[str, Any]],
    index: dict[str, Any],
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for usage in capabilities:
        gap_type = ""
        disposition = "observe_more"
        evidence: list[str] = []
        counterevidence: list[str] = []
        if usage["eligible_considered_count"] >= 3 and usage["selected_count"] == 0:
            gap_type = "repeated_eligible_not_selected"
            disposition = "route_existing"
            evidence = [f"eligible_considered:{usage['eligible_considered_count']}"]
        elif usage["selected_count"] >= 3 and usage["executed_count"] == 0:
            gap_type = "selected_not_executed"
            evidence = [f"selected:{usage['selected_count']}"]
            counterevidence = ["selection_does_not_prove_execution_need"]
        elif usage["executed_count"] >= 3 and usage["supported_failure_count"] >= 2:
            gap_type = "repeated_independently_supported_failure"
            disposition = "improve_candidate"
            evidence = [f"executed:{usage['executed_count']}", f"supported_failure:{usage['supported_failure_count']}"]
        if not gap_type:
            continue
        fingerprint = _canonical_hash(
            {"gap_type": gap_type, "affected": usage["entity_id"], "evidence": sorted(evidence), "rule_revision": "capability-gap:v1"}
        )
        gaps.append(
            {
                "gap_id": f"gap:{fingerprint.split(':', 1)[1][:20]}",
                "fingerprint": fingerprint,
                "gap_type": gap_type,
                "disposition": disposition,
                "affected_ids": [usage["entity_id"]],
                "evidence_refs": evidence,
                "counterevidence_refs": counterevidence,
                "next_review": "after_material_route_or_execution_evidence_delta",
                "human_decision_required": disposition in {"improve_candidate", "new_candidate"},
            }
        )
    feedback: dict[tuple[str, str], list[str]] = defaultdict(list)
    for route in route_rows:
        if route.get("synthetic_or_fixture", False):
            continue
        outcome = str(route.get("route_outcome", "unknown"))
        reasons = {str(reason) for reason in route.get("override_reason_codes", [])}
        selected = [str(item) for item in route.get("selected_capabilities", [])]
        if outcome == "overridden":
            for capability_id in selected:
                feedback[("human_override_or_false_activation", capability_id)].append(str(route["id"]))
        if outcome == "suppressed":
            for considered in route.get("considered", []):
                if considered.get("eligible") and "query_match" in {
                    str(reason) for reason in considered.get("reason_codes", [])
                }:
                    feedback[("human_suppression_or_false_positive", str(considered["capability_id"]))].append(str(route["id"]))
        if "missing_dependency" in reasons or "missing_validator" in reasons:
            for capability_id in selected or ["capability:technical-product-architecture"]:
                feedback[("dependency_or_validator_omission", capability_id)].append(str(route["id"]))
    for (gap_type, affected), evidence in sorted(feedback.items()):
        threshold = 1 if gap_type == "dependency_or_validator_omission" else 2
        if len(evidence) < threshold:
            continue
        fingerprint = _canonical_hash(
            {
                "gap_type": gap_type,
                "affected": affected,
                "evidence": sorted(evidence),
                "rule_revision": "capability-gap-feedback:v1",
            }
        )
        gaps.append(
            {
                "gap_id": f"gap:{fingerprint.split(':', 1)[1][:20]}",
                "fingerprint": fingerprint,
                "gap_type": gap_type,
                "disposition": "improve_candidate",
                "affected_ids": [affected],
                "evidence_refs": sorted(evidence),
                "counterevidence_refs": ["human_override_is_feedback_not_proof_of_router_error"],
                "next_review": "after_held_out_shadow_router_comparison",
                "human_decision_required": True,
            }
        )
    for node in index["nodes"]:
        if node["node_type"] != "implementation" or node.get("review_status") not in {
            "stale",
            "superseded",
            "retired",
        }:
            continue
        affected = next(
            (
                edge["target"]
                for edge in index["edges"]
                if edge["source"] == node["node_id"] and edge["edge_type"] == "implements"
            ),
            node["node_id"],
        )
        fingerprint = _canonical_hash(
            {
                "gap_type": "stale_or_superseded_implementation",
                "implementation": node["node_id"],
                "state": node["review_status"],
                "affected": affected,
            }
        )
        gaps.append(
            {
                "gap_id": f"gap:{fingerprint.split(':', 1)[1][:20]}",
                "fingerprint": fingerprint,
                "gap_type": "stale_or_superseded_implementation",
                "disposition": "improve_candidate",
                "affected_ids": [affected, node["node_id"]],
                "evidence_refs": [f"implementation_state:{node['review_status']}"],
                "counterevidence_refs": ["lifecycle_state_requires_source_authority_review"],
                "next_review": "after_source_lifecycle_review",
                "human_decision_required": True,
            }
        )
    deduped = {row["fingerprint"]: row for row in gaps}
    return sorted(deduped.values(), key=lambda row: (not row["human_decision_required"], row["gap_id"]))


def mine_workflow_candidates(
    registry: dict[str, Any], route_rows: list[dict[str, Any]], run_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    validated_routes = {
        str(event.get("route_event_id", ""))
        for event in run_rows
        if not event.get("synthetic_or_fixture", False)
        and event.get("event_state") == "independently_validated"
        and event.get("validation_outcome") in {"supported_success", "supported_partial"}
        and event.get("independent_checker_ref")
        and event.get("independent_evaluation_ref")
    }
    known = {
        tuple(workflow["capability_sequence"])
        for workflow in registry["workflows"]
    }
    grouped: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for route in route_rows:
        if route.get("synthetic_or_fixture", False) or route.get("id") not in validated_routes:
            continue
        sequence = tuple(dict.fromkeys([*route.get("selected_capabilities", []), *route.get("supporting_capabilities", [])]))
        if len(sequence) >= 2 and sequence not in known:
            grouped[sequence].append(str(route["id"]))
    candidates = []
    for sequence, evidence in sorted(grouped.items()):
        if len(evidence) < 3:
            continue
        fingerprint = _canonical_hash({"sequence": sequence, "rule_revision": "workflow-miner:v1"})
        candidates.append(
            {
                "candidate_id": f"workflow-candidate:{fingerprint.split(':', 1)[1][:20]}",
                "fingerprint": fingerprint,
                "capability_sequence": list(sequence),
                "validated_run_count": len(evidence),
                "status": "candidate",
                "human_decision_required": True,
                "evidence_refs": sorted(evidence),
            }
        )
    return candidates


def _efficiency(run_rows: list[dict[str, Any]]) -> dict[str, Any]:
    events = [event for event in run_rows if not event.get("synthetic_or_fixture", False)]
    run_starts: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("event_state") == "started":
            run_starts.setdefault(str(event.get("run_id", "")), event)
    efficiency = {
        "model_call_count": 0,
        "known_input_tokens": 0,
        "known_output_tokens": 0,
        "known_cache_read_tokens": 0,
        "unknown_token_event_count": 0,
        "known_cost_total": 0.0,
        "unknown_cost_event_count": 0,
        "deterministic_run_count": 0,
        "agent_run_count": 0,
        "external_adapter_run_count": 0,
        "context_cache_hit_count": 0,
    }
    for event in run_starts.values():
        efficiency[f"{event.get('execution_mode', 'agent')}_run_count"] += 1
        efficiency["model_call_count"] += int(event.get("model_call_count", 0))
        if event.get("context_cache_hit"):
            efficiency["context_cache_hit_count"] += 1
        tokens = event.get("token_usage", {})
        if tokens.get("status") == "unknown":
            efficiency["unknown_token_event_count"] += 1
        else:
            efficiency["known_input_tokens"] += int(tokens.get("input_tokens") or 0)
            efficiency["known_output_tokens"] += int(tokens.get("output_tokens") or 0)
            efficiency["known_cache_read_tokens"] += int(tokens.get("cache_read_tokens") or 0)
        cost = event.get("cost_usage", {})
        if cost.get("status") == "unknown":
            efficiency["unknown_cost_event_count"] += 1
        else:
            efficiency["known_cost_total"] += float(cost.get("amount") or 0.0)
    efficiency["known_cost_total"] = round(efficiency["known_cost_total"], 8)
    return efficiency


def _operator_view(
    gaps: list[dict[str, Any]],
    workflow_candidates: list[dict[str, Any]],
    routine_evaluations: list[dict[str, Any]],
    *,
    quiet_mode: bool,
) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    for gap in gaps:
        kind = "coverage_gap" if "selected" in gap["gap_type"] or "eligible" in gap["gap_type"] else "health_risk"
        fingerprint = _canonical_hash({"kind": kind, "gap": gap["fingerprint"]})
        decisions.append(
            {
                "decision_id": f"decision:{fingerprint.split(':', 1)[1][:20]}",
                "decision_key": f"{kind}:{gap['affected_ids'][0]}",
                "kind": kind,
                "label": gap["affected_ids"][0].split(":", 1)[-1].replace("-", " "),
                "recommended_action": gap["disposition"],
                "alternatives": ["observe_more", "route_existing", "defer", "reject"],
                "covered_item_count": 1,
                "evidence_refs": gap["evidence_refs"],
                "human_only": True,
                "fingerprint": fingerprint,
            }
        )
    for candidate in workflow_candidates:
        fingerprint = _canonical_hash({"kind": "workflow_candidate", "candidate": candidate["fingerprint"]})
        decisions.append(
            {
                "decision_id": f"decision:{fingerprint.split(':', 1)[1][:20]}",
                "decision_key": f"workflow_candidate:{candidate['fingerprint']}",
                "kind": "workflow_candidate",
                "label": "repeated validated capability sequence",
                "recommended_action": "approve_bounded_shadow_pilot",
                "alternatives": ["observe_more", "defer", "reject"],
                "covered_item_count": candidate["validated_run_count"],
                "evidence_refs": candidate["evidence_refs"],
                "human_only": True,
                "fingerprint": fingerprint,
            }
        )
    for routine in routine_evaluations:
        if routine["evaluation_status"] != "candidate_due":
            continue
        fingerprint = _canonical_hash(
            {"kind": "routine_candidate", "routine": routine["idempotency_key"]}
        )
        decisions.append(
            {
                "decision_id": f"decision:{fingerprint.split(':', 1)[1][:20]}",
                "decision_key": f"routine_candidate:{routine['routine_id']}",
                "kind": "authority_gate",
                "label": routine["routine_id"].replace("-", " "),
                "recommended_action": "review_read_only_candidate",
                "alternatives": ["observe_more", "defer", "snooze", "reject", "pause"],
                "covered_item_count": 1,
                "evidence_refs": [routine["input_fingerprint"]],
                "human_only": True,
                "fingerprint": fingerprint,
            }
        )
    decisions.sort(key=lambda row: (row["kind"], row["decision_key"]))
    now = [] if quiet_mode else decisions[:3]
    return {
        "now": now,
        "digest": decisions,
        "overflow_count": max(0, len(decisions) - len(now)),
        "quiet_mode": quiet_mode,
        "immediate_decision_count": len(now),
        "review_minutes_estimate": min(5, len(now) * 1 + (1 if now else 0)),
    }


def build_capability_portfolio_snapshot(
    repo_root: Path,
    *,
    quiet_mode: bool = False,
    activated_routine_ids: Iterable[str] = (),
    previous_routine_fingerprints: dict[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    registry = load_technical_product_registry(repo_root)
    index = build_capability_index(repo_root)
    route_rows = _effective_events(_read_jsonl(_route_ledger(repo_root)))
    run_rows = _effective_events(_read_jsonl(_run_ledger(repo_root)))
    for row in route_rows:
        _validate(row, repo_root / ROUTE_SCHEMA)
    for row in run_rows:
        _validate(row, repo_root / RUN_SCHEMA)
    capability_usage, workflow_usage = _usage_projection(registry, route_rows, run_rows)
    gaps = _gap_candidates(capability_usage, route_rows, index)
    workflow_candidates = mine_workflow_candidates(registry, route_rows, run_rows)
    routine_evaluations = evaluate_routines(
        repo_root,
        activated_routine_ids=activated_routine_ids,
        previous_fingerprints=previous_routine_fingerprints,
        quiet_mode=quiet_mode,
        catalog_fingerprint=index["catalog_fingerprint"],
    )
    operational_route_count = sum(not row.get("synthetic_or_fixture", False) for row in route_rows)
    operational_run_count = len({str(row.get("run_id", "")) for row in run_rows if not row.get("synthetic_or_fixture", False)})
    snapshot = {
        "schema_version": "dad.capability_portfolio_snapshot.v1",
        "generated_at": (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        "status": "generated_candidate",
        "candidate_only": True,
        "execution_authorized": False,
        "catalog_fingerprint": index["catalog_fingerprint"],
        "source_fingerprints": index["source_fingerprints"],
        "summary": {
            "capability_count": len(capability_usage),
            "workflow_count": len(workflow_usage),
            "operational_route_count": operational_route_count,
            "operational_run_count": operational_run_count,
            "gap_candidate_count": len(gaps),
            "unobserved_capability_count": sum(row["observation_status"] == "unobserved" for row in capability_usage),
        },
        "capabilities": capability_usage,
        "workflows": workflow_usage,
        "workflow_candidates": workflow_candidates,
        "gap_candidates": gaps,
        "routines": routine_evaluations,
        "efficiency": _efficiency(run_rows),
        "operator": _operator_view(
            gaps,
            workflow_candidates,
            routine_evaluations,
            quiet_mode=quiet_mode,
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    _validate(snapshot, repo_root / SNAPSHOT_SCHEMA)
    return snapshot


def evaluate_routines(
    repo_root: Path,
    *,
    activated_routine_ids: Iterable[str] = (),
    previous_fingerprints: dict[str, str] | None = None,
    quiet_mode: bool = False,
    catalog_fingerprint: str | None = None,
) -> list[dict[str, Any]]:
    registry = load_technical_product_registry(repo_root)
    path = repo_root / "assets" / "agent-skills" / "technical-product-company-os" / "routines.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("routines"), list):
        raise ValueError("Invalid Technical Product OS routine contract")
    required = set(registry["automation_policy"]["required_fields"])
    activated = set(activated_routine_ids)
    previous = previous_fingerprints or {}
    catalog_fingerprint = catalog_fingerprint or build_capability_index(repo_root)["catalog_fingerprint"]
    route_fingerprint = _path_fingerprint(_route_ledger(repo_root))
    run_fingerprint = _path_fingerprint(_run_ledger(repo_root))
    combined_usage = _canonical_hash({"route": route_fingerprint, "run": run_fingerprint})
    portfolio_fingerprint = _canonical_hash(
        {"catalog": catalog_fingerprint, "route": route_fingerprint, "run": run_fingerprint}
    )
    values = {
        "catalog_fingerprint": catalog_fingerprint,
        "route_and_run_ledger_fingerprint": combined_usage,
        "portfolio_candidate_fingerprint": portfolio_fingerprint,
    }
    evaluations: list[dict[str, Any]] = []
    for routine in payload["routines"]:
        present = set(routine)
        normalized_required = required - {"stable_id"}
        if not normalized_required <= present or "routine_id" not in present:
            missing = sorted(normalized_required - present)
            raise ValueError(f"Routine contract missing required fields: {missing}")
        routine_id = str(routine["routine_id"])
        fingerprint = values[str(routine["input_fingerprint"])]
        is_activated = routine_id in activated
        previous_fingerprint = previous.get(routine_id, "")
        if not is_activated:
            status = "dormant"
            reason_codes = ["human_activation_missing"]
        elif quiet_mode:
            status = "suppressed"
            reason_codes = ["quiet_mode"]
        elif not previous_fingerprint:
            status = "baseline_required"
            reason_codes = ["prior_fingerprint_missing"]
        elif previous_fingerprint == fingerprint:
            status = "unchanged_heartbeat"
            reason_codes = ["input_fingerprint_unchanged"]
        else:
            status = "candidate_due"
            reason_codes = ["input_fingerprint_delta", "human_review_required"]
        idempotency_key = _canonical_hash(
            {"routine_id": routine_id, "revision": routine["revision"], "input": fingerprint}
        )
        evaluations.append(
            {
                "routine_id": routine_id,
                "revision": str(routine["revision"]),
                "activation_status": "activated_by_explicit_input" if is_activated else "dormant",
                "evaluation_status": status,
                "input_fingerprint": fingerprint,
                "previous_fingerprint": previous_fingerprint or None,
                "idempotency_key": idempotency_key,
                "reason_codes": reason_codes,
                "model_call_count": 0,
                "model_tokens": 0,
                "notification_authorized": False,
                "external_mutation_authorized": False,
                "human_decision_required": status == "candidate_due",
            }
        )
    return sorted(evaluations, key=lambda row: row["routine_id"])


def build_operational_capability_graph(
    repo_root: Path,
    *,
    snapshot: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    registry = load_technical_product_registry(repo_root)
    index = build_capability_index(repo_root)
    route_rows = _effective_events(_read_jsonl(_route_ledger(repo_root)))
    run_rows = _effective_events(_read_jsonl(_run_ledger(repo_root)))
    for row in route_rows:
        _validate(row, repo_root / ROUTE_SCHEMA)
    for row in run_rows:
        _validate(row, repo_root / RUN_SCHEMA)
    snapshot = snapshot or build_capability_portfolio_snapshot(repo_root, now=now)
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    def add_node(
        node_id: str,
        node_type: str,
        *,
        name: str = "",
        status: str = "candidate",
        authority_ref: str = REGISTRY_PATH.as_posix(),
        revision_ref: str = "",
        fingerprint: str = "",
        evidence_refs: Iterable[str] = (),
    ) -> None:
        node = {
            "node_id": node_id,
            "node_type": node_type,
            "name": name or node_id.split(":", 1)[-1],
            "status": status,
            "authority_ref": authority_ref,
            "evidence_refs": sorted(set(str(ref) for ref in evidence_refs)),
        }
        if revision_ref:
            node["revision_ref"] = revision_ref
        if fingerprint:
            node["fingerprint"] = fingerprint
        nodes.setdefault(node_id, node)

    def add_edge(source: str, edge_type: str, target: str, evidence_ref: str) -> None:
        key = (source, edge_type, target, evidence_ref)
        edges.setdefault(
            key,
            {
                "source": source,
                "edge_type": edge_type,
                "target": target,
                "status": "candidate",
                "evidence_ref": evidence_ref,
            },
        )

    for node in index["nodes"]:
        add_node(
            node["node_id"],
            node["node_type"],
            name=node["name"],
            status=str(node.get("review_status", "candidate")),
            authority_ref=str(node.get("authority_ref", REGISTRY_PATH.as_posix())),
            evidence_refs=[REGISTRY_PATH.as_posix()],
        )
    for edge in index["edges"]:
        add_edge(edge["source"], edge["edge_type"], edge["target"], edge["evidence_ref"])

    for right in registry["decision_rights"]:
        policy_id = f"policy:decision-right:{right['right_id']}"
        add_node(policy_id, "policy", name=right["right_id"], evidence_refs=[REGISTRY_PATH.as_posix()])
    for tier in registry["consequence_tiers"]:
        add_node(
            f"policy:consequence-tier:{tier['tier']}",
            "policy",
            name=tier["label"],
            evidence_refs=[REGISTRY_PATH.as_posix()],
        )
    for adapter in registry["adapter_policy"]:
        add_node(
            adapter["adapter_id"],
            "adapter",
            status=adapter["status"],
            evidence_refs=[REGISTRY_PATH.as_posix()],
        )

    for route in route_rows:
        route_id = str(route["id"])
        project_id = f"project:{route['opaque_task_id']}"
        repository_id = str(route["repository_id"])
        add_node(
            route_id,
            "route_trace",
            status=str(route.get("route_outcome", "unknown")),
            revision_ref=str(route["route_revision"]),
            fingerprint=str(route["semantic_task_fingerprint"]),
            evidence_refs=[route_id],
        )
        add_node(project_id, "project", evidence_refs=[route_id])
        add_node(repository_id, "repository", evidence_refs=[route_id])
        add_edge(project_id, "member_of", repository_id, route_id)
        add_edge(route_id, "applies_to", project_id, route_id)
        add_edge(route_id, "governed_by", f"policy:decision-right:{route['requested_right']}", route_id)
        add_edge(route_id, "governed_by", f"policy:consequence-tier:{route['consequence_tier']}", route_id)
        for capability_id in [
            *route.get("selected_capabilities", []),
            *route.get("supporting_capabilities", []),
        ]:
            add_edge(route_id, "applies_to", str(capability_id), route_id)
        for revision_id in route.get("selected_workflow_revisions", []):
            add_edge(route_id, "applies_to", str(revision_id), route_id)
        for validator in route.get("required_validators", []):
            add_node(str(validator), "validator", evidence_refs=[route_id])
            add_edge(route_id, "validated_by", str(validator), route_id)

    grouped_runs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in run_rows:
        grouped_runs[str(event["run_id"])].append(event)
    for run_id, events in grouped_runs.items():
        events.sort(key=lambda row: (str(row["time"]), str(row["id"])))
        first = events[0]
        node_id = f"workflow-run:{run_id}"
        add_node(
            node_id,
            "workflow_run",
            status=str(events[-1]["event_state"]),
            revision_ref=str(first["workflow_revision_id"]),
            evidence_refs=[str(event["id"]) for event in events],
        )
        add_edge(node_id, "derived_from", str(first["workflow_revision_id"]), str(first["id"]))
        add_edge(node_id, "observed_by", str(first["route_event_id"]), str(first["id"]))
        for capability_id in sorted(
            {str(cap) for event in events for cap in event.get("capability_ids", [])}
        ):
            add_edge(node_id, "applies_to", capability_id, str(first["id"]))
        for event in events:
            if event.get("event_state") != "independently_validated":
                continue
            evidence_id = str(event["independent_evaluation_ref"])
            validator_id = str(event["independent_checker_ref"])
            add_node(evidence_id, "evidence", status=str(event["validation_outcome"]), evidence_refs=[str(event["id"])])
            add_node(validator_id, "validator", evidence_refs=[str(event["id"])])
            add_edge(node_id, "validated_by", evidence_id, str(event["id"]))
            add_edge(evidence_id, "validated_by", validator_id, str(event["id"]))

    for gap in snapshot["gap_candidates"]:
        add_node(
            gap["gap_id"],
            "gap_candidate",
            status=gap["disposition"],
            fingerprint=gap["fingerprint"],
            evidence_refs=gap["evidence_refs"],
        )
        for affected in gap["affected_ids"]:
            if affected not in nodes:
                inferred_type = "capability" if str(affected).startswith("capability:") else "implementation"
                add_node(str(affected), inferred_type, evidence_refs=gap["evidence_refs"])
            add_edge(gap["gap_id"], "gap_evidence_for", str(affected), gap["fingerprint"])
    human_policy = "policy:decision-right:recommend"
    for decision in snapshot["operator"]["digest"]:
        add_node(
            decision["decision_id"],
            "human_decision",
            status="pending_human",
            fingerprint=decision["fingerprint"],
            evidence_refs=decision["evidence_refs"],
        )
        add_edge(decision["decision_id"], "governed_by", human_policy, decision["fingerprint"])

    node_rows = sorted(nodes.values(), key=lambda row: row["node_id"])
    edge_rows = sorted(edges.values(), key=lambda row: (row["source"], row["edge_type"], row["target"], row["evidence_ref"]))
    node_ids = {row["node_id"] for row in node_rows}
    if any(edge["source"] not in node_ids or edge["target"] not in node_ids for edge in edge_rows):
        raise ValueError("Operational graph contains an unresolved endpoint")
    source_fingerprint = _canonical_hash(
        {
            "catalog": index["catalog_fingerprint"],
            "routes": [(row["source"], row["id"]) for row in route_rows],
            "runs": [(row["source"], row["id"]) for row in run_rows],
            "snapshot": [row["fingerprint"] for row in snapshot["gap_candidates"]],
        }
    )
    graph = {
        "schema_version": "dad.capability_operational_graph.v1",
        "generated_at": (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        "status": "generated_candidate",
        "candidate_only": True,
        "execution_authorized": False,
        "catalog_fingerprint": index["catalog_fingerprint"],
        "source_fingerprint": source_fingerprint,
        "nodes": node_rows,
        "edges": edge_rows,
        "summary": {
            "node_count": len(node_rows),
            "edge_count": len(edge_rows),
            "node_type_counts": dict(sorted(Counter(row["node_type"] for row in node_rows).items())),
            "edge_type_counts": dict(sorted(Counter(row["edge_type"] for row in edge_rows).items())),
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    _validate(graph, repo_root / GRAPH_SCHEMA)
    return graph


def write_capability_os_outputs(repo_root: Path, snapshot: dict[str, Any]) -> dict[str, Any]:
    _validate(snapshot, repo_root / SNAPSHOT_SCHEMA)
    base = data_path(repo_root, "central_reports") / "portfolio_os"
    path = base / "capability-os-snapshot.json"
    graph = build_operational_capability_graph(repo_root, snapshot=snapshot)
    graph_path = base / "capability-os-operational-graph.json"
    routine_state_path = base / "capability-os-routine-state.json"
    atomic_write_text(path, json_dumps(snapshot, pretty=True) + "\n")
    atomic_write_text(graph_path, json_dumps(graph, pretty=True) + "\n")
    atomic_write_text(
        routine_state_path,
        json_dumps(
            {
                "schema_version": "dad.capability_routine_state.v1",
                "captured_at": snapshot["generated_at"],
                "fingerprints": {
                    row["routine_id"]: row["input_fingerprint"] for row in snapshot["routines"]
                },
                "execution_authorized": False,
                "authority_boundary": AUTHORITY_BOUNDARY,
            },
            pretty=True,
        )
        + "\n",
    )
    return {
        "path": str(path),
        "graph_path": str(graph_path),
        "routine_state_path": str(routine_state_path),
        "status": snapshot["status"],
        "summary": snapshot["summary"],
        "operator": snapshot["operator"],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def classify_offload(
    repo_root: Path,
    *,
    task_class: str,
    mechanical_task: bool,
    closed_allowed_paths: bool,
    stable_authority_and_interfaces: bool,
    deterministic_validation: bool,
    isolated_worktree: bool,
    reversible_diff: bool,
    explicit_lease: bool,
    independent_checker: bool,
    sanitized_minimal_packet: bool,
    prohibited_classes: Iterable[str] = (),
    adapter_id: str = "adapter:cursor-local",
) -> dict[str, Any]:
    registry = load_technical_product_registry(repo_root)
    adapter = next((row for row in registry["adapter_policy"] if row["adapter_id"] == adapter_id), None)
    checks = {
        "mechanical_task": mechanical_task,
        "closed_allowed_paths": closed_allowed_paths,
        "stable_authority_and_interfaces": stable_authority_and_interfaces,
        "deterministic_validation": deterministic_validation,
        "isolated_worktree": isolated_worktree,
        "reversible_diff": reversible_diff,
        "explicit_lease": explicit_lease,
        "independent_checker": independent_checker,
        "sanitized_minimal_packet": sanitized_minimal_packet,
    }
    prohibited = sorted(set(prohibited_classes) & set(registry["offload_policy"]["reject_classes"]))
    reasons = [f"missing_{key}" for key, passed in checks.items() if not passed]
    reasons.extend(f"prohibited_{value}" for value in prohibited)
    if adapter is None:
        reasons.append("adapter_unknown")
    elif adapter["status"] != "authorized":
        reasons.append("adapter_not_authorized")
    eligible = not reasons
    return {
        "task_class": task_class,
        "adapter_id": adapter_id,
        "eligible": eligible,
        "route": "approved_external_adapter" if eligible else "deterministic_local_or_manual",
        "reason_codes": reasons or ["all_offload_gates_passed"],
        "checks": checks,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


__all__ = [
    "AUTHORITY_BOUNDARY",
    "append_routing_receipt",
    "append_workflow_run_event",
    "build_capability_index",
    "build_capability_portfolio_snapshot",
    "build_operational_capability_graph",
    "build_routing_receipt",
    "build_workflow_run_event",
    "classify_offload",
    "evaluate_decision_right",
    "evaluate_routines",
    "load_technical_product_registry",
    "mine_workflow_candidates",
    "route_capabilities",
    "write_capability_os_outputs",
]
