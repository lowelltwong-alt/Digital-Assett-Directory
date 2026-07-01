# Python AI Engineering Preflight

## Python modular encapsulation rule

Use Python encapsulation and modular design: public functions or class methods define the external interface, while underscore-prefixed helpers are private implementation details. This creates a clean boundary where other code has one intended way to enter the module and receives a controlled output, instead of reaching into internal logic.

A leading underscore means **non-public by convention**, not security. Do not call `_helper()` methods or functions from external modules unless there is an explicit documented exception.

## Public API tactics

- Keep module-level public APIs small.
- Use `__all__` in modules that intentionally expose a public API.
- Prefer public methods named by business purpose: `bill_customer`, `import_customers`, `generate_report`.
- Keep helpers named by implementation purpose: `_parse_rows`, `_calculate_total`, `_write_output_file`.
- Do not expose internals just to make a test easier.
- Test public behavior by default. Test private helpers directly only when the helper contains complex isolated logic.

## Type and data tactics

- Use type hints on public functions and important helpers.
- Prefer dataclasses for structured data.
- Use `@dataclass(frozen=True)` for value objects that should not be mutated.
- Prefer `Enum`, `Literal`, or `NewType` for meaningful domain states and IDs.
- Avoid long parameter lists; introduce a typed data object.
- Avoid loose dictionaries for domain objects when fields are known.

## Long-script refactor tactics

For long scripts, do not wrap everything in one giant class. Extract in this order:

1. constants and config;
2. dataclasses/types;
3. pure parsing functions;
4. pure validation/calculation functions;
5. formatting functions;
6. filesystem/API/database adapters;
7. orchestration service or workflow;
8. thin `main()` entry point.

Keep import-time code minimal. Prefer:

```python
def main() -> int:
    ...
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

## Side-effect rules

Functions that read files, write files, call APIs, access environment variables, use subprocesses, randomness, or time must be named clearly and kept near the system edge.

Good:

```python
def _read_customer_csv(path: Path) -> list[str]: ...
def calculate_invoice_total(invoice: Invoice) -> Money: ...
```

Bad:

```python
def calculate_invoice_total(invoice):
    # secretly calls Stripe or writes a file
    ...
```

## Default checks

Run available checks. Prefer project-specific commands if they exist.

```bash
python -m pytest
ruff check .
ruff format --check .
mypy .
```

If a command is unavailable, report that it was not run and why.
