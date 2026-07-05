# Harness Vs Deterministic Enforcement

Status: reviewed DAD decision model for choosing harnesses, advisory checks,
and hard deterministic enforcement.

## Core Lesson

Do not turn every good idea into a hard validator. When DAD or a repo discovers
an issue, repeated pattern, coding improvement, or decision risk, the default
question is:

```text
Can this become a reusable harness first?
```

Harnesses are better when the system is still learning. They preserve examples,
synthetic cases, prompts, scripts, evals, false positives, false negatives, and
context deltas without forcing every repo to obey a brittle rule.

Deterministic enforcement is better when drift would create real harm and the
property can be checked with low ambiguity.

## Decision Flow

1. Start with a harness candidate for new, ambiguous, repeated, or high-leverage
   issues.
2. Link the candidate to an existing parent harness family when one exists.
3. Use the harness to collect examples, counterexamples, validation commands,
   false-positive notes, and false-negative notes.
4. Promote only the stable, low-noise parts to deterministic enforcement.
5. Downgrade noisy enforcement back into a harness, report, or preflight warning.

The useful pattern is a harness tree, not a pile of unrelated checks:

```text
master harness program
-> coding improvement harnesses
-> repo governance/mail harnesses
-> exception and fix-outcome harnesses
-> issue-specific subharnesses
-> synthetic cases and real-world evidence
-> only selected stable checks become hard enforcement
```

## Use A Harness When

- The issue is novel, evolving, or not yet well understood.
- A future agent would benefit from examples and counterexamples.
- The check needs model judgment, review quality, or context interpretation.
- The same problem appears in multiple repos but with different local shapes.
- You need to test whether agents notice and emit the right DAD mail without
  human rescue.
- You need to compare solutions, tactics, prompts, or implementation orders.
- False positives would create noise or slow work.
- The work is a coding improvement, research lead, AI behavior pattern, or
  professional-practice adaptation.

## Use Deterministic Enforcement When

- A violation can leak secrets, private data, credentials, or public-release
  unsafe material.
- A repo write boundary, protected-repo boundary, or human approval gate could
  be bypassed.
- A generated report could look current while using stale inputs.
- A schema, registry, manifest, route, or required metadata field must stay
  machine-readable for other tools.
- A missing check creates false green, false matched parity, or false release
  confidence.
- The property is cheap, stable, and unambiguous to check.
- The enforcement has a clear escape hatch, audit trail, or downgrade path.

## Red, Amber, Green Risk Lens

Use risk and data sensitivity to break ties.

| Tier | Meaning | Default posture |
| --- | --- | --- |
| Green | Public-safe, low blast radius, reversible, no sensitive data. | Harness, advisory report, or normal tests. Hard enforcement only for exact machine contracts. |
| Amber | Internal or cleaned data, important workflow, moderate blast radius, some ambiguity. | Harness plus review checkpoints. Enforce only source boundaries, required metadata, and stale/false-green blockers. |
| Red | Private, confidential, restricted, protected, public-release, secrets, legal/governance boundary, or high blast radius. | Deterministic gates for movement/release/boundaries, plus harnesses for learning and improvement. |

Risk is not evenly distributed across a repo. A public README typo is green; a
mail packet from a private repo to a public-facing repo is red; a generated
report used for planning may be amber until it becomes release evidence.

## Toss-Up Factors

When it is unclear, choose the lighter thing that still protects the boundary.

Favor a harness when:

- the rule is still changing;
- false positives are likely;
- the value is in learning, examples, or future agent behavior;
- the evidence is mostly qualitative;
- a repo can safely decide locally.

Favor deterministic enforcement when:

- the failure is hard to notice later;
- the check is objective;
- downstream repos or agents depend on the exact contract;
- the cost of a miss is higher than the cost of a block;
- the rule protects secrets, source authority, public release, or human gates.

## Preflight, Midflight, Postflight

Preflight should ask whether a task needs:

- no new harness or enforcement;
- a harness candidate;
- an existing harness run;
- advisory reporting only;
- deterministic enforcement.

Midflight should revisit this when an issue becomes harder than expected, when a
failure repeats, or when a check starts to feel bulky or noisy.

Postflight should record:

- whether a harness helped or was missing;
- whether deterministic enforcement was too heavy or too weak;
- whether the issue should become a subharness;
- which parent harness family it belongs under;
- what example, counterexample, or synthetic case should be saved.

## Repo Transmission

Repos should send DAD candidate mail when they discover:

- a repeated issue that should become a harness;
- a deterministic check that is useful but too heavy or noisy;
- a hard gate that prevented harm;
- a hard gate that blocked useful work without enough benefit;
- a red/amber/green sensitivity pattern DAD should route differently.

Send short metadata, paths, hashes, examples, validation commands, and context
limits. Do not send secrets, raw private rows, copied source blobs, or long logs.

## Anti-Bloat Rule

Harnesses should be real, but they should not become theater. A useful harness
has at least one of:

- a runnable check;
- a prompt or review rubric;
- synthetic cases;
- real-world examples with safe pointers;
- false-positive and false-negative notes;
- a promotion or downgrade path.

If none of those exist yet, record a small harness idea or DAD need rather than
creating a large empty folder.

## Authority Boundary

This model is advisory routing for DAD and enrolled repos. It does not override
local repo authority, source-of-truth rules, public/private release gates,
human approvals, or required validation.
