# Phase 13 Local Transport Acceptance Evidence

Date: 2026-07-07

## Accepted Scope

- AI runtime authority is agent-agnostic: AGENTS.md, DAD CLI lifecycle, schemas,
  audit records, Git/CI gates, and human gates remain the control plane.
- Claude support remains a wrapper over neutral lifecycle hooks, not a policy
  authority.
- Local runtime state is routed through the active data root when initialized.
- Daemon/readiness commands surface heartbeat and daily-review state.
- `dad-journal` support is data-only and uses checkpoint, repo-status, and
  remote-outbox quarantine flows.
- Downstream transport rollout is queue-driven through reviewed, non-protected
  policy records.
- Internal integrations default to MCP resources/tools/prompts before direct
  APIs. Direct APIs remain adapter fallback only and do not become DAD
  authority.

## Deferred Scope

- Cloudflare relay remains design-only until the phase-10a cloud/human gate.
- No downstream repo enrollment update is applied by this stack; generated
  plans require reviewed approval before mutation.
- `dad-journal` repository creation, daemon scheduler installation, and live
  data migration remain operator-approval steps.

## Evidence

- PR 13 adds the AI-agnostic lifecycle adapter and optional
  `agent_runtime_policy`.
- PR 14 adds the data-root transport core and migration/audit surface.
- PR 15 adds daemon cycle, heartbeat, daily review, and readiness checks.
- PR 16 adds `dad-journal` checkpointing and remote-outbox quarantine.
- PR 17 adds rollout docs, upgrade queue planning, and MCP-first integration
  policy.

## Validation

- `python -m pytest tests/test_transport.py tests/test_enrollment.py` passed.
- `python -m pytest tests/test_transport.py tests/test_enrollment.py tests/test_database_learning.py tests/test_data_root_generated_writers.py tests/test_agent_lifecycle.py tests/test_dad_local_deployment.py` passed.
- `python -m pytest tests/test_ai_navigation.py tests/test_validation_roadmap.py` passed after regenerating repo-inventory and Rust shadow-parity evidence.

## Remaining Risks

- The stacked PRs must merge in order to preserve schema and CLI surface
  compatibility.
- Generated evidence can drift when navigation/docs change and must be
  refreshed before release.
- Operator rollout commands must be reviewed before `--apply` on data migration,
  journal checkpointing, daemon installation, or downstream enrollment updates.
