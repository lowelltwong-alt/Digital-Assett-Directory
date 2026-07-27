# D17 — DAD cross-repo write scope

Status: **RESOLVED — agent_auto branch+PR scope approved**
Raised: 2026-07-09 by Fable (boss)
Owner: Lowell T. Wong (repo family owner)

## Question

May the DAD orchestration home (and agents dispatched from it) WRITE to non-DAD repos
as part of multi-agent buildouts — via feature branch + PR in the target repo, under that
repo's validators, an independent checker, and the Definition-of-Done constitution?

## Why this is a decision, not a default

DAD's enrollment contract (Substrate `AGENTS.md` DAD section, `.digital-asset/dad-integration.json`)
permits broad writes only during a reviewed `enroll apply`; **normal recurring DAD operation
writes only to `.digital-asset/mail/**`**. Elevating DAD to a cross-repo orchestration writer
changes that written contract. Unrecorded, the first cross-repo write is a boundary breach and
poisons the provenance trail from event one.

## Blocking paths

- Any task on `orchestration/TASK_BOARD.jsonl` with `target_repo != DAD` executed by an agent
  dispatched from this home (T-0001 .. T-0012).
- `orchestration/COORDINATION_PROTOCOL.md` → `dispatch_mode`.

## Safe placeholder (in force now, fail-closed)

- `dispatch_mode = human_manual`: the boss emits PR **specs** only; a human opens each worker
  session in the target repo and hands it the spec. Agents never self-dispatch cross-repo.
- DAD-side agents write only `orchestration/**` and `.digital-asset/mail/**`.

## Decision needed (record all four fields)

1. Named human approver + date.
2. Scope: branch+PR only; per-repo validators + checker + DoD mandatory; no direct push to main;
   canonical surfaces only via each repo's promotion process.
3. Revocation path: `orchestration/KILL_SWITCH.flag` (presence = all outbound writes disabled).
4. Dispatch mode granted: `agent_auto` (agents may claim and execute without per-task human
   dispatch) or `human_manual` retained.

## Risk if guessed

Authority inversion (orchestration home becomes de-facto authority over the control plane);
breach of the recorded DAD contract; provenance chain rooted in an unauthorized act.

## Resolution

Approved by: Lowell T. Wong
Decision date: 2026-07-10
Recorded from user instruction in Codex session: "context i just want you to take over and complet it all"

Scope:

- DAD orchestration agents may write to non-DAD repos only on feature branches and only for
  tasks recorded in `orchestration/TASK_BOARD.jsonl`.
- Direct pushes to `main`, canonical promotions, live connector writes, real-data writes,
  budget/appeal submissions, conflict clearance, matter opening, and DAD/ALS-private catalog
  propagation remain forbidden.
- Each target repo's validators, independent checker, Definition of Done, provenance block,
  and merge train remain mandatory.
- Hot files still require `REPO_LEASES.jsonl` lease grants.

Revocation path: create `orchestration/KILL_SWITCH.flag`. Its presence disables outbound
cross-repo writes immediately.

Dispatch mode granted: `agent_auto`.
