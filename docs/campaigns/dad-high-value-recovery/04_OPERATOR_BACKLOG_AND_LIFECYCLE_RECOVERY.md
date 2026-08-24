# Phase 04 — Operator Backlog and Lifecycle Recovery

## Outcome

Reduce unresolved operational debt enough that pilot results are not dominated
by stale sessions, mail gaps, unowned worktrees, branch debt, or contradictory
runtime health. Recovery is review-first and never implies deletion.

## Prerequisites

- Phase 03 value spine is accepted.
- Global workspace lifecycle policy, Windows adapter, and active-worktree
  registry are current and validator-clean.
- H-009 defines review-only classification or lists exact separately approved
  lifecycle effects.
- Existing cockpit, janitor, mail, session, and coverage surfaces are inventoried
  before any new code is proposed.

## Jobs in order

1. `jobs/J-400_CLOSE_OPERATIONAL_AND_WORKSPACE_DEBT.md`
2. `jobs/J-410_RECONCILE_DAEMON_JOURNAL_AND_TASK_HEALTH.md`

## Reuse existing projections

- `src/digital_asset_directory/agent_session_reaper.py`
- `src/digital_asset_directory/lifecycle_janitor.py`
- `src/digital_asset_directory/portfolio_cockpit.py`
- `src/digital_asset_directory/portfolio_recovery.py`
- `src/digital_asset_directory/mail_center.py`
- `src/digital_asset_directory/lesson_automation_coverage.py`
- `src/digital_asset_directory/daemon.py`
- `src/digital_asset_directory/journal.py`
- `src/digital_asset_directory/transport_readiness.py`
- `docs/LIFECYCLE_JANITOR.md`
- `docs/DAD_MAIL_STORM_AND_DIRTY_STATE_RUNBOOK.md`
- `docs/PR_BRANCH_LIFECYCLE_GOVERNANCE.md`
- global `ACTIVE_WORKTREES.yaml` as the only actual worktree-ownership authority

Do not build a second cockpit. If a unified view is needed, make it a read-only,
rebuildable projection over existing sources with no new execution authority.

## Workstreams

### A. Sessions

1. Classify open sessions by owner, last activity, branch/worktree, lease/hold,
   exception status, and evidence of completion.
2. Close completed sessions with honest postflight.
3. Mark truly abandoned sessions only through the existing reaper semantics and
   an approved action; never fabricate completion or review-lane evidence.
4. Preserve parked, leased, held, and ambiguous sessions.

### B. Mail and follow-through

1. Run read-only mail doctor/follow-through/coverage checks.
2. Deduplicate by stable IDs while preserving raw packets.
3. Separate invalid packet, delivery gap, missing response, saved-for-future,
   rejected, and needs-human-review.
4. Deliver, archive, or mutate mail only under its exact existing permission
   gate; this campaign does not infer mailbox authority.

### C. Worktrees and branches

1. Inventory canonical local roots and `git worktree list --porcelain`.
2. For every worktree record owner, purpose, dirty/untracked counts, unique
   commits/containment, hold, next review, and one exact policy disposition.
3. Classify branches by upstream, merged containment, unique local commits,
   open PR, owner, next action, and escalation date.
4. Use `recovery_hold` for ambiguity.
5. Do not prune, delete, remove, move, reset, rebase, push, merge, or archive
   without separate exact approval and fresh containment evidence.

### D. Human attention

Project one deduplicated read-only review list with severity, source evidence,
owner, age, expiry, and suggested next decision. Show no more than three
immediate asks; keep the full list filterable. Age may raise review priority but
never authorize action.

### E. Runtime truth

Reconcile scheduled-task state, daemon heartbeat, last completed cycle, journal
checkpoint, data root, transport audit, and generated report freshness. A
contradiction or missing source becomes `degraded` or `coverage_unavailable`,
not green.

## Target thresholds before the pilot

Phase 01 freezes the eligible operational population, observation cutoff,
source set, and reason-code mapping. Phase 04 denominators equal that frozen
population plus eligible append-only arrivals through the declared cutoff.
Reclassification may correct evidence only through a superseding reason-coded
receipt and independent reconciliation; it cannot silently remove an unresolved
item from the denominator.

The sole denominator authority is the exact accepted J-100 artifact at
`processed/reports/dad-high-value-recovery/operational-eligibility-baseline.json`.
J-400 must bind its digest before dispatch and reconcile `baseline_eligible +
eligible_arrivals - verified_closures - approved_superseding_corrections` to
stable item-level evidence. A changed cutoff, source set, rule, or reason code
requires a corrected baseline revision and re-acceptance; it cannot be applied
retroactively to make a Phase 04 ceiling pass.

- Worktree registry coverage: 100% owner/disposition/review or explicit hold.
- Open agent sessions: at most 20, with zero unowned active sessions older than
  the approved threshold.
- Follow-through issues: at most 20.
- Missing high-signal/attention queue: at most 10 eligible immediate items.
- Invalid mail packets: zero; unknown coverage reported separately.
- Every stale sensitive branch has a human disposition record; no deletion is
  required to pass.
- Review cockpit immediate asks: at most three.
- Daemon, task, and journal health: mutually consistent or explicitly degraded.

These thresholds are pilot-readiness gates, not proof of business value.

## Validation

Run focused tests for every modified existing surface plus:

```powershell
$env:PYTHONPATH = 'src'
python -m pytest tests/test_agent_session_reaper.py
python -m pytest tests/test_lifecycle_janitor.py
python -m pytest tests/test_mail_center.py
python -m pytest tests/test_portfolio_cockpit.py
python -m pytest tests/test_weekly_asset_coverage.py
python -m pytest tests/test_transport.py
python -m pytest
python -m digital_asset_directory.cli validate
python -m digital_asset_directory.cli roadmap check --no-update
```

Also prove source-zero-write for every read-only inventory/projection and compare
the global registry against actual worktree observations.

## Acceptance

- All target thresholds are met or the campaign stops with an owner-approved
  decision that the pilot cannot proceed.
- Every automated classification has source evidence, confidence/reason code,
  and human override path.
- No present worktree or branch was changed by read-only recovery.
- No session is labeled complete without actual completion evidence.
- No mail absence is interpreted as adoption or rejection.
- Health contradictions render non-green.
- No more than three immediate human asks are projected.
- Before/after ceilings use the frozen Phase 01 denominator and reason codes;
  no threshold is met by post-hoc eligibility changes.

## Rollback

Read-only projections can be regenerated. Any separately approved lifecycle
mutation must have its own inverse/restore plan before execution. A destructive
action with no tested restore path is out of scope.
