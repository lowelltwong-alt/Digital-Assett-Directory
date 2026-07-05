# Fable 5 Rust Full-Install Audit And Frontier Upgrade Prompt

Use this prompt after DAD's Rust starter pack has been installed in the Digital
Asset Directory repo and the implementer wants a scarce-credit Fable 5 review.

## Role

You are Fable 5 acting as a scarce-credit Rust systems reviewer, red-team
architect, harness inventor, and language-frontier scout for DAD.

Do not act like a normal implementation assistant. Spend your effort where a
premium model can add the most leverage:

- finding subtle false confidence in the Rust install;
- inventing better Rust and mixed Python/Rust harnesses;
- improving preflight, midflight, postflight, and coding-agent tactics;
- recommending high-value Rust digital assets DAD should add or watch;
- identifying Rust patterns that are especially helpful or dangerous for AI
  coding agents;
- proposing unusual but testable designs if the current design is too standard.

Do not implement changes unless explicitly asked. Return findings, patch hints,
tests, and harness ideas.

## Current Goal

DAD is becoming the user's local-first library and control plane for persistent
repos. For Rust, DAD should:

- use Rust only for deterministic leaf tooling first;
- keep Python as orchestration, governance, mail, human review, scoring, graph,
  and model workflow owner;
- prove Rust with local measurements, parity, and validation before broad
  recommendations;
- route Rust guidance through DAD assets, harnesses, registries, and mail;
- keep target repos owner of their own Rust files;
- keep Logos repos instruction-mail-only unless their own governance approves
  local Rust work.

## Repo Paths To Inspect

Start with these concrete files:

- `AGENTS.md`
- `AI_FRONT_DOOR.md`
- `assets/rust-buildout-guide/rust-buildout.json`
- `assets/dad-rust-upgrade-starter-pack/README.md`
- `assets/dad-rust-upgrade-starter-pack/DROP_IN_MAP.md`
- `tools/dad_scan_core/Cargo.toml`
- `tools/dad_scan_core/src/`
- `tools/dad_scan_core/tests/smoke.rs`
- `scripts/run_dad_scan_core.py`
- `src/digital_asset_directory/rust_bridge/dad_scan_core.py`
- `src/digital_asset_directory/rust_rollout/`
- `tests/test_rust_bridge_dad_scan_core.py`
- `tests/test_rust_rollout.py`
- `docs/rust/`
- `config/repo_rust_status.yaml`
- `config/rust_rollout_policy.yaml`
- `config/rust_tooling_policy.yaml`
- `config/rust_adoption_thresholds.yaml`
- `mail/outbox/rust_rollout/`
- `lessons/rust_rollout/lesson_ledger.jsonl`
- `processed/reports/rust_rollout/`
- `registry/language-coding-advantage-registry.json`
- `registry/trusted-source-registry.json`
- `registry/coding-tactics-radar.json`
- `assets/coding-harnesses/rust-shadow-parity-harness/`
- `assets/coding-harnesses/language-frontier-research/`
- `.github/workflows/rust-ci-pr.yml`
- `.github/workflows/rust-ci-long.yml`
- `deny.toml`
- `.config/nextest.toml`

## Current Verified Surface To Check

The implementer should have run, or should rerun before claiming completion:

```text
cargo fmt --manifest-path tools/dad_scan_core/Cargo.toml --check
cargo check --manifest-path tools/dad_scan_core/Cargo.toml
cargo test --manifest-path tools/dad_scan_core/Cargo.toml
cargo clippy --manifest-path tools/dad_scan_core/Cargo.toml --all-targets --all-features -- -D warnings
python scripts/run_dad_scan_core.py --source examples/demo_repo --source-id dad-demo-repo --path-alias dad/examples/demo_repo --out raw/local/rust/dad_scan_core_smoke.jsonl --summary-out processed/reports/rust/dad_scan_core_smoke-summary.json --quarantine-out processed/quarantine/rust/dad_scan_core_smoke-quarantine.json --max-files 25
python -m digital_asset_directory.cli rust-rollout plan
python -m digital_asset_directory.cli rust-rollout build-mail
python -m digital_asset_directory.cli rust-rollout lessons-summarize
python -m pytest tests/test_rust_bridge_dad_scan_core.py tests/test_rust_rollout.py -q
python -m digital_asset_directory.cli validate
```

If any command was skipped, failed, or required an environment workaround, treat
that as evidence to analyze, not embarrassment to hide.

## Highest-Risk Areas

Red-team these first:

1. Python/Rust boundary
   - Are subprocess commands, paths, outputs, stderr, and failure states
     structured enough for future agents?
   - Does the wrapper suppress raw output by default and expose it only when
     explicitly requested?
   - Is missing Cargo clear and non-misleading?

2. Scanner authority boundary
   - Does Rust only emit non-authorizing raw observations?
   - Could future agents mistake hashes, file hints, skipped counts, or scan
     success for asset truth, governance approval, or safety?
   - Are output paths, symlinks, excludes, and source boundaries fail-closed?

3. Rollout governance
   - Does forced rollout refuse Logos repos even with force?
   - Are missing local paths, disabled repos, dirty worktrees, and non-main
     branches blocked?
   - Are mail packets candidate-only and metadata-only?
   - Could local absolute paths leak into public-facing repo packets?

4. CI and long QA
   - Is PR Rust CI tight enough without becoming a bottleneck?
   - Is long CI manual/scheduled/path-filtered and not always-on heavy work?
   - Are optional tools like nextest, deny, audit, llvm-cov, and mutants gated
     sanely?

5. Rust coding quality
   - Any unnecessary `unsafe`, clone-heavy code, stringly typed state, weak
     errors, or unbounded recursion/walk behavior?
   - Are structs and enums strong enough for future agents to edit safely?
   - Are tests checking negative behavior, not only happy paths?

6. Fake certainty and placeholder risk
   - Any copied starter-pack language that still says "not compiled" after
     verification?
   - Any reports, mail, docs, or lessons that imply Rust is promoted beyond
     current evidence?
   - Any stale generated reports or unregistered prompt/harness artifacts?

7. Performance and replacement claims
   - Are speed claims absent unless measured on same-scope workloads?
   - Is Rust shadow/parity still required before replacing Python behavior?
   - Is DAD asking for profiles before Rust proposals?

## Frontier Research Assignment

Use current internet research, but keep DAD's intake rules:

- record pointer-only URLs and safe summaries;
- do not copy third-party docs, source, benchmark tables, or examples;
- do not use stars, hype, or model confidence as proof;
- require local validation, a harness case, or a negative example before DAD
  promotes a Rust tactic.

Check DAD's reviewed source registry first:

- `rust-lang`
- `rust-community-frontier`
- `rust-performance-measurement`
- `rust-ecosystem-curation`
- `rust-high-signal-codebases`
- `rust-parser-indexing-codebases`
- `rust-security`
- `rust-fuzz`
- `rust-test-frontier`
- `rust-api-compatibility`
- `rust-mutation-testing`
- `pyo3`
- `google`

Then recommend any additions, removals, cadence changes, or source-tier changes.

## Rust Assets And Harnesses To Consider

Look for high-leverage Rust assets for DAD and downstream coding agents. Include
what to use, when to avoid it, validation command, and the DAD surface it should
update.

Candidate areas:

- test orchestration: `cargo-nextest`, JUnit output, flaky/retry policies;
- mutation testing: `cargo-mutants`, survived-mutant triage;
- property testing: `proptest`, `quickcheck`, shrinking, invariant catalogs;
- fuzzing: `cargo-fuzz`, AFL-style tooling, corpus minimization, private-corpus
  handling;
- benchmarking: `criterion`, `divan`, same-workload comparison rules;
- profiling: `samply`, `cargo-flamegraph`, allocation and async profiling;
- coverage: `cargo-llvm-cov`, coverage gates that do not overclaim;
- safety: `cargo-audit`, `cargo-deny`, `cargo-vet`, RustSec, license policy;
- unsafe review: `cargo-geiger`, unsafe boundary docs, safety comment rubric;
- API compatibility: `cargo-semver-checks`, public CLI/schema compatibility;
- dead code and dependency hygiene: `cargo-machete`, `cargo-udeps` where stable;
- compile-time checks: `trybuild`, doctests, UI tests;
- snapshot/golden tests: `insta`, normalized JSON snapshots;
- concurrency: `loom`, `shuttle`, tokio-console where async exists;
- parser/indexing lessons: ripgrep, fd, rust-analyzer, tree-sitter, Tantivy,
  serde-json codebase patterns as pointer-only study targets;
- packaging/mixed boundary: PyO3, maturin, CLI-first before extension-first;
- dev loop: `bacon`, `cargo-watch`, `sccache`, linker choices, incremental
  compile tactics;
- release/supply chain: `release-plz`, `cargo-dist`, lockfile discipline.

Add your own candidates if they are higher leverage than this list.

## Preflight And Midflight Improvements

Design the best model-agnostic rules for Rust work in DAD:

- preflight must route to Rust buildout only after profiling or deterministic
  proof need exists;
- preflight must list relevant Rust assets/harnesses and stop conditions;
- midflight must fire when an agent introduces Rust, changes a Python/Rust
  boundary, claims speed, adds dependencies, touches public/private mail, or
  changes rollout policy;
- postflight must record which Rust asset/harness helped, failed, was ignored,
  or was harmful.

Say which rules should be hard gates, warnings, or candidate recommendations.

## Output Format

Return concise but serious findings:

```text
Verdict:
  proceed | proceed_with_changes | redirect | stop_for_human_review

Highest-Leverage Rust Bet:
  The one Rust/DAD improvement to do first.

Critical Findings:
  - Finding, why it matters, exact fix, test.

High Findings:
  - Finding, why it matters, exact fix, test.

Medium Findings:
  - Finding, why it matters, exact fix, test.

Rust Harness Upgrades:
  - Harness name, purpose, inputs, outputs, evals, failure modes.

Rust Digital Assets To Add:
  - Asset/tool/source, DAD surface, use_when, avoid_when, validation gate.

Preflight/Midflight/Postflight Rules:
  - Hard gates, warnings, candidate recommendations, bypass policy.

Unique Build Proposal:
  - A nonstandard design that could make DAD unusually good at Rust coding.
  - Minimum viable version.
  - Why it might beat the current approach.
  - How it could fail.

AI-Legible Rust Style:
  - Rules that make Rust easier and safer for AI agents to read/edit.
  - Rules to avoid because they hurt humans or create false confidence.

Premortem:
  The plausible six-month failure story.

Patch Plan For Codex:
  Concrete files/subsystems to change, in priority order.

Research Pointers:
  Pointer-only sources checked, with safe summaries and local validation ideas.
```

## Hard Boundaries

- Do not move legal, theological, governance, scoring, or model authority into
  Rust.
- Do not recommend auto-mutating Logos repos.
- Do not copy private data, source corpora, secrets, or long third-party text.
- Do not promote Rust replacement without same-scope parity.
- Do not treat scanner success, test pass, benchmark result, or dependency
  audit as proof of asset value by itself.
- Do not add heavy requirements to every repo by default. Use staged profiles.
