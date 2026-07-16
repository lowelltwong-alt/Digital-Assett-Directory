# AI Self-Learning and Improvement Research

Date: 2026-07-14
Status: primary-source synthesis and candidate architecture; not an activation,
training authorization, or promotion decision.

## Executive conclusion

DAD should add a cross-cutting **Self-Learning and Improvement overlay**, not an
eleventh product family and not a self-authorizing AI. The overlay observes
outcomes, finds capability gaps, routes the smallest useful improvement method,
constructs an isolated candidate, and requires frozen evaluation, an independent
checker, and Lowell's decision before adoption.

The research supports systems that improve from external evidence: execution
results, deterministic tests, trusted graders, held-out trials, human decisions,
and later field outcomes. It does not support treating unverified reflection or
self-grading as proof. Critique and revision help when the critic has better
information; intrinsic self-correction can also degrade correct answers. DAD
therefore treats self-assessment as telemetry and makes the evaluator a separately
governed component.

This overlay owns non-parametric and workflow learning. The existing Machine
Learning family owns parameter- and architecture-changing experiments. No weekly
routine may train, edit, deploy, promote, or retire a production model, workflow,
skill, policy, or agent instruction.

## What "self-learning" means

The term hides materially different mechanisms. DAD routes by the state being
changed, not by a paper's label.

| Surface | Changed state | Examples | Default authority |
|---|---|---|---|
| T0 | Test-time compute only | retries, search, best-of-N, tool execution feedback | Improvement overlay, bounded by run budget |
| T1 | Prompt, workflow, role, trigger, or tool policy | critique/refine, prompt optimization, workflow composition | Improvement overlay, candidate-only |
| T2 | External memory, retrieval, index, or skill library | episodic memory, RAG refresh, lesson retrieval | Improvement overlay plus Data/Graph governance |
| T3 | Training or evaluation data | active learning, hard-negative mining, synthetic data, curricula | Improvement overlay proposes; ML/Data/Quality validate |
| T4 | Model weights or adapters | fine-tuning, distillation, RLHF/RLAIF/RLVR, model editing | ML family; dormant until exact consequence classification and separate sandbox approval |
| T5 | Architecture or module population | expansion, isolation, evolutionary architecture search | ML family; dormant until exact consequence classification and separate sandbox approval |

Risk, rollback cost, contamination risk, and proof burden normally rise from T0
through T5. A T0 change can still be high consequence when it controls an external
tool, and a T1 prompt edit can still weaken authority. Consequence and update
surface are separate classifications. A bounded, isolated T4/T5 experiment may
be classified C2 or C3 only after its exact data, compute, output, and rollback
boundary is reviewed; unbounded or production autonomous self-modification is C4
and remains prohibited.

T0-T5 is multi-label. Tool execution can be T0 plus an external-effect
consequence; an executable memory or skill can be T1 and T2; agent-topology search
is T1 even when it changes the module population, while learned architectural
expansion is T5. Every case records all affected surfaces and applies the highest
applicable evidence and authority gate.

## Technique map

| Technique family | Surface | Useful when | Principal failure modes | Required proof |
|---|---:|---|---|---|
| External-feedback repair | T0/T1 | an executable check exposes a bounded error | repeated thrashing; degradation of correct work | replay, attempt cap, unchanged evaluator |
| Critique/refine and verbal reflection | T1/T2 | critic has external evidence or a different constraint view | confident unsupported critique; recursive false lessons | independent or deterministic feedback; replayed lesson |
| Best-of-N and verifier-guided search | T0 | candidates vary and a reliable verifier exists | verifier gaming; cost explosion; correlated samples | fixed budget and cost-normalized comparison |
| Debate or independent challenge | T0/T1 | disagreement predicts consequential errors | protocol sensitivity; group convergence; higher cost than ensembling | compare with simpler ensemble/self-consistency |
| Prompt/program optimization | T1 | task and evaluator are stable and repeatable | development-set overfit; prompt bloat; provider lock-in | frozen splits, provider stratification, ablation |
| Workflow/agent topology search | T1 | compound systems have measurable outcomes | excess roles/calls; proxy optimization; brittle topology | topology/cost caps and simplest-baseline comparison |
| Episodic memory and RAG | T2 | prior verified evidence is repeatedly useful | stale or poisoned memory; irrelevant retrieval; privacy leakage | retrieval-on/off bakeoff, provenance, expiry, deletion |
| Active learning | T3 | labels are scarce and uncertainty can be calibrated | selection bias; uncertain examples are not necessarily valuable | blind label process and downstream holdout gain |
| Self-supervised representation learning | T3/T4 | large unlabeled, lawful, domain-matched corpus exists | shortcut features; transfer failure; compute cost | non-target and downstream transfer evaluation |
| Pseudo-labeling/self-training | T3/T4 | teacher confidence is calibrated | confirmation bias; minority-class collapse | threshold/coverage analysis and human audit |
| Curriculum and hard-negative mining | T3/T4 | difficulty ordering or failure clusters matter | leakage; narrowness; catastrophic focus on edge cases | fresh holdout, diversity and retention checks |
| Distillation | T4 | a capable teacher can create a cheaper specialist | inherited errors; lost tail behavior; false savings | compare student, teacher, and direct-teacher cost |
| Meta-learning | T4 | many related tasks support fast adaptation | task-distribution overfit; expensive meta-training | out-of-distribution task families and adaptation cost |
| Continual learning/replay/consolidation | T3/T4 | sequential data cannot be retrained from scratch | catastrophic forgetting, stability gap, order effects, replay bias | forward/back transfer, worst-slice retention, multiple orders |
| Test-time adaptation | T4 at inference | observable domain shift has a trustworthy unsupervised signal | error accumulation; source forgetting; adversarial adaptation | online rollback, source retention, shift-specific trials |
| RLHF/RLAIF/process supervision/RLVR | T3/T4 | preference or verifiable outcome signals are reliable | reward hacking, judge bias, sycophancy, evaluator tampering | inaccessible reward, grader calibration, attack testing |
| Self-play and open-ended/evolutionary search | T3-T5 | simulator or objective supports diverse competition | collusion, cycles, narrow equilibria, unbounded compute | historical opponents, diversity, fixed resource envelope |
| Model editing and unlearning | T4 | a precise correction/deletion obligation exists | collateral changes, incomplete erasure, capability regression | locality, generality, privacy, safety, and relearning tests |

### Evidence boundaries

- Reflexion and Self-Refine demonstrate useful inference-time scaffolding and
  memory; they do not establish autonomous weight learning or trustworthy
  self-approval ([Reflexion](https://arxiv.org/abs/2303.11366),
  [Self-Refine](https://proceedings.neurips.cc/paper_files/paper/2023/hash/91edff07232fb1b55a505a9e9f6c0ff3-Abstract-Conference.html)).
- A critical survey found little broad evidence for successful intrinsic
  self-correction without external feedback, and separate work found that models
  more readily correct a located error than find it themselves
  ([TACL survey](https://aclanthology.org/2024.tacl-1.78/),
  [ACL Findings study](https://aclanthology.org/2024.findings-acl.826/)).
- OPRO, DSPy, TextGrad, and AFlow show that prompts, programs, and workflows can
  be optimized against defined evaluators. They are candidate generators, not
  trusted judges ([OPRO](https://arxiv.org/abs/2309.03409),
  [DSPy](https://openreview.net/forum?id=sY5N0zY5Od),
  [TextGrad](https://arxiv.org/abs/2406.07496),
  [AFlow](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5492ecbce4439401798dcd2c90be94cd-Abstract-Conference.html)).
- Continual-learning results require explicit forgetting and transfer measures;
  replay can help but can also introduce instability or bias
  ([continual evaluation](https://openreview.net/forum?id=Zy350cRstc6),
  [EWC](https://arxiv.org/abs/1612.00796),
  [large-scale replay study](https://proceedings.mlr.press/v235/yoo24a.html)).
- DAD infers that external RAG and structured memory can make content updates more
  inspectable and rollback-friendly than weight edits when revisions and deletion
  are implemented explicitly; the cited papers do not by themselves prove this
  governance property. Retrieved material remains evidence rather than truth
  ([RAG](https://proceedings.neurips.cc/paper/2020/hash/6b493230-Abstract.html),
  [Voyager](https://arxiv.org/abs/2305.16291)).
- Reward and evaluator surfaces must be treated as attack surfaces. Published
  reward-tampering work is a warning about specification gaming, not a prevalence
  estimate for ordinary production agents
  ([Anthropic reward tampering](https://www.anthropic.com/research/reward-tampering),
  [DeepMind specification gaming](https://deepmind.google/blog/specification-gaming-the-flip-side-of-ai-ingenuity/)).
- Test-time adaptation can improve shifted data but may accumulate errors and
  forget the source distribution
  ([TENT](https://openreview.net/pdf/4de0af9691a5dcc52de7de756676fded33d037ef.pdf),
  [CoTTA](https://openaccess.thecvf.com/content/CVPR2022/html/Wang_Continual_Test-Time_Domain_Adaptation_CVPR_2022_paper.html)).
- Model editing and unlearning require wide collateral-effect tests; a target fact
  changing is not sufficient evidence of safe removal
  ([ROME](https://proceedings.neurips.cc/paper_files/paper/2022/hash/6f1d43d5a82a37e89b0665b33bf3a182-Abstract-Conference.html),
  [MUSE](https://arxiv.org/abs/2407.06460)).

## The governed improvement loop

```text
observed outcome
  -> normalized, deduplicated signal
  -> eligibility and preserve-simple check
  -> causal hypothesis and smallest applicable method
  -> isolated candidate with immutable baseline/evaluator
  -> held-out shadow trial and anti-gaming attack
  -> independent checker
  -> human: adopt | extend pilot | reject | preserve current
  -> expiring activation lease, monitoring, and rollback
```

Every material case carries: update surface, consequence tier, producer and
checker identities, evidence and counterevidence, privacy/license state,
baseline and evaluator digests, inaccessible holdout, metrics and uncertainty,
cost/latency/human-attention budget, falsifier, kill criteria, rollback, affected
dependencies, and human decision.

An improvement is rejected when it wins only on development data; weakens safety,
privacy, authority, evaluator integrity, or maintainability; loses its advantage
on a later/provider-stratified holdout; cannot clear the predeclared practical
effect; costs disproportionate tokens or attention; improves a proxy while the
downstream outcome regresses; or performs no better than the simpler route.

## Expert capability packs

These are routed specialist packs, not continuously running personalities:

1. improvement router and portfolio steward;
2. research methodologist and provenance curator;
3. evaluation and causal-measurement scientist;
4. evaluator-integrity and reward-hacking specialist;
5. prompt, program, workflow, and routing optimizer;
6. memory, retrieval, and continual-learning engineer;
7. data, curriculum, and learning-signal curator;
8. tool-use and coding-trajectory improvement engineer;
9. training, distillation, RL, and model-editing specialist;
10. drift, feedback-loop, and capability-freshness sentinel;
11. cost, compute, and human-attention optimizer; and
12. independent adoption checker.

The shared family hierarchy remains router, boss, architect, foreman, worker,
independent checker, and sentinel. A task activates only the specialist packs it
needs. Domain overlays provide the definition of correctness, validators, and
task data; they do not duplicate the universal improvement machinery.

## Evidence classes

The source ledger distinguishes peer-reviewed proceedings/journals, reviewed
conference records, preprints, and official laboratory research reports. Peer
review is evidence-quality metadata, not a truth flag. Recent preprints and lab
reports may create research or reproduction candidates but cannot alone change
authority or an active workflow. Architecture conclusions in this document are
DAD synthesis unless the text explicitly attributes them to a source.

## Weekly research operations

The cheap design is a metadata-first delta harvester, not a general web crawler.
Its authoritative starting sources are arXiv, OpenReview, Crossref, Semantic
Scholar, PMLR/conference proceedings, ACL Anthology, watched implementation
releases, and official laboratory feeds. Blogs, aggregators, and social posts may
identify a lead but cannot establish adoption evidence.

Official interfaces and operating constraints:

- [arXiv API](https://info.arxiv.org/help/api/index.html),
  [terms](https://info.arxiv.org/help/api/tou.html), and
  [RSS](https://info.arxiv.org/help/rss.html)
- [OpenReview API v2](https://docs.openreview.net/reference/api-v2/openapi-definition)
- [Crossref REST guidance](https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/)
- [Semantic Scholar API](https://www.semanticscholar.org/product/api)
- [GitHub REST best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api)
- [ACL Anthology development interface](https://aclanthology.org/info/development/)

Each source needs its own reviewed collection contract before implementation:
permitted public fields, terms/robots version, request identity and rate policy,
cache location/size/TTL, raw-response retention, full-text/license rule, privacy
exclusions, cursor, and deletion path. OpenReview is limited to publicly readable
Notes and public metadata; private reviews, restricted readers, and private
profiles are excluded. Crossref is enrichment-only for shortlisted DOI identity,
relationships, publication updates, and retractions rather than a broad weekly
index harvest.

The weekly funnel is:

1. Check cursors, ETags, versions, acceptance/retraction state, and a 48-hour
   overlap. Weekly arXiv discovery uses submitted/updated-date API windows; RSS
   is only an announcement signal unless an approved deterministic daily process
   stores its snapshots, because a weekly RSS fetch alone can miss prior daily
   feed contents. If every source is unchanged, write one heartbeat and stop
   with zero model tokens and no cockpit item.
2. Normalize identity using DOI, arXiv base ID plus revision, OpenReview ID,
   proceedings ID, then a title-author-year fingerprint.
3. Apply deterministic taxonomy, source allowlists, BM25/full-text-index ranking,
   and duplicate/near-duplicate suppression.
4. Let Luna inspect only novel abstracts and emit structured candidate fields.
5. Let the smallest relevant expert and a distinct citation checker inspect the
   few surviving papers.
6. Project paper -> claim -> technique -> applicability condition -> workflow ->
   harness -> risk -> validator -> capability candidate. Nothing is adopted.

Separate relevance, novelty, and evidence-quality scores. Never combine them
into a truth score. A new paper can be relevant but weak; an old paper can remain
authoritative. Retractions, direct contradictions, critical safety discoveries,
or a changed dependency may bypass ordinary ranking but not the human gate.

Recommended normal envelope: 20-60 HTTP requests, less than 5 MB metadata, at
most 40 novel abstracts for Luna, at most six full papers for Terra, and no
recurring Sol or Fable call. Luna and Terra share one budget rather than each
receiving an additive allowance: normally no more than 30,000 input plus 4,000
output tokens for abstract triage and 70,000 input plus 12,000 output tokens for
evidence review, for a combined ceiling of 116,000. A 300,000-token hard
per-cycle ceiling requires a material delta and explicit recorded budget. A
digest exposes at most three decisions and should take less than ten minutes to
review.

Pause a query when false positives exceed 60% for four cycles, duplicates exceed
80% for four runs, no result is retained or adopted for twelve weeks, source
terms change, repeated authorization/rate-limit errors occur, identity collisions
cannot be resolved, or a cheaper authoritative source supersedes it.

## Selected load-bearing source ledger

This is a pointer ledger, not a copied-paper library. `P` means peer-reviewed
proceedings/journal, `R` a reviewed conference record, `A` a preprint, and `O` an
official research report. Status describes provenance, not truth.

| ID | Technique or boundary | Class | Primary source |
|---|---|---:|---|
| AG-01 | intrinsic self-correction limitation | P | [TACL critical survey](https://aclanthology.org/2024.tacl-1.78/) |
| AG-02 | error location versus correction | P | [ACL Findings study](https://aclanthology.org/2024.findings-acl.826/) |
| AG-03 | feedback/reflection memory | R | [Reflexion](https://arxiv.org/abs/2303.11366) |
| AG-04 | iterative self-refinement | R | [Self-Refine](https://proceedings.neurips.cc/paper_files/paper/2023/hash/91edff07232fb1b55a505a9e9f6c0ff3-Abstract-Conference.html) |
| AG-05 | prompt optimization | A | [OPRO](https://arxiv.org/abs/2309.03409) |
| AG-06 | program optimization | R | [DSPy](https://openreview.net/forum?id=sY5N0zY5Od) |
| AG-07 | textual-gradient optimization | A | [TextGrad](https://arxiv.org/abs/2406.07496) |
| AG-08 | workflow topology search | R | [AFlow](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5492ecbce4439401798dcd2c90be94cd-Abstract-Conference.html) |
| CL-01 | consolidation/EWC | A/P | [Kirkpatrick et al.](https://arxiv.org/abs/1612.00796) |
| CL-02 | continual evaluation/stability gap | R | [De Lange et al.](https://openreview.net/forum?id=Zy350cRstc6) |
| CL-03 | task similarity/order and forgetting | P | [Lin et al.](https://proceedings.mlr.press/v202/lin23f.html) |
| CL-04 | replay instability | P | [Yoo et al.](https://proceedings.mlr.press/v235/yoo24a.html) |
| DT-01 | active learning | P | [Gal et al.](https://proceedings.mlr.press/v70/gal17a.html) |
| DT-02 | pseudo-label/self-training | R | [FixMatch](https://proceedings.neurips.cc/paper/2020/hash/06964dce9addb1c5cb5d6e3d9838f733-Abstract.html) |
| DT-03 | meta-learning | P | [MAML](https://proceedings.mlr.press/v70/finn17a.html) |
| DT-04 | curriculum learning | P | [Bengio et al.](https://icml.cc/Conferences/2009/papers/119.pdf) |
| RL-01 | self-play/search | P | [AlphaGo Zero](https://www.nature.com/articles/nature24270) |
| RL-02 | RLHF | A/O | [InstructGPT](https://arxiv.org/abs/2203.02155) |
| RL-03 | RLAIF/constitutional critique | A/O | [Constitutional AI](https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback) |
| RL-04 | process supervision | O | [OpenAI report](https://openai.com/index/improving-mathematical-reasoning-with-process-supervision/) |
| MM-01 | external memory/RAG | R | [Lewis et al.](https://proceedings.neurips.cc/paper/2020/hash/6b493230-Abstract.html) |
| MM-02 | skill library/curriculum/memory | A | [Voyager](https://arxiv.org/abs/2305.16291) |
| DP-01 | test-time adaptation | R | [TENT](https://openreview.net/pdf/4de0af9691a5dcc52de7de756676fded33d037ef.pdf) |
| DP-02 | continual test-time adaptation limits | R | [CoTTA](https://openaccess.thecvf.com/content/CVPR2022/html/Wang_Continual_Test-Time_Domain_Adaptation_CVPR_2022_paper.html) |
| ED-01 | targeted model editing | R | [ROME](https://proceedings.neurips.cc/paper_files/paper/2022/hash/6f1d43d5a82a37e89b0665b33bf3a182-Abstract-Conference.html) |
| ED-02 | unlearning evaluation | A | [MUSE](https://arxiv.org/abs/2407.06460) |
| GV-01 | evaluator/risk governance | O | [NIST AI RMF core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/) |
| GV-02 | reward-tampering risk | O | [Anthropic report](https://www.anthropic.com/research/reward-tampering) |

The weekly radar must retain publication/revision date, venue/review state,
claim, limitation, and supersession/contradiction edges for every source it uses.
This initial ledger is deliberately incomplete and grows only through the
governed intake pipeline.

## Research limitations and open questions

- Many "self-evolving" agent results remain recent, benchmark-specific, and hard
  to compare. DAD should reproduce claims that could change authority or
  architecture before adoption.
- Model-provider transfer is an explicit unknown until the same workflow is
  evaluated across resolved Luna/Terra/Sol runtimes.
- Field utility and human-attention savings cannot be inferred from benchmark
  accuracy. The pilot must measure both.
- A weekly crawler can keep evidence fresh; it cannot make promotion decisions.
- T4/T5 work requires dedicated data governance, compute approval, checkpoint
  rollback, and a validator inaccessible to the learner. Those facilities do not
  yet exist and are outside this plan's activation boundary.

## Candidate disposition

Proceed to a phased, candidate-only design review. Build the evidence and
evaluation kernel before any optimizer. Pilot T1/T2 improvements before T3 and
keep T4/T5 under the ML family. Send the sanitized architecture packet to Fable
for an independent frontier review. Do not activate the weekly routine or any
self-modification path until that review, an independent DAD check, and Lowell's
separate approval are recorded.
