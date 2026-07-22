# Lifecycle Janitor

## Why this exists

DAD accumulates state in several places and puts a **governance gate** in front
of each — but historically shipped the gate without the **janitor** that keeps
the resource clean. That pairing (a gate demanding a clean resource + a system
that dirties it automatically and only cleans it manually) deadlocks by design:

| Accumulating resource | The gate | The missing janitor (now provided) |
|---|---|---|
| Per-scan catalog rows (edges/alerts/chunks) | scoring / validate | retention prune to latest complete scan + VACUUM |
| Open agent session records | pre-push "zero open sessions" | honest `abandoned_reaped` close of idle sessions |
| Git worktrees | — | `git worktree prune` (admin metadata for deleted dirs) |

The concrete failure that motivated this: a push was blocked because **15
orphaned agent sessions** had no postflight, and the session reaper is
dry-run-only (apply is human-gated and never runs), so they never cleared.

**The governing principle** (also recorded in `registry/design-authority.json`):

> Never add a gate that requires a clean resource without also shipping the
> reaper + retention that keeps it clean.

This is not novel research. It is standard resource-lifecycle management:
leases + TTL + owner references (Kubernetes GC), heartbeat-based reaping (SRE),
ephemeral-by-default worktrees, scheduled janitors (Janitor Monkey), and
log-structured compaction. DAD was over-gated and under-janitored; this closes
the gap.

## What it does

`digital_asset_directory.lifecycle_janitor` plans (and, per config, applies)
three deterministic sweeps:

1. **Agent sessions** — consumes the `agent_session_reaper` classification
   (tiering, mtime-based liveness, exception/keep skips) and closes sessions
   that are idle past a margin **above** the reaper's dry-run threshold. Reaped
   sessions get `status: abandoned_reaped` with a reason and timestamp — an
   honest "not completed" record, never a fabricated postflight (which would
   falsely claim the session's learning review lanes ran).
2. **Git worktrees** — `git worktree prune`, which removes administrative
   metadata **only** for worktrees whose directory is already gone. Present
   worktrees are reported, never force-removed.
3. **Catalog** — prunes superseded per-scan rows to the latest **complete**
   scan and VACUUMs, preserving lessons/handoffs.

## Safety invariants

- Deterministic; zero model calls.
- **Dry-run by default.** Session apply is opt-in (F2/G5), configured in
  `config/janitor.yaml`.
- Never mutates scanned source repositories.
- Never destroys work: worktree pruning is admin-only; session closing does not
  touch the session's branch/worktree; catalog retention preserves lessons and
  handoffs and keys on the latest *complete* scan.
- Conservative liveness: sessions are only auto-closed when idle past
  `session_reap.idle_hours` (default 24h) and never when leased/parked/held or
  on the keep list.

## Usage

```powershell
$env:PYTHONPATH = 'src'
# Dry-run plan (what would be cleaned):
python -m digital_asset_directory.cli janitor --hub .
# Apply the config-authorized sweeps:
python -m digital_asset_directory.cli janitor --apply --hub .
```

The daemon runs the janitor in **dry-run** on every active cycle for visibility
(surfaced in the heartbeat as `lifecycle_janitor_*`), and forces a refresh at
least hourly even when the cycle would otherwise be idle — because a session
crossing the idle threshold is a time-based transition that does not change the
cycle input fingerprint. To automate *cleanup*, schedule `janitor --apply` on the
DAD scheduler; enable session reaping by setting `session_reap.apply: true` **and
a nonempty `approval_ref`** (a named human approval — the flag alone is not the
gate) in `config/janitor.yaml`.

## Configuration

See `config/janitor.yaml`. Catalog retention and worktree prune apply by
default (they are safe); session reaping is opt-in.

## Follow-ups

- Bounded auto-apply of session reaping inside the daemon once trusted.
- Optional removal of present worktrees on merged + clean branches
  (`worktree_prune.remove_merged_clean`, runs without `--force`).
- Heartbeat/liveness for sessions so crashed agents expire without any reaper.
