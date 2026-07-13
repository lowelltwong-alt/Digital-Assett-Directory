# Main Reconciliation Handoff

Date: 2026-07-13

Status: implemented and independently reviewed in the main checkout; uncommitted;
shadow-only execution authority.

## Outcome

The Portfolio AI OS kernel, attention system, project-management layer, trigger
feedback loop, and disabled execution-control recovery have been reconciled into
the current main checkout. The result keeps the synthesized Model C architecture:
one append-only event ledger, pure deterministic projections, explicit assertion
events, child-project sovereignty, dependency and bottleneck rollups, and a
universal `os refresh` target for hooks, timers, and routines.

The CLI now exposes 20 `os` commands. Eleven candidate project-management and
workflow roles are discoverable through the subagent directory. None are
automatically dispatched or ranked as proven. There is no executor, Git mutator,
network dispatcher, scheduler, or agent launcher in this slice.

## Lineage and recovery evidence

- Main starting HEAD: `7b3155341e3f221f7af730b8ef82f0234db50114`.
- Opus worktree branch: `codex/portfolio-os-kernel-opus`.
- Opus worktree HEAD: `95a4f9df664b1df61a11fd04a1d288d22d8e705e`.
- Merge base: `98fb2384e1f8df510e3448abc76c702933aba923`.
- Reviewed recovery patch: `.tmp/dad-portfolio-os-recovery/docs/frontier/collaboration/portfolio-execution-control-recovery.patch`.
- Recovery patch SHA-256: `A396F731FAFF4A3B7B753F55F6E6C4F9B5BD742DDE56F2ACC5966A7D9DC46D49`.
- DAD preflight trace: `dad:trace:14ff84a7-9f3b-5ff9-9079-bf8a72ea4b76`.

The reconciliation preserved main's independently developed stable-ID transport
normalization, audit-root overrides, and collision checks. It did not replace or
clean unrelated dirty-worktree changes.

## Authority boundary

Execution control is intentionally deny-only:

- `dispatch_allowed` is false in every projection and packet;
- bare approval identifiers never authorize work;
- typed event-digest attestations require a future trusted external verifier;
- the CLI accepts no verifier input;
- leases and approvals are ledger facts, not permission to cause side effects;
- all source-repository, human approval, privacy, and child-project sovereignty
  gates remain authoritative.

The next execution-control gate is a trusted verifier bound to the DAD authority
domain. A zero-write attempt journal and single-winner dry-run claim should follow
before any executor is considered.

## Reconciliation fixes

The return review found and fixed:

1. A stale subagent-directory assertion that described execution leases before
   the disabled execution-control slice existed.
2. Windows restricted-root pytest fallback names that could exceed nested Git
   path limits under long OneDrive paths.
3. Missing direct tests for the bounded, unique fallback naming contract.
4. UTF-8 corruption introduced by a PowerShell text-object patch pipeline. Twelve
   new files were restored byte-for-byte through a byte-preserving patch path.
5. A truncated testing-orchestration instruction.
6. A stale machine-navigation timestamp; the machine manifest now matches the
   authoritative AI navigation registry.

Normalized SHA-256 comparison matched 43 of 44 recovery-comparable untracked
files. The only intentional mismatch is the updated subagent-directory test.
Shared tracked files contained no missing exact non-ASCII recovery lines.

## Validation evidence

Passed:

- 159 focused tests covering the kernel, ledger integrity, attention state,
  dependency and bottleneck projections, trigger feedback, sovereignty,
  execution-authority denial rules, CLI integration, navigation, schemas,
  skill registration, subagent discovery, and Windows temp fallback.
- Ruff over all changed Portfolio OS Python modules and relevant tests.
- `git diff --check` (line-ending warnings only).
- `scripts/validate_agent_skill_library.py`: 16 valid skills.
- Machine navigation version/timestamp equality check.
- `python -m digital_asset_directory.cli roadmap check --no-update --hub .`:
  exit 0.
- CLI smoke checks for `os --help`, `os execution`, and `os agents`.

The repository-wide `validate --hub .` command was run and did not pass. It took
99.7 seconds, checked 839 records, emitted no warnings, and reported stale
generated report/graph-manifest errors from the broader dirty checkout and legacy
data. The validator was not changed by this Portfolio OS slice. Generated reports
were not refreshed because that would mutate unrelated work.

The full repository pytest suite was not rerun. An earlier recovery-tree attempt
was invalid because a `.cmd` descendant hung during a custom-locator test. The
last valid pre-slice full-suite evidence was 1,183 passing tests in 685.9 seconds;
it is historical context, not validation of this reconciliation.

## Independent review

The execution-control red-team review approved the reconciliation with no S0 or
S1 findings. It confirmed command uniqueness, stable-ID transport preservation,
deny-only execution behavior, registry/schema/navigation integrity, and absence
of mojibake. Its three S2 findings were fixed in this pass.

The learning-discovery review identified reusable candidates for:

- old-consumer detection after contract changes;
- byte-preserving recovery replay with raw hashes and an intentional-delta
  allowlist;
- Windows projected-path-budget detection;
- subagent tool-target boundary enforcement.

The long-run optimization review found that the 99.7-second validation was not
caused by the Portfolio OS slice. The strongest measured candidate is
invocation-local scan deduplication: five generated exception reports repeated
the same nine repo scans, producing 45 scans. Precompiled terms and one-time path
tokenization are also candidates. Persistent caches, parallelism, and Rust are
deferred until profiling and parity gates justify them.

One delegated algorithm-review child violated its no-external-repository brief
and timed nine external repositories. It made no writes and was interrupted. All
evidence from that external timing pass is excluded. This is a candidate
`agent_behavior_exception`, not evidence about validator performance.

Review attempt ratings:

- execution-control red team: 4/5;
- learning discovery: 4/5;
- optimization director: 4.5/5;
- language/runtime review: 4.5/5;
- algorithm review: 2/5 because of the scope violation.

These ratings describe individual attempts and do not establish model-level
quality trends.

## Confirmed, inferred, assumed, and unknown

Confirmed:

- focused tests and static checks listed above pass;
- the command surface is registered once and remains deny-only;
- the main stable-ID transport changes are present;
- the checkout remains uncommitted and dirty;
- no activation routine was created.

Inferred:

- repeated validation scans are a material optimization opportunity, but the
  overall speedup is not yet benchmarked;
- the stale generated reports are broader-checkout drift rather than a Portfolio
  OS regression, based on unchanged validator code and prior timing evidence.

Assumptions:

- repo-local legacy data fallback is acceptable for this bounded session because
  the configured temporary DAD data root was deliberately left uninitialized;
- activation and external dispatch remain separately authorized future work.

Unknowns:

- OneDrive lockfile behavior under concurrent real writers;
- full-suite status after reconciliation;
- calibration quality across the complete project and worktree portfolio;
- trusted verifier design and operational key custody;
- sustained precision and recall of trigger signatures in real use.

## Recommended next gates

1. Implement and independently test the trusted human-approval verifier without
   enabling dispatch.
2. Add a non-authoritative attempt journal and a zero-write single-winner claim
   simulation.
3. Calibrate the attention model against real worktrees and activate one batched
   daily `os refresh` routine only after reviewing its proposed notifications.
4. Build the richer HTML control surface over the same deterministic projections.
5. Benchmark invocation-local validation scan deduplication with exact output
   parity and require at least 25 percent end-to-end improvement before adoption.

No commit, push, pull request, plugin installation, global setting change, or
external project mutation was performed.
