# Trusted Approval And Dry-Run Attempt Kernel Handoff

Date: 2026-07-13

Status: implemented and independently reviewed as a disabled shadow slice

Real execution status: NO-GO

## Outcome

DAD now has an exact-event approval-attestation verifier and a separate
source-zero-write attempt journal. The public execution API accepts raw signed
attestations only through the fixed repository trust path. Public folds and
loaders expose no verifier-result, raw-record, or bare-approval-ID injection.

The repository trust registry is intentionally empty, unanchored, and deny-all.
The Ed25519 backend could not be fetched and locked in the restricted environment,
so missing crypto returns `crypto_backend_unavailable` and clears all candidates.
Every execution projection and attempt record keeps `dispatch_allowed=false`,
`execution_performed=false`, and `source_write_count=0`.

No executor, worker launch, Git/source-repository mutation, scheduler activation,
private key, signing path, plugin installation, global setting, or external write
was added.

## Implemented surfaces

- `src/digital_asset_directory/portfolio_authority.py`
  - strict duplicate-key JSON parsing;
  - fixed printable signed fields and domain separation;
  - exact immutable-event digest binding;
  - canonical unpadded base64url key/signature decoding;
  - actor, domain, key, event-kind, registry digest, interval, and revocation checks;
  - immutable verifier result object used only behind private consumption paths;
  - missing backend and malformed trust fail closed.
- `src/digital_asset_directory/portfolio_execution.py`
  - guarded public deny-all fold;
  - fixed-path raw-attestation verification loader;
  - private compatibility/test fold only;
  - forced false executor and dispatch flags.
- `src/digital_asset_directory/portfolio_attempts.py`
  - separate hash-chained JSONL journal under DAD's resolved data root;
  - one lock covering validation, winner selection, tail sealing, and append;
  - strict duplicate-key and cross-event semantic validation;
  - exactly one selected dry-run claim per dispatch;
  - minimized-payload retry identity and command idempotency;
  - result records only for the selected claim;
  - complete valid unsealed tails are committed and sealed;
  - ambiguous/partial tails and interior corruption block append;
  - JSON and HTML source-zero-write projections.
- Three registered strict schemas and one empty trust registry.
- CLI routes for approval trust, execution, dispatch packets, attempt projection,
  claim/result recording, and deterministic race simulation.
- Navigation, table-of-contents, decision-contract, and regression-test updates.

## Independent review

The first return review found two must-fix defects:

1. a process-local seal was not an authenticity boundary while public folds accepted
   verifier-result injection;
2. retries compared raw caller input with minimized persisted payloads.

Both were fixed. The re-review confirmed:

- public verifier injection: fixed;
- minimized claim/result retry identity: fixed;
- naive-time rejection and `not_before <= issued_at < expires_at`: fixed;
- remaining must-fix findings: none;
- disabled shadow slice: GO;
- real execution: NO-GO.

The review also confirmed exact-event binding, missing-crypto deny-all behavior,
duplicate/corrupt journal rejection, complete-unsealed versus ambiguous-tail handling,
source-zero-write reconciliation downgrades, and the absence of execution or source
mutation.

## Validation evidence

Passed:

- 45 focused verifier, attempt, execution-control, authority-invariant, and CLI tests;
- 122 tests across the complete `test_portfolio_*.py` family;
- `tests/test_ai_navigation.py` and focused CLI/navigation tests;
- Python compile checks for all changed kernel and CLI modules;
- Ruff for the changed kernel, CLI, and tests;
- JSON parsing for the navigation registries, schema registry, trust registry, and
  three new schemas;
- `asset-dir roadmap check --no-update` equivalent, exit 0;
- `git diff --check`.

Repository-wide validation checked 845 surfaces and exited 1 on pre-existing stale
exception reports, missing generated exception ledgers/outboxes, and stale graph
manifests. The same unrelated failure appears in `test_repo_contracts_validate`.
No new Portfolio schema or navigation error was reported.

Not run or unavailable:

- real library-backed Ed25519 signature vectors, because the dependency could not be
  fetched or locked;
- cross-language canonical-byte vectors;
- multiprocess and OneDrive multi-host lock validation;
- real executor, source mutation, scheduler, worker, network, and private-key tests,
  because those capabilities do not exist and are outside this slice.

## Long-run optimization review

Repository validation took 63.97 seconds through the contract test and 107.4 seconds
inside a concurrent validation bundle. Static review found 45 candidate-path scans
representing nine unique scan requests, 97 report hashes representing 31 unique input
paths, and 14 methodology hashes representing two unique paths.

The approved candidate brief is Python-first and invocation-local:

1. plan and execute nine unique observations once, then compare all 45 report rows;
2. compile matcher terms and tokenize each path once;
3. memoize hashes, schemas, registries, and policy paths within one invocation only;
4. require exact 845-surface/error/warning/order parity and at least 25 percent median
   isolated-validator improvement across three serial trials.

Persistent caches, fail-fast release validation, immediate parallelism, and Rust are
rejected or deferred. Rust becomes eligible only after Python deduplication if the
stable read-only leaf still consumes at least ten seconds and twenty percent of total
validator time with a shadow-parity plan.

## Promotion blockers

Real execution remains blocked until all of the following receive separate approval
and evidence:

- an externally pinned and continuity-verified trust root;
- reviewed locked crypto dependency plus official and cross-implementation vectors;
- key lifecycle/provenance and registry-sequence continuity tests;
- a separate executor threat model and live source/Git enforcement boundary;
- multiprocess and multi-host locking or a different spend-once coordination system;
- an explicit human activation decision.

## Reusable lessons

- Security-sensitive Python objects are not authenticity capabilities. Remove public
  injection surfaces and keep the fixed raw-input verification path authoritative.
- Normalize/minimize payloads before identity, retry comparison, persistence, and
  returned output.
- Spend-once journals must seal complete valid tails but block ambiguous tails; ordinary
  truncate-on-recovery log policy can erase a winning claim.
- If a security dependency cannot be fetched and locked, revert its declaration and
  keep the optional feature explicitly tested as deny-all.

## Remaining risks

The trust registry is unanchored, the crypto backend is unavailable, external signer
canonicalization is unproven, and the lock is single-host. These are explicit blockers,
not hidden implementation debt. The main worktree also contains unrelated user changes
and stale generated evidence; this handoff does not claim those are clean or resolved.
