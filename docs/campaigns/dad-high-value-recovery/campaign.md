# Campaign Charter and Decision Gates

## 1. Terminal outcome

By the end of this campaign, DAD must either:

- prove measurable value on comparable real tasks and retain only the verified
  value-producing slices; or
- narrow or retire non-performing surfaces while preserving the safety,
  provenance, and validated-fix kernel.

The terminal artifact is a human-signed `scale`, `narrow`, `retire`, or
`re-audit` decision with reproducible evidence. Shipping more components is not
the terminal outcome.

## 2. Audit basis

The August 20, 2026 audit established the following confirmed baseline. These
figures are historical observations, not evergreen truth; Phase 01 must refresh
them before execution.

| Surface | Confirmed audit observation | Meaning |
|---|---:|---|
| Scheduled daemon | 18-stage cycle, 74 inputs, 0 material errors in the inspected live cycle | Real execution exists. |
| Journal | about 114,800 records | Durable activity exists, but volume is not value. |
| Learning/outcomes | 2,316 outcome rows; only 116 joined to a recommended asset in the audit | High-value attribution is currently weak. |
| Used outcomes | 99 of 1,286 `used` outcomes matched their recommendation | Most claimed use cannot support an asset-value conclusion. |
| Validated fixes | 6 validated fix outcomes | A small credible learning kernel exists. |
| Follow-through | 132 issues and 604 missing high-signal items | Collection greatly exceeds closure. |
| Workspaces | 101 worktrees, 121 local branches, 54 unmerged branches, 45 local-only commits | Lifecycle debt is material; deletion is not authorized. |
| CI | 10 scheduled-regression failures in the inspected run; advisory false-green paths existed | Actions run, but enforcement is not yet reliably binding. |
| Downstream adoption | Existing downstream usage/adoption/learning ledgers were empty in the inspected repos | Portfolio value is not yet demonstrated. |

The audit also found malformed decision-trace outcomes where prose such as
`none`, “No harmful…”, or attempted-failure explanations appeared where an
asset identity should be. `record_trace_outcomes` accepted arbitrary strings,
and the yield report counted lifecycle acknowledgements as reuse. Phase 03 must
repair these semantics before any value claim.

Audit provenance:

- prior audit trace: `dad:trace:4a713ca1-a47d-53c2-901f-18c95a5a44f4`
- prior audit handoff: `dad:handoff:08ef66d2-6977-5362-996e-4341d562625a`
- prior audit lesson: `dad:lesson:fb112433-95c1-51af-9776-8217a0a7c23f`

## 3. Keep, freeze, improve, and defer

### Keep now

- source-repository authority and privacy boundaries;
- append-only journal and immutable raw observations;
- deterministic validation and fail-closed unknown states;
- exception-to-independently-validated-fix flow;
- the small reviewed skill/asset set with real reuse evidence;
- MCP-first, provider-neutral adapters and human gates.

### Freeze during recovery

No new registry family, schema family, agent family, radar, dashboard, broad
command surface, recurring automation, external connector, or graph projection
may start unless it directly closes a campaign gate and Lowell approves a
documented exception. Maintenance and the narrow contract fields needed for the
value spine are allowed after their phase gate.

### Improve existing surfaces

- `.digital-asset/assets/adoption.jsonl` and repo asset-usage records;
- asset-use feedback and DAD notice adoption events;
- capability recommendations and workflow-run events;
- decision traces and `record_trace_outcomes`;
- `learning_yield_report.py`;
- existing portfolio/session/mail/worktree projections;
- current CI workflows and branch-protection evidence.

### Defer until pilot evidence

- ledger consolidation;
- session/handoff/lesson record redesign;
- queue consolidation beyond a read-only projection;
- additional automation or alerting;
- graph-driven action or recommendation promotion;
- provider-specific tuning or permanent model routing.

## 4. Required value spine

Every counted recommendation outcome must be joinable through this chain:

```text
task/run and baseline cohort
  -> recommendation_id + recommended asset_id + asset revision_id
  -> adoption_id OR explicit non-adoption reason
  -> constrained outcome enum + metric observations
  -> independent validation reference
  -> human lifecycle decision
```

Minimum fields for a counted row:

- trace ID and run/task ID;
- recommendation ID;
- recommended asset ID and immutable revision ID;
- adoption ID or constrained non-adoption reason;
- outcome enum: `used`, `ignored`, `attempted_failed`, or `harmful`;
- baseline and candidate metric values when part of a pilot;
- producer identity and distinct checker identity;
- verification status: `unverified`, `independently_validated`, or `rejected`;
- validation references;
- privacy class and synthetic/real flag;
- recorded time, duration, cost, and retry count when observable;
- lifecycle decision and its human receipt when promoted, retained, narrowed,
  superseded, or retired.

Only joinable, schema-valid, independently eligible rows may enter value
aggregates. Unknown and quarantined history remains queryable but excluded.

## 5. Outcome metrics

Lowell selects one primary metric before the pilot. J-500 must freeze that
metric's direction, estimator, analysis population, denominator, missing-data
rule, and P5B/P5C effect thresholds before any outcome is visible. The other
metrics remain predeclared secondary evidence or guardrails and cannot turn a
failed primary gate into a pass.

| Metric | Definition |
|---|---|
| Cycle time | Median elapsed time from accepted task start to independently verified completion, excluding declared human-wait time. |
| Rework | Number of repair attempts after the first checker result, normalized per completed task. |
| Review iterations | Count of material review/fix cycles before acceptance. |
| Defects prevented | Independently verified pre-merge failures caught that would otherwise have reached the protected branch. |
| Operator attention | Human decisions/minutes required per verified completed task. |
| Harmful recommendation rate | Harmful, independently confirmed recommendations divided by all closed recommendations. |
| False-positive attention rate | Alerts/asks rejected as not actionable divided by reviewed alerts/asks. |
| Closure rate | Valid closed outcome envelopes divided by eligible recommendations within seven days. |

Report median, sample size, missingness, cohort definition, and uncertainty.
Never substitute activity counts for these outcomes.

The default threshold schedule below is binding unless Lowell approves a
stricter schedule in H-005 before the first case. A launch revision may not make
it easier.

| Selected primary metric | P5B threshold | P5C threshold |
|---|---|---|
| Cycle time | at least 20% lower median elapsed time | at least 25% lower median elapsed time |
| Rework | at least 25% fewer repair attempts per completed task | at least 30% fewer repair attempts per completed task |
| Review iterations | at least 20% fewer material review/fix cycles per completed task | at least 30% fewer material review/fix cycles per completed task |
| Defects prevented | at least two additional independently verified preventions versus the matched baseline | at least three additional independently verified preventions versus the matched baseline |
| Operator attention | at least 20% fewer human minutes per verified completion | at least 25% fewer human minutes per verified completion |

All eligible cases belong to the primary analysis population unless a
pre-result exclusion rule applies. J-500 freezes minimum allocation by repo,
workflow slice, comparison arm or matched pair, and difficulty stratum. Later
relabeling, exclusion, arm switching, or metric substitution makes the gate
`inconclusive`; it never improves the result.

## 6. Phase graph

```text
P0 charter and signed launch
  -> P1 baseline and temporary freeze
  -> P2 immediate CI and enforcement recovery
       -> J-215 four-week scheduled stability observation ---------+
  -> P3 outcome contract and legacy classification                 |
  -> P4 operational lifecycle closure                              |
       +------------------------------------------------------------+
  -> P5A 10-task shadow calibration
  -> P5B 20-task comparative pilot
  -> P5C 40-task value gate
  -> P6 scale / narrow / retire / re-audit
```

P1 is complete only when J-100 emits and the checker accepts the hashed
`processed/reports/dad-high-value-recovery/operational-eligibility-baseline.json`
artifact. That artifact freezes the cutoff, source revisions, stable eligible
population, inclusion/exclusion rules, reason-code map, and reconciliation
equation used by P4. A later campaign stage cannot shrink that denominator.

Only the calendar wait in J-215 overlaps Phases 03–04. Implementation writes
remain serial. Phase 03 may start after J-210 proves immediate enforcement;
Phase 05 waits for both Phase 04 and four consecutive scheduled passes.
J-500 also binds the manifest's case-execution slots to exact case-bank digests.
The controller then leases exactly one atomic case child at a time; J-510,
J-520, and J-530 are cohort reconciliation gates, not whole-cohort work leases.
Revision 7 binds all 70 slots exactly once under the accepted J-500 binding-table
digest. The controller materializes each child packet in memory, replaces only
its `{case_digest}` placeholder, and limits that child to the unique envelope
`processed/reports/dad-high-value-recovery/pilot-case-envelopes/{job_id}.json`.
The binding-table digest must remain identical in the packet, lease, dispatch
projection, checkpoint, and receipt. Duplicate, rebound, skipped, unbound,
stale, or outcome-visible reordered slots fail closed.

Each cohort parent has action `validate` only. It may aggregate its declared
parent reports only after a complete cohort-closure artifact accounts for every
slot as independently verified started work or as an immutable unstarted or
withdrawn item with an exact reason. Closure also requires no active lease, no
unreconciled effect, no receipt or lease after a stop, and a bound stop trigger
and digest. `closure_complete` is control-plane accounting; it does not turn
partial or unavailable outcome coverage into evidence completeness.

An accepted terminal or inconclusive pilot result stops further work on that
pilot branch, closes it, and selects one of the declared Phase 06 routes. It is
not permission to skip closure or to execute a later cohort. J-600 receives a
runtime projection containing exactly the selected predecessor, never every
possible predecessor.

### Target calendar (planning target, not acceptance evidence)

| Window | Target work | Required decision point |
|---|---|---|
| Days 0–14 | baseline/freeze, local CI repair, immediate remote enforcement, new-outcome validation, start J-215 | stop feature expansion and make false green/invalid writes impossible |
| Days 15–30 | legacy classification, corrected yield, operational closure, runtime truth; begin 10-task shadow only after J-215 passes | confirm measurement and pilot readiness |
| Days 31–60 | 20-task comparative pilot across at least two repos | continue only on material benefit without guardrail regression |
| Days 61–90 | 40-task value gate across at least three repos and Phase 06 decision | scale only proven slices; otherwise narrow, retire, or re-audit |

Calendar dates never override acceptance. A missed target is reported; evidence
is not weakened to preserve the schedule.

## 7. Human decisions required before launch

Lowell recorded H-001 through H-010 for revision
`3-launch-candidate-20260821` in the candidate decision receipt. H-001 through
H-009 remain the selected campaign parameters. H-010 does not carry forward to
the changed activation candidate, so launch remains unapproved. Revision 7
preserves the accepted revision-6 controls and their evidence as historical,
adds atomic closure and terminal navigation, and remains unqualified and inert.
Revision 6
retains revision 5 and its hook-latency evidence immutably, repairs the prior
authorization inversion, and adds a non-dispatching execution-control bridge.
The bridge accepts only an exact, current, unexpired execution-authorization
receipt plus matching source, dependency, qualification, budget, idempotency,
lease, heartbeat, reconciliation, path, effect, durability, and stop-state
evidence. Its only outcomes are `blocked` and `ready-manual`; both keep
`execution_authorized:false` and `dispatch_allowed:false`. This prelaunch
evidence is candidate evidence and grants no execution authority.

| Decision ID | Required decision | Current selected value | Status for revision 7 |
|---|---|---|---|
| H-001 | Campaign owner | Lowell | recorded |
| H-002 | Campaign expiry/review date | 2026-11-19 | recorded |
| H-003 | Temporary expansion freeze | approve | recorded |
| H-004 | GitHub protection posture | enforce administrators | recorded; no GitHub change authorized yet |
| H-005 | Primary pilot metric | cycle time | recorded |
| H-006 | Pilot workflow scope | all three proposed workflows | recorded |
| H-007 | Pilot repositories | `repo:dad`, `repo:mock-trial`, `repo:lawfirm-os` | selection only; downstream approval still required |
| H-008 | Legacy invalid-row treatment | immutable quarantine from aggregates | recorded |
| H-009 | Worktree and stale-branch treatment | review-only classification | recorded |
| H-010 | Launch revision | revision 3 and digest `sha256:1ed2bb5a715ec61d9b92899016fabe90fa835511b079abd3615811a7fdf90a3c` | superseded; no revision-7 execution authorization exists |

No launch receipt may authorize deletion, push, merge, publication, deployment,
global settings, plugin installation, secret access, or downstream mutation by
implication.

### Revision-7 execution-control and host-gate boundary

Portfolio OS remains the sole lease and manual-packet authority projection.
Campaign bindings are strict, immutable material inside its existing lease and
dispatch scope digests; no campaign ledger, queue, executor, scheduler, or
authority store was added. A `ready-manual` bridge result is candidate evidence
only and cannot make the Portfolio OS executor available.

Codex intent-continuity host readiness is a separate hard gate for a future
supervised continuity-hook trial. It is not a campaign/J-100 readiness gate and
cannot substitute for the campaign execution-authorization, Portfolio OS lease,
or manual dispatch evidence. Conversely, a campaign bridge result does not
qualify Codex project trust, hook discovery, host delivery, or continuity value.

### Producer, checker, and terminal-navigation boundary

A producer first emits immutable attempt material. Its canonical
`producer_attempt_digest` covers binding revisions, idempotency, source and
input/dependency digests, outputs and evidence, outcome/state/coverage, budgets,
lease and effects, case/closure/route bindings, limitations, and affected paths,
before checker fields exist. A distinct checker then writes a separate record
that binds that digest, its identity and independence basis, a `pass` or
`challenge` disposition, timestamp, limitations, and its own canonical digest.
The final receipt binds the checker-record path and digest. The producer cannot
write its checker record, and a checker `pass` means the attempt was represented
faithfully; it does not change an unfavorable job result into `pass`.

The controller and shell adapter remain projection-only and cannot dispatch or
write terminal navigation. After a predecessor receipt, closure, and checker
record validate, the controller may project a navigation packet. The existing
Portfolio OS may separately lease a task-local `campaign-navigation-writer`; a
distinct `independent-checker` owns the immutable route receipt at
`checks/evidence/navigation/{route_id}.json`. That writer may update
`07_EVIDENCE_INDEX.md`
and `handoff.md` only under the exact route lease. It may update
`08_SUPERSESSION_AND_ARCHIVE_MAP.md` only after a signed J-600 decision. No
ordinary job writer may request those paths or the navigation-receipt root.
The pre-J-600 receipt binds the projection digest, stage, and exact applied
paths. Final navigation creates a second immutable
`checks/evidence/navigation/{route_id}-post-j600.json` receipt that additionally
binds the signed J-600 receipt and the 08 path. The two receipts cannot overwrite
or substitute for one another.
Successors reject a missing, stale, mismatched, partial, projection-only, or
unaccepted navigation receipt. This is a role contract, not a new job, command,
queue, scheduler, or automation.

## 8. Authority and effect classes

### Allowed after an exact launch approval

- bounded local edits named by the current job packet and manifest;
- local deterministic tests and read-only inventory;
- privacy-safe campaign reports and evidence pointers;
- independent read-only review;
- reversible quarantine from aggregates while preserving raw rows.

Terminal metadata navigation additionally requires its own Portfolio OS lease,
exact route packet, independent checker, and accepted route receipt.

### Separate exact approval required

- GitHub branch-protection or repository-setting changes;
- dispatching pilot work into another repository;
- adding or changing a recurring task;
- any external message, issue, PR, push, merge, release, or deployment;
- changing the global worktree registry beyond the currently approved campaign
  worktree record;
- moving, deleting, pruning, cleaning, or archiving a worktree or branch;
- lifecycle retirement that changes active public or downstream behavior.

### Prohibited in this campaign revision

- secrets or raw private/client data in DAD records;
- rewriting or deleting raw observations;
- self-grading as the sole acceptance signal;
- autonomous scope expansion;
- provider/model lock-in in the campaign core;
- inferring source-repository canon from DAD telemetry;
- treating missing coverage as success.

## 9. Research and professional-practice basis

The detailed evidence-to-decision matrix and anti-cargo-cult boundaries are in
`09_RESEARCH_BENCHMARK_AND_DESIGN_PRINCIPLES.md`.

The campaign translates current lead AI engineering practice into DAD-specific
gates:

- Anthropic's [agent-evaluation guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
  distinguishes traces from outcomes, recommends multiple grader types, real
  failure-derived tasks, negative cases, and small 20–50 task starter suites.
- Anthropic's [context-engineering guidance](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  supports bounded, curated context rather than ever-growing ambient memory.
- [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
  motivate provider-neutral trace fields and explicit experimental stability.
- [W3C PROV-O](https://www.w3.org/TR/prov-o/) motivates separate entities,
  activities, agents, and derivation rather than prose-only lineage.
- [SLSA Build provenance](https://slsa.dev/spec/v1.2/build-track-basics) motivates
  revision-bound inputs, builder/checker identity, and independently verifiable
  provenance rather than a green label alone.
- Google's [SRE SLO practice](https://sre.google/sre-book/service-level-objectives/)
  motivates explicit service indicators, objectives, and consequence-bearing
  thresholds instead of dashboard volume.
- The [MCP authorization specification](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)
  reinforces least privilege, audience-bound authority, and no token or
  permission passthrough.

These sources are design inputs, not adoption authority. DAD's local contracts
and current evidence remain controlling.

## 10. Global stop conditions

Stop, checkpoint, release the lease, and ask the named owner when:

- the user interrupts or changes scope;
- a job exceeds its cost, time, context, output, retry, or storage budget;
- a required human decision or external permission is absent;
- source or dependency digests changed;
- writer/checker independence is compromised;
- a secret, private payload, source-authority conflict, or security risk appears;
- a gold standard fails;
- validation is inconclusive or coverage is unavailable for a required gate;
- unrelated user changes overlap the job write set;
- the original attempt plus one bounded repair fails;
- evidence would have to be rewritten, relabeled, or selectively omitted to pass.

A valid terminal pilot result stops only its affected pilot branch. After exact
closure and checker acceptance, it follows the declared navigation route to
J-600; it does not authorize another pilot cohort or any external effect.

## 11. Completion definition

This campaign is complete only when all of the following are true:

1. Phase 01 baseline is reproducible and the freeze has an approved expiry.
2. Local validation is green and required GitHub enforcement has real external
   evidence, including four scheduled weekly regression passes.
3. New outcomes have 100% recommendation membership validation and zero prose
   sentinels in identity fields.
4. Every legacy outcome is classified `joinable`, `invalid`, or `unknown`, and
   aggregates exclude invalid/unknown rows.
5. Operational thresholds needed for pilot validity are met.
6. The 10-, 20-, and 40-task branches have complete control-plane closure,
   independently checked evidence, or an accepted exact terminal route.
7. The selected route binds J-600 to exactly one predecessor and permitted
   decision set through an accepted navigation receipt.
8. Phase 06 has a signed `scale`, `narrow`, `retire`, or `re-audit` decision.
9. Final navigation, DAD postflight, and workspace lifecycle disposition are
   recorded.

Disappointing evidence is not an incomplete campaign. A defensible narrow or
retire decision is a successful completion.
