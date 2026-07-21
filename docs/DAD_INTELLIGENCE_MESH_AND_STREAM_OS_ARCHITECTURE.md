# DAD Intelligence Mesh and Stream OS - Architecture

Status: candidate architecture (advice-only), authored by Fable 5, 2026-07-17.
Gates: every build derived from this document ships report-only or dry-run
first per `docs/LOAD_BEARING_DECISION_REVIEW.md`. Mid-risk-and-below builds are
routed in `docs/handoffs/CODEX54_EXECUTION_HANDOFF_2026-07-17.md`.

Ordered hardest-and-highest-leverage first, per Lowell's instruction.

---

## 1. The Stream OS - a system shaped like the operator's mind

### 1.1 The observed pattern (evidence, not theory)

- Ideas arrive **mid-stream**, inside other work - including inside a single
  prompt ("just like in this prompt").
- Interruptions are the norm: new directives land while an agent is mid-task,
  and the interrupted thread is what gets lost.
- Lost threads resurface later as **restarts elsewhere**: 64 worktrees, 77
  branches, two independent portfolio-OS kernel builds, three orphan radars.
- The cost asymmetry: capturing a thought must be cheaper than losing it, and
  resumption must be automatic, because attention will not come back on its own.

### 1.2 What already exists (build on, never rebuild)

Landed on main: `asset-dir os capture/capsule/workstreams` (event-sourced
workstream kernel with resume capsules), `os status` (worktree/branch attention
scan + HTML dashboard), `portfolio_attention`, the cockpit control plane design,
`dad-work-router` and `dad-iteration-optimizer` skills, the routine-contract
foreman, and the lifecycle contract check.

The gaps are exactly three: **capture friction**, **interruption debt**, and
**convergence**.

### 1.3 Kernel A - Zero-friction capture inbox

One append-only surface that accepts a raw one-liner with no structure
required, from any context:

```text
asset-dir os capture --raw "cockpit needs a bottleneck lane"
```

plus a drop-file fallback (`~/.dad/inbox.md`, one line per thought) for moments
when even a CLI is too much. A **daily structuring routine** (tier:
codex-luna / claude-haiku-4.5 - cheapest, per
`config/intelligence-routing-registry.json`) turns raw lines into structured
workstream candidates via `dad-work-router`, links duplicates to existing
workstreams instead of creating new ones, and queues ambiguous lines for a
one-tap human decision in the cockpit. Registered in the routine-contract
registry so the foreman notices if it ever stops running. Nothing is ever
deleted; structuring is append-only over the raw log.

V1 status (2026-07-20): `os capture --raw` and the explicit-path
`os capture-inbox` adapter are implemented with global byte/line/line-length
budgets, source-byte immutability, minimized append-only candidates, and a
sanitized operational-cockpit view. The routine contract is registered but
disabled. Creating `~/.dad/inbox.md`, scheduling the 26-hour routine, model
routing, and automatic workstream creation remain separately human-gated.

### 1.4 Kernel B - The interruption contract

A standing agent contract (AGENTS.md addition + skill), with a deterministic
backstop:

1. When a session receives a new directive that pivots away from in-progress
   work, the agent MUST, before pivoting: (a) write a resume capsule for the
   interrupted thread (`os capsule`), and (b) capture the new directive's
   novel ideas (`os capture`). Cost: seconds. This mirrors what cooperative
   agents already do informally; the contract makes it uniform.
2. Deterministic backstop (because advice only reaches cooperative agents):
   session records gain an `interrupted_by` pointer; the daily attention scan
   flags sessions that pivoted (task text changed materially or session closed
   with uncommitted worktree) without a capsule. Flags feed the cockpit
   attention lane, capped top-N.
3. Resumption: resume capsules already exist; the missing piece is surfacing -
   the cockpit's attention lane orders capsules by (age x leverage x
   staleness-risk), and the daily review queue includes the top three
   "threads you dropped" with one-command resume.

### 1.5 Kernel C - Convergence (branches that should meet)

A daily **report-only** convergence radar over branches/worktrees:

- Cheap deterministic pass first: branch-name token similarity + overlapping
  touched paths + shared merge-base distance. Zero tokens.
- Only the top candidates go to a cheap model pass to confirm same-intent.
- Output: a merge-proposal queue (pairs, overlap evidence, suggested
  direction, preservation status) into the cockpit. **Merging stays
  human-gated**; a "closure crew" routine (tier: codex-terra) executes
  approved merges/closes one at a time, preservation-first, and records the
  outcome.
- The 2026-07-16 preservation audit + drain are the precedent: preserve,
  then close; never prune unpreserved work.
V1 status (2026-07-19): the zero-model deterministic pass, strict report,
on-demand foreman contract, and sanitized top-five operational-cockpit view are
implemented in `portfolio_convergence.py` and
`portfolio_convergence_git.py`. The optional model confirmation pass and
closure crew remain unimplemented and separately gated; the deterministic
score is review priority, never a same-intent decision.


### 1.6 Real-time posture

The daemon stays the spine (F5 cadence tiers). "Real time" is achieved not by
a resident model but by cheap deterministic watchers (foreman contracts, os
status, attention scan) that run on schedule, plus event-driven agent
contracts at the moments that matter (interruption, capture, push). This is
the token-efficient version of a real-time OS: models run only when a
deterministic signal says something changed.

---

## 2. Intelligence routing and the adversarial review mesh

### 2.1 Routing ladder

`config/intelligence-routing-registry.json` is the kernel: vendor tiers
(codex-luna/terra/sol/ultra; claude-haiku/sonnet-low..high/fable), task-class
default tiers, one-step escalation with recorded reasons, and **fail-closed
human-approval gates for codex-ultra and claude-fable**. Fable is reserved for
the hardest, highest-leverage, highest-risk problems and top-of-ladder
disagreement arbitration - never a default.

Consumers to wire (routed to Codex): preflight surfaces the recommended tier
for the task class; every skill/subagent declares `default_tier` in its
metadata; dispatch records the tier used so de-escalation evidence accumulates.

### 2.2 Adversarial cross-vendor review mesh

Proven live on PR #57: the Codex review bot caught a real promotion-path bug
in Fable-authored code. Systematize it:

- **Rule: the reviewer's vendor differs from the author's** whenever both
  vendors are available. Claude-authored PRs get Codex bot review (already
  automatic); Codex-authored PRs get a Claude review lane (`/code-review` on
  the PR) before merge.
- Review findings must be answered or fixed; `required_conversation_resolution`
  on main is the deterministic backstop (it blocked PR #57 until threads were
  resolved - working as designed).
- **Disagreement ladder:** author and reviewer disagree after one reply round
  -> escalate the review one tier; disagreement persists at sol/sonnet-high ->
  human, with claude-fable arbitration available by human approval only.
- **Capability scouting routine** (weekly, report-only): scan both vendors'
  released agent capabilities (bots, review modes, skills) and file candidate
  mail proposing adoptions. External research is candidate-only per the
  trusted-source rules.
- Human-owned settings (agents cannot and must not change these): the Codex
  GitHub connector's review settings, branch protection, and any new bot
  installation.

---

## 3. Learning loops that actually improve

### 3.1 Inventory before invention

Existing loops: preflight/midflight/postflight + five review lanes, lessons
and handoffs, tactic-use feedback, semantic-evolution grading, subagent
attempt ratings + integrity kernel (honest self-prediction vs outcome),
harness discovery radar, exception learning queue, rust rollout lessons.
The problem is not loop scarcity - it is **yield measurement and closure**.

### 3.2 The meta-loop (measure yield, not activity)

A monthly report-only pass: for each loop, count (a) records written, (b)
records ever **reused** (cited by a later session, surfaced by preflight and
acknowledged, or promoted), (c) time-to-reuse. Loops with high write volume
and near-zero reuse are candidates for merge/retire - the same
stable-worker/upgrade/replace/workflowize/retire decision table used for
subagents (see section 4). No synthetic benchmarks: the only metrics are
outcome facts (reuse, closure, incident correlation) that cannot be gamed by
writing more records.

### 3.3 Anti-benchmark-gaming rule

Any claimed self-improvement must name the **outcome fact** it moved (PRs
landed, findings caught pre-merge, threads resumed, duplicate work avoided,
tokens saved at equal quality) and the measurement window. Improvements that
only move self-reported scores are recorded as `unverified_claim` and never
promoted. The subagent integrity kernel (self-prediction vs outcome audit)
extends to skills: a skill revision's claimed gain needs a before/after on
real tasks, sampled by an evaluator from the other vendor.

### 3.4 Research intake

The promotion-research-lane artifacts (parked 2026-07-16 in
`~/.dad/preserve/2026-07-16/main-untracked/`, pending F3 dispositions) already
define source tiers (T1 standards to T4 excluded) and query templates. The
routine version: weekly, report-only, tier codex-terra/claude-sonnet-medium -
pull trusted-source updates relevant to active workstreams and file candidate
upgrade mail with citations. Nothing auto-adopts.

---

## 4. Skill families and the stable-worker doctrine

### 4.1 Families

Packaging follows the landed convention
(`assets/agent-skills/<family>/SKILL.md` + `subagents.yaml` +
`agents/openai.yaml` + `routines.yaml`) so any runtime can invoke them.
Initial families (scaffolding routed to Codex; role content is the build):

- **full-stack-engineer-family**: architect (sol/sonnet-high), builder
  (terra/sonnet-medium), test-engineer (terra), reviewer (cross-vendor,
  terra+), mechanic (luna/haiku - formatting, renames, migrations).
- **machine-learning-family**: problem-framer (sol), data-contract steward
  (terra), evaluation-integrity auditor (reuses the landed kernel; terra),
  research-scout (terra, report-only), implementation pair (terra/sol).
- Each role declares `default_tier`, `stable_worker` (bool), and
  `improvement_policy` in its metadata.

### 4.2 Stable-worker doctrine (when NOT to improve)

From the subagent-mesh design, now policy: a role with >= N attempts, success
at threshold, no failure-cluster growth, and an unchanged input contract is
`stable_worker: true` - the improvement lane skips it; only the foreman
watches its output contract. Changes to a stable worker require the same
supersession review as replacing it. The decision table:
upgrade (failures cluster in instructions) / replace (structural failure or
two failed upgrades) / combine (high overlap + complementary strengths) /
**workflowize** (near-zero variance: demote to deterministic script; the
token ratchet) / retire (kill criteria met).

---

## 5. Cockpit integration (one glass, never overwhelming)

The landed cockpit control-plane design (feed-first, three layers, pertinence
methodology) gains four capped lanes, all report-only feeds:

1. **Dropped threads** - top 3 resume capsules by age x leverage.
2. **Convergence queue** - top 5 merge/close proposals with one-tap approve.
3. **System health** - foreman routine statuses + contract-check probation
   counters (violations observed, bypasses, days to review date).
4. **Leverage** - bottleneck analysis from the capacity mesh (#49) + the
   "one decision that unblocks the most" per day.

Everything else stays in drill-down. The cap is the feature: the cockpit's
job is to return attention to the highest-leverage thread, not to display
everything.

---

## 6. Build order (hardest first, every step gated)

| # | Build | Owner | Gate |
|---|-------|-------|------|
| 1 | Capture inbox (`os capture --raw` + drop file + structuring routine) | Codex (N4) | report-only routine; registered with foreman |
| 2 | Convergence radar (report-only) + closure-crew executor | Codex (N5) | radar report-only; closures human-approved each |
| 3 | Interruption contract + deterministic backstop | Fable (contract) + Codex (backstop scan) | AGENTS.md change = load-bearing, warn-first |
| 4 | Routing-registry consumers (preflight surfacing, skill tier fields) | Codex (N7) | advice-only surfacing |
| 5 | Cross-vendor review-lane mechanics | Codex (N8) + human (bot settings) | policy doc + labels; humans own settings |
| 6 | Skill-family scaffolds | Codex (N6) | candidate skills; local review before checkout |
| 7 | Meta-loop yield report | Codex (N9) | report-only |
| 8 | Research-intake routine | Codex, after F3 dispositions | report-only, trusted sources only |

Reflexive changes (anything that modifies DAD's own scoring, promotion, or
learning machinery) remain permanently human-gated per F3.
