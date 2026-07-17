# Albert Source Knowledge Ingestion Report

Report ID: `dad:report:albert-source-knowledge-ingestion:2026-07-16`

## Outcome

DAD now has its own privacy-safe, revision-bound candidate copy of the reusable
knowledge discovered in Albert. The snapshot accounts for all 4,426 tracked
paths without mutating Albert: 1,424 reusable/governance candidates and 3,002
privacy exclusions. Three approved untracked CI candidates are recorded
separately, producing 4,429 inventory rows.

The processed knowledge layer contains 552 normalized records and a closed
candidate graph with 1,987 nodes and 1,985 edges. Ten structured contracts
and CI evidence files were copied exactly after deterministic scanning. Twenty-
one approved source files were read and hash-bound. Front doors, TOCs,
instruction prose, lesson catalogs, and enrollment metadata were not copied
verbatim; their reusable fields were normalized and their current hashes retain
provenance.

Albert remains the source authority. Every DAD record is internal-only,
candidate-only, human-gated, and license-review-required.

## CI lesson dedupe

`ALBERT-LESSON-072` is not a second DAD lesson. It is source provenance for:

- `dad:learning-event:ci-unrelated-module-false-blocker:6631e5cb9401`
- `learning-rule:ci-tests-follow-declared-module-dependency-edges`
- `ci-module-boundary-governance`
- `skill:dad-ci-module-boundary-governance`

Albert's dirty/untracked workflow changes remain adoption evidence only. They
still have source-review gaps, including mixed scheduled/PR scope and provisional
required-check behavior. DAD's provider-neutral rule remains governing.

## Structured copy

The normalized layer contains:

- 72 numbered lessons plus 9 Monte Carlo lesson sections;
- 144 digital assets, 10 high-compounding families, and 12 workflow patterns;
- 5 executor adapters, 3 capability profiles, 3 mesh roles, and 5 task classes;
- 14 agent roles, 9 routing rules, and 4 decision surfaces;
- 9 workflow phases;
- 123 legal edge candidates and 16 research-basis records;
- 106 witness-preparation technique candidates and 8 registry findings.

These records are searchable candidate nodes. None were bulk-added to DAD's
global asset, agent, skill, learning-rule, or edge authorities.

## Privacy exclusions

No content or readable path names were retained for 3,002 excluded items:

| Family | Count |
|---|---:|
| `outputs/cases/**` | 1,282 |
| `source/**` | 125 |
| `reports/**` | 1,407 |
| `simulation/output/**` | 120 |
| `analysis/**` | 6 |
| `case_config/**` | 2 |
| `exports/**` | 2 |
| `training/**` | 19 |
| `reviews/**` | 4 |
| `data/non-asset/**` | 35 |

Each excluded inventory item has an opaque path SHA-256, Git index blob
identifier, size, family, and disposition; its source-path field is empty.
Generic family terms may still appear inside approved normalized governance
descriptions, but no excluded item path is exposed. Albert's ignored private workspace was neither
enumerated nor copied. The enrollment contract failed the exact-copy path scan
because it contains a stale absolute local path; only its hash and normalized
metadata were retained.

## Dedupe and authority findings

Deterministic exact checks found no SHA-256-identical approved source files in
DAD, no exact Albert asset-ID match against DAD's registered assets/offerings,
and no exact Albert workflow-pattern match against DAD's pattern records.
Semantic overlap remains candidate evidence and requires human disposition.

Albert's role mesh overlaps the global hierarchical mesh, its learning records
overlap DAD's priority-content promotion pipeline, and its legal taxonomies
overlap knowledge-engineering graph machinery. Those overlaps were routed as
source-specific candidates instead of competing global authorities.

## Independent red-team gate

Final verdict: `PROCEED` with no remaining blockers. The independent checker
verified 32/32 bounded ingestion and CI tests, all eight executable negative
ingestion fixtures, the removal of source-specific registries from exact-copy
scope, the precise excluded-inventory-path claim, both environment-sensitive
tests from a non-OneDrive temp root, 320/320 repository contracts, graph closure,
bound output hashes, and an unchanged Albert HEAD and dirty-state digest.

At publication review, Albert's HEAD was still the recorded commit but its live
dirty worktree had advanced. The DAD snapshot is therefore an immutable
historical candidate for the recorded capture-state digest, not a claim about
Albert's latest dirty state. No Albert files were restored or refreshed; a newer
snapshot requires a separate privacy-safe ingestion and human review.

## Cross-repository rollout

The existing metadata-only CI adoption audit covers eight enrolled repositories.
No downstream repository was modified. Each recommendation remains a proposed
local patch requiring that repository's authority, dependency declaration,
required-check review, validation, and approval.

See `roadmap/evidence/ci-module-boundary-adoption-audit.json` and
`templates/source-knowledge-ingestion/`.

## Rollback

1. Mark this snapshot `rejected` or `superseded` in
   `registry/source-knowledge-ingestion-registry.json`.
2. Route consumers to the prior reviewed snapshot, if one exists.
3. Rebuild the generated source-knowledge graph surface.
4. Preserve this immutable observation and its hashes for provenance.
5. Do not delete or rewrite Albert files.

## Unknowns and remaining risks

- Semantic duplicate detection remains human-reviewed; exact identifiers are
  insufficient to prove identity.
- Albert's private/internal license does not authorize public distribution.
- Metadata-only inventory cannot prove every candidate is useful or correct.
- Dirty and untracked source evidence can change until Albert commits it.
- A complete candidate graph is not proof of adoption, correctness, competence,
  or execution authority.
