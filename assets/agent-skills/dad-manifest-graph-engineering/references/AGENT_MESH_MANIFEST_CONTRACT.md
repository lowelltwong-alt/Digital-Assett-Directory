# Task-Local Agent Mesh Manifest Contract

Use this task-local artifact to preserve plan-to-execution continuity. It is
candidate coordination evidence, not an agent registry, dispatch instruction,
approval, or authority grant.

Validate with `scripts/validate_agent_mesh_manifest.py MANIFEST`. For execution,
use `--prior PRIOR_MANIFEST`. The canonical digest is SHA-256 over UTF-8
canonical JSON with keys sorted, compact separators, Unicode preserved, and the
top-level `manifest_digest` field excluded.

## Planning revision

Emit an append-only revision conforming to
`references/agent-mesh-manifest.schema.json` with:

- `schema_version`, stable `mesh_id`, unique `revision_id`, optional
  `supersedes_revision_id`, task identity, source-snapshot digest, and status;
- one row per planned role containing `role_id`, `why_needed`, `mission`,
  `inputs`, `dependencies`, `authority`, `model_effort_class`,
  `writer_checker_relation`, `acceptance_conditions`, `stop_conditions`, and
  `handoff`;
- the single writer role, distinct checker role, delegation-depth limit,
  non-overlap statement, unresolved decisions, and manifest digest.

Use provider-neutral model classes such as `deterministic`, `low`, `medium`,
`high`, or `frontier_manual`. A model class is a cost and uncertainty budget,
not a vendor or authority designation.

## Execution reconciliation

Before execution, reconcile every planned role with exactly one disposition:

- `reused`: mission and boundary are materially unchanged;
- `replaced`: exactly one new role assumes one prior role; preserve both role
  IDs, reason, and evidence;
- `split`: at least two new child role IDs replace one over-broad prior role;
  the prior role ID cannot survive as a child;
- `added`: new evidence requires one or more new roles absent from the plan;
- `removed`: evidence proves the role unnecessary and maps it to no current role;
- `blocked`: its inputs, authority, or independence are unavailable.

Record evidence, replacement or split IDs, dependency changes, handoff changes,
and whether drift is material. Append a new manifest revision for any role,
authority, writer/checker, dependency, acceptance, stop, or handoff change that
could alter execution or review. Never rewrite the prior revision.

Mark `replaced`, `split`, `added`, and `removed` as material drift. For `reused`,
derive the drift flag from mission, input, dependency, authority, acceptance,
stop, and handoff differences. Dependency graphs must be acyclic. Every proof
obligation must use the manifest's single top-level checker role.

## Postflight decomposition grade

Grade role coverage, scope separability, dependency correctness, writer/checker
independence, acceptance and stop-condition quality, handoff completeness,
proportional effort, blocked-role visibility, and reconciliation completeness.
Record evidence, counterevidence, limitations, and the independent checker.
Self-grade is calibration evidence only and cannot promote the mesh or conceal
an omitted, removed, or blocked role.
