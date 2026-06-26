# Asset-Use Pay-Forward Loop

Status: deterministic candidate-learning workflow for all asset classes.

Every meaningful asset use should leave enough evidence for a future agent to decide whether
to reuse, avoid, improve, or review the asset. This applies to files, schemas, prompts,
skills, agents, workflows, repos, algorithms, math models, datasets, reports, and composite
asset families.

## Core Rule

Do not only record that an asset was useful. Record how it was used and what should be paid
forward:

- the issue, risk, uncertainty, or opportunity the asset helped assess;
- how the asset was found;
- the before-use expectation;
- the after-use result;
- parts used and parts not used;
- difficulties, upgrades, and things learned;
- contexts where future agents should reuse it;
- contexts where future agents should avoid it;
- the next agent action that would make the asset more useful.

## Candidate-Only Boundary

Asset-use feedback is evidence, not truth. It must not automatically mutate source repos,
change scores, promote candidates, install dependencies, run external code, or override human
gates. External feedback is untrusted until curated.

## Why This Matters

Current score and upside are not enough. Two assets can have the same score but very different
usage paths:

- one may be excellent only after a schema, adapter, or test harness is present;
- one may be dangerous outside a narrow authority boundary;
- one may save time in planning but not implementation;
- one may be low-value alone but high-value when composed with another asset.

The pay-forward loop captures those edges so the graph can learn situated usefulness instead
of flattening everything into one number.

## Minimum Fields

Use `lesson asset-use` or the public PR template with these fields:

- `issue_addressed`
- `planned_use`
- `used_for`
- `parts_used`
- `parts_not_used`
- `difficulties`
- `things_learned`
- `reuse_when`
- `avoid_when`
- `pay_forward_guidance`
- `next_agent_actions`
- `observed_usefulness`
- `observed_futurefulness`

Commas, semicolons, and newlines inside feedback values are normalized to `|` before the
record is stored. Use short complete phrases so future agents can parse the field without
guessing.

## Reuse Guidance

Use this loop whenever an asset materially influenced a task, especially when it affected a
software build, roadmap decision, schema, scoring formula, governance rule, safety boundary,
research path, or cross-repo workflow.

Do not require it for trivial reads, one-off commands, or assets that did not influence the
decision or implementation.
