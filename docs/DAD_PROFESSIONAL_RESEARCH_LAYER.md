# DAD Professional Research Layer

Status: candidate control-plane design for professional research, source radar,
agent-role routing, and high-signal coding improvement intake.

## Purpose

DAD should not make every agent rediscover the same professional practice from
scratch. The professional research layer gives agents an early, deterministic
path for hard coding, architecture, testing, governance, and learning-loop work:

1. Search DAD first.
2. If DAD has no validated or relevant candidate, run bounded professional
   research.
3. Capture the useful result back into DAD as pointer-only candidate knowledge.
4. Promote only after screening, validation, and the right human/review gate.

This layer optimizes for AI coding and AI code reading. It borrows from human
software practices only when they improve the agent feedback loop, executable
proof, traceability, reviewability, or reusable context. Scrum, architecture
review, SRE, KCS, security review, and research workflows should be translated
into compact machine-actionable gates instead of copied as human ceremony.

## Operating Ladder

| Step | Agent action | DAD surface |
| --- | --- | --- |
| `dad_lookup_first` | Search context pack, offerings, lessons, exception fixes, harnesses, skills, tactics, and language playbooks. | `asset-dir agent preflight`, `asset-dir exceptions hard-issue-lookup`, `registry/dad-offerings-registry.json` |
| `professional_method_lookup` | If the problem is hard or novel, map it to a professional method: SRE incident learning, KCS reuse, security review, architecture decision, test strategy, performance profiling, or release engineering. | This document, `docs/RESEARCH_INTAKE_PIPELINE.md`, `registry/trusted-source-registry.json` |
| `public_source_research` | Consult reviewed source categories and record source pointers, not copied content. | `asset-dir research frontier-watch`, `asset-dir research intake` |
| `harness_or_skill_distill` | Convert the finding into a harness, skill pointer, tactic, exception pattern, or offering candidate with a falsification test. | `docs/HARNESS_DISCOVERY_RADAR.md`, `assets/coding-harnesses/language-frontier-research/` |
| `postflight_learning` | Record whether the recommendation helped, failed, was ignored, or was harmful. | `asset-dir agent postflight`, `processed/usage/decision-traces.jsonl`, exception/fix outcome ledgers |

The first step is mandatory for material work. External research is the fallback
when local DAD knowledge is missing, stale, unvalidated, or only loosely related.

## Role Lanes

These lanes are model-agnostic roles. Codex, Claude Code, Cursor, Fable, or a
future agent may implement them as subagents, skills, hooks, prompts, or ordinary
checklists depending on the environment.

| Lane | Trigger | Output |
| --- | --- | --- |
| `research-lane:dad-solution-lookup` | A task is non-trivial, risky, repeated, slow, blocked, or has prior exception signals. | DAD candidate matches, known fixes, warnings, stop conditions, and trace IDs. |
| `research-lane:professional-method-scout` | The task maps to architecture, SRE, testing, security, performance, knowledge management, release, or governance work. | Short method mapping adapted for AI agents, not human ceremony. |
| `research-lane:real-world-fix-scout` | DAD lookup misses and the issue has concrete error, dependency, tool, or repo-pattern clues. | Pointer-only public-source fix candidates with provenance, applicability limits, and validation ideas. |
| `research-lane:frontier-ai-capability-scout` | A source claims a new agent, harness, eval, tool-use, skill, context, or coding workflow capability. | High-signal frontier candidate, source tier, risk flags, and suggested DAD destination. |
| `research-lane:harness-skill-distiller` | A fix, source, or repeated pain can improve future AI coding. | Harness/skill/tactic candidate with an executable proof surface or rejection reason. |
| `research-lane:lesson-pattern-scout` | During preflight, midflight, or postflight the agent notices a reusable pattern or miss. | Candidate lesson, exception event, fix outcome, or DAD-needs mail. |
| `research-lane:red-team-noise-filter` | A finding is exciting, broad, externally sourced, public-facing, or could mutate governance. | False-positive checks, leak/provenance review, private/public hold decision, and tests. |

The expected default for substantial coding work is two explicit review lanes:
red-team/premortem and lesson-asset-harness scout. Professional research lanes
join those when DAD lacks a strong local answer.

## AI-Optimized Professional Practice

Human process names are source material, not doctrine. DAD should translate them
like this:

| Human practice | AI-first adaptation |
| --- | --- |
| Scrum backlog | Small hypothesis queue with task IDs, proof commands, stop conditions, and stale-item pruning. |
| Architecture review | Context-pack constraints, source-of-truth boundaries, interface contracts, and rollback/failure modes. |
| SRE postmortem | Exception/fix records with triggers, impact class, root-cause candidate, validated fix refs, and recurrence tests. |
| KCS knowledge base | Search DAD early/often; improve records when reused; capture if worth solving and missing. |
| Code review | Structured red-team prompt, high-risk diff checks, regression tests, and audit notes. |
| Research spike | Pointer-only source packet, trust tier, applicability limits, local falsification command, and promotion gate. |
| Pair programming | Main agent plus bounded specialist lane; specialist returns summarized findings, not unbounded logs. |

The result should be easier for an AI agent to read than a human process wiki:
stable IDs, short cards, schemas, command examples, path refs, validation refs,
known failure modes, and update channels.

## High-Signal Frontier Escalation

A research item is high-signal for DAD when it meets several of these criteria:

- It comes from a reviewed source category: official model/vendor docs, language
  project docs, professional SRE/security/testing bodies, or a known expert with
  reproducible examples.
- It changes the feedback loop for AI coding: better tests, harnesses, evals,
  structured outputs, context packs, tool interfaces, code reading, or repair.
- It has a local proof surface: test runner, compiler, linter, type checker,
  fuzzer, profiler, package auditor, schema validator, or reproducible script.
- It applies across multiple DAD-connected repos or an important protected repo.
- It explains a repeated failure, missed capture pattern, slow test battery,
  public/private boundary, or prior exception cluster.
- It can be captured as a pointer, delta, or harness case without copying
  proprietary text, leaked material, private data, secrets, raw logs, or source
  blobs.

High-signal does not mean true. It means DAD should create a candidate intake
record, route it to the right harness/asset/skill surface, and ask for validation.

## Leak And Hype Handling

If a leak, rumor, benchmark headline, or social-media thread suggests an
important coding-agent pattern, DAD may record only a public-safe pointer that a
topic needs review. It must not copy leaked/proprietary content or make the leak
the source of truth. The next step is to look for official documentation,
reputable public analysis, independent reproduction, or a local harness that can
test the idea without importing unsafe material.

This matters for examples like agent harness discussions. If official docs,
white papers, or reputable practitioner writeups show that harnesses, skills,
subagents, hooks, or eval loops materially improve coding agents, DAD should
escalate that as a frontier candidate. If the only evidence is leaked text or
uncorroborated claims, the item stays quarantined.

## Source Tiers To Prefer

| Tier | Examples | DAD action |
| --- | --- | --- |
| Official and reviewed | Language projects, model/vendor docs, SRE/KCS/security/testing bodies. | Pointer intake, screen, and route to harness or guidance. |
| Known practitioner | Maintainer blogs, high-signal engineering blogs, widely used tool authors. | Pointer intake with stricter applicability and validation notes. |
| Public codebase reference | Mature open-source repos with license/maintenance review. | Study as pointer-only inspiration; never vendor source through research. |
| Preprint or benchmark | arXiv, benchmark reports, lab notes. | Treat as hypothesis until local eval exists. |
| Leak/rumor/social thread | Unverified claims, copied proprietary material, viral takes. | Quarantine or reject; seek official/reputable source before use. |

## Capture Contract

Research that helps should become one of these candidate outputs:

- `dad:need:language-frontier-signals` mail for language/tooling discoveries.
- A harness discovery candidate under `processed/harnesses/`.
- A research intake record under `processed/research/intake/`.
- An exception/fix outcome when the research solved a hard issue.
- A coding tactic candidate in `registry/coding-tactics-radar.json`.
- A pointer-only offering or skill checkout candidate after screening.
- A postflight trace outcome tied to the preflight recommendation trace.

Every output should include source pointer, safe summary, why it matters, where
it applies, where it does not apply, proof surface, local validation idea,
provenance/licensing risk, public/private boundary, and proposed DAD destination.

## Tests DAD Needs

The research layer needs synthetic tests before it becomes operationally trusted:

- DAD lookup finds a prior fix and blocks unnecessary web research.
- DAD lookup misses, then professional research creates a pointer-only candidate.
- A high-signal official source escalates to harness discovery.
- A noisy blog post stays candidate-only and does not change guidance.
- A leak-like input is quarantined and no copied content enters DAD.
- A researched fix used in a real task is recorded as a fix outcome and later
  appears in hard-issue lookup.
- A source update changes the recommended DAD destination and stale guidance
  fails validation.
- Role selection differs by task: SRE-like issue, architecture issue, Rust
  performance issue, Python test issue, agent-instruction issue, and
  public/private boundary issue.

## Red-Team Premortem

Failure story: an agent sees an exciting frontier post, bypasses DAD lookup,
copies too much external content into a repo, labels the item high confidence,
and sends upgrade notices everywhere. A later agent treats that candidate as
reviewed doctrine, bloating repos with untested harnesses and leaking provenance
or private context.

Controls:

- DAD lookup first; research only after miss/stale/weak match.
- Pointer-only external intake.
- Separate high-signal from high-confidence.
- Require proof surfaces and local validation before promotion.
- Human release gates for private/public movement.
- Postflight outcome capture so reuse becomes review.
- Budgeted upgrade notices to avoid inbox spam.

## Fable Assignment

Use `docs/FABLE_PROFESSIONAL_RESEARCH_LAYER_PROMPT.md` when asking Fable to
stress-test this design. Ask it to improve role routing, high-signal detection,
noise filtering, novelty/delta capture, graph structure, and the AI-first
translation of human professional methods.
