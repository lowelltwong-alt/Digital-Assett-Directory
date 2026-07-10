---
name: subagent-continuous-improvement
description: Run self-review, independent review, routing audit, and thresholded human-gated instruction improvement for reusable subagent roles.
---

# Subagent Continuous Improvement

Review every attempt, then reuse `registry/subagent-evaluation-methodology.json`
(`0.1.0`) and its existing attempt/evaluation record contract. Do not invent a
parallel score or record. The weighted mean is 30/20/20/15/15 over correctness,
scope discipline, evidence traceability, efficiency/compute fit, and escalation
calibration; range 0-100; missing evidence is `insufficient_evidence`, never
zero. Preserve counterevidence and context.

The acting agent writes a concise self-review. A different agent/model reviews
the same bounded evidence independently; any model may review any other, and
self-review and parent review do not count as independent evidence. Store only
privacy-safe summaries and evidence references, never raw transcripts, hidden
reasoning, secrets, private rows, or long blobs.

## Peer-Check Mesh and Routing

Luna, Terra, Sol, and the routing auditor are peers in a bidirectional review
mesh, not a permanent hierarchy. Luna may catch Terra or Sol on bounded
evidence; Terra may audit Sol's proportionality; and any different model may
independently review another. The low/medium/high/xhigh ladder controls review
cost and risk escalation only. It does not confer authority, correctness, or
standing superiority.

The distinct `routing-auditor` assesses task complexity plus material/dataset
complexity, size, ambiguity, sensitivity, and consequence. It judges whether
Luna/Terra/Sol and low/medium/high/xhigh effort were proportionate, states the
factor-based rationale, and recommends a cheaper or stronger route when useful.
Nuanced audits default to Terra at medium effort. It recommends only and never
silently switches an in-flight agent; any reroute happens only at an explicit
boundary with owner/orchestrator approval.

- **Luna, low:** routine bounded checks; it may challenge any peer when it has
  concrete evidence of a gate, scope, privacy, or calibration issue.
- **Terra, medium by default, high when warranted:** nuanced audit and
  proportionality judgment; it may review any peer, including Sol. Check when
  evidence is incomplete, score below 70, self/independent delta >=15, or
  privacy/authority risk is present. Check comparable context and
  counterevidence.
- **Sol, high/xhigh only:** review or propose changes for a concrete gate
  failure, or the same
  normalized failure class in >=2 of the last 5 comparable attempts (>=3 of 10
  when noise is high). Propose the smallest testable instruction change with
  success, non-goals, and rollback. An imperfect score alone is not an
  exception.

A gate failure is an exception candidate, not proof of an instruction defect;
the peer mesh separates operator error, task mismatch, missing context, and
instruction defect. Fable is a rare, manual external architecture escalation
for unresolved super-high-risk boss/architect disagreements; it is not a
standing superior or routine review tier. A named human copy/pastes a
privacy-safe packet containing all positions, evidence, counterarguments, and
unknowns. Fable explains pros and cons, red-teams and premortems each option,
recommends a decision, and may propose a non-binary synthesis. Only a named human may
approve, apply, or reject Sol's change. Approval must cite role/version,
evidence, independent review, bounded diff, test cohort, success threshold,
and rollback. Keep prior attempts and instructions immutable.

Prefer one precise rule/example/checklist item over broad prompt prose. Remove
duplicated or low-yield wording and reject caveats without a falsifiable
validator. If subagents are unavailable, run explicit checklists and mark
independence unavailable; never fabricate it.
