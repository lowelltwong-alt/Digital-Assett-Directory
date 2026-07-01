# AI Engineering Preflight Asset

Version: `0.1.0`

This package is a reusable digital asset for AI-assisted software engineering. It gives Codex, Claude Code, Cursor, GitHub Copilot, and similar coding agents a consistent preflight checklist and implementation style for Python and Rust repositories.

The core rule is **modular encapsulation**:

> Public functions, class methods, module exports, and Rust `pub` items define the external interface. Underscore-prefixed Python helpers, private Rust items, and internal modules are implementation details. Other code should enter through the public API and receive controlled outputs instead of reaching into internal logic.

## What this asset contains

- `templates/common/` — shared engineering and agent instructions.
- `templates/python/` — Python-specific preflight rules, long-script refactor protocol, review checklist, and Codex/Claude/Copilot/Cursor-ready text.
- `templates/rust/` — Rust-specific preflight rules, module-boundary guidance, API-design rules, and verification commands.
- `repo_templates/python_minimal/` — a small Python repo skeleton that demonstrates the style.
- `repo_templates/rust_minimal/` — a small Rust crate skeleton that demonstrates the style.
- `codex_prompts/` — prompts to ask Codex to install the asset, deploy it to one repo, roll it out to many repos, or refactor a long script/module.
- `scripts/` — safe deployment utilities. They default to dry-run and preserve existing files unless you explicitly apply changes.

## Install first into your asset directory

Recommended central location inside your asset repository:

```bash
assets/ai-engineering-preflight/
```

From the extracted package root:

```bash
python scripts/install_asset.py --target /path/to/YOUR_ASSET_REPO/assets/ai-engineering-preflight --apply
```

Then deploy from that central asset directory to your coding repos:

```bash
python /path/to/YOUR_ASSET_REPO/assets/ai-engineering-preflight/scripts/deploy_to_repo.py \
  --repo /path/to/target-python-repo \
  --profile python \
  --apply
```

For Rust:

```bash
python /path/to/YOUR_ASSET_REPO/assets/ai-engineering-preflight/scripts/deploy_to_repo.py \
  --repo /path/to/target-rust-repo \
  --profile rust \
  --apply
```

For automatic detection:

```bash
python /path/to/YOUR_ASSET_REPO/assets/ai-engineering-preflight/scripts/deploy_to_repo.py \
  --repo /path/to/target-repo \
  --profile auto \
  --apply
```

## Safety model

The deploy scripts:

- default to dry-run unless `--apply` is provided;
- create parent directories only when applying;
- use managed block markers when appending to existing Markdown files;
- avoid overwriting unrelated user content;
- write `.candidate` files for collision-prone generated files unless `--force` is provided;
- print every target path it would change.

## Files agents should read first

For a Python repo:

1. `AGENTS.md`
2. `docs/ai-preflight/PYTHON_PREFLIGHT.md`
3. `docs/ai-preflight/LONG_SCRIPT_REFACTOR.python.md`

For a Rust repo:

1. `AGENTS.md`
2. `docs/ai-preflight/RUST_PREFLIGHT.md`
3. `docs/ai-preflight/LONG_MODULE_REFACTOR.rust.md`

For multi-language repos, deploy with `--profile mixed`.
