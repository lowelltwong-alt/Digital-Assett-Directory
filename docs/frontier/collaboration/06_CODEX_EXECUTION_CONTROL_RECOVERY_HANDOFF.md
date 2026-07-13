# Codex Execution-Control Recovery Handoff

Date: 2026-07-13
Branch target: `codex/portfolio-os-kernel-opus`
Recovery root: `.tmp/dad-portfolio-os-recovery`
Status: validated and independently approved as a disabled shadow kernel; not replayed to the read-only target worktree

## Outcome

This slice adds the first human-gated execution-authority plane beneath the
Portfolio OS. It can record and project bounded leases and exact dispatch
revisions, but it cannot execute, launch an agent, mutate Git, use the network,
or schedule work. Every normal CLI projection is deny-all and
`dispatch_allowed` is always false.

The independent reviewer initially blocked the design with reproduced authority
counterexamples. The revised fold closes them with composite identities,
immutable revisions, byte-exact scope hashes, typed event-digest attestations,
fold-time semantic revalidation, historical filtering, active-only
supersession, and attempt-journal-dependent reconciliation.

## DAD records

- Preflight session: `dad:session:4a176236-0e5f-4529-b9e3-df6cf4608711`
- Trace: `dad:trace:a006b227-f93a-58cd-a257-e164e7afb22a`
- Postflight handoff: `dad:handoff:738d2211-f158-5f70-aa3a-622a103344bd`
- Learning record: `dad:lesson:9f5f3583-4c03-52de-8260-68acc197f589`

## Intentional delta

- `src/digital_asset_directory/portfolio_events.py`
- `src/digital_asset_directory/portfolio_execution.py`
- `src/digital_asset_directory/cli.py`
- `schemas/portfolio-execution-control-event.schema.json`
- `registry/schema-registry.json`
- `tests/conftest.py`
- `tests/test_portfolio_execution_control.py`
- `tests/test_portfolio_execution_authority_invariants.py`
- `tests/test_portfolio_workstreams.py`
- `tests/test_ai_navigation.py`
- `assets/agent-skills/personal-project-management-ops/references/PROJECT_MANAGEMENT_CONTRACT.md`
- `registry/agent-skill-library.json`
- `docs/DAD_PORTFOLIO_AI_OPERATING_SYSTEM_PLAN.md`
- `docs/frontier/collaboration/05_EXECUTION_LEASE_AND_DISPATCH_CONTROL.md`
- `docs/TESTING_AND_ORCHESTRATION.md`
- `AI_TABLE_OF_CONTENTS.md`
- `MACHINE_NAVIGATION_MANIFEST.json`
- `registry/ai-navigation-registry.json`
- this handoff

## Validation

Passed:

- 21 execution-control and authority-invariant tests;
- 111-test Portfolio/event/attention/trigger/navigation/skill focused gate;
- Ruff on changed Python and tests;
- Python compilation for execution/events/CLI modules;
- agent-skill library validation: 16 valid;
- DAD validation: 241 checked, zero warnings/errors;
- roadmap check `--no-update`: exit zero;
- JSON parsing for changed schemas and registries; and
- independent correctness replay and disabled-shadow approval.

Not passed:

- The current full suite hung in
  `test_doctor_uses_custom_locator_from_non_dad_repo` after a Windows `.cmd`
  timeout left a CPU-active descendant. The process tree was terminated. This
  run is invalid and is not claimed as evidence. The last pre-slice full-suite
  evidence was 1,183 passed in 685.9 seconds.

## Replay

The target worktree was read-only under this session's sandbox. A relative
unified patch is packaged beside this handoff in the recovery tree. From the
target worktree, first inspect its dirty state and then run:

```powershell
git apply --check --ignore-space-change --ignore-whitespace '<absolute recovery path>\portfolio-execution-control-recovery.patch'
git apply --ignore-space-change --ignore-whitespace '<absolute recovery path>\portfolio-execution-control-recovery.patch'
```

After replay, rerun the 111-test focused gate, Ruff, DAD validate, and roadmap
check. Do not create an executor next. The next architecture gate is a trusted
human-verification provider bound to the DAD authority domain, followed by a
non-authoritative attempt journal and single-winner dry-run claim protocol.
