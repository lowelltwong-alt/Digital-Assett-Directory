# Preflight Profile Routing

Status: candidate routing guide for AI coding agents.

The router lives at:

```text
registry/preflight-profile-router.json
```

It maps task/context signals to:

- required preflight profiles;
- optional tactic bundles;
- recommended tactic IDs;
- validation expectations;
- authority boundaries;
- stop conditions.

## Use

Before material coding work, run DAD preflight, then ask the router which
profiles and tactics fit the task.

Preflight also returns `recommended_review_lanes`. For material coding,
governance, mail, enrollment, schema, registry, public/private, or cross-repo
work, run these lanes as subagents when available or as explicit checklist
prompts otherwise:

- `review-lane:red-team-and-premortem` checks the current work for defects,
  false confidence, governance drift, sensitive-data movement, and missing
  tests.
- `review-lane:lesson-asset-harness-scout` looks for reusable lessons, novel or
  important digital assets, coding-harness ideas, skill updates, and DAD needs.

Example:

```text
python scripts/suggest_coding_tactics.py --task "Refactor a long Python CLI script without changing behavior" --language python --risk behavior_preservation
```

For a Rust API design task:

```text
python scripts/suggest_coding_tactics.py --task "Design a Rust library API for a parity shadow layer" --language rust --risk public_api
```

## Midflight Prompt

When stuck or drifting toward generic code, ask:

```text
Given this repo, task, language, and failure mode, what DAD tactics should I consider?
Task: <task>
Language: <python|rust|mixed|agent-instruction>
Failure mode: <what is going wrong>
Constraints: <local authority, test limits, security/privacy concerns>
```

The response should include only tactics that fit the context:

- tactic name;
- why it applies;
- why it may not apply;
- risk if misapplied;
- minimal example;
- verification check.

Midflight should re-check the review lanes when the task scope changes, a new
repo boundary appears, a private/public movement is discovered, or a reusable
asset/harness idea emerges.

## Postflight Learning

Postflight closes the loop. It must record files changed, commands/tests,
confirmed vs inferred findings, assumptions, unknowns, reusable lessons, and
remaining risks. The red-team lane contributes reusable failure modes or missing
tests. The lesson/asset/harness lane contributes candidate lessons, asset
pointers, harness ideas, skill updates, or DAD needs.

Reusable findings stay candidate evidence until reviewed. Inside DAD they can
become lessons or registry candidates. In downstream repos they should go to the
repo outbox only when local policy allows, with source repo, lane ID, task
context, sensitivity/public-private status, source pointers or hashes, suggested
DAD control plane, and validation evidence.

Record lane closure in postflight:

```text
asset-dir agent postflight ... \
  --review-lane "review-lane:red-team-and-premortem:subagent:checked failure modes" \
  --review-lane "review-lane:lesson-asset-harness-scout:checklist:captured reusable asset ideas"
```

The statuses are model-agnostic: `subagent`, `checklist`, `not_applicable`, or
`not_run`.

## Current Route Families

- default AI engineering preflight;
- Python long-script refactor;
- Python library/API design;
- Rust library/API design;
- security-sensitive token/session/public-release work;
- repo-template and downstream pointer work;
- governance-sensitive LawFirm OS work;
- test validation and parity/shadow-layer work;
- data, ETL, CLI, and file-processing work.

## Boundary

Routes are recommendations. Target repos keep local authority. A route must
stop when local guidance conflicts, a secret or private row appears, source
visibility is unclear for public-facing delivery, or validation cannot prove the
claim being made.
