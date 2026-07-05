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

`rust-rollout build-mail` runs DAD's mail dirty-state gate before regenerating
staged instruction packets under `processed/mail/staged/rust_rollout/`. If DAD
is dirty and packet regeneration itself is a reviewed repair action, use
`--dirty-state-ack "<reason>"` with the current
`--dirty-state-fingerprint "<fingerprint>"` reported by `mail storm-gate` or
`mail doctor`; normal mail collect, route, and deliver commands still fail
closed on dirty state.

During a multi-repo Rust mail storm, run the authoritative gate first:

```powershell
python -m digital_asset_directory.cli mail storm-gate
python -m digital_asset_directory.cli mail doctor --repo all --summary-only --fail-on-dirty --fail-on-coverage-gap
```

For a fast read-only Rust leaf probe of hub-local mail roots, run:

```powershell
python -m digital_asset_directory.cli rust mail-spool-check
```

The Rust probe reports structural evidence only. Python `mail storm-gate` gives
the first go/no-go answer, and `mail doctor` remains the detailed authority for
collect, route, deliver, public release, and adoption.

The tracked `mail/outbox/rust_rollout/` tree is a reviewed reference snapshot,
not the routine build target. Writing there requires
`--promote-reference-snapshot-ack "<reason>"` after reviewing the staged packet
diff and promotion evidence. Promotion appends metadata-only evidence to
`processed/mail/archive/rust_rollout_snapshot_promotion.jsonl`, including packet
hashes and the acknowledgement. That log is audit evidence only; it does not
authorize inbox delivery, target repo adoption, public release, or cross-repo
writes.
