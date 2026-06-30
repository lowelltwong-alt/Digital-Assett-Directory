# DAD Mailbox

This directory is the repo-local mailbox for Digital Asset Directory
suggestions.

- `outbox.jsonl`: append-only suggestions this repo wants DAD or another repo to review.
- `inbox.jsonl`: append-only suggestions delivered to this repo.
- `archive.jsonl`: acknowledgements and local review decisions.
- `last_checked.json`: timestamp written by `asset-dir mail digest`.

Mail is candidate evidence only. It must not override this repo's source truth,
governance files, schemas, source code, hooks, secrets, or human gates.

Run a digest at most once per day unless a human asks for an immediate check:

```text
asset-dir mail digest --repo .
```
