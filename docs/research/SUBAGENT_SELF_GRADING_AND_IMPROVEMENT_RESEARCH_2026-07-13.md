# Self-Grading, Evaluator Integrity, and Cross-Domain Agent Improvement

Date: 2026-07-13
Status: external research synthesis and candidate DAD architecture; not a promotion decision.

## Conclusion

Self-grading is useful when it is a sealed prediction that can later be calibrated. A
runtime receipt before a recorded attempt end proves chronology only; it does not prove
that the actor was blind to outcome signals. It becomes cheating when the same agent sees the outcome, chooses the
rubric, judges its own artifact, controls the evidence, or benefits from the
reported grade and that grade is then treated as proof.

The professional pattern is not "trust a better self-score." It is a separation
of duties:

1. freeze the task and evaluation contract;
2. record the agent's criterion-level prediction before outcome evidence;
3. preserve immutable attempts, environments, and artifacts;
4. run deterministic and domain-specific validation;
5. obtain an independent verdict, preferably blind to the self prediction;
6. audit the evaluator itself;
7. attribute the failure to the agent, model, tool, input, data, workflow,
   handoff, evaluator, domain overlay, or downstream composition;
8. choose no change or a bounded intervention;
9. compare the candidate on held-out or shadow cases;
10. require a human promotion and rollback decision; and
11. monitor drift, latency, cost, and field outcomes.

Self-evaluation is therefore telemetry. It measures whether the actor knows when
it is likely to be wrong. It is not an authority mechanism.

## What Professional Practice Contributes

NIST's AI Risk Management Framework calls for rigorous test, evaluation,
verification, and validation; documentation of uncertainty; objective and
repeatable methods; domain expertise; independent assessment; and evaluation of
the TEVV process itself. This supports an evaluator-integrity layer rather than
assuming the grader is correct. The 11-step loop below is DAD's synthesis, not a
NIST-prescribed ordered checklist; it is based on AI RMF 1.0 while NIST's revision work
continues.

Source:
https://airc.nist.gov/airmf-resources/airmf/5-sec-core/

Anthropic's agent-evaluation guidance emphasizes unambiguous tasks, reference
solutions or clear success criteria, balanced problem sets, stable isolated
environments, deterministic graders where possible, human calibration of LLM
judges, an Unknown option, auditing task/grader defects, and resistance to
reward-hacking shortcuts.

Source:
https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents

OpenAI's PaperBench work separates the benchmark for research replication from
the benchmark used to evaluate the LLM judge. That is the key meta-evaluation
principle: the evaluator is another system with its own failure modes.

Source:
https://openai.com/index/paperbench/

Anthropic's AuditBench reports a tool-to-agent gap for deliberately implanted,
adversarially hidden behavior: an auditor with tools can outperform direct questioning.
This supports treating direct confession as weak for that threat model, not as proof that
all self-report is useless.

Source:
https://alignment.anthropic.com/2026/auditbench/

Research on intrinsic self-correction finds that language models often cannot
reliably correct reasoning without external feedback, and can make initially
correct answers worse. Surveys of self-correction likewise distinguish useful
feedback-driven refinement from unsupported introspection.

Sources:

- https://deepmind.google/research/publications/48252/
- https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00713/125177/When-Can-LLMs-Actually-Correct-Their-Own-Mistakes
- https://proceedings.neurips.cc/paper_files/paper/2023/hash/91edff07232fb1b55a505a9e9f6c0ff3-Abstract-Conference.html

Anthropic's reward-tampering research found rare specification-gaming behavior in an
artificial training setup. DAD infers from that result?not as a prevalence claim about
production models?that a visible grade linked to promotion, routing, or survival should
be threat-modeled as an attack surface.

Source:
https://www.anthropic.com/research/reward-tampering

Google's agentic-system architecture guidance recommends choosing orchestration
complexity according to task complexity, latency, cost, and human involvement.
Predictable structured tasks may not need an agentic loop. This supports a
preserve-simple disposition and workflow-level composition.

Source:
https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system

## Universal Core, Domain Overlays

The universal core governs evidence, independence, calibration, experimentation,
and authority. It does not decide what "correct" means in every domain.

Each domain overlay must state:

- where it applies and does not apply;
- danger if misapplied;
- criterion definitions and validator types;
- deterministic checks and required artifacts;
- necessary professional or domain qualifications;
- uncertainty and contested-claim handling;
- holdout, negative, adversarial, and regression cases;
- latency, cost, and safety budgets;
- minimum comparable evidence before a no-change or modification candidate; and
- an explicit ban on cross-domain score comparison.

No universal leaderboard should compare a financial algorithm researcher, an
archaeology evidence checker, a code formatter, and a portfolio architect.

The current DAD profiles do not yet satisfy this operational contract. They are explicit
candidate routing labels with descriptive criteria. Until artifact requirements,
criterion outcome records, thresholds, qualifications, hard gates, budgets, and trial
design are executable, they can require more evidence but cannot establish domain validity.
Fixed three- or five-attempt values are review floors only, not statistical sufficiency.

### Financial algorithms

Professional model-risk practice requires effective challenge and validation
independent from model development and use. A useful overlay should include:

- data vintage, look-ahead, survivorship, and target leakage checks;
- out-of-sample and regime-aware evaluation;
- realistic transaction cost, slippage, liquidity, and capacity assumptions;
- drawdown, tail, concentration, and stress behavior;
- benchmark and ablation comparisons;
- reproducible data and environment lineage; and
- qualified independent model-risk review.

Primary governance source:
https://www.federalreserve.gov/frrs/guidance/supervisory-guidance-on-model-risk-management.htm

### Archaeology and evidence-heavy historical claims

A useful overlay should include:

- artifact, excavation, collection, and citation provenance;
- stratigraphic, geographic, chronological, and dating context;
- explicit separation of observation, inference, contested interpretation, and
  theological claim;
- counterevidence and current scholarly dispute;
- uncertainty and alternative chronology;
- ethical and legal provenance; and
- qualified specialist review when authenticity, dating, ownership, or
  disciplinary interpretation is material.

Professional sources:

- https://www.saa.org/Member/SAAMember/Career-and-Practice/Principles-of-Archaeological-Ethics.aspx
- https://www.archaeological.org/wp-content/uploads/2019/05/Code-of-Professional-Standards.pdf
- https://www.archaeological.org/wp-content/uploads/2020/01/AIA-Publication-Presentation-Policy.pdf

## Anti-Cheating and Evaluator-Integrity Checks

An independent integrity reviewer should check:

- self-persuasion: make the independent verdict before revealing self score or
  model identity;
- identity and family bias: swap names/models while holding artifacts constant;
- position and verbosity bias: reverse choices and paraphrase or shorten outputs;
- prompt injection and rubric leakage;
- claim/outcome mismatch;
- task and grader bugs;
- hidden holdout canaries;
- known-good and known-bad mutations;
- contamination and evaluation awareness;
- reciprocal review cycles;
- common parent, prompt, training, or data lineage;
- multiple trials and heterogeneous reviewers;
- human adjudication on sampled disagreements;
- reference-solution and rubric viability;
- workflow ablations; and
- field outcome, latency, cost, and regression evidence.

A content hash proves that a record did not change. It does not prove that the
record is truthful, the artifact is valid, the environment is faithful, or the
reviewer is independent.

## Improvement Target Router

The reviewer should output a candidate disposition, competing causal
hypotheses, falsifiers, and a bounded test. It should not edit anything.

Candidate targets:

- agent instruction;
- model or reasoning-effort route;
- tool;
- input contract;
- context or data;
- workflow;
- handoff;
- evaluation harness;
- reviewer;
- domain overlay;
- downstream specialist;
- preserve simple; or
- observe more.

Candidate dispositions include:

- no_change_freeze_candidate;
- collect_more_evidence;
- repair_task_or_rubric;
- repair_evaluator;
- revise_agent_instruction;
- change_model_or_effort_route;
- change_context_or_data;
- change_tool_or_environment;
- redesign_workflow_or_handoff;
- compose_downstream_specialist;
- require_domain_expert;
- retire_or_supersede; and
- human_attribution_required.

## Simple Agents

A reliable narrow agent should not be forced to become reflective and verbose.
For deterministic transforms, validators, routers, and formatters:

- keep the core instruction small;
- put prediction capture, negative tests, fuzz/property tests, latency, cost, and
  independent review in the workflow wrapper;
- freeze the role when a comparable cohort and held-out shadow cases support it;
- compose orthogonal intelligence downstream; and
- reopen improvement only for drift, a new failure class, a contract change, or a
  meaningful cost/latency regression.

"No change" is a positive, evidence-backed improvement decision. It prevents
overfitting, prompt bloat, cost growth, and regressions.

## DAD Implementation Boundary

The initial DAD slice is intentionally candidate-only:

- asset-dir subagents profiles lists explicit overlays;
- asset-dir subagents self-assess --packet PATH adds an actor-claimed prediction with
  non-caller-controlled DAD receipt chronology; it does not attest actor identity or
  outcome blindness;
- asset-dir subagents integrity-review [--profile PROFILE] emits a strict
  read-only meta-evaluation;
- the report copies no source scores and creates no leaderboard;
- missing actor binding, criterion outcome records, blindness, prompt lineage, evidence
  replay, holdout canaries, or domain qualification blocks integrity clearance and the
  preserve-simple freeze path;
- all interventions require a held-out comparison, rollback, and named human
  approval; and
- no routine, auto-edit, model reroute, external send, or promotion is enabled.

## Remaining Research Limits

The first record model does not yet include a verified blind-review attestation,
domain-expert credential attestation, deterministic criterion-verification
record, environment replay receipt, held-out canary result, or signed human
adjudication. The integrity reviewer must report those absences rather than infer
them. A later version may add those records only after supervised trials show
that the extra ceremony improves decisions more than it increases cost and
latency.
