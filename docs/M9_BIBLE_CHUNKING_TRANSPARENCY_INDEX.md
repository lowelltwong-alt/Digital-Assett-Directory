# M9 Bible chunking transparency index

**Status:** active local-candidate preparation; no production or canonical release  
**Scope:** 66 Protestant books  
**Public surface:** sanitized documentation on the DAD repository draft PR

## What this publishes

This package documents how the Bible chunking work is organized, how the role and checker mesh is saved, what evidence has been completed, and which limits remain. It is intended to let future M7, M8, and M9 reviewers inspect and improve the workflow without reconstructing it from private task history.

The package contains:

- `docs/BIBLE_CHUNKING_REVIEW_MESH.md` — provider-neutral workflow, chunk contract, semantic exhibit handling, role categories, independence, and improvement loop.
- `docs/M9_BIBLE_CHUNKING_TRANSPARENCY_INDEX.md` — this status and publication map.
- `docs/M9_SUBAGENT_ROLE_CATALOG.md` — function/subject categories, saved instruction fields, and the nonauthor checker path.
- `docs/M9_CHECKPOINT_LINEAGE.md` — hash-only checkpoint and restart-prompt lineage.
- `docs/M9_LIMITS_AND_EVIDENCE.md` — retained limits, incidents, validation blocker, and current qualification boundary.

The DAD branch is `codex/m9-bible-chunking-workflow`; the review surface is [draft PR #97](https://github.com/lowelltwong-alt/Digital-Assett-Directory/pull/97). The PR is intentionally open, draft, and unmerged.

## Current progress

Eight books have local candidate indexes with 195 chunks total:

| Canonical order | Book | Chunks | State |
|---:|---|---:|---|
| 1 | Genesis | 55 | local candidate with retained holds |
| 2 | Exodus | 21 | local candidate with retained holds |
| 3 | Leviticus | 25 | local candidate with retained holds |
| 8 | Ruth | 11 | local candidate with retained holds |
| 25 | Lamentations | 14 | local candidate with retained holds |
| 27 | Daniel | 10 | local candidate with retained holds |
| 43 | John | 53 | local candidate with retained holds |
| 57 | Philemon | 6 | local candidate with retained holds |

The table is rendered in canonical 66-book order even though quality probes may finish out of order. Stable book, chapter, chunk, source-revision, and typed-byte identities are the comparison authority across M7, M8, and M9.

Joshua (canonical order 6) has a staged source packet and frozen role proposals. Its deterministic structural comparison retained 37 distinct proposed spans, but model adjudication and the separate semantic checker remain pending because two attempts were stopped by account capacity before execution. Joshua is not counted as a reviewed local candidate.

## Source and quality boundary

The operating anchors are WLC/OSHB and SBLGNT, with WEB Classic kept as a separate English alignment witness. Source selection and metadata do not decide original readings, doctrine, canon boundaries, or faithfulness. Every candidate retains source revision, raw-byte/Unicode provenance, annotation gaps, contrary evidence, alternatives, appeals, holds, and typed dependencies.

OCR is not implemented here. The public method records what an OCR input must preserve: file identity and revision, original bytes and Unicode, page/region provenance, stable coordinates, and semantic exhibit separation when a source labels exhibits indirectly. A semantic exhibit boundary must remain explicit even when the source uses another label.

## Qualification boundary

The published material is a workflow and transparency record. No clean author, production artifact, scheduler, successor, canonical promotion, public release, or repository-wide clean-validation claim is made. Raw source files, private paths, full transcripts, raw review rows, and task-local payloads remain outside the DAD repository.

The workflow is provider-neutral. It does not require an API or MCP to create a local candidate; the GitHub connector is used only for this documentation publication and read-back.

## Updating this surface

A workflow change should update the role catalog and limits record, add a new checkpoint hash, and keep the PR reviewable. Reviewers should compare the changed public document with its private source receipt, verify the exact remote bytes, and preserve unresolved limits instead of converting them into acceptance claims.
