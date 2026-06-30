# Repo Completion Proof Check V1

## Summary

Implemented a generated, fail-closed proof checker for repo-completion waves.
The checker exists so future agents can distinguish:

- a generated wave plan;
- actual proof that a wave is complete;
- the next missing human gate or generated artifact.

It does not approve actions, execute commands, read source contents, mutate
source repos, call GitHub, call models, install hooks, or mark roadmap phases
complete.

## Command

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend repo-completion-proof-check --dashboard-limit 500 --per-wave-repo-limit 25
```

Generated outputs:

```text
processed/reports/repo_completion_proof_check.md
processed/reports/repo_completion_proof_check.json
```

## Methodology

Methodology version: `repo-completion-proof-check-v0.1`

The proof checker reads only generated DAD surfaces:

- repo completion wave plan;
- repo completion dashboard summary;
- lesson automation decision ledger;
- lesson automation execution plan;
- priority content observations;
- priority content lesson candidates;
- learning-rule promotion candidates.

It reports proof status for each wave:

- `complete`;
- `blocked`;
- `blocked_by_prior_wave`.

The current wave is the first wave that is not complete.

## Live Result

The live proof check reported:

- wave count: 6;
- complete wave count: 0;
- blocked wave count: 6;
- current wave: `content_read_approval_wave`;
- current status: `blocked`;
- safe to advance: `false`;
- source repos mutated: 0;
- content files read: 0;
- GitHub/model calls: 0 / 0;
- roadmap phases marked complete: 0.

The missing proof for the current wave is:

1. Approve one bounded content-read decision row with exact repo keys,
   categories, byte/file caps, approval id, and redaction.
2. Regenerate the execution plan after a reviewed content-read approval.
3. Run the approved bounded priority-content-extract command, writing
   generated observations only under `processed/`.

## Red Team

- Risk: a proof check could be mistaken for authorization.
  Guard: the authority boundary and report say it is evidence only and grants no
  permission to read content or mutate repos.
- Risk: later waves could appear blocked for reasons that are downstream of wave
  1.
  Guard: later waves use `blocked_by_prior_wave` until earlier proof is
  complete.
- Risk: generated absence could be mistaken for source truth.
  Guard: missing proof means DAD lacks proof, not that the source repo lacks the
  asset.
- Risk: a future agent could skip the human gate and run extraction anyway.
  Guard: the current wave explicitly requires a reviewed decision row, execution
  plan readiness, and generated observations before advancing.

## Current Boundary

The next real work remains human-gated. The proof checker says the safest next
step is still to review `lesson-automation-decision-001` in the approval packet.
No content extraction was run in this implementation.

## Validation

Focused validation:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests\test_repo_completion.py tests\test_lesson_automation_coverage.py
python -m ruff check src\digital_asset_directory\repo_completion.py src\digital_asset_directory\cli.py tests\test_repo_completion.py src\digital_asset_directory\lesson_automation_coverage.py
```

Results:

- focused pytest: 10 passed;
- focused ruff: all checks passed.

Full validation was run after implementation and recorded in the agent
postflight for this session.

