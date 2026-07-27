# START HERE — LawFirm OS / DAD Multi-Agent Orchestration Home

This directory is the **coordination plane** for building the LawFirm OS repo family
with a multi-agent team. It runs **from the DAD repo**, which is the *operational OS /
orchestration home* — **not** an authority plane. Semantic Substrate remains canon.

**Integrator (Codex)**: read `CODEX_TAKEOVER_HANDOFF.md` first, then this file.
**Any worker (Composer/GLM/GPT-5.5)**: skip the handoff, read this file and do your role.
**Checker (paired model)**: read this file, then your spec, then COORDINATION_PROTOCOL.md §7.
**Fable (boss, disputes only)**: the handoff memo will re-invoke you when needed.

---

## Required read order

1. `orchestration/START_HERE.md` (this file)
2. `orchestration/DEFINITION_OF_DONE.md` — the constitution enforced on every task
3. `orchestration/COORDINATION_PROTOCOL.md` — claims, leases, merge train, report/verdict formats, dispatch mode
4. `orchestration/AGENT_REGISTRY.json` — who exists, their tier, their limits
5. `orchestration/ESCALATION_POLICY.md` — when to call a higher tier
6. `orchestration/ARCHITECTURE_PACKET.md` — the master design (Fable-owned)
7. `orchestration/PORTFOLIO.md` — active programs + repo-touch matrix; then your program's
   `orchestration/programs/<program_id>/ROADMAP.md`
8. `orchestration/TASK_BOARD.jsonl` + `orchestration/TASK_BOARD.schema.md` — the work bus
9. Your task's spec in `orchestration/specs/T-XXXX.md`
10. The **target repo's** own `AGENTS.md` / `AI_WORK_START_HERE.md` before editing it

---

## The model (blackboard, not a call graph)

The agents live in **independent tools/subscriptions and cannot invoke each other**. The
only shared state is **this filesystem + git**. So coordination is a *blackboard*:

- `TASK_BOARD.jsonl` is the append-only bus and the audit trail.
- Agents **claim** a task (lease), work it on a **branch in the target repo**, open a **PR**,
  and record events back to the board.
- A **checker agent** (a *different model than the worker*) **executes** the work and decides
  "done" — the worker's own success claim is ignored.
- Async messages/handoffs go through **DAD mail** (`mail/` and `.digital-asset/mail/`),
  referencing the `task_id`.

Co-located agents (same machine) coordinate via these files directly. Isolated/cloud agents
coordinate via the git remote + committed board and mail; the **PR is the handoff unit**.

---

## Roles

| Role | Model(s) | Does | Never does |
|---|---|---|---|
| **Boss / Architect** | Claude Fable | Specs, roadmap, task partition, reviews, rules disputes, promotes | Writes production code |
| **Hard coder** | GPT-5.5 | Difficult kernels, escalations | Touches canon without a boss ruling |
| **Cheap coder** | Cursor / Composer 2.5 | Bulk file-scoped PRs from specs | Infers authority; self-approves |
| **Cheap coder (foreign)** | GLM 5.2 | Bulk file-scoped PRs from specs | Merges without a backdoor scan |
| **Checker** | any model ≠ the worker | Executes the PR, verdicts against DoD | Trusts the worker's self-report |

The boss's own output is checked too. **No rank is above verification.**

---

## How to work a task (every coder)

1. Read this file, `DEFINITION_OF_DONE.md`, and your `specs/T-XXXX.md`.
2. Confirm the task is `open` and its `depends_on` are all `done`.
3. Append a `claimed` event (with `lease_until` and `base_sha`) to `TASK_BOARD.jsonl`. If another
   agent — in **any program** — has claimed overlapping `paths` in the same repo, do not proceed.
   If your task touches a file listed in `HOT_FILES.json` for the target repo, you also need the
   repo write-lease in `REPO_LEASES.jsonl` (the integrator grants it).
4. Create the branch named in the spec **in the target repo**. For the intake vertical, the
   target is **B** = `repos/LawFirm-os-intake-seed-clean-20260623` — **never** the stale root
   `LawFirm-os-intake` ("A").
5. Make only the changes in the spec's `paths`. Add fixtures + tests + validators as required.
6. Every code/artifact carries the **provenance block** (see `DEFINITION_OF_DONE.md` §Provenance).
7. Open a PR (no direct push to `main`). Append `pr_opened` to the board and update your
   `status/<agent>.status.json` heartbeat.
8. A checker (different model) executes it and appends `check_result`. If `fail`, fix and
   resubmit; on the **second** fail, escalate per `ESCALATION_POLICY.md`.
9. On `done`, append the `done` event with `merged_sha`.

## How to review a task (checker)

- **Execute** it: run the validators/tests, re-derive any claimed canonical value against the
  Substrate `registry/source-of-truth.json` (never model memory).
- Verdict `pass` only if the DoD constitution holds in full. If the worker's output is
  correct-but-unexpected and your check was too strict, **escalate to the boss** — disputes go
  both ways.

---

## Hard invariants (fail closed)

- DAD is the orchestration home, **not** an authority. Substrate stays canon.
- **Cross-repo WRITES fail closed until decision `D17` is recorded** (see `decisions/`). Until
  then, the boss may read, plan, and emit specs only.
- No real client/matter/privileged/carrier-private/firm-private/negotiated-rate data.
- No external writes, connectors, DAD hub network sync, Lake writes, budget/appeal submission,
  profile mutation, or conflict clearance.
- No DAD-private catalog content (ids, paths, scores, ranks, dependency graphs, strategy) in
  any non-DAD commit.
- AI output proposes; it never becomes legal/compliance/governance authority without reviewed
  human promotion.
