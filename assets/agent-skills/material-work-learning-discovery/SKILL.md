---
name: material-work-learning-discovery
description: Run after material builds, refactors, investigations, or cross-repo work to close learning loops; find reusable digital assets and new asset-discovery patterns; compare explicit conversation value with committed artifacts; screen exceptional prompts; and route privacy-safe candidate lessons back to DAD. Use before postflight whenever an agent materially changes or studies a DAD-enrolled repo.
---

# Material Work Learning Discovery

Apply this workflow before postflight for every material DAD or DAD-enrolled
repo task. Skip only trivial queries or commands that produced no material
decision, artifact, failure, or reusable observation.

## Run The Lanes

Check `registry/agent-skill-library.json`, DAD lessons, asset registries, and the
repo context pack first. Reuse matching agents and lessons before creating new
ones.

Start these AI-agnostic lanes when subagents are available:

1. Run the learning-loop sentinel at low effort. Escalate to medium, high, then
   frontier effort only when the loop is incomplete, ambiguous, conflicting,
   or high leverage.
2. Run the digital-asset and discovery-pattern miner at high effort for novel
   assets, missed-asset signals, and better ways to detect or apply assets.
3. Run the conversation-delta analyst at medium effort to find explicit
   decisions, tradeoffs, rejected options, hypotheses, failed attempts, user
   constraints, and operational discoveries absent from final artifacts.
4. Run the prompt curator at low effort. Escalate only prompts or prompt
   fragments that are unusually reusable, structured, novel, or outcome
   improving; ignore routine status checks and short project questions.
5. Run the reuse-and-application reviewer at high effort to identify where an
   existing or newly discovered asset should be applied, tested, or avoided.

If subagents are unavailable, execute the same lanes as explicit checklists and
record the fallback. Read `subagents.yaml` for role contracts and escalation.

## Compare Against Material Artifacts

Inventory code, tests, docs, reports, decisions, mail, exceptions, and already
captured lessons. Report only the delta that would otherwise be lost. Prefer
short structured summaries with paths, hashes, issue classes, evidence refs,
fix refs, validator refs, applies-when, and does-not-apply-when.

Do not store raw transcripts, hidden chain-of-thought, secrets, credentials,
private rows, raw case facts, long logs, or full source blobs. Conversation
analysis may capture explicit rationale stated by participants, but must never
infer or request private internal reasoning.

## Close The Loop

For every candidate:

- dedupe against existing DAD assets, lessons, prompts, patterns, and agents;
- classify as `reuse_existing`, `improve_existing`, `new_candidate`, `defer`,
  or `reject`;
- record evidence, confidence, scope, privacy, and authority boundaries;
- name a target repo or workflow where application can be tested;
- define a validator or falsifiable success measure;
- rate every reused or newly created subagent after use;
- record whether the loop is complete and the next action if it is not.

In downstream repos, emit candidate learning only through locally allowed DAD
outbox paths. In DAD itself, use postflight and governed candidate registries.
Never silently promote a lesson, prompt, pattern, agent, or asset to source
truth and never mutate another repo from this skill.
