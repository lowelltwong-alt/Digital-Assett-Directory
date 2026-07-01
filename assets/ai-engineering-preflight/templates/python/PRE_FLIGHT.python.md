# Python Preflight Checklist

## Before editing

- [ ] Read the target file and imports.
- [ ] Identify the public function, class, method, CLI command, or endpoint being changed.
- [ ] Identify underscore-prefixed helpers that should remain internal.
- [ ] Identify global variables and mutable module state.
- [ ] Identify data flow: inputs, transformations, outputs.
- [ ] Identify side effects: files, network, database, environment, subprocesses, time, randomness.
- [ ] Identify existing tests and fixtures.
- [ ] Identify likely verification commands.

## While coding

- [ ] Preserve public signatures unless an API change is requested.
- [ ] Keep business logic pure where possible.
- [ ] Move I/O to edge adapters.
- [ ] Add type hints to new public functions and complex helpers.
- [ ] Replace loose dicts/tuples with dataclasses when the shape is stable.
- [ ] Use `_helper_name` for internal helpers.
- [ ] Use `__all__` for intentional public module exports.
- [ ] Avoid hidden work during import.
- [ ] Keep `main()` thin.

## Before final answer

- [ ] Run tests.
- [ ] Run lint.
- [ ] Run format check.
- [ ] Run typecheck when configured.
- [ ] Inspect diff.
- [ ] Report changed files, commands run, commands not run, assumptions, and risks.
