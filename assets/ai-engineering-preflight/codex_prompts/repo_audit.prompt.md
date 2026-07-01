# Prompt: Audit repo for AI preflight readiness

Goal: Audit this repository for AI coding-agent readiness using the preflight asset.

Context:
- Read `AGENTS.md` if present.
- Read `docs/ai-preflight/` if present.
- If absent, inspect project structure and recommend which profile to deploy: `python`, `rust`, `mixed`, or `common`.

Return:
- language/profile detection;
- existing agent instruction files;
- public entry points;
- long scripts/modules;
- missing tests/check commands;
- risks for AI-generated code;
- recommended deployment command from the central asset directory.

Do not edit files unless explicitly asked.
