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

Run a digest at most once per day unless a human asks for an immediate check:

```text
asset-dir mail digest --repo .
```

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

Do not commit mailbox JSONL to a public-facing repo unless a human explicitly
reviews the packet provenance and public-release status.
