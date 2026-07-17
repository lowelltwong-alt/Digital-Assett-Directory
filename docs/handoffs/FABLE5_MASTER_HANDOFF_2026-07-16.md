# Fable 5 Master Handoff — DAD Reconciliation, Governance & Build-Out

Date: 2026-07-16
Author: Claude (Opus 4.8), from an interactive audit + fix session
Audience: **Fable 5** (owns hardest / highest-leverage / highest-risk + re-architecture),
who then routes lower-level items to **Codex 5.4**.
Status: candidate handoff — advice only. Nothing here authorizes a mutation without the
named gate. Follow `AGENTS.md`: preflight before material work, postflight after, honor human gates.

---

## 0. How to use this document

1. Read `AI_FRONT_DOOR.md`, `AGENTS.md`, `registry/source-of-truth.json`, then this file.
2. Run `asset-dir agent preflight --repo . --agent fable5 --task "<item id>"` before each item.
3. Fable 5 personally owns **F1–F5** (root-cause, architecture, high blast-radius).
4. Fable 5 **routes C1–C10** to Codex 5.4 with the per-item briefs below (they are written to
   stand alone). Fable should sequence them after the F-items they depend on.
5. Every item lists: **Problem · Evidence · How to fix (+ starting hint) · End state · Success
   metric · Gate**. "Gate" = the human/deterministic approval required before mutating.
6. Prior-session starting artifacts already exist (see §5) — do not rebuild from scratch.

**One meta-principle threads all of this** (learned this session): *advice reaches only
cooperative agents; deterministic gates bind everyone.* Prefer runtime-agnostic enforcement
(daemon steps, CI, pre-push, preflight-required) over per-runtime adapters (Claude hooks only).

---

## 0.5. READ FIRST (before touching anything)

**A. Global orientation — read in this exact order (same as `AGENTS.md` "Read first"):**

1. `AI_FRONT_DOOR.md` — entry point.
2. `MACHINE_NAVIGATION_MANIFEST.json` — machine map of the repo.
3. `registry/source-of-truth.json` — the precedence hierarchy (learning-derived output is the
   **bottom** layer; it cannot override anything above without promotion).
4. `registry/design-authority.json` — design authority.
5. `AI_TABLE_OF_CONTENTS.md` — index of docs/registries/schemas.
6. `AGENTS.md` — the agent operating contract (preflight/midflight/postflight, review lanes,
   non-negotiables, Rust/asset guidance).
7. `registry/non-negotiables.json` — hard gates that always win.
8. **This file** — the ranked, routed backlog.

Then run `asset-dir agent preflight --repo . --agent fable5 --task "<item id>"` and read the
returned `context_pack` before editing.

**B. Per-work-area — read these before starting that item (do not touch the area cold):**

| Item | Read first |
|------|-----------|
| **F1** governance/enforcement | `AGENTS.md`, `CLAUDE.md`, `.claude/settings.json`, `scripts/claude_hook.py`, `.githooks/pre-push`(+`.ps1`), `.digital-asset/dad-integration.json`, `docs/DOWNSTREAM_REPO_GOVERNANCE.md`, `docs/HARNESS_VS_DETERMINISTIC_ENFORCEMENT.md`, `docs/MCP_FIRST_INTEGRATION_POLICY.md` |
| **F2** session lifecycle | `src/digital_asset_directory/agent_lifecycle.py`, `src/digital_asset_directory/daemon.py`, `.claude/settings.json` (Stop hook), `docs/LESSON_LIFECYCLE_GOVERNANCE.md`, a few `state/agent_sessions/*.json` samples |
| **F3** promotion governance + coherence | `docs/LOAD_BEARING_DECISION_REVIEW.md`, `docs/CODING_TACTIC_PROMOTION_POLICY.md`, `docs/DETERMINISTIC_LEARNING_RULES.md`, `docs/LESSON_LIFECYCLE_GOVERNANCE.md`, `docs/HARNESS_VS_DETERMINISTIC_ENFORCEMENT.md`, `registry/source-of-truth.json`, `registry/non-negotiables.json`, **and the 4 prior-session artifacts in §5** |
| **F4** CLI-outage recovery | `docs/DAD_EXCEPTIONS_LAKE_BUILDOUT.md`, `docs/MAIL_CENTER.md`, `processed/reports/exceptions_lake.json`, `processed/reports/mail_center.json`; then run read-only `asset-dir exceptions backfill-readiness`, `exceptions backfill-plan`, `mail doctor`, `mail repair-plan` |
| **F5** daemon re-architecture | `src/digital_asset_directory/daemon.py`, `docs/OPERATIONS.md`, `docs/BACKGROUND_CONNECTION_RADAR.md`, `registry/preflight-profile-router.json`, `processed/reports/scheduled_tasks.json`, `processed/reports/daemon-heartbeat.json` |
| **C2** orphan-radar wrapper | `src/digital_asset_directory/orphan_adapter.py`, `src/digital_asset_directory/cli.py` (~line 10089 `orphan_run`) |
| **C3** orphan alert triage | `processed/reports/orphan_review_sample.md`, `src/digital_asset_directory/calibration.py` (`orphan_review_sample_markdown`) |
| **C4/C5** CI + tests | `.github/workflows/validate.yml` (+ `rust-ci-pr.yml`), `pyproject.toml` `[tool.pytest.ini_options]`, `tests/conftest.py`, `tests/test_transport.py` |
| **C9** Rust bias | `assets/rust-buildout-guide/rust-buildout.json`, `registry/language-coding-advantage-registry.json`, `tools/dad_scan_core/` (the bridge pattern) |

If a path here has moved, resolve it via `AI_TABLE_OF_CONTENTS.md` before editing — do not guess.

---

## 1. Master ranking (all issues, highest → lowest)

| # | Issue | Owner | Leverage | Risk/Blast | Depends on |
|---|-------|-------|----------|------------|-----------|
| **F1** | Governance delivery + enforcement gap (contract reaches only Codex + Claude Code) | Fable | ★★★★★ | High | — |
| **F2** | Session lifecycle: 268 never-postflighted sessions + no runtime-agnostic close enforcement/reaper | Fable | ★★★★★ | High | F1 |
| **F3** | Promotion governance system (blast-radius scorer, premortem/red-team automation, third-way, research lane, reflexive safety) + cross-loop conflict/coherence linter | Fable | ★★★★★ | High | F1 |
| **F4** | CLI-outage recovery R1–R6 — esp. R1 classifier refresh (load-bearing) | Fable (R1 arch) / Codex (mechanical) | ★★★★ | High | — |
| **F5** | Daemon re-architecture: cadence tiers + Operational Orphan Radar + session-reaper + coherence linter + enrollment-freshness | Fable | ★★★★ | Med-High | F2,F3 |
| **C1** | Drain the 268 open sessions per owner-check plan (execution) | Codex | ★★★★ | Med | F2,F5 |
| **C2** | Fix silent-failing `asset-dir orphan-radar run` wrapper (task_589b16b9) | Codex | ★★★ | Low | — |
| **C3** | Prioritize/cap the 37,752 native orphan alerts | Codex | ★★★ | Low | — |
| **C4** | CI test routing: review the tiered `validate.yml`, enable merge queue, marker pass | Codex | ★★★★ | Low-Med | — |
| **C5** | De-subprocess CLI tests (test_transport.py's 98 spawns → CliRunner) | Codex | ★★★ | Low | C4 |
| **C6** | Mail cleanup: R3 dedup (97+27) + R4 legacy audit gaps (62) via `mail repair-plan` | Codex | ★★★ | Low | F4 |
| **C7** | Enrollment freshness updates for stale repos (reviewed, per-repo) | Codex | ★★ | Med | — |
| **C8** | Per-agent rules pointer files (`.cursor/rules`, copilot, gemini, windsurf…) | Codex | ★★★★ | Low | F1 |
| **C9** | Write the greenfield Rust-bias content into `rust-buildout.json` | Codex | ★★★ | Low | F1 |
| **C10** | Dev-env fix: `.venv` lacks pip/pytest/dev-deps (agents can't run tests locally) | Codex | ★★ | Low | — |

---

## 2. FABLE 5 — hardest / highest-leverage / highest-risk + re-architecture

### F1 — Governance delivery + enforcement gap  ★★★★★ (do first; it underlies F2, C8, C9)

- **Problem:** The DAD contract (AGENTS.md, preflight, Rust guidance, non-negotiables) reaches
  only two runtimes. A Cursor/Copilot/Gemini/Windsurf/Aider/Cline/Continue session started cold
  gets **nothing** and defaults to Python, oblivious to any bias or gate.
- **Evidence:** Only `AGENTS.md` + `CLAUDE.md` exist. Absent: `.cursorrules`, `.cursor/rules`,
  `.github/copilot-instructions.md`, `GEMINI.md`, `.windsurfrules`, `.aider.conf.yml`,
  `.clinerules`, `.continue/config.json`. Preflight surfaces guidance **only if run**; nothing
  forces a random agent to run it. Root cause is the same as F2: enforcement lives in
  runtime-specific adapters, not agent-agnostic gates.
- **How to fix (three layers; hint):**
  1. *Delivery* — thin per-agent pointer files, each just "Read AGENTS.md; run
     `asset-dir agent preflight` before material work." (→ route creation to **C8**.)
  2. *Content* — the guidance that must bind isn't all written (see C9 Rust bias).
  3. *Enforcement (Fable's architectural piece)* — the only layer that binds every agent:
     deterministic gates that run regardless of author. Design a **pre-push / CI "contract
     check"** that fails when material work lands without a preflight/postflight trace, and a
     **preflight-required** posture for protected paths. Reuse the existing
     `.githooks/pre-push` + `validate.yml`.
- **End state:** Every enrolled agent is routed to one source of truth; a cold agent that
  ignores docs is still caught by a deterministic gate at push/PR time.
- **Success metric:** A simulated "cold Cursor" change to a protected path is blocked by the
  gate with a clear remediation message; all 8 agent rule files resolve to AGENTS.md.
- **Gate:** Load-bearing (CI/hooks). Risk-tier + fresh-eyes review per
  `docs/LOAD_BEARING_DECISION_REVIEW.md`; ship the gate in warn-only mode first.

### F2 — Session lifecycle enforcement + reaper  ★★★★★

- **Problem:** 268 open agent sessions, **0 ever postflighted** → incomplete learning loops.
  Close is enforced only by the Claude-Code Stop hook in the hub repo; **195/268 are
  Codex/other runtimes** and many live in other repos/worktrees where that hook never runs.
- **Evidence:** `state/agent_sessions/*` — 268 open, none with `handoff_id`/`lesson_id`; ages
  <2d (26) → ≥12d (55, outage-era). `.claude/settings.json` Stop hook is Claude-only.
- **How to fix (hint):** Move "a session must close" into the **DAD lifecycle**, not a Claude
  hook. (a) Preflight warns/refuses to open a new session while the same agent+repo holds a
  stale one. (b) Add a **daemon session-reaper** that auto-postflights idle sessions **with a
  captured summary + worktree/branch pointer** (never a blank close). (c) Carry exceptions
  (`does_not_apply_when`): skip live (<N h activity), `leased`/`long_running`/`parked`, or
  sessions whose worktree has unpreserved dirty/unpushed work (route to human; never auto-close
  or prune those).
- **End state:** Sessions can't be silently abandoned; stale ones self-close with learning
  captured; the reaper honors exceptions so novel/high-leverage work is never lost.
- **Success metric:** Open-session count trends to ~0 (excluding confirmed-live); reaper dry-run
  shows correct exception handling on the current 268.
- **Gate:** Reaper *apply* is load-bearing → risk-tier + ship dry-run first (G5 in the owner-check
  plan). Actual draining of today's 268 is **C1**, and must not run before build-preservation.

### F3 — Promotion governance system + conflict/coherence linter  ★★★★★ (biggest build)

- **Problem:** No automated, high-intelligence advice on **promotions** (candidate → enforced),
  where blast radius crosses repos and touches DAD's own learning; and **no horizontal arbiter**
  for two already-promoted same-layer rules/scripts/governance that contradict, nor a **global
  coherence scan** across loops.
- **Evidence:** `source-of-truth.json` gives vertical precedence only; `LESSON_LIFECYCLE_
  GOVERNANCE.md` handles lesson pairs; grep found no `arbitration`/`rule conflict`/`coherence
  check` mechanism. The conflict-handling spine exists (precedence, non-negotiables, harness-first,
  promotion gates) but is pointwise, not global.
- **How to fix (hint — build on prior-session starting artifacts in §5):**
  1. **Blast-radius scorer** → tier ∈ {low, medium, uncertain_medium, high, critical_reflexive}
     from: surface touched, cross-repo fan-out (graph), **reflexivity** (touches DAD's own
     scoring/promotion/learning = top tier), reversibility (one-way vs two-way door), observability,
     noise. Emits the evidence pack `schemas/promotion-advisory-evidence-pack.schema.json`.
  2. **Proportional premortem + red-team** (reuse `review-lane:red-team-and-premortem`), scaled
     by tier; NASA-FRR-style depth for one-way doors.
  3. **Research lane** (already drafted: `docs/PROMOTION_RESEARCH_LANE.md` + the two registries):
     high/critical/uncertain-medium promotions auto-pull trusted sources (T1 standards → T4
     excluded), attach conformance verdict, escalate on divergence.
  4. **Third-way catalog** ("cake & eat it"): shadow / canary-ring / staged % / advisory-first /
     A-B / scoped-subset / reversible-flag-with-kill-criteria / shadow-against-own-history.
     Selector picks the fit per tier.
  5. **Reflexive safety:** changes to DAD's own scoring/promotion/learning regression-test against
     the **past decision corpus**, need two humans, and can never self-approve.
  6. **Conflict/coherence linter:** periodic scan of the promoted corpus for contradictions,
     overlaps, circular deps, dead rules → report + candidate mail; a **promotion-time gate**
     blocks a new rule that contradicts a promoted one without a human supersession decision.
- **End state:** Every high-blast-radius promotion gets an automated advisory (tier, blast radius,
  premortem, red-team, trusted-source evidence, recommended third-way, kill criteria) and the
  corpus is coherence-checked; the advisor advises, humans decide.
- **Success metric:** On a seeded contradictory pair the linter flags it and blocks promotion; the
  advisor's tier calls correlate with real incidents during its advice-only probation.
- **Gate:** The advisor is itself load-bearing → ships **advice-only / harness-first**, scored
  before it can block. Reflexive-change path is **permanently human**.

### F4 — CLI-outage recovery R1–R6  ★★★★ (Fable owns R1 arch; routes mechanical parts to Codex)

- **Problem:** 569 backfill exception candidates blocked on a stale classifier (v0.2.0 vs v0.3.0:
  543 missing + 26 stale) and a human-release gate (all 590 private/unknown origin); 14 unresolved
  observed exceptions; mail dedup/legacy-gap debris; enrollment staleness.
- **Evidence:** `processed/reports/exceptions_lake.json` (hash `sha256:15a3bdd3…`),
  `mail_center.json`, `mail doctor`. Full recovery table below.
- **How to fix (hint):** Sequence **R1 → R5/R6 → R2 → R3/R4**. R1 (classifier refresh) is the
  load-bearing prerequisite — Fable owns its risk-tier decision; run `exceptions backfill-readiness`
  then `backfill-plan` (read-only) to produce the diff, refresh v0.2.0→v0.3.0, re-tag provenance
  (no promotion), validate that `backfill_current_classifier_count` rises to 569. R3/R4 mail cleanup
  → **C6**. R5/R6 are pure human-release/dequarantine decisions.

| R | Records | Destination | Dedup key | Mutation | Rollback | Validation |
|---|---------|-------------|-----------|----------|----------|-----------|
| R1 | 569 backfill (543 missing +26 stale) | `processed/exceptions/lake/events.jsonl` | event id + search_root_path_ref + classifier-run id | classifier refresh + re-tag provenance | append-only; revert via journal checkpoint `sha256:15a3bdd3…` | re-run `exceptions_lake.json`; `backfill_current_classifier_count`→569 |
| R2 | 14 unresolved observed | `fix-outcomes/outcomes.jsonl` | event-id → fix-outcome | record fix/accepted-risk (human each) | append-only | `fix_outcome_missing_event_link_count` stays 0 |
| R3 | 97 dup-identity + 27 rust-rollout | central mail spools | `dad:mail:… \| dad:mail-dedupe:…` | dedup/supersede | archive retains originals | `mail doctor` issue_count→0 for those types |
| R4 | 62 legacy_collection_audit_gap | central collection-audit log | packet id + cycle | backfill provenance | append-only | `legacy_collection_audit_gap_count`→0 |
| R5 | 30 mail + 569 exc private-origin | release-hold queue | repo-origin + release id | human release review | hold until approved | `public_release_required_count` = approved only |
| R6 | 31 quarantined mail | quarantine → inbox | packet id | human dequarantine/reject | quarantine retained | quarantine_count reflects decisions |

- **Success metric:** Post-recovery residual read-only audit shows 0 new debris; classifier current
  for all 569; mail doctor clean for R3/R4 types.
- **Gate:** R1 risk-tier sign-off; R5/R6 human release/dequarantine. Nothing runs before approval.

### F5 — Daemon re-architecture (cadence + orphan radar + reaper + linter + enrollment)  ★★★★

- **Problem:** The daemon runs **one** daily routine (`asset-dir daemon run-cycle`); it has no
  session-reaper, no **operational** orphan radar, no coherence linter, no promotion-advisory sweep,
  no enrollment-freshness. Weekly-expensive steps use a `weekly_asset_coverage_due` gate — reuse
  that pattern.
- **How to fix (hint):** Add cadence tiers and steps (all write-affecting steps ship **dry-run
  first**):

| New daemon step | Cadence | Does | Write scope |
|---|---|---|---|
| **Operational Orphan Radar** ⭐ | daily, read-only | idle open sessions, dirty/unpushed worktrees & branches, never-closed loops → `daily_review_queue` | report only |
| Session-reaper (F2) | daily dry-run; weekly apply (gated) | auto-postflight stale sessions w/ captured summary + pointer; honors exceptions | append-only |
| Coherence/conflict linter (F3) | weekly-gated | scan promoted corpus for contradictions/overlaps/dead rules | report + candidate mail |
| Promotion-advisory sweep (F3) | daily backstop | flag pending promotions missing an evidence pack | report only |
| Enrollment-freshness | weekly-gated | repos missing the runtime-agnostic lifecycle adapter | report only |

- **Key insight:** The **Operational Orphan Radar is the missing detector** — the existing
  `orphan-radar` tool + native orphan alerting only cover *asset/graph* orphans, **not**
  operational orphans (sessions/worktrees/branches/loops). Build it read-only first; it turns "I
  hope it works" into a daily signal with zero blast radius.
- **Success metric:** Daily review queue shows operational-orphan counts; reaper dry-run correct;
  linter surfaces seeded conflicts.
- **Gate:** Daemon step changes are load-bearing → risk-tier; read-only radar/dry-run steps first,
  apply variants behind the weekly gate + human approval.

---

## 3. CODEX 5.4 — lower-level, well-scoped fixes (Fable routes these)

### C1 — Drain the 268 open sessions (execution of the owner-check plan)  ★★★★
- **Problem/Evidence:** 268 open, 0 postflighted; builds live in **61 `_codex_worktrees` + 57
  DAD-attached worktrees + 8 unpushed DAD branches** — session names map to worktree names.
- **How:** Follow the scoped owner-check plan. **Lane 1 build-preservation FIRST** (read-only git
  audit → bucket each worktree/branch: clean+pushed / dirty→commit to `preserve/<name>` / unpushed→
  push or `git bundle` / detached→tag+bundle). Then Lane 2 tiered close: Tier-E ephemeral reviewers
  (`*-redteam/checker/scout/audit`, no owned build) batch-close with a 1-line finding pointer;
  Tier-B build sessions close only after their worktree is preserved + lessons captured; Tier-L
  live (<2d) excluded.
- **End state / Success:** open sessions → ~0 (excl. confirmed-live); **zero build lost** (every
  dirty/unpushed worktree preserved). **Start with the read-only disposition table (268 rows) +
  worktree preservation audit.**
- **Gate:** Never prune a worktree/branch until preserved (G4); never close a live session (G1).
  Requires F2's reaper + F5.

### C2 — Fix silent-failing `asset-dir orphan-radar run` wrapper  ★★★  (already spawned: task_589b16b9)
- **Problem:** Wrapper returns exit 1 with no stdout/stderr/report; the underlying `orphan-radar`
  tool works standalone (`scan`/`status`/`eval`).
- **How (hint):** `src/digital_asset_directory/orphan_adapter.py` + `cli.py:~10089 orphan_run`.
  Likely a stale subcommand/flag contract (tool now uses `scan`, wrapper may call `run`) and the
  adapter swallows the subprocess error. Align to the tool's current CLI, surface stdout/stderr +
  exit code, add a regression test.
- **Success:** `asset-dir orphan-radar run --src <path>` produces output or a clear error;
  regression test passes.
- **Gate:** none beyond normal review (candidate output).

### C3 — Prioritize/cap the 37,752 native orphan alerts  ★★★
- **Problem:** `orphan_review_sample.md` shows **37,752 open orphan alerts** — works but unusable
  (noise, no ranking).
- **How:** Add ranking (value_score × degree × recency) + a cap/top-N surface + intentional-isolation
  suppression, so the daily review queue shows a triage-able slice, not 37k.
- **Success:** review surface shows ranked top-N with suppression of declared-isolated assets.
- **Gate:** report-only; normal review.

### C4 — CI test routing (review + extend the prior-session diff)  ★★★★
- **Problem:** 1,348 tests ran fully on every PR, single-core.
- **Evidence/Starting point:** Already built this session (uncommitted): `pyproject.toml`
  (+`pytest-xdist>=3.6`) and `.github/workflows/validate.yml` (jobs: `changes` path-filter → `gate`
  full parallel suite on heavy PRs → non-blocking `affected-tests` testmon). Parallel-safety
  verified: 428 `tmp_path`, no session/module-scoped fixtures, 1 `chdir` (pinned by `--dist
  loadscope`).
- **How:** Review/merge the diff; **enable GitHub merge queue** in branch protection (unlocks
  subset-on-PR + full-at-merge); do a **marker pass** (only 11 `unit`/0 `slow` of 1,348 today) —
  start from `pytest --durations=25`, tag slow/unit.
- **Success:** PR wall-clock drops materially; full suite still gates at merge; docs-only PRs skip
  pytest.
- **Gate:** Load-bearing CI (medium) — full suite stays the merge gate; don't promote the testmon
  subset to required until the merge queue backstop is on.

### C5 — De-subprocess the CLI tests  ★★★
- **Problem:** Real bottleneck is process/IO, not CPU: 13 files use `subprocess.run`;
  **`test_transport.py` spawns 98 subprocesses** (each boots a Python interpreter). 216 files
  already use in-process `CliRunner`.
- **How:** Read-only audit of the 98 sites → convert logic tests to `CliRunner.invoke`; keep
  `subprocess` only where the process boundary *is* the SUT (real `git`, shim, argv, exit codes).
- **Success:** transport test wall-clock down sharply; no coverage loss.
- **Gate:** normal review. (Note: **not** a Rust task — see C9 rationale; Rust only for profiled
  CPU hot paths in *product* code.)

### C6 — Mail cleanup R3 + R4  ★★★
- **How:** `mail repair-plan` (read-only) → then dedup 97 duplicate-identity + 27 rust-rollout
  conflicts and backfill 62 legacy_collection_audit_gap provenance. Archive retains originals.
- **Success:** `mail doctor` issue_count → 0 for those types; legacy_collection_audit_gap_count → 0.
- **Gate:** after F4 sequencing; append-only.

### C7 — Enrollment freshness (reviewed, per-repo)  ★★
- **Problem:** All 82 inventory records are `active-no-write` / `central_only` on dirty worktrees.
- **How:** Per-repo `enroll update-apply` with an approval ID **once worktrees are clean**. Do NOT
  broadly rewrite.
- **Success:** stale repos current; no unreviewed cross-repo writes.
- **Gate:** reviewed approval ID per repo (fail-closed).

### C8 — Per-agent rules pointer files  ★★★★ (delivery layer of F1)
- **How:** Create thin pointers, each routing to AGENTS.md + "run preflight before material work":
  `.cursor/rules/dad.mdc`, `.github/copilot-instructions.md`, `GEMINI.md`, `.windsurfrules`
  (+ optionally aider/cline/continue). One source of truth.
- **Success:** all major agents resolve to the contract; a cold Cursor session sees it.
- **Gate:** low risk; normal review. (Enforcement backstop is F1.)

### C9 — Write the greenfield Rust-bias content  ★★★
- **Problem:** The "slight bias to Rust for new green-light components" is currently unwritten;
  `rust-buildout.json` is a neutral, profile-first decision aid (if anything Rust-restraining).
- **How:** Add a `greenfield_bias` rule to `assets/rust-buildout-guide/rust-buildout.json` (or a
  learning rule): *"New self-contained components matching `when_rust_pays_off` with a stable data
  contract → default to Rust; greenfield needs no profile/parity. Replacing working Python still
  needs profile + shadow-parity."* Green-light shapes: parsers/validators over bytes/JSONL, hashing/
  content-addressing, scanning/globbing, chunking/diffing, parallel scoring/graph math,
  distributable CLIs, daemon hot loops. Red-light: I/O glue, subprocess/git orchestration, thin
  plumbing, fast-changing logic, ecosystem-bound (pydantic/typer/networkx/LLM). Pattern to follow:
  the `tools/dad_scan_core` subprocess+JSON bridge (clap + serde_json via `src/…/rust_bridge`),
  with `cargo test` + proptest + fuzz.
- **Success:** the bias is a reviewable, cited rule; preflight can surface it for green-light tasks.
- **Gate:** touches guidance future agents inherit → fresh-eyes review.

### C10 — Dev-environment fix  ★★
- **Problem:** The `.venv` is a stripped runtime env — **no `pip`/`pytest`/dev-deps** — so agents
  can't run `pytest` locally (blocked local test verification this session). `validate` also exits 1
  on **pre-existing** staleness (exception-backfill reports, `rust_probe_shadow_parity`, graph
  manifests — the reconciliation debris), unrelated to code changes.
- **How:** Document/repair a proper dev env (`pip install -e '.[dev]'` into a dev venv, or a `nox`
  session); note the pre-existing `validate` staleness gets cleared by F4/C6 + a graph-manifest
  refresh.
- **Success:** an agent can run `pytest` locally; `validate` staleness is traceable to the
  reconciliation backlog, not new work.
- **Gate:** none.

---

## 4. Cross-cutting re-architecture (Fable's synthesis job)

After F1–F5 land, Fable should **re-architect DAD around one spine**: *runtime-agnostic lifecycle
+ deterministic gates*. Concretely: (a) session open/close, promotion, and contract-adherence are
enforced by the daemon + CI + pre-push, **not** per-runtime hooks; (b) all agents route to AGENTS.md;
(c) the promotion advisor + coherence linter guard every candidate→enforced transition; (d) the
Operational Orphan Radar + reaper keep operational state from accumulating; (e) advice-only /
harness-first for everything load-bearing, promoted only when scored. This turns the recurring
failure mode (guidance that only cooperative agents follow) into structural enforcement.

---

## 5. Prior-session starting artifacts (do not rebuild)

- **Promotion research lane (candidate):** `docs/PROMOTION_RESEARCH_LANE.md`,
  `registry/promotion-research-source-tier-registry.json`,
  `registry/promotion-research-query-templates.json`,
  `schemas/promotion-advisory-evidence-pack.schema.json`. Validated: JSON parses; sample instance
  validates. Needs the blast-radius scorer (F3) to emit the pack.
- **CI routing (uncommitted):** `pyproject.toml` (+pytest-xdist), `.github/workflows/validate.yml`.
- **Spawned task:** orphan-radar wrapper fix = task_589b16b9 (C2).
- **Recovery reports (read-only, ready):** `exceptions backfill-readiness`, `backfill-plan`,
  `mail repair-plan` produce the R1/R3/R4 diffs on demand.

## 6. Evidence pointers (privacy-safe)

- Outage window: instrumentation 2026-06-23; live capture ~2026-07-02; shim installed 2026-07-04.
- `processed/reports/exceptions_lake.json` (`sha256:15a3bdd3…`), `mail_center.json`,
  `scheduled_tasks.json`, `orphan_review_sample.md` (37,752 alerts), `daemon-heartbeat.json`.
- Sessions closed by this audit: `9d5a3199`, `fc773a59`, `cdf36202`, `8e2e21c8`, `14c32b52`
  (this handoff's own session pending postflight).
- CLI resolution order (confirmed): bare `asset-dir` → `~/.dad/bin/asset-dir.ps1` →
  `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli`.

## 7. Global guardrails (apply to every item)

Read-only until the named gate. Never store secrets/private rows/legal-client contents. Preserve
provenance + confidence labels. Keep changes narrow + reversible. Candidate-until-reviewed;
harness-first for load-bearing; profile-before-Rust when replacing Python. Postflight every material
item with the five review lanes closed.
