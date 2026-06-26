# Downstream Repository Governance

## Local installation

```text
asset-dir agent install --repo C:\path\to\repo
```

The installer can add an idempotent managed block to `AGENTS.md`, create a `CLAUDE.md` import when absent, add `.digital-asset-directory.yml`, and install a tool-neutral `pre-push` hook.

## Flow

```text
preflight -> context pack -> work -> tests -> postflight -> central lesson/handoff -> pre-push gate
```

## Load-bearing decisions

Before changing shared contracts, schemas, CI/hooks, governance, scoring/ranking,
roadmap gates, source-boundary rules, dependencies, migrations, or defaults that future
agents may inherit, classify the decision as high, medium, or low risk.

High-risk decisions require:

- explicit human attention;
- implementer self red-team and premortem;
- fresh-eyes review from another AI or human;
- rollback and kill criteria;
- a bounded A/B or comparison plan when feasible.

Use the hub template:

```text
templates/load-bearing-decision-review.template.md
```

## Cross-machine or remote-only work

The seed's strongest enforcement is local. For remote agents, add the optional workflow template under `templates/downstream/github-workflow.yml` and commit downstream handoff manifests under `.digital-asset/handoffs/`. The central scanner can ingest those manifests later.

## Bypass policy

Emergency bypass must be explicit, logged, and reviewed. Do not silently disable hooks or delete handoff history.
