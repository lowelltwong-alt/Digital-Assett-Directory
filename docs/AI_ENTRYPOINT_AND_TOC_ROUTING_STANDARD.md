# AI Entrypoint And TOC Routing Standard

## Purpose

Every AI-assisted repository needs one deterministic place for an agent to start,
then a table of contents that says not only what exists, but when to look
further. File names are not enough. Agents need role, tags, authority posture,
and routing triggers.

This standard makes repo navigation a reusable digital asset:

```text
single front door -> authority stack -> AI TOC branch -> graph entrypoints -> task-specific evidence
```

## Single Front Door Rule

Use `AI_FRONT_DOOR.md` as the single AI entrypoint.

The front door must include:

- repository identity and authority boundaries;
- required read order;
- work routes;
- AI TOC branch pointer;
- knowledge-graph entrypoints;
- preflight and postflight requirements;
- stop-and-report triggers;
- validation baseline.

Do not create competing start-here files unless `AI_FRONT_DOOR.md` points to
them as branches. A branch can specialize navigation, but it cannot replace the
front door.

## AI TOC Row Contract

Every first-class AI TOC entry should use this row shape:

| Field | Requirement |
|---|---|
| Path | Stable file path, registry path, command, or generated surface. |
| What it is | One short role description. Say what the thing does for the repo. |
| Tags | Lower-snake-case routing tags, comma separated. |
| Use when | A concrete trigger for reading or running it. |

Optional row fields for larger repos:

- `Authority posture`: source truth, reviewed rule, candidate evidence, generated output, or template.
- `Do not use when`: common misrouting case.
- `Owner`: human, repo, or system responsible for changing it.

## Required Branches

A mature AI TOC should contain these branches when the repo has matching assets:

- front doors and authority;
- architecture and workflows;
- knowledge graph entrypoints;
- contracts and schemas;
- controlled vocabularies and registries;
- operations and validation;
- roadmap and evidence;
- generated outputs;
- reference material.

Small repos can merge branches, but should keep the same row fields.

## Tag Method

Tags are routing aids, not proof of truth. Use a small, repeated vocabulary.
Prefer tags that answer "why would an agent open this?"

Recommended base tags:

- `front_door`
- `authority`
- `knowledge_graph`
- `schema`
- `registry`
- `workflow`
- `learning_loop`
- `calibration`
- `security_privacy`
- `roadmap`
- `generated_output`
- `validation`
- `public_safe`
- `cross_repo`

Add domain tags only when they route future work better than generic tags.

## Knowledge Graph Entrypoints

If a repo has a knowledge graph, the front door and AI TOC must point to the
graph entrypoints. In DAD, those are:

- `docs/KNOWLEDGE_GRAPH_MODEL.md`
- `ontology/digital-asset-ontology.ttl`
- `ontology/taxonomy.skos.ttl`
- `registry/edge-type-registry.json`
- `registry/asset-pattern-registry.json`
- `registry/context-tag-registry.json`
- generated graph and report surfaces under `processed/`

Graph outputs remain candidate evidence. A graph edge, centrality score,
similarity score, or generated pattern does not prove source truth or value.

## Deterministic Build Procedure

When adding this standard to another repo:

1. Create or update `AI_FRONT_DOOR.md`.
2. Add the required read order and authority boundary.
3. Create or update `AI_TABLE_OF_CONTENTS.md`.
4. Convert first-class entries to the row contract.
5. Add a tag index with the repo's accepted routing tags.
6. Add knowledge-graph entrypoints if the repo has graph, ontology, taxonomy,
   registry, or generated relationship outputs.
7. Add a machine-readable manifest if agents or tools need structured routing.
8. Record a lesson or evidence note explaining why the navigation standard was
   added.
9. Validate links, schemas, registries, and repo-specific tests.

## Applies When

Use this standard when:

- creating or revising AI entrypoints;
- creating or revising an AI table of contents;
- adding knowledge graph, ontology, taxonomy, registry, or generated report
  surfaces;
- building a repo template for future AI work;
- a future agent is likely to miss important docs because filenames are too
  vague.

## Does Not Apply When

Do not spend this ceremony when:

- the task is a trivial typo in an unrelated file;
- the repo is a tiny scratch project with no persistent AI use;
- a current navigation standard already provides equivalent path, role, tag,
  and use-when fields;
- the work only records raw observations and does not affect future routing.

## Danger If Misapplied

If ignored, future agents may miss authority rules, skip graph context, apply a
lesson out of context, or treat generated outputs as truth. If over-applied, the
repo can become noisy and slow to navigate. Keep the standard compact and make
rows earn their place.

## Future Improvement

A later validator can check that AI TOC rows use the required columns, that front
door graph entrypoints exist, and that generated-output rows are tagged
`generated_output`.
