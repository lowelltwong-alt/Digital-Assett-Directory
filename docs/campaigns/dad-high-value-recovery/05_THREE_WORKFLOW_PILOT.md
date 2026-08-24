# Phase 05 — Three-Workflow Outcome Pilot

## Outcome

Measure whether DAD materially improves real work, using comparable tasks,
source-separated evaluation, explicit counterevidence, and staged sample sizes.
The pilot tests three existing workflow slices, not the whole DAD architecture.

## Proposed workflow slices

1. **Preflight recommendation and reuse** — did an eligible recommendation lead
   to independently evidenced useful reuse?
2. **Exception to validated-fix reuse** — did a prior validated fix prevent or
   shorten a comparable failure?
3. **PR/worktree recovery triage** — did DAD reduce recovery time or rework
   without unsafe cleanup or false-positive attention?

Lowell may remove a slice before launch. Adding a fourth slice requires a new
campaign revision.

## Prerequisites

- Phases 01–04 pass.
- H-005 primary metric, H-006 workflows, and H-007 exact repositories are signed.
- Maximum three repos; each retains local authority and approves its evidence
  and write boundary.
- Pilot task definitions, baseline/candidate assignment, eligibility, exclusions,
  privacy, checker independence, and stopping rules are frozen before outcomes.
- The selected primary estimator, direction, denominator, P5B/P5C thresholds,
  analysis population, and minimum repo/slice/arm allocation are frozen before
  outcomes. Secondary metrics cannot satisfy the primary gate.
- No source repo receives DAD writes merely because it is selected.

## Jobs in order

1. `jobs/J-500_FREEZE_PILOT_PROTOCOL_AND_CASES.md`
2. `jobs/J-510_RUN_10_TASK_SHADOW_CALIBRATION.md`
3. `jobs/J-520_RUN_20_TASK_COMPARATIVE_PILOT.md`
4. `jobs/J-530_RUN_40_TASK_VALUE_GATE.md`

## Pilot record per case

Each case records:

- case and cohort ID; workflow slice; repo ID; real/synthetic flag;
- task definition and difficulty stratum fixed before the result;
- accepted source/head and environment/runtime revision;
- baseline/candidate assignment and assignment method;
- recommendation/adoption/outcome/validation/lifecycle IDs;
- primary and guardrail metric observations;
- defects, safety/privacy events, retries, review iterations, and human waits;
- producer/checker identities and independence basis;
- evidence paths/digests, missingness, exclusions, and correction lineage;
- voluntary-use signal, not inferred from tool invocation.

Do not store raw conversations, secrets, client rows, or private source content.

## Comparison design

- Prefer paired or matched comparable tasks. If randomization is practical and
  locally approved, record it; otherwise declare the matching method and bias.
- Freeze success criteria before seeing candidate outcomes.
- Use deterministic checks for code/state outcomes, an independent reviewer for
  judgment, and sampled human calibration.
- A producer may self-report telemetry but cannot be the sole evaluator.
- Preserve failures and negative cases; do not exclude hard tasks after results.
- Report every eligible case and every exclusion reason.
- Bind every case to an enumerated manifest child slot before its lease. A case
  cannot be rebound, duplicated, reordered after outcome visibility, or executed
  under a whole-cohort lease.
- Separate model/runtime changes from DAD workflow changes.
- Report medians and distributions, not only averages.
- Synthetic fixtures validate plumbing and negative controls only.

## P5A — 10-task shadow calibration

Purpose: prove envelope closure, measurement reliability, and operator workflow.
It is not a success claim.

- Exactly 10 eligible real tasks across the approved slices.
- Candidate advice may be shown or shadowed as approved; no automatic effects.
- At least one positive and one negative/should-not-trigger case per slice where
  feasible.
- Every case must close within seven days or carry an explicit unresolved reason.

Pass to P5B only when:

- 100% of cases have structurally valid, joinable envelopes;
- metric computation is reproducible;
- producer/checker independence is intact;
- no privacy, source-authority, or harmful-action breach occurred;
- classification disagreement is resolved or reported as uncertainty;
- operational gates remain at Phase 04 thresholds.

## P5B — 20-task comparative pilot

Purpose: detect a large practical effect before a larger investment.

- At least 20 comparable real tasks across at least two approved repos.
- All three slices should be represented unless H-006 narrowed scope.
- Baseline/candidate rules and primary metric are frozen.

Pass only when all safety/quality guardrails hold and the single H-005 primary
metric meets its frozen P5B threshold in the charter. A favorable secondary
metric is supportive evidence, not a pass.

Minimum allocation, unless H-005 approves a stricter one before outcomes:

- at least eight eligible cases per included repository;
- at least six eligible cases per selected workflow slice;
- at least eight cases per comparison arm, or eight completed matched pairs for
  a paired design; and
- every eligible case reconciled in the primary analysis population or excluded
  only by a frozen pre-result rule.

Additional required evidence:

- no increase in verified defect escape or safety/privacy incidents;
- at least 80% valid closure within seven days;
- harmful recommendation rate below 2%; with this sample, that requires zero
  independently confirmed harmful cases;
- false-positive attention rate below 10%;
- at least two assets independently reused across two repos;
- open sessions at most 20, follow-through at most 20, and immediate high-signal
  queue at most 10.

If no benefit threshold passes, stop for Phase 06 `narrow`/`retire`; do not grow
the sample merely to hunt for a favorable result unless the evidence is invalid.

## P5C — 40-task value gate

Purpose: decide whether any slice deserves continued investment.

- At least 40 comparable real tasks across at least three approved repos.
- At least two weeks of voluntary-use observation after participants can decline.
- Retain the frozen primary metric and report slice-level and overall results.
- Include at least ten eligible cases per repository, eight per selected
  workflow slice, and sixteen per arm or sixteen completed matched pairs. H-005
  may freeze stricter minima, never weaker ones.

Pass only when all guardrails hold and the single H-005 primary metric meets its
frozen P5C threshold in the charter. No alternative outcome may be selected
after results.

Guardrails:

- harmful recommendation rate below 2%; with fewer than 50 closed
  recommendations, that requires zero independently confirmed harmful cases;
- false-positive attention rate below 10%;
- median eligible queue age below seven days;
- at least 80% valid closure within seven days;
- no material defect, privacy, source-authority, or safety regression;
- all synthetic evidence excluded from success counts;
- at least two assets retain independently evidenced cross-repo reuse.

## Early stopping

Stop the affected slice immediately for a privacy/source-authority breach,
harmful rate at or above 2% with adequate denominator, repeated checker-integrity
failure, metric corruption, or a material safety regression. Preserve evidence
and proceed to Phase 06; failure is an acceptable result.

## Acceptance

- P5A, P5B, and P5C each have frozen protocols, complete case reconciliation,
  independent receipts, counterevidence, limitations, and corrections.
- A value claim is made only if P5C passes.
- Slice-level failures are not hidden by aggregate success.
- Cost and operator attention are included in the decision packet.
- The evidence supports a Phase 06 decision without another broad discovery
  build.

## Rollback

Pilot enrollment can be stopped and leases released. Source-repo code changes
use their local rollback plan and authority. Evidence remains immutable; a
correction supersedes but does not erase it.
