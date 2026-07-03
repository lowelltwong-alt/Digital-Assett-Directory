# Coding Asset Control Plane

Status: candidate DAD-side control plane for routing AI coding agents to reusable
assets, coding tactics, preflight profiles, downstream pointers, and candidate
mail packets.

## Purpose

DAD is the hub for reusable AI coding assets. A target repo keeps its own
authority, but a future agent should be able to start locally, see a small DAD
pointer, run DAD preflight, select the right coding profile, work with
midflight checks, and report useful lessons back to DAD.

This control plane is not a one-off template install. It is an asset discovery
and routing layer:

```text
target repo front door
-> DAD preflight
-> coding asset registry
-> preflight profile router
-> coding tactics radar
-> local implementation and validation
-> DAD postflight feedback
-> candidate mail to other repos when useful
```

## Authority Boundary

DAD owns reusable asset discovery, cataloging, routing, learning, and governed
reuse. DAD does not silently mutate source repos, override a repo's canon, or
promote generated tactics into reviewed doctrine without review evidence.

Downstream repos receive only lightweight pointers, local mailbox files, and
managed instruction blocks after local approval. Full DAD assets stay in DAD.

## Installed Assets

Requested zips found in Downloads:

- `ai-engineering-preflight-asset-v0.1.0.zip` and duplicate `(1)`; both hash to
  `933c2a5ccf640b90c6fb8c97ed28bf8081c6fd6fcaa01a08133ec1f8fdd21e73`.
- `python-ai-advantage-preflight-asset-v0.1.0.zip` and duplicates `(1)`/`(2)`;
  all hash to `324b66b23015c46fde818fcc4758505f29d231de9989884ffbc4a0b233b09673`.
- `lowelltwong-alt-repo-map-and-wave-plan-v0.1.0.zip` hashes to
  `fd3e30b22beea019e069682d7beb9f524bda4e3e7f1ddc2897ba1c85ad840f2d`.

Requested zips not found under the requested names in Downloads during this
pass:

- `dad-control-plane-rollout-kit-v0.1.0.zip`
- `dad-cross-repo-rollout-bundle-v0.1.0.zip`

The new Python asset is installed at:

```text
assets/python-ai-advantage-preflight/
```

Bytecode and `__pycache__` files from the zip were intentionally excluded.

## Core Surfaces

| Surface | Role |
| --- | --- |
| `registry/coding-asset-registry.json` | Catalog of reusable coding assets, profiles, validation, authority boundaries, review cadence, and evidence. |
| `registry/language-coding-advantage-registry.json` | Python, Rust, and future-language advantage contracts with trusted sources, overlooked patterns, harness routes, validation gates, and candidate-only adoption rules. |
| `registry/coding-tactics-radar.json` | Candidate tactics with applicability, non-applicability, danger, examples, verification, evidence, and promotion status. |
| `registry/preflight-profile-router.json` | Task/context to profile/tactic/validation routing. |
| `templates/downstream/AI_ASSETS_POINTER.template.json` | Lightweight pointer file for target repos. |
| `templates/downstream/CODING_ASSET_MANAGED_BLOCK.md` | Managed block for AI front doors or root agent files. |
| `templates/mail/*.mail.template.json` | Candidate mail packet templates for cross-repo suggestion transport. |
| `templates/tactic-use-feedback.template.json` | Postflight feedback packet for tactic usefulness and failures. |
| `registry/agent-skill-library.json` | Catalog of DAD-managed agent skills, checkout modes, lifecycle state, and update/retirement notice templates. |
| `templates/downstream/AGENT_SKILL_POINTER.template.json` | Lightweight pointer for repos that check out DAD-managed skills without copying full skill bodies. |

## Agent Flow

1. Read the target repo's local `AGENTS.md`, `CLAUDE.md`, AI front door, or
   equivalent.
2. Follow the local pointer to DAD when present.
3. Run DAD preflight.
4. Use `registry/preflight-profile-router.json` to choose required profiles and
   candidate tactics.
5. Use local validation and repo authority while coding.
6. Run midflight tactic recommendation when stuck or when code is drifting
   toward generic patterns.
7. Run postflight and capture tactic feedback if a tactic helped, failed, or
   should be added.
8. Route cross-repo suggestions through DAD mail as candidate packets only.
9. For reusable agent skills, render a pointer or wrapper from
   `registry/agent-skill-library.json`; updates, retirements, and replacements
   move by candidate mail and require local adoption.

## Mail Behavior

Control-plane mail packets are implementation suggestions, not commands. They
include target repo, source asset, profile, suggested local files, exact pointer
or managed-block content, evidence, risks, acceptance checks, validation
commands, and rollback notes.

Mail remains candidate-only even after delivery. Target repos decide whether to
incorporate anything through local preflight, implementation, validation, and
postflight.

Public-facing delivery inherits `docs/MAIL_CENTER.md`: private, internal,
restricted, or unknown source origins require explicit human release before
delivery to a public-facing repo.

## Risk Tier

This control plane is `risk_tier=high` because it affects future agents,
schemas, registries, templates, mail packets, and downstream repo behavior. The
bounded implementation reduces blast radius by:

- staying inside DAD-side registries, docs, templates, scripts, and master
  assets;
- avoiding downstream repo mutation;
- preserving candidate/reviewed/promotion separation;
- validating new registries against schemas;
- keeping pointer rendering dry-run/stdout by default;
- requiring local adoption and human gates for public/private boundary moves.

## Sources

- OpenAI Codex AGENTS guidance: https://developers.openai.com/codex/guides/agents-md
- OpenAI Codex customization and skills: https://developers.openai.com/codex/concepts/customization
- Anthropic Claude Code overview and skills: https://docs.anthropic.com/en/docs/claude-code/overview
- Cursor rules: https://cursor.com/docs/rules
- GitHub Copilot custom instructions: https://docs.github.com/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot
- Python docs: https://docs.python.org/3/
- pytest docs: https://docs.pytest.org/
- Hypothesis docs: https://hypothesis.readthedocs.io/
- Rust docs: https://doc.rust-lang.org/
- Rust API Guidelines: https://rust-lang.github.io/api-guidelines/about.html
- Rust Fuzz Book: https://rust-fuzz.github.io/book/
- cargo-nextest: https://nexte.st/
- AI-code security study: https://arxiv.org/abs/2211.03622
