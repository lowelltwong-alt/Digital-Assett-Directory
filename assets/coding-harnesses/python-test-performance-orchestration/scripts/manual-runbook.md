# Manual Runbook

1. Capture current full-suite command, wall time, and slowest tests.
2. Classify changed files by risk: local, shared behavior, public API, or unknown.
3. Propose a selected-test command only when the changed surface is bounded.
4. Require the full suite for shared behavior, public API, flaky tests, or unknown risk.
5. Record timing claims only with the exact commands and machine context.

This runbook is candidate guidance, not proof that selected tests are sufficient.
