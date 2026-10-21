# J-110 — Bind the Temporary Expansion Freeze

## Contract

- Phase: P1
- Depends on: accepted J-100 receipt
- Owner: `bounded-writer`
- Checker: `independent-checker`
- Lease: 45 minutes; heartbeat every 10 minutes
- Attempts: one original plus one bounded repair
- Idempotency key: `dad-high-value-recovery-v1:J-110:r1`
- Auto-advance: no; human gate H-003

## Goal

Make the temporary recovery freeze visible, expiring, reviewable, and hard to
silently bypass without building a new product control plane.

## Inputs

- H-001, H-002, H-003 receipts;
- accepted J-100 baseline;
- `AGENTS.md`, current governance/key-value contracts, and this campaign.

## Outputs

- `docs/DAD_HIGH_VALUE_RECOVERY_FREEZE.md`
- a narrow marker/pointer in `AGENTS.md` if Lowell approves that governing-file
  change
- required key-value change-log row for the expiry and scope, if applicable
- checker receipt under `checks/evidence/phase-1/`

## Procedure

1. Copy the approved allowed/prohibited work, owner, start, expiry, exception
   rule, and revocation rule exactly; do not broaden H-003.
2. State that there may be at most one active recovery build and one bounded
   pilot.
3. Define an exception as a signed, expiring receipt with exact files/outcome;
   the producer cannot self-approve.
4. Point to this campaign from the existing agent contract only if approved.
5. Do not add a new command, registry family, schema family, scheduled check, or
   dashboard to enforce the freeze.
6. Run navigation/governance validators and an independent policy review.

## Acceptance checks

- Owner and expiry are exact and no more than 90 days after launch.
- Allowed/prohibited categories match H-003.
- Emergency security/privacy work has a bounded exception path.
- Revocation stops the campaign and requires a revised manifest.
- The freeze itself creates no execution authority.
- Existing repo validation remains green.

## Failure and repair

Ambiguous scope or an absent H-003 receipt is `blocked_human`. A bounded repair
may correct wording that does not match the receipt. Do not infer approval.

## Handoff

Index the freeze digest, approval, checker receipt, expiry, and exception status.
J-200 may begin only after the owner accepts the freeze.

