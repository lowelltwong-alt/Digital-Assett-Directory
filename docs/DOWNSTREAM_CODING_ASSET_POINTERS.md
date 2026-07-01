# Downstream Coding Asset Pointers

Status: candidate pointer pattern for persistent repos that want DAD coding
asset guidance without copying full DAD assets.

## Files

Recommended pointer surfaces:

```text
.ai-assets.json
.digital-asset/skills/checkout.json
AGENTS.md managed block
.digital-asset/mail/README.md
```

Templates:

```text
templates/downstream/AI_ASSETS_POINTER.template.json
templates/downstream/CODING_ASSET_MANAGED_BLOCK.md
templates/downstream/AGENT_SKILL_POINTER.template.json
templates/downstream/AGENT_SKILL_MANAGED_BLOCK.md
templates/downstream/MAIL_README.md
```

## Rules

- The target repo must approve installation.
- Preserve local content outside managed markers.
- Do not copy full DAD assets into the repo unless explicitly approved.
- Do not install hooks, plugins, skills, MCP servers, or automation without
  separate human review.
- Agent skills should be checked out by pointer or wrapper from
  `registry/agent-skill-library.json`; do not copy full DAD skills without
  explicit approval.
- Mail is candidate-only and local review decides adoption.
- Public-facing repos need DAD mail provenance and human release gates before
  private/internal/restricted/unknown-origin mail can be delivered.

## Render Pointer

Dry-run to stdout:

```text
python scripts/render_downstream_coding_pointer.py --hub ../Digital-Assett-Directory
```

Write only when the target repo has approved the pointer:

```text
python scripts/render_downstream_coding_pointer.py --hub ../Digital-Assett-Directory --output .ai-assets.json
```

The renderer refuses to overwrite an existing output unless `--force` is
provided.

Render a skill checkout pointer:

```text
python scripts/render_agent_skill_checkout.py --skill-id skill:dad-coding-asset-control-plane --hub ../Digital-Assett-Directory
```

The default skill pointer is public-safe and uses stable `dad://` references.
Use `--include-local-paths` only for private/internal repos where local path
hints are appropriate.

## Suggested Managed Block

Use `templates/downstream/CODING_ASSET_MANAGED_BLOCK.md` inside a target repo's
AI front door or root agent instruction file only after local approval. The
block tells future agents to run DAD preflight, consult DAD coding assets, and
capture postflight lessons.

Use `templates/downstream/AGENT_SKILL_MANAGED_BLOCK.md` only after local
approval when a repo should know how to check out DAD-managed agent skills and
receive skill update, retirement, or replacement notices.

## Rollback

Rollback is local and simple:

- remove `.ai-assets.json`;
- remove `.digital-asset/skills/checkout.json` or the local skill wrapper;
- remove the managed block between DAD coding-asset markers;
- keep or archive local mailbox files according to the target repo's policy.
