# Prompt: Deploy preflight asset to a Rust repo

Goal: Deploy the central AI engineering preflight asset to this Rust repository.

Context:
- The central asset is at: `/path/to/YOUR_ASSET_REPO/assets/ai-engineering-preflight/`.
- This repo should receive Rust-specific AI coding-agent instructions.

Constraints:
- Read the asset `README.md` and `DEPLOYMENT_GUIDE.md` before changing files.
- Dry-run first.
- Use `--profile rust`.
- Do not overwrite existing instructions without preserving them or using managed block replacement.
- Do not refactor code yet. This task only installs preflight/instruction files.

Done when:
- `AGENTS.md` includes the managed preflight block.
- `docs/ai-preflight/RUST_PREFLIGHT.md` exists.
- `.github/copilot-instructions.md` includes the managed preflight block or candidate file is created.
- `.cursor/rules/ai-engineering-preflight.mdc` exists or candidate file is created.
- You report commands run, files changed, assumptions, and risks.
