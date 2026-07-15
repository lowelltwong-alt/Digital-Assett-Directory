# Personal Project Management Contract

## Object boundaries

| Object | Purpose | Does not authorize |
| --- | --- | --- |
| Idea | Cheap capture of a thought, question, or possibility | Project, branch, task, reminder, or WIP allocation |
| Project | Stable container for a durable goal or responsibility | Automatic execution or canonical merge with related projects |
| Workstream | Bounded outcome with acceptance evidence and dependencies | Git mutation or an attention slot |
| Execution lease | Expiring human authorization to focus or execute | Delivery, destructive cleanup, or indefinite priority |
| Task | Small action in service of a workstream | Project identity or portfolio priority |
| Attention claim | Expiring candidate explaining why attention may help | State mutation, notification, or guilt-based escalation |

## Project control packet

Every phase owner returns only applicable fields:

```text
packet_version
as_of
coverage: roots, sources, as_of, input_fingerprint, cursor, unavailable_sources, gaps
project_identity: project_id, authority_root, owner, repository_refs, privacy_class, sovereignty_boundary
idea_refs[]: idea_id, disposition, promotion_status
related_work_assertions[]: relation, evidence, counterevidence, review_status
outcome
non_goals[]
workstreams[]: id, state, bounded_outcome, next_action, acceptance_evidence
dependencies[]: dependent, prerequisite, strength, review_status, evidence
execution_leases[]: workstream, owner, start, expiry, return_state
today[]
wip_overflow[]
blockers[]
risks[]
human_decisions[]
routine_purpose_and_expiry_assessment
build_refusal_assessment
experience_surface_assessment[]
learning_velocity_measures
task_refs[]: task_id, workstream_id, source_system, source_authority, state, evidence_ref
quiet_option
next_review_condition
smallest_reversible_next_action
resume_capsule: last_verified_intent, repo_and_worktree_refs, branch, dirty_or_ahead_state, last_acceptance_evidence, next_bounded_action, suggested_first_command, blockers, unknowns, privacy_boundary
execution_handoff: workstream_id, repo, proposed_branch_or_worktree, acceptance_contract, next_action, validation_plan, authority_approval
authority_boundary
```

Unknown is valid. Never manufacture completeness.

## Routine purpose and expiry assessment

Assess a recurring process, review, trigger, or report before recommending it
and again at its review condition. Every field may be `unknown` when evidence
is missing; unknowns route to a human decision rather than an invented answer.

```text
consumer
decision_or_behavior_changed
why_now
risk_caught
retained_human_judgment
evidence_of_value
cost_ceiling
quiet_condition
review_expiry_or_retirement_condition
```

A routine without a named consumer or plausible changed decision/behavior is a
retirement or non-creation candidate. A routine becomes quiet when its recorded
quiet condition is true. Age, invocation count, or model confidence alone does
not prove value or justify retirement.

## Build-refusal assessment

Run this before expanding implementation and during artifact diagnosis:

```text
can_build: yes | no | unknown
should_exist: yes | no | unknown
target_user_and_outcome
what_it_replaces
maintenance_and_attention_cost
smallest_evidence_version
stop_condition
evidence_and_unknowns
human_decision_needed
```

`can_build=yes` never implies `should_exist=yes`. Prefer the smallest version
that can change a named decision or produce falsifiable evidence. A product
catalyst may recommend refusal, deferral, or a bounded experiment; it may not
allocate work or cancel an approved workstream.

## Applicable experience surfaces

Assess only surfaces that could affect the intended user or operating agent.
Each surface must have `state: applicable | not_applicable | unknown` plus an
`evidence` reference or a reason evidence is unavailable:

- UI;
- cockpit;
- CLI;
- MCP;
- API/SDK;
- error recovery;
- permissions;
- rollback;
- human handoff;
- agent handoff;
- next-action guidance.

Do not turn this list into a requirement to build every surface. `unknown`
means inspect or ask; `not_applicable` requires a short contextual reason.

## Learning-velocity measures

During the manual pilot, capture direct observations when available:

```text
evidence_to_candidate
candidate_to_first_test
test_to_decision
repeated_explanations
human_attention
unused_output
rework_and_defects
validated_benefit
use_after_30_days
```

Every measure records `value`, `unit`, `evidence_ref`, and `status`, where
`status` is `observed`, `unknown`, `not_measured`, or `not_applicable`.
Do not infer missing durations, counts, benefit, or continued use. These
measurements support comparison and diagnosis. Telemetry is not proof of product
value or a universal score.

## Artifact-proximate product catalyst

Activate `artifact-proximate-product-catalyst` only when all are true:

- a first runnable artifact or equivalent observable experience exists;
- an intended user and outcome are known or a human is available to clarify;
- inspection can stay inside the stated authority and privacy boundary; and
- a product/value diagnosis could change a near-term decision.

The catalyst inspects evidence, identifies current project position, evaluates
only applicable experience surfaces, performs the routine-purpose and
build-refusal assessments, and proposes the smallest evidence-producing
experiment with success, failure, and stop signals. Stop when artifact evidence
is absent, the intended user/outcome cannot be established, authority is
ambiguous, or the request requires work allocation, edits, release, self-
approval, or system mutation. It is a specialist under the phase owner, not a
second project manager.

For one-human operation, return one digest with no more than three immediate
action asks. Everything else stays in drill-down evidence or a quiet/watch
state. The catalyst may not create recurring work merely to complete its own
checklist.

Durable workstream `state` is closed to the implemented attention-kernel
vocabulary: `proposed`, `active`, `paused`, `snoozed`, `incubating`, `merged`,
`superseded`, or `archived`. Scrum `focus-window`, readiness, validation,
delivery, blocking, and research stages are candidate overlays; they must not be
written into the durable lifecycle field. Execution leases and exact dispatch
revisions are authority-plane events in the existing Portfolio OS ledger and
fold through `portfolio_execution.py`. A bare approval identifier is only an
attestation and never grants authority. An independent trusted provider must
verify a typed, time-bounded attestation bound to the exact authority-event
digest; reused identifiers invalidate all of their uses. The default is
deny-all, and the kernel never launches an agent or mutates Git.

## Lifecycle routes

### Capture and shape

1. Capture the idea without creating Git artifacts.
2. Search related work and report coverage.
3. Propose `continuation`, `sibling`, `experiment`, `contradiction`,
   `possible_duplicate`, or `independent`; preserve both identities.
4. Recommend capture-only, attach, promote, incubate, or discard. A human
   confirms promotion and subjective relationships.

### Plan

1. Define one outcome and non-goals.
2. Split only independently testable outcomes into workstreams.
3. Name acceptance evidence and the smallest next action before proposing active execution.
4. Separate reviewed dependencies from proposed edges. Detect cycles and use
   `unlock frontier`, not `critical path`, unless reviewed durations exist.
5. Propose branch/worktree boundaries only after promotion.
6. Hand approved execution to `$dad-work-router`; the PM skill coordinates but
   does not act as the implementation worker.

### Execute and recover

1. Confirm a human-approved execution-lease record or return a lease-request packet.
2. Keep Today at three or fewer and reveal overflow.
3. Close sessions with evidence, a state candidate, next action, blockers,
   validation status, and a resume capsule.
4. Reconstruct intent before cleanup. Offer resume, re-scope, attach, snooze,
   incubate, supersede, abandon, archive, or inspect further. Never delete.

### Research

Track question, informed decision, source coverage, evidence for and against,
falsification, uncertainty, synthesis, and stopping condition. Use the overlay
`question-framed`, `source-map`, `collecting`, `synthesizing`, `falsifying`,
`decision-ready`, `handed-off`, or `incubating`. Source count alone never means
decision-ready.

### Validate, deliver, and review the portfolio

1. Compare acceptance evidence with outcome and non-goals.
2. Run independent checks and state failures and untested paths exactly.
3. Require a named waiver for missing evidence.
4. Record owner, reviewer, delivery boundary, retained authority, and rollback.
5. Rebuild portfolio views from source evidence. Keep intentionally quiet work
   quiet and distinguish proposed dependencies from reviewed blockers.

## Routing and humane attention

- Exact inventory: deterministic code or Luna/low.
- Phase ownership, decomposition, research, or recovery: Terra/medium; use high
  only for material ambiguity.
- Cross-project architecture, sovereignty, privacy, or conflict: Sol/high after
  cheaper evidence collection.
- Fable: manual packet only after unresolved high-consequence disagreement.
- Default to one digest with at most three human action asks.
- Suppress unchanged and dismissed fingerprints until material evidence changes.
- Treat lease expiry as a return-state candidate, not failure or abandonment.
- Never use guilt language.

## Human gates

Require human approval for idea-to-project or project-to-workstream promotion,
subjective relationships, dependency promotion, lifecycle transitions, lease
grant or renewal, Git/worktree mutation, task/calendar/notification writes,
delivery, acceptance waivers, abandon/archive/delete/cleanup, sovereignty
transfer, and promotion of policies, skills, triggers, or routines.

## Acceptance and kill criteria

- Capturing an idea creates no project, task, branch, worktree, lease, or reminder.
- Multiple ideas remain distinct until human promotion.
- Similarity never merges identities.
- Missing/expired lease evidence blocks the skill's execution recommendation;
  do not claim kernel enforcement until a lease contract is implemented.
- Today never exceeds three and overflow remains visible.
- Quiet, snoozed, or unchanged-dismissed work stays silent.
- Proposed dependencies cannot block work or enter the unlock frontier.
- Identical input fingerprints produce identical portfolio projections.
- No routine mutates Git, tasks, calendars, notifications, delivery, or cleanup.
- Stop if the workflow creates artifacts without approval, hides WIP, ranks by
  age alone, claims complete coverage with unavailable sources, exposes private
  payloads, lets task-system status establish project identity, or lets an agent
  approve its own material output.
