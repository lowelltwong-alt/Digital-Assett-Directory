# Portfolio Capacity Review Contract

## Purpose

The review finds constraints on portfolio throughput without creating a second
project system or an autonomous management authority. It converts bounded local
metadata into a candidate weekly packet for human review.

## Review boundary

- Operate deterministic V0 in `manual_shadow` mode with zero semantic agent
  fan-out. Role definitions remain candidate extension contracts, not evidence
  that an agent attempt ran.
- Read only explicitly configured local roots and source-authorized metadata.
- Refer to private sources with stable identifiers or redacted references.
- Exclude C3 payloads: client content, secrets, credentials, raw conversations,
  private source rows, email bodies, and equivalent sensitive material.
- Preserve source-repository authority. DAD can compare evidence and recommend;
  it cannot redefine a repo mission or mutate its canon.
- Treat schedules, notifications, daemon control, Git changes, task mutations,
  instruction changes, and cross-repo writes as separate human-gated actions.

## Evidence classes

Label each finding as:

- `confirmed`: directly supported by current, valid evidence;
- `inferred`: a bounded interpretation with evidence and a falsifier;
- `disputed`: material counterevidence or reviewer disagreement remains;
- `unknown`: required evidence is missing, stale, invalid, or unavailable.

A plan proves intent only. Age proves elapsed time only. Centrality, source
count, model confidence, and repeated mention do not prove value or priority.

## Required source and lane matrix

Completeness is evaluated against a declared allowlist, never against only the
inputs that happened to arrive. The manual V0 requires current, schema-supported
metadata for portfolio flow, Git and worktree state, roadmap and acceptance
state, skill and library state, role revisions and evaluations, learning-loop
outcomes, measured iteration evidence, routine and daemon health, and research
freshness. It also requires a current reviewed mission contract for every
configured repository.

Unknown source identifiers are rejected. Missing sources are named and make the
packet partial. Unsupported schemas, unknown or future statuses, malformed
booleans, and C3/C4 flags block the packet. Privacy, trust, and status validation
happens before hashing. Optional operational sources may add evidence but cannot
substitute for a required lane.

Every required source has an executable shape adapter and consumption path.
Worktree attention, roadmap gates and dependencies, candidate registries,
unclosed learning loops, typed iteration observations, and stale research
receipts must be able to change deterministic candidates with zero agent
fan-out. Dynamic sources use declared freshness windows and a valid observation
timestamp; static registries report freshness as not applicable. Explicit JSON
`null` is not omission for a boolean. Scalar source payloads are rejected with a
generic invalid reference and are never fingerprinted.

## Noncompensatory precedence

Apply the first matching class in this exact order:

1. `authority_privacy_security_integrity_gate`
2. `human_decision_wait`
3. `dirty_or_conflicted_unique_value_risk`
4. `accepted_dependency_unlock`
5. `accepted_outcome_capability_learning_gap`
6. `measured_iteration_cycle_drag`
7. `routine_or_daemon_degradation`
8. `research_or_mission_freshness_debt`

Never calculate a numeric or composite score. Lower-precedence volume cannot
outvote a higher-precedence safety or authority gate. Within one class, prefer
the candidate with the strongest evidence status, an explicitly reversible next
action, a traced accepted unlock, and an evidence-bound falsification path. If
the comparison remains ambiguous, expose the disagreement; a lexical order may
stabilize presentation only after the tie is recorded.

## Composed worker mesh

Reuse existing roles before adding a specialist:

- `neglected-worktree-triage-manager` for dirty, stale, blocked, superseded, or
  unknown branches and worktrees;
- `dependency-critical-frontier-analyst` for reviewed dependency chains and
  the smallest candidate unlock;
- `research-project-workflow-steward` for research evidence, falsification, and
  decision readiness;
- `delivery-closeout-resumption-steward` for acceptance, residual work, and
  resume capsules;
- `evaluation-integrity-auditor` and `improvement-layer-router` for evaluator
  integrity and learning-loop attribution;
- deterministic DAD status, registry, roadmap, and portfolio projections for
  routine and daemon health, planned-versus-implemented evidence, and source
  coverage.

Create only these three capacity-review roles:

1. `portfolio-capacity-foreman` integrates bounded worker packets, applies
   categorical precedence, limits human asks to three, and reveals overflow.
2. `capability-maturity-and-cycle-auditor` distinguishes declared, implemented,
   validated, evaluated, and promoted capability evidence and diagnoses cycle
   drag only from measured or repeatable observations.
3. `independent-capacity-review-checker` receives source evidence, schemas, and
   mission records without the foreman's conclusions, checks coverage and
   counterevidence, and returns accept, revise, or block.

## Escalation

Use the existing `sol-automation-workflow-architect` only when cheaper lanes
establish a repeated cross-repository bottleneck with material architecture,
privacy, authority, or irreversible-cost consequences. The Sol packet must
contain evidence, counterevidence, rollback, kill criteria, and a bounded trial.

Recommend Fable only as a manual human-selected review when a material systemic
or master-architecture disagreement remains after the blind checker and Sol
review. No packet may invoke, schedule, or imply standing Fable authority.

## Human asks and overflow

Emit at most three human asks. An ask must name the decision, why a human is
needed, options, strongest counterargument, safe default, expiry or review
condition, and the smallest reversible next action. Do not escalate a choice
that can be resolved safely by deterministic validation within existing
authority.

Place every non-selected candidate in `overflow`. Mark overflow complete and
set the unrepresented count to zero. Quiet, dismissed, snoozed, unchanged, or
low-evidence items remain visible in overflow or `suppressed` with a reason and
at least one wake condition.

## Capability maturity

Use categorical stages only:

- `planned_only`
- `partially_implemented`
- `implemented_unvalidated`
- `validated_not_adopted`
- `active_current`
- `stale`
- `superseded`
- `unknown`

Do not infer maturity from the presence of a skill folder, role declaration,
plan, or test alone. Cite the missing next proof and the authority that can
promote the capability.

## Iteration evidence

Accept measured wall time, repeated failure signatures, queue delay, handoff
latency, or bounded before/after parity evidence only when the observation names
a typed numeric baseline and comparison in one unit, one identical workload
reference, a passed correctness or parity oracle, and a preserved failure path.
Measurements must be finite; `NaN` and infinity are invalid.
Every receipt declares a metric kind and whether lower or higher is better.
Only a same-workload comparison that is worse in that direction becomes
`measured_iteration_cycle_drag`. Equal or improved observations remain visible
as neutral evidence and are suppressed from bottlenecks and human asks.
Free-form evidence labels such as `baseline:missing` or `parity:not-run` are
pointers, not proof, and cannot create a bottleneck or human ask.
Separate model, agent, tool, input, data, workflow, handoff, evaluator, domain,
and downstream hypotheses. Do not propose a language migration or architectural
rewrite without profiling, parity, rollback, and human approval.

Routine scheduling state is `scheduled`, `not_scheduled`, or `unknown` and must
come from an inspected scheduler receipt. The candidate weekly routine remains
unscheduled regardless of other routine observations.

## Fan-out and blind checker lineage

Deterministic V0 must record `semantic_agent_fanout: 0`, mark the fan-out status
`deterministic_v0_not_dispatched`, use `not_dispatched` attempt identifiers, and
set checker lineage incomplete with verdict `not_run`. This is a valid shadow
packet and must not imply that foreman, checker, Sol, or Fable work occurred.

Only a separately invoked `agent_assisted_frozen_input` review may claim
complete blind lineage. Freeze the input fingerprint before dispatch. The
checker must have a distinct attempt identifier, must not be the foreman, and
must attest that it received only source evidence, schemas, and mission records
before its verdict. Disagreement is first-class output and cannot be erased by
the foreman.

## Feedback and evolution

The packet may offer labels for useful, noisy, missed, harmful, incomplete, or
defer feedback. Recording feedback, changing a role, promoting a pattern, or
activating the weekly routine remains a separate human-reviewed action. Freeze
simple deterministic workers when added prompt complexity does not improve
held-out results.

Bind the reviewed builder and contract revision into the material fingerprint.
A semantic implementation or contract change must wake suppression even when
the source evidence is unchanged; volatile run timestamps alone must not.

## Kill criteria

Stop or block the shadow review if it:

- includes C3 data or exposes a private absolute path;
- claims complete coverage while a required source is unavailable;
- hides overflow or exceeds three human asks;
- calculates a numeric or composite priority score;
- uses a plan, age, centrality, or model confidence as proof;
- lets an author serve as the independent checker or claims agent lineage when
  deterministic V0 dispatched no semantic agents;
- schedules itself or performs any mutation;
- changes a mission, role, prompt, routing rule, or authority boundary without
  explicit human review.
