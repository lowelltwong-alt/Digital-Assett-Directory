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

## Cross-machine or remote-only work

The seed's strongest enforcement is local. For remote agents, add the optional workflow template under `templates/downstream/github-workflow.yml` and commit downstream handoff manifests under `.digital-asset/handoffs/`. The central scanner can ingest those manifests later.

## Bypass policy

Emergency bypass must be explicit, logged, and reviewed. Do not silently disable hooks or delete handoff history.
