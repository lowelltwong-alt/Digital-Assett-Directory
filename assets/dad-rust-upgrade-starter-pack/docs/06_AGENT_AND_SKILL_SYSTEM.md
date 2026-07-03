# Agent, Skill, Plugin, and Multi-Agent System

## Recommended agent roles

| Agent | Responsibility | Should edit code? |
|---|---|---:|
| Rust Architect | crate boundaries, input/output contract, no-authority boundary | No or minimal |
| Rust Implementer | implements scanner/verifier, fixes compile errors | Yes |
| Python Bridge Agent | writes Python wrapper/adapters and JSONL validators | Yes |
| CI/QA Agent | workflows, nextest, deny/audit/coverage/mutation test setup | Yes |
| Security/Unsafe Reviewer | reviews unsafe, path traversal, symlink, secret/output risks | No final merge alone |
| Performance Agent | benchmark design, profiles, memory/throughput measurements | Yes, after correctness |
| Documentation Agent | runbooks, examples, migration notes | Yes |

## Agent task sequence

```text
1. Rust Architect defines contract.
2. Human or owner approves contract boundary.
3. Rust Implementer builds smallest compiling CLI.
4. Python Bridge Agent writes wrapper and schema validator.
5. CI/QA Agent adds PR CI.
6. Security/Unsafe Reviewer audits path/output/dependency risk.
7. Performance Agent adds long CI benchmark only after correctness.
8. Documentation Agent updates DAD docs and adoption matrix.
```

## Cursor / cheap model use

Cheap coding models are appropriate for:

- scaffolding modules;
- writing obvious serde structs;
- translating simple Python file-walk logic;
- adding straightforward tests;
- fixing common compiler errors.

Use a stronger implementation/review model for:

- crate architecture;
- unsafe review;
- security scanner rules;
- Rust/Python boundary design;
- long CI failure triage;
- changes that become cross-repo templates.

## Cursor plugins/extensions

For Cursor or VS Code-compatible Rust work, install:

- `rust-analyzer`;
- CodeLLDB or equivalent debugger;
- TOML support;
- crates/dependency helper extension if desired;
- GitHub Actions workflow validation helper if desired.

## Cargo plugins

Install as needed, not all at once:

```bash
cargo install cargo-nextest --locked
cargo install cargo-deny --locked
cargo install cargo-audit --locked
cargo install cargo-llvm-cov --locked
cargo install cargo-mutants --locked
cargo install cargo-watch --locked
cargo install cargo-machete --locked
```

## Skills included in this pack

```text
skills/rust-scan-core/SKILL.md
skills/rust-ci-qa/SKILL.md
skills/rust-python-bridge/SKILL.md
```

These are candidate skill descriptions for DAD/agent systems. They are not installed skills until reviewed.
