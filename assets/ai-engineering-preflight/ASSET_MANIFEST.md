# Asset Manifest

## Name

`ai-engineering-preflight-asset`

## Version

`0.1.0`

## Purpose

A source-of-truth asset directory for AI coding-agent instructions, repository preflight templates, Python modular encapsulation rules, Rust modular API rules, and safe rollout scripts.

## Canonical install path

```text
assets/ai-engineering-preflight/
```

## Managed block ID

```text
AI_ENGINEERING_PREFLIGHT_ASSET
```

Any deployment that appends instructions to an existing repo file should use:

```md
<!-- BEGIN AI_ENGINEERING_PREFLIGHT_ASSET -->
...
<!-- END AI_ENGINEERING_PREFLIGHT_ASSET -->
```

## Profiles

| Profile | Use |
|---|---|
| `common` | Generic repo guidance only. |
| `python` | Python repos and long Python scripts. |
| `rust` | Rust crates/workspaces and long Rust modules. |
| `mixed` | Repos containing both Python and Rust. |
| `auto` | Detect from `pyproject.toml`, `*.py`, `Cargo.toml`, and `*.rs`. |

## Artifact status

Confirmed:

- The package contains deployable Markdown instructions and sample repo templates.
- The package contains Python scripts for central install, repo deployment, multi-repo sync, and repo audit.
- The scripts are local-file operations only. They do not push to git remotes or call network APIs.

Assumed:

- Your central asset repository has or will have an `assets/` directory.
- You want instructions committed to target repos as repo-local files.

Unknown:

- Exact paths of your existing repos.
- Whether any target repos already have `AGENTS.md`, `CLAUDE.md`, Cursor rules, or Copilot instruction files.
