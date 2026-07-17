# Governed Source Knowledge Ingestion

Asset ID: `governed-source-knowledge-ingestion`

This provider-neutral capability inventories reusable knowledge in a source
repository, preserves source authority, creates candidate-only normalized
records, and projects them into DAD's registered graph surfaces. It extends the
existing priority-content learning pipeline; it does not promote records into
global lesson, asset, skill, agent, or graph-edge authorities.

## Safety contract

- Source repositories are read-only.
- Every tracked item receives a disposition.
- Prohibited paths are represented by opaque path hashes and aggregate families;
  their names and content are not stored in DAD.
- Content reads and exact copies require separate explicit allowlists.
- Exact copies must pass secret, absolute-path, binary, and privacy checks;
  source-specific asset, legal-edge, and witness registries remain normalized
  and hash-only even when their reusable fields are approved for extraction.
- UTF-8 text hashes canonically normalize CRLF and CR to LF so Windows checkout
  settings cannot create false provenance drift; binary content remains rejected.
- Dirty and untracked source artifacts remain provisional evidence.
- Snapshots are internal-only until license and human promotion review completes.
- Supersession adds a new immutable snapshot; it never overwrites source meaning.
- Later source-worktree drift makes a snapshot historical, not corrupt; record the
  drift as metadata and require a separately reviewed snapshot for newer state.

## Commands

```powershell
$env:PYTHONPATH='src'
python scripts/ingest_source_knowledge.py build `
  --source-root '<approved-source-repo>' `
  --destination 'assets/source-knowledge-ingestion/snapshots/<source-id>'
python scripts/ingest_source_knowledge.py validate `
  --destination 'assets/source-knowledge-ingestion/snapshots/<source-id>'
```

The Albert snapshot is the first revision-bound example. Its manifest records
4,426 tracked paths, 1,424 candidate paths, 3,002 privacy exclusions, 552
normalized records, safe copy hashes, the source commit, and the dirty-state
digest. `ALBERT-LESSON-072` is linked to DAD's existing CI module-boundary rule
instead of being registered as a duplicate lesson.

## Promotion and rollback

Promotion is always a separate human decision into the relevant existing DAD
registry. To roll back an ingestion revision, stop routing to its snapshot ID,
mark it superseded/rejected in the source-ingestion registry, and rebuild the
generated graph surface from the prior accepted snapshot. Do not delete the
old observation or mutate the source repository.
