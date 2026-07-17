# DAD Contract Check

Status: warn-only probation (see `registry/contract-check-policy.json`).

## Problem

The DAD lifecycle (preflight → work → postflight) reaches only cooperative
agents. A cold agent that never reads `AGENTS.md` leaves no session, so
session-based gates pass silently. The contract check closes that hole by
keying on the artifact every author must produce — the diff — instead of on
agent behavior.

## How it works

1. `.ci/module-boundaries.yaml` module roots + workflow paths, plus policy
   `extra_protected_globs`, define the protected surface. The policy never
   keeps a second competing path list.
2. Changes touching protected paths must carry a `DAD-Session:` trailer in a
   commit message or PR body. `asset-dir agent postflight` prints the exact
   trailer to paste.
3. `DAD-Bypass: <named-human>: <reason>` is always allowed and always logged —
   the escape hatch required by the downstream-governance bypass policy.
4. Chokepoints running the same checker:
   - CI: `.github/workflows/dad-contract-check.yml` (advisory,
     `continue-on-error`, non-required check);
   - pre-push: warn-only step in `.githooks/pre-push` after the existing
     open-session gate;
   - on demand: `asset-dir agent contract-check`.

## What a trailer does and does not prove

A trailer is a decision point, not cryptographic proof. It converts silent
governance drift into either compliance or an auditable lie. Hub-side
reconciliation (daemon lane) audits trailer identifiers against the session
store: unknown IDs and one ID reused across many pushes are flagged.

## Probation → promotion

Warn mode never blocks. Promotion to enforce is a reviewed flip of
`mode` in `registry/contract-check-policy.json`, gated by the probation
criteria recorded there (observation window, false-positive rate, cold-agent
simulation, human sign-off). Noisy enforcement downgrades per
`docs/HARNESS_VS_DETERMINISTIC_ENFORCEMENT.md`.
