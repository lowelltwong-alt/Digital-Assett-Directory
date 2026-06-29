# Cross-Repo Workflow Asset Patterns

Status: curated generated-candidate synthesis from local-only workflow sweeps.

This note records reusable workflow assets found across the current local catalog. It does not
promote source repo claims to truth, does not import private data, and does not authorize mutation
of Logos, LawFirm OS, Mock Trial, FMG, or any other source repository.

## Sweep Inputs

- Current DAD catalog: local Git Projects source, GitHub disabled.
- Generated reports:
  - `processed/reports/workflow_sweeps/workflow_sweeps_index.md`
  - `processed/reports/workflow_sweeps/workflow_usefulness_review.md`
  - `processed/reports/asset_family_recognition.md`
  - `processed/reports/logos_asset_family_candidates.md`
  - `processed/reports/worktree_archaeology.md`
  - `processed/reports/root_cause_lesson_candidates.md`
- Read-only source sampling from active/canonical docs and code, not scraped row data.

## High-Leverage Patterns

### Source-Faithful Chunking Gate System

Seed examples:

- Logos Scripture Graph chunking rules and reviewed gold.
- Mock Trial `legal_v1` chunking workflow.

Reusable shape:

```text
raw source custody
-> normalized source layer
-> source-faithful chunk layer
-> independent validator
-> coverage audit
-> A/B retrieval gate
-> graph/vector/retrieval promotion gate
```

Use when:

- a repo converts source material into chunks, passages, rows, claims, or retrieval records;
- downstream graph/vector/agent work depends on chunk correctness;
- a chunker can pass retrieval while silently dropping coverage.

Do not use as-is when:

- source text is not authoritative or does not need custody;
- the task is only exploratory summarization;
- there is no evaluation set or coverage audit.

Danger if misapplied:

- A good retrieval score can hide missing rows, unfaithful text, source drift, or contaminated
  graph facts.

What makes it valuable:

- Logos adds reviewed-gold and route-isolation discipline.
- Mock Trial adds legal-source custody, coverage invariants, source-faithfulness validation, and
  A/B retrieval proof.

### Reviewed Gold And Review Packet System

Seed examples:

- Logos `eval/chunking_gold/` manifests, review packet index, and stress atlas.
- DAD Phase 2 calibration review packets.

Reusable shape:

```text
candidate hard case
-> review packet
-> human-reviewed expected behavior
-> executable manifest/test
-> output-changing work allowed only for reviewed scope
```

Use when:

- generated output can look plausible while being wrong;
- route, chunk, score, or model behavior needs calibrated examples;
- hard negatives matter.

Do not use as-is when:

- review examples are not representative;
- records are characterization-only, pending review, or stress cases without promotion.

Danger if misapplied:

- A pending packet can be mistaken for approved gold.

### Exception-Lake Error-Correction Loop

Seed examples:

- LawFirm Exception Lake runtime.
- Logos governance architecture exception-lake integration.
- Nevada professional-intelligence exception lake pattern.

Reusable shape:

```text
exception event
-> append-only evidence
-> pressure vector / repeated-pattern summary
-> adaptation proposal
-> promotion decision
-> source authority updated only after governance
```

Use when:

- failures, conflicts, retrieval misses, or workflow gaps repeat;
- source truth must not be mutated from runtime evidence;
- agents need a learning loop that preserves provenance.

Do not use as-is when:

- the event class or route authority is unclear;
- raw sensitive payloads would be stored;
- there is no reviewer capacity for pressure vectors.

Danger if misapplied:

- Runtime observations can accidentally become canon, or private data can be retained in the lake.

### AI Work-Cycle Governance System

Seed examples:

- DAD preflight/midflight/postflight.
- LawFirm Runtime AI Work Cycle.
- Logos no-context review and rule registry.

Reusable shape:

```text
orient
-> confirm authority
-> classify task route
-> choose mode
-> apply stop conditions
-> execute inside scope
-> validate
-> report outcome
-> capture reusable lesson
```

Use when:

- agents work across repos or authority planes;
- a task can mutate contracts, generated outputs, governance, routes, scores, or source data;
- a future agent needs no-context reconstruction.

Do not use as-is when:

- the task is a trivial isolated query;
- the current repo has no authority boundaries or generated outputs.

Danger if misapplied:

- Too much process can bury small work, but too little process lets agents silently cross source,
  authority, privacy, or promotion boundaries.

### Cross-Repo Authority And Data-Flow Map

Seed examples:

- LawFirm OS intake and exception-lake data-flow maps.
- Logos boundary/source contract with Scripture graph.
- DAD source-of-truth and design-authority registries.

Reusable shape:

```text
planes/repos
-> authority order
-> allowed directions
-> forbidden writes
-> principal objects
-> handoff/admission path
-> human gates
```

Use when:

- several repos form one system;
- one repo consumes another repo's schemas, contracts, routes, or source records;
- copied local worktrees could be confused with canonical GitHub-tracking checkouts.

Do not use as-is when:

- there is only one repo and no external authority;
- all data is exploratory and disposable.

Danger if misapplied:

- A vertical demo, runtime observation, local copy, or generated export can be mistaken for
  platform canon.

### Calibration And A/B Gate System

Seed examples:

- DAD proposal/asset calibration.
- Mock Trial chunk retrieval A/B and Monte Carlo calibration.
- FMG quality metric and validation surfaces.

Reusable shape:

```text
baseline
-> candidate method
-> shared eval set
-> coverage/safety gates
-> metric report
-> human calibration
-> decision packet
```

Use when:

- a default, threshold, score, chunker, retriever, model, or workflow route is being chosen;
- two plausible approaches exist;
- false positives and false negatives matter.

Do not use as-is when:

- the eval set is stale, biased, or tuned after seeing results;
- a green metric ignores source coverage or safety.

Danger if misapplied:

- A/B can optimize the wrong target and make a weaker system look better.

### Security Scanner And Quarantine System

Seed examples:

- LawFirm skills-registry static and semantic-intent scanners.
- LawFirm AI ingestion quarantine policy.
- DAD public feedback and public-safe source sweep rules.

Reusable shape:

```text
incoming asset
-> static path/text scan
-> semantic intent scan
-> risk score
-> quarantine/reject/manual-review/safe-for-eval
-> governed promotion
```

Use when:

- importing skills, prompts, tools, feedback, workflow files, or external code;
- public PRs or untrusted generated content can influence the repo;
- content might include prompt injection, exfiltration, persistence, unsafe tools, or secrets.

Do not use as-is when:

- source ownership and license are unknown;
- binary/opaque payloads need separate sandbox analysis.

Danger if misapplied:

- Treating scanner output as proof of safety can miss attacks; treating every finding as fatal can
  block useful assets.

## Recommended Phase Order

1. Governance and authority maps first.
2. Learning loops and exception lakes second.
3. Chunking/evaluation/gold systems third.
4. Calibration/A-B and QA gates fourth.
5. Security/quarantine import systems fifth.
6. Variant/delta clusters and worktree archaeology last, so temp copies do not dominate asset value.

## Next Human Review Batch

Review these first as solid reusable assets:

- Logos chunking rules registry.
- Logos chunking gold README and review packet index.
- LawFirm Exception Lake data-flow map.
- LawFirm runtime AI work cycle.
- LawFirm AI ingestion quarantine policy and skills scanner.
- Mock Trial legal chunking workflow.
- Mock Trial AI workflow operating manual.
- DAD proposal calibration workflow.

Review questions:

- Which patterns should become first-class DAD contracts rather than docs?
- Which are safe for public DAD documentation?
- Which require a private asset catalog because examples contain legal/person/source data?
- Which should surface in preflight only for high-risk work to avoid excess ceremony?
