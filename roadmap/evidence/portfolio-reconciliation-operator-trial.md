# Portfolio Reconciliation Operator Trial

Date: 2026-07-13
Status: supervised local evidence; proposal-only activation
Method: `dad.portfolio-reconciliation-selection.v1`

## Question

Can DAD turn a real, sprawling Git portfolio plus a minimal workstream ledger into
bounded identity-assistance evidence without changing Git, accepting an identity,
or creating a second daily queue?

## Trial boundary

The trial used the current local portfolio. It captured one minimized DAD
workstream and one exact DAD repository binding with assertion status `proposed`.
No binding was accepted. The final supervised command was the default scan path:

```text
asset-dir os reconcile
```

The command refreshed four kinds of derived local output: Git attention,
workstream state folded from the existing ledger, the strict cockpit, and strict
reconciliation JSON/HTML. It did not append the ledger, modify Git, schedule a
routine, dispatch an agent, or expose a mutation control in HTML. Every scanner
Git subprocess ran with `GIT_OPTIONAL_LOCKS=0` so read-only status collection
could not opportunistically refresh an index.

## Observed portfolio

| Measure | Count |
| --- | ---: |
| Projects | 31 |
| Branches | 230 |
| Worktrees | 141 |
| Attention items | 192 |
| Cockpit Today items | 3 |
| Cockpit unknowns | 4 |
| Captured workstreams | 1 |

The first renderer exposed 325 resource-level unassigned rows. Grouping the
most-specific branch/worktree identity scope already attached to each attention
item reduced that to 188 stable recovery bundles. Broad repo bindings remain
project context and do not populate every branch/worktree bundle. This
325-to-188 delta is local usability evidence, not a universal performance claim.
The 188 bundles remain a collapsed inventory, explicitly not a second Today
queue.

## Reconciliation result

| Measure | Result |
| --- | ---: |
| Visible candidates | 3 |
| Hidden candidates | 0 |
| Existing exact proposals for review | 1 |
| Inspect-only lexical relations | 2 |
| Proposal-ready structural candidates | 0 |
| Hidden exact structural candidates | 0 |
| Persisted proposal commands | 0 |
| Review queue | 1, attached to an existing Today item |
| Reconciliation blockers | 0 |
| Unknown evidence rows | 4 |
| Blocking evidence total | 4 |
| `fully_reconciled` | `false` |

The existing exact proposed binding emitted no command. The lexical relations
emitted no commands. Unknown evidence remained visible and prevented a false
green. The HTML now exposes hidden-candidate counts and per-workstream coverage;
the full recovery inventory remains collapsed by default. The only bounded
review item was already in the cockpit's three-item Today set.

The regenerated reconciliation JSON passed its registered strict schema with
zero errors and its cross-field semantic validator with zero problems. Its
source hash exactly matched the regenerated cockpit.

## Zero-write and privacy evidence

A same-command before/after fingerprint exercised the default Git scan and
separated its complete observed scope into:

- 31 common Git project surfaces: logical refs, remotes, common config,
  packed refs, and lock presence;
- 141 linked worktree surfaces: porcelain status, index bytes and modification
  time, worktree HEAD, and lock presence;
- the exact append-only workstream ledger, including bytes and modification time;
- four pre-existing discovery errors, stored and compared only as opaque hashes.

Results:

- project surface sets unchanged: `true`
- changed project surfaces: `0`
- worktree surface sets unchanged: `true`
- changed worktree surfaces: `0`
- discovery-error fingerprints unchanged: `true`
- ledger bytes and modification time unchanged: `true`
- absolute Windows/UNC/user-path matches in reconciliation JSON: `0`
- absolute Windows/UNC/user-path matches in reconciliation HTML: `0`

The aggregate proof is retained locally at
`.tmp/reconciliation-zero-write-proof-current.json`. It contains hashes and
counts, not raw source paths, Git output, remotes, or error text. Runtime `.tmp`
evidence is supporting evidence; this document is the durable,
privacy-minimized record.

Two consecutive supervised default scans completed successfully on the current
OneDrive-backed portfolio. This is evidence for normal repeated operation, not
for crash recovery or concurrent lock contention.

## Validation

The final focused command is:

```text
python -m pytest tests/test_portfolio_os.py tests/test_portfolio_workstreams.py tests/test_portfolio_cockpit.py tests/test_portfolio_reconciliation.py tests/test_ai_navigation.py -q -p no:cacheprovider
python -m ruff check src/digital_asset_directory/portfolio_os.py src/digital_asset_directory/portfolio_reconciliation.py src/digital_asset_directory/cli.py tests/test_portfolio_os.py tests/test_portfolio_workstreams.py tests/test_portfolio_cockpit.py tests/test_portfolio_reconciliation.py tests/test_ai_navigation.py
```

The focused suite passed 136 tests. Ruff reported `All checks passed!`.
Runtime schema and semantic validation of the regenerated reconciliation report
also passed with zero findings. `asset-dir roadmap check --no-update` exited 0 and
`git diff --check` found no whitespace errors.

The repository-wide `asset-dir validate` check did not pass: it checked 850
records and reported stale exception-capture, event-pipeline, and graph-surface
reports already present in the dirty worktree. Those unrelated derived pipelines
were not regenerated in this slice. This failure is not cited as a reconciliation
pass; the registered reconciliation schema and semantic gates were run directly.

A monolithic test attempt is not cited as a result. Its ten-minute wrapper was
shorter than the evidence-backed 11.3-to-12.5-minute expected suite duration and
left a CPU-active Windows descendant. The exact processes were terminated and
confirmed gone. A later full authority run needs a tree-aware 15-minute cap.

## Subagent evaluation and reuse

Six privacy-safe, parent-observational attempt evaluations were ingested for the
identity architect, initial conformance reviewer, final red team, acceptance
gate, lesson/asset scout, and optimization director. The attempt-first capability
graph rebuilt to 23 attempts, 23 evaluations, and 14 role revisions. The declared
role directory rebuilt separately with 11 portable role contracts, and its eight
directory tests passed.

The ratings remain attempt-scoped candidate evidence. They do not count toward
profile eligibility, rank models, or change routing. Exact child-to-score identity
was unavailable for three nested optimization subreviews, so DAD retained the
reported scores in the evidence note but did not fabricate separate graph joins.
The privacy-safe evaluation source is
`roadmap/evidence/portfolio-reconciliation-subagent-evaluations.json`.

## Confirmed findings

- Proposal-only reconciliation can recover one exact existing intent without
  accepting it or fabricating a workstream.
- Most-specific branch/worktree bundle grouping materially reduces presentation
  fragmentation without letting one repo association masquerade as branch
  identity.
- Unknown evidence and unresolved ownership must be first-class counters; zero
  blockers alone is not an all-clear signal.
- Persisted proposal commands can be restricted to the existing bounded Today
  review set; off-queue exact evidence remains non-command-bearing
  `proposal_available` evidence.
- JSON Schema shape is insufficient for this contract. Stable card revisions and
  a cross-field semantic validator are required to detect internally coherent-
  looking tampering.
- Read-only Git scanning needs optional-lock suppression plus byte-and-time
  evidence over indexes; status-text equality alone is too weak.

## Inferred findings

- Repeated labeled trials may justify updating the existing trigger-pattern and
  daily-portfolio-pulse assets; one workstream does not justify promotion.
- Static local projections may benefit from a shared safety harness for CSP,
  escaping, accessibility, strict-schema validation, semantic integrity,
  bounded actionability, and publication ordering. This is a candidate
  mechanism, not a promoted asset.

## Assumptions and unknowns

- One workstream is insufficient to estimate proposal precision or recall.
- The 188-bundle inventory still needs later filtering or pagination if operators
  find the collapsed evidence expensive to inspect.
- Candidate-only split, rescope, recovery, and duplicate-workstream choices are
  not implemented in this slice.
- Four source unknowns remain; the report correctly stays not fully reconciled.
- Two normal OneDrive scans passed, but crash atomicity and active lock contention
  remain untested.
- Stable hashes provide local integrity detection, not authenticity or a digital
  signature.

## Activation decision

Keep reconciliation supervised and proposal-only. Do not create the daily
routine yet. Collect explicit labels for false positives, missed joins,
ambiguity, review usefulness, and inventory burden across repeated sessions
before changing triggers or scheduling.
