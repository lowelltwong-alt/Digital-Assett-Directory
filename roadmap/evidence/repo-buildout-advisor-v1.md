# Repo Buildout Advisor V1 Evidence

Date: 2026-06-29

## Status

Implemented as a manual, local-only generated-candidate advisor. It recommends
how to improve one cataloged repo from current DAD evidence, but it does not
rescan, mutate source repos, call GitHub, call models, install hooks, promote
candidates to truth, change current scores, or mark roadmap phases complete.

## Methodology

Methodology version: `repo-buildout-advisor-v0.1`

```text
priority_score = 100 * (
  0.25 * repo_relevance
+ 0.20 * gap_severity
+ 0.20 * workflow_leverage
+ 0.15 * validation_readiness
+ 0.10 * evidence_strength
+ 0.10 * low_risk_bonus
)
```

All components are clamped to `0.0..1.0`. Failed required gates cap priority at
`25`.

Required gates:

- evidence gate;
- source-boundary gate;
- privacy gate;
- no-target-mutation gate;
- no-external-call gate;
- scan-watermark gate.

## Inputs

- catalog assets, edges, alerts, and latest scan summary;
- optional workflow-part usage guidance;
- optional manual-task queue;
- optional semantic-evolution candidates;
- optional background-connection candidates;
- optional bottom-up and top-down proposals.

Missing optional inputs are warnings, not hard failures.

## Red Team

- Lexical overlap can look like workflow fit; recommendations require asset IDs
  and dataflow/validation language before action.
- Cross-repo inspiration can look like permission to copy; the command marks it
  human-gated and source-boundary limited.
- Priority score can be over-trusted; reports state it is review order only.
- Generated inputs may be stale; outputs carry scan watermark warnings.
- Public-safe/privacy mistakes are the highest-risk failure; reports cite
  metadata and IDs rather than raw private source dumps.

## Acceptance

Acceptance requires schema/model validation, deterministic output tests, CLI
wiring, and full validation baseline. Generated outputs stay under `processed/`
and are ignored by Git.
