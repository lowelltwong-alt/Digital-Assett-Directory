# Synthetic Silver Program

Status: **candidate program contract.** This document adapts the external
"Synthetic Silver Research and Implementation Program" packet (2026-07-19,
Downloads copy, referred to below as "the source packet") into a DAD-governed
program. The source packet remains candidate research evidence; this document
and the registered schemas are the operative contract.

Program ID: `synthetic-silver`
Registry: `registry/synthetic-silver-program-registry.json`
Schemas: `schemas/synthetic-silver-program-registry.schema.json`,
`schemas/synthetic-silver-provenance-record.schema.json`,
`schemas/synthetic-silver-release-manifest.schema.json`

## One-sentence definition

> Use synthetic silver to move a corpus; use human gold to measure the silver;
> use immutable primary sources to correct both.

A **versioned synthetic silver corpus** is a large, automatically produced
approximation of a desired corpus state, with explicit provenance, hard
deterministic validation, calibrated model judging, stratified human audit,
and versioned releases measured against an untouched human gold holdout.

## Architectural review verdict on the source packet

Adopted as sound:

- the manufacturing line (source -> contract -> gold anchor -> holdout ->
  multiple producers -> deterministic validators -> independent judges ->
  calibrated decision -> audit -> failure mining -> versioned release ->
  holdout evaluation);
- the three recipes (discrete labels, lossless transformations, open-ended
  outputs) with deterministic checks before any model judging;
- the artifact vocabulary (canonical source, gold anchor, gold holdout,
  silver corpus, challenge set, regression set, acceptance specification,
  grounded retrieval test set, preference corpus);
- source-family independence tracking for producers and judges;
- hard gates as binary, never averaged away by rubric scores;
- no numeric thresholds before corpus inspection and calibration;
- chunking as the first pilot;
- the risk register (recursive degradation, self-certification, correlated
  consensus, tail loss, benchmark leakage, normative drift, high-risk domain
  overreach).

Corrected before adoption (each correction is binding):

1. **Split the contract plane from the factory plane.** The source packet's
   proposed `synthetic_silver/` repo layout put governance, gold data, silver
   releases, generators, and judges in one tree. In the DAD portfolio that
   collapses authority boundaries. DAD owns only the contract plane: this
   document, the program registry, the record and manifest schemas, tier
   policy, and adapters. Factories (generators, validators, judges, corpora,
   gold sets, releases) live in the domain repos, which keep source authority.
   DAD never stores corpus content, gold rows, or generated silver payloads.
2. **Logos is read-only to DAD.** `registry/logos-repo-authority.json` and
   `docs/LOGOS_READ_ONLY_BRIDGE.md` deny all DAD writes into Logos with no
   scheduled bypass. The source packet's "Logos chunking pilot" therefore runs
   Logos-side: Logos pulls this contract and the schemas through its own
   tooling, implements chunkers and validators locally, and may send
   metadata-only results back. DAD reads approved metadata only.
3. **The litigation engine already has a stricter kernel contract.** The
   LawFirm Sim synthetic litigation world (private packet
   `law-firm-digital-twin-fable-architecture-review-v1` and addenda) gives the
   deterministic kernel sole ownership of world truth, and limits generative
   workers to proposal-only jobs. Synthetic silver artifacts entering that
   world are worker proposals at most; nothing in the silver ladder can write
   kernel-canonical state, and the engine's G0-G2 authority gates are not
   superseded by silver tiers. The engine's JobManifest/JobResult pattern is
   the reference implementation of this program's producer contract.
4. **Tier promotion routes through DAD's existing promotion machinery.** The
   packet's S0-S3/G1/G2 ladder is adopted, but G-tier promotion is not a new
   mechanism: it maps onto DAD's candidate -> reviewed -> promoted lifecycle,
   uses existing human gates, and high blast-radius promotions follow
   `docs/PROMOTION_RESEARCH_LANE.md` when that lane is active. A legal or
   theological output never becomes authoritative by accumulating silver
   metrics.
5. **Tool selection routes through the existing synthetic-data registry.**
   The packet's repository audit (Snorkel, Cleanlab, distilabel, NeMo Curator,
   TRDG, SynthTIGER, kraken, ragas, argilla, Meta synthetic-data-kit)
   duplicates `registry/synthetic-data-resource-registry.json`, which already
   carries several of these with license and verification state and a weekly
   scout. Missing tools are recorded in this program's research backlog and
   enter through that registry's normal intake, not through this program.
6. **Judge calibration reuses the subagent evaluation system.** Judge-human
   agreement tables, pair-order controls, and self-preference checks follow
   `docs/SUBAGENT_EVALUATION_AND_CAPABILITY_GRAPH.md` and
   `registry/subagent-evaluation-methodology.json` rather than a parallel
   judge-validation scheme.
7. **All numeric thresholds in the source packet are placeholders.** The
   registry stores gates with `calibration_required: true` and no numbers.
   Thresholds are set per corpus, per stratum, after gold-anchor calibration,
   and recorded in the domain repo's release manifests.

## Authority boundaries

- DAD authority: this contract, schemas, tier definitions, adapter pointers,
  and validation of DAD-held records. Candidate evidence only for everything
  else.
- Domain repo authority: corpus content, gold data, generators, validators,
  judges, releases, thresholds, and every acceptance decision about its own
  corpus.
- Human authority (Lowell): gold-anchor adjudication, tier promotion above
  S3, publication decisions, legal and theological approval, jurisdiction and
  confidentiality decisions.
- Prohibited everywhere: storing secrets or client data in silver records;
  treating model agreement as independent validation; silver artifacts
  overwriting canonical sources; automatic promotion to G tiers; DAD writes
  into Logos; copying private LawFirm rows into DAD.

## Tier ladder

| Tier | Name | DAD lifecycle | Permitted use | Required controls |
|---|---|---|---|---|
| S0 | raw_synthetic | candidate | exploration only | provenance record |
| S1 | machine_filtered | candidate | internal candidate pool | hard validators passed |
| S2 | calibrated_silver | candidate | bulk processing, training | gold-anchor calibration, active audit |
| S3 | human_sampled_silver | reviewed | retrieval, internal analysis | stratified human audit passed |
| G1 | human_adjudicated | reviewed | reference, publication prep | qualified human review |
| G2 | authoritative | promoted | source-of-truth layer | explicit human promotion via DAD gates |

Movement above S3 always requires a human decision. No metric, judge score,
or agreement rate promotes an artifact on its own.

## Non-negotiable controls

1. The canonical source is never overwritten.
2. Every derived item is traceable to an exact source span.
3. The gold holdout is excluded from prompts, examples, tuning, threshold
   selection, and training.
4. No model both generates and solely certifies the same output.
5. Prompt variants of one model family are correlated sources, not
   independent votes; independence is tracked at the source-family level.
6. Deterministic validators run before any model judging.
7. Accepted items remain auditable; rejected items are retained with reasons.
8. Rare and difficult strata are intentionally sampled and never silently
   filtered away.
9. Human corrections are a separate authoritative layer.
10. Every release has a version, manifest, and reproducible configuration.
11. A new model never silently regenerates an old benchmark.
12. Task specifications are semantically versioned; no silent re-labeling.
13. Critical errors are binary gates; rubric scores cannot compensate.
14. Synthetic-only evidence never establishes real-world readiness; real,
    source-separated holdouts remain the measure (consistent with
    `registry/synthetic-data-resource-registry.json`).

## Adapters

Adapters are pointers and mail routes, never code or content pushed by DAD.
Downstream adoption is by local approval in each repo.

| Adapter | Target | Mode | Notes |
|---|---|---|---|
| `logos` | Logos corpus family | read_only_pointer | Logos pulls contract/schemas; DAD reads approved metadata only; chunking pilot is Logos-side. |
| `law-firm-sim` | LawFirm Sim / synthetic litigation engine | sovereignty_child_pointer | Silver producers map to proposal-only JobManifest workers; kernel authority and G0-G2 gates unchanged. |
| `world-builder` | Synthetic world/corpus factory builds | target_unresolved | Repo identity unconfirmed; likely the litigation world kernel generalized. Human confirmation required before the pointer is bound. |
| `litigation-corpus-factory` | Case/artifact corpus generation lane inside the litigation world | sovereignty_child_pointer | Release manifests and provenance records apply to generated case corpora; treatment-blind evaluation remains engine-owned. |

## First pilot: Logos chunking (Logos-side)

Chunking is confirmed as the first pilot: largely deterministic correctness,
reversible failures, and it builds the provenance infrastructure every later
task needs. The pilot sequence (P0-P12), acceptance specification, candidate
chunker set, and retrieval test classes from the source packet are adopted as
the pilot brief. DAD holds the brief; Logos implements and owns results.

Hard requirements for chunk acceptance (deterministic, code-tested):
exact normalized-source reconstruction; zero omission; zero invention; exact
character offsets; stable source identity; explicit Unicode policy; intact
combining sequences; recoverable page/section/verse/line identity, heading
hierarchy, footnote anchors, and language/script spans; deterministic
serialization; no silent editorial rewriting.

Second lane (independent, LawFirm-side): the litigation corpus factory can
adopt the provenance record and release manifest for generated artifacts
without waiting on the Logos pilot; the two lanes share the contract, not a
schedule.

## Record contracts

- `schemas/synthetic-silver-provenance-record.schema.json` — one record per
  candidate item: source span, task and spec versions, producer identity with
  source family, hard-check results, judge results with pair order and rubric
  version, aggregate decision, tier status, and human adjudication.
- `schemas/synthetic-silver-release-manifest.schema.json` — one manifest per
  silver release: task/spec versions, source snapshot hashes, code commit,
  prompt hashes, producers, sampling strategy, per-stratum counts,
  accept/review/reject counts, validator failure counts, audit findings,
  gold-anchor and holdout performance, limitations, confidentiality tier,
  and supersession.

Golden examples live in `examples/synthetic-silver/` and are validated by
`asset-dir validate` and `tests/test_synthetic_silver_program.py`.

## Research backlog

Recorded in the registry: candidate intake of Snorkel, Cleanlab, ragas,
Argilla, Meta synthetic-data-kit, and kraken into
`registry/synthetic-data-resource-registry.json`; blind independent audit of
the source packet's claims (the packet's own W-wave prompts); corpus
inspection unknowns (volume, formats, OCR quality, licenses, reviewer
availability) that must be measured before any threshold is set.

## Validation

```text
python -m pytest tests/test_synthetic_silver_program.py
python -m digital_asset_directory.cli validate
```
