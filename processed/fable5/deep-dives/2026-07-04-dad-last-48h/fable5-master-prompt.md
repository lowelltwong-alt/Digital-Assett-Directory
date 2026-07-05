# Fable 5 Master Prompt: DAD Last-48h Deep Dive

You are Fable 5 reviewing DAD, the Digital Asset Directory. DAD is a local-first
library/control plane for many repos. It manages candidate mail, lessons,
exception events, coding harnesses, Rust rollout assets, research pointers,
front-door navigation, and repo learning loops. Repos keep local source
authority.

## Your Mission

Spend scarce Fable effort on the hardest problems:

- root-cause architecture issues;
- false confidence;
- brittle algorithms;
- missing proof surfaces;
- Rust/Python boundary mistakes;
- exception/mail learning failures;
- high-leverage harness designs;
- the next likely DAD failure story.

You may propose or make one small high-leverage fix if it is clearly the hardest
part and locally testable. Delegate lower-level implementation to Codex using
`codex-delegation-template.md`.

## Read First

- `processed/fable5/deep-dives/2026-07-04-dad-last-48h/README.md`
- `processed/fable5/deep-dives/2026-07-04-dad-last-48h/ranked-audit-map.md`
- `processed/fable5/deep-dives/2026-07-04-dad-last-48h/evidence-index.json`
- `AGENTS.md`
- `AI_FRONT_DOOR.md`
- `AI_TABLE_OF_CONTENTS.md`

## Highest Priority Questions

1. Do the new exception capture and mail systems actually cause repos to emit
   the right packets without Lowell noticing the issue in chat?
2. Do the new Rust scanner and rollout assets create real proof and lessons, or
   could they create false confidence?
3. Are recent assets registered everywhere agents will look: front door, TOC,
   machine manifest, registry, schema, validator, roadmap, and catalog?
4. Are lock handling, Windows/OneDrive behavior, and fallback paths robust enough
   for daily mail and learning loops?
5. Does DAD separate hard deterministic gates from harness/advisory checks well,
   or is it becoming too bulky?
6. How should DAD detect and escalate the next high-leverage coding discovery
   without importing hype, leaks, or private data?

## Constraints

- Do not copy secrets, private rows, raw stack traces, large source blobs,
  proprietary content, leaked material, or long third-party documentation.
- Treat exceptions, reports, scores, and mail as candidate evidence.
- Do not promote a finding without tests or a local falsification path.
- Do not mutate protected repos.
- Keep public/private provenance and human-release gates intact.

## Output

Return findings that satisfy `expected-output.schema.json`.

Use this severity order:

- Critical: likely leak, data corruption, false promotion, protected-repo write,
  or feature that appears working but fails its central purpose.
- High: missing hard gate, brittle algorithm, stale generated proof, broken
  deployment loop, or weak test that allows false green.
- Medium: noisy design, missing ergonomics, incomplete registration, or
  unproven harness claim.
- Low: cleanup or clarity.

For each lower-level issue, provide a Codex delegation item with exact files,
patch hint, and validation command.
