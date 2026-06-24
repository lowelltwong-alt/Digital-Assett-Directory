@AGENTS.md

## Claude Code integration

- Project hooks under `.claude/settings.json` create session/audit records and check for a postflight before a changed working tree is allowed to stop cleanly.
- Treat `CLAUDE.md` as guidance and the hooks/Git checks as enforcement support.
- Do not disable hooks to bypass a failed gate. Report the gate and fix the cause.
