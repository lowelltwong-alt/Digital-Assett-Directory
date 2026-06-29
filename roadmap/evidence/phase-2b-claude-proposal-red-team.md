# Phase 2B Claude Proposal Red Team

Date: 2026-06-26. Reviewer: Claude Code (independent, read-only). Status: candidate evidence
only. No labels changed, no generated JSONL edited, no roadmap phase marked complete, no source
or scanned repos mutated, GitHub scanning not enabled. Preflight session:
`dad:session:13fe1bf1-39a9-4689-9298-ed6699bfa297`.

## Verdict

**Conditional.** The individual labels are mostly defensible and the safety posture is intact
(every proposal is candidate-only with an authority boundary; nothing implies source mutation
or truth promotion). The human review showed good judgment (it caught the bundling gap on
`review-041` and correctly deferred the Mock Trial proposal on `review-009`). **But the
calibration *evidence* is biased by two structural artifacts that make the headline comparison
misleading, so it should not yet be used to decide engine policy operationally.**

The two artifacts:
1. **Top-down is inflated by repetition.** 24 of 25 top-down records are `reduces_risk`
   stale-asset reviews; 23 share an identical label pattern (`useful / already_known /
   actionable / accept`), all in `02_Other_Git_Projects`. That is **one idea - "review the
   stale research collection" - counted as ~23 separate accepted wins.** Top-down's 24/25
   accept rate is therefore ~6x overstated as "distinct useful proposals."
2. **Bottom-up is judged mostly on its worst case.** All 4 bottom-up accepts (and the 2 useful
   defers) are **same-repo / same-family**; all 17 rejects are **cross-repo / cross-domain**
   lexical-overlap false positives. Bottom-up is not broadly broken - its cross-repo lexical
   mode is, and the sample is dominated by that mode.

Net: after de-duplicating top-down's repeated stale items, top-down produced ~2 distinct ideas
(one rejected orphan link + one stale-collection review); bottom-up produced ~6 distinct
same-repo/same-family useful connections. The 24-vs-4 accept gap does **not** show top-down is
6x better; it shows top-down repeats and bottom-up was tested cross-domain.

## Top Findings (by severity)

1. **Repetitive item-level stale proposals counted as independent wins (HIGH).** `review-028`
   through `review-050` are near-identical `reduces_risk` stale reviews on
   `02_Other_Git_Projects` (24 proposals / 41 distinct stale assets). The engine emits
   item-level stale proposals instead of one collection bundle, and calibration counts each as
   a separate accept. This inflates top-down and burned ~23 of the 25 top-down review slots on
   one idea.
2. **Bottom-up cross-repo lexical overlap is the false-positive generator (HIGH).** 17/17
   bottom-up rejects are cross-repo `documents`/`adds_test` proposals justified by token
   overlap (e.g., "DAD README documents a private law-firm roster dataset"; "archived Logos
   philosophy README documents an FMG decision log"). v1 lexical evidence does not survive
   crossing domains.
3. **`actionability` is collinear with `usefulness` - a dead axis (MEDIUM-HIGH).** Counts are
   identical (30/18/2) and every record has `usefulness == actionability`. The axis added zero
   information; "useful but not actionable now" was never expressed (even the two deferred
   useful items were labeled `actionable`).
4. **`safety` is uniformly `safe` (50/50) - a dead axis (MEDIUM).** Even `review-009`, which was
   deferred *because it touches Mock Trial* (an active/excluded repo), is `safe`. The
   active/excluded-repo concern was carried only by `decision=defer` + a note, not by the
   safety axis. Safety should flag active-repo and external-action proposals.
5. **Engine comparison counts records, not distinct ideas (MEDIUM).** Because metrics are raw
   counts, an engine that repeats one idea 23 times outscores an engine that finds 6 distinct
   ideas. This biases the hybrid-default rationale.
6. **Hybrid default rationale is half-supported (MEDIUM).** "Top-down is the safer default
   review queue" is reasonable; "top-down dominated 24-vs-4" is an artifact. The labels support
   *gating bottom-up to same-repo/same-family*, not *putting bottom-up behind generic stricter
   filters*.
7. **Novelty is low (6/50 novel) (LOW-MEDIUM).** As a discovery engine this is thin; the real
   novel finds are the bottom-up same-family connections (008, 014, 016, 019), which the sample
   nearly drowns under cross-repo FPs and stale repeats.
8. **Accept semantics are undefined (LOW).** 28 `accept_candidate` on candidate-only proposals
   - does "accept" mean "act now" or "worth a bounded experiment"? Without a definition, 28
   accepts read as a large action queue that is mostly one repeated stale review.

## Labels I Would Change

Per-record labels are largely defensible; these are the changes that would remove the bias.
(Recommendation only - not applied.)

| sample_id | field | current | proposed | reason |
|---|---|---|---|---|
| review-028 ... review-050 (23) | decision | `accept_candidate` (each) | accept **one** bundled stale-collection review; mark the rest `defer` as bundle members | They are one idea repeated; 23 independent accepts overstate distinct value and bias the engine comparison. Keep `usefulness=useful` (the collection is worth reviewing). |
| review-009 | safety | `safe` | `needs_more_review` | Touches Mock Trial, an active/excluded repo; `decision=defer` is right but safety should carry the active-repo flag. |
| review-009, review-019 | actionability | `actionable` | `not_actionable` (now) | Both are `useful` but were **deferred** pending boundary/active-repo review - i.e., not actionable now. This is exactly the distinction that would make actionability informative again. |
| review-026 | (verify) | `not_useful` / reject | verify before finalizing | The only non-stale top-down idea (an `activates_orphan` link) was rejected; confirm it had no same-family signal worth keeping as weak `related_to` evidence rather than discarding. |

No usefulness label looks individually wrong; the problem is decision inflation + dead axes.

## Missed False Positives

- **The 23 repeated stale accepts (028-050)** are the main missed FP at the *calibration* level:
  not wrong per item, but counting them as 23 distinct useful accepts is a metric false
  positive.
- **Concentration risk:** 24 of 25 top-down accepts are in a single collection
  (`02_Other_Git_Projects`). If that collection contains active repos, "accept a stale review"
  could imply action on active assets - confirm `02_Other_Git_Projects` is not active/excluded
  before treating these as actionable.
- No bottom-up FP slipped through into "accept" - the 4 accepts are all same-repo and look
  sound. Good.

## Missed False Negatives

- **Bundling FN is noted once (041) but spans 028-050.** The higher-value action - "review N
  stale research assets in `02_Other_Git_Projects` as one governed keep/renew/archive/dismiss
  batch" - is the real proposal; the engine under-proposes it and over-proposes its members.
- **Discarded cross-repo bottom-up overlaps lose lineage signal.** Several rejects (cross-repo
  lexical) are correctly not-useful as *coverage* proposals, but the overlap itself could be
  retained as weak `related_to` / family evidence rather than thrown away. Reject-as-proposal
  != no-signal.
- **No engine proposed grouping stale assets by owner/topic/collection/decision-workflow** -
  the missing proposal *type* (collection-level review) is itself the FN.

## Recommended Algorithm / Data-Flow Fixes

1. **Collection-level stale review.** Replace item-level `reduces_risk` proposals with one
   bundled proposal per `(repo_root | collection, lifecycle_state, asset_type)`, carrying the
   member asset list. The top-down generator already has `bundles_assets`; route stale through
   it. Expected effect: top-down's 24 stale records collapse to ~1-3 bundles; the comparison
   stops being inflated.
2. **Gate bottom-up to same-repo / same-family by default.** Only emit cross-repo bottom-up
   `documents`/`adds_test` proposals when evidence exceeds lexical overlap: shared capability/
   need IDs, shared `content_sha256` / near-duplicate cluster, or shared outcome **plus**
   IDF-weighted similarity above a calibrated threshold. Expected effect: removes ~17/17 of the
   observed bottom-up FPs while keeping all 4 accepts.
3. **De-duplicate the comparison metric.** Count *distinct proposal ideas* (cluster by
   `type + repo-relationship + target family`), not raw proposal count, in
   `proposal_engine_comparison.md`. Report "distinct useful ideas per engine" and "FP rate by
   repo-relationship (same-repo vs cross-repo)."
4. **Cross-domain lexical guard.** Require a shared structured facet (capability/need/outcome)
   AND IDF similarity above threshold before any cross-repo coverage proposal. Raw token
   overlap alone should never produce a cross-domain `documents`/`adds_test` proposal.
5. **Active/excluded-repo guard.** Tag proposals whose source or target is in an active/excluded
   repo (Mock Trial, etc.); auto-set `safety=needs_more_review` and `decision=defer`, and
   surface the tag in the review record.

## Recommended Calibration-Methodology Fixes

1. **Redefine `actionability`** as "can act now without external/boundary dependency," so
   useful-but-deferred items (009, 019) are `not_actionable_now`. Restores an independent axis.
2. **Make `safety` carry real signal:** active/excluded-repo touch, external-code/import,
   implied work on a source repo -> `needs_more_review`. Otherwise drop the axis.
3. **Cap repetitive families before sampling.** Cluster proposals by `type + repo + target
   family` and sample distinct ideas, so the 25 top-down slots aren't spent on 23 copies of one
   stale-collection idea.
4. **Stratify the review sample** by `proposal_type` and `repo-relationship` (same-repo vs
   cross-repo) so bottom-up is not judged almost entirely on its cross-repo failure mode.
5. **Define `accept_candidate`** explicitly (e.g., "worth a bounded experiment" vs "ready to
   act") and record it in the methodology, since 28 accepts otherwise imply a large action
   queue.

## Is Hybrid Default Justified?

**Conditionally yes, but for different reasons than stated.** Use top-down as the default
*portfolio risk/stale* review queue and bottom-up for *same-repo / same-family* connections -
that split matches the labels. But the evidence does **not** justify "top-down >> bottom-up";
that gap is a repetition artifact. Recommended operational policy:
- Top-down default for portfolio/stale/orphan risk, **with bundling** so it stops flooding.
- Bottom-up restricted to **same repo_root / same asset family** unless evidence exceeds
  lexical; cross-repo bottom-up off by default until guard #4 exists.
- Do not record "top-down outperformed bottom-up 24-vs-4" as a finding; record "top-down
  produced ~2 distinct ideas (one repeated), bottom-up produced ~6 distinct same-family ideas;
  bottom-up's cross-repo lexical mode produced 17 FPs."

## Premortem (proposal system misleading future agents)

- **How it misleads:** a future agent reads "top-down accept rate 96%, bottom-up 16%,"
  disables bottom-up, and loses the same-family discovery that was bottom-up's real value;
  meanwhile it trusts 24 "accepted" stale reviews as 24 distinct actions and floods a human
  queue with one repeated idea.
- **What evidence would prevent it:** distinct-idea counts, FP-rate-by-repo-relationship, and
  bundled stale proposals - so the metrics reflect ideas, not repetition.
- **Add before Phase 3 / external use:** collection bundling, same-family gating for bottom-up,
  active/excluded-repo guard, and a definition of `accept_candidate`. Do not pilot these
  proposals into other repos while cross-repo lexical FPs and stale floods are unguarded.

## Remaining Human Decisions

1. **Is `02_Other_Git_Projects` an active/excluded repo?** Determines whether the 24 stale
   accepts are valid actions or should be `needs_more_review`.
2. **Approve collection-level stale bundling** (one review per collection) over item-level?
3. **Approve bottom-up = same-repo/same-family by default** until cross-repo evidence is
   stronger?
4. **Define `accept_candidate`** (bounded experiment vs ready-to-act).
5. **Re-run the comparison on distinct ideas** before recording the hybrid decision as evidence?

## Validation Run (read-only)

- `recommend proposal-review-summary` -> 50 reviewed; useful 30 / not_useful 18 / unsure 2;
  safe 50; novel 6 / already_known 25 / unsure 19; actionable 30 / not_actionable 18 / unsure
  2; decisions accept 28 / reject 18 / defer 4; FP notes 18, FN notes 1, useful-example 30;
  gate + structured notes complete.
- `validate` -> valid, 61 checked, 0 errors.
- `roadmap check --no-update` -> phases 0/1 complete (computed); phase-2 present (not marked by
  this review).
- Join check -> top-down `reduces_risk` reviewed: 24 proposals across 41 distinct stale assets
  (item-level, not bundled).
</content>
