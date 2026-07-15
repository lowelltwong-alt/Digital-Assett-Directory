# AI-Native Process Pilot

Status: candidate manual pilot; not enabled automation.

This pilot tests whether artifact-proximate product diagnosis and lightweight
learning-velocity evidence improve decisions without creating process work for
its own sake. It does not change project authority, schedule agents, promote a
trigger, write another repository, or require every project to run an end-to-end
product workflow.

## Scope and duration

- Duration: four weeks of observed work, extended only by a named human.
- Workstreams: exactly two bounded workstreams at a time: one internal
  DAD/cockpit workflow and one user-facing product workflow selected under that
  repository's authority.
- Comparison: use the nearest comparable prior workstream when available, plus
  a before-pilot baseline recorded before the catalyst review.
- Operation: manual invocation only. No scheduler, daemon, hook, notification,
  external mutation, or persistent automation is enabled by this document.
- Data movement: no cross-repo writes, transcript ingestion, external-source
  collection, or source/skill/trigger promotion.

## Entry criteria

Both workstreams must have:

1. a stable workstream identity and authority owner;
2. a bounded intended user and outcome;
3. a first runnable artifact or equivalent observable user/agent experience;
4. current acceptance evidence, non-goals, and known privacy constraints;
5. a named human willing to make the resulting product decision; and
6. a recorded baseline with unknowns left explicit.

If any entry criterion is missing, do not manufacture it. Return the smallest
clarification or evidence-gathering action and keep the workstream out of the
pilot.

## Manual pilot sequence

For each eligible workstream:

1. Record the baseline without rewriting prior history.
2. Run the routine-purpose/expiry assessment and build-refusal assessment.
3. Inspect first-runnable-artifact evidence and only applicable experience
   surfaces.
4. Produce at most one smallest evidence-producing experiment.
5. Give the human no more than three immediate action asks in the combined
   digest.
6. If approved, hand execution to the normal governed implementation route.
7. Record observed learning-velocity measures after the first test and decision.
8. At 30 days, record use status as observed, unknown, not measured, or not
   applicable; do not interpret silence as value or failure.

Human administration for the pilot must stay at or below 15 minutes per
workstream per review. If evidence collection exceeds that ceiling, stop or
simplify before asking for more attention.

## Evidence record

Use one record per workstream and preserve evidence pointers rather than copied
private payloads:

```text
pilot_id
workstream_id
authority_owner
as_of
baseline_comparison_ref
intended_user_and_outcome
artifact_evidence_refs[]
routine_purpose_and_expiry_assessment
build_refusal_assessment
experience_surface_assessment[]
smallest_evidence_producing_experiment
success_signal
failure_signal
stop_signal
learning_velocity_measures:
  evidence_to_candidate
  candidate_to_first_test
  test_to_decision
  repeated_explanations
  human_attention
  unused_output
  rework_and_defects
  validated_benefit
  use_after_30_days
human_action_asks[]
initial_decision: pilot | watch | reject | unknown
final_disposition: adopt | revise | watch | reject | stop | unknown
decision_evidence_ref
governance_or_privacy_delta
next_review_condition
unknowns[]
```

Each learning-velocity measure follows the project-management contract and may
be `unknown` or `not_measured`. Telemetry is candidate evidence, not proof of
benefit, causation, productivity, product-market fit, or release readiness.

## Exit criteria

Complete the manual pilot only after:

- both workstreams have a baseline and artifact-proximate review;
- approved experiments, if any, have success/failure evidence or a documented
  reason no experiment ran;
- human attention and the other learning-velocity measures are recorded without
  fake precision;
- governance, privacy, untested paths, and comparison limits are explicit;
- a human decides adopt, revise, watch, reject, or stop for each tested practice;
  and
- no automation, trigger, role, policy, or cross-repo change is promoted from
  the pilot without its separate authority gate.

## Kill and stop criteria

Stop the affected workstream immediately when:

- human administration exceeds 15 minutes for a review;
- the pilot grows documents without producing clearer decisions;
- it weakens security, privacy, source authority, independent verification, or
  another governance gate;
- the catalyst allocates work, edits artifacts, approves itself, releases, or
  mutates a system;
- the digest asks for more than three immediate human actions;
- the proposed experiment is not bounded, measurable, reversible, or owned;
- private evidence would have to cross a repository boundary; or
- source/transcript material would be collected or promoted without its own
  approval.

Stop the portfolio pilot if no measurable decision-speed, re-explanation,
human-attention, unused-output, rework, or validated-benefit improvement is
observed after six completed workstreams. Six workstreams is an evidence gate,
not permission to silently expand this initial two-workstream pilot; each later
workstream still requires a human continuation decision.

## Promotion boundary

The pilot may produce recommendations and trigger feedback. Trigger-radar
authority owns any later trigger trial or promotion. Delivery-plan acceptance
remains with the delivery-plan steward, and implementation/release remains with
the existing governed routes. A successful pilot does not enable scheduling or
make the product catalyst mandatory for every project.
