# Research Intake Pipeline

How external research becomes actual library entries. External content never skips
quarantine, screening, or a named human approval -- trust tiers only lower intake
friction.

## Flow

```text
research report entry (processed/research/*.json)
  -> asset-dir research intake        # quarantine record in processed/research/intake/
  -> asset-dir research screen  x4    # prompt_injection, license, provenance, compatibility
  -> asset-dir research promote       # named human + approval ID required
       -> assets/external/<slug>/POINTER.md            (pointer artifact, never a copy)
       -> registry/dad-offerings-registry.json row     (--target offering)
          or registry/agent-skill-library.json row     (--target skill_pointer, format pointer_only)
```

## Rules

- **Trusted sources** (`registry/trusted-source-registry.json`): `high_signal` (frontier
  labs, Trail of Bits, rust-lang, Google, PyO3, Astral, martinfowler.com) and `known`
  (arXiv, curated indexes) sources can be quarantined directly. Unknown sources require
  `--justification`. Adding a source to the registry is itself a human review act.
- **Language frontier radar**: trusted sources may include `language_focus`,
  `check_cadence`, `frontier_watch`, and `intake_actions`. These fields tell DAD
  where to look for Rust, Python, mixed-language, and future-language coding
  improvements. They are watch instructions only; they do not promote content.
- **Screening**: all four checks must be `pass`/`not_applicable` before promotion. A
  `fail` returns the record to quarantine. Skills are third-party instructions -- the
  prompt-injection check is not optional for them.
- **Promotion**: requires `--approved-by <named human>` (agent/unknown rejected) and
  `--approval-id`. Runs `check_offering_novelty` first and blocks `duplicate` /
  `possible_duplicate` verdicts (route those as `known_upgrades` or rename).
- **Pointer-only**: promotion writes a `POINTER.md` with provenance, license, trust tier,
  intake and approval IDs. DAD stores no external content. External skills enter the
  skill library as `pointer_only` format with checkout mode `pointer`, update policy
  `manual_review`, and a 90-day review due date.
- **Re-screening**: if the upstream changes, the promoted row's `does_not_apply_when`
  says so -- re-run screening before continued reuse.

## Commands

```text
asset-dir research intake --name "<name>" --kind skill --source-url <url> [--justification "..."]
asset-dir research screen --intake-id <id> --check prompt_injection --result pass
asset-dir research promote --intake-id <id> --approved-by <human> --approval-id <id> --target skill_pointer
asset-dir research intake-list [--status screened]
```

## Language Frontier Radar

DAD currently watches Rust and Python frontier sources as candidate input for:

- `assets/rust-buildout-guide/`
- `assets/python-underused-idioms/`
- `assets/coding-harnesses/rust-shadow-parity-harness/`
- `assets/coding-harnesses/python-test-performance-orchestration/`
- `assets/coding-harnesses/language-frontier-research/`
- future coding harnesses and skill pointers

Rust checks should prioritize official project updates, RFCs, compiler/cargo
roadmap changes, RustSec advisories, PyO3/maturin changes, and practical
performance techniques. A Rust recommendation is not actionable until a repo has
profile evidence and, for replacement work, verified shadow parity.

Python checks should prioritize accepted or near-accepted PEPs, CPython and
stdlib changes, packaging/tooling shifts, diagnostics, concurrency, typing, and
underused stdlib constructs that make generated code safer or easier for agents
to inspect. PEP drafts and benchmark claims stay candidate-only until reviewed.

When a repo finds a language idea worth teaching DAD, it should send
`dad:need:language-frontier-signals` mail with a source pointer, short safe
summary, applicability limits, proof surface, validation idea, and suggested
destination (idiom card, buildout guide, harness, tactic radar, template, or
skill pointer). Repos must not copy third-party content, private rows, raw logs,
or source blobs into that mail.
