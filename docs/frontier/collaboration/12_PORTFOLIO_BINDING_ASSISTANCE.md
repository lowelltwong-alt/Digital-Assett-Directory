# Portfolio Binding Assistance Decision

Status: implementation decision for the first DAD Portfolio OS reconciliation layer.
Risk tier: high. This layer suggests identity associations that a human may later
turn into durable binding assertions.

## Decision

Add one pure, snapshot-bound projection after the strict cockpit:

    dad.portfolio_attention.v1
      + dad.portfolio_workstreams.v1
      -> dad.portfolio_cockpit.v1
      -> dad.portfolio_reconciliation.v1
      -> local JSON + script-free HTML under DAD_DATA_ROOT

The public operator verb is 'asset-dir os reconcile'. It may refresh the
read-only Git observation and cockpit first, but reconciliation itself consumes
only the resulting strict cockpit object.

The projection may:

- signal that workstream intake is needed when no workstreams exist;
- repeat an existing exact proposed binding for review;
- propose the exact other half of a unique branch/worktree structural pair when
  the workstream label shares a discriminating non-default branch token;
- show lexical relation evidence as 'inspect_only';
- retain exact structural evidence outside the bounded Today review set as
  non-command-bearing 'proposal_available' evidence;
- expose exact opaque resource IDs, ambiguity, conflicts, unassigned observed
  work, intake need, quiet work, accepted-only dependency context, and evidence
  blockers.

It may not:

- generate split, rescope, recovery, or duplicate-workstream decisions in this slice;
- append a ledger event;
- accept or retract a binding;
- create or transition a workstream;
- create a branch, worktree, commit, task, schedule, notification, or dispatch;
- infer canonical identity from age, dirt, activity, similarity, or a score;
- show absolute source paths or raw conversation content.

## Options considered

1. Add automatic 'binding_asserted(proposed)' events on every refresh. Rejected:
   repeated scans would pollute the authority ledger, the current event lacks
   evidence-revision fields, and proposal churn could masquerade as user intent.
2. Add a pure reconciliation projection. Chosen: deterministic, removable,
   trialable without a migration, and incapable of promoting itself.
3. Keep manual 'os bind' only. Deferred fallback: safest, but it leaves the user
   to discover opaque exact resource IDs and does not help recover creative
   sprawl.
4. Add a separate proposal database. Rejected: it would introduce a second
   canon beside the Model C ledger.

## Source and identity contract

Methodology version: 'dad.portfolio-reconciliation-selection.v1'.

The cockpit must pass its registered strict schema, and both nested source
descriptors must be 'observed/current', before candidate generation. Duplicate
workstream/resource IDs are quarantined. Binding status, resolution, kind,
resource identity, and workstream identity must agree semantically. Accepted-but-
unresolved bindings are blockers. Cockpit unknowns prevent candidate commands and
`fully_reconciled=true`. A cross-field semantic validator recomputes source-hash
coupling, proposal and revision identities, exact command targets, card and bundle
references, summary counts, and the full-reconciliation predicate before any
cursor is published. Workstream cards have stable identity and evidence-revision
IDs so shape-valid tampering cannot silently change accepted or hidden coverage.

Stable proposal identity is:

    stable_id(method_id, workstream_id, exact_resource_id)

Evidence revision identity is:

    stable_id(proposal_id, canonical_material_evidence_hash)

'generated_at', inactive-day ticks, and input array order are excluded from the
proposal/revision identity. Set-like cockpit arrays are canonicalized in the
source fingerprint; Today and attention-queue order remain meaningful.

## Evidence precedence

The projection uses ordinal evidence classes, not one composite identity score:

1. 'E0_existing_exact': an exact proposed binding already exists. It is shown
   for review and emits no command because repeating it would duplicate ledger
   intent.
2. 'E1_unique_structural': an accepted exact branch or worktree and its
   opposite-kind counterpart are the only raw links on both sides, are reciprocal,
   share one project, the counterpart is not a generic/default branch, and the
   workstream label shares a discriminating token. This may emit a structured
   proposal-only 'asset-dir os bind' command only when no blocker or unknown
   evidence exists and the exact candidate is inside the bounded review set
   derived from cockpit Today. Otherwise it remains 'proposal_available' with no
   command. A command never includes '--accept', '--approved-by', or another
   promotion flag.
3. 'I0_inspect_only': the existing IDF-cosine relation classifier found a
   lexical relation. The numeric score is displayed only as similarity
   evidence. It cannot emit a command or create identity.

Dirt, age, and attention priority may explain why a resource needs recovery;
they never identify its workstream.

## False-green rules

'no_candidates_generated' is separate from 'fully_reconciled'.

'fully_reconciled' requires:

- a valid/current cockpit and nested sources;
- no reconciliation blockers;
- no cockpit unknowns;
- at least one eligible nonterminal workstream;
- every eligible workstream has a semantically valid exact accepted binding;
- every most-specific branch/worktree resource in observed attention has an exact
  accepted owner for the projected workstream (a repo binding is context only);
- no visible or hidden exact structural binding proposal remains ready or
  available;
- accepted ownership is bidirectional across binding, workstream, and resource
  projections.

Zero workstreams means 'intake_needed=true', zero binding candidates, and
'fully_reconciled=false'. The projection never fabricates a canonical
workstream ID.

Proposed bindings cannot join cockpit attention, change the board, affect
dependency rollup, or enter the accepted-only unlock frontier.

## Human attention budget

Reconciliation does not create a second daily queue. Its 'review_queue' is
bounded to three and may reference only items already present in cockpit
'today'. Persisted proposal commands are a subset of that bounded queue. All
other exact candidate evidence becomes non-command-bearing 'proposal_available'
or remains in lower recovery lanes. Hidden candidate and hidden exact-proposal
counts are explicit globally and per workstream.

The HTML is inert: fixed hash-bound inline CSS, no scripts, forms, external
resources, action buttons, or mutation controls. Labels are escaped and source
paths are omitted. It exposes hidden-candidate counters and per-workstream
coverage so a false state is explainable without opening raw JSON.

## Blast radius

- one pure Python projection module;
- one strict registered schema;
- one 'asset-dir os reconcile' command;
- 'asset-dir os refresh' publishes cockpit and reconciliation as one bounded
  pair with synchronous rollback if either cursor publication fails;
- one script-free local HTML report and one JSON report;
- scanner Git subprocesses run with `GIT_OPTIONAL_LOCKS=0` to prevent optional
  index refreshes during read-only status collection;
- focused adversarial tests and navigation/documentation updates.

No ledger migration, Git write, sibling-repository write, daemon schedule,
connector, MCP mutation tool, or execution-authority change is included.

## Adversarial acceptance

Required tests cover:

- missing/invalid/stale/future source state and no false green;
- zero workstreams producing intake need without identity creation;
- existing exact proposals remaining review-only;
- unique structural evidence producing only a proposal command;
- no promotion flags in the CLI or structured command;
- lexical similarity remaining inspect-only;
- deterministic output under set-like input permutations;
- duplicate, semantically contradictory, and accepted-unresolved binding
  blockers;
- repo-context bindings unable to join or quiet branch/worktree attention;
- reciprocal, same-project, opposite-kind, unique raw structural links;
- blocker or unknown evidence suppressing all proposal commands;
- proposed evidence unable to affect accepted dependency context;
- HTML escaping, path omission, CSP, and absence of active controls;
- strict output validation plus cross-field semantic validation before
  HTML-first/JSON-last publication;
- stable card identity/revision checks and command-target equality;
- commands bounded to the existing Today review set, with off-queue exact
  evidence remaining command-free;
- optional-lock suppression on every scanner Git subprocess;
- unchanged source-repository indexes, configs, refs, statuses, and ledger in
  the bounded operator trial.

## Kill and rollback criteria

Disable the layer immediately if it appends an event, mutates Git, generates an
accepted binding, selects an ambiguous winner, exposes an absolute path or raw
private payload, churns proposal identity on timestamps/order alone, represents
zero candidates as reconciled, or changes accepted dependency projections.

Rollback is removal of the module, schema, command routing, navigation rows, and
generated 'reconciliation.json'/'reconciliation.html'. Existing cockpit,
workstream ledger, and Git observations remain valid and require no migration.

## Independent architecture review

The registered 'workstream-intake-identity-steward' role reviewed the slice at
Terra/medium effort. It recommended this projection boundary over durable
automatic proposals, required separate proposal/revision identity, strengthened
zero-workstream and false-green behavior, prohibited token-only binding
proposals, and found no need for Sol/Fable escalation because current authority
sources agree.

The attempt self-rated 4.8/5. The remaining uncertainty is real-world proposal
precision, so activation remains a supervised operator trial and no schedule is
created.

## Operator evidence and deferred scope

The supervised trial is recorded in
`roadmap/evidence/portfolio-reconciliation-operator-trial.md`. It observed 31
projects, 230 branches, 141 worktrees, 192 attention items, and four unknowns.
One minimized workstream plus one existing exact proposed binding produced three
candidates: one exact review-only item, two inspect-only relations, and no
proposal-ready command. The report stayed `fully_reconciled=false`.

A repeated default-scan fingerprint found no changes across 31 common Git
project surfaces plus all 141 linked worktree surfaces, and no workstream-ledger
change. It compared index/config/HEAD bytes and modification times, logical refs,
statuses, remotes, packed refs, and lock presence with optional locks disabled.
Four discovery-error hashes also remained unchanged. The final JSON and HTML
contained no absolute Windows or UNC path.
Most-specific branch/worktree attention grouping reduced 325 fragmented
resource rows to 188 collapsed recovery bundles. Broad repo identity stays project
context and is not propagated into every branch/worktree bundle. That local delta
is evidence about presentation, not a general metric.

This slice implements identity reconciliation and a boolean intake signal only.
Candidate-only workstream split, rescope, duplicate detection, and recovery
options remain deliberately deferred until they have a supervised evidence model
and their own false-positive controls.
