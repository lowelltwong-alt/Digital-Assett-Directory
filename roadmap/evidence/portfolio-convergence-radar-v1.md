# Portfolio Convergence Radar V1

## Outcome

DAD now has a deterministic, report-only convergence radar for local Git
branches and checked-out worktrees. It consumes a schema-valid Portfolio
Attention snapshot, collects bounded read-only Git evidence, writes
`processed/reports/portfolio_os/convergence-radar.json`, and exposes a
sanitized top-five view in the operational cockpit.

The v1 evidence signals are:

- normalized branch-name token Jaccard similarity;
- touched-path Jaccard similarity, including bounded dirty-worktree paths when
  a checked-out branch is dirty;
- the commit distance from the shared merge base to both branch tips.

The priority score is an ordinal review queue, not a probability and not proof
that two branches share intent. Raw touched paths remain in the local-private
source report but are intentionally omitted from the operational HTML.

## Boundaries

- zero model calls and zero model tokens;
- `GIT_OPTIONAL_LOCKS=0` for every Git observation command;
- global project, command, wall-time, per-command-byte, and total-byte budgets;
- per-project branch, candidate-distance, path, timeout, and top-five budgets;
- categorical unknowns and truncation records instead of false all-clear;
- no merge, close, branch deletion, worktree removal, cleanup, dispatch,
  daemon activation, scheduling, or source-repository write;
- every suggested disposition remains an explicit human decision.

The foreman entry is `cli_on_demand` with no freshness cadence. Registration
does not activate or schedule the radar.

## Portability split

`portfolio_convergence.py` is the provider-neutral pure projection. It accepts
bounded branch evidence and returns deterministic candidate records without
Git, filesystem, network, model, or write effects.

The core schema accepts a generic bounded producer receipt and is independently
tested without importing the CLI or Git adapter. The Git-only producer receipt
has its own strict schema and exact runtime-adapter revision.

`portfolio_convergence_git.py` is the explicit read-only Git runtime adapter.
It preserves the core input, output, error, privacy, effect, and authority
contracts and records the exact adapter revision in every report.

The operational cockpit remains a separate portable knowledge interface. It
consumes only the precomputed, schema-valid convergence report and never scans
Git on a page request or foreground refresh.

## Risk review and premortem

This increment is medium risk rather than high risk: it changes a shared local
schema and cockpit consumer, but remains report-only, local, reversible,
candidate-only, and unable to execute or mutate scanned repositories. The
fresh-eyes review rejected two initial choices: a Git-bound core schema and
post-buffer path truncation. The repair separates a generic producer contract
from the exact Git receipt and bounds projects, commands, wall time, per-command
bytes, and total bytes before evidence is accepted.

Premortem failure modes are false convergence confidence, runaway observation,
raw-path leakage, and accidental Git effects. Kill criteria are any source ref
or status mutation, missing truncation/unknown evidence, schema acceptance of an
unbounded Git receipt, or raw touched paths in cockpit HTML. Rollback is a
single-revision revert that leaves prior portfolio attention and cockpit inputs
intact.

## Validation evidence

The focused exact-worktree suite passed on 2026-07-19:

~~~text
python -m pytest tests/test_portfolio_convergence_core.py tests/test_portfolio_convergence.py tests/test_operational_cockpit.py tests/test_routine_health.py -q
44 passed in 113.3s
~~~

The suite includes real temporary Git branches, before/after ref and worktree
status equality, all three evidence signals, deterministic ordering, top-five
bounds, unknown-distance behavior, invalid-source failure, CLI behavior,
strict report and cockpit schemas, script-free HTML privacy, transactional
cockpit publication, foreground host behavior, and routine registry validation.

Ruff also passed on every changed Python source and focused test file.

## Remaining risks

- Name and path similarity can still produce false positives; v1 therefore
  ranks review candidates and never confirms same intent.
- Very large repositories are deliberately truncated by explicit budgets; the
  report records coverage problems instead of claiming completeness.
- The on-demand radar can be absent or stale. The six-source cockpit remains
  `partial_candidate` until a current report exists.
- No daemon, scheduler, persistent host, cross-repo write, cleanup executor, or
  automatic closure crew is activated by this increment.
