# DAD Language Frontier Refresh Prompt

Use this when a coding agent, research pass, or scheduled refresh finds a
Python, Rust, mixed-language, or future-language idea that may improve how DAD
agents read, write, test, optimize, or repair code.

You are not promoting the idea. You are screening it into pointer-only DAD
candidate evidence.

## Inputs

- Language or toolchain: `<python|rust|mixed|future-language>`
- Source ID or HTTPS URL: `<source-id-or-url>`
- Source type: `<official-doc|official-blog|tool-doc|reference-codebase|research|community-curated|unknown>`
- Candidate idea: `<short-safe-summary>`
- Repo or task context where it may help: `<context>`

## Review Steps

1. Check whether the source matches `registry/trusted-source-registry.json`.
2. Reject copied documentation, copied code, private rows, credentials, raw logs,
   long source blobs, and benchmark-only claims.
3. Name the proof surface: compiler, formatter, linter, type checker, test
   runner, property/fuzz tool, profiler, package auditor, runtime tracer, schema
   validator, or structured report.
4. Decide whether the idea is:
   - `python_candidate`
   - `rust_candidate`
   - `mixed_python_rust_candidate`
   - `future_language_candidate`
   - `source_review_required`
   - `reject`
5. State why an average AI coding workflow may miss the pattern.
6. State what local command, harness case, or negative example would falsify the
   idea.
7. Route the candidate to the smallest DAD surface that can test it:
   - Python: `assets/python-ai-advantage-preflight/`,
     `assets/python-underused-idioms/`,
     `assets/coding-harnesses/python-test-performance-orchestration/`, or
     `registry/coding-tactics-radar.json`.
   - Rust: `assets/rust-buildout-guide/`,
     `assets/coding-harnesses/rust-shadow-parity-harness/`, or
     `registry/coding-tactics-radar.json`.
   - Mixed Python/Rust: Rust shadow parity plus native Python validation.
   - Future language: `future-language-template` in
     `registry/language-coding-advantage-registry.json` until a reviewed source
     and proof tool exist.

## Output Shape

Return concise JSON-compatible fields:

```json
{
  "language": "<python|rust|mixed|future-language>",
  "source_id_or_url": "<source-id-or-url>",
  "trusted_source_match": "<yes|no|needs_review>",
  "safe_summary": "<no copied docs or code>",
  "why_ai_coding_may_improve": "<one or two sentences>",
  "why_ai_may_miss_it": "<one sentence>",
  "applicability_limits": "<where not to use it>",
  "proof_surface": "<named executable check or inspection>",
  "validation_or_eval_idea": "<local command or harness case>",
  "target_dad_surface": ["<asset-or-registry-path>"],
  "decision": "<candidate|source_review_required|reject>",
  "rejection_reason": "<required when decision is reject>"
}
```

## Hard Boundaries

- Do not claim state of the art.
- Do not copy third-party docs, source, benchmark tables, or examples.
- Do not include private repo data, credentials, raw logs, or long source blobs.
- Do not recommend downstream adoption without local validation evidence.
- Do not use popularity, stars, ecosystem buzz, or model confidence as proof.
