---
name: subagent-continuous-improvement
description: Capture actor-claimed prediction receipts, run independent evidence and evaluator-integrity review, keep causal attribution explicit, and route only evidence-backed no-change or bounded human-gated improvements across domain-specific workflows.
---

# Subagent Continuous Improvement

Self-grading is diagnostic telemetry, never proof. Do not ask an agent to award
itself an authoritative aggregate grade. Before outcome evidence is visible,
lock the task contract and an explicit profile from
`registry/subagent-evaluation-profile-registry.json`, then record criterion-level
pass probabilities, confidence, falsifiers, anticipated failure modes, and
limitations with `asset-dir subagents self-assess`. The DAD runtime receipt time, not a claimed timestamp, establishes receipt chronology only.
It does not prove the actor identity or outcome blindness. Call a prediction pre-outcome
only when an orchestrator seals it before execution or validation and controls outcome access.

After the attempt, preserve immutable artifacts and use the existing attempt
evaluation methodology for bounded attempt evidence. A different reviewer makes
its verdict from the locked evidence before seeing the self prediction whenever
the workflow can support blindness. Then run `asset-dir subagents
integrity-review`. A hash proves record integrity only; it does not prove that an
artifact, claim, environment, grader, or reviewer is correct.

## Universal Loop and Domain Overlays

Use one universal control loop across domains:

1. lock the task and evaluation contract;
2. optionally seal a prediction when calibration is decision-relevant and outcome access is controlled;
3. preserve attempt and artifact evidence;
4. run deterministic and domain validation;
5. obtain independent review;
6. audit the evaluator for blindness, lineage, reciprocal review, identity bias,
   evidence replay, domain qualification, and holdout exposure;
7. test competing causal hypotheses before attributing a failure to a system layer;
8. choose no change or a bounded intervention;
9. compare on held-out shadow cases;
10. require a named human promotion and rollback decision; and
11. monitor drift, cost, latency, and regressions.

Do not use a universal cross-domain leaderboard. The universal loop governs
provenance, independence, calibration, experimentation, and authority. Domain profiles are candidate routing
contracts until their artifacts, validators, thresholds, qualifications, budgets, and hard
gates are executable; profile selection alone never proves domain validity. Financial algorithms require
leakage, out-of-sample regime, realistic cost/slippage/capacity, drawdown/tail,
and independent model-risk checks. Archaeological and historical claims require
artifact/citation provenance, context and chronology, observation-versus-
inference separation, counterevidence, contested interpretation, and ethical or
legal provenance. A qualified domain expert remains required where the profile
says so.

Profile selection is explicit candidate input. Do not infer a domain from private
prose, and do not apply a profile outside its `applies_when`,
`does_not_apply_when`, and `danger_if_misapplied` boundaries.

## Attribute Before Changing

An observed failure does not establish an instruction defect. Route a candidate
to one or more of these layers: agent instruction, model or effort route, tool,
input contract, context or data, workflow, handoff, evaluation harness, reviewer,
domain overlay, downstream specialist, preserve-simple, or observe-more.

Use the disposition vocabulary in the profile registry as future-safe candidate
vocabulary. The current kernel can expose missing evidence and broad hypotheses but cannot
localize most causal layers; use `human_attribution_required` until seeded ablations or
deterministic layer evidence identify a cause. Never auto-apply a change. In particular:

- `repair_evaluator` when the grader is gameable, uncalibrated, non-blind, or
  unable to replay evidence;
- `redesign_workflow_or_handoff` when the agent is locally correct but inputs,
  ordering, ownership, or handoffs create the failure;
- `compose_downstream_specialist` when a simple upstream role should remain
  stable and another role should interpret or extend its output;
- `no_change_freeze_candidate` when a simple deterministic role has a comparable
  passing cohort, negative/boundary evidence, proportionate latency and cost,
  no unresolved gate, and held-out shadow confirmation; and
- `collect_more_evidence` or `human_attribution_required` when causality is not
  localized.

For simple deterministic roles, first ask whether an agent is needed at all. Prefer exact,
property, metamorphic, or fuzz checks when they decide correctness. Keep any core agent
minimal and put optional prediction, validation, and review in the workflow wrapper. The
current kernel must not nominate a no-change freeze until runtime actor binding, criterion
outcomes, negative evidence, latency/cost evidence, and held-out confirmation are recorded.

## Independent Integrity Review

Identity separation alone is not independence. Check shared parent sessions,
model family, prompt or training lineage when available, reciprocal review
cycles, ordering, blindness to self scores, contamination, and domain
qualification. Use canaries, known-good/known-bad mutations, paraphrase and
position perturbations, prompt-injection tests, task/grader bug audits, and human
adjudication on held-out cases. A reviewer that fails these checks is itself an
improvement target.

Luna, Terra, Sol, and external reviewers are peers, not a permanent hierarchy.
Effort controls cost and unresolved risk. Use bounded deterministic checks or
Luna for routine completeness, Terra for nuanced integrity and attribution, and
Sol only for persistent high-leverage ambiguity or a bounded redesign. Fable is
a rare manual architecture escalation after unresolved high-consequence Codex
adjudication; never auto-send private evidence.

Store only privacy-safe summaries, categorical signals, hashes, and bounded
evidence references. Never store raw transcripts, hidden reasoning, secrets,
private source rows, or long source blobs. If independent review is unavailable,
say so; do not fabricate it.

Promotion requires a versioned candidate, held-out or shadow comparison against
the prior version, explicit success and non-regression criteria, cost and latency
measurement, rollback, and named human approval. Preserve prior attempts,
profiles, evaluators, and instructions immutably.
