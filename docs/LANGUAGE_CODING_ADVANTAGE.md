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
- `assets/coding-harnesses/language-frontier-research/`
- language assets such as `assets/python-ai-advantage-preflight/`,
  `assets/python-underused-idioms/`, and `assets/rust-buildout-guide/`

## Language Asset Shape

Every language DAD adopts should have the same minimum control surface:

- a registry row in `registry/language-coding-advantage-registry.json`;
- reviewed or candidate source IDs in `registry/trusted-source-registry.json`;
- proof-surface refs that point to the shared categories in
  `proof_surface_categories`;
- an internal playbook or asset that explains why the language helps agents;
- internal agent coding guidelines with proof requirements and failure modes;
- codebase watch targets that tell agents which high-signal projects or tools to
  study for patterns, not copy from;
- a frontier promotion policy that says what evidence promotes or rejects an
  idea;
- harness routes that test or falsify the proposed benefit;
- overlooked-pattern records that tell agents what to look for in code scans;
- postflight feedback paths so DAD learns what helped, failed, or was harmful.

The repeatable question is: what does this language, runtime, compiler,
toolchain, or ecosystem let an agent check, inspect, refactor, or run better
than an average generated-code workflow?

## Proof Surface Matrix

`registry/language-coding-advantage-registry.json` now carries a shared
`proof_surface_categories` matrix. Python, Rust, and every future language row
must reference the proof surfaces it can route to as a common checklist. A
reference is not a claim that the proof surface is authoritative in every repo;
the row's validation gates, local tool configuration, and repo authority decide
that. This gives agents a deterministic checklist before they promote a tactic:

- syntax/load proof before deeper analysis;
- compiler, type-checker, formatter, or linter proof when the repo already
  accepts that tool or the proposal is candidate-only;
- structured boundary proof for JSON, reports, schemas, and parser outputs;
- test orchestration proof when feedback speed or selected suites matter;
- property or fuzz proof for parsers, chunkers, normalizers, IDs, and
  serializers;
- profile or trace proof before optimization, hang, leak, or Rust-migration
  claims;
- package, license, advisory, and compatibility proof before a tool becomes a
  shared dependency;
- agent-readable output proof so future agents can parse, diff, audit, and
  postflight the result.

This matrix is intentionally language-neutral. Python maps to runtime
introspection, schema boundaries, pytest, property tests, static checkers, and
profiling. Rust maps to compiler/type-system checks, Clippy, cargo metadata,
doc tests, fuzz/property tests, API compatibility, and narrow interop
boundaries. A future language such as Go, TypeScript, or Zig starts as a
template row until its official sources, proof commands, failure examples, and
harness route are named.

The matrix is not security evidence by itself. It is a routing aid and
promotion checklist. Security-sensitive, public/private, cross-repo, and
protected-repo actions still use the harder governance gates elsewhere in DAD.

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
- Property, fuzzing, static-analysis, and alternate-runner ideas: treat them as
  harness candidates until a local validation command shows they help in the
  target repo.
- Unknown or new language work: use the future-language template record before
  creating any downstream recommendation.

During midflight, agents should check this registry when code starts feeling
generic, when a performance claim appears, when a language feature could make a
contract safer, or when a toolchain check could turn a review concern into a
deterministic failure.

Postflight should record what helped, failed, was ignored, or was harmful. Useful
language discoveries go through `dad:need:language-frontier-signals`; harness
outcomes go through `dad:need:coding-harness-feedback`.

When a repo notices a language-frontier signal during ordinary work, it should
also pass the observable signals through the exception-capture surface. The
reviewed rule `exception-capture-rule:language-frontier-signal` maps safe
Python, Rust, mixed-language, and future-language discoveries to
`capability_suggestion` mail with these required fields: `language`,
`source_id_or_url`, `safe_summary`, `why_ai_coding_may_improve`,
`applicability_limits`, `proof_surface`, `validation_or_eval_idea`, and
`target_dad_surface`. Older repo capture surfaces should refresh before treating
that packet as complete.

## Language Improvement Loop

This is the deterministic loop for Python, Rust, and any later language DAD
adopts:

1. Preflight routes by language, task, repo context, and risk to the language
   registry, coding tactics radar, and the matching harness.
2. Midflight checks the registry again when a claim appears about speed, safety,
   parser/chunker correctness, test selection, static analysis, package tooling,
   or a language feature that could change the proof surface.
3. The agent records only pointer-safe source refs, safe summaries, validation
   ideas, and applicability limits. It does not copy third-party code, private
   repo content, generated corpora, logs, or benchmark tables into DAD.
4. A local proof command or harness outcome is required before any language
   discovery becomes DAD guidance. For Python, that often means schema/type/test
   evidence, profiling, or pytest orchestration. For Rust, that means compiler,
   Clippy, test, doctest, fuzz/property, parity, or same-workload performance
   evidence.
5. Postflight records whether the tactic helped, failed, was ignored, or was
   harmful. DAD then updates assets, harnesses, or watchlists through reviewed
   promotion rather than by agent enthusiasm.

The high-value pattern is not "use a fancier language feature." It is "add a
machine-checkable proof surface future agents can run, inspect, and falsify."

For new Python, Rust, mixed-language, or future-language ideas, route the first
screen through `assets/coding-harnesses/language-frontier-research/`. That
harness asks for a source pointer, safe summary, applicability limits, proof
surface, and validation idea before DAD changes a tactic, idiom card, buildout
guide, or downstream recommendation.

For a scheduled frontier refresh, use
`assets/coding-harnesses/language-frontier-research/prompts/language-frontier-refresh.prompt.md`.
That prompt is the standard way to turn a source watch item into candidate DAD
evidence. It requires a trusted-source check, proof surface, falsification idea,
AI-overlooked pattern, and target DAD surface while blocking copied docs, copied
source, private rows, raw logs, long blobs, and benchmark-only claims.

## Internal Guidelines And Codebase Study

The language registry now separates three things agents often blur together:

- `agent_coding_guidelines`: DAD's internal rules for using the language better,
  each with proof requirements and a failure story.
- `ai_overlooked_operations`: concrete commands, inspections, or proof
  operations agents should consider before guessing from common GitHub-shaped
  examples. Each operation carries source IDs, review status, maturity,
  cost/risk, and `candidate_only` metadata.
- `codebase_watch_targets`: high-signal codebases, tools, or official projects
  worth studying for patterns. These are pointers for research intake, not
  license to copy source, docs, fixtures, or configs.
- `frontier_promotion_policy`: the evidence required before a frontier idea
  becomes DAD guidance, plus rejection signals that stop cargo-cult adoption.
- `recommendable`: whether an agent-facing matcher may use the row directly.
  Template rows must set this to `false`.

This is how DAD gets better than generic AI coding: it watches places where
strong engineers encode proof in compilers, linters, test runners, profilers,
fuzzers, and release processes, then converts only validated lessons into local
assets or harness cases.

The default coding style is AI-legible rather than merely clever. A useful
language advantage should leave future agents with named boundaries,
machine-readable outputs, stable commands, negative cases, source pointers, and
local validation hooks. If a technique makes code shorter but harder to inspect,
route, replay, or falsify, DAD treats it as a candidate at best.

Codebase watch targets use structured `example_refs` with `source_id`, `ref`,
`review_status`, and `provenance_note`. For real language rows, refs must be
HTTPS pointers matching the trusted source's reviewed URL patterns. Template
rows may use `replace-with-*` placeholders only while `recommendable` is false.
`reviewed` on a source pointer means the address pattern is approved for intake;
it does not mean every technique, crate, benchmark, or claim from that source is
adopted DAD guidance.

## Python

Python guidance focuses on:

- explicit JSON/config/domain boundaries;
- side-effect isolation for fast tests;
- property-based invariant tests for deterministic parsers, serializers,
  dedupe, normalization, and ID transformations;
- static checker contracts when a repo already runs mypy, pyright, or similar;
- stdlib features that make resource lifetime, state, or error causality clear;
- test orchestration before expensive full-suite runs;
- profiling before any Rust replacement discussion.

Use the smallest Python feature that makes the code easier to verify. Avoid
clever rewrites whose only benefit is using an advanced idiom.

Internal DAD default: Python remains the orchestration, governance, review,
mail, reporting, and human-workflow language unless profiling or maintainability
evidence shows a leaf tool belongs elsewhere. Python assets should make future
agents better at seeing data boundaries, side effects, fixture cost, type-checker
contracts, and safe failure paths.

Good Python frontier candidates usually answer at least one of these questions:

- Can a test generator expose edge cases examples miss without leaking private
  inputs?
- Can a type checker, schema validator, or linter turn a future-agent mistake
  into a deterministic failure?
- Can pytest collection, markers, fixtures, or report plugins reduce feedback
  time without hiding shared-contract coverage?
- Can CPython, stdlib, pytest, Hypothesis, type-checker, Ruff, uv, PyO3, or
  maturin patterns make the next agent's Python easier to inspect, validate, or
  safely speed up?

Python operations DAD now expects agents to consider:

- structural source queries with `ast`, `symtable`, `inspect`, and
  `importlib.metadata` when text search is too blunt;
- runtime-cost and failure traces with `cProfile`, `pstats`, `tracemalloc`, and
  `faulthandler` before speed, leak, hang, or Rust-migration claims;
- pytest collection, durations, markers, and small invariant/property probes
  before trimming a slow suite;
- environment and tooling census before suggesting a Python version feature,
  checker, package manager, or dependency;
- coverage, mutation-test, and repeatable profiling scouts when a passing suite
  may be falsely green or a speed claim may be measurement noise;
- AI-legible change surfaces: named parsers, schemas, stable commands, safe
  summaries, and negative tests around shared JSONL/report/CLI boundaries.

## Rust

Rust guidance focuses on:

- profiled CPU-bound hot paths;
- deterministic parsers, chunkers, scanners, hashing, and static-analysis tools;
- compiler-backed invariants: newtypes, typed errors, enums, exhaustive matches,
  `#[must_use]`, doc tests, and Clippy;
- small mixed-language boundaries where Python keeps orchestration and Rust owns
  a stable hot function.
- fuzzable parser/chunker/scanner boundaries that accept bytes or text from
  repo-local or cross-repo sources;
- machine-readable Rust test evidence when parity, speed, or safety claims need
  auditability.

Rust does not enter because it is exciting. It enters after profiling, Python
first-pass fixes, shadow parity, and human review for full ports.

Internal DAD default: Rust is deterministic leaf tooling first. Strong candidates
are read-only scanners, chunkers, hashers, manifest validators, source-offset
mappers, parser boundaries, and single-binary validators that reduce per-repo
environment drift. Python keeps orchestration and review authority. Rust code
should be easier for agents to audit because the compiler, Clippy, doc tests,
newtypes, enums, and property/fuzz tests carry part of the evidence.

Good Rust frontier candidates usually answer at least one of these questions:

- Can the compiler represent a state, ID, packet, or error boundary that Python
  or agent-written strings keep mixing up?
- Can fuzzing or property tests attack a pure boundary before the tool becomes a
  shared validator?
- Can a single Rust CLI remove per-repo environment drift without taking over
  orchestration logic that Python should keep?
- Can test-runner output show the same tests ran before anyone claims a speed
  win?
- Can high-signal Rust codebases such as compiler tooling, scanners, parser
  infrastructure, fuzz targets, or Python/Rust tooling suggest a small DAD
  harness experiment instead of a broad rewrite?

Rust operations DAD now expects agents to consider:

- `cargo metadata`, `cargo tree`, and dependency/advisory checks before adding
  Rust tooling or promoting a crate;
- `cargo fmt`, `cargo clippy`, `cargo check`, tests, doc tests, and rustdoc as
  executable evidence, not optional polish;
- structured Rust test identity and same-scope parity reports before any
  Python-vs-Rust speed claim;
- fuzz, property, mutation, and Miri-style scouts around pure parser, chunker,
  scanner, serializer, and unsafe-sensitive boundaries;
- API compatibility checks before a Rust crate or CLI becomes a DAD-owned shared
  dependency;
- benchmark and profiler scouts before adding parallelism, async, unsafe
  optimization, or a broader Rust port;
- AI-legible leaf contracts: schema-versioned JSON/JSONL, deterministic ordering,
  typed errors, and Python-side validators that can prove what the Rust tool
  emitted.

## Adding Another Language

For Go, TypeScript, Zig, or any later language, start from
`future-language-template` in the registry. A future language needs:

- official or reviewed source IDs;
- at least one codebase watch target;
- proof tools and minimum validation commands;
- a harness route or small local eval;
- avoid-when and rejection signals;
- a postflight/usage loop so DAD learns whether the advice helped.

Do not add a language because it is popular or because an agent prefers it. Add
it when it gives agents a new deterministic proof surface or makes code easier
to inspect, run, repair, or validate in your repo family.

## Source Watch Groups

The machine-readable watchlist is `registry/trusted-source-registry.json`.
Agents should refresh from reviewed source IDs, then create pointer-only intake
records. Useful starting groups:

| Language | Source IDs | Watch For |
| --- | --- | --- |
| Python | `python-core`, `python-packaging`, `python-typing`, `pytest-dev`, `hypothesis`, `python-type-checkers`, `python-test-quality-frontier`, `python-performance-profiling`, `python-interface-boundary-codebases`, `astral` | PEP/version changes, typing and diagnostics, pytest orchestration, property tests, coverage/mutation-test signals, profiling and benchmark design, schema/CLI/report interface patterns, fast tooling, packaging/security shifts. |
| Rust | `rust-lang`, `rust-community-frontier`, `rust-performance-measurement`, `rust-ecosystem-curation`, `rust-high-signal-codebases`, `rust-parser-indexing-codebases`, `rust-security`, `rust-fuzz`, `rust-test-frontier`, `rust-api-compatibility`, `rust-mutation-testing`, `pyo3`, `google` | Stabilized features, project goals, Cargo/Clippy, benchmarks/profilers, scanners, parsers, syntax trees, search indexes, parser/fuzz patterns, RustSec, test orchestration, API compatibility, mutation testing, PyO3/maturin boundary changes, and crates worth local harness evaluation. |
| Future languages | `openai`, `anthropic`, plus a reviewed language-specific source before use | New proof tools, compiler/linter/test contracts, and harness ideas before any downstream recommendation. |

Concrete URLs belong in the trusted source registry or research-intake records.
The doc stays as the map; the registry is the card catalog.

## Sites To Check

Use these as starting points for pointer-only intake. Do not copy articles,
code, examples, benchmarks, or generated corpora into DAD mail.

| Topic | Starting URLs | Intake Rule |
| --- | --- | --- |
| Rust official direction | `https://blog.rust-lang.org/`, `https://blog.rust-lang.org/inside-rust/`, `https://rust-lang.github.io/rust-project-goals/`, `https://github.com/rust-lang/rfcs`, `https://doc.rust-lang.org/reference/`, `https://doc.rust-lang.org/unstable-book/`, `https://rust-lang.github.io/api-guidelines/` | Capture stabilized features, project goals, RFCs, reference changes, API design guidance, and toolchain shifts as candidates. Do not treat drafts, nightly-only features, or unstable-book entries as adopted rules. |
| Rust compiler and tooling practice | `https://rustc-dev-guide.rust-lang.org/`, `https://github.com/rust-lang/rust-analyzer`, `https://github.com/rust-lang/rust-clippy`, `https://github.com/rust-lang/miri`, `https://doc.rust-lang.org/cargo/` | Watch compiler diagnostics, source-analysis, lint, interpreter, and Cargo workflows that could become deterministic DAD checks or AI-legibility patterns. |
| Rust implementation practice | `https://this-week-in-rust.org/`, `https://nnethercote.github.io/perf-book/`, `https://tokio.rs/blog`, `https://blessed.rs/`, `https://lib.rs/`, `https://docs.rs/` | Route crates and techniques to harness research first, especially scanners, parsers, chunkers, hashing, async boundaries, and CLI tooling. |
| Rust parser/search/indexing codebases | `https://github.com/tree-sitter/tree-sitter`, `https://github.com/quickwit-oss/tantivy`, `https://github.com/serde-rs/json`, `https://github.com/rust-lang/rust-analyzer` | Study pointer-only patterns for syntax trees, offsets, search indexes, JSON boundaries, and diagnostics. Convert observations into tiny DAD harness cases before guidance changes. |
| Rust safety/testing | `https://rustsec.org/`, `https://rust-fuzz.github.io/book/`, `https://nexte.st/`, `https://doc.rust-lang.org/clippy/` | Turn security, fuzzing, Clippy, and test-runner ideas into validation plans before changing defaults. |
| Rust API and mutation proof | `https://github.com/obi1kenobi/cargo-semver-checks`, `https://mutants.rs/`, `https://github.com/sourcefrog/cargo-mutants` | Treat API compatibility and mutation testing as candidate harness evidence for shared Rust tools; review cost, false positives, license, and local fit before adoption. |
| Rust benchmarking/profiling | `https://bheisler.github.io/criterion.rs/book/`, `https://github.com/flamegraph-rs/flamegraph`, `https://github.com/rust-lang/rustc-perf` | Use benchmark and profiler sources to design same-workload local measurements. Do not promote microbenchmark wins as repo-level savings without parity and wall-clock evidence. |
| Python official direction | `https://docs.python.org/3/whatsnew/`, `https://peps.python.org/`, `https://blog.python.org/`, `https://devguide.python.org/`, `https://typing.python.org/` | Capture version, typing, diagnostics, packaging, and stdlib changes with target Python version and checker/tool support. |
| Python tooling/testing | `https://docs.astral.sh/ruff/`, `https://docs.astral.sh/uv/`, `https://docs.astral.sh/ty/`, `https://docs.pytest.org/`, `https://hypothesis.readthedocs.io/`, `https://mypy.readthedocs.io/`, `https://microsoft.github.io/pyright/` | Route speed, lint, type, fixture, property, and test-selection ideas through local validation before broad guidance. Treat beta or fast-moving checker behavior as candidate-only until the target repo opts in and local evidence exists. |
| Python test-strength/profiling | `https://coverage.readthedocs.io/`, `https://github.com/boxed/mutmut`, `https://pyperf.readthedocs.io/`, `https://github.com/benfred/py-spy`, `https://github.com/plasma-umass/scalene` | Use coverage, mutation, and profiling sources to expose false-green tests and noisy speed claims. Keep raw reports, private paths, traces, and generated inputs local unless sanitized and approved. |
| Python schema/CLI/interface codebases | `https://docs.pydantic.dev/`, `https://typer.tiangolo.com/`, `https://rich.readthedocs.io/`, `https://textual.textualize.io/` | Study pointer-only patterns for validated boundaries, command UX, structured errors, and agent-readable output. Local dependency approval and tests are required before adoption. |
| Python runtime proof operations | `https://docs.python.org/3/library/ast.html`, `https://docs.python.org/3/library/inspect.html`, `https://docs.python.org/3/library/profile.html`, `https://docs.python.org/3/library/tracemalloc.html`, `https://docs.python.org/3/library/faulthandler.html` | Use structural and runtime introspection to prove what the repo does before changing design, performance, test, or Rust-migration guidance. |
| AI coding research | `https://developers.openai.com/codex/`, `https://docs.anthropic.com/en/docs/claude-code/overview`, `https://cursor.com/docs/rules`, `https://arxiv.org/` | Extract only agent-workflow or eval ideas that can become deterministic DAD checks or harness cases. |

## Frontier Refresh Loop

Reviewed source cadences live in `registry/trusted-source-registry.json`.

Weekly or monthly refreshes look for:

- newly stabilized language/tooling features;
- deprecations or version changes that should update existing guidance;
- high-leverage libraries or crates worth evaluating;
- AI-overlooked patterns that are uncommon in average examples but valuable in
  DAD contexts;
- new harness ideas that can test or falsify a claim.
- edge-frontier research that could change how agents read, write, validate, or
  run code, especially when it introduces a new deterministic check surface.

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
- at least one negative example, counterexample, or failure mode is named;
- security and source-boundary risks are screened;
- at least one postflight or eval outcome supports the recommendation;
- downstream repos receive pointers and local review steps, not copied assets.

## Premortem

Likely failure story: DAD sees a clever Rust crate or Python feature, writes it
into broad agent instructions, and future agents cargo-cult it into repos where
it adds complexity, hides bugs, or skips local tests. The prevention is boring
and important: pointer-only intake, explicit avoid-when limits, local validation,
and no promotion without reviewed evidence.
