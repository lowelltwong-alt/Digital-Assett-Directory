# Machine Learning Workflow Contract

Use this contract for a material ML recommendation, experiment, implementation,
deployment, or lifecycle review. The machine-readable workflow and dependency
cards live in `registry/ml-agent-family-registry.json`; technique cards live in
`registry/ml-technique-registry.json`.

## 1. Frame The Decision

Record the end goal, accountable decision owner, unit of analysis, target
population, prediction horizon or action, acceptable latency, error costs,
constraints, and success criteria. Separate prediction quality from whether the
result improves the downstream decision.

Create and test a no-ML alternative. ML is not indicated when rules, search,
statistics, optimization, better instrumentation, or process repair meet the
goal with lower lifecycle cost and risk.

## 2. Establish Data Authority

Name source authority, provenance, licenses or consent, sensitivity, retention,
label origin, time semantics, missingness, sampling, and expected shift. Preserve
raw observations and distinguish event time, observation time, label time, and
availability time. Do not let future information enter historical features.

Stop on unknown authority, unapproved sensitive data, unbounded collection,
untraceable labels, or a population definition that changes between training
and evaluation.

## 3. Lock The Experiment Before Training

Define the baseline, split unit, temporal or group isolation, metrics, slices,
thresholds, uncertainty, calibration checks, resource budget, negative cases,
and kill criteria. Select splits by the real deployment boundary: time, entity,
site, geography, device, document, or user—not random rows by habit.

Use nested selection or a final untouched test set when tuning materially. Keep
feature, preprocessing, resampling, and threshold fitting inside the training
fold. Record all exclusions and failed attempts.

## 4. Select Techniques From Evidence

Search the technique registry. For every candidate, carry forward prerequisites,
applicability, non-applicability, danger, evaluation requirements, and source
pointers. Compare at least one simple candidate with a more complex candidate
when complexity could materially increase maintenance or failure modes.

Do not select an algorithm from popularity, leaderboard position, novelty,
graph centrality, or one aggregate score. Match inductive bias and operational
constraints to the problem and data.

## 5. Implement Reproducibly

Pin data snapshots or immutable query identities, code revision, dependencies,
random seeds where meaningful, feature definitions, model configuration, and
hardware/runtime assumptions. Separate pure transforms from I/O and training
side effects. Test schema boundaries, leakage guards, invariants, serialization,
and deterministic preprocessing.

Prefer maintained libraries over handwritten algorithms unless the task is
research, the implementation is a bounded educational artifact, or a proven
gap requires custom code. Record license, security, compatibility, and upgrade
constraints before adoption.

## 6. Recheck At Midflight

Stop and run DAD midflight when a material data, label, split, metric, technique,
runtime, dependency, authority, privacy, scope, or proof-obligation change
appears. Record the affected path and context, acknowledge any applicable
learning rule, reassess blast radius and contraindications, and revise and
re-lock the experiment contract before implementation resumes. A new model,
paper, library, or available tool is evidence to review, not permission to
reroute or broaden the task silently.

## 7. Validate Independently

A checker who did not build the model must replay the locked acceptance checks.
Validate baseline lift, uncertainty, calibration, slice behavior, robustness to
plausible shifts, cost/latency, reproducibility, and operational failure modes.
Add fairness, privacy, security, safety, or regulated-domain validation when the
context requires it. Missing evidence is insufficient evidence, not a zero or a
pass.

## 8. Gate Deployment

Deployment requires named human approval, an owner, versioned artifacts,
observability, rollback, incident response, safe fallback behavior, and a
monitoring contract. Shadow, canary, or limited-scope trials are preferred when
the consequence or uncertainty is material. Do not make an offline metric the
sole deployment gate when downstream outcomes can be measured.

## 9. Monitor And Evolve

Track data quality, input and concept drift proxies, calibration, performance
when labels arrive, slice regressions, latency, cost, failures, and downstream
outcomes. Age alone does not make a model stale. Mark `watch`, `stale`, or
`superseded` only with a reason and evidence.

When a new model, provider, harness, library, paper, data source, or policy
appears, test compatibility and blast radius. Choose `no_change`, `adapt`,
`compose`, `rewrite`, `retire`, or `supersede_after_review`; preserve prior
revisions and rollback evidence.

## 10. Postflight

Report data and model identities, techniques considered, baseline, split,
metrics and slices, independent review, failed and unknown checks, deployment
state, graph/dependency changes, research inputs, lessons, and next review
trigger. Grade both the acting role and the workflow decomposition; never use a
self-grade as promotion authority.
