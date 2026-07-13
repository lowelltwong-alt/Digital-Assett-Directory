# Opus 4.8 xhigh: DAD Portfolio Operating System Kernel

You are Claude Opus 4.8 running at xhigh effort in an isolated Git worktree.
Act as a systems architect, creative-workflow researcher, kernel implementer,
and adversarial reviewer. The human explicitly asked you to design the whole
DAD-centered portfolio operating system and write its first executable kernel.

## Human problem

The user is highly creative and starts many related ideas across chats,
repositories, branches, and worktrees. Work is frequently left dirty or
forgotten. New ideas should discover related prior work automatically. Active
projects should gently surface relevant idle branches without creating a wall
of guilt or notifications. A chat containing several ideas should become
separate, resumable workstreams with their own branches/worktrees/tasks.

DAD is the local-first control plane. Codex is the primary environment. Cursor
is a bounded low-level implementation worker. Fable is a scarce-credit external
architect/auditor. The normal human UI should be HTML plus native Codex tasks.

## Required orientation

Read the complete local instructions and relevant authority before editing:

1. `AGENTS.md`, `AI_FRONT_DOOR.md`, `MACHINE_NAVIGATION_MANIFEST.json`
2. `registry/source-of-truth.json`, `registry/design-authority.json`,
   `AI_TABLE_OF_CONTENTS.md`
3. `docs/DAD_PORTFOLIO_AI_OPERATING_SYSTEM_PLAN.md`
4. `docs/research/PORTFOLIO_AI_OS_PRACTICE_RESEARCH_2026-07-11.md`
5. `roadmap/evidence/portfolio-attention-v1.md`
6. `src/digital_asset_directory/portfolio_os.py` and
   `tests/test_portfolio_os.py`
7. `docs/DAD_OS_BUILD_ROADMAP.md`, `docs/ARCHITECTURE.md`,
   `docs/DAD_ADDRESS_MODEL.md`, and
   `docs/CLAUDE_ARCHITECTURAL_ROOT_CAUSE_REVIEW.md`
8. The DAD agent-skill and asset registries before inventing a reusable skill,
   routine, plugin, or algorithm.

You may inspect `C:\tmp\dad-preserved-orchestration` read-only for its task
board, leases, checker protocol, merge train, programs, and specifications.
Treat it as candidate archaeology, not current authority.

The DAD preflight for this branch is already open as
`dad:session:fa999a07-e688-409e-a2f5-2941ef87496d` with trace
`dad:trace:3d58a7aa-8ed8-5e79-8152-a06c2fa1e1ef`.

## Architecture challenge

Do not merely propose a task manager, Kanban board, vector-search wrapper, or
notification system. Generate at least three genuinely different operating
models and compare them. At least one should be conservative and immediately
buildable; at least one should be novel enough that it might fail.

Pay particular attention to novel, testable mechanisms for:

- distinguishing healthy creative divergence from harmful abandoned sprawl;
- recognizing when a new idea is a continuation, sibling, duplicate,
  experiment, or contradiction of previous work;
- converting one conversation with multiple ideas into separate proposed
  workstreams without destroying the conversational context connecting them;
- deciding what to resurface today under a strict attention budget;
- learning a person's actual resume/ignore/snooze behavior without creating a
  manipulative engagement-ranking system;
- preserving incubation and serendipity while still closing loops;
- maintaining identity across repository, branch, worktree, Codex task,
  external-agent run, specification, and resume capsule;
- safely composing skills, subagents, routines, plugins, hooks, scheduled
  reviews, and deterministic algorithms;
- recognizing when the correct recommendation is to merge, split, supersede,
  archive, checkpoint, or deliberately do nothing.

For every novel mechanism, state:

1. what is actually new about it;
2. its inputs, state, and deterministic/AI boundary;
3. failure and abuse modes;
4. a cheap falsifiable experiment;
5. applies-when, does-not-apply-when, and danger-if-misapplied.

Plugins and persistent automation may be proposed, but do not install plugins,
enable memory, create scheduled tasks, or alter global configuration. Never
send repository contents, paths, private payloads, or secrets to a remote
service. Local source authority is absolute.

## Executable kernel

After comparing architectures, choose a bounded V0 kernel and implement it in
this worktree. The kernel must be useful without cloud services and must build
on, rather than duplicate, Portfolio OS Attention V1.

The implementation must demonstrate this loop:

`capture idea -> find related prior work -> classify relationship -> propose a
workstream -> preserve a resume capsule -> rank a bounded focus queue`

Requirements:

- local-first, deterministic core with AI as an optional advisory adapter;
- append-only or equivalently auditable state transitions;
- stable IDs and explicit provenance/confidence;
- idempotent commands and crash-safe writes;
- no automatic Git mutation, branch creation, worktree creation, deletion,
  merge, rebase, push, or source-repository write in V0;
- no hidden background activity;
- strict schemas and synthetic fixtures;
- human-readable reasons for every relation and focus recommendation;
- hysteresis/snooze/incubation behavior so the system does not nag;
- a maximum of three Today recommendations;
- compatibility with the existing `asset-dir os status` report;
- narrow public CLI commands under `asset-dir os`;
- tests for identity, idempotency, relationship classification, attention
  bounds, incubation, failure recovery, and privacy/path handling.

Prefer the smallest architecture that proves the hard state transitions. Do not
build a large UI, external service, embeddings pipeline, daemon, or autonomous
Git executor yet. Do not use Rust without measured evidence.

## Use of agents and skills

Inspect available skills, plugins, and subagent facilities. Use bounded
subagents when they materially improve independent architecture, algorithm,
privacy, or test review. Keep their writes non-overlapping. Require an
independent checker to execute acceptance tests. Do not claim a subagent or
plugin was used unless it actually was.

## Deliverables

Create:

- `docs/frontier/OPUS_4_8_PORTFOLIO_OS_ARCHITECTURE.md`
- the executable kernel in the normal `src/digital_asset_directory/` package;
- focused tests under `tests/`;
- any strict schema required under `schemas/`;
- a short evidence file under `roadmap/evidence/` with exact commands/results.

Update existing navigation only if required by repository contracts. Keep the
diff narrow. Run focused tests, lint, schema/DAD validation, and `git diff
--check`. Do not commit, push, open a PR, clean, reset, rebase, or modify another
worktree. End with a concise report separating confirmed findings, inferred
findings, assumptions, unknowns, reusable lessons, and remaining risks.
