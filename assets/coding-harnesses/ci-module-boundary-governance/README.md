# CI Module Boundary Governance

Provider-neutral candidate harness for declaring module ownership and dependency
edges, selecting only affected suites, separating PR, integration, release, and
scheduled-full lanes, and auditing CI trigger contracts without mutating source
repositories.

The deterministic manifest and evaluator are the authority for suite selection.
Provider workflow files are adapters. Missing semantic dependency evidence is
reported as 'coverage_unavailable'; it is never treated as proof of completeness.
GitHub-specific workflow inspection lives in the revision-bound adapter module,
not in the provider-neutral evaluator.
