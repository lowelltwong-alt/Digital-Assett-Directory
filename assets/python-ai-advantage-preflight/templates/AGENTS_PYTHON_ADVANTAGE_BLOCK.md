<!-- BEGIN PYTHON_AI_ADVANTAGE_PREFLIGHT -->
## Python AI Advantage Preflight

Before non-trivial Python work, use the DAD Python AI Advantage Preflight asset.

Default hub-relative path:

`assets/python-ai-advantage-preflight/`

### Required Python preflight

Before editing Python code, identify:

1. Public entry point.
2. Private/internal helpers.
3. Input and output data shapes.
4. Side effects: filesystem, network, database, subprocess, environment, clock, randomness, logging.
5. Current tests and missing characterization tests.
6. Validation commands.
7. Minimum supported Python version.

### Preferred patterns

Use these when they improve clarity and verification:

- `__all__` for intentional module exports.
- `_private` helpers for implementation details.
- `@dataclass(frozen=True, slots=True, kw_only=True)` for value/config/result objects.
- `NewType` or small wrappers for IDs and refs.
- `Protocol` for side-effect dependency boundaries.
- `TypedDict` for JSON/API/config boundary dicts.
- `StrEnum`, `Enum`, or `Literal` for closed states.
- `match` for structured closed variants, not for simple conditionals.
- `contextlib.ExitStack` for dynamic resource cleanup.
- `pathlib.Path` for filesystem boundaries.
- `raise ... from exc` for causal error wrapping.
- `secrets` for security-sensitive randomness.
- `importlib.resources` for package-owned templates/schemas.
- `contextvars` for request/session context in async code.

### Suppress average-GitHub habits

Do not default to:

- giant scripts;
- loose dicts everywhere;
- global mutable state;
- magic strings for closed states;
- `random` for tokens;
- swallowed exceptions;
- hand-rolled cleanup instead of context managers;
- public imports of underscore-prefixed internals;
- `eval` or `exec` unless explicitly justified and reviewed.

### Verification

Before reporting completion, state:

- files changed;
- commands run;
- tests run and results;
- tests not run;
- confirmed facts;
- inferred facts;
- assumptions;
- unknowns;
- remaining risks.
<!-- END PYTHON_AI_ADVANTAGE_PREFLIGHT -->
