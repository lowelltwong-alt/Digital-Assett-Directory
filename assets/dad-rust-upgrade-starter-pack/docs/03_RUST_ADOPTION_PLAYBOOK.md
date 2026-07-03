# Rust Adoption Playbook

## Rust decision rule

Start Rust when the work is:

```text
stable contract + repeated deterministic processing + file/data scale + JSON/JSONL boundary
```

Stay Python when the work is:

```text
changing product logic + human workflow + model/API orchestration + domain judgment
```

## Decision checklist

Use Rust when at least three are true:

- The code scans thousands of files or hundreds of MB.
- The code hashes, parses, validates, indexes, or streams artifacts.
- The input/output shape is stable enough to document.
- CI time comes from deterministic processing rather than model calls or workflow breadth.
- You need a single binary for local/Windows/macOS/Linux use.
- The tool must be no-mutation and fail-closed.
- The same engine can be reused by multiple repos.

Avoid Rust when three are true:

- The rules change every session.
- The output is a human review packet with evolving semantics.
- The code mostly calls APIs, LLMs, dashboards, or Excel formatting.
- The work is governance, legal judgment, theology, or authority mapping.
- The team cannot yet test it with `cargo check` and `cargo test`.

## Common Rust islands for your repo family

| Island | Reusable across repos |
|---|---|
| source scanner | DAD, Albert, Intake, Talent Intel, Legal Knowledge |
| JSONL validator | Logos Scripture, DAD, Intake, Exceptions Lake |
| ledger verifier | Intake, Orchestrator, Exceptions Lake |
| static security scanner | Skills Registry, DAD, all agent-skill repos |
| path-isolation checker | Albert, Intake, DAD, Logos Scripture |
| hash/manifest generator | All data-heavy repos |

## Keep the contract simple

```text
Rust reads local files.
Rust emits JSON/JSONL.
Python validates, interprets, routes, and reviews.
```

## Anti-patterns

- Rewriting the whole repo.
- Moving governance authority into Rust.
- Treating Rust output as canon.
- Adding async/Tokio before file IO and streaming need it.
- Using `unsafe` in first-pass scanner tools.
- Adding PyO3 before a CLI boundary proves stable.
- Running full scans on every PR before a fast smoke suite exists.
