# Downstream Repository Governance

## Local installation

```text
asset-dir agent install --repo C:\path\to\repo
```

The installer can add an idempotent managed block to `AGENTS.md`, create a
`CLAUDE.md` import when absent, add `.digital-asset-directory.yml`, create the
lightweight `.digital-asset/mail/` mirror, and install a tool-neutral `pre-push`
hook.

For persistent repos, prefer reviewed DAD enrollment:

```text
asset-dir enroll plan --repo all --wave <id>
asset-dir enroll apply --repo <path-or-id> --approval-id <human-review-id>
```

Enrollment is the full governance install path. It requires the repo to appear
in reviewed `enrollment.repos` policy and writes only approved DAD surfaces:
mailbox, context map, governance map, data map, coding asset pointer, skill
checkout pointer, managed AI guidance blocks, and pre-push hook files. After
enrollment, normal DAD operation is mailbox-only under `.digital-asset/mail/**`.

See `docs/DAD_REPO_ENROLLMENT.md` for the contract, cadence, public-safe
pointer policy, and update flow.

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
6. check out DAD-managed agent skills by pointer or wrapper from
   `registry/agent-skill-library.json` when the repo wants reusable skill
   awareness and update notices.

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
.digital-asset/mail/.gitignore
```

The mailbox is suggestion transport only. DAD may collect outbox packets and
deliver inbox packets under `.digital-asset/mail/`, but the target repo decides
whether to adopt any lesson, workflow, asset, taxonomy, capability, or
governance notice. Mail must not overwrite source code, registries, schemas,
hooks, AI authority files, or sensitive files.

Agent review of inbox mail is triage only. Human review is required for local
adoption, and DAD must record an explicit human release before
private/internal/restricted/unknown-origin mail can be delivered to a
public-facing repo.

Use `templates/downstream/MAIL_README.md` as the optional repo-local README.
Preflight does not collect mail. It only reports whether the repo's digest is
stale so daily checks do not run multiple times per day.

## DAD coding asset pointers

Persistent repos may adopt a small pointer to DAD coding assets after local
approval:

```text
templates/downstream/AI_ASSETS_POINTER.template.json
templates/downstream/CODING_ASSET_MANAGED_BLOCK.md
```

The pointer tells future AI agents to run DAD preflight, consult DAD coding
assets and tactics, and report useful tactic feedback after material work. It
does not copy full DAD assets, install hooks, or authorize DAD to override local
repo canon.

## DAD agent skill checkouts

Persistent repos may adopt a small pointer or wrapper to DAD-managed agent
skills after local approval:

```text
templates/downstream/AGENT_SKILL_POINTER.template.json
templates/downstream/AGENT_SKILL_MANAGED_BLOCK.md
```

The checkout tells future agents which DAD skill ID, version, source path, and
return address to use. It does not copy full DAD skills, install plugins, create
hooks, configure MCP servers, or authorize DAD to mutate local repo files. DAD
mail may announce skill updates, retirements, or replacements; the target repo
decides whether to adopt them.

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
