"""Deterministic search-before-create across DAD's durable capability surfaces."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .entity_identity import fold_state as fold_entity_state, read_events as read_entity_events
from .portfolio_intents import search_plans


AUTHORITY_BOUNDARY = (
    "Related-work results are retrieval evidence only. They cannot merge identities, "
    "create workstreams, promote dependencies, grant leases, or authorize execution."
)


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _candidate(
    *, candidate_id: str, kind: str, title: str, text: str, query_tokens: set[str], source_ref: str
) -> dict[str, Any] | None:
    shared = sorted(query_tokens & _tokens(text))
    if not shared:
        return None
    coverage = min(1.0, len(shared) / max(1, len(query_tokens)))
    return {
        "candidate_id": candidate_id,
        "candidate_kind": kind,
        "title": title,
        "shared_tokens": shared[:12],
        "deterministic_score": round(coverage, 6),
        "evidence_refs": [source_ref],
        "counterevidence": [] if coverage >= 0.5 else ["query_coverage_below_half"],
        "relation_candidate": "possible_duplicate_of" if coverage >= 0.8 else "peer_of",
        "review_status": "candidate",
        "execution_authorized": False,
    }


def search_related_work(
    repo_root: Path,
    hub_root: Path,
    query: str,
    *,
    privacy_partition: str = "private",
    limit: int = 5,
) -> dict[str, Any]:
    """Search plans, entities, families, skills and capability/workflow definitions.

    V1 intentionally performs no embedding call and never selects an identity winner.
    """

    query_tokens = _tokens(query)
    if not query_tokens:
        raise ValueError("Related-work query must contain searchable terms")
    rows: list[dict[str, Any]] = []

    try:
        plan_result = search_plans(
            hub_root, query, privacy_partition=privacy_partition, limit=25
        )
    except (OSError, RuntimeError):
        plan_result = {"matches": [], "coverage": {"unavailable": "plan_index"}}
    for plan in plan_result.get("matches", []):
        rows.append(
            {
                "candidate_id": plan["plan_id"],
                "candidate_kind": "plan",
                "title": plan["title"],
                "shared_tokens": plan["shared_tokens"],
                "deterministic_score": round(
                    min(1.0, len(plan["shared_tokens"]) / max(1, len(query_tokens))), 6
                ),
                "evidence_refs": [f"plan-revision:{plan['revision_id']}"],
                "counterevidence": [],
                "relation_candidate": "possible_duplicate_of",
                "review_status": "candidate",
                "execution_authorized": False,
            }
        )

    entity_state = fold_entity_state(read_entity_events(hub_root))
    for entity in entity_state["entities"]:
        card = entity["semantic_card"]
        if card.get("privacy_partition") != privacy_partition:
            continue
        text = " ".join(
            str(value)
            for key in (
                "label", "aliases", "capabilities", "outcomes", "scope_included", "audience", "domain_facets"
            )
            for value in ([card.get(key, "")] if isinstance(card.get(key), str) else card.get(key, []))
        )
        candidate = _candidate(
            candidate_id=entity["entity_id"],
            kind=card["entity_kind"],
            title=card["label"],
            text=text,
            query_tokens=query_tokens,
            source_ref=f"entity-revision:{entity['entity_revision_id']}",
        )
        if candidate:
            rows.append(candidate)

    sources = (
        ("registry/agent-family-portfolio-registry.json", "families", "family_id", "name", "agent_family"),
        ("registry/agent-skill-library.json", "skills", "skill_id", "name", "skill"),
        ("registry/technical-product-company-os-registry.json", "capabilities", "capability_id", "name", "capability"),
        ("registry/technical-product-company-os-registry.json", "workflows", "workflow_id", "workflow_id", "workflow"),
    )
    unavailable: list[str] = []
    for source_ref, collection, id_key, title_key, kind in sources:
        path = repo_root / source_ref
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            unavailable.append(source_ref)
            continue
        for row in payload.get(collection, []):
            text = json.dumps(row, sort_keys=True, ensure_ascii=False)
            candidate = _candidate(
                candidate_id=str(row[id_key]),
                kind=kind,
                title=str(row[title_key]),
                text=text,
                query_tokens=query_tokens,
                source_ref=source_ref,
            )
            if candidate:
                rows.append(candidate)

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["candidate_kind"], row["candidate_id"])
        current = deduped.get(key)
        if current is None or row["deterministic_score"] > current["deterministic_score"]:
            deduped[key] = row
    ranked = sorted(
        deduped.values(),
        key=lambda row: (-row["deterministic_score"], row["candidate_kind"], row["candidate_id"]),
    )
    top = ranked[: max(0, min(limit, 5))]
    equal_best = len(top) > 1 and top[0]["deterministic_score"] == top[1]["deterministic_score"]
    result_material = [
        {"candidate_id": row["candidate_id"], "candidate_kind": row["candidate_kind"], "score": row["deterministic_score"]}
        for row in top
    ]
    result = {
        "schema_version": "dad.portfolio_related_work.v1",
        "retrieval_result_digest": _digest({"candidates": result_material, "privacy_partition": privacy_partition}),
        "privacy_partition": privacy_partition,
        "candidates": top,
        "classification": "ambiguous" if equal_best else ("candidate_found" if top else "insufficient_evidence"),
        "primary_candidate_id": "",
        "smallest_viable_family_ids": [
            row["candidate_id"] for row in top if row["candidate_kind"] == "agent_family"
        ][:2],
        "coverage": {
            "candidate_count_before_limit": len(ranked),
            "returned_count": len(top),
            "unavailable_sources": sorted(set(unavailable)),
            "external_embedding_calls": 0,
            "model_calls": 0,
        },
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    return result


__all__ = ["AUTHORITY_BOUNDARY", "search_related_work"]
