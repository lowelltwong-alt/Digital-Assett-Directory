# Load-Bearing Decision Review Asset

Status: curated asset evidence; candidate-only graph and scoring semantics still apply.

## Asset Identity

- Asset pattern id: `load_bearing_decision_review_system`
- Asset family: governed learning loop system; security and governance gate system; proposal-to-promotion workflow
- Primary components:
  - `registry/learning-rule-registry.json`
  - `docs/LOAD_BEARING_DECISION_REVIEW.md`
  - `templates/load-bearing-decision-review.template.md`
  - `registry/context-tag-registry.json`
  - `docs/DETERMINISTIC_LEARNING_RULES.md`
  - governance and learning-loop tests

## Why This Is A Digital Asset

This is a reusable workflow asset, not only a document. It turns a repeated planning failure mode into a deterministic review process: identify a load-bearing decision, assign a risk tier, require the right review depth, capture red-team and premortem findings, define rollback and kill criteria, and preserve the evidence for future agents.

The asset is high leverage because it protects decisions that can silently multiply through schemas, registries, scoring formulas, roadmap gates, governance hooks, source-boundary rules, automation, dependencies, and future-agent defaults.

It is also an asset-use pay-forward workflow. When an agent uses this review system, the useful artifact is not only the chosen decision. The agent should also record how the review system was used, what issue or potential issue it helped assess, what parts were useful or too heavy, where it should be reused, where it should be avoided, and what a future agent should do next.

## Useful Future-Agent Information

Future agents should use this asset before implementing or promoting a decision that changes shared contracts, scoring, ranking, calibration defaults, source mutation policy, scan scope, CI/hooks, governance, security, privacy, or roadmap gates.

Use it to answer:

- Is this decision high, medium, or low risk?
- Which downstream files, repos, agents, generated outputs, labels, or users could be affected?
- What fresh-eyes review should be requested?
- What A/B or bounded comparison would reduce uncertainty?
- What rollback and kill criteria should exist before promotion?

After using it, future agents should run or submit `DAD_ASSET_USE_FEEDBACK_V1` feedback with:

- issue or potential issue addressed;
- parts of the review workflow used and skipped;
- reuse-when and avoid-when context;
- pay-forward guidance;
- next-agent action;
- observed usefulness and observed futurefulness.

## Current Value

Current value is high because the core rule is reviewed, preflight/midflight can surface it, and tests validate the learning-rule acknowledgement path. The asset already changes agent behavior during relevant work.

Current-value limits:

- The workflow has only early DAD-local usage evidence.
- Cross-repo examples are not yet reviewed.
- The cost of over-triggering the gate has not been calibrated.

## Upside And Lift Conditions

Upside is very high if the workflow accumulates reviewed examples across repos and becomes a reliable early-warning system for risky defaults.

Lift conditions:

- Add reviewed decision records from at least three different asset families or repos.
- Measure where fresh-eyes review caught missed downstream effects.
- Record cases where the rule correctly stayed low risk and avoided unnecessary ceremony.
- Connect decision records to later outcomes: avoided rework, rollback used, false positives, false negatives, or downstream failures.

## Missing Pieces

- A small reviewed corpus of high, medium, and low risk decision examples.
- Precision/recall style review for trigger quality.
- A lightweight report showing which repo decisions are repeatedly high risk.
- A reviewed policy for when a second AI review is required versus optional.
- Paired before-use and after-use records showing how this workflow performed in real builds.
- Calibration of when this workflow is helpful versus overly heavy.

## Candidate Graph Connections

Useful candidate edges include:

- `requires_human_gate` from high-risk decisions to the review workflow.
- `supports_but_cannot_override` from fresh-eyes review to human decision authority.
- `should_precede` from this workflow to schema, scoring, roadmap, governance, and automation changes.
- `learned_from_attempt` from later postflights and repo events back to this asset.

## Safety Notes

Do not treat this asset as proof that a proposed decision is correct. It is a review mechanism. It can raise attention, structure disagreement, and preserve evidence, but it cannot override source authority, human gates, tests, security review, or roadmap acceptance evidence.
