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

## External Research

External research can improve DAD, but it stays candidate-only. Research notes
must keep links, provenance, license/security/compatibility questions, and a
public/private release posture. Do not install, copy, or send externally
derived code into downstream repos without review.

## Fable/Claude/Codex Use

Use this radar when asking a stronger creative/research model to improve DAD.
Ask for:

- unusual harness families DAD is missing;
- ways to teach coding agents to check DAD before coding;
- eval cases for agent obedience and false confidence;
- safe research loops for current coding techniques and leakage reports;
- asset-recognition patterns that find useful repo assets without exposing
  private contents.
