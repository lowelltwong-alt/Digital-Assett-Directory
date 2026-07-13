# Phase 1 — Claude Independent Audit of the Partial Portfolio OS Kernel

Auditor: Claude Opus 4.8 (this collaboration session). Subject:
`src/digital_asset_directory/portfolio_workstreams.py` (untracked, 1331 lines),
`schemas/portfolio-workstream-state.schema.json` (untracked), against
`portfolio_os.py` (Attention V1, tracked) and the plan/research docs.

Method: code reading plus **executed synthetic checks** (scratchpad scripts;
key excerpts reproduced under each finding). No reliance on the module's
docstring claims or the prior model's completion report.

Honesty note: the collaboration prompt embedded Codex's finding list, so a
literally blind audit was impossible. Every finding below was nevertheless
reproduced (or refuted) by running code in a temp hub before being accepted,
and several findings in §3 are additions Codex did not list.

## 1. Verdict in one paragraph

The kernel's *shape* is right and worth keeping: an append-only JSONL ledger,
a pure fold to state, content-derived IDs, explainable deterministic relation
classification, tiered attention with a hard Today cap of 3, and a real
build-on-V1 join. But the implementation has one severe privacy defect
(redaction applied to idea text only), one severe durability defect (a torn
tail silently swallows the next acknowledged append), one dead feature
(terminal lifecycle transitions never fire), and a cluster of identity bugs
(capsule identity drops `last_check`; feedback identity includes wall-clock;
relation identity omits the source). The lifecycle fold is order-aware but not
last-event-wins. None of this requires abandoning the architecture; it
requires a strict event envelope, a lock + transactional append, full-field
minimization, and a real state machine. Roughly: right skeleton, unsafe
organs.

## 2. Findings with executed evidence

Severity: S0 = data loss/leak, S1 = wrong core behavior, S2 = quality/design
debt. Every item was reproduced in a fresh temp hub (fold time pinned).

| # | Sev | Finding | Executed evidence |
|---|---|---|---|
| C1 | S0 | **Redaction covers idea text only.** `conversation_title`, capsule `pause_reason`/`blocker`/`last_check`/`next_action`, feedback `note`, and provenance fields persist verbatim. | Captured with `api_key=sk-aaaa…` in title, capsule fields, and note → 6 raw occurrences in `workstream_events.jsonl`. Also: `redact_sensitive_text` covers secrets/emails/SSN/DB-URLs but **not local absolute paths**, which V1 explicitly treats as private (`public_safe=false`). |
| C2 | S0 | **Torn-tail append swallows an acknowledged event.** `_read_events` tolerates a corrupt line, but `_append_events` happily concatenates the next event onto a no-newline fragment. | Torn fragment + capture → API returns `events_appended=2`; re-read shows the `idea_captured` event gone (merged into the corrupt line), fold = 1 idea / 2 workstreams (orphan). Report claims success while the ledger lost the record. |
| C3 | S0 | **No interprocess lock; idea+workstream pair not transactional.** Read-check-append race between processes; two events written via one buffered handle can tear, and there is no repair/quarantine. | Truncating the pair after the idea event → fold silently accepts an orphan idea (1 idea, 0 workstreams), no diagnostic. Concurrent-writer interleaving is unguarded by construction (no lock anywhere in the module). |
| C4 | S1 | **Feedback is not idempotent.** `event_id = stable_id(ws, action, recorded_at)` — wall-clock participates in identity, so a retry is a new event and `dismiss_count` inflates. | Same logical dismiss at T and T+1s → 2 events, `dismiss_count=2`. |
| C5 | S1 | **Capsule identity omits `last_check`.** Updating only `last_check` yields the same `capsule_id` → same `event_id` → append skipped. | Second capsule with new `last_check` → `events_appended=0`, folded value still the old one. A "tests now FAIL" check-in is silently discarded. |
| C6 | S1 | **Lifecycle is not last-event-wins.** Any `resume` anywhere clears snooze forever: `snoozed` requires `not resumed_after` regardless of order. | resume@day1 then snooze@day2 (10 days) → state `active`; the later snooze is ignored and the item can nag. |
| C7 | S1 | **Terminal transitions never fire.** `if action in TERMINAL_STATES:` compares feedback *verbs* (`merge`,`supersede`,`archive`) against past-tense *states* (`merged`,…) — always false; the mapping dict below it is dead code. | `archive` feedback → lifecycle stays `proposed`. There is no working way to close a workstream at all. Sharper than "may not align": it is a dead branch. |
| C8 | S1 | **Relation identity collides.** `relation_id = stable_id(kind, target_id, type)` omits the source idea/workstream and any evidence revision. | Two different ideas → byte-identical `relation_id` against the same target. |
| C9 | S1 | **`mature` promotes weak overlap to continuation.** Every V1 project is `mature=True`, and `mature` alone forces `continuation` for any relation ≥ floor. | Idea sharing only `invoice, export` with a V1 project → score 0.24, confidence `low`, yet `continuation` → proposal `resume_existing` ("Resume and extend 'billing-sim'"). Wrong advice class from two common words. |
| C10 | S1 | **Co-captured ideas are invisible to each other.** Targets come from pre-existing state with the current pass excluded, so a two-idea conversation produces zero mutual relations. | Two near-identical ideas in one capture → `relations=[0, 0]`. The connective tissue the plan demands ("preserve the conversation relationships") only exists as a shared `conversation_id`. |
| C11 | S1 | **Solo capture is non-idempotent.** Default `conversation_id` embeds `recorded_at`, so retrying the same idea duplicates it. | Identical text captured twice without a conversation id → 2 ideas. |
| C12 | S2 | **Dismissal never suppresses.** Penalty capped at 30 with floor 1, so an 8×-dismissed item still sits in the focus queue (priority 30 in my run — the cap keeps it *above* trivial items) forever. | 8 dismissals → still in queue, tier `weekly`. Hysteresis exists; terminal suppression does not. |
| C13 | S2 | **Contradiction markers are common English words.** `without`, `drop`, `kill` as bare tokens force `contradiction` → `needs_human_decision` → priority-85 interrupt. | "auth service **without** password rotation support" vs prior rotation idea → flagged conflict interrupt at score 0.50. False interrupts are the exact guilt-wall the plan forbids. |
| C14 | S2 | `CaptureSettings.stale_days` validated, never read (grep: 3 hits, all declaration/validation). Focus logic uses module constant. | — |
| C15 | S2 | Schema exists but is **unregistered** (no hit in `registry/*.json`, `tests/test_schema_conformance.py`); there is **no event-envelope schema** at all — ledger rows are unvalidated dicts (any dict with an `event_id` folds). | grep evidence; `_read_events` accepts any keyed dict. |
| C16 | S2 | Ruff: `F401 dataclasses.field imported but unused`. | `python -m ruff check …` fails. |
| C17 | S2 | **No CLI, no kernel tests, no evidence file.** `cli.py` has no capture/capsule/feedback verbs; `tests/` has zero references to `portfolio_workstreams`. The docstring cites `docs/frontier/OPUS_4_8_PORTFOLIO_OS_ARCHITECTURE.md`, which does not exist. | grep evidence; `docs/frontier/` contains only the prompt. |

Positives confirmed by execution: fold determinism holds (byte-identical
state for same events+now); same-conversation recapture is genuinely
idempotent; Today cap of 3 enforced; HTML output escapes idea text; the V1
join reads the report instead of re-scanning Git; no Git mutation anywhere in
the module (verified by reading every subprocess/os call — there are none
beyond fsync/mkdir).

## 3. Evaluation against the required axes

- **Creative-sprawl model.** The five relationship classes and six proposal
  kinds are a reasonable, human-legible vocabulary. But divergence handling is
  thin: "no relations → healthy divergence" conflates *unrelated* with
  *unmeasurable* (empty token set → no relations → "healthy"), and the
  experiment/contradiction detection rests on single-word markers (C13).
- **Idea/workstream identity.** Content-derived (good), but conversation-id
  participates in idea identity, so the same idea in two chats is two ideas
  with no dedupe path (defensible only if relations then link them — they do,
  via `duplicate`, when text survives thresholds). Solo capture breaks
  identity outright (C11).
- **Relationship classification.** Deterministic, explainable, cheap — right
  boundary (no model call). Thresholds are unvalidated magic numbers; marker
  lists overreach (C13); mature-promotion overclaims (C9); relation identity
  collides (C8); no `depends_on`/`blocks`/`supersedes` — the vocabulary is
  similarity-only, weaker than the plan's relationship set.
- **Append-only/event-sourcing correctness.** Fold is pure and deterministic
  (verified), but ordering uses `(recorded_at, ordered.index(event))` — an
  O(n²) list scan comparing dict equality; capsules are last-write-wins by
  `recorded_at` string without sequence tiebreak across processes.
- **Concurrency/crash recovery.** C2/C3. No lock, no tail repair, no
  quarantine, no pair atomicity. `_append_events` fsyncs, which is necessary
  but not sufficient.
- **Idempotency.** Capture yes; capsule accidentally over-idempotent (C5);
  feedback not idempotent (C4); solo capture not idempotent (C11).
- **Privacy/redaction.** C1 is disqualifying for a ledger whose whole point is
  "safe to persist". Also no path redaction, and `provenance.captured_by` is
  free text.
- **Lifecycle ordering.** C6/C7. Not a state machine — a pile of flag scans.
  `paused` is unreachable as an explicit choice distinct from capsule
  side-effects; `proposed → active` happens implicitly when a capsule has a
  `next_action`, which surprises.
- **Snooze/incubation/hysteresis.** Snooze and incubation suppress correctly
  when they apply (verified in fold), but C6 breaks re-snooze, and dismissal
  decay has no terminal suppression (C12).
- **Attention ranking.** Tiering (interrupt/nudge/weekly) matches the plan's
  conditional-attention rules and reasons are human-readable — genuinely good.
  Priorities are unexplained magic integers (90/85/70/60), which the
  `calculated-score-requires-methodology` learning rule flags: they need a
  documented ordering rationale even if they stay heuristic.
- **Source-authority boundaries.** Good. `AUTHORITY_BOUNDARY` string on every
  output, no Git mutation, reports under the data plane, `public_safe=false`.
- **V1 compatibility.** The join consumes the V1 report shape correctly
  (`projects[].branches[].name/subject` — verified against `portfolio_os.py`
  output construction). One-way only; V1 knows nothing of workstreams, which
  is fine for V0.
- **Missing machinery.** CLI, event schema, registration, tests, evidence file,
  architecture doc it cites (C15/C17).
- **Novel or renamed-conventional?** Honest answer: the machinery is
  conventional (event sourcing + TF-IDF similarity + rule tiers). The genuinely
  distinctive parts are the *policy* choices: conditional attention instead of
  age-based staleness, needs-human-decision as a first-class proposal kind,
  accept-rate decay per relationship class (an unusual, good idea — precision
  feedback without engagement optimization), and the Today-cap contract. Call
  it: conventional mechanics, novel humane-attention policy. That is not a
  criticism; it is where the value actually lives.

## 4. What must not be lost in any rewrite

1. Pure fold over an append-only ledger with content-derived IDs.
2. The tier vocabulary and reason strings (they read like a colleague).
3. Relationship-class accept-rate decay (bounded, transparent, per-class).
4. The V1-report join (build-on, don't re-scan).
5. The authority-boundary string and `public_safe=false` posture.
6. Today ≤ 3, with suppressed items counted, not hidden.
