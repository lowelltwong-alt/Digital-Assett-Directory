---
name: personal-portfolio-capacity-review
description: Run a manual, read-only portfolio capacity and bottleneck review across explicitly configured repositories, worktrees, plans, libraries, skills, subagent packs, learning loops, routines, and daemons. Use for a weekly shadow review, a human-decision backlog review, a stalled or partial-buildout audit, an iteration-cycle bottleneck investigation, or a request for a bounded worker-foreman-checker mesh that escalates only the highest-leverage unresolved decisions.
---

# Personal Portfolio Capacity Review

Produce one evidence-backed shadow packet. Keep every recommendation advisory
and every side effect human-gated.

## Read before review

Read:

1. `references/PORTFOLIO_CAPACITY_REVIEW_CONTRACT.md`;
2. the repo-local mission file validated by `schemas/repo-missions.schema.json`;
3. `schemas/portfolio-capacity-review.schema.json`;
4. applicable source-repository front doors and authority files;
5. existing DAD worker skills and role packs named in `subagents.yaml`.

Stop when the configured coverage roots, source authority, mission evidence, or
data boundary cannot be established without C3 payloads.

## Run the shadow workflow

1. Declare coverage by stable root and repository identifiers. Never place
   absolute private paths in tracked artifacts or the portable packet.
2. Collect deterministic metadata first: Git/worktree state, roadmap and
   acceptance gates, registered skills and role revisions, learning-loop
   receipts, measured command durations, and routine or daemon status.
3. Reuse the bounded worker roles listed in `subagents.yaml`. Treat missing,
   stale, invalid, and unavailable sources as coverage findings, not silence.
4. Route synthesis to `portfolio-capacity-foreman`. Apply the contract's exact
   categorical precedence; never calculate a numeric or composite score.
5. Escalate capability maturity and measured cycle questions to
   `capability-maturity-and-cycle-auditor`. Use the existing
   `sol-automation-workflow-architect` only when the threshold in the contract
   is met. Keep Fable manual-only after unresolved independent disagreement.
6. Keep deterministic V0 at zero semantic agent fan-out and mark foreman and
   checker attempts `not_dispatched`. For a separately authorized agent-assisted
   review, freeze one input fingerprint, then give
   `independent-capacity-review-checker` source evidence, schemas, and mission
   records without the foreman's conclusions. Only that mode may claim complete
   blind lineage.
7. Return at most three `human_asks`. Put every remaining candidate in
   `overflow`; do not hide WIP. Preserve suppressions and explicit wake
   conditions.
8. Validate the packet against the capacity-review schema. Label confirmed,
   inferred, disputed, and unknown findings distinctly.

## Boundaries

- Read metadata only by default and never include C3 payloads, secrets, raw
  conversations, private source rows, client content, or credentials.
- Do not start or stop daemons, alter Git or worktrees, modify repositories,
  schedule routines, notify people, install plugins, or change agent
  instructions.
- Do not treat age, graph centrality, source count, a plan, or model confidence
  as proof of abandonment, importance, completeness, or correctness.
- Keep the weekly routine at `candidate_specs_not_scheduled` until a human
  approves the exact cadence, execution surface, delivery surface, and scope.
- Keep source repositories authoritative for their missions and internal canon.
- Treat self-improvement as candidate feedback. Require independent evidence
  and human review before changing roles, prompts, routing, or policy.

## Output

Emit only the schema-valid packet plus a short human summary containing:

- coverage and unavailable sources;
- the three-or-fewer human asks;
- the highest-leverage bottlenecks and quiet defaults;
- disagreements, unknowns, suppressions, and wake conditions;
- the fan-out status, checker verdict or `not_run`, and any threshold-only
  escalation recommendation.
