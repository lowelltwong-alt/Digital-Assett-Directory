# Agent Operating Contract

This file is read by Codex and may be imported by Claude Code through `CLAUDE.md`.

## Read first

1. `AI_FRONT_DOOR.md`
2. `MACHINE_NAVIGATION_MANIFEST.json`
3. `registry/source-of-truth.json`
4. `registry/design-authority.json`
5. `AI_TABLE_OF_CONTENTS.md`
6. task-relevant schemas, registries, and roadmap gates

## Reusable engineering assets

Before coding, refactoring, or creating repo templates, check
`assets/asset-registry.json`, `registry/coding-asset-registry.json`, and
consult `assets/ai-engineering-preflight/`
when the task involves AI-assisted Python, Rust, mixed-language, or agent
instruction work.

For Python-specific work, also consult
`assets/python-ai-advantage-preflight/` and the underused-idiom card in
`assets/python-underused-idioms/idioms.json` (cite `py-idiom:*` ids in reviews
and lessons). For performance, Rust, or Python-to-Rust migration work, consult
`assets/rust-buildout-guide/rust-buildout.json` and follow its staged path;
profiling evidence comes before any Rust proposal. For task-to-profile routing
and midflight tactic selection, use `registry/preflight-profile-router.json`
and `registry/coding-tactics-radar.json`. For Python, Rust, mixed-language, or
future-language frontier work, consult
`registry/language-coding-advantage-registry.json`; it routes trusted sources,
overlooked patterns, harnesses, and validation gates. These are candidate
guidance unless a record is explicitly reviewed or promoted.

Use the asset's dry-run deployment and audit scripts before applying downstream
repo changes. Installing or consulting the central asset does not authorize
mutating another repository.

Before creating, updating, retiring, replacing, or checking out agent skills,
check `registry/agent-skill-library.json` and `docs/AGENT_SKILL_LIBRARY.md`.
Downstream repos should receive skill pointers or wrappers by local approval;
do not copy full DAD skills, plugins, hooks, or automation into another repo
from the library alone.

For CI, test ownership, path filters, required checks, module boundaries,
monorepo workflows, or cross-repo release lanes, use
`assets/agent-skills/dad-ci-module-boundary-governance/`. Ordinary PR checks
must follow `.ci/module-boundaries.yaml` ownership and declared dependency
edges. Keep scheduled full-system regression separate, and fail closed on
undeclared workflows, silent scope broadening, or path-filtered required checks.
Do not infer a complete dependency graph when observed-edge coverage is absent.

## Before material work

CLI examples use `asset-dir` when DAD is installed. If `asset-dir` is not on
`PATH`, first try the stable user shim at `$HOME/.dad/bin/asset-dir` or
`$HOME\.dad\bin\asset-dir.ps1`. In a raw source checkout, use
`PYTHONPATH=src python -m digital_asset_directory.cli ...` instead; in
PowerShell, set `$env:PYTHONPATH='src'` before running the command.

Run a preflight:

```text
asset-dir agent preflight --repo . --agent <agent-id> --task "<task>"
```

Use an arbitrary non-empty `<agent-id>` such as `codex`, `claude-code`,
`cursor`, `copilot`, `human`, `ci`, or `other`. DAD's durable contract is
agent-agnostic; runtime-specific files and hooks are optional adapters.
Internal agent integrations default to MCP-style tools, resources, and prompts
over direct vendor APIs. Direct APIs are external fallback adapters only; MCP
tools with side effects still require the DAD lifecycle, audit records, and
human gates. See `docs/MCP_FIRST_INTEGRATION_POLICY.md`.

Transport/data-plane checks are part of normal orientation. Runtime data should
resolve through `DAD_DATA_ROOT` only after an initialized marker exists; a
configured-but-uninitialized root must still fall back to legacy paths. Inspect
with:

```text
asset-dir data status
asset-dir transport audit
asset-dir daemon status
asset-dir journal status
```

State the route, scope, validation plan, and stop conditions before editing.

If preflight returns `required_learning_rule_acknowledgements`, or if matching context
appears later during calibration, duplicate/variant review, temp-fixture review, or lesson
reuse, run a midflight check:

```text
asset-dir agent midflight --session <SESSION_ID> --context "<context>" --path "<path>" --ack-rule "<rule-id>"
```

Do not continue a matching task while required learning-rule acknowledgements are missing.

For material coding, governance, mail, enrollment, schema, registry, public/private,
or cross-repo work, use the preflight `recommended_review_lanes`:

- `review-lane:red-team-and-premortem` checks the current change for bugs,
  false confidence, governance drift, sensitive-data movement, and missing tests.
- `review-lane:lesson-asset-harness-scout` looks for reusable lessons, novel or
  important digital assets, coding-harness ideas, skill updates, and DAD needs.

Use subagents for those lanes when the environment supports them and the work is
large enough to benefit. Otherwise run them as explicit checklist prompts. Record
useful findings in postflight, and for downstream repos route candidate learning
through the repo outbox only when local policy allows. Do not copy private rows,
secrets, or long source blobs into DAD learning records.

When a command reaches 60 seconds of measured wall time, or is expected to run
for at least 120 seconds, apply
`skill:long-run-optimization-review-pack` once per normalized command signature
per session. Start a high-effort optimization director that delegates independent
algorithm/architecture, primary-source library/web research, and language/runtime
reviews; add a benchmark/parity reviewer and a separate high-effort builder only
when a concrete candidate earns an approved bounded brief. The language review
must consider Rust and existing DAD Rust modules, but profiling and shadow parity
remain mandatory. If subagents are
unavailable, run the same lanes as explicit local checklists and record that
fallback in postflight. Retrigger only after a material implementation change
or a measured duration increase of at least 25 percent.

For instrumented shell-level work, before repeating an expensive command against
unchanged inputs, use the deterministic redundant-work guard.
The second same-state repetition after a prior run of at least five seconds, or
the third same-state repetition when duration is unknown, is a candidate for
reuse, narrowing, batching, or an immutable state-keyed cache. Exact evidence
uses zero model calls; ambiguous changed clusters may use one Luna/low observer,
Terra is reserved for measured redesign, and Sol is reserved for unresolved
high-consequence cross-repository architecture. Suppress intentional benchmarks,
changed inputs, explicit failure retries, and isolation tests. Never cache mutable
current state without an exact invalidation fingerprint, and never store raw
commands or sensitive payloads in DAD. Repetition inside one process requires
explicit work-unit instrumentation; otherwise report `coverage_unavailable`,
never a clean result.

Before postflight for every material build, refactor, investigation, or
cross-repo task, apply `skill:material-work-learning-discovery`. Check the DAD
agent and asset libraries first, then run learning-loop, digital-asset/pattern,
conversation-delta, prompt-curation, and reuse/application lanes. Start the
learning sentinel and prompt screener at low effort and escalate only on
uncertainty or high leverage. Capture explicit reusable decisions and failure
lessons that are absent from final artifacts, but never store raw transcripts,
hidden chain-of-thought, secrets, private payloads, or inferred private
reasoning. Dedupe all outputs and route only privacy-safe candidates through
allowed DAD channels. For every reused or created subagent, record
criterion-level post-use outcomes. Assign or interpret a numeric rating only
under a pinned evaluation profile and methodology with task difficulty or a
comparable cohort, independent evaluator relationship/integrity, and
uncertainty/limitations; otherwise record `unscored`/`insufficient_evidence`.
A task-verification PASS is attempt evidence, not a capability score.

## Operating rules

Agents must:

- inventory before editing;
- preserve source-repository authority boundaries;
- keep raw observations immutable and append-only;
- treat generated metadata, links, scores, and synergies as candidates;
- use stable asset identity and separate revision identity;
- preserve provenance and confidence labels;
- keep changes narrow and reversible;
- run task-relevant validation;
- report exact commands and results;
- capture at least one explicit lesson or state that no reusable lesson was found;
- honor reviewed deterministic learning rules surfaced by preflight or midflight;
- produce a postflight before reporting completion.

Agents must not:

- mutate scanned source files during discovery;
- store secrets or raw credentials;
- infer a source repo's canon from runtime evidence;
- silently change registry semantics;
- mark roadmap work complete without acceptance evidence;
- claim tests passed unless they were run;
- treat graph centrality, similarity, entropy reduction, stars, or model output as proof of truth or value;
- auto-merge external code without license, provenance, security, and compatibility review.

## Required postflight

```text
asset-dir agent postflight --session <SESSION_ID> --repo . --summary "<summary>" --test "<command that passed>" --test-not-run "<command not run>"
```

The final report must include:

- files changed;
- commands run;
- tests run and results;
- tests not run;
- confirmed findings;
- inferred findings;
- assumptions;
- unknowns;
- reusable lessons;
- remaining risks.

Postflight should also close the review lanes with `--review-lane` records:

```text
--review-lane "review-lane:red-team-and-premortem:<subagent|checklist|not_applicable|not_run>:<summary>"
--review-lane "review-lane:lesson-asset-harness-scout:<subagent|checklist|not_applicable|not_run>:<summary>"
```

If a lane was not run, record `not_run` or let postflight default it to
`not_run`; do not leave lane status implicit.

## Validation baseline

```bash
$env:PYTHONPATH='src'
python -m pytest
python -m digital_asset_directory.cli validate
python -m digital_asset_directory.cli roadmap check --no-update
```

<!-- BEGIN DIGITAL_ASSET_DIRECTORY_GOVERNANCE -->
## Digital Asset Directory enrollment contract

Repo enrollment ID: `dad`
Central DAD hub: `dad://hub/Digital-Assett-Directory` resolved by `--hub`, `DAD_HUB`, or
`~/.dad/hub.json`.
Contract: `.digital-asset/dad-integration.json`

Before material AI-assisted work, read this repo's front door and run:

```text
asset-dir agent preflight --repo . --agent <agent-id> --task "<task>"
```

`<agent-id>` is any arbitrary non-empty string; Claude, Codex, Cursor, Copilot,
human, CI, and future runtimes are optional adapters over the same DAD contract.

Read the returned `context_pack` before editing. If DAD is unavailable, local
coding may continue with a logged warning, but cross-repo writes, public
release, enrollment apply/update, protected repo work, and mail containing
sensitive payloads fail closed unless a named human bypass is recorded.

Use `.digital-asset/context-map.json` to decide which DAD assets, skills,
templates, architecture references, governance maps, or data maps are relevant.
Mail is checked daily by digest; asset, skill, template, architecture,
governance-map, data-map, and enrollment freshness checks are weekly and should
surface preflight warnings only when stale.

DAD may write broadly only during `asset-dir enroll apply` or
`asset-dir enroll update-apply` with a reviewed approval ID. Normal recurring
DAD operation writes only to `.digital-asset/mail/**`.

Mail, assets, skills, and templates are candidate evidence until reviewed
locally. This repo keeps local source authority and decides whether to adopt
any suggestion. Public-facing repos cannot receive private/internal/
restricted/unknown-origin mail without a DAD human release record.

If work is PR-ready, an actual PR is open, or a branch is intentionally left
after a work session, record branch/PR status, owner or next reviewer,
validation refs, next action, and escalation date. Send metadata-only DAD mail
for stuck, superseded, duplicate, conflict-heavy, or stale PR/branch queues when
local policy allows.

Close material work with postflight and include the preflight trace ID plus any
used, ignored, failed, or harmful DAD recommendations.
<!-- END DIGITAL_ASSET_DIRECTORY_GOVERNANCE -->
