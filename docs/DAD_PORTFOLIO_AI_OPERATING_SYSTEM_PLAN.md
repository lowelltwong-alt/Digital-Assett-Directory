# DAD Portfolio AI Operating System Plan

Status: active architecture and buildout plan. P0, the non-mutating Model C
P1/P3/P4 kernel, the unified Portfolio Cockpit, proposal-only identity reconciliation,
candidate-only workstream shaping, and the read-only Portfolio Review Packet
slices are implemented. Evidence and decisions live in
`docs/frontier/collaboration/04_CODEX_RETURN_IMPLEMENTATION.md`,
`docs/frontier/collaboration/11_PORTFOLIO_COCKPIT_PROJECTION.md`,
`docs/frontier/collaboration/13_PORTFOLIO_WORKSTREAM_SHAPING.md`, and
`docs/frontier/collaboration/14_PORTFOLIO_REVIEW_PACKET.md`. This plan
is not a human gate approval and never permits DAD to mutate sibling repos.

## Recovery And 2026-07-11 Update

This plan was recovered from the untracked, obsolete worktree
`codex/orchestration-operating-system-plan-20260709`. That worktree was 25
commits behind `origin/main`, its upstream was gone, and the plan plus Fable
packet existed only as untracked files. The plan is preserved here on a fresh
branch from current `origin/main`; the old worktree remains untouched.

Repository archaeology also found a separate preserved orchestration seed at
commit `4f08594`. Its append-only task board, leases, checker protocol, programs,
and merge train are useful prior art, but it is LawFirm-specific and seven of
fourteen task records reference missing specs (`T-0007` through `T-0013`). Do
not cherry-pick the seed wholesale or treat its board as operational before a
queue audit.

The user's immediate problem is broader than the original plan: creative ideas
become chats, repos, branches, and worktrees, then disappear from attention.
The amended durable object model is:

```text
Project
-> Idea (one-sentence capture + tiny problem/user/v1 card)
-> Workstream (one intent, one branch, one worktree, one primary agent task)
-> SessionRef (Codex, Cursor, or Fable packet metadata; not raw chat)
-> ActivityEvent (append-only metadata)
-> ResumeCapsule (why paused, blocker, last check, literal next action)
```

The user-facing rule is conditional attention, not age-based guilt:

- interrupt only for conflicts, failed checks, or a blocked agent;
- gently nudge when a project is active but a related dirty/open workstream has
  been idle for roughly three days;
- request a weekly decision after seven days without a pause reason or next
  action;
- never nag intentionally paused/incubating work;
- resurface cold work when a new idea has an explainable relationship to it;
- every nudge offers `Resume`, `Checkpoint and pause`, `Mark superseded`,
  `Review`, or `Snooze`;
- never delete or clean a branch automatically.

### Implemented First Slice

Portfolio Attention V1 is implemented on this branch:

```text
asset-dir os status --root <portfolio-root> --stale-days 3
```

It uses read-only native Git metadata to group canonical repositories and linked
worktrees, inventory every local branch, identify dirty/conflicted/detached,
ahead/behind, gone-upstream, merged-by-ancestry, and inactive-branch states,
and generate explainable metadata-only related-project candidates. It writes:

```text
DAD_DATA_ROOT/processed/reports/portfolio_attention.json
DAD_DATA_ROOT/processed/reports/portfolio_attention.html
```

The HTML view caps `Today` at three items while keeping a filterable full queue.
No checkout, commit, merge, rebase, cleanup, deletion, branch creation, or
source-repo write occurs. Live validation on 2026-07-11 found 31 canonical
projects, 211 branches, 121 linked worktrees, 27 dirty worktrees, and 158
candidate attention items.

### Implemented Model C Kernel

The Claude-Codex synthesis now adds one verified append-only event ledger and
pure projections for ideas, workstreams, lifecycle, resume capsules, Today,
Scrum-style board columns, explicit dependency bottlenecks, and DAD child-project
sovereignty. Mutable commands accept explicit `--request-id` idempotency keys;
dependency suggestions remain proposed until a named human accepts them, and
mistaken assertions are retracted through inverse events rather than history
rewrites. `asset-dir os refresh` refreshes the read-only V1 snapshot before
folding workstreams and reports material Today changes, not timer ticks.

The implementation deliberately stops before P2 Git mutation. Branch,
worktree, and Codex-task creation belong to a separate human-gated executor
that consumes approved kernel proposals and returns verified result events.
Recurring activation also remains off until a named human enables it.


### Implemented Unified Portfolio Cockpit

The first Wave 6 organization surface is now implemented as a pure projection:

```text
asset-dir os cockpit
asset-dir os refresh
```

`os cockpit` can refresh the read-only Git snapshot, fold the verified
workstream ledger, and write one strict composite report plus a script-free
local HTML page:

```text
DAD_DATA_ROOT/processed/reports/portfolio_os/cockpit.json
DAD_DATA_ROOT/processed/reports/portfolio_os/cockpit.html
```

The global Today list is capped at three across both source systems. Candidates
enter an explicit ordinal band before source-local priority is considered:
human decision, integrity/unknown, dirty recovery, dependency unlock,
related-active neglect, then weekly maintenance. Those source priorities are
not a calibrated project-value score.

Repository, branch, and worktree identities are deterministic. Only an exact,
accepted resource binding may join Git attention to a workstream; proposed,
legacy name/path, ambiguous, and unresolved bindings remain visible but never
silently match. Missing, invalid, stale, or unknown source evidence blocks
`all_clear`. Dependency cycles are human-review unknowns and cannot enter the
unlock frontier. The HTML contains no scripts, forms, external resources, or
mutation controls, and its fixed inline stylesheet is hash-bound by CSP.

This cockpit alone is not the completed Wave 6 operating surface. The Portfolio
Review Packet now adds categorical daemon, daily-review, mail, journal, transport,
target-repo, checker, execution-shadow, and human-decision health. MCP read
resources, calibrated operator feedback, recurring activation, and any executor
remain separate future gates.
### Implemented Proposal-Only Reconciliation

The next organization layer is implemented as a pure projection over one
strict cockpit snapshot:

    asset-dir os reconcile

It exposes exact repo, branch, and worktree IDs; repeats existing exact
proposals for review; may prepare a proposal-only binding command from one
unique branch/worktree structural pair; and keeps every lexical match
`inspect_only`. It cannot append events, accept bindings, create
workstreams, mutate Git, dispatch agents, notify people, or change the
accepted-only dependency frontier.

Outputs are `reconciliation.json` and `reconciliation.html`
beside the cockpit reports. Zero candidates is explicitly different from
fully reconciled; zero workstreams produces intake need, not a fabricated
identity. Ambiguous equal-best exact candidates choose no winner. The full
decision and kill criteria are in
`docs/frontier/collaboration/12_PORTFOLIO_BINDING_ASSISTANCE.md`.

### Implemented Candidate-Only Workstream Shaping

The creative-sprawl layer is implemented as another pure projection:

    asset-dir os shape

It consumes the strict current workstream, cockpit, and reconciliation snapshots
and produces evidence-tiered split, rescope, possible-duplicate, and recovery
cases. Exact accepted identity and reciprocal structure can trigger review; label
similarity remains `inspect_only`; broad repo context cannot become branch or
worktree identity; and age alone never creates a case. Quiet and terminal work
remain quiet.

The review queue is a subset of the existing three-item cockpit Today list. The
full inventory is bounded and reports hidden counts. `no_cases_generated` is
separate from `shaping_complete`, so zero cases cannot become a false green. The
JSON and script-free HTML expose inert choices only: no command, active control,
accepted identity, durable decision event, raw conversation, or absolute path.

`os refresh`, `os reconcile`, and `os shape` publish the dependent shaping,
reconciliation, and cockpit cursor set with bounded six-file rollback. This is
not crash-atomic storage, and no timer, executor, task mutation, notification,
or agent dispatch has been enabled. The full evidence model and kill criteria
are in `docs/frontier/collaboration/13_PORTFOLIO_WORKSTREAM_SHAPING.md`.

### Implemented Read-Only Portfolio Review Packet

The first complete one-command Wave 6 review surface is implemented as:

    asset-dir os review

It reads the existing strict cockpit, reconciliation, and shaping cursors without
scanning Git or rewriting a source report. It reuses the one cockpit Today list,
attaches only matching reconciliation and shaping reviews, and shows now, next,
waiting, blocked, failed, completed, and intentionally quiet lanes. Independent
health adapters expose daemon, daily-review, mail, journal, transport, target-repo,
checker, execution-shadow, and roadmap human-decision state.

Missing, invalid, stale, future, dirty, unresolved, or unscoped evidence prevents
`all_clear`. A disabled executor with no applicable work is visible and safe; it
is never treated as approval. Material fingerprints exclude timer ticks, and the
script-free HTML plus authoritative JSON cursor roll back on synchronous
publication failure. The response template is copy-only and records no decision.
`os refresh` publishes this independent derived cursor only after the cockpit,
reconciliation, and shaping set succeeds. No timer, notification, MCP mutation
tool, durable calibration event, or executor is enabled.

### Implemented Project-Management Agent Directory

The first PM/trigger agent control-plane slice is now implemented outside the
Portfolio OS event ledger. DAD owns two runtime-neutral candidate skills:

- `personal-project-management-ops` for idea identity, workstream planning,
  delivery evidence, resumption, and quiet portfolio review;
- `dad-trigger-pattern-radar` for neglected-work, board, research, dependency,
  trigger-judging, automation-architecture, and trial-grading roles.

Their 11 roles are allowlisted through `registry/agent-skill-library.json`,
schema-validated, capability-addressable, and searchable through
`asset-dir subagents directory` or `asset-dir os agents`. Search is read-only
and categorical; it does not dispatch agents or rank quality. The generated
directory is a sidecar to the attempt-first evaluation graph, and every untried
role remains `insufficient_evidence` until exact immutable attempt/revision links
and independent grading exist. Scrum focus, readiness, blocking, validation,
delivery, and research state remain overlays; only the kernel's implemented
lifecycle vocabulary is durable. Execution leases and dispatch revisions are
separate authority-plane events, not lifecycle values.

`asset-dir os trigger-feedback` now produces a privacy-minimized, categorical
projection over exact trigger signatures and user feedback actions. It omits
notes and invalid signature text, calculates no quality score, and writes a
generated report only with explicit `--write`. The trigger radar and grader can
use this as shadow-trial evidence; it does not self-modify or enable routines.
### Implemented Execution-Control Shadow Kernel

Execution authority now uses the same append-only per-workstream ledger as the
rest of Model C, with a separate pure execution-control projection. The mixed
reader accepts legacy workstream event v1 rows and the new strict execution
control event v1 rows without rewriting history.

The shadow kernel records lease requests, grants, revocations, exact dispatch
revisions, separate dispatch approvals, expiry, byte-exact SHA-256 scope digests, accepted repo
bindings, independent worker/checker identities, repository-relative path scope,
validation and authority references, expected repository snapshots, and default
forbidden actions. `asset-dir os execution --write` renders local JSON and HTML.

Approval references are attestations, not proof. The default verifier is
deny-all and the CLI exposes no switch for callers to self-declare a verified
approval. Bare identifiers are ignored; a future trusted provider must supply a
typed, time-bounded attestation bound to the exact authority-event digest, and a
reused identifier invalidates every use. Even a projection built with those
attestations produces only a manual packet: `dispatch_allowed` remains false
because the executor, claim journal, mutation locks, repository drift checks,
and spend-once claim protocol are deliberately not implemented here. A
reconciliation cannot claim an outcome until the separate attempt journal


### Corrected Build Order

1. **P0 — read-only attention inventory (implemented here):** canonical repo,
   branch, worktree, dirt, upstream, age, relation candidates, JSON, and HTML.
2. **P1 — durable project/workstream model:** schemas for `Project`, `Idea`,
   `Workstream`, `SessionRef`, `ActivityEvent`, and `ResumeCapsule`; lifecycle,
   owner, next action, pause reason, and snooze are explicit.
3. **P2 — start/split/pause/resume:** one atomic workflow creates or records the
   branch, worktree, Codex task reference, allowed paths, validation, and
   resume capsule. A multi-idea chat becomes separate proposed workstream cards
   before implementation begins.
4. **P3 — calibrated related-work retrieval:** join workstream metadata to the
   existing Background Connection Radar; measure accept/defer/reject outcomes
   and decay low-precision suggestions.
5. **P4 — batched attention:** feed no more than three normal items into DAD's
   daily review queue; conflicts and failed checks may interrupt. Add explicit
   `snooze` and `paused_by_choice` terminal behavior.
6. **P5 — execution adapters:** Codex is the primary command center; Cursor gets
   bounded low-level implementation packets; Fable gets compact, sanitized
   architecture/audit packets. GitHub Projects is an optional projection, not
   source truth.
7. **P6 — human-gated archival assistant:** reversible archive/supersede flows
   only after clean/dirty, ancestry, patch-equivalence, PR, and conflict evidence.

### Research Anchors

Research found no single mature product that solves the whole problem. The
convergent pattern is a catalog plus one workstream per isolated checkout, an
append-only activity log, a batched attention queue, and cloud agents as
execution/audit adapters rather than canonical memory.

- Backstage software catalog and descriptor model: centralized discovery with
  repo-local ownership and lifecycle metadata.
- GitHub's 2026 durable-owner program: mandatory ownership, grace periods,
  reversible archival, and a low-water-mark abort for suspicious bulk actions.
- Native Git worktrees and machine-readable `worktree list --porcelain` remain
  the isolation substrate.
- Codex app projects, tasks, worktrees, automations, and review queues are the
  primary interactive surface available in this environment.
- Worktrunk is a strong branch-addressed worktree UX reference; it is not a
  required dependency.
- Beads provides useful `depends_on`, `relates_to`, `duplicate`, `supersedes`,
  and ready-task semantics, but DAD should not add a second canonical tracker.
- GitHub Projects can be a multi-repo projection, not the local source of truth.
- Research on programmers with ADHD supports clear milestones, task chunking,
  written state, and reminders; Microsoft inclusive-design guidance supports
  attention-proportional alerts; notification research favors predictable
  batching over continuous interruption.
- Local-first design supports DAD's local data root and bounded cloud handoffs.

Primary and community source links are preserved in the task's final research
report; changing vendor capabilities must be rechecked before implementation.

## Purpose

The goal is to turn DAD into the local operating system for AI-assisted work
across a repo family:

- one place to say what you want built;
- one queue that knows every active build, blocker, dependency, lease, checker,
  and human prompt needed;
- one scheduler that can reorder work when a task blocks or unblocks another;
- one model-routing layer that auditions models for task classes instead of
  trusting model names;
- one verification layer where worker, boss, and checker outputs are all
  executable claims, not authority;
- one dashboard that tells Lowell what needs attention, what can run, what is
  blocked, and what should wait.

This plan applies the multi-agent lesson from the pasted transcript: the system
does not try to eliminate hallucination by trusting a better model. It makes
hallucination, shortcutting, over-strict checking, and boss-level mistakes
survivable by separating specification, execution, checking, dispute resolution,
and evidence.

## What "Operating System" Means Here

DAD should not become a monorepo, source authority, or magic autopilot. "OS"
means a control plane with these services:

| Service | DAD owns | DAD must not own |
| --- | --- | --- |
| Work intake | Convert a human request into candidate programs, tasks, dependencies, checks, and prompts. | The target repo's product canon or legal/business authority. |
| Queue scheduling | Compute safe next actions from dependencies, leases, dirty state, model availability, and priority. | Silent cross-repo writes or direct pushes. |
| Agent routing | Assign task class to boss, hard coder, cheap coder, checker, or human prompt. | Trusting a model by brand, cost, or rank without audition and checks. |
| Verification | Require executable checks and independent checker verdicts. | Treating worker reports, model confidence, graph centrality, or scores as proof. |
| Learning | Capture postflight lessons, fix outcomes, model performance, and harness gaps. | Promote candidate lessons or generated findings without review. |
| Attention | Show a small human review queue: prompts needed, stuck work, failed checks, Fable rulings, merge train, and risks. | Flood Lowell with every worker log or intermediate model mistake. |

The durable rule is:

```text
source repo authority
-> DAD planning/control evidence
-> model-specific worker output
-> independent executable check
-> dispute/ruling when needed
-> target repo PR/merge process
-> DAD postflight learning
```

## Current Starting Point

Existing DAD pieces already cover much of the substrate:

- `docs/MAIL_CENTER.md`: candidate mail and local-pull transport.
- `docs/DAD_EVENT_PIPELINE.md`: short metadata events and response state.
- `docs/DAD_TRANSPORT_AND_COMMS_REDESIGN.md`: local data root, daemon, journal,
  and attention plane direction.
- `docs/MCP_FIRST_INTEGRATION_POLICY.md`: MCP-first adapters instead of direct
  vendor APIs for internal DAD access.
- `docs/AI_ENVIRONMENT_CAPABILITY_MATRIX.md`: model-environment capability
  routing across Codex, Cursor, Claude, MCP, skills, hooks, and automation.
- `docs/HARNESS_VS_DETERMINISTIC_ENFORCEMENT.md`: use harnesses while learning,
  enforce only objective high-risk boundaries.
- `docs/CROSS_REPO_GOVERNANCE_DEPENDENCY_MAP_PATTERN.md`: upstream authority,
  child mirrors, validators, and fail-closed routing.
- `registry/preflight-profile-router.json` and
  `registry/coding-tactics-radar.json`: task-to-profile and tactic routing.

The live checkout also contains an unmerged `orchestration/` seed with a
blackboard, task board, agent registry, hot-file leases, decisions, specs, and
program roadmaps. Treat it as prior art until it is landed through normal repo
review. Its strongest pieces are worth generalizing:

- `TASK_BOARD.jsonl` as append-only work bus;
- `AGENT_REGISTRY.json` for model tiers and checker pairings;
- `DEFINITION_OF_DONE.md` as a constitution checked on every task;
- `COORDINATION_PROTOCOL.md` for claims, leases, merge train, and verdicts;
- `HOT_FILES.json` for serializing dangerous shared paths;
- `decisions/D17...D20` for human gates and checker fleet decisions.

Observed gap: the live board creates a model-audition task `T-0008`, but the
referenced spec file is missing. Model auditioning must become a first-class,
schema-backed OS primitive, not an implied task.

## Target Architecture

### 1. Control Plane

Files and future commands:

```text
orchestration/START_HERE.md
orchestration/PORTFOLIO.md
orchestration/TASK_BOARD.jsonl
orchestration/WORK_QUEUE.jsonl
orchestration/HUMAN_PROMPTS.jsonl
orchestration/REPO_LEASES.jsonl
orchestration/INTEGRATION_QUEUE.jsonl
orchestration/AGENT_REGISTRY.json
orchestration/MODEL_AUDITIONS.jsonl
orchestration/CHECK_RESULTS.jsonl
orchestration/QUEUE_DECISIONS.jsonl
```

Command surface:

```text
asset-dir os intake --request "<human request>"
asset-dir os plan --request-id <id>
asset-dir os status
asset-dir os next
asset-dir os prompt-queue
asset-dir os dispatch-packet --task <task-id> --agent <agent-id>
asset-dir os check-packet --task <task-id> --checker <agent-id>
asset-dir os audition --model <model-id> --task-class <class>
asset-dir os queue-audit
```

The command names are placeholders until implementation. The important design
point is that every action writes short append-only metadata and can be
recomputed from source authority plus DAD events.

### 2. Work Intake

When Lowell says "build X" or "fix Y in repo Z", DAD should create an intent
card before it creates tasks.

Minimum intent card fields:

```json
{
  "request_id": "dad:req:...",
  "summary": "Build or fix request in Lowell's words.",
  "target_repos": ["repo-id-or-alias"],
  "source_authority_refs": ["target/AGENTS.md", "target/source-of-truth"],
  "assumptions": [],
  "unknowns": [],
  "candidate_programs": [],
  "forbidden_actions": [],
  "human_prompts_needed": [],
  "safe_next_step": "plan_only|dispatch_ready|human_needed|blocked"
}
```

DAD then turns the intent into a task graph:

```text
intent
-> repo authority read
-> architecture/spec task, if needed
-> implementation task(s)
-> checker task(s)
-> integration/merge task
-> postflight/lesson task
```

If the request affects multiple repos, DAD must model the repo family as a DAG.
The target repo that owns upstream contracts, schemas, prompts, or shared
kernels goes first. Dependent repos wait until their pinned source or contract
is updated, or they receive an explicit compatibility plan.

### 3. Queue Scheduler

The scheduler should be deterministic and conservative. It does not decide what
is true; it decides what is safe and useful to attempt next.

Ready-set algorithm:

```text
for each task:
  reject if blocked_by_human_decision
  reject if target_repo_write_not_allowed
  reject if dependency not done
  reject if target repo dirty and task needs clean base
  reject if active lease overlaps target repo + paths
  reject if checker or required model is unavailable
  reject if validation command is unknown for merge-bound work
  otherwise add to ready set
```

Ordering within the ready set:

```text
priority =
  explicit_human_priority
  + unblock_count
  + dependency_depth
  + stale_blocker_age
  + active_user_attention
  - hot_file_contention
  - risk_without_checker
  - missing_audition_penalty
  - estimated_human_prompt_cost
```

This is a planning heuristic only. The queue output must show why a task moved:

```text
T-0042 moved ahead of T-0031 because it unblocks 5 downstream tasks and does
not touch hot files; T-0031 waits on Fable ruling D22.
```

Cut-in-line rules:

- A task can jump when it unblocks more work, protects source authority, fixes a
  broken validator, resolves a merge conflict, or answers a human/Fable prompt.
- A task cannot jump merely because a model says it is important.
- A blocked task is skipped, not force-run.
- Reordering is recorded as `queue_decision`, with inputs and rationale.

### 4. Agent Org Chart

Use roles, not brands, as the durable contract.

| Role | Default use | Acceptance gate |
| --- | --- | --- |
| Boss / architect | Architecture packets, specs, task decomposition, dispute rulings, merge-train arbitration. | Checked by a different strong model or a red-team checklist. |
| Hard coder | Shared kernels, schema boundaries, migrations, tricky refactors, security-sensitive code. | Independent checker executes tests and validates diff scope. |
| Cheap coder | File-scoped docs, fixtures, schemas, narrow tests, repetitive implementation from exact specs. | Must pass executable checks; cannot infer authority. |
| Foreign/opaque cheap coder | Long low-level coding waves where cost matters. | Must pass audition, independent check, and supply-chain/backdoor scan. |
| Checker | Executes worker output, re-derives source authority, runs tests, records exact failure. | Checker can be disputed; boss can rule the checker wrong. |
| Human | Authorizes gates, sensitive movement, cross-repo write scope, public release, canon promotion. | Recorded decision file or DAD postflight reference. |

Fable should be reserved for architecture, kernel design, dispute rulings, and
high-leverage red team. It should not spend expensive tokens on bulk coding when
the task can be specified and checked.

Cursor/Composer-style agents should receive bounded specs with allowed paths,
forbidden paths, validation commands, and exact done criteria.

GLM or any lower-trust/opaque model should be treated as a supply-chain risk
class, not as a nationality judgment. The system should enforce:

- audition before first real task;
- no self-checking;
- no sole checker role;
- mandatory suspicious-code/backdoor scan before merge;
- no direct dependency additions without provenance review;
- no permission or network scope expansion;
- no code that bypasses local validators or DAD gates.

### 5. Model Auditions

Every model gets hired for a task class, not for all work.

Audition record:

```json
{
  "audition_id": "dad:audition:...",
  "model_id": "composer25|glm52|gpt55|fable|other",
  "task_class": "schema_fixture|python_refactor|frontend_accessibility|rust_parser|docs_port",
  "prompt_ref": "orchestration/auditions/<id>/prompt.md",
  "acceptance_command": "python ...",
  "max_runtime_seconds": 600,
  "hard_constraints": ["exactly five outputs", "no hidden network calls"],
  "result": "pass|fail|needs_review",
  "checker": "agent-or-command",
  "cost_estimate": "optional",
  "notes": "What the model is now trusted to do, and what it is not."
}
```

Audition harnesses should include:

- exact-output constraint tasks;
- repo-local micro-fixes with tests;
- quote/verbatim extraction checks;
- accessibility or UI checks where relevant;
- dependency hygiene checks;
- adversarial "shortcut" traps, such as hidden text, empty elements, fake
  validation, or generated claims without evidence.

Passing an audition allows a model into the worker pool for that task class. It
does not allow self-approval or unchecked writes.

### 6. Verification Layer

Every task ships with a checker job. The checker must ignore the worker report
as evidence and execute the work:

- run the target repo validation commands;
- inspect changed paths against the spec;
- re-derive canonical values from source registries;
- run domain checks, such as accessibility, schema validation, build output,
  screenshot comparison, quote exactness, or dependency scans;
- emit `pass`, `fail`, or `dispute` with exact reasons.

The OS must explicitly support checker failure. If a worker says the checker is
wrong, the dispute goes to Fable/boss. The ruling may fix the worker, the
checker, or the spec.

### 7. Human Attention Plane

The user-facing view should not be a pile of windows. It should be one compact
status surface:

```text
Now running
Ready next
Waiting on Lowell
Waiting on Fable
Waiting on checker
Blocked by dirty repo
Blocked by D17/D18/etc.
Failed checks needing retry
Risk alerts
Completed since last review
```

Human prompt records should be short and actionable:

```json
{
  "prompt_id": "dad:prompt:...",
  "needed_by": "T-0042",
  "target": "Lowell|Fable|Cursor|Checker",
  "question": "Approve D17 cross-repo branch+PR dispatch, or keep human_manual?",
  "options": ["approve_agent_auto_branch_pr", "keep_human_manual", "defer"],
  "default_safe_action": "keep_human_manual",
  "expires_or_review_by": "2026-07-12"
}
```

When Fable must be prompted externally, DAD should produce the prompt packet and
mark the queue item `waiting_on_fable`. When Lowell pastes or saves Fable's
answer, DAD should record the result path, parse only the safe summary/decisions,
and create implementation tasks from it after review.

### 8. MCP And Local Adapters

The OS should expose read-only local MCP resources first:

- `dad://os/status`
- `dad://os/queue`
- `dad://os/prompt-queue`
- `dad://os/task/{task_id}`
- `dad://os/repo/{repo_id}/leases`
- `dad://os/model/{model_id}/auditions`

Mutation tools, if added later, must wrap DAD CLI actions and require explicit
session IDs, repo IDs, task IDs, approval IDs where needed, and postflight.
Direct vendor APIs should remain fallback adapters.

### 9. Rollout To Sibling Repos

Do not push this system into sibling repos as a full copy. Use DAD enrollment and
pointers:

1. Each target repo keeps its own `AGENTS.md` or front door.
2. DAD adds only approved managed blocks, pointers, or mailbox/event surfaces.
3. Source authority remains local.
4. Cross-repo writes stay blocked until D17 or an equivalent named human
   decision records the allowed scope.
5. Protected or public-facing repos use central-only or human-release gates.
6. Every target repo has its own validation command list before worker dispatch.

The sibling repo should receive a task packet, not the entire DAD brain.

## Implementation Waves

### Wave 0: Land The Existing Orchestration Seed Safely

Goal: make the live `orchestration/` seed reviewable and source-controlled.

Actions:

- choose whether to adopt the live seed as-is, split it, or regenerate it from
  this plan;
- preserve its append-only board history if adopted;
- resolve the missing `T-0008.md` by creating an audition spec or withdrawing
  the board row with an append-only correction;
- keep D17 fail-closed until Lowell records the cross-repo write scope;
- add validation for board JSONL shape, missing spec refs, hot-file lease
  consistency, and blocked decision references.

Acceptance:

- `asset-dir os queue-audit` or its first script equivalent reports no missing
  spec refs except intentionally withdrawn rows;
- no target repo writes occur;
- DAD validation remains green.

### Wave 1: Schemas And Validators

Create contracts for:

- program records;
- task events;
- queue decisions;
- repo leases;
- human prompts;
- model auditions;
- checker verdicts;
- backdoor scan verdicts;
- dispatch packets.

Minimum validators:

- JSONL row shape and append-only event types;
- every task has a spec or a withdrawn/superseded event;
- every dependency points to a known task;
- every target repo is reviewed or central-only;
- every merge-bound task has validation commands and checker policy;
- every foreign/opaque worker has a scan requirement;
- no `done` event without checker pass.

### Wave 2: Queue Engine

Build the deterministic ready-set and queue-decision engine.

Acceptance:

- synthetic board with dependency DAG orders upstream tasks first;
- hot-file collision blocks parallel dispatch;
- dirty target repo blocks clean-base tasks;
- D17 blocks all non-DAD dispatch while allowing DAD-home tasks;
- a high-unblock task moves ahead with recorded rationale;
- repeated run is byte-stable except report-level timestamp.

### Wave 3: Model Audition Lab

Create audition tasks and score harnesses for current worker candidates.

Initial task classes:

- docs/schema/fixture worker;
- Python file-scoped implementation;
- frontend/accessibility worker if relevant;
- Rust/parser worker if relevant;
- quote/verbatim extractor;
- foreign/opaque low-trust worker.

Acceptance:

- no model can be assigned to a task class without a passing audition or a
  recorded human override;
- failed auditions produce reusable failure notes;
- audition results are visible in `asset-dir os status`.

### Wave 4: Checker And Backdoor Gates

Build independent checker packets and foreign-output scan harness.

Acceptance:

- checker verdicts require executed commands;
- worker report alone cannot mark `done`;
- GLM/foreign-output PRs require a scan verdict before merge;
- suspicious code patterns are flagged: hidden network calls, obfuscated blobs,
  unpinned dependencies, eval/exec of remote content, permission expansion, and
  validator weakening.

### Wave 5: Human/Fable Prompt Queue

Build the prompt queue and Fable handoff flow.

Acceptance:

- DAD can produce a Fable prompt packet for architecture review;
- the queue shows `waiting_on_fable` until a result path is recorded;
- Fable output is treated as candidate design, not approval;
- accepted Fable kernels become task specs with checks and stop conditions.

### Wave 6: Dashboard And MCP Read Surface

Build a local status dashboard before any remote/cloud relay.

Acceptance:

- one command shows now/next/waiting/blocked/failed/completed;
- stale daemon, stale mail digest, dirty target repo, and missing checker are
  visible;
- MCP resources expose read-only queue state with authority boundaries;
- no direct cross-repo mutation tool is exposed by default.

### Wave 7: Controlled Auto Dispatch

Only after D17 or equivalent approval:

- branch+PR only;
- no direct push to `main`;
- no external connector writes;
- per-repo validation required;
- independent checker required;
- kill switch respected;
- append-only dispatch and postflight events.

## Scrutiny And Premortem

Critical risks and required controls:

| Risk | Failure story | Control |
| --- | --- | --- |
| Authority inversion | DAD starts acting like the owner of sibling repo canon. | D17-style decision, target repo front-door read, source authority refs, branch+PR only. |
| False green queue | Dashboard says work is safe while target repo is dirty or spec is missing. | Queue audit blocks missing specs, dirty repos, stale checkers, absent validators. |
| Worker shortcut survives | Cheap worker hides text, pads output, weakens tests, or adds empty artifacts. | Executable checker, diff audit, domain checks, retry with exact fail reasons. |
| Checker overreach | Checker rejects valid work because a generic rule is too strict. | `dispute` verdict and boss ruling; checker fixes become tasks. |
| Boss self-trust | Fable creates a bug or bad spec and no one checks it. | Boss packets get red-team pass and implementation kernels get tests. |
| Model supply-chain risk | Opaque/foreign worker adds hidden exfiltration or dependency risk. | Audition, no self-check, scan gate, dependency review, network/permission diff. |
| Prompt/data leak | Cross-repo prompt packets include private rows, local absolute paths, or DAD-private strategy. | Metadata-only packets, sensitivity checks, public-release gates. |
| Queue spam | Every low-value item becomes a human prompt or mail notice. | Prompt budget, digest grouping, dormant-by-choice terminal state. |
| OneDrive conflict | Concurrent appends fork board files. | Append discipline, temp+rename, later commit-per-append, conflict detection. |
| Over-automation | Agent auto dispatch begins before policy and validators exist. | Human-manual mode until D17 plus Wave 1-6 acceptance evidence. |
| Cost blowout | Frontier model codes everything. | Role routing and model auditions; expensive model designs/reviews, cheap models implement. |
| Learning noise | One-off local success becomes universal rule. | Candidate-only postflight, harness-first, promotion review and non-applicability notes. |

## Immediate Next Actions

1. Run the supervised Portfolio Review trial in
   `roadmap/evidence/portfolio-review-operator-trial.md`; classify only its three
   displayed rows and verify a repeated run keeps `today_changed=false`.
2. Review shaping precision for useful/noisy recovery cases and missed
   splits/rescopes/duplicates before adding a durable decision command.
3. Build the candidate-only self-grade integrity reviewer and workflow-improvement
   router with domain overlays, `preserve_simple`, evaluator checks, and human-gated
   changes; never use a self-score as promotion evidence.
4. Expose the reviewed packet through local read-only MCP resources; keep mutation
   tools absent until the executor gate is approved.
5. Decide explicitly whether to enable activation rung 2 only after repeated review
   trials prove stale-source, nonzero-exit, unchanged-fingerprint, and prompt-budget
   behavior. Keep D17 in `human_manual` until queue audit, operator evidence,
   independent checker, anchored trust, and rollback controls are accepted.

## Reusable Lesson

The main reusable lesson is that multi-agent reliability comes from organization
design, not model faith. DAD should encode that as durable structure: written
constitution, auditions, task graph, independent executable checks, checker
disputes, supply-chain gates, and postflight learning.
