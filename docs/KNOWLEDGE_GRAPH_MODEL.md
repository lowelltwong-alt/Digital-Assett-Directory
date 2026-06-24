# Knowledge Graph Model

## Node families

- digital assets: repositories, files, schemas, workflows, tests, datasets, prompts, skills, agents, decisions, lessons, research;
- revisions: content-specific observations;
- activities: scans, builds, validations, research runs;
- agents: human or software actors when known;
- alerts, activation triggers, and synergy candidates.

## Edge discipline

Every generated edge carries:

- edge type;
- method;
- confidence;
- evidence;
- scan ID;
- review status.

A `related_to` edge means bounded similarity, not sameness. A `complements` edge means a plausible combination, not an implemented integration. A `satisfies_need` edge means lexical/metadata evidence that one capability may address another asset's need.

## Provenance mapping

The ontology aligns conceptually with W3C PROV-O:

- assets and revisions are `prov:Entity`-like objects;
- scans and transformations are `prov:Activity`-like objects;
- people and software tools are `prov:Agent`-like objects;
- derivation, generation, use, and attribution should remain traceable.

## Version and staleness

Staleness is type-specific and reviewable. A ten-year-old decision may remain valid; a six-month-old provider integration may be stale. The catalog records both age and the reason for the freshness classification.
