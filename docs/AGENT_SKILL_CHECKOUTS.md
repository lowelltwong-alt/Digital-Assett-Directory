# Agent Skill Checkouts

Status: downstream checkout pattern for DAD-managed agent skills.

## Recommended Files

A repo that wants DAD skill awareness should use the smallest local surface that
works:

```text
.digital-asset/skills/checkout.json
.digital-asset/mail/README.md
optional .agents/skills/<skill-name>/SKILL.md wrapper
```

Templates:

```text
templates/downstream/AGENT_SKILL_POINTER.template.json
templates/downstream/AGENT_SKILL_MANAGED_BLOCK.md
templates/downstream/MAIL_README.md
```

## Checkout Flow

1. Target repo reviews its local authority files.
2. DAD renders a checkout dry-run:

   ```text
   python scripts/render_agent_skill_checkout.py --skill-id skill:dad-coding-asset-control-plane --hub ../Digital-Assett-Directory
   ```

3. Target repo commits a pointer only after local approval.
4. DAD records the checkout in `processed/skills/checkouts.jsonl` or a later
   reviewed central checkout store.
5. DAD sends update, retirement, and replacement notices through candidate mail.
6. Target repo decides whether to update, replace, defer, or remove the checkout.

Render a small wrapper instead of JSON:

```text
python scripts/render_agent_skill_checkout.py --skill-id skill:dad-coding-asset-control-plane --mode wrapper --hub ../Digital-Assett-Directory
```

The renderer prints to stdout by default and refuses to overwrite output files
unless `--force` is used.

Rendered pointers use public-safe `dad://` references by default. Local absolute
paths are private/internal hints and require:

```text
python scripts/render_agent_skill_checkout.py --skill-id skill:dad-coding-asset-control-plane --hub ../Digital-Assett-Directory --include-local-paths
```

## Local Review Rules

- Do not copy full DAD skills into another repo without explicit approval.
- Do not install plugins, hooks, MCP servers, or automation from a checkout
  pointer alone.
- Preserve target repo files outside approved managed markers.
- Treat skill mail as candidate evidence until reviewed locally.
- Pin the DAD `skill_id`, `version`, `source_path`, and `source_provenance` so a
  repo split, copy, or rename does not lose the return address.
- If a repo is renamed or split, keep the old checkout record in archive and add
  a new one with the new repo identity.

## What Breaks On Rename Or Split

The skill system should not break if the repo path changes, as long as the
checkout record keeps stable identifiers:

- `source_skill_id`
- `source_version`
- `source_repo_id`
- `source_path`
- `dedupe_key`
- `return_address`

Path-only references are fragile. DAD mail and checkout records should use
stable repo aliases or IDs when known, and store path as current location
metadata rather than identity.
