# Portfolio Workstream Shaping Decision

Status: implemented candidate projection; no durable decision event or executor.
Risk tier: high. Decision date: 2026-07-13.

## Decision

Implement split, rescope, possible-duplicate, and recovery assistance as a pure, removable projection over the strict current workstream, cockpit, and reconciliation snapshots. A refresh may generate or remove cases but may not append proposal events. A future explicit human command may record a decision against an exact `case_id` and current `revision_id`; that command and every executor remain separate gates.

This adopts the safe half of the independent architecture recommendation. Durable scanner-generated proposal events were rejected because they would turn changing observations into apparent human intent, pollute the single authority ledger, require retraction semantics, and risk affecting board or attention folds.

## Load-bearing review

Selected checklist branches: universal; schema/contract; identity resolution; workflow/agent; security/authority; generated exports; testing.

Authority order:

1. Repository front door and registries.
2. The verified workstream fold.
3. The strict Portfolio Cockpit.
4. Proposal-only reconciliation.
5. This candidate-only shaping projection.
6. A later named human decision.

Similarity, age, labels, graph position, project co-location, and model output are never identity or execution authority. Exact accepted most-specific resource assertions remain the strongest evidence available, and even they produce a review case rather than a winner.

## Evidence tiers

The tier prefixes are local ordinal categories, not probabilities or a composite project-value score.

| Tier | Meaning | Disposition |
| --- | --- | --- |
| `PD0_shared_exact_specific_resource` | Two eligible workstreams claim one accepted branch or worktree. | Review the ownership collision; select no canonical workstream. |
| `PD1_reciprocal_exact_pair_split_between_workstreams` | A reciprocal same-project branch/worktree pair is split across owners. | Review scope or mistaken ownership; select no winner. |
| `PD2_similarity_only` | Short labels cross the existing deterministic duplicate threshold with at least three shared discriminating tokens. | Inspect only; shared tokens are emitted only as hashes. |
| `SP0_disconnected_exact_owned_components` | One eligible workstream owns at least two disconnected exact components, supported by multiple projects or attention-bearing components. | Review whether the boundary should split. |
| `RS0_exact_contextual_unassigned_bundle` | An exact unowned bundle has an exact joined workstream context. | Review later inclusion, sibling intake, or intentional non-assignment. |
| `RS1_repo_context_only` | The context comes only from broad repository ownership. | Inspect only; repo identity is not branch/worktree identity. |
| `RC0_integrity_unknown_attention` | Existing cockpit attention says integrity is unknown. | Inspect evidence or defer only. |
| `RC1_dirty_exact_attention` | Existing dirty-recovery attention has exact branch/worktree scope and `dirty=true`. | Offer inert recovery choices. |
| `RC2_existing_workstream_trigger` | An eligible joined workstream already has an explicit trigger kind and signature in an allowed band. | Offer inert recovery choices. |
| `RC3_unassigned_observed_bundle` | An exact observed bundle has no workstream context and at least one non-age structural reason. | Review intake/association or leave unassigned. |

Age is annotation only. A clean bundle whose only reasons are `stale_branch` or `stale_branch_in_active_project` creates no case. Same project alone creates no case. Quiet and terminal workstreams are excluded from recovery generation. Reciprocal branch/worktree pairs are the only structural edges collapsed into one component.

## Identity and source coupling

`case_id` hashes the method, case kind, canonical subjects, and canonical source anchors. `revision_id` hashes the case plus material evidence and choice vocabulary. Timestamps, inactivity counters, labels, scores, and array order do not churn identity.

The builder validates all three registered schemas, reconciliation semantics, and these frozen-snapshot equalities:

- canonical workstream hash equals `cockpit.source_refs.workstreams`;
- queue-aware cockpit hash equals `reconciliation.source_refs.cockpit`;
- every top-level shaping source ref equals its descriptor hash.

The projection persists the actual and claimed coupling hashes in a closed `source_coupling` object, plus bounded source-ID inventories. Standalone semantics recheck coupling, tier-to-kind/disposition/choice contracts, subject membership, status, completion, and authority text. Publication additionally rebuilds the complete projection from the frozen state, cockpit, and reconciliation values and rejects any difference.

Invalid, stale, future-dated, semantically invalid, or mismatched input produces zero cases and a blocked candidate. Reconciliation blockers and unknowns are preserved and prevent `shaping_complete`, although structurally valid evidence may remain visible for human inspection.

## Attention and false-green policy

The shaping review queue is not a second Today queue. It is capped at three, references only current cockpit Today attention IDs, and keeps off-queue cases in a bounded full inventory with explicit truncation counts.

`no_cases_generated` and `shaping_complete` are separate. Shaping can be complete only with current coupled sources, no blocker or unknown, at least one eligible workstream, no visible or hidden case, no unassigned bundle, exact scope for every eligible workstream, and a fully reconciled source. Zero workstreams means intake is needed.

## Authority and privacy invariants

The JSON and HTML contain no command, apply, accept, dispatch, or execute field. Every choice says execution is unavailable and a human decision is required. The HTML is script-free, form-free, button-free, external-resource-free, escaped, and CSP hash-bound. Inherited idea, repository, branch, worktree, blocker, and unknown prose is never treated as approved display content: shaping emits categorical labels, controlled notes, and opaque refs. Portable Windows/POSIX absolute-path forms are rejected. Raw conversations and `idea_text` values never enter the output.

Publication writes shaping, reconciliation, then cockpit while snapshotting all six dependent JSON/HTML cursors. Any ordinary synchronous `Exception`, including a late third-writer failure, restores every prior cursor; `KeyboardInterrupt` and `SystemExit` are not swallowed. `os shape` and `os reconcile` build attention and workstream-state sources in memory and do not rewrite those source cursors. `os refresh` intentionally refreshes derived source reports before publishing the dependent set. This is bounded rollback, not a claim of crash-atomic multi-file storage; OneDrive interruption and concurrent readers remain trial risks.

## Python preflight decision

`py-idiom:dataclass-strict` is applied to immutable keyword-only shaping settings because it makes the bounded policy auditable. Closed schema vocabularies remain JSON-owned strings instead of adding Python enums, consistent with the idiom card's external-schema limitation. No Rust or new library was justified: the path is policy and schema orchestration, not a measured CPU hotspot.

## Acceptance and kill criteria

Acceptance requires strict schema and semantic validation, adversarial fixtures for every tier, stable identities, false-green tests, source mismatch quarantine, inert/privacy-safe HTML, exact Today subset rules, six-cursor rollback, existing producer-contract tests, and a supervised zero-write trial.

Disable and remove this slice if refresh appends an event; mutates Git, tasks, schedules, notifications, agents, bindings, or source authority; chooses a canonical workstream; turns similarity or age into authority; exposes a raw path/conversation; changes board/dependency/reconciliation state; generates from mismatched sources; churns IDs on time/order; exceeds Today; hides cases without counts; or publishes schema-valid but semantically invalid output. Rollback is deletion of this module, schema, CLI/nav rows, and shaping reports plus restoration of the former two-projection publisher. No migration is required because no event is written.

## Deferred decisions

- Durable `shaping_decision_recorded` events and stale-revision rejection.
- Any command that applies split, binding, lifecycle, Git, task, schedule, notification, or agent changes.
- Typed workstream-to-workstream relation evidence.
- Patch/PR equivalence and explicit multi-resource scope intent.
- Activation rung 2 and MCP read resources.
