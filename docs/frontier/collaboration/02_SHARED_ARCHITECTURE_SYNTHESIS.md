# Phase 3 — Shared Architecture Synthesis (Claude ↔ Codex)

Three operating models compared honestly, then the synthesis actually built.
Nothing here defers to either author by default; classifications trace to the
executed evidence in `00_CLAUDE_INDEPENDENT_AUDIT.md` and
`01_CLAUDE_RESPONSE_TO_CODEX.md`.

## 1. The three models

### Model A — Claude's event-ledger/workstream kernel (as found)

One JSONL ledger; pure fold to state; content-derived IDs; TF-IDF relation
classes; rule-tier attention with Today ≤ 3; V1-report join. **Strengths:**
smallest possible moving parts; fold determinism proven by execution;
humane-attention policy (conditional triggers, reasons, per-class accept-rate
decay) is genuinely good. **Weaknesses (executed):** redaction covers one
field; torn tail loses acknowledged events; no lock; no working terminal
transition; identity bugs (capsule/feedback/relation); no bindings; no CLI /
schemas-in-registry / tests. A is a good skeleton wearing unsafe organs.

### Model B — Codex's portfolio graph + attention control plane

Explicit entity set (Project, RepoInstance, Idea, Workstream, SessionRef,
ActivityEvent, ResumeCapsule, AgentRun, Specification) and a rich relation
vocabulary (implements, branch_of, worktree_of, session_for, depends_on,
blocks, overlaps, relates_to, possible_duplicate, contradicts, supersedes,
paused_with, validated_by), flowing capture → retrieve → classify → propose →
approve → *atomic mutation layer later* → capsule → Today ≤ 3. **Strengths:**
the entity/relation vocabulary is the right long-term ontology; bindings as
first-class citizens; urgency/relevance separation; explicit human-approval
step before any workstream becomes real. **Weaknesses:** as specified it is a
*second canonical store* shape (a graph beside a ledger invites divergence —
the research doc itself warns against adding another canonical tracker);
"create branch/worktree/task atomically" smuggles a mutation engine into the
core mental model; nothing in B specifies durability, idempotency, or
redaction mechanics — the exact places A actually failed.

### Model C — the synthesis: chained streams + assertion graph + policy fold

Keep A's single append-only ledger and pure fold. Import B's ontology — but as
**assertion events in the same ledger**, not a second store: relations and
bindings are events with full identity (source, target, type, evidence
revision). Replace A's organs:

1. **Strict event envelope** (registered JSON Schema) validated on read and
   before write; unknown kinds quarantine, not crash.
2. **Per-stream hash-chained identity**: `event_id = H(kind, stream_id,
   payload_canonical, prev_event_id)`. Retry-idempotency without wall-clock;
   genuine repeats (new predecessor) append; tamper-evidence free.
3. **Interprocess lock + single-buffer transactional append**: one lockfile
   (O_CREAT|O_EXCL with stale takeover) around read-check-append; multi-event
   commands serialize to one buffer, one write, one fsync.
4. **Torn-tail quarantine**: on open-for-append, verify the tail; a torn
   fragment is moved to a `.quarantine` sidecar (never deleted) and the ledger
   truncated to the last valid newline **before** appending. Interior corrupt
   lines are counted and quarantined on read, never silently skipped.
5. **Explicit last-event-wins lifecycle state machine** with a legal-transition
   table; terminal states reachable (fixing the dead verbs) and re-openable
   only by explicit `resume`.
6. **Full-field minimization**: every string that will persist passes one
   redaction walker (secrets + emails + SSNs + DB URLs + **local absolute
   paths**) before identity is computed, so IDs never encode unredacted text.
7. **AttentionPolicy** dataclass actually threaded through the fold
   (stale/weekly days, dismissal-decision threshold), replacing dead settings.
8. Relation fixes from evidence: maturity only tips *within* the strong band;
   contradiction/experiment markers count only alongside sufficient overlap;
   within-batch pairwise relations so one conversation's ideas see each other;
   `co_captured_with` context preserved.

Why C over B-native graph store: one durable substrate means one recovery
story, one lock, one audit trail — and the fold can *still* project a graph
view for Codex's control plane later. Why C over A-as-is: every S0/S1 finding
in the audit is a C organ replacement.

## 2. Novel mechanisms (with required disclosures)

### M1 — Per-stream hash-chained event identity

- **Novel:** idempotency keys derived from the *predecessor pointer* rather
  than wall-clock or payload alone; crash-retry dedupes, intentional repeat
  appends. (Chained hashing is old; using the chain as the idempotency
  boundary for human feedback events is the new bit.)
- **State/inputs:** last event id per stream; canonical payload. Fully
  deterministic; no AI.
- **Failure/abuse:** if two *processes* race the same predecessor with
  different payloads, the lock serializes them; the loser recomputes against
  the winner's head and appends (both survive — correct, they were different
  actions). A replayed old request after the head moved becomes a *new* event
  — mitigated by byte-identical-payload dedupe against the whole stream.
- **Applies when:** human/agent feedback and capsule updates on one stream.
- **Does not apply when:** cross-stream batch semantics are needed (capture
  uses per-idea streams plus one conversation event).
- **Danger if misapplied:** treating chain verification failure as data loss
  and "repairing" it automatically; it must only ever quarantine and report.
- **Cheap experiment:** three-command test — same command twice (1 event),
  same command after an interleaved event (2 events). Implemented as tests.

### M2 — Dismissal-to-decision convergence

- **Novel:** repeated dismissal neither decays into priority soup (A) nor
  silently suppresses (implied by the Codex finding); at threshold N the
  kernel emits a **proposed lifecycle decision** ("incubate with review date")
  that must be explicitly accepted or rejected. Dismissals converge to a
  recorded decision.
- **State/inputs:** dismiss count per trigger signature (M3). Deterministic.
- **Failure/abuse:** a user rubber-stamping the proposal is still a recorded,
  reversible choice; threshold too low converts active triage into nagging —
  default N=3, policy-tunable.
- **Applies when:** the same trigger keeps firing on an open workstream.
- **Does not apply when:** interrupt-tier items (blockers/conflicts) — those
  may never auto-convert; a blocker you dismiss five times is still a blocker.
- **Danger if misapplied:** auto-*applying* (not proposing) the transition
  would be silent suppression wearing a suit.
- **Cheap experiment:** N dismissals → queue contains a `decision_proposed`
  item exactly once; accepting silences; rejecting resets the count.

### M3 — Trigger signatures (dismiss the reason, not the work)

- **Novel:** attention items carry `trigger_signature = H(workstream, trigger
  kind, discretized inputs)`; dismissal suppresses that signature only. A new
  *reason* (different trigger kind, or materially changed inputs) surfaces
  fresh. Distinguishes "stop telling me this" from "never mention this work."
- **State/inputs:** trigger kind + inputs from the fold. Deterministic.
- **Failure/abuse:** signature too granular → dismissals never accumulate
  (inputs are discretized: day-buckets, not timestamps); too coarse → new
  reasons suppressed. Bucket boundaries are policy, documented.
- **Applies when:** nudge/weekly tiers. **Not when:** interrupt tier.
- **Danger if misapplied:** hashing raw timestamps into the signature
  reintroduces the wall-clock identity bug (C4) at the attention layer.
- **Cheap experiment:** dismiss idle-nudge; make item blocked; blocker
  surfaces despite prior dismissals. A test.

### M4 — Relationship-class accept-rate decay (retained from A)

Kept as-is conceptually (per-class accepts/dismisses with a floor sample
size), because it is precision feedback, not engagement optimization: it can
only *lower* prominence, never raise it, and it reports its own stats.
Deterministic; abuse mode (one bad week poisons a class) bounded by the
sample floor and full visibility of the stats in the state output.

### M5 — Coverage honesty in the focus report (imported pattern)

Extracted from the DAD-governed conflicts-checker child project
(coverage-not-clearance, generalized): the focus report distinguishes **"no
trigger fired"** from **"could not evaluate"** (unparsable dates, empty token
sets, quarantined events). Silence must be evidence of evaluation, not of
failure. Deterministic; the danger if misapplied is treating a coverage gap
as an attention item itself and re-creating noise — gaps are a report
section, not queue items.

### M6 — Divergence vs. sprawl: the two-question test

- **Novel:** replaces "no relations → healthy divergence" with two explicit,
  separately-reported questions: (1) *Is it connected?* (relation classes) and
  (2) *Is it tended?* (has any of: next action, capsule, binding, recent
  event). Healthy divergence = unconnected but tended, or connected as
  experiment/sibling and tended. Sprawl signal = a growing set of
  sibling/duplicate-linked open workstreams that are untended. Reported as a
  cluster listing with reasons, never as a score.
- **Deterministic**; AI may later *annotate* clusters, never create them.
- **Applies when:** weekly review. **Not when:** items < stale_days old
  (fresh work is allowed to be untended). **Danger:** treating "untended"
  as guilt fuel — it feeds the weekly tier only, capped as ever at 3.
- **Cheap experiment:** fixture with 3 sibling-linked untended workstreams →
  one cluster row; add a capsule to one → it leaves the cluster.

## 3. Child-project sovereignty state machine (owner correction, this session)

DAD is the sovereign portfolio OS; child projects (e.g., LawFirm OS and its
conflicts-checker) are governed through DAD before delivery. The project
plane therefore carries an explicit sovereignty lifecycle:

```
incubating → dad_governed_child → release_candidate → delivery_approved
          → client_sovereign → maintained_upstream | fully_detached
```

Transition semantics (all transitions are human-recorded events, never
inferred): `incubating` (idea/workstream cluster, DAD-internal);
`dad_governed_child` (own repo(s), DAD governs identity/review/gates; child
owns domain facts); `release_candidate` (child's own delivery gates green;
DAD verifies gate evidence exists, does not re-judge domain truth);
`delivery_approved` (named human decision recorded in DAD);
`client_sovereign` (operational governance transfers; DAD retains provenance
history and reusable-pattern extraction rights already logged);
`maintained_upstream` (DAD keeps a maintenance channel) vs. `fully_detached`
(DAD archives its governance records; no further reach-back). Regressions
(e.g., client returns work) re-enter at `dad_governed_child` via a new event,
never by editing history. **V0 scope:** the enum and event kind are reserved
in the envelope schema and documented here; project-plane commands are
deferred — nothing in V0 mutates project sovereignty.

## 4. Agreements, disagreements, strengths, synergies

**Agreements (independent convergence):** single local-first substrate; Today
≤ 3; inactivity alone proves nothing; snooze/incubation suppress; no
engagement optimization; no automatic Git mutation in V0; human approval
before a workstream binds to real resources; explainable reasons everywhere.

**Claude-only strengths kept:** pure-fold determinism (executed proof); the
tier/reason language; per-class accept-rate decay; V1-report join; authority
boundary strings; HTML surface.

**Codex-only strengths adopted:** the entity/relation ontology (bindings,
depends_on/blocks/supersedes vocabulary reserved in schema); urgency vs.
relevance separation (tier vs. relation-strength kept orthogonal); the
finding set itself — 13/16 accepted verbatim with executed repro.

**Synergies (neither had alone):** chain identity (fixes Codex #4/#5 more
safely than either proposal); trigger signatures (resolves the
suppression-vs-nagging tension in #7); assertion-graph-in-ledger (B's
ontology without a second store); sovereignty plane (owner's correction,
formalized).

**Disagreements recorded for Codex's return review:** (1) B's atomic
branch/worktree/task creation should stay out of the kernel *permanently* —
mutation belongs in a separate, separately-gated executor that consumes
kernel proposals; Codex may push back. (2) I kept relation classification
similarity-based + marker-assisted rather than adopting B's full typed
vocabulary as *classifier outputs* — depends_on/blocks/supersedes are
human-asserted binding events in V0, not inferred classes; inferring them
from text would overclaim. (3) Dismissal convergence (M2) replaces both
authors' remedies; evidence requested: a usage week showing whether N=3
converts too eagerly.

**Rejected ideas and reasons:** separate graph database/store (second canon,
divergence risk); permanent silent suppression (violates no-lost-work);
dropping timestamps from event *records* (they stay as data, just not
identity); embeddings for relatedness in V0 (nondeterministic, unneeded at
current corpus size); daemon/background capture (boundary); SQLite for the
ledger (the JSONL + fold is sufficient at this scale and keeps the recovery
story trivial; objective trigger recorded below).

### M7 — Board, dependency, and bottleneck projection (owner request, this session)

- **What it is:** a scrum-style board and critical-path view as *pure
  projections* of the fold — workstreams grouped by lifecycle state, plus a
  dependency rollup over explicit `depends_on`/`blocks` assertions:
  `blocking_count` (open workstreams this one transitively blocks) and
  `blocked_by` (its own unresolved upstream). The workstream with the highest
  transitive blocking count *is* the bottleneck, by construction, with the
  chain shown as the reason.
- **Deterministic/AI boundary:** grouping and graph rollup are deterministic
  kernel code. Subagents may *propose* dependency edges from context and
  narrate the board; a proposed edge becomes real only through a
  human-accepted assertion event. A board that an agent can silently
  repopulate is a second source of truth wearing a costume — rejected.
- **Routines:** a scheduled routine may run `asset-dir os status` plus the
  workstream fold to refresh the board (read + fold + render only). No
  routine, daemon, or scheduled task is created in this pass (mission
  boundary); the commands are routine-safe by design: idempotent, read-only
  outside their own ledger/reports.
- **Failure/abuse:** auto-populating dependencies from co-occurrence would
  manufacture false critical paths — that is why proposal and assertion are
  separated. Danger-if-misapplied: treating `blocking_count` as priority
  authority; it feeds the queue reasons, the human decides.
- **Applies when:** ≥ 2 open workstreams share explicit dependencies.
  **Not when:** dependencies are unasserted — the board then shows lifecycle
  columns only, and says so (M5 coverage honesty).
- **Cheap experiment:** fixture DAG A blocks B blocks C, plus D independent →
  bottleneck = A with chain reason; resolving A (terminal state) recomputes to
  B. Implemented as a test.

### M8 — Trigger architecture: one refresh verb, a ladder of activators

- **What it is:** all workflow/timer/routine questions reduce to one
  idempotent entry point: `asset-dir os refresh` — V1-scan join + kernel fold
  + board/HTML render — whose output states whether **Today changed** since
  the last refresh. Triggers stay dumb (they only decide *when* to call it);
  the kernel stays the only brain; user-facing notification is gated on
  *change*, never on schedule, so a timer cannot become a nag.
- **Activation ladder:** (1) manual, V0; (2) one daily batched routine at a
  fixed time — the repo's own research (three predictable batches/day beat
  continuous notifications) picks this as the first automation; (3) DAD
  SessionStart piggyback showing a one-line Today summary; (4) DAD-home
  event-driven refresh (e.g., after postflight). Git hooks installed into
  child/source repos are **rejected** — that crosses the enrollment boundary.
- **Deterministic/AI boundary:** refresh is fully deterministic. Scrum/PM
  subagents sit *behind* the refreshed state: they may narrate the board,
  propose dependency edges, or draft a weekly review packet — always as
  proposals into the normal assertion/approval flow (M7).
- **Failure/abuse:** a trigger that bypasses refresh and reads the raw ledger
  invites divergence — refresh is the only supported read path for
  automation. Danger-if-misapplied: hourly timers with change-gating disabled
  reproduce the guilt wall; the change gate is not optional.
- **This pass:** no scheduled task, cron, hook edit, or daemon is created
  (mission boundary). Activation of rung 2+ is a named human step after the
  pass.
- **Cheap experiment:** two refreshes with no intervening events → second
  reports `today_changed=false`; append one event that flips a trigger →
  `today_changed=true`. Implemented as a test.

## 5. Chosen V0 boundary

In: modules `portfolio_events.py` (envelope, redaction walker, lock, chain
identity, torn-tail quarantine, transactional append), `portfolio_relations.py`
(classification with the evidence-driven fixes, within-batch relations,
targets), `portfolio_attention.py` (state machine, AttentionPolicy, trigger
signatures, focus fold, M2/M3/M6, dependency rollup M7), reworked
`portfolio_workstreams.py` (command surface + HTML board), declarative
bindings including `depends_on`/`blocks` assertions, event-envelope + state
schemas registered, CLI verbs under `asset-dir os` (capture / capsule /
feedback / bind / workstreams / refresh — refresh is the M8 trigger target
with a `today_changed` output), full test suite, no Git mutation, no network,
no daemon, no scheduled task creation.

Deferred (trigger to reconsider): project-plane sovereignty commands (first
child-project delivery event); mutation executor (named human decision à la
D17); Background Connection Radar join (V0 relations prove useful first);
SQLite projection (fold time > 2s at real ledger size, measured); AI advisory
annotator (after deterministic baseline precision is measured via M4 stats).

## 6. Rollback and kill criteria

Rollback: the kernel is additive — new modules, new schema rows, new CLI
verbs, one reworked untracked module; reverting the branch restores V1
untouched (V1 regression suite must stay green as proof).
Kill criteria for the V0 design itself: (a) chain identity produces any
demonstrated lost-update or duplicate under the concurrency tests — revert to
single-writer lock with monotonic sequence numbers; (b) fold time exceeds 2s
on a year-scale synthetic ledger (10k events) — introduce the SQLite
projection; (c) a redaction walker bypass is found — stop-the-line, no
feature work until the walker covers it; (d) real usage shows Today-cap
starvation (interrupts permanently crowding out weekly items) — add tier
quotas within the cap of 3.
