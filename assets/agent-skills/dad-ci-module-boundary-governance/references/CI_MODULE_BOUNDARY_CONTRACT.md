# CI Module Boundary Contract

The manifest declares ownership and suite-selection evidence; it does not prove
that undeclared semantic dependencies do not exist.

- Path edge types: 'code', 'contract', 'authoritative_input'.
- Module graph edge: 'direct_dependent', directed upstream to downstream and
  limited by its declared triggering path-edge types.
- Lanes: 'ci_contract', 'module', 'integration', 'release',
  'scheduled_full_regression'.
- Unknown or moved-outside-ownership paths fail the contract lane, not every
  module suite.
- Generated outputs trigger no module unless an authoritative input or reviewed
  dependency declaration changes.
- Integration and release scopes must list modules and dependency edge IDs.
- Any scope change relative to the base manifest needs a current reviewed
  exception bound to the exact diagnostic scope until the new baseline is
  approved. Future-dated reviews and code-wide exception suppression fail.
- Provider workflow configuration is an adapter and cannot broaden the
  manifest's normative selection.
- A required selector declares an exact suite-to-job map and its aggregator
  must depend on every mapped job. Module workflows are reusable calls; they do
  not own parallel PR/push path filters.
- CI must prove the base commit exists before comparison. A missing base
  manifest is allowed only for a confirmed first adoption in an available base
  commit (or an initial root commit).
