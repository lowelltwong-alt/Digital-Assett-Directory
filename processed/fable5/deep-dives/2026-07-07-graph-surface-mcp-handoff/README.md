# Fable 5 Handoff: Graph Surface Manifests And MCP Boundary

Status: candidate Fable review packet.

Created: 2026-07-07

Baseline commit before this handoff packet: `babcbc8`

## Purpose

This packet asks Fable to design the hard governance kernels for DAD graph
surface manifests after the AI-agnostic lifecycle and Local+Journal/MCP-first
transport stack.

DAD should have one source-controlled graph surface registry and several
generated per-graph manifests. Internal DAD integrations should prefer local MCP
resources, tools, and prompts over direct vendor APIs. MCP is an adapter
boundary, not a new authority.

## Start Here

1. Read `fable5-master-prompt.md`.
2. Read `kernel-briefs.md` for Codex's compact starter kernels.
3. Use `evidence-index.json` for exact paths and validation context.
4. Return findings in the shape described by `expected-output.schema.json`.

## Current State

- PR #13 adds an AI-agnostic lifecycle layer. Claude remains a thin adapter.
- PR #14 through PR #16 add Local+Journal transport: data root, daemon
  readiness, and dad-journal checkpointing.
- PR #17 adds rollout docs, queue-based transport upgrade planning, and
  MCP-first integration policy.
- A parallel transport completion audit is active on
  `codex/transport-kernel-followup`. It reports local-ready software with
  human gates pending, and it is still finding merge-level data-root writer
  surfaces that PR #17 may not yet include.
- Existing graph work already treats generated graphs as candidate evidence,
  not source truth.
- The lesson graph has a generated-manifest pattern in design/docs, but DAD
  does not yet have one registry that enumerates all graph surfaces.

## Fable Output Reconciliation

Fable output `fable-output/graph-surface-mcp-kernels.md` was authored from the
`fable/aios-architecture` branch. Its finding F1 says this packet and
`docs/MCP_FIRST_INTEGRATION_POLICY.md` were absent. Treat that as branch
visibility drift, not a policy finding against the stacked Codex work: those
files exist on the PR #17/#18 stack and are the intended base for follow-up
implementation.

## Parallel Transport Merge Context

Fable must consider the parallel transport work before finalizing graph surface
kernels. The current signal is:

- transport readiness reports `local_ready_human_gates_pending`;
- M0-M2 software is green locally, but operational gates remain unapproved;
- more data-plane surfaces are being routed through `DAD_DATA_ROOT`, including
  generated proposal, workflow-part, raw research, exception-capture, mail
  digest, and report writers;
- version tracking is now an open requirement so DAD can tell which repos have
  which transport/graph/MCP contract surfaces installed;
- synthetic data tests should prove the new way works before downstream rollout.

Primary parallel worktree:

`C:/Users/lowel/OneDrive/Desktop/Git Projects/_codex_worktrees/dad-transport-followup`

## Applies When

Use this packet when Fable is reviewing or designing:

- graph surface boundaries;
- graph manifest schemas and drift rules;
- MCP resource URI taxonomy for DAD graph context;
- no-lock-in AI runtime policy;
- graph centrality and generated-edge false-authority risks;
- buildable Codex kernels for graph surface implementation.

## Does Not Apply When

Do not use this packet as:

- human approval of any roadmap gate;
- permission to write downstream repos;
- permission to implement a cloud relay;
- permission to make MCP or any vendor runtime a policy authority;
- proof that generated graph edges are true, useful, or promoted.

## Danger If Misapplied

The main danger is false authority. A graph surface registry can make generated
relationships look official. Fable should preserve the rule that raw records,
registries, schemas, DAD lifecycle evidence, Git/CI, and human gates remain the
authority. Graphs and MCP resources are read-only candidate context unless a
separate reviewed workflow says otherwise.
