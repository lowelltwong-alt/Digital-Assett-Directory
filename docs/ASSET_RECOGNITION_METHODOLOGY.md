# Asset Recognition Methodology

Status: candidate deterministic method for finding useful DAD assets without
copying private contents.

## Purpose

DAD needs to recognize good digital assets while scanning or reviewing repos:
agent instructions, schemas, registries, prompts, harnesses, governance maps,
data maps, templates, evals, and workflow docs. Recognition is not promotion.
It creates candidate pointers with source context so a human or reviewed agent
can decide whether the asset should be saved, adopted, generalized, or ignored.

## Source Of Truth

- Methodology: `registry/asset-recognition-methodology.json`
- Schema: `schemas/asset-recognition-methodology.schema.json`
- CLI: `asset-dir dad asset-recognition`
- Candidate scout: `asset-dir dad asset-scout --repo <repo> --task "<task>"`

The scout is path/metadata-only by default. It does not copy file contents,
private rows, credentials, secrets, or large raw blobs into reports.

## Recognition Loop

1. Read the repo front door, context map, and task.
2. Scout candidate asset paths using controlled locations and signals.
3. Label each candidate as reviewed later, candidate-library-asset,
   save-for-future, reject, or needs-human-review.
4. Preserve source repo, return address, path pointer, score rationale, and
   public/private boundary.
5. Promote only through the reviewed DAD asset, offering, skill, harness, or
   template registry.

## High-Value Patterns

- Instructions that force agents to consult DAD before material coding.
- Test, eval, parity, benchmark, or review harnesses.
- Schemas and registries that encode reusable contracts.
- Templates and prompts that preserve repeatable workflows.
- Governance, data-flow, provenance, and public-release maps.
- Orphan assets that become useful when connected to a current task.

## Boundaries

Scores are candidate evidence. They do not prove truth, value, safety,
licensing, or compatibility. Secret-like paths are downgraded or excluded and
must not be shared through public-facing mail.

README-only harness folders and explicit `.stub.py` template files are useful
navigation or scaffold evidence, but they are downgraded so they are not
mistaken for implemented scripts, evals, examples, or runtime assets.
