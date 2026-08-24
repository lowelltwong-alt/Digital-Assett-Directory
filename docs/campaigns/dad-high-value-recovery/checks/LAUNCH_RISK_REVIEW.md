# Launch Risk Review

Status: revision-6 bounded repair accepted; launch blocked  
Risk tier: `high`  
Campaign: `dad-high-value-recovery-v1`  
Candidate revision: `6-execution-control-bridge-candidate-20260823`  
Candidate manifest digest:  
`sha256:58bf4181a3eeb2cc45156d8e50dc7089e8c1a42a17cd3ff4c4eda67f077c2ee9`  
Mesh semantic digest:  
`sha256:7ec717e316d513c65da5dc3eca372202b4488977aead6b88c1ae3d1ddf865451`

## Decision under review

Whether the bounded local revision-6 execution-control bridge, host-gate
decoupling, portability changes, evidence, and two metadata-only branch
dispositions are safe to retain. This review does not decide whether J-100 may
launch. Launch remains a separate, currently unauthorized decision.

## What revision 6 changes

- Replaces caller-supplied campaign runtime assertions with state derived from
  the existing Portfolio OS lease, dispatch, revocation, idempotency, attempt,
  and integrity projections.
- Requires a canonical manifest, measured source revision, exact active human
  authorization, named approver, and distinct verified Portfolio lease and
  dispatch approval IDs.
- Binds job action, paths, outputs, acceptance evidence, lease/heartbeat,
  worker/checker revisions, qualification files, durable receipt logs,
  budgets, checkpoints, repair state, and partial-effect reconciliation.
- Loads explicit repository-local Ed25519 authority attestations and verifies
  their signatures against the exact Portfolio events. Attestation-file
  digests are deliberately not included in the events they sign, avoiding an
  impossible circular digest.
- Keeps observation time as validated, non-authoritative metadata outside the
  stable evidence and packet digests. Rebuilding unchanged evidence later
  therefore reproduces the already approved packet.
- Denies every atomic child packet until a separate child execution binding is
  designed and implemented.
- Keeps the intent-continuity real-host qualification as a separate future
  supervised-trial gate. It is not a campaign or J-100 launch gate.
- Records the two explicitly authorized branch dispositions as metadata only;
  no branch or ref was mutated.

## Current operational result

The actual repository dry run is `blocked` with 47 human and machine reasons.
There is no revision-6 authorization, named approver, campaign-bound Portfolio
lease, or verified ready-manual dispatch. The packet digest is
`sha256:a56b05d4685c1cd56fec19cc87fde9f43c65809fa036fa043ad651263d436988`.
All seven effect counters are zero; `execution_authorized` and
`dispatch_allowed` are false.

The positive path is no longer only a synthetic in-memory projection. A
temporary repository integration test creates real Portfolio events, signs the
grant and dispatch approval with Ed25519, feeds the repository-local
attestations through the public adapter and authority fold, and reaches only
the inert `ready-manual` result. It launches nothing and performs none of the
seven prohibited effects.

## Validation evidence

- Campaign schema validator: pass; static specification only.
- Campaign consistency validator: pass.
- Mesh validation against the preserved revision-5 prior: pass.
- Execution-control, receipt, authority, and attempt focused suite: 82 passed;
  one signed integration test skipped under the standard project runtime.
- The skipped signed integration test: 1 passed under the existing bundled
  runtime with `cryptography 50.0.0`.
- Five revision-bound portability checks: pass on final registry bytes.
- Direct portability validation: valid, zero hard findings, one unrelated
  archival `nonroutable_stale_evidence` warning.
- Relevant Ruff checks and `git diff --check`: pass.
- Full repository suite and repository validator were not rerun in this
  bounded revision-6 lane. Existing untracked campaign-pointer authority
  remains a known repository-level blocker.

## Independent review

The non-author checker initially found a high-severity reproducibility defect:
volatile `observed_at` metadata was included in the packet binding. That defect
was repaired, given a regression test, and independently rechecked. Unchanged
evidence one second apart now yields the same evidence and packet digests. The
final dispositions are bounded revision-6 repair `ACCEPT` and launch, H-010,
and J-100 `BLOCK`. The machine-readable review is
`checks/evidence/launch/independent-launch-review-revision-6.json`, digest
`sha256:f1d058c3762084045732c5efc46d121f5ed4391b843846fc5c67baaf539841d1`.

## Launch blockers

1. H-010 is not valid for revision 6 or its manifest digest. The revision-3
   decision remains immutable history and does not transfer.
2. No exact revision-6 execution authorization, Portfolio lease grant, or
   manual dispatch approval exists.
3. `execution_authorized` and `dispatch_allowed` remain false; no executor or
   launch operation exists in the bridge.
4. Atomic child execution binding is intentionally unimplemented and fails
   closed.
5. Campaign files remain untracked. Repository source-authority validation
   cannot be treated as green before a separately authorized atomic tracking
   operation and full validation.
6. The standard project Python environment lacks the optional Ed25519 backend;
   a launch environment would need an explicitly reviewed dependency/runtime
   decision.
7. No real campaign job or business-value observation has been performed.

## Residual caveats

- `observed_at` is non-binding diagnostic metadata; its syntax and future-time
  boundary are checked, while current source and qualification bytes are
  independently remeasured.
- Signed attestations bind exact Portfolio events, not their own file paths or
  file digests. The adapter accepts only explicit repository-local paths and
  rejects duplicate JSON keys.
- The source revision is a content-derived digest of the canonical manifest
  and its declared source authority, not a Git commit claim.
- Date-time schema `format` behavior and the process-lifetime attempt-schema
  validator cache remain unchanged from revision 5.
- This is execution-control evidence, not proof of business value.

## Rollback and stop rule

Rollback is non-activation: retain the append-only evidence, reject or
supersede revision 6, and remove no history. Stop on changed frozen digests,
missing or unverifiable authority, stale source/qualification bytes, ledger
integrity errors, duplicate approvals, budget uncertainty, unreconciled
effects, privacy/security concern, or independent reviewer challenge.

## Required next decision

Do not treat this risk review as launch authority. After final independent
acceptance, the only next repository action that may be proposed is a separate
bounded atomic-tracking/commit decision. H-010 and J-100 remain later, distinct
decisions after all machine and repository gates pass. Staging, commit, push,
merge, deployment, GitHub changes, downstream mutation, plugins, global
settings, automation, branch deletion, and cleanup remain prohibited.
