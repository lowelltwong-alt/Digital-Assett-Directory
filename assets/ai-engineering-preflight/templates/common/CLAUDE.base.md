# CLAUDE.md — AI Engineering Preflight

Read `AGENTS.md` first when present. Follow the repository's AI engineering preflight rules.

Keep this file concise. Detailed language-specific procedures belong in `docs/ai-preflight/` or a skill under `.claude/skills/`.

## Required behavior

- Inspect relevant code before editing.
- Plan before multi-file or architectural changes.
- Preserve public API unless asked to change it.
- Keep implementation details private/internal.
- Use tests, type checks, lint, formatting checks, builds, or manual reproduction steps as verification.
- Report what changed, checks run, checks not run, assumptions, and remaining risks.

## Boundaries

Public entry points define how outside code should use a module. Private helpers exist to make implementation readable, not to create new external calling surfaces.

Do not call internal helpers from outside their module just because it is convenient.
