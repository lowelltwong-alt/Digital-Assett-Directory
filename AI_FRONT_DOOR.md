# AI Front Door - Digital Asset Directory

## Repository identity

- **Repository:** `Digital-Assett-Directory`
- **Role:** private portfolio intelligence, metadata, graph, discovery, and governed-learning hub
- **Authority level:** authority for this repository's catalog contracts and workflows only
- **Non-authority:** this repository does not redefine the internal canon of any source repository it scans

## Single AI entrypoint

All AI agents start here. Do not begin from a random doc, generated report, or
remembered path. This file is the deterministic front door; it routes agents to
authority, the AI table of contents, knowledge-graph entrypoints, task-specific
contracts, and validation.

```text
AI_FRONT_DOOR.md
-> authority stack
-> AI_TABLE_OF_CONTENTS.md branch
-> knowledge graph entrypoints
-> task-relevant schemas, registries, docs, and roadmap gates
-> generated reports only as candidate evidence
```

AI navigation files follow `docs/AI_ENTRYPOINT_AND_TOC_ROUTING_STANDARD.md`.
Every AI table-of-contents row must give the path, what it is, routing tags,
and when to look further.

## Required read order

1. `AGENTS.md`
2. `MACHINE_NAVIGATION_MANIFEST.json`
3. `registry/source-of-truth.json`
4. `registry/design-authority.json`
5. `registry/identity-layer-registry.json`
6. `AI_TABLE_OF_CONTENTS.md`
7. `docs/ARCHITECTURE.md`
8. `docs/ASSET_IDENTITY_AND_SIMILARITY_LADDER.md`
9. task-relevant schemas, registries, and roadmap gates

## AI TOC branches

Use `AI_TABLE_OF_CONTENTS.md` as the branching map after the required read
order. Choose the branch by task, then read only the matching docs, schemas,
registries, evidence, and generated reports needed for the work.

Core branches:

- front doors and authority;
- architecture and knowledge graph;
- contracts and controlled vocabularies;
- operations and validation;
- roadmap evidence;
- reference and generated-candidate surfaces.

## Knowledge graph entrypoints

Knowledge-graph surfaces are navigation and candidate-evidence aids. They do
not prove source truth, value, authority, or promotion.

| Entrypoint | What it is | Use when |
|---|---|---|
| `docs/KNOWLEDGE_GRAPH_MODEL.md` | Conceptual model for asset nodes, edges, authority posture, and graph use. | You need to understand what graph facts can and cannot mean. |
| `registry/edge-type-registry.json` | Controlled edge vocabulary. | You create, interpret, or validate graph relationships. |
| `registry/asset-pattern-registry.json` | Controlled high-leverage pattern vocabulary. | You classify workflows, composite assets, or reusable systems. |
| `registry/template-registry.json` | Controlled template library with forward and reverse dependencies. | You create, update, validate, or reuse templates. |
| `assets/asset-registry.json` | Local index of installed reusable assets. | You need a reusable asset, package provenance, rollout command, or source path before coding or template work. |
| `assets/ai-engineering-preflight/` | Installed AI engineering preflight asset with Python/Rust agent guidance, templates, prompts, and dry-run rollout scripts. | You are planning AI-assisted software changes, refactors, or repo instruction/template deployment. |
| `assets/python-ai-advantage-preflight/` | Installed Python preflight asset with candidate high-leverage Python tactics, examples, and an agent instruction block. | You are planning Python implementation, API design, or long-script refactor work and need Python-specific tactic guidance. |
| `docs/LANGUAGE_CODING_ADVANTAGE.md` | DAD language-specific AI coding advantage playbook for Python, Rust, and future languages, with source-intake and promotion boundaries. | You add or refresh Python/Rust guidance, evaluate a frontier language technique, or decide whether a language asset should become DAD guidance. |
| `docs/CODING_ASSET_CONTROL_PLANE.md` | DAD-side control-plane design for coding assets, tactics, routers, mail packets, and downstream pointers. | You are adding, routing, validating, or reusing AI coding assets. |
| `docs/CODING_HARNESS_LIBRARY.md` | DAD-side coding harness library for test performance, Rust parity, preflight, red-team, governance safety, and provenance workflows. | You create, recommend, evaluate, package, or adopt coding-improvement harnesses. |
| `docs/AGENT_SKILL_LIBRARY.md` | DAD-side library for agent skills, lifecycle notices, checkout pointers, and replacement policy. | You are creating, checking out, updating, retiring, or replacing agent skills across repos. |
| `docs/DAD_REPO_ENROLLMENT.md` | Reviewed-wave repo enrollment and control-plane contract for persistent repos. | You plan, apply, update, audit, or explain DAD full governance enrollment. |
| `registry/control-plane-registry.json` | Reviewed DAD control-plane registry with cadence, surfaces, and normal write boundaries. | You need to know what DAD can advise, update by approval, or touch during recurring operation. |
| `registry/dad-needs-registry.json` | DAD request list for lessons, assets, harness feedback, usage feedback, skill updates, and governance drift repos should send back through mail. | A repo needs to know what DAD is looking for. |
| `registry/dad-offerings-registry.json` | Rich DAD card catalog of assets, skills, templates, harnesses, architecture refs, maps, workflows, and known upgrades. | A repo needs to match context to DAD offerings or decide whether to use now, save for future, defer, reject, or ask for human review. |
| `registry/dad-usefulness-methodology.json` | Deterministic scoring method for DAD offering recommendations. | You need to explain why DAD suggested an offering without claiming the score proves truth or value. |
| `registry/asset-recognition-methodology.json` | Candidate scoring method for recognizing useful digital assets from repo paths and metadata without copying private contents. | You need to find high-value assets, instructions, harnesses, schemas, prompts, or maps in a repo scan. |
| `docs/ASSET_RECOGNITION_METHODOLOGY.md` | Human-readable asset-recognition loop and source-boundary rules. | You are deciding what DAD should save, promote, ignore, or ask a repo to send back. |
| `registry/agent-skill-library.json` | Governed skill registry with DAD skill IDs, versions, formats, source paths, checkout modes, and lifecycle state. | You need to select or validate a DAD-managed skill before a downstream repo checks it out. |
| `registry/coding-asset-registry.json` | Reusable coding asset registry with applicability, validation, authority boundaries, and source evidence. | You need to select a DAD coding asset before AI-assisted implementation. |
| `registry/language-coding-advantage-registry.json` | Python, Rust, and future-language coding advantage registry with trusted sources, overlooked patterns, harness routes, and adoption gates. | You need language-specific coding guidance or want to route a new language-frontier signal into DAD. |
| `registry/coding-harness-registry.json` | Coding-improvement harness registry with context routing, evidence, prompts, scripts, evals, examples, and package paths. | You need a reusable harness for AI coding improvement or test acceleration research. |
| `registry/harness-discovery-methodology.json` | Candidate radar method for finding missing or underpowered coding harnesses from orphan assets, tactics, lessons, and research leads. | You need to turn repeated coding pain or research opportunities into a reusable harness candidate. |
| `docs/HARNESS_DISCOVERY_RADAR.md` | Human-readable orphan/radar/research-to-harness workflow. | You are asking Fable, Claude, Codex, or another agent to improve DAD's coding harness library. |
| `registry/coding-tactics-radar.json` | Candidate Python, Rust, and agent-instruction tactics with examples, risks, and promotion status. | You need tactic recommendations or postflight tactic feedback targets. |
| `registry/preflight-profile-router.json` | Task/context router from repo/language/risk signals to DAD profiles, tactics, validation, and stop conditions. | You need to choose the right preflight profile or run a midflight tactic recommendation. |
| `docs/CROSS_REPO_GOVERNANCE_DEPENDENCY_MAP_PATTERN.md` | Reusable cross-repo governance map and child-mirror template pattern. | You design a repo family where upstream governance and child repo mirrors must stay aligned. |
| `docs/MAIL_CENTER.md` | Governed DAD mail hub and repo-local inbox/outbox mirror. | You need candidate lessons, workflows, assets, taxonomy, capabilities, or governance notices to move across repos without mutating source authority. |
| `ontology/digital-asset-ontology.ttl` | Ontology layer for graph concepts. | You need semantic graph structure or external graph alignment. |
| `ontology/taxonomy.skos.ttl` | Taxonomy layer for broader/narrower concept navigation. | You need controlled concept hierarchy. |
| `processed/graph/graph.json` | Generated graph output. | You need candidate edges from the latest processed catalog; treat as generated evidence. |
| `processed/reports/asset_family_recognition.md` | Generated report of asset-family candidates. | You need composite workflow or family candidates from scans. |
| `processed/reports/workflow_sweeps/workflow_sweeps_index.md` | Generated workflow-sweep index. | You need cross-repo workflow pattern candidates. |
| `processed/reports/workflow_part_recognition.md` | Generated workflow-part report. | You need recombinable workflow sub-unit candidates beneath existing asset patterns. |
| `processed/reports/workflow_part_calibration_review_sample.md` | Stratified workflow-part calibration sample. | You need human labels before workflow parts affect radar, preflight guidance, scoring, or assembly. |
| `processed/reports/workflow_part_usage_guidance.md` | Generated manual guidance from reviewed workflow-part labels. | You need to know which workflow-part candidates are review-use examples, human-gated, rejected noise, or blocked by missing dataflow. |
| `processed/reports/manual_task_queue.md` | Generated manual task queue that re-ranks alerts and workflow-part guidance. | You need the safest next manual review tasks, with source-boundary and red-team posture. |
| `processed/reports/repo_buildout/index.md` | Generated repo-specific buildout advisor index. | You need candidate recommendations for improving one cataloged repo from its own assets and safe cross-repo inspiration. |
| `processed/reports/reference_architectures.md` | Generated reference architecture candidate report. | You need local metadata-only candidates for reusable architecture patterns, component roles, and grade rationale. |
| `processed/learning/reference_architecture_candidates.jsonl` | Generated reference architecture candidate records. | You need structured candidate records for architecture components, roles, gates, scores, and reuse guidance. |
| `processed/reports/architecture_consults/` | Generated seed architecture consult reports and prompts. | You need to advise a new repo before implementation using DAD patterns without copying or imposing canon. |
| `processed/reports/repo_completion_dashboard.md` | Generated per-repo completion dashboard for lesson automation. | You need to see which cataloged repos are blocked by content-read, learning-loop, governance, validation, or AI-navigation gates. |
| `processed/reports/repo_completion_wave_plan.md` | Generated ordered wave plan for completing repo lesson automation. | You need the safest order for content-read approval, lesson synthesis, learning-loop installs, governance maps, and final reviews. |
| `processed/reports/repo_completion_proof_check.md` | Generated proof check for repo-completion wave advancement. | You need to know which wave is actually blocked, what proof is missing, and whether it is safe to advance. |
| `processed/reports/template_library.md` | Generated template dependency and review-cadence report. | You need to know what templates depend on and what depends on them. |
| `processed/mail/` | Generated central mail inbox, outbox, archive, and delivery logs. | You need collected/routed candidate suggestions; never treat them as source truth. |
| `processed/skills/` | Generated central skill-checkout ledger and future freshness reports. | You need candidate targets for skill update, retirement, replacement, or manual-review notices. |
| `processed/reports/mail_center.md` | Generated mail-center summary report. | You need mail counts and message-type distribution. |
| `processed/reports/scan_coverage_cycle.md` | Generated no-rescan coverage-cycle log. | You need to know what was checked, intentionally skipped, and should be scanned next without repeating broad passes. |
| `processed/learning/scan_cycle_events.jsonl` | Generated append-only scan-cycle event trail. | You need the sequence of prior coverage passes, skipped signal families, gated next work, and cycle handoff context. |
| `processed/reports/lesson_automation_next_actions.md` | Generated queue of human-gated next actions from existing scopes. | You need the safest next approval decision across priority content, repo learning loops, governance maps, CI/release artifacts, and external gates. |
| `processed/learning/lesson_automation_action_decisions.jsonl` | Generated human-decision template for lesson-automation approvals, deferrals, and rejects. | You need exact approved repo/category/path/cap fields before running content reads, source repo writes, or external calls. |
| `processed/reports/lesson_automation_approval_packet.md` | Generated packet of suggested decision-label commands for pending lesson-automation rows. | You need exact approve/defer command text for Lowell to review; this packet never applies labels. |
| `processed/reports/lesson_automation_approval_impact.md` | Generated impact brief for one pending lesson-automation approval. | You need exact repo/category/path counts, byte caps, risks, and unlocked proof before Lowell decides. |
| `processed/reports/lesson_automation_execution_plan.md` | Generated execution plan from approved lesson-automation decisions. | You need exact commands or manual next steps for reviewed approvals; this plan never executes them. |
| `processed/reports/repo_learning_loop_install_scope.md` | Generated repo-learning-loop installation approval scope. | You need candidate repos and proposed files-only install commands before mutating any source repo. |
| `processed/reports/governance_map_adoption_scope.md` | Generated governance dependency-map and child-mirror adoption approval scope. | You need candidate repo families before writing maps, mirrors, validators, tests, or PR disclosure into source repos. |
| `processed/reports/ci_release_artifact_scope.md` | Generated metadata-only CI/release artifact scope. | You need candidate CI workflows, changelogs, QA reports, logs, and lockfiles before authorizing any content reads. |
| `processed/reports/priority_content_extract_scope.md` | Generated metadata-only approval scope for a future bounded content pass. | You need candidate priority paths before any source content is read. |
| `processed/learning/priority_content_observations.jsonl` | Generated bounded observations from approved content reads. | You need candidate content signals after a human-approved scoped extract; do not treat as source truth. |
| `processed/learning/priority_content_lesson_candidates.jsonl` | Generated context-bound lesson candidates from approved content observations. | You need reviewable lesson candidates before any learning rule or preflight default is changed. |
| `processed/learning/learning_rule_promotion_candidates.jsonl` | Generated learning-rule promotion candidate packages. | You need reviewed lesson candidates packaged for later human-approved registry promotion without mutating learning rules. |

## Core boundary

```text
source artifact
-> immutable observation
-> normalized asset candidate
-> candidate graph relations
-> human-reviewable alert or context pack
-> explicit promotion decision, when needed
```

Discovery output is evidence and recommendation, not source-repository authority.

## What this repository owns

- source adapters and scan policy;
- asset identity and revision identity;
- the Asset Identity And Similarity Ladder for exact identity, similarity, graph discovery, and audit provenance;
- catalog metadata and local graph vocabulary;
- generated workflow-part candidates beneath existing asset-family patterns;
- candidate value, staleness, orphan, missing-part, and synergy scoring;
- lessons and AI handoff capture;
- DAD mail-center candidate suggestion transport;
- reviewed-wave DAD repo enrollment, control-plane registry, and mailbox-only recurring operation;
- DAD-managed agent skill library, pointer checkouts, and lifecycle notices;
- tracked reusable asset packages and their local discovery index;
- lesson-automation coverage routing and scan-cycle logs;
- metadata-only reference-architecture recognition and grading;
- generated architecture consult packs for new repo seeding;
- AI entrypoints and downstream integration templates;
- cross-repo governance dependency-map template seeds;
- local audit, validation, and roadmap state.

## What this repository must not own

- the meaning or authority rules of a scanned repository;
- silent changes to source repositories;
- automatic promotion of inferred tags, links, or research findings into source canon;
- credentials, API tokens, private keys, or raw secrets;
- a claim that a heuristic score proves truth or importance.

## Work routes

| Intent | Route | Required outputs |
|---|---|---|
| Scan new sources | `source_scan` | raw snapshot, processed assets, audit event, source-mutation check |
| Change metadata contracts | `schema_change` | schema, example, registry update, validation |
| Change graph vocabulary | `ontology_change` | edge registry, ontology/taxonomy update, migration note |
| Change identity or similarity rules | `identity_change` | ladder doc, identity-layer registry, schema/edge updates, validation |
| Add a learning record | `lesson_capture` | lesson JSONL, provenance, confidence, reuse candidates |
| Move repo suggestions | `mail_center` | compose/collect/route/deliver/digest/review, append-only JSONL, local review decision |
| Enroll a persistent repo | `repo_enrollment` | reviewed enrollment policy, plan report, approval ID, allowlisted managed surfaces, audit event |
| Manage skill library | `agent_skill_library` | registry/schema update, checkout template, update/retirement mail, validator, local-review boundary |
| Build a feature | `implementation` | preflight, changed files, tests, postflight, lessons |
| Check operational readiness | `doctor` | readiness JSON, `processed/reports/operational_readiness.md`, missing-surface warnings |
| Search external GitHub | `research_missing_part` | explicit `--enable-external`, query, candidates, license/freshness metadata, human review note |
| Change roadmap | `roadmap_change` | gate evidence, status transition, remaining risks |

## Mandatory AI preflight

Before material changes, report:

```text
Route:
Goal:
Authority files read:
Allowed paths:
Forbidden paths:
Validation plan:
Stop conditions:
Context pack used:
```

Run:

```text
asset-dir agent preflight --repo <repo> --agent <agent> --task "<task>"
```

If the preflight includes `required_learning_rule_acknowledgements`, run a midflight
acknowledgement before proceeding through the matching work:

```powershell
asset-dir agent midflight --session <id> --context "<task context>" --ack-rule "<rule id>"
```

## Mandatory AI postflight

Before reporting completion, record:

```text
Files changed:
Commands run:
Tests run:
Tests not run:
Discoveries:
Failures or uncertainty:
Reusable lessons:
New assets created:
Missing capabilities:
Risks:
Next recommended action:
```

Run:

```text
asset-dir agent postflight --session <id> --repo <repo> --summary "..." --tests "..."
```

## Stop-and-report triggers

Stop rather than guess when:

- the correct source repository or authority file is unclear;
- a scan would traverse a sensitive or excluded location;
- a requested action would modify source artifacts;
- a token or secret appears in content or configuration;
- the same logical asset appears under conflicting identities;
- a proposed workflow treats SHA-256, embeddings, graph similarity, or fuzzy hashing as enough by itself to prove authority, reuse value, or canonical status;
- a proposed relationship would imply authority transfer;
- a schema, lifecycle, or edge definition conflicts with an existing registry;
- validation fails;
- an external repository lacks a reviewable license or provenance path;
- a roadmap phase is being marked complete without its acceptance evidence.

## Validation

```text
python -m pytest
python -m digital_asset_directory.cli validate
python -m digital_asset_directory.cli roadmap check
```

<!-- BEGIN DIGITAL_ASSET_DIRECTORY_ENROLLMENT -->
## Digital Asset Directory Enrollment

- Contract: `.digital-asset/dad-integration.json`
- Context map: `.digital-asset/context-map.json`
- Mailbox: `.digital-asset/mail/`
- Governance map: `.digital-asset/governance-map.yaml`
- Data map: `.digital-asset/data-map.yaml`
- Skill checkout: `.digital-asset/skills/checkout.json`
- Coding asset pointer: `.ai-assets.json`

Use these surfaces when work involves AI-assisted coding, repo governance,
lessons, reusable assets, templates, agent skills, or cross-repo suggestions.
DAD mail is candidate-only and local review controls adoption for `dad`.
<!-- END DIGITAL_ASSET_DIRECTORY_ENROLLMENT -->
