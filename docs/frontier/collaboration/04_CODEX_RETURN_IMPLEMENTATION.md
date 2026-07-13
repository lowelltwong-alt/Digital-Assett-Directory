# Phase 5 — Codex Return Implementation and Verification

Date: 2026-07-12. Worktree:
`_codex_worktrees/dad-portfolio-os-kernel-opus`. Branch:
`codex/portfolio-os-kernel-opus`.

Status: implemented and independently rechecked in the working tree; deliberately
uncommitted. No recurring routine, Git mutation executor, hook, daemon, branch,
worktree, Codex task, or cross-repo write was created.

## Outcome

Claude's Model C remains the architecture: one append-only ledger, one pure fold,
assertion projections instead of a second canonical graph, humane conditional
attention, and a separately gated future mutation executor. Codex retained that
shape and replaced the unsafe implementation organs found during return review.

The completed V0.1 kernel now provides:

- strict runtime JSON Schema validation, recursive privacy minimization, verified
  event hashes, linear per-stream predecessors, duplicate conflict diagnostics,
  torn-tail quarantine, write-all/fsync, and a nonce-owned Windows-aware lock;
- explicit caller `request_id` idempotency instead of UTC-day guessing, with
  mutable commands treated as new intent when no request ID is supplied;
- deterministic lifecycle projection with expired-snooze resurfacing, terminal
  capsule noninterference, explicit `keep`, and reject/reset dismissal epochs;
- material trigger signatures and material Today fingerprints, so changed
  blockers/reasons surface even when the trigger class is unchanged;
- proposed dependency assertions that cannot affect rollups until a named human
  accepts them, plus self/cycle diagnostics and append-only retraction events;
- a Scrum-style lifecycle board, transitive bottleneck rollup, coverage honesty,
  calibrated relation feedback, and divergence/sprawl separation;
- an explicit V1 snapshot input to the pure fold; `os refresh` refreshes the
  read-only Git snapshot before folding and records its hash/as-of coverage;
- V0.1 Project entities and human-approved sovereignty transitions for DAD
  children such as LawFirm OS, without overriding child-domain facts;
- CLI failure exit codes for rejected writes, schema/navigation registration,
  and a self-contained local HTML board.

## Return-review findings closed

1. Legal short writes can no longer be acknowledged as complete.
2. The persistence boundary minimizes and strictly validates every incoming row.
3. Head selection/rebase occurs under the owned append lock; concurrent writers
   cannot fork a stream.
4. Read verifies schema, event identity, predecessor continuity, and duplicate
   conflicts; tampering becomes a diagnostic and blocks extension.
5. Explicit request IDs distinguish retries from legitimate repeats.
6. Idea and capsule identities are computed from minimized inputs.
7. Expired snoozes resurface; terminal capsules cannot change later projections.
8. Conflict resolution requires `keep`, `merge`, `supersede`, or `archive`.
9. Dismissal convergence has an explicit reject/reset epoch.
10. Proposed, accepted, cyclic, self, and retracted dependencies are distinct.
11. Material Today content changes are detected, not just signature ordering.
12. Sovereignty events are folded into visible Project state rather than ignored.

## Architecture adjudication

- **Day-bucket retry guard:** removed. Caller request identity is the supported
  retry mechanism.
- **Dismissal threshold:** default three remains a pilot policy, now bounded by
  explicit trigger epochs and rejection reset; real-use calibration is still
  required.
- **V1 join:** passed as an immutable explicit fold input with source hash and
  as-of time; no hidden I/O occurs inside the fold.
- **Mutation executor:** remains permanently outside the kernel. A future executor
  consumes approved proposals, checks preconditions, performs compensatable
  operations, and returns result events.
- **Sovereignty:** minimal Project entities ship in V0.1 before LawFirm OS reaches
  delivery, because governance identity must precede transfer.

## Executed verification

- `python -m pytest -q --durations=20` — **1,171 passed** in 616.2 seconds before
  the final accepted-assertion schema hardening.
- Final affected-surface replay after that hardening — **89 passed** across
  event/schema and workstream/integration suites.
- Portfolio event invariant suite — 14 passed.
- Portfolio attention invariant suite — 8 passed.
- Cross-module Portfolio OS invariant suite — 5 passed.
- Existing Portfolio workstream suite — 40 passed.
- Schema/navigation/Portfolio V1 focused suites — passed.
- 48 concurrent same-stream feedback commands — 48 persisted, zero exceptions,
  zero broken predecessors, zero invalid hashes, zero diagnostics.
- Ruff on changed Python/test surfaces — clean.
- Registered JSON files parse; repository validation, roadmap, and final
  `git diff --check` are postflight gates.

The full-suite profile was I/O/subprocess dominated. Its slowest existing tests
were transport readiness and journal workflows; no Rust migration or new test
dependency was justified. Focused changed-surface suites remain the iteration
loop, while the serial full suite remains release authority.

## Remaining gates and risks

1. JSONL plus fsync cannot prove power-loss all-or-none semantics for a multi-row
   batch. Write-all, explicit request IDs, and tail repair bound recovery; use a
   WAL/SQLite projection only if fault injection or measured scale justifies it.
2. The lock is robust for concurrent processes on one host, not a distributed
   lock for two machines editing a OneDrive-synchronized data root. DAD's approved
   data root should remain outside OneDrive.
3. Relationship thresholds and dismissal threshold three need a real usage-week
   trace before promotion from pilot policy.
4. Trigger-signature format changed; no live legacy workstream ledger has been
   migrated in this pass.
5. The P2 mutation executor and activation rung two remain human-gated and are
   not implementation-complete.

Kill criteria remain: any demonstrated acknowledged loss, privacy bypass, chain
fork, silent expired work, unauthorized dependency influence, or Today-cap
starvation stops feature expansion and reopens the kernel.
