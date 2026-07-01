# GitHub Copilot Instructions — AI Engineering Preflight

Use the repository's `AGENTS.md` and `docs/ai-preflight/` files as the source of truth for coding-agent behavior.

## Default workflow

1. Understand the task goal, context, constraints, and done-when criteria.
2. Inspect relevant files before editing.
3. Identify public entry points, private/internal helpers, and side effects.
4. Keep changes small and reviewable.
5. Run relevant checks before claiming completion.

## Engineering style

Use modular encapsulation: public APIs are for callers; internal helpers are implementation details. Keep business logic testable and side effects explicit.
