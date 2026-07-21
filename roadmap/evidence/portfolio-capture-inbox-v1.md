# Portfolio Capture Inbox V1 Evidence

Status: candidate implementation evidence, 2026-07-20.

## Delivered

- `asset-dir os capture --raw` provides the zero-friction one-line alias over
  the existing event-sourced, human-decision workstream capture kernel.
  It retains that existing command's proposal semantics; it does not execute or
  activate a workstream. The separately governed `capture-inbox` path below is
  candidate-only and never creates workstream events.
- `asset-dir os capture-inbox --inbox <explicit-path>` reads one explicitly
  supplied UTF-8 file under global byte, line, and line-length budgets.
- A provider-neutral core minimizes and deduplicates lines without filesystem,
  scheduler, model, workstream, or execution authority.
- The local-file adapter preserves the source byte-for-byte and appends only
  schema-validated DAD-local candidate records. Replays are idempotent.
- The operational cockpit consumes a strict sanitized report with counts,
  freshness, source fingerprint, redaction count, and categorical coverage. It
  never receives the captured text or source filesystem path.
- The foreman contract is registered disabled with a 26-hour freshness target;
  registration does not schedule or activate it.

## Hard budgets and failure posture

- Default input: 512,000 bytes, 500 lines, 2,000 characters per line.
- Maximum configured input: 8,000,000 bytes, 10,000 lines, 20,000 characters.
- Candidate ledger: 16,000,000 bytes and 20,000 records.
- Oversized, invalid UTF-8, overlong, excess-line, malformed-ledger, torn-tail,
  schema, and identity-conflict conditions fail closed. Partial intent is not
  emitted as a candidate.
- The input file is never created, cleared, acknowledged, truncated, renamed,
  deleted, or written.
- An input that resolves to, links to, or is the same file as the DAD capture
  report or candidate ledger is rejected before processing.

## What this evidence does not prove

- It does not prove a 26-hour cadence is useful or authorize a schedule.
- It does not prove a candidate is novel, valuable, or a separate workstream.
- It does not call a model or prove `dad-work-router` classification quality.
- It does not create `~/.dad/inbox.md`, install a hook, activate a daemon, send a
  notification, mutate another repository, or perform cross-repository rollout.

## Activation gates

Lowell approval remains required before creating a global drop file, enabling
or scheduling the routine, adding a persistent watcher, acknowledging or
clearing source lines, routing captured content to a model, auto-creating a
workstream, or deploying any wrapper to another repository.

## Validation target

Focused acceptance covers core boundedness, source digest equality before and
after, redaction, idempotent append, partial-report behavior, missing input,
strict schemas, raw CLI compatibility, cockpit source health, no capture text in
HTML, routine registry validity, portability evidence, and repository validation.
