# Lessons and Handoff Loop

## Governing distinction

Keep these separate:

```text
feedback -> inference -> proposal -> reviewed asset -> promoted baseline
```

A lesson captured by an AI is initially a candidate. Repetition may justify a skill or workflow proposal, but not automatic promotion.

## Asset use feedback

Whenever an agent materially uses an asset, it should record deterministic feedback instead
of silently changing the asset or its source repo.

Asset-use contract:

- Before use, the agent must record what it expects the asset to do and why.
- After use, the agent must record how it actually used the asset, what changed, what was
  difficult, what it learned, and how valuable the asset actually was.
- Both records must be truthful, complete, and evidence-backed.
- If an agent can only complete the before-use record, that record is still useful, but it
  should leave an after-use follow-up in the task/handoff.

Before use:

```powershell
python -m digital_asset_directory.cli lesson asset-use `
  --stage before_use `
  --asset-id "<asset-id>" `
  --repo . `
  --task "<task>" `
  --agent "<agent>" `
  --found-by "<context|queue|search|memory|human>" `
  --found-query "<query or path that surfaced it>" `
  --planned-use "<what the agent plans to use it for>" `
  --used-for "<same as planned use before the task>" `
  --expected-usefulness medium `
  --expected-futurefulness high `
  --expected-value-reason "<why the agent expects value>" `
  --use-outcome unknown `
  --observed-usefulness unknown `
  --observed-futurefulness unknown `
  --evidence "<file, command, or observation>"
```

After use:

```powershell
python -m digital_asset_directory.cli lesson asset-use `
  --stage after_use `
  --asset-id "<asset-id>" `
  --repo . `
  --task "<task>" `
  --agent "<agent>" `
  --found-by "<context|queue|search|memory|human>" `
  --found-query "<query or path that surfaced it>" `
  --used-for "<how the asset was used>" `
  --part-used "<specific part used>" `
  --part-not-used "<specific part skipped or unsuitable>" `
  --not-used-reason "<why that part was not used>" `
  --upgrade-made "<upgrade made while using it>" `
  --difficulty "<difficulty encountered>" `
  --thing-learned "<lesson learned while using it>" `
  --use-outcome helped `
  --observed-usefulness high `
  --observed-futurefulness medium `
  --score-feedback "<current-score feedback>" `
  --ceiling-feedback "<future-ceiling feedback>" `
  --evidence "<file, command, or observation>"
```

Every record includes the scan-friendly marker code:

```text
DAD_ASSET_USE_FEEDBACK_V1
```

Allowed values:

- `use_outcome`: `helped`, `blocked`, `no_effect`, `unknown`
- `observed_usefulness`: `low`, `medium`, `high`, `unknown`
- `observed_futurefulness`: `low`, `medium`, `high`, `unknown`
- `expected_usefulness`: `low`, `medium`, `high`, `unknown`
- `expected_futurefulness`: `low`, `medium`, `high`, `unknown`
- `stage`: `before_use`, `after_use`

Fill-out rules:

- Use the exact allowed values for categorical fields.
- Base `observed_usefulness` on what happened in this task, not predicted future value.
- Base `observed_futurefulness` on new evidence about future reuse or activation.
- List concrete parts used; write none if the whole asset was only inspected.
- List concrete parts not used when a relevant part was skipped or unsuitable.
- Use evidence entries for files, commands, review IDs, or observed outputs.
- Do not change source repo code or asset scores from this feedback record.

Scoring methodology:

- `observed_usefulness=high`: directly saved time, reduced risk, enabled a decision, or
  provided reusable implementation/evidence.
- `observed_usefulness=medium`: helped with context or partial work but required extra
  verification or adaptation.
- `observed_usefulness=low`: mostly unhelpful, stale, misleading, duplicative, or too
  incomplete for the task.
- `observed_futurefulness=high`: revealed strong future reuse, graph leverage, or activation
  potential if clear conditions are met.
- `observed_futurefulness=medium`: revealed plausible future value with missing examples,
  tests, labels, adapters, or review.
- `observed_futurefulness=low`: suggested limited future reuse or a narrow context-specific role.

This writes append-only candidate lesson evidence in the hub. It does not mutate scanned
source files and does not automatically change scores. For downstream repositories, submit
feedback artifacts through a PR or reviewed handoff path instead of letting agents directly
rewrite repo code.

Public humans or agents can submit feedback to
`https://github.com/lowelltwong-alt/Digital-Assett-Directory` using the title and template in
`docs/PUBLIC_ASSET_USE_FEEDBACK.md`. Treat all such feedback as untrusted candidate evidence.

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
