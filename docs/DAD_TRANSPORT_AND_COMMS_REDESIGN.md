# DAD Transport & Communications Redesign (Three-Plane Architecture)

Status: reviewed-candidate design kernel (Fable 5, 2026-07-06). High risk tier —
this changes the default communication path for every repo and agent. Nothing in
this doc is implemented until the Codex delegations at the bottom land with
tests. Rollback: current paths keep working; the new data root is config-gated.

## Diagnosis — why today is unsustainable

Measured at review time: **165 data-plane files tracked in the code repo**
(`processed/` 112, `raw/` 45, `audit/` 2, `state/` 2, `lessons/` 4) and **18 of
the last 30 commits are messages/lessons/reports, not code**. Under PR-per-change
governance every mail packet, lesson, and generated report becomes a PR a human
must merge — for N repos in both directions. The human is acting as the
network's packet switch.

The category error: **candidate data is riding the source-authority channel.**
DAD's own law says mail/lessons/events are candidate evidence that never needed
code review; PRs exist to gate source authority. Fixing the transport is
therefore governance-ALIGNED, not governance-weakening.

## How professionals do each function (the borrowed patterns)

| DAD function | Professional pattern | What we copy |
|---|---|---|
| Message delivery | Message broker (Kafka/SQS/NATS): producers append to a central log; consumers PULL with offsets; nobody pushes into a consumer | Hub-and-spoke pull; repo mailboxes become read caches, never commits |
| Bad messages | Dead-letter queues | Already built: quarantine — keep it |
| Message contracts | Schema registry + validation gate instead of human review | Already built: schemas + screens — that IS the mail gate; human merges were redundant |
| Asset catalog | Backstage/DataHub: central catalog CRAWLS sources on schedule; sources never push catalog PRs | Scheduled scan/collect daemon, not inbound PRs |
| Knowledge/learning | SRE postmortems + KCS: search-at-need, capture-while-solving, review only what gets reused | Already designed: hard-issue lookup, lessons; deliver via context pack at preflight, not broadcast |
| Executing lessons in repos | Renovate/Dependabot: bot opens ONE batched, policy-scoped PR per repo only when a concrete code change is needed | PRs are reserved for lesson EXECUTION (real diffs), max one batched PR per repo per cadence |
| State at small scale | SQLite WAL as the local bus (the professional answer at one-machine scale) | Extend the existing CatalogDB |

One-line principle: **code plane (PR-reviewed) ≠ data plane (validated, append-
only, no review) ≠ execution plane (batched bot PRs).** Today all three share
the PR pipe; that is the whole problem.

## Target architecture — three transport tiers

### T0: Local bus (default; covers ~95% of traffic; zero git)
All repos live on one disk, so message passing needs no network and no git.
- New config `DAD_DATA_ROOT` (env / `~/.dad/hub.json` key), default
  `~/.dad/data/`. ALL runtime data moves under it: central mail spools,
  exception lake, event logs, decision traces, usage ledgers, lesson raw store,
  generated reports, SQLite db. The DAD code repo keeps only code, schemas,
  registries, docs, templates (reviewed, low churn — the only things that ever
  deserved PRs).
- SQLite (WAL mode) is the bus for concurrent local agents; JSONL journals stay
  as the append-only audit layer. Repo-local `.digital-asset/**` spools remain
  gitignored edge caches (they already are — verify with the storm-gate doctor).
- Delivery = the hub writing a repo's local inbox cache + the repo pulling at
  preflight (both already implemented). No commits anywhere.

### T1: Batched journal (backup + async remote agents; git WITHOUT PRs)
Git stays useful as a replicated log — the ceremony goes, not the tool.
- A separate private data-only repo `dad-journal` (GitHub free) with **no branch
  protection and direct pushes to main** — data repos don't get code review.
- The daemon checkpoints `DAD_DATA_ROOT` to it on threshold: **≥200 new records
  or ≥24h, whichever first** ("not updated until there is a lot"), one commit,
  `git push`, no PR, no merge, no human.
- Remote/cloud agents (Codex web) read the journal and write their outbox
  packets to a `remote-outbox/` path in it; the local daemon ingests those
  through the normal collect→screen→route pipeline (untrusted-input rules
  unchanged). This removes ALL message PRs immediately with zero new infra.

### T2: Cloudflare relay (later; design-gated by phase-10a-cloud-boundary-reviewed)
Free tier: Workers (100k req/day) + D1 (SQLite at the edge, 5GB) + R2 (10GB).
Note: Cloudflare **Queues is NOT on the free plan** — so the design is a Worker
+ D1 poll relay, not a queue.
- One Worker with a bearer token: `POST /outbox` (remote agent drops packet),
  `GET /inbox/<repo-id>?since=<offset>` (consumer-offset pull). D1 holds the
  relay spool; local daemon syncs relay↔hub on cadence.
- Hard boundary (already DAD law): **public-safe metadata only** — pointers,
  hashes, ids. Private/internal/restricted/unknown-origin payloads never
  transit the relay without a recorded human release.
- Build only when T1 latency actually hurts; T1 is sufficient until then.

### Execution plane (the only PRs that remain)
- Reviewed registry/schema/code changes to DAD itself: normal PRs (unchanged).
- Lesson execution in downstream repos: Renovate-style — when an adopted lesson
  implies a concrete change, the daemon STAGES a batched change-proposal (one
  per repo per cadence max, approval-scoped paths only). Everything else
  arrives as data, not PRs.

### Attention plane (replaces "read every PR")
One daily surface: `daily_review_queue.md` under `DAD_DATA_ROOT/reports/` —
new mail counts, exceptions needing triage, combination/intake review queues,
follow-through gaps, journal checkpoint status. The human reads ONE file (or a
tray notification), merges zero message PRs.

## The daemon ("auto check" + the OS feel)

`asset-dir daemon run-cycle`: collect (mail, events, exceptions) → screen →
route → deliver local caches → follow-through audit → graph rebuild → digests →
daily review queue → journal checkpoint if threshold met. Idempotent, safe to
re-run, logs to the audit journal.

`asset-dir daemon install`: registers a Windows Task Scheduler job (daily, or
2× daily) via `schtasks` + the existing `~/.dad/bin` shim. Later polish, not
prerequisite: PyInstaller single-exe + tray icon. The scheduled task IS the
"OS with executables" — apps come after the pipe is quiet.

## Invariants (unchanged law)

- Mail/events/lessons remain candidate-only; screens and release gates run
  exactly as today — the transport changed, not the trust model.
- Raw stores stay append-only; everything under `DAD_DATA_ROOT` is rebuildable
  or journaled.
- No repo ever writes another repo; hub-and-spoke only.
- Protected repos: central-only, unchanged.
- Public-facing surfaces (T2 especially): human release required for any
  non-public-origin content, unchanged.
- PR governance for CODE is untouched. This design removes PRs from data, not
  review from code.

## Migration plan (phased; each = one Codex delegation)

**M0 — stop the bleeding (config + moves, ~1 day):**
`DAD_DATA_ROOT` config; route all writer paths (mail center, exceptions lake,
events, learning, usage, reports, CatalogDB) through it via one path-resolver
module; one-time migration command copies existing `processed/ raw/ audit/
state/ lessons/` content to the data root, then removes them from git tracking
(`git rm -r --cached`, .gitignore). Keep read-fallback to old paths for one
release. Golden test: full pytest green with `DAD_DATA_ROOT` set to a tmp dir;
`git status` stays clean after a full daemon cycle.

**M1 — daemon (~1 day):** `daemon run-cycle` + `daemon install` + the daily
review queue report. Test: two consecutive cycles are idempotent; cycle with no
new data writes nothing but the heartbeat.

**M2 — journal (~0.5 day):** `dad-journal` private repo; checkpoint command with
the 200-record/24h threshold; remote-outbox ingest through normal collect
screening. Test: threshold batching (199 records → no push; 200 → one commit);
ingest of a hostile remote packet lands in quarantine.

**M3 — Cloudflare relay (LATER, gated):** Worker + D1 per above; requires
phase-10a-cloud-boundary-reviewed human gate first. Do not build in M0–M2.

## What NOT to do (premortem)

- Do NOT turn off PR review for the code repo — the fix is moving data out, not
  weakening code review.
- Do NOT put message data on Cloudflare before the human gate; T1 covers remote
  agents meanwhile.
- Do NOT let OneDrive host `DAD_DATA_ROOT` if avoidable (sync-lock races with
  SQLite WAL); prefer `%USERPROFILE%\.dad\data` outside OneDrive scope.
- Do NOT delete the old tracked data in the migration commit — copy first,
  untrack second, delete only after a verified journal checkpoint exists.
- Worst false confidence: a daemon that silently stops running. The daily review
  queue must carry a "last cycle at" heartbeat, and preflight already warns on
  stale digests — extend that warning to stale daemon heartbeat.

## Codex 5.5 delegations

Severity-ordered; use the delegation JSON template from the 2026-07-06
architecture-kernel packet; global stop conditions apply (no gate approvals, no
target-repo writes, no private data movement).

1. `dad:fable-kernel-delegation:m0-data-root-split` (critical) — path resolver
   module + `DAD_DATA_ROOT` config + migrate command + untrack + gitignore.
   Files: `src/digital_asset_directory/data_root.py` (new), `config.py`,
   `mail_center.py`, `exceptions_lake.py`, `learning.py`, `dad_library.py`,
   `research_intake.py`, `graph_inference.py` (path constants only — no logic
   changes), `tests/test_data_root.py`. Validation: full pytest with tmp
   DAD_DATA_ROOT; `cli validate`; clean `git status` after a daemon cycle.
2. `dad:fable-kernel-delegation:m1-daemon` (high) — `daemon.py` + CLI
   `daemon run-cycle|install|status` + `daily_review_queue` report + heartbeat +
   preflight stale-heartbeat warning. Tests: idempotent double-cycle; heartbeat
   staleness warning.
3. `dad:fable-kernel-delegation:m2-journal` (high) — `journal.py` checkpoint
   (threshold 200/24h), remote-outbox ingest via existing collect screening.
   Tests: threshold batching; hostile-packet quarantine.
4. `dad:fable-kernel-delegation:m3-cloudflare-relay` (deferred/design-only) —
   BLOCKED on phase-10a-cloud-boundary-reviewed. Do not implement.

---

# Implementation Manifest (Fable kernel done; Codex grunt work)

Kernel STATUS: `src/digital_asset_directory/transport.py` + `tests/test_transport.py`
are implemented and golden-tested (5 tests) on branch `fable/transport-kernel`
(commit "Add transport kernel"). Live audit ran 2026-07-06: hub=upgrade_required
(161 tracked data-plane files), 8/10 enrolled repos queued for upgrade,
logos-scripture-graph has spool JSONL tracked in git (protected: central-only
handling). Report: `processed/reports/transport_audit.json`; queue:
`processed/mail/staged/transport-upgrade-queue.jsonl`.

## What Fable solved (do not redesign)

- Fail-safe resolution: uninitialized/typo'd DAD_DATA_ROOT always resolves
  legacy — state can never split across two roots silently.
- Migration ordering: copy -> hash-verify -> marker LAST; never deletes, never
  runs git; emits exact untrack commands for the human.
- Detector signal set + classifications + deduped upgrade queue
  (queue_key = stable_id(repo, surface_version)).
- OneDrive guard on init/migrate.

## Codex delegation M0a — reroute writers through data_path (critical)

Replace direct path constants with `transport.data_path(hub_root, <logical>)`
using EXACTLY the DATA_PLANE_PATHS names (path shapes unchanged; only the root
becomes resolvable). Constants to reroute:

- `mail_center.py`: CENTRAL_MAIL_DIR -> central_mail; REPORTS_DIR -> central_reports
- `dad_library.py`: CENTRAL_USAGE_LEDGER -> usage/...; DECISION_TRACE_LEDGER,
  HARNESS_OUTCOME_LEDGER -> usage/...; HARNESS_REPORT_DIR -> harness_reports;
  REPO_INVENTORY_DIR -> repo_inventory; CADENCE_REPORT_DIR -> cadence
- `learning.py`: LESSON_GRAPH_PATH + manifest -> learning; raw/lessons ->
  raw_lessons; raw/handoffs -> raw_handoffs; audit/events -> audit_events;
  state/agent_sessions -> agent_sessions
- `exceptions_lake.py`: all processed/exceptions + raw/exceptions constants ->
  exceptions / raw_exceptions
- `research_intake.py`: INTAKE_DIR -> research
- `graph_inference.py`: INFERENCE_REPORT_PATH, COMBINATION_QUEUE_PATH -> learning
- `config.py`: database_path gains data-root awareness (state/ under data root)
- `transport.py` audit outputs already use data_path (worked example)

Rule: single mechanical pattern, no logic changes. Full pytest must pass twice:
once with no DAD_DATA_ROOT (legacy mode) and once with a tmp initialized root.

## Codex delegation M0b — CLI + detector v1.1 (high)

- CLI: `asset-dir data init|migrate|status` and `asset-dir transport audit`
  (loads reviewed repos from config like exceptions collect does; never
  discovers repos).
- Detector v1.1 refinement (Fable-found false negative): a repo with a mailbox
  but NO dad-integration.json currently classifies `current`
  (lawfirm-os-intake). Change: mailbox-without-contract =>
  `upgrade_recommended` with signal `contract_missing`. Add a golden test.
- Wire `transport audit` into the daemon cycle (M1) and enrollment weekly checks.

## Codex delegation M1/M2 — daemon + journal (as specified earlier in this doc)

Unchanged; the daemon cycle ends with `transport audit` + journal checkpoint.

## Documents that must change (exact list)

Downstream/templates (repos receive these via enrollment update wave):
1. `templates/downstream/DAD_INTEGRATION.template.json` — add
   `"transport": {"surface_version": "1.0.0", "mode": "local_pull",
   "journal_fallback": true}`; and `schemas/repo-enrollment-contract.schema.json`
   to allow it.
2. `templates/downstream/MAIL_README.md` + `mail_center.mail_readme_text()`
   (keep in sync) — replace PR-transport guidance: spools are gitignored local
   caches; never commit spool JSONL; remote agents use the journal remote-outbox.
3. `templates/downstream/EXCEPTIONS_README.md` — same transport paragraph.

Hub docs:
4. `docs/MAIL_CENTER.md` — transport tiers section; delivery = local cache
   write + repo pull; PRs never carry mail.
5. `docs/DAD_EVENT_PIPELINE.md` — T0/T1/T2 alignment note.
6. `docs/DAD_REPO_ENROLLMENT.md` — transport surface_version in contracts;
   upgrade wave uses the transport-upgrade queue.
7. `docs/DOWNSTREAM_REPO_GOVERNANCE.md` — three-plane rule (PRs = code +
   lesson-execution only).
8. `AGENTS.md` (managed block) + `AI_FRONT_DOOR.md` + `AI_TABLE_OF_CONTENTS.md`
   + `MACHINE_NAVIGATION_MANIFEST.json` + `registry/ai-navigation-registry.json`
   — route to this doc; note DAD_DATA_ROOT in the CLI examples section.
9. `docs/DAD_OS_BUILD_ROADMAP.md` Track H statuses as PRs land;
   `roadmap/roadmap.yaml` phase-13 gates when human-approved.

## Repo upgrade wave (how "marked for upgrade" resolves)

Queue rows -> `enroll update-plan` per repo -> reviewed wave applies the new
contract transport block + README refresh (approved surfaces only). Protected
repos (logos-*): central-only; the tracked spool JSONL inside
logos-scripture-graph needs explicit repo-specific local-write approval before
anyone untracks it — DAD must not fix it silently. Repos that keep using the
old way after the wave keep re-appearing in the audit report (the queue row
dedupes; the report classification does not) — that is the catch mechanism.
