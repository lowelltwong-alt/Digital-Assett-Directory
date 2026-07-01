# AGENTS.md — AI Engineering Preflight

## Core working agreement

Before coding, inspect the relevant files and identify:

1. the public entry point being changed;
2. internal helpers that should stay private;
3. inputs, outputs, and side effects;
4. current tests and missing tests;
5. the verification command or manual reproduction step.

Use modular encapsulation by default. Public functions, class methods, module exports, and public API items define the external interface. Internal helpers are implementation details. Other code should enter through the public API and receive controlled outputs instead of reaching into internal logic.

## Prompt contract

Every non-trivial task should be framed with:

- **Goal** — what to build or change.
- **Context** — files, folders, docs, examples, errors, or logs that matter.
- **Constraints** — architecture, safety, naming, test, dependency, and compatibility rules.
- **Done when** — tests, lint, typecheck, behavior, or reproduction criteria that prove completion.

## Preflight checklist

- Read before editing.
- Prefer the existing project pattern over a new pattern.
- Keep public APIs small and named by business purpose.
- Keep internal helpers small and named by implementation purpose.
- Keep side effects at the edges: filesystem, database, network, subprocesses, environment, randomness, clock/time.
- Prefer pure functions for business rules and calculations.
- Prefer typed inputs and outputs.
- Avoid global mutable state.
- Avoid hidden import-time or module-load side effects.
- Do not mix broad refactoring with feature changes unless explicitly asked.
- Use small, reviewable diffs.
- Do not weaken tests to make them pass.
- Do not introduce dependencies without explaining why.

## Long-file protocol

When working in a long script or oversized module:

1. Produce a map first: entry points, helpers, data structures, side effects, external dependencies, tests.
2. Add characterization tests before risky refactors when behavior already exists.
3. Preserve behavior unless the task explicitly requests a behavior change.
4. Extract constants/config first, then data types, then pure logic, then adapters, then orchestration.
5. Keep the top-level entry point thin.
6. Run checks after each meaningful extraction.

## Verification before final response

Before reporting completion, include:

- files changed;
- behavior changed;
- commands run and results;
- commands not run and why;
- assumptions;
- remaining risks.

Do not claim completion if verification failed or was not run.
