# Coding Tactics Research Radar

Status: candidate research workflow for discovering, reviewing, and promoting
AI coding tactics.

## Principle

The goal is not to make agents use exotic language features everywhere. The
goal is to give agents better-than-average defaults when the build context
justifies them.

Every tactic must answer:

- what problem it prevents;
- when to use it;
- when not to use it;
- what goes wrong if misapplied;
- what small example shows correct use;
- what verification proves it helped;
- how usefulness should be reported back to DAD.

## Evidence Order

Use this order when researching or adding tactics:

1. Official language docs.
2. Official tool guidance.
3. Empirical research.
4. High-signal repos or ecosystem examples.
5. Local DAD observations.
6. Agent postflight observations.

Separate confirmed facts from inferred usefulness. Do not claim GitHub-wide
underuse without measurement evidence.

## Adoption Labels

Use calibrated labels:

- `confirmed_underused`
- `likely_underused`
- `specialized_not_common`
- `underused_by_local_agents`
- `unknown_frequency_high_value`
- `not_underused_but_high_value`

Most seed tactics are `candidate` with `unknown_frequency_high_value` or
`not_underused_but_high_value` because DAD has not measured broad adoption.

## Research Sources To Track

AI-agent configuration:

- OpenAI Codex AGENTS: https://developers.openai.com/codex/guides/agents-md
- OpenAI Codex customization: https://developers.openai.com/codex/concepts/customization
- OpenAI Codex skills: https://developers.openai.com/codex/skills
- OpenAI Codex subagents: https://developers.openai.com/codex/subagents
- Anthropic Claude Code overview: https://docs.anthropic.com/en/docs/claude-code/overview
- Anthropic Claude Code skills: https://docs.anthropic.com/en/docs/claude-code/skills
- Anthropic Claude Code hooks: https://docs.anthropic.com/en/docs/claude-code/hooks-guide
- Cursor rules: https://cursor.com/docs/rules
- GitHub Copilot custom instructions: https://docs.github.com/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot

Python:

- Python What's New: https://docs.python.org/3/whatsnew/
- PEP index: https://peps.python.org/
- Python Insider: https://blog.python.org/
- Python developer guide: https://devguide.python.org/
- Dataclasses: https://docs.python.org/3/library/dataclasses.html
- Typing: https://docs.python.org/3/library/typing.html
- Python typing site: https://typing.python.org/
- Enum: https://docs.python.org/3/library/enum.html
- Contextlib: https://docs.python.org/3/library/contextlib.html
- Importlib resources: https://docs.python.org/3/library/importlib.resources.html
- Secrets: https://docs.python.org/3/library/secrets.html
- Context variables: https://docs.python.org/3/library/contextvars.html
- Functools: https://docs.python.org/3/library/functools.html
- Exceptions: https://docs.python.org/3/tutorial/errors.html
- Python packaging guide: https://packaging.python.org/
- pytest docs: https://docs.pytest.org/
- Hypothesis docs: https://hypothesis.readthedocs.io/
- Ruff docs: https://docs.astral.sh/ruff/
- uv docs: https://docs.astral.sh/uv/

Rust:

- Rust blog: https://blog.rust-lang.org/
- Inside Rust blog: https://blog.rust-lang.org/inside-rust/
- Rust project goals: https://rust-lang.github.io/rust-project-goals/
- Rust RFCs: https://github.com/rust-lang/rfcs
- Rust Book modules: https://doc.rust-lang.org/book/ch07-00-managing-growing-projects-with-packages-crates-and-modules.html
- Rust Reference visibility: https://doc.rust-lang.org/reference/visibility-and-privacy.html
- Rust API Guidelines: https://rust-lang.github.io/api-guidelines/about.html
- Sealed traits: https://rust-lang.github.io/api-guidelines/future-proofing.html
- Clippy: https://doc.rust-lang.org/clippy/
- Cargo test: https://doc.rust-lang.org/cargo/commands/cargo-test.html
- Rustdoc tests: https://doc.rust-lang.org/rustdoc/documentation-tests.html
- Rust Performance Book: https://nnethercote.github.io/perf-book/
- This Week in Rust: https://this-week-in-rust.org/
- RustSec: https://rustsec.org/
- Rust Fuzz Book: https://rust-fuzz.github.io/book/
- cargo-nextest: https://nexte.st/
- crates/docs discovery: https://crates.io/, https://docs.rs/, https://lib.rs/

AI-code security:

- Do Users Write More Insecure Code with AI Assistants?: https://arxiv.org/abs/2211.03622
- Security Weaknesses of Copilot Generated Code in GitHub: https://arxiv.org/html/2310.02059v2

## Adding A Tactic

Add a record to `registry/coding-tactics-radar.json` that conforms to
`schemas/coding-tactic.schema.json`.

Minimum review posture:

```text
status = candidate
review_status = candidate
promotion_status = not_promoted
confidence = low|medium|high|unknown
```

Confidence is categorical and evidence-backed. It is not a numeric score.

Run:

```text
python scripts/validate_coding_asset_control_plane.py
```

## Promotion

Promotion is handled by `docs/CODING_TACTIC_PROMOTION_POLICY.md`. Candidate use
reports should use `templates/tactic-use-feedback.template.json` and must not
include secrets, private rows, or large copied source content.
