# Phase 01 — Baseline and Temporary Freeze

## Outcome

Produce a reproducible before-state, make every missing coverage area explicit,
and bind a temporary expansion freeze with an owner and expiry. This phase does
not repair the findings it measures.

## Prerequisites

- H-001 campaign owner, H-002 expiry, H-003 freeze, H-008 legacy treatment, and
  H-010 launch revision are signed.
- The governed worktree is registered and validated under the global lifecycle
  policy.
- DAD preflight has no unresolved required learning-rule acknowledgements.
- `campaign.json` input digests match the current source revision.
- One writer and a distinct checker hold non-overlapping leases.

## Jobs in order

1. `jobs/J-100_REPRODUCIBLE_BASELINE.md`
2. `jobs/J-110_TEMPORARY_EXPANSION_FREEZE.md`

## Baseline dimensions

J-100 must capture all dimensions below from read-only or non-mutating commands.
If a surface cannot be measured, record `coverage_unavailable` with the exact
reason.

| Dimension | Minimum evidence |
|---|---|
| Source state | HEAD, upstream, dirty/untracked counts, branch, worktree registration and hold status |
| Local validation | `pytest`, DAD validate, roadmap check, exact failures and durations |
| GitHub CI | recent scheduled/manual full-regression runs, required-check conclusion, workflow revision, run URLs |
| Protection | required contexts, administrator enforcement, bypass policy, current protected-branch settings |
| Outcome integrity | total outcomes; membership joins; constrained enum validity; prose-sentinel count; producer/checker collision count |
| Usage/adoption | per-repo usage rows, adoption rows, verified downstream reuse, non-adoption closure |
| Yield | current written/reused/promoted counts and the event types that caused each count |
| Operations | open sessions, follow-through issues, missing high-signal coverage, mail doctor issues, queue age |
| Workspace | local branches, unique/unpushed commits, present/prunable/detached/dirty worktrees, registry coverage |
| Runtime | data root, transport audit, daemon heartbeat/task state, journal checkpoint/status, contradictions |
| Cost/attention | command duration, known token/cost data, human decisions and estimated attention; unknown kept unknown |

J-100 must also emit the immutable, machine-readable operational denominator
artifact at
`processed/reports/dad-high-value-recovery/operational-eligibility-baseline.json`.
It records the observation cutoff; exact source IDs and revisions; inclusion and
exclusion rules; the frozen reason-code map; privacy-safe stable item IDs or
hashes; population counts by queue, session, worktree, branch, and mail
category; and this reconciliation identity:

```text
expected_open = baseline_eligible + eligible_arrivals
                - verified_closures - approved_superseding_corrections
```

Every term must reconcile to item-level evidence. An exclusion or reason-code
change after the cutoff requires a separately accepted correction receipt and
a new baseline revision; it cannot improve the active campaign's denominator.

## Recommended command families

Use the existing surfaces first. Exact flags must be confirmed against the
current CLI help before launch.

```powershell
git status --short --branch
git worktree list --porcelain
python -m pytest
python -m digital_asset_directory.cli validate
python -m digital_asset_directory.cli roadmap check --no-update
asset-dir data status
asset-dir transport audit
asset-dir daemon status
asset-dir journal status
asset-dir mail doctor --repo all --summary-only --fail-on-dirty --fail-on-coverage-gap
asset-dir os cockpit
asset-dir janitor --hub .
```

`asset-dir janitor --hub .` is dry-run evidence only. Do not use `--apply` in
this phase. GitHub inspection is read-only until H-004 and a separate external
setting approval exist.

## Build policy

Prefer a deterministic evidence composition over a new product command. A new
baseline helper is allowed only when all of these are true:

1. an existing command cannot emit a required machine-readable observation;
2. the gap is recorded as `coverage_unavailable` first;
3. the helper is read-only, campaign-scoped, deterministic, and tested;
4. it does not add a dashboard, recurring task, registry, schema family, or
   second source of truth; and
5. the launch manifest is revised to exact files and re-approved.

## Freeze contract

The freeze starts only after H-003 is signed. It allows:

- fixes required by Phases 01–04;
- narrow field additions needed to join the existing value spine;
- tests, fixtures, evidence, and documentation for campaign gates;
- security/privacy fixes and urgent production correctness fixes with an exact
  exception receipt.

It blocks new feature families, registries, schema families, commands, radars,
dashboards, agent families, scheduled routines, connectors, and broad graph
surfaces. The owner reviews exceptions; the producing agent cannot approve its
own exception.

## Acceptance

- Baseline regeneration on unchanged inputs produces semantically identical
  counts and source digests.
- The operational eligibility artifact has an immutable digest, cutoff, source
  set, item population, inclusion/exclusion rules, reason-code map, and a
  reconciled equation whose terms resolve to stable evidence IDs.
- Every number has an evidence pointer and observation time.
- All partial scopes and missing coverage are explicit.
- The historical audit figures are marked refreshed, changed, or unavailable;
  none are silently carried forward.
- A negative fixture reproduces the invalid recommendation/outcome join.
- A negative fixture or inspected workflow reproduces the false-green risk.
- The freeze has owner, start, expiry, allowed work, prohibited work, exception
  process, and rollback.
- No aggregate asserts DAD value before Phase 03 passes.

## Exit gate

The campaign owner and independent checker accept the baseline receipt and
freeze receipt. If the baseline cannot be reproduced, stop with
`validation_inconclusive`; do not move to CI repairs on an unstable measurement
surface.

## Rollback

Baseline artifacts are generated evidence and may be superseded by a correction
receipt; raw observations remain immutable. The freeze can be revoked by a
signed human decision, which also stops the campaign until a revised graph is
approved.
