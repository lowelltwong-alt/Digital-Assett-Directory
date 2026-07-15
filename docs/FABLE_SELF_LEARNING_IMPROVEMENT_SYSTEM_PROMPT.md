# Fable Handoff — Self-Learning and Improvement System

Use: manually copy the prompt below into Fable. Do not attach repositories,
private conversations, client material, secrets, absolute paths, or unpublished
source rows. Fable's response is advisory and must return to DAD for reconciliation,
independent review, and Lowell's decision.

---

## Prompt for Fable

You are the independent frontier architecture reviewer for **Design B**, a
candidate self-learning and self-improvement operating system for a one-person
technical-product portfolio. The operator has a separate full-time job, so the
system must be quiet, cheap, comprehensible, reversible, and usable in under ten
minutes per normal review. Do not assume Design B is correct. Reconstruct the
best architecture you would recommend, compare it with Design B, and state the
strongest disagreement first.

Budget: keep the full response under 12,000 output tokens. Prefer compact tables
and exact changes over repeating this packet.

### Mission

Design a model- and provider-independent system that can:

- observe privacy-safe outcomes and capability gaps;
- learn from failures, corrections, successful trajectories, research, and
  later field results;
- route expert subagents for the relevant improvement method;
- compose repeated successful capability sequences into candidate workflows;
- keep prompts, skills, workflows, memories, evaluators, and dependencies fresh;
- research new AI learning and agent-improvement techniques weekly at low cost;
- test improvement candidates without benchmark/evaluator gaming;
- preserve the current system when change is not justified; and
- surface at most three immediate decisions to one human.

This is an operating overlay across engineering, ML, quality, security, data,
research, integration, product, platform, and domain-governance capabilities.
It is not a new producer family and is not allowed to silently rewrite itself.

### Existing Design B

Design B classifies improvement by the state changed:

- T0: test-time compute/search only;
- T1: prompts, roles, workflows, triggers, and tool policy;
- T2: external memory, retrieval, indexes, and skill libraries;
- T3: training or evaluation data;
- T4: model parameters/adapters; and
- T5: architecture or module population.

The improvement overlay owns T0-T2 and proposes T3 candidates. A separately
governed ML family owns dormant T4/T5 sandbox design. Any bounded experiment
requires exact consequence classification and separate approval; autonomous or
production self-modification remains prohibited. Stable roles use abstract Luna,
Terra, and Sol capability tiers resolved at runtime from available models,
tools, privacy, cost, context, and consequence. Permanent vendor model IDs are
not stored in role definitions.

The common loop is:

```text
outcome -> normalize/dedupe -> eligibility/preserve-simple
-> causal hypothesis -> smallest applicable improvement method
-> isolated candidate -> frozen evaluator and inaccessible holdout
-> anti-gaming review -> independent checker
-> human adopt / extend / reject / preserve current
-> expiring activation lease, monitoring, rollback
```

The component being optimized cannot control its evaluator, holdout, approval,
or rollback. Producers cannot approve their own material output. Self-grades are
telemetry, not evidence of correctness.

Candidate expert packs are:

1. improvement router/portfolio steward;
2. research methodologist/provenance curator;
3. evaluation/causal-measurement scientist;
4. evaluator-integrity/reward-hacking specialist;
5. prompt/program/workflow optimizer;
6. memory/retrieval/continual-learning engineer;
7. data/curriculum/learning-signal curator;
8. tool-use/coding-trajectory engineer;
9. training/distillation/RL/model-editing specialist;
10. drift/freshness sentinel;
11. cost/compute/human-attention optimizer; and
12. independent adoption checker.

Design B proposes these workflow groups:

- eligibility, baseline/evaluator freeze, clustering, causal ablation,
  evaluator-integrity attack, preserve-simple comparison;
- external-feedback repair, critique/refine, best-of-N, adaptive test-time
  search, debate/challenge, tool and coding-trajectory repair;
- failure-to-lesson, memory admission/bakeoff/consolidation/poisoning audit,
  trace-to-workflow composition, skill/trigger improvement, supersession;
- prompt, demonstration, compound-program, topology, role, and model-route
  optimization;
- active evidence, hard negatives, data/drift correction, synthetic data,
  curricula, benchmark refresh, judge calibration, red-team, and cost loops; and
- separately gated continual learning, fine-tuning/distillation/RL, test-time
  adaptation, self-play/evolutionary search, model editing/unlearning, provider
  migration, and improvement-of-improvement experiments.

Every material case has versioned records for the baseline, immutable evaluator,
causal hypothesis, candidate, trial matrix, integrity report, independent
challenge, human decision, activation lease, rollback, post-adoption observation,
and lesson candidate.

The weekly research design is a metadata-first `P7D` delta funnel:

1. deterministic cursor/ETag/version/retraction check; arXiv uses submitted/
   updated-date API windows with overlap because a weekly RSS fetch alone is not
   complete; unchanged means zero model tokens and no notification;
2. DOI/arXiv/OpenReview/proceedings identity normalization and deduplication;
3. deterministic source/taxonomy/BM25/near-duplicate filtering;
4. Luna structured review of at most 40 novel abstracts;
5. Terra evidence review of at most six full papers;
6. a distinct citation/evidence checker; and
7. paper -> claim -> technique -> applicability -> workflow -> harness -> risk
   -> validator -> candidate graph reconstruction.

Sources begin with arXiv, OpenReview, primary conference proceedings, ACL
Anthology, Crossref, Semantic Scholar, watched implementation releases, and
official lab feeds. Luna abstract triage and Terra evidence review share one
normal 116,000-token envelope; hard ceiling 300,000 only for a recorded material
delta. Recurring Sol or Fable use is forbidden. The digest contains at most
three decisions.

No routine can activate itself, expand authority, edit active instructions,
train or deploy a model, send a message, spend money, release, or mutate an
external system. Any activation is separately human approved, leased, scoped,
audited, expiring, and reversible.

### Your review tasks

Produce a rigorous design review with these exact sections:

1. **Verdict** — `sound`, `sound_with_material_changes`, or `redesign`; include
   confidence and the three most important reasons.
2. **Strongest disagreement** — argue the best case against Design B before
   offering improvements.
3. **Independent architecture** — describe the architecture you would build
   without copying Design B's structure. Then map agreements and conflicts.
4. **Taxonomy review** — test whether T0-T5 is complete, mutually useful, and
   correctly split between overlay and ML authority. Add or replace dimensions
   if needed.
5. **Expert topology** — merge roles that are cosmetic, split roles with truly
   different methods/authority/failure modes, and give routing conditions. Keep
   fan-out and human attention bounded.
6. **Workflow coverage** — identify missing, duplicated, unsafe, or
   over-engineered loops. Supply a prioritized minimum viable suite and a later
   advanced suite.
7. **Evaluation integrity** — threat-model evaluator control, holdout leakage,
   prompt/data contamination, reward hacking, reciprocal review, identity bias,
   proxy optimization, and apparent gains caused by more compute.
8. **Weekly research economics** — redesign the crawler if necessary. Specify
   authoritative sources, legal/terms boundaries, cursors, dedupe, relevance vs
   novelty vs evidence grading, token/HTTP/storage caps, stop rules, and how to
   prove that the routine creates value rather than noise.
9. **Graph/data contract** — give the minimum node/edge/event model needed for
   provenance, causality claims, dependencies, use/last-use, supersession,
   rollback, and graph-to-workflow reconstruction. Separate observation from
   inference and approval.
10. **Decision rights** — provide a compact RACI/authority matrix for AI,
    deterministic services, independent checkers, domain experts, and Lowell.
    Identify anything that should remain categorically prohibited.
11. **Red-team and premortem** — list at least 15 realistic failure modes,
    including slow organizational failure: capability accumulation without use,
    notification fatigue, stale memory, evaluator drift, optimizer overfitting,
    runaway token spend, self-preservation incentives, and false certainty.
12. **Phased delivery** — propose the safest sequence with exit evidence, kill
    criteria, and what must stay dormant at each phase. Assume only one build and
    one bounded pilot may be active.
13. **Acceptance harness** — give synthetic adversarial tests and falsifiers for
    the architecture, including a case where no change is the correct answer.
14. **One-human cockpit** — show the minimum weekly view and exact conditions for
    interrupting the operator outside normal review.
15. **Convergence questions** — ask no more than seven questions whose answers
    could materially change the design. Do not ask for information already given.
16. **Recommended disposition** — `proceed_to_phase_1`, `revise_and_recheck`, or
    `stop`; list the exact blocking changes.

### Evidence standard

Distinguish established practice, peer-reviewed evidence, promising recent
research, inference, and speculation. Link primary sources for claims that
materially affect architecture. Do not treat benchmark gains, citations,
novelty, model confidence, or graph centrality as proof of downstream value.
State where evidence is weak or contradictory.

### Constraints

- Do not implement, run code, create accounts, activate schedules, contact
  anyone, or recommend silent autonomous self-modification.
- Do not assume a particular model vendor survives.
- Do not make Fable a standing recurring dependency.
- Do not solve token cost by omitting independent validation on consequential
  changes; instead route proportionally.
- Do not require the operator to monitor dashboards daily.
- Keep the default system quiet; `preserve_current` is valid.
- Every proposed mutation needs exact scope, consequence, evidence, independent
  review, human gate, expiry, and rollback.

End with a compact table: `Design B element | keep/change/remove | rationale |
blocking before Phase 1`.

---

## Return path

Return text only. Lowell or DAD—not Fable—may save the answer as a separate,
dated artifact. Do not overwrite this prompt or the candidate plan. DAD should
record: Fable model/runtime, date, sanitized packet digest, response pointer,
strongest disagreement, accepted/rejected changes, resolver, independent recheck,
and Lowell's final decision.
