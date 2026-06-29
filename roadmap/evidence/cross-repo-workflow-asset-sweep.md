# Cross-Repo Workflow Asset Sweep Evidence

Status: curated evidence for generated-candidate workflow patterns across local repos.

## Scope

- Source: current local Git Projects DAD catalog.
- GitHub scanning: disabled.
- Source mutation: none.
- Source repo contents: sampled read-only for active/canonical workflow docs and code surfaces.
- Generated outputs: under `processed/`, ignored by Git.

## Commands

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli recommend workflow-sweeps --source-id all --review-sample 150 --usefulness-per-sweep-limit 50 --usefulness-global-limit 200
python -m digital_asset_directory.cli recommend asset-families --source-id all --review-sample 150
python -m digital_asset_directory.cli recommend learning-loops --source-id all --review-sample 100
python -m digital_asset_directory.cli recommend semantic-evolution --source-id all --asset-type workflow --max-families 40 --review-sample 80 --max-read-bytes 500000
python -m digital_asset_directory.cli recommend archaeology --source-id all --include-worktrees --include-temp --max-repos 25 --max-commits 200 --review-sample 100
python -m digital_asset_directory.cli recommend root-cause-lessons --source-id all --include-worktrees --include-temp --review-sample 100
```

## Generated Counts

- Workflow sweep candidate matches: 1,271.
- Workflow usefulness candidates counted: 491.
- Asset-family candidate matches: 1,180 across 8 families.
- Logos-like assets in current catalog: 8,000.
- Learning-loop candidates: 22.
- Candidate learning-loop edges: 51.
- Semantic-evolution workflow candidates: 8.
- Worktree attempts: 378.
- Timeline events: 1,215.
- Change patterns: 300.
- Failure signals: 12,231.
- Root-cause lesson candidates that survived the strict context-bound filter: 1.

## Curated Pattern Decisions

The following generated-candidate patterns were recorded for future AI builders:

- source-faithful chunking gate system;
- reviewed gold and review packet system;
- exception-lake error-correction loop;
- AI work-cycle governance system;
- cross-repo authority and data-flow map;
- calibration and A/B gate system;
- security scanner and quarantine system.

These are candidate workflow assets. They should guide review and future recognition, not promote
source repo claims, generated outputs, runtime observations, or model scores to truth.

## Caveats

- Worktree and temp evidence is useful for archaeology but noisy; active/canonical files should be
  reviewed first.
- Some source folders contain private legal or person-related material. Track workflow patterns,
  not row-level examples.
- Patterns need human review before becoming deterministic preflight gates.
