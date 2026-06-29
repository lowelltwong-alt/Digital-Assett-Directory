# WorkflowPartRecord Phase A Evidence

Date: 2026-06-29

Status: implemented as a generated-candidate recognition layer.

## Scope

WorkflowPartRecord Phase A adds a deterministic way to recognize reusable workflow sub-parts beneath existing asset-family patterns. The implementation is local-only and candidate-only. It reads the existing catalog and graph outputs, does not rescan, does not call GitHub, does not call models, and does not mutate scanned source repositories.

Phase A is accepted only as a review surface. It is not accepted as source authority, automatic preflight guidance, workflow assembly, current-score input, or proof that a part is valuable.

## Added Contracts And Registries

- Added `WorkflowPartRecord` to the Pydantic models.
- Added `schemas/workflow-part.schema.json`.
- Registered the schema in `registry/schema-registry.json`.
- Added `registry/workflow-part-type-registry.json`.
- Added `workflow_part_types` to `MACHINE_NAVIGATION_MANIFEST.json`.
- Added five narrow edge types to `registry/edge-type-registry.json` and the ontology:
  - `produces_input_for`
  - `substitutes_for`
  - `specializes`
  - `generalizes`
  - `quarantines`

The optional `incompatible_with` edge was intentionally deferred because existing `unsafe_composition_with` already covers unsafe composition review.

## Generated Outputs

The CLI command is:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend workflow-parts --source-id all --review-sample 50
```

It writes generated candidate outputs only:

- `processed/learning/workflow_parts.jsonl`
- `processed/learning/workflow_part_candidate_edges.jsonl`
- `processed/reports/workflow_part_recognition.md`
- `processed/reports/workflow_part_review_sample.md`

These files remain generated outputs under `processed/` and are not promoted to tracked truth.

## Real-Catalog Smoke Result

The local smoke run completed successfully with:

- candidate workflow parts: 8177
- candidate workflow-part edges: 8820
- review sample size: 50

Top part-type counts from the smoke run:

- `contract`: 1901
- `eval_gold`: 1321
- `validator`: 1087
- `orchestrator`: 796
- `capability_provider`: 675
- `runner`: 544
- `human_gate`: 425

Top asset-pattern counts from the smoke run:

- `evaluation_contract_system`: 2807
- `gold_review_packet_system`: 1365
- `ai_work_cycle_governance_system`: 1360
- `agent_skill_graph_system`: 949
- `proposal_promotion_workflow`: 486
- `governed_learning_loop_system`: 348

## Safety Design

- Records default to `review_status="generated_candidate"`.
- Records include context-bound safety fields: `applies_when`, `does_not_apply_when`, and `danger_if_misapplied`.
- Public-safe recognition excludes likely raw data/output lanes, temporary fixtures, cache paths, secrets, private keys, and restricted/confidential sensitivity classes.
- V1 does not infer true dataflow. Inputs, outputs, preconditions, postconditions, side effects, and failure modes remain empty unless declared or reviewed.
- Duplicate and variant families are deduped before candidate emission so repeated copies do not multiply review burden.
- Evidence is metadata-only and bounded. Raw source content is not embedded in generated packets.

## Red-Team And Premortem

Risk: edge and ontology sprawl.
Mitigation: reuse existing edge vocabulary and add only five confirmed missing relationship types.

Risk: false positives from broad lexical cues.
Mitigation: keep all records candidate-only, require human review, and do not surface records as mandatory preflight guidance in Phase A.

Risk: private or sensitive source leakage.
Mitigation: filter temp, raw, data, output, state, cache, secret, and restricted paths before candidate generation.

Risk: hallucinated workflow dataflow.
Mitigation: leave dataflow fields empty in deterministic v1 unless evidence explicitly declares them.

Risk: duplicate/temp inflation.
Mitigation: family-level deduplication using duplicate and variant graph evidence, plus path exclusions for known temp lanes.

Risk: over-trusting generated candidates.
Mitigation: no current-score changes, no roadmap completion claim, no source-authority claim, and no automated promotion path.

## Validation Evidence

Focused validation completed before this evidence file:

```powershell
python -m pytest tests\test_workflow_parts.py tests\test_schema_conformance.py -q
# 16 passed

python -m ruff check src\digital_asset_directory\workflow_parts.py src\digital_asset_directory\models.py src\digital_asset_directory\cli.py tests\test_workflow_parts.py tests\test_schema_conformance.py
# All checks passed
```

Full validation completed before this evidence file:

```powershell
python -m pytest
# 175 passed

python -m ruff check src tests scripts noxfile.py
# All checks passed

$env:PYTHONPATH='src'; python -m digital_asset_directory.cli validate
# valid=true, checked_count=67, errors=[]

$env:PYTHONPATH='src'; python -m digital_asset_directory.cli roadmap check --no-update
# exited 0
```

Final validation should be rerun after this file is added.

## Reusable Lesson

When a workflow-recognition layer is added to DAD, the safest first implementation should recognize recombinable parts as candidate records, not as source truth. The contract must include context-bound applicability, non-applicability, and danger-if-misapplied fields before the records are allowed into reports. Any calculated or detected relationship should declare its methodology version and remain reviewable, reproducible, and reversible.

## Acceptance

Accepted in Phase A:

- Candidate WorkflowPartRecord contract.
- Candidate recognizer over the current catalog and graph outputs.
- Generated review reports.
- Schema/model/registry/ontology/docs/tests.

Deferred:

- Preflight or midflight surfacing.
- Workflow assembly packs.
- Model-assisted enrichment.
- Current value-score influence.
- Source-repo mutation or governance installation.
- Optional `incompatible_with` edge.

Next recommended step: review the generated workflow-part sample for false positives, missing part families, and public-safety issues before using workflow parts in background connection radar or future workflow assembly.
