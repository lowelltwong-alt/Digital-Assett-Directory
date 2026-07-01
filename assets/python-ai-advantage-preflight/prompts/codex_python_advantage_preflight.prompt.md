# Codex prompt: Python AI Advantage Preflight

You are working on Python code.

Before editing, inspect the relevant files and produce a short preflight:

1. Public entry point.
2. Private/internal helpers.
3. Input/output data shapes.
4. Side effects.
5. Current tests and missing tests.
6. Minimum supported Python version.
7. Proposed use of high-leverage Python features, if helpful.

Use modular encapsulation:

- Public functions, classes, methods, and module exports define the external interface.
- `_private` helpers are implementation details.
- Use `__all__` where a module/package has an intended public API.
- Do not import underscore-prefixed helpers from outside their module/package.

Prefer these Python patterns when they improve clarity:

- `@dataclass(frozen=True, slots=True, kw_only=True)` for value/result/config objects.
- `NewType` or wrappers for IDs and refs.
- `Protocol` for dependency boundaries.
- `TypedDict` for raw JSON/API/config dicts.
- `Enum`, `StrEnum`, or `Literal` for closed states.
- `match` only for structured closed variants.
- `pathlib.Path` for filesystem paths.
- `contextlib` for resource lifetimes.
- `raise ... from exc` for causal errors.
- `secrets` for security tokens.

Avoid average-code defaults:

- no giant all-purpose function;
- no loose dicts across layers;
- no magic-string state machines;
- no global mutable state for request/session context;
- no swallowed exceptions;
- no `eval`/`exec` for untrusted input;
- no `random` for secrets.

After editing, run relevant tests/type/lint commands and report exact results. Do not claim done unless verification passed.
