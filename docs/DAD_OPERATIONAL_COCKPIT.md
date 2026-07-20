# DAD Operational Cockpit

## Outcome

The operational cockpit is the thin local envelope around DAD's existing
Portfolio Cockpit v1, Portfolio Cockpit v2, Capability OS cockpit, daemon
heartbeat, event-pipeline report, and deterministic branch/worktree convergence
radar. It does not replace any of those source projections.


```text
repo-owned enrollment contracts + metadata/event outboxes
                         |
                         v
bounded collectors -> append-only DAD events -> precomputed projections
                                                 |
                                                 v
                                  operational-cockpit.json/html
                                                 |
                                                 v
                                  foreground loopback-only host
```

The host verifies a generation receipt, JSON schema, semantic invariants, and matching JSON/HTML digests on every request. It seeds and retains the last valid bundle in memory, so a transient mismatch during rebuild serves the previous coherent generation; an invalid startup has no fallback and returns HTTP 503. It also rejects Host headers outside the exact numeric IPv4 loopback allowlist (`127.0.0.1` with the bound port when present) and never reads a single source report larger than the bounded input budget. It never scans a repository, rebuilds a source projection, appends an event, or executes an action. The operator explicitly rebuilds the operational envelope when desired.

## Commands

Inspect source readiness without publishing or overwriting outputs:

~~~text
asset-dir os operational-cockpit --check --hub <DAD checkout>
~~~

Build or refresh the convergence evidence after a Portfolio Attention scan:

~~~text
asset-dir os status --hub <DAD checkout>
asset-dir os convergence-radar --hub <DAD checkout>
~~~

The convergence command reads Git metadata through optional-lock-free commands
bounded globally by project count, command count, wall time, per-command bytes,
and total bytes, then writes only a DAD-local candidate report. Its portable
report schema accepts any bounded zero-write producer; a separate strict receipt
schema binds the current Git adapter and every observation budget. It evaluates
normalized
branch-name tokens, touched-path overlap, and merge-base distance, then exposes
at most five review candidates. Scores are ordinal review priority, not
probabilities or proof of shared intent. No model is called, and no merge,
close, branch deletion, worktree removal, cleanup, or source-repository write is
authorized. Registration in the routine foreman is on-demand only and does not
schedule or activate the scan.

Build from precomputed local reports:


~~~text
asset-dir os operational-cockpit --publish --hub <DAD checkout>
~~~

Refresh the safe same-hub producers once and then publish the envelope:

~~~text
asset-dir os cockpit-refresh-now --hub <DAD checkout>
~~~

`cockpit-refresh-now` rebuilds portfolio v1, portfolio v2, the Capability OS
cockpit, and the event-pipeline report from existing DAD-local candidate state.
It does not scan configured repository roots, collect repo event outboxes, run a
daemon cycle, activate a scheduler or host, or write any source repository. It
stops at the first failed producer and leaves the last coherent operational
envelope in place. Successfully completed source reports remain independently
valid because their canonical writers publish atomically.

The daemon source is deliberately excluded. Without a separately approved real
daemon cycle, a normal foreground refresh may honestly remain
`partial_candidate`; the command never fabricates a completed heartbeat.
The convergence source is also precomputed and is not fabricated by
`cockpit-refresh-now`. If it has never run or is stale, the cockpit remains
honestly partial until an operator runs the explicit commands above.


Serve in the foreground on loopback only:

~~~text
asset-dir os cockpit-host --hub <DAD checkout> --port 8765
~~~

The host exposes only:

- `/` and `/index.html`: escaped, script-free HTML;
- `/api/snapshot`: the authoritative generated JSON projection;
- `/healthz`: coherent last-valid-bundle availability plus the exact snapshot ID, categorical evidence status, and bounded source summary; never action authority.

All mutation methods are denied. Directory browsing, arbitrary files, external bind addresses, Host headers outside `127.0.0.1` and `127.0.0.1:<bound-port>`, external JavaScript, and action endpoints are absent. Serving coherence and evidence currency are deliberately separate: a coherent partial snapshot is safe to display but is never an all-clear.

## Repo adapter contract

No cockpit implementation is copied to a source repository. An enrolled repo's
existing `.digital-asset/dad-integration.json` is its provider-neutral adapter
contract. Optional repo-local metadata events use
`.digital-asset/events/outbox.jsonl`; normal recurring DAD writes remain limited
to `.digital-asset/mail/**`. The operational snapshot publishes these stable
pointers and treats the adapter as metadata-and-derived-health only. The host and snapshot are explicitly `local_private_metadata`: they are same-machine, same-data-class views, not public release surfaces.

Adding this capability to more repos therefore means a reviewed, opt-in DAD
enrollment or enrollment-update wave. It does not mean installing a daemon,
hook, bot, plugin, duplicated dashboard, or runtime-specific agent.

## Refresh and real-time architecture

The current design is deliberately hybrid:

1. manual/on-demand generation produces a deterministic snapshot;
2. append-only event ingestion supplies low-latency candidate evidence;
3. scheduled reconciliation repairs missed events and refreshes source truth;
4. the foreground host serves the last valid snapshot without doing work on a
   page request.

A supervised daemon may later run collection, projection, and reconciliation,
but only after explicit approval for its repository scope, privacy/data class,
cadence, resource limits, failure policy, and stop procedure. It must never gain
decision or execution authority. Remote webhook ingress is a separate higher
risk deployment and is not part of this build.

## Source health semantics

Each source is independently fingerprinted and classified as `observed`,
`stale`, `missing`, or `invalid`. Portfolio v1, portfolio v2, Capability OS, and
convergence inputs must pass their authoritative registered JSON Schemas. Daemon and event inputs must pass strict producer invariants: daemon evidence counts as current only after a complete, finalized cycle with a completion timestamp, and event counts must be nonnegative. Missing timestamps, date-only or timezone-less timestamps, other malformed timestamps, timestamps more than five minutes in the future, wrong field types, and authority-contract violations are invalid. Stale or invalid sources cannot contribute decisions, convergence candidates, or event-pulse values.

The whole cockpit is `current_candidate` only when all six sources are current;
every other condition is `partial_candidate`. Candidate status is never an
approval or source-authority transfer.

The page exposes at most three immediate decisions with bounded evidence references and a separate top-five convergence review surface that omits raw touched paths. It also shows a provenance-bound portfolio scope (projects, branches, worktrees, and workstreams), explicit attention and uncertainty counts, the event pulse, source owners and producer references, and source actions for every gap. Portfolio counts appear only when Portfolio v1 is current and schema-valid; unavailable values render as unknown, never zero or green. The script-free HTML includes a skip link, consistent section navigation, semantic headings and tables, visible focus, 44-pixel disclosure targets, reduced-motion and increased-contrast handling, and responsive one- or two-column fallbacks.

## Revision-bound contract evidence

Revision `0.3.3` binds its contract digests to these canonical materials:

- input: six named precomputed sources, including the strict convergence report,
  a maximum five-minute future-clock tolerance, explicit-offset timestamps, and
  a two-megabyte per-source read budget;
- output: `dad.operational_cockpit.v1`, a
  `dad.operational_cockpit.receipt.v1` coherence receipt,
  `local_private_metadata`, at most three immediate decisions, a separate
  sanitized top-five convergence view, provenance-bound portfolio scope and readiness actions, non-publishing readiness inspection, evidence-aware health, and an in-memory last-valid
  bundle during foreground service;
- error: invalid sources force `partial_candidate`, stale/invalid payloads
  contribute no decisions or pulse, oversized sources fail closed, invalid startup bundles with no cached last-valid bundle return HTTP 503, non-loopback Host headers return HTTP 421, and mutation methods return HTTP 405;
- privacy: loopback-only bind and an exact `127.0.0.1` / `127.0.0.1:<bound-port>` Host allowlist, local-private classification,
  bounded source reads, decision strings bounded to 240 characters, and at most
  ten 240-character evidence refs.

The contract digests are deterministic canonical JSON digests of those named
materials. Any change to those values requires a new revision and fresh
validation evidence.
## Activation gates

The following remain separately human-gated:

- Windows Task Scheduler or any recurring daemon activation;
- persistent background host activation;
- remote ingress, tunnels, webhooks, GitHub Apps, plugins, or bots;
- enrollment writes or broad all-repository rollout;
- any action executor, notification, source mutation, or private payload flow.

Recommended rollout is: local DAD proof, one or two read-only opt-in repo pilots,
failure-injection and usability evidence, then a separately approved broader
wave. Daemon activation is justified only when measured on-demand freshness or
latency is insufficient.

## Research basis

- Backstage treats its catalog as a cached hub rather than the ultimate source
  of truth and keeps ownership in repository descriptors.
- GitHub webhook deliveries need explicit failure recovery, so events cannot
  replace reconciliation.
- Kubernetes watch semantics demonstrate consistent snapshots plus ordered
  change streams and resumable cursors.
- WHATWG Server-Sent Events are an appropriate later one-way browser update
  mechanism; WebSockets are unnecessary without bidirectional interaction.
- OpenTelemetry's separate but correlatable signals inform event lag, errors,
  reconciliation age, and source-coverage telemetry.
- WCAG 2.2 and native HTML table guidance inform keyboard, focus, non-color,
  reduced-motion, and status semantics.

See the task postflight for the exact reviewed source URLs and validation
evidence used for this revision.
