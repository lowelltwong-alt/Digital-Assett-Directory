# DAD Operational Cockpit

## Outcome

The operational cockpit is the thin local envelope around DAD's existing
Portfolio Cockpit v1, Portfolio Cockpit v2, Capability OS cockpit, daemon
heartbeat, and event-pipeline report. It does not replace any of those source
projections.

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

The host verifies a generation receipt, JSON schema, semantic invariants, and matching JSON/HTML digests on every request. It never scans a
repository, rebuilds a source projection, appends an event, or executes an
action. The operator explicitly rebuilds the operational envelope when desired.

## Commands

Build from precomputed local reports:

```text
asset-dir os operational-cockpit --hub <DAD checkout>
```

Serve in the foreground on loopback only:

```text
asset-dir os cockpit-host --hub <DAD checkout> --port 8765
```

The host exposes only:

- `/` and `/index.html`: escaped, script-free HTML;
- `/api/snapshot`: the authoritative generated JSON projection;
- `/healthz`: coherent last-valid-bundle availability, never source health or action authority.

All mutation methods are denied. Directory browsing, arbitrary files, external
bind addresses, external JavaScript, and action endpoints are absent.

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
`stale`, `missing`, or `invalid`. Portfolio v1, portfolio v2, and Capability OS inputs must pass their authoritative registered JSON Schemas. Daemon and event inputs must pass strict producer invariants: daemon evidence counts as current only after a complete, finalized cycle with a completion timestamp, and event counts must be nonnegative. Missing or malformed timestamps, timestamps more than five minutes in the future, wrong field types, and authority-contract violations are invalid. Stale or invalid sources cannot contribute decisions or event-pulse values.
The whole cockpit is `current_candidate` only when all five sources are current;
every other condition is `partial_candidate`. Candidate status is never an
approval or source-authority transfer.

The page exposes at most three immediate decisions and preserves the source
health table as the drill-down. Unknown state is visible and never rendered as
green.

## Revision-bound contract evidence

Revision `0.2.0` binds its contract digests to these canonical materials:

- input: five named precomputed sources, source-specific strict invariants v2,
  and a maximum five-minute future-clock tolerance;
- output: `dad.operational_cockpit.v1`, a
  `dad.operational_cockpit.receipt.v1` coherence receipt,
  `local_private_metadata`, and at most three decisions;
- error: invalid sources force `partial_candidate`, stale/invalid payloads
  contribute no decisions or pulse, invalid bundles return HTTP 503, and
  mutation methods return HTTP 405;
- privacy: loopback-only bind, local-private classification, decision strings
  bounded to 240 characters, and at most ten 240-character evidence refs.

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
