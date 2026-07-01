# Prompt: Refactor a long Python script using the preflight asset

Goal: Refactor the specified long Python script using the repository's AI engineering preflight rules.

Context:
- Read `AGENTS.md`.
- Read `docs/ai-preflight/PYTHON_PREFLIGHT.md`.
- Read `docs/ai-preflight/LONG_SCRIPT_REFACTOR.python.md`.
- Target file: `[path/to/script.py]`.

Constraints:
- First map the file. Do not edit in the first response.
- Preserve behavior unless I explicitly approve a behavior change.
- Do not wrap everything in one giant class.
- Extract pure logic before I/O adapters.
- Keep one public entry point and underscore-prefixed internals.
- Add characterization tests before risky refactors where possible.

Done when:
- The public entry point is clear.
- Private helpers are not called externally.
- Side effects are isolated at the edge.
- Tests/checks run or not-run reasons are reported.
- Diff is small enough to review.
