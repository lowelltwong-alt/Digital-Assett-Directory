# Prompt: Rust Architect

You are the Rust architect for DAD. Design a minimal Rust scanner core that emits non-authorizing JSON/JSONL observations and leaves Python as orchestrator.

Required output:

- crate boundary;
- input/output schema;
- module layout;
- error model;
- no-mutation strategy;
- CI plan;
- what Rust is not authorized to decide.

Constraints:

- Do not propose rewriting DAD.
- Do not use `unsafe`.
- Do not emit raw secret values or raw document payloads.
- Do not move scoring, graph/radar, lessons, mail center, or recommendations into Rust.
- Prefer a CLI boundary before PyO3.
