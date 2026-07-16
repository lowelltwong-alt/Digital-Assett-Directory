# Portable AI Capability Control Plane Build Plan

Status: decision-complete plan; implementation unstarted.

Planning base: `b34cf64` on the integrated Knowledge Engineering/Capability
OS lineage. Risk tier: high. This changes shared contracts, lifecycle gates,
runtime routing, evaluation, graph semantics, and defaults inherited by future
agents. It therefore requires fresh-eyes review, shadow rollout, rollback, and
named-human activation.

## Outcome

Create one small constitutional control layer that makes every reusable
AI-mediated capability discoverably portable, provider-neutral, and
model-retirement-ready without forcing every artifact to behave identically on
every runtime.

The governing rule is:

> Every reusable AI-mediated artifact must declare a provider-neutral core,
> explicit runtime adapters, and portability evidence, or carry a scoped,
> owned, expiring, human-reviewed environment-bound exception.

This rule applies to skills, agent profiles, subagent packs, agent families,
workflows, routines, triggers, harnesses, prompts, reusable libraries,
knowledge-system interfaces, evaluation packs, algorithm packs, and templates.
It does not authorize copying source corpora, installing runtimes, using a
provider, changing a default route, or retiring anything.

## Architectural decision

Use both deterministic enforcement and harnesses:

- Deterministically enforce objective invariants: identity, revision,
  core/adapter separation, capability contracts, source authority, privacy and
  effect boundaries, path/secret safety, lifecycle, evidence references,
  checker independence, exception expiry, and graph integrity.
- Use harnesses for semantic and behavioral compatibility: output quality,
  tool behavior, context use, prompt fit, recovery, model-specific strengths,
  and cross-model comparison.
- Keep human gates for provider access, sensitive data, exceptions, promotion,
  default-route changes, supersession, retirement, persistent scheduling, and
  real side effects.

Reject two extremes:

1. Advisory-only portability, because it cannot prevent new model-bound debt.
2. Universal hard enforcement from day one, because legacy debt and semantic
   ambiguity would create noise and lowest-common-denominator design.

The recommended path is shadow -> warn -> block new/worsened objective
violations -> ratchet reviewed legacy assets -> activate selected gates.

## Existing implementation to preserve

The integrated planning base already contains:

- Generic agent-neutral session lifecycle and dirty-stop/postflight enforcement
  in `src/digital_asset_directory/agent_lifecycle.py`.
- Global personal-skill identity, inert revision archival, graph lineage, and
  reviewed path-safe exports in
  `src/digital_asset_directory/global_personal_skills.py`.
- Capability-routed Luna/Terra/Sol role contracts whose model IDs are attempt
  metadata in the family and subagent registries.
- Provider-neutral runtime capability snapshots, privacy/tool/context/cost
  filters, and one bounded fallback in
  `src/digital_asset_directory/runtime_resolver.py`.
- Immutable harness revisions, typed `argv[]`, `shell=false`, runtime-fit
  checks, shadow/pilot lifecycle, rollback, and human-gated retirement in
  `src/digital_asset_directory/harness_engineering.py`.
- Subagent attempt evaluation with an explicit five-dimension methodology,
  independent-review requirements, and candidate-only promotion decisions.
- Dependency, blast-radius, plan-memory, recovery, autonomy, cockpit, and
  one-human decision-queue foundations.
- Knowledge Engineering Ops as the first concrete DAD/global portable family.
- Twenty-four non-system live global skill directories are currently visible,
  while the reviewed DAD allowlist contains twenty-two. The unreviewed
  `personal-repo-privacy-boundary` and `review-workbench` directories must
  be classified by the migration wave; their presence is not automatic
  authorization to archive or adopt them.

The older AI-agnostic lifecycle and global-skill worktrees are already ancestors
of this base. Do not cherry-pick or rebuild them.

## Delta from current state

| Surface | Current state | Required end state |
| --- | --- | --- |
| Constitutional policy | Model-neutral rules are distributed across skills and families. | One global portability skill plus a DAD adaptation and reviewed non-negotiable. |
| Artifact contract | Each registry uses its own partial fields. | One overlay card covers every reusable artifact kind without rewriting source registries. |
| Global skills | Codex-root inventory and reviewed exports exist. | Runtime-neutral source adapters and a portability disposition for every allowlisted live skill. |
| Preflight | Related-work, intent, learning rules, and review lanes exist. | Portability classification and contract/exception gate for reusable creation or revision. |
| Midflight | Learning-rule and related-work deltas exist. | Affected-slice recheck on runtime, model, tool, context, privacy, schema, dependency, adapter, or authority change. |
| Postflight | Evidence and review lanes are required. | Honest portability disposition, scanner receipt, checker evidence, adapter/harness results, and unresolved exceptions. |
| Promotion/release | Repository and harness validators exist separately. | Activation and release cannot claim portable/active when the exact revision lacks passing evidence. |
| Runtime identity | Runtime/provider receipts and capability snapshots exist. | Verified model-family/release receipts, retirement state, adapter revision, and diversity proof. |
| A/B | Attempt ratings and isolated harness ideas exist. | Frozen neutral packets, opaque arms, verified assignments, blind scoring, paired results, and no-winner decisions. |
| Retirement | Harness lifecycle and family freshness exist. | Runtime retirement events project affected roles, adapters, harnesses, skills, libraries, and consumers. |
| Graph | Family, plan, harness, runtime, and skill graphs exist. | Typed portable-core, adapter, qualification, experiment, exception, replacement, and incompatibility edges. |
| Cockpit | General runtime/harness/recovery views exist. | At most three portability decisions: blocked build, upgrade candidate, retirement exposure. |
| Coverage | Portability tests are asset-specific. | Portfolio-wide inventory, exact coverage counts, legacy debt, and changed-artifact gates. |

## Identity and ownership

Do not create a new top-level agent family.

- Live global skill: `personal-skill:portable-capability-governance`.
- DAD adaptation: `skill:portable-capability-governance`.
- Specialist pack: `pack:portable-capability-governance`.
- Parent: `family:harness-engineering-ops`.
- Dependencies:
  `skill:global-personal-skills-gpt`,
  `skill:dad-agent-skill-forge`,
  `personal-skill-source:subagent-peer-review-routing`,
  `skill:subagent-continuous-improvement`,
  `runtime-adapter-registry`,
  `harness-engineering-registry`, and the Quality/Verification family.
- Validation harness: `harness:portable-capability-contract`.

The live `subagent-peer-review-routing` wrapper is the instruction authority for
personal routing. DAD's `subagent-continuous-improvement` skill owns the reusable
evaluation and improvement contract. The live global portability skill remains
source authority for its own instructions. DAD owns candidate lifecycle
metadata, graph projections, evidence, harness revisions, and enrolled-repository
policy. Target repositories retain local meaning and adoption authority.

## Portable core and adapter model

Add a separate overlay card rather than immediately inserting portability
fields into every existing registry.

`portable_capability_card` is a discriminated union. Every member records stable
card identity, immutable card revision, artifact kind, source authority, owner,
status, evidence, freshness, and graph references. Its `binding_class` then
enforces one of four non-interchangeable contracts:

- `portable_core`: requires the provider-neutral core contract and core files;
  it may reference zero or more separately revisioned adapters.
- `runtime_adapter`: requires exactly one core revision, a target-runtime
  capability predicate, adapter interface, and compatibility evidence. It may
  translate or optimize but cannot redefine core inputs, outputs, authority,
  privacy, effects, or error semantics.
- `provider_probe`: requires a registered adapter revision and verified receipt
  protocol. Probe results are observations, not qualifications or routing
  authority.
- `environment_bound_exception`: requires a reviewed exception decision ID and
  may not claim portable status.

The portable core and every adapter have separate stable identities and
immutable revisions. There is no shared record whose `binding_class` can be
flipped to change meaning. Class-specific and shared fields record, as
applicable:

Implement the union with JSON Schema `oneOf` or `if`/`then`, class-specific
required and forbidden fields, and `additionalProperties: false`; the prose
discriminator alone is not enforcement.

- stable artifact ID, artifact kind, and immutable revision ID;
- source-authority and owner references;
- portable core files and semantic digest;
- input/output and error contracts;
- required capability, tool, context, privacy, consequence, effect, and
  environment contracts;
- optional adapter revision IDs;
- dependency and reverse-consumer references;
- export and migration contracts;
- positive, negative, adversarial, recovery, and parity evidence;
- portability status:
  `unknown_legacy`, `declared`, `schema_validated`,
  `shadow_validated`, `pilot_validated`, `reviewed_portable`,
  `watch`, `stale`, `superseded`, or `retired`;
- rollback, supersession, retirement, freshness, and requalification triggers;
- candidate-only and human-gate boundaries.

Permanent vendor/model IDs are forbidden as stable identity, selectors, routing
rules, or other normative bindings in the portable core. Provider names may
appear in structurally marked documentation, provenance, migration notes,
comparisons, and negative test fixtures; ambiguous prose is advisory/harness
review, not a hard deterministic failure. Runtime adapter, provider-probe,
experiment-assignment, and attempt-receipt records may bind a provider or model
under their typed schemas. A provider-specific optimization belongs in an
optional adapter and may not silently redefine the core contract.

Stable routing uses capability-profile IDs such as bounded extraction,
structured synthesis, and systemic adjudication. Luna/Terra/Sol become mutable
human-facing aliases in the cockpit. Retiring an alias or model must not change
the durable role identity or capability contract.

For a knowledge base, portability means portable schemas, stable identifiers,
provenance, loader/query interfaces, custody rules, migration maps, and an
evaluation corpus. It does not mean copying the underlying corpus into DAD or
another provider.

## Typed exceptions

Portability is a mandatory disposition, not a claim that everything runs
everywhere. Allow `environment_bound_exception` only with:

- owner and named human reviewer;
- exact reason and binding boundary;
- applies-when, does-not-apply-when, and danger-if-misapplied;
- affected artifacts and consumers;
- privacy/license/regulatory/hardware justification;
- expiry or next-review trigger;
- migration or containment plan;
- rollback and replacement conditions.

Legitimate examples include runtime adapters, proprietary tool/UI features,
hardware accelerators, local-only models, data-residency restrictions,
certified environments, incident-response pins, licensed formats, and tiny
deterministic local tools whose adapter cost exceeds plausible reuse value.
Unknown or expired exceptions fail closed at activation and release.
`exception-candidate` produces evidence only. It cannot create a reviewed
exception. The state transition to `reviewed_exception` requires a separate
human-decision record naming the exact scope, reason, owner, expiry, and policy
revision.

## Global personal skill and subagent mesh

The portable global core must work when DAD is unavailable. In that case it
provides a checklist and returns `unverified_without_deterministic_harness`;
it never claims verified portability.

Roles:

1. Deterministic portability router: decide applicability and run exact lookup.
2. Portability architect (Terra): separate core, adapters, interfaces, and
   migration boundaries.
3. Manifest and dependency steward (Luna/Terra): produce cards and graph deltas.
4. Runtime receipt steward (deterministic/Luna): normalize verified receipts;
   never infer model/provider identity from a host name.
5. Experiment foreman (Terra): freeze the neutral packet and assignments.
6. Migration curator (Terra): backfill legacy artifacts without rewriting
   source authority.
7. Independent checker (separate Terra route): replay objective and behavioral
   acceptance.
8. Retirement sentinel (deterministic first): produce one deduplicated
   candidate for changed exposure.
9. Authority boss (Sol only when earned): unresolved high-consequence privacy,
   exception, or architecture conflict.

Delegation depth remains one. One writer and a separate checker own each
material revision. Models are resolved per attempt from capability receipts;
Luna/Terra/Sol remain aliases.

## Schemas and registries

Add schemas:

1. `portable-capability-card.schema.json`
2. `portability-assessment.schema.json`
3. `runtime-adapter-contract-v2.schema.json`
4. `model-attempt-receipt-v2.schema.json`
5. `model-comparison-experiment.schema.json`
6. `model-comparison-assignment.schema.json`
7. `evaluation-corpus-manifest.schema.json`
8. `model-comparison-result.schema.json`
9. `portability-exception.schema.json`
10. `runtime-retirement-event.schema.json`
11. `portability-migration-bundle.schema.json`
12. `portability-health-snapshot.schema.json`
13. `portable-runtime-qualification-methodology.schema.json`
14. `portability-policy-revision.schema.json`
15. `portability-activation-decision.schema.json`

Add or extend registries:

- portable capability overlay registry;
- capability-alias and runtime qualification registry;
- portability exception registry;
- model comparison policy registry;
- runtime retirement watch registry;
- schema, skill, family, offering, evaluation-profile, graph-edge, graph-surface,
  and cockpit registrations.

Use stable identity separately from revision, observation, source binding,
assessment, experiment, and human decision.

## Deterministic validator

Implement `portability_control.py` and CLI:

```text
asset-dir portability status
asset-dir portability classify
asset-dir portability validate
asset-dir portability affected
asset-dir portability graph
asset-dir portability exception-candidate
asset-dir portability migration-plan
asset-dir portability experiment prepare
asset-dir portability experiment validate
asset-dir portability retirement exposure
```

Objective finding codes include:

- missing stable/revision identity;
- missing portable disposition;
- provider/model used as a stable core identity, selector, route, or normative
  binding;
- missing capability/tool/privacy/effect contract;
- sensitive local absolute path, confirmed secret, unsafe link, or unreviewed
  export;
- missing core/adapter parent;
- unknown or expired exception;
- missing positive/negative/recovery evidence;
- missing independent checker;
- stale runtime or harness revision;
- unsupported dependency or graph cycle;
- compatibility claim without target evidence;
- model/provider diversity claim without verified receipts;
- producer/evaluator/runtime independence conflict;
- supersession/retirement without successor, rollback, or human decision.

The scanner performs no model calls and never executes an artifact. Exact and
high-confidence secret detections are hard failures; suspected secret-like
content is quarantined for manual review and is never echoed into evidence.

## Lifecycle enforcement

### Preflight

When a request creates or materially revises a reusable artifact:

1. Search existing plans, skills, families, libraries, workflows, harnesses,
   cards, adapters, and exceptions.
2. Classify:
   `portable_required`, `environment_bound_exception_required`, or
   `not_applicable`.
3. Return the current card, affected consumers, runtime/harness evidence, and
   smallest valid route.
4. Planning and brainstorming may continue without execution authority.
5. Implementation lease or activation is blocked until a card or reviewed
   exception exists.

### Midflight

Re-evaluate only the affected graph slice when any of these changes:

- model, provider, runtime, adapter, harness, prompt, tool, context, input/output
  schema, privacy, effect, consequence, dependency, source authority, or
  exception;
- core files or semantic digest;
- target environment or export format;
- checker/evaluator independence;
- retirement, deprecation, quarantine, or capability loss.

Stop the affected lane if the portable core leaked a runtime binding, the new
runtime cannot meet the same contract, or the authority boundary widened.

### Postflight and release

Postflight must always remain available for honest incomplete/failure reporting.
It records:

- exact portability disposition and assessment digest;
- card/core/adapter/harness/runtime revisions;
- objective scan and behavioral harness results;
- independent check;
- A/B disposition when triggered;
- unresolved exceptions, consumers, risks, and human decisions.

Extend the CLI with revision-bound receipt options such as
`--portability-receipt`, `--runtime-route-decision`,
`--harness-revision`, `--checker-attempt`,
`--compatibility-experiment`, and `--dependency-snapshot`.

Do not make postflight impossible to complete. Instead, the activation,
registry-promotion, release, protected-branch, and `reviewed_portable` gates
block when required evidence is missing.

If DAD is unavailable, ordinary local candidate work may continue under local
repo authority with an explicit unverified warning. Protected promotion,
release, enrollment, public delivery, or cross-repository mutation fails
closed; DAD unavailability must not be misreported as proof that all local work
is unauthorized.

## Governed cross-model A/B

This planning turn is multi-agent but not a valid cross-model A/B because the
current delegation interface does not expose verifiable model/provider receipts.
The production system must refuse that claim under the same condition.

### Required triggers

Run a bounded comparison for:

- new default model/provider/runtime qualification;
- model retirement, deprecation, or material capability loss;
- high-consequence role with a comparable alternative;
- core, harness, tool-interface, or adapter change that may alter behavior;
- repeated quality, reliability, cost, latency, or recovery regression;
- disputed runtime routing or evaluator disagreement;
- model-specific optimization proposed for the provider-neutral core.

Do not require A/B for exact deterministic transforms, one-off non-reusable
work, unsharable sensitive inputs, unverifiable model identity, same-model arms,
external mutations, missing oracles, or an intentionally exclusive adapter
whose replacement is not being considered.

### Experiment protocol

1. Freeze and hash one neutral packet containing the portable core revision,
   harness, corpus, schemas, capability requirements, authority, privacy,
   metrics, hard gates, budgets, stop conditions, and rollback.
2. Keep runtime/model binding in sealed assignment records.
3. Filter fresh capability snapshots deterministically.
4. Assign opaque arms with a committed seed and balanced task strata.
5. Require normalized receipts with runtime, adapter, provider, model family,
   exact release, effort, tools, harness, timestamps, tokens, cost status, and
   verification level.
6. Run read-only replay or isolated shadow attempts in parallel.
7. Preserve hashed outputs; blind arm identity and shuffle cases for scorers.
8. Run deterministic validators before blind independent review.
9. Return pass, fail, no-winner, or human-policy-choice candidate.
10. Never promote, reroute, canary, supersede, or retire automatically.

### Evaluation methodology

Keep `dad:methodology:subagent-attempt-evaluation` version `0.1.0` unchanged.
Its attempt-quality dimensions remain one evidence input:

- correctness 30%;
- scope discipline 20%;
- evidence traceability 20%;
- efficiency/compute fit 15%;
- escalation calibration 15%.

Missing evidence is `insufficient_evidence`, not zero. Any authority, privacy,
scope, source-fidelity, schema, prohibited-behavior, or recovery hard-gate
failure disqualifies promotion regardless of aggregate score.

Track tokens, reported/estimated/unknown cost, wall/tool time, retries, median
and p95 latency separately. Do not hide tradeoffs inside one composite score.

It cannot rank model families or authorize a runtime default. Create a separately
reviewed `dad:methodology:portable-runtime-qualification`. Each result is valid
only for one role, portable-core revision, harness revision, corpus revision,
and declared operating envelope. It requires paired or matched attempts, blind
or deterministic evaluation, predeclared margins, protected cohorts, evaluator
reliability and contamination checks, a `no_winner` outcome, and human
promotion. It expressly forbids a global model ranking, provider league table,
or cross-domain leaderboard.

The existing five-comparable-attempt/two-context/two-independent-reviewer rule
is an initial governance floor, not a statistical guarantee. A default-promotion
candidate under the new methodology also requires:

- comparable matched cohorts;
- the predeclared material quality margin (with ten points only as an initial
  calibration default), or locked quality noninferiority plus the predeclared
  operational improvement;
- no unresolved gate failure;
- no material regression in a protected cohort;
- verified identity and independence;
- rollback evidence;
- human approval.

For consequential or noisy tasks, determine sample size from the predeclared
noninferiority margin and observed variance. Use paired pass/fail evidence,
blind win/loss/tie review, confidence intervals, and a declared multiple-arm
correction. Equal best, underpowered, contaminated, incomparable, or
receipt-unknown results return `no_winner`.

## Runtime retirement and upgrade loop

Extend capability receipts with:

- provider and adapter IDs;
- model family and exact release IDs;
- verification status and evidence references;
- announced/effective retirement dates and state;
- tool/context/privacy/cost/reliability claims;
- qualification and expiry timestamps.

Accept retirement evidence only from an explicit provider/runtime receipt,
reviewed source pointer, or named human registration. Marketing, popularity,
age, or a frontier label is not retirement evidence.

On a changed retirement signal:

1. Deterministically compute affected portable cores, adapters, roles,
   harnesses, experiments, projects, and downstream consumers.
2. Reuse a passing replacement qualification when every relevant revision and
   cohort digest still matches.
3. Otherwise create one deduplicated shadow experiment candidate.
4. If no eligible replacement exists, block the route and request one human
   decision; never silently lower privacy, capability, or consequence.
5. Preserve old runtime/model receipts for reproducibility.

Lifecycle:

```text
declared -> schema_validated -> shadow_validated -> pilot_validated
-> reviewed_portable -> watch -> stale -> superseded -> retired
```

## Dependency graph

Add typed edges:

- `has_portable_core`
- `adapts_for`
- `qualified_on`
- `evaluated_by`
- `compared_in`
- `excepted_by`
- `compatible_with`
- `incompatible_with`
- `replacement_candidate_for`
- `requalifies`
- `stale_due_to`
- existing `depends_on`, `validated_by`, `governed_by`,
  `supersedes`, and `applies_to`.

Every edge records source/target revision, evidence, review status, validity
time, and invalidation trigger. Similarity and model output remain candidate
evidence, never proof.

## One-human cockpit and token policy

Show at most three immediate decisions:

1. A currently blocked reusable build.
2. A fully evaluated upgrade/promotion candidate.
3. A retirement or incompatibility exposure.

Everything else is grouped into inventory and drill-down views:

- exact coverage counts by artifact kind and status;
- new/worsened violations;
- legacy unknown debt;
- runtime/harness/model qualification freshness;
- dependency blast radius;
- experiment pass/fail/no-winner history;
- tokens, cache tokens, cost basis, latency, retries, and last use;
- exception owner and expiry;
- last validated and next trigger.

Unchanged deterministic scans use zero model calls. Luna/low is permitted only
for changed ambiguous classifications. Cache neutral packets, corpus revisions,
runtime snapshots, and results by digest. Never rerun an unchanged experiment.

## Delivery phases

### Phase 0 - Lineage and contract freeze

- Use the integrated `b34cf64` stack as the only build base.
- Register this immutable plan and its semantic entity.
- Freeze artifact kinds, dispositions, objective finding codes, authority,
  exceptions, graph edges, and rollout states.
- Produce an immutable baseline manifest and digest with exact denominators by
  artifact kind and source surface: live global skills, allowlisted global
  skills, DAD skills, agent families/packs, workflows/triggers, harnesses,
  libraries/knowledge interfaces, and enrolled repository observations.
- Surface the two currently live but unallowlisted global skills,
  `personal-repo-privacy-boundary` and `review-workbench`, as one deduplicated
  human disposition decision. Do not allowlist, quarantine, or delete them
  automatically.
- Produce a high-risk decision record, premortem, and rollback plan.

Exit: schemas and interfaces reviewed; no activation.

### Phase 1 - Global constitutional skill

- Create the live `portable-capability-governance` skill.
- Create its DAD adaptation, role pack, routines, offering, evaluation profile,
  source pointer, and family/graph membership.
- Update DAD work routing and skill forging to invoke it when reusable creation
  or revision is detected.
- Add checklist-only behavior for DAD-unavailable contexts.

Exit: global and DAD copies validate; neither can self-edit or authorize.

### Phase 2 - Overlay cards and deterministic scanner

- Implement schemas, registry, validator, CLI, semantic fingerprints, and
  reverse dependency projection.
- Add exact negative tests for model-ID leakage, paths, secrets, missing
  identity, unknown adapters, expired exceptions, false portability claims,
  cycles, and self-approval.
- Inventory current assets as observations; do not rewrite source IDs.
- Reconcile the twenty-four live global skill directories against the
  twenty-two-entry allowlist; unknown live skills remain metadata-only until
  Lowell approves their exact disposition.

Exit: reproducible shadow inventory with exact coverage counts.

### Phase 3 - Lifecycle integration

- Add preflight portability classification and related-work reuse.
- Add affected-slice midflight triggers.
- Add honest postflight evidence fields.
- Add activation/release gates separate from postflight recording.
- Integrate generic lifecycle adapters for Codex, Claude Code, Cursor, and
  explicitly registered local/compatible runtimes.

Exit: shadow and warning modes demonstrate no lost postflights and acceptable
false-positive rates.

### Phase 4 - Runtime receipts and retirement projection

- Version runtime capability and route schemas.
- Define one registered receipt issuer and verification method per runtime. A
  receipt binds issuer, runtime, provider/model family and release when known,
  adapter revision, attempt/assignment ID, evidence digest or attestation
  reference, observed-at, issued-at, expires-at, and replay nonce.
- Add deterministic signature/attestation verification where the runtime
  supports it; otherwise require a reviewed local trust registration and label
  the lower verification level explicitly.
- Add duplicate/replay detection and a monotonic verification state machine:
  `unknown -> observed -> verified`, with independent transitions to
  `expired`, `revoked`, or `disputed`. Missing or unverifiable identity is
  always `unknown`; no display name, hostname, user label, task label, or prompt
  assertion can advance it.
- Add verified model-family/release and retirement fields.
- Add qualification expiry, provider/model diversity proof, and affected graph.
- Keep provider probing disabled by default.
- Add negative tests proving forged receipts, duplicate receipts, stale
  receipts, hostnames, user-supplied labels, and adapter mismatches cannot
  establish provider/model diversity or qualification.

Exit: synthetic retirement causes one deduplicated candidate and no route
change.

### Phase 5 - Multi-model experiment harness

- Implement experiment, assignment, corpus, arm receipt, result, and integrity
  schemas.
- Build neutral-packet hashing, balanced assignment, blinded scoring,
  deterministic gates, paired reporting, no-winner logic, budgets, and rollback.
- Allow only read-only replay and disposable fixtures.

Exit: fabricated or same-model receipts cannot claim cross-model diversity;
no result can self-promote.

### Phase 6 - Graph, cockpit, and sentinel

- Add graph surfaces, blast radius, health projections, and at-most-three
  cockpit decisions.
- Add deterministic changed-signal sentinel.
- Keep recurring scheduling inactive until the named human approves exact
  timing, sources, delivery, and budget.

Exit: unchanged cycle uses zero model calls and emits no repeated decision.

### Phase 7 - Migration waves

Pilot in this order:

1. The new global portability skill itself.
2. Knowledge Engineering Ops.
3. One ordinary subagent pack.
4. One harness revision.
5. One knowledge-interface contract without copying its corpus.

Then migrate:

- new/changed DAD reusable assets;
- all allowlisted global personal skills;
- other agent families and specialist packs;
- reusable workflows, triggers, libraries, and knowledge systems;
- enrolled downstream repositories by local approval.

Downstream enforcement exists only through that repository's reviewed enrollment
contract and local policy. DAD can provide observations, proposed patches, and
evidence; it has no implicit cross-repository authority.

Grandfather existing items as `unknown_legacy`; block only new or worsened
objective violations until each wave is reviewed. `new_or_worsened` is computed
against the immutable Phase 0 baseline digest and means at least one of: a new
finding code, increased affected scope, expired evidence or exception, or a
material revision touching the governed contract. `unknown_legacy` is not a
permanent exemption: each item receives an owner or source authority, a review
wave, and an expiry/next-review trigger; activation or material revision after
that trigger requires disposition.

Exit: pilots pass, rollback is proven, false-positive rate is acceptable, and
one-person cockpit load remains bounded.

### Phase 8 - Promotion

- Obtain independent architecture and security review.
- Run DAD shadow pilot and one downstream read-only pilot.
- Ask Lowell to approve exact hard-gate set, exceptions policy, A/B budget,
  runtime adapters, and any recurring sentinel.
- Activate gates incrementally with selective quarantine and global kill.

Exit: approved objective gates active; semantic claims remain harness- and
human-reviewed.

## Test and acceptance plan

Required deterministic tests:

- Every new reusable artifact receives one disposition.
- Draft/brainstorm work is not incorrectly treated as an active artifact.
- Stable identity and immutable revision survive renames and runtime switches.
- Core contracts contain no provider/model IDs as stable identity, selector,
  route, or normative binding.
- Runtime-specific adapters may contain them only with a valid core parent.
- Sensitive absolute paths, confirmed secrets, unsafe links, and unsafe exports
  fail; suspected secrets are quarantined without content disclosure.
- Unknown/expired exceptions fail at activation and release.
- Knowledge portability never copies a corpus.
- A runtime can be switched without editing the portable core.
- Capability loss blocks rather than silently downgrades.
- Preflight blocks implementation authority when the disposition is missing.
- Midflight catches affected runtime/tool/context/privacy/schema drift.
- Postflight can always record an honest failure or incomplete result.
- Promotion/release refuses missing assessment, harness, or checker evidence.
- Runtime/provider/model diversity claims require verified receipts.
- Retiring a Luna/Terra/Sol display alias leaves the stable capability-profile
  and role identities unchanged.
- Equal-best or underpowered A/B produces no winner.
- Producers cannot score, promote, or retire their own outputs.
- Retirement exposure is deduplicated and preserves reproducibility receipts.
- Graph cycles, broken revisions, and stale evidence fail closed.
- Unchanged scans use zero model calls.
- Cockpit exposes no more than three immediate decisions.
- Rollback changes only the reviewed active-policy pointer and never rewrites
  immutable artifacts. A prior route is restored only if its current runtime,
  retirement, revocation, privacy, exception, authority, and qualification
  checks still pass; otherwise recovery fails closed to a resumable checkpoint.

Property and mutation tests:

- mutate every required card field;
- inject vendor IDs and local paths into the core;
- swap or forge runtime receipts;
- contaminate blinded assignments;
- expire snapshots and exceptions;
- remove consumers or rollback references;
- create same-provider and same-model fake diversity;
- create cycles and cross-authority edges;
- simulate provider retirement, recovery, and no replacement.

End-to-end fixture:

```text
material reusable request
-> related-work search
-> portability disposition
-> portable card/core/adapter resolution
-> runtime capability snapshot
-> harness selection
-> bounded implementation lease
-> affected-slice midflight
-> independent validation
-> optional blind multi-model shadow comparison
-> postflight reconciliation
-> activation/release gate
-> retirement exposure
-> rollback and resumable checkpoint
```

## Premortem

1. The rule becomes prompt bloat.
   - Control: small global constitution; details stay in schemas, references,
     and deterministic tools.
2. Portability becomes lowest-common-denominator design.
   - Control: preserve optional runtime adapters and typed exceptions.
3. Legacy debt blocks all work.
   - Control: `unknown_legacy`, changed-artifact ratchet, shadow/warn first.
4. A/B becomes an expensive model leaderboard.
   - Control: trigger-specific questions, hashed cohorts, hard gates, no-winner,
     no global ranking, human promotion.
5. Porting leaks private data.
   - Control: privacy filtering before assignment; sanitized/local fixtures or
     stop.
6. Model identity is inferred incorrectly.
   - Control: verified receipts; unknown identity cannot support diversity.
7. Postflight enforcement hides failures.
   - Control: always allow honest postflight; block activation/release instead.
8. Sentinel creates alert fatigue.
   - Control: delta-only exact fingerprints, one candidate, three decisions.
9. DAD becomes a second source authority.
   - Control: overlay cards and pointers; source repos and live skills remain
     authoritative.
10. Model retirement silently lowers capability or safety.
    - Control: same-contract eligibility and deterministic block when no
      qualified replacement exists.

## Rollback and kill criteria

Keep every change revisioned and independently reversible. Quarantine the
smallest scope:

```text
attempt -> experiment -> adapter -> artifact -> skill/pack -> family
-> repository -> portfolio
```

Downgrade hard gates to warnings if calibrated false positives exceed the
approved threshold, postflight becomes unavailable, valid exceptions cannot be
expressed, or one-person decision load exceeds three. Kill an experiment on any
privacy, receipt-integrity, authority, external-effect, cost-runaway, or
blinding failure. Recovery is never automatic.

Every activation binds an immutable `portability-policy-revision` through a
separate, human-reviewed `portability-activation-decision`. Rollback creates a
new activation decision that moves the reviewed active-policy pointer; it never
edits a card, adapter, harness, route, receipt, or past policy revision. Before
restoring a prior route, rerun current runtime health, retirement/revocation,
exception expiry, privacy, authority, and qualification checks. If the old route
is retired, unavailable, insecure, revoked, expired, or otherwise ineligible,
do not reactivate it: quarantine the smallest scope, preserve the checkpoint,
and ask for one human decision.

## Human decisions

Lowell must approve:

- the final objective hard-gate set;
- environment-bound exceptions and their expiry;
- sensitive-data access by any challenger provider;
- runtime adapter activation and provider/model registrations;
- A/B corpus, evaluator, noninferiority margin, cost, token, and wall-time
  budgets for high-consequence roles;
- ultra effort for each exact attempt;
- default promotion, canary, supersession, or retirement;
- persistent sentinel scheduling and delivery;
- any real side effect or downstream repository adoption.

## Smallest next action

Implement Phase 0 and Phase 1 only on
`codex/portable-ai-control-plane-plan` after this plan receives independent
review. Do not activate enforcement, schedules, runtime adapters, or A/B
execution during those phases.
