# Phase 4 — Claude Implementation Handoff (for Codex return review)

> Codex return review and remediation are complete. See
> `04_CODEX_RETURN_IMPLEMENTATION.md` for the independently reproduced defects,
> implemented repairs, final architecture adjudication, and current validation.

Session: Claude Opus 4.8 collaboration pass, 2026-07-12. Worktree
`_codex_worktrees/dad-portfolio-os-kernel-opus`, branch
`codex/portfolio-os-kernel-opus`. **Nothing committed** — the diff is left in
the working tree for Codex to independently test, challenge, and merge or
reject. DAD preflight `dad:session:4791e8b5-2c83-43ac-ba0c-aa39dfdc9110`.

## Files changed

| Path | Change |
|---|---|
| `docs/frontier/collaboration/00_CLAUDE_INDEPENDENT_AUDIT.md` | new — executed audit, findings C1–C17 |
| `docs/frontier/collaboration/01_CLAUDE_RESPONSE_TO_CODEX.md` | new — 13 ACCEPT / 2 SYNTHESIZE / 1 ACCEPT+DEFER / 0 DISPUTE |
| `docs/frontier/collaboration/02_SHARED_ARCHITECTURE_SYNTHESIS.md` | new — models A/B/C, mechanisms M1–M8, sovereignty state machine, V0 boundary, kill criteria |
| `docs/frontier/collaboration/03_CLAUDE_IMPLEMENTATION_HANDOFF.md` | new — this file |
| `src/digital_asset_directory/portfolio_events.py` | new — envelope, minimization walker, chain identity (M1), head-retry day-bucket dedup, lockfile, torn-tail quarantine, transactional append |
| `src/digital_asset_directory/portfolio_relations.py` | new — relation classification with C8/C9/C10/C13 fixes, coverage notes (M5) |
| `src/digital_asset_directory/portfolio_attention.py` | new — lifecycle state machine (C6/C7), AttentionPolicy (C14), trigger signatures (M3), decision convergence (M2), dependency rollup + board (M7), sprawl clusters (M6) |
| `src/digital_asset_directory/portfolio_workstreams.py` | rewritten — command surface (capture/capsule/feedback/bind/state/refresh M8), fold assembly, HTML board |
| `src/digital_asset_directory/cli.py` | modified — imports + six `os` verbs: capture, capsule, feedback, bind, workstreams, refresh |
| `schemas/portfolio-workstream-event.schema.json` | new — strict envelope with per-kind payload subschemas; sovereignty kind reserved |
| `schemas/portfolio-workstream-state.schema.json` | rewritten — matches the new fold output, strict |
| `registry/schema-registry.json` | modified — two new rows |
| `tests/test_portfolio_workstreams.py` | new — 40 tests |

Opus stream logs (`opus-4.8-*.json*`) untouched; consulted zero times.

## Exact commands and results

```
PYTHONPATH=src python -m pytest tests/test_portfolio_workstreams.py -q   → 40 passed
PYTHONPATH=src python -m pytest tests/test_portfolio_os.py tests/test_schema_conformance.py -q → 38 passed
PYTHONPATH=src python -m pytest tests/test_ai_navigation.py -q           → 13 passed
python -m ruff check src/...{4 modules} src/digital_asset_directory/cli.py tests/test_portfolio_workstreams.py → All checks passed
PYTHONPATH=src python -m digital_asset_directory.cli validate --hub .    → errors: [], warnings: []
PYTHONPATH=src python -m digital_asset_directory.cli roadmap check --no-update --hub . → exit=0
git diff --check                                                          → clean
PYTHONPATH=src python -m digital_asset_directory.cli os --help            → six new verbs registered
```

Tests **not** run: full `python -m pytest` (repo-wide; the V1 evidence file
records it exceeding the command budget — same posture kept here: focused
changed-surface suites plus conformance/navigation are the completed
evidence); no live-portfolio scan; no browser QA of the HTML board.

## Codex findings disposition (detail in 01)

Accepted: #1,2,3,5,6,8,10,11,12(sharpened: terminal transitions were fully
dead),13,14,15,16 and the gap half of #9. Synthesized: #4 (chain identity +
same-day head-retry guard instead of dropping timestamps), #7
(dismissal-to-decision convergence instead of silent suppression). Deferred:
the mutation half of #9 (atomic branch/worktree/task creation stays out of
the kernel). Disputed: none.

## Synthesis decisions implemented

M1 chain identity; M2 convergence (threshold 3 → `decision_proposed`);
M3 trigger signatures with cooldown, interrupts immune; M4 class accept-rate
decay retained; M5 coverage honesty (`coverage` + `ledger_diagnostics` in
state); M6 sprawl clusters (family-linked + untended); M7 depends_on/blocks
rollup, bottlenecks, board columns, downstream suppression ("waiting on
upstream"); M8 `os refresh` with `today_changed`. Sovereignty state machine:
enum + `sovereignty_recorded` event kind reserved in schema and module;
no V0 producer (per boundary).

## Assumptions

1. Ledger order is fold order (single machine, lock-serialized appends);
   cross-process clock skew therefore cannot reorder a stream.
2. A repeat of an identical command on a later UTC day is new intent (the
   day-bucket retry guard); identity itself stays wall-clock-free.
3. The V1 report join at capture time is sufficient V1 coupling for V0;
   refresh does not re-run the Git scan.
4. Legacy data-root resolution in tests (tmp hub) matches production
   behavior of `data_path`.

## Unknowns / remaining risks

1. **Lockfile robustness on OneDrive**: O_CREAT|O_EXCL + stale takeover is
   coarse; OneDrive sync could resurrect a deleted lockfile. Not observed in
   tests; needs a hostile test on a synced path.
2. **Single-buffer append atomicity on Windows** is an empirical claim for
   large batches; torn-tail quarantine bounds the damage but a >4KB capture
   batch crash test would strengthen it.
3. Relation thresholds (0.18/0.30/0.35/0.55/0.72) remain uncalibrated policy;
   M4 stats are the calibration loop but have no real data yet.
4. `related_active_idle` requires ledger adjacency; ideas related only to V1
   *projects* never produce that nudge (only capture-time advice). Possibly a
   gap worth a V1-side join at fold time.
5. Fold is O(events) per command; fine at personal scale, kill criterion (2s
   at 10k events) untested.

## Reusable lessons

1. **Retry-vs-repeat is the real idempotency problem**: pure content identity
   dedupes too much (capsule last_check), timestamped identity too little;
   chain identity + a same-day head guard covers both. Worth extracting as a
   DAD pattern for any human-feedback event log.
2. **Attention responses must not count as activity** — dismissals resetting
   the idle clock silently re-armed timers; found only by executing the
   cooldown test.
3. A torn JSONL tail makes the *next* append lie about success; every
   append-only JSONL store in DAD should adopt repair-before-append.

## Questions for Codex's return review

1. Does the day-bucket retry guard (M1 addendum) survive your adversarial
   testing, or do you find a case where it swallows a real command?
2. Is `decision_proposed` at threshold 3 too eager in real use? Counter-
   proposal welcome with a usage-week trace.
3. Should `related_active_idle` join live V1 report data at fold time (risk:
   fold stops being a pure function of the ledger)? My position: keep the
   fold pure; pass the report as an explicit fold input if needed.
4. The mutation executor boundary (deferred #9): do you accept "never in the
   kernel, separate gated executor consuming proposals," or contest?
5. Sovereignty plane: the enum/event kind is reserved — do you want project
   entities in V0.1, or after the first real child-project delivery?

## Lanes and postflight

Review lanes run as inline checklists (no subagents spawned; none were
needed for writes this bounded — recorded honestly per the mission's "record
what was actually used"). Red-team/premortem evidence: the audit itself plus
kill criteria in 02 §6. DAD postflight recorded against session
`dad:session:4791e8b5-2c83-43ac-ba0c-aa39dfdc9110` with `--hub .` in this
worktree.
