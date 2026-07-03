# Manual Runbook

1. Update `registry/exception-capture-pattern-registry.json` when DAD wants a new
   class of repo-side mail or exception capture.
2. Add or update a case in `examples/synthetic-capture-scenarios.json`.
3. Run `asset-dir exceptions capture-check`.
4. Add a regression test when the case represents a real missed capture.
5. Treat failures as capture-rule or downstream-template work, not as source truth.
