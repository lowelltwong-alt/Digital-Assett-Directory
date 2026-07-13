# Subagent Evaluation Pipeline Optimization Review

Date: 2026-07-13

Status: measured review only; no source implementation; no adoption authorized.

## Trigger

The full tests/test_subagent_evaluations.py file passed 27 tests in 79.4
seconds. That distinct command signature crossed DAD's 60-second optimization
threshold.

## Usable findings

The safe Python candidate is invocation-local reuse of compiled JSON Schema
validators, methodology snapshots, and snapshot hashes inside one
validate_records() call.

Measured repository-local evidence:

- collection: 27 tests in 1.3 seconds;
- seed validation call: 0.91 seconds;
- seed profile: 19 validator constructions and 0.707 seconds in schema checks;
- ingest plus double graph: 5.92-second call, 6.74-second wall time;
- invocation-local validator probe: 60 builds reduced to 15;
- representative wall time: 6.742 seconds to 6.091 seconds, about 9.7 percent;
- direct validate_records: 0.3055 seconds to 0.1293 seconds with equal result.

The candidate remains an experiment because it has not achieved the required 25
percent end-to-end median improvement across three uncontended trials with exact
output, error, concurrency, crash-prefix, authority, and full-suite parity.

Use existing testmon, --picked, -k, and --lf only for inner-loop selection.
Defer pytest-xdist. Reject a process-global validator cache, shared mutable test
hubs, replacement validators, Rust migration, or weakened durability and
authority checks.

## Scope incident

All explicit task paths were inside DAD, but the existing
assert_dad_write_allowed() implementation traversed Git ancestors and issued
remote probes at an ancestor Git root outside the repository. The director
detected this after profiling.

All write-guard and remote-cache timings are excluded from optimization evidence.
The ancestor traversal is a separate scope and security defect requiring a newly
authorized brief. No source files were changed, no full 79-second rerun occurred,
and no command remains running.

## Attempt ratings

- tooling and library scout: 4.5/5;
- optimization director and runtime lane: 3.5/5, gate failed because indirect
  scope crossing was detected only after profiling;
- algorithm and profiling delegate: 1/5, interrupted without a usable final.

These are parent-observational, attempt-scoped ratings. They cannot rank a model
family, promote a role, change routing, or authorize an instruction revision.
