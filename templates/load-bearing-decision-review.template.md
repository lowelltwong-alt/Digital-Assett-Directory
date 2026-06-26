# Load-Bearing Decision Fresh-Eyes Review

Use this template when a software, repo, roadmap, schema, scoring, governance, dependency,
automation, or source-boundary decision may affect downstream work.

## Request

You are reviewing a potentially load-bearing decision with fresh eyes. Stay read-only unless
explicitly authorized. Do not edit labels, generated files, roadmap status, source repos, or
governance settings. Treat generated evidence as candidate-only.

## Context

- Hub or repo:
- Mission:
- Authority boundaries:
- Current phase or roadmap gate:
- Relevant front-door files read:
- Relevant source files or evidence:
- Known exclusions or forbidden paths:

## Decision Under Review

- Decision:
- Proposed risk tier: high | medium | low
- Why the implementer thinks this tier fits:
- Downstream blast radius:
- Affected files, schemas, commands, repos, agents, generated outputs, labels, or users:
- Reversibility:
- Rollback path:

## Options

| Option | Summary | Benefits | Risks | Unknowns | Rollback cost |
|---|---|---|---|---|---|
| A |  |  |  |  |  |
| B |  |  |  |  |  |
| Defer/do nothing |  |  |  |  |  |

## Validation Plan

- Required commands:
- Required tests:
- Human gates:
- Stop conditions:
- Evidence required before promotion:

## What To Red-Team

Please answer:

1. Is the proposed risk tier correct? If not, what tier and why?
2. What downstream effects did the implementer miss?
3. What false positives, false negatives, or misleading metrics could this create?
4. What could future agents over-trust or apply out of context?
5. What would the six-month premortem say caused failure?
6. Is there a better option, hybrid, smaller slice, or safer order?
7. What A/B or bounded comparison would improve decision quality?
8. What validation, rollback, monitoring, or human gate is missing?
9. Should we proceed, defer, or stop for more human review?

## Output Format

Return:

- verdict: proceed | proceed_with_changes | defer | stop_for_human_review
- corrected_risk_tier:
- top_findings:
- missed_downstream_effects:
- premortem:
- A/B or bounded experiment:
- recommended changes:
- remaining unknowns:
- evidence reviewed:

Do not rewrite the implementation. Give decision-quality advice and cite concrete evidence.
