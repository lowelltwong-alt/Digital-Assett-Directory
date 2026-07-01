# Reusable Assets

This directory stores reviewed reusable assets that DAD can consult before
software implementation, refactors, repo-template work, or downstream rollout
planning.

Installed assets are not generated reports. Treat each asset directory as the
source package for that reusable asset, and use `assets/asset-registry.json` as
the local index for discovery, provenance, and rollout notes.

## Current Assets

| Asset | Path | Use when |
|---|---|---|
| AI Engineering Preflight Asset | `assets/ai-engineering-preflight/` | You need AI coding-agent preflight guidance, Python/Rust modular encapsulation rules, repo-ready instruction templates, or dry-run rollout scripts. |
| Python AI Advantage Preflight Asset | `assets/python-ai-advantage-preflight/` | You need Python-specific preflight guidance, underused high-leverage Python tactic candidates, or a Python agent instruction block with applicability limits. |
| DAD Agent Skill Library | `registry/agent-skill-library.json` | You need to find, check out, update, retire, or replace DAD-managed agent skills by pointer or wrapper. |
| lowelltwong-alt Repo Map And Wave Plan | `assets/repo-rollout-plans/lowelltwong-alt-repo-map-and-wave-plan-v0.1.0/` | You need candidate rollout waves, repo-family classifications, or draft DAD managed-pointer/mailbox commands for the `lowelltwong-alt` workspace. |

## Safety Rules

- Dry-run asset scripts before applying changes.
- Do not deploy an asset into another repository unless the task explicitly
  asks for that repo mutation.
- Keep downstream rollout decisions separate from installing the central asset.
- Check out DAD agent skills by pointer or wrapper; do not copy full skill
  bodies, plugins, hooks, or automation into another repo without approval.
- Treat rollout plans as candidate evidence until DAD refreshes local repo
  paths, authority files, branch state, visibility, and mail policy.
- Preserve asset provenance and avoid copying secrets, private rows, or raw
  credentials into asset metadata.
