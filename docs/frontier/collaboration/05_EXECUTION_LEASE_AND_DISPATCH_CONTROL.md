# Execution Lease And Dispatch Control Decision

Date: 2026-07-13
Risk tier: high
Status: independently approved as a disabled shadow kernel in the recovery tree; no executor or activation

## Decision

Keep lease, dispatch-intent, approval, revocation, and reconciliation authority
events in the existing Portfolio OS ledger. Derive a separate execution-control
projection. Do not create a second canonical authority ledger.

A future executor may own an append-only attempt journal for claims, starts,
outcomes, and crash recovery, but those observations cannot grant, renew,
revoke, or complete portfolio authority. Every join must use exact immutable
lease, dispatch-revision, scope-digest, approval, and attempt identifiers.

## Options considered

- Option A: one canonical ledger plus a separate pure execution projection.
  This preserves order with lifecycle, bindings, and revocations and reuses the
  tested redaction, hash-chain, idempotency, lock, torn-tail, and corruption
  controls.
- Option B: a second canonical execution ledger. Rejected because cross-ledger
  snapshot consistency, recovery ordering, and authority divergence add risk
  without providing a needed failure-domain benefit.
- Synthesis: a later non-authoritative attempt journal is allowed only to isolate
  noisy executor telemetry. It never becomes an authority source.

The independent architecture reviewer selected the synthesis above and required
reader-first migration, exact scope digests, separate lease and dispatch
approval, deny-all on diagnostics or drift, and no retry after an unknown outcome
without reconciliation.

## Implemented boundary

Implemented:

- mixed-schema reader for legacy workstream v1 and execution-control event v1;
- strict events for lease request/grant/revoke and dispatch propose/approve/revoke/reconcile;
- positive, maximum-31-day lease intervals and exact-boundary expiry;
- composite workstream/business identities and immutable first request/proposal folds;
- historical `as_of` filtering and fold-diagnostic blocking;
- active workstream, accepted repo binding, action, canonical repository-relative
  paths, agent-owner/worker, worker/checker, evidence, snapshot, and default
  forbidden-action gates;
- byte-exact SHA-256 scope digests for lease and dispatch revisions;
- default deny-all typed attestations bound to the exact authority-event digest,
  verifier identity, and validity interval; bare or reused IDs never authorize;
- fail-closed revocation, active-only renewal cutover, and explicit blocking when
  multiple active successors compete for one prior lease;
- reconciliation that remains pending until the attempt journal exists;
- local JSON/HTML execution projection and CLI commands;
- opt-in restricted-Windows pytest temp fixture using ignored
  `.pytest-tmp-root/` storage.

Not implemented:

- trusted human identity or approval provider;
- authority-domain/hub binding for trusted attestations;
- executor, Git mutation, agent launch, network, tasks, calendar, notifications, or scheduling;
- repository mutation lock, live HEAD/dirt/authority-manifest recheck, spend-once claim,
  attempt journal, crash recovery, or outcome reconciliation command;
- cross-repo approval, public release, delivery, merge, cleanup, or protected-branch writes.

The CLI intentionally cannot accept verified attestations. A recorded approval
is therefore `approval_unverified` in normal operation. Even an independently
built projection with a typed attestation returns only a manual packet:
`dispatch_allowed` remains false.

## Independent review

The first correctness review blocked promotion after reproducing:

- cross-workstream authority attachment by business-ID collision;
- dispatch action, binding, path, owner, and forbidden-action scope escalation;
- duplicate request/proposal resurrection after revocation;
- bare approval-ID reuse and deterministic scope-digest collisions;
- future authority events affecting historical projections;
- invalid replacements superseding valid leases;
- ignored fold diagnostics and overlong schema-valid raw leases;
- reconciliation claiming outcomes without an attempt journal; and
- schema-valid traversal paths bypassing writer helpers.

The revised fold and authority-invariant suite close those reproductions. The
same independent reviewer replayed the cases and approved the result as a
disabled shadow kernel. No Git, subprocess, network, agent-launch, or execution
path was found; `dispatch_allowed` remains unconditionally false.

## Kill criteria

Stop before executor work if any caller can self-verify approval, lease alone can
trigger mutation, joins become fuzzy, repo drift does not force reapproval,
concurrent claims can both win, unknown outcomes retry automatically, ledger
diagnostics are ignored, result observations affect authority, expiry changes
lifecycle, raw payloads or absolute paths leak, or rollback requires truncation.

## Validation evidence

- Execution-control and authority-invariant suites: 21 tests pass.
- Expanded Portfolio/event/attention/trigger/navigation/skill focused gate:
  111 tests pass.
- Ruff passes on changed Python and tests.
- Agent-skill library validation reports 16 valid skills.
- DAD validation checks 241 records with zero warnings or errors.
- Roadmap check exits zero without updating evidence.
- CLI help exposes lease request/grant/revoke, dispatch propose/approve/revoke,
  execution projection, and dispatch packet commands; it exposes no executor.

The first pytest attempts did not reach product assertions because Windows ACLs
denied pytest's managed temporary roots. The opt-in `DAD_PYTEST_TMP_ROOT`
fixture changed the observable result from setup failure to passing focused
gates while leaving normal pytest behavior unchanged when unset.

A current full-suite run is not claimed. It hung in
`test_doctor_uses_custom_locator_from_non_dad_repo` after a Windows `.cmd`
timeout left a CPU-active descendant. The process tree was terminated and the
run is recorded as invalid, not passed. The last pre-slice full-suite evidence
remains 1,183 passed in 685.9 seconds.

## Next gate

Build a trusted local human-approval verifier, bound to this authority domain,
before any executor. Then build a separate dry-run attempt journal and executor
with live repository precondition checks and a single-winner claim protocol. It
must remain disabled until independent tests prove revocation between claim and
mutation, repository drift, crash/unknown outcome, OneDrive lock contention,
and zero-write dry runs.
