# DAD Enrollment Plan: enroll-wave-2026-07-18-law-firm-digital-twin

DAD enrollment installs or updates only reviewed, marker-bounded governance surfaces after a human approval ID. Normal recurring DAD operation remains mailbox-only under .digital-asset/mail/**.

| Repo | Operation | Wave | Apply Ready | Update Ready | Branch | Dirty | Holds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `law-firm-digital-twin` | `enroll` | `wave-2026-07-18-law-firm-digital-twin` | True | True | `master` | 61 |  |

Approved DAD-managed paths:

- `.digital-asset/dad-integration.json`
- `.digital-asset/mail/README.md`
- `.digital-asset/mail/.gitignore`
- `.digital-asset/mail/inbox.jsonl`
- `.digital-asset/mail/outbox.jsonl`
- `.digital-asset/mail/archive.jsonl`
- `.digital-asset/mail/adoption.jsonl`
- `.digital-asset/assets/README.md`
- `.digital-asset/assets/index.jsonl`
- `.digital-asset/assets/adoption.jsonl`
- `.digital-asset/learning/events.jsonl`
- `.digital-asset/skills/checkout.json`
- `.digital-asset/context-map.json`
- `.digital-asset/governance-map.yaml`
- `.digital-asset/data-map.yaml`
- `.ai-assets.json`
- `AGENTS.md`
- `CLAUDE.md`
- `AI_FRONT_DOOR.md`
- `AI_TABLE_OF_CONTENTS.md`
- `.githooks/pre-push`
- `.githooks/pre-push.ps1`

Repo-local source-owned paths (not written by enrollment):

Repo-local exception and fix-outcome paths are source-repo owned and are not created or updated by DAD enrollment. They are not DAD-managed authority surfaces and normal DAD operation may not mutate them.

- `.digital-asset/exceptions/README.md`
- `.digital-asset/exceptions/.gitignore`
- `.digital-asset/exceptions/outbox.jsonl`
- `.digital-asset/exceptions/inbox.jsonl`
- `.digital-asset/exceptions/archive.jsonl`
- `processed/exceptions/fix-outcomes/outcomes.jsonl`

Normal recurring operation after enrollment writes only to `.digital-asset/mail/**`.
