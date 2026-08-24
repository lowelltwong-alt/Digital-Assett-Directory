# Research Benchmark and Design Principles

Research cutoff: 2026-08-20  
Evidence policy: primary or official sources only  
Status: design input, not execution authority

## Why this file exists

The audit showed that DAD already performs substantial work, but activity,
catalog size, graph density, and journal volume do not establish user value.
This benchmark translates current AI engineering and architecture practice into
specific DAD decisions. It is deliberately selective: a practice is included
only when it changes a campaign gate, implementation boundary, or value test.

## Evidence-to-decision matrix

| Current practice | Primary evidence | What it means for DAD | Campaign decision |
|---|---|---|---|
| Evaluate outcomes, not just agent claims or traces. Use realistic tasks and a mix of deterministic, model, and human graders. | [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) distinguishes transcripts from final environment state, recommends grader combinations, failure-derived tasks, and human calibration. [OpenAI evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices) recommends task-specific, real-distribution evals, early/continuous evaluation, and human calibration. | DAD cannot count a recommendation, invocation, acknowledgement, or self-reported use as value. It needs a joinable outcome and an independent final-state check. | Phase 03 repairs the value spine. Phase 05 uses real cases, negative controls, a distinct checker, and a frozen primary metric. |
| Let evaluation evidence justify architecture complexity. | OpenAI's current evaluation guide says the decision to use multi-agent architecture should be driven by evals and warns that starting there adds complexity. | More agents, registries, dashboards, or orchestration layers are not inherently progress. | Freeze new feature families. Repair the existing kernel and add only controls needed to complete the value test. |
| Treat context as a finite attention budget; retrieve and curate the smallest high-signal set. | [Anthropic: Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) describes context as finite, subject to diminishing returns, and recommends minimal high-signal prompts, tools, examples, retrieval, compaction, and structured notes. | DAD should route compact pointers and task-specific context, not dump the catalog, raw journal, or all prior conversations into every task. | Keep the front door/context map, bound job inputs by digest, and reject another ambient-memory layer. Measure retrieval precision and operator attention before adding RAG infrastructure. |
| Use provider-neutral telemetry vocabulary, but track maturity and privacy. | The [OpenTelemetry GenAI Semantic Conventions repository](https://github.com/open-telemetry/semantic-conventions-genai) defines cross-provider spans, metrics, events, MCP, and evaluation signals; its GenAI documents are explicitly still in development. | DAD benefits from stable internal concepts for run, agent, model, tool, cost, latency, exception, and evaluation, with adapters at the edge. It must not claim OTel compliance or copy unstable fields blindly. | Map only the fields needed by the value spine, pin the upstream revision, keep raw prompts/tool payloads out by default, and revalidate mappings when the convention changes. |
| Model provenance as entities, activities, responsible agents, revisions, and derivations. | [W3C PROV-O](https://www.w3.org/TR/prov-o/) defines interoperable Entity, Activity, Agent, generation, use, derivation, and responsibility concepts. | Asset identity, asset revision, recommendation activity, adoption activity, producer, checker, and lifecycle decision must be separate typed records. | Phase 03 forbids prose in identity fields and requires stable recommendation/revision/adoption/validation joins. |
| Bind artifacts to exact inputs, builders, processes, and verifiable provenance. | [SLSA Build Track 1.2](https://slsa.dev/spec/v1.2/build-track-basics) progresses from provenance existence to hosted, signed, and hardened production; provenance identifies the builder, process, inputs, and output. | A green label without exact source, job, adapter, producer/checker, and evidence digests is weak evidence. | The manifest and receipt checker bind revisions, dependencies, leases, paths, identities, evidence, budgets, and revalidation triggers. DAD borrows the integrity pattern; it does not claim a SLSA level. |
| Define indicators and objectives from user-important behavior, with explicit measurement windows and consequences. | [Google SRE: Service Level Objectives](https://sre.google/sre-book/service-level-objectives/) defines SLIs/SLOs, warns against easy-to-measure proxies and statistical assumptions, and ties objectives to action. | Daemon uptime, records processed, stars, asset count, or centrality are operating signals, not value objectives. | Phase 04 uses readiness ceilings; Phase 05 uses cycle time, rework, review iterations, defects prevented, or operator attention. Missing a gate changes the lifecycle decision instead of changing the metric. |
| Bind authorization to the intended resource and never pass authority through an intermediary. | The [MCP authorization specification](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization) requires audience validation, rejects invalid scopes, forbids token passthrough, and addresses confused-deputy risk. | A DAD recommendation, campaign goal, MCP connection, or upstream approval must not become blanket downstream authority. | Exact effect classes, repo-local approvals, short leases, separate GitHub/downstream/destructive gates, and no token or permission passthrough remain mandatory. |
| Govern, map, measure, and manage AI risk as an ongoing lifecycle. | [NIST AI RMF Generative AI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf) adapts the AI RMF lifecycle to generative-AI risks. | Risk work must be connected to actual scope, evidence, measurement, owners, and response—not just a policy document. | The campaign uses named owners, privacy boundaries, negative controls, harm stops, re-audit, and a signed terminal decision. It does not claim NIST conformance. |

## Architecture implications

### Keep

- The append-only journal, provenance boundaries, deterministic validation,
  reviewed fix kernel, existing registry/asset identity, and repo-local authority.
- MCP-first, provider-neutral interfaces with explicit adapters.
- Existing projections when they can answer a question without gaining mutation
  authority.

### Repair before adding features

- Required CI and branch-protection enforcement.
- Recommendation-to-asset membership and revision validation.
- Adoption/non-adoption, outcome, checker, and lifecycle joins.
- Learning-yield semantics and legacy-row quarantine.
- Operational queue ownership, age, and closure truth.
- Receipt contracts, case-level idempotency, and denominator integrity.

### Add only because a gate requires it

- A fail-closed receipt validator.
- A campaign consistency validator.
- One frozen pilot protocol and case-binding table.
- Atomic case child records and independent cohort reconciliation.
- Minimal cross-provider telemetry mapping for the fields the pilot measures.

These are control/evidence additions, not new product families.

### Defer or reject

- A second operating system, universal ledger, agent family, queue, dashboard,
  graph projection, ambient memory, or broad RAG build.
- Provider-specific optimization before a provider-neutral baseline exists.
- A new database or vector store without a measured retrieval problem and a
  comparative evaluation.
- Autonomous promotion, cleanup, merge, deployment, or downstream enrollment.
- Rust or another language migration without a measured deterministic hotspot,
  shadow parity, and a better result than a narrow Python repair.

## Anti-cargo-cult rules

1. A standard or vendor guide is design evidence, not local authority.
2. “Best practice” does not justify a new component unless it closes a measured
   DAD failure and has an acceptance test.
3. OpenTelemetry GenAI conventions are evolving; pin and adapt, do not mirror
   them as a new source of truth.
4. PROV-O and SLSA inspire typed lineage and integrity; DAD does not claim formal
   compliance or a SLSA level in this campaign.
5. OpenAI's legacy Evals platform is scheduled for retirement in late 2026; use
   the evaluation methodology, not a new dependency on that platform.
6. Synthetic tests validate plumbing and failure paths. Only approved real tasks
   can support a business-value claim.
7. A favorable secondary metric, activity count, or post-hoc cohort definition
   cannot rescue a failed primary gate.

## Highest-value course

The research and audit point to the same sequence:

1. Stop expansion and reproduce the baseline.
2. Make enforcement truthful.
3. Make every counted outcome joinable and independently checkable.
4. Reduce operational debt without deleting ambiguous work.
5. Measure one frozen user-important outcome on comparable real tasks.
6. Scale only the slices that pass; otherwise narrow, retire, or re-audit.

The key architectural move is subtraction: turn DAD from a large collection and
control surface into a smaller evidence-producing loop whose recommendations
can be connected to verified outcomes and explicit human decisions.

