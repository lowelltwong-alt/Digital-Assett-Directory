# Priority Content Extractor V1

## Summary

Implemented a fail-closed bounded extractor for the priority-content scan-cycle
family. The extractor reads only human-approved candidate paths from the
generated scope file, caps bytes per file, redacts secret-like text, and writes
generated observations.

This evidence records the implementation only. No live repo content pass was
run without human approval.

## Command

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-extract `
  --approval-id "<human-approval-id>" `
  --repo-key "<catalog-repo-key>" `
  --category ai_navigation `
  --category schemas_contracts `
  --max-bytes-per-file 20000 `
  --limit 50
```

The command fails closed without:

- a non-empty approval id;
- at least one repo key;
- at least one category;
- a positive byte cap.

## Outputs

Generated only:

- `processed/learning/priority_content_observations.jsonl`
- `processed/reports/priority_content_extract_report.md`
- `processed/reports/priority_content_extract_report.json`

## Authority Boundary

Generated bounded content observations only. The command reads only
human-approved candidate paths from a generated scope file, resolves them under
configured local source roots, caps bytes per file, redacts secret-like text,
writes generated outputs under `processed/`, and does not mutate source repos,
call GitHub, call models, install hooks, or promote findings to truth.

## Risk Tier

High when run on live repos, because it reads source content.

Medium for this implementation turn, because only synthetic temp fixtures were
read in tests and the live command was not run.

## Applies When

- A human has approved exact repo keys and content categories from the generated
  priority-content scope.
- The task needs candidate content signals for AI navigation, schemas,
  validators, governance, learning loops, or workflow/dataflow files.
- The output will remain generated evidence under `processed/`.

## Does Not Apply When

- The source is outside the approved local scope.
- The user has not approved content reads.
- The task would require reading entire repos, private rows, secrets, GitHub PR
  metadata, CI logs, or external services.

## Danger If Misapplied

- A future agent could treat bounded excerpts as source truth rather than
  generated observations.
- Pattern redaction can miss sensitive material; redaction count is evidence of
  known redactions, not proof of safety.
- Broad repo/category allowlists could accidentally read noisy or sensitive
  content.

## Red-Team

- Path traversal: mitigated by resolving candidate paths under configured source
  roots and rejecting escapes.
- Scope drift: mitigated by reading only paths from the generated scope JSON.
- Secret leakage: mitigated by bounded reads and pattern redaction, but not fully
  eliminated.
- Source mutation: no writes outside DAD `processed/` outputs.
- Over-promotion: every observation is `generated_candidate`.

## Premortem

Failure mode: an agent runs the extractor with broad repo and category
allowlists and imports too much source content.

Guard: command requires explicit allowlists, byte caps, and approval id; docs
call for human review of repo families/categories first.

Failure mode: the generated observations become deterministic learning rules
without review.

Guard: observations are generated candidates and coverage status only says
`extracted_candidate_observations_present`.

Failure mode: secret redaction is over-trusted.

Guard: evidence says redaction is pattern-based and not a proof of complete
privacy safety.

## Validation

- Focused tests cover fail-closed approval requirements, bounded extraction,
  redaction, generated-only outputs, and coverage-cycle status.
- Full validation is required before committing this evidence.

## Acceptance Status

Implemented and tested on synthetic fixtures only. Live content extraction still
requires explicit human approval of repo keys and categories.
