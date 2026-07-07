from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .ids import stable_id
from .models import (
    CounterfactualLessonRecord,
    LearningRulePromotionCandidateRecord,
    LearningRuleRecord,
    PriorityContentLessonReviewRecord,
)
from .transport import data_relative_path
from .utils import atomic_write_text, json_dumps, utc_now, write_jsonl

METHODOLOGY_VERSION = "priority-content-lesson-synthesis-v0.1"
AUTHORITY_BOUNDARY = (
    "Generated lesson candidates only. This command consumes bounded priority-content "
    "observations already written under `processed/`; it does not read source repos, call "
    "GitHub, call models, mutate downstream repos, install hooks, or promote lessons to truth."
)
PROMOTION_METHODOLOGY_VERSION = "learning-rule-promotion-candidate-v0.1"
PROMOTION_AUTHORITY_BOUNDARY = (
    "Generated learning-rule promotion candidates only. This command consumes generated lesson "
    "candidates and human review labels under `processed/`; it does not edit "
    "`registry/learning-rule-registry.json`, change preflight behavior, mutate source repos, "
    "or promote generated lessons to reviewed rules."
)
PROMOTION_HUMAN_GATES = [
    "Human must approve editing registry/learning-rule-registry.json.",
    "Human must verify applies_when, does_not_apply_when, and danger_if_ignored still match the target context.",
    "Run validate and roadmap check after any later registry edit.",
]

SIGNAL_LESSON_TEMPLATES: dict[str, dict[str, Any]] = {
    "ai_navigation": {
        "lesson": (
            "For similar repo work, read the repo-local AI navigation and operating contract "
            "before choosing implementation order or treating generated evidence as source truth."
        ),
        "context_tags": ["ai_navigation", "human_gate", "source_authority", "counterfactual_sequence"],
        "applies_when": [
            "An approved observation shows repo-local AI front doors, AGENTS/CLAUDE contracts, TOCs, or start-here docs.",
            "A future agent is planning or editing a repo with persistent AI navigation surfaces.",
        ],
        "does_not_apply_when": [
            "The repo has no observed AI navigation surface or the observed surface is stale/unreviewed boilerplate.",
            "The task is a trivial isolated command that does not rely on repo authority or future-agent routing.",
        ],
        "danger": (
            "Applied too broadly, stale navigation can override the actual source authority or add process "
            "overhead to small tasks."
        ),
        "better_order": [
            "Open the repo-local AI entrypoint or operating contract.",
            "Identify authority, stop conditions, and validation route.",
            "Use generated DAD evidence only as candidate context.",
            "Capture postflight lessons after the work changes behavior or reveals a reusable rule.",
        ],
        "risk": "medium",
    },
    "schema_contract": {
        "lesson": (
            "For similar structured-data work, identify schemas, contracts, and validators before "
            "changing record shapes, scoring, graph edges, or exports."
        ),
        "context_tags": ["schema_contract", "source_authority", "counterfactual_sequence"],
        "applies_when": [
            "Approved observations show schemas, validators, typed contracts, or contract tests.",
            "The task changes structured records, APIs, graph outputs, scoring metadata, or exports.",
        ],
        "does_not_apply_when": [
            "The work is exploratory prose or source reading with no structured output change.",
            "The observed schema is unrelated to the data shape being changed.",
        ],
        "danger": (
            "Applied too early, this can freeze premature structure; applied too broadly, it can make "
            "unrelated schemas look authoritative."
        ),
        "better_order": [
            "Find the controlling schema or contract.",
            "Find the validator or conformance test.",
            "Change implementation or generated output.",
            "Run the validator and record any methodology or score changes.",
        ],
        "risk": "medium",
    },
    "governance": {
        "lesson": (
            "For similar governance-sensitive work, resolve source authority, human gates, and privacy "
            "boundaries before expanding automation or cross-repo reuse."
        ),
        "context_tags": [
            "source_authority",
            "human_gate",
            "load_bearing_decision",
            "counterfactual_sequence",
        ],
        "applies_when": [
            "Approved observations show authority, privacy, governance, gate, or source-of-truth language.",
            "The task can affect downstream repos, scan scope, public safety, or future-agent defaults.",
        ],
        "does_not_apply_when": [
            "The change is generated-only local reporting with no source-boundary or downstream effect.",
            "A reviewed gate already covers the exact same authority decision.",
        ],
        "danger": (
            "If stripped from context, this can either block safe local reporting or allow broad automation "
            "to proceed on a weak gate."
        ),
        "better_order": [
            "Identify source authority and privacy boundary.",
            "Classify the decision risk tier.",
            "Run human/fresh-eyes gate when the decision is load-bearing.",
            "Only then automate, extract, or reuse across repos.",
        ],
        "risk": "high",
    },
    "learning_loop": {
        "lesson": (
            "For similar asset-use or repo-work tasks, capture before/after learning events so future "
            "agents can reuse the asset with context instead of rediscovering the same rule."
        ),
        "context_tags": ["asset_use_pay_forward", "human_gate", "counterfactual_sequence"],
        "applies_when": [
            "Approved observations show repo learning-loop files, lesson capture, handoff, or pay-forward guidance.",
            "An agent materially uses an asset, fixes a non-trivial issue, or learns a reusable workflow constraint.",
        ],
        "does_not_apply_when": [
            "The asset was only glanced at and did not influence the work.",
            "The task is trivial and lesson capture would add more noise than future value.",
        ],
        "danger": (
            "Overused learning capture creates noisy logs; under-contextualized events can mislead future agents."
        ),
        "better_order": [
            "Record expected asset use before material work when feasible.",
            "Record failures or dependency-order lessons during the work.",
            "Record actual usefulness and missing parts after the work.",
            "Keep the lesson candidate until human review or repeated evidence supports promotion.",
        ],
        "risk": "medium",
    },
    "workflow_dataflow": {
        "lesson": (
            "For similar workflow or dataflow work, map inputs, transformations, validations, and outputs "
            "before recombining assets into a new workflow."
        ),
        "context_tags": ["data_normalization", "dependency_ordering", "counterfactual_sequence"],
        "applies_when": [
            "Approved observations show workflow, dataflow, normalization, pipeline, migration, or chunking language.",
            "The task composes multiple assets or changes how data moves through a repo.",
        ],
        "does_not_apply_when": [
            "The task does not change data shape, dependency order, or workflow composition.",
            "The observed workflow language is only a filename convention without supporting content signals.",
        ],
        "danger": (
            "Applied without evidence, this can invent dataflow that the source repo does not actually own."
        ),
        "better_order": [
            "Identify inputs and source authority.",
            "Identify transformations and normalization rules.",
            "Identify validators, gates, and output contracts.",
            "Only then compose or automate the workflow.",
        ],
        "risk": "medium",
    },
}


def load_priority_content_observations(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"Priority content observations file does not exist: {path}")
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
    if not records:
        raise ValueError(f"Priority content observations file is empty: {path}")
    return records


def load_priority_content_lesson_candidates(path: Path) -> list[CounterfactualLessonRecord]:
    if not path.exists():
        raise ValueError(f"Priority content lesson candidate file does not exist: {path}")
    records: list[CounterfactualLessonRecord] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(CounterfactualLessonRecord.model_validate_json(line))
        except Exception as exc:
            raise ValueError(f"Invalid lesson candidate at {path}:{line_number}: {exc}") from exc
    if not records:
        raise ValueError(f"Priority content lesson candidate file is empty: {path}")
    return records


def load_priority_content_lesson_reviews(path: Path) -> list[PriorityContentLessonReviewRecord]:
    if not path.exists():
        raise ValueError(f"Priority content lesson review file does not exist: {path}")
    reviews: list[PriorityContentLessonReviewRecord] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            reviews.append(PriorityContentLessonReviewRecord.model_validate_json(line))
        except Exception as exc:
            raise ValueError(f"Invalid lesson review at {path}:{line_number}: {exc}") from exc
    return reviews


def _confidence(count: int) -> str:
    if count >= 3:
        return "high"
    if count == 2:
        return "medium"
    return "low"


def build_priority_content_lesson_candidates(
    observations: list[dict[str, Any]],
    *,
    scan_id: str,
    min_observations: int = 1,
    limit: int = 100,
    generated_at: str | None = None,
) -> list[CounterfactualLessonRecord]:
    if min_observations < 1:
        raise ValueError("min_observations must be at least 1.")
    generated = generated_at or utc_now()
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        repo_key = str(observation.get("repo_key") or "").strip()
        if not repo_key:
            continue
        for signal_tag in observation.get("signal_tags") or []:
            if signal_tag in SIGNAL_LESSON_TEMPLATES:
                groups[(repo_key, signal_tag)].append(observation)

    records: list[CounterfactualLessonRecord] = []
    for (repo_key, signal_tag), group in sorted(groups.items()):
        if len(group) < min_observations:
            continue
        template = SIGNAL_LESSON_TEMPLATES[signal_tag]
        evidence_asset_ids = sorted(
            {
                str(item.get("asset_id"))
                for item in group
                if str(item.get("asset_id") or "").strip()
            }
        )
        source_events = sorted(
            {
                str(item.get("observation_id"))
                for item in group
                if str(item.get("observation_id") or "").strip()
            }
        )
        if not source_events:
            continue
        records.append(
            CounterfactualLessonRecord(
                lesson_candidate_id=stable_id("priority-content-lesson", repo_key, signal_tag, scan_id),
                lesson_candidate=f"{repo_key}: {template['lesson']}",
                applies_when=list(template["applies_when"]),
                does_not_apply_when=list(template["does_not_apply_when"]),
                danger_if_misapplied=str(template["danger"]),
                counterfactual_better_order=list(template["better_order"]),
                evidence_asset_ids=evidence_asset_ids,
                source_events=source_events,
                context_tags=list(template["context_tags"]),
                confidence=_confidence(len(group)),  # type: ignore[arg-type]
                risk=str(template["risk"]),  # type: ignore[arg-type]
                authority_boundary=AUTHORITY_BOUNDARY,
                generated_at=generated,
                scan_id=scan_id,
            )
        )
        if len(records) >= limit:
            break
    return records


def lesson_synthesis_summary(records: list[CounterfactualLessonRecord]) -> dict[str, Any]:
    tag_counts: Counter[str] = Counter()
    risk_counts: Counter[str] = Counter()
    confidence_counts: Counter[str] = Counter()
    for record in records:
        tag_counts.update(record.context_tags)
        risk_counts[record.risk] += 1
        confidence_counts[record.confidence] += 1
    return {
        "lesson_candidate_count": len(records),
        "context_tag_counts": dict(sorted(tag_counts.items())),
        "risk_counts": dict(sorted(risk_counts.items())),
        "confidence_counts": dict(sorted(confidence_counts.items())),
    }


def priority_content_lessons_markdown(records: list[CounterfactualLessonRecord]) -> str:
    summary = lesson_synthesis_summary(records)
    lines = [
        "# Priority Content Lesson Candidates",
        "",
        AUTHORITY_BOUNDARY,
        "",
        f"- Lesson candidates: **{summary['lesson_candidate_count']}**",
        "",
        "## Counts",
        "",
        f"- Risk counts: `{summary['risk_counts']}`",
        f"- Confidence counts: `{summary['confidence_counts']}`",
        "",
        "## Candidates",
        "",
    ]
    for record in records:
        lines.extend(
            [
                f"### {record.lesson_candidate_id}",
                "",
                f"- Lesson: {record.lesson_candidate}",
                f"- Risk: `{record.risk}`",
                f"- Confidence: `{record.confidence}`",
                f"- Context tags: `{record.context_tags}`",
                f"- Source events: **{len(record.source_events)}**",
                f"- Evidence assets: **{len(record.evidence_asset_ids)}**",
                f"- Danger if misapplied: {record.danger_if_misapplied}",
                "- Applies when:",
            ]
        )
        for item in record.applies_when:
            lines.append(f"  - {item}")
        lines.append("- Does not apply when:")
        for item in record.does_not_apply_when:
            lines.append(f"  - {item}")
        lines.append("")
    lines.extend(
        [
            "## Red-Team",
            "",
            "- These records are generated lesson candidates, not reviewed learning rules.",
            "- Observation excerpts are source-derived generated evidence and can be incomplete.",
            "- Human review is required before any candidate influences preflight defaults or repo automation.",
            "",
        ]
    )
    return "\n".join(lines)


def write_priority_content_lesson_outputs(
    repo_root: Path,
    *,
    observations_file: Path | None = None,
    scan_id: str,
    min_observations: int = 1,
    limit: int = 100,
    generated_at: str | None = None,
) -> dict[str, Any]:
    observations_path = observations_file or (
        data_relative_path(
            repo_root, Path("processed") / "learning" / "priority_content_observations.jsonl"
        )
    )
    if not observations_path.is_absolute():
        observations_path = data_relative_path(repo_root, observations_path)
    records = build_priority_content_lesson_candidates(
        load_priority_content_observations(observations_path),
        scan_id=scan_id,
        min_observations=min_observations,
        limit=limit,
        generated_at=generated_at,
    )
    if not records:
        raise ValueError("No lesson candidates were generated from the provided observations.")
    learning_dir = data_relative_path(repo_root, Path("processed") / "learning")
    reports_dir = data_relative_path(repo_root, Path("processed") / "reports")
    paths = {
        "lesson_candidates": learning_dir / "priority_content_lesson_candidates.jsonl",
        "report_markdown": reports_dir / "priority_content_lesson_candidates.md",
        "report_json": reports_dir / "priority_content_lesson_candidates.json",
    }
    write_jsonl(paths["lesson_candidates"], [record.model_dump(mode="json") for record in records])
    payload = {
        "methodology_version": METHODOLOGY_VERSION,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "observations_file": str(observations_path),
        "summary": lesson_synthesis_summary(records),
        "lesson_candidates": [record.model_dump(mode="json") for record in records],
        "review_status": "generated_candidate",
    }
    atomic_write_text(paths["report_markdown"], priority_content_lessons_markdown(records))
    atomic_write_text(paths["report_json"], json_dumps(payload, pretty=True) + "\n")
    return {
        "output_type": "generated_candidate_lessons",
        "review_status": "generated_candidate",
        "summary": payload["summary"],
        "outputs": {key: str(path) for key, path in paths.items()},
    }


def build_priority_content_lesson_review_template(
    candidates: list[CounterfactualLessonRecord],
    *,
    sample_size: int = 100,
) -> list[PriorityContentLessonReviewRecord]:
    if sample_size < 1:
        raise ValueError("sample_size must be at least 1.")
    ranked = sorted(
        candidates,
        key=lambda record: (
            {"high": 0, "medium": 1, "low": 2}.get(record.risk, 3),
            {"high": 0, "medium": 1, "low": 2}.get(record.confidence, 3),
            record.lesson_candidate_id,
        ),
    )[:sample_size]
    reviews: list[PriorityContentLessonReviewRecord] = []
    for index, candidate in enumerate(ranked, start=1):
        sample_id = f"priority-content-lesson-review-{index:03d}"
        reviews.append(
            PriorityContentLessonReviewRecord(
                review_id=stable_id(
                    "priority-content-lesson-review",
                    sample_id,
                    candidate.lesson_candidate_id,
                ),
                sample_id=sample_id,
                lesson_candidate_id=candidate.lesson_candidate_id,
                evidence={
                    "methodology_version": METHODOLOGY_VERSION,
                    "candidate_risk": candidate.risk,
                    "candidate_confidence": candidate.confidence,
                    "lesson_candidate": candidate.lesson_candidate,
                    "applies_when": candidate.applies_when,
                    "does_not_apply_when": candidate.does_not_apply_when,
                    "danger_if_misapplied": candidate.danger_if_misapplied,
                    "counterfactual_better_order": candidate.counterfactual_better_order,
                    "context_tags": candidate.context_tags,
                    "source_events": candidate.source_events,
                    "evidence_asset_ids": candidate.evidence_asset_ids,
                    "generated_candidate_only": True,
                },
            )
        )
    return reviews


def _review_is_pending(review: PriorityContentLessonReviewRecord) -> bool:
    return (
        review.applicability == "unreviewed"
        and review.usefulness == "unreviewed"
        and review.safety == "unreviewed"
        and review.actionability == "unreviewed"
        and review.decision == "pending"
        and not any(
            [
                review.notes,
                review.false_positive_reason,
                review.missing_context_note,
                review.useful_example_note,
                review.promotion_blocker_note,
            ]
        )
    )


def summarize_priority_content_lesson_reviews(
    reviews: list[PriorityContentLessonReviewRecord],
) -> dict[str, Any]:
    reviewed = [review for review in reviews if not _review_is_pending(review)]
    accepted = [review for review in reviewed if review.decision == "accept_for_review_use"]
    rejected = [review for review in reviewed if review.decision == "reject_candidate"]
    return {
        "template_count": len(reviews),
        "reviewed_count": len(reviewed),
        "pending_count": len(reviews) - len(reviewed),
        "accepted_for_review_use_count": len(accepted),
        "rejected_count": len(rejected),
        "applicability_counts": dict(Counter(review.applicability for review in reviews)),
        "usefulness_counts": dict(Counter(review.usefulness for review in reviews)),
        "safety_counts": dict(Counter(review.safety for review in reviews)),
        "actionability_counts": dict(Counter(review.actionability for review in reviews)),
        "decision_counts": dict(Counter(review.decision for review in reviews)),
        "false_positive_note_count": sum(1 for review in reviews if review.false_positive_reason),
        "missing_context_note_count": sum(1 for review in reviews if review.missing_context_note),
        "useful_example_note_count": sum(1 for review in reviews if review.useful_example_note),
        "promotion_blocker_note_count": sum(1 for review in reviews if review.promotion_blocker_note),
        "promotion_gate_complete": False,
        "authority_boundary": (
            "Review records are labels for generated candidates only; they do not promote "
            "lessons to deterministic learning rules."
        ),
    }


def priority_content_lesson_review_markdown(
    reviews: list[PriorityContentLessonReviewRecord],
    *,
    review_sample: int = 50,
) -> str:
    summary = summarize_priority_content_lesson_reviews(reviews)
    lines = [
        "# Priority Content Lesson Review Template",
        "",
        "Generated review queue only. Human labels are required before any candidate lesson is reused.",
        "",
        f"- Template count: **{summary['template_count']}**",
        f"- Reviewed count: **{summary['reviewed_count']}**",
        "",
    ]
    for review in reviews[:review_sample]:
        evidence = review.evidence
        lines.extend(
            [
                f"## {review.sample_id}",
                "",
                f"- Lesson id: `{review.lesson_candidate_id}`",
                f"- Risk: `{evidence.get('candidate_risk', '')}`",
                f"- Confidence: `{evidence.get('candidate_confidence', '')}`",
                f"- Lesson: {evidence.get('lesson_candidate', '')}",
                f"- Context tags: `{evidence.get('context_tags', [])}`",
                f"- Danger if misapplied: {evidence.get('danger_if_misapplied', '')}",
                "",
            ]
        )
    return "\n".join(lines)


def write_priority_content_lesson_review_template_outputs(
    repo_root: Path,
    candidates: list[CounterfactualLessonRecord],
    *,
    sample_size: int = 100,
) -> dict[str, Any]:
    reviews = build_priority_content_lesson_review_template(candidates, sample_size=sample_size)
    learning_dir = data_relative_path(repo_root, Path("processed") / "learning")
    reports_dir = data_relative_path(repo_root, Path("processed") / "reports")
    paths = {
        "review_template": learning_dir / "priority_content_lesson_review_template.jsonl",
        "review_report": reports_dir / "priority_content_lesson_review_template.md",
        "review_summary": reports_dir / "priority_content_lesson_review_summary.json",
    }
    write_jsonl(paths["review_template"], [review.model_dump(mode="json") for review in reviews])
    atomic_write_text(paths["review_report"], priority_content_lesson_review_markdown(reviews))
    atomic_write_text(
        paths["review_summary"],
        json_dumps(summarize_priority_content_lesson_reviews(reviews), pretty=True) + "\n",
    )
    return {
        "output_type": "generated_candidate_review_template",
        "review_status": "generated_candidate",
        "summary": summarize_priority_content_lesson_reviews(reviews),
        "outputs": {key: str(path) for key, path in paths.items()},
    }


def build_priority_content_lesson_review_queue(
    reviews: list[PriorityContentLessonReviewRecord],
    *,
    status: str = "pending",
    limit: int = 10,
) -> dict[str, Any]:
    if status not in {"pending", "reviewed", "all"}:
        raise ValueError("status must be one of: pending, reviewed, all")
    selected: list[PriorityContentLessonReviewRecord] = []
    for review in reviews:
        pending = _review_is_pending(review)
        if status == "pending" and not pending:
            continue
        if status == "reviewed" and pending:
            continue
        selected.append(review)
        if len(selected) >= limit:
            break
    return {
        "status": status,
        "limit": limit,
        "count": len(selected),
        "items": [review.model_dump(mode="json") for review in selected],
        "summary": summarize_priority_content_lesson_reviews(reviews),
    }


def update_priority_content_lesson_review_record(
    reviews: list[PriorityContentLessonReviewRecord],
    *,
    sample_id: str | None = None,
    lesson_candidate_id: str | None = None,
    reviewer: str | None = None,
    applicability: str | None = None,
    usefulness: str | None = None,
    safety: str | None = None,
    actionability: str | None = None,
    decision: str | None = None,
    notes: str | None = None,
    false_positive_reason: str | None = None,
    missing_context_note: str | None = None,
    useful_example_note: str | None = None,
    promotion_blocker_note: str | None = None,
    reviewed_at: str | None = None,
) -> tuple[list[PriorityContentLessonReviewRecord], PriorityContentLessonReviewRecord]:
    matches = [
        review
        for review in reviews
        if (sample_id and review.sample_id == sample_id)
        or (lesson_candidate_id and review.lesson_candidate_id == lesson_candidate_id)
    ]
    if not sample_id and not lesson_candidate_id:
        raise ValueError("sample_id or lesson_candidate_id is required.")
    if not matches:
        raise ValueError("No matching priority content lesson review record found.")
    if len(matches) > 1:
        raise ValueError("Multiple matching review records found; use sample_id.")
    target = matches[0]
    updates = {
        key: value
        for key, value in {
            "reviewer": reviewer,
            "applicability": applicability,
            "usefulness": usefulness,
            "safety": safety,
            "actionability": actionability,
            "decision": decision,
            "notes": notes,
            "false_positive_reason": false_positive_reason,
            "missing_context_note": missing_context_note,
            "useful_example_note": useful_example_note,
            "promotion_blocker_note": promotion_blocker_note,
        }.items()
        if value is not None
    }
    if updates and "reviewed_at" not in updates:
        updates["reviewed_at"] = reviewed_at or utc_now()
    updated = target.model_copy(update=updates)
    updated.review_status = "reviewed" if not _review_is_pending(updated) else "generated_candidate"
    validated = PriorityContentLessonReviewRecord.model_validate(updated.model_dump(mode="json"))
    return [validated if review.review_id == target.review_id else review for review in reviews], validated


def update_priority_content_lesson_review_file(
    path: Path,
    **kwargs: Any,
) -> tuple[PriorityContentLessonReviewRecord, dict[str, Any]]:
    reviews = load_priority_content_lesson_reviews(path)
    updated_reviews, updated = update_priority_content_lesson_review_record(reviews, **kwargs)
    write_jsonl(path, [review.model_dump(mode="json") for review in updated_reviews])
    return updated, summarize_priority_content_lesson_reviews(updated_reviews)


def _shorten(value: str, limit: int = 320) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _promotion_blockers(
    review: PriorityContentLessonReviewRecord,
    candidate: CounterfactualLessonRecord | None,
) -> tuple[str, list[str]]:
    blockers: list[str] = []
    missing: list[str] = []
    if candidate is None:
        blockers.append("No matching lesson candidate was found for the review record.")
    if review.review_status != "reviewed":
        missing.append("Human review is incomplete.")
    expected = {
        "applicability": ("valid_context", review.applicability),
        "usefulness": ("useful", review.usefulness),
        "safety": ("safe", review.safety),
        "actionability": ("actionable", review.actionability),
        "decision": ("accept_for_review_use", review.decision),
    }
    for field, (wanted, observed) in expected.items():
        if observed == "unreviewed" or observed == "pending":
            missing.append(f"{field} is still {observed}.")
        elif observed != wanted:
            blockers.append(f"{field} is {observed}, not {wanted}.")
    if review.false_positive_reason:
        blockers.append(f"False-positive note present: {review.false_positive_reason}")
    if review.promotion_blocker_note:
        blockers.append(f"Promotion blocker note present: {review.promotion_blocker_note}")
    if blockers:
        return "blocked", blockers + missing
    if missing:
        return "needs_more_evidence", missing
    return "eligible_for_human_promotion", []


def _proposed_learning_rule(
    candidate: CounterfactualLessonRecord,
    review: PriorityContentLessonReviewRecord,
) -> LearningRuleRecord:
    trigger_terms = sorted(
        {
            "lesson-review",
            "priority-content",
            *candidate.context_tags,
        }
    )
    evidence = [
        candidate.lesson_candidate_id,
        review.review_id,
        *candidate.source_events[:10],
        *candidate.evidence_asset_ids[:10],
    ]
    return LearningRuleRecord(
        rule_id=stable_id("learning-rule", candidate.lesson_candidate_id),
        title=_shorten(candidate.lesson_candidate.split(":", 1)[-1].strip(), 96)
        or "Candidate rule from priority content lesson",
        summary=_shorten(candidate.lesson_candidate),
        trigger_terms=trigger_terms,
        trigger_path_patterns=[],
        context_tags=list(candidate.context_tags),
        applies_when=list(candidate.applies_when),
        does_not_apply_when=list(candidate.does_not_apply_when),
        required_actions=list(candidate.counterfactual_better_order),
        danger_if_ignored=candidate.danger_if_misapplied,
        evidence=evidence,
        enforcement_level="surface",
        review_status="generated_candidate",
    )


def build_learning_rule_promotion_candidates(
    candidates: list[CounterfactualLessonRecord],
    reviews: list[PriorityContentLessonReviewRecord],
    *,
    scan_id: str,
    limit: int = 100,
    generated_at: str | None = None,
) -> list[LearningRulePromotionCandidateRecord]:
    if limit < 1:
        raise ValueError("limit must be at least 1.")
    generated = generated_at or utc_now()
    by_candidate_id = {candidate.lesson_candidate_id: candidate for candidate in candidates}
    records: list[LearningRulePromotionCandidateRecord] = []
    for review in sorted(reviews, key=lambda item: (item.sample_id, item.lesson_candidate_id)):
        if len(records) >= limit:
            break
        candidate = by_candidate_id.get(review.lesson_candidate_id)
        readiness, blockers = _promotion_blockers(review, candidate)
        if candidate is None:
            fallback_rule = LearningRuleRecord(
                rule_id=stable_id("learning-rule", review.lesson_candidate_id),
                title="Blocked candidate from missing lesson record",
                summary="Blocked because the reviewed lesson candidate could not be found.",
                trigger_terms=["priority-content", "lesson-review"],
                trigger_path_patterns=[],
                context_tags=["human_gate"],
                applies_when=["The missing lesson candidate is recovered and reviewed."],
                does_not_apply_when=["The lesson candidate cannot be found or verified."],
                required_actions=["Recover the source lesson candidate before promotion."],
                danger_if_ignored="A rule could be promoted without its source lesson context.",
                evidence=[review.review_id],
                enforcement_level="surface",
                review_status="generated_candidate",
            )
            evidence = {"methodology_version": PROMOTION_METHODOLOGY_VERSION}
        else:
            fallback_rule = _proposed_learning_rule(candidate, review)
            evidence = {
                "methodology_version": PROMOTION_METHODOLOGY_VERSION,
                "candidate_risk": candidate.risk,
                "candidate_confidence": candidate.confidence,
                "review_decision": review.decision,
                "reviewer": review.reviewer,
                "reviewed_at": review.reviewed_at,
                "generated_candidate_only": True,
            }
        records.append(
            LearningRulePromotionCandidateRecord(
                promotion_candidate_id=stable_id(
                    "learning-rule-promotion-candidate",
                    review.review_id,
                    review.lesson_candidate_id,
                    scan_id,
                ),
                source_lesson_candidate_id=review.lesson_candidate_id,
                source_review_id=review.review_id,
                proposed_rule=fallback_rule,
                promotion_readiness=readiness,  # type: ignore[arg-type]
                blockers=blockers,
                required_human_gates=list(PROMOTION_HUMAN_GATES),
                registry_mutated=False,
                authority_boundary=PROMOTION_AUTHORITY_BOUNDARY,
                evidence=evidence,
                generated_at=generated,
                scan_id=scan_id,
            )
        )
    return records


def learning_rule_promotion_summary(
    records: list[LearningRulePromotionCandidateRecord],
) -> dict[str, Any]:
    readiness_counts = Counter(record.promotion_readiness for record in records)
    return {
        "promotion_candidate_count": len(records),
        "readiness_counts": dict(sorted(readiness_counts.items())),
        "eligible_for_human_promotion_count": readiness_counts.get(
            "eligible_for_human_promotion", 0
        ),
        "blocked_count": readiness_counts.get("blocked", 0),
        "needs_more_evidence_count": readiness_counts.get("needs_more_evidence", 0),
        "registry_mutated": False,
        "authority_boundary": PROMOTION_AUTHORITY_BOUNDARY,
    }


def learning_rule_promotion_markdown(
    records: list[LearningRulePromotionCandidateRecord],
) -> str:
    summary = learning_rule_promotion_summary(records)
    lines = [
        "# Learning Rule Promotion Candidates",
        "",
        PROMOTION_AUTHORITY_BOUNDARY,
        "",
        f"- Promotion candidates: **{summary['promotion_candidate_count']}**",
        f"- Readiness counts: `{summary['readiness_counts']}`",
        f"- Registry mutated: `{summary['registry_mutated']}`",
        "",
        "## Human Gates",
        "",
    ]
    for gate in PROMOTION_HUMAN_GATES:
        lines.append(f"- {gate}")
    lines.extend(["", "## Candidates", ""])
    for record in records:
        rule = record.proposed_rule
        lines.extend(
            [
                f"### {record.promotion_candidate_id}",
                "",
                f"- Readiness: `{record.promotion_readiness}`",
                f"- Source lesson: `{record.source_lesson_candidate_id}`",
                f"- Source review: `{record.source_review_id}`",
                f"- Proposed rule id: `{rule.rule_id}`",
                f"- Proposed title: {rule.title}",
                f"- Enforcement if later promoted: `{rule.enforcement_level}`",
                f"- Registry mutated now: `{record.registry_mutated}`",
            ]
        )
        if record.blockers:
            lines.append("- Blockers:")
            for blocker in record.blockers:
                lines.append(f"  - {blocker}")
        lines.append("- Applies when:")
        for item in rule.applies_when:
            lines.append(f"  - {item}")
        lines.append("- Does not apply when:")
        for item in rule.does_not_apply_when:
            lines.append(f"  - {item}")
        lines.append(f"- Danger if ignored: {rule.danger_if_ignored}")
        lines.append("")
    lines.extend(
        [
            "## Red-Team",
            "",
            "- Accepted review-use labels are not enough to mutate deterministic learning rules.",
            "- A proposed rule can still be too broad when moved into a different repo context.",
            "- Human review must verify the exact applies/does-not-apply boundary before any registry edit.",
            "",
        ]
    )
    return "\n".join(lines)


def write_learning_rule_promotion_candidate_outputs(
    repo_root: Path,
    candidates: list[CounterfactualLessonRecord],
    reviews: list[PriorityContentLessonReviewRecord],
    *,
    scan_id: str,
    limit: int = 100,
    generated_at: str | None = None,
) -> dict[str, Any]:
    records = build_learning_rule_promotion_candidates(
        candidates,
        reviews,
        scan_id=scan_id,
        limit=limit,
        generated_at=generated_at,
    )
    if not records:
        raise ValueError("No learning-rule promotion candidates were generated.")
    learning_dir = data_relative_path(repo_root, Path("processed") / "learning")
    reports_dir = data_relative_path(repo_root, Path("processed") / "reports")
    paths = {
        "promotion_candidates": learning_dir / "learning_rule_promotion_candidates.jsonl",
        "report_markdown": reports_dir / "learning_rule_promotion_candidates.md",
        "report_json": reports_dir / "learning_rule_promotion_candidates.json",
    }
    write_jsonl(paths["promotion_candidates"], [record.model_dump(mode="json") for record in records])
    payload = {
        "methodology_version": PROMOTION_METHODOLOGY_VERSION,
        "authority_boundary": PROMOTION_AUTHORITY_BOUNDARY,
        "summary": learning_rule_promotion_summary(records),
        "promotion_candidates": [record.model_dump(mode="json") for record in records],
        "review_status": "generated_candidate",
    }
    atomic_write_text(paths["report_markdown"], learning_rule_promotion_markdown(records))
    atomic_write_text(paths["report_json"], json_dumps(payload, pretty=True) + "\n")
    return {
        "output_type": "generated_learning_rule_promotion_candidates",
        "review_status": "generated_candidate",
        "summary": payload["summary"],
        "outputs": {key: str(path) for key, path in paths.items()},
    }
