from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .ids import stable_id
from .models import CounterfactualLessonRecord
from .utils import atomic_write_text, json_dumps, utc_now, write_jsonl

METHODOLOGY_VERSION = "priority-content-lesson-synthesis-v0.1"
AUTHORITY_BOUNDARY = (
    "Generated lesson candidates only. This command consumes bounded priority-content "
    "observations already written under `processed/`; it does not read source repos, call "
    "GitHub, call models, mutate downstream repos, install hooks, or promote lessons to truth."
)

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
        repo_root / "processed" / "learning" / "priority_content_observations.jsonl"
    )
    if not observations_path.is_absolute():
        observations_path = repo_root / observations_path
    records = build_priority_content_lesson_candidates(
        load_priority_content_observations(observations_path),
        scan_id=scan_id,
        min_observations=min_observations,
        limit=limit,
        generated_at=generated_at,
    )
    if not records:
        raise ValueError("No lesson candidates were generated from the provided observations.")
    learning_dir = repo_root / "processed" / "learning"
    reports_dir = repo_root / "processed" / "reports"
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
