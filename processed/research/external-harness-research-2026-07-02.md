# External Harness & Asset Research — 2026-07-02

Candidate-only external research with provenance. Nothing here is promoted, installed, or
shared downstream without license, security, compatibility, and source-visibility review.
Machine-readable version: [external-harness-research-2026-07-02.json](external-harness-research-2026-07-02.json).

## Headline findings

1. **The harness is worth ~a model generation.** The same model scored 57.5% vs 64.7% on
   Terminal-Bench depending only on which harness ran it. DAD's core bet is quantified.
2. **Both frontier labs now publish harness engineering as a discipline** (Anthropic
   "Effective harnesses for long-running agents"; OpenAI "Harness engineering" + Codex App
   Server posts). Fowler formalized the vocabulary: feedforward guides vs feedback sensors;
   computational vs inferential checks; "harnessability" as an environment property.
3. **AGENTS.md became a Linux Foundation standard** (Google, OpenAI, Sourcegraph, Cursor,
   Factory) — DAD's front-door design is now the industry convention; align section names.
4. **Biggest gap in DAD's harness families: test quality.** Mutation testing
   (cargo-mutants, Trail of Bits mewt/muton skills) and property-based testing are the 2026
   consensus answer to AI false-green code — no current DAD family covers this.
5. **Trail of Bits publishes professional security skills** (code-graph audit, mutation
   campaigns, differential review) — highest-signal external skill source found; requires
   quarantine review before any pointer checkout.
6. **Rust payoff math changed:** PyO3 + free-threaded Python 3.14 means Rust hot paths can
   use all cores without multiprocessing. Exemplar path stays: profile first → PyO3/maturin
   extension → keep Python API (Ruff/uv/Polars/Pydantic-core shape). Canonical learning
   path: Google's Comprehensive Rust (+ Idiomatic Rust and Unsafe Rust modules). Quality
   stack: nextest, semver-checks (merging into cargo), miri, proptest, criterion, insta,
   cargo-mutants.

## Top promotion candidates (human review required)

1. New `test_quality` harness family (mutation + property + approved fixtures).
2. Harness-registry taxonomy fields from Fowler (guide/sensor, computational/inferential, lifecycle stage).
3. Session-harness patterns from the Anthropic post (init script, progress file, JSON
   feature list, session-start sequence) into the agent_instruction harness.
4. rust-buildout-guide v0.2.0 upgrade (free-threading, call-boundary gotcha, learning resources, cargo stack).
5. Trail of Bits skill pointers — only after security/license/prompt-injection review.

## Explicitly not recommended

- Installing third-party actions/skill packs without per-item review.
- Importing benchmark task data into DAD repos.
- Reading leaderboard scores as model truth (harness-confounded).
