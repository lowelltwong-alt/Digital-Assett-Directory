# Future Language Playbook Template

Status: template; not directly recommendable.

Use this when DAD considers a new language such as Go, TypeScript, Zig, or
another toolchain as a recurring coding advantage.

## Minimum Gates

- Name official or reviewed source IDs in `registry/trusted-source-registry.json`.
- Add a language row to `registry/language-coding-advantage-registry.json` with
  `recommendable=false` until reviewed.
- Identify what deterministic proof surface the language adds: compiler,
  type-checker, linter, formatter, test runner, fuzzer, profiler, package
  auditor, API checker, or agent-readable output.
- Add at least one codebase watch target and one avoid-when limit.
- Add a harness route or small eval case before downstream recommendations.

## Promotion Questions

- What can this language prove that Python, Rust, or existing DAD harnesses do
  not already prove well enough?
- Which repo contexts should avoid it?
- What command falsifies the benefit?
- What private/public, dependency, license, packaging, or source-authority risk
  does it introduce?
- How will postflight tell DAD whether the guidance helped, failed, was ignored,
  or was harmful?

## Rejection Signals

- The reason is popularity, novelty, or agent preference.
- The source is a draft or benchmark-only claim with no local validation path.
- The proposed use would copy third-party code or private repo content into
  DAD.
- The language would replace local authority instead of adding a small proof
  surface.

