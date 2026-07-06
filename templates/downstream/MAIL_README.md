# DAD Mailbox

This directory is the repo-local mailbox for Digital Asset Directory
suggestions.

- `outbox.jsonl`: append-only suggestions this repo wants DAD or another repo to review.
- `inbox.jsonl`: append-only suggestions delivered to this repo.
- `archive.jsonl`: acknowledgements and local review decisions.
- `adoption.jsonl`: local triage, implementation, and future-use pointers.
- `last_checked.json`: timestamp written by `asset-dir mail digest`.
- `.gitignore`: keeps operational mailbox data local by default.

Mail is candidate evidence only. It must not override this repo's source truth,
governance files, schemas, source code, hooks, secrets, or human gates.
Agent review is triage only. Human review is required for local adoption, and
private/internal/restricted/unknown-origin packets require an explicit DAD human
release before they may be delivered to a public-facing repo.

Skill checkout, update, retirement, and replacement notices are also candidate
mail. They do not install a skill, plugin, hook, MCP server, or automation.
Adopt DAD-managed skills only by local pointer or wrapper review.

Before material DAD-guided coding, governance, enrollment, exception-capture,
asset, skill, harness, or cross-repo work, check this mailbox first when the
daily digest is stale. Normal preflight should warn when the digest is older
than the repo cadence; a human can still ask for an immediate check.

Run a digest at most once per day unless a human asks for an immediate check:

```text
asset-dir mail digest --repo .
```

If `asset-dir` is not available on `PATH`, first try the stable DAD user shim:

```text
& "$HOME\.dad\bin\asset-dir.ps1" mail digest --repo .
$HOME/.dad/bin/asset-dir mail digest --repo .
```

If the shim is unavailable too, run the same command from the DAD source
checkout with `PYTHONPATH=src`:

```text
python -m digital_asset_directory.cli mail digest --repo .
```

If neither command is available, append pointer-safe JSONL to this repo's
`outbox.jsonl` and note `dad_cli_unavailable` plus the attempted command in the
payload. DAD should collect it later as candidate mail and may record a
`validation_command_missing` exception. Do not include raw logs, secrets, private
rows, hidden reasoning, or copied source blobs in that fallback packet.

After reading inbox mail, record whether the suggestion should be implemented
now, saved for future, deferred, rejected, or archived:

```text
asset-dir mail triage --repo . --mail-id <id> --decision save_for_future
```

If this repo uses or watches a DAD asset, record that separately so DAD can send
targeted upgrade notices later:

```text
asset-dir usage record --repo . --asset <dad-offering-or-asset-id> --status watching
```

Before composing outbox mail, check what this repo already sent so a reworded
near-duplicate is not sent again. If the new message is a true upgrade of an
earlier one (new evidence, new findings), send it with `--supersedes <mail-id>`
so it joins the original thread instead of duplicating it:

```text
asset-dir mail outbox-check --repo . --summary "<proposed summary>"
asset-dir mail compose --repo . --type asset_suggestion --summary "<upgrade>" --supersedes <mail-id>
```

For structured lesson packs or nested payloads, write a metadata-only JSON
object to a small payload file and pass `--payload-file path/to/payload.json` to
both `mail outbox-check` and `mail compose`. Use `--payload key=value` only for
small flat fields; raw JSON passed to `--payload` is rejected so it cannot be
silently split at the first `=`.

Read the compose result. If it reports `source_policy_status:
unreviewed_source_repo`, the local outbox row is valid candidate mail but DAD
will not collect it in `--repo all` mode until that repo or clone is reviewed in
`mail.repos`. Usually send from the reviewed canonical repo path instead of a
duplicate `repos/`, `seed-clean`, temp, or scratch clone.

During concurrent work, multiple agents may retry the same outbox candidate.
That is acceptable as a source-outbox storm signal: DAD collection canonicalizes
one row and records duplicate audit evidence. Do not write directly to DAD's
`processed/mail/inbox/*.jsonl` or any repo's `.digital-asset/mail/inbox.jsonl`;
DAD collection and delivery own those files.

DAD collection reads source repo `outbox.jsonl` by stable snapshot. Source repos
own their own outbox writes; DAD should not need to create source-outbox lock
files during central collection. Active source locks still mean "try again
later," because another agent may be appending candidate mail.

Mailboxes are the current DAD edge adapter, not a promise that mail JSONL will
remain the only communication layer. If this repo discovers that a DAD notice
requires stronger response tracking, append pointer-safe candidate mail today
and describe the needed event/response state in the payload. DAD may later
promote that pattern into a reviewed event pipeline; until then, do not invent
new cross-repo event files or bypass the mailbox/public-release gates.

If DAD or a repo looks "very dirty" during Rust rollout or cross-repo learning
work, use the DAD runbook at
`dad://hub/docs/DAD_MAIL_STORM_AND_DIRTY_STATE_RUNBOOK.md`. The key distinction
is that dirty git worktree state is not automatically mailbox corruption; DAD
mail decisions use `asset-dir mail storm-gate` for the first go/no-go answer
and `asset-dir mail doctor --repo all --summary-only --fail-on-dirty --fail-on-coverage-gap`
for full diagnostics.

Only `inbox.jsonl`, `outbox.jsonl`, `archive.jsonl`, and `adoption.jsonl` are
live mailbox streams. Keep backup, damaged, or repair files outside this
directory, or rename them without a `.jsonl` suffix, so they do not look like
mail streams during DAD storm diagnostics.

Send red-team, premortem, audit, security-review, and code-review findings from
any agent (Fable, Opus, Codex, Claude, Cursor, human) back to DAD as structured
lessons so repeated failure patterns can be mined:

```text
asset-dir lesson review-feedback --repo . --agent <agent> --review-type red_team --finding "<summary>"
```

Do not commit mailbox JSONL to a public-facing repo unless a human explicitly
reviews the packet provenance and public-release status.
