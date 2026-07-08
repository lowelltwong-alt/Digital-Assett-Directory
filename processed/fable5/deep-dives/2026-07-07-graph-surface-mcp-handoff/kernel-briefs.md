# Kernel Briefs For Fable

These are Codex starter kernels. Fable should accept, rewrite, split, or reject
them. The final answer should keep kernels compact and buildable.

## Kernel GS-1: Graph Surface Registry

Purpose: create one source-controlled catalog of DAD graph surfaces without
stuffing generated evidence into the source registry.

Files:

- add `registry/graph-surface-registry.json`
- add `schemas/graph-surface-registry.schema.json`
- update `registry/schema-registry.json`
- update navigation docs after the registry is real

Initial rows:

- `lesson_graph`
- `asset_knowledge_graph`
- `research_intake_graph`
- `repo_inventory_enrollment_graph`
- `transport_journal_graph`
- `mcp_resource_graph`

Required fields:

- `graph_id`
- `status`: `active`, `partial`, `planned`, `deprecated`
- `authority_boundary`
- `source_inputs`
- `generated_outputs`
- `manifest_path`
- `schema_path`
- `build_command`
- `validate_command`
- `mcp_resource_uri`
- `data_root_behavior`
- `human_gate_required`

Invariant: registry rows define surfaces and routes only. They do not certify
freshness, correctness, usefulness, authority, or human approval.

## Kernel GS-2: Shared Generated Graph Manifest

Purpose: make every generated graph manifest comparable without forcing all
graphs into one ontology.

Files:

- add `schemas/graph-manifest.schema.json`
- update existing lesson graph manifest generation to conform or wrap
- add builders for active graph surfaces only

Required manifest fields:

- `graph_id`
- `schema_version`
- `generated_at`
- `authority_boundary`
- `source_inputs`
- `input_hashes`
- `method_versions_used`
- `node_counts`
- `edge_counts`
- `coverage_report`
- `known_gaps`
- `staleness_policy`
- `data_root_mode`

Invariant: the graph stores no unrecoverable state. Migration is rebuild.

## Kernel GS-3: Data Root And Journal Placement

Purpose: keep the source repo clean after Local+Journal while preserving
reviewable graph evidence.

Rule:

- Source-controlled registry stays in Git.
- Generated graph manifests route through `data_path` when `DAD_DATA_ROOT` is
  initialized.
- Legacy fallback may read old `processed/**` paths until migration.
- `dad-journal` checkpoints graph manifests as data evidence, not source files.

Fable should decide whether checkpoint payloads are full snapshots, hash-only
records, compressed bundles, or threshold deltas.

## Kernel GS-4: Validation And Drift

Purpose: prevent stale graph manifests from creating false-green governance.

Validation rules:

- active graph surface row validates;
- active row must have a manifest path and schema;
- planned row may omit generated files but must say what will generate them;
- manifest input hashes are checked;
- edge types in generated graphs must exist in a registry;
- inference edges require method versions;
- stale behavior is per surface: `fail`, `warn`, or `ignore_planned`.

Fable should decide fail versus warn for each initial surface.

## Kernel GS-5: MCP Graph Resources

Purpose: expose graph context through MCP without direct API lock-in.

Initial read-only resources:

- `dad://graph/surfaces`
- `dad://graph/lesson/manifest`
- `dad://graph/asset/manifest`
- `dad://graph/research/manifest`
- `dad://graph/repo/manifest`
- `dad://graph/transport/manifest`
- `dad://graph/mcp/manifest`

Rules:

- resources are read-only;
- URIs validate against the graph surface registry;
- resource descriptions are advisory only;
- side effects stay behind DAD CLI lifecycle tools and human gates.

## Kernel GS-6: Minimal MCP Query Tools

Purpose: decide whether v1 MCP should expose query tools or only resources.

Codex bias: resources first, query tools second.

Candidate v1 tools if Fable approves:

- `graph_surface_status(graph_id?)`
- `graph_manifest_check(graph_id)`
- `graph_neighbors(node_id, graph_id, max_depth=1)`
- `graph_paths(source_id, target_id, graph_id, max_depth=3)`
- `graph_explain_edge(edge_id, graph_id)`

Forbidden in v1:

- graph mutation;
- promotion;
- enrollment updates;
- protected repo writes;
- cloud mirroring;
- direct vendor API calls as the primary route.

## Kernel GS-7: Anti-False-Authority

Purpose: stop graph rank, centrality, match counts, and generated edges from
becoming accidental truth.

Required output labels:

- candidate evidence;
- generated view;
- not source truth;
- not human approval;
- not canonical preference;
- not proof of value.

Forbidden edge claims:

- `approved_by_human` unless backed by explicit human gate evidence;
- `source_of_truth_for` unless sourced from a reviewed registry;
- `must_write_to` or any edge implying mutation authority;
- `safe_to_publish` without release gate evidence;
- `best`, `winner`, or `canonical` from graph score alone.

## Kernel GS-8: Build Order

Fable must adjust this order if the parallel transport completion work changes
the data-root surface list or downstream rollout dependency chain.

1. Merge/reconcile transport data-plane surface definitions.
2. Add schemas and source registry.
3. Register active/planned graph surfaces.
4. Add validation for registry only.
5. Normalize one generated manifest, probably lesson graph.
6. Add data-root routing for generated manifests.
7. Add stale-manifest validation.
8. Register MCP resource URIs.
9. Add synthetic mini-hub tests.
10. Implement read-only local MCP resources.
11. Add query tools only after resource behavior is stable.

Stop before implementing cloud relay, direct APIs, graph mutation, or downstream
repo writes.

## Kernel GS-9: Surface Version Tracking

Purpose: let DAD know which repo has which internal contract surfaces installed,
so future upgrades can target only stale or missing repos.

Candidate tracked versions:

- `agent_runtime_policy.surface_version`
- `transport.surface_version`
- `graph_surface.surface_version`
- `mcp_resource_surface.surface_version`
- `journal.surface_version`
- `enrollment_contract.schema_version`
- managed block revision ids for `AGENTS.md`, `CLAUDE.md`, and mail docs

Likely files:

- `schemas/repo-enrollment-contract.schema.json`
- `templates/downstream/DAD_INTEGRATION.template.json`
- `src/digital_asset_directory/enrollment.py`
- `src/digital_asset_directory/transport_upgrade.py`
- future `registry/graph-surface-registry.json`

Invariant: version rows are detection and planning evidence only. They do not
silently mutate downstream repos.

Fable should decide whether this belongs in the graph surface registry, the
enrollment contract, a separate repo-surface ledger, or all three with distinct
roles.

## Kernel GS-10: Synthetic Mini-Hub Tests

Purpose: prove the new graph/MCP surface model works before making it the
default for downstream repos.

Synthetic fixtures should include:

- one repo with current transport, graph, MCP, and enrollment versions;
- one repo missing graph surface manifest;
- one repo with stale generated manifest hashes;
- one protected repo that must stay central-only;
- one repo with mailbox but missing contract;
- one repo with generated graph outputs only under initialized `DAD_DATA_ROOT`;
- one hostile or malformed MCP resource URI;
- one graph rank/centrality output that must remain candidate-only;
- one journal checkpoint containing graph manifest evidence;
- one downstream update wave that selects only reviewed non-protected repos.

Required assertions:

- stale active manifests warn or fail according to the registry policy;
- planned surfaces do not require generated files;
- MCP resource URIs match registry rows;
- no direct API or vendor-specific authority is required;
- generated data lands under initialized data root;
- source repo stays clean after daemon/journal/graph manifest operations;
- downstream update plans are review-only until human approval.

Fable should reduce or refine this test set, but should not remove the protected
repo, stale manifest, data-root, MCP URI, and no-lock-in controls.

## Kernel GS-12: End-To-End Acceptance Tests

Purpose: prove DAD can run the new graph/MCP surface model locally from a clean
source repo and an initialized data root.

Acceptance scenario:

1. Create a synthetic hub with registered graph surfaces and three synthetic
   enrolled repos.
2. Initialize `DAD_DATA_ROOT`.
3. Build graph manifests.
4. Run read-only MCP resource listing over the manifests.
5. Run `transport readiness`.
6. Run `journal checkpoint --plan-only`.
7. Generate a downstream update plan from reviewed non-protected rows.
8. Confirm source repo `git status` stays clean except intentional source edits.

Assertions:

- generated graph manifests land under the active data root;
- journal checkpoint plan includes graph manifests as data-only evidence;
- MCP resources expose manifests read-only;
- no direct API or vendor SDK is required;
- protected repo rows are skipped;
- stale/missing graph manifests are reported according to policy;
- version report identifies current, stale, missing, and protected repos;
- every side-effecting command is plan-only unless explicit approval is present.

Validation commands should include both normal and initialized-data-root suites:

- `python -m pytest tests/test_graph_surfaces.py`
- `python -m pytest tests/test_mcp_resources.py`
- `python -m pytest tests/test_transport.py tests/test_journal.py`
- `DAD_DATA_ROOT=<initialized temp root> python -m pytest tests/test_graph_surfaces.py tests/test_mcp_resources.py`
- `python -m digital_asset_directory.cli validate --hub .`

## Kernel GS-13: Red-Team And Premortem Fixes

Purpose: make failure modes first-class before Codex implements the default
graph/MCP path.

Red-team matrix:

| Attack or failure | Expected guardrail |
|---|---|
| Graph centrality says asset is "best" | Output labels forbid authority; tests assert no canonical/winner claims from rank alone. |
| Stale manifest still validates | Hash check fails or warns per surface policy; tests mutate one input after manifest build. |
| MCP URI escapes approved surfaces | URI parser rejects unknown schemes, traversal, absolute paths, and unregistered graph ids. |
| Direct vendor API becomes default path | Tests scan docs/templates/code for direct API default language; MCP-first policy remains required. |
| Protected repo gets update row | Queue selection skips protected rows and records reason. |
| DAD_DATA_ROOT split-state hides generated files | Initialized-root tests assert no hub-relative generated manifest writes. |
| Journal checkpoint misses graph manifests | Checkpoint test includes graph manifest files in data-only plan. |
| Version detector says stale repo is current | Synthetic repo with old surface version must report `update_available`. |
| Hostile graph manifest payload is trusted | Schema validation/quarantine path rejects or marks invalid; no trust side channel. |
| Synthetic tests pass but real route missing | Validation asserts each registry row has a real command, schema, or planned status reason. |

Premortem:

- Future agents treat MCP resource descriptions as policy.
- Operators merge graph surfaces before final transport data-plane path registry.
- Repo versioning sprawls across enrollment, graph registry, and transport status
  with no single query.
- Generated graph manifests return to Git after data-root activation.
- Downstream rollout starts before synthetic protected-repo and stale-version
  negative controls pass.

Required fixes:

- add explicit authority boundary to every graph manifest and MCP resource;
- require `data_path` for generated manifest writes;
- add one `asset-dir graph surfaces status` or equivalent status command;
- add stale-version synthetic fixtures;
- keep downstream rollout plan-only until reviewed approval id exists;
- require postflight to record whether red-team/premortem checks ran.

## Kernel GS-11: Parallel Transport Merge Adjustment

Purpose: prevent graph/MCP implementation from landing on stale transport
assumptions while `codex/transport-kernel-followup` is still expanding the
data-plane surface registry.

Fable should compare PR #17 with the follow-up worktree and answer:

- Which `DATA_PLANE_PATHS` must graph manifests use?
- Should generated graph manifests wait until proposal, workflow-part, raw
  research, exception-capture, and report writers are fully merged?
- Does journal checkpoint scope need a graph-manifest-specific test?
- Does transport readiness need to include graph manifest readiness?
- Does repo-status need to report graph/MCP surface versions alongside
  transport versions?

Output a corrected merge/build order for Codex if the answer changes GS-8.
