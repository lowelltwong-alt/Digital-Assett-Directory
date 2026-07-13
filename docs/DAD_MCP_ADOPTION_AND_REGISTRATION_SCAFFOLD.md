# DAD MCP Adoption And Registration Scaffold

Status: governed scaffold only. This document does not install, register, or
start an MCP server.

DAD already has a local read-only stdio MCP server for graph surfaces:

- canonical implementation: `src/digital_asset_directory/mcp_server.py`;
- compatibility facade: `src/digital_asset_directory/mcp_graph_server.py`;
- CLI entry point: `asset-dir mcp graph-stdio --hub <DAD-root>`;
- downstream declaration: `templates/downstream/DAD_INTEGRATION.template.json`
  declares `mcp.mode = local_stdio_read_only`.

The missing piece for downstream repositories is a reviewed adoption packet that
tells Codex, Cursor, Claude Code, or another host exactly what may be registered
after human approval. This scaffold fills that gap without changing global tool
configuration by itself.

## Authority Boundary

MCP is a transport, resource, tool, and prompt boundary. It is not DAD
authority. Durable authority remains:

- the downstream repo's `AGENTS.md` and local front door;
- DAD enrollment and governance contracts;
- DAD CLI lifecycle evidence;
- schemas, validators, audit records, Git review, and human gates.

No agent may install, enable, or register a DAD MCP server in Codex, Cursor,
Claude Code, or another global/user configuration unless a human explicitly
approves the adoption request for that host and scope.

## Adoption Packet

A downstream repo that wants DAD MCP access should create a reviewed adoption
packet from `templates/downstream/MCP_ADOPTION_REQUEST.template.json`.

The packet must record:

- repo ID and local repo path;
- intended host: `codex`, `cursor`, `claude_code`, or another named host;
- DAD hub path;
- exact command and args to launch the server;
- allowed resources/tools;
- side-effect policy;
- privacy boundary;
- human approval ID;
- rollback/removal instructions.

The safe default is read-only graph/resource access only:

```text
asset-dir mcp graph-stdio --hub <DAD-root>
```

If `asset-dir` is not on `PATH`, the packet may use the repo-local Python module
entry point from a reviewed DAD checkout, but it must name the checkout path and
must not silently fall back to an unrelated global install:

```text
python -m digital_asset_directory.cli mcp graph-stdio --hub <DAD-root>
```

## Downstream Repo Pattern

For repos such as Albert, do not copy DAD's MCP server as source authority.
Reuse the pattern:

- stdio first;
- dependency-light runtime;
- read-only resources before tools;
- URI allowlists and hostile URI tests;
- tool calls as thin wrappers over existing CLI scripts and validators;
- explicit authority-boundary fields in responses;
- no vendor SDK, direct model key, cloud upload, or external API by default;
- no raw/private payloads sent to DAD;
- side effects fail closed unless exact confirmation fields, review status, and
  validator evidence are present;
- response fields avoid false authority such as uncalibrated `best`, `top`,
  `rank`, or hidden scoring claims.

Albert-specific examples may include:

- `albert://case/{case_id}/status`;
- `albert://case/{case_id}/artifacts`;
- `albert://case/{case_id}/graphlite`;
- `albert://case/{case_id}/review-queue`;
- tools such as `prepare_case_query`, `run_source_bound_case_query`,
  `get_query_evidence`, and `save_case_output`.

Those are Albert-native tools and resources. They may follow DAD's MCP safety
shape, but they do not inherit DAD authority and must pass Albert's local
validators.

## Host Registration Guidance

This document intentionally avoids checked-in user-specific config snippets.
Different hosts store MCP configuration in different user or workspace files,
and those files may contain private paths or credentials.

When a human approves host registration, the implementing agent should:

1. read the host's current official MCP configuration instructions;
2. create a host-specific registration draft from the approved adoption packet;
3. show the exact command, args, working directory, and removal steps;
4. apply the config only if the human approved that host and scope;
5. run a read-only MCP list-resources/list-tools smoke test;
6. record validation evidence in the downstream repo and DAD postflight.

Do not enable side-effecting DAD MCP tools through this scaffold. A separate
policy and approval packet is required for any side-effecting MCP tool.

## Validation Checklist

Before registration is considered ready:

- DAD MCP server tests pass, especially hostile URI and candidate-boundary
  tests.
- The downstream repo records that DAD is candidate evidence only.
- The adoption packet has a human approval ID.
- No secrets, client payloads, raw case files, or private source text appear in
  the packet.
- The rollback instructions are executable by a human.
- The host registration draft names the exact server command and DAD hub.

If any item fails, do not register the MCP server.
