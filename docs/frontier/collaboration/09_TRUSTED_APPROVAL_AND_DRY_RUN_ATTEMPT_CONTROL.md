# Trusted Approval And Dry-Run Attempt Control

Status: candidate kernel contract; no executor or activation authority

Date: 2026-07-13

Risk tier: high

## Decision

DAD will verify Portfolio OS approval attestations with Ed25519 public keys over a
canonical message that names one complete immutable authority event. The repository
trust registry is empty and deny-all until a human-reviewed key record is added.
Private keys, signing, key generation, dispatch, Git mutation, agent launch, network
writes, and scheduler activation remain outside this slice.

Dry-run execution attempts use a separate append-only journal. Its only permitted
claim mode is `source_zero_write`; every record states that execution was not
performed and that source writes equal zero. A winning claim means only that the
candidate won the local simulation lock. It is never approval, execution authority,
or evidence that a real outcome occurred.

## Blast radius

- Portfolio execution fold and read-only CLI projections.
- Three strict schemas and the schema registry.
- One empty approval trust registry.
- A new non-authoritative local attempt journal under DAD's resolved data root.
- Portfolio execution, attempt, schema, CLI, and navigation tests.
- AI navigation and the Portfolio OS architecture handoff.

No source repository, external task system, connector, scheduler, or worker runtime
is in scope.

## Options considered

1. Keep caller-supplied typed records. Rejected: a caller can label an unverified
   dictionary as verified.
2. Shared-secret HMAC. Rejected: verification would require distributing signing
   authority to every verifier and would encourage secrets in local configuration.
3. Asymmetric signatures over approval IDs. Rejected: a valid signature could be
   replayed against a changed event or scope.
4. Ed25519 signatures over a canonical complete-event digest. Selected: verification
   uses public material, exact scope binding, short validity windows, explicit domain,
   actor, key, nonce, and event identity, with deny-all defaults.
5. Defer verification entirely. Retained as the runtime default whenever the trust
   registry, dependency, attestation, event match, or clock checks are not valid.

## Signed contract

The signed message contains only fixed, printable fields and excludes the signature:

- schema and authority-context versions;
- attestation ID and unique nonce;
- approval ID, authority domain, and approver ID;
- event ID, event kind, and digest of the full immutable event envelope;
- key ID derived from the SHA-256 fingerprint of the raw Ed25519 public key;
- issued-at, not-before, and expires-at timestamps.

Verification additionally requires the approval ID and approver to match the exact
ledger event, the registry and key to be reviewed/current, the event kind and actor
to be allowed by that key, the signature to be valid, and the approval ID not to be
reused for another authority event.

## Self red-team and premortem

- Canonicalization drift could make another implementation sign different bytes.
  Control: fixed field set, printable strings, sorted compact JSON, versioned context,
  and published test vectors before any external signer is built.
- A caller could launder dictionaries through a parameter named `verified`.
  Control: public folds accept no verifier-result, raw-record, or bare-ID injection;
  only the fixed-path raw-attestation loader may supply a private verified bundle.
- A stolen or stale attestation could be replayed. Control: bind it to one event,
  key, actor, domain, nonce, and a maximum 24-hour interval; reject reused approval
  identities and currently revoked or expired keys.
- Clock skew could produce false authorization. Control: timezone-required UTC
  parsing, a bounded five-minute future tolerance, and half-open validity windows.
- A dry-run winner could later be mistaken for a real worker outcome. Control: a
  separate schema and ledger, constant source-zero-write mode, explicit false
  execution flag, zero source-write count, and reconciliation status that remains
  `reconciliation_dry_run_only`.
- Concurrent candidates could both win after a crash or OneDrive lock anomaly.
  Control: one owned lock around repair, validation, winner selection, append, flush,
  and fsync; hash chaining; complete unsealed-tail recovery; ambiguous-tail blocking;
  and concurrency tests. OneDrive multi-host semantics remain an activation blocker.

Six-month failure is most likely if an external signer implements a different byte
contract, operators add keys without independent review, or a future executor treats
candidate projections as permission. The executor must therefore remain a separate
future gate with its own threat model and real filesystem/Git enforcement.

## Invariants

- Missing, empty, candidate, malformed, expired, revoked, wrong-domain, wrong-actor,
  wrong-event, wrong-digest, reused-ID, or invalid-signature input denies authority.
- A valid attestation authorizes only its exact ledger event during the intersection
  of attestation, key, lease, and dispatch validity windows.
- Trust-registry edits never create signing capability.
- Exactly one valid claim per dispatch can have `won=true` in the attempt journal.
- Retried commands are idempotent; conflicting command reuse fails closed.
- Interior corruption and ambiguous partial tails block append; complete unsealed tails are sealed before append.
- Attempt journal content never sets `dispatch_allowed`, `authorization_valid`, or a
  real reconciliation outcome to true.

## Validation and promotion gate

Required evidence before this candidate can be described as implemented:

- strict schema rejection tests;
- official Ed25519 test-vector or library-backed signature tests;
- event/digest/actor/domain/key/expiry/revocation/replay negative tests;
- deterministic and concurrent single-winner tests;
- torn-tail, corruption, retry, and result-recording tests;
- CLI deny-all and dry-run-only integration tests;
- existing Portfolio execution and authority-invariant regression tests;
- Ruff, schema validation, navigation validation, roadmap check, and diff check.

Promotion to a real executor is explicitly excluded. Stop and request a new human
decision if implementation needs a private key, persistent global setting, external
write, package/plugin installation beyond the reviewed Python dependency, scheduler,
worker launch, Git mutation, or weaker invariant.

## Implementation outcome

- The guarded public execution facade accepts no verifier-result injection; raw signed
  attestations are verified only through the fixed repository trust path, and raw
  dictionaries and bare approval IDs are never authority.
- The exact-event verifier, empty deny-all trust registry, three schemas, attempt
  journal, read-only CLI projections, and navigation routes are implemented.
- The execution fold remains a shadow projection and every dispatch flag remains false.
- The selected Ed25519 library could not be fetched or locked because package-network
  access is unavailable in this environment. The optional backend therefore fails
  closed with `crypto_backend_unavailable`; no dependency declaration was left unlocked.
- Forty-five focused verifier, journal, execution-control, authority-invariant, and CLI
  tests passed. The full 122-test Portfolio OS family also passed; broader validation
  evidence is recorded in the implementation handoff.
- Real execution remains NO-GO until a trust registry is externally anchored, the
  crypto backend and cross-implementation vectors pass, and a separate executor threat
  model and source-mutation enforcement gate are approved.

## Rollback

Remove the verifier, trust registry, attempt module, schemas, CLI projections, and
their navigation rows. The existing Portfolio execution kernel then returns to its
deny-all typed-attestation placeholder. Existing authority ledger events remain
append-only and unchanged.
