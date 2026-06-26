# AI Table of Contents

## Front doors and authority

- `AI_FRONT_DOOR.md` - mission, ownership, routing, stop conditions
- `AGENTS.md` - standing agent contract
- `MACHINE_NAVIGATION_MANIFEST.json` - machine-readable entrypoint map
- `registry/source-of-truth.json` - repository precedence and layer definitions
- `registry/design-authority.json` - non-negotiable design rules
- `registry/identity-layer-registry.json` - Asset Identity And Similarity Ladder registry

## Architecture

- `docs/ARCHITECTURE.md`
- `docs/ASSET_IDENTITY_AND_SIMILARITY_LADDER.md`
- `docs/DATA_FLOW.md`
- `docs/KNOWLEDGE_GRAPH_MODEL.md`
- `docs/ASSET_VALUE_MODEL.md`
- `docs/ORPHAN_ACTIVATION_AND_SYNERGY_RADAR.md`
- `docs/LESSONS_AND_HANDOFF_LOOP.md`
- `docs/ASSET_USE_PAY_FORWARD_LOOP.md` - deterministic before/after use feedback workflow for all asset classes
- `docs/DETERMINISTIC_LEARNING_RULES.md` - reviewed learning rules surfaced in preflight and enforced by midflight acknowledgements
- `docs/LOAD_BEARING_DECISION_REVIEW.md` - high/medium/low risk gates for load-bearing software, repo, roadmap, schema, governance, scoring, and automation decisions
- `docs/SOFTWARE_REPO_CHECKLIST_TREE.md` - compositional checklist tree for software, repo, data normalization, governance, scoring, source-scan, review, and release work
- `docs/WORKFLOW_SWEEPS.md` - governance-first generated-candidate sweeps for discovering important workflow assets across repos
- `docs/PROFESSIONAL_RECRUITING_INTELLIGENCE_WORKFLOW.md` - reusable workflow asset for official-source professional identity, roster, enrichment, recruiting, acquisition, and group-liftout intelligence
- `docs/SEMANTIC_EVOLUTION_GRADING.md` - deterministic grading scale for real semantic evolution versus copy/fixture noise
- `docs/PUBLIC_ASSET_USE_FEEDBACK.md` - public PR path and untrusted-input rules for asset-use feedback
- `docs/LOGOS_REUSABLE_ASSET_FINDINGS.md` - reusable Logos-derived asset-family and learning-loop patterns
- `docs/CONTEXTUAL_LEARNING_AND_WORKTREE_ARCHAEOLOGY.md` - context-bound lessons from worktrees, temp repos, and history
- `docs/AI_GOVERNANCE.md`
- `docs/SECURITY_AND_PRIVACY.md`
- `docs/ORPHAN_RADAR_INTEGRATION.md`
- `docs/RESEARCH_BASIS.md`
- `docs/DUAL_PROPOSAL_ENGINE_RESEARCH_AND_BUILD_PLAN.md` - research-backed plan for bottom-up and top-down proposal engines

## Contracts

- `schemas/asset.schema.json`
- `schemas/asset-chunk.schema.json`
- `schemas/asset-identity-layer.schema.json`
- `schemas/asset-delta.schema.json`
- `schemas/semantic-evolution.schema.json`
- `schemas/duplicate-cluster.schema.json`
- `schemas/asset-pattern.schema.json`
- `schemas/edge.schema.json`
- `schemas/lesson.schema.json`
- `schemas/learning-rule.schema.json`
- `schemas/learning-loop.schema.json`
- `schemas/context-tag.schema.json`
- `schemas/worktree-attempt.schema.json`
- `schemas/repo-timeline-event.schema.json`
- `schemas/change-pattern.schema.json`
- `schemas/failure-signal.schema.json`
- `schemas/root-cause-hypothesis.schema.json`
- `schemas/counterfactual-lesson.schema.json`
- `schemas/repo-learning-event.schema.json`
- `schemas/handoff.schema.json`
- `schemas/alert.schema.json`
- `schemas/source.schema.json`
- `schemas/synergy.schema.json`
- `schemas/activation-trigger.schema.json`
- `schemas/capability-recommendation.schema.json`
- `schemas/proposal.schema.json`
- `schemas/proposal-review.schema.json`
- `schemas/asset-calibration-review.schema.json`
- `examples/proposals/bottom-up-proposal.example.json`
- `examples/proposals/top-down-proposal.example.json`

## Controlled vocabularies

- `registry/asset-type-registry.json`
- `registry/asset-pattern-registry.json`
- `registry/context-tag-registry.json`
- `registry/learning-rule-registry.json`
- `registry/semantic-evolution-grade-registry.json`
- `registry/identity-layer-registry.json`
- `registry/edge-type-registry.json`
- `registry/lifecycle-registry.json`
- `config/taxonomy.yaml`
- `ontology/digital-asset-ontology.ttl`
- `ontology/taxonomy.skos.ttl`

## Operations

- `config/sources.example.yaml`
- `docs/OPERATIONS.md`
- `docs/PROPOSAL_ENGINE_CALIBRATION_WORKFLOW.md` - operational workflow for reviewing bottom-up and top-down proposal engines
- `asset-dir recommend workflow-sweeps` - generated governance-first workflow-family sweep reports under `processed/reports/workflow_sweeps/`
- `docs/DOWNSTREAM_REPO_GOVERNANCE.md`
- `docs/TESTING_AND_ORCHESTRATION.md` - marker taxonomy, change-driven test selection, and nox tasks
- `docs/ALGORITHM_CALIBRATION_AND_FIXES_HANDOFF.md` - implemented algorithm fixes, remaining work, and how to calibrate thresholds/weights/confidence
- `scripts/bootstrap.ps1`
- `scripts/install_to_target.ps1`
- `scripts/new_repo.ps1` - scaffold a new repository pre-wired to this hub
- `scripts/claude_hook.py`
- `scripts/register_scheduled_scan.ps1`
- `scripts/unregister_scheduled_scan.ps1`
- `templates/asset-use-feedback.template.md` - copyable public feedback template
- `templates/load-bearing-decision-review.template.md` - fresh-eyes red-team/premortem template for high-risk load-bearing decisions
- `templates/software-repo-checklist-tree.template.md` - reusable checklist-tree record for non-trivial software, repo, data, workflow, scoring, governance, source-scan, and release work

## Roadmap

- `roadmap/roadmap.yaml`
- `roadmap/gate-evidence.json` - tracked human-gate and validation-command evidence
- `roadmap/state.json`
- `docs/ROADMAP_EXECUTION.md`
- `roadmap/evidence/contextual-learning-archaeology.md` - generated-candidate archaeology counts, caveats, and review needs
- `roadmap/evidence/deterministic-learning-rules.md` - reviewed learning-rule seed evidence and midflight acknowledgement trace
- `roadmap/evidence/load-bearing-decision-review-asset.md` - curated evidence that the load-bearing decision review workflow is a reusable composite digital asset
- `roadmap/evidence/software-repo-checklist-tree.md` - curated evidence for the software and repo checklist tree workflow asset
- `roadmap/evidence/semantic-evolution-grading.md` - candidate evidence for separating real semantic evolution from copy/fixture noise
- `roadmap/evidence/phase-1.5-scoring-discipline.md` - implemented scoring discipline and clean-sampling checkpoint evidence
- `roadmap/evidence/phase-1.5-human-review.md` - human review research and gate decisions for Phase 1.5
- `roadmap/evidence/phase-2-temp-fixture-calibration-research.md` - first-batch Phase 2 temp fixture scoring research and recommendations
- `roadmap/evidence/phase-2-claude-second-opinion.md` - intake file for Claude's independent Phase 2 calibration findings
- `roadmap/evidence/phase-2-claude-red-team-premortem.md` - Claude red-team premortem warning against calibrating on stale noisy samples
- `roadmap/evidence/phase-2-asset-calibration.md` - generated tracked Phase 2 calibration gate evidence after 100 reviewed labels
- `roadmap/evidence/phase-2-calibration-human-review-research.md` - human review rationale, label policy, and score-change recommendations for Phase 2
- `roadmap/evidence/phase-2-calibration-label-table.csv` - compact tracked table of all 100 Phase 2 asset-rating labels
- `roadmap/evidence/phase-2.5-content-aware-scoring.md` - content-aware scoring recommendation, implementation notes, and red-team before downstream use
- `roadmap/evidence/nevada-bar-professional-intelligence-workflow.md` - curated evidence for the Nevada Bar Results professional recruiting intelligence workflow asset family

## Reference

- `docs/DATA_DICTIONARY.md` - field meanings and authority posture.
- `registry/capability-registry.json` - controlled capability IDs.
- `registry/need-registry.json` - controlled missing-part IDs.
- `VERIFICATION_REPORT.md` - verified checks, scope, and environment-dependent gaps
