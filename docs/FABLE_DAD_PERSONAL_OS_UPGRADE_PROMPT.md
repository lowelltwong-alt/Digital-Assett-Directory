# Fable Handoff — DAD Personal Operating System Upgrade

Use: manually copy the prompt below into Fable. Do not attach repositories,
private conversations, client material, secrets, absolute paths, or unpublished
source rows. Fable's response is advisory and must return to DAD for
reconciliation, independent review, and Lowell's decision.

Agreed ends (Lowell, 2026-07-23): DAD graduates from a batch CLI into a live
personal AI operating system on one Windows laptop — booted like a program
when the operator sits down to work (always-on service optional, not
required) — the memory,
governance, and coordination substrate every agent runtime plugs into — with
state tri-replicated (live laptop, secondary local drive mirror, governed
surfaces on GitHub). It must be AI-first and work seamlessly, day one, from
inside Claude Code, Codex, and Cursor: the same preflight, memory, lifecycle,
and cockpit surfaces reachable from each runtime with zero per-session setup,
no runtime privileged over the others. Delivery tempo: the fully functional cockpit AND fully
functional learning loops (T0–T2 active, T3 proposal-only, T4/T5 dormant) ship
**as soon as safely possible — not staged out over a year**. The 6-month /
1-year / 3-year horizons below are NOT delivery phases; they are projections
of where frontier AI capability will be, used to build DAD ready *in advance*
for what is coming: ~6 months = multi-day agent runs common, live tiered
memory table stakes; ~1 year = week-long autonomous tasks at usable
reliability, skill libraries self-maintaining; ~3 years = month-horizon
agents, where the winner is whoever already owns a governed personal
substrate that makes that autonomy safe and cumulative.

---

## Prompt for Fable

You are the independent frontier architecture reviewer for the **DAD Personal
OS Upgrade**: the plan to turn a mature, governed, local-first digital-asset
and learning hub into a live personal AI operating system for a one-person
technical portfolio. The operator has a separate full-time job; the system must
be quiet, cheap, comprehensible, reversible, and reviewable in under ten
minutes on a normal day. Do not assume the plan below is right. Reconstruct
the architecture you would build, compare, and state your strongest
disagreement first.

Budget: keep the response under 14,000 output tokens. Compact tables and exact
changes beat prose.

### The operator (design for this person, not an idealized one)

- Thinks in **stream of consciousness**: ideas arrive fast, mid-task, and
  branch; capture must cost one sentence or it is lost.
- Naturally accumulates **many started products, chats, branches, and dirty
  worktrees** (last live scan: ~31 canonical repos, 211 branches, 121 linked
  worktrees, 27 dirty). This is the operator's creative style, not a defect
  to train away; the system absorbs the entropy.
- **No prior software-development experience.** The system must supply the
  missing engineering judgment automatically: translate Git states, test
  results, and hygiene debt into plain language; propose the next safe action
  as a one-click/one-command decision; never require the operator to know
  what a rebase, lockfile, or CI matrix is to stay safe.
- Has a separate full-time job; attention is the scarcest resource in the
  whole design. Existing DAD rules already encode this (Today ≤ 3, never nag
  paused work, interrupt only on conflict/failure/blocked) — the upgrade must
  make that help **automatic** (fire on session boot and on material change),
  not something the operator remembers to run.

### The DAD repo family (context, do not request contents)

One hub plus satellites: the **hub repo** (catalog, governance, portfolio-OS
kernel, this plan); a **private data-only journal repo** (checkpoint/
replication log); a **user-level plane** outside any repo (CLI shim, data
root, hub locator, control mirrors); a 7-repo **LawFirm OS child family**
governed by DAD (including an orchestrator repo that is prior art for any
layer-4 orchestration); a 5-repo **Logos family** behind a strict read-only
boundary DAD may never write; and further enrolled children. The upgrade must
strengthen the hub-and-satellite shape, not flatten it.

### What exists today (condensed, all real and tested)

- **Asset substrate**: local + GitHub scanners; stable asset identity separate
  from revision identity; SHA-256/chunk-hash/text/embedding similarity ladder;
  SQLite catalog; JSONL + graph exports; staleness/orphan/dormant/synergy
  radars; append-only lessons, handoffs, audit events.
- **Governance**: agent-agnostic AGENTS.md contract; preflight/midflight/
  postflight lifecycle with session ledger and Git-hook enforcement; reviewed
  enrollment waves with approval IDs, marker-bounded managed surfaces, cancel/
  unenroll/rollback lifecycle; human gates everywhere; append-only audit.
- **Portfolio OS layer (read-only projections)**: event-sourced workstream
  kernel (Idea → Workstream → SessionRef → ActivityEvent → ResumeCapsule);
  Git-wide attention scan (31 repos, 211 branches, 121 worktrees at last
  validation); unified cockpit HTML with Today capped at three; conditional
  attention rules (interrupt only on conflict/failure/blocked; never nag
  paused work); proposal-only reconciliation; recovery-decision control plane.
- **Learning design (mostly dormant)**: a reviewed self-improvement plan with
  a T0–T5 state-change taxonomy (T0 test-time compute … T5 architecture);
  overlay owns T0–T2, proposes T3; T4/T5 dormant by design; abstract
  Luna/Terra/Sol capability tiers instead of vendor model IDs; frozen
  evaluators, inaccessible holdouts, anti-gaming review, expiring activation
  leases; a weekly metadata-first research funnel design (arXiv/OpenReview/
  Crossref cursors, dedupe, ≤40 Luna abstracts, ≤6 Terra papers, ≤3 human
  decisions).
- **Skills/assets as a library**: governed agent-skill registry with versions,
  checkout modes, pointer-only downstream distribution, retirement notices;
  coding-asset/tactic/harness registries; portability contract with digest
  gates on every governed file.
- **Transport/data plane**: DAD_DATA_ROOT split from the repo (marker-gated,
  legacy fallback); private data-only journal repo for replication; mail
  center (candidate-only inbox/outbox across repos); daemon with scheduled
  cycles (graph surfaces, mail digests, exception-lake reports); MCP-first
  policy with a local MCP server exposing graph/lifecycle/recovery tools.
- **Known frictions (fresh evidence)**: OneDrive sync + Windows file locks
  make the full test suite environment-flaky and slow (a suite that computes
  in ~17s can take 75–95s wall); CI is billing-fragile, pushing the operator
  to a local-first merge gate; enrollment reliability was just repaired
  (writability prechecks, config source-of-authority pointer, lifecycle
  rollback).

### The upgrade thesis you are reviewing

The 2026 frontier converged on exactly DAD's shape — persistent instructions +
skill library + entities + memory, local-first, tiered model economics — and
then moved past it in three ways DAD has not: (1) memory became a **live,
tiered, bitemporal, provenance-carrying layer** agents read/write through
(Letta-style core/recall/archival tiers; Zep/Graphiti-style temporal knowledge
graphs where every fact has valid-time and source); (2) self-improvement
became an **operating loop** over skill libraries, not a plan (SkillOps-style
lifecycle management, generate-store-reuse, continual-learning benchmarks);
(3) agent task horizons are **doubling roughly every 7 months** (METR:
frontier ~12h at 50% reliability today; month-long tasks plausible 2027) while
reliability remains the binding constraint — so the scarce asset becomes a
durable, governed personal substrate that makes long autonomy safe and
cumulative. The thesis: DAD should be that substrate, and should become live.

Planned new functionality (stress-test each; strike any that is wrong):

1. **DAD Live session**: DAD becomes bootable like a program — one command or
   shortcut starts the live session (daemon + MCP server + cockpit refresh +
   health surface, warm caches) for the duration of a work session, with a
   crash-restart contract and clean shutdown; an always-on Windows service is
   an optional later mode, not the requirement. While the session is up,
   every agent runtime preflights against it in milliseconds instead of
   seconds.
2. **Tiered bitemporal memory layer**: a Core/Recall/Archival memory API over
   the existing catalog + lessons + events, where every fact carries
   valid-from/valid-to, ingestion time, source episode, and confidence;
   exposed to all runtimes via MCP tools (`memory.recall`, `memory.append`,
   `memory.pin`); append candidate-only, promotion human-gated; answers
   "what is true now / what was true then / where did this come from".
3. **Session continuity spine**: every agent session in Claude Code, Codex,
   or Cursor opens with a context pack from the memory layer and closes by
   depositing outcome events — identical contract in all three, wired through
   each runtime's native hook/MCP mechanism so it costs the operator zero
   setup per session; ResumeCapsules become executable — one command
   reconstitutes a paused workstream's context into whichever runtime the
   operator opens next, including across runtimes (pause in Codex, resume in
   Claude Code).
4. **Operating self-improvement loop (T0–T2)**: activate the dormant design
   as a real weekly cycle — outcome normalization, failure-to-lesson,
   skill/trigger improvement with frozen evaluators, memory admission/
   consolidation/poisoning audit, trace-to-workflow composition — capped at
   three human decisions per week, `preserve_current` always valid.
5. **Local-first assurance plane**: the local CI runner becomes the primary
   merge gate (deterministic governance checks hard; environment-flaky suites
   quarantined with evidence), cloud CI demoted to an optional mirror; a
   nightly self-verification cycle (validate, digests, backups, replication
   lag) reports into the cockpit.
6. **Tri-replication contract**: DAD_DATA_ROOT lives on the fastest local
   disk (explicitly out of OneDrive); an fsync-safe mirror job replicates to
   the secondary drive on a schedule with verification manifests; governed
   code/registry surfaces remain on GitHub; recovery is a tested runbook, not
   an aspiration (quarterly restore drill).
7. **Capability-horizon radar**: the weekly research funnel gains one job —
   track the autonomy/reliability frontier (time-horizon data, new memory/
   skill-library results, runtime capability releases) and emit "prepare-for"
   cards: what DAD should scaffold *now* so a 2027 month-horizon agent can be
   adopted safely (e.g., longer activation leases, deeper rollback, richer
   holdout suites, budget circuit breakers).
8. **One-human cockpit, always current**: the existing cockpit HTML becomes
   the single pane — Today (≤3), memory-promotion queue, improvement-loop
   decisions, replication/backup health, capability-horizon cards — refreshed
   by the live session on boot and on material change, never requiring daily
   attention.

9. **Automatic entropy absorption (the missing librarian)**: today the
   attention scan, capture, and capsules exist but wait to be run. Upgrade
   them to fire automatically — on live-session boot and on material change:
   sweep new chats/branches/worktrees into Ideas and Workstreams, draft
   ResumeCapsules for anything going cold (why paused, literal next action,
   in plain language), convert dirty-worktree states into one-decision
   proposals ("keep as WIP commit / park / mark superseded"), and translate
   every Git/test/CI state the operator meets into non-developer language
   with the safe next step attached. Proposals only — nothing is deleted,
   merged, or cleaned without the human choosing.

Explicit non-goals: no cloud dependency for core function; no autonomous
self-modification; no T4/T5 activation; no second human; no rewrite of the
existing event-sourced kernel; no abandoning the governance/audit posture that
already works.

### Your review tasks

Produce a rigorous design review with these exact sections:

1. **Verdict** — `sound`, `sound_with_material_changes`, or `redesign`;
   confidence and the three most important reasons.
2. **Strongest disagreement** — the best case against this upgrade thesis
   before any improvements. Candidates you must consider: "a live service is
   operational burden masquerading as capability for a one-person system";
   "bitemporal memory is over-engineering when lessons + grep already work";
   "the improvement loop will generate decisions nobody has time to review".
3. **Independent architecture** — what you would build for the same ends
   without copying this plan; then map agreements and conflicts.
4. **Memory-layer review** — is Core/Recall/Archival over a SQLite+JSONL
   substrate the right shape? Bitemporal on every fact, or only on contested
   facts? Admission control, consolidation cadence, poisoning defense,
   forgetting policy, and what "pin" should mean. Compare against
   Letta/Mem0/Zep-class designs on capability, not fashion.
5. **Liveness review** — service vs. scheduled daemon vs. on-demand with
   warm cache: which actually serves a sub-second preflight and an
   always-current cockpit at lowest operational risk on one Windows laptop?
   Include OneDrive/file-lock hazards, crash recovery, and upgrade-in-place.
6. **Improvement-loop activation** — the safest first three loops to turn on,
   their frozen-evaluator design, and the exact evidence that would justify
   turning on the next three. Where does the loop most plausibly rot into
   noise, and what kills it cleanly?
7. **Replication/backup review** — critique the tri-replication contract:
   mirror cadence, verification, restore drills, ransomware/corruption
   blast-radius, and what belongs in Git vs. data-plane vs. mirror-only.
8. **Runtime-coupling review** — the surface Claude Code, Codex, and Cursor
   all consume: minimum MCP tool set, per-runtime adapter thickness (hooks vs
   MCP vs config), versioning, what must never be exposed (secrets, raw
   private rows, mutation without lifecycle), how "seamless in all three with
   zero per-session setup" is actually achieved, and how any single vendor
   runtime stays replaceable in under a day.
9. **Horizon preparation** — given task horizons doubling ~7 months and
   reliability the binding constraint, what should exist in DAD *before*
   adopting week-plus autonomous runs? Rank the prepare-for scaffolds by
   regret if missing.
10. **Sequencing** — the operator wants the fully functional cockpit AND
    fully functional T0–T2 learning loops as soon as safely possible, not
    staged over a year. Give the fastest safe build order to that state
    (weeks, not quarters), with exit evidence and kill criteria per step —
    then, separately, the horizon-readiness roadmap: which prepare-for
    scaffolds get built at ~6 months, ~1 year, ~3 years of projected frontier
    capability. Assume one build and one bounded pilot active at any time;
    say explicitly what "safely possible" must not compress.
11. **Red-team and premortem** — ≥15 realistic failure modes including: live
    service silently dead for weeks; memory layer poisoned by a bad scan;
    mirror silently stale; improvement loop optimizing its own metrics;
    cockpit ignored; operator burnout; vendor runtime EOL; laptop loss.
12. **Acceptance harness** — synthetic adversarial tests for the memory
    layer (temporal correctness, provenance, poisoning), the live service
    (kill/restart/upgrade), replication (corrupt-and-restore), and the loop
    (a case where `preserve_current` must win).
13. **One-human cockpit** — the minimum always-current view and the exact
    interrupt conditions; everything else must be pull, not push.
14. **Operator-fit review** — judge the design against the operator profile:
    does idea capture genuinely cost one sentence from inside any runtime?
    Does the system automatically absorb dirty-worktree/branch entropy into
    ResumeCapsules and plain-language next actions without being asked? Where
    does the design still silently assume software-engineering judgment the
    operator does not have, and what automatic translation or guardrail
    closes each gap? Name the places a stream-of-consciousness workflow would
    break this architecture.
15. **Convergence questions** — ≤7 questions whose answers materially change
    the design; nothing already answered here.
16. **Recommended disposition** — `proceed_to_phase_1`,
    `revise_and_recheck`, or `stop`; exact blocking changes.

### Evidence standard

Distinguish established practice, peer-reviewed evidence, promising recent
research, inference, and speculation. Link primary sources for claims that
materially affect architecture (METR time-horizon data, temporal-KG memory
papers, skill-library lifecycle work). Do not treat benchmark gains, GitHub
stars, novelty, model confidence, or graph centrality as proof of downstream
value. State where evidence is weak or contradictory — especially on whether
live personal-OS daemons are actually retained by solo operators past month
two.

### Constraints

- Do not implement, run code, create accounts, activate schedules, contact
  anyone, or recommend silent autonomous self-modification.
- Do not assume any model vendor survives; capability tiers stay abstract.
- Do not make Fable a standing recurring dependency.
- Do not solve cost by dropping independent validation on consequential
  changes; route proportionally.
- The operator must be able to ignore the system for two weeks without harm.
- `preserve_current` is always a valid outcome; quiet is the default.
- Every proposed mutation needs scope, consequence class, evidence,
  independent review, human gate, expiry, and rollback.

End with a compact table: `Upgrade element | keep/change/remove | rationale |
blocking before Phase 1`.

---

## Return path

Return text only. Lowell or DAD — not Fable — may save the answer as a
separate, dated artifact under `processed/fable5/deep-dives/`. Do not
overwrite this prompt. DAD should record: Fable model/runtime, date, sanitized
packet digest, response pointer, strongest disagreement, accepted/rejected
changes, resolver, independent recheck, and Lowell's final decision.
