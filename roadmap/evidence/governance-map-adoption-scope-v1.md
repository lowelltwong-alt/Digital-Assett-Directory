# Governance Map Adoption Scope V1

Status: implemented as generated candidate scope. No source repo adoption has
been approved or performed.

## Purpose

This evidence records the metadata-only planning layer for cross-repo governance
dependency-map adoption. The goal is to help future agents see which repo
families should be reviewed before anyone writes governance maps, child mirrors,
validators, tests, or PR disclosure requirements into source repositories.

## Implemented Surfaces

- Command:
  `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend governance-map-scope --limit 50`
- Module:
  `src/digital_asset_directory/governance_map_scope.py`
- Tests:
  `tests/test_governance_map_scope.py`
- Generated outputs:
  `processed/reports/governance_map_adoption_scope.md`
  `processed/reports/governance_map_adoption_scope.json`
  `processed/reports/governance_map_adoption_approval_prompt.md`
- Coverage-cycle integration:
  `recommend lesson-automation-coverage` now marks
  `governance_map_adoption` as `adoption_scope_ready` when the generated scope
  exists and no observed map or mirror already creates partial coverage.

## Live Scope Result

The live command was run local-only against the current catalog.

- Catalog assets considered: 95,902
- Candidate repos before limit: 35
- Reported repos: 35
- Candidate families: 6
- Noise/temp/worktree repos skipped: 108
- Status counts: 35 `missing_governance_dependency_surface`
- Source repos mutated: 0
- Hooks installed: 0
- Content files read: 0
- Filesystem recursions: 0
- GitHub calls: 0
- Model calls: 0

Families seen in the generated scope:

- `git-projects/00_lawfirm_os`
- `git-projects/02_other_git_projects`
- `git-projects/03_world_view`
- `git-projects/04_digital_assett_directory`
- `git-projects/90_ai_tooling_and_temp`
- `git-projects/lawfirm-skills-merge-workspace`

## Methodology

The command reads cataloged asset metadata and logical paths only. It groups
assets by cataloged repo, filters temp/worktree noise, detects governance-map
surfaces by path, and ranks candidates with:

```text
priority_score = 100 * (0.25*family_size_signal + 0.25*governance_gap + 0.20*downstream_likelihood + 0.15*ai_navigation_readiness + 0.10*validation_readiness + 0.05*configured_source_path)
```

This score is only review routing. It does not prove repo value, governance
authority, or adoption approval.

## Authority Boundary

Generated scope output is not a source-repo change request and not a governance
decision. A human must explicitly select a repo family and approve source-repo
edits before any map, mirror, validator, test, or PR template section is added.
DAD does not own the internal governance meaning of scanned repos.

## Red-Team And Premortem

- False positives: path-prefix family grouping can group repos that are adjacent
  on disk but not actually governed together.
- False negatives: metadata-only cataloging can miss existing maps if they were
  excluded or absent from the last scan.
- Authority risk: a child mirror can appear to override upstream governance if
  generated boilerplate is copied without adaptation.
- Process risk: adopting a map without a validator and test creates confidence
  without enforcement.
- Public-safety risk: future public DAD releases should keep this report as
  metadata-only and avoid importing private repo contents.

## Validation To Date

- `PYTHONPATH=src python -m pytest tests/test_governance_map_scope.py`:
  3 passed.
- `PYTHONPATH=src python -m pytest tests/test_governance_map_scope.py tests/test_lesson_automation_coverage.py tests/test_repo_learning_scope.py tests/test_ci_release_scope.py`:
  10 passed.
- `python -m pytest`: 231 passed.
- `python -m ruff check src tests scripts noxfile.py`: passed.
- `PYTHONPATH=src python -m digital_asset_directory.cli validate`: valid,
  84 checked, 0 errors.
- `PYTHONPATH=src python -m digital_asset_directory.cli roadmap check --no-update`:
  passed; phases 4 and 5 remain `boundary_deferred`.

## Next Human Gate

Select one repo family for actual governance-map adoption, or defer all source
repo writes. Recommended first review question: which repo is the upstream
governance authority, and which repos should carry child mirrors?
