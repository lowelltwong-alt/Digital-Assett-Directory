---
name: codex-capability-radar
description: Match available Codex capabilities to a task using local inspection, official-first verification, explicit privacy boundaries, and user approval gates.
---

# Codex Capability Radar

1. Inspect locally available models, skills, plugins, tools, and platform
   constraints before recommending a capability.
2. Verify changing capabilities against current official documentation. Treat
   community reports as dated candidate evidence, never product authority.
3. Match the need to the smallest surface: skill, plugin or app, command,
   subagent, worktree, scheduled task, long-running goal, hook, memory,
   browser or computer control, or visual tool.
4. Recommend at most three high-leverage changes. Explain benefit, cost,
   privacy boundary, platform availability, and validation.
5. Do not install plugins, enable persistent capture, modify global
   configuration, or create automations without explicit user approval.
6. Recheck availability before use because models and platform support change.

This skill is a runtime-capability routing aid. It does not authorize product
configuration changes, persistent data capture, or any action that local policy
or a human gate reserves.
