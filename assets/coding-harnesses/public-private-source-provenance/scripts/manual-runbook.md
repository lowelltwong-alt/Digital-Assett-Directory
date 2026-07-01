# Manual Runbook

1. Canonicalize source repo, target repo, visibility, and return address.
2. Treat unknown, private, internal, or restricted origin as not public-safe by default.
3. Screen for credential and PII patterns as best-effort triage.
4. Reject raw blobs, copied private rows, and long free-form payloads for public delivery.
5. Require explicit human release before private-origin mail reaches public-facing repos.

This runbook is screening guidance, not a guarantee that content is safe.
