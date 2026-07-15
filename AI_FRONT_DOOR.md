# AI Front Door - Digital Asset Directory

## Concurrent Work Default

DAD often has multiple agents, branches, mail runs, Rust rollout tasks, and
human edits active at the same time. Assume concurrent work is happening unless
current evidence proves otherwise.

Before material edits, do not work directly in the live checkout unless a human
explicitly asks for that. Create or switch to an isolated branch/worktree from
the current remote tip, then rerun the required preflight and read order inside
that isolated checkout:

```text
git fetch origin
git worktree add -b <codex/task-branch> <isolated-worktree-path> origin/main
asset-dir agent preflight --repo <isolated-worktree-path> --agent <agent> --task "<task>" --hub <isolated-worktree-path>
```

If an existing isolated worktree is reused, first verify its branch, base, and
dirty state. Never overwrite, reset, merge, rebase, or clean another agent's
working tree without an explicit human instruction.

For DAD-hub changes, pass `--hub <isolated-worktree-path>` on DAD CLI commands
run inside the branch/worktree. Do not let the user-level DAD locator or shim
silently redirect preflight, postflight, generated reports, or mail diagnostics
back to another checkout.

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

## Navigation freshness

DAD changes quickly. Do not compare this repo to memory of an older table of
contents. After this front door, check `registry/ai-navigation-registry.json`
for `navigation_version`, `updated_at`, `recent_changes`, and affected
`branch_map` rows.

The mailbox, library catalog, graph reports, and generated evidence are
branches from this front door, not competing entrypoints. Dates and version
signals live in the navigation registry so the AI table of contents can stay
shallow and descriptive instead of becoming a bulky change log.

## MCP-First Integrations

DAD internal agent integrations default to MCP over direct vendor APIs. MCP
resources expose read-only DAD context, MCP tools wrap bounded DAD CLI actions,
and MCP prompts package repeatable workflows. Direct APIs and vendor SDKs are
fallback adapters only when MCP cannot express the integration and a reviewed
human gate approves the exception.

Read `docs/MCP_FIRST_INTEGRATION_POLICY.md` before creating or reviewing an MCP
server, plugin, connector, cloud agent, API bridge, or runtime adapter.
Read `docs/DAD_MCP_ADOPTION_AND_REGISTRATION_SCAFFOLD.md` before registering
DAD's local MCP server in Codex, Cursor, Claude Code, or another downstream
host. That scaffold is documentation and request-template guidance only; it
does not install, enable, or authorize a global/user MCP configuration change.

## Transport And Data Root

DAD's transport redesign is routed through
`docs/DAD_TRANSPORT_AND_COMMS_REDESIGN.md`. Runtime candidate data belongs under
the active `DAD_DATA_ROOT` local bus or the private `dad-journal` fallback, not
as message PRs. Use `asset-dir data status`, `asset-dir transport audit`,
`asset-dir daemon status`, and `asset-dir journal status` to inspect the current
transport state before changing mail, exception, lesson, report, or ledger
writers.

The Logos family has a stricter asymmetric boundary documented in
`docs/LOGOS_READ_ONLY_BRIDGE.md` and registered in
`registry/logos-repo-authority.json`: Logos-local tooling may write its own
outbox and pull central candidates, while DAD may read approved metadata but
cannot write any Logos filesystem entry. There is no standing or scheduled
approval bypass.

## Required read order

1. `AGENTS.md`
2. `MACHINE_NAVIGATION_MANIFEST.json`
3. `registry/ai-navigation-registry.json`
4. `registry/source-of-truth.json`
5. `registry/design-authority.json`
6. `registry/identity-layer-registry.json`
7. `AI_TABLE_OF_CONTENTS.md`
8. `docs/ARCHITECTURE.md`
9. `docs/ASSET_IDENTITY_AND_SIMILARITY_LADDER.md`
10. task-relevant schemas, registries, and roadmap gates

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
| `docs/DAD_ADDRESS_MODEL.md` | DAD's adopted 9-layer address model, compact fill policy, workflow-card encoding, and evolution rules. | You need to decide how an asset, workflow, exception, or lesson should be addressed without bloating records or replacing graph edges. |
| `registry/dad-address-model-registry.json` | Machine-readable DAD address model with layer definitions, tuple segments, source inspirations, and frontier review policy. | You need the exact layer model for repo-local asset cards, learning loops, workflow/orchestration pointers, or validation. |
| `docs/FABLE_DAD_ADDRESS_MODEL_PROMPT.md` | Prompt for Fable/frontier AI to red-team and improve the DAD address model. | You want a high-leverage critique of layer 9, compact workflow encoding, tests, and evolution policy. |
| `processed/fable5/deep-dives/2026-07-06-dad-deployment-rust-handoff/fable5-master-prompt.md` | Current Fable review packet for the DAD deployment roadmap, Phase 8 local deployment proof, Phase 10A event pipeline, and Rust event-log checker boundary. | You are handing DAD to Fable to audit roadmap order, false-confidence risks, Rust/Python boundaries, or next high-leverage Rust leaf work. |
| `processed/fable5/deep-dives/2026-07-07-graph-surface-mcp-handoff/fable5-master-prompt.md` | Fable review packet for graph surface manifests, MCP-first resources, no-lock-in runtime policy, parallel transport merge context, version tracking, synthetic tests, red-team, and premortem kernels. | You are handing DAD to Fable before building the graph surface registry, MCP graph resources, or repo surface-version tracking. |
| `registry/edge-type-registry.json` | Controlled edge vocabulary. | You create, interpret, or validate graph relationships. |
| `docs/SUBAGENT_EVALUATION_AND_CAPABILITY_GRAPH.md` | Attempt-first subagent identity, rating, evidence, graph, and human consolidation contract. | You record or compare subagent runs, evaluate role revisions, or review keep/combine/promote/supersede candidates. |
| `registry/subagent-evaluation-methodology.json` | Current versioned attempt-rating rubric and evidence thresholds. | You calculate or audit an attempt score; use the pinned snapshot named by each evaluation. |
| `registry/subagent-evaluation-profile-registry.json` | Candidate universal improvement loop plus explicit domain overlays, intervention layers, and preserve-simple policy. | You design or audit self-grading, evaluator integrity, cross-domain improvement, or workflow-versus-agent attribution; never compare domains by one score. |
| `docs/research/SUBAGENT_SELF_GRADING_AND_IMPROVEMENT_RESEARCH_2026-07-13.md` | Primary-source research and DAD architecture for honest self prediction, independent evaluator audit, domain overlays, and no-change decisions. | You need the evidence and tradeoffs behind `subagents self-assess` or `subagents integrity-review`. |
| `processed/agents/subagent-capability-graph.json` | Generated candidate graph over role revisions, attempts, evaluations, capabilities, model claims, and repositories. | You need processed subagent evidence; never use it as a model leaderboard or automatic routing authority. |
| `processed/agents/subagent-role-directory.json` | Generated candidate directory over explicitly registered PM/workflow role packs, with exact evaluation-revision links only. | You need to find a declared subagent role by identity, capability, or task phrase without dispatching or quality-ranking it. |
| `assets/agent-skills/ml-workflow-agent-family/` | Model-independent ML opportunity, technique, experiment, implementation, checking, research, monitoring, and lifecycle family. | You need to decide whether ML fits, find a governed ML role or technique, run a bounded ML workflow, or review ML research and staleness. |
| `registry/ml-agent-family-registry.json` | Machine-readable ML workflows, expiring runtime-adapter observations, lifecycle policy, research cadence, and typed dependencies. | You need the exact routing compatibility, 14-day research, up/down dependency, or adaptation-versus-rewrite contract. |
| `registry/ml-technique-registry.json` | Context-bounded ML technique cards with prerequisites, contraindications, baselines, leakage controls, evaluation, implementation pointers, and lifecycle. | You need to shortlist an ML approach without treating popularity, novelty, or the registry as proof. |
| `registry/asset-pattern-registry.json` | Controlled high-leverage pattern vocabulary. | You classify workflows, composite assets, or reusable systems. |
| `registry/template-registry.json` | Controlled template library with forward and reverse dependencies. | You create, update, validate, or reuse templates. |
| `assets/asset-registry.json` | Local index of installed reusable assets. | You need a reusable asset, package provenance, rollout command, or source path before coding or template work. |
| `assets/ai-engineering-preflight/` | Installed AI engineering preflight asset with Python/Rust agent guidance, templates, prompts, and dry-run rollout scripts. | You are planning AI-assisted software changes, refactors, or repo instruction/template deployment. |
| `assets/python-ai-advantage-preflight/` | Installed Python preflight asset with candidate high-leverage Python tactics, examples, and an agent instruction block. | You are planning Python implementation, API design, or long-script refactor work and need Python-specific tactic guidance. |
| `docs/LANGUAGE_CODING_ADVANTAGE.md` | DAD language-specific AI coding advantage playbook for Python, Rust, and future languages, with source-intake and promotion boundaries. | You add or refresh Python/Rust guidance, evaluate a frontier language technique, or decide whether a language asset should become DAD guidance. |
| `assets/dad-rust-upgrade-starter-pack/README.md` | First-stop guide for understanding DAD's Rust system, rollout packet, and where the Rust assets point. | Another repo or AI asks where to start for DAD Rust guidance. |
| `docs/rust/RUST_ADOPTION_PLAN.md` | DAD Rust adoption plan after the starter pack, with staged adoption context and validation expectations. | You need to understand when DAD should use Rust, how adoption is staged, or what gates apply before more Rust work. |
| `tools/dad_scan_core/` | DAD's installed Rust leaf-tool crate for bounded source scans, mail-spool checks, event-log JSONL checks, and repo-inventory probes. | You need the actual Rust code for deterministic source inventory, hashing, JSONL structural validation, or scanner validation inside DAD. |
| `src/digital_asset_directory/rust_bridge/` | Python-to-Rust orchestration bridge for invoking DAD Rust tools without giving Rust governance authority. | You need to see how Python calls DAD's Rust scan core or where mixed-language boundaries live. |
| `docs/rust/DAD_FORCED_RUST_ROLLOUT_POLICY.md` | DAD Rust rollout policy, Logos exclusion, target ownership model, and local apply boundaries. | You plan Rust rollout, mail packets, target scaffolds, or DAD-first Rust lessons. |
| `docs/rust/RUST_ROLLOUT_LESSON_CAPTURE_PROTOCOL.md` | Rust rollout lesson-capture protocol, ledger shape, summary command, and append-only update rule. | You need to send, review, or validate Rust rollout lessons from DAD or another repo. |
| `docs/CODING_ASSET_CONTROL_PLANE.md` | DAD-side control-plane design for coding assets, tactics, routers, mail packets, and downstream pointers. | You are adding, routing, validating, or reusing AI coding assets. |
| `docs/CODING_HARNESS_LIBRARY.md` | DAD-side coding harness library for test performance, Rust parity, preflight, red-team, governance safety, and provenance workflows. | You create, recommend, evaluate, package, or adopt coding-improvement harnesses. |
| `docs/HARNESS_VS_DETERMINISTIC_ENFORCEMENT.md` | DAD decision model for choosing harnesses, advisory checks, or deterministic enforcement using risk, data sensitivity, and maturity. | You are deciding whether a discovered issue should become a harness, warning, report, or hard gate. |
| `docs/AGENT_SKILL_LIBRARY.md` | DAD-side library for agent skills, lifecycle notices, checkout pointers, and replacement policy. | You are creating, checking out, updating, retiring, or replacing agent skills across repos. |
| `docs/DAD_REPO_ENROLLMENT.md` | Reviewed-wave repo enrollment and control-plane contract for persistent repos. | You plan, apply, update, audit, or explain DAD full governance enrollment. |
| `docs/REPO_LOCAL_DIGITAL_ASSET_DIRECTORY.md` | Repo-local `.digital-asset/assets/` memory standard, compatibility inputs, and fractal placement guidance. | You need a repo to log its own digital assets, compare an existing asset directory to DAD convention, or collect metadata-only asset sightings without mutating the source repo. |
| `registry/control-plane-registry.json` | Reviewed DAD control-plane registry with cadence, surfaces, and normal write boundaries. | You need to know what DAD can advise, update by approval, or touch during recurring operation. |
| `registry/logos-repo-authority.json` | Stable Logos repo identities and unconditional DAD runtime write denial. | You scan, collect from, audit, enroll, deliver to, or otherwise target a Logos-family repo. |
| `registry/dad-needs-registry.json` | DAD request list for lessons, assets, harness feedback, usage feedback, skill updates, and governance drift repos should send back through mail. | A repo needs to know what DAD is looking for. |
| `registry/dad-offerings-registry.json` | Rich DAD card catalog of assets, skills, templates, harnesses, architecture refs, maps, workflows, and known upgrades. | A repo needs to match context to DAD offerings or decide whether to use now, save for future, defer, reject, or ask for human review. |
| `registry/dad-usefulness-methodology.json` | Deterministic scoring method for DAD offering recommendations. | You need to explain why DAD suggested an offering without claiming the score proves truth or value. |
| `registry/asset-recognition-methodology.json` | Candidate scoring method for recognizing useful digital assets from repo paths and metadata without copying private contents. | You need to find high-value assets, instructions, harnesses, schemas, prompts, or maps in a repo scan. |
| `docs/ASSET_RECOGNITION_METHODOLOGY.md` | Human-readable asset-recognition loop and source-boundary rules. | You are deciding what DAD should save, promote, ignore, or ask a repo to send back. |
| `docs/LESSON_LIFECYCLE_GOVERNANCE.md` | Candidate design for lesson review clocks, upgrade, downgrade, improvement, supersession, and archive overlays. | You need to decide whether an old lesson is still useful, stale, harmful, superseded, or ready for promotion review. |
| `registry/agent-skill-library.json` | Governed skill registry with DAD skill IDs, versions, formats, source paths, checkout modes, and lifecycle state. | You need to select or validate a DAD-managed skill before a downstream repo checks it out. |
| `docs/GLOBAL_PERSONAL_SKILLS_GPT.md` | Governed personal-skill source authority, allowlist, inert local-only archive, revision graph, reviewed export, and daily steward contract. | You need to inventory, archive, compare, query, or port Lowell's global personal skills without creating a second active source. |
| `registry/coding-asset-registry.json` | Reusable coding asset registry with applicability, validation, authority boundaries, and source evidence. | You need to select a DAD coding asset before AI-assisted implementation. |
| `registry/language-coding-advantage-registry.json` | Python, Rust, and future-language coding advantage registry with trusted sources, overlooked patterns, harness routes, and adoption gates. | You need language-specific coding guidance or want to route a new language-frontier signal into DAD. |
| `registry/coding-harness-registry.json` | Coding-improvement harness registry with context routing, evidence, prompts, scripts, evals, examples, and package paths. | You need a reusable harness for AI coding improvement or test acceleration research. |
| `registry/harness-discovery-methodology.json` | Candidate radar method for finding missing or underpowered coding harnesses from orphan assets, tactics, lessons, and research leads. | You need to turn repeated coding pain or research opportunities into a reusable harness candidate. |
| `docs/HARNESS_DISCOVERY_RADAR.md` | Human-readable orphan/radar/research-to-harness workflow. | You are asking Fable, Claude, Codex, or another agent to improve DAD's coding harness library. |
| `docs/CLAUDE_ARCHITECTURAL_ROOT_CAUSE_REVIEW.md` | Claude-readable packet guidance for integration and implementation issue patterns that may have architectural root causes. | You see repeated integration failures, boundary mismatch, implementation drift, or a review finding that may need architectural root-cause analysis. |
| `assets/coding-harnesses/exception-capture-completeness/` | Harness for proving DAD-worthy repo patterns become mail, exception, fix, or no-packet decisions with required metadata. | You changed DAD capture patterns, downstream exception guidance, or need the no-chat emission regression. |
| `assets/coding-harnesses/exception-learning-readiness/` | Synthetic harness for checking conservative exception learning queue statuses. | You changed exception learning, fix outcomes, release blockers, sample thresholds, or backfill promotion boundaries. |
| `registry/coding-tactics-radar.json` | Candidate Python, Rust, and agent-instruction tactics with examples, risks, and promotion status. | You need tactic recommendations or postflight tactic feedback targets. |
| `registry/preflight-profile-router.json` | Task/context router from repo/language/risk signals to DAD profiles, tactics, validation, and stop conditions. | You need to choose the right preflight profile or run a midflight tactic recommendation. |
| `docs/CROSS_REPO_GOVERNANCE_DEPENDENCY_MAP_PATTERN.md` | Reusable cross-repo governance map and child-mirror template pattern. | You design a repo family where upstream governance and child repo mirrors must stay aligned. |
| `docs/MAIL_CENTER.md` | Governed DAD mail hub, repo-local inbox/outbox mirror, dirty-spool doctor protocol, and warning-only QRD/IFC lesson receiver boundary. | You need candidate lessons, workflows, assets, taxonomy, capabilities, or governance notices to move across repos, need the synthetic lesson receiver contract, or Rust rollout/concurrent repo mail looks dirty. |
| `docs/LOGOS_READ_ONLY_BRIDGE.md` | Asymmetric Logos communication and fail-closed DAD write guard. | You need Logos-to-DAD communication without granting DAD a reverse write channel. |
| `docs/DAD_EVENT_PIPELINE.md` | Local-first event/data pipeline contract beneath mail, with repo event outboxes, central candidate event logs, response-state rows, quarantine, and Rust leaf-check boundaries. | You need repo learning-loop responses, asset-use events, exception/fix outcomes, or DAD notice adoption to be explicit instead of inferred from mail presence. |
| `docs/DAD_MAIL_STORM_AND_DIRTY_STATE_RUNBOOK.md` | Operator runbook for distinguishing true mailbox/staged-packet dirt from ordinary dirty worktree or Rust reference-snapshot churn. | Multiple repos or branches are sending DAD mail, Rust rollout lessons, or learning-loop packets and the tree looks very dirty. |
| `docs/PR_BRANCH_LIFECYCLE_GOVERNANCE.md` | DAD lesson and repo-facing governance pattern for preventing PR-ready branches and open PRs from becoming stale conflict debt. | Work is PR-ready, an actual PR is open, branches are accumulating, or a handoff needs owner, next action, and escalation-clock evidence. |
| `docs/DAD_PORTFOLIO_AI_OPERATING_SYSTEM_PLAN.md` | Active portfolio AI operating-system plan covering projects, ideas, workstreams, worktrees, resume capsules, conditional attention, creative-sprawl shaping, the strict read-only `os review` packet, and governed execution. | You need to organize creative multi-repo work, split ideas into isolated workstreams, recover forgotten work, or continue the DAD portfolio OS buildout. |
| `asset-dir os agents` | Read-only categorical search over registered project-management and trigger-pattern role contracts. | You need a candidate PM, recovery, research, dependency, board, trigger, or delivery role while preserving human routing authority. |
| `asset-dir os trigger-feedback` | Privacy-minimized categorical projection over exact focus-trigger signatures and explicit user actions. | You need trigger shadow-trial evidence without copying notes, calculating quality scores, or enabling automation. |
| `asset-dir os status` | Read-only local Git portfolio scan with branch/worktree attention JSON and static HTML output. | You need to see dirty, conflicted, stale, unpushed, detached, or related work without changing source repositories. |
| `asset-dir os capture/capsule/feedback/bind/unbind/workstreams/refresh` | Event-sourced workstream kernel with explicit retry keys, human-approved dependency assertions, reversible bindings, resume capsules, conditional attention, and a refresh target that reports material Today changes. | You need to capture chat ideas, resume or close work, maintain the Scrum-style board, explain bottlenecks, or refresh attention without mutating Git. |
| `asset-dir os project/sovereignty` | Human-gated DAD child-project sovereignty plane from incubation through delivery, client sovereignty, maintenance, or detachment. | You need DAD to govern a child such as LawFirm OS before delivery while preserving the child's domain authority. |
| `assets/coding-harnesses/repo-enrollment-mail-governance-safety/` | Reusable harness and eval cases for enrollment/mail write boundaries, dirty-spool gates, source-outbox storms, Rust rollout snapshot churn, and public/private release safety. | You need to test or red-team DAD mail/enrollment behavior during concurrent repo mail, Rust rollout, or very dirty worktree states. |
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
| `processed/mail/` | Generated central mail inbox, outbox, archive, collection/delivery logs, release logs, and quarantine. | You need collected/routed candidate suggestions or audit proof for mailbox movement; never treat mail as source truth. |
| `processed/skills/` | Generated central skill-checkout ledger and future freshness reports. | You need candidate targets for skill update, retirement, replacement, or manual-review notices. |
| `processed/reports/mail_center.md` | Generated mail-center summary report. | You need mail counts and message-type distribution. |
| `processed/reports/exception_backfill_review_queue.md` | Generated source-review queue for historical path-signal exception backfill groups. | You need to review backfill candidates by source repo, classifier rule, status, hashes, release blockers, and classifier provenance before any learning promotion. |
| `processed/exceptions/review-queue/backfill_review_decisions.jsonl` | Append-only source/human/agent decision ledger for backfill review groups. | You need to know whether a path-signal group was confirmed, rejected, deferred, asked for a source packet, or blocked for classifier refresh; never treat this ledger as learning promotion by itself. |
| `processed/reports/exception_source_packet_opportunities.md` | Generated read-only opportunity report showing which backfill groups are eligible or blocked for source-packet decisions. | You need to decide which historical path-signal groups can safely request source-repo confirmation before appending a `needs_source_packet` decision. |
| `processed/reports/exception_source_packet_requests.md` | Generated report of DAD-authored central source-packet request mail. | You need to see which `needs_source_packet` decisions were compiled into central candidate mail before any source repo mailbox delivery. |
| `processed/mail/staged/source_packet_requests.jsonl` | Staged central candidate mail asking source repos to confirm, reject, or replace backfill path-signal evidence. | You need non-deliverable request records before any reviewed promotion to normal mail outbox; these do not mutate target repos or promote learning by themselves. |
| `processed/reports/exception_learning_queue.md` | Generated exception learning-readiness queue. | You need to prioritize exception clusters that need fix outcomes, fix validation, source review, or human lesson review. |
| `processed/reports/exception_learning_readiness_check.md` | Generated synthetic readiness-check report for the exception learning queue. | You need pass/fail evidence that the learning queue did not over-learn from weak or mixed evidence. |
| `processed/reports/exception_capture_emission_simulation.md` | Generated no-chat emission report from capture-suggest through temp-repo real packet writers and observed-check. | You need evidence that reviewed DAD capture patterns emit candidate JSONL with provenance without Lowell rescuing the issue from chat. |
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
- candidate DAD event/data pipeline design that can keep mailboxes as edge adapters while tracking repo responses and learning-loop outcomes;
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
| Design repo event flow | `event_pipeline` | roadmap evidence, event contract, response-state semantics, local-first/cloud-deferred boundaries, validation plan |
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
asset-dir agent preflight --repo <repo> --agent <agent-id> --task "<task>"
```

If `asset-dir` is not on `PATH`, first try the stable DAD user shim at
`$HOME/.dad/bin/asset-dir` or `$HOME\.dad\bin\asset-dir.ps1`. If the shim is
unavailable too, run the same command from a raw DAD source checkout as
`python -m digital_asset_directory.cli ...` with `PYTHONPATH=src` set first
(`$env:PYTHONPATH='src'` in PowerShell).

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
asset-dir agent postflight --session <id> --repo <repo> --summary "..." --test "..." --test-not-run "..."
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
python -m digital_asset_directory.cli roadmap check --no-update
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
- Asset memory: `.digital-asset/assets/index.jsonl`

Use these surfaces when work involves AI-assisted coding, repo governance,
lessons, reusable assets, templates, agent skills, or cross-repo suggestions.
DAD mail is candidate-only and local review controls adoption for `dad`.
Use `.digital-asset/assets/` for compact metadata-only asset cards. DAD's
address model uses 9 compact layers with layer 9 as learning/adaptation; put
long workflow details in workflow cards or source docs and reference them.
<!-- END DIGITAL_ASSET_DIRECTORY_ENROLLMENT -->
