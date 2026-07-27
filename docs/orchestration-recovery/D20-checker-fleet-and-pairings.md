# D20 — Checker fleet availability and worker/checker pairing matrix

Status: **OPEN — pairing matrix proposed, awaiting owner confirmation of available subscriptions**
Raised: 2026-07-09 by Fable (boss)
Owner: Lowell T. Wong

## Question

Which model subscriptions are available to run CHECKER sessions, and is the proposed pairing
matrix approved? (T1 requires the checker to EXECUTE the work; T2 requires the checker to be a
different model than the worker; a checker that only reads the worker's report fails.)

## Proposed pairing matrix

| Worker | Allowed checkers (preference order) | Never |
|---|---|---|
| Composer 2.5 (cheap) | GPT-5.5 → Claude | Composer checks Composer |
| GLM 5.2 (cheap, foreign) | GPT-5.5 → Claude | GLM checks anything of GLM's; GLM as sole checker of any merge-bound task |
| GPT-5.5 (hard) | Claude (must execute, not just review) | GPT-5.5 checks GPT-5.5 |
| Fable/Claude (boss specs, packet) | GPT-5.5 red-team pass | self-approval |

Additional rule: GLM-authored code additionally passes the backdoor scan (T6) regardless of
who checks it.

## Resolution — 2026-07-09 (fleet confirmed by owner: Composer 2.5, GPT-5.5, GLM 5.2, Claude/Fable)

Confirmed pairings (checker ≠ worker family; Claude reserved for hard-task checks to avoid
bottlenecking on cheap volume):

| Task class | Worker | Checker | Extra gate |
|---|---|---|---|
| cheap (docs/schema/fixtures/tests) | Composer 2.5 | **GPT-5.5** | — |
| cheap, GLM-authored | GLM 5.2 | **GPT-5.5** | **backdoor scan (T6) before merge** |
| hard (kernels/refactors/MC) | GPT-5.5 | **Claude (must EXECUTE)** | — |
| boss packet/specs | Fable | GPT-5.5 red-team pass | — |

Per-task assignments for the seeded board:
- T-0001, T-0002, T-0010: Composer → GPT-5.5.
- T-0003, T-0011: GLM → GPT-5.5 (+ backdoor scan).
- T-0004, T-0005, T-0006, T-0009, T-0012: GPT-5.5 → Claude.
Integrator (merge + `done`): Fable/owner today.

Status: **RESOLVED** (owner may override any single pairing).
