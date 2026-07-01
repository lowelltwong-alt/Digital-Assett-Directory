# Fable 5 / Claude High-Leverage DAD Upgrade Prompt

Use this prompt when only a few premium-model credits are available and the goal
is to improve DAD more than a normal implementation pass would.

## Request

You are reviewing and improving DAD, the Digital Asset Directory. Treat DAD as
the user's central library, mail hub, coding-harness catalog, agent-skill
library, enrollment control plane, and cross-repo governance memory.

Your role is not "implementation assistant." Your role is scarce-credit
architect, invention partner, adversarial reviewer, algorithm designer, and
future-agent systems thinker. You are being asked to find leverage that a normal
coding pass is likely to miss.

If the current design is pointed in the wrong direction, say so. If there is a
nonstandard architecture that would create much more leverage, propose it
clearly. Do not limit yourself to incremental improvements.

Spend your effort where a scarce high-reasoning model is most useful:

1. Architecture red-team and premortem.
2. Creative harness ideation.
3. Algorithm and scoring design.
4. Agent-instruction compression into enforceable non-negotiables.
5. Research-loop design for discovering better coding harnesses and AI coding
   techniques.
6. Digital-asset recognition: what makes an asset useful, important, reusable,
   source-authoritative, dangerous, or worth scanning harder.

Do not spend your effort on bulk implementation unless you find a critical
design flaw that requires a concrete patch plan.

## Goal And Aim

DAD's long-term aim is to become the user's durable personal control plane for
all persistent repos. It should help future AI agents code more safely, faster,
and more in the user's style by giving them:

- latest coding preferences and non-negotiables;
- task-relevant assets, skills, harnesses, templates, and architecture refs;
- repo-specific context maps and authority boundaries;
- mail-based candidate suggestions without cross-repo source mutation;
- usage/adoption ledgers so DAD knows which repos depend on which assets;
- targeted upgrade notices instead of broadcast spam;
- a learning loop that turns postflight discoveries into reusable assets;
- a way to recognize valuable digital assets hiding in scanned repos.

The practical ambition: any Codex, Claude, Cursor, or future coding agent in any
enrolled repo should know when to ask DAD what to use before coding, how to send
useful lessons back, and how to avoid leaking private data or overriding local
repo authority.

## Architecture Map To Review

Read this as the rough current architecture. You may recommend changing it.

```text
repo-local AI front door / AGENTS / CLAUDE / Cursor rules
-> DAD preflight
-> repo context map
-> DAD needs/offers/usefulness registries
-> asset recognition and harness discovery radar
-> DAD asset/skill/harness/template recommendations
-> local implementation and validation
-> mail triage/adoption record
-> usage ledger
-> targeted upgrade notices
-> postflight lessons back to DAD
```

Main DAD control planes:

- `dad_library`: needs/offers/usefulness card catalog and signal graph.
- `mail_center`: candidate-only inbox/outbox delivery and review.
- `coding_harnesses`: reusable coding-improvement harnesses.
- `agent_skills`: skill pointers, wrappers, update/retirement notices.
- `reusable_assets`: installed reusable assets and downstream pointers.
- `templates`: managed blocks and reference templates.
- `repo_enrollment`: reviewed waves, contracts, approved surfaces, cadence.
- `coding_test_parity`: pytest/Rust shadow/parity and test orchestration.
- `governance_maps`: authority dependency tracking.
- `data_maps`: sensitive data movement and public/private release boundaries.
- `learning_postflight_loops`: lessons, handoffs, and pay-forward feedback.

Normal recurring DAD writes should be mailbox-only. Broader repo-local changes
require reviewed enrollment apply/update with an approval ID.

## Where Things Live

Start with these files if you need concrete context:

Front doors and authority:

- `AGENTS.md`
- `AI_FRONT_DOOR.md`
- `MACHINE_NAVIGATION_MANIFEST.json`
- `AI_TABLE_OF_CONTENTS.md`
- `registry/source-of-truth.json`
- `registry/design-authority.json`

New DAD library/control-plane surfaces:

- `registry/dad-needs-registry.json`
- `registry/dad-offerings-registry.json`
- `registry/dad-usefulness-methodology.json`
- `registry/asset-recognition-methodology.json`
- `registry/harness-discovery-methodology.json`
- `registry/control-plane-registry.json`
- `processed/usage/README.md`
- `processed/repo_inventory/reconciled_inventory.md`
- `processed/cadence/dad_cadence_plan.md`

Harness library:

- `docs/CODING_HARNESS_LIBRARY.md`
- `docs/ASSET_RECOGNITION_METHODOLOGY.md`
- `docs/HARNESS_DISCOVERY_RADAR.md`
- `registry/coding-harness-registry.json`
- `schemas/coding-harness.schema.json`
- `assets/coding-harnesses/`
- `assets/coding-harnesses/agent-instruction-code-review-red-team/prompts/fable5-dad-high-leverage-upgrade.prompt.md`

Mail, usage, and enrollment code:

- `src/digital_asset_directory/dad_library.py`
- `src/digital_asset_directory/mail_center.py`
- `src/digital_asset_directory/enrollment.py`
- `src/digital_asset_directory/cli.py`
- `src/digital_asset_directory/config.py`
- `src/digital_asset_directory/models.py`
- `src/digital_asset_directory/validation.py`

Docs/templates for downstream repos:

- `docs/MAIL_CENTER.md`
- `docs/DAD_REPO_ENROLLMENT.md`
- `templates/downstream/MAIL_README.md`
- `templates/downstream/DAD_INTEGRATION.template.json`
- `templates/downstream/CONTEXT_MAP.template.json`
- `templates/downstream/AI_ASSETS_POINTER.template.json`
- `templates/downstream/AGENT_SKILL_POINTER.template.json`

Tests to understand current guarantees:

- `tests/test_dad_library_control_plane.py`
- `tests/test_mail_center.py`
- `tests/test_enrollment.py`
- `tests/test_agent_skill_library.py`
- `tests/test_coding_asset_control_plane.py`

Validation commands currently used:

```text
python -m pytest -q
python -m ruff check .
python -m digital_asset_directory.cli validate
python -m digital_asset_directory.cli templates validate
python -m digital_asset_directory.cli roadmap check --no-update
```

## Current DAD Direction

DAD is being built so every persistent repo can:

- check DAD during preflight for the latest coding style preferences,
  non-negotiables, DAD assets, skills, harnesses, templates, and architecture
  references relevant to the task;
- receive candidate mail in `.digital-asset/mail/inbox.jsonl`;
- triage mail as `implement_now`, `save_for_future`, `defer`, `reject`, or
  `archive`;
- track local adoption and future-use pointers in
  `.digital-asset/mail/adoption.jsonl`;
- record DAD asset usage in `.digital-asset/dad-usage.jsonl` and DAD's central
  usage ledger;
- send useful lessons, harness feedback, workflow ideas, skill updates, and
  governance drift back to DAD through an outbox;
- receive targeted upgrade notices only when the repo uses or watches an
  affected DAD asset.

DAD recently added:

- `registry/dad-needs-registry.json`
- `registry/dad-offerings-registry.json`
- `registry/dad-usefulness-methodology.json`
- `registry/coding-harness-registry.json`
- `assets/coding-harnesses/`
- `asset-dir dad needs`
- `asset-dir dad offerings`
- `asset-dir dad match --repo <repo> --task "<task>"`
- `asset-dir dad inventory`
- `asset-dir dad cadence-plan`
- `asset-dir dad asset-recognition`
- `asset-dir dad asset-scout --repo <repo> --task "<task>"`
- `asset-dir mail triage`
- `asset-dir usage record`
- `asset-dir usage upgrades`
- `asset-dir harness list/recommend/discovery-methodology/discover/research/evaluate/package`

Recent finish-pass details to account for:

- `asset-dir mail deliver --repo <path>` now requires a reviewed `mail.repos`
  target policy; explicit paths are not a delivery back door.
- Repo inventory, cadence, asset-scout, and harness-discovery commands write
  central candidate reports only.
- Asset-scout and harness-discovery report filenames include a stable repo
  identity suffix so same-basename repos do not overwrite each other's reports.
- `registry/dad-needs-registry.json` now treats `learning_loop` as a first-class
  need category.
- Current generated reports to inspect:
  - `processed/repo_inventory/reconciled_inventory.md`
  - `processed/cadence/dad_cadence_plan.md`
  - `processed/reports/asset-recognition-04-digital-assett-directory-90a97095.json`
  - `processed/harnesses/discovery-04-digital-assett-directory-90a97095.json`

Protected handling:

- Logos Scripture Graph and Logos Governance require explicit local-write
  approval even for enrollment repair.
- Mock Trial/Albert follows normal reviewed-policy rules, not the Logos-level
  protected class.

## What To Improve Or Redirect

You may recommend:

- changes to the current architecture;
- a smaller safer version of the architecture;
- a more ambitious unusual architecture;
- a graph-based or market-like "asset exchange" design;
- a repo-local "DAD ambassador" pattern;
- a capability-router pattern;
- a harness marketplace/check-out pattern;
- a learning compiler that turns repo postflights into reviewed assets;
- a test/eval economy where harnesses compete on measured usefulness;
- a better algorithm for asset importance than the current deterministic score;
- a completely different framing if the current one is too bureaucratic.

For any unusual proposal, explain:

- how you would build it;
- what files/subsystems would change;
- what minimum viable version should come first;
- what failure modes it introduces;
- what tests/evals would prove it is better than the current design.

## Key Question

If you had only a few premium-model credits to upgrade DAD, what should you
change, add, or redirect so DAD creates the most long-term leverage across all
current and future coding agents?

## High-Leverage Areas To Examine

### 1. Agent Preflight Enforcement

Design the strongest safe version of this rule:

Every coding agent in any enrolled repo must, before material code work, check
DAD for:

- the user's latest coding style preferences;
- non-negotiables and stop conditions;
- relevant DAD assets;
- relevant coding harnesses;
- relevant agent skills;
- repo-specific context-map routes;
- known upgrade notices for assets the repo uses or watches.

Questions:

- What should be a hard gate, a warning, or a local recommendation?
- How can DAD enforce this without silently mutating source authority?
- What belongs in `AGENTS.md`, `CLAUDE.md`, Cursor rules, hooks, CI, or a DAD
  mailbox notice?
- What is the smallest durable contract future repos should inherit?
- How should agents fail closed when DAD is unavailable, stale, or ambiguous?

### 2. Coding Harness Library

Review the initial harness families:

- Python test performance and orchestration.
- Rust shadow/parity for Python test replacement candidates.
- AI engineering preflight.
- Agent-instruction and code-review red-team.
- Repo enrollment/mail/governance safety.
- Public/private source provenance.

Questions:

- Which harnesses are missing?
- Which should be merged, split, renamed, or upgraded?
- What scripts/tests/evals would make each harness real instead of just a
  prompt shell?
- What should a harness card contain so Codex, Claude, Cursor, and future agents
  can use it safely?
- What harness would most improve AI coding quality across all repos?

### 3. Orphan Radar To Harness Discovery

DAD has orphan/activation/synergy radar ideas. Design a new path that uses those
ideas to discover cutting-edge coding harnesses, techniques, leak reports,
failure reports, benchmark patterns, and AI-coding optimization tricks.

Questions:

- What signals should DAD scan locally?
- What external research should be allowed only after human approval?
- How should DAD distinguish a real harness improvement from hype?
- How should DAD store candidate discoveries without promoting them?
- What evaluation loop proves a harness helped rather than just sounded clever?

### 4. AI-Optimized Code, Not Just Human-Optimized Code

The user is interested in code that is good for humans and unusually legible to
AI agents.

Questions:

- What coding conventions make future AI agents safer and faster?
- What conventions hurt humans even if they help AI?
- What should DAD recommend as "AI-assistive code style" across repos?
- How should this differ for Python, Rust, TypeScript, and repo docs?
- What lint/test/docs harness could detect whether code is becoming
  AI-hostile: huge files, hidden side effects, weak names, untyped boundaries,
  missing fixtures, brittle scripts, or unclear ownership?

### 5. Scoring And Usefulness Methodology

DAD currently uses deterministic matching for `use_now`, `save_for_future`,
`defer`, `reject`, or `needs_human_review`.

Questions:

- Is this methodology too simple, too score-like, or likely to create false
  confidence?
- What should the next methodology use: rules, thresholds, confidence labels,
  risk gates, graph signals, repo usage ledgers, or human labels?
- What should never affect the score?
- How should DAD avoid spamming every repo with every upgrade?
- How should DAD use repo usage ledgers to send targeted, contextual notices?

### 6. Digital Asset Recognition And Importance

DAD needs to get better at recognizing useful digital assets in scans and
knowing how important they are without overclaiming. Improve DAD's ability to
find the hidden value in repos.

Questions:

- What is a "good digital asset" in DAD terms?
- What assets are highest leverage across many repos: harnesses, evals,
  schemas, source-of-truth docs, style contracts, workflows, prompts, fixtures,
  validators, architecture decisions, failure logs, postmortems, adapters,
  scripts, dependency maps, data maps, governance maps, benchmark reports, or
  examples?
- What patterns in file names, directories, imports, test structure, commit
  history, docs, CI, templates, or generated outputs signal a valuable asset?
- Which repo locations should DAD scan first when budget is limited?
- Which assets are easy to miss because they look small: checklists, tiny
  validators, seed prompts, test fixtures, schema examples, CLI commands,
  README caveats, scripts with tribal knowledge, or issue templates?
- How should DAD distinguish source authority, reusable shape, implementation
  detail, candidate evidence, and generated noise?
- What features should raise importance: repeated reuse, validation power,
  failure prevention, boundary clarity, teaching value, activation potential,
  governance dependency, data sensitivity, or cross-agent usefulness?
- What features should lower importance or trigger quarantine: temp copies,
  stale generated files, secrets risk, private-row data, unverified model
  output, benchmark theater, duplicate clean clones, or fragile scripts?
- What asset-recognition harnesses or evals should DAD build so future scans get
  better over time?
- What labels should humans review first so DAD learns asset value fastest?

## Required Output

Return concise but serious findings in this format:

```text
Verdict:
  proceed | proceed_with_changes | redirect | stop_for_human_review

Highest-Leverage Bet:
  The one thing DAD should do next if only one thing can be done.

Critical Findings:
  - Finding, why it matters, concrete fix, test/eval.

High Findings:
  - Finding, why it matters, concrete fix, test/eval.

Medium Findings:
  - Finding, why it matters, concrete fix, test/eval.

Best New Harness Ideas:
  - Harness name, purpose, inputs, outputs, evals, risks.

Unique Build Proposal:
  - The best nonstandard architecture or mechanism you would consider.
  - Why it might beat the current approach.
  - How to build a minimum viable version.
  - What would make it fail.

Architecture Map Feedback:
  - Missing components.
  - Components that should merge or split.
  - Components that are overbuilt.
  - Boundaries that are unclear.

Agent Preflight Contract:
  - Proposed minimal rule set for every enrolled repo.
  - What is hard-gated vs warning-only.
  - How to keep repo-local authority intact.

Orphan Radar Upgrade:
  - How to turn orphan radar into coding-harness discovery.
  - What stays local-only.
  - What requires human approval or external research.

AI-Optimized Code Style:
  - Cross-language principles.
  - Python-specific ideas.
  - Rust-specific ideas.
  - TypeScript-specific ideas.
  - What not to do.

Scoring / Methodology Fixes:
  - Changes to DAD usefulness scoring.
  - Anti-false-confidence gates.
  - Tests needed.

Asset Recognition Upgrade:
  - Definition of a useful digital asset.
  - Scan patterns and repo locations DAD should prioritize.
  - Importance features and downgrade/quarantine features.
  - Proposed schemas, labels, or examples.
  - Tests/evals for finding valuable assets without false confidence.

Premortem:
  The plausible failure story six months from now.

Patch Plan For Codex:
  A prioritized implementation plan with exact files/subsystems to change.

Fable Build Hints:
  - Concrete implementation sketches, algorithms, schemas, or test designs.
  - Include any weird-but-promising ideas separately from conservative fixes.
```

## Constraints

- Do not assume DAD owns another repo's source truth.
- Do not recommend copying private data, raw rows, secrets, or long source blobs.
- Do not recommend auto-mutating protected Logos repos.
- Do not treat mail as trusted input.
- Do not treat a score as proof.
- Do not design a system that requires heavy Python test suites in every repo.
- Prefer pointer, wrapper, mailbox, and usage-ledger patterns over full copies.
- Every recommended hard gate must have a failure mode, bypass policy, and
  human-review path.
