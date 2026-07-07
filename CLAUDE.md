@AGENTS.md

## Claude Code integration

- Project hooks under `.claude/settings.json` create session/audit records and check for a postflight before a changed working tree is allowed to stop cleanly.
- Treat `CLAUDE.md` as guidance and the hooks/Git checks as enforcement support.
- Treat Claude Code support as an optional adapter over the agent-agnostic DAD lifecycle. DAD governance lives in `AGENTS.md`, the DAD CLI, schemas, audit records, deterministic hooks, and human gates.
- Do not disable hooks to bypass a failed gate. Report the gate and fix the cause.

<!-- BEGIN DIGITAL_ASSET_DIRECTORY_CLAUDE_IMPORT -->
@AGENTS.md

Claude Code should follow the DAD enrollment contract in `AGENTS.md` and
`.digital-asset/dad-integration.json`. `CLAUDE.md` is an optional runtime
adapter, not the source of DAD governance truth. Agent review is triage only;
human approval gates remain separate.
<!-- END DIGITAL_ASSET_DIRECTORY_CLAUDE_IMPORT -->
