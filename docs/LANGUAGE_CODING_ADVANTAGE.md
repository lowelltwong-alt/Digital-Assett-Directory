# Language Coding Advantage

Status: candidate DAD control-plane guidance for Python, Rust, and future
language-specific AI coding assets.

## Purpose

DAD should help coding agents write better-than-average code by knowing which
language features, toolchains, libraries, and harnesses are actually useful in
context. The target is not novelty. The target is code that future agents can
read, validate, refactor, and repair with fewer hidden assumptions.

The source of truth is:

- `registry/language-coding-advantage-registry.json`
- `schemas/language-coding-advantage-registry.schema.json`
- `registry/trusted-source-registry.json`
- `registry/coding-tactics-radar.json`
- language assets such as `assets/python-ai-advantage-preflight/`,
  `assets/python-underused-idioms/`, and `assets/rust-buildout-guide/`

## Boundary

Language guidance is candidate evidence. It does not override repo-local style,
tests, security policy, source authority, or human gates.

Do not copy third-party docs, code, benchmarks, private rows, raw logs, or
credentials into DAD. Frontier intake uses pointers, source IDs, safe summaries,
hashes, applicability limits, and validation ideas.

Scores, source trust tiers, popularity, benchmark claims, and agent confidence
are not proof. A technique becomes durable DAD guidance only after screened
source pointers, local validation, context limits, and reviewed promotion.

## How Agents Use It

Before material coding, preflight should route by language and task:

- Python work: check Python advantage assets, idiom cards, and Python tactics.
- Rust or performance work: check the Rust buildout guide before proposing Rust.
- Mixed Python/Rust work: require profile evidence, native validation, and
  same-scope shadow parity before timing claims.
- Unknown or new language work: use the future-language template record before
  creating any downstream recommendation.

During midflight, agents should check this registry when code starts feeling
generic, when a performance claim appears, when a language feature could make a
contract safer, or when a toolchain check could turn a review concern into a
deterministic failure.

Postflight should record what helped, failed, was ignored, or was harmful. Useful
language discoveries go through `dad:need:language-frontier-signals`; harness
outcomes go through `dad:need:coding-harness-feedback`.

## Python

Python guidance focuses on:

- explicit JSON/config/domain boundaries;
- side-effect isolation for fast tests;
- stdlib features that make resource lifetime, state, or error causality clear;
- test orchestration before expensive full-suite runs;
- profiling before any Rust replacement discussion.

Use the smallest Python feature that makes the code easier to verify. Avoid
clever rewrites whose only benefit is using an advanced idiom.

## Rust

Rust guidance focuses on:

- profiled CPU-bound hot paths;
- deterministic parsers, chunkers, scanners, hashing, and static-analysis tools;
- compiler-backed invariants: newtypes, typed errors, enums, exhaustive matches,
  `#[must_use]`, doc tests, and Clippy;
- small mixed-language boundaries where Python keeps orchestration and Rust owns
  a stable hot function.

Rust does not enter because it is exciting. It enters after profiling, Python
first-pass fixes, shadow parity, and human review for full ports.

## Frontier Refresh Loop

Reviewed source cadences live in `registry/trusted-source-registry.json`.

Weekly or monthly refreshes look for:

- newly stabilized language/tooling features;
- deprecations or version changes that should update existing guidance;
- high-leverage libraries or crates worth evaluating;
- AI-overlooked patterns that are uncommon in average examples but valuable in
  DAD contexts;
- new harness ideas that can prove or falsify a claim.

Refresh output is candidate-only:

```text
language
source_id_or_url
safe_summary
why_ai_coding_may_improve
applicability_limits
validation_or_eval_idea
target_control_plane
```

Forbidden:

```text
copied third-party docs
raw private rows
credentials or tokens
long source blobs
unverified benchmark claims as truth
```

## Promotion Checklist

Promote a language advantage only when:

- the source is official, reviewed, or explicitly justified;
- the applicable language versions and tool support are named;
- avoid-when limits are written;
- a local example, harness, or validation command exists;
- security and source-boundary risks are screened;
- at least one postflight or eval outcome supports the recommendation;
- downstream repos receive pointers and local review steps, not copied assets.

## Premortem

Likely failure story: DAD sees a clever Rust crate or Python feature, writes it
into broad agent instructions, and future agents cargo-cult it into repos where
it adds complexity, hides bugs, or skips local tests. The prevention is boring
and important: pointer-only intake, explicit avoid-when limits, local validation,
and no promotion without reviewed evidence.
