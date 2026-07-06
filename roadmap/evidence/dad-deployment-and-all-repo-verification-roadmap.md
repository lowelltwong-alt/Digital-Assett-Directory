# DAD Deployment And All-Repo Verification Roadmap

Created: 2026-07-04
Status: roadmap plan, not implementation evidence

## Purpose

This roadmap slice turns the next large DAD goals into ordered phases with
clear acceptance gates. The goal is to prove DAD works as a local-first hub
across repos before any broad enrollment or recurring cross-repo operation is
trusted.

The plan keeps three boundaries:

- DAD recommendations are candidate evidence until reviewed locally.
- Normal recurring DAD writes stay inside repo mailboxes.
- Public, protected, private-origin, and cross-repo actions fail closed until
  the relevant human gate is satisfied.

## Risk Tier

Risk tier: high.

Reason: these phases shape future repo enrollment, cross-repo mail, exception
capture, asset discovery, Rust adoption, and agent preflight behavior. A wrong
default could spam repos, miss important learning, leak private-origin context,
or give agents false confidence that DAD is deployed everywhere.

Chosen approach: staged proof ladder.

Rejected approach: enroll all repos first and debug failures after. That would
mix discovery, writes, mail, protected-repo policy, and agent behavior into one
large failure surface.

Rollback principle: every phase must be useful in read-only mode. Local repo
writes require reviewed policy and explicit phase gates.

## Phase Order

1. Local deployability.
2. All-repo read-only inventory and classification.
3. End-to-end mail trial.
4. Mailbox-backed event/data pipeline design.
5. Exception capture completeness.
6. Rust production slice.
7. Library and card catalog upgrade.
8. Reviewed enrollment waves.

Phase 6 and Phase 7 already exist in `roadmap/roadmap.yaml`; this document
adds the execution plan and adds downstream phases that depend on them.

## Fable Review Checkpoint

Current Fable packet:
`processed/fable5/deep-dives/2026-07-06-dad-deployment-rust-handoff/`.

Use it before making the next high-leverage roadmap or Rust-boundary change if
Fable is available. The packet focuses on Phase 8 deployment false confidence,
roadmap ordering, the Phase 10A Rust event-log checker, and whether DAD's
front-door/TOC registration is coherent enough for future agents.

This packet is review input only. It does not approve human gates, enroll
repos, authorize cross-repo writes, approve public release, or promote Rust to
governance authority.

## Goal 1: DAD Local Deployment

Objective: make DAD callable from any local repo without manual `PYTHONPATH`
knowledge.

Build tasks:

- Provide a local install/bootstrap command or documented script.
- Make `asset-dir` available on PATH or provide a stable wrapper.
- Write `~/.dad/hub.json` with the canonical DAD hub path.
- Make `asset-dir doctor` check hub resolution, PATH/install state, Python
  environment, Rust toolchain availability, and repo-local policy reachability.
- Add a raw-checkout fallback note, but make it the exception rather than the
  normal path.

Acceptance evidence:

- From DAD: `asset-dir doctor` passes.
- From at least two non-DAD repos: `asset-dir doctor` resolves the same hub.
- `asset-dir agent preflight --repo .` works outside DAD.
- Unavailable hub policy is tested: local coding warns, cross-repo writes fail
  closed.

Tests:

- Unit tests for hub resolution order.
- Integration test using temp repos and a temp user-level hub config.
- CLI smoke test for `asset-dir doctor`.

Stop conditions:

- PATH install requires modifying protected or unrelated repo files.
- A public-facing repo would receive a local absolute DAD path by default.
- DAD unavailable would allow cross-repo writes.

## Goal 2: All-Repo Read-Only Test

Objective: prove DAD can see and classify the repo world without writing to
target repos.

Build tasks:

- Reconcile GitHub repo inventory, local Git roots, reviewed policy, and
  existing DAD contracts.
- Classify each repo as `enroll`, `protected-central-only`, `active-no-write`,
  `side-project`, `archive-ignore`, `duplicate-ignore`, or
  `needs-human-classification`.
- Preserve stable repo IDs across rename/copy where policy can prove lineage.
- Produce a central report with local path redaction rules for public-facing
  entries.

Acceptance evidence:

- A read-only report covers every GitHub-visible repo and local persistent repo.
- Logos Scripture Graph and Logos Governance remain protected-central-only
  unless separately approved.
- Mock Trial/Albert is classified as active but not extra-protected.
- Duplicate clones, archives, temp worktrees, and pytest workspaces are not
  enrolled by default.

Tests:

- Synthetic inventory with duplicate basenames, renamed repos, copied repos,
  nested clones, and archived folders.
- Public-facing report redacts local absolute paths unless explicitly approved.

Stop conditions:

- Discovery attempts local writes.
- Bare repo names are ambiguous.
- A dirty active worktree would be enrolled by default.

## Goal 3: End-To-End Mail System Trial

Objective: prove outbox, central DAD collection, routing, dedupe, delivery,
digest, and review work on real and synthetic repos.

Build tasks:

- Create a two-temp-repo integration harness.
- Send lesson, asset, workflow, governance, and exception-adjacent mail from
  repo A to DAD.
- Route only to policy-approved repo B.
- Deliver only to `.digital-asset/mail/**`.
- Convert duplicate deliveries into acknowledgements.
- Prove private/internal/unknown origin to public-facing target is quarantined
  until human release.

Acceptance evidence:

- Repo A outbox mail is collected once.
- DAD central inbox/outbox/archive records provenance and return address.
- Repo B receives candidate mail and digest can read it.
- Duplicate delivery does not spam the target inbox.
- Public release gate blocks private-origin public-target delivery.

Tests:

- JSONL malformed-line tolerance.
- Dedupe by `mail_id` and `dedupe_key`.
- Same-basename target collision holds centrally.
- Human release approval/rejection paths.

Stop conditions:

- Mail packet contains secrets, raw private rows, long blobs, or prompt-injection
  payloads.
- Delivery path escapes `.digital-asset/mail/**`.
- Agent triage is treated as human release.

## Goal 3A: Mailbox-Backed Event/Data Pipeline

Objective: keep repo-local mailboxes as the safe edge adapter, but move DAD's
source-of-truth communication model toward a real append-only event/data
pipeline. The pipeline should make repo learning-loop responses deterministic
instead of depending on a human noticing a chat signal.

Observed communication issues from current DAD work:

- Mail JSONL is doing too many jobs at once: transport, queue, audit ledger,
  delivery state, human-readable inbox, and response tracking.
- Cross-repo writes are brittle under Windows, OneDrive, sandboxing, stale
  locks, and active-worktree protection.
- Some repos emit no DAD packet unless the user notices the pattern in chat and
  asks the repo to write mail.
- A repo can receive a suggestion but never deterministically record whether it
  implemented, saved, rejected, or escalated it.
- Bulky command output can fail or time out even when the underlying report was
  generated correctly.
- Generated reports drift when source code or methodology hashes change, so DAD
  needs dependency-aware refresh paths instead of manual report chasing.

Build tasks:

- Define a repo-local event outbox alongside mail:
  `.digital-asset/events/outbox.jsonl`.
- Define central append-only event storage:
  `processed/events/event_log.jsonl`, `processed/events/quarantine/`, and
  `processed/events/reports/`.
- Treat mail as a presentation and delivery edge, not the canonical state
  machine. Mail digest remains how repo agents see notices; event records become
  how DAD tracks source, provenance, dedupe, response, and learning outcomes.
- Add event types for `lesson_found`, `exception_seen`, `fix_outcome`,
  `asset_used`, `asset_rejected`, `harness_needed`, `dad_notice_ack`,
  `dad_notice_saved_for_future`, `dad_notice_implemented`,
  `dad_notice_rejected`, `governance_drift`, and `pipeline_health`.
- Add a deterministic response contract: every actionable DAD notice must
  eventually receive `acknowledged`, `saved_for_future`, `implementing`,
  `implemented`, `rejected`, `deferred`, or `needs_human_review`.
- Add dependency-aware report refresh metadata so validation can tell which
  reports need regeneration and which command owns each report.
- Keep local-first as the default. A future Cloudflare deployment may mirror
  public-safe metadata only after explicit human review.
- Evaluate Rust leaf tools for event JSONL validation, dedupe scanning, path
  hashing, provenance checks, and dependency-graph freshness checks.

Local-first architecture:

```text
repo event outbox -> DAD read-only collector -> central event log
central event log -> router -> repo mail digest / repo action queue
repo response event -> DAD collector -> usage, lesson, exception, and upgrade ledgers
```

Cloudflare-compatible architecture, deferred until local gates pass:

```text
Worker API -> Queue -> validator/router Worker -> D1 metadata
                                             -> R2 audit artifacts
                                             -> Durable Object per repo/stream for leases
```

Cloudflare boundaries:

- Workers may host public-safe APIs and webhook-style ingestion later.
- Queues are suitable for async routing and retry, but at-least-once delivery
  means every event handler must be idempotent.
- D1 is suitable for event metadata, repo states, notice states, and
  acknowledgements, not large raw payloads.
- R2 is suitable for larger audit artifacts and report snapshots.
- Durable Objects are suitable for per-repo locks, leases, cursors, and live
  coordination, but should not become a single global bottleneck.
- Private/internal/restricted/unknown-origin payloads stay local unless a human
  release explicitly approves public-safe movement.

Acceptance evidence:

- A temp repo can emit event records without DAD writing into source code.
- DAD can collect events read-only, validate them, dedupe them, quarantine bad
  rows, and route actionable notices to mailbox digest.
- A repo response event updates DAD's central usage/learning state without
  rewriting source authority.
- Every routed actionable notice has a response-state row or a stale-response
  warning.
- Private-origin to public-facing movement is held until human release.
- Pipeline status can explain whether failures are transport, validation,
  delivery, response, or report-refresh failures.

Tests:

- JSONL line-by-line tolerant parse and malformed-row quarantine.
- Idempotent event ingestion by stable event id and dedupe key.
- Response-state transitions and duplicate response handling.
- Synthetic "repo should have emitted this" cases across lessons, exceptions,
  assets, harnesses, skills, templates, workflows, governance, and data maps.
- Pattern-update simulation proves new required event fields reach repo
  outboxes or capture suggestions.
- Rust event scanner/checker parity tests against the Python validator before
  Rust promotion.
- Cloudflare design remains planning-only until local pipeline gates are green.

Stop conditions:

- Pipeline events carry secrets, private rows, hidden reasoning, long logs, or
  raw case content.
- A cloud mirror is treated as authoritative for private/local repo state.
- Event response status is inferred from absence of mail rather than explicit
  repo response events.
- Rust scanner output makes governance decisions instead of returning bounded
  observations for Python/DAD policy to review.

## Goal 4: Exception Capture Completeness

Objective: prove repos emit the right DAD mail or exception packets without the
user rescuing the signal from chat.

Build tasks:

- Expand the synthetic capture harness across asset types and exception types.
- Use the LawFirm-os-intake missed capture as a golden regression.
- Simulate pattern updates and prove enrolled repos learn the new packet fields.
- Backfill observed real repos read-only and distinguish legacy misses from
  current-surface failures.

Acceptance evidence:

- Synthetic DAD-worthy events produce expected mail or exception packets.
- Synthetic non-events do not produce noisy packets.
- Pattern update simulation causes changed expected fields to appear in repo
  outboxes or capture suggestions.
- Observed-audit gaps are triaged into legacy miss, current miss, protected
  central-only, or policy-blocked.
- `processed/reports/phase6_exception_capture_machine_evidence_summary.json`
  compiles capture, emission-simulation, taxonomy, and observed-audit reports so
  green synthetic evidence cannot hide a red observed-audit gate.
- Mail-storm diagnostics identify wrong-box inbox writes as blockers and keep
  Rust rollout packet churn separate from ordinary worktree dirt.

Tests:

- Positive and negative synthetic packet emission tests.
- Pattern-update migration tests.
- Sensitive payload quarantine tests.
- Capture surface version compatibility tests.
- Stale combined-summary validation after any Phase 6 source report changes.
- Mail storm delivery-policy holds for write-protected or delivery-disallowed
  repos.
- Rust rollout packet output path gate for other-repo mailboxes and source
  trees.

Stop conditions:

- A capture suggestion requires raw private content to be useful.
- Current-surface misses are normalized as acceptable legacy misses.
- Generated reports imply human gates are satisfied.

## Goal 5: Rust Production Slice

Objective: use Rust for a real DAD job where it is appropriate, and collect
lessons from actual use.

Build tasks:

- Keep Rust as a deterministic leaf worker, not a governance owner.
- Run `tools/dad_scan_core` through the Python bridge in a normal DAD workflow.
- Measure runtime and correctness against the Python path where comparable.
- Record Rust lessons and bridge outcomes in DAD.
- Promote Rust only for bounded scanning, hashing, walking, parsing, or
  compute-heavy deterministic steps with evidence.

Acceptance evidence:

- Rust scan output is consumed by a DAD workflow.
- Rust output contains alias-only paths and no local absolute path leakage.
- Rust default excludes block credentials and DAD control/evidence surfaces.
- Python wrapper validates JSONL and summary/quarantine outputs.
- Timing claims are gated behind correctness/parity evidence.

Tests:

- Cargo fmt/check/test/clippy.
- Python bridge tests.
- Scan output schema tests.
- Sensitive/default exclude tests.
- Bounded scan determinism tests.

Stop conditions:

- Rust is proposed before profiling or correctness evidence.
- Rust output hashes private or sensitive files by default.
- Rust becomes the source of governance decisions.

## Goal 6: Library And Card Catalog Upgrade

Objective: make DAD offerings easy for agents to find and use through compact
context packs, not scavenger hunts.

Build tasks:

- Normalize DAD offerings, needs, skills, harnesses, templates, architecture
  references, governance maps, data maps, and Rust assets.
- Add route-quality checks for AI front door, TOC, machine manifest, and
  offering registry entries.
- Ensure every important offering has `use_when`, `do_not_use_when`,
  validation, owner authority, update channel, and adoption record semantics.
- Keep generated graph and match outputs as candidate evidence.

Acceptance evidence:

- `asset-dir dad offerings` and `agent preflight` surface the right top assets
  for sample tasks.
- Important DAD systems have exact routes in AI front door and TOC.
- Offering records point to harness registry entries instead of duplicating
  large records.
- Usage ledger can say which repos use or watch a DAD asset.

Tests:

- Golden task-to-offering cases.
- TOC/front-door route tests.
- Schema validation for offerings and usage records.
- Regression that public-facing references do not expose private local paths.

Stop conditions:

- Preflight output becomes too large to act on.
- A generated match score is treated as proof of value.
- An offering lacks authority boundary or update path.

## Goal 7: Reviewed Enrollment Waves

Objective: enroll approved persistent repos only after local deployability,
read-only inventory, mail trial, exception capture, Rust slice, and catalog
routes are proven.

Build tasks:

- Create reviewed waves from the read-only inventory.
- Apply enrollment only to repos in policy with approval IDs.
- Install full governance footprint only during enrollment/update apply.
- Keep normal recurring DAD operation mailbox-only.
- Record repo-local usage, asset pointers, context map, governance map, data
  map, and skill checkout pointers.

Acceptance evidence:

- Wave plans list exact repos, protections, dirty-worktree status, branch, and
  allowed write paths.
- Apply writes only approved managed surfaces.
- Daily mail and weekly asset/skill/template checks are wired.
- Protected repos remain central-only unless specifically approved.
- Renamed/copied repo lineage is preserved by stable repo ID.

Tests:

- Temp repo enrollment apply/update idempotence.
- Dirty/non-main block behavior.
- Protected repo write-block behavior.
- Public repo local-path redaction.
- Daily mail writes only mailbox files.
- Weekly update notice budgets prevent inbox spam.

Stop conditions:

- A discovered repo is enrolled without reviewed policy.
- Enrollment touches source code or governance outside approved surfaces.
- Protected Logos repos receive local writes without explicit approval.

## Red Team And Premortem

Likely failure story: DAD gets installed broadly before read-only proof is
solid. Repo names collide, a dirty active repo receives stale mail, generated
reports imply capture completeness, and a private-origin note reaches a
public-facing repo because target visibility was guessed. Agents then trust
preflight because DAD "knows all repos," even though the deployment was never
validated end-to-end.

Controls:

- Prove local deployment before enrollment.
- Prove inventory read-only before writes.
- Prove mail in temp repos before real repos.
- Prove exception capture with synthetic pattern updates before claiming
  learning completeness.
- Prove Rust on one production slice before broad Rust promotion.
- Prove catalog routes with golden tasks before depending on preflight.
- Enroll in reviewed waves only.

## Validation Plan

Minimum validation while this plan is only roadmap evidence:

```text
python -m digital_asset_directory.cli roadmap check --no-update
python -m digital_asset_directory.cli validate
```

Implementation phases add their own focused tests before they can advance from
planned to active or complete.
