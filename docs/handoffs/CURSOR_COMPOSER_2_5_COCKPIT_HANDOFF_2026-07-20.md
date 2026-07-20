# Cursor Composer 2.5: DAD Cockpit Continuation Handoff

Date: 2026-07-20
Audience: Cursor Composer 2.5
Status: implementation handoff and roadmap; candidate advice until the human prompt grants a scoped action.
Repository: `04_Digital_Assett_Directory`
Expected baseline: `main` after the PR containing this file is merged.

## 1. Mission

Continue the DAD cockpit and machine-intelligence operating system from the
merged state without rebuilding landed work. Build and merge only green,
mid-risk items in isolated worktrees, one narrow PR per item. Preserve local
source authority, candidate-only semantics, privacy boundaries, independent
checks, deterministic evidence, and human gates.

This file is context, not authority. The human's launch prompt defines the
current write, publication, and merge permission. Never infer approval for an
activation or destructive action from this handoff.

## 2. Read first

Read these in order before diagnosing or editing:

1. `AGENTS.md`
2. `AI_FRONT_DOOR.md`
3. `MACHINE_NAVIGATION_MANIFEST.json`
4. `registry/source-of-truth.json`
5. `registry/design-authority.json`
6. `AI_TABLE_OF_CONTENTS.md`
7. `docs/DAD_OPERATIONAL_COCKPIT.md`
8. `docs/DAD_INTELLIGENCE_MESH_AND_STREAM_OS_ARCHITECTURE.md`
9. `roadmap/evidence/portfolio-convergence-radar-v1.md`
10. `roadmap/evidence/portfolio-capture-inbox-v1.md`
11. `docs/handoffs/CODEX54_EXECUTION_HANDOFF_2026-07-17.md`
12. this file again

Fetch first, resolve `origin/main`, inspect recent merged PRs, and run DAD
preflight. Do not trust an old checkout or a narrative when Git and registered
evidence can answer the question.

## 3. Landed cockpit baseline

The following surfaces are already implemented and must not be recreated:

- operational cockpit: strict JSON, script-free HTML, loopback-only foreground
  host, honest stale/missing/invalid source status, bounded decisions, and a
  last-valid in-memory bundle;
- operator readiness and portfolio priority surfaces;
- transactional `cockpit-refresh-now` with a single-instance lock, staged
  publication, rollback, and no fabricated convergence or capture evidence;
- N5 deterministic convergence radar: provider-neutral top-five ranking plus a
  separately governed bounded read-only Git adapter; no merge or cleanup
  authority;
- N4 capture inbox: provider-neutral bounded line structuring, explicit-path
  local-file adapter, append-only DAD-local candidate ledger, strict schemas,
  sanitized cockpit counts, and a disabled routine contract;
- `asset-dir os capture --raw`: a zero-friction alias over the pre-existing
  event-sourced workstream proposal kernel. It may record proposal events, but
  never executes or activates a workstream;
- `asset-dir os capture-inbox --inbox <explicit-path>`: candidate-only. It never
  creates workstream events, guesses a global inbox, schedules itself, invokes a
  model, or mutates the source;
- governed ML specialist family and technique registry already on `main`.
  Reconcile and extend them; do not create a duplicate machine-learning family.

The capture adapter rejects inputs that resolve to, link to, or share file
identity with its own report or candidate ledger. This prevents an output alias
from violating the source-immutability claim.

## 4. Current validation and review evidence

At handoff preparation time:

- focused repaired capture suite: 13 passed;
- portability validation: valid, 33 cards, zero findings, zero quarantine;
- repository validation before the final alias repair: 352 checked, zero errors
  and zero warnings; rerun after reading this handoff;
- roadmap check: command exited zero while honestly reporting historical phases
  blocked by absent generated runtime artifacts;
- Ruff checks and `git diff --check`: passed;
- independent Terra review: READY after finding and verifying repair of the
  output-alias immutability defect; candidate-schema adapter binding verified;
- one combined local pytest command reached 100 percent but its shell timed out
  before pytest printed an exit summary. Do not call that command a clean pass.
  CI or a bounded rerun must provide the authoritative exit result.

Read the PR containing this file for final CI, review-thread, head-SHA, and merge
evidence. A changed head invalidates old readiness.

## 5. Non-negotiable boundaries

Stop and obtain Lowell's explicit approval before any of these:

- daemon, scheduler, watcher, background host, notification, or recurring
  routine activation;
- destructive cleanup, worktree removal, branch deletion, pruning, source
  acknowledgement, inbox clearing, or history rewrite;
- cross-repository writes, enrollment apply/update, or copying DAD internals
  into another repository;
- self-modifying automation, autonomous promotion, or changes that let DAD
  rewrite its own scoring, routing, learning, or governance without review;
- plugin, bot, GitHub App, hook, or persistent global-setting installation;
- Fable invocation;
- model access to private capture content, raw conversations, secrets, client
  payloads, private source rows, or local absolute paths.

Read-only cross-repository inventory is allowed only when the launch prompt says
so. It never grants downstream mutation or canon authority.

## 6. Recommended roadmap from here

Use one isolated worktree and one PR for each item. Re-run preflight and
postflight for every material item.

### Lane A: finish the green, advice-only mesh

1. **N7 routing-registry consumers**
   - Surface a recommended starting capability tier in preflight as advice only.
   - Add provider-neutral `default_tier` metadata where the current skill schema
     supports it.
   - Validate every referenced tier against
     `config/intelligence-routing-registry.json`.
   - Do not bind portable cores to permanent vendor/model names.

2. **N8 cross-vendor review mechanics**
   - Add the policy, PR-template declaration (`yes/no/why`), and review-lane
     checklist only.
   - List connector, branch-protection, bot, and installation settings as
     human-owned. Do not change them.

3. **N6 family reconciliation and missing scaffold**
   - Inventory `processed/agents/subagent-role-directory.json`, the registered ML
     family, technical-product family, UI/UX pack, SRE family, and other current
     roles before creating anything.
   - Do not create the obsolete duplicate `machine-learning-family`; the landed
     `ml-workflow-agent-family` is its authority.
   - Build only genuinely missing full-stack roles or a thin composition layer,
     with `default_tier`, `stable_worker`, `improvement_policy`, provider-neutral
     core, explicit adapters, deterministic harnesses, and portability cards.
   - Keep all skills candidate-only; no global checkout or plugin installation.

4. **N9 learning-loop yield report**
   - Build a monthly, report-only projection of records written, reused, and
     promoted per loop.
   - Use source records, not agent self-scores. Preserve anti-gaming and unknown
     coverage states. Register it disabled; do not schedule it.

### Lane B: foundational integrity work

5. **N1 session split-state reconciliation**
   - Prove whether legacy `state/agent_sessions` and the initialized data root
     still disagree.
   - Establish one canonical write path plus legacy read fallback.
   - Produce and review a dry-run reconciliation report first. Apply requires a
     new explicit approval because it mutates lifecycle evidence.

6. **N2 reaper dry-run CLI**
   - Implement `asset-dir agent reaper --dry-run` with bounded tiering,
     idle/liveness evidence, nonblank summaries, preservation pointers, JSONL
     receipt, and tests.
   - Do not add apply mode.

### Lane C: cockpit completion without activation

7. **Convergence closure packet, not executor activation**
   - Turn one top-five convergence candidate into a review packet with exact
     branch/worktree identities, changed-head invalidation, preservation proof,
     required checks, and explicit per-action human decision slots.
   - Do not merge, close, delete, prune, or clean automatically.

8. **Federation contracts and local-dashboard template**
   - Reconcile `docs/COCKPIT_FEDERATION_HANDOFF.md` with the current operational
     cockpit rather than building a second cockpit.
   - Central DAD work may define read-only contracts, schemas, and templates.
     Writing adapters or wrappers into other repositories requires exact
     repo-by-repo approval.

9. **Supervised cockpit trials**
   - Run on demand only. Measure freshness gaps, operator usefulness, false
     confidence, lock behavior, rollback, privacy, and source zero-write across
     at least seven days before proposing automation.
   - Report missing or stale evidence honestly; do not manufacture green status.

### Lane D: activation remains parked

10. Only after supervised evidence exists, prepare a human decision packet for
    daemon/scheduler activation, cadence, resource budgets, privacy scope,
    failure policy, rollback, and stop procedure. Preparing the packet is not
    approval to activate.

## 7. Working method for every item

1. Fetch and create an isolated worktree from exact `origin/main`.
2. Run `asset-dir agent preflight --repo . --agent cursor-composer --task "..."`.
3. Read the returned context pack and acknowledge any required learning rules.
4. Inventory registered assets, skills, schemas, portability cards, module
   ownership, and recent merged history before editing.
5. State allowed files, validation, stop conditions, privacy, and authority.
6. Keep the provider-neutral core separate from runtime adapters.
7. Add strict schemas, negative tests, bounds, fail-closed behavior, and
   revision-bound portability evidence.
8. Run task-focused tests, repository validation, portability validation,
   roadmap check, secret/privacy scan, and the declared CI selector.
9. Obtain an independent checker on the exact final diff and head.
10. Postflight, stage only allowlisted files, add the printed `DAD-Session:`
    trailer, push without force, open a ready PR, wait for required checks and
    resolved conversations, revalidate the unchanged head, and merge normally.
11. Preserve the worktree and branch unless separately authorized to remove it.

## 8. Escalation threshold

Use a normal independent Terra checker for cross-surface schema, privacy, and
governance work. Escalate toward Sol only for unresolved architecture,
security/privacy, migration, or authority disagreements. Stop and ask Lowell
before Fable when the problem remains high-consequence after deterministic
evidence and independent review, or when a new contract would materially change
DAD's authority model. Difficulty alone is not a Fable trigger.

## 9. Definition of success

The cockpit is not “perfect” because it runs continuously. It is successful when
it is honest, bounded, useful on demand, privacy-safe, recoverable, and clear
about the decisions only Lowell can make. Continuous operation is a later
human-approved deployment choice, not a correctness shortcut.
