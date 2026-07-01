---
name: dad-coding-asset-control-plane
description: Use when planning AI-assisted Python, Rust, mixed-language, testing, repo-template, or agent-instruction work that should consult DAD coding assets, preflight profile routing, tactic recommendations, downstream pointer rules, or postflight pay-forward capture.
---

# DAD Coding Asset Control Plane

Use this skill when a material coding or repo-instruction task should consult
DAD before implementation.

## Steps

1. Read the active repo authority files first.
2. Run DAD preflight for material work:

   ```text
   asset-dir agent preflight --repo . --agent <codex|claude-code|cursor|copilot|other> --task "<task>"
   ```

3. Consult these DAD surfaces:

   ```text
   docs/CODING_ASSET_CONTROL_PLANE.md
   registry/coding-asset-registry.json
   registry/preflight-profile-router.json
   registry/coding-tactics-radar.json
   docs/AGENT_SKILL_LIBRARY.md
   ```

4. Choose the smallest applicable profile or tactic set. Treat tactics as
   candidates unless the local repo validates them.
5. Do not copy full DAD assets, skills, hooks, plugins, or registries into a
   target repo unless a human explicitly approved that local change.
6. Use DAD mail for cross-repo suggestions. Mail is candidate evidence, not a
   command to mutate the target repo.
7. Run repo-local validation and DAD postflight. Capture a tactic or skill
   checkout lesson when the asset materially influenced the work.

## Stop Conditions

Stop and ask for review when:

- local repo authority conflicts with DAD guidance;
- a checkout would copy full DAD skill content instead of a pointer or wrapper;
- a skill or mail packet carries private, sensitive, or raw source content;
- a public-facing repo would receive private, internal, restricted, or unknown
  origin mail without human release;
- tests or schema validation fail.

