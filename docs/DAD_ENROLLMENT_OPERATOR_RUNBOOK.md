# DAD Enrollment Operator Runbook

Step-by-step operator flow for enrolling, inspecting, and rolling back a repo,
plus recovery for the reliability issues this runbook was written to remove.
Companion to `DAD_REPO_ENROLLMENT.md` (contract) and `AGENTS.md` (authority).

## 0. One-time machine setup — stop copying private config by hand

`config/sources.local.yaml` holds enrollment policies and is gitignored, so it
never appears in an isolated worktree. Record a governed pointer once instead of
copying it into each worktree:

```text
asset-dir config set-local-pointer --path "C:\path\to\live\config\sources.local.yaml"
asset-dir config show
```

`config show` prints the precedence chain and which file won. Isolated worktrees
now resolve the canonical config automatically. `--config <file>` and a repo's
own `config/sources.local.yaml` still take precedence; a missing pointer is
ignored with a warning (never a silent wrong-config).

## 1. Confirm the dev environment can run tests

If `python -m pytest` reports `No module named pytest`, the interpreter lacks the
declared dev extras. Detect and get the exact recovery (this never installs):

```text
asset-dir dev-env
```

Recovery (run it yourself, in the intended interpreter / activated `.venv`):

```text
python -m pip install -e ".[dev]"
```

Supported: Python >= 3.11; run tests with `PYTHONPATH=src` set
(`$env:PYTHONPATH='src'` in PowerShell).

## 2. Work in an isolated worktree

Never enroll from the live checkout. Branch from the remote tip and pass `--hub`
so DAD writes land in the worktree, not another checkout:

```text
git fetch origin
git worktree add -b codex/<task> <worktree-path> origin/main
asset-dir agent preflight --repo <worktree-path> --agent <id> --task "<task>" --hub <worktree-path>
```

If the preflight cannot write its decision-trace ledger, it now returns the
context pack with a `decision_trace_recovery` instruction instead of crashing.
Follow it: run from a writable hub/worktree, pass `--hub`, initialize a writable
`DAD_DATA_ROOT` (`asset-dir data status`), or fix directory permissions.

## 3. Discover, plan, and check nested visibility

```text
asset-dir enroll discover
```

Read `nested_visibility_conflicts` in the output. A nested Git repo inside a
configured parent folder keeps its own exact policy — the most specific path
wins — but a visibility mismatch (e.g. a private repo inside a public parent
folder) is flagged so the parent cannot silently misclassify the child. Add an
exact policy for the nested repo with its correct visibility before planning.

```text
asset-dir enroll plan --repo <path-or-id> --wave <id>
```

## 4. Apply (reviewed approval required)

```text
asset-dir enroll apply --repo <path-or-id> --approval-id <reviewed-id>
git config core.hooksPath .githooks   # activate the disclosed pre-push hook
asset-dir enroll status --repo <path-or-id>   # expect lifecycle_state: enrolled
```

Apply fails closed without a reviewed policy + approval id, on a dirty worktree,
or on a non-main branch unless the policy explicitly allows it.

## 5. Cancel or roll back

- **Cancel before apply** (audit-only, writes nothing to the repo):

  ```text
  asset-dir enroll cancel --repo <path-or-id> --reason "paused by human"
  ```

- **Roll back / unenroll** after surfaces were written (reviewed approval
  required). Removes DAD-managed config/pointer/map/hook surfaces and strips only
  the marker-bounded governance blocks, preserving repo-owned material:

  ```text
  asset-dir enroll unenroll --repo <path-or-id> --approval-id <reviewed-id>
  asset-dir enroll status --repo <path-or-id>   # expect lifecycle_state: retired
  ```

  Idempotent and resumable: re-running reports `already_removed`; a partial
  failure records `rollback_incomplete` so a resume re-run finishes. The
  append-only `processed/enrollment/audit.jsonl` keeps the full history.

  Never removed by unenroll: `.digital-asset/mail/*.jsonl`, asset memory,
  learning events, and source-owned exception/fix-outcome paths.

## 6. Paused enrollment records

If enrollment was stopped after plan/apply, the central `audit.jsonl` and
`processed/enrollment/plans/*` are candidate evidence. Do not commit or publish
them without a human decision. Leave them untouched until the owner decides.

## Performance note (focused enrollment suite)

The enrollment test suite's wall time is dominated by filesystem overhead, not
algorithm cost: each `apply` writes ~22 small files and `_repo_git_state` spawns
several `git` subprocesses (~0.15s each on Windows). On a OneDrive-synced tree
with Defender scanning every written/spawned file this inflates to ~60-90s; the
in-test compute is ~10-17s and on Linux CI the suite is fast. To speed local
runs, run the suite from a non-synced path or exclude the dev tree from
real-time antivirus scanning. Correctness is unchanged either way.
