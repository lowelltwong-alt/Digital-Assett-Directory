# Lesson Automation Coverage V1

## Summary

Implemented a no-rescan coverage and scan-cycle report for lesson automation.
The goal is to help future agents start with unscanned signal families and
uninstrumented repos instead of repeating broad scans.

## Risk Tier

Medium-high.

Reason: this influences future agent routing across many repos. The blast radius
is constrained because the command is report-only, generated-only, local-only,
and does not mutate downstream repos.

## Authority Boundary

Generated coverage and scan-cycle guidance only. It reads the current catalog,
configuration metadata, and generated-output presence. It does not rescan source
repos, read source file contents, call GitHub, call models, mutate downstream
repos, install hooks, or promote candidate findings to truth.

## Applies When

- An agent is deciding what repo or signal family to inspect next.
- The user has asked not to repeat previous broad scans.
- A future task needs to route into unscanned or under-instrumented areas.

## Does Not Apply When

- The user explicitly authorizes a fresh broad scan.
- The source scope is not approved even for metadata observation.
- A target repo is named for direct repo-specific inspection.

## Danger If Misapplied

A generated gap can be mistaken for proof that a repo or workflow has no value.
It only means DAD has not observed the surface yet. Missing learning-loop files
also do not authorize mutation; a repo must be explicitly selected before
files-only installation.

## Outputs

Generated only:

- `processed/reports/lesson_automation_coverage.md`
- `processed/reports/lesson_automation_coverage.json`
- `processed/reports/scan_coverage_cycle.md`
- `processed/reports/scan_coverage_cycle.json`

Tracked support:

- `docs/LESSON_AUTOMATION_COVERAGE.md`
- `src/digital_asset_directory/lesson_automation_coverage.py`
- `tests/test_lesson_automation_coverage.py`

## Red-Team

- Privacy leak risk: mitigated by not reading source contents, raw user
  messages, GitHub, CI logs, or private rows.
- Repetition risk: mitigated by a scan-cycle log that records checked and
  intentionally skipped inputs.
- False negative risk: metadata-only catalog evidence can miss existing repo
  surfaces; reports use "not observed" language.
- Mutation risk: command writes only under `processed/reports/`.
- Governance risk: downstream learning-loop installation remains a separate
  explicit command with per-repo approval.

## Premortem

Failure mode: a future agent treats the report as a scorecard and edits many
repos to "fix" gaps.

Guard: docs and generated reports state that all actions require source-scope,
privacy, and mutation gates.

Failure mode: the agent repeats old broad scans anyway.

Guard: the generated scan-cycle log lists checked inputs, skipped inputs, next
signal families, and stop conditions.

Failure mode: content-light metadata makes a real workflow look absent.

Guard: the command reports scan depth and recommends bounded priority-content
extracts only after approval.

## Validation Plan

- Focused tests for metadata-only gaps, deterministic output, and generated-only
  writer behavior.
- Full pytest.
- Ruff.
- Repository validation.
- Roadmap check without updates.

## Acceptance Status

Implemented as generated candidate reporting. No roadmap phase is marked
complete by this evidence.
