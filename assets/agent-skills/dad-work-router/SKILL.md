---
name: dad-work-router
description: Route material coding, governance, registry, and cross-repository work through DAD preflight, reusable assets, proportional review, and postflight.
---

# DAD Work Router

1. Locate the repository front door, authority contract, and DAD enrollment
   boundary before material work.
2. Run the repository's DAD preflight. If DAD is unavailable, honor the
   repository's fail-closed boundaries rather than inventing authority.
3. Search the DAD agent-skill library and asset registries before creating an
   agent, skill, template, algorithm, or workflow. Reuse the narrowest
   reviewed asset that fits.
   For CI workflows, module test ownership, path filters, required checks,
   monorepos, or cross-repo release lanes, route through
   `dad-ci-module-boundary-governance` and its deterministic validator.
   For cross-repository learning ingestion or a DAD-owned copy of reusable
   source knowledge, route through `governed-source-knowledge-ingestion` and
   preserve the source authority, privacy allowlists, candidate-only status,
   and human promotion gate.
4. State the scope, validation plan, and stop conditions. Local repository
   authority remains controlling.
5. Use proportional independent review lanes for material work. Keep writes
   non-overlapping when work is delegated.
6. Activate learning, asset-discovery, or iteration work only when their
   specific trigger evidence exists.
7. Close with DAD postflight, exact validation evidence, unresolved risks, and
   outcomes for any recommendations used, ignored, failed, or harmful.

Never move client payloads, secrets, private source rows, or long chat
transcripts into DAD. Store privacy-safe metadata, hashes, scoped lessons, and
evidence references only.
