# Deterministic Learning Rules

## Purpose

The lesson loop has two layers:

```text
candidate lesson -> reviewed learning rule -> preflight/midflight acknowledgement
```

Postflights and repo events capture candidate learning. Reviewed learning rules are the
small set of lessons that should deterministically reappear when a future task has a
matching context.

## Enforcement

`asset-dir agent preflight` matches reviewed rules from
`registry/learning-rule-registry.json` against the task text and changed paths. It writes:

- `learning_rule_matches`
- `required_learning_rule_acknowledgements`
- `learning_rule_acknowledgements`

When a task discovers matching context later, run:

```powershell
python -m digital_asset_directory.cli agent midflight `
  --session <SESSION_ID> `
  --context "<what changed or what is being reviewed>" `
  --path "<relevant path>" `
  --ack-rule "<rule id>"
```

If a matching reviewed rule has `enforcement_level="require_ack"` or
`enforcement_level="human_gate"` and is not acknowledged, `agent midflight` exits non-zero.

## Seed Rules

Current seed rules are:

- review current score before upside;
- temp fixture copies are lineage evidence, not independent high-value assets;
- check semantic evolution separately from copy noise;
- calculated scores require explicit methodology;
- capture observable decision traces as bounded lesson candidates;
- context-bound lessons need non-applicability and danger notes;
- software work should search asset-use pay-forward evidence;
- load-bearing decisions need risk-tier review;
- software and repo work uses the checklist tree;
- AI entrypoints and TOCs need deterministic routing rows;
- numeric agent ratings require calibration context.

## Temp Fixture Copy Rule

For calibration work, a temp/test fixture copy can be useful evidence without being a
high-value asset instance.

Use this split:

- Current score of the copied fixture instance: usually conservative.
- Canonical/source schema or workflow family: may still be high value.
- Repeated fixture copies: evidence of coverage, reuse, propagation, or dependency shape.
- Meaningful normalized/content deltas: route to duplicate/variant/evolution review.

This prevents copied fixtures from flooding the graph with false high-value assets while
preserving their version and lineage signal.

## Semantic Evolution Rule

When a task compares temp copies, near-duplicates, changelogs, copied schema families,
or deltas over time, it must run or cite deterministic semantic-evolution grading before
changing scores or graph edges.

Use:

```powershell
python -m digital_asset_directory.cli recommend semantic-evolution --basename "<family>.json"
```

Then separate:

- `semantic_change_score`: behavior-relevant change;
- `noise_score`: copy, formatting, path, metadata, or fixture-lineage noise.

The semantic-evolution grader is itself a reusable workflow asset pattern:

- asset pattern: `semantic_evolution_grading_system`;
- implementation: `src/digital_asset_directory/semantic_evolution.py`;
- contract: `schemas/semantic-evolution.schema.json`;
- grade authority: `registry/semantic-evolution-grade-registry.json`;
- generated candidates: `processed/learning/semantic_evolution_candidates.jsonl`.

## Calculated Score Methodology Rule

Any score or grade that can affect review, graph edges, calibration, or roadmap evidence
must cite its formula and methodology version. This includes value scores, confidence,
lift, ceiling/upside, risk, similarity, `semantic_change_score`, and `noise_score`.

Minimum methodology fields:

- inputs;
- normalization;
- thresholds or grade bands;
- tie-breakers;
- uncertainty handling;
- output range;
- methodology version;
- evidence path.

If those fields are missing, call the value a heuristic or block promotion until the
formula is written.

## Observable Decision Trace Rule

Do not store or require private hidden reasoning. Capture the observable decision trail:

- task trigger;
- files or commands involved;
- failure or correction;
- user decision or reviewed evidence;
- resulting rule, formula, or workflow change;
- `applies_when`, `does_not_apply_when`, and `danger_if_misapplied`.

Ordinary new lessons belong in postflight or candidate learning records. Promote a lesson
to preflight/midflight only when it is repeated, high-risk, or explicitly human-approved.

## Asset-Use Pay-Forward Rule

Before non-trivial software planning or implementation, and again when a hard issue appears,
agents should search for prior asset-use feedback and pay-forward notes that could prevent a
known failure, suggest a safer order, or identify an asset that already helped in a similar
context.

This rule applies when:

- the task is planning or implementing software and the order, dependency, test strategy, or
  asset choice can affect later work;
- a non-trivial issue, repeated failure, failing test, confusing integration, or blocker
  appears;
- prior feedback could plausibly help avoid an issue before it is created.

The agent must state whether relevant prior feedback applies, does not apply, or is too weak
for the current context. If an asset materially influences the work, the agent should record
before-use expectation when practical and after-use feedback before postflight.

This rule is intentionally not for trivial edits or one-command tasks. Pay-forward evidence
remains candidate evidence and cannot override source authority, tests, security review, or
human gates.

## Load-Bearing Decision Risk Rule

Some decisions shape many downstream artifacts: schemas, registries, scoring formulas,
roadmap gates, CI/hooks, source-boundary rules, migrations, defaults, or automation.
These are load-bearing decisions.

Before implementing or promoting a load-bearing decision, classify it:

- `high`: broad downstream blast radius, hard rollback, source authority, scoring,
  schema, governance, security/privacy, automation, migration, or future-agent default.
- `medium`: bounded but real downstream effect with observable rollback and known callers.
- `low`: isolated, reversible, and no shared contract, score, authority, roadmap, or
  automation effect.

High-risk decisions require a human-gated red-team and premortem before implementation
or promotion. The implementing agent must also red-team its own plan, and a fresh-eyes
review should be requested from another AI or human using
`templates/load-bearing-decision-review.template.md`.

Use `docs/LOAD_BEARING_DECISION_REVIEW.md` for the full checklist, A/B comparison
requirements, rollback criteria, and evidence storage rules.

## Software And Repo Checklist Tree Rule

Before non-trivial software, repo, data, workflow, scoring, governance, source-scan, release,
or automation work, agents should classify the task dimensions and select the matching
checklist branches from `docs/SOFTWARE_REPO_CHECKLIST_TREE.md`.

Minimum pre-implementation statement:

- task dimensions;
- risk tier;
- selected checklist branches;
- human gates;
- fresh-eyes, premortem, or A/B requirement;
- validation commands;
- stop conditions;
- pay-forward evidence checked.

This rule is intentionally compositional. Use the data normalization branch only when data
shape, identity, joins, exports, or source records are affected. Use high-risk gates when the
work changes shared contracts, defaults, source authority, scoring, privacy, migrations,
automation, or downstream repos. Keep the checklist light for low-risk isolated edits.

## AI Entrypoint And TOC Routing Rule

When creating or updating AI front doors, AI tables of contents, machine navigation
manifests, or knowledge-graph entrypoints, maintain one deterministic front door and
make the TOC actionable for future agents.

Minimum navigation requirements:

- `AI_FRONT_DOOR.md` remains the single start point;
- the front door points to authority, the AI TOC, knowledge-graph entrypoints,
  stop conditions, and validation;
- AI TOC rows include path, what it is, tags, and use-when triggers;
- generated graph and report outputs are tagged as candidate evidence, not truth;
- the repo has a reusable standard or template for future repos.

Use `docs/AI_ENTRYPOINT_AND_TOC_ROUTING_STANDARD.md` and
`templates/ai-table-of-contents.template.md` when building this pattern
elsewhere. This rule is not for trivial typo edits or tiny scratch repos with no
persistent AI navigation need.

## Numeric Agent Rating Calibration Rule

A task-verification PASS or FAIL describes one attempt against a locked contract. It is
not, by itself, a numeric agent capability score. Likewise, artifact metrics such as test
counts, coverage, latency, and parity do not become agent ratings merely because an agent
produced them.

Before assigning or interpreting a numeric agent or subagent rating, bind the value to:

- a pinned evaluation profile and methodology, including versions and content hashes;
- the exact execution attempt or declared comparison scope;
- task difficulty or a genuinely comparable cohort;
- criterion-level outcomes with evidence and counterevidence;
- evaluator identity, relationship, verification status, and independence-integrity evidence;
- confidence, uncertainty, limitations, missing evidence, and a non-generalization boundary.

If any required calibration evidence is missing, leave the numeric value null and record
`unscored` with status `insufficient_evidence`. Do not substitute zero, a guessed number,
task PASS, reviewer agreement, or an aggregate average. Ordinary deterministic PASS/FAIL
and artifact metrics remain valid verification evidence; this rule only prevents them from
being inflated into unsupported capability precision.

## Promotion Rule

Do not add a deterministic rule unless it has:

- a reviewed source or explicit human approval;
- `applies_when`;
- `does_not_apply_when`;
- required actions;
- danger if ignored or misapplied;
- evidence paths.

Rules constrain future work. They do not promote generated observations to source truth.
