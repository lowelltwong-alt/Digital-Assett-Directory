# Artifact Honesty And Scoped Observation Lesson

Evidence date: 2026-06-30

Source: user-provided lesson from another repo. The operative lesson was that
Claude caught two important boundaries:

- Cursor's honesty is useful, but the honesty must live in the durable artifact,
  not only in chat.
- An overnight pass must be its own scoped read-only observation task, not a
  continuation of the chunking handoff.

DAD lesson record:

```text
dad:lesson:1acd128b-b896-521f-a112-f12eb0bd7b78
```

## Candidate Lesson

When an agent discovers limitations, skipped work, uncertainty, scope drift, or
important caveats, those caveats must be written into the artifact that future
agents will read. Chat honesty is not durable enough.

When a later background, overnight, or extended review pass follows a prior
handoff, it should start as a separate scoped read-only observation task with
its own route, scope, validation plan, stop conditions, and output artifact.
It should not silently inherit the authority boundary of the previous handoff.

## Applies When

- A handoff, report, index, seed artifact, review packet, or generated candidate
  artifact will guide future agents.
- The agent knows important uncertainty, exclusions, caveats, or unverified
  assumptions.
- A background, overnight, or extended pass is proposed after another task such
  as chunking, scanning, calibration, or handoff writing.
- The work is read-only observation and should not mutate source repositories.

## Does Not Apply When

- The work is pure chat brainstorming and produces no downstream artifact.
- The durable artifact already states scope, checked inputs, unchecked inputs,
  caveats, candidate status, and stop conditions.
- The follow-up pass already has its own explicit preflight, task boundary,
  read-only scope, and output artifact.

## Required Actions

- Put honesty into the artifact: what was checked, what was not checked, what is
  uncertain, what is candidate-only, and what could be wrong.
- Treat overnight/background work as a new observation task unless a human
  explicitly says it is the same task.
- Keep read-only observation separate from implementation, promotion,
  mutation, and scoring changes.
- If the observation may affect future task order or defaults, carry
  `applies_when`, `does_not_apply_when`, and `danger_if_misapplied`.

## Danger If Misapplied

If honesty remains only in chat, future agents may trust a polished artifact
that omits known limitations. If an overnight pass inherits the wrong handoff
boundary, it may read too broadly, mutate sources, blend observations into the
wrong task, or present unverified background findings as completed work.

## Status

Candidate lesson only. This note does not mutate
`registry/learning-rule-registry.json` and does not make the rule deterministically
enforced. Promotion to a reviewed learning rule should be a separate human gate.
