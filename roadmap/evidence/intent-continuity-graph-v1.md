# Intent Continuity Graph V1 Evidence

Status: implementation in progress; recurring activation is not eligible.

## Required outcomes

| Outcome | Acceptance evidence | Current status |
| --- | --- | --- |
| Fresh isolated build surface | Worktree created from verified `origin/main`; dirty main untouched | implemented candidate |
| One lifecycle model | Durable kernel lifecycle retained; overlays separated; stray plan execution state removed | implemented candidate |
| Manual capture-to-archive workflow | CLI and tests for roadmap, resume, evidence acceptance, and separate archive assessment | implemented candidate |
| Ref-aware recovery | Local heads, remote-tracking refs, tags, linked worktrees, detached heads, and dirty-overlay fixtures; no network/write commands | implemented candidate |
| Codex metadata adapter | Strict minimized receipt; no transcript/internal-file access; initialized private-data-root gate | implemented candidate |
| Global/repository projections and queues | Deterministic replay, repo/global graph, live conservative duplicate/closeout inputs, repository-local cockpits, four required action queues plus three supporting queue views, at most three immediate next actions | implemented candidate |
| Silent shadow hooks | Repo-local Codex hook definition, content-free handler, exact retry, privacy, missed-hook reconciliation, latency, rollback tests, and host-readiness assessment | committed candidate; project trust, exact hook trust, linked-worktree discovery, and real dispatch unverified |
| Bounded PM roles | Existing role pack remains 0.4.0; portable PM capability is 0.4.7; evaluated revision IDs remain empty pending real evidence | implemented candidate; promotion prohibited |
| Supervised trial | Five qualifying reviews across at least seven days, measured latency, and zero-failure gates | preflight review recorded one missed capture; qualifying trial not started |
| Progressive activation | Dormant previews plus append-only, revision-bound, predecessor-ordered approve/revoke/kill evidence with expiry, rollback, and kill criteria; no automatic cleanup | implemented candidate; all non-manual stages blocked by current trial evidence |

## Current activation boundary

Only manual commands and the repo-local content-free lifecycle hook are eligible
during this phase. Persistent hook execution still requires Codex review of the
exact hook hash. No session-start summary, digest, breakpoint prompt, scheduler,
notification, Codex archive, worktree removal, branch
deletion, worktree creation, push, merge, or deployment is authorized by this
evidence record.

The exact candidate hook-definition digest is
`sha256:bfb90dcdb1e12c4a83193e4e858b386c30ae13fa02c61264e0dda83befcc38b5`.
This DAD digest binds the exact hook-file bytes; it does not replace Codex's
own trust state or supported `/hooks` review flow.

## Hook activation decision

Risk tier: high. The change affects a persistent lifecycle hook, private
metadata, future-agent defaults, and the evidence used by later activation
gates.

- Chosen bounded option: one trusted-project `.codex/hooks.json` with four
  lifecycle events, a five-second host timeout, a 1.5-second fail-fast ledger
  lock budget, ignored content-bearing inputs, a non-path DAD repository ID,
  private DAD-root writes, silent success/failure, a config-backed runtime kill
  switch, and manual reconciliation. `Stop` means turn completion only and never
  closes the Codex session.
- Rejected option: global hooks, transcript or prompt ingestion, memories,
  notifications, schedulers, model calls, and any cleanup action. It has a much
  larger privacy and authority blast radius and is unnecessary for the trial.
- Downstream surfaces: Codex project hook discovery, the private continuity
  event ledger, rebuildable projections, trial reviews, portability cards, and
  later human activation decisions. Git, tasks, branches, worktrees, and
  external project systems remain outside the write boundary.
- Rollback: delete or disable `.codex/hooks.json`, disable the four lifecycle
  triggers in the reviewed config, retain immutable evidence, and reconcile
  current state from local refs and explicit metadata.
- Kill criteria: prompt/path/transcript/model metadata persistence, visible hook
  output, notification, network/model call, Git/task mutation, semantic retry
  conflict, missing review sample, p95 latency over the reviewed 1,500 ms
  cold-start shadow budget, repeated unchanged
  reminders, false duplicate, false completion, or restore failure.

## Validation snapshot

- 140 focused continuity, roadmap, plan-memory, recovery, and workstream tests
  passed after the final graph-integrity and closeout-freshness repairs.
- 33 global personal-skill registry tests passed.
- Ruff passed on the new and changed continuity modules and tests.
- Portability validation passed with 19 cards and zero findings after rebasing
  over the current upstream MCP, CI-boundary, and ML-research capability cards.
- General `asset-dir validate --hub .` passed 344 checks with zero warnings or
  errors.
- `asset-dir roadmap check --no-update` passed.
- The instrumented repository suite completed in 19m51s with 1,794 passes and
  one navigation-freshness failure. The missing historical paths were restored
  without increasing the 20-entry limit; the affected navigation and
  portability slice then passed 16 tests. The expensive unchanged full suite
  was not repeated after this bounded metadata repair.
- Independent asset review classified this as an internal candidate revision
  of Personal Project Management Ops, not a duplicate skill. It found that the
  Codex-host adapter digest was not derived by the validator; the validator now
  recomputes the digest from the exact normalized repo-local authority file and
  a negative tampering test passes.
- The adapter binding now covers the hook definition, Windows/POSIX command
  entrypoint, silent handler, and Codex bridge as one deterministic revision.
- Production-clock preflight review
  `dad:continuity-review:40ca761102e0cdc300da5fe61f1985ed4aaef4502f879e72465f96a26b1b25eb`
  records one missed capture and zero latency samples after two real Codex CLI
  sessions produced no hook event. It is held under the separate
  `trial:intent-continuity-shadow-v1-preflight` ID and cannot qualify activation.
- Two independent five-sample exact Windows hook measurements after stdin repair
  found p95 values of 837.276 ms and 870.4 ms. Both runs were silent and used
  temporary private data roots; the reviewed cold-start shadow budget is 1,500 ms
  under the five-second host timeout. These measurements are engineering evidence,
  not qualifying trial evidence, until an instrumented receipt is revision-bound.
- Independent architecture review initially deferred persistent trust. It also
  caught and drove repairs for false `Stop`-as-session-close semantics, imports
  outside the silence boundary, double ledger scanning, missing non-path repo
  attribution, and the lock/host timeout collision. Real Desktop-host firing and
  a fresh independent review of the repaired adapter remain required before trust.
- Adapter revision 0.3.0 adds a rebuildable SHA-256-bound command/offset index,
  schema-derived cold replay with full validation retained on append, dead-owner
  stale-lock recovery, content-free failure markers, concurrent process coverage,
  and typed performance/0-1K-10K scale receipts. Trial review now rejects
  free-form latency and requires at least five exact samples bound to the current
  adapter-interface digest.
- Adapter revision 0.3.1 closes independent adversarial findings: cold replay
  enforces the nested receipt payload contract, scale validation requires exact
  size/digest/count outcomes, stale recovery is cross-process serialized with
  owner-token release, and benchmark receipts explicitly disclose their lack of
  cryptographic origin authentication.
- Adapter revision 0.3.2 treats Windows `PermissionError` on an existing
  exclusive lock as ordinary contention while re-raising unrelated permission
  failures, preventing best-effort failure-marker loss under concurrent hooks.
- The final independent exact-hash review found adapter 0.3.2 safe to request
  for repository-only supervised silent-shadow trust. It did not grant trust,
  prove Desktop dispatch, authorize a later activation stage, or weaken any
  kill criterion.
- Adapter revision 0.3.3 adds a schema-validated, read-only host-readiness
  assessment that separately gates project trust, exact hook trust, `/hooks`
  discovery, exact-file hook-definition digest, current adapter-interface
  digest, content-free failure markers, linked-worktree discovery risk, and a
  human attestation bound to one exact current-revision event ID with temporal
  ordering. Eight positive/negative/privacy tests pass. The assessment states
  that ledger origin is not cryptographically authenticated.
  The gate was added after current official Codex source research exposed an
  open linked-worktree project-hook discovery report; absence of a real event
  now fails closed instead of being treated as a trust-only problem.
- PM capability revision 0.4.2 restores append-only compatibility for the
  historical pre-attestation review row. Historical unattested real reviews
  remain readable but fail `supervisor_attestation_missing`; new production
  reviews are rejected before append without explicit attestation. Fourteen
  trial tests, 25 portability tests, and the aggregate activation check passed.
- PM capability revision 0.4.3 exposes the host-readiness assessment through
  the existing continuity CLI without adding an activation or trust-write path.
- Adapter revision 0.3.4 and PM capability revision 0.4.4 bind activation
  eligibility to an explicitly recorded private host-readiness assessment.
  The assessment exposes at most five content-free event references for exact
  human attestation, is append-only and replay-safe, and is rechecked against
  the current repository, hook bytes, adapter revision, and interface digest.
  Reviews before the assessment and stale bindings fail closed; recording does
  not grant trust, activation, cleanup, or archive authority.
- The affected-suite rerun passed all 81 host-readiness, hook, runtime,
  benchmark, trial, portability, and navigation tests in 114.8 seconds. A final
  tightening kept linked-worktree risk open until exact-event attestation; all
  eight host-readiness tests and Ruff passed afterward. Portability validation
  reported zero findings, general validation passed 344 checks with zero
  warnings/errors, roadmap inspection completed, and `git diff --check` passed.
  The unchanged expensive 81-test command is retained as immutable evidence.
- The final gate-link repair passed 31 focused host-readiness, trial, and
  runtime tests plus Ruff. A later three-group parallel pytest attempt timed
  out after 64.1 seconds without preserving per-group output. Its isolated
  benchmark group then confirmed that concurrency was the wrong orchestration:
  the contended warm-10K case reached 1,584.438 ms, above the 1,500 ms budget,
  while the final revision-bound isolated run measured 937.199 ms and passed.
  The failed contended run is retained as negative orchestration evidence; the
  expensive benchmark was not repeated. Final delta validation therefore
  reuses the immutable isolated receipts and runs only changed evidence and
  navigation checks.
- Because the continuity CLI is part of the revision-bound portability control
  plane, its card advanced to 0.1.2 with a freshly computed content digest.
  Repository portability validation then returned 19 cards, zero findings,
  and zero quarantines.
- The live-queue and progressive-readiness continuation advanced the portable
  PM core to 0.4.6, the supervised Codex adapter to 0.3.6, and the portability
  harness card to 0.1.4. Unified recovery now joins local Git/worktree/Codex
  evidence with DAD plans, entities, families, skills, capabilities, and
  workflows; repository cockpits expose local queue/activity/closeout slices;
  trial reviews add missed-recovery, false-duplicate, and unauthorized-mutation
  metrics; and dormant
  attention previews remain explicitly non-deliverable.
- Linked-worktree hub routing is explicit: source validation uses `--hub .`;
  private continuity/trial operations omit `--hub` and use the canonical user
  hub locator. This prevents accidental worktree-local private-store creation.
- Performance and scale receipts are schema-checked, revision-bound, and
  self-consistent local evidence, not cryptographically origin-authenticated
  proof. Every qualifying real review therefore requires supervisor attestation,
  and no receipt can authorize hook trust or activation by itself.
- Revision-bound performance receipt
  `dad:hook-performance:bdf5bdf4cb99e3aeb4868a2db7b40e7080f7fadd307e8049883ceabdc47f8773`
  recorded five exact cold-process Windows samples with p95 687.66 ms under the
  1,500 ms budget; all five were silent, persisted, privacy-safe, and left the
  source worktree unchanged. Evidence:
  `roadmap/evidence/intent-continuity-hook-performance-2026-07-17.json`.
- Revision-bound scale receipt
  `dad:hook-scale:14fc23e66463fca3a1c142879a7b0fbe836e5575ede98220de5dc31e64267d77`
  measured warm 0/1K/10K hook latency at 682.698/656.841/696.77 ms and a cold
  10K index rebuild at 1,972.582 ms. Every case was silent, persisted exactly one
  event, produced a valid size/hash-bound index, recorded zero failure markers,
  remained below its applicable boundary, and left source unchanged. Evidence:
  `roadmap/evidence/intent-continuity-hook-scale-2026-07-17.json`.
- Host-readiness assessment
  `sha256:abf01ad55681ca23afc58b819163dfd3f08032b5956b826282212388664d62aa`
  proves the exact 0.3.7 adapter-interface digest matches, all four intended
  lifecycle events are configured, no current-revision failure marker exists,
  and the repository is a linked worktree. It correctly reports `not_ready`
  because project trust, exact hook trust, `/hooks` discovery, hook-review
  attestation, a current-revision dispatch event, and an exact-event dispatch
  attestation are absent. Evidence:
  `roadmap/evidence/intent-continuity-host-readiness-2026-07-17.json`.
- The continuation focused gate passed 36 trial/runtime tests, 50 host/hook/
  benchmark/adapter/event tests, 25 portability-control tests, and 30 schema
  conformance tests. Repository validation checked 346 contracts with zero warnings/errors;
  portability validation returned 19 cards with zero findings/quarantines;
  Ruff and `git diff --check` passed on the affected surfaces.
- A live unified recovery query for the lost full-stack engineering work
  returned the registered family, skill, and exact durable audit plan in one
  candidate-only result with zero network/model/Git writes. A live continuity
  status rebuild remained non-authorizing, and the post-revision activation
  check correctly stayed `inactive_shadow` with zero reviews and missing
  recorded host readiness.
- The digest-bound `trial-readiness` operator packet now reports the exact
  current host gate, remaining review count, real-clock wait, earliest possible
  eligibility, permanent append-only failures requiring a new trial ID, and the
  next honest human action. It binds the exact review set and current adapter
  digest, rejects path-like identifiers and failure tokens, and carries
  explicit false delivery, activation, cleanup, and execution authorities.
- PM core 0.4.7, supervised Codex adapter 0.3.7, and portability harness 0.1.5
  close the remaining non-human completion gaps. Recovery now searches exact
  private plan source bindings and accepted workstream bindings without
  emitting their raw refs, and a two-repository fixture proves cross-repository
  plan binding edges. Trial-review recording fails before reading supplied
  files or appending unless current recorded host readiness is ready. The new
  private stage-decision ledger binds approvals to stable eligibility evidence,
  the exact adapter interface and predecessor event; expiry, stale bindings,
  revocation, kill, future records, fixtures, and duplicates all fail closed.
  Independent review found and drove three additional repairs: private binding
  match tokens are redacted, append order makes a later kill authoritative
  despite clock rollback, and live status/reconcile consumes the raw stage
  ledger instead of leaving it on a standalone CLI path.
  Its live status contains zero approval records and authorizes no delivery,
  execution, archive, or cleanup effect.
- The final bounded delta passed 123 continuity/recovery/host/hook/trial tests,
  25 portability-control tests, and 30 schema-conformance tests. Portability
  validation returned 19 cards with zero findings/quarantines; repository
  validation checked 348 contracts with zero warnings/errors; roadmap check,
  Ruff, JSON parsing, and `git diff --check` passed. The 65.1-second portability
  slice is retained as immutable same-state evidence and was not redundantly
  repeated.
- The future qualifying production trial has zero reviews and has not started.
- Manual reconciliation rebuilt the canonical private candidate projections
  without touching Git, tasks, or source files; the timestamped pre-commit
  projection fingerprint was
  `sha256:a75d5783a0a55532752b3b2339759d989d19ef93c4a715d92a17a8ba51f9681d`.
  Its immediate same-state live rebuild returned the exact same fingerprint.
  Committing legitimately changes the repository HEAD included in projection
  material, so this revision does not make a self-changing claim about the
  post-commit current fingerprint. A regression test now proves that changing
  only an inventory observation timestamp cannot change the projection
  fingerprint; that volatile field was removed from fingerprint material after
  the completion audit exposed the mismatch.
  Coverage remains explicitly partial because activity-duration and Codex task
  metadata were not supplied.
- The immutable preflight trial currently has one nonqualifying review, span
  zero days, one missed capture, no bound latency sample, and no supervisor
  attestation. It is useful failing evidence but is not part of the future
  qualifying trial.
- The worktree was created from then-current `origin/main` at `dd831017`. The
  candidate branch was subsequently rebased over freshly fetched `origin/main`
  at `da71413` and is four local commits ahead with no upstream commits missing.
  Publication remains a future governed step and is not completion evidence.
- A frozen-revision full-suite attempt reached the 1,004-second command timeout
  without a buffered pytest summary. Current full-suite status is therefore
  unknown; no pass is claimed.

## Reusable learning

Repo-local lifecycle and source-authority contracts must be inventoried before
using an installed/global project-management contract. A similarly named
external contract is candidate guidance, not permission to replace the repo's
reviewed lifecycle vocabulary. The observable correction in this build is one
durable repo-local lifecycle kernel with plan, readiness, delivery, validation,
and closeout represented as separate overlays or gates.

The candidate asset is the 0.4.7 revision of Personal Project Management Ops
plus a separate 0.3.7 supervised Codex-host adapter. It is not a new
idea-library skill.
The linked-worktree routing surprise was captured as a privacy-safe local
exception candidate and resolved in the reviewed documentation and focused
harness. Central exception collection still follows the canonical enrolled
repo path, so the worktree-local candidate is not claimed as a centrally
validated fix outcome.
Hook trust, project trust, configuration discovery, and runtime dispatch are
four different claims. A trusted hash cannot prove discovery in a linked
worktree, and a discovered hook cannot prove successful private persistence.
The reusable correction is to gate on an exact reviewed definition plus one
real current-revision event, while treating upstream bug reports as risk signals
rather than proof about the installed host.
Unknowns remain visible: non-Codex and cross-OS qualification, public licensing,
production adoption, and role-revision evaluation.

## Completion rule

V1 is complete only when every required outcome above has current deterministic
or supervised evidence. Passing implementation tests does not replace the
seven-day trial or Lowell's final activation decisions.
