# Harness Discovery Radar

Status: candidate radar for turning repeated coding problems, orphan assets, and
research leads into reusable DAD harnesses.

## Purpose

Coding improvement is a top-priority DAD asset class. A good harness is more
than a note: it has a package shape, prompts, scripts, tests or evals,
examples, research notes, versioning, and clear adoption boundaries.

The harness discovery radar watches for repeated signals that should become
new or upgraded harnesses:

- slow Python test batteries;
- Rust shadow/parity opportunities;
- agent-instruction quality gaps;
- private/public provenance risks;
- enrollment and mail safety risks;
- orphan assets that could become reusable coding improvement systems.

## Source Of Truth

- Methodology: `registry/harness-discovery-methodology.json`
- Schema: `schemas/harness-discovery-methodology.schema.json`
- Existing harnesses: `registry/coding-harness-registry.json`
- CLI: `asset-dir harness discovery-methodology`
- Candidate report: `asset-dir harness discover --repo <repo> --task "<task>"`

## Discovery Loop

1. Check DAD offerings, coding tactics, postflight lessons, usage ledger, and
   orphan/background radar outputs.
2. Score opportunities against controlled harness families.
3. Prefer evaluating an existing harness when a family exists.
4. Create a research candidate only when the family is missing or materially
   underpowered.
5. Promote only when the harness has `harness.json`, README, prompt or script
   entrypoint, tests/evals, source evidence, safety notes, and review approval.

Use `docs/HARNESS_VS_DETERMINISTIC_ENFORCEMENT.md` before proposing a new hard
check. In early or ambiguous cases, create a harness or subharness first. Promote
only the low-noise, stable, objective slice into deterministic enforcement.

When a new case belongs to a larger family, link it upward:

```text
parent harness family -> issue-specific subharness -> examples/evals -> promoted checks
```

This keeps DAD from accumulating one-off validators while still preserving the
learning value of repeated issues.

## External Research

External research can improve DAD, but it stays candidate-only. Research notes
must keep links, provenance, license/security/compatibility questions, and a
public/private release posture. Do not install, copy, or send externally
derived code into downstream repos without review.

When the discovery came from a hard task, the agent should record whether DAD
was searched first. If DAD had no useful answer and external research produced a
fix, the fix belongs in the exception/fix-outcome or research-intake flow so the
next agent can find it without repeating the search. See
`docs/DAD_PROFESSIONAL_RESEARCH_LAYER.md`.

High-signal frontier items are allowed to escalate quickly into harness
discovery, but not into promoted guidance. Examples include official agent
workflow documentation, reputable harness/eval writeups, language/toolchain
changes with proof surfaces, and repeated public codebase patterns. Leak-like or
uncorroborated content must be quarantined or reduced to a public-safe topic
pointer until an official or reputable source exists.

## Fable/Claude/Codex Use

Use this radar when asking a stronger creative/research model to improve DAD.
Ask for:

- unusual harness families DAD is missing;
- ways to teach coding agents to check DAD before coding;
- eval cases for agent obedience and false confidence;
- safe research loops for current coding techniques and leakage reports;
- asset-recognition patterns that find useful repo assets without exposing
  private contents.
