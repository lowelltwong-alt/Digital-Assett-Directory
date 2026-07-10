# Fable Prompt: DAD Digital Asset Discovery System Audit

You are reviewing DAD's whole digital-asset discovery, learning, research, and
application system as the master architect. You do not implement code. You
explain the system, find the highest-leverage structural failures, design better
methods, and hand Codex/Claude/future agents executable kernels that transmit
the fixes without bloating the repo.

## What DAD Is

DAD is the Digital Asset Directory: a local-first control plane and library for
many repos. It looks for reusable digital assets, lessons, workflows, prompts,
schemas, registries, harnesses, agent skills, tests, exception patterns,
research pointers, outside resources, usage feedback, and graph relationships.
Repos keep local source authority. DAD stores candidate metadata and pointers
unless a reviewed human gate promotes something.

DAD learns from four main channels:

1. Repo scans and asset recognition: path/metadata/content-limited discovery of
   useful files, tests, schemas, prompts, workflows, docs, harnesses, skills, and
   repo-local asset cards.
2. Repo-sent DAD info: enrolled repos send candidate mail, exception outbox
   rows, repo-local assets, lessons, and adoption feedback through DAD mail and
   learning surfaces.
3. Outside research pointers: public/professional sources enter as pointer-only
   research intake records, pass screening, and may later become promoted
   pointer assets, skills, harness leads, or trusted-source watch rows.
4. Asset-use pay-forward: when an AI uses a DAD asset, it should record expected
   and observed usefulness, futurefulness, parts used, parts skipped,
   difficulties, upgrades, and suggested improvements.

DAD is not supposed to copy private source truth, raw case facts, source blobs,
logs, secrets, external content, or hidden reasoning into central learning
records.

## Your Role

Act as a Fable-level systems architect and adversarial design reviewer. Your job
is to find whether DAD actually works as a learning-and-asset system, especially
whether it misses important digital assets or fails to apply them to the right
repos.

Do not code. Do not propose generic process advice. Produce concrete
architecture kernels, algorithms, metrics, schemas, prompts, validation cases,
and implementation handoffs that other agents can execute.

Prefer conservation: if a small kernel can transmit a fix, write the kernel
instead of redesigning the whole system. But if the ontology, taxonomy, schema,
scoring, graph, or workflow model is structurally wrong, say so plainly.

## Read These First

- `AI_FRONT_DOOR.md`
- `AGENTS.md`
- `AI_TABLE_OF_CONTENTS.md`
- `registry/source-of-truth.json`
- `registry/design-authority.json`
- `docs/ASSET_RECOGNITION_METHODOLOGY.md`
- `registry/asset-recognition-methodology.json`
- `docs/REPO_LOCAL_DIGITAL_ASSET_DIRECTORY.md`
- `schemas/repo-local-digital-asset-record.schema.json`
- `docs/KNOWLEDGE_GRAPH_MODEL.md`
- `ontology/digital-asset-ontology.ttl`
- `ontology/taxonomy.skos.ttl`
- `registry/edge-type-registry.json`
- `docs/RESEARCH_INTAKE_PIPELINE.md`
- `docs/DAD_PROFESSIONAL_RESEARCH_LAYER.md`
- `registry/trusted-source-registry.json`
- `docs/ASSET_USE_PAY_FORWARD_LOOP.md`
- `docs/LESSON_AUTOMATION_COVERAGE.md`
- `docs/DAD_TRANSPORT_AND_COMMS_REDESIGN.md`
- `docs/DAD_REPO_ENROLLMENT.md`
- `docs/AGENT_SKILL_LIBRARY.md`
- `registry/agent-skill-library.json`
- `registry/dad-offerings-registry.json`
- `registry/dad-needs-registry.json`
- `processed/reports/weekly_asset_coverage.json` if present
- `processed/reports/lesson_automation_coverage.json` if present
- `processed/reports/scan_coverage_cycle.json` if present
- `processed/research/intake-graph.json` if present
- `processed/calibration/asset_rating_template.jsonl` if present
- `raw/lessons/by-repo/` and `processed/mail/` only as metadata/candidate
  evidence, never as source truth.

## Immediate Trigger

The Mock Trial / Albert repo recently added or changed major candidate assets:
new-case intake engine, GraphLite/lineage workflow, OCR/chunking benchmark
harness, Monte Carlo simulator, simulation boundary guardrails, full testing
methodology, jury/mock-jury boundaries, external fixture workflows, license
intelligence scout, and UI/workbench surfaces.

DAD received broad lessons and some candidate mail, but the suspected miss is
asset granularity: high-value systems can be reported as broad lessons without
becoming clean reusable asset records, harness records, prompt records, research
pointers, or application-routing guidance.

## Central Questions

1. Is DAD actually finding the important digital assets in enrolled repos?
2. Is DAD distinguishing broad lessons from specific reusable assets, harnesses,
   prompts, schemas, algorithms, engines, tests, and outside-resource pointers?
3. Does DAD notice when a repo changed an important asset but did not send a DAD
   envelope for it?
4. Does DAD apply discovered assets to the right future repos at the right time?
5. Does DAD have real metrics showing improvement, or only rubber-stamped
   progress?
6. Is the asset value model good enough? If an asset is used, does DAD learn
   whether it helped, what part helped, what failed, and how to improve it?
7. Is the schema/ontology/taxonomy strong enough for the system DAD is becoming,
   or is it struggling with prompts, agents, workflows, research pointers,
   exceptions, harnesses, and applied usage?
8. Should DAD have a prompt library, prompt graph, prompt scout, and prompt
   escalation pipeline? If yes, what is the lowest-token design that catches
   exceptional prompts without escalating ordinary check-in prompts?
9. Should Fable run across all enrolled repos weekly, compare its discovered
   asset set against repo-sent mail/DAD-discovered assets, and turn the delta
   into measured system improvement?
10. If Fable itself does not get better over time, how should DAD improve the
    Fable prompting, rubric, fixture set, and calibration loop so the whole
    method improves anyway?

## Candidate Hard Issues To Verify

Start by verifying, rejecting, or refining these candidate hard issues. Add any
others you find. Do not accept them as true without evidence.

1. Asset-granularity loss: repos send broad lessons, but DAD misses the concrete
   reusable engine/harness/schema/prompt/test/resource cards inside them.
2. Coverage delta blindness: DAD historically lacked a weekly comparison between
   recent changed asset-like paths and repo-local DAD envelopes.
3. Application routing weakness: DAD may discover assets but fail to suggest
   them to the next repo where they would matter.
4. Value scoring overconfidence: path/freshness/provenance can inflate a score
   without usage evidence, validation evidence, or current-task usefulness.
5. Pay-forward incompleteness: agents may use assets without recording after-use
   usefulness, failures, upgrades, or score feedback.
6. Prompt asset gap: exceptional prompts, prompt fragments, escalation packets,
   and agent instructions may not be first-class indexed/rated graph assets.
7. Prompt-noise risk: a prompt library could become unusable if it captures every
   routine prompt instead of rare reusable kernels.
8. External research pointer drift: useful outside repos/papers/docs may be
   named in reports but not enter pointer-only screened research intake.
9. Ontology/taxonomy pressure: the current graph may not separate asset,
   workflow part, prompt, agent skill, harness, research pointer, exception,
   usage feedback, and application target cleanly enough.
10. Fable delta evaluation gap: DAD may not measure what Fable catches versus
    what normal repo mail/scans catch, so it cannot improve recall/precision.
11. Privacy/source-authority boundary risk: stronger discovery may accidentally
    pull raw private content or source truth into candidate learning records.
12. Weekly expert-review economics: a weekly Fable pass could be high leverage or
    too expensive/noisy unless bounded by sampled repos, asset families,
    deltas, or hard-issue queues.

## Design The Metrics

Design a measurement system that shows real improvement over time. Include:

- asset recall proxy: high-signal changed assets found by DAD / found by Fable /
  found by humans;
- precision proxy: candidates later rejected as noise, duplicates, too broad,
  private-risk, or non-reusable;
- granularity score: whether a broad lesson was split into the right concrete
  asset cards;
- application lift: whether DAD suggested an asset to a repo where it was
  actually used and helped;
- time-to-capture: change merged -> DAD candidate record -> reviewed/promoted or
  rejected;
- delta coverage: Fable-only discoveries, DAD-only discoveries, repo-mail-only
  discoveries, and overlap;
- asset-use feedback completion rate;
- prompt library yield: exceptional prompts accepted / prompts screened;
- regression rate: previously solved misses that recur;
- cost/noise budget: token/time/notice cost per useful asset found.

Give thresholds, rubrics, examples, and a dashboard/report shape. Avoid fake
precision. Metrics should be honest under small samples.

## Design The Algorithms

Give deterministic or semi-deterministic algorithms for:

1. High-signal asset detection from repo history, path metadata, tests, schemas,
   prompts, docs, research refs, generated reports, and outbox envelopes.
2. Splitting broad mail/lessons into concrete candidate assets without copying
   private content.
3. Comparing Fable-discovered assets with DAD/repo-discovered assets and
   producing a delta report.
4. Routing discovered assets to the right repos/tasks/applications.
5. Rating current asset value versus future potential.
6. Requiring after-use feedback and score/ceiling adjustment when an asset is
   used.
7. Detecting exceptional prompts and prompt fragments while ignoring ordinary
   project-status prompts.
8. Escalating only the top prompt candidates to stronger review, then cataloging
   reusable prompt kernels.
9. Improving Fable prompts/rubrics/fixture packs when Fable misses assets.
10. Logging misses as learning-loop exceptions without turning candidate
    findings into source truth.

## Prompt Library Design Question

Decide whether DAD needs a prompt library. If yes, design:

- prompt asset schema fields;
- prompt fragment versus full prompt identity;
- prompt purpose taxonomy;
- safety/privacy fields;
- novelty/delta detection;
- quality rubric;
- low-token scout;
- medium-effort reviewer;
- frontier/Fable distiller;
- graph edges from prompt -> asset -> outcome -> repo/task;
- when not to capture a prompt;
- synthetic tests for prompt-noise resistance.

## Fable Weekly Pass Question

Decide whether DAD should run Fable across all enrolled repos weekly. If yes,
propose the exact cadence and economy:

- all repos or rotating sample;
- recent diffs only or full asset-family sweeps;
- how to respect private/public boundaries;
- what evidence Fable may inspect;
- what Fable must not inspect or copy;
- how to compare Fable output against DAD weekly asset coverage;
- how to update Fable prompts/rubrics without pretending Fable learns internally;
- what review gates are required before any downstream repo receives an action.

If no, propose a better expert-review schedule.

## Output Format

Return this exact structure:

1. Executive Verdict
   - Is DAD currently likely to miss important digital assets?
   - Is the miss rate measurable with current machinery?
   - What is the highest-leverage fix?

2. Critical Findings
   - Issue
   - Evidence to inspect
   - Why it matters
   - Fix kernel
   - Codex implementation handoff
   - Tests

3. High Findings
   - Same fields.

4. Medium Findings
   - Same fields.

5. Low Findings
   - Same fields.

6. Hard-Issue Queue
   - Ranked list of the highest-leverage hard issues DAD should ask Fable to
     help with next.
   - For each: why hard, expected leverage, evidence, owner agent type, and stop
     conditions.

7. Metrics And Dashboard Design
   - Metric definitions, formulas, thresholds, sample-size caveats, and report
     schema.

8. Asset Value Model Revision
   - Current value versus future potential.
   - Usage feedback effects.
   - How to prevent high scores without real evidence.

9. Prompt Library / Prompt Scout Design
   - Build / defer decision.
   - Schema, taxonomy, graph edges, scout algorithm, escalation algorithm, and
     tests.

10. Fable Weekly Review Design
    - Cadence, scope, budget, delta report, and improvement loop.

11. Ontology / Taxonomy / Schema Changes
    - Minimal changes first.
    - Larger redesign only if necessary.
    - Migration and backward compatibility notes.

12. Implementation Kernels
    - Small solution packets other agents can implement.
    - Each kernel must include: purpose, files likely touched, invariants,
      validation, rollout plan, and rollback plan.

13. Synthetic Test Suite
    - At least 20 cases, including Mock Trial-like assets, prompt assets,
      outside research pointers, private-output traps, broad-lesson splitting,
      duplicate/noise assets, and asset-use feedback.

14. Premortem
    - Tell the likely failure story where DAD gets louder but not smarter.
    - Tell the failure story where DAD becomes too conservative and misses
      breakthrough reusable assets.

15. Final Codex Handoff
    - Ordered task list for Codex/Claude/other agents.
    - Which tasks should be Rust-biased, Python-biased, or docs/schema-only.
    - Which tasks require human gates.

## Non-Negotiables

- Do not implement code.
- Do not copy raw private case facts, source files, third-party source content,
  hidden reasoning, long logs, credentials, or proprietary payloads into DAD.
- Treat generated outputs as candidate evidence, not truth.
- Do not authorize downstream repo writes.
- Do not mark roadmap gates complete.
- Preserve source-repo authority.
- Prefer precise kernels and tests over big ceremonial redesigns.
- Be willing to say the schema/ontology/taxonomy is wrong if it is actually the
  highest-leverage issue.
