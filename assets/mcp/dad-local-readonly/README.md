# DAD Local Read-only MCP Host Adapters

This bundle configures existing AI hosts to start DAD's one local, read-only
stdio MCP server. It does not create a second server, contact a remote service,
use a vendor SDK, install configuration, or grant execution authority.

## Canonical server

- Logical name: `dad-local-graph-surfaces`
- Implementation: `digital_asset_directory.mcp_server:DADGraphMCPServer`
- Direct executable: the Python interpreter identified by `DAD_PYTHON`
- Arguments: `-m digital_asset_directory.cli mcp graph-stdio --hub DAD_HUB`
- Transport: local stdio only
- Authority: read-only candidate evidence; no Git or DAD execution authority

`DAD_PYTHON` must identify the Python executable for an environment in which
the DAD package is installed. On Windows this should normally be the environment's
`python.exe`, not a PowerShell, CMD, batch, or shim wrapper. `DAD_HUB` identifies
the initialized DAD hub directory.

## Templates and host locations

| Host | Template | Intended host file | Variable handling |
|---|---|---|---|
| Codex project | `templates/codex.project.config.toml` | `.codex/config.toml` | Render `{{DAD_PYTHON}}` and `{{DAD_HUB}}` before merging. |
| Codex global | `templates/codex.global.config.toml` | user `config.toml` | Render both placeholders before merging. |
| Claude Code | `templates/claude-code.project.mcp.json` | project `.mcp.json` | Native `${DAD_PYTHON}` and `${DAD_HUB}` expansion. |
| Claude Desktop | `templates/claude-desktop.mcp.json` | `claude_desktop_config.json` | Render both placeholders before merging. |
| Cursor | `templates/cursor.mcp.json` | project or user `mcp.json` | Native `${env:DAD_PYTHON}` and `${env:DAD_HUB}` expansion. |
| VS Code / GitHub Copilot | `templates/vscode-github-copilot.mcp.json` | workspace or profile `mcp.json` | Native `${env:DAD_PYTHON}` and `${env:DAD_HUB}` expansion. |
| GitHub Copilot CLI | `templates/github-copilot-cli.mcp-config.json` | user `mcp-config.json` | Render both placeholders before merging. |

These are fragments for a governed merge. Never overwrite an existing host
configuration. Only merge the named server after reviewing the resolved Python
executable, hub, host, and scope. Host trust or activation is a separate human
gate. Removing the named server entry is the rollback.

## Validation

Run `python assets/mcp/dad-local-readonly/validate.py`. A valid result proves
that every declared template normalizes to the same logical server, direct
Python command, argument vector, tool allowlist, and authority metadata. It also
rejects absolute paths, credential-like fields, remote transports, shell
wrappers, undeclared templates, and conflicting server definitions.

The validator does not start the server and does not edit any host file.

Repository validation also checks `registry/mcp-dependency-map.json`. That map
binds the server's important dependency categories, source-to-sink flows,
runtime tool/resource inventory, local Python imports, CLI/packaging coupling,
authority direction, and downstream change effects. Dedicated MCP artifacts use
exact hashes; selected semantics are used for shared files. A stale map blocks
current impact claims. The MCP refresh surface calculates a review candidate
only and never changes the map or host configuration.

`installed-host-evidence.json` is a privacy-safe named-server observation. It
does not retain host config payloads or paths and does not equate a reusable
template, a configured entry, an initialize handshake, and active host use.

`task-mesh/mcp-dependency-repair-planning.json` and its execution successor are
task-local candidate coordination evidence. They record the material checker
mission delta after independent findings while preserving one writer, a
separate read-only checker, delegation depth one, and no execution authority.

## Host-shape sources

The template shapes were checked against first-party documentation on
2026-07-13:

- OpenAI Codex MCP configuration: <https://learn.chatgpt.com/docs/extend/mcp.md>
- Claude Code MCP configuration: <https://code.claude.com/docs/en/mcp>
- Cursor MCP configuration: <https://cursor.com/docs/mcp.md>
- VS Code MCP configuration: <https://code.visualstudio.com/docs/agents/reference/mcp-configuration>
- GitHub Copilot CLI MCP configuration: <https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers>

Host formats can change. Recheck those sources before changing or installing a
template. The DAD contract remains vendor-neutral even when a host adapter
changes.
