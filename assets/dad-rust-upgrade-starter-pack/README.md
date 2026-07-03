# DAD Rust Upgrade Starter Pack

Generated: `2026-07-02T17:56:48.839505+00:00`

This is a drop-in planning and starter-implementation pack for upgrading **Digital Asset Directory** to use Rust in the right places first, while keeping Python as the orchestration layer.

## What this pack is

This pack contains:

- a DAD-first Rust scanner scaffold under `overlay/tools/dad_scan_core/`;
- repo-by-repo Rust readiness/status for the visible Lowell repo set;
- Rust-vs-Python harness guidance;
- long CI templates for Rust-heavy QA;
- agent, skill, and multi-agent task prompts;
- Rust learning resources and high-signal GitHub repo references;
- a dry-run overlay installer.

## What this pack is not

- It is not canonical DAD policy until copied into the DAD repo and reviewed.
- It does not rewrite DAD.
- It does not claim the Rust scaffold compiles yet. I generated it without a local Rust toolchain in this environment, so `cargo check` must be the first real verification step.
- It does not move governance, legal judgment, theology, budget generation, or review authority into Rust.

## Drop-in path

Recommended local placement inside the DAD repo:

```text
assets/dad-rust-upgrade-starter-pack/
```

Then preview the overlay:

```bash
python assets/dad-rust-upgrade-starter-pack/scripts/apply_overlay.py --repo-root . --dry-run
```

Apply only after review:

```bash
python assets/dad-rust-upgrade-starter-pack/scripts/apply_overlay.py --repo-root . --apply
```

## First Rust upgrade sequence for DAD

1. Copy `overlay/tools/dad_scan_core/` into `tools/dad_scan_core/`.
2. Run `cargo check --manifest-path tools/dad_scan_core/Cargo.toml`.
3. Fix compile errors before expanding features.
4. Run `cargo test --manifest-path tools/dad_scan_core/Cargo.toml`.
5. Run the scanner on `examples/` or a tiny fixture, not your whole drive.
6. Add `templates/github/workflows/rust-ci-pr.yml` as `.github/workflows/rust-ci-pr.yml`.
7. Add `templates/github/workflows/rust-ci-long.yml` as `.github/workflows/rust-ci-long.yml` only after PR CI is stable.
8. Keep Python as the DAD CLI and orchestrator until the Rust observation contract is stable.

## Read order

```text
docs/00_EXECUTIVE_DECISION.md
docs/01_REPO_RUST_ADOPTION_MATRIX.md
docs/02_DAD_FIRST_RUST_UPGRADE_PLAN.md
docs/03_RUST_ADOPTION_PLAYBOOK.md
docs/04_RUST_VS_PYTHON_HARNESSES.md
docs/05_LONG_RUST_CI_QA_PLAN.md
docs/06_AGENT_AND_SKILL_SYSTEM.md
docs/07_GITHUB_RUST_REPO_SEARCH_GUIDE.md
docs/08_RUST_LEARNING_AND_CRATE_RESOURCES.md
docs/09_MODEL_ROUTING_FOR_RUST.md
```

## Main decision

Use Rust for deterministic leaf tooling:

```text
scan -> hash -> parse -> validate -> emit JSON/JSONL -> Python composes
```

Do not use Rust as the first place for:

```text
governance meaning, legal judgment, theological authority, human review, model orchestration, dashboard/UI iteration
```
