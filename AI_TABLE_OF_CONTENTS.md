# AI Table Of Contents

This is the branching map after `AI_FRONT_DOOR.md`. Each first-class entry uses
the deterministic AI TOC row shape:

| Field | Meaning |
|---|---|
| Path | File, registry, command, or generated surface. |
| What it is | The role of the entry, not just its name. |
| Tags | Lower-snake-case routing tags. |
| Use when | The trigger for looking further. |

Navigation rows follow `docs/AI_ENTRYPOINT_AND_TOC_ROUTING_STANDARD.md`.
Generated outputs are candidate evidence unless a tracked human gate promotes
them.

## Tag Index

| Tag | Meaning |
|---|---|
| `front_door` | Start-here docs and machine entrypoints. |
| `authority` | Source-of-truth, design authority, and trust-boundary rules. |
| `knowledge_graph` | Graph model, ontology, taxonomy, edges, and graph reports. |
| `schema` | JSON Schemas and structured record contracts. |
| `registry` | Controlled vocabularies and deterministic IDs. |
| `workflow` | Repeatable work patterns, checklists, and pipelines. |
| `learning_loop` | Lessons, feedback, handoff, and pay-forward systems. |
| `calibration` | Human labels, score review, thresholds, and evidence. |
| `security_privacy` | Secret, PII, prompt-injection, public-safe, and source-boundary controls. |
| `roadmap` | Phase gates, roadmap status, and tracked acceptance evidence. |
| `generated_output` | Ignored processed outputs; useful but not source truth. |
| `public_safe` | Metadata-only patterns safe for a future public DAD repo. |
| `cross_repo` | Multi-repo patterns, workflows, and authority boundaries. |
| `validation` | Tests, CLI validators, and verification reports. |
| `background_connection` | Low-compute connection scouting, escalation packets, and bounded expansion maps. |
| `workflow_part` | Reusable workflow sub-units beneath asset patterns. |
| `repo_buildout` | Repo-specific buildout advice from cataloged assets, workflows, alerts, and safe inspiration candidates. |
| `template_library` | Reusable templates, dependencies, review cadence, and template upgrade governance. |
| `governance` | Governance maps, repo contracts, authority mirrors, PR checks, and fail-closed controls. |
| `coverage_cycle` | No-rescan coverage logs that show what was checked, skipped, and should be scanned next. |

## Front Doors And Authority

| Path | What it is | Tags | Use when |
|---|---|---|---|
| `AI_FRONT_DOOR.md` | Single AI entrypoint, route map, stop conditions, and validation baseline. | `front_door`, `authority`, `workflow` | Always read first before material work. |
| `AGENTS.md` | Standing operating contract for AI agents in this repo. | `front_door`, `authority`, `workflow` | You need mandatory preflight, postflight, edit, and validation rules. |
| `MACHINE_NAVIGATION_MANIFEST.json` | Machine-readable entrypoint, registry, generated-surface, and validation map. | `front_door`, `registry`, `validation` | A tool or agent needs deterministic repo navigation. |
| `registry/source-of-truth.json` | Repository precedence and authority-layer definitions. | `authority`, `registry` | You need to know what can override what. |
| `registry/design-authority.json` | Non-negotiable design rules and boundary constraints. | `authority`, `registry` | You are changing design behavior or evaluating a proposed change. |
| `registry/identity-layer-registry.json` | Asset identity and similarity ladder registry. | `authority`, `registry`, `knowledge_graph` | You compare assets, versions, duplicates, or semantic similarity. |
| `docs/AI_ENTRYPOINT_AND_TOC_ROUTING_STANDARD.md` | Deterministic standard for AI front doors, TOCs, tags, and graph entrypoints. | `front_door`, `workflow`, `learning_loop` | You create or update AI navigation in this repo or another repo. |

## Architecture And Workflows

| Path | What it is | Tags | Use when |
|---|---|---|---|
| `docs/ARCHITECTURE.md` | High-level system architecture. | `workflow`, `authority` | You need the shape of the DAD pipeline. |
| `docs/ASSET_IDENTITY_AND_SIMILARITY_LADDER.md` | Identity, fingerprint, chunk, similarity, graph, and audit layers. | `knowledge_graph`, `workflow`, `calibration` | You decide whether assets are exact, similar, variants, or graph-related. |
| `docs/DATA_FLOW.md` | Data movement and authority boundaries. | `authority`, `workflow`, `security_privacy` | You change scan, process, graph, or reporting flow. |
| `docs/KNOWLEDGE_GRAPH_MODEL.md` | Conceptual graph model and authority posture. | `knowledge_graph`, `authority` | You interpret nodes, edges, graph centrality, or graph limitations. |
| `docs/ASSET_VALUE_MODEL.md` | Value scoring concepts, current score, ceiling, and calibration language. | `calibration`, `workflow` | You review scores, score ranges, lift, or usefulness. |
| `docs/ORPHAN_ACTIVATION_AND_SYNERGY_RADAR.md` | Orphan, activation, missing-part, and synergy model. | `knowledge_graph`, `calibration` | You look for assets that could become useful through connection. |
| `docs/BACKGROUND_CONNECTION_RADAR.md` | Two-speed design for low-compute background connection scouting and bounded high-intensity verification. | `knowledge_graph`, `workflow`, `learning_loop` | You want DAD to surface new connections between current attention and cold-storage assets. |
| `docs/LESSONS_AND_HANDOFF_LOOP.md` | Lesson and handoff capture workflow. | `learning_loop`, `workflow` | You need to preserve reusable work knowledge. |
| `docs/ASSET_USE_PAY_FORWARD_LOOP.md` | Before/after asset-use feedback workflow for all asset classes. | `learning_loop`, `workflow` | You use an asset and need to pay forward usefulness and reuse notes. |
| `docs/LESSON_AUTOMATION_COVERAGE.md` | No-rescan coverage and scan-cycle workflow for future lesson automation. | `learning_loop`, `coverage_cycle`, `generated_output` | You need to start with unscanned signal families or avoid repeating broad scans. |
| `docs/DETERMINISTIC_LEARNING_RULES.md` | Reviewed learning rules surfaced by preflight and midflight. | `learning_loop`, `authority`, `workflow` | Preflight flags rules or you are adding a future-agent rule. |
| `docs/LOAD_BEARING_DECISION_REVIEW.md` | Risk-tier gate for downstream-impact decisions. | `workflow`, `authority`, `calibration` | A decision affects schemas, scoring, roadmap gates, or future defaults. |
| `docs/SOFTWARE_REPO_CHECKLIST_TREE.md` | Checklist tree for software, repo, data, workflow, scoring, governance, source-scan, and release work. | `workflow`, `validation`, `security_privacy` | You plan or implement non-trivial repo work. |
| `docs/WORKFLOW_SWEEPS.md` | Governance-first candidate sweeps for workflow assets across repos. | `workflow`, `cross_repo`, `generated_output` | You need to find workflow assets from scans. |
| `docs/CROSS_REPO_WORKFLOW_ASSET_PATTERNS.md` | Reusable workflow patterns found across major repo families. | `workflow`, `cross_repo`, `knowledge_graph` | You want to compose or recognize workflows across repos. |
| `docs/CROSS_REPO_GOVERNANCE_DEPENDENCY_MAP_PATTERN.md` | Reusable pattern and adoption guide for upstream governance maps, child mirrors, discovery surfaces, PR disclosure, validators, and tests. | `workflow`, `cross_repo`, `governance`, `template_library`, `validation` | You design or scan for repo-family governance dependency-map patterns. |
| `docs/PROFESSIONAL_RECRUITING_INTELLIGENCE_WORKFLOW.md` | Official-source professional identity, enrichment, recruiting, acquisition, and liftout workflow. | `workflow`, `public_safe`, `security_privacy` | You are modeling attorney/professional intelligence without importing private rows. |
| `docs/PUBLIC_SAFE_SOURCE_SWEEPS.md` | Metadata-only sweep workflow for private sources. | `public_safe`, `security_privacy`, `workflow` | You need reusable lessons from sensitive repos without copying data. |
| `docs/NEVADA_BAR_PUBLIC_SAFE_IMPORT_POLICY.md` | Public-safe boundary for Nevada Bar workflow reuse. | `public_safe`, `security_privacy`, `authority` | You scan Nevada-style sources and must avoid row-level import. |
| `docs/SEMANTIC_EVOLUTION_GRADING.md` | Deterministic grading scale for real semantic evolution versus copy noise. | `calibration`, `knowledge_graph`, `workflow` | You compare near-duplicates, temp copies, changelogs, or variants. |
| `docs/PUBLIC_ASSET_USE_FEEDBACK.md` | Public PR path and untrusted-input rules for asset-use feedback. | `learning_loop`, `security_privacy`, `public_safe` | External users or agents report how they used an asset. |
| `docs/LOGOS_REUSABLE_ASSET_FINDINGS.md` | Logos-derived asset-family and learning-loop patterns generalized beyond Bible projects. | `workflow`, `knowledge_graph`, `cross_repo` | You recognize chunking, eval, route, or learning-loop systems. |
| `docs/CONTEXTUAL_LEARNING_AND_WORKTREE_ARCHAEOLOGY.md` | Context-bound lessons from worktrees, temp repos, and history. | `learning_loop`, `cross_repo`, `workflow` | You mine worktree or history signals for lessons. |
| `docs/AI_GOVERNANCE.md` | AI governance rules and expectations. | `authority`, `workflow` | You are adjusting agent behavior. |
| `docs/SECURITY_AND_PRIVACY.md` | Security, privacy, secret, and public-readiness posture. | `security_privacy`, `authority` | You touch sensitive data, generated outputs, feedback, or public-safe rules. |
| `docs/ORPHAN_RADAR_INTEGRATION.md` | How orphan radar connects into the broader system. | `knowledge_graph`, `workflow` | You wire orphan or activation outputs into reports. |
| `docs/RESEARCH_BASIS.md` | Research basis and rationale for DAD patterns. | `workflow`, `calibration` | You need background justification before extending the model. |
| `docs/DUAL_PROPOSAL_ENGINE_RESEARCH_AND_BUILD_PLAN.md` | Research-backed bottom-up and top-down proposal engine plan. | `workflow`, `calibration`, `knowledge_graph` | You work on proposal generation or engine comparison. |

## Knowledge Graph Entrypoints

| Path | What it is | Tags | Use when |
|---|---|---|---|
| `docs/KNOWLEDGE_GRAPH_MODEL.md` | Human-readable graph model and authority boundary. | `knowledge_graph`, `authority` | You need to understand what a graph edge means. |
| `ontology/digital-asset-ontology.ttl` | Ontology for digital asset graph concepts. | `knowledge_graph`, `schema` | You need machine-readable graph classes or relationships. |
| `ontology/taxonomy.skos.ttl` | SKOS taxonomy for broader/narrower concept navigation. | `knowledge_graph`, `registry` | You need concept hierarchy or tag alignment. |
| `registry/edge-type-registry.json` | Controlled edge-type vocabulary. | `knowledge_graph`, `registry` | You add, validate, or interpret graph edges. |
| `registry/asset-pattern-registry.json` | Controlled high-leverage asset pattern vocabulary. | `knowledge_graph`, `registry`, `workflow` | You classify workflows, composite assets, or reusable systems. |
| `registry/context-tag-registry.json` | Controlled context tags for lessons and routing. | `knowledge_graph`, `registry`, `learning_loop` | You constrain when a lesson or pattern applies. |
| `registry/template-registry.json` | Controlled template library with direct and reverse dependencies. | `registry`, `template_library`, `workflow` | You create, update, validate, or reuse templates and need impact analysis. |
| `docs/CROSS_REPO_GOVERNANCE_DEPENDENCY_MAP_PATTERN.md` | Cross-repo governance dependency-map digital asset and scanning checklist. | `knowledge_graph`, `cross_repo`, `workflow`, `template_library` | You need the reusable control-plane/child-mirror pattern or want to recognize missing versions in scanned repos. |
| `registry/capability-registry.json` | Controlled capability IDs. | `knowledge_graph`, `registry` | You connect assets to what they can do. |
| `registry/need-registry.json` | Controlled need and missing-part IDs. | `knowledge_graph`, `registry` | You connect assets to gaps or activation needs. |
| `processed/graph/graph.json` | Generated candidate graph. | `knowledge_graph`, `generated_output` | You need current generated graph evidence; never treat it as truth. |
| `processed/reports/asset_family_recognition.md` | Generated asset-family candidate report. | `knowledge_graph`, `generated_output`, `workflow` | You need candidate composite assets or family patterns. |
| `processed/reports/workflow_sweeps/workflow_sweeps_index.md` | Generated workflow-sweep index. | `knowledge_graph`, `generated_output`, `cross_repo` | You need cross-repo workflow candidates. |
| `processed/reports/workflow_part_recognition.md` | Generated workflow-part candidate report. | `knowledge_graph`, `generated_output`, `workflow_part` | You need recombinable sub-units such as validators, contracts, gates, runners, prompt parts, learning signals, and quarantine gates. |
| `processed/reports/workflow_part_review_sample.md` | Generated workflow-part review queue sample. | `generated_output`, `workflow_part`, `calibration` | You need to review whether detected parts are useful, safe, too broad, or missing declared dataflow. |
| `processed/reports/workflow_part_calibration_review_sample.md` | Stratified generated workflow-part calibration sample. | `generated_output`, `workflow_part`, `calibration` | You need balanced human labels across workflow-part types before using parts in radar, preflight, scoring, or assembly. |
| `processed/reports/workflow_part_review_results_summary.md` | Generated summary of workflow-part human review labels. | `generated_output`, `workflow_part`, `calibration` | You need to see whether workflow-part calibration is still pending or gate-complete. |
| `processed/reports/workflow_part_usage_guidance.md` | Generated manual usage guidance from completed workflow-part labels. | `generated_output`, `workflow_part`, `calibration`, `human_gate` | You need to know which workflow parts may be cited as review context, which require human gates, and which are false-positive/noise patterns. |
| `processed/reports/background_connection_candidates.md` | Generated manual-review report for background connection candidates. | `knowledge_graph`, `generated_output`, `background_connection` | You need candidate links between current attention and cold-storage assets. |
| `processed/reports/background_connection_escalation_packets.md` | Generated bounded review packets for high-score candidate connections. | `knowledge_graph`, `generated_output`, `background_connection` | You need minimal context for fresh-eyes review or future strong-model verification. |
| `processed/reports/manual_task_queue.md` | Generated manual task queue that re-ranks alerts and workflow-part guidance with source-boundary and red-team posture. | `knowledge_graph`, `generated_output`, `workflow_part`, `validation` | You need the safest next human-review tasks from the current alert and workflow-part queues. |
| `processed/reports/repo_buildout/index.md` | Generated repo-specific buildout advisor index. | `knowledge_graph`, `generated_output`, `repo_buildout`, `cross_repo` | You need one cataloged repo's candidate buildout plan, internal combinations, safe cross-repo inspirations, and fresh-eyes prompt. |
| `processed/reports/template_library.md` | Generated template dependency, reverse-dependency, and review-cadence report. | `generated_output`, `template_library`, `workflow` | You need to know which templates are stale, what they depend on, and what depends on them. |
| `processed/reports/scan_coverage_cycle.md` | Generated scan-cycle log showing checked, skipped, and next signal families. | `generated_output`, `coverage_cycle`, `learning_loop` | You need to know where the next agent should scan without repeating old passes. |

## Contracts

| Path | What it is | Tags | Use when |
|---|---|---|---|
| `schemas/asset.schema.json` | Asset record contract. | `schema`, `authority` | You change or validate catalog asset records. |
| `schemas/asset-chunk.schema.json` | Asset chunk contract. | `schema`, `knowledge_graph` | You change chunking, retrieval, or text span records. |
| `schemas/asset-identity-layer.schema.json` | Identity-layer record contract. | `schema`, `knowledge_graph` | You change exact, metadata, chunk, semantic, or graph identity evidence. |
| `schemas/asset-delta.schema.json` | Asset delta contract. | `schema`, `knowledge_graph` | You compare variants or cluster differences. |
| `schemas/semantic-evolution.schema.json` | Semantic-evolution candidate contract. | `schema`, `calibration` | You record semantic change versus noise. |
| `schemas/duplicate-cluster.schema.json` | Duplicate cluster contract. | `schema`, `knowledge_graph` | You group exact, near, or variant assets. |
| `schemas/asset-pattern.schema.json` | Asset pattern record contract. | `schema`, `knowledge_graph`, `workflow` | You add or validate reusable pattern candidates. |
| `schemas/edge.schema.json` | Graph edge contract. | `schema`, `knowledge_graph` | You create or validate asset relationships. |
| `schemas/lesson.schema.json` | Lesson record contract. | `schema`, `learning_loop` | You capture reusable lessons. |
| `schemas/learning-rule.schema.json` | Reviewed learning-rule contract. | `schema`, `learning_loop`, `authority` | You add rules that preflight or midflight can surface. |
| `schemas/learning-loop.schema.json` | Learning-loop candidate contract. | `schema`, `learning_loop` | You generate learning-loop candidates. |
| `schemas/workflow-part.schema.json` | Workflow-part candidate contract. | `schema`, `workflow_part`, `knowledge_graph` | You generate or validate recombinable workflow sub-units beneath existing asset patterns. |
| `schemas/workflow-part-review.schema.json` | Workflow-part human review label contract. | `schema`, `workflow_part`, `calibration` | You label workflow-part candidates for usefulness, safety, specificity, dataflow completeness, and review-use decision. |
| `schemas/template-record.schema.json` | Template registry record contract. | `schema`, `template_library`, `workflow` | You register or validate reusable templates, dependencies, review cadence, and update policies. |
| `schemas/context-tag.schema.json` | Context tag contract. | `schema`, `registry`, `learning_loop` | You add or validate context vocabulary. |
| `schemas/worktree-attempt.schema.json` | Worktree attempt contract. | `schema`, `learning_loop`, `cross_repo` | You mine temp or worktree attempts. |
| `schemas/repo-timeline-event.schema.json` | Repo timeline event contract. | `schema`, `learning_loop`, `cross_repo` | You mine bounded local git history. |
| `schemas/change-pattern.schema.json` | Change pattern contract. | `schema`, `learning_loop` | You identify repeated change signals. |
| `schemas/failure-signal.schema.json` | Failure signal contract. | `schema`, `learning_loop` | You capture failure-like evidence as data. |
| `schemas/root-cause-hypothesis.schema.json` | Root-cause hypothesis contract. | `schema`, `learning_loop` | You propose context-bound causes from evidence. |
| `schemas/counterfactual-lesson.schema.json` | Counterfactual lesson contract. | `schema`, `learning_loop` | You record better-order lessons with applicability limits. |
| `schemas/repo-learning-event.schema.json` | Repo-local learning event contract. | `schema`, `learning_loop` | You capture before, during, after, or review events. |
| `schemas/attention-seed.schema.json` | Background radar attention seed contract. | `schema`, `background_connection`, `security_privacy` | You define privacy-first attention inputs without raw chat persistence. |
| `schemas/connection-candidate.schema.json` | Background radar connection candidate contract. | `schema`, `background_connection`, `knowledge_graph` | You score candidate links with gate-before-score semantics. |
| `schemas/escalation-packet.schema.json` | Background radar escalation packet contract. | `schema`, `background_connection`, `workflow` | You package bounded evidence for manual or future verifier review. |
| `schemas/expansion-map.schema.json` | Background radar expansion map contract. | `schema`, `background_connection`, `knowledge_graph` | You inspect capped direct and second-hop graph expansion. |
| `schemas/repo-buildout-recommendation.schema.json` | Repo buildout recommendation contract. | `schema`, `repo_buildout`, `workflow` | You generate or validate candidate repo-specific buildout recommendations. |
| `schemas/handoff.schema.json` | Handoff contract. | `schema`, `learning_loop` | You transfer context between agents. |
| `schemas/alert.schema.json` | Alert contract. | `schema`, `knowledge_graph` | You emit reviewable alerts. |
| `schemas/source.schema.json` | Source config contract. | `schema`, `authority` | You add or validate scanned sources. |
| `schemas/synergy.schema.json` | Synergy candidate contract. | `schema`, `knowledge_graph`, `calibration` | You propose useful asset combinations. |
| `schemas/activation-trigger.schema.json` | Activation trigger contract. | `schema`, `knowledge_graph` | You record what would activate an asset. |
| `schemas/capability-recommendation.schema.json` | Capability recommendation contract. | `schema`, `knowledge_graph` | You suggest missing capabilities or helpers. |
| `schemas/proposal.schema.json` | Proposal record contract. | `schema`, `calibration`, `workflow` | You generate or review bottom-up/top-down proposals. |
| `schemas/proposal-review.schema.json` | Proposal review contract. | `schema`, `calibration` | You label proposals for usefulness, safety, novelty, and actionability. |
| `schemas/asset-calibration-review.schema.json` | Asset calibration review contract. | `schema`, `calibration` | You label current value scores and notes. |
| `examples/proposals/bottom-up-proposal.example.json` | Example bottom-up proposal. | `schema`, `calibration` | You need a valid bottom-up proposal shape. |
| `examples/proposals/top-down-proposal.example.json` | Example top-down proposal. | `schema`, `calibration` | You need a valid top-down proposal shape. |

## Controlled Vocabularies

| Path | What it is | Tags | Use when |
|---|---|---|---|
| `registry/asset-type-registry.json` | Controlled asset type vocabulary. | `registry`, `knowledge_graph` | You classify what an asset is. |
| `registry/asset-pattern-registry.json` | High-leverage asset pattern vocabulary. | `registry`, `knowledge_graph`, `workflow` | You classify reusable systems and composite workflows. |
| `registry/context-tag-registry.json` | Context tags for lesson and routing constraints. | `registry`, `learning_loop` | You define when lessons apply or do not apply. |
| `registry/workflow-part-type-registry.json` | Controlled workflow-part role vocabulary. | `registry`, `workflow_part`, `knowledge_graph` | You classify recombinable workflow parts such as validators, contracts, gates, runners, and learning signals. |
| `registry/learning-rule-registry.json` | Reviewed deterministic learning rules. | `registry`, `learning_loop`, `authority` | You change preflight/midflight surfaced rules. |
| `registry/semantic-evolution-grade-registry.json` | Semantic evolution grade thresholds. | `registry`, `calibration` | You grade change versus noise. |
| `registry/identity-layer-registry.json` | Identity/similarity layer definitions. | `registry`, `knowledge_graph` | You compare assets at exact, chunk, semantic, or graph layers. |
| `registry/edge-type-registry.json` | Graph relationship vocabulary. | `registry`, `knowledge_graph` | You add or interpret edges. |
| `registry/lifecycle-registry.json` | Lifecycle vocabulary. | `registry`, `workflow` | You classify asset maturity or status. |
| `config/taxonomy.yaml` | Configured taxonomy. | `registry`, `knowledge_graph` | You need YAML taxonomy inputs. |
| `ontology/digital-asset-ontology.ttl` | Ontology graph model. | `knowledge_graph`, `schema` | You need RDF/semantic graph structure. |
| `ontology/taxonomy.skos.ttl` | SKOS taxonomy. | `knowledge_graph`, `registry` | You need concept hierarchy. |

## Operations

| Path | What it is | Tags | Use when |
|---|---|---|---|
| `config/sources.example.yaml` | Example source configuration. | `workflow`, `authority` | You configure local scan scope. |
| `docs/OPERATIONS.md` | Operational command and runbook guidance. | `workflow`, `validation` | You run DAD tasks. |
| `asset-dir doctor` | Local operational readiness check that does not rescan or mutate sources. | `validation`, `workflow`, `generated_output` | You need one command to verify front-door, catalog, roadmap, generated surfaces, and readiness warnings. |
| `docs/TEMPLATE_LIBRARY_GOVERNANCE.md` | Template library dependency and upgrade-governance rules. | `template_library`, `workflow`, `validation` | You create, update, review, or validate reusable templates. |
| `asset-dir templates check` | Template registry validator and generated dependency report command. | `template_library`, `validation`, `generated_output` | You need template dependency impact analysis or periodic template review. |
| `asset-dir templates validate` | No-write template registry validation command. | `template_library`, `validation` | You need to check template graph metadata without writing generated reports. |
| `docs/PROPOSAL_ENGINE_CALIBRATION_WORKFLOW.md` | Proposal review workflow. | `calibration`, `workflow` | You review bottom-up and top-down proposal engines. |
| `asset-dir recommend workflow-sweeps` | CLI command for generated workflow-family sweep reports. | `workflow`, `generated_output`, `cross_repo` | You need generated workflow candidates. |
| `asset-dir recommend workflow-parts` | CLI command for generated workflow-part candidates from the current catalog. | `workflow`, `workflow_part`, `generated_output` | You need recombinable sub-unit candidates without rescanning or mutating source repos. |
| `asset-dir recommend workflow-part-review-template` | CLI command for a stratified workflow-part review template. | `workflow_part`, `calibration`, `generated_output` | You need a balanced sample before human labels or fresh-eyes review. |
| `asset-dir recommend workflow-part-review-queue` | CLI command for pending or reviewed workflow-part labels. | `workflow_part`, `calibration` | You review candidates in chat or inspect label context. |
| `asset-dir recommend workflow-part-review-label` | CLI command to apply one human-approved workflow-part label. | `workflow_part`, `calibration`, `human_gate` | Lowell has approved a specific workflow-part review label. |
| `asset-dir recommend workflow-part-calibration-evidence` | Fail-closed evidence export for workflow-part calibration. | `workflow_part`, `calibration`, `roadmap` | You have enough human labels and structured notes to track curated calibration evidence. |
| `asset-dir recommend workflow-part-guidance` | Generated manual guidance command for reviewed workflow parts. | `workflow_part`, `calibration`, `generated_output`, `human_gate` | You need review-use, human-gated, rejected/noise, and missing-dataflow boundaries before citing workflow parts. |
| `asset-dir recommend manual-tasks` | Generated manual task queue over current alerts and workflow-part guidance. | `workflow`, `knowledge_graph`, `generated_output`, `workflow_part` | You need ranked manual tasks, family grouping, local research support, and red-team caveats before acting on alerts. |
| `asset-dir recommend repo-buildout` | Generated repo-specific buildout advisor command. | `repo_buildout`, `knowledge_graph`, `workflow`, `generated_output` | You want DAD to recommend how to improve one cataloged repo without rescanning or mutating it. |
| `asset-dir recommend lesson-automation-coverage` | Generated no-rescan coverage report and scan-cycle log. | `coverage_cycle`, `learning_loop`, `generated_output` | You need a queue of unscanned repos, unscanned signal families, and next-cycle gates. |
| `asset-dir recommend background-connections` | CLI command for manual, local-only background connection scouting. | `background_connection`, `generated_output`, `knowledge_graph` | You want bounded candidate connections without rescanning, daemon work, GitHub, or model calls. |
| `docs/DOWNSTREAM_REPO_GOVERNANCE.md` | Downstream governance install and pilot guidance. | `workflow`, `authority`, `cross_repo` | You prepare a sandbox or downstream pilot. |
| `docs/TESTING_AND_ORCHESTRATION.md` | Marker taxonomy, change-driven test selection, and nox tasks. | `validation`, `workflow` | You select or explain tests. |
| `docs/ALGORITHM_CALIBRATION_AND_FIXES_HANDOFF.md` | Algorithm fixes and calibration handoff. | `calibration`, `workflow` | You work on similarity, scoring, confidence, or threshold calibration. |
| `scripts/bootstrap.ps1` | Bootstrap script. | `workflow`, `validation` | You set up a repo environment. |
| `scripts/install_to_target.ps1` | Downstream install script. | `workflow`, `cross_repo` | You install governance into an approved target. |
| `scripts/new_repo.ps1` | Scaffold a new repository pre-wired to this hub. | `workflow`, `cross_repo` | You create a sandbox or new DAD-connected repo. |
| `scripts/claude_hook.py` | Claude hook integration. | `workflow`, `learning_loop` | You inspect or adjust Claude-side hooks. |
| `scripts/register_scheduled_scan.ps1` | Scheduled scan registration script. | `workflow`, `validation` | You explicitly enable scheduled scans after gates. |
| `scripts/unregister_scheduled_scan.ps1` | Scheduled scan removal script. | `workflow`, `validation` | You disable scheduled scans. |
| `templates/asset-use-feedback.template.md` | Copyable public feedback template. | `learning_loop`, `public_safe` | Someone reports asset use through PR or repo-local feedback. |
| `templates/load-bearing-decision-review.template.md` | Fresh-eyes red-team and premortem template. | `workflow`, `calibration` | A high-risk decision needs independent review. |
| `templates/software-repo-checklist-tree.template.md` | Reusable checklist-tree record. | `workflow`, `validation` | You document selected checklist branches. |
| `templates/ai-table-of-contents.template.md` | Reusable AI TOC template with descriptions, tags, and use-when triggers. | `front_door`, `workflow`, `learning_loop` | You build AI navigation for this repo or another repo. |
| `templates/downstream/AGENTS_MANAGED_BLOCK.md` | Managed downstream governance block template. | `template_library`, `workflow`, `cross_repo` | A downstream repo is explicitly approved for DAD governance installation. |
| `templates/cross-repo-governance-dependency-map/` | Template seed for upstream governance maps, child mirrors, front-door and TOC sections, repo contracts, PR sections, validators, tests, and handoff/adoption checklists. | `template_library`, `governance`, `cross_repo`, `validation` | A future repo family needs deterministic governance dependency mapping from day one. |

## Roadmap

| Path | What it is | Tags | Use when |
|---|---|---|---|
| `roadmap/roadmap.yaml` | Roadmap phases and gates. | `roadmap`, `authority` | You inspect or change phase expectations. |
| `roadmap/gate-evidence.json` | Tracked human-gate and validation-command evidence. | `roadmap`, `authority`, `validation` | You decide whether a phase gate is proven. |
| `roadmap/state.json` | Roadmap state data. | `roadmap` | You inspect computed or recorded roadmap status. |
| `docs/ROADMAP_EXECUTION.md` | Roadmap execution rules. | `roadmap`, `workflow` | You plan phase work or evidence export. |
| `roadmap/evidence/contextual-learning-archaeology.md` | Archaeology counts, caveats, and review needs. | `roadmap`, `learning_loop`, `generated_output` | You use worktree/history learning evidence. |
| `roadmap/evidence/deterministic-learning-rules.md` | Reviewed learning-rule seed evidence. | `roadmap`, `learning_loop` | You need why rules became deterministic. |
| `roadmap/evidence/load-bearing-decision-review-asset.md` | Evidence that risk-tier review is a reusable asset. | `roadmap`, `workflow` | You evaluate load-bearing decision governance. |
| `roadmap/evidence/software-repo-checklist-tree.md` | Evidence for the checklist-tree workflow asset. | `roadmap`, `workflow` | You apply or revise software/repo checklists. |
| `roadmap/evidence/cross-repo-workflow-asset-sweep.md` | Workflow-pattern sweep evidence across repo families. | `roadmap`, `cross_repo`, `workflow` | You inspect cross-repo workflow candidates. |
| `roadmap/evidence/nevada-bar-public-safe-source-scope.md` | Nevada metadata-only public-safe source boundary. | `roadmap`, `public_safe`, `security_privacy` | You need public-safe source-scope evidence. |
| `roadmap/evidence/semantic-evolution-grading.md` | Semantic evolution versus noise evidence. | `roadmap`, `calibration`, `knowledge_graph` | You calibrate variant/delta reviews. |
| `roadmap/evidence/phase-1.5-scoring-discipline.md` | Scoring discipline and clean-sampling checkpoint evidence. | `roadmap`, `calibration` | You need why noisy copies were gated. |
| `roadmap/evidence/phase-1.5-human-review.md` | Phase 1.5 human review gate decisions. | `roadmap`, `calibration` | You inspect human review decisions. |
| `roadmap/evidence/phase-2-temp-fixture-calibration-research.md` | First-batch temp fixture calibration research. | `roadmap`, `calibration` | You review why temp copies were scored conservatively. |
| `roadmap/evidence/phase-2-claude-second-opinion.md` | Intake file for Claude's independent calibration findings. | `roadmap`, `calibration` | You compare independent review notes. |
| `roadmap/evidence/phase-2-claude-red-team-premortem.md` | Claude red-team premortem on calibration risks. | `roadmap`, `calibration` | You need failure modes before trusting scores. |
| `roadmap/evidence/phase-2-asset-calibration.md` | Tracked Phase 2 calibration gate evidence after labels. | `roadmap`, `calibration` | You verify asset calibration evidence. |
| `roadmap/evidence/phase-2-calibration-human-review-research.md` | Human review rationale, label policy, and score-change recommendations. | `roadmap`, `calibration` | You inspect label policy or score-change reasoning. |
| `roadmap/evidence/phase-2-calibration-label-table.csv` | Compact table of Phase 2 asset-rating labels. | `roadmap`, `calibration` | You audit label records. |
| `roadmap/evidence/phase-2.5-content-aware-scoring.md` | Content-aware scoring recommendation and red-team notes. | `roadmap`, `calibration` | You work on downstream score use. |
| `roadmap/evidence/nevada-bar-professional-intelligence-workflow.md` | Evidence for Nevada professional intelligence workflow family. | `roadmap`, `workflow`, `public_safe` | You reuse the Nevada workflow pattern without private data. |
| `roadmap/evidence/ai-entrypoint-toc-routing-standard.md` | Evidence for the AI front-door and deterministic TOC routing standard. | `roadmap`, `front_door`, `learning_loop` | You need why AI navigation became a reusable rule. |
| `roadmap/evidence/background-connection-radar-design.md` | Evidence that the background connection radar is designed but not enabled. | `roadmap`, `knowledge_graph`, `learning_loop` | You need status, risks, or gates before implementing background connection discovery. |
| `roadmap/evidence/background-connection-radar-synthesis.md` | Synthesis of Codex's radar design and Claude's workflow-composition red-team. | `roadmap`, `knowledge_graph`, `workflow` | You need the reuse-first design decision before implementing connection or workflow-part logic. |
| `roadmap/evidence/claude-background-connection-radar-review.md` | Claude's fresh-eyes review adding gate-before-score math, privacy-first attention, compute caps, and family dedup. | `roadmap`, `knowledge_graph`, `calibration` | You need the independent hardening review before implementing background connection scoring or escalation. |
| `roadmap/evidence/background-connection-radar-v1-implementation.md` | Implementation evidence, red-team, premortem, validation, and risks for manual radar v1. | `roadmap`, `background_connection`, `validation` | You verify what v1 shipped and why it remains candidate-only. |
| `roadmap/evidence/workflow-part-record-phase-a.md` | Implementation evidence for WorkflowPartRecord Phase A. | `roadmap`, `workflow_part`, `validation` | You need the contract, conservative defaults, risks, and validation status for workflow-part recognition. |
| `roadmap/evidence/workflow-part-calibration-review-path.md` | Evidence for workflow-part calibration review commands and fail-closed gate. | `roadmap`, `workflow_part`, `calibration` | You need to know how workflow-part candidates should be reviewed before radar, preflight, scoring, or assembly use. |
| `roadmap/evidence/workflow-part-usage-guidance.md` | Evidence for the manual workflow-part usage guidance surface after calibration. | `roadmap`, `workflow_part`, `calibration`, `human_gate` | You need the risk tier, boundaries, and next gate before using reviewed workflow parts operationally. |
| `roadmap/evidence/operational-readiness-doctor.md` | Evidence for the local-only `doctor` readiness command. | `roadmap`, `validation`, `workflow` | You need to know what the readiness command proves and what it does not prove. |
| `roadmap/evidence/manual-task-queue-prioritization.md` | Evidence, formula, local research support, and red-team for manual task queue prioritization. | `roadmap`, `knowledge_graph`, `workflow_part`, `validation` | You need why alerts are re-ranked before human work and what the queue must not be used to justify. |
| `roadmap/evidence/repo-buildout-advisor-v1.md` | Evidence, formula, red-team, and boundaries for repo-specific buildout advice. | `roadmap`, `repo_buildout`, `knowledge_graph`, `validation` | You need why repo buildout recommendations are generated-only and how their priority score is derived. |
| `roadmap/evidence/template-library-governance-v1.md` | Evidence for tracked template dependency governance and update boundaries. | `roadmap`, `template_library`, `validation` | You need why templates became first-class dependency-tracked assets. |
| `roadmap/evidence/cross-repo-governance-dependency-map-pattern.md` | Implementation evidence, premortem, red-team, and validation plan for the cross-repo governance dependency-map asset. | `roadmap`, `cross_repo`, `governance`, `template_library` | You need why the pattern was added and what remains candidate or human-gated. |
| `roadmap/evidence/lesson-automation-coverage-v1.md` | Evidence for no-rescan lesson-automation coverage and scan-cycle logging. | `roadmap`, `coverage_cycle`, `learning_loop`, `validation` | You need why the coverage command exists and what it must not be used to prove. |
| `roadmap/evidence/claude-workflow-composition-red-team.md` | Claude's independent warning against ontology sprawl and recommendation for WorkflowPartRecord. | `roadmap`, `workflow`, `knowledge_graph` | You need the fresh-eyes review behind the background-radar synthesis. |
| `roadmap/evidence/phase-3-sandbox-pilot.md` | Sandbox downstream-governance pilot evidence. | `roadmap`, `downstream_governance`, `validation` | You verify Phase 3 gates or learn how the files-only learning loop was tested. |
| `roadmap/evidence/phase-4-semantic-enrichment.md` | Conservative Phase 4 semantic-enrichment boundary and evaluation evidence. | `roadmap`, `semantic_enrichment`, `privacy` | You need to know what Phase 4 approved, what remains deferred, or why embeddings are still gated. |
| `roadmap/evidence/phase-5-alerting-and-research-radar.md` | Conservative Phase 5 manual-alert/radar boundary and external-research gates. | `roadmap`, `alerting`, `external_research` | You need to know what alerting/research surfaces are approved and what remains gated. |
| `roadmap/evidence/claude-post-merge-roadmap-red-team.md` | Claude's post-merge red-team of roadmap completion, human gates, and external-call risks. | `roadmap`, `fresh_eyes_review`, `human_gate` | You need the independent critique behind roadmap gate hardening. |
| `roadmap/evidence/roadmap-gate-hardening.md` | Remediation evidence for strict human-gate verification, boundary-deferred status, and external research enablement. | `roadmap`, `human_gate`, `security_privacy` | You need why some phases intentionally no longer compute complete after hardening. |
| `roadmap/evidence/human-gate-review-2026-06-29.md` | Lowell's human-review decisions for reopened Phase 1, Phase 3, and Phase 4/5 boundary gates. | `roadmap`, `human_gate`, `boundary_deferred` | You need the human decision trail after roadmap gate hardening. |

## Reference

| Path | What it is | Tags | Use when |
|---|---|---|---|
| `docs/DATA_DICTIONARY.md` | Field meanings and authority posture. | `schema`, `authority` | You need field semantics. |
| `registry/capability-registry.json` | Controlled capability IDs. | `registry`, `knowledge_graph` | You map assets to capabilities. |
| `registry/need-registry.json` | Controlled missing-part IDs. | `registry`, `knowledge_graph` | You map assets to needs or missing parts. |
| `VERIFICATION_REPORT.md` | Verified checks, scope, and environment-dependent gaps. | `validation`, `roadmap` | You need prior verification context. |
