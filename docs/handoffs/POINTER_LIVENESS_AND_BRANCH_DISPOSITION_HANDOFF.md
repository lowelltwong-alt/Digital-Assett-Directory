# Pointer Liveness and Branch Disposition Handoff

Implemented 2026-07-27 (see `src/digital_asset_directory/pointer_liveness.py` and
`src/digital_asset_directory/branch_disposition.py`). This file preserves the
originating handoff text verbatim for provenance; the module docstrings carry
the final scoping rationale and live-repo finding counts.

```text
You are implementing two validators in the Digital Asset Directory (DAD) repo.

=====================================================================
1. WHY THIS EXISTS - THE INCIDENT
=====================================================================
On 2026-07-10 the DAD multi-agent orchestration layer was checkpointed onto branch
codex/preserve-parallel-orchestration-20260710 (commit 4f08594) and never integrated into main.

Verified 2026-07-26:
  git merge-base --is-ancestor 4f08594 main          -> false
  git ls-files orchestration                          -> 0 files
  git ls-tree -r --name-only 4f08594 -- orchestration -> 30 files
  git branch -a --contains 4f08594                    -> that one branch only

All 30 files are intact on that branch: TASK_BOARD.jsonl, ARCHITECTURE_PACKET.md,
CODEX_TAKEOVER_HANDOFF.md, COORDINATION_PROTOCOL.md, AGENT_REGISTRY.json, REPO_LEASES.jsonl,
INTEGRATION_QUEUE.jsonl, HOT_FILES.json, ESCALATION_POLICY.md, decisions D17-D20,
programs P1-P3, specs T-0001..T-0006.

NOTHING WAS LOST. The failure was preservation without integration. For 16 days, agent memory,
cross-repo handoffs, and program plans kept citing 04_Digital_Assett_Directory/orchestration/ as
the live dispatch home. Any agent following that pointer found an empty path and could reasonably
conclude the capability was deleted - and rebuild what already existed one branch away. Four
decision records still cited as open gates were unreachable from main.

Two capability gaps made this both possible and undetectable:
  CAP-1: nothing checks that a preserve/checkpoint branch is integrated or explicitly tombstoned
         within a bounded window.
  CAP-2: nothing validates that paths named in front doors and registries still resolve ON THE
         DEFAULT BRANCH.

Originating lesson: dad:lesson:0cf6def7-acf4-5824-b465-c2f9bfe5d305

=====================================================================
2. STANDING RULES
=====================================================================
- Extend existing machinery. Do NOT create a parallel report surface, a second git wrapper, or a
  new staleness convention.
- Read-only git only. These are validators. Neither may merge, delete, push, or rewrite anything.
- Fail closed with an explicit human escape hatch: an unresolvable pointer or an undispositioned
  stranded branch is an ERROR, but a recorded human disposition clears it.
- Any new registry file gets its schema registered in registry/schema-registry.json.
- Tests live flat as tests/test_<module>.py.
- Run python scripts/validate_repo.py and scripts/local_ci.sh before reporting done.

=====================================================================
3. CAP-2 - POINTER LIVENESS VALIDATOR
=====================================================================
Registries and front doors declare paths. Nothing verifies those paths exist - and critically,
nothing verifies they exist on the DEFAULT BRANCH, which is what every other clone, agent, and
downstream consumer actually sees.

Surfaces: registry/ai-navigation-registry.json (singular_entrypoint.path, branch_map[].path,
branch_map[].paths, branch_map[].route_after[]), registry/graph-surface-registry.json (ref,
module, manifest_logical_path, body_logical_path), registry/dad-offerings-registry.json (path,
source_refs, validation_refs, harness_registry_ref), registry/template-registry.json (path +
per-record contract paths), MACHINE_NAVIGATION_MANIFEST.json
(navigation_standards.single_ai_entrypoint, navigation_standards.navigation_registry),
AI_TABLE_OF_CONTENTS.md (| Path | table rows).

OUT OF SCOPE for v1: dad:// logical URIs - deliberately not local paths.

Two modes, both required: worktree (fast, default) and default-branch
(git ls-tree -r --name-only <default-branch>) - the mode that catches the incident class.

Stable issue codes: pointer_target_missing_in_worktree,
pointer_target_missing_on_default_branch (headline), pointer_target_untracked,
pointer_registry_unparseable.

Acceptance: runs inside validate_repo; standalone CLI with
--mode worktree|default-branch|both; regression test using the real incident
(fixture registry pointing at orchestration/); distinguishes untracked from absent;
zero false positives on the current repo.

=====================================================================
4. CAP-1 - BRANCH DISPOSITION CHECK
=====================================================================
A branch can hold real work indefinitely without anyone deciding what happens to it.
118 branches / ~40 worktrees as of 2026-07-26: a naive "warn on every unmerged branch"
check produces 100+ findings, gets muted, and protects nothing. GETTING THE SCOPE RIGHT
IS THE WORK. Scoping priority: ahead of default and unmerged; tip older than the window;
no registered worktree; not in the disposition registry. Launch scoped to name patterns
(preserve/, checkpoint/, wip/, *-preserve-*) plus branches whose diff touches registry/,
decisions/, or docs/. RECORD THE SCOPING RATIONALE IN THE MODULE DOCSTRING.

Disposition registry: registry/branch-disposition-registry.json
(integrate | tombstone | active; reason REQUIRED; review_after for active;
schema registered in registry/schema-registry.json). integrate remains an ERROR until
the content is reachable from the default branch; tombstone clears with a reason;
active clears until review_after.

Staleness window: reuse an existing convention (routine_health evaluate_contract or
mcp_dependency_map observation_max_age_days + future_skew_seconds). Initial window
14 days; the incident ran 16.

Acceptance: detects codex/preserve-parallel-orchestration-20260710 as stranded when
undispositioned (THE regression test); clears once tombstone/integrate recorded;
re-raises for integrate until reachable; rejects empty reason; respects review_after;
manageable documented finding count; never merges/deletes/pushes/rewrites (enforced by test).

=====================================================================
5. WHAT NOT TO BUILD
=====================================================================
- DO NOT auto-merge preserve branches (a checkpoint may be a deliberate quarantine).
  The validator's job is to force a DECISION, never to make it.
- DO NOT create a new top-level report surface. Extend validate_repo.
- DO NOT add a second git wrapper (portfolio_convergence_git exists).
- DO NOT invent a third staleness scheme.
- DO NOT resolve dad:// URIs as filesystem paths.

=====================================================================
6. OUT OF SCOPE
=====================================================================
Decisions D17-D20 are still stranded on the preserve branch and need their own disposition.
That is a SEPARATE recovery task. This handoff builds the detectors; it does not resolve the
incident that motivated them.
```
