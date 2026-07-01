# Deployment Guide

## 1. Install the asset into the central asset directory

Extract the zip, then run from the extracted package root:

```bash
python scripts/install_asset.py \
  --target /path/to/YOUR_ASSET_REPO/assets/ai-engineering-preflight \
  --apply
```

Dry-run first:

```bash
python scripts/install_asset.py \
  --target /path/to/YOUR_ASSET_REPO/assets/ai-engineering-preflight
```

The dry-run prints what would be copied without writing files.

## 2. Commit the asset directory in the central repo

```bash
cd /path/to/YOUR_ASSET_REPO
git status
git add assets/ai-engineering-preflight
git commit -m "Add AI engineering preflight asset"
```

## 3. Deploy to one Python repo

```bash
python /path/to/YOUR_ASSET_REPO/assets/ai-engineering-preflight/scripts/deploy_to_repo.py \
  --repo /path/to/python-repo \
  --profile python \
  --apply
```

This writes or updates:

```text
AGENTS.md
CLAUDE.md
.github/copilot-instructions.md
.github/instructions/ai-engineering-preflight.instructions.md
.cursor/rules/ai-engineering-preflight.mdc
.claude/skills/ai-engineering-preflight/SKILL.md
docs/ai-preflight/PYTHON_PREFLIGHT.md
docs/ai-preflight/LONG_SCRIPT_REFACTOR.python.md
docs/ai-preflight/REVIEW_CHECKLIST.python.md
docs/ai-preflight/ASSET_SOURCE.md
```

## 4. Deploy to one Rust repo

```bash
python /path/to/YOUR_ASSET_REPO/assets/ai-engineering-preflight/scripts/deploy_to_repo.py \
  --repo /path/to/rust-repo \
  --profile rust \
  --apply
```

This writes or updates:

```text
AGENTS.md
CLAUDE.md
.github/copilot-instructions.md
.github/instructions/ai-engineering-preflight.instructions.md
.cursor/rules/ai-engineering-preflight.mdc
.claude/skills/ai-engineering-preflight/SKILL.md
docs/ai-preflight/RUST_PREFLIGHT.md
docs/ai-preflight/LONG_MODULE_REFACTOR.rust.md
docs/ai-preflight/REVIEW_CHECKLIST.rust.md
docs/ai-preflight/ASSET_SOURCE.md
```

## 5. Deploy to many repos

Create a repo list:

```bash
cp configs/repos.example.txt /path/to/repos.txt
```

Edit it:

```text
# one repo path per line
/path/to/repo-one
/path/to/repo-two
/path/to/repo-three
```

Dry-run:

```bash
python /path/to/YOUR_ASSET_REPO/assets/ai-engineering-preflight/scripts/sync_to_many_repos.py \
  --repos-file /path/to/repos.txt \
  --profile auto
```

Apply:

```bash
python /path/to/YOUR_ASSET_REPO/assets/ai-engineering-preflight/scripts/sync_to_many_repos.py \
  --repos-file /path/to/repos.txt \
  --profile auto \
  --apply
```

## 6. Ask Codex to perform deployment

Use the prompts in `codex_prompts/`:

- `install_asset_first.prompt.md`
- `deploy_to_python_repo.prompt.md`
- `deploy_to_rust_repo.prompt.md`
- `rollout_to_many_repos.prompt.md`

## 7. Review before committing target repo changes

In each target repo:

```bash
git diff -- AGENTS.md CLAUDE.md .github .cursor .claude docs/ai-preflight
```

Then run repo checks if relevant.

Python examples:

```bash
python -m pytest
ruff check .
ruff format --check .
mypy .
```

Rust examples:

```bash
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --all
cargo test --doc
```

## Important limitation

These scripts copy instruction files. They do not automatically refactor existing code. After deployment, ask Codex to use the preflight docs before changing code.
