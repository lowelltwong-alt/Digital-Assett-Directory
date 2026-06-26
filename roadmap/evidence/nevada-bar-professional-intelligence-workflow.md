# Nevada Bar Professional Intelligence Workflow Evidence

Status: curated evidence for a reusable generated-candidate workflow asset.

Source sweep:

- Local source label: `Nevada Bar Results`; absolute path intentionally omitted from tracked evidence.
- Generated report: `processed/reports/external_sweeps/nevada_bar_results_usefulness_sweep.md` (ignored by Git)
- Generated candidates: `processed/reports/external_sweeps/nevada_bar_results_usefulness_candidates.json` (ignored by Git)
- Public-safe boundary: `docs/NEVADA_BAR_PUBLIC_SAFE_IMPORT_POLICY.md`
- Safe sweep method: `docs/PUBLIC_SAFE_SOURCE_SWEEPS.md`

## What Was Detected

The Nevada Bar Results folder contains a composite professional recruiting intelligence workflow:

- official source intake from Nevada bar-result files and public directory evidence;
- stable person, credential, organization, alias, source, and revision identity layers;
- source snapshots and extraction audit trails;
- law-firm roster and attorney-bio extraction;
- public enrichment lanes for LinkedIn-like evidence without default profile scraping;
- identity review queues and exception-lake design;
- opportunity signals for acquisition, group liftout, succession, rising talent, and market context;
- deterministic roadmap state and test gates;
- derived exports for stakeholder review.

The most reusable asset is not one file. It is the ordered workflow and its sub-assets:

```text
official source truth
-> identity and credential model
-> organization and roster discovery
-> bio/profile extraction
-> conservative identity resolution
-> exception review
-> candidate opportunity signals
-> reviewed exports
-> roadmap/test gates
```

## Classification

| Candidate | Classification | Reason |
|---|---|---|
| Authority-first enrichment workflow | review first | Prevents enrichment sources from becoming source truth. |
| Person vs credential identity architecture | review first | Generalizes to any durable external credential or official id. |
| Canonical SQLite database and schema | preserve as source-evidence architecture | High value, but row-level data is sensitive and should not be broadly imported by default. |
| Deterministic roadmap/check gate | review first | Concrete active-project governance loop. |
| LinkedIn exception lake | review first but unproven | Strong architecture; current snapshot has zero exception rows. |
| Opportunity signal taxonomy | review first with caution | Useful review-lead model; false-positive risk if detached from caveats. |
| Insurance-defense master lane | review first after abstraction | Strong national-discovery workflow; domain labels need generalization. |
| Firm-specific scrapers | variant/delta review | Valuable pattern library but likely duplicated and bespoke. |
| Generated exports | generated output, not canon | Useful for UX/product shape but derived from SQLite. |
| Pycache and bulk snapshots | exclude from default review | Noise unless doing provenance archaeology. |

## Review Decision

Promote as a candidate workflow family for future DAD recognition:

```text
professional_recruiting_intelligence_workflow_system
```

This does not promote or import Nevada Bar row data, attorney records, recruiting leads,
LinkedIn matches, acquisition signals, or liftout signals to truth. It only records the
workflow shape and recognition pattern for future AI builders.

## Reuse Conditions

Reuse this workflow when a repo or folder has:

- official population or credential sources;
- public enrichment sources that are weaker than the official source;
- entity matching across people, credentials, organizations, aliases, and profiles;
- review-lead signals that can create false positives if treated as facts;
- generated exports from a canonical data store;
- handoff, roadmap, test, or audit gates.

Do not reuse as-is when:

- there is no official source of truth;
- the project permits enrichment sources to define the core population;
- row-level personal data cannot be safely indexed or summarized;
- source terms forbid the intended data collection;
- human review is unavailable for ambiguous identity or recruiting signals.

## Future DAD Work

- Teach recognizers to identify this pattern across repos from table names, docs, scripts, tests,
  and output lanes.
- Emit composite workflow candidates with sub-assets and candidate edges.
- Add privacy-aware source-scan policy before importing row-level public-person data.
- Cluster and delta-review scraper variants before reusing code.
- Calibrate opportunity-signal usefulness and false-positive rates before default scoring.
