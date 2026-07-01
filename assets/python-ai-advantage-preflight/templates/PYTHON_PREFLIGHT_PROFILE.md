# Python Preflight Profile

Use this profile when a task touches Python code.

## Route

`python_implementation` or `python_refactor`

## Read first

1. Repo `AGENTS.md`
2. Repo AI front door / work-start file
3. DAD Python AI Advantage asset
4. Existing tests
5. The public entry-point file

## Preflight questions

- What is the public API?
- What must remain private?
- Which inputs are raw external data?
- Which internal values should become dataclasses?
- Which external dicts need `TypedDict`?
- Which strings should become `Enum`, `StrEnum`, `Literal`, or `NewType`?
- Which side effects can be pushed to adapters?
- Which existing behavior needs characterization tests before refactor?
- Which Python version is supported?

## Action rule

Prefer the smallest feature that clarifies a boundary, data shape, resource lifetime, state vocabulary, or test seam.
