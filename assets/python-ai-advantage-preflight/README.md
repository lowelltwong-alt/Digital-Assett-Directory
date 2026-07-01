# Python AI Advantage Preflight Asset

Version: 0.1.0

This DAD-ready asset teaches AI coding agents to use Python deliberately rather than copying the average GitHub style.

It covers:

- Python keywords and soft keywords.
- Operators, delimiters, literals, builtins, reserved names, and dunder hooks.
- High-leverage but often under-applied Python techniques.
- AI preflight instructions for Python modules, long scripts, boundaries, tests, and refactors.

## Core idea

Average repository code is not a sufficient standard. AI coding agents are strongly influenced by common code patterns in public source corpora, but common code contains bugs, under-typed interfaces, weak boundaries, duplicated logic, and insecure defaults. This asset teaches the agent to prefer explicit boundaries, typed data, resource safety, and verifiable behavior.

## Recommended DAD placement

```text
assets/python-ai-advantage-preflight/
```

## Recommended downstream pointer

```md
Before Python work, consult the DAD asset:

`../Digital-Assett-Directory/assets/python-ai-advantage-preflight/`

Use:
- `templates/AGENTS_PYTHON_ADVANTAGE_BLOCK.md`
- `templates/PYTHON_PREFLIGHT_PROFILE.md`
- `prompts/codex_python_advantage_preflight.prompt.md`
```

## Use before

- Python feature work
- Python refactors
- long script cleanup
- repo template creation
- AI coding-agent instruction writing
- security-sensitive Python code
- filesystem/config/data-pipeline code

## Do not use as

- a mandate to use every advanced feature;
- an excuse for clever code;
- a replacement for repo-local authority, tests, or review.

The rule is: use the smallest Python feature that makes the boundary, data shape, resource lifetime, or verification path clearer.
