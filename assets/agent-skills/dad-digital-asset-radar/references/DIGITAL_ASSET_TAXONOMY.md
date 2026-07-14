# Extensible Digital Asset Facets

Taxonomy version ID: `dad.digital_asset_taxonomy.v0_1`.

Classify with independent, multi-label facets. Do not force one hierarchy or
infer missing values. Use `unknown` when evidence is unavailable and
`unclassified` when evidence exists but no reviewed value fits. Record the
taxonomy revision, evidence, confidence, and any proposed new value.

- `form`: code, library, service, schema, manifest, dataset, model, prompt,
  skill, agent role, workflow, algorithm, test, harness, template, document,
  research pointer, policy, taxonomy, or other.
- `capability_domain`: problems solved and domains served; allow multiple.
- `composition`: atomic, component, composite, bundle, adapter, wrapper,
  projection, or family.
- `execution_dataflow_role`: source, transformer, validator, orchestrator,
  router, index, projection, query, interface, sink, observer, or control.
- `lifecycle_maturity`: idea, candidate, experimental, validated, reviewed,
  active, deprecated, superseded, retired, or archived.
- `authority_trust`: observation, candidate, reviewed, authoritative-for-scope,
  external-untrusted, disputed, or unknown.
- `sensitivity_release`: public, internal, restricted, private, unknown;
  releasable, gated, embargoed, or prohibited.
- `provenance_license`: local, imported, derived, generated, mixed, unknown;
  license identity and verification state are separate values.
- `runtime_platform`: language, runtime, operating system, host, protocol,
  deployment, hardware, and portability claims; allow multiple.
- `freshness_maintenance`: current, stale, unsupported, abandoned, unknown;
  maintainer, review date, source digest, and rebuild trigger.
- `reuse_adoption`: reusable, target-specific, adapted, adopted, trialed,
  rejected, harmful, or unknown, with target and evidence.
- `typed_relationships`: revision_of, variant_of, derived_from, depends_on,
  validates, supersedes, replaces, wraps, adapts, projects, exposes, combines,
  complements, conflicts_with, duplicate_candidate_of, or used_by.

Unknown values remain visible in coverage and routing. `unknown` is not a weak
match, and `unclassified` is not `other`. New facet values are candidate
taxonomy revisions requiring evidence, compatibility review, and independent
audit. Relationships never prove identity, value, trust, or adoption.
