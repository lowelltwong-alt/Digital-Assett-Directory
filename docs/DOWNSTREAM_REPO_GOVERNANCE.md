# Downstream Repository Governance

## Local installation

```text
asset-dir agent install --repo C:\path\to\repo
```

The installer can add an idempotent managed block to `AGENTS.md`, create a
`CLAUDE.md` import when absent, add `.digital-asset-directory.yml`, create the
lightweight `.digital-asset/mail/` mirror, and install a tool-neutral `pre-push`
hook.

## Flow

```text
preflight -> context pack -> work -> tests -> postflight -> central lesson/handoff -> pre-push gate
```

## AI environment capability guidance

Downstream repos may add a short advisory pointer to the hub's AI environment
capability matrix when they want Codex, Cursor, Claude Code, or another agent
runtime to choose appropriate skills, subagents, MCP servers, hooks, plugins,
connectors, or background/cloud agents.

Keep the full matrix outside mandatory repo contracts until the target repo
owner reviews it. A safe adoption path is:

1. add a link or local copy as advisory documentation;
2. state which AI environments the repo actually supports;
3. keep local authority in the target repo's `AGENTS.md`, `CLAUDE.md`, Cursor
   rules, hooks, CI, and review policy;
4. record last-verified and stale-after dates;
5. capture postflight feedback when a capability was useful, missing, risky, or
   misleading.

Do not auto-install tool-specific MCP servers, hooks, plugins, skills, cloud
agents, or subagent configurations across repos without the normal source
boundary, security, provenance, and human-gate review.

## DAD mailboxes

Persistent downstream repos may add a lightweight mailbox:

```text
.digital-asset/mail/README.md
.digital-asset/mail/inbox.jsonl
.digital-asset/mail/outbox.jsonl
.digital-asset/mail/archive.jsonl
```

The mailbox is suggestion transport only. DAD may collect outbox packets and
deliver inbox packets under `.digital-asset/mail/`, but the target repo decides
whether to adopt any lesson, workflow, asset, taxonomy, capability, or
governance notice. Mail must not overwrite source code, registries, schemas,
hooks, AI authority files, or sensitive files.

Use `templates/downstream/MAIL_README.md` as the optional repo-local README.
Preflight does not collect mail. It only reports whether the repo's digest is
stale so daily checks do not run multiple times per day.

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
