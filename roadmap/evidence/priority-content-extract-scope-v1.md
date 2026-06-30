# Priority Content Extract Scope V1

## Summary

Implemented a metadata-only approval scope for the first unscanned signal family
in the scan-cycle log: priority content extracts.

The command lists candidate paths for a future bounded content pass, but reads no
source file contents.

## Command

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-scope --limit 120 --per-repo-limit 8
```

Generated outputs:

- `processed/reports/priority_content_extract_scope.md`
- `processed/reports/priority_content_extract_scope.json`
- `processed/reports/priority_content_extract_approval_prompt.md`

## Live Scope Result

- Catalog assets considered: 95,902
- Repos with candidates before global limit: 30
- Repos reported: 15
- Candidate files listed: 120
- Total candidate files before global limit: 231
- Content files read: 0
- Source repos mutated: 0
- Noise repo groups skipped: 113

Reported category counts:

- `ai_navigation`: 90
- `schemas_contracts`: 27
- `validators_tests`: 3

## Risk Tier

Medium.

Reason: this affects which downstream content might be read in a later pass, but
the command itself is generated-only, local-only, metadata-only, and does not
read content or mutate source repos.

## Authority Boundary

Generated approval scope only. It uses catalog metadata and logical paths to
select candidate files for a future bounded content pass. It does not read
source file contents, recurse through source filesystems, call GitHub, call
models, mutate source repos, install hooks, or promote candidate findings to
truth.

## Applies When

- The scan-cycle log marks `priority_content_extracts` as not scanned or scoped.
- The user wants to start with signals that have not been scanned before.
- A future agent needs a reviewable list of candidate priority paths before
  content reads.

## Does Not Apply When

- The user asks for a direct repo-specific buildout plan.
- A source is outside approved scope.
- The task has already authorized exact content paths and byte caps.

## Danger If Misapplied

- Metadata-only candidate paths may be stale, noisy, sensitive, or less important
  than their filenames suggest.
- A path appearing in the scope is not approval to read the file.
- Current value scores in the catalog are routing hints, not proof of authority
  or value.

## Red-Team

- False positives: README and contract path terms can over-select boilerplate.
- False negatives: workflow content can hide in ordinary code files or notebooks
  without obvious path terms.
- Privacy risk: later extraction must cap bytes, redact secrets, and avoid row
  import from private datasets.
- Scope drift risk: future agents must not broaden from scoped paths to entire
  repos without a new human gate.

## Premortem

Failure mode: a future content extractor reads every listed path across all
repos without category or repo-family review.

Guard: this scope pack writes an approval prompt and states that human approval
is required before content reads.

Failure mode: AI navigation files dominate the scope and crowd out workflows.

Guard: the report shows category counts; a human can approve a narrower second
scope focused on workflow/dataflow or governance paths.

Failure mode: noisy nested copies appear as candidate paths.

Guard: temp/worktree/generated/noise paths are skipped, and remaining candidates
are still only metadata-level proposals.

## Validation

Planned validation:

- Focused tests for scope generation and coverage-cycle integration.
- Full pytest.
- Ruff.
- Repository validation.
- Roadmap check without updates.

## Acceptance Status

Implemented as generated candidate scoping only. No roadmap phase is marked
complete by this evidence.
