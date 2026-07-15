# Project Position and Right-Sized Completion Contract

## Purpose

Diagnose what a project currently is, what works, what is broken, why it exists,
where Lowell wants it to go, and the smallest sufficient route from here to
there. The diagnostic is read-only candidate evidence. It does not turn every
request into a complete product lifecycle and does not authorize work.

Use this contract for an existing idea, repository, worktree, partial build,
feature, integration, prototype, service, or product when its position, purpose,
destination, or finish line is unclear.

## Two independent axes

Never collapse observed position and desired destination.

1. **Observed position** comes from bounded evidence: project/repository
   identity, current project-management state, artifacts, tests, working and
   broken surfaces, accepted decisions, dependencies, delivery evidence, and
   unavailable sources. Activity, file count, branch age, TODO count, or model
   confidence cannot establish purpose or completion.
2. **Desired destination** belongs to Lowell. It is `unknown`, `proposed`, or
   `human_confirmed`. Until confirmed, the system may diagnose, compare options,
   and ask questions, but it cannot create an execution handoff.

The project keeps the canonical project-management durable-state vocabulary:
`proposed`, `active`, `paused`, `snoozed`, `incubating`, `merged`,
`superseded`, or `archived`. Readiness, focus, blocking, validation, delivery,
recovery, and evidence stage remain candidate overlays; the diagnostic never
turns them into a second lifecycle.

## Evidence-stage projection

Select the latest stage actually supported by evidence and preserve mixed or
unknown surfaces explicitly:

- `unknown`
- `problem-framed`
- `solution-shaped`
- `implementation-underway`
- `integrated`
- `validated`
- `released`
- `operating`
- `recovery`

This stage is descriptive, not a command to execute the next stage. A validated
library may already be complete. A released prototype may intentionally never
become a production service.

## Destination class and completion depth

Lowell chooses the intended end-state class:

- `answer-or-decision`
- `reusable-artifact`
- `bounded-change`
- `integration`
- `prototype`
- `pilot`
- `mvp`
- `major-product`
- `production-service`
- `operating-system`
- `maintenance-only`
- `retire-or-archive`
- `unknown`

Then choose the completion depth for this engagement:

- `diagnose-only`
- `repair-current-intent`
- `complete-bounded-outcome`
- `integrate-with-target`
- `validate-existing-build`
- `productionize-approved-scope`
- `maintain`
- `retire`
- `unknown`

The destination class describes the durable end state. Completion depth
describes how far this engagement may go. A major product can receive a
diagnose-only or bounded integration engagement. A small reusable artifact can
be completed without activating the rest of the product portfolio.

## Basic issue diagnosis

Emit zero or more reason codes, with evidence and affected surfaces:

- `identity-unclear`
- `purpose-unclear`
- `destination-unconfirmed`
- `acceptance-missing`
- `scope-drift`
- `duplicate-or-related-work-unresolved`
- `broken-build-or-test`
- `missing-dependency`
- `dependency-cycle`
- `integration-target-unknown`
- `integration-contract-missing`
- `mcp-fit-unknown`
- `data-or-schema-gap`
- `security-or-privacy-gate`
- `ui-ux-gap`
- `accessibility-gap`
- `deployment-or-operations-gap`
- `stale-or-conflicting-authority`
- `validation-gap`
- `release-or-handoff-gap`
- `none-observed`

An issue code is not a work order. The diagnostic returns evidence,
counterevidence, confidence basis, and the smallest next check.

## Human clarification

Ask only questions that materially change the route and expose at most three at
once. Reuse answers already present in authoritative evidence. Prefer:

1. What durable end state should exist when this project is truly done?
2. How far should this engagement go now?
3. What must it integrate with, and what permission, data, security, cost, or
   deployment constraints govern that boundary?

If the answer is unknown, offer bounded options plus `diagnose-only`,
`incubate`, and `preserve-current`. Silence never confirms a destination.

## MCP-first integration assessment

When the desired outcome requires agents or systems to exchange context or
invoke bounded behavior, route through the existing Integration/MCP/Automation
family. Evaluate the smallest interface first:

- resource for read-only context;
- prompt for a reusable human-invoked workflow;
- tool for a bounded action with explicit permissions;
- a combination when the interfaces are independently justified; or
- `not-applicable` when an internal function, file, CLI, library call, or
  ordinary user interface is simpler.

Direct APIs are fallback adapters only under `docs/MCP_FIRST_INTEGRATION_POLICY.md`.
No design grants credentials, host configuration, plugin installation, connector
activation, or side-effect permission.

## Right-sized routing

1. Diagnose locally and deterministically where possible.
2. If purpose/destination is unknown, route only the project-position
   diagnostician and return the human questions.
3. After confirmation, retrieve at most three primary capabilities plus exact
   prerequisites and independent validators.
4. Activate a specialist pack role only for a named gap. Never activate a whole
   MCP or UI/UX suite because its parent family matched.
5. Product catalyst is optional for an unresolved problem or alternative. The
   project manager is optional and starts only after outcome and project identity
   are approved.
6. Full software-product delivery is reserved for an explicitly approved major
   product, MVP, production-service, or operating-system engagement whose
   acceptance matrix actually requires that workflow.
7. Stop at the confirmed sufficient condition. Do not add production, cloud,
   telemetry, analytics, accounts, mobile, design systems, automation, or
   integrations merely because they could be useful later.

## Required output

Emit `dad.project_position_diagnosis.v1` containing:

- coverage and unavailable evidence;
- stable project identity and existing PM state;
- evidence stage and working/broken/incomplete surfaces;
- issue codes with evidence;
- purpose and destination confirmation state;
- destination class, completion depth, integration targets, non-goals, and
  sufficient-stop condition;
- MCP-first applicability and selected interface class;
- smallest selected capabilities, prerequisites, validators, and suppressed
  capabilities;
- at most three human decisions;
- smallest reversible next action and execution-handoff status; and
- explicit `execution_authorized: false`.

`human_confirmed` requires a human decision reference bound to the exact
destination, completion depth, acceptance, non-goals, and sufficient-stop
contract. A candidate execution handoff additionally requires producer and
independent-validation references. These references attest evidence; they do
not authorize execution or create an approval graph edge.

## Acceptance tests

- A request to fix one test does not activate full-stack delivery, Product/UX,
  Platform, or MCP without separate evidence.
- A request to connect an existing tool to an agent can route MCP specialists
  without productizing the repository.
- An unfinished repository with no confirmed destination returns questions and
  no execution handoff.
- A human-confirmed reusable script can stop when its contract and tests pass;
  production-service capabilities remain suppressed.
- A major product request still begins with current-position evidence and a
  confirmed acceptance matrix; “major” does not waive scope control.
- The route preserves at most three primary capabilities and three immediate
  human decisions.
- Identical evidence and confirmed decisions produce the same candidate route.
- No project state, task, Git artifact, schedule, notification, connector, or
  external system is mutated.

## Kill conditions

Stop when the diagnostic infers user intent from activity, treats age or
incompleteness as a mandate to continue, creates a competing lifecycle, hides
unavailable evidence, routes every family, exceeds three immediate decisions,
or emits an execution handoff before destination and completion depth are
human-confirmed.
