# Knowledge Engineering Workflow Contract

## 1. Diagnose before architecture

Record the user and decision, questions, end state, corpus, change rate,
authority, sensitivity, latency/cost envelope, consequence, acceptable
abstention, and owner. Identify exact, semantic, synthesis, multi-hop, temporal,
structured, multimodal, and adaptive query shapes. If deterministic navigation,
search, or direct context meets the goal, stop without RAG.

## 2. Establish source and ingestion authority

Name canonical sources, stable source/document/revision IDs, checksums, licenses,
classification, retention, ACL/tenant boundaries, event and observation time,
parser/normalizer versions, quarantine, update/delete/tombstone behavior,
reconciliation, and rebuild checkpoints. A vector or graph index is a derived
projection, never the only source or source authority.

## 3. Lock baselines and evaluation

Before optimization, lock representative and adversarial queries plus protected
gold evidence. Baseline deterministic lookup/direct context, lexical search, and
fixed or structural chunks. Define retrieval recall/rank, answer correctness,
grounding, citation entailment/completeness, contradiction/abstention, graph
precision/path correctness, ACL/privacy, latency/cost, freshness/deletion,
outage, migration, and recovery gates. Automated judges require human
calibration and cannot approve their own replacement.

## 4. Select lanes from evidence

- Direct long context: bounded corpus and whole-document synthesis; test
  position, distraction, contradiction, latency, and cost.
- Lexical: names, IDs, citations, jargon, code symbols, and exact phrases.
- Dense vector: semantic similarity and paraphrase, subject to privacy/provider
  and embedding lifecycle gates.
- Hybrid and reranking: use rank fusion and bounded second-stage reranking when
  local recall/quality lift justifies latency and cost.
- Graph-lite: prefer authoritative source links, dependencies, provenance,
  supersession, and typed relationships already present.
- Extracted/GraphRAG/LightRAG: require measurable multi-hop, global-theme,
  relationship, or contradiction lift and entity/link evaluation.
- RDF/property/event/temporal: choose by interoperability, traversal,
  provenance, and valid/as-of-time requirements; do not infer time from an
  atemporal graph.
- Agentic/corrective retrieval: escalation only after bounded static routes and
  recovery criteria exist.

No lane is a universal winner. Missing evidence means investigate or block.

## 5. Engineer chunks and context

Preserve source spans, headings, tables, code/legal/form boundaries, parent-child
relations, overlap semantics, parser and policy revisions, hashes, and privacy
classification. Compare fixed, structural, and parent-child first. Add
contextual, late, semantic, or hierarchical strategies only when failure
analysis shows lost context or abstraction problems. Separate retrieved
evidence from instructions and preserve citations to canonical source spans.

## 6. Engineer replaceable indexes

Pin embedding identity/dimension/distance, sparse/dense representations,
metadata schema, index algorithm/parameters, filter behavior, tenant isolation,
freshness/consistency, backup/restore, export, and observability. Benchmark the
actual filtered workload and concurrency. Never make an integrated hosted
embedding or provider schema mandatory to the portable source contract.

## 7. Recheck at midflight

Stop and re-lock when source authority, corpus, parser, chunk policy, embedding,
index, retrieval, graph schema/extraction, context assembly, evaluation set,
privacy/provider, runtime, dependency, cost, latency, scope, or proof obligation
changes. Build a new revision beside the current one; shadow before cutover.

## 8. Validate independently

The checker re-derives the route and replays ingestion parity, retrieval,
answers/citations, graph/entity resolution, ACL/tenant isolation, poisoning and
prompt-injection handling, latency/cost, freshness/deletion, outage, backup,
migration, rollback, and unknown-state tests. High-consequence domain gold sets
require qualified human review.

## 9. Migrate and retire safely

Freeze the old and new manifests. Backfill from canonical sources, replay CDC
from a checkpoint, dual-write only when authorized, shadow queries, compare all
quality and operational gates, cut over through a logical alias/router, retain
bounded rollback, verify deletion parity, then retire with lineage. Never
silently change embeddings, chunking, indexes, graphs, or rerankers in place.

## 10. Research and postflight

Weekly research is deterministic-delta first, pointer-only, deduplicated, and
inactive until exact human activation. Primary sources, official standards,
official release notes, original papers, counterevidence, security disclosures,
and local reproducibility plans are required. Postflight reports all component
revisions, dependencies, routes considered, baselines, tests, failures,
unknowns, human gates, lessons, and next review triggers.
