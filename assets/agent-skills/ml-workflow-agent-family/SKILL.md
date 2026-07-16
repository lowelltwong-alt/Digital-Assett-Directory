---
name: ml-workflow-agent-family
description: Decide when machine learning is appropriate, select and execute a governed ML workflow, route a model-independent worker-checker-foreman-boss mesh, audit data and evaluation risks, monitor deployed models, or refresh ML research and technique libraries. Use for ML opportunity assessment, experiment design, implementation, validation, deployment readiness, drift review, technique research, and ML-agent lifecycle decisions.
---

# Machine Learning Workflow Agent Family

Compose this ML specialization with DAD's existing routing, graph, research,
and subagent-improvement contracts. Do not redefine their authority or hard-code
a provider as an agent identity.

## Start With The Decision

1. Run DAD preflight and inspect `registry/ml-agent-family-registry.json`.
2. State the end goal, decision owner, target population, prediction or action,
   error costs, latency, privacy, and the no-ML baseline.
3. Recommend ML only when data, feedback, evaluation, maintenance, and expected
   value justify it. Prefer rules, search, statistics, optimization, or process
   repair when they solve the goal more safely or cheaply.
4. Search `registry/ml-technique-registry.json` by problem shape and constraints.
   Carry forward `applies_when`, `does_not_apply_when`, and
   `danger_if_misapplied` from every selected technique.
5. Read `references/ML_WORKFLOW_CONTRACT.md` before implementation or deployment.

## Route The Family

- Use the existing Luna/Terra/Sol capability aliases through
  `personal-hierarchical-agent-mesh` and `subagent-peer-review-routing`.
- Treat boss, architect, foreman, worker, checker, data steward, researcher, and
  lifecycle curator as responsibilities, not permanent model or provider IDs.
- Resolve current models at runtime from availability, tools, context, privacy,
  cost, and consequence. Dated adapter observations in the family registry are
  hints only and may be stale.
- Keep one writer and a distinct independent checker. A worker never approves
  its own split, metrics, leakage analysis, deployment, or instruction change.
- Use the declared roles in `subagents.yaml` for bounded delegation. Search them
  through DAD's subagent directory; declarations are not competence ratings.

## Execute The ML Lifecycle

Use the workflow cards in the family registry and preserve evidence for:

1. problem and authority framing;
2. data provenance, consent, vintages, labels, and leakage controls;
3. deterministic or statistical baselines;
4. split strategy and experiment contract before training;
5. technique selection with contraindications;
6. reproducible implementation and environment capture;
7. a DAD midflight checkpoint whenever data, split, metric, technique, runtime,
   authority, scope, or proof obligations change materially;
8. independent metric, calibration, robustness, fairness, privacy, security,
   cost, and latency review as applicable;
9. human deployment approval, rollback, observability, and incident ownership;
10. drift, decay, retraining, retirement, and supersession review.

At a midflight trigger, stop work, run DAD midflight with the current session,
context, affected path, and any required learning-rule acknowledgement, then
revise and re-lock the experiment contract before continuing. Availability of
a new model or technique never authorizes silent rerouting or scope expansion.

Stop when the target is not measurable, source authority is unknown, sensitive
data lacks approval, leakage cannot be ruled out, a domain overlay is missing,
or the proposed validation cannot distinguish the model from the baseline.

## Improve Without Prompt Bloat

Use `subagent-continuous-improvement` for attempt-first ratings, independent
grading, preserve-simple decisions, held-out trials, and human-gated changes.
Attribute a deficit to the agent, model route, tool, input, data, workflow,
handoff, evaluator, domain overlay, harness, or downstream specialist before
editing instructions.

Leave a role alone when deterministic checks, negative cases, latency/cost
evidence, and held-out confirmation show that extra intelligence would add
complexity without value. Adapt a role when interfaces remain compatible;
rewrite it only when the old contract cannot satisfy a new capability,
privacy, tool, or evidence boundary. Never auto-promote, auto-supersede, or
delete prior revisions.

## Refresh Research

Use the `workflow:ml-frontier-research-refresh` card every 14 days only after a
human activates an automation. Research is primary-source, pointer-only,
deduplicated, screened, and candidate-only. A paper, benchmark, model claim, or
library release does not change technique guidance until applicability,
counterevidence, replication or local eval design, compatibility, and a human
promotion decision are recorded.

## Preserve Authority

The source repository owns its data and meaning. Named humans own product,
domain, privacy, security, deployment, release, and exception decisions. This
skill produces candidate recommendations and evidence; it does not authorize
data access, training, deployment, recurring automation, cross-repo mutation,
or live global-skill installation.
