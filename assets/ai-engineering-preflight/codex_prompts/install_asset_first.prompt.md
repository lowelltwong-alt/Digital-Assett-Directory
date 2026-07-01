# Prompt: Install asset into central asset directory

You are working in my central asset repository.

Goal: Install the extracted `ai-engineering-preflight-asset` package into `assets/ai-engineering-preflight/`.

Context:
- The extracted package contains `asset.json`, `README.md`, `templates/`, `scripts/`, and `codex_prompts/`.
- Use the package's own `scripts/install_asset.py` if available.

Constraints:
- Dry-run first.
- Do not delete unrelated files.
- Preserve existing asset files unless the script reports that it is replacing files within the same asset directory.
- Show the exact commands before running them.

Done when:
- `assets/ai-engineering-preflight/asset.json` exists.
- `assets/ai-engineering-preflight/templates/python/AGENTS.python.md` exists.
- `assets/ai-engineering-preflight/templates/rust/AGENTS.rust.md` exists.
- You report files changed, commands run, checks not run, assumptions, and risks.
