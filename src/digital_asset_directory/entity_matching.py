"""Deterministic, candidate-only semantic entity matching."""

from __future__ import annotations

from typing import Any

from .entity_identity import AUTHORITY_BOUNDARY, normalize_label
from .ids import stable_id
from .utils import idf_weighted_cosine, idf_weights, tokens

WEIGHTS = {
    "capabilities": 0.30,
    "outcomes": 0.20,
    "scope": 0.15,
    "lexical": 0.15,
    "graph": 0.10,
    "lineage": 0.10,
}


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _set(card: dict[str, Any], field: str) -> set[str]:
    return {normalize_label(str(value)) for value in card.get(field, []) if str(value).strip()}


def _card_text(card: dict[str, Any]) -> str:
    values = [str(card.get("label", "")), *[str(v) for v in card.get("aliases", [])]]
    values.extend(str(v) for field in ("capabilities", "outcomes", "scope_included", "audience", "domain_facets") for v in card.get(field, []))
    return " ".join(values)


def compare_cards(
    source: dict[str, Any],
    target: dict[str, Any],
    *,
    graph_neighbors_source: set[str] | None = None,
    graph_neighbors_target: set[str] | None = None,
    lineage_source: set[str] | None = None,
    lineage_target: set[str] | None = None,
) -> dict[str, Any]:
    if source.get("privacy_partition") != target.get("privacy_partition"):
        return {"eligible": False, "blocker": "privacy_partition_mismatch"}
    source_caps, target_caps = _set(source, "capabilities"), _set(target, "capabilities")
    source_out, target_out = _set(source, "outcomes"), _set(target, "outcomes")
    source_scope = _set(source, "scope_included") | _set(source, "audience")
    target_scope = _set(target, "scope_included") | _set(target, "audience")
    source_tokens, target_tokens = tokens(_card_text(source)), tokens(_card_text(target))
    lexical_weights = idf_weights([source_tokens, target_tokens])
    components = {
        "capabilities": _jaccard(source_caps, target_caps),
        "outcomes": _jaccard(source_out, target_out),
        "scope": _jaccard(source_scope, target_scope),
        "lexical": idf_weighted_cosine(source_tokens, target_tokens, lexical_weights),
        "graph": _jaccard(graph_neighbors_source or set(), graph_neighbors_target or set()),
        "lineage": _jaccard(lineage_source or set(), lineage_target or set()),
    }
    evidence_families = sum(1 for name, score in components.items() if score > 0 and name != "lexical")
    coverage = sum(WEIGHTS[name] for name, score in components.items() if score > 0)
    score = sum(WEIGHTS[name] * value for name, value in components.items())
    excluded_conflict = bool(_set(source, "scope_excluded") & _set(target, "scope_included")) or bool(
        _set(target, "scope_excluded") & _set(source, "scope_included")
    )
    relation = "peer_of"
    if excluded_conflict and score >= 0.35:
        relation = "conflicts_with"
    elif source_caps and source_caps < target_caps and source_caps.issubset(target_caps) and components["outcomes"] >= 0.5:
        relation = "specializes"
    elif (
        score >= 0.70
        and coverage >= 0.60
        and components["capabilities"] >= 0.70
        and components["outcomes"] >= 0.70
        and not excluded_conflict
    ):
        relation = "possible_duplicate_of"
    elif components["outcomes"] >= 0.6 and components["capabilities"] >= 0.5 and _set(source, "methods") != _set(target, "methods"):
        relation = "variant_of"
    band = "no_candidate"
    if score >= 0.65 and coverage >= 0.60 and evidence_families >= 3:
        band = "strong_review_candidate"
    elif score >= 0.45 and coverage >= 0.40 and evidence_families >= 2:
        band = "review_candidate"
    elif score >= 0.30:
        band = "weak_inspect_only"
    return {
        "eligible": True,
        "score": round(score, 4),
        "evidence_coverage": round(coverage, 4),
        "evidence_family_count": evidence_families,
        "components": {key: round(value, 4) for key, value in components.items()},
        "proposed_relation": relation,
        "band": band,
        "review_status": "candidate",
        "same_identity": False,
        "execution_authorized": False,
    }


def find_candidates(source_entity: dict[str, Any], entities: list[dict[str, Any]], *, limit: int = 5) -> dict[str, Any]:
    source_card = source_entity["semantic_card"]
    matches: list[dict[str, Any]] = []
    for target in entities:
        if target.get("entity_id") == source_entity.get("entity_id"):
            continue
        comparison = compare_cards(source_card, target["semantic_card"])
        if not comparison.get("eligible") or comparison.get("band") == "no_candidate":
            continue
        matches.append(
            {
                "candidate_id": stable_id(
                    "entity-match-candidate",
                    str(source_entity.get("entity_revision_id", "")),
                    str(target.get("entity_revision_id", "")),
                    str(comparison["proposed_relation"]),
                ),
                "source_entity_id": source_entity.get("entity_id"),
                "target_entity_id": target.get("entity_id"),
                "target_label": target["semantic_card"].get("label"),
                **comparison,
            }
        )
    matches.sort(key=lambda row: (-row["score"], str(row["target_entity_id"])))
    selected = matches[: max(0, min(limit, 5))]
    ambiguous = len(selected) >= 2 and abs(selected[0]["score"] - selected[1]["score"]) <= 0.05
    return {
        "matches": selected,
        "ambiguous_no_primary_candidate": ambiguous,
        "primary_candidate_id": "" if ambiguous or not selected else selected[0]["candidate_id"],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


__all__ = ["WEIGHTS", "compare_cards", "find_candidates"]
