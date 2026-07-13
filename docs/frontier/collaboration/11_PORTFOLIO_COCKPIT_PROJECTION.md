# Portfolio Cockpit Projection Decision

Status: implementation decision for the first unified DAD Portfolio OS cockpit.
Risk tier: high. This adds a shared projection contract and a cross-source attention
ordering that future agents and the primary user interface may rely on.

## Decision

Add one pure, read-only projection bridge between the existing Git/worktree
observation report and the existing Model C workstream fold:

```text
configured local roots
  -> dad.portfolio_attention.v1
  -> dad.portfolio_workstreams.v1
  -> dad.portfolio_cockpit.v1
  -> local JSON + script-free HTML under DAD_DATA_ROOT
```

The bridge does not scan repositories, append events, create identities, accept
bindings, promote dependencies, launch agents, or mutate Git. It preserves both
input reports as independently valid source projections.

## Options considered

1. Extend one existing HTML renderer to consume the other report. Rejected:
   this would hide the join inside presentation code and provide no strict,
   independently testable composite contract.
2. Add a pure JSON/HTML cockpit projection. Chosen: it is reversible, keeps I/O
   at the edges, and gives the global Today cap and unknown-state handling a
   deterministic contract.
3. Wait for missions, Tier-0 federation, adaptive weights, and a local server.
   Rejected for this phase: it leaves the two current dashboards fragmented and
   delays the daily organization surface.

## Source and identity boundaries

- An observed Git repository is not a registered DAD child project.
- A generated relation is not a resource binding.
- A resource binding is not a dependency.
- A proposed assertion is not an accepted assertion.
- Unassigned observed work is an attention candidate, not an automatically
  created workstream.
- Exact accepted resource bindings are the only evidence that may join Git and
  workstream attention items.

The projection assigns deterministic local resource IDs:

- repository: the existing `dad:portfolio-project:*` observation ID;
- branch: `stable_id("portfolio-branch", project_id, branch_name)`;
- worktree: `stable_id("portfolio-worktree", project_id, normalized_local_path)`.

Legacy name/path bindings remain unresolved. The cockpit never guesses them into
an accepted match.

## Today selection methodology

Methodology version: `dad.portfolio-cockpit-selection.v1`.

The two source priority numbers are not treated as one calibrated score. Every
candidate is first placed in one explicit ordinal band:

1. `human_decision`
2. `integrity_unknown`
3. `dirty_recovery`
4. `dependency_unlock`
5. `related_active_neglect`
6. `weekly_maintenance`

Within a band, candidates sort by:

1. highest source-local priority;
2. highest accepted downstream blocking count;
3. greatest inactive-day observation;
4. stable attention ID ascending.

The first three non-quiet candidates become Today. The full queue remains
visible. Paused, snoozed, and not-yet-due incubating work cannot enter Today.
Dependency cycles appear as unknown/human-review items and never as an unlock
frontier. Missing or invalid inputs can never produce an `all_clear` result.

This methodology applies only to cockpit display order. It does not rank asset
value, graph truth, project worth, people, models, or execution authority.
Applying it outside this UI would turn weak attention evidence into false
importance evidence.

## Blast radius

- new Python public projection module;
- new strict JSON schema and schema-registry row;
- one new `asset-dir os cockpit` command;
- `asset-dir os refresh` gains cockpit output after its existing two source
  projections are written;
- navigation manifest, AI table of contents, navigation registry, and focused
  regression tests.

No source repository, enrollment contract, daemon schedule, notification path,
agent dispatcher, or execution authority changes.

## Self red-team and premortem

- False green when one source is missing: source descriptors and unknowns are
  mandatory; `all_clear` requires both valid, current sources.
- Numeric priority soup: ordinal bands precede source-local priority and the
  report names the methodology.
- Quiet work becomes nagging: quiet lifecycle states are a separate collapsed
  lane and have a regression test.
- Similarity becomes identity: related work remains candidate-only and cannot
  populate accepted bindings.
- Dirty status failure becomes clean: `dirty=null` becomes an
  `integrity_unknown` item.
- Dependency centrality becomes a schedule claim: the UI says `unlock frontier`,
  never `critical path`.
- Malicious local metadata becomes executable HTML: all values are escaped,
  the Phase-A page has no scripts/forms/external resources, and a hash-bound CSP
  permits only the fixed inline stylesheet.
- The cockpit becomes an executor: it contains no action controls or mutation
  endpoints.

## Validation and kill criteria

Required evidence:

- strict schema conformance;
- global Today count of at most three and deterministic ordering;
- accepted-exact binding dedupe, with proposed/legacy bindings remaining
  unresolved;
- missing, invalid, stale, and unknown inputs remain visible;
- only accepted dependencies affect the unlock frontier;
- HTML escaping, CSP hash, accessibility landmarks, and absence of executable
  controls or external URLs;
- identical source-repository Git fingerprints before and after an authorized
  real-root dry run;
- focused Portfolio regression tests, navigation tests, Ruff, repository
  validation, roadmap check, and diff check.

Disable the projection if it mutates a source repository, traverses outside a
configured root, exposes changed filenames/diffs/private payloads, represents
unknown state as clean, guesses an ambiguous binding, auto-creates durable
state, promotes a proposed dependency, or triggers notification/dispatch.

## Independent return review

The independent red-team initially reproduced false-green and reminder-loss
paths. The accepted implementation now:

- validates both inputs against their registered strict schemas before use;
- quarantines malformed, wrong-version, non-object, future-unknown, and
  duplicate resource/workstream identities from all downstream projections;
- treats corrupt lines, invalid envelopes, torn ledger tails, fold problems,
  and ledger problems as integrity unknowns;
- prevents paused, snoozed, incubating, terminal, and priority-zero workstreams
  from re-entering Today through a Git binding;
- exposes the unified cockpit today_changed separately from the workstream-only
  change signal;
- derives worktree identity by lexical normalization without filesystem or UNC
  resolution; and
- validates cockpit output before publication.

The JSON report is the authoritative notification cursor. HTML is written first
and JSON last. If OneDrive blocks HTML publication, JSON remains unchanged and
a retry retains today_changed: true; command failure remains nonzero. Eighteen
adversarial cockpit tests cover these invariants, including the failure/retry
case.

Final independent verdict: accepted for manual read-only use and technically
acceptable for activation rung 2 only if the routine treats every nonzero exit
as failure and reads JSON as the authoritative cursor. No schedule is enabled
by this implementation; activation still requires an explicit human decision.

Rollback is deletion of the new generated cockpit files and removal of the
new command/module/schema routing. The two existing source projections remain unchanged.
