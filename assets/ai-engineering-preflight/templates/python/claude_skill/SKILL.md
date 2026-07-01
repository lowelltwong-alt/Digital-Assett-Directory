---
name: ai-engineering-preflight-python
description: Use before modifying Python code, especially long scripts, modules with private helpers, public APIs, tests, or refactors.
---

# Python AI Engineering Preflight Skill

## Procedure

1. Read `AGENTS.md` and `docs/ai-preflight/PYTHON_PREFLIGHT.md`.
2. Map public entry points, underscore-prefixed internals, side effects, data objects, and tests.
3. Plan before multi-file or long-script changes.
4. Preserve public behavior unless asked.
5. Keep private helpers private.
6. Prefer pure functions for business logic and side-effect adapters at the edge.
7. Run the relevant checks and report exact results.

## Output

Report:

- public API touched;
- internals touched;
- files changed;
- tests/checks run;
- checks not run and why;
- risks.
