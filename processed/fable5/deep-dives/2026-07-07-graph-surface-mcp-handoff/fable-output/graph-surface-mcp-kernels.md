# Fable 5: Graph Surfaces, Generated Manifests, MCP Boundary — Kernels

Status: candidate design output (Fable 5, 2026-07-07). Review input only; no
human gates approved; no roadmap implementation marked complete. NOTE: this
packet's README/kernel-briefs/evidence-index/expected-output.schema.json and
`docs/MCP_FIRST_INTEGRATION_POLICY.md` were referenced by the prompt but DO NOT
EXIST in main or the transport worktree — Fable created this packet directory.
Finding F1 below. Structured markdown used in place of the absent schema.

Baseline read: `docs/KNOWLEDGE_GRAPH_MODEL.md` (worktree), phase-13 local
acceptance evidence (M0–M2 implemented, human gates pending), transport
worktree code (daemon/journal/transport_readiness/transport_upgrade present).

---

## Part 1 — Decision table (the 16 questions)

| # | Question | Decision |
|---|---|---|
| 1 | What counts as a graph surface? | A NAMED, REGISTERED, generated projection: (surface_id, purpose, ontology_id, input sources, builder command, manifest path, graph path, schema ref, rebuild command). If it is rebuilt from raw+registries it is a surface; if rows are human-reviewed it is a REGISTRY (authority) and never a "generated surface." Current surfaces: lesson-graph, inference overlay, research intake-graph, exception clusters (future), repo-status view (future). Navigation registry is NOT a surface (it is reviewed authority). Transport audit is a report, not a graph surface. |
| 2 | One ontology or several? | Several BOUNDED ontologies with shared guardrails (DDD bounded contexts): knowledge (assets/lessons/patterns), research-intake, exceptions, operations (repo/transport/enrollment views). Shared guardrails: node-id scheme, edge_class join/inference split, review_status, method_version-required-on-inference, registered-edge-types-only. Do NOT merge into one universal ontology — edge semantics differ per context and a universal graph invites universal (false) queries. |
| 3 | Navigation vs knowledge hard boundary | Navigation = reviewed routing rows (front door/TOC/nav registry), changes via PR, answers "where do I go", authority rank 3. Knowledge = generated candidate evidence, answers "what may relate", authority rank 6. Hard rules: no generated process may write navigation rows; no knowledge edge may auto-create a route; context packs may CITE knowledge edges only with review_status attached. |
| 4 | Stale manifests: block vs warn | Distinguish STALE (inputs newer than build — expected between daemon cycles) from INCONSISTENT (methodology/edge-registry hash mismatch, or schema-invalid manifest — corruption). Stale ⇒ WARN (daemon rebuilds); inconsistent ⇒ BLOCK. Exception: a generated report claiming freshness while consuming a stale surface in the same validate run ⇒ BLOCK that report, not the surface. This fixes the recurring validate-red-because-a-lesson-was-added pain (observed twice this week). |
| 5 | Manifests in Git after DAD_DATA_ROOT? | NO. Graphs + manifests live under DAD_DATA_ROOT and checkpoint to dad-journal. Git keeps only the surface REGISTRY + schemas (reviewed). No status stubs in git — `asset-dir graph status` and the daily review queue are the visibility surface. |
| 6 | Journal checkpoint form | Manifests: full JSON every checkpoint (small). Graph bodies: gzip snapshot + sha256 in a checkpoint index line. NO deltas — surfaces are rebuildable; raw records are the lineage; journal is backup/transport, not history. Skip body upload when hash unchanged since last checkpoint. |
| 7 | MCP first: manifests, tools, or both? | Both, minimal: read-only RESOURCES for manifests/registries/reports (pointer-sized) + exactly 4 read-only TOOLS (get_node, neighbors, search_nodes, surface_status). Resources-only is token-hostile (clients parse whole graphs); tools-only hides provenance. Graph BODIES are not resources (too big) — reachable only via tools with limits. |
| 8 | Prevent rank/centrality fake authority | (a) MCP responses never include computed centrality/rank/score fields — only stored evidence fields (matched_terms, counts with N). (b) Every tool response embeds edge_class, review_status, method_version, and the authority_boundary string. (c) No "top/best assets" tool in v1; search sorts by node_id or declared field, never by score. (d) Existing law stands: no percentages under N=10 reviewed. |
| 9 | Forbidden edge types/claims | Forbidden as generated edges (imply truth/quality/approval/authority): `approved_by`, `verified`, `trusted`, `production_ready`, `better_than`, `recommended`, `canonical`, `authorized_by`, generated `depends_on` (declared-only, existing law), `replaces` unless derived from reviewed supersedes, bare `causes` (only `caused_by` HYPOTHESIS inside the exception ontology with method_version). Enforcement: edge types must exist in graph-edge-registry; validators reject unregistered types (wired) — extend registry with an explicit `forbidden_edge_claims` list so the rejection is self-documenting. |
| 10 | Repo/enrollment/transport state as graph? | Operational records stay source of truth (config, policies, audits, contracts). A DERIVED `repo-status` graph surface projects them for query. Never model state primarily as a graph — you cannot gate on a projection. |
| 11 | Minimal MCP query API v1 | `dad_graph_surface_status()` → manifests+freshness; `dad_graph_get_node(surface_id, node_id)`; `dad_graph_neighbors(surface_id, node_id, edge_type?, direction?, limit≤50)`; `dad_graph_search_nodes(surface_id, terms, node_type?, limit≤25)`. Read-only, local stdio, no write tools, no cross-surface joins in v1. |
| 12 | MCP resource URI taxonomy | Extend the existing `dad://` scheme: `dad://registry/{registry_id}`, `dad://surface/{surface_id}/manifest`, `dad://report/{report_id}`, `dad://kernel/aios-governance`, `dad://packet/{fable_packet_id}`. Rules: URIs never contain local paths; server resolves via surface registry; optional pin `?at={content_hash}`; unknown URI ⇒ error, never fuzzy match. |
| 13 | Does Codex's plan order change? | YES — see Part 3. Surface registry + manifest schema + stale policy land FIRST (path-independent); everything that writes graph/manifest files WAITS for the transport M0a merge and must consume `transport.data_path()` (never path literals). MCP server lands after journal checkpointing so resources can cite checkpoint hashes. |
| 14 | Surface-contract versions to track | Per-repo in enrollment contract: `transport.surface_version` (1.0.0, exists), `events.surface_version` (0.4.0 capture generations exist), plus NEW `graph.surface_version`, `mcp.surface_version`, `journal.surface_version`, and existing `enrollment.version`. Central: generalize the transport-detector pattern into one `surface-status` report. Law: ABSENCE = legacy, never current (fail-closed, same as capture surfaces). |
| 15 | Required synthetic tests | Kernel K9/K10 below — mini-hub build determinism, stale-vs-inconsistent discrimination, URI round-trip, hostile payloads, protected-repo negative control, data-root split-state, version detector, no-lock-in control, real-wiring canary. |
| 16 | Safe rollout sequence | Synthetic green → hub self-serves MCP locally (stdio) → ONE pilot non-protected repo reads MCP in preflight for a week → enrollment update wave bumps surface versions per queue → protected repos LAST and central-only. Any stage red ⇒ stop, exception event, no advance. |

---

## Part 2 — Kernels

Shared invariants (apply to every kernel; do not restate per kernel): generated
outputs are candidate evidence; rebuildable from raw+registries; deterministic
(sorted, stable ids, generated_at only at top level); no raw bodies/secrets;
protected repos never written; human gates untouched; style law =
`graph_inference.py`.

### K1 — Graph surface registry
Purpose: make "graph surface" a reviewed, closed vocabulary.
Files: `registry/graph-surface-registry.json` (+ `schemas/graph-surface-registry.schema.json`, schema-registry row).
Row fields: surface_id, ontology_id (knowledge|research_intake|exceptions|operations), purpose, inputs[] (logical data_path names + registry paths), builder_command, manifest_logical_path, graph_logical_path, schema_ref, rebuild_command, consumed_by[], review_status.
Seed rows: lesson-graph, graph-inference-overlay, research-intake-graph; placeholders (status: planned) for exception-clusters, repo-status.
Invariants: surface_id immutable; inputs use ONLY logical names from `transport.DATA_PLANE_PATHS` or registry paths; builder must exist as a CLI command.
Tests: `tests/test_graph_surface_registry.py::test_registry_validates_and_builders_exist`, `::test_inputs_are_logical_names_only`.
Validate: `PYTHONPATH=src python -m digital_asset_directory.cli validate`.
Not yet: no auto-generation of registry rows; no operations-surface builder.
Human gate: registry review = normal PR review.

### K2 — Shared generated graph-manifest schema
Purpose: one manifest contract for ALL surfaces (today lesson-graph has its own shape).
Files: `schemas/graph-surface-manifest.schema.json`; migrate lesson-graph manifest writer in `learning.py` to it; inference report adopts it.
Required fields: schema_version, surface_id, ontology_id, generated_at, builder_version, input_hashes{logical_name: sha256}, methodology_hashes{}, edge_registry_hash, counts{nodes_by_type, edges_by_type}, coverage{}, graph_content_hash, freshness{state: fresh|stale|inconsistent, computed_at}, authority_boundary.
Invariants: `graph_content_hash` = sha256 of the sorted graph JSON (byte-stable); manifests carry hashes, never inline graph content.
Tests: `tests/test_graph_manifest_schema.py::test_all_surface_manifests_validate`, `::test_content_hash_matches_graph_file`.
Not yet: don't force exception/ops surfaces onto it before they exist.
Human gate: none beyond PR.

### K3 — DAD_DATA_ROOT + dad-journal placement
Purpose: graphs/manifests live in the data plane, never re-enter git.
Files: builders write via `transport.data_path(hub, "learning")` (already true for lesson-graph/inference on the worktree — VERIFY, don't rewrite); `journal.py` gains surface checkpointing.
Journal layout: `surfaces/{surface_id}/manifest.json` (full) + `surfaces/{surface_id}/graph.json.gz` + `surfaces/checkpoint-index.jsonl` ({surface_id, graph_content_hash, checkpointed_at}); skip body when hash unchanged.
Invariants: after data-root activation, `git ls-files processed/learning` = 0 in the hub; journal writes only in checkpoint step; gunzip(graph.json.gz) hash == manifest.graph_content_hash.
Tests: `tests/test_journal_surfaces.py::test_checkpoint_skips_unchanged_bodies`, `::test_roundtrip_hash_integrity`, extend `tests/test_data_root_generated_writers.py` (worktree) with the two graph writers.
Not yet: no real journal repo creation/push (human gate phase-13-journal-repo-approved); plan/status modes only.
Human gate: journal repo + first push = existing phase-13 gates.

### K4 — Validation & stale-manifest policy
Purpose: end stale-false-red and stale-false-green with one rule.
Files: `validation.py` (replace the current hard lesson-graph staleness error), small helper `graph_freshness.py` or inside transport module.
Rule: for each registered surface — schema-invalid manifest ⇒ BLOCK; methodology/edge-registry hash mismatch ⇒ BLOCK (inconsistent); input_hashes differ from current inputs ⇒ WARN `stale` (listed in daily review queue; daemon rebuilds); a downstream generated report whose manifest claims `fresh` while consuming a `stale` surface ⇒ BLOCK the report.
Tests: `tests/test_graph_freshness_policy.py::test_new_lesson_warns_not_blocks`, `::test_methodology_hash_mismatch_blocks`, `::test_fresh_claim_over_stale_input_blocks`.
Not yet: no auto-rebuild inside validate (validate stays read-only).
Human gate: none.

### K5 — MCP resource URIs
Purpose: stable discovery without exposing paths or bodies.
Files: `src/digital_asset_directory/mcp_server.py` (stdio, stdlib+mcp lib), `docs/MCP_FIRST_INTEGRATION_POLICY.md` (CREATE — currently a ghost reference).
Resources: `dad://registry/{id}` (reviewed registries, read-only), `dad://surface/{id}/manifest`, `dad://report/{id}` (allowlisted reports), `dad://kernel/aios-governance`, `dad://packet/{id}` (fable packet READMEs).
Invariants: URI→file mapping only via surface/schema/nav registries (no path math from URI segments — rejects traversal by construction); unknown URI ⇒ explicit error; every resource response prepends the authority_boundary line; graph bodies are NOT resources.
Tests: `tests/test_mcp_server.py::test_uri_resolution_via_registry_only`, `::test_traversal_and_unknown_uris_rejected`, `::test_every_response_carries_authority_boundary`.
Not yet: no write tools; no remote transport (stdio only); no vendor-specific extensions.
Human gate: none for local stdio; any network exposure = new human gate.

### K6 — Minimal MCP graph query tools (v1: yes, 4 tools)
Purpose: token-cheap queries with provenance attached.
Files: `mcp_server.py` (same module).
Tools: surface_status / get_node / neighbors (limit≤50) / search_nodes (limit≤25) per decision #11. Responses embed: review_status, edge_class, method_version (edges), freshness.state of the surface, authority_boundary.
Invariants: read-only; limits enforced server-side; no score/rank/centrality fields ever; stale surface ⇒ responses tagged `freshness: stale` (still served — staleness is visible, not hidden).
Tests: `tests/test_mcp_server.py::test_tools_readonly_and_limited`, `::test_no_rank_or_score_fields_in_responses`, `::test_stale_surface_tagged_not_hidden`.
Not yet: cross-surface joins, mutation tools, subscription/streaming.
Human gate: none (local).

### K7 — Anti-false-authority enforcement
Purpose: make decision #8/#9 mechanical, not cultural.
Files: `registry/graph-edge-registry.json` gains `forbidden_edge_claims[]` (list from decision #9 with reasons); `validation.py` rejects any surface containing a forbidden or unregistered edge type; `mcp_server.py` response-shape test guards (K6).
Invariants: forbidden list is reviewed vocabulary; error message names the law ("edges never imply approval/truth/quality/authority").
Tests: `tests/test_graph_freshness_policy.py::test_forbidden_edge_type_blocks_validation`.
Not yet: nothing — this is small and lands with K1/K4.
Human gate: PR review of the forbidden list.

### K8 — Surface version tracking & repo status
Purpose: know which repos run which graph/transport/journal/MCP/enrollment surfaces; absence = legacy.
Files: generalize `transport.audit_repo_transport` detector pattern into `surface_status.py`; extend `templates/downstream/DAD_INTEGRATION.template.json` + contract schema with `graph.surface_version`, `mcp.surface_version`, `journal.surface_version`; central report `surface_status.json` + upgrade queue rows (dedupe key = repo+surface+expected_version, same as transport).
Invariants: read-only over reviewed repos; absence classifies legacy (fail-closed); protected repos central-only rows.
Tests: `tests/test_surface_status.py::test_absent_contract_is_legacy_never_current`, `::test_queue_dedupes_per_surface_version`.
Not yet: no delivery of upgrade notices (rides existing enrollment wave gates).
Human gate: upgrade waves = existing phase-12/13 gates.

### K9 — Synthetic mini-hub validation
Purpose: convince a skeptic before this becomes the default.
Files: `tests/test_graph_mcp_mini_hub.py` + fixture builder (reuse planted-hub idiom from `test_graph_inference.py`/`test_transport.py`).
Cases (exact): `test_build_twice_byte_identical_manifests`; `test_touch_input_flips_fresh_to_stale_warn_only`; `test_methodology_hash_change_flips_to_inconsistent_block`; `test_mcp_uri_roundtrip_over_mini_hub`; `test_hostile_manifest_oversize_and_bad_schema_quarantined`; `test_hostile_remote_outbox_graph_payload_rejected_by_ingest_screens`; `test_protected_repo_negative_control_no_surface_writes`; `test_source_repo_git_clean_after_full_build_and_checkpoint` (split-state guard); `test_version_detector_classifies_stale_current_absent`; `test_no_lock_in_server_runs_with_zero_vendor_env` (unset all vendor API keys; server + tools fully functional on local files); `test_real_wiring_canary` (mini-hub intentionally UNWIRES one builder and asserts the acceptance suite FAILS — guards "synthetic passes while real surfaces unwired").
Human gate: this suite green is machine evidence FOR the phase-14/13 gates, never gate closure itself.

### K10 — End-to-end acceptance
Purpose: one command proving the loop: records → surfaces → manifests → journal plan → MCP answers.
Files: `tests/test_graph_mcp_acceptance.py::test_lesson_to_mcp_answer_roundtrip` — add a lesson via real API, rebuild surfaces, assert manifest fresh, journal checkpoint PLAN includes new hash, MCP `search_nodes` finds the lesson node with review_status=candidate, and `git status` stays clean under initialized DAD_DATA_ROOT.
Validate battery: full pytest; `cli validate`; `roadmap check --no-update`; `asset-dir daemon run-cycle` twice idempotent (worktree).
Human gate: none; evidence input for gates.

### K11 — Red-team & premortem fixes (see Part 4 — each fix is a line item in K1–K10)

### K12 — Parallel transport merge adjustment
Purpose: correct build order given M0–M2 implemented but unmerged.
Rules for Codex: (1) K1/K2/K4/K7 are path-independent — build NOW on a branch off main. (2) Anything writing graph/manifest/journal files (K3, K5, K6, K8-report) rebases onto the transport worktree branch or waits for its merge; imports `transport.data_path` only — a path literal in review = automatic reject. (3) Do NOT duplicate detector logic — K8 imports/refactors from `transport.py` + `transport_upgrade.py` (worktree) after merge. (4) The two branches (`fable/aios-architecture`, transport followup) merge BEFORE K3+ to avoid three-way registry drift; `dad-graph-inference-kernel` is already merged (verified).
Stop: if transport merge slips >1 week, K5/K6 may ship reading LEGACY paths through the same resolver (it fail-safes to legacy) — never by adding literals.

### K13 — Work order & stop conditions
Order: K1→K2→K4+K7 (parallel) → [transport merge point] → K3 → K5→K6 → K8 → K9→K10 → rollout per decision #16.
Global stops (any ⇒ halt + exception event + ask human): would approve a human gate; would write a target/protected repo; would push a real journal; would add a vendor SDK as default path; would emit score/rank in MCP; validate red on anything you touched.

---

## Part 3 — Corrected Codex plan (summary)

Codex's implied order (surfaces+MCP alongside transport merge) changes in one
way: **registry/schema/policy first, file-writers after the merge point** (K12).
The stale-policy fix (K4) moves UP — it is causing recurring false-red today
and is independent of transport. MCP moves AFTER journal checkpointing so
resources can pin `?at={hash}` to checkpointed content.

## Part 4 — Red-team findings & premortem (top 8, with fixes)

| # | Sev | Finding / failure story | Fix (kernel) |
|---|---|---|---|
| F1 | High | Prompt references ghost artifacts (this packet's README/briefs/schema, MCP policy doc) — future agents will "read" nonexistent authority | This file creates the packet; K5 creates the policy doc; add packet README stub; evidence-index must be generated from real paths (Codex task) |
| F2 | Critical | Graph rank becomes authority via MCP convenience (clients sort by whatever number appears) | K6/K7: no score fields in responses, no top-N tool, forbidden-claims registry, response-shape tests |
| F3 | Critical | Vendor fallback becomes default (someone wires a direct API "temporarily") | K9 no-lock-in test runs in CI with vendor envs unset; MCP-first policy doc states direct APIs are adapters requiring a recorded reason |
| F4 | High | Stale-manifest false-green: report claims fresh over stale inputs | K4 fresh-claim-over-stale ⇒ BLOCK + test |
| F5 | High | Split-state: half the writers on legacy paths, half on data root after partial migration | Transport resolver already fail-safes (uninitialized ⇒ legacy); K9 split-state test asserts git-clean + single-root writes; K12 forbids literals |
| F6 | Critical | Hostile journal remote-outbox or crafted manifest executes influence (prompt-injection-shaped fields, oversized payloads, path-traversal URIs) | Ingest screens unchanged (untrusted-input law); K5 registry-only URI resolution; K9 hostile-payload tests; manifests size-capped by schema |
| F7 | High | Version tracking silently marks stale repos current (empty contract read as "no news = fine") | K8 absence=legacy law + explicit test; mirrors capture-surface precedent |
| F8 | High | Synthetic suite passes while real surfaces unwired (mocks drift from builders) | K9 real-wiring canary test (unwire one builder ⇒ suite must fail); K10 uses real APIs end-to-end |

Premortem one-liner: six months out the likeliest death is not breakage but
QUIET AUTHORITY CREEP — agents citing graph neighbors as facts and MCP as the
source of truth. The countermeasures that must never be optimized away:
authority_boundary on every response (K5/K6), forbidden-claims registry (K7),
and navigation/knowledge separation (decision #3).

## Direct fix made this session

One tiny, local, reversible fix only: created this packet directory + this
output file (the packet itself was the missing artifact). No code, registry,
or roadmap files touched.
