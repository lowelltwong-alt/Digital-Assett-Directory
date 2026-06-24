# Lessons and Handoff Loop

## Governing distinction

Keep these separate:

```text
feedback -> inference -> proposal -> reviewed asset -> promoted baseline
```

A lesson captured by an AI is initially a candidate. Repetition may justify a skill or workflow proposal, but not automatic promotion.

## Mandatory postflight payload

- task and repository;
- agent/model where known;
- changed files;
- commands and tests;
- tests not run;
- confirmed findings;
- inferred findings;
- assumptions and unknowns;
- failures and edge cases;
- reusable patterns;
- missing capabilities;
- new assets produced;
- next actions and risks.

## Repetition to skill candidate

When the same reusable pattern or missing capability appears repeatedly, emit a candidate such as:

- context-intake skill;
- citation/provenance audit skill;
- staleness validation skill;
- evaluation-generation agent;
- escalation-routing skill;
- lesson-capture agent;
- source-ingestion checklist;
- schema or adapter pattern.

The threshold is configurable and the generated candidate remains reviewable.
