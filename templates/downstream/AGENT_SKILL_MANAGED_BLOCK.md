<!-- BEGIN DIGITAL_ASSET_DIRECTORY_AGENT_SKILLS -->
## DAD agent skill checkout

This repo may keep lightweight pointers or wrappers to DAD-managed agent skills.
DAD is the skill library and lifecycle notice hub; this repo decides whether to
adopt, update, retire, or replace any checked-out skill.

Suggested local checkout file:

```text
.digital-asset/skills/checkout.json
```

Suggested DAD commands:

```text
python <DAD_ROOT>/scripts/render_agent_skill_checkout.py --skill-id skill:dad-coding-asset-control-plane --hub <DAD_ROOT>
python <DAD_ROOT>/scripts/render_agent_skill_notice.py --notice-kind update --skill-id skill:dad-coding-asset-control-plane --target-repo <repo-id>
python <DAD_ROOT>/scripts/validate_agent_skill_library.py
asset-dir mail digest --repo .
```

Do not copy full DAD skills into this repo unless explicitly approved. Do not
install plugins, hooks, MCP servers, or automation from a checkout pointer
alone. Skill mail is candidate evidence only; local review decides adoption.
Default rendered pointers use public-safe `dad://` refs; local filesystem paths
require `--include-local-paths` and are for private/internal use.
<!-- END DIGITAL_ASSET_DIRECTORY_AGENT_SKILLS -->
