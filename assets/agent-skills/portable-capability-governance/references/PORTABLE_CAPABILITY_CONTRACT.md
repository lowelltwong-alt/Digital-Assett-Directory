# Portable Capability Contract

## Applicability

Apply to reusable AI-mediated skills, roles, packs, families, workflows,
routines, triggers, harnesses, prompts, libraries, knowledge interfaces,
evaluation packs, algorithm packs, and templates. Brainstorming, ordinary
answers, and one-off non-reusable work are not active artifacts.

## Disposition

- `portable_core`: provider-neutral contract and files; may reference adapters.
- `runtime_adapter`: exactly one core revision plus target capability predicate,
  interface, and compatibility evidence; cannot redefine core semantics.
- `provider_probe`: registered adapter plus verified receipt protocol; produces
  observations only.
- `environment_bound_exception`: reviewed human decision, exact scope, owner,
  expiry, containment, and migration; cannot claim portable status.

Use stable card and revision identities for every core and adapter. Keep
provider/model values out of normative core identities, selectors, routes, and
dependencies. Structurally marked provenance, documentation, comparisons,
migration notes, and negative fixtures may name them.

## Evidence And Gates

Require schema validity, exact dependencies, freshness, source authority,
privacy/effect/authority contracts, positive/negative/recovery evidence,
independent checking, safe rollback, and reverse-consumer coverage. Suspected
secrets are quarantined without disclosure; confirmed/high-confidence secrets
hard-fail. Unknown or expired exceptions fail at activation and release.

Runtime qualification is local to one role, core revision, adapter revision,
harness revision, corpus revision, and operating envelope. Use matched attempts,
predeclared margins, protected cohorts, evaluator-integrity checks, no-winner,
and human promotion. Never produce a global model leaderboard.

Rollback creates a new reviewed activation decision that moves an active-policy
pointer. It never edits history and never restores an ineligible route.

## Activation Trust

The policy registry cannot trust its own approval strings. A control-plane
activation, policy change, exception-verifier change, or gate weakening becomes
active only after an external protected-branch merge with the repository's
required deterministic validation and the human's exact merge authorization.
CODEOWNERS identifies the one-human owner; branch protection forbids direct or
force updates and requires the `validate` status. If that external trust anchor
is absent or unverifiable, the revision remains candidate/shadow evidence even
when its local digest is internally consistent.

## Lifecycle

`unknown_legacy -> declared -> schema_validated -> shadow_validated ->
pilot_validated -> reviewed_portable -> watch -> stale -> superseded -> retired`

Legacy status is time-bounded. A new finding, larger affected scope, expired
evidence/exception, or material governed-contract revision is
`new_or_worsened`. Postflight remains closable; activation, promotion, protected
release, and public/cross-repository delivery fail closed when their evidence is
missing.
