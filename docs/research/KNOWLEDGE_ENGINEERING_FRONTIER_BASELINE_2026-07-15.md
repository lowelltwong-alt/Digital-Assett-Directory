# Knowledge Engineering Frontier Baseline — 2026-07-15

Status: candidate research synthesis. Primary-source pointers and bounded
claims only; no source content, dependency, instruction, or schedule is
automatically adopted.

## Architectural conclusion

Portable knowledge systems should separate canonical sources, governed
ingestion/change handling, versioned transforms, interchangeable retrieval
lanes, optional graphs, reranking, evidence assembly, generation, and
independent evaluation. Direct long context, lexical search, vectors, graphs,
and agentic retrieval are complementary. A cheap deterministic route should
choose the smallest lane for the query and consequence.

## Current findings

- Long context does not eliminate retrieval. Effective use can vary by evidence
  position and distraction, so direct-context and RAG routes require workload
  evaluation. See [Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/)
  and [RAG or Long Context](https://aclanthology.org/2024.emnlp-industry.66/).
- Structural chunks are the explainable baseline. Parent-child, contextual,
  late, semantic, and hierarchical chunking are candidate improvements for
  specific failure modes. See [Anthropic Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval),
  [Late Chunking](https://arxiv.org/abs/2409.04701), and
  [RAPTOR](https://arxiv.org/abs/2401.18059).
- Hybrid lexical+dense retrieval with bounded reranking is a candidate baseline
  for mixed workloads, but must beat cheaper local baselines. Exact terms, identifiers, citations,
  and symbols remain lexical strengths. See [Pinecone relevance guidance](https://docs.pinecone.io/guides/optimize/increase-relevance)
  and [Qdrant hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/).
- Graph-lite authoritative links should precede extracted graphs. Microsoft
  GraphRAG targets entity/relationship/community and global/local reasoning;
  LightRAG uses graph+vector low/high-level retrieval. Both have extraction,
  cost, migration, and evaluation obligations. See [Microsoft GraphRAG](https://github.com/microsoft/graphrag)
  and [LightRAG](https://arxiv.org/abs/2410.05779).
- Property, RDF, provenance, event, and temporal graphs solve different needs.
  RDF/SPARQL 1.2 remained in the standards process on the baseline date, so
  compatibility must be pinned. See [RDF 1.2 Concepts](https://www.w3.org/TR/rdf12-concepts/),
  [SPARQL 1.2 Query](https://www.w3.org/TR/sparql12-query/), and
  [PROV-O](https://www.w3.org/TR/prov-o/).
- Temporal context graphs and HippoRAG are promising for changing facts and
  multi-hop memory, but their reported gains are not universal. See
  [Graphiti](https://github.com/getzep/graphiti) and
  [HippoRAG](https://arxiv.org/abs/2405.14831).
- Vector-database selection is operational. pgvector, Qdrant, Pinecone, and
  other engines expose different filtering, isolation, update, backup, export,
  and operations tradeoffs. No primary source establishes a universal winner.
  See [pgvector](https://github.com/pgvector/pgvector),
  [Qdrant data model](https://qdrant.tech/documentation/concepts/), and
  [Pinecone data modeling](https://docs.pinecone.io/guides/index-data/data-modeling).
- Evaluation must separate ingestion, retrieval, answer/citation, graph,
  security/privacy, operations, and recovery. Model-judge metrics require
  calibration and independent human slices. See [RAGAS](https://aclanthology.org/2024.eacl-demo.16/),
  [ARES](https://aclanthology.org/2024.naacl-long.20/), and
  [RAGTruth](https://aclanthology.org/2024.acl-long.585/).
- Agentic retrieval adds decisions and failure surfaces. Self-RAG supports
  conditional retrieval/reflection, but static routes and recovery gates should
  come first. See [Self-RAG](https://openreview.net/forum?id=hSyW5go0v8).
- The knowledge base is an attack surface. Source allowlists, provenance,
  untrusted-context separation, tenant isolation, poisoning tests, secret/PII
  controls, deletion, and human corpus/ontology/ACL gates are mandatory. See
  [PoisonedRAG](https://www.usenix.org/conference/usenixsecurity25/presentation/zou-poisonedrag),
  [OWASP vector and embedding weaknesses](https://genai.owasp.org/llmrisk/llm082025-vector-and-embedding-weaknesses/),
  and the [NIST GenAI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence).

## Local reuse evidence

- DAD already supplies the parent Data/Schema/Knowledge-Graph family, Research
  and Provenance peer family, manifest/graph engineering, research intake,
  graph surfaces, context packs, and asset identity controls.
- Logos owns mature domain chunking, chunk-map, retrieval-neighborhood, graph,
  and evaluation contracts. DAD stores only pointers and reusable patterns.
- Mock Trial owns deterministic legal chunking, BM25 A/B retrieval, vector-index
  manifest, graph retrieval pack, exact-span, provenance, and synthetic fixture
  assets. DAD stores no case/client rows.

## Principal uncertainties

- Reported chunking, retrieval, and graph gains often fail to transfer domains.
- LLM-extracted graphs can fabricate, merge, or omit entities and relations.
- Automated judges share model biases and can reward unsupported answers.
- Vector-store filtering, consistency, backup, and deletion semantics vary.
- Semantic chunking and agentic retrieval lack one stable universal standard.
- No universal vector database, chunker, embedding, reranker, graph method, or
  long-context route is supported by the reviewed evidence.
