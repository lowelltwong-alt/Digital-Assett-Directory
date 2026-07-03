# Coding Harness Library

Status: candidate DAD library for reusable coding-improvement harnesses.

## Purpose

DAD keeps harnesses for improving AI coding, test speed, review quality, and
governance safety. Harnesses are higher-order assets: they package prompts,
scripts, tests/evals, examples, research notes, and version metadata so Codex,
Claude, Cursor, and future agents can reuse the same improvement workflow.

Harnesses are candidate guidance until reviewed locally. They do not authorize
DAD to mutate another repo, skip tests, copy private data, or treat a score as
proof.

## Surfaces

| Surface | Role |
| --- | --- |
| `assets/coding-harnesses/<harness-id>/` | Harness package directories. |
| `registry/coding-harness-registry.json` | Index of harnesses, capabilities, context, and evidence. |
| `schemas/coding-harness.schema.json` | Contract for each harness record and `harness.json`. |
| `schemas/coding-harness-eval.schema.json` | Contract for candidate eval records under `tests-or-evals/`. |
| `registry/harness-discovery-methodology.json` | Radar method for discovering missing or underpowered coding harnesses. |
| `docs/HARNESS_DISCOVERY_RADAR.md` | Human-readable discovery loop for orphan/radar/research-to-harness work. |
| `registry/dad-offerings-registry.json` | Rich card catalog that exposes harnesses next to assets, skills, templates, and maps. |
| `processed/usage/repo-asset-usage.jsonl` | Central usage ledger for repos using or watching harnesses and other DAD offerings. |

## CLI

```text
asset-dir harness list
asset-dir harness recommend --repo <repo> --task "<task>"
asset-dir harness discovery-methodology
asset-dir harness discover --repo <repo> --task "<task>"
asset-dir harness research --harness <id>
asset-dir harness evaluate --harness <id> --repo <repo>
asset-dir harness package --harness <id>
```

Research and evaluation outputs are candidate-only generated reports under
`processed/harnesses/`.

Every harness directory must contain at least one concrete non-README artifact
in `scripts/`, `tests-or-evals/`, and `examples/`. README-only harness folders
fail DAD validation because they look more complete than they are. Eval JSON
files under `tests-or-evals/` must conform to
`schemas/coding-harness-eval.schema.json`.

## Initial Harness Families

- Python test performance and orchestration.
- Rust shadow/parity for Python test replacement candidates.
- AI engineering preflight.
- Agent-instruction and code-review red-team.
- Repo enrollment/mail/governance safety.
- Public/private source provenance.
- Exception learning readiness for mixed-evidence, fix-outcome, release, and
  backfill promotion boundaries.
- Language frontier harnesses for Python, Rust, and future languages. These
  convert source-watch discoveries into small validation cases before DAD
  changes coding guidance or downstream recommendations.

## Language Frontier Harness Rule

When a Python, Rust, or future-language source suggests a coding improvement,
DAD should ask whether it needs a harness before it becomes advice:

- performance claims need same-workload timing and correctness evidence;
- parsing, chunking, scanning, routing, hashing, and serialization claims need
  malformed-input or property/fuzz cases;
- type, lint, compiler, and test-runner claims need commands that future agents
  can run and audit;
- crate, package, or tool recommendations need license, maintenance, and
  compatibility screening.

If a discovery cannot name a validation command or eval idea, it stays as a
pointer-only research note.

## Adoption Flow

1. A repo receives mail or runs `asset-dir dad match --repo <repo>`.
2. The repo decides `implement_now`, `save_for_future`, `defer`, `reject`, or `archive`.
3. Future-use or implemented items write `.digital-asset/mail/adoption.jsonl`.
4. The repo records usage with `asset-dir usage record`.
5. DAD can later send upgrade notices only to repos that use or watch the asset.

## Boundaries

- Coding harnesses may recommend tests or scripts, but local repo authority
  decides implementation.
- Public-facing repos receive public-safe pointers by default.
- Logos Scripture Graph and Logos Governance require explicit local-write
  approval even for enrollment repair.
- Mock Trial/Albert follows normal reviewed-policy enrollment/mail rules rather
  than a special protected-repo class.
