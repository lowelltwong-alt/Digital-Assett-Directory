---
name: dad-manifest-graph-engineering
description: Design, build, evolve, and independently validate governed manifests, registries, typed graphs, dependency and data-flow projections, semantic fingerprints, reverse blast-radius maps, and read-only query or MCP surfaces. Use for machine-readable structured artifacts, schema or ontology changes, generated graph builders, plan-to-execution agent meshes, or repository-wide dependency and freshness audits.
---

# DAD Manifest Graph Engineering

1. Establish mission, source authority, scope, non-goals, sensitivity, and the
   artifact that remains authoritative. Treat every generated relation as a
   candidate until its stated review gate passes.
2. Inventory existing registries, schemas, builders, identifiers, fingerprints,
   queries, consumers, and tests. Use deterministic parsing before model work.
3. Read `references/AGENT_MESH_MANIFEST_CONTRACT.md`, start from
   `assets/agent-mesh-manifest.template.json`, and validate against
   `references/agent-mesh-manifest.schema.json` with
   `scripts/validate_agent_mesh_manifest.py`. During execution, pass `--prior`,
   reconcile every role, and append a revision for material decomposition drift.
4. Route bounded reasoning with `subagents.yaml`. Use one writer, non-overlapping
   scopes, delegation depth one, and a distinct independent checker. A role may
   not approve its own artifact or grade.
5. Separate stable identity from revision identity and display labels. Define
   address grammar, ontology terms, typed nodes and edges, provenance,
   confidence, unknowns, and authority before implementing a builder.
6. Define strict schemas and compatibility policy, then build deterministic,
   reproducible projections. Preserve raw observations; never ingest secrets,
   client payloads, raw conversations, or private source rows.
7. Bind outputs to semantic fingerprints, source coverage, freshness states,
   versioning, and reverse consumer dependencies. Fail closed on missing,
   invalid, stale-authority, unsupported-version, or ambiguous-source evidence.
8. Expose queries or MCP projections as read-only views with bounded output,
   privacy filters, explicit candidate status, and no execution authority.
9. Validate schema, deterministic replay, migration, negative cases, stale and
   partial input, cycles, identity collisions, privacy, and reverse blast radius.
   Have the checker red-team false authority and missing consumers.
10. Postflight the mesh reconciliation and grade decomposition quality using
    independent evidence. Treat self-grades as calibration evidence only.

Return source coverage, authority map, identities, typed relations, schemas,
builder and migration plan, fingerprints, freshness policy, reverse blast
radius, query boundary, mesh revisions, validation evidence, unknowns, and
human decisions.
