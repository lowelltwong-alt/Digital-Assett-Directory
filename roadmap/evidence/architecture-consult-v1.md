# Architecture Consult V1

Date: 2026-06-30
Status: implemented as generated-candidate advisor

## Purpose

Architecture Consult V1 lets a new repo-seeding chat or coding agent ask DAD
for seed architecture advice before implementation begins.

The input is an intent file describing:

- what the new repo is for;
- domain;
- risk level;
- expected users or agents;
- data sensitivity;
- workflows needed;
- validation needs.

The output is a generated candidate architecture pack with reference
architectures, reusable parts, templates, dependency notes, human gates, starter
structure, validation checklist, and a bounded seed prompt.

## Authority Boundary

DAD advises the seed architecture. The new repository retains its own canon,
source-of-truth, and design authority.

The command does not:

- rescan;
- read source repo contents;
- call GitHub;
- call models;
- mutate target or source repos;
- install hooks or templates;
- copy source-owned facts;
- promote candidates to truth;
- mark roadmap phases complete.

## Command

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli recommend architecture-consult --intent-file "<new-repo-intent.md>" --limit 10
```

Generated outputs:

```text
processed/reports/architecture_consults/<slug>.md
processed/reports/architecture_consults/<slug>.json
processed/reports/architecture_consults/<slug>_seed_prompt.md
```

## Inputs

The command reads local DAD artifacts only:

- `processed/learning/reference_architecture_candidates.jsonl`;
- `processed/reports/reference_architectures.json`;
- `registry/template-registry.json`;
- `processed/workflow_parts/workflow_part_usage_guidance.json`;
- `processed/learning/background_connection_candidates.jsonl`;
- `processed/reports/governance_map_adoption_scope.json`;
- `registry/learning-rule-registry.json`;
- `docs/SOFTWARE_REPO_CHECKLIST_TREE.md`.

Missing optional generated inputs become warnings, not permission to rescan.

## Formula

```text
match_score =
  100 * (
    0.45 * source_strength
  + 0.35 * intent_overlap
  + 0.20 * context_boost
  )
```

`source_strength` is the existing reference-architecture score divided by 100.
`intent_overlap` is deterministic token overlap between the redacted intent and
candidate metadata. `context_boost` rewards risk/sensitivity/workflow matches
such as high-risk governance, non-public data boundaries, schema/test
validation, AI navigation, and learning-loop needs.

The score is a review ordering signal only.

## Red Team And Premortem

- A generated consult can overfit to file names or stale candidate metadata.
- Missing upstream reports can hide useful architectures.
- Cross-repo inspiration can accidentally imply authority transfer.
- Templates can be copied without their dependencies, validation, or human
  gates.
- A seed prompt can be mistaken for a complete implementation plan.
- Secret-like intent text can leak if not redacted.

Controls added:

- intent parsing uses redaction before output;
- redaction failure creates a privacy gate failure;
- outputs carry `review_status="generated_candidate"`;
- consult IDs include the source scan watermark;
- no command refreshes upstream scans or reports;
- seed prompt says to reuse architecture shape, not source-owned facts;
- required human gates are explicit in the report.

## Live Command Check

Ran against a temporary intent file:

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli recommend architecture-consult --intent-file $env:TEMP\dad-architecture-consult-intent.md --limit 10
```

Result:

- matched reference architectures: `10`;
- recommended templates: `9`;
- warnings: none;
- generated files under `processed/reports/architecture_consults/`;
- candidate-only output: true.

## Validation

Passed in this implementation turn:

- `python -m pytest tests/test_architecture_consult.py tests/test_schema_conformance.py -q` - 23 passed.
- `python -m ruff check src/digital_asset_directory/architecture_consult.py tests/test_architecture_consult.py src/digital_asset_directory/cli.py tests/test_schema_conformance.py` - passed.
- `python -m pytest` - 265 passed.
- `python -m ruff check src tests scripts noxfile.py` - passed.
- `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli validate` - valid, 87 checked, 0 errors.
- `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli roadmap check --no-update` - passed; roadmap statuses unchanged by this feature.

## Remaining Risks

- Architecture matching still depends on the quality and freshness of prior
  generated reference-architecture and workflow-part surfaces.
- The first version does not infer full dataflow, side effects, or preconditions
  unless upstream artifacts already declare them.
- Human review remains required before a new repo treats a consult as local
  architecture canon.
