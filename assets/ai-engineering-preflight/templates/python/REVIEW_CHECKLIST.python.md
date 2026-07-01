# Python AI Code Review Checklist

## Boundary review

- [ ] Is there a clear public entry point?
- [ ] Are underscore helpers kept internal?
- [ ] Did new external code avoid calling `_private` helpers?
- [ ] Is `__all__` used when the module exports a public API?

## Maintainability review

- [ ] Are names specific and business-relevant?
- [ ] Are type hints present on public APIs?
- [ ] Are dataclasses or typed models used instead of loose dicts where appropriate?
- [ ] Are side effects explicit and near the edge?
- [ ] Is global mutable state avoided?
- [ ] Does `main()` stay thin?

## Verification review

- [ ] Tests added or updated where behavior changed.
- [ ] `python -m pytest` run or not-run reason stated.
- [ ] `ruff check .` run or not-run reason stated.
- [ ] `ruff format --check .` run or not-run reason stated.
- [ ] `mypy .` run or not-run reason stated.
