# Lesson Automation Coverage

This report path exists so future agents can start with what has not been scanned
or instrumented yet, instead of repeating broad passes.

## Command

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend lesson-automation-coverage --limit 50
```

The command writes generated candidate outputs only:

```text
processed/reports/lesson_automation_coverage.md
processed/reports/lesson_automation_coverage.json
processed/reports/scan_coverage_cycle.md
processed/reports/scan_coverage_cycle.json
```

## What It Checks

- current catalog assets and repository boundaries;
- latest scan summary metadata;
- local and GitHub source configuration metadata;
- presence of generated reports that indicate prior signal-family work;
- repo-level surfaces visible in the catalog, such as AI front doors, TOCs,
  learning-loop files, and governance dependency maps.

## What It Does Not Check

- source file contents;
- fresh filesystem recursion;
- GitHub PR or issue APIs;
- CI logs or remote artifacts;
- model or embedding calls;
- downstream repo writes.

## Scan-Cycle Log

`processed/reports/scan_coverage_cycle.md` is the handoff surface for the next
agent. It records:

- what this pass checked;
- what was intentionally skipped;
- which signal families are next in the cycle;
- which next steps require human approval;
- stop conditions for broad scans, external APIs, and downstream repo mutation.

Use the log as a routing aid, not as proof that a repo has no value. A missing
surface means DAD has not observed it yet.

## Context Boundaries

Applies when:

- an agent is choosing the next repo or signal family to inspect;
- the user wants new work to begin with unscanned or uninstrumented areas;
- a future task needs to avoid redoing broad scans.

Does not apply when:

- the user explicitly authorizes a fresh broad source scan;
- a target repo is outside the approved source scope;
- the job is to inspect one named repo directly.

Danger if misapplied:

- generated gaps can be mistaken for negative evidence;
- a future agent may install learning-loop files without per-repo approval;
- metadata-only evidence may hide existing docs, tests, or governance files.

## Review Cycle

Default order:

1. catalog metadata and repo boundaries;
2. priority content extracts for approved front doors, schemas, docs, tests, and
   governance files;
3. repo-local learning events;
4. cross-repo governance maps and mirrors;
5. bounded local git history and worktree archaeology;
6. CI logs, release notes, and changelogs;
7. GitHub PR, issue, and review metadata;
8. private-source workflow sweeps without row import.

Each step remains gated by source scope, privacy, and mutation rules.

## Priority Content Scope

Before a bounded content extract pass, generate an approval scope from catalog
metadata:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-scope --limit 200 --per-repo-limit 12
```

This writes:

```text
processed/reports/priority_content_extract_scope.md
processed/reports/priority_content_extract_scope.json
processed/reports/priority_content_extract_approval_prompt.md
```

The scope command still does not read source file contents. It only lists
candidate paths already present in the catalog and classifies them into
human-review categories:

- AI navigation and repo contracts;
- schemas, contracts, and registries;
- validators, tests, and quality gates;
- governance, security, and privacy boundaries;
- learning loops and pay-forward surfaces;
- workflows, dataflow, and normalization.

After this scope exists, `recommend lesson-automation-coverage` marks
`priority_content_extracts` as `scoped_not_extracted`. Human approval is still
required before any content is read.

## Bounded Priority Content Extract

After human approval, use the fail-closed extractor:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-extract `
  --approval-id "<human-approval-id>" `
  --repo-key "git-projects/00_lawfirm_os/lawfirm-os-orchestrator" `
  --category ai_navigation `
  --category schemas_contracts `
  --max-bytes-per-file 20000 `
  --limit 50
```

The extractor refuses to run without:

- an approval id;
- at least one repo key;
- at least one category;
- a positive byte cap.

It writes generated outputs only:

```text
processed/learning/priority_content_observations.jsonl
processed/reports/priority_content_extract_report.md
processed/reports/priority_content_extract_report.json
```

The extractor reads only candidate paths from the generated scope file, resolves
them under configured local source roots, caps bytes per file, redacts
secret-like text, and keeps all observations as `generated_candidate` evidence.
After observations exist, `recommend lesson-automation-coverage` marks
`priority_content_extracts` as `extracted_candidate_observations_present`.
