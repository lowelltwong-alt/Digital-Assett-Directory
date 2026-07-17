# Codex 5.4 Execution + Audit Handoff

Date: 2026-07-17
Author: Fable 5 (Claude), from the interactive execution session that landed PRs #57 and #59.
Audience: **Codex 5.4** - mid-risk-and-below execution, plus a full independent audit of
Fable's work. Status: advice-only; every item names its gate. Follow `AGENTS.md`:
preflight before each item (`asset-dir agent preflight --repo . --agent codex --task "<item>"`),
postflight after with the five review lanes, include the printed `DAD-Session:` trailer in
commit messages (the contract check now watches for it, warn-mode).

Default intelligence tiers per `config/intelligence-routing-registry.json`:
mechanical items at codex-luna, standard builds at codex-terra, red-team/audit at codex-sol.
codex-ultra requires named human approval - none of the items below needs it.

---

## 0. Read first

`AI_FRONT_DOOR.md`, `MACHINE_NAVIGATION_MANIFEST.json`, `registry/source-of-truth.json`,
`AI_TABLE_OF_CONTENTS.md`, `AGENTS.md`, `registry/non-negotiables.json`, then
`docs/handoffs/FABLE5_MASTER_HANDOFF_2026-07-16.md` (the spec Fable worked against), then
`docs/DAD_INTELLIGENCE_MESH_AND_STREAM_OS_ARCHITECTURE.md` (the architecture behind N-items),
then this file. The repo moves fast and concurrently: **fetch origin and diff against
origin/main before diagnosing anything as missing or stranded** (Fable lost an hour to a
17-commit-stale checkout).

---

## 1. Complete record of Fable's work (2026-07-16 to 2026-07-17) - audit against this

Everything below is verifiable; nothing requires trusting the narrative.

### 1.1 Landed code (PRs - audit lane X1 targets these)

- **PR #57** (merge 6465e21): routine-contract foreman + warn-only lifecycle contract check.
  Commits: e0d46c0 (contract check), 2dd5169 (foreman), 08712ae (merge + portability
  dispositions), 7c94da7 (merge origin/main + digest re-pins), 97104d1 (CI scope exception,
  human-reviewed by Lowell), 4f2cca4 (.githooks module ownership), f63a4f5 (accepted both
  Codex-bot review findings: CI job now runs --mode policy; hooks propagate exit codes).
- **PR #59** (merge e7b3d4e): removed the temporary PR57 CI exception per the PR56/58 precedent.
- New surfaces: `src/digital_asset_directory/routine_health.py`, `contract_check.py`,
  `scripts/contract_check.py`, `registry/routine-contract-registry.json`,
  `registry/contract-check-policy.json` (+ 2 schemas, schema-registry rows, TOC rows),
  `.github/workflows/dad-contract-check.yml` (declared + digest-pinned in
  `.ci/module-boundaries.yaml`), extended `.githooks/pre-push{,.ps1}`, postflight now prints
  the `DAD-Session:` commit trailer, `asset-dir agent contract-check` and
  `asset-dir routines health` CLIs, tests `test_routine_health.py` (12) and
  `test_contract_check.py` (10).

### 1.2 Operational actions (audit lane X2)

- **Lane-1 preservation (2026-07-16):** 64 worktrees audited; 15 dirty ones captured as
  patches + untracked copies to `~/.dad/preserve/2026-07-16/` with `disposition_table.json`;
  all-refs bundle `dad-all-refs.bundle` (5.6MB); all detached HEADs verified branch-reachable.
- **C1 drain (human-approved):** 139 stale sessions closed via tiered administrative
  postflights. Liveness rule: session-file idle >= 6h (only Fable's own sessions were under
  it). Every close is non-blank with the preservation pointer; ledger `drain_ledger.jsonl`
  in the session scratchpad (path in the closing handoffs). ~20 sessions had duplicate
  records in BOTH `state/agent_sessions/` and the data root - see N1.
- **Scheduled task:** user-level `weekly-skill-orphan-radar` disabled 2026-07-16 (its script
  exists only in WIP commit 01e3063 on `codex/skill-need-orphan-radar-hardening-20260713`;
  it was burning tokens weekly against a missing dependency).
- **Parked (verified copies in `~/.dad/preserve/2026-07-16/main-untracked/`):** the three
  promotion-research registry/schema artifacts (pending F3 dispositions) and the prior
  session's C4 CI diff (branch `preserve/c4-ci-test-routing`, superseded by PR #55's CI rewrite).
- **Superseded duplicate lines (do NOT rebuild from):** local branches
  `codex/dad-portfolio-os-kernel` and `codex/portfolio-os-kernel-opus` - their content
  landed in evolved form via PRs #45-#55.

### 1.3 Session/lifecycle evidence

Fable sessions (all closed with five lanes): 02d828f2 (F1 investigation),
c68164b7 (mesh investigation), a16181e2 (A/D/B/C/F1 execution), d0dcf42e (C1 drain +
landing), 4af351d7 (this architecture + handoff). Handoffs are queryable in the learning
store by those session ids.

### 1.4 Known residual issues Fable did NOT fix (honest debts)

- 12 pre-existing graph-surface-manifest hash inconsistencies make local
  `cli validate` exit 1 (identical on clean main; CI is hermetic and unaffected).
- `.codex-check-temp/` contains two embedded git worktrees inside the hub tree (N3).
- 3 unread items in the hub mail inbox await human triage.
- The OneDrive-hosted `.git` produced one unexplained git-log anomaly on 2026-07-16;
  documented in memory as a sync-desync risk, unresolved.

---

## 2. Audit lanes (do these FIRST, at codex-sol effort)

### X1 - Independent audit of the landed code (leverage: highest)
Red-team PRs #57/#59 as if reviewing a stranger's work: correctness of
`routine_health.py` status logic (glob newest-match, dual-root data resolution,
freshness boundaries), `contract_check.py` (trailer regex, base-resolution via merge-base,
PR-body fallback, bypass semantics - can a malformed-but-plausible trailer slip through?),
the pre-push hooks (does exit-code propagation hold on Windows PowerShell AND sh? test the
ps1 path on a real Windows push), the portability card additions in 08712ae/7c94da7 (were
the 10 file additions to `harness:portable-capability-control-plane` semantically right, or
should some files have their own cards?), and the CI declaration digests. File findings as
review comments or a candidate report; fix only with normal review. Success: written verdict
per component with any findings reproduced.

### X2 - Audit the drain
Sample >= 20 closed sessions from the drain ledger: verify each has a handoff record, the
preservation pointer, and that no session with idle < 6h was closed. Verify the census math
(140 -> 0 excluding Fable's own). Check for sessions the liveness rule may have wrongly
closed (any agent that was actually alive will fail its own postflight - search for
postflight errors after 2026-07-17T12:00Z). Success: sampled verification report.

---

## 3. Routed execution items (mid-risk and below)

Every item: preflight, narrow diff, tests, postflight + trailer, PR (the Codex review bot
and conversation-resolution gate apply to you too - answer findings before merge).

### C8 - Per-agent rules pointer files (tier: luna)
Create thin pointers, each ~5 lines: "Read `AGENTS.md`. Run `asset-dir agent preflight`
before material work. Postflight prints a `DAD-Session:` trailer - include it in your
commit message; protected-path changes without it are flagged by the contract check."
Files: `.cursor/rules/dad.mdc`, `.github/copilot-instructions.md`, `GEMINI.md`,
`.windsurfrules`, `.aider.conf.yml`, `.clinerules`, `.continue/config.json` (use each
tool's native format; content identical in substance). Gate: normal review. Success: all
pointers resolve to AGENTS.md; a cold session in each tool sees the contract.

### C9 - Greenfield Rust-bias content (tier: terra)
Per the 2026-07-16 handoff C9 brief verbatim: add the `greenfield_bias` rule to
`assets/rust-buildout-guide/rust-buildout.json` with green-light/red-light shapes and the
`tools/dad_scan_core` bridge pattern. Gate: fresh-eyes review (guidance future agents inherit).

### C2 - Fix the orphan-radar wrapper (tier: terra; task_589b16b9 exists)
`orphan_adapter.py` + `cli.py` `orphan_run`. Align to the tool's current CLI, surface
stdout/stderr/exit code, regression test. THEN update the `orphan-radar-wrapper` row in
`registry/routine-contract-registry.json`: set a real consumer and freshness once wired.
Success: wrapper produces output or a clear error; foreman row goes meaningful.

### C3 - Rank/cap the 37,752 orphan alerts (tier: terra)
Ranking (value_score x degree x recency, cite the methodology fields you use) + top-N
surface + intentional-isolation suppression. Report-only. Success: triageable slice.

### C4-revised - CI acceleration remnants (tier: terra)
The old C4 brief is superseded by PR #55's selector architecture. Remaining value only:
(a) add pytest-xdist to dev deps and `-n auto --dist loadscope` to the python suite
command (verify parallel-safety claims from the old brief still hold), (b) propose - do
not enable - GitHub merge queue in a short doc for Lowell. Gate: load-bearing CI = warn
first; the full suite stays the gate.

### N1 - Session split-state fix (tier: terra to sol)
Problem (found during the drain): session records exist in BOTH `state/agent_sessions/`
(legacy) and the data root; `open_sessions` dedupes by filename with data-root wins, but
writers disagree, so a session can be closed in one copy and open in the other (~20 cases).
Fix in `learning.py`: single canonical write path with legacy fallback read-only, plus a
one-shot reconciliation command (dry-run first) that merges duplicate records preferring
the closed/newer state. Gate: dry-run report reviewed before apply; this touches the
enforce gate's data source, so add regression tests around `open_sessions`.

### N2 - Reaper dry-run CLI (tier: terra; F2 groundwork)
Port the drain logic (tiering, idle-time liveness, non-blank summaries with preservation
pointers, JSONL ledger, drain-operator checklist lanes) into
`asset-dir agent reaper --dry-run` as a first-class command with tests. The drain script
pattern lives in session d0dcf42e's handoff record. **Apply mode is out of scope** - F2's
gate (G5) keeps apply human-approved until the reaper earns it.

### N3 - Worktree hygiene (tier: luna)
Remove the two embedded worktrees under `.codex-check-temp/` (git worktree remove after
confirming clean + preserved - check `~/.dad/preserve/2026-07-16/disposition_table.json`;
both were clean), add `.codex-check-temp/` to `.gitignore`, and document the rule: hub-tree
worktrees live under `.claude/worktrees/` or outside the repo, never ad-hoc in tracked space.
Gate: preservation check before removal; never prune dirty/unpushed.

### N4 - Capture inbox (tier: terra; Stream OS kernel A, architecture 1.3)
`asset-dir os capture --raw "<line>"` append path + `~/.dad/inbox.md` drop-file ingestion +
the daily structuring routine (report-only, luna-tier prompt packaged as a routine spec).
Register the routine in `registry/routine-contract-registry.json` (artifact: structured
captures JSONL; freshness 26h). Gate: report-only; no auto-created workstreams without the
existing `os` human-decision surfaces.

### N5 - Convergence radar (tier: terra; Stream OS kernel C, architecture 1.5)
Deterministic branch/worktree same-intent scan (name tokens + touched-path overlap +
merge-base distance) producing a top-5 merge-proposal report for the cockpit. No model
calls in v1. Register with the foreman. Gate: report-only; merges/closes remain
human-approved each.

### N6 - Skill-family scaffolds (tier: terra; architecture 4)
Scaffold `assets/agent-skills/full-stack-engineer-family/` and
`machine-learning-family/` per the landed packaging convention, with per-role
`default_tier`, `stable_worker`, `improvement_policy` metadata per the architecture.
Check `processed/agents/subagent-role-directory.json` first and point to existing roles
rather than duplicating (semantic-evolution rule). Gate: candidate skills; library
registry entry + local review before any checkout.

### N7 - Routing-registry consumers (tier: terra; architecture 2.1)
(a) Preflight surfaces the recommended start tier for the task class (advice-only string
in the context pack); (b) add `default_tier` fields to existing skill metadata; (c) a tiny
validator test that every referenced tier_id exists in the registry (extend
`tests/test_intelligence_routing.py`). Gate: advice-only.

### N8 - Cross-vendor review-lane mechanics (tier: luna to terra; architecture 2.2)
A short policy doc + PR template line ("cross-vendor review: yes/no/why") + a checklist
entry in the review lanes. Explicitly list the human-owned settings (Codex connector review
config, branch protection, bot installs) - do not touch them. Gate: docs/process only.

### N9 - Learning-loop yield report (tier: terra; architecture 3.2)
Monthly report-only meta-loop: per loop, records written vs reused vs promoted, with the
anti-gaming rule (architecture 3.3) embedded: reuse facts only, no self-reported scores.
Gate: report-only.

---

## 4. Sequencing

X1/X2 first (audit before building on Fable's surfaces). Then N1 (data-integrity
prerequisite for everything session-shaped), then C8/N3 (cheap wins), then N4/N5
(Stream OS), then C2/C3, then N7/N8/N6, then C9, then N9, then C4-rev. One PR per item,
narrow diffs.

## 5. Standing constraints

Preservation-first, candidate-until-reviewed, no secrets in mail, mailbox-only recurring
writes, contract-check trailers on every PR, and the merge-gate playbook: required check
`local-full-suite`, strict up-to-date, **required conversation resolution** (unresolved
review threads are the usual invisible blocker), CI-contract scope changes need a
human-reviewed exception in `.ci/module-boundaries.yaml`, every changed path must be
module-owned, workflow files are digest-pinned, and changes to files pinned by
`registry/portable-capability-registry.json` cards (notably `cli.py`,
`registry/schema-registry.json`) must re-pin the card digest in the same commit
(`portability_control._portable_files_digest`). Also: runtime-naming policy files cannot
live in portable_core cards (hard gate `normative_runtime_binding_in_source`) - that is
why the intelligence-routing registry lives in `config/`, which is outside the governed
prefixes, while its vendor-neutral schema is carded in `schemas/`.
