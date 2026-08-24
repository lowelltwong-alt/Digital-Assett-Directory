# DAD High-Value Recovery Campaign

Status: `activation_candidate`; execution mode remains `specification_only`  
Campaign ID: `dad-high-value-recovery-v1`  
Start date: not authorized  
Execution owner: Lowell (H-001)  
Current authority: bounded prelaunch repair and local qualification only

This directory turns the August 2026 DAD audit into an ordered, resumable build
campaign. It is intentionally not another operating system, dashboard, radar,
registry family, or source of execution authority.

The audit found a real safety and provenance kernel with working scheduled
execution, append-only records, deterministic validation, and a small number of
validated fixes. It also found that DAD cannot yet make a credible high-value
claim because recommendation, adoption, outcome, validation, and lifecycle
records do not reliably join; required CI can look green while important checks
are advisory; and operational queues are far larger than their verified closure
rate.

The campaign therefore follows one value sequence:

```text
truthful baseline
  -> binding enforcement
  -> valid recommendation-to-outcome joins
  -> operational closure
  -> comparable real-task pilots
  -> scale, narrow, retire, or re-audit
```

## How to use this package

1. Copy the goal from `GOAL_PROMPT.md` into a new Codex goal.
2. The current package includes the bounded prelaunch repairs authorized after
   revision 3; it still cannot execute J-100.
3. Lowell reviews the remaining blockers and explicitly approves the new exact
   activation manifest revision and digest. The revision-3 H-010 is superseded.
4. Execute the numbered phase files in order. Within each phase, execute the
   listed `jobs/J-*.md` packets in order.
5. Do not advance on `blocked_human`, `inconclusive`, `fail_terminal`, a stale
   input digest, or missing independent evidence.
6. After every job, append only evidence pointers to `07_EVIDENCE_INDEX.md` and
   update `handoff.md`. Never rewrite raw observations to make a metric pass.
7. Before pilot execution, J-500 binds all 70 case slots. The controller leases
   one child case at a time; cohort jobs only reconcile their child receipts.
8. Campaign completion is a signed Phase 06 decision backed by valid pilot data;
   activity volume, graph centrality, asset count, or daemon uptime is not enough.

## Required reading and execution order

| Order | File | Outcome |
|---:|---|---|
| 0 | `campaign.md` | Bind authority, non-goals, metrics, stops, and human decisions. |
| 0A | `campaign.json` | Validate the machine graph and pin launch inputs. |
| 0B | `mesh/agent-mesh.plan.v1.json` | Keep one writer and a distinct independent checker. |
| 0C | `09_RESEARCH_BENCHMARK_AND_DESIGN_PRINCIPLES.md` | Connect current official AI-engineering practice to DAD keep, repair, add, defer, and retire decisions. |
| 0D | `checks/LAUNCH_RISK_REVIEW.md` | Review the high-risk launch boundary, candidate revision, blockers, rollback, and human decisions. |
| 1 | `01_BASELINE_AND_FREEZE.md` | Reproduce the before-state and stop feature expansion. |
| 2 | `02_CI_AND_ENFORCEMENT_RECOVERY.md` | Make local and GitHub checks fail closed. |
| 3 | `03_OUTCOME_CONTRACT_AND_DATA_REPAIR.md` | Repair the value spine and quarantine invalid aggregates. |
| 4 | `04_OPERATOR_BACKLOG_AND_LIFECYCLE_RECOVERY.md` | Reduce sessions, follow-through, worktree, branch, and health debt safely. |
| 5 | `05_THREE_WORKFLOW_PILOT.md` | Run 10-task calibration, 20-task comparison, and 40-task value gates. |
| 6 | `06_SCALE_OR_SHRINK_DECISION.md` | Select `scale`, `narrow`, `retire`, or `re-audit`. |
| 7 | `07_EVIDENCE_INDEX.md` | Locate immutable evidence and checker receipts. |
| 8 | `08_SUPERSESSION_AND_ARCHIVE_MAP.md` | Prevent duplicate plans, ledgers, queues, and control planes. |
| H | `handoff.md` | Resume from the exact last accepted gate. |

## Non-negotiable execution rules

- The repository and global workspace policies remain authoritative.
- A goal prompt is not approval to publish, merge, deploy, change GitHub settings,
  enroll downstream repos, delete or move worktrees, clean branches, access
  secrets, or activate recurring automation.
- Every implementation job gets one bounded writer and a distinct checker.
- Producer identity cannot be the sole evaluator identity.
- Raw observations are immutable. Legacy bad rows may be quarantined from
  aggregates, never silently rewritten or deleted.
- `coverage_unavailable`, `unknown`, and `unverified` are valid results and must
  never be rendered as zero or green.
- No new product feature family starts while the temporary freeze is active.
- Cross-repository pilot work requires exact repository, privacy, metric, and
  write-boundary approval.
- Synthetic and fixture evidence is reported separately and cannot satisfy the
  real-task value gate.

## Quick validation

From the repository root:

```powershell
python C:\Users\lowel\.codex\skills\orchestrate-long-run-campaigns\scripts\validate_campaign.py docs/campaigns/dad-high-value-recovery/campaign.json
python docs/campaigns/dad-high-value-recovery/checks/validate_campaign_consistency.py
python C:\Users\lowel\.codex\skills\dad-manifest-graph-engineering\scripts\validate_agent_mesh_manifest.py docs/campaigns/dad-high-value-recovery/mesh/agent-mesh.plan.v1.json
```

Passing these commands validates static specification shape only. It does not
authorize campaign execution.
