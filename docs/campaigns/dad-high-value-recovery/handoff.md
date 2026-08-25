# Campaign Handoff

## Current state

- Campaign: `dad-high-value-recovery-v1`
- Phase: bounded revision-6 postcommit evidence correction
- Status: `specification_only`; actual dry run `blocked`
- Execution authorized: no
- Dispatch allowed: no
- Candidate revision: `6-execution-control-bridge-candidate-20260823`
- Candidate manifest digest:
  `sha256:58bf4181a3eeb2cc45156d8e50dc7089e8c1a42a17cd3ff4c4eda67f077c2ee9`
- Mesh semantic digest:
  `sha256:7ec717e316d513c65da5dc3eca372202b4488977aead6b88c1ae3d1ddf865451`
- Current blocked packet digest:
  `sha256:a56b05d4685c1cd56fec19cc87fde9f43c65809fa036fa043ad651263d436988`
- H-001 through H-010: the exact revision-3 decision is preserved, but none of
  it authorizes revision 6 or a campaign job.
- Original independent review: bounded revision-6 repair `ACCEPT`; launch,
  H-010, and J-100 `BLOCK`. Frozen review receipt digest:
  `sha256:f1d058c3762084045732c5efc46d121f5ed4391b843846fc5c67baaf539841d1`.
- Postcommit evidence correction: candidate receipt
  `checks/evidence/launch/prelaunch-evidence-correction-revision-6-postcommit.json`;
  final correction disposition lives only in
  `checks/evidence/launch/independent-evidence-correction-review-revision-6-postcommit.json`.
  The original review's diff-cleanliness assertion is superseded; its other
  evidence and dispositions remain unchanged.
- Current governed worktree: `C:\wt\dad-high-value-execution`
- Current branch: `codex/dad-high-value-execution-plan-20260820`
- Current HEAD and `origin/main`:
  `76c268d191d40dd66016e7f41ad5fa79ffbd5f29` (`1` ahead, `0` behind)
- Staged files: zero. Commit, push, merge, GitHub, deployment, downstream,
  branch/ref, and cleanup effects: zero.
- Worktree disposition: `active`; preserve it under the existing registry hold.
- Current DAD session: `dad:session:e238d819-e2a4-4598-a1bc-4eeb036948e8`
- Current preflight trace:
  `dad:trace:d04b66c9-5a18-532c-b78d-d4acda486818`
- Accepted revision-6 postflight handoff:
  `dad:handoff:b6cf68cb-992c-5efb-9714-ada561fb6958`
- Captured revision-6 learning-loop record:
  `dad:lesson:701bf269-77c2-5c73-bba7-bb1e038aca3a`

## Completed revision-6 work

1. Added a provider-neutral execution-control bridge that returns only
   `blocked` or inert `ready-manual` and has no launch method.
2. Derived attempts, stops, idempotency, lease, dispatch, authority, and budget
   state from existing durable Portfolio projections and fully verified receipt
   logs instead of caller assertions.
3. Bound canonical manifest/source bytes, exact approval identities and named
   approver, qualifications, job scope, outputs, evidence, budgets, heartbeat,
   repair/reissue, and partial-effect reconciliation.
4. Added explicit repository-local authority-attestation inputs with strict
   duplicate-key rejection and existing Ed25519 event verification.
5. Prevented circular attestation binding by signing exact Portfolio events and
   binding their stable approval IDs rather than attestation-file digests.
6. Prevented volatile packet drift by excluding `observed_at` only from the
   stable evidence digest while validating it as non-future metadata.
7. Added a real signed public-fold integration proof plus negative tests for
   canonical-manifest, source, authority, identity, scope, durability, budgets,
   conflicts, atomic children, and timestamp stability.
8. Decoupled intent-continuity host qualification from the campaign launch
   gate and updated the portable core/adapter candidate records.
9. Added the two authorized metadata-only branch dispositions; branch checks
   now report both rows valid without ref mutation.

## Qualification summary

- Static campaign, consistency, and mesh validators: pass.
- Focused execution-control suite: 82 passed and one optional-crypto skip.
- Real signed adapter/Portfolio-fold integration under the existing bundled
  crypto runtime: 1 passed.
- Five final portability nodes: pass; direct portability validation has no
  hard finding and one unrelated stale, non-routable archival warning.
- Relevant Ruff and diff checks: pass.
- Postcommit evidence correction: the precommit diff result above did not cover
  64 then-untracked files. `git diff-tree --check HEAD^ HEAD` exits 2 with 29
  historical findings on 18 paths. This supersedes only the diff-cleanliness
  assertion; no flagged historical line is changed in the correction lane.
- Same-HEAD full repository suite: 2209 passed, 1 skipped in 1530.37 seconds.
- Same-HEAD repository validator: 380 checked, zero errors, with one stale-branch
  warning.
- Actual prelaunch dry run: blocked by 47 missing exact authority/control
  bindings, with all seven effect counters zero.

## Exact next actions, in order

1. Complete the distinct checker receipt for the bounded six-path evidence-only
   correction and stop on any challenge or path drift.
2. Present the exact final six-path working-byte digest and stop before staging
   or commit for a separate atomic-commit decision.
3. Under any later exact commit authority, stage only the digest-bound six-path
   set, commit once, and run the authorized postcommit checks against the new
   commit delta. Do not normalize the 29 historical finding lines.
4. Decide explicitly which reviewed runtime supplies Ed25519 verification if a
   real manual dispatch trial is ever proposed.
5. Only after every non-human gate is green may a new H-010 request name the
   exact then-current revision and manifest SHA-256.
6. Only after that separate H-010 may J-100 be considered. `ready-manual` alone
   never launches or authorizes work.

## Resume protocol

1. Read the workspace lifecycle policy, Windows adapter, and active-worktree
   registry; validate the policy and confirm the existing owner/hold.
2. Confirm worktree path, branch, HEAD, dirty/untracked inventory, and the exact
   new authority. Do not create another worktree to escape this state.
3. Read `campaign.json`, `campaign.md`, this handoff, the risk review,
   `prelaunch-revision-6.json`, the frozen revision-6 independent review, both
   postcommit evidence-correction receipts, and the branch disposition registry.
4. Run DAD preflight and read its context pack.
5. Recompute manifest, mesh, controller, adapter, schema, portability,
   qualification, dry-run, and review digests.
6. Stop on any byte change, missing authority, stale evidence, ledger problem,
   privacy/security concern, or reviewer disagreement.

## Known blockers and caveats

- No revision-6 authorization, lease, dispatch approval, H-010, or J-100 launch
  authority exists.
- Atomic child execution binding is deliberately absent and fail-closed.
- The 100-file campaign packet is committed locally. The six-path postcommit
  evidence correction is not staged or committed, and no such operation is
  authorized in this lane.
- The standard project runtime lacks `cryptography`; the signed proof used an
  already present bundled runtime and did not install or enable anything.
- Observation time is non-binding; source, qualification, receipt, authority,
  and scope bytes remain binding and revalidated.
- The bridge contains no executor and proves control reachability, not business
  value.

No cleanup or destructive disposition is authorized. Preserve this worktree
and all evidence for the next exact decision.
