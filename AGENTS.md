# Agent Operating Contract

This file is read by Codex and may be imported by Claude Code through `CLAUDE.md`.

## Read first

1. `AI_FRONT_DOOR.md`
2. `MACHINE_NAVIGATION_MANIFEST.json`
3. `registry/source-of-truth.json`
4. `registry/design-authority.json`
5. `AI_TABLE_OF_CONTENTS.md`
6. task-relevant schemas, registries, and roadmap gates

## Before material work

Run a preflight:

```text
asset-dir agent preflight --repo . --agent <codex|claude-code|other> --task "<task>"
```

State the route, scope, validation plan, and stop conditions before editing.

## Operating rules

Agents must:

- inventory before editing;
- preserve source-repository authority boundaries;
- keep raw observations immutable and append-only;
- treat generated metadata, links, scores, and synergies as candidates;
- use stable asset identity and separate revision identity;
- preserve provenance and confidence labels;
- keep changes narrow and reversible;
- run task-relevant validation;
- report exact commands and results;
- capture at least one explicit lesson or state that no reusable lesson was found;
- produce a postflight before reporting completion.

Agents must not:

- mutate scanned source files during discovery;
- store secrets or raw credentials;
- infer a source repo's canon from runtime evidence;
- silently change registry semantics;
- mark roadmap work complete without acceptance evidence;
- claim tests passed unless they were run;
- treat graph centrality, similarity, entropy reduction, stars, or model output as proof of truth or value;
- auto-merge external code without license, provenance, security, and compatibility review.

## Required postflight

```text
asset-dir agent postflight --session <SESSION_ID> --repo . --summary "<summary>" --tests "<commands or not run>"
```

The final report must include:

- files changed;
- commands run;
- tests run and results;
- tests not run;
- confirmed findings;
- inferred findings;
- assumptions;
- unknowns;
- reusable lessons;
- remaining risks.

## Validation baseline

```bash
python -m pytest
python -m digital_asset_directory.cli validate
python -m digital_asset_directory.cli roadmap check
```
