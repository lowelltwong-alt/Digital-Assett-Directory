---
name: global-personal-skills-gpt
description: Govern deterministic inventory, inert content-addressed archival, delta review, graph queries, and reviewed portable exports for explicitly allowlisted global personal skills without creating a second active source.
---

# Global Personal Skills GPT

Use `asset-dir personal-skills` to inventory, status, snapshot, list, query,
graph, or export Lowell's allowlisted global personal skills. The live runtime
skill root remains source authority. Archive blobs are local-only, inert, and
never auto-discovered, installed, or executed.

## Controls

- Read only direct-child entries in `config/global-personal-skills.json`; deny
  wins and unknown origins remain metadata-only.
- Reject link/junction traversal, unstable reads, unsupported binaries,
  oversized files, sensitive paths, and secret-like content. Do not archive a
  partially safe revision.
- Keep stable skill identity separate from per-skill revision identity and
  shared blob hashes. Missing sources never delete history.
- Require an initialized `DAD_DATA_ROOT` for recurring writes. Local archive
  bodies never enter journal replication; portable exports require a named
  reviewer and approval ID and exclude local absolute paths.
- Treat graph presence, equal hashes, adaptations, checkout pointers, and
  portability as candidate evidence, not approval or installation.

## Steward Routing

Run deterministic status first. Luna-low reviews sanitized delta metadata only.
Use Terra for integration or portability ambiguity. Use Sol only for unresolved
load-bearing architecture. Any model at ultra effort requires explicit human
permission for that exact attempt. Follow `subagent-peer-review-routing`; do
not duplicate its thresholds.

Never edit the live global skills from the archive. Validate focused tests,
schemas, the agent-skill library, DAD validation, and roadmap checks before
publishing a change.
