# Manual Runbook

1. Update `registry/exception-capture-pattern-registry.json` when DAD wants a new
   class of repo-side mail or exception capture.
2. Add or update a case in `examples/synthetic-capture-scenarios.json`.
3. Run `asset-dir exceptions capture-check`.
4. Run `asset-dir exceptions capture-simulate-emission` to prove the reviewed
   signal can flow through `capture-suggest`, real packet writers, and
   observed-check in a temp repo with suggestion provenance.
5. Add a regression test when the case represents a real missed capture.
6. Treat failures as capture-rule or downstream-template work, not as source truth.
