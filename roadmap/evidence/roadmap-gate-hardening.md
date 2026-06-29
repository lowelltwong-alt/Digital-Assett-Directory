# Roadmap Gate Hardening Evidence

Status: implemented remediation after Claude post-merge red-team.

Date: 2026-06-29

## Trigger

Claude's post-merge review found that roadmap human gates were satisfied by
`status="verified"` plus a matching `phase_id`, even when the reviewer was an
agent such as `codex`. That made "human gate" self-attestable by the same agent
doing the work.

Claude also found that Phase 4 and Phase 5 were computed `complete` even though
the named capabilities remained deferred:

- external embeddings or AI-assisted enrichment;
- scheduled scans;
- external missing-part research automation;
- notification channels;
- autonomous promotion.

## Risk Tier

High. This affects roadmap status, future-agent trust, external-call safety, and
public-release posture.

## Implemented Remediation

- Human gate verification now requires an explicit human reviewer.
- Agent reviewers such as `codex`, `claude-code`, automation, bots, or systems
  no longer satisfy human gates by themselves.
- Roadmap check output now includes unverified human-gate details with reviewer
  and rejection reason.
- Roadmap phases can use `boundary_deferred` to distinguish a documented safe
  boundary from delivered capability completion.
- Phase 4 and Phase 5 are declared `boundary_deferred`, with tracked evidence
  files as anchors, but their human gates remain unverified until a human signs
  them directly.
- Phase 4 and Phase 5 evidence prose was revised to say boundary-deferred, not
  complete.
- `asset-dir research missing` now requires `--enable-external` before any live
  GitHub API call can run.
- Documentation now names the explicit `--enable-external` requirement and keeps
  scheduled scans behind a future human gate.

## Current Roadmap Consequence

After this remediation, `roadmap check --no-update` intentionally no longer
computes every phase complete.

Current unverified human gates include:

- Phase 1 source mutation / changed-during-scan summary review, because the
  existing record was agent-observed;
- Phase 3 pre-push enforcement, central lesson arrival, and bypass/failure
  behavior, because the existing records were agent-observed;
- Phase 4 and Phase 5 conservative boundary gates, because the existing records
  are boundary-deferred or agent-authored rather than direct human verification.

This is a correction, not a regression. It prevents future agents from treating
agent-authored evidence as human approval.

## Validation

Commands run:

```powershell
python -m pytest
python -m ruff check src tests scripts noxfile.py
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli validate
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli roadmap check --no-update
```

Results:

- `python -m pytest`: `166 passed`
- `ruff`: all checks passed
- `validate`: valid, `checked_count=65`, `errors=[]`
- `roadmap check --no-update`: command passed and reported unverified human
  gates instead of silently counting agent-authored gates as complete

## Remaining Human Decisions

Lowell can later verify specific gates directly after reviewing the evidence.
Until then, the safer machine state is `awaiting_human_gate` or
`boundary_deferred`, not `complete`.

Future external research, scheduled scanning, notifications, embeddings, model
enrichment, and autonomous promotion still require separate human gates.
