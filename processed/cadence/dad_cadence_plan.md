# DAD Cadence Plan

Generated: 2026-07-01T21:33:33.483818+00:00

This DAD report is central candidate metadata only. It does not authorize enrollment, delivery, hooks, source edits, or writes to downstream repos.

## Daily Mail

- mail collect from reviewed repo outboxes
- mail route with provenance and public-release gates
- mail deliver only to .digital-asset/mail/** for policy-approved repos
- mail digest freshness update

Preflight behavior: Warn only when mail digest is older than 24 hours.
Write boundary: `.digital-asset/mail/**`

## Weekly Library Checks

- asset offering freshness check
- agent skill update/retirement/replacement check
- coding harness update and research-opportunity check
- template/reference architecture update check
- governance-map and data-map drift check
- enrollment contract update-plan generation

Preflight behavior: Surface stale weekly checks as warnings; do not run heavy scans on every preflight.
Write boundary: central reports plus candidate mail; enrollment apply still needs approval

## Blocked Operations

- no normal recurring source edits
- no hook installation outside approved enrollment apply/update-apply
- no private/internal/restricted/unknown origin delivery to public-facing repos without release
- no broad discovered-repo delivery without reviewed policy
