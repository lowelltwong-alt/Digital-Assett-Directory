# Portfolio Recovery Decision Control

Status: implemented control-plane contract; recovery execution and recurring
activation remain disabled.

Date: 2026-07-13

Authority: this record defines durable human decisions, transient manual-action
receipts, and verified result evidence. It does not approve a preservation
commit, worktree removal, push, merge, branch deletion, raw-artifact action,
automation, or native Git executor.

## Decision

Portfolio recovery uses a third strict event-envelope family in the existing
single Portfolio ledger:

`dad.portfolio_shaping_decision_event.v1`

It is separate from workstream lifecycle events and execution-control events.
The supported event kinds are:

- `shaping_decision_recorded`;
- `shaping_decision_retracted`;
- `manual_recovery_result_recorded`.

The event family can record what a named human decided about one exact shaping
case and what an independently checked manual operation later proved. It cannot
change workstream lifecycle, accept resource bindings, create workstreams,
dispatch an agent, or authorize Git.

## Exact decision binding

A recorded decision binds all of the following:

- stable decision, case, and case-revision identities;
- the shaping source-snapshot digest;
- the expected-preconditions digest;
- one canonical choice identity and choice kind from that exact case revision;
- a categorical disposition and optional review date;
- approver and approval reference;
- optional superseded decision identity;
- an explicit request identity for retry idempotency.

Before append, the writer rebuilds the current shaping projection and rejects a
missing or stale case, revision, source snapshot, precondition set, or choice.
Source timestamps are evaluated against the actual observation time with a
26-hour maximum age and one-hour future-skew bound; a stored `current` label is
never sufficient. The rebuild reconstructs the frozen source projections at
their original observation time for exact hash coupling, then evaluates shaping
freshness at the current time. An identical retry returns the existing event
before current-state staleness or packet-expiry checks. Reusing a request
identity for different content fails closed. Retraction is an inverse event;
history is not rewritten.

## Manual recovery receipt

`asset-dir os recovery-packet` returns a transient, non-authorizing JSON receipt.
It binds stable resource identities, exact source and precondition digests, a
categorical action, expiry, and a human gate. It deliberately excludes absolute
paths, filenames, private prose, raw labels, shell commands, and executable
controls. Its deterministic packet identity binds every other receipt field,
including issue/expiry times, approval reference, precondition codes, and all
deny-all flags. A regex-valid substituted identity is rejected. Every receipt
states `execution_authorized=false`.

Approval happens outside DAD against the exact receipt. A supervised worker may
then resolve paths in local transient context and perform only the separately
approved action. A different checker verifies deterministic hashes, status, and
test evidence. Only the privacy-safe outcome is appended afterward. Worker and
checker identity equality is rejected.

This separation is load-bearing:

```text
shaping evidence
  -> durable human decision
  -> transient non-authorizing receipt
  -> separately approved manual worker
  -> independent checker
  -> durable privacy-safe result
```

## Projection behavior

Shaping and daily review writers emit v2. Shaping v2 exposes only categorical
active, retracted, stale, pending, failed, aborted, or verified decision state.
Review v2 maps:

- approved but unperformed work to `waiting`;
- failed verification to `failed`;
- future-dated deferral to `intentionally_quiet`;
- verified results to `completed`;
- stale source or precondition snapshots to `blocked`.

The review reuses the single cockpit Today list and remains capped at three.
Legacy v1 generated cursors are migration input only: a read-only review reports
`upgrade_required`, while `os refresh` performs a source-derived v2 rebuild.
Cockpit and reconciliation retain their v1 semantics.

## Privacy and presentation

Generated JSON and HTML contain no absolute paths, raw worktree labels, private
prose, commands, forms, buttons, or authority language. HTML is static,
script-free, and non-executing. Categorical evidence references are permitted
only after minimization and schema validation.

## Rollout gate

No schedule is enabled by this slice. At least five supervised reviews spanning
at least seven days must first prove deterministic validation, source zero-write,
bounded Today output, material-only change detection, silent unchanged healthy
runs, useful/noisy row labels, single-instance locking, publication rollback,
and fail-closed OneDrive lock/interrupted-write recovery.

After that evidence, activation still requires a final explicit human approval.
The allowed automation runs only `os refresh`, never executes recovery, dedupes
failure fingerprints, emits no more than one notice per day, and shows at most
three asks. Rollback disables the automation and deletes only regenerated review
cursors; append-only decisions are corrected through retraction events.

## Kill criteria

Disable the slice and preserve evidence if any of the following occurs:

- a decision can target a stale or noncanonical shaping choice;
- an event changes lifecycle, binding, dependency, dispatch, or Git state;
- a receipt contains a path, filename, command, private prose, or execution flag;
- one identity can act as both worker and checker;
- a corrupt or torn ledger remains writable;
- a v1 cursor is silently treated as authoritative v2 state;
- Today exceeds three or a second recovery queue appears;
- unchanged input generates repeated attention;
- publication failure consumes the authoritative cursor;
- recovery, removal, raw-artifact handling, or automation occurs without its
  own exact approval.

Recovery writes never invoke generic torn-tail repair. Any torn tail, corrupt
row, invalid envelope, or chain problem blocks both new writes and retries
without truncating the ledger, writing quarantine, or appending an event.

## Deferred work

The native executor remains outside DAD pending a separate threat model,
anchored approval verification, cryptographic packet binding, concurrency and
rollback controls, and human authorization. Daemon remediation and the journal
backlog are also a separate workstream and are not evidence that worktree
recovery is complete.
