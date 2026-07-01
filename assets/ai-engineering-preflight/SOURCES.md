# Research Sources

This asset is based on high-signal official sources and stable language documentation.

## AI coding-agent guidance

- OpenAI Codex best practices: prompts should specify goal, context, constraints, and done-when criteria.  
  https://developers.openai.com/codex/learn/best-practices

- OpenAI Codex AGENTS.md guidance: Codex reads `AGENTS.md` before work and layers global plus project-specific guidance.  
  https://developers.openai.com/codex/guides/agents-md

- OpenAI Codex goal guidance: long-running work needs a clear success condition and validation loop.  
  https://developers.openai.com/codex/use-cases/follow-goals

- OpenAI Codex subagents guidance: subagents help parallel exploration and multi-step planning but consume additional tokens.  
  https://developers.openai.com/codex/subagents

- Anthropic Claude Code memory guidance: `CLAUDE.md` stores persistent instructions, but concise, specific, structured instructions work better and long files consume context.  
  https://code.claude.com/docs/en/memory

- Anthropic Claude Code skills guidance: skills are reusable instruction folders that load when relevant, useful when a repeated checklist or procedure outgrows `CLAUDE.md`.  
  https://code.claude.com/docs/en/skills

- Anthropic Claude Code subagents guidance: subagents preserve context by isolating exploration and returning summaries.  
  https://code.claude.com/docs/en/sub-agents

- Anthropic Claude Code hooks guidance: hooks can run actions such as formatting, blocking protected files, or injecting context at lifecycle points.  
  https://code.claude.com/docs/en/hooks-guide

- Cursor agent best practices: agents do better with specific prompts, careful review, verifiable goals, typed languages, linters, and tests.  
  https://cursor.com/blog/agent-best-practices

- GitHub Copilot repository custom instructions: Copilot uses repository instructions to understand how to build, test, and validate changes.  
  https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions

- GitHub changelog: Copilot coding agent supports `AGENTS.md`, nested `AGENTS.md`, `.github/copilot-instructions.md`, `.github/instructions/**.instructions.md`, `CLAUDE.md`, and `GEMINI.md`.  
  https://github.blog/changelog/2025-08-28-copilot-coding-agent-now-supports-agents-md-custom-instructions/

## Python guidance

- PEP 8: single leading underscore marks non-public names; `__all__` declares public API.  
  https://peps.python.org/pep-0008/

- Python `typing` docs: type hints provide vocabulary for annotations and static-analysis tooling.  
  https://docs.python.org/3/library/typing.html

- Python `dataclasses` docs: dataclasses generate common methods from typed fields; frozen dataclasses emulate immutability.  
  https://docs.python.org/3/library/dataclasses.html

## Rust guidance

- Rust Reference, visibility and privacy: items are private by default except associated items in public traits and variants in public enums; private items are accessible to the current module and descendants.  
  https://doc.rust-lang.org/reference/visibility-and-privacy.html

- Rust API Guidelines: newtypes, custom argument types, builders, validation, and `Debug` for public types are recommended API design tactics.  
  https://rust-lang.github.io/api-guidelines/checklist.html

- Rust API Guidelines GitHub repo: recommendations are authored largely by the Rust library team, based on standard library and ecosystem experience.  
  https://github.com/rust-lang/api-guidelines

- Rust Style Guide: defines default Rust style; `rustfmt` uses it as reference.  
  https://doc.rust-lang.org/style-guide/

- Clippy docs: `cargo clippy` is the standard cargo subcommand for Clippy; warnings can be denied in CI.  
  https://doc.rust-lang.org/clippy/usage.html

- Rustdoc book: rustdoc generates documentation and Cargo integrates with it through `cargo doc`.  
  https://doc.rust-lang.org/rustdoc/what-is-rustdoc.html
