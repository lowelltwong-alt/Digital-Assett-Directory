# AI Table Of Contents

This file is the branching map after `AI_FRONT_DOOR.md`. Each first-class entry
uses this deterministic row shape:

| Path | What it is | Tags | Use when |
|---|---|---|---|
| `AI_FRONT_DOOR.md` | Single AI entrypoint and authority route. | `front_door`, `authority` | Always read first. |

## Tag Index

| Tag | Meaning |
|---|---|
| `front_door` | Start-here docs and machine entrypoints. |
| `authority` | Source-of-truth, design authority, and trust-boundary rules. |
| `knowledge_graph` | Graph model, ontology, taxonomy, edge vocabulary, and graph reports. |
| `schema` | Structured record contracts. |
| `registry` | Controlled vocabularies and deterministic IDs. |
| `workflow` | Repeatable work patterns, checklists, and pipelines. |
| `learning_loop` | Lessons, feedback, handoff, and pay-forward systems. |
| `security_privacy` | Secret, PII, prompt-injection, and source-boundary controls. |
| `roadmap` | Phase gates, acceptance evidence, and roadmap state. |
| `validation` | Tests, validators, and verification reports. |
| `generated_output` | Ignored processed outputs that are useful but not source truth. |

## Front Doors And Authority

| Path | What it is | Tags | Use when |
|---|---|---|---|
| `AI_FRONT_DOOR.md` | Single AI entrypoint, required read order, work routes, stop conditions, and validation baseline. | `front_door`, `authority`, `workflow` | Always read first before material work. |
| `AGENTS.md` | Standing operating contract for AI agents. | `front_door`, `authority`, `workflow` | You need mandatory preflight, postflight, edit, and validation rules. |
| `MACHINE_NAVIGATION_MANIFEST.json` | Machine-readable entrypoint and registry map. | `front_door`, `registry`, `validation` | A tool or agent needs structured navigation. |

## Knowledge Graph Entrypoints

| Path | What it is | Tags | Use when |
|---|---|---|---|
| `docs/KNOWLEDGE_GRAPH_MODEL.md` | Human-readable graph model and authority boundary. | `knowledge_graph`, `authority` | You need to understand graph meaning and limitations. |
| `registry/edge-type-registry.json` | Controlled edge vocabulary. | `knowledge_graph`, `registry` | You add, validate, or interpret graph relationships. |
| `registry/asset-pattern-registry.json` | Controlled high-leverage asset pattern vocabulary. | `knowledge_graph`, `registry`, `workflow` | You classify workflows, composite assets, or reusable systems. |
| `processed/graph/graph.json` | Generated graph output. | `knowledge_graph`, `generated_output` | You need candidate graph evidence; never treat it as truth. |

## Architecture And Workflows

| Path | What it is | Tags | Use when |
|---|---|---|---|
| `docs/ARCHITECTURE.md` | High-level system shape. | `workflow`, `authority` | You need the repo architecture. |

## Contracts

| Path | What it is | Tags | Use when |
|---|---|---|---|
| `schemas/example.schema.json` | Example structured record contract. | `schema` | You change or validate records of this type. |

## Operations And Validation

| Path | What it is | Tags | Use when |
|---|---|---|---|
| `docs/OPERATIONS.md` | Operational runbook. | `workflow`, `validation` | You run repo commands. |
| `python -m pytest` | Test baseline. | `validation` | You verify code changes. |
