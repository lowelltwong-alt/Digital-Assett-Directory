# Operational Readiness Doctor Evidence

Evidence date: 2026-06-29

## Decision

Add an additive diagnostic command:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli doctor
```

Generated outputs:

- `processed/reports/operational_readiness.md`
- `processed/reports/operational_readiness.json`

## Boundary

The command checks current local evidence only. It does not:

- run a scan;
- call GitHub or external services;
- mutate scanned/source repositories;
- mark roadmap gates complete;
- run tests automatically;
- promote generated outputs to truth.

It exits non-zero when required local readiness surfaces are missing, contract
validation fails, the catalog is missing or empty, unverified roadmap gates are
present, GitHub sources are enabled, or tracked git changes exist.

## Risk Tier

`risk_tier=medium`

Why not high:

- It is additive and opt-in.
- It does not change scan, scoring, roadmap, preflight, source mutation, or
  external-research behavior.
- Failure is advisory through exit code and report warnings; it does not block
  git hooks or mutate state outside ignored readiness reports.

## What It Proves

The command can prove that the current local DAD hub has:

- required front-door files;
- valid registered contracts;
- a non-empty local catalog database;
- generated catalog, graph, scan summary, alert inbox, and workflow-part usage
  guidance surfaces;
- no unverified roadmap gates;
- no enabled GitHub source in the active config;
- no tracked git worktree changes at the time of the check.

## What It Does Not Prove

- Clean-clone reproducibility of ignored generated outputs.
- Correctness of generated candidate scores, edges, or recommendations.
- Approval for broad local scans, GitHub scanning, embeddings, scheduled scans,
  external research, automatic workflow assembly, or source-repo mutation.

## Red Team And Premortem

If this fails later, likely causes are:

- future agents treat `doctor` as equivalent to full test execution;
- generated surfaces are stale but still present;
- a clean clone is reported as not ready because ignored generated files are
  absent, which is expected until a local scan/report refresh runs;
- warnings are ignored and a later agent assumes GitHub scanning or workflow
  assembly is approved.

Mitigation:

- the report lists exact validation commands separately;
- the authority boundary is printed in JSON and Markdown;
- the command remains local-only and generated-output-only.

