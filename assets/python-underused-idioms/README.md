# Python Underused Idioms (AI Coding Card)

Offering: `dad:offering:python-underused-idioms` — machine-readable card in [idioms.json](idioms.json).

## Why this asset exists

AI coding agents write the Python they saw most often in training data. Constructs that are
rare on public GitHub — because they are newer than most training code, or historically
under-taught — get skipped even where they are the best tool. This card curates stdlib-only,
stable constructs judged under-represented relative to their value for **writing**,
**reading**, and **researching** code, so agents deliberately consider them.

Under-representation claims are heuristic judgments, not measured GitHub frequencies.

## How agents should use it

1. During preflight, when the task involves Python coding, refactoring, review, debugging,
   or performance work, read the groups relevant to the task:
   - `syntax_and_operators`, `control_flow_and_matching` — writing and refactoring
   - `stdlib_data_tools` — data shaping, grouping, ranking, dependency ordering
   - `contracts_and_typing` — module boundaries, ids, closed vocabularies
   - `code_research_toolkit` — investigating unfamiliar code, hangs, leaks, hot spots
2. Respect `min_python` against the target repo's floor and every `avoid_when` condition.
   Several entries (for/else, `__init_subclass__`, groupby) are included mainly so agents
   *read* them correctly; their avoid_when notes say when NOT to write them.
3. Cite idiom ids (e.g. `py-idiom:zip-strict`) in reviews, lessons, and postflights so
   adoption becomes traceable through the usage ledger and lesson graph.
4. Never rewrite working code solely to use an idiom. An idiom needs a task-level reason:
   a bug class prevented, a contract made checkable, or duplication removed.

## Frontier refresh

Refresh candidates come from `registry/trusted-source-registry.json` entries for
`python-core`, `python-packaging`, `python-typing`, `pytest-dev`, `hypothesis`,
`python-type-checkers`, `astral`, and `pyo3`. Treat them as research pointers
only. New Python guidance needs screening, target-version review, checker or
tool support notes when relevant, and a small regression or example before it
changes this card.

## Boundary

Installed candidate guidance for local reuse. Local repo style authority wins on conflict.
