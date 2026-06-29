# Workflow Part Calibration Evidence

Evidence date: 2026-06-29T16:45:12.918701+00:00

## Source Review File

- Review file: `processed/workflow_parts/workflow_part_review_template.jsonl`
- Source review records are human labels over generated workflow-part candidates.
- This evidence does not promote workflow parts to source truth, current scoring, or mandatory preflight guidance.

## Gate Coverage

- Reviewed records: **50**
- Required reviewed records: **50**
- Calibration gate complete: **True**

## Review Outcomes

- Usefulness: `{'not_useful': 14, 'useful': 35, 'unsure': 1}`
- Safety: `{'needs_more_review': 14, 'safe': 36}`
- Specificity: `{'too_broad': 14, 'right_level': 35, 'too_narrow': 1}`
- Dataflow completeness: `{'not_applicable': 14, 'missing_inputs': 10, 'adequate_for_now': 20, 'missing_side_effects': 4, 'missing_outputs': 2}`
- Decisions: `{'reject_candidate': 14, 'accept_for_review_use': 28, 'needs_human_gate': 7, 'defer': 1}`

## Decision Samples

### Accepted For Review Use

- `workflow-part-review-002` `calibration_gate` `calibration_ab_gate_system` - Accepted for review-use only; no score or threshold authority transferred. Path: `git-projects/02_Other_Git_Projects/fmg-fractal-capability-ontology/governance/ALIGNMENT_SCOREBOARD.md`
- `workflow-part-review-003` `capability_provider` `agent_skill_graph_system` - Real reusable capability provider candidate. Path: `git-projects/lawfirm-skills-merge-workspace/LawFirm-os-skills-registry/skills/approved/elegant-design-review/SKILL.md`
- `workflow-part-review-004` `contract` `evaluation_contract_system` - Enum schemas are valid workflow contracts. Path: `git-projects/00_LawFirm_OS/LawFirm-os-semantic-substrate/schema/enums/projection_status.yaml`
- `workflow-part-review-005` `decision_record` `proposal_promotion_workflow` - Promotion-decision schema is useful as decision-record structure. Path: `git-projects/02_Other_Git_Projects/fmg-fractal-capability-ontology/schemas/promotion-decision.schema.json`
- `workflow-part-review-007` `gate` `ai_work_cycle_governance_system` - Real gate candidate, review-use only. Path: `git-projects/02_Other_Git_Projects/fmg-fractal-capability-ontology/.github/workflows/validate-governed-learning.yml`
- `workflow-part-review-009` `learning_signal` `governed_learning_loop_system` - Exception/retrieval workflow docs are useful learning-signal candidates. Path: `git-projects/02_Other_Git_Projects/fmg-fractal-capability-ontology/governance/EXCEPTIONS_RETRIEVAL_WORKFLOW_SYNERGY.md`
- `workflow-part-review-012` `prompt_part` `ai_agent_workflow_system` - Useful prompt surface for AI navigation review. Path: `git-projects/00_LawFirm_OS/LawFirm-os-semantic-substrate/docs/AI_FRONT_DOOR_QUESTIONS.md`
- `workflow-part-review-014` `runner` `ai_work_cycle_governance_system` - Real runner candidate. Path: `git-projects/00_LawFirm_OS/LawFirm-os-semantic-substrate/scripts/phase3/build_graph_manifests.py`
- `workflow-part-review-015` `validator` `evaluation_contract_system` - Real validator candidate. Path: `git-projects/00_LawFirm_OS/LawFirm-os-semantic-substrate/scripts/validation/tests/test_validate_canonical_grounding_chain.py`
- `workflow-part-review-017` `calibration_gate` `agent_skill_graph_system` - Useful review cadence calibration part. Path: `git-projects/00_LawFirm_OS/LawFirm-os-semantic-substrate/docs/governance/agent-skills/ownership-and-review-cadence-policy.md`
- `workflow-part-review-019` `contract` `proposal_promotion_workflow` - Promotion-decision schema is a real contract candidate. Path: `git-projects/02_Other_Git_Projects/fmg-fractal-capability-ontology/schemas/promotion-decision.schema.json`
- `workflow-part-review-020` `decision_record` `load_bearing_decision_review_system` - Allocation decision type is a useful decision-record contract. Path: `git-projects/02_Other_Git_Projects/fmg-fractal-capability-ontology/schema/types/allocation_decision.yaml`
- `workflow-part-review-022` `gate` `route_isolated_evaluation_harness` - Useful route-isolated gate candidate. Path: `git-projects/03_World_View/logos-scripture-graph-repo/tests/test_chunking_agent_preflight.py`
- `workflow-part-review-024` `learning_signal` `agent_skill_graph_system` - Real learning-signal candidate. Path: `git-projects/02_Other_Git_Projects/fmg-fractal-capability-ontology/docs/governance/agent-skills/audit-and-governed-learning-boundary.md`
- `workflow-part-review-025` `lesson_part` `agent_skill_graph_system` - Real lesson-part candidate. Path: `git-projects/00_LawFirm_OS/LawFirm-os-legal-knowledge-runtime/docs/RESEARCH_DELTA_2026_AGENT_HARNESS_LESSONS.md`
- `workflow-part-review-026` `orchestrator` `governed_learning_loop_system` - Useful orchestrator candidate. Path: `git-projects/02_Other_Git_Projects/fmg-fractal-capability-ontology/docs/governance/ai-workflow/templates/chat-handoff-template.md`
- `workflow-part-review-029` `runner` `duplicate_variant_preservation_system` - Real runner candidate. Path: `git-projects/00_LawFirm_OS/LawFirm-os-semantic-substrate/scripts/validation/validate_dna_invariants.py`
- `workflow-part-review-030` `validator` `duplicate_variant_preservation_system` - Real validator candidate with composite-role lesson. Path: `git-projects/00_LawFirm_OS/LawFirm-os-semantic-substrate/scripts/validation/validate_dna_invariants.py`
- `workflow-part-review-031` `boundary_map` `frontier_signal_intake_loop` - Real boundary-map candidate. Path: `git-projects/03_World_View/logos-boundary-literature/governance/CANON_AND_AUTHORITY_POLICY.md`
- `workflow-part-review-037` `gate` `proposal_promotion_workflow` - Accept for review-use only, not source authority. Path: `git-projects/02_Other_Git_Projects/airca-fractal-decision-architecture/papers/generated/architecture-approval-example.md`

### Human-Gated

- `workflow-part-review-008` `human_gate` `proposal_promotion_workflow` - Phase dependency maps are useful human-gate surfaces, but need human review before reuse. Path: `git-projects/02_Other_Git_Projects/fmg-fractal-capability-ontology/docs/roadmap/PHASE_DEPENDENCY_MAP.md`
- `workflow-part-review-010` `lesson_part` `governed_learning_loop_system` - Useful but private-path and context-sensitive; route through human gate. Path: `git-projects/00_LawFirm_OS/LawFirm-os-talent-intelligence-private/.ai/workflows/state-buildout-lessons.md`
- `workflow-part-review-016` `boundary_map` `agent_skill_graph_system` - Authority-sensitive security packet; keep behind human gate. Path: `git-projects/lawfirm-skills-merge-workspace/zip-extract/LawFirm-os-skills-registry/codex-task-packets/PR0_SECURITY_HARDENING.md`
- `workflow-part-review-023` `human_gate` `agent_skill_graph_system` - Roadmap governance document is useful but should remain human-gated. Path: `git-projects/02_Other_Git_Projects/fmg-fractal-capability-ontology/docs/governance/agent-skills/generated-index-and-graphrag-roadmap.md`
- `workflow-part-review-027` `prompt_part` `agent_skill_graph_system` - Useful prompt part but external-scout enabling must stay human-gated. Path: `git-projects/lawfirm-skills-merge-workspace/zip-extract/LawFirm-os-skills-registry/codex-task-packets/PR5_ENABLE_GITHUB_SCOUT.md`
- `workflow-part-review-038` `human_gate` `route_isolated_evaluation_harness` - Roadmap gate candidate is useful but human-gated. Path: `git-projects/03_World_View/logos-scripture-graph-repo/docs/roadmap/T336_OPTIMIZED_WHOLE_BIBLE_CHUNKING_ROADMAP.md`
- `workflow-part-review-046` `boundary_map` `boundary_contamination_firewall` - Privacy boundary material should stay human-gated before reuse. Path: `git-projects/00_LawFirm_OS/LawFirm-os-semantic-substrate/docs/governance/ai-workflow/ai-audit-retention-and-privacy.md`

### Rejected

- `workflow-part-review-001` `boundary_map` `boundary_contamination_firewall` - Reject current candidate; preserve as lineage/noise signal only. Path: `git-projects/00_LawFirm_OS/LawFirm-os-skills-registry/security/rulepacks/active/.gitkeep`
- `workflow-part-review-006` `eval_gold` `gold_review_packet_system` - Reject as current eval_gold candidate; may remain directory lineage evidence. Path: `git-projects/03_World_View/logos-boundary-literature/eval/.gitkeep`
- `workflow-part-review-011` `orchestrator` `agent_skill_graph_system` - Reject as orchestrator; may be package lineage only. Path: `git-projects/lawfirm-skills-merge-workspace/LawFirm-os-skills-registry/src/lawfirm_os_skills_registry/governance/__init__.py`
- `workflow-part-review-013` `quarantine_gate` `boundary_contamination_firewall` - Reject current quarantine candidate; preserve as lineage/noise signal. Path: `git-projects/00_LawFirm_OS/LawFirm-os-skills-registry/security/rulepacks/active/.gitkeep`
- `workflow-part-review-018` `capability_provider` `boundary_contamination_firewall` - Reject as capability provider; marker files are not capability assets. Path: `git-projects/00_LawFirm_OS/LawFirm-os-skills-registry/security/rulepacks/active/.gitkeep`
- `workflow-part-review-021` `eval_gold` `governed_learning_loop_system` - Reject eval_gold role; may be learning/gate material instead. Path: `git-projects/00_LawFirm_OS/LawFirm-os-semantic-substrate/docs/governance/retrieval-feedback-and-promotion-policy.md`
- `workflow-part-review-028` `quarantine_gate` `security_scanner_quarantine_system` - Reject weak marker-file candidate. Path: `git-projects/00_LawFirm_OS/LawFirm-os-skills-registry/quarantine/.gitkeep`
- `workflow-part-review-032` `calibration_gate` `proposal_promotion_workflow` - Reject due temp-fixture path; preserve semantic-evolution/copy evidence only. Path: `git-projects/90_AI_Tooling_And_Temp/.pytest-tmp-lawfirm-os-orchestrator/basetemp/test_upgrade_proposal_packet_w0/packets/upgrade_proposal_validator_threshold_example/risk_review.md`
- `workflow-part-review-033` `capability_provider` `gold_review_packet_system` - Reject as capability provider. Path: `git-projects/lawfirm-skills-merge-workspace/LawFirm-os-skills-registry/src/lawfirm_os_skills_registry/evaluation/__init__.py`
- `workflow-part-review-034` `contract` `route_isolated_evaluation_harness` - Reject current contract candidate; route to temp/variant review if needed. Path: `git-projects/90_AI_Tooling_And_Temp/patch_bundles/lawfirm_os_orchestrator_agent_hostile_mvp_seed_bundle/agent_hostile_patch_repo/src/lawfirm_os_orchestrator/model_router/schema_factory.py`
- `workflow-part-review-035` `decision_record` `route_isolated_evaluation_harness` - Reject decision_record role; could be validator in another sample. Path: `git-projects/03_World_View/logos-scripture-graph-repo/tests/test_chunking_theological_decision_register.py`
- `workflow-part-review-042` `prompt_part` `proposal_promotion_workflow` - Reject due temp-fixture path. Path: `git-projects/90_AI_Tooling_And_Temp/.pytest-tmp-lawfirm-os-orchestrator/basetemp/test_upgrade_proposal_packet_w0/packets/upgrade_proposal_validator_threshold_example/codex_task_draft.md`
- `workflow-part-review-043` `quarantine_gate` `agent_skill_graph_system` - Reject weak package-marker candidate. Path: `git-projects/lawfirm-skills-merge-workspace/LawFirm-os-skills-registry/src/lawfirm_os_skills_registry/governance/__init__.py`
- `workflow-part-review-048` `capability_provider` `duplicate_variant_preservation_system` - Reject capability-provider role. Path: `git-projects/lawfirm-skills-merge-workspace/zip-extract/LawFirm-os-skills-registry/examples/exception_clusters.jsonl`

### Deferred

- `workflow-part-review-036` `eval_gold` `route_isolated_evaluation_harness` - Defer; may be eval output rather than gold set. Path: `git-projects/03_World_View/logos-scripture-graph-repo/eval/chunking_runs/claude-opus-4.8__pass2__D_claude_pass2_post_t327__20260608T215149Z.json`

## Calibration Notes

- False positive notes: **14**
- False negative notes: **1**
- Useful example notes: **25**
- Missing dataflow notes: **16**

### False Positive Notes

- `workflow-part-review-001` `boundary_map` `boundary_contamination_firewall`: Empty marker/security rulepack paths do not prove a boundary map; likely path-cue false positive.
- `workflow-part-review-006` `eval_gold` `gold_review_packet_system`: Eval .gitkeep/__init__ evidence is too weak to identify a gold or review set.
- `workflow-part-review-011` `orchestrator` `agent_skill_graph_system`: __init__.py governance package marker is too weak to prove an orchestrator workflow part.
- `workflow-part-review-013` `quarantine_gate` `boundary_contamination_firewall`: Security rulepack .gitkeep paths are too weak to identify a quarantine gate.
- `workflow-part-review-018` `capability_provider` `boundary_contamination_firewall`: Security rulepack .gitkeep paths do not prove a capability provider.
- `workflow-part-review-021` `eval_gold` `governed_learning_loop_system`: Retrieval feedback policy is useful governance material but not itself an eval gold set.
- `workflow-part-review-028` `quarantine_gate` `security_scanner_quarantine_system`: Quarantine .gitkeep marker does not prove a reusable quarantine gate.
- `workflow-part-review-032` `calibration_gate` `proposal_promotion_workflow`: Pytest temp risk-review packet is lineage evidence, not an independent calibration gate.
- `workflow-part-review-033` `capability_provider` `gold_review_packet_system`: Evaluation __init__.py package marker is too weak to prove a capability provider.
- `workflow-part-review-034` `contract` `route_isolated_evaluation_harness`: Temp patch-bundle schema_factory.py should not be treated as a stable contract candidate.
- `workflow-part-review-035` `decision_record` `route_isolated_evaluation_harness`: A test for a decision register is validator evidence, not the decision record itself.
- `workflow-part-review-042` `prompt_part` `proposal_promotion_workflow`: Pytest temp codex task draft is not a stable prompt-part candidate.
- `workflow-part-review-043` `quarantine_gate` `agent_skill_graph_system`: Governance __init__.py marker is too weak to prove a quarantine gate.
- `workflow-part-review-048` `capability_provider` `duplicate_variant_preservation_system`: Exception cluster JSONL is data/evidence, not a capability provider by itself.

### False Negative Notes

- `workflow-part-review-030` `validator` `duplicate_variant_preservation_system`: The same validation script is both runner and validator; future recognizers should surface composite roles rather than force one role per review item.

### Useful Examples

- `workflow-part-review-002` `calibration_gate` `calibration_ab_gate_system`: Alignment scoreboards are useful calibration-gate examples for score/review workflows.
- `workflow-part-review-003` `capability_provider` `agent_skill_graph_system`: Skill files are useful capability-provider workflow parts.
- `workflow-part-review-007` `gate` `ai_work_cycle_governance_system`: CI validation workflow is a useful governance gate example.
- `workflow-part-review-012` `prompt_part` `ai_agent_workflow_system`: AI front-door question docs are useful prompt-part candidates.
- `workflow-part-review-014` `runner` `ai_work_cycle_governance_system`: Build graph manifest script is a reusable runner candidate.
- `workflow-part-review-015` `validator` `evaluation_contract_system`: Canonical grounding-chain test is a useful validator example.
- `workflow-part-review-016` `boundary_map` `agent_skill_graph_system`: Security hardening task packet can be useful as a boundary-map review example.
- `workflow-part-review-017` `calibration_gate` `agent_skill_graph_system`: Ownership and review cadence policies are useful calibration-gate surfaces.
- `workflow-part-review-022` `gate` `route_isolated_evaluation_harness`: Chunking agent preflight test is a useful gate example.
- `workflow-part-review-024` `learning_signal` `agent_skill_graph_system`: Governed-learning boundary docs are useful learning-signal candidates.
- `workflow-part-review-025` `lesson_part` `agent_skill_graph_system`: Research delta lesson docs are useful lesson-part examples.
- `workflow-part-review-026` `orchestrator` `governed_learning_loop_system`: Chat handoff template is a useful orchestration part.
- `workflow-part-review-029` `runner` `duplicate_variant_preservation_system`: DNA invariant validation script is a useful runner candidate.
- `workflow-part-review-030` `validator` `duplicate_variant_preservation_system`: DNA invariant validation script is also a useful validator candidate.
- `workflow-part-review-031` `boundary_map` `frontier_signal_intake_loop`: Canon and authority policy is a strong boundary-map example.

### Missing Dataflow Notes

- `workflow-part-review-002` `calibration_gate` `calibration_ab_gate_system`: Needs declared score inputs, thresholds, and reviewer boundary before assembly.
- `workflow-part-review-003` `capability_provider` `agent_skill_graph_system`: Needs declared inputs/dependencies before composition.
- `workflow-part-review-007` `gate` `ai_work_cycle_governance_system`: Needs side-effect and trigger declarations before reuse in another repo.
- `workflow-part-review-010` `lesson_part` `governed_learning_loop_system`: Private LawFirm lesson needs applicability and authority inputs before reuse.
- `workflow-part-review-014` `runner` `ai_work_cycle_governance_system`: Needs declared inputs and output artifacts before reuse.
- `workflow-part-review-015` `validator` `evaluation_contract_system`: Needs declared fixture and expected-output inputs before assembly.
- `workflow-part-review-022` `gate` `route_isolated_evaluation_harness`: Needs side-effect and stop-condition declaration before reuse.
- `workflow-part-review-026` `orchestrator` `governed_learning_loop_system`: Needs declared handoff outputs and acceptance criteria before assembly.
- `workflow-part-review-027` `prompt_part` `agent_skill_graph_system`: GitHub scout prompt needs explicit network/external-call side-effect boundaries.
- `workflow-part-review-029` `runner` `duplicate_variant_preservation_system`: Needs input config and expected outputs declared before reuse.
- `workflow-part-review-030` `validator` `duplicate_variant_preservation_system`: Needs fixture/input contract before assembly.
- `workflow-part-review-036` `eval_gold` `route_isolated_evaluation_harness`: Generated chunking run needs clear gold/review status before it can be eval_gold.
- `workflow-part-review-041` `orchestrator` `ai_work_cycle_governance_system`: Needs side-effect and trigger details before reuse.
- `workflow-part-review-044` `runner` `route_isolated_evaluation_harness`: Needs route input and command-output contract before assembly.
- `workflow-part-review-045` `validator` `route_isolated_evaluation_harness`: Needs fixture/input contract before assembly.

## Remaining Risks

- Labels calibrate review usefulness only; they do not authorize source-repo mutation.
- Preflight surfacing, workflow assembly, and score influence remain separate gates.
