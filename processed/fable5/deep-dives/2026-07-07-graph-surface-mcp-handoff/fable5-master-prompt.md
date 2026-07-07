# Fable 5 Prompt: DAD Graph Surface Manifests And MCP Boundary

You are Fable 5 reviewing DAD, the Digital Asset Directory. DAD is a
local-first governance, learning, graph, and transport control plane. Repos
retain local source authority. DAD recommendations, mail, generated reports,
graph edges, scores, runtime observations, and Fable output are candidate
evidence until reviewed.

## Mission

Spend scarce Fable effort on this question:

How should DAD define graph surfaces, generated graph manifests, and MCP
resources so future agents can discover and query DAD knowledge without turning
generated graph evidence, MCP servers, or any AI vendor runtime into authority?

Build compact implementation kernels for Codex. Prefer precise, buildable
kernels over long essays.

Also review Codex's proposed build plan. If graph surface manifests, MCP
resources, version tracking, synthetic tests, or transport merge work require a
different order, say so and emit the corrected kernel order.

## Non-Negotiables

- AI runtimes stay agent-agnostic. Claude, Codex, Cursor, Copilot, Fable, MCP
  clients, and future tools are optional adapters.
- No AI or vendor lock-in. Direct APIs and vendor SDKs are fallback adapters
  only.
- Internal DAD integrations default to local MCP resources/tools/prompts over
  direct APIs.
- MCP is not a governance authority. DAD CLI lifecycle, schemas, audit records,
  Git/CI gates, and human gates remain durable authority.
- Generated graph records are candidate evidence. They never approve human
  gates, source mutations, public release, enrollment, or protected repo writes.
- Generated graph outputs must be rebuildable. Raw records and reviewed
  registries are source truth.

## Read First

- `processed/fable5/deep-dives/2026-07-07-graph-surface-mcp-handoff/README.md`
- `processed/fable5/deep-dives/2026-07-07-graph-surface-mcp-handoff/kernel-briefs.md`
- `processed/fable5/deep-dives/2026-07-07-graph-surface-mcp-handoff/evidence-index.json`
- `docs/MCP_FIRST_INTEGRATION_POLICY.md`
- `docs/GRAPH_BUILDOUT_HANDOFF.md`
- `docs/KNOWLEDGE_GRAPH_MODEL.md`
- `docs/DAD_OS_BUILD_ROADMAP.md`
- `docs/DAD_TRANSPORT_AND_COMMS_REDESIGN.md`
- `roadmap/evidence/phase-13-transport-local-acceptance.md`
- Parallel transport worktree files, if available:
  - `C:/Users/lowel/OneDrive/Desktop/Git Projects/_codex_worktrees/dad-transport-followup/src/digital_asset_directory/transport.py`
  - `C:/Users/lowel/OneDrive/Desktop/Git Projects/_codex_worktrees/dad-transport-followup/src/digital_asset_directory/cli.py`
  - `C:/Users/lowel/OneDrive/Desktop/Git Projects/_codex_worktrees/dad-transport-followup/src/digital_asset_directory/daemon.py`
  - `C:/Users/lowel/OneDrive/Desktop/Git Projects/_codex_worktrees/dad-transport-followup/src/digital_asset_directory/journal.py`
  - `C:/Users/lowel/OneDrive/Desktop/Git Projects/_codex_worktrees/dad-transport-followup/src/digital_asset_directory/mail_center.py`
  - `C:/Users/lowel/OneDrive/Desktop/Git Projects/_codex_worktrees/dad-transport-followup/src/digital_asset_directory/dad_library.py`
  - `C:/Users/lowel/OneDrive/Desktop/Git Projects/_codex_worktrees/dad-transport-followup/src/digital_asset_directory/exception_capture.py`
  - `C:/Users/lowel/OneDrive/Desktop/Git Projects/_codex_worktrees/dad-transport-followup/src/digital_asset_directory/readiness.py`
  - `C:/Users/lowel/OneDrive/Desktop/Git Projects/_codex_worktrees/dad-transport-followup/src/digital_asset_directory/research.py`
  - `C:/Users/lowel/OneDrive/Desktop/Git Projects/_codex_worktrees/dad-transport-followup/src/digital_asset_directory/template_library.py`
  - `C:/Users/lowel/OneDrive/Desktop/Git Projects/_codex_worktrees/dad-transport-followup/src/digital_asset_directory/proposals.py`
  - `C:/Users/lowel/OneDrive/Desktop/Git Projects/_codex_worktrees/dad-transport-followup/src/digital_asset_directory/workflow_parts.py`
  - `C:/Users/lowel/OneDrive/Desktop/Git Projects/_codex_worktrees/dad-transport-followup/tests/test_data_root_generated_writers.py`
  - `C:/Users/lowel/OneDrive/Desktop/Git Projects/_codex_worktrees/dad-transport-followup/tests/test_transport.py`
- `AI_FRONT_DOOR.md`
- `AI_TABLE_OF_CONTENTS.md`
- `MACHINE_NAVIGATION_MANIFEST.json`
- `registry/ai-navigation-registry.json`

## Highest Priority Questions

Answer these directly. If a question changes implementation, emit a kernel.

1. What exactly counts as a DAD graph surface?
2. Should DAD have one unified graph ontology or several bounded graph
   ontologies with shared guardrails?
3. What is the hard boundary between navigation graph and knowledge graph?
4. Which stale generated graph manifests should block validation versus warn?
5. Should generated graph manifests live in Git after `DAD_DATA_ROOT` is active?
6. How should graph manifests checkpoint into `dad-journal`: full snapshots,
   hashes, compressed bundles, or deltas?
7. What should MCP expose first: graph manifests, graph query tools, or both?
8. How does DAD prevent graph centrality, match counts, or graph ranking from
   becoming fake authority?
9. Which graph edge types or edge claims are forbidden because they imply truth,
   quality, source authority, dependency, or human approval?
10. Should repo/enrollment/transport state be modeled as a graph, or as
    operational records with derived graph views?
11. What is the minimal useful graph query API for the first MCP release?
12. What should the stable MCP resource URI taxonomy be?
13. Does Codex's graph surface build plan need to change because transport
    completion is still being merged in parallel?
14. What version numbers or surface-contract versions must DAD track so it can
    tell which repos have which graph, transport, journal, MCP, and enrollment
    surfaces installed?
15. What synthetic mini-hub tests are required before calling the new graph/MCP
    surface model the default way of doing this?
16. What is the safe downstream rollout sequence after the local system passes
    synthetic tests?

## Kernel Assignment

For each consequential answer, produce a compact kernel. A kernel should be
short enough for Codex to implement without rereading the whole packet.

Required kernel candidates:

- Graph surface registry kernel.
- Shared generated graph-manifest schema kernel.
- DAD_DATA_ROOT and dad-journal placement kernel.
- Validation and stale-manifest policy kernel.
- MCP graph resource URI kernel.
- Minimal MCP graph query tool kernel, if tools should exist in v1.
- Anti-false-authority kernel for centrality, rank, score, and edge semantics.
- Surface version tracking and repo-status kernel.
- Synthetic mini-hub validation kernel.
- End-to-end acceptance-test kernel.
- Red-team and premortem fix kernel.
- Parallel transport merge-adjustment kernel.
- Work order and stop conditions kernel.

Each kernel should include:

- purpose;
- source files to add or edit;
- data/generated paths;
- exact invariants;
- tests;
- validation commands;
- what Codex must not implement yet;
- human-gate implications.

## Testing, Red-Team, And Premortem Assignment

Do not only say "add tests." Design the tests that would convince a skeptical
operator that the new graph/MCP/transport surface model actually works.

Return:

- unit test kernel;
- synthetic mini-hub integration kernel;
- initialized `DAD_DATA_ROOT` kernel;
- journal checkpoint kernel;
- MCP resource URI/kernel;
- downstream repo-version detection kernel;
- protected repo negative-control kernel;
- no-lock-in negative-control kernel;
- red-team finding list;
- premortem failure list;
- concrete fixes or guardrails for each red-team and premortem item.

Red-team should try to break:

- source repo cleanliness after generated graph operations;
- stale manifest detection;
- graph rank becoming authority;
- direct API/vendor fallback becoming the default;
- protected repo mutation;
- malformed MCP resource URIs;
- hostile remote-outbox or graph manifest payloads;
- data-root split-state between source repo and journal;
- version tracking that silently marks stale repos current;
- synthetic tests that pass while real surfaces are unwired.

## Token Discipline

Conserve tokens. Do not rewrite all background. Prefer:

- top 8 findings only unless critical;
- one decision table;
- compact kernels;
- exact file paths;
- exact test names;
- no copied source blobs;
- no broad restatement of the MCP spec.

## Severity Order

- Critical: false authority, secret/private-data leak, protected repo mutation,
  human-gate bypass, or cloud/API lock-in.
- High: stale manifest false-green, graph/navigation boundary blur, MCP resource
  URI instability, or graph score/rank over-trust.
- Medium: missing docs, missing navigation, weak tests, incomplete operator
  ergonomics.
- Low: clarity and naming.

## Output

Return JSON or structured markdown that satisfies `expected-output.schema.json`.

If you make one direct fix, keep it tiny, reversible, and local to this packet.
Otherwise give Codex exact delegation items.
