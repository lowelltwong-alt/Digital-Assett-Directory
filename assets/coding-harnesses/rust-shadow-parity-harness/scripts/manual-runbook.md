# Manual Runbook

1. Define the Python native test scope and expected structured report.
2. Define the Rust shadow scope and expected structured report.
3. Compare test identities through an explicit Python-to-Rust map.
4. Treat missing, stale, empty, or mismatched reports as unverified parity.
5. Report timing deltas only when parity is verified for the same scope.

This runbook is candidate guidance; Rust speed does not prove coverage.
