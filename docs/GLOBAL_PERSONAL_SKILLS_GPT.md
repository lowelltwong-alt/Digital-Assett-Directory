# Global Personal Skills GPT

Status: candidate DAD control plane under independent review for deterministic,
inert archival of Lowell's explicitly allowlisted global personal Codex skills.

## Authority And Boundary

`%CODEX_HOME%/skills` (normally `~/.codex/skills`) remains the only active source
authority. DAD never edits that root from archive state. Archive blobs are not
placed under a runtime skill-discovery directory, are never executed, and are
not Agent Skill Library checkouts.

`config/global-personal-skills.json` is default-deny. Only named direct-child
personal skills are read. `.system`, `codex-primary-runtime`, plugin caches,
third-party roots, unknown origins, links/junctions, generated caches, binaries,
oversized files, sensitive paths, and secret-like content are excluded or
blocked. Unknown origins are recorded by directory name only; their bodies are
not inspected.

## Storage And Identity

Recurring state resolves through the initialized-root/legacy transport policy.
Archive bodies use the reviewed local-only logical surface
`personal_skill_archives` at `DAD_DATA_ROOT/private/personal-skills`. That
surface participates in copy/verify data-root migration but is deliberately not
in `DATA_PLANE_PATHS`, so the Git-backed DAD journal cannot replicate it.

Recurring `daily` and default `snapshot` writes fail closed unless the exact hub
has an initialized data-root marker. Read-only inventory, status, list, query,
and graph access retain legacy fallback. A manual bounded snapshot may opt into
legacy write explicitly; that is not the automation path.

Identity layers are separate:

- `personal-skill:*` is the stable allowlisted skill identity;
- each file blob is stored once by exact SHA-256;
- the canonical sorted path/hash/size tree has its own SHA-256;
- `dad:personal-skill-revision:*` binds one stable skill identity to one tree
  hash;
- append-only run and event records preserve observations, disappearance, and
  reappearance;
- mutable current pointers are regenerable convenience state and never source
  authority.

Changed content creates a revision. Identical content deduplicates blobs and
reuses the per-skill revision. Disappearance changes pointer status but never
deletes revisions or blobs.

## Graph

The generated local graph distinguishes `personal_skill`,
`active_personal_source`, `personal_source_observation`, `archived_revision`,
`portable_export`, `dad_adaptation`, `checkout_pointer`, and `runtime` nodes. Candidate edges use
the closed registries and may include `snapshot_of`, `revision_of`,
`adapted_as`, `portable_to`, `loaded_by`, and `duplicate_content_of` alongside
`derived_from`.

No automatic `supersedes` edge is emitted: replacement needs declared reviewed
lineage. Graph presence, equal hashes, target runtime, a DAD adaptation, or a
checkout pointer never proves approval, installation, compatibility, canon, or
authority transfer. Absolute paths are absent from graph output.

## Portable Export

`personal-skills export` requires `reviewed_by` and `approval_id`. A bundle:

- derives from one validated source snapshot;
- separates portable procedure files from runtime adapters;
- omits source-runtime adapters by default;
- redacts known local roots and fails if any Windows or home absolute path
  remains;
- has sorted paths, fixed ZIP timestamps/modes, and deterministic bytes;
- carries candidate compatibility language and does not install anything.

Runtime-neutral DAD adaptations remain separately registered under
`assets/agent-skills/`; they are not rewritten archive snapshots.

## CLI And Required Queries

```powershell
asset-dir personal-skills inventory
asset-dir personal-skills status
asset-dir personal-skills diff
asset-dir personal-skills snapshot
asset-dir personal-skills list
asset-dir personal-skills query --health unsafe
asset-dir personal-skills query --health stale
asset-dir personal-skills query --health unvalidated
asset-dir personal-skills query --artifact-role source_snapshot
asset-dir personal-skills graph
asset-dir personal-skills export --skill-id <id> --target-runtime <runtime> --reviewed-by <name> --approval-id <id>
asset-dir personal-skills daily
```

These answer: active global personal skills and revisions; deltas since the last
run; source snapshot/adaptation/duplicate relationships; reviewed path-free
portable export; and stale, unsafe, unknown-origin, or unvalidated state.

## Steward And Automation

Daily work is deterministic first. `daily` snapshots only on deltas and only
under an initialized data root. Sanitized relative paths, hashes, statuses, and
validation reasons may route to Luna-low. Terra reviews integration or
portability ambiguity. Sol is reserved for unresolved load-bearing
architecture. Any model using ultra effort requires explicit human permission
for that exact attempt.

Automation must invoke the stable post-merge hub/shim, never an ephemeral
worktree. A blocked data root or unsafe/unknown-origin row is surfaced for
review; it never widens read scope or writes live skills.

## Rollback And Kill Criteria

Rollback disables automation and removes the control-plane/skill registry rows
and CLI route; immutable local archive state may remain for reviewed recovery.
Stop recurring work on any path escape, link/junction, secret-like content,
unstable read, local-path export leak, schema failure, blob collision, journal
replication of archive bodies, or live-skill mutation.
