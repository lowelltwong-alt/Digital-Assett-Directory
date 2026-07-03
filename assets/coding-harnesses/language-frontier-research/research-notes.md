# Research Notes

The useful frontier for DAD is not "new language feature exists." The useful
frontier is "this language or tool gives agents a new deterministic way to
inspect, validate, refactor, or run code."

Starting source groups are already governed in
`registry/trusted-source-registry.json`. High-signal Rust refreshes should watch
the official Rust blog, Inside Rust, Rust project goals, RFCs, the Rust
Performance Book, Clippy, RustSec, Rust Fuzz, nextest, docs.rs, lib.rs, PyO3,
and mature scanner/parser CLI codebases. High-signal Python refreshes should
watch Python release notes, PEPs, the developer guide, typing docs, PyPA,
pytest, Hypothesis, Ruff, uv, mypy, and pyright.

Research intake stays candidate-only. DAD should capture source pointers and
validation ideas, then use this harness to decide whether the discovery belongs
in an idiom card, buildout guide, coding tactic, eval case, or future-language
record.

## AI-Overlooked Pattern Families

- Shape boundaries: raw JSON, CLI input, config, and mail packets become named
  records before business logic spreads.
- Proof boundaries: compiler, type checker, schema validator, property test,
  fuzzer, or linter is named before the advice becomes a rule.
- Performance boundaries: same-workload timing and correctness evidence are
  required before speed claims.
- Source boundaries: no copied external docs, private data, long source blobs,
  or generated crash corpora move through DAD mail.
- Legibility boundaries: the tactic should make future-agent edits easier to
  review, not merely look advanced.
