# Python Long-Script Refactor Protocol

Use this when a Python file is large, procedural, globally mutable, or hard for an AI agent to reason about.

## Phase 1 — Map, do not edit

Return a map first:

```text
- public entry points
- internal helpers
- classes
- data structures
- global variables
- side effects
- external dependencies
- current tests
- missing tests
- proposed extraction plan
```

## Phase 2 — Lock existing behavior

If the script already works, add characterization tests before refactoring. Capture current outputs, error behavior, important edge cases, and CLI behavior where practical.

## Phase 3 — Extract safely

Extract in small commits or checkpoints:

1. constants/config;
2. dataclasses/types;
3. pure parsing;
4. pure validation;
5. pure calculation;
6. formatting/rendering;
7. I/O adapters;
8. orchestration class/function;
9. thin `main()`.

After each extraction, run the smallest relevant test set.

## Phase 4 — Preserve the public API

Do not change CLI flags, public function names, return shapes, output file names, or exception behavior unless asked.

## Phase 5 — Verify

Run available checks and report exact results.
