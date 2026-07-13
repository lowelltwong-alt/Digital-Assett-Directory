"""Portfolio OS relationship classification (deterministic core).

Fixes over the audited draft (evidence in
``docs/frontier/collaboration/00_CLAUDE_INDEPENDENT_AUDIT.md``):

* relation identity includes the source, target, type, and an evidence
  revision, so two ideas relating to the same target can no longer collide
  (audit C8);
* intent markers (experiment/contradiction/continuation) only apply alongside
  sufficient token overlap, so common words like "without" cannot force a
  conflict interrupt on their own (C13);
* target maturity only *tips* a strong-band overlap toward continuation; a
  weak two-token overlap with an established project is a sibling, not a
  "resume existing work" instruction (C9);
* ideas captured together in one conversation become relation candidates for
  one another (C10) via ``co_captured_idea`` targets.

No model call happens here. Every relation carries a human-readable reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from .ids import stable_id
from .utils import idf_weighted_cosine, idf_weights, tokens

# Thresholds are ordinal policy, not calibrated probabilities. Methodology:
# scores are idf-weighted cosine over normalized token sets in [0, 1]; bands
# were chosen so that (a) two generic shared tokens near the floor can never
# drive a strong claim, (b) marker words require MARKER_MIN_SCORE of real
# overlap before they may reclassify, and (c) duplicate claims need both a
# high score and 3+ shared tokens. Accept/dismiss stats per class
# (portfolio_attention) are the calibration feedback loop; changing a band
# should cite those stats.
RELATION_MIN_SCORE = 0.18
RELATION_MIN_SHARED = 2
MARKER_MIN_SCORE = 0.30
MATURE_CONTINUATION_MIN_SCORE = 0.35
MATURE_CONTINUATION_MIN_SHARED = 3
CONTINUATION_MIN_SCORE = 0.55
DUPLICATE_MIN_SCORE = 0.72
DEFAULT_RELATION_LIMIT = 5

RELATIONSHIP_TYPES = (
    "continuation",
    "sibling",
    "duplicate",
    "experiment",
    "contradiction",
)

_EXPERIMENT_MARKERS = frozenset(
    {"experiment", "spike", "prototype", "poc", "alternative", "compare", "variant", "benchmark"}
)
_CONTRADICTION_MARKERS = frozenset(
    {"instead", "replace", "replaces", "revert", "abandon", "undo", "reverse", "scrap", "supersede"}
)
_CONTINUATION_MARKERS = frozenset(
    {"continue", "finish", "resume", "extend", "complete", "followup", "polish", "harden"}
)

_GENERIC_TOKENS = frozenset(
    {
        "add", "build", "chore", "codex", "docs", "feature", "fix", "idea", "initial",
        "main", "make", "new", "plan", "project", "prototype", "test", "thing", "update", "work",
    }
)
_SHORT_DOMAIN_TOKENS = frozenset({"ai", "os", "ui", "db", "ml", "cli", "api"})
_WORD_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True, slots=True, kw_only=True)
class RelationTarget:
    """Prior work a new idea can relate to.

    ``target_kind``: ``workstream`` | ``co_captured_idea`` |
    ``portfolio_project`` | ``portfolio_branch``. ``mature`` marks established
    prior work; per C9 it can only tip classification inside the strong band.
    """

    target_kind: str
    target_id: str
    target_label: str
    text: str
    mature: bool = False


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def short_label(text: str, *, limit: int = 60) -> str:
    normalized = normalize_text(text)
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def idea_tokens(text: str) -> set[str]:
    separated = re.sub(r"[-_./\\:+]+", " ", text)
    short = {part.casefold() for part in separated.split() if part.casefold() in _SHORT_DOMAIN_TOKENS}
    return (tokens(separated) | short) - _GENERIC_TOKENS


def _markers(text: str) -> set[str]:
    words = set(_WORD_RE.findall(text.casefold()))
    found: set[str] = set()
    if words & _EXPERIMENT_MARKERS:
        found.add("experiment")
    if words & _CONTRADICTION_MARKERS:
        found.add("contradiction")
    if words & _CONTINUATION_MARKERS:
        found.add("continuation")
    return found


def _confidence_for(score: float, shared_count: int) -> str:
    if score >= DUPLICATE_MIN_SCORE and shared_count >= 3:
        return "high"
    if score >= CONTINUATION_MIN_SCORE or shared_count >= 4:
        return "medium"
    return "low"


def relation_identity(
    *,
    source_id: str,
    target_kind: str,
    target_id: str,
    relationship_type: str,
    shared: list[str],
    score: float,
) -> str:
    """Identity includes source, target, type, and an evidence revision (C8)."""

    evidence_revision = f"{','.join(shared)}@{score:.2f}"
    return stable_id(
        "portfolio-relation", source_id, target_kind, target_id, relationship_type, evidence_revision
    )


def classify_relations(
    source_id: str,
    idea_text: str,
    targets: Iterable[RelationTarget],
    *,
    limit: int = DEFAULT_RELATION_LIMIT,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Classify how a new idea relates to candidate prior work.

    Deterministic; no state; no AI. Returns (relations, coverage_notes).
    Coverage notes record *why nothing could be evaluated* when that happens
    (mechanism M5: silence must be evidence of evaluation, not of failure).
    """

    coverage: list[str] = []
    target_list = list(targets)
    if not target_list:
        coverage.append("no_candidate_targets")
        return [], coverage
    source_tokens = idea_tokens(idea_text)
    if not source_tokens:
        coverage.append("idea_text_yielded_no_tokens")
        return [], coverage
    markers = _markers(idea_text)
    target_token_sets = [idea_tokens(t.text) for t in target_list]
    weights = idf_weights([source_tokens, *target_token_sets])

    relations: list[dict[str, Any]] = []
    for target, target_tokens in zip(target_list, target_token_sets):
        shared = sorted(source_tokens & target_tokens)
        if len(shared) < RELATION_MIN_SHARED:
            continue
        score = idf_weighted_cosine(source_tokens, target_tokens, weights)
        if score < RELATION_MIN_SCORE:
            continue
        family = max(shared, key=lambda token: (weights.get(token, 1.0), token))
        divergent = sorted(source_tokens - target_tokens)
        relationship_type, reason = _relationship_for(
            target=target,
            score=score,
            shared=shared,
            family=family,
            divergent=divergent,
            markers=markers,
        )
        relations.append(
            {
                "relation_id": relation_identity(
                    source_id=source_id,
                    target_kind=target.target_kind,
                    target_id=target.target_id,
                    relationship_type=relationship_type,
                    shared=shared,
                    score=score,
                ),
                "source_id": source_id,
                "target_kind": target.target_kind,
                "target_id": target.target_id,
                "target_label": target.target_label,
                "relationship_type": relationship_type,
                "score": round(score, 4),
                "shared_tokens": shared[:8],
                "family_token": family,
                "reason": reason,
                "confidence": _confidence_for(score, len(shared)),
            }
        )
    relations.sort(key=lambda item: (-item["score"], item["target_label"].casefold(), item["target_id"]))
    return relations[:limit], coverage


def _relationship_for(
    *,
    target: RelationTarget,
    score: float,
    shared: list[str],
    family: str,
    divergent: list[str],
    markers: set[str],
) -> tuple[str, str]:
    label = target.target_label
    shared_str = ", ".join(shared[:5])
    rounded = round(score, 2)
    co_captured = target.target_kind == "co_captured_idea"
    context = " (captured together in this conversation)" if co_captured else ""

    # Markers may only reclassify when real overlap backs them (C13).
    if "contradiction" in markers and score >= MARKER_MIN_SCORE:
        return (
            "contradiction",
            f"Conflicts with '{label}'{context}: shares the goal '{family}' but the wording "
            f"proposes the opposite direction (contradiction marker, similarity {rounded}). "
            f"Needs a keep-or-supersede decision.",
        )
    if "experiment" in markers and score >= MARKER_MIN_SCORE:
        return (
            "experiment",
            f"An alternative approach to '{label}'{context} (experiment marker, similarity "
            f"{rounded}); same area '{family}', different method. Shared: {shared_str}.",
        )
    if score >= DUPLICATE_MIN_SCORE and len(shared) >= 3 and "continuation" not in markers:
        return (
            "duplicate",
            f"Near-identical to '{label}'{context} (similarity {rounded}; shared: {shared_str}). "
            f"Likely the same idea already captured - consider deduping.",
        )
    strong = score >= CONTINUATION_MIN_SCORE
    marker_continue = "continuation" in markers and score >= MARKER_MIN_SCORE
    mature_continue = (
        target.mature
        and score >= MATURE_CONTINUATION_MIN_SCORE
        and len(shared) >= MATURE_CONTINUATION_MIN_SHARED
    )
    if strong or marker_continue or mature_continue:
        driver = (
            "a continuation marker is present"
            if marker_continue
            else f"the overlap is strong ({rounded})"
            if strong
            else f"the prior work is established and the overlap is substantial ({rounded})"
        )
        return (
            "continuation",
            f"Extends existing work '{label}'{context} because {driver}. Shared: {shared_str}.",
        )
    divergent_str = ", ".join(divergent[:3]) or "a new angle"
    return (
        "sibling",
        f"Same family as '{label}'{context} via shared '{family}', but a different specific "
        f"focus ({divergent_str}). Shared: {shared_str}.",
    )


def proposal_for(relations: list[dict[str, Any]], *, tended_hint: bool = False) -> dict[str, Any]:
    """Map the top relation to a proposed workstream action with a reason.

    ``tended_hint`` feeds the divergence honesty note (mechanism M6): a fresh
    unrelated idea is only "healthy divergence" pending tending evidence.
    """

    if not relations:
        note = "" if tended_hint else " Divergence is healthy while it is tended; give it a next action."
        return {
            "proposal_kind": "new_independent_workstream",
            "recommended_action": "Start a fresh workstream; no related prior work was found." + note,
            "needs_human_decision": False,
            "divergence": True,
            "primary_relation_id": "",
        }
    top = relations[0]
    kind_by_type = {
        "duplicate": (
            "merge_or_dedupe",
            f"Likely a duplicate of '{top['target_label']}'. Point at the existing "
            "workstream instead of starting a new one.",
            False,
        ),
        "continuation": (
            "resume_existing",
            f"Resume and extend '{top['target_label']}' rather than opening a parallel branch.",
            False,
        ),
        "experiment": (
            "new_experiment_workstream",
            f"Open a separate experiment workstream linked to '{top['target_label']}' "
            "(same goal, different method).",
            False,
        ),
        "contradiction": (
            "new_workstream_flagged_conflict",
            f"Capture it, but flag the conflict with '{top['target_label']}' for a "
            "keep-or-supersede decision before doing overlapping work.",
            True,
        ),
        "sibling": (
            "new_sibling_workstream",
            f"Start a sibling workstream in the same family as '{top['target_label']}'.",
            False,
        ),
    }
    proposal_kind, recommended_action, needs_decision = kind_by_type[top["relationship_type"]]
    return {
        "proposal_kind": proposal_kind,
        "recommended_action": recommended_action,
        "needs_human_decision": needs_decision,
        "divergence": False,
        "primary_relation_id": top["relation_id"],
    }


def targets_from_portfolio_report(report: dict[str, Any]) -> list[RelationTarget]:
    """Relation targets from a Portfolio Attention V1 report (metadata only).

    The build-on-V1 join: project names, branch names, and commit subjects the
    read-only Git scan already produced, without re-scanning Git.
    """

    targets: list[RelationTarget] = []
    for project in report.get("projects", []):
        branch_terms = " ".join(
            f"{branch.get('name', '')} {branch.get('subject', '')}"
            for branch in project.get("branches", [])
        )
        text = f"{project.get('name', '')} {branch_terms}".strip()
        if not text:
            continue
        targets.append(
            RelationTarget(
                target_kind="portfolio_project",
                target_id=str(project.get("project_id", project.get("name", ""))),
                target_label=str(project.get("name", "project")),
                text=text,
                mature=True,
            )
        )
    return targets


__all__ = [
    "DEFAULT_RELATION_LIMIT",
    "RELATIONSHIP_TYPES",
    "RelationTarget",
    "classify_relations",
    "idea_tokens",
    "normalize_text",
    "proposal_for",
    "relation_identity",
    "short_label",
    "targets_from_portfolio_report",
]
