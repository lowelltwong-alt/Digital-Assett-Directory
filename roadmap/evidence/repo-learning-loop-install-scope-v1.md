# Repo Learning Loop Install Scope V1

## Summary

This change adds a generated approval scope for repo-local learning-loop
installation:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend repo-learning-loop-scope --limit 50
```

The command writes generated outputs only:

```text
processed/reports/repo_learning_loop_install_scope.md
processed/reports/repo_learning_loop_install_scope.json
processed/reports/repo_learning_loop_install_approval_prompt.md
```

## Why

The goal is to automate lessons across repos, but DAD must not silently mutate
active source repositories. A selection scope creates the bridge: it shows which
repos lack learning-loop surfaces, what files would be written, and the exact
files-only install command, while keeping installation behind explicit per-repo
approval.

## Priority Methodology

```text
priority_score = 100 * (0.35*learning_gap + 0.20*ai_navigation_readiness + 0.15*validation_readiness + 0.15*governance_readiness + 0.10*configured_source_path + 0.05*low_noise_bonus)
```

The score is review routing only. It does not prove repo value, source truth, or
permission to write.

## Boundaries

- Uses existing catalog metadata and logical paths only.
- Does not write to downstream/source repos.
- Does not install hooks.
- Does not read source file contents.
- Does not create repo learning events automatically.
- Does not promote generated findings to truth.

## Context

Applies when a human is deciding which cataloged repos should receive files-only
DAD learning-loop templates.

Does not apply when the repo is active and no explicit write approval has been
given, or when the repo already has an equivalent reviewed learning mechanism.

Danger if misapplied: installing learning-loop files without per-repo approval
can mutate active repos and create process noise.

## Acceptance Status

Implemented as generated candidate infrastructure. No roadmap phase is marked
complete by this evidence.
