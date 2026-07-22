# Agent Family Reconciliation (N6)

Status: candidate process evidence. Candidate-only; no global checkout, plugin
install, or activation.

## Authority map

| Surface | Path | Role |
| --- | --- | --- |
| Portfolio catalog | `registry/agent-family-portfolio-registry.json` | Shared family IDs, graph edges, pilots |
| ML workflow family | `registry/ml-agent-family-registry.json` + `assets/agent-skills/ml-workflow-agent-family/` | Sole ML family authority (`family:ml-workflow` / `skill:ml-workflow-agent-family`) |
| Technical Product OS | `registry/technical-product-company-os-registry.json` + `skill:technical-product-company-os` | Thin composition / ranking layer over existing families |
| Knowledge engineering | `registry/knowledge-engineering-family-registry.json` | Specialist pack under data-schema family |
| Role directory | `processed/agents/subagent-role-directory.json` | Generated, git-ignored candidate projection; role authority stays in per-family `subagents.yaml` |

## Forbidden duplicate

Do **not** create `machine-learning-family` or any parallel ML family id.
`family:ml-workflow` is the landed authority.

## Inventory outcome (2026-07-20)

Twelve portfolio families are present as `implemented_candidate`, including
full-stack, QVR, security, knowledge, data-schema, MCP integration, product UX,
platform/SRE, harness ops, autonomy overlay, legal overlay, and ML workflow.

Specialist packs with assets: UI/UX, MCP integration, observability/resilience,
developer-platform/DevEx, product-intelligence, knowledge-engineering-ops.

## Deferred gaps (do not invent without recurrence evidence)

1. Full-stack placeholder packs named only as strings
   (`migration_modernization`, `performance`, `cost_optimization`) — not pack
   assets. Prefer specialist_pack disposition after three-repo recurrence.
2. `pack:portable-capability-governance` is referenced on harness-engineering-ops
   but has no matching skill asset yet.
Resolved former gap: unified `processed/agents/subagent-role-directory.json`
now has a governed generator (see the "Declared role directory" section of
`docs/SUBAGENT_EVALUATION_AND_CAPABILITY_GRAPH.md`). The projection is
git-ignored candidate output, never tracked reconciliation authority.

## Thin composition

Use `skill:technical-product-company-os` to rank and sequence existing families.
Do not create a second portfolio catalog or a second ML family. New mesh roles
are not required; full-stack mesh roles already exist.

## Pilot coverage note

`pilot:dad-agent-family-portfolio` should list every implemented core family that
DAD itself exercises, including `family:ml-workflow` and
`family:platform-cloud-sre`.

## Stop conditions

- No global skill checkout or plugin installation from this note.
- No daemon/scheduler activation.
- No recreation of obsolete `machine-learning-family`.
