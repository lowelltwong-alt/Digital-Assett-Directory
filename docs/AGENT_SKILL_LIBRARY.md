# Agent Skill Library

Status: governed DAD-side library for reusable agent skills, skill pointers,
skill lifecycle notices, and downstream checkout guidance.

## Purpose

DAD is the central library for agent skills that can help Codex, Claude Code,
Cursor, Copilot, and future agent environments. Other repos may "check out" a
skill by storing a small pointer or wrapper that names the DAD source, version,
return address, and update policy.

The checkout model is intentionally lightweight:

```text
DAD skill library
-> reviewed skill registry
-> downstream pointer or wrapper
-> repo-local approval and validation
-> DAD mail notices for updates, retirements, and replacements
```

The DAD registry is the lifecycle authority for DAD-managed skill metadata. A
target repo remains the authority for whether it adopts, updates, retires, or
replaces a checked-out skill.

## Core Surfaces

| Surface | Role |
| --- | --- |
| `registry/agent-skill-library.json` | Catalog of DAD skill records, lifecycle state, checkout modes, source paths, and update policy. |
| `schemas/agent-skill-library.schema.json` | Contract for the skill library registry. |
| `schemas/agent-skill-checkout-pointer.schema.json` | Contract for downstream skill checkout pointers rendered by DAD. |
| `assets/agent-skills/` | DAD-owned skill source directories. |
| `templates/downstream/AGENT_SKILL_POINTER.template.json` | Lightweight checkout pointer for repos that should not vendor skill content. |
| `templates/downstream/AGENT_SKILL_MANAGED_BLOCK.md` | Managed block for AI front doors or root agent files after local approval. |
| `templates/mail/skill-*.mail.template.json` | Candidate mail packets for skill checkout, update, retirement, and replacement notices. |
| `scripts/render_agent_skill_checkout.py` | Dry-run renderer for a pointer or wrapper from the registry. |
| `scripts/render_agent_skill_notice.py` | Dry-run renderer for skill checkout, update, and retirement mail notices from the registry. |
| `scripts/check_agent_skill_checkouts.py` | Dry-run checker for stale, retired, replaced, or unknown skill checkouts recorded in `processed/skills/checkouts.jsonl`. |
| `scripts/validate_agent_skill_library.py` | Registry, path, template, and mail-template validator. |

## Checkout Modes

| Mode | Use when | Boundary |
| --- | --- | --- |
| `pointer` | A repo only needs to know where the skill lives and when to check for updates. | Stores metadata only; no skill body is copied. |
| `wrapper` | A repo wants a tiny local `SKILL.md` that routes agents back to DAD. | Wrapper must state that DAD is source and local repo decides adoption. |
| `local_copy_requires_human_approval` | A repo must run offline or pin a full skill body. | Requires explicit human approval and provenance review. |
| `plugin_install_manual` | A skill is distributed through a plugin. | Human installs or upgrades the plugin; DAD only points to it. |

Default checkout is `pointer`. Renderers use public-safe `dad://` references by
default. Local filesystem paths are private/internal hints and require
`--include-local-paths`.

DAD must not silently write `.agents/skills/`,
`.codex/skills/`, `AGENTS.md`, `CLAUDE.md`, Cursor rules, plugins, hooks, or
source files in another repo.

## Lifecycle

Skill records use explicit lifecycle fields instead of inferred graph or score
changes:

- `active`: usable with its current applicability limits.
- `candidate`: available for experiment, not durable guidance.
- `deprecated`: still usable, but update or replacement is expected.
- `retired`: do not newly check out; existing checkouts should remove or pin
  with a local reason.
- `replaced`: use `replacement_skill_id` after local review.

When DAD updates, retires, or replaces a skill, it creates candidate mail. Mail
does not update the target repo. The target repo reviews the notice and decides
whether to change its local pointer or wrapper.

DAD tracks known downstream checkouts in append-only generated state:

```text
processed/skills/checkouts.jsonl
```

Check which repos need update or retirement notices:

```text
python scripts/check_agent_skill_checkouts.py
```

```text
python scripts/render_agent_skill_notice.py --notice-kind update --skill-id skill:dad-coding-asset-control-plane --target-repo <repo-id>
python scripts/render_agent_skill_notice.py --notice-kind retirement --skill-id <skill-id> --target-repo <repo-id>
```

Lifecycle notice rendering is fail-closed: notices default to
`public_release_status=pending_human`, and retirement notices require the skill
to be marked `deprecated`, `retired`, or `replaced` in the registry.

## Relationship Graph

```mermaid
flowchart TD
    A["DAD skill registry"] --> B["Pointer or wrapper checkout"]
    A --> C["Skill update notice"]
    A --> D["Skill retirement/replacement notice"]
    B --> E["Target repo local review"]
    C --> E
    D --> E
    E --> F["Local adoption, defer, reject, or archive"]
    F --> G["Postflight feedback to DAD"]
```

## Public And Private Boundary

Skill pointers can still leak sensitive context if they carry private source
paths, copied examples, or private repo descriptions. Cross-repo skill mail
therefore inherits `docs/MAIL_CENTER.md`:

- private, internal, restricted, or unknown source origins headed to a
  public-facing target are held for human release;
- skill mail is best-effort screened and candidate-only;
- payloads should contain short summaries, IDs, hashes, paths, and review notes,
  not raw copied code, secrets, private rows, or prompt blobs.

## Update Discipline

Other repos should check skill freshness through DAD mail or a scheduled digest,
not during every preflight. A repo-local preflight may warn that its skill digest
or mail digest is stale after 24 hours, but the central DAD job should be the
normal update path.

## No Scores

The skill library does not assign numeric value scores. Status, confidence, and
review posture are categorical lifecycle labels and must not be treated as proof
of usefulness.
