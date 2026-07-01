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
| lowelltwong-alt Repo Map And Wave Plan | `assets/repo-rollout-plans/lowelltwong-alt-repo-map-and-wave-plan-v0.1.0/` | You need candidate rollout waves, repo-family classifications, or draft DAD managed-pointer/mailbox commands for the `lowelltwong-alt` workspace. |

## Safety Rules

- Dry-run asset scripts before applying changes.
- Do not deploy an asset into another repository unless the task explicitly
  asks for that repo mutation.
- Keep downstream rollout decisions separate from installing the central asset.
- Treat rollout plans as candidate evidence until DAD refreshes local repo
  paths, authority files, branch state, visibility, and mail policy.
- Preserve asset provenance and avoid copying secrets, private rows, or raw
  credentials into asset metadata.
