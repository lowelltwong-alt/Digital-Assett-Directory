# Python Coding Playbook

Status: candidate DAD operational guidance.

## Role

Python is DAD's default language for orchestration, governance, mail, review,
reporting, schemas, and human workflow. Use Python to make data shape, side
effects, fixtures, and validation commands visible to future agents.

## Before Coding

- Inspect the repo's Python version, `pyproject.toml`, configured tools, and
  existing test commands before recommending a checker or dependency.
- Identify raw JSON, JSONL, CLI, config, and report boundaries. Prefer named
  parsers, schemas, `TypedDict`, dataclasses, or small boundary functions over
  spreading nested dictionaries.
- If tests are slow, collect node IDs and durations before trimming. Selected
  tests are only evidence when the selected scope is named.
- If performance is mentioned, profile first. Record command, scope, duration,
  top symbols, and what the profile proved. Do not propose Rust from intuition.
- For parsers, normalizers, IDs, dedupe, sorting, hashing, or serializers,
  consider a small invariant, property test, malformed-input test, or static
  checker contract.

## AI-Overlooked Operations

- Use `ast`, `symtable`, `inspect`, and `importlib.metadata` when text search
  is too blunt for definitions, decorators, imports, call signatures, or entry
  points.
- Use `cProfile`, `pstats`, `tracemalloc`, and `faulthandler` for speed,
  allocation, hang, and leak questions.
- Use pytest collection, markers, durations, and fixture inspection before
  changing test orchestration.
- Use coverage, mutation-test, or profiling scouts as candidate evidence when a
  passing suite may be falsely green. Do not turn these into repo gates without
  local approval.
- Cite Python idiom IDs from `assets/python-underused-idioms/idioms.json` when
  a review or lesson relies on an idiom.

## Harness Routes

- Slow test battery: `dad:harness:python-test-performance-orchestration`.
- Possible Rust replacement: profile, Python-first fix, then
  `dad:harness:rust-shadow-parity`.
- New Python technique or tool: `dad:harness:language-frontier-research`.
- Agent instruction or review quality issue:
  `dad:harness:agent-instruction-code-review-red-team`.

## Frontier Watch

Use `asset-dir research frontier-watch --language python` for the current
source list. Watch official Python/PEP/version changes, typing/checker
diagnostics, pytest/Hypothesis patterns, Ruff/uv/ty, coverage/mutation signals,
profiling tools, and schema/CLI/report interface patterns.

Frontier findings are pointer-only. Record source URL or source ID, safe
summary, applicability limits, proof surface, local validation idea, and target
DAD surface. Do not copy docs, source, raw logs, private rows, credentials, or
benchmark tables.

## Send Back To DAD

Send candidate mail when a Python change reveals:

- a reusable idiom with avoid-when limits;
- a test selection or fixture pattern that saved time without hiding coverage;
- a property/static/negative test that caught an agent mistake;
- a profiling result that falsified or supported a speed claim;
- a new frontier source pointer that could improve DAD assets or harnesses.

