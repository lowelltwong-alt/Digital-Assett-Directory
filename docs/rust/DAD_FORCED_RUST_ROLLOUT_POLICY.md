# DAD Rust Rollout Policy

DAD implements Rust in DAD first. Downstream repos receive candidate plans and
local instruction packets unless a reviewed policy record allows a local apply.

Hard rules:

- A repo with `logos` anywhere in its name is instruction-mail-only.
- `--force` never bypasses Logos exclusion.
- `apply` requires a reviewed `--approval-id dad:approval:<id>` and a clean
  target git worktree when the target is a git repo.
- A repo without a configured `local_path` cannot receive an apply.
- Absolute `local_path` values require an explicit reviewed config allowance.
- Disabled, archived, inactive, or unsafe repos cannot receive an apply unless
  config explicitly overrides that status.
- Target repos own their own Rust files.
- DAD does not push, open PRs, call GitHub writes, send external email, or make
  destructive source changes as part of Rust rollout.

The source policy files are:

- `config/rust_rollout_policy.yaml`
- `config/repo_rust_status.yaml`

The main commands are:

```bash
asset-dir rust scan-local --help
asset-dir rust-rollout plan
asset-dir rust-rollout build-mail
asset-dir rust-rollout apply --repo Digital-Assett-Directory --approval-id dad:approval:<id> --force
asset-dir rust-rollout lessons-summarize
```
