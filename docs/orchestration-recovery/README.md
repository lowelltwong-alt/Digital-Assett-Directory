# Orchestration Recovery — D17–D20 and Reference Docs

Status: **recovered drafts — no decision in this directory is thereby made or approved**

These files were recovered on 2026-07-27 from branch
`codex/preserve-parallel-orchestration-20260710` (commit `4f085940`, dated 2026-07-10), where the
entire `orchestration/` layer was checkpointed and never integrated — the incident recorded as DAD
lesson `dad:lesson:0cf6def7-acf4-5824-b465-c2f9bfe5d305` and the origin of the pointer-liveness and
branch-disposition validators.

They are ported here so that the decision records active plans cite (**D17–D20**) are reachable
from `main` instead of stranded on a preserve branch. Recovery of *content* is not resolution of
*decisions*:

| File | What it is | Status |
|---|---|---|
| `D17-dad-cross-repo-write-scope.md` | DAD cross-repo write scope decision record | **OPEN — needs owner decision** |
| `D18-sim-harness-home.md` | Home for `lawfirm-os-sim-harness` (gates marathon Wave 8; must not be pre-empted by Wave 3) | **OPEN — needs owner decision** |
| `D19-stale-intake-copy-A-disposition.md` | Disposition of the stale intake snapshot A | **OPEN — needs owner decision** |
| `D20-checker-fleet-and-pairings.md` | Checker pairing matrix | **OPEN — needs owner decision** |
| `ARCHITECTURE_PACKET.md` | Orchestration architecture reference (v1.0, 2026-07-09) | Historical reference; parts may be superseded by the daemon/cockpit/portfolio-execution machinery that landed after 2026-07-10 |
| `START_HERE.md` | Original orchestration entry point | Historical reference |

The remaining 24 checkpointed files (TASK_BOARD state, leases, queues, specs T-0001…T-0006,
programs P1–P3) stay on the preserve branch under its recorded disposition
(**active, review_after 2026-08-09**, `registry/branch-disposition-registry.json`). Operational
state from 2026-07-10 should not be re-published as if live; whether any of it is ported or
tombstoned is decided per record during the review, not wholesale.
