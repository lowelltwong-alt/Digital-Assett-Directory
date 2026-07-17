---
name: dad-ci-module-boundary-governance
description: Design, implement, audit, or migrate provider-neutral CI and test ownership through declared module paths and dependency edges. Use for monorepos or multi-repo families whenever work changes CI workflows, path filters, module suites, required checks, integration/release lanes, scheduled regression, generated artifacts, or changed-path/dependency test selection; also use after an unrelated-module CI blocker, duplicate push/pull-request run, skipped-required-check deadlock, or silent trigger-scope broadening.
---

# DAD CI Module Boundary Governance

1. Search existing module, ownership, dependency, workflow, and test contracts.
   Reuse DAD's change-selection harness and governance dependency-map pattern;
   do not infer module meaning from directory names alone.
2. Keep '.ci/module-boundaries.yaml' provider-neutral and authoritative. Declare
   stable module IDs, owners, concrete roots, 'code', 'contract', and
   'authoritative_input' triggers, plus upstream-to-downstream
   'direct_dependent' edges with evidence.
3. Use deterministic scripts for path inventory, normalization, validation,
   transitive evaluation, fixture replay, and metadata-only adoption audits.
   Use Luna/low only for bounded ambiguous inventory; use Terra/medium for
   workflow/dependency synthesis; use Sol/high only for an unresolved
   high-consequence architecture conflict. Keep one writer and an independent
   checker.
4. Separate 'ci_contract', 'module', 'integration', 'release', and
   'scheduled_full_regression' lanes. Cross-module suites require explicit
   scope and edges. Scheduled full-system regression must not become an
   ordinary PR gate.
5. Make provider adapters thin. Required PR status must come from an
   always-starting selector/aggregator; conditional module jobs may skip, but
   the required status must always report. Restrict push to the default branch
   or tags when pull requests already cover feature branches.
6. Treat generated artifacts as derived lineage, not authoritative inputs.
   Evaluate both old and new paths for moves. Fail the contract lane on
   unowned paths, invalid/expired exceptions, broad globs, repository-wide
   module workflows, or unreviewed scope changes.
7. Compare declared edges with observed dependency evidence when available.
   When it is unavailable, report 'coverage_unavailable'; never claim the
   dependency graph is complete.
8. Require exceptions to name owner, reason, expiry, reviewer, review time, and
   evidence reference. Keep downstream adoption manual or approval-gated and
   return metadata-only findings.
9. Run the fixture harness and a fresh-eyes review covering false blockers,
   missing edges, broad/narrow paths, moves, generated lineage, duplicate
   events, and required-check deadlocks before recommending activation.

Read 'references/CI_MODULE_BOUNDARY_CONTRACT.md' when authoring or reviewing a
manifest. Use 'templates/ci-module-boundary/' for adoption patches.
