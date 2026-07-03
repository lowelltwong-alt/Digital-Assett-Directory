# Language Coding Playbooks

Status: candidate DAD playbooks for AI coding agents.

These playbooks are the quick operational layer above
`registry/language-coding-advantage-registry.json`. The registry is the
machine-readable source of truth; the playbooks tell an agent what to check
before it writes Python, Rust, mixed-language, or future-language code.

## Use

1. Run DAD preflight and read the returned context pack.
2. Run `asset-dir research language-playbook --language <python|rust|future-language-template>`
   to load the DAD playbook, proof surfaces, watch targets, harness routes, and
   safe mail contract for the language.
3. Pick the playbook for the language or boundary being changed.
4. Use the proof operations before making claims about speed, safety, test
   coverage, or frontier techniques.
5. Route new discoveries through `dad:need:language-frontier-signals` or
   `dad:need:coding-harness-feedback`.
6. Keep third-party content, private rows, raw logs, secrets, and long source
   blobs out of DAD mail.

## Playbooks

- `python/PLAYBOOK.md`: Python orchestration, boundaries, test strength,
  profiling, and stdlib introspection.
- `rust/PLAYBOOK.md`: Rust as deterministic leaf tooling, compiler proof,
  parity, fuzz/property checks, and Python/Rust boundaries.
- `future-language-template/PLAYBOOK.md`: minimum gates before DAD adds a new
  language row or sends recommendations to repos.

## Frontier Rule

Frontier research is not adoption. A new language feature, crate, package, or
paper becomes DAD guidance only after pointer-only intake, applicability limits,
local validation, negative/failure evidence, and postflight or harness outcomes.
