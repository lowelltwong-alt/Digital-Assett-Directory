---
name: dad-iteration-optimizer
description: Diagnose and reduce slow commands and repeated workflows with measurement-first optimization, parity checks, and privacy-preserving evidence.
---

# DAD Iteration Optimizer

1. Preserve a baseline: command, input scope, wall time, correctness result,
   and resource signal.
2. Locate the bottleneck before changing languages. Check algorithmic
   complexity, redundant I/O, repeated parsing, process startup, network waits,
   and test isolation.
3. Prefer the simplest proven improvement: narrower scope, incremental state,
   batching, caching with invalidation, a mature library, or safe parallelism.
4. Consider Rust only for a measured deterministic CPU- or parsing-heavy
   hotspot with a stable, parity-testable boundary. Keep orchestration in the
   existing suitable runtime when latency dominates.
5. Benchmark the same workload after a change and run parity plus failure-path
   tests. Reject speedups that weaken correctness, privacy, or governance.
6. Capture the reusable optimization pattern, its limits, and the evidence in
   DAD.

Use the reviewed long-run optimization pack when available for commands that
meet its documented duration trigger. Do not infer a bottleneck from elapsed
time alone.
