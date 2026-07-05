# Lesson Lifecycle Governance

Status: candidate design, not enforced.

DAD lessons are append-only evidence first. A lesson can later become more useful,
less useful, superseded, or archived, but that lifecycle decision should be a
review overlay on top of the original lesson rather than a rewrite of the raw
lesson.

## Problem

The current lesson record has `created_at`, `confidence`, and `review_status`.
That is enough to capture a lesson, but not enough to manage it over time.

DAD needs a future lifecycle layer so agents can ask:

- Is this lesson still useful?
- Should it be upgraded into a stronger rule, harness, template, or asset?
- Should it be downgraded because it is noisy, stale, too narrow, or harmful?
- Has another lesson replaced it?
- When should DAD check it again?

This design is intentionally non-enforced until DAD has enough reviewed examples.

## Source Boundary

Raw lesson records remain immutable candidate evidence. Lifecycle records may
classify, supersede, improve, or archive a lesson, but they must not delete or
silently edit the original lesson.

Lifecycle labels are not proof of truth or value. They are review state and
routing metadata.

## Future Metadata Shape

When DAD is ready to implement this, add a lifecycle overlay record rather than
changing all historical lesson rows in place.

Candidate fields:

```json
{
  "schema_version": "0.1.0",
  "lifecycle_record_id": "dad:lesson-lifecycle:<id>",
  "lesson_id": "dad:lesson:<id>",
  "created_at": "2026-07-04T00:00:00Z",
  "last_reviewed_at": null,
  "next_review_due_at": "2026-08-04T00:00:00Z",
  "review_cadence": "monthly",
  "lifecycle_status": "candidate",
  "review_status": "candidate",
  "review_reason": "new_lesson",
  "evidence_summary": {
    "reuse_count": 0,
    "helped_count": 0,
    "failed_count": 0,
    "harmful_count": 0,
    "contradiction_count": 0,
    "superseding_lesson_count": 0
  },
  "recommended_action": "watch",
  "supersedes": [],
  "superseded_by": [],
  "improvement_notes": [],
  "archive_reason": null,
  "authority_boundary": "Lifecycle metadata is candidate review state and does not rewrite the source lesson."
}
```

Suggested `lifecycle_status` values:

- `candidate`: captured, not reviewed enough to rely on.
- `watch`: plausible and worth checking after more uses.
- `review_use`: useful for review context, but not a rule.
- `promote_candidate`: enough signal to propose a rule, harness, template, or asset.
- `promoted`: promoted by a separate reviewed gate.
- `improve`: keep the lesson, but revise applicability, avoid-when, or danger notes.
- `downgrade`: lesson is too broad, noisy, stale, weak, or less useful than expected.
- `superseded`: a newer lesson or asset replaces it.
- `archived`: kept for audit/history but normally hidden from preflight recommendations.
- `rejected`: reviewed and should not guide future work.

Suggested `review_reason` values:

- `new_lesson`
- `scheduled_review`
- `repeated_reuse`
- `failed_reuse`
- `harmful_reuse`
- `contradicted_by_new_evidence`
- `source_changed`
- `asset_upgraded`
- `duplicate_or_variant`
- `superseded_by_better_lesson`
- `human_review`

## Review Cadence

Initial candidate cadence:

- High-risk or governance lessons: review after 7 days or 2 material uses.
- Coding, test, and workflow lessons: review after 30 days or 3 material uses.
- Narrow one-off lessons: review after 90 days or when reused.
- Archived/superseded lessons: review only when referenced again or when their parent
  asset changes.

These cadences are defaults for later design, not current enforcement.

## Upgrade Signals

Upgrade a lesson only when there is reviewed evidence such as:

- independent reuse in more than one task or repo;
- validated fix outcomes tied to the lesson;
- a harness or synthetic test showing the lesson prevents a real failure mode;
- repeated postflight feedback that the lesson saved time, reduced risk, or
  prevented false confidence;
- a clear path into a DAD asset, harness, template, skill, non-negotiable, or
  learning rule.

Upgrade should produce a proposal, not silently mutate guidance.

## Downgrade And Archive Signals

Downgrade or archive when:

- the lesson depends on a stale tool, schema, prompt, repo shape, or source;
- later evidence contradicts it;
- it was useful only in a narrow context and is being over-applied;
- it causes noisy preflight recommendations;
- it duplicates a stronger lesson or reviewed asset;
- it lacks `applies_when`, `does_not_apply_when`, or `danger_if_misapplied`;
- it was harmful, misleading, or created false confidence.

Archive should hide the lesson from normal recommendation paths while preserving
the audit trail.

## Future Queues And Commands

Possible generated surfaces:

```text
processed/learning/lesson_lifecycle_records.jsonl
processed/reports/lesson_lifecycle_review.md
processed/reports/lesson_lifecycle_review.json
```

Possible future commands:

```text
asset-dir lesson lifecycle queue
asset-dir lesson lifecycle review --lesson-id <id> --decision watch|improve|downgrade|archive|supersede|promote-candidate
asset-dir lesson lifecycle report
```

The first implementation should be advisory. It should not block preflight until
DAD has reviewed examples and tests.

## Tests To Add Later

- A raw lesson remains unchanged after lifecycle review.
- A lifecycle record can mark a lesson as superseded without deleting it.
- Archived lessons are excluded from normal recommendations but still searchable.
- Lessons missing applicability or danger notes are routed to `improve`, not
  automatically promoted.
- Harmful or failed reuse pushes a lesson toward `downgrade` or `archive`.
- Small sample sizes report counts, not fake-confidence percentages.
- A promoted lifecycle decision requires a separate human-reviewed promotion gate.

## Premortem

Failure story: DAD captures many lessons, treats them all as equally current, and
future agents keep seeing stale or over-broad guidance. A once-useful lesson
becomes a default, then blocks better approaches or spreads false confidence
across repos. The fix is to keep raw lessons immutable and add a reviewed lifecycle
overlay with review clocks, downgrade paths, supersession links, and archive
behavior.
