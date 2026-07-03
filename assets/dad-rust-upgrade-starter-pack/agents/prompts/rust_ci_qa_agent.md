# Prompt: Rust CI/QA Agent

Add Rust CI for DAD's scanner core.

Required:

- PR workflow with fmt, clippy, test, wrapper help.
- Long workflow with nextest, deny, audit, coverage, large fixture scan.
- Clear separation between PR and long CI.
- Artifact upload for JSON reports.
- Path filters so Rust CI triggers on `tools/dad_scan_core/**`, `scripts/run_dad_scan_core.py`, and Rust docs/config.

Do not make long CI a required PR blocker until it has passed twice manually.

Report:

- files changed;
- commands run locally;
- commands not run;
- remaining risks.
