# Language Frontier Research Runbook

1. Identify the source ID or URL in `registry/trusted-source-registry.json`.
2. Record a safe summary, language, tool or feature, and applicability limits.
3. Reject copied docs, copied code, private rows, credentials, long logs, and
   benchmark-only claims.
4. Name the proof surface: compiler, type checker, linter, test runner, fuzzer,
   profiler, package auditor, runtime tracer, or schema validator.
5. Route the candidate to a DAD asset:
   - Python: `assets/python-ai-advantage-preflight/`,
     `assets/python-underused-idioms/`, or Python test performance harness.
   - Rust: `assets/rust-buildout-guide/` or Rust shadow parity harness.
   - Future language: candidate language row plus a proof-tool note.
6. For scheduled refreshes, run the review through
   `prompts/language-frontier-refresh.prompt.md` so the output includes a
   trusted-source match, proof surface, AI-overlooked pattern, falsification
   idea, and target DAD surface.
7. Add or update a harness eval case before broad downstream guidance.
