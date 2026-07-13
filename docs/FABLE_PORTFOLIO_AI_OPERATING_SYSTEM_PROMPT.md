# Fable Prompt: DAD Portfolio AI Operating System

Update 2026-07-11: Portfolio Attention V1 now exists as a read-only Git metadata
scanner and local HTML/JSON dashboard (`asset-dir os status`). Review the
recovered plan's corrected P0-P6 order. Concentrate Fable tokens on the durable
Project/Idea/Workstream/SessionRef/ActivityEvent/ResumeCapsule contracts, atomic
start/split/pause/resume semantics, conditional attention and snooze behavior,
and authority-safe Codex/Cursor/Fable adapters. Do not spend architecture tokens
redesigning the V1 scanner unless validation evidence shows a false-green or
privacy defect.

You are reviewing a candidate plan to make DAD the local operating system for
AI-assisted work across many sibling repos. DAD is the Digital Asset Directory:
a local-first control plane for repo inventory, candidate assets, mail, events,
lessons, harnesses, model/agent guidance, and governed learning. Target repos
retain local source authority.

Do not implement changes. Produce architecture kernels, scrutiny, and corrected
work ordering that Codex or other worker agents can execute later.

## Read First

- `AI_FRONT_DOOR.md`
- `AGENTS.md`
- `MACHINE_NAVIGATION_MANIFEST.json`
- `registry/source-of-truth.json`
- `registry/design-authority.json`
- `AI_TABLE_OF_CONTENTS.md`
- `docs/DAD_PORTFOLIO_AI_OPERATING_SYSTEM_PLAN.md`
- `docs/MCP_FIRST_INTEGRATION_POLICY.md`
- `docs/DAD_TRANSPORT_AND_COMMS_REDESIGN.md`
- `docs/DAD_EVENT_PIPELINE.md`
- `docs/MAIL_CENTER.md`
- `docs/AI_ENVIRONMENT_CAPABILITY_MATRIX.md`
- `docs/CROSS_REPO_GOVERNANCE_DEPENDENCY_MAP_PATTERN.md`
- `docs/HARNESS_VS_DETERMINISTIC_ENFORCEMENT.md`
- `docs/CODING_HARNESS_LIBRARY.md`
- `registry/preflight-profile-router.json`
- `registry/coding-tactics-radar.json`
- `registry/agent-skill-library.json`

If the live checkout has an `orchestration/` folder, inspect it as prior art.
Treat it as unmerged candidate evidence unless it is tracked and reviewed.

## Design Goal

Improve the plan for a DAD-hosted AI portfolio OS that can:

1. Accept Lowell's natural-language request and convert it into a repo-aware
   task graph.
2. Know what else is in progress, what is queued, and what depends on what.
3. Reorder tasks when one build affects another or unblocks many downstream
   tasks.
4. Route Fable to architecture/spec/ruling work, hard coders to kernels, cheap
   workers to bounded file-scoped tasks, and checkers to executable validation.
5. Use model auditions and task-class trust instead of model-name trust.
6. Treat lower-trust or opaque model output as supply-chain risk: useful for
   grunt work only after audition, independent checking, and backdoor scans.
7. Give Lowell one prompt/attention queue instead of many windows.
8. Keep DAD from becoming a silent cross-repo authority or source mutator.

## Constraints

- DAD recommendations, queue scores, graph edges, and model outputs are
  candidate evidence.
- Target repos retain source authority.
- Cross-repo writes fail closed until a named human decision records scope,
  revocation path, allowed dispatch mode, and target repo gates.
- Do not recommend direct pushes to target repo `main`.
- Do not recommend copying private rows, secrets, raw logs, local absolute paths,
  DAD-private catalog content, or long source blobs into prompts, mail, events,
  or dashboard outputs.
- Prefer local MCP resources and DAD CLI wrappers over direct vendor APIs.
- Every merge-bound task must have independent executable checking.
- Boss, worker, and checker can all be wrong; the system must support disputes.
- Harness-first for evolving behavior; deterministic enforcement only for
  stable, objective, high-risk boundaries.

## Questions To Answer

Critical:
- What must be true before DAD can safely auto-dispatch agents across repos?
- What would cause authority inversion, false green status, or silent source
  mutation?
- Which parts of the live orchestration seed should be adopted, split, or
  rejected?

High:
- What schemas and validators are required before worker dispatch?
- What queue algorithm should decide "next" and "cut in line" without turning
  heuristic priority into authority?
- How should DAD represent Fable-required prompts, Cursor/worker handoffs,
  checker verdicts, and human decisions?
- How should model auditions be designed so models are trusted per task class?

Medium:
- Which parts belong in DAD source docs, DAD data root, target repo managed
  blocks, target repo PRs, or future MCP resources?
- What should the first dashboard show?
- Which checks should be deterministic gates and which should start as harnesses?

Low:
- What naming, file layout, and command structure will make the system easy for
  future agents to navigate?

## Desired Output

Return:

Critical Findings:
- Issue, risk, exact fix, acceptance evidence.

High Findings:
- Issue, risk, exact fix, acceptance evidence.

Medium Findings:
- Issue, risk, exact fix, acceptance evidence.

Corrected Architecture:
- Control plane, execution plane, evidence plane, attention plane, verification
  plane, learning plane.

Queue Algorithm:
- Pseudocode for ready-set computation, priority/rationale, conflict handling,
  hot-file leases, dirty repo blocking, human/Fable prompt blocking, and
  cut-in-line rules.

Model Audition System:
- Task classes, tryout examples, scoring rules, trust labels, failure handling,
  and how to route Composer/Cursor, GLM/opaque workers, GPT hard coders, Fable,
  and checkers.

Implementation Kernels:
- Kernel id, severity, purpose, files to create/edit, invariants, tests, stop
  conditions, and Codex/worker delegation packet.

First 10 Tasks:
- Ordered task list with dependencies, target repo, allowed paths, checker
  policy, and validation commands.

Premortem:
- The most likely way this OS becomes noisy, unsafe, expensive, or falsely
  confident six months from now, and the controls that must never be optimized
  away.

Do not claim any roadmap phase is complete. Do not approve D17 or any human
gate. Do not write target repo code.
