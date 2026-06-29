# Asset Identity And Similarity Ladder

## Purpose

Digital asset discovery needs more than one identity signal. A SHA-256 hash is excellent for exact file identity, but it cannot answer whether two assets play the same role, discuss the same concept, contain mostly the same text, or should be reviewed together.

This ladder defines the standard order for identifying, comparing, and reusing assets in this repository and in downstream repositories that adopt the Digital Asset Directory pattern.

## V1 Ladder

| Layer | Status | Primary question | Authority posture |
| --- | --- | --- | --- |
| Metadata fingerprint | Required | Did this observable file state probably change? | Fast change detection only. It is not proof of content sameness. |
| SHA-256 | Required when bytes can be safely read | Is this exact file content already known? | Exact identity for the byte stream only. It does not choose canonical source or legal authority. |
| Chunk hashes | Required for extracted text or metadata records | Which parts changed or overlap? | Fine-grained comparison evidence. Shared chunks are candidates for review. |
| Extracted text | Required when safe and supported | What text can deterministic tools compare, tag, or index? | Generated evidence surface. Source files remain authoritative. |
| Embeddings | Deferred | What assets are semantically similar? | Only after privacy, license, provider, retention, and eval gates are approved. |
| Knowledge graph | Required | How does this asset relate to systems, workflows, schemas, tests, people, risks, and future uses? | Reviewable relationship evidence. Candidate edges do not prove truth. |
| Audit log | Required | Who/what observed, generated, changed, or approved this asset record? | Append-only provenance and accountability record. |

Fuzzy hashing, MinHash, and SimHash are optional similarity accelerators. They should be added when the directory sees many duplicate PDFs, ZIPs, exports, binaries, copied repository folders, or shifted/reordered text. In v1, deterministic token-shingle MinHash is already used for near-duplicate candidate generation over extracted text.

## Design Rules

- Use the lowest sufficient layer first.
- Never treat a metadata fingerprint as proof that file content is identical.
- Never treat SHA-256 sameness as proof that one asset should replace another.
- Keep chunk hashes tied to a specific asset revision and scan ID.
- Keep extracted text clearly marked as generated output, not source truth.
- Do not enable embeddings until privacy, license, provider, retention, and evaluation gates are documented.
- Preserve graph edges as candidate relationships with method, confidence, evidence, scan ID, and review status.
- Keep audit records append-only.

## What Each Layer Answers

| Layer | Example answer |
| --- | --- |
| SHA-256 | "This is the exact same file content as a prior record." |
| Metadata fingerprint | "The observable file state changed or stayed stable during this scan." |
| Chunk hashes | "These sections overlap, and these sections differ." |
| Extracted text | "This file can be compared, classified, searched, or chunked by deterministic text tools." |
| Embeddings | "These assets appear conceptually similar, subject to privacy and eval controls." |
| Knowledge graph | "This asset implements, tests, documents, governs, activates, or complements another asset." |
| Audit log | "This scan, agent, or human produced this record under these conditions." |

## Fuzzy Hashing Deferral

Do not add fuzzy hashing by default. Add it only after one of these signals appears:

- Many PDFs, ZIP files, exports, binaries, or copied repo snapshots are present.
- Exact SHA-256 misses obvious near-duplicates that humans must repeatedly reconcile.
- Text extraction is unavailable or insufficient for a major asset family.
- A validated evaluation set shows fuzzy hashing improves review quality without unacceptable false positives.

Until then, exact SHA-256, metadata fingerprints, chunk hashes, extracted text, deterministic MinHash candidates, graph relationships, and audit logs are the v1 stack.

## Downstream Use

Downstream repositories should reference this ladder when they create their own asset catalogs. A downstream project may already implement only part of the ladder. That is acceptable if the missing layers are explicitly marked as deferred and the implemented layers remain deterministic and auditable.

For example, a legal mock-trial knowledge-graph repo may already have raw-source SHA hashes, canonical chunk hashes, graph relationships, and packet provenance, while intentionally deferring embeddings and fuzzy hashing. That repo should point back here as the firm-wide direction rather than inventing a separate identity model.

