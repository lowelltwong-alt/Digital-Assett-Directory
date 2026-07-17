# DAD Intent Continuity Graph

## Purpose

The Intent Continuity Graph extends the existing DAD Portfolio OS so explicit
material ideas, plans, workstreams, repositories, refs, worktrees, Codex task
metadata, interruptions, validation, and closeout evidence can be recovered as
one current view. It is not a second idea library or execution authority.

The system answers five questions:

1. What material work exists, and where is its current evidence?
2. Was this idea or plan continued or restarted elsewhere?
3. What was interrupted, and what is the exact next action?
4. Which roadmap outcomes have acceptance evidence?
5. Which tasks or worktrees are ready for a separate human archive decision?

## Authority and privacy

- Existing DAD plan, workstream, identity, execution-control, Git observation,
  validation, and human-decision records retain their authority.
- Continuity events are minimized observations. They do not create projects,
  workstreams, priority, leases, tasks, branches, worktrees, reminders, archive
  actions, notifications, or execution rights.
- The core stores no raw messages, conversations, prompts, prompt hashes,
  hidden reasoning, source blobs, diffs, credentials, or sensitive absolute
  paths.
- Codex task data enters only through an explicit versioned metadata receipt.
  DAD does not inspect Codex internal files or raw transcripts.
- Similarity may produce `possible_duplicate_of`; it never merges identities.
- Task archive, worktree removal, and branch deletion are three separate human
  decisions. No continuity command performs them.

## One state model with orthogonal overlays

The durable workstream lifecycle remains the implemented attention-kernel
vocabulary:

```text
proposed | active | paused | snoozed | incubating | merged |
superseded | archived
```

Readiness, focus, blocking, validation, delivery, research, plan lifecycle, and
implementation status are evidence overlays. They never replace or silently
transition the durable lifecycle.

Plan lifecycle is:

```text
draft | decision_complete | superseded | withdrawn
```

`approved_for_execution` is deliberately not a plan lifecycle value. Execution
approval is derived only from the signed, time-bounded Portfolio OS execution-
control plane. A bare approval identifier grants nothing.

Interruption is an observation plus a resume capsule. It is not a lifecycle
state. A task switch cannot silently mark work paused, blocked, abandoned, or
archived.

## Manual workflow

The first activation rung is completely manual:

```text
intent checkpoint
  -> immutable plan revision
  -> structured roadmap items
  -> resume packet
  -> evidence-gated roadmap/plan acceptance
  -> proposal-only archive assessment
```

Relevant commands:

```text
asset-dir os intent checkpoint
asset-dir os plan capture
asset-dir os plan revise
asset-dir os plan roadmap-add
asset-dir os plan roadmap-transition
asset-dir os plan roadmap-status
asset-dir os plan resume
asset-dir os plan accept
asset-dir os plan archive-assess
asset-dir os plan workflow-status
asset-dir os continuity scan
asset-dir os continuity recover "<idea or plan>"
asset-dir os continuity status --view summary
asset-dir os continuity status --view graph
asset-dir os continuity status --view queues
asset-dir os continuity reconcile
asset-dir os continuity observe --receipt-file <minimized-receipt.json>
asset-dir os continuity benchmark-hook --output <performance-evidence.json>
asset-dir os continuity benchmark-hook-scale --output <scale-evidence.json>
asset-dir os continuity host-readiness --repo <local-repo>
asset-dir os continuity host-readiness --repo <local-repo> <review-and-dispatch-attestations> --record
asset-dir os continuity trial-review --performance-evidence <performance-evidence.json> --supervisor-attestation-id <reviewed-attestation-id>
asset-dir os continuity activation-check
asset-dir os continuity trial-readiness --trial-id <trial-id> --repo <local-repo>
asset-dir os continuity stage-status --trial-id <trial-id> --repo <local-repo>
asset-dir os continuity stage-approval --trial-id <trial-id> --stage-id <stage> --decision <approve|revoke|kill> <operator-attestation-and-safety-criteria>
```

Benchmark receipts are revision-bound, schema-checked, and internally
self-consistent, but they are not cryptographically origin-authenticated. They
remain local candidate evidence and require a supervisor to attest each real
trial review; a receipt alone cannot authorize trust or activation.
Historical review rows written before the attestation field was introduced
remain readable. Fixture rows never count toward activation, and historical
real rows without attestation remain failing evidence. Every new
production-clock review is rejected at recording time without an explicit
supervisor attestation, while the evaluator independently rejects any
unattested real review. The recorder also fails before reading metrics or
appending anything unless the repository has a recorded, current, ready host
assessment bound to the exact runtime-adapter interface.

An accepted roadmap item requires acceptance evidence, an independent check,
distinct producer/checker identities, and explicit human approval evidence.
A verified-complete plan retains the stricter existing validation-receipt gate.
Closed tasks, merged branches, clean worktrees, contained commits, and patch
equivalence are supporting evidence only.

Task-archive readiness also requires a current minimized task snapshot with an
explicit receipt reference. Its observation and expiry must bracket the
assessment time, and the validity window may not exceed 24 hours. An expired,
future-dated, malformed, or unreceipted snapshot blocks readiness. Task
archive, worktree removal, and branch deletion remain separate proposals that
require exact human approval; assessment never performs an action.

## Ref-aware recovery

Recovery uses local evidence only and must never fetch:

- `refs/heads/**`, `refs/remotes/**`, and `refs/tags/**`;
- deduplicated commit object IDs;
- linked worktrees and detached heads;
- staged, unstaged, and untracked overlay counts;
- bounded ref and worktree matching;
- DAD plans (including private source bindings), entities, accepted workstream
  bindings, and explicit Codex metadata receipts.

`asset-dir os continuity recover` joins those sources into one bounded,
no-winner result. Git objects, dirty overlays, and Codex receipts remain
path/content minimized; DAD plans, entities, families, skills, capabilities,
and workflows retain their stable IDs and evidence references. Missing source
classes remain explicit coverage gaps rather than a false all-clear.

Missing, timed-out, corrupt, ignored, binary, oversized, or unavailable sources
produce coverage gaps. They never produce a false all-clear result. Ref search
persists match identities and hashes, not source snippets or blobs.

## Graph and projections

The rebuildable graph may contain entity, project, plan revision, roadmap item,
workstream, repository, ref, commit, worktree, Codex task, observation,
validation, and human-decision nodes.

Typed candidate edges include `contains`, `plans_for`, `implements`, `bound_to`,
`continues`, `depends_on`, `possible_duplicate_of`, `supersedes`,
`validated_by`, and `observed_as`.

Views are:

- one repository cockpit per repository;
- one cross-repository temporal graph;
- current-state queue;
- interrupted/resume queue;
- possible-duplicate queue;
- next-action queue, with at most three immediate asks;
- archive candidates with separate task/worktree gates.

Each repository cockpit carries repository-local current state, activity rows,
queue slices and counts, closeout readiness counts, and coverage. The live
status/reconciliation runtime conservatively derives duplicate-plan pairs and
terminal closeout assessments instead of leaving those queues empty unless a
test injects evidence. Automatic duplicate discovery first requires an exact
normalized identity-token signature and then the established relation
classifier; it is bounded to 250 plans and reports truncation as a coverage
gap. No duplicate candidate is merged automatically.

The objective's four action queues are `interrupted_resume`,
`possible_duplicates`, `task_archive`, and `worktree_close`. The projection
schema exposes seven queue keys because it also includes the supporting
`current_state`, bounded `next_actions`, and `next_actions_overflow` views; this
is one contract, not seven additional workflow requirements.

All projections carry observation times, source digests, coverage gaps, and
candidate-only authority labels. Deleting a projection and replaying immutable
events must reproduce it.

External planning systems remain optional projections. For example,
[GitHub Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects)
can expose a useful roadmap view, but it cannot become the authority for
unpublished ideas, local dirty overlays, linked worktrees, private DAD plans, or
Codex task observations. Import and export adapters must preserve this one-way
authority boundary and may not infer completion from an external board state.

## Shadow adapters and reconciliation

Hooks are lossy sensors. A thin adapter may record a minimized local receipt and
must return without model, network, notification, scheduler, or Git-write work.
Exact retries are idempotent; conflicting reuse fails closed. Periodic
reconciliation is the recovery mechanism when a hook is absent or fails.

Initial runtime events are limited to session start, pre/post compaction, turn stop,
explicit task metadata, and DAD lifecycle checkpoints. `UserPromptSubmit` is
not eligible for initial activation because it touches every prompt and has a
higher privacy/noise cost.

The reviewed adapter specification is
`config/intent-continuity-shadow-hooks.json`. The supervised repo-local hook is
defined in `.codex/hooks.json`; Codex loads project hooks only for trusted
projects and requires review of the exact command-hook hash before persistent
execution. The handler ignores `cwd`, `transcript_path`, model, permission mode,
prompts, messages, and source content, and emits no output. `UserPromptSubmit`
is absent from the installed hook definition. Codex `Stop` is recorded only as
`turn_stopped`; it never closes a session. The repo-local adapter supplies the
reviewed non-path DAD enrollment ID so cross-repository projections can attribute
activity without storing a filesystem path. The handler reads the reviewed
trigger config on every invocation, so disabling a trigger or changing the
shadow status is an effective fail-closed runtime kill switch.

Codex host readiness is a separate adapter gate. The non-mutating-by-default
`host-readiness` command binds the current hook definition, adapter-interface
digest, project-trust attestation, exact-hook-trust attestation, `/hooks`
discovery observation, the exact hook-file byte digest, and an operator
attestation bound to one exact current-revision ledger event. It validates the
event's adapter, revision, source kind, repository, event kind, and temporal
order. Ledger integrity does not authenticate host origin, so the result records
`origin_authenticated: false` and never describes the event as cryptographic
proof. An operator-attested event is required because project-hook discovery can
differ by host and repository layout. In particular, an open upstream Codex issue reports
project hooks being ignored in linked worktrees even when trust is present:
https://github.com/openai/codex/issues/27133. This is a runtime risk signal, not
proof that every Codex version is affected. The gate therefore remains closed
until this exact worktree produces a silent event that a human observer binds to
its exact content-free event ID.

The command remains read-only unless `--record` is explicitly supplied. A
recorded assessment is appended to the initialized private DAD data root with
exact-replay deduplication. It stores at most five content-free attestable event
references (event ID, observed time, and event kind), never prompts, transcripts,
paths, source content, or model names. `activation-check` loads the latest
recorded assessment for that repository by default, revalidates its digest, repository identity,
current hook bytes, adapter revision, and adapter-interface digest, and rejects
reviews that predate that assessment. An explicit evidence file may be checked,
but it must exactly match the latest assessment for that repository already present in the private ledger
and receives the same current-binding validation. This is eligibility
evidence only; activation still requires a separate human approval.

Do not write private `[hooks.state]` values, use
`--dangerously-bypass-hook-trust`, move the hook to a user-global layer, or copy
the repository merely to make this gate pass. Codex's supported review path is
`/hooks`; the linked-worktree trial must record operator-attested discovery and
dispatch evidence in the actual host after human review. The official Codex hooks contract is:
https://learn.chatgpt.com/docs/hooks.

Normal append uses a rebuildable exact-content index containing command IDs and
byte offsets, never source content. The index is accepted only when its ledger
size and SHA-256 match exactly and its last event revalidates. A crash or any
ledger change invalidates the index and forces a full chained replay. Every new
event still receives full JSON Schema, privacy, payload-digest, and chain
validation. Cold replay uses a schema-derived integrity validator, including
the nested adapter payload contract, to avoid general-purpose JSON Schema
overhead across thousands of already-validated rows. A dead-owner lock older
than 30 seconds may be recovered under a durable cross-process recovery guard;
owner-token checking prevents one process from releasing another process's
lock, and a live owner is never displaced. Normal hook lock acquisition fails
after 1.5 seconds, leaving
time for the five-second host boundary. When normal ingestion fails but the
private root remains reachable, a separate content-free failure marker makes
missed coverage measurable without storing the prompt, path, transcript, model,
session ID, or turn ID.

Observation, production-trial, and projection writes fail closed unless
`DAD_DATA_ROOT` is initialized and its marker belongs to the selected DAD hub.
The isolated worktree uses the existing user hub locator to write minimized
private evidence to the initialized central DAD data root; it does not create a
second private store inside OneDrive. Read-only scan, recovery, and in-memory
status remain available without that write surface.

### Linked-worktree hub routing

The two command classes deliberately resolve different authority surfaces:

- Validate source and registries in this checkout with `--hub .`, for example
  `asset-dir validate --hub .` and `asset-dir portability validate --hub .`.
- Run private continuity and trial commands without `--hub` so
  `~/.dad/hub.json` resolves the canonical DAD hub whose initialized
  `DAD_DATA_ROOT` marker owns the private ledgers.

Passing `--hub .` to a private trial command inside a linked worktree selects
that worktree as a distinct, uninitialized hub and must fail closed. Do not fix
that failure by initializing a second worktree-local private store.

## Activation ladder

```text
manual
  -> supervised repo-local silent shadow (current; trust review pending)
  -> trial incomplete
  -> eligible for human activation
  -> session-start read-only summary
  -> weekly changed-only digest
  -> separately approved breakpoint prompts
```

The system never enables automatic cleanup.

At least five non-fixture supervised reviews must span at least seven real
calendar days. Synthetic timestamps test the evaluator but cannot satisfy the
production gate. Every qualifying review must include at least five measured
hook samples, nearest-rank p95 latency, the reviewed latency budget, and an
instrumented receipt bound to the exact adapter-interface digest. Eligibility also
requires zero missed or harmful captures, false merges, accidental mutations,
repeated unchanged asks, privacy failures, unauthorized notifications, and
latency-budget failures; no digest may contain more than three asks. Schedule,
timezone, channel, retention, expiry, rollback, and kill criteria require an
exact human approval record after the trial.

The trial CLI no longer accepts free-form latency values. It validates the
instrumented receipt's measurement identity, sample math, command digest,
adapter revision, adapter-interface digest, silence, persistence, privacy, and
unchanged-source result before recording a production-clock review.

The current review contract also measures `missed_recoveries`,
`false_duplicate_suggestions`, and `unauthorized_mutations` independently from
accidental mutations. Historical rows without those fields remain
readable but fail the current activation gate until current supervised reviews
provide them.

`trial-readiness` composes the validated activation state into one digest-bound,
read-only operator packet. It reports the exact remaining review count, real
calendar span, earliest possible eligibility timestamp, revision failures that
require a new trial ID, the full metrics/performance contract, and the next
honest human action. It cannot record a review, advance time, trust a host,
activate a stage, deliver a reminder, or authorize cleanup.

The projection includes a dormant `attention_readiness` contract. It renders a
bounded session-start summary preview, reuses the existing changed-only weekly
digest builder, and emits at most one generic breakpoint-prompt preview. Every
preview records `delivery_authorized: false`; trial eligibility only opens a
separate human-approval gate for the session summary and cannot skip ahead to a
digest or breakpoint prompt.

Later stages have an append-only, private stage-decision ledger. An approval is
bound to the stable qualifying review set, recorded host assessment, exact
adapter-interface digest, predecessor approval event, expiry, rollback
criteria, and kill criteria. Revoke and kill decisions fail closed and block
downstream stages. Fixture approvals never authorize a real stage. The records
are operator-attested rather than cryptographically origin-authenticated, and
the control plane only projects scoped authority: it does not deliver a
summary, schedule work, invoke a model, mutate Git or tasks, archive a task, or
clean up a worktree. Both `stage-status` and the main in-memory/persisted
continuity projections recompute state from the raw append-order ledger; a
later safety decision wins even if a producer clock moves backward.

The first real-clock preflight review is intentionally non-qualifying: the
installed npm CLI is older than the desktop host, its documented one-off trust
bypass is unavailable, and two attempted sessions produced no hook receipt.
That review records one missed capture and zero latency samples under a separate
preflight trial ID. The qualifying seven-day clock does not start until an
actual trusted desktop-host event is observed.

## Bounded agent roles

Existing Personal Project Management roles are reused:

- `related-work-scout`: ref-aware retrieval and duplicate candidates;
- `forgotten-plan-sentinel`: quiet changed-only resume suggestions;
- `workstream-intake-identity-steward`: worktree-need recommendations;
- `partial-build-diagnostician`: plan/Git/task/validation reconciliation;
- `delivery-closeout-resumption-steward`: separate archive proposals;
- `recovery-independent-checker`: completion and cleanup verification.

Deterministic code owns ordinary observations. Agents enter only for ambiguity
or independent judgment, remain read-only, and cannot approve their own output.

## Kill criteria

Disable proactive activation if any cycle causes a false automatic merge,
privacy escape, unapproved task/Git mutation, repeated unchanged ask, more than
three immediate asks, false completion, non-replayable projection, duplicate
semantic event on retry, missing latency sample, p95 latency above the reviewed
1,500 ms cold-start shadow budget, blocking hook latency, or failed restore.
Rollback removes or disables
`.codex/hooks.json` and sets the four lifecycle triggers back to disabled;
private append-only evidence is retained for audit and never used to authorize
cleanup.
