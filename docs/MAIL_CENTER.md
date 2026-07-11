# DAD Mail Center

Status: governed candidate-message channel for sharing lessons, assets,
workflows, taxonomy ideas, capability updates, and governance notices across
repos.

DAD is the central mail hub. Persistent repos may keep a lightweight local
mirror under `.digital-asset/mail/`. The mirror is intentionally small: JSONL
files plus a README. A repo does not need to vendor DAD's Python test suite just
to receive or send suggestions.

Mail is the repo-facing presentation and delivery adapter. DAD's newer
local-first event pipeline in `docs/DAD_EVENT_PIPELINE.md` is the candidate
state layer for deterministic response tracking, learning-loop signals, and
future mailbox-backed dataflow. Mail absence must never be interpreted as repo
adoption; actionable notices need explicit response events.

## Transport Tiers

DAD mail no longer rides the code PR pipe. T0 local pull is the default: mailbox
JSONL is a gitignored repo-local cache, DAD central spools live under the active
`DAD_DATA_ROOT`, and repos read their own inbox during preflight or digest. T1
`dad-journal` is the private data-only fallback for backup and remote agents;
remote outbox rows are ingested by the local daemon through the same screening
and quarantine gates. T2 Cloudflare relay is design-only until its human gate.

PRs remain for source-code changes and adopted lesson execution, not candidate
mail packets. Internal remote-agent access should prefer an MCP adapter over a
direct API, with mail resources read-only and mail mutation tools routed through
DAD audit/quarantine gates.

## Authority Boundary

Mail packets are append-only candidate evidence. They are not source truth,
instructions, or approval to mutate a target repo.

Mail must not overwrite:

- `AGENTS.md`, `CLAUDE.md`, Cursor rules, AI front doors, or local governance;
- registries, schemas, source code, hooks, CI, migrations, or roadmap gates;
- secrets, credentials, private rows, or large raw file contents.

Cross-repo delivery writes only to `.digital-asset/mail/` in repos covered by
reviewed DAD `mail.repos` policy. If a target is missing, read-only, lacks
reviewed target policy, ambiguous, or marked `central_only`, DAD keeps the
packet centrally.

Private, internal, restricted, and unknown source origins are not presumed safe
for public-facing repositories. If a target repo is marked `public_facing: true`
in reviewed mail policy, mail from those origins is held in central quarantine
until `asset-dir mail release` records explicit human approval. Agent-authored
mail review decisions are triage only and never satisfy public release.

## Packet Types

The mail message schema supports:

- `lesson_suggestion`
- `asset_suggestion`
- `workflow_suggestion`
- `taxonomy_suggestion`
- `capability_suggestion`
- `governance_notice`
- `inbox_ack`
- `review_decision`

Core fields are `mail_id`, `thread_id`, `message_type`, `source_repo`,
`target_repo`, `created_at`, `dedupe_key`, `sensitivity`, `review_status`,
`payload`, `evidence`, `suggested_actions`, `supersedes`,
`source_provenance`, and `public_release`.

`source_provenance` records the canonical source repo, reviewed visibility,
original source chain, return address, and compose/collect timestamps.
`public_release` records the target visibility, whether a public release gate is
required, release status, human release ID, and release reason.

Coding asset control-plane packets are represented as ordinary candidate mail.
Use `templates/mail/coding-tactic-suggestion.mail.template.json`,
`templates/mail/asset-upgrade-available.mail.template.json`, and
`templates/mail/repo-pointer-install-request.mail.template.json` for tactic
suggestions, asset upgrade notices, and downstream pointer requests. These
templates must stay short and metadata-oriented; do not include full copied
assets, source blobs, hooks, credentials, private rows, or executable authority
from untrusted mail.

Agent skill library packets are also ordinary candidate mail. Use
`templates/mail/skill-checkout-request.mail.template.json`,
`templates/mail/skill-update-available.mail.template.json`, and
`templates/mail/skill-retirement-notice.mail.template.json` when a repo should
review a skill checkout, update an existing checkout, or retire/replace a stale
checkout. Skill mail must not copy full DAD skills, plugins, hooks, MCP servers,
or automation into a target repo.

Schemas:

```text
schemas/mail-message.schema.json
schemas/lesson-payload.schema.json
schemas/mail-decision.schema.json
```

`schemas/lesson-payload.schema.json` is warning-only for the first release.
`mail compose --type lesson_suggestion` reports payload validation warnings but
still appends valid mail. Use `--no-payload-validation` only when you need an
explicit temporary escape hatch. The optional `lesson_ir`, `anonymity_set`,
`adversary_model`, `privilege_screen`, `lesson_disclosure_proof`, and
`crossing_proof` fields are sanitized receiver projections for synthetic
candidate packets. Using any projection requires explicit synthetic scope and
literal-false real/private/client/matter/carrier/privilege/work-product flags.
The projections exclude support identifiers and free text and keep all
human-review, receiver-authority, send, privacy-guarantee, and noninterference-
guarantee claims false.

Schema-valid means only that a payload matches DAD's warning-only receiver
shape. It does not authorize disclosure, crossing, delivery, promotion, legal
judgment, or compliance judgment. Intake remains the owner of QRD/IFC proof
generation; DAD receives reviewed candidate projections and cannot promote them
without its normal review gate.

## Storage

Central DAD storage:

```text
processed/mail/inbox/*.jsonl
processed/mail/outbox/*.jsonl
processed/mail/archive/*.jsonl
processed/mail/quarantine/*.jsonl
processed/mail/releases/*.jsonl
processed/reports/mail_center.md
processed/reports/mail_center.json
```

Repo-local mirror:

```text
.digital-asset/mail/inbox.jsonl
.digital-asset/mail/outbox.jsonl
.digital-asset/mail/archive.jsonl
.digital-asset/mail/adoption.jsonl
.digital-asset/mail/README.md
.digital-asset/mail/.gitignore
.digital-asset/mail/last_checked.json
```

Mailbox JSONL and `last_checked.json` are local operational state by default.
The mailbox `.gitignore` keeps them out of normal commits. Do not commit them to
a public-facing repo unless a human has reviewed packet provenance and public
release status.

## Commands

DAD docs use `python -m digital_asset_directory.cli` because some enrolled repo
shells may not have the `asset-dir` console script on `PATH`. If `asset-dir`
is missing, first try the stable DAD user shim at `$HOME/.dad/bin/asset-dir` or
`$HOME\.dad\bin\asset-dir.ps1`. When working from the source checkout, set
`PYTHONPATH=src` first. If none of those entrypoints are available in a
downstream repo, append metadata-only fallback mail to
`.digital-asset/mail/outbox.jsonl` with `dad_cli_unavailable` and the attempted
command; do not include raw logs, secrets, private rows, hidden reasoning, or
copied source blobs.

Compose a repo-local outbox packet:

```powershell
python -m digital_asset_directory.cli mail compose `
  --repo C:\path\to\repo `
  --type lesson_suggestion `
  --target-repo central_only `
  --summary "Use daily mail digest before adopting cross-repo suggestions."
```

For a structured lesson pack or other nested payload, write the JSON object to a
small payload file and pass `--payload-json path\to\payload.json` or
`--payload-json -` for stdin. UTF-8 files with a BOM are tolerated. Use
`--payload key=value` only for small flat metadata fields; raw JSON passed to
`--payload` is rejected so it cannot be silently split at the first `=`.

Read the compose result. If it reports `source_policy_status:
unreviewed_source_repo`, the local outbox row is valid candidate mail but DAD
will not collect it in `--repo all` mode until that repo or clone is reviewed in
`mail.repos`. Agents should usually send from the reviewed canonical repo path
instead of a duplicate `repos/`, `seed-clean`, temp, or scratch clone.

Use the same payload source for the novelty check before composing:

```powershell
python -m digital_asset_directory.cli mail outbox-check `
  --repo C:\path\to\repo `
  --type lesson_suggestion `
  --summary "Structured lesson pack delivery." `
  --payload-json path\to\payload.json
```

Collect repo outboxes into DAD:

```powershell
python -m digital_asset_directory.cli mail ingest
python -m digital_asset_directory.cli mail collect --repo C:\path\to\repo
python -m digital_asset_directory.cli mail collect --repo all
python -m digital_asset_directory.cli mail discover-repos
```

`mail ingest` is the preferred storm-safe receive command. It defaults to all
reviewed `mail.repos`, collects source outboxes into DAD, routes central
candidates, and never writes target repo inboxes. Use it when many repos are
sending Rust rollout lessons or learning-loop packets and you want DAD to
receive the mail without crossing protected-repo delivery boundaries.

Central collection reads repo source outboxes by stable snapshot. DAD should
not need to create lock files inside source repos just to collect their
outbound candidate mail. If a source outbox has an active lock, collection
waits for the next pass; if the lock owner is gone and the filesystem refuses
cleanup, the dead lock is recorded as a tombstone observation instead of
blocking ingest.

`--repo all` uses only reviewed `mail.repos` config entries. If bounded
discovery finds unreviewed mailbox candidates nearby, `mail collect --repo all`
and `mail deliver --repo all` fail closed unless a named
`--allow-coverage-gap-ack` is provided. `discover-repos` is read-only and
reports mailbox candidates; it does not authorize delivery. Delivery to
`--repo all` also fails closed when any enabled reviewed repo is
write-protected or delivery-disallowed; narrow delivery to explicit reviewed
targets instead of letting protected repos disappear from "all."
Discovery walks configured local source roots with bounded recursion and prunes
build, cache, archive-worktree, and test-temp directories so nested persistent
repos such as LawFirm OS subrepos can be surfaced without turning discovery
into a broad source scan.

Collection, routing, and delivery run a dirty-spool gate before writing. During
concurrent repo work, you can run the same diagnostic yourself to see the
operator summary before attempting a write:

```powershell
python -m digital_asset_directory.cli mail doctor --summary-only --fail-on-dirty
python -m digital_asset_directory.cli mail doctor --repo all --summary-only --fail-on-dirty --fail-on-coverage-gap
python -m digital_asset_directory.cli rust mail-spool-check
```

For the short operator playbook on "very dirty" DAD states, mail storms, Rust
rollout reference snapshots, wrong-box writes, and worktree-dirt separation,
read `docs/DAD_MAIL_STORM_AND_DIRTY_STATE_RUNBOOK.md`.

`mail doctor` is read-only unless `--repair-stale-locks` or
`--repair-temp-fragments` is provided. It checks JSONL lock debris, interrupted
atomic-write fragments, malformed rows, oversized rows, same-stage duplicates,
repo inbox rows without delivery-log evidence, central inbox rows that bypassed
collection, and staged Rust rollout instruction packets. Repos should write
candidate messages only to their own `.digital-asset/mail/outbox.jsonl`; DAD
collects those into `processed/mail/inbox/*.jsonl` and now writes a hash-backed
collection audit row under `processed/mail/archive/collection_log.jsonl`.
Lifecycle copies across outbox, central inbox, routed outbox, delivered inbox,
and archive are normal audit observations unless the same lifecycle stage
repeats.

Use `--repo all` when you are checking a real multi-repo mail storm. Without a
repo argument, doctor inspects DAD's hub-local mailbox, central spools, staged
mail, and Rust rollout packets; with `--repo all`, it also inspects reviewed
repo outboxes/inboxes from `mail.repos`. When `--repo all` is used, the doctor
also includes read-only `mailbox_coverage` evidence. If it reports unreviewed
mailbox candidates, DAD has found repo-local inbox/outbox files outside reviewed
mail policy. Those candidates are not collected or delivered, but they explain
why the workspace may look busy during a Rust or learning-loop storm. Doctor
uses `--fail-on-coverage-gap` for strict investigations; collect/deliver
`--repo all` fail closed by default and require `--allow-coverage-gap-ack` to
continue with reviewed repos only.

`rust mail-spool-check` is a read-only Rust leaf probe for fast structural
evidence about DAD mail roots. It reports public-safe aliases and row/file
counts only. It does not replace `mail doctor`, and it cannot authorize collect,
route, deliver, public release, or adoption.

Duplicate rows in a source repo's own outbox are treated as storm/backpressure
observations, not dirty-spool blockers. Collection canonicalizes one row into
central mail and records duplicate sightings as audit evidence. Duplicates in
central inbox/outbox, delivered inboxes, or Rust rollout packet snapshots still
block because those can create false delivery confidence or repeated inbox
spam.

When reviewed `mail.repos` policy identifies two different source repo IDs for
the same source-outbox packet identity, DAD treats that as a provenance
conflict, not a harmless retry. Collection, routing, and delivery pause until a
human or agent review determines which source repo owns the candidate message.

The doctor also reports a separate `worktree_state`. That answers a different
question: "does the DAD git tree have ordinary code, docs, registry, or Rust
snapshot changes?" A dirty worktree is not automatically a dirty mailbox.
`--fail-on-dirty` fails only for mail spool or staged-packet hazards. Use
`--fail-on-worktree-dirty` when a script truly requires a clean DAD git tree.

Collection also requires a stable source-outbox snapshot. If a repo or branch
is still appending to `.digital-asset/mail/outbox.jsonl`, DAD reports
`source_outbox_unstable`, treats the doctor result as not safe to collect, writes
no central inbox row for that moving snapshot, and expects the next collection
pass to retry after the repo agent finishes. The Rust mail-spool probe uses the
same 64 KB default row-size ceiling as Python mail validation so it does not
report a structurally clean spool for rows Python will reject as oversized.

Use the `action_summary` before deciding what to do next:

- `clean` or `clean_with_legacy_observations`: normal collection/routing may
  proceed when repo policy allows. Legacy collection-audit observations are not
  permission to rewrite old central inbox rows.
- `dirty_repairable`: pause collection and repair only active/stale lock or
  live JSONL temp hazards that are still blocking safe operations. Dead-owner
  lock tombstones are non-blocking hygiene observations when DAD can prove the
  owner is gone.
- `dirty_needs_review` or `blocked`: pause collection, routing, and delivery.
  Quarantine malformed/oversized rows by hash and metadata only; wrong-box
  central inbox or repo inbox rows must be re-collected or delivered through the
  governed DAD flow.

Backdated central inbox rows are not trusted just because the packet says it is
old. A pre-enforcement central inbox row is treated as clean legacy evidence
only when a separate allowlist row matches its `mail_id`, `dedupe_key`, and
record hash. For a reviewed migration of old DAD rows:

```powershell
python -m digital_asset_directory.cli mail doctor `
  --repo all `
  --summary-only `
  --allowlist-legacy-central-inbox `
  --legacy-allowlist-ack "reviewed pre-enforcement rows as candidate evidence only"
```

This allowlist does not approve delivery, local adoption, or public release.

Rust rollout packet builds default to ignored staging under
`processed/mail/staged/rust_rollout/`. The tracked
`mail/outbox/rust_rollout/` folder is a reviewed reference snapshot, not the
normal write target for every branch. `rust-rollout build-mail` also runs the
dirty-spool gate; if you are intentionally regenerating staged Rust packets as
part of a reviewed repair, pass `--dirty-state-ack "<reason>"` and the current
`--dirty-state-fingerprint "<fingerprint>"` from `mail storm-gate` or
`mail doctor` so the bypass is tied to the exact reviewed dirty state. If you
intentionally promote the tracked reference snapshot, also pass
`--promote-reference-snapshot-ack "<reason>"`.

Route and deliver:

```powershell
python -m digital_asset_directory.cli mail route
python -m digital_asset_directory.cli mail deliver --repo C:\path\to\target
python -m digital_asset_directory.cli mail deliver --repo all
```

`mail deliver` requires reviewed target policy even for explicit `--repo` paths.
Add the repo to `mail.repos` before delivery so DAD knows the target visibility
and whether it is public-facing.

Release a held private/internal/restricted/unknown-origin packet to a
public-facing target only after human review:

```powershell
python -m digital_asset_directory.cli mail release `
  --mail-id dad:mail:... `
  --decision approve `
  --human-reviewed-by Lowell `
  --notes "Checked provenance, payload, license, and public-safe summary."
```

Review locally:

```powershell
python -m digital_asset_directory.cli mail digest --repo C:\path\to\target
python -m digital_asset_directory.cli mail review `
  --repo C:\path\to\target `
  --mail-id dad:mail:... `
  --decision accept `
  --decided-by human `
  --human-reviewed
```

Review decisions are append-only. Without `--human-reviewed`, a review is agent
triage and does not mark the message handled for local digest purposes. Accepted
mail still requires a normal local change, local tests, preflight/postflight,
and any repo-specific human gates.

Review central-only collected mail in DAD:

```powershell
python -m digital_asset_directory.cli mail central-review `
  --mail-id dad:mail:... `
  --decision accept `
  --decided-by codex
```

`mail central-review` is DAD hub triage for mail that was collected or routed
centrally but not delivered to a repo-local inbox. It writes
`processed/mail/archive/central_review_decisions.jsonl` and does not satisfy
target repo adoption, does not deliver mail, and does not replace
`asset-dir mail release` for public-facing delivery gates.

Triage into adoption tracking:

```powershell
python -m digital_asset_directory.cli mail triage `
  --repo C:\path\to\target `
  --mail-id dad:mail:... `
  --decision save_for_future `
  --importance future `
  --planned-use "Review when this repo next touches test orchestration."
```

`mail triage` writes `.digital-asset/mail/adoption.jsonl`. Future-use and
implement-now records preserve the original mail ID, dedupe key, source asset
refs, return address, and update channel so DAD can later notify only repos
that use or watch an affected asset.

When a repo actually uses, watches, rejects, or retires a DAD asset, record it:

```powershell
python -m digital_asset_directory.cli usage record `
  --repo C:\path\to\target `
  --asset dad:offering:rust-shadow-parity-harness `
  --status watching

python -m digital_asset_directory.cli usage upgrades --repo C:\path\to\target
```

Usage records write a central mirror under `processed/usage/` and, when the repo
is not protected, a repo-local `.digital-asset/dad-usage.jsonl`. Write-protected
Logos repos remain central-only unless a separate explicit local-write approval
is recorded.

## Daily Check Model

DAD runs the central daily collection, routing, and delivery job. Repos do not
collect mail on every preflight.

Preflight only reads `.digital-asset/mail/last_checked.json`. If the digest is
missing, invalid, in the future, or older than 24 hours, preflight surfaces a
stale mail-digest warning. Before material DAD-guided work, read the digest
when this warning appears so new DAD lessons, harnesses, asset updates, and
governance notices are not missed. The fix is to run:

```powershell
python -m digital_asset_directory.cli mail digest --repo C:\path\to\repo
```

## Event Pipeline Direction

Mailboxes are the current safe repo-local edge adapter. They are not intended
to carry every long-term pipeline responsibility by themselves.

The planned direction is:

```text
repo-local event outbox -> DAD read-only collection -> central event log
central event log -> routing and notice generation -> repo mailbox digest
repo response event -> DAD learning, usage, exception, and upgrade ledgers
```

Until the event/data pipeline phase is implemented and reviewed, agents should
keep using mail commands and mailbox JSONL. The pipeline plan is recorded in
`roadmap/evidence/dad-deployment-and-all-repo-verification-roadmap.md` as a
planning gate, not as permission to write new repo-local event files broadly.
Future pipeline work must preserve the same source-authority, provenance,
public-release, and sensitive-payload gates as mail.

## Deduplication

DAD deduplicates by canonical `mail_id` plus `dedupe_key`. On collection, DAD
does not trust hand-written packet IDs. It revalidates the packet, rewrites the
source repo to the actual outbox owner, applies best-effort credential/PII
screening, rejects disallowed sensitivity, downgrades unreviewed source
visibility claims to `unknown`, and recomputes canonical identity. Duplicate
delivery creates an `inbox_ack` archive record instead of a second inbox
suggestion.

## Sensitivity

Mail may carry metadata, paths, summaries, hashes, and review notes. It must not
carry secrets, credentials, raw private rows, copied prompt/code blobs, or large
raw file contents.

Transport rejects `confidential`, `restricted`, and `unknown` sensitivity. DAD
performs best-effort credential/PII screening for common tokens, keys, emails,
phones, SSN-like values, database URLs, and private-key blocks. A screening
count is not proof of safety. Public-facing delivery also rejects unknown payload
keys, long free-form values, table-like rows, and packets that needed screening.
Use public-safe summaries and point to local evidence that the target repo can
review under its own authority.

## Taxonomy Inbox

Existing taxonomy recommendation inbox notes are candidate inputs for
`taxonomy_suggestion` mail. Fold them into mail packets or mail-center docs after
review; do not stage standalone recommendation inbox files as authority unless a
separate governance change approves them.
