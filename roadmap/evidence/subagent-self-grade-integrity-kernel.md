# Subagent Self-Grade Integrity Kernel Decision

Date: 2026-07-13
Risk tier: high
Status: P1 trust-boundary hardening applied after an independent unsafe verdict;
second fresh-eyes review and supervised trial still pending.

## Decision

Adopt a separate categorical integrity layer over the existing attempt-evaluation
records. Keep existing attempt scores as bounded observations, treat
self-assessment as an actor-claimed prediction with non-caller-controlled receipt chronology, select an
explicit domain profile, and route candidate interventions to the smallest
plausible agent or workflow layer. Calculate no new composite score and forbid
cross-domain leaderboards.

## Blast radius

- schemas for self assessment, profile registry, integrity report, and optional
  empty improvement recommendations;
- schema registry and global validation;
- subagent evaluation CLI and status;
- the continuous-improvement skill and searchable subagent role pack;
- capability and agent-skill registries;
- future subagent orchestrators that choose to capture self predictions;
- generated candidate reports and human review practices.

No routine, global hook, plugin, external send, automatic agent edit, automatic
model reroute, promotion, or workflow mutation is enabled.

## Options

### A. Extend the existing post-hoc numeric self score

Hypothesis: a richer common rubric and more independent scores improve agents.

Rejected because the acting agent can optimize the visible reward; post-outcome
introspection is not calibrated prediction; absolute score deltas lose optimism
direction; common-mode inflation survives agreement; and a universal score
cannot represent financial model validity, archaeology provenance, and
deterministic parser behavior comparably.

### B. Separate integrity meta-review with universal loop and domain overlays

Hypothesis: pre-outcome predictions plus evaluator audit, fault attribution,
held-out comparison, and a preserve-simple path improve decisions while
preventing grade gaming.

Chosen as the smallest candidate slice. It is additive, read-only at review time,
uses strict records, and preserves existing source authority.

### C. Defer all evaluation changes

Hypothesis: current parent and independent reviews are sufficient until more
attempt data exists.

Rejected because current records cannot distinguish hash integrity from evidence
truth, post-hoc scores from predictions, independent identity from blind and
lineage independence, or agent defects from workflow and evaluator defects.
Deferral would preserve a known false-confidence channel.

## Implementer red team

- An agent can backdate its claimed recorded time. Mitigation: user packets and the
  Python API cannot supply receipt time. The receipt proves chronology only; without
  orchestrator sealing and actor attestation, outcome blindness and self identity remain
  unverified.
- A reviewer can be a different actor but share parent, prompt, model, data, or
  incentive lineage. Mitigation: report every available lineage signal and mark
  unavailable dimensions explicitly.
- A human label can be mistaken for domain expertise. Mitigation: current
  domain-expert count remains zero until a qualification attestation exists.
- A caller can select the wrong domain profile. Mitigation: selection is explicit
  unverified candidate input, not automatic inference.
- A hash can be treated as proof. Mitigation: the report explicitly separates
  record integrity from evidence truth and copies no source grades.
- Every failure can still be routed to instruction change. Mitigation: target
  vocabulary includes tool, input, data, workflow, handoff, evaluator, profile,
  downstream specialist, preserve simple, and observe more.
- The new loop can burden simple agents. Mitigation: the workflow wrapper owns
  prediction and checks; no-change and downstream composition are valid outcomes.
- A candidate no-change decision can freeze a hidden defect. Mitigation: the current
  implementation fails this path closed because runtime actor binding and locked criterion
  outcome records do not yet exist. Future activation also requires negative cases,
  latency/cost evidence, held-out shadow, a human gate, and rollback.

## Independent Review Adjudication

The first blind implementation review returned **unsafe** and reproduced four P1 defects:
caller-controlled Python receipt time, prediction packets never compared with criterion
outcomes, self-asserted evaluator verification, and preserve-simple nomination without
required deterministic evidence. The hardening pass removed the receipt override, renamed
the result to receipt chronology, requires verified runtime/provider provenance for an
evaluator attempt, detects review cycles longer than two nodes, and blocks calibration and
preserve-simple until external actor and criterion-outcome records exist.

Causal layer localization, per-attempt domain binding, executable domain contracts, privacy
classification of arbitrary prose, and real blind/domain-qualified attestations remain
incomplete. Vocabulary is not treated as implemented capability.

## Premortem

Assume this failed in six months. Likely causes:

- self assessments were captured after the work and treated as calibration;
- profile selection became automatic keyword classification;
- reviewer identity checks were mistaken for true independence;
- agents optimized familiar tests and holdouts leaked;
- domain-expert requirements became a checkbox without qualification evidence;
- the integrity report became another dashboard no one used;
- prompt and process overhead outweighed decision value for simple roles;
- candidate dispositions were automatically applied without causal evidence; or
- cross-domain counts quietly became rankings.

## Bounded comparison

Compare the prior workflow and the new integrity wrapper on a small cohort of:

- one deterministic role with seeded boundary failures;
- one open-ended coding or architecture role;
- one financial-algorithm fixture with deliberate leakage and cost errors; and
- one evidence-heavy historical fixture with provenance and
  observation/inference errors.

Shared acceptance criteria:

- catches seeded false grades and evaluator defects;
- does not leak source scores or private prose;
- attributes at least the deliberately isolated workflow and evaluator failures;
- preserves the deterministic role when no change is warranted;
- routes domain-expert requirements without claiming expertise;
- no automatic write or promotion;
- stable material fingerprint;
- bounded latency and review burden; and
- rollback to the previous skill and schema references is straightforward.

## Rollback

Remove the three new schema registrations, the profile registry, integrity
module and CLI commands, role-pack revision, research/evidence navigation rows,
and restore the previous skill-library entry and optional-recommendation schema
line. Raw self assessments remain immutable candidate evidence but are ignored by
the prior workflow.

## Kill criteria

Stop or revert if the implementation:

- accepts caller-supplied runtime receipt time;
- reports a post-outcome self grade as calibrated;
- treats a hash, agreement, or model identity as evidence truth;
- produces an aggregate cross-domain score or ranking;
- infers and approves a domain profile automatically;
- claims a human reviewer is a qualified expert without attestation;
- automatically changes agents, prompts, workflows, or routes;
- cannot nominate no change for an appropriate simple role;
- leaks private payloads or absolute source paths; or
- materially increases simple-role latency without better decisions.

## Human and fresh-eyes gates

The implementation remains candidate. Independent review must check the schema,
forged-grade cases, lineage logic, preserve-simple threshold, privacy boundary,
and whether a smaller or safer hybrid is preferable. A supervised operator trial
must precede activation in recurring subagent workflows.

The focused independent re-review completed after the integrity hardening pass
changed the verdict from unsafe to an acceptable candidate. The reviewer found
no remaining priority-one defect in the scoped implementation. Priority-two
limitations remain: domain contracts and blind-review attestations are still
candidate metadata rather than independently executable proof, and causal
attribution remains conservative until per-attempt evidence is stronger.
