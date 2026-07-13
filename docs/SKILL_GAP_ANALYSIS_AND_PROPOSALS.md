# Skill Gap Analysis and High-Leverage Skill Proposals

Generated: 2026-07-12
Status: **candidate** (unreviewed proposal evidence; not a reviewed registry, not an adoption decision)
Author context: produced by Claude Code session `dad:session:a89f9a2b-fac3-4560-83a6-91b62f5cb68a` from a read-only sweep of the full workspace.

## How an AI should use this file

This file is a self-contained build brief. Each proposed skill has: an id, a short
description of what it does, why it is high-leverage, and why it is missing from the
current libraries. Complicated skills include a **kernel** — a SKILL.md skeleton with
steps, inputs, outputs, and guardrails that a builder agent can expand directly.

Rules for any AI building from this file:

- Follow `docs/AGENT_SKILL_LIBRARY.md` and register new skills in
  `registry/agent-skill-library.json` via the `skill:dad-agent-skill-forge` process.
- Every new skill needs `trigger_examples`, `does_not_apply_when`, capabilities,
  an `authority_boundary`, and `review_status: candidate` until a human reviews it.
- "Leverage" labels in this file are **heuristic qualitative judgments**, not
  calculated scores. No scoring methodology is claimed
  (per `learning-rule:calculated-score-requires-methodology`).
- Proposals are candidate evidence. They do not authorize cross-repo writes,
  plugin installs, or registry semantic changes.

---

## Part 1 — Is the asset directory an effective knowledge graph?

**Short answer: it is a real knowledge graph in structure and governance, but its
findability and connection-discovery are only partially effective, and skills are the
weakest node type in the graph.**

### What already works (genuine KG strengths)

- **Typed, closed edge vocabulary.** `registry/edge-type-registry.json` and
  `registry/graph-edge-registry.json` define reviewed edge types (`learned_in`,
  `about_asset`, `matches_pattern`, `uses_asset`, `supersedes`, …) with direction,
  cardinality, evidence requirements, and `danger_if_wrong`. Most hobby "knowledge
  graphs" never get this far.
- **Forbidden-claim discipline.** Generated edges cannot claim `approved_by`,
  `verified`, `trusted`, `better_than`, `canonical`, `causes`. This prevents the
  classic KG failure where inferred structure masquerades as authority.
- **Node registries exist for every major entity type**: offerings, assets, skills,
  lessons, patterns, needs, templates, harnesses, tactics, trusted sources,
  context tags, exceptions.
- **The Phase 11 "library card catalog"** adds deterministic task-intent routing
  (`match` over offerings with declared `validation_refs`, `owner_authority`,
  `adoption_semantics`, and golden/paraphrase/negative test cases). That is a real
  retrieval surface with evals — rare and valuable.
- **Cross-repo edges exist** via enrollment contracts, usage ledgers
  (`uses_asset`, `depends_on` vs `dependency_candidate`), and mail.

### What limits effectiveness (the honest gaps)

1. **The graph is sharded across ~40 JSON registries with no traversal surface.**
   To answer "what connects to X?" an agent must know which registries to open and
   join them by hand. There is no `asset-dir graph neighbors <id>` /
   `asset-dir graph path <a> <b>` query. Findability today = filename knowledge +
   grep, plus the new card catalog for offerings only.
2. **Skills are under-connected nodes.** Offerings and lessons have rich edges;
   skills mostly have `dependencies` (file pointers) and lifecycle stubs. There are
   no `skill -> skill` composition edges (`loads`, `complements`, `supersedes` in
   practice), no `skill -> repo` applicability edges, and no
   `skill -> task-intent` routes in the card catalog. So the exact thing you want —
   "see connections to forecast the next skill" — is not yet queryable.
3. **The skill estate is split across four uncatalogued locations** with partial
   duplication and no drift detection:
   - DAD library: `registry/agent-skill-library.json` (14 records) + `assets/agent-skills/`
   - Global Codex/GPT personal skills: `~/.codex/skills/` (22 skills, incl. the
     `personal-*` family and PR-lifecycle family — several are copies/ports of DAD
     skills that can silently drift)
   - LawFirm OS: `LawFirm-os-skills-registry/skills/` (2 approved, ~18 drafts)
   - Claude Code plugins/built-ins (skill-creator, code-review, verify, …)
   A "skill knowledge graph" that omits three of its four shards cannot forecast well.
4. **No semantic similarity layer** (deliberate, to avoid false authority) — but
   the consequence is that "like ones" are only found when a human or agent already
   suspects the link. A governed, candidate-labeled similarity edge would be safe
   under existing forbidden-claim rules.
5. **Discovery docs go stale silently.** `AI_FRONT_DOOR.md` /
   `AI_TABLE_OF_CONTENTS.md` / `MACHINE_NAVIGATION_MANIFEST.json` exist in several
   repos but nothing audits them against the actual tree.

**Verdict:** the graph substrate is excellent; the *query, unification, and
skill-node layers* are the gap. The highest-leverage skills below attack exactly that.

---

## Part 2 — Current skill inventory (as of 2026-07-12)

### DAD skill library (`registry/agent-skill-library.json`, v0.5.0)

| Skill | Role |
|---|---|
| skill:dad-work-router | Routes material work through preflight/lanes/postflight |
| skill:dad-learning-loop | Evidence-backed lesson loops |
| skill:dad-digital-asset-radar | Asset discovery/grading/dedup |
| skill:dad-iteration-optimizer | Bottleneck/optimization routing |
| skill:dad-agent-skill-forge | Skill lifecycle creation/registration |
| skill:codex-capability-radar | Runtime capability matching |
| skill:dad-coding-asset-control-plane | Coding asset + tactic routing |
| skill:ai-engineering-preflight-python / -rust | Language preflights |
| skill:python-ai-advantage-preflight-profile | Python tactic profile |
| skill:rust-qa-subagent-pack | Rust QA subagent roles |
| skill:long-run-optimization-review-pack | Long-command optimization trigger |
| skill:material-work-learning-discovery | Post-build learning lanes |
| skill:subagent-continuous-improvement | Subagent grading/routing audits |

### Global personal skills (`~/.codex/skills/`)

DAD ports: codex-capability-radar, dad-agent-skill-forge, dad-digital-asset-radar,
dad-iteration-optimizer, dad-learning-loop, dad-work-router,
subagent-continuous-improvement, plus dad-trigger-pattern-radar (not in DAD library).

Personal family: personal-daily-decision-ops, personal-decision-redteam-premortem,
personal-hierarchical-agent-mesh, personal-human-decision-radar,
personal-mesh-architecture-thinking, personal-project-management-ops,
personal-worktree-radar.

PR family: cross-repo-pr-queue, pr-lifecycle-router, pr-publish-worker,
pr-review-merge-gate, subagent-peer-review-routing, codex-primary-runtime.

### LawFirm OS skills registry

Approved: elegant-design-review, malicious-skill-review.
Drafts (~18): legal-retrieval-planner, legal-corpus-ingestion-preflight,
legal-prompt-injection-boundary-review, privilege-aware-retrieval-review,
skill-evaluation-harness, legal-adversarial-eval-builder, and similar
legal-RAG/eval/integrity skills.

### Observed overlap/drift risks

- `dad-work-router`, `dad-learning-loop`, etc. exist in both DAD and `~/.codex/skills`
  with independent copies — no automated drift check.
- `skill-evaluation-harness` (LFOS draft) overlaps `dad-agent-skill-forge` grading.
- `personal-worktree-radar` + `cross-repo-pr-queue` overlap the proposed
  workspace-state radar below; a new skill should extend, not duplicate, them.

---

## Part 3 — Repo portfolio map and the common thread

| Repo | What it is |
|---|---|
| 04_Digital_Assett_Directory | Sovereign governance OS: asset/skill/lesson registries, preflight/postflight, mail, roadmap gates |
| 00_LawFirm_OS (multi-repo) | Legal ops platform: intake, orchestrator, semantic substrate, skills registry, talent intel, exceptions lake |
| 03_World_View: logos-* | Governed Bible knowledge graph (data plane) + governance architecture + doctrine genealogy + boundary literature |
| 03_World_View: noesis-atlas | Worldview/philosophy taxonomy control plane feeding Logos via governed exports |
| 02: kirsten-dissertation-knowledge-graph | Dissertation as governed KG: ontology, chunking, anchors, provenance, audit loop |
| 02: fmg-fractal-capability-ontology | Semantic control plane / Innovation OS contracts |
| 02: airca-fractal-decision-architecture | AI-era RACI: fractal decision architecture, decision-capacity governance |
| 02: lowell-career-os | Living self-model: career navigation, positioning, evidence updates |
| 01: obsidian-knowledge-vault | Personal notes vault |
| 90_AI_Tooling_And_Temp, workspaces | CI contracts, patch bundles, worktrees, merge workspaces |

**The common thread is unmistakable: every serious repo is a governed knowledge
graph with the same skeleton** — ontology/taxonomy + JSON registries + schemas +
provenance and confidence labels + candidate-vs-reviewed lifecycle + human gates +
AI front doors + evidence packets + roadmap gates. DAD is the sovereign instance;
LawFirm OS, Logos/Noesis, the dissertation KG, FMG, and AIRCA are siblings or
children of the same pattern.

**Therefore the highest-leverage skills are the ones that operate on that shared
skeleton once and pay off in every repo** — not per-domain skills. Forecast: the
portfolio is converging on (a) runtime orchestration layers over data-plane repos
(Logos runtime, LFOS orchestrator), (b) MCP-first exposure of registries, and
(c) retrieval + eval surfaces everywhere. Skills below are ordered accordingly.

---

## Part 4 — Proposed skills (the full list)

Leverage labels: **[very high] / [high] / [medium]** — heuristic judgments, not scores.

### Group A — Skill-ecosystem meta-skills

**A1. unified-skill-catalog (skill-graph-indexer)** [very high]
- Does: scans all four skill shards (DAD library, `~/.codex/skills`, LFOS registry,
  Claude plugins + repo `.claude/skills`), builds one catalog with stable ids and
  candidate typed edges: `same_family_as`, `ported_from`, `drifted_from`,
  `overlaps_capability`, `loads` (composition), `applies_to_repo`. Emits a drift
  report for DAD↔codex duplicate copies.
- Why high-leverage: it is the missing "card catalog" for skills — the exact gap in
  Part 1. Every later skill decision (build/retire/merge) gets cheaper.
- Why missing: `agent-skill-library.json` only sees DAD-managed records; nothing
  today can even list your whole skill estate. **Kernel: K1.**

**A2. skill-gap-forecaster** [high]
- Does: recurring review that joins postflight lessons, dad-needs-registry, repeated
  midflight rule hits, and repo roadmaps to propose new skill candidates (this
  document, turned into a repeatable skill).
- Why: converts your learning-loop exhaust into a skill pipeline instead of ad-hoc
  requests. Missing: forge creates skills on demand; nothing scans for demand.

**A3. skill-porting-adapter** [high]
- Does: converts a skill between formats (codex_skill ↔ claude_skill ↔ generic)
  preserving frontmatter, triggers, `does_not_apply_when`, authority boundaries, and
  writing a `ported_from` edge + checkout record instead of a silent copy.
- Why: your #1 observed drift source is hand-porting DAD skills into
  `~/.codex/skills`. Missing: checkout policy defines modes but no executable skill.

**A4. skill-eval-harness (generalize LFOS draft)** [high]
- Does: golden/paraphrase/negative trigger tests + execution grading for any skill,
  DAD-side; promotes LFOS `skill-evaluation-harness` draft into the sovereign library.
- Why: Phase 11 proved eval-backed routing works for offerings; skills deserve the
  same. Missing: grading exists in forge but no runnable harness.

### Group B — Knowledge-graph operations (pays off in ~6 repos)

**B1. kg-query-navigator** [very high]
- Does: deterministic traversal over JSON registries without a database: neighbors,
  paths, orphan nodes, dangling refs, subgraph export (JSON/Mermaid) for any id.
  Read-only; labels every derived connection `candidate`.
- Why: single biggest findability gap (Part 1, item 1). Turns 40 registries into one
  navigable graph for every agent. **Kernel: K2.**

**B2. registry-schema-scaffolder** [very high]
- Does: creates a new registry + JSON schema + validator wiring + tests + docs stub
  in one pass following DAD conventions (authority_boundary, review_status,
  versioning, forbidden-claim inheritance). Works in DAD and sibling repos.
- Why: you build this exact quadruple constantly across DAD/Logos/LFOS/dissertation;
  it is your most repeated manual workflow. Missing: templates exist, no skill runs them.

**B3. graph-edge-auditor** [high]
- Does: validates every edge instance against the edge-type registry (direction,
  cardinality, evidence-required, forbidden claims), reports orphans and dangling ids.
- Why: governance exists on paper; nothing enforces it continuously. Cheap to build
  once B1 exists.

**B4. cross-repo-crosswalk-builder** [high]
- Does: governed crosswalks between ontologies/taxonomies (Noesis↔Logos exports,
  FMG↔AIRCA, DAD context-tags↔LFOS skill tags): candidate mappings + confidence
  labels + human-gate packet; never writes into the target repo. **Kernel: K3.**
- Why: your repos are siblings that will increasingly consume each other's exports;
  crosswalks are the connective tissue and are all hand-made today.

**B5. candidate-similarity-radar** [medium]
- Does: adds governed "like this" discovery — cheap lexical/structural similarity
  over registry rows and skill descriptions, emitted only as `similar_to` candidate
  edges with methodology cited, honoring semantic-evolution grading for near-copies.
- Why: safe version of the semantic layer you deliberately avoided; makes "find like
  ones" real without false authority.

**B6. provenance-chain-verifier** [medium]
- Does: walks any generated artifact to its source pointers; flags missing
  provenance/confidence labels or broken evidence paths.

### Group C — Governance and gate mechanics (all repos)

**C1. human-gate-packet-builder** [very high]
- Does: for any pending gate (e.g. the four open Phase 11 gates), assembles a review
  packet: what changed, evidence links, blast radius, options considered, rollback,
  open questions — using `templates/load-bearing-decision-review.template.md`.
- Why: human review is your system's bottleneck by design; making packets cheap
  directly raises throughput of the *whole* portfolio. Missing: templates + docs
  exist, no skill assembles them. **Kernel: K4.**

**C2. front-door-auditor** [high]
- Does: audits/refreshes AI_FRONT_DOOR.md, AI_TABLE_OF_CONTENTS.md,
  MACHINE_NAVIGATION_MANIFEST.json against the actual tree; reports staleness;
  regenerates candidates (never force-writes).
- Why: front doors are how every agent orients in every repo; silent staleness
  poisons all downstream navigation.

**C3. roadmap-gate-navigator** [high]
- Does: reads roadmap.yaml + gate-evidence.json, answers "what is blocking phase N,
  what evidence is missing, generate the evidence stub."
- Why: you run this by hand every session in DAD and LFOS.

**C4. release-boundary-gatekeeper** [medium]
- Does: pre-publication check for public-facing repos: private/internal mail rows,
  secrets, unreviewed candidate labels, license/provenance of imported code.

### Group D — Cross-repo operations

**D1. repo-enrollment-wizard** [high]
- Does: end-to-end dry-run-first enrollment of a new repo into DAD (contract,
  context-map, mail dirs, front-door stubs), driven by `asset-dir enroll` with the
  approval-ID gate preserved.
- Why: forecast — kirsten-dissertation, noesis-atlas, career-os are natural
  next enrollees; each manual enrollment re-derives the same steps.

**D2. mail-digest-triager** [high]
- Does: sweeps `.digital-asset/mail/**` across all enrolled repos, produces one
  digest (stale, unanswered, candidate suggestions), drafts metadata-only replies.
- Why: preflight already flags your mail digest as stale; mail is the designed
  cross-repo channel and currently under-used because triage is manual.

**D3. workspace-state-radar** [medium]
- Does: extends personal-worktree-radar + cross-repo-pr-queue into one sweep:
  branches, PRs, worktrees (`_codex_worktrees`, `_worktree-*`), merge workspaces,
  stale escalation dates; emits the branch/PR status records AGENTS.md requires.
- Why missing piece: existing skills each see one slice; nothing sees the whole desk.

**D4. governance-mirror-sentinel** [medium]
- Does: detects drift between mirrored governance files (AGENTS.md variants,
  CLAUDE.md imports, contract mirrors like
  `.ai/control/governance-dependency-map-mirror.json`), grading real semantic
  evolution vs copy noise per the semantic-evolution methodology.

### Group E — Domain accelerators (per-repo, reusing Group B machinery)

**E1. legal-skill-promotion-runner** [medium] — runs LFOS drafts through
skill-eval-harness + malicious-skill-review to move draft → approved with evidence.
**E2. scripture-graph-ingestion-qa** [medium] — chunking/anchor/concordance
validation loop for logos-scripture-graph releases (contract-first, data-plane only).
**E3. dissertation-evidence-auditor** [medium] — manuscript → extraction → audit →
fix loop for the dissertation KG, using its existing DATA_FLOW_MAP endpoints.
**E4. vault-to-graph-linker** [medium] — proposes candidate links from
obsidian-knowledge-vault notes to registry nodes across repos (read-only, outbox only).
**E5. career-os-evidence-updater** [medium] — turns session/project outcomes into
career-os evidence rows (role experiments, capability demonstrations).

### Group F — Retrieval and evaluation (the Phase-11 pattern, generalized)

**F1. retrieval-eval-builder** [very high]
- Does: for any router/matcher/retrieval surface (DAD card catalog, LFOS
  legal-retrieval-planner, future Logos concordance retrieval), generates
  golden + paraphrased + negative + multi-intent cases, runs them, and reports
  routing-basis coverage. **Kernel: K5.**
- Why: Phase 11 proved the pattern; LFOS drafts (legal-retrieval-quality-eval,
  legal-adversarial-eval-builder) want the same thing; building it once as a
  sovereign skill de-duplicates three roadmaps.

**F2. prompt-injection-boundary-reviewer** [high]
- Does: generalizes LFOS legal-prompt-injection-boundary-review to any repo that
  ingests external text (mail, scraped sources, boundary literature): checks that
  observed content is treated as data, front doors state it, tests cover it.

### Group G — Forecast skills (what you'll need next, based on where the repos are heading)

**G1. mcp-registry-server-scaffolder** [very high, near-term]
- Does: wraps DAD registries and the card catalog as MCP resources/tools (read-only
  first), matching `docs/MCP_FIRST_INTEGRATION_POLICY.md`; generates server stub,
  tool schemas mirroring CLI authority checks, and parity tests. **Kernel: K6.**
- Why forecast: your own policy says MCP-first; every agent runtime you're building
  (LFOS orchestrator, Logos runtime, Claude Code, Codex) will want registry access
  without shelling into the CLI.

**G2. runtime-contract-bridge** [high, near-term]
- Does: scaffolds the contract layer between a data-plane repo and its future agent
  runtime (Logos explicitly promises this split; LFOS orchestrator already lives it):
  validated release artifacts, version pinning, consumption tests.

**G3. embedding-sidecar-governor** [medium, later]
- Does: when you eventually add semantic search, this skill keeps embeddings as
  governed sidecars: candidate-only labels, methodology citation, no edge promotion
  without review. Pre-building the governance prevents the most likely future drift.

**G4. agent-mesh-instantiator** [medium, later]
- Does: turns `personal-hierarchical-agent-mesh` from prose into runnable
  configuration: generates Claude Code agent definitions / Codex subagents.yaml for
  a chosen mesh shape (worker+checker, foreman, boss) with budget stops.

**G5. data-root-migration-operator** [medium, later]
- Does: operates the `DAD_DATA_ROOT` transport/data-plane lifecycle (status, audit,
  staged migration, rollback) — the current uncommitted work shows this is live.

---

## Part 5 — Kernels for the complicated skills

### K1. unified-skill-catalog

```markdown
---
name: unified-skill-catalog
description: Build and refresh one candidate catalog of every skill across DAD,
  ~/.codex/skills, LawFirm OS skills registry, and Claude Code plugin/repo skills;
  detect duplicates, ports, and drift; emit typed candidate edges.
---
Inputs: skill shard roots (configurable list), registry/agent-skill-library.json,
  LFOS skill-agent-manifest.json, ~/.codex/skills/**, repo .claude/skills/**.
Steps:
1. Enumerate shards read-only. Parse SKILL.md frontmatter + registry records.
2. Assign stable catalog ids: reuse skill_id when present; else derive
   shard:name; never rename source records.
3. Detect families: same name across shards -> `same_family_as`; byte-identical
   -> `copy_of`; same name different content -> `drifted_from` with a diff summary
   graded via semantic-evolution methodology (real evolution vs noise).
4. Detect capability overlap (shared capability tags / high lexical overlap of
   descriptions) -> `overlaps_capability` candidate edges, methodology cited.
5. Emit: catalog JSON (nodes+edges, all review_status=candidate), drift report MD,
   and gap list (capabilities present in one ecosystem and absent in another).
Outputs: processed/skill-catalog/catalog.json, drift-report.md, gap-list.md.
Guardrails: read-only over all shards; no edge may use forbidden claims
  (recommended/canonical/better_than); catalog is candidate evidence; updating any
  source skill remains a separate human-gated action.
Validation: golden fixture shard with a known copy, a known drift, and a known
  unique skill; assert exact expected edges.
```

### K2. kg-query-navigator

```markdown
---
name: kg-query-navigator
description: Deterministic read-only traversal over DAD-style JSON registries —
  neighbors, paths, orphans, dangling references, and subgraph export — treating
  every derived connection as candidate evidence.
---
Inputs: registry root(s); edge-type registry; id conventions
  (asset:/skill:/lesson:/offering:/pattern:/repo: prefixes).
Steps:
1. Load node registries; build an in-memory index id -> record -> declared refs.
2. Extract edges only from declared fields listed in the edge-type registry
   (allowed_bases); label each edge with its basis field.
3. Commands: neighbors <id> [--depth n]; path <a> <b>; orphans; dangling;
   subgraph <id> --format json|mermaid.
4. Every output row carries: edge_type, basis, review_status=candidate,
   registry file + JSON pointer provenance.
Outputs: query results to stdout; optional Mermaid subgraph file for humans.
Guardrails: read-only; never invents edge types; refuses forbidden-claim wording;
  no similarity inference here (that is candidate-similarity-radar's job).
Validation: fixture registry set with known graph shape; assert neighbor sets,
  shortest path, orphan and dangling detection.
Note: fits naturally as `asset-dir graph ...` CLI subcommands later; build as a
  skill + script first, promote to CLI after review.
```

### K3. cross-repo-crosswalk-builder

```markdown
---
name: cross-repo-crosswalk-builder
description: Build governed candidate crosswalks between two ontologies/taxonomies
  in different repos, with confidence labels and a human-gate packet; never write
  into the target repo.
---
Inputs: source vocabulary (file + JSON pointers), target vocabulary, prior
  crosswalk rows if any, both repos' authority docs.
Steps:
1. Read both vocabularies read-only; record version/hash of each side.
2. Propose mappings in tiers: exact-label, alias/synonym-list, structural
   (same parent pattern), each tier labeled with its basis; no tier is "verified".
3. Grade near-duplicate terms with semantic-evolution methodology before claiming
   evolution or equivalence.
4. Write crosswalk file in the SOURCE repo (or DAD outbox) only:
   rows = {source_id, target_id, basis, confidence_label(heuristic), notes,
   review_status: candidate}.
5. Assemble a human-gate packet: counts per tier, ambiguous cases, unmapped
   remainder, danger_if_wrong per high-impact row.
Guardrails: target repo is never mutated; confidence labels are heuristic and say
  so; crosswalk adoption is the target repo's decision via its own review.
Validation: fixture pair of small vocabularies with known exact/synonym/unmappable
  terms; assert tier assignment and that no write touches the target fixture.
```

### K4. human-gate-packet-builder

```markdown
---
name: human-gate-packet-builder
description: Assemble a complete review packet for any pending human gate so the
  human decision takes minutes, not an archaeology session.
---
Inputs: gate id (roadmap gate, enrollment approval, skill promotion, crosswalk
  adoption), roadmap/gate-evidence.json, relevant evidence files, git log scope.
Steps:
1. Resolve the gate: what it protects, its acceptance criteria, current status.
2. Collect evidence: changed files, tests run + results (never claim unrun tests),
   validation refs, prior related decisions.
3. Fill templates/load-bearing-decision-review.template.md: blast radius, options
   considered (>=2 for high risk), rollback/kill criteria, open questions,
   explicit "what saying YES authorizes / what it does not".
4. List unknowns and the smallest experiment that would reduce each.
5. Write packet to roadmap/evidence/ or the gate's evidence home as *.human-review-packet.md.
Guardrails: the packet supports review; generating it never satisfies or closes
  the gate; no evidence may be summarized in a way that hides failures.
Validation: run against a known closed gate; a reviewer should reconstruct the
  original decision from the packet alone.
```

### K5. retrieval-eval-builder

```markdown
---
name: retrieval-eval-builder
description: Generate and run golden, paraphrased, negative, and multi-intent test
  cases for any deterministic router or retrieval surface; report routing-basis
  coverage and failures.
---
Inputs: the surface under test (CLI command or function), its declared intent
  vocabulary / routing methodology doc, existing cases if any.
Steps:
1. Read the routing methodology; enumerate declared intents and priority rules.
2. For each intent: >=1 golden case (canonical phrasing), >=2 paraphrases,
   >=1 negative (should NOT route here), plus multi-intent collisions across
   every priority boundary.
3. Run cases; classify failures: wrong route, tie mishandled, vocabulary gap,
   methodology/doc mismatch.
4. Report coverage per intent and per priority rule; write cases as durable test
   fixtures next to the surface's tests.
Guardrails: deterministic surfaces only (no LLM-judge here); cases must cite the
  methodology version they encode; a passing eval is evidence, not approval.
Validation: apply to the Phase 11 offering matcher first — it already has cases,
  so the skill's output can be diffed against a known-good baseline.
```

### K6. mcp-registry-server-scaffolder

```markdown
---
name: mcp-registry-server-scaffolder
description: Scaffold a read-only MCP server exposing DAD registries, the card
  catalog matcher, and graph queries as MCP resources/tools with the same
  authority checks as the CLI.
---
Inputs: registry list to expose, existing CLI entry points (match, data status,
  transport audit), docs/MCP_FIRST_INTEGRATION_POLICY.md.
Steps:
1. Phase 1 read-only: resources = registry files (versioned URIs);
   tools = library_match(task), graph_neighbors(id), preflight_summary(repo).
2. Every tool reuses the CLI/Python functions — no logic forks; parity tests
   assert tool output == CLI output for identical inputs.
3. Tool descriptions carry authority boundaries verbatim (candidate evidence,
   no adoption authority) so downstream agents inherit the framing.
4. Side-effectful tools (postflight write, mail send) are Phase 2 and each
   requires the DAD lifecycle + human gate mapping before scaffolding.
Guardrails: Phase 1 ships zero write tools; server config changes are
  user-approved; no secrets in resources; enrollment/mail authority unchanged.
Validation: MCP client smoke test + CLI-parity test suite; red-team check that no
  resource leaks private mail payloads.
```

---

## Part 6 — External landscape (what people are building, 2026)

Patterns from current ecosystem research worth stealing:

- **Behavioral/discipline skills dominate adoption** — the most-starred community
  skills encode working discipline (planning loops, TDD, worktree flows, "don't
  over-engineer" guardrails), not domain knowledge. Your `personal-*` family is
  already this shape; the gap is porting them into runnable mesh/config form (G4).
- **Universal SKILL.md portability** — skills are now written once and run across
  Claude Code, Codex CLI, Cursor, Gemini CLI. This validates A3
  (skill-porting-adapter) as a first-class need, not a chore.
- **Token/context compression skills** (structure maps, output compression) are a
  rising category — relevant to your 40-registry problem: B1's subgraph export is
  effectively a context-compression surface for DAD.
- **Memory architecture consensus** — production agent stacks converge on tiered
  memory (small always-loaded core + retrieval layer + explicit forgetting) and
  **shared knowledge graphs as the coordination layer between agents** — which is
  precisely DAD's architecture; the missing piece everywhere (including in the
  literature) is the query layer, reinforcing B1/G1 as the right bets.
- **Skill graphs with typed dependencies** are an active research direction
  (skills as nodes, composition edges, retrieval-based selection) — your instinct to
  make skills first-class graph nodes (A1) matches where the field is going.
- **Skill retrieval ambiguity** (multiple skills with same capability) is a named
  research problem — your `overlaps_capability` edges (A1) and eval harness (A4)
  address it directly.

Sources:
- [Composio — Top 10 Claude Code Skills 2026](https://composio.dev/content/top-claude-skills)
- [Firecrawl — Best Claude Code Skills](https://www.firecrawl.dev/blog/best-claude-code-skills)
- [Taskade — Best Claude Code Skills (tested + how to build)](https://www.taskade.com/blog/claude-code-skills)
- [Awesome Claude Skills directory](https://agent-skills.cc/claude-skills/top)
- [DevRev — AI agent orchestration & shared memory architecture 2026](https://devrev.ai/blog/ai-agent-orchestration)
- [AI Agent Memory Systems 2026 guide](https://jobsbyculture.com/blog/ai-agent-memory-systems-guide-2026)
- [SkillGraph: evolving skill graphs (arXiv)](https://arxiv.org/html/2605.12039)
- [SkillResolve-Bench: same-capability ambiguity in skill retrieval (arXiv)](https://arxiv.org/pdf/2606.10388)
- [awesome-harness-engineering (GitHub)](https://github.com/ai-boost/awesome-harness-engineering)

---

## Part 7 — Recommended build order (the best ones to make)

1. **A1 unified-skill-catalog** — you cannot manage what you cannot see; unblocks
   every other skill decision and fixes the DAD↔codex drift blind spot.
2. **B1 kg-query-navigator** — turns the registry shards into an actual queryable
   knowledge graph; the single biggest findability win.
3. **C1 human-gate-packet-builder** — attacks the portfolio-wide bottleneck
   (human review throughput); four Phase 11 gates are pending right now.
4. **B2 registry-schema-scaffolder** — your most repeated manual workflow across
   six repos.
5. **F1 retrieval-eval-builder** — generalizes the proven Phase 11 pattern and
   collapses three repos' eval roadmaps into one skill.
6. **G1 mcp-registry-server-scaffolder** — your own MCP-first policy, made real;
   future-proofs every runtime integration.
7. **A3 skill-porting-adapter** — stops the drift that A1 will reveal.
8. **C2 front-door-auditor** — cheap, and keeps every repo navigable for agents.

Rationale for the ordering: 1–2 build the *visibility layer*, 3–4 accelerate the
*governance loop*, 5–6 build the *interfaces* the next year of work needs, 7–8 keep
the estate clean. Domain accelerators (Group E) should be built after B1/B2 exist so
they reuse the shared machinery instead of forking it.

---

*This document is candidate evidence under DAD authority boundaries. Adopting any
proposal, registering any skill, or exposing any interface remains subject to the
normal DAD lifecycle, validation, and human gates.*
