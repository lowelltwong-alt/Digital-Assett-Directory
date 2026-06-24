# AI Governance

## Front-door strategy

- Codex reads `AGENTS.md` before work.
- Claude Code reads `CLAUDE.md`, which imports `AGENTS.md`.
- Claude project hooks record sessions and tool events and check for a postflight when the working tree changed.
- Git pre-push enforcement is tool-neutral and can require a current handoff for changed work.

## Behavioral guidance versus enforcement

Instruction files guide model behavior. Enforcement belongs in deterministic hooks, validators, Git hooks, CI, and review policy.

## Handoff quality

Automatic hook capture is a fallback, not the preferred record. An explicit postflight should replace the draft with task context, tests, uncertainty, and reusable lessons.

## Agent swarm recommendations

The catalog may recommend specialized roles based on task and assets:

- source/provenance steward;
- schema and ontology reviewer;
- code implementation agent;
- test/evaluation agent;
- security/license reviewer;
- orphan-link analyst;
- research scout;
- handoff and lesson curator.

No swarm role receives authority beyond the source repository's governance.
