# Repo Rust Adoption Matrix

This matrix includes **27 visible `lowelltwong-alt` entries** from inspection. The user asked for all 26; this pack includes the extra visible entry so an empty/retired/legacy repo is not silently omitted.

| Priority | Repo | Rust status | First Rust slice | Confidence | Risk |
|---:|---|---|---|---|---|
| 1 | `Digital-Assett-Directory` | `immediate` | tools/dad_scan_core: local source scanner emitting raw asset observation JSONL and quarantine report. | high | medium: avoid replacing DAD orchestration before Rust observation contract is stable. |
| 2 | `logos-scripture-graph` | `immediate_already_started` | Split usfm_observation_scanner into modules; add cargo test/fmt/clippy; add manual/nightly full-scan workflow. | high | medium: must preserve no-text/non-authorizing boundaries. |
| 3 | `LawFirm-os-intake` | `immediate_narrow` | tools/intake_ingest_probe: source inventory, byte/line offsets, hashes, duplicate source candidates, JSONL ledger integrity. | high | medium-high: legal workflow logic must not move into Rust evidence scanner. |
| 4 | `Albert-Trial-Simulation-System` | `high_next_case_scaling` | tools/albert_evidence_indexer: raw/processed evidence hash inventory, OCR completeness, path-isolation and chunk-manifest outputs. | medium-high | medium-high: do not encode legal strategy or witness knowledge rules in early Rust. |
| 5 | `LawFirm-os-skills-registry` | `medium_high_after_dad` | tools/skill_static_scanner: path, secret, shell/network/browser/tool declaration, encoded payload, rulepack safety checks. | high | medium: rule severity must remain governed; scanner must not approve skills. |
| 6 | `LawFirm-os-talent-intelligence` | `medium_later_scaling` | tools/talent_ingest_core: CSV normalization, snapshot hashes, identity-fingerprint candidate features, bulk SQLite import. | medium | medium: identity resolution must remain review-gated. |
| 7 | `LawFirm-Talent-Intel-ATS` | `medium_later_shared_utility` | Reuse talent_ingest_core if workspace volume grows; no separate Rust crate first. | medium-low | medium: source truth separation must not collapse LinkedIn and Nevada workspaces. |
| 8 | `LawFirm-os-legal-knowledge-runtime` | `medium_later` | tools/legal_doc_preflight: source inventory, hash manifest, offset map, bounded text profile, chunk-boundary candidates. | medium | medium-high: retrieval/model output must not become legal truth. |
| 9 | `orphan-radar` | `medium_low_optional` | tools/orphan_scan_core: markdown link extraction, note inventory, source hash manifest, edge list. | medium | low-medium. |
| 10 | `LawFirm-os-exceptions-lake-runtime` | `low_medium_later` | tools/exceptions_ledger_verify: JSONL validation, hash-chain verify, idempotency-key scan, no raw-payload enforcement. | medium | medium: runtime evidence must not become canon. |
| 11 | `exceptions-lake-runtime` | `low_medium_later_shared` | Shared exceptions_ledger_verify only if older FMG runtime remains maintained. | medium-low | low-medium. |
| 12 | `LawFirm-os-orchestrator` | `low_optional_verifier` | tools/orchestrator_packet_verify: packet hash verification, contract pin drift check, JSONL evidence packet integrity. | medium | medium: Rust must not create route/event authority. |
| 13 | `LawFirm-os-semantic-substrate` | `low_control_plane_not_now` | Optional lawfirm_contract_lint later: duplicate IDs, changed-path coverage, JSON registry coverage, link checks. | high | medium-high if Rust is allowed to encode policy authority prematurely. |
| 14 | `logos-governance-architecture` | `low_control_plane_not_now` | Optional logos_gov_lint much later for link/frontmatter/dependency-map coverage. | high | medium-high: do not make tool output certify governance truth. |
| 15 | `logos-boundary-literature` | `low_wait_for_corpus` | Future boundary_source_audit after corpus import: source metadata, trust profile, contamination checks. | high | medium: boundary material must not contaminate canonical Scripture. |
| 16 | `kirsten-dissertation-knowledge-graph` | `low_later_if_citation_audit_slow` | tools/citation_ledger_check: source-file hashes, citation registry integrity, PDF/source inventory. | medium | medium: citation correctness cannot be inferred from structural checks alone. |
| 17 | `fmg-fractal-capability-ontology` | `low_control_plane_not_now` | Optional shared contract linter if validation becomes slow. | medium-high | medium. |
| 18 | `All-Law-Firm-Talent-Intel` | `unknown_low` | None until DAD scans it and identifies active data paths. | low | unknown. |
| 19 | `obsidian-foundry-vault` | `low_optional_vault_scan` | Reuse orphan_scan_core or DAD scanner; no custom crate first. | low-medium | low. |
| 20 | `airca-fractal-decision-architecture` | `none_now` | None; maybe future artifact validator if machine-readable artifacts grow. | high | low. |
| 21 | `noesis-atlas` | `none_now` | None now; future route/export validator possible. | medium-high | medium if Rust collapses worldview authority boundaries. |
| 22 | `Bi-Test` | `none_now` | None. | high | low. |
| 23 | `lowell-career-os` | `none_now` | None. | high | low. |
| 24 | `lowelltwong-alt` | `none_now` | None. | high | low. |
| 25 | `Ryans-Project` | `unknown_low` | None until real data/runtime hot path appears. | low | unknown. |
| 26 | `lairca-logos-grounded-theological-model` | `none_now` | None. | medium | low. |
| 27 | `logos-governed-core` | `none_archived` | None. | high | low. |

## Status meanings

| Status | Meaning |
|---|---|
| `immediate` | Start Rust now in a narrow, deterministic leaf tool. |
| `immediate_already_started` | Rust already exists; modularize, test, and govern it. |
| `immediate_narrow` | Start a small Rust preflight/scanner, not a rewrite. |
| `high_next_case_scaling` | Start as soon as the next scaling use case begins. |
| `medium_later_scaling` | Wait for volume or CI/runtime pressure. |
| `low_control_plane_not_now` | Keep Python/docs/JSON; maybe Rust linter much later. |
| `none_now` | No useful Rust pressure visible. |
| `none_archived` | Do not invest. |
| `unknown_low` | Inventory first with DAD; do not guess. |

## Promotion rule

A repo moves from `later` to `immediate` only when at least three of these are true:

```text
1. A stable input/output artifact contract exists.
2. A Python scanner/parser/validator is slow or repeatedly run.
3. CI time is being driven by deterministic data processing.
4. The task can emit JSON/JSONL without domain judgment.
5. The task touches many files or large files.
6. The task needs stronger no-mutation/source-safety guarantees.
7. The tool can be reused across two or more repos.
```
