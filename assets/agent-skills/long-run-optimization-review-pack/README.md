# Long-Run Optimization Review Pack

This AI-agnostic pack turns observed command duration into a deterministic
review trigger. It supplements normal task ownership; it does not cancel a
running command or authorize a rewrite.

## Trigger

Run the pack once per normalized command signature in a material work session
when either condition is true:

- an executed command reaches 60 seconds of measured wall time; or
- a command is expected to exceed 120 seconds before it starts.

Normalize the signature by removing temporary paths, timestamps, and fixture
identifiers. Do not retrigger for the same signature unless its duration grows
by at least 25 percent or its implementation changes materially.

## Review lanes

Start an optimization director at high effort. The director reads the measured
evidence, separates algorithmic opportunities from I/O or external waiting,
and delegates the bounded lanes below when they are relevant:

1. Algorithm and architecture reviewer, high effort.
2. Existing library and web research scout, low or medium effort.
3. Language and runtime boundary reviewer, high effort.
4. Benchmark and parity planner, medium effort, after concrete candidates exist.
5. Improvement builder, high effort, only after the director accepts a brief.

The research scout searches current primary sources, official documentation,
package registries, papers, and reference implementations. It returns links,
license and maintenance facts, applicable algorithms, and rejected options. It
does not edit code. The director decides whether to defer, experiment, adopt an
existing library, or issue a bounded build brief. The builder owns only that
brief and must preserve the existing public contract while making the workflow
smaller, faster, or easier to operate.

If subagents are unavailable, run the same lane prompts as explicit local
checklists and record `subagents_unavailable`. Never silently skip the review.

The language lane must consider Rust and DAD's existing
`tools/dad_scan_core` library. Rust is eligible for stable deterministic inner
loops with profile evidence and shadow parity. Authority-sensitive
orchestration, policy, and human gates remain in the host language unless a
separate reviewed architecture decision says otherwise.

## Required questions

- Which measured functions or subprocesses dominate wall time?
- Can algorithmic complexity, batching, caching, or less repeated work remove
  the cost before a language change?
- Does a maintained existing library already solve the hot operation with
  compatible license, provenance, and security posture?
- Is the work CPU-bound, I/O-bound, lock-bound, startup-bound, or external?
- Would Rust, another runtime, or an existing native tool improve the measured
  bottleneck without moving governance semantics?
- What same-input parity test and benchmark prove the claimed gain?

## Required output

Each candidate reports:

- measured baseline and command signature;
- bottleneck class and evidence;
- proposed algorithm, library, or language boundary;
- expected gain as a range, not a promise;
- implementation and maintenance cost;
- correctness, privacy, license, and portability risks;
- benchmark, parity, rollback, and stop conditions;
- disposition: `adopt`, `experiment`, `defer`, or `reject`;
- reviewer effectiveness rating after use.

The director also records every delegated role, effort level, evidence used,
decision, and builder handoff. Research and implementation must remain separate
agents so the builder independently checks the scout's recommendation.

Recommendations are candidate evidence. A faster result is not sufficient if
outputs, ordering, authority boundaries, or failure behavior change.
