# Reference Architecture Recognition V1

Evidence date: 2026-06-30

## Summary

Implemented a metadata-only reference architecture recognizer for the current
catalog.

Command:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend reference-architectures --limit 50 --component-limit 12
```

Generated outputs:

```text
processed/reports/reference_architectures.md
processed/reports/reference_architectures.json
processed/learning/reference_architecture_candidates.jsonl
processed/learning/scan_cycle_events.jsonl
```

Latest generated result:

- candidate count: 36;
- top score: 88.88;
- top candidate: `logos-governance-architecture governance control plane`;
- architecture type counts: 21 governance control planes, 8 evaluation/quality
  architectures, 5 schema-contract architectures, 1 learning-loop architecture,
  and 1 public-safe/private-source architecture.

## Methodology

The scan reads existing catalog metadata only by default:

- asset type;
- title;
- repo-relative path;
- tags;
- capabilities;
- needs;
- sensitivity;
- value score;
- configured repository-root metadata.

It intentionally does not read source file contents, recurse the filesystem,
call GitHub, call models, mutate source repositories, or promote candidates to
truth.

Full candidate-edge loading is skipped by default because the current catalog
contains hundreds of thousands of candidate edges. The CLI exposes
`--include-edges` for a later bounded composition pass when that cost is
explicitly justified.

## Score Formula

```text
reference_score = 100 * (
  0.22 * completeness
+ 0.20 * usefulness
+ 0.18 * reusability
+ 0.15 * composition
+ 0.15 * validation_readiness
+ 0.10 * novelty
) * (1 - 0.35 * risk)
```

Failed gates cap score at `25`.

The score is a review-order signal only. Current component evidence must be
reviewed before any future-upside or reuse claim.

## Red Team And Fixes

- Initial live run exposed a false-positive risk where repo names such as
  `logos-governance-architecture` leaked architecture/governance terms into
  every child file. The classifier now uses repo-relative paths.
- A second false-positive risk came from generic prose descriptions. V1 now
  avoids descriptions during role matching and uses path/title/type/tags/
  capabilities/needs instead.
- Loading all candidate edges caused the first live run to time out. The command
  now skips edges by default and records that skip in the scan-cycle event.
- Privacy-sensitive candidates fail `privacy_gate` and are capped at score `25`.

## Remaining Risks

- Metadata-only matching can still over-classify files whose names contain broad
  terms like `review`, `workflow`, or `template`.
- V1 can identify likely component roles but cannot prove real dataflow between
  components without a later human-approved content or edge-aware pass.
- Candidate architecture repetition across copied or variant repos still needs
  a later family-dedup pass before promotion or template extraction.
- The generated report is useful for review, not proof of canonical source
  architecture.

## Next Scan Cycle

Recommended next passes:

1. Human review the top architecture candidates.
2. Compare accepted candidates against `registry/template-registry.json` to find
   reusable templates or missing template dependencies.
3. Compare accepted candidates against workflow-part records for reusable
   subcomponents.
4. Request bounded content-read approval only for specific repo/path scopes where
   metadata cannot prove the component roles.

No roadmap phase is marked complete by this evidence.

## Validation

Commands run after implementation:

```powershell
python -m pytest
python -m ruff check src tests scripts noxfile.py
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli validate
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli roadmap check --no-update
```

Results:

- `python -m pytest`: 260 passed.
- `python -m ruff check src tests scripts noxfile.py`: all checks passed.
- `validate`: valid, 86 checked, 0 errors.
- `roadmap check --no-update`: exit 0; Phase 4 and Phase 5 remain
  `boundary_deferred`.
